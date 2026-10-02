"""Testsatz (SE Inspect 1.0, A6/A7): Pruefszenen mit Soll-Werten.

Ein Testsatz ist die Voraussetzung dafuer, dass die Qualitaetsziele (Q1-Q4)
Zahlen sind und keine Behauptungen. Jede Szene: ein Bild des
Pruef-Ausschnitts, die Soll-Klassen (Mehrfachnennung erlaubt, leer =
nichts liegt), eine Notiz und - zur Bequemlichkeit - das Ist-Urteil im
Moment der Aufnahme. Der Testsatz wird NICHT zum Lernen benutzt.

Ablage: <daten>/testsatz/NNNN.jpg + testsatz.json
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np


class Testsatz:
    DATEI = "testsatz.json"

    def __init__(self, ordner):
        self.ordner = Path(ordner) / "testsatz"
        self.ordner.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.szenen: List[dict] = []
        self._laden()

    def _laden(self) -> None:
        p = self.ordner / self.DATEI
        try:
            if p.exists():
                d = json.loads(p.read_text(encoding="utf-8"))
                self.szenen = list(d.get("szenen") or [])
        except Exception:
            self.szenen = []

    def _speichern(self) -> None:
        p = self.ordner / self.DATEI
        p.write_text(json.dumps({"version": 1, "szenen": self.szenen},
                                ensure_ascii=False, indent=1), encoding="utf-8")

    def _naechste_id(self) -> int:
        return (max((int(s.get("id", 0)) for s in self.szenen), default=0) + 1)

    def aufnehmen(self, bild: np.ndarray, soll: List[str], notiz: str = "",
                  ist: Optional[List[dict]] = None, quelle: str = "haupt") -> dict:
        if bild is None or bild.size == 0:
            return {"ok": False, "grund": "kein Bild"}
        soll = [str(s).strip() for s in (soll or []) if str(s).strip()]
        with self._lock:
            nr = self._naechste_id()
            datei = f"{nr:04d}.jpg"
            cv2.imwrite(str(self.ordner / datei), bild, [cv2.IMWRITE_JPEG_QUALITY, 95])
            h, w = bild.shape[:2]
            eintrag = {"id": nr, "datei": datei, "zeit": time.time(),
                       "soll": soll, "leer": not soll, "notiz": str(notiz or "")[:200],
                       "ist": [{"name": o.get("name"), "anteil": round(float(o.get("anteil") or 0), 3)}
                               for o in (ist or [])],
                       "bild": [w, h], "quelle": quelle}
            self.szenen.append(eintrag)
            self._speichern()
        return {"ok": True, "szene": eintrag, "anzahl": len(self.szenen)}

    def loeschen(self, nr: int) -> dict:
        with self._lock:
            rest = [s for s in self.szenen if int(s.get("id", -1)) != int(nr)]
            weg = [s for s in self.szenen if int(s.get("id", -1)) == int(nr)]
            for s in weg:
                try:
                    (self.ordner / s["datei"]).unlink(missing_ok=True)
                except Exception:
                    pass
            self.szenen = rest
            self._speichern()
        return {"ok": bool(weg), "anzahl": len(self.szenen)}

    def soll_aendern(self, nr: int, soll: List[str], notiz: Optional[str] = None) -> dict:
        with self._lock:
            for s in self.szenen:
                if int(s.get("id", -1)) == int(nr):
                    s["soll"] = [str(x).strip() for x in soll if str(x).strip()]
                    s["leer"] = not s["soll"]
                    if notiz is not None:
                        s["notiz"] = str(notiz)[:200]
                    self._speichern()
                    return {"ok": True, "szene": s}
        return {"ok": False, "grund": "Szene unbekannt"}

    def bild(self, datei: str) -> Optional[bytes]:
        p = self.ordner / Path(datei).name
        return p.read_bytes() if p.exists() else None

    def uebersicht(self) -> dict:
        n = len(self.szenen)
        leer = sum(1 for s in self.szenen if s.get("leer"))
        einzeln = sum(1 for s in self.szenen if len(s.get("soll") or []) == 1)
        mehrere = sum(1 for s in self.szenen if len(s.get("soll") or []) >= 2)
        klassen: dict = {}
        for s in self.szenen:
            for k in s.get("soll") or []:
                klassen[k] = klassen.get(k, 0) + 1
        return {"anzahl": n, "leer": leer, "einzeln": einzeln, "mehrere": mehrere,
                "klassen": klassen, "letzte": list(reversed(self.szenen[-6:]))}
