// Rauchtest Aufnahmefenster am Bild (1.9.47): Leiste im Videokopf, Ecke, Lernzonen-Knopf.
//   node tools/smoke_fenster.js http://127.0.0.1:8765   (Server im Profil stationaer)
const { JSDOM } = require("jsdom"); const BASIS = process.argv[2] || "http://127.0.0.1:8765"; const fehler = [];
(async () => {
  const html = await (await fetch(BASIS + "/")).text();
  const dom = new JSDOM(html, { url: BASIS + "/", runScripts: "dangerously", pretendToBeVisual: true, resources: "usable",
    beforeParse(w) { w.fetch = (u, o) => fetch(new URL(u, BASIS).href, o); w.requestAnimationFrame = f => setTimeout(() => f(Date.now()), 16);
      w.HTMLCanvasElement.prototype.getContext = () => ({ fillRect(){}, drawImage(){}, save(){}, restore(){}, setLineDash(){}, strokeRect(){}, set fillStyle(v){}, set strokeStyle(v){}, set lineWidth(v){} });
      w.alert = () => {}; w.console.error = (...a) => fehler.push(a.join(" ")); w.addEventListener("error", e => fehler.push(e.message)); } });
  const w = dom.window, d = w.document, $ = id => d.getElementById(id); const warte = ms => new Promise(r => setTimeout(r, ms)); await warte(3000);
  const ok = (b, t) => { console.log((b ? "ok  " : "FEHL ") + t); if (!b) fehler.push(t); };
  ok($("fensterLeiste").hidden, "Betrieb: Fensterleiste verborgen");
  ok($("lernzonenKnopf").hidden, "Lernzonen-Knopf verborgen (stationaer)");
  d.querySelector('#seitenNav .snav[data-modus="anlernen"]').click(); await warte(1200);
  w.eval("fensterSetzen(100)"); await warte(600);
  ok(!$("fensterLeiste").hidden, "Lernen: Fensterleiste sichtbar: " + $("fensterLeisteWert").textContent);
  ok($("lernzonenKnopf").hidden, "Lernen: Lernzonen-Knopf bleibt verborgen");
  d.querySelector('[data-tat="fenster_schritt"][data-schritt="-5"]').click(); await warte(500);
  const st = await (await fetch(BASIS + "/api/state")).json(); ok(Math.round(st.bereich.fenster) === 95, "[-] -> Server fenster 95 (ist " + st.bereich.fenster + ")");
  ok(/95 %/.test($("fensterLeisteWert").textContent), "Leiste zeigt 95 %");
  w.eval("fensterSetzen(60)"); await warte(400); const st2 = await (await fetch(BASIS + "/api/state")).json(); ok(Math.round(st2.bereich.fenster) === 60, "fensterSetzen(60) -> Server 60");
  await warte(1200); const b = w.eval("Z.bereich"); const rx = (b.x + b.seite) / b.bild_breite, ry = (b.y + b.seite) / b.bild_hoehe;
  ok(!!w.eval(`anRahmenEcke(${rx - 0.005}, ${ry - 0.005})`), "Rahmenecke wird erkannt");
  ok(!w.eval(`anRahmenEcke(${(b.x + b.seite / 2) / b.bild_breite}, ${(b.y + b.seite / 2) / b.bild_hoehe})`), "Rahmenmitte ist keine Ecke");
  d.querySelector('#seitenNav .snav[data-modus="betreiben"]').click(); await warte(800); ok($("fensterLeiste").hidden, "zurueck im Betrieb: Leiste weg");
  console.log(fehler.length ? "FEHLER: " + fehler.join(" | ") : "FENSTER_OK"); process.exit(fehler.length ? 1 : 0);
})();
