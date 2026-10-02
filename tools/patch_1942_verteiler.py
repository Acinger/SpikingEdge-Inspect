#!/usr/bin/env python3
"""A4 — Kartenverteiler (Build 1.9.42).

edge_learn.py:
  - Replikation: im Profil stationaer bekommt JEDE Karte den vollen
    Prototypensatz, wenn er auf eine Karte passt (verbund_modus
    "repliziert"); sonst wie bisher verteilt (G Karten teilen sich die
    Beispiele, verbund_modus "verteilt"). Entscheidung in _verbund_planen().
  - erkenne_auf_karte(bild, maske, ki): Urteil mit EINER Karte (nur im
    replizierten Verbund gleichwertig zum Gesamturteil).
  - Urteilsbildung aus Potentialen in _urteil() ausgelagert (eine Stelle).
server.py:
  - bewerte(..., ki=None) -> chip_erkenne(patch, pmaske, ki)
  - self.verteiler = Kartenverteiler(lerner) im Profil stationaer;
    _hypothesen_entscheiden nutzt verteiler.bewerte_viele (Threads je Karte).
  - Lernbericht/Zustand: verbund_modus sichtbar.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
E = ROOT / "vorsa" / "edge_learn.py"
S = ROOT / "vorsa" / "web" / "server.py"


def ers(text, alt, neu, n=1):
    k = text.count(alt)
    if k != n:
        raise SystemExit(f"FEHLER: {k}x statt {n}x gefunden:\n{alt[:200]}")
    return text.replace(alt, neu)


el = E.read_text(encoding="utf-8")
if "def erkenne_auf_karte" in el:
    print("edge_learn.py: schon gepatcht")
else:
    el = ers(el, '''        self.karten_max = 4
''', '''        self.karten_max = 4
        # KARTENVERTEILER (SE Inspect A4, 1.9.42): "repliziert" = jede
        # Karte traegt alle Prototypen, ein Auftrag braucht nur EINE Karte
        # -> mehrere Auftraege gleichzeitig auf mehreren Karten.
        # "verteilt" = Beispiele ueber die Karten verteilt (mehr Kapazitaet),
        # jeder Auftrag fragt alle Karten (max-Verbund). replikation=True
        # ist der Wunsch; was wirklich passt, entscheidet _verbund_planen.
        self.replikation = False
        self.verbund_modus = "verteilt"
        self._karten_locks: Dict[int, threading.Lock] = {}
''')
    el = ers(el, '''        kleinste = min(len(b) for b in bilder_je_klasse.values())
        G = max(1, min(len(self.geraete), kleinste))
        self.geraete = self.geraete[:G]
        self._messwerk_an()
        anteil_groesste = -(-groesste // G)        # aufgerundet
        neuronen = max(self.neuronen, anteil_groesste)

        melde(f"Lernschicht auf {G} Karte(n) legen")
''', '''        kleinste = min(len(b) for b in bilder_je_klasse.values())
        plan = self._verbund_planen(len(self.geraete), kleinste, groesste)
        G = plan["karten"]
        self.geraete = self.geraete[:G]
        self._messwerk_an()
        anteil_groesste = plan["je_karte"]
        neuronen = max(self.neuronen, anteil_groesste)
        self.verbund_modus = plan["modus"]
        schritt = 1 if plan["modus"] == "repliziert" else G

        melde(f"Lernschicht auf {G} Karte(n) legen ({plan['modus']})")
''')
    el = ers(el, '''            for k, name in enumerate(namen):
                teil = X[name][i::G]
                if len(teil):''', '''            for k, name in enumerate(namen):
                # repliziert: jede Karte sieht ALLE Beispiele (i::1);
                # verteilt: Karte i jedes G-te, versetzt um i.
                teil = X[name][(i if schritt > 1 else 0)::schritt]
                if len(teil):''')
    el = ers(el, '''        if neuronen < max(self.neuronen, anteil_groesste):
            warnungen.append(
                f"Nur {neuronen} Neuronen je Objekt und Karte - mehr passt "
                "nicht; aehnliche Ansichten teilen sich einen Platz.")
        self.neuronen_zuletzt = neuronen
''', '''        if neuronen < max(self.neuronen, anteil_groesste):
            warnungen.append(
                f"Nur {neuronen} Neuronen je Objekt und Karte - mehr passt "
                "nicht; aehnliche Ansichten teilen sich einen Platz.")
            if self.verbund_modus == "repliziert" and G > 1 and neuronen < groesste:
                # Replikation passt doch nicht ganz - ehrlich bleiben:
                # dann verteilen, damit nichts verloren geht.
                self.verbund_modus = "verteilt"
                schritt = G
                warnungen.append("Prototypen passen nicht komplett auf eine "
                                 "Karte - Verbund verteilt statt repliziert "
                                 "(Auftraege laufen nacheinander).")
        self.neuronen_zuletzt = neuronen
''')
    el = ers(el, '''        self.bericht = Lernbericht(
            ok=True, klassen=namen, beispiele=n_bsp,
            ms_je_beispiel=dauer / max(n_bsp, 1),
            num_weights=num_weights, neuronen_je_klasse=neuronen,
            aktive_merkmale=an_je_bild,
            dichte=an_je_bild / (self.SIL * self.SIL),
            dichte_vorher=an_je_bild / (self.SIL * self.SIL),
            ausduennen="Silhouetten-Abgleich, kein Rumpf",
            aufgerichtet=self._roh_gezaehlt[0] - self._roh_gezaehlt[1],
            nicht_aufgerichtet=self._roh_gezaehlt[1],
            treffer_eigen=richtig / max(gesamt, 1),
            karten=G,
            verwechslung=vw, warnungen=warnungen)
        return self.bericht
''', '''        if G > 1:
            warnungen.append(
                f"Kartenverbund: {G} Karten, "
                + ("jede mit allen Prototypen (parallele Auftraege)."
                   if self.verbund_modus == "repliziert"
                   else "Prototypen verteilt (Auftraege nacheinander)."))
        self.bericht = Lernbericht(
            ok=True, klassen=namen, beispiele=n_bsp,
            ms_je_beispiel=dauer / max(n_bsp, 1),
            num_weights=num_weights, neuronen_je_klasse=neuronen,
            aktive_merkmale=an_je_bild,
            dichte=an_je_bild / (self.SIL * self.SIL),
            dichte_vorher=an_je_bild / (self.SIL * self.SIL),
            ausduennen="Silhouetten-Abgleich, kein Rumpf",
            aufgerichtet=self._roh_gezaehlt[0] - self._roh_gezaehlt[1],
            nicht_aufgerichtet=self._roh_gezaehlt[1],
            treffer_eigen=richtig / max(gesamt, 1),
            karten=G,
            verwechslung=vw, warnungen=warnungen)
        return self.bericht

    # ------------------------------------------------------------------
    # KARTENVERTEILER (A4): Planung des Verbunds, Urteil je Karte
    def _verbund_planen(self, karten: int, kleinste: int, groesste: int) -> dict:
        """Wie werden die Beispiele auf die Karten gelegt?

        repliziert: alle Karten, jede alle Beispiele (je_karte = groesste)
        verteilt:   hoechstens so viele Karten wie die kleinste Klasse
                    Beispiele hat, je Karte ein Anteil (aufgerundet)."""
        karten = max(1, int(karten))
        if self.replikation:
            return {"modus": "repliziert", "karten": karten, "je_karte": int(groesste)}
        G = max(1, min(karten, int(kleinste)))
        return {"modus": "verteilt", "karten": G, "je_karte": -(-int(groesste) // G)}

    def _karten_lock(self, ki: int) -> threading.Lock:
        with self._lock:
            l = self._karten_locks.get(ki)
            if l is None:
                l = self._karten_locks[ki] = threading.Lock()
            return l

    def _urteil(self, x: np.ndarray, pro_klasse: np.ndarray, sieger) -> dict:
        """Urteil aus Klassenpotentialen - eine Stelle fuer Verbund und
        Einzelkarte (Wiederfindung, Reinheit, unklar, unbekannt, warum)."""
        nw = max(int(getattr(self.bericht, "num_weights", 0) or 0), 1)
        probe_punkte = int((x > 0).sum())
        nenner = max(int(nw * 0.35), min(nw, probe_punkte), 8)
        wiederfindung = np.clip(pro_klasse / nenner, 0.0, 1.0)
        reinheit = np.clip(pro_klasse / max(probe_punkte, 8), 0.0, 1.0)
        anteile = np.minimum(wiederfindung, reinheit)
        beste = int(np.argmax(pro_klasse))
        sortiert = np.sort(pro_klasse)[::-1]
        vorsprung = (float(sortiert[0] - sortiert[1]) / max(float(sortiert[0]), 1.0)
                     if len(sortiert) > 1 else 1.0)
        return {
            "klasse": self.klassen[beste],
            "sicherheit": float(anteile[beste]),
            "vorsprung": round(vorsprung, 3),
            "unklar": vorsprung < 0.05,
            "unbekannt": float(anteile[beste]) < self.UNBEKANNT_AB,
            "warum": self.warum(sieger),
            "potentiale": [int(p) for p in pro_klasse],
            "alle": [{"name": n, "anteil": float(a)}
                     for n, a in zip(self.klassen, anteile)],
        }

    def erkenne_auf_karte(self, bild: np.ndarray, maske: Optional[np.ndarray],
                          ki: int) -> Optional[dict]:
        """Urteil mit EINER Karte (replizierter Verbund). Wirft bei
        Kartenfehler nach Meldung an den Waechter, damit der Verteiler den
        Auftrag anderswo wiederholen kann."""
        if self.modell is None or not self.klassen or self.modus != "silhouette":
            return None
        modelle = self.modelle or [self.modell]
        if ki < 0 or ki >= len(modelle) or not self.karte_nutzbar(ki):
            raise RuntimeError(f"Karte {ki} nicht nutzbar")
        C = len(self.klassen)
        x = self._silhouette(bild, maske)[None, ...]
        with self._karten_lock(ki):
            try:
                t0 = time.perf_counter()
                roh = np.asarray(modelle[ki].forward(x))[0].ravel()
                ms = (time.perf_counter() - t0) * 1000.0
            except Exception as exc:
                self.karte_gestoert(ki, f"{type(exc).__name__}: {exc}")
                raise
        self.karte_notiz(ki, "Silhouetten-Abgleich (parallel)", ms)
        self.chip_ms_letzte = ms
        pro_klasse = roh.reshape(C, -1).max(axis=1).astype(float)
        j = int(np.argmax(roh))
        return self._urteil(x, pro_klasse, (ki, j, float(roh[j])))
''')
    # erkenne(): Urteil ueber _urteil()
    el = ers(el, '''                nw = max(int(getattr(self.bericht, "num_weights", 0) or 0), 1)
                # Ehrliche Normierung fuer TEILSTUECKE (2026-08-28): der''', '''                self.letzter_fehler = ""
                return self._urteil(x, pro_klasse, sieger)
                # (alte Urteilsbildung unten bleibt als Dokumentation der
                #  Herleitung stehen; sie ist in _urteil() uebernommen.)
                nw = max(int(getattr(self.bericht, "num_weights", 0) or 0), 1)
                # Ehrliche Normierung fuer TEILSTUECKE (2026-08-28): der''')
    el = ers(el, '''    def vergessen(self) -> None:''', '''    def verbund_info(self) -> dict:
        n = len(self.modelle) if self.modelle else (1 if self.modell else 0)
        return {"modus": self.verbund_modus, "karten": n,
                "replikation": bool(self.replikation),
                "nutzbar": [i for i in range(n) if self.karte_nutzbar(i)]}

    def vergessen(self) -> None:''', 1)
    E.write_text(el, encoding="utf-8")
    print("edge_learn.py gepatcht")

srv = S.read_text(encoding="utf-8")
if "1.9.42-verteiler" in srv:
    print("server.py: schon gepatcht")
else:
    srv = ers(srv, 'BUILD = "1.9.41-hypothesen"', 'BUILD = "1.9.42-verteiler"')
    srv = ers(srv, '''        def chip_erkenne(patch, pmaske):
            erg = self.lerner.erkenne(patch, pmaske)''', '''        def chip_erkenne(patch, pmaske, ki=None):
            if ki is not None:
                erg = self.lerner.erkenne_auf_karte(patch, pmaske, ki)
            else:
                erg = self.lerner.erkenne(patch, pmaske)''')
    srv = ers(srv, '''            def bewerte(box, kontur=None, sperren=None, direkt_maske=None):
                patch, pmaske = self._patch(ausschnitt, box.scaled(faktor),
                                            kontur, faktor, sperren=sperren,
                                            direkt_maske=direkt_maske)
                if patch is None:
                    return None
                erg = chip_erkenne(patch, pmaske)''', '''            def bewerte(box, kontur=None, sperren=None, direkt_maske=None, ki=None):
                patch, pmaske = self._patch(ausschnitt, box.scaled(faktor),
                                            kontur, faktor, sperren=sperren,
                                            direkt_maske=direkt_maske)
                if patch is None:
                    return None
                erg = chip_erkenne(patch, pmaske, ki)''')
    srv = ers(srv, '''        from ..mehrbild import Mehrbild
        self.mehrbild = Mehrbild(anzahl=4 if self.profil == "stationaer" else 1)
''', '''        from ..mehrbild import Mehrbild
        self.mehrbild = Mehrbild(anzahl=4 if self.profil == "stationaer" else 1)
        # KARTENVERTEILER (A4, 1.9.42): nur stationaer; dort werden die
        # Prototypen repliziert und Hypothesen-Auftraege parallel bewertet.
        self.verteiler = None
        if self.profil == "stationaer" and lerner is not None:
            from ..verteiler import Kartenverteiler
            try:
                lerner.replikation = _os.environ.get("VORSA_VERBUND", "repliziert") != "verteilt"
            except Exception:
                pass
            self.verteiler = Kartenverteiler(lerner)
''')
    srv = ers(srv, '''            self.zustand.bereich_info["mehrbild"] = self.mehrbild.als_dict()
''', '''            self.zustand.bereich_info["mehrbild"] = self.mehrbild.als_dict()
            if getattr(self, "verteiler", None) is not None:
                self.zustand.bereich_info["verteiler"] = self.verteiler.als_dict()
                try:
                    self.zustand.bereich_info["verbund"] = self.lerner.verbund_info()
                except Exception:
                    pass
''')
    S.write_text(srv, encoding="utf-8")
    print("server.py gepatcht")
