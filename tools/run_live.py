#!/usr/bin/env python3
"""Livebetrieb auf dem Raspberry Pi 5.

    python3 tools/run_live.py --calib calibration.json
    python3 tools/run_live.py --calib calibration.json --model vorsa_crop.fbz
    python3 tools/run_live.py --calib calibration.json --profile P2 --model vorsa_m3.fbz

Vorher einmal das leere Band aufnehmen - das verbessert die Maske deutlich:
    python3 tools/run_live.py --calib calibration.json --grab-background band_leer.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vorsa import calibration, config    # noqa: E402
from vorsa.pipeline import run_camera    # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calib", default="calibration.json")
    ap.add_argument("--model", default="", help=".fbz; leer -> Stub-Klassifikator")
    ap.add_argument("--profile", default="P1", choices=("P1", "P2"))
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--background", default="", help="Bild des leeren Bandes")
    ap.add_argument("--grab-background", default="",
                    help="ein Bild aufnehmen und als Bandreferenz speichern")
    args = ap.parse_args()

    if args.grab_background:
        cap = cv2.VideoCapture(args.camera)
        ok, frame = cap.read()
        cap.release()
        if not ok:
            print("Kamera liefert kein Bild.")
            return 1
        cal = calibration.Calibration.load(args.calib)
        cv2.imwrite(args.grab_background, cal.undistort_board(frame))
        print(f"Bandreferenz gespeichert: {args.grab_background}")
        return 0

    if not Path(args.calib).exists():
        print(f"Kalibrierung fehlt: {args.calib}")
        print("Zuerst tools/calibrate_board.py ausfuehren.")
        return 1

    import os
    if os.name == "posix" and sys.platform != "darwin" and not (
            os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        print("Keine Anzeige vorhanden - der Livebetrieb zeigt ein Fenster.")
        print("Ueber SSH geht das nicht. Direkt am Pi oder per VNC arbeiten.")
        print()
        print("Ohne Anzeige pruefen laesst sich die Kette so:")
        print("  python3 tools/run_selftest.py --use-background --out ergebnis/")
        print("Das schreibt Overlay-Bilder in einen Ordner, statt sie anzuzeigen.")
        return 1

    cal = calibration.Calibration.load(args.calib)
    cfg = config.RuntimeConfig(
        profile=args.profile, camera_index=args.camera, model_file=args.model
    )

    bg = cv2.imread(args.background) if args.background else None
    if args.background and bg is None:
        print(f"Bandreferenz nicht lesbar: {args.background} - laufe ohne.")

    run_camera(cal, cfg, background_ref=bg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
