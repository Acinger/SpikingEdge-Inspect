// Rauchtest Anlernen & Pruefen (1.9.58): Objektkarten, Foto loeschen mit Rueckgaengig, Live-Vorschau, Hilfe.
//   node tools/smoke_anlernen.js http://127.0.0.1:8765
const { JSDOM } = require("jsdom"); const BASIS = process.argv[2] || "http://127.0.0.1:8765"; const fehler = [];
(async () => {
  const html = await (await fetch(BASIS + "/")).text();
  const dom = new JSDOM(html, { url: BASIS + "/", runScripts: "dangerously", pretendToBeVisual: true, resources: "usable",
    beforeParse(w) { w.fetch = (u, o) => fetch(new URL(u, BASIS).href, o); w.requestAnimationFrame = f => setTimeout(() => f(Date.now()), 16);
      w.HTMLCanvasElement.prototype.getContext = () => new Proxy({}, { get: () => () => {}, set: () => true });
      w.alert = () => {}; w.confirm = () => { fehler.push("Browser-confirm benutzt"); return false; };
      w.console.error = (...a) => fehler.push(a.join(" ")); w.addEventListener("error", e => fehler.push(e.message)); } });
  const w = dom.window, d = w.document, $ = id => d.getElementById(id), warte = ms => new Promise(r => setTimeout(r, ms));
  const ok = (b, t) => { console.log((b ? "ok  " : "FEHL ") + t); if (!b) fehler.push(t); };
  await warte(3000); w.eval('spracheSetzen("de")'); w.localStorage.setItem("nbes_erststart", "zu");
  await w.setzeModus("anlernen"); await warte(1200);
  const karten = d.querySelectorAll("#rechts .okarte");
  ok(karten.length >= 2, "Objektkarten: " + karten.length);
  ok(!!d.querySelector("#rechts .okarte .ok-balken i") && !!d.querySelector("#rechts .okarte .ok-ampel"), "Karte: Balken + Ampel");
  ok(!d.querySelector('#rechts [data-tat="aufnehmen"]') && !d.querySelector('#rechts [data-tat="training_dialog"]'), "keine doppelten Knoepfe in der Spalte");
  // zwei Fotos aufnehmen
  for (let i = 0; i < 2; i++) { $("opsHaupt").click(); await warte(1300); }
  await w.ladeDateien(); await w.aktualisieren(); await warte(600);
  const vorher = w.eval("DATEIEN.length");
  ok(vorher >= 2, "Fotos vorhanden: " + vorher);
  const x = d.querySelector('#rechts [data-tat="foto_weg"]');
  x.click(); await warte(400);
  ok(!$("rueckToast").hidden, "Rueckgaengig-Hinweis sichtbar");
  ok(d.querySelectorAll('#rechts [data-tat="foto_weg"]').length === vorher - 1, "Foto sofort ausgeblendet");
  d.querySelector('[data-tat="rueckgaengig"]').click(); await warte(400);
  ok($("rueckToast").hidden && d.querySelectorAll('#rechts [data-tat="foto_weg"]').length === vorher, "Rueckgaengig stellt das Foto wieder her");
  const st0 = await (await fetch(BASIS + "/api/prototypen?klasse=" + w.eval("AKTIV"))).json();
  ok(st0.dateien.length === vorher, "Server hat nichts geloescht");
  d.querySelector('#rechts [data-tat="foto_weg"]').click(); await warte(5600);
  const st1 = await (await fetch(BASIS + "/api/prototypen?klasse=" + w.eval("AKTIV"))).json();
  ok(st1.dateien.length === vorher - 1, "nach 5 s wirklich geloescht");
  // Objekt loeschen nutzt eigenen Dialog (kein Browser-confirm)
  d.querySelector('#rechts [data-tat="objekt_weg"]').click(); await warte(400);
  ok(!!d.querySelector(".schleier:not([hidden]) .fenster, .bestaetigen, [role=dialog]:not([hidden])"), "Objekt loeschen: eigener Dialog");
  d.body.dispatchEvent(new w.KeyboardEvent("keydown", { key: "Escape", bubbles: true })); await warte(300);
  // Pruefen: Live-Vorschau + gebuchte Pruefungen
  await w.setzeModus("betreiben"); await warte(1500);
  ok(/Live-Vorschau/.test(d.body.textContent) && /Gebuchte Prüfungen/.test(d.body.textContent), "Live-Vorschau und Gebuchte Pruefungen getrennt");
  d.body.dispatchEvent(new w.KeyboardEvent("keydown", { key: "?", bubbles: true })); await warte(200);
  ok(!$("dHilfe").hidden, "? oeffnet Tastenkuerzel-Hilfe");
  d.body.dispatchEvent(new w.KeyboardEvent("keydown", { key: "Escape", bubbles: true })); await warte(200);
  ok($("dHilfe").hidden, "Esc schliesst Hilfe");
  console.log(fehler.length ? "FEHLER: " + fehler.join(" | ") : "ANLERNEN_OK"); process.exit(fehler.length ? 1 : 0);
})();
