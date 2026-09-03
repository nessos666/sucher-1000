#!/usr/bin/env python3
"""
SUCHER — WEB-BÜNDEL (Multi-Engine Web-Suche)
=============================================
Mehrere Web-Such-Quellen PARALLEL durchsuchen und aus allen sammeln.
Eingebaut nach Davids Korrektur (03.09.2026): NICHT eine Web-Suche,
sondern ein Bündel — ein Befehl durchsucht mehrere Engines.

Quellen (live getestet 03.09.2026):
  q_ddgs        — DuckDuckGo (Python-Lib, kein Key, blockt gelegentlich)
  q_bing_html   — Bing via HTML (kein Key, brauchbar)
  q_tavily      — Tavily API (Env-Key TAVILY_API_KEY, karte-frei, 1000/Monat)
  q_mojeek      — Mojeek (AUS: Botwall seit 03.09.2026, nur 5KB Blockseite)
  q_serpapi     — Google-Rankings via SerpApi (Env-Key, optional)

Regeln:
- Key-freie Quellen laufen IMMER (Grundlast)
- Key-Quellen nur wenn Key in Env — fehlt → Meldung "übersprungen", kein Fehler
- Eine Quelle tot → andere liefern weiter + Fehler wird geloggt
- Komplett Hermes-unabhängig: nur stdlib + ddgs/requests
"""
import os, re, sys, json, time
from concurrent.futures import ThreadPoolExecutor, as_completed

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"}

def _env(name):
    """Key aus Env lesen (auch ~/.hermes/.env als Fallback, wenn vorhanden)."""
    v = os.environ.get(name, "")
    if not v:
        try:
            p = os.path.expanduser("~/.hermes/.env")
            if os.path.exists(p):
                for line in open(p, encoding="utf-8"):
                    if line.startswith(name + "="):
                        v = line.strip().split("=", 1)[1]; break
        except Exception:
            pass
    return (v or "").strip()

def _log_web_error(quelle, exc):
    """Fehler sichtbar machen (nie still schlucken)."""
    msg = str(exc)[:100]
    print(f"  ⚠ [{quelle}] Fehler: {msg}", file=sys.stderr)

# ---------- Quelle 1: DuckDuckGo (ddgs) ----------
def q_ddgs(query, n=8):
    try:
        from ddgs import DDGS
    except ImportError:
        _log_web_error("ddgs", "Lib fehlt: pip install ddgs")
        return []
    out = []
    try:
        with DDGS() as d:
            for r in list(d.text(query, max_results=n)):
                out.append({"title": r.get("title", ""), "year": None,
                    "venue": "Web", "is_oa": True, "pdf": None, "doi": None,
                    "source": "ddgs", "url": r.get("href"),
                    "snippet": (r.get("body") or "")[:200]})
    except Exception as e:
        _log_web_error("ddgs", e)
    return out

# ---------- Quelle 2: Bing via RSS (saubere echte URLs, keine Redirects) ----------
def q_bing_html(query, n=8):
    """Bing-Suche über das RSS-Format — liefert echte Ziel-URLs ohne /ck/a-Redirects.

    Getestet 03.09.2026: ?format=rss → <item> mit <link>=echte URL.
    """
    import urllib.request, urllib.parse
    out = []
    try:
        url = "https://www.bing.com/search?" + urllib.parse.urlencode(
            {"q": query, "format": "rss"})
        req = urllib.request.Request(url, headers=UA)
        xml = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore")
        for item in re.findall(r"<item>.*?</item>", xml, re.S):
            t = re.search(r"<title>(.*?)</title>", item, re.S)
            l = re.search(r"<link>(.*?)</link>", item, re.S)
            d = re.search(r"<description>(.*?)</description>", item, re.S)
            if not t or not l: continue
            title = t.group(1).strip()
            link = l.group(1).strip()
            if not title or not link.startswith("http"): continue
            out.append({"title": title, "year": None, "venue": "Web",
                "is_oa": True, "pdf": None, "doi": None,
                "source": "Bing", "url": link,
                "snippet": re.sub(r"<[^>]+>", "", d.group(1))[:200] if d else ""})
            if len(out) >= n: break
    except Exception as e:
        _log_web_error("Bing", e)
    return out

# ---------- Quelle 3: Tavily (Key optional) ----------
def q_tavily(query, n=8):
    key = _env("TAVILY_API_KEY")
    if not key:
        print("  ⚠ [Tavily] übersprungen (kein TAVILY_API_KEY in Env)")
        return []
    out = []
    try:
        import urllib.request, json as _json
        body = _json.dumps({"api_key": key, "query": query,
            "max_results": n, "search_depth": "basic"}).encode()
        req = urllib.request.Request("https://api.tavily.com/search",
            data=body, headers={"Content-Type": "application/json"})
        j = _json.loads(urllib.request.urlopen(req, timeout=20).read())
        for r in j.get("results", []):
            out.append({"title": r.get("title", ""), "year": None, "venue": "Web",
                "is_oa": True, "pdf": None, "doi": None,
                "source": "Tavily", "url": r.get("url"),
                "snippet": (r.get("content") or "")[:250]})
    except Exception as e:
        _log_web_error("Tavily", e)
    return out

# ---------- Quelle 4: SerpApi (Google-Rankings, Key optional) ----------
def q_serpapi(query, n=8):
    key = _env("SERPAPI_API_KEY") or _env("SERPER_API_KEY")
    if not key:
        print("  ⚠ [SerpApi] übersprungen (kein SERPAPI_API_KEY in Env)")
        return []
    out = []
    try:
        import urllib.request, urllib.parse, json as _json
        url = "https://serpapi.com/search.json?" + urllib.parse.urlencode(
            {"q": query, "api_key": key, "num": n})
        req = urllib.request.Request(url, headers=UA)
        j = _json.loads(urllib.request.urlopen(req, timeout=20).read())
        for r in j.get("organic_results", [])[:n]:
            out.append({"title": r.get("title", ""), "year": None, "venue": "Web",
                "is_oa": True, "pdf": None, "doi": None,
                "source": "Google", "url": r.get("link"),
                "snippet": (r.get("snippet") or "")[:200]})
    except Exception as e:
        _log_web_error("SerpApi", e)
    return out

# ---------- Register ----------
WEB = {"ddgs": q_ddgs, "bing": q_bing_html, "tavily": q_tavily, "serpapi": q_serpapi}

def search_web(query, n=8, only=None, timeout=30):
    """Alle Web-Quellen PARALLEL durchsuchen, aus allen sammeln.

    Parallele Ausführung → Gesamtzeit = langsamste Quelle, nicht Summe.
    """
    active = dict(WEB)
    if only and only in active:
        active = {only: active[only]}
    results, seen = [], set()
    with ThreadPoolExecutor(max_workers=len(active)) as ex:
        futs = {ex.submit(fn, query, n): name for name, fn in active.items()}
        try:
            for fut in as_completed(futs, timeout=timeout):
                try:
                    for it in fut.result():
                        key = ((it.get("title") or "") + (it.get("url") or "")).lower()[:90]
                        if key and key not in seen:
                            seen.add(key); results.append(it)
                except Exception as e:
                    _log_web_error(futs[fut], e)
        except Exception as e:
            _log_web_error("Parallel", f"Timeout nach {timeout}s: {e}")
    return results

def list_web():
    for name, fn in WEB.items():
        needs = "Key" if name in ("tavily", "serpapi") else "frei"
        print(f"  {name:10s} ({needs})")


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "IT Systemhaus München"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    print(f"Web-Bündel-Suche: {q!r} (n={n})\n")
    res = search_web(q, n)
    print(f"\n→ {len(res)} Treffer aus {len(set(r['source'] for r in res))} Quellen\n")
    for r in res:
        print(f"[{r['source']}] {r['title'][:70]}")
        if r.get("url"): print(f"      {r['url'][:90]}")
