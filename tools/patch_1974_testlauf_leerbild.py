#!/usr/bin/env python3
"""1.9.74: Testlauf benutzt das Leerbild - wie die Live-Erkennung.

Pi 2026-10-04: auf leeren Testsatz-Szenen meldete der Testlauf zwei
"SD CARD" (0,71 / 0,99), live auf derselben leeren Flaeche: "Kein Teil".
Grund: die Testszene ist ein 687-px-Ausschnitt, _leerbild_crop verlangte
aber die Form des ganzen Kamerabilds -> kein Leerbild -> andere
Segmentierung als live. Jetzt: ist ein Testbild aktiv, wird das Leerbild am
aktuellen Aufnahmefenster zugeschnitten und auf die Testszene skaliert.
Idempotent."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
S = ROOT / "vorsa/web/server.py"
s = S.read_text(encoding="utf-8")
if "Testbild: Leerbild am Aufnahmefenster" in s:
    print("schon angewendet"); raise SystemExit(0)
def ers(t, a, b):
    assert t.count(a) == 1, (a[:60], t.count(a)); return t.replace(a, b)
s = ers(s, 'BUILD = "1.9.73-roh"', 'BUILD = "1.9.74-testleer"')
s = ers(s, '''        v = self._leerbild.get(str(quelle))
        if not v or not self._leerbild_passt(quelle, v):
            return None
        b = v["bild"]
        if b.shape[:2] != tuple(form[:2]):
            return None
        r = v.get("rausch")''', '''        v = self._leerbild.get(str(quelle))
        if not v or not self._leerbild_passt(quelle, v):
            return None
        b = v["bild"]
        r = v.get("rausch")
        if (str(quelle) == "haupt" and getattr(self, "_testbild", None) is not None
                and b.shape[:2] != tuple(form[:2])):
            # 1.9.74 Testbild: Leerbild am Aufnahmefenster zuschneiden und auf
            # die Testszene skalieren - dieselbe Kette wie live.
            try:
                lh, lw = b.shape[:2]
                lx, ly, ls, _h = self.zustand.bereich.rechteck(lw, lh)
                th, tw = y1 - y0, x1 - x0
                if ls >= 8 and th >= 8 and tw >= 8:
                    lb = cv2.resize(b[ly:ly + ls, lx:lx + ls], (tw, th), interpolation=cv2.INTER_AREA)
                    if r is not None and r.shape[:2] == b.shape[:2]:
                        lr = cv2.resize(r[ly:ly + ls, lx:lx + ls], (tw, th), interpolation=cv2.INTER_AREA)
                        return (lb, lr)
                    return lb
            except Exception:
                pass
            return None
        if b.shape[:2] != tuple(form[:2]):
            return None''')
S.write_text(s, encoding="utf-8")
print("ok 1.9.74")
