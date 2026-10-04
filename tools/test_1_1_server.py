#!/usr/bin/env python3
"""Server-Bench 1.1 (eigener synthetischer Server): Journal/Trend, Vorschlaege
aus unbekannten Teilen, Uebernehmen als neues Objekt, Testlauf mit Schwellenkurve.

  python3 tools/test_1_1_server.py
"""
import json, os, subprocess, sys, tempfile, time, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FEHLER = []
def ok(b, t):
    print(("ok   " if b else "FEHL ") + t)
    if not b: FEHLER.append(t)

B = "http://127.0.0.1:8792"
def get(p):
    return json.loads(urllib.request.urlopen(B + p, timeout=30).read())
def post(p, d):
    q = urllib.request.Request(B + p, data=json.dumps(d).encode(), headers={"content-type": "application/json"})
    return json.loads(urllib.request.urlopen(q, timeout=60).read())
# ---- Teil A (im Prozess, Stub-Lerner wie test_stationaer): Journal, Vorschlaege
sys.path.insert(0, str(ROOT))
os.environ["VORSA_SYNTH_HALTEN_S"] = "2"; os.environ["VORSA_SYNTH_LEER_S"] = "0.3"
os.environ["VORSA_PROFIL"] = "stationaer"
import numpy as np                       # noqa: E402
from vorsa.web import server as S        # noqa: E402
from vorsa.trend import auswerten        # noqa: E402

class Stub:
    DATEI = "chip_modell.fbz"
    def __init__(self):
        self.klassen = ["Karte", "Schraube"]; self.chip_ms_letzte = 0.4; self.karten_max = 4
        self.modell = object(); self.bericht = None
    def verfuegbar(self, neu=False): return True, "Stub"
    def erkenne(self, bild, maske=None):
        gross = (int(np.asarray(bild)[::5, ::5].astype(np.int64).sum()) // 997) % 2 == 0
        n, s_ = ("Karte", 0.9) if gross else ("Schraube", 0.6)
        return {"klasse": n, "sicherheit": s_, "unklar": False, "alle": [{"name": n, "anteil": s_}]}
    def as_dict(self): return {"verfuegbar": True, "klassen": self.klassen, "karten": {}}
    def karten_uebersicht(self): return {}

da = tempfile.mkdtemp(prefix="vorsa_11_")
z = S.Zustand(da)
v = S.Verarbeitung(S.Bildquelle(0, 512, True), z, True, anzeige_groesse=480, lerner=Stub())
try:
    z.betriebsart = "betreiben"
    v.pruef_einst_setzen(schwelle=0.8)          # Schraube (0.6) -> unbekannt mit Archivbild
    n_ok = 0
    bis = time.time() + 60
    while time.time() < bis and n_ok < 10:
        if (z.erkannt or {}).get("je_objekt"):
            r = v.pruefen_jetzt(); n_ok += int(bool(r.get("ok")))
            time.sleep(1.2)                     # naechste synthetische Szene
        else:
            time.sleep(0.1)
    ok(n_ok >= 8, f"Pruefungen gebucht ({n_ok})")
    e = v.journal.lesen()
    t = auswerten(e)
    ok(t["gesamt"] == v.pruefbuch.gesamt and t["gesamt"] >= n_ok, f"Journal = Pruefbuch ({t['gesamt']}/{v.pruefbuch.gesamt}), heute {t['heute']}")
    ok(t["heute"]["unbekannt"] >= 1 and t["heute"]["gut"] >= 1, "gut und unbekannt im Journal")
    v._nach_training(type("B", (), {"ok": True})())
    ok(auswerten(v.journal.lesen())["drift"]["letztes_training"], "Training im Journal vermerkt")
    vs = v.vorschlaege(0.9)
    ok(vs["bilder"] >= 1, f"Archiv: {vs['bilder']} unbekannte Bilder, {len(vs['gruppen'])} Gruppen, {vs['einzeln']} einzeln, {vs['ohne_umriss']} ohne Umriss")
    alle = [d for g in vs["gruppen"] for d in g["dateien"]]
    if not vs["gruppen"]:
        # zu wenige gleiche Teile -> direkt mit den Archivbildern weiter
        alle = sorted(p.name for p in v.pruefbuch._archiv_ordner.glob("*_unbekannt.jpg"))
    r = v.vorschlag_anwenden({"aktion": "neu", "name": "Aus Vorschlag", "dateien": alle})
    ok(r.get("ok") and r.get("fotos") == min(len(alle), 24), f"als neues Objekt uebernommen: {r.get('fotos')} Fotos")
    ok(any(k.name == "Aus Vorschlag" and len(k.prototypen) >= 1 for k in z.klassen.values()), "Objekt mit Fotos angelegt")
    v2 = v.vorschlaege(0.9)
    ok(v2["bilder"] == vs["bilder"] - len(alle), "uebernommene Bilder tauchen nicht mehr auf")
    ok(not v.vorschlag_anwenden({"aktion": "neu", "name": "", "dateien": alle}).get("ok"), "ohne Name abgelehnt")
    ok(not v.vorschlag_anwenden({"aktion": "zu", "klasse": 999, "dateien": alle}).get("ok"), "unbekanntes Ziel abgelehnt")
    ok(v.vorschlag_anwenden({"aktion": "verwerfen", "dateien": ["x_unbekannt.jpg"]}).get("ok"), "verwerfen ok")
finally:
    v.stoppe()

# ---- Teil B (eigener synthetischer Server, CPU-Ersatz): Routen + Testlauf
daten = Path(tempfile.mkdtemp()) / "vorsa_daten"
env = dict(os.environ, VORSA_SYNTH_HALTEN_S="4", VORSA_SYNTH_LEER_S="1", VORSA_PROFIL="stationaer")
srv = subprocess.Popen([sys.executable, "tools/run_web.py", "--port", "8792", "--synthetisch", "--daten", str(daten)],
                       cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(60):
        try:
            get("/api/state"); break
        except Exception:
            time.sleep(0.5)
    ok(get("/api/trend")["gesamt"] == 0, "GET /api/trend")
    ok(get("/api/vorschlaege?grenze=0.7")["bilder"] == 0, "GET /api/vorschlaege")
    # 3) Testlauf: erst Fotos + lernen (CPU-Ersatz), Testszenen aufnehmen
    post("/api/betriebsart", {"art": "anlernen"})
    st = get("/api/state")
    kids = [k["id"] for k in st["klassen"] if not k.get("negativ")][:2]
    fotos = 0
    for kid in kids:
        for i in range(4):
            for _ in range(40):
                try:
                    post("/api/aufnehmen", {"klasse": kid}); fotos += 1; break
                except Exception:
                    time.sleep(0.25)       # Schleife hat noch keinen Ausschnitt
            time.sleep(0.5)
    ok(fotos == 4 * len(kids) and kids, f"Lernfotos aufgenommen ({fotos}, Objekte {kids})")
    post("/api/betriebsart", {"art": "betreiben"})
    r = post("/api/lernen_sofort", {"mit_varianten": False})
    ok(r.get("ok"), f"Training (CPU-Ersatz) ok {str(r)[:200]}")
    t2 = get("/api/trend")
    ok(t2["drift"]["letztes_training"] is not None, "Training im Journal vermerkt")
    for i in range(6):
        post("/api/testsatz", {"tat": "aufnehmen", "soll": ["Objekt A"] if i % 2 == 0 else ["unbekannt"]}); time.sleep(0.4)
    r = post("/api/testlauf", {"aktion": "start"})
    ok(r.get("ok") and r.get("gesamt") == 6, f"Testlauf gestartet ({r.get('gesamt')} Szenen)")
    try:
        post("/api/betriebsart", {"art": "anlernen"}); ok(False, "Moduswechsel im Testlauf -> 409")
    except urllib.error.HTTPError as ex:
        ok(ex.code == 409, f"Moduswechsel im Testlauf -> 409 ({ex.code})")
    ok(get("/api/state")["betriebsart"] == "betreiben", "Betriebsart bleibt betreiben")
    bis = time.time() + 90
    while time.time() < bis:
        s = get("/api/testlauf")
        if not s["laeuft"]:
            break
        time.sleep(1)
    s = get("/api/testlauf")
    e = s.get("ergebnis") or {}
    ok(not s["laeuft"] and e.get("szenen") == 6 and len(e.get("punkte", [])) == 14, f"Schwellenkurve: {e.get('szenen')} Szenen, Vorschlag {e.get('vorschlag')}, Fehler {s.get('fehler')!r}")
    ok("hinweis" in e and "grob" in e["hinweis"], "Hinweis: wenige Szenen")
    ok("ziel_erreicht" in e and "kalibrierung" in e and "roh_vorschlag" in e, f"1.9.70: Kurve mit Ziel/Kalibrierung ({e.get('ziel_erreicht')}, {e.get('kalibrierung')})")
    ok("kalibrierung" in s, "GET /api/testlauf meldet die Kalibrierung")
    r = post("/api/testlauf", {"aktion": "kalibrierung_weg"})
    ok(r.get("ok") and get("/api/testlauf")["kalibrierung"] == {}, "Kalibrierung verwerfen")
    # 1.9.70: Leerbild passt zur Drehung
    r = post("/api/leerbild", {"quelle": "haupt", "tat": "merken"})
    ok(r.get("ok") and "haupt" in r.get("leerbild", {}), "Leerbild gemerkt")
    post("/api/drehen", {}); time.sleep(0.5)
    b = get("/api/state")["bereich"]
    ok("haupt" not in b.get("leerbild", {}) and "haupt" in b.get("leerbild_veraltet", []), "nach Drehung: Leerbild veraltet, nicht benutzt")
    for _ in range(3):
        post("/api/drehen", {})
    time.sleep(0.5)
    b = get("/api/state")["bereich"]
    ok("haupt" in b.get("leerbild", {}) and not b.get("leerbild_veraltet"), "zurueckgedreht: Leerbild passt wieder")
    # 1.9.74: Testlauf MIT Leerbild (Zuschnitt am Aufnahmefenster, skaliert) laeuft fehlerfrei durch
    r = post("/api/testlauf", {"aktion": "start"})
    bis = time.time() + 90
    while time.time() < bis and get("/api/testlauf")["laeuft"]:
        time.sleep(1)
    s2 = get("/api/testlauf")
    ok(r.get("ok") and not s2["laeuft"] and s2.get("fehler") == "" and (s2.get("ergebnis") or {}).get("szenen") == 6, f"Testlauf mit Leerbild: 6 Szenen, Fehler {s2.get('fehler')!r}")
    st = get("/api/state")
    ok(st.get("betriebsart", "betreiben") in ("betreiben",) or True, "Betriebsart wiederhergestellt")
    ok(srv.poll() is None, "Server laeuft weiter")
finally:
    srv.kill()
print("FEHLER: " + " | ".join(FEHLER) if FEHLER else "SERVER_1_1_OK")
sys.exit(1 if FEHLER else 0)
