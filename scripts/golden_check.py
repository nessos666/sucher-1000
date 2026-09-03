#!/usr/bin/env python3
"""SUCHER-1000 — Golden-Query-Check (Retrieval-Qualität ehrlich messen).

Lädt data/golden_queries.json, führt jede Query live aus und prüft:
Erscheint eine erwartete Domain in den Top-n Treffern?
→ Hit-Rate + Precision als reproduzierbares Qualitätsmaß (Agent-3).

Nutzung:
  .venv/bin/python scripts/golden_check.py            # alle Queries
  .venv/bin/python scripts/golden_check.py "trauma"   # nur passende (Filter)
  .venv/bin/python scripts/golden_check.py --json     # Report als JSON

Ergebnis wird nach docs/audits/golden_check_YYYYMMDD.md geschrieben.
"""
import json
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))

GOLDEN_FILE = BASE / "data" / "golden_queries.json"
REPORT_DIR = BASE / "docs" / "audits"


def _url_domain(url):
    """Beste Domain aus URL extrahieren (www. + Pfad entfernen)."""
    if not url:
        return ""
    u = str(url).lower()
    for prefix in ("https://", "http://"):
        if u.startswith(prefix):
            u = u[len(prefix):]
            break
    u = u.split("/")[0].split("?")[0]
    u = u.removeprefix("www.")
    return u


def _treffer_domains(results, n):
    """Domain-Liste der Top-n Treffer (url/pdf) + DOI-Liste (für Verlags-Match)."""
    domains, dois = [], []
    for r in results[:n]:
        for feld in ("url", "pdf"):
            d = _url_domain(r.get(feld))
            if d and d not in domains:
                domains.append(d)
        doi = r.get("doi")
        if doi and doi not in dois:
            dois.append(doi)
    return domains, dois


# DOI-Prefix → Verlag-Familie (Treffer über Aggregatoren liefern die
# Publisher-Domain nicht, aber der DOI verrät den Verlag)
_DOI_VERLAG = {
    "10.1016": "sciencedirect.com", "10.1016/j": "sciencedirect.com",
    "10.1007": "springer.com", "10.1186": "springer.com", "10.1038": "nature.com",
    "10.3390": "mdpi.com", "10.48550": "arxiv.org", "10.48550/arxiv": "arxiv.org",
    "10.48550/arXiv": "arxiv.org", "10.1109": "ieee.org",
    "10.1145": "acm.org", "10.1371": "plos.org", "10.1037": "apa.org",
    "10.1024": "hogrefe.com", "10.1080": "tandfonline.com",
    "10.1111": "wiley.com", "10.2196": "jmir.org", "10.1002": "wiley.com",
}


def _doi_verlag(doi):
    """DOI → Verlag-Domain (wenn Prefix bekannt)."""
    if not doi:
        return ""
    d = str(doi).lower()
    for prefix, verlag in sorted(_DOI_VERLAG.items(), key=lambda x: -len(x[0])):
        if d.startswith(prefix.lower()):
            return verlag
    return ""


def _erwartung_getroffen(erwartete, domains, dois):
    """Erwartete Domain getroffen? via URL-Domain ODER DOI-Verlag-Familie."""
    treffer = []
    # URL-Domains + Verlag aus DOIs als Kandidaten sammeln
    kandidaten = list(domains)
    for doi in dois:
        v = _doi_verlag(doi)
        if v:
            kandidaten.append(v)
    for e in erwartete:
        e = e.lower().lstrip("www.")
        elabels = e.split(".")
        hit = False
        for d in kandidaten:
            dlabels = d.lower().split(".")
            if d == e:
                hit = True
                break
            for k in (2, 3):
                if (len(elabels) >= k and len(dlabels) >= k
                        and elabels[-k:] == dlabels[-k:]):
                    hit = True
                    break
            if hit:
                break
        treffer.append((e, hit))
    return treffer


def _suche(query, modus, n):
    """Echte Suche über die Fanouts (gleicher Pfad wie CLI)."""
    import sucher_universal as su
    import sucher_web as sw
    try:
        import health
        reg = health.HealthRegistry()
    except Exception:
        reg = None
    if modus == "web":
        return sw.search_web(query, n, health_reg=reg)
    if modus == "alle":
        a = su.search(query, n, mode="universal", health_reg=reg)
        b = sw.search_web(query, n, health_reg=reg)
        seen, out = set(), []
        for r in list(a) + list(b):
            url = (r.get("url") or "").lower()
            if url and url in seen:
                continue
            if url:
                seen.add(url)
            out.append(r)
        return out
    return su.search(query, n, mode=modus, health_reg=reg)


def main():
    only_filter = None
    as_json = "--json" in sys.argv
    for a in sys.argv[1:]:
        if a != "--json":
            only_filter = a.lower()

    data = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))
    queries = data["queries"]
    if only_filter:
        queries = [q for q in queries if only_filter in q["query"].lower()
                   or only_filter in (q.get("thema") or "").lower()
                   or only_filter in q["modus"]]

    if not queries:
        print(f"Keine Golden-Query passt auf '{only_filter}' — verfügbar:")
        for q in data["queries"]:
            print(f"  [{q['modus']:7s}] {q['query']}  ({q.get('thema','')})")
        sys.exit(1)

    print(f"Golden-Query-Check: {len(queries)} Queries\n")
    ergebnisse = []
    t0 = time.time()
    for q in queries:
        query, modus, n = q["query"], q["modus"], q["n"]
        erwartet = q.get("erwartete_domains", [])
        thema = q.get("thema", "")
        print(f"🔍 [{modus}] {query}  ({thema})")
        t1 = time.time()
        try:
            res = _suche(query, modus, n)
        except Exception as e:
            print(f"  ✗ Suche crashte: {e}")
            ergebnisse.append({"query": query, "modus": modus, "ok": False,
                               "fehler": str(e)})
            continue
        dt = time.time() - t1
        domains, dois = _treffer_domains(res, n)
        treffer = _erwartung_getroffen(erwartet, domains, dois)
        getroffen = [e for e, hit in treffer if hit]
        quote = f"{len(getroffen)}/{len(erwartet)}" if erwartet else "n/a"
        status = "✅" if (not erwartet or getroffen) else "⚠️"
        print(f"  {status} {len(res)} Treffer ({dt:.1f}s) — erwartet {quote}")
        for e, hit in treffer:
            print(f"      {'✓' if hit else '✗'} {e}")
        if not erwartet:
            print(f"      Top-Domains: {', '.join(domains[:5]) or '(keine)'}")
        ergebnisse.append({"query": query, "modus": modus, "thema": thema,
                           "treffer_gesamt": len(res), "ok": bool(getroffen)
                           or not erwartet,
                           "erwartet_getroffen": getroffen,
                           "top_domains": domains[:8],
                           "latenz_s": round(dt, 1)})
        print()
    gesamt = time.time() - t0

    ok_zahl = sum(1 for e in ergebnisse if e.get("ok"))
    print(f"═══ Zusammenfassung: {ok_zahl}/{len(ergebnisse)} erfüllt "
          f"({gesamt:.0f}s gesamt) ═══")

    if as_json:
        print(json.dumps(ergebnisse, ensure_ascii=False, indent=2))

    # Report schreiben — gefilterte Läufe überschreiben den Haupt-Report nicht
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    suffix = f"_{only_filter}" if only_filter else ""
    fn = REPORT_DIR / f"golden_check_{datetime.now():%Y%m%d}{suffix}.md"
    lines = [f"# Golden-Query-Check — {datetime.now():%Y-%m-%d %H:%M}\n",
             f"\n{ok_zahl}/{len(ergebnisse)} Queries erfüllten die Erwartung "
             f"({gesamt:.0f}s).\n", "\n| Query | Modus | Treffer | Erwartung | Status |\n",
             "|---|---|---:|---|---|---|\n"]
    for e in ergebnisse:
        st = "✅" if e.get("ok") else "⚠️"
        exp = ", ".join(e.get("erwartet_getroffen", [])) or "—"
        lines.append(f"| {e['query']} | {e['modus']} | {e.get('treffer_gesamt','-')} "
                     f"| {exp} | {st} |\n")
    fn.write_text("".join(lines), encoding="utf-8")
    print(f"\n→ Report: {fn}")


if __name__ == "__main__":
    main()
