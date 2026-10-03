"""Digitale Ein-/Ausgaenge (Industrie-Paket I1, Build 1.9.59).

Damit sich SE Inspect wie eine Industriekamera in eine Anlage einbinden laesst:

  Eingang  trigger   steigende Flanke -> eine Pruefung ausloesen
                     (Lichtschranke, Taster oder SPS-Ausgang)
  Ausgang  bereit    Anlage bereit (Bild aktuell, keine Stoerung)
  Ausgang  ok        nach jeder Pruefung: alles gut          (Puls oder Halten)
  Ausgang  nok       nach jeder Pruefung: unbekannt/ausschuss (Puls oder Halten)
  Ausgang  fehler    aktive Stoerung / Alarm

Treiber (eine Konfiguration, austauschbar):
  sim     Simulation - Standard. Kein Zugriff auf Hardware; Zustaende sind in
          der Oberflaeche sichtbar, der Trigger laesst sich per Knopf ausloesen.
  gpio    Pi-GPIO ueber gpiozero (lgpio-Backend auf dem Pi 5). Fuer
          Optokoppler-/Relaismodule und GPIO-basierte Relais-HATs.
  modbus  Modbus-TCP-I/O-Modul im Netz (Coils = Ausgaenge, Discrete Inputs =
          Eingaenge). Eigener, kleiner Client - keine Zusatzbibliothek.

Sicherheit: GPIO 18 (Bandrelais) und der Bandpin aus VORSA_BAND_PIN werden nie
belegt. Nichts hiervon ist eine Sicherheitsfunktion (siehe SAFETY.md) - Not-Halt
und Schutztueren gehoeren in die festverdrahtete Sicherheitskette.

Konfiguration: <daten>/eaio.json (wird von der Oberflaeche geschrieben),
Treiber-Vorgabe ueber VORSA_EAIO=sim|gpio|modbus.
"""
from __future__ import annotations

import json
import os
import socket
import struct
import threading
import time
from pathlib import Path
from typing import Callable, Optional

EINGAENGE = ("trigger",)
AUSGAENGE = ("bereit", "ok", "nok", "fehler")
SIGNALE = EINGAENGE + AUSGAENGE

# Vorschlag fuer die GPIO-Belegung (BCM). Frei auf dem Pi 5 und nicht mit
# Kamera (CSI), PCIe, I2C (2/3) oder dem Bandrelais (18) belegt.
GPIO_VORGABE = {"trigger": 17, "bereit": 22, "ok": 23, "nok": 24, "fehler": 25}
MODBUS_VORGABE = {"trigger": 0, "bereit": 0, "ok": 1, "nok": 2, "fehler": 3}
GESPERRT_BASIS = {0, 1, 2, 3, 18}   # ID-EEPROM, I2C, Bandrelais

VORGABE = {
    "treiber": "sim",
    "pins": dict(GPIO_VORGABE),
    "invertiert": {s: False for s in SIGNALE},
    "modus": "puls",          # puls | halten
    "puls_ms": 200,
    "entprell_ms": 20,
    "modbus": {"host": "192.0.2.10", "port": 502, "einheit": 1,
               "adressen": dict(MODBUS_VORGABE), "zyklus_ms": 20},
}


def gesperrte_pins() -> set:
    s = set(GESPERRT_BASIS)
    try:
        s.add(int(os.environ.get("VORSA_BAND_PIN", "18")))
    except ValueError:
        pass
    return s


# ---------------------------------------------------------------- Treiber
class TreiberSim:
    name = "sim"

    def __init__(self, cfg: dict):
        self.ein = {s: False for s in EINGAENGE}
        self.aus = {s: False for s in AUSGAENGE}
        self._cb: Optional[Callable[[str], None]] = None

    def verbinden(self) -> str:
        return ""

    def bei_flanke(self, cb):
        self._cb = cb

    def setze(self, signal: str, wert: bool):
        self.aus[signal] = bool(wert)

    def lies(self, signal: str) -> bool:
        return bool(self.ein.get(signal))

    def sim_flanke(self, signal: str = "trigger"):
        self.ein[signal] = True
        if self._cb:
            self._cb(signal)
        self.ein[signal] = False

    def zu(self):
        pass


class TreiberGpio:
    """gpiozero: DigitalInputDevice / DigitalOutputDevice. Wird erst beim
    Verbinden importiert - auf Rechnern ohne GPIO bleibt das Modul ladbar."""
    name = "gpio"

    def __init__(self, cfg: dict, fabrik=None):
        self.cfg = cfg
        self._fabrik = fabrik           # Tests: gpiozero-Pin-Fabrik (Mock)
        self._ein = {}
        self._aus = {}
        self._cb = None

    def verbinden(self) -> str:
        try:
            import gpiozero  # noqa: F401
            from gpiozero import DigitalInputDevice, DigitalOutputDevice
        except Exception as exc:     # pragma: no cover - je nach System
            return f"gpiozero nicht verfuegbar ({str(exc)[:60]}) - sudo apt install python3-gpiozero"
        pins = self.cfg.get("pins", {})
        inv = self.cfg.get("invertiert", {})
        ent = max(0, int(self.cfg.get("entprell_ms", 20))) / 1000.0
        sperr = gesperrte_pins()
        kw = {"pin_factory": self._fabrik} if self._fabrik else {}
        try:
            for s in EINGAENGE:
                p = pins.get(s)
                if p is None or int(p) in sperr:
                    continue
                d = DigitalInputDevice(int(p), pull_up=bool(inv.get(s)), bounce_time=ent or None, **kw)
                d.when_activated = (lambda sig=s: self._cb and self._cb(sig))
                self._ein[s] = d
            for s in AUSGAENGE:
                p = pins.get(s)
                if p is None or int(p) in sperr:
                    continue
                self._aus[s] = DigitalOutputDevice(int(p), active_high=not inv.get(s), initial_value=False, **kw)
        except Exception as exc:
            self.zu()
            return f"GPIO: {str(exc)[:90]}"
        return ""

    def bei_flanke(self, cb):
        self._cb = cb

    def setze(self, signal: str, wert: bool):
        d = self._aus.get(signal)
        if d is not None:
            d.on() if wert else d.off()

    def lies(self, signal: str) -> bool:
        d = self._ein.get(signal)
        return bool(d.is_active) if d is not None else False

    def zu(self):
        for d in list(self._ein.values()) + list(self._aus.values()):
            try:
                d.close()
            except Exception:
                pass
        self._ein.clear()
        self._aus.clear()


class TreiberModbus:
    """Modbus TCP: Ausgaenge als Coils (FC 5), Eingaenge als Discrete Inputs
    (FC 2), zyklisch gelesen. Steigende Flanke am Trigger -> Rueckruf."""
    name = "modbus"

    def __init__(self, cfg: dict):
        m = cfg.get("modbus", {})
        self.host = str(m.get("host", ""))
        self.port = int(m.get("port", 502))
        self.einheit = int(m.get("einheit", 1))
        self.adr = dict(m.get("adressen", MODBUS_VORGABE))
        self.zyklus = max(5, int(m.get("zyklus_ms", 20))) / 1000.0
        self.inv = cfg.get("invertiert", {})
        self._s: Optional[socket.socket] = None
        self._tid = 0
        self._lock = threading.Lock()
        self._cb = None
        self._lauf = False
        self._letzt = {s: False for s in EINGAENGE}
        self.fehler = ""

    def _anfrage(self, fc: int, daten: bytes) -> bytes:
        with self._lock:
            if self._s is None:
                self._s = socket.create_connection((self.host, self.port), timeout=1.0)
            self._tid = (self._tid + 1) & 0xFFFF
            pdu = bytes([fc]) + daten
            self._s.sendall(struct.pack(">HHHB", self._tid, 0, len(pdu) + 1, self.einheit) + pdu)
            kopf = self._lies(7)
            tid, _, laenge, _ = struct.unpack(">HHHB", kopf)
            rest = self._lies(laenge - 1)
            if rest[0] & 0x80:
                raise IOError(f"Modbus-Ausnahme {rest[1] if len(rest) > 1 else '?'} (FC {fc})")
            return rest[1:]

    def _lies(self, n: int) -> bytes:
        b = b""
        while len(b) < n:
            t = self._s.recv(n - len(b))
            if not t:
                raise IOError("Verbindung geschlossen")
            b += t
        return b

    def verbinden(self) -> str:
        if not self.host:
            return "Modbus: keine Adresse eingetragen"
        try:
            self._lies_eingaenge()
        except Exception as exc:
            self._trennen()
            return f"Modbus {self.host}:{self.port}: {str(exc)[:70]}"
        self._lauf = True
        threading.Thread(target=self._schleife, daemon=True, name="eaio-modbus").start()
        return ""

    def _trennen(self):
        try:
            if self._s:
                self._s.close()
        except Exception:
            pass
        self._s = None

    def _lies_eingaenge(self) -> dict:
        aus = {}
        for s in EINGAENGE:
            a = int(self.adr.get(s, 0))
            r = self._anfrage(2, struct.pack(">HH", a, 1))
            v = bool(r[1] & 1) if len(r) > 1 else False
            aus[s] = (not v) if self.inv.get(s) else v
        return aus

    def _schleife(self):
        while self._lauf:
            try:
                werte = self._lies_eingaenge()
                for s, v in werte.items():
                    if v and not self._letzt[s] and self._cb:
                        self._cb(s)
                    self._letzt[s] = v
                self.fehler = ""
            except Exception as exc:
                self.fehler = f"Modbus: {str(exc)[:70]}"
                self._trennen()
                time.sleep(1.0)
            time.sleep(self.zyklus)

    def bei_flanke(self, cb):
        self._cb = cb

    def setze(self, signal: str, wert: bool):
        a = int(self.adr.get(signal, 0))
        v = (not wert) if self.inv.get(signal) else bool(wert)
        try:
            self._anfrage(5, struct.pack(">HH", a, 0xFF00 if v else 0x0000))
        except Exception as exc:
            self.fehler = f"Modbus: {str(exc)[:70]}"
            self._trennen()

    def lies(self, signal: str) -> bool:
        return bool(self._letzt.get(signal))

    def zu(self):
        self._lauf = False
        self._trennen()


# ---------------------------------------------------------------- Steuerung
class EinAusgaenge:
    """Signallogik ueber dem Treiber: Bereit/Fehler aus dem Anlagenzustand,
    OK/NOK nach jeder Pruefung, Trigger -> Rueckruf."""

    def __init__(self, ordner, ausloesen: Optional[Callable[[], None]] = None):
        self._pfad = Path(ordner) / "eaio.json" if ordner else None
        self._ausloesen = ausloesen
        self._lock = threading.Lock()
        self.cfg = json.loads(json.dumps(VORGABE))
        self._laden()
        env = os.environ.get("VORSA_EAIO", "").lower()
        if env in ("sim", "gpio", "modbus"):
            self.cfg["treiber"] = env
        self.zustand = {s: False for s in SIGNALE}
        self.ereignisse: list = []
        self.zaehler = {"trigger": 0, "ok": 0, "nok": 0}
        self.fehler = ""
        self.treiber = None
        self._puls_bis: dict = {}
        self._starten()

    # -- Konfiguration --------------------------------------------------
    def _laden(self):
        try:
            if self._pfad and self._pfad.exists():
                d = json.loads(self._pfad.read_text(encoding="utf-8"))
                for k in ("treiber", "modus", "puls_ms", "entprell_ms"):
                    if k in d:
                        self.cfg[k] = d[k]
                for k in ("pins", "invertiert"):
                    self.cfg[k].update(d.get(k) or {})
                m = d.get("modbus") or {}
                self.cfg["modbus"].update({k: v for k, v in m.items() if k != "adressen"})
                self.cfg["modbus"]["adressen"].update(m.get("adressen") or {})
        except Exception:
            pass

    def _speichern(self):
        try:
            if self._pfad:
                self._pfad.write_text(json.dumps(self.cfg, indent=1), encoding="utf-8")
        except Exception:
            pass

    def pruefe_cfg(self, cfg: dict) -> str:
        if cfg.get("treiber") not in ("sim", "gpio", "modbus"):
            return "Treiber: sim, gpio oder modbus"
        if cfg.get("modus") not in ("puls", "halten"):
            return "Modus: puls oder halten"
        if cfg["treiber"] == "gpio":
            sperr = gesperrte_pins()
            belegt = {}
            for s, p in cfg.get("pins", {}).items():
                if p is None or p == "":
                    continue
                try:
                    p = int(p)
                except (TypeError, ValueError):
                    return f"{s}: Pin muss eine Zahl sein"
                if not 0 <= p <= 27:
                    return f"{s}: GPIO {p} gibt es nicht (0-27)"
                if p in sperr:
                    return f"{s}: GPIO {p} ist gesperrt (Bandrelais/I2C/EEPROM)"
                if p in belegt:
                    return f"{s}: GPIO {p} schon fuer {belegt[p]} belegt"
                belegt[p] = s
        return ""

    def einstellen(self, neu: dict) -> dict:
        cfg = json.loads(json.dumps(self.cfg))
        for k in ("treiber", "modus"):
            if k in neu:
                cfg[k] = str(neu[k])
        for k in ("puls_ms", "entprell_ms"):
            if k in neu:
                cfg[k] = max(0, min(5000, int(neu[k])))
        for k in ("pins", "invertiert"):
            if isinstance(neu.get(k), dict):
                for s, v in neu[k].items():
                    if s in SIGNALE:
                        cfg[k][s] = (None if v in ("", None) else int(v)) if k == "pins" else bool(v)
        m = neu.get("modbus")
        if isinstance(m, dict):
            for k in ("host",):
                if k in m:
                    cfg["modbus"][k] = str(m[k]).strip()[:64]
            for k in ("port", "einheit", "zyklus_ms"):
                if k in m:
                    cfg["modbus"][k] = int(m[k])
            if isinstance(m.get("adressen"), dict):
                for s, v in m["adressen"].items():
                    if s in SIGNALE:
                        cfg["modbus"]["adressen"][s] = max(0, int(v))
        f = self.pruefe_cfg(cfg)
        if f:
            return {"ok": False, "grund": f, **self.status()}
        with self._lock:
            self.cfg = cfg
            self._speichern()
        self._starten()
        return {"ok": True, **self.status()}

    # -- Treiber --------------------------------------------------------
    def _starten(self):
        with self._lock:
            if self.treiber is not None:
                try:
                    self.treiber.zu()
                except Exception:
                    pass
            art = self.cfg.get("treiber", "sim")
            t = {"gpio": TreiberGpio, "modbus": TreiberModbus}.get(art, TreiberSim)(self.cfg)
            t.bei_flanke(self._flanke)
            f = t.verbinden()
            if f:
                # Ohne Hardware nie stehen bleiben: Simulation, Grund sichtbar.
                self.fehler = f
                t = TreiberSim(self.cfg)
                t.bei_flanke(self._flanke)
            else:
                self.fehler = ""
            self.treiber = t
            self._puls_bis = {}
            for s in AUSGAENGE:
                self.zustand[s] = False
                try:
                    t.setze(s, False)
                except Exception:
                    pass

    def _merke(self, text: str):
        self.ereignisse.insert(0, {"zeit": time.strftime("%H:%M:%S"), "text": text})
        del self.ereignisse[30:]

    def _flanke(self, signal: str):
        if signal != "trigger":
            return
        self.zaehler["trigger"] += 1
        self.zustand["trigger"] = True
        self._merke("Trigger")
        if self._ausloesen:
            try:
                self._ausloesen()
            except Exception as exc:
                self._merke(f"Trigger nicht ausgefuehrt: {str(exc)[:60]}")
        threading.Timer(0.15, lambda: self.zustand.__setitem__("trigger", False)).start()

    def _setze(self, signal: str, wert: bool):
        if self.zustand.get(signal) == bool(wert):
            return
        self.zustand[signal] = bool(wert)
        try:
            self.treiber.setze(signal, bool(wert))
        except Exception as exc:
            self.fehler = str(exc)[:90]

    # -- Anlagenlogik ---------------------------------------------------
    def anlage(self, bereit: bool, stoerung: bool):
        """Einmal je Bild: Bereit/Fehler nachfuehren, Pulse beenden."""
        self._setze("bereit", bool(bereit) and not stoerung)
        self._setze("fehler", bool(stoerung))
        jetzt = time.time()
        for s, bis in list(self._puls_bis.items()):
            if jetzt >= bis:
                self._setze(s, False)
                self._puls_bis.pop(s, None)

    def ergebnis(self, urteil: str):
        """Nach einer Pruefung: gut -> OK, sonst NOK (Puls oder Halten)."""
        gut = urteil == "gut"
        an, aus = ("ok", "nok") if gut else ("nok", "ok")
        self._setze(aus, False)
        self._puls_bis.pop(aus, None)
        self._setze(an, True)
        self.zaehler[an] += 1
        self._merke(("OK" if gut else "NOK") + f" ({urteil})")
        if self.cfg.get("modus") == "puls":
            self._puls_bis[an] = time.time() + max(20, int(self.cfg.get("puls_ms", 200))) / 1000.0
        else:
            self._puls_bis.pop(an, None)

    def test(self, signal: str) -> dict:
        """Verdrahtungstest: Ausgang 1 s an / Trigger simulieren."""
        if signal == "trigger":
            if isinstance(self.treiber, TreiberSim):
                self.treiber.sim_flanke("trigger")
            else:
                self._flanke("trigger")
            return {"ok": True, **self.status()}
        if signal not in AUSGAENGE:
            return {"ok": False, "grund": "unbekanntes Signal", **self.status()}
        self._setze(signal, True)
        self._puls_bis[signal] = time.time() + 1.0
        self._merke(f"Test {signal}")
        return {"ok": True, **self.status()}

    def status(self) -> dict:
        t = self.treiber
        return {
            "treiber": self.cfg.get("treiber"),
            "aktiv": getattr(t, "name", "sim"),
            "simuliert": isinstance(t, TreiberSim),
            "fehler": self.fehler or getattr(t, "fehler", "") or "",
            "zustand": dict(self.zustand),
            "zaehler": dict(self.zaehler),
            "ereignisse": list(self.ereignisse[:12]),
            "cfg": json.loads(json.dumps(self.cfg)),
            "gesperrt": sorted(gesperrte_pins()),
            "eingaenge": list(EINGAENGE), "ausgaenge": list(AUSGAENGE),
        }

    def zu(self):
        try:
            self.treiber.zu()
        except Exception:
            pass
