#!/usr/bin/env python3
"""1.9.64 — Version 1.1: selbstlernende Zelle, Auto-Schwelle, Statistik & Trend.

Server:
  * Pruefjournal (vorsa/trend.py): jedes gebuchte Teil + jedes Training, dauerhaft.
  * GET /api/trend                     Stunden/Tage/Drift
  * GET /api/vorschlaege?grenze=0.7    Gruppen aus unbekannten Archivbildern (vorsa/selbstlernen.py)
  * POST /api/vorschlag_anwenden       neu | zu | hintergrund | verwerfen
  * POST /api/testlauf {aktion:start}  Testsatz durch die laufende Erkennung schicken
    GET  /api/testlauf                 Fortschritt + Schwellenkurve (vorsa/schwelle.py)
  * Testbild-Einspeisung in die Bildschleife (nur waehrend des Testlaufs; ohne
    Leerbild-Differenz, Mehrbild und Buchung - wie tools/eval_testsatz.py).
Oberflaeche: Anlernen › Vorschlaege (Dialog), Pruefung › Trend (Reiter),
Einstellungen › Erkennung › Schwelle aus dem Testsatz.
"""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "vorsa" / "web" / "static" / "index.html"
S = ROOT / "vorsa" / "web" / "server.py"
D = ROOT / "vorsa" / "web" / "static" / "sprache_en.js"


def ers(t, a, n, k=1):
    if t.count(a) != k:
        raise SystemExit(f"FEHLER: {t.count(a)}x statt {k}x: {a[:140]}")
    return t.replace(a, n)


s = S.read_text(encoding="utf-8")
if "/api/vorschlaege" in s:
    print("server.py: schon gepatcht")
else:
    s = ers(s, 'BUILD = "1.9.63-sicherung"', 'BUILD = "1.9.64-selbstlernen"')
    # --- Journal ---------------------------------------------------------
    s = ers(s, '''        self.pruefbuch = Pruefbuch()
        try:
            self.pruefbuch.archiv_setzen(self.zustand.ordner)
        except Exception:
            pass
''', '''        self.pruefbuch = Pruefbuch()
        try:
            self.pruefbuch.archiv_setzen(self.zustand.ordner)
        except Exception:
            pass
        # PRUEFJOURNAL (1.1-C): jedes gebuchte Teil dauerhaft - fuer Trend und Drift.
        from ..trend import Journal
        self.journal = Journal(self.zustand.ordner)
        _buche_roh = self.pruefbuch.buche

        def _buche_mit_journal(urteil, name="", konf=0.0, *a, **k):
            e = _buche_roh(urteil, name, konf, *a, **k)
            try:
                self.journal.teil(e.get("urteil", urteil), e.get("name", ""), e.get("konfidenz", 0.0), e.get("zeit"))
            except Exception:
                pass
            return e
        self.pruefbuch.buche = _buche_mit_journal
        self._testbild = None
        self._testlauf = {"laeuft": False, "fertig": 0, "gesamt": 0, "ergebnis": None, "fehler": ""}
''')
    # --- Testbild-Einspeisung ---------------------------------------------
    s = ers(s, '''            frame = self.quelle.lies()
            # Bilddrehung in 90-Grad-Schritten (Knopf im Videokopf,''', '''            frame = self.quelle.lies()
            # TESTLAUF (1.1-B): statt des Kamerabilds eine Testsatz-Szene.
            tb = self._testbild
            if tb is not None:
                frame = tb.copy()
            # Bilddrehung in 90-Grad-Schritten (Knopf im Videokopf,''')
    s = ers(s, '''            d = getattr(self, "drehung", 0)
            if d:
                frame = np.ascontiguousarray(np.rot90(frame, d // 90))
            h, w = frame.shape[:2]
            x, y, seite, hinweis = self.zustand.bereich.rechteck(w, h)''', '''            d = getattr(self, "drehung", 0)
            if d and tb is None:
                frame = np.ascontiguousarray(np.rot90(frame, d // 90))
            h, w = frame.shape[:2]
            if tb is None:
                x, y, seite, hinweis = self.zustand.bereich.rechteck(w, h)
            else:
                # Testszene IST der Pruef-Ausschnitt: ganzes Bild, Fenster bleibt unberuehrt.
                x, y, seite, hinweis = 0, 0, min(w, h), ""''')
    s = ers(s, '''            if (self.profil == "stationaer" and self.mehrbild.anzahl > 1
                    and str(self.zustand.betriebsart) == "betreiben"):''', '''            if (self.profil == "stationaer" and self.mehrbild.anzahl > 1 and tb is None
                    and str(self.zustand.betriebsart) == "betreiben"):''')
    s = ers(s, '''            if self.profil == "stationaer":
                try:
                    self._pruef_stationaer_takt(art)''', '''            if self.profil == "stationaer" and tb is None:
                try:
                    self._pruef_stationaer_takt(art)''')
    s = ers(s, '''                        bereit=(art == "betreiben"),''', '''                        bereit=(art == "betreiben" and tb is None),''')
    # --- Methoden ------------------------------------------------------------
    s = ers(s, '''    def _eaio_trigger(self) -> None:''', '''    # ---- 1.1: Training merken, Vorschlaege, Testlauf -----------------------
    def _nach_training(self, bericht):
        try:
            if getattr(bericht, "ok", False):
                self.journal.training()
        except Exception:
            pass
        return bericht

    def _vorschlag_erledigt_pfad(self):
        return Path(self.zustand.ordner) / "vorschlaege_erledigt.json"

    def _vorschlag_erledigt(self) -> set:
        try:
            return set(json.loads(self._vorschlag_erledigt_pfad().read_text(encoding="utf-8")))
        except Exception:
            return set()

    def _vorschlag_erledigt_add(self, dateien) -> None:
        e = self._vorschlag_erledigt() | set(dateien)
        try:
            self._vorschlag_erledigt_pfad().write_text(json.dumps(sorted(e)[-5000:]), encoding="utf-8")
        except Exception:
            pass

    def vorschlaege(self, grenze: float = 0.7) -> dict:
        from ..selbstlernen import merkmale, vorschlaege
        ordner = self.pruefbuch._archiv_ordner
        if ordner is None:
            return {"gruppen": [], "bilder": 0, "ohne_umriss": 0, "einzeln": 0, "grenze": grenze}
        fertig = self._vorschlag_erledigt()
        dateien = [d for d in sorted(p.name for p in ordner.glob("*_unbekannt.jpg")) if d not in fertig][-300:]
        # Merkmale der gelernten Objekte (fuer "aehnelt X"), je Objekt hoechstens 6 Fotos.
        bekannte = {}
        try:
            for k in self.zustand.klassen.values():
                if k.negativ or not k.prototypen:
                    continue
                vs = []
                for d in list(k.prototypen)[:6]:
                    b = self.zustand.prototyp_bild(d)
                    v = merkmale(b) if b is not None else None
                    if v is not None:
                        vs.append(v)
                bekannte[k.name] = vs
        except Exception:
            bekannte = {}
        return vorschlaege(ordner, dateien, grenze=max(0.3, min(1.5, float(grenze))), bekannte=bekannte)

    def vorschlag_anwenden(self, k: dict) -> dict:
        aktion = str(k.get("aktion", ""))
        dateien = [Path(str(d)).name for d in (k.get("dateien") or [])][:200]
        ordner = self.pruefbuch._archiv_ordner
        if not dateien or ordner is None:
            return {"ok": False, "grund": "keine Bilder"}
        if aktion == "verwerfen":
            self._vorschlag_erledigt_add(dateien)
            return {"ok": True, "aktion": aktion, "anzahl": len(dateien)}
        if aktion == "neu":
            name = str(k.get("name", "")).strip()[:40]
            if not name:
                return {"ok": False, "grund": "Name fehlt"}
            kl = self.zustand.klasse_anlegen(name)
        elif aktion == "hintergrund":
            kl = next((x for x in self.zustand.klassen.values() if x.negativ), None) or self.zustand.klasse_anlegen("Hintergrund", True)
        elif aktion == "zu":
            try:
                kl = self.zustand.klassen.get(int(k.get("klasse")))
            except Exception:
                kl = None
            if kl is None:
                return {"ok": False, "grund": "Objekt unbekannt"}
        else:
            return {"ok": False, "grund": "aktion=neu|zu|hintergrund|verwerfen"}
        n = 0
        for d in dateien[:24]:                  # mehr Fotos bringen beim Chip-Lernen wenig
            b = cv2.imread(str(ordner / d))
            if b is not None and self.zustand.prototyp_speichern(kl.id, b):
                n += 1
        self._vorschlag_erledigt_add(dateien)
        try:
            self.rollen and self.rollen.protokoll("vorschlag", "/api/vorschlag_anwenden", {"aktion": aktion, "objekt": kl.name, "fotos": n})
        except Exception:
            pass
        return {"ok": n > 0, "aktion": aktion, "klasse": kl.name, "klasse_id": kl.id, "fotos": n,
                "hinweis": "Jetzt „Training …“ – erst danach erkennt die Anlage das Objekt."}

    def testlauf_starten(self) -> dict:
        if self._testlauf.get("laeuft"):
            return {"ok": False, "grund": "läuft schon", **self._testlauf}
        if self.testsatz is None or not self.testsatz.szenen:
            return {"ok": False, "grund": "Testsatz leer – erst Szenen aufnehmen (Prüfung › Testsatz)"}
        li = self.linie
        if li is not None and getattr(li, "aktiv", False):
            return {"ok": False, "grund": "Linie läuft – erst stoppen"}
        if not getattr(self.lerner, "klassen", None):
            return {"ok": False, "grund": "nichts gelernt – erst trainieren"}
        szenen = list(self.testsatz.szenen)
        self._testlauf = {"laeuft": True, "fertig": 0, "gesamt": len(szenen), "ergebnis": None, "fehler": ""}
        threading.Thread(target=self._testlauf_faden, args=(szenen,), daemon=True, name="testlauf").start()
        return {"ok": True, **self._testlauf}

    def _testlauf_faden(self, szenen) -> None:
        from ..schwelle import ist_aus_erkennung, kurve
        alt_art = self.zustand.betriebsart
        ergebnisse = []
        try:
            self.zustand.betriebsart = "betreiben"
            neg = self._negativ_namen()
            for sz in szenen:
                b = cv2.imread(str(self.testsatz.ordner / sz["datei"]))
                if b is None:
                    self._testlauf["fertig"] += 1
                    continue
                self._testbild = b
                start = getattr(self, "_takt", 0)
                bis = time.time() + 8.0
                while time.time() < bis and getattr(self, "_takt", 0) < start + 6:
                    time.sleep(0.03)
                erk = self.zustand.erkannt or {}
                ergebnisse.append({"id": sz.get("id"), "soll": list(sz.get("soll") or []),
                                   "ist": ist_aus_erkennung(erk.get("je_objekt") or [], neg)})
                self._testlauf["fertig"] += 1
            k = kurve(ergebnisse)
            k["aktuelle_schwelle"] = self.konfidenz_schwelle
            k["zeit"] = time.strftime("%Y-%m-%d %H:%M")
            k["build"] = BUILD
            k["einzeln"] = [{"id": e["id"], "soll": e["soll"], "ist": [[n, round(c, 3)] for n, c in e["ist"]]} for e in ergebnisse]
            self._testlauf["ergebnis"] = k
            try:
                (self.testsatz.ordner / "schwellenkurve.json").write_text(json.dumps(k, ensure_ascii=False, indent=1), encoding="utf-8")
            except Exception:
                pass
        except Exception as exc:
            self._testlauf["fehler"] = f"{type(exc).__name__}: {str(exc)[:100]}"
        finally:
            self._testbild = None
            self.zustand.betriebsart = alt_art
            self._testlauf["laeuft"] = False

    def _eaio_trigger(self) -> None:''')
    # --- Training-Hooks --------------------------------------------------
    s = ers(s, '''                    lambda l: chip_lernen(zustand, lerner, mit_var, l).as_dict()))''',
            '''                    lambda l: verarbeitung._nach_training(chip_lernen(zustand, lerner, mit_var, l)).as_dict()))''')
    s = ers(s, '''                bericht = chip_lernen(
                    zustand, lerner,
                    mit_varianten=bool(koerper.get("mit_varianten", True)))''', '''                bericht = verarbeitung._nach_training(chip_lernen(
                    zustand, lerner,
                    mit_varianten=bool(koerper.get("mit_varianten", True))))''')
    # --- Routen --------------------------------------------------------------
    s = ers(s, '''            if weg == "/api/sps":
                return self._json(verarbeitung.sps_status())''', '''            if weg == "/api/sps":
                return self._json(verarbeitung.sps_status())

            if weg == "/api/trend":
                from ..trend import auswerten
                return self._json(auswerten(verarbeitung.journal.lesen(seit=time.time() - 15 * 86400)))

            if weg == "/api/vorschlaege":
                try:
                    g = float((frage.get("grenze") or ["0.7"])[0])
                except ValueError:
                    g = 0.7
                return self._json(verarbeitung.vorschlaege(g))

            if weg == "/api/testlauf":
                t = dict(verarbeitung._testlauf)
                if t.get("ergebnis") is None and not t.get("laeuft"):
                    try:
                        p = verarbeitung.testsatz.ordner / "schwellenkurve.json"
                        if p.exists():
                            t["ergebnis"] = json.loads(p.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                t["szenen"] = len(verarbeitung.testsatz.szenen) if verarbeitung.testsatz else 0
                return self._json(t)''')
    s = ers(s, '''            if weg == "/api/sps":
                return self._json(verarbeitung.sps_einstellen(koerper))''', '''            if weg == "/api/sps":
                return self._json(verarbeitung.sps_einstellen(koerper))

            if weg == "/api/vorschlag_anwenden":
                return self._json(verarbeitung.vorschlag_anwenden(koerper))

            if weg == "/api/testlauf":
                if koerper.get("aktion") == "start":
                    return self._json(verarbeitung.testlauf_starten())
                return self._json({"ok": False, "grund": "aktion=start"}, 400)''')
    S.write_text(s, encoding="utf-8")
    print("server.py gepatcht")
