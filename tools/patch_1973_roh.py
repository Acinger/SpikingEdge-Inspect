#!/usr/bin/env python3
"""1.9.73: Testlauf misst garantiert roh.

Pi 2026-10-04 12:50: ab Szene 10 waren die Ist-Werte ploetzlich kalibriert
(SD 0,87-0,94 statt 0,55-0,61) - irgendetwas hat ler.kalibrierung mitten im
Lauf wieder gesetzt. Statt den Schreiber zu jagen: ein Sperrflag am Lerner,
das _kalibriere waehrend des Laufs hart abschaltet, _kalib_anwenden ist
waehrend des Laufs ein No-op, und jede Anwendung wird ins Serverlog
geschrieben. Idempotent."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
S = ROOT / "vorsa/web/server.py"; L = ROOT / "vorsa/edge_learn.py"
s, l = S.read_text(encoding="utf-8"), L.read_text(encoding="utf-8")
if "_kalib_sperre" in l:
    print("schon angewendet"); raise SystemExit(0)
def ers(t, a, b):
    assert t.count(a) == 1, (a[:60], t.count(a)); return t.replace(a, b)
s = ers(s, 'BUILD = "1.9.72-testlauf"', 'BUILD = "1.9.73-roh"')
l = ers(l, '''        kal = getattr(self, "kalibrierung", None) or {}
        if not kal:
            return anteile''', '''        if getattr(self, "_kalib_sperre", False):     # Testlauf: immer roh
            return anteile
        kal = getattr(self, "kalibrierung", None) or {}
        if not kal:
            return anteile''')
s = ers(s, '''    def _kalib_anwenden(self) -> None:
        if self.lerner is not None:
            try:
                self.lerner.kalibrierung = dict((self._kalib or {}).get("werte") or {})
            except Exception:
                pass''', '''    def _kalib_anwenden(self) -> None:
        if self.lerner is not None:
            if getattr(self, "_testlauf", {}).get("laeuft"):
                print("  Kalibrierung: nicht angewendet (Testlauf laeuft)", flush=True)
                return
            try:
                w = dict((self._kalib or {}).get("werte") or {})
                self.lerner.kalibrierung = w
                print(f"  Kalibrierung angewendet: {w}", flush=True)
            except Exception:
                pass''')
s = ers(s, '''            ler.kalibrierung = {}
            ler.UNBEKANNT_AB = 0.0
            self.zustand.betriebsart = "betreiben"''', '''            ler._kalib_sperre = True
            ler.UNBEKANNT_AB = 0.0
            self.zustand.betriebsart = "betreiben"''')
s = ers(s, '''                self._testlauf["fertig"] += 1
            ler.kalibrierung = alt_kal
            if hatte_ab:''', '''                self._testlauf["fertig"] += 1
            ler._kalib_sperre = False
            if hatte_ab:''')
s = ers(s, '''                if not getattr(ler, "kalibrierung", None):
                    self._kalib_anwenden()
            except Exception:
                pass
            self.zustand.betriebsart = alt_art
            self._testlauf["laeuft"] = False''', '''            except Exception:
                pass
            ler._kalib_sperre = False
            self.zustand.betriebsart = alt_art
            self._testlauf["laeuft"] = False
            self._kalib_anwenden()''')
S.write_text(s, encoding="utf-8"); L.write_text(l, encoding="utf-8")
print("ok 1.9.73")
