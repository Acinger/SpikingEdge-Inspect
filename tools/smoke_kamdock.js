// Rauchtest Kamera-Dock (1.9.52): Kamera-Knopf klappt das Dock auf, vier Spalten, Regler wirken, Pfeil schliesst.
//   node tools/smoke_kamdock.js http://127.0.0.1:8765
const { JSDOM } = require("jsdom"); const BASIS = process.argv[2] || "http://127.0.0.1:8765"; const fehler = [];
(async () => {
  const html = await (await fetch(BASIS + "/")).text();
  const dom = new JSDOM(html, { url: BASIS + "/", runScripts: "dangerously", pretendToBeVisual: true, resources: "usable",
    beforeParse(w) { w.fetch = (u, o) => fetch(new URL(u, BASIS).href, o); w.requestAnimationFrame = f => setTimeout(() => f(Date.now()), 16);
      w.HTMLCanvasElement.prototype.getContext = () => ({ fillRect(){}, drawImage(){}, save(){}, restore(){}, setLineDash(){}, strokeRect(){}, set fillStyle(v){}, set strokeStyle(v){}, set lineWidth(v){} });
      w.alert = () => {}; w.console.error = (...a) => fehler.push(a.join(" ")); w.addEventListener("error", e => fehler.push(e.message)); } });
  const w = dom.window, d = w.document, $ = id => d.getElementById(id); const warte = ms => new Promise(r => setTimeout(r, ms)); await warte(3000);
  const ok = (b, t) => { console.log((b ? "ok  " : "FEHL ") + t); if (!b) fehler.push(t); };
  w.eval('spracheSetzen("de")'); w.eval("kamDockSetzen(false)"); w.eval("fensterSetzen(100)"); await warte(600);
  ok(!$("videoteil").classList.contains("dockoffen"), "Dock zu beim Start");
  ok($("opsObservation").hidden, "Betrieb: Erkennungsdetails unter dem Bild verborgen");
  $("kamHauptKnopf").click(); await warte(500);
  ok($("videoteil").classList.contains("dockoffen") && w.eval("KAMDOCK_OFFEN"), "Kamera-Knopf oeffnet Dock");
  ok($("kamDockInhalt").querySelectorAll(".kd-sp").length === 4, "vier Spalten");
  ok(/Bild/.test($("kamDockInhalt").textContent) && /Farbe/.test($("kamDockInhalt").textContent) && /Fenster/.test($("kamDockInhalt").textContent) && /Hintergrund/.test($("kamDockInhalt").textContent), "Spaltentitel Bild / Farbe / Fenster / Hintergrund");
  ok(!!$("kamDockInhalt").querySelector('[data-tat="leerbild"]') && !!$("kamDockInhalt").querySelector('[data-tat="rezept_speichern"]'), "Leerbild + als Pruefprogramm sichern im Dock");
  const r = $("kamDockInhalt").querySelector('input[data-regler="fenster"]'); r.value = "70"; r.dispatchEvent(new w.Event("input", { bubbles: true })); await warte(900);
  const st = await (await fetch(BASIS + "/api/state")).json(); ok(Math.round(st.bereich.fenster) === 70, "Fenster-Regler im Dock wirkt (" + st.bereich.fenster + ")");
  ok(/70 %/.test($("kamDockInhalt").querySelector(".kd-fenster-wert").textContent), "Dock zeigt 70 %");
  $("kamDock").querySelector('[data-tat="kamdock"]').click(); await warte(400);
  ok(!$("videoteil").classList.contains("dockoffen"), "Pfeil schliesst Dock");
  ok(w.localStorage.getItem("nbes_kamdock") === "0", "Zustand gemerkt");
  // Rechtsklick > Kamera-Leiste oeffnet Dock
  $("bild").dispatchEvent(new w.MouseEvent("contextmenu", { bubbles: true, cancelable: true, clientX: 300, clientY: 300 })); await warte(200);
  $("ansichtMenue").querySelector('[data-tat="feed_kam"][data-art="haupt"]').click(); await warte(300);
  ok($("videoteil").classList.contains("dockoffen") && $("ansichtMenue").hidden, "Rechtsklick > Kamera oeffnet Dock und schliesst Menue");
  // Lernmodus: Dock bleibt nutzbar, Details-Block sichtbar (nicht Betrieb)
  d.querySelector('#seitenNav .snav[data-modus="anlernen"]').click(); await warte(1000);
  ok(!$("opsObservation").hidden, "Lernen: Vorgang & Hinweise sichtbar");
  ok($("kamDockInhalt").querySelectorAll(".kd-sp").length === 4, "Dock auch im Lernen");
  d.querySelector('#seitenNav .snav[data-modus="betreiben"]').click(); await warte(500); w.eval("kamDockSetzen(false)"); w.eval("fensterSetzen(100)"); await warte(400);
  console.log(fehler.length ? "FEHLER: " + fehler.join(" | ") : "KAMDOCK_OK"); process.exit(fehler.length ? 1 : 0);
})();
