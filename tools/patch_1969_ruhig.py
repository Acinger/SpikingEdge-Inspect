#!/usr/bin/env python3
"""1.9.69: zwei springende Elemente auf dem Pi (Video 2026-10-04).

1. Knopf "Lernzonen" im Videokopf: aktualisieren() zeigte ihn im Anlernen bei
   JEDEM Zustandsabruf, opsSync() versteckte ihn danach wieder (Einkamera) -
   Kamera/Ansicht/Vollbild sprangen im Takt seitlich. Jetzt eine Regel an
   beiden Stellen.
2. "Erste Schritte" in der Seitenleiste: verschwand bei 6/6 und kam bei 5/6
   zurueck - die Haken Schaerfe/Gepruefte Teile kippen kurz (Hand im Bild,
   Zaehler). Die ganze Leiste sprang um eine Zeile. Jetzt: einmal 6/6 =
   ausgeblendet fuer diese Sitzung (ueber "Einstellungen > Allgemein > Erste
   Schritte" weiter erreichbar). Idempotent."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "vorsa/web/static/index.html"; S = ROOT / "vorsa/web/server.py"
h, s = H.read_text(encoding="utf-8"), S.read_text(encoding="utf-8")
if "NAVSTART_FERTIG" in h:
    print("schon angewendet"); raise SystemExit(0)
def ers(t, a, b):
    assert t.count(a) == 1, (a[:60], t.count(a)); return t.replace(a, b)
s = ers(s, 'BUILD = "1.9.68-testsatz"', 'BUILD = "1.9.69-ruhig"')
h = ers(h, '''  const lk = $("lernzonenKnopf");
  if (lk) lk.hidden = MODUS !== "anlernen";''', '''  const lk = $("lernzonenKnopf");
  if (lk) { const weg = MODUS !== "anlernen" || STATIONAER() || EINKAMERA(); if (lk.hidden !== weg) lk.hidden = weg; }''')
h = ers(h, '''    ns.hidden = s.erledigt >= 6;''', '''    if (s.erledigt >= 6) NAVSTART_FERTIG = true;
    const weg = NAVSTART_FERTIG;
    if (ns.hidden !== weg) ns.hidden = weg;''')
h = ers(h, "function ablaufMalen() {", "let NAVSTART_FERTIG = false;   // einmal 6/6 -> bleibt weg (kein Springen)\nfunction ablaufMalen() {")
H.write_text(h, encoding="utf-8"); S.write_text(s, encoding="utf-8")
print("ok 1.9.69")
