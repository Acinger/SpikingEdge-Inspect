#!/usr/bin/env python3
"""Testsatz auswerten (SE Inspect A7): Q1-Q4 als Zahlen.

Laesst jede Szene des Testsatzes durch DIESELBE Erkennungskette wie der
Server (Verarbeitung im Profil stationaer, Mehrbild aus, gelernter Stand aus
<daten>) und vergleicht das Ist mit dem Soll.

  python3 tools/eval_testsatz.py --daten vorsa_daten [--schwelle 0.6] [--aus bericht.md]

Ohne Karte: VORSA_CPU_LERNEN=1 (CPU-Ersatz) - dann gelten die Zahlen fuer die
Software-Kette, nicht fuer die Hardware; der Bericht sagt das.

Kennzahlen (Definitionen in SE_INSPECT_1_0_SPEC.md, Abschnitt 6):
  Q1 falsch-sicher   benannt mit Konfidenz >= Schwelle, aber Name nicht im Soll
  Q2 Treffer einzeln Szenen mit genau einem Soll-Teil: Ist == Soll
  Q3 unbekannt       Szenen mit Soll "unbekannt"/Fremdteil: als unbekannt erkannt
  Q4 Ueberlappung    Szenen mit >= 2 Soll-Teilen: Ist-Multimenge == Soll-Multimenge
  Leer               leere Szenen ohne Falschteil
Schwellenvorschlag: kleinste Schwelle, bei der Q1 <= 0.5 % bleibt.
Ausgabe: Markdown-Bericht + JSON daneben.
"""
import argparse, json, os, sys, time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("VORSA_PROFIL", "stationaer")
if "VORSA_CPU_LERNEN" not in os.environ:
    try:
        import akida  # noqa: F401
    except Exception:
        os.environ["VORSA_CPU_LERNEN"] = "1"

import cv2                                   # noqa: E402
import numpy as np                           # noqa: E402

UNBEKANNT_NAMEN = {"unbekannt", "unknown", "fremd", "fremdteil", "?"}


class BildquelleListe:
    """Liefert ein festes Bild, bis es gewechselt wird - wie ein Tisch."""
    synthetisch = True
    hinweis = ""
    cap = None
    stationaer = False

    def __init__(self, groesse=512):
        self.groesse = groesse
        self._bild = np.zeros((groesse, groesse, 3), np.uint8)
        self.zaehler = 0

    def setze_bild(self, b):
        self._bild = b
        self.zaehler = 0

    def lies(self):
        self.zaehler += 1
        time.sleep(0.01)
        return self._bild.copy()

    def lies_einstellungen(self, hoechstalter=2.0):
        return {}

    def schliesse(self):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--daten", default="vorsa_daten")
    ap.add_argument("--schwelle", type=float, default=None,
                    help="Konfidenzschwelle fuer 'benannt' (Standard: aus pruef.json, sonst 0.55)")
    ap.add_argument("--aus", default=None, help="Bericht (Markdown); Standard <daten>/testsatz/bericht.md")
    ap.add_argument("--frames", type=int, default=6, help="Bilder je Szene bis zum Urteil")
    args = ap.parse_args()

    from vorsa.web import server as srv
    from vorsa.edge_learn import EdgeLerner, CPU_ERSATZ
    from vorsa.testsatz import Testsatz

    ts = Testsatz(args.daten)
    if not ts.szenen:
        print("Testsatz leer - erst Szenen in der Oberflaeche aufnehmen (Pruefung > Testsatz).")
        return 1
    zustand = srv.Zustand(args.daten)
    quelle = BildquelleListe()
    lerner = EdgeLerner(groesse=128)
    lerner.replikation = True
    da, info = lerner.verfuegbar()
    if not da:
        print("Chip-Lernen nicht verfuegbar:", info)
        return 1
    geladen = lerner.laden(args.daten, zustand.fingerabdruck())
    if not geladen.get("ok"):
        print("Gelernter Stand nicht ladbar:", geladen.get("grund"), "- lerne neu aus den Fotos")
    # Die Testbilder SIND der Pruef-Ausschnitt: Fenster auf 100 %, mittig.
    try:
        zustand.bereich_setzen(100.0, 0.5, 0.5)
    except Exception:
        pass
    v = srv.Verarbeitung(quelle, zustand, True, anzeige_groesse=480, lerner=lerner)
    try:
        if not lerner.klassen:
            srv.lernen_beim_start(zustand, lerner)
        if not lerner.klassen:
            print("Nichts gelernt - keine Klassen mit Fotos.")
            return 1
        v.mehrbild.einstellen(anzahl=1)
        zustand.betriebsart = "betreiben"
        schwelle = args.schwelle
        if schwelle is None:
            schwelle = v.konfidenz_schwelle if v.konfidenz_schwelle is not None else 0.55
        neg = v._negativ_namen()

        ergebnisse = []
        for s in ts.szenen:
            b = cv2.imread(str(ts.ordner / s["datei"]))
            if b is None:
                continue
            # Ausschnitt ist quadratisch; die Quelle liefert ihn als ganzes Bild
            quelle.setze_bild(b)
            # auf die Erkennung dieses Bildes warten
            start = quelle.zaehler
            bis = time.time() + 10
            while time.time() < bis and quelle.zaehler < start + args.frames:
                time.sleep(0.03)
            erk = zustand.erkannt or {}
            ist = []
            for o in erk.get("je_objekt") or []:
                name = str(o.get("name") or "")
                konf = float(o.get("anteil") or 0.0)
                if o.get("unbekannt") or o.get("unklar") or name in ("unklar", "unbekanntes Teil", ""):
                    ist.append(("<unbekannt>", konf))
                elif name in neg:
                    ist.append(("<negativ>", konf))
                else:
                    ist.append((name, konf))
            soll = [x for x in (s.get("soll") or [])]
            ergebnisse.append({"id": s["id"], "soll": soll, "ist": ist, "notiz": s.get("notiz", "")})
            print(f"  #{s['id']:04d}  soll={soll or ['leer']}  ist={[f'{n}:{k:.2f}' for n, k in ist]}")

        # -- Kennzahlen ------------------------------------------------
        def benannt(ist, schw):
            return [n for n, k in ist if not n.startswith("<") and k >= schw]

        def auswerten(schw):
            fs = 0; fs_moegl = 0
            q2_ok = q2_n = q3_ok = q3_n = q4_ok = q4_n = leer_ok = leer_n = 0
            konf = Counter()
            for e in ergebnisse:
                soll = e["soll"]; ist = e["ist"]
                soll_namen = [x for x in soll if x.lower() not in UNBEKANNT_NAMEN]
                soll_unb = [x for x in soll if x.lower() in UNBEKANNT_NAMEN]
                ben = benannt(ist, schw)
                # Q1: benannte Namen, die nicht im Soll sind
                fs_moegl += len(ist)
                fs += sum(1 for n in ben if n not in soll_namen)
                ist_namen = [n if (not n.startswith("<") and k >= schw) else "<unbekannt>" for n, k in ist]
                if not soll:
                    leer_n += 1; leer_ok += int(not ben)
                elif soll_unb and not soll_namen:
                    q3_n += 1; q3_ok += int(not ben and len(ist) >= 1)
                elif len(soll_namen) == 1 and not soll_unb:
                    q2_n += 1
                    treffer = Counter(ist_namen) == Counter(soll_namen)
                    q2_ok += int(treffer)
                    for n in ben:
                        konf[(soll_namen[0], n)] += 1
                    if not ben:
                        konf[(soll_namen[0], "<unbekannt>")] += 1
                else:
                    q4_n += 1
                    q4_ok += int(Counter(ist_namen) == Counter(soll_namen + ["<unbekannt>"] * len(soll_unb)))
            return {"schwelle": schw, "q1_falsch_sicher": fs, "q1_bezug": fs_moegl,
                    "q1_rate": (fs / fs_moegl if fs_moegl else 0.0),
                    "q2": (q2_ok, q2_n), "q3": (q3_ok, q3_n), "q4": (q4_ok, q4_n), "leer": (leer_ok, leer_n),
                    "konfusion": konf}

        haupt = auswerten(schwelle)
        vorschlag = None
        for sw in [x / 100 for x in range(30, 100, 1)]:
            if auswerten(sw)["q1_rate"] <= 0.005:
                vorschlag = sw
                break

        # -- Bericht ---------------------------------------------------
        aus = Path(args.aus) if args.aus else ts.ordner / "bericht.md"
        pct = lambda a, b: f"{a}/{b} ({(a / b * 100) if b else 0:.0f} %)"
        z = []
        z.append(f"# Testsatz-Auswertung · {time.strftime('%Y-%m-%d %H:%M')}")
        z.append("")
        z.append(f"Build {srv.BUILD} · {len(ergebnisse)} Szenen · Klassen {lerner.klassen} · "
                 f"Rechenweg: {'CPU-Ersatz (Software, keine Hardware-Aussage)' if CPU_ERSATZ else 'AKD1500'} · "
                 f"Verbund {lerner.verbund_modus} · Schwelle {schwelle:.2f}")
        z.append("")
        z.append("| Kennzahl | Wert | Ziel 1.0 |")
        z.append("|---|---|---|")
        z.append(f"| Q1 falsch-sichere Urteile | {haupt['q1_falsch_sicher']} von {haupt['q1_bezug']} Teilurteilen ({haupt['q1_rate'] * 100:.2f} %) | ≤ 0,5 % |")
        z.append(f"| Q2 Treffer einzeln liegend | {pct(*haupt['q2'])} | ≥ 98 % |")
        z.append(f"| Q3 Unbekanntes als unbekannt | {pct(*haupt['q3'])} | ≥ 95 % |")
        z.append(f"| Q4 Mehrere/überlappende Teile korrekt | {pct(*haupt['q4'])} | ≥ 90 % |")
        z.append(f"| Leerer Tisch ohne Falschteil | {pct(*haupt['leer'])} | 100 % |")
        z.append(f"| Schwellenvorschlag (Q1 ≤ 0,5 %) | {('%.2f' % vorschlag) if vorschlag is not None else 'keine Schwelle ≤ 0,99 erreicht Q1'} | — |")
        z.append("")
        if haupt["konfusion"]:
            z.append("## Konfusion (Soll → Ist, einzeln liegende Teile)")
            z.append("")
            z.append("| Soll | Ist | Anzahl |")
            z.append("|---|---|---|")
            for (s_, i_), n in sorted(haupt["konfusion"].items()):
                z.append(f"| {s_} | {i_} | {n} |")
            z.append("")
        z.append("## Szenen")
        z.append("")
        z.append("| # | Soll | Ist | Notiz |")
        z.append("|---|---|---|---|")
        for e in ergebnisse:
            z.append(f"| {e['id']} | {' + '.join(e['soll']) or 'leer'} | "
                     f"{', '.join(f'{n} {k:.2f}' for n, k in e['ist']) or '—'} | {e['notiz']} |")
        aus.write_text("\n".join(z) + "\n", encoding="utf-8")
        (aus.with_suffix(".json")).write_text(json.dumps(
            {"build": srv.BUILD, "cpu_ersatz": CPU_ERSATZ, "schwelle": schwelle, "vorschlag": vorschlag,
             "kennzahlen": {k: v_ for k, v_ in haupt.items() if k != "konfusion"},
             "konfusion": {f"{a}->{b}": n for (a, b), n in haupt["konfusion"].items()},
             "szenen": ergebnisse}, ensure_ascii=False, indent=1), encoding="utf-8")
        print("\n".join(z[:12]))
        print(f"\nBericht: {aus}")
        return 0
    finally:
        v.stoppe()


if __name__ == "__main__":
    raise SystemExit(main())
