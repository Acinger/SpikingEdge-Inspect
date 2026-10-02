# VORSA INSPECT / VORSA-M3 — Projektbericht für die Website (Alpha-Stand 1.9.37)

Stand: 26. September 2026 · Software-Build `1.9.37-lernrahmen` · Oberfläche „UI 2.2"

Dieser Text ist die technische Grundlage für den Blog. Alle Zahlen sind entweder **gemessen** (dann steht dabei, womit) oder **aus dem Prüfstand** (synthetische Bilder, dann steht das dabei). Was noch nicht belegt ist, steht unter „Offene Punkte" — nicht im Fließtext als Behauptung.

---

## 1. Worum es geht

**VORSA INSPECT** ist eine industrielle Bilderkennungsanlage im Kleinformat: ein Förderband, zwei Kameras, ein Raspberry Pi 5 und vier neuromorphe BrainChip-Akida-Karten (AKD1500). Teile werden in einer Anlieferzone erkannt und beurteilt (gut / unbekannt / Ausschuss), das Band fördert sie in eine Abholzone, ein Roboterarm räumt sie ab. Angelernt wird direkt an der Anlage mit wenigen Fotos, in Sekunden, ohne GPU.

**VORSA-M3** (*Visual Overlap-Resilient Sparse Architecture, lokale Kapazität 3*) ist der dazugehörige, selbst entworfene Objektdetektor für den AKD1500. Sein Kernziel: die vollständige neuronale Erkennung läuft auf **genau einem AKD1500 in einem einzigen Hardwaredurchgang**, mit frei definierbaren Klassen, und beschreibt bis zu drei stark überlagerte Objekte *pro Bildstelle* getrennt. Es ist bewusst kein verkleinertes YOLO.

Das Projekt wurde von einem Nicht-Programmierer mit KI-Unterstützung (Claude für den Code, ChatGPT für Design-Vorgaben) aufgebaut. Das ist kein Nebensatz: Viele Entscheidungen unten sind dokumentiert, *weil* sie ohne Vorwissen getroffen werden mussten — und die Dokumentation war das, was Fehler gefunden hat.

---

## 2. Die Anlage (Hardware)

| Komponente | Details |
|---|---|
| Rechner | Raspberry Pi 5, Raspberry Pi OS Bookworm (64-bit, Debian 12, Python 3.11), Kernel 6.12 |
| Neuromorphe Beschleuniger | 4 × BrainChip AKD1500 (PCIe, je 16 MB Host-DDR-Fenster, 32 Neural Processors je Karte), MetaTF/akida 2.19.3, Firmware `BC.A1.003.009` |
| Kameras | 2 × Raspberry Pi Camera Module 3 (Sensor imx708, Betrieb bei 2304 × 1296 px), an beiden CSI-Ports des Pi 5. Benannt nach Einbaulage: „1. Cam (links)" und „2. Cam (rechts)" |
| Förderband | 12-V-Motor, geschaltet über ein Relaismodul an GPIO 18 (High-Trigger); nur an/aus, eine Richtung |
| Roboterarm | 3-Achs-Schrittmotorarm auf RAMPS 1.4 / Arduino Mega 2560, eigene Firmware „VORSA-ARM 1.0" (115200 Baud), Pumpe/Greifer an D10; per USB direkt am Pi 5 (`/dev/ttyACM0`). Alternativ ein externer Arm-Server auf einem Pi 4 (HTTP) |
| Bedienung | Weboberfläche im Browser (PC, Tablet, Handy im selben Netz), keine Anzeige am Pi nötig |

Wichtige Erfahrung zur Hardware: Die Akida-Karten sitzen hinter einem PCIe-Switch (Bus `0001:xx`). Eine Karte kann im Betrieb „hängen bleiben" (`akida-pcie … DMA wait completion timed out`), ohne dass der PCIe-Link ausfällt. Das ist am 20.09.2026 einmal aufgetreten und wurde ohne Neustart mit einem PCIe-Remove/Rescan behoben (Abschnitt 8).

---

## 3. Softwarearchitektur

Alles läuft in **einem Python-Prozess** auf dem Pi (`tools/run_web.py`), der von `systemd` als Dienst `vorsa` gestartet wird. Der Webserver nutzt nur die Python-Standardbibliothek (kein Flask), die Oberfläche ist eine einzelne `index.html`.

```
Kamera(s) ──► Segmentierung (Pi, OpenCV) ──► Kandidaten (Rahmen, Konturen)
                                                   │
                        ┌──────────────────────────┼─────────────────────────┐
                        ▼                          ▼                         ▼
              Silhouetten-Abgleich          M3-Detektor (optional)      Geometrie/Tracking
              auf Karten 0–2 (Verbund)      auf Karte 3                 (Pi)
                        └──────────────► Fusion, Urteil, Prüfbuch ◄──────────┘
                                                   │
                                Linien-Zustandsmaschine (Band, Zonen, Arm)
                                                   │
                                     Weboberfläche (HTTP/JSON, JPEG-Feeds)
```

### 3.1 Arbeitsteilung Pi ↔ Akida

Der Grundsatz, der sich im Projekt bewährt hat: **Jede Aufgabe läuft dort, wo sie im Verbund am wenigsten Energie kostet.** Der Pi macht Vordergrund/Hintergrund, Konturen, Geometrie, Tracking und Darstellung. Die Akida-Karten machen das, was ihnen liegt: Wiedererkennen gelernter Muster in Millisekunden.

### 3.2 Der Silhouetten-Abgleich (Chip-Lernen)

Das produktive Erkennungsverfahren heute. Jedes freigestellte Teil wird als binäre Silhouette (48 × 48 px, zwei Kanäle) einer Akida-`FullyConnected`-Schicht mit **On-Chip-Lernen** (`AkidaUnsupervised`) vorgelegt. Lernen heißt hier: Prototypen speichern, kein Gradientenabstieg. Gemessen auf dem AKD1500: rund **2 ms je Lernbeispiel**; ein komplettes Chip-Lernen mit 79 Beispielen aus 3 Objekten dauert unter einer Sekunde.

**Kartenverbund:** Karten 0–2 lernen denselben Bestand, aber verschiedene Anteile der Ansichten (Karte *i* bekommt jede dritte Aufnahme, versetzt). Zusammen halten sie dreimal so viele Schablonen je Objekt. Erkannt wird mit der besten Übereinstimmung über alle Karten. Der Lernstand wird als `.fbz` je Karte gesichert und beim Start zurückgespielt.

**Konfidenz** wird als Anteil des wiedergefundenen Musters (Potential / `num_weights`) ausgegeben, nicht als Softmax-Anteil — ein frei liegendes, sauberes Teil erreicht damit über 90 %.

### 3.3 VORSA-M3 (der Detektor)

Der M3-Kopf gibt pro Rasterfeld **drei gleichwertige Objektausgänge** aus (Slot: Objektheit, Mittelpunkt, Größe, Winkel als sin 2θ/cos 2θ, Sichtbarkeit, Klasse) plus drei feldweite Werte (lokale Anzahl, Überlappungs- und Überfüllungswahrscheinlichkeit). Ankerfrei; Mittelpunkte dürfen über die Feldgrenze reichen; die Zuordnung Vorhersage ↔ Zielobjekt wird beim Training reihenfolgeunabhängig über alle Permutationen gesucht (M! ≤ 24). Die Nachverarbeitung schützt Treffer aus demselben Feld voreinander (slot-bewusste Soft-NMS).

**Kernziel-Prüfung (gemessen 26.08.2026, AKD1500, `hw_only=True`):** Alle Varianten V2–V6 bestehen mit einer Hardwaresequenz und einem Durchgang; V6 (256 px Eingang, 32 × 32 Raster, 8-px-Zellen) braucht 18 von 32 NPs. Die beiden Gegenproben (Kopfeingang > 256 Kanäle, Eingang > 256 px) scheitern wie erwartet — daran erkennt man, dass die Prüfung selbst funktioniert. Hardwaregrenzen aus den Fehlermeldungen des Mappings: Eingangskante ≤ 256 px, Eingangsschicht ≤ 64 Filter, Kopfeingang ≤ 256 Kanäle.

Das Training läuft in TensorFlow/Keras, wird mit `cnn2snn` quantisiert und zur `.fbz` gewandelt. Im Betrieb liefert der Detektor auf Karte 3 Kandidaten (Kästen, Winkel, Verdeckungsgrad), die der Verbund benennt („Finden und Bestätigen").

### 3.4 Segmentierung — das eigentliche Schlachtfeld

Der größte Teil der Praxisprobleme lag nicht im Netz, sondern davor: *Was ist Teil, was ist Band?* Der heutige Stand, jeweils mit Prüfstand im Repo:

- **Farbmaske mit örtlichem Bandmodell** (`farbmaske_lokal`): Das Band wird je Pixel als glatte Fläche 4. Ordnung im Lab-Farbraum modelliert, robust über fünf Runden gefittet (Teile fallen als Ausreißer heraus). Grund: Die Pi-Kamera hat eine deutliche Randabdunklung; mit *einer* Bandfarbe lag die Schwelle bei ~31 und eine schwarze Karte auf dunkelgrünem Band blieb Hintergrund — nur ihre weißen Etiketten wurden „erkannt". Prüfstand: Karte 98 % statt 7 % erfasst (`tools/test_farbmaske.py`).
- **Kanten-Silhouette:** Alles, was von geschlossenen Farbkanten umschlossen ist und vom Bildrand nicht erreichbar, ist Teil — egal, was innen liegt.
- **Leerbild mit Rauschkarte:** „Leerbild merken" nimmt 16 Bilder über ~2 s auf; Median = leeres Band, je Pixel die größte gesehene Abweichung = Rauschkarte. Die Differenzschwelle gilt **je Pixel**. Damit sind flackernde Blendflecken und — bei laufendem Band während der Aufnahme — auch die Bandstruktur abgedeckt.
- **Glanzfilter:** Kleine gesättigte Flecken samt Lichthof (1,8 × Fleckradius) werden nie zu Teilen; große weiße Teile bleiben. Was im Leerbild glänzt, ist immer Band (`tools/test_glanz.py`).
- **Loch-Signatur:** Beim Anlernen wird gemessen, welche Klassen ein umschlossenes Loch haben (Karabiner ja, SD-Karte nein). Ein Klumpen, der ein Loch umschließt, aber als „SD-Karte" benannt wird, kann physikalisch nicht stimmen und wird am Loch zerlegt. Das hat die Szene „Karabiner um SD-Karte" gelöst.
- **Weichkanten-Wächter** gegen Phantomteile aus Schatten, **Leerwächter** gegen leere Negativ-Fotos, **Korrektur-Lernen** (richtigen Rahmen ziehen → Lernbeispiel).

### 3.5 Linienbetrieb

Zustandsmaschine in `vorsa/linie.py`, je Kamerabild getaktet. Zwei Zonen (Anlieferung, Abholung), je Zone frei wählbare Kamera, optional **„Blick 2"** (zweite Kamera auf die Anlieferzone; zwei Winkel, ein fusioniertes Urteil). Zwei Takte:

- **Fluss** (Standard seit 1.9.33): Band läuft von sich aus; ein Teil in der Anlieferung hält es kurz zum Prüfen (stabiles Urteil oder nach 4 s „unbekannt"), dann weiter; jedes weitere Teil hält erneut; in der Abholung hält es für den Arm. Dasselbe Teil wird beim Wegfahren nicht doppelt geprüft. Prüfstand: `tools/test_linie_fluss.py`.
- **Einzel** (alter Ablauf): Band startet erst, wenn die Anlieferung ein benanntes Teil zeigt.

Sicherheit vor Tempo: Ein unbekanntes Teil in der Abholung stoppt das Band und ruft *nicht* den Arm. Ohne funktionierende Erkennung fährt kein Band.

### 3.6 Professionelle Prüf-Funktionen (Stufen 1–5)

Nach einer Recherche, was industrielle Inspektionssoftware können muss, wurden eingebaut: Prüf-Urteil je Teil (gut / unbekannt / Ausschuss) mit Statistik und CSV-Export; Alarmbuch nach ISA-101 (flankengesteuert, quittierbar); Bedien- vs. Expertenansicht; Rezepte je Teilevariante; Konfidenzschwelle mit Unbekannt-Quote und Nachlern-Auslöser; Archiv der Nicht-gut-Fälle als Nachlernmaterial. Noch offen: Stufe 6 (PIN/Rollen, Audit-Trail).

### 3.7 „Warum?" — Erklärbarkeit ohne zweites Modell

Akida lernt Prototypen. Nach dem Lernen wird jedes Lernfoto einmal vorgelegt und dem Neuron zugeordnet, das es am stärksten trifft. Beim Urteil zeigt die Oberfläche das Live-Teil neben genau dem gelernten Foto, das den Ausschlag gab („Neuron 3 · Karte 2"). Das ist mit klassischen CNN-Klassifikatoren so nicht möglich und einer der Gründe, warum sich der Akida-Weg für kleine Anlagen lohnt.

### 3.8 Karten-Wächter

Seit 1.9.36 hat jede Karte einen Live-Stand (aktuelle Aufgabe, letzte Rechenzeit, Aufrufe/s). Wirft eine Karte beim Abgleich einen Fehler, wird sie aus dem Verbund genommen, die Linie läuft mit den übrigen weiter, ein Alarm geht ins Meldungsbuch, nach 60 s folgt ein Wiederaufnahmeversuch. Ein Knopf „Karte zurücksetzen (PCIe)" führt Remove/Rescan aus und spielt den Lernstand wieder auf.

---

## 4. Was wir gelernt haben (die teuren Lektionen)

1. **Zwei numpy-Welten.** Der Kamerastack (`picamera2`/`simplejpeg`) ist ein Systembinary gegen numpy 1.x; der Akida-Trainingsstack (`cnn2snn` 2.19, opencv-python 5) verlangt numpy ≥ 2. Beides in einem venv macht wahlweise Kamera oder Training kaputt. Lösung: Server in `~/akida-env` (numpy 1.26.4), Training als Unterprozess in `~/m3-train-env` (numpy 2.1.3).
2. **Erst prüfen, dann trainieren.** `check_single_pass.py` prüft das Kernziel mit Zufallsgewichten, *bevor* eine Minute Training investiert wird. Gegenproben, die scheitern *müssen*, gehören dazu — sonst ist ein PASS nichts wert.
3. **Übertragung verifizieren.** Drei Prüfläufe waren wertlos, weil der Code nie auf dem Pi angekommen war. Seitdem zeigen `sync.ps1`/`watch.ps1` die Versionsmarke lokal und auf dem Pi, und der Build-String steht in der Fußzeile der Oberfläche.
4. **Das System muss erklären, was es denkt.** Jeder Rahmen trägt ein Herkunftskürzel, die Ablaufzeile nennt bei jedem Verwerfen die Zahlen. Der Fehler „Hintergrund gewinnt mit 66 % gegen Karabiner 43 %" war so in Minuten gefunden: fünf Fotos leeren Bands in der Negativklasse.
5. **Leere Negativ-Fotos vergiften die Klasse.** Der Leerwächter lernt sie nicht mehr; der Vergiftungsschutz beim Lernfoto speichert keinen Ausschnitt ohne freistellbares Teil.
6. **Vignette schlägt Schwelle.** Eine globale Hintergrundfarbe scheitert an der Randabdunklung realer Objektive; das Bandmodell muss örtlich sein.
7. **Ein Leerbild ist nichts, viele sind alles.** Ein Einzelbild kennt das Flackern nicht; erst Median + Rauschkarte machen die Differenz belastbar.
8. **Winkel wandern mit.** Der Selbsttest der Augmentierung fand einen Vorzeichenfehler, der bei 90°/180°/270° unsichtbar war und erst bei 45° auftrat — im Training wäre er dem Modell zugeschrieben worden.
9. **Händigkeit.** Teile mit linker/rechter Ausführung dürfen nicht gespiegelt werden — die Anlage sperrt das je Klasse mit Begründung statt still.
10. **SD-Karten-Images ziehen, nicht nur tar.** Eine defekte SD-Karte hat die VideoCore-Firmware-Mailbox blockiert und die Kamera „getötet"; der Neuaufbau ist dokumentiert (`WIEDERAUFBAU_PI.md`). Nach jedem Boot-/Firmware-Eingriff sofort neu starten und prüfen.
11. **Der akida-pcie-Treiber kennt Kernel 6.12 nicht.** Zwei Patches am DKMS-Paket (`setup_akida_treiber.sh`) machen ihn reproduzierbar baubar.
12. **Eine Datei, ein Bearbeiter.** Zwei KI-Assistenten, die dieselbe `index.html` beschreiben, löschen sich gegenseitig die Arbeit; seitdem liefert einer Vorgaben, einer baut, und Einbauten liegen als wiederholbare Patch-Skripte vor.
13. **Blendflecken löst man an der Quelle.** Polfilter oder schräges Licht nehmen mehr weg, als jede Maske kann; die Software maskiert nur.

---

## 5. Alpha-Installation auf dem Raspberry Pi 5

Voraussetzungen: Raspberry Pi 5, Raspberry Pi OS **Bookworm 64-bit** (nicht Trixie — Akida-SDK), mindestens eine Pi Camera Module 3, eine oder mehrere AKD1500-PCIe-Karten, Netzwerk. Der Projektordner heißt `~/vorsa-m3` (auf dem Entwicklungs-PC `C:\vorsa-m3`).

### 5.1 System

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y git python3-venv python3-pip python3-picamera2 python3-opencv dkms
sudo reboot
```

Kameratest vor allem anderen:

```bash
vcgencmd version
python3 -c "from picamera2 import Picamera2; print(Picamera2.global_camera_info())"
```

Die Liste muss `imx708` zeigen. Wenn `vcgencmd` scheitert, ist die SD-Karte oder der Pi defekt — nicht die Software.

### 5.2 Akida-PCIe-Treiber (Kernel 6.12)

```bash
bash ~/vorsa-m3/setup_akida_treiber.sh
```

Das Skript klont `Brainchip-Inc/akida_dw_edma`, entfernt die Kernelschranke in `dkms.conf`, ersetzt den Makefile-Abbruch für Kernel > 6.9 durch den 6.9-Zweig, installiert per DKMS und trägt das Modul in `/etc/modules-load.d/` ein. Prüfung:

```bash
lspci | grep -i -c brainchip     # Zahl der Karten
lsmod | grep akida
```

### 5.3 Server-Umgebung (Kamera + Inferenz, **kein** TensorFlow)

```bash
python3 -m venv ~/akida-env --system-site-packages
source ~/akida-env/bin/activate
pip install --upgrade pip
pip install akida==2.19.3
pip install "numpy<2" opencv-python pyserial
python3 -c "import akida,cv2,numpy; from picamera2 import Picamera2; print(akida.devices(), numpy.__version__)"
```

Erwartung: die Karten werden gelistet, numpy ist 1.26.x. **Nie** `tensorflow` oder `cnn2snn` in dieses venv installieren.

### 5.4 Trainings-Umgebung (nur für das M3-Training)

```bash
bash ~/vorsa-m3/setup_m3_train.sh
~/m3-train-env/bin/python -c "import numpy,cv2,tensorflow,cnn2snn,akida; print('train-env ok', numpy.__version__)"
```

Legt `~/m3-train-env` an mit numpy 2.1.3, tensorflow 2.19.0, tf_keras 2.19.0, cnn2snn 2.19.3, akida 2.19.3, opencv-python-headless. Der Server findet die Umgebung automatisch (`~/m3-train-env/bin/python` oder `VORSA_M3_PY`).

### 5.5 Projekt übertragen

Vom Windows-PC (PowerShell), einmalig SSH-Schlüssel, dann:

```powershell
cd C:\vorsa-m3
.\sync.ps1          # überträgt vorsa/ und tools/ und zeigt die Versionsmarke beidseitig
```

Erstinstallation zusätzlich (Wurzeldateien werden von `sync.ps1` nicht übertragen):

```powershell
scp C:\vorsa-m3\start.sh C:\vorsa-m3\vorsa.service C:\vorsa-m3\setup_m3_train.sh C:\vorsa-m3\setup_akida_treiber.sh <user>@<PI-IP>:~/vorsa-m3/
```

### 5.6 Dienst einrichten

```bash
chmod +x ~/vorsa-m3/start.sh
sudo cp ~/vorsa-m3/vorsa.service /etc/systemd/system/vorsa.service
sudo systemctl daemon-reload
sudo systemctl enable --now vorsa
sudo systemctl status vorsa
journalctl -u vorsa -f
```

`start.sh` aktiviert `~/akida-env` und setzt `VORSA_BAND=relais` (12-V-Relais an GPIO 18) und `VORSA_ARM=uno` (Arduino-Arm an `/dev/ttyACM0`). Ohne Band/Arm beide Zeilen auskommentieren — das Band läuft dann in Simulation. Benutzer und Pfad in `vorsa.service` anpassen, falls nicht `<user>`/`/home/<user>/vorsa-m3`.

Optional, für den PCIe-Reset-Knopf ohne Passwort (`sudo visudo`):

```
<user> ALL=(root) NOPASSWD: /usr/bin/tee /sys/bus/pci/devices/*/remove, /usr/bin/tee /sys/bus/pci/rescan
```

### 5.7 Oberfläche öffnen

`http://<PI-IP>:8080` im Browser. Nach jedem Code-Update: `sudo systemctl restart vorsa`, Browser mit Strg+Umschalt+R laden, Build-String in der Fußzeile prüfen (`1.9.37-lernrahmen`).

Ohne jede Hardware zum Ausprobieren (auch auf dem PC):

```bash
python3 tools/run_web.py --synthetisch --port 8080
```

---

## 6. Testen

### 6.1 Prüfstände ohne Hardware (laufen auf jedem Rechner mit numpy/opencv)

| Befehl | Prüft | Erwartung |
|---|---|---|
| `python3 tools/test_m3_head.py` | M3-Ausgabelogik, Soft-NMS mit Feldschutz | 8 Treffer statt 4, alle `[OK]` |
| `python3 tools/run_selftest.py --use-background --out selftest_out` | Pi-Referenzstrecke auf synthetischen Szenen | `GESAMT: OK`, Mittelpunktfehler median ≤ 1 mm |
| `python3 tools/test_farbmaske.py` | Bandmodell gegen Vignetten (Parabel, cos⁴, flach) | `FEHLER: 0` |
| `python3 tools/test_glanz.py` | Blendflecken, Leerbild mit Rauschkarte | `FEHLER: 0` |
| `python3 tools/test_linie_fluss.py` | Fluss-/Einzel-Takt der Linie | `FLUSS_OK` |
| `python3 tools/test_karten_waechter.py` | Ausfall, Sperre, Wiederaufnahme einer Karte | `WAECHTER_OK` |
| `python3 -c "from vorsa.augment import pruefe_winkelmitfuehrung; print(pruefe_winkelmitfuehrung())"` | Winkel bei Drehen/Spiegeln | `[]` |

### 6.2 Mit Akida-Hardware

```bash
source ~/akida-env/bin/activate && cd ~/vorsa-m3
python3 tools/check_single_pass.py           # Kernziel aller Varianten, PASS/FAIL mit Grund
python3 tools/check_training_env.py          # welcher Trainingsweg ist offen
python3 tools/train_smoke.py --steps 60 --batch 4   # Durchstich: trainieren, quantisieren, .fbz, mappen
```

Der Durchstich beweist nur, dass die Kette geschlossen ist — ein fallender Verlust auf 60 Schritten sagt nichts über Erkennungsleistung.

### 6.3 Oberflächen-Rauchtest (PC, ohne Browser)

Ein jsdom-Rauchtest gegen den synthetischen Server prüft ~45 Punkte (Navigation, Lernzonen, Zoom, Zustand-Reiter, Fokus-Entkopplung, Warum-Block). Er liegt bei den Entwicklungsdateien (`smoke_ui.js`, `smoke22.js`) und braucht Node 22 plus `npm install jsdom@24`.

### 6.4 Erster Durchlauf an der Anlage

1. **Kamera & Zonen:** Kamera pro Zone wählen, Anlieferzone so ziehen, dass die Bandkante draußen bleibt. Kamera-Leiste (Knopf „Kamera"): Fokus einmal scharf, Belichtung festhalten.
2. **Leerbild:** Bei leerem, **laufendem** Band je Kamera „Leerbild merken".
3. **Objekte & Lernen:** Objekt anlegen, 5–10 Fotos je Lage (Serie: Teil langsam drehen), eine Negativklasse mit echten Störteilen (kein leeres Band). „Chip-Lernen" — Sekunden.
4. **Erkennung:** Teil auflegen, Urteil und „Warum erkannt?" prüfen.
5. **Linienbetrieb:** Takt Fluss, „Linie aktivieren", drei Teile nacheinander auflegen; Prüfbuch und Meldungen ansehen.

---

## 7. Bedienoberfläche (UI 2.2)

Nach ISA-101 (High-Performance HMI): ruhige Fläche, Farbe nur für Zustände. Seitenleiste mit sieben Einträgen in drei Gruppen — *Betrieb* (Erkennung, Linienbetrieb, Rezepte), *Einrichten* (Kamera & Zonen, Objekte & Lernen; nur in der Expertenansicht), *System* (Zustand, Meldungen). Kamera-Einstellungen sitzen als bündige Leiste direkt am Bild — dieselbe Leiste für Hauptbild und Zonen-Kacheln. Anzeige-Optionen im Auge-Menü. „Zustand" bündelt Hardware (Karten mit Live-Aufgabe), Diagnose (Messreihe Pi gegen Akida, Kernziel) und Wartung. Das frühere Einstellungsfenster mit sieben Reitern ist aufgelöst: jede Einstellung sitzt dort, wo man ihre Wirkung sieht.

Die Oberfläche ist eine Datei (`vorsa/web/static/index.html`), Vanilla JS, keine Build-Kette, und spricht rund 60 JSON-Endpunkte unter `/api/…` an.

---

## 8. Betrieb und Störungen — Spickzettel

| Symptom | Ursache | Griff |
|---|---|---|
| Nur schwarze Bilder, `Camera frontend has timed out` | CSI-Kabel locker | Kabel prüfen, Pi neu starten |
| `akida.devices(): Error reading … errno(110)` oder `DMA wait completion timed out` in `dmesg` | eine Karte hängt | `Zustand → Hardware → Karte zurücksetzen`, oder manuell: `sudo systemctl stop vorsa; echo 1 \| sudo tee /sys/bus/pci/devices/<adr>/remove; sleep 2; echo 1 \| sudo tee /sys/bus/pci/rescan; sudo systemctl start vorsa`; wenn wiederholt dieselbe Karte: Karte/Steckplatz tauschen |
| Kamera tot nach numpy-Update (`simplejpeg: numpy.dtype size changed`) | numpy ≥ 2 im Server-venv | `pip install "numpy<2"` in `~/akida-env` |
| Etiketten statt Karte erkannt | Vignette/Hintergrundmodell | ab 1.9.33 örtliches Bandmodell; zusätzlich Leerbild merken |
| Blendflecken werden Teile | Einzelbild-Leerbild | ab 1.9.35 Leerbild neu merken (16 Bilder, Rauschkarte); optisch: Polfilter |
| „7 von 25 Fotos der Negativklasse zeigen nur leeren Hintergrund" | leere Negativ-Fotos | Fotos löschen; Negativklasse nur für echte Störteile |
| Fußzeile zeigt alten Build | Dienst nicht neu gestartet / Browser-Cache | `sudo systemctl restart vorsa`, Strg+Umschalt+R |

Neustart aller Komponenten: `sudo systemctl restart vorsa` (Kamera, Akida, Band, Arm in einem Prozess).

---

## 9. Messwerte, die belastbar sind

- Chip-Lernen: ~2 ms je Beispiel (AKD1500, gemessen).
- Kernziel: V6 in einer Sequenz, einem Durchgang, 18/32 NPs (gemessen, Firmware BC.A1.003.009).
- Gesamtlatenz Kamera → Urteil bei der Abnahme der Berührungsszene (Stand 1.2.6): 22,7 ms je Bild; die reine Chip-Rechenzeit je Karte liegt im Millisekundenbereich und ist seit 1.9.36 je Karte live ablesbar (Zustand → Hardware).
- Referenzstrecke auf synthetischen Szenen: Mittelpunktfehler median 0,2 mm, Winkel 0,5°, ~15 ms je Bild (kein Netz, perfekte Kalibrierung — am Band schlechter).
- Bandmodell (Prüfstand): Karte auf Vignette-Band 98 % statt 7 % erfasst; leeres Band 0,0–0,7 % Fehlpixel.
- Leistungsaufnahme der Karten: der AKD1500 trägt in MetaTF 2.19.3 **keinen** auslesbaren Leistungssensor (nur AKD1000). Community-Messungen nennen unter 1 W je Karte — das ist ein Fremdwert, keine eigene Messung.

---

## 10. Offene Punkte (ehrlich)

- Der M3-Detektor ist trainierbar und läuft auf Karte 3; belastbare Erkennungsraten an echten Bildern (Abnahmekriterien A1–A15 der SPEC) stehen aus.
- Stufe 6 (PIN/Rollen, Audit-Trail) fehlt.
- Fluss-Takt: die Zeiten 0,25 s (Anhalten) und 4 s (Prüf-Timeout) sind am Prüfstand, nicht am Band eingefahren.
- Reihenfolge der Akida-Karten im Treiber vs. PCIe-Adressen wird für den Reset-Knopf als gleich angenommen; bei einem Tausch der Karten prüfen.
- Energie je korrekt erkanntem Objekt (Pi gegen Akida) ist als Messreihe vorbereitet, aber noch nicht als Zahl veröffentlicht.
- Screenshots der Oberfläche in 1366/1440/1920 px sind nicht automatisiert; die visuelle Abnahme ist manuell.

## 11. Roadmap

Leuchtturm 2 „selbstlernende Anlage": Unbekannt-Fälle sammeln, Vorschlag neuer Klassen, Nachlernen mit einem Klick in Sekunden. Danach: One-Class-Betrieb, Weight-Bank-Paging, Lernstand-Transfer zwischen Anlagen, OPC UA/MQTT-Anbindung, Maßprüfung.

---

## Anhang A — Repository-Aufbau

```
vorsa/            Kern: config, model_m3, postprocess, assignment, detection, akida_pool,
                  pipeline, tracking, overlay, segmentation, fitting, calibration,
                  edge_learn (Silhouetten-Abgleich, Verbund, Warum?, Karten-Wächter),
                  linie (Zustandsmaschine), detektor, train_job, m3_extern, dataset_build,
                  augment, synth_objects, arm_uno
vorsa/web/        server.py (HTTP/JSON, Prüfbuch, Alarmbuch, Rezepte, Leerbild, Lernzonen)
                  static/index.html (Oberfläche)
tools/            run_web, run_selftest, check_single_pass, check_training_env, train_smoke,
                  test_* (Prüfstände), akida_report, calibrate_board
setup_akida_treiber.sh, setup_m3_train.sh, start.sh, vorsa.service, sync.ps1, watch.ps1
SPEC.md (Spezifikation + Abnahmekriterien), FAHRPLAN.md (Chronik), KARTENPLAN.md,
PROFI_AUSBAU.md (Industrie-Anforderungen), WIEDERAUFBAU_PI.md, BEDIENKONZEPT.md
```

## Anhang B — Versionschronik (Auszug)

| Build | Inhalt |
|---|---|
| 1.3.x–1.4.x | Überlappung: Gruppentreue, Loch-Signatur, Leerwächter, Loch-Veto, Lose-Taufe |
| 1.5–1.7 | Linienmodus, Zonen als eigene Fenster, Zweitkamera je Zone, reales Band per Relais |
| 1.8 | Arduino-Arm integriert |
| 1.9.0–1.9.7 | Zweite Pi-Kamera, ISA-101-Look, Kamera-Leiste je Feed |
| 1.9.8–1.9.16 | Stufen 1–5: Prüfbuch, Alarme, Bedienansicht, Rezepte, Schwellen |
| 1.9.17–1.9.26 | Belichtung/Fokus je Kamera, Farb-/Kantenmaske, Leerbild, Korrektur-Lernen |
| 1.9.27–1.9.31 | Blick 2, Lernzonen A/B, Warum?, Flacker-Stabilisierung |
| 1.9.32–1.9.34 | UI 2.1/2.2 (Navigation, Zustand, eine Kamera-Leiste) |
| 1.9.33 | Örtliches Bandmodell, Fluss-Takt |
| 1.9.35 | Leerbild mit Rauschkarte, Glanzfilter |
| 1.9.36 | Karten-Wächter, Live-Aufgabe je Karte, PCIe-Reset |
| 1.9.37 | Lernzonen nur bei offener Lernzonen-Ansicht |
