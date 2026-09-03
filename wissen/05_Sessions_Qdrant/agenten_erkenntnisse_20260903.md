# Konsolidierte Verbesserungs-Erkenntnisse — 3 Spezialisten-Agenten (03.09.2026)

> Ergebnis der Jobs 2+4+5: Qdrant/Rechner-Durchsuchung (Agent 1), Internet-Recherche (Agent 2),
> Architektur-Entwurf „funktioniert IMMER" (Agent 3). Alle Reports vollständig gelesen und
> hier konsolidiert. Ergänzt den P-Plan `docs/plans/SUCHER_1000_VERBESSERUNG_2026.md`.

## A. Die 12 „IMMER"-Mechanismen (Agent 3 — Kern-Architektur)

„Funktioniert meist" = Code existiert, aber jede unkontrollierte Abhängigkeit ist ein
Single Point of Failure. „IMMER" = 12 durchsetzbare Mechanismen im Zusammenspiel:

1. **Redundanz (kein SPOF):** ≥3 keyless Web-Quellen + 7 akademische + Wikipedia/Wikidata/Lokal.
   `q_lokal` ist die einzige OFFLINE-Quelle — liefert HAUPTLAGER-Treffer auch ohne Internet.
   Bleibt immer im Register (letztes Glied der Ergebnisgarantie).
2. **Zwei Zeitgrenzen:** Pro-Request-Timeout 8s (Transport) + globales Budget 25–30s
   (Orchestrierung). Heute: 12×25s sequenziell = bis 5 Min!
3. **Null stille Exceptions:** jedes `except` loggt (Quelle, URL, Fehlerklasse, Dauer)
   + zählt in Health. Heutige Stellen: sucher_universal Z.151, Z.221, Z.299–300.
4. **HTTP 200 ≠ Erfolg:** Format-Validierung — JSON anfordern, HTML/Captcha bekommen
   (BASE-Anubis!) = `FormatError`, zählt wie Block, löst Proxy-Retry aus.
5. **Proxy nur bei Block-Indikator:** 403/429/5xx/FormatError → 1× identischer Request
   über DataImpulse. Pro Quelle konfigurierbar (`proxy_allowed`). Akademische APIs: nie.
6. **Health als Daten + Cooldown:** `provider_health` in SQLite. 2 Fails → DEGRADED,
   3+ → BROKEN + 60min-Cooldown → BROKEN wird ÜBERSPRUNGEN statt ertragen.
7. **Key-optional:** Tavily/Exa/SerpApi nur bei Env-Key; fehlt → „übersprungen (kein Key)"
   in Diagnose, nie Fehler/Abbruch.
8. **Ergebnis-Garantie als Vertrag:** `search()` liefert IMMER `hits` (evtl. leer)
   + `diagnostics` (je Quelle: ok/Fehler/Treffer/Latenz). Leer mit Ursache = Diagnose.
9. **Hermes-Unabhängigkeit strukturell:** 0 Hermes-Importe, eigenes `.venv/` mit gepinnten
   requirements, eigener Git-Ordner, `launch.sh` ohne Hermes-Umgebung.
10. **Dedup + deterministisches Scoring NACH Fanout** — Reihenfolge nie von Thread-Zeit abhängig.
11. **Netz-gemockte Tests:** jede Quelle 4 Fälle (ok/leer/429/kaputt). Refactor-Bruch = rot.
12. **Ehrliche Grenzen:** kein „nie geblockt"-Versprechen, kein Brave (Karte), kein
    Google-SERP-Scraping. IMMER = Teilausfall → Tool liefert weiter + sagt, was fehlt.

**Test-Frage je Phase:** „Was passiert, wenn X heute stirbt/blockt/60s braucht/HTML liefert?"
Antwort muss sein: „Rest läuft, Fehler gemeldet, nächster Lauf skippt."

## B. Die 15 Ideen aus Qdrant/Rechner (Agent 1)

**Top 3 Hebel:** (5) Circuit-Breaker FAIL_COUNT, (13) DataImpulse-Proxy (Code existiert in
DeepWeb_Tool), (9) 200-≠-OK-Validierung.

| # | Idee | Beleg (Pfad) | Aufwand |
|---|------|--------------|---------|
| 1 | Tavily als karte-freier Default fest verdrahten | marktlage_2026.md; Keys in Env ✓ | klein |
| 2 | Empirische Quellen-Gewichte (Tavily hoch, Bing niedrig) | knowledge_nuggets Source-Weights | klein |
| 3 | n=30 pro Quelle + Query-Fanout (3× mehr Treffer) | DeepWeb Phase A: 30→117 unique | klein-mittel |
| 4 | Fehlende Keys melden ≠ Fehler (als Test sichern) | sucher_web.py Z.96-101 ✓ | klein |
| 5 | **Circuit-Breaker FAIL_COUNT=3** (wichtigster Fund) | ApplicationPlatform search_client.py | klein-mittel |
| 6 | Fallback-Kaskade mit Stats-Zählern | ApplicationPlatform search_router.py | klein |
| 7 | „Explicit config wins" als Anti-Muster meiden | Registry-Lesson (Hermes) | klein |
| 8 | Ersatz-Tabelle tote Engines: DDG-HTML `html.duckduckgo.com/html/?q=` + `uddg=`-Unwrap | dead_api_fallbacks.md | klein |
| 9 | **200-≠-OK: Roh-Bytes + JSON-Validierung + Blockseiten-Größe** | pitfalls_websuche §4 | klein |
| 10 | Antwort-Cache (1h TTL) gegen Rate-Limits | requests-cache im AuftragHunter | klein-mittel |
| 11 | ddgs-LIB (nicht CLI); Wikipedia-Array-Parser | pitfalls §6, §10 | klein |
| 12 | SearXNG nur lokal, Engines aktivieren, nie docker-exec-Heredoc | DeepWeb-Skill Pitfalls | mittel |
| 13 | **DataImpulse-Proxy: `--proxy` + Env** (Muster existiert fertig!) | DeepWeb config.py:112-113 | klein-mittel |
| 14 | Proxy strategisch: nur HTML-Quellen (Bing/Mojeek), nie akademisch | blocked-page-recovery | Policy |
| 15 | Fehler-Historie als Selbst-Checks: Brave-402, CAPTCHA-Cooldown, SSRF-pyflakes, Wayback-Leiter | knowledge_nuggets + Skills | mittel |

## C. Internet-Recherche (Agent 2 — Kernfakten)

- **SearXNG-Selfhost als aggregierender Kern**: bis 279 Dienste hinter EINER lokalen JSON-API,
  Engine-Status getrennt (/stats). Eigene Docker-Instanz isoliert von fragilen Quellen.
- **Öffentliche SearXNG-Instanzen als Fallback**: searx.space/data/instances.json (maschinenlesbar,
  Uptime+JSON-Flag je Instanz) → Top-N gesunde laden, bei Ausfall nächste.
- **ddgs** = wichtigste keyless Quelle (duckduckgo_search → ddgs umbenannt, pip install ddgs, v9.x).
- **Whoogle ist TOT** (Projekt beendet 24.07.2026, archiviert Aug 2026) — NICHT einplanen.
- **Serlo/Werbe-Angaben** („Searlo 3000/Monat") ohne Bestandsgarantie — vor Einbau verifizieren.
- Empfohlene Schichtung: SearXNG-lokal + Instanzen-Pool → ddgs → Free-Tier-APIs + Cache +
  Circuit-Breaker + RRF-Merge.

## D. Erkenntnisse für den P-Plan (Änderungen)

1. **P0 erweitert:** venv + pytest-Gerüst + FakeTransport SOFORT (nicht erst P3) — Hermes-Kollision ab Tag 1 aus.
2. **Reihenfolge P1→P3 geändert:** Fehler-Sichtbarkeit → net.py+Proxy → Parallelität
   (Begründung Agent 3: „Parallelität ohne gehärtete Fehler = schnelleres Schweigen").
3. **Bing = zerbrechlichste Quelle** (Layout-Änderungen) — Parser-Fixtures + Cooldown; nur 1 von 4 Web-Quellen.
4. **Mojeek-Widerspruch dokumentiert:** DeepWeb (08/2026) „funktioniert" vs. Live-Test (03.09) „Botwall 5KB" → bei Einbau: Botwall-Erkennung Pflicht.
5. **Proxy-Details:** Credentials `PROXY_LOGIN`/`PROXY_PASSWORD` existieren in Env; Host gw.dataimpulse.com:823; Erreichbarkeit dieser Session NICHT live getestet → P2-RED-Test.
6. **Gesamtaufwand Agent 3:** ~22–25h Handarbeit für P0–P7.
