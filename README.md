# SUCHER — Davids Studien- & Literatur-Such-Tool

## Name & Status
- **Name:** SUCHER (Ausbaustufe 1000 = "Sucher 1000")
- **Status:** Eigener, **update-proof Git-Ordner** — getrennt von `~/.hermes`, überlebt Hermes-Updates.
- **Besitzer:** David (gebaut mit Hermes, Code von Hermes, Anforderung + Konzept von David)

## Was es kann
Robuste **Multi-Quellen-Suche** über 6 Quellen (mit Fallback), **universal für jedes Thema**:

### Modi (wahlbar)
- `--modus studien` — nur Wissenschaft (OpenAlex, DOAJ, Crossref, Europe PMC, Semantic Scholar)
- `--modus universal` — Wissenschaft + Allgemeinwissen (Wikipedia DE/EN) → Standard
- `--modus alle` — alle Quellen

### Quellen
- **Wissenschaft:** OpenAlex · DOAJ · Crossref · Europe PMC · Semantic Scholar
- **Allgemein:** Wikipedia (deutsch + englisch)
- `--quelle NAME` — nur eine bestimmte Quelle suchen (z.B. `--quelle wikipedia`)

## Nutzung (im HAUPTLAGER)
```bash
cd ~/HAUPTLAGER/03_PROJEKTE/42_Sucher_Tool
python3 sucher_universal.py "dein Suchbegriff" [anzahl] [--modus M] [--quelle Q]
python3 sucher_universal.py --list        # Quellen & Modi anzeigen
python3 batch_search.py                    # 8-Themen-Batch
python3 studien_search.py "query"          # alte Einzelversion (nur Wissenschaft)
```

## Ausgabe-Felder
`title` · `year` · `venue` · `is_oa` (frei?) · `pdf` (Link) · `doi` · `source` · `url` · `snippet`

## Ehrlichkeit
- ✅ FREI = frei ladbar (oder PDF-Link) · 🔒 geschützt = nicht frei → **legal** über Onleihe/Bibliothek/Verlag
- Bei `--quelle wikipedia`: Allgemeinwissen-Einträge (kein PDF, frei zugänglich)

## Update-Schutz
Liegt **außerhalb** `~/.hermes/` (`HAUPTLAGER/03_PROJEKTE/42_Sucher_Tool`) → **überlebt** `hermes update`.