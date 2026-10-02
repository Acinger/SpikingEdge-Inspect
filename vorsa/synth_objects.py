"""Synthetische Trainingsbilder mit bekannten Objekten und Überlagerungen.

Zweck: die Trainingskette pruefen, bevor echte Daten annotiert werden. Wenn
Keras-Modell, Verlustfunktion, Quantisierung und Umwandlung nach .fbz auf
kuenstlichen Bildern nicht funktionieren, funktionieren sie auf echten erst
recht nicht - und dann waere jede Annotationsarbeit vorher verschwendet.

Ausdruecklich KEIN Ersatz fuer echte Aufnahmen: die Abschlussmessung muss mit
echten, bisher ungesehenen Kamerabildern erfolgen (SPEC.md Abschnitt 10).

Die Szenen decken bewusst die schwierigen Faelle ab:
  * mehrere unabhaengige Ueberlagerungsstellen im selben Bild
  * zwei und drei Objekte mit fast gleichem Mittelpunkt
  * gleiche Klasse nebeneinander (Worst Case fuer NMS)
  * runde Objekte, bei denen der Winkel bedeutungslos ist
  * mehr als M Objekte an einer Stelle (Ueberfuellung)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import cv2
import numpy as np

from .assignment import GtObject

# Formfamilien. "rund" schaltet die Winkelbewertung ab.
SHAPES = ("rechteck", "langgestreckt", "quadrat", "rund", "unregelmaessig")


@dataclass
class Scene:
    image: np.ndarray            # (H, W, 3) uint8
    objects: List[GtObject]

    @property
    def count(self) -> int:
        return len(self.objects)


def _background(size: int, rng: np.random.Generator) -> np.ndarray:
    """Kontrollierter, aber nicht identischer Hintergrund (SPEC.md 4.4)."""
    grund = int(rng.integers(45, 75))
    img = np.full((size, size, 3), grund, dtype=np.int16)
    img += rng.normal(0, 6, (size, size, 1)).astype(np.int16)

    # Leichter Helligkeitsverlauf - simuliert seitliche Beleuchtung.
    gy, gx = np.mgrid[0:size, 0:size]
    richtung = rng.uniform(0, 2 * math.pi)
    verlauf = (np.cos(richtung) * gx + np.sin(richtung) * gy) / size
    img += (verlauf * rng.uniform(-18, 18)).astype(np.int16)[..., None]

    # Ein paar Stoerkanten: Kratzer, Nahtstellen, Verschmutzung.
    img = np.clip(img, 0, 255).astype(np.uint8)
    for _ in range(int(rng.integers(0, 4))):
        p1 = rng.integers(0, size, 2)
        p2 = p1 + rng.integers(-size // 3, size // 3, 2)
        ton = int(rng.integers(30, 95))
        cv2.line(img, tuple(p1), tuple(np.clip(p2, 0, size - 1)), (ton, ton, ton), 1)
    return cv2.GaussianBlur(img, (3, 3), 0)


def _draw(img: np.ndarray, obj: GtObject, shape: str,
          rng: np.random.Generator) -> None:
    ton = int(rng.integers(120, 215))
    farbe = (ton - int(rng.integers(0, 25)), ton - int(rng.integers(0, 15)), ton)
    rect = ((obj.cx, obj.cy), (obj.width, obj.height), obj.angle)
    pts = cv2.boxPoints(rect).astype(np.int32)

    # Schatten zuerst, versetzt - gibt dem Modell einen Tiefenhinweis.
    cv2.fillConvexPoly(img, pts + np.array([3, 4]), (28, 26, 25), lineType=cv2.LINE_AA)

    if shape == "rund":
        cv2.ellipse(img, ((obj.cx, obj.cy), (obj.width, obj.height), obj.angle),
                    farbe, -1, cv2.LINE_AA)
    elif shape == "unregelmaessig":
        # Ecken zufaellig einbeulen, damit nicht alles perfekt konvex ist.
        stoer = rng.normal(0, min(obj.width, obj.height) * 0.12, pts.shape)
        cv2.fillPoly(img, [(pts + stoer).astype(np.int32)], farbe, cv2.LINE_AA)
    else:
        cv2.fillConvexPoly(img, pts, farbe, lineType=cv2.LINE_AA)

    # Helle Aussenkante - ohne sie verschwimmen ueberlappende Objekte gleicher
    # Farbe zu einer Flaeche, und genau die muss das Modell trennen lernen.
    cv2.polylines(img, [pts], True,
                  tuple(min(255, c + 40) for c in farbe), 1, cv2.LINE_AA)


def _size_for(shape: str, size: int, rng: np.random.Generator) -> Tuple[float, float]:
    """Groesse in Pixeln. Klein, mittel, gross - alle drei kommen vor."""
    stufe = rng.choice(["klein", "mittel", "gross"], p=[0.4, 0.4, 0.2])
    grund = {"klein": size * 0.06, "mittel": size * 0.13, "gross": size * 0.24}[stufe]
    grund *= rng.uniform(0.8, 1.25)

    if shape == "langgestreckt":
        return grund * rng.uniform(2.5, 4.5), grund * 0.7
    if shape in ("quadrat", "rund"):
        s = grund
        return s, s * rng.uniform(0.92, 1.08)
    if shape == "rechteck":
        return grund * rng.uniform(1.3, 2.2), grund
    return grund * rng.uniform(1.0, 1.8), grund


def make_scene(
    size: int = 256,
    num_classes: int = 8,
    max_objects: int = 14,
    cell_px: float = 8.0,
    p_koinzident: float = 0.5,
    seed: Optional[int] = None,
    rng: Optional[np.random.Generator] = None,
) -> Scene:
    """Ein Bild mit mehreren Objekten und mehreren Ueberlagerungsstellen.

    `cell_px` ist die Rasterzellgroesse des Modells, `p_koinzident` der Anteil
    der Ueberlagerungsstellen, deren Objekte absichtlich fast denselben
    Mittelpunkt bekommen.

    Warum das noetig ist: M3 greift nur, wenn mehrere Objektmittelpunkte in
    DASSELBE Rasterfeld fallen. Bei 8 px Zellen liegen zwei ueberlappende
    Objekte mit 15 px Mittelpunktabstand bereits in verschiedenen Feldern -
    dann bekommen Slot 2 und 3 nie ein Objekt zugewiesen und bleiben
    untrainiert. Ohne diesen Anteil im Datensatz waere die lokale
    Mehrfachbelegung totes Gewicht im Modell.
    """
    rng = rng or np.random.default_rng(seed)
    img = _background(size, rng)

    objekte: List[GtObject] = []
    formen: List[str] = []

    # Mehrere unabhaengige Stellen, jede mit 1 bis 4 Objekten. Vier bedeutet
    # Ueberfuellung bei M=3 - das Modell soll lernen, das zu melden.
    n_stellen = int(rng.integers(2, 6))
    for _ in range(n_stellen):
        if len(objekte) >= max_objects:
            break
        n_hier = int(rng.choice([1, 2, 3, 4], p=[0.35, 0.30, 0.24, 0.11]))
        mitte = rng.uniform(size * 0.15, size * 0.85, 2)

        # Gleiche Klasse an einer Stelle ist der schwierigste Fall fuer NMS -
        # deshalb absichtlich haeufig.
        gleiche_klasse = rng.random() < 0.45

        # Koinzidente Stelle: alle Mittelpunkte innerhalb einer Rasterzelle.
        koinzident = n_hier >= 2 and rng.random() < p_koinzident
        klasse_hier = int(rng.integers(0, num_classes))

        for _ in range(n_hier):
            if len(objekte) >= max_objects:
                break
            shape = str(rng.choice(SHAPES))
            w, h = _size_for(shape, size, rng)

            if koinzident:
                # Innerhalb einer Zelle streuen -> gemeinsames Rasterfeld.
                streu = cell_px * 0.35
            else:
                # Ueberlagert, aber mit deutlich getrennten Mittelpunkten.
                streu = min(w, h) * rng.uniform(0.15, 0.75)
            cx = float(np.clip(mitte[0] + rng.normal(0, streu), 4, size - 4))
            cy = float(np.clip(mitte[1] + rng.normal(0, streu), 4, size - 4))

            objekte.append(GtObject(
                cx=cx, cy=cy, width=float(w), height=float(h),
                angle=float(rng.uniform(0, 180)),
                class_id=klasse_hier if gleiche_klasse else int(rng.integers(0, num_classes)),
                visibility=1.0,
                rotation_matters=(shape != "rund"),
            ))
            formen.append(shape)

    # Zeichnen in zufaelliger Reihenfolge; spaeter Gezeichnetes verdeckt.
    reihenfolge = list(rng.permutation(len(objekte)))
    for i in reihenfolge:
        _draw(img, objekte[i], formen[i], rng)

    _update_visibility(objekte, formen, reihenfolge, img.shape[:2])

    img = cv2.GaussianBlur(img, (3, 3), 0)
    return Scene(image=img, objects=objekte)


def _update_visibility(objekte: List[GtObject], formen: List[str],
                       reihenfolge: Sequence[int], shape_hw) -> None:
    """Berechnet den sichtbaren Anteil jedes Objekts.

    Wichtig fuer den `vis`-Kanal: das Modell soll den Verdeckungsgrad lernen,
    nicht raten. Der Wert ergibt sich aus der Zeichenreihenfolge - was spaeter
    gezeichnet wurde, liegt oben.
    """
    h, w = shape_hw
    masken = []
    for obj in objekte:
        m = np.zeros((h, w), dtype=np.uint8)
        pts = cv2.boxPoints(((obj.cx, obj.cy), (obj.width, obj.height),
                             obj.angle)).astype(np.int32)
        cv2.fillConvexPoly(m, pts, 255)
        masken.append(m)

    # Position in der Zeichenreihenfolge: hoeher = weiter oben.
    rang = {idx: pos for pos, idx in enumerate(reihenfolge)}

    for i, obj in enumerate(objekte):
        eigen = cv2.countNonZero(masken[i])
        if eigen == 0:
            obj.visibility = 0.0
            continue
        verdeckt = np.zeros((h, w), dtype=np.uint8)
        for j in range(len(objekte)):
            if j != i and rang[j] > rang[i]:
                verdeckt = cv2.bitwise_or(verdeckt, masken[j])
        ueberdeckt = cv2.countNonZero(cv2.bitwise_and(masken[i], verdeckt))
        obj.visibility = float(max(0.0, 1.0 - ueberdeckt / eigen))


def make_batch(n: int, size: int = 256, num_classes: int = 8,
               cell_px: float = 8.0, p_koinzident: float = 0.5,
               seed: int = 0) -> Tuple[np.ndarray, List[List[GtObject]]]:
    """(N, size, size, 3) uint8 plus Objektlisten je Bild."""
    rng = np.random.default_rng(seed)
    bilder, listen = [], []
    for _ in range(n):
        s = make_scene(size=size, num_classes=num_classes, cell_px=cell_px,
                       p_koinzident=p_koinzident, rng=rng)
        bilder.append(s.image)
        listen.append(s.objects)
    return np.stack(bilder).astype(np.uint8), listen


def statistik(listen: List[List[GtObject]], grid: int = 32,
              image_px: float = 256.0) -> dict:
    """Deckt der erzeugte Datensatz die Pflichtfaelle ab (SPEC.md 10)?

    Die drei Zeilen zur Feldbelegung sind die wichtigsten: sie sagen, wie oft
    die lokale Mehrfachbelegung im Training ueberhaupt geuebt wird. Stehen
    dort Nullen, lernt das Modell M3 nie - egal wie gut alles andere aussieht.
    """
    from .assignment import assign_to_cells

    n_obj = [len(l) for l in listen]
    vis = [o.visibility for l in listen for o in l]
    rund = sum(1 for l in listen for o in l if not o.rotation_matters)
    gesamt = max(sum(n_obj), 1)

    felder_mit = {1: 0, 2: 0, 3: 0, 4: 0}
    for liste in listen:
        for objs in assign_to_cells(liste, grid, (image_px, image_px)).values():
            felder_mit[min(len(objs), 4)] += 1

    return {
        "bilder": len(listen),
        "objekte": sum(n_obj),
        "objekte_je_bild": round(float(np.mean(n_obj)), 2) if n_obj else 0,
        "anteil_frei": round(float(np.mean([v >= 0.9 for v in vis])), 3) if vis else 0,
        "anteil_teilverdeckt": round(
            float(np.mean([0.3 <= v < 0.9 for v in vis])), 3) if vis else 0,
        "anteil_stark_verdeckt": round(
            float(np.mean([v < 0.3 for v in vis])), 3) if vis else 0,
        "anteil_rund": round(rund / gesamt, 3),
        "felder_1_objekt": felder_mit[1],
        "felder_2_objekte": felder_mit[2],
        "felder_3_objekte": felder_mit[3],
        "felder_ueberfuellt": felder_mit[4],
    }
