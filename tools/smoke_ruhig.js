// Rauchtest 1.9.69: nichts springt im Zustandstakt (Lernzonen-Knopf, Erste Schritte).
//   node tools/smoke_ruhig.js http://127.0.0.1:8765
const { JSDOM } = require("jsdom"); const BASIS = process.argv[2] || "http://127.0.0.1:8765"; const fehler = [];
const ok = (b, t) => { console.log((b ? "ok  " : "FEHL ") + t); if (!b) fehler.push(t); };
const warte = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const html = await (await fetch(BASIS + "/")).text();
  const dom = new JSDOM(html, { url: BASIS + "/", runScripts: "dangerously", pretendToBeVisual: true,
    beforeParse(w) { w.fetch = (u, o) => fetch(new URL(u, BASIS).href, o); w.requestAnimationFrame = f => setTimeout(() => f(Date.now()), 16);
      w.HTMLCanvasElement.prototype.getContext = () => new Proxy({}, { get: () => () => {}, set: () => true });
      w.console.error = (...m) => fehler.push(m.join(" ")); w.addEventListener("error", ev => fehler.push(ev.message)); } });
  const w = dom.window, d = w.document, $ = id => d.getElementById(id);
  await warte(3500);
  await w.eval("setzeModus('anlernen')"); await warte(1500);
  // Lernzonen-Knopf: hidden darf sich im Takt nie aendern
  const lk = $("lernzonenKnopf"); let wechsel = 0, letzt = lk.hidden;
  new w.MutationObserver(() => { if (lk.hidden !== letzt) { wechsel++; letzt = lk.hidden; } }).observe(lk, { attributes: true, attributeFilter: ["hidden"] });
  for (let i = 0; i < 8; i++) { await w.eval("aktualisieren()"); await warte(150); }
  ok(wechsel === 0, `Lernzonen-Knopf bleibt ruhig (${wechsel} Wechsel, hidden=${lk.hidden})`);
  // Erste Schritte: 6/6 -> weg, kurzer Rueckfall auf 5/6 -> bleibt weg
  const ns = $("navStart");
  w.eval("ablaufStand = (orig => () => Object.assign(orig(), { erledigt: 6 }))(ablaufStand); ablaufMalen()");
  ok(ns.hidden, "6/6: Erste Schritte ausgeblendet");
  w.eval("ablaufStand = (orig => () => Object.assign(orig(), { erledigt: 5 }))(ablaufStand); ablaufMalen()");
  ok(ns.hidden, "kurzer Rueckfall auf 5/6: bleibt ausgeblendet");
  await w.eval("setzeModus('betreiben')"); await warte(500);
  console.log(fehler.length ? "FEHLER: " + fehler.join(" | ") : "RUHIG_OK"); process.exit(fehler.length ? 1 : 0);
})();
