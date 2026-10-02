"""VORSA-M3 - Visual Overlap-Resilient Sparse Architecture.

Objektdetektor fuer BrainChip AKD1500, Steuerung durch Raspberry Pi 5.
Siehe SPEC.md fuer Anforderungen und Abnahmekriterien.

Die Untermodule werden erst beim Zugriff geladen (PEP 562). Grund: die
Kernziel-Pruefung (model_m3, config) braucht nur numpy und akida. Wuerde das
Paket beim Import alles mitziehen, koennte man auf einem Pi ohne OpenCV nicht
einmal pruefen, ob das Modell in einen Hardwaredurchgang passt.
"""
import importlib
from typing import TYPE_CHECKING

__version__ = "0.1.0"

_SUBMODULES = (
    "akida_pool",      # akida (optional)
    "assignment",      # numpy
    "augment",         # cv2
    "bench",           # numpy, cv2, akida (optional)
    "calibration",     # cv2
    "config",          # -
    "crops",           # cv2
    "dataset_build",   # cv2
    "edge_learn",      # cv2, akida (optional)
    "jobs",            # -
    "train_job",       # tensorflow (nur zum Trainieren)
    "detection",       # cv2
    "fitting",         # cv2
    "keras_model",     # tensorflow + cnn2snn (nur zum Trainieren)
    "losses",          # tensorflow (nur zum Trainieren)
    "model_m3",        # akida (optional)
    "normalisieren",   # cv2
    "overlay",         # cv2
    "pipeline",        # cv2
    "postprocess",     # numpy
    "segmentation",    # cv2
    "synth",           # cv2
    "synth_objects",   # cv2
    "tracking",        # numpy
)

__all__ = list(_SUBMODULES)


def __getattr__(name: str):
    if name in _SUBMODULES:
        module = importlib.import_module(f".{name}", __name__)
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} hat kein Attribut {name!r}")


def __dir__():
    return sorted(set(globals()) | set(_SUBMODULES))


if TYPE_CHECKING:  # nur fuer Typpruefer, zur Laufzeit ohne Wirkung
    from . import (  # noqa: F401
        akida_pool, assignment, calibration, config, crops, detection, fitting,
        model_m3, overlay, pipeline, postprocess, segmentation, synth, tracking,
    )
