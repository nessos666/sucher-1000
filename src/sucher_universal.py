#!/usr/bin/env python3
"""
SUCHER — UNIVERSAL (Ausbaustufe 1000+)
Universelle Suche für JEDES Thema/Kontext. Mehrere Modi:
  --modus studien   : nur wissenschaftliche Quellen (OpenAlex/DOAJ/Crossref/EuropePMC/SemanticScholar)
  --modus universal : Studien + Allgemeinwissen (Wikipedia/Wikidata) — breiteste Suche
  --modus alle      : alle verfügbaren Quellen (ohne Einschränkung)
  --quelle NAME     : nur eine bestimmte Quelle
  --list           : verfügbare Quellen anzeigen
Nutzung: python3 sucher_universal.py "suchbegriff" [anzahl] [--modus M] [--quelle Q]
"""
import urllib.request, urllib.parse, json, time, sys, os, re

UA = {"User-Agent": "Sucher1000/ (mailto:kontakt@sucher1000.example)"}
OUTDIR = "sucher_ergebnisse"
os.makedirs(OUTDIR, exist_ok=True)

def http_json(url, timeout=25, retries=2):
    for i in range(retries+1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < retries:
                time.sleep(5); continue
            return {"_error": f"HTTP {e.code}"}
        except Exception as e:
            if i < retries:
                time.sleep(3); continue
            return {"_error": str(e)[:80]}
    return {"_error": "timeout"}

# ---------- Wissenschaftliche Quellen ----------
def q_openalex(query, n=8):
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode({
        "search": query, "per-page": n, "sort": "relevance_score:desc"})
    j = http_json(url)
    if "_error" in j: return []
    out=[]
    for w in j.get("results", []):
        oa = w.get("open_access") or {}
        pl = w.get("primary_location") or {}
        src = pl.get("source") or {}
        out.append({"title": w.get("title") or "", "year": w.get("publication_year"),
            "venue": src.get("display_name") if src else "",
            "is_oa": oa.get("is_oa", False),
            "pdf": oa.get("oa_url") or (w.get("best_oa_location") or {}).get("pdf_url"),
            "doi": w.get("doi"), "source": "OpenAlex", "url": w.get("doi")})
    return out

def q_crossref(query, n=8):
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode(
        {"query": query, "rows": n, "select": "title,DOI,issued,container-title,URL"})
    j = http_json(url)
    if "_error" in j: return []
    out=[]
    for w in j.get("message", {}).get("items", []):
        yr = (w.get("issued",{}).get("date-parts",[[None]])[0][0])
        out.append({"title": (w.get("title") or [""])[0], "year": yr,
            "venue": (w.get("container-title") or [""])[0] if w.get("container-title") else "",
            "is_oa": False, "pdf": None, "doi": w.get("DOI"), "source": "Crossref", "url": w.get("URL")})
    return out

def q_doaj(query, n=8):
    url = "https://doaj.org/api/search/articles/" + urllib.parse.quote(query) + f"?pageSize={n}&page=1"
    j = http_json(url)
    if "_error" in j: return []
    out=[]
    for r in j.get("results", []):
        b=r.get("bibjson",{}); loc=r.get("bibjson",{}).get("link",[{}])
        url_pdf=next((l.get("url") for l in loc if l.get("type")=="fulltext"), None)
        out.append({"title": b.get("title",""), "year": b.get("year"),
            "venue": b.get("journal",{}).get("title","") if b.get("journal") else "",
            "is_oa": True, "pdf": url_pdf, "doi": b.get("identifier",[{}])[0].get("id") if b.get("identifier") else "",
            "source": "DOAJ", "url": url_pdf})
    return out

def q_europepmc(query, n=8):
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urllib.parse.urlencode(
        {"query": query, "format":"json", "pageSize": n, "resultType":"core"})
    j = http_json(url)
    if "_error" in j: return []
    out=[]
    for r in j.get("resultList",{}).get("result",[]):
        url_pdf=None
        for t in r.get("fullTextUrlList",{}).get("fullTextUrl",[]) if r.get("fullTextUrlList") else []:
            if t.get("availability")=="Open access": url_pdf=t.get("url"); break
        out.append({"title": r.get("title",""), "year": r.get("pubYear"),
            "venue": r.get("journalInfo",{}).get("journal",{}).get("title","") if r.get("journalInfo") else "",
            "is_oa": r.get("isOpenAccess", False), "pdf": url_pdf, "doi": r.get("doi"),
            "source": "EuropePMC", "pmcid": r.get("pmcid"),
            "url": f"https://pmc.ncbi.nlm.nih.gov/articles/{r['pmcid']}/" if r.get("pmcid") else None})
    return out

def q_semanticscholar(query, n=8):
    url = "https://api.semanticscholar.org/graph/v1/paper/search?" + urllib.parse.urlencode(
        {"query": query, "limit": n, "fields":"title,year,venue,openAccessPdf,externalIds,url"})
    j = http_json(url)
    if "_error" in j or not j.get("data"): return []
    out=[]
    for r in j["data"]:
        oa=r.get("openAccessPdf") or {}
        out.append({"title": r.get("title",""), "year": r.get("year"),
            "venue": r.get("venue",""), "is_oa": bool(oa), "pdf": oa.get("url"),
            "doi": (r.get("externalIds") or {}).get("DOI"), "source":"SemanticScholar", "url": r.get("url")})
    return out

# ---------- Allgemein-Wissen Quellen (universal) ----------
def q_wikipedia(query, n=6):
    """Allgemeine Web-/Wissenssuche (deutsch + englisch)."""
    out=[]
    for lang in ("de","en"):
        url = f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
            {"action":"opensearch","search":query,"limit":n,"format":"json"})
        j = http_json(url)
        if "_error" in j or not isinstance(j, list): continue
        titles = j[1] if len(j) > 1 else []
        descs  = j[2] if len(j) > 2 else []
        urls   = j[3] if len(j) > 3 else []
        for i,t in enumerate(titles):
            out.append({"title": t, "year": None, "venue": f"Wikipedia({lang.upper()})",
                "is_oa": True, "pdf": None, "doi": None, "source": "Wikipedia",
                "url": urls[i] if i < len(urls) else None,
                "snippet": descs[i] if i < len(descs) else ""})
    return out

# ---------- Preprint-Quellen (neu) ----------
def q_arxiv(query, n=6):
    """arXiv-API (Atom-Feed): Preprints Physik/ML/quantitativ."""
    url = "http://export.arxiv.org/api/query?" + urllib.parse.urlencode(
        {"search_query": f"all:{query}", "max_results": n, "sortBy":"relevance"})
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            xml = r.read().decode()
    except Exception:
        return []
    out = []
    for e in re.findall(r"<entry>.*?</entry>", xml, re.S):
        t = re.search(r"<title>(.*?)</title>", e, re.S)
        link = re.search(r'<link href="(http[^"]*)"', e)
        summ = re.search(r"<summary>(.*?)</summary>", e, re.S)
        out.append({
            "title": re.sub(r"\s+"," ",t.group(1).strip()) if t else "",
            "year": None, "venue": "arXiv", "is_oa": True,
            "pdf": None, "doi": None, "source": "arXiv",
            "url": link.group(1) if link else None,
            "snippet": re.sub(r"\s+"," ",summ.group(1))[:150] if summ else ""})
    return out

def q_biorxiv(query, n=6):
    """bioRxiv/medRxiv-API: biomedizinische Preprints."""
    # bioRxiv Such-API
    url = f"https://api.biorxiv.org/details/biorxiv/0_.{int(time.time())}_{n}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent":"Sucher1000/ (mailto:kontakt@sucher1000.example)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            j = json.load(r)
    except Exception:
        return []
    out=[]
    for p in j.get("collection", [])[:n]:
        out.append({
            "title": p.get("title",""), "year": (p.get("date") or "")[:4] or None,
            "venue":"bioRxiv", "is_oa":True, "pdf":None, "doi":p.get("doi"),
            "source":"bioRxiv", "url":f"https://doi.org/{p.get('doi')}",
            "snippet": f"{p.get('authors','')}"})
    return out

# ---------- Quellen-Register ----------
SCI = {"openalex": q_openalex, "crossref": q_crossref, "doaj": q_doaj,
       "europepmc": q_europepmc, "semanticscholar": q_semanticscholar,
       "arxiv": q_arxiv, "biorxiv": q_biorxiv}
GENERAL = {"wikipedia": q_wikipedia}

def resolve_sources(mode):
    """Gibt die aktiven Quellen je Modus zurück."""
    if mode == "studien":   return dict(SCI)
    if mode == "universal": return {**SCI, **GENERAL}
    if mode == "alle":      return {**SCI, **GENERAL}
    return dict(SCI)  # default

def search(query, n=8, mode="universal", only=None):
    active = resolve_sources(mode)
    if only and only in active: active = {only: active[only]}
    seen, results = set(), []
    for name, fn in active.items():
        try:
            for it in fn(query, n):
                key = ((it.get("title") or "") + (it.get("url") or "")).lower()[:90]
                if key and key not in seen:
                    seen.add(key); results.append(it)
        except Exception:
            pass
    return results

def pretty(results, mode):
    print(f"\n→ {len(results)} Treffer (Modus: {mode}, dedupl.)\n")
    for r in results:
        oa = "✅ FREI" if r.get("is_oa") else ("🟡 PDF?" if r.get("pdf") else "🔒 geschützt")
        lbl = r.get("title") or "(ohne Titel)"
        print(f"[{oa}] [{r.get('source')}] {lbl}  ({r.get('year') or ''})")
        if r.get("venue"): print(f"      {r['venue']}")
        if r.get("snippet"): print(f"      {r['snippet']}")
        if r.get("doi"): print(f"      DOI: {r['doi']}")
        if r.get("pdf"): print(f"      PDF: {r['pdf']}")
        if r.get("pmcid"): print(f"      PMC: https://pmc.ncbi.nlm.nih.gov/articles/{r['pmcid']}/")
        if r.get("url") and r.get("source")!="OpenAlex": print(f"      Link: {r['url']}")
        print()

def main():
    argv = sys.argv[1:]
    query = None
    n = 8
    mode = "universal"
    only = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--modus" and i+1 < len(argv):
            mode = argv[i+1]; i += 2
        elif a == "--quelle" and i+1 < len(argv):
            only = argv[i+1]; i += 2
        elif a == "--list":
            print("Verfügbare Quellen:\n  WISSENSCHAFT:", ", ".join(SCI.keys()))
            print("  ALLGEMEIN:", ", ".join(GENERAL.keys()))
            print("Modi: studien | universal | alle")
            return
        else:
            if query is None:
                query = a
            elif isinstance(a, str) and a.isdigit() and n == 8:
                n = int(a)
            i += 1
    if query is None:
        query = "somatic experiencing trauma"
    res = search(query, n, mode, only)
    pretty(res, mode)
    fn = os.path.join(OUTDIR, "ergebnis_" + re.sub(r'\W+','_', query)[:40] + ".json")
    with open(fn, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(f"→ JSON gespeichert: {fn}")

if __name__ == "__main__":
    main()