#!/usr/bin/env python3
"""Kalibrierung des Bandbildes.

Variante 1 - Referenzrechteck anklicken (kein Schachbrett noetig):
    python3 tools/calibrate_board.py --click --width-mm 200 --height-mm 150

Variante 2 - Schachbrett auf dem Band:
    python3 tools/calibrate_board.py --chessboard 9x6 --square-mm 20

Ergebnis: calibration.json. Ohne diese Datei sind alle mm-Angaben wertlos.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vorsa import calibration, config    # noqa: E402


def hat_bildschirm() -> bool:
    """Gibt es eine Anzeige? Ueber SSH ohne X-Weiterleitung nicht."""
    if os.name == "nt" or sys.platform == "darwin":
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def kein_bildschirm_hinweis() -> None:
    print("Dieses Werkzeug braucht eine Anzeige - ueber SSH gibt es keine.")
    print()
    print("Drei Moeglichkeiten:")
    print("  1. Direkt am Pi arbeiten (Monitor, Tastatur, Maus)")
    print("  2. Fernzugriff auf den Desktop des Pi (VNC)")
    print("  3. Ohne Anzeige kalibrieren: Bild aufnehmen, Ecken ablesen,")
    print("     dann mit --corners uebergeben, z.B.")
    print("       python3 tools/calibrate_board.py --image band.png \\")
    print("         --corners 120,80 900,95 890,610 130,600 \\")
    print("         --width-mm 200 --height-mm 150")


clicked = []


def _on_mouse(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN and len(clicked) < 4:
        clicked.append((float(x), float(y)))
        print(f"  Ecke {len(clicked)}: ({x}, {y})")


def grab(source: str, camera: int):
    if source:
        img = cv2.imread(source)
        if img is None:
            raise SystemExit(f"Bild nicht lesbar: {source}")
        return img
    cap = cv2.VideoCapture(camera)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise SystemExit(f"Kamera {camera} liefert kein Bild.")
    return frame


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default="", help="statt Kamera ein Bild verwenden")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--click", action="store_true")
    ap.add_argument("--corners", nargs=4, metavar="X,Y",
                    help="vier Bildecken ohne Anzeige, z.B. 120,80 900,95 890,610 130,600")
    ap.add_argument("--width-mm", type=float, default=200.0)
    ap.add_argument("--height-mm", type=float, default=150.0)
    ap.add_argument("--chessboard", default="", help='z.B. "9x6" (innere Ecken)')
    ap.add_argument("--square-mm", type=float, default=20.0)
    ap.add_argument("--out", default="calibration.json")
    args = ap.parse_args()

    if args.click and not hat_bildschirm():
        kein_bildschirm_hinweis()
        return 1

    frame = grab(args.image, args.camera)

    if args.corners:
        punkte = []
        for teil in args.corners:
            x, y = teil.replace(";", ",").split(",")
            punkte.append((float(x), float(y)))
        print(f"Ecken uebernommen: {punkte}")
        cal = calibration.from_reference_rect(punkte, args.width_mm, args.height_mm)
        # from_reference_rect sortiert die Ecken (oben-links, oben-rechts,
        # unten-rechts, unten-links). Fuer die Fehlerpruefung muss dieselbe
        # Reihenfolge verwendet werden, sonst vergleicht man Ecke gegen Ecke
        # ueber Kreuz und bekommt sinnlos grosse Werte.
        sortiert = calibration.order_corners(punkte)
        rest = calibration.residual_check(
            cal, sortiert,
            [(0, 0), (args.width_mm, 0),
             (args.width_mm, args.height_mm), (0, args.height_mm)],
        )
        print(f"Restfehler je Ecke in mm: {[round(r, 2) for r in rest]}")
        print("Werte deutlich ueber 1 mm heissen: eine Ecke wurde falsch abgelesen.")
        cal.save(args.out)
        cv2.imwrite("calibration_check.png", cal.undistort_board(frame))
        print(f"Gespeichert: {args.out}, Kontrollbild: calibration_check.png")
        return 0

    if args.chessboard:
        cols, rows = (int(v) for v in args.chessboard.lower().split("x"))
        cal = calibration.from_chessboard(frame, (cols, rows), args.square_mm)
        if cal is None:
            print("Schachbrett nicht gefunden. Beleuchtung pruefen oder --click nutzen.")
            return 1
    elif args.click:
        print("Vier Ecken des Referenzrechtecks anklicken (beliebige Reihenfolge).")
        cv2.namedWindow("Kalibrierung")
        cv2.setMouseCallback("Kalibrierung", _on_mouse)
        while len(clicked) < 4:
            view = frame.copy()
            for p in clicked:
                cv2.circle(view, (int(p[0]), int(p[1])), 5, (0, 255, 0), -1)
            cv2.imshow("Kalibrierung", view)
            if cv2.waitKey(20) & 0xFF == 27:
                cv2.destroyAllWindows()
                return 1
        cv2.destroyAllWindows()
        cal = calibration.from_reference_rect(clicked, args.width_mm, args.height_mm)
    else:
        print("Bitte --click oder --chessboard angeben.")
        return 2

    cal.save(args.out)
    print(f"\nGespeichert: {args.out}")
    print(f"  Ausgabegroesse: {cal.out_size} px bei {cal.px_per_mm} px/mm")
    print(f"  Ein Teil ist damit {config.PART_LENGTH_MM * cal.px_per_mm:.0f} x "
          f"{config.PART_WIDTH_MM * cal.px_per_mm:.0f} px gross.")

    board = cal.undistort_board(frame)
    cv2.imwrite("calibration_check.png", board)
    print("  Kontrollbild: calibration_check.png")
    print("\nJetzt pruefen: liegt ein bekanntes Mass im Kontrollbild wirklich richtig?")
    print("Dazu ein Teil auflegen, im Kontrollbild ausmessen und mit 80 mm vergleichen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
