#!/usr/bin/env python3
"""A2 — Mehrbild-Aufnahme stationaer (Build 1.9.40).

server.py: Mehrbild auf dem Ausschnitt im Profil stationaer (Betreiben),
Einstellung `mehrbild` in pruef.json und /api/pruef_einst, Stand im
Pruefbereich. index.html: Regler "Bilder mitteln" in den Pruefparametern,
Anzeige "gemittelt N" im Szenenstatus. Exakte Ersetzungen, idempotent.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
S = ROOT / "vorsa" / "web" / "server.py"
H = ROOT / "vorsa" / "web" / "static" / "index.html"


def ers(text, alt, neu, n=1):
    k = text.count(alt)
    if k != n:
        raise SystemExit(f"FEHLER: {k}x statt {n}x gefunden:\n{alt[:200]}")
    return text.replace(alt, neu)


srv = S.read_text(encoding="utf-8")
if "1.9.40-mehrbild" in srv:
    print("server.py: schon gepatcht")
else:
    srv = ers(srv, 'BUILD = "1.9.39-sprache"', 'BUILD = "1.9.40-mehrbild"')
    srv = ers(srv, '''        self._pruef_ausschnitt = None     # Bild der letzten Erkennung
        self._pruef_anfrage = False       # /api/pruefen wartet auf den Takt
''', '''        self._pruef_ausschnitt = None     # Bild der letzten Erkennung
        self._pruef_anfrage = False       # /api/pruefen wartet auf den Takt
        # MEHRBILD (1.9.40, A2): im Profil stationaer wird der Ausschnitt
        # ueber N Bilder gemittelt, solange die Szene steht. Weniger
        # Rauschen, kein LED-Flackern in der Leerbild-Differenz.
        from ..mehrbild import Mehrbild
        self.mehrbild = Mehrbild(anzahl=4 if self.profil == "stationaer" else 1)
''')
    srv = ers(srv, '''            ausschnitt = frame[y:y + seite, x:x + seite].copy()
            n = 0
''', '''            ausschnitt = frame[y:y + seite, x:x + seite].copy()
            n = 0
            # MEHRBILD (A2): nur stationaer und nur beim Betreiben - die
            # Lernfotos bleiben einzelne, echte Aufnahmen.
            if (self.profil == "stationaer" and self.mehrbild.anzahl > 1
                    and str(self.zustand.betriebsart) == "betreiben"):
                try:
                    ausschnitt = self.mehrbild.verarbeite(ausschnitt)
                    # Anzeige, Leerbild und Erkennung sehen dasselbe Bild.
                    frame[y:y + seite, x:x + seite] = ausschnitt
                except Exception:
                    pass
            self.zustand.bereich_info["mehrbild"] = self.mehrbild.als_dict()
''')
    srv = ers(srv, '''                ps["profil"] = self.profil
                ps["letzte_pruefung"] = self._pruef_letzte''', '''                ps["profil"] = self.profil
                ps["mehrbild"] = self.mehrbild.als_dict()
                ps["letzte_pruefung"] = self._pruef_letzte''')
    # Einstellung persistent
    srv = ers(srv, '''        return {"schwelle": self.konfidenz_schwelle,
                "unbekannt_ziel": self.unbekannt_ziel,
                "ausloeser": self.pruef_ausloeser}
''', '''        return {"schwelle": self.konfidenz_schwelle,
                "unbekannt_ziel": self.unbekannt_ziel,
                "ausloeser": self.pruef_ausloeser,
                "mehrbild_anzahl": self.mehrbild.anzahl}

    def mehrbild_setzen(self, anzahl) -> dict:
        try:
            n = max(1, min(16, int(anzahl)))
        except Exception:
            n = 4
        self.mehrbild.einstellen(anzahl=n)
        p = self._pruef_einst_pfad()
        try:
            if p:
                d = {}
                if p.exists():
                    d = json.loads(p.read_text(encoding="utf-8"))
                d["mehrbild"] = n
                p.write_text(json.dumps(d), encoding="utf-8")
        except Exception:
            pass
        return self.pruef_einst()
''')
    srv = ers(srv, '''                if d.get("ausloeser") in ("hand", "auto"):
                    self.pruef_ausloeser = d["ausloeser"]
        except Exception:
            pass
''', '''                if d.get("ausloeser") in ("hand", "auto"):
                    self.pruef_ausloeser = d["ausloeser"]
                if d.get("mehrbild") is not None and self.profil == "stationaer":
                    self.mehrbild.einstellen(anzahl=max(1, min(16, int(d["mehrbild"]))))
        except Exception:
            pass
''')
    srv = ers(srv, '''                p.write_text(json.dumps({
                    "schwelle": self.konfidenz_schwelle,
                    "unbekannt_ziel": self.unbekannt_ziel,
                    "ausloeser": self.pruef_ausloeser}), encoding="utf-8")''', '''                p.write_text(json.dumps({
                    "schwelle": self.konfidenz_schwelle,
                    "unbekannt_ziel": self.unbekannt_ziel,
                    "ausloeser": self.pruef_ausloeser,
                    "mehrbild": self.mehrbild.anzahl}), encoding="utf-8")''')
    srv = ers(srv, '''                if koerper.get("ausloeser") in ("hand", "auto"):
                    return self._json(verarbeitung.pruef_ausloeser_setzen(
                        koerper["ausloeser"]))''', '''                if koerper.get("ausloeser") in ("hand", "auto"):
                    return self._json(verarbeitung.pruef_ausloeser_setzen(
                        koerper["ausloeser"]))
                if koerper.get("mehrbild") is not None:
                    return self._json(verarbeitung.mehrbild_setzen(koerper["mehrbild"]))''')
    S.write_text(srv, encoding="utf-8")
    print("server.py gepatcht")

h = H.read_text(encoding="utf-8")
if 'data-regler="pruef_mehrbild"' in h:
    print("index.html: schon gepatcht")
else:
    # Statuszeile: gemittelt N
    h = ers(h, '''    <div class="pu-status ${P.szene_steht && teil && !P.szene_gebucht ? "bereit" : ""}">${status}</div>''',
            '''    <div class="pu-status ${P.szene_steht && teil && !P.szene_gebucht ? "bereit" : ""}">${status}${
      P.mehrbild && P.mehrbild.anzahl > 1 ? ` · ${P.mehrbild.gemittelt} von ${P.mehrbild.anzahl} Bildern gemittelt` : ""}</div>''')
    # Regler in den Pruefparametern (nur stationaer)
    h = ers(h, '''      <label>Ziel Unbek.-Quote</label>
      <input type="range" data-regler="pruef_ziel" min="1" max="50"
             step="1" value="${Math.round(P.unbekannt_ziel || 10)}"
             title="Ab dieser Unbekannt-Quote wird Nachlernen empfohlen">
      <b>${Math.round(P.unbekannt_ziel || 10)} %</b>''', '''      <label>Ziel Unbek.-Quote</label>
      <input type="range" data-regler="pruef_ziel" min="1" max="50"
             step="1" value="${Math.round(P.unbekannt_ziel || 10)}"
             title="Ab dieser Unbekannt-Quote wird Nachlernen empfohlen">
      <b>${Math.round(P.unbekannt_ziel || 10)} %</b>
      ${STATIONAER() ? `<label>Bilder mitteln</label>
      <input type="range" data-regler="pruef_mehrbild" min="1" max="16"
             step="1" value="${P.mehrbild_anzahl || 1}"
             title="Stehende Szene über N Bilder mitteln: weniger Rauschen, kein Flackern (1 = aus)">
      <b>${(P.mehrbild_anzahl || 1) > 1 ? (P.mehrbild_anzahl + " Bilder") : "aus"}</b>` : ""}''')
    # Regler-Handler
    h = ers(h, '''    } else if (el.dataset.regler === "pruef_ziel") {''', '''    } else if (el.dataset.regler === "pruef_mehrbild") {
      const b = el.nextElementSibling;
      if (b) b.textContent = wert > 1 ? wert + " Bilder" : "aus";
      spaeter(() => hole("/api/pruef_einst", { mehrbild: wert }));
    } else if (el.dataset.regler === "pruef_ziel") {''')
    H.write_text(h, encoding="utf-8")
    print("index.html gepatcht")
