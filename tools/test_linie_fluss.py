"""Pruefstand fuer den Fluss-Takt der Linie (1.9.33), ohne Hardware.

Ablauf, den der Bediener erwartet: Band laeuft; ein Teil in der
Anlieferung haelt es kurz zum Pruefen; dann faehrt es weiter, bis ein
Teil in der Abholung liegt (Arm); jedes weitere Teil in der Anlieferung
haelt es erneut. Einzel-Takt (alter Weg) bleibt erhalten."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vorsa.linie import LinienSteuerung   # noqa: E402

L = LinienSteuerung(); L.takt = "fluss"; L.aktivieren(True)
t = [1000.0]; ph = []
def tick(objs, dt=0.1):
    t[0] += dt; L.tick(objs, True, jetzt=t[0])
    s = (L.phase, L.band.laeuft)
    if not ph or ph[-1] != s: ph.append(s)
def an(name="SD"): return {"name": name, "x": 0.15, "y": 0.6, "sicher": 0.9}
def ab(name="SD"): return {"name": name, "x": 0.8, "y": 0.8, "sicher": 0.9}
unb_an = {"name": None, "x": 0.15, "y": 0.6}
unb_ab = {"name": None, "x": 0.8, "y": 0.8}

for _ in range(3): tick([])
assert L.phase == "lauf" and L.band.laeuft, "Band laeuft leer los"
for _ in range(15): tick([an()])
assert L.geprueft == 1 and L.phase == "lauf", "1. Teil geprueft, weiter"
for _ in range(10): tick([an()])
assert L.geprueft == 1, "dasselbe Teil beim Wegfahren nicht doppelt"
for _ in range(10): tick([])
for _ in range(15): tick([an("Ring")])
assert L.geprueft == 2 and L.phase == "lauf", "2. Teil geprueft"
# 1. Teil erreicht die Abholung, waehrend der Ring noch in der Anlieferung liegt
for _ in range(6): tick([ab("SD"), an("Ring")])
assert L.phase == "arm" and not L.band.laeuft, L.phase
for _ in range(5): tick([ab("SD"), an("Ring")])
assert L.phase == "arm" and not L.band.laeuft, "Anlieferung wartet, solange der Arm arbeitet"
# Arm raeumt ab: Band laeuft, Ring faehrt aus der Anlieferung, drittes Teil kommt
for _ in range(8): tick([an("Ring")])
assert L.gefoerdert == 1 and L.phase == "lauf", (L.phase, L.gefoerdert)
assert L.geprueft == 2, "Ring nicht ein zweites Mal geprueft"
for _ in range(8): tick([])
for _ in range(15): tick([an("Karabiner")])
assert L.geprueft == 3 and L.phase == "lauf", (L.geprueft, L.phase)
# Unbekanntes Teil in der Anlieferung: Timeout -> unbekannt gebucht, weiter
for _ in range(8): tick([])
for _ in range(60): tick([unb_an])
assert L.geprueft == 4 and L.pruefungen[-1]["urteil"] == "unbekannt" \
    and L.phase == "lauf", (L.geprueft, L.phase)
# Unbekanntes Teil erreicht Abholung -> Stoerung, Band steht; geraeumt -> lauf
for _ in range(20): tick([unb_ab])
assert L.phase == "stoerung" and not L.band.laeuft
for _ in range(10): tick([])
assert L.phase == "lauf" and L.band.laeuft
# Linie aus: Band steht
L.aktivieren(False); tick([])
assert not L.band.laeuft and L.phase == "aus"

# Einzel-Takt: Band startet erst bei benanntem Teil
E = LinienSteuerung(); E.takt = "einzel"; E.aktivieren(True); t[0] = 2000
def tickE(objs): t[0] += 0.1; E.tick(objs, True, jetzt=t[0])
for _ in range(5): tickE([])
assert E.phase == "warte" and not E.band.laeuft
for _ in range(6): tickE([an()])
assert E.phase == "band" and E.band.laeuft

print("Ablauf:", " -> ".join(f"{p}{'>' if b else '|'}" for p, b in ph))
print("FLUSS_OK  geprueft=%d gefoerdert=%d" % (L.geprueft, L.gefoerdert))
