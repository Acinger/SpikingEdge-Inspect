# SE Inspect 1.0 — Spezifikation

Stand 01.10.2026 · Grundlage: VORSA INSPECT Build 1.9.37-lernrahmen, `SPEC.md` (M3), `PROJEKTBERICHT_ALPHA.md`, Benches in `tools/`.
Status: Entwurf zur Freigabe durch Ace. Alles, was hier als „heute“ bezeichnet wird, ist im Repo vorhanden und getestet; alles andere ist als **neu** markiert.

---

## 0. Leitsatz

SE Inspect 1.0 ist eine **stationäre Prüfzelle**: ein Teil (oder mehrere) liegt still unter einer Kamera, wird freigestellt, vermessen, mit am Gerät gelernten Prototypen verglichen und mit einem Urteil versehen, das lieber „unbekannt“ sagt als falsch. Das System läuft auf einem Raspberry Pi 5 mit einer bis vier AKD1500-Karten, lernt neue Teile in unter einer Minute ohne Cloud und ohne GPU, und jede Zahl, die wir behaupten, hat eine Bench im Repo.

Nicht in 1.0: Förderband, Roboterarm, zweite Kamera, Modell-Splitting über Karten. Der Code dafür bleibt im Repo und wird als **experimental** geführt.

---

## 1. Namen

| Ebene | Name | Anmerkung |
|---|---|---|
| Marke | SpikingEdge | spikingedge.com |
| Produkt | **SE Inspect** | die stationäre Prüfzelle, Version 1.0 |
| Detektor | **SE-M3** | bisher VORSA-M3; Architektur unverändert (`SPEC.md`) |
| Laborprototyp | VORSA INSPECT | bleibt als historischer Name auf Projektseite und in Lab Notes |
| Python-Paket | `vorsa/` → `seinspect/` | **eigener Schritt** nach dem Funktionsstand, nie gleichzeitig mit Funktionsänderungen (betrifft systemd-Dienst, `sync.ps1`, `start.sh`, alle Importe) |

Reihenfolge der Umbenennung: erst Sichtbares (UI-Titel, Footer-Build-String, Docs, Repo-Name), dann Paket. Die Anlage darf wegen einer Umbenennung nie stehen.

---

## 2. Hardwareprofile

| Profil | Hardware | Wofür |
|---|---|---|
| **Laptop** | nur Python, numpy < 2, OpenCV | `--synthetisch`: komplette UI, Segmentierung, Messung, Hypothesen mit synthetischen Szenen; Lernen/Erkennen als Stub mit klarer Kennzeichnung |
| **Minimal** | Pi 5, 1 × AKD1500 (M.2) auf Träger, 1 × Camera Module 3, feste Beleuchtung | der Einstieg für die Community (< 1 000 €); alles aus 1.0 funktioniert, nur mit einer Karte langsamer und mit weniger Prototypen |
| **Voll** | Pi 5, 4 × AKD1500, 1 × Camera Module 3 | Referenzaufbau; Hypothesen-Parallelität, Kapazität, Ausfallsicherheit |

Beleuchtung ist Teil des Profils: 1.0 dokumentiert eine empfohlene Leuchte (diffus, flackerfrei, fester Winkel) und misst alle Qualitätsziele unter dieser Beleuchtung. Blendflecken werden trotzdem gefiltert (heute: `glanzmaske`), weil keine Beleuchtung perfekt ist.

---

## 3. Funktionsumfang 1.0

| # | Funktion | Heute | 1.0 |
|---|---|---|---|
| F1 | Leerbild aus 16 Frames mit Rauschkarte, Schwelle je Pixel | vorhanden (`leerbild_merken`, `foreground_mask` mit `background_noise`) | unverändert; Aufnahme auch bei stehendem Band |
| F2 | Lokales Hintergrundmodell gegen Vignettierung | vorhanden (`farbmaske_lokal`, Polynom 4. Grades je Lab-Kanal) | unverändert |
| F3 | Blendfleckfilter | vorhanden (`glanzmaske`, ≥ 246, < 2 %, Halo 1,8 r) | unverändert |
| F4 | Segmentierung: Watershed, Rechteckzerlegung, Tracking | vorhanden (`segmentation.py`, `fitting.py`, `tracking.py`) | Tracking im stationären Modus nur zur Stabilisierung über Frames |
| F5 | Kalibrierung Pixel → mm, Messung Mittelpunkt/Winkel/Maße | vorhanden (`calibration.py`, Selbsttest A4/A5) | unverändert; Messprotokoll als CSV (heute `/api/pruef_csv`) |
| F6 | Lernen am Gerät: Silhouetten-Prototypen, Fotos je Klasse, „Warum erkannt?“ | vorhanden (`EdgeLerner`, Modus `silhouette`, 48×48×2 binär, FullyConnected 1 Bit) | unverändert |
| F7 | Kartenverbund: Beispiele auf G Karten verteilt, Potential = max über Karten | vorhanden (`_lerne_silhouette`, `_verbund_sieger`) | bleibt die Basis (siehe 5) |
| F8 | Karten-Wächter: Live-Status je Karte, Sperre 60 s, Alarm, PCIe-Reset | vorhanden (1.9.36/37) | unverändert |
| F9 | Mehrbild-Aufnahme stationär (N Frames mitteln, optional 2 Belichtungen) | **neu** | Pflicht |
| F10 | Hypothesen-Parallelität bei Überlappung | **neu** | Pflicht (Voll-Profil); im Minimal-Profil sequentiell |
| F11 | Kartenverteiler: Ausschnitte und Hypothesen gleichzeitig auf freie Karten | **neu** | Pflicht |
| F12 | Unsicherheitsurteil: „gut / Klasse X / unbekannt / prüfen“ mit begründeter Schwelle | teilweise (Übereinstimmungsmaß, `UNBEK_S`) | Schwelle aus Testsatz kalibriert, nicht geraten |
| F13 | Betriebsart `stationaer` (Band/Arm/Zonen ausgeblendet) | **neu** (heute Betriebsarten einrichten/anlernen/betreiben/messen + Linienzonen) | Pflicht |
| F14 | Testsatz-Werkzeug: Szenen mit Soll-Werten aufnehmen und beschriften | **neu** | Pflicht, weil Q-Ziele sonst nicht messbar |
| F15 | UI im SpikingEdge-Design | **neu** (Token-Tausch, kein Layoutumbau) | Pflicht |
| F16 | SE-M3-Detektor (Karte 3) | vorhanden, experimental | bleibt **experimental** in 1.0; Silhouetten-Verbund ist der Standardweg |

---

## 4. Erkennungskette stationär

```
Auslöser (Taste / Lichtschranke / API)
 → F9  N Frames (Standard 4) mitteln, optional kurze + lange Belichtung
 → F1–F3  Leerbild-Differenz je Pixel, lokales Hintergrundmodell, Blendflecken raus
 → F4  Blobs → Watershed → Rechteckzerlegung → Teilkandidaten
 → F10 je mehrdeutigem Blob: Hypothesen H1..Hk (1 Teil / 2 Teile an Watershed-Linie / Zerlegung in 3–4)
 → F11 Ausschnitte aller Hypothesen gleichzeitig auf freie Karten (Silhouette → Potential je Klasse)
 → Konsistenz: Score(H) = Σ Klassenpotential · geometrische Plausibilität (Soll-Maße aus Rezept)
 → F12 Urteil je Teil: Klasse + Übereinstimmung; unter Schwelle → „unbekannt“; Hypothesen uneins → „prüfen“
 → F5  Messung (Mittelpunkt, Winkel, Länge, Breite) in mm
 → Anzeige + Protokoll (CSV, Ereignisbuch, „Warum?“-Foto)
```

Der stationäre Modus darf sich Zeit nehmen: Ziel ist **Qualität je Prüfung**, nicht Frames je Sekunde. Richtwert ≤ 1 s von Auslöser bis Urteil im Voll-Profil (Messung vor Freigabe, siehe Q7).

---

## 5. Vier-Karten-Systematik

Korrektur zu meiner Aussage vom 01.10.: Der heutige Verbund ist **kein** Ensemble identischer Modelle. `_lerne_silhouette` verteilt die Lernbeispiele jeder Klasse reihum auf G Karten (`X[name][i::G]`), jede Karte trägt also andere Prototypen, und beim Erkennen ist das Klassenpotential das Maximum über alle Karten. Vier Karten bedeuten heute **viermal so viele Prototypen** (Kapazität) und Ausfallsicherheit durch den Wächter — aber jede Erkennung fragt alle Karten nacheinander ab.

1.0 fügt drei Nutzungsarten hinzu, die alle über einen gemeinsamen **Kartenverteiler** (F11) laufen:

| Rolle | Was | Gewinn | Profil |
|---|---|---|---|
| R1 Kapazität (heute) | Prototypen über Karten verteilt, max-Verbund | mehr Ansichten je Klasse, Ausfallsicherheit | alle |
| R2 Datenparallel | N Ausschnitte eines Frames gleichzeitig auf N freie Karten | Frame-Zeit = Maximum statt Summe bei mehreren Teilen | Voll |
| R3 Hypothesenparallel | k Zerlegungs-Hypothesen eines Blobs gleichzeitig bewerten, konsistenteste gewinnt | Überlappung: Qualität statt Geschwindigkeit | Voll |
| R4 Test-Time-Augmentation | ein Ausschnitt in 4 Lagen (0/90/180/270° bzw. gespiegelt) gleichzeitig; Urteil nur bei Einigkeit | weniger falsch-sichere Urteile | Voll, optional |

Randbedingung durch R1: Wenn Prototypen über Karten verteilt sind, muss ein Ausschnitt für ein vollständiges Urteil **alle** Karten sehen. R2–R4 funktionieren deshalb nur sauber, wenn jede Karte den **vollen** Prototypensatz trägt (Replikation) — oder in zwei Stufen (erst Vorauswahl auf einer Karte, dann Bestätigung auf allen). 1.0 wählt: **Replikation, solange der Prototypensatz auf eine Karte passt** (heute bis ~20 Neuronen je Klasse und Karte, Lernschicht halbiert sich automatisch bei Platzmangel), sonst Rückfall auf R1. Der Verteiler entscheidet das beim Lernen und zeigt es im Lernbericht an („repliziert auf 4 Karten“ / „verteilt auf 4 Karten“).

Nicht in 1.0: Modellsplitting (eine größere Netzarchitektur schichtweise über Karten). Forschungsstrang mit eigener Bench in 1.2.

---

## 6. Qualitätsziele (Zahlen, die auf die Website dürfen)

Alle Ziele werden auf dem **SE-Testsatz 1** gemessen (siehe 7). Label auf der Site: OUR OBSERVATION mit Datum und Build; Bench-Werte zusätzlich mit BENCH.

| # | Ziel | Wert | Heute belegt |
|---|---|---|---|
| Q1 | Falsch-sichere Urteile (falsche Klasse mit Übereinstimmung über Schwelle) | ≤ 0,5 % der Prüfungen | nicht gemessen |
| Q2 | Trefferquote bekannte Teile, einzeln liegend | ≥ 98 % | Gegenprobe auf Lernfotos (`treffer_eigen`), kein Testsatz |
| Q3 | Unbekanntes Teil wird als „unbekannt“ erkannt | ≥ 95 % | nicht gemessen |
| Q4 | Zwei überlappende Teile korrekt getrennt und klassifiziert | ≥ 90 % der Szenen | synthetisch: Selbsttest overlap/mixed OK; real: nicht gemessen |
| Q5 | Mittelpunktfehler median / Winkelfehler median | ≤ 0,5 mm / ≤ 1,0° (Kalibrierbrett) | synthetisch 0,22 mm / 0,33° (`run_selftest.py`) |
| Q6 | Leeres Band/Tisch: Falschteile | 0 in 1 000 Frames unter Referenzbeleuchtung | Bench 0 % (`test_glanz.py`, `test_farbmaske.py`); real nur visuell |
| Q7 | Auslöser → Urteil, Voll-Profil, bis 5 Teile | ≤ 1,0 s | Einzelbild 22,7 ms (Band, 1 Teil); stationär mit Hypothesen nicht gemessen |
| Q8 | Neue Klasse lernen (20 Fotos) bis einsatzbereit | ≤ 60 s | ~2 ms je Beispiel Chip-Zeit; Gesamtzeit inkl. Aufbereitung nicht protokolliert |
| Q9 | Ausfall einer Karte im Betrieb | Prüfung läuft weiter, Alarm einmal, Reset aus der UI | Bench `test_karten_waechter.py` OK; real 2026-09-20 |
| Q10 | Laptop-Modus | UI + Segmentierung + Messung + Hypothesen ohne Hardware, Stub klar gekennzeichnet | `run_web.py --synthetisch` vorhanden; Hypothesen neu |

Was wir bewusst **nicht** versprechen: Oberflächenfehler (Kratzer, Lackfehler), Teile ohne Silhouettenunterschied, Teile unter 8 mm im Bild, Prüfung bei wechselndem Umgebungslicht ohne Referenzbeleuchtung.

---

## 7. Benches und Testsatz

| Bench | Belegt | Status |
|---|---|---|
| `tools/test_farbmaske.py` | F2 / Q6 (synthetisch) | grün |
| `tools/test_glanz.py` | F1, F3 / Q6 (synthetisch) | grün |
| `tools/run_selftest.py` | F4, F5 / Q5 (synthetisch, 5 Szenen) | grün |
| `tools/test_m3_head.py` | SE-M3 Kopf | grün, experimental |
| `tools/test_karten_waechter.py` | F8 / Q9 | grün |
| `tools/test_linie_fluss.py` | Linie (nicht 1.0) | grün, experimental |
| **`tools/test_hypothesen.py`** | F10: synthetische Überlappungen mit bekannter Wahrheit, Hypothesenwahl ≥ 95 % korrekt | **neu** |
| **`tools/test_verteiler.py`** | F11: simulierte Karten, N Aufträge, max statt Summe, Ausfall mitten im Auftrag | **neu** |
| **`tools/test_mehrbild.py`** | F9: Rauschen sinkt mit N, Blendfleck-Flackern verschwindet | **neu** |
| **`tools/eval_testsatz.py`** | Q1–Q4, Q7, Q8 auf dem realen Testsatz; schreibt Konfusionsmatrix, Übereinstimmungs-Histogramm, Schwellenvorschlag | **neu** |

**SE-Testsatz 1** (real, mit F14 aufgenommen): 10 Klassen × 30 Fotos Lernmaterial, getrennt davon 100 Prüfszenen (40 einzeln, 30 mit zwei überlappenden Teilen, 15 mit unbekannten Teilen, 15 leer oder mit Störobjekten wie Schrauben/Spänen), jede Szene mit Soll-Klasse(n), Soll-Position auf dem Kalibrierbrett und Soll-Lage. Der Testsatz wird **nicht** zum Lernen verwendet und mit dem Release veröffentlicht (Zenodo-DOI), damit jeder die Zahlen nachrechnen kann.

Schwelle für F12: aus dem Übereinstimmungs-Histogramm von Testsatz-Treffern gegen Testsatz-Unbekannten so gewählt, dass Q1 eingehalten wird; der Wert steht im Lernbericht und auf der Website.

---

## 8. Arbeitspakete

| AP | Inhalt | Berührt | Prüfung |
|---|---|---|---|
| A1 | Betriebsart `stationaer`: Linienzonen, Band, Arm aus der UI und dem Zustand ausgeblendet; Auslöser-Taste und `/api/pruefen`; Kamera-Hauptbild als Prüfzone | `server.py`, `index.html`, `config.py` | jsdom-Smoke, synthetischer Lauf |
| A2 | Mehrbild-Aufnahme F9 (N Frames, optional 2 Belichtungen, Mittelung vor Segmentierung) | `server.py` (Aufnahme), `segmentation.py` | `test_mehrbild.py` |
| A3 | Hypothesenmodul F10: aus einem Blob k Zerlegungen erzeugen, Score mit Rezept-Maßen | `segmentation.py` → neues `hypothesen.py` | `test_hypothesen.py` |
| A4 | Kartenverteiler F11: Auftragsliste, freie Karten, Replikation beim Lernen, Rückfall R1 | `edge_learn.py` → neues `verteiler.py` | `test_verteiler.py`, Wächter-Bench bleibt grün |
| A5 | Unsicherheitsurteil F12 mit kalibrierter Schwelle, Anzeige „unbekannt / prüfen“ | `edge_learn.py`, `server.py`, UI | `eval_testsatz.py` |
| A6 | Testsatz-Werkzeug F14 in der UI (Szene aufnehmen, Soll eintragen, exportieren) | `server.py`, `index.html` | manuell + Export-Format-Test |
| A7 | `eval_testsatz.py` und SE-Testsatz 1 aufnehmen | `tools/` + Anlage | Bericht mit Q1–Q8 |
| A8 | Laptop-Modus prüfen: `--synthetisch` mit Hypothesen und Stub-Kennzeichnung | `synth.py`, `run_web.py` | Smoke |
| A9 | UI im SE-Design (Token-Tausch aus `spikingedge-brand-v26.css`, Logo, Schrift) | `index.html` CSS-Block | Screenshots |
| A10 | Repo-Hygiene und Release: LICENSE (PolyForm NC 1.0.0), COMMERCIAL.md, CONTRIBUTING (DCO+CLA), CITATION.cff, SAFETY.md, CHANGELOG, README (EN), `install.sh`, IPs/Benutzer/Backups raus, CI-Action für alle Benches | Repo | CI grün, frisches Pi nach README installierbar |
| A11 | Umbenennung Sichtbares (SE Inspect, SE-M3), danach Paket `seinspect/` | alles | Smoke + Anlage läuft |
| A12 | Website: Produktseite SE Inspect, Get SE Inspect, Guide-Pfad „Minimal“, Evidence mit Testsatz-Zahlen | `Website/content` | Link-Check, Live-Check |
| A13 | UI zweisprachig Deutsch/Englisch: Wörterbuch im Client, Umschalter im Kopf, Sprache gemerkt; Server-Meldungen (Lernbericht, Alarme, Ereignisse) über Schlüssel übersetzt | `index.html`, `server.py`, `edge_learn.py` | jsdom-Smoke in beiden Sprachen, keine untranslatierten Schlüssel |

Reihenfolge: A1 → A13 → A2 → A3 → A4 → A5 → A8 (Laptop früh, damit die Community mitlesen kann) → A6 → A7 → A9 → A10 → A11 → A12. A13 kommt direkt nach A1, weil die stationäre Oberfläche weniger Text hat als die Linien-UI und nur dieser übersetzt werden muss. A7 ist der einzige Schritt, der die Anlage und Zeit am Tisch braucht.

---

## 9. Release-Kriterien 1.0.0

1. Alle Benches aus Abschnitt 7 grün, in CI.
2. `eval_testsatz.py` auf SE-Testsatz 1: Q1–Q4, Q7, Q8 erfüllt; Bericht im Repo und auf der Evidence-Seite.
3. Q5 auf dem Kalibrierbrett real gemessen.
4. Q6 real: 1 000 Frames leer unter Referenzbeleuchtung, Protokoll im Repo.
5. Installation auf einem frisch geflashten Pi 5 nach README ohne Nachfrage bis zum ersten gelernten Teil (Minimal-Profil).
6. Laptop-Modus: `git clone` → drei Befehle → UI mit synthetischen Szenen.
7. Keine IP-Adressen, Benutzernamen, Backups oder Trainingsdaten im Repo.
8. Tag `v1.0.0`, CHANGELOG, Zenodo-DOI, Website umgestellt.

Versionierung ab Release: `MAJOR.MINOR.PATCH`; der Footer-Build-String wird zur Versionsnummer plus Git-Kurzhash.

---

## 10. Ausbaustufen

| Version | Inhalt |
|---|---|
| 1.1 | Band-Modus (Fluss-Takt) als optionales Modul mit eigener Zeitmessung auf echtem Band; Lichtschranke als Auslöser |
| 1.2 | Modellsplitting-Bench; Spezialkarten-Kaskade (Detektor → Feinklassifikator → On-Chip-Klassen → Anomalie) |
| 1.3 | Zweite Kamera (Lernzonen A/B), Arm-Abholung |
| 2.0 | Selbstlernende Zelle: unbekannte Fälle sammeln, Klassenvorschläge aus Clustern, Nachlernen mit einem Klick |

---

## 11. Risiken

- **Replikation vs. Kapazität (Abschnitt 5):** Wenn ein Anwender mehr Prototypen braucht, als auf eine Karte passen, fällt der Verteiler auf R1 zurück und R2–R4 greifen nicht. Das muss im Lernbericht sichtbar sein, sonst wundert sich der Anwender über die Geschwindigkeit.
- **Testsatz-Aufwand:** 100 Szenen mit Soll-Werten sind ein Nachmittag am Tisch, aber ohne sie bleiben Q1–Q4 Behauptungen.
- **Beleuchtung:** Die Zahlen gelten unter der Referenzleuchte. Die Website muss das so sagen.
- **Umbenennung:** Zwei Namen in Code und Doku gleichzeitig sind die größte Quelle für Verwirrung; deshalb A11 erst, wenn der Funktionsstand steht.
- **Silhouette als Grenze:** Teile, die sich nur in Farbe oder Oberfläche unterscheiden, trennt der Silhouettenmodus nicht. Für 1.0 ist das eine dokumentierte Grenze, kein Fehler.


## Nachtrag 2026-10-03: Industrie-Paket (nach den UI-Paketen 1–4)

Abgleich mit dem Standard bei Keyence (IV/CV-X), Cognex In-Sight, SICK Inspector, Omron FH. Ohne I1–I3 ist SE Inspect nicht in eine Anlage einbaubar.

| Nr | Inhalt | Kern |
|---|---|---|
| I1 | Digitale I/O | Trigger-Eingang (Lichtschranke/SPS), Ausgänge OK / NOK / Bereit / Fehler; Pi-GPIO über Optokoppler bzw. 24-V-I/O-HAT; Puls- und Halte-Modus, Watchdog „Bereit“ |
| I2 | Anbindung SPS/Leitrechner | Modbus TCP (Server) oder OPC UA, dazu MQTT bzw. einfaches TCP-Protokoll: Programm wählen, triggern, Ergebnis/Name/Konfidenz lesen |
| I3 | Benutzerrollen | Bediener / Einrichter / Admin mit PIN, Bedienansicht für Bediener fest; Änderungsprotokoll (wer, wann, was) |
| I4 | Prüfprogramme per I/O/API umschalten, Komplettsicherung als eine Datei (Export/Import) |
| I5 | Auto-Schwelle | aus Gut-/Schlecht-Beispielen des Testsatzes Schwelle vorschlagen (Keyence „Auto-Tuning“) |
| I6 | Kalibrierung mm | Kalibrierplättchen, Messwerte in mm |
| I7 | NG-Bildarchiv | Ablage, Filter, Export auf Netzlaufwerk |
| I8 | Positionsnachführung | Prüfbereiche folgen verschobenem/gedrehtem Teil |
| I9 | Statistik/Trend | Ausbeute über Zeit, Schichtzähler, Konfidenz-Drift |
| I10 | Offline-Simulation | Einstellung gegen gespeicherte Bilder (Testsatz) prüfen, bevor sie live geht |

Reihenfolge: I1 → I3 → I2 → I4 → I5, danach I6–I10.
