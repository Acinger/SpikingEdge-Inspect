"""Ausschneiden und Normalisieren der Objektausschnitte fuer die Akidas."""
from __future__ import annotations

from typing import List, Tuple

import cv2
import numpy as np

from .detection import Detection, OrientedBox

# Eingangsgroesse des Crop-Klassifikators (Profil P1).
CROP_SIZE: Tuple[int, int] = (96, 32)      # (Breite, Hoehe) ~ 3:1, nah an 80:22
CROP_MARGIN = 0.12                          # 12 % Rand, damit die Kante mit drin ist


def extract_oriented(
    board: np.ndarray,
    box: OrientedBox,
    size: Tuple[int, int] = CROP_SIZE,
    margin: float = CROP_MARGIN,
) -> np.ndarray:
    """Schneidet ein gedrehtes Rechteck aus und richtet es waagerecht aus.

    Damit sieht der Klassifikator jedes Teil immer in derselben Lage - er muss
    Drehinvarianz nicht erst lernen. Das spart genau die Modellkapazitaet, die
    auf dem AKD1500 knapp ist.
    """
    w = box.length * (1.0 + margin)
    h = box.width * (1.0 + margin)

    src = cv2.boxPoints(((box.cx, box.cy), (w, h), box.angle)).astype(np.float32)
    # boxPoints liefert im Uhrzeigersinn ab unten-links; Zielreihenfolge fixieren.
    dst = np.array(
        [[0, size[1] - 1], [0, 0], [size[0] - 1, 0], [size[0] - 1, size[1] - 1]],
        dtype=np.float32,
    )
    M = cv2.getPerspectiveTransform(src, dst)
    crop = cv2.warpPerspective(board, M, size, flags=cv2.INTER_LINEAR)

    if crop.ndim == 2:
        crop = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
    return np.ascontiguousarray(crop.astype(np.uint8))


def batch_from_detections(
    board: np.ndarray,
    dets: List[Detection],
    size: Tuple[int, int] = CROP_SIZE,
) -> np.ndarray:
    """(N, H, W, 3) uint8 - direkt so, wie akida.Model.forward es erwartet."""
    if not dets:
        return np.zeros((0, size[1], size[0], 3), dtype=np.uint8)
    return np.stack([extract_oriented(board, d.box, size) for d in dets], axis=0)
