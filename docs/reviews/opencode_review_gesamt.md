# OpenCode Review — GESAMT (Stand master @ 4130223, 03.09.2026)

Unabhängige Gesamt-Review des kompletten Code-Stands: `sucher.py`, `src/sucher_universal.py`,
`src/sucher_web.py`, `src/net.py`, `src/health.py`, `src/store.py`, `src/proxy.py`,
`src/sucher_oa.py`, `src/sucher_download.py`, `scripts/health_check.py`, `check.sh`,
`launch.sh`, `tests/*.py`.

Kriterien: echte Bugs/Logikfehler, Race-Conditions in den Thread-Fanouts, Health-Registry-Logik,
Netz-Härtungslücken, Test-Lücken, Sicherheit, SQLite-Inkonsistenzen.

**Selbst ausgeführt:** `.venv/bin/python -m pytest tests/ -q` → `71 passed, 2 deselected in 24.65s`
(2 deselected = `@pytest.mark.live`). Zusätzliche reproduzierende Mini-Harnesse unter
`/tmp/opencode/`. Verifikations-Vermerk: `data/` ist gitignored und wurde durch die Test-Suite
NICHT beschrieben (per-Modul md5-Kontrolle + Env-Isolation); eine von mir selbst verursachte
Veränderung an `data/health.json` während der Review wurde zurückgesetzt.

---

## FINDINGS

### Finding 1 — Health-Selbstheilung im Web-Bündel greift für 6 von 7 Quellen nie (Namens-Mismatch)
- Datei:Zeile: `src/sucher_web.py:362-377` (Commit-Loop) vs. Fehler-Labels `:109` ("Bing"),
  `:175` ("Mojeek"), `:132` ("Tavily"), `:154` ("SerpApi"), `:244` ("Exa"),
  `:219` (`"Wikipedia-{lang}"`); Register-Key `src/sucher_web.py:253-255`; dagegen korrekt: `:68/:79` ("ddgs").
- Schweregrad: `HOCH`
- Beschreibung: Die Health-Auswertung iteriert `active.keys()` aus dem `WEB`-Register
  (`bing`, `mojeek`, `tavily`, `serpapi`, `exa`, `wikipedia`), aber fast alle `q_*`-Funktionen loggen
  ihre Fehler unter einem **anderen Label** (`Bing`, `Mojeek`, `Tavily`, `SerpApi`, `Exa`,
  `Wikipedia-de`/`Wikipedia-en`). `fehler_register.get(name)` liefert dadurch für diese Quellen immer
  `None` → die Quelle wird bei realem Fehler als `ok=True` (HEALTHY) verbucht statt als
  DEGRADED/BROKEN. **Reproduktion** (Harness, 3 Läufe mit je 1 Captcha-Fail pro Quelle):
  Quelle mit passendem Key wird BROKEN (consec=3), Quelle, die wie der echte `q_mojeek` unter
  `"Mojeek"` loggt, bleibt `HEALTHY, consec=0`. **Produktions-Beleg:** `data/health.json` zeigt
  `mojeek: HEALTHY, ok_count=11` obwohl Mojeek laut eigenem Docstring/Commit-Message seit demselben
  Tag Captcha-blockt — jeder Block wird als Erfolg gezählt. Nur `ddgs` ist korrekt verdrahtet.
  Damit sind die P6-B2-Zusagen „BROKEN-Skip", „Mojeek wird nach 3 Fails gecooldowned" und die
  generelle Web-Selbstheilung für 6/7 Quellen funktionslos. Tests decken es nicht ab, weil sie
  Fake-Quellen mit **identischem** Dict-Key/Label verwenden.
- Fix-Vorschlag: Ein kanonisches Label je Quelle festlegen und in `_log_web_error` nutzen (z. B.
  pro `q_*` den WEB-Register-Key verwenden bzw. eine `_WEB_QUELLEN_NAME = {"mojeek": "Mojeek", ...}`-
  Zuordnung in der Commit-Schleife auflösen). Regressionstest mit realer Funktions-Semantik
  (Quelle loggt unter anderem Namen → muss DEGRADED werden) ergänzen.

### Finding 2 — `q_base` (BASE) und `q_biorxiv` sind tote Quellen: definiert, aber nirgends registriert
- Datei:Zeile: `src/sucher_universal.py:245-267` (`q_base`), `:197-215` (`q_biorxiv`),
  Register `:318-322` (SCI) / `:322` (GENERAL); `tests/test_codex_fixes.py:77-85` (F3-Test).
- Schweregrad: `MITTEL`
- Beschreibung: `resolve_sources()` (verifiziert) liefert nur `SCI ∪ GENERAL`; weder `base` noch
  `biorxiv` sind dort enthalten. Der F3-Härtungs-Fix („BASE-Anubis-Falle") und der zugehörige
  Test `test_f3_q_base_nutzt_net` prüfen nur den Quelltext einer **nie ausgeführten** Funktion.
  Die im Modul-Docstring suggerierte Quelle BASE ist in keinem Modus aktiv; „12 akademische Quellen"
  sind real 7 (SCI) + 3 allgemein = 10 aktive. Tote Funktionen täuschen Abdeckung vor.
- Fix-Vorschlag: `q_base` in SCI registrieren (sofern die API lebt) **oder** Funktion + F3-Test +
  Docstring-Erwähnung entfernen. `q_biorxiv` entfernen (API kann keine Freiwort-Suche, vgl. `:321`).

### Finding 3 — launch.sh-Menü verspricht „Alles (Studien + Web)", Modus `alle` enthält kein Web
- Datei:Zeile: `launch.sh:36` vs. `src/sucher_universal.py:324-329` (`resolve_sources`) und
  `sucher.py:76-80` (Web nur bei `--modus web`).
- Schweregrad: `MITTEL`
- Beschreibung: Option 3 „Alles (Studien + Web)" setzt `--modus alle`. `resolve_sources("alle")`
  liefert aber exakt dieselbe Menge wie `"universal"` (SCI + GENERAL, **kein** Web-Bündel —
  verifiziert). Der Menüpunkt ist damit identisch zu Option 2 plus Allgemeinwissen, das
  Web-Bündel fehlt trotz Beschriftung komplett. Ein echter Kombi-Modus „Studien + Web" existiert
  nicht.
- Fix-Vorschlag: Entweder Menütext korrigieren („3) Studien + Allgemeinwissen") oder in `sucher.py`
  für `alle` Web + universal zusammensetzen (echter Gesamt-Modus).

### Finding 4 — 5 Web-Quellen umgehen die zentrale Netz-Härtung (net.py) komplett
- Datei:Zeile: `src/sucher_web.py:94` (Bing, `urlopen` 15s), `:208` (Wikipedia, 12s),
  `:125/:147/:237` (Tavily/SerpApi/Exa, je 20s, POST bzw. Key im Query-String).
- Schweregrad: `MITTEL`
- Beschreibung: Diese Quellen laufen über direktes `urllib.request.urlopen` — ohne 8s-Cap, ohne
  Retry/Backoff, ohne Proxy-Fallback und ohne `block_indicator`. Ein Bing-Captcha liefert z. B.
  HTML ohne `<item>` → stille `[]` **ohne Fehlereintrag** → laut Finding-1-Mechanik HEALTHY.
  Das widerspricht dem net.py-Anspruch „zentrale Schicht für ALLE Quellen" (`src/net.py:5-7`) und
  der P2-Zusage eines 8s-harten Timeouts (analog zum früher gefixten arXiv-Bypass). Nur `q_mojeek`
  geht korrekt über `net.get_text`. Hinweis: `net.get_json` kann kein POST — für Tavily/Exa ist ein
  POST-fähiger Net-Pfad nötig, sonst bleiben sie Bypass.
- Fix-Vorschlag: `get_text`/`get_json` auch für Bing/Wikipedia nutzen; für POST-Quellen einen
  `net.post_json()` (gleiche Härtung) ergänzen und alle Web-Quellen darüber laufen lassen.

### Finding 5 — health_check.py: `TIMEOUT_PER` wird nie erzwungen, Läufe sequenziell
- Datei:Zeile: `scripts/health_check.py:24` (`TIMEOUT_PER = 12`, einzige Nutzung `:103` im
  Report-Text), `:59-65` (sequenzielle Schleifen), `:44` (`--modus`-Parsing).
- Schweregrad: `MITTEL`
- Beschreibung: Der angekündigte „Timeout 12s/Quelle" existiert nur als Konstante/Text. Jede
  `q_*`-Funktion bringt ihr eigenes (bis 20s bei Tavily/SerpApi/Exa) Timeout mit; der Check läuft
  strikt sequenziell über alle Quellen → Dauer = Summe, nicht Max. Ein hängender Anbieter dehnt den
  Health-Check beliebig (kein Gesamtbudget). Zusätzlich: `sys.argv[index("--modus")+1]` wirft
  `IndexError`, wenn `--modus` als letztes Argument ohne Wert steht.
- Fix-Vorschlag: `_measure` mit eigenem hartem Deadline (z. B. in Thread + `timeout`) versehen,
  Quellen parallel messen oder Gesamtlaufzeit deckeln; `--modus`-Wert defensiv prüfen.

### Finding 6 — Race: verwaiste Daemon-Threads nach Budget-Überschreitung schreiben in das Fehlerregister des NÄCHSTEN Laufs
- Datei:Zeile: `src/sucher_universal.py:344-346` (globaler `clear()`), `:421-424` (orphane Threads
  werden nicht gejoint), `:431-444` (Health-Commit liest dasselbe globale Register).
- Schweregrad: `NIEDRIG`
- Beschreibung: `_QUELLEN_FEHLER` ist modul-global; `search()` leert es nur beim Start. Ein über das
  Budget abgeschnittener Daemon-Thread aus Lauf 1 kann nach dem `clear()` von Lauf 2 (gleicher
  Prozess) noch `_log_quellenfehler()` aufrufen und dessen Health-Attribution verfälschen (Quelle,
  die in Lauf 2 leer aber gesund war, bekommt einen Fremd-Fehler zugeschlagen). Der frühere F5-Fix
  deckt nur bereits abgeschlossene Lauf-1-Fehler ab; das Budget-Fenster bleibt offen. In der CLI
  (1 Suche/Prozess) harmlos, in Mehrfach-Suchen desselben Prozesses real.
- Fix-Vorschlag: Fehlerregister pro Suchlauf lokal erzeugen und an Worker durchreichen, oder
  Einträge mit Lauf-Token versehen und fremde Tokens beim Commit ignorieren.

### Finding 7 — Test-Lücken (mehrere)
- Datei:Zeile: `tests/test_p6_web_buendel.py:59-75`, `tests/test_p7_quellen_4faelle.py:19-23`,
  `tests/test_p6_web_buendel.py:116-235`; fehlende Dateien: keinerlei Tests für
  `src/sucher_oa.py`, `src/sucher_download.py`.
- Schweregrad: `MITTEL`
- Beschreibung:
  (a) `test_wikipedia_web_parst_de_en` heißt „parst", führt aber nur `assert callable(...)` aus —
  der komplette DE/EN-Parse-Pfad (urllib-Direktzugriff, daher offline nicht mockbar) ist ungetestet.
  (b) Der P7-„4-Fälle je Kern-Quelle"-Test deckt nur 3 von 10 aktiven Quellen ab
  (`openalex`, `crossref`, `arxiv`); der `QUELLEN`-URL-Präfix wird gar nicht zum Routen genutzt
  (geroutet wird generisch auf `"http"`). `doaj/europepmc/semanticscholar/pubmed/wikidata/wikipedia/lokal`
  haben keinen 4-Fälle-Test.
  (c) Finding 1 (Alias-Mismatch) bleibt unsichtbar, weil alle Web-Health-Tests Fake-Quellen mit
  identischem Key+Label verwenden.
  (d) Für `sucher_oa` und `sucher_download` existiert kein einziger Test (DOI-Extraktion,
  `extract_doi`, PDF-/HTML-Erkennung, Konvertierungs-Fallback ungetestet).
- Fix-Vorschlag: Wikipedia-Parse via `urllib`-Monkeypatch offline testen; 4-Fälle-Matrix auf alle
  aktiven Quellen ausweiten (oder mind. je Kategorie eine); Alias-Regressionstest (Finding 1);
  Grundtests für `sucher_oa.extract_doi`/`resolve` und `sucher_download.is_pdf/is_html` ergänzen.

### Finding 8 — SQLite: Health-Spiegel ist kein „Source of Truth", driftet und behält Test-Artefakte
- Datei:Zeile: `src/store.py:5-15` (Doku: „DB ist die Source of Truth"), `:131-156`
  (`save_health`), Schema `:56-66`.
- Schweregrad: `NIEDRIG`
- Beschreibung: Die tatsächliche Entscheidungsquelle ist `data/health.json` (HealthRegistry lädt/`save()`t
  nur JSON); `provider_health` wird ausschließlich vom CLI (`sucher.py:111-116`) gespiegelt.
  `save_health` verwendet `INSERT OR REPLACE`, löscht aber nie Zeilen, die im Registry nicht mehr
  existieren → Drift. Beleg in `data/sucher.db`: Zeile `source='haengt'` (HEALTHY) existiert in
  `health.json` nicht; `ergebnisse` enthält die Artefakt-Zeile `query='test query'`/`quelle='test'`
  (Rest eines früheren Test-/Verifikationslaufs, ts 13:51:10). Zudem geht das `reason`-Feld von
  `NO_KEY`/`DISABLED` verloren (Spalte fehlt), und `queries.modus` wird in `save_ergebnisse`
  hart auf `"universal"` gesetzt, auch bei Web-Läufen (`:104`).
- Fix-Vorschlag: Entweder DB zur echten Quelle machen (HealthRegistry liest/schreibt DB) oder
  Doku korrigieren; `save_health` um Löschen nicht mehr vorhandener Sources erweitern; `modus` im
  Aufruf durchreichen; Artefakt-Zeilen in `data/sucher.db` bereinigen.

### Finding 9 — sucher.py `--sources` ruft System-`python3` statt des venv-Python
- Datei:Zeile: `sucher.py:59`.
- Schweregrad: `NIEDRIG`
- Beschreibung: `--sources` startet `subprocess.run(["python3", src_list, "--list"])` mit dem
  System-Interpreter, während alle anderen Subprozesse (`:61`) korrekt `sys.executable` nutzen.
  Inkonsistent mit dem venv-zentrierten, Hermes-unabhängigen Setup (launch.sh) — schlägt fehl bzw.
  nutzt falsche Umgebung, falls das Repo-venv nicht das System-Python ist.
- Fix-Vorschlag: `python3` durch `sys.executable` ersetzen.

### Finding 10 — PubMed: Fehler des zweiten Requests (esummary) werden nicht geloggt
- Datei:Zeile: `src/sucher_universal.py:227-243`.
- Schweregrad: `NIEDRIG`
- Beschreibung: Der erste Request (`esearch`) läuft über `_check_fehler("pubmed", j)`, der zweite
  (`esummary`, `:229`) wird ohne `_check_fehler`/Fehlerlog verarbeitet → bei 429/Timeout des zweiten
  Calls liefert PubMed still `[]`, obwohl der Fehler hätte sichtbar sein müssen (P1-Prinzip).
- Fix-Vorschlag: Nach `http_json(u2)` ebenfalls `if _check_fehler("pubmed", j2): return []` einfügen.

### (Kein Finding) Geprüfte Verdachtsfälle, die sich als unkritisch erwiesen
- `sucher.py --download` (`:96`, `r["_oa"]` = Tupel) crasht NICHT: `json.dump` serialisiert Tupel
  als Arrays (per Harness verifiziert).
- Frühere Findings der Vor-Reviews (Exit-Hang, arXiv-Bypass, stille `_error`, Proxy-Text-
  Validierung, deterministisches Scoring, Skalar-Handling, per-Lauf-Reset) sind im aktuellen Stand
  behoben bzw. getestet — bis auf die hier in Findings 5/6 benannten Reste.
- Test-Suite schreibt nicht in Produktions-`data/health.json`/`sucher.db` (per md5-Kontrolle
  verifiziert).

---

## VERDICT: FAIL

Begründung: Die Offline-Suite ist grün (71 passed, 2 live deselected) und die früheren
Review-Findings sind weitgehend umgesetzt. Aber Finding 1 (Health-Alias-Mismatch) macht die
P6-B2-Selbstheilung für 6 von 7 Web-Quellen real funktionslos — belegt durch Reproduktion und den
Produktionszustand (`mojeek: HEALTHY` trotz dokumentiertem Captcha-Block). Da das Kernversprechen
„immer funktionieren" wesentlich über das Health-/BROKEN-Cooldown-System getragen wird, ist das ein
BLOCKER-artiger Befund. Zusätzlich offen: tote Quellen `q_base`/`q_biorxiv` mit irreführendem Test
(Finding 2), falsch beschrifteter Web-Kombi-Modus (Finding 3) und nicht gehärtete Web-Transports
(Finding 4). Empfehlung: Findings 1-4 vor dem nächsten Merge beheben, 5-10 einplanen.
