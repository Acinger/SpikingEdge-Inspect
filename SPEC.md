# VORSA-M3 — Spezifikation v0.1

*Visual Overlap-Resilient Sparse Architecture, lokale Kapazität 3*

Stand: 2026-08-26 · Status: Entwurf · Grundlage: Projektbeschreibung Abschnitt 17

---

## 1. Was VORSA-M3 ist

Ein eigenständiger, kompakter Objektdetektor für den BrainChip AKD1500 mit
**frei definierbaren Objektklassen**. Nicht auf ein Material, Produkt oder eine
Formfamilie beschränkt: Schrauben, SD-Karten, Karabiner, Verpackungen,
Werkstücke — was vor dem Training festgelegt wird.

**Kein verkleinertes YOLO.** Eigener Merkmalsextraktor, eigener Kopf mit
lokaler Mehrfachbelegung, eigene Trainingszuordnung ohne feste Reihenfolge,
eigene Nachverarbeitung. YOLO bleibt Vergleichsmaßstab, nicht Vorlage.

**M3** heißt: bis zu drei stark überlagerte Objekte *pro lokaler Bildposition*
werden getrennt beschrieben. Nicht: nur drei Objekte im Bild. Mehrere
unabhängige Überlagerungsstellen im selben Bild sind ausdrücklich vorgesehen.

## 2. Kernziel (harte Bedingung)

Eine Modellvariante gilt nur dann als tauglich, wenn **alle** Punkte zutreffen:

1. genau ein physischer AKD1500 (`len(akida.devices())` genutzt: 1)
2. `model.map(device, hw_only=True)` ohne Exception → keine Schicht auf der CPU
3. `len(model.sequences) == 1` → eine einzige Hardwaresequenz
4. Sequenz-Backend = Hardware, nicht Software
5. NP-Verbrauch ≤ verfügbare NPs (`config.AKD1500_NP_BUDGET`, Default 32 —
   **vor Ort verifizieren**)
6. genau ein Hardwaredurchgang pro Bild, kein Umladen von Modellteilen

Geprüft **vor** dem Training, mit Zufallsgewichten: `tools/check_single_pass.py`.
Ausgabe `PASS` / `FAIL` mit Begründung. Erst bei PASS lohnt Training.

## 3. Schichtbeschränkung Akida 1.0

Erlaubt (`model_m3.ALLOWED_LAYERS`): `InputConvolutional`, `Convolutional`,
`SeparableConvolutional`, `FullyConnected`.

Nicht verfügbar und deshalb architektonisch ausgeschlossen: transponierte
Faltungen, Upsampling, auflösungsübergreifende Konkatenation, Batch-Norm als
Laufzeitschicht (wird beim Quantisieren gefaltet).

**Folge:** Meilenstein 1 beschreibt Objekte durch **gedrehte Rahmen**, nicht
durch Masken. Ein Maskendekoder braucht Upsampling — das kommt erst mit
VORSA-Seg (Meilenstein 2) und einer eigens dafür entworfenen Architektur.

## 3a. Gemessene Hardwaregrenzen

Gemessen am 2026-08-26 auf `PCIe/AKD1500/16MB/0`, Firmware `BC.A1.003.009`,
`IpVersion.v1`, MetaTF 2.19.3. Die Werte stammen aus Fehlermeldungen von
`model.map(hw_only=True)`, nicht aus einer Dokumentation — sie sind belastbar,
aber an diese Firmwareversion gebunden.

| Grenze | Wert | Meldung bei Überschreitung |
|---|---|---|
| Eingangskantenlänge | **≤ 256 px** | „maximum input second dimension size is 256" |
| Filter der Eingangsschicht | **≤ 64** | „num_neurons should be set between 1 and 64" |
| Kanäle am Kopfeingang | **≤ 256** | „Filter size is too big to fit in a CNP" |
| Neural Processors | **32** | — |

### Ergebnis der Kernziel-Prüfung

Alle Varianten mit Zufallsgewichten geprüft, `hw_only=True`, Modus `AllNps`:

| Variante | Eingang | Raster | Zelle | Sequenzen | Passes | AllNps | Bedarf | frei | |
|---|---|---|---|---|---|---|---|---|---|
| V2 | 224 px | 14×14 | 16 px | 1 | 1 | 29 | 5 | 27 | PASS |
| V3 | 160 px | 10×10 | 16 px | 1 | 1 | 32 | 4 | 28 | PASS |
| V4 | 224 px | 28×28 | 8 px | 1 | 1 | 23 | 14 | 18 | PASS |
| V5 | 256 px | 16×16 | 16 px | 1 | 1 | 32 | 5 | 27 | PASS |
| **V6** | **256 px** | **32×32** | **8 px** | 1 | 1 | 28 | 18 | 14 | **PASS** |
| V2-M1 | 224 px | 14×14 | 16 px | 1 | 1 | 30 | 5 | 27 | PASS |
| V2-M2 | 224 px | 14×14 | 16 px | 1 | 1 | 32 | 5 | 27 | PASS |
| X-gross | 224 px | — | — | — | — | — | — | — | FAIL ✓ |
| X-px320 | 320 px | — | — | — | — | — | — | — | FAIL ✓ |

Die beiden `X-`Varianten sind Gegenproben und **müssen** scheitern. Sie tun es,
jede an der vorhergesagten Stelle (Kopfeingang 512 bzw. Eingang 320 px). Damit
ist belegt, dass die Prüfung Fehler finden kann — ohne diesen Nachweis wäre
kein PASS etwas wert.

**Gewählte Variante: V6.** Sie erfüllt das Kernziel mit der feinsten
Rasterung, die die 256-px-Grenze zulässt, und lässt 14 NPs Reserve.

**Der begrenzende Faktor ist nicht die Rechenkapazität, sondern die
Eingangsauflösung.** Bei 256 px ist Schluss. Für kleine Objekte ist das die
eigentliche Schranke — nicht die Modellgröße.

### Was das feine Raster kostet

V6 erzeugt 32 × 32 × 3 = **3072 Slots** je Bild, V2 nur 588. Das ist kein
Hardwareproblem, aber ein Trainingsproblem: die weit überwiegende Mehrheit
der Slots ist leer, das Ungleichgewicht zwischen „Objekt" und „kein Objekt"
wächst entsprechend. Der Objektheits-Verlust braucht deshalb eine Gewichtung
(fokal oder feste Positiv-/Negativ-Quote), sonst lernt das Modell schlicht,
überall „kein Objekt" zu sagen.

Rückfallposition, falls das Training instabil bleibt: **V5** — gleiche
Auflösung, gröberes Raster, 588 Slots.

### MapMode — der Modus entscheidet über das Kernziel

| Modus | NPs | Passes | Bewertung |
|---|---|---|---|
| `Minimal` | 5 | 1 | Maßstab für den echten Bedarf |
| `AllNps` (Standard) | 29 | 1 | Betriebsmodus, verteilt für Durchsatz |
| `HwPr` | 47 | **2** | **verletzt das Kernziel, nicht verwenden** |

`AllNps` belegt absichtlich möglichst viele NPs, um den Durchsatz zu erhöhen.
Die dortige NP-Zahl ist eine Belegungsentscheidung, **keine Bedarfsangabe** —
wer sie als Kapazitätsgrenze liest, zieht falsche Schlüsse über die Reserve.

Verbindlich für die Prüfung ist deshalb: mapping im Betriebsmodus `AllNps` mit
`len(sequence.passes) == 1`, Kapazitätsreserve gemessen in `Minimal`.

## 3b. Prototypen-Lernen auf dem Chip

Gemessen am 2026-08-26, `tools/check_edge_learning.py`.

VORSA-M3 selbst lässt sich **nicht** auf dem Chip trainieren — ein Detektor mit
Boxen, Winkeln und Verdeckungsgraden lernt per Rückpropagierung auf einem PC.
Akida kann aber die letzte vollverbundene Schicht auf der Hardware lernen
lassen. Daraus folgt die Arbeitsteilung:

```
VORSA-M3        findet WO etwas liegt    fest, offline trainiert
Edge Learning   sagt WAS es ist          auf dem Chip, aus Prototypen
```

### Messwerte

| | |
|---|---|
| Lerngeschwindigkeit | **2 ms je Beispiel** |
| Beispiele je Klasse | 5 genügten |
| Merkmalsvektor | 512 Stellen, 38 % belegt |
| bestes `num_weights` | **48** ≈ ¼ der aktiven Merkmale (193) |
| Trefferquote | 75 % bei 5 Klassen, **mit Zufallsgewichten im Rumpf** |

`num_weights` ist die entscheidende Stellschraube. Ein zu kleiner Wert lässt
das Modell immer dieselbe Klasse antworten — ein Lauf mit `num_weights=1`
lieferte 20 % bei fünf identischen Antworten. Das sieht in einer Oberfläche
genauso erfolgreich aus wie ein funktionierender Lauf, deshalb muss die Zahl
der **verschiedenen** Antworten mit angezeigt werden, nicht nur die Trefferquote.

### Was das für die Bedienoberfläche bedeutet

Erlaubt: „Objekt hinlegen, fünf Aufnahmen, sofort erkannt." Bei 2 ms je
Beispiel ist das Lernen für den Bediener nicht wahrnehmbar.

**Nicht erlaubt**: der Eindruck, damit werde VORSA-M3 trainiert. Prototypen-
Lernen setzt einen trainierten Rumpf voraus und ersetzt das Training nicht.
Die Reihenfolge ist damit vorgegeben: erst VORSA-M3 trainieren, dann den
trainierten Rumpf als Merkmalsgeber für die Lernschicht nutzen.

### Offene Einschränkung

Ein AKD1500 hält genau ein Programm. Detektor und Lernklassifikator
gleichzeitig heißt zweiter Chip oder Umschalten zwischen Betriebsarten. Das
Umschalten widerspricht dem Kernziel nicht — das verbietet Umladen
*innerhalb einer Bilderkennung* — kostet aber Zeit und muss in der Oberfläche
als Betriebsartwechsel sichtbar sein.

## 4. Eingang

`uint8`, `H × W × 3`. Startwert 224 × 224 (`ModelConfig.input_size`).
Der Pi liefert das Bild bereits zugeschnitten, entzerrt und skaliert.

Rastergröße ergibt sich aus den Strides der Variante, nicht aus einer
freien Wahl. Bei 224 px und Gesamtstride 16: **14 × 14**.

## 5. Ausgabestruktur — der M3-Kopf

Pro Rasterfeld werden **M = 3 Objektausgänge (Slots)** und drei feldweite
Werte erzeugt. Kanäle pro Feld:

```
M * (8 + C) + 3
```

Pro Slot (8 + C Kanäle):

| Feld | Größe | Bedeutung |
|---|---|---|
| obj | 1 | Objekt vorhanden |
| tx, ty | 2 | Mittelpunkt relativ zum Feld |
| tw, th | 2 | Breite und Höhe |
| sin 2θ, cos 2θ | 2 | Drehwinkel |
| vis | 1 | sichtbarer Anteil (1 − Verdeckungsgrad) |
| Klassen | C | Klassenlogits |

Feldweit (3 Kanäle):

| Feld | Bedeutung |
|---|---|
| local_count | erwartete Objektzahl an dieser Stelle |
| overlap_prob | hier liegt eine Überlagerung vor |
| **local_overflow_prob** | hier sind vermutlich mehr Objekte, als M ausgeben kann |

C ist beim Modellbau frei wählbar. Zielbereich zunächst 1–16, später Test bis
etwa 20. Die tatsächliche Obergrenze entscheidet die Mapping-Prüfung, nicht
der Wunsch.

### 5.1 Warum kein Anker-Mechanismus

Größe wird direkt regressiert: `w = sigmoid(tw) · W_bild`, ebenso h. Keine
Ankerboxen, keine Anker-Zuordnung, kein Anker-Tuning.

Grund: Anker sind bei YOLO nötig, weil pro Zelle eine feste Zahl von
Formhypothesen bereitsteht. VORSA-M3 hat stattdessen M gleichwertige, ungebundene
Slots — eine Formhypothese je Slot wäre eine Beschränkung ohne Nutzen. Anker
würden zusätzlich an Objektgrößen des Trainingssatzes gebunden und damit dem
Ziel „frei definierbare Klassen und Größen" widersprechen.

### 5.2 Warum der Mittelpunkt über das Feld hinausreichen darf

`cx = (gx + 2·sigmoid(tx) − 0.5) · Feldbreite`, Wertebereich −0,5 bis +1,5 Felder.

Bei drei fast deckungsgleichen Objekten liegen die Mittelpunkte oft knapp
beiderseits einer Feldgrenze. Ein auf 0…1 begrenzter Offset zwingt sie in
verschiedene Felder — genau die Trennung, die M3 vermeiden soll.

### 5.3 Warum der Winkel als sin 2θ / cos 2θ

Ein Rahmen sieht bei θ und θ + 180° identisch aus. Ein direkt regressierter
Winkel hätte an der Naht 179° → 0° einen Sprung und läge dort systematisch
daneben. Das Paar (sin 2θ, cos 2θ) ist stetig; dekodiert wird über
θ = ½·atan2(sin 2θ, cos 2θ) mod 180°.

Bei runden Objekten ist der Winkel bedeutungslos — dann wird der Winkelanteil
des Verlusts über die Annotation abgeschaltet, statt Rauschen zu lernen.

## 6. Reihenfolgeunabhängige Trainingszuordnung

Slot 1 hat keine feste Bedeutung. Für jedes Rasterfeld wird die beste Zuordnung
zwischen den M Vorhersagen und den echten Objekten gesucht.

Bei M ≤ 4 wird über **alle Permutationen** exakt optimiert (M! ≤ 24). Das ist
billiger und exakter als eine Ungarische Methode und braucht keine
Fremdbibliothek. Ab M ≥ 5 wäre `scipy.optimize.linear_sum_assignment` nötig.

Zuordnungskosten je Paar (Vorhersage, echtes Objekt):

```
Kosten = w_pos·|Δ Mittelpunkt| + w_size·|Δ Größe|
       + w_ang·(1 − cos(2Δθ)) + w_cls·(1 − p_richtige_Klasse)
```

Die Zuordnung läuft nur beim Training auf einem normalen Rechner. Auf dem
AKD1500 entsteht dadurch keinerlei Zusatzlast.

## 7. Verlustfunktion

| Anteil | Form | gilt für |
|---|---|---|
| Objektheit | binäre Kreuzentropie | alle Slots |
| Mittelpunkt | Smooth-L1 | zugeordnete Slots |
| Größe | Smooth-L1 auf log-Größe | zugeordnete Slots |
| Winkel | 1 − cos(2Δθ) | zugeordnete Slots, außer runde Objekte |
| Sichtbarkeit | L1 | zugeordnete Slots |
| Klasse | Kreuzentropie | zugeordnete Slots |
| local_count | L1 | alle Felder |
| overlap_prob | binäre Kreuzentropie | alle Felder |
| overflow_prob | binäre Kreuzentropie | alle Felder |

Leere Slots lernen ausschließlich `obj → 0`. Ihre Koordinaten werden nicht
bestraft — sonst würden alle Slots zur Bildmitte gezogen.

## 8. Nachverarbeitung

Zwei Objekte aus **demselben Rasterfeld, aber verschiedenen Slots** sind
konstruktionsbedingt verschiedene Objekte. Sie dürfen einander **nie**
unterdrücken, egal wie stark ihre Rahmen überlappen. Genau hier verliert
Standard-NMS bei Überlagerungen das zweite Objekt.

Unterdrückt wird nur zwischen *verschiedenen* Feldern, und dort per **Soft-NMS**
(Score senken statt löschen) auf **gedrehten** Rahmen.

Startwerte für die Versuchsreihe: `score_thresh` ∈ {0,20 / 0,25 / 0,30},
`iou_thresh` ∈ {0,55 / 0,65 / 0,75}. Startwerte, keine Zielwerte.

Bei `local_overflow_prob` über der Schwelle meldet das System die Stelle als
überfüllt, statt eine Objektzahl vorzutäuschen. Der Pi kann daraufhin ein
weiteres Bild, die zeitliche Verfolgung oder eine zweite Kamera anfordern.

## 9. Physikalische Grenze

Ein vollständig verdecktes Objekt liefert im Einzelbild keine Bildinformation.
Das ist keine Trainingsfrage. VORSA-M3 erkennt **teilweise** verdeckte Objekte;
vollständig unsichtbare brauchen zeitliche Verfolgung, eine zweite Ansicht,
einen anderen Sensor oder mechanische Vereinzelung.

Das System meldet in solchen Fällen `UNRESOLVED`, statt zu raten.

## 10. Trainingsdaten

Jedes Objekt einzeln annotiert, auch teilweise verdeckt: Klasse, vollständiger
Mittelpunkt, gedrehter Rahmen, Breite, Höhe, Winkel, sichtbarer Bereich,
geschätzter verdeckter Bereich, Verdeckungsgrad, Objekt-ID bei Tracking.

Verdeckungsstufen: 0–10 %, 10–30 %, 30–50 %, 50–70 %, über 70 %.

Pflichtanteile: zwei Objekte gleicher Klasse, zwei verschiedener Klassen, drei
gleicher, drei verschiedener; ähnliche und unterschiedliche Mittelpunkte;
ähnliche und stark verschiedene Winkel; klein auf groß und groß auf klein;
Negativbilder ohne jede gesuchte Klasse.

Künstlich zusammengesetzte Bilder sind erlaubt und sinnvoll. Die **abschließende
Qualitätsmessung** muss aber mit echten, bisher ungesehenen Kamerabildern
erfolgen.

## 11. Messgrößen

Erkennungsrate frei / teilverdeckt / bei 2 lokalen / bei 3 lokalen Objekten;
korrekte Gesamtanzahl; Klassenfehler; Fehlalarme; Positions-, Größen- und
Winkelfehler; Zeit pro Bild; Bilder pro Sekunde; Energie pro Bild.

Leitgröße ist nicht Geschwindigkeit, sondern:

```
Energie pro korrekt erkanntem Objekt
= Gesamtenergie (Pi + Kamera + AKD1500 + Trägerplatine)
  / Anzahl korrekt erkannter Objekte
```

Praxisnah: **Wattstunden pro 1.000 korrekt verarbeitete Objekte.**

Vergleichsreihe: reine Pi-Bildverarbeitung · kleines YOLO auf AKD1500 ·
VORSA-M1 · M2 · M3 · M3 mit Pi-Tracking zwischen Erkennungsbildern ·
bedarfsgesteuerte Nutzung weiterer Chips.

## 12. Rolle des Raspberry Pi

Kein Notbehelf, sondern Bestandteil. Er darf alles Nicht-Neuronale übernehmen:
Aufnahme, Zuschnitt, Perspektivkorrektur, Skalierung, Helligkeitsnormalisierung,
Differenzbilder, geometrische Prüfungen, zeitliche Verfolgung, Darstellung,
Maschinensteuerung.

Legitim ist sein Einsatz, wenn er mindestens eines bewirkt: weniger
Gesamtenergie, höhere Genauigkeit, weniger Akida-Durchgänge, kleineres Modell,
stabilere Verarbeitung, besseres Tracking.

Unverändert gilt: die **gelernte** Objekterkennung läuft vollständig auf einem
AKD1500 in einem Durchgang.

## 13. Abnahmekriterien Meilenstein 1

| Nr. | Kriterium |
|---|---|
| A1 | eigene Architektur und Implementierung |
| A2 | Klassenanzahl beim Modellbau festlegbar |
| A3 | mehrere Objektformen und -größen erkannt |
| A4 | viele Objekte gleichzeitig im Bild |
| A5 | mehrere unabhängige Überlagerungsstellen verarbeitet |
| A6 | bis zu 3 lokal überlagerte Objekte getrennt ausgegeben |
| A7 | bei mehr als 3 lokalen Objekten Überfüllungswahrscheinlichkeit |
| A8 | vollständiges neuronales Modell auf genau einem AKD1500 |
| A9 | eine Hardwaresequenz |
| A10 | genau ein Hardwaredurchgang pro Bild |
| A11 | keine neuronale Schicht auf dem Pi |
| A12 | nicht-neuronale Vor-/Nachverarbeitung auf dem Pi erlaubt |
| A13 | Geschwindigkeit, Genauigkeit, Energie gemessen |
| A14 | gegen kleines YOLO-Vergleichsmodell geprüft |
| A15 | keine Detektion wird stillschweigend verworfen — alles protokolliert |

## 14. Beispielanwendung Förderband

Als erste konkrete Anwendung dient ein Förderband mit PU-Kunstlederteilen
(80 × 22 × 1,2 mm). Diese Anwendung liefert echte Bilder, echte Überlagerungen
und eine Referenzstrecke ohne neuronales Netz.

Sie ist **Anwendungsfall, nicht Modellannahme**. Die Sollgeometrie steht
ausschließlich im Anwendungsteil (`vorsa/config.py`, Abschnitt Beispiel-
anwendung, sowie `segmentation.py` / `fitting.py`) und geht nirgends in die
Modellarchitektur ein.

Nutzen dieser Strecke:

- Referenzwert für den Energievergleich (Punkt 1 der Vergleichsreihe)
- Erzeugung annotierter Überlagerungsbilder für das Training
- Rückfallebene, falls das Modell an einer Stelle versagt

## 15. Offene Punkte

- [ ] NP-Budget des AKD1500 vor Ort auslesen
- [ ] Mindestobjektgröße in Bildpunkten festlegen (Abschnitt 4.2 Projektstand)
- [ ] Klassenliste der ersten Anwendung festlegen
- [ ] Schwellwert für `local_overflow_prob` empirisch bestimmen
- [ ] Messaufbau für die Energiemessung (Strommesspunkt, Integrationsdauer)
- [ ] YOLO-Vergleichsmodell auswählen und auf AKD1500 mappen
- [ ] Behandlung von Objekten, die teilweise außerhalb des Bildes liegen
