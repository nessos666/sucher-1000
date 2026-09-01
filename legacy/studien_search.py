#!/usr/bin/env python3
"""
STUDIEN-SEARCH-TOOL (Git-Projekt) — David 2026
Robuste Multi-Quellen-Studiensuche: OpenAlex, Crossref, DOAJ, Europe PMC, Semantic Scholar.
Ersetzt die instabile DuckDuckGo-Suche durch direkte wissenschaftliche APIs mit Fallback.
"""
import urllib.request, urllib.parse, json, time, sys, os, re

UA = {"User-Agent": "Sucher1000/ (mailto:kontakt@sucher1000.example)"}

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

# ---------- Quellen ----------
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
        out.append({
            "title": w.get("title") or "",
            "year": w.get("publication_year"),
            "venue": src.get("display_name") if src else "",
            "is_oa": oa.get("is_oa", False),
            "pdf": oa.get("oa_url") or (w.get("best_oa_location") or {}).get("pdf_url"),
            "doi": w.get("doi"),
            "source": "OpenAlex"})
    return out

def q_crossref(query, n=8):
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode({
        "query": query, "rows": n, "select": "title,DOI,issued,container-title,name,URL"})
    j = http_json(url)
    if "_error" in j: return []
    out=[]
    for w in j.get("message", {}).get("items", []):
        yr = (w.get("issued",{}).get("date-parts",[[None]])[0][0])
        out.append({"title": (w.get("title") or [""])[0], "year": yr,
            "venue": (w.get("container-title") or [""])[0] if w.get("container-title") else "",
            "is_oa": False, "pdf": None, "doi": w.get("DOI"), "source": "Crossref"})
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
            "source": "DOAJ"})
    return out

def q_europepmc(query, n=8):
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urllib.parse.urlencode(
        {"query": query, "format":"json", "pageSize": n, "resultType":"core"})
    j = http_json(url)
    if "_error" in j: return []
    out=[]
    for r in j.get("resultList",{}).get("result",[]):
        out.append({"title": r.get("title",""), "year": r.get("pubYear"),
            "venue": r.get("journalInfo",{}).get("journal",{}).get("title","") if r.get("journalInfo") else "",
            "is_oa": r.get("isOpenAccess", False),
            "pdf": r.get("fullTextUrlList",{}).get("fullTextUrl",[{}])[0].get("url") if r.get("fullTextUrlList") else None,
            "doi": r.get("doi"), "source": "EuropePMC", "pmcid": r.get("pmcid")})
    return out

def q_semanticscholar(query, n=8):
    url = "https://api.semanticscholar.org/graph/v1/paper/search?" + urllib.parse.urlencode(
        {"query": query, "limit": n, "fields":"title,year,venue,openAccessPdf,externalIds"})
    j = http_json(url)
    if "_error" in j or not j.get("data"): return []
    out=[]
    for r in j["data"]:
        oa=r.get("openAccessPdf") or {}
        out.append({"title": r.get("title",""), "year": r.get("year"),
            "venue": r.get("venue",""), "is_oa": bool(oa),
            "pdf": oa.get("url"), "doi": (r.get("externalIds") or {}).get("DOI"), "source":"SemanticScholar"})
    return out

# ---------- Orchestrator ----------
SOURCES = {"openalex": q_openalex, "crossref": q_crossref, "doaj": q_doaj,
           "europepmc": q_europepmc, "semanticscholar": q_semanticscholar}

def search(query, n=8, skip=()):
    seen, results = set(), []
    for name, fn in SOURCES.items():
        if name in skip: continue
        try:
            for it in fn(query, n):
                key = (it.get("title") or "").lower()[:60]
                if key and key not in seen:
                    seen.add(key); results.append(it)
        except Exception as e:
            pass
    return results

def pretty(results):
    print(f"→ {len(results)} Treffer (dedupl.)\n")
    for r in results:
        oa = "✅ FREI" if r.get("is_oa") else ("🟡 PDF?" if r.get("pdf") else "🔒 geschützt")
        print(f"[{oa}] [{r.get('source')}] {r.get('title')}  ({r.get('year')})")
        if r.get("venue"): print(f"      {r['venue']}")
        if r.get("doi"): print(f"      DOI: {r['doi']}")
        if r.get("pdf"): print(f"      PDF: {r['pdf']}")
        if r.get("pmcid"): print(f"      PMC: https://pmc.ncbi.nlm.nih.gov/articles/{r['pmcid']}/")
        print()

if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv)>1 else "vegetotherapy body psychotherapy"
    n = int(sys.argv[2]) if len(sys.argv)>2 else 8
    res = search(q, n)
    pretty(res)
    # JSON-Speicherung
    fn = "result_" + re.sub(r'\W+','_', q)[:40] + ".json"
    with open(fn, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(f"→ JSON gespeichert: {fn}")