# Änderungen

Format: Build-String (Footer) · Datum · Inhalt. Älteres siehe `PROJEKTBERICHT_ALPHA.md` Anhang B.

## 1.0.0-alpha.3 (2026-10-04) · dritte öffentliche Alpha

- Versionsstring `1.0.0-alpha.3`; Inhalt = 1.9.74-testleer (Version 1.1: Vorschläge aus dem Betrieb, Schwelle aus dem Testsatz mit Kalibrierung, Trend; M3-Fortschritt; Testlauf-Fixes; Drehknopf; Installer mit Konfiguration; Komplettsicherung). `RELEASE_NOTES.md`, README-Status, CITATION aktualisiert. GitHub-Issue-Vorlagen (`.github/ISSUE_TEMPLATE/`) erstmals im Paket.

## 1.9.74-testleer (2026-10-04)

- **Testlauf benutzt jetzt das Leerbild** wie die Live-Erkennung. Vorher: Testszene (687-px-Ausschnitt) ≠ Form des Kamerabilds → kein Leerbild → auf leeren Szenen „zwei SD-Karten“ (0,71/0,99), live auf derselben Fläche „Kein Teil“. Jetzt wird das Leerbild am Aufnahmefenster zugeschnitten und auf die Szene skaliert. Bench `test_1_1_server.py` erweitert. Patch `tools/patch_1974_testlauf_leerbild.py`.

## 1.9.73-roh (2026-10-04)

- **Testlauf misst garantiert roh:** ab Szene 10 waren die Ist-Werte plötzlich kalibriert (SD 0,87–0,94 statt 0,55–0,61) – etwas setzte die Kalibrierung mitten im Lauf. Jetzt Sperrflag am Lerner (während des Laufs immer roh), `_kalib_anwenden` während des Laufs ein No-op, jede Anwendung im Serverlog. Patch `tools/patch_1973_roh.py`.

## 1.9.72-testlauf (2026-10-04)

- **Testlauf gegen Moduswechsel geschützt:** auf dem Pi lieferte ein Lauf ab Szene 20 nur noch leere Ergebnisse – währenddessen war auf Anlernen umgeschaltet worden. Jetzt lehnt der Server einen Moduswechsel während des Testlaufs ab (409, Meldung in der Oberfläche); bricht der Modus trotzdem weg, endet der Lauf mit klarem Grund statt mit falschen Zahlen. Bench `test_1_1_server.py` erweitert. Patch `tools/patch_1972_testlauf_fest.py`.

## 1.9.71-m3fortschritt (2026-10-04) · M3-Training hängt nicht mehr still

- **Befund:** „Fotos freistellen 0 %“ war kein Hänger, sondern 121 Fotos × 32 Augmentierungsvarianten = 3 872 Freistellungen auf 687-px-Bildern im Server, ohne Fortschrittsmeldung – auf dem Pi Dutzende Minuten. Die Drehvarianten sind für M3 wertlos (die Szenensynthese dreht und skaliert jedes Teil ohnehin zufällig).
- **Schneller:** nur Original + Spiegelungen (Händigkeit bleibt beachtet), Bilder vorher auf 384 px. Rund 10- bis 40-mal weniger Arbeit; hier 0,1 s je Foto.
- **Fortschritt sichtbar:** „Fotos freistellen i von n“ und ein **Gesamtfortschritt über alle Phasen** (Freistellen 15 %, TensorFlow 5 %, Training 68 %, Quantisieren/Umwandeln 7 %, Chip 3 %) in `/api/lauf` (`gesamt`).
- **Fortschrittsbalken farbig:** Prozentzahl, blau während des Laufs, grün fertig, rot bei Fehler, gestreift pulsierend bei Phasen ohne Zählung – in der großen Zeile unterm Bild und im Training-Dialog.
- Bench `tools/test_m3_fortschritt.py`, Smoke `tools/smoke_laufbalken.js`, Entwicklerwerkzeug `tools/ui_statisch.js`, CI. Patch `tools/patch_1971_m3_fortschritt.py`.

## 1.9.70-kalibrierung (2026-10-04)

Anlass: auf dem Pi schlug „Schwelle aus dem Testsatz“ 96 % vor – danach wurde fast nichts mehr benannt. Die SD-Karte erreicht richtig erkannt nur ~0,6, der Inbusschlüssel ~0,9; leere Szenen lieferten Phantomteile (Leerbild vor der Drehung aufgenommen).

- **Neuer Schwellen-Vorschlag:** unter den Schwellen mit höchstens 1 % falsch-sicher die mit den meisten Treffern. Bleiben dabei weniger als 70 % Treffer, ist das Ziel nicht erreichbar – dann die beste Abwägung (Treffer − 3 × falsch-sicher), klar als **Kompromiss** gekennzeichnet, mit Hinweis, was wirklich hilft.
- **Kalibrierung je Objekt:** der Testlauf misst roh, bestimmt je Objekt die typische Sicherheit richtiger Treffer (ab 3 Einzelszenen) und rechnet sie so um, dass ein typischer Treffer überall bei 90 % liegt (`kalibrierung.json`, gilt sofort für Erkennung und Prüfung). Nach neuem Training als „veraltet“ markiert. Anzeige + „Kalibrierung verwerfen“ in Einstellungen › Erkennung. Mit den Pi-Daten: 23 statt 12 von 30 Treffern beim Vorschlag, bei 80 % Schwelle 22 statt 10.
- **Leerbild passt zur Drehung:** das Leerbild merkt sich die Drehung; passt sie nicht mehr, wird es nicht benutzt, der Schritt „Leerbild“ ist wieder offen und Einrichten sowie die Prüfspalte warnen.
- Bench `tools/test_kalibrierung.py` (Pi-Testlauf nachgebaut), `test_1_1_server.py` und `smoke_elf.js` erweitert, CI. Patch `tools/patch_1970_kalibrierung.py`.

## 1.9.69-ruhig (2026-10-04)

- **Nichts springt mehr im Zustandstakt** (Video vom Pi): der Knopf „Lernzonen“ im Videokopf wurde im Anlernen bei jedem Abruf gezeigt und gleich wieder versteckt (Einkamera) – Kamera/Ansicht/Vollbild rutschten seitlich hin und her. „Erste Schritte“ in der Seitenleiste verschwand bei 6/6 und kam bei kurzen 5/6 zurück – die ganze Leiste sprang. Jetzt eine Regel für den Knopf; „Erste Schritte“ bleibt nach 6/6 für die Sitzung weg (Einstellungen › Allgemein öffnet es weiter).
- Smoke `tools/smoke_ruhig.js`, CI erweitert. Patch `tools/patch_1969_ruhig.py`.

## 1.9.68-testsatz (2026-10-04)

- **Testsatz in jedem Profil:** bisher nur im Profil „stationär“ sichtbar – `sync.ps1` legt auf dem Pi aber `VORSA_PROFIL=linie` an, dort fehlte er. Jetzt oberster Block im Reiter **Prüfen › Prüfdetails**, in jedem Profil.
- Einstellungen › Erkennung › „Schwelle aus dem Testsatz“: Knopf **„Testsatz öffnen“** springt direkt dorthin und klappt ihn auf. Smoke `smoke_elf.js` erweitert. Patch `tools/patch_1968_testsatz_ort.py`.

## 1.9.67-fremdteil (2026-10-04)

- Testsatz: neuer Chip **„Fremdteil“** (Soll = unbekannt). Vorher ließ sich in der Oberfläche keine Fremdteil-Szene anlegen – die Schwelle aus dem Testsatz konnte „Unbekanntes erkennt“ dann nicht messen. Smoke `smoke_elf.js` erweitert. Patch `tools/patch_1967_fremdteil.py`.

## 1.9.66-drehen (2026-10-04)

- **Drehknopf in der Zoomleiste** (neben 1:1): dreht das Kamerabild um 90°, der Winkel steht am Knopf. Im Prüfen gesperrt – die Lage gilt für Lernen und Prüfen gemeinsam.
- Die Bilddrehung **bleibt nach einem Neustart erhalten** (`vorsa_daten/drehung.json`); vorher fiel sie auf 0° zurück. Winkel steht in `/api/state`.
- Smoke `tools/smoke_drehen.js`, CI erweitert. Patch `tools/patch_1966_drehen.py`.

## 1.9.65-selbstlernen (2026-10-03) · Version 1.1: selbstlernende Zelle, Schwelle aus dem Testsatz, Trend

- **Vorschläge aus dem Betrieb** (`vorsa/selbstlernen.py`): unbekannte Teile aus dem Prüfarchiv werden nach Form und Farbe gruppiert. Anlernen › Karte „Vorschläge aus dem Betrieb“ → Dialog: als neues Objekt, zu einem Objekt, Hintergrund oder verwerfen; danach „Training …“. Regler feiner/gröber. `/api/vorschlaege`, `/api/vorschlag_anwenden`.
- **Schwelle aus dem Testsatz** (`vorsa/schwelle.py`): Einstellungen › Erkennung › Testlauf spielt alle Testsatz-Szenen durch die Erkennung, zeigt die Kurve 30–95 % (Treffer, Fremdteil erkannt, Bekanntes unbekannt, Falsch-sicher) und schlägt die kleinste Schwelle mit ≤ 0,5 % falsch-sicher vor – ein Klick übernimmt sie. `/api/testlauf`.
- **Trend** (`vorsa/trend.py`): dauerhaftes Prüfjournal (`pruefjournal.jsonl`), Prüfung › Reiter „Trend“ mit 24-h-Balken, 14-Tage-Tabelle und **Drift-Warnung** („Sicherheit sinkt“, auch in der Prüfspalte). `/api/trend`.
- Englisch vollständig (Nachtrag 19). Benches `test_selbstlernen.py`, `test_trend.py`, `test_1_1_server.py`, Smoke `smoke_elf.js`, CI erweitert. Patches `tools/patch_1964_selbstlernen.py` (Server), `tools/patch_1965_ui11.py` (Oberfläche). Spezifikation `SE_INSPECT_1_1_SPEC.md`.

## 1.9.63-sicherung (2026-10-03) · Installer mit Konfiguration + Komplettsicherung (I4)

- **`install.sh --config "<Link>"`**: übernimmt den Link aus spikingedge.com/configure/ und schreibt `start.local.sh`, `vorsa_daten/eaio.json`, `sps.json`, `pruef.json` (alte Dateien als `*.vor-<Zeit>` gesichert, `pruef.json` zusammengeführt). Einzeln: `python3 tools/konfig_anwenden.py "<Link>" [--zeigen]`. Ausgabe identisch mit dem Website-Konfigurator (abgeglichen).
- **Komplettsicherung** (`vorsa/sicherung.py`): Einstellungen › Wartung › „Sicherung herunterladen“ – eine ZIP mit dem ganzen Datenordner (Objekte, Fotos, Gelerntes, Prüfprogramme, Leerbilder, Einstellungen, I/O, Benutzer, Testsatz, Protokolle) und Manifest mit Prüfsummen. „Sicherung einspielen …“ prüft (Art, Pfade, Prüfsummen, Größe), zeigt Herkunft und Build, sichert den aktuellen Stand nach `vorsa_sicherungen/` und startet den Dienst neu. Nur Admin, wenn Rollen aktiv sind. Nicht enthalten: der trainierte M3-Detektor.
- Benches `tools/test_konfig.py`, `tools/test_sicherung.py` (inkl. eigenem Server: Download, Prüfen, Einspielen, Neustartcode); CI erweitert. Patch `tools/patch_1963_sicherung.py`.

## 1.0.0-alpha.2 (2026-10-03) · zweite öffentliche Alpha

- Versionsstring `1.0.0-alpha.2`; Inhalt = 1.9.62-training (UI-Pakete 1–4, I/O, Rollen, Modbus, Training-Begriff). `RELEASE_NOTES.md`, README-Status, CITATION aktualisiert.

## 1.9.62-training (2026-10-03)

- Begriff: der Knopf rechts oben im Anlernen heißt **„Training …“ / „Neu trainieren …“** (EN „Train …“ / „Retrain …“) statt „Lernen …“ – er öffnet den Dialog mit beiden Wegen (Chip-Lernen, M3-Training). Auch in „Erste Schritte“ und den Hinweisen. Patch `tools/patch_1962_training.py`.

## 1.9.61-sps (2026-10-03) · Industrie-Paket I2: SPS-Anbindung (Modbus TCP)

- Neues Modul `vorsa/sps.py`: SE Inspect als **Modbus-TCP-Server** (eigene Implementierung, FC 1/2/3/4/5/6/16). Eingangsregister 0–12: Status-Bits (bereit, prüft, Störung, letzte OK/NOK, simuliert), Urteil, Objekt-ID, Konfidenz ‰, Teile, Zähler (32 Bit), gut/unbekannt/Ausschuss, Programm-Nr., Lebenszähler, **Ergebnis-Sequenz**. Halteregister 0 ← 1 Prüfen / 2 Zähler zurücksetzen, Halteregister 1 ← Prüfprogramm-Nr. laden, Coil 0 ← Prüfen.
- Standard **aus**, Port 1502, Schalter „nur lesen“; Einstellen nur als Admin. Stationär: Prüfen per SPS ohne Teil → Urteil 4 (leer). Linie: Ergebnis je gebuchtem Teil.
- Einstellungen › **SPS / Modbus**: Ein/Aus, Port, Schreibrecht, Live-Registertabelle, Programmnummern, letzter Befehl. `/api/sps`.
- Bench `tools/test_sps.py` (Protokoll gegen Attrappe + optional gegen laufenden Server), CI erweitert. Patch `tools/patch_1961_sps.py`.

## 1.9.60-rollen (2026-10-03) · Industrie-Paket I3: Benutzerrollen

- Neues Modul `vorsa/rollen.py`: **Bediener / Einrichter / Admin** mit PIN (4–8 Ziffern, nur als PBKDF2-Hash mit Salz gespeichert, `rollen.json` mit Rechten 600). Ohne Admin-PIN bleibt alles offen wie bisher.
- Prüfung **im Server** vor jeder ändernden Anfrage (403 mit Grund). Bediener: prüfen, quittieren, Prüfprogramm laden, Linie starten/stoppen. Admin-only: Benutzer, Ein-/Ausgänge, Gelerntes/Objekte/Programme löschen. Sitzungen per Token, automatische Abmeldung (Vorgabe 15 min), Sperre 30 s nach 5 Fehlversuchen.
- **Änderungsprotokoll** (`aenderungen.jsonl`): Zeit, Rolle, Aktion, Kurzinhalt – ohne PINs.
- Oberfläche: Schloss unten links (Anmelden/Abmelden), PIN-Dialog, eine verweigerte Aktion öffnet die Anmeldung; ohne Anmeldung reine Bedienstation. Einstellungen › **Benutzer** (PINs, Abmeldezeit, Rollen aus, Protokoll).
- Fix: Keep-Alive-Verbindungen bekamen den Anfragekörper der vorigen Anfrage (nur mit dem neuen Zwischenspeicher, vor der Auslieferung gefunden).
- Smoke `tools/smoke_rollen.js` (setzt am Ende alles zurück); CI erweitert. Patch `tools/patch_1960_rollen.py`.

## 1.9.59-eaio (2026-10-03) · Industrie-Paket I1: digitale Ein-/Ausgänge

- Neues Modul `vorsa/eaio.py`: Eingang **Trigger**, Ausgänge **Bereit / OK / NOK / Fehler**; Puls oder Halten. Treiber **Simulation** (Vorgabe), **GPIO** (gpiozero; Optokoppler-/Relaismodule, GPIO-Relais-HATs) und **Modbus TCP** (eigener Client, Coils/Discrete Inputs). Ohne Hardware fällt jeder Treiber auf Simulation zurück und nennt den Grund. GPIO 18 (Bandrelais), 0–3 gesperrt; Doppelbelegung abgelehnt.
- Server: Prüf-Auslöser **Extern** (stationär) – Trigger-Flanke bucht eine Prüfung, ohne Teil → NOK. OK/NOK stationär je Szene, im Linienbetrieb je gebuchtem Teil. Bereit = im Prüfen ohne Alarm, Fehler = aktiver Alarm. `/api/eaio` (GET Zustand; POST `einstellen` / `test`).
- Oberfläche: Einstellungen › **Ein-/Ausgänge** mit Treiberwahl, Pin-/Adresstabelle, Live-Lampen, Test je Signal, Puls/Halten, Protokoll. Auslöser „Extern“ in Kachel und Allgemein.
- Bench `tools/test_eaio.py` (Simulation, nachgebautes gpiozero, Modbus-Server im Prozess), Smoke `tools/smoke_eaio.js`; CI erweitert. Patch `tools/patch_1959_eaio.py`.

## 1.9.58-anlernen (2026-10-03) · UI-Paket 4

- **Objektkarten** im Anlernen: Vorschaubild, Foto-Fortschritt als Balken (x/5), Ampel; „nichts / Störteil“ heißt jetzt **Hintergrund** und ist erklärt. Doppelte Knöpfe in der Spalte entfallen (Foto aufnehmen / Lernen sitzen oben rechts).
- **Prüfen**: Urteilskarte als **Live-Vorschau** markiert, Zähler darunter als **Gebuchte Prüfungen** – kein „GUT, aber Geprüft 0“ mehr ohne Erklärung. „Urteil vom Gesamtbild“ ist eine leise Zeile; der Leerbild-Knopf erscheint nur, solange keins gemerkt ist.
- **Löschen**: Foto mit „Rückgängig“ (5 s, gelöscht wird erst danach); Objekt über den eigenen Bestätigungsdialog statt Browser-Fenster.
- **Tastenkürzel-Hilfe** mit „?“ (auch im „⋯“-Menü).
- `state.py`: Klasse liefert `titelbild` (erstes Foto) für die Karte.
- Smoke `tools/smoke_anlernen.js`; Patch `tools/patch_1958_anlernen.py`. Alle Smokes beider Profile, Rundgang (211 Schritte, 0 JS-Fehler, 0 unübersetzt) und API-Fuzz grün.

## 1.9.57-einstellungen (2026-10-03) · UI-Paket 3

- **Ein Einstellungsfenster** (Zahnrad „Einstellungen“ in der Seitenleiste) mit Reitern Allgemein · Kamera · Erkennung · Prüfprogramme | Hardware · Diagnose · Wartung. „Zustand“ öffnet dasselbe Fenster auf Hardware.
- Allgemein: Sprache, Darstellung, Ton, Prüf-Auslöser, Erste Schritte. Erkennung: Konfidenzschwelle, Ziel Unbekannt-Quote, Bilder mitteln – mit Erklärung.
- **Rezepte heißen jetzt Prüfprogramme** (EN „Jobs“; API und `rezepte.json` unverändert). „Einstellung sichern“ geht darin auf: Einrichten-Spalte und Kamera-Dock sichern als Prüfprogramm; ältere Kamera-Einstellungen bleiben unter Einstellungen › Prüfprogramme ladbar.
- Fußleiste links nur noch Symbole mit Tooltip (keine abgeschnittenen „M.. / C..“), Versionszeile → Einstellungen › Hardware › Software.
- Smoke `tools/smoke_einstellungen.js`; Patch `tools/patch_1957_einstellungen.py`.

## 1.9.56-ablauf (2026-10-03) · UI-Pakete 1+2

- **Geführter Ablauf**: Seitenleiste als Schritte ① Einrichten → ② Anlernen → ③ Prüfen, mit Häkchen, sobald erledigt (Leerbild/Fenster · zwei Objekte mit je 5 Fotos + gelernt · erste Prüfung). Seitentitel heißen wie die Schritte.
- **Nächster Schritt**: Karte oben in der rechten Spalte („Noch nichts gelernt → Anlernen“, „Eingerichtet ✓ → weiter“, Fortschritt beim Fotografieren).
- **Erste Schritte**: Assistent mit 6 Punkten, hakt sich live ab, jeder Punkt mit Knopf; öffnet sich einmal bei frischer Anlage, danach über die Seitenleiste oder „⋯“.
- **Ein Hauptknopf je Seite** rechts oben: Prüfen → PRÜFEN · Anlernen → Foto aufnehmen (+ Lernen …) · Einrichten → Leerbild merken (+ Weiter). Analyse und Bedienansicht im „⋯“-Menü. Linie/Arm nur im Linienbetrieb; eine laufende Linie bleibt überall stoppbar.
- Kopfzeile: „Gelernt: 2 Objekte“ statt „Verbund + M3 · 128 NPs“ (Technik im Tooltip, Klick → Anlernen). „90° drehen“ aus der Bildleiste ins Rechtsklick-Menü.
- Smoke `tools/smoke_ablauf.js`; Vorschau-Werkzeug `tools/ui_vorschau.js` / `.sh` (statische UI-Schnappschüsse für Screenshots). Patch `tools/patch_1956_ablauf.py`.

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
