"""Keras-Gegenstueck zur Akida-Topologie und die Umwandlung nach .fbz.

Trainiert wird in Keras, ausgefuehrt auf dem AKD1500. Damit das aufgeht, muss
das Keras-Modell exakt dieselbe Struktur haben wie das native Akida-Modell aus
model_m3.py - sonst besteht die Kernziel-Pruefung fuer eine Topologie, die
spaeter gar nicht trainiert wird.

Kette fuer Akida 1.0:

    build_keras(variant)          normales Keras-Modell
      -> quantize_for_akida(...)  4-Bit-Gewichte, 8 Bit im Eingang
      -> Training (QAT)
      -> convert_to_akida(...)    akida.Model
      -> save(.fbz)               laedt der Pi

Wichtige Randbedingungen von cnn2snn, die die Bauform bestimmen:

  * Faltungen ohne Bias, dahinter BatchNorm. Die Normierung wird beim
    Umwandeln in die Gewichte eingerechnet und existiert auf dem Chip nicht
    mehr als eigene Schicht.
  * Aktivierung ReLU mit Obergrenze. Ohne Obergrenze gibt es keinen
    definierten Wertebereich zum Quantisieren.
  * Die letzte Schicht bleibt linear - Koordinaten und Winkel duerfen nicht
    bei null abgeschnitten werden.
  * V6 kommt ohne Pooling aus. Das ist kein Zufall: die zulaessige Reihenfolge
    von Pooling und Aktivierung unterscheidet sich zwischen cnn2snn-Versionen,
    und was man nicht baut, kann nicht falsch herum stehen.
"""
from __future__ import annotations

import inspect
import os
from typing import Optional

from . import config
from .model_m3 import VARIANTS, Variant


def legacy_keras_anfordern() -> None:
    """Muss VOR dem ersten `import tensorflow` laufen.

    TensorFlow 2.19 bringt Keras 3 mit. Der Umwandlungsweg von cnn2snn fuer
    Akida 1.0 stammt aus der Keras-2-Zeit und greift auf Dinge zu, die es in
    Keras 3 nicht mehr gibt - `model.input_names` etwa. Das faellt erst beim
    Quantisieren auf, also NACH dem Training: der teuerste Zeitpunkt fuer
    einen Fehlschlag.

    Mit gesetzter Umgebungsvariable und installiertem `tf_keras` liefert
    `tf.keras` wieder die Keras-2-Schnittstelle.
    """
    os.environ.setdefault("TF_USE_LEGACY_KERAS", "1")


def keras_modul():
    """Das Keras, mit dem gebaut und trainiert wird - und sein Name.

    Rueckgabe: (modul, herkunft). Die Herkunft wird protokolliert, damit im
    Fehlerfall nicht geraten werden muss, welches Keras im Spiel war.
    """
    legacy_keras_anfordern()
    tf = _tf()
    try:
        import tf_keras
        return tf_keras, "tf_keras (Keras 2)"
    except Exception:
        pass
    version = getattr(getattr(tf, "keras", None), "__version__", "?")
    return tf.keras, f"tf.keras {version}"


def _tf():
    try:
        import tensorflow as tf  # noqa: F401
        return tf
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "TensorFlow ist nicht installiert. Das Training laeuft auf einem "
            "PC, nicht zwingend auf dem Pi:  pip install tensorflow-cpu"
        ) from exc


# ----------------------------------------------------------------------
def build_keras(variant: Variant, relu_max: float = 6.0, rescale: bool = True):
    """Baut die Variante als Keras-Modell.

    `rescale=True` haengt eine Skalierung 1/255 vor das Netz. Akida erwartet
    uint8 am Eingang; im Training rechnet Keras mit Fliesskomma. Die Skalierung
    verschwindet beim Umwandeln in die Gewichte der ersten Schicht.
    """
    keras, _herkunft = keras_modul()
    L = keras.layers

    px = variant.input_shape[0]
    eingang = L.Input(shape=(px, px, 3), name="bild")
    x = L.Rescaling(1.0 / 255.0, name="skalierung")(eingang) if rescale else eingang

    for i, spec in enumerate(variant.backbone):
        gemeinsam = dict(
            filters=spec.filters,
            kernel_size=spec.kernel,
            strides=spec.stride,
            padding="same",
            use_bias=False,
            name=spec.name or f"schicht_{i}",
        )
        if spec.kind == "InputConvolutional" or spec.kind == "Convolutional":
            x = L.Conv2D(**gemeinsam)(x)
        elif spec.kind == "SeparableConvolutional":
            x = L.SeparableConv2D(**gemeinsam)(x)
        else:
            raise ValueError(f"Schicht '{spec.kind}' hat kein Keras-Gegenstueck.")

        x = L.BatchNormalization(name=f"{gemeinsam['name']}_bn")(x)
        if spec.pool:
            x = L.MaxPool2D(pool_size=spec.pool, strides=spec.pool,
                            padding="same", name=f"{gemeinsam['name']}_pool")(x)
        x = L.ReLU(max_value=relu_max, name=f"{gemeinsam['name']}_relu")(x)

    # Kopf: linear, ohne Bias, ohne Normierung.
    ausgang = L.Conv2D(
        filters=variant.head_channels, kernel_size=(1, 1), strides=(1, 1),
        padding="same", use_bias=False, name="m3_head",
    )(x)

    return keras.Model(eingang, ausgang, name=variant.name.replace("-", "_"))


def active_variant() -> Variant:
    return VARIANTS[config.ACTIVE_VARIANT]


# ----------------------------------------------------------------------
def quantize_for_akida(model, weight_bits: int = 4, activ_bits: int = 4,
                       input_weight_bits: int = 8):
    """Quantisiert das Modell fuer Akida 1.0.

    Die Signatur von cnn2snn.quantize hat sich zwischen Versionen geaendert.
    Statt eine Variante zu raten, werden die tatsaechlich akzeptierten
    Argumentnamen gelesen und passend belegt.
    """
    try:
        import cnn2snn
    except Exception as exc:  # pragma: no cover
        # Den ECHTEN Grund mitgeben. "pip install cnn2snn" war als Rat
        # wertlos, wenn das Paket installiert ist und nur sein Import an
        # einer NumPy-Unvertraeglichkeit scheitert - genau das ist am
        # 2026-08-27 passiert und die Meldung hat es versteckt.
        raise RuntimeError(
            f"cnn2snn laesst sich nicht importieren: "
            f"{type(exc).__name__}: {exc}") from exc

    sig = inspect.signature(cnn2snn.quantize)
    namen = set(sig.parameters)
    kwargs = {}
    for kandidat, wert in (
        ("weight_quantization", weight_bits),
        ("activ_quantization", activ_bits),
        ("input_weight_quantization", input_weight_bits),
    ):
        if kandidat in namen:
            kwargs[kandidat] = wert

    if not kwargs:
        print(f"[keras_model] Unbekannte quantize-Signatur: {sig}")
        print("[keras_model] Rufe ohne Bitbreiten auf - Vorgaben von cnn2snn.")

    try:
        return cnn2snn.quantize(model, **kwargs)
    except AttributeError as exc:
        if "input_names" not in str(exc) and "output_names" not in str(exc):
            raise
        # Notbehelf. Der saubere Weg ist tf_keras; wenn das fehlt, werden die
        # beiden Keras-2-Felder nachgereicht. Das reicht fuer diesen Aufruf,
        # ist aber ausdruecklich kein Ersatz - deshalb die Meldung.
        print("[keras_model] Keras 3 erkannt: cnn2snn erwartet Keras 2. "
              "Reiche input_names/output_names nach.")
        print("[keras_model] Dauerhafte Loesung:  pip install tf-keras")
        _keras2_felder_nachreichen(model)
        return cnn2snn.quantize(model, **kwargs)


def _keras2_felder_nachreichen(model) -> None:
    def namen(tensoren):
        aus = []
        for t in (tensoren if isinstance(tensoren, (list, tuple)) else [tensoren]):
            n = getattr(t, "name", None) or getattr(t, "_keras_history", ["?"])[0]
            aus.append(str(n).split(":")[0])
        return aus

    for feld, quelle in (("input_names", "inputs"), ("output_names", "outputs")):
        if getattr(model, feld, None):
            continue
        try:
            object.__setattr__(model, feld, namen(getattr(model, quelle)))
        except Exception as exc:
            raise RuntimeError(
                f"Konnte {feld} nicht nachreichen ({exc}). Das Training ist "
                "nicht verloren - es fehlt nur die Umwandlung. Abhilfe:\n"
                "    pip install tf-keras\n"
                "und den Lauf wiederholen."
            ) from exc


def convert_to_akida(model):
    """Wandelt das quantisierte Keras-Modell in ein akida.Model um."""
    try:
        import cnn2snn
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            f"cnn2snn laesst sich nicht importieren: "
            f"{type(exc).__name__}: {exc}") from exc
    return cnn2snn.convert(model)


def save_fbz(akida_model, pfad: str) -> str:
    akida_model.save(pfad)
    return pfad


# ----------------------------------------------------------------------
def compare_topologies(keras_model, variant: Variant) -> list:
    """Vergleicht Keras-Ausgabeformen mit der Akida-Variante.

    Der Sinn: das Keras-Modell koennte unbemerkt eine andere Rastergroesse
    erzeugen als die gepruefte Akida-Variante - etwa weil 'same'-Padding bei
    ungeraden Groessen anders rundet. Dann waere die bestandene
    Kernziel-Pruefung fuer ein anderes Modell erfolgt als das trainierte.
    """
    probleme = []
    form = keras_model.output_shape           # (None, S, S, K)
    erwartet_s = variant.grid
    erwartet_k = variant.head_channels

    if form[1] != erwartet_s or form[2] != erwartet_s:
        probleme.append(
            f"Raster {form[1]}x{form[2]} statt {erwartet_s}x{erwartet_s}")
    if form[3] != erwartet_k:
        probleme.append(f"Kopf {form[3]} Kanaele statt {erwartet_k}")

    return probleme


def summary_text(model) -> str:
    zeilen = []
    model.summary(print_fn=zeilen.append)
    return "\n".join(zeilen)
