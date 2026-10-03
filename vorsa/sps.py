"""SPS-Anbindung per Modbus TCP (Industrie-Paket I2, Build 1.9.61).

SE Inspect ist hier der Modbus-SERVER (Slave): die SPS liest Ergebnisse und
schreibt Befehle. Reines Python, keine Zusatzbibliothek. Standardmaessig AUS;
Port 1502 (502 braucht root). Modbus kennt keine Anmeldung - deshalb gibt es
"nur lesen", und die Freigabe ist eine bewusste Einstellung des Admins.

Registerkarte (alle Adressen 0-basiert, 16 Bit):

  Eingangsregister (FC 4), gespiegelt in Halteregister 100-115 (FC 3):
    0  Status-Bits   b0 bereit · b1 pruefung laeuft · b2 stoerung
                     b3 letzte OK · b4 letzte NOK · b5 simuliert (kein Chip)
    1  letztes Urteil   0 keins · 1 gut · 2 unbekannt · 3 ausschuss · 4 kein Teil
    2  Objekt-ID + 1 des (ersten) Teils, 0 = keins
    3  Konfidenz in Promille (0-1000)
    4  Teile in der letzten Pruefung
    5/6  Pruefzaehler gesamt (low/high)
    7  gut (low 16)   8 unbekannt (low 16)   9 ausschuss (low 16)
    10 aktives Pruefprogramm (Nr., 0 = keins)
    11 Lebenszaehler (+1 je Sekunde)
    12 Ergebnis-Sequenz (+1 je Pruefung - Flanke fuer die SPS)
  Halteregister (FC 3 lesen, FC 6/16 schreiben):
    0  Befehl     1 = Pruefung ausloesen · 2 = Zaehler zuruecksetzen
                  (wird nach Ausfuehrung wieder 0)
    1  Programm   Nr. schreiben -> Pruefprogramm laden (Nr. wie in der Liste)
  Coils (FC 1 / FC 5):  0 = Pruefung ausloesen (selbstruecksetzend)
  Discrete Inputs (FC 2): 0-5 wie die Status-Bits
"""
from __future__ import annotations

import socket
import struct
import threading
import time
from typing import Callable, Optional

URTEIL_CODE = {"": 0, None: 0, "gut": 1, "unbekannt": 2, "ausschuss": 3, "leer": 4}


class SpsServer:
    def __init__(self, liefern: Callable[[], dict], befehl: Callable[[str, int], str]):
        self._liefern = liefern
        self._befehl = befehl
        self.port = 1502
        self.nur_lesen = False
        self.aktiv = False
        self.fehler = ""
        self.verbindungen = 0
        self.anfragen = 0
        self.letzter_befehl = ""
        self._s: Optional[socket.socket] = None
        self._lauf = False
        self._start = time.time()

    # -- Lebenszyklus -----------------------------------------------------
    def starten(self, port: int, nur_lesen: bool) -> str:
        self.stoppen()
        self.port, self.nur_lesen = int(port), bool(nur_lesen)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("0.0.0.0", self.port))
            s.listen(4)
            s.settimeout(0.5)
        except OSError as exc:
            self.fehler = f"Port {self.port}: {exc.strerror or exc}"
            self.aktiv = False
            return self.fehler
        self._s, self._lauf, self.aktiv, self.fehler = s, True, True, ""
        self._faden = threading.Thread(target=self._annehmen, args=(s,), daemon=True, name="sps-modbus")
        self._faden.start()
        return ""

    def stoppen(self):
        self._lauf = False
        self.aktiv = False
        f = getattr(self, "_faden", None)
        if f is not None and f.is_alive():
            f.join(1.5)          # accept() mit 0,5-s-Takt: erst danach ist der Port frei
        try:
            if self._s:
                self._s.close()
        except Exception:
            pass
        self._s = None

    def _annehmen(self, s):
        while self._lauf and self._s is s:
            try:
                c, _ = s.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            self.verbindungen += 1
            threading.Thread(target=self._bedienen, args=(c,), daemon=True).start()

    # -- Register -----------------------------------------------------------
    def register(self) -> list:
        d = self._liefern() or {}
        bits = (int(bool(d.get("bereit"))) | int(bool(d.get("laeuft"))) << 1 | int(bool(d.get("stoerung"))) << 2
                | int(d.get("urteil") == "gut") << 3 | int(d.get("urteil") in ("unbekannt", "ausschuss", "leer")) << 4
                | int(bool(d.get("simuliert"))) << 5)
        g = int(d.get("gesamt", 0)) & 0xFFFFFFFF
        return [bits, URTEIL_CODE.get(d.get("urteil"), 0), max(0, int(d.get("objekt_id", -1)) + 1) & 0xFFFF,
                max(0, min(1000, int(round(float(d.get("konfidenz") or 0) * 1000)))), int(d.get("teile", 0)) & 0xFFFF,
                g & 0xFFFF, g >> 16, int(d.get("gut", 0)) & 0xFFFF, int(d.get("unbekannt", 0)) & 0xFFFF,
                int(d.get("ausschuss", 0)) & 0xFFFF, int(d.get("programm", 0)) & 0xFFFF,
                int(time.time() - self._start) & 0xFFFF, int(d.get("sequenz", 0)) & 0xFFFF]

    def _schreiben(self, adresse: int, wert: int) -> Optional[int]:
        """Halteregister schreiben -> Modbus-Ausnahmecode oder None."""
        if self.nur_lesen:
            return 1                    # ILLEGAL FUNCTION
        if adresse == 0:
            if wert == 0:
                return None
            art = {1: "pruefen", 2: "zaehler_reset"}.get(wert)
            if not art:
                return 3                # ILLEGAL DATA VALUE
            self.letzter_befehl = self._befehl(art, wert) or art
            return None
        if adresse == 1:
            self.letzter_befehl = self._befehl("programm", wert) or f"programm {wert}"
            return None
        return 2                        # ILLEGAL DATA ADDRESS

    # -- Protokoll ------------------------------------------------------------
    @staticmethod
    def _lies(c, n):
        b = b""
        while len(b) < n:
            t = c.recv(n - len(b))
            if not t:
                raise ConnectionError
            b += t
        return b

    def _bedienen(self, c):
        c.settimeout(60)
        try:
            while self._lauf:
                tid, pid, laenge, einheit = struct.unpack(">HHHB", self._lies(c, 7))
                if laenge < 2 or laenge > 260:
                    return
                pdu = self._lies(c, laenge - 1)
                self.anfragen += 1
                antw = self._pdu(pdu)
                c.sendall(struct.pack(">HHHB", tid, pid, len(antw) + 1, einheit) + antw)
        except (ConnectionError, OSError, struct.error):
            pass
        finally:
            try:
                c.close()
            except Exception:
                pass

    def _pdu(self, pdu: bytes) -> bytes:
        fc = pdu[0]
        aus = lambda code: bytes([fc | 0x80, code])
        try:
            if fc in (3, 4):
                a, n = struct.unpack(">HH", pdu[1:5])
                if not 1 <= n <= 125:
                    return aus(3)
                reg = self.register()
                if fc == 3:
                    feld = {0: 0, 1: 0}
                    werte = []
                    for i in range(a, a + n):
                        if i in feld:
                            werte.append(feld[i])
                        elif 100 <= i < 100 + len(reg):
                            werte.append(reg[i - 100])
                        else:
                            return aus(2)
                else:
                    if a + n > len(reg):
                        return aus(2)
                    werte = reg[a:a + n]
                return bytes([fc, 2 * n]) + struct.pack(">" + "H" * n, *werte)
            if fc in (1, 2):
                a, n = struct.unpack(">HH", pdu[1:5])
                if fc == 1:
                    bits = [0] * 1
                else:
                    r0 = self.register()[0]
                    bits = [(r0 >> i) & 1 for i in range(6)]
                if a + n > len(bits) or n < 1:
                    return aus(2)
                wert = 0
                for i in range(n):
                    wert |= bits[a + i] << i
                anz = (n + 7) // 8
                return bytes([fc, anz]) + wert.to_bytes(anz, "little")
            if fc == 5:
                a, v = struct.unpack(">HH", pdu[1:5])
                if a != 0:
                    return aus(2)
                if v == 0xFF00:
                    f = self._schreiben(0, 1)
                    if f:
                        return aus(f)
                return pdu[:5]
            if fc == 6:
                a, v = struct.unpack(">HH", pdu[1:5])
                f = self._schreiben(a, v)
                return aus(f) if f else pdu[:5]
            if fc == 16:
                a, n, _ = struct.unpack(">HHB", pdu[1:6])
                werte = struct.unpack(">" + "H" * n, pdu[6:6 + 2 * n])
                for i, v in enumerate(werte):
                    f = self._schreiben(a + i, v)
                    if f:
                        return aus(f)
                return pdu[:5]
            return aus(1)
        except struct.error:
            return aus(3)

    def status(self) -> dict:
        return {"aktiv": self.aktiv, "port": self.port, "nur_lesen": self.nur_lesen, "fehler": self.fehler,
                "verbindungen": self.verbindungen, "anfragen": self.anfragen, "letzter_befehl": self.letzter_befehl}
