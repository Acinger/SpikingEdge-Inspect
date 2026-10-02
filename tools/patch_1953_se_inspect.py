#!/usr/bin/env python3
"""A11 — Sichtbare Umbenennung auf SE Inspect (Build 1.9.53).

Programm: Marke in der Seitenleiste, Fenstertitel, Versionszeile, Hinweise,
Banner beim Start, Woerterbuch. Das Python-Paket bleibt `vorsa/`, Dateinamen
(vorsa_m3.fbz, vorsa_daten/) und Umgebungsvariablen (VORSA_*) bleiben -
die Anlage darf wegen einer Umbenennung nie stehen.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "vorsa" / "web" / "static" / "index.html"
S = ROOT / "vorsa" / "web" / "server.py"
R = ROOT / "tools" / "run_web.py"
D = ROOT / "vorsa" / "web" / "static" / "sprache_en.js"


def ers(t, a, n, k=1):
    if t.count(a) != k:
        raise SystemExit(f"FEHLER: {t.count(a)}x statt {k}x: {a[:160]}")
    return t.replace(a, n)


h = H.read_text(encoding="utf-8")
if "<b>SE INSPECT</b>" in h:
    print("index.html: schon gepatcht")
else:
    h = ers(h, "<title>VORSA INSPECT · OPS 2.1</title>", "<title>SE Inspect · SpikingEdge</title>")
    h = ers(h, '''    <span><b>VORSA</b><small>INSPECT / OPS 2.2</small></span>''',
            '''    <span><b>SE INSPECT</b><small>SpikingEdge · UI 2.3</small></span>''')
    h = ers(h, '''    <div class="ops-version">VORSA INSPECT · UI 2.2</div>''',
            '''    <div class="ops-version">SE Inspect · UI 2.3 · früher VORSA INSPECT</div>''')
    h = ers(h, '''    <div class="kasten">VORSA-M3 — Visual Overlap-Resilient Sparse Architecture.''',
            '''    <div class="kasten">SE-M3 (VORSA-M3) — Visual Overlap-Resilient Sparse Architecture.''')
    h = h.replace('console.error("VORSA:", kaputt);', 'console.error("SE Inspect:", kaputt);')
    # Marke: Schriftzug etwas kleiner, damit "SE INSPECT" in die Leiste passt
    h = ers(h, '''/* Kamera-Dock (1.9.52) */''', '''/* Marke SE Inspect (1.9.53) */
#navMarke span b { font-size:17px; letter-spacing:.06em; }
#navMarke span small { letter-spacing:.14em; }
body#opsApp.schmal #navMarke span { display:none; }
/* Kamera-Dock (1.9.52) */''')
    H.write_text(h, encoding="utf-8")
    print("index.html gepatcht")

s = S.read_text(encoding="utf-8")
if "1.9.53-se-inspect" not in s:
    s = ers(s, 'BUILD = "1.9.52-kamdock"', 'BUILD = "1.9.53-se-inspect"')
    s = ers(s, '''        "Erkennung laeuft geometrisch (OpenCV), VORSA-M3 ist noch nicht trainiert")''',
            '''        "Erkennung laeuft geometrisch (OpenCV), SE-M3 ist noch nicht trainiert")''')
    s = ers(s, '''        f"VORSA-M3 Oberflaeche auf  http://0.0.0.0:{port}",''',
            '''        f"SE Inspect (frueher VORSA INSPECT) auf  http://0.0.0.0:{port}",''')
    S.write_text(s, encoding="utf-8")
    print("server.py gepatcht")

r = R.read_text(encoding="utf-8")
if "SE Inspect" not in r:
    r = ers(r, '"""Startet die VORSA-M3 Weboberflaeche.', '"""Startet die SE Inspect Weboberflaeche (frueher VORSA-M3 / VORSA INSPECT).')
    R.write_text(r, encoding="utf-8")
    print("run_web.py gepatcht")

d = D.read_text(encoding="utf-8")
if "Nachtrag 9" not in d:
    d = d.replace('''"Erkennung laeuft geometrisch (OpenCV), VORSA-M{} ist noch nicht trainiert": "Recognition runs geometrically (OpenCV), VORSA-M{} is not trained yet",''',
                  '''"Erkennung laeuft geometrisch (OpenCV), VORSA-M{} ist noch nicht trainiert": "Recognition runs geometrically (OpenCV), VORSA-M{} is not trained yet",
  "Erkennung laeuft geometrisch (OpenCV), SE-M{} ist noch nicht trainiert": "Recognition runs geometrically (OpenCV), SE-M{} is not trained yet",''')
    d = d.replace('\nif (window.spracheNachladen) window.spracheNachladen();\n', '''
/* ---- Nachtrag 9 (1.9.53 SE Inspect) ---- */
Object.assign(window.SPRACHEN.en, {
  "SE INSPECT": "SE INSPECT", "SpikingEdge · UI {}": "SpikingEdge · UI {}", "SE Inspect · UI {} · früher VORSA INSPECT": "SE Inspect · UI {} · formerly VORSA INSPECT",
  "SE-M3 (VORSA-M3) — Visual Overlap-Resilient Sparse Architecture. Ein AKD1500, eine Sequenz, ein Durchgang. Die Erkennung im Livebild läuft derzeit geometrisch über OpenCV; der trainierte Detektor ersetzt sie, sobald das M3-Training durchgelaufen ist.": "SE-M3 (VORSA-M3) — Visual Overlap-Resilient Sparse Architecture. One AKD1500, one sequence, one pass. Live recognition currently runs geometrically via OpenCV; the trained detector replaces it once the M3 training has finished."
});

if (window.spracheNachladen) window.spracheNachladen();
''')
    D.write_text(d, encoding="utf-8")
    print("sprache_en.js gepatcht")
