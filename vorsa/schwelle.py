"""Auto-Schwelle aus dem Testsatz (SE Inspect 1.1-B).

Rein rechnerisch: aus den Ist-Ergebnissen je Testszene (Name + Konfidenz je
Teil) und den Soll-Werten wird fuer jede Schwelle ausgezaehlt, wie oft die
Anlage
  falsch-sicher waere   (benannt, aber falsch)      -> soll ~0 sein
  richtig benennt       (einzeln liegende Teile)
  Unbekanntes erkennt   (Fremdteile als "unbekannt")
und daraus die kleinste Schwelle vorgeschlagen, bei der falsch-sicher hoechstens
1 % der Teilurteile ausmacht und dabei die meisten Treffer bleiben
(1.9.70: vorher 0,5 % ohne Blick auf die Treffer).

Die Ist-Ergebnisse liefert der Server (Testlauf) oder eval_testsatz.py.
Ein Teil: (name, konfidenz); "<unbekannt>" / "<negativ>" fuer nicht benannte.
"""
from __future__ import annotations

from collections import Counter
from typing import List, Optional

UNBEKANNT_NAMEN = {"unbekannt", "unknown", "fremd", "fremdteil", "?"}
ZIEL_FALSCH_SICHER = 0.01      # hoechstens 1 % der Teilurteile falsch-sicher
MIN_TREFFER = 0.70             # darunter ist die Schwelle kein Ziel, sondern ein Kompromiss


def ist_aus_erkennung(je_objekt: list, negativ: set) -> list:
    ist = []
    for o in je_objekt or []:
        name = str(o.get("name") or "")
        konf = float(o.get("anteil") or o.get("konfidenz") or 0.0)
        if o.get("unbekannt") or o.get("unklar") or name in ("unklar", "unbekanntes Teil", ""):
            ist.append(("<unbekannt>", konf))
        elif name in negativ:
            ist.append(("<negativ>", konf))
        else:
            ist.append((name, konf))
    return ist


def auswerten(ergebnisse: List[dict], schw: float) -> dict:
    """ergebnisse: [{"soll": [...], "ist": [(name, konf), ...]}, ...]"""
    fs = fs_bezug = 0
    q2_ok = q2_n = q3_ok = q3_n = q4_ok = q4_n = leer_ok = leer_n = 0
    unb_bekannt = 0
    for e in ergebnisse:
        soll = list(e.get("soll") or [])
        ist = [tuple(x) for x in e.get("ist") or []]
        soll_namen = [x for x in soll if x.lower() not in UNBEKANNT_NAMEN]
        soll_unb = [x for x in soll if x.lower() in UNBEKANNT_NAMEN]
        ben = [n for n, k in ist if not n.startswith("<") and k >= schw]
        fs_bezug += len(ist)
        fs += sum(1 for n in ben if n not in soll_namen)
        ist_namen = [n if (not n.startswith("<") and k >= schw) else "<unbekannt>" for n, k in ist]
        if not soll:
            leer_n += 1
            leer_ok += int(not ben)
        elif soll_unb and not soll_namen:
            q3_n += 1
            q3_ok += int(not ben and len(ist) >= 1)
        elif len(soll_namen) == 1 and not soll_unb:
            q2_n += 1
            q2_ok += int(Counter(ist_namen) == Counter(soll_namen))
            unb_bekannt += int(not ben)
        else:
            q4_n += 1
            q4_ok += int(Counter(ist_namen) == Counter(soll_namen + ["<unbekannt>"] * len(soll_unb)))
    r = lambda a, b: (a / b) if b else None
    return {"schwelle": round(schw, 2), "falsch_sicher": fs, "bezug": fs_bezug, "falsch_sicher_rate": r(fs, fs_bezug) or 0.0,
            "treffer_einzeln": [q2_ok, q2_n], "unbekannt_erkannt": [q3_ok, q3_n], "ueberlappung": [q4_ok, q4_n],
            "leer": [leer_ok, leer_n], "bekannt_als_unbekannt": [unb_bekannt, q2_n]}


def _rate(a) -> Optional[float]:
    return (a[0] / a[1]) if a and a[1] else None


def kurve(ergebnisse: List[dict], von=0.30, bis=0.95, schritt=0.05) -> dict:
    """Kurve 30-95 % plus Vorschlag (1.9.70, neue Regel).

    Vorher: kleinste Schwelle mit <= 0,5 % falsch-sicher - egal, wie viele
    richtige Teile dabei durchfallen. Auf dem Pi ergab das 96 %, und fast
    nichts wurde mehr benannt (2026-10-04). Jetzt:
      1. Unter den Schwellen mit hoechstens ZIEL_FALSCH_SICHER die mit den
         meisten Treffern (bei Gleichstand die kleinere).
      2. Liefert die weniger als MIN_TREFFER Treffer (oder gibt es keine),
         ist das Ziel nicht erreichbar: dann die beste ABWAEGUNG
         Treffer - 3 x falsch-sicher, deutlich als Kompromiss gekennzeichnet.
    """
    n = int(round((bis - von) / schritt)) + 1
    punkte = [auswerten(ergebnisse, round(von + i * schritt, 2)) for i in range(n)]
    kand = []
    for sw in [x / 100 for x in range(int(round(von * 100)), 100)]:
        p = auswerten(ergebnisse, sw)
        kand.append((round(sw, 2), p, _rate(p["treffer_einzeln"])))
    vorschlag: Optional[float] = None
    ziel_erreicht = False
    machbar = [k for k in kand if k[1]["falsch_sicher_rate"] <= ZIEL_FALSCH_SICHER]
    if machbar:
        best = max(machbar, key=lambda k: ((k[2] if k[2] is not None else 1.0), -k[0]))
        if best[2] is None or best[2] >= MIN_TREFFER:
            vorschlag, ziel_erreicht = best[0], True
    if vorschlag is None and kand:
        best = max(kand, key=lambda k: ((k[2] or 0.0) - 3.0 * k[1]["falsch_sicher_rate"], -k[0]))
        vorschlag = best[0]
    vp = auswerten(ergebnisse, vorschlag) if vorschlag is not None else None
    hinweise = []
    if len(ergebnisse) < 20:
        hinweise.append(f"Nur {len(ergebnisse)} Szenen – der Vorschlag ist grob. Ab etwa 50 Szenen (mit Fremdteilen) wird er belastbar.")
    elif not any(e.get("soll") and all(s.lower() in UNBEKANNT_NAMEN for s in e["soll"]) for e in ergebnisse):
        hinweise.append("Keine Fremdteil-Szenen im Testsatz – ob die Anlage Unbekanntes erkennt, ist so nicht geprüft.")
    if vp is not None and not ziel_erreicht:
        tr = _rate(vp["treffer_einzeln"])
        hinweise.append(
            "Keine Schwelle erreicht beides – viele Treffer UND kaum Falschbenennungen. Der Vorschlag ist ein Kompromiss"
            + (f" ({round(tr * 100)} % Treffer, {vp['falsch_sicher_rate'] * 100:.1f} % falsch-sicher)." if tr is not None else ".")
            + " Besser wird es nur durch bessere Trennung: Leerbild neu, mehr Lernfotos in verschiedenen Lagen, Störteile als Hintergrund lernen.")
    return {"szenen": len(ergebnisse), "punkte": punkte, "vorschlag": vorschlag,
            "vorschlag_punkt": vp, "ziel_erreicht": ziel_erreicht,
            "ziel_falsch_sicher": ZIEL_FALSCH_SICHER, "min_treffer": MIN_TREFFER,
            "hinweis": " ".join(hinweise), "hinweise": hinweise}


# ---- Kalibrierung je Objekt (1.9.70) ------------------------------------
# Die Sicherheit ist je Objekt verschieden hoch: ein fast rechteckiger Umriss
# (SD-Karte) erreicht selbst richtig erkannt nur ~0,6, ein markanter (Inbus-
# schluessel) ~0,9. Eine gemeinsame Schwelle passt dann fuer keins von beiden.
# Aus dem Testsatz (echte Szenen, nicht die Lernfotos - die kennt der Chip
# auswendig) wird je Objekt die typische Sicherheit RICHTIGER Treffer
# bestimmt; angezeigt wird danach  roh / typisch x 0,9  (hoechstens 1).
# Ein typischer richtiger Treffer steht damit bei jedem Objekt bei ~90 %.
KALIB_ZIEL = 0.9
KALIB_MIN_SZENEN = 3


def kalibrierung_aus(ergebnisse: List[dict]) -> dict:
    """{name: typische rohe Sicherheit} aus Einzelszenen, die richtig benannt
    wurden (genau ein Teil, Name = Soll). Mindestens KALIB_MIN_SZENEN je Objekt."""
    werte: dict = {}
    for e in ergebnisse:
        soll = [x for x in (e.get("soll") or []) if x.lower() not in UNBEKANNT_NAMEN]
        ist = [tuple(x) for x in e.get("ist") or []]
        if len(e.get("soll") or []) == 1 and len(soll) == 1 and len(ist) == 1 and ist[0][0] == soll[0]:
            werte.setdefault(soll[0], []).append(float(ist[0][1]))
    aus = {}
    for n, v in werte.items():
        if len(v) >= KALIB_MIN_SZENEN:
            v = sorted(v)
            m = v[len(v) // 2] if len(v) % 2 else (v[len(v) // 2 - 1] + v[len(v) // 2]) / 2
            aus[n] = round(min(1.0, max(0.3, m)), 3)
    return aus


def kalibriere_wert(name: str, roh: float, kal: dict) -> float:
    r = (kal or {}).get(name)
    return min(1.0, float(roh) / r * KALIB_ZIEL) if r else float(roh)


def kalibriert(ergebnisse: List[dict], kal: dict, unbekannt_ab: float = 0.0) -> List[dict]:
    """Ist-Werte umrechnen; was danach unter unbekannt_ab liegt, wird
    "<unbekannt>" - so wie es die Anlage mit dieser Kalibrierung melden wuerde."""
    aus = []
    for e in ergebnisse:
        ist = []
        for n, k in (e.get("ist") or []):
            if str(n).startswith("<"):
                ist.append((n, k))
                continue
            c = kalibriere_wert(n, k, kal)
            ist.append(("<unbekannt>", c) if c < unbekannt_ab else (n, c))
        aus.append({**e, "ist": ist})
    return aus
