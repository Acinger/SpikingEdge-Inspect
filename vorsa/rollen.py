"""Benutzerrollen mit PIN und Änderungsprotokoll (Industrie-Paket I3, 1.9.60).

  bediener   prüfen, quittieren, Prüfprogramm laden, Linie starten/stoppen
  einrichter zusätzlich: einrichten, anlernen, alle Einstellungen
  admin      zusätzlich: PINs, Rollen, Ein-/Ausgänge, Löschen von Gelerntem

Solange kein Admin-PIN gesetzt ist, sind Rollen AUS und alles ist offen - wie
bisher. Mit dem ersten Admin-PIN wird die Anlage ohne Anmeldung zur
Bedienstation. Die Prüfung erfolgt im Server (nicht nur in der Oberfläche).

PINs: 4-8 Ziffern, gespeichert nur als PBKDF2-Hash mit Salz (rollen.json).
Sitzungen: Zufallstoken je Browser, verfallen nach N Minuten ohne Aktion.
Fehlversuche: nach 5 Fehlern 30 s Sperre.
Änderungsprotokoll: jede ändernde Aktion mit Zeit, Rolle, Weg, Kurzinhalt
(aenderungen.jsonl, die letzten 2000 Zeilen).
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
import time
from pathlib import Path
from typing import Optional

STUFE = {"bediener": 0, "einrichter": 1, "admin": 2}

# Was ein Bediener darf (POST). Alles andere braucht mindestens "einrichter".
BEDIENER = {
    "/api/pruefen", "/api/alarm_quittieren", "/api/rezept_laden", "/api/linie",
    "/api/anzeige", "/api/anzeigegroesse", "/api/rahmen_pause", "/api/ereignis",
    "/api/anmelden", "/api/abmelden", "/api/linie_ansicht",
}
# Nur Admin.
ADMIN = {
    "/api/rollen", "/api/eaio", "/api/sps", "/api/sicherung", "/api/sicherung_pruefen", "/api/sicherung_einspielen", "/api/vergessen", "/api/klasse_loeschen",
    "/api/ereignisse_leeren", "/api/rezept_loeschen", "/api/preset_loeschen",
}
# Nicht ins Änderungsprotokoll (häufig und harmlos).
LEISE = {"/api/anzeigegroesse", "/api/rahmen_pause", "/api/ereignis", "/api/anmelden", "/api/pruefen",
         "/api/abmelden", "/api/linie_ansicht", "/api/anzeige"}


def _hash(pin: str, salz: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salz), 120_000).hex()


class Rollen:
    def __init__(self, ordner):
        self._pfad = Path(ordner) / "rollen.json" if ordner else None
        self._log = Path(ordner) / "aenderungen.jsonl" if ordner else None
        self._lock = threading.Lock()
        self.d = {"salz": secrets.token_hex(16), "pins": {}, "abmelden_min": 15}
        self._sitzungen: dict = {}       # token -> {"rolle", "zuletzt"}
        self._fehl = 0
        self._sperre_bis = 0.0
        self._laden()

    # -- Datei -----------------------------------------------------------
    def _laden(self):
        try:
            if self._pfad and self._pfad.exists():
                d = json.loads(self._pfad.read_text(encoding="utf-8"))
                if isinstance(d.get("pins"), dict) and d.get("salz"):
                    self.d.update(d)
        except Exception:
            pass

    def _speichern(self):
        try:
            if self._pfad:
                tmp = self._pfad.with_suffix(".tmp")
                tmp.write_text(json.dumps(self.d), encoding="utf-8")
                os.replace(tmp, self._pfad)
                try:
                    os.chmod(self._pfad, 0o600)
                except Exception:
                    pass
        except Exception:
            pass

    # -- Zustand ---------------------------------------------------------
    def aktiv(self) -> bool:
        return bool(self.d["pins"].get("admin"))

    def noetig(self, weg: str, koerper: dict) -> str:
        if weg == "/api/betriebsart":
            return "bediener" if str(koerper.get("art")) == "betreiben" else "einrichter"
        if weg in BEDIENER:
            return "bediener"
        if weg in ADMIN:
            return "admin"
        return "einrichter"

    def rolle(self, token: str) -> str:
        if not self.aktiv():
            return "admin"               # Rollen aus: alles offen
        with self._lock:
            s = self._sitzungen.get(token or "")
            if not s:
                return "bediener"
            if time.time() - s["zuletzt"] > 60 * max(1, int(self.d.get("abmelden_min", 15))):
                self._sitzungen.pop(token, None)
                return "bediener"
            s["zuletzt"] = time.time()
            return s["rolle"]

    @staticmethod
    def darf(rolle: str, noetig: str) -> bool:
        return STUFE.get(rolle, 0) >= STUFE.get(noetig, 1)

    # -- Anmelden --------------------------------------------------------
    def anmelden(self, pin: str) -> dict:
        jetzt = time.time()
        if jetzt < self._sperre_bis:
            return {"ok": False, "grund": f"zu viele Fehlversuche - {int(self._sperre_bis - jetzt) + 1} s warten"}
        pin = str(pin or "").strip()
        for rolle in ("admin", "einrichter"):
            h = self.d["pins"].get(rolle)
            if h and secrets.compare_digest(h, _hash(pin, self.d["salz"])):
                tok = secrets.token_urlsafe(24)
                with self._lock:
                    # alte Sitzungen begrenzen
                    if len(self._sitzungen) > 50:
                        self._sitzungen.clear()
                    self._sitzungen[tok] = {"rolle": rolle, "zuletzt": jetzt}
                self._fehl = 0
                self.protokoll(rolle, "/api/anmelden", {})
                return {"ok": True, "token": tok, "rolle": rolle}
        self._fehl += 1
        if self._fehl >= 5:
            self._sperre_bis = jetzt + 30
            self._fehl = 0
        return {"ok": False, "grund": "PIN falsch"}

    def abmelden(self, token: str) -> dict:
        with self._lock:
            self._sitzungen.pop(token or "", None)
        return {"ok": True, "rolle": "bediener" if self.aktiv() else "admin"}

    # -- Verwaltung (Admin) ------------------------------------------------
    def verwalten(self, rolle: str, k: dict) -> dict:
        a = k.get("aktion")
        if a == "pin":
            ziel = str(k.get("rolle", ""))
            pin = str(k.get("pin", "")).strip()
            if ziel not in ("admin", "einrichter"):
                return {"ok": False, "grund": "Rolle admin oder einrichter"}
            if ziel == "einrichter" and pin == "":
                self.d["pins"].pop("einrichter", None)
                self._speichern()
                return {"ok": True, **self.uebersicht(rolle)}
            if not (pin.isdigit() and 4 <= len(pin) <= 8):
                return {"ok": False, "grund": "PIN: 4 bis 8 Ziffern"}
            andere = "einrichter" if ziel == "admin" else "admin"
            h = _hash(pin, self.d["salz"])
            if self.d["pins"].get(andere) == h:
                return {"ok": False, "grund": "Admin- und Einrichter-PIN müssen verschieden sein"}
            self.d["pins"][ziel] = h
            self._speichern()
            return {"ok": True, **self.uebersicht(rolle)}
        if a == "aus":
            self.d["pins"] = {}
            with self._lock:
                self._sitzungen.clear()
            self._speichern()
            return {"ok": True, **self.uebersicht("admin")}
        if a == "zeit":
            self.d["abmelden_min"] = max(1, min(480, int(k.get("minuten", 15))))
            self._speichern()
            return {"ok": True, **self.uebersicht(rolle)}
        return {"ok": False, "grund": "aktion=pin|aus|zeit"}

    # -- Protokoll ---------------------------------------------------------
    def protokoll(self, rolle: str, weg: str, koerper: dict):
        if weg in LEISE and weg != "/api/anmelden":
            return
        kurz = {k: v for k, v in (koerper or {}).items() if k not in ("pin", "bild", "daten")}
        text = json.dumps(kurz, ensure_ascii=False)[:160]
        e = {"zeit": time.strftime("%Y-%m-%d %H:%M:%S"), "rolle": rolle if self.aktiv() else "offen",
             "weg": weg, "inhalt": text}
        try:
            if self._log:
                with self._lock:
                    with open(self._log, "a", encoding="utf-8") as f:
                        f.write(json.dumps(e, ensure_ascii=False) + "\n")
                    if self._log.stat().st_size > 600_000:
                        zeilen = self._log.read_text(encoding="utf-8").splitlines()[-2000:]
                        self._log.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
        except Exception:
            pass

    def letzte(self, n: int = 50) -> list:
        try:
            if self._log and self._log.exists():
                z = self._log.read_text(encoding="utf-8").splitlines()[-n:]
                return [json.loads(x) for x in reversed(z) if x.strip()]
        except Exception:
            pass
        return []

    def uebersicht(self, rolle: str) -> dict:
        return {"aktiv": self.aktiv(), "rolle": rolle,
                "pins": {r: bool(self.d["pins"].get(r)) for r in ("admin", "einrichter")},
                "abmelden_min": int(self.d.get("abmelden_min", 15)),
                "protokoll": self.letzte(50) if self.darf(rolle, "einrichter") else []}
