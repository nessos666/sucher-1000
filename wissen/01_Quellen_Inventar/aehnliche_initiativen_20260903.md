# Ähnliche Initiativen zu SUCHER-1000 — Recherche (03.09.2026)

**Was SUCHER-1000 ist:** Multi-Engine-Websucher (Web-Bündel + 10 akademische
Quellen), Hermes-unabhängig, Health-Selbstheilung, SQLite-Archiv, Quality-Gate.
Suche nach "ähnlichen Initiativen" in 3 Quellen: Hermes-Skill-DB, GitHub, Reddit.

---

## Job 1: Hermes-Skill-DB (lokal, ~163 Skills)

Kein Fremd-Projekt — aber 2 Skills dokumentieren DIE Eigen-Initiativen, die
SUCHER-1000 am nächsten stehen (alle von David selbst gebaut):

| Skill | Beziehung zu SUCHER-1000 |
|---|---|
| **research-engine-development** | DER Skill, der SUCHER-1000 + DeepWeb_Tool + alle Härtungs-Muster dokumentiert (P0-P8, 49 Pitfalls, Reviews). „Eigene Suchmaschine, multi-source, kein Cloud" |
| **deep-web-search-tool** | DeepWeb_Tool-Architektur (Discovery-Crawler, 15 Engines, SearXNG-Adapter) — Davids „Universum-Sucher" |

Verwandte Such-/Recherche-Skills (gleiche Domäne, anderer Fokus):
research-orchestration (Multi-Query), qdrant-wissenssuche/-scout (Wissens-DB),
web-extraction-fallback + blocked-page-recovery (Transport-Fallback),
deep-web-research (unsichtbares Web), evidence-based-search-claims.

**Fazit Job 1:** In der Skill-DB ist SUCHER-1000 selbst die Referenz-Initiative.
Keine fremde „ähnliche Initiative" dort — die Skills BESCHREIBEN Davids eigene.

---

## Job 2: GitHub — ähnliche Open-Source-Initiativen

### ★★★ SHIRABERU (jim-ww) — der nächste Verwandte
**„Multi-engine search aggregator for the terminal — no API keys, no server.
CLI + Go library."** Go, SearXNG/duckduckgo-Backends, Privacy.
→ Praktisch SUCHER-1000s Konzept in Go. Kein Health/Cooldown, kein SQLite-Archiv
dokumentiert. Beweis, dass das Konzept „Terminal-Such-Aggregator ohne API-Keys"
auch andere bauen — aber keiner so gehärtet (2 Reviewer, 94 Tests).

### ★★★ SearXNG (searxng/searxng) — der Gigant
Metasuchmaschine, aggregiert 70-250+ Engines, selbst-hostbar, AGPL, kein
Tracking. **Der etablierte Standard**, an dem sich alle messen. Unterschied zu
SUCHER-1000: SearXNG ist ein Web-Server (Docker), SUCHER-1000 ist eine CLI ohne
Server. SearXNG-Upstreams werden oft geblockt (Davids ursprüngliches Problem).

### ★★ Weitere echte Verwandte:
| Projekt | Was | Sprache |
|---|---|---|
| **NikolaiT/GoogleScraper** | Scraped mehrere Engines (Google/Yandex/Bing/DDG), async | Python |
| **OneSearch MCP** (yokingma) | Web-Suche+Scrape über SearXNG/Tavily/DDG/Bing/Exa — MCP | TypeScript |
| **TrailSearch** (self-hosted) | Such-Routing + SQLite-FTS + SearXNG + Brave | — |
| **Perplexica** (ItzCrazyKns) | Perplexity-Style-UI, SearXNG-Anbindung, mehrere Modi | TypeScript |
| **searchxng-lib** (npm) | Aggregiert Bing+DDG, Dedup/Ranking/Caching, kein Key | JS |
| **mwmbl** | Open-Source Suchmaschine mit eigenem Crawler (non-profit) | Python |

### GitHub-Topic-Landkarte:
`ai-search-engine` · `multiple-search-engine` · `searx` · `searxng` ·
`duckduckgo-search` — die Topics, unter denen solche Projekte laufen.

---

## Job 3: Reddit — Diskussionen & Community-Konsens

### r/selfhosted (Such-Threads):
- „Open Source Search Engines" → SearXNG, YaCy, Whoogle genannt
- „Self-hosted private search engine" → SearXNG = privater Aggregator-Standard
- „What search engine do yall selfhost?" → SearXNG + Omnisearch + Alternativen
- Kern-Konsens: **SearXNG ist die Standard-Antwort**; Whoogle = Google-Proxy,
  wird oft geblockt; YaCy = P2P-Crawler (schwergewichtig)

### r/LocalLLM + r/LocalLLaMA (Agent-Suche, 2026 — DAS relevante Feld):
- **„Comparing web search for AI agents: self-hosted SearXNG vs managed Tavily
  vs custom implementations"** (Feb 2026) → exakt Davids Entscheidung!
- **„SearXNG gets blocked under sustained use + inconsistent JSON — better
  options exist: MCP-connected..."** (Mai 2026) → **bestätigt Davids
  Kern-Problem** (SearXNG-Upstream-Blocks) — die Community sucht Alternativen
- **„DIY Perplexity: SearXNG + Local LLM"** → Perplexica als UI-Standard
- **„I ended up just building my own with SearXNG + web fetch tool"** →
  mehrere bauen genau wie David eigene Lösungen, weil Fertig-Tools blocken

### Was Reddit 2026 über Davids Problem sagt:
1. SearXNG = Standard, ABER: „gets blocked under sustained use, inconsistent
   JSON" — die Community validiert Davids ursprüngliche Erfahrung
2. Der Trend geht zu **Multi-Provider-Fallback** (Tavily/Serper/Brave als
   Ergänzung) + **MCP-Server** als Integrations-Schicht
3. „Besser eigene Lösung bauen" ist ein anerkannter Weg — David ist mit
   SUCHER-1000 dort, wo die Community hinstrebt (Multi-Engine, kein
   Single-Point-of-Failure)

---

## Gesamt-Einordnung (ehrlich)

**SUCHER-1000 ist KEINE exotische Idee** — Terminal-Such-Aggregatoren ohne
API-Key existieren (shiraberu), SearXNG ist der etablierte Riese, und die
LLM-Community baut 2026 aktiv eigene Such-Lösungen, weil Fertig-Tools blocken.

**Was SUCHER-1000 von den ähnlichen Initiativen unterscheidet:**
1. **Hybrid**: Web-Bündel + akademische Quellen in EINEM Tool (die anderen sind
   entweder/oder)
2. **Härtung**: Health-Selbstheilung mit Cooldown, NO_KEY-Handling,
   Captcha-Erkennung, hartes Budget — bei keinem Vergleichs-Projekt dokumentiert
3. **Qualitäts-Gate**: 94 Tests + mypy + ruff + bandit + 2 unabhängige
   AI-Reviews — untypisch für persönliche Such-Tools
4. **Hermes-unabhängig**: eigenes venv, kein Server, keine Cloud

**Was David von den anderen lernen kann:**
- SearXNG als ZUSÄTZLICHE Quelle ins Web-Bündel (es läuft bei David schon als
  Docker) — wenn dessen Upstreams frei sind
- MCP-Server-Schicht als nächster Integrations-Schritt (LLM-Tools nutzen dann
  SUCHER-1000)
- Perplexica/Omnisearch zeigen UI-Möglichkeiten (falls David je eine
  Web-Oberfläche will)
