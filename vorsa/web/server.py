"""HTTP-Server der Weboberflaeche - nur Standardbibliothek.

Bildquelle ist entweder eine Kamera oder ein synthetischer Generator. Der
synthetische Weg ist kein Spielzeug: er erlaubt, die gesamte Oberflaeche ohne
Anlage zu pruefen, und war schon beim Aufbau der einzige Weg, ueberhaupt
etwas zu sehen - an einem Pi ohne Bildschirm.
"""
from __future__ import annotations

# Picamera2 ZUERST importieren - vor cv2, TensorFlow und allem anderen.
# Solo importiert lief es; im Server, wo cv2 und TF schon geladen waren, kam
# "numpy.dtype size changed". Die kompilierten Module beissen sich je nach
# Ladereihenfolge - also laden wir in der Reihenfolge, die nachweislich geht,
# und merken uns andernfalls den VOLLEN Grund statt 60 Zeichen davon.
try:
    from picamera2 import Picamera2 as _PICAM2_KLASSE
    _PICAM2_FEHLER = ""
except Exception as _exc:                      # pragma: no cover
    _PICAM2_KLASSE = None
    _PICAM2_FEHLER = f"{type(_exc).__name__}: {_exc}"

import json
import mimetypes
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import parse_qs, urlparse

import cv2
import numpy as np

from .. import config
from ..edge_learn import EdgeLerner
from ..web.state import Zustand

HIER = Path(__file__).resolve().parent
STATISCH = HIER / "static"

# Stand des M3-Detektors (Stufe 2) - fuers Kartenfenster und die Diagnose.
_DETEKTOR: dict = {"aktiv": False}

# Stand des Servers. Steht beim Start im Log UND unten rechts in der
# Oberflaeche. Wir haben mehrfach Fehler gesucht, die in Wahrheit nur alte
# Dateien auf dem Pi waren - mit dieser Zeile ist das in zwei Sekunden
# geklaert statt in zwei Runden.
# Bei JEDER Aenderung erhoehen. Zuletzt war tagelang dieselbe Nummer im
# Umlauf, und ob der Pi neuen oder alten Code fuhr, war nicht feststellbar.
BUILD = "1.0.0-alpha.2"


# ----------------------------------------------------------------------
# Kameraeinstellungen. Nicht jede USB-Kamera kennt jede davon - welche
# tatsaechlich wirken, wird beim Start durch Setzen und Zurueeklesen ermittelt
# statt aus einer Liste angenommen.
KAMERA_EIGENSCHAFTEN = {
    "autofokus":          ("CAP_PROP_AUTOFOCUS", True),
    "fokus":              ("CAP_PROP_FOCUS", False),
    "auto_weissabgleich": ("CAP_PROP_AUTO_WB", True),
    "weissabgleich":      ("CAP_PROP_WB_TEMPERATURE", False),
    "auto_belichtung":    ("CAP_PROP_AUTO_EXPOSURE", True),
    "belichtung":         ("CAP_PROP_EXPOSURE", False),
    "helligkeit":         ("CAP_PROP_BRIGHTNESS", False),
    "kontrast":           ("CAP_PROP_CONTRAST", False),
    "saettigung":         ("CAP_PROP_SATURATION", False),
    "verstaerkung":       ("CAP_PROP_GAIN", False),
}


class PiBildquelle:
    """Pi Camera Module 3 ueber Picamera2 - dieselbe Schnittstelle wie
    Bildquelle, damit Verarbeitung und Oberflaeche nichts davon merken.

    Das Modul 3 ist KEINE USB-Webcam: cv2.VideoCapture kommt an libcamera
    nicht vorbei. Dafuer gibt es echte Gegenwerte fuer alles, was die
    Oberflaeche anbietet - Autofokus mit Linsenposition, Belichtung,
    Weissabgleich ueber Farbverstaerkungen.

    Die Reglerwerte bleiben in den UI-Einheiten der USB-Kamera (Fokus 0-255,
    Belichtung -13..0 usw.) und werden hier auf die libcamera-Bereiche
    umgerechnet. So funktionieren Presets und Drift-Vergleich unveraendert.
    """

    AUFLOESUNG = (2304, 1296)      # 16:9, gebinnt, bis 30 Bilder je Sekunde

    def __init__(self, groesse: int = 512):
        if _PICAM2_KLASSE is None:
            raise RuntimeError(_PICAM2_FEHLER or "picamera2 nicht installiert")
        Picamera2 = _PICAM2_KLASSE
        self.groesse = groesse
        self.synthetisch = False
        self.kamera_nr = 0
        self.hinweis = ""
        self._cap_lock = threading.Lock()
        self._fehlschlaege = 0
        self._letztes = None
        self._Picamera2 = Picamera2
        self._starten()
        # UI-Einheiten der Ausgangswerte; "zurueck" stellt genau die her.
        self._werte = {"autofokus": 1.0, "auto_belichtung": 3.0,
                       "auto_weissabgleich": 1.0, "fokus": 128.0,
                       "belichtung": -8.0, "helligkeit": 128.0,
                       "kontrast": 128.0, "saettigung": 128.0,
                       "weissabgleich": 4500.0}
        self.start_werte = dict(self._werte)
        self.koennen = {n: v for n, v in self._werte.items()}
        self.cap = self._picam                 # "lebt"-Kennzeichen

    def _starten(self) -> None:
        self._picam = self._Picamera2()
        konf = self._picam.create_video_configuration(
            main={"size": self.AUFLOESUNG, "format": "RGB888"},
            controls={"FrameRate": 30})
        self._picam.configure(konf)
        self._picam.start()
        self.aufloesung = self.AUFLOESUNG
        self._setze_rohe({"AfMode": 2})        # durchgehender Autofokus
        print(f"  Pi-Kameramodul: {self.AUFLOESUNG[0]}x{self.AUFLOESUNG[1]} px, "
              "Autofokus an", flush=True)

    # -- Umrechnung UI-Einheit -> libcamera ---------------------------
    def _rohe_controls(self, name: str, wert: float) -> dict:
        if name == "autofokus":
            return {"AfMode": 2 if wert > 0 else 0}
        if name == "auto_belichtung":
            return {"AeEnable": wert > 1.5}    # V4L2-Brauch: 3=auto, 1=manuell
        if name == "auto_weissabgleich":
            return {"AwbEnable": wert > 0}
        if name == "fokus":                    # 0..255 -> Linse 0..10 Dioptrien
            return {"AfMode": 0, "LensPosition": max(0.0, wert) / 25.5}
        if name == "belichtung":               # -13..0 -> 2^x Sekunden
            us = int(1e6 * (2.0 ** float(wert)))
            return {"AeEnable": False,
                    "ExposureTime": int(min(200000, max(100, us)))}
        if name == "helligkeit":               # 0..255 -> -1..1
            return {"Brightness": (wert - 128.0) / 128.0}
        if name == "kontrast":                 # 0..255 -> 0..2
            return {"Contrast": max(0.0, wert / 128.0)}
        if name == "saettigung":
            return {"Saturation": max(0.0, wert / 128.0)}
        if name == "weissabgleich":            # 2000..7500 K -> Farbgewinne
            t = min(7500.0, max(2000.0, wert))
            rot = 2.8 - (t - 2000.0) / 5500.0 * 1.6
            blau = 1.2 + (t - 2000.0) / 5500.0 * 1.4
            return {"AwbEnable": False, "ColourGains": (rot, blau)}
        return {}

    def _setze_rohe(self, controls: dict) -> None:
        with self._cap_lock:
            self._picam.set_controls(controls)

    def steuere(self, controls: dict) -> dict:
        """Rohe libcamera-Controls setzen (fuer den Feed-Kamera-Knopf).
        Bewusst tolerant: ein nicht unterstuetztes Control soll die
        Kamera nie zum Absturz bringen."""
        try:
            self._setze_rohe(dict(controls))
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "grund": str(exc)[:80]}

    def metadaten(self) -> dict:
        """Aktuelle Belichtungszeit/Gain der Kamera (fuer Licht +/-)."""
        try:
            with self._cap_lock:
                return dict(self._picam.capture_metadata())
        except Exception:
            return {}

    # -- Schnittstelle wie Bildquelle ---------------------------------
    def lies_einstellungen(self, hoechstalter: float = 2.0) -> dict:
        return dict(self._werte)

    def setze(self, name: str, wert: float) -> dict:
        if name not in self._werte:
            return {"ok": False, "grund": "nicht verfuegbar"}
        try:
            self._setze_rohe(self._rohe_controls(name, float(wert)))
        except Exception as exc:
            return {"ok": False, "grund": str(exc)[:80]}
        self._werte[name] = float(wert)
        return {"ok": True, "gesetzt": float(wert), "gelesen": float(wert),
                "uebernommen": True}

    def einfrieren(self) -> dict:
        try:
            # Linsenposition der Automatik festhalten, dann alles manuell.
            with self._cap_lock:
                md = self._picam.capture_metadata()
            linse = float(md.get("LensPosition", 5.0))
            self._setze_rohe({"AeEnable": False, "AwbEnable": False,
                              "AfMode": 0, "LensPosition": linse})
            self._werte.update(autofokus=0.0, auto_belichtung=1.0,
                               auto_weissabgleich=0.0,
                               fokus=round(linse * 25.5, 1))
            return {"ok": True, "werte": self.lies_einstellungen()}
        except Exception as exc:
            return {"ok": False, "grund": str(exc)[:80]}

    def automatik_an(self) -> dict:
        try:
            self._setze_rohe({"AeEnable": True, "AwbEnable": True, "AfMode": 2})
            self._werte.update(autofokus=1.0, auto_belichtung=3.0,
                               auto_weissabgleich=1.0)
            return {"ok": True, "werte": self.lies_einstellungen()}
        except Exception as exc:
            return {"ok": False, "grund": str(exc)[:80]}

    def zuruecksetzen(self) -> dict:
        for name, wert in self.start_werte.items():
            self.setze(name, wert)
        return {"ok": True, "zurueckgesetzt": sorted(self.start_werte),
                "nicht_uebernommen": [], "werte": self.lies_einstellungen()}

    def neu_oeffnen(self) -> dict:
        try:
            with self._cap_lock:
                self._picam.stop()
                self._picam.close()
        except Exception:
            pass
        try:
            self._starten()
            self.cap = self._picam
            self._fehlschlaege = 0
            self.hinweis = ""
            return {"ok": True, "werte": self.lies_einstellungen()}
        except Exception as exc:
            self.cap = None
            self.hinweis = f"Pi-Kamera liess sich nicht neu oeffnen: {str(exc)[:70]}"
            return {"ok": False, "grund": self.hinweis}

    def lies(self) -> np.ndarray:
        try:
            with self._cap_lock:
                # Picamera2 nennt das Format RGB888, liefert im Speicher aber
                # B,G,R - genau die Ordnung, die OpenCV erwartet. Bekannt und
                # dokumentiert, trotzdem jedes Mal eine Falle.
                bild = self._picam.capture_array()
            self._fehlschlaege = 0
            self._letztes = bild
            return bild
        except Exception:
            self._fehlschlaege += 1
            if self._fehlschlaege >= 10:
                self._fehlschlaege = 0
                self.neu_oeffnen()
            if self._letztes is not None:
                time.sleep(0.05)
                return self._letztes
            leer = np.zeros((480, 640, 3), np.uint8)
            cv2.putText(leer, "KEIN KAMERABILD", (150, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 229, 255), 2,
                        cv2.LINE_AA)
            time.sleep(0.1)
            return leer

    def schliesse(self) -> None:
        try:
            with self._cap_lock:
                self._picam.stop()
                self._picam.close()
        except Exception:
            pass
        self.cap = None


class Bildquelle:
    """Kamera oder synthetische Szenen - dieselbe Schnittstelle."""

    def __init__(self, kamera: int = 0, groesse: int = 512,
                 synthetisch: bool = False):
        self.groesse = groesse
        self.synthetisch = synthetisch
        self.kamera_nr = kamera
        self.start_werte: dict = {}
        self.aufloesung = (0, 0)
        self.cap = None
        self.hinweis = ""
        self._zaehler = 0
        self.koennen: dict = {}     # was diese Kamera tatsaechlich kann
        # cv2.VideoCapture ist NICHT threadsicher. Ohne diese Sperre greifen
        # der Bild-Thread (read) und der HTTP-Thread (set/get beim Verstellen
        # eines Reglers) gleichzeitig zu - dann liefert read() einmal False.
        self._cap_lock = threading.Lock()
        self._fehlschlaege = 0
        self._letztes = None
        self._werte_cache: dict = {}
        self._werte_zeit = 0.0

        if not synthetisch:
            self.cap = cv2.VideoCapture(kamera)
            if self.cap.isOpened():
                self._aufloesung_setzen()
            if not self.cap.isOpened():
                self.hinweis = (f"Kamera {kamera} nicht verfuegbar - "
                                "synthetische Bilder aktiv")
                self.cap.release()
                self.cap = None
                self.synthetisch = True
            else:
                self.koennen = self._pruefe_eigenschaften()
                # Die Werte, mit denen die Kamera geoeffnet wurde. Nur so
                # gibt es spaeter ein "zurueck" - ohne sie bleibt nur Raten,
                # was vorher eingestellt war.
                self.start_werte = dict(self.koennen)

    # ------------------------------------------------------------------
    def _aufloesung_setzen(self) -> None:
        """Volle Kameraaufloesung anfordern statt der Voreinstellung.

        OpenCV oeffnet USB-Kameras mit 640x480, wenn niemand etwas anderes
        verlangt - und niemand hat. Ein 134-px-Ausschnitt aus 480 Zeilen
        KANN nur unscharf sein, egal was die Anzeige damit macht. Genau
        daran sind drei Anlaeufe zur 'Schaerfe' gescheitert: sie haben am
        falschen Ende gearbeitet.

        Angefordert wird von gross nach klein; die Kamera behaelt das
        groesste, was sie kann. Das Ergebnis steht im Startlog.
        """
        with self._cap_lock:
            # ZUERST auf MJPEG stellen. Unkomprimiert (YUYV) schafft USB nur
            # etwa 5 Bilder je Sekunde bei 1080p - gemessen waren es 2,8.
            # Die volle Aufloesung ohne MJPEG ist also keine Verbesserung,
            # sondern ein Standbild.
            self.cap.set(cv2.CAP_PROP_FOURCC,
                         cv2.VideoWriter_fourcc(*"MJPG"))
        for b, h in ((1920, 1080), (1280, 720)):
            with self._cap_lock:
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, b)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
                self.cap.set(cv2.CAP_PROP_FPS, 30)
                ist = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            if ist >= b - 8:
                break
        with self._cap_lock:
            self.aufloesung = (int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                               int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
            fps = self.cap.get(cv2.CAP_PROP_FPS)
        print(f"  Kamera liefert {self.aufloesung[0]}x{self.aufloesung[1]} px "
              f"bei {fps:.0f} Bildern je Sekunde", flush=True)
        if fps and fps < 15:
            print("  ACHTUNG: unter 15 Bildern je Sekunde - MJPEG wurde "
                  "vermutlich nicht angenommen.", flush=True)
        if self.aufloesung[0] < 1000:
            print("  ACHTUNG: Kamera bleibt unter 1280 px - Ausschnitte werden "
                  "grob. USB-2-Anschluss oder Kameragrenze.", flush=True)

    def _pruefe_eigenschaften(self) -> dict:
        """Welche Einstellungen wirken wirklich?

        Geprueft wird durch Lesen: liefert die Kamera fuer eine Eigenschaft
        einen sinnvollen Wert, gilt sie als vorhanden. Eine Eigenschaft
        anzubieten, die die Kamera stillschweigend ignoriert, waere schlimmer
        als sie wegzulassen - der Bediener dreht dann an etwas Wirkungslosem.
        """
        aus = {}
        for name, (attr, _) in KAMERA_EIGENSCHAFTEN.items():
            prop = getattr(cv2, attr, None)
            if prop is None:
                continue
            try:
                with self._cap_lock:
                    wert = self.cap.get(prop)
            except Exception:
                continue
            if wert is not None and wert != -1:
                aus[name] = float(wert)
        return aus

    def lies_einstellungen(self, hoechstalter: float = 2.0) -> dict:
        """Kameraeinstellungen, hoechstens alle `hoechstalter` Sekunden neu.

        Die Zustandsabfrage laeuft jede Sekunde. Wuerde sie jedes Mal zehn
        Eigenschaften einzeln von der Kamera lesen und dabei die Sperre
        belegen, die auch der Bild-Thread braucht, stockt das Livebild - und
        bei ungluecklichem Zusammentreffen steht der Server.
        """
        if self.cap is None:
            return {}
        jetzt = time.perf_counter()
        if self._werte_cache and (jetzt - self._werte_zeit) < hoechstalter:
            return dict(self._werte_cache)

        # Nicht warten. Bekommt der Bild-Thread gerade die Sperre, liefern wir
        # die zuletzt bekannten Werte - eine Sekunde alte Zahl ist besser als
        # ein stehendes Bild.
        if not self._cap_lock.acquire(timeout=0.05):
            return dict(self._werte_cache)
        try:
            aus = {}
            for name in self.koennen:
                prop = getattr(cv2, KAMERA_EIGENSCHAFTEN[name][0], None)
                if prop is None:
                    continue
                try:
                    aus[name] = round(float(self.cap.get(prop)), 3)
                except Exception:
                    pass
        finally:
            self._cap_lock.release()

        self._werte_cache = aus
        self._werte_zeit = jetzt
        return dict(aus)

    def setze(self, name: str, wert: float) -> dict:
        """Setzt eine Eigenschaft und liest zurueck, was angekommen ist.

        Die Rueckmeldung ist wichtig: viele Kameras nehmen einen Wert
        entgegen, uebernehmen ihn aber nicht oder runden stark. Nur der
        zurueckgelesene Wert ist die Wahrheit.
        """
        if self.cap is None or name not in KAMERA_EIGENSCHAFTEN:
            return {"ok": False, "grund": "nicht verfuegbar"}
        prop = getattr(cv2, KAMERA_EIGENSCHAFTEN[name][0], None)
        if prop is None:
            return {"ok": False, "grund": "von OpenCV nicht unterstuetzt"}
        try:
            with self._cap_lock:
                self.cap.set(prop, float(wert))
                time.sleep(0.05)
                zurueck = round(float(self.cap.get(prop)), 3)
        except Exception as exc:
            return {"ok": False, "grund": str(exc)[:80]}

        self._werte_zeit = 0.0      # Cache ungueltig, Wert hat sich geaendert
        uebernommen = abs(zurueck - float(wert)) < max(1.0, abs(wert) * 0.05)
        return {"ok": True, "gesetzt": float(wert), "gelesen": zurueck,
                "uebernommen": uebernommen}

    def einfrieren(self) -> dict:
        """Schaltet alle Automatiken ab und haelt die aktuellen Werte fest.

        Fuer die Erkennung ist das der wichtigere Zustand: nachregelnder
        Weissabgleich laesst dasselbe Objekt von Bild zu Bild anders
        aussehen, und das Modell hat keine Moeglichkeit, diese Aenderung von
        einer echten Aenderung am Objekt zu unterscheiden.
        """
        if self.cap is None:
            return {"ok": False, "grund": "keine Kamera"}
        ergebnis = {}
        for name, (attr, ist_auto) in KAMERA_EIGENSCHAFTEN.items():
            if ist_auto and name in self.koennen:
                # Belichtung: V4L2 nutzt 1 fuer manuell, 3 fuer automatisch.
                aus_wert = 1.0 if name == "auto_belichtung" else 0.0
                ergebnis[name] = self.setze(name, aus_wert)
        return {"ok": True, "abgeschaltet": ergebnis,
                "werte": self.lies_einstellungen()}

    def zuruecksetzen(self) -> dict:
        """Zurueck auf die Werte, mit denen die Kamera geoeffnet wurde.

        Nicht "Werkseinstellung": was die Kamera beim Oeffnen liefert, ist
        ihr eigener Ausgangszustand. Genau der ist gemeint, wenn man sich
        verstellt hat und wieder auf festen Boden will.
        """
        if self.cap is None:
            return {"ok": False, "grund": "keine Kamera"}
        if not self.start_werte:
            return {"ok": False, "grund": "keine Startwerte gemerkt"}
        ergebnis = {}
        for name, wert in self.start_werte.items():
            ergebnis[name] = self.setze(name, wert)
        nicht = [n for n, r in ergebnis.items() if not r.get("uebernommen", True)]
        return {"ok": True, "zurueckgesetzt": sorted(self.start_werte),
                "nicht_uebernommen": nicht,
                "werte": self.lies_einstellungen(hoechstalter=0.0)}

    def neu_oeffnen(self) -> dict:
        """Haerteres Mittel: Kamera schliessen und neu oeffnen.

        Fuer den Fall, dass sie nicht mehr antwortet. Einzelne Eigenschaften
        zu setzen hilft dann nicht mehr - der Treiber braucht einen neuen
        Anfang.
        """
        with self._cap_lock:
            if self.cap is not None:
                self.cap.release()
            self.cap = cv2.VideoCapture(self.kamera_nr)
            offen = self.cap.isOpened()
            if not offen:
                self.cap.release()
                self.cap = None
        if not offen:
            # NICHT auf Testbilder wechseln - lies() versucht die
            # Wiederverbindung von selbst weiter.
            self.hinweis = f"Kamera {self.kamera_nr} liess sich nicht neu oeffnen"
            return {"ok": False, "grund": self.hinweis}
        self._aufloesung_setzen()
        self.synthetisch = False
        self._fehlschlaege = 0
        self._werte_zeit = 0.0
        self.koennen = self._pruefe_eigenschaften()
        self.start_werte = dict(self.koennen)
        self.hinweis = ""
        return {"ok": True, "werte": self.lies_einstellungen(hoechstalter=0.0)}

    def automatik_an(self) -> dict:
        if self.cap is None:
            return {"ok": False, "grund": "keine Kamera"}
        ergebnis = {}
        for name, (attr, ist_auto) in KAMERA_EIGENSCHAFTEN.items():
            if ist_auto and name in self.koennen:
                an_wert = 3.0 if name == "auto_belichtung" else 1.0
                ergebnis[name] = self.setze(name, an_wert)
        return {"ok": True, "eingeschaltet": ergebnis,
                "werte": self.lies_einstellungen()}

    # Erst nach so vielen Fehlversuchen HINTEREINANDER gilt die Kamera als
    # gestoert. Dann wird sie NEU VERBUNDEN - nicht durch Testbilder ersetzt.
    # Der stille Wechsel auf synthetische Bilder war eine Ersatzhandlung, die
    # zweimal wie ein Erkennungsfehler aussah und einmal beim Fokussieren
    # zuschlug. Testbilder gibt es nur noch, wenn ausdruecklich mit
    # --synthetisch gestartet wurde oder beim Start keine Kamera da war.
    MAX_FEHLSCHLAEGE = 15
    HEIL_ABSTAND = 3.0          # Sekunden zwischen Wiederverbindungsversuchen

    def _heilen(self) -> None:
        """Kamera schliessen und neu oeffnen - Selbstheilung im Betrieb."""
        jetzt = time.perf_counter()
        if jetzt - getattr(self, "_letzte_heilung", 0.0) < self.HEIL_ABSTAND:
            return
        self._letzte_heilung = jetzt
        with self._cap_lock:
            if self.cap is not None:
                self.cap.release()
            self.cap = cv2.VideoCapture(self.kamera_nr)
            offen = self.cap.isOpened()
            if not offen:
                self.cap.release()
                self.cap = None
        if offen:
            self._aufloesung_setzen()
            self._fehlschlaege = 0
            self._werte_zeit = 0.0
            self.koennen = self._pruefe_eigenschaften()
            self.hinweis = "Kamera nach Aussetzer neu verbunden"
            print("  Kamera nach Aussetzer neu verbunden", flush=True)
        else:
            self.hinweis = ("Kamera antwortet nicht - naechster Versuch in "
                            f"{self.HEIL_ABSTAND:.0f} s")
            print(f"  {self.hinweis}", flush=True)

    def lies(self) -> np.ndarray:
        if self.cap is not None:
            with self._cap_lock:
                ok, frame = self.cap.read()
            if ok:
                self._fehlschlaege = 0
                self._letztes = frame
                # BEWUSST in voller Aufloesung. Der Ausschnitt wird aus diesem
                # Bild geschnitten - waere es vorher verkleinert, wuerde
                # Hineinzoomen Aufloesung verlieren statt gewinnen. Verkleinert
                # wird erst die Anzeige.
                return frame
            self._fehlschlaege += 1
            if self._fehlschlaege >= self.MAX_FEHLSCHLAEGE:
                self._heilen()

        elif not self.synthetisch:
            # Kamera war da und ist weg: weiter versuchen, nie ersetzen.
            self._heilen()

        if not self.synthetisch:
            # Letztes gutes Bild zeigen, solange die Heilung laeuft. Ein
            # stehendes echtes Bild ist ehrlicher als ein laufendes falsches.
            if self._letztes is not None:
                time.sleep(0.05)
                return self._letztes
            leer = np.zeros((480, 640, 3), np.uint8)
            cv2.putText(leer, "KEIN KAMERABILD", (150, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 229, 255), 2,
                        cv2.LINE_AA)
            time.sleep(0.1)
            return leer

        from ..synth_objects import make_scene
        self._zaehler += 1
        if getattr(self, "stationaer", False):
            # STATIONAER (1.9.38): wie ein Tisch, auf den jemand Teile legt -
            # eine Szene steht szene_halten_s still, dann ist der Tisch
            # leer_s lang leer, dann kommt die naechste. So lassen sich
            # Automatik-Ausloeser und Pruefbuch ohne Kamera vorfuehren.
            takt = float(self.szene_halten_s) + float(self.szene_leer_s)
            t = time.time() - getattr(self, "_t0", 0.0)
            if not getattr(self, "_t0", 0.0):
                self._t0 = time.time()
                t = 0.0
            nr = int(t // takt)
            if t - nr * takt >= self.szene_halten_s:
                leer = np.full((self.groesse, self.groesse, 3), 34, np.uint8)
                time.sleep(0.05)
                return leer
            seed = 1000 + nr
            if seed != getattr(self, "_szene_seed", None):
                self._szene_seed = seed
                self._szene_bild = make_scene(
                    size=self.groesse, num_classes=config.NUM_CLASSES,
                    cell_px=self.groesse / config.GRID, seed=seed).image
            time.sleep(0.05)
            return self._szene_bild
        szene = make_scene(size=self.groesse, num_classes=config.NUM_CLASSES,
                           cell_px=self.groesse / config.GRID,
                           seed=self._zaehler)
        return szene.image

    def schliesse(self) -> None:
        with self._cap_lock:
            if self.cap is not None:
                self.cap.release()
                self.cap = None


# ----------------------------------------------------------------------
class Zweitkamera:
    """Eigene Zonen-Quellen im Linienmodus (1.7.0, PiCam ab 1.9.0).

    Zwei Sorten Quellen:
      "picamN"  zweite Pi-Kamera am CSI-Port N (>=1; Num 0 ist die
                Hauptkamera und schon belegt) - ueber picamera2.
      "usbN"    USB-Webcam an /dev/videoN - ueber cv2.
    Je Quelle laeuft bei Bedarf ein Grabber-Thread, der das letzte
    Bild vorhaelt. Faellt sie aus, wird alle paar Sekunden neu
    geoeffnet; die Zone meldet solange "Quelle startet/fehlt".
    """

    def __init__(self):
        self._laeufer = {}          # quelle(str) -> Zustands-Dict
        self._lock = threading.Lock()

    # -- USB-Grabber (cv2) --------------------------------------------
    def _starte_usb(self, index: int, z: dict) -> None:
        def lauf():
            cap = None
            while not z["stop"]:
                if cap is None:
                    try:
                        cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                        if not cap.isOpened():
                            raise RuntimeError("laesst sich nicht oeffnen")
                        z["fehler"] = ""
                    except Exception as exc:
                        try:
                            if cap is not None:
                                cap.release()
                        except Exception:
                            pass
                        cap = None
                        z["fehler"] = f"USB {index}: {exc}"[:90]
                        time.sleep(5.0)
                        continue
                ok, bild = cap.read()
                if ok and bild is not None:
                    z["bild"], z["ts"] = bild, time.time()
                else:
                    z["fehler"] = f"USB {index}: kein Bild"
                    try:
                        cap.release()
                    except Exception:
                        pass
                    cap = None
                    time.sleep(2.0)
            try:
                if cap is not None:
                    cap.release()
            except Exception:
                pass
        z["thread"] = threading.Thread(target=lauf, daemon=True)
        z["thread"].start()

    # -- PiCam-Grabber (picamera2, camera_num>=1) ---------------------
    def _starte_picam(self, num: int, z: dict) -> None:
        def lauf():
            cam = None
            while not z["stop"]:
                if cam is None:
                    try:
                        cam = _PICAM2_KLASSE(camera_num=num)
                        konf = cam.create_video_configuration(
                            main={"size": (1280, 720),
                                  "format": "RGB888"},
                            controls={"FrameRate": 15})
                        cam.configure(konf)
                        cam.start()
                        cam.set_controls({"AfMode": 2})   # Autofokus
                        z["cam"] = cam                    # fuer Kamerasteuerung
                        z["fehler"] = ""
                    except Exception as exc:
                        try:
                            if cam is not None:
                                cam.close()
                        except Exception:
                            pass
                        cam = None
                        z["cam"] = None
                        z["fehler"] = f"Pi-Kam {num}: {exc}"[:90]
                        time.sleep(5.0)
                        continue
                try:
                    # capture_array liefert bei RGB888 BGR im Speicher -
                    # genau wie die Hauptkamera, passt fuer cv2/_erkenne.
                    z["bild"], z["ts"] = cam.capture_array(), time.time()
                except Exception as exc:
                    z["fehler"] = f"Pi-Kam {num}: {exc}"[:90]
                    try:
                        cam.stop(); cam.close()
                    except Exception:
                        pass
                    cam = None
                    z["cam"] = None
                    time.sleep(2.0)
            try:
                if cam is not None:
                    cam.stop(); cam.close()
            except Exception:
                pass
        z["thread"] = threading.Thread(target=lauf, daemon=True)
        z["thread"].start()

    def _starte(self, quelle: str) -> dict:
        z = {"bild": None, "ts": 0.0, "fehler": "", "stop": False, "cam": None}
        if quelle.startswith("picam"):
            self._starte_picam(int(quelle[5:] or 1), z)
        else:
            self._starte_usb(int(quelle.replace("usb", "") or 0), z)
        return z

    def steuere(self, quelle: str, controls: dict) -> dict:
        """libcamera-Controls an eine laufende Pi-Zweitkamera schicken.
        USB-Kameras (cv2) haben keine solche Steuerung."""
        quelle = str(quelle)
        with self._lock:
            z = self._laeufer.get(quelle)
            cam = z.get("cam") if z else None
        if not quelle.startswith("picam"):
            return {"ok": False, "grund": "USB: keine Kamerasteuerung"}
        if cam is None:
            return {"ok": False, "grund": "Kamera noch nicht bereit"}
        try:
            cam.set_controls(dict(controls))   # picamera2: threadsicher
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "grund": str(exc)[:80]}

    def metadaten(self, quelle: str) -> dict:
        with self._lock:
            z = self._laeufer.get(str(quelle))
            cam = z.get("cam") if z else None
        if cam is None:
            return {}
        try:
            return dict(cam.capture_metadata())
        except Exception:
            return {}

    @staticmethod
    def verfuegbare():
        """Vorhandene Zonen-Kameras: [{"quelle","name"}, ...] -
        zuerst zweite Pi-Kameras (CSI-Port>=1), dann USB-Webcams."""
        import glob
        import os
        import re
        aus = []
        # Zweite Pi-Kameras (Num 0 = Hauptkamera, deshalb ab 1).
        # global_camera_info erzeugt jedes Mal einen CameraManager
        # (Log + Overhead) - CSI-Kameras wechseln nicht zur Laufzeit,
        # also nur EINMAL ermitteln und merken.
        cache = getattr(Zweitkamera, "_picam_cache", None)
        if cache is None:
            cache = []
            try:
                if _PICAM2_KLASSE is not None:
                    for c in _PICAM2_KLASSE.global_camera_info():
                        num = int(c.get("Num", 0))
                        if num >= 1:
                            # Namensgebung nach Einbaulage (Wunsch 2026-09-07):
                            # die zweite Pi-Kamera (Num 1) sitzt LINKS.
                            nm = ("1. Cam (links)" if num == 1
                                  else f"Pi-Kamera {num + 1}")
                            cache.append({"quelle": f"picam{num}",
                                          "name": nm})
            except Exception:
                pass
            Zweitkamera._picam_cache = cache
        aus.extend(cache)
        # USB-Webcams (nur echte USB-Geraete, per by-id)
        for pfad in sorted(glob.glob("/dev/v4l/by-id/*-video-index0")):
            try:
                ziel = os.path.realpath(pfad)
                m = re.search(r"video(\d+)$", ziel)
                if not m:
                    continue
                name = os.path.basename(pfad)
                name = name.replace("usb-", "").replace("-video-index0", "")
                name = re.sub(r"[_-]+", " ", name).strip()[:36]
                aus.append({"quelle": f"usb{m.group(1)}",
                            "name": "USB " + (name or ziel)})
            except Exception:
                continue
        return aus

    def bild(self, quelle: str):
        """Letztes Bild der Quelle ("picamN"/"usbN") -> (Bild|None, Text)."""
        quelle = str(quelle)
        with self._lock:
            z = self._laeufer.get(quelle)
            if z is None:
                z = self._laeufer[quelle] = self._starte(quelle)
        alter = time.time() - z["ts"]
        if z["bild"] is None or alter > 3.0:
            return None, z["fehler"] or f"{quelle}: startet ..."
        return z["bild"], ""


class Pruefbuch:
    """Pruef-Urteile JE TEIL: Zaehler, Protokoll, Bildarchiv (Stufe 1, 1.9.8).

    VORSA klassifiziert statt zu messen. Das Urteil ist deshalb dreiwertig:
      gut        - Teil sicher benannt (erwartete Klasse)
      unbekannt  - nichts sicher zugeordnet -> Mensch prueft / nachlernen
      ausschuss  - Negativklasse getroffen (bewusst als "schlecht" gelernt)
    Gebucht wird NICHT je Bild, sondern je physischem Teil - im Linienmodus
    an den Uebergaengen der Zustandsmaschine (abgeraeumt / Stoerung). Die
    Unbekannt-Quote ist unsere Leitkennzahl: steigt sie, muss nachgelernt
    oder die Optik geprueft werden.
    """

    MAX_PROTOKOLL = 2000
    MAX_ARCHIV = 500

    def __init__(self):
        from collections import deque
        self._deque = deque
        self._lock = threading.Lock()
        self._archiv_ordner: Optional[Path] = None
        self._archiv: list = []
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self.start = time.time()
            self.gesamt = self.gut = self.unbekannt = self.ausschuss = 0
            self.protokoll = self._deque(maxlen=self.MAX_PROTOKOLL)
            self.letztes: Optional[dict] = None

    def archiv_setzen(self, ordner) -> None:
        try:
            self._archiv_ordner = Path(ordner) / "ergebnisse"
            self._archiv_ordner.mkdir(parents=True, exist_ok=True)
            self._archiv = sorted(p.name for p in
                                  self._archiv_ordner.glob("*.jpg"))
        except Exception:
            self._archiv_ordner = None

    def buche(self, urteil: str, name: str = "", konfidenz: float = 0.0,
              grund: str = "", bild=None, quelle: str = "") -> dict:
        if urteil not in ("gut", "unbekannt", "ausschuss"):
            urteil = "unbekannt"
        ts = time.time()
        datei = ""
        # Nur Nicht-GUT-Faelle archivieren: das ist das Material zum
        # Nachlernen; GUT-Bilder wuerden nur Platz kosten.
        if (bild is not None and urteil != "gut"
                and self._archiv_ordner is not None):
            try:
                datei = (time.strftime("%Y%m%d_%H%M%S", time.localtime(ts))
                         + f"_{int((ts % 1) * 1000):03d}_{urteil}.jpg")
                b = bild
                h, w = b.shape[:2]
                f = min(1.0, 480.0 / max(h, w, 1))
                if f < 1.0:
                    b = cv2.resize(b, (max(8, int(w * f)), max(8, int(h * f))),
                                   interpolation=cv2.INTER_AREA)
                cv2.imwrite(str(self._archiv_ordner / datei), b,
                            [cv2.IMWRITE_JPEG_QUALITY, 82])
                self._archiv.append(datei)
                while len(self._archiv) > self.MAX_ARCHIV:
                    alt = self._archiv.pop(0)
                    (self._archiv_ordner / alt).unlink(missing_ok=True)
            except Exception:
                datei = ""
        eintrag = {"zeit": ts, "urteil": urteil, "name": str(name or ""),
                   "konfidenz": round(float(konfidenz or 0.0), 3),
                   "grund": str(grund or ""), "quelle": str(quelle or ""),
                   "bild": datei}
        with self._lock:
            self.gesamt += 1
            if urteil == "gut":
                self.gut += 1
            elif urteil == "ausschuss":
                self.ausschuss += 1
            else:
                self.unbekannt += 1
            self.protokoll.append(eintrag)
            self.letztes = eintrag
        return eintrag

    def statistik(self, live: Optional[dict] = None) -> dict:
        with self._lock:
            dauer = max(0.0, time.time() - self.start)
            g = self.gesamt
            return {
                "gesamt": g, "gut": self.gut, "unbekannt": self.unbekannt,
                "ausschuss": self.ausschuss,
                "quote_gut": round(self.gut / g * 100, 1) if g else None,
                "quote_unbekannt": (round(self.unbekannt / g * 100, 1)
                                    if g else None),
                "teile_pro_min": (round(g / (dauer / 60.0), 2)
                                  if dauer > 5 and g else 0.0),
                "laufzeit_s": int(dauer),
                "letztes": dict(self.letztes) if self.letztes else None,
                "protokoll": [dict(e) for e in
                              list(self.protokoll)[-12:]][::-1],
                "live": live,
            }

    def csv_text(self) -> str:
        def s(v):
            return str(v).replace(";", ",").replace("\n", " ")
        with self._lock:
            zeilen = ["zeit;urteil;name;konfidenz;grund;quelle;bild"]
            for e in self.protokoll:
                t = time.strftime("%Y-%m-%d %H:%M:%S",
                                  time.localtime(e["zeit"]))
                zeilen.append(";".join([t, e["urteil"], s(e["name"]),
                                        str(e["konfidenz"]), s(e["grund"]),
                                        s(e["quelle"]), e["bild"]]))
        return "\n".join(zeilen) + "\n"


class Alarmbuch:
    """Alarmverwaltung nach ISA-101 (Stufe 2, 1.9.10).

    Jeder Alarm hat einen SCHLUESSEL (Bedingung) und wird FLANKENGESTEUERT
    angelegt: solange die Bedingung ansteht, gibt es genau EINEN aktiven
    Eintrag (kein Spam je Bild). Faellt sie weg, wird er "inaktiv", bleibt
    aber in der Historie - und UNQUITTIERT, bis ein Mensch ihn quittiert.
    Zustaende: aktiv/unquittiert, aktiv/quittiert, inaktiv/unquittiert
    (zurueck auf normal, noch nicht gesehen), inaktiv/quittiert (erledigt).
    Stufen: alarm (Betrieb beeintraechtigt), warn (Hinweis), info.
    """

    MAX = 500

    def __init__(self):
        from collections import deque
        self._lock = threading.Lock()
        self._eintraege = deque(maxlen=self.MAX)
        self._aktiv: dict = {}          # schluessel -> eintrag
        self._naechste_id = 1

    def melde(self, schluessel: str, stufe: str, text: str,
              einmalig: bool = False) -> None:
        stufe = stufe if stufe in ("alarm", "warn", "info") else "warn"
        with self._lock:
            e = self._aktiv.get(schluessel)
            if e is not None and not einmalig:
                if text and e["text"] != text:
                    e["text"] = str(text)[:160]
                return
            e = {"id": self._naechste_id, "zeit": time.time(),
                 "stufe": stufe, "schluessel": schluessel,
                 "text": str(text)[:160], "aktiv": not einmalig,
                 "quittiert": False, "quittiert_zeit": None,
                 "ende_zeit": (time.time() if einmalig else None)}
            self._naechste_id += 1
            self._eintraege.append(e)
            if not einmalig:
                self._aktiv[schluessel] = e

    def beende(self, schluessel: str) -> None:
        with self._lock:
            e = self._aktiv.pop(schluessel, None)
            if e is not None:
                e["aktiv"] = False
                e["ende_zeit"] = time.time()

    def quittiere(self, id_: Optional[int] = None) -> int:
        n = 0
        with self._lock:
            for e in self._eintraege:
                if e["quittiert"]:
                    continue
                if id_ is None or e["id"] == id_:
                    e["quittiert"] = True
                    e["quittiert_zeit"] = time.time()
                    n += 1
        return n

    def kurz(self) -> dict:
        """Kompakt fuer jeden Zustandsabruf (Glocke + Statusbanner)."""
        with self._lock:
            unq = [e for e in self._eintraege if not e["quittiert"]]
            return {
                "unquittiert": len(unq),
                "aktiv_alarm": any(e["aktiv"] and e["stufe"] == "alarm"
                                   for e in self._aktiv.values()),
                "aktiv_warn": any(e["aktiv"] and e["stufe"] == "warn"
                                  for e in self._aktiv.values()),
                "letzte": [dict(e) for e in list(self._eintraege)[-3:]][::-1],
            }

    def liste(self) -> dict:
        with self._lock:
            alle = [dict(e) for e in self._eintraege][::-1]
        return {"eintraege": alle,
                "unquittiert": sum(1 for e in alle if not e["quittiert"]),
                "aktiv": sum(1 for e in alle if e["aktiv"])}


class Rezeptbuch:
    """Rezepte/Auftraege je Teilevariante (Stufe 4, 1.9.12).

    Ein Rezept buendelt die EINRICHTUNG fuer ein Produkt, damit das
    Umruesten eine Auswahl ist statt vieler Klicks:
      kamera   - Kameraeinstellungen (Fokus, Belichtung, ...)
      bereich  - Erkennungsfenster (Groesse/Lage)
      linie    - Zonen (Anlieferung/Abholung) + Kameraquellen je Zone
      arm      - Punkte + Sequenz "Holen"
      schwelle - Konfidenzschwelle (Stufe 5; bis dahin None)
    Das GEDAECHTNIS (gelernte Teile) wird bewusst NICHT kopiert - es ist
    mehrklassig und gilt produktuebergreifend; ein Rezept merkt sich nur
    seinen Fingerabdruck als Hinweis, ob es dazu passt.
    """

    DATEI = "rezepte.json"

    def __init__(self, ordner):
        self._pfad = Path(ordner) / self.DATEI
        self._lock = threading.Lock()
        self._daten = {"aktiv": "", "rezepte": {}}
        try:
            if self._pfad.exists():
                d = json.loads(self._pfad.read_text(encoding="utf-8"))
                if isinstance(d, dict):
                    self._daten = {"aktiv": str(d.get("aktiv", "")),
                                   "rezepte": dict(d.get("rezepte", {}))}
        except Exception:
            pass

    def _sichern(self) -> None:
        try:
            self._pfad.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._pfad.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._daten, indent=2,
                                      ensure_ascii=False), encoding="utf-8")
            tmp.replace(self._pfad)
        except Exception:
            pass

    def aktiv_name(self) -> str:
        return str(self._daten.get("aktiv", "") or "")

    def uebersicht(self) -> dict:
        with self._lock:
            return {
                "aktiv": self._daten["aktiv"],
                "rezepte": {n: {"gespeichert": r.get("gespeichert", ""),
                                "zonen": bool(r.get("linie")),
                                "arm": bool((r.get("arm") or {}).get("holen")),
                                "kamera": bool(r.get("kamera")),
                                "gedaechtnis": r.get("gedaechtnis", "")}
                            for n, r in self._daten["rezepte"].items()},
            }

    def aufnehmen(self, name: str, verarbeitung, zustand) -> dict:
        name = (name or "").strip()[:40]
        if not name:
            return {"ok": False, "grund": "Name fehlt"}
        r = {"gespeichert": time.strftime("%Y-%m-%d %H:%M")}
        try:
            r["kamera"] = dict(verarbeitung.quelle.lies_einstellungen())
        except Exception:
            r["kamera"] = {}
        try:
            b = zustand.bereich.as_dict()
            r["bereich"] = {"fenster": b.get("fenster"),
                            "cx": b.get("cx"), "cy": b.get("cy")}
        except Exception:
            r["bereich"] = {}
        li = verarbeitung.linie
        if li is not None:
            r["linie"] = {"anliefer": list(li.anliefer),
                          "abhol": list(li.abhol),
                          "quellen": dict(getattr(li, "quellen", {}) or {})}
        a = getattr(verarbeitung, "arm_uno", None)
        if a is not None:
            try:
                r["arm"] = {"punkte": dict(a.punkte()),
                            "holen": list((a.programme().get("Holen")
                                           or {}).get("steps") or [])}
            except Exception:
                r["arm"] = {}
        r["schwelle"] = getattr(verarbeitung, "konfidenz_schwelle", None)
        try:
            r["gedaechtnis"] = str(zustand.fingerabdruck())[:16]
        except Exception:
            r["gedaechtnis"] = ""
        with self._lock:
            self._daten["rezepte"][name] = r
            self._daten["aktiv"] = name
            self._sichern()
        return {"ok": True, "name": name, **self.uebersicht()}

    def anwenden(self, name: str, verarbeitung, zustand) -> dict:
        with self._lock:
            r = self._daten["rezepte"].get(name)
        if r is None:
            return {"ok": False, "grund": "Rezept unbekannt"}
        bericht = []
        # 1) Kamera
        try:
            nicht = []
            for k, v in (r.get("kamera") or {}).items():
                erg = verarbeitung.quelle.setze(k, v)
                if not (erg or {}).get("uebernommen", True):
                    nicht.append(k)
            bericht.append("Kamera" + (f" (ohne {', '.join(nicht)})"
                                       if nicht else ""))
        except Exception as exc:
            bericht.append(f"Kamera: {str(exc)[:60]}")
        # 2) Erkennungsfenster
        try:
            b = r.get("bereich") or {}
            if b.get("fenster") is not None:
                zustand.bereich_setzen(b.get("fenster"), b.get("cx"),
                                       b.get("cy"))
                bericht.append("Fenster")
        except Exception as exc:
            bericht.append(f"Fenster: {str(exc)[:60]}")
        # 3) Linie: Zonen + Quellen
        li = verarbeitung.linie
        L = r.get("linie") or {}
        if li is not None and L:
            try:
                if L.get("anliefer"):
                    li.anliefer = tuple(float(v) for v in L["anliefer"])
                if L.get("abhol"):
                    li.abhol = tuple(float(v) for v in L["abhol"])
                q = L.get("quellen") or {}
                for art in ("anliefer", "abhol"):
                    if art in q:
                        li.quellen[art] = str(q[art])
                li.speichern(zustand.ordner)
                li._zone_frisch = time.time()
                bericht.append("Zonen + Quellen")
            except Exception as exc:
                bericht.append(f"Linie: {str(exc)[:60]}")
        # 4) Arm: Punkte + Sequenz Holen
        a = getattr(verarbeitung, "arm_uno", None)
        A = r.get("arm") or {}
        if a is not None and A:
            try:
                if isinstance(A.get("punkte"), dict):
                    a._punkte_datei.write_text(
                        json.dumps(A["punkte"], indent=2), encoding="utf-8")
                if isinstance(A.get("holen"), list):
                    a.programm_speichern("Holen", A["holen"])
                bericht.append("Arm-Sequenz")
            except Exception as exc:
                bericht.append(f"Arm: {str(exc)[:60]}")
        # 5) Schwelle (Stufe 5) - persistent uebernehmen
        if "schwelle" in r:
            try:
                verarbeitung.pruef_einst_setzen(
                    schwelle=r.get("schwelle"),
                    schwelle_aus=r.get("schwelle") is None)
                bericht.append("Schwelle")
            except Exception:
                pass
        with self._lock:
            self._daten["aktiv"] = name
            self._sichern()
        # Passt das Gedaechtnis noch zum Rezept?
        hinweis = ""
        try:
            if r.get("gedaechtnis") and r["gedaechtnis"] != str(
                    zustand.fingerabdruck())[:16]:
                hinweis = ("Gelernter Stand hat sich seit dem Speichern "
                           "geaendert - Erkennung pruefen.")
        except Exception:
            pass
        return {"ok": True, "name": name, "angewendet": bericht,
                "hinweis": hinweis, **self.uebersicht()}

    def loeschen(self, name: str) -> dict:
        with self._lock:
            ok = self._daten["rezepte"].pop(name, None) is not None
            if self._daten["aktiv"] == name:
                self._daten["aktiv"] = ""
            self._sichern()
        return {"ok": ok, **self.uebersicht()}


class Verarbeitung:
    """Holt Bilder, laesst die Pipeline laufen, haelt das letzte Ergebnis."""

    def __init__(self, quelle: Bildquelle, zustand: Zustand,
                 mit_erkennung: bool = True, anzeige_groesse: int = 640,
                 lerner: "EdgeLerner" = None):
        self.quelle = quelle
        self.zustand = zustand
        self.mit_erkennung = mit_erkennung
        self.anzeige_groesse = anzeige_groesse
        self.lerner = lerner
        self.detektor = None             # M3Detektor (Stufe 2), s. detektor_laden
        # Linien-Modus (2026-09-03): Foerderband + Zone + Arm-Uebergabe.
        # Standard ist die SIMULATION - erst mit VORSA_BAND=echt beim Start
        # schaltet der L298N wirklich (VORSA_ARM_URL fuer den Pi 4 des Arms).
        import os as _os
        from ..linie import LinienSteuerung, ArmKlient, band_bauen
        # PROFIL (SE Inspect 1.0, 1.9.38): "stationaer" (Standard) =
        # Pruefzelle ohne Band, Arm und Zonen - die Linie bleibt als
        # schlafendes Objekt im Speicher (viele Pfade erwarten sie),
        # darf aber nie aktiv werden und das Band bleibt Simulation.
        # "linie" = bisheriges Verhalten (Band, Arm, Zonen).
        self.profil = _os.environ.get("VORSA_PROFIL", "").lower()
        if self.profil not in ("stationaer", "linie"):
            # Nicht gesetzt (z. B. aelteres start.sh): wer Band oder Arm
            # konfiguriert hat, meint die Linie - sonst die Pruefzelle.
            # Sonst haette ein sync ohne neues start.sh die Anlage still
            # von Band+Arm auf Simulation umgestellt (Audit 2026-10-02).
            band = _os.environ.get("VORSA_BAND", "sim").lower()
            arm = _os.environ.get("VORSA_ARM", "").lower() or _os.environ.get("VORSA_ARM_URL", "")
            self.profil = "linie" if (band in ("echt", "relais") or arm) else "stationaer"
        if self.profil == "stationaer" and getattr(quelle, "synthetisch", False):
            quelle.stationaer = True
            quelle.szene_halten_s = float(_os.environ.get("VORSA_SYNTH_HALTEN_S", "6"))
            quelle.szene_leer_s = float(_os.environ.get("VORSA_SYNTH_LEER_S", "2"))
        # VORSA_BAND: "sim" (Standard) | "echt" (L298N) | "relais"
        # (12-V-Relaismodul an GPIO, VORSA_BAND_PIN aendert den Pin).
        _band_art = _os.environ.get("VORSA_BAND", "sim").lower()
        if self.profil == "stationaer":
            _band_art = "sim"
        # VORSA_ARM=uno: der Arduino-Stepperarm haengt per USB DIREKT
        # am Pi 5 und wird von diesem Server mitgesteuert (Anlernen im
        # ARM-Dialog, die Linie ruft ihn intern, ohne HTTP). Sonst wie
        # gehabt: VORSA_ARM_URL fuer einen externen Arm-Server (Pi 4).
        self.arm_uno = None
        if self.profil == "linie" and _os.environ.get("VORSA_ARM", "").lower() in (
                "uno", "arduino", "seriell"):
            from ..arm_uno import ArmUno, ArmIntern
            self.arm_uno = ArmUno(
                _os.environ.get("VORSA_ARM_PORT", "/dev/ttyACM0"),
                zustand.ordner)
            arm_klient = ArmIntern(self.arm_uno)
        else:
            arm_klient = ArmKlient(_os.environ.get("VORSA_ARM_URL", ""))
        self.linie = LinienSteuerung(
            band=band_bauen(
                pins={"ena": int(_os.environ.get("VORSA_BAND_PIN", "18"))},
                simulation=_band_art not in ("echt", "relais"),
                art="relais" if _band_art == "relais" else "l298n"),
            arm=arm_klient)
        try:
            self.linie.laden(zustand.ordner)   # gespeicherte Zonen
        except Exception:
            pass
        # EINKAMERA (SE Inspect 1.0, 1.9.55): Anlieferung und Abholung
        # kommen aus derselben Kamera. Zweitkameras/Blick 2/Lernzonen
        # gibt es erst wieder mit VORSA_ZWEITKAMERA=1. Eine gespeicherte
        # Zonen-Quelle wie "picam1" (Kamera abgesteckt -> schwarzes Feld,
        # "list index out of range") wird hier auf die Hauptkamera gelegt.
        self.einkamera = _os.environ.get("VORSA_ZWEITKAMERA", "0").lower() not in ("1", "ja", "true")
        if self.einkamera:
            try:
                q = getattr(self.linie, "quellen", {}) or {}
                fremd = {a: v for a, v in q.items() if str(v) != "haupt"}
                if fremd:
                    for a in fremd:
                        q[a] = "haupt"
                    print(f"  Einkamera: Zonen-Quellen {fremd} -> Hauptkamera "
                          f"(Zone ggf. neu ziehen)", flush=True)
            except Exception:
                pass
        # USB-Zweitkameras als Zonen-Quellen; annotierte Zonen-Feeds
        # (JPEG) fuer die Splitansicht, wenn die Quelle nicht "haupt" ist.
        self.zweitkamera = Zweitkamera()
        self._linie_feeds = {}
        # Pruefbuch (Stufe 1): Urteil je Teil, Zaehler, Protokoll, Archiv.
        self.pruefbuch = Pruefbuch()
        try:
            self.pruefbuch.archiv_setzen(self.zustand.ordner)
        except Exception:
            pass
        self._pruef_gefoerdert = 0        # letzter bekannter Zaehlerstand
        self._pruef_geprueft = 0          # Fluss-Takt: gebuchte Pruefungen
        self._pruef_phase = ""            # letzte Linienphase (Uebergaenge)
        self._pruef_stand = None          # letzte Statistik (fuer bereich_info)
        # STATIONAERE PRUEFUNG (1.9.38): Ausloeser "hand" (Knopf / API)
        # oder "auto" (Szene steht still und ist neu). Gebucht wird je
        # Teil im Bild; danach ist die Szene "abgehakt", bis sie sich
        # aendert. Letzte Pruefung fuer die Anzeige.
        self.pruef_ausloeser = "hand"
        self._pruef_szene_seit = 0.0      # seit wann steht die Szene so?
        self._pruef_szene_sig = ""        # Kennung der aktuellen Szene
        self._pruef_gebucht_sig = ""      # Kennung der zuletzt gebuchten
        self._pruef_gebucht_zeit = 0.0
        self._pruef_letzte: Optional[dict] = None
        self._pruef_ausschnitt = None     # Bild der letzten Erkennung
        self._pruef_anfrage = False       # /api/pruefen wartet auf den Takt
        # TESTSATZ (A6, 1.9.45): Pruefszenen mit Soll-Werten fuer die
        # Qualitaetsziele; Aufnahme nimmt den ROHEN Ausschnitt (vor dem
        # Mehrbild-Mittel), damit die Auswertung dieselbe Kette durchlaeuft.
        from ..testsatz import Testsatz
        try:
            self.testsatz = Testsatz(zustand.ordner)
        except Exception:
            self.testsatz = None
        self._roh_ausschnitt = None
        # MEHRBILD (1.9.40, A2): im Profil stationaer wird der Ausschnitt
        # ueber N Bilder gemittelt, solange die Szene steht. Weniger
        # Rauschen, kein LED-Flackern in der Leerbild-Differenz.
        from ..mehrbild import Mehrbild
        self.mehrbild = Mehrbild(anzahl=4 if self.profil == "stationaer" else 1)
        # KARTENVERTEILER (A4, 1.9.42): nur stationaer; dort werden die
        # Prototypen repliziert und Hypothesen-Auftraege parallel bewertet.
        self.verteiler = None
        if self.profil == "stationaer" and lerner is not None:
            from ..verteiler import Kartenverteiler
            try:
                lerner.replikation = _os.environ.get("VORSA_VERBUND", "repliziert") != "verteilt"
            except Exception:
                pass
            self.verteiler = Kartenverteiler(lerner)
        # LERNZONEN (1.9.29): je Kamera eine eigene Zone im Lernmodus -
        # ein Foto-Klick nimmt aus ALLEN aktiven Zonen auf (zwei
        # Perspektiven). Slot "a"/"b", Konfiguration in lernzonen.json.
        self._lernzonen = {
            "a": {"quelle": "haupt", "zone": [0.30, 0.20, 0.70, 0.80], "an": True},
            "b": {"quelle": "aus", "zone": [0.02, 0.02, 0.98, 0.98], "an": False},
        }
        self._lernzonen_laden()
        # BLICK 2 (1.9.27): zweite Kamera auf die ANLIEFERUNG - zwei
        # Blickwinkel, ein fusioniertes Urteil. Konfiguration liegt hier
        # (blick2.json), linie.py bleibt unangetastet.
        self._blick2 = {"quelle": "aus", "zone": [0.02, 0.02, 0.98, 0.98]}
        self._fusion_info: dict = {}
        self._blick2_laden()
        if getattr(self, "einkamera", True) and self._blick2.get("quelle", "aus") != "aus":
            print(f"  Einkamera: Blick 2 ({self._blick2['quelle']}) bleibt aus", flush=True)
            self._blick2["quelle"] = "aus"      # nur im Speicher, blick2.json bleibt
        # LEERBILD je Kamera (2026-09-19): Referenz des leeren Bands fuer
        # die Differenz-Segmentierung. quelle -> {"bild", "zeit"}.
        self._leerbild: dict = {}
        self._leerbild_laden()
        # Rezeptbuch (Stufe 4): Einrichtung je Teilevariante.
        try:
            self.rezeptbuch = Rezeptbuch(self.zustand.ordner)
        except Exception:
            self.rezeptbuch = None
        # Stufe 5 (1.9.25): Konfidenzschwelle + Ziel-Unbekanntquote,
        # persistent in vorsa_daten/pruef.json. None = keine Schwelle
        # (Chip-Urteil gilt wie es kommt).
        self.konfidenz_schwelle = None
        self.unbekannt_ziel = 10.0        # % - darueber: Nachlernen empfohlen
        self._pruef_einst_laden()
        # Alarmbuch (Stufe 2): flankengesteuerte Alarme mit Quittieren.
        self.alarmbuch = Alarmbuch()
        # BENUTZERROLLEN (I3, 1.9.60): ohne Admin-PIN alles offen.
        try:
            from ..rollen import Rollen
            self.rollen = Rollen(zustand.ordner)
        except Exception as exc:
            print(f"  Rollen nicht verfuegbar: {exc}", flush=True)
            self.rollen = None
        # DIGITALE EIN-/AUSGAENGE (I1, 1.9.59): Trigger rein, OK/NOK/Bereit/
        # Fehler raus. Ohne Hardware: Simulation. Bandrelais (GPIO 18) tabu.
        self._pruef_anfrage_grund = "hand"
        try:
            from ..eaio import EinAusgaenge
            self.eaio = EinAusgaenge(zustand.ordner, ausloesen=self._eaio_trigger)
            if self.eaio.fehler:
                print(f"  Ein-/Ausgaenge: {self.eaio.fehler} -> Simulation", flush=True)
        except Exception as exc:
            print(f"  Ein-/Ausgaenge nicht verfuegbar: {exc}", flush=True)
            self.eaio = None
        # SPS-ANBINDUNG (I2, 1.9.61): Modbus-TCP-Server, Standard aus.
        self._sps_letzt = {"urteil": "", "objekt_id": -1, "konfidenz": 0.0, "teile": 0}
        self._sps_seq = 0
        try:
            from ..sps import SpsServer
            self.sps = SpsServer(self._sps_stand, self._sps_befehl)
            c = self._sps_cfg()
            if c.get("an"):
                f = self.sps.starten(int(c.get("port", 1502)), bool(c.get("nur_lesen")))
                print(f"  SPS/Modbus: {'Port ' + str(self.sps.port) if not f else f}", flush=True)
        except Exception as exc:
            print(f"  SPS nicht verfuegbar: {exc}", flush=True)
            self.sps = None
        if self.profil == "linie":
            # Linie: jedes gebuchte Teil meldet OK/NOK an Ein-/Ausgaenge und
            # SPS - eine Stelle, linie.py bleibt unangetastet.
            _buche = self.pruefbuch.buche

            def _buche_mit_ausgang(urteil, name="", konf=0.0, *a, **k):
                e = _buche(urteil, name, konf, *a, **k)
                try:
                    if self.eaio is not None:
                        self.eaio.ergebnis(str(urteil))
                    self._sps_merken(str(urteil), str(name or ""), float(konf or 0), 1)
                except Exception:
                    pass
                return e
            self.pruefbuch.buche = _buche_mit_ausgang
        # KARTEN-WAECHTER (1.9.36): Stoerung/Wiederaufnahme einer Karte
        # landet als Alarm im Meldungsbuch - flankengesteuert.
        try:
            if self.lerner is not None:
                self.lerner.on_karte_fehler = self._karte_alarm
        except Exception:
            pass
        self._alarm_stand = None
        self._system_stand = "bereit"
        self._roh: Optional[np.ndarray] = None
        self._ausschnitt: Optional[np.ndarray] = None
        self._anzeige: Optional[np.ndarray] = None
        self._letztes_ereignis = 0.0
        self._lock = threading.Lock()
        self._laeuft = True
        self._thread = threading.Thread(target=self._schleife, daemon=True)
        self._thread.start()

    def detektor_laden(self, pfad: str) -> None:
        """Laedt vorsa_m3.fbz auf die LETZTE Karte (Stufe 2 des Kartenplans).

        Laeuft im Hintergrund: mappen dauert Sekunden, der Server soll
        sofort antworten. Schlaegt es fehl, steht der Grund in den
        Hinweisen - die Erkennung laeuft dann ohne Detektor weiter.
        """
        global _DETEKTOR
        # Drei Versuche mit Pause: beim Start mappen Verbund (Karten 0-2)
        # und Detektor (Karte 3) parallel - dieses Rennen hat das Laden
        # schon einmal still scheitern lassen. Das Lerner-Lock haelt die
        # beiden ausserdem auseinander.
        letzter = ""
        for versuch in range(3):
            try:
                import akida
                from ..detektor import M3Detektor
                geraete = akida.devices()
                if not geraete:
                    raise RuntimeError("keine Karte gefunden")
                nr = len(geraete) - 1 if len(geraete) > 1 else 0
                sperre = getattr(self.lerner, "_lock", None) or threading.Lock()
                with sperre:
                    self.detektor = M3Detektor(pfad, geraete[nr])
                _DETEKTOR = {"aktiv": True, "karte": nr, "datei": pfad}
                self.zustand.hinweise.append(
                    f"M3-Detektor geladen auf Karte {nr} - findet Teile "
                    "trotz Ueberlappung; benannt wird vom Verbund")
                print(f"  M3-Detektor: {pfad} auf Karte {nr}", flush=True)
                return
            except Exception as exc:
                letzter = f"{type(exc).__name__}: {exc}"[:130]
                print(f"  M3-Detektor Versuch {versuch + 1}: {letzter}",
                      flush=True)
                time.sleep(3)
        _DETEKTOR = {"aktiv": False, "grund": letzter, "datei": pfad}
        self.zustand.hinweise.append(f"M3-Detektor nicht geladen: {letzter}")

    @staticmethod
    def _fusion(geo, m3, maske=None, bewerte=None, punkte_ab: float = 0.35,
                ersetzbar=None):
        """Fuehrt Geometrie- und Detektor-Rahmen zusammen.

        Regel: sieht der Detektor INNERHALB eines Geometrie-Klumpens
        mehrere Teile, ersetzen seine Kaesten den Klumpen - das ist der
        Fall "SD liegt auf dem Karabiner", in dem die Wasserscheide keine
        Trennlinie findet. Sieht er dort nur eines, bleibt der genauere
        Geometrie-Rahmen. Detektortreffer ausserhalb jeder Geometrie
        kommen als Verdeckungsverdacht dazu.
        """
        import cv2 as _cv2
        from ..detection import Occlusion
        if not m3:
            return geo
        m3 = [m for m in m3 if m.score >= punkte_ab]
        if not m3:
            return geo
        benutzt = set()
        aus = []
        # Deckungsregel: ein Detektorkasten zaehlt nur, wenn er zu einem
        # nennenswerten Teil auf VORDERGRUND liegt. Ohne sie hat ein viel
        # zu grosser Kasten (halb ueber leerem Leuchtpad) die enge
        # Geometrie eines frei liegenden Karabiners ersetzt (2026-08-28).
        binaer0 = (np.asarray(maske) > 0).astype(np.uint8) \
            if maske is not None else None
        def _deckung(m):
            if binaer0 is None:
                return 1.0
            probe = np.zeros(binaer0.shape, np.uint8)
            _cv2.fillPoly(probe, [np.asarray(m.box.corners())
                                  .astype(np.int32)], 1)
            flaeche = int(probe.sum())
            if flaeche < 1:
                return 0.0
            return float((binaer0 & probe).sum()) / flaeche
        m3 = [m for m in m3 if _deckung(m) >= 0.20]
        if not m3:
            return geo
        for g in geo:
            umriss = (g.contour.astype(np.int32).reshape(-1, 1, 2)
                      if g.contour is not None
                      else g.box.corners().astype(np.int32).reshape(-1, 1, 2))
            drin = [i for i, m in enumerate(m3) if i not in benutzt
                    and _cv2.pointPolygonTest(
                        umriss, (float(m.box.cx), float(m.box.cy)), False) >= 0]
            if len(drin) >= 2 and (ersetzbar is None or id(g) in ersetzbar):
                # Schiedsrichter: der Chip vergleicht das GANZE mit den
                # Stuecken. Nur wenn ein Stueck DEUTLICH besser passt, wird
                # zerlegt - sonst hat der Detektor in einem einzelnen Teil
                # Gespenster gesehen (freier Karabiner in zwei Kaesten,
                # 2026-08-28). Die Chip-Antworten werden gecacht, das
                # Benennen fragt spaeter nicht noch einmal.
                punkte_je = {}
                if bewerte is not None:
                    ganz = bewerte(g.box, g.contour)
                    bestes = 0.0
                    zweitbestes = 0.0
                    for i in drin:
                        # FAIR bewerten: die Nachbar-Kaesten ausstanzen,
                        # genau wie spaeter beim Benennen. Ohne Sperrzonen
                        # war die Stueck-Maske verschmutzt, das "unbekannte
                        # Ganze" gewann, und der Klumpen blieb (2026-08-28).
                        nachbarn = [np.asarray(m3[j].box.corners())
                                    for j in drin if j != i]
                        s = bewerte(m3[i].box, None, sperren=nachbarn)
                        if s:
                            m3[i].meta["chip"] = s[1]
                            punkte_je[i] = s[0]
                            if s[0] > bestes:
                                zweitbestes = bestes
                                bestes = s[0]
                            elif s[0] > zweitbestes:
                                zweitbestes = s[0]
                    # Zerlegt wird nur, wenn die Stuecke wirklich tragen:
                    # das beste klar besser als das Ganze UND das zweite
                    # wenigstens brauchbar. Ohne die zweite Bedingung haben
                    # zwei schiefe Detektorkaesten (66 %/33 %) eine saubere
                    # Geometrie ersetzt (2026-08-28).
                    if ganz is not None:
                        g.meta["chip"] = ganz[1]
                        if ganz[0] >= bestes - 0.04 or zweitbestes < 0.35:
                            benutzt.update(drin)
                            aus.append(g)
                            continue
                for i in drin:
                    benutzt.add(i)
                    # Traeger unter 35 % fliegen: der dritte, windschiefe
                    # Kasten (28 %) hat sonst als Geist mitgezeichnet.
                    if punkte_je and punkte_je.get(i, 0.0) < 0.35:
                        continue
                    m3[i].meta["fusion"] = "Detektor zerlegt Klumpen"
                    aus.append(m3[i])
            else:
                benutzt.update(drin)
                aus.append(g)
        # Zusatzkaesten ohne Geometrie-Gegenstueck nur mit hoher Punktzahl
        # UND Zentrum auf Vordergrund - Kaesten ins leere Leuchtpad haben
        # die Anzeige nur zugemuellt (2026-08-28). Hoechstens zwei davon.
        binaer = None
        if maske is not None:
            binaer = (np.asarray(maske) > 0)
        zusatz = 0
        for i, m in enumerate(m3):
            if i in benutzt or m.score < 0.7 or zusatz >= 2:
                continue
            if binaer is not None:
                y, x = int(round(m.box.cy)), int(round(m.box.cx))
                if not (0 <= y < binaer.shape[0] and 0 <= x < binaer.shape[1]
                        and binaer[y, x]):
                    continue
            m.meta["fusion"] = "nur Detektor - Verdacht Verdeckung"
            if m.occlusion == Occlusion.FREE:
                m.occlusion = Occlusion.PARTIAL
            aus.append(m)
            zusatz += 1
        return aus

    def _schleife(self) -> None:
        while self._laeuft:
            t0 = time.perf_counter()
            frame = self.quelle.lies()
            # Bilddrehung in 90-Grad-Schritten (Knopf im Videokopf,
            # 2026-08-28): VOR allem anderen angewandt, damit Erkennung,
            # Lernfotos und Anzeige dieselbe Lage sehen - z. B. wenn die
            # Kamera gedreht montiert ist.
            d = getattr(self, "drehung", 0)
            if d:
                frame = np.ascontiguousarray(np.rot90(frame, d // 90))
            h, w = frame.shape[:2]
            x, y, seite, hinweis = self.zustand.bereich.rechteck(w, h)
            self.zustand.bereich_info = {
                "x": x, "y": y, "seite": seite, "bild_breite": w,
                "bild_hoehe": h, "hinweis": hinweis,
                "modell_px": config.MODEL.input_size[0],
                # Pruefbuch (Stufe 1): letzten Stand SOFORT mitgeben. Das
                # Dict wird hier neu gebaut, das frische Urteil kommt erst
                # am Schleifenende - dazwischen sahen die Abfragen sonst
                # kein "pruef" (gleiche Falle wie einst bei "linie").
                "pruef": getattr(self, "_pruef_stand", None),
                # Alarmbuch + Systemstatus (Stufe 2): ebenfalls sofort da.
                "alarme": getattr(self, "_alarm_stand", None),
                "system": getattr(self, "_system_stand", "bereit"),
                # Rezept (Stufe 4): Name des aktiven Rezepts fuer den Kopf.
                "rezept": (self.rezeptbuch.aktiv_name()
                           if getattr(self, "rezeptbuch", None) else ""),
                # Leerbild je Kamera (Uhrzeit) fuer die Feed-Leisten.
                **self.leerbild_stand(),
            }

            # Ausschnitt in voller Aufloesung - das wird gespeichert.
            ausschnitt = frame[y:y + seite, x:x + seite].copy()
            n = 0
            self._roh_ausschnitt = ausschnitt
            # MEHRBILD (A2): nur stationaer und nur beim Betreiben - die
            # Lernfotos bleiben einzelne, echte Aufnahmen.
            if (self.profil == "stationaer" and self.mehrbild.anzahl > 1
                    and str(self.zustand.betriebsart) == "betreiben"):
                try:
                    ausschnitt = self.mehrbild.verarbeite(ausschnitt)
                    # Anzeige, Leerbild und Erkennung sehen dasselbe Bild.
                    frame[y:y + seite, x:x + seite] = ausschnitt
                except Exception:
                    pass
            self.zustand.bereich_info["mehrbild"] = self.mehrbild.als_dict()
            if getattr(self, "verteiler", None) is not None:
                self.zustand.bereich_info["verteiler"] = self.verteiler.als_dict()
                try:
                    self.zustand.bereich_info["verbund"] = self.lerner.verbund_info()
                except Exception:
                    pass

            # Schaerfe des Ausschnitts messen (Laplace-Varianz), jedes fuenfte
            # Bild. "Unscharf" war bisher ein Gefuehl - mit dieser Zahl ist es
            # eine Messung: faellt sie beim Fokussieren, liegt es an der
            # Kamera; bleibt sie hoch und das Bild sieht trotzdem weich aus,
            # liegt es an der Anzeige.
            self._takt = getattr(self, "_takt", 0) + 1
            if self._takt % 5 == 0 and ausschnitt.size:
                probe = cv2.resize(ausschnitt, (160, 160),
                                   interpolation=cv2.INTER_AREA)
                grau = cv2.cvtColor(probe, cv2.COLOR_BGR2GRAY)
                self._schaerfe = round(
                    float(cv2.Laplacian(grau, cv2.CV_64F).var()), 1)
            # JEDES Bild eintragen, nicht nur jedes fuenfte: bereich_info wird
            # oben jedes Bild neu aufgebaut, und vier von fuenf Abfragen sahen
            # deshalb keinen Wert - die Anzeige stand auf "-" und rot.
            if getattr(self, "_schaerfe", None) is not None:
                self.zustand.bereich_info["schaerfe"] = self._schaerfe
            # Diagnosefelder ueberleben den Neuaufbau: sie entstehen tief
            # in _erkenne, dieses dict wird aber JEDES Bild hier oben neu
            # gebaut - Abfragen sahen deshalb nie ein "D" und nie einen
            # Fehlertext, obwohl beides gesetzt wurde (2026-08-28).
            for feld in ("segmente", "erkennung_fehler", "detektor_fehler",
                         "inferenz_ms", "ablauf", "linie"):
                wert = getattr(self, "_diag_" + feld, None)
                if wert:
                    self.zustand.bereich_info[feld] = wert

            # Anzeige verkleinern; die Erkennung laeuft auf dieser kleineren
            # Fassung, weil die geometrische Strecke von mehr Pixeln nichts hat.
            f = min(1.0, self.anzeige_groesse / max(h, w))
            anzeige = cv2.resize(frame, (int(w * f), int(h * f)),
                                 interpolation=cv2.INTER_AREA) if f < 1.0 else frame.copy()
            ax, ay, aseite = int(x * f), int(y * f), max(8, int(seite * f))

            # Im Anlernen-Modus bleibt das Bild ruhig: nur der Aufnahmerahmen,
            # keine Erkennung. Wer Fotos sammelt, soll das Teil sehen und
            # nicht die Rahmen von etwas, das noch gar nicht gelernt ist.
            art = self.zustand.betriebsart
            # Zonen-Wahl-Modus (Bediener zieht gerade eine Zone auf,
            # rahmen_pause aktiv): Erkennung stumm schalten, damit im
            # Zonenfenster NUR der blanke Feed plus das Ziehrechteck zu
            # sehen ist. Objektrahmen lenkten ab und erweckten den
            # Eindruck, die Zone stimme nicht (Wunsch 2026-09-07).
            _zone_wahl = time.time() < getattr(self, "_rahmen_pause_bis", 0)
            erkennen = (self.mit_erkennung and art != "anlernen"
                        and not _zone_wahl)

            # Selbstheilung: ist der Detektor beim Start gescheitert (oder
            # still weggeblieben), alle 30 s nachladen - ein fehlender
            # Detektor darf kein Dauerzustand sein, der erst beim naechsten
            # Neustart auffaellt (2026-08-28).
            if (self.detektor is None
                    and time.time() - getattr(self, "_det_retry", 0) > 30):
                self._det_retry = time.time()
                pfad_neu = _DETEKTOR.get("datei")
                if not pfad_neu and Path("vorsa_m3.fbz").exists():
                    pfad_neu = "vorsa_m3.fbz"
                if pfad_neu:
                    threading.Thread(target=self.detektor_laden,
                                     args=(pfad_neu,), daemon=True).start()

            self._je_objekt = False
            if erkennen:
                try:
                    # Erkennung auf einer KONSTANTEN 640er-Fassung des
                    # echten Ausschnitts - nicht auf dem Anzeige-Crop.
                    # Der war bei kleiner Anzeige nur ~326 px: das duenne
                    # Ringrohr hatte 4 Pixel, die Wasserscheide schlug den
                    # oberen Bogen der SD zu, und keine Nachverarbeitung
                    # konnte das heilen (2026-08-28). Bei 640 px loest
                    # dieselbe Szene mit 86 %. Gezeichnet wird auf der
                    # 640er-Fassung und fuers Livebild herunterskaliert.
                    E = min(self.ERKENNUNG_PX, seite)
                    # Schrift bemisst sich an der ganzen Anzeige - gezeichnet
                    # wird jetzt DIREKT auf dem Anzeige-Crop (scharf), nicht
                    # mehr auf der 640er-Fassung mit anschliessendem
                    # Hochskalieren (matschige Rahmen, 2026-08-28).
                    self._font_ref = self.anzeige_groesse
                    # LINIENMODUS: die Zonen liegen im GANZEN Kamerabild,
                    # also muss dort auch die Erkennung das ganze Bild
                    # sehen - das quadratische Fenster gilt nur fuer
                    # Lernen und normale Erkennung (2026-09-03).
                    voll = self.linie is not None and (
                        self.linie.aktiv
                        or time.time() < getattr(self,
                                                 "_linie_ansicht_bis", 0))
                    self._erkenne_vollbild = voll
                    if voll:
                        # Die ZONEN sind die Erkennungsfenster der Linie:
                        # je Zone eine eigene Analyse in voller
                        # Aufloesung - unabhaengig vom Fenster des
                        # Erkennungs-Menues (2026-09-03).
                        n = 0
                        gesammelt = []
                        ah_, aw_ = anzeige.shape[:2]
                        status = {}
                        for zart, z in (("anliefer", self.linie.anliefer),
                                        ("abhol", self.linie.abhol)):
                            q = str(self.linie.quellen.get(zart, "haupt"))
                            if q != "haupt":
                                # Eigene USB-Kamera: das GANZE Zweitbild
                                # ist die Zone. Erkannt wird auf dem
                                # Zweitbild, gezeichnet auf eine eigene
                                # Leinwand, die als JPEG-Feed an die
                                # Splitansicht geht (1.7.0).
                                qb, fehler = self.zweitkamera.bild(q)
                                if qb is None:
                                    status[zart] = fehler
                                    self._linie_feeds.pop(zart, None)
                                    continue
                                qh, qw = qb.shape[:2]
                                # Roh-Vollbild fuer den Zonen-Ziehmodus
                                # im Feedfenster (TTL vom Client-GET).
                                if time.time() < (getattr(
                                        self, "_linie_roh_bis", {})
                                        or {}).get(zart, 0):
                                    rf = min(1.0, 640.0 / max(qw, qh, 1))
                                    rb = (cv2.resize(
                                        qb, (max(8, int(qw * rf)),
                                             max(8, int(qh * rf))),
                                        interpolation=cv2.INTER_AREA)
                                        if rf < 1.0 else qb)
                                    okr, bufr = cv2.imencode(
                                        ".jpg", rb,
                                        [cv2.IMWRITE_JPEG_QUALITY, 80])
                                    if okr:
                                        self._linie_feeds[zart + "_roh"] = {
                                            "jpg": bufr.tobytes(),
                                            "ts": time.time()}
                                # Zonen-Rechteck gilt RELATIV zum
                                # USB-Bild (im Feed gezogen, 1.7.1);
                                # zu klein/ungesetzt = ganzes Bild.
                                uzx0, uzy0 = int(z[0] * qw), int(z[1] * qh)
                                uzx1, uzy1 = int(z[2] * qw), int(z[3] * qh)
                                q_form = qb.shape
                                q_leer = None
                                if (uzx1 - uzx0 >= 48
                                        and uzy1 - uzy0 >= 48):
                                    q_leer = self._leerbild_crop(
                                        q, q_form, uzy0, uzy1, uzx0, uzx1)
                                    qb = qb[uzy0:uzy1, uzx0:uzx1]
                                    qh, qw = qb.shape[:2]
                                else:
                                    q_leer = self._leerbild_crop(
                                        q, q_form, 0, q_form[0], 0, q_form[1])
                                zf = min(1.0, 640.0 / max(qw, qh, 1))
                                lw = (cv2.resize(
                                    qb, (max(8, int(qw * zf)),
                                         max(8, int(qh * zf))),
                                    interpolation=cv2.INTER_AREA)
                                    if zf < 1.0 else qb.copy())
                                self._erkenne_offset = (
                                    z[0], z[1], z[2] - z[0], z[3] - z[1])
                                cm = max(qb.shape[:2])
                                gez, nz = self._erkenne(
                                    qb, qb,
                                    cm / max(1, min(self.ERKENNUNG_PX, cm)),
                                    leinwand=lw, leerbild=q_leer)
                                okj, buf = cv2.imencode(
                                    ".jpg", gez,
                                    [cv2.IMWRITE_JPEG_QUALITY, 80])
                                if okj:
                                    self._linie_feeds[zart] = {
                                        "jpg": buf.tobytes(),
                                        "ts": time.time()}
                                n += nz
                                gesammelt += list(getattr(
                                    self, "_linie_objekte", []))
                                continue
                            self._linie_feeds.pop(zart, None)
                            zx0, zy0 = int(z[0] * w), int(z[1] * h)
                            zx1, zy1 = int(z[2] * w), int(z[3] * h)
                            if zx1 - zx0 < 48 or zy1 - zy0 < 48:
                                continue
                            crop = frame[zy0:zy1, zx0:zx1]
                            h_leer = self._leerbild_crop(
                                "haupt", frame.shape, zy0, zy1, zx0, zx1)
                            azx0, azy0 = int(z[0] * aw_), int(z[1] * ah_)
                            azx1, azy1 = int(z[2] * aw_), int(z[3] * ah_)
                            lw = anzeige[azy0:azy1, azx0:azx1].copy()
                            self._erkenne_offset = (
                                z[0], z[1], z[2] - z[0], z[3] - z[1])
                            cm = max(crop.shape[:2])
                            gez, nz = self._erkenne(
                                crop, crop,
                                cm / max(1, min(self.ERKENNUNG_PX, cm)),
                                leinwand=lw, leerbild=h_leer)
                            anzeige[azy0:azy1, azx0:azx1] = gez
                            n += nz
                            gesammelt += list(getattr(
                                self, "_linie_objekte", []))
                        self._erkenne_offset = None
                        # BLICK 2 (1.9.27): zweite Kamera auf die Anlieferung,
                        # Urteile fusionieren. Nur wenn konfiguriert.
                        if str(self._blick2.get("quelle", "aus")) != "aus":
                            try:
                                gesammelt = self._blick2_fusion(
                                    gesammelt, frame, status)
                            except Exception as exc:
                                status["anliefer2"] = f"Blick 2: {exc}"[:90]
                                self._erkenne_offset = None
                        self._linie_objekte = gesammelt
                        self._linie_quellen_status = status
                    elif ausschnitt.size and E >= 32:
                        innen = cv2.resize(ausschnitt, (E, E),
                                           interpolation=cv2.INTER_AREA)
                        scharf = cv2.resize(
                            ausschnitt, (aseite, aseite),
                            interpolation=(cv2.INTER_AREA if seite > aseite
                                           else cv2.INTER_LINEAR))
                        m_leer = self._leerbild_crop(
                            "haupt", frame.shape, y, y + seite, x, x + seite)
                        gezeichnet, n = self._erkenne(
                            innen, ausschnitt, seite / max(E, 1),
                            leinwand=scharf, leerbild=m_leer)
                        anzeige[ay:ay + aseite, ax:ax + aseite] = gezeichnet
                except Exception as exc:
                    # NICHT dauerhaft abschalten: genau das hat am
                    # 2026-08-28 die Erkennung nach EINEM Fehler lautlos
                    # beerdigt ("0 Umrisse" fuer immer, Ganzbild-Rueckfall
                    # uebernahm). Stattdessen: Fehler anzeigen, ins Log
                    # schreiben, naechstes Bild wieder versuchen.
                    import traceback
                    text = f"{type(exc).__name__}: {exc}"[:140]
                    if getattr(self, "_diag_erkennung_fehler", None) != text:
                        traceback.print_exc()
                    self._diag_erkennung_fehler = text
                    n = 0
                else:
                    self._diag_erkennung_fehler = None
                    self.zustand.bereich_info.pop("erkennung_fehler", None)
            else:
                # Alte Treffer wegraeumen. Sie stehenzulassen waere schlimmer
                # als nichts anzuzeigen: die Fussleiste meldete dann eine
                # Objektzahl, die aus einem Bild von vorhin stammt.
                self.zustand.letzte_detektionen = []

            # Was hat der Chip gelernt? Ganzer Ausschnitt nur dann, wenn die
            # Geometrie keine Teile geliefert hat - sonst hat _erkenne schon
            # jedes Teil einzeln benannt, und ein Gesamturteil ueber drei
            # verschiedene Teile waere Unsinn.
            if (self.lerner is not None and self.lerner.klassen
                    and art != "anlernen" and not self._je_objekt
                    and not getattr(self, "_erkenne_vollbild", False)):
                roh = self.lerner.erkenne(ausschnitt)
                # Auch hier gilt: die Negativklasse konkurriert nicht. Ohne
                # diesen Filter kam "nichts" durch die Hintertuer des
                # Ganzbild-Rueckfalls doch wieder in die Balkenliste.
                if roh and roh.get("alle"):
                    ohne = self._ohne_negativ(roh)
                    leer = ohne is None or ohne.get("hintergrund")
                    roh = ohne if not leer else {
                        "klasse": "", "sicherheit": 0.0, "unklar": False,
                        "leer": True, "je_objekt": [], "alle": []}
                self.zustand.erkannt = roh
            elif art == "anlernen":
                self.zustand.erkannt = None

            if art == "betreiben":
                self._betrieb_buchen(ausschnitt)

            an = self.zustand.anzeige
            # Waehrend der Bediener Linien-Zonen aufzieht, stoert der
            # Aufnahmerahmen nur - er wird kurz pausiert (mit Zeitnetz,
            # falls der Browser das Ausschalten verschluckt).
            rahmen_pause = time.time() < getattr(self, "_rahmen_pause_bis", 0)
            # Im LINIENMODUS (Linie aktiv oder Splitansicht offen) hat
            # der Aufnahmerahmen aus Lernen/Erkennen nichts verloren:
            # die Zonen sind dort die Fenster, der Rahmen stand als
            # Geisterrechteck mitten im Zonen-Feed (2026-09-04).
            # NUR im Betreiben-Modus: im LERNMODUS braucht es den
            # Rahmen immer - er verschwand, wenn die Linie nebenbei
            # aktiv blieb (2026-09-05).
            linie_an = (self.linie is not None and art == "betreiben"
                        and (self.linie.aktiv
                             or time.time() < getattr(
                                 self, "_linie_ansicht_bis", 0)))
            if ((an.aufnahmerahmen or an.abdunkeln)
                    and not rahmen_pause and not linie_an):
                self._zeichne_rahmen(anzeige, ax, ay, aseite, seite,
                                     rahmen=an.aufnahmerahmen,
                                     abdunkeln=an.abdunkeln)

            # Linien-Modus: Band/Zone/Arm-Zustandsmaschine fuettern. Ohne
            # laufende Erkennung im Betreiben-Modus faehrt kein Band.
            if self.linie is not None:
                try:
                    ok = (bool(erkennen) and art == "betreiben"
                          and not getattr(self, "_diag_erkennung_fehler",
                                          None))
                    # Stufe 5: Konfidenzschwelle EINMAL hier anwenden -
                    # Linie, Teile-Anzeige und Pruefbuch sehen dasselbe.
                    self._linie_objekte = self._schwelle_anwenden(
                        getattr(self, "_linie_objekte", []))
                    self.linie.tick(
                        self._linie_objekte if ok else [],
                        erkennung_ok=ok)
                    ld = self.linie.als_dict()
                    # PRUEFBUCH (Stufe 1): Urteil JE TEIL aus den
                    # Uebergaengen der Zustandsmaschine ablesen - linie.py
                    # bleibt unangetastet. abgeraeumt -> gut/ausschuss,
                    # Stoerung "unbekanntes Teil" -> unbekannt.
                    try:
                        self._pruef_buchen(frame)
                    except Exception:
                        pass
                    # Teil-Details je Zone (zweigeteilte Teildetails im
                    # Linienmodus): das beste BENANNTE Teil, sonst der
                    # Hinweis auf ein unbekanntes. Die Zonen SIND im
                    # Linienmodus die Erkennungsfenster - eine Warnung
                    # vorm Erkennungs-Menue-Fenster ist damit obsolet.
                    objs = (getattr(self, "_linie_objekte", [])
                            if erkennen and art == "betreiben" else [])
                    at, au = self.linie._treffer(objs, self.linie.anliefer)
                    bt, bu = self.linie._treffer(objs, self.linie.abhol)
                    ld["anliefer_teil"] = at or ({"name": None}
                                                 if au else None)
                    ld["abhol_teil"] = bt or ({"name": None} if bu else None)
                    ld["quellen_status"] = dict(getattr(
                        self, "_linie_quellen_status", {}) or {})
                    # Vorhandene USB-Kameras (alle 10 s neu ermittelt) -
                    # die Oberflaeche baut daraus die Quellen-Auswahl.
                    if (time.time() - getattr(
                            self, "_usb_liste_ts", 0)) > 10.0:
                        try:
                            self._usb_liste = Zweitkamera.verfuegbare()
                        except Exception:
                            self._usb_liste = []
                        self._usb_liste_ts = time.time()
                    ld["usb_kameras"] = list(
                        getattr(self, "_usb_liste", []) or [])
                    # Blick 2 (Konfiguration + Fusionsergebnis).
                    ld["blick2"] = {**dict(self._blick2),
                                    **dict(getattr(self, "_fusion_info", {}))}
                    ld["einkamera"] = bool(getattr(self, "einkamera", True))
                    self.zustand.bereich_info["linie"] = ld
                    # Auch in die Persistenz: bereich_info wird am
                    # Schleifenanfang NEU gebaut, und bei niedriger
                    # Bildrate sah die Haelfte aller Abfragen sonst ein
                    # dict OHNE linie ("Server liefert keine Zonendaten"
                    # trotz richtigem Build, 2026-09-03).
                    self._diag_linie = ld
                    frisch = (time.time() - getattr(
                        self.linie, "_zone_frisch", 0)) < 6.0
                    if self.linie.aktiv or frisch:
                        ah, aw = anzeige.shape[:2]
                        for zart, z, name, farbe in (
                                ("anliefer", self.linie.anliefer,
                                 "ANLIEFERUNG", (255, 200, 0)),
                                ("abhol", self.linie.abhol,
                                 "ABHOLUNG", (94, 197, 34))):
                            # Zone mit eigener Kamera: kein Rahmen im
                            # Hauptbild - sie liegt dort nicht.
                            if str(self.linie.quellen.get(
                                    zart, "haupt")) != "haupt":
                                continue
                            p1 = (int(z[0] * aw), int(z[1] * ah))
                            p2 = (int(z[2] * aw), int(z[3] * ah))
                            cv2.rectangle(anzeige, p1, p2, farbe, 2)
                            cv2.putText(anzeige, name,
                                        (p1[0] + 6, p1[1] + 18),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                        farbe, 1, cv2.LINE_AA)
                except Exception as exc:
                    self.zustand.bereich_info["linie"] = {
                        "aktiv": False, "phase": "fehler",
                        "meldung": str(exc)[:90]}

            # LERNZONEN (1.9.29): im Lernmodus bei offener Splitansicht die
            # beiden Lern-Feeds fuellen (kein Erkennen, nur Ausschnitte).
            # Stabil (1.9.31): NICHT am Ansicht-Heartbeat haengen - der
            # kippt beim Zonenziehen/Umschalten kurz auf 0 und riss Luecken
            # in den Feed. Solange eine Lernzone aktiv ist, werden die Feeds
            # im Lernmodus durchgehend erzeugt (billig: zwei JPEG-Crops).
            if art == "anlernen" and any(
                    e.get("an") and e.get("quelle") != "aus"
                    for e in self._lernzonen.values()):
                try:
                    self._lernzonen_feeds(frame)
                except Exception:
                    pass
            try:
                self.zustand.bereich_info["lernzonen"] = self.lernzonen_stand()
            except Exception:
                pass

            # STATIONAERE PRUEFUNG (1.9.38): Knopf/API oder Automatik.
            if self.profil == "stationaer":
                try:
                    self._pruef_stationaer_takt(art)
                except Exception:
                    pass

            # PRUEFBUCH (Stufe 1): Live-Urteil des aktuellen Bilds plus
            # Sitzungsstatistik in jedem Zustand mitliefern.
            try:
                self._pruef_stand = self.pruefbuch.statistik(self._pruef_live())
                # Stufe 5: Einstellungen + Nachlern-Empfehlung mitgeben.
                ps = self._pruef_stand
                ps.update(self.pruef_einst())
                ps["profil"] = self.profil
                ps["mehrbild"] = self.mehrbild.als_dict()
                ps["letzte_pruefung"] = self._pruef_letzte
                if self.testsatz is not None:
                    ps["testsatz"] = self.testsatz.uebersicht()
                ps["szene_steht"] = bool(
                    self._pruef_szene_sig and self._pruef_szene_seit
                    and time.time() - self._pruef_szene_seit >= self.PRUEF_STILL_S)
                ps["szene_gebucht"] = bool(
                    self._pruef_szene_sig
                    and self._pruef_szene_sig == self._pruef_gebucht_sig)
                qu = ps.get("quote_unbekannt")
                ps["nachlernen"] = bool(
                    qu is not None and ps.get("gesamt", 0) >= 10
                    and qu > self.unbekannt_ziel)
                ps["unbekannt_archiv"] = [
                    e for e in ps.get("protokoll", [])
                    if e.get("urteil") == "unbekannt" and e.get("bild")][:6]
                self.zustand.bereich_info["pruef"] = ps
                # ALARMBUCH + SYSTEMSTATUS (Stufe 2)
                self._alarme_pruefen(art)
                self._alarm_stand = self.alarmbuch.kurz()
                self._system_stand = self._system_ableiten(art)
                self.zustand.bereich_info["alarme"] = self._alarm_stand
                self.zustand.bereich_info["system"] = self._system_stand
                if self.eaio is not None:
                    self.eaio.anlage(
                        bereit=(art == "betreiben"),
                        stoerung=bool((self._alarm_stand or {}).get("aktiv_alarm")))
                    self.zustand.bereich_info["eaio"] = {
                        "zustand": dict(self.eaio.zustand),
                        "simuliert": self.eaio.status()["simuliert"],
                        "treiber": self.eaio.cfg.get("treiber")}
            except Exception as exc:
                # Nicht stumm: ein Fehler hier hiesse "keine Kachel" ohne
                # Hinweis. Einmal ins Log, dann weiter.
                if getattr(self, "_pruef_fehler", "") != str(exc):
                    self._pruef_fehler = str(exc)
                    print(f"  Pruefbuch: {type(exc).__name__}: {exc}",
                          flush=True)

            dt = (time.perf_counter() - t0) * 1000
            self.zustand.messwerte.melde(dt, n)

            with self._lock:
                self._roh = frame
                self._ausschnitt = ausschnitt
                self._anzeige = anzeige

            # Nicht schneller als noetig - das Bild soll fluessig sein, aber
            # der Pi soll daneben noch fuer die Erkennung Luft haben.
            time.sleep(max(0.0, 0.033 - (time.perf_counter() - t0)))

    # Kantenlaenge, auf der die geometrische Suche laeuft. Mehr Pixel machen
    # die Kanten nicht besser, nur die Suche langsamer.
    ERKENNUNG_PX = 640

    # Hoechstens so viele Teile je Bild einzeln an den Chip - jedes kostet
    # einen Durchgang. Sechs mal wenige Millisekunden stoeren nicht.
    MAX_JE_OBJEKT = 6

    @staticmethod
    def _patch(ausschnitt: np.ndarray, box, kontur=None, faktor: float = 1.0,
               sperren=None, direkt_maske=None):
        """Quadrat um ein Teil aus dem vollaufgeloesten Ausschnitt.

        Rueckgabe (patch, maske). Die Maske entsteht aus der Wasserscheiden-
        Kontur des Teils - sie sagt, welcher Teil des Quadrats zu DIESEM
        Teil gehoert. Ohne sie greift das Freistellen im Patch die groesste
        Flaeche, und bei beruehrenden Teilen ist das der ganze Klumpen.

        `sperren`: Umrisse der NACHBAR-Teile (Anzeigemassstab). Sie werden
        aus der Maske ausgestanzt. Grund (2026-08-28): im Detektor-Kasten
        des verdeckten Karabiners lag immer auch ein Stueck SD-Karte - die
        Silhouette war dadurch verschmutzt und hiess bestenfalls
        "unbekannt". Ohne eigene Kontur dient der Kasten selbst als Umriss.
        """
        H, W = ausschnitt.shape[:2]
        halb = int(max(box.length, box.width) * 0.65) + 4
        x0, y0 = max(0, int(box.cx) - halb), max(0, int(box.cy) - halb)
        x1, y1 = min(W, int(box.cx) + halb), min(H, int(box.cy) + halb)
        if x1 - x0 < 12 or y1 - y0 < 12:
            return None, None
        patch = ausschnitt[y0:y1, x0:x1]
        maske = None
        if direkt_maske is not None:
            # Exakte Teilmaske im SUCH-Massstab (z. B. der Ring-Kranz des
            # Loch-Ankers): direkt uebernehmen, OHNE Otsu-Verschnitt und
            # ohne den Gefuellt-Rueckfall - der hat duenne Kraenze zu
            # Scheiben gemacht und Ringe als SD-Karte benannt (2026-08-28).
            sm = np.asarray(direkt_maske)
            sy0, sy1 = int(y0 / faktor), max(int(y1 / faktor), int(y0 / faktor) + 1)
            sx0, sx1 = int(x0 / faktor), max(int(x1 / faktor), int(x0 / faktor) + 1)
            sm = sm[max(0, sy0):sy1, max(0, sx0):sx1]
            if sm.size:
                maske = cv2.resize((sm > 0).astype(np.uint8) * 255,
                                   (patch.shape[1], patch.shape[0]),
                                   interpolation=cv2.INTER_NEAREST)
                if maske.sum() < 20 * 255:
                    maske = None
            return patch, maske
        eigener_faktor = faktor
        if kontur is None and sperren:
            kontur = np.asarray(box.corners())   # schon im Ausschnittmass
            eigener_faktor = 1.0
        if kontur is not None:
            p = (kontur.reshape(-1, 2).astype(np.float64) * eigener_faktor)
            p -= (x0, y0)
            maske = np.zeros(patch.shape[:2], np.uint8)
            cv2.fillPoly(maske, [np.rint(p).astype(np.int32)], 255)
            for s in (sperren or []):
                q = (np.asarray(s).reshape(-1, 2).astype(np.float64) * faktor
                     - (x0, y0))
                cv2.fillPoly(maske, [np.rint(q).astype(np.int32)], 0)

            # Loecher wiederherstellen. fillPoly malt die AUSSENkontur voll -
            # aus dem Karabinerring wurde eine Scheibe, waehrend die
            # Lernbilder den Ring MIT Loch zeigen. Also die gefuellte Flaeche
            # mit dem echten Vordergrund verschneiden: was innerhalb der
            # Kontur hell wie die Unterlage ist, ist Loch.
            grau = (cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
                    if patch.ndim == 3 else patch)
            rand = np.concatenate([grau[0, :], grau[-1, :],
                                   grau[:, 0], grau[:, -1]])
            diff = cv2.absdiff(grau, np.full_like(grau, int(np.median(rand))))
            _s, vg = cv2.threshold(diff, 0, 255,
                                   cv2.THRESH_BINARY | cv2.THRESH_OTSU)
            vg = cv2.morphologyEx(vg, cv2.MORPH_OPEN,
                                  np.ones((3, 3), np.uint8))
            fein = cv2.bitwise_and(maske, vg)
            # Nur uebernehmen, wenn der Kontrast das Teil ueberhaupt traegt -
            # sonst bliebe von der Maske nichts und die Aussenkontur ist
            # besser als gar nichts.
            if fein.sum() > 0.3 * maske.sum():
                maske = fein
            if maske.sum() < 20 * 255:
                maske = None
        return patch, maske

    def _negativ_namen(self) -> set:
        try:
            return {k.name for k in self.zustand.klassen.values()
                    if getattr(k, "negativ", False)}
        except Exception:
            return set()

    def _ohne_negativ(self, erg):
        """Chip-Urteil neu ausrechnen, OHNE die Negativklasse(n).

        None heisst: die Negativklasse gewinnt deutlich - das Teil ist
        Hintergrund oder Stoerteil und gehoert nicht in die Anzeige.
        Sonst: Sieger, Vorsprung und Unklar-Frage nur unter den echten
        Objekten - "nichts" darf ein Ergebnis schlucken, aber nie eines
        streitig machen.
        """
        alle = erg.get("alle") or []
        neg = self._negativ_namen()
        if not alle or not neg:
            return erg
        pos = sorted((a for a in alle if a["name"] not in neg),
                     key=lambda a: -a["anteil"])
        if not pos:
            return None
        n1 = max((a["anteil"] for a in alle if a["name"] in neg), default=0.0)
        p1 = float(pos[0]["anteil"])
        # Hintergrund NUR bei klarem Sieg der Negativklasse (>= 55 %). Ein
        # knapper nichts-Sieg ueber ein 45 %-Ringstueck ist KEIN Beweis fuer
        # Hintergrund - genau so verschwand der Karabiner zweimal als
        # "m/hintergrund" (Ablaufprotokoll 2026-08-28). Unentschieden heisst
        # jetzt: sichtbar bleiben als "unbekannt" - dann darf der Loch-Anker
        # oder der Detektor noch ran, und der Mensch SIEHT das Teil.
        if n1 >= p1 + 0.05 and p1 < 0.55:
            if n1 >= 0.55:
                # Klarer Drop - aber mit Zahlen, damit die Ablaufzeile
                # verraet, WIE klar er war (hg n62p41 statt "hintergrund").
                return {"hintergrund": True,
                        "n1": round(n1, 2), "p1": round(p1, 2)}
            return {"klasse": pos[0]["name"], "sicherheit": p1,
                    "vorsprung": 0.0, "unklar": False, "unbekannt": True,
                    "neg_knapp": round(n1, 2), "alle": pos}
        p2 = float(pos[1]["anteil"]) if len(pos) > 1 else 0.0
        vorsprung = (p1 - p2) / max(p1, 1e-6)
        schwelle = float(getattr(self.lerner, "UNBEKANNT_AB", 0.55))
        return {"klasse": pos[0]["name"], "sicherheit": p1,
                "vorsprung": round(vorsprung, 3), "unklar": vorsprung < 0.05,
                "unbekannt": p1 < schwelle, "alle": pos}

    @staticmethod
    def _gruppen_loch(d, dets, maske) -> bool:
        """Umschliesst die Beruehrungsgruppe um d ein Loch? (2026-08-28)

        d allein ist oft nur ein C (der Nachbar unterbricht den Ring).
        Darum: d plus alle Nachbarn, deren Box d fast beruehrt, als EINE
        Silhouette fuellen, leicht schliessen, die Aussenkontur voll
        ausmalen - und pruefen, ob darin Hintergrund eingeschlossen ist,
        der nicht am Bildrand haengt. Ein Zwickel zwischen eckigen Teilen
        bleibt unter der 5-%-Schwelle; ein Ring-Loch nicht.
        """
        import cv2 as _cv2
        if maske is None or d.contour is None:
            return False
        binaer = (np.asarray(maske) > 0).astype(np.uint8)
        H, W = binaer.shape[:2]
        region = np.zeros((H, W), np.uint8)
        _cv2.fillPoly(region, [d.contour.astype(np.int32)], 1)
        x, y, w, h = _cv2.boundingRect(d.contour.astype(np.int32))
        for n in dets:
            if n is d or n.contour is None:
                continue
            nx, ny, nw, nh = _cv2.boundingRect(n.contour.astype(np.int32))
            if (nx > x + w + 12 or nx + nw < x - 12
                    or ny > y + h + 12 or ny + nh < y - 12):
                continue
            _cv2.fillPoly(region, [n.contour.astype(np.int32)], 1)
        region = _cv2.morphologyEx(
            region, _cv2.MORPH_CLOSE,
            _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (9, 9)))
        rflaeche = int(region.sum())
        if rflaeche < 400:
            return False
        konturen, _ = _cv2.findContours(region, _cv2.RETR_EXTERNAL,
                                        _cv2.CHAIN_APPROX_SIMPLE)
        voll = np.zeros_like(region)
        _cv2.drawContours(voll, konturen, -1, 1, thickness=-1)
        loecher = (voll & (1 - binaer)).astype(np.uint8)
        nl, _, sl, _ = _cv2.connectedComponentsWithStats(loecher, 8)
        for i in range(1, nl):
            if (sl[i, _cv2.CC_STAT_AREA] >= 0.05 * rflaeche
                    and sl[i, _cv2.CC_STAT_LEFT] > 0
                    and sl[i, _cv2.CC_STAT_TOP] > 0
                    and sl[i, _cv2.CC_STAT_LEFT]
                        + sl[i, _cv2.CC_STAT_WIDTH] < W
                    and sl[i, _cv2.CC_STAT_TOP]
                        + sl[i, _cv2.CC_STAT_HEIGHT] < H):
                return True
        return False

    @staticmethod
    def _loch_anker(dets, maske, bewerte, lochname=None, loch_werte=None):
        """Zerlegt unbenannte Klumpen anhand ihres LOCHS (2026-08-28).

        Bei satter Ueberlappung (SD liegt AUF dem Karabiner) hat die
        Wasserscheide keine Trennlinie und der Detektor raet. Aber das
        LOCH des Rings ist fast immer sichtbar - und ein grosses inneres
        Loch ist der staerkste geometrische Anker, den es gibt: um das
        Loch wird ein Ring-Kandidat gelegt (Loch aufgeweitet, mit dem
        Vordergrund verschnitten), der Rest ist der zweite Kandidat.
        Beide muessen sich dem Chip stellen; nur wenn der Ring benennbar
        ist, wird zerlegt. Deterministisch, ohne Detektor.
        """
        import cv2 as _cv2
        from ..detection import Detection, Occlusion, OrientedBox
        if maske is None or bewerte is None:
            return dets
        binaer = (np.asarray(maske) > 0).astype(np.uint8)
        H, W = binaer.shape[:2]
        aus = []
        for d in dets:
            c = d.meta.get("chip") or {}
            unben = (not c) or c.get("unbekannt") or c.get("unklar")
            # LOCH-VETO (2026-08-28): auch ein BENANNTES Teil kommt auf den
            # Pruefstand, wenn seine Klasse laut Loch-Signatur FLACH ist
            # (kein Loch gelernt), die Silhouette aber ein grosses Loch
            # umschliesst. "SD Karte 56 %" um einen Karabiner-Ring ist
            # physikalisch unmoeglich - genau der Fall m/SD Kart56.
            kl = c.get("klasse")
            falschflach = (not unben and lochname and kl
                           and kl != lochname
                           and float((loch_werte or {}).get(kl, 0.0)) < 0.2)
            if (not unben and not falschflach) or d.contour is None:
                aus.append(d)
                continue
            region = np.zeros((H, W), np.uint8)
            _cv2.fillPoly(region, [d.contour.astype(np.int32)], 1)
            rflaeche = int(region.sum())
            if rflaeche < 400:
                aus.append(d)
                continue
            # Innere Loecher: Hintergrund INNERHALB der Region.
            loecher = (region & (1 - binaer)).astype(np.uint8)
            nl, ll, sl, _ = _cv2.connectedComponentsWithStats(loecher, 8)
            kand = [i for i in range(1, nl)
                    if sl[i, _cv2.CC_STAT_AREA] >= 0.06 * rflaeche
                    # Randberuehrende "Loecher" sind Buchten, keine Loecher.
                    and sl[i, _cv2.CC_STAT_LEFT] > 0
                    and sl[i, _cv2.CC_STAT_TOP] > 0
                    and sl[i, _cv2.CC_STAT_LEFT] + sl[i, _cv2.CC_STAT_WIDTH] < W
                    and sl[i, _cv2.CC_STAT_TOP] + sl[i, _cv2.CC_STAT_HEIGHT] < H]
            if not kand:
                aus.append(d)
                continue
            gi = max(kand, key=lambda i: sl[i, _cv2.CC_STAT_AREA])
            loch = (ll == gi).astype(np.uint8)
            # Rohrdicke NICHT schaetzen (das Loch kann angeschnitten sein,
            # dann ueberschaetzt jede Formel): mehrere Dicken probieren
            # und den Chip die beste Fassung waehlen lassen.
            rw = None
            ring = ringkontur = ringbox = None
            for dicke in (8, 12, 16, 22):
                kern = _cv2.getStructuringElement(
                    _cv2.MORPH_ELLIPSE, (2 * dicke + 1, 2 * dicke + 1))
                r = (_cv2.dilate(loch, kern) & binaer
                     & region).astype(np.uint8)
                if int(r.sum()) < 200:
                    continue
                rk, _h1 = _cv2.findContours(r, _cv2.RETR_EXTERNAL,
                                            _cv2.CHAIN_APPROX_SIMPLE)
                if not rk:
                    continue
                kontur = max(rk, key=_cv2.contourArea)
                box = OrientedBox.from_cv_rect(_cv2.minAreaRect(kontur))
                w = bewerte(box, None, direkt_maske=r * 255)
                if w is not None and (rw is None or w[0] > rw[0]):
                    rw, ring, ringkontur, ringbox = w, r, kontur, box
            # Benennung ueber die LOCH-SIGNATUR: kennt der Verbund genau
            # eine Klasse mit umschlossenem Loch, IST der Ring diese
            # Klasse - der sichtbare Halbring ist zu deformiert, als dass
            # Aehnlichkeit ihn tragen koennte (23 % im Sandkasten). Die
            # Chip-Quote bleibt als Bonus, nicht als Huerde.
            if ring is None:
                aus.append(d)
                continue
            if lochname is not None:
                sicher = max(float(rw[0]) if rw else 0.0, 0.58)
                rw = (sicher, {"klasse": lochname, "sicherheit": sicher,
                               "unklar": False, "unbekannt": False,
                               "alle": [],
                               "vorsprung": 0.2})
            elif rw is None or rw[0] < 0.55:
                aus.append(d)
                continue
            # Ring benennbar! Rest der Region als zweiter Kandidat.
            rest = ((region & binaer) & (1 - ring)).astype(np.uint8)
            rest = _cv2.morphologyEx(rest, _cv2.MORPH_OPEN,
                                     np.ones((3, 3), np.uint8))
            ringdet = Detection(box=ringbox, contour=ringkontur,
                                score=float(rw[0]),
                                occlusion=Occlusion.PARTIAL, source="merged",
                                meta={"chip": rw[1],
                                      "fusion": "Loch-Anker: Ring"})
            neu_dets = [ringdet]
            kk, _h2 = _cv2.findContours(rest, _cv2.RETR_EXTERNAL,
                                        _cv2.CHAIN_APPROX_SIMPLE)
            for k in sorted(kk, key=_cv2.contourArea, reverse=True)[:2]:
                if _cv2.contourArea(k) < 0.08 * rflaeche:
                    continue
                kbox = OrientedBox.from_cv_rect(_cv2.minAreaRect(k))
                einzel = np.zeros_like(rest)
                _cv2.fillPoly(einzel, [k.astype(np.int32)], 1)
                kw = bewerte(kbox, None,
                             direkt_maske=(einzel & rest) * 255)
                neu_dets.append(Detection(
                    box=kbox, contour=k,
                    score=float(kw[0]) if kw else 0.3,
                    occlusion=Occlusion.TOUCHING, source="merged",
                    meta=({"chip": kw[1]} if kw and kw[1] else {})
                    | {"fusion": "Loch-Anker: Rest"}))
            aus.extend(neu_dets)
        return aus

    @staticmethod
    def _lose_taufe(dets, maske, lochname):
        """Vereint UNBENANNTE Splitter einer Beruehrungsgruppe zu EINEM
        Stueck und tauft es auf die Loch-Klasse (2026-08-28).

        Ausloeser: mit jeder neu angelernten Klasse verteilen sich die
        Aehnlichkeiten neu - Bogen-Stuecke, die eben noch 60 % hatten,
        fallen auf 53 % und bleiben unbenannt. Unbenannte werden aber
        nicht wiedervereint, und so zerfiel die Szene in vier Rahmen.
        Die Physik bleibt: umschliesst die Gruppensilhouette (Splitter
        plus beruehrende benannte Nachbarn) ein Loch, und es gibt genau
        eine Loch-Klasse, dann SIND die Splitter dieses Teil. Schutz:
        keine Taufe, wenn irgendwo schon ein benanntes Stueck der
        Loch-Klasse steht (ein Fremdteil daneben erbt sonst den Namen).
        """
        import cv2 as _cv2
        from ..detection import Detection, Occlusion, OrientedBox
        if maske is None or not lochname:
            return dets
        for d in dets:
            c = d.meta.get("chip") or {}
            if (c.get("klasse") == lochname and not c.get("unbekannt")
                    and not c.get("unklar")):
                return dets
        unben = [d for d in dets if d.contour is not None
                 and (lambda c: (not c) or c.get("unbekannt")
                      or c.get("unklar"))(d.meta.get("chip") or {})]
        if not unben:
            return dets
        unben_ids = {id(d) for d in unben}
        # Beruehrungsgruppen unter den Unbenannten (single-link, Boxen).
        def _bb(d):
            return _cv2.boundingRect(d.contour.astype(np.int32))
        gruppen = []
        for d in unben:
            x, y, w, h = _bb(d)
            ziel = None
            for g in gruppen:
                for e in g:
                    ex, ey, ew, eh = _bb(e)
                    if not (ex > x + w + 12 or ex + ew < x - 12
                            or ey > y + h + 12 or ey + eh < y - 12):
                        ziel = g
                        break
                if ziel:
                    break
            (ziel.append(d) if ziel else gruppen.append([d]))
        binaer = (np.asarray(maske) > 0).astype(np.uint8)
        H, W = binaer.shape[:2]
        kern = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (9, 9))
        aus = [d for d in dets if id(d) not in unben_ids]
        for g in gruppen:
            region = np.zeros((H, W), np.uint8)
            for e in g:
                _cv2.fillPoly(region, [e.contour.astype(np.int32)], 1)
            region = _cv2.morphologyEx(region, _cv2.MORPH_CLOSE, kern)
            # Loch-Pruefung auf der Silhouette inkl. beruehrender
            # BENANNTER Nachbarn - die SD unterbricht ja den Ring.
            gx, gy, gw, gh = _cv2.boundingRect(region)
            voll_q = region.copy()
            for n in dets:
                if id(n) in unben_ids or n.contour is None:
                    continue
                nx, ny, nw2, nh2 = _cv2.boundingRect(
                    n.contour.astype(np.int32))
                if (nx > gx + gw + 12 or nx + nw2 < gx - 12
                        or ny > gy + gh + 12 or ny + nh2 < gy - 12):
                    continue
                _cv2.fillPoly(voll_q, [n.contour.astype(np.int32)], 1)
            konturen, _h = _cv2.findContours(voll_q, _cv2.RETR_EXTERNAL,
                                             _cv2.CHAIN_APPROX_SIMPLE)
            voll = np.zeros_like(voll_q)
            _cv2.drawContours(voll, konturen, -1, 1, thickness=-1)
            loecher = (voll & (1 - binaer)).astype(np.uint8)
            nl, _l, sl, _z = _cv2.connectedComponentsWithStats(loecher, 8)
            vollflaeche = max(int(voll.sum()), 1)
            hat_loch = any(
                sl[i, _cv2.CC_STAT_AREA] >= 0.05 * vollflaeche
                and sl[i, _cv2.CC_STAT_LEFT] > 0
                and sl[i, _cv2.CC_STAT_TOP] > 0
                and sl[i, _cv2.CC_STAT_LEFT]
                    + sl[i, _cv2.CC_STAT_WIDTH] < W
                and sl[i, _cv2.CC_STAT_TOP]
                    + sl[i, _cv2.CC_STAT_HEIGHT] < H
                for i in range(1, nl))
            kk, _h2 = _cv2.findContours(region, _cv2.RETR_EXTERNAL,
                                        _cv2.CHAIN_APPROX_SIMPLE)
            if not hat_loch or not kk:
                aus.extend(g)
                continue
            gross = max(kk, key=_cv2.contourArea)
            beste = max((float((e.meta.get("chip") or {})
                               .get("sicherheit") or 0.0) for e in g),
                        default=0.0)
            sicher = max(beste, 0.58)
            aus.append(Detection(
                box=OrientedBox.from_cv_rect(_cv2.minAreaRect(gross)),
                contour=gross.reshape(-1, 2),
                score=sicher,
                occlusion=Occlusion.PARTIAL, source="merged",
                meta={"chip": {"klasse": lochname, "sicherheit": sicher,
                               "vorsprung": 0.2},
                      "fusion": "Lose-Taufe: Loch-Signatur der Gruppe"}))
        return aus

    @staticmethod
    def _loch_filter(dets, maske, mindest_anteil: float = 0.20):
        """Entfernt Rahmen, deren Flaeche kaum Vordergrund enthaelt.

        Schwelle bewusst niedrig: ein duenner Ring hat selbst nur maessige
        Fuellung (Aussenkontur schliesst sein Loch ein), ein echtes Loch
        dagegen praktisch null Vordergrund."""
        if maske is None or not dets:
            return dets
        binaer = (np.asarray(maske) > 0).astype(np.uint8)
        H, W = binaer.shape[:2]
        aus = []
        for d in dets:
            if d.contour is None:
                aus.append(d)
                continue
            probe = np.zeros((H, W), np.uint8)
            cv2.fillPoly(probe, [d.contour.astype(np.int32)], 1)
            flaeche = int(probe.sum())
            if flaeche < 1:
                continue
            anteil = float((binaer & probe).sum()) / flaeche
            if anteil >= mindest_anteil:
                aus.append(d)
        return aus

    @staticmethod
    def _weichkanten_filter(dets, bild, schwelle: float = 30.0):
        """Verwirft Rahmen, deren Umriss nur weiche Kanten hat.

        Massstab ist das 70. Perzentil des Gradientenbetrags entlang der
        Kontur: ein echtes Teil hat mindestens ein Drittel harte
        Aussenkante (auch wenn der Rest Wasserscheiden-Trennlinie im
        Klumpen ist), ein Schatten-Phantom hat NIRGENDS eine harte
        Kante. Konturpunkte am Bildrand zaehlen nicht mit."""
        if not dets:
            return dets
        # FARBBEWUSST (2026-09-08): Gradient je Farbkanal, das Maximum
        # zaehlt. Im Grau hat "schwarze Karte auf dunkelgruenem Band"
        # kaum eine Kante - der Waechter warf das ganze Teil als Schatten-
        # Phantom weg. Im Gruen-Kanal ist dieselbe Kante hart. Schatten
        # (gleicher Farbton, nur dunkler) bleiben in ALLEN Kanaelen weich.
        glatt = cv2.GaussianBlur(bild, (3, 3), 0)
        kanaele = ([glatt] if glatt.ndim == 2
                   else [glatt[:, :, i] for i in range(glatt.shape[2])])
        mag = None
        for kn in kanaele:
            gx = cv2.Sobel(kn, cv2.CV_32F, 1, 0, ksize=3)
            gy = cv2.Sobel(kn, cv2.CV_32F, 0, 1, ksize=3)
            m = cv2.magnitude(gx, gy)
            mag = m if mag is None else np.maximum(mag, m)
        # Kontur sitzt auf dem Maskenrand, der Gradient 1-2 px daneben:
        # lokales Maximum in der 3er-Nachbarschaft nehmen.
        mag = cv2.dilate(mag, np.ones((3, 3), np.float32))
        H, W = mag.shape[:2]
        aus = []
        for d in dets:
            if d.contour is None:
                aus.append(d)
                continue
            pts = np.asarray(d.contour).reshape(-1, 2)
            xs = np.clip(pts[:, 0].astype(int), 0, W - 1)
            ys = np.clip(pts[:, 1].astype(int), 0, H - 1)
            innen = (xs > 2) & (xs < W - 3) & (ys > 2) & (ys < H - 3)
            if int(innen.sum()) >= 8:
                xs, ys = xs[innen], ys[innen]
            werte = mag[ys, xs]
            if werte.size and float(np.percentile(werte, 70)) >= schwelle:
                aus.append(d)
        return aus

    @staticmethod
    def _fehlende_ergaenzen(dets, teil_masken, min_flaeche: int = 200):
        """Rahmen fuer Wasserscheiden-Stuecke, die der Fit verworfen hat."""
        from ..detection import Detection, Occlusion, OrientedBox
        aus = list(dets)
        for m in teil_masken or []:
            mb = (np.asarray(m) > 0).astype(np.uint8)
            if int(mb.sum()) < min_flaeche:
                continue
            xs = np.flatnonzero(mb.any(axis=0))
            ys = np.flatnonzero(mb.any(axis=1))
            cx = float((xs[0] + xs[-1]) / 2)
            cy = float((ys[0] + ys[-1]) / 2)
            gedeckt = False
            for d in aus:
                dx = abs(cx - d.box.cx)
                dy = abs(cy - d.box.cy)
                if (dx < d.box.length * 0.6 and dy < d.box.length * 0.6
                        and d.contour is not None
                        and cv2.pointPolygonTest(
                            d.contour, (cx, cy), False) >= 0):
                    gedeckt = True
                    break
            if gedeckt:
                continue
            konturen, _h = cv2.findContours(mb, cv2.RETR_EXTERNAL,
                                            cv2.CHAIN_APPROX_SIMPLE)
            if not konturen:
                continue
            k = max(konturen, key=cv2.contourArea)
            aus.append(Detection(
                box=OrientedBox.from_cv_rect(cv2.minAreaRect(k)),
                contour=k, score=0.3, occlusion=Occlusion.UNRESOLVED,
                source="nachgereicht"))
        return aus

    def _hypothesen_entscheiden(self, dets, maske, bewerte, px_per_mm: float):
        """HYPOTHESEN (SE Inspect A3, 1.9.41): je zusammenhaengender
        Flaeche alle Deutungen aufzaehlen, Chip bewertet rundenweise alle
        Auftraege auf einmal (bewerte_viele), beste Deutung gewinnt."""
        import cv2 as _cv2
        from .. import hypothesen as HY
        dets = list(dets)
        if len(dets) < 2:
            self._diag_hypothesen = {"flaechen": 0}
            return dets
        binaer = (np.asarray(maske) > 0).astype(np.uint8)
        _n, lab = _cv2.connectedComponents(binaer)
        H, W = lab.shape

        def flaechen_id(d):
            if d.contour is None:
                px, py = int(d.box.cx), int(d.box.cy)
                return int(lab[py, px]) if 0 <= px < W and 0 <= py < H else 0
            p = d.contour.reshape(-1, 2)
            werte = lab[np.clip(p[:, 1], 0, H - 1), np.clip(p[:, 0], 0, W - 1)]
            werte = werte[werte > 0]
            return int(np.bincount(werte).argmax()) if len(werte) else 0

        gruppen = {}
        for d in dets:
            gruppen.setdefault(flaechen_id(d), []).append(d)
        verteiler = getattr(self, "verteiler", None)
        bewerte_viele = (verteiler.bewerte_viele(bewerte) if verteiler is not None
                         else HY.sequentiell(bewerte))
        neu, diag = [], []
        for fid, gruppe in gruppen.items():
            if fid == 0 or len(gruppe) == 1:
                neu.extend(gruppe)
                continue
            try:
                blob = (lab == fid).astype(np.uint8) * 255
                best, info = HY.hypothesen_waehlen(
                    gruppe, lab.shape, bewerte_viele, px_per_mm, blob_maske=blob,
                    nominal=False)
                if best is None:
                    neu.extend(gruppe)
                    continue
                neu.extend(HY.hypothese_zu_detektionen(best, gruppe))
                diag.append({"stuecke": len(gruppe), "gewaehlt": best.name,
                             "teile": len(best.teile), "score": round(best.score, 3),
                             "runden": info.get("runden"), "auftraege": info.get("auftraege"),
                             "top": info.get("scores", [])[:3]})
            except Exception as exc:
                neu.extend(gruppe)
                diag.append({"stuecke": len(gruppe), "fehler": str(exc)[:80]})
        self._diag_hypothesen = {"flaechen": len(diag), "entscheidungen": diag}
        return neu

    @staticmethod
    def _verschmelze(dets, maske=None, deckung: float = 0.45, bewerte=None):
        """Fasst Rahmen zusammen, die zu EINEM Teil gehoeren.

        Grundlage ist die Vordergrundmaske: die Wasserscheide zerschneidet
        nur, was vorher EINE zusammenhaengende Flaeche war. Fuer jede
        Flaeche mit mehreren Stuecken gibt es zwei Deutungen:

          a) EIN Teil, von der Wasserscheide faelschlich zerlegt
          b) MEHRERE Teile, die sich beruehren oder ueberlappen

        Geometrie allein kann das nicht unterscheiden - hier hat sie erst
        SD-Karten zerstueckelt und dann SD-auf-Karabiner zusammengeklebt.
        Deshalb entscheidet, wenn vorhanden, der Chip: `bewerte(box)` liefert
        die Uebereinstimmung mit dem besten gelernten Muster. Passt das
        Ganze besser als seine Stuecke, ist es ein Teil; passen die Stuecke
        besser, sind es mehrere. Ohne Chip gewinnt Deutung a - fuer die
        reine Umrissanzeige das kleinere Uebel.
        """
        import cv2 as _cv2
        from ..detection import Occlusion, OrientedBox
        dets = list(dets)

        if maske is not None and len(dets) > 1:
            binaer = (np.asarray(maske) > 0).astype(np.uint8)
            _n, lab = _cv2.connectedComponents(binaer)
            H, W = lab.shape

            def flaechen_id(d):
                if d.contour is None:
                    px, py = int(d.box.cx), int(d.box.cy)
                    return int(lab[py, px]) if 0 <= px < W and 0 <= py < H else 0
                p = d.contour.reshape(-1, 2)
                werte = lab[np.clip(p[:, 1], 0, H - 1),
                            np.clip(p[:, 0], 0, W - 1)]
                werte = werte[werte > 0]
                return int(np.bincount(werte).argmax()) if len(werte) else 0

            gruppen = {}
            for d in dets:
                gruppen.setdefault(flaechen_id(d), []).append(d)

            neu = []
            for fid, gruppe in gruppen.items():
                if fid == 0 or len(gruppe) == 1:
                    neu.extend(gruppe)
                    continue

                basis = max(gruppe, key=lambda d: d.box.area)
                punkte = np.concatenate([d.box.corners() for d in gruppe])
                ganz_box = OrientedBox.from_cv_rect(_cv2.minAreaRect(punkte))

                einzeln = ganz = None
                if bewerte is not None:
                    # Jedes Stueck MIT seiner Wasserscheiden-Kontur bewerten:
                    # nur so sieht der Chip die Einzelsilhouette und nicht
                    # bei jedem Stueck denselben Klumpen.
                    teile_w = [bewerte(d.box, d.contour) for d in gruppe]
                    einzeln = [w for w in teile_w if w is not None]
                    ganz = bewerte(ganz_box)
                g_w = (ganz[0] if isinstance(ganz, tuple) else 0.0) \
                    if ganz is not None else 0.0
                # Stuecke gewinnen, wenn sie klar besser passen ODER wenn
                # das Ganze unbenennbar ist (unter der Neuheitsschwelle),
                # waehrend ein Stueck benennbar waere - ein "unbekanntes
                # Ganzes" darf benannte Teile nicht schlucken (2026-08-28,
                # Beruehrungsszene: 'Karabiner 60%' um BEIDE Teile).
                if (einzeln and ganz is not None
                        and (max(w for w, _e in einzeln) > g_w + 0.04
                             or (g_w < 0.55
                                 <= max(w for w, _e in einzeln)))):
                    # Die Stuecke passen besser: mehrere Teile. Ergebnisse
                    # merken, damit der Chip nicht doppelt gefragt wird, und
                    # das schwaechere Stueck als beruehrt kennzeichnen.
                    bestes = max(w for w, _e in einzeln)
                    for d, w in zip(gruppe, teile_w):
                        if w is None:
                            continue
                        if w[1] is not None:
                            d.meta["chip"] = w[1]
                        if w[0] < bestes:
                            d.occlusion = max(d.occlusion, Occlusion.TOUCHING)
                    # TEILVERSCHMELZUNG (2026-08-28): die Erosions-Trennung
                    # zersplittert duenne Ringe in Boegen. Regel: Stuecke
                    # DERSELBEN Klasse in einer Beruehrungsgruppe gehoeren
                    # zusammen (drei Ringboegen sind EIN Karabiner);
                    # Unbenennbare schlagen sich der naechstgelegenen
                    # Gruppe zu. Jede Vereinigung muss sich dem Chip
                    # stellen: nur wenn sie mindestens so gut passt wie ihr
                    # bestes Einzelstueck, ersetzt sie die Stuecke.
                    def sammel(mitglieder):
                        leinwand = np.zeros(lab.shape, np.uint8)
                        for d in mitglieder:
                            poly = (d.contour if d.contour is not None
                                    else d.box.corners())
                            _cv2.fillPoly(
                                leinwand,
                                [np.asarray(poly).astype(np.int32)], 255)
                        leinwand = _cv2.morphologyEx(
                            leinwand, _cv2.MORPH_CLOSE,
                            np.ones((9, 9), np.uint8))
                        kk, _hh = _cv2.findContours(
                            leinwand, _cv2.RETR_EXTERNAL,
                            _cv2.CHAIN_APPROX_SIMPLE)
                        if not kk:
                            return None, None
                        sk = max(kk, key=_cv2.contourArea)
                        return sk, OrientedBox.from_cv_rect(
                            _cv2.minAreaRect(sk))

                    def klasse_von(w):
                        if w is None or w[0] < 0.55 or w[1] is None:
                            return None
                        return w[1].get("klasse")

                    gruppenk = {}
                    for d, w in zip(gruppe, teile_w):
                        gruppenk.setdefault(klasse_von(w), []).append((d, w))
                    lose = gruppenk.pop(None, [])
                    lose_dets = [d for d, _ in lose]
                    # Lose (unbenennbare) Stuecke: ERST untereinander
                    # vereinen und vom Chip benennen lassen - drei Boegen
                    # ergeben oft erst gemeinsam einen Karabiner. Blind an
                    # die naechste Namensgruppe kleben hat den ganzen
                    # Klumpen zur 'SD Karte' gemacht (2026-08-28).
                    if len(lose_dets) >= 2:
                        l_sk, l_sbox = sammel(lose_dets)
                        l_w = bewerte(l_sbox, l_sk) if l_sk is not None else None
                        if l_w is not None and l_w[0] >= 0.55:
                            traeger = lose_dets[0]
                            traeger.box = l_sbox
                            traeger.contour = l_sk
                            traeger.meta["chip"] = l_w[1]
                            traeger.source = "merged"
                            traeger.occlusion = max(traeger.occlusion,
                                                    Occlusion.TOUCHING)
                            kname = (l_w[1] or {}).get("klasse")
                            gruppenk.setdefault(kname, []).append(
                                (traeger, l_w))
                            lose_dets = []
                    # Zweiter Versuch: testweise an eine Namensgruppe
                    # anfuegen - uebernommen nur, wenn der Chip die
                    # Anfuegung benennen kann.
                    if lose_dets and gruppenk:
                        beste = None
                        for k, mitglieder in gruppenk.items():
                            sk_a, sb_a = sammel(
                                [d for d, _ in mitglieder] + lose_dets)
                            w_a = (bewerte(sb_a, sk_a)
                                   if sk_a is not None else None)
                            if w_a and (beste is None or w_a[0] > beste[0][0]):
                                beste = (w_a, k, sk_a, sb_a)
                        if beste and beste[0][0] >= 0.55:
                            w_a, k, sk_a, sb_a = beste
                            traeger = gruppenk[k][0][0]
                            traeger.box = sb_a
                            traeger.contour = sk_a
                            traeger.meta["chip"] = w_a[1]
                            traeger.source = "merged"
                            traeger.occlusion = max(traeger.occlusion,
                                                    Occlusion.TOUCHING)
                            gruppenk[k] = [(traeger, w_a)]
                            lose_dets = []
                    # Was uebrig bleibt, bleibt ehrlich einzeln (unbekannt).
                    ergebnis = list(lose_dets)
                    for kname, mitglieder in gruppenk.items():
                        if len(mitglieder) == 1:
                            ergebnis.append(mitglieder[0][0])
                            continue
                        sk, sbox = sammel([d for d, _ in mitglieder])
                        if sk is None:
                            ergebnis.extend(d for d, _ in mitglieder)
                            continue
                        # Gleichnamige Stuecke werden IMMER vereint - drei
                        # "Karabiner" im Bild sind Unsinn. Der Chip hat hier
                        # kein Vetorecht: eine C-foermige Vereinigung passt
                        # auf kein Template, ihre Boegen einzeln schon
                        # (38 % vs 83 %, Sandkasten 2026-08-28). Das Label
                        # kommt vom besten Mitglied, die Vereinigung liefert
                        # nur den ehrlichen Rahmen.
                        beste_w = max((w for _d, w in mitglieder
                                       if w is not None),
                                      key=lambda w: w[0], default=None)
                        traeger = mitglieder[0][0]
                        traeger.box = sbox
                        traeger.contour = sk
                        if beste_w is not None and beste_w[1] is not None:
                            traeger.meta["chip"] = beste_w[1]
                        traeger.source = "merged"
                        traeger.occlusion = max(traeger.occlusion,
                                                Occlusion.TOUCHING)
                        ergebnis.append(traeger)
                    neu.extend(ergebnis)
                    continue

                # Ein Teil: vereinen, Umriss = echter Flaechenumriss.
                basis.box = ganz_box
                basis.score = max(d.score for d in gruppe)
                basis.occlusion = min(d.occlusion for d in gruppe)
                if ganz is not None and ganz[1] is not None:
                    basis.meta["chip"] = ganz[1]
                konturen, _h = _cv2.findContours(
                    (lab == fid).astype(np.uint8), _cv2.RETR_EXTERNAL,
                    _cv2.CHAIN_APPROX_SIMPLE)
                if konturen:
                    basis.contour = max(konturen, key=_cv2.contourArea)
                neu.append(basis)
            dets = neu

        # Danach noch der Deckungs-Durchgang fuer sich ueberlappende Rahmen
        # verschiedener Flaechen (Glanzpunkt-Bruchstuecke ohne Maskenbezug).
        geaendert = True
        while geaendert and len(dets) > 1:
            geaendert = False
            for i in range(len(dets)):
                for j in range(i + 1, len(dets)):
                    a, b = dets[i], dets[j]
                    ok, schnitt = _cv2.rotatedRectangleIntersection(
                        a.box.to_cv_rect(), b.box.to_cv_rect())
                    if ok == _cv2.INTERSECT_NONE or schnitt is None:
                        continue
                    flaeche = float(_cv2.contourArea(_cv2.convexHull(schnitt)))
                    if flaeche / max(min(a.box.area, b.box.area), 1e-6) < deckung:
                        continue
                    punkte = np.concatenate([a.box.corners(), b.box.corners()])
                    gross, klein = (a, b) if a.box.area >= b.box.area else (b, a)
                    gross.box = OrientedBox.from_cv_rect(_cv2.minAreaRect(punkte))
                    gross.score = max(a.score, b.score)
                    if gross.contour is None:
                        gross.contour = klein.contour
                    dets = [d for k, d in enumerate(dets) if k != (
                        j if gross is a else i)]
                    geaendert = True
                    break
                if geaendert:
                    break
        return dets

    @staticmethod
    def _skaliere_dets(dets, s: float):
        """Kopien der Detections, Geometrie mit s multipliziert.

        Fuers SCHARFE Zeichnen: erkannt wird auf der 640er-Fassung,
        gezeichnet auf dem Anzeige-Crop in voller Aufloesung. Die
        Originale bleiben unveraendert (Records, Zaehlung, Tracking).
        """
        import copy
        from ..detection import OrientedBox
        aus = []
        for d in dets:
            k = copy.copy(d)
            b = d.box
            k.box = OrientedBox(b.cx * s, b.cy * s, b.length * s,
                                b.width * s, b.angle)
            if d.contour is not None:
                k.contour = np.round(np.asarray(
                    d.contour, dtype=np.float32) * s).astype(np.int32)
            aus.append(k)
        return aus

    def _erkenne(self, frame: np.ndarray, ausschnitt: np.ndarray = None,
                 faktor: float = 1.0,
                 leinwand: np.ndarray = None,
                 leerbild: np.ndarray = None) -> Tuple[np.ndarray, int]:
        """Erkennung ueber die vorhandene Pi-Strecke.

        Kein neuronales Netz: der Detektor ist noch nicht trainiert. Was hier
        laeuft, ist die geometrische Referenzstrecke. Die Oberflaeche zeigt
        das ausdruecklich an, damit niemand die Rahmen fuer Modellausgaben
        haelt.
        """
        from ..calibration import identity
        from ..fitting import detections_from_masks
        from ..overlay import draw
        from ..segmentation import segment_parts

        h, w = frame.shape[:2]

        # Gesucht wird auf einer kleineren Fassung, gezeichnet auf der grossen.
        # Das Livebild wurde groesser, damit es im Browser nicht mehr
        # hochskaliert und unscharf wird - die geometrische Strecke soll davon
        # aber nicht langsamer werden. Mehr Pixel bringen ihr nichts: die
        # Kanten sind dieselben.
        f = min(1.0, self.ERKENNUNG_PX / max(h, w, 1))
        such = (cv2.resize(frame, (max(8, int(w * f)), max(8, int(h * f))),
                           interpolation=cv2.INTER_AREA) if f < 1.0 else frame)

        cal = identity(such.shape[1::-1], px_per_mm=1.0)
        # LEERBILD (2026-09-19): liegt eine Referenz des leeren Bands vor,
        # segmentiert die Differenz dazu - robust gegen "schwarz auf
        # dunkelgruen", Aufschriften und Glanz. Auf die Suchgroesse
        # gebracht, damit Pixel auf Pixel passt.
        ref_such, rausch_such = None, None
        leer_rausch = None
        if isinstance(leerbild, tuple):
            leerbild, leer_rausch = leerbild
        if leerbild is not None:
            try:
                ref_such = (cv2.resize(leerbild, (such.shape[1], such.shape[0]),
                                       interpolation=cv2.INTER_AREA)
                            if leerbild.shape[:2] != such.shape[:2] else leerbild)
                if leer_rausch is not None:
                    # Rauschkarte NICHT mitteln (INTER_AREA wuerde Spitzen
                    # glaetten): groesster Wert im Umfeld zaehlt.
                    rausch_such = (cv2.resize(
                        cv2.dilate(leer_rausch, np.ones((3, 3), np.uint8)),
                        (such.shape[1], such.shape[0]),
                        interpolation=cv2.INTER_NEAREST)
                        if leer_rausch.shape[:2] != such.shape[:2] else leer_rausch)
            except Exception:
                ref_such, rausch_such = None, None
        teile, maske, _ = segment_parts(such, cal.px_per_mm, config.DEFAULT.seg,
                                        background_ref=ref_such,
                                        background_noise=rausch_such)
        dets = detections_from_masks(teile, maske, cal.px_per_mm,
                                     config.DEFAULT.seg, nominal=False)
        # Verworfene Stuecke zurueckholen: der Rechteck-Fit filtert nach
        # Form, und ein halb verdeckter Karabiner faellt da durch. Dann hatte
        # der ganze Klumpen KEINEN Rahmen mehr - drei Teile im Bild, eines
        # gemeldet. Jedes Wasserscheiden-Stueck, das kein Rahmen abdeckt,
        # wird deshalb als einfacher Rahmen nachgereicht; benennen kann der
        # Chip es trotzdem, ihm ist die Rechteckform egal.
        vor_ergaenzung = len(dets)
        dets = self._fehlende_ergaenzen(dets, teile)
        # Loecher aussortieren: die Segmentierung findet gelegentlich das
        # LOCH eines Rings als eigenes Teil. Dessen helles Viereck ging dann
        # als Objekt an den Chip - und wurde prompt zur SD-Karte erklaert,
        # waehrend der Ring selbst leer ausging. Ein Teil, dessen Flaeche
        # fast nur Hintergrund ist, ist kein Teil.
        dets = self._loch_filter(dets, maske)
        # Diagnose in die Fussleiste: wie viele Stuecke liefert die
        # Wasserscheide, wie viele Rahmen macht der Fit daraus, wie viele
        # werden nachgereicht? Ohne diese Zahlen raten wir am Bildschirmfoto.
        # Lokal aufbauen, am Ende EINMAL schreiben: das schrittweise
        # Anhaengen (erst Basis, dann " D2") hat dem Polling immer wieder
        # den Zwischenstand ohne D geliefert - sah aus wie ein toter
        # Detektor, war aber nur ein Wettlauf ums Feld (2026-08-28).
        seg = (f"{len(teile or [])}W {vor_ergaenzung}F "
               f"+{len(dets) - vor_ergaenzung}N")
        self.zustand.bereich_info["segmente"] = seg
        # WEICHKANTEN-WAECHTER (nur Zonen-Laeufe des Linienmodus): Otsu
        # findet auf leerer Flaeche IMMER eine Schwelle - aus Schatten
        # und Beleuchtungsverlauf wurden Phantom-Teile, die der Chip mit
        # 47-64 % benannte und die Zonen dauerbelegten (2026-09-04).
        # Echte Teile haben an der Umrisslinie einen harten Kontrast-
        # sprung, Schatten nicht - der Gradient entlang der Kontur
        # trennt beide. Marker "w" in der Segment-Diagnose.
        if getattr(self, "_erkenne_offset", None) is not None:
            vor_weich = len(dets)
            dets = self._weichkanten_filter(dets, such)
            if len(dets) != vor_weich:
                seg += f" w{vor_weich - len(dets)}"
        # Der Chip als Schiedsrichter - frueh definiert, weil sowohl die
        # Detektor-Fusion als auch _verschmelze ihn brauchen: passt das
        # GANZE besser als seine Stuecke, ist es ein Teil.
        # Chip-Zeit dieses Bildes: Summe ALLER Karten-Aufrufe (Verbund und
        # Detektor). Das ist die Zahl, um die es bei Neuromorphik geht -
        # die Gesamtlatenz misst dagegen Kamera, Geometrie und Uebertragung.
        self._chip_ms = 0.0

        def chip_erkenne(patch, pmaske, ki=None):
            if ki is not None:
                erg = self.lerner.erkenne_auf_karte(patch, pmaske, ki)
            else:
                erg = self.lerner.erkenne(patch, pmaske)
            # Nur die Kartenzeit zaehlen, die erkenne() selbst gestoppt
            # hat - nicht die CPU-Vorarbeit (Freistellen, Aufrichten).
            self._chip_ms += float(getattr(self.lerner,
                                           "chip_ms_letzte", 0.0) or 0.0)
            return erg

        bewerte = None
        if (getattr(self.lerner, "klassen", None) and ausschnitt is not None):
            def bewerte(box, kontur=None, sperren=None, direkt_maske=None, ki=None):
                patch, pmaske = self._patch(ausschnitt, box.scaled(faktor),
                                            kontur, faktor, sperren=sperren,
                                            direkt_maske=direkt_maske)
                if patch is None:
                    return None
                erg = chip_erkenne(patch, pmaske, ki)
                if not erg:
                    return None
                return (0.0 if erg.get("unklar") else float(erg["sicherheit"]),
                        erg)
        # Zerstueckelte Teile zusammensetzen, beruehrende getrennt lassen -
        # den Streitfall entscheidet der Chip als Schiedsrichter. Die
        # Geometrie-Kette laeuft ZUERST komplett durch.
        if (getattr(self, "profil", "linie") == "stationaer"
                and bewerte is not None and maske is not None):
            dets = self._hypothesen_entscheiden(dets, maske, bewerte, cal.px_per_mm)
        else:
            dets = self._verschmelze(dets, maske, bewerte=bewerte)

        # LOCH-ANKER: unbenannte Klumpen mit grossem inneren Loch werden
        # am Loch zerlegt (Ring + Rest) - der deterministische
        # Ueberlappungs-Loeser, VOR dem Detektor-Notnagel.
        try:
            vor_anker = len(dets)
            lochk = [n for n, a in (getattr(self.lerner, "loch_klassen", {})
                                    or {}).items() if a >= 0.6]
            dets = self._loch_anker(
                dets, maske, bewerte,
                lochname=lochk[0] if len(lochk) == 1 else None,
                loch_werte=getattr(self.lerner, "loch_klassen", {}) or {})
            if len(dets) != vor_anker:
                seg += f" L{len(dets) - vor_anker + 1}"
            # Lose-Taufe: unbenannte Splitter der Beruehrungsgruppe zu
            # EINEM Stueck vereinen und ueber die Loch-Signatur benennen.
            vor_taufe = len(dets)
            dets = self._lose_taufe(
                dets, maske, lochk[0] if len(lochk) == 1 else None)
            if len(dets) != vor_taufe:
                seg += f" T{vor_taufe - len(dets)}"
        except Exception as exc:
            self._diag_erkennung_fehler = f"Loch-Anker: {exc}"[:120]

        # STUFE 2 ALS NOTNAGEL (Umbau 2026-08-28): der Detektor kam bisher
        # VOR der Geometrie-Kette und hat mit maessig sitzenden Kaesten
        # sauber getrennte Beruehrungs-Szenen wieder zerlegt. Jetzt darf er
        # nur noch an das, was nach dem Chip-Schiedsrichter UNBENANNT
        # geblieben ist - der Fall "SD liegt satt auf dem Karabiner", in
        # dem die Wasserscheide keine Trennlinie hat.
        # In den ZONEN-Laeufen des Linienmodus bleibt der M3-Detektor
        # draussen: er ist fuer Ueberlapp-Klumpen im Prueffeld trainiert
        # und halluzinierte auf dem Blech neben dem Leuchtfeld reihenweise
        # Teile ([a]-Geister), die die Abholzone dauerbelegten und das
        # Band nie starten liessen (2026-09-03). Geometrie + Chip genuegen
        # in den kleinen Zonenfenstern.
        if (self.detektor is not None
                and getattr(self, "_erkenne_offset", None) is None):
            try:
                # Der Detektor kostet ~230 ms je Durchgang - jedes Bild
                # gerechnet drueckte er die Anzeige auf 3,7 Bilder/s
                # (gemessen 2026-08-28). Also: nur jedes 4. Bild rechnen,
                # dazwischen die letzten Kaesten weiterverwenden - auf dem
                # Pruefplatz liegen die Teile still. Der Massstabswechsel
                # beim Zoomen ist unkritisch: die Kaesten sind im
                # Suchmassstab gecacht und der aendert sich nur mit dem
                # Fenster, dann rechnet der naechste Takt ohnehin neu.
                self._m3_takt = getattr(self, "_m3_takt", 0) + 1
                # Der Takt gilt nur, solange die Szene stillsteht. Zieht man
                # Teile auseinander, klebten die gecachten Kaesten noch auf
                # der alten Lage und zerlegten den falschen Rahmen
                # (2026-08-28). Frisch gerechnet wird deshalb auch, wenn
                # sich die Zahl der Geometrie-Teile aendert oder ein
                # gecachter Kasten nicht mehr auf Vordergrund liegt.
                alte = getattr(self, "_m3_dets", []) or []
                binaer = (np.asarray(maske) > 0) if maske is not None else None
                def _veraltet():
                    if len(dets) != getattr(self, "_m3_geo_n", -1):
                        return True
                    if binaer is None:
                        return False
                    for m in alte:
                        y, x = int(round(m.box.cy)), int(round(m.box.cx))
                        if not (0 <= y < binaer.shape[0]
                                and 0 <= x < binaer.shape[1] and binaer[y, x]):
                            return True
                    return False
                if (self._m3_takt % 4 == 1
                        or getattr(self, "_m3_mass", None) != such.shape[:2]
                        or _veraltet()):
                    td = time.perf_counter()
                    self._m3_dets, _voll = self.detektor.finde(
                        such, obj_ab=0.35)
                    if (_DETEKTOR.get("stand") or {}).get("status") == "gestoert":
                        try:
                            self.alarmbuch.beende(f"karte_{_DETEKTOR.get('karte', 3)}")
                            self.alarmbuch.melde("detektor_ok", "info",
                                                 "Detektorkarte antwortet wieder",
                                                 einmalig=True)
                        except Exception:
                            pass
                    _DETEKTOR["stand"] = {
                        "aufgabe": (f"M3-Detektor: {such.shape[1]}x{such.shape[0]} px, "
                                    f"{len(self._m3_dets or [])} Kaesten"),
                        "letzte_ms": round((time.perf_counter() - td) * 1000.0, 1),
                        "letzte_zeit": time.time(), "status": "aktiv"}
                    self._m3_mass = such.shape[:2]
                    self._m3_geo_n = len(dets)
                    self._chip_ms += float(
                        getattr(self.detektor, "ms_chip", 0.0) or 0.0)
                import copy
                m3_dets = copy.deepcopy(getattr(self, "_m3_dets", []) or [])
                # Nur unbenannte Reste duerfen ersetzt werden.
                def _unbenannt(d):
                    c = d.meta.get("chip") or {}
                    return (not c) or bool(c.get("unbekannt")) \
                        or bool(c.get("unklar"))
                ersetzbar = {id(d) for d in dets if _unbenannt(d)}
                dets = self._fusion(dets, m3_dets, maske, bewerte=bewerte,
                                    ersetzbar=ersetzbar)
                seg += f" D{len(m3_dets)}"
                self._diag_detektor_fehler = None
                self.zustand.bereich_info.pop("detektor_fehler", None)
            except Exception as exc:
                self._diag_detektor_fehler = f"{type(exc).__name__}: {exc}"[:110]
                self.zustand.bereich_info["detektor_fehler"] = (
                    self._diag_detektor_fehler)
                st = _DETEKTOR.setdefault("stand", {})
                if st.get("status") != "gestoert":
                    st["gestoert_seit"] = time.time()
                    try:
                        self.alarmbuch.melde(
                            f"karte_{_DETEKTOR.get('karte', 3)}", "alarm",
                            f"Detektorkarte antwortet nicht ({str(exc)[:60]}) - "
                            "Erkennung laeuft ohne Detektor weiter")
                    except Exception:
                        pass
                st.update({"status": "gestoert", "grund": str(exc)[:120],
                           "aufgabe": "gestoert - Detektor ausgesetzt"})
        elif _DETEKTOR.get("grund"):
            # Ein NICHT geladener Detektor war bisher unsichtbar - kein D,
            # keine Meldung. Jetzt steht der Grund im Achtung-Block.
            self._diag_detektor_fehler = ("nicht geladen: "
                                          + str(_DETEKTOR["grund"])[:90])
            self.zustand.bereich_info["detektor_fehler"] = (
                self._diag_detektor_fehler)

        if f < 1.0:
            zurueck = 1.0 / f
            for d in dets:
                d.box = d.box.scaled(zurueck)
                if d.contour is not None:
                    d.contour = (d.contour.astype(np.float32) * zurueck).astype(np.int32)

        # Jedes gefundene Teil EINZELN vom Chip benennen lassen.
        #
        # Das Chip-Lernen beurteilt einen Ausschnitt als Ganzes - mit drei
        # Teilen darin ist "nicht unterscheidbar" die richtige, aber nutzlose
        # Antwort. Die Geometrie liefert die Teile aber laengst einzeln.
        # Also: um jedes Teil ein Quadrat aus dem vollaufgeloesten Ausschnitt
        # schneiden und dem Chip vorlegen. Aufrichten und Freistellen macht
        # erkenne() selbst.
        namen = list(getattr(self.lerner, "klassen", []) or [])
        klassen_namen = config.CLASS_NAMES
        verworfen = 0
        # Ablaufprotokoll: was geschah mit JEDEM Rahmen? Ohne das raten wir
        # an Bildschirmfotos, wenn Teile lautlos verschwinden (2026-08-28:
        # 2 Fit-Rahmen, 0 Objekte, kein Fehler, keine Spur).
        ablauf = []
        if namen and dets and ausschnitt is not None:
            klassen_namen = namen + ["unbekannt"]
            objekte = []
            for d in dets[:self.MAX_JE_OBJEKT]:
                # Zuerst das beim Verschmelzen gemerkte Ergebnis - der Chip
                # soll fuer dasselbe Teil nicht zweimal gefragt werden.
                erg = d.meta.get("chip")
                if erg is None:
                    # Detektor-Kaesten (ohne eigene Kontur): die Flaechen
                    # der Nachbarn ausstanzen, damit z. B. das SD-Stueck im
                    # Karabiner-Kasten nicht die Silhouette verschmutzt.
                    sperren = None
                    if d.contour is None and len(dets) > 1:
                        sperren = [o.contour if o.contour is not None
                                   else np.asarray(o.box.corners())
                                   for o in dets[:self.MAX_JE_OBJEKT]
                                   if o is not d]
                    patch, pmaske = self._patch(
                        ausschnitt, d.box.scaled(faktor), d.contour, faktor,
                        sperren=sperren)
                    erg = (chip_erkenne(patch, pmaske)
                           if patch is not None else None)
                quelle = (d.source or "?")[:1]
                if not erg:
                    ablauf.append(f"{quelle}/leer:" + (str(getattr(
                        self.lerner, "letzter_fehler", ""))[:24] or "patch"))
                    continue
                # Die Negativklasse ist ein AUFFANGBECKEN, kein Objekt. Sie
                # soll leeres Band und Stoerteile schlucken - aber nicht in
                # der Anzeige auftauchen und nicht mit echten Objekten um
                # den Sieg konkurrieren (Rueckmeldung 2026-08-27: "nichts /
                # Stoerteil" stand staendig mit hoher Zahl in der Liste).
                # Also: Sieger und Vorsprung nur unter den ECHTEN Objekten;
                # gewinnt die Negativklasse deutlich, ist das Teil
                # Hintergrund und verschwindet ganz.
                erg = self._ohne_negativ(erg)
                if quelle == "m" and (erg is None or erg.get("hintergrund")
                                      or erg.get("unbekannt")):
                    # Wiedervereinte Stuecke sind per Konstruktion ECHTER
                    # Vordergrund aus einer Beruehrungsgruppe - nie
                    # Hintergrund, egal was die Negativklasse meint (die
                    # Szene "Karabiner um SD Karte" fiel genau hier:
                    # m/hg n66p43, 2026-08-28).
                    n1v = (erg or {}).get("n1")
                    p1v = float((erg or {}).get("p1")
                                or (erg or {}).get("sicherheit") or 0.0)
                    # Loch-Signatur der GRUPPE: das C-Stueck allein hat kein
                    # umschlossenes Loch (die SD unterbricht den Ring), aber
                    # die Gesamtsilhouette aus Stueck + beruehrenden Nachbarn
                    # schon. Gibt es genau EINE gelernte Klasse mit Loch, ist
                    # das die staerkste verbleibende Aussage.
                    lochk = [n for n, a in (getattr(
                        self.lerner, "loch_klassen", {}) or {}).items()
                        if a >= 0.6]
                    if (len(lochk) == 1 and lochk[0] in namen
                            and self._gruppen_loch(d, dets, maske)):
                        d.class_id = namen.index(lochk[0])
                        d.class_score = max(p1v, 0.58)
                        d.meta["chip"] = {"klasse": lochk[0],
                                          "sicherheit": d.class_score}
                        d.meta["fusion"] = "Loch-Signatur der Gruppe"
                        ablauf.append(f"m/{lochk[0][:7]}"
                                      f"{int(d.class_score * 100)}L")
                        objekte.append({"name": lochk[0],
                                        "anteil": float(d.class_score),
                                        "unklar": False, "unbekannt": False,
                                        "alle": (erg or {}).get("alle") or []})
                        continue
                    # Sonst: sichtbar als unbekannt - Loch-Anker und
                    # Detektor duerfen weiter benennen.
                    d.class_id = len(namen)
                    d.class_score = p1v
                    ablauf.append(f"m/unb{int(p1v * 100)}"
                                  + (f"!n{int(n1v * 100)}" if n1v else ""))
                    objekte.append({"name": "unbekanntes Teil",
                                    "anteil": p1v, "unklar": False,
                                    "unbekannt": True, "alle": []})
                    continue
                if erg is None or erg.get("hintergrund"):
                    d.meta["hintergrund"] = True
                    # Sichtbar machen, WAS verschluckt wurde und WIE klar:
                    # "hg n62p41" = nichts 62 %, bestes echtes Teil 41 %.
                    # Taucht hier ein echtes Teil auf, frisst der Filter
                    # zu aggressiv (Karabiner ohne Kontur, 2026-08-28).
                    verworfen += 1
                    if erg and erg.get("n1") is not None:
                        ablauf.append(f"{quelle}/hg n{int(erg['n1'] * 100)}"
                                      f"p{int(erg['p1'] * 100)}")
                    else:
                        ablauf.append(f"{quelle}/hintergrund")
                    continue
                # Neuheitswaechter: findet selbst der beste Kandidat kaum
                # mehr als die Haelfte seiner Schablone wieder, ist das Teil
                # nie gelernt worden. Dann steht "unbekanntes Teil" am
                # Rahmen - nicht die beste Fehlzuordnung.
                unbekannt = bool(erg.get("unbekannt"))
                if not erg.get("unklar") and not unbekannt:
                    d.class_id = namen.index(erg["klasse"])
                    d.class_score = float(erg["sicherheit"])
                elif unbekannt:
                    # Virtueller Eintrag am Ende der Namensliste, damit das
                    # Overlay "unbekannt" an den Rahmen schreibt.
                    d.class_id = len(namen)
                    d.class_score = float(erg["sicherheit"])
                ablauf.append(quelle + "/"
                              + ("unb" if unbekannt else "unklar" if
                                 erg.get("unklar") else erg["klasse"][:7])
                              + str(int(erg["sicherheit"] * 100))
                              + (f"!n{int(erg['neg_knapp'] * 100)}"
                                 if erg.get("neg_knapp") else ""))
                try:
                    _ec = np.asarray(d.box.scaled(faktor).corners())
                    _box = [int(max(0, _ec[:, 0].min())), int(max(0, _ec[:, 1].min())),
                            int(_ec[:, 0].max()), int(_ec[:, 1].max())]
                except Exception:
                    _box = None
                objekte.append({"name": ("unbekanntes Teil" if unbekannt
                                else erg["klasse"] if not erg.get("unklar")
                                else "unklar"),
                                "anteil": float(erg["sicherheit"]),
                                "unklar": bool(erg.get("unklar")),
                                "unbekannt": unbekannt,
                                "alle": erg.get("alle") or [],
                                "box_px": _box,
                                # "Warum?": Lernfoto hinter dem Urteil.
                                "warum": erg.get("warum")})
            # Hintergrund-Teile verschwinden ganz: kein Rahmen, keine Zeile.
            dets = [d for d in dets if not d.meta.get("hintergrund")]
            # Stationaere Pruefung: das Bild, auf dem geurteilt wurde.
            self._pruef_ausschnitt = ausschnitt
            if not objekte:
                # Nur Hintergrund im Rahmen - Anzeige leeren, statt das
                # letzte echte Ergebnis stehen zu lassen. _je_objekt MUSS
                # dabei gesetzt werden: die Geometrie HAT geurteilt (nur
                # Hintergrund) - sonst ueberschreibt der Ganzbild-Rueckfall
                # das leere Ergebnis wieder mit "nichts 80 %".
                self._je_objekt = True
                self.zustand.erkannt = {"klasse": "", "sicherheit": 0.0,
                                        "unklar": False, "leer": True,
                                        "je_objekt": [], "alle": []}
            if objekte:
                self._je_objekt = True
                klar = [o for o in objekte
                        if not o["unklar"] and not o.get("unbekannt")]
                beste: dict = {}
                for o in klar:
                    beste[o["name"]] = max(beste.get(o["name"], 0.0), o["anteil"])
                # Bei genau EINEM Teil die volle Klassenaufschluesselung
                # zeigen: "SD 80, Karabiner 74" ist eine andere Diagnose als
                # "SD 80, Karabiner 15" - nur der Sieger allein verraet nicht,
                # ob es knapp war oder der Verlierer tot ist.
                if len(objekte) == 1 and objekte[0].get("alle"):
                    aufschluesselung = sorted(objekte[0]["alle"],
                                              key=lambda a: -a["anteil"])
                else:
                    aufschluesselung = [{"name": n, "anteil": a} for n, a in
                                        sorted(beste.items(), key=lambda x: -x[1])]
                fremde = [o for o in objekte if o.get("unbekannt")]
                # "Warum?" des sichersten benannten Teils nach oben reichen.
                sieger_obj = max(klar, key=lambda o: o["anteil"], default=None)
                self.zustand.erkannt = {
                    "klasse": " · ".join(dict.fromkeys(o["name"] for o in klar))
                              or ("unbekanntes Teil" if fremde else "unklar"),
                    "sicherheit": max((o["anteil"] for o in klar), default=0.0),
                    "unklar": not klar,
                    "je_objekt": objekte,
                    "alle": aufschluesselung,
                    "warum": (sieger_obj or {}).get("warum"),
                }

        if verworfen:
            seg += f" V{verworfen}"
        self.zustand.bereich_info["segmente"] = seg
        self._diag_segmente = seg
        if getattr(self, "_diag_hypothesen", None):
            self.zustand.bereich_info["hypothesen"] = self._diag_hypothesen
        self._diag_ablauf = (f"{len(dets)} Rahmen nach Fusion -> "
                             + (", ".join(ablauf[:8]) or "keiner benannt"))
        self.zustand.bereich_info["ablauf"] = self._diag_ablauf
        self._diag_inferenz_ms = round(self._chip_ms, 1)
        self.zustand.bereich_info["inferenz_ms"] = self._diag_inferenz_ms

        self.zustand.letzte_detektionen = [
            d.as_record(cal.px_per_mm) for d in dets[:32]]
        a = self.zustand.anzeige
        # font_ref: die Schrift bemisst sich an der GANZEN Anzeige, nicht am
        # kleinen Ausschnitt, in den hier gezeichnet wird - sonst waechst sie
        # im Ausschnitt ins Riesige und verdeckt das Teil.
        # Fuer den Linien-Modus: Zentren aller Teile, relativ 0..1 im
        # GESAMTEN Kamerabild. Das Mapping laeuft ueber einen Offset
        # (x0, y0, breite, hoehe des analysierten Bereichs, alles
        # vollbild-relativ): im Linienmodus je Zone gesetzt, sonst ist
        # es das Erkennungsfenster. name=None heisst unbenannt.
        _off = getattr(self, "_erkenne_offset", None)
        if _off is None:
            _bi = self.zustand.bereich_info or {}
            _bw = _bi.get("bild_breite", 1) or 1
            _bh = _bi.get("bild_hoehe", 1) or 1
            _bs = _bi.get("seite", 1) or 1
            _off = (_bi.get("x", 0) / _bw, _bi.get("y", 0) / _bh,
                    _bs / _bw, _bs / _bh)
        self._linie_objekte = [
            {"name": (klassen_namen[d.class_id]
                      if d.class_id is not None and klassen_namen
                      and 0 <= d.class_id < len(klassen_namen) else None),
             "x": _off[0] + float(d.box.cx) / max(w, 1) * _off[2],
             "y": _off[1] + float(d.box.cy) / max(h, 1) * _off[3],
             # Details fuer die zweigeteilte Teile-Anzeige im Linienmodus.
             "sicher": float(d.class_score or 0.0),
             "laenge": int(d.box.length * faktor),
             "breite": int(d.box.width * faktor),
             "winkel": int(d.box.angle),
             "quelle": (d.source or "?")[:1]}
            for d in dets]

        # Scharf zeichnen: auf der uebergebenen Leinwand (Anzeige-Crop in
        # voller Aufloesung) statt auf der 640er-Analysefassung - vorher
        # wurden Rahmen, Konturen und Schrift mit dem Video hochskaliert
        # und matschig (Rueckmeldung 2026-08-28).
        if leinwand is not None:
            s = leinwand.shape[0] / max(frame.shape[0], 1)
            ziel, dets_z = leinwand, self._skaliere_dets(dets, s)
        else:
            ziel, dets_z = frame, dets
        gezeichnet = draw(ziel, dets_z, cal.px_per_mm, show_mm=False,
                          class_names=klassen_namen,
                          show_contour=a.konturen, show_box=a.objektrahmen,
                          show_axis=a.laengsachse, show_label=a.beschriftung,
                          show_legend=a.legende,
                          font_ref=getattr(self, "_font_ref",
                                           self.anzeige_groesse))
        return gezeichnet, len(dets)

    # ------------------------------------------------------------------
    # Betrieb: zaehlen und schwere Faelle aufheben.
    EREIGNIS_ABSTAND = 3.0      # Sekunden, sonst fuellt ein Stau die Platte

    # -- Lernzonen je Kamera (1.9.29) -----------------------------------
    def _lernzonen_pfad(self) -> Optional[Path]:
        try:
            return Path(self.zustand.ordner) / "lernzonen.json"
        except Exception:
            return None

    def _lernzonen_laden(self) -> None:
        p = self._lernzonen_pfad()
        try:
            if p and p.exists():
                d = json.loads(p.read_text(encoding="utf-8"))
                for s in ("a", "b"):
                    e = d.get(s)
                    if isinstance(e, dict):
                        z = [float(v) for v in e.get("zone", self._lernzonen[s]["zone"])]
                        if len(z) == 4:
                            self._lernzonen[s] = {
                                "quelle": str(e.get("quelle", "aus")),
                                "zone": z, "an": bool(e.get("an", False))}
        except Exception:
            pass

    def lernzone_setzen(self, slot: str, quelle=None, zone=None, an=None) -> dict:
        slot = "b" if slot == "b" else "a"
        e = self._lernzonen[slot]
        if quelle is not None:
            q = str(quelle)
            if q in ("aus", "haupt") or q.startswith("usb") or q.startswith("picam"):
                e["quelle"] = q
                e["an"] = q != "aus"
        if zone is not None:
            try:
                x0, y0, x1, y1 = [max(0.0, min(1.0, float(v))) for v in zone]
                x0, x1 = sorted((x0, x1)); y0, y1 = sorted((y0, y1))
                if x1 - x0 >= 0.05 and y1 - y0 >= 0.05:
                    e["zone"] = [round(x0, 3), round(y0, 3),
                                 round(x1, 3), round(y1, 3)]
            except Exception:
                pass
        if an is not None:
            e["an"] = bool(an) and e["quelle"] != "aus"
        p = self._lernzonen_pfad()
        try:
            if p:
                p.write_text(json.dumps(self._lernzonen), encoding="utf-8")
        except Exception:
            pass
        return self.lernzonen_stand()

    def lernzonen_stand(self) -> dict:
        return {s: dict(e) for s, e in self._lernzonen.items()}

    def _lernzone_bild(self, slot: str, frame):
        """(Vollbild, Zonen-Ausschnitt) der Kamera dieses Slots - oder
        (None, None), wenn die Quelle aus/ohne Bild ist."""
        e = self._lernzonen.get(slot) or {}
        q = str(e.get("quelle", "aus"))
        if not e.get("an") or q == "aus":
            return None, None
        if q == "haupt":
            voll = frame
        else:
            voll, _f = self.zweitkamera.bild(q)
        if voll is None:
            return None, None
        h, w = voll.shape[:2]
        z = e.get("zone") or [0.02, 0.02, 0.98, 0.98]
        x0, y0 = int(z[0] * w), int(z[1] * h)
        x1, y1 = int(z[2] * w), int(z[3] * h)
        if x1 - x0 < 24 or y1 - y0 < 24:
            return voll, None
        return voll, np.ascontiguousarray(voll[y0:y1, x0:x1])

    def _lernzonen_feeds(self, frame) -> None:
        """Feeds "lern_a"/"lern_b" (Zonen-Ausschnitt mit Rahmen) und die
        Roh-Vollbilder fuer den Ziehmodus - nur im Lernmodus bei offener
        Splitansicht."""
        roh_bis = getattr(self, "_linie_roh_bis", {}) or {}
        for slot in ("a", "b"):
            art = "lern_" + slot
            voll, crop = self._lernzone_bild(slot, frame)
            if voll is None:
                self._linie_feeds.pop(art, None)
                continue
            if time.time() < roh_bis.get(art, 0):
                vh, vw = voll.shape[:2]
                rf = min(1.0, 640.0 / max(vw, vh, 1))
                rb = (cv2.resize(voll, (max(8, int(vw * rf)), max(8, int(vh * rf))),
                                 interpolation=cv2.INTER_AREA) if rf < 1.0 else voll)
                okr, bufr = cv2.imencode(".jpg", rb, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if okr:
                    self._linie_feeds[art + "_roh"] = {"jpg": bufr.tobytes(),
                                                       "ts": time.time()}
            if crop is None:
                self._linie_feeds.pop(art, None)
                continue
            ch, cw = crop.shape[:2]
            f = min(1.0, 640.0 / max(cw, ch, 1))
            lw = (cv2.resize(crop, (max(8, int(cw * f)), max(8, int(ch * f))),
                             interpolation=cv2.INTER_AREA) if f < 1.0 else crop.copy())
            # Dezenter Rahmen: das ist das Lernfoto, genau so geht es weg.
            cv2.rectangle(lw, (1, 1), (lw.shape[1] - 2, lw.shape[0] - 2),
                          (205, 205, 208), 1, cv2.LINE_AA)
            okj, buf = cv2.imencode(".jpg", lw, [cv2.IMWRITE_JPEG_QUALITY, 82])
            if okj:
                self._linie_feeds[art] = {"jpg": buf.tobytes(), "ts": time.time()}

    def lernfotos_aufnehmen(self, kid: int, negativ: bool) -> dict:
        """Ein Klick, alle aktiven Lernzonen: je Zone ein Lernfoto.

        VERGIFTUNGSSCHUTZ: ein Ausschnitt ohne freistellbares Teil wird
        NICHT gespeichert (sonst lernt die Klasse leeres Band). Nur bei
        Negativklassen ist "nichts" erlaubt - dafuer sind sie da."""
        from ..dataset_build import freistellen
        frame = self.hole_roh()
        ergebnisse = []
        for slot in ("a", "b"):
            e = self._lernzonen[slot]
            if not e.get("an") or e.get("quelle") == "aus":
                continue
            voll, crop = self._lernzone_bild(slot, frame)
            if crop is None:
                ergebnisse.append({"slot": slot, "ok": False,
                                   "grund": "kein Bild / Zone zu klein"})
                continue
            if not negativ:
                try:
                    t = freistellen(crop, 0)
                except Exception:
                    t = None
                if t is None:
                    ergebnisse.append({"slot": slot, "ok": False,
                                       "grund": "kein Teil freistellbar - "
                                                "uebersprungen"})
                    continue
            try:
                pruefung = self.zustand.foto_pruefen(crop, negativ=negativ)
            except Exception as exc:
                pruefung = {"ok": True, "maengel": [], "fehler": str(exc)[:80]}
            name = self.zustand.prototyp_speichern(kid, crop)
            ergebnisse.append({"slot": slot, "ok": bool(name), "datei": name,
                               "quelle": e.get("quelle"), "pruefung": pruefung})
        return {"ergebnisse": ergebnisse,
                "gespeichert": sum(1 for r in ergebnisse if r.get("ok"))}

    # -- Blick 2: zweite Kamera auf die Anlieferung + Fusion ------------
    def _blick2_pfad(self) -> Optional[Path]:
        try:
            return Path(self.zustand.ordner) / "blick2.json"
        except Exception:
            return None

    def _blick2_laden(self) -> None:
        p = self._blick2_pfad()
        try:
            if p and p.exists():
                d = json.loads(p.read_text(encoding="utf-8"))
                q = str(d.get("quelle", "aus"))
                z = [float(v) for v in d.get("zone", [0.02, 0.02, 0.98, 0.98])]
                if len(z) == 4:
                    self._blick2 = {"quelle": q, "zone": z}
        except Exception:
            pass

    def blick2_setzen(self, quelle=None, zone=None) -> dict:
        if quelle is not None:
            q = str(quelle)
            if q in ("aus", "haupt") or q.startswith("usb") or q.startswith("picam"):
                self._blick2["quelle"] = q
        if zone is not None:
            try:
                x0, y0, x1, y1 = [max(0.0, min(1.0, float(v))) for v in zone]
                x0, x1 = sorted((x0, x1)); y0, y1 = sorted((y0, y1))
                if x1 - x0 >= 0.05 and y1 - y0 >= 0.05:
                    self._blick2["zone"] = [round(x0, 3), round(y0, 3),
                                            round(x1, 3), round(y1, 3)]
            except Exception:
                pass
        p = self._blick2_pfad()
        try:
            if p:
                p.write_text(json.dumps(self._blick2), encoding="utf-8")
        except Exception:
            pass
        return dict(self._blick2)

    def _blick2_fusion(self, gesammelt: list, frame, status: dict) -> list:
        """Zweiten Blick erkennen und mit der Anlieferung fusionieren.

        Regel (Multi-View, konservativ):
          beide benennen dasselbe  -> Sicherheit = max + 0.08 (einig)
          beide benennen anderes   -> nur wenn einer >= 0.80 und der andere
                                       < 0.55, gilt der Sichere; sonst
                                       UNBEKANNT (Widerspruch statt Raten)
          nur Blick 2 benennt      -> sein Urteil zaehlt (2. Winkel sieht,
                                       was der erste nicht sieht)
        """
        q = str(self._blick2.get("quelle", "aus"))
        info = {"quelle": q, "kam2": None, "kam2_sicher": 0.0,
                "einig": None, "entschieden": ""}
        if q == "aus":
            self._fusion_info = info
            return gesammelt
        if q == "haupt":
            qb = frame
        else:
            qb, fehler = self.zweitkamera.bild(q)
            if qb is None:
                status["anliefer2"] = fehler
                self._fusion_info = info
                return gesammelt
        qh, qw = qb.shape[:2]
        z2 = self._blick2["zone"]
        x0, y0 = int(z2[0] * qw), int(z2[1] * qh)
        x1, y1 = int(z2[2] * qw), int(z2[3] * qh)
        leer = None
        q_form = qb.shape
        if x1 - x0 >= 48 and y1 - y0 >= 48:
            leer = self._leerbild_crop(q, q_form, y0, y1, x0, x1)
            # Roh-Vollbild fuer den Zonen-Ziehmodus (TTL vom Client-GET).
            if time.time() < (getattr(self, "_linie_roh_bis", {})
                              or {}).get("anliefer2", 0):
                rf = min(1.0, 640.0 / max(qw, qh, 1))
                rb = (cv2.resize(qb, (max(8, int(qw * rf)), max(8, int(qh * rf))),
                                 interpolation=cv2.INTER_AREA) if rf < 1.0 else qb)
                okr, bufr = cv2.imencode(".jpg", rb, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if okr:
                    self._linie_feeds["anliefer2_roh"] = {
                        "jpg": bufr.tobytes(), "ts": time.time()}
            qb = qb[y0:y1, x0:x1]
            qh, qw = qb.shape[:2]
        # Positionen in die PRIMAERE Anlieferzone abbilden, damit dieselbe
        # Treffer-Logik greift; die Erkennung schreibt _linie_objekte, das
        # wird danach zurueckgesetzt.
        za = self.linie.anliefer
        self._erkenne_offset = (za[0], za[1], za[2] - za[0], za[3] - za[1])
        zf = min(1.0, 640.0 / max(qw, qh, 1))
        lw = (cv2.resize(qb, (max(8, int(qw * zf)), max(8, int(qh * zf))),
                         interpolation=cv2.INTER_AREA) if zf < 1.0 else qb.copy())
        cm = max(qb.shape[:2])
        gez, _nz = self._erkenne(qb, qb, cm / max(1, min(self.ERKENNUNG_PX, cm)),
                                 leinwand=lw, leerbild=leer)
        objs2 = list(getattr(self, "_linie_objekte", []) or [])
        self._erkenne_offset = None
        okj, buf = cv2.imencode(".jpg", gez, [cv2.IMWRITE_JPEG_QUALITY, 78])
        if okj:
            self._linie_feeds["anliefer2"] = {"jpg": buf.tobytes(),
                                              "ts": time.time()}
        objs2 = self._schwelle_anwenden(objs2)
        a_b, a_u = self.linie._treffer(gesammelt, za)
        b_b, b_u = self.linie._treffer(objs2, za)
        info["kam2"] = (b_b or {}).get("name")
        info["kam2_sicher"] = float((b_b or {}).get("sicher") or 0.0)
        if a_b and b_b:
            sa = float(a_b.get("sicher") or 0.0)
            sb = float(b_b.get("sicher") or 0.0)
            if a_b["name"] == b_b["name"]:
                a_b["sicher"] = min(0.99, max(sa, sb) + 0.08)
                info["einig"], info["entschieden"] = True, "einig"
            elif sb >= 0.80 and sa < 0.55:
                a_b["name"], a_b["sicher"] = b_b["name"], sb
                info["einig"], info["entschieden"] = False, "kam2"
            elif sa >= 0.80 and sb < 0.55:
                info["einig"], info["entschieden"] = False, "kam1"
            else:
                a_b["name"] = None
                a_b["widerspruch"] = True
                info["einig"], info["entschieden"] = False, "unbekannt"
        elif b_b and not a_b:
            ziel = next((o for o in gesammelt
                         if za[0] <= o.get("x", -1) <= za[2]
                         and za[1] <= o.get("y", -1) <= za[3]
                         and not o.get("name")), None)
            if ziel is not None:
                ziel["name"], ziel["sicher"] = b_b["name"], float(
                    b_b.get("sicher") or 0.0)
            else:
                gesammelt.append({
                    "name": b_b["name"], "sicher": float(b_b.get("sicher") or 0.0),
                    "x": (za[0] + za[2]) / 2, "y": (za[1] + za[3]) / 2,
                    "laenge": int(b_b.get("laenge") or 0),
                    "breite": int(b_b.get("breite") or 0),
                    "winkel": int(b_b.get("winkel") or 0), "quelle": "2"})
            info["entschieden"] = "kam2"
        elif a_b and not b_b:
            info["entschieden"] = "kam1"
        self._fusion_info = info
        return gesammelt

    # -- Stufe 5: Schwelle / Ziel-Unbekanntquote -----------------------
    def _pruef_einst_pfad(self) -> Optional[Path]:
        try:
            return Path(self.zustand.ordner) / "pruef.json"
        except Exception:
            return None

    def _pruef_einst_laden(self) -> None:
        p = self._pruef_einst_pfad()
        try:
            if p and p.exists():
                d = json.loads(p.read_text(encoding="utf-8"))
                s = d.get("schwelle")
                self.konfidenz_schwelle = (None if s is None
                                           else max(0.0, min(1.0, float(s))))
                self.unbekannt_ziel = float(d.get("unbekannt_ziel", 10.0))
                if d.get("ausloeser") in ("hand", "auto", "extern"):
                    self.pruef_ausloeser = d["ausloeser"]
                if d.get("mehrbild") is not None and self.profil == "stationaer":
                    self.mehrbild.einstellen(anzahl=max(1, min(16, int(d["mehrbild"]))))
        except Exception:
            pass

    def pruef_einst_setzen(self, schwelle=None, unbekannt_ziel=None,
                           schwelle_aus: bool = False) -> dict:
        if schwelle_aus:
            self.konfidenz_schwelle = None
        elif schwelle is not None:
            self.konfidenz_schwelle = max(0.0, min(1.0, float(schwelle)))
        if unbekannt_ziel is not None:
            self.unbekannt_ziel = max(0.0, min(100.0, float(unbekannt_ziel)))
        p = self._pruef_einst_pfad()
        try:
            if p:
                p.write_text(json.dumps({
                    "schwelle": self.konfidenz_schwelle,
                    "unbekannt_ziel": self.unbekannt_ziel,
                    "ausloeser": self.pruef_ausloeser,
                    "mehrbild": self.mehrbild.anzahl}), encoding="utf-8")
        except Exception:
            pass
        return self.pruef_einst()

    def pruef_einst(self) -> dict:
        return {"schwelle": self.konfidenz_schwelle,
                "unbekannt_ziel": self.unbekannt_ziel,
                "ausloeser": self.pruef_ausloeser,
                "mehrbild_anzahl": self.mehrbild.anzahl}

    def mehrbild_setzen(self, anzahl) -> dict:
        try:
            n = max(1, min(16, int(anzahl)))
        except Exception:
            n = 4
        self.mehrbild.einstellen(anzahl=n)
        p = self._pruef_einst_pfad()
        try:
            if p:
                d = {}
                if p.exists():
                    d = json.loads(p.read_text(encoding="utf-8"))
                d["mehrbild"] = n
                p.write_text(json.dumps(d), encoding="utf-8")
        except Exception:
            pass
        return self.pruef_einst()

    # -- STATIONAERE PRUEFUNG (SE Inspect 1.0, 1.9.38) ------------------
    PRUEF_STILL_S = 0.6        # so lange muss die Szene unveraendert stehen
    PRUEF_SPERRE_S = 1.5       # Mindestabstand zweier Buchungen

    def _pruef_szene_kennung(self) -> str:
        """Kennung der Szene: Namen + grobe Lage der Teile. Gleiche
        Kennung = dieselbe Szene; eine Buchung je Kennung."""
        erk = self.zustand.erkannt or {}
        objs = erk.get("je_objekt") or []
        if not objs:
            return ""
        teile = []
        for o in objs:
            b = o.get("box_px") or [0, 0, 0, 0]
            teile.append(f"{o.get('name', '')}:{b[0] // 24}:{b[1] // 24}")
        return "|".join(sorted(teile))

    def _pruef_urteil_teil(self, o: dict, neg: set) -> dict:
        """Urteil fuer EIN Teil - dieselben Regeln wie _pruef_live."""
        name = str(o.get("name") or "")
        konf = float(o.get("anteil") or 0.0)
        s = self.konfidenz_schwelle
        if o.get("unbekannt"):
            return {"urteil": "unbekannt", "name": "", "konfidenz": konf,
                    "grund": "nie gelernt - unbekanntes Teil"}
        if o.get("unklar") or not name or name == "unklar":
            return {"urteil": "unbekannt", "name": "", "konfidenz": konf,
                    "grund": "nicht sicher zugeordnet"}
        if name in neg:
            return {"urteil": "ausschuss", "name": name, "konfidenz": konf,
                    "grund": "Negativklasse"}
        if s is not None and konf < s:
            return {"urteil": "unbekannt", "name": name, "konfidenz": konf,
                    "grund": f"unter Schwelle {int(s * 100)} %"}
        return {"urteil": "gut", "name": name, "konfidenz": konf,
                "grund": "sicher benannt"}

    def _pruef_stationaer_buchen(self, grund: str = "hand") -> dict:
        """Alle Teile der aktuellen Szene ins Pruefbuch buchen."""
        erk = self.zustand.erkannt or {}
        objs = list(erk.get("je_objekt") or [])
        if not objs:
            return {"ok": False, "grund": "kein Teil im Bild", "teile": []}
        neg = self._negativ_namen()
        bild = self._pruef_ausschnitt
        teile = []
        for o in objs:
            u = self._pruef_urteil_teil(o, neg)
            crop = None
            try:
                b = o.get("box_px")
                if bild is not None and b and b[2] - b[0] >= 8 and b[3] - b[1] >= 8:
                    h, w = bild.shape[:2]
                    r = max(8, int(0.15 * max(b[2] - b[0], b[3] - b[1])))
                    crop = bild[max(0, b[1] - r):min(h, b[3] + r),
                                max(0, b[0] - r):min(w, b[2] + r)].copy()
                elif bild is not None:
                    crop = bild
            except Exception:
                crop = bild
            e = self.pruefbuch.buche(u["urteil"], u["name"], u["konfidenz"],
                                     u["grund"] + (" · Automatik" if grund == "auto" else ""),
                                     crop, "haupt")
            teile.append({"urteil": u["urteil"], "name": u["name"],
                          "konfidenz": round(u["konfidenz"], 3),
                          "grund": u["grund"], "bild": e.get("bild", ""),
                          "box_px": o.get("box_px")})
        gesamt = ("gut" if all(t["urteil"] == "gut" for t in teile)
                  else "ausschuss" if any(t["urteil"] == "ausschuss" for t in teile)
                  else "unbekannt")
        if gesamt == "unbekannt":
            self.alarmbuch.melde("pruef_unbekannt", "warn",
                                 "UNBEKANNT: Teil nicht zuordenbar", einmalig=True)
        elif gesamt == "ausschuss":
            self.alarmbuch.melde("pruef_ausschuss", "warn",
                                 "AUSSCHUSS erkannt", einmalig=True)
        self._pruef_letzte = {"zeit": time.time(), "ausloeser": grund,
                              "urteil": gesamt, "teile": teile}
        self._pruef_gebucht_sig = self._pruef_szene_sig or self._pruef_szene_kennung()
        self._pruef_gebucht_zeit = time.time()
        try:
            if self.eaio is not None:
                self.eaio.ergebnis(gesamt)
            t0 = teile[0] if teile else {}
            self._sps_merken(gesamt, str(t0.get("name") or ""), float(t0.get("konfidenz") or 0), len(teile))
        except Exception:
            pass
        return {"ok": True, "urteil": gesamt, "teile": teile}

    def _pruef_stationaer_takt(self, art: str) -> None:
        """Einmal je Bild: Szene verfolgen, Automatik und Anfragen bedienen."""
        jetzt = time.time()
        sig = self._pruef_szene_kennung() if art == "betreiben" else ""
        if sig != self._pruef_szene_sig:
            self._pruef_szene_sig = sig
            self._pruef_szene_seit = jetzt if sig else 0.0
            if not sig:
                # Tisch leer: naechste Szene darf wieder gebucht werden,
                # auch wenn sie zufaellig dieselbe Kennung hat.
                self._pruef_gebucht_sig = ""
        if self._pruef_anfrage:
            self._pruef_anfrage = False
            grund, self._pruef_anfrage_grund = self._pruef_anfrage_grund, "hand"
            self._pruef_antwort = self._pruef_stationaer_buchen(grund)
            if grund in ("extern", "sps") and not self._pruef_antwort.get("ok"):
                # Trigger ohne Teil: die SPS wartet auf eine Antwort -> NOK.
                try:
                    if self.eaio is not None:
                        self.eaio.ergebnis("leer")
                    self._sps_merken("leer", "", 0.0, 0)
                except Exception:
                    pass
            return
        if (self.pruef_ausloeser == "auto" and sig
                and sig != self._pruef_gebucht_sig
                and jetzt - self._pruef_szene_seit >= self.PRUEF_STILL_S
                and jetzt - self._pruef_gebucht_zeit >= self.PRUEF_SPERRE_S):
            self._pruef_stationaer_buchen("auto")

    def testsatz_aufnehmen(self, soll, notiz: str = "") -> dict:
        """Aktuelle Szene in den Testsatz: rohes Bild + Soll + Ist."""
        if self.testsatz is None:
            return {"ok": False, "grund": "kein Testsatz-Ordner"}
        bild = self._roh_ausschnitt
        if bild is None:
            return {"ok": False, "grund": "kein Bild"}
        erk = self.zustand.erkannt or {}
        return self.testsatz.aufnehmen(bild.copy(), list(soll or []), notiz,
                                       ist=list(erk.get("je_objekt") or []))

    # ---- SPS (I2) -------------------------------------------------------
    def _sps_cfg_pfad(self):
        try:
            return Path(self.zustand.ordner) / "sps.json"
        except Exception:
            return None

    def _sps_cfg(self) -> dict:
        p = self._sps_cfg_pfad()
        try:
            if p and p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {"an": False, "port": 1502, "nur_lesen": False}

    def sps_einstellen(self, k: dict) -> dict:
        c = self._sps_cfg()
        if "an" in k:
            c["an"] = bool(k["an"])
        if "port" in k:
            c["port"] = max(1, min(65535, int(k["port"])))
        if "nur_lesen" in k:
            c["nur_lesen"] = bool(k["nur_lesen"])
        p = self._sps_cfg_pfad()
        try:
            if p:
                p.write_text(json.dumps(c), encoding="utf-8")
        except Exception:
            pass
        f = ""
        if self.sps is not None:
            if c["an"]:
                f = self.sps.starten(c["port"], c["nur_lesen"])
            else:
                self.sps.stoppen()
        return {"ok": not f, "grund": f, **self.sps_status()}

    def _sps_programme(self) -> list:
        rb = getattr(self, "rezeptbuch", None)
        if rb is None:
            return []
        try:
            return sorted((rb.uebersicht().get("rezepte") or {}).keys(), key=str.casefold)
        except Exception:
            return []

    def _sps_merken(self, urteil: str, name: str, konf: float, teile: int) -> None:
        oid = -1
        try:
            for k in self.zustand.klassen.values():
                if k.name == name:
                    oid = int(k.id)
                    break
        except Exception:
            pass
        self._sps_seq = (self._sps_seq + 1) & 0xFFFF
        self._sps_letzt = {"urteil": urteil, "objekt_id": oid, "konfidenz": konf, "teile": teile, "name": name}

    def _sps_stand(self) -> dict:
        st = {}
        try:
            st = self.pruefbuch.statistik()
        except Exception:
            pass
        al = getattr(self, "_alarm_stand", None) or {}
        rb = getattr(self, "rezeptbuch", None)
        aktiv = rb.aktiv_name() if rb else ""
        prog = self._sps_programme()
        return {**self._sps_letzt,
                "bereit": str(self.zustand.betriebsart) == "betreiben" and not al.get("aktiv_alarm"),
                "laeuft": bool(getattr(self, "_pruef_anfrage", False)),
                "stoerung": bool(al.get("aktiv_alarm")),
                "simuliert": not bool((getattr(self.zustand, "hardware", {}) or {}).get("geraet")),
                "gesamt": st.get("gesamt", 0), "gut": st.get("gut", 0),
                "unbekannt": st.get("unbekannt", 0), "ausschuss": st.get("ausschuss", 0),
                "programm": (prog.index(aktiv) + 1) if aktiv in prog else 0,
                "sequenz": self._sps_seq}

    def _sps_befehl(self, art: str, wert: int) -> str:
        if art == "pruefen":
            if self.profil != "stationaer":
                return "abgewiesen: Pruefen per SPS nur stationaer"
            if str(self.zustand.betriebsart) != "betreiben":
                return "abgewiesen: nicht im Pruefen"
            self._pruef_anfrage_grund = "sps"
            self._pruef_anfrage = True
            return "Pruefung ausgeloest"
        if art == "zaehler_reset":
            self.pruefbuch.reset()
            return "Zaehler zurueckgesetzt"
        if art == "programm":
            prog = self._sps_programme()
            if not 1 <= int(wert) <= len(prog):
                return f"abgewiesen: Programm {wert} gibt es nicht (1-{len(prog)})"
            name = prog[int(wert) - 1]
            threading.Thread(target=lambda: self.rezeptbuch.anwenden(name, self, self.zustand),
                             daemon=True).start()
            try:
                self.rollen and self.rollen.protokoll("sps", "/sps/programm", {"name": name})
            except Exception:
                pass
            return f"Programm {wert} ({name}) wird geladen"
        return "unbekannt"

    def sps_status(self) -> dict:
        c = self._sps_cfg()
        st = self.sps.status() if self.sps is not None else {"aktiv": False, "fehler": "nicht verfuegbar"}
        reg = []
        try:
            reg = self.sps.register() if self.sps is not None else []
        except Exception:
            pass
        return {"cfg": c, **st, "register": reg, "programme": self._sps_programme(),
                "letzt": dict(self._sps_letzt)}

    def _eaio_trigger(self) -> None:
        """Trigger-Eingang (Flanke): eine Pruefung anfordern. Wirft mit Grund,
        wenn nicht zulaessig - der Grund steht dann im I/O-Protokoll."""
        if self.profil != "stationaer":
            raise RuntimeError("nur im Profil stationaer (Linie hat eigene Sensorik)")
        if self.pruef_ausloeser != "extern":
            raise RuntimeError("Pruef-Ausloeser steht nicht auf Extern")
        if str(self.zustand.betriebsart) != "betreiben":
            raise RuntimeError("nicht im Pruefen")
        self._pruef_anfrage_grund = "extern"
        self._pruef_anfrage = True

    def pruefen_jetzt(self) -> dict:
        """/api/pruefen: naechstes Bild buchen und Ergebnis zurueckgeben."""
        if self.profil != "stationaer":
            return {"ok": False, "grund": "nur im Profil stationaer"}
        if str(self.zustand.betriebsart) != "betreiben":
            return {"ok": False, "grund": "Betriebsart Erkennung waehlen"}
        self._pruef_antwort = None
        self._pruef_anfrage = True
        bis = time.time() + 3.0
        while time.time() < bis:
            a = getattr(self, "_pruef_antwort", None)
            if a is not None:
                return a
            time.sleep(0.03)
        self._pruef_anfrage = False
        return {"ok": False, "grund": "kein Bild innerhalb von 3 s"}

    def pruef_ausloeser_setzen(self, art: str) -> dict:
        art = str(art).lower()
        art = art if art in ("auto", "extern") else "hand"
        self.pruef_ausloeser = art
        p = self._pruef_einst_pfad()
        try:
            if p:
                d = {}
                if p.exists():
                    d = json.loads(p.read_text(encoding="utf-8"))
                d["ausloeser"] = art
                p.write_text(json.dumps(d), encoding="utf-8")
        except Exception:
            pass
        return self.pruef_einst()

    def _schwelle_anwenden(self, objekte: list) -> list:
        """Namen unter der Konfidenzschwelle streichen -> 'unbekannt'.
        EINE Stelle vor der Linien-Zustandsmaschine; linie.py bleibt
        unangetastet."""
        s = self.konfidenz_schwelle
        if s is None or not objekte:
            return objekte
        aus = []
        for o in objekte:
            if o.get("name") and float(o.get("sicher", 0.0) or 0.0) < s:
                o = dict(o); o["name"] = None; o["unter_schwelle"] = True
            aus.append(o)
        return aus

    # -- Leerbild (Referenz des leeren Bands) --------------------------
    def _leerbild_ordner(self) -> Optional[Path]:
        try:
            p = Path(self.zustand.ordner) / "leerbild"
            p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception:
            return None

    def _leerbild_laden(self) -> None:
        o = self._leerbild_ordner()
        if o is None:
            return
        for pfad in o.glob("*.png"):
            if pfad.stem.endswith("_rausch"):
                continue
            try:
                b = cv2.imread(str(pfad))
                if b is not None:
                    e = {"bild": b, "zeit": pfad.stat().st_mtime}
                    r = cv2.imread(str(pfad.with_name(pfad.stem + "_rausch.png")),
                                   cv2.IMREAD_GRAYSCALE)
                    if r is not None and r.shape[:2] == b.shape[:2]:
                        e["rausch"] = r
                    self._leerbild[pfad.stem] = e
            except Exception:
                pass

    def leerbild_merken(self, quelle: str, anzahl: int = 16) -> dict:
        """Leeres Band merken - aus MEHREREN Bildern (2026-09-19).

        Ein einzelnes Bild kennt das Flackern nicht: Blendflecken der
        Lampen, LED-Flimmern und die nachregelnde Belichtung lassen das
        leere Band von Bild zu Bild um 20-40 Werte schwanken - genau dort
        entstanden dann "Teile". Jetzt: Median aus ~8 Bildern als Leerbild
        plus je Pixel die groesste gesehene Abweichung (Rauschkarte). Die
        Segmentierung setzt daraus die Schwelle je Pixel.
        STRUKTURIERTES BAND (2026-09-20): laeuft das Band waehrend der
        Aufnahme, wandert seine Textur durchs Bild - die Rauschkarte
        enthaelt dann je Pixel die ganze Bandbreite der Bandfarben, und
        nur was AUSSERHALB liegt (ein Teil), zaehlt. ~2 s, 16 Bilder."""
        quelle = str(quelle or "haupt")
        bilder = []
        for _ in range(max(1, int(anzahl))):
            if quelle == "haupt":
                bild = self.hole_roh()
            else:
                bild, _f = self.zweitkamera.bild(quelle)
            if bild is not None:
                if bilder and bild.shape != bilder[0].shape:
                    break
                bilder.append(np.ascontiguousarray(bild))
            time.sleep(0.12)
        if not bilder:
            return {"ok": False, "grund": "kein Bild von " + quelle}
        # Rohbild: das leere Band OHNE Overlays. Ein Teil im Bild waere
        # jetzt fuer immer "Hintergrund" - deshalb der Hinweis in der UI.
        stapel = np.stack(bilder).astype(np.int16)
        median = np.median(stapel, axis=0).astype(np.uint8)
        abw = np.abs(stapel - median.astype(np.int16)).max(axis=3)  # je Bild, je Pixel
        rausch = np.clip(abw.max(axis=0), 0, 255).astype(np.uint8)
        self._leerbild[quelle] = {"bild": median, "rausch": rausch,
                                  "zeit": time.time()}
        o = self._leerbild_ordner()
        if o is not None:
            try:
                cv2.imwrite(str(o / f"{quelle}.png"), median)
                cv2.imwrite(str(o / f"{quelle}_rausch.png"), rausch)
            except Exception:
                pass
        return {"ok": True, "quelle": quelle, "bilder": len(bilder),
                "rausch_max": int(rausch.max()),
                "rausch_p99": int(np.percentile(rausch, 99)),
                "zeit": time.strftime("%H:%M:%S"), **self.leerbild_stand()}

    def leerbild_loeschen(self, quelle: str) -> dict:
        quelle = str(quelle or "haupt")
        self._leerbild.pop(quelle, None)
        o = self._leerbild_ordner()
        if o is not None:
            (o / f"{quelle}.png").unlink(missing_ok=True)
            (o / f"{quelle}_rausch.png").unlink(missing_ok=True)
        return {"ok": True, **self.leerbild_stand()}

    def leerbild_stand(self) -> dict:
        return {"leerbild": {q: time.strftime("%H:%M", time.localtime(v["zeit"]))
                             for q, v in self._leerbild.items()}}

    def _leerbild_crop(self, quelle: str, form, y0, y1, x0, x1):
        """Passender Ausschnitt des Leerbilds - oder None, wenn keins da
        ist oder die Bildgroesse nicht mehr passt (Kamera/Drehung neu)."""
        v = self._leerbild.get(str(quelle))
        if not v:
            return None
        b = v["bild"]
        if b.shape[:2] != tuple(form[:2]):
            return None
        r = v.get("rausch")
        if r is not None and r.shape[:2] == b.shape[:2]:
            # (Bild, Rauschkarte) - _erkenne nimmt beides auseinander.
            return (b[y0:y1, x0:x1], r[y0:y1, x0:x1])
        return b[y0:y1, x0:x1]

    # -- Alarmbuch + Systemstatus (Stufe 2) ---------------------------
    def _alarme_pruefen(self, art: str) -> None:
        """Bedingungen je Bild auswerten - flankengesteuert ins Alarmbuch."""
        ab = self.alarmbuch
        # Kamera weg (nicht synthetisch, aber kein Geraet).
        try:
            kam_weg = (not self.quelle.synthetisch
                       and getattr(self.quelle, "cap", None) is None)
        except Exception:
            kam_weg = False
        if kam_weg:
            ab.melde("kamera", "alarm", "Kamera liefert kein Bild - "
                     "Heilung laeuft, Erkennung steht.")
        else:
            ab.beende("kamera")
        # Erkennung gestoert.
        ef = getattr(self, "_diag_erkennung_fehler", None)
        if ef:
            ab.melde("erkennung", "alarm", f"Erkennung gestoert: {ef}"[:160])
        else:
            ab.beende("erkennung")
        # M3-Detektor nicht geladen (Hinweis, kein Betriebsstopp).
        df = getattr(self, "_diag_detektor_fehler", None)
        if df and self.detektor is None:
            ab.melde("detektor", "warn", f"M3-Detektor: {df}"[:160])
        else:
            ab.beende("detektor")
        # Linie: Stoerung (Alarm) bzw. sonstige Meldung (Hinweis).
        li = self.linie
        if li is not None:
            phase = str(getattr(li, "phase", "") or "")
            meld = str(getattr(li, "meldung", "") or "")
            if phase == "stoerung":
                ab.melde("linie_stoerung", "alarm",
                         ("Linie gestoppt: " + meld) if meld
                         else "Linie in Stoerung")
            else:
                ab.beende("linie_stoerung")
            if (meld and phase != "stoerung"
                    and not meld.startswith("Erkennung pausiert")):
                ab.melde("linie_meldung", "warn", meld[:160])
            else:
                ab.beende("linie_meldung")

    def _system_ableiten(self, art: str) -> str:
        """BEREIT / LAEUFT / EINRICHTEN / ALARM - aus dem, was ist."""
        k = self._alarm_stand or {}
        if k.get("aktiv_alarm"):
            return "alarm"
        if art != "betreiben":
            return "einrichten"
        if self.linie is not None and getattr(self.linie, "aktiv", False):
            return "laeuft"
        return "bereit"

    # -- Pruefbuch (Stufe 1) ------------------------------------------
    def _negativ_namen(self) -> set:
        try:
            return {k.name for k in self.zustand.klassen.values()
                    if getattr(k, "negativ", False)}
        except Exception:
            return set()

    def _karte_alarm(self, ki: int, grund: str, wieder: bool) -> None:
        try:
            if wieder:
                self.alarmbuch.beende(f"karte_{ki}")
                self.alarmbuch.melde(f"karte_{ki}_ok", "info",
                                     f"Karte {ki + 1} antwortet wieder - "
                                     "zurueck im Verbund", einmalig=True)
            else:
                self.alarmbuch.melde(f"karte_{ki}", "alarm",
                                     f"Karte {ki + 1} antwortet nicht "
                                     f"({grund[:60]}) - aus dem Verbund "
                                     "genommen, Erkennung laeuft mit den "
                                     "uebrigen Karten weiter")
            self.zustand.hinweise.append(
                f"Karte {ki + 1}: " + ("wieder da" if wieder else grund[:80]))
        except Exception:
            pass

    # -- Karten-Reset ueber PCIe (1.9.36) ------------------------------
    @staticmethod
    def _pci_adressen() -> list:
        """PCIe-Adressen der Akida-Karten in Aufzaehlreihenfolge."""
        import os, re
        basis = "/sys/bus/pci/drivers/akida-pcie"
        try:
            adressen = sorted(e for e in os.listdir(basis)
                              if re.match(r"^[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9]$", e))
        except Exception:
            adressen = []
        return adressen

    @staticmethod
    def _sysfs_schreiben(pfad: str, wert: str = "1") -> str:
        """Direkt schreiben; ohne Rechte ueber sudo -n. Leer = ok, sonst Grund."""
        import subprocess
        try:
            with open(pfad, "w") as f:
                f.write(wert)
            return ""
        except PermissionError:
            pass
        except Exception as exc:
            return f"{pfad}: {exc}"[:120]
        try:
            r = subprocess.run(["sudo", "-n", "tee", pfad], input=wert.encode(),
                               capture_output=True, timeout=15)
            if r.returncode == 0:
                return ""
            return ("keine Rechte fuer " + pfad + " - sudoers-Regel noetig: "
                    "'<benutzer> ALL=(root) NOPASSWD: /usr/bin/tee "
                    "/sys/bus/pci/devices/*/remove, /usr/bin/tee /sys/bus/pci/rescan'")
        except Exception as exc:
            return f"sudo: {exc}"[:120]

    def karte_reset(self, nr: int) -> dict:
        """Eine haengende Karte per PCIe remove/rescan neu einbinden und
        ihr Modell wieder aufspielen - ohne Neustart des Dienstes."""
        global _GERAETE
        schritte = []
        adressen = self._pci_adressen()
        if nr < 0 or nr >= len(adressen):
            return {"ok": False, "grund": f"Karte {nr + 1}: keine PCIe-Adresse "
                    f"(gefunden: {len(adressen)})", "schritte": schritte}
        adr = adressen[nr]
        schritte.append(f"Karte {nr + 1} = {adr}")
        lerner = self.lerner
        sperre = getattr(lerner, "_lock", None) or threading.Lock()
        with sperre:
            # Sperren, damit waehrend des Resets niemand auf die Karte greift.
            try:
                if lerner is not None:
                    lerner.karte_gestoert(nr, "Reset laeuft")
                    lerner.karten_stand[nr]["naechster_versuch"] = time.time() + 3600
            except Exception:
                pass
            f = self._sysfs_schreiben(f"/sys/bus/pci/devices/{adr}/remove")
            if f:
                return {"ok": False, "grund": f, "schritte": schritte}
            schritte.append("entfernt")
            time.sleep(2.0)
            f = self._sysfs_schreiben("/sys/bus/pci/rescan")
            if f:
                return {"ok": False, "grund": f, "schritte": schritte}
            schritte.append("neu aufgezaehlt")
            time.sleep(3.0)
            try:
                import akida
                geraete = list(akida.devices())
                _GERAETE = geraete
                schritte.append(f"{len(geraete)} Karten sichtbar")
            except Exception as exc:
                return {"ok": False, "grund": f"akida.devices(): {str(exc)[:90]}",
                        "schritte": schritte}
            # Detektorkarte?
            if _DETEKTOR.get("aktiv") and _DETEKTOR.get("karte") == nr:
                pfad = _DETEKTOR.get("datei")
                schritte.append("Detektor wird neu geladen")
                threading.Thread(target=self.detektor_laden, args=(pfad,),
                                 daemon=True).start()
                return {"ok": True, "schritte": schritte}
            try:
                if lerner is not None and nr < len(lerner.modelle) and nr < len(geraete):
                    lerner.geraete[nr] = geraete[nr]
                    lerner.modelle[nr].map(geraete[nr], hw_only=True)
                    lerner.karte_notiz(nr, "nach Reset wieder eingebunden")
                    schritte.append("Lernstand wieder aufgespielt")
                elif lerner is not None:
                    lerner.karten_stand.pop(nr, None)
                    schritte.append("keine Aufgabe auf dieser Karte")
            except Exception as exc:
                return {"ok": False, "schritte": schritte, "grund": (
                    f"wieder einbinden: {str(exc)[:90]} - bitte Dienst neu "
                    "starten (sudo systemctl restart vorsa)")}
        return {"ok": True, "schritte": schritte}

    def _pruef_zonenbild(self, frame, art: str = "abhol"):
        """Bild der Zone fuers Archiv: Ausschnitt aus dem Hauptbild
        oder das Bild der eigenen Zonenkamera."""
        try:
            q = str(self.linie.quellen.get(art, "haupt"))
            if q != "haupt":
                b, _f = self.zweitkamera.bild(q)
                return b
            z = self.linie.abhol if art == "abhol" else self.linie.anliefer
            h, w = frame.shape[:2]
            x0, y0 = int(z[0] * w), int(z[1] * h)
            x1, y1 = int(z[2] * w), int(z[3] * h)
            if x1 - x0 >= 16 and y1 - y0 >= 16:
                return frame[y0:y1, x0:x1].copy()
        except Exception:
            pass
        return frame

    def _pruef_buchen(self, frame) -> None:
        """Urteil je Teil aus den Linien-Uebergaengen ableiten."""
        li = self.linie
        neg = self._negativ_namen()
        quelle = str(li.quellen.get("abhol", "haupt"))
        fluss = getattr(li, "takt", "einzel") == "fluss"
        # 0) FLUSS-Takt (1.9.33): das Urteil faellt in der ANLIEFERUNG,
        #    waehrend das Band dafuer haelt. Jede Pruefung einmal buchen.
        gp = int(getattr(li, "geprueft", 0) or 0)
        if gp > self._pruef_geprueft:
            neue = list(getattr(li, "pruefungen", []) or [])[
                -(gp - self._pruef_geprueft):]
            qa = str(li.quellen.get("anliefer", "haupt"))
            for pr in neue:
                name = str(pr.get("name") or "")
                konf = float(pr.get("sicher") or 0.0)
                if pr.get("urteil") != "benannt" or not name:
                    self.pruefbuch.buche("unbekannt", "", 0.0,
                                         "Anlieferung: kein stabiles Urteil",
                                         self._pruef_zonenbild(frame, "anliefer"),
                                         qa)
                    self.alarmbuch.melde("pruef_unbekannt", "warn",
                                         "UNBEKANNT: Teil in der Anlieferung "
                                         "nicht zuordenbar", einmalig=True)
                elif name in neg:
                    self.pruefbuch.buche("ausschuss", name, konf,
                                         "Negativklasse in der Anlieferung",
                                         self._pruef_zonenbild(frame, "anliefer"),
                                         qa)
                    self.alarmbuch.melde("pruef_ausschuss", "warn",
                                         f"AUSSCHUSS: {name} erkannt",
                                         einmalig=True)
                else:
                    self.pruefbuch.buche("gut", name, konf,
                                         "Anlieferung: benannt", None, qa)
        self._pruef_geprueft = gp
        # 1) Abgeraeumt: gefoerdert ist gestiegen -> gut oder ausschuss.
        #    (Im Fluss-Takt ist das Urteil schon in der Anlieferung
        #    gefallen - hier nicht doppelt zaehlen.)
        gef = int(getattr(li, "gefoerdert", 0) or 0)
        if gef > self._pruef_gefoerdert and not fluss:
            obj = dict(getattr(li, "_zonen_objekt", None) or {})
            name = str(obj.get("name") or "")
            konf = float(obj.get("sicherheit") or obj.get("konf") or 0.0)
            if name and name in neg:
                self.pruefbuch.buche("ausschuss", name, konf,
                                     "Negativklasse - vom Arm abgeraeumt",
                                     self._pruef_zonenbild(frame), quelle)
                self.alarmbuch.melde("pruef_ausschuss", "warn",
                                     f"AUSSCHUSS: {name} abgeraeumt",
                                     einmalig=True)
            else:
                self.pruefbuch.buche("gut", name, konf,
                                     "benannt und abgeraeumt", None, quelle)
        self._pruef_gefoerdert = gef
        # 2) Stoerung "unbekanntes Teil in Abholung" -> unbekannt (einmal
        #    je Eintritt in die Stoerungsphase).
        phase = str(getattr(li, "phase", "") or "")
        if phase == "stoerung" and self._pruef_phase != "stoerung":
            meld = str(getattr(li, "meldung", "") or "")
            if "Unbekannt" in meld or "unbekannt" in meld:
                self.pruefbuch.buche("unbekannt", "", 0.0,
                                     "unbekanntes Teil in der Abholzone",
                                     self._pruef_zonenbild(frame), quelle)
                self.alarmbuch.melde("pruef_unbekannt", "warn",
                                     "UNBEKANNT: Teil in der Abholzone "
                                     "nicht zuordenbar", einmalig=True)
        self._pruef_phase = phase

    def _pruef_live(self) -> dict:
        """Urteil fuer das AKTUELLE Bild (Anzeige, kein Zaehler)."""
        erk = self.zustand.erkannt or {}
        live = {"urteil": "leer", "name": "", "konfidenz": 0.0,
                "grund": "kein Teil im Fenster"}
        if not erk or erk.get("leer"):
            return live
        name = str(erk.get("klasse") or "")
        konf = float(erk.get("sicherheit") or 0.0)
        unklar = bool(erk.get("unklar") or erk.get("gleichstand"))
        s = self.konfidenz_schwelle
        if name and name in self._negativ_namen():
            return {"urteil": "ausschuss", "name": name, "konfidenz": konf,
                    "grund": "Negativklasse"}
        if name and not unklar and s is not None and konf < s:
            return {"urteil": "unbekannt", "name": name, "konfidenz": konf,
                    "grund": f"unter Schwelle {int(s * 100)} %"}
        if name and not unklar:
            return {"urteil": "gut", "name": name, "konfidenz": konf,
                    "grund": "sicher benannt"}
        return {"urteil": "unbekannt", "name": name, "konfidenz": konf,
                "grund": ("Gleichstand - Merkmale trennen nicht"
                          if erk.get("gleichstand")
                          else "nicht sicher zugeordnet")}

    def _betrieb_buchen(self, ausschnitt: np.ndarray) -> None:
        erk = self.zustand.erkannt
        if erk and erk.get("je_objekt"):
            # Je Objekt EINZELN zaehlen. Die Kopfzeile ("SD Karte ·
            # Karabiner") als eigene Klasse zu buchen hat die
            # Aufschluesselung mit Kombi-Namen zugemuellt (2026-08-28).
            namen = [o["name"] for o in erk["je_objekt"]
                     if o.get("name") and not o.get("unklar")]
            if namen:
                self.zustand.zaehle(namen)
        elif erk and erk.get("klasse"):
            self.zustand.zaehle([erk["klasse"]])

        # Unklare Faelle mit Bild ablegen - das ist das Material fuer die
        # naechste Trainingsrunde. Die Anlage sammelt damit selbst genau die
        # Faelle, an denen sie scheitert.
        unklar = [d for d in self.zustand.letzte_detektionen
                  if int(d.get("occlusion", 0)) >= 3]
        if not unklar:
            return
        jetzt = time.perf_counter()
        if jetzt - self._letztes_ereignis < self.EREIGNIS_ABSTAND:
            return
        self._letztes_ereignis = jetzt
        self.zustand.ereignis_ablegen(
            ausschnitt, "nicht aufloesbar",
            {"objekte": len(self.zustand.letzte_detektionen),
             "unklar": len(unklar),
             "vermutung": (erk or {}).get("klasse", "")})

    @staticmethod
    def _zeichne_rahmen(bild: np.ndarray, x: int, y: int, seite: int,
                        echte_seite: int = 0, rahmen: bool = True,
                        abdunkeln: bool = True) -> None:
        """Rahmen um den Ausschnitt, alles ausserhalb abgedunkelt.

        Das Abdunkeln ist nicht Zierde: ohne es ist auf einem kleinen Display
        nicht auf einen Blick zu sehen, was drin und was draussen ist. Beim
        Einrichten stoert es aber - dort will man sehen, was knapp neben dem
        Rahmen liegt. Deshalb schaltbar.
        """
        if abdunkeln:
            # NUR die vier Baender aussenherum abdunkeln, direkt an Ort und
            # Stelle. Vorher lief das ueber das ganze Bild, brauchte dafuer
            # jedes Mal ein frisches leeres Bild derselben Groesse und musste
            # den Ausschnitt hinterher wieder einsetzen - drei volle
            # Bilddurchgaenge je Einzelbild. Bei 1560 px hat das die Bildrate
            # halbiert.
            h, w = bild.shape[:2]
            for band in (bild[:y], bild[y + seite:],
                         bild[y:y + seite, :x], bild[y:y + seite, x + seite:]):
                if band.size:
                    cv2.convertScaleAbs(band, dst=band, alpha=0.38, beta=0)

        if not rahmen:
            return

        # Gelb wie die Oberflaeche. Die Kanten gestrichelt und duenn, die
        # Ecken massiv: so begrenzt der Rahmen den Bereich, ohne das Objekt
        # zu ueberdecken. Ein durchgehender dicker Rahmen zieht den Blick auf
        # sich - hier soll er auf dem Teil bleiben.
        GELB = (205, 205, 208)        # BGR - neutral hell; der gelbe
        # Rahmen stammte aus dem alten Skin (Vorlage 2026-08-28)
        strich, luecke = 9, 7
        for i in range(x, x + seite, strich + luecke):
            j = min(i + strich, x + seite)
            cv2.line(bild, (i, y), (j, y), GELB, 1, cv2.LINE_AA)
            cv2.line(bild, (i, y + seite), (j, y + seite), GELB, 1, cv2.LINE_AA)
        for i in range(y, y + seite, strich + luecke):
            j = min(i + strich, y + seite)
            cv2.line(bild, (x, i), (x, j), GELB, 1, cv2.LINE_AA)
            cv2.line(bild, (x + seite, i), (x + seite, j), GELB, 1, cv2.LINE_AA)

        e = max(8, seite // 14)
        for (ex, ey, dx, dy) in ((x, y, 1, 1), (x + seite, y, -1, 1),
                                 (x, y + seite, 1, -1), (x + seite, y + seite, -1, -1)):
            cv2.line(bild, (ex, ey), (ex + dx * e, ey), GELB, 2, cv2.LINE_AA)
            cv2.line(bild, (ex, ey), (ex, ey + dy * e), GELB, 2, cv2.LINE_AA)

        # Die ECHTE Ausschnittgroesse anzeigen, nicht die der verkleinerten
        # Anzeige - sonst liest man eine Zahl ab, die nichts bedeutet.
        s = echte_seite or seite
        cv2.putText(bild, f"{s} PX", (x + e + 6, max(14, y - 7)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, GELB, 1, cv2.LINE_AA)

    def hole_roh(self) -> Optional[np.ndarray]:
        with self._lock:
            return None if self._roh is None else self._roh.copy()

    def hole_ausschnitt(self) -> Optional[np.ndarray]:
        """Genau das Bild, das der Chip bekommt - und das gespeichert wird."""
        with self._lock:
            return None if self._ausschnitt is None else self._ausschnitt.copy()

    def hole_anzeige(self) -> Optional[np.ndarray]:
        with self._lock:
            return None if self._anzeige is None else self._anzeige.copy()

    def stoppe(self) -> None:
        self._laeuft = False
        self._thread.join(timeout=1.0)
        self.quelle.schliesse()


# ----------------------------------------------------------------------
def chip_lernen(zustand: Zustand, lerner: "EdgeLerner",
                mit_varianten: bool = False, lauf=None):
    """Sammelt die Lernbilder ein und uebergibt sie der Karte.

    OHNE Augmentierungsvarianten - das war frueher anders, und der Wechsel
    hat einen Grund: seit dem Aufrichten wird jedes Bild vor dem Lernen
    freigestellt, waagerecht gedreht und die Seite festgelegt. Eine
    gespiegelte oder gedrehte Variante landet danach auf FAST DEMSELBEN
    Formbild wie das Original. 720 Beispiele je Objekt waren in Wahrheit
    80 Fotos mal 9 nahezu identische Kopien - sie haben die 128 Neuronen
    mit Duplikaten geflutet und die echten Unterschiede verdraengt.

    Fuer das M3-Training bleiben die Varianten richtig und erhalten: dort
    wird nicht aufgerichtet, dort muss das Netz die Lagen selbst sehen.
    """
    from ..assignment import GtObject
    from ..augment import erzeuge_varianten

    if lauf is not None:
        lauf.setze_phase("Bilder einsammeln", 0, len(zustand.klassen))
    bilder = {}
    dateien = {}                    # parallel zu bilder: Herkunftsfoto je Bild
    for nr, k in enumerate(zustand.klassen.values(), 1):
        if lauf is not None:
            lauf.setze_phase(f"Bilder einsammeln: {k.name}", nr,
                             len(zustand.klassen))
        liste, namen_liste = [], []
        for datei in k.prototypen:
            b = zustand.prototyp_bild(datei)
            if b is None:
                continue
            if mit_varianten:
                h, w = b.shape[:2]
                platz = [GtObject(w / 2, h / 2, w * .6, h * .3, 0.0, k.id)]
                for _, bild, _o in erzeuge_varianten(b, platz, k.augment):
                    liste.append(bild); namen_liste.append(datei)
            else:
                liste.append(b); namen_liste.append(datei)
        if liste:
            bilder[k.name] = liste
            dateien[k.name] = namen_liste

    if lauf is not None:
        lauf.melde(f"{sum(len(v) for v in bilder.values())} Beispiele aus "
                   f"{len(bilder)} Objekten")
    # Dem Lerner sagen, welche Klassen Negativklassen sind - die bekommen
    # keine Torso-Varianten (Stoerteil-Torsi fressen echte Teile).
    lerner.negativ_namen = {k.name for k in zustand.klassen.values()
                            if getattr(k, "negativ", False)}
    # Waechter gegen LEERE Negativ-Fotos (2026-08-28): ein Foto vom leeren
    # Band enthaelt kein Teil - die Freistellung macht daraus einen
    # zufaelligen Fetzen (Schatten, Papierkante, Rauschen), und kleine
    # amorphe Fetzen passen UEBERALL hinein. Genau so kam "nichts" auf
    # 72 % AUF dem Karabiner-Bogen. Solche Fotos werden nicht gelernt;
    # leeres Band braucht keine Negativklasse (kein Vordergrund, keine
    # Erkennung).
    leer_warnung = None
    for nname in list(lerner.negativ_namen):
        alt = bilder.get(nname) or []
        voll = [b for b in alt
                if float(np.asarray(b, dtype=np.float32).std()) >= 12.0]
        if len(voll) < len(alt):
            leer_warnung = (
                f"{len(alt) - len(voll)} von {len(alt)} Fotos der "
                f"Negativklasse „{nname}“ zeigen nur leeren "
                f"Hintergrund und wurden NICHT gelernt - solche Fotos "
                f"machen die Klasse zum Alles-Matcher. Bitte loeschen; "
                f"die Negativklasse ist nur fuer echte Stoerteile da.")
            if lauf is not None:
                lauf.melde(leer_warnung)
            if voll:
                # Dateinamen parallel mitfiltern.
                behalten = [i for i, b in enumerate(alt)
                            if float(np.asarray(b, dtype=np.float32).std()) >= 12.0]
                bilder[nname] = voll
                dn = dateien.get(nname) or []
                dateien[nname] = [dn[i] for i in behalten if i < len(dn)]
            else:
                del bilder[nname]
                dateien.pop(nname, None)
                lerner.negativ_namen.discard(nname)
    bericht = lerner.lerne(bilder, lauf=lauf)
    if leer_warnung and hasattr(bericht, "warnungen"):
        bericht.warnungen.append(leer_warnung)
    if bericht.ok:
        # "WARUM?" (2026-09-19): Neuron -> Lernfoto zuordnen, damit jedes
        # Urteil das echte Beispiel zeigen kann, das gefeuert hat.
        if lauf is not None:
            lauf.setze_phase("Erklaerung aufbauen")
        try:
            n_k = lerner.neuron_karte_bauen(bilder, dateien)
            if lauf is not None:
                lauf.melde(f"Warum?-Karte: {n_k} Neuronen mit Lernfoto belegt")
        except Exception as exc:
            if lauf is not None:
                lauf.melde(f"Warum?-Karte nicht gebaut: {str(exc)[:80]}")
        # Sofort sichern. Der Lernstand liegt sonst nur im Arbeitsspeicher
        # der Karte und ist beim naechsten Neustart weg - das hat schon
        # einmal wie ein Fehlschlag des Lernens ausgesehen.
        if lauf is not None:
            lauf.setze_phase("Sichern")
        lerner.fingerabdruck = zustand.fingerabdruck()
        lerner.herkunft = "gelernt"
        erg = lerner.speichern(zustand.ordner)
        if erg.get("ok"):
            bericht.gesichert = True
            if lauf is not None:
                lauf.melde(f"gesichert: {erg.get('datei')} "
                           f"({erg.get('kb')} kB, {erg.get('schichten')} Schichten)")
        else:
            bericht.warnungen.append(
                f"Gelerntes nicht sicherbar: {erg.get('grund')} - "
                "nach einem Neustart muss neu gelernt werden.")
            if lauf is not None:
                lauf.melde(f"SICHERN FEHLGESCHLAGEN: {erg.get('grund')}")
    return bericht


def lernen_beim_start(zustand: Zustand, lerner: "EdgeLerner") -> None:
    """Stellt das Gelernte nach einem Neustart wieder her.

    Zwei Wege, in dieser Reihenfolge:

      1. Gesicherte .fbz zurueckspielen. Schnell, und es ist genau das
         Modell, das zuletzt geprueft wurde.
      2. Nur wenn das fehlt oder die Fotos sich geaendert haben: neu lernen
         und sichern.

    Die Lernschicht der Karte ist fluechtig. Ohne diesen Schritt stand die
    Oberflaeche nach jedem Neustart auf "bereit, aber nichts gelernt" - und
    das sah aus, als haette das Lernen nie funktioniert.
    """
    da, info = lerner.verfuegbar()
    if not da:
        return

    finger = zustand.fingerabdruck()
    geladen = lerner.laden(zustand.ordner, finger)
    if geladen.get("ok"):
        lerner.herkunft = "zurueckgespielt"
        zustand.hinweise.append(
            f"Gelerntes zurueckgespielt ({len(lerner.klassen)} Objekte, "
            f"gesichert {geladen.get('gesichert','?')})")
        print(f"  Chip: Lernstand zurueckgespielt, {lerner.klassen}", flush=True)
        return
    if geladen.get("veraltet"):
        zustand.hinweise.append(
            "Gesicherter Lernstand passt nicht mehr zu den Fotos - es wird "
            "neu gelernt.")

    echte = [k for k in zustand.klassen.values() if k.prototypen and not k.negativ]
    if len(echte) < 2:
        return
    try:
        bericht = chip_lernen(zustand, lerner)
    except Exception as exc:
        zustand.hinweise.append(f"Wiederherstellen des Gelernten: {str(exc)[:90]}")
        return
    zustand.hinweise.append(
        f"Neu gelernt: {len(bericht.klassen)} Objekte, {bericht.beispiele} Beispiele"
        if bericht.ok else f"Gelerntes NICHT wiederherstellbar: {bericht.grund}")
    print(f"  Chip-Lernen beim Start: "
          f"{'ok' if bericht.ok else bericht.grund}", flush=True)


# ----------------------------------------------------------------------
def baue_handler(verarbeitung: Verarbeitung, zustand: Zustand,
                 laeufe: dict = None, protokoll: bool = False):
    laeufe = laeufe or {}

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format, *args):
            """Zugriffsprotokoll - abschaltbar, aber standardmaessig AN.

            Es abzuschalten war ein Fehler: ohne Protokoll ist von aussen
            nicht zu sehen, ob ein Browser eine Anfrage ueberhaupt stellt.
            Genau diese Frage war spaeter nicht mehr zu beantworten.
            """
            if protokoll:
                print(f"  {self.client_address[0]}  {format % args}", flush=True)

        # --- Hilfen -------------------------------------------------
        def _json(self, daten, code: int = 200):
            roh = json.dumps(daten, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(roh)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(roh)

        def _bytes(self, roh: bytes, typ: str, code: int = 200):
            self.send_response(code)
            self.send_header("Content-Type", typ)
            self.send_header("Content-Length", str(len(roh)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(roh)

        def _koerper(self) -> dict:
            # 1.9.60: einmal lesen, danach aus dem Zwischenspeicher - die
            # Rollenpruefung braucht den Koerper vor der Route.
            if "_koerper_d" in self.__dict__:
                return self._koerper_d
            self._koerper_d = self._koerper_lesen()
            return self._koerper_d

        def _koerper_lesen(self) -> dict:
            try:
                laenge = int(self.headers.get("Content-Length", 0))
            except Exception:
                laenge = 0
            if not laenge:
                return {}
            try:
                d = json.loads(self.rfile.read(laenge).decode("utf-8"))
            except Exception:
                return {}
            # Audit 2026-10-02: "[]", "null", "\"text\"" sind gueltiges JSON,
            # aber kein Objekt - jede Route erwartet ein dict.
            return d if isinstance(d, dict) else {}

        # Audit 2026-10-02: eine Ausnahme in einer Route darf die Verbindung
        # nicht stumm abbrechen - der Browser sah "Remote end closed" und
        # die Oberflaeche lief ins Leere. Jetzt: JSON 500 mit Grund, einmal
        # ins Log (gleiche Meldung nicht wiederholt).
        _letzter_routenfehler = ""

        def do_POST(self):
            try:
                # Keep-Alive: dieselbe Handler-Instanz bedient mehrere
                # Anfragen - den Koerper der vorigen nie wiederverwenden.
                self.__dict__.pop("_koerper_d", None)
                weg = urlparse(self.path).path
                koerper = self._koerper()
                r = getattr(verarbeitung, "rollen", None)
                rolle = r.rolle(self.headers.get("X-SE-Token", "")) if r else "admin"
                if r is not None:
                    noetig = r.noetig(weg, koerper)
                    if not r.darf(rolle, noetig):
                        return self._json({
                            "ok": False, "verboten": True, "rolle": rolle, "rolle_noetig": noetig,
                            "grund": {"einrichter": "Anmeldung als Einrichter nötig",
                                      "admin": "Anmeldung als Admin nötig"}.get(noetig, "nicht erlaubt")}, 403)
                antwort = self._post_roh()
                if r is not None:
                    r.protokoll(rolle, weg, koerper)
                return antwort
            except Exception as exc:
                self._routenfehler("POST", exc)

        def do_GET(self):
            try:
                return self._get_roh()
            except Exception as exc:
                self._routenfehler("GET", exc)

        def _routenfehler(self, methode, exc):
            import traceback
            text = f"{type(exc).__name__}: {str(exc)[:160]}"
            key = f"{methode} {self.path.split('?')[0]} {text}"
            # Falsche Eingaben (Typ, Wert, fehlender Schluessel) sind ein 400,
            # alles andere ein 500 - nur das bekommt einen Stack ins Log.
            code = 400 if isinstance(exc, (ValueError, TypeError, KeyError)) else 500
            if key != type(self)._letzter_routenfehler:
                type(self)._letzter_routenfehler = key
                print(f"  ROUTENFEHLER {code} {key}", flush=True)
                if code == 500:
                    traceback.print_exc()
            try:
                self._json({"fehler": text, "weg": self.path.split("?")[0]}, code)
            except Exception:
                pass

        # --- GET ----------------------------------------------------
        def _get_roh(self):
            pfad = urlparse(self.path)
            weg = pfad.path
            frage = parse_qs(pfad.query)

            if weg in ("/", "/index.html"):
                datei = STATISCH / "index.html"
                if not datei.exists():
                    return self._bytes(b"index.html fehlt", "text/plain", 500)
                return self._bytes(datei.read_bytes(), "text/html; charset=utf-8")

            if weg == "/karte.png":
                # Platinen-Icon fuer den Kartenverbund-Block (2026-08-28).
                datei = STATISCH / "karte.png"
                if not datei.exists():
                    return self._bytes(b"", "image/png", 404)
                return self._bytes(datei.read_bytes(), "image/png")

            if weg.startswith("/static/") and weg.endswith(".js"):
                # Sprachdateien der Oberflaeche (A13). Nur der Dateiname
                # zaehlt - kein Pfad-Traversal moeglich.
                name = Path(weg).name
                datei = STATISCH / name
                if not datei.exists():
                    return self._bytes(b"", "application/javascript", 404)
                return self._bytes(datei.read_bytes(),
                                   "application/javascript; charset=utf-8")

            if weg.startswith("/static/") and weg.endswith((".png", ".webp", ".svg")):
                # Statische Bilder (Kartenbilder, Marke). Nur der Dateiname
                # zaehlt - kein Pfad-Traversal moeglich.
                name = Path(weg).name
                datei = STATISCH / name
                typ = {"png": "image/png", "webp": "image/webp", "svg": "image/svg+xml"}[name.rsplit(".", 1)[-1]]
                if not datei.exists():
                    return self._bytes(b"", typ, 404)
                return self._bytes(datei.read_bytes(), typ)

            if weg == "/api/state":
                # Jeder Teil einzeln abgesichert. Der Zustand ist die
                # Lebensader der Oberflaeche - haengt oder scheitert er,
                # steht alles still und man sieht nur ein leeres Fenster.
                d = zustand.as_dict()
                d["profil"] = getattr(verarbeitung, "profil", "linie")
                try:
                    d["lernen"] = (verarbeitung.lerner.as_dict()
                                   if verarbeitung.lerner else {})
                except Exception as exc:
                    d["lernen"] = {"verfuegbar": False,
                                   "info": f"Lernteil: {str(exc)[:80]}"}
                d["erkannt"] = zustand.erkannt
                d["arm_uno"] = verarbeitung.arm_uno is not None
                try:
                    d["kamera"] = {
                        "vorhanden": not verarbeitung.quelle.synthetisch,
                        # Kamera war da, liefert aber gerade nicht - die
                        # Heilung laeuft. Muss die Oberflaeche gross zeigen.
                        "ausgefallen": (not verarbeitung.quelle.synthetisch
                                        and verarbeitung.quelle.cap is None),
                        "hinweis": verarbeitung.quelle.hinweis,
                        "koennen": sorted(verarbeitung.quelle.koennen),
                        "werte": verarbeitung.quelle.lies_einstellungen(),
                        "startwerte": dict(verarbeitung.quelle.start_werte),
                    }
                except Exception as exc:
                    d["kamera"] = {"vorhanden": False, "koennen": [], "werte": {},
                                   "fehler": str(exc)[:80]}
                # Hat sich die Kamera seit dem Training verstellt? Ohne diese
                # Meldung sucht man den Fehler im Modell, waehrend er in der
                # Kamera sitzt.
                try:
                    d["drift"] = zustand.drift(d["kamera"].get("werte") or {})
                except Exception:
                    d["drift"] = []
                d["fortschritt"] = zustand.fortschritt(
                    gelernt=bool(getattr(verarbeitung.lerner, "klassen", [])))
                d["laeufe"] = {n: {"laeuft": l.laeuft, "fertig": l.fertig,
                                   "ok": l.ok, "phase": l.phase,
                                   "anteil": (round(l.schritt / l.schritte, 3)
                                              if l.schritte else 0.0)}
                               for n, l in laeufe.items()}
                return self._json(d)

            if weg == "/api/arm":
                # Zustand des eingebauten Arduino-Arms (ARM-Dialog).
                a = verarbeitung.arm_uno
                if a is None:
                    return self._json({"vorhanden": False})
                try:
                    if a.verbunden and not a.busy \
                            and not a.programm_laeuft:
                        a.pos_lesen()
                    elif not a.verbunden:
                        a.verbinde()
                except Exception:
                    pass
                return self._json(a.zustand())

            if weg == "/api/linie_feed":
                # Annotierter Zonen-Feed einer USB-Quelle (Linienmodus).
                # roh=1: unbeschnittenes Vollbild der Kamera fuer den
                # Zonen-Ziehmodus (der GET selbst haelt das Roh-Encoding
                # per TTL am Leben).
                art = (frage.get("art") or ["abhol"])[0]
                schluessel = art
                if (frage.get("roh") or ["0"])[0] == "1":
                    b = getattr(verarbeitung, "_linie_roh_bis", None)
                    if b is None:
                        b = verarbeitung._linie_roh_bis = {}
                    b[art] = time.time() + 8
                    schluessel = art + "_roh"
                f = (getattr(verarbeitung, "_linie_feeds", {})
                     or {}).get(schluessel)
                # 8 s statt 4 s (1.9.31): unter Last lieber das letzte gute
                # Bild liefern als 404 - der Client haelt es ohnehin nur,
                # bis das naechste kommt.
                if not f or time.time() - f["ts"] > 8.0:
                    return self._bytes(b"", "image/jpeg", 404)
                return self._bytes(f["jpg"], "image/jpeg")

            if weg == "/api/alarme":
                # Alarmliste mit Historie (Stufe 2).
                return self._json(verarbeitung.alarmbuch.liste())

            if weg == "/api/eaio":
                e = getattr(verarbeitung, "eaio", None)
                return self._json(e.status() if e else {"fehler": "nicht verfuegbar"})

            if weg == "/api/sps":
                return self._json(verarbeitung.sps_status())

            if weg == "/api/rollen":
                r = getattr(verarbeitung, "rollen", None)
                if r is None:
                    return self._json({"aktiv": False, "rolle": "admin", "pins": {}, "protokoll": []})
                return self._json(r.uebersicht(r.rolle(self.headers.get("X-SE-Token", ""))))

            if weg == "/api/rezepte":
                rb = getattr(verarbeitung, "rezeptbuch", None)
                return self._json(rb.uebersicht() if rb
                                  else {"aktiv": "", "rezepte": {}})

            if weg == "/api/pruef_csv":
                # Ergebnis-Protokoll als CSV (Stufe 1) - Rueckverfolgbarkeit.
                text = verarbeitung.pruefbuch.csv_text()
                roh = text.encode("utf-8-sig")       # BOM: Excel liest Umlaute
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition",
                                 'attachment; filename="vorsa_pruefprotokoll_'
                                 + time.strftime("%Y%m%d_%H%M") + '.csv"')
                self.send_header("Content-Length", str(len(roh)))
                self.end_headers()
                self.wfile.write(roh)
                return

            if weg == "/api/testsatz_bild":
                datei = (frage.get("datei") or [""])[0]
                ts = verarbeitung.testsatz
                b = ts.bild(datei) if (ts is not None and datei) else None
                return self._bytes(b or b"", "image/jpeg", 200 if b else 404)

            if weg == "/api/pruef_bild":
                # Archivbild eines Nicht-GUT-Falls (nur aus dem Archivordner).
                datei = (frage.get("datei") or [""])[0]
                ordner = verarbeitung.pruefbuch._archiv_ordner
                if not datei or ordner is None:
                    return self._bytes(b"", "image/jpeg", 404)
                pfad = (ordner / Path(datei).name)
                try:
                    if not pfad.resolve().is_relative_to(ordner.resolve()):
                        return self._bytes(b"", "image/jpeg", 403)
                    if not pfad.exists():
                        return self._bytes(b"", "image/jpeg", 404)
                    return self._bytes(pfad.read_bytes(), "image/jpeg")
                except Exception:
                    return self._bytes(b"", "image/jpeg", 404)

            if weg == "/api/snapshot":
                bild = verarbeitung.hole_anzeige()
                if bild is None:
                    return self._json({"fehler": "kein Bild"}, 503)
                # Qualitaet nach Groesse: ein grosses Bild darf staerker
                # komprimiert werden, es hat mehr Pixel zum Verstecken. So
                # bleibt die Datenmenge aehnlich, obwohl das Bild schaerfer wird.
                guete = 82 if bild.shape[1] <= 1000 else 74
                ok, buf = cv2.imencode(".jpg", bild,
                                       [cv2.IMWRITE_JPEG_QUALITY, guete])
                return self._bytes(buf.tobytes(), "image/jpeg")

            if weg == "/api/ausschnitt":
                # Genau das Bild, das an den Chip geht - fuer die Miniatur
                # "Was der Chip sieht". Auf Modellgroesse skaliert, damit man
                # sieht, was das Modell wirklich bekommt, nicht das Original.
                bild = verarbeitung.hole_ausschnitt()
                if bild is None:
                    return self._bytes(b"kein Bild", "text/plain", 503)
                px = config.MODEL.input_size[0]
                klein = cv2.resize(bild, (px, px), interpolation=cv2.INTER_AREA)
                ok, buf = cv2.imencode(".jpg", klein, [cv2.IMWRITE_JPEG_QUALITY, 85])
                return self._bytes(buf.tobytes(), "image/jpeg")

            if weg == "/stream.mjpg":
                return self._strom()

            if weg == "/api/prototyp":
                datei = frage.get("datei", [""])[0]
                bild = zustand.prototyp_bild(datei)
                if bild is None:
                    return self._bytes(b"nicht gefunden", "text/plain", 404)
                ok, buf = cv2.imencode(".jpg", bild, [cv2.IMWRITE_JPEG_QUALITY, 80])
                return self._bytes(buf.tobytes(), "image/jpeg")

            if weg == "/api/prototypen":
                kid = int(frage.get("klasse", ["0"])[0])
                k = zustand.klassen.get(kid)
                return self._json({"dateien": k.prototypen if k else []})

            if weg == "/api/vorschau":
                kid = int(frage.get("klasse", ["0"])[0])
                datei = frage.get("datei", [""])[0]
                nummer = int(frage.get("nr", ["0"])[0])
                varianten = zustand.varianten_vorschau(kid, datei)
                if nummer >= len(varianten):
                    return self._bytes(b"nicht vorhanden", "text/plain", 404)
                return self._bytes(varianten[nummer]["jpeg"], "image/jpeg")

            if weg == "/api/vorschau_liste":
                kid = int(frage.get("klasse", ["0"])[0])
                datei = frage.get("datei", [""])[0]
                varianten = zustand.varianten_vorschau(kid, datei)
                return self._json({"varianten": [
                    {"nr": i, "name": v["name"], "winkel": v["winkel"]}
                    for i, v in enumerate(varianten)]})

            if weg == "/api/ereignis":
                datei = frage.get("datei", [""])[0]
                bild = zustand.ereignis_bild(datei)
                if bild is None:
                    return self._bytes(b"nicht gefunden", "text/plain", 404)
                ok, buf = cv2.imencode(".jpg", bild, [cv2.IMWRITE_JPEG_QUALITY, 80])
                return self._bytes(buf.tobytes(), "image/jpeg")

            if weg == "/api/ereignisse":
                return self._json({"eintraege": list(reversed(zustand.ereignisse))})

            if weg == "/api/lauf":
                name = frage.get("name", [""])[0]
                l = laeufe.get(name)
                if l is None:
                    return self._json({"fehler": f"kein Lauf {name!r}",
                                       "vorhanden": sorted(laeufe)}, 404)
                return self._json(l.as_dict())

            if weg == "/api/trainingsplan":
                return self._json(zustand.trainingsplan())

            if weg == "/api/karten":
                return self._json(karten_info(verarbeitung.lerner))

            return self._bytes(b"nicht gefunden", "text/plain", 404)

        # --- MJPEG --------------------------------------------------
        def _strom(self):
            grenze = "vorsaframe"
            self.send_response(200)
            self.send_header(
                "Content-Type", f"multipart/x-mixed-replace; boundary={grenze}")
            self.send_header("Cache-Control", "no-store")
            # Der Strom endet nie und hat keine Laengenangabe. Ohne
            # "Connection: close" wartet ein HTTP/1.1-Client auf ein Ende,
            # das nicht kommt.
            self.send_header("Connection", "close")
            self.close_connection = True
            self.end_headers()
            try:
                while True:
                    bild = verarbeitung.hole_anzeige()
                    if bild is None:
                        time.sleep(0.05)
                        continue
                    ok, buf = cv2.imencode(
                        ".jpg", bild, [cv2.IMWRITE_JPEG_QUALITY, 75])
                    if not ok:
                        continue
                    roh = buf.tobytes()
                    self.wfile.write(f"--{grenze}\r\n".encode())
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(f"Content-Length: {len(roh)}\r\n\r\n".encode())
                    self.wfile.write(roh)
                    self.wfile.write(b"\r\n")
                    time.sleep(0.05)
            except (BrokenPipeError, ConnectionResetError):
                pass

        # --- POST ---------------------------------------------------
        def _post_roh(self):
            weg = urlparse(self.path).path
            koerper = self._koerper()

            if weg == "/api/bereich":
                b = zustand.bereich_setzen(
                    koerper.get("fenster"), koerper.get("cx"), koerper.get("cy"))
                # Sofort selbst rechnen statt auf das naechste Kamerabild zu
                # warten. Sonst meldet die Antwort den Stand von vorher, und
                # der Regler scheint wirkungslos.
                info = zustand.bereich_info
                w = info.get("bild_breite") or 0
                h = info.get("bild_hoehe") or 0
                if w and h:
                    x, y, seite, hinweis = b.rechteck(
                        w, h, config.MODEL.input_size[0])
                    return self._json({
                        **b.as_dict(), "x": x, "y": y, "seite": seite,
                        "hinweis": hinweis, "bild_breite": w, "bild_hoehe": h,
                        "modell_px": config.MODEL.input_size[0],
                    })
                return self._json({**b.as_dict(), **info})

            if weg == "/api/kamera_setzen":
                r = verarbeitung.quelle.setze(
                    str(koerper.get("name", "")), float(koerper.get("wert", 0)))
                return self._json({**r, "werte": verarbeitung.quelle.lies_einstellungen()})

            if weg == "/api/kamera_einfrieren":
                return self._json(verarbeitung.quelle.einfrieren())

            if weg == "/api/kamera_automatik":
                return self._json(verarbeitung.quelle.automatik_an())

            if weg == "/api/kamera_zuruecksetzen":
                return self._json(verarbeitung.quelle.zuruecksetzen())

            if weg == "/api/kamera_neu":
                return self._json(verarbeitung.quelle.neu_oeffnen())

            if weg == "/api/linie":
                # Linie aktivieren/stoppen ("Linie aktivieren"-Knopf) -
                # oder nur den Takt wechseln ({takt: "fluss"|"einzel"}).
                li = verarbeitung.linie
                if verarbeitung.profil != "linie" and koerper.get("aktiv"):
                    return self._json({"fehler": "Profil stationaer: keine Linie "
                                       "(Start mit VORSA_PROFIL=linie)"}, 409)
                if koerper.get("takt") in ("fluss", "einzel"):
                    li.takt = koerper["takt"]
                    try:
                        li.speichern(verarbeitung.zustand.ordner)
                    except Exception:
                        pass
                    if li.aktiv:
                        if li.takt == "fluss" and li.phase in ("warte", "band"):
                            li._wechsel("lauf", "Takt: Fluss")
                            li.band.start()
                        elif li.takt == "einzel" and li.phase in ("lauf", "pruefen"):
                            li.band.stopp()
                            li._wechsel("warte", "Takt: Einzel")
                if "aktiv" in koerper:
                    li.aktivieren(bool(koerper.get("aktiv")))
                return self._json(li.als_dict())

            if weg == "/api/linie_ansicht":
                # Client-Heartbeat: Linien-Splitansicht ist offen - die
                # Zonen-Erkennung laeuft dann auch ohne aktive Linie
                # (Spiegel der Zonen). TTL statt Abmelde-Pflicht.
                verarbeitung._linie_ansicht_bis = (
                    time.time() + 12 if koerper.get("an") else 0)
                return self._json({"ok": True})

            if weg == "/api/rahmen_pause":
                # Aufnahmerahmen kurz ausblenden (Zonen-Ziehmodus).
                verarbeitung._rahmen_pause_bis = (
                    time.time() + 180 if koerper.get("an") else 0)
                return self._json({"pause": bool(koerper.get("an"))})

            if weg == "/api/arm":
                # Befehle an den eingebauten Arduino-Arm (ARM-Dialog).
                a = verarbeitung.arm_uno
                if a is None:
                    return self._json({"fehler": "kein Arduino-Arm "
                                       "(Start mit VORSA_ARM=uno)"}, 409)
                tat = str(koerper.get("tat", ""))
                try:
                    if tat == "motoren":
                        a.motoren_an(bool(koerper.get("an")))
                    elif tat == "home":
                        a.home_start()
                    elif tat == "jog":
                        a.jog(str(koerper.get("achse")),
                              int(koerper.get("schritte", 0)))
                    elif tat == "pumpe":
                        a.pumpe_setzen(bool(koerper.get("an")))
                    elif tat == "tempo":
                        a.tempo(int(koerper.get("us", 1000)))
                    elif tat == "stop":
                        a.stop()
                    elif tat == "punkt_merken":
                        a.punkt_merken(str(koerper.get("name", "")))
                    elif tat == "punkt_geh":
                        a.punkt_geh(str(koerper.get("name", "")))
                    elif tat == "punkt_weg":
                        a.punkt_weg(str(koerper.get("name", "")))
                    elif tat == "programm_speichern":
                        a.programm_speichern(
                            "Holen", list(koerper.get("steps") or []))
                    elif tat == "programm_test":
                        a.programm_start(
                            "Holen",
                            int(koerper.get("durchlaeufe", 1) or 1))
                    else:
                        return self._json({"fehler": "tat?"}, 404)
                except Exception as exc:
                    return self._json({"detail": str(exc)[:160]}, 409)
                return self._json(a.zustand())

            if weg == "/api/linie_quelle":
                # Bildquelle je Zone: "haupt" oder "usb0"/"usb1"/... Die
                # USB-Kamera IST dann als Ganzes die Zone (1.7.0).
                art = str(koerper.get("art", "abhol"))
                q = str(koerper.get("quelle", "haupt"))
                if getattr(verarbeitung, "einkamera", True) and q != "haupt":
                    return self._json({"fehler": "Einkamera-Betrieb: Zonen kommen aus der "
                                       "Hauptkamera (Zweitkamera: VORSA_ZWEITKAMERA=1)"}, 409)
                if art in ("lern_a", "lern_b"):
                    # Lernzone (1.9.29): Kamera des Slots waehlen.
                    return self._json({"lernzonen": verarbeitung.lernzone_setzen(
                        art[-1], quelle=q)})
                if art == "anliefer2":
                    # Blick 2 (1.9.27): zweite Kamera auf die Anlieferung.
                    verarbeitung.blick2_setzen(quelle=q)
                    return self._json(verarbeitung.linie.als_dict()
                                      | {"blick2": dict(verarbeitung._blick2)})
                if art not in ("anliefer", "abhol") or not (
                        q == "haupt" or q.startswith("usb")
                        or q.startswith("picam")):
                    return self._json({"fehler": "art=anliefer|abhol, "
                                       "quelle=haupt|usbN|picamN"})
                alt = str(verarbeitung.linie.quellen.get(art, "haupt"))
                feld = "anliefer" if art == "anliefer" else "abhol"
                merk = getattr(verarbeitung.linie, "_haupt_zonen", {})
                verarbeitung.linie._haupt_zonen = merk
                if alt == "haupt" and q != "haupt":
                    # Rechteck der Hauptkamera merken; im USB-Bild
                    # startet die Zone als (fast) ganzes Bild - im
                    # Feed laesst sie sich enger ziehen.
                    merk[art] = tuple(getattr(verarbeitung.linie, feld))
                    setattr(verarbeitung.linie, feld,
                            (0.02, 0.02, 0.98, 0.98))
                elif alt != "haupt" and q == "haupt" and art in merk:
                    setattr(verarbeitung.linie, feld, merk[art])
                verarbeitung.linie.quellen[art] = q
                verarbeitung.linie.speichern(zustand.ordner)
                verarbeitung.linie._zone_frisch = time.time()
                print(f"  Linien-Quelle {art}: {q}", flush=True)
                return self._json(verarbeitung.linie.als_dict())

            if weg == "/api/linie_zone":
                # Zone im Kamerabild aufgezogen: [x0,y0,x1,y1] relativ 0..1
                # im Erkennungs-Ausschnitt.
                try:
                    x0, y0, x1, y1 = [max(0.0, min(1.0, float(v)))
                                      for v in (koerper.get("zone") or [])]
                except Exception:
                    return self._json({"fehler": "zone = [x0,y0,x1,y1]"})
                x0, x1 = sorted((x0, x1))
                y0, y1 = sorted((y0, y1))
                if x1 - x0 < 0.05 or y1 - y0 < 0.05:
                    return self._json({"fehler": "Zone zu klein - bitte ein "
                                       "groesseres Rechteck aufziehen."})
                z = (round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3))
                art = str(koerper.get("art", "abhol"))
                if art in ("lern_a", "lern_b"):
                    return self._json({"lernzonen": verarbeitung.lernzone_setzen(
                        art[-1], zone=z), "quellen": {}})
                if art == "anliefer2":
                    verarbeitung.blick2_setzen(zone=z)
                    return self._json(verarbeitung.linie.als_dict()
                                      | {"blick2": dict(verarbeitung._blick2)})
                if art == "anliefer":
                    verarbeitung.linie.anliefer = z
                else:
                    verarbeitung.linie.abhol = z
                verarbeitung.linie.speichern(zustand.ordner)
                # Kurz anzeigen, auch wenn die Linie noch aus ist - sonst
                # sieht man nicht, was man gerade gesetzt hat.
                verarbeitung.linie._zone_frisch = time.time()
                print(f"  Linien-Zone {art}: {z}", flush=True)
                return self._json(verarbeitung.linie.als_dict())

            if weg == "/api/drehen":
                # Kamerabild um 90 Grad weiterdrehen (0/90/180/270).
                verarbeitung.drehung = (getattr(verarbeitung, "drehung", 0)
                                        + 90) % 360
                # Die Linien-Zonen drehen sich MIT dem Bild - sonst zeigen
                # die Rahmen nach der Drehung auf die falsche Stelle.
                # np.rot90 (k=1, CCW): Punkt (x, y) -> (y, 1 - x).
                # ABER: drehung gilt NUR fuers Hauptkamerabild (Zeile ~971).
                # Zonen auf einer eigenen Kamera (picam/usb) duerfen NICHT
                # mitgedreht werden - deren Bild bleibt ja stehen, sonst
                # zeigt die Zone ins Leere (2026-09-07).
                def _rz(z):
                    p = [(z[0], z[1]), (z[2], z[3])]
                    p = [(py, 1.0 - px) for px, py in p]
                    xs = sorted((p[0][0], p[1][0]))
                    ys = sorted((p[0][1], p[1][1]))
                    return (round(xs[0], 3), round(ys[0], 3),
                            round(xs[1], 3), round(ys[1], 3))
                _q = getattr(verarbeitung.linie, "quellen", {}) or {}
                gedreht = []
                if str(_q.get("anliefer", "haupt")) == "haupt":
                    verarbeitung.linie.anliefer = _rz(verarbeitung.linie.anliefer)
                    gedreht.append("anliefer")
                if str(_q.get("abhol", "haupt")) == "haupt":
                    verarbeitung.linie.abhol = _rz(verarbeitung.linie.abhol)
                    gedreht.append("abhol")
                verarbeitung.linie.speichern(zustand.ordner)
                print(f"  Bilddrehung: {verarbeitung.drehung} Grad "
                      f"(mitgedrehte Zonen: {gedreht or 'keine'})", flush=True)
                return self._json({"drehung": verarbeitung.drehung})

            if weg == "/api/feed_kamera":
                # Kamerasteuerung pro Feed (Autofokus/Belichtung), 1.9.6.
                # quelle: "haupt" | "picamN" | "usbN"; aktion: s. unten.
                quelle = str(koerper.get("quelle", "haupt"))
                aktion = str(koerper.get("aktion", ""))
                ev = getattr(verarbeitung, "_feed_ev", None)
                if ev is None:
                    ev = verarbeitung._feed_ev = {}
                if aktion == "af_auto":
                    controls = {"AfMode": 2}
                elif aktion == "af_einmal":
                    controls = {"AfMode": 1, "AfTrigger": 0}
                elif aktion in ("heller", "dunkler"):
                    # ECHTE BELICHTUNG (1.9.15): nicht heller RECHNEN
                    # (Brightness-Offset -> blass), sondern mehr Licht
                    # EINFANGEN. Automatik aus, aktuelle Belichtungszeit und
                    # Verstaerkung lesen und je Schritt um den Faktor 1.4
                    # skalieren: erst die Zeit bis zur Bildrate-Grenze
                    # (~30 ms), dann die Verstaerkung. Dunkler umgekehrt.
                    if quelle == "haupt":
                        kam0 = getattr(verarbeitung, "quelle", None)
                        md = (kam0.metadaten()
                              if hasattr(kam0, "metadaten") else {})
                    elif quelle.startswith("picam"):
                        md = verarbeitung.zweitkamera.metadaten(quelle)
                    else:
                        md = {}
                    t = float(md.get("ExposureTime") or 10000.0)
                    g = float(md.get("AnalogueGain") or 1.0)
                    if aktion == "heller":
                        if t < 30000.0:
                            t = min(30000.0, t * 1.4)
                        else:
                            g = min(16.0, g * 1.4)
                    else:
                        if g > 1.05:
                            g = max(1.0, g / 1.4)
                        else:
                            t = max(200.0, t / 1.4)
                    ev[quelle] = round((t / 10000.0) * g, 2)   # nur Anzeige
                    controls = {"AeEnable": False, "ExposureTime": int(t),
                                "AnalogueGain": float(g), "Brightness": 0.0}
                elif aktion == "belichtung_auto":
                    ev[quelle] = 0.0
                    controls = {"AeEnable": True, "ExposureValue": 0.0,
                                "Brightness": 0.0}
                elif aktion == "alles_auto":
                    # Alle Automatiken dieser Kamera zurueck (1.9.19):
                    # Belichtung, Weissabgleich, dauerhafter Autofokus,
                    # Bildparameter neutral. Der Ein-Klick-Reset, wenn eine
                    # Kamera nach Handeingriffen dunkel/unscharf haengt.
                    ev[quelle] = 0.0
                    controls = {"AeEnable": True, "AwbEnable": True,
                                "AfMode": 2, "ExposureValue": 0.0,
                                "Brightness": 0.0, "Contrast": 1.0,
                                "Saturation": 1.0, "Sharpness": 1.0}
                elif aktion == "roh":
                    # Voller Durchgriff (1.9.19): {controls:{...}} mit
                    # libcamera-Namen. Zahlenwerte werden gefiltert, damit
                    # nichts Unerwartetes an die Kamera geht.
                    erlaubt = {"ExposureTime": int, "AnalogueGain": float,
                               "LensPosition": float, "Contrast": float,
                               "Saturation": float, "Sharpness": float,
                               "Brightness": float, "ExposureValue": float,
                               "AeEnable": bool, "AwbEnable": bool,
                               "AfMode": int, "AfTrigger": int,
                               "ColourGains": tuple}
                    roh = koerper.get("controls") or {}
                    controls = {}
                    for k_, v_ in roh.items():
                        if k_ not in erlaubt:
                            continue
                        try:
                            if erlaubt[k_] is tuple:
                                controls[k_] = (float(v_[0]), float(v_[1]))
                            else:
                                controls[k_] = erlaubt[k_](v_)
                        except Exception:
                            continue
                    # Weissabgleich als Farbtemperatur (Kelvin) ueber die
                    # gleiche Kurve wie im Kameradialog der Hauptkamera.
                    if "kelvin" in roh:
                        try:
                            t = min(7500.0, max(2000.0, float(roh["kelvin"])))
                            rot = 2.8 - (t - 2000.0) / 5500.0 * 1.6
                            blau = 1.2 + (t - 2000.0) / 5500.0 * 1.4
                            controls["AwbEnable"] = False
                            controls["ColourGains"] = (rot, blau)
                        except Exception:
                            pass
                    if "ExposureTime" in controls or "AnalogueGain" in controls:
                        controls.setdefault("AeEnable", False)
                    if "LensPosition" in controls:
                        controls.setdefault("AfMode", 0)
                    if not controls:
                        return self._json({"ok": False, "grund": "controls?"}, 400)
                else:
                    return self._json({"ok": False, "grund": "Aktion?"}, 400)
                if quelle == "haupt":
                    kam = getattr(verarbeitung, "quelle", None)
                    res = (kam.steuere(controls)
                           if hasattr(kam, "steuere")
                           else {"ok": False, "grund": "Hauptkamera ohne "
                                 "Steuerung (USB-Rueckfall?)"})
                    # Schalterwert im Einstellungsdialog ehrlich halten:
                    # Licht +/- schaltet die Automatik aus, Auto wieder an.
                    try:
                        if hasattr(kam, "_werte"):
                            w_ = kam._werte
                            if "AeEnable" in controls:
                                w_["auto_belichtung"] = (
                                    3.0 if controls["AeEnable"] else 1.0)
                            if "AwbEnable" in controls:
                                w_["auto_weissabgleich"] = (
                                    1.0 if controls["AwbEnable"] else 0.0)
                            if "AfMode" in controls:
                                w_["autofokus"] = (
                                    1.0 if controls["AfMode"] == 2 else 0.0)
                    except Exception:
                        pass
                elif quelle.startswith("picam"):
                    res = verarbeitung.zweitkamera.steuere(quelle, controls)
                else:
                    res = {"ok": False, "grund": "USB: keine Kamerasteuerung"}
                res = dict(res)
                res["ev"] = round(ev.get(quelle, 0.0), 1)
                return self._json(res)

            if weg in ("/api/rezept_speichern", "/api/rezept_laden",
                       "/api/rezept_loeschen"):
                # Rezepte/Auftraege (Stufe 4).
                rb = getattr(verarbeitung, "rezeptbuch", None)
                if rb is None:
                    return self._json({"ok": False,
                                       "grund": "Rezeptbuch nicht verfuegbar"})
                name = str(koerper.get("name", ""))
                if weg.endswith("speichern"):
                    return self._json(rb.aufnehmen(name, verarbeitung, zustand))
                if weg.endswith("laden"):
                    return self._json(rb.anwenden(name, verarbeitung, zustand))
                return self._json(rb.loeschen(name))

            if weg == "/api/pruefen":
                # STATIONAER (1.9.38): Szene jetzt pruefen und buchen.
                return self._json(verarbeitung.pruefen_jetzt())

            if weg == "/api/testsatz":
                # TESTSATZ (A6): {tat: aufnehmen|liste|loeschen|soll, ...}
                ts = verarbeitung.testsatz
                if ts is None:
                    return self._json({"ok": False, "grund": "kein Testsatz"}, 503)
                tat = str(koerper.get("tat", "liste"))
                if tat == "aufnehmen":
                    return self._json(verarbeitung.testsatz_aufnehmen(
                        koerper.get("soll") or [], str(koerper.get("notiz", ""))))
                if tat == "loeschen":
                    return self._json(ts.loeschen(int(koerper.get("id", -1))))
                if tat == "soll":
                    return self._json(ts.soll_aendern(int(koerper.get("id", -1)),
                                                      koerper.get("soll") or [],
                                                      koerper.get("notiz")))
                return self._json({"ok": True, "szenen": ts.szenen,
                                   "uebersicht": ts.uebersicht()})

            if weg == "/api/sps":
                return self._json(verarbeitung.sps_einstellen(koerper))

            if weg in ("/api/anmelden", "/api/abmelden", "/api/rollen"):
                r = getattr(verarbeitung, "rollen", None)
                if r is None:
                    return self._json({"ok": False, "grund": "Rollen nicht verfuegbar"}, 409)
                if weg == "/api/anmelden":
                    return self._json(r.anmelden(str(koerper.get("pin", ""))))
                if weg == "/api/abmelden":
                    return self._json(r.abmelden(self.headers.get("X-SE-Token", "")))
                rolle = r.rolle(self.headers.get("X-SE-Token", ""))
                return self._json(r.verwalten(rolle, koerper))

            if weg == "/api/eaio":
                # I1: {aktion: "einstellen", ...cfg} | {aktion: "test", signal}
                e = getattr(verarbeitung, "eaio", None)
                if e is None:
                    return self._json({"ok": False, "grund": "nicht verfuegbar"}, 409)
                if koerper.get("aktion") == "test":
                    return self._json(e.test(str(koerper.get("signal", ""))))
                if koerper.get("aktion") == "einstellen":
                    return self._json(e.einstellen(koerper))
                return self._json({"ok": False, "grund": "aktion=einstellen|test"}, 400)

            if weg == "/api/pruef_einst":
                # Stufe 5: {schwelle: 0..1 | null, unbekannt_ziel: %}
                # 1.9.38: {ausloeser: "hand"|"auto"}
                if koerper.get("ausloeser") in ("hand", "auto", "extern"):
                    return self._json(verarbeitung.pruef_ausloeser_setzen(
                        koerper["ausloeser"]))
                if koerper.get("mehrbild") is not None:
                    return self._json(verarbeitung.mehrbild_setzen(koerper["mehrbild"]))
                return self._json(verarbeitung.pruef_einst_setzen(
                    schwelle=koerper.get("schwelle"),
                    unbekannt_ziel=koerper.get("unbekannt_ziel"),
                    schwelle_aus=bool(koerper.get("schwelle_aus"))))

            if weg == "/api/pruef_uebernehmen":
                # Nachlern-Ausloeser (Stufe 5): ein archiviertes UNBEKANNT-
                # Bild als Lernfoto einer Klasse uebernehmen.
                datei = Path(str(koerper.get("datei", ""))).name
                try:
                    kid = int(koerper.get("klasse"))
                except Exception:
                    return self._json({"ok": False, "grund": "klasse?"})
                ordner = verarbeitung.pruefbuch._archiv_ordner
                if not datei or ordner is None:
                    return self._json({"ok": False, "grund": "kein Archiv"})
                pfad = ordner / datei
                bild = cv2.imread(str(pfad)) if pfad.exists() else None
                if bild is None:
                    return self._json({"ok": False, "grund": "Bild fehlt"})
                k = zustand.klassen.get(kid)
                if k is None:
                    return self._json({"ok": False, "grund": "Klasse unbekannt"})
                name = zustand.prototyp_speichern(kid, bild)
                return self._json({"ok": bool(name), "klasse": k.name,
                                   "anzahl": len(k.prototypen),
                                   "hinweis": "Danach Chip-Lernen ausfuehren."})

            if weg == "/api/karte_reset":
                # Karten-Waechter (1.9.36): haengende Karte per PCIe neu
                # einbinden - dauert ~6 s, blockiert solange die Erkennung.
                try:
                    nr = int(koerper.get("nr", -1))
                except Exception:
                    nr = -1
                return self._json(verarbeitung.karte_reset(nr))

            if weg == "/api/leerbild":
                # Leerbild (Referenz des leeren Bands) je Kamera merken /
                # loeschen (2026-09-19). {quelle, tat: "merken"|"loeschen"}
                q = str(koerper.get("quelle", "haupt"))
                if koerper.get("tat") == "loeschen":
                    return self._json(verarbeitung.leerbild_loeschen(q))
                return self._json(verarbeitung.leerbild_merken(
                    q, int(koerper.get("bilder", 16) or 16)))

            if weg == "/api/korrektur":
                # KORREKTUR-LERNEN (1.9.20): der Bediener zieht den RICHTIGEN
                # Rahmen um ein Teil, das die Segmentierung zu klein gefasst
                # hat (z. B. nur die Aufschrift der SD-Karte). Der Ausschnitt
                # wird als Lernfoto der Klasse abgelegt - mit Randluft, damit
                # das Freistellen das Band als Hintergrund sieht. Beim
                # naechsten Chip-Lernen kennt der Chip die ganze Silhouette.
                try:
                    kid = int(koerper.get("klasse"))
                    x0, y0, x1, y1 = [max(0.0, min(1.0, float(v)))
                                      for v in (koerper.get("zone") or [])]
                except Exception:
                    return self._json({"ok": False,
                                       "grund": "klasse + zone [x0,y0,x1,y1]"})
                x0, x1 = sorted((x0, x1))
                y0, y1 = sorted((y0, y1))
                if x1 - x0 < 0.02 or y1 - y0 < 0.02:
                    return self._json({"ok": False, "grund": "Rahmen zu klein"})
                quelle = str(koerper.get("quelle", "haupt"))
                if quelle == "haupt":
                    bild = verarbeitung.hole_roh()
                else:
                    bild, _f = verarbeitung.zweitkamera.bild(quelle)
                if bild is None:
                    return self._json({"ok": False, "grund": "kein Bild"})
                h, w = bild.shape[:2]
                # 18 % Randluft je Seite (geclampt) - der Rand muss Band sein.
                bw, bh = (x1 - x0) * w, (y1 - y0) * h
                px0 = int(max(0, x0 * w - 0.18 * bw))
                py0 = int(max(0, y0 * h - 0.18 * bh))
                px1 = int(min(w, x1 * w + 0.18 * bw))
                py1 = int(min(h, y1 * h + 0.18 * bh))
                if px1 - px0 < 24 or py1 - py0 < 24:
                    return self._json({"ok": False, "grund": "Ausschnitt zu klein"})
                crop = np.ascontiguousarray(bild[py0:py1, px0:px1])
                k = zustand.klassen.get(kid)
                if k is None:
                    return self._json({"ok": False, "grund": "Klasse unbekannt"})
                name = zustand.prototyp_speichern(kid, crop)
                if not name:
                    return self._json({"ok": False, "grund": "nicht gespeichert"})
                try:
                    verarbeitung.alarmbuch.melde(
                        "korrektur", "info",
                        f"Korrektur-Beispiel fuer {k.name} abgelegt "
                        f"({px1 - px0}x{py1 - py0} px, {quelle})", einmalig=True)
                except Exception:
                    pass
                return self._json({"ok": True, "klasse": k.name, "datei": name,
                                   "anzahl": len(k.prototypen),
                                   "hinweis": "Danach einmal Chip-Lernen "
                                              "ausfuehren, damit es wirkt."})

            if weg == "/api/alarm_quittieren":
                # Alarm(e) quittieren (Stufe 2): {"id": n} oder {"alle": true}
                if koerper.get("alle"):
                    n = verarbeitung.alarmbuch.quittiere(None)
                else:
                    try:
                        n = verarbeitung.alarmbuch.quittiere(
                            int(koerper.get("id")))
                    except Exception:
                        return self._json({"ok": False, "grund": "id?"}, 400)
                return self._json({"ok": True, "quittiert": n,
                                   **verarbeitung.alarmbuch.liste()})

            if weg == "/api/pruef_reset":
                # Sitzungszaehler des Pruefbuchs auf null (Stufe 1). Das
                # Bildarchiv bleibt - es ist Nachlern-Material.
                verarbeitung.pruefbuch.reset()
                verarbeitung._pruef_gefoerdert = int(getattr(
                    verarbeitung.linie, "gefoerdert", 0) or 0) \
                    if verarbeitung.linie is not None else 0
                return self._json({"ok": True})

            if weg == "/api/anzeigegroesse":
                # Der Browser sagt, wie breit er das Bild darstellt. Alles
                # andere ist Raten - und Raten hat hier zweimal danebengelegen:
                # ein 960-px-Bild in einem 1560-px-Feld wird um Faktor 1,6
                # hochgezogen, und dann ist ALLES unscharf, nicht nur der
                # Rahmen.
                alt = verarbeitung.anzeige_groesse
                # Deckel 2048: mit Digital-Zoom meldet der Browser mehr als
                # die Fensterbreite - bis Faktor 3. Mehr als ~2048 px bringt
                # nichts (der Kamera-Crop hat selten mehr echte Pixel) und
                # kostet nur JPEG-Zeit.
                neu = int(max(480, min(2048, float(koerper.get("breite", alt)))))
                if abs(neu - alt) > 32:
                    verarbeitung.anzeige_groesse = neu
                    print(f"  Livebild jetzt {neu} px "
                          f"(vorher {alt}) - vom Browser gemeldet", flush=True)
                return self._json({"breite": verarbeitung.anzeige_groesse})

            if weg == "/api/anzeige":
                try:
                    a = zustand.anzeige_setzen(koerper.get("felder"),
                                               str(koerper.get("vorlage", "")))
                except KeyError as exc:
                    return self._json({"fehler": f"Vorlage {exc} unbekannt"}, 400)
                return self._json(a.as_dict())

            if weg == "/api/zaehler_zuruecksetzen":
                zustand.zaehler_zuruecksetzen()
                return self._json({"ok": True})

            if weg == "/api/ereignisse_leeren":
                return self._json({"ok": True, "geloescht": zustand.ereignisse_leeren()})

            if weg == "/api/ereignis_uebernehmen":
                # Einen schweren Fall zum Lernbild machen. Das ist der
                # eigentliche Sinn des Protokolls: die Anlage sammelt selbst,
                # woran sie scheitert, und man gibt es ihr zurueck.
                datei = str(koerper.get("datei", ""))
                kid = int(koerper.get("klasse", -1))
                bild = zustand.ereignis_bild(datei)
                if bild is None:
                    return self._json({"fehler": "Ereignis nicht gefunden"}, 404)
                name = zustand.prototyp_speichern(kid, bild)
                if name is None:
                    return self._json({"fehler": "Objekt unbekannt"}, 400)
                return self._json({"ok": True, "datei": name})

            if weg == "/api/preset_speichern":
                return self._json(zustand.preset_speichern(
                    str(koerper.get("name", "")),
                    verarbeitung.quelle.lies_einstellungen()))

            if weg == "/api/preset_laden":
                name = str(koerper.get("name", ""))
                p = zustand.presets.get(name)
                if p is None:
                    return self._json({"fehler": "unbekannt"}, 404)
                ergebnis = {}
                for k, v in (p.get("kamera") or {}).items():
                    ergebnis[k] = verarbeitung.quelle.setze(k, v)
                b = p.get("bereich") or {}
                zustand.bereich_setzen(b.get("fenster"), b.get("cx"), b.get("cy"))
                nicht_uebernommen = [k for k, r in ergebnis.items()
                                     if not r.get("uebernommen", True)]
                return self._json({
                    "geladen": name,
                    "werte": verarbeitung.quelle.lies_einstellungen(),
                    # Ehrlich melden, was die Kamera nicht angenommen hat -
                    # sonst glaubt man, das Preset sei vollstaendig wieder da.
                    "nicht_uebernommen": nicht_uebernommen,
                })

            if weg == "/api/preset_loeschen":
                return self._json({"ok": zustand.preset_loeschen(
                    str(koerper.get("name", "")))})

            if weg == "/api/lernen":
                lerner = verarbeitung.lerner
                lauf = laeufe.get("chip")
                if lerner is None or lauf is None:
                    return self._json({"ok": False, "grund": "kein Lerner"}, 503)
                # Im Hintergrund: mit 700 Beispielen und vier Versuchen dauert
                # das lange genug, dass die Anfrage sonst in eine
                # Zeitueberschreitung liefe und die Seite haengend aussaehe.
                mit_var = bool(koerper.get("mit_varianten", True))
                return self._json(lauf.starte(
                    lambda l: chip_lernen(zustand, lerner, mit_var, l).as_dict()))

            if weg == "/api/lernen_sofort":
                lerner = verarbeitung.lerner
                if lerner is None:
                    return self._json({"ok": False, "grund": "kein Lerner"}, 503)
                bericht = chip_lernen(
                    zustand, lerner,
                    mit_varianten=bool(koerper.get("mit_varianten", True)))
                if bericht.ok:
                    # Die Kameraeinstellung des Trainings festhalten. Alles,
                    # was sich danach verstellt, ist ab jetzt meldbar.
                    zustand.referenz_setzen(
                        verarbeitung.quelle.lies_einstellungen(hoechstalter=0.0))
                return self._json(bericht.as_dict())

            if weg == "/api/vergessen":
                if verarbeitung.lerner is not None:
                    verarbeitung.lerner.vergessen()
                    # Auch die Sicherung loeschen - sonst waere das Gelernte
                    # nach dem naechsten Neustart wieder da, obwohl es
                    # ausdruecklich verworfen wurde.
                    verarbeitung.lerner.loeschen(zustand.ordner)
                zustand.erkannt = None
                return self._json({"ok": True})

            if weg == "/api/aufnehmen":
                kid = int(koerper.get("klasse", 0))
                k0 = zustand.klassen.get(kid)
                if k0 is None:
                    return self._json({"fehler": "Klasse unbekannt"}, 400)
                # LERNZONEN (1.9.29): NUR wenn der Client die Lernzonen-
                # Ansicht offen hat (lernzonen:true), nimmt ein Klick aus
                # ALLEN aktiven Zonen auf. Sonst gilt der normale Lernrahmen -
                # vorher griff der Zonenweg auch bei geschlossener Ansicht,
                # weil Slot A standardmaessig aktiv ist (Fix 1.9.37).
                lz = verarbeitung._lernzonen
                if bool(koerper.get("lernzonen", False)) and any(
                        e.get("an") and e.get("quelle") != "aus"
                        for e in lz.values()):
                    r = verarbeitung.lernfotos_aufnehmen(kid, bool(k0.negativ))
                    letzte = next((x for x in r["ergebnisse"] if x.get("ok")), {})
                    return self._json({
                        "datei": letzte.get("datei", ""),
                        "anzahl": len(k0.prototypen),
                        "mit_augmentierung": len(k0.prototypen)
                            * k0.augment.anzahl_varianten(),
                        "pruefung": letzte.get("pruefung", {"ok": True, "maengel": []}),
                        "lernzonen": r["ergebnisse"],
                        "gespeichert": r["gespeichert"],
                    })
                # Gespeichert wird der AUSSCHNITT, nicht das ganze Kamerabild.
                # Genau dieses Bild bekommt spaeter auch der Chip.
                bild = verarbeitung.hole_ausschnitt()
                if bild is None:
                    return self._json({"fehler": "kein Bild"}, 503)
                k = zustand.klassen.get(kid)
                if k is None:
                    return self._json({"fehler": "Klasse unbekannt"}, 400)

                # Sofort pruefen, nicht erst beim Training. Ein unbrauchbares
                # Foto faellt sonst erst Stunden spaeter auf - und bis dahin
                # liegen neun weitere daneben, die denselben Fehler haben.
                try:
                    pruefung = zustand.foto_pruefen(bild, negativ=k.negativ)
                except Exception as exc:
                    pruefung = {"ok": True, "maengel": [],
                                "fehler": str(exc)[:80]}

                name = zustand.prototyp_speichern(kid, bild)
                return self._json({
                    "datei": name,
                    "anzahl": len(k.prototypen),
                    "mit_augmentierung": len(k.prototypen) * k.augment.anzahl_varianten(),
                    "pruefung": pruefung,
                })

            if weg == "/api/klasse_neu":
                k = zustand.klasse_anlegen(str(koerper.get("name", "")).strip(),
                                           bool(koerper.get("negativ", False)))
                return self._json(k.as_dict())

            if weg == "/api/klasse_aendern":
                k = zustand.klasse_aendern(
                    int(koerper.get("id", -1)),
                    koerper.get("name"), koerper.get("augment"),
                    koerper.get("negativ"))
                if k is None:
                    return self._json({"fehler": "unbekannt"}, 404)
                return self._json(k.as_dict())

            if weg == "/api/klasse_loeschen":
                ok = zustand.klasse_loeschen(int(koerper.get("id", -1)))
                return self._json({"ok": ok})

            if weg == "/api/prototyp_loeschen":
                ok = zustand.prototyp_loeschen(
                    int(koerper.get("klasse", -1)), str(koerper.get("datei", "")))
                return self._json({"ok": ok})

            if weg == "/api/betriebsart":
                art = str(koerper.get("art", "betreiben"))
                # "erkennen" bleibt als alter Name gueltig, damit eine
                # gespeicherte Verknuepfung nicht ins Leere laeuft.
                art = {"erkennen": "betreiben"}.get(art, art)
                if art not in ("einrichten", "anlernen", "betreiben", "messen"):
                    return self._json({"fehler": f"Betriebsart {art!r} unbekannt"}, 400)
                zustand.betriebsart = art
                return self._json({"betriebsart": art})

            # --- Hintergrundlaeufe ----------------------------------
            if weg == "/api/m3_start":
                lauf = laeufe.get("training")
                if lauf is None:
                    return self._json({"ok": False, "grund": "kein Lauf"}, 503)
                # M3-Training laeuft in einer GETRENNTEN Umgebung
                # (~/m3-train-env, numpy 2), weil cnn2snn numpy>=2 braucht,
                # der Server-Kern aber numpy<2. baue_arbeit_extern faellt auf
                # den alten in-process-Weg zurueck, wenn keine da ist.
                from ..train_job import baue_arbeit_extern
                arbeit = baue_arbeit_extern(
                    zustand, verarbeitung,
                    variante=str(koerper.get("variante", "")),
                    schritte=int(koerper.get("schritte", 300)),
                    batch=int(koerper.get("batch", 4)),
                    lr=float(koerper.get("lr", 1e-3)),
                    ausgabe=str(koerper.get("ausgabe", "vorsa_m3.fbz")),
                    mit_varianten=bool(koerper.get("mit_varianten", True)))
                return self._json(lauf.starte(arbeit))

            if weg == "/api/messung_start":
                lauf = laeufe.get("messung")
                if lauf is None:
                    return self._json({"ok": False, "grund": "kein Lauf"}, 503)
                from ..bench import baue_arbeit as bench_arbeit
                arbeit = bench_arbeit(
                    verarbeitung,
                    variante=str(koerper.get("variante", "")),
                    bilder=int(koerper.get("bilder", 30)),
                    watt_pi=float(koerper.get("watt_pi", 7.0)),
                    watt_akd=float(koerper.get("watt_akd", 1.0)))
                return self._json(lauf.starte(arbeit))

            if weg == "/api/kernziel_start":
                lauf = laeufe.get("messung")
                if lauf is None:
                    return self._json({"ok": False, "grund": "kein Lauf"}, 503)
                from ..bench import kernziel_pruefen

                def arbeit(l):
                    l.setze_phase("Kernziel-Pruefung")
                    l.melde("Varianten bauen und auf den AKD1500 mappen")
                    erg = kernziel_pruefen(koerper.get("varianten") or ())
                    for z in erg.get("zeilen", []):
                        marke = ("NICHT-PRUEFBAR" if z.get("blockiert")
                                 else ("PASS" if z.get("ok") else "FAIL"))
                        l.melde(f"{marke:>14}  {z['variante']}"
                                + (f"  {z.get('grund','')}" if z.get("grund") else ""))
                    if not erg.get("aussagekraeftig"):
                        l.melde("Hinweis: es ist nichts durchgefallen. Ein PASS "
                                "bedeutet nur etwas, wenn auch etwas scheitern kann.")
                    return erg

                return self._json(lauf.starte(arbeit))

            if weg == "/api/lauf_abbrechen":
                lauf = laeufe.get(str(koerper.get("name", "")))
                if lauf is None:
                    return self._json({"ok": False, "grund": "kein Lauf"}, 404)
                return self._json(lauf.abbrechen())

            return self._json({"fehler": "unbekannter Endpunkt"}, 404)

    return Handler


# ----------------------------------------------------------------------
# Geraeteliste einmal holen und behalten. akida.devices() ist teuer, und die
# Karten kommen im Betrieb nicht dazu.
_GERAETE = None


def karten_info(lerner=None) -> dict:
    """Status aller Karten: wer arbeitet woran, und was zieht er dabei.

    Die Leistung kommt vom Messwerk der Karte selbst - das ist ein echter
    Messwert, kein Datenblatt. Karte 0 traegt derzeit alles; die uebrigen
    sind ausgewiesene Reserve fuer den Parallelbetrieb nach dem M3-Training.
    """
    global _GERAETE
    try:
        import akida
    except Exception:
        return {"karten": [], "grund": "MetaTF nicht importierbar"}
    try:
        if _GERAETE is None:
            _GERAETE = akida.devices()
    except Exception as exc:
        return {"karten": [], "grund": str(exc)[:90]}
    if not _GERAETE:
        return {"karten": [], "grund": "keine Karte gefunden - Treiber?"}

    # WICHTIG: rechnet der Lerner, dann auf SEINEN Geraetehandles - nur
    # deren Messwerk sieht die Ereignisse. Ein frisch geholtes Handle auf
    # dieselbe Karte meldet ewig nichts; genau so blieb die Anzeige "-".
    quelle = list(getattr(lerner, "geraete", []) or []) or list(_GERAETE)
    # ALLE Karten ins Fenster - auch die, die der Lerner nicht traegt
    # (Detektorkarte, oder eine, deren Laden fehlschlug).
    if len(quelle) < len(_GERAETE):
        quelle = quelle + list(_GERAETE[len(quelle):])
    det_nr = _DETEKTOR.get("karte") if _DETEKTOR.get("aktiv") else None

    aus = []
    for i, g in enumerate(quelle):
        e = {"nr": i, "name": str(getattr(g, "desc", f"Karte {i}")),
             "nps": None, "mw": None, "version": None}
        mesh = getattr(g, "mesh", None)
        if mesh is not None and getattr(mesh, "nps", None) is not None:
            e["nps"] = len(mesh.nps)
        try:
            e["version"] = str(getattr(g, "version", "")) or None
        except Exception:
            pass
        try:
            soc = getattr(g, "soc", None)
            if soc is None:
                # Kein Defekt: laut BrainChip-Doku (MetaTF 2.19.3) wird der
                # Leistungssensor derzeit NUR auf dem AKD1000 unterstuetzt -
                # auf dem AKD1500 ist g.soc None. "Unterstuetzung kommt
                # spaeter." Bis dahin ehrlich "kein Sensor" statt Fehlertext.
                e["mw_text"] = "kein Sensor"
            else:
                if not getattr(soc, "power_measurement_enabled", False):
                    soc.power_measurement_enabled = True
                messer = soc.power_meter
                ereignisse = messer.events()
                if ereignisse:
                    e["mw"] = round(float(np.mean(
                        [x.power for x in ereignisse[-10:]])), 0)
                else:
                    # Ereignisse entstehen erst, wenn die Karte rechnet. Bis
                    # dahin wenigstens den Ruhewert statt eines Strichs.
                    boden = float(getattr(messer, "floor", 0.0))
                    if boden > 0:
                        e["mw_ruhe"] = round(boden, 0)
        except Exception as exc:
            # NICHT verschlucken: "keine Leistungsdaten" ohne Grund hat uns
            # schon einmal raten lassen.
            e["leistung_info"] = str(exc)[:70]
        klassen = list(getattr(lerner, "klassen", []) or [])
        verbund = len(getattr(lerner, "modelle", []) or [])
        if det_nr is not None and i == len(quelle) - 1:
            e["nr"] = det_nr
            e["status"] = "aktiv"
            e["aufgabe"] = ("M3-Detektor: findet Kaesten, Winkel und "
                            "Verdeckungsgrad mehrerer Teile in einem "
                            "Durchgang - auch bei Ueberlappung")
        elif (_DETEKTOR.get("grund") and i == len(quelle) - 1):
            e["status"] = "reserve"
            e["aufgabe"] = ("M3-Detektor NICHT geladen: "
                            + str(_DETEKTOR.get("grund")))
        elif klassen and i < max(verbund, 1):
            e["status"] = "aktiv"
            e["aufgabe"] = (
                f"Silhouetten-Abgleich, Gedaechtnisteil {i + 1} von "
                f"{max(verbund, 1)} - {len(klassen)} Objekte: "
                + ", ".join(klassen[:4]))
        elif i == 0:
            e["status"] = "bereit"
            e["aufgabe"] = "bereit - wartet auf Chip-Lernen"
        else:
            e["status"] = "reserve"
            e["aufgabe"] = ("Reserve - bekommt nach dem M3-Training einen "
                            "eigenen Bildbereich")
        aus.append(e)
    # LIVE-STAND (1.9.36): was die Karte GERADE tut, aus dem Waechter des
    # Lerners bzw. dem Detektorlauf - ueberschreibt den statischen Text.
    try:
        live = lerner.karten_uebersicht() if lerner is not None else {}
    except Exception:
        live = {}
    jetzt = time.time()
    for e in aus:
        st = None
        if det_nr is not None and e["nr"] == det_nr:
            st = _DETEKTOR.get("stand")
        else:
            st = live.get(e["nr"])
        if not st:
            continue
        e["live"] = {k: st.get(k) for k in ("status", "aufgabe", "letzte_ms",
                                            "aufrufe", "aufrufe_s", "fehler",
                                            "grund", "gestoert_seit")}
        lz = st.get("letzte_zeit") or 0
        e["live"]["vor_s"] = round(jetzt - lz, 1) if lz else None
        if st.get("status") == "gestoert":
            e["status"] = "gestoert"
            seit = st.get("gestoert_seit") or 0
            e["aufgabe"] = ("GESTOERT seit " + time.strftime("%H:%M:%S", time.localtime(seit))
                            + " - " + str(st.get("grund") or "")[:80]
                            + " - aus dem Verbund genommen, naechster Versuch "
                            "automatisch")
        elif st.get("aufgabe"):
            teile = [str(st["aufgabe"])]
            if st.get("letzte_ms") is not None:
                teile.append(f"{st['letzte_ms']} ms")
            if e["live"]["vor_s"] is not None:
                teile.append(f"vor {e['live']['vor_s']} s")
            if st.get("aufrufe_s"):
                teile.append(f"{st['aufrufe_s']:.1f}/s")
            e["live_text"] = " · ".join(teile)
    ergebnis = {"karten": aus, "detektor": dict(_DETEKTOR)}
    if aus and all(x.get("mw") is None for x in aus) and any(
            x.get("mw_text") for x in aus):
        ergebnis["leistung_hinweis"] = (
            "Der AKD1500 traegt noch keinen auslesbaren Leistungssensor - "
            "BrainChip unterstuetzt die Messung derzeit nur auf dem AKD1000 "
            "(MetaTF 2.19.3). Typischer Bedarf laut Messungen der Community: "
            "unter 1 W je Karte.")
    return ergebnis


def hardware_info() -> dict:
    """Was steckt drin? Fuer die Diagnoseanzeige."""
    info = {"akida": False, "geraet": None, "nps": None,
            "tensorflow": False, "cnn2snn": False, "build": BUILD}
    try:
        import akida
        info["akida"] = getattr(akida, "__version__", True)
        d = akida.devices()
        if d:
            info["geraet"] = str(getattr(d[0], "desc", "?"))
            # ALLE Karten ausweisen. Gelernt und erkannt wird derzeit auf
            # Karte 0; die uebrigen sind der Ausbau fuer parallele Streams
            # nach dem M3-Training (akida_pool liegt dafuer schon bereit).
            info["karten"] = len(d)
            nps = 0
            for g in d:
                mesh = getattr(g, "mesh", None)
                if mesh is not None and getattr(mesh, "nps", None) is not None:
                    nps += len(mesh.nps)
            info["nps"] = nps or None
    except Exception as exc:
        info["akida_fehler"] = str(exc)[:120]
    for name in ("tensorflow", "cnn2snn"):
        try:
            m = __import__(name)
            info[name] = getattr(m, "__version__", True)
        except Exception:
            pass
    return info


def starte(port: int = 8080, kamera: int = 0, groesse: int = 512,
           synthetisch: bool = False, daten: str = "vorsa_daten",
           mit_erkennung: bool = True, mit_lernen: bool = True,
           protokoll: bool = False, anzeige: int = 960) -> None:
    zustand = Zustand(daten)
    zustand.hardware = hardware_info()

    # Pi-Kameramodul zuerst, USB als Rueckfall. Das Modul 3 haengt an
    # libcamera - cv2.VideoCapture sieht es nicht.
    quelle = None
    if not synthetisch:
        try:
            quelle = PiBildquelle(groesse)
        except Exception as exc:
            # VOLLE Meldung. Die auf 60 Zeichen gekappte hat uns eine Runde
            # gekostet, weil der Modulname hinten abgeschnitten war.
            print(f"  Pi-Kameramodul nicht nutzbar - versuche USB-Kamera.\n"
                  f"    Grund: {exc}", flush=True)
    if quelle is None:
        quelle = Bildquelle(kamera, groesse, synthetisch)
    if quelle.hinweis:
        zustand.hinweise.append(quelle.hinweis)
    if quelle.synthetisch:
        zustand.hinweise.append(
            "Synthetische Bildquelle - keine echte Kamera")
    zustand.hinweise.append(
        "Erkennung laeuft geometrisch (OpenCV), SE-M3 ist noch nicht trainiert")

    lerner = None
    if mit_lernen:
        lerner = EdgeLerner(groesse=128)
        # Einmal beim Start fragen, danach nur noch den gemerkten Stand nutzen.
        da, info = lerner.verfuegbar()
        zustand.hinweise.append(
            f"Chip-Lernen bereit: {info}" if da
            else f"Chip-Lernen nicht moeglich: {info}")
    else:
        zustand.hinweise.append("Chip-Lernen abgeschaltet (--ohne-lernen)")

    # STUFE 2: liegt ein trainiertes vorsa_m3.fbz vor, bekommt der Detektor
    # die letzte Karte - der Silhouetten-Verbund arbeitet dann auf dreien.
    # Das MUSS vor dem Wiederherstellen entschieden sein, sonst belegt der
    # Verbund alle vier und der Detektor haette keinen Platz.
    detektor_pfad = None
    for kandidat in (Path("vorsa_m3.fbz"), Path(daten) / "vorsa_m3.fbz"):
        if kandidat.exists():
            detektor_pfad = str(kandidat)
            break
    if detektor_pfad and lerner is not None:
        lerner.karten_max = 3
    if not detektor_pfad:
        _DETEKTOR.update({"aktiv": False, "grund": (
            "vorsa_m3.fbz nicht gefunden - im Startverzeichnis des Servers "
            "ablegen")})

    verarbeitung = Verarbeitung(quelle, zustand, mit_erkennung,
                                anzeige_groesse=anzeige, lerner=lerner)
    if detektor_pfad:
        threading.Thread(target=verarbeitung.detektor_laden,
                         args=(detektor_pfad,), daemon=True).start()

    # Zwei Hintergrundlaeufe, je einer gleichzeitig: das lange M3-Training
    # und die Messreihe. Beide wuerden in einer HTTP-Anfrage in eine
    # Zeitueberschreitung laufen und die Oberflaeche haengend aussehen lassen.
    from ..jobs import Lauf
    laeufe = {"training": Lauf("M3-Training"), "messung": Lauf("Messung"),
              "chip": Lauf("Chip-Lernen")}

    # Gelerntes wiederherstellen - im Hintergrund, damit der Server sofort
    # antwortet. Sonst haengt die Seite beim Start ohne erkennbaren Grund.
    if lerner is not None:
        threading.Thread(target=lernen_beim_start, args=(zustand, lerner),
                         daemon=True).start()

    handler = baue_handler(verarbeitung, zustand, laeufe, protokoll=protokoll)

    try:
        server = ThreadingHTTPServer(("0.0.0.0", port), handler)
    except OSError as exc:
        verarbeitung.stoppe()
        if getattr(exc, "errno", None) == 98:      # Address already in use
            print(f"\nPort {port} ist belegt - vermutlich laeuft noch ein")
            print("aelterer Server. Das ist die haeufigste Ursache dafuer, dass")
            print("im Browser weiter der alte Zustand erscheint, obwohl hier")
            print("neu gestartet wurde.\n")
            print("  pkill -f run_web.py     # alten Server beenden")
            print(f"  python3 tools/run_web.py    # neu starten")
            print(f"\noder anderen Port waehlen:  --port {port + 1}")
            return
        raise

    # flush=True ueberall: ohne das liegen die Zeilen im Puffer, sobald die
    # Ausgabe in eine Datei geht - und dann fehlt beim Suchen genau das,
    # was man beim Start wissen muss.
    # Lernstand-Zeile: der Kartenverbund sichert als chip_modell_k0..k3.fbz,
    # nicht als chip_modell.fbz - die alte Pruefung meldete deshalb "noch
    # keiner", obwohl eine Zeile darueber zurueckgespielt wurde. Jetzt wird
    # auch der Verfahrens-Stempel angezeigt (muss LERNSTAND erreichen, sonst
    # lernt der Start neu).
    fbz = Path(daten) / EdgeLerner.DATEI
    kart0 = Path(daten) / f"chip_modell_k0.fbz"
    stempel = "?"
    try:
        import json as _json
        beg = _json.loads((Path(daten) / EdgeLerner.BEGLEIT)
                          .read_text(encoding="utf-8"))
        stempel = f"Verfahren {beg.get('lernstand', 1)}/{EdgeLerner.LERNSTAND}"
    except Exception:
        stempel = "keine Begleitdatei"
    lern_txt = ("vorhanden" if fbz.exists() or kart0.exists()
                else "noch keiner")
    for zeile in (
        f"SE Inspect (frueher VORSA INSPECT) auf  http://0.0.0.0:{port}",
        f"  BUILD:      {BUILD}   <- muss unten rechts in der Oberflaeche stehen",
        f"  Bildquelle: {'synthetisch' if quelle.synthetisch else f'Kamera {kamera}'}",
        f"  Anzeige:    {anzeige} px",
        f"  Daten:      {Path(daten).resolve()}",
        f"  Lernstand:  {lern_txt}  ({stempel})",
        f"  Hardware:   {zustand.hardware}",
        "  Beenden mit Strg+C",
    ):
        print(zeile, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nbeendet")
    finally:
        verarbeitung.stoppe()
        server.server_close()
