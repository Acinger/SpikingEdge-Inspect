#!/usr/bin/env python3
"""UI 1.9.54 — Marke: SpikingEdge-Icon links, "SE INSPECT" daneben in einer
Zeile, kein Umbruch (Anmerkung Ace). Server liefert /static/*.webp|svg."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "vorsa" / "web" / "static" / "index.html"; S = ROOT / "vorsa" / "web" / "server.py"
def ers(t, a, n, k=1):
    if t.count(a) != k: raise SystemExit(f"FEHLER: {t.count(a)}x statt {k}x: {a[:120]}")
    return t.replace(a, n)
h = H.read_text(encoding="utf-8")
if 'se_icon.webp' in h:
    print("index.html: schon gepatcht")
else:
    h = ers(h, '''    <svg viewBox="0 0 34 30" aria-hidden="true"><path d="M2 2 L13 26 L17 17 L10 2 Z" fill="#d3e2ee"/><path d="M15 2 L22 17 L32 2 Z" fill="#88abc5"/></svg>
    <span><b>SE INSPECT</b><small>SpikingEdge · UI 2.3</small></span>''',
            '''    <img src="/static/se_icon.webp" alt="SpikingEdge" class="marke-icon">
    <span class="marke-text"><b>INSPECT</b></span>''')
    h = ers(h, '''/* Marke SE Inspect (1.9.53) */
#navMarke span b { font-size:17px; letter-spacing:.06em; }
#navMarke span small { letter-spacing:.14em; }
body#opsApp.schmal #navMarke span { display:none; }''', '''/* Marke SE Inspect (1.9.54): Icon + Schriftzug, eine Zeile */
#navMarke { white-space:nowrap; overflow:hidden; }
#navMarke .marke-icon { width:34px; height:auto; flex-shrink:0; display:block; }
/* Spezifitaet hoeher als "body#opsApp #navMarke b" (22px / 3px) weiter unten */
body#opsApp #navMarke .marke-text b, body[data-skin] #navMarke .marke-text b { font-size:19px; letter-spacing:.14em; white-space:nowrap; line-height:1.1; }
body#opsApp #navMarke .marke-icon, body[data-skin] #navMarke .marke-icon { width:34px; height:auto; }
body#opsApp.hpm:not(.se) #navMarke .marke-icon { filter:invert(1); }   /* heller Look: Marke dunkel */
body#opsApp.schmal #navMarke .marke-text { display:none; }''')
    H.write_text(h, encoding="utf-8"); print("index.html gepatcht")
s = S.read_text(encoding="utf-8")
if "1.9.54-logo" not in s:
    s = ers(s, 'BUILD = "1.9.53-se-inspect"', 'BUILD = "1.9.54-logo"')
    s = ers(s, '''            if weg.startswith("/static/") and weg.endswith(".png"):
                # Statische PNGs (z. B. die AKD1500-Kartenbilder). Nur
                # der Dateiname zaehlt - kein Pfad-Traversal moeglich.
                name = Path(weg).name
                datei = STATISCH / name
                if not datei.exists():
                    return self._bytes(b"", "image/png", 404)
                return self._bytes(datei.read_bytes(), "image/png")''', '''            if weg.startswith("/static/") and weg.endswith((".png", ".webp", ".svg")):
                # Statische Bilder (Kartenbilder, Marke). Nur der Dateiname
                # zaehlt - kein Pfad-Traversal moeglich.
                name = Path(weg).name
                datei = STATISCH / name
                typ = {"png": "image/png", "webp": "image/webp", "svg": "image/svg+xml"}[name.rsplit(".", 1)[-1]]
                if not datei.exists():
                    return self._bytes(b"", typ, 404)
                return self._bytes(datei.read_bytes(), typ)''')
    S.write_text(s, encoding="utf-8"); print("server.py gepatcht")
