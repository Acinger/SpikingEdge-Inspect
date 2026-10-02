// Rauchtest UI 2.2 (jsdom gegen den synthetischen Server auf :8765)
const { JSDOM } = require("jsdom");
const BASIS = process.argv[2] || "http://127.0.0.1:8765";
const fehler = [];
(async () => {
  const html = await (await fetch(BASIS + "/")).text();
  const dom = new JSDOM(html, { url: BASIS + "/", runScripts: "dangerously", pretendToBeVisual: true,
    beforeParse(w) {
      w.fetch = (u, o) => fetch(new URL(u, BASIS).href, o);
      w.requestAnimationFrame = f => setTimeout(() => f(Date.now()), 16);
      w.HTMLCanvasElement.prototype.getContext = () => ({ fillRect(){}, drawImage(){}, save(){}, restore(){}, setLineDash(){}, strokeRect(){}, set fillStyle(v){}, set strokeStyle(v){}, set lineWidth(v){} });
      w.alert = m => fehler.push("alert: " + m);
      w.console.error = (...a) => fehler.push("console.error: " + a.join(" "));
      w.addEventListener("error", e => fehler.push("window.error: " + e.message));
    }});
  const w = dom.window, d = w.document, $ = id => d.getElementById(id);
  const ok = (b, was) => { if (!b) fehler.push("PRUEFUNG: " + was); else console.log("ok  " + was); };
  const warte = ms => new Promise(r => setTimeout(r, ms));
  await warte(2500);
  ok(d.querySelectorAll("#seitenNav .snav:not(.klein)").length === 7, "Seitenleiste: 7 Eintraege");
  ok(!$("griffPfeil") && !$("opsTools"), "Werkzeuge-Dock entfernt");
  ok(!$("kamHaupt"), "1.9.54: alter Kamera-Streifen entfernt");
  w.eval("kamDockSetzen(false)"); await warte(100);
  $("kamHauptKnopf").click(); await warte(300);
  ok($("videoteil").classList.contains("dockoffen"), "Kamera-Knopf oeffnet Dock (auch Linie)");
  ok($("kamHauptKnopf").getAttribute("aria-controls") === "kamDock" && $("kamHauptKnopf").getAttribute("aria-expanded") === "true", "aria am Kamera-Knopf");
  $("kamHauptKnopf").click(); await warte(300);
  ok(!$("videoteil").classList.contains("dockoffen"), "Kamera-Knopf schliesst Dock");
  $("ansichtKnopf").click(); await warte(100);
  ok(!$("ansichtMenue").hidden && $("ansichtMenue").querySelectorAll(".schalt").length === 7, "Ansicht-Menue mit 7 Schaltern");
  $("ansichtKnopf").click(); await warte(50);
  ok($("ansichtMenue").hidden, "Ansicht-Menue schliesst");
  ok($("zoneKnopf").hidden, "Zone-Knopf im Betrieb verborgen");
  $("navZustand").click(); await warte(600);
  ok(!$("dEinstellungen").hidden && /Hardware/.test($("eInhalt").innerHTML) && $("eNav").querySelectorAll("button").length === 3, "Zustand: 3 Reiter, Hardware offen");
  d.querySelector('#eNav button[data-id="diagnose"]').click(); await warte(100);
  ok(/Diagnose/.test($("eInhalt").innerHTML), "Zustand: Diagnose");
  d.querySelector('#eNav button[data-id="wartung"]').click(); await warte(100);
  ok(/Gelerntes verwerfen/.test($("eInhalt").innerHTML), "Zustand: Wartung");
  // Karten-Waechter: Hardware-Reiter mit simulierten Karten (gestoert -> Reset-Knopf)
  w.eval("KARTEN = " + JSON.stringify({ karten: [
    { nr: 0, name: "akd1500_0", nps: 8, status: "aktiv", aufgabe: "Silhouetten-Abgleich", live_text: "Silhouetten-Abgleich · 1.4 ms · vor 0.2 s · 5.1/s" },
    { nr: 3, name: "akd1500_3", nps: 8, status: "gestoert", aufgabe: "GESTOERT seit 12:41 - DMA timeout" } ] }));
  w.eval("ABSCHNITT = 'hardware'"); w.zeichneEinstellungen(); await warte(50);
  ok(/1\.4 ms/.test($("eInhalt").innerHTML) && /GESTÖRT/.test($("eInhalt").innerHTML), "Hardware: Live-Zeile + Stoerung sichtbar");
  ok(!!d.querySelector('#eInhalt button[data-tat="karte_reset"][data-nr="3"]'), "Hardware: Reset-Knopf an gestoerter Karte");
  $("dEinstellungen").hidden = true;
  await w.setzeModus("einrichten"); await warte(400);
  ok(/Aufnahmefenster/.test($("rechts").innerHTML), "Einrichten: Aufnahmefenster in der Spalte");
  ok(!$("zoneKnopf").hidden, "Zone-Knopf im Einrichten sichtbar");
  ok($("opsPageName").textContent === "Kamera & Zonen", "Titel Kamera & Zonen");
  await w.setzeModus("anlernen"); await warte(400);
  ok(/Aufnahmeserie/.test($("rechts").innerHTML), "Lernen: Aufnahmeserie in der Spalte");
  $("lernzonenKnopf").click(); await warte(600);
  ok($("opsPageName").textContent === "Lernzonen A / B", "Titel Lernzonen A / B");
  ok(/LERNZONE · KAMERA A/.test(d.querySelector(".lfeed.anl .lfkopf .lft").textContent), "Kacheltitel im .lft");
  const fkB = d.querySelector('[data-tat="feed_kam"][data-art="lern_b"]');
  ok(fkB && fkB.getAttribute("aria-controls") === "kamDock", "aria-controls Zonen-Kamera -> kamDock (eine Kamera)");
  const aktive = [...d.querySelectorAll("#seitenNav .snav.an")].map(b => b.textContent.trim());
  ok(aktive.length === 1 && /Objekte/.test(aktive[0]), "genau ein Nav-Eintrag aktiv: " + aktive.join("|"));
  await w.setzeModus("betreiben"); await warte(400);
  ok(/ANLIEFERUNG · FEED 1/.test(d.querySelector(".lfeed.anl .lfkopf .lft").textContent), "Kacheltitel zurueck");
  const inp = d.createElement("input"); $("rechts").appendChild(inp); inp.focus();
  const vorher = $("opsSummary").innerHTML;
  w.eval("Z").bereich = Object.assign({}, w.eval("Z").bereich, { pruef: { vorhanden: true, live: { urteil: "gut", name: "TESTTEIL-XY", konfidenz: 0.93 }, gesamt: 5, gut: 4, unbekannt: 1, ausschuss: 0, schwelle: 0.6 } });
  w.zeichneRechts();
  ok(d.activeElement === inp, "Fokus bleibt in der Eingabe");
  ok($("opsSummary").innerHTML !== vorher || /TESTTEIL|gut/i.test($("opsSummary").innerHTML), "Zusammenfassung aktualisiert trotz Fokus");
  inp.remove();
  const fl = fehler.filter(f => !/favicon|404/.test(f));
  console.log(fl.length ? "FEHLER:\n" + fl.join("\n") : "ALLES OK");
  process.exit(fl.length ? 1 : 0);
})().catch(e => { console.log("ABBRUCH", e); process.exit(2); });
