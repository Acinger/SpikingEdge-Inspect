#!/usr/bin/env python3
"""1.9.62 — Begriff: "Lernen …" heißt "Training …" (Anmerkung Ace).

Der Knopf öffnet den Dialog mit beiden Wegen (Chip-Lernen in Sekunden,
M3-Training in Stunden) - "Training" ist der Oberbegriff. EN: Train / Retrain.
Der Ablaufschritt "Anlernen" (Teach) bleibt.
"""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "vorsa" / "web" / "static" / "index.html"
S = ROOT / "vorsa" / "web" / "server.py"
D = ROOT / "vorsa" / "web" / "static" / "sprache_en.js"
ERS = [
    ('neben = { t: s.gelernt ? "Neu lernen …" : "Lernen …",', 'neben = { t: s.gelernt ? "Neu trainieren …" : "Training …",'),
    ('Oben rechts „Lernen …“ öffnet den Dialog.', 'Oben rechts „Training …“ öffnet den Dialog.'),
    ('Rechts oben „Lernen …“ drücken.', 'Rechts oben „Training …“ drücken.'),
    ('["gelernt", "Lernen", "Die Fotos auf den Chip bringen — dauert Sekunden.", "Lernen …"],',
     '["gelernt", "Training", "Die Fotos auf den Chip bringen — dauert Sekunden.", "Training …"],'),
]
h = H.read_text(encoding="utf-8")
if "Neu trainieren …" not in h:
    for a, b in ERS:
        assert h.count(a) == 1, a
        h = h.replace(a, b)
    H.write_text(h, encoding="utf-8"); print("index.html gepatcht")
d = D.read_text(encoding="utf-8")
if "Nachtrag 17" not in d:
    d = d.replace('\nif (window.spracheNachladen) window.spracheNachladen();\n', '''
/* ---- Nachtrag 17 (1.9.62 Training) ---- */
Object.assign(window.SPRACHEN.en, {
  "Training …": "Train …", "Neu trainieren …": "Retrain …", "Training": "Training",
  "Zwei oder mehr Objekte haben genug Fotos. Rechts oben „Training …“ drücken.": "Two or more objects have enough photos. Press “Train …” at the top right.",
  "Oben rechts „Training …“ öffnet den Dialog. Er zeigt vorher, was hingeht, und lässt die Wahl zwischen den beiden Wegen:": "“Train …” at the top right opens the dialog. It shows beforehand what goes in and lets you choose between the two paths:"
});

if (window.spracheNachladen) window.spracheNachladen();
''', 1)
    D.write_text(d, encoding="utf-8"); print("sprache_en.js gepatcht")
s = S.read_text(encoding="utf-8")
if "1.9.62-training" not in s:
    s = s.replace('BUILD = "1.9.61-sps"', 'BUILD = "1.9.62-training"'); S.write_text(s, encoding="utf-8"); print("BUILD 1.9.62-training")
