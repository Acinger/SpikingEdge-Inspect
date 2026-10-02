#!/usr/bin/env python3
"""Akida Capability Report - was koennen die vier AKD1500 wirklich?

Read-only: liest nur Geraete-Metadaten, mappt kein Modell, veraendert
nichts. Erster, risikofreier Schritt in Kevin D. Johnsons Weight-Bank-
Thema - zeigt NP-Zahl, Mesh, Version, Speicher und alle vom SDK
gemeldeten Faehigkeiten je Karte.

Aufruf (Server vorher stoppen, sonst sind die Karten belegt):
    pkill -f run_web
    source ~/akida-env/bin/activate
    python3 tools/akida_report.py
"""
from __future__ import annotations
import sys


def zeig(obj, name, tiefe=0):
    """Ein Attribut sicher ausgeben (Wert, oder Fehler statt Absturz)."""
    try:
        v = getattr(obj, name)
    except Exception as exc:
        print(f"    {name}: <Fehler: {exc}>"); return
    if callable(v):
        try:
            v = v()
        except Exception as exc:
            print(f"    {name}(): <nicht abrufbar: {exc}>"); return
    print(f"    {name}: {v}")


def main() -> int:
    try:
        import akida
    except ImportError:
        print("akida nicht gefunden - im akida-env starten"); return 2
    print("=" * 60)
    print("AKIDA CAPABILITY REPORT")
    print("  akida-Version:", getattr(akida, "__version__", "?"))
    for fn in ("AkidaVersion", "get_akida_version"):
        if hasattr(akida, fn):
            try: print("  API-Level:", getattr(akida, fn)())
            except Exception: pass
    print("=" * 60)

    devs = akida.devices()
    print(f"Gefundene Karten: {len(devs)}\n")

    # interessante Attribute, die je nach SDK-Version existieren koennen
    kandidaten = ["desc", "version", "ip_version", "pcie_device_id",
                  "memory", "metrics", "learning_mem", "np_per_row",
                  "np_per_col"]
    for i, d in enumerate(devs):
        print(f"--- Karte {i+1} " + "-" * 44)
        for a in kandidaten:
            if hasattr(d, a):
                zeig(d, a)
        # Mesh (Neural Processors)
        mesh = getattr(d, "mesh", None)
        if mesh is not None:
            print("    mesh:")
            for a in ("nps", "dma_event", "dma_conf", "ident"):
                if hasattr(mesh, a):
                    zeig(mesh, a)
            try:
                print(f"    Neural Processors (len mesh.nps): "
                      f"{len(mesh.nps)}")
            except Exception:
                pass
        # alles Uebrige, das nicht privat ist - zum Stoebern
        rest = [a for a in dir(d)
                if not a.startswith("_") and a not in kandidaten
                and a != "mesh"]
        print("    weitere Attribute:", ", ".join(rest))
        print()

    print("Fertig - nichts veraendert (read-only).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
