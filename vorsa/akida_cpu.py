"""CPU-Ersatz fuer den Silhouetten-Abgleich ohne AKD1500 (SE Inspect A8).

Das ist KEIN Akida und rechnet nicht wie einer. Es bildet nur den kleinen
Ausschnitt der MetaTF-Schnittstelle nach, den `edge_learn.py` im Modus
"silhouette" benutzt: InputData -> FullyConnected (1 Bit), unueberwachtes
Lernen mit Klassenzuordnung, forward als Potentialzaehlung. Im
Silhouettenmodus IST das Neuronenpotential die Zahl der uebereinstimmenden
Bildpunkte zweier binaerer Silhouetten - genau das wird hier in numpy
gezaehlt. Damit laufen Lernen, Erkennen, "Warum?", Hypothesen und Verteiler
auf einem Laptop ohne Karte durch, mit denselben Zahlen wie auf dem Chip,
nur langsamer und ohne jede Aussage ueber Hardware.

Aktiv nur, wenn `edge_learn.py` es ausdruecklich laedt (VORSA_CPU_LERNEN=1
oder synthetischer Start). Die Oberflaeche sagt dann "CPU-Ersatz".
"""
from __future__ import annotations

import time
from typing import List, Optional

import numpy as np

__version__ = "cpu-ersatz-1"


class _Soc:
    def __init__(self):
        self.power_measurement_enabled = False


class Device:
    def __init__(self, nr: int):
        self.nr = nr
        self.soc = _Soc()
        self.desc = f"CPU-Ersatz Karte {nr}"
        self.version = "cpu"

    def __repr__(self):
        return self.desc


_GERAETE: Optional[List[Device]] = None


def devices() -> List[Device]:
    global _GERAETE
    if _GERAETE is None:
        import os
        n = max(1, min(8, int(os.environ.get("VORSA_CPU_KARTEN", "2"))))
        _GERAETE = [Device(i) for i in range(n)]
    return list(_GERAETE)


class InputData:
    def __init__(self, input_shape, input_bits: int = 1, name: str = "input"):
        self.input_shape = tuple(input_shape)
        self.name = name
        self.variables = {}

    def get_variable(self, n):
        return self.variables[n]

    def set_variable(self, n, v):
        self.variables[n] = v


class FullyConnected:
    def __init__(self, units: int, weights_bits: int = 1, activation: bool = False,
                 name: str = "fc", **_):
        self.units = int(units)
        self.name = name
        self.weights: Optional[np.ndarray] = None       # (units, D) 0/1
        self.belegt: Optional[np.ndarray] = None        # (units,) bool

    def get_variable(self, n):
        if n == "weights":
            return self.weights
        raise KeyError(n)

    def set_variable(self, n, v):
        if n == "weights":
            self.weights = np.asarray(v)


class AkidaUnsupervised:
    def __init__(self, num_weights: int, num_classes: int = 1,
                 learning_competition: float = 0.0, **_):
        self.num_weights = int(num_weights)
        self.num_classes = int(num_classes)
        self.learning_competition = learning_competition


class Model:
    """Nur InputData + FullyConnected. forward: Ueberlappungszaehlung."""

    def __init__(self, pfad: Optional[str] = None):
        self.layers: list = []
        self.device: Optional[Device] = None
        self._opt: Optional[AkidaUnsupervised] = None
        self._D = 0
        if pfad:
            self._laden(pfad)

    # -- Aufbau --------------------------------------------------------
    def add(self, layer):
        if isinstance(layer, InputData):
            self._D = int(np.prod(layer.input_shape))
        elif isinstance(layer, FullyConnected):
            if not self._D:
                raise RuntimeError("InputData zuerst")
            layer.weights = np.zeros((layer.units, self._D), np.uint8)
            layer.belegt = np.zeros(layer.units, bool)
        else:
            raise NotImplementedError(
                f"CPU-Ersatz kennt nur InputData/FullyConnected, nicht {type(layer).__name__}")
        self.layers.append(layer)

    def map(self, device, hw_only: bool = True):
        self.device = device

    def compile(self, optimizer=None, **_):
        self._opt = optimizer

    def summary(self):
        return f"CPU-Ersatz: {len(self.layers)} Schichten, D={self._D}"

    @property
    def _fc(self) -> FullyConnected:
        for l in self.layers:
            if isinstance(l, FullyConnected):
                return l
        raise RuntimeError("keine Lernschicht")

    # -- Lernen --------------------------------------------------------
    def fit(self, X, y):
        """Je Klasse units/num_classes Neuronen. Jedes Beispiel wird ein
        Neuron; ist die Klasse voll, verschmilzt es mit dem aehnlichsten
        Neuron (Mehrheit der Bits) - so bleibt die Kapazitaet ehrlich."""
        fc = self._fc
        opt = self._opt or AkidaUnsupervised(num_weights=8, num_classes=1)
        C = max(1, opt.num_classes)
        je = fc.units // C
        Xb = (np.asarray(X).reshape(len(X), -1) > 0).astype(np.uint8)
        if Xb.shape[1] != self._D:
            raise ValueError(f"Eingang {Xb.shape[1]} statt {self._D}")
        y = np.asarray(y).astype(int)
        for xb, k in zip(Xb, y):
            lo, hi = k * je, (k + 1) * je
            frei = np.where(~fc.belegt[lo:hi])[0]
            if len(frei):
                j = lo + int(frei[0])
                fc.weights[j] = xb
                fc.belegt[j] = True
            else:
                pots = fc.weights[lo:hi].astype(np.int32) @ xb.astype(np.int32)
                j = lo + int(np.argmax(pots))
                # Verschmelzen: Bits, die beide haben, bleiben; neue Bits
                # kommen dazu, wenn das Neuron noch "duenn" ist.
                alt = fc.weights[j].astype(np.int32)
                fc.weights[j] = ((alt + xb) >= 1).astype(np.uint8) if alt.sum() < opt.num_weights \
                    else ((alt + xb) >= 2).astype(np.uint8)
            time.sleep(0.0005)       # 0.5 ms "Chipzeit" je Beispiel - nur Takt
        return self

    # -- Erkennen ------------------------------------------------------
    def forward(self, x):
        fc = self._fc
        xb = (np.asarray(x).reshape(len(x), -1) > 0).astype(np.int32)
        pots = xb @ fc.weights.astype(np.int32).T            # (n, units)
        pots[:, ~fc.belegt] = 0
        return pots.reshape(len(x), 1, 1, fc.units).astype(np.int32)

    predict = forward

    # -- Sichern -------------------------------------------------------
    def save(self, pfad: str):
        fc = self._fc
        inp = self.layers[0]
        np.savez_compressed(pfad, weights=fc.weights, belegt=fc.belegt,
                            units=fc.units, input_shape=np.asarray(inp.input_shape),
                            magie=np.frombuffer(b"VORSA-CPU-ERSATZ", np.uint8))
        # np.savez haengt .npz an, wenn die Endung fehlt - .fbz bleibt .fbz:
        import os
        if not os.path.exists(pfad) and os.path.exists(pfad + ".npz"):
            os.replace(pfad + ".npz", pfad)

    def _laden(self, pfad: str):
        d = np.load(pfad, allow_pickle=False)
        shape = tuple(int(v) for v in d["input_shape"])
        self.add(InputData(input_shape=shape, input_bits=1))
        fc = FullyConnected(units=int(d["units"]), weights_bits=1, activation=False,
                            name="lernschicht")
        self.add(fc)
        fc.weights = d["weights"].astype(np.uint8)
        fc.belegt = d["belegt"].astype(bool)
