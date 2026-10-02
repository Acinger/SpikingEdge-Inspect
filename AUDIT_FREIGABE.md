# Freigabe-Audit · SE Inspect Build 1.9.51-audit · 2026-10-02

Geprüft wurde der Stand nach den Builds 1.9.38–1.9.50 (stationäres Profil, Zweisprachigkeit, Mehrbild, Hypothesen, Kartenverteiler, CPU-Ersatz, Testsatz, SE-Design, Bedienkorrekturen). Ziel: Freigabequalität für den ersten öffentlichen Stand (Alpha, nicht 1.0 — die 1.0 braucht den realen Testsatz, siehe unten).

## 1. Ergebnis

**Freigabefähig als Alpha** nach Behebung der unten aufgeführten Befunde. Alle Benches und Smokes grün, Oberfläche in beiden Profilen, drei Looks und zwei Sprachen ohne JavaScript-Fehler, API gegen Fehleingaben robust, Release-Export ohne private Daten.

| Prüfung | Umfang | Ergebnis |
|---|---|---|
| Python-Benches | farbmaske, glanz, linie_fluss, karten_waechter, m3_head, mehrbild, hypothesen, verteiler, stationaer, run_selftest | 10/10 grün |
| UI-Smokes (jsdom) | stationaer, sprache, fenster, einrichten, ui22 (Linie) | 5/5 grün |
| UI-Rundgang (`tools/audit_ui_rundgang.js`) | 211 Schritte je Profil: 3 Modi × 3 Looks × 2 Sprachen, alle Dialoge, Reiter, Kontextmenü, Linienansicht | 0 JS-Fehler, 0 unübersetzte Texte (bereinigt um Eigennamen) |
| API-Fuzz (`tools/audit_api_fuzz.py`) | 45 Routen × 9 Körper (leer, `[]`, `null`, String, kaputt, falsche Typen, Pfad-Traversal) + 7 GET-Sonderfälle = 502 Aufrufe, beide Profile | 0 Befunde nach Fix, Server lebt |
| Release-Export | `tools/release_export.py` | 188 Dateien, 0 private Adressen/Namen, Export kompiliert |
| Installer | `install.sh --laptop` in frischem venv | läuft durch, Benches grün |

## 2. Befunde und Behebung

| # | Schwere | Befund | Behebung |
|---|---|---|---|
| B1 | **hoch** | `sync.ps1` überträgt nur `vorsa/` und `tools/`, nicht `start.sh`. Mit dem neuen Standardprofil `stationaer` hätte der nächste Sync die Anlage still von Band+Arm auf Simulation umgestellt (altes `start.sh` ohne `VORSA_PROFIL`). | Server leitet das Profil ab, wenn `VORSA_PROFIL` fehlt: Band `echt`/`relais` oder Arm gesetzt → `linie`, sonst `stationaer`. `start.sh` ist jetzt generisch (Standard stationaer) und lädt `start.local.sh` (nicht versioniert) für Maschinen-Einstellungen; `sync.ps1` überträgt `start.sh`, `vorsa.service`, `install.sh`, `CHANGELOG.md` und legt auf dem Pi einmalig `start.local.sh` mit `linie/relais/uno` an, falls es fehlt. |
| B2 | **hoch** | Jede Ausnahme in einer API-Route brach die HTTP-Verbindung stumm ab („Remote end closed“), 63 Tracebacks im Fuzz; JSON-Körper `[]`/`null`/`"text"` führten zu `AttributeError` auf `.get`. | `_koerper()` liefert nur dicts; `do_GET`/`do_POST` fangen alles: falsche Eingaben → JSON 400 mit Grund, sonst JSON 500 mit Grund, Stack nur bei 500 und nur einmal je Meldung. |
| B3 | mittel | Mehrbild-Mittel in float32/numpy kostete ~24 ms je 1296²-Ausschnitt (x86), auf dem Pi geschätzt 60–90 ms je Bild → spürbarer Bildratenverlust. | uint16-Summe mit `cv2.add/subtract/convertScaleAbs`: 6–9 ms (x86), gleiche Ergebnisse, Bench grün. |
| B4 | mittel | `install.sh --laptop` zog über `opencv-python-headless` numpy 2 trotz `numpy<2`. | Laptop: numpy 2 ist erlaubt (kein picamera2); Pi: `numpy<2` bleibt Pflicht; Skript unterscheidet. |
| B5 | mittel | `vorsa.service`/`start.sh` im Release trugen hart `VORSA_PROFIL=linie`, `VORSA_BAND=relais`, `VORSA_ARM=uno` — ein fremder Pi hätte Relais und Arm angesprochen. | siehe B1: `start.sh` neutral, Maschinenwerte in `start.local.sh`; `install.sh` setzt `User=` und Pfade im Service aus der Umgebung. |
| B6 | niedrig | Vollbild-Knopf warf in Browsern ohne Fullscreen-API (iOS Safari, Kiosk-Webviews, jsdom) eine unbehandelte Ausnahme. | Guard + try/catch. |
| B7 | niedrig | Smokes waren von Vorläufen abhängig (Fenstergröße, Sprache) und schlugen in Serie fehl. | Jeder Smoke setzt seinen Ausgangszustand selbst (Sprache de, Fenster 100 %). |
| B8 | niedrig | `verbund_modus` (repliziert/verteilt) ging beim Zurückspielen des Lernstands verloren → Verteiler fiel nach Neustart auf sequentiell. | In der Begleitdatei gesichert und beim Laden wiederhergestellt (1.9.45). |
| B9 | niedrig | `bereich_info` wird je Bild neu aufgebaut; `/api/state` zwischen Aufbau und Befüllung sieht einen Teilstand (Schlüssel fehlen kurz). Vorbestehend, UI toleriert es (Werte „–“ für einen Takt). | Nicht geändert; dokumentiert. Behebung (Aufbau in lokaler Kopie, dann Tausch) für 1.0 vorgemerkt. |

## 3. Code-Review der neuen Module (Kurzfassung)

- **`vorsa/hypothesen.py`**: rein geometrisch, zwei Bewertungsrunden, Aufträge als Paket; `_beruehren` füllt je Paar zwei Masken in Suchbildgröße (≤ 640²) — bei ≤ 6 Stücken unter 10 ms. Grenze dokumentiert (zerschnittener Ring 80 %).
- **`vorsa/verteiler.py`**: ThreadPool je Kartenzahl, Pool wird bei Kartenwechsel erneuert (`shutdown(wait=False)`), Wiederholung auf anderer Karte, Rückfall Verbundweg; Zähler im Zustand. Kein geteilter veränderlicher Zustand außer Zählern (GIL-sicher).
- **`edge_learn.erkenne_auf_karte`**: eigener Lock je Karte, Wächter-Meldung bei Ausnahme, Urteilsbildung mit `erkenne()` identisch (`_urteil`). `_roh_gezaehlt`-Zähler ist zwischen Threads nicht exakt (nur Statistik).
- **`vorsa/akida_cpu.py`**: nur InputData/FullyConnected; `fit` verschmilzt bei voller Kapazität mit dem ähnlichsten Neuron (Mehrheit der Bits); `save` als npz unter `.fbz` (Magie-Feld). Klar als Ersatz gekennzeichnet; kein Hardware-Anspruch.
- **`vorsa/mehrbild.py`**: Bewegungsmaß auf 1/16 der Pixel, Puffer wird bei Bewegung verworfen, uint16-Summe (16 × 255 = 4080 < 65535).
- **`vorsa/testsatz.py`**: Lock um Datei und Liste, Bildnamen nur über `Path(...).name`, kein Traversal (Fuzz bestätigt).
- **Server stationär**: `pruefen_jetzt` wartet höchstens 3 s auf den Bildtakt; zwei gleichzeitige Anfragen teilen sich das nächste Urteil (Zweite kann leer ausgehen — akzeptiert, Knopf ist währenddessen gesperrt).

## 4. Was diese Freigabe NICHT abdeckt

1. **Hardware-Durchlauf 1.9.51 auf dem Pi** (Kamera, Karten, Relais) — der Sandbox-Stand ist ohne MetaTF. Das ist Schritt 1 des Fahrplans: `sync.ps1`, Neustart, Footer, Prüfung mit echtem Teil, Lernbericht „repliziert auf N Karten“, Diagnose-Reiter `verteiler.modus = parallel`.
2. **Qualitätszahlen Q1–Q4** — erst mit dem realen Testsatz (`eval_testsatz.py`).
3. **Umbenennung** auf SE Inspect in Oberfläche und Website (A11/A12) — bewusst nach dem Hardware-Durchlauf.
4. **CI auf GitHub** — die Action ist geschrieben, lief aber noch nicht (Repo nicht veröffentlicht).

## 5. Reproduktion des Audits

```
for t in farbmaske glanz linie_fluss karten_waechter m3_head mehrbild hypothesen verteiler stationaer; do python3 tools/test_$t.py | tail -1; done
python3 tools/run_selftest.py --use-background --out /tmp/selftest | tail -1
python3 tools/run_web.py --port 8765 --synthetisch --daten /tmp/vd &            # Profil stationaer
node tools/smoke_stationaer.js; node tools/smoke_sprache.js; node tools/smoke_fenster.js; node tools/smoke_einrichten.js
node tools/audit_ui_rundgang.js http://127.0.0.1:8765
python3 tools/audit_api_fuzz.py http://127.0.0.1:8765
VORSA_PROFIL=linie python3 tools/run_web.py --port 8766 --synthetisch --daten /tmp/vd2 &
node tools/smoke_ui22.js http://127.0.0.1:8766; node tools/audit_ui_rundgang.js http://127.0.0.1:8766; python3 tools/audit_api_fuzz.py http://127.0.0.1:8766
python3 tools/release_export.py --ziel /tmp/rel
```
