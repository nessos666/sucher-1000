# SUCHER-1000 — Verbesserungsplan „Höchstes Level" (P-Plan 2026-09)

> Erstellt: 03.09.2026 nach Live-Recherche (Marktlage 2026) + vollständigem Code-Read.
> Ziel: **SUCHER funktioniert IMMER** — unabhängig von Hermes-Updates/-Fehlern.
> Methode: Davids Build-Regeln (Checken→Forschen→Bauen, Phase für Phase, Plan zuerst).

## Ist-Zustand (ehrlich, aus Code gelesen)

`sucher_universal.py` (441 Zeilen, 1 Datei):
- ✅ 12 Quellen-Funktionen: OpenAlex, Crossref, DOAJ, EuropePMC, SemScholar, Wikipedia, arXiv, PubMed, BASE, Wikidata, Lokal (+ bioRxiv-Funktion existiert, aber im Register ausgeschaltet)
- ✅ Retry-Logik (`http_json`), Query-Expansion DE↔EN, Cross-Quellen-Scoring, Filter (--jahr/--oa/--sort), JSON+Markdown-Export
- ✅ Läuft mit reiner Python-Standardbibliothek (urllib) — keine Hermes-Importe → **schon jetzt Hermes-unabhängig**

### Schwächen (aus Code-Read, 03.09.2026)

| # | Schwäche | Wo | Risiko |
|---|----------|-----|--------|
| S1 | **Stille Exceptions** `except: pass` / `except Exception: return []` ohne Log | search() Z.299, q_arxiv, q_biorxiv, q_base | Quelle tot → still 0, kein Hinweis WARUM |
| S2 | **Sequenzielle Ausführung** — 12 Quellen nacheinander | search() Schleife Z.292 | Langsam: 12×(Timeout 25s) möglich = 5 Min |
| S3 | **Keine echte Web-Suche** (nur akademisch + Wikipedia/Wikidata/Lokal) | GENERAL-Register | Firmen/Produkte/Personen finden geht nicht |
| S4 | **BASE = Anubis-Botwall** — HTTP 200, aber HTML statt JSON → still 0 | q_base | Registriert aber nutzlos (bekannt aus SUCHER-v2-Lesson) |
| S5 | **bioRxiv-Funktion existiert, ist aber aus** (API hat keine Freiwort-Suche) | Register Z.276 | Toter Code |
| S6 | **Kein eigenes venv/requirements.txt** | Repo | Update-Konflikte mit System-Python |
| S7 | **Keine Tests** | — | Kein Beweis, dass Fixes nichts brechen |
| S8 | **Scoring statisch** — keine adaptive Provider-Wahl | _score_sort | Wenn OpenAlex down ist, kein Ausweichen auf bessere Quelle |
| S9 | **Kein Health-Check** — merkt nicht, welche Quelle heute tot ist | — | Nutzer sieht leere Ergebnisse ohne Diagnose |
| S10 | **Kein venv-isoliertes Skript/Launcher** für den Desktop | — | Nutzung umständlich |

## Ziel-Architektur (3 Stufen — „funktioniert IMMER")

```
SUCHER-1000 (EIGENES venv, EIGENE Dependencies, 0 Hermes-Importe)
│
├── Stufe 1 — OHNE KEY (immer da, 0€, keine Anmeldung)
│   OpenAlex · Crossref · DOAJ · EuropePMC · Semantic Scholar · arXiv · PubMed
│   Wikipedia · Wikidata · Lokal (HAUPTLAGER)
│
├── Stufe 2 — MIT KEY, KARTE-FREI (verlässlich, optional)
│   Tavily (1000/Monat gratis, keine Karte) — Web-Suche + Extract
│   └── Key wird NUR aus Env-Var gelesen; fehlt er → Stufe 2 übersprungen, Stufe 1+3 laufen
│
├── Stufe 3 — FALLBACK (ohne Key)
│   ddgs (DuckDuckGo Python-Lib) — Web-Suche, wenn Tavily fehlt/tot
│
└── Resilienz-Schicht
    ├── Health-Check je Quelle (erreichbar? JSON? Treffer?) — tote Quellen melden + überspringen
    ├── Fehler-Sichtbarkeit (jede stille Exception → Log mit Quelle+URL+Fehler)
    ├── Parallelität (ThreadPool: 12 Quellen gleichzeitig statt nacheinander)
    ├── Timeouts hart (10s) + Retry mit Backoff
    └── Ergebnis-Persistenz in SQLite (Source of Truth) — kein JSON-Chaos
```

## Phasen-Plan (je Phase: Analyse → RED-Test → minimaler Fix → Commit → STOP)

### P0 — Read-only Baseline (Check, kein Bau)
- Reproduzierbarer Health-Test aller 12 Quellen (gleiche Query, messen: Treffer/Fehler/Latenz)
- Ergebnis: Quellen-Status-Tabelle (HEALTHY/UNSTABLE/BROKEN/DISABLED) — wie DeepWeb-Audit
- **Commit:** `docs/audits/quellen_health_2026.md`

### P1 — Fehler-Sichtbarkeit (S1, S4)
- Jede stille Exception → `_log_quellenfehler(quelle, url, exc)` (loggt + zählt, raised nie)
- BASE: aus Standard-Register nehmen (bleibt als `--quelle base` manuell erreichbar) ODER Botwall-Umgehung prüfen
- RED-Test: defekte Quelle → Meldung erscheint statt still 0
- **Commit:** Logging + BASE-Handling

### P2 — Parallelität + harte Timeouts (S2)
- `ThreadPoolExecutor(max_workers=6)` — Quellen parallel, `as_completed`, Gesamt-Timeout 30s
- Ergebnis-Reihenfolge stabil halten (Scoring danach)
- RED-Test: 2 Fake-Quellen (1 langsam 8s, 1 schnell 0.1s) → Gesamtzeit < 3s statt 8s
- **Commit:** parallele Ausführung

### P3 — Hermes-Unabhängigkeit veredeln (S6, S10)
- `requirements.txt` (ddgs, requests optional), eigenes venv im Repo (`.venv/`, gitignored)
- `launch.sh` (Menü + `read -p`), Desktop-Entry optional
- Verifikation: läuft in frischem venv ohne Hermes-Umgebung
- **Commit:** venv + Launcher

### P4 — Web-Suche-Stufe 2+3 (S3) — Herzstück „höchstes Level"
- `q_tavily()`: Key aus Env (`TAVILY_API_KEY`); fehlt → Quelle inaktiv (Meldung, kein Fehler)
- `q_ddgs()`: DuckDuckGo-Lib als Free-Fallback, immer verfügbar
- Neue Modi: `--modus web` (nur Tavily/ddgs/Wikipedia) und `--modus alle` erweitert
- RED-Test: ohne Key → tavily übersprungen, ddgs liefert; mit Key → beide
- **Commit:** Web-Suche integriert

### P5 — SQLite-Persistenz (Ergebnis-Source-of-Truth)
- `sucher.db`: Tabelle `ergebnisse` (query, ts, quelle, title, url, year, doi, is_oa, json)
- JSON-Export bleibt (Kompatibilität), DB ist das Archiv
- **Commit:** SQLite

### P6 — Tests + Quality-Gate (S7)
- pytest: Netz gemockt (4 Fälle je Quelle: ok/leer/429/kaputt), Logik-Tests (Scoring, Expansion, Filter)
- `check.sh`: py_compile + pytest + 1 Live-Smoke
- **Commit:** Test-Foundation + check.sh

## Nicht-Tun (ehrliche Grenzen)

- **Kein** „ohne Limit/ohne Block"-Versprechen — existiert nicht (Recherche-Beleg in `wissen/01_Quellen_Inventar/marktlage_2026.md`)
- **Kein** Brave als Fundament (Karte-Pflicht seit 2026 — Recherche-Beleg)
- **Kein** DeepWeb_Tool-Umbau (bleibt Discovery-„Universum")
- **Kein** Hermes-eigener web_search-Umbau (der ist Config, nicht SUCHER)

## Offene Entscheidung für David (vor P4)

Web-Suche braucht Klarheit:
- (a) Tavily-Key in Env setzen (1000/Monat, karte-frei) → beste Qualität
- (b) Nur ddgs (0€, kein Key) → reicht oft, blockt gelegentlich
- (c) Beides (ddgs primary, tavily optional) → robusteste Variante (Empfehlung)

## Erfolgskriterium (am Ende messbar)

```
1. python3 sucher.py "beliebiger begriff" 8  →  liefert IMMER etwas (Stufe 1)
2. Eine Quelle künstlich tot → andere liefern weiter + Fehler wird gemeldet
3. Läuft in frischem venv OHNE Hermes (Hermes-Update bricht nichts)
4. 30 Sekunden-Timeout hart: nie > 60s Gesamtlaufzeit
```
