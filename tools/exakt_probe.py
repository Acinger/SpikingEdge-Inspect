#!/usr/bin/env python3
"""Exaktheitsprobe: Chip gegen Software, bitgenau.

Kevins Kernwarnung (AKD1500-Speicherfahrplan, Stufe B): jenseits der
64-MiB-Reichweite des Gewichts-Basisregisters liefert der Chip
PLAUSIBLEN MUELL - Mapping ok, Inferenz "gesund", Zahlen falsch. Die
SDK-Waechter (hw_only, assert_on_silicon) sehen das konstruktionsbedingt
nicht. Der einzige verlaessliche Detektor ist der Zahlenvergleich.

Diese Probe schickt dieselben Zufallseingaben einmal durch das Modell
in SOFTWARE (nicht gemappt, CPU) und einmal durch das Modell AUF DER
KARTE und vergleicht die Ausgaben bitgenau. Gruen = weiterarbeiten,
Rot = sofort stoppen und letzte Aenderung zuruecknehmen.

Aufruf (auf dem Pi 5, Linie gestoppt):

    source ~/akida-env/bin/activate
    python3 tools/exakt_probe.py                     # vorsa_m3.fbz, letzte Karte
    python3 tools/exakt_probe.py --fbz pfad.fbz --karte 0 --n 32
"""
from __future__ import annotations

import argparse
import sys
import time

import numpy as np


def haupt() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--fbz", default="vorsa_m3.fbz",
                   help="Akida-Modelldatei (Standard: vorsa_m3.fbz)")
    p.add_argument("--karte", type=int, default=-1,
                   help="Karten-Nr. (Standard: letzte = Detektorkarte)")
    p.add_argument("--n", type=int, default=16,
                   help="Anzahl Zufallsbilder (Standard: 16)")
    p.add_argument("--saat", type=int, default=42,
                   help="Zufallssaat - fest, damit Laeufe vergleichbar sind")
    a = p.parse_args()

    try:
        import akida
    except ImportError:
        print("FEHLER: akida-Paket nicht gefunden - im akida-env starten"
              " (source ~/akida-env/bin/activate)")
        return 2

    try:
        modell = akida.Model(a.fbz)
    except Exception as exc:
        print(f"FEHLER: Modell '{a.fbz}' nicht ladbar: {exc}")
        return 2

    form = tuple(modell.input_shape)
    rng = np.random.default_rng(a.saat)
    eingaben = rng.integers(0, 256, size=(a.n,) + form, dtype=np.uint8)
    print(f"Modell {a.fbz}  Eingabe {form}  {a.n} Zufallsbilder "
          f"(Saat {a.saat})")

    # ---- 1) SOFTWARE-Referenz (nicht gemappt -> CPU) ----
    t0 = time.perf_counter()
    weich = modell.forward(eingaben)
    t_weich = (time.perf_counter() - t0) * 1000
    print(f"Software: {t_weich:8.1f} ms  Ausgabe {weich.shape} "
          f"{weich.dtype}")

    # ---- 2) HARDWARE ----
    geraete = akida.devices()
    if not geraete:
        print("FEHLER: keine Akida-Karte gefunden")
        return 2
    nr = a.karte if a.karte >= 0 else len(geraete) - 1
    if nr >= len(geraete):
        print(f"FEHLER: Karte {nr} gibt es nicht "
              f"({len(geraete)} vorhanden)")
        return 2
    print(f"Karte {nr}: {geraete[nr].desc}")
    try:
        modell.map(geraete[nr])
    except Exception as exc:
        print(f"FEHLER: Mapping auf Karte {nr} gescheitert: {exc}")
        return 2
    t0 = time.perf_counter()
    hart = modell.forward(eingaben)
    t_hart = (time.perf_counter() - t0) * 1000
    print(f"Hardware: {t_hart:8.1f} ms  Ausgabe {hart.shape} "
          f"{hart.dtype}")

    # ---- 3) Bitgenauer Vergleich ----
    if weich.shape != hart.shape:
        print(f"ROT: Ausgabeformen weichen ab "
              f"({weich.shape} vs {hart.shape})")
        return 1
    gleich = np.array_equal(weich, hart)
    if gleich:
        print(f"GRUEN: {a.n} Bilder BITGENAU identisch "
              f"(Software == Karte {nr}).")
        return 0
    diff = weich.astype(np.int64) - hart.astype(np.int64)
    schlecht = int(np.count_nonzero(diff))
    print("ROT: ABWEICHUNG! Chip liefert andere Zahlen als die "
          "Software-Referenz.")
    print(f"  abweichende Werte: {schlecht} von {diff.size} "
          f"({100.0 * schlecht / diff.size:.2f} %)")
    print(f"  groesste Abweichung: {int(np.abs(diff).max())}")
    print("  -> SOFORT STOPPEN und die letzte Aenderung (Treiber/SDK/"
          "Fenstergroesse) zuruecknehmen.")
    return 1


if __name__ == "__main__":
    sys.exit(haupt())
