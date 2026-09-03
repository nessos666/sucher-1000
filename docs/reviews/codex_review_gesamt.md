# Codex Review Gesamt

Stand geprüft: `master` @ `b23bc11884566b08489588379e7b89d87c9ed27e` am 2026-09-03

Ausgeführt:
- `.venv/bin/python -m pytest tests/ -q` → `90 passed, 2 deselected`
- `./check.sh tests` → `FAIL` (`ruff` rot, `bandit` rot)

## FINDINGS

1. `src/net.py:237` `HIGH`
   `get_text()` validiert den Proxy-Body im `HTTPError`-Pfad nicht mehr auf Botwall/Captcha. Reproduktion: bei direktem `HTTP 403` und Proxy-Response `"<html>captcha required</html>"` liefert die Funktion aktuell `(text, None)` statt eines Fehlers. Dadurch können Blockseiten als Erfolg in Parser und Health laufen. Fix: im Branch `e.code in (403, 429)` denselben `block_indicator(..., erwartet="text")`-Check anwenden wie im normalen Block-Pfad und nur saubere Proxy-Antworten akzeptieren.

2. `src/sucher_universal.py:406` `HIGH`
   Im akademischen Fanout werden Quellen nach Budget-Ablauf als `ok=True` verbucht, obwohl ihr Worker nie fertig wurde. Reproduktion: eine Quelle mit `sleep(2)` und `budget_s=0` endet mit leerem Ergebnis, aber `HealthRegistry().status("slow") == HEALTHY`. Das kaschiert Timeouts als Gesundheit und unterläuft Cooldown/Selbstheilung. Fix: abgeschlossene Quellen separat tracken; nur abgeschlossene Quellen committen, nicht beantwortete Quellen als `timeout`/Fehler oder gar nicht bewerten.

3. `src/sucher_web.py:381` `HIGH`
   Das gleiche Timeout-zu-`HEALTHY`-Problem existiert im Web-Fanout. Reproduktion: `search_web(..., timeout=0)` auf einer hängenden Quelle schreibt `HEALTHY`, obwohl kein Payload eingesammelt wurde. Damit werden gerade die Quellen gesundgemeldet, die das Budget reißen. Fix: analog zu `sucher_universal.py` nur tatsächlich abgeschlossene Quellen healthen; offene Worker nach Timeout nicht als Erfolg werten.

4. `sucher.py:97` `MEDIUM`
   `--modus alle` verwirft beim URL-Dedup jeden Treffer ohne `url`, statt ihn nur nicht zu deduplizieren. Der Code hängt `dedup.append(r)` an `if url and url not in seen`; Einträge mit `None`/leerem URL-Feld verschwinden also komplett. Das ist echter Datenverlust, weil mehrere aktive Quellen `url` optional liefern. Fix: für URL-lose Treffer einen Fallback-Key wie `title+source+year` verwenden oder solche Treffer ungefiltert übernehmen.

5. `src/sucher_oa.py:25` `MEDIUM`
   Der OA-Resolver umgeht die gehärtete Transport-Schicht komplett: direktes `urlopen`, `timeout=25`, kein Retry, keine Block-Erkennung, kein Proxy-Fallback. Das widerspricht der Projektprämisse "immer funktionieren" und verhält sich anders als `src/net.py`. Fix: `http_json()` auf `net.get_json()` umstellen oder eine gemeinsame gehärtete JSON-Hilfsfunktion verwenden.

6. `pyproject.toml:25` `MEDIUM`
   Die neue Ruff-Konfiguration ist als Profi-Gate derzeit kaputt. `S110` ist global aktiv, die beabsichtigten Unterdrückungen sitzen aber überwiegend auf der `pass`-Zeile statt auf der diagnostizierten `except`-Zeile; dadurch meldet `ruff` im aktuellen Stand 25 Fehler und `./check.sh tests` wird rot, obwohl die Suite grün ist. Fix: `# noqa: S110` an die `except`-Zeile verschieben oder die betroffenen Dateien sauber in `per-file-ignores` aufnehmen; alternativ `S110` nicht global selektieren, wenn das Fallback-Design bewusst erlaubt ist.

7. `src/store.py:167` `LOW`
   Die Bandit-Unterdrückung für den dynamischen `NOT IN (?,...,?)`-Query greift nicht, weil `# nosec B608` an `conn.execute(` hängt, die eigentliche Beanstandung aber auf der SQL-String-Zeile landet. Ergebnis: `bandit` meldet einen Medium-Fund und `./check.sh tests` bleibt rot, obwohl der Query parametrisiert ist. Fix: `# nosec B608` direkt an die SQL-Expression setzen oder den Query-Aufbau so umstellen, dass Bandit ihn nicht mehr als String-Konstruktion erkennt.

## VERDICT

`FAIL`

Begründung: Die Tests sind zwar grün, aber zwei zentrale Laufzeitfehler bleiben im Produktcode: beide Parallel-Fanouts markieren nicht abgeschlossene Timeout-Quellen als `HEALTHY`, und der gehärtete Text-Transport akzeptiert im Proxy-Fehlerpfad wieder Captcha-HTML als Erfolg. Zusätzlich ist das Qualitäts-Gate im aktuellen Stand selbst nicht grün (`ruff`, `bandit`), und `--modus alle` verliert Treffer ohne URL. Die Suite deckt genau diese Timeout-Health- und `modus=alle`-Fälle derzeit nicht ab.
