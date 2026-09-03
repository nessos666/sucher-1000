#!/usr/bin/env python3
"""
SUCHER — WEB-BÜNDEL (Multi-Engine Web-Suche)
=============================================
Mehrere Web-Such-Quellen PARALLEL durchsuchen und aus allen sammeln.
Eingebaut nach Davids Korrektur (03.09.2026): NICHT eine Web-Suche,
sondern ein Bündel — ein Befehl durchsucht mehrere Engines.

Quellen (live getestet 03.09.2026):
  q_ddgs        — DuckDuckGo (Python-Lib, kein Key, blockt gelegentlich)
  q_bing_html   — Bing via HTML/RSS (kein Key, brauchbar)
  q_mojeek      — Mojeek (kein Key; Captcha-Block seit 03.09.2026 wird ERKANNT
                  und gemeldet — Source bleibt aktiv, Health cooldowned nach 3 Fails)
  q_wikipedia_web — Wikipedia DE+EN (MediaWiki-API, kein Key)
  q_tavily      — Tavily API (Env-Key TAVILY_API_KEY, karte-frei, 1000/Monat)
  q_exa         — Exa semantisch (Env-Key EXA_API_KEY, optional)
  q_serpapi     — Google-Rankings via SerpApi (Env-Key, optional)

Regeln:
- Key-freie Quellen laufen IMMER (Grundlast)
- Key-Quellen nur wenn Key in Env — fehlt → Meldung "übersprungen", kein Fehler
- Eine Quelle tot → andere liefern weiter + Fehler wird geloggt
- Komplett Hermes-unabhängig: nur stdlib + ddgs/requests
"""
import os
import re
import sys
import threading
import urllib.parse

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"}

# Lauf-Register für Web-Fehler (P6-B2) — analog sucher_universal._QUELLEN_FEHLER
_WEB_FEHLER: dict = {}
_WEB_FEHLER_LOCK = threading.Lock()

def _env(name):
    """Key aus Env lesen (auch ~/.hermes/.env als Fallback, wenn vorhanden)."""
    v = os.environ.get(name, "")
    if not v:
        try:
            p = os.path.expanduser("~/.hermes/.env")
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    for line in f:
                        if line.startswith(name + "="):
                            v = line.strip().split("=", 1)[1]
                            break
        except Exception:  # noqa: S110 - bewusster Fallback (optional)
            pass
    return (v or "").strip()

def _web_fehler_count(name):
    """Fehler-Zähler mit Alias-Normalisierung lesen (F4/F1-OpenCode).

    q_*-Funktionen loggen teils unter abweichendem Label ('Mojeek' vs.
    Register-Key 'mojeek'). Der Worker-Vergleich (F4) braucht DIESELBE
    Normalisierung wie der Health-Commit, sonst bleibt der Zähler 0 und
    eine kranke Quelle wird HEALTHY (Regression durch F4-Fix).
    """
    with _WEB_FEHLER_LOCK:
        if name in _WEB_FEHLER:
            return _WEB_FEHLER[name][1]
        low = name.lower()
        if low in _WEB_FEHLER:
            return _WEB_FEHLER[low][1]
        for label, info in _WEB_FEHLER.items():
            if label.lower().startswith(low) or low.startswith(label.lower()):
                return info[1]
        return 0


def _log_web_error(quelle, exc):
    """Fehler sichtbar machen (nie still schlucken)."""
    msg = str(exc)[:100]
    print(f"  ⚠ [{quelle}] Fehler: {msg}", file=sys.stderr)
    # P6-B2: Web-Fehler auch ins Lauf-Register (für Health-Anbindung)
    try:
        with _WEB_FEHLER_LOCK:
            alt = _WEB_FEHLER.get(quelle)
            if alt:
                _WEB_FEHLER[quelle] = (msg, alt[1] + 1)
            else:
                _WEB_FEHLER[quelle] = (msg, 1)
    except Exception:  # noqa: S110 - bewusster Fallback (optional)
        pass


def _jahr_aus_pubdate(pubdate):
    """Jahr aus RSS-pubDate extrahieren — F14 (OpenCode-Block5).

    pubDate-Formate: 'Wed, 03 Sep 2026 10:00:00 GMT' | '2026-09-03T10:00:00Z'
    Gibt int-Jahr oder None (kein Crash bei exotischen Formaten).
    """
    import html as _html
    import re as _re
    text = _html.unescape(pubdate or "")
    m = _re.search(r"\b(20\d{2})\b", text)
    if m:
        try:
            return int(m.group(1))
        except ValueError:  # noqa: S110 - bewusster Fallback (optional)
            pass
    return None


# ---------- Quelle 1: DuckDuckGo (ddgs, Lib + HTML-Fallback) ----------
def q_ddgs(query, n=8):
    """DDG-Suche: erst Python-Lib, bei Fehler HTML-Fallback (Shiraberu-Muster).

    Fallback nutzt html.duckduckgo.com/html/?o=json — läuft über net.get_text
    (8s-Cap + Block-Erkennung), parsebar als JSON-Objekte im HTML.
    """
    out = []
    # Weg 1: ddgs-Lib
    try:
        from ddgs import DDGS
        with DDGS() as d:
            for r in list(d.text(query, max_results=n)):
                out.append({"title": r.get("title", ""), "year": None,
                    "venue": "Web", "is_oa": True, "pdf": None, "doi": None,
                    "source": "ddgs", "url": r.get("href"),
                    "snippet": (r.get("body") or "")[:200]})
        if out:
            return out
    except Exception:  # noqa: S110 - Cache/RateLimit nie fatal
        pass  # → HTML-Fallback
    # F4 (OpenCode-Shiraberu): Teiltreffer der Lib nicht mit Fallback mischen
    out = []
    # Weg 2: HTML o=json (Shiraberu: html.duckduckgo.com/html/?o=json)
    try:
        import urllib.parse

        import net
        url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode(
            {"q": query, "o": "json", "v": "1"})
        text, err = net.get_text(url, timeout=12)
        if err:
            _log_web_error("ddgs", f"HTML-Fallback: {err}")
            return []
        for m in re.finditer(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                             text, re.DOTALL):
            href, raw_title = m.group(1), m.group(2)
            # DDG-Redirect-URLs auflösen (//duckduckgo.com/l/?uddg=<encoded>)
            um = re.search(r"uddg=([^&]+)", href)
            link = urllib.parse.unquote(um.group(1)) if um else href
            if not link.startswith("http"):
                continue
            title = re.sub(r"<[^>]+>", "", raw_title).strip()
            out.append({"title": title, "year": None, "venue": "Web",
                        "is_oa": True, "pdf": None, "doi": None,
                        "source": "ddgs", "url": link, "snippet": ""})
            if len(out) >= n:
                break
    except Exception as e:
        _log_web_error("ddgs", f"HTML-Fallback: {e}")
    return out

# ---------- Quelle 2: Bing via RSS (saubere echte URLs, keine Redirects) ----------
def q_bing_html(query, n=8):
    """Bing-Suche über das RSS-Format — liefert echte Ziel-URLs ohne /ck/a-Redirects.

    Getestet 03.09.2026: ?format=rss → <item> mit <link>=echte URL.
    F4 (OpenCode-Gesamt): läuft über net.get_text → 8s-Cap + Block-Erkennung.
    F5 (OpenCode-Block5): Titel/Link/Snippet durch html.unescape ziehen — das
    echte Bing-RSS liefert XML-Escapes (&amp;, &lt;).
    """
    import html as _html
    import urllib.parse
    try:
        import net
    except ImportError:
        _log_web_error("bing", "net fehlt")
        return []
    out = []
    url = "https://www.bing.com/search?" + urllib.parse.urlencode(
        {"q": query, "format": "rss"})
    xml, err = net.get_text(url, timeout=12)
    if err:
        _log_web_error("bing", f"Block/Fehler: {err}")
        return []
    for item in re.findall(r"<item>.*?</item>", xml, re.DOTALL):
        t = re.search(r"<title>(.*?)</title>", item, re.DOTALL)
        l = re.search(r"<link>(.*?)</link>", item, re.DOTALL)
        d = re.search(r"<description>(.*?)</description>", item, re.DOTALL)
        p = re.search(r"<pubDate>(.*?)</pubDate>", item, re.DOTALL)
        if not t or not l: continue
        title = _html.unescape(t.group(1)).strip()
        link = _html.unescape(l.group(1)).strip()
        if not title or not link.startswith("http"): continue
        snip = re.sub(r"<[^>]+>", "", _html.unescape(d.group(1)))[:200] if d else ""
        out.append({"title": title, "year": _jahr_aus_pubdate(
            p.group(1) if p else ""), "venue": "Web",
            "is_oa": True, "pdf": None, "doi": None,
            "source": "Bing", "url": link, "snippet": snip})
        if len(out) >= n: break
    return out

# ---------- Quelle 3: Tavily (Key optional) ----------
def q_tavily(query, n=8):
    key = _env("TAVILY_API_KEY")
    if not key:
        print("  ⚠ [tavily] übersprungen (kein TAVILY_API_KEY in Env)", file=sys.stderr)
        return []
    try:
        import net
    except ImportError:
        _log_web_error("tavily", "net fehlt")
        return []
    out = []
    j = net.post_json("https://api.tavily.com/search",
                      {"api_key": key, "query": query, "max_results": n,
                       "search_depth": "basic"}, timeout=12)
    if "_error" in j:
        _log_web_error("tavily", j["_error"])
        return []
    for r in j.get("results", []):
        out.append({"title": r.get("title", ""), "year": None, "venue": "Web",
            "is_oa": True, "pdf": None, "doi": None,
            "source": "Tavily", "url": r.get("url"),
            "snippet": (r.get("content") or "")[:250]})
    return out

# ---------- Quelle 4: SerpApi (Google-Rankings, Key optional) ----------
def q_serpapi(query, n=8):
    key = _env("SERPAPI_API_KEY") or _env("SERPER_API_KEY")
    if not key:
        print("  ⚠ [serpapi] übersprungen (kein SERPAPI_API_KEY in Env)", file=sys.stderr)
        return []
    try:
        import net
    except ImportError:
        _log_web_error("serpapi", "net fehlt")
        return []
    out = []
    url = "https://serpapi.com/search.json?" + urllib.parse.urlencode(
        {"q": query, "api_key": key, "num": n})
    j = net.get_json(url, timeout=12)
    if "_error" in j:
        _log_web_error("serpapi", j["_error"])
        return []
    for r in j.get("organic_results", [])[:n]:
        out.append({"title": r.get("title", ""), "year": None, "venue": "Web",
            "is_oa": True, "pdf": None, "doi": None,
            "source": "SerpApi", "url": r.get("link"),
            "snippet": (r.get("snippet") or "")[:200]})
    return out

# ---------- Quelle 5: Mojeek (key-frei, Captcha-sicher über net.get_text) ----------
def q_mojeek(query, n=8):
    """Mojeek-Suche. Nutzt net.get_text → Captcha/Botwall wird ERKANNT (nicht geparst).

    Mojeek blockt seit 03.09.2026 mit Captcha — dann kommt eine saubere Meldung
    statt Müll. Sobald Mojeek wieder freigibt, parst diese Funktion echte
    Ergebnisse (class="ob"-Links).
    """
    import urllib.parse
    try:
        import net
    except ImportError:
        _log_web_error("mojeek", "net fehlt")
        return []
    out = []
    url = "https://www.mojeek.com/search?" + urllib.parse.urlencode({"q": query})
    text, err = net.get_text(url, timeout=12)
    if err:
        _log_web_error("mojeek", f"Block/Fehler: {err}")
        return []
    # Ergebnis-Block: <h2><a class="ob" href="URL">Titel</a></h2> + <p class="s">Snippet</p>
    for m in re.finditer(r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', text, re.DOTALL):
        link, raw_title = m.group(1), m.group(2)
        title = re.sub(r"<[^>]+>", "", raw_title).strip()
        if not link.startswith("http") or not title:
            continue
        # Snippet: <p class="s"> nach dem h2
        snip_m = re.search(r'<p class="s">(.*?)</p>', text[m.end():], re.DOTALL)
        snippet = re.sub(r"<[^>]+>", "", snip_m.group(1)).strip()[:200] if snip_m else ""
        out.append({"title": title, "year": None, "venue": "Web", "is_oa": True,
                    "pdf": None, "doi": None, "source": "Mojeek", "url": link,
                    "snippet": snippet})
        if len(out) >= n:
            break
    if not out:
        # 0 Treffer OHNE Fehler möglich (leere Ergebnismenge) — kein Log nötig
        return []
    return out


# ---------- Quelle 6: Wikipedia DE+EN (key-frei, zuverlässig) ----------
def q_wikipedia_web(query, n=8):
    """Wikipedia-Suche über die offene MediaWiki-API — Deutsch + Englisch parallel.

    F4 (OpenCode-Gesamt): läuft über net.get_json → 8s-Cap + Retry.
    """
    try:
        import net
    except ImportError:
        _log_web_error("wikipedia_web", "net fehlt")
        return []
    out = []
    for lang in ("de", "en"):
        url = f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
            "action": "query", "list": "search", "srsearch": query,
            "format": "json", "srlimit": min(n, 10)})
        j = net.get_json(url, timeout=12)
        if "_error" in j:
            _log_web_error("wikipedia_web", f"{lang}: {j['_error']}")
            continue
        for r in j.get("query", {}).get("search", [])[:n]:
            t = r.get("title", "")
            if not t:
                continue
            page_url = f"https://{lang}.wikipedia.org/wiki/" + urllib.parse.quote(t.replace(" ", "_"))
            out.append({"title": t, "year": None, "venue": "Wikipedia",
                        "is_oa": True, "pdf": None, "doi": None,
                        "source": "Wikipedia", "url": page_url,
                        "snippet": re.sub(r"<[^>]+>", "", r.get("snippet", ""))[:200]})
    return out[:n]


# ---------- Quelle 7: Exa (semantisch, Key optional) ----------
def q_exa(query, n=8):
    """Exa-Suche (semantische Websuche). Key optional: EXA_API_KEY in Env."""
    key = _env("EXA_API_KEY")
    if not key:
        print("  ⚠ [exa] übersprungen (kein EXA_API_KEY in Env)", file=sys.stderr)
        return []
    try:
        import net
    except ImportError:
        _log_web_error("exa", "net fehlt")
        return []
    out = []
    j = net.post_json("https://api.exa.ai/search", {"query": query, "numResults": n},
                      timeout=12, headers={"x-api-key": key})
    if "_error" in j:
        _log_web_error("exa", j["_error"])
        return []
    for r in j.get("results", []):
        out.append({"title": r.get("title", ""), "year": None, "venue": "Web",
                    "is_oa": True, "pdf": None, "doi": None,
                    "source": "Exa", "url": r.get("url"),
                    "snippet": (r.get("text") or "")[:250]})
    return out


# ---------- Quelle 8: HackerNews (Algolia-API, key-frei, JSON) ----------
def q_hn(query, n=8):
    """HackerNews-Suche über die offizielle Algolia-API — KEIN Key nötig.

    Live verifiziert 03.09.2026 (Agent-2-Recherche): HTTP 200, 10.000 req/h.
    Ask-HN-Posts haben kein url-Feld → Item-Link (news.ycombinator.com).
    """
    try:
        import net
    except ImportError:
        _log_web_error("hn", "net fehlt")
        return []
    out = []
    url = "https://hn.algolia.com/api/v1/search?" + urllib.parse.urlencode(
        {"query": query, "hitsPerPage": n})
    j = net.get_json(url, timeout=12)
    if "_error" in j:
        _log_web_error("hn", j["_error"])
        return []
    for r in j.get("hits", [])[:n]:
        title = r.get("title") or ""
        if not title:
            continue
        link = r.get("url")
        if not link:  # Ask-HN/Show-HN ohne externe URL → Item-Seite
            oid = r.get("objectID")
            if not oid:  # F13 (OpenCode-Block5): ohne objectID kein brauchbarer Link
                continue
            link = f"https://news.ycombinator.com/item?id={oid}"
        # created_at: "2025-10-29T18:57:29Z" → Jahr
        year = None
        ca = r.get("created_at") or ""
        if len(ca) >= 4 and ca[:4].isdigit():
            year = int(ca[:4])
        pts = r.get("points")
        author = r.get("author") or ""
        snip = f"{pts} Punkte · {author}" if pts else (author or "")
        out.append({"title": title, "year": year, "venue": "HackerNews",
                    "is_oa": True, "pdf": None, "doi": None,
                    "source": "HackerNews", "url": link, "snippet": snip})
    return out


# ---------- Quelle 9: Google News RSS (key-frei) ----------
def q_google_news(query, n=8):
    """Google-News über den key-freien RSS-Feed (live 03.09.2026: HTTP 200).

    Item-Links sind Google-Redirect-Tokens (news.google.com/rss/articles/…)
    — bleiben als Link (RSS-Reader-Muster), der Browser löst sie auf.
    """
    import html as _html
    try:
        import net
    except ImportError:
        _log_web_error("google_news", "net fehlt")
        return []
    out = []
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": query, "hl": "de", "gl": "DE", "ceid": "DE:de"})
    xml, err = net.get_text(url, timeout=12)
    if err:
        _log_web_error("google_news", f"Block/Fehler: {err}")
        return []
    for item in re.findall(r"<item>.*?</item>", xml, re.DOTALL):
        t = re.search(r"<title>(.*?)</title>", item, re.DOTALL)
        l = re.search(r"<link>(.*?)</link>", item, re.DOTALL)
        d = re.search(r"<description>(.*?)</description>", item, re.DOTALL)
        p = re.search(r"<pubDate>(.*?)</pubDate>", item, re.DOTALL)
        if not t or not l:
            continue
        title = _html.unescape(t.group(1)).strip()
        link = _html.unescape(l.group(1)).strip()
        if not title or not link.startswith("http"):
            continue
        out.append({"title": title, "year": _jahr_aus_pubdate(
            p.group(1) if p else ""), "venue": "News",
                    "is_oa": True, "pdf": None, "doi": None,
                    "source": "GoogleNews", "url": link,
                    "snippet": _html.unescape(re.sub(r"<[^>]+>", "",
                        _html.unescape(d.group(1))))[:200] if d else ""})
        if len(out) >= n:
            break
    return out


# ---------- Quelle 10: Bing News RSS (key-frei, echte URL im apiclick-Param) ----------
def q_bing_news(query, n=8):
    """Bing-News über den key-freien RSS-Feed (live 03.09.2026: HTTP 200).

    Der item-Link ist ein apiclick-Wrapper — die ECHTE Ziel-URL steckt im
    url=-Parameter (dekodierbar, kein Extra-Request nötig).
    """
    import html as _html
    try:
        import net
    except ImportError:
        _log_web_error("bing_news", "net fehlt")
        return []
    out = []
    url = "https://www.bing.com/news/search?" + urllib.parse.urlencode(
        {"q": query, "format": "rss"})
    xml, err = net.get_text(url, timeout=12)
    if err:
        _log_web_error("bing_news", f"Block/Fehler: {err}")
        return []
    for item in re.findall(r"<item>.*?</item>", xml, re.DOTALL):
        t = re.search(r"<title>(.*?)</title>", item, re.DOTALL)
        l = re.search(r"<link>(.*?)</link>", item, re.DOTALL)
        d = re.search(r"<description>(.*?)</description>", item, re.DOTALL)
        p = re.search(r"<pubDate>(.*?)</pubDate>", item, re.DOTALL)
        if not t or not l:
            continue
        title = _html.unescape(t.group(1)).strip()
        raw_link = _html.unescape(l.group(1)).strip()
        # echte URL aus apiclick: url=https%3a%2f%2f… extrahieren
        link = raw_link
        um = re.search(r"[?&]url=([^&]+)", raw_link)
        if um:
            link = urllib.parse.unquote(um.group(1))
        if not title or not link.startswith("http"):
            continue
        out.append({"title": title, "year": _jahr_aus_pubdate(
            p.group(1) if p else ""), "venue": "News",
                    "is_oa": True, "pdf": None, "doi": None,
                    "source": "BingNews", "url": link,
                    "snippet": _html.unescape(re.sub(r"<[^>]+>", "",
                        _html.unescape(d.group(1))))[:200] if d else ""})
        if len(out) >= n:
            break
    return out


# ---------- Block 7: StackExchange / Wikis / OpenLibrary / Archive / GitHub ----------
def q_stackexchange(query, n=8, site="stackoverflow"):
    """StackExchange (StackOverflow + alle SE-Sites), key-frei JSON.

    Live verifiziert 03.09.2026: 300 Req/Tag anonym (10k mit kostenlosem
    App-Key). site= erlaubt Sub-Engines (superuser, serverfault, …).
    """
    import html as _html
    try:
        import net
    except ImportError:
        _log_web_error("stackexchange", "net fehlt")
        return []
    out = []
    url = ("https://api.stackexchange.com/2.3/search/advanced?"
           + urllib.parse.urlencode(
               {"site": site, "q": query, "pagesize": n,
                "order": "desc", "sort": "relevance"}))
    j = net.get_json(url, timeout=12)
    if "_error" in j:
        _log_web_error("stackexchange", j["_error"])
        return []
    for it in j.get("items", [])[:n]:
        title = it.get("title") or ""
        if not title:
            continue
        tags = ",".join(it.get("tags") or [])
        snip = f"Score {it.get('score')}"
        if tags:
            snip += f" · [{tags}]"
        out.append({"title": _html.unescape(title), "year": None,
                    "venue": "StackExchange", "is_oa": True, "pdf": None,
                    "doi": None, "source": "StackExchange",
                    "url": it.get("link"), "snippet": snip})
    return out


def q_wikis(query, n=8):
    """Wikiquote + Wikinews + Wikisource (DE+EN) via MediaWiki-API, key-frei.

    Live verifiziert 03.09.2026: alle 6 Projekte HTTP 200. Ein Adapter,
    mehrere Sub-Quellen — tote Projekte werden übersprungen (nicht fatal).
    """
    try:
        import net
    except ImportError:
        _log_web_error("wikis", "net fehlt")
        return []
    out = []
    projekte = [("de", "wikiquote"), ("en", "wikiquote"), ("de", "wikinews"),
                ("en", "wikinews"), ("de", "wikisource"), ("en", "wikisource")]
    for lang, proj in projekte:
        try:
            url = f"https://{lang}.{proj}.org/w/api.php?" + urllib.parse.urlencode({
                "action": "query", "list": "search", "srsearch": query,
                "srlimit": max(1, min(n, 5)), "format": "json"})
            j = net.get_json(url, timeout=12)
            if "_error" in j:
                _log_web_error("wikis", f"{lang}.{proj}: {j['_error']}")
                continue
            for r in j.get("query", {}).get("search", [])[:n]:
                t = r.get("title", "")
                if not t:
                    continue
                page_url = (f"https://{lang}.{proj}.org/wiki/"
                            + urllib.parse.quote(t.replace(" ", "_")))
                snip = re.sub(r"<[^>]+>", "", r.get("snippet", ""))[:150]
                out.append({"title": t, "year": None, "venue": f"{proj.capitalize()}",
                            "is_oa": True, "pdf": None, "doi": None,
                            "source": "Wikis", "url": page_url, "snippet": snip})
        except Exception as e:
            _log_web_error("wikis", f"{lang}.{proj}: {e}")
            continue
    return out


def q_openlibrary(query, n=8):
    """OpenLibrary (Bücher), key-frei JSON. Live: /search.json HTTP 200."""
    try:
        import net
    except ImportError:
        _log_web_error("openlibrary", "net fehlt")
        return []
    out = []
    url = "https://openlibrary.org/search.json?" + urllib.parse.urlencode(
        {"q": query, "limit": n,
         "fields": "title,author_name,first_publish_year,key"})
    j = net.get_json(url, timeout=12)
    if "_error" in j:
        _log_web_error("openlibrary", j["_error"])
        return []
    for d in j.get("docs", [])[:n]:
        title = d.get("title") or ""
        if not title:
            continue
        authors = d.get("author_name") or []
        author = authors[0] if authors else ""
        key = d.get("key") or ""
        link = f"https://openlibrary.org{key}" if key else None
        out.append({"title": title, "year": d.get("first_publish_year"),
                    "venue": "OpenLibrary", "is_oa": True, "pdf": None,
                    "doi": None, "source": "OpenLibrary",
                    "url": link, "snippet": author})
    return out


def q_archive(query, n=8):
    """Internet Archive advancedsearch (Solr-JSON), key-frei.

    Live verifiziert 03.09.2026: numFound 116k für 'linux'. Details-Seite:
    archive.org/details/<identifier>.
    """
    try:
        import net
    except ImportError:
        _log_web_error("archive", "net fehlt")
        return []
    out = []
    # fl[]= Felder via urlencode mit leeren Klammern
    url = ("https://archive.org/advancedsearch.php?q="
           + urllib.parse.quote(query)
           + "&fl%5B%5D=identifier&fl%5B%5D=title&fl%5B%5D=year"
             f"&rows={n}&output=json")
    j = net.get_json(url, timeout=12)
    if "_error" in j:
        _log_web_error("archive", j["_error"])
        return []
    for d in j.get("response", {}).get("docs", [])[:n]:
        title = d.get("title") or ""
        ident = d.get("identifier") or ""
        if not title or not ident:
            continue
        yr = d.get("year")
        try:
            yr = int(str(yr)[:4]) if yr else None
        except (TypeError, ValueError):
            yr = None
        out.append({"title": title, "year": yr, "venue": "Internet Archive",
                    "is_oa": True, "pdf": None, "doi": None,
                    "source": "Archive",
                    "url": f"https://archive.org/details/{ident}",
                    "snippet": f"Archive.org · {ident}"})
    return out


def q_github(query, n=8):
    """GitHub-Suche (Repos), key-frei JSON. Live: 10 Suchanfragen/min anonym."""
    try:
        import net
    except ImportError:
        _log_web_error("github", "net fehlt")
        return []
    out = []
    url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode(
        {"q": query, "per_page": n, "sort": "stars"})
    j = net.get_json(url, timeout=12)
    if "_error" in j:
        _log_web_error("github", j["_error"])
        return []
    for it in j.get("items", [])[:n]:
        name = it.get("full_name") or ""
        if not name:
            continue
        desc = (it.get("description") or "")[:150]
        snip = f"⭐ {it.get('stargazers_count')}"
        if desc:
            snip = desc + " · " + snip
        out.append({"title": name, "year": None, "venue": "GitHub",
                    "is_oa": True, "pdf": None, "doi": None,
                    "source": "GitHub", "url": it.get("html_url"),
                    "snippet": snip})
    return out


# ---------- Block 8: HuggingFace / Google Patents / Reddit-OAuth ----------
def q_huggingface(query, n=8):
    """HuggingFace Models+Datasets (ML-Models, key-frei JSON).

    Live verifiziert 03.09.2026: api/models?search=… HTTP 200. Kombiniert
    Models UND Datasets in einer Engine (David-Anforderung).
    """
    try:
        import net
    except ImportError:
        _log_web_error("huggingface", "net fehlt")
        return []
    out = []
    for korpus, label in (("models", "HF Model"), ("datasets", "HF Dataset")):
        url = f"https://huggingface.co/api/{korpus}?" + urllib.parse.urlencode(
            {"search": query, "limit": max(1, n // 2 + 1)})
        j = net.get_json(url, timeout=12)
        if "_error" in j:
            _log_web_error("huggingface", f"{korpus}: {j['_error']}")
            continue
        if not isinstance(j, list):
            continue
        for m in j:
            mid = m.get("id") or ""
            if not mid:
                continue
            dl = m.get("downloads") or 0
            likes = m.get("likes") or 0
            snip = f"⬇ {dl:,} · ♥ {likes}".replace(",", ".")
            if m.get("pipeline_tag"):
                snip += f" · {m['pipeline_tag']}"
            out.append({"title": mid, "year": None, "venue": label,
                        "is_oa": True, "pdf": None, "doi": None,
                        "source": "HuggingFace",
                        "url": f"https://huggingface.co/{mid}",
                        "snippet": snip})
            if len(out) >= n:
                break
    return out[:n]


def q_patents(query, n=8):
    """Google Patents über die XHR-JSON-API (key-frei, Google-Kleinod).

    Live verifiziert 03.09.2026: HTTP 200 + 124k Treffer für 'linux'. ABER:
    Google blockt bei mehreren Anfragen (503 "automated queries") — wie bei
    Mojeek/DDG. Health-Cooldown fängt das ab (Quelle pausiert, andere liefern).
    """
    import html as _html
    try:
        import net
    except ImportError:
        _log_web_error("patents", "net fehlt")
        return []
    out = []
    url = ("https://patents.google.com/xhr/query?url="
           + urllib.parse.quote(f"q={query}", safe="") + "&exp=")
    j = net.get_json(url, timeout=12)
    if "_error" in j:
        _log_web_error("patents", j["_error"])
        return []
    try:
        cluster = j["results"]["cluster"]
    except (KeyError, TypeError):
        return []
    count = 0
    for c in cluster:
        for r in (c.get("result") or []):
            p = r.get("patent") or {}
            title = p.get("title") or ""
            if not title:
                continue
            pid = r.get("id") or ""
            # id ist z. B. "patent/US9324234B2/en" — daraus die URL bauen,
            # ohne "patent/patent" oder "/en/en" zu duplizieren
            pid_clean = pid
            if pid_clean.startswith("patent/"):
                pid_clean = pid_clean.removeprefix("patent/")
            pid_clean = pid_clean.rstrip("/").removesuffix("/en")
            pid_clean = pid_clean.removesuffix("/en")
            year = None
            pd = p.get("publication_date") or p.get("grant_date") or ""
            if len(pd) >= 4 and pd[:4].isdigit():
                year = int(pd[:4])
            snip_bits = []
            if p.get("assignee"):
                snip_bits.append(str(p["assignee"]))
            if p.get("inventor"):
                snip_bits.append(str(p["inventor"]))
            out.append({"title": _html.unescape(title).strip(), "year": year,
                        "venue": "Google Patents", "is_oa": True, "pdf": None,
                        "doi": None, "source": "GooglePatents",
                        "url": f"https://patents.google.com/patent/{pid_clean}/en"
                               if pid_clean else None,
                        "snippet": " · ".join(snip_bits)[:150]})
            count += 1
            if count >= n:
                break
        if count >= n:
            break
    return out


def _reddit_token():
    """Reddit-OAuth-Token (client_credentials) holen — form-encoded + Basic.

    Respektiert net._transport (Test-Hook); ohne _transport echter Request.
    Gibt Token-String oder None (Fehler wird geloggt).
    """
    import base64
    import json as _json
    import urllib.error
    import urllib.parse
    import urllib.request
    try:
        import net
    except ImportError:
        return None
    cid = _env("REDDIT_CLIENT_ID")
    csec = _env("REDDIT_CLIENT_SECRET")
    if not cid or not csec:
        print("  ⚠ [reddit] übersprungen (kein REDDIT_CLIENT_ID/SECRET in Env — "
              "kostenlose App: reddit.com/prefs/apps)", file=sys.stderr)
        return None
    auth = base64.b64encode(f"{cid}:{csec}".encode()).decode()
    body = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    token_url = "https://www.reddit.com/api/v1/access_token"
    try:
        if net._transport is not None:  # Test-Hook
            raw = net._decode_body(net._transport.open(token_url, timeout=10))
        else:
            req = urllib.request.Request(
                token_url, data=body,
                headers={"User-Agent": UA["User-Agent"],
                         "Authorization": f"Basic {auth}",
                         "Content-Type": "application/x-www-form-urlencoded"})
            with urllib.request.urlopen(req, timeout=10) as r:  # nosec B310
                raw = r.read()
        j = _json.loads(raw.decode("utf-8", "replace"))
        tok = j.get("access_token")
        if not tok:
            _log_web_error("reddit", f"Token-Fehler: {str(j)[:80]}")
            return None
        return tok
    except Exception as e:
        _log_web_error("reddit", f"Token: {e}")
        return None


def q_reddit(query, n=8):
    """Reddit-Suche über die OFFIZIELLE OAuth-Data-API (Key-optional).

    Seit 2026 blockt der .json-Endpoint von Server-IPs (403) — offizieller
    Weg: kostenlose App-Registrierung (reddit.com/prefs/apps) → 100 QPM free.
    Keys: REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET in Env.
    """
    import html as _html
    try:
        import net
    except ImportError:
        _log_web_error("reddit", "net fehlt")
        return []
    tok = _reddit_token()
    if not tok:
        return []
    out = []
    url = "https://oauth.reddit.com/search?" + urllib.parse.urlencode(
        {"q": query, "limit": n, "sort": "relevance", "type": "link"})
    j = net.get_json(url, timeout=12, headers={
        "Authorization": f"Bearer {tok}", "User-Agent": UA["User-Agent"]})
    if "_error" in j:
        _log_web_error("reddit", j["_error"])
        return []
    try:
        children = j["data"]["children"]
    except (KeyError, TypeError):
        return []
    for ch in children[:n]:
        d = ch.get("data") or {}
        title = d.get("title") or ""
        if not title:
            continue
        perm = d.get("permalink") or ""
        link = f"https://www.reddit.com{perm}" if perm else d.get("url")
        import datetime as _dt
        year = None
        try:
            year = _dt.datetime.fromtimestamp(
                d.get("created_utc") or 0).year
        except (OverflowError, OSError, ValueError):
            pass
        snip = f"r/{d.get('subreddit')} · Score {d.get('score')}"
        out.append({"title": _html.unescape(title), "year": year,
                    "venue": "Reddit", "is_oa": True, "pdf": None,
                    "doi": None, "source": "Reddit",
                    "url": link, "snippet": snip})
    return out
def q_google_scholar(query, n=8):
    """Google Scholar (HTML-Parsing), key-frei — captcha-Gefahr bei Serien.

    Live verifiziert 03.09.2026: HTTP 200, 10 Treffer, 0 Captcha. Parser:
    gs_ri-Blöcke → h3 → <a href>Titel</a>, Jahr aus gs_a (letzte 4-stellige
    Zahl). Scholar blockt nach Dutzenden Requests → Health-Cooldown hilft.
    """
    import html as _html
    try:
        import net
    except ImportError:
        _log_web_error("google_scholar", "net fehlt")
        return []
    out = []
    url = "https://scholar.google.com/scholar?" + urllib.parse.urlencode(
        {"hl": "de", "q": query})
    text, err = net.get_text(url, timeout=12)
    if err:
        _log_web_error("google_scholar", f"Block/Fehler: {err}")
        return []
    blocks = re.findall(r'<div class="gs_ri">(.*?)(?=<div class="gs_r|</div>\s*</div>)',
                        text, re.DOTALL)
    if not blocks:  # Fallback: bis ans Ende
        blocks = re.findall(r'<div class="gs_ri">(.*)', text, re.DOTALL)[:1]
    for b in blocks[:n]:
        h3 = re.search(r"<h3[^>]*>(.*?)</h3>", b, re.DOTALL)
        if not h3:
            continue
        a = re.search(r'href="([^"]+)"[^>]*>(.*?)</a>', h3.group(1), re.DOTALL)
        if not a:
            continue
        raw_url = _html.unescape(a.group(1))
        title = re.sub(r"<[^>]+>", "", a.group(2))
        title = re.sub(r"\[(BUCH|B|CITATION|ZITATION|PDF)\]", "", title).strip()
        if not title:
            continue
        year = None
        gsa = re.search(r'<div class="gs_a">(.*?)</div>', b, re.DOTALL)
        if gsa:
            ym = re.search(r"\b(20\d{2})\b", gsa.group(1))
            if ym:
                year = int(ym.group(1))
        snip_m = re.search(r'<div class="gs_rs">(.*?)</div>', b, re.DOTALL)
        snip = re.sub(r"<[^>]+>", "", snip_m.group(1))[:200] if snip_m else ""
        out.append({"title": title, "year": year, "venue": "Google Scholar",
                    "is_oa": True, "pdf": None, "doi": None,
                    "source": "Scholar", "url": raw_url, "snippet": snip})
    return out


def q_autosuggest(query, n=8):
    """Google-Autosuggest (Suchvorschläge), key-frei JSON.

    Live verifiziert 03.09.2026: suggestqueries.google.com → JSON-Array
    [query, [suggestions…]]. Liefert Vorschläge als Treffer — nützlich für
    Themen-Erkundung/Keyword-Ideen.
    """
    import json as _json
    import net as _net
    out = []
    url = "https://suggestqueries.google.com/complete/search?" + urllib.parse.urlencode(
        {"client": "firefox", "q": query, "hl": "de"})
    # Google liefert charset=ISO-8859-1 — net.get_json dekodiert utf-8 (kaputt).
    # Daher Bytes direkt holen (respektiert Test-Hook) und latin-1 dekodieren.
    try:
        raw = _net._decode_body(_net._open(url, timeout=12))
        j = _json.loads(raw.decode("iso-8859-1"))
    except Exception as e:
        _log_web_error("autosuggest", str(e)[:80])
        return []
    if not isinstance(j, list) or len(j) < 2:
        return []
    for sugg in j[1][:n]:
        s = str(sugg)
        if not s:
            continue
        out.append({"title": s, "year": None, "venue": "Google Suggest",
                    "is_oa": True, "pdf": None, "doi": None,
                    "source": "GoogleSuggest",
                    "url": "https://www.google.com/search?q="
                           + urllib.parse.quote(s),
                    "snippet": f"Vorschlag zu: {query}"})
    return out


def q_knowledgegraph(query, n=8):
    """Google Knowledge Graph (semantische Entitäten), Key-optional.

    100.000 Read-Calls/Tag gratis (offiziell). Key: GOOGLE_KG_API_KEY.
    Ohne Key: übersprungen (NO_KEY-Mechanik).
    """
    key = _env("GOOGLE_KG_API_KEY")
    if not key:
        print("  ⚠ [knowledgegraph] übersprungen (kein GOOGLE_KG_API_KEY — "
              "kostenlos: console.cloud.google.com)", file=sys.stderr)
        return []
    try:
        import net
    except ImportError:
        _log_web_error("knowledgegraph", "net fehlt")
        return []
    out = []
    url = "https://kgsearch.googleapis.com/v1/entities:search?" + urllib.parse.urlencode(
        {"query": query, "key": key, "limit": n, "languages": "de"})
    j = net.get_json(url, timeout=12)
    if "_error" in j:
        _log_web_error("knowledgegraph", j["_error"])
        return []
    for el in j.get("itemListElement", [])[:n]:
        r = el.get("result") or {}
        name = r.get("name") or ""
        if not name:
            continue
        desc = r.get("description") or ""
        dd = (r.get("detailedDescription") or {}).get("url")
        types = r.get("@type") or []
        tstr = ",".join(types) if isinstance(types, list) else str(types)
        snip = " · ".join(x for x in [desc, tstr] if x)
        out.append({"title": name, "year": None, "venue": "Knowledge Graph",
                    "is_oa": True, "pdf": None, "doi": None,
                    "source": "KnowledgeGraph", "url": dd or None,
                    "snippet": snip})
    return out


def q_google_books(query, n=8):
    """Google Books API, Key-optional (anonym = 429 geteiltes Tagesquota).

    Key: GOOGLE_BOOKS_API_KEY (kostenloser Google-Cloud-Key, ~1000 Req/Tag).
    Ohne Key: übersprungen.
    """
    key = _env("GOOGLE_BOOKS_API_KEY")
    if not key:
        print("  ⚠ [google_books] übersprungen (kein GOOGLE_BOOKS_API_KEY — "
              "kostenlos: console.cloud.google.com)", file=sys.stderr)
        return []
    try:
        import net
    except ImportError:
        _log_web_error("google_books", "net fehlt")
        return []
    out = []
    url = "https://www.googleapis.com/books/v1/volumes?" + urllib.parse.urlencode(
        {"q": query, "key": key, "maxResults": min(n, 40)})
    j = net.get_json(url, timeout=12)
    if "_error" in j:
        _log_web_error("google_books", j["_error"])
        return []
    for it in j.get("items", [])[:n]:
        vi = it.get("volumeInfo") or {}
        title = vi.get("title") or ""
        if not title:
            continue
        yr = None
        pd = vi.get("publishedDate") or ""
        if len(pd) >= 4 and pd[:4].isdigit():
            yr = int(pd[:4])
        authors = vi.get("authors") or []
        author = ", ".join(authors[:2])
        out.append({"title": title, "year": yr, "venue": "Google Books",
                    "is_oa": True, "pdf": None, "doi": None,
                    "source": "GoogleBooks", "url": vi.get("infoLink"),
                    "snippet": author})
    return out


def q_youtube(query, n=8):
    """YouTube-Suche via InnerTube (Google-Kleinod, key-frei).

    Live verifiziert 03.09.2026: youtubei/v1/search HTTP 200, 20 Treffer.
    Inoffiziell (kein SLA) — Serienabrufe → 429/leer; Health-Cooldown hilft.
    Public-Web-Key wird von youtube.com mitgeliefert (stabil).
    """
    try:
        import net
    except ImportError:
        _log_web_error("youtube", "net fehlt")
        return []
    url = ("https://www.youtube.com/youtubei/v1/search?key="
           "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8")
    body = {"context": {"client": {"clientName": "WEB",
                                   "clientVersion": "2.20240101.00.00"}},
            "query": query}
    j = net.post_json(url, body, timeout=12)
    if "_error" in j:
        _log_web_error("youtube", j["_error"])
        return []
    out = []
    try:
        contents = j["contents"]["twoColumnSearchResultsRenderer"][
            "primaryContents"]["sectionListRenderer"]["contents"]
    except (KeyError, TypeError):
        return []
    for sec in contents:
        try:
            items = sec["itemSectionRenderer"]["contents"]
        except (KeyError, TypeError):
            continue
        for it in items:
            vr = it.get("videoRenderer")
            if not vr:
                continue
            vid = vr.get("videoId") or ""
            runs = (vr.get("title") or {}).get("runs") or []
            title = runs[0].get("text", "") if runs else ""
            if not title or not vid:
                continue
            owner = (vr.get("ownerText") or {}).get("runs") or []
            channel = owner[0].get("text", "") if owner else ""
            length = (vr.get("lengthText") or {}).get("simpleText") or ""
            snip = " · ".join(x for x in (length, channel) if x)
            out.append({"title": title, "year": None, "venue": "YouTube",
                        "is_oa": True, "pdf": None, "doi": None,
                        "source": "YouTube",
                        "url": f"https://www.youtube.com/watch?v={vid}",
                        "snippet": snip})
            if len(out) >= n:
                return out
    return out


KEY_QUELLEN_MAP = {"tavily": "TAVILY_API_KEY", "exa": "EXA_API_KEY",
                   "serpapi": "SERPAPI_API_KEY", "reddit": "REDDIT_CLIENT_ID",
                   "knowledgegraph": "GOOGLE_KG_API_KEY",
                   "google_books": "GOOGLE_BOOKS_API_KEY"}

# ---------- Register ----------
WEB = {"ddgs": q_ddgs, "bing": q_bing_html, "mojeek": q_mojeek,
       "wikipedia_web": q_wikipedia_web, "tavily": q_tavily, "exa": q_exa,
       "serpapi": q_serpapi, "hn": q_hn, "google_news": q_google_news,
       "bing_news": q_bing_news, "stackexchange": q_stackexchange,
       "wikis": q_wikis, "openlibrary": q_openlibrary, "archive": q_archive,
       "github": q_github, "huggingface": q_huggingface,
       "patents": q_patents, "reddit": q_reddit,
       "youtube": q_youtube, "google_scholar": q_google_scholar,
       "autosuggest": q_autosuggest, "knowledgegraph": q_knowledgegraph,
       "google_books": q_google_books}  # Block 7-10 (Agenten-Runden 2+3)

# P6-B3: Web-Quellen-Gewichte (für deterministische Sortierung — nicht
# completion-order der Threads). Bing hinten: Junk-Problem (Juli-Audit ⭐⭐).
# Block 5: HackerNews hoch (relevante Tech-Treffer), News-Feeds mittel.
# Block 7: StackExchange/GitHub hoch (Community-Qualität), Archive/Bücher mittel.
# Block 8: HuggingFace hoch (ML), Google Patents mittel, Reddit mittel.
_WEB_WEIGHT = {"ddgs": 1.0, "mojeek": 1.0, "wikipedia": 0.9, "tavily": 0.8,
               "exa": 0.8, "serpapi": 0.9, "bing": 0.4, "hackernews": 0.95,
               "googlenews": 0.7, "bingnews": 0.5, "stackexchange": 0.95,
               "wikis": 0.7, "openlibrary": 0.7, "archive": 0.7, "github": 0.9,
               "huggingface": 0.95, "googlepatents": 0.7, "reddit": 0.75,
               "youtube": 0.8, "scholar": 0.95, "googlesuggest": 0.3,
               "knowledgegraph": 0.85, "googlebooks": 0.7}


def _web_score_sort(results):
    """Web-Ergebnisse DETERMINISTISCH sortieren (P6-B3/F7-Muster).

    Vorher: completion-order der parallelen Threads (nondeterministisch!).
    Jetzt: Quellen-Gewicht + Titel als stabilem letzten Schlüssel.
    """
    def score(r):
        src = _WEB_WEIGHT.get((r.get("source") or "").lower(), 0.6)
        return src
    return sorted(results, key=lambda r: (score(r), (r.get("title") or "")[:80]),
                  reverse=True)

def search_web(query, n=8, only=None, timeout=30):
    """Alle Web-Quellen PARALLEL durchsuchen, aus allen sammeln.

    Parallele Ausführung → Gesamtzeit = langsamste Quelle, nicht Summe.
    Timeout HART: nach timeout-Sekunden wird abgebrochen, Teilergebnisse bleiben.
    Daemon-Threads (F1): keine non-daemon Worker → kein Prozess-Exit-Hang.
    """
    import queue as _queue
    import threading as _t
    import time as _time

    # P6-B2: Health-Registry auch für Web-Quellen — BROKEN (Cooldown) überspringen
    try:
        import health as _health
        _reg = _health.HealthRegistry()
    except Exception:
        _reg = None
    with _WEB_FEHLER_LOCK:
        _WEB_FEHLER.clear()  # frisches Lauf-Register (F5-Muster)

    active = dict(WEB)
    if only:
        if only in active:
            active = {only: active[only]}
        else:
            # Unbekannte Web-Quelle: Meldung statt still ALLE durchsuchen (F6)
            print(f"  ⚠ Unbekannte Web-Quelle '{only}' — verfügbar: {', '.join(active.keys())}",
                  file=sys.stderr)
            return []
    # BROKEN/NO_KEY-Quellen überspringen (P4-Mechanik auch für Web)
    if _reg is not None:
        uebersprungen = []
        for name in list(active.keys()):
            skip, grund = _reg.is_skippable(name)
            if skip:
                # Selbstheilung: NO_KEY + Key JETZT vorhanden → Quelle darf laufen
                if "NO_KEY" in grund and _env(KEY_QUELLEN_MAP.get(name, "")):
                    continue
                del active[name]
                uebersprungen.append((name, grund))
        for name, grund in uebersprungen:
            print(f"  ⏭ [{name}] übersprungen: {grund}", file=sys.stderr)
    # Key-Quellen ohne Env-Key: NICHT starten, als NO_KEY markieren (kein ok=True!)
    if _reg is not None:
        for name in list(active.keys()):
            envvar = KEY_QUELLEN_MAP.get(name)
            if envvar and not _env(envvar):
                del active[name]
                _reg.mark_no_key(name)
                print(f"  ⚠ [{name}] übersprungen (kein {envvar} in Env)", file=sys.stderr)
        try:
            _reg.save()  # auch wenn gleich 0 aktive bleiben — NO_KEY muss persistieren
        except Exception:  # noqa: S110 - bewusster Fallback (optional)
            pass
    if not active:
        return []
    results, seen = [], set()
    ergebnis_q = _queue.Queue()
    threads = []
    quellen_mit_fehler = set()  # F4/F15: Worker-gemeldete Fehler (eigener Lauf)
    for name, fn in active.items():
        def _arbeite(_n=name, _f=fn):
            # TTL-Cache zuerst (F5: kein throttle bei Cache-Hit — kein Netz!)
            try:
                import cache as _cache
                treffer = _cache.get("web", _n, query, n)
                if treffer is not None:
                    # F1: Cache-Treffer = KEIN Health-Signal → Status 'cached'
                    ergebnis_q.put((_n, "cached", treffer))
                    return
            except Exception:  # noqa: S110 - Cache/RateLimit nie fatal
                pass
            # Rate-Limit (Shiraberu): pro Quelle drosseln (nur bei echtem Request)
            try:
                import ratelimit
                ratelimit.throttle(_n)
            except Exception:  # noqa: S110 - Cache/RateLimit nie fatal
                pass
            # F4 (OpenCode-Block5): Fehler-Zählerstand VOR dem Aufruf merken —
            # Worker meldet seinen EIGENEN Fehlerstatus (nicht das globale
            # Register, das verwaiste Threads aus Vorläufen verfälschen können).
            try:
                vorher = _web_fehler_count(_n)
                ergebnis = list(_f(query, n))
                nachher = _web_fehler_count(_n)
                hatte_fehler = nachher > vorher
                # Cache füllen (nur echte Ergebnisse, keine Fehler/leer-Timeout)
                if ergebnis and not hatte_fehler:
                    try:
                        import cache as _cache
                        _cache.put("web", _n, query, n, ergebnis)
                    except Exception:  # noqa: S110 - Cache/RateLimit nie fatal
                        pass
                ergebnis_q.put((_n, "ok" if not hatte_fehler else "err_lokal",
                                ergebnis))
            except Exception as e:
                _log_web_error(_n, e)
                ergebnis_q.put((_n, "err", []))
        t = _t.Thread(target=_arbeite, daemon=True)
        t.start(); threads.append(t)

    t_start = _time.monotonic()
    offen = len(threads)
    quellen_mit_treffern = set()
    quellen_abgeschlossen = set()  # F3-Codex: nur GEMELDETE Quellen healthen
    while offen > 0 and _time.monotonic() - t_start < timeout:
        try:
            name, status, payload = ergebnis_q.get(timeout=0.2)
            offen -= 1
            if status != "cached":
                quellen_abgeschlossen.add(name)  # F1: Cache ≠ abgeschlossen
            if payload and status in ("ok", "err_lokal"):
                # err_lokal (F4/F15): Treffer vorhanden, ABER Quelle meldete
                # Fehler → Treffer zählen, für Health trotzdem als Fehler
                quellen_mit_treffern.add(name)
            if status == "err_lokal":
                quellen_mit_fehler.add(name)
            elif status == "err":
                quellen_mit_fehler.add(name)
            for it in payload:
                key = ((it.get("title") or "") + (it.get("url") or "")).lower()[:90]
                if key and key not in seen:
                    seen.add(key); results.append(it)
        except _queue.Empty:
            continue  # noch keine Antwort — weiter auf Budget warten

    # Verwaiste Threads NICHT joinen — daemon, sterben mit Prozess (F1)

    # P6-B2: Health pro Quelle genau EINMAL committen (aggregiert, nicht pro Thread)
    # F4 (OpenCode-Block5): Entscheidung basiert auf WORKER-gemeldetem Status
    # (quellen_mit_fehler), nicht auf dem globalen Register-Snapshot — verwaiste
    # Threads aus Vorläufen können das Register nach clear() verfälschen.
    if _reg is not None:
        try:
            with _WEB_FEHLER_LOCK:
                fehler_register = dict(_WEB_FEHLER)

            def _alias_fehler(name):
                """Fehler-Eintrag zu einem Register-Key finden (F1-Fix).

                q_*-Funktionen können unter leicht abweichendem Label loggen
                ('Mojeek' vs. Key 'mojeek', 'Wikipedia-de' vs. 'wikipedia').
                Normalisierung: exakt, dann lower, dann Präfix.
                """
                if name in fehler_register:
                    return fehler_register[name]
                low = name.lower()
                if low in fehler_register:
                    return fehler_register[low]
                for label, info in fehler_register.items():
                    if label.lower().startswith(low) or low.startswith(label.lower()):
                        return info
                return None

            # F3 (Codex-Gesamt): NUR abgeschlossene Quellen committen — Quellen,
            # die das Budget rissen (nie geantwortet), werden NICHT als HEALTHY
            # verbucht (Timeout darf nicht als Gesundheit zählen).
            for name in list(active.keys()):
                if name not in quellen_abgeschlossen:
                    continue  # Timeout — nicht bewerten
                fehlerinfo = _alias_fehler(name)
                fehlertext = fehlerinfo[0] if fehlerinfo else ""
                if name in quellen_mit_fehler:
                    # F15: auch mit (Teil-)Treffern als Fehler verbuchen — sonst
                    # bliebe eine konstant halbkaputte Quelle HEALTHY.
                    _reg.record_outcome(name, ok=False, error=fehlertext)
                else:
                    _reg.record_outcome(name, ok=True)
            _reg.save()
        except Exception:  # noqa: S110 - bewusster Fallback (optional)
            pass
    # P6-B3: deterministisch sortieren (Gewicht + Titel) statt completion-order
    return _web_score_sort(results)

def list_web():
    for name, fn in WEB.items():
        needs = "Key" if name in ("tavily", "serpapi", "exa") else "frei"
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
