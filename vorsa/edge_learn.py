"""Prototypen-Lernen direkt auf dem AKD1500.

Das ist NICHT das Training von VORSA-M3. Der Detektor mit Boxen, Winkeln und
Verdeckungsgraden lernt per Rueckpropagierung auf einem PC. Hier lernt nur die
letzte vollverbundene Schicht - auf der Hardware, aus wenigen Beispielen.

    Merkmalsextraktor   fest         erzeugt Bildmerkmale
    Lernschicht         lernt        ordnet Merkmale einer Klasse zu

Gemessen am 2026-08-26: 2 ms je Beispiel, 5 Aufnahmen je Klasse genuegten,
bestes num_weights etwa ein Viertel der aktiven Merkmale.

Ehrliche Einschraenkung: der Merkmalsextraktor ist derzeit untrainiert. Er
liefert brauchbare, aber grobe Merkmale - unterschieden werden vor allem
Flaeche, Helligkeit und grobe Form. Zwei aehnlich grosse, aehnlich helle
Objekte werden verwechselt. Das ist keine Fehlfunktion des Lernens, sondern
die Grenze der Merkmale. Mit trainiertem Rumpf verschwindet diese Art Fehler.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

try:
    import akida
    AKIDA_DA = True
except Exception:                      # pragma: no cover
    akida = None
    AKIDA_DA = False
# CPU-ERSATZ (SE Inspect A8, 1.9.44): ohne MetaTF und nur auf Wunsch
# (VORSA_CPU_LERNEN=1, beim synthetischen Start automatisch) rechnet der
# Silhouetten-Abgleich in numpy. Gleiche Zahlen wie auf dem Chip, keine
# Aussage ueber Hardware - die Oberflaeche sagt "CPU-Ersatz".
CPU_ERSATZ = False
if not AKIDA_DA:
    import os as _os
    if _os.environ.get("VORSA_CPU_LERNEN", "") == "1":
        try:
            from . import akida_cpu as akida      # type: ignore
            AKIDA_DA = True
            CPU_ERSATZ = True
        except Exception:                  # pragma: no cover
            akida = None


@dataclass
class Lernbericht:
    ok: bool
    klassen: List[str] = field(default_factory=list)
    beispiele: int = 0
    ms_je_beispiel: float = 0.0
    num_weights: int = 0
    neuronen_je_klasse: int = 0
    aktive_merkmale: float = 0.0
    dichte: float = 0.0             # Anteil feuernder Merkmale, nach Ausduennen
    dichte_vorher: float = 0.0      # ... und davor
    ausduennen: str = ""
    aufgerichtet: int = 0           # Bilder, bei denen das Teil freigestellt wurde
    nicht_aufgerichtet: int = 0     # ... und bei denen es nicht ging
    karten: int = 1                 # Karten im Verbund
    treffer_eigen: float = 0.0          # auf den Lernbildern selbst
    verwechslung: List[List[int]] = field(default_factory=list)
    grund: str = ""
    gesichert: bool = False
    warnungen: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "ok": self.ok, "klassen": self.klassen, "beispiele": self.beispiele,
            "ms_je_beispiel": round(self.ms_je_beispiel, 1),
            "num_weights": self.num_weights,
            "neuronen_je_klasse": self.neuronen_je_klasse,
            "dichte": round(self.dichte * 100, 1),
            "dichte_vorher": round(self.dichte_vorher * 100, 1),
            "ausduennen": self.ausduennen,
            "aufgerichtet": self.aufgerichtet,
            "nicht_aufgerichtet": self.nicht_aufgerichtet,
            "karten": self.karten,
            "aktive_merkmale": round(self.aktive_merkmale, 1),
            "treffer_eigen": round(self.treffer_eigen * 100),
            "verwechslung": self.verwechslung,
            "grund": self.grund, "warnungen": self.warnungen,
            "gesichert": self.gesichert,
        }


class EdgeLerner:
    """Haelt Merkmalsmodell und Lernschicht, lernt und erkennt."""

    # Kantenlaenge der Silhouette, die an die Lernschicht geht. 48 statt 32,
    # damit der duenne Schaft eines Schraubenziehers nicht wegfaellt.
    SIL = 48

    # Neuheitswaechter: unter dieser Wiederfindungsquote gilt ein Teil als
    # NIE GELERNT. Gemessen: sauber liegende bekannte Teile treffen 70-95 %,
    # das Karabiner-Loch als Fremdkoerper traf 83 % auf die FALSCHE Klasse -
    # aber echte Fremdteile liegen erfahrungsgemaess unter 50 %. 55 % laesst
    # schraege Lagen bekannter Teile durch und faengt Fremdes.
    UNBEKANNT_AB = 0.55
    # Version des Lernverfahrens (siehe speichern/laden): aeltere
    # Sicherungen werden beim Start automatisch neu gelernt.
    # 2 = Negativklasse ohne Torso-Varianten + Loch-Signatur.
    # 3 = leere Negativ-Fotos (nur Hintergrund) werden nicht gelernt.
    LERNSTAND = 3

    def __init__(self, groesse: int = 128, neuronen_je_klasse: int = 20,
                 aufrichten: bool = True, formbild: bool = True,
                 modus: str = "silhouette"):
        self.groesse = groesse
        self.neuronen = neuronen_je_klasse
        self.aufrichten = aufrichten
        # Formbild: Silhouette, Kanten und Dickenverlauf statt Farbe. Farbe
        # haengt an Belichtung und Weissabgleich - die Form nicht.
        self.formbild = formbild
        # "silhouette": die aufgerichtete Silhouette geht DIREKT in die
        # Lernschicht - ohne Zufallsrumpf. Das Neuronenpotential ist dann die
        # Ueberlappung zweier ausgerichteter Silhouetten: das ehrlichste Mass
        # fuer Teile im Gegenlicht. Der Zufallsrumpf ("merkmale") hat genau
        # diese Information erst zerhackt und dann verglichen.
        self.modus = modus
        self._roh_gezaehlt = [0, 0]      # [gesamt, nicht aufrichtbar]
        self.modell = None
        self.rumpf = None
        self.geraet = None
        self.klassen: List[str] = []
        self.bericht: Optional[Lernbericht] = None
        self.letzter_fehler = ""
        self._faktor = 1.0
        self._schwelle_basis: Dict[str, np.ndarray] = {}
        # Kennzeichen des Fotobestands, mit dem gelernt wurde. Aendert er
        # sich, ist ein gesicherter Lernstand ueberholt.
        self.fingerabdruck = ""
        self.herkunft = ""          # "gelernt" | "zurueckgespielt"
        self._schwellwerte: Optional[np.ndarray] = None
        self.modelle: List = []          # Kartenverbund (Silhouettenmodus)
        self.geraete: List = []
        # Wie viele Karten darf der Verbund belegen? Der Server setzt das
        # auf 3, wenn der M3-Detektor die letzte Karte bekommt (Stufe 2).
        self.karten_max = 4
        # KARTENVERTEILER (SE Inspect A4, 1.9.42): "repliziert" = jede
        # Karte traegt alle Prototypen, ein Auftrag braucht nur EINE Karte
        # -> mehrere Auftraege gleichzeitig auf mehreren Karten.
        # "verteilt" = Beispiele ueber die Karten verteilt (mehr Kapazitaet),
        # jeder Auftrag fragt alle Karten (max-Verbund). replikation=True
        # ist der Wunsch; was wirklich passt, entscheidet _verbund_planen.
        self.replikation = False
        self.verbund_modus = "verteilt"
        self._karten_locks: Dict[int, threading.Lock] = {}
        # KARTEN-WAECHTER (1.9.36): je Karte Live-Stand (was rechnet sie
        # gerade, wie lange, wie oft) und Stoerung. Eine Karte, die beim
        # Abgleich einen Fehler wirft (DMA-Timeout, Link weg), wird fuer
        # karten_sperre_s aus dem Verbund genommen; der Rest antwortet
        # weiter. Nach Ablauf ein vorsichtiger Versuch - klappt er, ist sie
        # wieder drin. Der Server haengt einen Rueckruf fuer den Alarm an.
        self.karten_stand: Dict[int, dict] = {}
        self.karten_sperre_s = 60.0
        self.on_karte_fehler = None      # callback(ki, grund, wieder: bool)
        self._lock = threading.Lock()
        # Ergebnis der Geraetesuche merken. akida.devices() ist teuer und darf
        # NICHT bei jeder Zustandsabfrage laufen - das legt den Server lahm.
        self._verf: Optional[Tuple[bool, str]] = None

    # ------------------------------------------------------------------
    def verfuegbar(self, neu: bool = False) -> Tuple[bool, str]:
        if self._verf is not None and not neu:
            return self._verf
        self._verf = self._pruefe_verfuegbar()
        return self._verf

    def _pruefe_verfuegbar(self) -> Tuple[bool, str]:
        if not AKIDA_DA:
            return False, ("MetaTF nicht importierbar - Umgebung aktivieren: "
                           "source ~/akida-env/bin/activate")
        if CPU_ERSATZ:
            return True, (f"CPU-Ersatz ({len(akida.devices())} simulierte Karten) - "
                          "Silhouetten-Abgleich in Software, nur zum Ausprobieren")
        try:
            g = akida.devices()
        except Exception as exc:
            return False, f"akida.devices(): {str(exc)[:90]}"
        if not g:
            return False, "kein AKD1500 gefunden"
        return True, str(getattr(g[0], "desc", "Geraet"))

    # ------------------------------------------------------------------
    def _rumpf_bauen(self, mit_lernschicht: int = 0, roh_merkmale: bool = False):
        m = akida.Model()
        m.add(akida.InputConvolutional(
            input_shape=(self.groesse, self.groesse, 3), filters=16,
            kernel_size=(3, 3), kernel_stride=(2, 2), padding=akida.Padding.Same,
            weights_bits=8, activation=True, act_bits=4,
            pool_type=akida.PoolType.Max, pool_size=(2, 2), pool_stride=(2, 2),
            name="stem"))
        m.add(akida.SeparableConvolutional(
            filters=32, kernel_size=(3, 3), kernel_stride=(2, 2),
            padding=akida.Padding.Same, weights_bits=4, activation=True,
            act_bits=4, name="sep1"))
        # Letzte Merkmalsschicht mit 1-Bit-Aktivierung: die Lernschicht
        # arbeitet mit binaeren Gewichten und braucht eine duenn besetzte,
        # binaere Eingabe, sonst lernt sie zwar, unterscheidet aber schlecht.
        # roh_merkmale=True liefert die Potentiale statt der Feuerentscheidung.
        # Nur so laesst sich die Schwelle ausrechnen, statt sie zu suchen.
        m.add(akida.SeparableConvolutional(
            filters=64, kernel_size=(3, 3), kernel_stride=(2, 2),
            padding=akida.Padding.Same, weights_bits=4,
            activation=not roh_merkmale,
            act_bits=1, name="merkmale"))
        if mit_lernschicht:
            m.add(akida.FullyConnected(
                units=mit_lernschicht, weights_bits=1, activation=False,
                name="lernschicht"))

        rng = np.random.default_rng(0)
        for layer in m.layers:
            if layer.name == "lernschicht":
                continue
            lim = 127 if layer.name == "stem" else 7
            for vn in list(layer.variables.names):
                cur = np.asarray(layer.get_variable(vn))
                if cur.size == 0:
                    continue
                if "weight" in vn:
                    mag = rng.integers(1, lim + 1, size=cur.shape)
                    sig = rng.choice(np.array([-1, 1]), size=cur.shape)
                    layer.set_variable(vn, (mag * sig).astype(cur.dtype))
                elif "act_step" in vn and not np.any(cur):
                    layer.set_variable(vn, np.ones_like(cur))
        return m

    # Zielbereich fuer die Belegungsdichte der Merkmalsschicht.
    #
    # Das ist der Kern der Sache. Die Lernschicht hat BINAERE Gewichte und
    # zaehlt Uebereinstimmungen. Feuert die Haelfte aller Merkmale, passt
    # jedes Neuron ungefaehr gleich gut auf jede Eingabe - die Potentiale
    # laufen in die Saettigung und alle Klassen kommen auf denselben Wert.
    # Genau das war am 2026-08-27 zu sehen: 33 / 33 / 33 Prozent bei drei
    # Objekten, also ein glattes Unentschieden.
    #
    # Mit wenigen aktiven Merkmalen wird die Uebereinstimmung wieder
    # aussagekraeftig. 4 bis 12 Prozent hat sich als brauchbar erwiesen.
    DICHTE_ZIEL = (0.04, 0.12)
    DICHTE_WUNSCH = 0.07

    def _dichte(self, rumpf, proben: np.ndarray) -> float:
        """Anteil feuernder Merkmale, gemittelt ueber die Proben."""
        merkmale = np.asarray(rumpf.forward(proben))
        flach = merkmale.reshape(merkmale.shape[0], -1)
        return float((flach > 0).mean())

    def _schwelle_setzen(self, rumpf, faktor: float) -> bool:
        """Skaliert die Feuerschwelle der letzten Merkmalsschicht."""
        schicht = None
        for l in rumpf.layers:
            if l.name == "merkmale":
                schicht = l
        if schicht is None:
            return False
        gesetzt = False
        for vn in list(schicht.variables.names):
            if "threshold" not in vn:
                continue
            if vn not in self._schwelle_basis:
                self._schwelle_basis[vn] = np.asarray(schicht.get_variable(vn)).copy()
            basis = self._schwelle_basis[vn].astype(np.float64)
            # Bei einer Basis aus lauter Nullen greift ein Faktor nicht -
            # dann von 1 aus hochziehen statt bei 0 zu bleiben.
            if not np.any(basis):
                basis = np.ones_like(basis)
            neu = np.rint(basis * faktor).astype(
                np.asarray(schicht.get_variable(vn)).dtype)
            schicht.set_variable(vn, neu)
            gesetzt = True
        if gesetzt:
            # Merken, damit dasselbe Ausduennen auf dem Modell MIT Lernschicht
            # wiederholt werden kann. Wuerde dort die alte Schwelle stehen,
            # lernte die Karte auf anderen Merkmalen, als hier gemessen wurden.
            self._faktor = faktor
        return gesetzt

    def _schwelle_aus_potentialen(self, proben: np.ndarray,
                                  ziel: float) -> Optional[np.ndarray]:
        """Berechnet die Feuerschwelle je Filter aus den echten Potentialen.

        Das Tasten mit Faktoren ist hier gescheitert: die Belegungsdichte
        faellt nicht gleichmaessig, sondern springt. Am 2026-08-27 ging sie
        von 51 % bei Faktor 4096 auf 0,1 % bei Faktor 8192 - dazwischen liegt
        nichts, was man haette treffen koennen.

        Deshalb umgekehrt: die Schicht einmal OHNE Aktivierung rechnen lassen,
        die Potentiale ansehen und die Schwelle je Filter auf das Quantil
        legen, das genau den gewuenschten Anteil uebrig laesst. Ein Rechenweg
        statt einer Suche - und je Filter, damit nicht einige alles beitragen
        und andere nie feuern.
        """
        try:
            roh = self._rumpf_bauen(roh_merkmale=True)
            p = np.asarray(roh.forward(proben)).astype(np.float64)
        except Exception:
            return None
        if p.ndim != 4 or p.shape[-1] < 2:
            return None
        # (N, H, W, F) -> je Filter alle Positionen aller Proben
        je_filter = p.transpose(3, 0, 1, 2).reshape(p.shape[-1], -1)
        return np.percentile(je_filter, 100.0 * (1.0 - ziel), axis=1)

    def _schwelle_schreiben(self, modell, werte: np.ndarray) -> bool:
        for l in modell.layers:
            if l.name != "merkmale":
                continue
            for vn in list(l.variables.names):
                if "threshold" not in vn:
                    continue
                cur = np.asarray(l.get_variable(vn))
                try:
                    l.set_variable(vn, np.rint(
                        werte.reshape(cur.shape)).astype(cur.dtype))
                    return True
                except Exception:
                    return False
        return False

    def _ausduennen(self, rumpf, proben: np.ndarray) -> Tuple[float, str]:
        """Sucht die Feuerschwelle, bei der die Merkmale duenn besetzt sind.

        Zweiteilung ueber den Faktor, nicht Raten: welcher Zahlenwert die
        richtige Dichte ergibt, haengt an den zufaelligen Gewichten des
        Rumpfes und ist von aussen nicht vorhersagbar.
        """
        self._schwelle_basis = {}
        dichte = self._dichte(rumpf, proben)
        if dichte <= self.DICHTE_ZIEL[1]:
            return dichte, "Merkmale waren bereits duenn besetzt"
        if not self._schwelle_setzen(rumpf, 1.0):
            return dichte, ("Feuerschwelle nicht einstellbar - Merkmale bleiben "
                            "dicht besetzt, die Objekte werden sich aehnlich sehen")

        lo, hi = 1.0, 2.0
        # Erst eine Obergrenze finden, bei der es duenn genug ist.
        for _ in range(12):
            self._schwelle_setzen(rumpf, hi)
            if self._dichte(rumpf, proben) <= self.DICHTE_WUNSCH:
                break
            lo, hi = hi, hi * 2.0
        else:
            self._schwelle_setzen(rumpf, hi)
            return self._dichte(rumpf, proben), (
                f"Merkmale liessen sich nur auf "
                f"{self._dichte(rumpf, proben)*100:.1f} % ausduennen")

        for _ in range(14):
            mitte = (lo + hi) / 2.0
            self._schwelle_setzen(rumpf, mitte)
            d = self._dichte(rumpf, proben)
            if d > self.DICHTE_WUNSCH:
                lo = mitte
            else:
                hi = mitte
            if self.DICHTE_ZIEL[0] <= d <= self.DICHTE_ZIEL[1]:
                return d, f"Feuerschwelle x{mitte:.2f}"
        self._schwelle_setzen(rumpf, hi)
        d = self._dichte(rumpf, proben)
        return d, f"Feuerschwelle x{hi:.2f}"

    def _silhouette(self, bild: np.ndarray,
                    maske: Optional[np.ndarray] = None) -> np.ndarray:
        """Aufgerichtete Silhouette als ZWEI binaere Kanaele (SIL x SIL x 2).

        Kanal 1: die Fuellung, Kanal 2: ein zwei Punkte breites Band entlang
        der Aussenlinie. In der Rasterprobe vom 2026-08-27 (vier Teile,
        zwanzig ungesehene Ansichten, zwei Zufallslaeufe) war genau diese
        Kombination die beste: 97,5 % Wiedererkennung gegen 93,8 % fuer die
        Fuellung allein. Die Fuellung traegt die Flaeche, das Band bestraft
        Umrissabweichungen doppelt.
        """
        from .normalisieren import aufrichten_oder_roh
        formb, geklappt = aufrichten_oder_roh(bild, self.groesse, form=True,
                                              vorgabe_maske=maske)
        self._roh_gezaehlt[0] += 1
        self._roh_gezaehlt[1] += 0 if geklappt else 1
        sil = cv2.resize(formb[..., 0], (self.SIL, self.SIL),
                         interpolation=cv2.INTER_AREA)
        return self._kanaele((sil > 127).astype(np.uint8))

    @staticmethod
    def _hat_loch(fuell: np.ndarray) -> bool:
        """Hat die Silhouette ein UMSCHLOSSENES Loch (>= 8 % der Fuellung)?

        Merkmal fuer den Loch-Anker (2026-08-28): ein grosses inneres Loch
        ist in der Teilewelt eine Klassen-Signatur (Ring/Karabiner) - und
        bei satter Ueberlappung oft das einzige, was vom verdeckten Teil
        eindeutig sichtbar bleibt."""
        f = (fuell > 0).astype(np.uint8)
        inv = (1 - f).astype(np.uint8)
        n, _lab, st, _ = cv2.connectedComponentsWithStats(inv, 4)
        H, W = f.shape[:2]
        fl = max(int(f.sum()), 1)
        for i in range(1, n):
            l, t = st[i, cv2.CC_STAT_LEFT], st[i, cv2.CC_STAT_TOP]
            w, h = st[i, cv2.CC_STAT_WIDTH], st[i, cv2.CC_STAT_HEIGHT]
            if (l > 0 and t > 0 and l + w < W and t + h < H
                    and st[i, cv2.CC_STAT_AREA] >= 0.08 * fl):
                return True
        return False

    def _kanaele(self, m: np.ndarray) -> np.ndarray:
        """Fuellung + Umrissband aus einer binaeren Maske (SIL x SIL)."""
        rand = cv2.morphologyEx(m, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
        rand = cv2.dilate(rand, np.ones((2, 2), np.uint8))
        return np.ascontiguousarray(np.stack([m, rand], axis=-1))

    def _torso_varianten(self, x: np.ndarray, rng, anzahl: int = 1) -> list:
        """Kuenstlich verdeckte Fassungen einer Lernsilhouette.

        Torso-Lernen (2026-08-27): liegt ein Teil AUF einem anderen, sieht
        die Kamera vom unteren nur einen Torso - und der beste Treffer fuer
        einen Karabiner-Torso war faelschlich die SD-Karte. Also bekommt der
        Chip Torsi als eigene Ansichten: ein Randstreifen (20-35 % der Box)
        wird abgedeckt, der Rest wird NEU aufgerichtet und formatfuellend
        gesetzt - genau so praepariert die Live-Strecke einen echten Torso.
        """
        S = self.SIL
        fuell = x[..., 0].astype(np.uint8)
        punkte = cv2.findNonZero(fuell)
        if punkte is None or len(punkte) < 40:
            return []
        bx, by, bw, bh = cv2.boundingRect(punkte)
        aus = []
        for _ in range(anzahl):
            f = fuell.copy()
            anteil = float(rng.uniform(0.20, 0.35))
            if rng.random() < 0.5:                      # Streifen von links/rechts
                w = max(2, int(bw * anteil))
                x0 = bx if rng.random() < 0.5 else bx + bw - w
                f[by:by + bh, x0:x0 + w] = 0
            else:                                       # von oben/unten
                h = max(2, int(bh * anteil))
                y0 = by if rng.random() < 0.5 else by + bh - h
                f[y0:y0 + h, bx:bx + bw] = 0
            if f.sum() < 0.4 * fuell.sum():
                continue
            # Nur das groesste Stueck behalten - zerfallene Reste lernt
            # die Live-Strecke ohnehin als getrennte Teile.
            n, lab = cv2.connectedComponents(f)
            if n > 2:
                groesstes = 1 + int(np.argmax(
                    [np.sum(lab == i) for i in range(1, n)]))
                f = (lab == groesstes).astype(np.uint8)
            # Neu aufrichten: eigene Drehlage des Torsos, lange Seite
            # waagerecht, dann formatfuellend mit Rand.
            pk = cv2.findNonZero(f)
            if pk is None or len(pk) < 30:
                continue
            (cx, cy), (rw, rh), wk = cv2.minAreaRect(pk)
            if rw < rh:
                wk += 90.0
            M = cv2.getRotationMatrix2D((cx, cy), wk, 1.0)
            g = cv2.warpAffine(f, M, (S, S), flags=cv2.INTER_NEAREST)
            pg = cv2.findNonZero(g)
            if pg is None:
                continue
            gx, gy, gw, gh = cv2.boundingRect(pg)
            ziel = S - 4
            fak = min(ziel / max(gw, 1), ziel / max(gh, 1))
            neu_w, neu_h = max(1, int(gw * fak)), max(1, int(gh * fak))
            stueck = cv2.resize(g[gy:gy + gh, gx:gx + gw], (neu_w, neu_h),
                                interpolation=cv2.INTER_NEAREST)
            leer = np.zeros((S, S), np.uint8)
            ox, oy = (S - neu_w) // 2, (S - neu_h) // 2
            leer[oy:oy + neu_h, ox:ox + neu_w] = stueck
            # Seitenwahl wie in der Live-Strecke: Schwerpunkt nach
            # links/oben, gegen die 180-Grad-Mehrdeutigkeit.
            mom = cv2.moments(leer, binaryImage=True)
            if mom["m00"] > 0:
                if mom["m10"] / mom["m00"] > S / 2:
                    leer = leer[:, ::-1]
                if mom["m01"] / mom["m00"] > S / 2:
                    leer = leer[::-1, :]
            aus.append(self._kanaele(np.ascontiguousarray(leer)))
        return aus

    def _aufbereiten(self, bild: np.ndarray) -> np.ndarray:
        """Bild so vorbereiten, wie die Karte es sehen soll.

        Mit `aufrichten` wird das Teil freigestellt, waagerecht gedreht,
        zentriert und formatfuellend auf neutralen Grund gesetzt. Damit
        entfallen Drehung, Groesse, Lage und Hintergrund als Stoergroessen -
        genau die vier Dinge, gegen die ein untrainierter Merkmalsextraktor
        nichts ausrichten kann.
        """
        if self.aufrichten:
            from .normalisieren import aufrichten_oder_roh
            aus, geklappt = aufrichten_oder_roh(bild, self.groesse,
                                                form=self.formbild)
            self._roh_gezaehlt[0] += 1
            self._roh_gezaehlt[1] += 0 if geklappt else 1
            return aus
        b = cv2.resize(bild, (self.groesse, self.groesse),
                       interpolation=cv2.INTER_AREA)
        if b.ndim == 2:
            b = cv2.cvtColor(b, cv2.COLOR_GRAY2BGR)
        return np.ascontiguousarray(b.astype(np.uint8))

    # ------------------------------------------------------------------
    def lerne(self, bilder_je_klasse: Dict[str, List[np.ndarray]],
              lauf=None) -> Lernbericht:
        """Lernt alle Klassen aus ihren Bildern. Vorheriges Wissen wird verworfen.

        `lauf` ist ein `jobs.Lauf` fuer den Fortschritt. Ohne ihn laeuft alles
        genauso, nur stumm - aber mit 700 Beispielen dauert das lange genug,
        dass eine Oberflaeche ohne Rueckmeldung wie abgestuerzt aussieht.
        """
        def melde(text, schritt=0, von=0):
            if lauf is not None:
                lauf.setze_phase(text, schritt, von)
                if not schritt:
                    lauf.melde(text)

        with self._lock:
            da, info = self.verfuegbar()
            if not da:
                return Lernbericht(ok=False, grund=info)

            if self.modus == "silhouette":
                return self._lerne_silhouette(bilder_je_klasse, lauf)

            namen = [n for n, b in bilder_je_klasse.items() if b]
            if len(namen) < 2:
                return Lernbericht(
                    ok=False,
                    grund="mindestens zwei Objekte mit Fotos noetig - "
                          "mit einer Klasse gibt es nichts zu unterscheiden")

            warnungen = []
            for n in namen:
                if len(bilder_je_klasse[n]) < 3:
                    warnungen.append(
                        f"„{n}“ hat nur {len(bilder_je_klasse[n])} Bilder - "
                        "gemessen waren 5 je Objekt noetig")

            self.geraet = akida.devices()[0]

            # 1. Merkmale ausduennen. DAS ist der entscheidende Schritt.
            #
            #    Ein Rumpf mit zufaelligen Gewichten laesst rund die Haelfte
            #    aller Merkmale feuern. Die Lernschicht zaehlt aber nur
            #    Uebereinstimmungen binaerer Muster - bei halb gefuellten
            #    Mustern passt jedes Neuron auf jede Eingabe, die Potentiale
            #    saettigen, und am Ende bekommen alle Klassen denselben Wert.
            #    Am 2026-08-27 waren das 33/33/33 Prozent bei drei Objekten.
            self._roh_gezaehlt = [0, 0]
            melde("Merkmale ausduennen")
            self.rumpf = self._rumpf_bauen()
            proben = np.stack([
                self._aufbereiten(b)
                for n in namen for b in bilder_je_klasse[n][:4]
            ])
            dichte_vorher = self._dichte(self.rumpf, proben)

            # Erst rechnen, nur zur Not tasten.
            self._schwellwerte = self._schwelle_aus_potentialen(
                proben, self.DICHTE_WUNSCH)
            if (self._schwellwerte is not None
                    and self._schwelle_schreiben(self.rumpf, self._schwellwerte)):
                dichte = self._dichte(self.rumpf, proben)
                wie = "Schwelle je Filter aus den Potentialen berechnet"
                if not (self.DICHTE_ZIEL[0] <= dichte <= self.DICHTE_ZIEL[1]):
                    # Quantile auf ganzzahligen Schwellen treffen nicht exakt.
                    # Nachziehen, solange es in die richtige Richtung geht.
                    for _ in range(6):
                        if dichte > self.DICHTE_ZIEL[1]:
                            self._schwellwerte = self._schwellwerte + np.maximum(
                                1, np.abs(self._schwellwerte) * 0.05)
                        elif dichte < self.DICHTE_ZIEL[0]:
                            self._schwellwerte = self._schwellwerte - np.maximum(
                                1, np.abs(self._schwellwerte) * 0.05)
                        else:
                            break
                        self._schwelle_schreiben(self.rumpf, self._schwellwerte)
                        dichte = self._dichte(self.rumpf, proben)
                    wie += f", nachgezogen auf {dichte*100:.1f} %"
            else:
                self._schwellwerte = None
                dichte, wie = self._ausduennen(self.rumpf, proben)

            if lauf is not None:
                lauf.melde(f"Merkmalsdichte {dichte_vorher*100:.0f} % -> "
                           f"{dichte*100:.1f} %  ({wie})")

            merkmale = np.asarray(self.rumpf.forward(proben))
            flach = merkmale.reshape(merkmale.shape[0], -1)
            aktiv = float((flach > 0).sum(axis=1).mean())

            if aktiv < 3:
                return Lernbericht(
                    ok=False, aktive_merkmale=aktiv,
                    grund="die Merkmalsschicht feuert kaum - aus diesen Bildern "
                          "ist nichts zu lernen (zu dunkel? Ausschnitt leer?)")
            if dichte > self.DICHTE_ZIEL[1]:
                warnungen.append(
                    f"Merkmale sind mit {dichte*100:.0f} % dicht besetzt "
                    f"(Ziel unter {self.DICHTE_ZIEL[1]*100:.0f} %). {wie}. "
                    "Die Objekte werden sich dadurch aehnlich sehen.")

            # 2. Neuronenzahl an die tatsaechliche Beispielzahl koppeln.
            #
            #    Jedes Neuron der Lernschicht haelt ein Muster. Kommen mehr
            #    Beispiele als Neuronen, schreibt fit() in bereits belegte
            #    Neuronen - die spaeteren Bilder ueberschreiben die frueheren.
            #    Mit Augmentierung passiert das schnell: 5 Fotos x 8 Varianten
            #    sind 40 Beispiele gegen 20 Neuronen. Es sieht dann nach
            #    Lernen aus, aber die Haelfte der Aufnahmen ist wirkungslos.
            #
            #    Deshalb: mindestens so viele Neuronen wie Beispiele der
            #    groessten Klasse. Nach oben begrenzt, weil die Schicht sonst
            #    nicht mehr in einen Durchgang passt - dann lieber ehrlich
            #    warnen als stillschweigend abschneiden.
            groesste = max(len(b) for b in bilder_je_klasse.values())
            neuronen = max(self.neuronen, groesste)
            OBERGRENZE = 512
            if len(namen) * neuronen > OBERGRENZE:
                neuronen = max(2, OBERGRENZE // len(namen))
                warnungen.append(
                    f"Mehr Beispiele ({groesste} je Objekt) als Platz auf der "
                    f"Karte ({neuronen} Neuronen je Objekt). Die Karte fasst sie "
                    "zu Gruppen zusammen - weniger Varianten waeren hier "
                    "genauer als mehr.")
            self.neuronen_zuletzt = neuronen

            # 3. Modell mit Lernschicht bauen und auf den Chip legen.
            #
            #    Mehr Neuronen sind nicht beliebig zu haben: die Lernschicht
            #    haengt an 8x8x64 = 4096 Merkmalen, jedes Neuron bringt also
            #    4096 Gewichte mit. Irgendwann passt die Schicht nicht mehr in
            #    eine NP. Statt eine Obergrenze zu raten, wird sie gesucht:
            #    gewuenschte Zahl versuchen, bei Fehlschlag halbieren.
            #
            #    Das Raten hatte mich schon einmal in die Irre gefuehrt - die
            #    Karte sagt selbst am besten, was hineinpasst.
            melde("Lernschicht auf die Karte legen")
            versuche: List[str] = []
            gewuenscht = neuronen

            def frisches_modell(n_neuronen: int):
                """Neues Modell, gemappt und ausgeduennt - noch nicht compiled.

                Fuer jeden num_weights-Versuch braucht es ein FRISCHES Modell:
                `compile` laesst sich auf demselben Modell kein zweites Mal
                aufrufen ("Model was already compiled"). Das war der Abbruch
                vom 2026-08-27.
                """
                m = self._rumpf_bauen(mit_lernschicht=len(namen) * n_neuronen)
                m.map(self.geraet, hw_only=True)
                if self._schwellwerte is not None:
                    self._schwelle_schreiben(m, self._schwellwerte)
                else:
                    self._schwelle_setzen(m, self._faktor)
                return m

            while True:
                try:
                    self.modell = frisches_modell(neuronen)
                    break
                except Exception as exc:
                    versuche.append(f"{neuronen} Neuronen: {str(exc)[:80]}")
                    if neuronen <= 4:
                        return Lernbericht(ok=False, warnungen=versuche, grund=(
                            "Die Lernschicht laesst sich nicht auf die Karte "
                            "legen - auch nicht in der kleinsten Groesse. "
                            f"Zuletzt: {str(exc)[:110]}"))
                    neuronen = max(4, neuronen // 2)

            if neuronen < gewuenscht:
                warnungen.append(
                    f"Nur {neuronen} statt {gewuenscht} Neuronen je Objekt - "
                    "mehr passt nicht auf die Karte. Die Beispiele werden zu "
                    "Gruppen zusammengefasst; weniger Varianten waeren hier "
                    "genauer als mehr.")
            self.neuronen_zuletzt = neuronen

            # 4. num_weights nicht raten, sondern ausprobieren.
            #
            #    num_weights sagt, wie viele Verbindungen ein Neuron behaelt.
            #    Zu wenige, und alle Neuronen sehen gleich aus; zu viele, und
            #    jedes passt auf alles. Der richtige Wert haengt an der
            #    Belegungsdichte, die wir gerade erst eingestellt haben - eine
            #    feste Formel dafuer waere wieder nur eine Behauptung.
            X = {name: np.stack([self._aufbereiten(b) for b in bilder_je_klasse[name]])
                 for name in namen}
            C = len(namen)
            kandidaten = sorted({max(2, int(aktiv * f)) for f in (0.25, 0.5, 0.75, 1.0)})

            bestes = None
            t0 = time.perf_counter()
            n_bsp = sum(len(x) for x in X.values())
            for nr, kandidat in enumerate(kandidaten, 1):
                melde(f"Lernen, Versuch {nr} von {len(kandidaten)}",
                      nr, len(kandidaten))
                try:
                    modell = frisches_modell(neuronen)
                    modell.compile(optimizer=akida.AkidaUnsupervised(
                        num_weights=kandidat, num_classes=C,
                        learning_competition=0.1))
                    for k, name in enumerate(namen):
                        modell.fit(X[name],
                                   np.full(len(X[name]), k, dtype=np.int32))
                    vw = [[0] * C for _ in range(C)]
                    richtig = gesamt = 0
                    for k, name in enumerate(namen):
                        v = np.asarray(modell.predict_classes(
                            X[name], num_classes=C)).ravel()
                        for p in v:
                            vw[k][int(p)] += 1
                            gesamt += 1
                            richtig += int(p) == k
                except Exception as exc:
                    versuche.append(f"num_weights {kandidat}: {str(exc)[:70]}")
                    continue
                quote = richtig / max(gesamt, 1)
                verschieden = sum(1 for s in range(C) if any(vw[z][s] for z in range(C)))
                if lauf is not None:
                    lauf.melde(f"  num_weights {kandidat}: {quote*100:.0f} % "
                               f"Treffer, {verschieden} von {C} Antwortsorten")
                # Eine Antwortsorte fuer alles ist wertlos, egal wie hoch die
                # Quote dabei aussieht. Deshalb zaehlt sie mit.
                guete = (verschieden, quote)
                if bestes is None or guete > bestes[0]:
                    # Das Modell des Siegers behalten - dann muss der Gewinner
                    # nicht noch einmal gelernt werden.
                    bestes = (guete, kandidat, vw, quote, modell)
            dauer = (time.perf_counter() - t0) * 1000 / max(len(kandidaten), 1)

            if bestes is None:
                return Lernbericht(ok=False, warnungen=versuche, grund=(
                    "Keiner der num_weights-Werte liess sich lernen: "
                    + "; ".join(versuche[-2:])))

            _guete, num_weights, vw, quote, self.modell = bestes

            # Der Sieger muss zurueck auf die Karte. Jeder Versuch hat sein
            # eigenes Modell dorthin gelegt, also liegt dort gerade der
            # LETZTE - nicht der beste. Das faellt sonst nirgends auf: das
            # Objekt in der Hand waere der Sieger, die Karte rechnete mit
            # etwas anderem.
            melde(f"Bestes Ergebnis auf die Karte legen (num_weights {num_weights})")
            try:
                self.modell.map(self.geraet, hw_only=True)
            except Exception as exc:
                return Lernbericht(ok=False, warnungen=versuche, grund=(
                    f"Sieger liess sich nicht auf die Karte legen: {str(exc)[:110]}"))

            # Und nachrechnen, dass dort auch wirklich der Sieger liegt.
            vw = [[0] * C for _ in range(C)]
            richtig = gesamt = 0
            for k, name in enumerate(namen):
                v = np.asarray(self.modell.predict_classes(
                    X[name], num_classes=C)).ravel()
                for p in v:
                    vw[k][int(p)] += 1
                    gesamt += 1
                    richtig += int(p) == k
            nachher = richtig / max(gesamt, 1)
            if abs(nachher - quote) > 0.02:
                warnungen.append(
                    f"Nach dem Zurueckspielen {nachher*100:.0f} % statt "
                    f"{quote*100:.0f} % - der Lernstand hat das Umlegen nicht "
                    "unveraendert ueberstanden.")
            quote = nachher
            melde(f"Auf der Karte: {quote*100:.0f} % Treffer auf den Lernbildern")
            if len(kandidaten) > 1:
                warnungen.append(
                    f"num_weights aus {kandidaten} gewaehlt: {num_weights}")

            self.klassen = namen
            einzig = sum(1 for s in range(C) if any(vw[z][s] for z in range(C)))
            if einzig == 1:
                warnungen.append(
                    "Es kommt immer dieselbe Antwort heraus - die Merkmale "
                    "trennen diese Objekte nicht.")

            self.bericht = Lernbericht(
                ok=True, klassen=namen, beispiele=n_bsp,
                ms_je_beispiel=dauer / max(n_bsp, 1),
                num_weights=num_weights, neuronen_je_klasse=neuronen,
                aktive_merkmale=aktiv, dichte=dichte,
                dichte_vorher=dichte_vorher, ausduennen=wie,
                aufgerichtet=self._roh_gezaehlt[0] - self._roh_gezaehlt[1],
                nicht_aufgerichtet=self._roh_gezaehlt[1],
                treffer_eigen=richtig / max(gesamt, 1),
                verwechslung=vw, warnungen=warnungen)
            return self.bericht

    # ------------------------------------------------------------------
    def _lerne_silhouette(self, bilder_je_klasse, lauf=None) -> Lernbericht:
        """Silhouetten-Abgleich: Eingang direkt in die Lernschicht.

        Aufbau auf der Karte:  InputData(48,48,1) -> FullyConnected(binaer).
        Jedes Neuron speichert eine Silhouette; das Potential zaehlt die
        ueberlappenden Punkte. Kein Zufallsrumpf, kein Ausduennen, keine
        Schwellensuche - alles, was dort schiefgehen konnte, existiert in
        diesem Aufbau nicht mehr.
        """
        def melde(text, schritt=0, von=0):
            if lauf is not None:
                lauf.setze_phase(text, schritt, von)
                if not schritt:
                    lauf.melde(text)

        namen = [n for n, b in bilder_je_klasse.items() if b]
        if len(namen) < 2:
            return Lernbericht(ok=False, grund=(
                "mindestens zwei Objekte mit Fotos noetig - mit einer Klasse "
                "gibt es nichts zu unterscheiden"))

        warnungen: List[str] = []
        self._roh_gezaehlt = [0, 0]
        melde("Silhouetten aufbereiten")
        X = {n: np.stack([self._silhouette(b) for b in bilder_je_klasse[n]])
             for n in namen}
        C = len(namen)
        n_bsp = sum(len(x) for x in X.values())
        an_je_bild = float(np.mean([x.sum() for n in namen for x in X[n]]))
        if an_je_bild < 20:
            return Lernbericht(ok=False, grund=(
                "die Silhouetten sind fast leer - Teil nicht freistellbar "
                "oder Ausschnitt leer"))
        melde(f"{n_bsp} Silhouetten, im Mittel {an_je_bild:.0f} gesetzte "
              f"Punkte von {self.SIL * self.SIL}")

        # num_weights = mittlere Punktzahl einer VOLLEN Silhouette - vor dem
        # Torso-Zuschlag berechnet, sonst saenke die Bezugsgroesse und jede
        # Prozentangabe wuerde billiger.
        num_weights = max(8, int(an_je_bild))

        # Loch-Signatur je Klasse festhalten (VOR dem Torso-Zuschlag, der
        # Loecher aufschneiden kann): Anteil der Ansichten mit
        # umschlossenem Loch. Der Loch-Anker der Live-Strecke benennt
        # damit verdeckte Ringe ueber ihr Loch statt ueber Aehnlichkeit.
        self.loch_klassen = {
            n: round(float(np.mean([self._hat_loch(x[..., 0])
                                    for x in X[n]])), 3)
            for n in namen}

        # TORSO-LERNEN: zu jeder Ansicht eine kuenstlich verdeckte Fassung.
        # Ein halb verdeckter Karabiner hiess sonst "SD Karte" - der Chip
        # kannte nur ganze Silhouetten, und der beste Ganzkoerper-Treffer
        # fuer einen Torso ist fast immer der falsche.
        melde("Torso-Varianten erzeugen")
        rng = np.random.default_rng(7)
        torso_gesamt = 0
        for n in namen:
            # KEINE Torsi fuer die Negativklasse: Stoerteil-Torsi matchen
            # Ringstuecke und liessen "nichts" echte Teile fressen
            # (m/hintergrund, 2026-08-28).
            if n in getattr(self, "negativ_namen", set()):
                continue
            varianten = []
            for x in X[n]:
                varianten += self._torso_varianten(x, rng)
            if varianten:
                X[n] = np.concatenate([X[n], np.stack(varianten)])
                torso_gesamt += len(varianten)
        n_bsp = sum(len(x) for x in X.values())
        if torso_gesamt:
            melde(f"{torso_gesamt} Torso-Varianten dazu (halb verdeckte "
                  f"Ansichten), zusammen {n_bsp} Beispiele")

        groesste = max(len(x) for x in X.values())
        neuronen = max(self.neuronen, groesste)

        # KARTENVERBUND: jede verfuegbare Karte lernt einen ANDEREN Anteil
        # der Ansichten (Karte i bekommt jede G-te Aufnahme, versetzt um i).
        # Zusammen halten G Karten das G-fache Gedaechtnis je Objekt - und
        # unsere Fehler waren fast immer "diese eine Drehlage war nicht im
        # Gedaechtnis". Erkannt wird spaeter mit der besten Uebereinstimmung
        # ueber alle Karten.
        alle = akida.devices()
        if not alle:
            return Lernbericht(ok=False, grund="keine Karte gefunden")
        self.geraete = list(alle[:max(1, self.karten_max)])
        # Nicht mehr Karten als Aufnahmen der kleinsten Klasse - sonst
        # bekaeme eine Karte von einem Objekt gar nichts zu sehen.
        kleinste = min(len(b) for b in bilder_je_klasse.values())
        plan = self._verbund_planen(len(self.geraete), kleinste, groesste)
        G = plan["karten"]
        self.geraete = self.geraete[:G]
        self._messwerk_an()
        anteil_groesste = plan["je_karte"]
        neuronen = max(self.neuronen, anteil_groesste)
        self.verbund_modus = plan["modus"]
        schritt = 1 if plan["modus"] == "repliziert" else G

        melde(f"Lernschicht auf {G} Karte(n) legen ({plan['modus']})")

        def karten_modell(n_neuronen: int, geraet):
            m = akida.Model()
            # input_bits=1: das Lernen verlangt BINAERE Eingaenge.
            try:
                m.add(akida.InputData(input_shape=(self.SIL, self.SIL, 2),
                                      input_bits=1))
            except TypeError:
                m.add(akida.InputData(input_shape=(self.SIL, self.SIL, 2)))
            m.add(akida.FullyConnected(units=C * n_neuronen, weights_bits=1,
                                       activation=False, name="lernschicht"))
            m.map(geraet, hw_only=True)
            return m

        while True:
            try:
                self.modelle = [karten_modell(neuronen, g)
                                for g in self.geraete]
                break
            except Exception as exc:
                if neuronen <= 4:
                    return Lernbericht(ok=False, grund=(
                        f"Lernschicht passt nicht auf die Karte: {str(exc)[:110]}"))
                neuronen = max(4, neuronen // 2)
        if neuronen < max(self.neuronen, anteil_groesste):
            warnungen.append(
                f"Nur {neuronen} Neuronen je Objekt und Karte - mehr passt "
                "nicht; aehnliche Ansichten teilen sich einen Platz.")
            if self.verbund_modus == "repliziert" and G > 1 and neuronen < groesste:
                # Replikation passt doch nicht ganz - ehrlich bleiben:
                # dann verteilen, damit nichts verloren geht.
                self.verbund_modus = "verteilt"
                schritt = G
                warnungen.append("Prototypen passen nicht komplett auf eine "
                                 "Karte - Verbund verteilt statt repliziert "
                                 "(Auftraege laufen nacheinander).")
        self.neuronen_zuletzt = neuronen

        t0 = time.perf_counter()
        for i, m in enumerate(self.modelle):
            melde(f"Lernen, Karte {i}", i + 1, G + 1)
            try:
                m.compile(optimizer=akida.AkidaUnsupervised(
                    num_weights=num_weights, num_classes=C,
                    learning_competition=0.1))
            except Exception as exc:
                return Lernbericht(ok=False,
                                   grund=f"compile Karte {i}: {str(exc)[:100]}")
            for k, name in enumerate(namen):
                # repliziert: jede Karte sieht ALLE Beispiele (i::1);
                # verteilt: Karte i jedes G-te, versetzt um i.
                teil = X[name][(i if schritt > 1 else 0)::schritt]
                if len(teil):
                    try:
                        tk = time.perf_counter()
                        m.fit(teil, np.full(len(teil), k, dtype=np.int32))
                        self.karte_notiz(i, f"Chip-Lernen: {name}, "
                                            f"{len(teil)} Beispiele",
                                         (time.perf_counter() - tk) * 1000.0)
                    except Exception as exc:
                        self.karte_gestoert(i, f"{type(exc).__name__}: {exc}")
                        return Lernbericht(ok=False, grund=(
                            f"Karte {i + 1} antwortet nicht ({str(exc)[:80]}) - "
                            "Karte zuruecksetzen (Zustand > Hardware) und "
                            "Chip-Lernen wiederholen"))
        dauer = (time.perf_counter() - t0) * 1000

        # Gegenprobe ueber den VERBUND - genau so, wie spaeter erkannt wird.
        melde("Gegenprobe", G + 1, G + 1)
        vw = [[0] * C for _ in range(C)]
        richtig = gesamt = 0
        for k, name in enumerate(namen):
            for x in X[name]:
                pots = self._verbund_potentiale(x[None, ...], C)
                p = int(np.argmax(pots))
                vw[k][p] += 1
                gesamt += 1
                richtig += p == k

        self.modell = self.modelle[0]
        self.rumpf = None
        self.klassen = namen
        einzig = sum(1 for s in range(C) if any(vw[z][s] for z in range(C)))
        if einzig == 1:
            warnungen.append("Es kommt immer dieselbe Antwort heraus - die "
                             "Silhouetten trennen diese Objekte nicht.")
        if self._roh_gezaehlt[1]:
            warnungen.append(
                f"{self._roh_gezaehlt[1]} Bilder ohne freistellbares Teil.")

        if G > 1:
            warnungen.append(
                f"Kartenverbund: {G} Karten, "
                + ("jede mit allen Prototypen (parallele Auftraege)."
                   if self.verbund_modus == "repliziert"
                   else "Prototypen verteilt (Auftraege nacheinander)."))
        self.bericht = Lernbericht(
            ok=True, klassen=namen, beispiele=n_bsp,
            ms_je_beispiel=dauer / max(n_bsp, 1),
            num_weights=num_weights, neuronen_je_klasse=neuronen,
            aktive_merkmale=an_je_bild,
            dichte=an_je_bild / (self.SIL * self.SIL),
            dichte_vorher=an_je_bild / (self.SIL * self.SIL),
            ausduennen="Silhouetten-Abgleich, kein Rumpf",
            aufgerichtet=self._roh_gezaehlt[0] - self._roh_gezaehlt[1],
            nicht_aufgerichtet=self._roh_gezaehlt[1],
            treffer_eigen=richtig / max(gesamt, 1),
            karten=G,
            verwechslung=vw, warnungen=warnungen)
        return self.bericht

    # ------------------------------------------------------------------
    # KARTENVERTEILER (A4): Planung des Verbunds, Urteil je Karte
    def _verbund_planen(self, karten: int, kleinste: int, groesste: int) -> dict:
        """Wie werden die Beispiele auf die Karten gelegt?

        repliziert: alle Karten, jede alle Beispiele (je_karte = groesste)
        verteilt:   hoechstens so viele Karten wie die kleinste Klasse
                    Beispiele hat, je Karte ein Anteil (aufgerundet)."""
        karten = max(1, int(karten))
        if self.replikation:
            return {"modus": "repliziert", "karten": karten, "je_karte": int(groesste)}
        G = max(1, min(karten, int(kleinste)))
        return {"modus": "verteilt", "karten": G, "je_karte": -(-int(groesste) // G)}

    def _karten_lock(self, ki: int) -> threading.Lock:
        with self._lock:
            l = self._karten_locks.get(ki)
            if l is None:
                l = self._karten_locks[ki] = threading.Lock()
            return l

    def _kalibriere(self, anteile: np.ndarray) -> np.ndarray:
        """1.9.70: Sicherheit je Objekt kalibriert (siehe vorsa/schwelle.py).
        kalibrierung = {Objektname: typische rohe Sicherheit richtiger
        Treffer}; ohne Eintrag bleibt der Wert roh."""
        if getattr(self, "_kalib_sperre", False):     # Testlauf: immer roh
            return anteile
        kal = getattr(self, "kalibrierung", None) or {}
        if not kal:
            return anteile
        a = np.array(anteile, dtype=np.float64)
        for i, n in enumerate(self.klassen):
            r = kal.get(n)
            if r:
                a[i] = min(1.0, a[i] / float(r) * 0.9)
        return a

    def _urteil(self, x: np.ndarray, pro_klasse: np.ndarray, sieger) -> dict:
        """Urteil aus Klassenpotentialen - eine Stelle fuer Verbund und
        Einzelkarte (Wiederfindung, Reinheit, unklar, unbekannt, warum)."""
        nw = max(int(getattr(self.bericht, "num_weights", 0) or 0), 1)
        probe_punkte = int((x > 0).sum())
        nenner = max(int(nw * 0.35), min(nw, probe_punkte), 8)
        wiederfindung = np.clip(pro_klasse / nenner, 0.0, 1.0)
        reinheit = np.clip(pro_klasse / max(probe_punkte, 8), 0.0, 1.0)
        anteile = self._kalibriere(np.minimum(wiederfindung, reinheit))
        beste = int(np.argmax(pro_klasse))
        sortiert = np.sort(pro_klasse)[::-1]
        vorsprung = (float(sortiert[0] - sortiert[1]) / max(float(sortiert[0]), 1.0)
                     if len(sortiert) > 1 else 1.0)
        return {
            "klasse": self.klassen[beste],
            "sicherheit": float(anteile[beste]),
            "vorsprung": round(vorsprung, 3),
            "unklar": vorsprung < 0.05,
            "unbekannt": float(anteile[beste]) < self.UNBEKANNT_AB,
            "warum": self.warum(sieger),
            "potentiale": [int(p) for p in pro_klasse],
            "alle": [{"name": n, "anteil": float(a)}
                     for n, a in zip(self.klassen, anteile)],
        }

    def erkenne_auf_karte(self, bild: np.ndarray, maske: Optional[np.ndarray],
                          ki: int) -> Optional[dict]:
        """Urteil mit EINER Karte (replizierter Verbund). Wirft bei
        Kartenfehler nach Meldung an den Waechter, damit der Verteiler den
        Auftrag anderswo wiederholen kann."""
        if self.modell is None or not self.klassen or self.modus != "silhouette":
            return None
        modelle = self.modelle or [self.modell]
        if ki < 0 or ki >= len(modelle) or not self.karte_nutzbar(ki):
            raise RuntimeError(f"Karte {ki} nicht nutzbar")
        C = len(self.klassen)
        x = self._silhouette(bild, maske)[None, ...]
        with self._karten_lock(ki):
            try:
                t0 = time.perf_counter()
                roh = np.asarray(modelle[ki].forward(x))[0].ravel()
                ms = (time.perf_counter() - t0) * 1000.0
            except Exception as exc:
                self.karte_gestoert(ki, f"{type(exc).__name__}: {exc}")
                raise
        self.karte_notiz(ki, "Silhouetten-Abgleich (parallel)", ms)
        self.chip_ms_letzte = ms
        pro_klasse = roh.reshape(C, -1).max(axis=1).astype(float)
        j = int(np.argmax(roh))
        return self._urteil(x, pro_klasse, (ki, j, float(roh[j])))

    # ------------------------------------------------------------------
    def _verbund_potentiale(self, x: np.ndarray, C: int) -> np.ndarray:
        """Bestes Potential je Klasse ueber ALLE Karten des Verbunds.

        Jede Karte kennt andere Ansichten; die beste Uebereinstimmung
        irgendeiner Karte ist die Antwort des Verbunds.
        """
        pots, _ = self._verbund_sieger(x, C)
        return pots

    # ------------------------------------------------------------------
    # Karten-Waechter (1.9.36)
    def _ks(self, ki: int) -> dict:
        e = self.karten_stand.get(ki)
        if e is None:
            e = self.karten_stand[ki] = {
                "status": "aktiv", "aufgabe": "", "letzte_ms": None,
                "letzte_zeit": 0.0, "aufrufe": 0, "fehler": 0, "grund": "",
                "gestoert_seit": 0.0, "naechster_versuch": 0.0,
                "_takt": [0.0, 0]}
        return e

    def karte_notiz(self, ki: int, aufgabe: str, ms: float = None) -> None:
        """Erfolgreichen Aufruf vermerken - Live-Stand fuer die Anzeige."""
        e = self._ks(ki)
        jetzt = time.time()
        war_gestoert = e["status"] == "gestoert"
        e["status"] = "aktiv"
        e["aufgabe"] = aufgabe
        e["letzte_zeit"] = jetzt
        if ms is not None:
            e["letzte_ms"] = round(float(ms), 2)
        e["aufrufe"] += 1
        t = e["_takt"]
        if jetzt - t[0] >= 1.0:
            e["aufrufe_s"] = t[1] / max(jetzt - t[0], 1e-3) if t[0] else 0.0
            t[0], t[1] = jetzt, 0
        t[1] += 1
        if war_gestoert:
            e["grund"] = ""
            e["gestoert_seit"] = 0.0
            cb = self.on_karte_fehler
            if cb:
                try:
                    cb(ki, "", True)
                except Exception:
                    pass

    def karte_gestoert(self, ki: int, grund: str) -> None:
        e = self._ks(ki)
        jetzt = time.time()
        neu = e["status"] != "gestoert"
        e["status"] = "gestoert"
        e["fehler"] += 1
        e["grund"] = str(grund)[:120]
        if neu:
            e["gestoert_seit"] = jetzt
        e["naechster_versuch"] = jetzt + float(self.karten_sperre_s)
        e["aufgabe"] = "gestoert - aus dem Verbund genommen"
        if neu:
            cb = self.on_karte_fehler
            if cb:
                try:
                    cb(ki, e["grund"], False)
                except Exception:
                    pass

    def karte_nutzbar(self, ki: int) -> bool:
        e = self.karten_stand.get(ki)
        if not e or e["status"] != "gestoert":
            return True
        return time.time() >= float(e.get("naechster_versuch", 0.0))

    def karten_uebersicht(self) -> Dict[int, dict]:
        aus = {}
        for ki, e in self.karten_stand.items():
            d = {k: v for k, v in e.items() if not k.startswith("_")}
            d["vor_s"] = (round(time.time() - e["letzte_zeit"], 1)
                          if e["letzte_zeit"] else None)
            aus[ki] = d
        return aus

    def _verbund_sieger(self, x: np.ndarray, C: int):
        """(Potential je Klasse, Sieger-Neuron) ueber alle Karten.

        Sieger-Neuron = (karte, index) des staerksten Neurons ueberhaupt -
        das ist der Schluessel fuer "Warum?": welches gelernte Beispiel
        hat gefeuert (2026-09-19).
        KARTEN-WAECHTER (1.9.36): eine Karte, die wirft, fliegt fuer eine
        Weile raus; die uebrigen antworten. Erst wenn KEINE mehr antwortet,
        geht der Fehler nach oben."""
        pots = None
        sieger = (0, 0, -1.0)                       # (karte, neuron, potential)
        letzter = None
        geantwortet = 0
        for ki, m in enumerate(self.modelle or [self.modell]):
            if not self.karte_nutzbar(ki):
                continue
            try:
                t0 = time.perf_counter()
                roh = np.asarray(m.forward(x))[0].ravel()
                ms = (time.perf_counter() - t0) * 1000.0
            except Exception as exc:
                letzter = exc
                self.karte_gestoert(ki, f"{type(exc).__name__}: {exc}")
                continue
            self.karte_notiz(ki, "Silhouetten-Abgleich", ms)
            geantwortet += 1
            je_klasse = roh.reshape(C, -1).max(axis=1).astype(float)
            pots = je_klasse if pots is None else np.maximum(pots, je_klasse)
            j = int(np.argmax(roh))
            if float(roh[j]) > sieger[2]:
                sieger = (ki, j, float(roh[j]))
        if pots is None:
            raise RuntimeError("keine Karte antwortet"
                               + (f": {letzter}" if letzter else ""))
        return pots, sieger

    # ------------------------------------------------------------------
    # "WARUM?" - Neuron -> Lernfoto (2026-09-19). Akida lernt Prototypen;
    # nach dem Lernen wird jedes Lernfoto einmal vorgelegt und dem Neuron
    # zugeordnet, das es am staerksten trifft. Beim Urteil zeigt das
    # Sieger-Neuron dann auf das echte Foto, das den Ausschlag gab.
    def neuron_karte_bauen(self, bilder_je_klasse, dateien_je_klasse) -> int:
        self.neuron_karte = {}
        if self.modell is None or not self.klassen:
            return 0
        C = len(self.klassen)
        n = 0
        try:
            for name in self.klassen:
                bilder = bilder_je_klasse.get(name) or []
                dateien = dateien_je_klasse.get(name) or []
                for i, b in enumerate(bilder):
                    datei = dateien[i] if i < len(dateien) else ""
                    if not datei:
                        continue
                    try:
                        if self.modus == "silhouette":
                            x = self._silhouette(b)[None, ...]
                        else:
                            x = self._aufbereiten(b)[None, ...]
                        _p, (ki, j, pot) = self._verbund_sieger(x, C)
                    except Exception:
                        continue
                    key = f"{ki}:{j}"
                    alt = self.neuron_karte.get(key)
                    if alt is None or pot > alt.get("pot", -1):
                        self.neuron_karte[key] = {"datei": datei, "klasse": name,
                                                  "pot": float(pot)}
                        n += 1
        except Exception:
            pass
        return len(self.neuron_karte)

    def warum(self, sieger) -> Optional[dict]:
        karte = getattr(self, "neuron_karte", None) or {}
        if not karte:
            return None
        ki, j, pot = sieger
        e = karte.get(f"{ki}:{j}")
        if not e:
            return None
        return {"datei": e["datei"], "klasse": e["klasse"],
                "karte": int(ki), "neuron": int(j), "potential": float(pot)}

    def _messwerk_an(self) -> None:
        """Leistungsmessung auf den eigenen Geraetehandles einschalten.

        Muss auf DIESEN Handles geschehen: das Messwerk eines fremden
        Handles auf dieselbe Karte sieht die Rechen-Ereignisse nicht -
        deshalb blieb die mW-Anzeige im Kartenfenster leer."""
        for g in (self.geraete or []):
            try:
                g.soc.power_measurement_enabled = True
            except Exception:
                pass

    def erkenne(self, bild: np.ndarray,
                maske: Optional[np.ndarray] = None) -> Optional[dict]:
        """Klassifiziert ein Bild. None, solange nichts gelernt wurde.

        `maske` grenzt bei beruehrenden Teilen ab, welcher Teil des Bildes
        gemeint ist - ohne sie wuerde die groesste zusammenhaengende Flaeche
        genommen, und das ist bei einem Klumpen der ganze Klumpen.
        """
        if self.modell is None or not self.klassen:
            self.letzter_fehler = "" if self.modell is None else "keine Klassen"
            return None
        with self._lock:
            try:
                C = len(self.klassen)
                # NUR die Kartendurchgaenge stoppen - das Freistellen und
                # Aufrichten davor ist Pi-CPU-Arbeit. Die Anzeige "Inferenz"
                # hat sonst 300 ms behauptet, wo die Karten wenige
                # Millisekunden gebraucht haben (2026-08-28).
                if self.modus == "silhouette":
                    x = self._silhouette(bild, maske)[None, ...]
                    t0 = time.perf_counter()
                    pro_klasse, sieger = self._verbund_sieger(x, C)
                    self.chip_ms_letzte = (time.perf_counter() - t0) * 1000.0
                else:
                    x = self._aufbereiten(bild)[None, ...]
                    t0 = time.perf_counter()
                    roh = np.asarray(self.modell.forward(x))[0].ravel()
                    self.chip_ms_letzte = (time.perf_counter() - t0) * 1000.0
                    pro_klasse = roh.reshape(C, -1).max(axis=1).astype(float)
                    j = int(np.argmax(roh))
                    sieger = (0, j, float(roh[j]))

                # UEBEREINSTIMMUNG statt Anteil. Der Anteil an der Summe
                # ueber alle Klassen kann bei vier Klassen kaum ueber 50 %
                # steigen, selbst wenn das Muster perfekt passt - die Zahl
                # sah deshalb immer schwach aus. Das Potential eines Neurons
                # zaehlt getroffene Verbindungen; geteilt durch num_weights
                # ist es der Anteil des gelernten Musters, der wirklich
                # wiedergefunden wurde. DIESE Zahl kann und soll ueber 90 %
                # liegen, wenn das Teil frei und sauber liegt.
                self.letzter_fehler = ""
                return self._urteil(x, pro_klasse, sieger)
                # (alte Urteilsbildung unten bleibt als Dokumentation der
                #  Herleitung stehen; sie ist in _urteil() uebernommen.)
                nw = max(int(getattr(self.bericht, "num_weights", 0) or 0), 1)
                # Ehrliche Normierung fuer TEILSTUECKE (2026-08-28): der
                # Nenner ist das Sichtbare, nicht die volle Schablone. Ein
                # C-foermiger Ringbogen hat nur ~60 % der Punkte einer
                # vollen Silhouette - relativ zur vollen Schablone war er
                # selbst bei perfekter Uebereinstimmung auf ~60 % gedeckelt
                # und riss die 55-%-Neuheitsschwelle nie. Untergrenze 35 %
                # der Schablone, damit winzige Stoerflecken nicht durch
                # einen kleinen Nenner gross gerechnet werden.
                probe_punkte = int((x > 0).sum())
                nenner = max(int(nw * 0.35), min(nw, probe_punkte), 8)
                wiederfindung = np.clip(pro_klasse / nenner, 0.0, 1.0)
                # ... UND die Gegenfrage (2026-08-28): wie viel von dem,
                # was ich SEHE, gehoert zur Schablone? Ohne sie hiess ein
                # Klumpen, der die SD-Karte ENTHAELT, selbst "SD Karte" -
                # obwohl die halbe Flaeche (der Karabiner samt Loch) gar
                # nicht dazugehoert. Das Minimum aus Wiederfindung und
                # Reinheit benennt nur, was die Silhouette auch ERKLAERT;
                # unerklaerte Klumpen bleiben unbenannt und gehen in die
                # Zerlegungs-Kaskade.
                reinheit = np.clip(pro_klasse / max(probe_punkte, 8),
                                   0.0, 1.0)
                anteile = self._kalibriere(np.minimum(wiederfindung, reinheit))
                beste = int(np.argmax(pro_klasse))
                self.letzter_fehler = ""

                # Unentschieden erkennen. Liegen alle Klassen gleichauf, ist
                # das KEINE Erkennung mit niedriger Sicherheit, sondern gar
                # keine - die Merkmale trennen die Objekte nicht. Als
                # "33 Prozent Karabiner" angezeigt sieht es aber aus wie ein
                # schwacher Treffer, und man sucht den Fehler beim Objekt.
                sortiert = np.sort(pro_klasse)[::-1]
                vorsprung = (float(sortiert[0] - sortiert[1]) / max(float(sortiert[0]), 1.0)
                             if len(sortiert) > 1 else 1.0)
                return {
                    "klasse": self.klassen[beste],
                    "sicherheit": float(anteile[beste]),
                    "vorsprung": round(vorsprung, 3),
                    "unklar": vorsprung < 0.05,
                    # Neuheitswaechter (Kartenplan 1b): "unklar" heisst
                    # "zwei Kandidaten liegen gleichauf" - RELATIV. Das hier
                    # ist ABSOLUT: selbst der beste Treffer findet kaum mehr
                    # als die Haelfte seiner Schablonenpunkte wieder. Dann
                    # ist das Teil nicht schlecht erkannt, sondern nie
                    # gelernt worden - und ein Produkt sagt "kenne ich
                    # nicht" statt selbstbewusst falsch zu liegen.
                    "unbekannt": float(anteile[beste]) < self.UNBEKANNT_AB,
                    # "Warum?": das Lernfoto hinter dem Sieger-Neuron.
                    "warum": self.warum(sieger),
                    "potentiale": [int(p) for p in pro_klasse],
                    "alle": [{"name": n, "anteil": float(a)}
                             for n, a in zip(self.klassen, anteile)],
                }
            except Exception as exc:
                # Den Grund NICHT verschlucken. Ein stilles None sieht in der
                # Oberflaeche genauso aus wie "nichts erkannt" - und dann sucht
                # man den Fehler beim Objekt statt beim Programm.
                self.letzter_fehler = f"{type(exc).__name__}: {str(exc)[:110]}"
                return None

    # ------------------------------------------------------------------
    # Gelerntes sichern und zurueckspielen.
    #
    # Der Lernstand liegt in den Gewichten der Lernschicht. Auf der Karte
    # sind sie fluechtig - beim Ausschalten weg, beim Neustart des Servers
    # ebenso. Ein `Model.save` schreibt sie samt Rumpf in eine .fbz; beim
    # Start wird die Datei geladen und wieder auf die Karte gelegt.
    #
    # Fuer den Bediener ist damit erledigt, was ihn zu Recht geaergert hat:
    # einmal angelernt bleibt angelernt. Technisch bleibt es ein Zurueck-
    # spielen, kein nichtfluechtiger Speicher auf dem Chip - deshalb dauert
    # der Start eine Sekunde laenger.
    DATEI = "chip_modell.fbz"
    BEGLEIT = "chip_modell.json"

    def _kartendatei(self, i: int) -> str:
        return f"chip_modell_{i}.fbz"

    def speichern(self, ordner) -> dict:
        from pathlib import Path
        modelle = self.modelle or ([self.modell] if self.modell else [])
        if not modelle or not self.klassen:
            return {"ok": False, "grund": "nichts gelernt"}
        p = Path(ordner)
        p.mkdir(parents=True, exist_ok=True)

        # Jede Karte des Verbunds einzeln sichern und sofort gegenpruefen.
        # Ein `save`, das ohne Fehler zurueckkommt, aber nichts Brauchbares
        # hinterlaesst, faellt sonst erst beim naechsten Neustart auf.
        gesamt_kb = 0.0
        for i, m in enumerate(modelle):
            ziel = p / self._kartendatei(i)
            try:
                m.save(str(ziel))
            except Exception as exc:
                return {"ok": False,
                        "grund": f"speichern Karte {i}: {str(exc)[:100]}"}
            if not ziel.exists() or ziel.stat().st_size < 1024:
                return {"ok": False, "grund": f"Datei fehlt oder leer ({ziel})"}
            try:
                probe = akida.Model(str(ziel))
                if len(probe.layers) != len(m.layers):
                    return {"ok": False, "grund": (
                        f"Karte {i}: {len(probe.layers)} statt "
                        f"{len(m.layers)} Schichten gespeichert")}
            except Exception as exc:
                return {"ok": False, "grund": (
                    f"Karte {i} nicht wieder lesbar: {str(exc)[:90]}")}
            gesamt_kb += ziel.stat().st_size / 1024
        # Alte Einzeldatei wegraeumen, damit kein veralteter Stand herumliegt.
        (p / self.DATEI).unlink(missing_ok=True)
        ziel = p / self._kartendatei(0)
        n_gespeichert = len(modelle)
        import json
        (p / self.BEGLEIT).write_text(json.dumps({
            "klassen": self.klassen,
            "groesse": self.groesse,
            "faktor": self._faktor,
            "formbild": self.formbild,
            "modus": self.modus,
            "verbund_modus": self.verbund_modus,
            "fingerabdruck": self.fingerabdruck,
            "bericht": self.bericht.as_dict() if self.bericht else None,
            "loch_klassen": getattr(self, "loch_klassen", {}),
            # "Warum?": Neuron -> Lernfoto, damit die Erklaerung auch nach
            # einem Neustart aus der Sicherung wieder da ist.
            "neuron_karte": getattr(self, "neuron_karte", {}) or {},
            # Lernstand-Version: wird das LERNVERFAHREN verbessert (nicht
            # nur die Fotos), zaehlt sie hoch - aeltere Sicherungen gelten
            # beim Start als veraltet und werden automatisch neu gelernt.
            # 2 = Negativklasse ohne Torso-Varianten + Loch-Signatur.
            "lernstand": self.LERNSTAND,
            "karten": len(modelle),
            "zeit": time.strftime("%Y-%m-%d %H:%M"),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, "datei": str(ziel),
                "kb": round(gesamt_kb, 1),
                "schichten": n_gespeichert}

    def laden(self, ordner, fingerabdruck: str = "") -> dict:
        """Spielt einen gesicherten Lernstand zurueck auf die Karten."""
        from pathlib import Path
        import json
        p = Path(ordner)
        if not (p / self.BEGLEIT).exists() or not (
                (p / self.DATEI).exists()
                or (p / self._kartendatei(0)).exists()):
            return {"ok": False, "grund": "kein gesicherter Lernstand"}
        try:
            begleit = json.loads((p / self.BEGLEIT).read_text(encoding="utf-8"))
        except Exception as exc:
            return {"ok": False, "grund": f"Begleitdatei: {str(exc)[:80]}"}

        # Haben sich die Fotos geaendert, ist der alte Stand ueberholt. Ihn
        # trotzdem zu laden waere die unangenehmste Sorte Fehler: die Karte
        # antwortet, aber auf Grundlage von Bildern, die es nicht mehr gibt.
        if fingerabdruck and begleit.get("fingerabdruck") != fingerabdruck:
            return {"ok": False, "veraltet": True,
                    "grund": "Fotos haben sich seit dem Sichern geaendert"}
        if (bool(begleit.get("formbild", False)) != self.formbild
                or begleit.get("modus", "merkmale") != self.modus):
            # Mit anderer Bilddarstellung gelernt als jetzt eingestellt -
            # der Stand wuerde laden, aber auf falschen Eingaben rechnen.
            return {"ok": False, "veraltet": True,
                    "grund": "mit anderer Bilddarstellung gesichert"}
        if int(begleit.get("lernstand", 1)) < self.LERNSTAND:
            # Mit aelterem Lernverfahren gesichert (z. B. noch mit
            # Stoerteil-Torsi oder ohne Loch-Signatur). Statt den Nutzer um
            # ein manuelles Chip-Lernen zu bitten, gilt der Stand als
            # veraltet - der Start lernt dann selbst neu und sichert.
            return {"ok": False, "veraltet": True,
                    "grund": f"Lernverfahren veraltet "
                             f"(Stand {begleit.get('lernstand', 1)} < "
                             f"{self.LERNSTAND})"}

        da, info = self.verfuegbar()
        if not da:
            return {"ok": False, "grund": info}
        karten = int(begleit.get("karten", 1))
        with self._lock:
            try:
                geraete = list(akida.devices()[:max(1, self.karten_max)])
                if len(geraete) < karten:
                    return {"ok": False, "veraltet": True, "grund": (
                        f"gesichert mit {karten} Karten, nutzbar nur "
                        f"{len(geraete)} (Detektor belegt eine) - es wird "
                        "neu gelernt")}
                self.geraete = list(geraete[:karten])
                self._messwerk_an()
                self.modelle = []
                for i in range(karten):
                    datei = p / (self._kartendatei(i) if karten > 1
                                 or (p / self._kartendatei(0)).exists()
                                 else self.DATEI)
                    m = akida.Model(str(datei))
                    m.map(self.geraete[i], hw_only=True)
                    self.modelle.append(m)
                self.modell = self.modelle[0]
                self.geraet = self.geraete[0]
            except Exception as exc:
                return {"ok": False, "grund": f"zurueckspielen: {str(exc)[:110]}"}
            self.klassen = list(begleit.get("klassen") or [])
            self._faktor = float(begleit.get("faktor", 1.0))
            self.fingerabdruck = begleit.get("fingerabdruck", "")
            self.loch_klassen = dict(begleit.get("loch_klassen") or {})
            self.neuron_karte = dict(begleit.get("neuron_karte") or {})
            if begleit.get("verbund_modus") in ("repliziert", "verteilt"):
                self.verbund_modus = begleit["verbund_modus"]
            b = begleit.get("bericht")
            if b:
                self.bericht = Lernbericht(
                    ok=True, klassen=self.klassen,
                    beispiele=int(b.get("beispiele", 0)),
                    ms_je_beispiel=float(b.get("ms_je_beispiel", 0)),
                    num_weights=int(b.get("num_weights", 0)),
                    neuronen_je_klasse=int(b.get("neuronen_je_klasse", 0)),
                    aktive_merkmale=float(b.get("aktive_merkmale", 0)),
                    dichte=float(b.get("dichte", 0)) / 100.0,
                    dichte_vorher=float(b.get("dichte_vorher", 0)) / 100.0,
                    ausduennen=str(b.get("ausduennen", "")),
                    treffer_eigen=float(b.get("treffer_eigen", 0)) / 100.0,
                    karten=int(b.get("karten", karten)),
                    aufgerichtet=int(b.get("aufgerichtet", 0)),
                    nicht_aufgerichtet=int(b.get("nicht_aufgerichtet", 0)),
                    verwechslung=b.get("verwechslung") or [],
                    warnungen=list(b.get("warnungen") or []),
                )
        return {"ok": True, "klassen": self.klassen,
                "gesichert": begleit.get("zeit", "")}

    def loeschen(self, ordner) -> None:
        from pathlib import Path
        namen = [self.DATEI, self.BEGLEIT] + [self._kartendatei(i)
                                              for i in range(4)]
        for name in namen:
            try:
                (Path(ordner) / name).unlink(missing_ok=True)
            except Exception:
                pass

    def verbund_info(self) -> dict:
        n = len(self.modelle) if self.modelle else (1 if self.modell else 0)
        return {"modus": self.verbund_modus, "karten": n,
                "replikation": bool(self.replikation),
                "nutzbar": [i for i in range(n) if self.karte_nutzbar(i)]}

    def vergessen(self) -> None:
        with self._lock:
            self.modell = None
            self.modelle = []
            self.klassen = []
            self.bericht = None
            self.letzter_fehler = ""

    def as_dict(self) -> dict:
        da, info = self.verfuegbar()
        return {
            "verfuegbar": da,
            "info": info,
            "gelernt": list(self.klassen),
            "bericht": self.bericht.as_dict() if self.bericht else None,
            "fehler": self.letzter_fehler,
            "herkunft": self.herkunft,
        }
