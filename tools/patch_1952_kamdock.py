#!/usr/bin/env python3
"""UI 1.9.52 — Kamera-Dock, Erkennungsdetails weg, Hinweis "keine Umrisse"
(Anmerkungen Ace, 2026-10-02).

1 KAMERA-DOCK: Kameraeinstellungen als Tafel UNTER dem Bild, die mit dem
  Kamera-Knopf (oder Rechtsklick > Kamera) nach oben aufklappt; das Bild
  rueckt animiert zusammen, Pfeil im Dock schliesst es wieder. Vier Spalten
  auf einen Blick: Bild (Belichtung, Verstaerkung, Fokus) / Farbe
  (Weissabgleich, Kontrast, Saettigung, Schaerfe) / Fenster (Groesse,
  Schaerfewert, Bilder mitteln) / Hintergrund & Sichern (Leerbild,
  Festhalten, Einstellung sichern + laden). Ersetzt die schmale Kamera-
  Leiste (kamHaupt) fuer das Hauptbild.
2 Block "Erkennungsdetails" unter dem Bild ist im Betrieb weg (steht
  rechts im Live-Urteil) - er erscheint nur noch fuer Vorgaenge/Hinweise.
3 Live-Urteil: wenn die Geometrie KEINE Umrisse fand und das Urteil vom
  Gesamtbild stammt, steht das dabei - mit dem Rat "Leerbild merken".
  (Ohne Umrisse gibt es auch keine Objektrahmen zu zeichnen.)
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "vorsa" / "web" / "static" / "index.html"
S = ROOT / "vorsa" / "web" / "server.py"


def ers(t, a, n, k=1):
    if t.count(a) != k:
        raise SystemExit(f"FEHLER: {t.count(a)}x statt {k}x: {a[:160]}")
    return t.replace(a, n)


h = H.read_text(encoding="utf-8")
if 'id="kamDock"' in h:
    print("index.html: schon gepatcht")
else:
    # --- 1) Dock-Element unter dem Bild (vor #stoerung)
    h = ers(h, '''    <div id="opsConnectionWarning" role="status" aria-live="polite" hidden></div>
    <div id="stoerung"></div>
''', '''    <div id="opsConnectionWarning" role="status" aria-live="polite" hidden></div>
    <div id="kamDock" aria-label="Kameraeinstellungen">
      <div class="kd-kopf"><b>Kameraeinstellungen</b><span id="kdStand" class="kd-stand"></span>
        <span class="rest"></span>
        <button class="vknopf kd-zu" data-tat="kamdock" title="Kameraeinstellungen schließen" aria-label="Schließen">
          <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 6l5 5 5-5"/></svg></button></div>
      <div class="kd-spalten" id="kamDockInhalt"></div>
    </div>
    <div id="stoerung"></div>
''')

    # --- 2) Kamera-Knopf des Hauptbilds oeffnet das Dock statt der Leiste
    h = ers(h, '''  if (tat === "feed_kam") {
    // Kamera-Leiste dieser Kachel (oder des Hauptbilds) ein-/ausblenden;
    // je Feed gemerkt. UI 2.2: Standard zu.
    const art = el.dataset.art;''', '''  if (tat === "kamdock" || (tat === "feed_kam" && el.dataset.art === "haupt")) {
    kamDockSetzen(!KAMDOCK_OFFEN);
    if (MENUE_KONTEXT) ansichtMenueZeigen(false);
    return;
  }
  if (tat === "feed_kam") {
    // Kamera-Leiste dieser Kachel (oder des Hauptbilds) ein-/ausblenden;
    // je Feed gemerkt. UI 2.2: Standard zu.
    const art = el.dataset.art;''')

    # --- 3) Dock-Logik + Inhalt
    h = ers(h, '''/* LIVE-URTEIL (1.9.48): grosser Kopf mit Balken. */''', '''/* KAMERA-DOCK (1.9.52): Tafel unter dem Bild, vier Spalten. */
let KAMDOCK_OFFEN = false, KAMDOCK_LETZT = "";
try { KAMDOCK_OFFEN = localStorage.getItem("nbes_kamdock") === "1"; } catch (e) {}
function kamDockSetzen(an) {
  KAMDOCK_OFFEN = !!an;
  try { localStorage.setItem("nbes_kamdock", KAMDOCK_OFFEN ? "1" : "0"); } catch (e) {}
  $("videoteil").classList.toggle("dockoffen", KAMDOCK_OFFEN);
  const k = $("kamHauptKnopf");
  if (k) { k.classList.toggle("an", KAMDOCK_OFFEN); k.setAttribute("aria-expanded", String(KAMDOCK_OFFEN)); }
  if (KAMDOCK_OFFEN) { KAMDOCK_LETZT = ""; kamDockMalen(); }
}
function kamDockMalen() {
  const box = $("kamDockInhalt");
  if (!box || !KAMDOCK_OFFEN || !Z) return;
  if (document.activeElement && box.contains(document.activeElement) && document.activeElement.matches("input[type=range],input[type=text]")) return;
  const kam = Z.kamera || {}, b = Z.bereich || {}, P = b.pruef || {};
  const werte = kam.werte || {}, koennen = kam.koennen || [];
  const L = (b.leerbild || {})[quelleVon("haupt")];
  const fk = (n) => { const r = FEED_REGLER.find(x => x[0] === n); if (!r) return ""; const [, l, min, max, st, e] = r;
    return `<div class="kd-z"><label>${l}</label><input type="range" data-fk="${n}" data-art="haupt" min="${min}" max="${max}" step="${st}" value="${FEED_REGLER_START[n]}"><span class="w" id="fkw-haupt-${n}">${FEED_REGLER_START[n]}${e}</span></div>`; };
  const v4 = (n) => { if (!REGLER_BEREICHE[n]) return ""; const [min, max, step] = REGLER_BEREICHE[n]; const w = werte[n] != null ? werte[n] : min;
    return `<div class="kd-z"><label>${txt(n)}</label><input type="range" data-kamera="${n}" min="${min}" max="${max}" step="${step}" value="${w}"><span class="w">${w}</span></div>`; };
  const usb = koennen.some(n => REGLER_BEREICHE[n]);
  const ohne = !kam.vorhanden ? `<div class="kd-hinweis">Keine Kamera aktiv — synthetische Bilder, Regler ohne Wirkung.</div>` : "";
  const bild = ohne || (usb ? ["belichtung", "verstaerkung", "fokus"].map(v4).join("") : ["ExposureTime", "AnalogueGain", "LensPosition"].map(fk).join(""));
  const farbe = ohne ? "" : (usb ? ["weissabgleich", "kontrast", "saettigung", "helligkeit"].map(v4).join("") : ["kelvin", "Contrast", "Saturation", "Sharpness"].map(fk).join(""));
  const f = Math.round(b.fenster || 100), knapp = (b.seite || 0) < (b.modell_px || 256);
  const presets = Object.keys(Z.presets || {});
  const neu = `
    <div class="kd-sp"><div class="kd-titel">Bild</div>${bild}
      <div class="kd-knoepfe">
        <button class="mini" data-tat="kam" data-art="haupt" data-akt="af_einmal" title="Einmal scharf stellen und festhalten">Scharf stellen</button>
        <button class="mini" data-tat="kam" data-art="haupt" data-akt="dunkler">Licht −</button>
        <button class="mini" data-tat="kam" data-art="haupt" data-akt="heller">Licht +</button>
        <button class="mini" data-tat="kam" data-art="haupt" data-akt="alles_auto" title="Alle Automatiken dieser Kamera zurück">Auto alle</button></div>
      <span id="fHaupt" class="kd-rueck"></span></div>
    <div class="kd-sp"><div class="kd-titel">Farbe</div>${farbe || '<div class="kd-hinweis">—</div>'}
      <div class="kd-knoepfe"><button class="mini" data-tat="festhalten" title="Belichtung, Weißabgleich und Fokus einfrieren">Festhalten</button>
        <button class="mini" data-tat="kamera_zurueck">Auf Startwerte</button></div></div>
    <div class="kd-sp"><div class="kd-titel">Fenster</div>
      <div class="kd-z"><label>Größe</label><input type="range" data-regler="fenster" min="10" max="100" step="1" value="${f}"><span class="w kd-fenster-wert">${f} %</span></div>
      <div class="kd-wert ${knapp ? "warn" : ""}">${b.seite || "–"} → ${b.modell_px || 256} px${knapp ? " · zu klein, wird hochskaliert" : ""}</div>
      <div class="kd-wert">Schärfe <b style="color:${(b.schaerfe || 0) < 25 ? "var(--rot)" : (b.schaerfe || 0) < 60 ? "var(--warn)" : "var(--gut)"}">${b.schaerfe != null ? b.schaerfe : "–"}</b>${(b.schaerfe || 0) < 25 ? " — fokussieren" : ""}</div>
      ${STATIONAER() ? `<div class="kd-z"><label>Mitteln</label><input type="range" data-regler="pruef_mehrbild" min="1" max="16" step="1" value="${P.mehrbild_anzahl || 1}" title="Stehende Szene über N Bilder mitteln (1 = aus)"><b>${(P.mehrbild_anzahl || 1) > 1 ? P.mehrbild_anzahl + " Bilder" : "aus"}</b></div>` : ""}
      <div class="kd-hinweis">Rahmen im Bild: Ecke ziehen oder Mausrad.</div></div>
    <div class="kd-sp"><div class="kd-titel">Hintergrund &amp; Sichern</div>
      <div class="kd-wert">Leerbild: <b>${L ? "✓ " + txt(L) : "nicht gemerkt"}</b></div>
      <div class="kd-knoepfe"><button class="mini ${L ? "" : "an"}" data-tat="leerbild" data-art="haupt">${L ? "Neu merken" : "Leerbild merken"}</button>
        ${L ? `<button class="mini gefahr" data-tat="leerbild_weg" data-art="haupt">Verwerfen</button>` : ""}</div>
      <div class="kd-z"><input class="eingabe" id="presetName" type="text" placeholder="Name der Einstellung"><button class="mini" data-tat="preset_speichern">Sichern</button></div>
      ${presets.length ? `<div class="kd-presets">${presets.slice(0, 4).map(n => `<button class="mini" data-tat="preset_laden" data-name="${txt(n)}" title="Einstellung laden">${txt(n)}</button>`).join("")}</div>` : `<div class="kd-hinweis">Kamera + Fenster zusammen sichern — nach dem Einrichten.</div>`}
    </div>`;
  if (neu !== KAMDOCK_LETZT) { box.innerHTML = neu; KAMDOCK_LETZT = neu; }
  const st = $("kdStand");
  if (st) { const t = kam.vorhanden ? `${txt(kam.name || "Kamera")}${b.bild_breite ? ` · ${b.bild_breite}×${b.bild_hoehe}` : ""}` : "synthetisch"; if (st.textContent !== t) st.textContent = t; }
}
/* LIVE-URTEIL (1.9.48): grosser Kopf mit Balken. */''')

    # Dock bei jedem Zustand nachzeichnen + Startzustand
    h = ers(h, '''  const observation = $("opsObservation");
  const forced = !production || !!MELDUNG || !!(LAUF && LAUF.laeuft);
  const observationOpen = forced || OPS_OPEN.has("observation");
  if (observation.open !== observationOpen) observation.open = observationOpen;
  observation.querySelector("summary").textContent = forced ? "Vorgang & Hinweise" : "Erkennungsdetails";''', '''  const observation = $("opsObservation");
  const forced = !production || !!MELDUNG || !!(LAUF && LAUF.laeuft);
  const observationOpen = forced || OPS_OPEN.has("observation");
  if (observation.open !== observationOpen) observation.open = observationOpen;
  observation.querySelector("summary").textContent = forced ? "Vorgang & Hinweise" : "Erkennungsdetails";
  // 1.9.52: im Betrieb steht das Urteil rechts - der Block unter dem Bild
  // erscheint nur noch fuer Vorgaenge und Hinweise.
  observation.hidden = production && !forced;
  if ($("videoteil").classList.contains("dockoffen") !== KAMDOCK_OFFEN) kamDockSetzen(KAMDOCK_OFFEN);
  kamDockMalen();''')

    # --- 4) Live-Urteil: Hinweis ohne Umrisse
    h = ers(h, '''  const klassen = (!leer && alle.length > 1) ? `<div class="lu-klassen">${alle.map(a => `''', '''  const ohneUmriss = !leer && L.name && teile === 0 && (Z.detektionen || []).length === 0;
  const umrissHinweis = ohneUmriss ? `<div class="lu-umriss">Urteil vom Gesamtbild — die Geometrie fand keinen Umriss, darum auch keine Objektrahmen.
      <button class="mini" data-tat="leerbild" data-art="haupt">Leerbild merken</button></div>` : "";
  const klassen = (!leer && alle.length > 1) ? `<div class="lu-klassen">${alle.map(a => `''')
    h = ers(h, '''    <div class="lu-grund">${txt(L.grund || "")}</div>
    ${klassen}
  </div>`;''', '''    <div class="lu-grund">${txt(L.grund || "")}</div>
    ${umrissHinweis}
    ${klassen}
  </div>`;''')

    # --- 5) CSS
    h = ers(h, '''/* Live-Urteil (1.9.48) */''', '''/* Kamera-Dock (1.9.52) */
#kamDock { position:absolute; left:0; right:0; bottom:30px; z-index:6; max-height:0; overflow:hidden;
  background:var(--panel,#0b1b22); border-top:1px solid var(--rand,#333b43); transition:max-height .32s ease; }
#videoteil.dockoffen #kamDock { max-height:min(340px,60%); overflow:auto; }
body#opsApp #videoteil #bild { transition:padding-bottom .32s ease; }
body#opsApp #videoteil.dockoffen #bild { padding-bottom:min(340px,60%); }
body#opsApp #videoteil.dockoffen #zoomLeiste { bottom:calc(min(340px,60%) + 36px); }
body#opsApp #videoteil.dockoffen #kamHaupt { display:none; }
.kd-kopf { display:flex; align-items:center; gap:10px; padding:6px 12px; border-bottom:1px solid var(--rand,#333b43); font-size:12px; }
.kd-kopf b { font-weight:700; color:var(--text); } .kd-stand { color:var(--leise,#8a94a0); font-size:11px; }
.kd-zu svg { transform:none; } .kd-zu { min-width:30px; }
.kd-spalten { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:0; }
.kd-sp { padding:10px 12px; border-right:1px solid var(--rand,#333b43); min-width:0; }
.kd-sp:last-child { border-right:0; }
.kd-titel { font-size:10px; letter-spacing:.12em; text-transform:uppercase; color:var(--leise,#8a94a0); margin-bottom:8px; font-weight:700; }
.kd-z { display:grid; grid-template-columns:78px 1fr 58px; align-items:center; gap:6px; margin:4px 0; font-size:11px; }
.kd-z label { color:var(--leise,#8a94a0); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.kd-z input[type=range] { width:100%; min-width:0; } .kd-z .w, .kd-z b { text-align:right; font-variant-numeric:tabular-nums; font-size:11px; }
.kd-z .eingabe { grid-column:1 / 3; font-size:12px; padding:4px 6px; }
.kd-knoepfe { display:flex; flex-wrap:wrap; gap:5px; margin-top:8px; } .kd-knoepfe .mini { font-size:11px; padding:4px 8px; }
.kd-wert { font-size:11.5px; color:var(--leise,#8a94a0); margin:4px 0; } .kd-wert b { color:var(--text); } .kd-wert.warn { color:var(--warn,#ffc62e); }
.kd-hinweis { font-size:10.5px; color:var(--leise,#8a94a0); margin-top:6px; line-height:1.4; }
.kd-rueck { display:block; font-size:10.5px; color:var(--leise,#8a94a0); margin-top:4px; min-height:14px; }
.kd-presets { display:flex; flex-wrap:wrap; gap:5px; margin-top:6px; }
@media (max-width:1150px) { .kd-spalten { grid-template-columns:repeat(2,minmax(0,1fr)); } .kd-sp:nth-child(2) { border-right:0; } }
.lu-umriss { margin-top:8px; padding:8px 10px; border:1px dashed var(--warn,#ffc62e); border-radius:6px; font-size:11.5px; color:var(--text); display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
/* Live-Urteil (1.9.48) */''')
    h = ers(h, '''      const wert = $("fensterWert");
      if (wert) wert.textContent = `${Math.round(r.fenster)} %`;''', '''      document.querySelectorAll("#fensterWert, .kd-fenster-wert").forEach(wert => {
        wert.textContent = `${Math.round(r.fenster)} %`; });
      const fl = $("fensterLeisteWert");
      if (fl) { fl.dataset.wert = String(Math.round(r.fenster)); fl.textContent = `Fenster ${Math.round(r.fenster)} %`; }''')
    H.write_text(h, encoding="utf-8")
    print("index.html gepatcht")

s = S.read_text(encoding="utf-8")
if "1.9.52-kamdock" not in s:
    s = ers(s, 'BUILD = "1.9.51-audit"', 'BUILD = "1.9.52-kamdock"')
    S.write_text(s, encoding="utf-8"); print("server.py gepatcht")
