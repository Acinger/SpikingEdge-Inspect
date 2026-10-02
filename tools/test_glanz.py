"""Pruefstand Blendflecken (2026-09-19): Lampenreflexe auf dem Band duerfen
keine Teile sein - ohne Leerbild (Glanzfilter) und mit Leerbild aus
mehreren flackernden Bildern (Rauschkarte, Schwelle je Pixel)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, cv2
from vorsa.segmentation import foreground_mask, segment_parts
from vorsa.config import SegmentationParams

h, w = 480, 640
rng = np.random.default_rng(3)
def band(flimmer=0.0):
    b = np.zeros((h, w, 3), np.float32); b[..., 0] = 40; b[..., 1] = 95; b[..., 2] = 25
    b += rng.normal(0, 3, b.shape)
    # drei Blendflecken: gesaettigter Kern + weicher Halo, Halo flackert
    for (cx, cy, r) in [(120, 90, 14), (500, 380, 18), (330, 60, 10)]:
        yy, xx = np.mgrid[0:h, 0:w]
        d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        halo = np.clip(1.0 - (d - r) / (r * 1.6), 0, 1) * (1.0 + flimmer * rng.normal())
        b += (halo[..., None] * np.array([200, 200, 200], np.float32))
        b[d < r] = 255
    return np.clip(b, 0, 255).astype(np.uint8)
def karte(img):
    img = img.copy(); cv2.rectangle(img, (220, 160), (420, 380), (18, 20, 19), -1)
    cv2.rectangle(img, (245, 180), (265, 360), (200, 205, 200), -1)
    soll = np.zeros((h, w), np.uint8); cv2.rectangle(soll, (220, 160), (420, 380), 255, -1)
    return img, soll
def iou(m, soll):
    a = m > 0; b = soll > 0; return (a & b).sum() / max((a | b).sum(), 1)
fehler = 0
BILDER = os.environ.get("VORSA_BENCH_BILDER")
if BILDER: os.makedirs(BILDER, exist_ok=True)
def bild(name, img, m_alt, m_neu):
    if not BILDER: return
    panels = [img.copy(), cv2.cvtColor(m_alt, cv2.COLOR_GRAY2BGR), cv2.cvtColor(m_neu, cv2.COLOR_GRAY2BGR)]
    for im, t in zip(panels, ("input", "without glare filter", "with glare filter / reference")):
        cv2.putText(im, t, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.imwrite(os.path.join(BILDER, name + ".png"), np.hstack(panels))
def pr(name, wert, lo=None, hi=None):
    global fehler
    ok = (lo is None or wert >= lo) and (hi is None or wert <= hi)
    fehler += 0 if ok else 1
    print(("ok  " if ok else "FEHLT") + " %-48s %6.2f" % (name, wert))
P = SegmentationParams()
# 1) ohne Leerbild
leer = band(0.0)
m = foreground_mask(leer, P)
P0 = SegmentationParams(); P0.glanz_schwelle = 0
bild("glanz_leeres_band", leer, foreground_mask(leer, P0), m)
pr("ohne Leerbild: leeres Band mit Blendflecken, Vordergrund %", (m > 0).mean() * 100, None, 0.3)
teile, _, _ = segment_parts(leer, 1.0, P)
pr("ohne Leerbild: gefundene Teile auf leerem Band", len(teile), None, 0)
img, soll = karte(leer)
bild("glanz_karte", img, foreground_mask(img, P0), foreground_mask(img, P))
pr("ohne Leerbild: Karte neben Blendflecken IoU", iou(foreground_mask(img, P), soll), 0.85)
# 2) mit Leerbild aus 8 flackernden Bildern (wie leerbild_merken)
stapel = np.stack([band(0.25) for _ in range(8)]).astype(np.int16)
median = np.median(stapel, axis=0).astype(np.uint8)
rausch = np.clip(np.abs(stapel - median.astype(np.int16)).max(axis=3).max(axis=0), 0, 255).astype(np.uint8)
live = band(0.25)
m_alt = foreground_mask(live, P, background_ref=median)             # nur Median, keine Rauschkarte
m_neu = foreground_mask(live, P, background_ref=median, background_noise=rausch)
bild("glanz_leerbild_rauschkarte", live, m_alt, m_neu)
pr("Leerbild ohne Rauschkarte: Vordergrund % (Info)", (m_alt > 0).mean() * 100)
pr("Leerbild MIT Rauschkarte: leeres Band Vordergrund %", (m_neu > 0).mean() * 100, None, 0.3)
teile, _, _ = segment_parts(live, 1.0, P, background_ref=median, background_noise=rausch)
pr("Leerbild MIT Rauschkarte: Teile auf leerem Band", len(teile), None, 0)
img, soll = karte(live)
pr("Leerbild MIT Rauschkarte: Karte IoU", iou(foreground_mask(img, P, median, rausch), soll), 0.85)
# 3) Karte LIEGT AUF einem Blendfleck: Fleck wird Loch, Karte bleibt
img2 = img.copy(); cv2.rectangle(img2, (100, 70), (300, 290), (18, 20, 19), -1)
soll2 = np.zeros((h, w), np.uint8); cv2.rectangle(soll2, (100, 70), (300, 290), 255, -1); cv2.rectangle(soll2, (220, 160), (420, 380), 255, -1)
pr("Karte ueber Blendfleck: IoU", iou(foreground_mask(img2, P, median, rausch), soll2), 0.85)
# 4) grosses weisses Teil (gesaettigt) darf NICHT als Glanz verschwinden
img3 = leer.copy(); cv2.rectangle(img3, (200, 150), (440, 330), (255, 255, 255), -1)
soll3 = np.zeros((h, w), np.uint8); cv2.rectangle(soll3, (200, 150), (440, 330), 255, -1)
pr("grosses weisses Teil bleibt (ohne Leerbild) IoU", iou(foreground_mask(img3, P), soll3), 0.85)
print("FEHLER:", fehler); sys.exit(1 if fehler else 0)
