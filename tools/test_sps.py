#!/usr/bin/env python3
"""Bench I2 (1.9.61): Modbus-TCP-Server fuer die SPS.

  python3 tools/test_sps.py                       # Protokoll gegen Attrappe
  python3 tools/test_sps.py http://127.0.0.1:8765 # zusaetzlich gegen den laufenden Server

Ein kleiner Modbus-Client im Test spricht FC 1/2/3/4/5/6/16 und prueft Register,
Befehle, Ausnahmen, "nur lesen".
"""
import json, socket, struct, sys, time, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vorsa.sps import SpsServer  # noqa: E402

FEHLER = []


def ok(b, t):
    print(("ok   " if b else "FEHL ") + t)
    if not b:
        FEHLER.append(t)


class Client:
    def __init__(self, port):
        self.s = socket.create_connection(("127.0.0.1", port), timeout=2)
        self.t = 0

    def frage(self, pdu):
        self.t += 1
        self.s.sendall(struct.pack(">HHHB", self.t, 0, len(pdu) + 1, 1) + pdu)
        kopf = self.s.recv(7)
        _, _, n, _ = struct.unpack(">HHHB", kopf)
        b = b""
        while len(b) < n - 1:
            b += self.s.recv(n - 1 - len(b))
        return b

    def lies(self, fc, a, n):
        r = self.frage(struct.pack(">BHH", fc, a, n))
        if r[0] & 0x80:
            return ("ausnahme", r[1])
        if fc in (3, 4):
            return list(struct.unpack(">" + "H" * n, r[2:2 + 2 * n]))
        return int.from_bytes(r[2:2 + r[1]], "little")

    def schreib(self, a, v):
        r = self.frage(struct.pack(">BHH", 6, a, v))
        return ("ausnahme", r[1]) if r[0] & 0x80 else "ok"


# ---------------------------------------------------------------- Attrappe
stand = {"bereit": True, "laeuft": False, "stoerung": False, "urteil": "gut", "objekt_id": 2, "konfidenz": 0.873,
         "teile": 1, "gesamt": 70000, "gut": 60, "unbekannt": 7, "ausschuss": 3, "programm": 2, "sequenz": 5, "simuliert": True}
befehle = []
srv = SpsServer(lambda: stand, lambda art, w: befehle.append((art, w)) or f"{art} {w}")
f = srv.starten(0, False) if False else srv.starten(15021, False)
ok(not f and srv.aktiv, "Server startet auf 15021 " + f)
c = Client(15021)
ir = c.lies(4, 0, 13)
ok(ir[0] == 0b101001, f"Status-Bits bereit+OK+simuliert ({ir[0]:06b})")
ok(ir[1] == 1 and ir[2] == 3 and ir[3] == 873 and ir[4] == 1, f"Urteil/Objekt/Konfidenz/Teile {ir[1:5]}")
ok(ir[5] + (ir[6] << 16) == 70000, "Zaehler 32 Bit low/high")
ok(ir[7:11] == [60, 7, 3, 2] and ir[12] == 5, "gut/unbek./Ausschuss/Programm/Sequenz")
ok(c.lies(3, 100, 13)[:5] == ir[:5], "Spiegel ab Halteregister 100")
ok(c.lies(2, 0, 6) == 0b101001, "Discrete Inputs = Status-Bits")
ok(c.schreib(0, 1) == "ok" and befehle[-1] == ("pruefen", 1), "HR0 <- 1: Pruefen")
ok(c.schreib(0, 2) == "ok" and befehle[-1] == ("zaehler_reset", 2), "HR0 <- 2: Zaehler zuruecksetzen")
ok(c.schreib(0, 9) == ("ausnahme", 3), "HR0 <- 9: Ausnahme ILLEGAL DATA VALUE")
ok(c.schreib(1, 3) == "ok" and befehle[-1] == ("programm", 3), "HR1 <- 3: Programm 3")
ok(c.schreib(7, 1) == ("ausnahme", 2), "falsche Adresse: ILLEGAL DATA ADDRESS")
r = c.frage(struct.pack(">BHH", 5, 0, 0xFF00))
ok(r[0] == 5 and befehle[-1] == ("pruefen", 1), "Coil 0 <- 1: Pruefen")
r = c.frage(struct.pack(">BHHB", 16, 0, 1, 2) + struct.pack(">H", 1))
ok(r[0] == 16 and befehle[-1] == ("pruefen", 1), "FC 16 (mehrere Register): Pruefen")
ok(c.lies(4, 10, 10) == ("ausnahme", 2), "Lesen ueber das Ende: Ausnahme")
ok(c.frage(bytes([43, 14, 1, 0]))[0] == 43 | 0x80, "unbekannter Funktionscode: Ausnahme")
c.s.close()
srv.starten(15021, True)
c = Client(15021)
n = len(befehle)
ok(c.schreib(0, 1) == ("ausnahme", 1) and len(befehle) == n, "nur lesen: Befehl abgewiesen")
ok(isinstance(c.lies(4, 0, 2), list), "nur lesen: Lesen geht")
c.s.close(); srv.stoppen()
ok(not srv.aktiv, "Server gestoppt")

# ---------------------------------------------------------------- laufender Server
if len(sys.argv) > 1:
    B = sys.argv[1].rstrip("/")
    def post(p, d):
        q = urllib.request.Request(B + p, data=json.dumps(d).encode(), headers={"content-type": "application/json"})
        return json.loads(urllib.request.urlopen(q, timeout=5).read())
    st = post("/api/sps", {"an": True, "port": 15022, "nur_lesen": False})
    ok(st.get("aktiv") and st.get("port") == 15022, "Server: Modbus eingeschaltet")
    post("/api/betriebsart", {"art": "betreiben"})
    time.sleep(0.5)
    c = Client(15022)
    vor = c.lies(4, 0, 13)
    ok(vor[0] & 1 == 1, "Server: bereit-Bit im Pruefen")
    c.schreib(0, 1); time.sleep(2.5)
    nach = c.lies(4, 0, 13)
    stat = json.loads(urllib.request.urlopen(B + "/api/sps", timeout=5).read())
    profil = json.loads(urllib.request.urlopen(B + "/api/state", timeout=5).read()).get("profil")
    if profil == "stationaer":
        ok(nach[12] == (vor[12] + 1) & 0xFFFF, f"Server: Befehl Pruefen -> neue Ergebnis-Sequenz ({vor[12]} -> {nach[12]}, Urteil {nach[1]})")
    ok("Pruef" in stat.get("letzter_befehl", "") or "abgewiesen" in stat.get("letzter_befehl", ""), "Server: letzter Befehl sichtbar: " + stat.get("letzter_befehl", ""))
    c.s.close()
    post("/api/sps", {"an": False})

print("FEHLER: " + " | ".join(FEHLER) if FEHLER else "SPS_OK")
sys.exit(1 if FEHLER else 0)
