# OpenCode Review — Shiraberu-Übernahmen (Block 1–3, 3670e23..fa332b2)

Unabhängige Review der drei neuen Shiraberu-Übernahmen:

- **Block 1 (3670e23):** `src/ratelimit.py` (pro-Quellen-Drosselung, 150 ms Default,
  thread-sicher, Stampede-Reservierung) + Integration in beide Fanout-Worker
  (`sucher_universal.search()` und `sucher_web.search_web()`).
- **Block 2 (2bd05a7):** `src/cache.py` (TTL-Cache, SQLite, 15 Min, case-insensitiv,
  MAX 2000) + Cache-Lookup/Put in beiden Fanouts + conftest-Isolation.
- **Block 3 (fa332b2):** `q_ddgs`-HTML-Fallback (Lib → `html.duckduckgo.com/?o=json`
  via `net.get_text`, uddg-Redirect-Auflösung).

**Selbst ausgeführt:** `.venv/bin/python -m pytest tests/ -q` → `108 passed, 2 deselected in 24.93s`
(2 deselected = `@pytest.mark.live`). Zusätzlich reproduzierende Mini-Harnesse (unter `/tmp/opencode/`):
Cache-Roundtrip in `search_web`, Health-Verschleierung durch Cache-Hits, Cache-Trim, Live-Proben
gegen `html.duckduckgo.com`. **Es wurden keine Code-Änderungen vorgenommen** (nur diese Datei).

---

## FINDINGS

### Finding 1 — Cache-Treffer zählt als „abgeschlossen" → HEALTHY: verschleiert echte Quellen-Ausfälle bis zu 15 Min (TTL)
- Datei:Zeile: `src/sucher_web.py:395-403` (Cache-Hit im Worker) + `:463-476` (Health-Commit) und
  `src/sucher_universal.py:364-373` + `:444-458`; Ursache der Policy in `src/cache.py:82-107`
  (`put` cached nur erfolgreiche Payloads, `get` unterscheidet nicht, woher der Treffer kam).
- Schweregrad: **HOCH**
- Beschreibung: Ein Cache-Hit wird im Worker als normales „ok"-Ergebnis in die Queue gelegt
  (`sucher_web.py:400` / `sucher_universal.py:370`). Der Main-Loop trägt die Quelle damit in
  `quellen_abgeschlossen` ein und der Health-Commit verbucht sie als `ok=True` → HEALTHY.
  Dabei wurde die Quelle in diesem Lauf **nie kontaktiert** — die „Vervollständigung" ist nicht
  verifiziert. Das verletzt genau die Invariante, die Commit 927723b (F2) eingeführt hat
  („Timeout≠HEALTHY — nur wirklich abgeschlossene Quellen committen"). Empirisch belegt
  (Harness): Quelle liefert Treffer → gecacht; Quelle geht DANACH down (HTTP 500);
  3 weitere identische Suchen → alle Cache-Hits, Health bleibt `HEALTHY`, die q-Funktion wurde
  nur 1× aufgerufen, kein DEGRADED/BROKEN/Cooldown. Eine tote Quelle bleibt bis zum TTL-Ablauf
  (15 Min) gesund — Selbstheilung/Cooldown greifen in Wiederhol-Such-Szenarien nicht.
  Einschränkung: `scripts/health_check.py:82-97` ruft die `q_*`-Funktionen DIREKT auf (kein Fanout,
  kein Cache) → das eigentliche Health-Messwerkzeug ist nicht betroffen; betroffen ist das
  opportunistische Health-Update aus normalen Suchen.
- Fix-Vorschlag: Cache-Hits im Health-Sinn als „neutral" behandeln statt als `ok=True`, d. h. im
  Worker-Tupel einen 4. Status (`cached`) mitgeben und im Commit-Loop bei Cache-Hit KEIN
  `record_outcome(ok=True)` ausführen (weder ok noch fail — kein neues Signal). Alternativ Cache
  bei Quellen im Zustand DEGRADED/BROKEN überspringen. Regressionstest: Treffer cachen → Quelle
  down → 3 Läufe → Status muss DEGRADED/BROKEN werden (schlägt heute fehl).

### Finding 2 — Cache-Key `Quelle|query|n` kollidiert über Fanouts: „wikipedia" hat zwei verschiedene q-Funktionen
- Datei:Zeile: `src/cache.py:53-54` (`_key`) in Kombination mit `src/sucher_universal.py:285`
  (`GENERAL = {"wikipedia": q_wikipedia, ...}`) und `src/sucher_web.py:306`
  (`WEB = {..., "wikipedia": q_wikipedia_web, ...}`).
- Schweregrad: **MITTEL**
- Beschreibung: Beide Fanouts schreiben/lesen unter demselben Schlüssel
  `wikipedia|<query>|<n>`, obwohl `q_wikipedia` (OpenSearch) und `q_wikipedia_web`
  (MediaWiki-Such-API) unterschiedliche Abfragen/Antwortstrukturen liefern. Da die Cache-DB
  zwischen Prozessen überlebt (`src/cache.py:26-28`), kann eine Universal-Suche (Modus
  `universal`/`alle` enthält `q_wikipedia`) den Web-Lauf derselben Query binnen 15 Min mit
  OpenSearch-Daten versorgen und umgekehrt. Modi selbst müssen NICHT im Key stecken (ein Modus
  wählt nur die Quellenmenge; dieselbe Quelle+Query liefert dasselbe), aber die
  **Funktions-Identität** der Quelle fehlt. Weitere Kollisionen: `wikipedia` ist der einzige
  Name, der in beiden Registern vorkommt (ddgs/bing/… nur Web, openalex/… nur SCI) — heute also
  eine einzige, aber echte Datenverfälschung.
- Fix-Vorschlag: Key-Namespace einführen, z. B. `f"{fanout}|{quelle}|{query}|{n}"` oder die
  q-Funktion (Modul+Name) in den Key aufnehmen. Regressionstest: Universal-Lauf cached
  Wikipedia, Web-Lauf derselben Query muss NICHT diesen Payload bekommen.

### Finding 3 — Subprozess-Tests schreiben in die Produktions-Cache-DB (Isolations-Lücke)
- Datei:Zeile: `tests/conftest.py:74-79` (Fixture gilt nur im pytest-Prozess) vs.
  `tests/test_p6_web_buendel.py:153-171` (`test_web_suche_kein_exit_hang`, setzt nur
  `SUCHER_HEALTH_FILE`, `:156`) und `tests/test_opencode_fixes.py:39-42` (analog).
- Schweregrad: **MITTEL**
- Beschreibung: Die autouse-Fixture `cache_auf_tmp` monkeypatcht `cache.DEFAULT_CACHE_DB` nur
  im pytest-Prozess. Die Subprozess-Tests starten `search_web`/`search` mit ECHTEM Netz in einem
  Kindprozess, ohne `SUCHER_CACHE_DB` zu setzen → der Kindprozess nutzt den Default
  `data/sucher_cache.db`. Empirisch belegt: Nach meinem Offline-pytest-Lauf enthält die
  Produktions-DB Einträge des Testlaufs (`bing|kurzer test|3`, `ddgs|kurzer test|3`,
  `tavily|kurzer test|3`, `wikipedia|kurzer test|3`; Datei-Mtime = Zeitpunkt der Test-Suite).
  Die Offline-Suite verschmutzt damit die echte Cache-DB (und damit spätere echte Suchen).
- Fix-Vorschlag: In den Subprozess-Tests zusätzlich `SUCHER_CACHE_DB=str(tmp_path / "cache.db")`
  in die `env`-Dicts aufnehmen (analog `SUCHER_HEALTH_FILE`); in `conftest.py` ggf. ein Helfer
  „Subprozess-Env" bündeln.

### Finding 4 — `q_ddgs`-HTML-Fallback: live unverifiziert; Anomaly-Wall wird nicht als Block erkannt → stilles []
- Datei:Zeile: `src/sucher_web.py:90-116` (Fallback), `src/net.py:36-41` (`_BLOCK_MARKER`),
  Lib-Pfad `src/sucher_web.py:78-89`.
- Schweregrad: **MITTEL**
- Beschreibung:
  (a) **Live-Reproduktion** aus dieser Umgebung: Die ddgs-Lib liefert echte Treffer (5 Hits),
      aber `https://html.duckduckgo.com/html/?o=json&v=1` antwortet dort konsistent mit einer
      DDG-Botwall („anomaly", 67×), die KEINEN `result__a`-Anchor enthält. Der Fallback-Pfad
      (Lib-Import erzwungen kaputt) gab live **0 Treffer**. Das Ergebnis-Markup des echten
      Endpunkts ist damit **UNVERIFIED** — die Tests mocken nur ein idealisiertes Markup
      (`tests/test_p6_web_buendel.py:57-71`).
  (b) Die Botwall wird von `net.get_text`/`block_indicator` NICHT erkannt: „anomaly" / „select all
      squares" fehlen in `_BLOCK_MARKER` → `get_text` liefert `(text, None)` → Regex findet 0
      Treffer → `q_ddgs` gibt `[]` zurück **ohne `_log_web_error`** (Fehler-Zweig `:97-99` nur bei
      `err`). Eine geblockte DDG-HTML-Quelle sieht damit aus wie „0 Treffer, erreichbar".
  (c) Wirft die Lib erst NACH dem Appenden von Teiltreffern, bleiben diese in `out` und werden
      mit HTML-Fallback-Treffern gemischt (kein `out = []`-Reset zwischen Weg 1 und Weg 2).
  (d) Der Fallback feuert auch bei „Lib liefert 0 echte Treffer" (leer, kein Fehler) → bei
      wirklich leeren Ergebnissen ein zusätzlicher Netz-Request pro Suche. Das ist vertretbar,
      sollte aber bewusst sein.
- Fix-Vorschlag: (b) „anomaly" in `_BLOCK_MARKER` aufnehmen ODER im Fallback nach `get_text`
  prüfen: 0 `result__a`-Matches + kein „No results."-Marker → als Block behandeln und loggen;
  (c) vor Weg 2 `out = []` setzen; (a) Live-Smoke gegen das echte Markup dokumentieren
  (`check.sh live`) bzw. Fallback auf den POST-Endpunkt umstellen, wenn sich das GET-Markup
  nicht bestätigt.

### Finding 5 — `throttle()` läuft auch bei Cache-Treffern → unnötige Wartezeit + Slot-Reservierung
- Datei:Zeile: `src/sucher_web.py:389-403` und `src/sucher_universal.py:357-373`
  (Reihenfolge: erst `throttle`, dann `cache.get`); `src/ratelimit.py:35-56`.
- Schweregrad: **NIEDRIG**
- Beschreibung: Auch wenn die Antwort aus dem Cache kommt (kein Netz-Request), wird vorher
  `throttle(quelle)` aufgerufen. Bei raschen Wiederhol-Suchen schläft dadurch JEDER gecachte
  Lauf unnötig (empirisch gemessen: 4 aufeinanderfolgende Cache-Hits je ~0.137–0.150 s), und die
  Reservierung (`ratelimit.py:49` `_last_ts[quelle] = now + warte`) verschiebt echte
  Folge-Requests der Quelle nach hinten, obwohl gar kein Request stattfand. Kein Deadlock
  (zwei unabhängige Locks, nie verschachtelt; Sleep außerhalb des Locks — verifiziert), aber die
  Cache-Beschleunigung wird halbiert.
- Fix-Vorschlag: Reihenfolge tauschen: erst `cache.get`; nur bei Miss `throttle()` + Netz-Request.
  Damit entfällt die Drosselung für reine Cache-Läufe komplett.

### Finding 6 — `cache.put`: Erstzugriffs-/DDL-Race kann Schreibvorgänge still verschlucken; kein MAX-2000-Test
- Datei:Zeile: `src/cache.py:82-107` (besonders `:87` `_init(db)` AUSSERHALB des Locks; `:102-104`
  innerer Rollback nur im Lock-Bereich), `:35-38` (`_conn` setzt bei jedem Öffnen `PRAGMA
  journal_mode=WAL`).
- Schweregrad: **NIEDRIG**
- Beschreibung: `put` ruft bei JEDEM Schreiben `_init` (CREATE TABLE IF NOT EXISTS + Commit) auf
  einer separaten Verbindung außerhalb des Modul-Locks auf. Beim ersten parallelen Schreiben
  mehrerer Worker kann eine Verbindung „database is locked" bekommen; der Fehler läuft in den
  äußeren `except: pass` (`:106-107`) → der Eintrag geht still verloren (Cache-Miss, kein Crash).
  Zusätzlich DDL-Overhead pro Write. Die Trim-Logik (`:98-100`, `LIMIT -1 OFFSET 2000`) ist
  funktional korrekt (verifiziert: 2100 Puts → 2000 Zeilen, die 100 ältesten gelöscht), aber
  ungetestet.
- Fix-Vorschlag: `_init` einmalig (z. B. bei `clear`/Test) bzw. innerhalb des Locks mit
  `CREATE TABLE IF NOT EXISTS` ausführen; oder beim Fehlschlag 1 Retry. Trim-Verhalten als
  Test ergänzen.

### Finding 7 — Test-Lücken der drei Blöcke (Integrationsebene fehlt fast komplett)
- Datei:Zeile: `tests/test_cache.py`, `tests/test_ratelimit.py` (nur Unit),
  `tests/test_p6_web_buendel.py:62-121` (nur `q_ddgs`-Fallback isoliert).
- Schweregrad: **MITTEL**
- Beschreibung: Die Integration in die Fanouts ist ungetestet. Es fehlen Tests für:
  1. Cache im Fanout: 2. identische `search`/`search_web`-Suchen → Cache-Treffer, q-Funktion und
     Netz (FakeTransport-Calls) werden NICHT erneut aufgerufen;
  2. leere Ergebnisse (0 Treffer) werden NICHT gecacht; Fehler/Timeout-Quellen NICHT gecacht;
  3. Cache×Health (Finding 1) — würde den Bug heute rot machen;
  4. Cache-Key-Kollision über Fanouts (Finding 2);
  5. Throttle bei Cache-Treffer übersprungen (Finding 5);
  6. `ratelimit.set_interval` + Fanout (dass ein Worker wirklich schläft) — `set_interval` ist
     heute nur in Unit-Tests verdrahtet, in Produktion nirgends;
  7. `SUCHER_CACHE_DB`-Isolation in Subprozess-Tests (Finding 3);
  8. DDG-Fallback mit realistischerem Markup (`&amp;rut`, weitere Attribute vor `href`,
     Reihenfolge `href` vor `class`).
- Fix-Vorschlag: Integrationstests je Fanout mit `FakeTransport` + frischer tmp-Cache-DB
  ergänzen (Muster existiert in `test_p6_web_buendel.py`), mindestens die Punkte 1–3 und 6.

---

## Beantwortung der Prüffragen

1. **Cache × Health:** Teilweise falsch. Timeout-Quellen werden nie gecacht (put nur bei
   nicht-leerem `payload`, Worker ohne Antwort schreibt nichts) — korrekt. ABER ein Cache-Treffer
   zählt als abgeschlossen → HEALTHY ohne Verifikation des Ist-Zustands → maskiert Ausfälle bis
   zur TTL (Finding 1). `health_check.py` ist dank Direktaufruf nicht betroffen.
2. **Rate-Limit + Cache:** Kein Deadlock (Locks getrennt, nie verschachtelt, Sleep außerhalb des
   Locks — verifiziert). Sie blockieren sich nicht, aber `throttle` läuft auch bei Cache-Treffern
   → unnötige ~150 ms + Slot-Reservierung pro gecachtem Lauf (Finding 5).
3. **Cache-Key `Quelle|query|n`:** Modi brauchen keinen eigenen Key-Anteil (Modus wählt nur die
   Quellenmenge). ABER die Quellen-IDENTITÄT fehlt: „wikipedia" existiert als unterschiedliche
   q-Funktion in beiden Fanouts → Cross-Fanout-Kollision (Finding 2). `n` und Case-Insensitivität
   sind korrekt umgesetzt und getestet.
4. **Cache-Treffer mit 0 Treffern werden nicht gecacht:** Korrekt als Policy — leere Ergebnisse
   sind mehrdeutig (0 echte Treffer vs. stiller Block) und dürfen den Cache nicht vergiften.
   Trade-off: wiederholte echte Null-Treffer-Suchen kosten weiter Netz (bewusst).
5. **DDG-Fallback:** Regex-Form ist plausibel, aber gegen echtes Live-Markup **UNVERIFIED**;
   live liefert der HTML-Endpunkt hier eine Botwall, die die Block-Erkennung nicht fängt → stilles
   `[]` (Finding 4). uddg-Auflösung ist sicher: `startswith("http")`-Filter verhindert
   `javascript:`/relative URLs; der aufgelöste Link ist das eigentliche Suchergebnis (kein
   Open-Redirect-Risiko). Fallback feuert bei Lib-Exception UND bei Lib-leer (nur bei leer auch
   bei „wirklich 0 Treffer").
6. **Thread-Safety `cache.py`:** Grundsätzlich ok — ein Modul-Lock serialisiert alle DB-Zugriffe,
   Verbindungen pro Aufruf, WAL. Schwachstelle: `_init`/DDL außerhalb des Locks + stiller
   `except: pass` → seltene, verlorene Erstschreibvorgänge; kein Lock-Problem (Finding 6).
7. **Test-Lücken:** Siehe Finding 7 (Fanout-Integration, Cache×Health, Subprozess-Isolation
   ungetestet).
8. **Data-Isolation:** In-Prozess sauber (`conftest.py:74-79`, autouse, tmp-DB). Lücke: Tests mit
   Subprozess + echtem Netz setzen `SUCHER_CACHE_DB` nicht → schreiben in die Produktions-DB
   (empirisch belegt, Finding 3).

---

## VERDICT: FAIL

Begründung: Finding 1 verletzt die im Vorgänger-Commit 927723b dokumentierte Health-Invariante
(„nur verifizierte Abschlüsse dürfen HEALTHY machen") — ein Cache-Treffer ist kein verifizierter
Abschluss und verschleiert echte Ausfälle bis zu 15 Min. Dazu Finding 2 (Cache-Datenverfälschung
über Fanout-Grenzen) und Finding 3 (Offline-Suite schreibt in die Produktions-Cache-DB, empirisch
belegt). Die Unit-Tests sind grün (108 passed), decken diese Integrationsfehler aber nicht ab.
Die drei Blöcke sind nach Fix von Finding 1, 2, 3 und den Regressionstests aus Finding 7
(erneut bewertbar) als PASS einstufbar. Keine Code-Änderungen vorgenommen.
