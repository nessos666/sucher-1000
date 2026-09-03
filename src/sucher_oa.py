#!/usr/bin/env python3
"""
SUCHER-OA — Open-Access-Resolver für Sucher
Findet für eine DOI/URL die KOSTENLOSE, ladbare Version VOOR dem Download,
vermeidet so reCAPTCHA/Cloudflare-Blocks an der Wurzel.

Quellen-Kaskade (kostenlos, alle live getestet):
  1. Unpaywall (best_oa_location / oa_locations) — Docker öffentlich
  2. OpenAlex (best_oa_location, enthält Unpaywall-Spiegel)
  3. Europe PMC (Open-Access-URLs)

Nutzung:
  python3 sucher_oa.py <doi-ou-URL>          # → druckt beste freie PDF-URL + Quelle
  python3 sucher_oa.py --list                # Quellen anzeigen
"""
import urllib.request, urllib.parse, json, sys, re

EMAIL = "kontakt@sucher1000.example"
UA = {"User-Agent": f"Sucher1000/ (mailto:{EMAIL})"}

def http_json(url, timeout=25):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except Exception as e:
        return {"_error": str(e)[:80]}

def extract_doi(query):
    """Extrahiert DOI aus URL oder Original-DOI.

    F7 (OpenCode-Gesamt): schneidet Query-Parameter (?/&/#) ab — vorher blieb
    '?foo=bar' am DOI hängen, wenn die URL Parameter hatte.
    """
    if not query: return None
    m = re.search(r"10\.\d{4,9}/[^\s\"']+", query)
    if not m:
        return query if query.startswith("10.") else None
    doi = m.group(0)
    # Trailing Query/Fragment abschneiden: ?foo &bar #baz
    for sep in ("?", "&", "#"):
        if sep in doi:
            doi = doi.split(sep)[0]
    return doi.rstrip(".,)")

def q_unpaywall(doi):
    """Unpaywall: beste freie PDF-URL."""
    url = f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi)}?email={EMAIL}"
    j = http_json(url)
    if "_error" in j or not j.get("is_oa"): return []
    out = []
    loc = j.get("best_oa_location") or {}
    if loc.get("url_for_pdf"): out.append(("Unpaywall-PDF", loc["url_for_pdf"]))
    elif loc.get("url"): out.append(("Unpaywall-Landing", loc["url"]))
    # Rückfall: PMC/EuropePMC direkt = meist leicht ladbar
    for l in j.get("oa_locations", []):
        u = l.get("url_for_pdf") or l.get("url") or ""
        if "pmc.ncbi" in u or "europepmc" in u:
            out.append(("Unpaywall-PMC", u)); break
    return out

def q_openalex(doi):
    """OpenAlex: beste Open-Access-Location (Unpaywall-Spiegel)."""
    url = f"https://api.openalex.org/works/https://doi.org/{urllib.parse.quote(doi)}"
    j = http_json(url)
    if "_error" in j or not j.get("open_access", {}).get("is_oa"): return []
    out = []
    best = j.get("best_oa_location") or {}
    if best.get("pdf_url"): out.append(("OpenAlex-PDF", best["pdf_url"]))
    if best.get("landing_page_url"): out.append(("OpenAlex-Landing", best["landing_page_url"]))
    return out

def q_europepmc(doi):
    """Europe PMC: Open-Access-Volltext-Links."""
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urllib.parse.urlencode(
        {"query": "DOI:"+doi, "format":"json", "pageSize":1, "resultType":"core"})
    j = http_json(url)
    if "_error" in j: return []
    res = (j.get("resultList") or {}).get("result") or []
    if not res: return []
    r = res[0]
    out = []
    ft = r.get("fullTextUrlList", {}).get("fullTextUrl", []) or []
    for t in ft:
        if t.get("availability") == "Open access" and t.get("url"):
            out.append(("EuropePMC-OA", t["url"]))
    if not out and r.get("pmcid"):
        out.append(("EuropePMC-PMCID", f"https://pmc.ncbi.nlm.nih.gov/articles/{r['pmcid']}/"))
    return out

SOURCES = {"unpaywall": q_unpaywall, "openalex": q_openalex, "europepmc": q_europepmc}

def resolve(query, prefer=("unpaywall","openalex","europepmc")):
    doi = extract_doi(query)
    if not doi:
        return [], None
    results = []
    for name in prefer:
        fn = SOURCES.get(name)
        if not fn: continue
        try:
            results.extend(fn(doi))
        except Exception:
            pass
    return results, doi

def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    if sys.argv[1] == "--list":
        print("Verfügbare OA-Quellen:", ", ".join(SOURCES.keys()))
        return
    query = sys.argv[1]
    results, doi = resolve(query)
    if not doi:
        print("Keine DOI in:", query); sys.exit(1)
    print(f"DOI: {doi}")
    if not results:
        print("→ Keine freie Version gefunden (ggf. geschützt) 🔒")
    else:
        print("→ Freie/nachladbare Versionen:")
        for src, url in results:
            print(f"   [{src}] {url}")

if __name__ == "__main__":
    main()