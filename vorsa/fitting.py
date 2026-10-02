"""Anpassung des bekannten 80 x 22 mm Rechtecks (Fall 1 und Fall 2).

Der Trick des ganzen Projekts: die Sollgeometrie ist bekannt. Statt eine
beliebige Form zu segmentieren, wird ein Rechteck fester Groesse an die
*sichtbaren* Kanten angelegt. Das funktioniert auch dann noch, wenn eine Ecke
verdeckt ist.
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

import cv2
import numpy as np

from . import config
from .detection import Detection, Occlusion, OrientedBox


# ----------------------------------------------------------------------
def dominant_angle(contour: np.ndarray) -> float:
    """Richtung der langen Achse in Grad (0..180).

    Bevorzugt die laengste gerade Kante des Polygonzugs. Eine reine
    Hauptachsenanalyse waere bei stark verdeckten Teilen ungenau, weil die
    fehlende Flaeche den Schwerpunkt verschiebt; eine sichtbare lange Kante
    dagegen ist auch dann noch korrekt ausgerichtet.
    """
    peri = cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, 0.01 * peri, True).reshape(-1, 2).astype(float)

    best_len, best_ang = 0.0, None
    for i in range(len(approx)):
        p, q = approx[i], approx[(i + 1) % len(approx)]
        d = q - p
        seg = float(np.hypot(*d))
        if seg > best_len:
            best_len, best_ang = seg, math.degrees(math.atan2(d[1], d[0]))

    if best_ang is None:
        return OrientedBox.from_cv_rect(cv2.minAreaRect(contour)).angle
    return best_ang % 180.0


def _axes(angle_deg: float) -> Tuple[np.ndarray, np.ndarray]:
    a = math.radians(angle_deg)
    u = np.array([math.cos(a), math.sin(a)])       # lange Achse
    v = np.array([-math.sin(a), math.cos(a)])      # kurze Achse
    return u, v


def _rect_mask(box: OrientedBox, shape: Tuple[int, int]) -> np.ndarray:
    m = np.zeros(shape, dtype=np.uint8)
    cv2.fillConvexPoly(m, box.corners().astype(np.int32), 255)
    return m


def _part_area_px(px_per_mm: float) -> float:
    return config.PART_AREA_MM2 * px_per_mm * px_per_mm


def longest_edge(contour: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float]:
    """Laengste gerade Kante des Polygonzugs als (Startpunkt, Endpunkt, Laenge)."""
    peri = cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, 0.012 * peri, True).reshape(-1, 2).astype(float)
    if len(approx) < 2:
        rect = cv2.minAreaRect(contour)
        pts = cv2.boxPoints(rect)
        return pts[0], pts[1], float(np.linalg.norm(pts[1] - pts[0]))

    best = (approx[0], approx[1], 0.0)
    for i in range(len(approx)):
        p, q = approx[i], approx[(i + 1) % len(approx)]
        seg = float(np.linalg.norm(q - p))
        if seg > best[2]:
            best = (p, q, seg)
    return best


# ----------------------------------------------------------------------
def fit_nominal_rect(
    contour: np.ndarray,
    px_per_mm: float,
    foreground: Optional[np.ndarray] = None,
    angle_deg: Optional[float] = None,
) -> Tuple[OrientedBox, Occlusion, dict]:
    """Legt ein Rechteck mit Sollmassen an die sichtbaren Kanten einer Kontur.

    Rueckgabe: (Box, Verdeckungsgrad, Diagnose).

    Vorgehen bei Teilverdeckung:
      1. Winkel aus der laengsten sichtbaren Kante.
      2. Kontur auf lange/kurze Achse projizieren -> sichtbare Ausdehnung.
      3. Fehlt Laenge, gibt es zwei moegliche Lagen (nach vorn oder nach
         hinten verlaengert). Es gewinnt die Lage, deren ergaenzte Flaeche
         staerker mit dem uebrigen Vordergrund ueberlappt - denn genau dort
         liegt das verdeckende Teil.
    """
    L_nom = config.PART_LENGTH_MM * px_per_mm
    W_nom = config.PART_WIDTH_MM * px_per_mm

    ang = dominant_angle(contour) if angle_deg is None else angle_deg % 180.0
    u, v = _axes(ang)

    pts = contour.reshape(-1, 2).astype(float)
    pu, pv = pts @ u, pts @ v
    ext_u = float(pu.max() - pu.min())
    ext_v = float(pv.max() - pv.min())

    # Falls die "lange" Achse kuerzer als die "kurze" ist, war die Kante die
    # Schmalseite -> um 90 Grad drehen.
    if ext_u < ext_v:
        ang = (ang + 90.0) % 180.0
        u, v = _axes(ang)
        pu, pv = pts @ u, pts @ v
        ext_u, ext_v = float(pu.max() - pu.min()), float(pv.max() - pv.min())

    visible_area = float(cv2.contourArea(contour))
    coverage = visible_area / max(L_nom * W_nom, 1e-6)

    diag = {
        "angle_deg": round(ang, 2),
        "ext_len_mm": round(ext_u / px_per_mm, 2),
        "ext_wid_mm": round(ext_v / px_per_mm, 2),
        "coverage": round(coverage, 3),
    }

    # Mitte der kurzen Achse: bei flachen Teilen ist die Breite fast immer
    # vollstaendig sichtbar, deshalb einfach mitteln.
    cv_ = 0.5 * (pv.max() + pv.min())

    len_missing = L_nom - ext_u
    if len_missing <= 0.10 * L_nom:
        cu = 0.5 * (pu.max() + pu.min())
        occ = Occlusion.FREE if coverage >= 0.85 else Occlusion.TOUCHING
        box = OrientedBox(
            cx=float(cu * u[0] + cv_ * v[0]),
            cy=float(cu * u[1] + cv_ * v[1]),
            length=L_nom, width=W_nom, angle=ang,
        )
        diag["case"] = "vollstaendig sichtbar"
        return box, occ, diag

    # Zu wenig Laenge sichtbar -> zwei Kandidatenlagen.
    cand_u = [pu.min() + 0.5 * L_nom, pu.max() - 0.5 * L_nom]
    boxes = [
        OrientedBox(
            cx=float(c * u[0] + cv_ * v[0]),
            cy=float(c * u[1] + cv_ * v[1]),
            length=L_nom, width=W_nom, angle=ang,
        )
        for c in cand_u
    ]

    if foreground is not None:
        own = np.zeros(foreground.shape, dtype=np.uint8)
        cv2.drawContours(own, [contour.astype(np.int32)], -1, 255, -1)
        others = cv2.bitwise_and(foreground, cv2.bitwise_not(own))
        scores = []
        for b in boxes:
            rm = _rect_mask(b, foreground.shape)
            added = cv2.bitwise_and(rm, cv2.bitwise_not(own))
            hidden = cv2.countNonZero(cv2.bitwise_and(added, others))
            total = max(cv2.countNonZero(added), 1)
            scores.append(hidden / total)
        idx = int(np.argmax(scores))
        diag["anchor_scores"] = [round(s, 3) for s in scores]
        # Beide Lagen gleich plausibel -> ehrlich als unaufgeloest melden.
        if abs(scores[0] - scores[1]) < 0.08 and max(scores) < 0.35:
            diag["case"] = "Lage mehrdeutig"
            return boxes[idx], Occlusion.UNRESOLVED, diag
    else:
        idx = 0
        diag["anchor_scores"] = None

    diag["case"] = "teilverdeckt, Laenge ergaenzt"
    diag["missing_mm"] = round(len_missing / px_per_mm, 2)
    occ = Occlusion.PARTIAL if coverage >= 0.35 else Occlusion.UNRESOLVED
    return boxes[idx], occ, diag


# ----------------------------------------------------------------------
def plausible(box: OrientedBox, px_per_mm: float) -> bool:
    """Geometrie-Plausibilitaet unabhaengig vom Score (SPEC.md Abschnitt 7)."""
    l_mm = box.length / px_per_mm
    w_mm = box.width / px_per_mm
    area = l_mm * w_mm
    if not (
        (1 - config.AREA_TOLERANCE) * config.PART_AREA_MM2
        <= area
        <= (1 + config.AREA_TOLERANCE) * config.PART_AREA_MM2
    ):
        return False
    asp = l_mm / max(w_mm, 1e-6)
    lo = (1 - config.ASPECT_TOLERANCE) * config.PART_ASPECT
    hi = (1 + config.ASPECT_TOLERANCE) * config.PART_ASPECT
    return lo <= asp <= hi


def fit_from_edge(
    contour: np.ndarray,
    region: np.ndarray,
    px_per_mm: float,
    own_mask: Optional[np.ndarray] = None,
) -> Tuple[Optional[OrientedBox], float, dict]:
    """Legt ein Sollrechteck an die laengste sichtbare Kante einer Kontur.

    Robuster als minAreaRect, wenn die Kontur mehrere Teile umfasst: die
    laengste gerade Kante gehoert praktisch immer zu genau einem Teil, waehrend
    das umschliessende Rechteck alle Teile zusammen einrahmen wuerde.

    Die Kante kann Laengs- oder Schmalseite sein - was davon zutrifft, wird
    nicht aus der Kantenlaenge geraten (eine abgeschnittene Laengskante ist
    kurz), sondern durch Ausprobieren beider Annahmen entschieden.

    Bewertet werden zwei Groessen:
      * Abdeckung  - liegt das Rechteck im Vordergrund?
      * Erklaerung - deckt es das gerade betrachtete Bruchstueck ab?

    Nur die Abdeckung allein wuerde in der Zerlegung dazu fuehren, dass ein
    bereits gefundenes Teil ein zweites Mal gefunden wird.
    """
    L = config.PART_LENGTH_MM * px_per_mm
    W = config.PART_WIDTH_MM * px_per_mm

    p, q, e = longest_edge(contour)
    if e < 1e-6:
        return None, 0.0, {"case": "keine Kante"}

    u0 = (q - p) / e
    v0 = np.array([-u0[1], u0[0]])
    ang0 = math.degrees(math.atan2(u0[1], u0[0])) % 180.0

    if own_mask is None:
        own_mask = np.zeros(region.shape, dtype=np.uint8)
        cv2.drawContours(own_mask, [contour.astype(np.int32)], -1, 255, -1)
    own_area = max(cv2.countNonZero(own_mask), 1)

    candidates = []
    # Annahme A: die Kante ist die Laengsseite.
    lo, hi = sorted((float(p @ u0), float(q @ u0)))
    base = float(p @ v0)
    for cu in (lo + 0.5 * L, hi - 0.5 * L, 0.5 * (lo + hi)):
        for cvv in (base + 0.5 * W, base - 0.5 * W):
            candidates.append((cu, cvv, u0, v0, ang0, "laengsseite"))
    # Annahme B: die Kante ist die Schmalseite -> lange Achse quer dazu.
    u1, v1 = v0, u0
    ang1 = (ang0 + 90.0) % 180.0
    mid_short = 0.5 * (float(p @ v1) + float(q @ v1))
    base1 = float(p @ u1)
    for cu in (base1 + 0.5 * L, base1 - 0.5 * L):
        candidates.append((cu, mid_short, u1, v1, ang1, "schmalseite"))

    best_box, best_score, best_kind = None, -1.0, ""
    for cu, cvv, u, v, ang, kind in candidates:
        box = OrientedBox(
            cx=float(cu * u[0] + cvv * v[0]),
            cy=float(cu * u[1] + cvv * v[1]),
            length=L, width=W, angle=ang,
        )
        rm = _rect_mask(box, region.shape)
        rect_area = max(cv2.countNonZero(rm), 1)
        coverage = cv2.countNonZero(cv2.bitwise_and(rm, region)) / rect_area
        explain = cv2.countNonZero(cv2.bitwise_and(rm, own_mask)) / min(own_area, rect_area)
        score = 0.5 * coverage + 0.5 * min(explain, 1.0)
        if score > best_score:
            best_box, best_score, best_kind = box, score, kind

    diag = {
        "angle_deg": round(best_box.angle, 2) if best_box else None,
        "edge_mm": round(e / px_per_mm, 2),
        "edge_rolle": best_kind,
        "fit_score": round(best_score, 3),
        "case": "kantenbasiert",
    }
    return best_box, best_score, diag


def decompose_overlap(
    blob_mask: np.ndarray,
    px_per_mm: float,
    max_parts: int = 4,
    min_fit_score: float = 0.72,
) -> List[Tuple[OrientedBox, np.ndarray, float, dict]]:
    """Zerlegt einen Blob mit ueberlappenden Teilen (Fall 2).

    Gieriges Verfahren: an die laengste sichtbare Kante ein Sollrechteck legen,
    dessen Flaeche abziehen, mit dem Rest von vorn beginnen. Das funktioniert,
    weil die Sollgroesse bekannt ist - eine allgemeine Segmentierung muesste
    hier raten.

    Rueckgabe je Teil: (Box, benutzte Kontur, sichtbare Abdeckung, Diagnose).
    """
    one = _part_area_px(px_per_mm)
    remaining = blob_mask.copy()
    found: List[Tuple[OrientedBox, np.ndarray, float, dict]] = []
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

    while len(found) < max_parts:
        cnts, _ = cv2.findContours(remaining, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            break
        c = max(cnts, key=cv2.contourArea)
        vis = float(cv2.contourArea(c))
        if vis < 0.28 * one:
            break

        own = np.zeros(blob_mask.shape, dtype=np.uint8)
        cv2.drawContours(own, [c.astype(np.int32)], -1, 255, -1)
        own = cv2.bitwise_and(own, remaining)
        box, score, diag = fit_from_edge(c, blob_mask, px_per_mm, own_mask=own)
        if box is None or score < min_fit_score:
            diag["reject"] = f"fit_score {score:.2f} < {min_fit_score}"
            break

        diag["visible_ratio"] = round(min(vis / one, 1.0), 3)
        found.append((box, c, min(vis / one, 1.0), diag))

        rm = _rect_mask(box, remaining.shape)
        rm = cv2.dilate(rm, ker, iterations=1)
        remaining = cv2.bitwise_and(remaining, cv2.bitwise_not(rm))
        remaining = cv2.morphologyEx(remaining, cv2.MORPH_OPEN, ker, iterations=2)

    return found


# ----------------------------------------------------------------------
def detections_from_masks(
    part_masks: List[np.ndarray],
    foreground: np.ndarray,
    px_per_mm: float,
    params: Optional["config.SegmentationParams"] = None,
    nominal: bool = True,
) -> List[Detection]:
    """Geometrische Detektionen aus Einzelteil-Masken.

    Enthaelt eine Maske flaechenmaessig deutlich mehr als ein Teil, obwohl
    Watershed sie nicht trennen konnte, liegt Fall 2 vor -> Rechteck-Zerlegung.

    `nominal=False` ist der NBES-Modus fuer beliebige Teile: der Rahmen ist
    das ECHTE umschliessende Rechteck der Kontur, und die Soll-Zerlegung
    entfaellt. Das Sollmass 80x22 stammt aus der Frueh-Spezifikation mit
    festem Teil - am 2026-08-28 hat es einem Karabiner ein "SD-Rechteck"
    mitten ins Loch gesetzt und eine zoomvergroesserte SD-Karte in vier
    Streifen zerlegt. Beruehrende Teile trennen in NBES Wasserscheide und
    Chip-Schiedsrichter, nicht das Rechteckmass.
    """
    p = params or config.SegmentationParams()
    one = _part_area_px(px_per_mm)
    out: List[Detection] = []

    for m in part_masks:
        cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            continue
        c = max(cnts, key=cv2.contourArea)
        # Pixelzahl statt Polygonflaeche: gleiche Groesse wie in segmentation.py,
        # sonst weichen die beiden Schwellen leicht voneinander ab.
        area = float(cv2.countNonZero(m))
        if area < 10:
            continue

        if not nominal:
            (cx, cy), (w, h), ang = cv2.minAreaRect(c)
            if w < h:
                w, h, ang = h, w, ang + 90.0
            deck = area / max(w * h, 1.0)
            out.append(Detection(
                box=OrientedBox(cx=float(cx), cy=float(cy), length=float(w),
                                width=float(h), angle=float(ang % 180.0)),
                contour=c, score=float(min(1.0, 0.4 + 0.6 * deck)),
                occlusion=Occlusion.FREE, source="geometry",
                meta={"case": "freies rechteck", "coverage": round(float(deck), 3)},
            ))
            continue

        if area >= p.decompose_trigger_parts * one:
            pieces = decompose_overlap(
                m, px_per_mm,
                max_parts=p.decompose_max_parts,
                min_fit_score=p.decompose_min_fit_score,
            )
            if len(pieces) >= 2:
                for box, cnt, vis_ratio, diag in pieces:
                    occ = Occlusion.FREE if vis_ratio >= 0.92 else Occlusion.PARTIAL
                    diag["case"] = "ueberlappung zerlegt"
                    out.append(
                        Detection(
                            box=box, contour=cnt,
                            score=float(min(1.0, 0.55 + 0.45 * vis_ratio)),
                            occlusion=occ, source="geometry", meta=diag,
                        )
                    )
                continue

        box, occ, diag = fit_nominal_rect(c, px_per_mm, foreground)
        out.append(
            Detection(
                box=box,
                contour=c,
                score=float(min(1.0, diag.get("coverage", 0.0) + 0.15)),
                occlusion=occ,
                source="geometry",
                meta=diag,
            )
        )
    return out
