#!/usr/bin/env python3
"""Bench 1.9.70: Schwellen-Vorschlag + Kalibrierung je Objekt.

Daten = Testlauf vom Pi am 2026-10-04 (48 Szenen, aus der Anzeige nachgebaut; SD-Karte + Inbusschluessel,
Fremdteile, leere Flaeche), Ist-Werte roh wie gemessen.
  python3 tools/test_kalibrierung.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vorsa.schwelle import auswerten, kurve, kalibrierung_aus, kalibriert, kalibriere_wert  # noqa: E402

FEHLER = []
def ok(b, t):
    print(("ok   " if b else "FEHL ") + t)
    if not b: FEHLER.append(t)

SD, AK, U = "SD CARD", "Allen Key", "<unbekannt>"
E = []
for w in [.61, .59, None, .59, .57, .58, .58, "u53", "u53", .55, .58, .56, .57, .56, None]:
    E.append({"soll": [SD], "ist": [(AK, .63), (AK, .57)] if w is None and len(E) == 2 else
              [(AK, .58), (U, .55)] if w is None else [(U, .53)] if w == "u53" else [(SD, w)]})
for w in [.87, .84, .92, .77, None, .96, .86, .68, .95, .89, .88, .84, "2", .82, "3"]:
    E.append({"soll": [AK], "ist": [(SD, .59), (AK, .81)] if w is None else [(AK, .74), (AK, .75)] if w == "2"
              else [(U, .50), (AK, .85), (AK, .78)] if w == "3" else [(AK, w)]})
E += [{"soll": [AK, SD], "ist": i} for i in [[(SD, .64), (AK, .90)], [(AK, .93), (U, .53)], [(AK, .65), (AK, .82), (U, .53)],
      [(SD, .60), (AK, .85)], [(AK, .73), (SD, .61)], [(SD, .61), (AK, .80), (SD, .65)], [(U, .52), (AK, .81)], [(AK, .73), (SD, .56)]]]
E += [{"soll": [], "ist": i} for i in [[(U, .46), (AK, .65)], [(U, .50), (AK, .62)], [(U, .48)], [], [(U, .45)]]]
E += [{"soll": ["unbekannt"], "ist": i} for i in [[(AK, .62)], [(U, .51)], [(AK, .86)], [(SD, .62)], [(U, .49)]]]
ok(len(E) == 48, f"48 Szenen ({len(E)})")

# alte Regel: kleinste Schwelle mit <= 0,5 % falsch-sicher -> 96 %
alt = next(x / 100 for x in range(30, 100) if auswerten(E, x / 100)["falsch_sicher_rate"] <= 0.005)
tr_alt = auswerten(E, alt)["treffer_einzeln"]
ok(alt >= 0.85 and tr_alt[0] <= 6, f"alte Regel: {alt:.2f}, nur {tr_alt[0]}/{tr_alt[1]} Treffer (auf dem Pi mit allen Szenen: 0,96)")

k = kurve(E)
tr = k["vorschlag_punkt"]["treffer_einzeln"]
ok(not k["ziel_erreicht"] and "Kompromiss" in k["hinweis"], f"neue Regel roh: Kompromiss {k['vorschlag']} ({tr[0]}/{tr[1]} Treffer) und klarer Hinweis")
ok(k["vorschlag"] < alt and tr[0] > tr_alt[0] + 5, "Kompromiss behaelt deutlich mehr Treffer als die alte Regel")

kal = kalibrierung_aus(E)
ok(set(kal) == {SD, AK}, f"Kalibrierung fuer beide Objekte: {kal}")
ok(0.55 <= kal[SD] <= 0.60 and 0.82 <= kal[AK] <= 0.90, "typisch: SD ~0,58, Inbus ~0,86")
ok(abs(kalibriere_wert(SD, kal[SD], kal) - 0.9) < 1e-6 and kalibriere_wert(AK, 1.0, kal) == 1.0, "typischer Treffer -> 90 %, gedeckelt bei 100 %")
ok(kalibriere_wert("neu", 0.4, kal) == 0.4, "Objekt ohne Kalibrierung bleibt roh")

EK = kalibriert(E, kal, unbekannt_ab=0.55)
kk = kurve(EK)
t2 = kk["vorschlag_punkt"]["treffer_einzeln"]
print(f"    kalibriert: Vorschlag {kk['vorschlag']}, Treffer {t2[0]}/{t2[1]}, falsch-sicher {kk['vorschlag_punkt']['falsch_sicher_rate']:.3f}, Ziel {kk['ziel_erreicht']}")
sd_scores = [i[0][1] for e in EK if e["soll"] == [SD] for i in [e["ist"]] if len(i) == 1 and i[0][0] == SD]
ok(min(sd_scores) >= 0.8, f"SD-Treffer kalibriert >= 80 % (min {min(sd_scores):.2f})")
gleich = auswerten(EK, 0.80)["treffer_einzeln"][0]
ok(gleich >= 20, f"bei 80 % gemeinsamer Schwelle: {gleich}/30 Treffer (roh: {auswerten(E, 0.80)['treffer_einzeln'][0]}/30)")
ok(t2[0] >= tr[0], "kalibriert mindestens so viele Treffer wie roh")
# edge_learn wendet die Kalibrierung an
import numpy as np  # noqa: E402
from vorsa.edge_learn import EdgeLerner  # noqa: E402
el = EdgeLerner.__new__(EdgeLerner)
el.klassen = [SD, AK]
el.kalibrierung = {}
ok(list(el._kalibriere(np.array([0.58, 0.40]))) == [0.58, 0.40], "ohne Kalibrierung: roh")
el.kalibrierung = kal
a = el._kalibriere(np.array([0.58, 1.0]))
ok(abs(a[0] - 0.9) < 0.001 and a[1] == 1.0, f"Lerner kalibriert: {list(np.round(a, 3))}")
el._kalib_sperre = True
ok(list(el._kalibriere(np.array([0.58, 1.0]))) == [0.58, 1.0], "Sperre (Testlauf): roh trotz Kalibrierung")
el._kalib_sperre = False
print("FEHLER: " + " | ".join(FEHLER) if FEHLER else "KALIBRIERUNG_OK"); sys.exit(1 if FEHLER else 0)
