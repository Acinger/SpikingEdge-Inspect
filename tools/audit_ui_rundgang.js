// Audit: Rundgang durch alle Modi, Dialoge, Looks und Sprachen - sammelt JS-Fehler.
//   node tools/audit_ui_rundgang.js http://127.0.0.1:8765
const { JSDOM } = require("jsdom"); const BASIS = process.argv[2] || "http://127.0.0.1:8765"; const fehler = [];
(async () => {
  const html = await (await fetch(BASIS + "/")).text();
  const dom = new JSDOM(html, { url: BASIS + "/", runScripts: "dangerously", pretendToBeVisual: true, resources: "usable",
    beforeParse(w) { w.fetch = (u, o) => fetch(new URL(u, BASIS).href, o); w.requestAnimationFrame = f => setTimeout(() => f(Date.now()), 16);
      w.HTMLCanvasElement.prototype.getContext = () => ({ fillRect(){}, drawImage(){}, save(){}, restore(){}, setLineDash(){}, strokeRect(){}, set fillStyle(v){}, set strokeStyle(v){}, set lineWidth(v){}, measureText(){ return { width: 10 }; }, fillText(){}, beginPath(){}, moveTo(){}, lineTo(){}, stroke(){}, arc(){}, fill(){}, clearRect(){}, translate(){}, scale(){}, rotate(){} });
      w.alert = m => fehler.push("alert: " + m); w.console.error = (...a) => fehler.push("console.error: " + a.join(" ").slice(0, 200));
      w.addEventListener("error", e => fehler.push("window.error: " + e.message)); w.addEventListener("unhandledrejection", e => fehler.push("unhandled: " + (e.reason && e.reason.message))); } });
  const w = dom.window, d = w.document, $ = id => d.getElementById(id); const warte = ms => new Promise(r => setTimeout(r, ms));
  const klick = (sel, ms = 350) => { const e = d.querySelector(sel); if (e) e.click(); return warte(ms); };
  await warte(3000);
  let schritte = 0;
  const schritt = async (name, fn) => { const vor = fehler.length; await fn(); schritte++; if (fehler.length > vor) console.log("  !! " + name + ": " + fehler.slice(vor).join(" / ")); };
  for (const sprache of ["de", "en"]) {
    w.eval(`spracheSetzen("${sprache}")`); await warte(300);
    for (const look of ["spikingedge", "industrie", "magna"]) {
      w.eval(`skinSetzen("${look}")`); await warte(200);
      for (const m of ["betreiben", "anlernen", "einrichten"]) {
        await schritt(`${sprache}/${look}/modus ${m}`, () => klick(`#seitenNav .snav[data-modus="${m}"]`, 900));
        await schritt("kam-leiste", async () => { await klick("#kamHauptKnopf"); await klick("#kamHauptKnopf"); });
        await schritt("ansicht-menue", async () => { await klick("#ansichtKnopf"); await klick("#ansichtKnopf"); });
        await schritt("rechtsklick", async () => { $("bild").dispatchEvent(new w.MouseEvent("contextmenu", { bubbles: true, cancelable: true, clientX: 200, clientY: 200 })); await warte(200); d.body.dispatchEvent(new w.MouseEvent("pointerdown", { bubbles: true })); await warte(100); });
        await schritt("details auf", async () => { d.querySelectorAll("details").forEach(x => { x.open = true; }); await warte(200); });
        for (const pane of ["details", "diagnose", "pruefung"]) await schritt("pane " + pane, () => klick(`[data-ops-pane="${pane}"]`, 400));
      }
      await schritt("linie-ansicht", async () => { await klick("#navLinie", 900); await klick('#seitenNav .snav[data-modus="betreiben"]', 500); });
      await schritt("rezepte", async () => { await klick('[data-tat="rezepte"]', 700); await klick('[data-tat="rezepte"]', 200); const dr = $("dRezepte"); if (dr) dr.hidden = true; });
      await schritt("alarme", async () => { await klick('[data-tat="alarme"]', 700); const da = $("dAlarme"); if (da) da.hidden = true; });
      await schritt("zustand", async () => { await klick("#navZustand", 700); for (const id of ["allgemein", "kamera", "erkennung", "programme", "eaio", "sps", "benutzer", "diagnose", "wartung", "hardware"]) await klick(`#eNav button[data-id="${id}"]`, 300); const de = $("dEinstellungen"); if (de) de.hidden = true; });
      await schritt("analyse", async () => { await klick("#opsAnalysisButton", 700); const da = $("dOpsAnalyse"); if (da) da.hidden = true; });
      for (const t of ["arm", "training", "messen", "einstellungen"]) await schritt("dialog " + t, async () => { await klick(`[data-tat="${t}"]`, 500); d.querySelectorAll(".schleier").forEach(s => { s.hidden = true; }); });
      await schritt("betriebsansicht", async () => { await klick("#betriebKnopf", 500); await klick("#betriebKnopf", 300); });
      await schritt("vollbild", async () => { await klick('[data-tat="vollbild"]', 200); });
    }
  }
  await schritt("sprache de zurueck", async () => { w.eval('spracheSetzen("de")'); w.eval('skinSetzen("spikingedge")'); await warte(200); });
  const fehlend = [...w.I18N_FEHLEND].filter(s => !/^[A-Z0-9 ._×·%:/()-]+$|MetaTF|TensorFlow|cnn2snn|NPs|akida|\d+\.\d+\.\d+|^DE$|^EN$/.test(s));
  console.log(`Schritte: ${schritte}, JS-Fehler: ${fehler.length}, unuebersetzt (EN, bereinigt): ${fehlend.length}`);
  if (fehlend.length) console.log("  unuebersetzt: " + fehlend.slice(0, 60).join(" | "));
  if (fehler.length) { console.log("FEHLER:\n  " + [...new Set(fehler)].join("\n  ")); process.exit(1); }
  console.log("RUNDGANG_OK"); process.exit(0);
})();
