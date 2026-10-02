// Erntet alle sichtbaren deutschen Texte der UI (jsdom gegen den synthetischen
// Server) ueber moeglichst viele Ansichten hinweg. Ausgabe: JSON-Liste.
//   node tools/i18n_ernte.js http://127.0.0.1:8765 > /tmp/ernte.json
const { JSDOM } = require("jsdom");
const BASIS = process.argv[2] || "http://127.0.0.1:8765";
const texte = new Map();           // text -> Beispielkontext
function sammle(d, wo) {
  const walker = d.createTreeWalker(d.body, 5 /* ELEMENT|TEXT */);
  let n;
  while ((n = walker.nextNode())) {
    if (n.nodeType === 3) {
      const s = n.textContent.replace(/\s+/g, " ").trim();
      if (s.length >= 2 && /[A-Za-zÄÖÜäöüß]{2,}/.test(s) && !/^[a-z_]+$/.test(s)) {
        const p = n.parentElement;
        if (p && (p.tagName === "SCRIPT" || p.tagName === "STYLE")) continue;
        if (!texte.has(s)) texte.set(s, wo);
      }
    } else {
      for (const a of ["title", "placeholder", "aria-label", "alt", "data-tipp"]) {
        const v = n.getAttribute && n.getAttribute(a);
        if (v && v.trim().length >= 2 && /[A-Za-zÄÖÜäöüß]{2,}/.test(v) && !texte.has(v.trim())) texte.set(v.trim(), wo + "@" + a);
      }
      if (n.tagName === "INPUT" && (n.type === "button" || n.type === "submit") && n.value) texte.set(n.value, wo + "@value");
    }
  }
}
(async () => {
  const html = await (await fetch(BASIS + "/")).text();
  const dom = new JSDOM(html, { url: BASIS + "/", runScripts: "dangerously", pretendToBeVisual: true, resources: "usable",
    beforeParse(w) {
      w.fetch = (u, o) => fetch(new URL(u, BASIS).href, o);
      w.requestAnimationFrame = f => setTimeout(() => f(Date.now()), 16);
      w.HTMLCanvasElement.prototype.getContext = () => ({ fillRect(){}, drawImage(){}, save(){}, restore(){}, setLineDash(){}, strokeRect(){}, set fillStyle(v){}, set strokeStyle(v){}, set lineWidth(v){} });
      w.alert = () => {};
      w.console.error = () => {};
      w.addEventListener("error", () => {});
    }});
  const w = dom.window, d = w.document, $ = id => d.getElementById(id);
  const warte = ms => new Promise(r => setTimeout(r, ms));
  const klick = sel => { const e = d.querySelector(sel); if (e) e.click(); };
  await warte(3000);
  sammle(d, "start");
  for (const m of ["betreiben", "anlernen", "einrichten"]) {
    klick(`#seitenNav .snav[data-modus="${m}"]`); await warte(1200); sammle(d, "modus:" + m);
    for (const sel of ['[data-tat="feed_kam"]', '[data-ops-pane="details"]', '[data-ops-pane="pruefung"]', "#ansichtKnopf", "#kamHauptKnopf", "#lernzonenKnopf", "#betriebKnopf"]) {
      klick(sel); await warte(300); sammle(d, m + ":" + sel); klick(sel); await warte(150);
    }
    d.querySelectorAll("details").forEach(x => { x.open = true; }); await warte(300); sammle(d, m + ":details");
  }
  klick('#seitenNav .snav[data-modus="betreiben"]'); await warte(500);
  klick("#navLinie"); await warte(1200); sammle(d, "linie");
  klick('[data-tat="rezepte"]'); await warte(800); sammle(d, "rezepte"); klick('[data-tat="rezepte"]'); await warte(200);
  klick('[data-tat="alarme"]'); await warte(800); sammle(d, "alarme");
  klick("#navZustand"); await warte(800); sammle(d, "zustand:hardware");
  for (const id of ["diagnose", "wartung"]) { klick(`#eNav button[data-id="${id}"]`); await warte(400); sammle(d, "zustand:" + id); }
  klick("#opsAnalysisButton"); await warte(800); sammle(d, "analyse");
  for (const sel of ['[data-tat="arm"]', '[data-tat="training"]', '[data-tat="messen"]', '[data-tat="einstellungen"]', '[data-tat="look"]']) { klick(sel); await warte(500); sammle(d, sel); }
  d.querySelectorAll("details").forEach(x => { x.open = true; }); await warte(300); sammle(d, "details-alle");
  // alles, was in dialogen versteckt ist
  d.querySelectorAll("[hidden]").forEach(x => x.removeAttribute("hidden")); await warte(200); sammle(d, "hidden");
  const aus = [...texte.entries()].map(([t, wo]) => ({ t, wo }));
  process.stdout.write(JSON.stringify(aus, null, 0));
  process.exit(0);
})();
