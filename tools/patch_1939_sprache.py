#!/usr/bin/env python3
"""A13 — UI zweisprachig Deutsch/Englisch (Build 1.9.39).

- index.html: Woerterbuch laden, Uebersetzer (MutationObserver ueber Textknoten
  und title/placeholder/aria-label/alt), Umschalter DE/EN in der Seitenleiste,
  Sprache in localStorage (nbes_sprache), Vorgabe aus navigator.language.
- server.py: /static/*.js ausliefern; Build 1.9.39-sprache.
Exakte Ersetzungen, idempotent.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "vorsa" / "web" / "static" / "index.html"
S = ROOT / "vorsa" / "web" / "server.py"


def ers(text, alt, neu, n=1):
    k = text.count(alt)
    if k != n:
        raise SystemExit(f"FEHLER: {k}x statt {n}x gefunden:\n{alt[:200]}")
    return text.replace(alt, neu)


srv = S.read_text(encoding="utf-8")
if "1.9.39-sprache" in srv:
    print("server.py: schon gepatcht")
else:
    srv = ers(srv, 'BUILD = "1.9.38-stationaer"', 'BUILD = "1.9.39-sprache"')
    srv = ers(srv, '''            if weg.startswith("/static/") and weg.endswith(".png"):''', '''            if weg.startswith("/static/") and weg.endswith(".js"):
                # Sprachdateien der Oberflaeche (A13). Nur der Dateiname
                # zaehlt - kein Pfad-Traversal moeglich.
                name = Path(weg).name
                datei = STATISCH / name
                if not datei.exists():
                    return self._bytes(b"", "application/javascript", 404)
                return self._bytes(datei.read_bytes(),
                                   "application/javascript; charset=utf-8")

            if weg.startswith("/static/") and weg.endswith(".png"):''')
    S.write_text(srv, encoding="utf-8")
    print("server.py gepatcht")

h = H.read_text(encoding="utf-8")
if 'id="navSprache"' in h:
    print("index.html: schon gepatcht")
    raise SystemExit(0)

# 1) Woerterbuch laden (vor dem Hauptskript)
h = ers(h, '''</head>''', '''<script src="/static/sprache_en.js?v=1939"></script>
</head>''')

# 2) Umschalter in der Seitenleiste
h = ers(h, '''      <button class="snav klein" data-tat="seite_schmal" title="Navigation ein- oder ausklappen">''',
        '''      <button class="snav klein" data-tat="sprache" id="navSprache" title="Sprache: Deutsch / English" lang="en">
        <svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6"/><path d="M2 8h12M8 2c2.5 2.5 2.5 9.5 0 12M8 2c-2.5 2.5-2.5 9.5 0 12"/></svg><span id="navSpracheLabel">EN</span></button>
      <button class="snav klein" data-tat="seite_schmal" title="Navigation ein- oder ausklappen">''')

# 3) Uebersetzer
h = ers(h, '''/* ---------- Modus ---------- */''', '''/* ---------- Sprache (A13, 1.9.39) ----------
   Die Oberflaeche ist auf Deutsch geschrieben; Englisch entsteht zur Laufzeit
   aus dem Woerterbuch (static/sprache_en.js) ueber die Textknoten. Ein
   MutationObserver uebersetzt alles, was spaeter eingefuegt wird (die
   Spalten werden jede Sekunde neu aufgebaut). Unbekannte Texte bleiben
   Deutsch und landen in window.I18N_FEHLEND - so waechst das Woerterbuch. */
let SPRACHE = "de";
const I18N_FEHLEND = new Set(); window.I18N_FEHLEND = I18N_FEHLEND;
let I18N_EXAKT = {}, I18N_MUSTER = [], I18N_RUECK = new Set(), I18N_RUECK_MUSTER = [];
const I18N_ATTR = ["title", "placeholder", "aria-label", "alt"];
const I18N_DE = new WeakMap();          // Element -> {attr: deutscher Wert}
function i18nBauen(code) {
  const w = (window.SPRACHEN || {})[code] || {};
  I18N_EXAKT = {}; I18N_MUSTER = []; I18N_RUECK = new Set(Object.values(w)); I18N_RUECK_MUSTER = [];
  I18N_FEHLEND.clear();
  const keys = Object.keys(w).sort((a, b) => b.length - a.length);
  for (const k of keys) {
    const kk = k.replace(/\\s+/g, " ").trim();
    if (kk.includes("{}")) {
      const re = new RegExp("^" + kk.replace(/[.*+?^$()|[\\]\\\\]/g, "\\\\$&").replace(/\\{\\}/g, "(\\\\d+(?:[.,]\\\\d+)?)") + "$");
      I18N_MUSTER.push({ re, out: w[k] });
      I18N_RUECK_MUSTER.push(new RegExp("^" + w[k].replace(/[.*+?^$()|[\\]\\\\]/g, "\\\\$&").replace(/\\{\\}/g, "(\\\\d+(?:[.,]\\\\d+)?)") + "$"));
    } else I18N_EXAKT[kk] = w[k];
  }
}
function uebersetzeText(s) {
  const k = s.replace(/\\s+/g, " ").trim();
  if (!k || !/[A-Za-zÄÖÜäöüß]{2,}/.test(k)) return null;
  if (I18N_EXAKT[k] !== undefined) return I18N_EXAKT[k];
  if (I18N_RUECK.has(k)) return k;                 // schon englisch
  for (const m of I18N_MUSTER) {
    const r = k.match(m.re);
    if (r) { let i = 0; return m.out.replace(/\\{\\}/g, () => r[++i]); }
  }
  if (I18N_RUECK_MUSTER.some(re => re.test(k))) return k;   // schon englisch (Muster)
  I18N_FEHLEND.add(k);
  return null;
}
function i18nKnoten(n, voll = false) {
  if (n.nodeType === 3) {
    const p = n.parentNode;
    if (!p || p.nodeName === "SCRIPT" || p.nodeName === "STYLE") return;
    if (!voll && n.__setz !== undefined && n.data === n.__setz) return;   // eigener Eintrag
    if (n.__de === undefined || n.data !== n.__ziel) n.__de = n.data;  // neuer deutscher Text
    const de = n.__de;
    let ziel = de;
    if (SPRACHE !== "de") {
      const en = uebersetzeText(de);
      if (en !== null) {
        const vorn = de.match(/^\\s*/)[0], hinten = de.match(/\\s*$/)[0];
        ziel = vorn + en + hinten;
      }
    }
    if (n.data !== ziel) { n.__setz = ziel; n.data = ziel; }
    n.__ziel = ziel;
    return;
  }
  if (n.nodeType !== 1) return;
  let m = I18N_DE.get(n);
  for (const a of I18N_ATTR) {
    if (!n.hasAttribute(a)) continue;
    const v = n.getAttribute(a);
    if (!m) { m = {}; I18N_DE.set(n, m); }
    if (m[a] === undefined || v !== m[a + "_ziel"]) m[a] = v;       // neuer deutscher Wert
    let ziel = m[a];
    if (SPRACHE !== "de") { const en = uebersetzeText(m[a]); if (en !== null) ziel = en; }
    if (v !== ziel) n.setAttribute(a, ziel);
    m[a + "_ziel"] = ziel;
  }
}
function i18nBaum(wurzel, voll = false) {
  if (!wurzel) return;
  if (wurzel.nodeType === 3) { i18nKnoten(wurzel, voll); return; }
  if (wurzel.nodeType !== 1 && wurzel.nodeType !== 11) return;
  if (wurzel.nodeType === 1) i18nKnoten(wurzel, voll);
  const w = document.createTreeWalker(wurzel, 5);
  let n;
  while ((n = w.nextNode())) i18nKnoten(n, voll);
}
let I18N_BEOBACHTER = null;
function i18nStart() {
  if (I18N_BEOBACHTER) return;
  I18N_BEOBACHTER = new MutationObserver(muts => {
    for (const m of muts) {
      if (m.type === "childList") m.addedNodes.forEach(i18nBaum);
      else if (m.type === "characterData") i18nKnoten(m.target);
      else if (m.type === "attributes") i18nKnoten(m.target);
    }
  });
  I18N_BEOBACHTER.observe(document.body, { childList: true, subtree: true, characterData: true,
    attributes: true, attributeFilter: I18N_ATTR });
}
function spracheSetzen(code, merken = true) {
  SPRACHE = (code === "en") ? "en" : "de";
  i18nBauen(SPRACHE);
  document.documentElement.lang = SPRACHE;
  document.body.classList.toggle("sprache-en", SPRACHE === "en");
  const l = document.getElementById("navSpracheLabel");
  if (l) l.textContent = SPRACHE === "en" ? "DE" : "EN";      // zeigt das Ziel
  if (merken) { try { localStorage.setItem("nbes_sprache", SPRACHE); } catch (e) {} }
  i18nBaum(document.body, true);
  i18nStart();
}
(function spracheStart() {
  let s = null;
  try { s = localStorage.getItem("nbes_sprache"); } catch (e) {}
  if (s !== "de" && s !== "en") s = /^de/i.test(navigator.language || "") ? "de" : "en";
  const los = () => spracheSetzen(s, false);
  if (document.body) los(); else document.addEventListener("DOMContentLoaded", los);
  // Kommt das Woerterbuch erst nach dem Hauptskript an (asynchrones Laden),
  // meldet es sich hier und die Seite wird einmal nachuebersetzt.
  window.spracheNachladen = () => { if (document.body) spracheSetzen(SPRACHE, false); };
})();

/* ---------- Modus ---------- */''')

# 4) Klick: Sprache umschalten
h = ers(h, '''  if (tat === "look") {
    // Oberflaeche umschalten: Industrie (ISA-101) <-> Magna (1.9.7).''', '''  if (tat === "sprache") { spracheSetzen(SPRACHE === "en" ? "de" : "en"); return; }
  if (tat === "look") {
    // Oberflaeche umschalten: Industrie (ISA-101) <-> Magna (1.9.7).''')

H.write_text(h, encoding="utf-8")
print("index.html gepatcht")
