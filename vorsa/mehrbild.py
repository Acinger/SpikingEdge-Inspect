"""Mehrbild-Aufnahme fuer die stationaere Pruefung (SE Inspect 1.0, A2).

Ein Teil, das still liegt, darf mehrfach fotografiert werden. Das Mittel
ueber N Bilder senkt das Sensorrauschen um etwa sqrt(N) und glaettet das
Flackern von LED-Treibern und Belichtungsregelung - genau die beiden
Dinge, die die Differenz zum Leerbild und die Blendfleck-Halos unruhig
machen. Bewegt sich etwas, waere Mitteln falsch (Bewegungsunschaerfe,
Geisterbilder): dann wird der Puffer verworfen und das aktuelle Bild
genommen.

Reine numpy-Logik, keine Kamera, kein Server - damit die Bench sie exakt
pruefen kann.
"""
from __future__ import annotations

from collections import deque
from typing import Optional

import cv2
import numpy as np


class Mehrbild:
    """Gleitendes Mittel ueber die letzten N Bilder einer STEHENDEN Szene.

    anzahl        - wie viele Bilder hoechstens gemittelt werden (1 = aus)
    bewegung_max  - mittlere absolute Differenz (0..255) zum vorigen Bild,
                    ab der die Szene als bewegt gilt und der Puffer faellt
    """

    def __init__(self, anzahl: int = 4, bewegung_max: float = 2.5):
        self.anzahl = max(1, int(anzahl))
        self.bewegung_max = float(bewegung_max)
        self._puffer: deque = deque()
        self._summe: Optional[np.ndarray] = None
        self._letztes: Optional[np.ndarray] = None
        self.bewegung = 0.0          # letzte gemessene Bewegung
        self.gemittelt = 0           # wie viele Bilder im letzten Ergebnis

    def zuruecksetzen(self) -> None:
        self._puffer.clear()
        self._summe = None
        self.gemittelt = 0

    def einstellen(self, anzahl: Optional[int] = None,
                   bewegung_max: Optional[float] = None) -> None:
        if anzahl is not None:
            self.anzahl = max(1, int(anzahl))
            while len(self._puffer) > self.anzahl:
                alt = self._puffer.popleft()
                if self._summe is not None:
                    cv2.subtract(self._summe, alt, dst=self._summe)
        if bewegung_max is not None:
            self.bewegung_max = float(bewegung_max)

    @staticmethod
    def _bewegung(a: np.ndarray, b: np.ndarray) -> float:
        # Grob abgetastet (jedes 4. Pixel) - das reicht fuer "steht / steht
        # nicht" und kostet bei 1080p unter einer Millisekunde.
        ka = a[::4, ::4].astype(np.int16)
        kb = b[::4, ::4].astype(np.int16)
        return float(np.abs(ka - kb).mean())

    def verarbeite(self, frame: np.ndarray) -> np.ndarray:
        """Gibt das zu verwendende Bild zurueck: Mittel oder Original."""
        if self.anzahl <= 1:
            self._letztes = frame
            self.gemittelt = 1
            self.bewegung = 0.0
            return frame
        if (self._letztes is not None and self._letztes.shape == frame.shape):
            self.bewegung = self._bewegung(self._letztes, frame)
        else:
            self.bewegung = 0.0
            self.zuruecksetzen()
        self._letztes = frame
        if self.bewegung > self.bewegung_max:
            # Szene hat sich geaendert: alter Puffer weg. Das aktuelle Bild
            # ist schon das erste der neuen Szene und zaehlt mit.
            self.zuruecksetzen()
        # uint16-Summe mit OpenCV-Arithmetik: ~4x schneller als float32 in
        # numpy (Audit 2026-10-02: 6 ms statt 24 ms fuer 1296^2 auf x86).
        # 16 x 255 = 4080 passt in 16 Bit.
        f16 = frame.astype(np.uint16)
        if self._summe is None or self._summe.shape != f16.shape or self._summe.dtype != np.uint16:
            self._summe = np.zeros_like(f16)
            self._puffer.clear()
        self._puffer.append(f16)
        cv2.add(self._summe, f16, dst=self._summe)
        while len(self._puffer) > self.anzahl:
            cv2.subtract(self._summe, self._puffer.popleft(), dst=self._summe)
        self.gemittelt = len(self._puffer)
        if self.gemittelt == 1:
            return frame
        return cv2.convertScaleAbs(self._summe, alpha=1.0 / self.gemittelt)

    def als_dict(self) -> dict:
        return {"anzahl": self.anzahl, "gemittelt": self.gemittelt,
                "bewegung": round(self.bewegung, 2),
                "bewegung_max": self.bewegung_max}
