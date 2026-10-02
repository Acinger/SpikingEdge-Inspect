"""Pruefstand fuer farbmaske_lokal: Vignetten, leeres Band, Teil am Rand,
grosses Teil, flaches Band. Erwartung je Fall in Klammern."""
import sys, time
import numpy as np, cv2
import os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vorsa.segmentation import farbmaske_lokal, foreground_mask
from vorsa.config import SegmentationParams

h, w = 480, 640
ys, xs = np.mgrid[0:h, 0:w]
r = np.sqrt(((xs - w / 2) / (w / 2)) ** 2 + ((ys - h / 2) / (h / 2)) ** 2)
rng = np.random.default_rng(1)
PROFILE = {
    "parabel":  np.clip(1.0 - 0.35 * r ** 2, 0.25, 1.0),
    "geklippt": np.clip(1.0 - 0.55 * r ** 2, 0.25, 1.0),
    "cos4":     np.cos(np.arctan(r * 0.9)) ** 4,
    "flach":    np.ones_like(r),
}
def band(vig, sig=3):
    bg = np.zeros((h, w, 3), np.float32)
    bg[..., 1] = 95 * vig; bg[..., 0] = 40 * vig; bg[..., 2] = 25 * vig
    bg += rng.normal(0, sig, bg.shape)
    return np.clip(bg, 0, 255).astype(np.uint8)
def karte(img, x0=200, y0=120, x1=400, y1=340, etiketten=True):
    img = img.copy()
    cv2.rectangle(img, (x0, y0), (x1, y1), (18, 20, 19), -1)
    if etiketten:
        cv2.rectangle(img, (x0 + 25, y0 + 20), (x0 + 45, y1 - 20), (200, 205, 200), -1)
        cv2.rectangle(img, (x1 - 70, y0 + 30), (x1 - 30, y1 - 40), (60, 60, 230), -1)
        cv2.putText(img, "microSD", (x0 + 55, (y0 + y1) // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (210, 210, 210), 2)
    soll = np.zeros((h, w), np.uint8); cv2.rectangle(soll, (x0, y0), (x1, y1), 255, -1)
    return img, soll
def iou(m, soll):
    if m is None: return -1.0
    a = m > 0; b = soll > 0
    return (a & b).sum() / max((a | b).sum(), 1)
fehler = 0
BILDER = os.environ.get("VORSA_BENCH_BILDER")   # Ordner: Eingang | alte Maske | neue Maske
if BILDER: os.makedirs(BILDER, exist_ok=True)
def alt_maske(img):
    lab = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2LAB), (5, 5), 0).astype(np.float32)
    rand = np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]).reshape(-1, 3); hg = np.median(rand, 0)
    d = np.sqrt(((rand - hg) ** 2).sum(1)); t = max(12, 1.6 * np.percentile(d, 99) + 4)
    return (np.sqrt(((lab - hg) ** 2).sum(2)) > t).astype(np.uint8) * 255
def bild(name, img, neu):
    if not BILDER: return
    m0 = cv2.cvtColor(alt_maske(img), cv2.COLOR_GRAY2BGR)
    m1 = cv2.cvtColor(neu if neu is not None else np.zeros(img.shape[:2], np.uint8), cv2.COLOR_GRAY2BGR)
    for im, t in ((img, "input"), (m0, "old: global belt colour"), (m1, "new: local belt model")):
        cv2.putText(im, t, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.imwrite(os.path.join(BILDER, name + ".png"), np.hstack([img, m0, m1]))
def pr(name, wert, soll_min=None, soll_max=None):
    global fehler
    ok = (soll_min is None or wert >= soll_min) and (soll_max is None or wert <= soll_max)
    if not ok: fehler += 1
    print(("ok  " if ok else "FEHLT") + " %-42s %6.2f" % (name, wert))

for pn, vig in PROFILE.items():
    leer = band(vig)
    ml = farbmaske_lokal(leer, 5, 12.0)
    pr(pn + ": leeres Band, Vordergrund %", (ml > 0).mean() * 100 if ml is not None else 0, None, 3.0 if pn == "geklippt" else 1.0)
    img, soll = karte(leer)
    m_neu = farbmaske_lokal(img, 5, 12.0); bild("farbmaske_" + pn, img.copy(), m_neu)
    pr(pn + ": Karte IoU", iou(m_neu, soll), 0.85)
    pr(pn + ": foreground_mask gesamt IoU", iou(foreground_mask(img, SegmentationParams()), soll), 0.85)
# Teil beruehrt den Rand
img, soll = karte(band(PROFILE["cos4"]))
cv2.rectangle(img, (0, 380), (120, 479), (18, 20, 19), -1)
pr("cos4: Karte IoU mit 2. Teil am Rand", iou(farbmaske_lokal(img, 5, 12.0), soll), 0.85)
# grosses Teil (45 % des Bilds)
img, soll = karte(band(PROFILE["cos4"]), 120, 60, 520, 400)
pr("cos4: grosse Karte (45 %) IoU", iou(farbmaske_lokal(img, 5, 12.0), soll), 0.85)
# kleiner Zonen-Ausschnitt
kl = cv2.resize(karte(band(PROFILE["cos4"]))[0], (220, 300))
t0 = time.time(); mk = farbmaske_lokal(kl, 5, 12.0); ms = (time.time() - t0) * 1000
pr("klein 220x300: Vordergrund % (Soll ~14.7)", (mk > 0).mean() * 100, 12, 18)
t0 = time.time()
for _ in range(10): farbmaske_lokal(img, 5, 12.0)
pr("Laufzeit 640x480 ms (x86)", (time.time() - t0) * 100, None, 60)
# starkes Rauschen leer
ml = farbmaske_lokal(band(PROFILE["cos4"], 8), 5, 12.0)
pr("cos4 Rauschen 8: leer Vordergrund %", (ml > 0).mean() * 100 if ml is not None else 0, None, 1.5)
print("FEHLER:", fehler)
sys.exit(1 if fehler else 0)
