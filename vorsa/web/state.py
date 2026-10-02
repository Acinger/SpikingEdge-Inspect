"""Zustand der Weboberflaeche: Klassen, Prototypen, Messwerte.

Alles wird auf Platte gespiegelt. Ein Neustart des Servers - oder ein
Stromausfall an der Anlage - darf keine aufgenommenen Prototypen kosten.
"""
from __future__ import annotations

import json
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Deque, Dict, List, Optional

import cv2
import numpy as np

from ..augment import AugmentConfig, erzeuge_varianten
from ..assignment import GtObject


@dataclass
class Bereich:
    """Der Bildausschnitt, den der Chip sieht und der aufgenommen wird.

    Der AKD1500 bekommt ein quadratisches Bild fester Groesse (256 x 256).
    Fuellt das Objekt nur ein Zehntel des Kamerabildes, geht der groesste Teil
    dieser Aufloesung fuer Hintergrund drauf. Ein enger Ausschnitt bringt das
    Objekt formatfuellend in dieselben 256 Pixel - das ist echter Gewinn an
    Detail, nicht nur Vergroesserung.

    `fenster` ist die Kantenlaenge in Prozent des groessten moeglichen
    Quadrats. 100 % = ganzes Bild (kurze Seite), 25 % = ein Viertel davon.

    Bewusst so herum und nicht als Zoomfaktor: die Zahl beschreibt direkt,
    was zu sehen ist. Ein Zoomwert muesste erst im Kopf umgerechnet werden,
    und zwar gegenlaeufig - grosser Zoom, kleines Fenster.

    cx/cy Mittelpunkt des Ausschnitts, 0..1 im Bild
    """

    fenster: float = 100.0
    cx: float = 0.5
    cy: float = 0.5

    MIN_PROZENT = 10.0

    def rechteck(self, breite: int, hoehe: int, modell_px: int = 256):
        """(x, y, seite, hinweis) des quadratischen Ausschnitts."""
        gross = min(breite, hoehe)
        f = max(self.MIN_PROZENT, min(100.0, self.fenster)) / 100.0
        seite = max(32, int(round(gross * f)))

        x = int(round(self.cx * breite - seite / 2))
        y = int(round(self.cy * hoehe - seite / 2))
        x = max(0, min(breite - seite, x))
        y = max(0, min(hoehe - seite, y))

        # Ehrlichkeitshinweis: unter der Modellgroesse wird das Bild beim
        # Skalieren aufgeblasen. Der Ausschnitt wird dann zwar formatfuellend,
        # gewinnt aber keine Bildinformation mehr hinzu - er vergroessert nur
        # vorhandene Pixel.
        hinweis = ""
        if seite < modell_px:
            hinweis = (f"Ausschnitt {seite} px ist kleiner als die Modellgroesse "
                       f"{modell_px} px - wird hochskaliert, ohne Detail zu gewinnen")
        return x, y, seite, hinweis

    def as_dict(self) -> dict:
        return {"fenster": round(self.fenster, 1), "cx": round(self.cx, 3),
                "cy": round(self.cy, 3)}

    @staticmethod
    def aus_dict(d: dict) -> "Bereich":
        """Liest auch aeltere Dateien, die noch `zoom` enthalten.

        Die alte Skala war gegenlaeufig und ging bis 15 % Restgroesse:
        Fenster = 100 - 85 * zoom/100. Ohne diese Umrechnung waere eine
        gespeicherte Einstellung nach dem Umbau stillschweigend eine andere.
        """
        if "fenster" in d:
            return Bereich(fenster=float(d.get("fenster", 100.0)),
                           cx=float(d.get("cx", 0.5)), cy=float(d.get("cy", 0.5)))
        z = float(d.get("zoom", 0.0))
        return Bereich(fenster=max(Bereich.MIN_PROZENT, 100.0 - 0.85 * z),
                       cx=float(d.get("cx", 0.5)), cy=float(d.get("cy", 0.5)))


@dataclass
class Anzeige:
    """Was ins Livebild gezeichnet wird.

    Einzeln schaltbar, weil dieselben Daten unterschiedlich dicht gebraucht
    werden. Bei sechs Teilen verdecken Beschriftungen mehr, als sie erklaeren;
    wer dagegen die Trennung zweier beruehrender Teile beurteilen will,
    braucht die Konturen ohne alles andere.
    """

    aufnahmerahmen: bool = True
    abdunkeln: bool = True
    objektrahmen: bool = True
    konturen: bool = True
    laengsachse: bool = True
    beschriftung: bool = False
    legende: bool = False

    def as_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def aus_dict(d: dict) -> "Anzeige":
        gueltig = {f: bool(d[f]) for f in Anzeige().__dict__ if f in d}
        return Anzeige(**gueltig)


# Drei Voreinstellungen, damit man nicht sieben Schalter bedient.
ANZEIGE_VORLAGEN: Dict[str, dict] = {
    "sauber":   dict(aufnahmerahmen=True, abdunkeln=False, objektrahmen=False,
                     konturen=False, laengsachse=False, beschriftung=False,
                     legende=False),
    "arbeiten": dict(aufnahmerahmen=True, abdunkeln=True, objektrahmen=True,
                     konturen=True, laengsachse=True, beschriftung=False,
                     legende=False),
    "pruefen":  dict(aufnahmerahmen=True, abdunkeln=True, objektrahmen=True,
                     konturen=True, laengsachse=True, beschriftung=True,
                     legende=True),
}


@dataclass
class Klasse:
    id: int
    name: str
    augment: AugmentConfig = field(default_factory=AugmentConfig)
    prototypen: List[str] = field(default_factory=list)   # Dateinamen
    # Negativklasse: leeres Band, Unterlage, Stoerteil. Ohne sie muss der
    # Chip sich immer fuer eines der echten Objekte entscheiden - auch wenn
    # gar nichts da ist. Das sieht dann nach einem Erkennungsfehler aus, ist
    # aber ein Fehler in der Aufgabenstellung.
    negativ: bool = False

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "negativ": self.negativ,
            "augment": asdict(self.augment),
            "varianten_je_aufnahme": self.augment.anzahl_varianten(),
            "prototypen": len(self.prototypen),
            "gesamt_mit_augmentierung": (
                len(self.prototypen) * self.augment.anzahl_varianten()),
        }


class Messwerte:
    """Gleitende Messung von Bildrate und Latenz."""

    def __init__(self, fenster: int = 60):
        self.zeiten: Deque[float] = deque(maxlen=fenster)
        self.latenzen: Deque[float] = deque(maxlen=fenster)
        self.objekte: Deque[int] = deque(maxlen=fenster)
        self._lock = threading.Lock()

    def melde(self, latenz_ms: float, n_objekte: int) -> None:
        with self._lock:
            self.zeiten.append(time.perf_counter())
            self.latenzen.append(latenz_ms)
            self.objekte.append(n_objekte)

    def as_dict(self) -> dict:
        with self._lock:
            if len(self.zeiten) < 2:
                return {"fps": 0.0, "latenz_ms": 0.0, "objekte_mittel": 0.0,
                        "bilder": len(self.zeiten)}
            dauer = self.zeiten[-1] - self.zeiten[0]
            fps = (len(self.zeiten) - 1) / dauer if dauer > 0 else 0.0
            return {
                "fps": round(fps, 1),
                "latenz_ms": round(float(np.mean(self.latenzen)), 1),
                "latenz_max_ms": round(float(np.max(self.latenzen)), 1),
                "objekte_mittel": round(float(np.mean(self.objekte)), 1),
                "bilder": len(self.zeiten),
            }


class Zustand:
    """Gemeinsamer Zustand aller Anfragen."""

    def __init__(self, datenordner: str = "vorsa_daten"):
        self.ordner = Path(datenordner)
        self.bilder_ordner = self.ordner / "prototypen"
        self.bilder_ordner.mkdir(parents=True, exist_ok=True)
        self.ereignis_ordner = self.ordner / "ereignisse"
        self.ereignis_ordner.mkdir(parents=True, exist_ok=True)
        self.konfig_datei = self.ordner / "klassen.json"

        self.klassen: Dict[int, Klasse] = {}
        self.messwerte = Messwerte()
        self.letzte_detektionen: List[dict] = []
        self.hardware: dict = {}
        # einrichten | anlernen | betreiben | messen
        #
        # Immer in der Erkennung starten. Das ist der Zustand, in dem die
        # Anlage laeuft; Einrichten und Lernen sind Ausnahmen, die man
        # bewusst aufsucht. Nach einem Stromausfall soll die Maschine
        # weiterarbeiten und nicht in einem Einrichtbild stehenbleiben.
        self.betriebsart = "betreiben"
        self.anzeige = Anzeige()
        # Kameraeinstellung zum Zeitpunkt des Trainings. Weicht die aktuelle
        # davon ab, hat das Modell etwas anderes gelernt, als es jetzt sieht.
        self.kamera_referenz: dict = {}
        self.ereignisse: List[dict] = []
        self.zaehler: Dict[str, int] = {}
        self.hinweise: List[str] = []
        self.bereich = Bereich()
        self.bereich_info: dict = {}
        self.erkannt = None    # letzte Klassifikation des Chips
        # Presets halten Kameraeinstellungen UND Ausschnitt zusammen. Getrennt
        # gespeichert waeren sie wertlos: eine Belichtung ohne den zugehoerigen
        # Bildausschnitt ergibt nicht dasselbe Bild.
        self.presets: Dict[str, dict] = {}
        self._lock = threading.Lock()

        self._laden()

    # ------------------------------------------------------------------
    def _laden(self) -> None:
        if not self.konfig_datei.exists():
            for i, name in enumerate(("Objekt A", "Objekt B")):
                self.klassen[i] = Klasse(id=i, name=name)
            self._speichern()
            return
        try:
            d = json.loads(self.konfig_datei.read_text(encoding="utf-8"))
            for k in d.get("klassen", []):
                self.klassen[int(k["id"])] = Klasse(
                    id=int(k["id"]), name=k["name"],
                    augment=AugmentConfig(**k.get("augment", {})),
                    prototypen=list(k.get("prototypen", [])),
                    negativ=bool(k.get("negativ", False)),
                )
            if "bereich" in d:
                self.bereich = Bereich.aus_dict(d["bereich"])
            if "anzeige" in d:
                self.anzeige = Anzeige.aus_dict(d["anzeige"])
            self.presets = dict(d.get("presets", {}))
            self.kamera_referenz = dict(d.get("kamera_referenz", {}))
            self.zaehler = dict(d.get("zaehler", {}))
        except Exception as exc:
            self.hinweise.append(f"Klassendatei nicht lesbar: {exc}")
            self.klassen[0] = Klasse(id=0, name="Objekt A")

    def _speichern(self) -> None:
        d = {
            "klassen": [
                {"id": k.id, "name": k.name, "augment": asdict(k.augment),
                 "prototypen": k.prototypen, "negativ": k.negativ}
                for k in self.klassen.values()
            ],
            "bereich": self.bereich.as_dict(),
            "anzeige": self.anzeige.as_dict(),
            "presets": self.presets,
            "kamera_referenz": self.kamera_referenz,
            "zaehler": self.zaehler,
        }
        self.konfig_datei.write_text(
            json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

    # ------------------------------------------------------------------
    def bereich_setzen(self, fenster=None, cx=None, cy=None) -> Bereich:
        with self._lock:
            if fenster is not None:
                self.bereich.fenster = max(
                    Bereich.MIN_PROZENT, min(100.0, float(fenster)))
            if cx is not None:
                self.bereich.cx = max(0.0, min(1.0, float(cx)))
            if cy is not None:
                self.bereich.cy = max(0.0, min(1.0, float(cy)))
            self._speichern()
            return self.bereich

    def preset_speichern(self, name: str, kamera: dict) -> dict:
        with self._lock:
            name = (name or "").strip() or f"Einstellung {len(self.presets)+1}"
            self.presets[name] = {
                "kamera": kamera,
                "bereich": self.bereich.as_dict(),
                "gespeichert": time.strftime("%Y-%m-%d %H:%M"),
            }
            self._speichern()
            return {name: self.presets[name]}

    def preset_loeschen(self, name: str) -> bool:
        with self._lock:
            if name not in self.presets:
                return False
            del self.presets[name]
            self._speichern()
            return True

    # ------------------------------------------------------------------
    def anzeige_setzen(self, felder: dict = None, vorlage: str = "") -> Anzeige:
        with self._lock:
            if vorlage:
                if vorlage not in ANZEIGE_VORLAGEN:
                    raise KeyError(vorlage)
                self.anzeige = Anzeige(**ANZEIGE_VORLAGEN[vorlage])
            if felder:
                jetzt = self.anzeige.as_dict()
                jetzt.update({f: bool(v) for f, v in felder.items() if f in jetzt})
                self.anzeige = Anzeige(**jetzt)
            self._speichern()
            return self.anzeige

    # ------------------------------------------------------------------
    def referenz_setzen(self, kamera: dict) -> dict:
        """Haelt die Kameraeinstellung fest, mit der trainiert wurde."""
        with self._lock:
            self.kamera_referenz = {
                "werte": dict(kamera or {}),
                "bereich": self.bereich.as_dict(),
                "zeit": time.strftime("%Y-%m-%d %H:%M"),
            }
            self._speichern()
            return self.kamera_referenz

    # Unterhalb dieser relativen Abweichung gilt ein Wert als unveraendert.
    # Kameras liefern beim Zuruecklesen leicht schwankende Zahlen; jede
    # Schwankung als Drift zu melden waere so nutzlos wie gar keine Meldung.
    DRIFT_SCHWELLE = 0.08

    def drift(self, jetzt: dict) -> List[dict]:
        """Was hat sich seit dem Training an der Kamera geaendert?

        Ohne diese Pruefung sucht man den Fehler im Modell, waehrend er in
        der Kamera sitzt - der bequemste Weg, ein funktionierendes System
        fuer kaputt zu halten.
        """
        ref = (self.kamera_referenz or {}).get("werte") or {}
        if not ref or not jetzt:
            return []
        aus = []
        for name, alt in ref.items():
            if name not in jetzt:
                continue
            neu = jetzt[name]
            bezug = max(abs(float(alt)), 1.0)
            if abs(float(neu) - float(alt)) / bezug > self.DRIFT_SCHWELLE:
                aus.append({"name": name, "beim_training": round(float(alt), 3),
                            "jetzt": round(float(neu), 3)})

        ref_b = (self.kamera_referenz or {}).get("bereich") or {}
        if ref_b.get("fenster") is not None:
            if abs(float(ref_b["fenster"]) - self.bereich.fenster) > 2.0:
                aus.append({"name": "fenster",
                            "beim_training": ref_b["fenster"],
                            "jetzt": round(self.bereich.fenster, 1)})
        return aus

    # ------------------------------------------------------------------
    MAX_EREIGNISSE = 200

    def ereignis_ablegen(self, bild, grund: str, daten: dict = None) -> dict:
        """Legt einen unklaren Fall mit Bild ab.

        Das ist das Material fuer die naechste Trainingsrunde: die Anlage
        sammelt selbst genau die Faelle, an denen sie scheitert.
        """
        name = f"e{int(time.time()*1000)}.jpg"
        try:
            cv2.imwrite(str(self.ereignis_ordner / name), bild,
                        [cv2.IMWRITE_JPEG_QUALITY, 80])
        except Exception as exc:
            return {"ok": False, "grund": str(exc)[:80]}
        eintrag = {"datei": name, "grund": grund,
                   "zeit": time.strftime("%Y-%m-%d %H:%M:%S"),
                   **(daten or {})}
        with self._lock:
            self.ereignisse.append(eintrag)
            while len(self.ereignisse) > self.MAX_EREIGNISSE:
                alt = self.ereignisse.pop(0)
                (self.ereignis_ordner / alt["datei"]).unlink(missing_ok=True)
        return {"ok": True, **eintrag}

    def ereignis_bild(self, datei: str):
        pfad = self.ereignis_ordner / datei
        if not pfad.resolve().is_relative_to(self.ereignis_ordner.resolve()):
            return None
        return cv2.imread(str(pfad)) if pfad.exists() else None

    def ereignisse_leeren(self) -> int:
        with self._lock:
            n = len(self.ereignisse)
            for e in self.ereignisse:
                (self.ereignis_ordner / e["datei"]).unlink(missing_ok=True)
            self.ereignisse = []
        return n

    # ------------------------------------------------------------------
    def zaehle(self, namen: List[str]) -> None:
        with self._lock:
            for n in namen:
                self.zaehler[n] = self.zaehler.get(n, 0) + 1

    def zaehler_zuruecksetzen(self) -> None:
        with self._lock:
            self.zaehler = {}
            self._speichern()

    # ------------------------------------------------------------------
    def fingerabdruck(self) -> str:
        """Kennzeichen des Fotobestands.

        Aendert sich auch nur ein Foto oder eine Variantenwahl, aendert sich
        dieser Wert - und ein gesicherter Lernstand gilt als ueberholt. Ohne
        diese Pruefung koennte die Karte nach dem Neustart auf Grundlage von
        Bildern antworten, die es nicht mehr gibt.
        """
        import hashlib
        teile = []
        for k in sorted(self.klassen.values(), key=lambda x: x.id):
            teile.append(f"{k.id}|{k.name}|{k.negativ}|"
                         + ",".join(sorted(k.prototypen)) + "|"
                         + repr(sorted(asdict(k.augment).items())))
        return hashlib.sha1("\n".join(teile).encode("utf-8")).hexdigest()[:16]

    def fortschritt(self, gelernt: bool = False) -> dict:
        """Die drei Schritte des ersten Starts."""
        mit_fotos = [k for k in self.klassen.values() if k.prototypen]
        echte = [k for k in mit_fotos if not k.negativ]
        return {
            "eingerichtet": bool(self.presets) or self.bereich.fenster < 100.0,
            "angelernt": len(echte) >= 2,
            "betriebsbereit": bool(gelernt),
        }

    # ------------------------------------------------------------------
    def klasse_anlegen(self, name: str, negativ: bool = False) -> Klasse:
        with self._lock:
            neue_id = max(self.klassen) + 1 if self.klassen else 0
            k = Klasse(id=neue_id, name=name or f"Objekt {neue_id}",
                       negativ=bool(negativ))
            self.klassen[neue_id] = k
            self._speichern()
            return k

    def klasse_aendern(self, kid: int, name: Optional[str] = None,
                       augment: Optional[dict] = None,
                       negativ: Optional[bool] = None) -> Optional[Klasse]:
        with self._lock:
            k = self.klassen.get(kid)
            if k is None:
                return None
            if name:
                k.name = name
            if negativ is not None:
                k.negativ = bool(negativ)
            if augment:
                gueltig = {f: augment[f] for f in AugmentConfig().__dict__
                           if f in augment}
                k.augment = AugmentConfig(**{**asdict(k.augment), **gueltig})
            self._speichern()
            return k

    def klasse_loeschen(self, kid: int) -> bool:
        with self._lock:
            if kid not in self.klassen:
                return False
            for datei in self.klassen[kid].prototypen:
                try:
                    (self.bilder_ordner / datei).unlink(missing_ok=True)
                except Exception:
                    pass
            del self.klassen[kid]
            self._speichern()
            return True

    # ------------------------------------------------------------------
    # Schaerfe: Varianz des Laplace-Filters. Unter diesem Wert ist auf einem
    # 256-px-Ausschnitt keine Kante mehr sicher zu erkennen - und Kanten sind
    # alles, woraus die Kontur entsteht.
    SCHAERFE_MIN = 25.0
    FLAECHE_MIN = 0.02          # Teil zu klein im Rahmen
    FLAECHE_MAX = 0.85          # Teil fuellt den Rahmen, Kanten fehlen

    def foto_pruefen(self, bild: np.ndarray, negativ: bool = False) -> dict:
        """Taugt dieses Foto zum Anlernen?

        Beim Speichern geprueft, nicht erst beim Training. Ein unbrauchbares
        Foto faellt sonst erst Stunden spaeter auf - und bis dahin liegen
        neun weitere daneben, die denselben Fehler haben.
        """
        from ..dataset_build import freistellen

        grau = cv2.cvtColor(bild, cv2.COLOR_BGR2GRAY)
        schaerfe = float(cv2.Laplacian(grau, cv2.CV_64F).var())
        hell = float(grau.mean())
        ueber = float((grau >= 250).mean())

        maengel: List[str] = []
        if schaerfe < self.SCHAERFE_MIN:
            maengel.append("unscharf")
        if ueber > 0.08:
            maengel.append("ueberstrahlt")
        if hell < 25:
            maengel.append("zu dunkel")

        anteil = 0.0
        if not negativ:
            t = freistellen(bild, 0)
            if t is None:
                maengel.append("kein Teil vom Hintergrund trennbar")
            else:
                # Flaeche des umschliessenden Rechtecks am ganzen Rahmen.
                anteil = float((t.laenge * t.breite) / max(grau.size, 1))
                if anteil < self.FLAECHE_MIN:
                    maengel.append("Teil zu klein im Rahmen")
                elif anteil > self.FLAECHE_MAX:
                    maengel.append("Teil fuellt den Rahmen ganz aus")

        return {"ok": not maengel, "schaerfe": round(schaerfe, 1),
                "helligkeit": round(hell, 1),
                "ueberstrahlt": round(ueber * 100, 1),
                "flaechenanteil": round(anteil * 100, 1),
                "maengel": maengel}

    def prototyp_speichern(self, kid: int, bild: np.ndarray) -> Optional[str]:
        with self._lock:
            k = self.klassen.get(kid)
            if k is None:
                return None
            name = f"k{kid}_{int(time.time()*1000)}.jpg"
            cv2.imwrite(str(self.bilder_ordner / name), bild,
                        [cv2.IMWRITE_JPEG_QUALITY, 92])
            k.prototypen.append(name)
            self._speichern()
            return name

    def prototyp_loeschen(self, kid: int, datei: str) -> bool:
        with self._lock:
            k = self.klassen.get(kid)
            if k is None or datei not in k.prototypen:
                return False
            k.prototypen.remove(datei)
            (self.bilder_ordner / datei).unlink(missing_ok=True)
            self._speichern()
            return True

    def prototyp_bild(self, datei: str) -> Optional[np.ndarray]:
        pfad = self.bilder_ordner / datei
        # Kein Verzeichniswechsel ueber praeparierte Namen.
        if not pfad.resolve().is_relative_to(self.bilder_ordner.resolve()):
            return None
        if not pfad.exists():
            return None
        return cv2.imread(str(pfad))

    # ------------------------------------------------------------------
    def varianten_vorschau(self, kid: int, datei: str,
                           max_bilder: int = 8) -> List[dict]:
        """Erzeugt die Augmentierungsvarianten einer Aufnahme als Vorschau."""
        k = self.klassen.get(kid)
        bild = self.prototyp_bild(datei)
        if k is None or bild is None:
            return []

        h, w = bild.shape[:2]
        platzhalter = [GtObject(cx=w / 2, cy=h / 2, width=w * 0.6,
                                height=h * 0.3, angle=30.0, class_id=kid)]
        aus = []
        for name, b, objs in erzeuge_varianten(bild, platzhalter, k.augment)[:max_bilder]:
            ok, buf = cv2.imencode(".jpg", b, [cv2.IMWRITE_JPEG_QUALITY, 75])
            if not ok:
                continue
            aus.append({
                "name": name,
                "winkel": round(objs[0].angle, 1) if objs else None,
                "jpeg": buf.tobytes(),
            })
        return aus

    # ------------------------------------------------------------------
    def datensatz_uebersicht(self) -> dict:
        aufnahmen = sum(len(k.prototypen) for k in self.klassen.values())
        gesamt = sum(len(k.prototypen) * k.augment.anzahl_varianten()
                     for k in self.klassen.values())
        gesperrt = [k.name for k in self.klassen.values() if k.augment.haendigkeit]
        return {
            "klassen": len(self.klassen),
            "aufnahmen": aufnahmen,
            "mit_augmentierung": gesamt,
            "faktor": round(gesamt / aufnahmen, 1) if aufnahmen else 0,
            "spiegeln_gesperrt": gesperrt,
        }

    # ------------------------------------------------------------------
    MS_JE_BEISPIEL = 2.0        # gemessen am 2026-08-26 auf dem AKD1500
    FOTOS_EMPFOHLEN = 5

    def trainingsplan(self) -> dict:
        """Was ginge jetzt an den Chip - vor dem Klick, nicht danach.

        Ein Trainingsknopf, der still etwas verwirft und etwas anderes
        aufnimmt, ist der Grund, warum niemand weiss, was das Modell
        gelernt hat.
        """
        zeilen, warnungen = [], []
        beispiele = 0
        for k in sorted(self.klassen.values(), key=lambda x: x.id):
            n = len(k.prototypen)
            v = k.augment.anzahl_varianten()
            zeilen.append({"id": k.id, "name": k.name, "negativ": k.negativ,
                           "fotos": n, "varianten": v, "gesamt": n * v})
            beispiele += n * v
            if n == 0:
                warnungen.append(f"„{k.name}“ hat noch keine Fotos.")
            elif n < self.FOTOS_EMPFOHLEN:
                warnungen.append(
                    f"„{k.name}“ hat nur {n} "
                    f"{'Foto' if n == 1 else 'Fotos'} - gemessen waren "
                    f"{self.FOTOS_EMPFOHLEN} noetig.")
            if k.negativ and k.augment.haendigkeit:
                warnungen.append(
                    f"„{k.name}“ ist Negativklasse und zugleich haendig "
                    "gesperrt - das schraenkt ohne Nutzen ein.")

        mit_fotos = [z for z in zeilen if z["fotos"]]
        echte = [z for z in mit_fotos if not z["negativ"]]
        bereit = len(echte) >= 2
        if not bereit:
            warnungen.insert(0, "Mindestens zwei echte Objekte mit Fotos "
                                "noetig - mit einem gibt es nichts zu "
                                "unterscheiden.")
        if mit_fotos and not any(z["negativ"] for z in mit_fotos):
            warnungen.append(
                "Keine Negativklasse angelegt. Der Chip muss sich dann auch "
                "bei leerem Band fuer ein Objekt entscheiden.")

        return {
            "zeilen": zeilen,
            "objekte": len(mit_fotos),
            "fotos": sum(z["fotos"] for z in zeilen),
            "beispiele": beispiele,
            "sekunden_chip": round(beispiele * self.MS_JE_BEISPIEL / 1000.0, 2),
            "bereit": bereit,
            "warnungen": warnungen,
        }

    def as_dict(self) -> dict:
        return {
            "betriebsart": self.betriebsart,
            "klassen": [k.as_dict() for k in self.klassen.values()],
            "messwerte": self.messwerte.as_dict(),
            "detektionen": self.letzte_detektionen,
            "hardware": self.hardware,
            "datensatz": self.datensatz_uebersicht(),
            "hinweise": self.hinweise[-5:],
            "bereich": {**self.bereich.as_dict(), **self.bereich_info},
            "anzeige": self.anzeige.as_dict(),
            "presets": {n: {"gespeichert": p.get("gespeichert", ""),
                            "fenster": (p.get("bereich") or {}).get("fenster")}
                        for n, p in self.presets.items()},
            "trainingsplan": self.trainingsplan(),
            "kamera_referenz": {
                "zeit": (self.kamera_referenz or {}).get("zeit", ""),
                # Der Ausschnitt beim Anlernen. Weicht er ab, sieht der Chip
                # ein anders beschnittenes Bild als das, was er gelernt hat -
                # deshalb muss er wiederherstellbar sein, nicht nur meldbar.
                "fenster": ((self.kamera_referenz or {}).get("bereich") or {}).get("fenster"),
            },
            "zaehler": dict(self.zaehler),
            "ereignisse": len(self.ereignisse),
        }
