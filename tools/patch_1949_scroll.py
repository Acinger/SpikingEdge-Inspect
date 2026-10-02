#!/usr/bin/env python3
"""UI 1.9.49 — Pruef-Kachel scrollt als Ganzes (Anmerkung Ace: Details nicht
erreichbar). Kopf mit Reitern bleibt oben stehen (sticky); das Live-Urteil,
PRUEFEN, Zaehler, Testsatz und die Detailbloecke laufen in einer Spalte
durch, statt dass die Details in einem Mini-Fenster unter dem festen Kopf
haengen."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "vorsa" / "web" / "static" / "index.html"; S = ROOT / "vorsa" / "web" / "server.py"
def ers(t, a, n, k=1):
    if t.count(a) != k: raise SystemExit(f"FEHLER: {t.count(a)}x statt {k}x: {a[:120]}")
    return t.replace(a, n)
h = H.read_text(encoding="utf-8")
if "/* Kachel scrollt als Ganzes (1.9.49) */" in h:
    print("index.html: schon gepatcht")
else:
    css = '''
/* Kachel scrollt als Ganzes (1.9.49) */
body#opsApp #opsInspector { overflow:auto; overscroll-behavior:contain; }
body#opsApp .ops-inspector-heading { position:sticky; top:0; z-index:3; background:var(--panel); }
body#opsApp #opsSummary { flex:0 0 auto; }
body#opsApp #rechts { flex:0 0 auto; overflow:visible; min-height:auto; }
'''
    i = h.rfind("</style>")
    h = h[:i] + css + h[i:]
    H.write_text(h, encoding="utf-8"); print("index.html gepatcht")
s = S.read_text(encoding="utf-8")
if "1.9.49-scroll" not in s:
    s = ers(s, 'BUILD = "1.9.48-liveurteil"', 'BUILD = "1.9.49-scroll"'); S.write_text(s, encoding="utf-8"); print("server.py gepatcht")
