// Entwicklung: aus einer ui_vorschau.js-Datei eine STATISCHE Vorschau (ohne Skripte) bauen,
// optional nach einem JS-Aufruf (JS=...). Fuer Screenshots im Vorschaufenster.
//   NODE_PATH=/tmp/jt/node_modules JS='...' node tools/ui_statisch.js <vorschau.html> <wartezeit_ms> <ziel.html>
const { JSDOM } = require("jsdom"); const fs = require("fs");
const outer = fs.readFileSync(process.argv[2], "utf8");
const m = outer.match(/srcdoc="([\s\S]*)"><\/iframe>/);
const inner = m[1].replace(/&quot;/g, '"').replace(/&amp;/g, "&");
const dom = new JSDOM(inner, { url: "http://vorschau.local/", runScripts: "dangerously", pretendToBeVisual: true,
  beforeParse(w) { w.Response = Response; w.requestAnimationFrame = f => setTimeout(() => f(Date.now()), 16);
    w.HTMLCanvasElement.prototype.getContext = () => new Proxy({}, { get: () => () => {}, set: () => true });
    w.console.error = (...a) => console.log("ERR", ...a); w.addEventListener("error", e => console.log("ERR", e.message)); } });
setTimeout(() => { const w = dom.window;
  if (process.env.JS) w.eval(process.env.JS);
  setTimeout(() => {
    w.document.querySelectorAll("script").forEach(s => s.remove());
    const st = w.document.createElement("style"); st.textContent = "*,*::before,*::after{animation:none!important;transition:none!important}"; w.document.head.appendChild(st);
    const html = "<!doctype html>" + w.document.documentElement.outerHTML;
    const esc = html.replace(/&/g, "&amp;").replace(/"/g, "&quot;");
    fs.writeFileSync(process.argv[4], `<!doctype html><meta charset="utf-8"><style>html,body{margin:0;background:#111}iframe{border:0;width:1400px;height:900px;transform:scale(0.593);transform-origin:0 0}</style><iframe srcdoc="${esc}"></iframe>`);
    console.log("STATISCH", process.argv[4]); process.exit(0); }, 1500);
}, Number(process.argv[3] || 4000));
