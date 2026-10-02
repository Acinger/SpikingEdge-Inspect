"""Darstellung: Konturen, gedrehte Rahmen, IDs, Verdeckungsgrad."""
from __future__ import annotations

from typing import List, Optional, Sequence

import cv2
import numpy as np

from . import config
from .detection import Detection, Occlusion

# BGR - dieselben Farben wie die Oberflaeche.
#   Gelb  = in Ordnung, freiliegend
#   Weiss = beruehrt, aber vollstaendig sichtbar
#   Bernstein = teilweise verdeckt, Form rekonstruiert
#   Rot   = nicht aufloesbar
COLOR_BY_OCCLUSION = {
    Occlusion.FREE: (0, 229, 255),
    Occlusion.TOUCHING: (244, 238, 233),
    Occlusion.PARTIAL: (32, 176, 255),
    Occlusion.UNRESOLVED: (90, 90, 255),
}
LABEL_BY_OCCLUSION = {
    Occlusion.FREE: "frei",
    Occlusion.TOUCHING: "beruehrt",
    Occlusion.PARTIAL: "verdeckt",
    Occlusion.UNRESOLVED: "unklar",
}


def draw(
    board: np.ndarray,
    dets: List[Detection],
    px_per_mm: float,
    class_names: Sequence[str] = config.CLASS_NAMES,
    show_contour: bool = True,
    show_mm: bool = True,
    show_box: bool = True,
    show_axis: bool = True,
    show_label: bool = True,
    show_legend: bool = True,
    font_ref: Optional[int] = None,
) -> np.ndarray:
    """Zeichnet die Erkennung ins Bild.

    Die Schalter sind nicht Zierde. Auf einem kleinen Display verdecken
    Beschriftungen bei sechs Teilen mehr, als sie erklaeren - und wer die
    Trennung zweier beruehrender Teile beurteilen will, braucht die Konturen
    ohne alles andere. Beide Ansichten zeigen dieselben Daten, nur verschieden
    dicht.
    """
    canvas = board.copy() if board.ndim == 3 else cv2.cvtColor(board, cv2.COLOR_GRAY2BGR)

    for d in dets:
        # Ampellogik nach der Design-Vorlage (2026-08-28): GRUEN = benannt,
        # ROT = unbekannt/unklar/unaufloesbar. Die Verdeckung steht als Wort
        # am Rahmen - sie bekommt keine eigene Farbe mehr.
        GRUEN, ROT = (94, 197, 34), (68, 68, 239)
        benannt = (0 <= d.class_id < len(class_names)
                   and class_names[d.class_id] != "unbekannt"
                   and d.occlusion != Occlusion.UNRESOLVED)
        color = GRUEN if benannt else ROT

        # Bewusst UNgeglaettet: der Versuch mit gleitendem Mittelwert sah in
        # der Praxis schlechter aus als die rohen Konturen (Rueckmeldung vom
        # 2026-08-27). _glatt bleibt fuer spaeter erhalten, wird aber nicht
        # benutzt.
        if show_contour and d.contour is not None:
            cv2.drawContours(canvas, [d.contour.astype(np.int32)], -1, color, 1,
                             cv2.LINE_AA)

        pts = d.box.corners().astype(np.int32)
        if show_box:
            # Duenne Kante, massive Ecken - dieselbe Bauform wie der
            # Aufnahmerahmen. Ein 2 px starkes Rechteck um ein kleines Teil
            # verdeckt genau die Kanten, die man beurteilen will.
            if d.occlusion in (Occlusion.PARTIAL, Occlusion.UNRESOLVED):
                # Verdeckte Teile gestrichelt: die ergaenzte Kante ist eine
                # Rekonstruktion, keine Beobachtung. Das muss sichtbar sein.
                _dashed_poly(canvas, pts, color, 1)
            else:
                cv2.polylines(canvas, [pts], True, color, 1, cv2.LINE_AA)
            _corner_ticks(canvas, pts, color)

        if show_axis:
            c = np.array([d.box.cx, d.box.cy])
            ang = np.radians(d.box.angle)
            half = 0.5 * d.box.length * np.array([np.cos(ang), np.sin(ang)])
            cv2.line(canvas, tuple((c - half).astype(int)),
                     tuple((c + half).astype(int)), color, 1, cv2.LINE_AA)

        if show_label:
            # Nur beschriften, was eine Aussage traegt. cv2.putText kann
            # ausserdem nur ASCII - ein Gradzeichen wird zu "??", und genau
            # das stand dann im Bild. Der Normalfall "frei" bleibt unbe-
            # schriftet: was ueberall dransteht, sagt nichts.
            teile = []
            if 0 <= d.class_id < len(class_names):
                # Quellen-Kuerzel im Label (g=Geometrie, m=verschmolzen,
                # a=Detektor): beendet das Raten am Bildschirmfoto, welcher
                # Pfad einen Kasten erzeugt hat (2026-08-28).
                teile.append(f"{class_names[d.class_id]} "
                             f"{d.class_score*100:.0f}% "
                             f"[{(d.source or '?')[:1]}]")
            # "beruehrt" ist keine Stoerung, sondern Alltag - nur die beiden
            # echten Problemlagen werden angeschrieben.
            if d.occlusion in (Occlusion.PARTIAL, Occlusion.UNRESOLVED):
                teile.append(LABEL_BY_OCCLUSION.get(d.occlusion, "?"))
            if show_mm:
                l_mm = d.box.length / px_per_mm
                w_mm = d.box.width / px_per_mm
                teile.append(f"{l_mm:.0f}x{w_mm:.0f}mm {d.box.angle:.0f}Grad")
            if teile:
                _label(canvas, "  ".join(teile), pts.min(axis=0), color,
                       font_ref)

    if show_legend:
        _legend(canvas, dets, font_ref)
    return canvas


def _glatt(kontur: np.ndarray, staerke: float = 0.02) -> np.ndarray:
    """Glaettet eine geschlossene Kontur fuer die Anzeige.

    Die Konturen stammen aus einer verkleinerten Suchfassung und werden
    hochskaliert - jede Maskenstufe wird dabei zur sichtbaren Treppe. Ein
    gleitender Mittelwert RINGSUM (die Kontur ist geschlossen, Anfang und
    Ende sind Nachbarn) buegelt die Stufen weg, ohne Ecken wegzurunden:
    die Fensterbreite waechst mit der Punktzahl, bleibt aber klein.

    Nur fuer die ANZEIGE - Messwerte rechnen weiter auf dem Original.
    """
    p = np.asarray(kontur).reshape(-1, 2).astype(np.float64)
    n = len(p)
    if n < 12:
        return np.asarray(kontur).astype(np.int32)
    k = max(3, int(n * staerke) | 1)
    kern = np.ones(k) / k
    aus = np.empty_like(p)
    for achse in (0, 1):
        # Ringsum falten: vorn und hinten mit dem jeweils anderen Ende
        # verlaengern, dann die Mitte behalten.
        w = np.concatenate([p[-k:, achse], p[:, achse], p[:k, achse]])
        aus[:, achse] = np.convolve(w, kern, mode="same")[k:k + n]
    return np.rint(aus).astype(np.int32).reshape(-1, 1, 2)


def _corner_ticks(img, pts, color, anteil: float = 0.22, dicke: int = 2):
    """Kurze kraeftige Striche an den vier Ecken des gedrehten Rechtecks."""
    n = len(pts)
    for i in range(n):
        p = pts[i].astype(float)
        for nachbar in (pts[(i + 1) % n], pts[(i - 1) % n]):
            richtung = nachbar.astype(float) - p
            laenge = np.linalg.norm(richtung)
            if laenge < 4:
                continue
            ziel = p + richtung * min(anteil, 8.0 / laenge if laenge > 36 else anteil)
            cv2.line(img, tuple(p.astype(int)), tuple(ziel.astype(int)),
                     color, dicke, cv2.LINE_AA)


def _dashed_poly(img, pts, color, thickness=2, dash=8):
    n = len(pts)
    for i in range(n):
        p, q = pts[i].astype(float), pts[(i + 1) % n].astype(float)
        seg = np.linalg.norm(q - p)
        if seg < 1e-6:
            continue
        steps = max(int(seg // dash), 1)
        for s in range(0, steps, 2):
            a = p + (q - p) * (s / steps)
            b = p + (q - p) * (min(s + 1, steps) / steps)
            cv2.line(img, tuple(a.astype(int)), tuple(b.astype(int)), color, thickness)


def _schrift(img, ref: Optional[int] = None) -> float:
    """Schriftgroesse im Verhaeltnis zum Bild.

    Feste Pixelgroessen waren der Fehler: dasselbe 0,4er Mass sieht auf einem
    640er Bild riesig aus und auf einem 1600er winzig. `ref` erlaubt, die
    GESAMTE Anzeige als Massstab zu nehmen, wenn nur in einen Ausschnitt
    davon gezeichnet wird - sonst waechst die Schrift im kleinen Ausschnitt
    ins Riesige.
    """
    # Obergrenze 0.95: seit die Erkennung auf einer 640er-Fassung zeichnet,
    # die danach fuers Livebild verkleinert wird, muss die Schrift VOR der
    # Verkleinerung entsprechend groesser sein (ref wird hochgerechnet).
    return max(0.34, min(0.95, (ref or img.shape[1]) / 3300.0))


def _label(img, text, anchor, color, ref: Optional[int] = None):
    """Gefuellter Beschriftungs-Chip in Rahmenfarbe - wie die Vorlage
    (2026-08-28). Textfarbe nach Helligkeit des Chips: dunkel auf Gruen,
    weiss auf Rot."""
    s = _schrift(img, ref)
    x, y = int(anchor[0]), int(anchor[1]) - 8
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, s, 1)
    y = max(y, th + 10)
    cv2.rectangle(img, (x - 4, y - th - 6), (x + tw + 5, y + 5),
                  color, -1, cv2.LINE_AA)
    luma = 0.114 * color[0] + 0.587 * color[1] + 0.299 * color[2]
    schrift = (12, 24, 10) if luma > 120 else (255, 255, 255)
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, s,
                schrift, 1, cv2.LINE_AA)


def _legend(img, dets: List[Detection], ref: Optional[int] = None):
    """Zaehlung in EINER Zeile, unten links.

    Der Normalfall "frei" wird nicht aufgezaehlt - "1 Teile  frei 1" hat
    dasselbe zweimal gesagt und dabei auch noch falsch dekliniert.
    """
    counts = {}
    for d in dets:
        if d.occlusion != Occlusion.FREE:
            counts[d.occlusion] = counts.get(d.occlusion, 0) + 1
    text = f"{len(dets)} " + ("Teil" if len(dets) == 1 else "Teile")
    if counts:
        text += "   " + "   ".join(
            f"{LABEL_BY_OCCLUSION.get(k, '?')} {v}" for k, v in sorted(counts.items()))
    s = _schrift(img, ref)
    y = img.shape[0] - int(10 * s / 0.4)
    cv2.putText(img, text, (9, y + 1), cv2.FONT_HERSHEY_SIMPLEX, s,
                (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(img, text, (8, y), cv2.FONT_HERSHEY_SIMPLEX, s,
                (0, 229, 255), 1, cv2.LINE_AA)


def draw_mask_debug(mask: np.ndarray, part_masks: List[np.ndarray]) -> np.ndarray:
    """Farbige Darstellung der Einzelteil-Masken - fuer die Watershed-Kontrolle."""
    out = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
    rng = np.random.default_rng(7)
    for m in part_masks:
        col = rng.integers(60, 255, size=3).tolist()
        out[m > 0] = col
    return out
