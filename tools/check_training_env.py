#!/usr/bin/env python3
"""Prueft, welcher Weg vom Keras-Modell zum .fbz auf diesem Rechner offen ist.

Es gibt zwei Umwandlungsketten in der BrainChip-Werkzeugkiste:

  Akida 1.0:  Keras -> cnn2snn.quantize -> Training -> cnn2snn.convert -> .fbz
  Akida 2.0:  Keras -> quantizeml       -> Training -> cnn2snn.convert -> .fbz

Der AKD1500 ist Akida 1.0 (IpVersion.v1, gemessen). Damit ist der erste Weg
der richtige. Ob er hier verfuegbar ist, sagt dieses Skript.

    python3 tools/check_training_env.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def probe(name: str, attr: str = "__version__"):
    try:
        mod = __import__(name)
    except Exception as exc:
        return None, str(exc)
    return getattr(mod, attr, "?"), None


def main() -> int:
    print("=== Umgebung fuer das Training ===\n")

    gefunden = {}
    for paket in ("tensorflow", "keras", "akida", "cnn2snn", "quantizeml", "numpy"):
        ver, fehler = probe(paket)
        gefunden[paket] = ver
        if ver:
            print(f"  [OK  ] {paket:<12} {ver}")
        else:
            kurz = fehler.split("\n")[0][:70]
            print(f"  [FEHL] {paket:<12} {kurz}")

    print()

    # ------------------------------------------------------------------
    if gefunden.get("cnn2snn"):
        import cnn2snn
        print("cnn2snn-Schnittstelle:")
        for fn in ("quantize", "convert", "load_quantized_model", "check_model_compatibility"):
            print(f"  {fn:<26} {'vorhanden' if hasattr(cnn2snn, fn) else 'FEHLT'}")

        try:
            import inspect
            print(f"\n  Signatur quantize: {inspect.signature(cnn2snn.quantize)}")
            print(f"  Signatur convert:  {inspect.signature(cnn2snn.convert)}")
        except Exception as exc:
            print(f"  Signaturen nicht lesbar: {exc}")

    print()

    # ------------------------------------------------------------------
    tf_ok = bool(gefunden.get("tensorflow"))
    c2s_ok = bool(gefunden.get("cnn2snn"))

    if tf_ok and c2s_ok:
        print("BEFUND: Training und Umwandlung koennen auf DIESEM Rechner laufen.")
        print("Naechster Schritt: python3 tools/train_smoke.py")
    elif c2s_ok and not tf_ok:
        print("BEFUND: cnn2snn ist da, TensorFlow fehlt.")
        print("  pip install tensorflow-cpu")
        print("Auf einem Pi ist das moeglich, aber langsam. Trainieren besser")
        print("auf einem PC, nur die Umwandlung und das Mapping hier.")
    elif tf_ok and not c2s_ok:
        print("BEFUND: TensorFlow ist da, cnn2snn fehlt.")
        print("  pip install cnn2snn")
    else:
        print("BEFUND: Weder TensorFlow noch cnn2snn vorhanden.")
        print()
        print("Arbeitsteilung, die sich anbietet:")
        print("  PC  : pip install tensorflow cnn2snn  -> bauen, trainieren, .fbz erzeugen")
        print("  Pi  : akida (bereits da)              -> .fbz laden, mappen, messen")
        print()
        print("Das Training braucht keine Akida-Hardware. Nur die Umwandlung")
        print("nach .fbz braucht cnn2snn - und die laeuft auch ohne Chip.")

    print()
    print("Hinweis zur Version: cnn2snn und akida muessen zueinander passen.")
    print(f"  akida hier: {gefunden.get('akida')}")
    print(f"  cnn2snn hier: {gefunden.get('cnn2snn')}")
    print("Weichen die Hauptversionen ab, schlaegt convert() spaeter fehl -")
    print("meist mit einer Meldung ueber eine nicht unterstuetzte Schicht,")
    print("was leicht als Architekturproblem missverstanden wird.")

    return 0 if (tf_ok and c2s_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
