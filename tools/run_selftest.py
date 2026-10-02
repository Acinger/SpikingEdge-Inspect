#!/usr/bin/env python3
"""Selbsttest der Pi-Pipeline auf synthetischen Szenen.

    python3 tools/run_selftest.py --out ergebnisse/

Prueft je Szene die erkannte Teilezahl gegen die bekannte Wahrheit und
schreibt Overlay-Bilder zum Anschauen. Laeuft ohne Kamera und ohne Akida.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vorsa import calibration, config, overlay, synth   # noqa: E402
from vorsa.akida_pool import AkidaPool                  # noqa: E402
from vorsa.pipeline import Pipeline                     # noqa: E402


# Erwartete Zaehlung. 'stacked' ist der ehrliche Sonderfall: aus der Draufsicht
# sind zwei deckungsgleiche Teile nicht trennbar, 1 ist das korrekte Ergebnis
# einer Einzelbildmessung.
EXPECTED = {
    "free": 2,
    "touching": 2,
    "overlap": 2,
    "mixed": 5,
    "stacked": 1,
}


def match_errors(res, scene):
    """Ordnet Detektionen den bekannten Teilen zu und misst Lage- und Winkelfehler.

    Nur so werden die Kriterien A4/A5 aus SPEC.md wirklich gemessen statt
    geschaetzt. Bei 'stacked' liegen zwei Teile deckungsgleich - dort wird nur
    das sichtbare obere Teil bewertet.
    """
    import math

    gt = [
        (p.cx / scene.px_per_mm, p.cy / scene.px_per_mm, p.angle % 180.0)
        for p in scene.parts
    ]
    used, pos_err, ang_err = set(), [], []

    for d in res.detections:
        dx, dy = d.center_mm(scene.px_per_mm)
        best_i, best_d = -1, 1e9
        for i, (gx, gy, _) in enumerate(gt):
            if i in used:
                continue
            dist = math.hypot(dx - gx, dy - gy)
            if dist < best_d:
                best_i, best_d = i, dist
        if best_i < 0 or best_d > 25.0:
            continue
        used.add(best_i)
        pos_err.append(best_d)
        da = abs(d.box.angle - gt[best_i][2]) % 180.0
        ang_err.append(min(da, 180.0 - da))

    return pos_err, ang_err


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="selftest_out")
    ap.add_argument("--use-background", action="store_true",
                    help="leeres Band als Referenz nutzen (empfohlen)")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    cfg = config.RuntimeConfig(profile="P1", draw_debug=True)
    pool = AkidaPool(model_file="", num_classes=config.NUM_CLASSES)

    ok_all = True
    all_pos, all_ang = [], []
    print(f"{'Szene':<10} {'erwartet':>9} {'erkannt':>8} {'Status':>8}   Zeiten")
    print("-" * 78)

    for kind in synth.ALL_KINDS:
        scene = synth.make_scene(kind, seed=42)
        cal = calibration.identity(
            (scene.image.shape[1], scene.image.shape[0]), scene.px_per_mm
        )
        pipe = Pipeline(
            cal, cfg, pool=pool,
            background_ref=scene.background if args.use_background else None,
        )
        res = pipe.process(scene.image)

        exp = EXPECTED[kind]
        good = res.count == exp
        ok_all &= good
        print(f"{kind:<10} {exp:>9} {res.count:>8} {'OK' if good else 'ABW':>8}   "
              f"{res.timings_ms}")

        for d in res.detections:
            rec = d.as_record(scene.px_per_mm)
            print(f"    #{rec['track_id']:<3} {rec['x_mm']:>7.1f},{rec['y_mm']:>7.1f} mm  "
                  f"{rec['length_mm']:>5.1f}x{rec['width_mm']:<5.1f}  "
                  f"{rec['angle_deg']:>6.1f} deg  occ={rec['occlusion']}  "
                  f"{d.meta.get('case', '')}")
        for dg in res.diagnostics:
            if "warn" in dg:
                print(f"    ! Blob {dg['blob']}: {dg['warn']}")

        pos_err, ang_err = match_errors(res, scene)
        all_pos += pos_err
        all_ang += ang_err
        if pos_err:
            print(f"    Lagefehler max {max(pos_err):.2f} mm, "
                  f"Winkelfehler max {max(ang_err):.2f} deg")

        cv2.imwrite(str(out / f"{kind}_overlay.png"), pipe.render(res))
        if res.mask is not None:
            cv2.imwrite(str(out / f"{kind}_masken.png"),
                        overlay.draw_mask_debug(res.mask, res.part_masks))
        cv2.imwrite(str(out / f"{kind}_eingang.png"), scene.image)

    pool.close()
    print("-" * 78)

    import statistics as st
    if all_pos:
        med_pos, med_ang = st.median(all_pos), st.median(all_ang)
        a5 = med_pos <= 1.0
        a4 = med_ang <= 3.0
        print(f"A5 Mittelpunktfehler median: {med_pos:.2f} mm  (Ziel <= 1.00) "
              f"{'OK' if a5 else 'ABW'}")
        print(f"A4 Winkelfehler median:      {med_ang:.2f} deg (Ziel <= 3.00) "
              f"{'OK' if a4 else 'ABW'}")
        ok_all &= a4 and a5

    print(f"Akida-Pool: {pool.stats()}")
    print(f"Bilder in: {out.resolve()}")
    print("GESAMT:", "OK" if ok_all else "Abweichungen vorhanden")
    print("\nHinweis: das sind synthetische Bilder mit perfekter Kalibrierung.")
    print("Die echten Werte am Band werden schlechter - der Test zeigt nur,")
    print("dass die Rechenkette selbst keinen Fehler einbaut.")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
