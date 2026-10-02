"""VORSA-M3 Modellskelett - ausschliesslich Akida-1.0-kompatible Schichten.

Zweck dieses Moduls: eine Modellvariante *vor* dem Training baubar machen,
damit sofort geprueft werden kann, ob sie das Kernziel erfuellt
(ein AKD1500, eine Hardwaresequenz, ein Hardwaredurchgang).

Die Gewichte sind hier zufaellig. Fuer die Mapping-Pruefung ist das egal:
die Hardware interessiert nur die Topologie, nicht der Inhalt.

Trainiert wird spaeter ueber Keras + cnn2snn/quantizeml. Die Topologie in
`VARIANTS` ist bewusst so gehalten, dass sie sich 1:1 in Keras nachbauen laesst.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from . import config

# Bei jeder inhaltlichen Aenderung hochzaehlen. Das Pruefskript gibt den Wert
# aus, damit sofort sichtbar ist, ob auf dem Zielsystem noch eine alte Fassung
# liegt - eine veraltete Datei sieht in der Ausgabe sonst genauso aus wie ein
# echter Befund.
BUILD = "0.2.0-hwlimits"

try:
    import akida  # type: ignore
    AKIDA_AVAILABLE = True
except Exception:  # pragma: no cover
    akida = None  # type: ignore
    AKIDA_AVAILABLE = False


# Whitelist Akida 1.0 (AKD1000 / AKD1500). Alles ausserhalb davon wuerde beim
# Mapping auf die CPU zurueckfallen und damit das Kernziel verletzen.
ALLOWED_LAYERS = (
    "InputConvolutional",
    "Convolutional",
    "SeparableConvolutional",
    "FullyConnected",
)

# Ausdruecklich nicht verfuegbar auf Akida 1.0 - deshalb kein Maskendekoder:
FORBIDDEN_LAYERS = (
    "Conv2DTranspose",
    "UpSampling2D",
    "Concatenate",
    "BatchNormalization",
)


# ----------------------------------------------------------------------
@dataclass
class LayerSpec:
    kind: str
    filters: int
    kernel: Tuple[int, int] = (3, 3)
    stride: Tuple[int, int] = (1, 1)
    pool: Optional[Tuple[int, int]] = None
    activation: bool = True
    weights_bits: int = 4
    act_bits: int = 4
    name: str = ""


@dataclass
class Variant:
    """Eine Modellvariante nach SPEC.md Abschnitt 5.

    Der Kopf ist ankerfrei: statt fester Formhypothesen je Zelle gibt es M
    gleichwertige, ungebundene Objektausgaenge (Slots) plus drei feldweite
    Werte. Siehe SPEC.md Abschnitt 5.1.
    """

    name: str
    input_shape: Tuple[int, int, int]
    backbone: List[LayerSpec]
    model_cfg: config.ModelConfig = field(default_factory=config.ModelConfig)
    note: str = ""

    # ------------------------------------------------------------------
    @property
    def num_classes(self) -> int:
        return self.model_cfg.num_classes

    @property
    def slots(self) -> int:
        return self.model_cfg.slots

    @property
    def head_channels(self) -> int:
        return self.model_cfg.head_channels

    @property
    def layers(self) -> List[LayerSpec]:
        """Rumpf plus Kopfschicht - das ist das vollstaendige Netz."""
        return self.backbone + [
            LayerSpec(
                kind="Convolutional",
                filters=self.head_channels,
                kernel=(1, 1),
                activation=False,      # lineare Ausgabe, sonst gehen Koordinaten kaputt
                weights_bits=4,
                name="m3_head",
            )
        ]

    @property
    def grid(self) -> int:
        s = self.input_shape[0]
        for l in self.backbone:
            s //= l.stride[0]
            if l.pool:
                s //= l.pool[0]
        return s

    @property
    def cell_px(self) -> float:
        return self.input_shape[0] / max(self.grid, 1)

    def summary(self) -> str:
        m = self.model_cfg
        lines = [f"Variante {self.name}  Eingang {self.input_shape}"]
        for l in self.layers:
            lines.append(
                f"  {l.kind:<24} f={l.filters:<4} k={l.kernel} s={l.stride} "
                f"pool={l.pool} act={l.activation} w{l.weights_bits}/a{l.act_bits}"
            )
        lines.append(
            f"  M3-Kopf: {self.grid}x{self.grid}x{self.head_channels}"
        )
        lines.append(
            f"    = {m.slots} Slots x (8 + {m.num_classes} Klassen) "
            f"+ {m.CELL_EXTRAS} feldweite Werte"
        )
        lines.append(
            f"    Slot: obj, tx, ty, tw, th, sin2t, cos2t, vis, {m.num_classes} Klassen"
        )
        lines.append(
            "    feldweit: local_count, overlap_prob, local_overflow_prob"
        )
        lines.append(f"    Feldgroesse im Bild: {self.cell_px:.0f} px")
        if self.note:
            lines.append(f"  Hinweis: {self.note}")
        return "\n".join(lines)


# ----------------------------------------------------------------------
def _backbone(widths: List[int], first_stride: int = 2,
              pool_stem: bool = True) -> List[LayerSpec]:
    """Gemeinsamer Merkmalsextraktor (Projektbeschreibung 8.1).

    Er laeuft genau einmal ueber das Bild. Bei M3 entsteht dadurch nicht der
    dreifache Rechenaufwand - nur der Kopf wird breiter, der teure Teil bleibt
    einmal vorhanden.

    Stride-2-Faltungen statt Pooling, um Schichten und damit NPs zu sparen.
    """
    out = [
        LayerSpec("InputConvolutional", widths[0], (5, 5), (first_stride, first_stride),
                  pool=(2, 2) if pool_stem else None, weights_bits=8, name="stem")
    ]
    for i, w in enumerate(widths[1:], start=1):
        stride = (2, 2) if i <= 2 else (1, 1)
        out.append(
            LayerSpec("SeparableConvolutional", w, (3, 3), stride, name=f"sep{i}")
        )
    return out


def make_variant(
    name: str,
    widths: List[int],
    input_px: int = 224,
    num_classes: int = 8,
    slots: int = 3,
    pool_stem: bool = True,
    note: str = "",
) -> Variant:
    cfg = config.ModelConfig(num_classes=num_classes, slots=slots,
                             input_size=(input_px, input_px))
    cfg.validate()
    return Variant(
        name=name,
        input_shape=(input_px, input_px, 3),
        backbone=_backbone(widths, pool_stem=pool_stem),
        model_cfg=cfg,
        note=note,
    )


# Nach der Messung vom 2026-08-26 neu geordnet.
#
# Der begrenzende Faktor ist NICHT die Rechenkapazitaet: V2 braucht 5 von 32
# NPs. Begrenzend ist die Eingangsaufloesung, die bei 256 px hart endet.
# Deshalb zielen die neuen Varianten auf ein feineres Raster und mehr
# Merkmalstiefe, nicht auf Sparsamkeit.
VARIANTS: Dict[str, Variant] = {
    # --- gemessene Referenzen -------------------------------------------
    "V2": make_variant("V2-mittel", [16, 32, 64, 128],
                       note="Gemessen: 1 Pass, 5 NPs noetig. Referenz."),
    "V3": make_variant("V3-klein", [16, 32, 64], input_px=160,
                       note="Gemessen: 1 Pass, 4 NPs. Sparvariante."),

    # --- Gegenproben, die scheitern MUESSEN ------------------------------
    "X-gross": make_variant("X-Kopfeingang-512", [64, 128, 256, 512],
                            note="MUSS scheitern: Kopf-Eingang 512 > 256 Kanaele."),
    "X-px320": make_variant("X-Eingang-320px", [16, 32, 64, 128], input_px=320,
                            note="MUSS scheitern: 320 px > 256 px Eingangsgrenze."),

    # --- die eigentlichen Kandidaten, jetzt mit Reserve ------------------
    "V4": make_variant("V4-fein", [32, 64, 128, 256], pool_stem=False,
                       note="Raster 28x28 statt 14x14: Zelle 8 px statt 16 px. "
                            "Fuer kleine Objekte (Schrauben, SD-Karten)."),
    "V5": make_variant("V5-256px", [32, 64, 128, 256], input_px=256,
                       note="Maximale zulaessige Eingangsgroesse, Raster 16x16."),
    "V6": make_variant("V6-256px-fein", [32, 64, 128, 256], input_px=256,
                       pool_stem=False,
                       note="Beides: 256 px und Raster 32x32, Zelle 8 px. "
                            "Der ehrgeizigste Kandidat."),

    # --- Vergleichsprofile fuer die Energiemessung -----------------------
    "V2-M1": make_variant("V2-M1", [16, 32, 64, 128], slots=1,
                          note="Vergleichsprofil ohne lokale Mehrfachbelegung."),
    "V2-M2": make_variant("V2-M2", [16, 32, 64, 128], slots=2,
                          note="Vergleichsprofil M2 (SPEC.md Abschnitt 11)."),
}


# ----------------------------------------------------------------------
def _filtered_kwargs(cls, kwargs: dict) -> dict:
    """Nur die Argumente behalten, die diese MetaTF-Version wirklich kennt.

    Die Signaturen der Akida-Schichten haben sich zwischen Versionen geaendert.
    Statt hart zu scheitern, wird geloggt, was verworfen wurde.
    """
    try:
        sig = inspect.signature(cls.__init__)
        accepted = set(sig.parameters)
    except (TypeError, ValueError):
        return kwargs
    if any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values()):
        return kwargs
    dropped = [k for k in kwargs if k not in accepted]
    if dropped:
        print(f"[model_m3] {cls.__name__}: ignoriere unbekannte Argumente {dropped}")
    return {k: v for k, v in kwargs.items() if k in accepted}


def check_hardware_limits(variant: Variant) -> List[str]:
    """Prueft die auf echter Hardware gemessenen Grenzen - ohne Geraet.

    Spart einen Mappingversuch und sagt genauer, was zu aendern ist. Die Werte
    stehen in config.py und stammen aus Fehlermeldungen des AKD1500, nicht aus
    einer Dokumentation.
    """
    problems: List[str] = []
    px = variant.input_shape[0]
    if px > config.HW_MAX_INPUT_DIM:
        problems.append(
            f"Eingang {px} px > {config.HW_MAX_INPUT_DIM} px "
            "(harte Grenze der Eingangsschicht)"
        )
    stem = variant.backbone[0] if variant.backbone else None
    if stem and stem.filters > config.HW_MAX_STEM_FILTERS:
        problems.append(
            f"Eingangsschicht {stem.filters} Filter > {config.HW_MAX_STEM_FILTERS}"
        )
    if variant.backbone:
        head_in = variant.backbone[-1].filters
        if head_in > config.HW_MAX_HEAD_INPUT_CH:
            problems.append(
                f"Kopf-Eingang {head_in} Kanaele > {config.HW_MAX_HEAD_INPUT_CH} "
                "(passt nicht in ein CNP)"
            )
    return problems


def randomize_variables(model, variant: Variant, seed: int = 0) -> List[str]:
    """Fuellt die Gewichte mit Zufallswerten ungleich null.

    Akida legt neue Schichten mit Nullgewichten an. Die Eingangsschicht (HRC)
    laesst sich so nicht auf Hardware abbilden - das Mapping bricht ab mit
    "All weights in a hrc layer cannot be zeroes".

    Fuer die Kernziel-Pruefung ist der Inhalt der Gewichte belanglos: die
    Hardware interessiert nur die Topologie. Null duerfen sie trotzdem nicht
    sein, sonst prueft man nie das Modell, sondern immer nur diesen Fehler.

    Rueckgabe: Liste der beschriebenen Variablen, zur Kontrolle im Bericht.
    """
    rng = np.random.default_rng(seed)
    touched: List[str] = []

    for layer, spec in zip(model.layers, variant.layers):
        try:
            var_names = list(layer.variables.names)
        except Exception:      # pragma: no cover - API-Unterschiede
            continue

        # Signierter Wertebereich der Quantisierung: 4 Bit -> -7..7, 8 Bit -> -127..127
        limit = max(2 ** (spec.weights_bits - 1) - 1, 1)

        for vn in var_names:
            try:
                cur = np.asarray(layer.get_variable(vn))
            except Exception:  # pragma: no cover
                continue
            if cur.size == 0:
                continue

            if "weight" in vn:
                mag = rng.integers(1, limit + 1, size=cur.shape)    # nie 0
                sign = rng.choice(np.array([-1, 1]), size=cur.shape)
                new = (mag * sign).astype(cur.dtype)
            elif "act_step" in vn and not np.any(cur):
                # Eine Aktivierungsschrittweite von 0 ist kein gueltiger Wert.
                new = np.ones_like(cur)
            else:
                continue

            try:
                layer.set_variable(vn, new)
                touched.append(f"{layer.name}.{vn}{tuple(cur.shape)}")
            except Exception as exc:  # pragma: no cover
                print(f"[model_m3] {layer.name}.{vn} nicht setzbar: {exc}")

    return touched


def build_akida_model(variant: Variant, randomize: bool = True, seed: int = 0):
    """Baut die Variante als natives akida.Model.

    `randomize=True` fuellt die Gewichte mit Zufallswerten ungleich null -
    ohne das schlaegt das Hardware-Mapping der Eingangsschicht fehl.
    """
    if not AKIDA_AVAILABLE:
        raise RuntimeError(
            "MetaTF (Paket 'akida') ist nicht importierbar. "
            "Auf dem Pi: pip install akida"
        )

    model = akida.Model()
    Padding = akida.Padding
    PoolType = akida.PoolType

    for i, spec in enumerate(variant.layers):
        if spec.kind not in ALLOWED_LAYERS:
            raise ValueError(
                f"Schicht '{spec.kind}' steht nicht auf der Akida-1.0-Whitelist "
                f"{ALLOWED_LAYERS}"
            )
        cls = getattr(akida, spec.kind)
        kwargs = dict(
            filters=spec.filters,
            kernel_size=spec.kernel,
            kernel_stride=spec.stride,
            padding=Padding.Same,
            weights_bits=spec.weights_bits,
            activation=spec.activation,
            act_bits=spec.act_bits,
            name=spec.name or f"{spec.kind.lower()}_{i}",
        )
        if spec.pool:
            kwargs.update(
                pool_type=PoolType.Max, pool_size=spec.pool, pool_stride=spec.pool
            )
        if i == 0:
            kwargs["input_shape"] = variant.input_shape

        model.add(cls(**_filtered_kwargs(cls, kwargs)))

    if randomize:
        randomize_variables(model, variant, seed)

    return model


# ----------------------------------------------------------------------
def describe_devices() -> List[dict]:
    """Liest aus, was tatsaechlich angeschlossen ist.

    Wichtig fuer den TODO-Wert AKD1500_NP_BUDGET in config.py: die Zahl 32 ist
    dort eine Annahme. Was der Chip wirklich hat, steht hier.
    """
    if not AKIDA_AVAILABLE:
        return []

    out: List[dict] = []
    try:
        devices = list(akida.devices())
    except Exception as exc:  # pragma: no cover
        # Kein Geraet, sondern ein Fehler. Muss als solcher erkennbar bleiben,
        # sonst zaehlt der Aufrufer den Fehlereintrag als gefundenes Geraet.
        return [{"__fehler__": str(exc)}]

    for i, dev in enumerate(devices):
        info = {"index": i, "desc": str(getattr(dev, "desc", f"dev{i}"))}
        ver = getattr(dev, "version", None)
        if ver is not None:
            info["version"] = str(ver)
        mesh = getattr(dev, "mesh", None)
        nps = getattr(mesh, "nps", None) if mesh is not None else None
        if nps is not None:
            try:
                info["nps"] = len(nps)
            except TypeError:
                info["nps"] = str(nps)
        for attr in ("ip_version", "product_id", "hw_version"):
            val = getattr(dev, attr, None)
            if val is not None:
                info[attr] = str(val)
        out.append(info)
    return out


@dataclass
class MappingReport:
    variant: str
    ok: bool
    checks: List[Tuple[str, bool, str]] = field(default_factory=list)
    # True, wenn die Pruefung an der Umgebung scheiterte (kein MetaTF, kein
    # Geraet) und nicht am Modell. Der Unterschied ist wichtig: ein blockierter
    # Lauf sagt NICHTS ueber die Groesse des Modells aus. Wer ihn als
    # Modellfehler liest, verkleinert grundlos.
    blocked: bool = False
    blocked_reason: str = ""

    def add(self, label: str, passed: bool, detail: str = "") -> None:
        self.checks.append((label, passed, detail))
        if not passed:
            self.ok = False

    def block(self, label: str, detail: str) -> None:
        self.add(label, False, detail)
        self.blocked = True
        self.blocked_reason = detail

    def render(self) -> str:
        lines = [f"--- Mapping-Bericht {self.variant} ---"]
        for label, passed, detail in self.checks:
            mark = "OK  " if passed else "FEHL"
            lines.append(f"  [{mark}] {label}" + (f"  ({detail})" if detail else ""))
        if self.blocked:
            lines.append("  ERGEBNIS: NICHT PRUEFBAR (Umgebung, nicht Modell)")
        else:
            lines.append(f"  ERGEBNIS: {'PASS' if self.ok else 'FAIL'}")
        return "\n".join(lines)


def check_single_pass(variant: Variant, np_budget: int = config.AKD1500_NP_BUDGET) -> MappingReport:
    """Prueft das Kernziel aus SPEC.md Abschnitt 3."""
    rep = MappingReport(variant=variant.name, ok=True)

    if not AKIDA_AVAILABLE:
        rep.block("MetaTF importierbar", "Paket 'akida' fehlt")
        return rep
    rep.add("MetaTF importierbar", True, getattr(akida, "__version__", "?"))

    bad = [l.kind for l in variant.layers if l.kind not in ALLOWED_LAYERS]
    rep.add("nur Akida-1.0-Schichten", not bad, ", ".join(bad))

    limits = check_hardware_limits(variant)
    rep.add("gemessene Hardwaregrenzen", not limits, "; ".join(limits))

    try:
        model = build_akida_model(variant, randomize=False)
    except Exception as exc:
        rep.add("Modell baubar", False, str(exc))
        return rep
    rep.add("Modell baubar", True, f"{len(model.layers)} Schichten")

    touched = randomize_variables(model, variant)
    rep.add("Gewichte ungleich null", bool(touched),
            f"{len(touched)} Variablen gesetzt" if touched
            else "keine Variable beschreibbar - Mapping wird scheitern")

    try:
        devices = list(akida.devices())
    except Exception as exc:
        rep.block("Geraet gefunden", str(exc))
        return rep

    if not devices:
        rep.block("Geraet gefunden", "akida.devices() ist leer")
        return rep
    dev = devices[0]
    rep.add("Geraet gefunden", True, f"{len(devices)} Geraet(e), nutze {getattr(dev, 'desc', 'dev0')}")

    try:
        model.map(dev, hw_only=True, mode=akida.MapMode.AllNps)
    except Exception as exc:
        rep.add("map(hw_only=True)", False, str(exc))
        return rep
    rep.add("map(hw_only=True)", True, "keine Schicht auf CPU ausgelagert")

    seqs = list(getattr(model, "sequences", []))
    rep.add("genau eine Hardwaresequenz", len(seqs) == 1, f"{len(seqs)} Sequenz(en)")

    # Der eigentliche Kernzielpunkt. Eine Sequenz kann mehrere Passes
    # enthalten - dann laeuft das Bild mehrfach durch den Chip. Wer nur die
    # Sequenzen zaehlt, uebersieht genau das (Modus HwPr braucht z.B. 2 Passes).
    passes = _count_passes(model)
    if passes is None:
        rep.add("genau ein Hardwaredurchgang", False, "Passzahl nicht auslesbar")
    else:
        rep.add("genau ein Hardwaredurchgang", passes == 1, f"{passes} Pass(es)")

    if seqs:
        backend = str(getattr(seqs[0], "backend", "?"))
        rep.add("Sequenz laeuft auf Hardware",
                "Hardware" in backend or "HW" in backend, backend)

    nps = _summary_nps(model)
    if nps is not None:
        rep.add("NP-Belegung (AllNps)", nps <= np_budget, f"{nps} / {np_budget} NPs")

    # Zweite Messung im sparsamen Modus: erst sie zeigt den echten Bedarf.
    # Im Modus AllNps verteilt der Mapper absichtlich auf moeglichst viele NPs,
    # deshalb sagt die Zahl von oben nichts ueber die verbleibende Reserve.
    try:
        model.map(dev, hw_only=True, mode=akida.MapMode.Minimal)
        need = _summary_nps(model)
        if need is not None:
            rep.add("Bedarf (Minimal)", True,
                    f"{need} NPs noetig, {np_budget - need} frei")
    except Exception as exc:
        rep.add("Bedarf (Minimal)", False, str(exc))

    return rep


def _count_passes(model) -> Optional[int]:
    try:
        return sum(len(s.passes) for s in model.sequences)
    except Exception:  # pragma: no cover
        return None


def _summary_nps(model) -> Optional[int]:
    """Liest die NP-Zahl aus der Mapping-Zusammenfassung."""
    import contextlib
    import io
    import re

    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            model.summary()
    except Exception:  # pragma: no cover
        return None
    m = re.search(r"\[\d+, \d+, \d+\]\s+\[[^\]]+\]\s+(\d+)\s+(\d+)\s+(\d+)",
                  buf.getvalue())
    return int(m.group(3)) if m else None


def _count_nps(model) -> Optional[int]:
    """Versucht, die belegten Neural Processors aus dem Modell zu lesen."""
    for attr in ("nps", "num_nps"):
        val = getattr(model, attr, None)
        if isinstance(val, int):
            return val
        if val is not None:
            try:
                return len(val)
            except TypeError:
                pass
    total = 0
    found = False
    for seq in getattr(model, "sequences", []):
        for prog in getattr(seq, "passes", []) or []:
            for layer in getattr(prog, "layers", []) or []:
                mapping = getattr(layer, "mapping", None)
                nps = getattr(mapping, "nps", None) if mapping else None
                if nps is not None:
                    total += len(nps)
                    found = True
    return total if found else None
