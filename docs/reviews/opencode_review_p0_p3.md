# Code Review P0-P3 (Opencode-Zweitmeinung)

Unabhängige Review der Commits `fc57e0d..2adc0ca` (P0-P3 + Codex-Fixes) als Zweitmeinung nach Codex. Geprüft: `src/sucher_universal.py`, `src/sucher_web.py`, `src/net.py`, `src/proxy.py`, `sucher.py`, `scripts/health_check.py`, `tests/`. Kriterien: echte Bugs, Race-Conditions, Sicherheit, Logikfehler in Parallelität/Scoring/Dedup, Test-Lücken. Tests selbst ausgeführt: `24 passed` (12-16s intern), aber Wanduhr `70s` — Prozess hängt nach Testende.

## Finding 1
- Datei:Zeile: `src/sucher_universal.py:357-360`, `src/sucher_web.py:174-176`
- Schweregrad: `HOCH`
- Beschreibung: Budget nicht prozess-hart; Exit hängt. `shutdown(wait=False, cancel_futures=True)` lässt laufende Worker weiterlaufen. ThreadPool-Worker sind in Py3.11 **non-daemon**; der Interpreter joined sie beim Exit (verifiziert: Skript mit 5s-Sleep dauerte 8s/5s Wanduhr trotz sofortigem `shutdown`). Folge: Wird das Budget überschritten, kehrt `search()` zwar sofort zurück, aber der CLI-Prozess (sucher.py, sucher_universal.py) blockiert bis die verwaiste Quelle endet (net 8s, arxiv 30s, Tests 60s). Die Budget-Tests (`test_p3_parallel.py:41`, `test_codex_fixes.py:26`) messen nur die Funktions-Rückkehr — pytest meldet `12.28s` intern, Prozess lief `70.39s`. Die Live-Claims „hartes Budget / 3.8s" sind nur bei schnellen Quellen wahr.
- Konkreter Fix-Vorschlag: Worker-Threads als Daemon-Threads führen (eigener Executor mit daemon-Thread-Factory) oder die Suche in einen Kind-Prozess auslagern, der nach Budget hart beendet wird. Alternativ am Prozessende explizit verwaiste Threads nicht mehr joinen. Zusätzlich die Budget-Tests so erweitern, dass sie die Prozess-Wanduhr statt nur die Funktions-Rückkehr messen.

## Finding 2
- Datei:Zeile: `src/sucher_universal.py:157-160` (q_arxiv)
- Schweregrad: `MITTEL`
- Beschreibung: q_arxiv (aktive Quelle) umgeht die ganze net.py-Härtung: direktes `urlopen(timeout=30)` ohne 8s-Cap, ohne Block-Erkennung, ohne Proxy-Fallback. Eine hängende arXiv-Antwort frisst das komplette 30s-Gesamtbudget. Widerspricht dem net.py-Anspruch „zentrale Schicht für ALLE Quellen" (`net.py:5-7`). Codex-F3 fixt nur q_base, nicht q_arxiv. (q_biorxiv `:177` tot, nicht registriert.)
- Konkreter Fix-Vorschlag: q_arxiv auf `net.get_text()` bzw. `http_json()` umstellen, sodass 8s-Cap, Block-Erkennung und Proxy-Fallback greifen. Den toten q_biorxiv-Pfad entweder registrieren oder entfernen.

## Finding 3
- Datei:Zeile: `src/sucher_universal.py:49, 68, 87, 107, 203, 254, 141` (q_openalex, q_crossref, q_doaj, q_europepmc, q_pubmed, q_wikidata, q_wikipedia, und q_semanticscholar)
- Schweregrad: `MITTEL`
- Beschreibung: P1-Fehler-Sichtbarkeit greift auf dem Hauptfehlerpfad nicht. `if "_error" in j: return []` erfolgt **ohne** `_log_quellenfehler`. Timeout/429 via net sind die häufigsten Fehler und erscheinen nie im Register — `pretty()` meldet dann „keine Quellen-Fehler", obwohl alle Quellen tot waren. Nur arxiv/base/biorxiv bzw. geworfene Exceptions werden geloggt. Tests injizieren nur werfende, nie `_error`-liefernde Quellen → Lücke.
- Konkreter Fix-Vorschlag: In jedem `if "_error" in j`-Zweig `_log_quellenfehler(name, j["_error"])` aufrufen. Tests um einen Fall ergänzen, in dem `net.get_json` ein `_error`-Dict liefert statt zu werfen.

## Finding 4
- Datei:Zeile: `src/net.py:141-146`, `src/proxy.py:81`
- Schweregrad: `MITTEL`
- Beschreibung: Proxy-Text-Fallback unvalidiert. Beim `erwartet="text"`-Pfad wird die Proxy-Antwort **ohne** `block_indicator`-Check zurückgegeben. Liefert DataImpulse eine Captcha/Botwall-Seite (Text), gilt sie als Erfolg — genau die F2-Falle, die der Fix beheben sollte, bleibt im Proxy-Pfad offen.
- Konkreter Fix-Vorschlag: Auch die Text-Antwort aus `proxy.fetch(..., erwartet="text")` vor der Rückgabe durch `block_indicator(body, erwartet="text")` prüfen und bei Block-Erkennung als Fehlschlag behandeln.

## Finding 5
- Datei:Zeile: `src/sucher_universal.py:320`, `src/sucher_universal.py:28`
- Schweregrad: `NIEDRIG`/`MITTEL`
- Beschreibung: Race: verwaiste Threads schreiben in Folge-Läufe. `_QUELLEN_FEHLER` ist Modul-global, `clear()` nur bei Suchstart (`:320`), `_log_quellenfehler` schreibt aus Worker-Threads (`:28`, nicht-atomares read-modify-write für den Zähler). Ein über das Budget abgeschnittener Thread aus Lauf 1, der nach dem `clear()` von Lauf 2 fehlschlägt, verfälscht dessen Diagnose. F5 fixt nur abgeschlossene Lauf-1-Fehler.
- Konkreter Fix-Vorschlag: Das Fehlerregister pro Aufruf lokal führen (Aufbau über eine Lock oder thread-lokale/atomare Aktualisierung) und verwaiste Worker nach Budget so kappen, dass sie keine Folge-Läufe mehr beschreiben können (siehe Finding 1).

## Finding 6
- Datei:Zeile: `src/net.py:74-88`
- Schweregrad: `NIEDRIG`
- Beschreibung: F7-Skalar-Logik inkonsistent. Die Zeilen lassen gültige JSON-Skalare als „kein Block" durch, aber der `get_json`-Vertrag verspricht dict/list (`net.py:17-19`) und jede `q_*`-Funktion crasht mit `TypeError` bei `True/123` (`"_error" in j`), was dann als Quellenfehler geloggt wird. Die F7-Semantik existiert nur isoliert im Unit-Test.
- Konkreter Fix-Vorschlag: Entweder `get_json` garantiert nur dict/list zurückzugeben (Skalare als `FORMAT`-Fehler behandeln) und den Unit-Test entsprechend anpassen, oder alle `q_*`-Konsumenten typ-robust machen. Beides zusammen ist widersprüchlich — eine der beiden Semantiken festlegen.

## Finding 7
- Datei:Zeile: `src/sucher_universal.py:427`
- Schweregrad: `NIEDRIG`
- Beschreibung: Scoring „deterministisch" nur näherungsweise. `sorted` ist stabil, aber die Eingabe = Completion-Reihenfolge paralleler Futures → bei Punktgleichstand variiert die Rangfolge zwischen Läufen.
- Konkreter Fix-Vorschlag: Als letzten Sortierschlüssel einen stabilen Wert ergänzen (z. B. Titel/URL), damit Punktgleichstände laufunabhängig deterministisch aufgelöst werden.

## Finding 8
- Datei:Zeile: `src/sucher_universal.py:283` (q_lokal)
- Schweregrad: `NIEDRIG`
- Beschreibung: q_lokal-Divergenzen. Docstring verspricht „Dateinamen + Inhalt", Code matcht nur Dateinamen. Zeitlimit wird nur zwischen Verzeichnissen geprüft — ein riesiger Ordner kann es überziehen. Bis zu 3 Query-Varianten walken parallel über 133GB.
- Konkreter Fix-Vorschlag: Zeitlimit auch während des Walkens innerhalb eines Verzeichnisses prüfen, Docstring an das tatsächliche Verhalten anpassen (oder Inhalts-Matching ergänzen) und die Anzahl paralleler Walker begrenzen.

## Finding 9
- Datei:Zeile: `src/sucher_universal.py:35-42`
- Schweregrad: `NIEDRIG`
- Beschreibung: http_json-Shim verschluckt timeout. Signaturdefault `timeout=25`, implementiert aber hart `8` — ein übergebener Timeout wird still ignoriert.
- Konkreter Fix-Vorschlag: Den Parameter tatsächlich durchreichen (`net.get_json(url, timeout=timeout, retries=retries)`) oder die Signatur auf den realen Wert (`timeout=8`) korrigieren, damit kein Aufrufer von einem falschen Default ausgeht.

## Finding 10
- Datei:Zeile: `src/scripts/health_check.py` (TIMEOUT_PER), `tests/test_codex_fixes.py:89-104`, `tests/`
- Schweregrad: `TEST-LÜCKEN`
- Beschreibung: (a) `test_codex_fixes.py:89-104` (F4) ist ein **Live-Netz-Test in der Offline-Suite** und verbraucht echte API-Quota (TAVILY_KEY aus `~/.hermes/.env` vorhanden) — offline schlägt die Suite fehl. (b) Kein Test deckt die `_error`-Stille (Finding 3), Skalar-end-to-end (Finding 6) oder Prozess-Exit-Hang (Finding 1) ab. (c) Dedup-Key auf 90 Zeichen gekappt (`src/sucher_universal.py:348`) — Kollisions-/Bound-Verhalten ungetestet. (d) `health_check.py`: `TIMEOUT_PER=12` wird nie erzwungen, Läufe seriell → Dauer = Summe der Quellen-Timeouts.
- Konkreter Fix-Vorschlag: Live-Test hinter Marker/Umgebungsvariable stellen oder aus der Suite entfernen; Regressionstests für `_error`-Logging, Skalar-Antworten und Prozess-Exit-Hang ergänzen; Dedup-Key-Bound testen; im Health-Check `TIMEOUT_PER` durchsetzen und Quellen parallel laufen lassen.

## Verdict
`VERDICT: FAIL`

Die zentralen P3-/P2-Zusagen (hartes Budget auf Prozessebene, 8s für alle Quellen, lückenlose Fehlersichtbarkeit) sind durch den Exit-Hang mit verwaisten Threads, den arxiv-Bypass und die stille `_error`-Behandlung real nicht erfüllt — das sollte vor Merge behoben werden.
