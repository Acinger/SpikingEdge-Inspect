"""Arbeitswarteschlange ueber mehrere AKD1500 (Profil P1).

Wichtig zum Verstaendnis: vier Akida-Chips bilden *keinen* vierfach grossen
Prozessor. Jedes Modell wird genau einem Geraet zugeordnet. Die Verteilung der
Arbeit muss der Raspberry Pi machen - genau das tut dieses Modul.

Ohne installierte MetaTF-Umgebung faellt der Pool automatisch auf einen
Stub-Klassifikator zurueck, damit die restliche Pipeline trotzdem laeuft.
"""
from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

import numpy as np

try:  # MetaTF ist nur auf dem Zielsystem installiert
    import akida  # type: ignore
    AKIDA_AVAILABLE = True
except Exception:  # pragma: no cover
    akida = None  # type: ignore
    AKIDA_AVAILABLE = False


# ----------------------------------------------------------------------
@dataclass
class WorkerInfo:
    index: int
    name: str
    backend: str          # "hardware" | "stub"
    jobs: int = 0
    total_ms: float = 0.0


class _Backend:
    """Ein Rechenknoten: genau ein Modell auf genau einem Geraet."""

    def infer(self, batch: np.ndarray) -> np.ndarray:  # pragma: no cover
        raise NotImplementedError


class HardwareBackend(_Backend):
    def __init__(self, model_file: str, device, hw_only: bool = True):
        self.model = akida.Model(model_file)
        self.model.map(device, hw_only=hw_only)
        self.device = device

    def infer(self, batch: np.ndarray) -> np.ndarray:
        # forward() liefert die Rohaktivierungen der letzten Schicht.
        return np.asarray(self.model.forward(batch))


class StubBackend(_Backend):
    """Platzhalter ohne Hardware.

    Gibt bewusst *keine* erfundene Klasse zurueck, sondern eine flache
    Verteilung mit niedriger Konfidenz. So faellt im Log sofort auf, dass hier
    noch kein trainiertes Modell laeuft.
    """

    def __init__(self, num_classes: int):
        self.num_classes = num_classes

    def infer(self, batch: np.ndarray) -> np.ndarray:
        n = len(batch)
        return np.full((n, self.num_classes), 1.0 / self.num_classes, dtype=np.float32)


# ----------------------------------------------------------------------
class AkidaPool:
    """Verteilt Crops auf N Geraete. Reihenfolge der Ergebnisse bleibt erhalten."""

    def __init__(
        self,
        model_file: str = "",
        num_classes: int = 8,
        max_devices: int = 4,
        hw_only: bool = True,
    ):
        self.workers: List[WorkerInfo] = []
        self._backends: List[_Backend] = []
        self._lock = threading.Lock()

        devices: Sequence = []
        if AKIDA_AVAILABLE and model_file:
            try:
                devices = list(akida.devices())[:max_devices]
            except Exception as exc:  # pragma: no cover
                print(f"[AkidaPool] akida.devices() fehlgeschlagen: {exc}")
                devices = []

        for i, dev in enumerate(devices):
            try:
                self._backends.append(HardwareBackend(model_file, dev, hw_only))
                self.workers.append(
                    WorkerInfo(i, getattr(dev, "desc", f"akida{i}"), "hardware")
                )
            except Exception as exc:  # pragma: no cover
                print(f"[AkidaPool] Geraet {i} nicht nutzbar: {exc}")

        if not self._backends:
            reason = (
                "MetaTF nicht installiert" if not AKIDA_AVAILABLE
                else "kein Modell angegeben" if not model_file
                else "kein Geraet gemappt"
            )
            print(f"[AkidaPool] Stub-Modus aktiv ({reason}). Ergebnisse sind Platzhalter.")
            self._backends.append(StubBackend(num_classes))
            self.workers.append(WorkerInfo(0, "stub", "stub"))

        self._task_q: "queue.Queue" = queue.Queue()
        self._threads: List[threading.Thread] = []
        self._results: dict = {}
        self._stop = threading.Event()

        for i in range(len(self._backends)):
            t = threading.Thread(target=self._loop, args=(i,), daemon=True)
            t.start()
            self._threads.append(t)

    # ------------------------------------------------------------------
    @property
    def num_workers(self) -> int:
        return len(self._backends)

    @property
    def on_hardware(self) -> bool:
        return any(w.backend == "hardware" for w in self.workers)

    # ------------------------------------------------------------------
    def _loop(self, widx: int) -> None:
        backend = self._backends[widx]
        while not self._stop.is_set():
            try:
                job = self._task_q.get(timeout=0.2)
            except queue.Empty:
                continue
            if job is None:
                self._task_q.task_done()
                break
            job_id, item_idx, sample = job
            t0 = time.perf_counter()
            try:
                out = backend.infer(sample[None, ...])[0]
            except Exception as exc:  # pragma: no cover
                out = None
                print(f"[AkidaPool] Worker {widx} Fehler: {exc}")
            dt = (time.perf_counter() - t0) * 1000.0

            with self._lock:
                self._results.setdefault(job_id, {})[item_idx] = out
                w = self.workers[widx]
                w.jobs += 1
                w.total_ms += dt
            self._task_q.task_done()

    # ------------------------------------------------------------------
    def infer_batch(self, batch: np.ndarray, timeout: float = 5.0) -> List[Optional[np.ndarray]]:
        """Verteilt die Crops und wartet auf alle Ergebnisse."""
        n = len(batch)
        if n == 0:
            return []

        job_id = object()
        with self._lock:
            self._results[job_id] = {}
        for i in range(n):
            self._task_q.put((job_id, i, batch[i]))

        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            with self._lock:
                done = len(self._results[job_id]) >= n
            if done:
                break
            time.sleep(0.001)

        with self._lock:
            res = self._results.pop(job_id, {})
        missing = n - len(res)
        if missing:
            print(f"[AkidaPool] {missing} Ergebnis(se) im Zeitlimit nicht erhalten.")
        return [res.get(i) for i in range(n)]

    # ------------------------------------------------------------------
    def stats(self) -> List[dict]:
        with self._lock:
            return [
                {
                    "worker": w.index,
                    "name": w.name,
                    "backend": w.backend,
                    "jobs": w.jobs,
                    "avg_ms": round(w.total_ms / w.jobs, 2) if w.jobs else 0.0,
                }
                for w in self.workers
            ]

    def close(self) -> None:
        self._stop.set()
        for _ in self._threads:
            self._task_q.put(None)
        for t in self._threads:
            t.join(timeout=1.0)

    def __enter__(self) -> "AkidaPool":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


# ----------------------------------------------------------------------
def softmax(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32).ravel()
    x = x - x.max()
    e = np.exp(x)
    return e / max(e.sum(), 1e-9)
