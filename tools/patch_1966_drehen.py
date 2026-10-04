#!/usr/bin/env python3
"""1.9.66: Drehknopf in der Zoomleiste + Bilddrehung bleibt nach Neustart.

Die Drehung gab es schon (/api/drehen, Knopf nur im Einrichten-Block), sie ging
aber beim Neustart verloren - bei schraeg montierter Kamera stimmte dann die
Lage der Lernfotos nicht mehr. Jetzt: drehung.json im Datenordner, Winkel im
/api/state, Knopf neben 1:1 (im Pruefen gesperrt: die Lage gilt fuer Lernen
und Pruefen gemeinsam). Idempotent."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "vorsa/web/static/index.html"
S = ROOT / "vorsa/web/server.py"
E = ROOT / "vorsa/web/static/sprache_en.js"
h = H.read_text(encoding="utf-8")
s = S.read_text(encoding="utf-8")
e = E.read_text(encoding="utf-8")
if "zoomDrehen" in h:
    print("schon angewendet"); raise SystemExit(0)


def ers(text, alt, neu):
    assert text.count(alt) == 1, (alt[:70], text.count(alt))
    return text.replace(alt, neu)


s = ers(s, 'BUILD = "1.9.65-selbstlernen"', 'BUILD = "1.9.66-drehen"')
# laden beim Start
s = ers(s, "        self._pruef_einst_laden()\n", """        self._pruef_einst_laden()
        # 1.9.66: Bilddrehung ueberlebt den Neustart (montierte Kamera).
        self.drehung = 0
        try:
            _dw = int(json.loads((Path(self.zustand.ordner) / "drehung.json").read_text(encoding="utf-8")).get("drehung", 0))
            self.drehung = _dw if _dw in (0, 90, 180, 270) else 0
        except Exception:
            pass
""")
# speichern
s = ers(s, """                verarbeitung.linie.speichern(zustand.ordner)
                print(f"  Bilddrehung: {verarbeitung.drehung} Grad \"""", """                verarbeitung.linie.speichern(zustand.ordner)
                try:
                    (Path(zustand.ordner) / "drehung.json").write_text(
                        json.dumps({"drehung": verarbeitung.drehung}), encoding="utf-8")
                except Exception:
                    pass
                print(f"  Bilddrehung: {verarbeitung.drehung} Grad \"""")
# im Zustand
s = ers(s, """                d["profil"] = getattr(verarbeitung, "profil", "linie")\n""",
        """                d["profil"] = getattr(verarbeitung, "profil", "linie")
                d["drehung"] = int(getattr(verarbeitung, "drehung", 0) or 0)\n""")

# Knopf
h = ers(h, """      <button id="zoomNull" title="Zoom zur&uuml;cksetzen (auch Doppelklick aufs Bild)">1:1</button>
    </div>""", """      <button id="zoomNull" title="Zoom zur&uuml;cksetzen (auch Doppelklick aufs Bild)">1:1</button>
      <span class="zl-trenn" aria-hidden="true"></span>
      <button id="zoomDrehen" data-tat="drehen" title="Bild 90° drehen" aria-label="Bild 90° drehen"><svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/></svg><span id="zoomDrehWert"></span></button>
    </div>""")
h = ers(h, """  #zoomLeiste.aktiv { border-color:var(--akzent); }""", """  #zoomLeiste.aktiv { border-color:var(--akzent); }
  #zoomLeiste .zl-trenn { width:1px; height:16px; background:rgba(255,255,255,.18); margin:0 3px; }
  #zoomLeiste #zoomDrehen { width:auto; min-width:30px; padding:0 7px; display:inline-flex; align-items:center; gap:4px; font-size:11px; }
  #zoomLeiste #zoomDrehen:disabled { opacity:.4; cursor:default; background:transparent; }
  #zoomLeiste #zoomDrehen.gedreht { color:var(--akzent); }""")
# Klick: sofort Rueckmeldung, Winkel merken
h = ers(h, """    try { await hole("/api/drehen", {}); } catch (e) {}
    return;""", """    if (MODUS === "betreiben") return;
    el.disabled = true;
    try { const r = await hole("/api/drehen", {}); if (r && r.drehung != null && Z) Z.drehung = r.drehung; } catch (e) {}
    el.disabled = false; drehKnopfMalen();
    return;""")
# Zustand malen (im opsSync, wo auch die Reiter nachgefuehrt werden)
h = ers(h, """  $("opsPaneTabs").querySelectorAll("button").forEach(b => {
    b.setAttribute("aria-pressed", String(b.dataset.opsPane === OPS_PANE));
  });""", """  $("opsPaneTabs").querySelectorAll("button").forEach(b => {
    b.setAttribute("aria-pressed", String(b.dataset.opsPane === OPS_PANE));
  });
  drehKnopfMalen();""")
h = ers(h, "/* TESTSATZ (A6, 1.9.45): Pruefszenen mit Soll-Werten sammeln. */", """/* 1.9.66: Drehknopf in der Zoomleiste */
function drehKnopfMalen() {
  const b = $("zoomDrehen"); if (!b) return;
  const d = (Z && Z.drehung) || 0, pruefen = MODUS === "betreiben";
  b.disabled = pruefen;
  b.classList.toggle("gedreht", !!d);
  const w = $("zoomDrehWert"), t = d ? d + "°" : "";
  if (w.textContent !== t) w.textContent = t;
  const titel = pruefen ? "Drehen nur in Einrichten oder Anlernen – die Lage gilt für Lernen und Prüfen"
    : d ? `Bild 90° drehen (jetzt ${d}°)` : "Bild 90° drehen";
  if (b.title !== titel) { b.title = titel; b.setAttribute("aria-label", titel); }
}
/* TESTSATZ (A6, 1.9.45): Pruefszenen mit Soll-Werten sammeln. */""")

e = ers(e, "if (window.spracheNachladen) window.spracheNachladen();", """/* ---- Nachtrag 20 (1.9.66 Drehknopf) ---- */
Object.assign(window.SPRACHEN.en, {
  "Bild 90° drehen": "Rotate image 90°", "Bild 90° drehen (jetzt {}°)": "Rotate image 90° (now {}°)",
  "Drehen nur in Einrichten oder Anlernen – die Lage gilt für Lernen und Prüfen": "Rotate only in Set up or Teach – the orientation applies to teaching and inspection"
});

if (window.spracheNachladen) window.spracheNachladen();""")

H.write_text(h, encoding="utf-8")
S.write_text(s, encoding="utf-8")
E.write_text(e, encoding="utf-8")
print("ok 1.9.66")
