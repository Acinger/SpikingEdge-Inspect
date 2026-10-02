"""Pruefstand Karten-Waechter (1.9.36): eine Karte wirft beim Abgleich -
der Verbund antwortet mit den uebrigen, meldet die Stoerung einmal,
prueft nach der Sperre erneut und nimmt die Karte wieder auf."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from vorsa.edge_learn import EdgeLerner

class Karte:
    def __init__(self, antwort, kaputt=False):
        self.antwort = np.asarray(antwort, np.float32); self.kaputt = kaputt; self.n = 0
    def forward(self, x):
        self.n += 1
        if self.kaputt:
            raise RuntimeError("DMA wait completion timed out")
        return self.antwort[None, None, None, :]

L = EdgeLerner()
L.karten_sperre_s = 0.3
ereignisse = []
L.on_karte_fehler = lambda ki, grund, wieder: ereignisse.append((ki, wieder))
C = 2
k0 = Karte([5, 1, 2, 0]); k1 = Karte([1, 9, 0, 0], kaputt=True); k2 = Karte([0, 0, 7, 1])
L.modelle = [k0, k1, k2]; L.modell = k0
x = np.zeros((1, 4, 4, 2), np.uint8)
pots, sieger = L._verbund_sieger(x, C)
assert list(pots) == [5.0, 7.0], pots
assert sieger[0] == 2, sieger
assert L.karten_stand[1]["status"] == "gestoert" and ereignisse == [(1, False)], (L.karten_stand[1], ereignisse)
# waehrend der Sperre wird Karte 1 NICHT angefragt
n1 = k1.n
for _ in range(5): L._verbund_sieger(x, C)
assert k1.n == n1, "Karte 1 waehrend der Sperre angefragt"
assert L.karten_stand[0]["aufrufe"] == 6 and L.karten_stand[0]["letzte_ms"] is not None
# Sperre abgelaufen, Karte noch kaputt -> ein Versuch, wieder Sperre, KEIN zweiter Alarm
time.sleep(0.35); L._verbund_sieger(x, C)
assert k1.n == n1 + 1 and ereignisse == [(1, False)], (k1.n, ereignisse)
# Karte repariert -> nach der Sperre wieder drin, Wiederaufnahme gemeldet
k1.kaputt = False; time.sleep(0.35)
pots, sieger = L._verbund_sieger(x, C)
assert list(pots) == [9.0, 7.0] and sieger == (1, 1, 9.0), (pots, sieger)
assert L.karten_stand[1]["status"] == "aktiv" and ereignisse[-1] == (1, True), ereignisse
# alle kaputt -> Fehler nach oben
for k in (k0, k1, k2): k.kaputt = True
time.sleep(0.35)
try:
    L._verbund_sieger(x, C); raise SystemExit("FEHLT: kein Fehler bei totalem Ausfall")
except RuntimeError as exc:
    assert "keine Karte antwortet" in str(exc), exc
u = L.karten_uebersicht()
assert all(u[i]["status"] == "gestoert" for i in range(3))
print("WAECHTER_OK", {i: (u[i]["status"], u[i]["aufrufe"], u[i]["fehler"]) for i in u})
