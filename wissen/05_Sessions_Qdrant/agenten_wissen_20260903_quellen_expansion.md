# Agenten-Wissen 03.09.2026 Runde 2 — Quellen-Expansion (deleg_03ed951d)

Drei Recherche-Agenten, ALLE Quellen-Status live per curl (deutsche IP) verifiziert.
Kontext: 10 Web-Quellen + 10 akademische eingebaut. Ziel: +10-20 neue Quellen,
davon key-frei UND bezahlt als Option (NO_KEY-Mechanik + Key-Wizard).

---

## A) Kostenlose Web-/Wissens-Quellen (Agent 1) — Top 12, live geprüft

| # | Quelle | Live 2026 | Key | Limit | Format |
|---|---|---|---|---|---|
| 1 | **StackExchange-API** | ✅ 200 | nein | 300/Tag (10k mit Free-App-Key) | JSON |
| 2 | **Internet Archive advancedsearch** | ✅ 200 (numFound 38k) | nein | fair use 1-2 r/s | Solr-JSON |
| 3 | **OpenLibrary** | ✅ 200 (numFound 4.3k) | nein | fair use | JSON |
| 4 | **Marginalia** (api.marginalia.nu public) | ✅ 200; api2=429 geteilt | 'public' gratis | geteilt, oft leer | JSON |
| 5 | **GitHub-Suche** (Repos+Issues) | ✅ 200 | nein (Code braucht PAT) | 10 Such/min | JSON |
| 6 | **Wikiquote/Wikinews/Wikisource** DE+EN | ✅ alle 6 | nein | fair use, UA setzen | MediaWiki-JSON |
| 7 | **DEV.to API** | ✅ 200 | nein | großzügig | JSON (Tag-Feed, kein Search) |
| 8 | **Gutendex** (Gutenberg) | ✅ 200 (301 folgen!) | nein | freundlich | JSON |
| 9 | **Lobsters** | ✅ JSON+HTML | nein | be nice | JSON+HTML |
| 10 | **Medium RSS-Tag-Feeds** | ✅ 200 | nein | unkritisch | RSS |
| 11 | **Reddit Data API** (offiziell OAuth) | OAuth ✅, .json=403 | OAuth-App frei | 100 QPM | JSON |
| 12 | **Wiby** (Smallweb) | ✅ 200 | nein | kein Limit | HTML |

**Verworfen (live getestet):** Startpage (Anubis-JS), Brave (429), Ecosia (403),
Yahoo (conn reset), Yep (403), Petal (DNS tot), Stract (404), GDELT https (instabil;
http lebt, 1 req/5s — nur mit kurzem Timeout), Common Crawl (nur URL-Lookup,
kein Keyword).

## B) Wissenschaft + Politik/amtlich (Agent 2) — Top 15, live geprüft

**Wissenschaft (8):**
1. **Zenodo** (CERN): key-frei, JSON — https://zenodo.org/api/records?q={Q}&size=25
2. **OpenAIRE** (EU): key-frei, JSON — api.openaire.eu/search/publications (alte API
   deprecated 31.05.2026 → Graph-API v3 Umstieg einplanen)
3. **DataCite**: key-frei, JSON — api.datacite.org/dois?query={Q} (~40 Mio DOIs)
4. **DBLP** (Informatik): key-frei, JSON — dblp.org/search/publ/api (1 req/3s Etikette)
5. **Unpaywall**: E-Mail statt Key (kein Freitext, DOI-Lookup → OA-Volltext-Anreicherung!)
6. **DOAB** (OA-Bücher): key-frei — directory.doabooks.org/rest/search
7. **OpenReview**: key-frei — api.openreview.net/notes/search (ICLR/NeurIPS inkl. Reviews)
8. **OSF Preprints**: key-frei — api.osf.io/v2/preprints/ (SocArXiv/PsyArXiv…)
- CORE: Free-Key nötig (ohne = 429) → Key-optional aufnehmen

**Politik/amtlich (5+):**
10. **Eurostat**: key-frei, JSON-stat v2 — ec.europa.eu/eurostat/api/… (updated 08/2026)
11. **EZB SDW**: key-frei — data-api.ecb.europa.eu (ALT-Host seit 01.10.2025 TOT!)
12. **Weltbank**: key-frei — api.worldbank.org/v2 (BIP etc., updated 07/2026)
13. **OECD**: key-frei SDMX — stats.oecd.org (ACHTUNG: immer gzip+detail=dataonly, sonst >100MB!)
14. **UN SDG API**: key-frei — unstats.un.org/SDGAPI (UNdata tot ohne Registrierung)
15. **GDELT**: key-frei, 1 req/5s — http (https instabil von DE-IP)
- **GovData.de**: key-frei CKAN — govdata.de/ckan/api/3/action/package_search (Pfad /ckan/ nötig!)
- Key nötig (gratis): GovInfo (US), DIP Bundestag, destatis GENESIS
- Probleme: data.europa.eu (Schema kaputt), SSOAR (Anubis), PapersWithCode (SPA),
  EUR-Lex (SOAP+Login), IMF (Migrationszustand), BASE (Key IP-gebunden)

## C) Bezahl-APIs als OPTION (Agent 3) — Top 10 + UX-Empfehlung

| # | Anbieter | Free (kartenfrei) | Preis/1k | Key-URL |
|---|---|---|---|---|
| 1 | **Serper.dev** | 2.500 einmalig ✅ | $1,00 | serper.dev/api-key |
| 2 | **You.com** | 100/Tag DAUERHAFT ✅ | $5,00 | you.com/platform |
| 3 | **ZenRows** | 5.000/Monat ✅ | $0,36 | app.zenrows.com |
| 4 | **Firecrawl** | 1.000/Monat ✅ | ~$3,20 | firecrawl.dev |
| 5 | **Jina Reader/Search** | Reader keylos ✅ | token | jina.ai |
| 6 | **ScaleSERP** | 125/Monat ✅ | $6,60 | app.scaleserp.com |
| 7 | **SearchAPI.io** | 100 einmalig ✅ | $4,00 | searchapi.io (50+ Engines!) |
| 8 | **Zenserp** | 50/Monat ✅ | $5,00 | app.zenserp.com |
| 9 | **Perplexity Sonar** | kein Free ❌ | $5-13 | perplexity.ai |
| 10 | **ValueSerp** | kein Dauer-Free ❌ | $2,00 | app.valueserp.com |

**Tot/verworfen (live):** Brave (Free-Tier gestrichen 20.08.2026!), Bing-API
(retired 11.08.2025), Yandex v1 (tot), ContextualWeb (DNS tot), 1NewsAPI (DNS tot),
Webshare (kein Such-API). NewsAPI.org: Dev-Key 100/Tag (nur Dev-Lizenz).

**UX-Empfehlung (Agent 3, rclone-Muster):** Interaktiver Wizard `sucher auth`:
(1) Menü aller Paid-Quellen mit Status [x]aktiv/[ ]aus/[!]Key fehlt per Pfeiltasten,
(2) Key-Eingabe via getpass (nie sichtbar), (3) SOFORTIGER Verbindungstest gegen
echten Endpoint (HTTP 200 → „OK: serper verbunden (10 Ergebnisse, 1,2s)"), bei
401/403 → „Key abgelehnt. Prüfe: <Key-URL>", (4) `sucher config` zeigt Status je
Quelle, (5) NO_KEY-Mechanik bei Suche: „Quelle serper ist aktiv, hat aber keinen
API-Key. Hol ihn kostenlos unter <URL> und gib ihn ein mit: sucher auth serper" —
immer den NÄCHSTEN Befehl mitzeigen, (6) `--list`, `--test-all`, `--remove`.
Keys nie in Logs/JSON-Exporte.

---

## Nächste Umsetzungs-Blöcke (priorisiert)

**Block 6 — key-freie Studien-Erweiterung (sucher_universal):** zenodo, datacite,
dblp, openaire (Graph-API!), + openreview/osf → je RED-Test+Commit
**Block 7 — key-freie Web-Erweiterung (sucher_web):** stackexchange (mit site=
  = 5+ Sub-Engines), wikiquote/wikinews/wikisource (MediaWiki-Adapter), openlibrary,
  internet-archive, github-repos → je RED-Test+Commit
**Block 8 — Key-optional (KEY_QUELLEN_MAP erweitern):** serper, youcom, zenrows,
  firecrawl, jina (Search), scaleserp → NO_KEY-Mechanik existiert, nur q-Funktion+Map
**Block 9 — `sucher auth`-Wizard:** getpass-Key-Eingabe + Live-Test (Agent-3-UX)
  + `sucher config`-Statuszeilen (aus UX-Laien-Block übernommen)
