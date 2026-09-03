# Search Infrastructure Master Audit — 01.07.2026

## Phase 1-2: Inventar + Health Check

| Searcher | Typ | Status | Ergebnisse | CAPTCHA? |
|----------|-----|:------:|:----------:|:--------:|
| **Bing** (via SearXNG) | Meta | 🟢 | 10/Query | Nein |
| **Startpage** (via SearXNG) | Meta | 🟢 | 10/Query | Nein |
| **Google** (via SearXNG) | Meta | 🔴 | 0 | **JA — 403, 180s suspend** |
| **DuckDuckGo** (via SearXNG) | Meta | 🔴 | 0 | **JA — CAPTCHA wt-wt** |
| **DDGS** (Python lib) | Direkt | 🔴 | 0 | Rate-Limit |
| **Brave Search** | API | ⚠️ | — | Kein API-Key |
| **Crawl4AI** | Crawler | 🟢 | ✓ | Nein |
| **Scrapy** | Crawler | 🟢 | ✓ | Nein |

## Phase 3: Google-Problem

**Ursache klar:** Google blockt die SearXNG-Instanz seit ~12h intensiver Nutzung (15+ Suchen/Stunde). Docker-Logs zeigen `SearxEngineAccessDeniedException: HTTP error 403, suspended_time=180`.

**DDGS ebenfalls blockiert** — CAPTCHA `wt-wt` seit mehreren Stunden.

**Bing + Startpage funktionieren**, aber liefern minderwertige Ergebnisse (Definitionen, Wörterbücher, Apple, mobile.de — kaum echte Firmen).

## Phase 4-5: Qualitätsvergleich

| Engine | Echte Firmen | Jobportale | Junk | Qualität |
|--------|:-----------:|:----------:|:----:|:--------:|
| Google (wenn aktiv) | 🟢 Hoch | Mittel | Niedrig | ⭐⭐⭐⭐⭐ |
| Bing | 🔴 Niedrig | Hoch | Sehr hoch | ⭐⭐ |
| Startpage | 🟡 Mittel | Mittel | Mittel | ⭐⭐⭐ |
| DuckDuckGo | 🟡 Mittel | Mittel | Niedrig | ⭐⭐⭐ |
| Brave (API) | 🟢 Hoch | Niedrig | Niedrig | ⭐⭐⭐⭐ |

## Phase 6: Ursachen

1. **Google blockiert** — IP-basierter 403 nach intensiver Nutzung
2. **DDGS blockiert** — CAPTCHA nach Rate-Limit-Überschreitung
3. **Kein Brave-Key** — 0€/Monat aber nie registriert
4. **Bing/Startpage** — funktionieren aber schlechte Qualität

## Phase 7-9: Empfehlung

| # | Maßnahme | Impact |
|---|----------|--------|
| 1 | **Brave Search API-Key holen** (0€, 1000/Monat) | 🔥 Google-Qualität |
| 2 | Google-Sperre abwarten (180s × N → Stunden) | 🟡 Temporär |
| 3 | GelbeSeiten/DasÖrtliche scraper reaktivieren | 🟢 Telefone! |
| 4 | Bing nur als Not-Fallback | 🟡 |

## Ampel

| Searcher | Status | Qualität | Empfehlung |
|----------|:------:|:--------:|------------|
| **Brave** | ⚠️ Kein Key | ⭐⭐⭐⭐ | **Sofort holen** |
| **Google** | 🔴 Blockiert | ⭐⭐⭐⭐⭐ | Warten |
| **Bing** | 🟢 Aktiv | ⭐⭐ | Fallback |
| **Startpage** | 🟢 Aktiv | ⭐⭐⭐ | Nutzbar |
| **DDGS** | 🔴 Blockiert | ⭐⭐⭐ | Warten |
| **Crawl4AI** | 🟢 Aktiv | ⭐⭐⭐⭐ | Impressum |
