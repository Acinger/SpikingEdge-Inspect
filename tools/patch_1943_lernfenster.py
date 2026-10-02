#!/usr/bin/env python3
"""UI: Aufnahmefenster (Groesse, Schaerfe) auch im Lernmodus (Anmerkung Ace,
2026-10-01) - kein Wechsel nach Kamera noetig. Build 1.9.43."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "vorsa" / "web" / "static" / "index.html"
S = ROOT / "vorsa" / "web" / "server.py"
def ers(t, a, n, k=1):
    if t.count(a) != k: raise SystemExit(f"FEHLER: {t.count(a)}x statt {k}x: {a[:120]}")
    return t.replace(a, n)
h = H.read_text(encoding="utf-8")
if "griffFensterHtml() + griffSerieHtml()" in h:
    print("index.html: schon gepatcht")
else:
    h = ers(h, '''  aus += griffSerieHtml();
  aus += `<div class="block">
    <div class="btitel"><span>Training</span>''', '''  // Aufnahmefenster direkt hier: Groesse und Schaerfe gehoeren zum
  // Fotografieren, nicht in einen anderen Modus (Anmerkung 2026-10-01).
  aus += griffFensterHtml() + griffSerieHtml();
  aus += `<div class="block">
    <div class="btitel"><span>Training</span>''')
    H.write_text(h, encoding="utf-8"); print("index.html gepatcht")
s = S.read_text(encoding="utf-8")
if "1.9.43-lernfenster" not in s:
    s = ers(s, 'BUILD = "1.9.42-verteiler"', 'BUILD = "1.9.43-lernfenster"'); S.write_text(s, encoding="utf-8"); print("server.py gepatcht")
