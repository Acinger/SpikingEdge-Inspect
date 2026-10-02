#!/usr/bin/env python3
"""Startet die SE Inspect Weboberflaeche (frueher VORSA-M3 / VORSA INSPECT).

    python3 tools/run_web.py                    # Kamera 0, Port 8080
    python3 tools/run_web.py --synthetisch      # ohne Kamera, zum Ausprobieren
    python3 tools/run_web.py --port 8000 --kamera 1

Danach im Browser oeffnen - vom Pi selbst, vom PC oder vom Handy im selben
Netz:

    http://<Pi-Adresse>:8080

Damit entfaellt das Bildschirmproblem: die Oberflaeche braucht keine Anzeige
auf dem Pi, sie liefert eine.
"""
from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# CPU-Ersatz fuers Chip-Lernen beim synthetischen Start (A8): muss VOR dem
# Import des Servers feststehen, weil edge_learn beim Import entscheidet.
import os as _os
if "--synthetisch" in sys.argv and "VORSA_CPU_LERNEN" not in _os.environ:
    try:
        import akida  # noqa: F401  (echte Karte vorhanden? dann kein Ersatz)
    except Exception:
        _os.environ["VORSA_CPU_LERNEN"] = "1"
from vorsa.web.server import starte      # noqa: E402


def eigene_adresse() -> str:
    """Adresse im lokalen Netz - fuer die Ausgabe, damit man sie abtippen kann."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))       # baut keine Verbindung auf
        adresse = s.getsockname()[0]
        s.close()
        return adresse
    except Exception:
        return "localhost"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--kamera", type=int, default=0)
    ap.add_argument("--groesse", type=int, default=512,
                    help="Kantenlaenge der synthetischen Bilder")
    ap.add_argument("--synthetisch", action="store_true",
                    help="keine Kamera verwenden")
    ap.add_argument("--daten", default="vorsa_daten",
                    help="Ordner fuer Klassen und Prototypen")
    ap.add_argument("--ohne-erkennung", action="store_true",
                    help="nur Livebild, keine Bildverarbeitung")
    ap.add_argument("--ohne-lernen", action="store_true",
                    help="Akida-Lernteil nicht laden - zum Eingrenzen von Fehlern")
    ap.add_argument("--protokoll", action="store_true",
                    help="jede Anfrage mitschreiben - zeigt, was der Browser holt")
    ap.add_argument("--profil", choices=("stationaer", "linie"), default=None,
                    help="stationaer (Standard): Pruefzelle ohne Band/Arm/Zonen; "
                         "linie: Band, Arm und Zonen (wie VORSA_PROFIL)")
    ap.add_argument("--anzeige", type=int, default=960,
                    help="Kantenlaenge des Livebildes in Pixeln. Kleiner ist "
                         "schneller, groesser ist schaerfer - unter der Breite "
                         "des Browserfensters wird das Bild hochskaliert und "
                         "sieht dann unscharf aus.")
    args = ap.parse_args()
    if args.profil:
        import os
        os.environ["VORSA_PROFIL"] = args.profil

    print(f"\n  Im Browser oeffnen:  http://{eigene_adresse()}:{args.port}\n")

    starte(port=args.port, kamera=args.kamera, groesse=args.groesse,
           synthetisch=args.synthetisch, daten=args.daten,
           mit_erkennung=not args.ohne_erkennung,
           mit_lernen=not args.ohne_lernen,
           protokoll=args.protokoll, anzeige=args.anzeige)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
