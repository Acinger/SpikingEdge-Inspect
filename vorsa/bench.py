"""Messreihen: Pi gegen AKD1500.

Was hier gemessen wird und was nicht - das ist der wichtigere Teil:

  GEMESSEN   Zeit je Bild auf der CPU des Pi (geometrische Strecke)
             Zeit je Bild auf dem AKD1500 (ein Durchgang, echte Hardware)
             belegte NPs, Sequenzen und Passes der gemappten Variante
             Bildrate der Kamera

  NICHT GEMESSEN, SONDERN GERECHNET
             Energie je 1000 Objekte. Der Pi hat keinen Stromsensor, und die
             AKD1500-Karte meldet ihre Aufnahme nicht. Die Zahl entsteht aus
             gemessener Zeit mal ANGENOMMENER Leistung. Die Annahme steht in
             jedem Ergebnis mit dabei; wer ein Leistungsmessgeraet an der
             Steckdose hat, traegt seinen Wert ein und bekommt eine belastbare
             Zahl.

Eine gerechnete Energiezahl als Messwert auszugeben waere der bequemste Weg,
sich das Kernziel schoenzurechnen.
"""
from __future__ import annotations

import platform
import time
from typing import Dict, List, Optional, Sequence

import numpy as np

# ----------------------------------------------------------------------
# Leistungswerte aus veroeffentlichten Messungen, nicht geschaetzt.
# Jede Zahl mit Quelle - wer sie ersetzen will, weiss dann, wogegen.
#
#   Pi 5 Leerlauf   2,6 W  Tom's Hardware, mit Kuehlkoerper, 50 Grad
#                   3,0 W  raspberry.tips 2026, kopflos, nur WLAN
#                   3,6 W  mit Ethernet, HDMI und USB-Geraeten
#   Pi 5 Last       6,8 W  Tom's Hardware, stress-Test, 59,3 Grad
#                   8,8 W  Spitzenwert bei Volllast
#   AKD1500       < 0,3 W  BrainChip, PCIe-Betrieb, Serienstand 2026
#                 < 0,2 W  im seriellen Betrieb
#
# Genommen wird bewusst der jeweils UNGUENSTIGERE Wert fuer die Karte und
# der guenstigere fuer den Pi. Wer den eigenen Ansatz schoenrechnet, merkt
# den Fehler erst, wenn jemand nachmisst.
WATT_PI5_LAST = 6.8        # Tom's Hardware, stress-Test
WATT_PI5_RUHE = 2.6        # Tom's Hardware, Leerlauf mit Kuehlkoerper
WATT_AKD1500 = 0.3         # BrainChip, PCIe-Betrieb (Obergrenze)

QUELLEN = {
    "pi_last": "Tom's Hardware, Pi-5-Test: 6,8 W im stress-Test bei 59,3 Grad",
    "pi_ruhe": "Tom's Hardware: 2,6 W im Leerlauf mit Kuehlkoerper",
    "akd": "BrainChip: unter 300 mW im PCIe-Betrieb",
}


def _statistik(zeiten_ms: Sequence[float]) -> dict:
    a = np.asarray(zeiten_ms, dtype=float)
    if a.size == 0:
        return {"n": 0}
    return {
        "n": int(a.size),
        "ms_mittel": round(float(a.mean()), 2),
        "ms_median": round(float(np.median(a)), 2),
        "ms_min": round(float(a.min()), 2),
        "ms_max": round(float(a.max()), 2),
        # Der 95er ist die Zahl fuer eine Taktzeit. Ein Mittelwert verbirgt
        # genau die Ausreisser, an denen eine Anlage spaeter stehenbleibt.
        "ms_p95": round(float(np.percentile(a, 95)), 2),
        "bilder_je_s": round(1000.0 / max(float(a.mean()), 1e-6), 1),
    }


def energie_je_1000(ms_je_bild: float, watt: float,
                    objekte_je_bild: float) -> Optional[float]:
    """Wh je 1000 erkannte Objekte. None, wenn nichts erkannt wurde.

    Das Kernmass des Projekts. Es haengt an drei Groessen, und die dritte
    wird gern vergessen: ein Weg, der schnell ist, aber die Haelfte der
    Objekte uebersieht, verbraucht je Objekt doppelt so viel.
    """
    if objekte_je_bild <= 0 or ms_je_bild <= 0:
        return None
    stunden_je_bild = ms_je_bild / 1000.0 / 3600.0
    wh_je_bild = watt * stunden_je_bild
    return round(wh_je_bild / objekte_je_bild * 1000.0, 6)


# ----------------------------------------------------------------------
def messe_pi_strecke(bilder: Sequence[np.ndarray], lauf=None) -> dict:
    """Geometrische Erkennung auf der CPU des Pi."""
    from . import config
    from .calibration import identity
    from .fitting import detections_from_masks
    from .segmentation import segment_parts

    zeiten: List[float] = []
    objekte: List[int] = []
    for i, bild in enumerate(bilder):
        if lauf is not None and lauf.abbruch_gewuenscht:
            break
        h, w = bild.shape[:2]
        cal = identity((w, h), px_per_mm=1.0)
        t0 = time.perf_counter()
        teile, maske, _ = segment_parts(bild, cal.px_per_mm, config.DEFAULT.seg)
        dets = detections_from_masks(teile, maske, cal.px_per_mm, config.DEFAULT.seg)
        zeiten.append((time.perf_counter() - t0) * 1000.0)
        objekte.append(len(dets))
        if lauf is not None:
            lauf.setze_phase("Pi-Strecke", i + 1, len(bilder))

    st = _statistik(zeiten)
    st["objekte_je_bild"] = round(float(np.mean(objekte)), 2) if objekte else 0.0
    st["objekte_gesamt"] = int(np.sum(objekte)) if objekte else 0
    return st


def messe_akida(variante: str, bilder: Sequence[np.ndarray],
                lauf=None) -> dict:
    """Ein Durchgang auf dem AKD1500, mit den Hardwarezahlen dazu."""
    try:
        import akida
    except Exception as exc:
        return {"ok": False, "grund": f"MetaTF nicht importierbar: {exc}"}

    from .model_m3 import VARIANTS, build_akida_model

    if variante not in VARIANTS:
        return {"ok": False, "grund": f"Variante {variante} unbekannt"}
    var = VARIANTS[variante]

    geraete = akida.devices()
    if not geraete:
        return {"ok": False, "grund": "kein AKD1500 gefunden"}
    geraet = geraete[0]

    if lauf is not None:
        lauf.setze_phase("Modell bauen und mappen", 0, len(bilder))
    modell = build_akida_model(var, randomize=True)
    try:
        modell.map(geraet, hw_only=True, mode=akida.MapMode.AllNps)
    except Exception as exc:
        return {"ok": False, "grund": f"Mapping: {str(exc)[:140]}"}

    sequenzen = len(modell.sequences)
    passes = sum(len(s.passes) for s in modell.sequences)
    try:
        belegt = sum(len(p.layers) for s in modell.sequences for p in s.passes)
    except Exception:
        belegt = None

    # Leistungsmessung der Karte einschalten, wenn sie es kann. Damit wird
    # aus einer gerechneten Zahl eine gemessene - fuer die Kartenseite
    # jedenfalls. Der Pi hat nichts Vergleichbares.
    leistung_an = False
    try:
        geraet.soc.power_measurement_enabled = True
        leistung_an = bool(geraet.soc.power_measurement_enabled)
    except Exception:
        leistung_an = False

    px = var.input_shape[0]
    import cv2
    vorbereitet = [
        np.ascontiguousarray(cv2.resize(b, (px, px),
                                        interpolation=cv2.INTER_AREA).astype(np.uint8))
        for b in bilder]

    # Erster Durchgang zaehlt nicht: er enthaelt einmalige Vorbereitung im
    # Treiber. Ihn mitzumitteln wuerde die Karte schlechter aussehen lassen,
    # als sie ist.
    if vorbereitet:
        modell.forward(vorbereitet[0][None, ...])

    zeiten: List[float] = []
    for i, b in enumerate(vorbereitet):
        if lauf is not None and lauf.abbruch_gewuenscht:
            break
        t0 = time.perf_counter()
        modell.forward(b[None, ...])
        zeiten.append((time.perf_counter() - t0) * 1000.0)
        if lauf is not None:
            lauf.setze_phase("AKD1500", i + 1, len(vorbereitet))

    st = _statistik(zeiten)
    st.update({
        "ok": True, "variante": var.name, "eingang_px": px,
        "sequenzen": sequenzen, "passes": passes, "schichten_gemappt": belegt,
        "kernziel_erfuellt": sequenzen == 1 and passes == 1,
    })

    # Zusaetzlich die von der Karte selbst gemeldete Zeit, wenn vorhanden.
    # Sie enthaelt den Bustransfer nicht - der Unterschied zur Wanduhr ist
    # genau der Preis, den der Pi fuer das Hin- und Herschieben zahlt.
    try:
        stat = modell.statistics
        st["karte_ms"] = round(float(getattr(stat, "inference_time", 0.0)), 3) or None
    except Exception:
        st["karte_ms"] = None

    st.update(_leistung_auslesen(geraet, leistung_an))
    return st


def _leistung_auslesen(geraet, war_an: bool) -> dict:
    """Liest die Leistungsmessung der Karte aus, falls vorhanden.

    Stand MetaTF 2.19.3 unterstuetzt BrainChip die Messung NUR auf dem
    AKD1000 - auf dem AKD1500 ist geraet.soc None ("support will be added
    later"). Fehlt der Sensor, wird das gesagt und nicht durch eine
    Schaetzung ersetzt.
    """
    if not war_an:
        return {"mw_gemessen": None,
                "leistung_hinweis": (
                    "AKD1500 ohne auslesbaren Leistungssensor - BrainChip "
                    "unterstuetzt die Messung derzeit nur auf dem AKD1000")}
    try:
        messer = geraet.soc.power_meter
        werte = [float(e.power) for e in messer.events()]
        boden = float(getattr(messer, "floor", 0.0))
    except Exception as exc:
        return {"mw_gemessen": None,
                "leistung_hinweis": f"Leistungsmesser: {str(exc)[:80]}"}
    if not werte:
        return {"mw_gemessen": None,
                "leistung_hinweis": "Leistungsmesser lieferte keine Werte"}
    return {
        "mw_gemessen": round(float(np.mean(werte)), 1),
        "mw_max": round(float(np.max(werte)), 1),
        "mw_ruhe": round(boden, 1),
        "leistung_proben": len(werte),
        "leistung_hinweis": "von der Karte gemessen",
    }


def messe_kamera(quelle, anzahl: int = 60, lauf=None) -> dict:
    zeiten: List[float] = []
    for i in range(anzahl):
        if lauf is not None and lauf.abbruch_gewuenscht:
            break
        t0 = time.perf_counter()
        quelle.lies()
        zeiten.append((time.perf_counter() - t0) * 1000.0)
        if lauf is not None:
            lauf.setze_phase("Kamera", i + 1, anzahl)
    st = _statistik(zeiten)
    st["synthetisch"] = bool(getattr(quelle, "synthetisch", False))
    return st


# ----------------------------------------------------------------------
def system_info() -> dict:
    info = {"maschine": platform.machine(), "system": platform.platform(),
            "python": platform.python_version()}
    try:
        with open("/proc/device-tree/model", "rb") as fh:
            info["modell"] = fh.read().decode("utf-8", "ignore").strip("\x00")
    except Exception:
        pass
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as fh:
            info["kerne"] = sum(1 for z in fh if z.startswith("processor"))
    except Exception:
        pass
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", encoding="utf-8") as fh:
            info["cpu_grad"] = round(int(fh.read().strip()) / 1000.0, 1)
    except Exception:
        pass
    return info


def baue_arbeit(verarbeitung, variante: str = "", bilder: int = 30,
                watt_pi: float = WATT_PI5_LAST, watt_akd: float = WATT_AKD1500):
    """Erzeugt die Arbeitsfunktion einer Messreihe fuer `jobs.Lauf`."""
    from . import config

    def arbeit(lauf) -> dict:
        lauf.melde(f"Messreihe ueber {bilder} Bilder")
        info = system_info()
        lauf.melde(f"{info.get('modell', info.get('maschine'))} "
                   f"| {info.get('kerne', '?')} Kerne "
                   f"| {info.get('cpu_grad', '?')} Grad")

        # Immer dieselben Bilder fuer beide Wege. Zwei Messungen auf
        # verschiedenen Bildern vergleichen nicht die Wege, sondern die Bilder.
        lauf.setze_phase("Bilder sammeln", 0, bilder)
        proben = []
        for i in range(bilder):
            if lauf.abbruch_gewuenscht:
                break
            b = verarbeitung.hole_ausschnitt()
            if b is not None:
                proben.append(b)
            lauf.setze_phase("Bilder sammeln", i + 1, bilder)
            time.sleep(0.04)
        if not proben:
            return {"ok": False, "grund": "keine Bilder von der Quelle"}
        lauf.melde(f"{len(proben)} Ausschnitte, "
                   f"{proben[0].shape[1]}x{proben[0].shape[0]} px")

        kamera = messe_kamera(verarbeitung.quelle, min(30, bilder), lauf)
        lauf.melde(f"Kamera: {kamera.get('bilder_je_s', 0)} Bilder/s"
                   + (" (synthetisch)" if kamera.get("synthetisch") else ""))

        pi = messe_pi_strecke(proben, lauf)
        lauf.melde(f"Pi-Strecke: {pi.get('ms_mittel')} ms je Bild, "
                   f"{pi.get('objekte_je_bild')} Objekte je Bild")

        lauf.setze_phase("AKD1500")
        akd = messe_akida(variante or config.ACTIVE_VARIANT, proben, lauf)
        if akd.get("ok"):
            lauf.melde(f"AKD1500: {akd.get('ms_mittel')} ms je Bild, "
                       f"{akd.get('sequenzen')} Sequenz(en), "
                       f"{akd.get('passes')} Pass(es)")
            if not akd.get("kernziel_erfuellt"):
                lauf.melde("ACHTUNG: nicht ein Durchgang - Kernziel verletzt.")
        else:
            lauf.melde(f"AKD1500 nicht gemessen: {akd.get('grund')}")

        v = vergleich(pi, akd, watt_pi, watt_akd)
        if v.get("faktor_zeit"):
            lauf.melde(f"Zeit: Karte ist Faktor {v['faktor_zeit']} schneller")
        if v.get("pi_wh_je_1000"):
            lauf.melde(f"Energie (gerechnet): Pi {v['pi_wh_je_1000']} Wh, "
                       f"Karte {v.get('akd_wh_je_1000')} Wh je 1000 Objekte")

        return {"ok": True, "system": info, "kamera": kamera, "pi": pi,
                "akd": akd, "vergleich": v,
                "bilder": len(proben), "zeit": time.strftime("%Y-%m-%d %H:%M")}

    return arbeit


def kernziel_pruefen(varianten: Sequence[str] = ()) -> dict:
    """Prueft, welche Varianten in einen Durchgang auf einen AKD1500 passen.

    Dieselbe Pruefung wie tools/check_single_pass.py, nur aus der Oberflaeche
    heraus. Ein PASS bedeutet nur dann etwas, wenn auch FAILs vorkommen -
    deshalb werden die absichtlich zu grossen Gegenproben mitgeprueft.
    """
    try:
        from .model_m3 import VARIANTS, check_single_pass
    except Exception as exc:
        return {"ok": False, "grund": f"model_m3 nicht ladbar: {exc}"}

    namen = list(varianten) or list(VARIANTS)
    zeilen = []
    for n in namen:
        if n not in VARIANTS:
            continue
        try:
            r = check_single_pass(VARIANTS[n])
            d = {"variante": r.variant, "ok": bool(r.ok),
                 "blockiert": bool(r.blocked), "grund": r.blocked_reason,
                 "pruefungen": [{"was": w, "ok": bool(o), "detail": t}
                                for w, o, t in r.checks]}
        except Exception as exc:
            d = {"variante": n, "ok": False, "blockiert": True,
                 "grund": str(exc)[:140], "pruefungen": []}
        zeilen.append(d)

    # Ein blockierter Lauf sagt NICHTS ueber die Groesse des Modells aus.
    # Ihn als Fehlschlag zu zaehlen waere der direkte Weg zu einem grundlos
    # verkleinerten Modell.
    echte = [z for z in zeilen if not z.get("blockiert")]
    bestanden = sum(1 for z in echte if z.get("ok"))
    return {"ok": True, "zeilen": zeilen, "bestanden": bestanden,
            "geprueft": len(echte), "blockiert": len(zeilen) - len(echte),
            # Ein PASS bedeutet nur etwas, wenn auch etwas durchfallen kann.
            "aussagekraeftig": 0 < bestanden < len(echte)}


def vergleich(pi: dict, akd: dict, watt_pi: float = WATT_PI5_LAST,
              watt_akd: float = WATT_AKD1500) -> dict:
    """Stellt beide Wege nebeneinander - mit offengelegten Annahmen."""
    objekte = float(pi.get("objekte_je_bild", 0) or 0)
    pi_ms = float(pi.get("ms_mittel", 0) or 0)
    akd_ms = float(akd.get("ms_mittel", 0) or 0) if akd.get("ok") else 0.0

    # Hat die Karte selbst gemessen, gilt ihr Wert - nicht der Datenblattwert.
    gemessen_mw = akd.get("mw_gemessen")
    if gemessen_mw:
        watt_akd = float(gemessen_mw) / 1000.0
        karte_herkunft = f"von der Karte gemessen ({gemessen_mw:.0f} mW)"
    else:
        karte_herkunft = QUELLEN["akd"]

    aus = {
        "objekte_je_bild": objekte,
        "watt_pi": watt_pi,
        "watt_akd": round(watt_akd, 3),
        "watt_akd_gemessen": bool(gemessen_mw),
        "quelle_pi": QUELLEN["pi_last"],
        "quelle_ruhe": QUELLEN["pi_ruhe"],
        "quelle_akd": karte_herkunft,
        "pi_wh_je_1000": energie_je_1000(pi_ms, watt_pi, objekte),
        # Fuer den Akida-Weg zaehlt die Leistung BEIDER Teile: die Karte
        # rechnet, aber der Pi haelt sie am Leben und schiebt die Bilder.
        # Nur die Karte zu zaehlen waere die verbreitetste Art, sich diese
        # Zahl schoenzurechnen.
        "akd_wh_je_1000": (energie_je_1000(akd_ms, watt_akd + WATT_PI5_RUHE, objekte)
                           if akd_ms else None),
        "pi_ruhe_mitgezaehlt": WATT_PI5_RUHE,
    }
    if pi_ms and akd_ms:
        aus["faktor_zeit"] = round(pi_ms / akd_ms, 2)
    if aus["pi_wh_je_1000"] and aus["akd_wh_je_1000"]:
        aus["faktor_energie"] = round(
            aus["pi_wh_je_1000"] / aus["akd_wh_je_1000"], 2)
    aus["hinweis"] = (
        "Zeiten gemessen. Leistung der Karte "
        + ("gemessen. " if gemessen_mw else "aus der Herstellerangabe. ")
        + "Leistung des Pi aus veroeffentlichten Tests - er hat keinen "
          "Stromsensor. Beim Akida-Weg ist der Ruhebedarf des Pi mitgezaehlt, "
          "denn ohne ihn laeuft die Karte nicht.")
    return aus
