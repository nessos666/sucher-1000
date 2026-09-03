# 38-Searcher-Session — Assistant-Antworten (Ergebnisse)

> Extrahiert 03.09.2026 aus Qdrant 6335/session-technical. 5 Antwort-Chunks.


---
## Antwort 1

[assistant]: ---

## Zusammenfassung der Recherche

**Durchgeführte Schritte:**
- Beide arXiv-Papers vollständig gelesen (ContextSniper 2607.01916, CodeCompass 2602.20048)
- Codebase-Memory-Paper (2603.27277) gelesen + GitHub-README analysiert
- Droste-GitHub-README vollständig analysiert (v1.1.6)
- Ant CGM (CodeFuse-CGM), Serena, codegraph via Web-Extracts und Websuche recherchiert
- Serena-Tool-Liste via offizielle Doku abgeglichen

**Kernergebnisse:**
- **Causale Kanten (caller/callee):** Droste ✅, Codebase-Memory ✅, Ant CGM ✅, codegraph ✅, Serena ⚠️ (indirekt via LSP), CodeCompass ❌, ContextSniper ❌
- **Cross-Language-Bridges:** Exklusiv Droste — kein anderes Tool verbindet Python↔SQL↔Dart/TS
- **Token-Effizienz:** Droste (1.200 chars Budget) vs Codebase-Memory (~1.000 Tokens) vs ContextSniper (38-52% Reduktion) — unterschiedliche Ansätze, schwer direkt vergleichbar
- **CodeCompass Navigation Paradox:** Akademisch validiert (p<0.001), aber 58% Tool-Ignore-Rate — das beste Graph-Tool nützt nichts, wenn der Agent es nicht aufruft
- Die CT+Droste-Fusion (`droste_client.py` → Prompt-Injection) ist architektonisch gut positioniert; Dual-MCP mit Codebase-Memory als Ergänzung wäre strategisch sinnvoll

---
## Antwort 2

[assistant]: ---

**VOLLSTÄNDIGE RECHERCHE — Neue Plugins, Tools, MCP-Server für Hermes Agent**

---

## 1. DEIN IST-ZUSTAND

| Bereich | Installiert |
|---------|------------|
| Plugins | 17 (browser, kanban, memory, spotify, observability, etc.) |
| Skills | 25 Kategorien (~60+ Skills) |
| MCP-Server | **0 — komplett ungenutzt** |
| Deaktivierte Toolsets | 7 (video, x_search, homeassistant, spotify, yuanbao, moa, video_gen) |

---

## 2. MCP-SERVER — Das größte ungenutzte Potenzial

MCP (Model Context Protocol) ist der Standardweg, externe Tools in Hermes einzubinden. Du hast **keinen einzigen** MCP-Server konfiguriert. Das ist, als hättest du einen App-Store ohne installierte Apps.

**Top-Empfehlungen (alle kostenlos, per npx/stdio):**

| MCP-Server | Was er kann | Befehl |
|-----------|-------------|--------|
| **GitHub** | Issues, PRs, Repos, Commits, Gists verwalten | `npx -y @modelcontextprotocol/server-github` |
| **PostgreSQL** | Direkte DB-Abfragen, Schema-Inspektion | `npx -y @modelcontextprotocol/server-postgres` |
| **Filesystem** | Sicheres Dateisystem (besser als terminal-tools) | `npx -y @modelcontextprotocol/server-filesystem` |
| **Brave Search** | Web-Suche mit API (präziser als DuckDuckGo) | `npx -y @modelcontextprotocol/server-brave-search` |
| **Puppeteer** | Headless-Browser für JS-lastige Seiten | `npx -y @modelcontextprotocol/server-puppeteer` |
| **Sequential Thinking** | Chain-of-Thought für komplexe Probleme | `npx -y @modelcontextprotocol/server-sequential-thinking` |
| **Memory** | Wissensgraph-basiertes Gedächtnis | `npx -y @modelcontextprotocol/server-memory` |
| **SQLite** | SQLite-DB direkt ansteuern | `npx -y @modelcontextprotocol/server-sqlite` |
| **Google Maps** | Geocoding, Routen, POIs | `npx -y @modelcontextprotocol/server-google-maps` |

**Community-Highlights (top gerated auf GitHub):**

| Server | ⭐ | Funktion |
|--------|---|----------|
| `browserbase/mcp-server-browserbase` | Cloud-Browser | Stagehand + Playwright in der Cloud |
| `pierrebrunelle/mcp-server-openai` | OpenAI-API-Proxy | DALL-E, TTS, GPT via MCP |
| `exa-labs/exa-mcp-server` | Exa Search | Neuronale Websuche (besser als Google) |
| `qdrant/mcp-server-qdrant` | Vektor-DB | Semantische Suche + RAG |
| ` stripe/mcp-server-stripe` | Stripe-API | Payments, Kunden, Abos |
| `airtable/mcp-server-airtable` | Airtable | Tabellen/CRM via MCP |

**Installation (Beispiel GitHub):**
```bash
hermes mcp add github --command npx --args "-y" "@modelcontextprotocol/server-github"
# Dann in ~/.hermes/.env:
# GITHUB_PERSONAL_ACCESS_TOKEN=ghp_...
hermes mcp test github
# → Tools erscheinen automatisch nach /reset
```

---

## 3. NEUE PLUGINS (Community + Offizielle)

Neben deinen 17 installierten Plugins gibt es:

| Plugin | Status | Funktion |
|--------|--------|----------|
| **honcho** | Offiziell (Memory) | User-übergreifendes Langzeitgedächtnis |
| **mem0** | Offiziell (Memory) | KI-gestützte Memory-Layer |
| **supermemory** | Offiziell (Memory) | Memory-Endpunkt für externe Apps |
| **strike-freedom-cockpit** | Community | Live-Überwachung aller Agent-Aktionen |
| **rl** | Offiziell (Tools) | Reinforcement Learning Feedback-Loop |
| **disk-cleanup** | ✅ Hast du | Automatische Speicherbereinigung |

**Memory-Plugins** sind besonders relevant für dein Multi-Session-Setup — honcho/mem0 können kontext über Tage/Wochen halten ohne dass der Context explodiert.

---

## 4. AKTIVIERBARE TOOLSETS (ausgeschaltet, aber sofort nutzbar)

```bash
hermes tools enable video           # Videoanalyse (Screenshots, Szenen)
hermes tools enable x_search        # Twitter/X Suche
hermes tools enable homeassistant   # Smart Home Steuerung
hermes tools enable spotify         # Musiksteuerung
hermes tools enable moa             # Mixture of Agents (parallel LLM calls)
hermes tools enable video_gen       # KI-Videogenerierung
hermes tools enable debugging       # Extra Debug-Tools
```

---

## 5. OPTIONALE SKILLS (im Repo, nicht aktiviert)

Hermes hat einen `optional-skills/` Ordner mit Skills die nicht automatisch installiert werden. Mit `hermes skills browse` durchsuchbar. Beispiele:
- `claude-code` / `codex` / `opencode` — externe Coding-Agents spawnen
- `segment-anything-model` — Bildsegmentierung
- `audiocraft-audio-generation` — Musik/Sound per KI
- `serving-llms-vllm` — vLLM Model Serving

---

## 6. EMPFEHLUNGEN (priorisiert)

**SOFORT (5 Minuten):**
1. GitHub MCP-Server installieren — deine gh-tools werden dadurch nicht obsolet, aber MCP gibt strukturierten Zugriff
2. Brave Search MCP — bessere Websuche als current tools

**HEUTE (30 Minuten):**
3. Filesystem MCP — sicherer als rohe terminal-Befehle
4. Sequential Thinking MCP — besseres Reasoning bei komplexen Debugging-Aufgaben
5. Memory-Plugin wechseln zu mem0 oder honcho — besseres Langzeitgedächtnis

**DIESE WOCHE:**
6. PostgreSQL MCP — direkt auf deine Trading-DBs
7. Puppeteer MCP — für JS-lastige Web-Recherche
8. `video` + `x_search` toolsets aktivieren

---

Welche davon so

---
## Antwort 3

[assistant]: ## 1. Analyse — Was existiert bereits

**State of the platform after today's 8-hour sprint:**

| Komponente | Datei | Status | Bewertung |
|-----------|-------|:------:|-----------|
| Company Discovery | `search_router.py` | ✅ | Gut. Tavily+Bing+Startpage Fallback |
| Company DB | `application_platform.db` | ✅ | 400+ Firmen, 101 mit Email |
| Impressum Scraper | `draft_pipeline.py` (inline) | ⚠️ | Funktioniert, aber kein separates Modul |
| Asset Selector | `asset_selector.py` | ✅ | Gut. Rule-based matching |
| Quality Gates | `quality_gate.py` | ✅ | 4 Checks, funktionieren |
| Draft Pipeline | `draft_pipeline.py` | ⚠️ | Monolith. 350+ Zeilen, alles in einer Datei |
| DecisionMakerDiscovery | `dm_discovery.py` | 🟡 | V3 Beta, funktioniert |
| Contact Research | `contact_research.py` | 🟡 | V3 Beta, bugs behoben |
| Personalization | `personalization.py` | 🟡 | V3 Beta, basic |
| Hungarian Scouts | `scout_hungary.py` | ✅ | Funktioniert |
| IT Job Search | `it_job_search.py` | 🟡 | Existiert, ungenutzt |

**Das größte Problem: Keine Architektur.** Alles in einer flachen `app/`-Directory, Module importieren sich gegenseitig, keine Interfaces, keine Dependency Injection.

## 2. Fehlende Module

| # | Modul | Schwere |
|---|-------|:------:|
| 1 | **Config System** — Keine zentrale Konfiguration. API-Keys, Pfade, Templates hart codiert | 🔴 |
| 2 | **Logger** — `print()` statt structured logging | 🔴 |
| 3 | **Data Layer** — Kein Repository Pattern. SQL direkt in jeder Datei | 🔴 |
| 4 | **Pipeline Orchestrator** — Kein zentraler Workflow. Manuelles Ausführen einzelner Skripte | 🔴 |
| 5 | **Testing** — 0 Tests für ApplicationPlatform | 🔴 |
| 6 | **Error Handling** — Kein retry, kein circuit breaker | 🟡 |
| 7 | **CLI** — Kein einheitliches CLI. Verschiedene `python script.py command`-Patterns | 🟡 |
| 8 | **Monitoring/Health** — Keine Pipeline-Health-Checks | 🟢 |

## 3. Priorität

**HIGH (diese Woche)**
1. Config System — Basis für alles andere
2. Data Layer (Repository Pattern) — Entkoppelt SQL von Business-Logik
3. Pipeline Orchestrator — Macht aus Skripten eine Plattform

**MEDIUM (nächste Woche)**
4. Structured Logging
5. Unified CLI
6. Error Handling & Retry

**LOW (später)**
7. Tests
8. Monitoring

## 4. Architektur-Design

```
ApplicationPlatform/
├── config/
│   ├── settings.yaml          # API keys, paths, limits
│   └── settings.py            # Pydantic Settings loader
│
├── core/
│   ├── models.py              # Pydantic models: Company, Contact, Draft, Asset
│   ├── interfaces.py          # ABCs: ISearcher, IScraper, IEnricher, ISelector
│   ├── errors.py              # Domain exceptions
│   └── logging.py             # Structured logger
│
├── data/
│   ├── repository.py          # CompanyRepo, ContactRepo, DraftRepo
│   ├── database.py            # Connection manager, migrations
│   └── unit_of_work.py        # Transaction boundary
│
├── services/
│   ├── discovery/
│   │   ├── searcher.py        # ISearcher: Tavily + Bing + Startpage
│   │   └── scraper.py         # IScraper: Impressum, HtmlRAG
│   ├── enrichment/
│   │   └── enricher.py        # IEnricher: Email, Phone, Contact
│   ├── matching/
│   │   ├── asset_selector.py  # ISelector: CV, Template matching
│   │   └── quality_gate.py    # IQualityGate: Pre-export checks
│   ├── outreach/
│   │   ├── dm_discovery.py    # Decision maker finder
│   │   ├── contact_research.py
│   │   └── personalization.py
│   └── pipeline/
│       ├── orchestrator.py    # Main workflow: Discover→Enrich→Match→Draft
│       └── draft_builder.py   # IMAP draft creation
│
├── cli/
│   └── main.py                # Typer CLI: `jh search`, `jh draft`, `jh export`
│
├── tests/
│   ├── test_discovery.py
│   ├── test_matching.py
│   └── test_pipeline.py
│
└── data/
    └── application_platform.db
```

## 5. Implementierungsplan

**Schritt 1: Config System (30 Min)**
```python
# config/settings.yaml
tavily:
  api_key: "tvly-dev-..."
  max_requests_per_hour: 50
webde:
  email: "kontakt@sucher1000.example"
  imap_server: "imap.web.de"
paths:
  cv_dir: "~/Schreibtisch/Bewerbungen_Sammlung/BESTE_MAPPE/email_ready"
  templates_dir: "~/Schreibtisch/Bewerbungen_Sammlung/Anschreiben"
```

**Schritt 2: Data Layer (1h)**
- `CompanyRepo.find_by_email(email)` statt `c.execute("SELECT ... WHERE email=?")`
- `ContactRepo.save(contact)` statt direktem SQL
- `UnitOfWork` für Transaktionen

**Schritt 3: Pipeline Orchestrator (1h)**
- `Pipeline.run(steps=["discover","enrich","match","draft","export"])`
- Jeder Step ist idempotent
- Resume bei Abbruch

**Schritt 4: Alten Code migrieren (1h)**
- `draft_pipeline.py` → `services/pipeline/draft_builder.py`
- `asset_selector.py` → `services/matching/`
- `dm_discovery.py` → `services/outreach/`

## 6. Risiken

| Risiko | Impact | Mitigation |
|--------|:------:|------------|
| Migration bricht bestehende Pipeline | 🔴 Hoch | Alten Code parallel laufen lassen |
| Over-Engineering | 🟡 Mittel | Nur Abstrahieren was WIRKLICH variiert |
| web.de Credentials i

---
## Antwort 4

[assistant]: Phase 0 zeigt wichtige Überraschungen. Kurz dokumentieren, dann korrigiert in Phase 1:
[assistant]: Phase 0 abgeschlossen. Wichtige Erkenntnis: **Es existieren bereits bessere Tabellen als geplant.** `tme_channels` (46) + `tme_jobs` (mit Scam-Detection!) statt neuer Tabellen. Plan wird korrigiert. Jetzt Phase 1:
[assistant]: ✅ **Phase 1 fertig.** `channel_registry`: 54 Einträge, 0 Datenverlust. Phase 2 — Telegram Discovery Engine:
[assistant]: Falsche Datei. Korrigiere:
[assistant]: Jetzt Job-Extraktor und Discovery-Modul:
[assistant]: Jetzt das Discovery-Hauptmodul:
[assistant]: Phase 2 Code steht. Jetzt testen:
[assistant]: Telemetr-API-Endpunkt falsch. Fixen — zuerst checken, wie die echte API aussieht:
[assistant]: Telemetr braucht API-Key (nicht frei). Pragmatisch: DDGS-Fallback einbauen — der existierende Scanner funktioniert ja bereits mit 46 Channels.
[assistant]: DDGS-basiert. Jetzt live testen:
[assistant]: Telegram-Discovery funktioniert (DDGS-basiert, integriert in DB). Channel-Neufunde sind rar über Websuche — der @germantechjobs-Cronjob ist der bessere Kanal. Jetzt **Phase 3: HackerNews Scanner**:
[assistant]: Test:
[assistant]: 🔥 **42 HN-Jobs gefunden!** Phase 3 funktioniert. Jetzt Phase 4 (Reddit) + Phase 5 (Integration):
[assistant]: Phase 5 — Integration + Audit:
[assistant]: Finaler Integrationstest:
[assistant]: UNIQUE-Constraint auf post_url. Fix:
[assistant]: Nochmal:

---
## Antwort 5

[assistant]: Gute Architektur-Idee, aber ehrliche Bewertung:

---

## Agentic Company Researcher — Check

**GitHub:** guy-hartstein/company-research-agent
**Stars:** wachsend | **Lizenz:** MIT | **243 Commits**

### Was es macht

8 spezialisierte Agenten in Pipeline:
```
CompanyAnalyzer → IndustryAnalyzer → FinancialAnalyst → NewsScanner
    ↓
Collector → Curator → Briefing → Editor → PDF
```

### Architektur — interessant

| Komponente | Tech |
|------------|------|
| Orchestrierung | LangGraph |
| Suche | Tavily API |
| Synthese | Gemini 2.5 Flash |
| Formatierung | GPT-5.1 |
| Backend | FastAPI |
| Frontend | React |

### ❌ Für uns unbrauchbar — warum

- **Tavily:** API-Key tot, kostet Geld
- **Gemini + GPT:** beides kostenpflichtige APIs
- **Finanzanalyse:** irrelevant für Handwerker-Kontakte
- **Fokus:** Unternehmens-Due-Diligence, nicht Kontakt-Extraktion

---

### ✅ Was wir MITNEHMEN können

Die **Curator-Idee** ist stark: Relevanz-Scoring VOR der Synthese, nicht alles in einen Topf werfen. Das fehlt in unserer Pipeline.

Unser JobHunter-Channel-Discovery macht das bisher so:
```
DDGS-Suche → t.me-Links → DB
HN API → Keyword-Filter → DB
```

Mit Curator-Schritt:
```
DDGS-Suche → Relevanz-Score → NUR Top-Ergebnisse → DB
```

Das können wir in 30 Minuten nachrüsten — ohne externe APIs, nur mit dem job_extractor.py den wir schon haben.

---

**Fazit:** Cooles Tool für Corporate Research, aber für Handwerker am Balaton ist unsere eigene Pipeline schneller und kostet 0€. Soll ich den Curator-Schritt einbauen, oder erstmal bei der Jobsuche weitermachen?
[user]: da rüste bitte jubhuter auf danke
[assistant]: Bauen wir den Curator-Schritt ein. Erst checken was wir haben, dann erweitern:
[user]: bitte bau es du hast es abgebrochen weil ich den pc aus schalten muste
[assistant]: Alles klar, bauen wir fertig. Curator ist schon geschrieben — jetzt in die Scanner einbauen:
[assistant]: Jetzt `run_all.py` updaten mit Curator-Stats:
[assistant]: Läuft. Jetzt testen:
