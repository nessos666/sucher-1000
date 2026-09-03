# Code Review P0-P3

## Finding 1
- Datei:Zeile: `src/sucher_web.py:152`
- Schweregrad: `HOCH`
- Beschreibung: `search_web()` nutzt einen `ThreadPoolExecutor` als Kontextmanager. Wenn `as_completed(..., timeout=timeout)` in Zeile 155 wegen Timeout abbricht, wird der `except`-Block zwar erreicht, aber beim Verlassen des `with`-Blocks wartet `ThreadPoolExecutor.__exit__()` trotzdem auf alle noch laufenden Worker. Damit ist das dokumentierte Zeitbudget nicht hart; eine hängende Web-Quelle kann den gesamten Aufrufer weiter blockieren.
- Konkreter Fix-Vorschlag: Den Executor wie in `sucher_universal.search()` ohne Kontextmanager verwalten und im `finally` mit `shutdown(wait=False, cancel_futures=True)` schließen. Zusätzlich sollte das Timeout gezielt nur `TimeoutError` behandeln statt pauschal jede Exception.

## Finding 2
- Datei:Zeile: `src/net.py:132`
- Schweregrad: `HOCH`
- Beschreibung: `get_text()` versucht bei Block/403/429 einen Proxy-Retry, ruft dafür aber `_try_proxy(url, timeout)` auf. `_try_proxy()` ruft in Zeile 155 immer `proxy.fetch(..., erwartet="json")` auf. Für Text/HTML-Endpunkte kann der Proxy-Pfad damit nie erfolgreich sein, weil `proxy.fetch()` Nicht-JSON als Fehlschlag verwirft. Der beworbene Proxy-Fallback ist für Textquellen faktisch kaputt.
- Konkreter Fix-Vorschlag: `_try_proxy()` um einen Parameter `erwartet` erweitern und aus `get_json()` mit `json`, aus `get_text()` mit `text` aufrufen. `proxy.fetch()` kann dann korrekt zwischen JSON- und Textantworten unterscheiden.

## Finding 3
- Datei:Zeile: `src/sucher_universal.py:229`
- Schweregrad: `HOCH`
- Beschreibung: `q_base()` umgeht die zentrale Transport-Härtung aus `net.py` vollständig und verwendet direkt `urllib.request.urlopen(..., timeout=30)`. Damit fallen genau für eine der problematischsten Quellen die P2/P3-Schutzmechanismen weg: kein 8s-Limit, keine Blockseiten-Erkennung, kein Retry, kein Proxy-Fallback. Das reintroduziert lange Hänger und falsch als "leer" interpretierte Botwall-Antworten.
- Konkreter Fix-Vorschlag: `q_base()` auf `http_json()` bzw. `net.get_json()` umstellen und den 30s-Direct-Call entfernen. Falls BASE kein valides JSON mehr liefert, sollte die Quelle explizit deaktiviert oder als HTML-Scraper mit `net.get_text()` und klarer Parser-/Blocklogik neu implementiert werden.

## Finding 4
- Datei:Zeile: `src/scripts/health_check.py:85`
- Schweregrad: `MITTEL`
- Beschreibung: Der `--json`-Pfad erzeugt kein sauberes JSON auf `stdout`. Vor dem `if as_json:`-Block werden bereits Statuszeilen und Überschriften ausgegeben (Zeilen 60-84). Automatisierte Konsumenten, die `python3 scripts/health_check.py --json` parsen wollen, erhalten daher gemischten Text statt gültigem JSON.
- Konkreter Fix-Vorschlag: Bei gesetztem `--json` alle Konsolenprints vorab unterdrücken und ausschließlich `json.dumps(...)` ausgeben. Alternativ den menschenlesbaren Report auf `stderr` schreiben und JSON strikt auf `stdout` belassen.

## Finding 5
- Datei:Zeile: `src/sucher_universal.py:19`
- Schweregrad: `MITTEL`
- Beschreibung: `_QUELLEN_FEHLER` ist global und wird in `search()` nicht zurückgesetzt. Fehler aus einem früheren Lauf bleiben dadurch im Prozess erhalten und tauchen in späteren, erfolgreichen Suchen erneut in `pretty()` auf. Bei mehreren Aufrufen im selben Prozess sind die Diagnosen damit nicht mehr laufbezogen und führen zu falscher Fehlersichtbarkeit.
- Konkreter Fix-Vorschlag: `_QUELLEN_FEHLER` zu Beginn von `search()` leeren oder das Fehlerregister pro Aufruf lokal führen und zusammen mit den Ergebnissen zurückgeben. Die Ausgabe in `pretty()` sollte nur die Fehler des aktuellen Suchlaufs anzeigen.

## Finding 6
- Datei:Zeile: `src/sucher_web.py:149`
- Schweregrad: `MITTEL`
- Beschreibung: `search_web(..., only=...)` filtert nur bei bekannten Quellnamen. Ein unbekannter Wert wird still ignoriert, und die Funktion durchsucht dann alle Web-Quellen. Das ist derselbe Bedienfehler, der in `sucher_universal.search()` bereits explizit behoben wurde. Für CLI- oder API-Aufrufer ist das irreführend und kann unnötige Netzlast erzeugen.
- Konkreter Fix-Vorschlag: Das Verhalten an `sucher_universal.search()` angleichen: unbekannte Web-Quelle explizit auf `stderr` melden und `[]` zurückgeben, statt still auf den Komplettlauf zurückzufallen.

## Finding 7
- Datei:Zeile: `src/net.py:73`
- Schweregrad: `NIEDRIG`
- Beschreibung: `block_indicator()` akzeptiert bei `erwartet="json"` nur Antworten, deren erster Nicht-Whitespace-Charakter `{` oder `[` ist. Gültige JSON-Skalare wie `"ok"`, `true`, `false`, `null` oder `123` werden damit fälschlich als `FORMAT`/`HTML` klassifiziert. Das ist derzeit vermutlich selten, aber die Transport-Schicht ist damit unnötig enger als JSON selbst.
- Konkreter Fix-Vorschlag: Die Formatprüfung nicht über Präfixe, sondern über einen echten `json.loads()`-Versuch implementieren. Nur wenn Parsing scheitert und zugleich HTML-/Bot-Marker erkennbar sind, sollte der Transport `FORMAT` oder `BLOCK` melden.

## Verdict
`VERDICT: FAIL`

Die P0-P3-Serie verbessert Tests, Sichtbarkeit und Parallelisierung deutlich, ist aber noch nicht freigabereif. Zwei zentrale Architekturversprechen sind aktuell nicht zuverlässig erfüllt: Das Web-Bündel hat kein hartes Timeout, und der Proxy-Fallback funktioniert für Textquellen nicht. Dazu kommen ein direkter Bypass der gehärteten HTTP-Schicht bei `BASE`, fehlerhafte `--json`-Ausgabe im Health-Check und prozessweit auslaufende Fehlerdiagnostik. Solange diese Punkte offen sind, besteht weiterhin Risiko für Hänger, irreführende Diagnosen und falsche Betriebsannahmen.
