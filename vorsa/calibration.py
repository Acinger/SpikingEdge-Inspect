"""Perspektivkorrektur und Millimeter-Kalibrierung.

Ziel: aus dem schraegen Kamerabild ein Bild erzeugen, in dem 1 mm auf dem Band
exakt PX_PER_MM Pixeln entspricht. Ohne diesen Schritt ist jede Aussage ueber
"80 x 22 mm" wertlos, weil Teile am Bildrand kleiner erscheinen als in der Mitte.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import cv2
import numpy as np

from . import config


@dataclass
class Calibration:
    """Homographie Kamerabild -> entzerrtes Bandbild in mm-Raster."""

    H: np.ndarray                       # 3x3
    out_size: Tuple[int, int]           # (w, h) in px
    px_per_mm: float

    # ------------------------------------------------------------------
    def undistort_board(self, frame: np.ndarray) -> np.ndarray:
        return cv2.warpPerspective(
            frame, self.H, self.out_size, flags=cv2.INTER_LINEAR
        )

    def px_to_mm(self, px: float) -> float:
        return px / self.px_per_mm

    def mm_to_px(self, mm: float) -> float:
        return mm * self.px_per_mm

    def point_to_mm(self, pt: Sequence[float]) -> Tuple[float, float]:
        return (pt[0] / self.px_per_mm, pt[1] / self.px_per_mm)

    # ------------------------------------------------------------------
    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "H": self.H.tolist(),
                    "out_size": list(self.out_size),
                    "px_per_mm": self.px_per_mm,
                },
                fh,
                indent=2,
            )

    @staticmethod
    def load(path: str) -> "Calibration":
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        return Calibration(
            H=np.asarray(d["H"], dtype=np.float64),
            out_size=(int(d["out_size"][0]), int(d["out_size"][1])),
            px_per_mm=float(d["px_per_mm"]),
        )


# ----------------------------------------------------------------------
def order_corners(pts: np.ndarray) -> np.ndarray:
    """Sortiert 4 Punkte nach oben-links, oben-rechts, unten-rechts, unten-links."""
    pts = np.asarray(pts, dtype=np.float32).reshape(4, 2)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    out = np.zeros((4, 2), dtype=np.float32)
    out[0] = pts[np.argmin(s)]
    out[2] = pts[np.argmax(s)]
    out[1] = pts[np.argmin(d)]
    out[3] = pts[np.argmax(d)]
    return out


def from_reference_rect(
    image_corners: Sequence[Sequence[float]],
    rect_width_mm: float,
    rect_height_mm: float,
    px_per_mm: float = config.PX_PER_MM,
    board_width_mm: float = config.BOARD_WIDTH_MM,
    board_height_mm: float = config.BOARD_HEIGHT_MM,
    origin_mm: Tuple[float, float] = (0.0, 0.0),
) -> Calibration:
    """Kalibriert ueber ein bekanntes Rechteck im Bild.

    Praktisch: ein aufgeklebtes Blatt oder eine gefraeste Platte mit
    exakt bekannten Aussenmassen auf das Band legen, die vier Ecken im Bild
    anklicken, Masse in mm angeben.
    """
    src = order_corners(np.asarray(image_corners, dtype=np.float32))
    x0, y0 = origin_mm
    dst = np.array(
        [
            [x0, y0],
            [x0 + rect_width_mm, y0],
            [x0 + rect_width_mm, y0 + rect_height_mm],
            [x0, y0 + rect_height_mm],
        ],
        dtype=np.float32,
    ) * px_per_mm

    H = cv2.getPerspectiveTransform(src, dst)
    out_size = (
        int(round(board_width_mm * px_per_mm)),
        int(round(board_height_mm * px_per_mm)),
    )
    return Calibration(H=H.astype(np.float64), out_size=out_size, px_per_mm=px_per_mm)


def from_chessboard(
    image: np.ndarray,
    pattern: Tuple[int, int],
    square_mm: float,
    px_per_mm: float = config.PX_PER_MM,
    board_width_mm: float = config.BOARD_WIDTH_MM,
    board_height_mm: float = config.BOARD_HEIGHT_MM,
) -> Optional[Calibration]:
    """Kalibriert ueber ein Schachbrettmuster auf dem Band.

    `pattern` = (Spalten, Zeilen) der *inneren* Ecken.
    Gibt None zurueck, wenn das Muster nicht gefunden wurde.
    """
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    found, corners = cv2.findChessboardCorners(
        gray,
        pattern,
        flags=cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE,
    )
    if not found:
        return None

    corners = cv2.cornerSubPix(
        gray,
        corners,
        (11, 11),
        (-1, -1),
        (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001),
    ).reshape(-1, 2)

    cols, rows = pattern
    src = np.array(
        [
            corners[0],
            corners[cols - 1],
            corners[-1],
            corners[-cols],
        ],
        dtype=np.float32,
    )
    dst = np.array(
        [
            [0.0, 0.0],
            [(cols - 1) * square_mm, 0.0],
            [(cols - 1) * square_mm, (rows - 1) * square_mm],
            [0.0, (rows - 1) * square_mm],
        ],
        dtype=np.float32,
    ) * px_per_mm

    H = cv2.getPerspectiveTransform(src, dst)
    out_size = (
        int(round(board_width_mm * px_per_mm)),
        int(round(board_height_mm * px_per_mm)),
    )
    return Calibration(H=H.astype(np.float64), out_size=out_size, px_per_mm=px_per_mm)


def identity(
    size_px: Tuple[int, int], px_per_mm: float = config.PX_PER_MM
) -> Calibration:
    """Platzhalter-Kalibrierung fuer Tests mit synthetischen Bildern."""
    return Calibration(H=np.eye(3), out_size=size_px, px_per_mm=px_per_mm)


def residual_check(
    cal: Calibration,
    image_points: Sequence[Sequence[float]],
    world_points_mm: Sequence[Sequence[float]],
) -> List[float]:
    """Restfehler der Kalibrierung in mm, je Kontrollpunkt.

    Immer ausfuehren: eine Homographie laesst sich auch auf falsch geklickte
    Ecken rechnen, ohne dass es auffaellt. Erst der Restfehler zeigt es.
    """
    pts = np.asarray(image_points, dtype=np.float32).reshape(-1, 1, 2)
    proj = cv2.perspectiveTransform(pts, cal.H).reshape(-1, 2) / cal.px_per_mm
    world = np.asarray(world_points_mm, dtype=np.float32).reshape(-1, 2)
    return list(np.linalg.norm(proj - world, axis=1))
