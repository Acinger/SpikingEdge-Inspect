# Änderungen

Format: Build-String (Footer) · Datum · Inhalt. Älteres siehe `PROJEKTBERICHT_ALPHA.md` Anhang B.

## 1.0.0-alpha.1 (2026-10-02) · erste öffentliche Alpha

- Versionsstring `1.0.0-alpha.1`; `RELEASE_NOTES.md` (Umfang, bekannte Grenzen), CITATION auf das Code-Repository, README-Status. Inhaltlich identisch mit 1.9.55-einkamera. Export mit `tools/release_export.py`, Tag `v1.0.0-alpha.1`.

## 1.9.55-einkamera (2026-10-02)

- Einkamera-Version: Anlieferung und Abholung kommen aus der Hauptkamera. Quellen-Dropdowns, "Blick 2" und Lernzonen sind ausgeblendet; /api/linie_quelle mit Fremdquelle -> 409. Gespeicherte Fremdquellen (z. B. picam1 -> schwarzes Feld "list index out of range") werden beim Start auf die Hauptkamera gelegt, blick2.json bleibt unangetastet. Zweitkamera-Betrieb: VORSA_ZWEITKAMERA=1 in start.local.sh.

## 1.9.54-logo (2026-10-02)

- Marke: SpikingEdge-Icon (Original) links, "INSPECT" daneben, eine Zeile, kein Umbruch; Server liefert /static/*.webp|svg.
- Einkamera-Version: alter Kamera-Streifen (#kamHaupt, "Mehr"-Regler) entfernt; jeder Kamera-Knopf (Hauptbild, Zonen, Rechtsklick) oeffnet das Kamera-Dock. Gemerkte Streifen-Zustaende werden geloescht.
- Rechtsklick-Menue bleibt im Bild (Hoehe begrenzt, scrollt) statt abgeschnitten zu werden.
- Englisch: "Leerbild ✓ 12:49", Leerbild-Meldungen und Titel uebersetzt; {}-Muster erfasst Uhrzeit/Datum.

## 1.9.53-se-inspect · 2026-10-02 · A11/A12 Umbenennung

- Programm: Marke „SE INSPECT · SpikingEdge · UI 2.3“ in der Seitenleiste, Fenstertitel „SE Inspect · SpikingEdge“, Versionszeile „SE Inspect · UI 2.3 · früher VORSA INSPECT“, Hinweise und Startbanner auf SE Inspect / SE-M3. Paketname `vorsa/`, Dateinamen (`vorsa_m3.fbz`, `vorsa_daten/`) und Umgebungsvariablen (`VORSA_*`) bleiben bewusst unverändert.
- Website: alle Seiten außer Lab Notes (historisch) und Rechtsseiten auf SE Inspect / SE-M3; CTA „Get SE Inspect“; Projektseite trägt „formerly VORSA INSPECT“. URLs unverändert (indexiert).

## 1.9.52-kamdock · 2026-10-02

- **Kamera-Dock** (Anmerkung Ace): Kameraeinstellungen als Tafel unter dem Bild, die mit dem Kamera-Knopf (oder Rechtsklick → Kamera) animiert nach oben aufklappt; das Bild rückt zusammen, Pfeil schließt. Vier Spalten auf einen Blick: Bild (Belichtungszeit, Verstärkung, Fokus, Scharf stellen, Licht −/+, Auto alle) · Farbe (Weißabgleich, Kontrast, Sättigung, Schärfe, Festhalten, Startwerte) · Fenster (Größe, Pixelmaß, Schärfewert, Bilder mitteln) · Hintergrund & Sichern (Leerbild, Einstellung sichern/laden). Ersetzt die schmale Kamera-Leiste des Hauptbilds; Zustand wird gemerkt.
- Block „Erkennungsdetails“ unter dem Bild ist im Betrieb weg (doppelt zum Live-Urteil); erscheint nur noch für Vorgänge und Hinweise.
- Live-Urteil: findet die Geometrie keinen Umriss und das Urteil stammt vom Gesamtbild, steht das jetzt dabei (mit Knopf „Leerbild merken“) — ohne Umriss gibt es auch keine Objektrahmen zu zeichnen.
- Smoke `tools/smoke_kamdock.js`; Patch `tools/patch_1952_kamdock.py`.

## 1.9.51-audit · 2026-10-02 · Freigabe-Audit (siehe AUDIT_FREIGABE.md)

- Profil-Ableitung ohne `VORSA_PROFIL`: Band `echt`/`relais` oder Arm gesetzt → `linie`, sonst `stationaer` (B1). `start.sh` generisch, Maschinenwerte in `start.local.sh` (nicht versioniert); `sync.ps1` überträgt `start.sh`, `vorsa.service`, `install.sh`, `CHANGELOG.md` und legt `start.local.sh` auf dem Pi einmalig an (B1/B5).
- API: Nicht-Objekt-JSON wird als leerer Körper behandelt; jede Routen-Ausnahme antwortet als JSON 400 (Eingabefehler) oder 500 (sonst) statt die Verbindung abzubrechen; Stack nur bei 500, einmal je Meldung (B2).
- Mehrbild: uint16/OpenCV-Summe, ~4× schneller (B3). `install.sh --laptop`: numpy 2 erlaubt, Pi bleibt `numpy<2` (B4). Vollbild ohne Fullscreen-API ohne Ausnahme (B6). Smokes setzen ihren Ausgangszustand selbst (B7).
- Neue Audit-Werkzeuge: `tools/audit_ui_rundgang.js` (211 Schritte je Profil, JS-Fehler + unübersetzte Texte), `tools/audit_api_fuzz.py` (502 Aufrufe, Traversal).

## 1.9.50-einrichten · 2026-10-02

- Modus Kamera (Einrichten), rechte Spalte (Anmerkung Ace „nichts Nützliches“): **Einrichtungs-Checkliste** (Bild scharf, Fenster groß genug, Leerbild gemerkt, Kamera festgehalten, mit Zähler), Aufnahmefenster, **Kamera-Block** (Scharf stellen, Licht −/+, Auto alle, Festhalten, Automatik-Schalter, Regler Belichtungszeit/Verstärkung/Fokus/Weißabgleich/Kontrast/Sättigung/Schärfe), **Leerbild-Block** (merken/neu/verwerfen mit Stand), **Bilder mitteln** (stationaer), dann Chipbild, Drift, Einstellungen sichern.
- **Rechtsklick auf das Kamerabild** öffnet das Anzeige-Menü am Mauszeiger: Vorlagen Sauber/Arbeiten/Prüfen, Schalter Aufnahmerahmen/Abdunkeln/Objektrahmen/Konturen/Längsachse/Beschriftung/Legende, dazu Aktionen Zoom zurücksetzen, Kamera-Leiste, Fenster −/+ (Lernen/Einrichten), Leerbild, Prüfen (Betrieb).
- Smoke `tools/smoke_einrichten.js`; Patch `tools/patch_1950_einrichten.py`.

## 1.9.49-scroll · 2026-10-02

- Prüf-Kachel scrollt als Ganzes (Anmerkung Ace: Details waren nicht erreichbar): Kopf mit Reitern bleibt oben stehen, Live-Urteil, PRÜFEN, Zähler, Testsatz und die Detailblöcke laufen in einer Spalte durch. Patch `tools/patch_1949_scroll.py`.

## 1.9.48-liveurteil · 2026-10-02

- Live-Urteil ganz oben in der Prüf-Kachel (Anmerkung Ace): großes Urteil in Ampelfarbe, Teilname groß, Konfidenzbalken mit Schwellenmarke und Prozent, Grund, Aufschlüsselung je Klasse als Balken (Sieger hervorgehoben), kurze Aufpop-Animation beim Wechsel. Danach PRÜFEN, dann Zähler. Patch `tools/patch_1948_liveurteil.py`.

## 1.9.47-fenster · 2026-10-02

- Aufnahmefenster direkt am Bild (Anmerkung Ace): im Videokopf **[−] Fenster 60 % [+]** (Lernen und Einrichten), **Rahmenecke ziehen** ändert die Größe (Cursor zeigt es), **Mausrad über dem Rahmen** ebenfalls (statt Zoom), alles mit sofortiger Anzeige und gebündeltem Senden an `/api/bereich`.
- Knopf „Lernzonen“ im Profil stationaer ausgeblendet.
- Smoke `tools/smoke_fenster.js`; Patch `tools/patch_1947_fenster.py`.

## 1.9.46-se-design · 2026-10-01 · SE Inspect A9

- Dritter Look **SpikingEdge** (Standard für neue Installationen): Farb-Tokens der Website (Nachtblau #061015, Panels #0b1b22, Linien #19343e, Cyan #49e7ff, Grün #79efbd, Amber #ffd174, Pink #ff779b), Inter, Monospace-Eyebrows, feines Raster; flache Flächen wie ISA-101, kein Glas. Layout und Logik unverändert. Look-Knopf wechselt SpikingEdge → Hell → Magna und zeigt das Ziel.
- Profil stationaer: „Linie aktivieren“ in der Befehlsleiste ausgeblendet (war in A1 übersehen).
- Patch `tools/patch_1946_se_design.py`; Smokes stationaer/sprache/linie grün.

## 1.9.45-testsatz · 2026-10-01 · SE Inspect A6/A7

- `vorsa/testsatz.py`: Prüfszenen mit Soll-Werten (`<daten>/testsatz/NNNN.jpg` + `testsatz.json`), roher Ausschnitt vor dem Mehrbild-Mittel, Ist-Urteil zur Aufnahmezeit, nie zum Lernen benutzt. API `/api/testsatz` (aufnehmen/liste/loeschen/soll), `/api/testsatz_bild`; Übersicht in `bereich.pruef.testsatz`.
- UI (stationaer, Prüfung): Block „Testsatz“ — Soll per Klassen-Chips (Mehrfach), „leer“, „Szene aufnehmen“, Zähler einzeln/mehrere/leer, letzte Szenen mit Bild und Löschen.
- `tools/eval_testsatz.py`: Szenen durch dieselbe Erkennungskette wie der Server (Verarbeitung stationaer, Mehrbild aus, gelernter Stand oder Neu-Lernen aus Fotos) → Q1 falsch-sicher, Q2 einzeln, Q3 unbekannt, Q4 mehrere, leer; Konfusion; Schwellenvorschlag (Q1 ≤ 0,5 %); Bericht Markdown + JSON; kennzeichnet CPU-Ersatz.
- `edge_learn.py`: `verbund_modus` wird mit gesichert und beim Zurückspielen wiederhergestellt.
- Sprachdatei um die Testsatz-Texte ergänzt.

## 1.9.44-cpu-ersatz · 2026-10-01 · SE Inspect A8 (Laptop-Modus)

- `vorsa/akida_cpu.py`: CPU-Ersatz für den Silhouetten-Abgleich ohne Karte — bildet nur den von `edge_learn.py` genutzten MetaTF-Ausschnitt nach (InputData → FullyConnected 1 Bit, unüberwachtes Lernen mit Klassenzuordnung, forward = Überlappungszählung, save/load). Gleiche Zahlen wie auf dem Chip, keine Aussage über Hardware. Aktiv nur bei `VORSA_CPU_LERNEN=1`; `run_web.py --synthetisch` setzt das automatisch, wenn kein MetaTF da ist. Oberfläche meldet „Chip-Lernen bereit: CPU-Ersatz (2 simulierte Karten) …“.
- Damit läuft auf dem Laptop die komplette Kette: Objekte anlegen → Fotos → Chip-Lernen (repliziert auf 2 simulierte Karten) → Erkennung mit „Warum?“ → Hypothesen über den Verteiler → PRÜFEN bucht ins Prüfbuch → Sichern/Zurückspielen. Geprüft per API gegen den synthetischen Server.

## 1.9.43-lernfenster · 2026-10-01

- Lernmodus: Block „Aufnahmefenster“ (Größe-Regler, Schärfe) steht jetzt direkt in der Spalte Objekte & Lernen über der Aufnahmeserie — kein Wechsel nach Kamera mehr nötig (Anmerkung Ace). Patch `tools/patch_1943_lernfenster.py`.

## 1.9.42-verteiler · 2026-10-01 · SE Inspect A4

- `vorsa/verteiler.py`: Kartenverteiler. Bewertungsaufträge (Hypothesen-Teile) reihum auf die nutzbaren Karten, je Karte ein Thread; Ausfall mitten im Auftrag → Wächter sperrt die Karte, Auftrag wird auf einer anderen Karte wiederholt, zuletzt über den Verbundweg. Rückfall sequentiell bei < 2 Karten oder verteiltem Verbund. Stand in `bereich.verteiler` und `bereich.verbund`.
- `edge_learn.py`: replizierter Verbund (`replikation=True`, Standard im Profil stationaer; `VORSA_VERBUND=verteilt` schaltet um): jede Karte lernt ALLE Beispiele; passt der Satz nicht auf eine Karte, fällt das Lernen auf „verteilt“ zurück und sagt das im Lernbericht. `_verbund_planen()`, `erkenne_auf_karte(bild, maske, ki)` mit Karten-Lock und Wächter-Meldung, Urteilsbildung in `_urteil()` zusammengezogen, `verbund_info()`.
- Server: `bewerte(..., ki)`; Hypothesen werden im Profil stationaer über den Verteiler bewertet.
- Bench `tools/test_verteiler.py` (VERTEILER_OK): 8 Aufträge auf 4 simulierten Karten 44 ms statt ~160 ms, gleichmäßig verteilt, Ausfall einer Karte ohne Ergebnisverlust mit genau einem Alarm, verteilter Verbund sequentiell. Wächter-, Stationär- und Hypothesen-Benches weiter grün.

## 1.9.41-hypothesen · 2026-10-01 · SE Inspect A3

- `vorsa/hypothesen.py`: Deutungen einer zusammenhängenden Fläche als explizite Hypothesen (ganz, Stücke, Paare, Rechteckzerlegung mit Sollmaß, Vereinigungen aus Runde-1-Ergebnissen: unbenennbare Stücke je Berührungscluster, plus angrenzendes benanntes Stück, gleiche Klasse zusammen, „bestes Stück + Rest“). Score = mittlere Übereinstimmung − 0,03 je weiterem Teil, × geometrische Plausibilität (Sollmaße, wenn bekannt); unbenennbar zählt 0,3. Höchstens zwei Bewertungsrunden, jede Runde als EIN Auftragspaket (`bewerte_viele`) — Schnittstelle für den Kartenverteiler.
- Server: im Profil stationaer entscheidet `_hypothesen_entscheiden` statt `_verschmelze`; Profil linie unverändert. Diagnose in `bereich.hypothesen` (Stücke, gewählt, Score, Runden, Aufträge, Top-3).
- Bench `tools/test_hypothesen.py` (HYPOTHESEN_OK): zerschnittenes Einzelteil → ganz 100 %, zwei berührende Teile → Stücke 100 %, Überlappung nominal → Zerlegung 100 %, zerschnittener Ring + Scheibe 80 % (Ziel 75 %, dokumentierte Grenze: die Wasserscheide schneidet Nachbarn mit; Nachschneiden mit gelernter Form ist Ausbaustufe).

## 1.9.40-mehrbild · 2026-10-01 · SE Inspect A2

- `vorsa/mehrbild.py`: gleitendes Mittel über N Bilder des Prüf-Ausschnitts, solange die Szene steht (Bewegungsmaß = mittlere Differenz zum Vorbild, Schwelle 2,5); Bewegung verwirft den Puffer, das erste Bild der neuen Szene zählt mit. Nur im Profil stationaer und nur beim Betreiben (Lernfotos bleiben Einzelaufnahmen). Anzeige, Leerbild und Erkennung sehen dasselbe gemittelte Bild.
- Einstellung `mehrbild` (1–16, Standard 4) in `pruef.json`, `/api/pruef_einst {mehrbild}`, Regler „Bilder mitteln“ in den Prüfparametern, Stand im Szenenstatus („3 von 4 Bildern gemittelt“) und in `bereich.mehrbild`.
- Bench `tools/test_mehrbild.py` (MEHRBILD_OK): Restrauschen fällt ~1/√N (6,4 → 1,6 bei N=16), flackernder Blendfleck 85 → 0 Schwankung, Szenenwechsel ohne Geisterbild, mit Leerbild-Verfahren 0/16 Falschteile statt 12/24, 1080p ≈ 40 ms (x86).

## 1.9.39-sprache · 2026-10-01 · SE Inspect A13

- Oberfläche zweisprachig Deutsch/Englisch. Umschalter unten in der Seitenleiste (DE/EN), Sprache in `localStorage` (`nbes_sprache`), Vorgabe aus der Browsersprache. Übersetzung zur Laufzeit über die Textknoten und `title`/`placeholder`/`aria-label`/`alt` (MutationObserver), Wörterbuch `vorsa/web/static/sprache_en.js` (~690 Einträge, Zahlen als `{}`-Muster). Unbekannte Texte bleiben Deutsch und stehen in `window.I18N_FEHLEND`.
- Server liefert `/static/*.js`.
- Benches: `tools/smoke_sprache.js` (EN → DE → EN, Attribute, Lernmodus, Zustand), `tools/i18n_ernte.js` (Textsammlung). Patch: `tools/patch_1939_sprache.py`.

## 1.9.38-stationaer · 2026-10-01 · SE Inspect A1

- Profil `stationaer` (Standard) / `linie` (`VORSA_PROFIL`, `run_web.py --profil`). Im Profil stationaer: kein Band, kein Arm, keine Zonen; Linie lässt sich nicht aktivieren (409); Band bleibt Simulation, egal was `VORSA_BAND` sagt. Der Pi-Aufbau bleibt über `start.sh` auf `linie`.
- Stationäre Prüfung: `/api/pruefen` bucht alle Teile der Szene je Teil ins Prüfbuch (gut / unbekannt / ausschuss, Archivbild je Teil). Auslöser `hand` (Knopf, Leertaste, API) oder `auto` (Szene steht ≥ 0,6 s still und ist neu; eine Buchung je Szene; Tisch leer = neu scharf). Einstellung in `pruef.json`, `/api/pruef_einst {ausloeser}`.
- `je_objekt` trägt `box_px` (Pixelrahmen im Ausschnitt).
- Synthetische Bildquelle im Profil stationaer: Szene steht 6 s, Tisch 2 s leer (`VORSA_SYNTH_HALTEN_S`, `VORSA_SYNTH_LEER_S`).
- UI: `PROFIL` aus `/api/state`; Linienbetrieb und Zonen-Knopf verschwinden, „Kamera & Zonen“ heißt „Kamera“; Prüf-Kachel mit PRÜFEN-Knopf, Hand/Auto, Szenenstatus, letzte Prüfung je Teil.
- Benches: `tools/test_stationaer.py` (STATIONAER_OK), `tools/smoke_stationaer.js`; alle bisherigen Benches grün. Patches reproduzierbar: `tools/patch_1938_stationaer.py`, `tools/patch_1938_ui.py`.
