#!/usr/bin/env python3
"""1.9.71: M3-Training haengt nicht mehr still bei "Fotos freistellen 0 %".

Befund (Pi, 2026-10-04): 121 Lernfotos x 32 Augmentierungsvarianten = 3 872
Freistellungen (Farbmaske, Kantensilhouette, Glanz) auf 687-px-Bildern, im
Server-Prozess, ohne Fortschrittsmeldung. Das dauerte Dutzende Minuten und
sah aus wie ein Haenger. Dabei sind die Drehvarianten fuer M3 wertlos: die
Szenensynthese (baue_szene) dreht und skaliert jedes Teil ohnehin zufaellig.

  - dataset_build.freistellen_aus_zustand: nur Original + Spiegelungen
    (Haendigkeit bleibt beachtet), Bilder vor dem Freistellen auf max.
    384 px (das Modell sieht 256 px), Fortschritts-Callback je Foto.
  - train_job: Fortschritt "Fotos freistellen i von n" + GESAMT-Fortschritt
    ueber alle Phasen (freistellen 15 %, TF laden 5 %, Training 70 %,
    Quantisieren/Umwandeln 7 %, Chip 3 %).
  - jobs.Lauf: Feld `gesamt` (0..1) in as_dict.
  - Oberflaeche: Fortschrittsbalken mit Prozentzahl, farbig nach Stand
    (blau laeuft, gruen fertig, rot Fehler), in der grossen Zeile unterm
    Bild und im Training-Dialog; unbestimmte Phasen pulsieren.
Idempotent."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "vorsa/dataset_build.py"; T = ROOT / "vorsa/train_job.py"; J = ROOT / "vorsa/jobs.py"
H = ROOT / "vorsa/web/static/index.html"; S = ROOT / "vorsa/web/server.py"; E = ROOT / "vorsa/web/static/sprache_en.js"
d, t, j, h, s, e = (p.read_text(encoding="utf-8") for p in (D, T, J, H, S, E))
if "fortschritt=None" in d:
    print("schon angewendet"); raise SystemExit(0)


def ers(x, a, b, n=1):
    assert x.count(a) == n, (a[:70], x.count(a)); return x.replace(a, b)


s = ers(s, 'BUILD = "1.9.70-kalibrierung"', 'BUILD = "1.9.71-m3fortschritt"')

# ---------------------------------------------------------------- dataset_build
d = ers(d, '''def freistellen_aus_zustand(zustand, mit_varianten: bool = True
                            ) -> Tuple[List[Freigestellt], List[str], List[str]]:
    """Stellt alle gesammelten Fotos frei.

    Rueckgabe: (Teile, Klassennamen in Reihenfolge der Kennung, Warnungen).
    """
    from .assignment import GtObject as _G          # noqa: F401  (Doku)
    from .augment import erzeuge_varianten

    namen: List[str] = []
    teile: List[Freigestellt] = []
    warnungen: List[str] = []

    for idx, k in enumerate(sorted(zustand.klassen.values(), key=lambda x: x.id)):
        namen.append(k.name)
        gefunden = 0
        for datei in k.prototypen:
            roh = zustand.prototyp_bild(datei)
            if roh is None:
                continue
            quellen = [roh]
            if mit_varianten:
                h, w = roh.shape[:2]
                platz = [GtObject(w / 2, h / 2, w * .6, h * .3, 0.0, idx)]
                quellen = [b for _n, b, _o in erzeuge_varianten(roh, platz, k.augment)]
            for b in quellen:''', '''FREISTELL_MAX_PX = 384     # das Modell sieht 256 px - mehr kostet nur Zeit


def freistellen_aus_zustand(zustand, mit_varianten: bool = True,
                            fortschritt=None
                            ) -> Tuple[List[Freigestellt], List[str], List[str]]:
    """Stellt alle gesammelten Fotos frei.

    Rueckgabe: (Teile, Klassennamen in Reihenfolge der Kennung, Warnungen).
    fortschritt(i, n): je Foto, fuer die Anzeige.

    1.9.71: NUR Original + Spiegelungen. Drehvarianten brachten fuer M3
    nichts - baue_szene dreht und skaliert jedes Teil ohnehin zufaellig -
    kosteten aber das 8- bis 32-Fache an Zeit (auf dem Pi Dutzende Minuten
    ohne sichtbaren Fortschritt). Bilder vorher auf FREISTELL_MAX_PX.
    """
    from .assignment import GtObject as _G          # noqa: F401  (Doku)
    from .augment import erzeuge_varianten, AugmentConfig

    namen: List[str] = []
    teile: List[Freigestellt] = []
    warnungen: List[str] = []
    klassen = sorted(zustand.klassen.values(), key=lambda x: x.id)
    n_fotos = sum(len(k.prototypen) for k in klassen)
    i_foto = 0

    for idx, k in enumerate(klassen):
        namen.append(k.name)
        gefunden = 0
        for datei in k.prototypen:
            i_foto += 1
            if fortschritt is not None:
                try:
                    fortschritt(i_foto, n_fotos)
                except Exception:
                    pass
            roh = zustand.prototyp_bild(datei)
            if roh is None:
                continue
            h, w = roh.shape[:2]
            if max(h, w) > FREISTELL_MAX_PX:
                f = FREISTELL_MAX_PX / float(max(h, w))
                roh = cv2.resize(roh, (max(16, int(w * f)), max(16, int(h * f))),
                                 interpolation=cv2.INTER_AREA)
                h, w = roh.shape[:2]
            quellen = [roh]
            if mit_varianten:
                a = k.augment
                nur_spiegel = AugmentConfig(
                    spiegeln_horizontal=bool(getattr(a, "spiegeln_horizontal", True)),
                    spiegeln_vertikal=bool(getattr(a, "spiegeln_vertikal", False)),
                    drehen_90=False, drehen_frei=False,
                    haendigkeit=bool(getattr(a, "haendigkeit", False)))
                platz = [GtObject(w / 2, h / 2, w * .6, h * .3, 0.0, idx)]
                quellen = [b for _n, b, _o in erzeuge_varianten(roh, platz, nur_spiegel)]
            for b in quellen:''')

# ---------------------------------------------------------------- jobs.Lauf
j = ers(j, '''        self.schritt = 0
        self.schritte = 0
        self.ergebnis: dict = {}''', '''        self.schritt = 0
        self.schritte = 0
        self.gesamt: Optional[float] = None     # 1.9.71: Fortschritt ueber alle Phasen
        self.ergebnis: dict = {}''')
j = ers(j, '''    def setze_phase(self, phase: str, schritt: int = 0, schritte: int = 0) -> None:
        self.phase = phase
        if schritte:
            self.schritte = schritte
        self.schritt = schritt
''', '''    def setze_phase(self, phase: str, schritt: int = 0, schritte: int = 0) -> None:
        self.phase = phase
        if schritte:
            self.schritte = schritte
        self.schritt = schritt

    def setze_gesamt(self, anteil: float) -> None:
        try:
            self.gesamt = max(0.0, min(1.0, float(anteil)))
        except Exception:
            pass
''')
j = ers(j, '''            "anteil": round(self.schritt / self.schritte, 3) if self.schritte else 0.0,''',
        '''            "anteil": round(self.schritt / self.schritte, 3) if self.schritte else 0.0,
            "gesamt": (1.0 if self.fertig and self.ok else
                       round(self.gesamt, 3) if self.gesamt is not None else None),''')

# ---------------------------------------------------------------- train_job
PH = '''
# 1.9.71: Gesamtfortschritt ueber die Phasen (Anteil am Gesamtlauf, grob
# nach Dauer auf dem Pi geschaetzt).
PHASEN_GEWICHT = (("Fotos freistellen", 0.15), ("TensorFlow laden", 0.05), ("Modell bauen", 0.02),
                  ("Training", 0.68), ("Quantisieren", 0.04), ("Nach Akida umwandeln", 0.03),
                  ("Auf den AKD1500 legen", 0.03))


def _gesamt(phase: str, anteil: float = 0.0) -> float:
    """Fortschritt 0..1 ueber alle Phasen: abgeschlossene Phasen voll, die
    laufende anteilig. Unbekannte Phasen (z. B. aus dem Unterprozess) werden
    dem Training zugeschlagen."""
    vor = 0.0
    for name, g in PHASEN_GEWICHT:
        if phase.startswith(name):
            return vor + g * max(0.0, min(1.0, anteil))
        vor += g
    # unbekannt: zwischen "TensorFlow laden" und Training
    return 0.22 + 0.68 * max(0.0, min(1.0, anteil))


def _phase_mit_gesamt(lauf, phase: str, schritt: int = 0, schritte: int = 0) -> None:
    lauf.setze_phase(phase, schritt, schritte)
    lauf.setze_gesamt(_gesamt(phase, (schritt / schritte) if schritte else 0.0))

'''
t = ers(t, "def _train_python() -> str:", PH + "def _train_python() -> str:")
# externer Weg
t = ers(t, '''        # --- 1. Fotos freistellen (cv2, laeuft unter numpy<2) ---------
        lauf.setze_phase("Fotos freistellen")
        teile, namen, warnungen = freistellen_aus_zustand(zustand, mit_varianten)''',
'''        # --- 1. Fotos freistellen (cv2, laeuft unter numpy<2) ---------
        _phase_mit_gesamt(lauf, "Fotos freistellen")
        teile, namen, warnungen = freistellen_aus_zustand(
            zustand, mit_varianten,
            fortschritt=lambda i, n: _phase_mit_gesamt(lauf, "Fotos freistellen", i, n))''')
t = ers(t, '''        lauf.setze_phase("Training (getrennte Umgebung)")
        lauf.melde(f"starte {py}")''', '''        _phase_mit_gesamt(lauf, "TensorFlow laden")
        lauf.melde(f"starte {py}")''')
t = ers(t, '''                if zeile.startswith("@PHASE|"):
                    lauf.setze_phase(zeile[7:])
                elif zeile.startswith("@STEP|"):
                    try:
                        _, i, n = zeile.split("|", 2)
                        lauf.setze_phase("Training", int(i), int(n))''', '''                if zeile.startswith("@PHASE|"):
                    _phase_mit_gesamt(lauf, zeile[7:])
                elif zeile.startswith("@STEP|"):
                    try:
                        _, i, n = zeile.split("|", 2)
                        _phase_mit_gesamt(lauf, "Training", int(i), int(n))''')
t = ers(t, '''        if Path(ziel).exists():
            lauf.setze_phase("Auf den AKD1500 legen")''', '''        if Path(ziel).exists():
            _phase_mit_gesamt(lauf, "Auf den AKD1500 legen")''')
# in-process Weg
t = ers(t, '''        lauf.setze_phase("Fotos freistellen")
        lauf.melde(f"Variante {var.name}: {px}x{px}, Raster {grid}x{grid}, "
                   f"Zelle {cell:.0f} px")
        teile, namen, warnungen = freistellen_aus_zustand(zustand, mit_varianten)''',
'''        _phase_mit_gesamt(lauf, "Fotos freistellen")
        lauf.melde(f"Variante {var.name}: {px}x{px}, Raster {grid}x{grid}, "
                   f"Zelle {cell:.0f} px")
        teile, namen, warnungen = freistellen_aus_zustand(
            zustand, mit_varianten,
            fortschritt=lambda i, n: _phase_mit_gesamt(lauf, "Fotos freistellen", i, n))''')
for alt, neu in (('        lauf.setze_phase("TensorFlow laden")', '        _phase_mit_gesamt(lauf, "TensorFlow laden")'),
                 ('        lauf.setze_phase("Modell bauen")', '        _phase_mit_gesamt(lauf, "Modell bauen")'),
                 ('            lauf.setze_phase("Training", schritt, schritte)', '            _phase_mit_gesamt(lauf, "Training", schritt, schritte)'),
                 ('        lauf.setze_phase("Quantisieren")', '        _phase_mit_gesamt(lauf, "Quantisieren")'),
                 ('        lauf.setze_phase("Nach Akida umwandeln")', '        _phase_mit_gesamt(lauf, "Nach Akida umwandeln")'),
                 ('        lauf.setze_phase("Auf den AKD1500 legen")\n        ergebnis = {"ok": True', '        _phase_mit_gesamt(lauf, "Auf den AKD1500 legen")\n        ergebnis = {"ok": True')):
    t = ers(t, alt, neu)

# ---------------------------------------------------------------- Oberflaeche
# grosse Zeile unterm Bild
h = ers(h, '''    $("satz").innerHTML = txt(LAUF.name)
      + `<small>${txt(LAUF.phase)}${LAUF.schritte
          ? ` · Schritt ${LAUF.schritt} von ${LAUF.schritte}` : ""}</small>`;
    $("balken").style.width = Math.round((LAUF.anteil || 0) * 100) + "%";
    return;''', '''    const pz = laufProzent(LAUF);
    $("satz").innerHTML = txt(LAUF.name)
      + `<small>${txt(LAUF.phase)}${LAUF.schritte
          ? ` · Schritt ${LAUF.schritt} von ${LAUF.schritte}` : ""}${pz != null ? ` · <b class="lauf-pz">${pz} %</b>` : ""}</small>`;
    laufBalken($("balken"), LAUF);
    return;''')
h = ers(h, '''/* ---------- grosse Ergebniszeile ---------- */
function zeichneErgebnis() {''', '''/* 1.9.71: Fortschritt eines Laufs - Prozent ueber alle Phasen, Farbe nach Stand */
function laufProzent(l) {
  if (!l) return null;
  if (l.fertig && l.ok) return 100;
  if (l.gesamt != null) return Math.round(l.gesamt * 100);
  return l.schritte ? Math.round((l.anteil || 0) * 100) : null;
}
function laufBalken(el, l) {
  if (!el) return;
  const pz = laufProzent(l);
  const stand = l.fertig ? (l.ok ? "fertig" : "fehler") : (pz == null ? "unbestimmt" : "laeuft");
  const b = el.closest(".balken, .mini-balken") || el.parentNode;
  if (b) { b.classList.remove("lb-laeuft", "lb-fertig", "lb-fehler", "lb-unbestimmt"); b.classList.add("lb-" + stand, "lb-aktiv"); }
  el.style.width = (stand === "unbestimmt" ? 100 : Math.max(1, pz || 0)) + "%";
}
/* ---------- grosse Ergebniszeile ---------- */
function zeichneErgebnis() {''')
# wenn kein Lauf: Klassen wieder weg (sonst bleibt der Balken gruen)
h = ers(h, '''  if (MELDUNG) {
    $("satz").innerHTML = txt(MELDUNG);
    $("balken").style.width = "0%";
    return;
  }''', '''  const balkenBox = $("balken").parentNode;
  if (balkenBox && !(LAUF && LAUF.laeuft)) balkenBox.classList.remove("lb-laeuft", "lb-fertig", "lb-fehler", "lb-unbestimmt", "lb-aktiv");
  if (MELDUNG) {
    $("satz").innerHTML = txt(MELDUNG);
    $("balken").style.width = "0%";
    return;
  }''')
# Training-Dialog
h = ers(h, '''      <div class="kasten">${txt(l.phase)}${l.schritte
        ? ` · Schritt ${l.schritt} von ${l.schritte}` : ""}
        ${l.sekunden ? ` · ${l.sekunden} s` : ""}</div>
      <div class="mini-balken" style="width:100%;height:9px;margin-bottom:12px">
        <i style="width:${l.laeuft && !l.schritte ? 100
          : Math.round((l.anteil || 0) * 100)}%"></i></div>''', '''      <div class="kasten">${txt(l.phase)}${l.schritte
        ? ` · Schritt ${l.schritt} von ${l.schritte}` : ""}
        ${l.sekunden ? ` · ${l.sekunden} s` : ""}${laufProzent(l) != null ? ` · <b class="lauf-pz">${laufProzent(l)} %</b>` : ""}</div>
      <div class="mini-balken lb-aktiv lb-${l.fertig ? (l.ok ? "fertig" : "fehler") : (laufProzent(l) == null ? "unbestimmt" : "laeuft")}" style="width:100%;height:10px;margin-bottom:12px">
        <i style="width:${l.fertig ? 100 : laufProzent(l) == null ? 100 : Math.max(1, laufProzent(l))}%"></i></div>''')
# CSS
h = ers(h, '''.as-ergebnis { font-size:12.5px; margin:6px 0; }''', '''.as-ergebnis { font-size:12.5px; margin:6px 0; }
/* 1.9.71: Fortschrittsbalken eines Laufs - farbig nach Stand */
.lb-aktiv { position:relative; border-radius:4px; overflow:hidden; transition:background .3s; }
#ergebnis .balken.lb-aktiv { height:9px !important; margin-top:12px; background:#1b2733 !important; }
body#opsApp #ergebnis .balken.lb-aktiv { height:9px !important; }
.lb-aktiv i { transition:width .4s ease, background .3s; }
.lb-laeuft i, body#opsApp .lb-laeuft i { background:linear-gradient(90deg,#1d9bf0,#49e7ff) !important; }
.lb-fertig i, body#opsApp .lb-fertig i { background:#22c55e !important; }
.lb-fehler i, body#opsApp .lb-fehler i { background:#ef4444 !important; }
.lb-unbestimmt i, body#opsApp .lb-unbestimmt i { background:repeating-linear-gradient(90deg,#1d9bf0 0 14px,#0d5f93 14px 28px) !important; animation:lbPuls 1.1s linear infinite; }
@keyframes lbPuls { from { background-position:0 0; } to { background-position:28px 0; } }
.lauf-pz { color:var(--akzent); font-weight:700; font-variant-numeric:tabular-nums; }''')

e = ers(e, "if (window.spracheNachladen) window.spracheNachladen();", '''/* ---- Nachtrag 25 (1.9.71 M3-Fortschritt) ---- */
Object.assign(window.SPRACHEN.en, {
  "Fotos freistellen": "Isolating photos", "TensorFlow laden": "Loading TensorFlow", "Modell bauen": "Building model",
  "Quantisieren": "Quantising", "Nach Akida umwandeln": "Converting to Akida", "Auf den AKD1500 legen": "Mapping onto the AKD1500",
  "Training (getrennte Umgebung)": "Training (separate environment)"
});

if (window.spracheNachladen) window.spracheNachladen();''')

for p, x in ((D, d), (T, t), (J, j), (H, h), (S, s), (E, e)):
    p.write_text(x, encoding="utf-8")
print("ok 1.9.71")
