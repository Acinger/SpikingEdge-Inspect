#!/usr/bin/env python3
"""1.9.58 — Anlernen & Prüfen verständlicher (Paket 4).

* Objekte als Karten: Vorschaubild, Foto-Fortschritt (x/5) als Balken, Ampel,
  "Hintergrund" statt "nichts / Störteil" erklärt. Doppelte Knöpfe in der Spalte
  ("Foto aufnehmen", "Training starten") entfallen - beides sitzt oben rechts.
* Prüfen: Urteilskarte klar als "Live-Vorschau" markiert, Zähler darunter als
  "Gebuchte Prüfungen". Der Dauerhinweis "Urteil vom Gesamtbild …" wird eine
  kleine Zeile (Leerbild-Knopf nur, solange keins gemerkt ist).
* Löschen: Foto mit "Rückgängig" (5 s, Löschen erst danach), Objekt über den
  eigenen Bestätigungsdialog statt Browser-Fenster.
* Tastenkürzel-Hilfe mit "?".
"""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "vorsa" / "web" / "static" / "index.html"
S = ROOT / "vorsa" / "web" / "server.py"
ST = ROOT / "vorsa" / "web" / "state.py"
D = ROOT / "vorsa" / "web" / "static" / "sprache_en.js"


def ers(t, a, n, k=1):
    if t.count(a) != k:
        raise SystemExit(f"FEHLER: {t.count(a)}x statt {k}x: {a[:140]}")
    return t.replace(a, n)


st = ST.read_text(encoding="utf-8")
if '"titelbild"' not in st:
    st = ers(st, '''            "prototypen": len(self.prototypen),
            "gesamt_mit_augmentierung": (''', '''            "prototypen": len(self.prototypen),
            # Vorschaubild fuer die Objektkarte (1.9.58): erstes Foto
            "titelbild": (self.prototypen[0] if self.prototypen else ""),
            "gesamt_mit_augmentierung": (''')
    ST.write_text(st, encoding="utf-8")
    print("state.py: titelbild")

h = H.read_text(encoding="utf-8")
if "OBJEKTKARTEN (1.9.58)" in h:
    print("index.html: schon gepatcht")
else:
    # ---------- Objektkarten ----------
    h = ers(h, '''  let aus = `<div class="block">
    <div class="btitel"><span>OBJEKTE</span><span>${ks.length}</span></div>
    <div class="chips">${ks.map(x => `
      <span class="chip ${x.id === AKTIV ? "aktiv" : ""} ${x.negativ ? "negativ" : ""}"
            data-tat="objekt" data-id="${x.id}">
        <b>${txt(x.name)}</b>
        <span class="n ${x.prototypen >= ZIEL ? "voll" : ""}">${x.prototypen}/${ZIEL}</span>
      </span>`).join("")}</div>
    <div class="zeile" style="margin-top:10px">
      <input class="eingabe" id="neuName" type="text" placeholder="Neues Objekt">
      <button class="mini" style="flex:0 0 auto" data-tat="objekt_neu">+</button></div>
    ${ks.some(x => x.negativ) ? "" : `<div class="warnzeile">
      Keine Negativklasse. Ohne sie meldet der Chip auch bei leerem Band ein Objekt.
      <button class="mini" style="margin-top:6px" data-tat="objekt_neu"
              data-negativ="1">„nichts / Störteil" anlegen</button></div>`}
  </div>`;''', '''  // OBJEKTKARTEN (1.9.58): Bild, Fortschritt, Ampel - auf einen Blick, was fehlt.
  const karte = (x) => {
    const p = x.prototypen || 0, voll = p >= ZIEL;
    const ampel = x.negativ ? "neg" : voll ? "gruen" : p ? "gelb" : "grau";
    const unter = x.negativ ? "Hintergrund · " + p + " Fotos"
      : voll ? p + " Fotos · bereit" : p ? `noch ${ZIEL - p} Fotos` : "noch keine Fotos";
    return `<button class="okarte ${x.id === AKTIV ? "aktiv" : ""} ${x.negativ ? "negativ" : ""}" data-tat="objekt" data-id="${x.id}"
        title="${x.negativ ? "Hintergrund: leere Fläche, Unterlage, Störteile — damit die Anlage auch „nichts“ sagen kann" : "Objekt wählen"}">
      <span class="ok-bild">${x.titelbild ? `<img src="/api/prototyp?datei=${encodeURIComponent(x.titelbild)}" alt="" loading="lazy">`
        : `<span>${txt((x.name || "?").slice(0, 1).toUpperCase())}</span>`}</span>
      <span class="ok-text"><b>${txt(x.name)}</b><small>${unter}</small>
        <span class="ok-balken"><i style="width:${Math.min(100, Math.round(p / ZIEL * 100))}%"></i></span></span>
      <i class="ok-ampel ${ampel}" aria-hidden="true"></i></button>`;
  };
  let aus = `<div class="block">
    <div class="btitel"><span>OBJEKTE</span><span>${ks.filter(x => !x.negativ).length}${ks.some(x => x.negativ) ? " + Hintergrund" : ""}</span></div>
    <div class="ok-karten">${ks.map(karte).join("")}</div>
    <div class="zeile" style="margin-top:10px">
      <input class="eingabe" id="neuName" type="text" placeholder="Neues Objekt, z. B. Schraube M6">
      <button class="mini an" style="flex:0 0 auto" data-tat="objekt_neu" title="Objekt anlegen">+ Anlegen</button></div>
    ${ks.some(x => x.negativ) ? "" : `<div class="warnzeile">
      Noch kein Hintergrund. Ohne ihn meldet die Anlage auch bei leerer Fläche ein Objekt.
      <button class="mini" style="margin-top:6px" data-tat="objekt_neu"
              data-negativ="1">Hintergrund anlegen</button></div>`}
  </div>`;''')
    h = ers(h, '''      { name: negativ ? "nichts / Störteil" : name, negativ });''',
            '''      { name: negativ ? "Hintergrund" : name, negativ });''')
    # Foto-Block: Titel + Hinweis statt doppeltem Knopf
    h = ers(h, '''      <div class="btitel"><span>LERNFENSTER · ${txt(k.name)}</span>
        <span>${k.prototypen} Fotos · ${k.gesamt_mit_augmentierung} Beispiele</span></div>
      <div id="raster">${felder.join("")}</div>
      <div class="knopfreihe" style="margin-top:11px">
        <button class="haupttaste" style="flex:1" data-tat="aufnehmen">Foto aufnehmen</button>
      </div>''', '''      <div class="btitel"><span>FOTOS · ${txt(k.name)}</span>
        <span>${k.prototypen}/${ZIEL}${k.prototypen > ZIEL ? "+" : ""}</span></div>
      <div id="raster">${felder.join("")}</div>
      <div class="ok-hinweis">Teil in den Rahmen legen, dann Leertaste oder oben „Foto aufnehmen“. Lage zwischen den Fotos ändern.
        <span>${k.gesamt_mit_augmentierung} Lernbeispiele mit Varianten</span></div>''')
    h = ers(h, '''    <button class="haupttaste" style="width:100%" data-tat="training_dialog"
            ${plan.bereit ? "" : "disabled"}>Training starten …</button>
    ${plan.bereit ? `<div class="hinweis">Der Dialog zeigt vorher, was hingeht,''',
            '''    ${plan.bereit ? `<div class="hinweis">Oben rechts „Lernen …“ öffnet den Dialog. Er zeigt vorher, was hingeht,''')
    # Foto-Kachel: Loeschen mit Rueckgaengig
    h = ers(h, '''        <span class="weg" data-tat="foto_weg" data-datei="${txt(d)}">×</span></div>`);''',
            '''        <span class="weg" data-tat="foto_weg" data-datei="${txt(d)}" title="Foto löschen (rückgängig machbar)">×</span></div>`).filter((_, i) => !FOTO_WEG.has(DATEIEN[i]));''')

    # ---------- Live-Vorschau vs. gebucht ----------
    h = ers(h, '''  const ohneUmriss = !leer && L.name && teile === 0 && (Z.detektionen || []).length === 0;
  const umrissHinweis = ohneUmriss ? `<div class="lu-umriss">Urteil vom Gesamtbild — die Geometrie fand keinen Umriss, darum auch keine Objektrahmen.
      <button class="mini" data-tat="leerbild" data-art="haupt">Leerbild merken</button></div>` : "";''',
            '''  const ohneUmriss = !leer && L.name && teile === 0 && (Z.detektionen || []).length === 0;
  const lbDa = !!(((Z.bereich || {}).leerbild || {})[quelleVon("haupt")]);
  // 1.9.58: eine leise Zeile statt eines Kastens; der Knopf nur, solange er hilft.
  const umrissHinweis = ohneUmriss ? `<div class="lu-umriss klein" title="Die Geometrie fand keinen Umriss — das Urteil stammt vom ganzen Fenster, darum keine Objektrahmen.">ⓘ Kein Umriss gefunden · Urteil aus dem ganzen Fenster${
      lbDa ? "" : ` <button class="lu-link" data-tat="leerbild" data-art="haupt">Leerbild merken</button>`}</div>` : "";''')
    h = ers(h, '''  return `<div class="lu ${L.urteil}" data-lu="${txt(L.urteil + ":" + name + ":" + pct)}">
    <div class="lu-kopf">''', '''  return `<div class="lu ${L.urteil}" data-lu="${txt(L.urteil + ":" + name + ":" + pct)}">
    <div class="lu-live" title="Was die Kamera gerade sieht — gezählt wird erst beim Prüfen"><i></i>Live-Vorschau</div>
    <div class="lu-kopf">''')
    h = ers(h, '''    <div class="pu-stat">
      <div><span>Geprüft</span><b>${P.gesamt ?? "–"}</b></div>''', '''    <div class="pu-stat-titel">Gebuchte Prüfungen</div>
    <div class="pu-stat">
      <div><span>Geprüft</span><b>${P.gesamt ?? "–"}</b></div>''')
    h = ers(h, '''    <p class="ops-count-note">Zähler erfassen abgeschlossene Prüfungen.</p>
''', '')

    # ---------- Handler: Foto rueckgaengig, Objekt per Dialog, ? ----------
    h = ers(h, '''  if (tat === "foto_weg") {
    await hole("/api/prototyp_loeschen",
      { klasse: AKTIV, datei: el.dataset.datei });
    await ladeDateien(); return aktualisieren();
  }''', '''  if (tat === "foto_weg") {
    // 1.9.58: erst ausblenden, nach 5 s wirklich loeschen - bis dahin rueckgaengig.
    const datei = el.dataset.datei, klasse = AKTIV;
    FOTO_WEG.add(datei); LETZTE_SPALTE = ""; zeichneRechts();
    rueckgaengigZeigen("Foto gelöscht", () => { FOTO_WEG.delete(datei); LETZTE_SPALTE = ""; zeichneRechts(); },
      async () => { await hole("/api/prototyp_loeschen", { klasse, datei }); FOTO_WEG.delete(datei); await ladeDateien(); aktualisieren(); });
    return;
  }
  if (tat === "rueckgaengig") { if (RUECK) { const r = RUECK; RUECK = null; clearTimeout(r.timer); r.zurueck(); $("rueckToast").hidden = true; } return; }
  if (tat === "hilfe_zu") { $("dHilfe").hidden = true; return; }''')
    h = ers(h, '''    if (!confirm(`„${k.name}“ mit ${k.prototypen} Fotos endgültig löschen?`)) return;''',
            '''    if (!await bestaetigen({ titel: "Objekt löschen", text: `„${k.name}“ mit ${k.prototypen} Fotos endgültig löschen? Das lässt sich nicht rückgängig machen.`, ok: "Löschen" })) return;''')
    h = ers(h, '''  if (ev.key === "Escape") {
    $("dEinstellungen").hidden = true;
    $("dTraining").hidden = true;
  }''', '''  if (ev.key === "Escape") {
    $("dEinstellungen").hidden = true;
    $("dTraining").hidden = true;
    $("dHilfe").hidden = true;
  }
  if (ev.key === "?") { $("dHilfe").hidden = !$("dHilfe").hidden; }''')
    h = ers(h, '''function ablaufMenueZu() {''', '''/* RUECKGAENGIG (1.9.58): eine Aktion, 5 s Zeit. */
const FOTO_WEG = new Set();
let RUECK = null;
function rueckgaengigZeigen(text, zurueck, ausfuehren) {
  if (RUECK) { clearTimeout(RUECK.timer); RUECK.ausfuehren(); }
  const t = $("rueckToast");
  $("rueckText").textContent = text; t.hidden = false;
  RUECK = { zurueck, ausfuehren, timer: setTimeout(() => { const r = RUECK; RUECK = null; t.hidden = true; if (r) r.ausfuehren(); }, 5000) };
}
function ablaufMenueZu() {''')
    h = ers(h, '''        <button class="ops-btn" data-tat="erststart" role="menuitem">Erste Schritte</button>''',
            '''        <button class="ops-btn" data-tat="erststart" role="menuitem">Erste Schritte</button>
        <button class="ops-btn" data-tat="hilfe" role="menuitem">Tastenkürzel  ?</button>''')
    h = ers(h, '''  if (tat === "erst_schritt") { return erstSchrittTun(el.dataset.nr); }''',
            '''  if (tat === "erst_schritt") { return erstSchrittTun(el.dataset.nr); }
  if (tat === "hilfe") { ablaufMenueZu(); $("dHilfe").hidden = false; return; }''')
    # ---------- DOM: Toast + Hilfe ----------
    h = ers(h, '''<section id="opsCommand" aria-label="Arbeitsbereich und Linienbefehle" tabindex="-1">''', '''<div id="rueckToast" role="status" hidden><span id="rueckText"></span>
  <button data-tat="rueckgaengig">Rückgängig</button></div>
<div class="schleier" id="dHilfe" hidden>
  <div class="fenster hilfe-fenster">
    <div class="fkopf"><h2>Tastenkürzel</h2><button class="zu" data-tat="hilfe_zu">×</button></div>
    <div class="hilfe-liste">
      <div><kbd>Leertaste</kbd><span>Prüfen (Schritt 3) · Foto aufnehmen (Schritt 2)</span></div>
      <div><kbd>1</kbd>–<kbd>8</kbd><span>Objekt wählen (Schritt 2)</span></div>
      <div><kbd>Mausrad</kbd><span>über dem Rahmen: Aufnahmefenster größer/kleiner</span></div>
      <div><kbd>Rechtsklick</kbd><span>im Bild: Anzeige und Aktionen</span></div>
      <div><kbd>Esc</kbd><span>Fenster schließen</span></div>
      <div><kbd>?</kbd><span>diese Hilfe</span></div>
    </div>
  </div>
</div>

<section id="opsCommand" aria-label="Arbeitsbereich und Linienbefehle" tabindex="-1">''')
    # ---------- CSS ----------
    h = ers(h, '''/* Kamera-Dock (1.9.52) */''', '''/* ANLERNEN & PRUEFEN (1.9.58) ------------------------------------------------ */
.ok-karten { display:grid; grid-template-columns:1fr; gap:6px; }
.okarte { display:grid; grid-template-columns:44px 1fr 12px; gap:10px; align-items:center; width:100%; text-align:left; cursor:pointer;
  padding:6px 10px 6px 6px; border:1px solid var(--rand,#333b43); border-radius:8px; background:transparent; color:var(--text); font:inherit; }
.okarte:hover { border-color:var(--randhell,#55606b); }
.okarte.aktiv { border-color:var(--akzent,#49e7ff); background:rgba(73,231,255,.07); box-shadow:inset 3px 0 var(--akzent,#49e7ff); }
.okarte .ok-bild { width:44px; height:44px; border-radius:6px; overflow:hidden; background:#ffffff10; display:flex; align-items:center; justify-content:center; }
.okarte .ok-bild img { width:100%; height:100%; object-fit:cover; display:block; }
.okarte .ok-bild span { font-weight:800; font-size:18px; color:var(--leise,#8a94a0); }
.okarte .ok-text { min-width:0; display:block; }
.okarte .ok-text b { display:block; font-size:13.5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.okarte .ok-text small { display:block; font-size:11.5px; color:var(--leise,#8a94a0); margin:1px 0 5px; }
.okarte .ok-balken { display:block; height:4px; border-radius:2px; background:#ffffff18; overflow:hidden; }
.okarte .ok-balken i { display:block; height:100%; background:var(--akzent,#49e7ff); }
.okarte .ok-ampel { width:10px; height:10px; border-radius:50%; background:#5a6570; }
.okarte .ok-ampel.gruen { background:var(--gut,#22c55e); } .okarte .ok-ampel.gelb { background:var(--warn,#f5b041); }
.okarte .ok-ampel.neg { background:transparent; border:2px solid var(--leise,#8a94a0); }
.okarte.negativ .ok-balken i { background:var(--leise,#8a94a0); }
.ok-hinweis { font-size:12px; color:var(--leise,#8a94a0); line-height:1.5; margin-top:10px; }
.ok-hinweis b { color:var(--text); } .ok-hinweis span { display:block; font-size:11px; margin-top:3px; opacity:.8; }
.lu-live { display:flex; align-items:center; gap:6px; font-size:10.5px; font-weight:700; letter-spacing:.12em; text-transform:uppercase; color:var(--leise,#8a94a0); margin-bottom:4px; }
.lu-live i { width:7px; height:7px; border-radius:50%; background:var(--rot,#ff2d7a); animation:luLive 1.6s ease-in-out infinite; }
@keyframes luLive { 50% { opacity:.25; } }
.lu-umriss.klein { font-size:11.5px; color:var(--leise,#8a94a0); border:0; background:transparent; padding:4px 0 0; margin:6px 0 0; }
.lu-link { background:none; border:0; padding:0; margin-left:4px; color:var(--akzent,#49e7ff); text-decoration:underline; cursor:pointer; font:inherit; }
.pu-stat-titel { font-size:10.5px; font-weight:700; letter-spacing:.12em; text-transform:uppercase; color:var(--leise,#8a94a0); margin:14px 0 4px; }
#rueckToast { position:fixed; left:50%; bottom:52px; transform:translateX(-50%); z-index:70; display:flex; gap:16px; align-items:center;
  padding:10px 14px 10px 18px; border-radius:10px; background:#101c24; border:1px solid var(--rand,#333b43); color:#e8f4f6; box-shadow:0 12px 30px #0008; font-size:13px; }
#rueckToast[hidden] { display:none; }
#rueckToast button { background:none; border:1px solid var(--akzent,#49e7ff); color:var(--akzent,#49e7ff); border-radius:6px; padding:6px 12px; cursor:pointer; font:inherit; font-weight:700; }
.hilfe-fenster { max-width:520px; }
.hilfe-liste { padding:14px 18px 18px; display:grid; gap:10px; }
.hilfe-liste div { display:grid; grid-template-columns:150px 1fr; gap:12px; align-items:center; font-size:13px; color:var(--text); }
.hilfe-liste kbd { display:inline-block; padding:3px 8px; border:1px solid var(--rand,#556); border-bottom-width:2px; border-radius:5px; font:600 12px ui-monospace,Consolas,monospace; background:#ffffff0a; }
/* Kamera-Dock (1.9.52) */''')
    H.write_text(h, encoding="utf-8")
    print("index.html gepatcht")

s = S.read_text(encoding="utf-8")
if "1.9.58-anlernen" not in s:
    s = ers(s, 'BUILD = "1.9.57-einstellungen"', 'BUILD = "1.9.58-anlernen"')
    S.write_text(s, encoding="utf-8")
    print("server.py: BUILD 1.9.58-anlernen")

d = D.read_text(encoding="utf-8")
if "Nachtrag 13" not in d:
    d = ers(d, '\nif (window.spracheNachladen) window.spracheNachladen();\n', '''
/* ---- Nachtrag 13 (1.9.58 Anlernen & Pruefen) ---- */
Object.assign(window.SPRACHEN.en, {
  "OBJEKTE": "OBJECTS", "{} + Hintergrund": "{} + background", "Hintergrund": "Background", "Hintergrund · {} Fotos": "Background · {} photos",
  "{} Fotos · bereit": "{} photos · ready", "noch {} Fotos": "{} more photos", "noch keine Fotos": "no photos yet", "Objekt wählen": "Select object",
  "Hintergrund: leere Fläche, Unterlage, Störteile — damit die Anlage auch „nichts“ sagen kann": "Background: empty surface, base, foreign parts — so the cell can also say “nothing”",
  "Neues Objekt, z. B. Schraube M6": "New object, e.g. screw M6", "+ Anlegen": "+ Add", "Objekt anlegen": "Add object",
  "Noch kein Hintergrund. Ohne ihn meldet die Anlage auch bei leerer Fläche ein Objekt.": "No background yet. Without it the cell reports an object even on an empty surface.",
  "Hintergrund anlegen": "Add background", "FOTOS · {}": "PHOTOS · {}",
  "Teil in den Rahmen legen, dann Leertaste oder oben „Foto aufnehmen“. Lage zwischen den Fotos ändern.": "Place the part in the frame, then press space or “Take photo” at the top. Change its position between photos.",
  "{} Lernbeispiele mit Varianten": "{} learning examples with variants",
  "Foto löschen (rückgängig machbar)": "Delete photo (can be undone)", "Foto gelöscht": "Photo deleted", "Rückgängig": "Undo",
  "Live-Vorschau": "Live preview", "Was die Kamera gerade sieht — gezählt wird erst beim Prüfen": "What the camera sees right now — counted only when inspecting",
  "Gebuchte Prüfungen": "Logged inspections", "ⓘ Kein Umriss gefunden · Urteil aus dem ganzen Fenster": "ⓘ No outline found · verdict from the whole window",
  "Die Geometrie fand keinen Umriss — das Urteil stammt vom ganzen Fenster, darum keine Objektrahmen.": "Geometry found no outline — the verdict comes from the whole window, hence no object frames.",
  "Objekt löschen": "Delete object", "Löschen": "Delete",
  "„{}“ mit {} Fotos endgültig löschen? Das lässt sich nicht rückgängig machen.": "Permanently delete “{}” with {} photos? This cannot be undone.",
  "Tastenkürzel": "Keyboard shortcuts", "Tastenkürzel  ?": "Shortcuts  ?", "Leertaste": "Space",
  "Prüfen (Schritt 3) · Foto aufnehmen (Schritt 2)": "Inspect (step 3) · take photo (step 2)", "Objekt wählen (Schritt 2)": "Select object (step 2)",
  "Mausrad": "Mouse wheel", "über dem Rahmen: Aufnahmefenster größer/kleiner": "over the frame: capture window larger/smaller",
  "Rechtsklick": "Right-click", "im Bild: Anzeige und Aktionen": "in the image: display and actions", "Fenster schließen": "Close window", "Esc": "Esc", "diese Hilfe": "this help",
  "Oben rechts „Lernen …“ öffnet den Dialog. Er zeigt vorher, was hingeht, und lässt die Wahl zwischen den beiden Wegen:": "“Learn …” at the top right opens the dialog. It shows beforehand what goes in and lets you choose between the two paths:"
});

if (window.spracheNachladen) window.spracheNachladen();
''')
    D.write_text(d, encoding="utf-8")
    print("sprache_en.js: Nachtrag 13")
