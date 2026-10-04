#!/usr/bin/env python3
"""Bench 1.1-A/B: Vorschlaege aus unbekannten Teilen + Auto-Schwelle.

  python3 tools/test_selbstlernen.py

1. Synthetische "unbekannte" Teile (3 Formen x verschiedene Lage/Groesse/Helligkeit,
   dazu Einzelstuecke) -> drei Gruppen, Reinheit >= 90 %, Einzelstuecke bleiben einzeln.
2. Auto-Schwelle: konstruierter Testsatz mit bekannten Konfidenzen -> erwarteter Vorschlag.
"""
import math, random, sys, tempfile
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vorsa.selbstlernen import vorschlaege  # noqa: E402
from vorsa.schwelle import auswerten, kurve  # noqa: E402

FEHLER = []


def ok(b, t):
    print(("ok   " if b else "FEHL ") + t)
    if not b:
        FEHLER.append(t)


rnd = random.Random(7)


def teil(form, groesse=1.0, winkel=0, hell=200, farbe=None, versatz=(0, 0)):
    b = np.full((240, 240, 3), (52, 60, 58), np.uint8)
    b = cv2.add(b, np.random.default_rng(rnd.randint(0, 9999)).integers(0, 8, b.shape, dtype=np.uint8))
    c = (120 + versatz[0], 120 + versatz[1])
    col = farbe or (hell, hell, hell)
    M = cv2.getRotationMatrix2D(c, winkel, groesse)
    def pts(p):
        p = np.array(p, np.float32)
        return cv2.transform(p[None], M)[0].astype(np.int32)
    if form == "kreis":
        cv2.circle(b, c, int(45 * groesse), col, -1)
        cv2.circle(b, c, int(15 * groesse), (52, 60, 58), -1)     # Scheibe mit Loch
    elif form == "rechteck":
        cv2.fillPoly(b, [pts([(70, 95), (170, 95), (170, 145), (70, 145)])], col)
    elif form == "L":
        cv2.fillPoly(b, [pts([(80, 60), (100, 60), (100, 160), (170, 160), (170, 180), (80, 180)])], col)
    elif form == "stern":
        p = [(120 + 60 * math.cos(a * math.pi / 5) * (1 if a % 2 == 0 else .4), 120 + 60 * math.sin(a * math.pi / 5) * (1 if a % 2 == 0 else .4)) for a in range(10)]
        cv2.fillPoly(b, [pts(p)], col)
    elif form == "dreieck":
        cv2.fillPoly(b, [pts([(120, 50), (190, 180), (50, 180)])], (40, 40, 200))
    return b


d = Path(tempfile.mkdtemp())
wahr = {}
for form, n in (("kreis", 8), ("rechteck", 7), ("L", 6)):
    for i in range(n):
        b = teil(form, groesse=rnd.uniform(.85, 1.15), winkel=rnd.uniform(0, 360), hell=rnd.randint(170, 225),
                 versatz=(rnd.randint(-15, 15), rnd.randint(-15, 15)))
        name = f"2026_{form}_{i}_unbekannt.jpg"
        cv2.imwrite(str(d / name), b)
        wahr[name] = form
for form in ("stern", "dreieck"):
    name = f"2026_{form}_0_unbekannt.jpg"
    cv2.imwrite(str(d / name), teil(form))
    wahr[name] = form
cv2.imwrite(str(d / "2026_leer_unbekannt.jpg"), np.full((240, 240, 3), (52, 60, 58), np.uint8))
wahr["2026_leer_unbekannt.jpg"] = "leer"

v = vorschlaege(d, sorted(wahr))
gr = v["gruppen"]
print("    Gruppen:", [(g["anzahl"], sorted({wahr[x] for x in g["dateien"]})) for g in gr], "einzeln", v["einzeln"], "ohne Umriss", v["ohne_umriss"])
ok(3 <= len(gr) <= 4, f"drei Formen -> 3 (hoechstens 4) Gruppen ({len(gr)}); Aufteilen ist harmlos, Mischen nicht")
rein = []
for g in gr:
    formen = [wahr[x] for x in g["dateien"]]
    haupt = max(set(formen), key=formen.count)
    rein.append(formen.count(haupt) / len(formen))
ok(all(r >= 0.9 for r in rein), "Reinheit je Gruppe >= 90 %: " + ", ".join(f"{r:.0%}" for r in rein))
abgedeckt = sum(max([wahr[x] for x in g["dateien"]].count(f) for f in ("kreis", "rechteck", "L")) for g in gr)
abgedeckt = sum(len(g["dateien"]) for g in gr if len({wahr[x] for x in g["dateien"]}) == 1)
ok(abgedeckt >= 0.85 * 21, f"mindestens 85 % der 21 Wiederholer zugeordnet ({abgedeckt})")
ok(v["ohne_umriss"] == 1, "leeres Bild: kein Umriss, kein Vorschlag")
ok(all(g["bild"] in g["dateien"] for g in gr), "Repraesentant aus der Gruppe")

# ---------------------------------------------------------------- Auto-Schwelle
erg = []
for i in range(40):                         # einzeln, richtig benannt, Konfidenz 0.6-0.95
    erg.append({"soll": ["A"], "ist": [("A", 0.6 + 0.35 * i / 39)]})
for i in range(10):                         # Fremdteile, faelschlich als A mit 0.40-0.62
    erg.append({"soll": ["unbekannt"], "ist": [("A", 0.40 + 0.22 * i / 9)]})
for i in range(5):
    erg.append({"soll": [], "ist": []})
k = kurve(erg)
ok(k["vorschlag"] == 0.63, f"Vorschlag 0.63 (knapp ueber dem hoechsten Fremdteil 0.62): {k['vorschlag']}")
p = k["vorschlag_punkt"]
ok(p["falsch_sicher"] == 0 and p["unbekannt_erkannt"] == [10, 10], "beim Vorschlag: 0 falsch-sicher, 10/10 Fremdteile unbekannt")
ok(p["treffer_einzeln"][0] == 40 - sum(1 for i in range(40) if 0.6 + 0.35 * i / 39 < 0.63), "Treffer = bekannte Teile ueber der Schwelle")
ok(auswerten(erg, 0.5)["falsch_sicher"] == 5, "bei 0.50: 5 Fremdteile falsch-sicher")
ok(len(k["punkte"]) == 14 and k["hinweis"] == "", "Kurve 0.30..0.95, kein Hinweis bei 55 Szenen mit Fremdteilen")

print("FEHLER: " + " | ".join(FEHLER) if FEHLER else "SELBSTLERNEN_OK")
sys.exit(1 if FEHLER else 0)
