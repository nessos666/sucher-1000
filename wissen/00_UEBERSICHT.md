# 00 — Websuche-Wissen Master-Index

> Konsolidiert am 03.09.2026. Alles Websuche-Wissen von Davids Rechner an EINEM Ort.
> Herkunft: SUCHER-1000, DeepWeb_Tool, ApplicationPlatform, Qdrant-Sessions, Hermes-Skills.

## Ordner-Logik

| Ordner | Inhalt |
|--------|--------|
| `01_Quellen_Inventar/` | Alle Such-Quellen je Projekt (SUCHER/DeepWeb/ApplicationPlatform) |
| `02_Audits/` | Gemessene Health-Checks, Benchmarks, Status-Ampeln |
| `03_Architektur/` | Wie die Tools aufgebaut sind (Router, Fallback-Ketten, Parallelität) |
| `04_Pitfalls_Fixes/` | Jede Falle + der Fix, der funktioniert hat |
| `05_Sessions_Qdrant/` | Erkenntnisse aus Qdrant-Sessions (Verlauf, Entscheidungen) |

## Die 3 Websuche-Projekte (nicht verwechseln!)

| Projekt | Ort | Quellen | Zweck |
|---------|-----|---------|-------|
| **SUCHER-1000** (dieses Repo) | `42_Sucher_Tool/` | 12 Quellen | Studien, Paper, Dossiers |
| **DeepWeb_Tool** | `~/PROJECTS_CLEAN/DeepWeb_Tool/` | 15 Engines, 13+ Provider | Discovery, „Universum durchsuchen" |
| **ApplicationPlatform** | `Hermes_Projects/ApplicationPlatform/` | 9 Engines + 38-Searcher-Audit | JobHunter-Firmensuche (Legacy) |

## Die 2 kritischen Erkenntnisse (03.09.2026)

1. **Hermes' eigener `web_search` zeigte auf SearXNG** → alle Engines blockt → leer/Wikipedia-Junk.
   **Fix:** `search_backend: brave-free`, `extract_backend: tavily` (Keys liegen in Hermes-Env-Datei). Live verifiziert: 2×5 echte Treffer.
2. **„Ohne Limit, ohne Block" gibt es nicht** — jede Engine blockt/drosselt. Die Lösung ist Redundanz + Fallback-Kette + API-Keys, nicht ein Zauber-Tool.

## Verwandte Skills (Hermes)

- `research-engine-development` — Bau-Muster für eigenständige Such-Tools
- `deep-web-search-tool` — DeepWeb-Architektur + SUCHER-Referenzen
- `qdrant-wissenssuche` — Davids Wissensbasis durchsuchen
- `web-extraction-fallback` — curl-Fallback wenn web_extract scheitert
- `blocked-page-recovery` — Wayback/archive.today bei Blockaden
