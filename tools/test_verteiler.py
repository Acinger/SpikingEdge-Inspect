#!/usr/bin/env python3
"""Bench: Kartenverteiler (SE Inspect A4) mit simulierten Karten.

  1. _verbund_planen: repliziert vs verteilt
  2. 8 Auftraege auf 4 Karten: Zeit ~ Maximum statt Summe (>= 2.5x schneller)
  3. Karte faellt mitten im Auftrag aus: alle Ergebnisse da, Karte gestoert,
     Auftrag auf anderer Karte wiederholt, Alarm genau einmal
  4. verteilter Verbund -> sequentieller Rueckfall, kein Thread
  5. Hypothesen + Verteiler zusammen: eine Runde, Ergebnis unveraendert
Ausgabe: VERTEILER_OK oder FEHLER.
"""
import sys, time, threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np                              # noqa: E402
from vorsa.edge_learn import EdgeLerner         # noqa: E402
from vorsa.verteiler import Kartenverteiler     # noqa: E402

fehler = 0


def ok(bed, text):
    global fehler
    print(("ok  " if bed else "FEHL") + " " + text)
    if not bed:
        fehler += 1


# 1) Planung
L = EdgeLerner(groesse=128)
L.replikation = True
p = L._verbund_planen(4, kleinste=5, groesste=30)
ok(p == {"modus": "repliziert", "karten": 4, "je_karte": 30}, f"Plan repliziert: {p}")
L.replikation = False
p = L._verbund_planen(4, kleinste=3, groesste=30)
ok(p == {"modus": "verteilt", "karten": 3, "je_karte": 10}, f"Plan verteilt (kleinste Klasse begrenzt Karten): {p}")


# Simulierte Karten: forward dauert 20 ms; Karte 2 kann auf Befehl werfen
class KarteSim:
    def __init__(self, nr, C=3, n=4):
        self.nr = nr; self.C = C; self.n = n; self.kaputt = False; self.aufrufe = 0
    def forward(self, x):
        self.aufrufe += 1
        if self.kaputt:
            raise RuntimeError("DMA wait completion timed out")
        time.sleep(0.02)
        pots = np.zeros((1, 1, 1, self.C * self.n), np.int32)
        pots[0, 0, 0, 0] = 90 + self.nr          # Klasse 0 gewinnt, Karte sichtbar
        return pots


def lerner_sim(repliziert=True):
    l = EdgeLerner(groesse=128)
    l.klassen = ["A", "B", "C"]
    l.modelle = [KarteSim(i) for i in range(4)]
    l.modell = l.modelle[0]
    l.verbund_modus = "repliziert" if repliziert else "verteilt"
    l.replikation = repliziert
    class B: num_weights = 100
    l.bericht = B()
    l._silhouette = lambda bild, maske=None: np.ones((48, 48, 2), np.uint8)
    l.warum = lambda s: None
    alarme = []
    l.on_karte_fehler = lambda ki, grund, wieder: alarme.append((ki, grund, wieder))
    return l, alarme


def bewerte_fuer(l):
    def bewerte(box, kontur=None, ki=None):
        erg = l.erkenne_auf_karte(np.zeros((64, 64, 3), np.uint8), None, ki) if ki is not None \
            else l.erkenne(np.zeros((64, 64, 3), np.uint8), None)
        return (float(erg["sicherheit"]), erg) if erg else None
    return bewerte


# 2) parallel ~ Maximum statt Summe
l, alarme = lerner_sim(True)
v = Kartenverteiler(l)
viele = v.bewerte_viele(bewerte_fuer(l))
auftraege = [(None, None)] * 8
t0 = time.perf_counter(); aus = viele(auftraege); dt = (time.perf_counter() - t0) * 1000
ok(len(aus) == 8 and all(a is not None for a in aus), f"8 Ergebnisse ({v.stand['modus']}, {v.stand['karten']} Karten)")
ok(dt < 160 / 2.5, f"8 Auftraege auf 4 Karten: {dt:.0f} ms (sequentiell waeren ~160 ms)")
ok(sorted(m.aufrufe for m in l.modelle) == [2, 2, 2, 2], f"gleichmaessig verteilt: {[m.aufrufe for m in l.modelle]}")
ok(set(e[1]["potentiale"][0] for e in aus) == {90, 91, 92, 93}, "jede Karte hat geantwortet (Potentiale 90..93)")

# 3) Karte 2 faellt waehrend des Pakets aus
l.modelle[2].kaputt = True
t0 = time.perf_counter(); aus = viele(auftraege); dt = (time.perf_counter() - t0) * 1000
ok(len(aus) == 8 and all(a is not None for a in aus), "Ausfall Karte 2: trotzdem 8 Ergebnisse")
ok(not l.karte_nutzbar(2), "Karte 2 vom Waechter gesperrt")
ok(len(alarme) == 1 and alarme[0][0] == 2 and alarme[0][2] is False, f"Alarm genau einmal: {alarme}")
ok(v.stand["wiederholt"] >= 1, f"Auftraege wiederholt: {v.stand['wiederholt']}")
aus2 = viele(auftraege)
ok(v.stand["karten"] == 3 and all(a is not None for a in aus2), f"naechstes Paket nur auf {v.stand['karten']} Karten, vollstaendig")
ok(all(e[1]["potentiale"][0] != 92 for e in aus2), "gesperrte Karte wird nicht mehr gefragt")

# 4) verteilter Verbund -> sequentiell
l2, _ = lerner_sim(False)
v2 = Kartenverteiler(l2)
viele2 = v2.bewerte_viele(bewerte_fuer(l2))
t0 = time.perf_counter(); aus = viele2(auftraege[:4]); dt = (time.perf_counter() - t0) * 1000
ok(v2.stand["modus"] == "sequentiell" and len(aus) == 4, f"verteilt: sequentiell ({dt:.0f} ms fuer 4 Auftraege ueber 4 Karten)")
ok(dt > 4 * 4 * 20 * 0.8, "jeder Auftrag fragt alle Karten (Verbund)")

# 5) Hypothesen + Verteiler: eine Runde
from vorsa import hypothesen as HY
from vorsa.detection import Detection, OrientedBox
import cv2
l3, _ = lerner_sim(True)
v3 = Kartenverteiler(l3)
dets = [Detection(box=OrientedBox(100 + 60 * i, 100, 50, 40, 0), contour=None) for i in range(3)]
best, info = HY.hypothesen_waehlen(dets, (300, 400), v3.bewerte_viele(bewerte_fuer(l3)), 4.0)
ok(best is not None and info["runden"] >= 1 and v3.stand["parallel"] >= 3, f"Hypothesen ueber Verteiler: {best.name}, {info['runden']} Runde(n), {v3.stand['parallel']} parallel")

print("FEHLER:", fehler)
print("VERTEILER_OK" if not fehler else "VERTEILER_FEHLER")
sys.exit(1 if fehler else 0)
