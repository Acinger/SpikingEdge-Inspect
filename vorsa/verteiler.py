"""Kartenverteiler (SE Inspect 1.0, A4).

Mehrere Bewertungsauftraege (Ausschnitte, Hypothesen-Teile) gleichzeitig
auf mehrere AKD1500-Karten legen. Voraussetzung ist der REPLIZIERTE Verbund
(jede Karte traegt alle Prototypen, EdgeLerner.verbund_modus ==
"repliziert"); im verteilten Verbund braucht jeder Auftrag alle Karten und
laeuft wie bisher nacheinander.

Regeln:
  - je Karte ein Arbeitsthread; Auftraege reihum auf die NUTZBAREN Karten
    (Karten-Waechter: gestoerte Karten werden uebersprungen)
  - wirft eine Karte mitten im Auftrag, meldet erkenne_auf_karte das dem
    Waechter; der Auftrag wird einmal auf einer anderen Karte wiederholt,
    zuletzt ueber den normalen Verbundweg (bewerte ohne ki)
  - Rueckfall sequentiell, wenn < 2 nutzbare Karten oder nicht repliziert
Die Pi-CPU-Vorarbeit (Freistellen, Aufrichten) liegt in `bewerte` und
laeuft mit im Thread - sie ist numpy/OpenCV und gibt den GIL frei.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, List, Optional


class Kartenverteiler:
    def __init__(self, lerner, max_karten: int = 4):
        self.lerner = lerner
        self.max_karten = max_karten
        self._pool: Optional[ThreadPoolExecutor] = None
        self._pool_n = 0
        self._lock = threading.Lock()
        self.stand = {"modus": "sequentiell", "karten": 0, "auftraege": 0,
                      "parallel": 0, "wiederholt": 0, "ms_letzte": 0.0}

    # -- Karten ---------------------------------------------------------
    def karten(self) -> List[int]:
        l = self.lerner
        try:
            info = l.verbund_info()
        except Exception:
            return []
        if info.get("modus") != "repliziert":
            return []
        return list(info.get("nutzbar", []))[:self.max_karten]

    def _pool_fuer(self, n: int) -> ThreadPoolExecutor:
        with self._lock:
            if self._pool is None or self._pool_n != n:
                if self._pool is not None:
                    self._pool.shutdown(wait=False)
                self._pool = ThreadPoolExecutor(max_workers=n, thread_name_prefix="karte")
                self._pool_n = n
            return self._pool

    # -- Auftraege ------------------------------------------------------
    def bewerte_viele(self, bewerte: Callable) -> Callable:
        """Liefert f(auftraege) fuer vorsa.hypothesen: auftraege = [(box, kontur)]."""
        def viele(auftraege):
            t0 = time.perf_counter()
            karten = self.karten()
            n = len(auftraege)
            self.stand["auftraege"] += n
            if len(karten) < 2 or n < 2:
                self.stand["modus"] = "sequentiell"
                self.stand["karten"] = len(karten)
                aus = [self._sicher(bewerte, b, k, None) for b, k in auftraege]
                self.stand["ms_letzte"] = round((time.perf_counter() - t0) * 1000, 1)
                return aus
            self.stand["modus"] = "parallel"
            self.stand["karten"] = len(karten)
            self.stand["parallel"] += n
            pool = self._pool_fuer(len(karten))
            futs = []
            for i, (b, k) in enumerate(auftraege):
                ki = karten[i % len(karten)]
                futs.append(pool.submit(self._mit_wiederholung, bewerte, b, k, ki, karten))
            aus = [f.result() for f in futs]
            self.stand["ms_letzte"] = round((time.perf_counter() - t0) * 1000, 1)
            return aus
        return viele

    def _sicher(self, bewerte, box, kontur, ki):
        try:
            return bewerte(box, kontur, ki=ki) if ki is not None else bewerte(box, kontur)
        except Exception:
            return None

    def _mit_wiederholung(self, bewerte, box, kontur, ki, karten):
        try:
            return bewerte(box, kontur, ki=ki)
        except Exception:
            self.stand["wiederholt"] += 1
            # eine andere, noch nutzbare Karte probieren
            for alt in karten:
                if alt == ki:
                    continue
                try:
                    if not self.lerner.karte_nutzbar(alt):
                        continue
                    return bewerte(box, kontur, ki=alt)
                except Exception:
                    continue
            # zuletzt der normale Verbundweg (Waechter sortiert die Karte aus)
            return self._sicher(bewerte, box, kontur, None)

    def als_dict(self) -> dict:
        return dict(self.stand)
