# VORSA INSPECT — Pi 5 neu aufsetzen (frische SD-Karte)

Grund: Nach dem ersten Reboot seit Wochen antwortet die VideoCore-
Firmware-Mailbox nicht mehr (`vcgencmd: ioctl_set_msg failed`,
`raspberrypi-clk … failed -22`) — die Pi-Kamera ist damit tot. Alle
Software-Reparaturen (EEPROM, Kernel-Reinstall, rpi-update, cma raus)
haben nichts geaendert -> mit hoher Wahrscheinlichkeit ein
beschaedigter Bereich der bisherigen SD-Karte. Test + Reparatur:
frisches OS auf NEUER Karte. Alte Karte bleibt unangetastet als
Fallback und Datenquelle.

Akida/Band/Arm sind gesund. Der Projektcode liegt vollstaendig auf
dem PC unter C:\vorsa-m3 und als tar (~/sicherungen bzw. PC).

============================================================
PHASE 1 — FLASHEN + KAMERA-TEST (der entscheidende Beweis)
============================================================
Am Windows-PC, Raspberry Pi Imager:
  Geraet:  Raspberry Pi 5
  OS:      Raspberry Pi OS (64-bit), Version BOOKWORM (wie bisher -
           Debian 12 / Python 3.11; NICHT Trixie, wegen Akida-SDK)
  Medium:  die NEUE SD-Karte
  Einstellungen bearbeiten:
    - Hostname: pi
    - Benutzer: <user> + bekanntes Passwort
    - WLAN: SSID + Passwort, Land DE
    - Dienste: SSH aktivieren (Passwortanmeldung)
  Schreiben, auswerfen.

Am Pi 5:
  - Alte Karte raus (beschriften, aufheben!), neue rein, Strom an.
  - Per SSH verbinden, DANN nur:

      vcgencmd version
      python3 -c "from picamera2 import Picamera2; print(Picamera2.global_camera_info())"

  GRUEN: vcgencmd zeigt Version UND Liste zeigt 'imx708'
         -> Pi ist gesund, es war die Karte. Weiter mit Phase 2.
  ROT:   weiterhin tot -> Pi-5-Hardware. Ersatz-Pi noetig
         (dann Phase 2 spaeter auf dem Ersatzgeraet).

============================================================
PHASE 2 — WIEDERAUFBAU (erst nach GRUENem Kamera-Test)
============================================================
Reihenfolge wichtig: erst System, dann Akida, dann Projekt.

1) System aktuell machen, Werkzeug:
     sudo apt update && sudo apt full-upgrade -y
     sudo apt install -y git python3-venv python3-pip python3-picamera2 \
          python3-opencv dkms
     sudo reboot

2) Akida-SDK + PCIe-Treiber (die vier AKD1500). Der genaue Weg
   haengt von BrainChips Paketen ab - so, wie es beim ersten Mal
   eingerichtet wurde:
     - PCIe-Treiber (akida-pcie, DKMS) installieren -> nach Reboot
       muessen `lspci | grep -i brainchip` vier Geraete zeigen und
       `lsmod | grep akida` das Modul.
     - ACHTUNG numpy (2026-09-07 gelernt): der Server-venv MUSS numpy<2
       haben, sonst ist die Kamera tot (picamera2/simplejpeg ist ein
       System-Binary gegen numpy 1.x). cnn2snn/TensorFlow gehoeren NICHT
       in diesen venv - sie ziehen numpy>=2 nach. Das M3-Training laeuft
       in einem ZWEITEN venv (siehe unten).
     - Server-venv (Akida-Inferenz, Kamera, KEIN TensorFlow):
         python3 -m venv ~/akida-env --system-site-packages
         source ~/akida-env/bin/activate
         pip install --upgrade pip
         pip install akida==2.19.3
         pip install "numpy<2" opencv-python pyserial
     - Test: python3 -c "import akida,cv2,numpy; from picamera2 import
       Picamera2; print(akida.devices(), numpy.__version__)"
       muss die vier Karten listen und numpy 1.26.x zeigen.
     - Train-venv (nur fuers M3-Training, numpy 2) SEPARAT anlegen:
         bash ~/vorsa-m3/setup_m3_train.sh
       (baut ~/m3-train-env mit numpy 2.1.3 + tensorflow 2.19.0 +
       tf_keras 2.19.0 + cnn2snn 2.19.3 + akida 2.19.3 + opencv-headless.)
   MERKE: Falls BrainChip ein eigenes Repo/DKMS-Paket fuer den
   akida-pcie-Treiber hat, dessen Installationsschritte hier
   nachtragen, sobald wieder eingerichtet.

3) Projekt zurueckspielen (vom PC, PowerShell):
     scp -r C:\vorsa-m3\vorsa      <user>@<PI-IP>:~/vorsa-m3/
     scp -r C:\vorsa-m3\tools      <user>@<PI-IP>:~/vorsa-m3/
     scp C:\vorsa-m3\start.sh      <user>@<PI-IP>:~/vorsa-m3/
     scp C:\vorsa-m3\setup_m3_train.sh <user>@<PI-IP>:~/vorsa-m3/
     scp C:\vorsa-m3\vorsa_m3.fbz  <user>@<PI-IP>:~/vorsa-m3/   (falls vorhanden)
   ODER komplett aus dem tar:
     scp C:\vorsa-m3\sicherungen\vorsa-m3-20260906.tar.gz <user>@<PI-IP>:~/
     ssh: tar xzf ~/vorsa-m3-20260906.tar.gz -C ~

4) LERNSTAND + ZONEN + ARM-PUNKTE (vorsa_daten) von der ALTEN Karte
   holen (die Linux-Partition ist lesbar, nur Boot/Firmware war das
   Problem): alte Karte per USB-Kartenleser an den LAUFENDEN neuen
   Pi 5 stecken, mounten, vorsa_daten kopieren:
     lsblk                      # Partition der alten Karte finden (z.B. sda2)
     sudo mkdir -p /mnt/alt
     sudo mount /dev/sda2 /mnt/alt
     cp -r /mnt/alt/home/<user>/vorsa-m3/vorsa_daten ~/vorsa-m3/
     cp /mnt/alt/home/<user>/vorsa-m3/vorsa_m3.fbz ~/vorsa-m3/ 2>/dev/null
     sudo umount /mnt/alt
   (Das rettet das angelernte Gedaechtnis, die Zonen und die
   Arm-Punkte 1:1 - kein Neu-Anlernen noetig.)

5) Start wie gehabt:
     ~/vorsa-m3/start.sh
   Kontrolle: Kamerabild da, unten rechts BUILD 1.8.6, vier Karten,
   Zonen sitzen, Band + Arm reagieren.

============================================================
CMA (Speicher-Fahrplan Stufe A) — DIESMAL VORSICHTIG
============================================================
Der Verdacht, dass der Reboot mit cma=256M die Karte ans Licht
brachte, bleibt bestehen (Ursache war die Karte, nicht cma selbst).
Trotzdem: auf der frischen Karte cma NUR setzen, wenn wieder ein
Vollbackup + Image existiert, und danach SOFORT neu starten und
Kamera testen. Bei kleinstem Zweifel Finger weg - die 16 MB je Karte
reichen fuer VORSAs SRAM-Modelle voellig.

============================================================
LEHRE FUER KUENFTIG
============================================================
- Vom laufenden, funktionierenden System regelmaessig ein
  SD-KARTEN-IMAGE ziehen (Win32DiskImager / Raspberry Pi Imager
  "Read"), nicht nur ein Datei-tar. Dann ist "zurueck zu gestern"
  ein 10-Minuten-Restore statt eines Neuaufbaus.
- Nach JEDEM Boot-/cmdline-/Firmware-Eingriff sofort neu starten und
  pruefen - nicht Wochen spaeter, wenn niemand mehr weiss, was war.
