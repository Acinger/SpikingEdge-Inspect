#!/usr/bin/env python3
"""A3 — Hypothesen im Server (Build 1.9.41).

Im Profil stationaer entscheidet vorsa.hypothesen statt _verschmelze:
Stuecke je zusammenhaengender Flaeche -> Hypothesen -> Chip bewertet alle
Auftraege je Runde ueber `bewerte_viele` (Vorbereitung fuer den
Kartenverteiler, bis dahin sequentiell) -> beste Deutung. Diagnose in
bereich_info["hypothesen"]. Profil linie bleibt bei _verschmelze.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
S = ROOT / "vorsa" / "web" / "server.py"


def ers(text, alt, neu, n=1):
    k = text.count(alt)
    if k != n:
        raise SystemExit(f"FEHLER: {k}x statt {n}x gefunden:\n{alt[:200]}")
    return text.replace(alt, neu)


srv = S.read_text(encoding="utf-8")
if "1.9.41-hypothesen" in srv:
    print("server.py: schon gepatcht")
    raise SystemExit(0)
srv = ers(srv, 'BUILD = "1.9.40-mehrbild"', 'BUILD = "1.9.41-hypothesen"')
srv = ers(srv, '''        dets = self._verschmelze(dets, maske, bewerte=bewerte)

        # LOCH-ANKER''', '''        if (getattr(self, "profil", "linie") == "stationaer"
                and bewerte is not None and maske is not None):
            dets = self._hypothesen_entscheiden(dets, maske, bewerte, cal.px_per_mm)
        else:
            dets = self._verschmelze(dets, maske, bewerte=bewerte)

        # LOCH-ANKER''')
srv = ers(srv, '''    @staticmethod
    def _verschmelze(dets, maske=None, deckung: float = 0.45, bewerte=None):''', '''    def _hypothesen_entscheiden(self, dets, maske, bewerte, px_per_mm: float):
        """HYPOTHESEN (SE Inspect A3, 1.9.41): je zusammenhaengender
        Flaeche alle Deutungen aufzaehlen, Chip bewertet rundenweise alle
        Auftraege auf einmal (bewerte_viele), beste Deutung gewinnt."""
        import cv2 as _cv2
        from .. import hypothesen as HY
        dets = list(dets)
        if len(dets) < 2:
            self._diag_hypothesen = {"flaechen": 0}
            return dets
        binaer = (np.asarray(maske) > 0).astype(np.uint8)
        _n, lab = _cv2.connectedComponents(binaer)
        H, W = lab.shape

        def flaechen_id(d):
            if d.contour is None:
                px, py = int(d.box.cx), int(d.box.cy)
                return int(lab[py, px]) if 0 <= px < W and 0 <= py < H else 0
            p = d.contour.reshape(-1, 2)
            werte = lab[np.clip(p[:, 1], 0, H - 1), np.clip(p[:, 0], 0, W - 1)]
            werte = werte[werte > 0]
            return int(np.bincount(werte).argmax()) if len(werte) else 0

        gruppen = {}
        for d in dets:
            gruppen.setdefault(flaechen_id(d), []).append(d)
        verteiler = getattr(self, "verteiler", None)
        bewerte_viele = (verteiler.bewerte_viele(bewerte) if verteiler is not None
                         else HY.sequentiell(bewerte))
        neu, diag = [], []
        for fid, gruppe in gruppen.items():
            if fid == 0 or len(gruppe) == 1:
                neu.extend(gruppe)
                continue
            try:
                blob = (lab == fid).astype(np.uint8) * 255
                best, info = HY.hypothesen_waehlen(
                    gruppe, lab.shape, bewerte_viele, px_per_mm, blob_maske=blob,
                    nominal=False)
                if best is None:
                    neu.extend(gruppe)
                    continue
                neu.extend(HY.hypothese_zu_detektionen(best, gruppe))
                diag.append({"stuecke": len(gruppe), "gewaehlt": best.name,
                             "teile": len(best.teile), "score": round(best.score, 3),
                             "runden": info.get("runden"), "auftraege": info.get("auftraege"),
                             "top": info.get("scores", [])[:3]})
            except Exception as exc:
                neu.extend(gruppe)
                diag.append({"stuecke": len(gruppe), "fehler": str(exc)[:80]})
        self._diag_hypothesen = {"flaechen": len(diag), "entscheidungen": diag}
        return neu

    @staticmethod
    def _verschmelze(dets, maske=None, deckung: float = 0.45, bewerte=None):''')
# Diagnose in bereich_info
srv = ers(srv, '''        self.zustand.bereich_info["segmente"] = seg
        self._diag_segmente = seg''', '''        self.zustand.bereich_info["segmente"] = seg
        self._diag_segmente = seg
        if getattr(self, "_diag_hypothesen", None):
            self.zustand.bereich_info["hypothesen"] = self._diag_hypothesen''')
S.write_text(srv, encoding="utf-8")
print("server.py gepatcht")
