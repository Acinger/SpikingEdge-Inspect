"""Trainingsszenen aus den gesammelten Fotos bauen.

Das Chip-Lernen kommt mit einzelnen Ausschnitten aus. VORSA-M3 nicht: der
Detektor soll mehrere Objekte finden, auch wenn sie sich beruehren oder
ueberdecken. Solche Bilder entstehen beim Sammeln aber nicht - dort liegt
jedes Teil einzeln und formatfuellend im Rahmen.

Deshalb werden die Szenen hier zusammengesetzt: jedes Foto wird freigestellt
und dann mehrfach, gedreht und teilweise ueberlappend, auf eine Leinwand
gelegt. Der Gewinn ist nicht die Bildmenge, sondern dass die Beschriftung
dabei exakt bekannt ist. Wer echte Ueberlappungsbilder von Hand beschriftet,
raet bei genau der Groesse, auf die es ankommt: wo das verdeckte Teil endet.
Hier ist sie gesetzt, weil wir das Teil selbst dorthin gelegt haben.

Ehrliche Grenze: die Teile werden flach eingesetzt. Schattenwurf,
gegenseitige Beleuchtung und echte Verformung fehlen. Ein so trainiertes
Modell ist ein Anfang, kein Ersatz fuer Bilder von der Anlage.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import cv2
import numpy as np

from .assignment import GtObject

_K3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
_K5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))


@dataclass
class Freigestellt:
    """Ein aus seinem Foto herausgeloestes Teil."""

    bild: np.ndarray        # (h, w, 3) eng um das Teil zugeschnitten
    maske: np.ndarray       # (h, w) uint8, 255 = Teil
    laenge: float           # lange Seite in px
    breite: float           # kurze Seite in px
    winkel: float           # Grad, 0..180, Richtung der langen Seite
    klasse: int
    hintergrund: Tuple[int, int, int]


# ----------------------------------------------------------------------
def freistellen(bild: np.ndarray, klasse: int,
                min_anteil: float = 0.005,
                max_anteil: float = 0.95) -> Optional[Freigestellt]:
    """Loest das Teil vom Hintergrund.

    Der Hintergrund wird am Bildrand gemessen, nicht geraten. Beim Sammeln
    liegt das Teil in der Mitte des Rahmens - der Rand zeigt also fast immer
    die Unterlage.

    None, wenn nichts Brauchbares gefunden wurde. Das ist der wichtigere
    Rueckgabewert: ein halb erfasstes Teil erzeugt eine falsche Beschriftung,
    und eine falsche Beschriftung ist schlimmer als ein fehlendes Bild.
    """
    if bild is None or bild.ndim != 3:
        return None
    h, w = bild.shape[:2]
    if h < 16 or w < 16:
        return None

    grau = cv2.cvtColor(bild, cv2.COLOR_BGR2GRAY)
    rand = np.concatenate([grau[0, :], grau[-1, :], grau[:, 0], grau[:, -1]])
    hg_grau = int(np.median(rand))

    diff = cv2.absdiff(grau, np.full_like(grau, hg_grau))
    _, maske = cv2.threshold(diff, 0, 255,
                             cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    # FARBBEWUSST (2026-09-12), gleiche Logik wie segmentation.foreground_
    # mask: was sich FARBLICH klar von der Randfarbe abhebt, ist Teil -
    # auch wenn es im Grau gleich hell ist (schwarze Karte auf gruenem
    # Band). Schwelle aus dem Rauschen des Rands, nicht Otsu. Damit sehen
    # Anlernen und Live-Erkennung DASSELBE Teil - vorher lernte der Chip
    # nur die weisse Aufschrift und erkannte die ganze Karte live nicht.
    try:
        from .segmentation import farbmaske_lokal
        # Oertliches Bandmodell (Vignette der Pi-Kamera, 2026-09-19) -
        # dieselbe Funktion wie live, sonst lernt der Chip etwas anderes,
        # als er spaeter sieht.
        m_farbe = farbmaske_lokal(bild, 5, 12.0)
        if m_farbe is None:
            lab = cv2.cvtColor(bild, cv2.COLOR_BGR2LAB).astype(np.float32)
            lab = cv2.GaussianBlur(lab, (5, 5), 0)
            rand3 = np.concatenate([lab[0, :], lab[-1, :],
                                    lab[:, 0], lab[:, -1]]).reshape(-1, 3)
            hg3 = np.median(rand3, axis=0)
            d_rand = np.sqrt(((rand3 - hg3) ** 2).sum(axis=1))
            p99 = float(np.percentile(d_rand, 99)) if d_rand.size else 0.0
            t_f = max(12.0, 1.6 * p99 + 4.0)
            dist = np.sqrt(((lab - hg3) ** 2).sum(axis=2))
            m_farbe = (dist > t_f).astype(np.uint8) * 255
            if m_farbe.mean() >= 0.55 * 255:
                m_farbe = None
        if m_farbe is not None:
            maske = cv2.bitwise_or(maske, m_farbe)
    except Exception:
        pass
    # Kanten-Silhouette wie in der Live-Segmentierung (2026-09-19).
    try:
        from .segmentation import _kanten_silhouette
        innen = _kanten_silhouette(bild)
        if innen is not None:
            maske = cv2.bitwise_or(maske, innen)
    except Exception:
        pass
    # Blendflecken wie live ausschliessen - sonst lernt der Chip Lampen.
    try:
        from .segmentation import glanzmaske
        from .config import DEFAULT
        g = glanzmaske(bild, int(getattr(DEFAULT.seg, "glanz_schwelle", 246)),
                       float(getattr(DEFAULT.seg, "glanz_max_anteil", 0.02)))
        if g is not None:
            maske[g > 0] = 0
    except Exception:
        pass
    maske = cv2.morphologyEx(maske, cv2.MORPH_OPEN, _K3, iterations=2)
    maske = cv2.morphologyEx(maske, cv2.MORPH_CLOSE, _K5, iterations=2)

    # RETR_CCOMP statt RETR_EXTERNAL: Loecher muessen Loecher bleiben.
    # Mit EXTERNAL wurde die groesste Kontur voll ausgemalt - ein Ring wurde
    # dadurch zur Scheibe, und zwei Teile mit gleichem Umriss waren nicht
    # mehr zu unterscheiden. Genau daran ist die Formbild-Pruefung am
    # 2026-08-27 gescheitert.
    konturen, hierarchie = cv2.findContours(maske, cv2.RETR_CCOMP,
                                            cv2.CHAIN_APPROX_SIMPLE)
    if not konturen:
        return None
    aussen = [i for i in range(len(konturen))
              if hierarchie[0][i][3] == -1]
    gi = max(aussen, key=lambda i: cv2.contourArea(konturen[i]))
    grosse = konturen[gi]
    flaeche = float(cv2.contourArea(grosse))
    if not (min_anteil * h * w < flaeche < max_anteil * h * w):
        return None

    (cx, cy), (rw, rh), winkel = cv2.minAreaRect(grosse)
    if rw < 4 or rh < 4:
        return None
    if rw >= rh:
        laenge, breite, ang = rw, rh, winkel
    else:
        laenge, breite, ang = rh, rw, winkel + 90.0

    # Nur die groesste Kontur behalten - Staub und Spiegelungen sonst mit.
    # Ihre Loecher wieder austragen, aber nur nennenswerte: winzige stammen
    # meist von Glanzpunkten, nicht von der Form.
    sauber = np.zeros_like(maske)
    cv2.drawContours(sauber, [grosse], -1, 255, cv2.FILLED)
    for i in range(len(konturen)):
        if (hierarchie[0][i][3] == gi
                and cv2.contourArea(konturen[i]) > 0.01 * flaeche):
            cv2.drawContours(sauber, [konturen[i]], -1, 0, cv2.FILLED)

    x, y, bw, bh = cv2.boundingRect(grosse)
    x, y = max(0, x - 2), max(0, y - 2)
    bw, bh = min(w - x, bw + 4), min(h - y, bh + 4)

    hg = bild.reshape(-1, 3)[np.repeat((maske == 0).ravel(), 1)]
    hg_farbe = (tuple(int(v) for v in np.median(hg, axis=0))
                if len(hg) else (hg_grau, hg_grau, hg_grau))

    return Freigestellt(
        bild=np.ascontiguousarray(bild[y:y + bh, x:x + bw]),
        maske=np.ascontiguousarray(sauber[y:y + bh, x:x + bw]),
        laenge=float(laenge), breite=float(breite), winkel=float(ang % 180.0),
        klasse=int(klasse), hintergrund=hg_farbe)


# ----------------------------------------------------------------------
def _drehe_teil(t: Freigestellt, winkel: float, faktor: float
                ) -> Tuple[np.ndarray, np.ndarray, float, float, float]:
    """Dreht und skaliert ein freigestelltes Teil.

    Die Winkelmitfuehrung ist dieselbe wie in augment.py: das Bild wird um
    `winkel` gedreht, der Objektwinkel wird deshalb um `winkel` KLEINER.
    Ein Vorzeichenfehler faellt bei 90 Grad nicht auf, weil +90 und -90 modulo
    180 gleich sind - genau daran ist es hier schon einmal vorbeigerutscht.
    """
    h, w = t.maske.shape[:2]
    ecke = int(round(np.hypot(h, w) * faktor)) + 4
    M = cv2.getRotationMatrix2D((w / 2, h / 2), winkel, faktor)
    M[0, 2] += ecke / 2 - w / 2
    M[1, 2] += ecke / 2 - h / 2

    bild = cv2.warpAffine(t.bild, M, (ecke, ecke), flags=cv2.INTER_LINEAR,
                          borderValue=t.hintergrund)
    maske = cv2.warpAffine(t.maske, M, (ecke, ecke), flags=cv2.INTER_NEAREST,
                           borderValue=0)
    return (bild, maske, t.laenge * faktor, t.breite * faktor,
            (t.winkel - winkel) % 180.0)


def _einsetzen(leinwand: np.ndarray, bild: np.ndarray, maske: np.ndarray,
               mx: int, my: int) -> None:
    """Setzt ein Teil an (mx, my) ein - Mittelpunkt, mit Beschnitt am Rand."""
    H, W = leinwand.shape[:2]
    h, w = maske.shape[:2]
    x0, y0 = mx - w // 2, my - h // 2
    zx0, zy0 = max(0, x0), max(0, y0)
    zx1, zy1 = min(W, x0 + w), min(H, y0 + h)
    if zx1 <= zx0 or zy1 <= zy0:
        return
    qx0, qy0 = zx0 - x0, zy0 - y0
    q_maske = maske[qy0:qy0 + (zy1 - zy0), qx0:qx0 + (zx1 - zx0)]
    q_bild = bild[qy0:qy0 + (zy1 - zy0), qx0:qx0 + (zx1 - zx0)]
    ziel = leinwand[zy0:zy1, zx0:zx1]
    ziel[q_maske > 0] = q_bild[q_maske > 0]


# ----------------------------------------------------------------------
def baue_szene(teile: Sequence[Freigestellt], px: int, rng: np.random.Generator,
               min_objekte: int = 1, max_objekte: int = 6,
               p_ueberlappung: float = 0.65,
               ziel_anteil: Tuple[float, float] = (0.10, 0.35),
               ) -> Tuple[np.ndarray, List[GtObject]]:
    """Legt mehrere Teile auf eine Leinwand und gibt die Beschriftung zurueck.

    `ziel_anteil` ist die lange Seite eines Teils als Anteil der Bildkante.
    Zu grosse Teile passen sonst in keine Rasterzelle, zu kleine verschwinden.
    """
    hg = np.median(np.array([t.hintergrund for t in teile]), axis=0)
    leinwand = np.full((px, px, 3), hg, dtype=np.uint8)
    # Etwas Rauschen: eine vollkommen glatte Flaeche kommt in der Anlage nicht
    # vor, und ein Modell, das nie Rauschen gesehen hat, stolpert darueber.
    rausch = rng.normal(0, 4, (px, px, 3))
    leinwand = np.clip(leinwand.astype(np.float32) + rausch, 0, 255).astype(np.uint8)

    n = int(rng.integers(min_objekte, max_objekte + 1))
    objekte: List[GtObject] = []
    platziert: List[Tuple[int, int, float]] = []

    for _ in range(n):
        t = teile[int(rng.integers(0, len(teile)))]
        anteil = float(rng.uniform(*ziel_anteil))
        faktor = (px * anteil) / max(t.laenge, 1.0)
        faktor = float(np.clip(faktor, 0.05, 4.0))
        winkel = float(rng.uniform(0, 180))
        bild, maske, laenge, breite, ang = _drehe_teil(t, winkel, faktor)

        rand = int(laenge / 2)
        if platziert and rng.random() < p_ueberlappung:
            # Bewusst dicht an ein vorhandenes Teil - das ist der Fall, fuer
            # den M3 gebaut wurde. Ohne ihn trainieren die Slots 2 und 3 nie.
            ax, ay, al = platziert[int(rng.integers(0, len(platziert)))]
            # Untergrenze 0.05 statt 0.25 (2026-08-28): mit dem alten
            # Mindestabstand gab es NIE satt aufeinanderliegende Teile im
            # Training - und genau dort sassen die Detektorkaesten im
            # Betrieb windschief. Jetzt kommen auch fast deckungsgleiche
            # Lagen vor; die Slots desselben Rasterfelds sind dafuer da.
            abstand = float(rng.uniform(0.05, 0.85)) * (al + laenge) / 2
            richtung = float(rng.uniform(0, 2 * np.pi))
            mx = int(ax + np.cos(richtung) * abstand)
            my = int(ay + np.sin(richtung) * abstand)
        else:
            mx = int(rng.integers(rand, max(rand + 1, px - rand)))
            my = int(rng.integers(rand, max(rand + 1, px - rand)))
        mx = int(np.clip(mx, 4, px - 4))
        my = int(np.clip(my, 4, px - 4))

        _einsetzen(leinwand, bild, maske, mx, my)
        objekte.append(GtObject(cx=float(mx), cy=float(my), width=float(laenge),
                                height=float(breite), angle=float(ang),
                                class_id=int(t.klasse)))
        platziert.append((mx, my, laenge))

    return leinwand, objekte


def baue_stapel(teile: Sequence[Freigestellt], anzahl: int, px: int,
                seed: int = 0, **kw) -> Tuple[np.ndarray, List[List[GtObject]]]:
    rng = np.random.default_rng(seed)
    bilder, listen = [], []
    for _ in range(anzahl):
        b, o = baue_szene(teile, px, rng, **kw)
        bilder.append(b)
        listen.append(o)
    return np.stack(bilder).astype(np.uint8), listen


# ----------------------------------------------------------------------
FREISTELL_MAX_PX = 384     # das Modell sieht 256 px - mehr kostet nur Zeit


def freistellen_aus_zustand(zustand, mit_varianten: bool = True,
                            fortschritt=None
                            ) -> Tuple[List[Freigestellt], List[str], List[str]]:
    """Stellt alle gesammelten Fotos frei.

    Rueckgabe: (Teile, Klassennamen in Reihenfolge der Kennung, Warnungen).
    fortschritt(i, n): je Foto, fuer die Anzeige.

    1.9.71: NUR Original + Spiegelungen. Drehvarianten brachten fuer M3
    nichts - baue_szene dreht und skaliert jedes Teil ohnehin zufaellig -
    kosteten aber das 8- bis 32-Fache an Zeit (auf dem Pi Dutzende Minuten
    ohne sichtbaren Fortschritt). Bilder vorher auf FREISTELL_MAX_PX.
    """
    from .assignment import GtObject as _G          # noqa: F401  (Doku)
    from .augment import erzeuge_varianten, AugmentConfig

    namen: List[str] = []
    teile: List[Freigestellt] = []
    warnungen: List[str] = []
    klassen = sorted(zustand.klassen.values(), key=lambda x: x.id)
    n_fotos = sum(len(k.prototypen) for k in klassen)
    i_foto = 0

    for idx, k in enumerate(klassen):
        namen.append(k.name)
        gefunden = 0
        for datei in k.prototypen:
            i_foto += 1
            if fortschritt is not None:
                try:
                    fortschritt(i_foto, n_fotos)
                except Exception:
                    pass
            roh = zustand.prototyp_bild(datei)
            if roh is None:
                continue
            h, w = roh.shape[:2]
            if max(h, w) > FREISTELL_MAX_PX:
                f = FREISTELL_MAX_PX / float(max(h, w))
                roh = cv2.resize(roh, (max(16, int(w * f)), max(16, int(h * f))),
                                 interpolation=cv2.INTER_AREA)
                h, w = roh.shape[:2]
            quellen = [roh]
            if mit_varianten:
                a = k.augment
                nur_spiegel = AugmentConfig(
                    spiegeln_horizontal=bool(getattr(a, "spiegeln_horizontal", True)),
                    spiegeln_vertikal=bool(getattr(a, "spiegeln_vertikal", False)),
                    drehen_90=False, drehen_frei=False,
                    haendigkeit=bool(getattr(a, "haendigkeit", False)))
                platz = [GtObject(w / 2, h / 2, w * .6, h * .3, 0.0, idx)]
                quellen = [b for _n, b, _o in erzeuge_varianten(roh, platz, nur_spiegel)]
            for b in quellen:
                t = freistellen(b, idx)
                if t is not None:
                    teile.append(t)
                    gefunden += 1
        if gefunden == 0 and k.prototypen:
            warnungen.append(
                f"Bei „{k.name}“ liess sich in keinem Foto ein Teil vom "
                "Hintergrund trennen - zu wenig Kontrast oder das Teil fuellt "
                "den Rahmen ganz aus.")
        elif not k.prototypen:
            warnungen.append(f"„{k.name}“ hat noch keine Fotos.")

    return teile, namen, warnungen
