# 05 — Qdrant-Sessions: Erkenntnisse & Entscheidungs-Verlauf Websuche

> Aus Davids Qdrant-Sammlungen gezogen (session-technical, session-project, knowledge_nuggets,
> 6333+6335), 03.09.2026. Zitate sind Chunk-Auszüge, keine freie Erfindung.

## Chronologie der Websuche-Entscheidungen

**17.07.2026** (knowledge_nuggets):
> „Hermes Websuche-Fix: Brave-Free API Monatslimit $5 erreicht → HTTP 402.
> Fix: search_backend von brave-free auf ddgs in config.yaml. DDGS g[ing weiter]"

**01.07.2026** (Master-Audit, ApplicationPlatform):
> „Google blockt die SearXNG-Instanz seit ~12h intensiver Nutzung. Docker-Logs zeigen
> `SearxEngineAccessDeniedException: HTTP error 403, suspended_time=180`."
> Empfehlung #1: „Brave Search API-Key holen (0€, 1000/Monat) — 🔥 Google-Qualität"

**07/2026** (Session technical):
> „Kein Google-CSE-Support in Hermes. Die verfügbaren Search-Backends sind:
> ddgs, brave-free, searxng, tavily, firecrawl..."

**08/2026** (DeepWeb-Audits):
> SearXNG public instances alle tot (searx.be → HTML statt JSON, sapti.me → 429,
> bus-hit.me → DNS-Fail). Lokale Docker-Instanz als ERSTE in der Liste. Ergebnis:
> 64 → 119 unique Treffer nach SearXNG+DDG-Fix.

## Kern-Erkenntnisse aus Sessions

1. **DDGS ist der stabile Free-Fallback** — lief durch mehrere Fix-Zyklen als Retter,
   wenn Brave-Limit oder SearXNG-Tod kam. Python-Lib `ddgs` stabiler als ddgs-CLI.

2. **Brave = die „Google-Qualität"-Lösung** — wurde im Juli-Audit als Empfehlung #1
   notiert, der Key wurde geholt, lief bis zum Monatslimit. Am 03.09.2026 wieder aktiviert.

3. **Die „38 Searcher"-Session** (DEEP AUDIT) dokumentiert die Methode: NICHT neu bauen,
   NICHT blind Tools installieren — erst prüfen, messen, vergleichen, reparieren.
   Regeln: keine Cronjobs, keine Massensuchen, keine Proxys ohne Report, nichts löschen.

4. **Werkzeug-Hierarchie (aus qdrant-wissenssuche-Skill, 09/2026):**
   Bei Web-Recherche zuerst SUCHER-1000 (liefert konsistent 30–47 Treffer), dann ddgs,
   dann Bing-HTML, dann web_search. — **Seit dem brave-free-Fix (03.09.2026) ist die
   Reihenfolge überholt:** web_search (brave-free) funktioniert jetzt zuverlässig.

## Wie diese Erkenntnisse hierher kamen

Die Inhalte dieses Ordners sind konsolidiert aus:
- Qdrant Scroll-Abfragen (Ports 6333/6335, Sammlungen session-technical/project, knowledge_nuggets)
- Reports auf der Platte (ApplicationPlatform/reports/)
- Hermes-Skills (research-engine-development, qdrant-wissenssuche, web-extraction-fallback, blocked-page-recovery)
- Live-Messungen am 03.09.2026 (SearXNG-Status, ddgs-Test, brave-free-Test)
