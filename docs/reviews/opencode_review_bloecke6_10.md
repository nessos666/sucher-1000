# OpenCode-Review: Blöcke 6–10 (SUCHER-1000, 175 Tests)

Datum: 2026-09-03 · Review-Methode: 10 Tiefen-Durchgänge × Breite (alle Module,
alle Register, alle Tests, alle Fehlerpfade) · Jedes Finding am Code verifiziert
(Datei:Zeile) und, wo möglich, reproduziert.

## Verifikations-Basis (tatsächlich ausgeführt)

| Check | Ergebnis |
|---|---|
| `.venv/bin/python -m pytest tests/ -q -m "not live"` | **175 passed, 2 deselected** (41,1 s) |
| `.venv/bin/mypy src/*.py sucher.py --ignore-missing-imports` | Success: no issues |
| `.venv/bin/ruff check src/ sucher.py scripts/` | All checks passed |
| `.venv/bin/bandit -r src/ -q` | 23 Issues, alle Low, 0 Medium/High (bekannte, noqa-dokumentierte) |
| Register-Introspektion (Skript) | WEB=23 Quellen, SCI=16, GENERAL=3 |

Kein Finding ist geraten — jedes hat einen Code-Beleg und (wo sinnvoll) ein
Reproduktionsskript.

---

## Positive Befunde (nicht geschönt, aber sauber)

1. **Register/Gewicht/F2-Muster konsistent**: Alle `source`-Felder der 23
   WEB-`q_*` treffen `_WEB_WEIGHT` (lower()), alle SCI-`source`-Felder treffen
   `q_weight`. Es gibt **keinen** F2-Fall „source traf Gewicht nie".
2. **Fehler-Labels = Register-Keys**: `_log_web_error("<label>")` in allen
   q_*-Funktionen == WEB-Register-Key (syst. Skript-Check: 0 Mismatches).
3. **Health getrennt**: `wikipedia` (SCI) und `wikipedia_web` (WEB) sind in
   `data/health.json` getrennte Keys (F3-Fix greift).
4. **Cache-Namespace**: Fanout-Key `studien|…` vs. `web|…` verhindert die
   Wikipedia-Kollision (cache.py:53-54, F2-Shiraberu).
5. **Scholar-RegEx kein ReDoS**: 913-KB-HTML, 1000 Blöcke → 2 ms / Parse,
   5× in 9 ms. Kein katastrophales Backtracking.
6. **Feed ≠ Botwall (F1)** greift für Bing/Google-News-RSS; youtubei-POST läuft
   über `post_json` und ist von der Feed-Logik korrekt nicht betroffen.
7. Cache-Hit ≠ Health-Signal; Timeout nicht abgeschlossener Quellen wird nicht
   als HEALTHY verbucht; Worker-meldet-eigenen-Fehlerstatus (F4/F15) sind in
   beiden Fanouts umgesetzt.

---

## Findings

### MITTEL

#### M1 — Universaler Fanout verwirft Teiltreffer bei `err_lokal` (Datenverlust)

- **Datei:Zeile**: `src/sucher_universal.py:707-729` (Status-Verzweigung),
  Worker setzt Status `err_lokal` in `src/sucher_universal.py:686-687`.
- **Problem**: Der Worker sendet bei „Quelle loggte selbst einen Fehler" den
  Status `err_lokal` **inklusive payload**. Die Sammel-Schleife behandelt aber
  nur `ok`, `cached` und `err`. Ein `err_lokal`-payload (z. B. `q_wikipedia`
  DE schlug fehl, EN lieferte 2 Treffer) wird **ersatzlos verworfen** — die
  EN-Treffer fehlen im Ergebnis UND `quellen_mit_treffern` bleibt leer.
- **Inkonsistenz**: Der WEB-Fanout behält `err_lokal`-Teiltreffer explizit
  (sucher_web.py:1226-1237: `if payload and status in ("ok","err_lokal")`).
  Der universale Fanout hat kein Pendant.
- **Reproduktion** (ausgeführt):
  ```python
  def halb_kaputt(q, n):
      su._log_quellenfehler('wikimix', 'de-lang tot')
      return [{'title':'En-Treffer','url':'http://e.de','source':'Wikipedia'}]
  su.GENERAL = {'wikimix': halb_kaputt}; su.SCI = {}
  res = su.search('test', 3, mode='universal')
  # → Ergebnisse: []   (En-Treffer geht verloren)
  ```
- **Fix**: `err_lokal` wie im Web-Fanout behandeln: payload in `results`
  aufnehmen + `quellen_mit_treffern.add(name)` (Health bleibt gemäß F15
  `ok=False`). Ergänzend RED-Test „1 von 2 Sprachen tot → Treffer bleiben".

#### M2 — `block_indicator(erwartet="text")` killt echte Treffer-Seiten mit Marker-Wörtern

- **Datei:Zeile**: Marker-Liste `src/net.py:36-42`, Anwendung auf den ersten
  4000 Zeichen des Bodys `src/net.py:105-108`.
- **Problem**: Für HTML/Text-Seiten wird der **gesamte Body-Anfang** auf
  generische Wörter geprüft — darunter `anomaly`, `access denied`,
  `attention required`. Echte Ergebnisseiten von Google Scholar / DDG-HTML /
  Mojeek (allesamt `get_text`-Pfad) enthalten diese Wörter regelmäßig in
  Titeln/Snippets. Der Feed-Ausnahmezweig (net.py:101-104) schützt nur RSS,
  nicht HTML-Ergebnisseiten.
- **Reproduktion** (ausgeführt):
  ```python
  html = '<html><body><h3>Anomaly detection in network traffic …</h3>…'
  net.block_indicator(html.encode(), erwartet='text')
  # → 'BLOCK: anomaly'   (obwohl eine normale Trefferseite)
  ```
  Konkret: `q_google_scholar("anomaly detection …")` liefert dauerhaft
  `BLOCK: anomaly` statt Treffern → Fehl-Health-Fails bis BROKEN (60-Min-Cooldown)
  für eine gesunde Quelle, allein wegen des Suchbegriffs.
- **Fix**: Für `erwartet="text"` Marker nicht body-weit prüfen, sondern
  strukturell: (a) Marker nur im `<title>`/`<head>`-Bereich ODER (b) Block nur
  wenn Marker **und** keine erwartete Ergebnisstruktur (Result-Links/-Divs)
  vorhanden. Mindestens die Marker `anomaly`/`attention required` sind für
  generische Web-Ergebnisse zu unspezifisch.

#### M3 — Health-Lost-Update-Race im Modus `alle`

- **Datei:Zeile**: `sucher.py:88-99` (zwei parallele Threads rufen
  `su.search(...)` und `sw.search_web(...)` auf), `src/health.py:66-72`
  (`save()` schreibt die **ganze** Datei aus dem beim `__init__` geladenen
  Snapshot).
- **Problem**: Beide Fanouts erzeugen **je eine eigene**
  `HealthRegistry()`-Instanz auf derselben Datei. `save()` überschreibt die
  Datei mit dem jeweils eigenen, beim Konstruktor geladenen Stand
  (tmp+replace ist atomar, aber kein Merge). Wer zuletzt speichert, verliert
  die Updates des anderen: z. B. speichert der Web-Fanout (schneller fertig)
  seine Web-Updates, danach überschreibt der Studien-Fanout mit seinem
  Snapshot vom Laufbeginn → Web-`record_outcome` (BROKEN/HEALTHY/NO_KEY)
  verschwindet. Umgekehrt ebenso.
- **Reproduktion**: Code-Lese-Beleg reicht (zwei Instanzen, `_data` je
  Ladezeitpunkt, Ganz-Datei-Write). Race ist completion-order-abhängig.
- **Fix**: Eine gemeinsame `HealthRegistry`-Instanz in `sucher.py` an beide
  Fanouts übergeben (Parametrisierung), oder `save()` vor dem Schreiben die
  Datei neu laden lassen (merge), oder Datei-Lock über Instanzen hinweg.

#### M4 — `q_wikis` ignoriert die `n`-Obergrenze (bis 30 Treffer bei n=8)

- **Datei:Zeile**: `src/sucher_web.py:516-552`, Rückgabe `return out` in
  Zeile 552 ohne `out[:n]`-Cap.
- **Problem**: Der Adapter iteriert 6 Sub-Projekte (Wikiquote/Wikinews/
  Wikisource DE+EN) und sammelt je Projekt bis `min(n,5)` Einträge. Bei n=8
  werden so **bis zu 30** Treffer geliefert (n=3 → bis zu 18). Das bricht die
  dokumentierte Semantik „`n` pro Quelle" und bläht Cache-Payloads, Trefferzahl
  und Dedup-Basis im Fanout unkontrolliert auf (23 Quellen × n ⇒ keine
  vorhersagbare Gesamtzahl mehr).
- **Reproduktion** (ausgeführt): `q_wikis('x', 3)` → 18 Treffer;
  `q_wikis('x', 8)` → 48 (mit 9 Fake-Ergebnissen je Projekt). Der Block-7-Test
  `test_wikis_parst_mediawiki` zementiert das Verhalten (assert len==6 bei n=3).
- **Fix**: `return out[:n]` (Web-Quellen-Konvention wie `q_wikipedia_web`/
  `q_huggingface`). Block-7-Test dann auf `<= n` korrigieren. Falls die
  6 Sub-Projekte bewusst „mehr als n" liefern sollen, muss die n-Semantik in
  CLI-Hilfe/README explizit dokumentiert werden (aktuell widersprüchlich).

#### M5 — Präfix-Alias in `_web_fehler_count`/`_alias_fehler` kann echte Fehler maskieren

- **Datei:Zeile**: `src/sucher_web.py:67-70` und `1252-1267`
  (Präfix-Fallback `label.lower().startswith(low)` / umgekehrt).
- **Problem**: `bing` ist Präfix von `bing_news`. Der Worker zählt „vorher"
   per `_web_fehler_count(register-key)`. Loggt nur `bing_news` einen Fehler,
   liefert `_web_fehler_count('bing')` fälschlich dessen Zähler (kein exakter
   Match → Präfix-Match). Schlägt danach `q_bing_html` fehl und loggt unter
   `bing`, ist `vorher == nachher` → `hatte_fehler=False` → die Quelle wird im
   Health-Commit trotz Fehler als `ok` verbucht (bleibt HEALTHY trotz konstantem
   Block). Alle heutigen Labels sind bereits exakt==Register-Key (verifiziert),
   der Präfix-Fallback ist also toter Code mit reinem Schadensrisiko.
- **Reproduktion** (ausgeführt):
  ```python
  w._log_web_error('bing_news', 'BLOCK')
  w._web_fehler_count('bing')   # → 1  (sollte 0 sein: bing selbst fehlerfrei)
  ```
- **Fix**: Präfix-Fallback entfernen; nur exakt + lower() vergleichen
  (F2-Fall „Mojeek" vs. „mojeek" wird durch lower abgedeckt). Beide Stellen
  synchron ändern.

---

### NIEDRIG

#### N1 — `list_web()`/`--sources` deklariert neue Key-Quellen als „frei"

- **Datei:Zeile**: `src/sucher_web.py:1289-1292` (hartkodiertes Tupel
  `("tavily","serpapi","exa")`).
- **Problem**: `reddit`, `knowledgegraph`, `google_books` stehen in
  `KEY_QUELLEN_MAP` (Zeile 1072-1075) und werden zur Laufzeit ohne Key als
  NO_KEY übersprungen — die Quellenliste (ausgeführt: `sucher.py --sources`)
  zeigt sie aber als `(frei)`. Nutzer erfahren den Key-Bedarf erst zur Laufzeit.
- **Fix**: `needs = "Key" if name in KEY_QUELLEN_MAP else "frei"`.

#### N2 — Offline-Test `test_cli_0_treffer_kein_crash` geht ins echte Netz

- **Datei:Zeile**: `tests/test_p5_cli_e2e.py:41-52` (kein `@pytest.mark.live`,
  kein `net._transport`-Mock, keine Proxy-Neutralisierung).
- **Problem**: Der Test startet `sucher.py … --modus web` als Subprozess → das
  echte `search_web` feuert bis zu 23 Live-Requests (incl. Reddit-Token-Pfad)
  mit 30-s-Budget. Das verletzt die eigene Zusage „Netz gemockt — offline
  reproduzierbar" (F10) und verbraucht fremde API-Quota in der Standard-Suite.
  Er besteht offline nur, weil die Requests fehlschlagen.
- **Fix**: Netz im Subprozess mocken (FakeTransport-Muster wie
  `test_p6_web_buendel.py:172-184`) oder `@pytest.mark.live`.

#### N3 — Doku/UX-Zahlen veraltet (Quellen- und Testzahlen)

- **Datei:Zeile**: `sucher.py:51-52` („bei 10 Web-Quellen also bis zu ~80
  Treffer" — real 23 Web-Quellen), `README.md` („121 automatisierte Tests",
  „Web-Suche (10 Quellen…)"), `launch.sh:27` („12 Studien-Quellen" — real 16),
  Modul-Docstring `src/sucher_web.py:9-17` (listet nur 7 Quellen).
- **Fix**: Zahlen aus den Registern ableiten bzw. aktualisieren.

#### N4 — `.env.example` dokumentiert neue optionale Keys nicht

- **Datei:Zeile**: `.env.example:14-35`.
- **Problem**: `REDDIT_CLIENT_ID/SECRET`, `GOOGLE_KG_API_KEY`,
  `GOOGLE_BOOKS_API_KEY` fehlen in der Vorlage, obwohl sie in
  `KEY_QUELLEN_MAP` sind und ohne Doku in `--sources` als „frei" erscheinen.
- **Fix**: Drei Blöcke mit Hinweis „optional, sonst wird übersprungen" ergänzen.

#### N5 — Produktions-`health.json` enthält Test-Artefakt `fake`

- **Datei:Zeile**: `data/health.json` (nicht in git; Zustand nach Testlauf).
- **Problem**: Eintrag `"fake": HEALTHY` — offensichtlich ein Test-/Dev-Artefakt,
  das in die echte Registry gewandert ist (kein Register-Key existiert).
  → Daten-Anomalie; Default laut Regelwerk ist (b) bereinigen, nicht Code
  defensiv machen.
- **Fix**: Eintrag löschen (`.venv/bin/python -c` … `pop("fake"); save()`).
  Optional Ursache ermitteln (welcher Lauf ohne SUCHER_HEALTH_FILE-Setzung).

#### N6 — Doppelte `.removesuffix("/en")` (Kosmetik)

- **Datei:Zeile**: `src/sucher_web.py:731-732` — zweites `removesuffix("/en")`
  ist nach `rstrip("/").removesuffix("/en")` ein No-op.
- **Fix**: Zeile 732 entfernen.

---

## Test-Lücken (Durchgang 7)

- Kein Test deckt den `err_lokal`-Teiltreffer-Pfad des universalen Fanouts ab
  (M1) — der Web-Fanout hat F12/F15-Tests, der universale nicht.
- Kein Test prüft `q_wikis`-`n`-Obergrenze (M4); der Block-7-Test kodiert die
  Überlieferung sogar als Soll.
- Kein Test für Präfix-Alias-Nebenwirkung `bing`/`bing_news` (M5).
- Kein Test für Health-Konsistenz im Modus `alle` (M3, zwei Registries).
- Fehlerpfad „Quelle liefert gültiges JSON, aber falsche Struktur (Liste statt
  dict)" ist nur über den generischen Worker-`except` abgesichert, nicht
  getestet.
- `route_net`-Fixture mit Proxy-Aus ist in Block 5–10 vorbildlich konsistent.

---

## Verdict

**FAIL** — reproduzierbare Funktionsfehler erfordern Fixes vor der nächsten
Feature-Stufe: (M1) universale Teiltreffer werden verworfen, (M2) text-Block-
Erkennung killt echte Ergebnisseiten bei unspezifischen Marker-Wörtern,
(M3) Health-Lost-Update-Race in `--modus alle`, (M4) `q_wikis`-n-Cap,
(M5) Präfix-Alias kann Fehler maskieren. Dazu 6 niedrige Funde (UX-Doku,
.env.example, Offline-Suite, Daten-Hygiene).

Geprüfte Grundlage: 175 Tests grün, mypy/ruff sauber, bandit ohne neue Funde,
Register×Gewicht×Label konsistent — die Architektur ist tragfähig, die Bugs
sind lokal und mit obigen Fixes klein.

**Anzahl Findings: 11 (0 HOCH / 5 MITTEL / 6 NIEDRIG) · Höchste Schwere: MITTEL**
