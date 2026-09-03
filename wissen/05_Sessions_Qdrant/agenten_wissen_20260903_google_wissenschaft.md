# Agenten-Wissen 03.09.2026 Runde 3 — Google-Teile + Wissenschaft (deleg_b109285c)

Live-verifiziert per curl (deutsche IP). Kontext: David will Reddit/GitHub/
HuggingFace (eingebaut Block 7+8), mehr Google-Kleinode, mehr Wissenschaft.

## A) Google-eigene APIs (Agent 1) — live geprüft

| # | Quelle | Live 2026 | Key | Format |
|---|---|---|---|---|
| 1 | **YouTube InnerTube** (youtubei/v1/search, Public-Web-Key) | ✅ 200, 20 Treffer | keiner (inoffiziell) | JSON POST |
| 2 | **Google-Autosuggest** (suggestqueries.google.com/complete/search?client=firefox) | ✅ 200 | keiner | JSON |
| 3 | Google News RSS | ✅ (schon drin) | keiner | RSS |
| 4 | **Google Scholar** (HTML) | ✅ 200, 0 Captcha heute | keiner | HTML, captcha-Gefahr |
| 5 | Google Patents XHR | ✅ (Block 8, heute 503 nach Serie) | keiner | JSON |
| 6 | Google Books | ❌ anonym 429; ✅ mit kostenlosem Key | Key | JSON |
| 7 | Google Trends | ⚠️ blockt DC-IPs | — | JSON m. Präfix |
| 8 | Knowledge Graph API | ✅ 403 ohne Key; 100k Calls/Tag gratis | Key | JSON |
- YouTube oEmbed/Channel-RSS (key-frei, Metadaten), Books-Ngram (key-frei,
  Worthäufigkeit), Google-Suche-html tbm=bks/shop/isch (leben, captcha-Risiko)
- Maps: Key+Billing nötig. CSE: tot 01/2027 (nicht nehmen)

## B) Wissenschaft (Agent 2) — live geprüft, Top-10

| # | Quelle | Live | Key | Format | Endpoint |
|---|---|---|---|---|---|
| 1 | **ClinicalTrials.gov v2** | ✅ 200 | nein | JSON | /api/v2/studies?query.term=… |
| 2 | **OpenReview v1** | ✅ 200 | nein | JSON | api.openreview.net/notes/search?term=… (v2=403!) |
| 3 | **OSF Preprints** | ✅ 200 | nein | JSON | api.osf.io/v2/preprints/?filter[title]=… |
| 4 | bioRxiv/medRxiv | ✅ 200 | nein | JSON | nur Harvest nach Datum, KEIN Keyword |
| 5 | PMC E-utilities | ✅ 200 | nein (3r/s) | XML | eutils.ncbi.nlm.nih.gov (efetch 159KB) |
| 6 | **CORE v3** | ✅ 200 OHNE Key (curl -L!) | frei | JSON | api.core.ac.uk/v3/search/works?q=… |
| 7 | DOAB + OAPEN | ✅ DSpace 6.3 | nein | XML-OAI | /oai/request |
| 8 | OpenLibrary | ✅ (schon drin) | nein | JSON | — |
| 9 | RePEc/EconPapers | ⚠️ HTML+RSS, kein REST | nein | HTML | econpapers.repec.org |
| 10 | Unpaywall + OpenCitations COCI | ✅ | Email/nein | JSON | DOI-Lookup + Zitationsgraf |
- Verworfen: SSRN (403 Botwall), Lens (401 Key), Scilit (403), Dimensions (paid),
  IEEE/ACM (nur via Crossref-DOI), BASE (Anubis), WHO-ICTRP (kein REST)
- Wichtig für David: ClinicalTrials (klinische Studien), Preprints via EuropePMC
  SRC:PPR schon abgedeckt; OpenReview/OSF als Direktquellen ergänzen

## Nächste Umsetzung (Block 9)

**Wissenschaft (SCI):** clinicaltrials, openreview, osf, core → je RED-Test+Commit
**Web:** youtube (InnerTube) — Google-Kleinod, live 20 Treffer
