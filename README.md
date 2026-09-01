# SUCHER — Davids Studien- & Literatur-Such-Tool

## Name & Status
- **Name:** SUCHER (Ausbaustufe 1000 = "Sucher 1000")
- **Status:** Eigener, **update-proof Git-Ordner** — getrennt von `~/.hermes`, überlebt Hermes-Updates.
- **Besitzer:** David (gebaut mit Hermes, Code von Hermes, Anforderung + Konzept von David)

## Was es kann
Robuste **Multi-Quellen-Studiensuche** über 5 wissenschaftliche APIs (mit Fallback):
- **OpenAlex** (große Open-Data-DB, Open-Access-Erkennung + PDF-Links)
- **DOAJ** (reine Open-Access-Zeitschriften)
- **Crossref** (DOI-Metadaten)
- **Europe PMC** (biomedizinische Volltexte, PMC-IDs)
- **Semantic Scholar** (Fallback)

Findet Studien + frei ladbare PDFs + legale Bezugswege (kein DDGS-Drama).

## Nutzung (im HAUPTLAGER)
```bash
cd ~/HAUPTLAGER/03_PROJEKTE/42_Sucher_Tool
python3 studien_search.py "deine suchanfrage" [anzahl]   # Einzelsuche
python3 batch_search.py                                   # 8-Themen-Batch
```

## Ausgabe-Felder
`title` · `year` · `venue` · `is_oa` (frei?) · `pdf` (Link) · `doi` · `source` · `pmcid`

## Ehrlichkeit
- ✅ FREI = Quelle meldet Open Access (oder `pdf`-Link vorhanden)
- 🔒 geschützt = nicht frei → **legal** über Onleihe/Bibliothek/Verlag (nie Raubkopie)
- Von Quelle blockierte Fulltext-Links (Cloudflare o.ä.) → Liste im Batch-Ergebnis; Browsert-Download.

## Update-Schutz
Dieses Tool liegt **außerhalb** `~/.hermes/` (in `HAUPTLAGER/03_PROJEKTE/42_Sucher_Tool`),
daher **überlebt** `hermes update` vollständig. Bei Bedarf zusätzlich als Skill-Datei verlinkbar.