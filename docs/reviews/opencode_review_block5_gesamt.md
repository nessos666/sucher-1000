# OpenCode-Review Block 5 + Veröffentlichungs-Reife — SUCHER-1000

Datum: 03.09.2026 · Basis: HEAD `086e2e5` · Methodik: Code-Lektüre + eigene
Live-Proben der drei neuen Feeds + offline-Reproduktionen (pytest: 121 passed,
2 deselected; mypy/ruff/bandit grün).

## VERDICT: **FAIL** (1 HOCH, 5 MITTEL, 9 NIEDRIG)

Begründung: Finding 1 (HOCH) ist reproduzierbar, betrifft die neuen Text-Quellen
direkt und erzeugt **stille 0-Treffer-Ergebnisse + gesundheitsschädigende
Fehl-Fails** bei legitimen Suchanfragen. Der Fix ist klein, aber vor einem
Release nötig. Dazu mehrere echte Konsistenzlücken (Gewichts-Dead-Key,
Health-Namenskollision über Fanouts, Entity-Leaks).

---

## HOCH

### F1 — net.py: Body-weite Block-Marker erkennen legitime Inhalte als „Botwall" → stille 0 Treffer + Fehl-Health-Fails
- **Datei:Zeile:** `src/net.py:36-42` (`_BLOCK_MARKER`), `:73-94`
  (`block_indicator`, Probe = erste 4000 Bytes), `:217-256` (`get_text`,
  `erwartet="text"`).
- **Problem:** Für Text/HTML/RSS-Antworten wird der GESAMTE Body-Anfang auf
  Botwall-Wörter gescannt. RSS/HTML-Suchergebnisse **echoen die Query** im
  Feed-/Seitentitel und in den Treffer-Titeln/Descriptions. Enthält die Query
  selbst (oder ein Top-Treffer) eines der Marker-Wörter (`captcha`,
  `anomaly`, `access denied`, `unusual traffic`, `just a moment`,
  `attention required`, `verify you are human`, `enable javascript and
  cookies`, `are you a robot`, `anubis`, `select all squares`), wird die
  gesamte Antwort als Block klassifiziert. Die Marker greifen ohne
  Wortgrenzen und case-insensitiv (`re.IGNORECASE`), d. h. auch `recaptcha`,
  `anomaly detection` usw.
  Betroffen sind ALLE `get_text`-Quellen — insbesondere die neuen
  `q_google_news`/`q_bing_news` (RSS ohne Lib-Pfad) plus `q_bing_html`,
  `q_mojeek` und der DDG-HTML-Fallback. In `search_web` wird so ein Fehler
  geloggt → 0 Treffer → `record_outcome(ok=False)` (sucher_web.py:602-608):
  **drei legitime Suchen mit solchen Wörtern schalten eine gesunde Quelle
  60 Min in den Cooldown.**
- **Reproduktion (live, 03.09.2026):** `q=“captcha“` → Google-News-Feed und
  Bing-News-Feed liefern HTTP 200 und hunderte echte Artikel. Trotzdem:
  ```
  q_google_news("captcha", 3)  → []  + "⚠ [google_news] Fehler: Block/Fehler: BLOCK: 'captcha'"
  q_bing_news("captcha", 3)    → []  + identischer Fehler
  ```
  `rg -c captcha /tmp/gcap.xml` → Marker liegt im Feed bereits bei Byte 165
  (Channel-/Item-Titel echoen die Query). Im `search_web`-Pfad wird der Fail
  sauber gezählt (`consecutive_fails` inkrementiert) → DEGRADED/BROKEN für
  eine Quelle, die nie blockt.
- **Fix-Vorschlag:** Marker-Erkennung auf echte Botwall-Seiten beschränken.
  Optionen (kombinierbar): (a) bei `erwartet="text"` nur auswerten, wenn die
  Antwort KEINE erwartete Struktur hat (z. B. kein `<rss`/`<feed`, kein
  `<html` mit `result`/`search`-Markup); (b) Marker-Wörter, die im Query bzw.
  in Element-Titeln vorkommen, aus der Probe herausnehmen; (c) Marker nur
  dann als Block werten, wenn KEIN einziger `<item>`/Ergebnis-Block geparst
  werden konnte (Parser-Ebene statt Transport-Ebene entscheidet). Für die
  neuen Quellen genügt z. B. die Regel „Feed mit mindestens einem parsebaren
  `<item>` ist kein Block".

---

## MITTEL

### F2 — `_WEB_WEIGHT`-Key „serpapi" ist tot: SerpApi-Ergebnisse ranken mit Default 0.6 statt 0.9
- **Datei:Zeile:** `src/sucher_web.py:442-444` (Gewichte) vs. `:202`
  (`"source": "Google"` in `q_serpapi`) und Lookup `:454`
  (`_WEB_WEIGHT.get((r.get("source") or "").lower(), 0.6)`).
- **Problem:** Das Sortier-Gewicht wird über das **source-Feld** der
  Ergebnis-Dicts nachgeschlagen. `q_serpapi` setzt `source="Google"`, die
  Map hat aber nur den Key `"serpapi"` (und keinen `"google"`). Der Eintrag
  `"serpapi": 0.9` wird **nie** getroffen; SerpApi-Ergebnisse fallen auf den
  Default `0.6` und ranken damit hinter Mojeek/GoogleNews (0.7) und auf einer
  Stufe mit unbekannten/neuen Quellen. Die übrigen Quellen (auch die 3 neuen:
  `hackernews`/`googlenews`/`bingnews` aus `HackerNews`/`GoogleNews`/
  `BingNews`) matchen korrekt.
- **Reproduktion:** `_web_score_sort([{"source":"Google",...}])` →
  Score-Quelle ist 0.6, nicht der dokumentierte 0.9.
- **Fix-Vorschlag:** Konsistenz herstellen — entweder `q_serpapi` liefert
  `source="SerpApi"` (Key `"serpapi"` bleibt) oder die Map bekommt `"google"`.
  Am besten die Gewichte an den Register-Namen hängen und in den
  q-Funktionen den gleichen Bezeichner verwenden (einzige Abweichung im
  ganzen Register).

### F3 — Health-Registry-Key „wikipedia" wird von ZWEI unabhängigen Quellen/Fanouts geteilt
- **Datei:Zeile:** `src/sucher_universal.py:285` (`GENERAL = {"wikipedia":
  q_wikipedia, …}`, OpenSearch-API `:157-173`) und `src/sucher_web.py:434-437`
  (`WEB = {…, "wikipedia": q_wikipedia_web, …}`, MediaWiki `list=search`-API
  `:247-275`). Beide committen unter dem Namen `wikipedia`
  (universal `:453-468`, web `:599-609`).
- **Problem:** Die Cache-Kollision zwischen den Fanouts wurde beim letzten
  Review per Fanout-Namespace gefixt (F2/c8d16c5) — die **Health-Zelle** hat
  aber weiter keinen Fanout-Namespace. Beide Funktionen sind verschiedene
  Endpunkte mit verschiedenen Fehlerbildern, teilen sich aber einen
  Registry-Eintrag. Fällt `q_wikipedia` (OpenSearch) 3× aus → `BROKEN` →
  `is_skippable("wikipedia")` (health.py:144-149) überspringt im selben
  Prozess (Modus `alle`, sucher.py:86-108) auch die funktionierende
  `q_wikipedia_web` — und umgekehrt. Auch ok/fail-Zähler vermischen sich.
- **Reproduktion:** Registry auf `wikipedia` künstlich auf BROKEN setzen →
  `sucher_web.search_web` überspringt die (gesunde) Web-Wikipedia.
- **Fix-Vorschlag:** Health-Keys fanout-qualifizieren (z. B. `web:wikipedia`
  vs. `studien:wikipedia`) analog zum Cache-Key-Namespace, oder die beiden
  Wikipedia-Funktionen auf EINE gemeinsame q-Funktion zurückführen.

### F4 — Web-Fanout liest Health aus globalem Register ohne Pro-Worker-Zähler (Restrisiko Cross-Run)
- **Datei:Zeile:** `src/sucher_web.py:476-477` (`_WEB_FEHLER.clear()` zu
  Laufbeginn) + `:576-577` (Snapshot) + `:599-609` (Commit). Vergleich:
  sucher_universal.py:380-399 löst exakt dieses Problem per
  Vorher/Nachher-Zähler im Worker (F6-Kommentar `:376-379`).
- **Problem:** Daemon-Worker eines Läufes, der das Budget riss (net-retries
  bis ~25-36 s > Default-Budget 30 s möglich), können NACH `clear()` des
  Folgeläufes in dessen Fenster einen Fehler ins Register loggen. Der
  Folgelauf attribuiert ihn dann seiner gleichnamigen Quelle (falscher
  `ok=False`, falls die Quelle 0 Treffer hatte). Der Web-Fanout hat die im
  Universal-Fanout etablierte F6-Absicherung (Worker meldet eigenen
  Zählerstand) nicht übernommen. In der CLI ist nur 1 Suche/Prozess üblich
  (geringes Risiko), bei künftigen Mehrfach-Suchen im selben Prozess wird es
  real.
- **Reproduktion:** `search_web(…, timeout=2)` mit echter/verzögerter Quelle,
  sofort danach `search_web(…, timeout=2)`; der erste, noch laufende Worker
  loggt während des zweiten Laufs.
- **Fix-Vorschlag:** Wie Universal: Worker zählt `_WEB_FEHLER`-Stand vor dem
  `fn()`-Aufruf, meldet `hatte_fehler` im Queue-Tupel, Commit nutzt nur
  gemeldete Werte statt des globalen Snapshots.

### F5 — `q_bing_html` dekodiert HTML-Entities NICHT (die zwei neuen News-Parser schon)
- **Datei:Zeile:** `src/sucher_web.py:142-147` (`title = t.group(1).strip()`,
  `link = l.group(1).strip()`) — ohne `html.unescape`, im Gegensatz zu
  `q_google_news` (:370-371) und `q_bing_news` (:410-411).
- **Problem:** Das echte Bing-Search-RSS liefert Titel mit XML-Escapes
  (`&amp;`, `&lt;`). Ohne Unescape landen sie literal in
  Ergebnis-JSON/CLI-Ausgabe. Inkonsistent zum Rest des Moduls.
- **Reproduktion (live + offline):**
  ```
  Feed-Item: <title>Definition, Arten &amp; Einsatzmöglichkeiten</title>
  q_bing_html(...)  → title = 'Definition, Arten &amp; Einsatzmöglichkeiten'
  ```
- **Fix-Vorschlag:** `title`/`link`/`snippet` durch `html.unescape` ziehen
  (Muster aus `q_google_news`); Snippet-Tag-Strip danach.

### F6 — Google-News-Description ist DOPPELT encodiert → Snippets enthalten literal `&nbsp;`/`&amp;`
- **Datei:Zeile:** `src/sucher_web.py:377-378` (q_google_news, gleiches Muster
  `q_bing_news`: `:422-423`): genau EIN `html.unescape` vor dem Tag-Strip.
- **Problem:** Der echte Google-News-Feed encodiert Teile doppelt
  (`&amp;nbsp;`, vgl. `&amp;lt;`-Werte im Description-Anker). Nach einmaligem
  Unescape + Tag-Strip bleibt literal `&nbsp;` im Snippet stehen
  (Live-Messung: `repr`-Snippet `'…SZ.de&nbsp;&nbsp;SZ.de'`, `\xa0` = 0).
  Der Test-Fixture (test_block5_neue_quellen.py:34-44) enthält NUR
  einfach-encodierte Entities und deckt das nicht ab.
- **Reproduktion:** Live-Feed `/tmp/gnews.xml`: 200× `&amp;…;` im Body,
  2× `&amp;nbsp;` im ersten Description.
- **Fix-Vorschlag:** Nach dem Tag-Strip ein zweites `html.unescape` auf den
  Snippet-Text anwenden (oder Description vor UND nach Strip unescapen).

---

## NIEDRIG

### F7 — `search_web` liefert bis zu `n × aktive Quellen` Treffer (n-Semantik inkonsistent)
- **Datei:Zeile:** `src/sucher_web.py:459-613` (kein Gesamt-Cap; nur
  Pro-Quellen-Cap `n` in den q-Funktionen), CLI `sucher.py:109-118`.
- **Problem:** `sucher.py "…" 3 --modus web` kann ~7×3=21 (mit Keys bis 10×3)
  Treffer liefern. Eigene Demo zeigt n=3 → „12 Treffer" (docs/demo.md:11).
  Wenn das Absicht ist (Bündel), fehlt die Dokumentation; die Zahl `n` wird
  in Help/README als Trefferanzahl verkauft.
- **Reproduktion:** `search_web("test", 3)` mit 3 Fake-Quellen à 3 Ergebnissen
  → 9 Treffer.
- **Fix-Vorschlag:** Entweder Gesamtlimit `results[:n]` nach dem Sortieren
  oder README/`--help` klarmachen: „n pro Quelle".

### F8 — README: veraltete Zahlen + fehlende neue Quellen
- **Datei:Zeile:** `README.md:9` (Quellenliste ohne HN/GoogleNews/BingNews),
  `:72` und `:91` („111 Tests" → aktuell **121**), `:85` („Web-Bündel
  (7 Quellen)" → **10**).
- **Reproduktion:** `.venv/bin/python -m pytest tests/ -q -m "not live"` →
  121 passed.
- **Fix-Vorschlag:** Zahlen aktualisieren, die 3 neuen key-freien Quellen in
  die Quellenliste/Struktur aufnehmen.

### F9 — `.env.example` suggeriert Standalone-`.env`-Laden, das es nicht gibt
- **Datei:Zeile:** `.env.example:8` („cp .env.example .env (Standalone — wird
  automatisch geladen?)").
- **Problem:** Kein Code lädt ein Projekt-`.env`. Keys kommen nur aus
  `os.environ` + `~/.hermes/.env` (sucher_web.py:37-51, proxy.py:28-42);
  `launch.sh:20-23` sourced `~/.hermes/.env`. Wer `cp .env.example .env`
  macht, wundert sich, warum Keys ignoriert werden (Quelle wird übersprungen,
  still).
- **Fix-Vorschlag:** Entweder wirklich ein `.env`-Laden ergänzen (einfacher
  dotenv-artiger Reader in `_env`) oder die Zeile korrigieren auf
  `cp .env.example ~/.hermes/.env`.

### F10 — Offline-Suite macht echte Netzrequests (nicht `live`-markiert)
- **Datei:Zeile:** `tests/test_p6_web_buendel.py:153-172`
  (`test_web_suche_kein_exit_hang`): ruft `search_web` (alle 10 echten
  Quellen, inkl. neuer) in einem Subprozess OHNE Transport-Mock auf. Läuft in
  der Default-Suite (`-m "not live"`), obwohl README „Netz gemockt — offline
  reproduzierbar" verspricht (README.md:72).
- **Reproduktion:** Beim hiesigen Testlauf wurden reale Requests an
  hn.algolia.com/news.google.com/bing.com etc. gesendet (durch Budget 2 s
  begrenzt, daher grün).
- **Fix-Vorschlag:** Transport mocken (FakeTransport auch im Subprozess,
  z. B. env-Flag) oder Test als `@pytest.mark.live` markieren.

### F11 — Test-Isolation: `mojeek_route` patcht den Proxy-Fallback nicht (anders als `route_net`)
- **Datei:Zeile:** `tests/test_p6_web_buendel.py:31-35` (`mojeek_route` nur
  `_transport`) vs. `tests/test_block5_neue_quellen.py:61-71` (`route_net`
  patcht zusätzlich `_try_proxy`/`_try_proxy_post`).
- **Problem:** `test_mojeek_captcha_erkannt` liefert eine BLOCK-Antwort →
  `net.get_text` versucht den echten Proxy-Retry. Aktuell sind die
  Proxy-Credentials in `~/.hermes/.env` leer (kein Netz), aber sobald der
  dokumentierte DataImpulse-Proxy konfiguriert ist, geht der „Offline"-Test
  ins echte Netz.
- **Fix-Vorschlag:** `_try_proxy`/`_try_proxy_post` auch in `mojeek_route`
  (und allen Text-Block-Tests) neutralisieren.

### F12 — Test-Lücke: google_news/bing_news nicht durch den Fanout-/Cache-/Health-Pfad getestet
- **Datei:Zeile:** `tests/test_block5_neue_quellen.py:168-174` — nur `hn`
  läuft durch `search_web`. Für `google_news`/`bing_news` existieren nur
  q-Ebene-Tests (parse/Fehler), kein Fanout-Integrations-, Cache- oder
  Health-Regressionstest. Der Block-5-Register-/Health-Alias-Test
  (test_p6_web_buendel.py:239-248) deckt nur Label→Register-Strings statisch ab.
- **Fix-Vorschlag:** Je Quelle ein `search_web(…, only=…)`-Erfolgs- UND
  Fehlerpfad-Test mit Health-Assert (analog `test_fanout_liefert_hn_treffer`
  bzw. P6-B2-Muster), plus ein Cache-Hit-Test (cached ≠ Health-Signal).

### F13 — q_hn: Ask-HN-Link wird kaputt, wenn `objectID` fehlt
- **Datei:Zeile:** `src/sucher_web.py:328-329` — `f"…item?id={r.get('objectID',
  '')}"` ohne None-Check.
- **Problem:** Bei einem Datensatz ohne `url` UND ohne `objectID` (in der
  Praxis bei Algolia-Hits unüblich) entstünde `…item?id=`. Kein Crash, aber
  ein defekter Link.
- **Fix-Vorschlag:** `objectID` prüfen und Treffer sonst überspringen.

### F14 — News-Quellen parsen `pubDate` nicht → `year` ist immer None
- **Datei:Zeile:** `src/sucher_web.py:374` (q_google_news), `:419`
  (q_bing_news); ebenso `q_bing_html` (`:149`) — die RSS-Items enthalten
  `<pubDate>`, das Jahr wird verworfen. `q_hn` macht es vor (created_at →
  Jahr, `:330-334`).
- **Fix-Vorschlag:** Jahr aus `pubDate` extrahieren (analog q_hn) — kostet
  nichts und macht die News-Treffer z. B. für Jahres-Sortierung nutzbar.

### F15 — `search_web`: Quelle mit Treffern UND Fehler wird als `ok=True` verbucht
- **Datei:Zeile:** `src/sucher_web.py:605-608` — `hat_fehler and name not in
  quellen_mit_treffern → fail`, sonst `ok=True`.
- **Problem:** Loggt eine Quelle einen Fehler, liefert aber (Teil-)Treffer
  (z. B. Wikipedia DE fail / EN ok), verschwindet der Fehler im Health-Status
  und taucht nur 1× auf stderr auf. Bei konstant halbkaputten Quellen bleibt
  `HEALTHY` trotz Dauerfehler.
- **Fix-Vorschlag:** Bei `hat_fehler` und vorhandenen Treffern den Zustand
  zumindest nicht auf frisch `HEALTHY` setzen bzw. als „Teilerfolg mit
  Fehler" kennzeichnen (eigene Health-Semantik oder ok=False mit Notiz).

---

## Verifikation

- `pytest tests/ -q -m "not live"` → **121 passed, 2 deselected** (35 s)
- `mypy src/*.py sucher.py --ignore-missing-imports` → Success
- `ruff check src/ sucher.py scripts/` → All checks passed
- `bandit -r src/` → 0 High/Medium
- Live-Proben (03.09.2026): Google-News-Feed (100 Items), Bing-News-Feed
  (12 Items, apiclick-URLs korrekt extrahiert), Bing-Search-RSS, HN-Algolia,
  „captcha"-False-Positive reproduziert.

## Positiv-Befunde (kurz)

- apiclick-url-Extraktion (F1-Fokus) ist korrekt und sicher: unescape →
  `[?&]url=([^&]+)` → unquote; echte Ziele sauber (12/12 Live-Items), kein
  `&`-Truncation-Problem, kein SSRF (URLs werden nie nachgeladen).
- Health-Labels der 3 neuen Quellen (`hn`, `google_news`, `bing_news`)
  entsprechen exakt den Register-Keys; `_alias_fehler` + statischer
  Regressionstest greifen.
- `q_hn`-year-Parsing + Ask-HN-ohne-URL-Fall korrekt und getestet.
- Kein Regex-Catastrophe-Risiko (alle Muster nicht-gierig/linear).
