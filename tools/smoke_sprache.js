// Rauchtest Zweisprachigkeit (jsdom gegen den synthetischen Server)
//   node tools/smoke_sprache.js http://127.0.0.1:8765
const { JSDOM } = require("jsdom");
const BASIS = process.argv[2] || "http://127.0.0.1:8765";
const fehler = [];
(async () => {
  const html = await (await fetch(BASIS + "/")).text();
  const dom = new JSDOM(html, { url: BASIS + "/", runScripts: "dangerously", pretendToBeVisual: true, resources: "usable",
    beforeParse(w) {
      w.fetch = (u, o) => fetch(new URL(u, BASIS).href, o);
      w.requestAnimationFrame = f => setTimeout(() => f(Date.now()), 16);
      w.HTMLCanvasElement.prototype.getContext = () => ({ fillRect(){}, drawImage(){}, save(){}, restore(){}, setLineDash(){}, strokeRect(){}, set fillStyle(v){}, set strokeStyle(v){}, set lineWidth(v){} });
      w.alert = m => fehler.push("alert: " + m);
      w.console.error = (...a) => fehler.push("console.error: " + a.join(" "));
      w.addEventListener("error", e => fehler.push("window.error: " + e.message));
      Object.defineProperty(w.navigator, "language", { value: "en-US" });
    }});
  const w = dom.window, d = w.document, $ = id => d.getElementById(id);
  const ok = (b, was) => { if (!b) fehler.push("PRUEFUNG: " + was); else console.log("ok  " + was); };
  const warte = ms => new Promise(r => setTimeout(r, ms));
  await warte(3500);
  ok(!!w.SPRACHEN && !!w.SPRACHEN.en, "Woerterbuch geladen (/static/sprache_en.js)");
  ok(w.eval("SPRACHE") === "en", "Vorgabe aus navigator.language: en");
  ok(d.documentElement.lang === "en", "html lang=en");
  const nav = [...d.querySelectorAll("#seitenNav .snav span")].map(e => e.textContent.trim());
  ok(nav.includes("Inspection") && nav.includes("Status") && nav.includes("Messages"), "Seitenleiste englisch: " + nav.join(", "));
  ok($("opsPageName").textContent === "Inspection", "Seitentitel Inspection");
  ok(d.querySelector('[data-tat="pruefen"]').textContent.trim() === "INSPECT", "PRUEFEN -> INSPECT");
  ok(/Manual: button or space bar/.test(d.querySelector(".pu-ausloeser .ltakt").getAttribute("title")), "title-Attribut uebersetzt");
  ok($("navSpracheLabel").textContent === "DE", "Umschalter zeigt DE als Ziel");
  const fehlend1 = [...w.I18N_FEHLEND];
  console.log("    fehlende Uebersetzungen (sichtbar beim Start):", fehlend1.length, fehlend1.slice(0, 80).join(" | "));
  // Moduswechsel: neu aufgebaute Spalten werden uebersetzt
  d.querySelector('#seitenNav .snav[data-modus="anlernen"]').click(); await warte(1200);
  ok($("opsPageName").textContent === "Objects & learning", "Modus Lernen: Titel uebersetzt");
  ok(!/Foto aufnehmen/.test(d.body.textContent) || /Take photo/.test(d.body.textContent), "Lernmodus-Knoepfe uebersetzt");
  d.querySelector('#seitenNav .snav[data-modus="betreiben"]').click(); await warte(800);
  // Umschalten auf Deutsch stellt alles zurueck
  $("navSprache").click(); await warte(600);
  ok(w.eval("SPRACHE") === "de" && d.documentElement.lang === "de", "Umschalter -> de");
  ok($("opsPageName").textContent === "Erkennung", "Titel wieder Erkennung");
  ok(d.querySelector('[data-tat="pruefen"]').textContent.trim() === "PRÜFEN", "Knopf wieder PRÜFEN");
  ok(/Hand: Knopf oder Leertaste/.test(d.querySelector(".pu-ausloeser .ltakt").getAttribute("title")), "title wieder deutsch");
  ok(w.localStorage.getItem("nbes_sprache") === "de", "Sprache gemerkt");
  $("navSprache").click(); await warte(600);
  ok(w.eval("SPRACHE") === "en" && d.querySelector('[data-tat="pruefen"]').textContent.trim() === "INSPECT", "zurueck auf en");
  // Zustand-Dialog
  $("navZustand").click(); await warte(800);
  ok(/Hardware/.test($("eInhalt").innerHTML), "Zustand oeffnet");
  const fehlend2 = [...w.I18N_FEHLEND].filter(x => !fehlend1.includes(x));
  console.log("    weitere fehlende (Lernen, Zustand):", fehlend2.length, fehlend2.slice(0, 80).join(" | "));
  if (fehler.length) { console.log("FEHLER:\n  " + fehler.join("\n  ")); process.exit(1); }
  console.log("SMOKE_SPRACHE_OK");
  process.exit(0);
})();
