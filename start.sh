#!/bin/bash
# ============================================================
# SE Inspect / VORSA INSPECT - Komplettstart mit EINEM Befehl:   ./start.sh
# Standard: Profil stationaer (Pruefzelle ohne Band und Arm).
# Maschinenspezifisches gehoert in start.local.sh (nicht versioniert):
#   export VORSA_PROFIL=linie      # Band + Arm + Zonen
#   export VORSA_BAND=relais       # 12-V-Relais an GPIO 18 (sim | echt | relais)
#   export VORSA_ARM=uno           # Arduino-Arm an /dev/ttyACM0
#   export VORSA_ARM_PORT=/dev/ttyACM1
# Beenden mit Strg+C.
# ============================================================
cd "$(dirname "$0")"
if [ -f "$HOME/akida-env/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$HOME/akida-env/bin/activate"
fi
export VORSA_PROFIL="${VORSA_PROFIL:-stationaer}"
if [ -f ./start.local.sh ]; then
  # shellcheck disable=SC1091
  source ./start.local.sh
fi
exec python3 tools/run_web.py "$@"
