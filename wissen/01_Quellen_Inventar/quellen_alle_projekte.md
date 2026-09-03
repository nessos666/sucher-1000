# 01 — Quellen-Inventar: Alle Websuche-Quellen auf Davids Rechner

> Stand: 03.09.2026. Zusammengeführt aus: sucher_universal.py (12 Funktionen),
> DeepWeb_Tool provider_contract (13+ Provider), ApplicationPlatform Audit (38 Searcher → 12 dokumentiert).

## A. SUCHER-1000 — 12 Quellen (`src/sucher_universal.py`)

Zweck: Studien/Paper/Dossiers. Modus `studien` = 5 akademische Quellen; `universal` = + Wikipedia.

| # | Funktion | Quelle | Typ |
|---|----------|--------|-----|
| 1 | `q_openalex` | OpenAlex | Akademisch (323M Werke, REST, kein Key) |
| 2 | `q_crossref` | Crossref | Akademisch (DOI-Registry) |
| 3 | `q_doaj` | DOAJ | Open-Access-Journals |
| 4 | `q_europepmc` | Europe PMC | Biomedizin (REST, kein Key) |
| 5 | `q_semanticscholar` | Semantic Scholar | Akademisch (REST) |
| 6 | `q_wikipedia` | Wikipedia (DE+EN opensearch) | Allgemeinwissen |
| 7 | `q_arxiv` | arXiv | Preprints |
| 8 | `q_biorxiv` | bioRxiv | Biologie-Preprints |
| 9 | `q_pubmed` | PubMed (NCBI eutils) | Medizin |
| 10 | `q_base` | BASE (base-search.net) | **⚠️ Anubis-Botwall — liefert 0 trotz HTTP 200** |
| 11 | `q_wikidata` | Wikidata | Entitäten (SPARQL/MediaWiki) |
| 12 | `q_lokal` | Lokale Dateisuche | Eigenes Dateisystem |

## B. DeepWeb_Tool — 13+ Provider (`src/deepweb.py` + provider_contract.py)

Zweck: Discovery („Universum durchsuchen"), Multi-Hop, 107 Domains/Query.

**HEALTHY (5):** wiby, marginalia, yandex_legacy=mojeek, doaj, internet_archive
**UNSTABLE (5):** baidu, openalex, wikidata, gutenberg, openlibrary
**BROKEN (3):** searxng 403, ddg_html captcha, commoncrawl API
**DISABLED (3):** duckduckgo, baidu, curlie_legacy

Dazu: Common Crawl, Curlie, OpenAlex, SearXNG (Docker :8080), CDX-API (Wayback).

## C. ApplicationPlatform — 9+ Engines (Legacy, JobHunter-Ära)

| Searcher | Typ | Status (Audit 01.07.2026) |
|----------|-----|:------:|
| SearXNG (Meta) | Docker :8080 | 🟡 Google+DDGS blockiert |
| DDGS | Python-Lib | 🔴 CAPTCHA |
| Brave Search API | REST | ⚠️ Kein Key → **inzwischen gesetzt!** |
| Bing (via SearXNG) | Meta | 🟢 (schlechte Qualität) |
| Startpage (via SearXNG) | Meta | 🟢 (mittlere Qualität) |
| Google (via SearXNG) | Meta | 🔴 403 blockiert |
| Crawl4AI | Crawler | 🟢 |
| Scrapy | Crawler | 🟢 |
| Search Router | Eigenbau | 🟡 |
| HtmlRAG | Parser | 🟢 |
| Impressum Scraper | Scraper | 🟢 |

## D. Hermes-eigene Web-Provider (Registry, 7 Stück)

firecrawl → parallel → tavily → exa → searxng → brave-free → ddgs (Legacy-Priorität).
**Aktiv seit 03.09.2026:** search=brave-free, extract=tavily. DDGS als Fallback.

## Qualitäts-Ampel (aus Master-Audit 01.07.2026)

| Engine | Echte Firmen | Junk | Qualität |
|--------|:-----------:|:----:|:--------:|
| Google | Hoch | Niedrig | ⭐⭐⭐⭐⭐ |
| Brave (API) | Hoch | Niedrig | ⭐⭐⭐⭐ |
| Startpage | Mittel | Mittel | ⭐⭐⭐ |
| DuckDuckGo | Mittel | Niedrig | ⭐⭐⭐ |
| Bing | Niedrig | Sehr hoch | ⭐⭐ |
