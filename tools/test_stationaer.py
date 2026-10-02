#!/usr/bin/env python3
"""Bench: stationaere Pruefung (SE Inspect 1.0, A1).

Ohne Hardware: synthetische Bildquelle, Stub-Lerner mit zwei Klassen.
Prueft
  - Profil "stationaer" ist Standard, Linie laesst sich nicht aktivieren
  - /api/pruefen bucht jedes Teil der Szene genau einmal ins Pruefbuch
  - Ausloeser "auto" bucht eine stehende Szene von selbst, und nur einmal
  - Negativklasse -> ausschuss, Schwelle -> unbekannt
Ausgabe: STATIONAER_OK oder FEHLER.
"""
import os, sys, time, json, tempfile, threading
from pathlib import Path

os.environ.setdefault("VORSA_PROFIL", "stationaer")
os.environ["VORSA_SYNTH_HALTEN_S"] = "30"      # Szene steht lange still
os.environ["VORSA_SYNTH_LEER_S"] = "0.5"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np                                  # noqa: E402
from vorsa.web import server as srv                 # noqa: E402


class StubLerner:
    """Antwortet wie EdgeLerner.erkenne, ohne Karte: grosse Teile heissen
    'Karte' (0.9), kleine 'Schraube' (0.8)."""
    DATEI = "chip_modell.fbz"

    def __init__(self):
        self.klassen = ["Karte", "Schraube", "nichts"]
        self.chip_ms_letzte = 0.4
        self.karten_max = 4
        self.modell = object()
        self.bericht = None
        self.sicherheit_schraube = 0.8

    def verfuegbar(self, neu=False):
        return True, "Stub"

    def erkenne(self, bild, maske=None):
        # deterministisch je Teil (Bildinhalt), nicht je Aufruf
        gross = (int(np.asarray(bild)[::5, ::5].astype(np.int64).sum()) // 997) % 2 == 0
        name = "Karte" if gross else "Schraube"
        s = 0.9 if gross else self.sicherheit_schraube
        return {"klasse": name, "sicherheit": s, "unklar": False,
                "alle": [{"name": name, "anteil": s},
                         {"name": "nichts", "anteil": 0.1}]}

    def as_dict(self):
        return {"verfuegbar": True, "klassen": self.klassen, "karten": {}}

    def karten_uebersicht(self):
        return {}


def fehler(msg):
    print("FEHLER:", msg)
    sys.exit(1)


def warte(bedingung, s=8.0, takt=0.05):
    bis = time.time() + s
    while time.time() < bis:
        try:
            if bedingung():
                return True
        except Exception:
            pass
        time.sleep(takt)
    return False


def main():
    daten = tempfile.mkdtemp(prefix="vorsa_stat_")
    zustand = srv.Zustand(daten)
    quelle = srv.Bildquelle(0, 512, True)
    lerner = StubLerner()
    v = srv.Verarbeitung(quelle, zustand, True, anzeige_groesse=480, lerner=lerner)
    try:
        if v.profil != "stationaer":
            fehler(f"Profil {v.profil!r} statt stationaer")
        if not v.linie.band.simulation if hasattr(v.linie.band, "simulation") else False:
            fehler("Band ist im Profil stationaer nicht in Simulation")
        zustand.betriebsart = "betreiben"
        ok = warte(lambda: (zustand.erkannt or {}).get("je_objekt"))
        if not ok:
            fehler("synthetische Szene liefert keine je_objekt-Teile")
        time.sleep(1.0)                      # Szene steht, Erkennung eingeschwungen
        n_teile = len(zustand.erkannt["je_objekt"])
        print(f"ok   Szene mit {n_teile} Teil(en) erkannt")
        if not all(o.get("box_px") for o in zustand.erkannt["je_objekt"]):
            fehler("box_px fehlt an je_objekt")

        # 1) Hand-Ausloeser: einmal buchen
        r = v.pruefen_jetzt()
        if not r.get("ok"):
            fehler(f"pruefen_jetzt: {r}")
        n_teile = len(r["teile"])
        if n_teile < 1:
            fehler("nichts gebucht")
        if v.pruefbuch.gesamt != n_teile:
            fehler(f"Pruefbuch gesamt {v.pruefbuch.gesamt} != {n_teile}")
        if r["urteil"] != "gut" or v.pruefbuch.gut != n_teile:
            fehler(f"Urteil {r['urteil']}, gut={v.pruefbuch.gut}")
        print(f"ok   Hand: {n_teile} Teile gebucht, Gesamturteil gut")
        st = v._pruef_stand or {}
        if not warte(lambda: (v._pruef_stand or {}).get("letzte_pruefung")):
            fehler("letzte_pruefung fehlt im Pruefstand")

        # 2) Automatik: dieselbe stehende Szene darf NICHT nochmal gebucht werden
        v.pruef_ausloeser_setzen("auto")
        if json.loads((Path(daten) / "pruef.json").read_text())["ausloeser"] != "auto":
            fehler("Ausloeser nicht persistiert")
        time.sleep(2.5)
        if v.pruefbuch.gesamt != n_teile:
            fehler(f"Automatik hat stehende, schon gebuchte Szene erneut gebucht "
                   f"({v.pruefbuch.gesamt})")
        print("ok   Auto: schon gebuchte Szene bleibt gebucht")

        # 3) Szene wechseln -> Automatik bucht genau einmal
        v._pruef_gebucht_sig = ""           # wie "Tisch leer" dazwischen
        v._pruef_gebucht_zeit = 0.0
        if not warte(lambda: v.pruefbuch.gesamt >= 2 * n_teile, s=6.0):
            fehler("Automatik bucht neue Szene nicht")
        time.sleep(2.0)
        if v.pruefbuch.gesamt > 2 * n_teile + 1:
            fehler(f"Automatik bucht mehrfach: {v.pruefbuch.gesamt}")
        print("ok   Auto: neue Szene genau einmal gebucht")
        v.pruef_ausloeser_setzen("hand")

        # 4) Urteilsregeln je Teil: Negativklasse, Schwelle, unbekannt, unklar
        neg = {"Schraube"}
        u = lambda o: v._pruef_urteil_teil(o, neg)["urteil"]
        if u({"name": "Schraube", "anteil": 0.9}) != "ausschuss":
            fehler("Negativklasse nicht ausschuss")
        if u({"name": "Karte", "anteil": 0.9}) != "gut":
            fehler("sicheres Teil nicht gut")
        if u({"name": "unbekanntes Teil", "anteil": 0.3, "unbekannt": True}) != "unbekannt":
            fehler("unbekannt nicht unbekannt")
        if u({"name": "unklar", "anteil": 0.5, "unklar": True}) != "unbekannt":
            fehler("unklar nicht unbekannt")
        v.pruef_einst_setzen(schwelle=0.95)
        if u({"name": "Karte", "anteil": 0.9}) != "unbekannt":
            fehler("Schwelle 95 % greift nicht")
        r = v.pruefen_jetzt()
        if any(t["urteil"] == "gut" for t in r["teile"]):
            fehler(f"Schwelle 95 % greift nicht in der Buchung: {r['teile']}")
        v.pruef_einst_setzen(schwelle_aus=True)
        print("ok   Urteilsregeln: ausschuss / gut / unbekannt / unklar / Schwelle")

        # 5) Linie laesst sich nicht aktivieren (Profilsperre im Handler)
        handler = srv.baue_handler(v, zustand, {}, protokoll=False)
        import http.server, socket
        s = srv.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        port = s.server_address[1]
        threading.Thread(target=s.serve_forever, daemon=True).start()
        import urllib.request, urllib.error
        def post(weg, body):
            req = urllib.request.Request(f"http://127.0.0.1:{port}{weg}",
                                         data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=5) as a:
                    return a.status, json.loads(a.read())
            except urllib.error.HTTPError as e:
                return e.code, json.loads(e.read() or b"{}")
        code, d = post("/api/linie", {"aktiv": True})
        if code != 409:
            fehler(f"/api/linie aktiv -> {code} statt 409")
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/state", timeout=5) as a:
            st = json.loads(a.read())
        if st.get("profil") != "stationaer":
            fehler("profil fehlt im /api/state")
        if (st.get("bereich") or {}).get("pruef", {}).get("ausloeser") != "hand":
            fehler("ausloeser fehlt in bereich.pruef")
        code, d = post("/api/pruefen", {})
        if code != 200 or not d.get("ok"):
            fehler(f"/api/pruefen -> {code} {d}")
        print("ok   HTTP: /api/linie 409, /api/state profil, /api/pruefen bucht")
        s.shutdown()
        print(f"STATIONAER_OK gesamt={v.pruefbuch.gesamt} gut={v.pruefbuch.gut} "
              f"unbekannt={v.pruefbuch.unbekannt} ausschuss={v.pruefbuch.ausschuss}")
    finally:
        v.stoppe()


if __name__ == "__main__":
    main()
