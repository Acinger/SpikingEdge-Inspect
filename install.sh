#!/usr/bin/env bash
# ============================================================================
# SE Inspect — one-shot installer for Raspberry Pi 5 (Raspberry Pi OS Bookworm 64-bit)
#
#   bash install.sh            # full: packages, Akida driver, runtime env, service
#   bash install.sh --laptop   # no hardware: runtime env only, CPU stand-in for the chip
#   bash install.sh --no-service
#
# Follows guide chapters 04–07 (spikingedge.com/guide/). Every step prints what it
# checks and stops at the first failure with the chapter to read. Re-running is safe.
# Verified on: Pi 5, Bookworm 64-bit, kernel 6.12, akida 2.19.3, AKD1500 fw BC.A1.003.009.
# ============================================================================
set -euo pipefail
HIER="$(cd "$(dirname "$0")" && pwd)"
LAPTOP=0; SERVICE=1
for a in "$@"; do
  case "$a" in
    --laptop) LAPTOP=1; SERVICE=0 ;;
    --no-service) SERVICE=0 ;;
    *) echo "unbekannte Option: $a"; exit 2 ;;
  esac
done
schritt() { printf '\n\033[1;36m== %s ==\033[0m\n' "$1"; }
ok()      { printf '   \033[32mok\033[0m  %s\n' "$1"; }
stop()    { printf '   \033[31mSTOP\033[0m %s\n   -> %s\n' "$1" "$2"; exit 1; }

schritt "0. System"
if [ "$LAPTOP" = 0 ]; then
  grep -qi 'bookworm' /etc/os-release || stop "Nicht Bookworm: $(. /etc/os-release; echo "$PRETTY_NAME")" "Guide Kapitel 04: Raspberry Pi OS Bookworm 64-bit flashen (nicht Trixie)."
  [ "$(uname -m)" = "aarch64" ] || stop "Nicht 64-bit ($(uname -m))" "Guide Kapitel 04."
  ok "$(. /etc/os-release; echo "$PRETTY_NAME"), Kernel $(uname -r)"
  if command -v vcgencmd >/dev/null; then ok "Firmware: $(vcgencmd version | head -1)"; fi
fi
PY=$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')
ok "Python $PY"

if [ "$LAPTOP" = 0 ]; then
  schritt "1. Pakete"
  sudo apt-get update -qq
  sudo apt-get install -y -qq git python3-venv python3-pip python3-picamera2 python3-opencv dkms build-essential linux-headers-"$(uname -r)" >/dev/null
  ok "apt-Pakete installiert"
  if python3 -c "from picamera2 import Picamera2; i=Picamera2.global_camera_info(); print(i)" 2>/dev/null | grep -q imx; then
    ok "Kamera gefunden (imx)"
  else
    echo "   !   keine Pi-Kamera gefunden - Kabel/CSI pruefen (Guide Kapitel 04). Weiter ohne Kamera (synthetischer Modus geht)."
  fi

  schritt "2. Akida-PCIe-Treiber"
  if lsmod | grep -q akida && ls /dev/akd1500_* >/dev/null 2>&1; then
    ok "Treiber geladen: $(ls /dev/akd1500_* | wc -l) Karte(n)"
  else
    if lspci 2>/dev/null | grep -qi brainchip; then
      [ -f "$HIER/setup_akida_treiber.sh" ] || stop "setup_akida_treiber.sh fehlt" "Projektordner vollstaendig kopieren."
      bash "$HIER/setup_akida_treiber.sh"
      ls /dev/akd1500_* >/dev/null 2>&1 || stop "Nach dem Treiberbau kein /dev/akd1500_*" "Guide Kapitel 05 / Troubleshooting: dmesg | grep -i akida"
      ok "Treiber gebaut: $(ls /dev/akd1500_* | wc -l) Karte(n)"
    else
      echo "   !   keine BrainChip-Karte am PCIe-Bus (lspci) - Treiber uebersprungen. Ohne Karte laeuft nur der CPU-Ersatz."
    fi
  fi
fi

schritt "3. Laufzeitumgebung ~/akida-env"
if [ ! -d "$HOME/akida-env" ]; then
  if [ "$LAPTOP" = 0 ]; then python3 -m venv "$HOME/akida-env" --system-site-packages; else python3 -m venv "$HOME/akida-env"; fi
fi
# shellcheck disable=SC1091
source "$HOME/akida-env/bin/activate"
pip install -q --upgrade pip
if [ "$LAPTOP" = 1 ]; then
  # Laptop: numpy 2 ist in Ordnung (kein picamera2/simplejpeg). Auf dem Pi
  # kommt OpenCV aus apt und numpy MUSS < 2 bleiben (Kamera-Pfad).
  pip install -q numpy opencv-python-headless
else
  pip install -q "numpy<2"
fi
if [ "$LAPTOP" = 0 ] && (lspci 2>/dev/null | grep -qi brainchip); then
  pip install -q akida==2.19.3
  python3 -c "import akida; d=akida.devices(); print('   akida', akida.__version__, len(d), 'Geraet(e)'); assert d" || stop "akida.devices() leer" "Guide Kapitel 05: Karten, Treiber, dmesg."
  ok "MetaTF 2.19.3 sieht die Karte(n)"
else
  ok "ohne Karte: Chip-Lernen laeuft als CPU-Ersatz (VORSA_CPU_LERNEN=1 setzt run_web.py beim synthetischen Start selbst)"
fi
python3 -c "import numpy,cv2; print('   numpy', numpy.__version__, 'opencv', cv2.__version__)"
( cd "$HIER" && python3 -c "import vorsa, vorsa.segmentation, vorsa.hypothesen, vorsa.verteiler; print('   vorsa importierbar')" ) || stop "Projekt nicht importierbar" "Im Projektordner starten: bash ~/vorsa-m3/install.sh"

schritt "4. Selbsttest ohne Hardware"
( cd "$HIER" && python3 tools/test_mehrbild.py >/dev/null && python3 tools/test_hypothesen.py >/dev/null && python3 tools/test_verteiler.py >/dev/null ) \
  && ok "Benches Mehrbild / Hypothesen / Verteiler gruen" || stop "eine Bench ist rot" "tools/test_*.py einzeln ausfuehren und Ausgabe melden."

if [ "$SERVICE" = 1 ]; then
  schritt "5. Dienst"
  USER_NAME="$(id -un)"
  sed -e "s|^User=.*|User=$USER_NAME|" -e "s|/home/[a-z0-9_]*/vorsa-m3|$HIER|g" "$HIER/vorsa.service" > /tmp/vorsa.service
  sudo cp /tmp/vorsa.service /etc/systemd/system/vorsa.service
  chmod +x "$HIER/start.sh"
  sudo systemctl daemon-reload
  sudo systemctl enable --now vorsa
  sleep 6
  systemctl is-active --quiet vorsa && ok "Dienst laeuft: http://$(hostname -I | awk '{print $1}'):8080" || stop "Dienst nicht aktiv" "journalctl -u vorsa -n 50"
  echo "   Profil: $(grep -E '^export VORSA_PROFIL' "$HIER/start.sh" || echo 'stationaer (Standard)')"
  echo "   Band/Arm nur im Profil linie (start.sh)."
else
  schritt "5. Start von Hand"
  echo "   source ~/akida-env/bin/activate && cd $HIER && python3 tools/run_web.py --synthetisch --port 8080"
fi

schritt "fertig"
echo "   Weiter mit Guide Kapitel 08 (erste Inbetriebnahme): Objekt anlegen, Fotos, Chip-Lernen, PRUEFEN."
