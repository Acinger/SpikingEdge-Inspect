"""M3-Training als EIGENER Prozess in einer zweiten Umgebung.

Warum getrennt (2026-09-07): der Akida-2.19-Stack (cnn2snn, opencv-python 5,
ml-dtypes) verlangt numpy>=2. Der Server-Kern dagegen braucht numpy<2, weil
picamera2/simplejpeg als System-Binary gegen numpy 1.x gebaut ist. Beides
passt nicht in EIN venv. Deshalb:

  * Server-venv  (~/akida-env, numpy 1.26.4)  -> Kamera + Inferenz + Mapping
  * Train-venv   (~/m3-train-env, numpy 2.1.3) -> nur DIESES Skript

Der Server stellt die Fotos frei (cv2, das laeuft unter numpy<2), schreibt die
freigestellten Teile als Pickle heraus und ruft dieses Skript im Train-venv
auf. Es trainiert, quantisiert, wandelt nach Akida um und speichert die .fbz.
Der Server laedt die fertige .fbz ueber `akida` (numpy<2) auf den Chip.

Aufruf:
    python -m vorsa.m3_extern <eingabe.pkl> <ausgabe.fbz>

Fortschritt geht Zeile fuer Zeile nach stdout, mit festem Praefix, damit der
Server ihn ins Protokoll spiegeln kann:
    @PHASE|<text>            neue Phase
    @STEP|<i>|<n>            Fortschritt innerhalb der Phase
    @MELDE|<text>            Protokollzeile
    @ERGEBNIS|<json>         Schlussergebnis (genau einmal, bei Erfolg)
    @FEHLER|<text>           Abbruchgrund (Exitcode != 0)
"""
from __future__ import annotations

import json
import os
import pickle
import sys
import time
from pathlib import Path
from typing import List

# TensorFlow leise halten: sonst ertraenkt sein Startgeschwaetz das Protokoll.
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

import numpy as np  # noqa: E402


def _phase(text: str) -> None:
    print(f"@PHASE|{text}", flush=True)


def _step(i: int, n: int) -> None:
    print(f"@STEP|{i}|{n}", flush=True)


def _melde(text: str) -> None:
    print(f"@MELDE|{text}", flush=True)


def _fehler(text: str) -> int:
    print(f"@FEHLER|{text}", flush=True)
    return 1


def main(argv: List[str]) -> int:
    if len(argv) < 3:
        return _fehler("Aufruf: python -m vorsa.m3_extern <eingabe.pkl> "
                       "<ausgabe.fbz>")
    eingabe, ausgabe = argv[1], argv[2]

    # --- Eingang laden -----------------------------------------------
    try:
        with open(eingabe, "rb") as f:
            paket = pickle.load(f)
        teile = paket["teile"]
        namen = paket["namen"]
        p = paket.get("params", {})
    except Exception as exc:
        return _fehler(f"Eingabe {eingabe} nicht lesbar: {exc}")

    variante = str(p.get("variante", "") or "")
    schritte = int(p.get("schritte", 300))
    batch = int(p.get("batch", 4))
    lr = float(p.get("lr", 1e-3))

    from . import config
    from .model_m3 import VARIANTS

    name = variante or config.ACTIVE_VARIANT
    if name not in VARIANTS:
        return _fehler(f"Variante {name} unbekannt")
    var = VARIANTS[name]
    mc = var.model_cfg
    px = var.input_shape[0]
    grid = var.grid

    _melde(f"Variante {var.name}: {px}x{px}, Raster {grid}x{grid}")
    _melde(f"{len(teile)} Vorlagen aus {len(namen)} Objekten")
    if len(namen) > mc.num_classes:
        return _fehler(f"{len(namen)} Objekte, das Modell hat "
                       f"{mc.num_classes} Klassenplaetze (config.py erhoehen).")

    # --- TensorFlow laden --------------------------------------------
    _phase("TensorFlow laden")
    _melde("TensorFlow wird geladen - auf dem Pi dauert das ~20 s")
    try:
        from .keras_model import legacy_keras_anfordern
        legacy_keras_anfordern()          # vor dem ERSTEN import tensorflow
        import tensorflow as tf
        from .keras_model import (
            build_keras, compare_topologies, convert_to_akida,
            keras_modul, quantize_for_akida,
        )
    except Exception as exc:
        return _fehler(f"TensorFlow/cnn2snn nicht nutzbar: {str(exc)[:200]}")

    from .assignment import match_batch
    from .dataset_build import baue_stapel
    from .losses import LossWeights, format_losses, vorsa_loss

    # --- Modell bauen ------------------------------------------------
    _phase("Modell bauen")
    keras, herkunft = keras_modul()
    _melde(f"Keras: {herkunft}")
    modell = build_keras(var)
    _melde(f"{len(modell.layers)} Schichten, {modell.count_params():,} Parameter")

    probleme = compare_topologies(modell, var)
    if probleme:
        for pr in probleme:
            _melde(f"ABWEICHUNG: {pr}")
        return _fehler("Keras-Form weicht von der geprueften Variante ab - "
                       "Abbruch.")

    # --- Training ----------------------------------------------------
    opt = keras.optimizers.Adam(learning_rate=lr)
    gew = LossWeights()
    verlauf: List[float] = []
    t0 = time.perf_counter()
    _phase("Training")

    for schritt in range(1, schritte + 1):
        bilder, listen = baue_stapel(teile, batch, px, seed=schritt,
                                     max_objekte=6, p_ueberlappung=0.5)
        x = tf.constant(bilder, dtype=tf.float32)

        roh = modell(x, training=False).numpy()
        y_true, maske = match_batch(roh, listen, grid, (px, px), mc)

        with tf.GradientTape() as tape:
            pred = modell(x, training=True)
            teile_v = vorsa_loss(tf.constant(y_true), pred,
                                 tf.constant(maske), mc, gew)
            verlust = teile_v["total"]
        grads = tape.gradient(verlust, modell.trainable_variables)
        opt.apply_gradients(zip(grads, modell.trainable_variables))

        verlauf.append(float(verlust))
        _step(schritt, schritte)
        if schritt == 1 or schritt % 10 == 0 or schritt == schritte:
            _melde(f"{schritt:>4}/{schritte}  {format_losses(teile_v)}")

    dauer = time.perf_counter() - t0
    if not verlauf:
        return _fehler("kein einziger Schritt gelaufen")
    anfang = float(np.mean(verlauf[:5]))
    ende = float(np.mean(verlauf[-5:]))
    _melde(f"{dauer:.0f} s, {dauer/len(verlauf)*1000:.0f} ms je Schritt")
    _melde(f"Verlust {anfang:.4f} -> {ende:.4f}")
    if ende >= anfang:
        _melde("ACHTUNG: der Verlust faellt nicht - es lernt nichts.")

    # --- Gewichte sichern, BEVOR quantisiert wird --------------------
    gewichte = str(Path(ausgabe).with_suffix("").resolve()) + ".weights.h5"
    try:
        modell.save_weights(gewichte)
        _melde(f"Gewichte gesichert: {gewichte}")
    except Exception as exc:
        gewichte = ""
        _melde(f"Gewichte NICHT sicherbar: {str(exc)[:110]}")

    # --- Quantisieren ------------------------------------------------
    _phase("Quantisieren")
    try:
        qmodell = quantize_for_akida(modell)
    except Exception as exc:
        return _fehler(f"Quantisieren: {str(exc)[:180]}"
                       + (f" (Gewichte liegen in {gewichte})" if gewichte else ""))

    # --- Nach Akida umwandeln + speichern ----------------------------
    _phase("Nach Akida umwandeln")
    ziel = str(Path(ausgabe).resolve())
    try:
        akida_modell = convert_to_akida(qmodell)
        akida_modell.save(ziel)
        _melde(f"gespeichert: {ziel}")
    except Exception as exc:
        return _fehler(f"Umwandeln: {str(exc)[:160]}")

    # Kennzahlen zum Modell (ohne Geraet - das Mapping macht der Server).
    ergebnis = {
        "ok": True, "datei": ziel, "variante": var.name,
        "schritte": len(verlauf), "verlust_anfang": round(anfang, 4),
        "verlust_ende": round(ende, 4), "sekunden": round(dauer, 1),
        "vorlagen": len(teile), "objekte": namen,
    }
    try:
        ergebnis["sequenzen"] = len(akida_modell.sequences)
        ergebnis["passes"] = sum(len(s.passes) for s in akida_modell.sequences)
    except Exception:
        pass
    print(f"@ERGEBNIS|{json.dumps(ergebnis, ensure_ascii=False)}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(_fehler("abgebrochen"))
    except Exception as exc:          # letzte Sicherung: nie stumm sterben
        import traceback
        traceback.print_exc()
        sys.exit(_fehler(f"{type(exc).__name__}: {exc}"))
