"""Statistik und Trend (SE Inspect 1.1-C).

Das Pruefbuch zaehlt nur seit dem letzten Zuruecksetzen und vergisst beim
Neustart. Hier entsteht daraus ein dauerhaftes Journal und eine Auswertung:

  Journal   <daten>/pruefjournal.jsonl - eine Zeile je gebuchtem Teil
            {"t": Zeit, "u": Urteil, "n": Name, "k": Konfidenz} und je Training
            {"t": Zeit, "ereignis": "training"}. Wird ab 20 MB auf die letzten
            200 000 Zeilen gekuerzt.
  Trend     je Stunde (letzte 24 h) und je Tag (letzte 14 Tage): Teile,
            Gut-/Unbekannt-/Ausschuss-Quote, mittlere Konfidenz der benannten Teile.
  Drift     mittlere Konfidenz der letzten 50 benannten Teile gegen die ersten 50
            nach dem letzten Training. Faellt sie um >= 8 Punkte, meldet die
            Anlage "Sicherheit sinkt" - meist Licht, Kamera oder neue Teilevarianten,
            selten das Gelernte. Die Unbekannt-Quote derselben Fenster steht daneben.
"""
from __future__ import annotations

import json
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

DRIFT_FENSTER = 50
DRIFT_SCHWELLE = 0.08


class Journal:
    DATEI = "pruefjournal.jsonl"
    MAX_BYTES = 20 * 1024 * 1024

    def __init__(self, ordner):
        self.pfad = Path(ordner) / self.DATEI if ordner else None
        self._lock = threading.Lock()

    def schreibe(self, eintrag: dict) -> None:
        if not self.pfad:
            return
        try:
            with self._lock:
                with open(self.pfad, "a", encoding="utf-8") as f:
                    f.write(json.dumps(eintrag, ensure_ascii=False, separators=(",", ":")) + "\n")
                if self.pfad.stat().st_size > self.MAX_BYTES:
                    z = self.pfad.read_text(encoding="utf-8").splitlines()[-200_000:]
                    self.pfad.write_text("\n".join(z) + "\n", encoding="utf-8")
        except Exception:
            pass

    def teil(self, urteil: str, name: str, konfidenz: float, t: Optional[float] = None) -> None:
        self.schreibe({"t": round(t or time.time(), 1), "u": urteil, "n": name or "", "k": round(float(konfidenz or 0), 3)})

    def training(self, t: Optional[float] = None) -> None:
        self.schreibe({"t": round(t or time.time(), 1), "ereignis": "training"})

    def lesen(self, seit: float = 0.0) -> list:
        if not self.pfad or not self.pfad.exists():
            return []
        aus = []
        try:
            with open(self.pfad, encoding="utf-8") as f:
                for z in f:
                    try:
                        e = json.loads(z)
                    except Exception:
                        continue
                    if e.get("t", 0) >= seit:
                        aus.append(e)
        except Exception:
            return []
        return aus


def _eimer(eintraege: list, start: float, breite: float, anzahl: int) -> list:
    b = [defaultdict(float) for _ in range(anzahl)]
    for e in eintraege:
        if "u" not in e:
            continue
        i = int((e["t"] - start) // breite)
        if 0 <= i < anzahl:
            x = b[i]
            x["n"] += 1
            x[e["u"]] += 1
            if e["u"] in ("gut", "ausschuss") and e.get("n"):
                x["ks"] += e.get("k", 0)
                x["kn"] += 1
    aus = []
    for i, x in enumerate(b):
        n = int(x["n"])
        aus.append({"start": start + i * breite, "teile": n,
                    "gut": round(x["gut"] / n * 100, 1) if n else None,
                    "unbekannt": round(x["unbekannt"] / n * 100, 1) if n else None,
                    "ausschuss": round(x["ausschuss"] / n * 100, 1) if n else None,
                    "konfidenz": round(x["ks"] / x["kn"], 3) if x["kn"] else None})
    return aus


def auswerten(eintraege: list, jetzt: Optional[float] = None) -> dict:
    jetzt = jetzt or time.time()
    lt = time.localtime(jetzt)
    stunde0 = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, lt.tm_hour, 0, 0, 0, 0, -1)) - 23 * 3600
    tag0 = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1)) - 13 * 86400
    stunden = _eimer(eintraege, stunde0, 3600, 24)
    # Tage: Lokalzeit-Mitternacht (Sommerzeit ignoriert -> 1 h Unschaerfe, egal)
    tage = _eimer(eintraege, tag0, 86400, 14)
    teile = [e for e in eintraege if "u" in e]
    trainings = [e["t"] for e in eintraege if e.get("ereignis") == "training"]
    letztes_training = max(trainings) if trainings else None
    benannt = [e for e in teile if e["u"] in ("gut", "ausschuss") and e.get("n")]
    seit = [e for e in benannt if letztes_training is None or e["t"] >= letztes_training]
    drift = {"status": "zu_wenig", "referenz": None, "aktuell": None, "differenz": None,
             "fenster": DRIFT_FENSTER, "seit_training": len(seit), "letztes_training": letztes_training}
    if len(seit) >= 2 * DRIFT_FENSTER:
        ref = sum(e["k"] for e in seit[:DRIFT_FENSTER]) / DRIFT_FENSTER
        akt = sum(e["k"] for e in seit[-DRIFT_FENSTER:]) / DRIFT_FENSTER
        alle_seit = [e for e in teile if letztes_training is None or e["t"] >= letztes_training]
        unb = lambda xs: round(sum(1 for e in xs if e["u"] == "unbekannt") / len(xs) * 100, 1) if xs else None
        drift.update({"referenz": round(ref, 3), "aktuell": round(akt, 3), "differenz": round(akt - ref, 3),
                      "unbekannt_anfang": unb(alle_seit[:2 * DRIFT_FENSTER]), "unbekannt_jetzt": unb(alle_seit[-2 * DRIFT_FENSTER:]),
                      "status": "sinkt" if akt - ref <= -DRIFT_SCHWELLE else "stabil"})
    heute = [e for e in teile if e["t"] >= time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))]
    return {"stunden": stunden, "tage": tage, "drift": drift, "gesamt": len(teile),
            "heute": {"teile": len(heute), "gut": sum(1 for e in heute if e["u"] == "gut"),
                      "unbekannt": sum(1 for e in heute if e["u"] == "unbekannt"),
                      "ausschuss": sum(1 for e in heute if e["u"] == "ausschuss")}}
