#!/usr/bin/env python3
"""Bench: Mehrbild-Aufnahme (SE Inspect A2).

Prueft an synthetischen Bildern:
  1. Rauschen sinkt mit N etwa wie 1/sqrt(N)          (Sensorrauschen)
  2. Flackernder Blendfleck wird im Mittel ruhig       (LED-Flackern)
  3. Bewegung verwirft den Puffer: kein Geisterbild    (Teil wird aufgelegt)
  4. Mit dem Leerbild-Verfahren: Blendfleck-Flackern erzeugt mit Mittel
     keine Falschteile mehr, ohne Mittel schon
Ausgabe: MEHRBILD_OK oder FEHLER.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np                       # noqa: E402
from vorsa.mehrbild import Mehrbild      # noqa: E402

rng = np.random.default_rng(7)
fehler = 0


def ok(bed, text, wert=None):
    global fehler
    print(("ok  " if bed else "FEHL") + f" {text}" + (f"  {wert}" if wert is not None else ""))
    if not bed:
        fehler += 1


def szene(h=240, w=320):
    b = np.full((h, w, 3), (40, 90, 60), np.uint8)          # gruenes Band
    b[80:160, 100:220] = (20, 20, 20)                        # schwarze Karte
    b[95:115, 120:200] = (235, 235, 235)                     # weisses Etikett
    return b


def verrauscht(b, sigma):
    return np.clip(b.astype(np.float32) + rng.normal(0, sigma, b.shape), 0, 255).astype(np.uint8)


# 1) Rauschen sinkt mit N
basis = szene()
for n in (1, 4, 8, 16):
    m = Mehrbild(anzahl=n, bewegung_max=50)
    aus = None
    for _ in range(n):
        aus = m.verarbeite(verrauscht(basis, 8.0))
    rest = float(np.abs(aus.astype(np.float32) - basis).mean())
    if n == 1:
        rest1 = rest
    ok(rest <= rest1 / np.sqrt(n) * 1.35 + 0.3, f"N={n:2d}: Restrauschen {rest:.2f} (N=1: {rest1:.2f})")

# 2) Flackernder Blendfleck wird ruhig
m = Mehrbild(anzahl=8, bewegung_max=50)
werte = []
for i in range(16):
    b = basis.copy()
    hell = 255 if i % 2 == 0 else 170                        # Fleck flackert
    b[30:46, 40:56] = hell
    aus = m.verarbeite(b)
    werte.append(float(aus[38, 48].mean()))
schwank_roh = 255 - 170
schwank_mittel = max(werte[8:]) - min(werte[8:])
ok(schwank_mittel < schwank_roh * 0.2, f"Blendfleck: Schwankung roh {schwank_roh} -> gemittelt {schwank_mittel:.1f}")

# 3) Bewegung verwirft den Puffer
m = Mehrbild(anzahl=8, bewegung_max=2.5)
for _ in range(8):
    m.verarbeite(basis)
leer = np.full_like(basis, (40, 90, 60))                      # Teil weggenommen
aus = m.verarbeite(leer)
ok(m.gemittelt == 1 and np.array_equal(aus, leer), f"Szenenwechsel: Puffer verworfen, gemittelt={m.gemittelt}, kein Geisterbild")
for _ in range(3):
    aus = m.verarbeite(leer)
ok(m.gemittelt == 4, f"stehende neue Szene fuellt wieder auf (gemittelt={m.gemittelt})")

# 4) Mit Leerbild-Verfahren: Flackern erzeugt ohne Mittel Falschteile, mit Mittel nicht
try:
    from vorsa.segmentation import foreground_mask
    from vorsa.config import SegmentationParams
    params = SegmentationParams()
    leerbild = np.full((240, 320, 3), (40, 90, 60), np.uint8)
    leerbild[30:46, 40:56] = 210                                # Fleck im Leerbild: mittlere Helligkeit
    roh_treffer = 0
    mit_treffer = 0
    m = Mehrbild(anzahl=8, bewegung_max=50)
    for i in range(24):
        b = leerbild.copy()
        b[30:46, 40:56] = 255 if i % 2 == 0 else 165
        b = verrauscht(b, 2.0)
        mk_roh = foreground_mask(b, params, background_ref=leerbild)
        roh_treffer += int(mk_roh[30:46, 40:56].mean() > 127)
        g = m.verarbeite(b)
        if i >= 8:
            mk = foreground_mask(g, params, background_ref=leerbild)
            mit_treffer += int(mk[30:46, 40:56].mean() > 127)
    ok(roh_treffer > 0, f"ohne Mittel: flackernder Fleck wird {roh_treffer}/24 mal Vordergrund (erwartet > 0)")
    ok(mit_treffer == 0, f"mit Mittel (N=8): Fleck wird {mit_treffer}/16 mal Vordergrund (Ziel 0)")
except Exception as exc:
    ok(False, f"Leerbild-Verfahren: {exc}")

# 5) Laufzeit
import time
m = Mehrbild(anzahl=4, bewegung_max=50)
gross = np.zeros((1080, 1920, 3), np.uint8)
t0 = time.perf_counter()
for _ in range(10):
    m.verarbeite(gross)
ms = (time.perf_counter() - t0) / 10 * 1000
ok(ms < 250, f"Laufzeit 1080p je Bild (x86) {ms:.1f} ms  (Richtwert < 60 ms ohne Last)")

print("FEHLER:", fehler)
print("MEHRBILD_OK" if not fehler else "MEHRBILD_FEHLER")
sys.exit(1 if fehler else 0)
