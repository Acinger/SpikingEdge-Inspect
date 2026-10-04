"""Selbstlernende Zelle (SE Inspect 1.1-A): Vorschlaege aus unbekannten Teilen.

Jedes als UNBEKANNT gebuchte Teil liegt mit Bild im Pruef-Archiv
(<daten>/ergebnisse/*_unbekannt.jpg). Hier werden diese Bilder nach Form und
Farbe gruppiert: aehnliche Teile landen in derselben Gruppe. Jede Gruppe ist
ein Vorschlag - "das hier kam 7-mal vor und war jedesmal unbekannt".
Der Mensch entscheidet: neues Objekt, zu einem vorhandenen Objekt, Hintergrund
oder verwerfen. Danach "Training …" - Sekunden auf dem Chip.

Bewusst einfach und nachpruefbar: keine Bibliothek, keine Zufallsinitialisierung.
Merkmale je Bild (alle in [0..1] skaliert, dann gewichtet):
  - Form: Hu-Momente 1-4 (log), Seitenverhaeltnis, Fuellgrad (Solidity), Ausdehnung
  - Groesse: Flaeche relativ zum Bild
  - Farbe: mittlerer Farbton (Kreis -> sin/cos), Saettigung, Helligkeit
Gruppierung: agglomerativ mit mittlerer Verknuepfung bis zu einer Distanzgrenze.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

# Hu 1-4 (Betrag, log) - die hoeheren Momente kippen bei Drehung/Spiegelung das
# Vorzeichen und rauschen; Seitenverhaeltnis, Fuellgrad, Ausdehnung sind die
# stabilsten Formmerkmale und zaehlen deshalb doppelt.
GEWICHT = np.array([1.0] * 4 + [2.0, 2.0, 1.5, 1.0] + [0.6, 0.6, 0.5, 0.4], dtype=np.float32)


def maske(bild: np.ndarray) -> Optional[np.ndarray]:
    """Groesster Vordergrund-Umriss: Hintergrund = Randfarbe des Bildausschnitts."""
    if bild is None or bild.size == 0:
        return None
    g = cv2.GaussianBlur(cv2.cvtColor(bild, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    rand = np.concatenate([g[0, :], g[-1, :], g[:, 0], g[:, -1]])
    hg = float(np.median(rand))
    diff = cv2.absdiff(g, np.full_like(g, int(hg)))
    # zusaetzlich Farbabstand (Teile gleicher Helligkeit wie der Hintergrund)
    lab = cv2.cvtColor(cv2.GaussianBlur(bild, (5, 5), 0), cv2.COLOR_BGR2LAB).astype(np.int16)
    rand_lab = np.concatenate([lab[0, :], lab[-1, :], lab[:, 0], lab[:, -1]])
    ref = np.median(rand_lab, axis=0)
    fdiff = np.clip(np.abs(lab[..., 1:] - ref[1:]).sum(axis=2), 0, 255).astype(np.uint8)
    d = cv2.max(diff, fdiff)
    _, m = cv2.threshold(d, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    kont, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not kont:
        return None
    k = max(kont, key=cv2.contourArea)
    if cv2.contourArea(k) < 0.002 * m.size:
        return None
    aus = np.zeros_like(m)
    cv2.drawContours(aus, [k], -1, 255, -1)
    return aus


def merkmale(bild: np.ndarray) -> Optional[np.ndarray]:
    m = maske(bild)
    if m is None:
        return None
    kont, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    k = max(kont, key=cv2.contourArea)
    flaeche = cv2.contourArea(k)
    hu = cv2.HuMoments(cv2.moments(k)).flatten()
    hu = np.array([-math.log10(abs(h)) if h != 0 else 12.0 for h in hu[:4]])
    hu = np.clip(hu / 12.0, 0.0, 1.0)                        # grob auf [0..1]
    (_, _), (bw, bh), _ = cv2.minAreaRect(k)
    seiten = min(bw, bh) / max(bw, bh, 1e-6)
    huelle = cv2.contourArea(cv2.convexHull(k))
    solid = flaeche / max(huelle, 1e-6)
    x, y, w, h = cv2.boundingRect(k)
    ausd = flaeche / max(w * h, 1e-6)
    groesse = math.sqrt(flaeche / m.size)
    hsv = cv2.cvtColor(bild, cv2.COLOR_BGR2HSV)
    sel = m > 0
    hue = hsv[..., 0][sel].astype(np.float32) * (2 * math.pi / 180.0)
    sat = float(hsv[..., 1][sel].mean()) / 255.0
    val = float(hsv[..., 2][sel].mean()) / 255.0
    # Farbton nur so stark gewichten, wie Farbe da ist (grau = kein Farbton)
    hs, hc = float(np.sin(hue).mean()) * sat, float(np.cos(hue).mean()) * sat
    v = np.concatenate([hu, [seiten, solid, ausd, groesse, hs, hc, sat, val]]).astype(np.float32)
    return v * GEWICHT


def gruppieren(vektoren: List[np.ndarray], grenze: float = 0.7) -> List[List[int]]:
    """Agglomerativ, mittlere Verknuepfung, bis der kleinste Abstand > grenze.
    Lance-Williams-Aktualisierung: O(n^2) je Schritt statt O(n^2) Gruppenpaare
    mit Teilmatrix-Mittelwert - 300 Bilder in Millisekunden statt Minuten."""
    n = len(vektoren)
    if n == 0:
        return []
    X = np.stack(vektoren).astype(np.float64)
    D = np.sqrt(((X[:, None, :] - X[None, :, :]) ** 2).sum(axis=2))
    np.fill_diagonal(D, np.inf)
    groesse = np.ones(n)
    mitglieder = {i: [i] for i in range(n)}
    aktiv = np.ones(n, dtype=bool)
    while aktiv.sum() > 1:
        k = int(np.argmin(D))
        i, j = divmod(k, n)
        if not np.isfinite(D[i, j]) or D[i, j] > grenze:
            break
        if j < i:
            i, j = j, i
        neu = (groesse[i] * D[i] + groesse[j] * D[j]) / (groesse[i] + groesse[j])
        D[i, :] = neu
        D[:, i] = neu
        D[i, i] = np.inf
        D[j, :] = np.inf
        D[:, j] = np.inf
        D[~aktiv, i] = np.inf
        D[i, ~aktiv] = np.inf
        groesse[i] += groesse[j]
        mitglieder[i] += mitglieder.pop(j)
        aktiv[j] = False
    return sorted((sorted(m) for m in mitglieder.values()), key=lambda g: (-len(g), g[0]))


_CACHE: dict = {}


def merkmale_datei(pfad: Path) -> Optional[np.ndarray]:
    """Merkmale eines Archivbilds, im Speicher gemerkt (Datei aendert sich nie)."""
    try:
        sch = (str(pfad), pfad.stat().st_mtime)
    except OSError:
        return None
    if sch in _CACHE:
        return _CACHE[sch]
    b = cv2.imread(str(pfad))
    v = merkmale(b) if b is not None else None
    if len(_CACHE) > 4000:
        _CACHE.clear()
    _CACHE[sch] = v
    return v


def vorschlaege(ordner: Path, dateien: List[str], min_groesse: int = 2, grenze: float = 0.7,
                bekannte: Optional[dict] = None) -> dict:
    """dateien: Archivbilder (unbekannt). bekannte: {name: [merkmalsvektoren]} der
    gelernten Objekte - fuer den Hinweis "aehnelt am ehesten X"."""
    vek, gueltig, ohne = [], [], []
    for d in dateien:
        v = merkmale_datei(Path(ordner) / d)
        if v is None:
            ohne.append(d)
            continue
        vek.append(v)
        gueltig.append(d)
    gr = gruppieren(vek, grenze)
    aus = []
    for g in gr:
        if len(g) < min_groesse:
            continue
        mitte = np.mean([vek[i] for i in g], axis=0)
        rep = min(g, key=lambda i: float(np.linalg.norm(vek[i] - mitte)))
        streu = float(np.mean([np.linalg.norm(vek[i] - mitte) for i in g]))
        aehnlich = None
        if bekannte:
            best = None
            for name, vs in bekannte.items():
                if not vs:
                    continue
                dist = float(min(np.linalg.norm(mitte - v) for v in vs))
                if best is None or dist < best[1]:
                    best = (name, dist)
            if best and best[1] < grenze * 1.2:
                aehnlich = {"name": best[0], "abstand": round(best[1], 3)}
        aus.append({"anzahl": len(g), "dateien": [gueltig[i] for i in g], "bild": gueltig[rep],
                    "streuung": round(streu, 3), "aehnlich": aehnlich})
    einzel = sum(1 for g in gr if len(g) < min_groesse)
    return {"gruppen": aus, "bilder": len(dateien), "ohne_umriss": len(ohne), "einzeln": einzel, "grenze": grenze}
