"""Laenger laufende Arbeiten im Hintergrund, mit Fortschritt.

Training und Messreihen dauern Sekunden bis Minuten. Wuerden sie in der
HTTP-Anfrage laufen, liefe die Anfrage in eine Zeitueberschreitung und die
Oberflaeche saehe aus, als haenge sie - der haeufigste Grund, einen laufenden
Vorgang abzubrechen, der gerade funktioniert.

Deshalb: starten, sofort antworten, Fortschritt abholbar machen.
"""
from __future__ import annotations

import threading
import time
import traceback
from collections import deque
from typing import Callable, Deque, Optional


class Lauf:
    """Ein Vorgang im Hintergrund. Immer nur einer je Instanz."""

    def __init__(self, name: str, max_zeilen: int = 400):
        self.name = name
        self._zeilen: Deque[str] = deque(maxlen=max_zeilen)
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._abbruch = threading.Event()
        self.laeuft = False
        self.fertig = False
        self.ok: Optional[bool] = None
        self.phase = ""
        self.schritt = 0
        self.schritte = 0
        self.ergebnis: dict = {}
        self.grund = ""
        self.begonnen = 0.0
        self.beendet = 0.0

    # ------------------------------------------------------------------
    def melde(self, text: str) -> None:
        with self._lock:
            self._zeilen.append(text)
        print(f"[{self.name}] {text}", flush=True)

    def setze_phase(self, phase: str, schritt: int = 0, schritte: int = 0) -> None:
        self.phase = phase
        if schritte:
            self.schritte = schritte
        self.schritt = schritt

    @property
    def abbruch_gewuenscht(self) -> bool:
        return self._abbruch.is_set()

    # ------------------------------------------------------------------
    def starte(self, arbeit: Callable[["Lauf"], dict]) -> dict:
        if self.laeuft:
            return {"ok": False, "grund": f"{self.name} laeuft bereits"}

        self._zeilen.clear()
        self._abbruch.clear()
        self.laeuft = True
        self.fertig = False
        self.ok = None
        self.grund = ""
        self.ergebnis = {}
        self.schritt = self.schritte = 0
        self.phase = "startet"
        self.begonnen = time.time()
        self.beendet = 0.0

        def huelle():
            try:
                self.ergebnis = arbeit(self) or {}
                self.ok = bool(self.ergebnis.get("ok", True))
                if not self.ok:
                    self.grund = str(self.ergebnis.get("grund", ""))
            except Exception as exc:
                # Vollstaendiger Ablauf ins Protokoll. Eine abgeschnittene
                # Meldung kostet spaeter mehr Zeit, als sie Platz spart.
                self.ok = False
                self.grund = f"{type(exc).__name__}: {exc}"
                for z in traceback.format_exc().splitlines()[-12:]:
                    self.melde(z)
            finally:
                self.laeuft = False
                self.fertig = True
                self.beendet = time.time()
                # "abgebrochen" nur, wenn wirklich abgebrochen wurde. Ein
                # Fehlschlag als Abbruch zu melden schiebt die Ursache auf
                # den Bediener statt auf die Sache.
                self.phase = ("fertig" if self.ok
                              else ("abgebrochen" if self.abbruch_gewuenscht
                                    else "fehlgeschlagen"))

        self._thread = threading.Thread(target=huelle, daemon=True)
        self._thread.start()
        return {"ok": True, "gestartet": self.name}

    def abbrechen(self) -> dict:
        if not self.laeuft:
            return {"ok": False, "grund": "laeuft nicht"}
        self._abbruch.set()
        self.melde("Abbruch angefordert - laeuft bis zum naechsten Haltepunkt")
        return {"ok": True}

    # ------------------------------------------------------------------
    def as_dict(self, zeilen: int = 60) -> dict:
        with self._lock:
            protokoll = list(self._zeilen)[-zeilen:]
        dauer = (self.beendet or time.time()) - self.begonnen if self.begonnen else 0.0
        return {
            "name": self.name,
            "laeuft": self.laeuft,
            "fertig": self.fertig,
            "ok": self.ok,
            "phase": self.phase,
            "schritt": self.schritt,
            "schritte": self.schritte,
            "anteil": round(self.schritt / self.schritte, 3) if self.schritte else 0.0,
            "sekunden": round(dauer, 1),
            "grund": self.grund,
            "ergebnis": self.ergebnis,
            "protokoll": protokoll,
        }
