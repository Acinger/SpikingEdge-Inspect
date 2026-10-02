"""Gemeinsame Datentypen: gedrehte Box, Detektion, Verdeckungsgrad."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Optional, Tuple

import cv2
import numpy as np


class Occlusion(IntEnum):
    FREE = 0          # freiliegend
    TOUCHING = 1      # beruehrt Nachbarteil, aber vollstaendig sichtbar
    PARTIAL = 2       # teilweise verdeckt, Form rekonstruiert
    UNRESOLVED = 3    # nicht aufloesbar -> nicht raten, melden


@dataclass
class OrientedBox:
    """Gedrehtes Rechteck in Pixelkoordinaten des entzerrten Bandbildes.

    angle: Grad, 0..180, Richtung der *langen* Seite.
    """

    cx: float
    cy: float
    length: float      # lange Seite, px
    width: float       # kurze Seite, px
    angle: float       # Grad

    # ------------------------------------------------------------------
    @staticmethod
    def from_cv_rect(rect) -> "OrientedBox":
        (cx, cy), (w, h), ang = rect
        if w >= h:
            length, width, angle = w, h, ang
        else:
            length, width, angle = h, w, ang + 90.0
        return OrientedBox(cx, cy, length, width, angle % 180.0)

    def to_cv_rect(self):
        return ((self.cx, self.cy), (self.length, self.width), self.angle)

    def corners(self) -> np.ndarray:
        return cv2.boxPoints(self.to_cv_rect()).astype(np.float32)

    @property
    def area(self) -> float:
        return self.length * self.width

    @property
    def aspect(self) -> float:
        return self.length / max(self.width, 1e-6)

    def angle_rad(self) -> float:
        return math.radians(self.angle)

    def scaled(self, factor: float) -> "OrientedBox":
        return OrientedBox(
            self.cx * factor,
            self.cy * factor,
            self.length * factor,
            self.width * factor,
            self.angle,
        )


def rotated_iou(a: OrientedBox, b: OrientedBox) -> float:
    """IoU zweier gedrehter Rechtecke.

    Achsparallele IoU waere hier falsch: zwei um 90 Grad verdrehte Teile
    haetten dann eine hohe Ueberlappung, obwohl sie sich kaum beruehren.
    """
    ok, inter = cv2.rotatedRectangleIntersection(a.to_cv_rect(), b.to_cv_rect())
    if ok == cv2.INTERSECT_NONE or inter is None:
        return 0.0
    inter_area = float(cv2.contourArea(cv2.convexHull(inter)))
    union = a.area + b.area - inter_area
    if union <= 1e-6:
        return 0.0
    return float(max(0.0, min(1.0, inter_area / union)))


@dataclass
class Detection:
    """Ein erkanntes Teil."""

    box: OrientedBox
    contour: Optional[np.ndarray] = None      # Nx1x2, px, sichtbare Aussenlinie
    score: float = 0.0                        # Objektwahrscheinlichkeit
    class_id: int = -1
    class_score: float = 0.0
    occlusion: Occlusion = Occlusion.FREE
    track_id: int = -1
    source: str = ""                          # "geometry" | "akida" | "merged"
    meta: dict = field(default_factory=dict)

    # ------------------------------------------------------------------
    def center_mm(self, px_per_mm: float) -> Tuple[float, float]:
        return (self.box.cx / px_per_mm, self.box.cy / px_per_mm)

    def size_mm(self, px_per_mm: float) -> Tuple[float, float]:
        return (self.box.length / px_per_mm, self.box.width / px_per_mm)

    def as_record(self, px_per_mm: float) -> dict:
        cx, cy = self.center_mm(px_per_mm)
        length, width = self.size_mm(px_per_mm)
        return {
            "track_id": self.track_id,
            "x_mm": round(cx, 2),
            "y_mm": round(cy, 2),
            "length_mm": round(length, 2),
            "width_mm": round(width, 2),
            "angle_deg": round(self.box.angle, 2),
            "class_id": self.class_id,
            "class_score": round(self.class_score, 3),
            "score": round(self.score, 3),
            "occlusion": int(self.occlusion),
            "source": self.source,
        }


def sort_by_score(dets: List[Detection]) -> List[Detection]:
    return sorted(dets, key=lambda d: d.score, reverse=True)
