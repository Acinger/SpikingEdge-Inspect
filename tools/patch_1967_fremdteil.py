#!/usr/bin/env python3
"""1.9.67: Testsatz-Chip "Fremdteil" (Soll = unbekannt). Ohne ihn liess sich in
der Oberflaeche keine Fremdteil-Szene anlegen - die Schwelle aus dem Testsatz
konnte "Unbekanntes erkennt" dann nie messen. Idempotent."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "vorsa/web/static/index.html"; S = ROOT / "vorsa/web/server.py"; E = ROOT / "vorsa/web/static/sprache_en.js"
h, s, e = (p.read_text(encoding="utf-8") for p in (H, S, E))
if 'data-name="unbekannt"' in h:
    print("schon angewendet"); raise SystemExit(0)
def ers(t, a, b):
    assert t.count(a) == 1, (a[:60], t.count(a)); return t.replace(a, b)
s = ers(s, 'BUILD = "1.9.66-drehen"', 'BUILD = "1.9.67-fremdteil"')
h = ers(h, '''    <div class="ts-chips">${chips || '<span class="leise">Erst Objekte anlegen.</span>'}''',
'''    <div class="ts-chips">${chips || '<span class="leise">Erst Objekte anlegen.</span>'}
      ${(() => { const n = TS_SOLL.filter(x => x === "unbekannt").length;
        return `<button class="mini ts-chip ${n ? "an" : ""}" data-tat="ts_soll" data-name="unbekannt"
          title="Teil, das die Anlage NICHT benennen soll (Störteil, fremdes Teil) – Soll: unbekannt. Rechtsklick / Umschalt-Klick: eins weniger">Fremdteil${n > 1 ? ` ×${n}` : ""}</button>`; })()}''')
h = ers(h, '''<span class="n">${s.leer ? "leer" : s.soll.map(txt).join(" + ")}</span>''',
'''<span class="n">${s.leer ? "leer" : s.soll.map(x => x === "unbekannt" ? "Fremdteil" : txt(x)).join(" + ")}</span>''')
h = ers(h, '''Soll: ${TS_SOLL.length ? TS_SOLL.map(txt).join(" + ") : "leer"}''',
'''Soll: ${TS_SOLL.length ? TS_SOLL.map(x => x === "unbekannt" ? "Fremdteil" : txt(x)).join(" + ") : "leer"}''')
e = ers(e, "if (window.spracheNachladen) window.spracheNachladen();", '''/* ---- Nachtrag 21 (1.9.67 Fremdteil) ---- */
Object.assign(window.SPRACHEN.en, {
  "Fremdteil": "Foreign part", "Fremdteil ×{}": "Foreign part ×{}",
  "Teil, das die Anlage NICHT benennen soll (Störteil, fremdes Teil) – Soll: unbekannt. Rechtsklick / Umschalt-Klick: eins weniger": "Part the cell must NOT name (stray or foreign part) – expected: unknown. Right-click / Shift-click: one less"
});

if (window.spracheNachladen) window.spracheNachladen();''')
for p, t in ((H, h), (S, s), (E, e)): p.write_text(t, encoding="utf-8")
print("ok 1.9.67")
