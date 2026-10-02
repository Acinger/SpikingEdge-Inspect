"""VORSA-M3 Hauptpipeline.

Profil P1 (Hybrid):
    Bild -> entzerren -> Maske -> Watershed -> Rechteck-Fit
         -> Crops -> 4x AKD1500 (Klassifikation) -> Merge -> Tracking -> Overlay

Profil P2 (Single-Pass):
    Bild -> entzerren -> auf Modelleingang skalieren -> 1x AKD1500 (Detektion)
         -> Kopf dekodieren -> Soft-NMS -> Geometrie-Gate -> Tracking -> Overlay

Beide Profile liefern dieselbe Ausgabestruktur (Liste von Detection).
Damit kann spaeter umgeschaltet werden, ohne den Rest anzufassen.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import cv2
import numpy as np

from . import config, crops, fitting, overlay, postprocess, segmentation
from .akida_pool import AkidaPool, softmax
from .calibration import Calibration
from .config import RuntimeConfig
from .detection import Detection
from .tracking import BeltTracker


@dataclass
class FrameResult:
    detections: List[Detection]
    board: np.ndarray
    mask: Optional[np.ndarray] = None
    part_masks: List[np.ndarray] = field(default_factory=list)
    timings_ms: dict = field(default_factory=dict)
    diagnostics: List[dict] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.detections)

    def records(self, px_per_mm: float) -> List[dict]:
        return [d.as_record(px_per_mm) for d in self.detections]


class Pipeline:
    def __init__(
        self,
        cal: Calibration,
        cfg: RuntimeConfig = config.DEFAULT,
        pool: Optional[AkidaPool] = None,
        background_ref: Optional[np.ndarray] = None,
        fps: float = 30.0,
        geometry_gate: bool = False,
    ):
        self.cal = cal
        self.cfg = cfg
        self.background_ref = background_ref
        # Anwendungsfilter mit bekannter Sollgeometrie. Standardmaessig aus:
        # VORSA-M3 ist nicht auf rechteckige Werkstuecke festgelegt.
        self.geometry_gate = geometry_gate
        self.pool = pool if pool is not None else AkidaPool(
            model_file=cfg.model_file,
            num_classes=config.NUM_CLASSES,
            max_devices=1 if cfg.profile == "P2" else 4,
        )
        self.tracker = BeltTracker(cfg.track, cal.px_per_mm, fps=fps)

    # ------------------------------------------------------------------
    def process(self, frame: np.ndarray) -> FrameResult:
        t = {}
        t0 = time.perf_counter()
        board = self.cal.undistort_board(frame)
        t["entzerren"] = (time.perf_counter() - t0) * 1000

        if self.cfg.profile == "P2":
            res = self._run_p2(board, t)
        else:
            res = self._run_p1(board, t)

        t0 = time.perf_counter()
        res.detections = self.tracker.update(res.detections)
        t["tracking"] = (time.perf_counter() - t0) * 1000
        t["gesamt"] = sum(t.values())
        res.timings_ms = {k: round(v, 2) for k, v in t.items()}
        return res

    # ------------------------------------------------------------------
    def _run_p1(self, board: np.ndarray, t: dict) -> FrameResult:
        t0 = time.perf_counter()
        part_masks, mask, diag = segmentation.segment_parts(
            board, self.cal.px_per_mm, self.cfg.seg, self.background_ref
        )
        t["segmentierung"] = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        dets = fitting.detections_from_masks(
            part_masks, mask, self.cal.px_per_mm, self.cfg.seg
        )
        t["rechteck_fit"] = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        batch = crops.batch_from_detections(board, dets)
        outputs = self.pool.infer_batch(batch) if len(batch) else []
        t["akida"] = (time.perf_counter() - t0) * 1000

        for det, out in zip(dets, outputs):
            if out is None:
                det.meta["akida"] = "kein Ergebnis"
                continue
            probs = softmax(np.asarray(out).ravel())
            det.class_id = int(np.argmax(probs))
            det.class_score = float(probs[det.class_id])
            det.source = "merged"

        return FrameResult(
            detections=dets, board=board, mask=mask,
            part_masks=part_masks, diagnostics=diag,
        )

    # ------------------------------------------------------------------
    def _run_p2(self, board: np.ndarray, t: dict) -> FrameResult:
        mc = self.cfg.model
        w, h = mc.input_size
        t0 = time.perf_counter()
        small = cv2.resize(board, (w, h), interpolation=cv2.INTER_AREA)
        out = self.pool.infer_batch(small[None, ...].astype(np.uint8))
        t["akida"] = (time.perf_counter() - t0) * 1000

        if not out or out[0] is None:
            return FrameResult(detections=[], board=board)

        raw = np.asarray(out[0])
        if raw.ndim != 3:
            side = int(round(np.sqrt(raw.size / mc.head_channels)))
            raw = raw.reshape(side, side, mc.head_channels)

        t0 = time.perf_counter()
        dets, flagged = postprocess.decode_head(
            raw, self.cal.out_size, model_cfg=mc, thresholds=self.cfg.head
        )
        dets = postprocess.soft_nms(dets, self.cfg.nms)
        if self.geometry_gate:
            dets = postprocess.geometry_gate(dets, self.cal.px_per_mm)
        notes = postprocess.overflow_notes(flagged, dets, self.cfg.head)
        t["nachbearbeitung"] = (time.perf_counter() - t0) * 1000

        return FrameResult(detections=dets, board=board, diagnostics=notes)

    # ------------------------------------------------------------------
    def render(self, res: FrameResult) -> np.ndarray:
        return overlay.draw(res.board, res.detections, self.cal.px_per_mm)

    def close(self) -> None:
        self.pool.close()


# ----------------------------------------------------------------------
def run_camera(
    cal: Calibration,
    cfg: RuntimeConfig = config.DEFAULT,
    background_ref: Optional[np.ndarray] = None,
    window: str = "VORSA-M3",
) -> None:  # pragma: no cover - braucht Kamera
    cap = cv2.VideoCapture(cfg.camera_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.capture_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.capture_height)
    if not cap.isOpened():
        raise RuntimeError(f"Kamera {cfg.camera_index} laesst sich nicht oeffnen.")

    pipe = Pipeline(cal, cfg, background_ref=background_ref)
    print(f"[VORSA] Profil {cfg.profile}, {pipe.pool.num_workers} Worker "
          f"({'Hardware' if pipe.pool.on_hardware else 'Stub'})")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            res = pipe.process(frame)
            cv2.imshow(window, pipe.render(res))
            if cfg.draw_debug and res.mask is not None:
                cv2.imshow(window + " Masken",
                           overlay.draw_mask_debug(res.mask, res.part_masks))
            if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        pipe.close()
