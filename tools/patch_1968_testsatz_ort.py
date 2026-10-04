#!/usr/bin/env python3
"""1.9.68: Testsatz in beiden Profilen und auffindbar.

Vorher stand der Testsatz nur im Profil "stationaer" und dort in der
angehefteten Kopfzeile der Pruefung. sync.ps1 legt auf dem Pi aber
VORSA_PROFIL=linie an - der Testsatz war dort unsichtbar (2026-10-04).
Jetzt: oberster Block im Reiter "Pruefdetails", in jedem Profil, und ein
Knopf "Testsatz oeffnen" bei der Schwelle aus dem Testsatz. Idempotent."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "vorsa/web/static/index.html"; S = ROOT / "vorsa/web/server.py"; E = ROOT / "vorsa/web/static/sprache_en.js"
h, s, e = (p.read_text(encoding="utf-8") for p in (H, S, E))
if 'data-tat="testsatz_zeigen"' in h:
    print("schon angewendet"); raise SystemExit(0)
def ers(t, a, b):
    assert t.count(a) == 1, (a[:60], t.count(a)); return t.replace(a, b)
s = ers(s, 'BUILD = "1.9.67-fremdteil"', 'BUILD = "1.9.68-testsatz"')
h = ers(h, '''    ${STATIONAER() ? testsatzBlock(P) : ""}</section>''', '''    </section>
    ${testsatzBlock(P)}''')
h = ers(h, '''  return `<div class="as-block"><h4>Schwelle aus dem Testsatz</h4>''', '''  inhalt += `<div class="knopfreihe" style="margin-top:8px"><button class="mini" data-tat="testsatz_zeigen">Testsatz öffnen</button></div>`;
  return `<div class="as-block"><h4>Schwelle aus dem Testsatz</h4>''')
h = ers(h, '''  if (tat === "vs_hg") {''', '''  if (tat === "testsatz_zeigen") {
    $("dEinstellungen").hidden = true;
    if (MODUS !== "betreiben") await setzeModus("betreiben");
    OPS_PANE = "details"; OPS_OPEN.add("testsatz");
    LETZTE_SPALTE = ""; zeichneRechts(); opsSync();
    const t = $("rechts").querySelector('[data-ops-disclosure="testsatz"]');
    if (t) { t.open = true; if (t.scrollIntoView) t.scrollIntoView({ block: "start" }); }
    return;
  }
  if (tat === "vs_hg") {''')
e = ers(e, "if (window.spracheNachladen) window.spracheNachladen();", '''/* ---- Nachtrag 22 (1.9.68 Testsatz) ---- */
Object.assign(window.SPRACHEN.en, { "Testsatz öffnen": "Open test set" });

if (window.spracheNachladen) window.spracheNachladen();''')
for p, t in ((H, h), (S, s), (E, e)): p.write_text(t, encoding="utf-8")
print("ok 1.9.68")
