#!/usr/bin/env python3
"""Durchstich der Trainingskette auf synthetischen Daten.

    python3 tools/train_smoke.py --steps 60 --batch 4
    python3 tools/train_smoke.py --steps 60 --skip-convert   # ohne cnn2snn

Zweck ist NICHT ein gutes Modell, sondern der Nachweis, dass die Kette haelt:

    Keras bauen -> Topologie gegen die geprueft Akida-Variante vergleichen
    -> Zuordnung -> Verlust faellt -> quantisieren -> nach .fbz umwandeln
    -> auf dem AKD1500 mappen -> ein Bild durchschicken

Bricht das irgendwo, waere jede vorher investierte Annotationsarbeit verloren.
Deshalb steht dieser Schritt vor der Datenerfassung, nicht danach.

Ein fallender Verlust auf 60 Schritten beweist keine Erkennungsleistung. Er
beweist nur, dass Gradienten ankommen und die Kette geschlossen ist.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vorsa import config, synth_objects                    # noqa: E402
from vorsa.assignment import match_batch                   # noqa: E402
from vorsa.losses import LossWeights, format_losses, vorsa_loss   # noqa: E402
from vorsa.model_m3 import VARIANTS                        # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default=config.ACTIVE_VARIANT)
    ap.add_argument("--steps", type=int, default=60)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--out", default="vorsa_m3.fbz")
    ap.add_argument("--skip-convert", action="store_true",
                    help="nur trainieren, keine Umwandlung nach .fbz")
    ap.add_argument("--skip-map", action="store_true",
                    help="nicht auf den Chip mappen (kein Geraet vorhanden)")
    args = ap.parse_args()

    variant = VARIANTS[args.variant]
    mc = variant.model_cfg
    px = variant.input_shape[0]
    grid = variant.grid
    cell = px / grid

    print(f"Variante {variant.name}")
    print(f"  Eingang {px}x{px}  Raster {grid}x{grid}  Zelle {cell:.0f} px")
    print(f"  Kopf {variant.head_channels} Kanaele, {grid*grid*mc.slots} Slots je Bild")
    print()

    # ------------------------------------------------------------------
    print("[1/6] Keras-Modell bauen")
    try:
        import tensorflow as tf
        from vorsa.keras_model import (
            build_keras, compare_topologies, convert_to_akida, quantize_for_akida,
        )
    except Exception as exc:
        print(f"  TensorFlow nicht nutzbar: {exc}")
        print("  Training braucht keinen Akida-Chip, aber TensorFlow:")
        print("    pip install tensorflow-cpu cnn2snn")
        return 1

    model = build_keras(variant)
    params = model.count_params()
    print(f"  {len(model.layers)} Schichten, {params:,} Parameter")

    # ------------------------------------------------------------------
    print("[2/6] Topologie gegen die geprueft Akida-Variante vergleichen")
    probleme = compare_topologies(model, variant)
    if probleme:
        print("  ABWEICHUNG:")
        for p in probleme:
            print(f"    - {p}")
        print("  Das Keras-Modell hat eine andere Form als die Variante, die")
        print("  die Kernziel-Pruefung bestanden hat. Abbruch: sonst trainierst")
        print("  du ein Modell, fuer das nichts geprueft wurde.")
        return 1
    print(f"  Ausgabe {model.output_shape} - stimmt ueberein")

    # ------------------------------------------------------------------
    print(f"[3/6] Training, {args.steps} Schritte")
    opt = tf.keras.optimizers.Adam(learning_rate=args.lr)
    gew = LossWeights()
    verlauf = []

    t0 = time.perf_counter()
    for schritt in range(1, args.steps + 1):
        bilder, listen = synth_objects.make_batch(
            args.batch, size=px, num_classes=mc.num_classes,
            cell_px=cell, p_koinzident=0.5, seed=schritt)
        x = tf.constant(bilder, dtype=tf.float32)

        # Zuordnung braucht die aktuelle Vorhersage: welcher Slot welches
        # Objekt lernt, haengt davon ab, was das Netz gerade sagt.
        roh = model(x, training=False).numpy()
        y_true, mask = match_batch(roh, listen, grid, (px, px), mc)
        y_true = tf.constant(y_true)
        mask = tf.constant(mask)

        with tf.GradientTape() as tape:
            pred = model(x, training=True)
            teile = vorsa_loss(y_true, pred, mask, mc, gew)
            verlust = teile["total"]
        grads = tape.gradient(verlust, model.trainable_variables)
        opt.apply_gradients(zip(grads, model.trainable_variables))

        verlauf.append(float(verlust))
        if schritt == 1 or schritt % 10 == 0 or schritt == args.steps:
            print(f"  {schritt:>4}  {format_losses(teile)}")

    dauer = time.perf_counter() - t0
    anfang = float(np.mean(verlauf[:5]))
    ende = float(np.mean(verlauf[-5:]))
    print(f"  {dauer:.1f} s, {dauer/args.steps*1000:.0f} ms je Schritt")
    print(f"  Verlust {anfang:.4f} -> {ende:.4f}")

    if ende >= anfang:
        print("  ACHTUNG: der Verlust faellt nicht. Die Kette ist geschlossen,")
        print("  aber es lernt nichts. Vor dem Weitermachen klaeren:")
        print("    - Lernrate zu hoch oder zu niedrig?")
        print("    - kommen ueberhaupt Objekte an? Zeile n_pos pruefen")
        print("    - einzelne Anteile ansehen: welcher faellt nicht?")
    else:
        print("  Gradienten kommen an. Das ist alles, was dieser Schritt zeigt -")
        print("  ueber Erkennungsleistung sagt er nichts.")

    # ------------------------------------------------------------------
    if args.skip_convert:
        print("\n[4/6] Umwandlung uebersprungen (--skip-convert)")
        return 0

    print("\n[4/6] Quantisieren (4 Bit Gewichte, 8 Bit im Eingang)")
    try:
        qmodel = quantize_for_akida(model)
        print("  quantisiert")
    except Exception as exc:
        print(f"  FEHLGESCHLAGEN: {exc}")
        print("  Haeufigste Ursache: eine Schicht oder Reihenfolge, die cnn2snn")
        print("  nicht kennt. Der Meldungstext nennt sie - das ist ein Bau-,")
        print("  kein Trainingsproblem.")
        return 1

    print("[5/6] Nach Akida umwandeln und speichern")
    try:
        akida_model = convert_to_akida(qmodel)
        akida_model.save(args.out)
        print(f"  gespeichert: {args.out}")
    except Exception as exc:
        print(f"  FEHLGESCHLAGEN: {exc}")
        return 1

    # ------------------------------------------------------------------
    if args.skip_map:
        print("\n[6/6] Mapping uebersprungen (--skip-map)")
        return 0

    print("[6/6] Auf den AKD1500 mappen und ein Bild durchschicken")
    try:
        import akida
        geraete = akida.devices()
        if not geraete:
            print("  Kein Geraet - .fbz liegt vor, Mapping spaeter auf dem Pi.")
            return 0
        dev = geraete[0]
        akida_model.map(dev, hw_only=True, mode=akida.MapMode.AllNps)
        passes = sum(len(s.passes) for s in akida_model.sequences)
        print(f"  Sequenzen {len(akida_model.sequences)}, Passes {passes}")
        if passes != 1:
            print("  ACHTUNG: mehr als ein Durchgang. Kernziel verletzt.")
            return 1

        probe = synth_objects.make_scene(size=px, num_classes=mc.num_classes,
                                         cell_px=cell, seed=99)
        t0 = time.perf_counter()
        aus = akida_model.forward(probe.image[None, ...].astype(np.uint8))
        dt = (time.perf_counter() - t0) * 1000
        print(f"  Ausgabe {np.asarray(aus).shape} in {dt:.1f} ms")
        print("\nDIE KETTE IST GESCHLOSSEN: Keras -> quantisiert -> .fbz")
        print("-> ein AKD1500, ein Durchgang -> Ausgabe in der erwarteten Form.")
    except Exception as exc:
        print(f"  FEHLGESCHLAGEN: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
