"""Hypothesen bei Beruehrung und Ueberlappung (SE Inspect 1.0, A3).

Eine zusammenhaengende Vordergrundflaeche mit mehreren Stuecken hat
mehrere Deutungen. Bisher entschied `_verschmelze` im Server das Schritt
fuer Schritt (Ganzes gegen Stuecke, dann Vereinigungen). Hier werden die
Deutungen zuerst als HYPOTHESEN aufgezaehlt, dann ALLE noetigen
Chip-Bewertungen in einem Rutsch angefordert (das ist die Stelle, an der
der Kartenverteiler sie parallel auf die Karten legt), und zuletzt wird
die konsistenteste Gesamterklaerung gewaehlt.

Hypothesen je Flaeche:
  ganz           ein Teil (die Wasserscheide hat faelschlich zerschnitten)
  stuecke        die Stuecke, wie die Wasserscheide sie geliefert hat
  zerlegung      Rechteckzerlegung mit Sollmass (fitting.decompose_overlap)
  paar:i+j       zwei benachbarte Stuecke vereint, der Rest einzeln

Bewertung:  score = mittlere Uebereinstimmung der Teile
                    - 0.03 je zusaetzlichem Teil (Sparsamkeit)
                    * geometrische Plausibilitaet (Sollmasse, wenn bekannt)
Ein unbenennbares Teil zaehlt mit 0.3, nicht 0: "zwei Teile, eines
unbekannt" darf ein benanntes Ganzes nicht automatisch schlagen - und
umgekehrt darf ein unbenennbares Ganzes benannte Stuecke nicht schlucken
(Regel aus _verschmelze, 2026-08-28).

Rein geometrisch und in numpy/OpenCV; der Chip kommt nur ueber die
Funktion `bewerte_viele` herein - deshalb laesst sich alles ohne Karte
benchen.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from .detection import Detection, Occlusion, OrientedBox

# Eine Bewertung: (Uebereinstimmung 0..1, Chip-Ergebnis oder None)
Bewertung = Optional[Tuple[float, Optional[dict]]]
# bewerte_viele([(box, kontur), ...]) -> [Bewertung, ...] in derselben Reihenfolge
BewerteViele = Callable[[List[Tuple[OrientedBox, Optional[np.ndarray]]]], List[Bewertung]]

UNBEKANNT_WERT = 0.30      # Beitrag eines unbenennbaren Teils
JE_TEIL_ABZUG = 0.03       # Sparsamkeit: jedes weitere Teil kostet etwas
BENANNT_AB = 0.55          # darunter gilt ein Teil als unbenennbar


@dataclass
class Teil:
    box: OrientedBox
    kontur: Optional[np.ndarray]
    quelle: str = ""                 # "stueck" | "ganz" | "zerlegung" | "paar"
    bewertung: Bewertung = None
    herkunft: List[int] = field(default_factory=list)   # Indizes der Stuecke


@dataclass
class Hypothese:
    name: str
    teile: List[Teil]
    score: float = -1.0
    geometrie: float = 1.0
    details: dict = field(default_factory=dict)


# ----------------------------------------------------------------------
def _kontur_aus_masken(leinwand_shape, polys: Sequence[np.ndarray]):
    """Vereinigung mehrerer Polygone -> (Aussenkontur, Box)."""
    leinwand = np.zeros(leinwand_shape[:2], np.uint8)
    for p in polys:
        cv2.fillPoly(leinwand, [np.asarray(p).reshape(-1, 2).astype(np.int32)], 255)
    leinwand = cv2.morphologyEx(leinwand, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    kk, _ = cv2.findContours(leinwand, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not kk:
        return None, None
    sk = max(kk, key=cv2.contourArea)
    return sk, OrientedBox.from_cv_rect(cv2.minAreaRect(sk))


def _poly(d: Detection) -> np.ndarray:
    return d.contour if d.contour is not None else d.box.corners()


def _abstand(a: Detection, b: Detection) -> float:
    return float(np.hypot(a.box.cx - b.box.cx, a.box.cy - b.box.cy))


def hypothesen_erzeugen(stuecke: List[Detection], flaechen_shape,
                        px_per_mm: float = 0.0,
                        blob_maske: Optional[np.ndarray] = None,
                        zerlegung_max: int = 4,
                        zerlegung_min_fit: float = 0.72,
                        nominal: bool = False) -> List[Hypothese]:
    """Alle Deutungen einer zusammenhaengenden Flaeche mit >= 2 Stuecken."""
    hyps: List[Hypothese] = []
    n = len(stuecke)
    if n == 0:
        return hyps

    # H ganz
    sk, sbox = _kontur_aus_masken(flaechen_shape, [_poly(d) for d in stuecke])
    if sbox is not None:
        hyps.append(Hypothese("ganz", [Teil(sbox, sk, "ganz", herkunft=list(range(n)))]))

    # H stuecke (nur bei mehreren)
    if n >= 2:
        hyps.append(Hypothese("stuecke", [Teil(d.box, d.contour, "stueck", herkunft=[i])
                                          for i, d in enumerate(stuecke)]))

    # H paar: zwei Stuecke vereint, der Rest einzeln (nur bei >= 3 Stuecken
    # sinnvoll - bei zweien ist das schon "ganz"). Bis vier Stuecke alle
    # Paare (ein zerschnittener Ring hat seine Haelften weit auseinander),
    # darueber die drei naechsten.
    if n >= 3:
        paare = sorted(((_abstand(stuecke[i], stuecke[j]), i, j)
                        for i in range(n) for j in range(i + 1, n)))
        for _, i, j in (paare if n <= 4 else paare[:3]):
            pk, pbox = _kontur_aus_masken(flaechen_shape, [_poly(stuecke[i]), _poly(stuecke[j])])
            if pbox is None:
                continue
            teile = [Teil(pbox, pk, "paar", herkunft=[i, j])]
            teile += [Teil(d.box, d.contour, "stueck", herkunft=[k])
                      for k, d in enumerate(stuecke) if k not in (i, j)]
            hyps.append(Hypothese(f"paar:{i}+{j}", teile))

    # H zerlegung (Sollmass) - nur im Nominal-Modus mit bekannter Teilegroesse.
    # Auch bei EINEM Stueck: ueberlappende Teile trennt die Wasserscheide
    # nicht, die Flaeche verraet sie trotzdem.
    if nominal and blob_maske is not None and px_per_mm > 0:
        try:
            from .fitting import decompose_overlap
            pieces = decompose_overlap(blob_maske, px_per_mm, max_parts=zerlegung_max,
                                       min_fit_score=zerlegung_min_fit)
            if len(pieces) >= 2:
                hyps.append(Hypothese("zerlegung", [Teil(b, c, "zerlegung") for b, c, _v, _d in pieces],
                                      details={"sichtbar": [round(v, 2) for _b, _c, v, _d in pieces]}))
        except Exception:
            pass
    return hyps


# ----------------------------------------------------------------------
def _plausibilitaet(teile: List[Teil], px_per_mm: float,
                    soll_masse: Optional[Sequence[Tuple[float, float]]]) -> float:
    """Wie gut passen die Teilmasse zu bekannten Sollmassen (L x B in mm)?
    1.0 ohne Sollmasse; sonst Mittel ueber die Teile von
    exp(-|log(ratio)|) der besten Sollgroesse (0.7 bei 1.4-facher Abweichung)."""
    if not soll_masse or px_per_mm <= 0:
        return 1.0
    werte = []
    for t in teile:
        L = max(t.box.length, t.box.width) / px_per_mm
        B = min(t.box.length, t.box.width) / px_per_mm
        best = 0.0
        for sl, sb in soll_masse:
            sl, sb = max(sl, sb), min(sl, sb)
            r = abs(np.log(max(L, 1e-3) / max(sl, 1e-3))) + abs(np.log(max(B, 1e-3) / max(sb, 1e-3)))
            best = max(best, float(np.exp(-r)))
        werte.append(best)
    return float(np.mean(werte)) if werte else 1.0


def hypothesen_bewerten(hyps: List[Hypothese], bewerte_viele: BewerteViele,
                        px_per_mm: float = 0.0,
                        soll_masse: Optional[Sequence[Tuple[float, float]]] = None) -> Optional[Hypothese]:
    """Alle Teile aller Hypothesen EINMAL bewerten lassen, dann waehlen."""
    if not hyps:
        return None
    # Auftraege einsammeln (gleiche Stuecke in mehreren Hypothesen nur einmal)
    auftraege: List[Tuple[OrientedBox, Optional[np.ndarray]]] = []
    schluessel: Dict[Tuple, int] = {}
    verweise: List[List[int]] = []
    for h in hyps:
        idx = []
        for t in h.teile:
            k = (t.quelle, tuple(t.herkunft)) if t.herkunft else (id(t),)
            if k not in schluessel:
                schluessel[k] = len(auftraege)
                auftraege.append((t.box, t.kontur))
            idx.append(schluessel[k])
        verweise.append(idx)
    ergebnisse = list(bewerte_viele(auftraege)) if auftraege else []
    while len(ergebnisse) < len(auftraege):
        ergebnisse.append(None)

    beste = None
    for h, idx in zip(hyps, verweise):
        werte = []
        for t, i in zip(h.teile, idx):
            t.bewertung = ergebnisse[i]
            w = t.bewertung[0] if t.bewertung is not None else 0.0
            werte.append(w if w >= BENANNT_AB else UNBEKANNT_WERT)
        h.geometrie = _plausibilitaet(h.teile, px_per_mm, soll_masse)
        h.score = (float(np.mean(werte)) - JE_TEIL_ABZUG * (len(h.teile) - 1)) * h.geometrie
        h.details["werte"] = [round(x, 3) for x in werte]
        if beste is None or h.score > beste.score + 1e-9:
            beste = h
    return beste


def hypothese_zu_detektionen(h: Hypothese, vorlage: List[Detection]) -> List[Detection]:
    """Gewaehlte Hypothese -> Detektionen (mit Chip-Ergebnis in meta['chip'])."""
    out = []
    mehrere = len(h.teile) > 1
    for t in h.teile:
        basis = vorlage[t.herkunft[0]] if t.herkunft else vorlage[0]
        d = Detection(box=t.box, contour=t.kontur, score=basis.score,
                      occlusion=basis.occlusion, source=("merged" if t.quelle != "stueck" else basis.source),
                      meta=dict(basis.meta))
        if t.bewertung is not None and t.bewertung[1] is not None:
            d.meta["chip"] = t.bewertung[1]
        d.meta["hypothese"] = h.name
        if mehrere:
            d.occlusion = max(d.occlusion, Occlusion.TOUCHING)
        out.append(d)
    return out


# ----------------------------------------------------------------------
def _beruehren(a: Detection, b: Detection, shape, rand: int = 9) -> bool:
    """Liegen zwei Stuecke aneinander (nach leichter Aufweitung)?"""
    la = np.zeros(shape[:2], np.uint8); lb = np.zeros(shape[:2], np.uint8)
    cv2.fillPoly(la, [np.asarray(_poly(a)).reshape(-1, 2).astype(np.int32)], 255)
    cv2.fillPoly(lb, [np.asarray(_poly(b)).reshape(-1, 2).astype(np.int32)], 255)
    k = np.ones((rand, rand), np.uint8)
    return bool(cv2.countNonZero(cv2.bitwise_and(cv2.dilate(la, k), lb)))


def _cluster(indizes: List[int], stuecke: List[Detection], shape) -> List[List[int]]:
    """Zusammenhangskomponenten unter den gegebenen Stuecken (Beruehrung)."""
    rest = list(indizes); out = []
    while rest:
        grp = [rest.pop(0)]
        i = 0
        while i < len(grp):
            for j in list(rest):
                if _beruehren(stuecke[grp[i]], stuecke[j], shape):
                    grp.append(j); rest.remove(j)
            i += 1
        out.append(sorted(grp))
    return out


def _vereinigung(stuecke: List[Detection], idx: List[int], shape, quelle: str) -> Optional[Teil]:
    k, b = _kontur_aus_masken(shape, [_poly(stuecke[i]) for i in idx])
    return Teil(b, k, quelle, herkunft=sorted(idx)) if b is not None else None


def hypothesen_waehlen(stuecke: List[Detection], flaechen_shape, bewerte_viele: BewerteViele,
                       px_per_mm: float = 0.0, blob_maske: Optional[np.ndarray] = None,
                       nominal: bool = False, soll_masse=None,
                       zerlegung_max: int = 4, zerlegung_min_fit: float = 0.72) -> Tuple[Optional[Hypothese], dict]:
    """Zwei Bewertungsrunden, beide parallelisierbar:

    Runde 1: Stuecke einzeln, das Ganze, Rechteckzerlegung.
    Runde 2: aus den Einzelergebnissen Vereinigungen ableiten - alles, was
             allein unbenennbar ist, wird (je Beruehrungscluster und
             insgesamt) vereint, wahlweise zusammen mit einem angrenzenden
             benannten Stueck; bei <= 3 Stuecken zusaetzlich alle Paare.
    Gewinner: hoechster Score ueber beide Runden."""
    info = {"runden": 0, "auftraege": 0, "hypothesen": 0}
    if not stuecke:
        return None, info
    hyps = hypothesen_erzeugen(stuecke, flaechen_shape, px_per_mm, blob_maske=blob_maske,
                               zerlegung_max=zerlegung_max, zerlegung_min_fit=zerlegung_min_fit,
                               nominal=nominal)
    # Paare in Runde 1 nur bei wenigen Stuecken - sonst Runde 2 entscheiden lassen
    hyps = [h for h in hyps if not h.name.startswith("paar") or len(stuecke) <= 3]
    zaehl = _Zaehler(bewerte_viele)
    beste = hypothesen_bewerten(hyps, zaehl, px_per_mm, soll_masse)
    info["runden"] = 1
    n = len(stuecke)
    if n >= 2:
        st = next((h for h in hyps if h.name == "stuecke"), None)
        werte = [t.bewertung[0] if t.bewertung else 0.0 for t in st.teile] if st else [0.0] * n
        unben = [i for i, w in enumerate(werte) if w < BENANNT_AB]
        benannt = [i for i in range(n) if i not in unben]
        neue: List[Hypothese] = []

        def mit_rest(vereint: List[List[int]], name: str):
            teile = []
            drin = set()
            for idx in vereint:
                v = _vereinigung(stuecke, idx, flaechen_shape, "vereint")
                if v is None:
                    return
                teile.append(v); drin |= set(idx)
            teile += [Teil(stuecke[i].box, stuecke[i].contour, "stueck", herkunft=[i])
                      for i in range(n) if i not in drin]
            if 1 <= len(teile) < n:
                neue.append(Hypothese(name, teile))

        if len(unben) >= 2:
            cl = _cluster(unben, stuecke, flaechen_shape)
            if len(cl) > 1 or len(cl[0]) < len(unben):
                mit_rest(cl, "vereint:cluster")
            mit_rest([unben], "vereint:unbekannt")
            # plus je ein angrenzendes benanntes Stueck (ein Ringbogen kann
            # allein schon "Ring" heissen und gehoert trotzdem dazu)
            for b in benannt:
                if any(_beruehren(stuecke[b], stuecke[u], flaechen_shape) for u in unben):
                    mit_rest([unben + [b]], f"vereint:unbekannt+{b}")
        elif len(unben) == 1 and benannt:
            # ein einzelnes unbenennbares Stueck: an jedes angrenzende
            # benannte Stueck probeweise anfuegen
            for b in benannt:
                if _beruehren(stuecke[b], stuecke[unben[0]], flaechen_shape):
                    mit_rest([[unben[0], b]], f"vereint:{unben[0]}+{b}")
        # "ein benanntes Stueck ist ein Teil, alles andere zusammen das
        # zweite" - fuer jedes benannte Stueck (die Wasserscheide schneidet
        # gern ein Stueck des Nachbarn mit ab, dann ist keine reine
        # Vereinigung richtig, aber diese kommt der Wahrheit am naechsten)
        if n >= 3:
            for b in sorted(benannt, key=lambda i: -werte[i])[:2]:
                mit_rest([[i for i in range(n) if i != b]], f"vereint:rest-ohne:{b}")
        # gleiche Klasse zusammen (drei Boegen heissen alle "Ring")
        klassen: Dict[str, List[int]] = {}
        if st:
            for i, t in enumerate(st.teile):
                if t.bewertung and t.bewertung[1] and werte[i] >= BENANNT_AB:
                    klassen.setdefault(str(t.bewertung[1].get("klasse")), []).append(i)
        for kname, idx in klassen.items():
            if len(idx) >= 2:
                mit_rest([idx], f"vereint:klasse:{kname}")
                if unben:
                    mit_rest([idx + unben], f"vereint:klasse+unbekannt:{kname}")
        # schon bewertete Namen nicht doppelt
        vorhanden = {tuple(sorted(tuple(t.herkunft) for t in h.teile)) for h in hyps}
        neue = [h for h in neue if tuple(sorted(tuple(t.herkunft) for t in h.teile)) not in vorhanden]
        if neue:
            b2 = hypothesen_bewerten(neue, zaehl, px_per_mm, soll_masse)
            info["runden"] = 2
            hyps += neue
            if b2 is not None and (beste is None or b2.score > beste.score + 1e-9):
                beste = b2
    info["auftraege"] = zaehl.auftraege
    info["hypothesen"] = len(hyps)
    info["scores"] = sorted(((round(h.score, 3), h.name) for h in hyps), reverse=True)[:6]
    return beste, info


class _Zaehler:
    def __init__(self, f):
        self.f = f; self.auftraege = 0; self.runden = 0

    def __call__(self, auftraege):
        self.auftraege += len(auftraege); self.runden += 1
        return self.f(auftraege)


def sequentiell(bewerte: Callable) -> BewerteViele:
    """Rueckfall ohne Verteiler: Auftraege nacheinander bewerten."""
    def viele(auftraege):
        return [bewerte(b, k) for b, k in auftraege]
    return viele
