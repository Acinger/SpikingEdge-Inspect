// Rauchtest 1.1-Oberflaeche (1.9.65): Vorschlaege-Dialog, Trend-Reiter, Schwelle aus dem Testsatz, Englisch.
//   node tools/smoke_elf.js http://127.0.0.1:8765   (synthetischer Server, Profil stationaer, frische Daten)
const { JSDOM } = require("jsdom"); const BASIS = process.argv[2] || "http://127.0.0.1:8765"; const fehler = [];
const ok = (b, t) => { console.log((b ? "ok  " : "FEHL ") + t); if (!b) fehler.push(t); };
const post = async (p, b) => (await fetch(BASIS + p, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(b || {}) })).json();
const get = async p => (await fetch(BASIS + p)).json();
const warte = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  // Daten: 2 Objekte lernen, Schwelle 99 % -> alles unbekannt mit Archivbild
  await post("/api/betriebsart", { art: "anlernen" });
  const st = await get("/api/state");
  const kids = st.klassen.filter(k => !k.negativ).slice(0, 2).map(k => k.id);
  for (const kid of kids) for (let i = 0; i < 4; i++) {
    for (let v = 0; v < 40; v++) { const r = await fetch(BASIS + "/api/aufnehmen", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ klasse: kid }) }); if (r.status === 200) break; await warte(250); }
    await warte(400);
  }
  ok((await post("/api/lernen_sofort", { mit_varianten: false })).ok, "Vorbereitung: Training (CPU-Ersatz)");
  await post("/api/betriebsart", { art: "betreiben" });
  await post("/api/pruef_einst", { schwelle: 0.99 });
  let n = 0;
  for (let i = 0; i < 14 && n < 8; i++) { const r = await post("/api/pruefen", {}); if (r.ok) n++; await warte(1300); }
  ok(n >= 4, `Vorbereitung: ${n} Pruefungen gebucht`);
  for (let i = 0; i < 3; i++) { await post("/api/testsatz", { tat: "aufnehmen", soll: i ? ["Objekt A"] : ["unbekannt"] }); await warte(500); }

  const html = await (await fetch(BASIS + "/")).text();
  const dom = new JSDOM(html, { url: BASIS + "/", runScripts: "dangerously", pretendToBeVisual: true, resources: "usable",
    beforeParse(w) { w.fetch = (u, o) => fetch(new URL(u, BASIS).href, o); w.requestAnimationFrame = f => setTimeout(() => f(Date.now()), 16);
      w.HTMLCanvasElement.prototype.getContext = () => new Proxy({}, { get: () => () => {}, set: () => true });
      w.alert = () => {}; w.console.error = (...m) => fehler.push(m.join(" ")); w.addEventListener("error", ev => fehler.push(ev.message)); } });
  const w = dom.window, d = w.document, $ = id => d.getElementById(id);
  await warte(3500);
  w.eval("spracheSetzen('de')"); await warte(500);     // Texte unten werden auf Deutsch geprueft

  // Trend
  ok(!!d.querySelector('[data-ops-pane="trend"]'), "Reiter Trend vorhanden");
  d.querySelector('[data-ops-pane="trend"]').click(); await warte(2500);
  const r = $("rechts");
  ok(r.querySelectorAll(".tr-balken > div").length === 24, "Trend: 24 Stundenbalken");
  ok(r.querySelectorAll(".tr-tab tbody tr").length === 14, "Trend: 14 Tage");
  ok(/Drift-Prüfung ab|Sicherheit/.test(r.textContent), "Trend: Drift-Zeile");
  ok(+r.querySelector(".tr-heute b").textContent >= n, "Trend: heute gezaehlt");
  d.querySelector('[data-ops-pane="pruefung"]').click(); await warte(500);

  // Vorschlaege (Anlernen)
  await w.eval("setzeModus('anlernen')"); await warte(3000);
  const karte = r.querySelector(".vs-block");
  ok(!!karte, "Anlernen: Karte Vorschlaege aus dem Betrieb");
  karte.querySelector('[data-tat="vorschlaege_zeigen"]').click(); await warte(2500);
  ok(!$("dVorschlaege").hidden, "Dialog offen");
  const gruppen = $("vsInhalt").querySelectorAll(".vs-gruppe");
  ok(gruppen.length >= 1 || /keine Gruppe/.test($("vsInhalt").textContent), `Dialog: ${gruppen.length} Gruppen`);
  if (gruppen.length) {
    gruppen[0].querySelector('[data-tat="vs_neu"]').click(); await warte(400);
    ok($("vsHinweis").hidden, "ohne Name: nichts passiert");
    const f = gruppen[0].querySelector("[data-vs-name]"); f.value = "Aus Betrieb"; f.dispatchEvent(new w.Event("input", { bubbles: true }));
    gruppen[0].querySelector('[data-tat="vs_neu"]').click(); await warte(3000);
    ok(!$("vsHinweis").hidden && /Aus Betrieb/.test($("vsHinweis").textContent), "uebernommen, Hinweis mit Training");
    ok((await get("/api/state")).klassen.some(k => k.name === "Aus Betrieb" && k.prototypen > 0), "Objekt angelegt");
    $("vsHinweis").querySelector('[data-tat="vs_training"]').click(); await warte(500);
    ok($("dVorschlaege").hidden && !$("dTraining").hidden, "Training-Dialog statt Vorschlaege");
    $("dTraining").hidden = true;
  }
  // Regler
  $("dVorschlaege").hidden = false;
  const reg = d.querySelector("[data-vs-grenze]"); reg.value = "120"; reg.dispatchEvent(new w.Event("change", { bubbles: true })); await warte(2500);
  ok(w.eval("VS_GRENZE") === 1.2 && w.eval("VS && VS.grenze") === 1.2, "Regler: neue Gruppierung geladen");
  $("dVorschlaege").hidden = true;

  // Testsatz: Chip "Fremdteil" legt eine Szene mit Soll "unbekannt" an
  await w.eval("setzeModus('betreiben')"); await warte(1500);
  w.eval("ABSCHNITT='erkennung'; $('dEinstellungen').hidden=false; zeichneEinstellungen()"); await warte(300);
  $("eInhalt").querySelector('[data-tat="testsatz_zeigen"]').click(); await warte(1200);
  ok($("dEinstellungen").hidden && w.eval("OPS_PANE") === "details" && !!$("rechts").querySelector('[data-ops-disclosure="testsatz"][open]'), "Testsatz oeffnen: Pruefdetails, Testsatz aufgeklappt");
  const chip = d.querySelector('[data-tat="ts_soll"][data-name="unbekannt"]');
  ok(!!chip && /Fremdteil/.test(chip.textContent), "Testsatz: Chip Fremdteil vorhanden");
  if (chip) {
    const vorher = (await get("/api/state")).bereich.pruef.testsatz.anzahl;
    chip.click(); await warte(200);
    d.querySelector('[data-tat="testsatz_aufnehmen"]').click(); await warte(1500);
    const ts = (await get("/api/state")).bereich.pruef.testsatz;
    ok(ts.anzahl === vorher + 1 && JSON.stringify(ts.letzte[0].soll) === '["unbekannt"]', "Fremdteil-Szene mit Soll unbekannt gespeichert");
    w.eval("TS_SOLL = []");
  }

  // Auto-Schwelle
  await w.eval("setzeModus('betreiben')"); await warte(1500);
  w.eval("ABSCHNITT = 'erkennung'; $('dEinstellungen').hidden = false; zeichneEinstellungen()"); await warte(1500);
  const e = $("eInhalt");
  ok(/Schwelle aus dem Testsatz/.test(e.textContent), "Einstellungen › Erkennung: Block Auto-Schwelle");
  const start = e.querySelector('[data-tat="as_start"]');
  ok(start && !start.disabled, "Testlauf-Knopf aktiv (3 Szenen)");
  start.click();
  let fertig = false;
  for (let i = 0; i < 60 && !fertig; i++) { await warte(1000); fertig = !!e.querySelector(".as-tab"); }
  ok(fertig && e.querySelectorAll(".as-tab tbody tr").length === 14, "Schwellenkurve: 14 Zeilen");
  ok(/grob/.test(e.textContent), "Hinweis: wenige Szenen");
  const ueb = e.querySelector('[data-tat="as_uebernehmen"]');
  if (ueb) {
    const soll = +ueb.dataset.wert; ueb.click(); await warte(1500);
    const p = (await get("/api/state")).bereich.pruef;
    ok(Math.abs(p.schwelle - soll) < 0.001, `Vorschlag ${soll} uebernommen`);
  } else ok(/Keine Schwelle/.test(e.textContent), "kein Vorschlag erklaert");

  // 1.9.70: Kalibrierung + Kompromiss im Block
  const k70 = w.eval(`(() => { const alt = TL; TL = { laeuft: false, kalibrierung: { werte: { 'Objekt A': 0.58 } }, ergebnis: { punkte: [], szenen: 48, vorschlag: 0.68, ziel_erreicht: false, ziel_falsch_sicher: 0.01, hinweise: ['x'] } };
    const h = blockAutoSchwelle(); TL = alt; return h; })()`);
  ok(/Kompromiss/.test(k70) && /Kalibrierung je Objekt/.test(k70) && /typisch 58 %/.test(k70) && /kalib_weg/.test(k70), "Kalibrierung + Kompromiss im Block");
  // Englisch: keine fehlenden Texte aus den neuen Bausteinen
  w.eval("spracheSetzen('en')"); await warte(1500);
  w.eval("OPS_PANE='trend'; LETZTE_SPALTE=''; zeichneRechts(); $('dVorschlaege').hidden = false; vsMalen()"); await warte(800);
  w.eval(`I18N_FEHLEND.clear();
    const box = document.createElement('div');
    box.innerHTML = blockAutoSchwelle() + trendHtml() + blockVorschlaege();
    TL = { laeuft: false, ergebnis: { punkte: [], szenen: 3, vorschlag: null, ziel_falsch_sicher: 0.005, hinweis: '' } };
    box.innerHTML += blockAutoSchwelle();
    TL = { laeuft: true, fertig: 1, gesamt: 3 }; box.innerHTML += blockAutoSchwelle();
    TL = { laeuft: false, kalibrierung: { werte: { 'SD CARD': 0.58 }, veraltet: true }, ergebnis: { punkte: [], szenen: 48, vorschlag: 0.68, ziel_erreicht: false, ziel_falsch_sicher: 0.01, hinweise: ['Keine Schwelle erreicht beides – viele Treffer UND kaum Falschbenennungen. Der Vorschlag ist ein Kompromiss (77 % Treffer, 4.6 % falsch-sicher). Besser wird es nur durch bessere Trennung: Leerbild neu, mehr Lernfotos in verschiedenen Lagen, Störteile als Hintergrund lernen.'] } };
    box.innerHTML += blockAutoSchwelle();
    Z.bereich.leerbild_veraltet = ['haupt']; box.innerHTML += pruefKarten();
    VS = { bilder: 4, gruppen: [] }; vsMalen(); box.innerHTML += blockVorschlaege();
    i18nBaum(box, true); i18nBaum($('dVorschlaege'), true);
    ['Sicherheit sinkt', 'Trend ansehen', 'Vorschläge ansehen', 'Bilder werden verglichen …', 'Nicht möglich'].forEach(t => uebersetzeText(t));`);
  const fehlend = [...w.eval("I18N_FEHLEND")].filter(s => !/^((unklar|unbekanntes Teil|Objekt [AB]|SD CARD)(, )?)+$|Objekt [AB]|SD CARD|Aus Betrieb|^„.*“$|^(Mon|Tue|Wed|Thu|Fri|Sat|Sun) \d\d\/\d\d$/.test(s));
  ok(fehlend.length === 0, "Englisch vollstaendig (1.1-Bausteine)" + (fehlend.length ? ": " + fehlend.slice(0, 40).join(" ‖ ") : ""));
  w.eval("spracheSetzen('de')");
  await post("/api/pruef_einst", { schwelle_aus: true });
  console.log(fehler.length ? "FEHLER: " + fehler.join(" | ") : "ELF_OK"); process.exit(fehler.length ? 1 : 0);
})();
