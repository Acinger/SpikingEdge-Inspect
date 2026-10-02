"""Hintergrundtrennung und Trennung beruehrender Teile (Fall 1).

Ablauf:
  Bild -> Vordergrundmaske -> zusammenhaengende Flaechen (Blobs)
       -> je Blob: enthaelt er ein oder mehrere Teile?
       -> mehrere: Distanztransformation + Watershed
       -> Ausgabe: eine Maske je Einzelteil
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import cv2
import numpy as np

from . import config
from .config import SegmentationParams


# ----------------------------------------------------------------------
def farbmaske_lokal(bild: np.ndarray, k: int = 5,
                    min_abstand: float = 12.0) -> Optional[np.ndarray]:
    """Farbmaske gegen ein OERTLICHES Hintergrundmodell (2026-09-19, 2).

    Vorher: EINE Bandfarbe (Median des Bildrands) fuer das ganze Bild.
    Die Pi-Kamera hat aber eine deutliche Randabdunklung (Vignette): Mitte
    hell, Ecken dunkel. Dann streut der Rand stark (hohes 99. Perzentil),
    die Schwelle wird gross, und eine schwarze Karte auf dunkelgruenem
    Band liegt darunter - nur die weisse Aufschrift bleibt ueber der
    Schwelle. Ergebnis: drei Etiketten-Rahmen statt einer Karte.

    Jetzt: das Band wird je Pixel geschaetzt - eine glatte Flaeche 4.
    Ordnung je Lab-Kanal, robust ueber das ganze Bild gefittet (Start am
    Randring, Toleranz sinkt ueber fuenf Runden auf das reine Rauschen;
    Teile fallen als Ausreisser heraus). Die Schwelle kommt aus dem Rest-
    Rauschen der Bandpixel, das ohne den Verlauf klein ist. Abstand zum
    oertlichen Band > Schwelle = Teil. Pruefstand: outputs/test_farbmaske.py
    (Vignetten parabel/cos^4/flach, leeres Band, Teil am Rand, 45-%-Teil).
    None, wenn kein brauchbares Modell (dann bleibt der alte Weg).
    """
    if bild is None or bild.ndim != 3:
        return None
    h, w = bild.shape[:2]
    if h < 24 or w < 24:
        return None
    k = max(1, int(k) | 1)
    lab = cv2.cvtColor(bild, cv2.COLOR_BGR2LAB)
    lab = cv2.GaussianBlur(lab, (k, k), 0).astype(np.float32)
    # Die Flaeche ist glatt: Fit und Auswertung auf einem GROBEN Raster
    # (Faktor 4), dann hochskaliert - auf dem Pi zaehlt jede Millisekunde.
    f = 4 if min(h, w) >= 96 else 1
    lab_k = cv2.resize(lab, (w // f, h // f), interpolation=cv2.INTER_AREA) \
        if f > 1 else lab
    hk, wk = lab_k.shape[:2]
    # BANDMODELL = glatte Flaeche 4. Ordnung je Lab-Kanal (15 Terme).
    # Eine echte Vignette (cos^4) ist glatt - das passt ein Polynom dieser
    # Ordnung ueberall auf 1-2 Einheiten, auch UNTER einem Teil, weil das
    # Modell global ist: eine Karte kann es nicht oertlich "aufsaugen".
    ys, xs = np.mgrid[0:hk, 0:wk]
    xn = (xs.astype(np.float32) / max(wk - 1, 1)) * 2.0 - 1.0
    yn = (ys.astype(np.float32) / max(hk - 1, 1)) * 2.0 - 1.0
    terme = [np.ones_like(xn)]
    for grad in range(1, 5):
        for i in range(grad + 1):
            terme.append((xn ** (grad - i)) * (yn ** i))
    A = np.stack(terme, axis=-1).reshape(-1, len(terme))
    B = lab_k.reshape(-1, 3)
    # ROBUST IN RUNDEN MIT SINKENDER TOLERANZ. Start: nur der Randring
    # gilt als Band (ein grosses Teil in der Mitte wuerde sonst die
    # Statistik kippen). Die Toleranz beginnt weit (3x Rauschmass des
    # Rands), damit Bandpixel in der Mitte trotz Extrapolationsfehler
    # hereinkommen, und zieht sich dann auf das reine Rauschen zusammen -
    # ein Teil, das in Runde 1 noch mitrutscht, faellt spaetestens in
    # Runde 3 wieder heraus, weil das globale Modell ihm nicht folgt.
    ring = int(max(2, min(hk, wk) * 0.05))
    gut = np.zeros((hk, wk), bool)
    gut[:ring, :] = True; gut[-ring:, :] = True
    gut[:, :ring] = True; gut[:, -ring:] = True
    gut = gut.reshape(-1)
    try:
        coef = np.linalg.lstsq(A[gut], B[gut], rcond=None)[0]
        rest = np.sqrt(((A @ coef - B) ** 2).sum(axis=1))
        rg = rest[gut]
        med = float(np.median(rg))
        mad = float(np.median(np.abs(rg - med))) * 1.4826 + 1e-3
        rausch = med + 3.0 * mad                 # Rauschmass des Bands
        for faktor in (3.0, 2.0, 1.4, 1.0, 1.0):
            neu = rest < rausch * faktor
            if neu.sum() < 0.30 * neu.size:       # Band nicht die Mehrheit
                return None
            if np.array_equal(neu, gut) and faktor == 1.0:
                break
            gut = neu
            coef = np.linalg.lstsq(A[gut], B[gut], rcond=None)[0]
            rest = np.sqrt(((A @ coef - B) ** 2).sum(axis=1))
            rg = rest[gut]
            med = float(np.median(rg))
            mad = float(np.median(np.abs(rg - med))) * 1.4826 + 1e-3
            rausch = med + 3.0 * mad
    except Exception:
        return None
    feld = (A @ coef).reshape(hk, wk, 3).astype(np.float32)
    hg = np.median(B[gut], axis=0)
    if np.abs(feld - hg).max() > 90.0:         # Flaeche laeuft davon
        return None
    gut = gut.reshape(hk, wk)
    if f > 1:
        feld = cv2.resize(feld, (w, h), interpolation=cv2.INTER_LINEAR)
    dist = np.sqrt(((lab - feld) ** 2).sum(axis=2))
    # Rauschschwelle in VOLLER Aufloesung (das grobe Raster mittelt das
    # Rauschen weg): Abstaende der Band-Pixel, 99. Perzentil.
    gm = gut.astype(np.uint8)
    if f > 1:
        gm = cv2.resize(gm, (w, h), interpolation=cv2.INTER_NEAREST)
    dr = dist[gm > 0]
    if dr.size > 40000:
        dr = dr[::dr.size // 40000 + 1]
    p99 = float(np.percentile(dr, 99)) if dr.size else 0.0
    t_f = max(float(min_abstand), 1.6 * p99 + 4.0)
    m = (dist > t_f).astype(np.uint8) * 255
    if m.mean() > 0.55 * 255:                   # halbes Bild: Unsinn
        return None
    return m


def _kanten_silhouette(board: np.ndarray) -> Optional[np.ndarray]:
    """Eingeschlossene Flaechen aus dem FARB-Kantenbild (2026-09-19).

    Loest das Grundproblem "Aufschrift statt Karte": eine schwarze Karte
    auf gruenem Band, deren Zone auch dunkle Streifen am Rand enthaelt.
    Farb- und Grauschwellen brauchen eine Hintergrundfarbe - und die ist
    am Bildrand dann schwarz, also gilt die Karte als Hintergrund. Der
    UMRISS der Karte gegen das Gruen ist aber eine geschlossene, harte
    Kante. Alles, was von Kanten umschlossen ist und vom Bildrand aus
    nicht erreichbar, ist ein Teil - egal, was innen drin ist (Schrift,
    Glanz, gleiche Farbe wie irgendwo am Rand).
    Die dunklen Randstreifen beruehren den Bildrand -> nicht umschlossen.
    """
    glatt = cv2.GaussianBlur(board, (5, 5), 0)
    kanten = None
    for i in range(glatt.shape[2]):
        c = cv2.Canny(glatt[:, :, i], 50, 120)
        kanten = c if kanten is None else cv2.bitwise_or(kanten, c)
    # Kleine Luecken im Umriss schliessen, sonst "leckt" die Flutung.
    kanten = cv2.morphologyEx(
        kanten, cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    h, w = kanten.shape[:2]
    # 1 px freier Rand ringsum, dann EINMAL vom Rand fluten (4er-Nachbar-
    # schaft: diagonale Luecken bleiben dicht). Was danach noch "frei"
    # ist, war vom Rand nicht erreichbar = eingeschlossen.
    frei = np.full((h + 2, w + 2), 255, np.uint8)
    frei[1:-1, 1:-1] = cv2.bitwise_not(kanten)
    ff = np.zeros((h + 4, w + 4), np.uint8)
    cv2.floodFill(frei, ff, (0, 0), 128)
    innen = (frei[1:-1, 1:-1] == 255).astype(np.uint8) * 255
    if not innen.any():
        return None
    # Bis zur Aussenkante auffuellen (die Kante selbst ist Teil des Teils).
    innen = cv2.dilate(innen, cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (5, 5)))
    if innen.mean() > 0.55 * 255:          # halbes Bild umschlossen: Unsinn
        return None
    return innen


def glanzmaske(bild: np.ndarray, schwelle: int, max_anteil: float,
               rand_px: int = 7, alles: bool = False) -> Optional[np.ndarray]:
    """Blendflecken (2026-09-19): Pixel, in denen ALLE Kanaele gesaettigt
    sind, in kleinen zusammenhaengenden Flecken - Reflexe der Lampen auf
    dem Band, keine Teile. Mit `alles` zaehlen auch grosse Flecken (fuer
    das Leerbild: was dort glaenzt, ist sicher Band). Rueckgabe: 255 =
    ausschliessen, mit Rand, oder None."""
    if bild is None or bild.ndim != 3 or schwelle <= 0:
        return None
    sat = (bild.min(axis=2) >= int(schwelle)).astype(np.uint8) * 255
    if not sat.any():
        return None
    if not alles:
        n, lbl, stats, _ = cv2.connectedComponentsWithStats(sat, 8)
        maxa = max_anteil * sat.size
        gross = [i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] > maxa]
        for i in gross:
            sat[lbl == i] = 0
        if not sat.any():
            return None
    # HALO: um den gesaettigten Kern liegt ein weicher Lichthof, etwa so
    # doppelt so breit wie der Kern - der Ausschluss waechst mit dem Fleck
    # (Abstandstransformation: alles naeher als r + rand_px zum Kern).
    dist = cv2.distanceTransform(cv2.bitwise_not(sat), cv2.DIST_L2, 5)
    n, lbl, stats, _ = cv2.connectedComponentsWithStats(sat, 8)
    aus = np.zeros_like(sat)
    for i in range(1, min(n, 60)):
        r = float(np.sqrt(stats[i, cv2.CC_STAT_AREA] / np.pi))
        x, y, bw, bh = stats[i, cv2.CC_STAT_LEFT], stats[i, cv2.CC_STAT_TOP], \
            stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        reich = int(1.8 * r + rand_px) + 1
        y0, y1 = max(0, y - reich), min(sat.shape[0], y + bh + reich)
        x0, x1 = max(0, x - reich), min(sat.shape[1], x + bw + reich)
        # Abstand zum NAECHSTEN Kern (nicht zwingend diesem) - reicht,
        # Flecken liegen weit auseinander.
        aus[y0:y1, x0:x1] |= (dist[y0:y1, x0:x1] <= 1.8 * r + rand_px).astype(np.uint8) * 255
    return aus


def foreground_mask(
    board: np.ndarray,
    params: SegmentationParams,
    background_ref: Optional[np.ndarray] = None,
    background_noise: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Binaere Vordergrundmaske (255 = Teil, 0 = Band).

    Zwei Wege:
      * `background_ref` gegeben -> Differenzbild zum leeren Band. Das ist der
        robustere Weg und sollte im Betrieb verwendet werden (leeres Band
        einmal aufnehmen).
      * sonst Otsu-Schwelle auf dem Graubild.
    """
    gray = board if board.ndim == 2 else cv2.cvtColor(board, cv2.COLOR_BGR2GRAY)
    k = max(1, params.blur_ksize | 1)
    gray = cv2.GaussianBlur(gray, (k, k), 0)

    if background_ref is not None:
        # LEERBILD-DIFFERENZ IN FARBE (2026-09-19). Vorher Grau: eine
        # schwarze Karte auf dunkelgruenem Band ist im Grau fast gleich
        # hell wie das Band - Differenz null, Karte unsichtbar. Je Kanal
        # (B, G, R) ist der Unterschied dagegen deutlich; das Maximum
        # ueber die Kanaele zaehlt. Untergrenze gegen Rauschen/leichte
        # Lichtdrift: unter 18/255 ist nichts ein Teil - sonst macht
        # Otsu auf leerem Band aus Rauschen Phantome.
        ref = background_ref
        if ref.shape[:2] != board.shape[:2]:
            ref = cv2.resize(ref, (board.shape[1], board.shape[0]),
                             interpolation=cv2.INTER_AREA)
        if board.ndim == 3 and ref.ndim == 3:
            b_ = cv2.GaussianBlur(board, (k, k), 0)
            r_ = cv2.GaussianBlur(ref, (k, k), 0)
            d3 = cv2.absdiff(b_, r_)
            diff = np.max(d3, axis=2).astype(np.uint8)
        else:
            r_ = ref if ref.ndim == 2 else cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY)
            r_ = cv2.GaussianBlur(r_, (k, k), 0)
            diff = cv2.absdiff(gray, r_)
        t_o, _ = cv2.threshold(diff, 0, 255,
                               cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        t = max(float(t_o), float(getattr(params, "leer_min_diff", 18.0)))
        if background_noise is not None:
            # SCHWELLE JE PIXEL (2026-09-19): wo das leere Band von Bild
            # zu Bild schwankt (Blendflecken, LED-Flackern, Belichtung),
            # muss die Differenz entsprechend groesser sein.
            try:
                nz = background_noise
                if nz.ndim == 3:
                    nz = nz.max(axis=2)
                if nz.shape[:2] != diff.shape[:2]:
                    nz = cv2.resize(nz, (diff.shape[1], diff.shape[0]),
                                    interpolation=cv2.INTER_LINEAR)
                fak = float(getattr(params, "leer_rausch_faktor", 1.5))
                t_pix = np.maximum(t, fak * nz.astype(np.float32) + 6.0)
                mask = (diff.astype(np.float32) > t_pix).astype(np.uint8) * 255
            except Exception:
                _, mask = cv2.threshold(diff, t, 255, cv2.THRESH_BINARY)
        else:
            _, mask = cv2.threshold(diff, t, 255, cv2.THRESH_BINARY)
        # Was im LEERBILD glaenzt, ist Band - immer ausschliessen (mit Rand).
        try:
            gs = int(getattr(params, "glanz_schwelle", 246))
            if gs > 0 and ref.ndim == 3:
                g_ref = glanzmaske(ref, gs, 1.0, rand_px=9, alles=True)
                if g_ref is not None:
                    mask[g_ref > 0] = 0
        except Exception:
            pass
    elif params.use_adaptive:
        mask = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 51, 5,
        )
    else:
        thr, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        thr = float(np.clip(thr + params.otsu_offset, 0, 255))
        # Teile duerfen heller oder dunkler als das Band sein -> Variante
        # mit der kleineren Vordergrundflaeche gewinnt.
        _, m_dark = cv2.threshold(gray, thr, 255, cv2.THRESH_BINARY_INV)
        _, m_light = cv2.threshold(gray, thr, 255, cv2.THRESH_BINARY)
        mask = m_dark if m_dark.mean() <= m_light.mean() else m_light

        # FARBMASKE (2026-09-08): "dunkles Teil auf dunklem Band". Im Grau
        # sind schwarze Karte und gruenes Band fast gleich hell - Otsu nahm
        # dann nur die weisse Aufschrift als Teil und der Kartenkoerper
        # blieb Hintergrund (Ergebnis: drei Schrift-Klumpen, "unbekannt").
        # Farblich ist Schwarz vs. Gruen eindeutig: Abstand jedes Pixels
        # zur BANDFARBE (Median des Bildrands, Lab) -> Otsu -> Maske. Sie
        # wird mit der Graumaske VEREINIGT, kann also nur Vordergrund
        # hinzufuegen. Schutz: floodet sie das halbe Bild (Rand zeigt nicht
        # das Band), bleibt es bei der Graumaske.
        if getattr(params, "farb_maske", True) and board.ndim == 3:
            try:
                min_ab = float(getattr(params, "farb_min_abstand", 12.0))
                # OERTLICHES Bandmodell (Vignette der Pi-Kamera, 2026-09-19).
                m_farbe = farbmaske_lokal(board, k, min_ab)
                if m_farbe is None:
                    # Rueckfall: EINE Bandfarbe aus dem Rand. Schwelle aus
                    # dem Rauschen des Bands (99. Perzentil), nicht Otsu -
                    # Otsu legte die Luecke zwischen Kartenkoerper und
                    # weisser Aufschrift (Fix 2026-09-08).
                    lab = cv2.cvtColor(board, cv2.COLOR_BGR2LAB)
                    lab = cv2.GaussianBlur(lab, (k, k), 0).astype(np.float32)
                    rand = np.concatenate([lab[0, :], lab[-1, :],
                                           lab[:, 0], lab[:, -1]]).reshape(-1, 3)
                    hg = np.median(rand, axis=0)
                    dist = np.sqrt(((lab - hg) ** 2).sum(axis=2))
                    d_rand = np.sqrt(((rand - hg) ** 2).sum(axis=1))
                    p99 = float(np.percentile(d_rand, 99)) if d_rand.size else 0.0
                    t_f = max(min_ab, 1.6 * p99 + 4.0)
                    m_farbe = (dist > t_f).astype(np.uint8) * 255
                    if m_farbe.mean() >= 0.55 * 255:
                        m_farbe = None
                if m_farbe is not None:
                    mask = cv2.bitwise_or(mask, m_farbe)
            except Exception:
                pass

    # KANTEN-SILHOUETTE (2026-09-19): umschlossene Flaechen als Vordergrund
    # dazunehmen - unabhaengig von Hintergrund- und Innenfarbe.
    if (background_ref is None and getattr(params, "kanten_fuellung", True)
            and board.ndim == 3):
        try:
            innen = _kanten_silhouette(board)
            if innen is not None:
                mask = cv2.bitwise_or(mask, innen)
        except Exception:
            pass

    # BLENDFLECKEN im Livebild (2026-09-19): kleine gesaettigte Flecken
    # sind Lampenreflexe - raus, mit Rand (der Halo drumherum ebenso).
    try:
        gs = int(getattr(params, "glanz_schwelle", 246))
        if gs > 0 and board.ndim == 3:
            g_live = glanzmaske(board, gs,
                                float(getattr(params, "glanz_max_anteil", 0.02)))
            if g_live is not None:
                mask[g_live > 0] = 0
    except Exception:
        pass

    if params.morph_open_px > 0:
        ker = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (params.morph_open_px, params.morph_open_px)
        )
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, ker)
    if params.morph_close_px > 0:
        ker = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (params.morph_close_px, params.morph_close_px)
        )
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, ker)
    return mask


# ----------------------------------------------------------------------
def part_area_px(px_per_mm: float) -> float:
    return config.PART_AREA_MM2 * px_per_mm * px_per_mm


def estimate_part_count(area_px: float, px_per_mm: float) -> float:
    return area_px / max(part_area_px(px_per_mm), 1e-6)


# ----------------------------------------------------------------------
def split_touching(
    blob_mask: np.ndarray,
    px_per_mm: float,
    params: SegmentationParams,
) -> List[np.ndarray]:
    """Trennt eine Blob-Maske mit mehreren beruehrenden Teilen.

    Distanztransformation: jeder Vordergrundpixel bekommt den Abstand zum
    naechsten Hintergrundpixel. In der Mitte jedes Teils entsteht ein Maximum.
    Diese Maxima sind die Saatpunkte fuer Watershed.
    """
    dist = cv2.distanceTransform(blob_mask, cv2.DIST_L2, 5)
    if dist.max() <= 0:
        return [blob_mask]

    _, seeds = cv2.threshold(
        dist, params.dt_seed_ratio * dist.max(), 255, cv2.THRESH_BINARY
    )
    seeds = seeds.astype(np.uint8)

    n_seeds, seed_lbl, seed_stats, _ = cv2.connectedComponentsWithStats(seeds, 8)
    min_seed_area = params.min_seed_area_frac * part_area_px(px_per_mm)
    keep = [
        i for i in range(1, n_seeds)
        if seed_stats[i, cv2.CC_STAT_AREA] >= min_seed_area
    ]
    if len(keep) <= 1:
        # Zweiter Anlauf: schrittweise Erosion. Die 55-%-Schwelle bemisst
        # sich am GROESSTEN Abstand im Blob - beruehrt ein duenner Ring
        # eine dicke SD-Karte, stammt das Maximum von der Karte, und der
        # Ring verliert seine Saat: ein Klumpen blieb ein Klumpen
        # (2026-08-28). Erosion trennt beruehrende Teile unabhaengig von
        # ihrer Dicke: die schmale Beruehrstelle reisst zuerst.
        # BESTE Iteration nehmen, nicht die erste mit zwei Treffern: im
        # Live-Massstab ist das Ringrohr nur wenige Pixel dick und
        # verschwindet, bevor sich die dicke SD ueberhaupt teilt - mit der
        # alten 88-px-Schwelle blieb der Klumpen ganz (2026-08-28). Kleine
        # Kerne (>= 20 px) zaehlen mit; die Chip-Wiedervereinigung setzt
        # zersplitterte Boegen spaeter wieder zusammen.
        ker3 = np.ones((3, 3), np.uint8)
        arbeit = blob_mask.copy()
        seeds2 = None
        beste_n = 1
        for _ in range(25):
            arbeit = cv2.erode(arbeit, ker3)
            if cv2.countNonZero(arbeit) < 30:
                break
            n2, lbl2, st2, _ = cv2.connectedComponentsWithStats(arbeit, 8)
            gross = [i for i in range(1, n2)
                     if st2[i, cv2.CC_STAT_AREA] >= 20]
            if len(gross) > beste_n:
                beste_n = len(gross)
                seeds2 = np.zeros_like(blob_mask)
                for i in gross:
                    seeds2[lbl2 == i] = 255
        if seeds2 is None:
            # Auch Erosion trennt nichts -> Blob unveraendert weiterreichen.
            return [blob_mask]
        seeds = seeds2
        n_seeds, seed_lbl, seed_stats, _ = cv2.connectedComponentsWithStats(
            seeds, 8)
        keep = list(range(1, n_seeds))

    markers = np.zeros(blob_mask.shape, dtype=np.int32)
    for new_id, old_id in enumerate(keep, start=1):
        markers[seed_lbl == old_id] = new_id

    # Sicherer Hintergrund: alles ausserhalb der leicht aufgeweiteten Blobflaeche.
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    sure_bg = cv2.dilate(blob_mask, ker, iterations=3)
    unknown = cv2.subtract(sure_bg, seeds)
    markers[unknown > 0] = 0
    markers[sure_bg == 0] = len(keep) + 1        # Hintergrundmarker

    bgr = cv2.cvtColor(blob_mask, cv2.COLOR_GRAY2BGR)
    cv2.watershed(bgr, markers)

    out: List[np.ndarray] = []
    for lbl in range(1, len(keep) + 1):
        part = np.zeros_like(blob_mask)
        part[(markers == lbl) & (blob_mask > 0)] = 255
        if cv2.countNonZero(part) > 0:
            out.append(part)
    return out or [blob_mask]


# ----------------------------------------------------------------------
def segment_parts(
    board: np.ndarray,
    px_per_mm: float,
    params: SegmentationParams,
    background_ref: Optional[np.ndarray] = None,
    background_noise: Optional[np.ndarray] = None,
) -> Tuple[List[np.ndarray], np.ndarray, List[dict]]:
    """Liefert (Einzelteil-Masken, Gesamtmaske, Blob-Diagnose).

    Die Diagnoseliste dokumentiert jede Entscheidung. Kriterium A7 aus SPEC.md:
    nichts wird stillschweigend verworfen.
    """
    mask = foreground_mask(board, params, background_ref, background_noise)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)

    one_part = part_area_px(px_per_mm)
    min_area = params.min_blob_area_frac * one_part
    max_area = params.max_blob_parts * one_part

    parts: List[np.ndarray] = []
    diag: List[dict] = []

    for i in range(1, n):
        area = float(stats[i, cv2.CC_STAT_AREA])
        est = estimate_part_count(area, px_per_mm)
        entry = {"blob": i, "area_px": area, "est_parts": round(est, 2)}

        if area < min_area:
            entry["action"] = "verworfen: zu klein (Schmutz/Rauschen)"
            diag.append(entry)
            continue
        # Die alte Obergrenze (max_blob_parts x PART_AREA_MM2) war in
        # Wahrheit eine PIXELGRENZE: die Live-Strecke kalibriert mit
        # px_per_mm=1, also wuchs jedes Teil mit dem Fensterzoom - und am
        # 2026-08-28 verschwand eine frei liegende SD-Karte kommentarlos
        # als "zu gross". Verworfen wird jetzt nur noch, was nach
        # Belichtungs-/Bandfehler aussieht: ein Blob, der fast die halbe
        # Suchflaeche bedeckt. Alles andere ist ein (grosses) Teil.
        if area > 0.45 * mask.shape[0] * mask.shape[1]:
            entry["action"] = "verworfen: bedeckt fast das halbe Bild (Belichtung/Bandfehler pruefen)"
            diag.append(entry)
            continue
        if area > max_area:
            entry["warn"] = ("groesser als das erwartete Teilemass - "
                             "Fenster/Zoom beachten")

        blob = np.zeros(mask.shape, dtype=np.uint8)
        blob[labels == i] = 255

        if est >= params.split_trigger_parts:
            pieces = split_touching(blob, px_per_mm, params)
            entry["action"] = f"watershed -> {len(pieces)} Teil(e)"
            if len(pieces) == 1:
                entry["warn"] = (
                    "Flaeche deutet auf mehrere Teile, Trennung schlug fehl "
                    "-> Verdacht Ueberlappung (Fall 2)"
                )
            parts.extend(pieces)
        else:
            entry["action"] = "einzeln"
            parts.append(blob)

        diag.append(entry)

    return parts, mask, diag


def mask_to_contour(part_mask: np.ndarray) -> Optional[np.ndarray]:
    cnts, _ = cv2.findContours(part_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    return max(cnts, key=cv2.contourArea)
