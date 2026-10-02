#!/usr/bin/env python3
"""A1 — UI fuer das Profil `stationaer` (index.html, Build 1.9.38).

- PROFIL aus /api/state; Linienbetrieb/Zonen verschwinden im Profil stationaer
- Pruef-Kachel: grosser PRUEFEN-Knopf, Ausloeser Hand/Auto, letzte Pruefung
  je Teil, Szenenstatus; Leertaste prueft in der Erkennung
Exakte Ersetzungen, idempotent.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "vorsa" / "web" / "static" / "index.html"


def ers(text, alt, neu, n=1):
    k = text.count(alt)
    if k != n:
        raise SystemExit(f"FEHLER: {k}x statt {n}x gefunden:\n{alt[:200]}")
    return text.replace(alt, neu)


h = H.read_text(encoding="utf-8")
if 'data-tat="pruefen"' in h:
    print("index.html: schon gepatcht")
    raise SystemExit(0)

# 1) Globale: PROFIL
h = ers(h, '''let Z = null;                 // letzter Zustand vom Server
let MODUS = "betreiben";      // die Anlage startet in der Erkennung
''', '''let Z = null;                 // letzter Zustand vom Server
let MODUS = "betreiben";      // die Anlage startet in der Erkennung
// PROFIL (SE Inspect 1.0, 1.9.38): "stationaer" = Pruefzelle ohne Band,
// Arm und Zonen; "linie" = Linienbetrieb. Kommt vom Server (/api/state).
let PROFIL = "linie";
const STATIONAER = () => PROFIL === "stationaer";
let PRUEF_LAEUFT = false;     // /api/pruefen unterwegs
''')

# 2) Zustand holen -> PROFIL uebernehmen
h = ers(h, '''    Z = await hole("/api/state");
''', '''    Z = await hole("/api/state");
    if (Z && Z.profil && Z.profil !== PROFIL) {
      PROFIL = Z.profil;
      document.body.classList.toggle("stationaer", STATIONAER());
      const nl = $("navLinie"); if (nl) nl.hidden = STATIONAER();
      const kz = document.querySelector('#seitenNav .snav[data-modus="einrichten"] span');
      if (kz) kz.textContent = STATIONAER() ? "Kamera" : "Kamera & Zonen";
    }
''')

# 3) opsSync: Namen und Zonen-Knopf
h = ers(h, '''  const names = { betreiben:"Erkennung", anlernen:"Objekte & Lernen", einrichten:"Kamera & Zonen" };''',
        '''  const names = { betreiben:"Erkennung", anlernen:"Objekte & Lernen",
                  einrichten: STATIONAER() ? "Kamera" : "Kamera & Zonen" };''')
h = ers(h, '''  const zk = $("zoneKnopf");
  if (zk) zk.hidden = !(MODUS === "einrichten" || (ANSICHT_LINIE && !lern));
  $("opsPaneTitle").textContent''', '''  const zk = $("zoneKnopf");
  if (zk) zk.hidden = STATIONAER() || !(MODUS === "einrichten" || (ANSICHT_LINIE && !lern));
  $("opsPaneTitle").textContent''')

# 4) Pruef-Kachel: stationaerer Kopf (Knopf, Ausloeser, letzte Pruefung)
h = ers(h, '''  const konf = L.konfidenz != null ? Math.round(L.konfidenz * 100) + " %" : "";
  return `<div class="block"><section class="ops-pruef-summary"><div class="btitel">
      <span>Aktuelles Prüfurteil</span></div>''', '''  const konf = L.konfidenz != null ? Math.round(L.konfidenz * 100) + " %" : "";
  const stat = STATIONAER() ? pruefStationaerKopf(P, zeit) : "";
  return `<div class="block"><section class="ops-pruef-summary">${stat}<div class="btitel">
      <span>${STATIONAER() ? "Livebild" : "Aktuelles Prüfurteil"}</span></div>''')

h = ers(h, '''      : `<div style="color:var(--leise);font-size:9.5px">Noch kein Teil
          geprüft — Urteile entstehen im Linienbetrieb je abgeräumtem
          Teil.</div>`}''', '''      : `<div style="color:var(--leise);font-size:9.5px">${STATIONAER()
          ? "Noch kein Teil geprüft — Teil auflegen und PRÜFEN drücken (oder Auslöser Auto)."
          : "Noch kein Teil geprüft — Urteile entstehen im Linienbetrieb je abgeräumtem Teil."}</div>`}''')

h = ers(h, '''function pruefKarten() {
  const P = ((Z.bereich || {}).pruef) || null;''', '''/* STATIONAERE PRUEFUNG (1.9.38): Kopf der Pruef-Kachel. */
function pruefStationaerKopf(P, zeit) {
  const U = { gut: "GUT", unbekannt: "UNBEKANNT", ausschuss: "AUSSCHUSS" };
  const auto = P.ausloeser === "auto";
  const L = P.letzte_pruefung || null;
  const teil = (Z.erkannt && (Z.erkannt.je_objekt || []).length) || 0;
  const status = PRUEF_LAEUFT ? "Prüfung läuft …"
    : !teil ? "Kein Teil im Bild"
    : P.szene_gebucht ? "Szene geprüft — nächstes Teil auflegen"
    : P.szene_steht ? (auto ? "Szene steht — Automatik prüft" : "Szene steht — bereit")
    : "Szene bewegt sich";
  const letzte = L ? `<div class="pu-urteil ${L.urteil}" style="margin-top:10px">
      <b>${U[L.urteil] || "—"}</b>
      <div><div class="pu-name">${L.teile.length} Teil${L.teile.length === 1 ? "" : "e"} ·
        ${zeit(L.zeit)} · ${L.ausloeser === "auto" ? "Automatik" : "Hand"}</div>
        <div class="pu-teile">${L.teile.map(t => `<div class="pu-zeile"><i class="${t.urteil}"></i>
          <span class="n">${txt(t.name || (t.urteil === "unbekannt" ? "unbekanntes Teil" : t.urteil))}</span>
          <span class="k">${t.konfidenz ? Math.round(t.konfidenz * 100) + "%" : ""}</span>
          <span class="g">${txt(t.grund || "")}</span>
          ${t.bild ? `<img src="/api/pruef_bild?datei=${encodeURIComponent(t.bild)}" alt="">` : ""}
        </div>`).join("")}</div></div></div>` : "";
  return `<div class="pu-stationaer">
    <div class="pu-ausloeser">
      <button class="pu-pruefen" data-tat="pruefen" ${(!teil || PRUEF_LAEUFT || MODUS !== "betreiben") ? "disabled" : ""}
        title="Alle Teile im Bild jetzt prüfen und buchen (Leertaste)">PRÜFEN</button>
      <span class="ltakt" title="Hand: Knopf oder Leertaste. Auto: jede neue, still liegende Szene wird von selbst geprüft.">
        <button data-tat="pruef_ausloeser" data-wert="hand" class="${auto ? "" : "an"}">Hand</button>
        <button data-tat="pruef_ausloeser" data-wert="auto" class="${auto ? "an" : ""}">Auto</button>
      </span>
    </div>
    <div class="pu-status ${P.szene_steht && teil && !P.szene_gebucht ? "bereit" : ""}">${status}</div>
    ${letzte}
  </div>`;
}
function pruefKarten() {
  const P = ((Z.bereich || {}).pruef) || null;''')

# 5) Aktionen
h = ers(h, '''  if (tat === "pruef_reset") {
    // Kritische Aktion -> Bestaetigung (Befehlsfuehrung, Stufe 2).''', '''  if (tat === "pruefen") { await pruefenJetzt(); return; }
  if (tat === "pruef_ausloeser") {
    try { await hole("/api/pruef_einst", { ausloeser: el.dataset.wert }); } catch (e) {}
    LETZTE_SPALTE = ""; await aktualisieren();
    return;
  }
  if (tat === "pruef_reset") {
    // Kritische Aktion -> Bestaetigung (Befehlsfuehrung, Stufe 2).''')

h = ers(h, '''/* STATIONAERE PRUEFUNG (1.9.38): Kopf der Pruef-Kachel. */''', '''/* STATIONAERE PRUEFUNG (1.9.38): Knopf / Leertaste -> /api/pruefen. */
async function pruefenJetzt() {
  if (PRUEF_LAEUFT || !STATIONAER() || MODUS !== "betreiben") return;
  PRUEF_LAEUFT = true;
  LETZTE_SPALTE = ""; zeichneRechts();
  try {
    const r = await hole("/api/pruefen", {});
    if (r && !r.ok) { MELDUNG = r.grund || "Prüfung nicht möglich"; setTimeout(() => { MELDUNG = ""; }, 2500); }
    else if (r && r.urteil && r.urteil !== "gut") pruefTon(r.urteil);
  } catch (e) {}
  PRUEF_LAEUFT = false;
  LETZTE_SPALTE = ""; await aktualisieren();
}
/* STATIONAERE PRUEFUNG (1.9.38): Kopf der Pruef-Kachel. */''')

# 6) Leertaste
h = ers(h, '''  if (ev.code === "Space" && MODUS === "anlernen") { ev.preventDefault(); aufnehmen(); }''',
        '''  if (ev.code === "Space" && MODUS === "anlernen") { ev.preventDefault(); aufnehmen(); }
  if (ev.code === "Space" && MODUS === "betreiben" && STATIONAER()) { ev.preventDefault(); pruefenJetzt(); }''')

# 7) CSS
h = ers(h, '''.pu-knoepfe { display:flex; gap:6px; margin-top:10px; flex-wrap:wrap; }''',
        '''.pu-knoepfe { display:flex; gap:6px; margin-top:10px; flex-wrap:wrap; }
/* stationaere Pruefung (1.9.38) */
.pu-stationaer { margin-bottom:12px; }
.pu-ausloeser { display:flex; align-items:center; gap:10px; }
.pu-pruefen { flex:1; min-height:52px; font-size:17px; font-weight:800; letter-spacing:1.5px;
  border-radius:6px; border:1px solid var(--akzent,#3a7bd5); background:var(--akzent,#3a7bd5);
  color:var(--aufAkzent,#fff); cursor:pointer; }
.pu-pruefen:disabled { opacity:.45; cursor:default; }
.pu-pruefen:not(:disabled):hover { filter:brightness(1.12); }
.pu-status { margin-top:6px; font-size:11px; color:var(--leise,#8a94a0); }
.pu-status.bereit { color:var(--gut,#22c55e); }
.pu-teile { margin-top:8px; display:grid; gap:4px; }
.pu-teile .pu-zeile .g { color:var(--leise,#8a94a0); font-size:9.5px; }
body#opsApp .pu-pruefen { border-radius:6px; }
body.stationaer #navLinie, body.stationaer #linieAnsicht, body.stationaer .ltakt-linie { display:none !important; }''')

H.write_text(h, encoding="utf-8")
print("index.html gepatcht")
