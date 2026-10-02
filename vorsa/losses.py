"""Verlustfunktion des M3-Kopfes (SPEC.md Abschnitt 7).

Eingaben:
  y_pred (B, S, S, K)  Rohausgabe des Netzes, unverarbeitete Logits
  y_true (B, S, S, K)  Zielwerte, bereits dekodiert - aus assignment.match_batch
  mask   (B, S, S, M)  1.0 wo einem Slot ein Objekt zugeordnet wurde

Zwei Punkte entscheiden hier ueber Erfolg oder Misserfolg:

1. Leere Slots lernen ausschliesslich "kein Objekt". Wuerde man auch ihre
   Koordinaten bestrafen, zoege es alle Slots zum selben Mittelwert - die
   lokale Mehrfachbelegung braeche zusammen, obwohl die Architektur stimmt.

2. Das Verhaeltnis leerer zu belegter Slots betraegt bei V6 etwa 1:500. Ohne
   Gewichtung ist "ueberall kein Objekt" die bequemste Loesung fuer das Netz,
   und der Verlust faellt dabei ueberzeugend. Deshalb fokale Gewichtung.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from . import config


def _tf():
    try:
        import tensorflow as tf
        return tf
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("TensorFlow fehlt:  pip install tensorflow-cpu") from exc


@dataclass
class LossWeights:
    """Gewichte der Verlustanteile. Startwerte, keine Zielwerte."""

    obj: float = 1.0
    pos: float = 5.0        # hoch: Lagefehler sind das Hauptkriterium (A5)
    size: float = 2.0
    angle: float = 1.0
    vis: float = 0.5
    cls: float = 1.0
    count: float = 0.2
    overlap: float = 0.5
    overflow: float = 0.5

    # Fokale Gewichtung gegen das Ungleichgewicht
    focal_gamma: float = 2.0
    focal_alpha: float = 0.75   # Gewicht der positiven Slots


def _smooth_l1(tf, diff, beta: float = 0.1):
    absd = tf.abs(diff)
    return tf.where(absd < beta, 0.5 * absd * absd / beta, absd - 0.5 * beta)


def vorsa_loss(
    y_true,
    y_pred,
    mask,
    model_cfg: config.ModelConfig = config.MODEL,
    w: LossWeights = LossWeights(),
) -> Dict:
    """Gibt ein dict mit 'total' und allen Einzelanteilen zurueck.

    Die Einzelanteile sind nicht Dekoration: wenn das Training nicht
    konvergiert, sagt erst ihre Entwicklung, welcher Teil klemmt. Ein
    Gesamtverlust allein zeigt das nie.
    """
    tf = _tf()
    M, C = model_cfg.slots, model_cfg.num_classes
    P = model_cfg.per_slot
    E = M * P

    y_true = tf.cast(y_true, tf.float32)
    y_pred = tf.cast(y_pred, tf.float32)
    mask = tf.cast(mask, tf.float32)

    formen = tf.shape(y_pred)
    B, S = formen[0], formen[1]

    pt = tf.reshape(y_true[..., :E], (B, S, S, M, P))
    pp = tf.reshape(y_pred[..., :E], (B, S, S, M, P))

    n_pos = tf.maximum(tf.reduce_sum(mask), 1.0)

    # ------------------------------------------------------------------
    # Objektheit - ueber ALLE Slots, fokal gewichtet
    # ------------------------------------------------------------------
    obj_ziel = pt[..., 0]
    obj_logit = pp[..., 0]
    obj_p = tf.sigmoid(obj_logit)

    bce = tf.nn.sigmoid_cross_entropy_with_logits(labels=obj_ziel, logits=obj_logit)
    p_t = obj_ziel * obj_p + (1.0 - obj_ziel) * (1.0 - obj_p)
    alpha_t = obj_ziel * w.focal_alpha + (1.0 - obj_ziel) * (1.0 - w.focal_alpha)
    focal = alpha_t * tf.pow(1.0 - p_t, w.focal_gamma) * bce
    l_obj = tf.reduce_sum(focal) / n_pos

    # ------------------------------------------------------------------
    # Ab hier nur zugeordnete Slots
    # ------------------------------------------------------------------
    def mittel(x):
        return tf.reduce_sum(x * mask) / n_pos

    # Lage: Vorhersage in denselben Wertebereich bringen wie das Ziel
    ox = 2.0 * tf.sigmoid(pp[..., 1]) - 0.5
    oy = 2.0 * tf.sigmoid(pp[..., 2]) - 0.5
    l_pos = mittel(_smooth_l1(tf, ox - pt[..., 1]) + _smooth_l1(tf, oy - pt[..., 2]))

    # Groesse im Logarithmus: ein Fehler von 4 px wiegt bei einem kleinen
    # Objekt schwerer als bei einem grossen - genau das soll er auch.
    eps = 1e-6
    pw = tf.math.log(tf.maximum(tf.sigmoid(pp[..., 3]), eps))
    ph = tf.math.log(tf.maximum(tf.sigmoid(pp[..., 4]), eps))
    tw = tf.math.log(tf.maximum(pt[..., 3], eps))
    th = tf.math.log(tf.maximum(pt[..., 4], eps))
    l_size = mittel(_smooth_l1(tf, pw - tw) + _smooth_l1(tf, ph - th))

    # Winkel ueber das normierte Paar (sin 2t, cos 2t).
    # Runde Objekte tragen im Ziel (0, 0) und werden hier ausgeblendet -
    # ihnen einen Winkel beizubringen hiesse, Rauschen zu lernen.
    ps, pc = pp[..., 5], pp[..., 6]
    pn = tf.sqrt(tf.maximum(ps * ps + pc * pc, eps))
    ts, tc = pt[..., 5], pt[..., 6]
    tn = tf.sqrt(tf.maximum(ts * ts + tc * tc, eps))
    winkel_gilt = tf.cast(tn > 0.5, tf.float32)
    dot = (ps * ts + pc * tc) / (pn * tn)
    l_angle = tf.reduce_sum((1.0 - dot) * mask * winkel_gilt) / tf.maximum(
        tf.reduce_sum(mask * winkel_gilt), 1.0)

    # Sichtbarkeit
    l_vis = mittel(tf.abs(tf.sigmoid(pp[..., 7]) - pt[..., 7]))

    # Klasse
    cls_ce = tf.nn.softmax_cross_entropy_with_logits(
        labels=pt[..., 8:8 + C], logits=pp[..., 8:8 + C])
    l_cls = mittel(cls_ce)

    # ------------------------------------------------------------------
    # Feldweite Werte - ueber alle Felder
    # ------------------------------------------------------------------
    n_felder = tf.cast(B * S * S, tf.float32)

    count_p = tf.nn.softplus(y_pred[..., E + 0])
    l_count = tf.reduce_sum(tf.abs(count_p - y_true[..., E + 0])) / n_felder

    l_overlap = tf.reduce_sum(tf.nn.sigmoid_cross_entropy_with_logits(
        labels=y_true[..., E + 1], logits=y_pred[..., E + 1])) / n_felder
    l_overflow = tf.reduce_sum(tf.nn.sigmoid_cross_entropy_with_logits(
        labels=y_true[..., E + 2], logits=y_pred[..., E + 2])) / n_felder

    total = (w.obj * l_obj + w.pos * l_pos + w.size * l_size
             + w.angle * l_angle + w.vis * l_vis + w.cls * l_cls
             + w.count * l_count + w.overlap * l_overlap
             + w.overflow * l_overflow)

    return {
        "total": total,
        "obj": l_obj,
        "pos": l_pos,
        "size": l_size,
        "angle": l_angle,
        "vis": l_vis,
        "cls": l_cls,
        "count": l_count,
        "overlap": l_overlap,
        "overflow": l_overflow,
        "n_pos": n_pos,
    }


def format_losses(d: Dict) -> str:
    """Einzeilige Ausgabe fuer die Trainingsschleife."""
    teile = []
    for k in ("total", "obj", "pos", "size", "angle", "vis", "cls",
              "count", "overlap", "overflow"):
        if k in d:
            teile.append(f"{k}={float(d[k]):.4f}")
    return "  ".join(teile)
