# SUCHER 1000 — Davids großes Studien- & Literatur-Tool

**Update-proof · eigenständig · unabhängig von Hermes**

## Struktur (Git-Ordner, eigenständig)
```
42_Sucher_Tool/
├── sucher.py          ← HAUPT-Einstiegspunkt (die ganze Pipeline in einem Befehl)
├── src/               ← Module (suchen → freie Version → download)
│   ├── sucher_universal.py    (7-Quellen-Suche)
│   ├── sucher_oa.py           (Unpaywall/OpenAlex/EuropePMC → freie Version)
│   └── sucher_download.py     (curl → bei Block Browser-Engine)
├── ergebnisse/        ← Output (JSON + geladene PDFs/Markdown + LOG)
├── docs/              ← Anleitungen
├── legacy/            ← alte Versionen (batch_search, studien_search)
└── README.md
```

## Das große Tool — eine Pipeline
```
SUCHE (7 APIs) → OA-Resolver (freie Version finden) → DOWNLOAD (curl→Browser) → SORTIEREN → LOG
```
**Ein Befehl:**
```bash
python3 sucher.py "EMDR complex PTSD" 8 --modus studien             # nur suchen
python3 sucher.py "online EMDR" 3 --download                        # suchen + laden
python3 sucher.py --setup                                           # Umgebungs-Check
python3 sucher.py --sources                                         # Quellen anzeigen
```

## Quellen (7 wissenschaftlich + Allgemein)
OpenAlex · Crossref · DOAJ · Europe PMC · Semantic Scholar · arXiv · bioRxiv + Wikipedia
plus **OA-Resolver:** Unpaywall + OpenAlex + Europe PMC (findet kostenlose Version vor Download).

## Bot-Schutz-Lösung (reCAPTCHA/Cloudflare)
1. **OA-Resolver** → findet die freie PMC/UP-Version (vermeidet Block an der Wurzel)
2. **curl** → lädt offene Quellen
3. **Browser-Engine** (via Hermes/chrome) → holt, was curl nicht kann (echte Browser-Sitzung)

## Ehrlichkeit
- Falsch zugeordnete DOIs/Studien werden **nicht übernommen** (PDF-Erkennung + Titelcheck).
- Geschützte → ehrlich „keine freie Version" markiert (nie Raubkopie).
- Alles im LOG (`ergebnisse/sucher_log.md`) nachvollziehbar.

## Unabhängig von Hermes (Update-proof)
Liegt in `HAUPTLAGER/03_PROJEKTE/42_Sucher_Tool` — **außerhalb** `~/.hermes/`.
`hermes update` berührt nichts hier. Code bei Bedarf mit OpenCode validiert.