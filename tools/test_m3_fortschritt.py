#!/usr/bin/env python3
"""Bench 1.9.71: Freistellen fuer M3 schnell + mit Fortschritt; Gesamtfortschritt des Laufs.
  python3 tools/test_m3_fortschritt.py"""
import sys, time, tempfile, types
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np, cv2  # noqa: E402
from vorsa.dataset_build import freistellen_aus_zustand, FREISTELL_MAX_PX  # noqa: E402
from vorsa.augment import AugmentConfig  # noqa: E402
from vorsa.train_job import _gesamt, _phase_mit_gesamt  # noqa: E402
from vorsa.jobs import Lauf  # noqa: E402

FEHLER = []
def ok(b, t):
    print(("ok   " if b else "FEHL ") + t)
    if not b: FEHLER.append(t)

# Kunst-Zustand: 2 Objekte x 12 Fotos (687 px, helles Blatt, dunkles Teil), Augmentierung wie auf dem Pi (32 Varianten)
def foto(seed):
    r = np.random.default_rng(seed); b = np.full((687, 687, 3), 235, np.uint8)
    cx, cy = int(r.integers(220, 460)), int(r.integers(220, 460))
    cv2.rectangle(b, (cx - 90, cy - 60), (cx + 90, cy + 60), (40, 40, 45), -1)
    return b
class K:  # Klasse
    def __init__(s, i, n):
        s.id, s.name, s.prototypen = i, n, [f"{n}_{j}" for j in range(12)]
        s.augment = AugmentConfig(spiegeln_horizontal=True, spiegeln_vertikal=True, drehen_90=False, drehen_frei=True, drehschritte=8)
        s.negativ = False
class Z:
    def __init__(s): s.klassen = {0: K(0, "A"), 1: K(1, "B")}
    def prototyp_bild(s, d): return foto(hash(d) % 1000)
z = Z()
ok(z.klassen[0].augment.anzahl_varianten() == 32, "Augmentierung wie auf dem Pi: 32 Varianten je Foto")

ticks = []
t0 = time.perf_counter()
teile, namen, warn = freistellen_aus_zustand(z, True, fortschritt=lambda i, n: ticks.append((i, n)))
dauer = time.perf_counter() - t0
ok(len(ticks) == 24 and ticks[0] == (1, 24) and ticks[-1] == (24, 24), f"Fortschritt je Foto gemeldet ({len(ticks)} Meldungen)")
ok(namen == ["A", "B"] and not warn, f"2 Objekte, keine Warnung ({warn})")
ok(len(teile) == 24 * 3, f"nur Original + Spiegelungen: {len(teile)} Vorlagen (24 Fotos x 3), nicht x32")
ok(all(max(t.bild.shape[:2]) <= FREISTELL_MAX_PX for t in teile), f"Vorlagen hoechstens {FREISTELL_MAX_PX} px")
ok(dauer < 20, f"24 Fotos in {dauer:.1f} s (vorher: Dutzende Minuten auf dem Pi)")
print(f"    {dauer / 24 * 1000:.0f} ms je Foto hier; auf dem Pi grob x4")

# Gesamtfortschritt: monoton ueber die Phasen
folge = [("Fotos freistellen", 0, 0), ("Fotos freistellen", 12, 24), ("Fotos freistellen", 24, 24), ("TensorFlow laden", 0, 0),
         ("Modell bauen", 0, 0), ("Training", 1, 300), ("Training", 150, 300), ("Training", 300, 300), ("Quantisieren", 0, 0),
         ("Nach Akida umwandeln", 0, 0), ("Auf den AKD1500 legen", 0, 0)]
werte = [_gesamt(p, (i / n) if n else 0.0) for p, i, n in folge]
ok(all(b >= a for a, b in zip(werte, werte[1:])), "Gesamtfortschritt steigt monoton: " + " ".join(f"{round(w * 100)}" for w in werte))
ok(abs(werte[1] - 0.075) < 0.01 and abs(werte[6] - 0.56) < 0.01 and werte[-1] >= 0.96, "Gewichte: halbes Freistellen ~8 %, halbes Training ~56 %, Chip-Phase >= 96 %")
ok(0.2 < _gesamt("Irgendwas aus dem Unterprozess", 0.0) < 0.3, "unbekannte Phase landet im Trainingsbereich")
l = Lauf("M3-Training") if "name" in Lauf.__init__.__code__.co_varnames else Lauf()
_phase_mit_gesamt(l, "Training", 150, 300)
d = l.as_dict()
ok(abs(d["gesamt"] - 0.56) < 0.01 and d["phase"] == "Training" and d["schritt"] == 150, f"Lauf.as_dict liefert gesamt={d['gesamt']}")
l.fertig, l.ok = True, True
ok(l.as_dict()["gesamt"] == 1.0, "fertig + ok -> 100 %")
print("FEHLER: " + " | ".join(FEHLER) if FEHLER else "M3_FORTSCHRITT_OK"); sys.exit(1 if FEHLER else 0)
