// Rauchtest 1.9.71: Fortschrittsbalken eines Laufs - Prozent + Farbe nach Stand (gross unterm Bild, Training-Dialog).
//   node tools/smoke_laufbalken.js http://127.0.0.1:8765
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
  const box = $("balken").parentNode;
  // laufend, 56 % gesamt
  w.eval(`LAUF = { name: "M3-Training", laeuft: true, fertig: false, ok: null, phase: "Training", schritt: 150, schritte: 300, anteil: 0.5, gesamt: 0.56 }; zeichneErgebnis()`);
  ok(box.classList.contains("lb-laeuft") && $("balken").style.width === "56%", `laeuft: blau, Breite ${$("balken").style.width}`);
  ok(/56 %/.test($("satz").textContent) && /Schritt 150 von 300/.test($("satz").textContent), "Prozent und Schritt in der Zeile");
  // unbestimmte Phase (kein gesamt, keine Schritte)
  w.eval(`LAUF = { name: "M3-Training", laeuft: true, fertig: false, ok: null, phase: "TensorFlow laden", schritt: 0, schritte: 0, anteil: 0, gesamt: null }; zeichneErgebnis()`);
  ok(box.classList.contains("lb-unbestimmt") && $("balken").style.width === "100%", "unbestimmt: pulsierender Vollbalken");
  // Fotos freistellen mit Fortschritt -> gesamt
  w.eval(`LAUF = { name: "M3-Training", laeuft: true, fertig: false, ok: null, phase: "Fotos freistellen", schritt: 60, schritte: 121, anteil: 0.496, gesamt: 0.074 }; zeichneErgebnis()`);
  ok(box.classList.contains("lb-laeuft") && $("balken").style.width === "7%" && /7 %/.test($("satz").textContent), "Freistellen: 7 % gesamt sichtbar (nicht 0 %)");
  // Dialog: fertig gruen, Fehler rot
  w.eval(`LAUF = { name: "M3-Training", laeuft: false, fertig: true, ok: true, phase: "Auf den AKD1500 legen", schritt: 0, schritte: 0, anteil: 0, gesamt: 1, ergebnis: { ok: true } }; DIALOG_LAUF = true; $("dTraining").hidden = false; zeichneTraining()`);
  let mb = $("tKoerper").querySelector(".mini-balken");
  ok(mb && mb.classList.contains("lb-fertig") && mb.querySelector("i").style.width === "100%" && /100 %/.test($("tKoerper").textContent), "Dialog fertig: gruen, 100 %");
  w.eval(`LAUF = { name: "M3-Training", laeuft: false, fertig: true, ok: false, phase: "Quantisieren", schritt: 0, schritte: 0, anteil: 0, gesamt: 0.9, grund: "Quantisieren: x", ergebnis: { ok: false, grund: "x" } }; zeichneTraining()`);
  mb = $("tKoerper").querySelector(".mini-balken");
  ok(mb && mb.classList.contains("lb-fehler"), "Dialog Fehler: rot");
  // nach dem Lauf: grosse Zeile ohne Laufklassen
  w.eval(`LAUF = null; DIALOG_LAUF = false; $("dTraining").hidden = true; zeichneErgebnis()`);
  ok(!box.classList.contains("lb-aktiv"), "ohne Lauf: Balken wieder neutral");
  console.log(fehler.length ? "FEHLER: " + fehler.join(" | ") : "LAUFBALKEN_OK"); process.exit(fehler.length ? 1 : 0);
})();
