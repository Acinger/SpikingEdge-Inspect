"""Serieller Arduino-Arm (RAMPS-Sketch) - eingebaut in VORSA INSPECT.

Der 3-Achs-Stepperarm haengt per USB direkt am Pi 5. Sein Sketch
(Selbstauskunft per "help") versteht:

    g1 x <abs> y <abs> z <abs>     absolute Fahrt in Schritten, BUSY/DONE
    mv <x|y|z> <+|-> <steps>       relatives Joggen
    home <x|y|z|all>               Referenzfahrt auf die MAX-Endschalter
    enall <0|1>                    alle Motoren an/aus
    pump <0|1>                     Saugpumpe an D10 (echte Hardware)
    spd <us>                       Schritttakt (kleiner = schneller)
    pos                            "POS x=.. y=.. z=.. pump=.."

Aktiviert mit VORSA_ARM=uno beim Serverstart (Portwahl ueber
VORSA_ARM_PORT, Standard /dev/ttyACM0). Punkte und die Sequenz "Holen"
liegen in vorsa_daten/. Die Linie ruft den Arm INTERN - ohne HTTP.
"""
from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path

ACHSEN = ("x", "y", "z")


class ArmUno:
    """Treiber + Zustandsspiegel + Punkte/Sequenz-Verwaltung."""

    def __init__(self, geraet: str = "/dev/ttyACM0", ordner=None):
        self.geraet = geraet
        self.ordner = Path(ordner or ".")
        self.ordner.mkdir(parents=True, exist_ok=True)
        self._punkte_datei = self.ordner / "arm_punkte.json"
        self._programm_datei = self.ordner / "arm_programme.json"
        self._ser = None
        self._lock = threading.Lock()
        self.verbunden = False
        self.pos = {a: 0 for a in ACHSEN}
        self.pumpe = False
        self.motoren = False
        self.gehomed = False
        self.busy = False
        self.fehler = ""
        self.programm_laeuft = False
        self.programm_schritt = 0
        self.programm_gesamt = 0
        self.programm_durchlauf = 0
        self.programm_durchlaeufe = 0
        self.stop_wunsch = False
        self.ereignisse = []
        self.spd_us = 1000

    # -- Protokoll -----------------------------------------------------
    def log(self, text):
        self.ereignisse.append(time.strftime("%H:%M:%S  ")
                               + str(text)[:120])
        del self.ereignisse[:-40]

    def _lade(self, pfad, standard):
        try:
            return json.loads(pfad.read_text(encoding="utf-8"))
        except Exception:
            return standard

    def punkte(self) -> dict:
        return self._lade(self._punkte_datei, {})

    def programme(self) -> dict:
        return self._lade(self._programm_datei, {})

    # -- Verbindung ----------------------------------------------------
    def verbinde(self) -> bool:
        with self._lock:
            if self._ser is not None:
                return True
            try:
                import serial
                self._ser = serial.Serial(self.geraet, 115200,
                                          timeout=0.2)
            except Exception as exc:
                self.fehler = f"{self.geraet}: {exc}"[:120]
                return False
            time.sleep(2.5)                 # Arduino resettet beim Oeffnen
            banner = self._ser.read(2000).decode(errors="replace")
            self.verbunden = True
            self.fehler = ""
            erste = banner.splitlines()[0] if banner else ""
            self.log("Arduino verbunden: " + erste)
            return True

    def _trenne(self, exc):
        try:
            self._ser.close()
        except Exception:
            pass
        self._ser = None
        self.verbunden = False
        self.motoren = False
        self.gehomed = False
        self.fehler = str(exc)[:120]

    def _sende(self, cmd: str, timeout_s: float = 4.0,
               ende=("DONE", "ERR", "OK", "POS", "PONG")):
        if not self.verbinde():
            raise RuntimeError(self.fehler or "Arduino nicht erreichbar")
        with self._lock:
            try:
                self._ser.reset_input_buffer()
                self._ser.write((cmd + "\n").encode())
            except Exception as exc:
                self._trenne(exc)
                raise RuntimeError(f"Senden: {exc}")
            zeilen, rest, bis = [], b"", time.time() + timeout_s
            while time.time() < bis:
                try:
                    rest += self._ser.read(256)
                except Exception as exc:
                    self._trenne(exc)
                    raise RuntimeError(f"Lesen: {exc}")
                while b"\n" in rest:
                    zeile, rest = rest.split(b"\n", 1)
                    z = zeile.decode(errors="replace").strip()
                    if z:
                        zeilen.append(z)
                if any(z.split(" ")[0] in ende for z in zeilen):
                    break
            return zeilen

    # -- Grundbefehle --------------------------------------------------
    def pos_lesen(self):
        for z in self._sende("pos", 2.0):
            m = re.search(r"x=(-?\d+)\s+y=(-?\d+)\s+z=(-?\d+)"
                          r"(?:\s+pump=(\d+))?", z)
            if m:
                self.pos = {"x": int(m.group(1)), "y": int(m.group(2)),
                            "z": int(m.group(3))}
                if m.group(4) is not None:
                    self.pumpe = m.group(4) != "0"
        return self.pos

    def _bewegung(self, cmd, timeout_s):
        if self.busy:
            raise RuntimeError("Arm ist beschaeftigt")
        self.busy = True
        try:
            zeilen = self._sende(cmd, timeout_s, ende=("DONE", "ERR"))
            for z in zeilen:
                if z.startswith("ERR"):
                    raise RuntimeError(z)
            if not any(z.startswith("DONE") for z in zeilen):
                raise RuntimeError("keine DONE-Meldung (Timeout?)")
        finally:
            self.busy = False
            try:
                self.pos_lesen()
            except Exception:
                pass

    def motoren_an(self, an: bool):
        self._sende(f"enall {1 if an else 0}", 3.0)
        self.motoren = an
        if not an:
            self.gehomed = False        # stromlos = Lage nicht sicher
        self.log("Motoren " + ("AN" if an else "AUS"))

    def home(self):
        """Referenzfahrt der FIRMWARE (bewaehrter Weg): 'home all'
        faehrt die Achsen auf ihre Endschalter und setzt POS=0.
        Die Richtung steckt in der Firmware - eine Aenderung braucht
        einen neuen Sketch (arduino-sketch/VorsaArm liegt bereit)."""
        if not self.motoren:
            self.motoren_an(True)
        self.log("Referenzfahrt startet (Firmware 'home all') ...")
        self._bewegung("home all", 180.0)
        self.gehomed = True
        self.log("Referenzfahrt fertig")

    def home_start(self):
        """Referenzfahrt im Hintergrund - die Oberflaeche bleibt
        fluessig und zeigt den Fortschritt im Protokoll. Fehler
        landen sichtbar im Fehlerfeld statt in einem stummen
        HTTP-Timeout (2026-09-05)."""
        if self.busy or self.programm_laeuft:
            raise RuntimeError("Arm ist beschaeftigt")

        def lauf():
            try:
                self.fehler = ""
                self.home()
            except Exception as exc:
                self.fehler = f"Home: {exc}"[:120]
                self.log(self.fehler)
        threading.Thread(target=lauf, daemon=True).start()

    def jog(self, achse, schritte):
        if achse not in ACHSEN:
            raise RuntimeError("Achse?")
        if not self.motoren:
            raise RuntimeError("Motoren sind aus")
        richtung = "+" if schritte >= 0 else "-"
        self._bewegung(f"mv {achse} {richtung} {abs(int(schritte))}",
                       60.0)

    def fahre(self, ziel: dict):
        """Ziel in NULLPUNKT-Koordinaten (0 = am Endschalter)."""
        if not self.motoren:
            raise RuntimeError("Motoren sind aus")
        if not self.gehomed:
            raise RuntimeError("Erst Referenzfahrt (HOME)")
        teile = " ".join(f"{a} {int(ziel[a])}" for a in ACHSEN
                         if a in ziel)
        self._bewegung("g1 " + teile, 120.0)

    def pumpe_setzen(self, an: bool):
        self._sende(f"pump {1 if an else 0}", 3.0)
        self.pumpe = an
        self.log("Pumpe " + ("AN" if an else "AUS"))

    def tempo(self, us: int):
        us = max(300, min(5000, int(us)))
        self._sende(f"spd {us}", 3.0)
        self.spd_us = us

    def stop(self):
        self.stop_wunsch = True
        try:
            self.motoren_an(False)
        except Exception:
            pass
        try:
            self.pumpe_setzen(False)
        except Exception:
            pass
        self.log("STOP")

    # -- Punkte + Sequenz ----------------------------------------------
    def punkt_merken(self, name: str) -> str:
        punkte = self.punkte()
        name = (name or "").strip() or "P" + str(len(punkte) + 1)
        self.pos_lesen()
        punkte[name] = dict(self.pos)
        self._punkte_datei.write_text(json.dumps(punkte, indent=2),
                                      encoding="utf-8")
        self.log("Punkt gemerkt: " + name)
        return name

    def punkt_weg(self, name: str):
        punkte = self.punkte()
        punkte.pop(name, None)
        self._punkte_datei.write_text(json.dumps(punkte, indent=2),
                                      encoding="utf-8")

    def punkt_geh(self, name: str):
        punkte = self.punkte()
        if name not in punkte:
            raise RuntimeError("Punkt fehlt")
        self.fahre(punkte[name])

    def programm_speichern(self, name: str, schritte: list):
        programme = self.programme()
        programme[name or "Holen"] = {"steps": list(schritte or [])}
        self._programm_datei.write_text(
            json.dumps(programme, indent=2), encoding="utf-8")

    def _schritte_abspielen(self, schritte):
        punkte = self.punkte()
        for i, st in enumerate(schritte):
            if self.stop_wunsch:
                return
            self.programm_schritt = i + 1
            typ = st.get("type", "point")
            if typ == "wait":
                time.sleep(max(0, int(st.get("ms", 0))) / 1000.0)
            elif typ == "pumpe":
                self.pumpe_setzen(bool(st.get("an")))
            elif typ == "point":
                pn = st.get("point")
                if pn not in punkte:
                    raise RuntimeError(f"Punkt {pn} fehlt")
                self.fahre(punkte[pn])

    def _programm_lauf(self, schritte, name, durchlaeufe):
        """Jeder Durchlauf beginnt mit der Referenzfahrt (definierter
        Ausgangspunkt). Geht etwas schief: Pumpe aus, neu
        referenzieren, Sequenz von vorn - maximal 3 Anlaeufe je
        Durchlauf, dann Abbruch mit Fehlermeldung."""
        try:
            lauf = 0
            while lauf < durchlaeufe and not self.stop_wunsch:
                lauf += 1
                self.programm_durchlauf = lauf
                versuch = 0
                while True:
                    versuch += 1
                    try:
                        self.gehomed = False        # Start = Referenz
                        self.home()
                        self._schritte_abspielen(schritte)
                        break
                    except Exception as exc:
                        self.log(f"Lauf {lauf}, Anlauf {versuch} "
                                 f"gescheitert: {exc}"[:110])
                        if self.stop_wunsch or versuch >= 3:
                            raise
                        try:
                            self.pumpe_setzen(False)
                        except Exception:
                            pass
                        self.log("Selbstheilung: neu referenzieren, "
                                 "Sequenz von vorne")
            if not self.stop_wunsch:
                self.log(f"Programm '{name}' fertig "
                         f"({lauf} Durchlaeufe)")
        except Exception as exc:
            self.fehler = f"Programm: {exc}"[:120]
            self.log(self.fehler)
            try:
                self.pumpe_setzen(False)
            except Exception:
                pass
        finally:
            self.programm_laeuft = False
            self.programm_schritt = 0
            self.programm_gesamt = 0
            self.programm_durchlauf = 0
            self.programm_durchlaeufe = 0
            self.stop_wunsch = False

    def programm_start(self, name: str = "Holen",
                       durchlaeufe: int = 1):
        schritte = (self.programme().get(name) or {}).get("steps") or []
        if not schritte:
            raise RuntimeError(f"Programm '{name}' ist leer")
        if self.programm_laeuft or self.busy:
            raise RuntimeError("Arm ist beschaeftigt")
        durchlaeufe = max(1, min(999, int(durchlaeufe)))
        self.stop_wunsch = False
        self.fehler = ""
        self.programm_laeuft = True
        self.programm_gesamt = len(schritte)
        self.programm_durchlaeufe = durchlaeufe
        self.programm_durchlauf = 0
        threading.Thread(target=self._programm_lauf,
                         args=(schritte, name, durchlaeufe),
                         daemon=True).start()

    def zustand(self) -> dict:
        return {
            "vorhanden": True,
            "verbunden": self.verbunden,
            "geraet": self.geraet,
            "pos": self.pos,
            "pumpe": self.pumpe,
            "motoren": self.motoren,
            "gehomed": self.gehomed,
            "busy": self.busy or self.programm_laeuft,
            "programm_laeuft": self.programm_laeuft,
            "programm_schritt": self.programm_schritt,
            "programm_gesamt": self.programm_gesamt,
            "programm_durchlauf": self.programm_durchlauf,
            "programm_durchlaeufe": self.programm_durchlaeufe,
            "fehler": self.fehler,
            "spd_us": self.spd_us,
            "ereignisse": self.ereignisse[-14:],
            "punkte": self.punkte(),
            "programm": (self.programme().get("Holen")
                         or {}).get("steps") or [],
        }


class ArmIntern:
    """ArmKlient-Ersatz fuer die Linie: ruft den USB-Arm direkt.

    hole() startet das Programm 'Holen' im Hintergrund. Schlaegt das
    fehl (Motoren aus, nicht referenziert, beschaeftigt), landet der
    Grund in letzter_fehler - die Linie zeigt ihn an und fasst nach.
    """

    def __init__(self, arm: ArmUno):
        self.arm = arm
        self.letzter_fehler = None
        self.simulation = False

    def hole(self, objekt: dict) -> bool:
        name = (objekt or {}).get("name") or "Teil"
        self.letzter_fehler = None
        schritte = (self.arm.programme().get("Holen")
                    or {}).get("steps") or []
        if not schritte:
            self.arm.log(f"INSPECT ({name}): Programm 'Holen' fehlt "
                         "- nur quittiert")
            return True
        try:
            self.arm.programm_start("Holen")
            self.arm.log(f"INSPECT-Auftrag: {name} -> 'Holen'")
        except Exception as exc:
            self.letzter_fehler = str(exc)[:90]
        return True

    def info(self) -> dict:
        return {"simulation": False,
                "url": f"USB {self.arm.geraet}",
                "fehler": self.letzter_fehler or self.arm.fehler
                or None}
