---
name: sucher-1000
description: "40+ Quellen parallel durchsuchen, kein Key nötig."
version: 1.0.0
author: David Miko, Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [suche, recherche, web, wissenschaft, multi-engine]
---

# SUCHER-1000 — Multi-Engine-Suchtool nutzen

SUCHER-1000 durchsucht bei EINEM Aufruf 40+ Quellen parallel: Web (DuckDuckGo,
Bing, Wikipedia, HackerNews, GitHub, YouTube, Google Scholar …) UND Wissenschaft
(OpenAlex, PubMed, arXiv, EuropePMC, ClinicalTrials, Zenodo …). Key-frei
startbar, alle Ergebnisse werden automatisch in einer SQLite-DB archiviert und
sind danach per Blitz-Suche (FTS5) lokal durchsuchbar — auch ohne Netz.

Dieser Skill beschreibt BEDIENUNG + Installation des Tools, nicht seinen Bau
(dafür: `research-engine-development`).

## When to Use

- Nutzer will „suchen / recherchieren / nach X googeln / alles durchsuchen"
- Nutzer fragt nach einem Thema aus Web + Wissenschaft gleichzeitig
- Nutzer will frühere Suchergebnisse wiederfinden (Archiv-Suche)
- Nutzer fragt „was können wir noch einbauen / warum so wenige Treffer"

Don't use for: Quellen-Erweiterung, Parser-Bau, Härtung (→ research-engine-development).

## Prerequisites

- Repo: `git clone` des SUCHER-1000-Repos (bei David: `~/HAUPTLAGER/03_PROJEKTE/
  42_Sucher_Tool/`). Pfad VOR dem Lauf per `search_files target='files'
  pattern='sucher.py'` bestätigen — Repos können umgezogen sein.
- `setup.sh` einmalig: prüft python3 → venv → Abhängigkeiten → globalen
  `sucher`-Starter in ~/.local/bin → optionale API-Keys.
- Kein API-Key nötig zum Loslegen (Kern-Quellen key-frei). Optionale Keys
  (Tavily/Serper/ZenRows/…) via `scripts/sucher_auth.py --add <quelle>`.

## How to Run

Immer mit Umleitung in eine Datei, NIE durch eine Pipe (`| head`) — eine früh
schließende Pipe tötet den Prozess VOR dem Datei-/DB-Schreiben (BrokenPipe):

```bash
cd <sucher-repo>                      # Klon-Pfad (Davids: ~/HAUPTLAGER/03_PROJEKTE/42_Sucher_Tool)
.venv/bin/python sucher.py "<begriff>" 12 --modus alle --out ergebnisse/<slug> \
  > /tmp/<slug>.log 2>&1
```

Dann das Log lesen (Treffer + „→ N Treffer" + JSON-Pfad + DB-Archiv). ~30s.

## Quick Reference

```bash
sucher "Thema"                      # Web + Studien (Modus: universal)
sucher "Thema" --modus web          # nur Web-Engines (ddgs/Bing/Wikipedia/…)
sucher "Thema" --modus studien      # nur Wissenschaft (OpenAlex/PubMed/…)
sucher "Thema" --modus alle         # Web + Studien zusammen (parallel)
sucher "Thema" --quelle pubmed      # NUR eine Quelle
sucher --archiv "bentonit"          # lokale Archiv-Suche (FTS5, kein Netz)
sucher --archiv 'water retention'   # UND: beide Wörter
sucher --archiv 'trauma !kindheit'  # NOT: ohne 'kindheit'
sucher --sources                    # alle Quellen anzeigen
sucher --setup                      # Umgebung prüfen
sucher n=12                         # Tiefe PRO QUELLE (Default 12)
```

## Procedure

1. **Repo-Pfad finden** (`search_files target='files' pattern='sucher.py'`),
   dann `cd` dorthin.
2. **Aufruf bauen**: Thema + Modus wählen. How-to-/Praxis-Themen → `--modus web`
   (Studien-Quellen liefern dafür Rauschen); Wissenschaft/Forschung → `studien`;
   beides → `alle`. n=12 als Default-Tiefe.
3. **Ausführen mit Log-Umleitung** (siehe How to Run), Log lesen.
4. **Ergebnisse nutzen**: JSON liegt unter `--out`, DB-Archiv in `data/sucher.db`.
5. **Bei Bedarf vertiefen**: `sucher --archiv '<begriff>'` findet frühere Suchen.

## Pitfalls

- NIE Ausgabe durch `| head`/`| tail` pipen — BrokenPipe tötet vor dem Speichern.
- „X von Y Quellen lieferten Treffer" ist NICHT kaputt: Spezial-Quellen (GitHub,
  Patents) haben zu Nischenthemen („Hausmeister Island") schlicht keinen Inhalt.
- Mehrdeutige Begriffe (Personen-/Ortsnamen): Studien-Fanouts liefern
  akademisches Rauschen — kritisch sortieren, ggf. `--modus web`.
- Ohne Key übersprungene Quellen sind normal (Meldung mit Key-URL, kein Fehler).
- Erste Suche zu einem Thema kann 429-Rate-Limits treffen — zweiter Versuch ok.

## Verification

- Log endet mit „→ N Treffer" UND „Ergebnis: <pfad>.json" UND „SQLite-Archiv"
  (fehlt das Speichern, starb der Prozess früh — Pipe-Fehler prüfen).
- `sucher --archiv '<neuer begriff>'` findet die frisch gespeicherten Treffer.
- `sucher --setup` meldet alle Module ✓.
