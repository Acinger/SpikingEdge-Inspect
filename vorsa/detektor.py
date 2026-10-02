"""M3-Detektor: das trainierte Netz findet Teile trotz Ueberlappung.

Stufe 2 des Kartenplans (eingebaut 2026-08-28): bei satt ueberlappenden
Teilen sieht die Geometrie nur EINEN Klumpen - die Wasserscheide hat keine
Trennlinie, und der Silhouetten-Abgleich bekommt den ganzen Klumpen
vorgelegt. Genau dafuer wurde VORSA-M3 trainiert: es sagt Kaesten, Winkel
und Verdeckungsgrad MEHRERER Teile in einem einzigen Durchgang voraus.

Arbeitsteilung: der Detektor liefert WO (Kaesten samt Verdeckung), der
Silhouetten-Verbund liefert WAS (die Namen). Die Klassenkoepfe des
Detektors werden bewusst ignoriert - seine Klassenliste stammt aus der
Trainingszeit und muss nicht zur aktuellen Fotoverwaltung passen.
"""
from __future__ import annotations

import time
from typing import List, Tuple

import cv2
import numpy as np

from . import config
from .detection import Detection, rotated_iou
from .postprocess import decode_head, soft_nms


class M3Detektor:
    """Haelt das geladene vorsa_m3.fbz auf einer eigenen Karte."""

    def __init__(self, pfad: str, geraet=None):
        import akida
        self.pfad = str(pfad)
        self.modell = akida.Model(self.pfad)
        self.geraet = geraet
        if geraet is not None:
            self.modell.map(geraet, hw_only=True)
        self.px = int(config.MODEL.input_size[0])
        self.nms = config.NMSParams()
        self.ms = 0.0                    # letzte Laufzeit, fuer die Anzeige

    def finde(self, bild: np.ndarray,
              obj_ab: float = 0.0) -> Tuple[List[Detection], list]:
        """Detektionen im Koordinatensystem von `bild`.

        `predict` liefert Fliesskommawerte (der Kopf ist linear), decode_head
        macht daraus Kaesten, soft_nms raeumt Doppeltreffer weg - mit Schutz
        fuer Slots desselben Feldes, damit Ueberlagerungen ueberleben.
        """
        t0 = time.perf_counter()
        klein = cv2.resize(bild, (self.px, self.px),
                           interpolation=cv2.INTER_AREA)
        t1 = time.perf_counter()
        roh = self.modell.predict(
            np.ascontiguousarray(klein[None, ...], dtype=np.uint8))[0]
        # Nur der Kartendurchgang - Dekodierung und NMS sind Pi-CPU.
        self.ms_chip = (time.perf_counter() - t1) * 1000.0
        dets, voll = decode_head(roh, (bild.shape[1], bild.shape[0]))
        dets = soft_nms(dets, self.nms)
        if obj_ab > 0:
            dets = [d for d in dets if d.score >= obj_ab]
        # Zellen-Doppelgaenger wegraeumen. protect_same_cell laesst Slots
        # desselben Feldes absichtlich leben - richtig fuer drei fast
        # deckungsgleiche Trainingsobjekte, aber auf dem Pruefplatz malte es
        # vier Kaesten um zwei Teile (2026-08-28). Gierig nach Punktzahl:
        # wer sich stark mit einem Behaltenen ueberlappt, fliegt.
        dets = sorted(dets, key=lambda d: -d.score)
        behalten = []
        for d in dets:
            if all(rotated_iou(d.box, b.box) < 0.45
                   # Slots DERSELBEN Zelle sind konstruktionsbedingt
                   # verschiedene Objekte - genau dafuer wurde M3 gebaut.
                   # Der pauschale Dedup hat bei satt ueberlappenden
                   # Teilen den zweiten Kasten gefressen (2026-08-28).
                   or (d.meta.get("cell") == b.meta.get("cell")
                       and d.meta.get("slot") != b.meta.get("slot"))
                   for b in behalten):
                behalten.append(d)
        # Hoechstens 8: mit 29 Rohkaesten kostete jeder Treffer in einer
        # Kontur einen Schiedsrichter-Chipaufruf - 427 ms je Bild
        # (2026-08-28). Mehr als 8 Teile liegen nie im Rahmen.
        dets = behalten[:8]
        # Klassenurteil des Detektors verwerfen - benennen ist Sache des
        # Silhouetten-Verbunds (siehe Modulkommentar).
        for d in dets:
            d.class_id = -1
            d.class_score = 0.0
        self.ms = (time.perf_counter() - t0) * 1000.0
        return dets, voll
