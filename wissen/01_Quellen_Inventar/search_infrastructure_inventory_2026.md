# Search Infrastructure Inventory — 01.07.2026

## Alle 12 Searcher

| # | Searcher | Typ | Datei/Pfad | Status |
|---|----------|-----|------------|:------:|
| 1 | **SearXNG** | Meta | Docker :8080 | 🟡 Google+DDGS blockiert |
| 2 | **DDGS** | Python Lib | `duckduckgo_search` | 🔴 CAPTCHA |
| 3 | **Brave Search** | Python | `app/brave_search.py` | ⚠️ Kein Key |
| 4 | **Bing** | via SearXNG | — | 🟢 Funktioniert |
| 5 | **Startpage** | via SearXNG | — | 🟢 Funktioniert |
| 6 | **Google** | via SearXNG | — | 🔴 403 blockiert |
| 7 | **Crawl4AI** | Crawler | pip, v0.9.0 | 🟢 Funktioniert |
| 8 | **Scrapy** | Crawler | pip, v2.16 | 🟢 Funktioniert |
| 9 | **Search Router** | Python | `app/search_router.py` | 🟡 Braucht Update |
| 10 | **Query Tracker** | Python | `app/query_tracker.py` | 🟢 Funktioniert |
| 11 | **HtmlRAG** | Parser | `app/htmlrag.py` | 🟢 Funktioniert |
| 12 | **Impressum Scraper** | Scraper | `app/impressum_scraper.py` | 🟢 Funktioniert |

## SearXNG Docker Status
- Container: `searxng` läuft seit 12h
- Google: `SearxEngineAccessDeniedException: HTTP error 403`
- DuckDuckGo: `SearxEngineCaptchaException: CAPTCHA wt-wt`
- Bing: 10 Ergebnisse/Query
- Startpage: 10 Ergebnisse/Query

## Empfehlung
1. Startpage als Standard (funktioniert, mittlere Qualität)
2. Google-Sperre abwarten (temporär)
3. Tavily API evaluieren (0€ Basic Tier)
