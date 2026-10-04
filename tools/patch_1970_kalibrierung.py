#!/usr/bin/env python3
"""1.9.70: Schwellen-Vorschlag mit Augenmass, Kalibrierung je Objekt,
Leerbild passt zur Drehung.

Anlass (Pi, 2026-10-04): der Vorschlag aus dem Testsatz stand auf 96 % -
danach wurde fast nichts mehr benannt. Die SD-Karte erreicht richtig erkannt
nur ~0,6, der Inbusschluessel ~0,9; eine gemeinsame Schwelle passt fuer beide
nicht. Und das Leerbild war vor der Drehung aufgenommen - leere Szenen
lieferten Phantomteile.

  - vorsa/schwelle.py (neue Regel, kalibrierung_aus/kalibriert) - schon da
  - edge_learn: Sicherheit je Objekt kalibriert (roh / typisch x 0,9)
  - Server: Testlauf misst roh (ohne Kalibrierung, ohne Unbekannt-Grenze),
    leitet die Kalibrierung ab, rechnet die Kurve kalibriert, speichert
    kalibrierung.json; nach neuem Training als "veraltet" markiert
  - Leerbild merkt sich die Drehung; passt sie nicht mehr, wird es nicht
    benutzt und die Oberflaeche sagt es
  - Oberflaeche: Kalibrierung + Kompromiss-Hinweis im Block "Schwelle aus
    dem Testsatz", Warnung beim Leerbild
Idempotent."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "vorsa/web/static/index.html"
S = ROOT / "vorsa/web/server.py"
L = ROOT / "vorsa/edge_learn.py"
E = ROOT / "vorsa/web/static/sprache_en.js"
h, s, l, e = (p.read_text(encoding="utf-8") for p in (H, S, L, E))
if "_kalib_laden" in s:
    print("schon angewendet"); raise SystemExit(0)


def ers(t, a, b, n=1):
    assert t.count(a) == n, (a[:70], t.count(a)); return t.replace(a, b)


# ---------------------------------------------------------------- edge_learn
l = ers(l, "anteile = np.minimum(wiederfindung, reinheit)",
        "anteile = self._kalibriere(np.minimum(wiederfindung, reinheit))", n=2)
l = ers(l, "    def _urteil(self, x: np.ndarray, pro_klasse: np.ndarray, sieger) -> dict:",
'''    def _kalibriere(self, anteile: np.ndarray) -> np.ndarray:
        """1.9.70: Sicherheit je Objekt kalibriert (siehe vorsa/schwelle.py).
        kalibrierung = {Objektname: typische rohe Sicherheit richtiger
        Treffer}; ohne Eintrag bleibt der Wert roh."""
        kal = getattr(self, "kalibrierung", None) or {}
        if not kal:
            return anteile
        a = np.array(anteile, dtype=np.float64)
        for i, n in enumerate(self.klassen):
            r = kal.get(n)
            if r:
                a[i] = min(1.0, a[i] / float(r) * 0.9)
        return a

    def _urteil(self, x: np.ndarray, pro_klasse: np.ndarray, sieger) -> dict:''')

# ---------------------------------------------------------------- Server
s = ers(s, 'BUILD = "1.9.69-ruhig"', 'BUILD = "1.9.70-kalibrierung"')
# Kalibrierung laden (nach der Drehung)
s = ers(s, """            self.drehung = _dw if _dw in (0, 90, 180, 270) else 0
        except Exception:
            pass
""", """            self.drehung = _dw if _dw in (0, 90, 180, 270) else 0
        except Exception:
            pass
        # 1.9.70: Kalibrierung je Objekt aus dem letzten Testlauf.
        self._kalib = {}
        self._kalib_laden()
""")
s = ers(s, "    # ---- 1.1: Training merken, Vorschlaege, Testlauf -----------------------\n",
'''    # ---- 1.9.70: Kalibrierung je Objekt ------------------------------------
    def _kalib_pfad(self):
        return Path(self.zustand.ordner) / "kalibrierung.json"

    def _kalib_laden(self) -> None:
        try:
            self._kalib = json.loads(self._kalib_pfad().read_text(encoding="utf-8"))
        except Exception:
            self._kalib = {}
        self._kalib_anwenden()

    def _kalib_anwenden(self) -> None:
        if self.lerner is not None:
            try:
                self.lerner.kalibrierung = dict((self._kalib or {}).get("werte") or {})
            except Exception:
                pass

    def _kalib_speichern(self, werte: dict, szenen: int) -> None:
        self._kalib = {"werte": dict(werte), "szenen": int(szenen), "zeit": time.strftime("%Y-%m-%d %H:%M"),
                       "veraltet": False}
        try:
            self._kalib_pfad().write_text(json.dumps(self._kalib, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception:
            pass
        self._kalib_anwenden()

    def kalibrierung_stand(self) -> dict:
        return dict(self._kalib or {})

    def kalibrierung_weg(self) -> dict:
        self._kalib = {}
        try:
            self._kalib_pfad().unlink(missing_ok=True)
        except Exception:
            pass
        self._kalib_anwenden()
        return {"ok": True}

    # ---- 1.1: Training merken, Vorschlaege, Testlauf -----------------------
''')
# nach Training: Kalibrierung behalten, aber als veraltet markieren
s = ers(s, """            if getattr(bericht, "ok", False):
                self.journal.training()
        except Exception:
            pass
        return bericht""", """            if getattr(bericht, "ok", False):
                self.journal.training()
                if self._kalib.get("werte"):
                    self._kalib["veraltet"] = True
                    try:
                        self._kalib_pfad().write_text(json.dumps(self._kalib, ensure_ascii=False, indent=1), encoding="utf-8")
                    except Exception:
                        pass
                self._kalib_anwenden()
        except Exception:
            pass
        return bericht""")
# Testlauf: roh messen, Kalibrierung ableiten, Kurve kalibriert
s = ers(s, """        from ..schwelle import ist_aus_erkennung, kurve
        alt_art = self.zustand.betriebsart
        ergebnisse = []
        try:
            self.zustand.betriebsart = "betreiben"
""", """        from ..schwelle import ist_aus_erkennung, kurve, kalibrierung_aus, kalibriert
        alt_art = self.zustand.betriebsart
        ergebnisse = []
        ler = self.lerner
        alt_kal = dict(getattr(ler, "kalibrierung", None) or {})
        hatte_ab = "UNBEKANNT_AB" in getattr(ler, "__dict__", {})
        alt_ab = getattr(ler, "UNBEKANNT_AB", 0.55)
        try:
            # ROH messen: ohne Kalibrierung und ohne Unbekannt-Grenze - beides
            # wird danach nachgerechnet (sonst gingen Namen unter der Grenze
            # verloren und die Kalibrierung misst sich selbst).
            ler.kalibrierung = {}
            ler.UNBEKANNT_AB = 0.0
            self.zustand.betriebsart = "betreiben"
""")
s = ers(s, """            k = kurve(ergebnisse)
            k["aktuelle_schwelle"] = self.konfidenz_schwelle""", """            ler.kalibrierung = alt_kal
            if hatte_ab:
                ler.UNBEKANNT_AB = alt_ab
            else:
                try:
                    del ler.UNBEKANNT_AB
                except Exception:
                    pass
            ab = float(getattr(ler, "UNBEKANNT_AB", 0.55))
            kal = kalibrierung_aus(ergebnisse)
            if kal:
                self._kalib_speichern(kal, len(ergebnisse))
            else:
                kal = dict((self._kalib or {}).get("werte") or {})
            k = kurve(kalibriert(ergebnisse, kal, ab))
            k["kalibrierung"] = kal
            k["roh_vorschlag"] = kurve(kalibriert(ergebnisse, {}, ab)).get("vorschlag")
            k["aktuelle_schwelle"] = self.konfidenz_schwelle""")
s = ers(s, """        finally:
            self._testbild = None
            self.zustand.betriebsart = alt_art
            self._testlauf["laeuft"] = False""", """        finally:
            self._testbild = None
            try:
                if getattr(ler, "UNBEKANNT_AB", None) == 0.0:
                    if hatte_ab:
                        ler.UNBEKANNT_AB = alt_ab
                    else:
                        del ler.UNBEKANNT_AB
                if not getattr(ler, "kalibrierung", None):
                    self._kalib_anwenden()
            except Exception:
                pass
            self.zustand.betriebsart = alt_art
            self._testlauf["laeuft"] = False""")
# Testlauf-Routen: Kalibrierung zeigen / verwerfen
s = ers(s, """                t["szenen"] = len(verarbeitung.testsatz.szenen) if verarbeitung.testsatz else 0
                return self._json(t)""", """                t["szenen"] = len(verarbeitung.testsatz.szenen) if verarbeitung.testsatz else 0
                t["kalibrierung"] = verarbeitung.kalibrierung_stand()
                return self._json(t)""")
s = ers(s, """                if koerper.get("aktion") == "start":
                    return self._json(verarbeitung.testlauf_starten())
                return self._json({"ok": False, "grund": "aktion=start"}, 400)""", """                if koerper.get("aktion") == "start":
                    return self._json(verarbeitung.testlauf_starten())
                if koerper.get("aktion") == "kalibrierung_weg":
                    return self._json(verarbeitung.kalibrierung_weg())
                return self._json({"ok": False, "grund": "aktion=start|kalibrierung_weg"}, 400)""")

# Leerbild + Drehung
s = ers(s, """                b = cv2.imread(str(pfad))
                if b is not None:
                    e = {"bild": b, "zeit": pfad.stat().st_mtime}""", """                b = cv2.imread(str(pfad))
                if b is not None:
                    e = {"bild": b, "zeit": pfad.stat().st_mtime}
                    # 1.9.70: Drehung beim Aufnehmen (Begleitdatei). Alte
                    # Leerbilder ohne Begleitdatei: aelter als die letzte
                    # Drehung -> unbekannt (= passt nicht).
                    try:
                        e["drehung"] = int(json.loads(pfad.with_suffix(".json").read_text(encoding="utf-8")).get("drehung", 0))
                    except Exception:
                        try:
                            dj = Path(self.zustand.ordner) / "drehung.json"
                            dw = int(json.loads(dj.read_text(encoding="utf-8")).get("drehung", 0)) if dj.exists() else 0
                            e["drehung"] = -1 if (dj.exists() and dj.stat().st_mtime > e["zeit"]) else dw
                        except Exception:
                            e["drehung"] = 0""")
s = ers(s, """        self._leerbild[quelle] = {"bild": median, "rausch": rausch,
                                  "zeit": time.time()}
        o = self._leerbild_ordner()
        if o is not None:
            try:
                cv2.imwrite(str(o / f"{quelle}.png"), median)
                cv2.imwrite(str(o / f"{quelle}_rausch.png"), rausch)""", """        dreh = int(getattr(self, "drehung", 0) or 0) if quelle == "haupt" else 0
        self._leerbild[quelle] = {"bild": median, "rausch": rausch,
                                  "zeit": time.time(), "drehung": dreh}
        o = self._leerbild_ordner()
        if o is not None:
            try:
                cv2.imwrite(str(o / f"{quelle}.png"), median)
                cv2.imwrite(str(o / f"{quelle}_rausch.png"), rausch)
                (o / f"{quelle}.json").write_text(json.dumps({"drehung": dreh}), encoding="utf-8")""")
s = ers(s, """            (o / f"{quelle}_rausch.png").unlink(missing_ok=True)
        return {"ok": True, **self.leerbild_stand()}""", """            (o / f"{quelle}_rausch.png").unlink(missing_ok=True)
            (o / f"{quelle}.json").unlink(missing_ok=True)
        return {"ok": True, **self.leerbild_stand()}""")
s = ers(s, """    def leerbild_stand(self) -> dict:
        return {"leerbild": {q: time.strftime("%H:%M", time.localtime(v["zeit"]))
                             for q, v in self._leerbild.items()}}""", """    def _leerbild_passt(self, quelle: str, v: dict) -> bool:
        if str(quelle) != "haupt":
            return True
        return int(v.get("drehung", 0)) == int(getattr(self, "drehung", 0) or 0)

    def leerbild_stand(self) -> dict:
        # Ein Leerbild, das nicht zur aktuellen Drehung passt, gilt als
        # nicht vorhanden (Schritt "Leerbild" wieder offen) - und wird
        # ausdruecklich als veraltet gemeldet.
        return {"leerbild": {q: time.strftime("%H:%M", time.localtime(v["zeit"]))
                             for q, v in self._leerbild.items() if self._leerbild_passt(q, v)},
                "leerbild_veraltet": [q for q, v in self._leerbild.items() if not self._leerbild_passt(q, v)]}""")
s = ers(s, """        v = self._leerbild.get(str(quelle))
        if not v:
            return None
        b = v["bild"]""", """        v = self._leerbild.get(str(quelle))
        if not v or not self._leerbild_passt(quelle, v):
            return None
        b = v["bild"]""")

# ---------------------------------------------------------------- Oberflaeche
# Leerbild-Warnung im Einrichten-Block
h = ers(h, """      <button class="mini ${L ? "" : "an"}" data-tat="leerbild" data-art="haupt">${L ? "Neu merken" : "Leerbild merken"}</button>
      ${L ? `<button class="mini gefahr" data-tat="leerbild_weg" data-art="haupt">Verwerfen</button>` : ""}""",
"""      <button class="mini ${L ? "" : "an"}" data-tat="leerbild" data-art="haupt">${L ? "Neu merken" : "Leerbild merken"}</button>
      ${L ? `<button class="mini gefahr" data-tat="leerbild_weg" data-art="haupt">Verwerfen</button>` : ""}
      ${(((Z.bereich || {}).leerbild_veraltet) || []).includes(quelleVon("haupt")) ? `<div class="warnzeile" style="margin-top:8px">Das Leerbild passt nicht mehr – das Bild wurde seit der Aufnahme gedreht. Es wird nicht benutzt. Teil wegnehmen und neu merken.</div>` : ""}""")
# Hinweis auch in der Pruefspalte (Phantomteile!)
h = ers(h, """    ${TREND && TREND.drift && TREND.drift.status === "sinkt" ?""", """    ${(((Z.bereich || {}).leerbild_veraltet) || []).length ? `<div class="kasten warn tr-warn"><b>Leerbild veraltet</b> — seit der Aufnahme wurde das Bild gedreht. Ohne passendes Leerbild meldet die Anlage leicht Teile, wo keine sind.
      <button class="mini" style="margin-top:6px" data-tat="modus" data-modus="einrichten">Zum Einrichten</button></div>` : ""}
    ${TREND && TREND.drift && TREND.drift.status === "sinkt" ?""")
# Auto-Schwelle: Kompromiss + Kalibrierung
h = ers(h, """    inhalt = `<div class="as-ergebnis">${E.vorschlag != null
        ? `Vorschlag: <b>${Math.round(E.vorschlag * 100)} %</b> — die kleinste Schwelle, bei der höchstens ${(E.ziel_falsch_sicher * 100).toLocaleString(SPRACHE === "en" ? "en-GB" : "de-DE")} % der Teile falsch-sicher benannt werden.`
        : "Keine Schwelle erreicht das Ziel – erst mehr und bessere Lernfotos, dann neu messen."}""", """    inhalt = `<div class="as-ergebnis">${E.vorschlag == null
        ? "Keine Schwelle erreicht das Ziel – erst mehr und bessere Lernfotos, dann neu messen."
        : E.ziel_erreicht === false
        ? `Kompromiss: <b>${Math.round(E.vorschlag * 100)} %</b> — beste Abwägung zwischen Treffern und Falschbenennungen.`
        : `Vorschlag: <b>${Math.round(E.vorschlag * 100)} %</b> — die meisten Treffer bei höchstens ${(E.ziel_falsch_sicher * 100).toLocaleString(SPRACHE === "en" ? "en-GB" : "de-DE")} % falsch-sicher.`}""")
h = ers(h, """  return `<div class="as-block"><h4>Schwelle aus dem Testsatz</h4>""", """  const K = L.kalibrierung || {}, KW = K.werte || {};
  const kn = Object.keys(KW);
  inhalt += kn.length ? `<div class="as-kalib"><b>Kalibrierung je Objekt</b>${K.veraltet ? ` <span class="as-alt">vom letzten Training – Testlauf wiederholen</span>` : ""}
      <div class="as-kliste">${kn.map(n => `<span><i>${txt(n)}</i> typisch ${Math.round(KW[n] * 100)} % → 90 %</span>`).join("")}</div>
      <small>Jedes Objekt erreicht richtig erkannt eine andere Sicherheit. Die Anlage rechnet sie so um, dass ein typischer Treffer überall bei 90 % liegt – dann passt eine Schwelle für alle.</small>
      <div class="knopfreihe" style="margin-top:6px"><button class="mini gefahr" data-tat="kalib_weg">Kalibrierung verwerfen</button></div></div>`
    : `<div class="as-kalib leise"><small>Nach dem Testlauf wird die Sicherheit je Objekt kalibriert (ab 3 richtig erkannten Einzelszenen je Objekt).</small></div>`;
  return `<div class="as-block"><h4>Schwelle aus dem Testsatz</h4>""")
h = ers(h, """      ${E.hinweis ? `<div class="warnzeile">${txt(E.hinweis)}</div>` : ""}""", """      ${(E.hinweise || (E.hinweis ? [E.hinweis] : [])).map(t => `<div class="warnzeile">${txt(t)}</div>`).join("")}""")
h = ers(h, """.as-ergebnis { font-size:12.5px; margin:6px 0; }""", """.as-ergebnis { font-size:12.5px; margin:6px 0; }
.as-kalib { margin-top:12px; padding:10px 12px; border:1px solid var(--rand,#333b43); border-radius:8px; font-size:12px; }
.as-kalib small { display:block; color:var(--leise,#8a94a0); margin-top:6px; line-height:1.45; }
.as-kliste { display:flex; flex-wrap:wrap; gap:6px 14px; margin-top:6px; font-variant-numeric:tabular-nums; }
.as-kliste i { font-style:normal; font-weight:600; margin-right:4px; }
.as-alt { color:#f59e0b; font-size:11px; margin-left:6px; }""")
h = ers(h, """  if (tat === "as_uebernehmen") {""", """  if (tat === "kalib_weg") {
    await hole("/api/testlauf", { aktion: "kalibrierung_weg" });
    TL_ZEIT = 0; await elfLaden(); zeichneEinstellungen(); return;
  }
  if (tat === "as_uebernehmen") {""")

e = ers(e, "if (window.spracheNachladen) window.spracheNachladen();", """/* ---- Nachtrag 23 (1.9.70 Kalibrierung) ---- */
Object.assign(window.SPRACHEN.en, {
  "Kompromiss:": "Compromise:", "— beste Abwägung zwischen Treffern und Falschbenennungen.": "— best balance between hits and false names.",
  "— die meisten Treffer bei höchstens {} % falsch-sicher.": "— the most hits with at most {} % falsely confident.",
  "Kalibrierung je Objekt": "Calibration per object", "vom letzten Training – Testlauf wiederholen": "from the last training – repeat the test run",
  "typisch {} % → 90 %": "typically {} % → 90 %",
  "Jedes Objekt erreicht richtig erkannt eine andere Sicherheit. Die Anlage rechnet sie so um, dass ein typischer Treffer überall bei 90 % liegt – dann passt eine Schwelle für alle.": "Each object reaches a different confidence when recognised correctly. The cell rescales it so a typical hit sits at 90 % for every object – then one threshold fits all.",
  "Kalibrierung verwerfen": "Discard calibration",
  "Nach dem Testlauf wird die Sicherheit je Objekt kalibriert (ab 3 richtig erkannten Einzelszenen je Objekt).": "After the test run, confidence is calibrated per object (from 3 correctly recognised single scenes per object).",
  "Keine Schwelle erreicht beides – viele Treffer UND kaum Falschbenennungen. Der Vorschlag ist ein Kompromiss ({} % Treffer, {} % falsch-sicher). Besser wird es nur durch bessere Trennung: Leerbild neu, mehr Lernfotos in verschiedenen Lagen, Störteile als Hintergrund lernen.": "No threshold achieves both – many hits AND hardly any false names. The suggestion is a compromise ({} % hits, {} % falsely confident). Only better separation helps: new empty image, more training photos in different positions, teach stray parts as background.",
  "Das Leerbild passt nicht mehr – das Bild wurde seit der Aufnahme gedreht. Es wird nicht benutzt. Teil wegnehmen und neu merken.": "The empty image no longer fits – the image was rotated since it was captured. It is not used. Remove the part and capture it again.",
  "Leerbild veraltet": "Empty image outdated",
  "— seit der Aufnahme wurde das Bild gedreht. Ohne passendes Leerbild meldet die Anlage leicht Teile, wo keine sind.": "— the image was rotated since it was captured. Without a matching empty image the cell easily reports parts where there are none.",
  "Zum Einrichten": "Go to Set up"
});

if (window.spracheNachladen) window.spracheNachladen();""")

for p, t in ((H, h), (S, s), (L, l), (E, e)):
    p.write_text(t, encoding="utf-8")
print("ok 1.9.70")
