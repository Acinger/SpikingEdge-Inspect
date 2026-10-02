"""Zentrale Konfiguration VORSA-M3.

Zwei getrennte Bereiche:

  * MODELL - gilt fuer VORSA-M3 allgemein, kennt keine Produktart.
  * BEISPIELANWENDUNG - Foerderband mit PU-Kunstlederteilen. Diese Werte sind
    Anwendungswissen und gehen ausdruecklich NICHT in die Modellarchitektur
    ein (SPEC.md Abschnitt 14).

Alle Zahlen, die vor Ort gemessen werden muessen, sind mit TODO markiert.
Nichts hier ist geraten-und-versteckt: wenn ein Wert unsicher ist, steht es dabei.
"""
from dataclasses import dataclass, field
from typing import Sequence, Tuple


# ==========================================================================
# MODELL
# ==========================================================================
@dataclass
class ModelConfig:
    """Bauparameter des VORSA-Kopfes. Die Klassenanzahl ist frei waehlbar."""

    # Auf 8 festgelegt: die Anwendung ist spezialisiert, ein Betrieb weiss,
    # was er produziert. Mehr Klassen kosten Kopfbreite ohne Nutzen.
    num_classes: int = 8
    slots: int = 3                  # M: lokale Kapazitaet (M1 / M2 / M3)

    # Variante V6, am 2026-08-26 auf Hardware bestaetigt: ein AKD1500,
    # eine Sequenz, ein Pass, 18 von 32 NPs. 256 px ist die harte Obergrenze
    # der Eingangsschicht - mehr geht auf diesem Chip nicht.
    input_size: Tuple[int, int] = (256, 256)

    # Kanaele je Slot: obj, tx, ty, tw, th, sin2t, cos2t, vis + Klassen
    SLOT_FIELDS: int = 8
    # Feldweite Zusatzkanaele: local_count, overlap_prob, overflow_prob
    CELL_EXTRAS: int = 3

    @property
    def per_slot(self) -> int:
        return self.SLOT_FIELDS + self.num_classes

    @property
    def head_channels(self) -> int:
        return self.slots * self.per_slot + self.CELL_EXTRAS

    def validate(self) -> None:
        if not 1 <= self.num_classes <= 20:
            raise ValueError(
                f"num_classes={self.num_classes} liegt ausserhalb des geplanten "
                "Bereichs 1..20 (SPEC.md Abschnitt 5)."
            )
        if not 1 <= self.slots <= 4:
            raise ValueError(
                f"slots={self.slots}: die exakte Zuordnung ueber Permutationen "
                "ist nur bis M=4 vorgesehen (SPEC.md Abschnitt 6)."
            )


MODEL = ModelConfig()

# Rueckwaertskompatible Kurznamen
NUM_CLASSES = MODEL.num_classes
SLOTS = MODEL.slots
MODEL_INPUT: Tuple[int, int, int] = (*MODEL.input_size, 3)

# Gitterweite des Kopfes. Nicht frei waehlbar: sie ergibt sich aus den Strides
# der Variante. Verbindlich ist Variant.grid in model_m3.py.
GRID = 32                     # V6: 256 px Eingang, Gesamtstride 8, Zelle 8 px

# Gewaehlte Variante nach der Hardwaremessung. Siehe SPEC.md Abschnitt 3a.
ACTIVE_VARIANT = "V6"
FALLBACK_VARIANT = "V5"       # gleiches Bild, groeberes Raster, 588 statt 3072 Slots

# Am Geraet PCIe/AKD1500/16MB/0 (BC.A1.003.009, IpVersion.v1) ausgelesen.
AKD1500_NP_BUDGET = 32

# --------------------------------------------------------------------------
# Am 2026-08-26 auf echter Hardware gemessene Grenzen (MetaTF 2.19.3)
# --------------------------------------------------------------------------
# Diese Werte stehen in keiner Dokumentation so konkret. Sie stammen aus
# Fehlermeldungen von model.map(hw_only=True) und sind deshalb belastbarer
# als jede Schaetzung - aber auch an diese eine Firmwareversion gebunden.
HW_MAX_INPUT_DIM = 256      # "maximum input second dimension size is 256"
HW_MAX_STEM_FILTERS = 64    # "num_neurons should be set between 1 and 64"
HW_MAX_HEAD_INPUT_CH = 256  # 512 -> "Filter size is too big to fit in a CNP"

# Gemessener NP-Bedarf im Modus Minimal (nicht die Belegung im Modus AllNps):
#   V2-mittel  5 NPs   V3-klein  4 NPs   V1-gross  6 NPs
# Der Chip hat 32. Kapazitaet ist also nicht der begrenzende Faktor,
# die Eingangsaufloesung ist es.
#
# MapMode-Befund:
#   Minimal  wenigste NPs, 1 Pass   -> Massstab fuer den echten Bedarf
#   AllNps   verteilt breit, 1 Pass -> Standard, hoeherer Durchsatz
#   HwPr     47 NPs, 2 PASSES       -> verletzt das Kernziel, nicht verwenden
FORBIDDEN_MAP_MODES = ("HwPr",)

# Klassenliste der ersten Anwendung. Platzhalter, siehe SPEC.md Abschnitt 15.
CLASS_NAMES: Sequence[str] = (
    "objekt_a", "objekt_b", "objekt_c", "objekt_d",
    "objekt_e", "objekt_f", "objekt_g", "unbekannt",
)


# --------------------------------------------------------------------------
# Schwellwerte des M3-Kopfes
# --------------------------------------------------------------------------
@dataclass
class HeadThresholds:
    obj_thresh: float = 0.25
    # Ab hier meldet das System "hier sind mehr Objekte als M", statt eine
    # Objektzahl vorzutaeuschen. TODO: empirisch bestimmen.
    overflow_thresh: float = 0.50
    overlap_thresh: float = 0.50
    # Unterhalb dieser Sichtbarkeit gilt ein Objekt als stark verdeckt.
    vis_partial: float = 0.85
    vis_unresolved: float = 0.30


HEAD = HeadThresholds()


# ==========================================================================
# BEISPIELANWENDUNG: Foerderband mit PU-Kunstlederteilen
# --------------------------------------------------------------------------
# Anwendungswissen. Wird von segmentation.py und fitting.py genutzt, nicht
# vom Modell. Fuer eine andere Anwendung wird nur dieser Block ersetzt.
# ==========================================================================
PART_LENGTH_MM = 80.0
PART_WIDTH_MM = 22.0
PART_THICKNESS_MM = 1.2

PART_ASPECT = PART_LENGTH_MM / PART_WIDTH_MM          # ~3.636
PART_AREA_MM2 = PART_LENGTH_MM * PART_WIDTH_MM        # 1760 mm^2

# Zulaessige Abweichung eines Kandidaten von der Sollgeometrie.
AREA_TOLERANCE = 0.25        # +/- 25 % Flaeche
ASPECT_TOLERANCE = 0.30      # +/- 30 % Seitenverhaeltnis


# --------------------------------------------------------------------------
# Kalibrierung / Bildgeometrie
# --------------------------------------------------------------------------
# Aufloesung des entzerrten Bandbildes in Pixel pro Millimeter.
# 4 px/mm -> ein Teil ist 320 x 88 px. Guter Kompromiss aus Kantenschaerfe
# und Rechenlast auf dem Pi 5.
PX_PER_MM = 4.0

# Groesse des entzerrten Bildes in mm (sichtbarer Bandausschnitt).
# TODO: an den realen Kameraausschnitt anpassen.
BOARD_WIDTH_MM = 300.0
BOARD_HEIGHT_MM = 200.0


def mm_to_px(mm: float) -> float:
    return mm * PX_PER_MM


def px_to_mm(px: float) -> float:
    return px / PX_PER_MM


BOARD_SIZE_PX: Tuple[int, int] = (
    int(round(BOARD_WIDTH_MM * PX_PER_MM)),
    int(round(BOARD_HEIGHT_MM * PX_PER_MM)),
)


# --------------------------------------------------------------------------
# Segmentierung (Pi 5 / OpenCV)
# --------------------------------------------------------------------------
@dataclass
class SegmentationParams:
    # Hintergrundtrennung
    blur_ksize: int = 5
    use_adaptive: bool = False          # True bei ungleichmaessiger Ausleuchtung
    otsu_offset: int = 0                # manueller Versatz auf die Otsu-Schwelle
    morph_open_px: int = 3
    morph_close_px: int = 5
    # Farbmaske (2026-09-08): zusaetzlich zur Grau-Schwelle gilt als
    # Vordergrund, was sich FARBLICH vom Band unterscheidet (Lab-Abstand zur
    # Randfarbe). Loest "dunkles Teil auf dunklem Band": eine schwarze SD-
    # Karte auf gruenem Band ist im Grau kaum vom Band zu trennen, Otsu
    # nahm dann nur die weisse Aufschrift als Teil. Farblich ist Schwarz
    # vs. Gruen dagegen eindeutig -> ganze Karte = ein Klumpen.
    farb_maske: bool = True
    farb_min_abstand: float = 12.0      # unter diesem dE: Rauschen/Schatten
    # Kanten-Silhouette (2026-09-19): von Kanten umschlossene Flaechen sind
    # Teil - loest "Aufschrift statt Karte" auch bei gemischtem Rand.
    kanten_fuellung: bool = True
    # Leerbild-Differenz (2026-09-19): Mindestunterschied je Kanal zum
    # gemerkten leeren Band, darunter zaehlt nichts als Teil.
    leer_min_diff: float = 18.0
    # Leerbild aus MEHREREN Bildern (2026-09-19): je Pixel die groesste
    # gesehene Abweichung -> Schwelle = leer_rausch_faktor * Abweichung + 6.
    # Blendflecken flackern (LED, Belichtung) und bekommen so automatisch
    # eine hohe Schwelle, das ruhige Band eine niedrige.
    leer_rausch_faktor: float = 1.5
    # GLANZ (Blendflecken): gesaettigte Pixel (alle Kanaele >= Schwelle)
    # in kleinen Flecken (< Anteil der Bildflaeche) sind Reflexe der
    # Beleuchtung, keine Teile. 0 = aus. Im Leerbild gesaettigte Stellen
    # sind IMMER Band (Ausschlussmaske mit Rand).
    glanz_schwelle: int = 246
    glanz_max_anteil: float = 0.02

    # Flaechenfilter in mm^2, bezogen auf ein Einzelteil
    min_blob_area_frac: float = 0.35    # kleiner -> Schmutz
    max_blob_parts: int = 6             # groesser -> Fehlbelichtung, kein Cluster

    # Watershed
    # Anteil des Maximums der Distanztransformation, ab dem ein Kern als
    # sicherer Vordergrund gilt. Kleiner -> mehr Trennungen, mehr Uebertrennung.
    dt_seed_ratio: float = 0.55
    min_seed_area_frac: float = 0.20

    # Ein Blob wird nur dann zur Watershed-Trennung geschickt, wenn seine
    # Flaeche mindestens so viele Sollteile enthaelt.
    split_trigger_parts: float = 1.6

    # Schwelle fuer die Rechteck-Zerlegung (Fall 2). Niedriger als oben, weil
    # sich ueberlappende Teile weniger Flaeche zeigen als zwei getrennte.
    # Ein Versuch ist folgenlos: die Zerlegung greift nur, wenn sie mindestens
    # zwei Teile mit ausreichender Passgenauigkeit findet.
    decompose_trigger_parts: float = 1.35
    decompose_min_fit_score: float = 0.72
    decompose_max_parts: int = 4


# --------------------------------------------------------------------------
# Detektions-Nachbearbeitung
# --------------------------------------------------------------------------
@dataclass
class NMSParams:
    score_thresh: float = 0.25          # Versuchsreihe: 0.20 / 0.25 / 0.30
    iou_thresh: float = 0.65            # Versuchsreihe: 0.55 / 0.65 / 0.75
    soft: bool = True                   # Soft-NMS statt Hard-NMS
    soft_sigma: float = 0.5
    max_detections: int = 64

    # Objekte aus demselben Rasterfeld, aber verschiedenen Slots, sind
    # konstruktionsbedingt verschiedene Objekte. Sie duerfen einander nie
    # unterdruecken - sonst verliert man genau die Ueberlagerungen, fuer die
    # M3 gebaut wurde. Auf False setzen nur fuer den Vergleich mit YOLO-NMS.
    protect_same_cell: bool = True


# --------------------------------------------------------------------------
# Tracking
# --------------------------------------------------------------------------
@dataclass
class TrackingParams:
    # TODO: Bandgeschwindigkeit messen und hier eintragen.
    belt_speed_mm_s: float = 0.0        # 0 = unbekannt, dann rein positionsbasiert
    max_match_dist_mm: float = 15.0
    max_missed_frames: int = 3
    min_hits_to_confirm: int = 2


# --------------------------------------------------------------------------
# Laufzeit
# --------------------------------------------------------------------------
@dataclass
class RuntimeConfig:
    seg: SegmentationParams = field(default_factory=SegmentationParams)
    nms: NMSParams = field(default_factory=NMSParams)
    track: TrackingParams = field(default_factory=TrackingParams)
    model: ModelConfig = field(default_factory=ModelConfig)
    head: HeadThresholds = field(default_factory=HeadThresholds)

    camera_index: int = 0
    capture_width: int = 1920
    capture_height: int = 1080

    # P1 = Hybrid (4 Chips klassifizieren Crops), P2 = Single-Pass-Detektor
    profile: str = "P1"

    calibration_file: str = "calibration.json"
    model_file: str = ""                # .fbz; leer -> Stub-Klassifikator
    draw_debug: bool = True


DEFAULT = RuntimeConfig()
