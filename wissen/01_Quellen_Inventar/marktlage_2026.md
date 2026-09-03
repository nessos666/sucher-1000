# Marktlage Web-Such-APIs 2026 (Recherche 03.09.2026)

> Quellen: parallel.ai Vergleich (Aug 2026), iTechGuides 7-API-Vergleich, IntuitionLabs,
> SCiNiTO, CASRAI. Alles live abgerufen am 03.09.2026.

## ⚠️ KRITISCHE ÄNDERUNG: Brave-Free gibt es NICHT mehr!

**Seit Februar 2026** wurde der Brave-Free-Tier (2.000–5.000 Queries/Monat) **eliminiert**.
Jetzt: $5 monatliche Credits auf Metered-Plans, **Karte Pflicht** seit 2023, Attributions-Pflicht.
→ **$5 = nur ~1.000 Suchen/Monat, dann wird die Karte belastet.**

**Konsequenz für Davids Fix vom 03.09.2026:** `search_backend: brave-free` funktioniert noch
(Key existiert mit Rest-Credits), aber das Limit ist eine Zeitbombe. **Robuste Langzeit-Lösung:
Tavily als Primary** (siehe unten).

## Google Custom Search API: stirbt

- Für Neukunden **geschlossen**, Abschaltung **01.01.2027**.
- Nachfolger Vertex AI Search = nur Site-Search, kein offenes Web.

## Die Free-Tiers 2026 (ehrlich verglichen)

| Anbieter | Free | Karte? | Nachfüllung | Beste Rolle |
|----------|------|:------:|-------------|-------------|
| **Tavily** | 1.000 Credits/Monat | ❌ Nein | monatlich | ✅ **Bester Default für Research-Agenten** — Search + Extract in einem |
| **Exa** | $20 Start + $10/Monat | ❌ Nein | monatlich | Semantische Suche |
| **Firecrawl** | 1.000 Credits/Monat | ❌ Nein | monatlich | Search + Crawling + Extract |
| **SerpApi** | 250 Google-Suchen/Monat | ❌ Nein | nein (one-time) | Echte Google-Rankings |
| **Brave** | $5/Monat Credits | ✅ Ja | monatlich | Unabhängiger Index (aber Karte!) |
| **SearXNG** | Self-hosted, 0€ | — | — | Privatsphäre, aber Blocking-Risiko |
| **Parallel** | Freier MCP-Server, kein Account | ❌ | — | Agenten-Suche (neu 2026, $1/1000 paid) |
| **Linkup** | 4.000 Start + $5/Monat | ? | monatlich | Compliance-lastig |

## Kern-Lektionen (für „SUCHER funktioniert IMMER")

1. **„Free" heißt nie „unbegrenzt"** — Credits/Quotas/Rate-Limits binden immer.
2. **Karte = Risiko** (unbeabsichtigte Metered-Rechnung bei Retry-Loop um 3 Uhr nachts).
3. **Raten-Limit bindet vor Credits** — Parallel-Fanout braucht RPM-Check, nicht nur Credits.
4. **Wer liefert dichte Antwort-Exzerpte statt 20-Wort-Snippets?** → spart Folgefetchs
   (Tavily/Parallel besser als klassische SERP).
5. **Eigener Web-Index > Scraped-SERP** (Rechts-/Kontinuitätsrisiko bei Scraping-Diensten).

## Empfehlung für SUCHER-1000 (Hermes-unabhängig, immer funktionierend)

**Stufe 1 — Kein Key nötig (immer verfügbar):** akademische APIs (OpenAlex/Crossref/DOAJ/
EuropePMC/SemScholar — das macht STUDIEN_SEARCH_TOOL schon korrekt, eigenes Git-Repo!)

**Stufe 2 — Key-basiert, Karte-frei, verlässlich:** Tavily (1.000/Monat, keine Karte)

**Stufe 3 — Zusatz-Deckung (optional):** Exa ($10/Monat geschenkt), Firecrawl

**NICHT als Fundament:** Brave (Karte!), Google CSE (stirbt), reines SearXNG (Blocking)

## Wissenschaftliche APIs (Recherche-Ergebnis)

| API | Umfang | Key | Rolle |
|-----|--------|-----|-------|
| **OpenAlex** | 250M+ Werke, 90M Autoren | ❌ | Standard, offen, kein Key — Dev.to bestätigt |
| **Crossref** | DOI-Registry | ❌ | Zitations-Daten |
| **Semantic Scholar** | 200M+ Paper | ❌ | AI-Summaries, Citation-Rankings |
| **PubMed** | Biomedizin, MeSH | ❌ | Systematische Reviews |
| **OpenCitations** | Zitations-Graph | ❌ | offen |
| **Dimensions** | Output↔Grants↔Patents | lizenziert | nur mit Lizenz |
| **Scopus/WoS** | — | $$$ | Institutionell, für SUCHER irrelevant |

**Für Tool-Bau/Korpus-Analyse:** OpenAlex oder Semantic Scholar (offene APIs).
**Für systematische biomedizinische Reviews:** PubMed zuerst.
