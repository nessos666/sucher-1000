# SUCHER-1000 — Hermes-Skill (detaillierte Beschreibung)

> **Was ist das?** Ein Hermes-Skill, der einem KI-Agenten den Zugriff auf
> **SUCHER-1000** gibt — ein Multi-Engine-Suchtool, das bei EINEM Aufruf
> **40+ Quellen parallel** durchsucht und die Ergebnisse strukturiert archiviert.
> Kein API-Key nötig zum Start.

---

## 🧠 Was SUCHER-1000 kann (im Überblick)

| Fähigkeit | Beschreibung |
|---|---|
| **Web-Suche** | DuckDuckGo, Bing, Mojeek, Wikipedia (DE/EN), HackerNews, GitHub, StackExchange, YouTube, Google Scholar, Google Patents, Reddit, HuggingFace, News-Feeds (Google/Bing) u.v.m. — parallel |
| **Wissenschaft** | OpenAlex, PubMed, EuropePMC, arXiv, Crossref, DOAJ, SemanticScholar, ClinicalTrials, Zenodo, DataCite, DBLP, OpenAIRE, OpenReview, OSF, CORE, DOAB |
| **Lokale Suche** | Durchsucht die eigene Wissensbasis (Dateinamen) — findet, was du schon hast |
| **Archiv-Suche** | Jede Suche wird automatisch in SQLite archiviert; `--archiv` durchsucht ALLE gespeicherten Treffer per FTS5-Blitz-Suche — **auch offline** |
| **Kein Key nötig** | Kern-Quellen key-frei; optionale Premium-Quellen (Tavily, Serper, ZenRows, Firecrawl …) nur als Zusatz |
| **Funktioniert IMMER** | Health-System + Cooldown: tote Quellen werden automatisch übersprungen, andere liefern weiter |

## 🔢 Zahlen (Stand 09/2026)

- **40+ Quellen** (Web + Wissenschaft + optional Paid)
- **~1.200 archivierte Ergebnisse** in der Such-DB
- **219 automatisierte Tests**, Quality-Gate 18/18
- **3 AI-Review-Durchgänge** (Codex + OpenCode), alle Findings behoben

## 🚀 Installation

```bash
git clone <dein-repo-url> sucher-1000
cd sucher-1000
./setup.sh                 # venv + Abhängigkeiten + globaler 'sucher'-Befehl
```

Oder als Hermes-Skill:
```bash
hermes skills install <owner>/sucher-1000/skills/sucher-1000
```

## 💡 Beispiele

```bash
sucher "PTBS Behandlung München"          # Web-Suche
sucher "bentonite water retention" --modus studien   # Wissenschaft
sucher "KI Agenten" --modus alle          # Web + Studien parallel
sucher --archiv "bentonit"                # alle früheren Treffer durchsuchen
sucher --quelle pubmed "crispr"           # nur eine Quelle
```

## 📁 Projektstruktur

```
sucher-1000/
├── sucher.py              ← CLI-Einstieg
├── setup.sh               ← Installation
├── check.sh               ← Quality-Gate (18 Stufen)
├── src/                   ← Kern-Module (Fanouts, Netz, Cache, Health, FTS5)
├── scripts/               ← Auth-Wizard, Golden-Check, Health-Check
├── skills/sucher-1000/    ← dieser Hermes-Skill
├── data/golden_queries.json  ← Qualitäts-Messbasis (12 Themen)
└── tests/                 ← 219 Tests (Netz gemockt, offline reproduzierbar)
```

## 🛡 Qualität & Ehrlichkeit

- **Messbar statt behauptet:** Golden-Query-Check misst live, ob Themen ihre
  erwarteten Quellen finden (10/12, Rest ehrlich dokumentiert)
- **Reproduzierbar:** alle Tests offline (Netz gemockt), Gate als Skript
- **Transparenz:** nach jeder Suche „ℹ X von Y Quellen lieferten Treffer" —
  kein stiller Verdacht, etwas sei kaputt

## 📜 Lizenz

MIT — frei nutzbar, kopierbar, einbaubar. Details siehe `LICENSE` im Repo.
