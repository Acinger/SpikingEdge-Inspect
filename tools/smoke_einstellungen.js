// Rauchtest Einstellungen (1.9.57): Reiter, Sprache/Look/Ton, Erkennungsregler, Pruefprogramm sichern + laden.
//   node tools/smoke_einstellungen.js http://127.0.0.1:8765
const { JSDOM } = require("jsdom"); const BASIS = process.argv[2] || "http://127.0.0.1:8765"; const fehler = [];
(async () => {
  const html = await (await fetch(BASIS + "/")).text();
  const dom = new JSDOM(html, { url: BASIS + "/", runScripts: "dangerously", pretendToBeVisual: true, resources: "usable",
    beforeParse(w) { w.fetch = (u, o) => fetch(new URL(u, BASIS).href, o); w.requestAnimationFrame = f => setTimeout(() => f(Date.now()), 16);
      w.HTMLCanvasElement.prototype.getContext = () => new Proxy({}, { get: () => () => {}, set: () => true });
      w.alert = () => {}; w.console.error = (...a) => fehler.push(a.join(" ")); w.addEventListener("error", e => fehler.push(e.message)); } });
  const w = dom.window, d = w.document, $ = id => d.getElementById(id), warte = ms => new Promise(r => setTimeout(r, ms));
  const ok = (b, t) => { console.log((b ? "ok  " : "FEHL ") + t); if (!b) fehler.push(t); };
  await warte(3000); w.eval('spracheSetzen("de")'); await warte(300);
  $("navEinstellungen").click(); await warte(800);
  ok(!$("dEinstellungen").hidden, "Einstellungen offen");
  const reiter = [...$("eNav").querySelectorAll("button")].map(b => b.dataset.id);
  ok(reiter.join() === "allgemein,kamera,erkennung,programme,eaio,sps,benutzer,hardware,diagnose,wartung", "10 Reiter: " + reiter.join());
  ok(/Sprache/.test($("eInhalt").textContent) && /Darstellung/.test($("eInhalt").textContent), "Allgemein: Sprache + Darstellung");
  d.querySelector('[data-tat="sprache_setzen"][data-wert="en"]').click(); await warte(600);
  ok(w.eval("SPRACHE") === "en" && /Language/.test($("eInhalt").textContent), "Sprache -> English, Reiter uebersetzt");
  d.querySelector('[data-tat="sprache_setzen"][data-wert="de"]').click(); await warte(600);
  d.querySelector('[data-tat="look_setzen"][data-wert="industrie"]').click(); await warte(300);
  ok(w.eval("skinAktiv()") === "industrie", "Darstellung -> Hell");
  d.querySelector('[data-tat="look_setzen"][data-wert="spikingedge"]').click(); await warte(300);
  d.querySelector('[data-tat="pruef_ton_setzen"][data-wert="0"]').click(); await warte(200);
  ok(w.eval("PRUEF_TON") === false && w.localStorage.getItem("nbes_pruef_ton") === "0", "Ton aus gemerkt");
  d.querySelector('[data-tat="pruef_ton_setzen"][data-wert="1"]').click(); await warte(200);
  // Erkennung
  d.querySelector('#eNav [data-id="erkennung"]').click(); await warte(400);
  const r = $("eInhalt").querySelector('input[data-regler="pruef_schwelle"]');
  ok(!!r, "Erkennung: Konfidenzregler");
  r.value = "55"; r.dispatchEvent(new w.Event("input", { bubbles: true })); await warte(1500);
  let st = await (await fetch(BASIS + "/api/state")).json();
  ok(Math.round((st.bereich.pruef.schwelle || 0) * 100) === 55, "Schwelle am Server 55 % (" + st.bereich.pruef.schwelle + ")");
  // Pruefprogramme
  d.querySelector('#eNav [data-id="programme"]').click(); await warte(1200);
  const feld = $("eInhalt").querySelector(".rz-name");
  ok(!!feld, "Pruefprogramme: Namensfeld");
  feld.value = "Smoke-Programm";
  $("eInhalt").querySelector('[data-tat="rezept_speichern"]:not([data-name])').click(); await warte(1500);
  const rz = await (await fetch(BASIS + "/api/rezepte")).json();
  ok(!!(rz.rezepte || {})["Smoke-Programm"], "Pruefprogramm gespeichert");
  ok(/Smoke-Programm/.test($("eInhalt").textContent), "Liste zeigt das neue Programm");
  // Wartung: Komplettsicherung (1.9.63)
  d.querySelector('#eNav [data-id="wartung"]').click(); await warte(400);
  ok(!!$("eInhalt").querySelector('[data-tat="sicherung_laden"]') && !!$("eInhalt").querySelector("[data-sicherung-datei]"), "Wartung: Sicherung herunterladen + einspielen");
  // Zustand oeffnet Hardware
  $("dEinstellungen").hidden = true;
  $("navZustand").click(); await warte(600);
  ok(!$("dEinstellungen").hidden && w.eval("ABSCHNITT") === "hardware", "Zustand -> Reiter Hardware");
  ok(/Software/.test($("eInhalt").textContent), "Hardware zeigt Software/Version");
  $("dEinstellungen").hidden = true;
  // Fussleiste: keine abgeschnittenen Woerter
  const lab = [...d.querySelectorAll(".ops-nav-icons .snav.klein span:not(#navSpracheLabel)")].map(s => w.getComputedStyle(s).display);
  ok(lab.every(x => x === "none"), "Fussleiste: nur Symbole");
  // Pruefprogramm wieder loeschen
  await fetch(BASIS + "/api/rezept_loeschen", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ name: "Smoke-Programm" }) });
  await hole_schwelle_aus();
  async function hole_schwelle_aus() { await fetch(BASIS + "/api/pruef_einst", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ schwelle_aus: true }) }); }
  console.log(fehler.length ? "FEHLER: " + fehler.join(" | ") : "EINSTELLUNGEN_OK"); process.exit(fehler.length ? 1 : 0);
})();
