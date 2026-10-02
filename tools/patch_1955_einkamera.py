#!/usr/bin/env python3
"""1.9.55 — Einkamera-Version (Anmerkung Ace, Screenshot Linienmodus):
Anlieferung und Abholung kommen aus EINER Kamera. Zweitkameras (USB/picamN),
"Blick 2" und Lernzonen sind erst mit VORSA_ZWEITKAMERA=1 wieder da.
Gespeicherte Zonen-Quellen (z. B. picam1 = "Pi-Kam 1: list index out of range")
werden im Einkamera-Betrieb auf die Hauptkamera gelegt; blick2.json bleibt
unangetastet, wird nur nicht benutzt."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
S = ROOT / "vorsa" / "web" / "server.py"; H = ROOT / "vorsa" / "web" / "static" / "index.html"
D = ROOT / "vorsa" / "web" / "static" / "sprache_en.js"
def ers(t, a, n, k=1):
    if t.count(a) != k: raise SystemExit(f"FEHLER: {t.count(a)}x statt {k}x: {a[:120]}")
    return t.replace(a, n)
s = S.read_text(encoding="utf-8")
if "self.einkamera" in s:
    print("server.py: schon gepatcht")
else:
    s = ers(s, 'BUILD = "1.9.54-logo"', 'BUILD = "1.9.55-einkamera"')
    s = ers(s, '''        try:
            self.linie.laden(zustand.ordner)   # gespeicherte Zonen
        except Exception:
            pass
''', '''        try:
            self.linie.laden(zustand.ordner)   # gespeicherte Zonen
        except Exception:
            pass
        # EINKAMERA (SE Inspect 1.0, 1.9.55): Anlieferung und Abholung
        # kommen aus derselben Kamera. Zweitkameras/Blick 2/Lernzonen
        # gibt es erst wieder mit VORSA_ZWEITKAMERA=1. Eine gespeicherte
        # Zonen-Quelle wie "picam1" (Kamera abgesteckt -> schwarzes Feld,
        # "list index out of range") wird hier auf die Hauptkamera gelegt.
        self.einkamera = _os.environ.get("VORSA_ZWEITKAMERA", "0").lower() not in ("1", "ja", "true")
        if self.einkamera:
            try:
                q = getattr(self.linie, "quellen", {}) or {}
                fremd = {a: v for a, v in q.items() if str(v) != "haupt"}
                if fremd:
                    for a in fremd:
                        q[a] = "haupt"
                    print(f"  Einkamera: Zonen-Quellen {fremd} -> Hauptkamera "
                          f"(Zone ggf. neu ziehen)", flush=True)
            except Exception:
                pass
''')
    s = ers(s, '''        self._blick2 = {"quelle": "aus", "zone": [0.02, 0.02, 0.98, 0.98]}
        self._fusion_info: dict = {}
        self._blick2_laden()
''', '''        self._blick2 = {"quelle": "aus", "zone": [0.02, 0.02, 0.98, 0.98]}
        self._fusion_info: dict = {}
        self._blick2_laden()
        if getattr(self, "einkamera", True) and self._blick2.get("quelle", "aus") != "aus":
            print(f"  Einkamera: Blick 2 ({self._blick2['quelle']}) bleibt aus", flush=True)
            self._blick2["quelle"] = "aus"      # nur im Speicher, blick2.json bleibt
''')
    s = ers(s, '''                    ld["blick2"] = {**dict(self._blick2),
                                    **dict(getattr(self, "_fusion_info", {}))}
''', '''                    ld["blick2"] = {**dict(self._blick2),
                                    **dict(getattr(self, "_fusion_info", {}))}
                    ld["einkamera"] = bool(getattr(self, "einkamera", True))
''')
    s = ers(s, '''                if art in ("lern_a", "lern_b"):
                    # Lernzone (1.9.29): Kamera des Slots waehlen.''', '''                if getattr(verarbeitung, "einkamera", True) and q != "haupt":
                    return self._json({"fehler": "Einkamera-Betrieb: Zonen kommen aus der "
                                       "Hauptkamera (Zweitkamera: VORSA_ZWEITKAMERA=1)"}, 409)
                if art in ("lern_a", "lern_b"):
                    # Lernzone (1.9.29): Kamera des Slots waehlen.''')
    S.write_text(s, encoding="utf-8"); print("server.py gepatcht")
h = H.read_text(encoding="utf-8")
if "EINKAMERA" in h:
    print("index.html: schon gepatcht")
else:
    h = ers(h, '''const STATIONAER = () => PROFIL === "stationaer";''', '''const STATIONAER = () => PROFIL === "stationaer";
// 1.9.55: Einkamera-Version - Quellenwahl, Blick 2 und Lernzonen bleiben weg,
// bis der Server (VORSA_ZWEITKAMERA=1) sie wieder meldet.
const EINKAMERA = () => (((Z || {}).bereich || {}).linie || {}).einkamera !== false;''')
    h = ers(h, '''  try { quellenOptionen(LI); } catch (e) {}
  if (!lern) try { blick2Spiegeln(LI); } catch (e) {}''', '''  try { quellenOptionen(LI); } catch (e) {}
  if (!lern) try { blick2Spiegeln(LI); } catch (e) {}
  try { einkameraAnwenden(); } catch (e) {}''')
    h = ers(h, '''// Blick 2: Auswahl aus dem Serverstand spiegeln, Zonen-Knopf nur wenn an.''', '''// Einkamera (1.9.55): Quellen-Dropdowns, Blick 2 und das Fusions-Badge weg.
function einkameraAnwenden() {
  const ein = EINKAMERA();
  document.body.classList.toggle("einkamera", ein);
  if (!ein) return;
  document.querySelectorAll(".lfquelle, .lfblick2z, #fAnlBlick2").forEach(el => { el.hidden = true; });
}
// Blick 2: Auswahl aus dem Serverstand spiegeln, Zonen-Knopf nur wenn an.''')
    h = ers(h, '''  const lk = $("lernzonenKnopf");
  if (lk) lk.hidden = m !== "anlernen" || STATIONAER();''', '''  const lk = $("lernzonenKnopf");
  if (lk) lk.hidden = m !== "anlernen" || STATIONAER() || EINKAMERA();''')
    h = ers(h, '''  const lk2 = $("lernzonenKnopf");
  if (lk2 && STATIONAER()) lk2.hidden = true;''', '''  const lk2 = $("lernzonenKnopf");
  if (lk2 && (STATIONAER() || EINKAMERA())) lk2.hidden = true;''')
    h = ers(h, '''body.stationaer #lernzonenKnopf { display:none !important; }''', '''body.stationaer #lernzonenKnopf { display:none !important; }
body.einkamera #lernzonenKnopf, body.einkamera .lfquelle, body.einkamera .lfblick2z, body.einkamera #fAnlBlick2 { display:none !important; }''')
    H.write_text(h, encoding="utf-8"); print("index.html gepatcht")
d = D.read_text(encoding="utf-8")
if "Einkamera-Betrieb" not in d:
    d = ers(d, '''  "Kamera-Einstellungen": "Camera settings",''', '''  "Kamera-Einstellungen": "Camera settings",
  "Einkamera-Betrieb: Zonen kommen aus der Hauptkamera (Zweitkamera: VORSA_ZWEITKAMERA=1)": "Single-camera mode: zones come from the main camera (second camera: VORSA_ZWEITKAMERA=1)",''')
    D.write_text(d, encoding="utf-8"); print("sprache_en.js gepatcht")
