// Rauchtest Rollen (1.9.60): PIN setzen, 403 fuer Bediener, Anmelden, Einrichter vs. Admin, Protokoll, UI-Bedienstation.
//   node tools/smoke_rollen.js http://127.0.0.1:8765   (setzt am Ende alles zurueck)
const { JSDOM } = require("jsdom"); const BASIS = process.argv[2] || "http://127.0.0.1:8765"; const fehler = [];
const ok = (b, t) => { console.log((b ? "ok  " : "FEHL ") + t); if (!b) fehler.push(t); };
const post = async (p, b, tok) => { const r = await fetch(BASIS + p, { method: "POST", headers: Object.assign({ "content-type": "application/json" }, tok ? { "X-SE-Token": tok } : {}), body: JSON.stringify(b || {}) }); return { code: r.status, j: await r.json() }; };
(async () => {
  let r = await (await fetch(BASIS + "/api/rollen")).json();
  ok(r.aktiv === false && r.rolle === "admin", "Vorgabe: Rollen aus, alles offen");
  ok((await post("/api/rollen", { aktion: "pin", rolle: "admin", pin: "12" })).j.ok === false, "zu kurzer PIN abgelehnt");
  ok((await post("/api/rollen", { aktion: "pin", rolle: "admin", pin: "2468" })).j.ok, "Admin-PIN gesetzt -> Rollen aktiv");
  r = await (await fetch(BASIS + "/api/rollen")).json();
  ok(r.aktiv && r.rolle === "bediener", "ohne Anmeldung: Bediener");
  let x = await post("/api/klasse_neu", { name: "verboten" });
  ok(x.code === 403 && x.j.rolle_noetig === "einrichter", "Bediener: Objekt anlegen -> 403");
  x = await post("/api/betriebsart", { art: "anlernen" });
  ok(x.code === 403, "Bediener: Anlernen -> 403");
  x = await post("/api/betriebsart", { art: "betreiben" });
  ok(x.code === 200, "Bediener: Pruefen erlaubt");
  ok((await post("/api/anmelden", { pin: "0000" })).j.ok === false, "falscher PIN abgelehnt");
  const a = (await post("/api/anmelden", { pin: "2468" })).j;
  ok(a.ok && a.rolle === "admin" && a.token, "Admin angemeldet");
  ok((await post("/api/rollen", { aktion: "pin", rolle: "einrichter", pin: "1357" }, a.token)).j.ok, "Einrichter-PIN gesetzt");
  const e = (await post("/api/anmelden", { pin: "1357" })).j;
  ok(e.ok && e.rolle === "einrichter", "Einrichter angemeldet");
  x = await post("/api/pruef_einst", { unbekannt_ziel: 12 }, e.token);
  ok(x.code === 200, "Einrichter: Einstellung erlaubt");
  x = await post("/api/eaio", { aktion: "test", signal: "ok" }, e.token);
  ok(x.code === 403 && x.j.rolle_noetig === "admin", "Einrichter: Ein-/Ausgaenge -> 403 (Admin)");
  x = await post("/api/eaio", { aktion: "test", signal: "ok" }, a.token);
  ok(x.code === 200, "Admin: Ein-/Ausgaenge erlaubt");
  r = await (await fetch(BASIS + "/api/rollen", { headers: { "X-SE-Token": a.token } })).json();
  ok(r.protokoll.some(p => p.weg === "/api/pruef_einst" && p.rolle === "einrichter"), "Aenderungsprotokoll: Einrichter-Aenderung erfasst");
  ok(!JSON.stringify(r.protokoll).includes("2468") && !JSON.stringify(r.protokoll).includes("1357"), "Protokoll ohne PINs");
  // UI ohne Token: Bedienstation
  const html = await (await fetch(BASIS + "/")).text();
  const dom = new JSDOM(html, { url: BASIS + "/", runScripts: "dangerously", pretendToBeVisual: true, resources: "usable",
    beforeParse(w) { w.fetch = (u, o) => fetch(new URL(u, BASIS).href, o); w.requestAnimationFrame = f => setTimeout(() => f(Date.now()), 16);
      w.HTMLCanvasElement.prototype.getContext = () => new Proxy({}, { get: () => () => {}, set: () => true });
      w.alert = () => {}; w.console.error = (...m) => fehler.push(m.join(" ")); w.addEventListener("error", ev => fehler.push(ev.message)); } });
  const w = dom.window, d = w.document, $ = id => d.getElementById(id), warte = ms => new Promise(rr => setTimeout(rr, ms));
  await warte(3500);
  ok(d.body.classList.contains("rolle-bediener") && !$("navRolle").hidden, "UI: Bedienstation + Schloss sichtbar");
  await w.eval("hole('/api/klasse_neu', {name:'x'})"); await warte(300);
  ok(!$("dAnmelden").hidden, "UI: verweigerte Aktion oeffnet die Anmeldung");
  $("anmPin").value = "1357"; d.querySelector('[data-tat="anmelden"]').click(); await warte(1200);
  ok($("dAnmelden").hidden && !d.body.classList.contains("rolle-bediener") && w.eval("ROLLE.rolle") === "einrichter", "UI: als Einrichter angemeldet");
  $("navRolle").click(); await warte(1000);
  ok(w.eval("ROLLE.rolle") === "bediener", "UI: Abmelden -> Bediener");
  // zuruecksetzen
  ok((await post("/api/rollen", { aktion: "aus" }, a.token)).j.ok, "Rollen wieder aus");
  await post("/api/pruef_einst", { unbekannt_ziel: 10 });
  r = await (await fetch(BASIS + "/api/rollen")).json();
  ok(!r.aktiv, "alles offen wie vorher");
  console.log(fehler.length ? "FEHLER: " + fehler.join(" | ") : "ROLLEN_OK"); process.exit(fehler.length ? 1 : 0);
})();
