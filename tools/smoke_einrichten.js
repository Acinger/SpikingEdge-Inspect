// Rauchtest Einrichten-Spalte + Rechtsklick-Menue (1.9.50)
//   node tools/smoke_einrichten.js http://127.0.0.1:8765
const { JSDOM } = require("jsdom"); const BASIS = process.argv[2] || "http://127.0.0.1:8765"; const fehler = [];
(async () => {
  const html = await (await fetch(BASIS + "/")).text();
  const dom = new JSDOM(html, { url: BASIS + "/", runScripts: "dangerously", pretendToBeVisual: true, resources: "usable",
    beforeParse(w) { w.fetch = (u, o) => fetch(new URL(u, BASIS).href, o); w.requestAnimationFrame = f => setTimeout(() => f(Date.now()), 16);
      w.HTMLCanvasElement.prototype.getContext = () => ({ fillRect(){}, drawImage(){}, save(){}, restore(){}, setLineDash(){}, strokeRect(){}, set fillStyle(v){}, set strokeStyle(v){}, set lineWidth(v){} });
      w.alert = () => {}; w.console.error = (...a) => fehler.push(a.join(" ")); w.addEventListener("error", e => fehler.push(e.message)); } });
  const w = dom.window, d = w.document, $ = id => d.getElementById(id); const warte = ms => new Promise(r => setTimeout(r, ms)); await warte(3000);
  const ok = (b, t) => { console.log((b ? "ok  " : "FEHL ") + t); if (!b) fehler.push(t); };
  w.eval('spracheSetzen("de")'); w.eval("fensterSetzen(100)"); await warte(600);   // unabhaengig von vorherigen Laeufen
  // Rechtsklick im Betrieb
  $("bild").dispatchEvent(new w.MouseEvent("contextmenu", { bubbles: true, cancelable: true, clientX: 300, clientY: 300 })); await warte(200);
  ok(!$("ansichtMenue").hidden, "Rechtsklick oeffnet Menue");
  ok($("ansichtMenue").querySelectorAll(".schalt").length === 7, "7 Anzeige-Schalter im Menue");
  ok(!!$("ansichtMenue").querySelector('[data-tat="zoom_zurueck"]') && !!$("ansichtMenue").querySelector('[data-tat="pruefen"]'), "Aktionen: Zoom zurueck, Pruefen (stationaer/Betrieb)");
  ok(!$("ansichtMenue").querySelector('[data-tat="fenster_schritt"]'), "im Betrieb kein Fenster +/-");
  $("ansichtMenue").querySelector('[data-tat="zoom_zurueck"]').click(); await warte(100);
  ok($("ansichtMenue").hidden, "Aktion schliesst Menue");
  // Einrichten-Spalte
  d.querySelector('#seitenNav .snav[data-modus="einrichten"]').click(); await warte(1200);
  const r = $("rechts").textContent;
  ok(/Einrichtung|Setup/.test(r) && /Fenster groß genug|Bild scharf/.test(r), "Checkliste da");
  ok(/Kamera|Camera/.test(r) && (!!$("rechts").querySelector("input[data-fk]") || /Keine Kamera aktiv|No camera active/.test(r)), "Kamera-Block (Regler oder Hinweis ohne Kamera)");
  ok(/Leerbild/.test(r) && !!$("rechts").querySelector('[data-tat="leerbild"]'), "Leerbild-Block mit Knopf");
  ok(!!$("rechts").querySelector('input[data-regler="pruef_mehrbild"]'), "Bilder mitteln (stationaer)");
  ok(!!$("rechts").querySelector('input[data-regler="fenster"]'), "Aufnahmefenster-Regler");
  // Rechtsklick im Einrichten: Fenster +/- vorhanden
  $("bild").dispatchEvent(new w.MouseEvent("contextmenu", { bubbles: true, cancelable: true, clientX: 300, clientY: 300 })); await warte(200);
  ok(!!$("ansichtMenue").querySelector('[data-tat="fenster_schritt"]'), "Einrichten: Fenster +/- im Menue");
  $("ansichtMenue").querySelector('[data-tat="fenster_schritt"][data-schritt="-5"]').click(); await warte(500);
  const st = await (await fetch(BASIS + "/api/state")).json(); ok(Math.round(st.bereich.fenster) === 95, "Fenster − aus dem Menue wirkt (" + st.bereich.fenster + ")");
  d.querySelector('#seitenNav .snav[data-modus="betreiben"]').click(); await warte(500);
  console.log(fehler.length ? "FEHLER: " + fehler.join(" | ") : "EINRICHTEN_OK"); process.exit(fehler.length ? 1 : 0);
})();
