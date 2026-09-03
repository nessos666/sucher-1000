# 03 — Architektur: Wie die Websuche-Tools aufgebaut sind

> Die drei Ansätze im Vergleich — damit man weiß, welches Muster man wofür nimmt.

## A. SUCHER-1000 (dieses Repo) — Einfacher Multi-API-Aufruf

```
sucher.py "begriff" 8 --modus studien
  → je Quelle eine Funktion q_<quelle>()  (12 Stück, siehe 01_Quellen_Inventar)
  → Ergebnisse gesammelt, dedupliziert, Cross-Quellen-Scoring
  → ergebnis_*.json + Markdown-Report in ergebnisse/
```

- **Stärke:** simpel, robust, kein Docker, keine Keys nötig (nur legale OA-APIs)
- **Schwäche:** akademischer Bias — für Firmen-/Personensuche ungeeignet (Nature/PMC-Rauschen)

## B. DeepWeb_Tool — Discovery-Engine mit Multi-Hop

```
query → search_all() (13+ Provider parallel, ThreadPool)
  → link_extractor (Links aus Ergebnissen ziehen)
  → discovery_engine (Hop 0→1→2, ~107 Domains/Query)
  → domain_memory (schlechte Domains ausschließen)
  → query_tree (tote Zweige prunen)
  → SQLite data/deepweb.db
```

- **Stärke:** findet Domains, die Such-APIs nie zeigen (81% der v5.0-Domains kamen aus Links)
- **Schwäche:** Komplexität (50+ Module), Wartung. SearXNG-Adapter BROKEN (403), DDG captcha

## C. ApplicationPlatform — Fallback-Kette (Legacy)

```
search_router.py:
  Tavily (Key) → SearXNG/startpage → SearXNG/bing → ddgs → Fallback
  (stats: tavily/startpage/bing/ddgs/fallback Zähler)
```

- **Stärke:** klare Kaskade — fällt eine aus, nächste
- **Schwäche:** Reihenfolge fix; wenn vordere tot, zählt nur Statistik

## D. Hermes-eigene Registry (7 Provider) — die VERDRAHTETE Lösung

```
web_search → web_search_registry._resolve()
  1. explizite Config gewinnt (auch wenn unavailable — Fehler wird präzise!)
  2. sonst: einziger verfügbarer Provider
  3. sonst: Legacy-Priorität firecrawl→parallel→tavily→exa→searxng→brave-free→ddgs
```

**Das war der Bug (03.09.2026):** `search_backend: searxng` explizit gesetzt → SearXNG
gewinnt IMMER, obwohl tot. „Explicit config wins, ignoring availability" ist Feature und
Falle zugleich. Fix: Config auf brave-free gestellt (Key vorhanden).

## Wann welches Muster?

| Aufgabe | Tool |
|---------|------|
| Studien/Paper/Dossiers | **SUCHER-1000** (`--modus studien`) |
| Personen/Konzepte/Orte/allgemein | **SUCHER-1000** (`--modus universal`) |
| „Universum durchsuchen", Discovery, neue Domains | **DeepWeb_Tool** |
| Firmen + Telefone (JobHunter) | ApplicationPlatform-Scraper (DasÖrtliche/GelbeSeiten) |
| Hermes' eingebaute Suche im Chat | `web_search` (brave-free) / `web_extract` (tavily) |
