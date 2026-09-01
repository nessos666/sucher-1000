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

## Downloads mit Bot-Schutz-Umgehung
**Problem:** Viele Open-Access-Studien (PMC, Taylor&Francis u.a.) blocken `curl` via
**reCAPTCHA/Cloudflare** → nur leere Stubs.
**Lösung (Sucher-Download, `sucher_download.py`):**
```bash
python3 sucher_download.py "https://pmc.ncbi.nlm.nih.gov/articles/PMC13508539/" [ausgabe.md]
```
Strategie:
1. **curl** (schnell, für offene Quellen)
2. Erkennt Block (reCAPTCHA/Cloudflare/<40KB) automatisch
3. Legt `.browser_task`-Datei ab → **Hermes gibt sie an die reale Browser-Engine** (`browser_exec`), die reCAPTCHA umgeht (echte Browser-Sitzung)
4. HTML→Markdown-Konvertierung (html2text)

**Einfachster Aufruf:** Sage im Chat z.B. *"Sucher, lade URL X"* — Hermes nutzt dann automatisch: curl → bei Block Browser-Engine → speichert als Markdown in den Zielordner. (Demo: Online-EMDR-Studie, die per Browser-Engine gerettet wurde.)

## Autopilot-Workflow (blockierte Quellen)
1. `sucher_universal.py "thema"` → findet Studie + PDF/DOI-Link
2. `sucher_download.py <url>` → versucht curl
3. Bei Block: Browser-Engine (`browser_exec`) → extrahiert Volltext → `.md` in Ordner
4. Ehrlicher Check: Titel/Abstract verifizieren (keine fehl-zugeordneten Dateien)