"""Linien-Modus: Foerderband, Zone, Roboterarm (2026-09-03).

Der Ablauf einer Linie, als Zustandsmaschine:

    BAND     Das Foerderband laeuft, bis ein BENANNTES Objekt stabil in
             der Zone steht.
    ZONE     Band gestoppt, der Arm wird gerufen (HTTP an den externen
             Pi 4 - oder Simulation).
    ARM      Warten, bis die Zone wieder FREI ist. Die Kamera selbst ist
             der Fertig-Sensor: der Arm ist fertig, wenn das Teil weg
             ist. Das haelt das Protokoll zum Arm minimal und macht die
             Simulation ehrlich (Mensch nimmt das Teil, fertig).
    dann wieder BAND - das naechste Teil faehrt vor. Akida klassifiziert
    waehrenddessen ununterbrochen weiter.

Sicherheit vor Tempo:
  - Ein UNBEKANNTES Teil in der Zone stoppt das Band und ruft NICHT den
    Arm - erst wenn ein Mensch es entfernt hat, geht es weiter.
  - Laeuft das Band zu lange, ohne dass etwas die Zone erreicht, stoppt
    es (leere Linie), Meldung statt Endlosschleife.
  - Kommt der Arm nicht (Zone bleibt belegt), gibt es eine Meldung.

Hardware: L298N-Treiber am Pi-GPIO (ENA=PWM, IN1, IN2). Ist kein GPIO
verfuegbar oder Simulation gewuenscht, faellt das Band lautlos auf die
Simulation zurueck: Kommandos werden protokolliert statt geschaltet,
und die Teile schiebt waehrend der Tests eine Hand.
"""

from __future__ import annotations

import time
import threading
from collections import deque


# ----------------------------------------------------------------------
class Foerderband:
    """Band-Simulation - zugleich Basisklasse fuer die echte Hardware."""

    def __init__(self):
        self.laeuft = False
        self.simulation = True
        self.grund = "Simulation (keine Hardware angebunden)"

    def start(self) -> None:
        self.laeuft = True

    def stopp(self) -> None:
        self.laeuft = False

    def schliessen(self) -> None:
        self.stopp()

    def info(self) -> dict:
        return {"laeuft": self.laeuft, "simulation": self.simulation,
                "grund": self.grund}


class BandL298N(Foerderband):
    """Echtes Band am L298N (ENA=PWM fuer Tempo, IN1/IN2 fuer Richtung)."""

    def __init__(self, pin_ena: int = 18, pin_in1: int = 23,
                 pin_in2: int = 24, tempo: float = 0.85):
        super().__init__()
        from gpiozero import Motor, PWMOutputDevice  # wirft, wenn kein GPIO
        self._motor = Motor(forward=pin_in1, backward=pin_in2)
        self._ena = PWMOutputDevice(pin_ena, initial_value=0.0)
        self._tempo = max(0.0, min(1.0, tempo))
        self.simulation = False
        self.grund = f"L298N an ENA={pin_ena} IN1={pin_in1} IN2={pin_in2}"

    def start(self) -> None:
        self._motor.forward()
        self._ena.value = self._tempo
        self.laeuft = True

    def stopp(self) -> None:
        self._ena.value = 0.0
        self._motor.stop()
        self.laeuft = False

    def schliessen(self) -> None:
        self.stopp()
        self._ena.close()
        self._motor.close()


class BandRelais(Foerderband):
    """Echtes Band ueber ein 12-V-Relaismodul (Songle SRD o. ae.).

    Ein GPIO schaltet den Optokoppler-Eingang: nur an/aus, eine
    Richtung, kein Tempo - fuer die Linie genau genug. Der Jumper auf
    dem Modul muss auf L (Low-Trigger) stehen: der Pi zieht IN auf
    Masse, das Relais zieht an (active_high=False). NO als Kontakt
    verwenden - stuerzt der Pi ab, faellt das Relais ab, Band steht."""

    def __init__(self, pin: int = 18):
        super().__init__()
        from gpiozero import OutputDevice   # wirft, wenn kein GPIO
        # 12-V-Modul, JUMPER AUF H (High-Trigger): an = 3,3 V, aus =
        # 0 V. Am Praxisaufbau ermittelt (2026-09-04): der H-Eingang
        # schaltet mit 3,3 V zuverlaessig, waehrend im L-Modus "aus"
        # 12 V braeuchte, die der Pi nicht hat - dort zog das Relais
        # dauerhaft an. Bonus: die Pi-Pins starten beim Booten auf
        # Masse, das Band bleibt also ab der ersten Sekunde aus.
        self._relais = OutputDevice(pin, active_high=True,
                                    initial_value=False)
        self.simulation = False
        self.grund = f"Relais an GPIO {pin} (High-Trigger, Jumper H)"

    def start(self) -> None:
        self._relais.on()
        self.laeuft = True

    def stopp(self) -> None:
        self._relais.off()
        self.laeuft = False

    def schliessen(self) -> None:
        self.stopp()
        try:
            self._relais.close()
        except Exception:
            pass


def band_bauen(pins: dict = None, simulation: bool = False,
               art: str = "l298n") -> Foerderband:
    """Echte Hardware, wenn moeglich - sonst wortlos die Simulation."""
    if not simulation:
        try:
            p = pins or {}
            if str(art).lower() in ("relais", "relay"):
                return BandRelais(pin=int(p.get("ena", 18)))
            return BandL298N(pin_ena=int(p.get("ena", 18)),
                             pin_in1=int(p.get("in1", 23)),
                             pin_in2=int(p.get("in2", 24)))
        except Exception as exc:
            band = Foerderband()
            band.grund = f"Simulation ({str(exc)[:60]})"
            return band
    return Foerderband()


# ----------------------------------------------------------------------
class ArmKlient:
    """Der Roboterarm auf dem externen Pi 4, angesprochen per HTTP.

    Leere URL = Simulation: der Auftrag wird nur protokolliert, das
    Wegnehmen uebernimmt beim Testen eine Hand. Das Fertig-Signal kommt
    in BEIDEN Faellen von der Kamera (Zone wieder frei), nicht vom Arm.
    """

    def __init__(self, url: str = "", timeout_s: float = 3.0):
        self.url = (url or "").rstrip("/")
        self.timeout_s = timeout_s
        self.letzter_auftrag = None
        self.letzter_fehler = None

    @property
    def simulation(self) -> bool:
        return not self.url

    def hole(self, objekt: dict) -> bool:
        """Auftrag 'hol das Teil aus der Zone' - asynchron, blockiert nie."""
        self.letzter_auftrag = {"objekt": objekt, "zeit": time.time()}
        self.letzter_fehler = None
        if self.simulation:
            return True

        def _senden():
            try:
                import json
                import urllib.request
                daten = json.dumps({"auftrag": "holen",
                                    "objekt": objekt}).encode("utf-8")
                anfrage = urllib.request.Request(
                    self.url + "/api/holen", data=daten,
                    headers={"Content-Type": "application/json"})
                urllib.request.urlopen(anfrage, timeout=self.timeout_s)
            except Exception as exc:
                self.letzter_fehler = str(exc)[:90]

        threading.Thread(target=_senden, daemon=True).start()
        return True

    def info(self) -> dict:
        return {"simulation": self.simulation, "url": self.url,
                "fehler": self.letzter_fehler}


# ----------------------------------------------------------------------
class LinienSteuerung:
    """Die Zustandsmaschine der Linie. tick() wird je Kamerabild gerufen.

    ZWEI Zonen (2026-09-03): In der ANLIEFERUNG erkennt die Kamera ein
    neues Teil - erst dann startet das Band. Es laeuft, bis das Teil in
    der ABHOLUNG steht, dort greift der Arm. Ist die Abholung wieder
    frei, wartet die Linie auf die naechste Anlieferung. Beide Zonen
    zieht der Bediener im Kamerabild auf; sie werden gespeichert.
    """

    # Zonen im Ausschnitt, relative Koordinaten 0..1 (x0, y0, x1, y1).
    ANLIEFER = (0.03, 0.30, 0.34, 0.95)
    ABHOL = (0.62, 0.55, 0.95, 0.95)
    STABIL_S = 0.35            # Teil muss so lange stabil stehen (s)
    FREI_S = 0.6               # ... und so lange verschwunden sein (s)
    UNBEK_S = 1.2              # unbekannt so lange in Folge -> Stoerung
    BAND_TIMEOUT_S = 45.0      # Band laeuft, ohne dass die Abholung fuellt
    ARM_TIMEOUT_S = 60.0       # Abholung bleibt belegt -> Arm-Stoerung
    # FLUSS-Takt (1.9.33): Anlieferung meldet "etwas liegt da" nach
    ANLIEFER_S = 0.25          # ... so lange stabil -> Band haelt zum Pruefen
    PRUEF_S = 0.6              # Urteil muss so lange stabil stehen
    PRUEF_TIMEOUT_S = 4.0      # kein stabiles Urteil -> "unbekannt", weiter
    DATEI = "linie.json"

    def __init__(self, band: Foerderband = None, arm: ArmKlient = None,
                 anliefer=None, abhol=None):
        self.band = band or Foerderband()
        self.arm = arm or ArmKlient()
        self.anliefer = tuple(anliefer) if anliefer else self.ANLIEFER
        self.abhol = tuple(abhol) if abhol else self.ABHOL
        # Bildquelle je Zone: "haupt" = Ausschnitt der Hauptkamera,
        # "usb0"/"usb1" = eigener USB-Kamerastream (die ganze
        # Zweitkamera IST dann die Zone).
        self.quellen = {"anliefer": "haupt", "abhol": "haupt"}
        # TAKT (1.9.33): "fluss" = das Band laeuft von sich aus; liegt
        # etwas in der Anlieferung, haelt es kurz zum Pruefen und faehrt
        # weiter, bis ein Teil in der Abholung liegt (Arm) - und haelt
        # dazwischen fuer jedes weitere Teil in der Anlieferung erneut.
        # "einzel" = alter Weg: Band startet erst, wenn die Anlieferung
        # ein benanntes Teil zeigt, und faehrt es bis zur Abholung.
        self.takt = "fluss"
        self.aktiv = False
        self.phase = "aus"
        self.meldung = ""
        self.gefoerdert = 0        # fertig abgeraeumte Teile dieser Sitzung
        self.geprueft = 0          # Urteile in der Anlieferung (Fluss)
        self.pruefungen = deque(maxlen=20)   # {urteil, name, sicher, zeit}
        self.zone_belegt = None    # Abholung: Name | "unbekannt" | None
        self.anliefer_belegt = None
        self._seit = {}            # Zeitstempel je beobachteter Bedingung
        self._phase_seit = time.time()
        self._zonen_objekt = None
        self._anliefer_scharf = True   # Anlieferung darf wieder ausloesen
        self.ereignisse = deque(maxlen=14)

    # ------------------------------------------------------------------
    def _wechsel(self, phase: str, notiz: str = "") -> None:
        self.phase = phase
        # Zeitbasis des laufenden tick() (Pruefstand rechnet mit eigener
        # Uhr), sonst die echte.
        self._phase_seit = getattr(self, "_jetzt", None) or time.time()
        self._seit = {}
        text = f"{time.strftime('%H:%M:%S')}  {phase.upper()}"
        if notiz:
            text += f"  {notiz}"
        self.ereignisse.append(text)

    def aktivieren(self, an: bool) -> None:
        self.aktiv = bool(an)
        self.meldung = ""
        if self.aktiv:
            self._anliefer_scharf = True
            if self.takt == "fluss":
                # Fluss: das Band faehrt los und holt die Teile heran.
                self._wechsel("lauf", "Linie aktiviert (Fluss)")
                self.band.start()
            else:
                # Einzel: das Band startet NICHT blind - erst wenn die
                # Anlieferung ein benanntes Teil zeigt (oder schon eines
                # in der Abholung liegt), setzt sich die Linie in Bewegung.
                self._wechsel("warte", "Linie aktiviert")
        else:
            self.band.stopp()
            self._wechsel("aus", "Linie gestoppt")
        print(f"  Linie: {'AKTIVIERT' if self.aktiv else 'gestoppt'} "
              f"({self.band.info()['grund']})", flush=True)

    # ------------------------------------------------------------------
    def _treffer(self, objekte, zone) -> tuple:
        """(benanntes_objekt|None, unbekanntes_da) fuer eine Zone."""
        x0, y0, x1, y1 = zone
        benannt, unbekannt = None, False
        for o in objekte or []:
            if not (x0 <= o.get("x", -1) <= x1 and y0 <= o.get("y", -1) <= y1):
                continue
            if o.get("name"):
                # Das SICHERSTE benannte Teil zaehlt - nicht das erste
                # der Liste (ein Fehltreffer-Frame nannte sonst die Zone
                # nach dem falschen Teil, 2026-09-03).
                if (benannt is None or float(o.get("sicher") or 0)
                        > float(benannt.get("sicher") or 0)):
                    benannt = o
            else:
                unbekannt = True
        return benannt, unbekannt

    def _steht(self, name: str, bedingung: bool, dauer_s: float,
               jetzt: float) -> bool:
        """True, wenn `bedingung` seit mindestens dauer_s ununterbrochen
        gilt - ZEITbasiert statt Bilder zu zaehlen, damit die Linie bei
        hoher Bildrate schnell reagiert (2026-09-03)."""
        if not bedingung:
            self._seit.pop(name, None)
            return False
        seit = self._seit.setdefault(name, jetzt)
        return (jetzt - seit) >= dauer_s

    def tick(self, objekte, erkennung_ok: bool = True,
             jetzt: float = None) -> None:
        """Ein Kamerabild: objekte = [{name|None, x, y}] relativ 0..1."""
        # Beide Zonen werden IMMER live gespiegelt - auch bei inaktiver
        # Linie zeigt die Anzeige, was gerade wo liegt.
        ab_b, ab_u = self._treffer(objekte, self.abhol)
        an_b, an_u = self._treffer(objekte, self.anliefer)
        self.zone_belegt = ((ab_b or {}).get("name") if ab_b
                            else ("unbekannt" if ab_u else None))
        self.anliefer_belegt = ((an_b or {}).get("name") if an_b
                                else ("unbekannt" if an_u else None))
        if not self.aktiv:
            if self.band.laeuft:      # Sicherheitsnetz
                self.band.stopp()
            return
        if not erkennung_ok:
            # Ohne funktionierende Erkennung faehrt kein Band: sonst
            # schiebt es ein Teil blind ueber die Abholung hinaus.
            if self.band.laeuft:
                self.band.stopp()
            if self.phase in ("warte", "band", "zone") and not self.meldung:
                self.meldung = ("Erkennung pausiert oder gestoert - Band "
                                "sicherheitshalber angehalten.")
            return
        if self.meldung.startswith("Erkennung pausiert"):
            self.meldung = ""
        jetzt = time.time() if jetzt is None else jetzt
        self._jetzt = jetzt
        dauer = jetzt - self._phase_seit

        # Ein unbekanntes Teil in der ABHOLUNG stoppt das Band - der Arm
        # greift nur, was das System sicher benannt hat. ENTPRELLT: beim
        # Hineinlegen ist kurz die Hand im Bild und das Teil wackelt
        # unter die Schwelle - ein einzelner unbekannt-Frame darf keine
        # Stoerung ausloesen (2026-09-03).
        if (self._steht("unbek", ab_u, self.UNBEK_S, jetzt)
                and self.phase in ("warte", "band", "zone", "lauf", "pruefen")):
            if self.band.laeuft:
                self.band.stopp()
            self.meldung = ("Unbekanntes Teil in der Abholzone - Band "
                            "gestoppt. Bitte entfernen, dann laeuft "
                            "die Linie weiter.")
            self._wechsel("stoerung", "unbekanntes Teil in Abholung")
            return

        # Ruhephase nach Arm/Stoerung: Fluss faehrt weiter, Einzel wartet.
        ruhe = "lauf" if self.takt == "fluss" else "warte"

        # Anlieferung wieder "scharf", sobald sie eine Weile leer war -
        # sonst wuerde dasselbe Teil beim Wegfahren ein zweites Mal
        # pruefen lassen.
        an_da = bool(an_b) or an_u
        if not self._anliefer_scharf:
            # Eigener Zeitgeber, unabhaengig von Phasenwechseln (die
            # loeschen _seit): "leer seit" darf ein Arm-Zyklus nicht
            # zuruecksetzen.
            if an_da:
                self._an_leer_seit = None
            else:
                if getattr(self, "_an_leer_seit", None) is None:
                    self._an_leer_seit = jetzt
                if jetzt - self._an_leer_seit >= self.FREI_S:
                    self._anliefer_scharf = True

        if self.phase == "lauf":
            # FLUSS: Band laeuft. Halt (1) fuer ein Teil in der Abholung,
            # (2) fuer ein neues Teil in der Anlieferung - zum Pruefen.
            if not self.band.laeuft:
                self.band.start()
            if self._steht("l_ab", bool(ab_b), self.STABIL_S, jetzt):
                self.band.stopp()
                self._zonen_objekt = dict(ab_b)
                self._wechsel("zone", ab_b.get("name", "?"))
            elif (self._anliefer_scharf
                  and self._steht("l_an", an_da, self.ANLIEFER_S, jetzt)):
                self.band.stopp()
                self._wechsel("pruefen", "Anlieferung: Teil liegt an")
            return

        if self.phase == "pruefen":
            # Band steht, die Kamera urteilt in Ruhe. Stabiler Name ->
            # Urteil buchen und weiterfahren; nichts Stabiles bis zum
            # Timeout -> "unbekannt" buchen und trotzdem weiterfahren
            # (in der Abholung faengt es der Unbekannt-Waechter).
            if self.band.laeuft:
                self.band.stopp()
            fertig = None
            if self._steht("p_name", bool(an_b), self.PRUEF_S, jetzt):
                fertig = {"urteil": "benannt", "name": an_b.get("name", ""),
                          "sicher": float(an_b.get("sicher") or 0.0),
                          "objekt": dict(an_b)}
            elif self._steht("p_leer", not an_da, self.FREI_S, jetzt):
                self._wechsel("lauf", "Anlieferung wieder leer")
                self._anliefer_scharf = True
                return
            elif dauer > self.PRUEF_TIMEOUT_S:
                fertig = {"urteil": "unbekannt", "name": "", "sicher": 0.0,
                          "objekt": {}}
            if fertig:
                fertig["zeit"] = jetzt
                self.pruefungen.append(fertig)
                self.geprueft += 1
                self._anliefer_scharf = False
                self._wechsel("lauf", "geprueft: "
                              + (fertig["name"] or "unbekannt"))
                self.band.start()
            return

        if self.phase == "warte":
            # Liegt schon ein benanntes Teil in der Abholung, geht es
            # direkt zum Arm - sonst startet die Anlieferung das Band.
            if self._steht("w_ab", bool(ab_b), self.STABIL_S, jetzt):
                self._zonen_objekt = dict(ab_b)
                self._wechsel("zone", ab_b.get("name", "?")
                              + " lag schon bereit")
            elif self._steht("w_an", bool(an_b), self.STABIL_S, jetzt):
                self._wechsel("band", "Anlieferung: "
                              + an_b.get("name", "?"))
                self.band.start()
            return

        if self.phase == "band":
            if not self.band.laeuft:
                self.band.start()
            if self._steht("b_ab", bool(ab_b), self.STABIL_S, jetzt):
                self.band.stopp()
                self._zonen_objekt = dict(ab_b)
                self._wechsel("zone", ab_b.get("name", "?"))
            elif not ab_b:
                if dauer > self.BAND_TIMEOUT_S:
                    self.band.stopp()
                    self.meldung = ("Band lief, aber nichts hat die "
                                    "Abholzone erreicht - zurueck auf "
                                    "WARTE. Liegt das Teil noch auf dem "
                                    "Band?")
                    self._wechsel("warte", "Band-Timeout")
            return

        if self.phase == "zone":
            # Band steht, Teil liegt bereit: Arm rufen.
            self.arm.hole(self._zonen_objekt or {})
            self._arm_ruf = jetzt
            self._wechsel("arm", "Arm gerufen"
                          + (" (Simulation)" if self.arm.simulation else ""))
            return

        if self.phase == "arm":
            # Das Zonen-Objekt LIVE nachfuehren: ein Fehltreffer beim
            # Eintreffen soll nicht die ganze Arm-Phase falsch benannt
            # bleiben (2026-09-03).
            if ab_b:
                self._zonen_objekt = dict(ab_b)
            # NACHFASSEN (1.7.8): der Arm-Ruf war ein einmaliger Schuss -
            # schlug das HTTP fehl (Netz weg, Arm lehnte ab, weil er
            # gerade beschaeftigt oder SERVO OFF war), blieb der Auftrag
            # STUMM verloren und die Zone einfach liegen. Jetzt: Fehler
            # als Meldung zeigen und alle 6 s neu rufen, solange das
            # Teil liegt.
            if (self.arm.letzter_fehler and ab_b is not None
                    and jetzt - getattr(self, "_arm_ruf", 0) > 6.0):
                fehler = str(self.arm.letzter_fehler)
                self.meldung = f"Arm-Ruf fehlgeschlagen: {fehler}"[:120]
                self.ereignisse.append(
                    f"{time.strftime('%H:%M:%S')}  ARM  "
                    f"erneut gerufen ({fehler[:40]})")
                self._arm_ruf = jetzt
                self.arm.hole(self._zonen_objekt or {})
            elif (not self.arm.letzter_fehler
                  and str(self.meldung).startswith("Arm-Ruf")):
                self.meldung = ""
            if self._steht("a_frei", ab_b is None, self.FREI_S, jetzt):
                self.gefoerdert += 1
                self.meldung = ""
                self._wechsel(ruhe, "abgeraeumt"
                              + (", weiter" if ruhe == "lauf"
                                 else ", warte auf Anlieferung"))
                if ruhe == "lauf":
                    self.band.start()
            elif ab_b is not None:
                if dauer > self.ARM_TIMEOUT_S and not self.meldung:
                    self.meldung = ("Arm meldet sich nicht - die Abholzone "
                                    "ist seit ueber einer Minute belegt."
                                    + (f" Letzter Fehler: "
                                       f"{self.arm.letzter_fehler}"
                                       if self.arm.letzter_fehler else ""))
            return

        if self.phase == "stoerung":
            # SELBSTHEILUNG: erkennt das System das Teil doch (stabil
            # benannt), geht es normal zum Arm weiter. Sonst: weiter,
            # sobald ein Mensch das unbekannte Teil entfernt hat.
            if self._steht("s_ok", bool(ab_b) and not ab_u,
                           self.STABIL_S, jetzt):
                self.meldung = ""
                self._zonen_objekt = dict(ab_b)
                self._wechsel("zone", "doch erkannt: "
                              + ab_b.get("name", "?"))
            elif self._steht("s_frei", ab_b is None and not ab_u,
                             self.FREI_S, jetzt):
                self.meldung = ""
                self._wechsel(ruhe, "Abholung geraeumt, weiter")
                if ruhe == "lauf":
                    self.band.start()

    # ------------------------------------------------------------------
    def speichern(self, ordner) -> None:
        """Zonen dauerhaft merken (vorsa_daten/linie.json)."""
        import json
        from pathlib import Path
        try:
            (Path(ordner) / self.DATEI).write_text(json.dumps({
                "anliefer": list(self.anliefer),
                "abhol": list(self.abhol),
                "quellen": dict(self.quellen),
                "takt": self.takt,
            }, indent=2), encoding="utf-8")
        except Exception as exc:
            print(f"  Linie: Zonen nicht speicherbar ({exc})", flush=True)

    def laden(self, ordner) -> None:
        import json
        from pathlib import Path
        try:
            d = json.loads((Path(ordner) / self.DATEI)
                           .read_text(encoding="utf-8"))
            if d.get("anliefer"):
                self.anliefer = tuple(d["anliefer"])
            if d.get("abhol"):
                self.abhol = tuple(d["abhol"])
            if d.get("takt") in ("fluss", "einzel"):
                self.takt = d["takt"]
            if isinstance(d.get("quellen"), dict):
                for k in ("anliefer", "abhol"):
                    q = str(d["quellen"].get(k, "haupt"))
                    if (q == "haupt" or q.startswith("usb")
                            or q.startswith("picam")):
                        self.quellen[k] = q
            print(f"  Linie: Zonen geladen (Anlieferung {self.anliefer}, "
                  f"Abholung {self.abhol})", flush=True)
        except FileNotFoundError:
            pass
        except Exception as exc:
            print(f"  Linie: Zonen nicht ladbar ({exc})", flush=True)

    # ------------------------------------------------------------------
    def als_dict(self) -> dict:
        return {
            "aktiv": self.aktiv,
            "phase": self.phase,
            "zone_belegt": self.zone_belegt,
            "anliefer_belegt": self.anliefer_belegt,
            "zone": list(self.abhol),
            "anliefer": list(self.anliefer),
            "quellen": dict(self.quellen),
            "gefoerdert": self.gefoerdert,
            "geprueft": self.geprueft,
            "takt": self.takt,
            "band": self.band.info(),
            "arm": self.arm.info(),
            "objekt": (self._zonen_objekt or {}).get("name"),
            "ereignisse": list(self.ereignisse),
        }
