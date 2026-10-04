#!/usr/bin/env python3
"""1.9.65: Oberflaeche fuer 1.1 - Vorschlaege (Anlernen), Trend (Pruefung),
Schwelle aus dem Testsatz (Einstellungen > Erkennung). Idempotent."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "vorsa/web/static/index.html"
S = ROOT / "vorsa/web/server.py"
h = H.read_text(encoding="utf-8")
s = S.read_text(encoding="utf-8")

if "ELF_UI_1965" in h:
    print("schon angewendet"); raise SystemExit(0)


def ers(text, alt, neu, n=1):
    assert text.count(alt) == n, (alt[:70], text.count(alt))
    return text.replace(alt, neu)


s = ers(s, 'BUILD = "1.9.64-selbstlernen"', 'BUILD = "1.9.65-selbstlernen"')

# 1) Trend-Reiter
h = ers(h, '''        <button type="button" data-ops-pane="diagnose" aria-pressed="false">Diagnose</button>
      </div>''', '''        <button type="button" data-ops-pane="diagnose" aria-pressed="false">Diagnose</button>
        <button type="button" data-ops-pane="trend" aria-pressed="false">Trend</button>
      </div>''')

# 2) Dialog Vorschlaege
h = ers(h, '''<div id="rueckToast" role="status" hidden>''', '''<div class="schleier" id="dVorschlaege" hidden>
  <div class="fenster vs-fenster" role="dialog" aria-labelledby="vsTitel">
    <div class="fkopf"><h2 id="vsTitel">Vorschläge aus dem Betrieb</h2><button class="zu" data-tat="dialog_zu" data-ziel="dVorschlaege" aria-label="Schließen">×</button></div>
    <div class="vs-kopf">
      <p>Teile, die beim Prüfen <b>unbekannt</b> waren, nach Form und Farbe gruppiert. Du entscheidest je Gruppe – danach „Training …“.</p>
      <label class="vs-grenze"><span>feiner</span><input type="range" min="40" max="120" step="5" value="70" data-vs-grenze aria-label="Gruppierung feiner oder gröber"><span>gröber</span></label>
    </div>
    <div id="vsHinweis" class="vs-hinweis" hidden></div>
    <div id="vsInhalt" class="vs-inhalt"></div>
  </div>
</div>
<div id="rueckToast" role="status" hidden>''')

# 3) CSS (vor dem zweiten </style>)
CSS = '''
/* ELF_UI_1965: Vorschlaege, Trend, Auto-Schwelle */
.vs-block .vs-text { font-size:12px; color:var(--leise,#8a94a0); margin:4px 0 8px; line-height:1.45; }
.vs-mini { display:flex; gap:6px; margin-bottom:8px; }
.vs-mini img { width:44px; height:44px; object-fit:cover; border-radius:6px; border:1px solid var(--rand,#333b43); }
.vs-fenster { max-width:900px; }
.vs-kopf { display:flex; gap:18px; align-items:center; justify-content:space-between; padding:4px 18px 10px; flex-wrap:wrap; }
.vs-kopf p { margin:0; font-size:12.5px; color:var(--leise,#8a94a0); flex:1 1 380px; line-height:1.5; }
.vs-kopf p b { color:var(--text); }
.vs-grenze { display:flex; gap:8px; align-items:center; font-size:11px; color:var(--leise,#8a94a0); }
.vs-grenze input { width:130px; }
.vs-hinweis { margin:0 18px 10px; padding:10px 12px; border-radius:8px; background:rgba(34,197,94,.10); border:1px solid rgba(34,197,94,.35); font-size:12.5px; display:flex; gap:10px; align-items:center; justify-content:space-between; }
.vs-inhalt { overflow:auto; padding:0 18px 18px; display:flex; flex-direction:column; gap:10px; }
.vs-gruppe { border:1px solid var(--rand,#333b43); border-radius:10px; padding:12px; display:grid; grid-template-columns:1fr; gap:10px; }
.vs-bilder { display:flex; gap:6px; flex-wrap:wrap; align-items:center; }
.vs-bilder img { width:64px; height:64px; object-fit:cover; border-radius:6px; border:1px solid var(--rand,#333b43); background:#000; }
.vs-mehr { font-size:12px; color:var(--leise,#8a94a0); padding:0 6px; }
.vs-info { font-size:12.5px; }
.vs-info small { color:var(--leise,#8a94a0); margin-left:8px; }
.vs-aktion { display:flex; gap:6px; flex-wrap:wrap; align-items:center; }
.vs-aktion .eingabe { flex:1 1 180px; min-width:140px; }
.vs-aktion button { flex:0 0 auto !important; width:auto !important; min-height:32px; padding:6px 12px; }
body#opsApp .vs-aktion .vs-primaer, body#opsApp .vs-block .vs-primaer, body#opsApp .as-block .vs-primaer { background:var(--akzent); border:1px solid var(--akzent); color:var(--aufAkzent,#041014); font-weight:700; }
.vs-aktion select { background:var(--feld,#11161b); color:var(--text); border:1px solid var(--rand,#333b43); border-radius:6px; padding:5px 6px; font-size:12px; }
.vs-leer { padding:28px 8px; text-align:center; color:var(--leise,#8a94a0); font-size:13px; line-height:1.6; }
.tr-heute { margin-bottom:10px; }
.tr-balken { display:grid; grid-template-columns:repeat(24,1fr); gap:2px; align-items:end; height:92px; padding:6px 0 2px; border-bottom:1px solid var(--rand,#333b43); }
.tr-balken > div { display:flex; flex-direction:column-reverse; height:100%; min-width:0; }
.tr-balken i { display:block; width:100%; }
.tr-balken i.g { background:#22c55e; } .tr-balken i.u { background:#f59e0b; } .tr-balken i.a { background:#ef4444; }
.tr-achse { display:flex; justify-content:space-between; font-size:9.5px; color:var(--leise,#8a94a0); margin-top:3px; }
.tr-legende { display:flex; gap:12px; font-size:10.5px; color:var(--leise,#8a94a0); margin-top:6px; }
.tr-legende i { display:inline-block; width:8px; height:8px; border-radius:2px; margin-right:4px; vertical-align:middle; }
.tr-tab { width:100%; border-collapse:collapse; font-size:11.5px; margin-top:6px; }
.tr-tab th { text-align:right; font-weight:500; color:var(--leise,#8a94a0); padding:4px 4px; font-size:10.5px; }
.tr-tab th:first-child, .tr-tab td:first-child { text-align:left; }
.tr-tab td { text-align:right; padding:4px 4px; border-top:1px solid var(--rand,#333b43); font-variant-numeric:tabular-nums; }
.tr-tab tr.leer td { color:var(--leise,#8a94a0); }
.tr-ok { font-size:12px; margin:4px 0 10px; }
.tr-drift, .tr-warn { margin:8px 0 10px; }
.as-block { margin-top:18px; padding-top:14px; border-top:1px solid var(--rand,#333b43); }
.as-block h4 { margin:0 0 4px; font-size:13px; }
.as-block p { font-size:12px; color:var(--leise,#8a94a0); margin:0 0 10px; line-height:1.5; }
.as-lauf { display:flex; gap:10px; align-items:center; font-size:12px; }
.as-lauf .ok-balken { flex:1; height:6px; }
.as-tab { width:100%; border-collapse:collapse; font-size:11.5px; margin:8px 0; }
.as-tab th { font-weight:500; color:var(--leise,#8a94a0); text-align:right; padding:3px 6px; font-size:10.5px; }
.as-tab td { text-align:right; padding:3px 6px; border-top:1px solid var(--rand,#333b43); font-variant-numeric:tabular-nums; }
.as-tab th:first-child, .as-tab td:first-child { text-align:left; }
.as-tab tr.vorschlag td { background:rgba(34,197,94,.12); font-weight:600; }
.as-tab tr.aktuell td:first-child::after { content:" ●"; color:var(--akzent,#f97316); }
.as-ergebnis { font-size:12.5px; margin:6px 0; }
'''
i = h.index("</style>", h.index("</style>") + 1)
h = h[:i] + CSS + h[i:]

# 4) JS: Funktionen
JS = r'''/* 1.1 (1.9.65): Vorschlaege aus dem Betrieb, Trend, Schwelle aus dem Testsatz */
let TREND = null, TREND_ZEIT = 0, VS = null, VS_ZEIT = 0, VS_GRENZE = 0.7, VS_NAME = {}, VS_LAEDT = false;
let TL = null, TL_ZEIT = 0;
const pz = x => x == null ? "–" : Math.round(x * 100) + " %";
async function elfLaden() {
  const jetzt = Date.now();
  try {
    if (MODUS === "betreiben" && jetzt - TREND_ZEIT > (OPS_PANE === "trend" ? 15000 : 60000)) {
      TREND_ZEIT = jetzt; TREND = await hole("/api/trend"); LETZTE_SPALTE = ""; zeichneRechts();
    }
    if (MODUS === "anlernen" && jetzt - VS_ZEIT > 30000 && $("dVorschlaege").hidden) {
      VS_ZEIT = jetzt; VS = await hole("/api/vorschlaege?grenze=" + VS_GRENZE); LETZTE_SPALTE = ""; zeichneRechts();
    }
    if (!$("dEinstellungen").hidden && ABSCHNITT === "erkennung"
        && jetzt - TL_ZEIT > (TL && TL.laeuft ? 900 : 10000)) {
      TL_ZEIT = jetzt; TL = await hole("/api/testlauf"); zeichneEinstellungen();
    }
  } catch (e) {}
}
function blockVorschlaege() {
  if (!VS || !VS.bilder) return "";
  const n = (VS.gruppen || []).length;
  return `<div class="block vs-block">
    <div class="btitel"><span>Vorschläge aus dem Betrieb</span><span>${VS.bilder} unbekannt</span></div>
    <p class="vs-text">${n ? `${n} ${n === 1 ? "Gruppe" : "Gruppen"} ähnlicher Teile, die beim Prüfen unbekannt waren.`
      : "Unbekannte Teile liegen vor, aber noch keine Gruppe ähnlicher Teile."}</p>
    ${n ? `<div class="vs-mini">${VS.gruppen.slice(0, 5).map(g =>
      `<img src="/api/pruef_bild?datei=${encodeURIComponent(g.bild)}" alt="" title="${g.anzahl}×">`).join("")}</div>` : ""}
    <button class="mini vs-primaer" data-tat="vorschlaege_zeigen">Vorschläge ansehen</button></div>`;
}
async function vorschlaegeLaden() {
  if (VS_LAEDT) return;
  VS_LAEDT = true;
  const inh = $("vsInhalt");
  if (inh && !VS) inh.innerHTML = '<div class="vs-leer">Bilder werden verglichen …</div>';
  try { VS = await hole("/api/vorschlaege?grenze=" + VS_GRENZE); VS_ZEIT = Date.now(); } catch (e) {}
  VS_LAEDT = false;
  vsMalen();
}
function vsMalen() {
  const inh = $("vsInhalt");
  if (!inh) return;
  const G = (VS && VS.gruppen) || [];
  const ks = (Z.klassen || []).filter(k => !k.negativ);
  if (!G.length) {
    inh.innerHTML = `<div class="vs-leer">${VS && VS.bilder
      ? `${VS.bilder} unbekannte Bilder, aber keine Gruppe mit mindestens zwei ähnlichen Teilen.<br>Regler Richtung „gröber“ schieben – oder weiter prüfen, bis sich Teile wiederholen.`
      : "Noch keine unbekannten Teile aus dem Betrieb.<br>Was beim Prüfen unbekannt ist, landet hier – gruppiert, zum Übernehmen."}</div>`;
    return;
  }
  inh.innerHTML = G.map((g, i) => `<div class="vs-gruppe">
    <div class="vs-bilder">${g.dateien.slice(0, 8).map(d =>
      `<img src="/api/pruef_bild?datei=${encodeURIComponent(d)}" alt="" loading="lazy">`).join("")}${
      g.anzahl > 8 ? `<span class="vs-mehr">+${g.anzahl - 8}</span>` : ""}</div>
    <div class="vs-info"><b>${g.anzahl}× unbekannt</b>${g.aehnlich ? ` · ähnelt „${txt(g.aehnlich.name)}“` : ""}</div>
    <div class="vs-aktion">
      <input class="eingabe" data-vs-name="${i}" placeholder="Name, z. B. Mutter M8" maxlength="40" value="${txt(VS_NAME[i] || "")}">
      <button class="mini vs-primaer" data-tat="vs_neu" data-k="${i}">Als neues Objekt</button>
      <select data-vs-zu="${i}" aria-label="Zu vorhandenem Objekt"><option value="">Zu Objekt …</option>${
        ks.map(k => `<option value="${k.id}">${txt(k.name)}</option>`).join("")}</select>
      <button class="mini" data-tat="vs_hg" data-k="${i}" title="Unterlage, Störteile – damit die Anlage dazu „nichts“ sagt">Hintergrund</button>
      <button class="mini gefahr" data-tat="vs_weg" data-k="${i}" title="Nicht mehr vorschlagen">Verwerfen</button>
    </div></div>`).join("");
}
async function vsAnwenden(i, aktion, extra) {
  const g = ((VS && VS.gruppen) || [])[i];
  if (!g) return;
  const r = await hole("/api/vorschlag_anwenden", Object.assign({ aktion, dateien: g.dateien }, extra || {}));
  const h = $("vsHinweis");
  if (!r || !r.ok) {
    h.hidden = false; h.innerHTML = `<span>${txt((r && r.grund) || "Nicht möglich")}</span>`;
    return;
  }
  VS_NAME = {};
  h.hidden = false;
  h.innerHTML = aktion === "verwerfen"
    ? `<span>${r.anzahl} Bilder verworfen.</span>`
    : `<span>${r.fotos} Fotos → „${txt(r.klasse)}“. Erst nach dem Training erkennt die Anlage das Objekt.</span>
       <button class="mini an" data-tat="vs_training">Training …</button>`;
  VS = null;
  await vorschlaegeLaden();
  try { await aktualisieren(); } catch (e) {}
}
function trendHtml() {
  const T = TREND;
  if (!T) return '<div class="block"><p class="ops-empty">Trend wird geladen …</p></div>';
  const D = T.drift || {}, H = T.heute || {};
  const drift = D.status === "sinkt"
    ? `<div class="kasten warn tr-drift"><b>Sicherheit sinkt</b> — ${pz(D.referenz)} nach dem letzten Training, jetzt ${pz(D.aktuell)} (je ${D.fenster} Teile).
       Meist Licht, Kamera oder neue Teilevarianten – erst dort nachsehen, dann ggf. nachtrainieren.</div>`
    : D.status === "stabil" ? `<div class="tr-ok">Sicherheit stabil · ${pz(D.referenz)} → ${pz(D.aktuell)}</div>`
    : `<div class="tr-ok leise">Drift-Prüfung ab ${2 * (D.fenster || 50)} benannten Teilen nach dem Training · bisher ${D.seit_training || 0}</div>`;
  const st = T.stunden || [];
  const max = Math.max(1, ...st.map(s => s.teile));
  const bal = st.map(s => {
    const n = s.teile, f = x => n ? (n * (x || 0) / 100) / max * 100 : 0;
    const uhr = new Date(s.start * 1000).getHours();
    return `<div title="${uhr}:00 · ${n} Teile${n ? ` · ${s.gut} % gut · ${s.unbekannt} % unbekannt` : ""}">
      <i class="g" style="height:${f(s.gut)}%"></i><i class="u" style="height:${f(s.unbekannt)}%"></i><i class="a" style="height:${f(s.ausschuss)}%"></i></div>`;
  }).join("");
  const uhr = t => String(new Date(t * 1000).getHours()).padStart(2, "0") + ":00";
  const tag = t => new Date(t * 1000).toLocaleDateString("de-DE", { weekday: "short", day: "2-digit", month: "2-digit" });
  const pr = x => x == null ? "–" : x + " %";
  const zeilen = (T.tage || []).slice().reverse().map(d => `<tr class="${d.teile ? "" : "leer"}">
    <td>${tag(d.start)}</td><td>${d.teile || "–"}</td><td>${pr(d.gut)}</td><td>${pr(d.unbekannt)}</td><td>${pr(d.ausschuss)}</td><td>${pz(d.konfidenz)}</td></tr>`).join("");
  return `<div class="block">
    <div class="btitel"><span>Heute</span><span>${T.gesamt} Teile im Journal</span></div>
    <div class="pu-stat tr-heute">
      <div><span>Teile</span><b>${H.teile || 0}</b></div><div><span>Gut</span><b class="gut">${H.gut || 0}</b></div>
      <div><span>Unbekannt</span><b class="unb">${H.unbekannt || 0}</b></div><div><span>Ausschuss</span><b class="aus">${H.ausschuss || 0}</b></div>
    </div>
    ${drift}
  </div>
  <div class="block">
    <div class="btitel"><span>Letzte 24 Stunden</span><span>max. ${max} / h</span></div>
    <div class="tr-balken">${bal}</div>
    <div class="tr-achse"><span>${st.length ? uhr(st[0].start) : ""}</span><span>${st.length ? uhr(st[12].start) : ""}</span><span>jetzt</span></div>
    <div class="tr-legende"><span><i style="background:#22c55e"></i>gut</span><span><i style="background:#f59e0b"></i>unbekannt</span><span><i style="background:#ef4444"></i>Ausschuss</span></div>
  </div>
  <div class="block">
    <div class="btitel"><span>Letzte 14 Tage</span></div>
    <table class="tr-tab"><thead><tr><th>Tag</th><th>Teile</th><th>Gut</th><th>Unbek.</th><th>Aussch.</th><th>Sicherheit</th></tr></thead>
      <tbody>${zeilen}</tbody></table>
  </div>`;
}
function blockAutoSchwelle() {
  const P = ((Z.bereich || {}).pruef) || {};
  const n = (P.testsatz || {}).anzahl || 0;
  const L = TL || {}, E = L.ergebnis;
  let inhalt = "";
  if (L.laeuft) {
    inhalt = `<div class="as-lauf"><span class="ok-balken"><i style="width:${Math.round((L.fertig || 0) / Math.max(1, L.gesamt) * 100)}%"></i></span>
      <span>Szene ${L.fertig || 0} von ${L.gesamt} …</span></div>`;
  } else if (E && E.punkte) {
    const akt = P.schwelle;
    const zeilen = E.punkte.filter((_, i) => i % 1 === 0).map(p => {
      const q = (a) => a && a[1] ? Math.round(a[0] / a[1] * 100) + " %" : "–";
      return `<tr class="${E.vorschlag != null && Math.abs(p.schwelle - Math.floor(E.vorschlag * 20 + 1e-6) / 20) < 0.001 ? "vorschlag" : ""} ${akt != null && Math.abs(akt - p.schwelle) < 0.025 ? "aktuell" : ""}">
        <td>${Math.round(p.schwelle * 100)} %</td><td>${q(p.treffer_einzeln)}</td><td>${q(p.unbekannt_erkannt)}</td>
        <td>${q(p.bekannt_als_unbekannt)}</td><td>${(p.falsch_sicher_rate * 100).toLocaleString(SPRACHE === "en" ? "en-GB" : "de-DE", { maximumFractionDigits: 1 })} %</td></tr>`;
    }).join("");
    inhalt = `<div class="as-ergebnis">${E.vorschlag != null
        ? `Vorschlag: <b>${Math.round(E.vorschlag * 100)} %</b> — die kleinste Schwelle, bei der höchstens ${(E.ziel_falsch_sicher * 100).toLocaleString(SPRACHE === "en" ? "en-GB" : "de-DE")} % der Teile falsch-sicher benannt werden.`
        : "Keine Schwelle erreicht das Ziel – erst mehr und bessere Lernfotos, dann neu messen."}
        <span class="leise"> · ${E.szenen} Szenen · ${txt(E.zeit || "")}</span></div>
      ${E.hinweis ? `<div class="warnzeile">${txt(E.hinweis)}</div>` : ""}
      <table class="as-tab"><thead><tr><th>Schwelle</th><th>Treffer</th><th>Fremdteil erkannt</th><th>Bekanntes unbekannt</th><th>Falsch-sicher</th></tr></thead>
        <tbody>${zeilen}</tbody></table>
      <div class="knopfreihe">${E.vorschlag != null ? `<button class="mini vs-primaer" data-tat="as_uebernehmen" data-wert="${E.vorschlag}">${Math.round(E.vorschlag * 100)} % übernehmen</button>` : ""}
        <button class="mini" data-tat="as_start" ${n ? "" : "disabled"}>Neu messen</button></div>`;
  } else {
    inhalt = `<div class="knopfreihe"><button class="mini vs-primaer" data-tat="as_start" ${n ? "" : "disabled"}>Testlauf starten</button>
      <span class="leise" style="font-size:11.5px;align-self:center">${n ? `${n} Szenen im Testsatz` : "Testsatz leer – Szenen unter Prüfung › Testsatz aufnehmen"}</span></div>`;
  }
  return `<div class="as-block"><h4>Schwelle aus dem Testsatz</h4>
    <p>Spielt jede Testsatz-Szene durch das Gelernte und misst für jede Schwelle von 30 bis 95 %, wie oft richtig, unbekannt oder falsch-sicher benannt wird. Gut sind etwa 50 Szenen, darunter Fremdteile („unbekannt“). Prüfen pausiert so lange.</p>
    ${L.fehler ? `<div class="warnzeile">${txt(L.fehler)}</div>` : ""}${inhalt}</div>`;
}
document.addEventListener("input", ev => {
  const el = ev.target;
  if (el.matches && el.matches("[data-vs-name]")) VS_NAME[el.dataset.vsName] = el.value;
});
document.addEventListener("change", ev => {
  const el = ev.target;
  if (!el.matches) return;
  if (el.matches("[data-vs-grenze]")) { VS_GRENZE = (+el.value || 70) / 100; VS = null; vorschlaegeLaden(); }
  else if (el.matches("[data-vs-zu]") && el.value !== "") vsAnwenden(+el.dataset.vsZu, "zu", { klasse: +el.value });
});
'''
h = ers(h, "/* TESTSATZ (A6, 1.9.45): Pruefszenen mit Soll-Werten sammeln. */",
        JS + "/* TESTSATZ (A6, 1.9.45): Pruefszenen mit Soll-Werten sammeln. */")

# 5) Trend-Reiter in der rechten Spalte
h = ers(h, '''    if (OPS_PANE === "diagnose") {
      neu = blockChip() + neu + inspektKarten();
    } else {''', '''    if (OPS_PANE === "trend") {
      neu = trendHtml();
    } else if (OPS_PANE === "diagnose") {
      neu = blockChip() + neu + inspektKarten();
    } else {''')

# 6) Anlernen: Vorschlagskarte unter den Objekten
h = ers(h, '''  </div>`;

  if (k) {
    const felder = DATEIEN.map''', '''  </div>` + blockVorschlaege();

  if (k) {
    const felder = DATEIEN.map''')

# 7) Pruefung: Drift-Warnung + Vorschlaege beim Nachlernen
h = ers(h, '''      liegt über dem Ziel von ${Math.round(P.unbekannt_ziel || 10)} %.''',
        '''      liegt über dem Ziel von ${Math.round(P.unbekannt_ziel || 10)} %.
      <button class="mini an" style="margin-top:6px" data-tat="vorschlaege_zeigen">Vorschläge ansehen</button>''')
h = ers(h, '''    </div>` : ""}
    <div class="pu-knoepfe">
      <button data-tat="pruef_csv"''', '''    </div>` : ""}
    ${TREND && TREND.drift && TREND.drift.status === "sinkt" ? `<div class="kasten warn tr-warn"><b>Sicherheit sinkt</b> —
      ${pz(TREND.drift.referenz)} → ${pz(TREND.drift.aktuell)} seit dem letzten Training.
      <button class="mini" style="margin-top:6px" data-ops-pane="trend">Trend ansehen</button></div>` : ""}
    <div class="pu-knoepfe">
      <button data-tat="pruef_csv"''')

# 8) Einstellungen > Erkennung
h = ers(h, '''<b>Ziel Unbekannt-Quote</b> — liegt der Anteil unbekannter Teile darüber, schlägt die Anlage Nachlernen vor.</div>`;''',
        '''<b>Ziel Unbekannt-Quote</b> — liegt der Anteil unbekannter Teile darüber, schlägt die Anlage Nachlernen vor.</div>
    ${blockAutoSchwelle()}`;''')

# 9) Laden im Zustandstakt
h = ers(h, '''  OPS_STATE_OK = true;
  OPS_STATE_TIME = Date.now();''', '''  OPS_STATE_OK = true;
  OPS_STATE_TIME = Date.now();
  elfLaden();''')

# 10) Klicks
h = ers(h, '''  if (tat === "sicherung_laden") { return sicherungLaden(); }''', '''  if (tat === "sicherung_laden") { return sicherungLaden(); }
  if (tat === "vorschlaege_zeigen") {
    ablaufMenueZu(); $("vsHinweis").hidden = true; $("dVorschlaege").hidden = false;
    const r = $("dVorschlaege").querySelector("[data-vs-grenze]"); if (r) r.value = Math.round(VS_GRENZE * 100);
    VS = null; return vorschlaegeLaden();
  }
  if (tat === "vs_neu") {
    const i = +el.dataset.k, name = (VS_NAME[i] || "").trim();
    if (!name) { const f = $("vsInhalt").querySelector(`[data-vs-name="${i}"]`); if (f) { f.focus(); f.classList.add("fehlt"); } return; }
    return vsAnwenden(i, "neu", { name });
  }
  if (tat === "vs_hg") { return vsAnwenden(+el.dataset.k, "hintergrund"); }
  if (tat === "vs_weg") { return vsAnwenden(+el.dataset.k, "verwerfen"); }
  if (tat === "vs_training") { $("dVorschlaege").hidden = true; $("dTraining").hidden = false; zeichneTraining(); return; }
  if (tat === "as_start") {
    el.disabled = true;
    const r = await hole("/api/testlauf", { aktion: "start" });
    if (r && r.ok === false) { MELDUNG = r.grund || "Testlauf nicht möglich"; setTimeout(() => { MELDUNG = ""; }, 4000); }
    TL = r; TL_ZEIT = 0; zeichneEinstellungen(); return;
  }
  if (tat === "as_uebernehmen") {
    await hole("/api/pruef_einst", { schwelle: +el.dataset.wert });
    MELDUNG = `Konfidenzschwelle ${Math.round(+el.dataset.wert * 100)} % übernommen`; setTimeout(() => { MELDUNG = ""; }, 3000);
    await aktualisieren(); zeichneEinstellungen(); return;
  }''')

h = ers(h, '''  summary.hidden = !production;
  if (production) {''', '''  summary.hidden = !production || OPS_PANE === "trend";   // Trend braucht die ganze Spalte
  if (production) {''')
h = ers(h, '''    OPS_PANE = tab.dataset.opsPane;
    LETZTE_SPALTE = "";''', '''    OPS_PANE = tab.dataset.opsPane;
    if (OPS_PANE === "trend") { TREND_ZEIT = 0; elfLaden(); }
    LETZTE_SPALTE = "";''')
h = ers(h, '''<div class="vs-info"><b>${g.anzahl}× unbekannt</b>${g.aehnlich ? ` · ähnelt „${txt(g.aehnlich.name)}“` : ""}</div>''',
    '''<div class="vs-info"><b>${g.anzahl}× unbekannt</b>${g.aehnlich ? `<span> · ähnelt</span> <span class="vs-name">„${txt(g.aehnlich.name)}“</span>` : ""}</div>''')
h = ers(h, '''    : `<span>${r.fotos} Fotos → „${txt(r.klasse)}“. Erst nach dem Training erkennt die Anlage das Objekt.</span>''',
    '''    : `<span><span>${r.fotos} Fotos →</span> <b class="vs-name">„${txt(r.klasse)}“</b> <span>Erst nach dem Training erkennt die Anlage das Objekt.</span></span>''')
h = ers(h, '''const tag = t => new Date(t * 1000).toLocaleDateString("de-DE", {''', '''const tag = t => new Date(t * 1000).toLocaleDateString(SPRACHE === "en" ? "en-GB" : "de-DE", {''')
H.write_text(h, encoding="utf-8")
S.write_text(s, encoding="utf-8")
print("ok 1.9.65")
