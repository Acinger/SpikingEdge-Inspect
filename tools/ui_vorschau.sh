#!/bin/bash
# Erzeugt statische UI-Vorschauen (Entwicklung): bash tools/ui_vorschau.sh <ausgabeordner> [praefix] [sprache]
# Braucht jsdom unter /tmp/jt/node_modules und Demo-Daten in /tmp/vd (2 Objekte mit Fotos).
O=${1:-/tmp/ui}; PRE=${2:-vor}; SP=${3:-de}; mkdir -p "$O"; cd "$(dirname "$0")/.."
if [ ! -f /tmp/vd/zustand.json ] && [ ! -d /tmp/vd ]; then mkdir -p /tmp/vd; fi
(VORSA_SYNTH_HALTEN_S=30 timeout 150 python3 tools/run_web.py --port 8799 --synthetisch --daten /tmp/vd > /tmp/vsrv.log 2>&1 &)
sleep 6
for m in betreiben anlernen einrichten; do
  NODE_PATH=/tmp/jt/node_modules timeout 50 node tools/ui_vorschau.js http://127.0.0.1:8799 "$O/${PRE}_$m.html" $m $SP 2>&1 | grep VORSCHAU
done
pkill -f "^python3 tools/run_web.py --port 8799" || true
