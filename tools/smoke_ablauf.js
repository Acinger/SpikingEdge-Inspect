// Rauchtest Ablauf (1.9.56): Schritte in der Seitenleiste, Hauptknopf je Seite, ⋯-Menue, Erste Schritte.
//   node tools/smoke_ablauf.js http://127.0.0.1:8765
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
  const schritte = [...d.querySelectorAll("#seitenNav .snav.schritt")].map(b => b.dataset.modus);
  ok(schritte.join() === "einrichten,anlernen,betreiben", "Schritte in Ablauf-Reihenfolge: " + schritte.join());
  for (const [m, titel, haupt] of [["einrichten", "Einrichten", "leerbild"], ["anlernen", "Anlernen", "aufnehmen"], ["betreiben", "Prüfung", null]]) {
    d.querySelector(`#seitenNav .snav[data-modus="${m}"]`).click(); await warte(1300);
    ok($("opsPageName").textContent === titel, `Titel ${titel}`);
    const hk = $("opsHaupt");
    if (haupt) ok(!hk.hidden && hk.dataset.tat === haupt, `Hauptknopf ${m}: ${hk.dataset.tat} „${hk.textContent}“`);
    else ok(w.eval("STATIONAER()") ? (!hk.hidden && hk.dataset.tat === "pruefen") : true, "Hauptknopf Pruefen (stationaer)");
    ok(d.querySelectorAll(".ops-actions > button:not([hidden]):not(#opsNeben):not(#opsHaupt)").length <= 1, `${m}: hoechstens ein weiterer sichtbarer Kopfknopf`);
  }
  ok($("linieKnopf").hidden, "Linie-Knopf ausserhalb Linienbetrieb verborgen");
  ok($("armKnopf").hidden, "Arm-Knopf ausserhalb Linienbetrieb verborgen");
  // ⋯-Menue
  ok($("opsMehr").hidden, "⋯-Menue zu");
  $("opsMehrKnopf").click(); await warte(200);
  ok(!$("opsMehr").hidden && !!$("opsMehr").querySelector("#betriebKnopf") && !!$("opsMehr").querySelector("#opsAnalysisButton"), "⋯-Menue offen: Bedienansicht + Analyse");
  d.body.dispatchEvent(new w.MouseEvent("pointerdown", { bubbles: true })); await warte(100);
  ok($("opsMehr").hidden, "Klick daneben schliesst ⋯-Menue");
  // Erste Schritte
  w.eval("erstStartZeigen(true)"); await warte(1300);
  ok(!$("erstStart").hidden && $("erstStartListe").children.length === 6, "Erste Schritte: 6 Punkte");
  ok(/von 6 erledigt/.test($("erstStartStand").textContent), "Erste Schritte: Stand " + $("erstStartStand").textContent);
  const b = $("erstStartListe").querySelector('[data-tat="erst_schritt"][data-nr="3"]');
  if (b) { b.click(); await warte(1300); ok(w.eval("MODUS") === "anlernen" && $("erstStart").hidden, "Punkt 4 fuehrt zum Anlernen und schliesst"); }
  w.eval("erstStartZeigen(true)"); await warte(200);
  d.querySelector('[data-tat="erststart_zu"]').click(); await warte(200);
  ok($("erstStart").hidden && w.localStorage.getItem("nbes_erststart") === "zu", "Schliessen merkt sich das");
  // Kopf-Chip Klartext
  ok(!/NPs/.test($("cModell").textContent), "Kopf: Gelernt-Chip in Klartext („" + $("cModell").textContent + "“)");
  // Naechster Schritt im Pruefen ohne Gelerntes
  await w.setzeModus("betreiben"); await warte(1200);
  const gel = w.eval("ablaufStand().gelernt");
  ok(gel || /Noch nichts gelernt/.test($("rechts").textContent), "Pruefen ohne Gelerntes: Karte „Noch nichts gelernt“");
  w.localStorage.removeItem("nbes_erststart");
  console.log(fehler.length ? "FEHLER: " + fehler.join(" | ") : "ABLAUF_OK"); process.exit(fehler.length ? 1 : 0);
})();
