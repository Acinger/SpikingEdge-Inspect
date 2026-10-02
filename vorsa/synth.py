"""Synthetische Bandbilder mit bekannter Wahrheit.

Damit laesst sich die gesamte Pipeline heute testen - ohne Kamera, ohne Band,
ohne Akida. Und wichtiger: mit *bekannter* Teilezahl, sodass die Zaehlgenauigkeit
(Kriterien A2/A3 in SPEC.md) tatsaechlich messbar ist statt nur geschaetzt.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np

from . import config


@dataclass
class GroundTruthPart:
    cx: float
    cy: float
    angle: float
    on_top: bool = False


@dataclass
class SynthScene:
    image: np.ndarray
    background: np.ndarray
    parts: List[GroundTruthPart]
    px_per_mm: float

    @property
    def count(self) -> int:
        return len(self.parts)


def _belt(size_px: Tuple[int, int], rng: np.random.Generator) -> np.ndarray:
    w, h = size_px
    base = np.full((h, w, 3), 55, dtype=np.uint8)
    noise = rng.normal(0, 5, (h, w, 1)).astype(np.int16)
    base = np.clip(base.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    # Bandnaht als Stoerkante quer ueber das Band
    y = int(h * 0.78)
    cv2.line(base, (0, y), (w, y), (72, 70, 68), 2)
    return cv2.GaussianBlur(base, (3, 3), 0)


def _draw_part(
    img: np.ndarray,
    part: GroundTruthPart,
    px_per_mm: float,
    rng: np.random.Generator,
    shadow: bool = True,
) -> None:
    L = config.PART_LENGTH_MM * px_per_mm
    W = config.PART_WIDTH_MM * px_per_mm
    rect = ((part.cx, part.cy), (L, W), part.angle)
    pts = cv2.boxPoints(rect).astype(np.int32)

    if shadow:
        off = pts + np.array([3, 3])
        cv2.fillConvexPoly(img, off, (35, 33, 32), lineType=cv2.LINE_AA)

    tone = int(rng.integers(150, 190))
    cv2.fillConvexPoly(img, pts, (tone - 12, tone - 6, tone), lineType=cv2.LINE_AA)
    cv2.polylines(img, [pts], True, (tone + 25, tone + 25, tone + 25), 1, cv2.LINE_AA)


def make_scene(
    kind: str = "mixed",
    px_per_mm: float = config.PX_PER_MM,
    size_mm: Tuple[float, float] = (config.BOARD_WIDTH_MM, config.BOARD_HEIGHT_MM),
    seed: int = 0,
) -> SynthScene:
    """kind: 'free' | 'touching' | 'overlap' | 'mixed' | 'stacked'."""
    rng = np.random.default_rng(seed)
    size_px = (int(size_mm[0] * px_per_mm), int(size_mm[1] * px_per_mm))
    bg = _belt(size_px, rng)
    img = bg.copy()

    L = config.PART_LENGTH_MM * px_per_mm
    W = config.PART_WIDTH_MM * px_per_mm
    parts: List[GroundTruthPart] = []

    if kind == "free":
        parts = [
            GroundTruthPart(0.30 * size_px[0], 0.30 * size_px[1], 12.0),
            GroundTruthPart(0.70 * size_px[0], 0.65 * size_px[1], 105.0),
        ]

    elif kind == "touching":
        # Zwei Teile Schulter an Schulter, Abstand = Breite (Kontakt, kein Stapel)
        cx, cy, ang = 0.5 * size_px[0], 0.45 * size_px[1], 20.0
        n = np.array([-np.sin(np.radians(ang)), np.cos(np.radians(ang))])
        for k in (-0.52, 0.52):
            p = np.array([cx, cy]) + n * (k * W * 2.0)
            parts.append(GroundTruthPart(float(p[0]), float(p[1]), ang))

    elif kind == "overlap":
        # Zweites Teil liegt zu ~40 % auf dem ersten
        parts = [
            GroundTruthPart(0.42 * size_px[0], 0.45 * size_px[1], 8.0),
            GroundTruthPart(0.42 * size_px[0] + 0.55 * L, 0.45 * size_px[1] + 0.25 * W,
                            22.0, on_top=True),
        ]

    elif kind == "stacked":
        # Physikalische Grenze: exakt deckungsgleich gestapelt
        parts = [
            GroundTruthPart(0.5 * size_px[0], 0.5 * size_px[1], 35.0),
            GroundTruthPart(0.5 * size_px[0], 0.5 * size_px[1], 35.0, on_top=True),
        ]

    else:  # mixed
        parts = [
            GroundTruthPart(0.20 * size_px[0], 0.25 * size_px[1], 5.0),
            GroundTruthPart(0.55 * size_px[0], 0.30 * size_px[1], 95.0),
            GroundTruthPart(0.58 * size_px[0], 0.30 * size_px[1] + 1.6 * W, 95.0),
            GroundTruthPart(0.72 * size_px[0], 0.70 * size_px[1], 140.0),
            GroundTruthPart(0.72 * size_px[0] + 0.5 * L, 0.70 * size_px[1] + 0.3 * W,
                            150.0, on_top=True),
        ]

    for p in sorted(parts, key=lambda q: q.on_top):
        _draw_part(img, p, px_per_mm, rng)

    img = cv2.GaussianBlur(img, (3, 3), 0)
    return SynthScene(image=img, background=bg, parts=parts, px_per_mm=px_per_mm)


ALL_KINDS = ("free", "touching", "overlap", "mixed", "stacked")
