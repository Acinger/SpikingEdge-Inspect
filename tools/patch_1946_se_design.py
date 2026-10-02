#!/usr/bin/env python3
"""A9 — UI im SpikingEdge-Design (Build 1.9.46).

Dritter Look "spikingedge": flache ISA-101-Grundlage (wie "industrie"),
aber mit den Farb- und Schrift-Tokens der Website (spikingedge.com:
Nachtblau, Cyan, Gruen, Amber, Pink, Inter + Monospace-Labels, feines
Raster). Standard fuer neue Installationen; der Look-Knopf wechselt
SpikingEdge -> Hell (ISA-101) -> Magna. Kein Layout- oder Logikumbau.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "vorsa" / "web" / "static" / "index.html"
S = ROOT / "vorsa" / "web" / "server.py"


def ers(t, a, n, k=1):
    if t.count(a) != k:
        raise SystemExit(f"FEHLER: {t.count(a)}x statt {k}x: {a[:160]}")
    return t.replace(a, n)


h = H.read_text(encoding="utf-8")
if 'body#opsApp[data-ui="ops2"].se' in h:
    print("index.html: schon gepatcht")
else:
    # 1) Look-Logik: drei Looks
    h = ers(h, '''function skinAktiv() {
  try { return localStorage.getItem("nbes_look") || "industrie"; }
  catch (e) { return "industrie"; }
}
function skinSetzen(name) {
  name = (name === "magna") ? "magna" : "industrie";
  try { localStorage.setItem("nbes_look", name); } catch (e) {}
  document.body.dataset.skin = "magna";               // Layout-Basis
  document.body.classList.toggle("hpm", name === "industrie");
  const theme = document.getElementById("opsThemeLabel");
  if (theme) theme.textContent = name === "industrie" ? "Dunkel" : "Hell";
}''', '''// LOOKS (A9, 1.9.46): "spikingedge" (Standard, Marke), "industrie"
// (ISA-101 hell/grau), "magna" (dunkles Glas). Alle drei teilen das
// Layout; sie unterscheiden sich nur in Tokens und Flaechen.
const LOOKS = ["spikingedge", "industrie", "magna"];
const LOOK_NAMEN = { spikingedge: "SpikingEdge", industrie: "Hell", magna: "Magna" };
function skinAktiv() {
  try { const l = localStorage.getItem("nbes_look"); return LOOKS.includes(l) ? l : "spikingedge"; }
  catch (e) { return "spikingedge"; }
}
function skinSetzen(name) {
  name = LOOKS.includes(name) ? name : "spikingedge";
  try { localStorage.setItem("nbes_look", name); } catch (e) {}
  document.body.dataset.skin = "magna";               // Layout-Basis
  document.body.classList.toggle("hpm", name !== "magna");   // flache Flaechen
  document.body.classList.toggle("se", name === "spikingedge");
  const theme = document.getElementById("opsThemeLabel");
  // Der Knopf zeigt, WOHIN er schaltet.
  const naechster = LOOKS[(LOOKS.indexOf(name) + 1) % LOOKS.length];
  if (theme) theme.textContent = LOOK_NAMEN[naechster];
}''')
    h = ers(h, '''    skinSetzen(skinAktiv() === "industrie" ? "magna" : "industrie");''',
            '''    skinSetzen(LOOKS[(LOOKS.indexOf(skinAktiv()) + 1) % LOOKS.length]);''')
    h = ers(h, '''      <button class="snav klein" data-tat="look" title="Helle oder dunkle Darstellung">''',
            '''      <button class="snav klein" data-tat="look" title="Darstellung wechseln: SpikingEdge · Hell · Magna">''')

    # 2) Tokens + Flaechen
    css = '''
/* ===== LOOK "spikingedge" (A9, 1.9.46) — Tokens der Website spikingedge.com ===== */
body#opsApp[data-ui="ops2"].se {
  --nacht:#061015; --stahl:#0b1b22; --stahl2:#0e2028; --panel:#0a1a20;
  --rand:#19343e; --randhell:#28515e;
  --text:#eef8fb; --leise:#89a3ad; --marke:#eef8fb; --weiss:#ffffff;
  --akzent:#49e7ff; --akzentRGB:73,231,255; --aufAkzent:#041014;
  --gut:#79efbd; --warn:#ffd174; --rot:#ff779b;
  --grundA:#0b1b22; --grundB:#061015;
  --glas:none; --tastenglas:none; --tiefe:0 1px 2px rgba(0,0,0,.45); --kante:none;
  --ops-good-bg:rgba(121,239,189,.10); --ops-warn-bg:rgba(255,209,116,.10); --ops-bad-bg:rgba(255,119,155,.12);
  background:linear-gradient(rgba(73,231,255,.024) 1px,transparent 1px),
             linear-gradient(90deg,rgba(73,231,255,.024) 1px,transparent 1px),#061015 !important;
  background-size:38px 38px !important;
  font-family:"Inter","Segoe UI",system-ui,sans-serif;
  color:#eef8fb;
}
body#opsApp[data-ui="ops2"].se #seitenNav, body#opsApp[data-ui="ops2"].se #kopf,
body#opsApp[data-ui="ops2"].se #videoKopf, body#opsApp[data-ui="ops2"].se #videoFuss,
body#opsApp[data-ui="ops2"].se .block, body#opsApp[data-ui="ops2"].se .lfeed,
body#opsApp[data-ui="ops2"].se .lfkopf, body#opsApp[data-ui="ops2"].se #opsInspector,
body#opsApp[data-ui="ops2"].se #fuss { background:#0b1b22 !important; border-color:#19343e !important; }
body#opsApp[data-ui="ops2"].se #opsCommand { background:transparent !important; }
body#opsApp[data-ui="ops2"].se .snav.an { background:rgba(73,231,255,.10) !important; color:#49e7ff !important; }
body#opsApp[data-ui="ops2"].se .snav.an svg { stroke:#49e7ff; }
body#opsApp[data-ui="ops2"].se .ops-nav-caption, body#opsApp[data-ui="ops2"].se .btitel > span:first-child,
body#opsApp[data-ui="ops2"].se .pu-stat span, body#opsApp[data-ui="ops2"].se .ops-eyebrow,
body#opsApp[data-ui="ops2"].se .vtitel, body#opsApp[data-ui="ops2"].se .breadcrumb {
  font-family:ui-monospace,SFMono-Regular,Consolas,"Liberation Mono",monospace; font-size:10px; letter-spacing:.12em; text-transform:uppercase; color:#607f88; }
body#opsApp[data-ui="ops2"].se .pu-pruefen { background:#49e7ff !important; border-color:#49e7ff !important; color:#041014 !important; }
body#opsApp[data-ui="ops2"].se :is(.kopftaste,.mini,.zweittaste,.adx-btn,.ops-btn) { border-color:#28515e !important; background:#0b1c23 !important; color:#eef8fb !important; }
body#opsApp[data-ui="ops2"].se :is(.kopftaste,.mini,.zweittaste,.adx-btn,.ops-btn).an { background:rgba(73,231,255,.14) !important; color:#49e7ff !important; border-color:#49e7ff !important; }
body#opsApp[data-ui="ops2"].se .ltakt button.an { background:#49e7ff !important; color:#041014 !important; }
body#opsApp[data-ui="ops2"].se input[type=range] { accent-color:#49e7ff; }
body#opsApp[data-ui="ops2"].se #navMarke svg path:first-child { fill:#eef8fb; }
body#opsApp[data-ui="ops2"].se #navMarke svg path:last-child { fill:#49e7ff; }
body#opsApp[data-ui="ops2"].se #navMarke small { color:#49e7ff; letter-spacing:.14em; }
body#opsApp[data-ui="ops2"].se .ops-version { color:#607f88; font-family:ui-monospace,Consolas,monospace; font-size:10px; }
body#opsApp[data-ui="ops2"].se .pu-urteil.gut { border-color:#79efbd !important; } body#opsApp[data-ui="ops2"].se .pu-urteil.gut b { color:#79efbd !important; }
body#opsApp[data-ui="ops2"].se .pu-urteil.unbekannt { border-color:#ffd174 !important; } body#opsApp[data-ui="ops2"].se .pu-urteil.unbekannt b { color:#ffd174 !important; }
body#opsApp[data-ui="ops2"].se .pu-urteil.ausschuss { border-color:#ff779b !important; } body#opsApp[data-ui="ops2"].se .pu-urteil.ausschuss b { color:#ff779b !important; }
body#opsApp[data-ui="ops2"].se a { color:#8ef0ff; }
'''
    # vor dem letzten </style> einfuegen (opsDesign-Block ist der zweite)
    i = h.rfind("</style>")
    h = h[:i] + css + h[i:]
    h = ers(h, '''body.stationaer #navLinie, body.stationaer #linieAnsicht, body.stationaer .ltakt-linie { display:none !important; }''', '''body.stationaer #navLinie, body.stationaer #linieAnsicht, body.stationaer .ltakt-linie, body.stationaer #linieKnopf { display:none !important; }''')
    H.write_text(h, encoding="utf-8")
    print("index.html gepatcht")

s = S.read_text(encoding="utf-8")
if "1.9.46-se-design" not in s:
    s = ers(s, 'BUILD = "1.9.45-testsatz"', 'BUILD = "1.9.46-se-design"')
    S.write_text(s, encoding="utf-8")
    print("server.py gepatcht")
