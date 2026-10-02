#!/usr/bin/env python3
"""UI 1.9.50 — Einrichten-Spalte mit Inhalt + Rechtsklick-Menue im Bild
(Anmerkung Ace, 2026-10-02).

Rechte Spalte im Modus Kamera (Einrichten):
  1 Checkliste (Schaerfe, Fenster >= Modell, Leerbild, Kamera festgehalten)
  2 Aufnahmefenster (wie gehabt)
  3 Kamera: Schnellknoepfe (Fokus/Licht/Auto alle) + Regler (Belichtungszeit,
    Verstaerkung, Fokus, Weissabgleich, Kontrast, Saettigung, Schaerfe)
  4 Leerbild: merken / verwerfen, Stand
  5 Bilder mitteln (stationaer)
  6 Was der Chip sieht, Drift, Einstellungen sichern (wie gehabt)
Rechtsklick auf das Kamerabild: Kontextmenue mit Anzeige-Schaltern
(Objektrahmen, Konturen, Beschriftung, ...), Vorlagen und Aktionen.
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
if "function blockKameraEinrichten" in h:
    print("index.html: schon gepatcht")
else:
    # 1) Spalte Einrichten
    h = ers(h, '''function spalteEinrichten() {
  const p = Z.presets || {};
  const namen = Object.keys(p);
  return griffFensterHtml() + blockChip() + blockDrift() + `''', '''function blockCheckliste() {
  const b = Z.bereich || {}, kam = Z.kamera || {};
  const L = (b.leerbild || {})[quelleVon("haupt")];
  const scharf = (b.schaerfe || 0) >= 60, gross = (b.seite || 0) >= (b.modell_px || 256);
  const werte = kam.werte || {};
  const fest = !AUTOMATIKEN.some(n => autoAn(n, werte[n])) || !kam.vorhanden;
  const P = (b.pruef || {});
  const punkte = [
    [scharf, "Bild scharf", b.schaerfe != null ? `Schärfe ${b.schaerfe}` : "Schärfe –", (b.schaerfe || 0) < 25],
    [gross, "Fenster groß genug", `${b.seite || "–"} → ${b.modell_px || 256} px`, false],
    [!!L, "Leerbild gemerkt", L ? `vom ${L}` : "noch nicht", false],
    [fest, "Kamera festgehalten", fest ? "keine Automatik regelt nach" : "Automatik aktiv", false],
  ];
  const n_ok = punkte.filter(p => p[0]).length;
  return `<div class="block"><div class="btitel"><span>Einrichtung</span><span>${n_ok} / ${punkte.length}</span></div>
    <div class="ck">${punkte.map(([ok, t, d, rot]) => `<div class="ck-z ${ok ? "ok" : rot ? "rot" : "offen"}">
      <i>${ok ? "✓" : "○"}</i><b>${t}</b><span>${txt(d)}</span></div>`).join("")}</div>
    <div class="hinweis">Reihenfolge: Teil in den Rahmen, scharf stellen, Automatik festhalten, Leerbild ohne Teil merken, Einstellung sichern.</div></div>`;
}
function blockKameraEinrichten() {
  const kam = Z.kamera || {};
  if (!kam.vorhanden) {
    return `<div class="block"><div class="btitel"><span>Kamera</span><span>keine</span></div>
      <div class="kasten warn">Keine Kamera aktiv — es laufen synthetische Bilder. Regler hätten keine Wirkung.</div>
      <div class="knopfreihe"><button class="mini" data-tat="kamera_neu">Kamera neu öffnen</button></div></div>`;
  }
  const koennen = kam.koennen || [], werte = kam.werte || {};
  const v4l = koennen.filter(n => REGLER_BEREICHE[n]);
  const autos = koennen.filter(n => AUTOMATIKEN.includes(n));
  const regler = v4l.length ? v4l.map(n => {
      const [min, max, step] = REGLER_BEREICHE[n];
      const w = werte[n] != null ? werte[n] : min;
      return `<div class="zeile"><label>${txt(n)}</label>
        <input type="range" data-kamera="${n}" min="${min}" max="${max}" step="${step}" value="${w}"><span class="w">${w}</span></div>`;
    }).join("")
    : FEED_REGLER.map(([n, l, min, max, st, e]) => `<div class="zeile"><label>${l}</label>
        <input type="range" data-fk="${n}" data-art="haupt" min="${min}" max="${max}" step="${st}" value="${FEED_REGLER_START[n]}">
        <span class="w" id="fkw-haupt-${n}">${FEED_REGLER_START[n]}${e}</span></div>`).join("");
  return `<div class="block"><div class="btitel"><span>Kamera</span><span>${txt(kam.name || "")}</span></div>
    <div class="knopfreihe">
      <button class="mini" data-tat="kam" data-art="haupt" data-akt="af_einmal" title="Einmal scharf stellen und festhalten">Scharf stellen</button>
      <button class="mini" data-tat="kam" data-art="haupt" data-akt="dunkler">Licht −</button>
      <button class="mini" data-tat="kam" data-art="haupt" data-akt="heller">Licht +</button>
      <button class="mini" data-tat="kam" data-art="haupt" data-akt="alles_auto" title="Alle Automatiken dieser Kamera zurück">Auto alle</button>
      <button class="mini" data-tat="festhalten" title="Belichtung, Weißabgleich und Fokus einfrieren">Festhalten</button>
    </div>
    ${autos.length ? `<div class="spalten2"><div>${autos.map(n =>
      `<div class="schalt ${autoAn(n, werte[n]) ? "an" : ""}" data-tat="kamera_auto" data-name="${n}"><span>${txt(n.replace(/_/g, " "))}</span><i></i></div>`).join("")}</div></div>` : ""}
    ${regler}
    <div class="hinweis">Ein bewegter Regler schaltet die zugehörige Automatik ab. „Festhalten“ friert alle ein — das ist für die Erkennung der wichtigere Zustand.</div></div>`;
}
function blockLeerbild() {
  const L = ((Z.bereich || {}).leerbild || {})[quelleVon("haupt")];
  return `<div class="block"><div class="btitel"><span>Leerbild</span><span>${L ? "✓ " + txt(L) : "nicht gemerkt"}</span></div>
    <div class="leise" style="font-size:12px;margin-bottom:8px">Referenz des leeren Tischs: 16 Bilder über ~2 s, danach zählt als Teil, was sich davon unterscheidet. Bei neuer Beleuchtung oder Kameraeinstellung neu merken.</div>
    <div class="knopfreihe">
      <button class="mini ${L ? "" : "an"}" data-tat="leerbild" data-art="haupt">${L ? "Neu merken" : "Leerbild merken"}</button>
      ${L ? `<button class="mini gefahr" data-tat="leerbild_weg" data-art="haupt">Verwerfen</button>` : ""}
    </div></div>`;
}
function blockMehrbild() {
  if (!STATIONAER()) return "";
  const P = ((Z.bereich || {}).pruef) || {};
  const n = P.mehrbild_anzahl || 1;
  return `<div class="block"><div class="btitel"><span>Bilder mitteln</span><span>${n > 1 ? n + " Bilder" : "aus"}</span></div>
    <div class="zeile"><label>Anzahl</label>
      <input type="range" data-regler="pruef_mehrbild" min="1" max="16" step="1" value="${n}"
             title="Stehende Szene über N Bilder mitteln: weniger Rauschen, kein Flackern (1 = aus)">
      <b>${n > 1 ? n + " Bilder" : "aus"}</b></div></div>`;
}
function spalteEinrichten() {
  const p = Z.presets || {};
  const namen = Object.keys(p);
  return blockCheckliste() + griffFensterHtml() + blockKameraEinrichten() + blockLeerbild() + blockMehrbild() + blockChip() + blockDrift() + `''')

    # 2) Kontextmenue im Bild
    h = ers(h, '''function ansichtMenueZeigen(an) {
  const m = $("ansichtMenue"), k = $("ansichtKnopf");
  if (!m) return;
  m.hidden = !an;
  if (k) { k.setAttribute("aria-expanded", String(!!an)); k.classList.toggle("an", !!an); }
  if (an) ansichtMenueMalen();
}''', '''let MENUE_KONTEXT = null;           // {x, y} relativ zu #videoteil, wenn per Rechtsklick
function ansichtMenueZeigen(an, kontext = null) {
  const m = $("ansichtMenue"), k = $("ansichtKnopf");
  if (!m) return;
  MENUE_KONTEXT = an ? kontext : null;
  m.hidden = !an;
  if (k) { k.setAttribute("aria-expanded", String(!!an)); k.classList.toggle("an", !!an); }
  if (kontext) {
    const vt = $("videoteil"); const vr = vt.getBoundingClientRect();
    const x = Math.min(kontext.x, Math.max(0, vr.width - 250)), y = Math.min(kontext.y, Math.max(0, vr.height - 330));
    m.style.left = x + "px"; m.style.top = y + "px"; m.style.right = "auto";
  } else { m.style.left = ""; m.style.top = ""; m.style.right = ""; }
  if (an) ansichtMenueMalen();
}
// Rechtsklick auf das Kamerabild: Anzeige-Schalter und Aktionen am Ort.
$("videoteil").addEventListener("contextmenu", (e) => {
  if (!e.target.closest || !e.target.closest("#bild, #ueberlagerung, canvas")) return;
  e.preventDefault();
  const vr = $("videoteil").getBoundingClientRect();
  ansichtMenueZeigen(true, { x: e.clientX - vr.left, y: e.clientY - vr.top });
});''')
    h = ers(h, '''  const neu = `<div class="am-kopf">Anzeige</div>
    <div class="knopfreihe">
      <button class="mini" data-tat="vorlage" data-vorlage="sauber">Sauber</button>
      <button class="mini" data-tat="vorlage" data-vorlage="arbeiten">Arbeiten</button>
      <button class="mini" data-tat="vorlage" data-vorlage="pruefen">Prüfen</button>
    </div>
    ${felder.map(([f, n]) => schalter(f, n, a)).join("")}`;''', '''  const L = ((Z.bereich || {}).leerbild || {})[quelleVon("haupt")];
  const aktionen = MENUE_KONTEXT ? `<div class="am-kopf">Aktionen</div>
    <div class="am-aktionen">
      <button class="mini" data-tat="zoom_zurueck">Zoom zurücksetzen</button>
      <button class="mini" data-tat="feed_kam" data-art="haupt">Kamera-Leiste</button>
      ${MODUS !== "betreiben" ? `<button class="mini" data-tat="fenster_schritt" data-schritt="-5">Fenster −</button>
      <button class="mini" data-tat="fenster_schritt" data-schritt="5">Fenster +</button>` : ""}
      <button class="mini" data-tat="leerbild" data-art="haupt">${L ? "Leerbild neu" : "Leerbild merken"}</button>
      ${MODUS === "betreiben" && STATIONAER() ? `<button class="mini an" data-tat="pruefen">Prüfen</button>` : ""}
    </div>` : "";
  const neu = `<div class="am-kopf">Anzeige</div>
    <div class="knopfreihe">
      <button class="mini" data-tat="vorlage" data-vorlage="sauber">Sauber</button>
      <button class="mini" data-tat="vorlage" data-vorlage="arbeiten">Arbeiten</button>
      <button class="mini" data-tat="vorlage" data-vorlage="pruefen">Prüfen</button>
    </div>
    ${felder.map(([f, n]) => schalter(f, n, a)).join("")}${aktionen}`;''')
    # zoom_zurueck Aktion
    h = ers(h, '''  if (tat === "fenster_schritt") {''', '''  if (tat === "zoom_zurueck") { ZOOM = 1; ZX = ZY = 0; zoomAnwenden(); ansichtMenueZeigen(false); return; }
  if (tat === "fenster_schritt") {''')
    # Menue nach Aktion schliessen (Rechtsklick-Fall): pruefen/leerbild/feed_kam
    h = ers(h, '''  if (tat === "pruefen") { await pruefenJetzt(); return; }''', '''  if (tat === "pruefen") { if (MENUE_KONTEXT) ansichtMenueZeigen(false); await pruefenJetzt(); return; }''')
    # 3) CSS
    h = ers(h, '''/* Live-Urteil (1.9.48) */''', '''/* Einrichten-Checkliste (1.9.50) */
.ck { display:grid; gap:6px; }
.ck-z { display:grid; grid-template-columns:20px 1fr; column-gap:8px; align-items:baseline; font-size:12.5px; }
.ck-z i { font-style:normal; font-weight:800; text-align:center; border-radius:50%; width:18px; height:18px; line-height:18px; font-size:11px; }
.ck-z.ok i { background:var(--gut,#22c55e); color:#041014; } .ck-z.offen i { border:1px solid var(--rand,#333b43); color:var(--leise,#8a94a0); }
.ck-z.rot i { background:var(--rot,#ff2d7a); color:#fff; }
.ck-z b { font-weight:600; color:var(--text); } .ck-z span { grid-column:2; font-size:11px; color:var(--leise,#8a94a0); }
#ansichtMenue .am-aktionen { display:flex; flex-wrap:wrap; gap:6px; margin-top:4px; }
/* Live-Urteil (1.9.48) */''')
    H.write_text(h, encoding="utf-8")
    print("index.html gepatcht")

s = S.read_text(encoding="utf-8")
if "1.9.50-einrichten" not in s:
    s = ers(s, 'BUILD = "1.9.49-scroll"', 'BUILD = "1.9.50-einrichten"')
    S.write_text(s, encoding="utf-8"); print("server.py gepatcht")
