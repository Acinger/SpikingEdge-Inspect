#!/usr/bin/env python3
"""Kernziel-Pruefung: ein AKD1500, eine Hardwaresequenz, ein Hardwaredurchgang.

Auf dem Pi ausfuehren, solange der AKD1500 angeschlossen ist:

    python3 tools/check_single_pass.py            # alle Varianten
    python3 tools/check_single_pass.py --variant V2
    python3 tools/check_single_pass.py --list     # nur Topologien anzeigen

Ergebnis je Variante: PASS oder FAIL mit Begruendung. Erst bei PASS lohnt
sich das Training - siehe SPEC.md Abschnitt 3.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vorsa import config                      # noqa: E402
from vorsa.model_m3 import (                  # noqa: E402
    AKIDA_AVAILABLE, BUILD, VARIANTS, check_single_pass, describe_devices,
)

SCRIPT_BUILD = "0.2.0"


def print_devices() -> int:
    """Zeigt die angeschlossene Hardware. Liefert die NP-Zahl oder 0."""
    if not AKIDA_AVAILABLE:
        print("MetaTF ('akida') ist nicht importierbar.")
        return 0

    import akida
    print(f"MetaTF-Version: {getattr(akida, '__version__', 'unbekannt')}")
    infos = describe_devices()
    if not infos:
        print("Kein Akida-Geraet gefunden. PCIe-Verbindung und Treiber pruefen.")
        return 0

    if len(infos) == 1 and "__fehler__" in infos[0]:
        msg = infos[0]["__fehler__"]
        print("Geraeteabfrage FEHLGESCHLAGEN - kein nutzbares Geraet.")
        print(f"  {msg}")
        print()
        if "errno(110)" in msg or "timed out" in msg.lower():
            print("  errno 110 = Zeitueberschreitung beim Lesen eines Registers.")
            print("  Der Chip antwortet auf dem PCIe-Bus nicht mehr. Typisch,")
            print("  wenn ein vorheriger Prozess mitten im Betrieb beendet wurde")
            print("  und der Chip in einem halben Zustand haengt.")
            print()
            print("  Abhilfe, in dieser Reihenfolge:")
            print("    sudo modprobe -r akida_pcie && sudo modprobe akida_pcie")
            print("    sudo dmesg | grep -i akida | tail -5      # 'probed' erwartet")
            print("    sudo reboot                               # wenn das nicht reicht")
        elif "file lock" in msg.lower():
            print("  Ein anderer Prozess haelt das Geraet exklusiv.")
            print("    ps aux | grep -i python | grep -v grep")
        return 0

    print(f"Gefundene Geraete: {len(infos)}")
    nps = 0
    for info in infos:
        print("  " + "  ".join(f"{k}={v}" for k, v in info.items()))
        if info.get("index") == 0 and isinstance(info.get("nps"), int):
            nps = info["nps"]

    if nps:
        if nps != config.AKD1500_NP_BUDGET:
            print(f"\n  ACHTUNG: config.AKD1500_NP_BUDGET steht auf "
                  f"{config.AKD1500_NP_BUDGET}, der Chip meldet {nps}.")
            print(f"  Bitte in vorsa/config.py korrigieren: "
                  f"AKD1500_NP_BUDGET = {nps}")
        else:
            print(f"\n  NP-Budget bestaetigt: {nps}")
    else:
        print("\n  NP-Zahl war aus der API nicht auslesbar - "
              "Wert in config.py bleibt eine Annahme.")
    return nps


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default=None,
                    help="V1 | V2 | V3 | V2-M1 | V2-M2 | V2-C16")
    ap.add_argument("--list", action="store_true", help="nur Topologien anzeigen")
    ap.add_argument("--devices", action="store_true",
                    help="nur angeschlossene Hardware anzeigen")
    ap.add_argument("--np-budget", type=int, default=0,
                    help="0 = vom Chip lesen, sonst config-Wert ueberschreiben")
    args = ap.parse_args()

    # Steht hier eine aeltere Nummer als erwartet, liegt auf diesem Rechner
    # noch eine alte Fassung - dann sagt die Ausgabe nichts ueber das Modell.
    print(f"[Pruefskript {SCRIPT_BUILD} | model_m3 {BUILD}]")

    if args.devices:
        print_devices()
        return 0

    names = [args.variant] if args.variant else list(VARIANTS)
    for n in names:
        if n not in VARIANTS:
            print(f"Unbekannte Variante '{n}'. Bekannt: {list(VARIANTS)}")
            return 2

    if args.list:
        for n in names:
            print(VARIANTS[n].summary())
            print()
        return 0

    if not AKIDA_AVAILABLE:
        print("MetaTF ('akida') ist hier nicht installiert.")
        print("Dieses Skript muss auf dem Pi mit angeschlossenem AKD1500 laufen.")
        print("Ohne Hardware ist nur --list sinnvoll.\n")

    detected_nps = print_devices()
    print()
    budget = args.np_budget or detected_nps or config.AKD1500_NP_BUDGET

    results = {}
    reports = {}
    for n in names:
        v = VARIANTS[n]
        print(v.summary())
        rep = check_single_pass(v, np_budget=budget)
        print(rep.render())
        print()
        results[n] = rep.ok
        reports[n] = rep

    print("=== Zusammenfassung ===")
    for n, ok in results.items():
        rep = reports[n]
        status = "NICHT PRUEFBAR" if rep.blocked else ("PASS" if ok else "FAIL")
        print(f"  {n}: {status}")

    # Wenn ALLE Laeufe an der Umgebung scheiterten, sagt das nichts ueber die
    # Modellgroesse aus. Hier waere der Ratschlag "Modell verkleinern" falsch
    # und wuerde in die vollkommen falsche Richtung fuehren.
    if reports and all(r.blocked for r in reports.values()):
        reason = next(iter(reports.values())).blocked_reason
        print()
        print("Die Pruefung konnte NICHT durchgefuehrt werden.")
        print(f"Ursache: {reason}")
        print()
        print("Das ist kein Modellbefund. Ueber Groesse, Sequenzen und Passes")
        print("ist damit nichts gesagt - am Modell aendern waere jetzt falsch.")
        print()
        print("Zuerst das Geraet ansprechbar machen:")
        print("  dmesg | grep -i -E 'akida|brainchip' | tail -20")
        print("  ls -l /dev/ | grep -i -E 'akida|brain'")
        print("  sudo lsof /dev/akida* 2>/dev/null")
        print("  sudo $(which python3) -c \"import akida; print(akida.devices())\"")
        print()
        print("'ERROR (file lock): 11' bedeutet: die Sperre auf das Geraet ist")
        print("nicht zu bekommen. Meist haelt ein anderer Prozess den Chip, oder")
        print("dem eigenen Benutzer fehlen die Rechte am Geraetknoten.")
        return 2

    # Scheitern alle Varianten mit derselben Meldung, ist eine gemeinsame
    # Ursache viel wahrscheinlicher als sechs unabhaengige Groessenprobleme.
    # Unterschiedlich grosse Modelle scheitern normalerweise unterschiedlich.
    map_errors = {
        detail
        for rep in reports.values()
        for label, passed, detail in rep.checks
        if label.startswith("map(") and not passed
    }
    if len(names) > 1 and len(map_errors) == 1 and len(reports) > 1:
        msg = next(iter(map_errors))
        print()
        print("Alle Varianten scheitern mit exakt derselben Meldung:")
        print(f"  {msg}")
        print()
        print("Das spricht fuer eine gemeinsame Ursache im Modellbau, nicht")
        print("fuer sechs unabhaengige Groessenprobleme. Unterschiedlich grosse")
        print("Modelle scheitern sonst unterschiedlich.")
        if "zero" in msg.lower():
            print()
            print("Diese Meldung heisst: die Gewichte sind noch null. Pruefe die")
            print("Zeile 'Gewichte ungleich null' im Bericht - steht dort FEHL,")
            print("liegt es am Initialisieren, nicht an der Architektur.")
        print()

    if not any(results.values()):
        print("\nHinweis zur Fehlersuche (Messung vom 2026-08-26):")
        print("  Rechenkapazitaet ist NICHT der Engpass - V2 braucht 5 von 32 NPs.")
        print("  Wer bei einem FAIL zuerst Kanaele halbiert, behebt meist nichts.")
        print()
        print("  Zuerst die gemessenen harten Grenzen pruefen:")
        print(f"    Eingang    <= {config.HW_MAX_INPUT_DIM} px")
        print(f"    Stem       <= {config.HW_MAX_STEM_FILTERS} Filter")
        print(f"    Kopfeingang<= {config.HW_MAX_HEAD_INPUT_CH} Kanaele")
        print()
        print("  Ist es ein Passzahl-Problem, liegt es fast sicher am MapMode:")
        print("    Minimal  wenigste NPs, 1 Pass")
        print("    AllNps   Standard, 1 Pass, hoeherer Durchsatz")
        print("    HwPr     2 PASSES - verletzt das Kernziel, nicht verwenden")
        print()
        print("  M zu senken ist der letzte Schritt, nicht der erste: damit")
        print("  gibt man die lokale Mehrfachbelegung auf und damit das,")
        print("  was VORSA-M3 von einem kleinen YOLO unterscheidet.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
