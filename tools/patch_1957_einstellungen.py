#!/usr/bin/env python3
"""1.9.57 — Ein Einstellungsfenster statt vier Orte (Paket 3) + "Rezepte" heißen "Prüfprogramme".

* Zahnrad "Einstellungen" in der Seitenleiste -> Fenster mit Reitern
  Allgemein · Kamera · Erkennung · Prüfprogramme | Hardware · Diagnose · Wartung.
  "Zustand" öffnet dasselbe Fenster auf "Hardware".
* Allgemein: Sprache, Darstellung, Ton, Prüf-Auslöser, Erste Schritte.
  Erkennung: Konfidenzschwelle, Ziel Unbekannt-Quote, Bilder mitteln (dieselben
  Regler wie in den Prüfdetails, gleiche Werte).
* Rezepte -> Prüfprogramme (nur Bezeichnung; API, Datei rezepte.json bleiben).
  "Einstellung sichern" (Kamera + Fenster) geht im Prüfprogramm auf: Einrichten-
  Spalte und Kamera-Dock sichern jetzt als Prüfprogramm. Alte Presets bleiben ladbar.
* Fußleiste links: nur Symbole mit Tooltip, keine abgeschnittenen Wörter;
  Versionszeile raus (steht unter Einstellungen > Hardware > Software).
"""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "vorsa" / "web" / "static" / "index.html"
S = ROOT / "vorsa" / "web" / "server.py"
D = ROOT / "vorsa" / "web" / "static" / "sprache_en.js"


def ers(t, a, n, k=1):
    if t.count(a) != k:
        raise SystemExit(f"FEHLER: {t.count(a)}x statt {k}x: {a[:140]}")
    return t.replace(a, n)


h = H.read_text(encoding="utf-8")
if "EINSTELLUNGEN (1.9.57)" in h:
    print("index.html: schon gepatcht")
else:
    # ---------- Seitenleiste ----------
    h = ers(h, '''    <svg viewBox="0 0 16 16" aria-hidden="true"><rect x="3" y="2" width="10" height="13" rx="1"/><path d="M6 1h4v3H6zM6 7h4M6 10h4"/></svg><span>Rezepte</span></button>
  <div class="ops-nav-caption">System</div>
''', '''    <svg viewBox="0 0 16 16" aria-hidden="true"><rect x="3" y="2" width="10" height="13" rx="1"/><path d="M6 1h4v3H6zM6 7h4M6 10h4"/></svg><span>Prüfprogramme</span></button>
  <div class="ops-nav-caption">System</div>
  <!-- EINSTELLUNGEN (1.9.57): ein Fenster für alles Einstellbare -->
  <button class="snav ops-expert" id="navEinstellungen" data-tat="abschnitt_oeffnen" data-id="allgemein" title="Einstellungen: Allgemein, Kamera, Erkennung, Prüfprogramme">
    <svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="2.4"/><path d="M8 1v2M8 13v2M1 8h2M13 8h2M3 3l1.4 1.4M11.6 11.6L13 13M3 13l1.4-1.4M11.6 4.4L13 3"/></svg><span>Einstellungen</span></button>
''')
    h = ers(h, '''<button class="snav" data-tat="rezepte" title="Rezepte und Aufträge">''',
            '''<button class="snav" data-tat="rezepte" title="Prüfprogramme: Einrichtung je Produkt, Umrüsten per Auswahl">''')
    h = ers(h, '''<button class="chipfeld" data-tat="rezepte" title="Rezepte und Aufträge öffnen"><small>Rezept</small>''',
            '''<button class="chipfeld" data-tat="rezepte" title="Prüfprogramme öffnen"><small>Programm</small>''')
    h = ers(h, '''    <div class="fkopf"><h2>Rezepte &amp; Aufträge</h2>''', '''    <div class="fkopf"><h2>Prüfprogramme</h2>''')
    h = ers(h, '''    <div class="fkopf"><h2>Zustand</h2>
      <button class="zu" data-tat="dialog_zu" data-ziel="dEinstellungen">×</button></div>''',
            '''    <div class="fkopf"><h2>Einstellungen</h2>
      <button class="zu" data-tat="dialog_zu" data-ziel="dEinstellungen">×</button></div>''')

    # ---------- Reiter ----------
    h = ers(h, '''const ABSCHNITTE = [
  ["hardware", "Hardware"], ["diagnose", "Diagnose"], ["wartung", "Wartung"],
];''', '''const ABSCHNITTE = [
  ["allgemein", "Allgemein"], ["kamera", "Kamera"], ["erkennung", "Erkennung"], ["programme", "Prüfprogramme"],
  ["hardware", "Hardware"], ["diagnose", "Diagnose"], ["wartung", "Wartung"],
];''')
    h = ers(h, '''const ABSCHNITT_ALIAS = { modell: "hardware", ueber: "hardware",
  messen: "diagnose", daten: "wartung", aufnahme: "hardware",
  anzeige: "hardware", objekte: "hardware" };''', '''const ABSCHNITT_ALIAS = { modell: "hardware", ueber: "hardware",
  messen: "diagnose", daten: "wartung", aufnahme: "kamera",
  anzeige: "allgemein", objekte: "hardware", rezepte: "programme" };''')
    h = ers(h, '''  $("eNav").innerHTML = ABSCHNITTE.map(([id, name]) =>
    `<button class="${id === ABSCHNITT ? "an" : ""}" data-tat="abschnitt"
             data-id="${id}">${txt(name)}</button>`).join("");''', '''  $("eNav").innerHTML = ABSCHNITTE.map(([id, name]) =>
    (id === "hardware" ? '<span class="e-trenn" aria-hidden="true"></span>' : "") +
    `<button class="${id === ABSCHNITT ? "an" : ""}" data-tat="abschnitt"
             data-id="${id}">${txt(name)}</button>`).join("");''')
    h = ers(h, '''  if (ABSCHNITT === "wartung") return abschnittDaten();
''', '''  if (ABSCHNITT === "wartung") return abschnittDaten();
  if (ABSCHNITT === "allgemein") return abschnittAllgemein();
  if (ABSCHNITT === "kamera") return `<h3>Kamera</h3>
    <div class="e-hinweis">Schnell nachstellen geht direkt am Bild: Knopf „Kamera“ über dem Kamerabild.</div>`
    + blockKameraEinrichten() + blockLeerbild() + (STATIONAER() ? blockMehrbild() : "");
  if (ABSCHNITT === "erkennung") return abschnittErkennung();
  if (ABSCHNITT === "programme") return abschnittProgramme();
''')
    h = ers(h, '''function inhaltAbschnitt() {''', '''/* EINSTELLUNGEN (1.9.57): neue Reiter */
function eWahl(tat, wert, aktiv, text) {
  return `<button class="mini ${aktiv ? "an" : ""}" data-tat="${tat}" data-wert="${wert}" aria-pressed="${!!aktiv}">${text}</button>`;
}
function abschnittAllgemein() {
  const P = ((Z.bereich || {}).pruef) || {};
  const look = skinAktiv();
  return `<h3>Allgemein</h3>
    <div class="e-zeile"><div><b>Sprache</b><span>Oberfläche und Meldungen</span></div>
      <div class="e-wahl">${eWahl("sprache_setzen", "de", SPRACHE === "de", "Deutsch")}${eWahl("sprache_setzen", "en", SPRACHE === "en", "English")}</div></div>
    <div class="e-zeile"><div><b>Darstellung</b><span>Farbschema der Oberfläche</span></div>
      <div class="e-wahl">${eWahl("look_setzen", "spikingedge", look === "spikingedge", "SpikingEdge")}${eWahl("look_setzen", "industrie", look === "industrie", "Hell")}${eWahl("look_setzen", "magna", look === "magna", "Magna")}</div></div>
    <div class="e-zeile"><div><b>Ton bei Unbekannt / Ausschuss</b><span>Kurzer Hinweiston nach der Prüfung</span></div>
      <div class="e-wahl">${eWahl("pruef_ton_setzen", "1", PRUEF_TON, "An")}${eWahl("pruef_ton_setzen", "0", !PRUEF_TON, "Aus")}</div></div>
    ${STATIONAER() ? `<div class="e-zeile"><div><b>Prüf-Auslöser</b><span>Hand: Knopf oder Leertaste · Auto: jede neue, still liegende Szene</span></div>
      <div class="e-wahl">${eWahl("pruef_ausloeser", "hand", P.ausloeser !== "auto", "Hand")}${eWahl("pruef_ausloeser", "auto", P.ausloeser === "auto", "Auto")}</div></div>` : ""}
    <div class="e-zeile"><div><b>Erste Schritte</b><span>Die geführte Einrichtung erneut öffnen</span></div>
      <div class="e-wahl"><button class="mini" data-tat="erststart">Öffnen</button></div></div>`;
}
function abschnittErkennung() {
  const P = ((Z.bereich || {}).pruef) || {};
  const sw = P.schwelle == null ? 0 : Math.round(P.schwelle * 100);
  return `<h3>Erkennung</h3>
    <div class="e-hinweis">Dieselben Werte wie unter Prüfung › Prüfdetails › Prüfparameter.</div>
    <div class="pu-schwelle e-regler">
      <label>Konfidenzschwelle</label>
      <input type="range" data-regler="pruef_schwelle" min="0" max="100" step="1" value="${sw}"
             title="Darunter gilt ein benanntes Teil als UNBEKANNT (0 = aus)">
      <b>${P.schwelle == null ? "aus" : sw + " %"}</b>
      <label>Ziel Unbek.-Quote</label>
      <input type="range" data-regler="pruef_ziel" min="1" max="50" step="1" value="${Math.round(P.unbekannt_ziel || 10)}"
             title="Ab dieser Unbekannt-Quote wird Nachlernen empfohlen">
      <b>${Math.round(P.unbekannt_ziel || 10)} %</b>
      ${STATIONAER() ? `<label>Bilder mitteln</label>
      <input type="range" data-regler="pruef_mehrbild" min="1" max="16" step="1" value="${P.mehrbild_anzahl || 1}"
             title="Stehende Szene über N Bilder mitteln: weniger Rauschen (1 = aus)">
      <b>${(P.mehrbild_anzahl || 1) > 1 ? P.mehrbild_anzahl + " Bilder" : "aus"}</b>` : ""}
    </div>
    <div class="e-erkl"><b>Konfidenzschwelle</b> — wie sicher sich die Anlage sein muss, bevor sie einen Namen nennt. Höher = öfter „unbekannt“, dafür seltener falsch.<br>
      <b>Ziel Unbekannt-Quote</b> — liegt der Anteil unbekannter Teile darüber, schlägt die Anlage Nachlernen vor.</div>`;
}
let RZ_LETZT = null, RZ_GELADEN = 0;
function abschnittProgramme() {
  if (Date.now() - RZ_GELADEN > 5000) { RZ_GELADEN = Date.now(); rezepteLaden(); }
  const alt = Object.keys(Z.presets || {});
  return `<h3>Prüfprogramme</h3>` + rezepteHtml(RZ_LETZT || {}) + (alt.length ? `
    <h4>Ältere Kamera-Einstellungen</h4>
    <div class="e-hinweis">Aus früheren Versionen (nur Kamera + Fenster). Neu sichern geht als Prüfprogramm.</div>
    <div class="knopfreihe">${alt.map(n => `<button class="mini" data-tat="preset_laden" data-name="${txt(n)}">${txt(n)}</button>`).join("")}</div>` : "");
}
function inhaltAbschnitt() {''')

    # ---------- Rezepte -> Prüfprogramme, HTML wiederverwendbar ----------
    h = ers(h, '''function rezepteMalen(d) {
  const k = $("rzKoerper"); if (!k) return;
  const R = (d && d.rezepte) || {};''', '''function rezepteMalen(d) {
  if (d) RZ_LETZT = d;
  const k = $("rzKoerper");
  if (k) k.innerHTML = rezepteHtml(RZ_LETZT || {});
  try { if (ABSCHNITT === "programme") zeichneEinstellungen(); } catch (e) {}
}
function rezepteHtml(d) {
  const R = (d && d.rezepte) || {};''')
    h = ers(h, '''  k.innerHTML = `
    <div class="leise" style="font-size:11px;margin-bottom:10px;line-height:1.5">
      Ein Rezept bündelt die Einrichtung für ein Produkt: Kameraeinstellungen,
      Erkennungsfenster, Zonen + Kameraquellen und die Arm-Sequenz. Das
      Gelernte bleibt davon unberührt.</div>''', '''  return `
    <div class="leise" style="font-size:11px;margin-bottom:10px;line-height:1.5">
      Ein Prüfprogramm bündelt die Einrichtung für ein Produkt: Kameraeinstellungen,
      Aufnahmefenster, Zonen und die Arm-Sequenz. Umrüsten = Programm laden.
      Das Gelernte bleibt davon unberührt.</div>''')
    h = ers(h, '''    : `<div class="al-leer">Noch kein Rezept. Richte ein Produkt ein (Zonen,
        Kamera, Arm-Sequenz) und speichere die Einrichtung unter einem Namen —
        beim nächsten Umrüsten genügt „Laden".</div>`}`;
}''', '''    : `<div class="al-leer">Noch kein Prüfprogramm. Richte ein Produkt ein (Kamera,
        Fenster, Zonen, Arm-Sequenz) und speichere die Einrichtung unter einem Namen —
        beim nächsten Umrüsten genügt „Laden".</div>`}`;
}''')
    h = ers(h, '''      <input id="rzName" class="adx-eingabe" placeholder="Name, z. B. Karabiner M6"''',
            '''      <input class="adx-eingabe rz-name" placeholder="Name, z. B. Karabiner M6"''')
    h = ers(h, '''  if (tat === "rezept_speichern") {
    const feld = $("rzName");''', '''  if (tat === "rezept_speichern") {
    // Das Namensfeld neben DIESEM Knopf (Dialog, Einstellungen, Einrichten, Dock).
    const feld = (el.closest(".al-kopf,.kd-z,.block,.fenster") || document).querySelector(".rz-name");''')
    h = ers(h, '''    if (el.dataset.name && !await bestaetigen({ titel: "Rezept aktualisieren",''',
            '''    if (el.dataset.name && !await bestaetigen({ titel: "Prüfprogramm aktualisieren",''')

    # ---------- Einrichten-Spalte + Dock: als Prüfprogramm sichern ----------
    h = ers(h, '''    <div class="block">
      <div class="btitel"><span>EINSTELLUNGEN SICHERN</span></div>
      <div class="zeile"><input class="eingabe" id="presetName" type="text"
           placeholder="Name der Einstellung"></div>
      <div class="knopfreihe"><button class="mini" data-tat="preset_speichern">
        Aktuelle Einstellung sichern</button></div>
      ${namen.length ? namen.map(n => `
        <div class="zeile"><label style="min-width:auto;flex:1">${txt(n)}</label>
          <button class="mini" style="flex:0 0 auto" data-tat="preset_laden"
                  data-name="${txt(n)}">laden</button>
          <button class="mini gefahr" style="flex:0 0 auto" data-tat="preset_loeschen"
                  data-name="${txt(n)}">×</button></div>`).join("")
        : '<div class="leise" style="font-size:12px">noch keine gesichert</div>'}
      <div class="hinweis">Gesichert wird die Kameraeinstellung zusammen mit
        dem Ausschnitt. Getrennt wären sie wertlos.</div>
    </div>`;''', '''    <div class="block">
      <div class="btitel"><span>ALS PRÜFPROGRAMM SICHERN</span><span>${txt(((Z.bereich || {}).rezept) || "")}</span></div>
      <div class="zeile"><input class="eingabe rz-name" type="text"
           placeholder="Name, z. B. Gehäuse A" value="${txt(((Z.bereich || {}).rezept) || "")}"></div>
      <div class="knopfreihe"><button class="mini an" data-tat="rezept_speichern">Sichern</button>
        <button class="mini" data-tat="rezepte">Alle Prüfprogramme …</button></div>
      <div class="hinweis">Gesichert werden Kamera, Aufnahmefenster${STATIONAER() ? "" : ", Zonen und Arm-Sequenz"} —
        beim Umrüsten genügt „Laden“. ${namen.length ? `Ältere Kamera-Einstellungen (${namen.length}) unter Einstellungen › Prüfprogramme.` : ""}</div>
    </div>`;''')
    h = ers(h, '''      <div class="kd-z"><input class="eingabe" id="presetName" type="text" placeholder="Name der Einstellung"><button class="mini" data-tat="preset_speichern">Sichern</button></div>
      ${presets.length ? `<div class="kd-presets">${presets.slice(0, 4).map(n => `<button class="mini" data-tat="preset_laden" data-name="${txt(n)}" title="Einstellung laden">${txt(n)}</button>`).join("")}</div>` : `<div class="kd-hinweis">Kamera + Fenster zusammen sichern — nach dem Einrichten.</div>`}''',
            '''      <div class="kd-z"><input class="eingabe rz-name" type="text" placeholder="Prüfprogramm, z. B. Gehäuse A" value="${txt(((Z.bereich || {}).rezept) || "")}"><button class="mini" data-tat="rezept_speichern" title="Kamera + Fenster als Prüfprogramm sichern">Sichern</button></div>
      <div class="kd-knoepfe"><button class="mini" data-tat="rezepte">Prüfprogramme …</button></div>''')

    # ---------- Handler ----------
    h = ers(h, '''  if (tat === "sprache") { spracheSetzen(SPRACHE === "en" ? "de" : "en"); return; }''',
            '''  if (tat === "sprache") { spracheSetzen(SPRACHE === "en" ? "de" : "en"); return; }
  if (tat === "sprache_setzen") { spracheSetzen(el.dataset.wert); zeichneEinstellungen(); return; }
  if (tat === "look_setzen") { skinSetzen(el.dataset.wert); zeichneEinstellungen(); return; }
  if (tat === "pruef_ton_setzen") {
    PRUEF_TON = el.dataset.wert === "1";
    try { localStorage.setItem("nbes_pruef_ton", PRUEF_TON ? "1" : "0"); } catch (e) {}
    LETZTE_SPALTE = ""; zeichneEinstellungen(); return;
  }''')
    h = ers(h, '''  if (tat === "erststart") { ablaufMenueZu(); erstStartZeigen(true); return; }''',
            '''  if (tat === "erststart") { ablaufMenueZu(); $("dEinstellungen").hidden = true; erstStartZeigen(true); return; }''')

    # ---------- CSS ----------
    h = ers(h, '''/* Kamera-Dock (1.9.52) */''', '''/* EINSTELLUNGEN (1.9.57) ---------------------------------------------------- */
#eNav .e-trenn { display:block; height:1px; background:var(--rand,#333b43); margin:8px 4px; }
#eInhalt .e-zeile { display:flex; justify-content:space-between; align-items:center; gap:16px; padding:12px 0; border-bottom:1px solid var(--rand,#333b43); }
#eInhalt .e-zeile b { display:block; font-size:13.5px; color:var(--text); }
#eInhalt .e-zeile span { display:block; font-size:12px; color:var(--leise,#8a94a0); margin-top:2px; }
#eInhalt .e-wahl { display:flex; gap:6px; flex-wrap:wrap; justify-content:flex-end; flex:0 0 auto; }
#eInhalt .e-wahl .mini { min-width:64px; }
#eInhalt .e-wahl .mini.an, #eInhalt .e-wahl .mini[aria-pressed="true"] { background:var(--akzent,#49e7ff) !important; border-color:var(--akzent,#49e7ff) !important; color:var(--aufAkzent,#041014) !important; font-weight:700; }
#eInhalt .e-hinweis { font-size:12px; color:var(--leise,#8a94a0); margin:0 0 12px; }
#eInhalt .e-erkl { font-size:12px; color:var(--leise,#8a94a0); line-height:1.55; margin-top:14px; }
#eInhalt .e-erkl b { color:var(--text); }
#eInhalt .e-regler { padding:8px 0; }
body#opsApp .ops-nav-icons { justify-content:space-around; }
body#opsApp .ops-nav-icons .snav.klein { justify-content:center; min-height:38px; padding:8px; width:auto; flex:1; }
body#opsApp .ops-nav-icons .snav.klein span:not(#navSpracheLabel) { display:none; }
body#opsApp .ops-nav-icons #navSpracheLabel { font-size:11px; font-weight:700; }
body#opsApp .ops-version { display:none; }
/* Kamera-Dock (1.9.52) */''')
    H.write_text(h, encoding="utf-8")
    print("index.html gepatcht")

s = S.read_text(encoding="utf-8")
if "1.9.57-einstellungen" not in s:
    s = ers(s, 'BUILD = "1.9.56-ablauf"', 'BUILD = "1.9.57-einstellungen"')
    S.write_text(s, encoding="utf-8")
    print("server.py: BUILD 1.9.57-einstellungen")

d = D.read_text(encoding="utf-8")
if "Nachtrag 12" not in d:
    d = ers(d, '\nif (window.spracheNachladen) window.spracheNachladen();\n', '''
/* ---- Nachtrag 12 (1.9.57 Einstellungen, Prüfprogramme) ---- */
Object.assign(window.SPRACHEN.en, {
  "Einstellungen": "Settings", "Allgemein": "General", "Erkennung": "Recognition", "Prüfprogramme": "Jobs", "Programm": "Job",
  "Einstellungen: Allgemein, Kamera, Erkennung, Prüfprogramme": "Settings: general, camera, recognition, jobs",
  "Prüfprogramme: Einrichtung je Produkt, Umrüsten per Auswahl": "Jobs: setup per product, changeover by selection",
  "Prüfprogramme öffnen": "Open jobs", "Sprache": "Language", "Oberfläche und Meldungen": "Interface and messages",
  "Darstellung": "Appearance", "Farbschema der Oberfläche": "Colour scheme", "Hell": "Light",
  "Ton bei Unbekannt / Ausschuss": "Sound on unknown / reject", "Kurzer Hinweiston nach der Prüfung": "Short tone after inspection",
  "An": "On", "Aus": "Off", "Prüf-Auslöser": "Inspection trigger",
  "Hand: Knopf oder Leertaste · Auto: jede neue, still liegende Szene": "Manual: button or space bar · Auto: every new, settled scene",
  "Die geführte Einrichtung erneut öffnen": "Open the guided setup again", "Öffnen": "Open",
  "Schnell nachstellen geht direkt am Bild: Knopf „Kamera“ über dem Kamerabild.": "For quick adjustments use the “Camera” button above the image.",
  "Dieselben Werte wie unter Prüfung › Prüfdetails › Prüfparameter.": "Same values as Inspection › Inspection details › Parameters.",
  "Konfidenzschwelle": "Confidence threshold", "Ziel Unbek.-Quote": "Target unknown rate", "Bilder mitteln": "Average frames",
  "— wie sicher sich die Anlage sein muss, bevor sie einen Namen nennt. Höher = öfter „unbekannt“, dafür seltener falsch.": "— how sure the cell must be before it names a part. Higher = more often “unknown”, but less often wrong.",
  "Ziel Unbekannt-Quote": "Target unknown rate",
  "— liegt der Anteil unbekannter Teile darüber, schlägt die Anlage Nachlernen vor.": "— if the share of unknown parts exceeds it, the cell suggests re-teaching.",
  "Ältere Kamera-Einstellungen": "Older camera settings",
  "Aus früheren Versionen (nur Kamera + Fenster). Neu sichern geht als Prüfprogramm.": "From earlier versions (camera + window only). Save new ones as a job.",
  "ALS PRÜFPROGRAMM SICHERN": "SAVE AS JOB", "Name, z. B. Gehäuse A": "Name, e.g. Housing A", "Sichern": "Save",
  "Alle Prüfprogramme …": "All jobs …", "Prüfprogramme …": "Jobs …", "Prüfprogramm, z. B. Gehäuse A": "Job, e.g. Housing A",
  "Kamera + Fenster als Prüfprogramm sichern": "Save camera + window as a job",
  "Prüfprogramm aktualisieren": "Update job",
  "Ein Prüfprogramm bündelt die Einrichtung für ein Produkt: Kameraeinstellungen, Aufnahmefenster, Zonen und die Arm-Sequenz. Umrüsten = Programm laden. Das Gelernte bleibt davon unberührt.": "A job bundles the setup for one product: camera settings, capture window, zones and the arm sequence. Changeover = load the job. What was learned is not affected.",
  "Noch kein Prüfprogramm. Richte ein Produkt ein (Kamera, Fenster, Zonen, Arm-Sequenz) und speichere die Einrichtung unter einem Namen — beim nächsten Umrüsten genügt „Laden\\".": "No job yet. Set up a product (camera, window, zones, arm sequence) and save the setup under a name — next changeover, just “Load”."
});

if (window.spracheNachladen) window.spracheNachladen();
''')
    D.write_text(d, encoding="utf-8")
    print("sprache_en.js: Nachtrag 12")
