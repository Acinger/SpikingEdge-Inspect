"""Objekte vor dem Lernen aufrichten.

Der Merkmalsextraktor der Karte hat ZUFAELLIGE Gewichte - er ist nicht
trainiert. Solche Merkmale unterscheiden grobe Form, Flaeche und Helligkeit,
aber sie sind nicht drehinvariant, nicht groesseninvariant und nicht
unempfindlich gegen Hintergrund. Wer ihm ein Teil einmal quer und einmal
laengs zeigt, zeigt ihm aus seiner Sicht zwei verschiedene Dinge.

Statt dem Netz beizubringen, davon abzusehen - was ein trainierter Rumpf
koennte und dieser nicht -, wird die Schwankung vorher entfernt:

    freistellen  ->  aufrichten  ->  zentrieren  ->  auf Format bringen

Damit sieht die Karte dasselbe Teil immer gleich. Das ist derselbe Gedanke
wie in crops.py fuer den Kroppklassifikator, nur fuer das Chip-Lernen.

Ehrliche Grenze: was die Geometrie nicht findet, kann sie auch nicht
aufrichten. Bei zu wenig Kontrast liefert `aufrichten` None, und der Aufrufer
muss entscheiden - das Rohbild nehmen oder das Foto verwerfen. Stillschweigend
etwas Halbes zurueckzugeben waere hier das Schlechteste: es sieht aus wie ein
gutes Lernbild und ist keines.
"""
from __future__ import annotations

from typing import Optional, Tuple

import cv2
import numpy as np

from .dataset_build import freistellen


def aufrichten(bild: np.ndarray, groesse: int = 128, rand: float = 0.12,
               hintergrund: int = 0, form: bool = False,
               vorgabe_maske: Optional[np.ndarray] = None) -> Optional[np.ndarray]:
    """Stellt das Teil frei, dreht es waagerecht und fuellt das Format.

    `rand` laesst ringsum etwas Luft, damit die Aussenkante nicht am
    Bildrand klebt - dort schneiden die Faltungen sie an.
    None, wenn kein Teil gefunden wurde.
    """
    if vorgabe_maske is not None:
        # Die Maske kommt von aussen - von der Wasserscheide, die weiss,
        # welcher Teil des Klumpens zu DIESEM Teil gehoert. Selbst
        # freizustellen waere hier falsch: freistellen() nimmt die groesste
        # zusammenhaengende Flaeche, und bei beruehrenden Teilen ist das der
        # ganze Klumpen. Genau so bekamen am 2026-08-27 beide Teile dieselbe
        # Silhouette und damit denselben Namen.
        t = _aus_maske(bild, vorgabe_maske)
    else:
        t = freistellen(bild, 0)
    if t is None:
        return None

    h, w = t.maske.shape[:2]
    # Um den gemessenen Winkel zurueckdrehen, dann liegt die lange Seite
    # waagerecht. Vorzeichen wie in augment.py: Bild um `winkel` drehen macht
    # den Objektwinkel um `winkel` kleiner.
    ecke = int(round(np.hypot(h, w))) + 4
    M = cv2.getRotationMatrix2D((w / 2, h / 2), -t.winkel, 1.0)
    M[0, 2] += ecke / 2 - w / 2
    M[1, 2] += ecke / 2 - h / 2
    gedreht = cv2.warpAffine(t.bild, M, (ecke, ecke), flags=cv2.INTER_LINEAR,
                             borderValue=t.hintergrund)
    maske = cv2.warpAffine(t.maske, M, (ecke, ecke), flags=cv2.INTER_NEAREST,
                           borderValue=0)

    xs = np.flatnonzero(maske.any(axis=0))
    ys = np.flatnonzero(maske.any(axis=1))
    if xs.size < 2 or ys.size < 2:
        return None
    x0, x1, y0, y1 = xs[0], xs[-1] + 1, ys[0], ys[-1] + 1

    teil = gedreht[y0:y1, x0:x1]
    tmaske = maske[y0:y1, x0:x1]

    # 180-Grad-Mehrdeutigkeit aufloesen.
    #
    # minAreaRect kennt nur Winkel bis 180 Grad - ein Schraubenzieher mit
    # Griff links und einer mit Griff rechts sind fuer die Geometrie
    # derselbe Winkel. Nach dem Aufrichten liegt derselbe Gegenstand dann
    # mal so und mal so herum, und fuer das Netz sind das zwei verschiedene
    # Dinge. Genau daran ist die Gegenprobe am 2026-08-27 gescheitert.
    #
    # Aufgeloest ueber den Schwerpunkt: die schwerere Haelfte kommt immer
    # nach links, die schwerere Haelfte quer immer nach oben. Bei einem
    # symmetrischen Teil ist die Wahl beliebig - dann ist sie aber auch egal.
    teil, tmaske = _seite_festlegen(teil, tmaske)

    # Auf neutralen Grund setzen: der Hintergrund darf nicht mitlernen. Ein
    # Objekt, das immer auf derselben Unterlage fotografiert wurde, brachte
    # sonst die Unterlage als Merkmal mit.
    frei = np.full(teil.shape, hintergrund, dtype=np.uint8)
    frei[tmaske > 0] = teil[tmaske > 0]

    th, tw = frei.shape[:2]
    innen = int(groesse * (1.0 - 2 * rand))
    f = min(innen / max(tw, 1), innen / max(th, 1))
    zielmass = (max(1, int(round(tw * f))), max(1, int(round(th * f))))
    neu = cv2.resize(frei, zielmass, interpolation=cv2.INTER_AREA)

    ox = (groesse - neu.shape[1]) // 2
    oy = (groesse - neu.shape[0]) // 2

    if not form:
        leinwand = np.full((groesse, groesse, 3), hintergrund, dtype=np.uint8)
        leinwand[oy:oy + neu.shape[0], ox:ox + neu.shape[1]] = neu
        return leinwand

    # Formbild: die Gestalt AUSDRUECKLICH als die drei Bildkanaele, statt zu
    # hoffen, dass ein untrainierter Merkmalsextraktor sie aus Farben errraet.
    #
    #   Kanal 1  Silhouette      wo das Teil ist
    #   Kanal 2  Kanten          Umriss und Binnenkanten (Loch, Klinge, Clip)
    #   Kanal 3  Dickenverlauf   Abstand zum Rand - unterscheidet einen Ring
    #                            von einer Scheibe mit GLEICHEM Umriss
    #
    # Farbe und Textur fallen bewusst weg: sie haengen an Belichtung und
    # Weissabgleich, die Form nicht.
    m8 = cv2.resize(tmaske, zielmass, interpolation=cv2.INTER_NEAREST)
    grau = cv2.cvtColor(neu, cv2.COLOR_BGR2GRAY)
    # Kanten verbreitern und weichzeichnen: eine 1-px-Canny-Linie springt
    # von Ansicht zu Ansicht um einzelne Pixel, und im Vergleich zaehlt das
    # wie ein Unterschied. Breit und weich liegt dieselbe Kante wieder auf
    # sich selbst.
    kanten = cv2.Canny(grau, 60, 160)
    kanten[m8 == 0] = 0
    kanten = cv2.dilate(kanten, np.ones((3, 3), np.uint8))
    kanten = cv2.GaussianBlur(kanten, (5, 5), 0)
    # Kanten gedaempft: sie sind der unruhigste der drei Kanaele (gemessen
    # Trennschaerfe 1,24 gegen 1,85 der Silhouette). Halb so laut tragen sie
    # ihre Information bei, ohne die ruhigen Kanaele zu uebertoenen.
    kanten = (kanten * 0.5).astype(np.uint8)
    dist = cv2.distanceTransform((m8 > 0).astype(np.uint8), cv2.DIST_L2, 3)
    if dist.max() > 0:
        dist = dist / dist.max() * 255.0

    leinwand = np.zeros((groesse, groesse, 3), dtype=np.uint8)
    ziel = leinwand[oy:oy + neu.shape[0], ox:ox + neu.shape[1]]
    ziel[..., 0] = np.where(m8 > 0, 255, 0)
    ziel[..., 1] = kanten
    ziel[..., 2] = dist.astype(np.uint8)
    return leinwand


def _aus_maske(bild: np.ndarray, maske: np.ndarray):
    """Baut das Freistellergebnis aus einer vorgegebenen Maske."""
    from .dataset_build import Freigestellt
    m = (np.asarray(maske) > 0).astype(np.uint8) * 255
    if m.shape[:2] != bild.shape[:2] or int(m.sum()) < 20 * 255:
        return None
    konturen, _ = cv2.findContours(m, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    if not konturen:
        return None
    grosse = max(konturen, key=cv2.contourArea)
    (cx, cy), (rw, rh), winkel = cv2.minAreaRect(grosse)
    if rw < 4 or rh < 4:
        return None
    if rw >= rh:
        laenge, breite, ang = rw, rh, winkel
    else:
        laenge, breite, ang = rh, rw, winkel + 90.0
    x, y, bw, bh = cv2.boundingRect(grosse)
    x, y = max(0, x - 2), max(0, y - 2)
    bw = min(bild.shape[1] - x, bw + 4)
    bh = min(bild.shape[0] - y, bh + 4)
    grau = cv2.cvtColor(bild, cv2.COLOR_BGR2GRAY) if bild.ndim == 3 else bild
    rand = np.concatenate([grau[0, :], grau[-1, :], grau[:, 0], grau[:, -1]])
    hg = int(np.median(rand))
    return Freigestellt(
        bild=np.ascontiguousarray(bild[y:y + bh, x:x + bw]),
        maske=np.ascontiguousarray(m[y:y + bh, x:x + bw]),
        laenge=float(laenge), breite=float(breite), winkel=float(ang % 180.0),
        klasse=0, hintergrund=(hg, hg, hg))


def _seite_festlegen(teil: np.ndarray, maske: np.ndarray
                     ) -> Tuple[np.ndarray, np.ndarray]:
    """Spiegelt so, dass der Schwerpunkt immer links oben liegt."""
    h, w = maske.shape[:2]
    m = (maske > 0).astype(np.float64)
    summe = m.sum()
    if summe < 1:
        return teil, maske

    sx = float((m.sum(axis=0) * np.arange(w)).sum() / summe) / max(w - 1, 1)
    if sx > 0.5:
        teil, maske = cv2.flip(teil, 1), cv2.flip(maske, 1)
        m = (maske > 0).astype(np.float64)
    sy = float((m.sum(axis=1) * np.arange(h)).sum() / summe) / max(h - 1, 1)
    if sy > 0.5:
        teil, maske = cv2.flip(teil, 0), cv2.flip(maske, 0)
    return teil, maske


def aufrichten_oder_roh(bild: np.ndarray, groesse: int = 128,
                        form: bool = False,
                        vorgabe_maske: Optional[np.ndarray] = None
                        ) -> Tuple[np.ndarray, bool]:
    """Wie `aufrichten`, faellt aber auf das skalierte Rohbild zurueck.

    Der zweite Rueckgabewert sagt, welcher Weg genommen wurde - damit der
    Bericht ausweisen kann, wie viele Bilder nicht aufgerichtet werden
    konnten. Eine Mischung aus beidem ist naemlich schlechter als beides
    einzeln: das Netz sieht dann zwei verschiedene Darstellungen desselben
    Objekts.
    """
    aus = aufrichten(bild, groesse, form=form, vorgabe_maske=vorgabe_maske)
    if aus is not None:
        return aus, True
    roh = cv2.resize(bild, (groesse, groesse), interpolation=cv2.INTER_AREA)
    if roh.ndim == 2:
        roh = cv2.cvtColor(roh, cv2.COLOR_GRAY2BGR)
    if form:
        # Notbehelf in derselben Darstellung: Kanten des Rohbilds in Kanal 2,
        # damit wenigstens die Kanaele dieselbe Bedeutung behalten.
        grau = cv2.cvtColor(roh, cv2.COLOR_BGR2GRAY)
        aus = np.zeros_like(roh)
        aus[..., 1] = cv2.Canny(grau, 60, 160)
        return np.ascontiguousarray(aus), False
    return np.ascontiguousarray(roh.astype(np.uint8)), False
