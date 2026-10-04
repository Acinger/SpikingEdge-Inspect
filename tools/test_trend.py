#!/usr/bin/env python3
"""Bench 1.1-C: Journal, Trend je Stunde/Tag, Drift-Warnung.
  python3 tools/test_trend.py"""
import sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vorsa.trend import Journal, auswerten  # noqa: E402

FEHLER = []
def ok(b, t):
    print(("ok   " if b else "FEHL ") + t)
    if not b: FEHLER.append(t)

d = Path(tempfile.mkdtemp())
j = Journal(d)
jetzt = time.mktime(time.localtime()[:3] + (12, 0, 0, 0, 0, -1))   # Mittag: "heute" bleibt heute
# vor 3 Tagen: Training, dann 60 sichere Teile (0.9), 5 unbekannt
t0 = jetzt - 3 * 86400
j.training(t0)
for i in range(60):
    j.teil("gut", "A", 0.90, t0 + 60 + i * 30)
for i in range(5):
    j.teil("unbekannt", "", 0.0, t0 + 2000 + i)
# heute: 50 Teile mit 0.78, 10 unbekannt, 2 Ausschuss
for i in range(50):
    j.teil("gut", "A", 0.78, jetzt - 3000 + i * 30)
for i in range(10):
    j.teil("unbekannt", "", 0.0, jetzt - 1500 + i)
for i in range(2):
    j.teil("ausschuss", "Hintergrund", 0.8, jetzt - 600 + i)
e = j.lesen()
ok(len(e) == 128, f"Journal: 128 Zeilen ({len(e)})")
a = auswerten(e, jetzt)
ok(a["gesamt"] == 127, "127 Teile gesamt")
ok(a["heute"] == {"teile": 62, "gut": 50, "unbekannt": 10, "ausschuss": 2}, f"heute: {a['heute']}")
ok(len(a["stunden"]) == 24 and len(a["tage"]) == 14, "24 Stunden, 14 Tage")
ok(sum(x["teile"] for x in a["tage"]) == 127, "Tage summieren auf alle Teile")
heute = a["tage"][-1]
ok(heute["teile"] == 62 and abs(heute["unbekannt"] - 16.1) < 0.1, f"heutiger Tag: 62 Teile, 16,1 % unbekannt ({heute})")
dr = a["drift"]
ok(dr["status"] == "sinkt" and dr["referenz"] == 0.9 and abs(dr["aktuell"] - 0.7848) < 0.01, f"Drift erkannt: {dr['referenz']} -> {dr['aktuell']}")
# nach neuem Training: zu wenig Daten
j.training(jetzt)
a2 = auswerten(j.lesen(), jetzt + 1)
ok(a2["drift"]["status"] == "zu_wenig" and a2["drift"]["seit_training"] == 0, "nach neuem Training: Referenz beginnt neu")
# stabil
j2 = Journal(Path(tempfile.mkdtemp()))
j2.training(jetzt - 5000)
for i in range(120):
    j2.teil("gut", "B", 0.85 + (0.02 if i % 2 else -0.02), jetzt - 4000 + i * 10)
ok(auswerten(j2.lesen(), jetzt)["drift"]["status"] == "stabil", "gleichbleibende Sicherheit: stabil")
ok(Journal(None).lesen() == [], "ohne Ordner: kein Fehler")
print("FEHLER: " + " | ".join(FEHLER) if FEHLER else "TREND_OK"); sys.exit(1 if FEHLER else 0)
