"""Reihenfolgeunabhaengige Zuordnung zwischen Slots und echten Objekten.

Kern der M3-Trainingsstrategie (Projektbeschreibung Abschnitt 9, SPEC.md 6):
Slot 1 bedeutet nicht "immer die Schraube". Fuer jedes Rasterfeld wird die
beste Zuordnung zwischen den M Vorhersagen und den vorhandenen echten Objekten
gesucht.

Bei M <= 4 wird ueber **alle Permutationen** exakt optimiert. M! ist hoechstens
24 - das ist billiger als eine Ungarische Methode, exakt statt naeherungsweise
und braucht keine Fremdbibliothek. Ab M >= 5 waere
scipy.optimize.linear_sum_assignment noetig.

Dieses Modul laeuft ausschliesslich beim Training auf einem normalen Rechner.
Auf dem AKD1500 entsteht dadurch keinerlei Zusatzlast.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import permutations
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import config


# ----------------------------------------------------------------------
@dataclass
class GtObject:
    """Ein annotiertes Objekt in Bildkoordinaten (Pixel)."""

    cx: float
    cy: float
    width: float
    height: float
    angle: float                # Grad, 0..180
    class_id: int
    visibility: float = 1.0     # 1.0 = frei sichtbar, 0.0 = ganz verdeckt
    rotation_matters: bool = True   # False bei runden Objekten
    obj_id: int = -1


@dataclass
class CostWeights:
    """Gewichte der Zuordnungskosten. Startwerte, keine Zielwerte."""

    pos: float = 1.0
    size: float = 0.5
    angle: float = 0.3
    cls: float = 0.5


# ----------------------------------------------------------------------
def pair_cost(
    pred: Dict[str, float],
    gt: GtObject,
    cell_px: float,
    w: CostWeights = CostWeights(),
) -> float:
    """Kosten der Zuordnung einer Vorhersage zu einem echten Objekt.

    Alle Anteile sind auf etwa 0..1 normiert, damit die Gewichte vergleichbar
    bleiben. Die Lage wird auf die Feldgroesse bezogen, nicht auf Pixel - sonst
    haengt das Gewicht von der Eingabeaufloesung ab.
    """
    dpos = math.hypot(pred["cx"] - gt.cx, pred["cy"] - gt.cy) / max(cell_px, 1e-6)

    dsize = (
        abs(math.log(max(pred["width"], 1e-3) / max(gt.width, 1e-3)))
        + abs(math.log(max(pred["height"], 1e-3) / max(gt.height, 1e-3)))
    ) / 2.0

    if gt.rotation_matters:
        dang = 1.0 - math.cos(2.0 * math.radians(pred["angle"] - gt.angle))
        dang *= 0.5      # auf 0..1
    else:
        dang = 0.0       # runde Objekte: Winkel ist bedeutungslos

    p_cls = float(pred.get("class_probs", [0.0])[gt.class_id]) \
        if "class_probs" in pred and gt.class_id < len(pred["class_probs"]) else 0.0
    dcls = 1.0 - p_cls

    return w.pos * dpos + w.size * dsize + w.angle * dang + w.cls * dcls


def best_assignment(
    preds: Sequence[Dict[str, float]],
    gts: Sequence[GtObject],
    cell_px: float,
    weights: CostWeights = CostWeights(),
) -> Tuple[List[Optional[int]], float]:
    """Beste Zuordnung Slot -> echtes Objekt.

    Rueckgabe: (Liste je Slot mit GT-Index oder None, Gesamtkosten).

    Es werden alle Zuordnungen von min(M, N) Objekten auf die M Slots geprueft.
    Ueberzaehlige Objekte bleiben unzugeordnet - das ist genau der Fall, den
    local_overflow_prob spaeter meldet.
    """
    M, N = len(preds), len(gts)
    if M == 0:
        return [], 0.0
    if N == 0:
        return [None] * M, 0.0
    if M > 4:
        raise ValueError(
            f"M={M}: die exakte Permutationssuche ist bis M=4 vorgesehen. "
            "Fuer groessere M scipy.optimize.linear_sum_assignment verwenden."
        )

    cost = np.zeros((M, N), dtype=np.float64)
    for i, p in enumerate(preds):
        for j, g in enumerate(gts):
            cost[i, j] = pair_cost(p, g, cell_px, weights)

    k = min(M, N)
    best_map: List[Optional[int]] = [None] * M
    best_total = float("inf")

    for slots in permutations(range(M), k):
        for objs in permutations(range(N), k):
            total = sum(cost[s, o] for s, o in zip(slots, objs))
            if total < best_total:
                best_total = total
                best_map = [None] * M
                for s, o in zip(slots, objs):
                    best_map[s] = o

    return best_map, float(best_total)


# ----------------------------------------------------------------------
def assign_to_cells(
    gts: Sequence[GtObject],
    grid: int,
    image_size_px: Tuple[float, float],
) -> Dict[Tuple[int, int], List[GtObject]]:
    """Verteilt echte Objekte auf Rasterfelder nach ihrem Mittelpunkt."""
    w_img, h_img = image_size_px
    cw, ch = w_img / grid, h_img / grid
    cells: Dict[Tuple[int, int], List[GtObject]] = {}
    for g in gts:
        gx = int(np.clip(g.cx // cw, 0, grid - 1))
        gy = int(np.clip(g.cy // ch, 0, grid - 1))
        cells.setdefault((gx, gy), []).append(g)
    return cells


def build_targets(
    gts: Sequence[GtObject],
    grid: int,
    image_size_px: Tuple[float, float],
    model_cfg: config.ModelConfig = config.MODEL,
) -> np.ndarray:
    """Baut das Zielgitter fuer das Training.

    Wichtig: dies ist die *Struktur* der Ziele, ohne die Zuordnung zu bereits
    vorhandenen Vorhersagen. Die reihenfolgeunabhaengige Zuordnung geschieht
    waehrend des Trainings in jedem Schritt neu (best_assignment), weil sie von
    der aktuellen Vorhersage abhaengt. Hier werden die Objekte lediglich in der
    Reihenfolge abgelegt, in der sie im Feld liegen.

    Ausgabe: (S, S, M*(8+C)+3) mit
      Slot: [obj, cx_norm, cy_norm, w_norm, h_norm, sin2t, cos2t, vis, onehot]
    Die Koordinaten stehen hier als *dekodierte* Werte, nicht als Logits -
    die Verlustfunktion vergleicht dekodierte Groessen.
    """
    M, C = model_cfg.slots, model_cfg.num_classes
    per_slot = model_cfg.per_slot
    K = model_cfg.head_channels
    w_img, h_img = image_size_px
    cw, ch = w_img / grid, h_img / grid

    target = np.zeros((grid, grid, K), dtype=np.float32)
    cells = assign_to_cells(gts, grid, image_size_px)

    for (gx, gy), objs in cells.items():
        objs = sorted(objs, key=lambda o: -o.visibility)   # sichtbarste zuerst
        for k, g in enumerate(objs[:M]):
            base = k * per_slot
            a = math.radians(g.angle)
            target[gy, gx, base + 0] = 1.0
            target[gy, gx, base + 1] = (g.cx - gx * cw) / cw
            target[gy, gx, base + 2] = (g.cy - gy * ch) / ch
            target[gy, gx, base + 3] = g.width / w_img
            target[gy, gx, base + 4] = g.height / h_img
            target[gy, gx, base + 5] = math.sin(2 * a)
            target[gy, gx, base + 6] = math.cos(2 * a)
            target[gy, gx, base + 7] = g.visibility
            if 0 <= g.class_id < C:
                target[gy, gx, base + 8 + g.class_id] = 1.0

        extras = M * per_slot
        target[gy, gx, extras + 0] = len(objs)                       # local_count
        target[gy, gx, extras + 1] = 1.0 if len(objs) >= 2 else 0.0  # overlap
        target[gy, gx, extras + 2] = 1.0 if len(objs) > M else 0.0   # overflow

    return target


# ----------------------------------------------------------------------
def decode_slots_numpy(
    raw: np.ndarray,
    grid: int,
    image_size_px: Tuple[float, float],
    model_cfg: config.ModelConfig = config.MODEL,
) -> List[List[Dict]]:
    """Dekodiert die Rohvorhersage eines Feldes in lesbare Slot-Werte.

    Nur fuer die Zuordnung gedacht, nicht fuer die Ausgabe - deshalb ohne
    Schwellwerte und ohne NMS. Die Zuordnung braucht alle Slots, auch die mit
    niedriger Objektheit: sonst bekaeme ein noch untrainierter Slot nie ein
    Objekt zugewiesen und wuerde nie lernen.
    """
    S = grid
    M, C = model_cfg.slots, model_cfg.num_classes
    per_slot = model_cfg.per_slot
    w_img, h_img = image_size_px
    cw, ch = w_img / S, h_img / S

    def sig(x):
        return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, float(x)))))

    out: List[List[Dict]] = []
    for gy in range(S):
        zeile = []
        for gx in range(S):
            cell = raw[gy, gx]
            slots = []
            for k in range(M):
                t = cell[k * per_slot:(k + 1) * per_slot]
                logits = np.asarray(t[8:8 + C], dtype=np.float64)
                e = np.exp(logits - logits.max())
                probs = e / max(e.sum(), 1e-9)
                slots.append({
                    "cx": (gx + 2.0 * sig(t[1]) - 0.5) * cw,
                    "cy": (gy + 2.0 * sig(t[2]) - 0.5) * ch,
                    "width": sig(t[3]) * w_img,
                    "height": sig(t[4]) * h_img,
                    "angle": (0.5 * math.degrees(math.atan2(float(t[5]), float(t[6])))) % 180.0,
                    "class_probs": probs,
                })
            zeile.append(slots)
        out.append(zeile)
    return out


def match_batch(
    raw_batch: np.ndarray,
    gt_batch: Sequence[Sequence[GtObject]],
    grid: int,
    image_size_px: Tuple[float, float],
    model_cfg: config.ModelConfig = config.MODEL,
    weights: CostWeights = CostWeights(),
) -> Tuple[np.ndarray, np.ndarray]:
    """Erzeugt Zielgitter und Slot-Maske passend zur aktuellen Vorhersage.

    Das ist der Kern der reihenfolgeunabhaengigen Zuordnung im Training:
    welcher Slot welches Objekt lernen soll, haengt davon ab, was das Modell
    gerade vorhersagt. Deshalb muss die Zuordnung in jedem Schritt neu
    berechnet werden, nicht einmalig vorab.

    Rueckgabe:
      y_true (B, S, S, K)  Zielwerte, dekodiert (nicht als Logits)
      mask   (B, S, S, M)  1.0 wo ein Slot ein Objekt bekommen hat

    Slots ohne Objekt haben mask=0 und lernen ausschliesslich obj -> 0.
    Ihre Koordinaten duerfen nicht bestraft werden, sonst werden alle Slots
    zur Bildmitte gezogen und die lokale Mehrfachbelegung bricht zusammen.
    """
    B = len(gt_batch)
    S, M, C = grid, model_cfg.slots, model_cfg.num_classes
    per_slot, K = model_cfg.per_slot, model_cfg.head_channels
    w_img, h_img = image_size_px
    cw, ch = w_img / S, h_img / S
    cell_px = float(min(cw, ch))

    y_true = np.zeros((B, S, S, K), dtype=np.float32)
    mask = np.zeros((B, S, S, M), dtype=np.float32)

    for b in range(B):
        preds = decode_slots_numpy(raw_batch[b], S, image_size_px, model_cfg)
        cells = assign_to_cells(gt_batch[b], S, image_size_px)

        for (gx, gy), objs in cells.items():
            slots = preds[gy][gx]
            # Bei Ueberfuellung zaehlen die sichtbarsten Objekte zuerst. Ein
            # fast vollstaendig verdecktes Objekt einem Slot zuzuweisen und
            # ein frei sichtbares wegzulassen, waere die schlechtere Wahl.
            objs_sortiert = sorted(objs, key=lambda o: -o.visibility)
            zuordnung, _ = best_assignment(
                slots, objs_sortiert[:M], cell_px, weights)

            for k, idx in enumerate(zuordnung):
                if idx is None:
                    continue
                g = objs_sortiert[idx]
                base = k * per_slot
                a = math.radians(g.angle)
                y_true[b, gy, gx, base + 0] = 1.0
                y_true[b, gy, gx, base + 1] = (g.cx - gx * cw) / cw
                y_true[b, gy, gx, base + 2] = (g.cy - gy * ch) / ch
                y_true[b, gy, gx, base + 3] = g.width / w_img
                y_true[b, gy, gx, base + 4] = g.height / h_img
                y_true[b, gy, gx, base + 5] = math.sin(2 * a)
                y_true[b, gy, gx, base + 6] = math.cos(2 * a)
                y_true[b, gy, gx, base + 7] = g.visibility
                if 0 <= g.class_id < C:
                    y_true[b, gy, gx, base + 8 + g.class_id] = 1.0
                # Runde Objekte: Winkel ist bedeutungslos. Kennzeichnung ueber
                # sin/cos = 0, die Verlustfunktion blendet den Anteil dann aus.
                if not g.rotation_matters:
                    y_true[b, gy, gx, base + 5] = 0.0
                    y_true[b, gy, gx, base + 6] = 0.0
                mask[b, gy, gx, k] = 1.0

            extras = M * per_slot
            y_true[b, gy, gx, extras + 0] = len(objs)
            y_true[b, gy, gx, extras + 1] = 1.0 if len(objs) >= 2 else 0.0
            y_true[b, gy, gx, extras + 2] = 1.0 if len(objs) > M else 0.0

    return y_true, mask


def loss_terms() -> Dict[str, str]:
    """Bausteine der Verlustfunktion (SPEC.md Abschnitt 7).

    Als Nachschlagewerk fuer die Trainingsimplementierung. Bewusst als Text und
    nicht als Keras-Code: das Training laeuft auf einem anderen Rechner mit
    anderer Umgebung, und eine hier eingefrorene Verlustfunktion wuerde dort
    stillschweigend veralten.
    """
    return {
        "obj": "binaere Kreuzentropie ueber ALLE Slots",
        "pos": "Smooth-L1, nur zugeordnete Slots",
        "size": "Smooth-L1 auf log-Groesse, nur zugeordnete Slots",
        "angle": "1 - cos(2*dTheta), nur zugeordnete Slots mit rotation_matters",
        "vis": "L1, nur zugeordnete Slots",
        "cls": "Kreuzentropie, nur zugeordnete Slots",
        "local_count": "L1 ueber alle Felder",
        "overlap_prob": "binaere Kreuzentropie ueber alle Felder",
        "overflow_prob": "binaere Kreuzentropie ueber alle Felder",
        "WICHTIG": (
            "Leere Slots lernen ausschliesslich obj -> 0. Ihre Koordinaten "
            "duerfen NICHT bestraft werden, sonst werden alle Slots zur "
            "Bildmitte gezogen und die Mehrfachbelegung bricht zusammen."
        ),
    }
