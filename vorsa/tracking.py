"""Objektverfolgung ueber die Bandbewegung.

Zwei Aufgaben:
  1. stabile Objekt-IDs, damit ein Teil nicht in jedem Bild neu gezaehlt wird.
  2. Aufloesung von Fall 3: ein Teil, das jetzt verdeckt ist, war ein paar
     Bilder vorher vielleicht noch frei sichtbar. Diese aeltere Beobachtung
     ist mehr wert als jede Schaetzung aus dem aktuellen Einzelbild.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from .config import TrackingParams
from .detection import Detection, Occlusion


@dataclass
class Track:
    track_id: int
    cx: float
    cy: float
    angle: float
    class_id: int = -1
    class_score: float = 0.0
    hits: int = 1
    missed: int = 0
    confirmed: bool = False
    best_occlusion: Occlusion = Occlusion.UNRESOLVED
    history: List[Tuple[float, float]] = field(default_factory=list)

    def predict(self, dx: float, dy: float) -> Tuple[float, float]:
        return self.cx + dx, self.cy + dy


class BeltTracker:
    """Einfacher Naechster-Nachbar-Tracker mit Bandvorhersage.

    Bewusst kein Kalman-Filter: die Bewegung auf einem Foerderband ist
    gleichfoermig und bekannt. Ein Kalman-Filter waere hier zusaetzliche
    Komplexitaet ohne Nutzen.
    """

    def __init__(self, params: TrackingParams, px_per_mm: float, fps: float = 30.0):
        self.p = params
        self.px_per_mm = px_per_mm
        self.fps = max(fps, 1e-3)
        self.tracks: Dict[int, Track] = {}
        self._next_id = 1

    # ------------------------------------------------------------------
    @property
    def _shift_px(self) -> Tuple[float, float]:
        """Erwartete Verschiebung pro Bild. Bandrichtung = +y im entzerrten Bild."""
        if self.p.belt_speed_mm_s <= 0:
            return (0.0, 0.0)
        d = self.p.belt_speed_mm_s / self.fps * self.px_per_mm
        return (0.0, d)

    # ------------------------------------------------------------------
    def update(self, dets: List[Detection]) -> List[Detection]:
        dx, dy = self._shift_px
        max_dist = self.p.max_match_dist_mm * self.px_per_mm

        unmatched = set(range(len(dets)))
        for tid, tr in self.tracks.items():
            px_, py_ = tr.predict(dx, dy)
            best_i, best_d = -1, max_dist
            for i in unmatched:
                b = dets[i].box
                d = math.hypot(b.cx - px_, b.cy - py_)
                if d < best_d:
                    best_i, best_d = i, d

            if best_i >= 0:
                det = dets[best_i]
                unmatched.discard(best_i)
                tr.cx, tr.cy, tr.angle = det.box.cx, det.box.cy, det.box.angle
                tr.hits += 1
                tr.missed = 0
                tr.confirmed = tr.confirmed or tr.hits >= self.p.min_hits_to_confirm
                tr.history.append((tr.cx, tr.cy))

                # Klasse uebernehmen, wenn diesmal sicherer beobachtet.
                if det.class_score > tr.class_score:
                    tr.class_id, tr.class_score = det.class_id, det.class_score
                if det.occlusion < tr.best_occlusion:
                    tr.best_occlusion = det.occlusion

                det.track_id = tid
                # Frueher freie Sicht schlaegt heutige Schaetzung.
                if det.occlusion in (Occlusion.PARTIAL, Occlusion.UNRESOLVED):
                    if tr.best_occlusion == Occlusion.FREE:
                        det.meta["occlusion_resolved_by"] = "tracking"
                        det.class_id = tr.class_id
                        det.class_score = tr.class_score
            else:
                tr.missed += 1

        for i in unmatched:
            det = dets[i]
            tid = self._next_id
            self._next_id += 1
            self.tracks[tid] = Track(
                track_id=tid,
                cx=det.box.cx,
                cy=det.box.cy,
                angle=det.box.angle,
                class_id=det.class_id,
                class_score=det.class_score,
                best_occlusion=det.occlusion,
                history=[(det.box.cx, det.box.cy)],
            )
            det.track_id = tid

        dead = [tid for tid, tr in self.tracks.items() if tr.missed > self.p.max_missed_frames]
        for tid in dead:
            del self.tracks[tid]

        return dets

    # ------------------------------------------------------------------
    def confirmed_count(self) -> int:
        return sum(1 for t in self.tracks.values() if t.confirmed)

    def estimate_belt_speed(self) -> Optional[float]:
        """Schaetzt die Bandgeschwindigkeit in mm/s aus den Spuren.

        Praktisch fuer die Inbetriebnahme: statt zu messen, einfach ein paar
        Sekunden laufen lassen und den Wert in config.TrackingParams eintragen.
        """
        speeds = []
        for tr in self.tracks.values():
            if len(tr.history) < 3:
                continue
            pts = np.asarray(tr.history[-10:], dtype=float)
            steps = np.linalg.norm(np.diff(pts, axis=0), axis=1)
            if len(steps):
                speeds.append(float(np.median(steps)))
        if not speeds:
            return None
        return float(np.median(speeds)) / self.px_per_mm * self.fps
