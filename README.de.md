# VORSA-M3 v0.1

*Visual Overlap-Resilient Sparse Architecture* — eigenständiger, kompakter
Objektdetektor für den BrainChip AKD1500, mit frei definierbaren Objektklassen.

Kernziel: **ein AKD1500, eine Hardwaresequenz, ein Hardwaredurchgang.**

Spezifikation und Abnahmekriterien: **SPEC.md**

---

## Was heute schon läuft

### 1. Der M3-Kopf — das, was VORSA von einem verkleinerten YOLO unterscheidet

```bash
python3 tools/test_m3_head.py
```

Prüft ohne Hardware und ohne Training, ob die Ausgabelogik hält, was M3
verspricht. Aktuelles Ergebnis:

```
Kopf: 14x14x51 = 3 Slots x (8 + 8 Klassen) + 3 feldweite Werte

nach Soft-NMS mit Feldschutz:              8 Treffer
zum Vergleich, Standard-NMS ohne Schutz:   4 Treffer

[OK] Stelle A: 3 lokal überlagerte Objekte getrennt erhalten
     Rahmen-IoU der beiden stärksten: 0.84  (Standard-NMS hätte gelöscht)
[OK] Stellen B und C unabhängig verarbeitet
[OK] Überfüllung an Stelle C gemeldet (local_count 5, ausgegeben 3)
[OK] Duplikat aus Nachbarfeld zusammengefasst
[OK] Gegenprobe: ohne Feldschutz gehen 4 Objekte verloren
[OK] Zuordnung reihenfolgeunabhängig: Slot→Objekt [1, 0, 2]
```

Die vorletzte Zeile ist der eigentliche Punkt: Standard-NMS verliert bei
diesen Überlagerungen die Hälfte der Objekte. Der Feldschutz behält sie.

### 2. Die Pi-Referenzstrecke (Beispielanwendung Förderband)

```bash
python3 tools/run_selftest.py --use-background --out selftest_out
```

Vollständige Bildverarbeitung ohne neuronales Netz, auf synthetischen Bildern
mit bekannter Teilezahl:

| Szene | erwartet | erkannt | |
|---|---|---|---|
| free | 2 | 2 | frei liegende Teile |
| touching | 2 | 2 | Watershed trennt Berührung |
| overlap | 2 | 2 | Rechteck-Zerlegung trennt Überlappung |
| mixed | 5 | 5 | beides gemischt |
| stacked | 1 | 1 | deckungsgleich gestapelt → korrekt als 1 gemeldet |

Mittelpunktfehler median 0,23 mm, Winkelfehler median 0,33°, rund 15 ms je Bild.

Diese Strecke ist **Referenzwert für den Energievergleich** (Punkt 1 der
Vergleichsreihe in SPEC.md Abschnitt 11) und Quelle annotierter
Überlagerungsbilder — nicht die Modellarchitektur. Beispielbilder in
`beispielbilder/`.

Die Zahlen stammen aus synthetischen Bildern mit perfekter Kalibrierung. Am
echten Band werden sie schlechter. Der Test zeigt nur, dass die Rechenkette
selbst keinen Fehler einbaut.

---

## Der M3-Kopf im Detail

Pro Rasterfeld: **M = 3 gleichwertige Objektausgänge (Slots)** plus drei
feldweite Werte.

```
M * (8 + C) + 3   Kanäle je Feld

Slot:      obj, tx, ty, tw, th, sin2θ, cos2θ, vis, Klasse_0..C-1
feldweit:  local_count, overlap_prob, local_overflow_prob
```

Bei C = 8 und M = 3: 51 Kanäle, Gitter 14 × 14 bei 224 px Eingang.

**Ankerfrei.** Größe wird direkt regressiert. Ankerboxen wären an die
Objektgrößen des Trainingssatzes gebunden und würden dem Ziel „frei
definierbare Klassen und Größen" widersprechen.

**Mittelpunkt darf über die Feldgrenze reichen** (−0,5 bis +1,5 Felder). Bei
drei fast deckungsgleichen Objekten liegen die Mittelpunkte oft knapp
beiderseits einer Feldgrenze — ein auf 0…1 begrenzter Offset würde sie
auseinanderzwingen.

**Winkel als sin 2θ / cos 2θ**, weil ein Rahmen bei θ und θ + 180° gleich
aussieht. Ein direkt regressierter Winkel hätte an der Naht 179° → 0° einen
Sprung. Bei runden Objekten wird der Winkelanteil des Verlusts abgeschaltet,
statt Rauschen zu lernen.

**Slot 1 hat keine feste Bedeutung.** Die Zuordnung zwischen Vorhersagen und
echten Objekten wird bei jedem Trainingsschritt neu gesucht — exakt über alle
Permutationen, weil M! ≤ 24 billiger ist als eine Ungarische Methode und keine
Fremdbibliothek braucht (`vorsa/assignment.py`).

**Nachverarbeitung schützt gleiche Felder.** Zwei Treffer aus demselben Feld,
aber verschiedenen Slots, sind konstruktionsbedingt zwei verschiedene Objekte
und unterdrücken einander nie. Zwischen verschiedenen Feldern wird weich
unterdrückt (Soft-NMS auf gedrehten Rahmen).

**Überfüllung wird gemeldet, nicht überspielt.** Liegt `local_overflow_prob`
über der Schwelle, meldet das System „hier sind vermutlich mehr Objekte als M",
statt eine Zahl vorzutäuschen. Der Pi kann daraufhin ein weiteres Bild, die
zeitliche Verfolgung oder eine zweite Kamera anfordern.

---

## Weboberfläche

```bash
python3 tools/run_web.py                 # Kamera 0
python3 tools/run_web.py --synthetisch   # ohne Kamera, zum Ausprobieren
```

Dann im Browser `http://<Pi-Adresse>:8080` — vom Pi, vom PC oder vom Handy im
selben Netz. **Damit entfällt das Bildschirmproblem:** die Oberfläche braucht
keine Anzeige auf dem Pi, sie liefert eine.

Nur Standardbibliothek, kein Flask, keine Installation. Eine Abhängigkeit
weniger, die zu MetaTF passen müsste.

Enthalten: Livebild mit Erkennungsüberlagerung, Aufnahme mit Klassenzuordnung,
Galerie, Augmentierung je Klasse mit Variantenvorschau, Messwerte und
Hardwarediagnose.

### Händigkeit

Bei Bauteilen mit linker und rechter Ausführung darf **nicht** gespiegelt
werden — die gespiegelte linke Ausführung ist die rechte, also ein falsches
Beispiel für dieselbe Klasse. Der Schalter *Händigkeit* je Klasse sperrt das
Spiegeln und zeigt eine Begründung an, statt die Einstellung stillschweigend
zu ignorieren.

Gemessen: 8 Varianten je Aufnahme werden mit Händigkeit zu 4.

### Winkelmitführung

Beim Drehen und Spiegeln wandern die Winkel der Annotation mit. Wer das
vergisst, trainiert dem Modell systematisch falsche Winkel an.

```python
from vorsa.augment import pruefe_winkelmitfuehrung
print(pruefe_winkelmitfuehrung())     # leere Liste = alle 30 Fälle stimmen
```

Dieser Selbsttest hat beim Bau einen echten Fehler gefunden: bei freier
Drehung stand der Winkel um exakt 90° falsch. Die Fälle 90°, 180° und 270°
waren unauffällig — dort ist der Vorzeichenfehler modulo 180° unsichtbar.
Erst 45° hat ihn gezeigt. Im Training wäre er als unerklärlich hoher
Winkelfehler aufgetaucht und leicht dem Modell zugeschrieben worden.

### Prototypen-Lernen

Gemessen auf dem AKD1500: **2 ms je Beispiel**, 5 Aufnahmen je Klasse
genügten, bestes `num_weights` = 48. Trefferquote 75 % bei 5 Klassen — und
zwar **mit Zufallsgewichten im Rumpf**.

Wichtig für die Erwartung: Prototypen-Lernen betrifft die letzte Schicht und
setzt einen trainierten Rumpf voraus. Es ersetzt das Training von VORSA-M3
nicht, es baut darauf auf. Details in SPEC.md Abschnitt 3b.

## Trainingskette

**Erst prüfen, welcher Weg offen ist:**

```bash
python3 tools/check_training_env.py
```

**Dann der Durchstich** — trainiert 60 Schritte auf synthetischen Daten,
quantisiert, wandelt nach `.fbz`, mappt auf den Chip und schickt ein Bild
durch:

```bash
python3 tools/train_smoke.py --steps 60 --batch 4
```

Ohne Akida-Hardware am Trainingsrechner:

```bash
python3 tools/train_smoke.py --steps 60 --skip-map
```

Das Ziel ist **kein gutes Modell**, sondern der Nachweis, dass die Kette
geschlossen ist. Ein fallender Verlust auf 60 Schritten beweist nur, dass
Gradienten ankommen — über Erkennungsleistung sagt er nichts. Der Schritt
steht trotzdem vor der Datenerfassung: bricht die Kette, wäre jede vorher
investierte Annotationsarbeit verloren.

Schritt 2 des Durchstichs vergleicht die Keras-Ausgabeform mit der geprüften
Akida-Variante und bricht bei Abweichung ab. Sonst könnte man ein Modell
trainieren, für das die Kernziel-Prüfung nie stattgefunden hat.

### Arbeitsteilung

| | braucht | Aufgabe |
|---|---|---|
| PC | `tensorflow`, `cnn2snn` | bauen, trainieren, `.fbz` erzeugen |
| Pi | `akida` (vorhanden) | `.fbz` laden, mappen, messen |

Das Training braucht keinen Akida-Chip. Nur die Umwandlung braucht `cnn2snn`
— und die läuft ebenfalls ohne Hardware.

### Was beim feinen Raster zu beachten ist

V6 erzeugt 3072 Slots je Bild, davon sind typisch 40 belegt — ein Verhältnis
von etwa **1:500**. Ohne Gegenmaßnahme ist „überall kein Objekt" die bequemste
Lösung, und der Verlust fällt dabei überzeugend. Deshalb ist die Objektheit
fokal gewichtet (`losses.LossWeights`).

Zweitens: bei 8 px Zellgröße landen zwei überlappende Objekte mit 15 px
Mittelpunktabstand in **verschiedenen** Feldern. Die lokale Mehrfachbelegung
wird dann nie geübt, Slot 2 und 3 bleiben untrainiert. Der Datengenerator
erzeugt deshalb gezielt Stellen mit fast deckungsgleichen Mittelpunkten
(`p_koinzident`). Kontrolle:

```python
from vorsa import synth_objects
b, l = synth_objects.make_batch(40, cell_px=8.0)
print(synth_objects.statistik(l, grid=32, image_px=256))
```

Die Zeilen `felder_2_objekte` und `felder_3_objekte` müssen deutlich über null
liegen — sonst lernt das Modell M3 nie, egal wie gut alles andere aussieht.

## Automatische Übertragung

`watch.ps1` überträgt jede Änderung von selbst auf den Pi. Einmal in
PowerShell starten und das Fenster offen lassen:

```powershell
cd C:\vorsa-m3
.\watch.ps1
```

Einmalig statt dauerhaft: `.\sync.ps1`

Beide Skripte zeigen nach der Übertragung die Versionsmarke aus
`vorsa/model_m3.py` — lokal und auf dem Pi. Stimmen die beiden Zeilen nicht
überein, ist die Übertragung nicht angekommen und jedes Prüfergebnis wäre
wertlos. Genau dieser Fall hat am 26.08. drei Prüfläufe unbrauchbar gemacht.

**SSH-Schlüssel einrichten**, sonst fragt jede Übertragung nach dem Passwort:

```powershell
ssh-keygen -t ed25519 -C "vorsa-m3"
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh <user>@<PI-IP> "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"
```

Danach `ssh <user>@<PI-IP> hostname` — kommt `<pi-hostname>` ohne
Passwortabfrage, läuft der Wächter störungsfrei.

Andere Adresse oder anderer Benutzer: `.\watch.ps1 -Pi benutzer@10.0.0.5`

## Inbetriebnahme auf dem Pi

```bash
pip install opencv-python numpy akida
```

**Kernziel prüfen** (mit angeschlossenem AKD1500) — der erste echte Schritt:

```bash
python3 tools/check_single_pass.py            # alle Varianten
python3 tools/check_single_pass.py --list     # nur Topologien, ohne Hardware
```

Verfügbare Varianten (Stand nach der Messung vom 26.08.):

| | Eingang | Gitter | Zelle | Zweck |
|---|---|---|---|---|
| V2 | 224 px | 14×14 | 16 px | gemessen: 1 Pass, 5 NPs. Referenz |
| V3 | 160 px | 10×10 | 16 px | gemessen: 1 Pass, 4 NPs |
| **V4** | 224 px | 28×28 | **8 px** | feines Raster für kleine Objekte |
| **V5** | 256 px | 16×16 | 16 px | maximale zulässige Eingangsgröße |
| **V6** | 256 px | 32×32 | **8 px** | beides — der ehrgeizigste Kandidat |
| X-gross | 224 px | 14×14 | 16 px | **muss scheitern**: Kopfeingang 512 |
| X-px320 | 320 px | 20×20 | 16 px | **muss scheitern**: über 256 px |
| V2-M1 | 224 px | 14×14 | 16 px | Vergleichsprofil ohne Mehrfachbelegung |
| V2-M2 | 224 px | 14×14 | 16 px | Vergleichsprofil M2 |

Die beiden `X-`Varianten sind Gegenproben. Gehen sie durch, ist die Prüfung
kaputt und kein PASS ist etwas wert.

Kapazität ist nicht der Engpass: V2 braucht 5 von 32 NPs. Begrenzend ist die
Eingangsauflösung, die bei 256 px hart endet — siehe SPEC.md Abschnitt 3a.

**Referenzstrecke kalibrieren** (nur für die Förderband-Anwendung):

```bash
python3 tools/calibrate_board.py --click --width-mm 200 --height-mm 150
python3 tools/run_live.py --calib calibration.json --grab-background band_leer.png
python3 tools/run_live.py --calib calibration.json --background band_leer.png
```

---

## Aufbau

```
vorsa/
  config.py        MODELL (allgemein) und BEISPIELANWENDUNG streng getrennt
  model_m3.py      Merkmalsextraktor + M3-Kopf, Varianten, Mapping-Prüfung
  postprocess.py   Kopf dekodieren, slot-bewusste Soft-NMS, Überfüllung
  assignment.py    reihenfolgeunabhängige Zuordnung, Zielgitter, Verlustbausteine
  detection.py     gedrehte Box, Detektion, Verdeckungsgrad
  akida_pool.py    Arbeitswarteschlange über bis zu 4 AKD1500
  pipeline.py      Hauptschleife, Profile P1 und P2
  tracking.py      Objekt-IDs über die Zeit
  overlay.py       Rahmen, Konturen, IDs zeichnen
  calibration.py   Perspektivkorrektur, Pixel ↔ Millimeter   (Anwendung)
  segmentation.py  Vordergrundmaske, Watershed               (Anwendung)
  fitting.py       Sollrechteck an sichtbare Kanten           (Anwendung)
  crops.py         gedrehte Ausschnitte für Profil P1         (Anwendung)
  synth.py         synthetische Testszenen                    (Anwendung)
tools/
  test_m3_head.py      M3-Ausgabelogik prüfen, ohne Hardware
  check_single_pass.py ein Chip, eine Sequenz, ein Pass
  run_selftest.py      Referenzstrecke ohne Hardware
  calibrate_board.py   Kalibrierung
  run_live.py          Livebetrieb
```

Die mit *(Anwendung)* markierten Module kennen die Förderbandgeometrie. Für
eine andere Anwendung wird nur dieser Block ersetzt; Modell, Kopf und
Nachverarbeitung bleiben unberührt.

---

## Die zwei Profile

**P1 — Hybrid.** Der Pi macht Geometrie und Konturen, bis zu vier AKD1500
klassifizieren Ausschnitte parallel. Vier Chips sind kein vierfach großer
Prozessor: jedes Modell gehört genau einem Gerät, die Verteilung macht der Pi.
Ohne trainiertes Modell läuft der Pool im Stub-Modus und gibt bewusst eine
flache Verteilung mit Konfidenz 1/C zurück — damit im Log sofort sichtbar ist,
dass hier noch kein echtes Modell arbeitet.

**P2 — Single-Pass (das eigentliche Ziel).** Ein AKD1500 verarbeitet das ganze
Bild in einem Hardwaredurchgang. Code und Nachverarbeitung stehen und sind
getestet; das Modell muss zuerst `check_single_pass.py` bestehen und dann
trainiert werden.

---

## Physikalische Grenze

Ein vollständig verdecktes Objekt liefert im Einzelbild keine
Bildinformation. Das ist keine Trainingsfrage. VORSA-M3 erkennt **teilweise**
verdeckte Objekte; vollständig unsichtbare brauchen zeitliche Verfolgung, eine
zweite Ansicht, einen anderen Sensor oder mechanische Vereinzelung.

Das System meldet in solchen Fällen `UNRESOLVED`, statt zu raten. Im Overlay
werden rekonstruierte Kanten **gestrichelt** gezeichnet: was das Programm nicht
gesehen, sondern ergänzt hat, muss man ansehen können.

---

## Was noch gemessen werden muss

In `config.py` als TODO markiert:

- NP-Budget des AKD1500 (`AKD1500_NP_BUDGET`, aktuell 32 angenommen)
- Schwellwert für `local_overflow_prob` (`HeadThresholds.overflow_thresh`)
- Mindestobjektgröße in Bildpunkten
- Klassenliste der ersten Anwendung
- Bandausschnitt und Bandgeschwindigkeit für die Referenzstrecke

Solange die Bandgeschwindigkeit 0 ist, arbeitet das Tracking rein
positionsbasiert. Das reicht für langsame Bänder, nicht für schnelle.

---

## Nächste Schritte

1. `check_single_pass.py` auf dem Pi → welche Variante besteht das Kernziel?
2. Klassenliste festlegen, Bilder aufnehmen und annotieren (SPEC.md 10)
3. Training mit reihenfolgeunabhängiger Zuordnung aufsetzen (SPEC.md 6/7)
4. Kleines YOLO als Vergleichsmodell auf denselben Daten trainieren
5. Messaufbau für Energie pro korrekt erkanntem Objekt
6. Abnahmekriterien A1–A15 an echten Bildern nachweisen
