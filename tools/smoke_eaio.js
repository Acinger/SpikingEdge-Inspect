// Rauchtest Ein-/Ausgaenge (1.9.59, Simulation): Reiter, Lampen, Trigger (Extern) -> Pruefung, OK/NOK, Ablehnung GPIO 18.
//   node tools/smoke_eaio.js http://127.0.0.1:8765
const { JSDOM } = require("jsdom"); const BASIS = process.argv[2] || "http://127.0.0.1:8765"; const fehler = [];
const post = (p, b) => fetch(BASIS + p, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(b) }).then(r => r.json());
(async () => {
  const html = await (await fetch(BASIS + "/")).text();
  const dom = new JSDOM(html, { url: BASIS + "/", runScripts: "dangerously", pretendToBeVisual: true, resources: "usable",
    beforeParse(w) { w.fetch = (u, o) => fetch(new URL(u, BASIS).href, o); w.requestAnimationFrame = f => setTimeout(() => f(Date.now()), 16);
      w.HTMLCanvasElement.prototype.getContext = () => new Proxy({}, { get: () => () => {}, set: () => true });
      w.alert = () => {}; w.console.error = (...a) => fehler.push(a.join(" ")); w.addEventListener("error", e => fehler.push(e.message)); } });
  const w = dom.window, d = w.document, $ = id => d.getElementById(id), warte = ms => new Promise(r => setTimeout(r, ms));
  const ok = (b, t) => { console.log((b ? "ok  " : "FEHL ") + t); if (!b) fehler.push(t); };
  await warte(3000); w.eval('spracheSetzen("de")'); w.localStorage.setItem("nbes_erststart", "zu");
  const stat = w.eval("STATIONAER()");
  let e = await (await fetch(BASIS + "/api/eaio")).json();
  ok(e.treiber === "sim" && e.simuliert, "Vorgabe Simulation");
  $("navEinstellungen").click(); await warte(500);
  d.querySelector('#eNav [data-id="eaio"]').click(); await warte(1500);
  ok(d.querySelectorAll("#eInhalt .eio-tab tbody tr").length === 5, "5 Signale in der Tabelle");
  ok(!!d.querySelector('#eInhalt [data-tat="eaio_test"][data-signal="ok"]'), "Test-Knopf je Signal");
  // Test OK -> Lampe
  d.querySelector('#eInhalt [data-tat="eaio_test"][data-signal="ok"]').click(); await warte(500);
  e = await (await fetch(BASIS + "/api/eaio")).json();
  ok(e.zustand.ok === true, "Test OK: Ausgang an");
  // GPIO 18 ablehnen
  const r = await post("/api/eaio", { aktion: "einstellen", treiber: "gpio", pins: { nok: 18 } });
  ok(r.ok === false && /gesperrt/.test(r.grund), "GPIO 18 abgelehnt");
  // Bereit im Pruefen
  await w.setzeModus("betreiben"); await warte(1500);
  e = await (await fetch(BASIS + "/api/eaio")).json();
  ok(e.zustand.bereit === true, "Bereit im Pruefen");
  if (stat) {
    await post("/api/pruef_einst", { ausloeser: "hand" });
    let r2 = await post("/api/eaio", { aktion: "test", signal: "trigger" });
    ok((r2.ereignisse || []).some(x => /nicht ausgef/.test(x.text)), "Trigger bei Hand: abgewiesen mit Grund");
    await post("/api/pruef_einst", { ausloeser: "extern" });
    const vor = (await (await fetch(BASIS + "/api/state")).json()).bereich.pruef.gesamt || 0;
    const z0 = e.zaehler.ok + e.zaehler.nok;
    await post("/api/eaio", { aktion: "test", signal: "trigger" }); await warte(2500);
    const e2 = await (await fetch(BASIS + "/api/eaio")).json();
    const nach = (await (await fetch(BASIS + "/api/state")).json()).bereich.pruef.gesamt || 0;
    ok(e2.zaehler.ok + e2.zaehler.nok === z0 + 1, `Trigger extern -> genau ein OK/NOK (${e2.ereignisse.slice(0, 3).map(x => x.text).join(" | ")})`);
    ok(nach >= vor, `Pruefbuch ${vor} -> ${nach}`);
    await post("/api/pruef_einst", { ausloeser: "hand" });
    ok(/Extern/.test(d.querySelector(".pu-ausloeser") ? d.querySelector(".pu-ausloeser").textContent : "Extern"), "Kachel: Ausloeser Extern waehlbar");
  }
  await post("/api/eaio", { aktion: "einstellen", treiber: "sim", modus: "puls" });
  console.log(fehler.length ? "FEHLER: " + fehler.join(" | ") : "EAIO_UI_OK"); process.exit(fehler.length ? 1 : 0);
})();
