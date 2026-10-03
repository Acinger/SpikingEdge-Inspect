#!/usr/bin/env python3
"""Bench I1 (1.9.59): digitale Ein-/Ausgaenge ohne Hardware.

  python3 tools/test_eaio.py

1. Simulation: Trigger -> Rueckruf, OK/NOK-Puls, Halten, Bereit/Fehler.
2. GPIO-Treiber gegen ein nachgebautes gpiozero (Pins, Polaritaet, Flanke,
   gesperrte Pins 18/I2C).
3. Modbus-TCP-Treiber gegen einen kleinen Modbus-Server im selben Prozess
   (FC 2 Discrete Inputs, FC 5 Coils, Flanke am Trigger).
"""
import json, socket, struct, sys, tempfile, threading, time, types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
FEHLER = []


def ok(b, t):
    print(("ok   " if b else "FEHL ") + t)
    if not b:
        FEHLER.append(t)


from vorsa import eaio  # noqa: E402

# ---------------------------------------------------------------- 1 Simulation
tmp = tempfile.mkdtemp()
ausgeloest = []
e = eaio.EinAusgaenge(tmp, ausloesen=lambda: ausgeloest.append(time.time()))
ok(e.status()["aktiv"] == "sim" and e.status()["simuliert"], "Vorgabe: Simulation")
e.test("trigger")
ok(len(ausgeloest) == 1 and e.zaehler["trigger"] == 1, "Trigger (Sim) loest Pruefung aus")
e.anlage(bereit=True, stoerung=False)
ok(e.zustand["bereit"] and not e.zustand["fehler"], "Bereit an, Fehler aus")
e.anlage(bereit=True, stoerung=True)
ok(not e.zustand["bereit"] and e.zustand["fehler"], "Stoerung: Bereit aus, Fehler an")
e.anlage(bereit=True, stoerung=False)
e.einstellen({"modus": "puls", "puls_ms": 100})
e.ergebnis("gut")
ok(e.zustand["ok"] and not e.zustand["nok"], "gut -> OK an")
time.sleep(0.15); e.anlage(True, False)
ok(not e.zustand["ok"], "OK-Puls nach 100 ms aus")
e.ergebnis("unbekannt")
ok(e.zustand["nok"] and not e.zustand["ok"], "unbekannt -> NOK")
e.einstellen({"modus": "halten"})
e.ergebnis("ausschuss"); time.sleep(0.3); e.anlage(True, False)
ok(e.zustand["nok"], "Halten: NOK bleibt stehen")
e.ergebnis("gut")
ok(e.zustand["ok"] and not e.zustand["nok"], "Halten: naechstes Ergebnis loest ab")
ok(json.loads((Path(tmp) / "eaio.json").read_text())["modus"] == "halten", "Konfiguration gespeichert")
r = e.einstellen({"treiber": "gpio", "pins": {"ok": 18}})
ok(not r["ok"] and "gesperrt" in r["grund"], "GPIO 18 (Bandrelais) abgelehnt: " + r.get("grund", ""))
r = e.einstellen({"treiber": "gpio", "pins": {"ok": 22, "bereit": 22}})
ok(not r["ok"] and "belegt" in r["grund"], "Doppelbelegung abgelehnt")
r = e.einstellen({"treiber": "gpio"})
ok(r["ok"] and r["simuliert"] and r["fehler"], "GPIO ohne gpiozero: faellt auf Simulation zurueck, Grund sichtbar")
e.einstellen({"treiber": "sim"})

# ---------------------------------------------------------------- 2 GPIO (nachgebaut)
class Geraet:
    alle = {}

    def __init__(self, pin, **kw):
        self.pin, self.kw, self.wert, self.when_activated = pin, kw, False, None
        Geraet.alle[pin] = self

    def on(self): self.wert = True
    def off(self): self.wert = False
    def close(self): Geraet.alle.pop(self.pin, None)

    @property
    def is_active(self): return self.wert


class Aus(Geraet):
    def on(self): self.wert = self.kw.get("active_high", True)
    def off(self): self.wert = not self.kw.get("active_high", True)


gz = types.ModuleType("gpiozero")
gz.DigitalInputDevice = Geraet
gz.DigitalOutputDevice = Aus
sys.modules["gpiozero"] = gz
ausgeloest.clear()
r = e.einstellen({"treiber": "gpio", "pins": dict(eaio.GPIO_VORGABE), "invertiert": {"fehler": True}, "modus": "puls", "puls_ms": 50})
ok(r["ok"] and not r["simuliert"] and r["aktiv"] == "gpio", "GPIO-Treiber aktiv: " + (r.get("fehler") or "ohne Fehler"))
ok(set(Geraet.alle) == {17, 22, 23, 24, 25}, "Pins belegt: " + str(sorted(Geraet.alle)))
ok(18 not in Geraet.alle, "GPIO 18 unberuehrt")
Geraet.alle[17].when_activated()
ok(len(ausgeloest) == 1, "Flanke an GPIO 17 -> Pruefung")
e.ergebnis("gut")
ok(Geraet.alle[23].wert is True, "OK -> GPIO 23 high")
e.anlage(True, True)
ok(Geraet.alle[25].kw.get("active_high") is False and Geraet.alle[25].wert is False, "Fehler invertiert (aktiv low) -> GPIO 25 low")
e.einstellen({"treiber": "sim"})
ok(not Geraet.alle, "Umschalten gibt alle Pins frei")
del sys.modules["gpiozero"]

# ---------------------------------------------------------------- 3 Modbus TCP
class ModbusServer(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.s = socket.socket(); self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.s.bind(("127.0.0.1", 0)); self.s.listen(2)
        self.port = self.s.getsockname()[1]
        self.coils = [False] * 16; self.eingang = [False] * 16
        self.lauf = True

    def run(self):
        while self.lauf:
            try:
                c, _ = self.s.accept()
            except OSError:
                return
            threading.Thread(target=self.bediene, args=(c,), daemon=True).start()

    def bediene(self, c):
        try:
            while True:
                kopf = c.recv(7)
                if len(kopf) < 7:
                    return
                tid, pid, ln, unit = struct.unpack(">HHHB", kopf)
                pdu = c.recv(ln - 1)
                fc = pdu[0]
                if fc == 2:
                    a, n = struct.unpack(">HH", pdu[1:5])
                    bits = 0
                    for i in range(n):
                        bits |= (1 << i) if self.eingang[a + i] else 0
                    antw = bytes([2, 1, bits])
                elif fc == 5:
                    a, v = struct.unpack(">HH", pdu[1:5])
                    self.coils[a] = v == 0xFF00
                    antw = pdu[:5]
                else:
                    antw = bytes([fc | 0x80, 1])
                c.sendall(struct.pack(">HHHB", tid, 0, len(antw) + 1, unit) + antw)
        except OSError:
            return


srv = ModbusServer(); srv.start()
ausgeloest.clear()
r = e.einstellen({"treiber": "modbus", "modus": "halten",
                  "modbus": {"host": "127.0.0.1", "port": srv.port, "einheit": 1, "zyklus_ms": 10}})
ok(r["ok"] and r["aktiv"] == "modbus" and not r["simuliert"], "Modbus verbunden: " + (r.get("fehler") or "ok"))
e.anlage(True, False)
ok(srv.coils[0] is True, "Bereit -> Coil 0")
e.ergebnis("ausschuss")
ok(srv.coils[2] is True and srv.coils[1] is False, "NOK -> Coil 2")
srv.eingang[0] = True; time.sleep(0.1); srv.eingang[0] = False; time.sleep(0.1)
ok(len(ausgeloest) == 1, "Discrete Input 0 steigende Flanke -> Pruefung (einmal)")
time.sleep(0.1)
ok(len(ausgeloest) == 1, "keine Doppel-Ausloesung bei gehaltenem/abgefallenem Eingang")
e.einstellen({"treiber": "modbus", "modbus": {"host": "127.0.0.1", "port": 1}})
st = e.status()
ok(st["simuliert"] and "Modbus" in st["fehler"], "Modbus nicht erreichbar -> Simulation + Grund: " + st["fehler"][:50])
e.zu(); srv.lauf = False; srv.s.close()

print("FEHLER: " + " | ".join(FEHLER) if FEHLER else "EAIO_OK")
sys.exit(1 if FEHLER else 0)
