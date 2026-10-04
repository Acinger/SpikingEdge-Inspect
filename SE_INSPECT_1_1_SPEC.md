# SE Inspect 1.1 – Spezifikation

Stand 2026-10-03 · Build 1.9.65-selbstlernen · Ziel: die Zelle lernt aus dem eigenen Betrieb, die Schwelle wird gemessen statt geraten, und die Anlage merkt, wenn sie schlechter wird.

## A · Selbstlernende Zelle (Vorschläge aus unbekannten Teilen)

**Problem.** Jedes unbekannte Teil landet mit Bild im Prüfarchiv – bisher musste man jedes Bild einzeln einem Objekt zuordnen.

**Lösung.** `vorsa/selbstlernen.py` gruppiert die Archivbilder `*_unbekannt.jpg` nach Form und Farbe:

- Merkmale je Bild: Hu-Momente 1–4 (log), Seitenverhältnis, Füllgrad, Ausdehnung, Größe, Farbton (sin/cos × Sättigung), Sättigung, Helligkeit; gewichtet, Formmerkmale doppelt.
- Gruppierung agglomerativ, mittlere Verknüpfung (Lance-Williams), Grenze einstellbar (0,4–1,2; Vorgabe 0,7). 300 Bilder in Millisekunden; Merkmale je Datei im Speicher.
- Je Gruppe: Anzahl, Bilder, repräsentatives Bild, Streuung, „ähnelt X“ (nächstes gelerntes Objekt).

**Bedienung.** Anlernen › Karte „Vorschläge aus dem Betrieb“ → Dialog. Je Gruppe: *Als neues Objekt* (Name), *Zu Objekt …*, *Hintergrund*, *Verwerfen*. Höchstens 24 Fotos je Übernahme. Danach Hinweis mit Knopf „Training …“. Erledigte Bilder stehen in `vorschlaege_erledigt.json` und tauchen nicht mehr auf. Auch erreichbar aus „Nachlernen empfohlen“ in der Prüfung.

**API.** `GET /api/vorschlaege?grenze=0.7` · `POST /api/vorschlag_anwenden {aktion: neu|zu|hintergrund|verwerfen, dateien, name?, klasse?}` (Rolle Einrichter).

**Grenzen.** Kein Ersatz für saubere Lernfotos: Archivbilder sind Prüfausschnitte, nicht gezielt aufgenommen. Der Mensch entscheidet immer.

## B · Schwelle aus dem Testsatz

**Problem.** Die Konfidenzschwelle wurde nach Gefühl gesetzt.

**Lösung.** `vorsa/schwelle.py` + Testlauf im Server: jede Testsatz-Szene wird als Bild in die Erkennung gespeist (6 Durchläufe je Szene), das Ergebnis mit dem Soll verglichen. Für Schwellen 30–95 % (5er-Schritte) entstehen Trefferquote, Fremdteil-erkannt, Bekanntes-als-unbekannt und Falsch-sicher-Rate. **Vorschlag** = kleinste Schwelle (1 %-Schritte) mit Falsch-sicher ≤ 0,5 %. Ergebnis in `testsatz/schwellenkurve.json`.

**Bedienung.** Einstellungen › Erkennung › „Schwelle aus dem Testsatz“: Testlauf starten (Fortschritt), Tabelle, Vorschlag markiert, aktuelle Schwelle mit Punkt, Knopf „xx % übernehmen“. Hinweise bei < 20 Szenen und ohne Fremdteil-Szenen.

**API.** `POST /api/testlauf {aktion: start}` · `GET /api/testlauf`.

## C · Statistik & Trend mit Drift-Warnung

**Problem.** Das Prüfbuch zählt nur die Sitzung und vergisst beim Neustart.

**Lösung.** `vorsa/trend.py`: Journal `pruefjournal.jsonl` (eine Zeile je gebuchtem Teil, eine je Training; ab 20 MB gekürzt). Auswertung: 24 Stunden, 14 Tage (Teile, Gut-/Unbekannt-/Ausschuss-Quote, mittlere Sicherheit), **Drift**: mittlere Sicherheit der letzten 50 benannten Teile gegen die ersten 50 nach dem letzten Training; fällt sie um ≥ 8 Punkte → „Sicherheit sinkt“.

**Bedienung.** Prüfung › Reiter **Trend** (Heute, gestapelte Stundenbalken, Tagestabelle, Drift-Zeile). Drift-Warnung zusätzlich in der Prüfspalte mit Sprung zum Trend.

**API.** `GET /api/trend`.

## Tests

| Bench / Smoke | prüft |
|---|---|
| `tools/test_selbstlernen.py` | Merkmale, Gruppierung (stabil über Zufallssaaten), Vorschläge, Schwellenkurve |
| `tools/test_trend.py` | Journal, Stunden/Tage, Drift sinkt/stabil/zu wenig |
| `tools/test_1_1_server.py` | im Prozess: Journal = Prüfbuch, Vorschläge, Übernehmen, Ablehnungen; eigener Server: Routen, Training-Vermerk, Testlauf mit Kurve |
| `tools/smoke_elf.js` | Oberfläche: Trend-Reiter, Vorschläge-Dialog inkl. Regler und Übernahme, Auto-Schwelle inkl. Übernehmen, Englisch vollständig |

Alle bestehenden Benches, Smokes und der Rundgang (211 Schritte, 0 Fehler) laufen weiter grün. CI erweitert.
