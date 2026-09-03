# SUCHER-1000 — Multi-Quellen-Such- & Wissens-Tool

> **Ein Ordner für alles:** Suchen (Studien/Paper/Universal) + das gesamte Websuche-Wissen.
> Git-versioniert, update-proof, eigenständig. Stand: 03.09.2026.

## Was ist SUCHER-1000?

Eine Such-Pipeline in EINEM Ordner:
```
sucher.py "suchbegriff" 8 [--modus studien|universal|alle] [--quelle <name>]
  → 12 Quellen (OpenAlex, Crossref, DOAJ, EuropePMC, SemScholar, Wikipedia,
     arXiv, bioRxiv, PubMed, BASE, Wikidata, Lokal)
  → dedupliziert + Cross-Quellen-Scoring
  → Ergebnis: ergebnis_*.json + Markdown-Report in ergebnisse/
```

## Ordner-Struktur (Git)

| Ordner | Inhalt |
|--------|--------|
| `sucher.py` | Haupt-Einstiegspunkt |
| `src/` | `sucher_universal.py` (12 Quellen), `sucher_oa.py`, `sucher_download.py` |
| `ergebnisse/` | Such-Ergebnisse: JSON + Markdown-Reporte (Studien zu EMDR, Trading, ...) |
| `wissen/00_UEBERSICHT.md` | **Master-Index** des Websuche-Wissens |
| `wissen/01_Quellen_Inventar/` | Alle Quellen aller 3 Such-Projekte |
| `wissen/02_Audits/` | Health-Checks, Benchmarks, Status-Ampeln |
| `wissen/03_Architektur/` | Architektur-Vergleich SUCHER / DeepWeb / ApplicationPlatform |
| `wissen/04_Pitfalls_Fixes/` | 12 Fallen + Fixes (inkl. brave-free-Fix 03.09.2026) |
| `wissen/05_Sessions_Qdrant/` | 38-Searcher-Voll-Session + Erkenntnis-Verlauf |
| `docs/` | Validierungs-Doku |
| `legacy/` | Alte Einzel-Skripte (batch_search, studien_search) |

## Nutzung

```bash
cd ~/HAUPTLAGER/03_PROJEKTE/42_Sucher_Tool
python3 sucher.py "posttraumatic growth" 8 --modus studien     # akademisch
python3 sucher.py "Vermögensberater" 4 --modus universal        # allgemein
python3 sucher.py "bioenergetic analysis" 4 --quelle wikipedia  # nur 1 Quelle
```

## Git-Regeln

- 1 Block = 1 Commit = STOP (nie ohne Davids Go weiter)
- Jede Änderung im Repo versioniert — keine parallelen Branches
- Wissen konsolidieren, nichts löschen, nichts doppelt bauen
