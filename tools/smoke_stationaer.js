// Rauchtest Profil stationaer (jsdom gegen den synthetischen Server, Standard :8765)
//   node tools/smoke_stationaer.js http://127.0.0.1:8765
// Erwartet: Server mit VORSA_PROFIL=stationaer (Standard).
const { JSDOM } = require("jsdom");
const BASIS = process.argv[2] || "http://127.0.0.1:8765";
const fehler = [];
(async () => {
  const html = await (await fetch(BASIS + "/")).text();
  const dom = new JSDOM(html, { url: BASIS + "/", runScripts: "dangerously", pretendToBeVisual: true,
    beforeParse(w) {
      w.fetch = (u, o) => fetch(new URL(u, BASIS).href, o);
      w.requestAnimationFrame = f => setTimeout(() => f(Date.now()), 16);
      w.HTMLCanvasElement.prototype.getContext = () => ({ fillRect(){}, drawImage(){}, save(){}, restore(){}, setLineDash(){}, strokeRect(){}, set fillStyle(v){}, set strokeStyle(v){}, set lineWidth(v){} });
      w.alert = m => fehler.push("alert: " + m);
      w.console.error = (...a) => fehler.push("console.error: " + a.join(" "));
      w.addEventListener("error", e => fehler.push("window.error: " + e.message));
    }});
  const w = dom.window, d = w.document, $ = id => d.getElementById(id);
  const ok = (b, was) => { if (!b) fehler.push("PRUEFUNG: " + was); else console.log("ok  " + was); };
  const warte = ms => new Promise(r => setTimeout(r, ms));
  await warte(3000);
  ok(w.eval("PROFIL") === "stationaer", "PROFIL stationaer uebernommen");
  ok(d.body.classList.contains("stationaer"), "body.stationaer gesetzt");
  ok($("navLinie").hidden, "Linienbetrieb aus der Seitenleiste");
  ok(/^Kamera$/.test(d.querySelector('#seitenNav .snav[data-modus="einrichten"] span').textContent.trim()), "Einrichten heisst Kamera");
  ok($("zoneKnopf").hidden, "Zonen-Knopf verborgen");
  const knopf = d.querySelector('[data-tat="pruefen"]');
  ok(!!knopf, "PRUEFEN-Knopf in der Pruef-Kachel");
  ok(knopf && knopf.disabled, "PRUEFEN ohne Teil im Bild gesperrt");
  ok(!!d.querySelector('[data-tat="pruef_ausloeser"][data-wert="auto"]'), "Ausloeser Hand/Auto");
  ok(/Kein Teil im Bild|Szene/.test((d.querySelector(".pu-status") || {}).textContent || ""), "Szenenstatus sichtbar");
  // Ausloeser umschalten -> Server persistiert, Kachel zeigt Auto an
  d.querySelector('[data-tat="pruef_ausloeser"][data-wert="auto"]').click(); await warte(800);
  const st = await (await fetch(BASIS + "/api/state")).json();
  ok(st.bereich.pruef.ausloeser === "auto", "Ausloeser auto am Server");
  ok(d.querySelector('[data-tat="pruef_ausloeser"][data-wert="auto"]').classList.contains("an"), "Auto in der Kachel aktiv");
  d.querySelector('[data-tat="pruef_ausloeser"][data-wert="hand"]').click(); await warte(800);
  // Leertaste in der Erkennung ruft pruefenJetzt (ohne Teil: Meldung, kein Fehler)
  d.body.dispatchEvent(new w.KeyboardEvent("keydown", { code: "Space", bubbles: true })); await warte(600);
  ok(true, "Leertaste ohne Teil: kein Fehler");
  // Einrichten-Modus: Zonen-Knopf bleibt verborgen
  d.querySelector('#seitenNav .snav[data-modus="einrichten"]').click(); await warte(800);
  ok($("zoneKnopf").hidden, "Zonen-Knopf auch im Einrichten verborgen");
  ok($("opsPageName").textContent === "Kamera", "Seitentitel Kamera");
  d.querySelector('#seitenNav .snav[data-modus="betreiben"]').click(); await warte(500);
  if (fehler.length) { console.log("FEHLER:\n  " + fehler.join("\n  ")); process.exit(1); }
  console.log("SMOKE_STATIONAER_OK");
  process.exit(0);
})();
