// Statische UI-Vorschau: zeichnet alle API-Antworten eines laufenden (synthetischen)
// Servers auf und baut daraus EINE in sich geschlossene HTML-Datei, die ohne Server
// rendert (fetch und Bildquellen werden auf die Aufzeichnung umgelenkt).
//   node tools/ui_vorschau.js http://127.0.0.1:8765 <ziel.html> [modus] [sprache]
// modus: betreiben | anlernen | einrichten ; sprache: de | en
// Nur fuer Entwicklung/Screenshots - nicht Teil der Anlage.
const { JSDOM } = require("jsdom"); const fs = require("fs");
const BASIS = process.argv[2] || "http://127.0.0.1:8765";
const ZIEL = process.argv[3] || "vorschau.html";
const MODUS = process.argv[4] || "betreiben";
const SPRACHE = process.argv[5] || "de";
const b64 = async (u) => Buffer.from(await (await fetch(BASIS + u)).arrayBuffer()).toString("base64");
(async () => {
  const aufz = {};               // pfad -> antworttext (letzte gewinnt)
  const html = await (await fetch(BASIS + "/")).text();
  const dom = new JSDOM(html, { url: BASIS + "/", runScripts: "dangerously", pretendToBeVisual: true, resources: "usable",
    beforeParse(w) {
      w.fetch = async (u, o) => {
        const url = new URL(u, BASIS); const r = await fetch(url.href, o);
        const t = await r.clone().text();
        if (url.pathname.startsWith("/api/") && (r.headers.get("content-type") || "").includes("json")) aufz[url.pathname] = t;
        return r;
      };
      w.requestAnimationFrame = f => setTimeout(() => f(Date.now()), 16);
      w.HTMLCanvasElement.prototype.getContext = () => new Proxy({}, { get: () => () => {}, set: () => true });
      w.alert = () => {}; w.confirm = () => true;
    } });
  const w = dom.window, warte = ms => new Promise(r => setTimeout(r, ms));
  await warte(3000);
  w.eval(`spracheSetzen("${SPRACHE}")`);
  w.eval(`setzeModus("${MODUS}")`); await warte(2500);
  const snap = await b64("/api/snapshot");
  const sprache = await (await fetch(BASIS + "/static/sprache_en.js")).text();
  const icon = await b64("/static/se_icon.webp");
  const stub = `<script>(function(){
  var A=${JSON.stringify(aufz).replace(/</g, "\\u003c")}, SNAP="data:image/jpeg;base64,${snap}", ICON="data:image/webp;base64,${icon}";
  window.fetch=function(u,o){var p=new URL(String(u),"http://vorschau.local/").pathname;var t=A[p]; if(t==null)t='{"ok":true}';
    return Promise.resolve(new Response(t,{status:200,headers:{"Content-Type":"application/json"}}));};
  var d=Object.getOwnPropertyDescriptor(HTMLImageElement.prototype,"src");
  Object.defineProperty(HTMLImageElement.prototype,"src",{get:d.get,set:function(v){v=String(v);
    if(v.indexOf("/api/snapshot")>=0||v.indexOf("/api/vorschau")>=0||v.indexOf("/api/prototyp")>=0)v=SNAP;
    else if(v.indexOf("se_icon")>=0)v=ICON; d.set.call(this,v);}});
  try{localStorage.setItem("nbes_sprache","${SPRACHE}")}catch(e){}
  window.__VORSCHAU_MODUS="${MODUS}";
  document.addEventListener("DOMContentLoaded",function(){setTimeout(function(){try{setzeModus("${MODUS}")}catch(e){}},400);
    setTimeout(function(){try{${(process.env.NACH_JS || "").replace(/</g, "\\u003c")}}catch(e){console.error(e)}},700)});
})();</script>`;
  let out = html.replace(/(<meta charset="[^"]*">)/i, "$1" + stub)
    .replace(/<script src="\/static\/sprache_en\.js[^"]*"><\/script>/, "<script>" + sprache.replace(/<\/script>/g, "<\\/script>") + "</script>")
    .replace(/src="\/static\/se_icon\.webp"/g, `src="data:image/webp;base64,${icon}"`)
    .replace(/<link[^>]+fonts\.googleapis[^>]*>/g, "");
  // Vorschaufenster ist ~840 px breit: die Seite in einem 1400x900-iframe rendern und verkleinern,
  // damit das Desktop-Layout (nicht das schmale) zu sehen ist. BREITE=375 fuer Telefon.
  const B = +(process.env.BREITE || 1400), H = +(process.env.HOEHE || 900), S = Math.min(1, 830 / B);
  const esc = out.replace(/&/g, "&amp;").replace(/"/g, "&quot;");
  out = `<!doctype html><meta charset="utf-8"><style>html,body{margin:0;background:#111}iframe{border:0;width:${B}px;height:${H}px;transform:scale(${S});transform-origin:0 0}</style><iframe srcdoc="${esc}"></iframe>`;
  fs.writeFileSync(ZIEL, out);
  console.log("VORSCHAU", ZIEL, Math.round(out.length / 1024) + " kB", Object.keys(aufz).length + " API-Antworten");
  process.exit(0);
})();
