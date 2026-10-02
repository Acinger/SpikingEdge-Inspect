#!/usr/bin/env python3
"""Test des M3-Kopfes ohne Hardware und ohne Training.

Geprueft wird genau das, was VORSA-M3 von einem verkleinerten YOLO
unterscheidet:

  1. Drei stark ueberlagerte Objekte in EINEM Rasterfeld ueberleben die
     Nachverarbeitung. Standard-NMS wuerde hier zwei davon loeschen.
  2. Mehrere unabhaengige Ueberlagerungsstellen werden getrennt verarbeitet.
  3. Bei mehr als drei lokalen Objekten wird eine Ueberfuellung gemeldet,
     statt eine Objektzahl vorzutaeuschen.
  4. Die Zuordnung Slot -> echtes Objekt ist reihenfolgeunabhaengig.
  5. Duplikate aus benachbarten Feldern werden weiterhin zusammengefasst.

    python3 tools/test_m3_head.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vorsa import config, postprocess                      # noqa: E402
from vorsa.assignment import (                             # noqa: E402
    CostWeights, GtObject, best_assignment, build_targets,
)
from vorsa.detection import rotated_iou                    # noqa: E402


def logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def write_slot(cell, k, mc, *, obj, ox, oy, w_frac, h_frac, angle, vis, cls):
    """Schreibt einen Slot als Roh-Logits, wie sie der Chip liefern wuerde."""
    b = k * mc.per_slot
    a = math.radians(angle)
    cell[b + 0] = logit(obj)
    cell[b + 1] = logit((ox + 0.5) / 2.0)     # Umkehrung von 2*sig - 0.5
    cell[b + 2] = logit((oy + 0.5) / 2.0)
    cell[b + 3] = logit(w_frac)
    cell[b + 4] = logit(h_frac)
    cell[b + 5] = math.sin(2 * a)
    cell[b + 6] = math.cos(2 * a)
    cell[b + 7] = logit(vis)
    cell[b + 8 + cls] = 6.0


def write_extras(cell, mc, *, count, overlap, overflow):
    e = mc.slots * mc.per_slot
    cell[e + 0] = count
    cell[e + 1] = logit(overlap)
    cell[e + 2] = logit(overflow)


def build_scene(mc, grid=14):
    raw = np.zeros((grid, grid, mc.head_channels), dtype=np.float32)
    # Leere Felder: obj-Logit deutlich negativ.
    for k in range(mc.slots):
        raw[:, :, k * mc.per_slot] = -8.0
    e = mc.slots * mc.per_slot
    raw[:, :, e + 1] = -8.0
    raw[:, :, e + 2] = -8.0

    # Stelle A (Feld 3,3): drei stark ueberlagerte Objekte, fast gleiche Lage.
    c = raw[3, 3]
    write_slot(c, 0, mc, obj=0.90, ox=0.50, oy=0.50, w_frac=0.12, h_frac=0.05,
               angle=10.0, vis=0.95, cls=0)
    write_slot(c, 1, mc, obj=0.85, ox=0.55, oy=0.52, w_frac=0.12, h_frac=0.05,
               angle=16.0, vis=0.60, cls=1)
    write_slot(c, 2, mc, obj=0.80, ox=0.45, oy=0.48, w_frac=0.12, h_frac=0.05,
               angle=22.0, vis=0.35, cls=2)
    write_extras(c, mc, count=3, overlap=0.95, overflow=0.05)

    # Stelle B (Feld 9,5): zwei ueberlagerte Objekte, unabhaengig von A.
    c = raw[5, 9]
    write_slot(c, 0, mc, obj=0.88, ox=0.5, oy=0.5, w_frac=0.09, h_frac=0.09,
               angle=0.0, vis=0.98, cls=3)
    write_slot(c, 1, mc, obj=0.70, ox=0.6, oy=0.45, w_frac=0.09, h_frac=0.09,
               angle=80.0, vis=0.55, cls=3)
    write_extras(c, mc, count=2, overlap=0.90, overflow=0.05)

    # Stelle C (Feld 11,11): Ueberfuellung - mehr Objekte als Slots.
    c = raw[11, 11]
    for k in range(mc.slots):
        write_slot(c, k, mc, obj=0.75, ox=0.5 + 0.04 * k, oy=0.5,
                   w_frac=0.07, h_frac=0.04, angle=30.0 * k, vis=0.5, cls=4)
    write_extras(c, mc, count=5, overlap=0.97, overflow=0.92)

    # Duplikat: dasselbe Objekt wie Stelle B, im Nachbarfeld gemeldet.
    # Das MUSS zusammengefasst werden - es ist kein zweites Objekt.
    c = raw[5, 10]
    write_slot(c, 0, mc, obj=0.60, ox=-0.42, oy=0.5, w_frac=0.09, h_frac=0.09,
               angle=1.0, vis=0.98, cls=3)
    write_extras(c, mc, count=1, overlap=0.05, overflow=0.02)

    return raw


def main() -> int:
    mc = config.ModelConfig(num_classes=8, slots=3)
    mc.validate()
    grid, img = 14, (896.0, 896.0)

    print(f"Kopf: {grid}x{grid}x{mc.head_channels} "
          f"= {mc.slots} Slots x (8 + {mc.num_classes}) + {mc.CELL_EXTRAS}")
    print()

    raw = build_scene(mc, grid)
    dets, flagged = postprocess.decode_head(raw, img, model_cfg=mc)
    print(f"dekodiert: {len(dets)} Treffer, {len(flagged)} auffaellige Felder")

    nms = config.NMSParams(score_thresh=0.25, iou_thresh=0.55)
    kept = postprocess.soft_nms(dets, nms)
    print(f"nach Soft-NMS mit Feldschutz: {len(kept)} Treffer")

    ohne = postprocess.soft_nms(dets, config.NMSParams(
        score_thresh=0.25, iou_thresh=0.55, protect_same_cell=False, soft=False))
    print(f"zum Vergleich, Standard-NMS ohne Feldschutz: {len(ohne)} Treffer")
    print()

    ok = True

    # 1 - drei Objekte aus Feld (3,3)
    a = [d for d in kept if d.meta.get("cell") == (3, 3)]
    good = len(a) == 3
    ok &= good
    print(f"[{'OK ' if good else 'FEHL'}] Stelle A: 3 lokal ueberlagerte Objekte "
          f"getrennt erhalten (erhalten: {len(a)})")
    if len(a) >= 2:
        iou = rotated_iou(a[0].box, a[1].box)
        print(f"         Rahmen-IoU der beiden staerksten: {iou:.2f} "
              f"(> {nms.iou_thresh} -> Standard-NMS haette geloescht)")
    for d in a:
        print(f"         Slot {d.meta['slot']}  Klasse {d.class_id}  "
              f"score {d.score:.2f}  Sichtbarkeit {d.meta['visibility']:.2f}  "
              f"{d.occlusion.name}")

    # 2 - unabhaengige Stellen
    b = [d for d in kept if d.meta.get("cell") == (9, 5)]
    cc = [d for d in kept if d.meta.get("cell") == (11, 11)]
    good = len(b) == 2 and len(cc) == 3
    ok &= good
    print(f"[{'OK ' if good else 'FEHL'}] Stellen B und C unabhaengig verarbeitet "
          f"(B: {len(b)}, C: {len(cc)})")

    # 3 - Ueberfuellung gemeldet
    notes = postprocess.overflow_notes(flagged, kept)
    good = any(n["cell"] == (11, 11) for n in notes)
    ok &= good
    print(f"[{'OK ' if good else 'FEHL'}] Ueberfuellung an Stelle C gemeldet")
    for n in notes:
        print(f"         Feld {n['cell']}: local_count {n['local_count']}, "
              f"overflow {n['overflow_prob']}, ausgegeben {n['ausgegeben']}")
        print(f"         -> {n['hinweis']}")

    # 4 - Duplikat aus Nachbarfeld zusammengefasst
    dup = [d for d in kept if d.meta.get("cell") == (10, 5)]
    good = len(dup) == 0
    ok &= good
    print(f"[{'OK ' if good else 'FEHL'}] Duplikat aus Nachbarfeld zusammengefasst "
          f"(uebrig: {len(dup)})")

    # 5 - Standard-NMS verliert tatsaechlich Objekte (Gegenprobe)
    good = len(ohne) < len(kept)
    ok &= good
    print(f"[{'OK ' if good else 'FEHL'}] Gegenprobe: ohne Feldschutz gehen "
          f"{len(kept) - len(ohne)} Objekte verloren")
    print()

    # 6 - reihenfolgeunabhaengige Zuordnung
    preds = [
        {"cx": 300.0, "cy": 300.0, "width": 100.0, "height": 40.0, "angle": 20.0,
         "class_probs": [0.1, 0.8, 0.1]},                       # passt zu GT 1
        {"cx": 100.0, "cy": 100.0, "width": 100.0, "height": 40.0, "angle": 5.0,
         "class_probs": [0.9, 0.05, 0.05]},                     # passt zu GT 0
        {"cx": 500.0, "cy": 500.0, "width": 60.0, "height": 60.0, "angle": 0.0,
         "class_probs": [0.05, 0.05, 0.9]},                     # passt zu GT 2
    ]
    gts = [
        GtObject(100, 100, 100, 40, 5.0, 0),
        GtObject(300, 300, 100, 40, 20.0, 1),
        GtObject(500, 500, 60, 60, 0.0, 2, rotation_matters=False),
    ]
    mapping, cost = best_assignment(preds, gts, cell_px=64.0)
    good = mapping == [1, 0, 2]
    ok &= good
    print(f"[{'OK ' if good else 'FEHL'}] Zuordnung reihenfolgeunabhaengig: "
          f"Slot->Objekt {mapping}, Kosten {cost:.3f}")
    print("         Slot 0 hat das zweite Objekt bekommen - genau das soll "
          "moeglich sein.")

    # 7 - Zielgitter
    tgt = build_targets(gts, grid, img, mc)
    e = mc.slots * mc.per_slot
    n_cells = int((tgt[:, :, 0] > 0).sum())
    good = tgt.shape == (grid, grid, mc.head_channels) and n_cells == 3
    ok &= good
    print(f"[{'OK ' if good else 'FEHL'}] Zielgitter {tgt.shape}, "
          f"{n_cells} belegte Felder")

    # 8 - Overflow im Zielgitter
    many = [GtObject(100 + 2 * i, 100 + 2 * i, 40, 20, 10.0 * i, i % 3)
            for i in range(5)]
    tgt2 = build_targets(many, grid, img, mc)
    overflow_cells = int((tgt2[:, :, e + 2] > 0).sum())
    good = overflow_cells >= 1
    ok &= good
    print(f"[{'OK ' if good else 'FEHL'}] Zielgitter markiert Ueberfuellung bei "
          f"5 Objekten in einem Feld ({overflow_cells} Feld(er))")

    print()
    print("GESAMT:", "OK" if ok else "FEHLER")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
