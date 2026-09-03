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
    except Exception:
        pass  # → HTML-Fallback
    # Weg 2: HTML o=json (Shiraberu: html.duckduckgo.com/html/?o=json)
    try:
        import net
        import urllib.parse
        url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode(
            {"q": query, "o": "json", "v": "1"})
        text, err = net.get_text(url, timeout=12)
        if err:
            _log_web_error("ddgs", f"HTML-Fallback: {err}")
            return []
        for m in re.finditer(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                             text, re.S):
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
    """
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
        if not t or not l: continue
        title = t.group(1).strip()
        link = l.group(1).strip()
        if not title or not link.startswith("http"): continue
        out.append({"title": title, "year": None, "venue": "Web",
            "is_oa": True, "pdf": None, "doi": None,
            "source": "Bing", "url": link,
            "snippet": re.sub(r"<[^>]+>", "", d.group(1))[:200] if d else ""})
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
            "source": "Google", "url": r.get("link"),
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
        _log_web_error("wikipedia", "net fehlt")
        return []
    out = []
    for lang in ("de", "en"):
        url = f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
            "action": "query", "list": "search", "srsearch": query,
            "format": "json", "srlimit": min(n, 10)})
        j = net.get_json(url, timeout=12)
        if "_error" in j:
            _log_web_error("wikipedia", f"{lang}: {j['_error']}")
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


# Key-Quellen → Env-Variablen (für NO_KEY-Handling)
KEY_QUELLEN_MAP = {"tavily": "TAVILY_API_KEY", "exa": "EXA_API_KEY",
                   "serpapi": "SERPAPI_API_KEY"}

# ---------- Register ----------
WEB = {"ddgs": q_ddgs, "bing": q_bing_html, "mojeek": q_mojeek,
       "wikipedia": q_wikipedia_web, "tavily": q_tavily, "exa": q_exa,
       "serpapi": q_serpapi}

# P6-B3: Web-Quellen-Gewichte (für deterministische Sortierung — nicht
# completion-order der Threads). Bing hinten: Junk-Problem (Juli-Audit ⭐⭐).
_WEB_WEIGHT = {"ddgs": 1.0, "mojeek": 1.0, "wikipedia": 0.9, "tavily": 0.8,
               "exa": 0.8, "serpapi": 0.9, "bing": 0.4}


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
    for name, fn in active.items():
        def _arbeite(_n=name, _f=fn):
            # Rate-Limit (Shiraberu): pro Quelle drosseln
            try:
                import ratelimit
                ratelimit.throttle(_n)
            except Exception:
                pass
            # TTL-Cache: gleiche (Quelle, Query, n) binnen 15 Min aus Cache
            try:
                import cache as _cache
                treffer = _cache.get(_n, query, n)
                if treffer is not None:
                    ergebnis_q.put((_n, treffer))
                    return
            except Exception:
                pass
            try:
                ergebnis = list(_f(query, n))
                # Cache füllen (nur echte Ergebnisse)
                if ergebnis:
                    try:
                        import cache as _cache
                        _cache.put(_n, query, n, ergebnis)
                    except Exception:
                        pass
                ergebnis_q.put((_n, ergebnis))
            except Exception as e:
                _log_web_error(_n, e)
                ergebnis_q.put((_n, []))
        t = _t.Thread(target=_arbeite, daemon=True)
        t.start(); threads.append(t)

    t_start = _time.monotonic()
    offen = len(threads)
    quellen_mit_treffern = set()
    quellen_abgeschlossen = set()  # F3-Codex: nur GEMELDETE Quellen healthen
    while offen > 0 and _time.monotonic() - t_start < timeout:
        try:
            name, payload = ergebnis_q.get(timeout=0.2)
            offen -= 1
            quellen_abgeschlossen.add(name)
            if payload:
                quellen_mit_treffern.add(name)
            for it in payload:
                key = ((it.get("title") or "") + (it.get("url") or "")).lower()[:90]
                if key and key not in seen:
                    seen.add(key); results.append(it)
        except _queue.Empty:
            continue  # noch keine Antwort — weiter auf Budget warten

    # Verwaiste Threads NICHT joinen — daemon, sterben mit Prozess (F1)

    # P6-B2: Health pro Quelle genau EINMAL committen (aggregiert, nicht pro Thread)
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
                hat_fehler = fehlerinfo is not None and fehlerinfo[1] > 0
                fehlertext = fehlerinfo[0] if fehlerinfo else ""
                if hat_fehler and name not in quellen_mit_treffern:
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
