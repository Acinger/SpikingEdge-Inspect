// Rauchtest Drehknopf (1.9.66): Knopf in der Zoomleiste, gesperrt im Pruefen, Winkel im Zustand.
//   node tools/smoke_drehen.js http://127.0.0.1:8765   (dreht am Ende auf 0 zurueck)
const { JSDOM } = require("jsdom"); const BASIS = process.argv[2] || "http://127.0.0.1:8765"; const fehler = [];
const ok = (b, t) => { console.log((b ? "ok  " : "FEHL ") + t); if (!b) fehler.push(t); };
const warte = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const html = await (await fetch(BASIS + "/")).text();
  const dom = new JSDOM(html, { url: BASIS + "/", runScripts: "dangerously", pretendToBeVisual: true, resources: "usable",
    beforeParse(w) { w.fetch = (u, o) => fetch(new URL(u, BASIS).href, o); w.requestAnimationFrame = f => setTimeout(() => f(Date.now()), 16);
      w.HTMLCanvasElement.prototype.getContext = () => new Proxy({}, { get: () => () => {}, set: () => true });
      w.alert = () => {}; w.console.error = (...m) => fehler.push(m.join(" ")); w.addEventListener("error", ev => fehler.push(ev.message)); } });
  const w = dom.window, d = w.document, $ = id => d.getElementById(id);
  await warte(3500); w.eval("spracheSetzen('de')");
  const b = $("zoomDrehen");
  ok(!!b && b.parentNode.id === "zoomLeiste", "Drehknopf in der Zoomleiste");
  await w.eval("setzeModus('betreiben')"); await warte(1500);
  ok(b.disabled && /nur in Einrichten/.test(b.title), "im Pruefen gesperrt, mit Grund");
  await w.eval("setzeModus('einrichten')"); await warte(1500);
  ok(!b.disabled, "im Einrichten aktiv");
  const vor = (await (await fetch(BASIS + "/api/state")).json()).drehung;
  b.click(); await warte(1500);
  const nach = (await (await fetch(BASIS + "/api/state")).json()).drehung;
  ok(nach === (vor + 90) % 360, `gedreht ${vor} -> ${nach}`);
  ok($("zoomDrehWert").textContent === (nach ? nach + "°" : "") && b.classList.contains("gedreht") === !!nach, "Winkel am Knopf");
  // zurueck auf 0
  for (let i = 0; i < 4 && (await (await fetch(BASIS + "/api/state")).json()).drehung; i++)
    await fetch(BASIS + "/api/drehen", { method: "POST", headers: { "content-type": "application/json" }, body: "{}" });
  await w.eval("setzeModus('betreiben')"); await warte(800);   // Ausgangslage fuer folgende Smokes
  console.log(fehler.length ? "FEHLER: " + fehler.join(" | ") : "DREHEN_OK"); process.exit(fehler.length ? 1 : 0);
})();
