"""Spiegeln und Drehen von Bildern samt Annotation.

Der heikle Teil ist nicht das Bild, sondern die Annotation. Wer ein Bild
dreht und die Winkel nicht mitfuehrt, bringt dem Modell systematisch falsche
Winkel bei - und merkt es erst, wenn die Winkelfehler im Betrieb unerklaerlich
gross bleiben.

Zweiter Punkt, der leicht uebersehen wird: **Spiegeln ist nicht immer
erlaubt.** Ein Bauteil mit Haendigkeit - linke und rechte Ausfuehrung - wird
durch Spiegeln zum jeweils anderen Teil. Als Trainingsbeispiel fuer dieselbe
Klasse ist das schlicht falsch. Deshalb ist die Spiegelung hier je Klasse
abschaltbar und nicht global.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Sequence, Tuple

import cv2
import numpy as np

from .assignment import GtObject


@dataclass
class AugmentConfig:
    """Augmentierung je Klasse. Vorgaben bewusst zurueckhaltend."""

    spiegeln_horizontal: bool = True
    spiegeln_vertikal: bool = False
    drehen_90: bool = True          # 90, 180, 270 Grad
    drehen_frei: bool = False       # beliebige Winkel
    drehschritte: int = 8           # nur bei drehen_frei
    haendigkeit: bool = False       # True -> Spiegeln gesperrt

    def erlaubt_spiegeln(self) -> bool:
        """Haendigkeit sticht jede Spiegel-Einstellung.

        Absichtlich nicht als stille Korrektur der Schalter, sondern als
        eigene Abfrage: so bleibt in der Oberflaeche sichtbar, dass der
        Bediener Spiegeln gewaehlt hat und WARUM es trotzdem nicht passiert.
        """
        return not self.haendigkeit

    def anzahl_varianten(self) -> int:
        n = 1
        if self.erlaubt_spiegeln():
            if self.spiegeln_horizontal:
                n *= 2
            if self.spiegeln_vertikal:
                n *= 2
        if self.drehen_frei:
            n *= max(self.drehschritte, 1)
        elif self.drehen_90:
            n *= 4
        return n


# ----------------------------------------------------------------------
def _obj_kopie(o: GtObject, **aend) -> GtObject:
    d = dict(cx=o.cx, cy=o.cy, width=o.width, height=o.height, angle=o.angle,
             class_id=o.class_id, visibility=o.visibility,
             rotation_matters=o.rotation_matters, obj_id=o.obj_id)
    d.update(aend)
    return GtObject(**d)


def spiegle(bild: np.ndarray, objekte: Sequence[GtObject],
            horizontal: bool = True) -> Tuple[np.ndarray, List[GtObject]]:
    """Spiegelt Bild und Annotation.

    Der Winkel wird negiert: aus theta wird 180 - theta. Ein um 30 Grad
    gedrehtes Teil erscheint im Spiegelbild um 150 Grad gedreht.
    """
    h, w = bild.shape[:2]
    if horizontal:
        neu = cv2.flip(bild, 1)
        objekte_neu = [
            _obj_kopie(o, cx=w - o.cx, angle=(180.0 - o.angle) % 180.0)
            for o in objekte
        ]
    else:
        neu = cv2.flip(bild, 0)
        objekte_neu = [
            _obj_kopie(o, cy=h - o.cy, angle=(180.0 - o.angle) % 180.0)
            for o in objekte
        ]
    return neu, objekte_neu


def drehe(bild: np.ndarray, objekte: Sequence[GtObject],
          winkel: float) -> Tuple[np.ndarray, List[GtObject]]:
    """Dreht Bild und Annotation um `winkel` Grad gegen den Uhrzeigersinn.

    Bei 90, 180 und 270 Grad wird verlustfrei umsortiert statt interpoliert -
    das erhaelt scharfe Kanten, auf die der Detektor angewiesen ist.
    """
    h, w = bild.shape[:2]
    winkel = winkel % 360.0

    if abs(winkel) < 1e-6:
        return bild.copy(), [_obj_kopie(o) for o in objekte]

    if abs(winkel - 90) < 1e-6:
        neu = cv2.rotate(bild, cv2.ROTATE_90_COUNTERCLOCKWISE)
        objekte_neu = [_obj_kopie(o, cx=o.cy, cy=w - o.cx,
                                  angle=(o.angle + 90.0) % 180.0) for o in objekte]
        return neu, objekte_neu
    if abs(winkel - 180) < 1e-6:
        neu = cv2.rotate(bild, cv2.ROTATE_180)
        objekte_neu = [_obj_kopie(o, cx=w - o.cx, cy=h - o.cy) for o in objekte]
        return neu, objekte_neu
    if abs(winkel - 270) < 1e-6:
        neu = cv2.rotate(bild, cv2.ROTATE_90_CLOCKWISE)
        objekte_neu = [_obj_kopie(o, cx=h - o.cy, cy=o.cx,
                                  angle=(o.angle + 90.0) % 180.0) for o in objekte]
        return neu, objekte_neu

    # Freier Winkel: um die Bildmitte drehen, Bildgroesse beibehalten.
    mitte = (w / 2.0, h / 2.0)
    M = cv2.getRotationMatrix2D(mitte, winkel, 1.0)
    neu = cv2.warpAffine(bild, M, (w, h), flags=cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_REPLICATE)
    objekte_neu = []
    for o in objekte:
        p = M @ np.array([o.cx, o.cy, 1.0])
        # MINUS, nicht plus. Die Bild-y-Achse zeigt nach unten, deshalb
        # verkleinert eine Drehung gegen den Uhrzeigersinn den ueber
        # atan2(dy, dx) gemessenen Winkel.
        #
        # Bei 90, 180 und 270 Grad faellt der Unterschied nicht auf: modulo
        # 180 liefern +90 und -90 dasselbe Ergebnis. Der Fehler zeigt sich
        # erst bei krummen Winkeln - und dann als konstante Abweichung von
        # 90 Grad, die man leicht dem Modell statt der Augmentierung
        # zuschreibt. Genau dafuer gibt es pruefe_winkelmitfuehrung().
        objekte_neu.append(_obj_kopie(o, cx=float(p[0]), cy=float(p[1]),
                                      angle=(o.angle - winkel) % 180.0))
    return neu, objekte_neu


# ----------------------------------------------------------------------
def erzeuge_varianten(
    bild: np.ndarray,
    objekte: Sequence[GtObject],
    cfg: AugmentConfig,
) -> List[Tuple[str, np.ndarray, List[GtObject]]]:
    """Alle erlaubten Varianten als (Bezeichnung, Bild, Objekte).

    Die Bezeichnung landet in der Oberflaeche, damit der Bediener sieht, was
    aus einer Aufnahme geworden ist - und bei Haendigkeit sofort erkennt,
    dass keine gespiegelten Varianten dabei sind.
    """
    aus: List[Tuple[str, np.ndarray, List[GtObject]]] = [
        ("original", bild.copy(), [_obj_kopie(o) for o in objekte])
    ]

    if cfg.erlaubt_spiegeln():
        basis = list(aus)
        for name, b, o in basis:
            if cfg.spiegeln_horizontal:
                nb, no = spiegle(b, o, horizontal=True)
                aus.append((f"{name}+gespiegelt", nb, no))
            if cfg.spiegeln_vertikal:
                nb, no = spiegle(b, o, horizontal=False)
                aus.append((f"{name}+gespiegelt-v", nb, no))

    if cfg.drehen_frei:
        schritte = max(cfg.drehschritte, 1)
        winkel_liste = [i * 360.0 / schritte for i in range(1, schritte)]
    elif cfg.drehen_90:
        winkel_liste = [90.0, 180.0, 270.0]
    else:
        winkel_liste = []

    if winkel_liste:
        basis = list(aus)
        for name, b, o in basis:
            for wnk in winkel_liste:
                nb, no = drehe(b, o, wnk)
                aus.append((f"{name}+{wnk:.0f}gr", nb, no))

    return aus


# ----------------------------------------------------------------------
def pruefe_winkelmitfuehrung(groesse: int = 128) -> List[str]:
    """Selbsttest: wandern die Winkel korrekt mit?

    Ein Testbild mit einem Balken bekannter Ausrichtung wird gedreht und
    gespiegelt; danach wird der Winkel aus dem Bild zurueckgemessen und mit
    der mitgefuehrten Annotation verglichen. Ohne diese Probe faellt eine
    falsche Winkelformel erst im Training auf - als unerklaerlich hoher
    Winkelfehler.
    """
    probleme: List[str] = []

    for ausgangswinkel in (0.0, 30.0, 75.0, 120.0, 160.0):
        bild = np.zeros((groesse, groesse, 3), np.uint8)
        obj = GtObject(cx=groesse / 2, cy=groesse / 2, width=groesse * 0.6,
                       height=groesse * 0.15, angle=ausgangswinkel, class_id=0)
        pts = cv2.boxPoints(((obj.cx, obj.cy), (obj.width, obj.height),
                             obj.angle)).astype(np.int32)
        cv2.fillConvexPoly(bild, pts, (255, 255, 255))

        faelle = [("spiegeln-h", *spiegle(bild, [obj], True)),
                  ("spiegeln-v", *spiegle(bild, [obj], False)),
                  ("drehen-90", *drehe(bild, [obj], 90.0)),
                  ("drehen-180", *drehe(bild, [obj], 180.0)),
                  ("drehen-270", *drehe(bild, [obj], 270.0)),
                  ("drehen-45", *drehe(bild, [obj], 45.0))]

        for name, nb, no in faelle:
            grau = cv2.cvtColor(nb, cv2.COLOR_BGR2GRAY)
            cnts, _ = cv2.findContours(grau, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
            if not cnts:
                probleme.append(f"{name} bei {ausgangswinkel:.0f}gr: nichts sichtbar")
                continue
            c = max(cnts, key=cv2.contourArea)
            (mx, my), (bw, bh), ang = cv2.minAreaRect(c)
            gemessen = (ang if bw >= bh else ang + 90.0) % 180.0
            erwartet = no[0].angle % 180.0
            d = abs(gemessen - erwartet) % 180.0
            d = min(d, 180.0 - d)
            if d > 4.0:
                probleme.append(
                    f"{name} bei {ausgangswinkel:.0f}gr: "
                    f"Annotation {erwartet:.1f}gr, im Bild {gemessen:.1f}gr "
                    f"(Abweichung {d:.1f}gr)")
            dm = math.hypot(mx - no[0].cx, my - no[0].cy)
            if dm > 3.0:
                probleme.append(
                    f"{name} bei {ausgangswinkel:.0f}gr: Mittelpunkt "
                    f"{dm:.1f} px daneben")

    return probleme
