"""Dekodierung des M3-Kopfes und slot-bewusste Nachverarbeitung.

Kanalaufbau je Rasterfeld (SPEC.md Abschnitt 5):

    M x [obj, tx, ty, tw, th, sin2t, cos2t, vis, Klasse_0..Klasse_C-1]
    + [local_count, overlap_prob, local_overflow_prob]

Ankerfrei: die Groesse wird direkt regressiert, nicht relativ zu vorgegebenen
Ankerboxen. Der Mittelpunkt darf ueber die Feldgrenze hinausreichen, damit drei
fast deckungsgleiche Objekte nicht kuenstlich auf verschiedene Felder verteilt
werden muessen.
"""
from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

import numpy as np

from . import config
from .config import HeadThresholds, ModelConfig, NMSParams
from .detection import Detection, Occlusion, OrientedBox, rotated_iou, sort_by_score


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(np.asarray(x, dtype=np.float32), -30, 30)))


def _softmax(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32).ravel()
    x = x - x.max()
    e = np.exp(x)
    return e / max(e.sum(), 1e-9)


# ----------------------------------------------------------------------
class CellReport:
    """Feldweite Aussagen eines Rasterfeldes."""

    __slots__ = ("gx", "gy", "local_count", "overlap_prob", "overflow_prob")

    def __init__(self, gx: int, gy: int, local_count: float,
                 overlap_prob: float, overflow_prob: float):
        self.gx, self.gy = gx, gy
        self.local_count = local_count
        self.overlap_prob = overlap_prob
        self.overflow_prob = overflow_prob

    def as_record(self) -> dict:
        return {
            "cell": (self.gx, self.gy),
            "local_count": round(self.local_count, 2),
            "overlap_prob": round(self.overlap_prob, 3),
            "overflow_prob": round(self.overflow_prob, 3),
        }

    def __repr__(self) -> str:
        return (f"CellReport({self.gx},{self.gy} n={self.local_count:.1f} "
                f"overlap={self.overlap_prob:.2f} overflow={self.overflow_prob:.2f})")


def decode_head(
    raw: np.ndarray,
    image_size_px: Sequence[int],
    model_cfg: ModelConfig = config.MODEL,
    thresholds: HeadThresholds = config.HEAD,
) -> Tuple[List[Detection], List[CellReport]]:
    """raw: (S, S, M*(8+C)+3) -> (Detektionen, ueberfuellte Felder).

    `image_size_px` = (Breite, Hoehe) des Bildes, auf das zurueckgerechnet wird.
    Die zweite Rueckgabe enthaelt nur Felder, deren Ueberfuellungs- oder
    Ueberlagerungswahrscheinlichkeit ueber der Schwelle liegt - also genau die
    Stellen, an denen der Pi nachfassen sollte.
    """
    raw = np.asarray(raw, dtype=np.float32)
    if raw.ndim != 3:
        raise ValueError(f"Kopfausgabe muss (S, S, K) sein, ist {raw.shape}")

    S = raw.shape[0]
    M, C = model_cfg.slots, model_cfg.num_classes
    per_slot = model_cfg.per_slot
    expected = M * per_slot + model_cfg.CELL_EXTRAS
    if raw.shape[-1] != expected:
        raise ValueError(
            f"Kopf hat {raw.shape[-1]} Kanaele, erwartet {expected} "
            f"(M={M}, C={C}). Passt die ModelConfig zum geladenen Modell?"
        )

    w_img, h_img = float(image_size_px[0]), float(image_size_px[1])
    cell_w, cell_h = w_img / S, h_img / S

    dets: List[Detection] = []
    flagged: List[CellReport] = []

    for gy in range(S):
        for gx in range(S):
            cell = raw[gy, gx]
            extras = cell[M * per_slot:]
            report = CellReport(
                gx, gy,
                local_count=float(max(0.0, extras[0])),
                overlap_prob=float(_sigmoid(extras[1])),
                overflow_prob=float(_sigmoid(extras[2])),
            )
            if (report.overflow_prob >= thresholds.overflow_thresh
                    or report.overlap_prob >= thresholds.overlap_thresh):
                flagged.append(report)

            for k in range(M):
                t = cell[k * per_slot:(k + 1) * per_slot]
                obj = float(_sigmoid(t[0]))
                if obj < thresholds.obj_thresh:
                    continue

                # Mittelpunkt darf ueber das Feld hinausreichen: -0.5 .. +1.5
                cx = (gx + 2.0 * float(_sigmoid(t[1])) - 0.5) * cell_w
                cy = (gy + 2.0 * float(_sigmoid(t[2])) - 0.5) * cell_h

                # Groesse ankerfrei als Bruchteil des Bildes
                w = float(_sigmoid(t[3])) * w_img
                h = float(_sigmoid(t[4])) * h_img
                length, width = (w, h) if w >= h else (h, w)

                sin2, cos2 = float(t[5]), float(t[6])
                norm = math.hypot(sin2, cos2)
                angle = 0.0 if norm < 1e-6 else (
                    0.5 * math.degrees(math.atan2(sin2 / norm, cos2 / norm)) % 180.0
                )
                if w < h:
                    angle = (angle + 90.0) % 180.0

                vis = float(np.clip(_sigmoid(t[7]), 0.0, 1.0))
                if vis >= thresholds.vis_partial:
                    occ = Occlusion.FREE
                elif vis >= thresholds.vis_unresolved:
                    occ = Occlusion.PARTIAL
                else:
                    occ = Occlusion.UNRESOLVED

                probs = _softmax(t[8:8 + C])
                cid = int(np.argmax(probs))

                dets.append(
                    Detection(
                        box=OrientedBox(cx, cy, length, width, angle),
                        score=obj,
                        class_id=cid,
                        class_score=float(probs[cid]),
                        occlusion=occ,
                        source="akida",
                        meta={
                            "cell": (gx, gy),
                            "slot": k,
                            "visibility": round(vis, 3),
                            "overlap_prob": round(report.overlap_prob, 3),
                            "overflow_prob": round(report.overflow_prob, 3),
                        },
                    )
                )

    return dets, flagged


# ----------------------------------------------------------------------
def soft_nms(dets: List[Detection], params: NMSParams) -> List[Detection]:
    """Soft-NMS auf gedrehten Rahmen, mit Schutz gleicher Rasterfelder.

    Der entscheidende Unterschied zu Standard-NMS: zwei Treffer aus demselben
    Rasterfeld, aber verschiedenen Slots, sind konstruktionsbedingt zwei
    verschiedene Objekte. Sie werden nie gegeneinander unterdrueckt - auch dann
    nicht, wenn ihre Rahmen fast deckungsgleich sind. Genau das ist der Fall,
    fuer den M3 gebaut wurde.

    Zwischen verschiedenen Feldern wird unterdrueckt, aber weich: der Score
    sinkt, der Treffer verschwindet nicht sofort.
    """
    pool = [
        Detection(
            box=d.box, contour=d.contour, score=d.score, class_id=d.class_id,
            class_score=d.class_score, occlusion=d.occlusion, track_id=d.track_id,
            source=d.source, meta=dict(d.meta),
        )
        for d in dets
    ]
    keep: List[Detection] = []

    while pool and len(keep) < params.max_detections:
        pool = sort_by_score(pool)
        best = pool.pop(0)
        if best.score < params.score_thresh:
            break
        keep.append(best)

        best_cell = best.meta.get("cell")
        survivors: List[Detection] = []
        for d in pool:
            same_cell = (
                params.protect_same_cell
                and best_cell is not None
                and d.meta.get("cell") == best_cell
                and d.meta.get("slot") != best.meta.get("slot")
            )
            if same_cell:
                d.meta["nms"] = "geschuetzt: gleiches Feld, anderer Slot"
                survivors.append(d)
                continue

            iou = rotated_iou(best.box, d.box)
            if iou <= params.iou_thresh:
                survivors.append(d)
                continue

            if params.soft:
                d.score *= math.exp(-(iou ** 2) / max(params.soft_sigma, 1e-6))
                if d.score >= params.score_thresh:
                    d.meta["nms"] = f"soft abgewertet, iou={iou:.2f}"
                    survivors.append(d)
                else:
                    d.meta["dropped"] = f"soft-nms, iou={iou:.2f}"
            else:
                d.meta["dropped"] = f"hard-nms, iou={iou:.2f}"
        pool = survivors

    return keep


# ----------------------------------------------------------------------
def overflow_notes(flagged: List[CellReport], detections: List[Detection],
                   thresholds: HeadThresholds = config.HEAD) -> List[dict]:
    """Stellen, an denen die lokale Kapazitaet vermutlich ueberschritten ist.

    Das System gibt hier keine Objektzahl aus, sondern meldet die Unsicherheit.
    Der Pi kann daraufhin ein weiteres Bild, die zeitliche Verfolgung oder eine
    zweite Kamera anfordern (Projektbeschreibung 4.8).
    """
    notes = []
    for rep in flagged:
        if rep.overflow_prob < thresholds.overflow_thresh:
            continue
        n_here = sum(1 for d in detections if d.meta.get("cell") == (rep.gx, rep.gy))
        notes.append({
            **rep.as_record(),
            "ausgegeben": n_here,
            "hinweis": "lokale Kapazitaet vermutlich ueberschritten "
                       "-> zusaetzliche Information anfordern",
        })
    return notes


# ----------------------------------------------------------------------
def geometry_gate(dets: List[Detection], px_per_mm: float) -> List[Detection]:
    """Optionaler Anwendungsfilter: verwirft geometrisch unmoegliche Rahmen.

    Nur fuer Anwendungen mit bekannter Sollgeometrie (Beispiel Foerderband).
    Fuer allgemeine Klassen ist dieser Filter ausdruecklich NICHT zu verwenden.
    """
    from .fitting import plausible

    out = []
    for d in dets:
        if plausible(d.box, px_per_mm):
            out.append(d)
        else:
            d.meta["dropped"] = "geometrie unplausibel (Anwendungsfilter)"
    return out


def merge_geometry_and_model(
    geo: List[Detection],
    model_dets: List[Detection],
    iou_thresh: float = 0.4,
) -> List[Detection]:
    """Fuehrt Geometrie- und Modellergebnisse zusammen (Profil P1).

    Die Geometrie liefert die genauere Lage, das Modell die Klasse. Modelltreffer
    ohne geometrisches Gegenstueck bleiben erhalten, aber markiert - das ist der
    interessante Fall: ein verdecktes Objekt, dessen Kontur nicht sichtbar war.
    """
    used = set()
    merged: List[Detection] = []

    for g in geo:
        best_i, best_iou = -1, 0.0
        for i, m in enumerate(model_dets):
            if i in used:
                continue
            iou = rotated_iou(g.box, m.box)
            if iou > best_iou:
                best_i, best_iou = i, iou
        if best_i >= 0 and best_iou >= iou_thresh:
            m = model_dets[best_i]
            used.add(best_i)
            g.class_id = m.class_id
            g.class_score = m.class_score
            g.score = max(g.score, m.score)
            g.source = "merged"
            g.meta["match_iou"] = round(best_iou, 3)
        merged.append(g)

    for i, m in enumerate(model_dets):
        if i not in used:
            m.meta["note"] = "nur Modell, keine sichtbare Kontur -> Verdacht Verdeckung"
            if m.occlusion == Occlusion.FREE:
                m.occlusion = Occlusion.PARTIAL
            merged.append(m)

    return merged
