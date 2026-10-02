#!/usr/bin/env python3
"""A1 — Profil `stationaer` (SE Inspect 1.0, Build 1.9.38).

Exakte Ersetzungen in vorsa/web/server.py und tools/run_web.py; jede Stelle
wird genau einmal erwartet. Laeuft idempotent (zweiter Lauf: nichts zu tun).
"""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
S = ROOT / "vorsa" / "web" / "server.py"
R = ROOT / "tools" / "run_web.py"


def ers(text, alt, neu, n=1):
    k = text.count(alt)
    if k != n:
        raise SystemExit(f"FEHLER: {k}x statt {n}x gefunden:\n{alt[:160]}")
    return text.replace(alt, neu)


srv = S.read_text(encoding="utf-8")
if "1.9.38-stationaer" in srv:
    print("server.py: schon gepatcht")
else:
    # 1) Build
    srv = ers(srv, 'BUILD = "1.9.37-lernrahmen"', 'BUILD = "1.9.38-stationaer"')

    # 2) Profil + Band/Arm nur im Profil linie
    srv = ers(srv, '''        import os as _os
        from ..linie import LinienSteuerung, ArmKlient, band_bauen
        # VORSA_BAND: "sim" (Standard) | "echt" (L298N) | "relais"
        # (12-V-Relaismodul an GPIO, VORSA_BAND_PIN aendert den Pin).
        _band_art = _os.environ.get("VORSA_BAND", "sim").lower()
''', '''        import os as _os
        from ..linie import LinienSteuerung, ArmKlient, band_bauen
        # PROFIL (SE Inspect 1.0, 1.9.38): "stationaer" (Standard) =
        # Pruefzelle ohne Band, Arm und Zonen - die Linie bleibt als
        # schlafendes Objekt im Speicher (viele Pfade erwarten sie),
        # darf aber nie aktiv werden und das Band bleibt Simulation.
        # "linie" = bisheriges Verhalten (Band, Arm, Zonen).
        self.profil = _os.environ.get("VORSA_PROFIL", "").lower()
        if self.profil not in ("stationaer", "linie"):
            # Nicht gesetzt (z. B. aelteres start.sh): wer Band oder Arm
            # konfiguriert hat, meint die Linie - sonst die Pruefzelle.
            # Sonst haette ein sync ohne neues start.sh die Anlage still
            # von Band+Arm auf Simulation umgestellt (Audit 2026-10-02).
            band = _os.environ.get("VORSA_BAND", "sim").lower()
            arm = _os.environ.get("VORSA_ARM", "").lower() or _os.environ.get("VORSA_ARM_URL", "")
            self.profil = "linie" if (band in ("echt", "relais") or arm) else "stationaer"
        if self.profil == "stationaer" and getattr(quelle, "synthetisch", False):
            quelle.stationaer = True
            quelle.szene_halten_s = float(_os.environ.get("VORSA_SYNTH_HALTEN_S", "6"))
            quelle.szene_leer_s = float(_os.environ.get("VORSA_SYNTH_LEER_S", "2"))
        # VORSA_BAND: "sim" (Standard) | "echt" (L298N) | "relais"
        # (12-V-Relaismodul an GPIO, VORSA_BAND_PIN aendert den Pin).
        _band_art = _os.environ.get("VORSA_BAND", "sim").lower()
        if self.profil == "stationaer":
            _band_art = "sim"
''')
    srv = ers(srv, '''        self.arm_uno = None
        if _os.environ.get("VORSA_ARM", "").lower() in (
                "uno", "arduino", "seriell"):''', '''        self.arm_uno = None
        if self.profil == "linie" and _os.environ.get("VORSA_ARM", "").lower() in (
                "uno", "arduino", "seriell"):''')

    # 3) Stationaere Pruefung: Zustand
    srv = ers(srv, '''        self._pruef_stand = None          # letzte Statistik (fuer bereich_info)
''', '''        self._pruef_stand = None          # letzte Statistik (fuer bereich_info)
        # STATIONAERE PRUEFUNG (1.9.38): Ausloeser "hand" (Knopf / API)
        # oder "auto" (Szene steht still und ist neu). Gebucht wird je
        # Teil im Bild; danach ist die Szene "abgehakt", bis sie sich
        # aendert. Letzte Pruefung fuer die Anzeige.
        self.pruef_ausloeser = "hand"
        self._pruef_szene_seit = 0.0      # seit wann steht die Szene so?
        self._pruef_szene_sig = ""        # Kennung der aktuellen Szene
        self._pruef_gebucht_sig = ""      # Kennung der zuletzt gebuchten
        self._pruef_gebucht_zeit = 0.0
        self._pruef_letzte: Optional[dict] = None
        self._pruef_ausschnitt = None     # Bild der letzten Erkennung
        self._pruef_anfrage = False       # /api/pruefen wartet auf den Takt
''')

    # 4) je_objekt bekommt die Pixelbox mit (Archivbild je Teil)
    srv = ers(srv, '''                objekte.append({"name": ("unbekanntes Teil" if unbekannt
                                else erg["klasse"] if not erg.get("unklar")
                                else "unklar"),
                                "anteil": float(erg["sicherheit"]),
                                "unklar": bool(erg.get("unklar")),
                                "unbekannt": unbekannt,
                                "alle": erg.get("alle") or [],
                                # "Warum?": Lernfoto hinter dem Urteil.
                                "warum": erg.get("warum")})''', '''                try:
                    _ec = np.asarray(d.box.scaled(faktor).corners())
                    _box = [int(max(0, _ec[:, 0].min())), int(max(0, _ec[:, 1].min())),
                            int(_ec[:, 0].max()), int(_ec[:, 1].max())]
                except Exception:
                    _box = None
                objekte.append({"name": ("unbekanntes Teil" if unbekannt
                                else erg["klasse"] if not erg.get("unklar")
                                else "unklar"),
                                "anteil": float(erg["sicherheit"]),
                                "unklar": bool(erg.get("unklar")),
                                "unbekannt": unbekannt,
                                "alle": erg.get("alle") or [],
                                "box_px": _box,
                                # "Warum?": Lernfoto hinter dem Urteil.
                                "warum": erg.get("warum")})''')
    srv = ers(srv, '''            # Hintergrund-Teile verschwinden ganz: kein Rahmen, keine Zeile.
            dets = [d for d in dets if not d.meta.get("hintergrund")]
            if not objekte:''', '''            # Hintergrund-Teile verschwinden ganz: kein Rahmen, keine Zeile.
            dets = [d for d in dets if not d.meta.get("hintergrund")]
            # Stationaere Pruefung: das Bild, auf dem geurteilt wurde.
            self._pruef_ausschnitt = ausschnitt
            if not objekte:''')

    # 5) Pruefbuch-Takt: stationaer buchen (auto / angefragt)
    srv = ers(srv, '''            # PRUEFBUCH (Stufe 1): Live-Urteil des aktuellen Bilds plus
            # Sitzungsstatistik in jedem Zustand mitliefern.
            try:
                self._pruef_stand = self.pruefbuch.statistik(self._pruef_live())
                # Stufe 5: Einstellungen + Nachlern-Empfehlung mitgeben.
                ps = self._pruef_stand
                ps.update(self.pruef_einst())''', '''            # STATIONAERE PRUEFUNG (1.9.38): Knopf/API oder Automatik.
            if self.profil == "stationaer":
                try:
                    self._pruef_stationaer_takt(art)
                except Exception:
                    pass

            # PRUEFBUCH (Stufe 1): Live-Urteil des aktuellen Bilds plus
            # Sitzungsstatistik in jedem Zustand mitliefern.
            try:
                self._pruef_stand = self.pruefbuch.statistik(self._pruef_live())
                # Stufe 5: Einstellungen + Nachlern-Empfehlung mitgeben.
                ps = self._pruef_stand
                ps.update(self.pruef_einst())
                ps["profil"] = self.profil
                ps["letzte_pruefung"] = self._pruef_letzte
                ps["szene_steht"] = bool(
                    self._pruef_szene_sig and self._pruef_szene_seit
                    and time.time() - self._pruef_szene_seit >= self.PRUEF_STILL_S)
                ps["szene_gebucht"] = bool(
                    self._pruef_szene_sig
                    and self._pruef_szene_sig == self._pruef_gebucht_sig)''')

    # 6) Einstellungen: Ausloeser persistent
    srv = ers(srv, '''    def pruef_einst(self) -> dict:
        return {"schwelle": self.konfidenz_schwelle,
                "unbekannt_ziel": self.unbekannt_ziel}
''', '''    def pruef_einst(self) -> dict:
        return {"schwelle": self.konfidenz_schwelle,
                "unbekannt_ziel": self.unbekannt_ziel,
                "ausloeser": self.pruef_ausloeser}

    # -- STATIONAERE PRUEFUNG (SE Inspect 1.0, 1.9.38) ------------------
    PRUEF_STILL_S = 0.6        # so lange muss die Szene unveraendert stehen
    PRUEF_SPERRE_S = 1.5       # Mindestabstand zweier Buchungen

    def _pruef_szene_kennung(self) -> str:
        """Kennung der Szene: Namen + grobe Lage der Teile. Gleiche
        Kennung = dieselbe Szene; eine Buchung je Kennung."""
        erk = self.zustand.erkannt or {}
        objs = erk.get("je_objekt") or []
        if not objs:
            return ""
        teile = []
        for o in objs:
            b = o.get("box_px") or [0, 0, 0, 0]
            teile.append(f"{o.get('name', '')}:{b[0] // 24}:{b[1] // 24}")
        return "|".join(sorted(teile))

    def _pruef_urteil_teil(self, o: dict, neg: set) -> dict:
        """Urteil fuer EIN Teil - dieselben Regeln wie _pruef_live."""
        name = str(o.get("name") or "")
        konf = float(o.get("anteil") or 0.0)
        s = self.konfidenz_schwelle
        if o.get("unbekannt"):
            return {"urteil": "unbekannt", "name": "", "konfidenz": konf,
                    "grund": "nie gelernt - unbekanntes Teil"}
        if o.get("unklar") or not name or name == "unklar":
            return {"urteil": "unbekannt", "name": "", "konfidenz": konf,
                    "grund": "nicht sicher zugeordnet"}
        if name in neg:
            return {"urteil": "ausschuss", "name": name, "konfidenz": konf,
                    "grund": "Negativklasse"}
        if s is not None and konf < s:
            return {"urteil": "unbekannt", "name": name, "konfidenz": konf,
                    "grund": f"unter Schwelle {int(s * 100)} %"}
        return {"urteil": "gut", "name": name, "konfidenz": konf,
                "grund": "sicher benannt"}

    def _pruef_stationaer_buchen(self, grund: str = "hand") -> dict:
        """Alle Teile der aktuellen Szene ins Pruefbuch buchen."""
        erk = self.zustand.erkannt or {}
        objs = list(erk.get("je_objekt") or [])
        if not objs:
            return {"ok": False, "grund": "kein Teil im Bild", "teile": []}
        neg = self._negativ_namen()
        bild = self._pruef_ausschnitt
        teile = []
        for o in objs:
            u = self._pruef_urteil_teil(o, neg)
            crop = None
            try:
                b = o.get("box_px")
                if bild is not None and b and b[2] - b[0] >= 8 and b[3] - b[1] >= 8:
                    h, w = bild.shape[:2]
                    r = max(8, int(0.15 * max(b[2] - b[0], b[3] - b[1])))
                    crop = bild[max(0, b[1] - r):min(h, b[3] + r),
                                max(0, b[0] - r):min(w, b[2] + r)].copy()
                elif bild is not None:
                    crop = bild
            except Exception:
                crop = bild
            e = self.pruefbuch.buche(u["urteil"], u["name"], u["konfidenz"],
                                     u["grund"] + (" · Automatik" if grund == "auto" else ""),
                                     crop, "haupt")
            teile.append({"urteil": u["urteil"], "name": u["name"],
                          "konfidenz": round(u["konfidenz"], 3),
                          "grund": u["grund"], "bild": e.get("bild", ""),
                          "box_px": o.get("box_px")})
        gesamt = ("gut" if all(t["urteil"] == "gut" for t in teile)
                  else "ausschuss" if any(t["urteil"] == "ausschuss" for t in teile)
                  else "unbekannt")
        if gesamt == "unbekannt":
            self.alarmbuch.melde("pruef_unbekannt", "warn",
                                 "UNBEKANNT: Teil nicht zuordenbar", einmalig=True)
        elif gesamt == "ausschuss":
            self.alarmbuch.melde("pruef_ausschuss", "warn",
                                 "AUSSCHUSS erkannt", einmalig=True)
        self._pruef_letzte = {"zeit": time.time(), "ausloeser": grund,
                              "urteil": gesamt, "teile": teile}
        self._pruef_gebucht_sig = self._pruef_szene_sig or self._pruef_szene_kennung()
        self._pruef_gebucht_zeit = time.time()
        return {"ok": True, "urteil": gesamt, "teile": teile}

    def _pruef_stationaer_takt(self, art: str) -> None:
        """Einmal je Bild: Szene verfolgen, Automatik und Anfragen bedienen."""
        jetzt = time.time()
        sig = self._pruef_szene_kennung() if art == "betreiben" else ""
        if sig != self._pruef_szene_sig:
            self._pruef_szene_sig = sig
            self._pruef_szene_seit = jetzt if sig else 0.0
            if not sig:
                # Tisch leer: naechste Szene darf wieder gebucht werden,
                # auch wenn sie zufaellig dieselbe Kennung hat.
                self._pruef_gebucht_sig = ""
        if self._pruef_anfrage:
            self._pruef_anfrage = False
            self._pruef_antwort = self._pruef_stationaer_buchen("hand")
            return
        if (self.pruef_ausloeser == "auto" and sig
                and sig != self._pruef_gebucht_sig
                and jetzt - self._pruef_szene_seit >= self.PRUEF_STILL_S
                and jetzt - self._pruef_gebucht_zeit >= self.PRUEF_SPERRE_S):
            self._pruef_stationaer_buchen("auto")

    def pruefen_jetzt(self) -> dict:
        """/api/pruefen: naechstes Bild buchen und Ergebnis zurueckgeben."""
        if self.profil != "stationaer":
            return {"ok": False, "grund": "nur im Profil stationaer"}
        if str(self.zustand.betriebsart) != "betreiben":
            return {"ok": False, "grund": "Betriebsart Erkennung waehlen"}
        self._pruef_antwort = None
        self._pruef_anfrage = True
        bis = time.time() + 3.0
        while time.time() < bis:
            a = getattr(self, "_pruef_antwort", None)
            if a is not None:
                return a
            time.sleep(0.03)
        self._pruef_anfrage = False
        return {"ok": False, "grund": "kein Bild innerhalb von 3 s"}

    def pruef_ausloeser_setzen(self, art: str) -> dict:
        art = "auto" if str(art).lower() == "auto" else "hand"
        self.pruef_ausloeser = art
        p = self._pruef_einst_pfad()
        try:
            if p:
                d = {}
                if p.exists():
                    d = json.loads(p.read_text(encoding="utf-8"))
                d["ausloeser"] = art
                p.write_text(json.dumps(d), encoding="utf-8")
        except Exception:
            pass
        return self.pruef_einst()
''')
    srv = ers(srv, '''                self.unbekannt_ziel = float(d.get("unbekannt_ziel", 10.0))
        except Exception:
            pass
''', '''                self.unbekannt_ziel = float(d.get("unbekannt_ziel", 10.0))
                if d.get("ausloeser") in ("hand", "auto"):
                    self.pruef_ausloeser = d["ausloeser"]
        except Exception:
            pass
''')
    srv = ers(srv, '''                p.write_text(json.dumps({
                    "schwelle": self.konfidenz_schwelle,
                    "unbekannt_ziel": self.unbekannt_ziel}), encoding="utf-8")''', '''                p.write_text(json.dumps({
                    "schwelle": self.konfidenz_schwelle,
                    "unbekannt_ziel": self.unbekannt_ziel,
                    "ausloeser": self.pruef_ausloeser}), encoding="utf-8")''')

    # 7) Routen: /api/pruefen, Ausloeser in /api/pruef_einst, Linie sperren, Profil im Zustand
    srv = ers(srv, '''            if weg == "/api/pruef_einst":
                # Stufe 5: {schwelle: 0..1 | null, unbekannt_ziel: %}
                return self._json(verarbeitung.pruef_einst_setzen(''', '''            if weg == "/api/pruefen":
                # STATIONAER (1.9.38): Szene jetzt pruefen und buchen.
                return self._json(verarbeitung.pruefen_jetzt())

            if weg == "/api/pruef_einst":
                # Stufe 5: {schwelle: 0..1 | null, unbekannt_ziel: %}
                # 1.9.38: {ausloeser: "hand"|"auto"}
                if koerper.get("ausloeser") in ("hand", "auto"):
                    return self._json(verarbeitung.pruef_ausloeser_setzen(
                        koerper["ausloeser"]))
                return self._json(verarbeitung.pruef_einst_setzen(''')
    srv = ers(srv, '''                li = verarbeitung.linie
                if koerper.get("takt") in ("fluss", "einzel"):''', '''                li = verarbeitung.linie
                if verarbeitung.profil != "linie" and koerper.get("aktiv"):
                    return self._json({"fehler": "Profil stationaer: keine Linie "
                                       "(Start mit VORSA_PROFIL=linie)"}, 409)
                if koerper.get("takt") in ("fluss", "einzel"):''')
    srv = ers(srv, '''                d = zustand.as_dict()
                try:
                    d["lernen"] = (verarbeitung.lerner.as_dict()''', '''                d = zustand.as_dict()
                d["profil"] = getattr(verarbeitung, "profil", "linie")
                try:
                    d["lernen"] = (verarbeitung.lerner.as_dict()''')
    srv = ers(srv, '''        from ..synth_objects import make_scene
        self._zaehler += 1
        szene = make_scene(size=self.groesse, num_classes=config.NUM_CLASSES,
                           cell_px=self.groesse / config.GRID,
                           seed=self._zaehler)
        return szene.image
''', '''        from ..synth_objects import make_scene
        self._zaehler += 1
        if getattr(self, "stationaer", False):
            # STATIONAER (1.9.38): wie ein Tisch, auf den jemand Teile legt -
            # eine Szene steht szene_halten_s still, dann ist der Tisch
            # leer_s lang leer, dann kommt die naechste. So lassen sich
            # Automatik-Ausloeser und Pruefbuch ohne Kamera vorfuehren.
            takt = float(self.szene_halten_s) + float(self.szene_leer_s)
            t = time.time() - getattr(self, "_t0", 0.0)
            if not getattr(self, "_t0", 0.0):
                self._t0 = time.time()
                t = 0.0
            nr = int(t // takt)
            if t - nr * takt >= self.szene_halten_s:
                leer = np.full((self.groesse, self.groesse, 3), 34, np.uint8)
                time.sleep(0.05)
                return leer
            seed = 1000 + nr
            if seed != getattr(self, "_szene_seed", None):
                self._szene_seed = seed
                self._szene_bild = make_scene(
                    size=self.groesse, num_classes=config.NUM_CLASSES,
                    cell_px=self.groesse / config.GRID, seed=seed).image
            time.sleep(0.05)
            return self._szene_bild
        szene = make_scene(size=self.groesse, num_classes=config.NUM_CLASSES,
                           cell_px=self.groesse / config.GRID,
                           seed=self._zaehler)
        return szene.image
''')
    S.write_text(srv, encoding="utf-8")
    print("server.py gepatcht")

rw = R.read_text(encoding="utf-8")
if "--profil" in rw:
    print("run_web.py: schon gepatcht")
else:
    rw = ers(rw, '''    ap.add_argument("--anzeige", type=int, default=960,''', '''    ap.add_argument("--profil", choices=("stationaer", "linie"), default=None,
                    help="stationaer (Standard): Pruefzelle ohne Band/Arm/Zonen; "
                         "linie: Band, Arm und Zonen (wie VORSA_PROFIL)")
    ap.add_argument("--anzeige", type=int, default=960,''')
    rw = ers(rw, '''    args = ap.parse_args()
''', '''    args = ap.parse_args()
    if args.profil:
        import os
        os.environ["VORSA_PROFIL"] = args.profil
''')
    R.write_text(rw, encoding="utf-8")
    print("run_web.py gepatcht")
