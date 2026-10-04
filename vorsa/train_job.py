"""M3-Training als Hintergrundlauf, gespeist aus den gesammelten Fotos.

Das ist der lange Weg - Minuten bis Stunden, nicht Sekunden. Er liefert den
eigentlichen Detektor: mehrere Teile je Bild, mit Kasten, Winkel und
Verdeckungsgrad. Das Chip-Lernen aus edge_learn.py bleibt daneben bestehen;
es beantwortet eine andere Frage (welches Teil ist in diesem Ausschnitt) und
braucht dafuer Sekunden statt Stunden.

Die Trainingsbilder entstehen nicht aus den Fotos direkt, sondern werden aus
ihnen zusammengesetzt (dataset_build). Nur so gibt es ueberlappende Szenen
mit exakt bekannter Beschriftung.
"""
from __future__ import annotations

import json
import os
import pickle
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable, List

import numpy as np

from . import config
from .dataset_build import baue_stapel, freistellen_aus_zustand
from .jobs import Lauf

MIN_TEILE = 6          # unter so wenigen Vorlagen wiederholt sich jede Szene


# ----------------------------------------------------------------------
# Getrennte Trainingsumgebung (2026-09-07)
#
# Der Akida-2.19-Stack (cnn2snn, opencv-python 5, ml-dtypes) verlangt
# numpy>=2. Der Server-Kern braucht numpy<2 (picamera2/simplejpeg ist ein
# System-Binary gegen numpy 1.x). Beides passt nicht in EIN venv. Deshalb
# laeuft das eigentliche Training in einem zweiten venv (~/m3-train-env,
# numpy 2) als Unterprozess; der Server (numpy<2) stellt nur die Fotos frei
# und legt die fertige .fbz auf den Chip.

# 1.9.71: Gesamtfortschritt ueber die Phasen (Anteil am Gesamtlauf, grob
# nach Dauer auf dem Pi geschaetzt).
PHASEN_GEWICHT = (("Fotos freistellen", 0.15), ("TensorFlow laden", 0.05), ("Modell bauen", 0.02),
                  ("Training", 0.68), ("Quantisieren", 0.04), ("Nach Akida umwandeln", 0.03),
                  ("Auf den AKD1500 legen", 0.03))


def _gesamt(phase: str, anteil: float = 0.0) -> float:
    """Fortschritt 0..1 ueber alle Phasen: abgeschlossene Phasen voll, die
    laufende anteilig. Unbekannte Phasen (z. B. aus dem Unterprozess) werden
    dem Training zugeschlagen."""
    vor = 0.0
    for name, g in PHASEN_GEWICHT:
        if phase.startswith(name):
            return vor + g * max(0.0, min(1.0, anteil))
        vor += g
    # unbekannt: zwischen "TensorFlow laden" und Training
    return 0.22 + 0.68 * max(0.0, min(1.0, anteil))


def _phase_mit_gesamt(lauf, phase: str, schritt: int = 0, schritte: int = 0) -> None:
    lauf.setze_phase(phase, schritt, schritte)
    lauf.setze_gesamt(_gesamt(phase, (schritt / schritte) if schritte else 0.0))

def _train_python() -> str:
    """Pfad zum Python der Trainingsumgebung - oder "" wenn keine da ist."""
    gesetzt = os.environ.get("VORSA_M3_PY")
    if gesetzt and Path(gesetzt).exists():
        return gesetzt
    kandidat = Path.home() / "m3-train-env" / "bin" / "python"
    return str(kandidat) if kandidat.exists() else ""


def baue_arbeit_extern(zustand, verarbeitung, variante: str = "",
                       schritte: int = 300, batch: int = 4, lr: float = 1e-3,
                       ausgabe: str = "vorsa_m3.fbz",
                       mit_varianten: bool = True) -> Callable[[Lauf], dict]:
    """M3-Training im getrennten venv. Fallback auf in-process, wenn keine
    Trainingsumgebung eingerichtet ist."""

    def arbeit(lauf: Lauf) -> dict:
        py = _train_python()
        if not py:
            # Keine getrennte Umgebung: alten Weg versuchen (klappt nur, wenn
            # TensorFlow ausnahmsweise im Server-venv liegt).
            lauf.melde("Keine Trainingsumgebung ~/m3-train-env gefunden - "
                       "versuche in-process (nur mit TensorFlow im Server-venv).")
            return baue_arbeit(zustand, variante=variante, schritte=schritte,
                               batch=batch, lr=lr, ausgabe=ausgabe,
                               mit_varianten=mit_varianten)(lauf)

        # --- 1. Fotos freistellen (cv2, laeuft unter numpy<2) ---------
        _phase_mit_gesamt(lauf, "Fotos freistellen")
        teile, namen, warnungen = freistellen_aus_zustand(
            zustand, mit_varianten,
            fortschritt=lambda i, n: _phase_mit_gesamt(lauf, "Fotos freistellen", i, n))
        for w in warnungen:
            lauf.melde(f"Hinweis: {w}")
        lauf.melde(f"{len(teile)} Vorlagen aus {len(namen)} Objekten")
        if len(teile) < MIN_TEILE:
            return {"ok": False, "grund": (
                f"nur {len(teile)} brauchbare Vorlagen - mindestens {MIN_TEILE} "
                "noetig. Mehr Fotos sammeln oder den Kontrast verbessern.")}

        # --- 2. Freigestellte Teile als Pickle herausschreiben --------
        tmp = tempfile.mkdtemp(prefix="m3_")
        eingabe = str(Path(tmp) / "eingang.pkl")
        try:
            with open(eingabe, "wb") as f:
                pickle.dump({"teile": teile, "namen": namen,
                             "params": {"variante": variante,
                                        "schritte": schritte,
                                        "batch": batch, "lr": lr}},
                            f, protocol=4)
        except Exception as exc:
            shutil.rmtree(tmp, ignore_errors=True)
            return {"ok": False, "grund": f"Eingabe nicht schreibbar: {exc}"}

        # --- 3. Trainingsprozess im zweiten venv ----------------------
        ziel = str(Path(ausgabe).resolve())
        projekt = str(Path(__file__).resolve().parent.parent)  # enthaelt vorsa/
        umg = dict(os.environ)
        umg["TF_CPP_MIN_LOG_LEVEL"] = "3"
        _phase_mit_gesamt(lauf, "TensorFlow laden")
        lauf.melde(f"starte {py}")
        ergebnis = {"ok": False, "grund": "kein Ergebnis vom Trainingsprozess"}
        try:
            proc = subprocess.Popen(
                [py, "-m", "vorsa.m3_extern", eingabe, ziel],
                cwd=projekt, env=umg, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, bufsize=1)
        except Exception as exc:
            shutil.rmtree(tmp, ignore_errors=True)
            return {"ok": False, "grund": f"Trainingsprozess nicht startbar: {exc}"}

        try:
            for zeile in proc.stdout:                       # Zeile fuer Zeile
                zeile = zeile.rstrip("\n")
                if not zeile:
                    continue
                if lauf.abbruch_gewuenscht:
                    proc.terminate()
                    lauf.melde("abgebrochen")
                    break
                if zeile.startswith("@PHASE|"):
                    _phase_mit_gesamt(lauf, zeile[7:])
                elif zeile.startswith("@STEP|"):
                    try:
                        _, i, n = zeile.split("|", 2)
                        _phase_mit_gesamt(lauf, "Training", int(i), int(n))
                    except Exception:
                        pass
                elif zeile.startswith("@MELDE|"):
                    lauf.melde(zeile[7:])
                elif zeile.startswith("@ERGEBNIS|"):
                    try:
                        ergebnis = json.loads(zeile[10:])
                    except Exception as exc:
                        lauf.melde(f"Ergebnis unlesbar: {exc}")
                elif zeile.startswith("@FEHLER|"):
                    ergebnis = {"ok": False, "grund": zeile[8:]}
                    lauf.melde("FEHLER: " + zeile[8:])
                else:
                    lauf.melde(zeile[:160])                  # z. B. Traceback
        finally:
            code = proc.wait()
            shutil.rmtree(tmp, ignore_errors=True)

        if code != 0 and ergebnis.get("ok"):
            ergebnis = {"ok": False, "grund": f"Trainingsprozess Exitcode {code}"}
        if not ergebnis.get("ok"):
            return ergebnis

        # --- 4. Fertige .fbz auf den Chip legen (akida, numpy<2) ------
        if Path(ziel).exists():
            _phase_mit_gesamt(lauf, "Auf den AKD1500 legen")
            try:
                verarbeitung.detektor_laden(ziel)
                ergebnis["gemappt"] = bool(
                    getattr(verarbeitung, "detektor", None) is not None)
                lauf.melde("Detektor neu geladen" if ergebnis["gemappt"]
                           else "Detektor nicht gemappt - Selbstheilung "
                                "versucht es weiter")
            except Exception as exc:
                ergebnis["gemappt"] = False
                lauf.melde(f"Laden auf Chip spaeter (Selbstheilung): "
                           f"{str(exc)[:120]}")
        return ergebnis

    return arbeit


def baue_arbeit(zustand, variante: str = "", schritte: int = 300,
                batch: int = 4, lr: float = 1e-3,
                ausgabe: str = "vorsa_m3.fbz",
                mit_varianten: bool = True) -> Callable[[Lauf], dict]:
    """Erzeugt die Arbeitsfunktion fuer einen `Lauf`."""

    def arbeit(lauf: Lauf) -> dict:
        from .model_m3 import VARIANTS

        name = variante or config.ACTIVE_VARIANT
        if name not in VARIANTS:
            return {"ok": False, "grund": f"Variante {name} unbekannt"}
        var = VARIANTS[name]
        mc = var.model_cfg
        px = var.input_shape[0]
        grid = var.grid
        cell = px / grid

        # --- 1. Vorlagen freistellen ---------------------------------
        _phase_mit_gesamt(lauf, "Fotos freistellen")
        lauf.melde(f"Variante {var.name}: {px}x{px}, Raster {grid}x{grid}, "
                   f"Zelle {cell:.0f} px")
        teile, namen, warnungen = freistellen_aus_zustand(
            zustand, mit_varianten,
            fortschritt=lambda i, n: _phase_mit_gesamt(lauf, "Fotos freistellen", i, n))
        for w in warnungen:
            lauf.melde(f"Hinweis: {w}")
        lauf.melde(f"{len(teile)} Vorlagen aus {len(namen)} Objekten")

        if len(teile) < MIN_TEILE:
            return {"ok": False, "grund": (
                f"nur {len(teile)} brauchbare Vorlagen - mindestens {MIN_TEILE} "
                "noetig. Mehr Fotos sammeln oder den Kontrast zum Untergrund "
                "verbessern.")}
        if len(namen) > mc.num_classes:
            return {"ok": False, "grund": (
                f"{len(namen)} Objekte, das Modell hat {mc.num_classes} "
                "Klassenplaetze. In config.py erhoehen und die Kernziel-"
                "Pruefung erneut laufen lassen.")}

        # --- 2. TensorFlow ------------------------------------------
        _phase_mit_gesamt(lauf, "TensorFlow laden")
        lauf.melde("TensorFlow wird geladen - auf dem Pi dauert das ~20 s")
        try:
            # MUSS vor dem ersten Import von TensorFlow stehen: danach ist die
            # Wahl zwischen Keras 2 und Keras 3 nicht mehr aenderbar.
            from .keras_model import legacy_keras_anfordern
            legacy_keras_anfordern()

            import tensorflow as tf
            from .keras_model import (
                build_keras, compare_topologies, convert_to_akida,
                keras_modul, quantize_for_akida,
            )
        except Exception as exc:
            return {"ok": False, "grund": (
                f"TensorFlow nicht nutzbar: {str(exc)[:120]}. "
                "Installieren: pip install tensorflow-cpu cnn2snn")}

        from .assignment import match_batch
        from .losses import LossWeights, format_losses, vorsa_loss

        _phase_mit_gesamt(lauf, "Modell bauen")
        keras, herkunft = keras_modul()
        lauf.melde(f"Keras: {herkunft}")
        modell = build_keras(var)
        lauf.melde(f"{len(modell.layers)} Schichten, "
                   f"{modell.count_params():,} Parameter")

        probleme = compare_topologies(modell, var)
        if probleme:
            for p in probleme:
                lauf.melde(f"ABWEICHUNG: {p}")
            return {"ok": False, "grund": (
                "Das Keras-Modell hat eine andere Form als die Variante, die "
                "die Kernziel-Pruefung bestanden hat. Abbruch - sonst "
                "trainierst du ein Modell, fuer das nichts geprueft wurde.")}

        # --- 3. Training --------------------------------------------
        opt = keras.optimizers.Adam(learning_rate=lr)
        gew = LossWeights()
        verlauf: List[float] = []
        t0 = time.perf_counter()

        for schritt in range(1, schritte + 1):
            if lauf.abbruch_gewuenscht:
                lauf.melde(f"abgebrochen nach {schritt-1} Schritten")
                break

            bilder, listen = baue_stapel(teile, batch, px, seed=schritt,
                                         max_objekte=6, p_ueberlappung=0.5)
            x = tf.constant(bilder, dtype=tf.float32)

            # Die Zuordnung braucht die aktuelle Vorhersage: welcher Slot
            # welches Objekt lernt, haengt davon ab, was das Netz gerade sagt.
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
            _phase_mit_gesamt(lauf, "Training", schritt, schritte)
            if schritt == 1 or schritt % 10 == 0 or schritt == schritte:
                lauf.melde(f"{schritt:>4}/{schritte}  {format_losses(teile_v)}")

        dauer = time.perf_counter() - t0
        if not verlauf:
            return {"ok": False, "grund": "kein einziger Schritt gelaufen"}
        anfang = float(np.mean(verlauf[:5]))
        ende = float(np.mean(verlauf[-5:]))
        lauf.melde(f"{dauer:.0f} s, {dauer/len(verlauf)*1000:.0f} ms je Schritt")
        lauf.melde(f"Verlust {anfang:.4f} -> {ende:.4f}")
        if ende >= anfang:
            lauf.melde("ACHTUNG: der Verlust faellt nicht. Die Kette ist "
                       "geschlossen, aber es lernt nichts.")

        # --- 4. Gewichte sichern, BEVOR quantisiert wird -------------
        #
        #     Das Trainieren ist der teure Teil, das Umwandeln der
        #     zerbrechliche. Faellt die Umwandlung aus, waeren sonst alle
        #     Schritte verloren - und genau das ist am 2026-08-26 passiert,
        #     als cnn2snn an Keras 3 scheiterte.
        gewichte = str(Path(ausgabe).with_suffix("").resolve()) + ".weights.h5"
        try:
            modell.save_weights(gewichte)
            lauf.melde(f"Gewichte gesichert: {gewichte}")
        except Exception as exc:
            gewichte = ""
            lauf.melde(f"Gewichte NICHT sicherbar: {str(exc)[:110]}")

        _phase_mit_gesamt(lauf, "Quantisieren")
        try:
            qmodell = quantize_for_akida(modell)
        except Exception as exc:
            return {"ok": False, "gewichte": gewichte, "grund": (
                f"Quantisieren: {str(exc)[:160]}"
                + (f" — Das Training ist nicht verloren, die Gewichte liegen "
                   f"in {gewichte}." if gewichte else ""))}

        _phase_mit_gesamt(lauf, "Nach Akida umwandeln")
        ziel = str(Path(ausgabe).resolve())
        try:
            akida_modell = convert_to_akida(qmodell)
            akida_modell.save(ziel)
            lauf.melde(f"gespeichert: {ziel}")
        except Exception as exc:
            return {"ok": False, "grund": f"Umwandeln: {str(exc)[:140]}"}

        # --- 5. Auf den Chip legen ----------------------------------
        _phase_mit_gesamt(lauf, "Auf den AKD1500 legen")
        ergebnis = {"ok": True, "datei": ziel, "variante": var.name,
                    "schritte": len(verlauf), "verlust_anfang": round(anfang, 4),
                    "verlust_ende": round(ende, 4), "sekunden": round(dauer, 1),
                    "vorlagen": len(teile), "objekte": namen}
        try:
            import akida
            geraete = akida.devices()
            if not geraete:
                lauf.melde("kein Geraet - die .fbz liegt vor, Mapping spaeter")
                ergebnis["gemappt"] = False
                return ergebnis
            akida_modell.map(geraete[0], hw_only=True, mode=akida.MapMode.AllNps)
            passes = sum(len(s.passes) for s in akida_modell.sequences)
            ergebnis.update({"gemappt": True,
                             "sequenzen": len(akida_modell.sequences),
                             "passes": passes,
                             "kernziel_erfuellt": (
                                 len(akida_modell.sequences) == 1 and passes == 1)})
            lauf.melde(f"Sequenzen {len(akida_modell.sequences)}, Passes {passes}")
            if not ergebnis["kernziel_erfuellt"]:
                lauf.melde("ACHTUNG: mehr als ein Durchgang - Kernziel verletzt.")
        except Exception as exc:
            lauf.melde(f"Mapping fehlgeschlagen: {str(exc)[:140]}")
            ergebnis["gemappt"] = False
        return ergebnis

    return arbeit
