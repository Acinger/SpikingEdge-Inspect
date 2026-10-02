#!/usr/bin/env python3
"""Prueft Prototypen-Lernen direkt auf dem AKD1500 (Akida Edge Learning).

    python3 tools/check_edge_learning.py
    python3 tools/check_edge_learning.py --classes 6 --neurons 20 --shots 5

Hintergrund: VORSA-M3 selbst laesst sich nicht auf dem Chip trainieren - ein
Detektor mit Boxen, Winkeln und Verdeckungsgraden lernt per Rueckpropagierung
auf einem PC. Akida kann aber die LETZTE vollverbundene Schicht auf der
Hardware lernen lassen, aus wenigen Beispielen, in Sekunden.

Das ergibt die Arbeitsteilung:

    VORSA-M3       findet WO etwas liegt   (fest, offline trainiert)
    Edge Learning  sagt WAS es ist         (auf dem Chip, aus Prototypen)

Dieses Skript beantwortet vier Fragen, die die Weboberflaeche spaeter
verspricht - und die niemand raten sollte:

    1. Ist Edge Learning auf DIESEM Chip und dieser MetaTF-Version verfuegbar?
    2. Wie viele Klassen und wie viele Beispiele je Klasse gehen?
    3. Wie lange dauert das Lernen eines Prototyps?
    4. Werden verschiedene Objekte danach tatsaechlich unterschieden?

Die vierte Frage ist die wichtigste. Ein Lernvorgang, der ohne Fehler
durchlaeuft, aber nichts unterscheidet, sieht in einer Oberflaeche genauso
erfolgreich aus wie einer, der funktioniert.
"""
from __future__ import annotations

import argparse
import inspect
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import akida
    AKIDA = True
except Exception as exc:  # pragma: no cover
    akida = None
    AKIDA = False
    _fehler = exc


# ----------------------------------------------------------------------
def api_bericht() -> dict:
    """Was bietet diese MetaTF-Version fuer das Lernen an?"""
    vorhanden = {}
    for name in ("AkidaUnsupervised", "FullyConnected", "InputData",
                 "Model", "LearningType", "compile"):
        vorhanden[name] = hasattr(akida, name)

    print("=== Lern-Schnittstelle ===")
    print(f"MetaTF {getattr(akida, '__version__', '?')}")
    for name, da in vorhanden.items():
        print(f"  {name:<20} {'vorhanden' if da else 'FEHLT'}")

    for methode in ("compile", "fit", "predict_classes", "forward"):
        print(f"  Model.{methode:<14} "
              f"{'vorhanden' if hasattr(akida.Model, methode) else 'FEHLT'}")

    if hasattr(akida, "AkidaUnsupervised"):
        try:
            print(f"\n  Signatur AkidaUnsupervised: "
                  f"{inspect.signature(akida.AkidaUnsupervised)}")
        except (TypeError, ValueError):
            pass
    if hasattr(akida.Model, "fit"):
        try:
            print(f"  Signatur Model.fit:         {inspect.signature(akida.Model.fit)}")
        except (TypeError, ValueError):
            pass
    return vorhanden


# ----------------------------------------------------------------------
def muster(klasse: int, n: int, groesse: int, rng) -> np.ndarray:
    """Erzeugt n Varianten eines unterscheidbaren Musters.

    Absichtlich einfache, klar verschiedene Muster: der Test soll das LERNEN
    pruefen, nicht die Schwierigkeit der Bilder. Wenn schon diese Muster nicht
    getrennt werden, liegt es nicht am Datensatz.
    """
    import cv2
    aus = []
    for _ in range(n):
        img = np.full((groesse, groesse, 3), 20, np.uint8)
        # Leichte Streuung, damit nicht n-mal dasselbe Bild gelernt wird.
        dx, dy = rng.integers(-2, 3, 2)
        m = groesse // 2
        t = int(groesse * 0.30)
        farbe = (255, 255, 255)

        if klasse % 5 == 0:
            cv2.rectangle(img, (m - t + dx, m - t + dy), (m + t + dx, m + t + dy), farbe, -1)
        elif klasse % 5 == 1:
            cv2.circle(img, (m + dx, m + dy), t, farbe, -1)
        elif klasse % 5 == 2:
            cv2.line(img, (dx + 2, dy + 2), (groesse - 3 + dx, groesse - 3 + dy), farbe, 3)
        elif klasse % 5 == 3:
            cv2.rectangle(img, (m - t + dx, m - t // 3 + dy),
                          (m + t + dx, m + t // 3 + dy), farbe, -1)
        else:
            pts = np.array([[m + dx, m - t + dy], [m - t + dx, m + t + dy],
                            [m + t + dx, m + t + dy]], np.int32)
            cv2.fillPoly(img, [pts], farbe)

        # Klassenabhaengige Helligkeit als zusaetzliches Merkmal
        img = np.clip(img.astype(np.int16) * (0.55 + 0.09 * (klasse % 5)), 0, 255)
        aus.append(img.astype(np.uint8))
    return np.stack(aus)


def _rumpf_schichten(m, groesse: int) -> None:
    m.add(akida.InputConvolutional(
        input_shape=(groesse, groesse, 3), filters=16, kernel_size=(3, 3),
        kernel_stride=(2, 2), padding=akida.Padding.Same, weights_bits=8,
        activation=True, act_bits=4,
        pool_type=akida.PoolType.Max, pool_size=(2, 2), pool_stride=(2, 2),
        name="stem"))
    m.add(akida.SeparableConvolutional(
        filters=32, kernel_size=(3, 3), kernel_stride=(2, 2),
        padding=akida.Padding.Same, weights_bits=4,
        activation=True, act_bits=1, name="merkmale"))


def _fuelle_rumpf(m, seed: int = 0) -> None:
    """Gleicher Seed = gleiche Gewichte in Rumpf- und Gesamtmodell.

    Nur so misst die Aktivitaetsmessung am Rumpf tatsaechlich das, was spaeter
    in die Lernschicht laeuft.
    """
    rng = np.random.default_rng(seed)
    for layer in m.layers:
        if layer.name == "lernschicht":
            continue
        lim = 127 if layer.name == "stem" else 7
        for vn in list(layer.variables.names):
            cur = np.asarray(layer.get_variable(vn))
            if cur.size == 0:
                continue
            if "weight" in vn:
                mag = rng.integers(1, lim + 1, size=cur.shape)
                sign = rng.choice(np.array([-1, 1]), size=cur.shape)
                layer.set_variable(vn, (mag * sign).astype(cur.dtype))
            elif "act_step" in vn and not np.any(cur):
                layer.set_variable(vn, np.ones_like(cur))


def baue_rumpf(groesse: int):
    """Nur der Merkmalsextraktor - zum Messen, was in die Lernschicht laeuft."""
    m = akida.Model()
    _rumpf_schichten(m, groesse)
    _fuelle_rumpf(m)
    return m


def baue_lernmodell(groesse: int, units: int):
    """Merkmalsextraktor mit lernender Schlussschicht.

    Die Schicht VOR der Lernschicht liefert 1-Bit-Aktivierungen. Akida lernt
    die Schlussschicht mit binaeren Gewichten - dafuer muss ihre Eingabe
    duenn besetzt und binaer sein, sonst lernt sie zwar, unterscheidet aber
    schlecht.
    """
    m = akida.Model()
    _rumpf_schichten(m, groesse)
    m.add(akida.FullyConnected(
        units=units, weights_bits=1, activation=False, name="lernschicht"))
    _fuelle_rumpf(m)
    return m


def lernen_und_pruefen(groesse: int, units: int, C: int, S: int,
                       nw: int, dev, rng) -> tuple:
    """Ein vollstaendiger Lern- und Pruefdurchgang mit gegebenem num_weights.

    Rueckgabe: (Trefferquote, Verwechslungsmatrix, ms je Beispiel).
    """
    model = baue_lernmodell(groesse, units)
    model.map(dev, hw_only=True)
    model.compile(optimizer=akida.AkidaUnsupervised(
        num_weights=nw, num_classes=C, learning_competition=0.1))

    zeiten = []
    for k in range(C):
        x = muster(k, S, groesse, rng)
        t0 = time.perf_counter()
        model.fit(x, np.full(S, k, dtype=np.int32))
        zeiten.append((time.perf_counter() - t0) * 1000 / S)

    verwechslung = np.zeros((C, C), dtype=int)
    richtig = gesamt = 0
    for k in range(C):
        x = muster(k, 4, groesse, rng)
        for v in np.asarray(model.predict_classes(x, num_classes=C)).ravel():
            verwechslung[k, int(v)] += 1
            gesamt += 1
            richtig += int(v) == k
    return richtig / max(gesamt, 1), verwechslung, float(np.mean(zeiten))


# ----------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--classes", type=int, default=5)
    ap.add_argument("--neurons", type=int, default=20,
                    help="Neuronen je Klasse (ENGRAM nutzte 20)")
    ap.add_argument("--shots", type=int, default=5, help="Beispiele je Klasse")
    ap.add_argument("--size", type=int, default=32)
    ap.add_argument("--num-weights", type=int, default=0,
                    help="aktive Verbindungen je Neuron, 0 = automatisch")
    args = ap.parse_args()

    if not AKIDA:
        print(f"MetaTF nicht importierbar: {_fehler}")
        return 1

    api_bericht()
    if not hasattr(akida, "AkidaUnsupervised"):
        print("\nEdge Learning steht in dieser MetaTF-Version nicht zur Verfuegung.")
        print("Damit faellt die Option 'Prototyp aufnehmen und sofort lernen' weg.")
        print("Die Oberflaeche darf sie dann nicht anbieten.")
        return 1

    print()
    C, N, S = args.classes, args.neurons, args.shots
    units = C * N
    print(f"=== Aufbau ===")
    print(f"  {C} Klassen x {N} Neuronen = {units} Einheiten, {S} Beispiele je Klasse")

    geraete = akida.devices()
    if not geraete:
        print("  Kein Geraet gefunden.")
        return 1
    dev = geraete[0]
    rng = np.random.default_rng(1)

    # ------------------------------------------------------------------
    # Was laeuft ueberhaupt in die Lernschicht? Gemessen wird der RUMPF,
    # nicht das Gesamtmodell - dessen Ausgabe ist vor dem Lernen fast leer
    # und ergaebe einen unbrauchbar kleinen Wert fuer num_weights.
    print("\n=== Merkmale vor der Lernschicht ===")
    rumpf = baue_rumpf(args.size)
    proben = np.concatenate([muster(k, 3, args.size, rng) for k in range(C)])
    merkmale = np.asarray(rumpf.forward(proben))
    flach = merkmale.reshape(merkmale.shape[0], -1)
    aktiv = (flach > 0).sum(axis=1)
    print(f"  Merkmalsvektor: {flach.shape[1]} Stellen")
    print(f"  aktiv je Bild:  {aktiv.mean():.0f} im Mittel "
          f"({aktiv.min()} bis {aktiv.max()}), "
          f"Belegung {aktiv.mean()/flach.shape[1]*100:.0f} %")

    if aktiv.mean() < 3:
        print("  ZU WENIG AKTIVITAET. Die Merkmalsschicht feuert kaum -")
        print("  daraus kann keine Lernschicht etwas unterscheiden.")
    elif aktiv.mean() > 0.7 * flach.shape[1]:
        print("  ZU VIEL AKTIVITAET. Fast alles feuert bei jedem Bild,")
        print("  damit sehen alle Klassen gleich aus.")

    # ------------------------------------------------------------------
    # num_weights ist die entscheidende Stellschraube. Statt einen Wert zu
    # raten, werden mehrere durchprobiert - der Lauf dauert Sekunden.
    if args.num_weights > 0:
        kandidaten = [args.num_weights]
    else:
        m = max(int(aktiv.mean()), 2)
        kandidaten = sorted({max(2, m // 4), max(2, m // 2), m,
                             min(m * 2, flach.shape[1])})
    print(f"\n=== Lernen, num_weights aus {kandidaten} ===")

    bestes = None
    for nw in kandidaten:
        try:
            quote, verwechslung, ms = lernen_und_pruefen(
                args.size, units, C, S, nw, dev, rng)
        except Exception as exc:
            print(f"  num_weights={nw:<4} FEHLER: {str(exc)[:80]}")
            continue
        einzig = int((verwechslung.sum(axis=0) > 0).sum())
        print(f"  num_weights={nw:<4} Treffer {quote*100:>3.0f} %  "
              f"{ms:.0f} ms je Beispiel  "
              f"{einzig} verschiedene Antworten von {C}")
        if bestes is None or quote > bestes[0]:
            bestes = (quote, verwechslung, ms, nw)

    if bestes is None:
        print("\nKein Durchgang gelang. Siehe Fehlermeldungen oben.")
        return 1

    quote, verwechslung, ms_je, nw = bestes
    print(f"\n=== Bester Lauf: num_weights={nw} ===")
    print(f"  Trefferquote {quote*100:.0f} %, {ms_je:.0f} ms je Beispiel")
    print("  Verwechslungsmatrix (Zeile = wahr, Spalte = erkannt):")
    for k in range(C):
        print("   ", " ".join(f"{v:>3}" for v in verwechslung[k]))

    einzig = int((verwechslung.sum(axis=0) > 0).sum())
    if einzig == 1:
        print("\n  Das Modell antwortet IMMER dieselbe Klasse. Das ist keine")
        print("  schwache Unterscheidung, sondern gar keine - die Lernschicht")
        print("  bekommt keine brauchbaren Merkmale.")

    zufall = 1.0 / C
    print()
    if quote >= 0.8:
        print(f"BEFUND: Prototypen-Lernen funktioniert ({quote*100:.0f} % gegen "
              f"{zufall*100:.0f} % Zufall).")
        print("Die Oberflaeche darf 'Prototyp aufnehmen und sofort lernen' anbieten.")
        print(f"Richtwerte: {S} Aufnahmen je Objekt, rund {ms_je:.0f} ms je Aufnahme,")
        print(f"num_weights={nw}.")
    elif quote > zufall * 1.5:
        print(f"BEFUND: Es lernt, aber schwach ({quote*100:.0f} %).")
        print("Stellschrauben: num_weights, Neuronen je Klasse, mehr Beispiele -")
        print("und vor allem ein trainierter Merkmalsextraktor statt Zufallsgewichten.")
    else:
        print(f"BEFUND: Keine brauchbare Unterscheidung ({quote*100:.0f} %, "
              f"Zufall waere {zufall*100:.0f} %).")
        print()
        print("Die Schnittstelle funktioniert nachweislich: compile, fit und")
        print("predict_classes laufen fehlerfrei, das Lernen dauert Millisekunden.")
        print()
        print("Was fehlt, ist ein brauchbarer Merkmalsextraktor. Der Rumpf hat")
        print("hier ZUFALLSGEWICHTE - Edge Learning kann nur unterscheiden, was")
        print("die Merkmale hergeben. Es ersetzt kein Training des Rumpfes.")
        print()
        print("Fuer den Betrieb heisst das: erst VORSA-M3 trainieren, dann den")
        print("trainierten Rumpf als Merkmalsgeber fuer die Lernschicht nutzen.")
        print("Die Reihenfolge ist damit vorgegeben - Prototypen-Lernen ist kein")
        print("Ersatz fuer das Training, sondern baut darauf auf.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
