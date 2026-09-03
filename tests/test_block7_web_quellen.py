"""Block 7 — 5 neue Web-Quellen (Agenten-Wissen Runde 2, live verifiziert).

q_stackexchange  StackExchange (StackOverflow + Sites, key-frei JSON, 300/Tag)
q_wikis          Wikiquote+Wikinews+Wikisource DE+EN (MediaWiki, key-frei)
q_openlibrary    OpenLibrary (Bücher, key-frei JSON)
q_archive        Internet Archive advancedsearch (Solr-JSON, key-frei)
q_github         GitHub-Suche Repos+Issues (key-frei JSON, 10/min)

RED zuerst: Funktionen existieren noch nicht.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import sucher_web as web

# --- Echte StackExchange-Antwort ---
SE_JSON = {"quota_remaining": 295, "items": [
    {"title": "Simplest async/await example possible in Python",
     "link": "https://stackoverflow.com/questions/50757497/simplest", "score": 303,
     "is_answered": True, "tags": ["python", "async"]}]}

# --- Echte OpenLibrary-Antwort ---
OL_JSON = {"numFound": 4365, "docs": [
    {"title": "Linux For Dummies", "first_publish_year": 1999,
     "author_name": ["Dee-Ann LeBlanc"], "key": "/books/OL1"}]}

# --- Echte Internet-Archive-Antwort (Solr) ---
IA_JSON = {"response": {"numFound": 116698, "docs": [
    {"identifier": "linuxbook", "title": "Linux Book", "year": "2001"}]}}

# --- Echte GitHub-Antwort ---
GH_JSON = {"total_count": 670664, "items": [
    {"full_name": "0xAX/linux-insides", "html_url": "https://github.com/0xAX/linux-insides",
     "description": "A book-in-progress about the Linux kernel", "stargazers_count": 32990}]}

# --- Echte MediaWiki-Antwort (Wikiquote/Wikinews/Wikisource) ---
MW_JSON = {"query": {"search": [{"title": "Linux", "snippet": "<span>Linux</span> Zitat"}]}}


@pytest.fixture
def route_net(fake_transport, monkeypatch):
    """net._transport auf FakeTransport setzen + Proxy-Fallback AUS (Isolation)."""
    import net
    monkeypatch.setattr(net, "_transport", fake_transport)
    monkeypatch.setattr(net, "_try_proxy", lambda *a, **k: None)
    monkeypatch.setattr(net, "_try_proxy_post", lambda *a, **k: None)
    return fake_transport


# ---------- q_stackexchange ----------

def test_stackexchange_parst_json(route_net):
    route_net.route("https://api.stackexchange.com/2.3/search/advanced",
                    route_net.ok_json(SE_JSON))
    out = web.q_stackexchange("python async", 5)
    assert len(out) == 1
    assert "async/await" in out[0]["title"]
    assert out[0]["url"].startswith("https://stackoverflow.com")
    assert out[0]["source"] == "StackExchange"
    assert "303" in (out[0]["snippet"] or ""), "Score im Snippet"


def test_stackexchange_fehler_leer(route_net, capsys):
    route_net.route("https://api.stackexchange.com/2.3/search/advanced",
                    exc=route_net.err(429))
    out = web.q_stackexchange("python", 5)
    assert out == []
    assert "stackexchange" in capsys.readouterr().err.lower()


# ---------- q_wikis (Wikiquote/Wikinews/Wikisource DE+EN) ----------

def test_wikis_parst_mediawiki(route_net):
    """Adapter ruft mehrere Projekte; Treffer mit Projekt-URL."""
    for proj in ("de.wikiquote.org", "en.wikiquote.org", "de.wikinews.org",
                 "en.wikinews.org", "de.wikisource.org", "en.wikisource.org"):
        route_net.route(f"https://{proj}/w/api.php", route_net.ok_json(MW_JSON))
    out = web.q_wikis("linux", 3)
    assert len(out) == 6, f"6 Projekte je 1 Treffer: {len(out)}"
    urls = [r["url"] for r in out]
    assert any("wikiquote.org" in u for u in urls)
    assert any("wikinews.org" in u for u in urls)
    assert any("wikisource.org" in u for u in urls)
    assert out[0]["source"] == "Wikis"
    assert out[0]["title"] == "Linux"


def test_wikis_fehler_ueberspringt_projekt(route_net):
    """Ein totes Projekt crasht nicht — andere liefern weiter."""
    import net
    # alle Projekte routen, aber de.wikiquote wirft
    for proj in ("de.wikiquote.org", "en.wikiquote.org", "de.wikinews.org"):
        route_net.route(f"https://{proj}/w/api.php", route_net.ok_json(MW_JSON))
    route_net.route("https://en.wikinews.org/w/api.php", exc=route_net.err(500))
    out = web.q_wikis("linux", 3)
    assert len(out) >= 2, f"2 gesunde Projekte müssen liefern: {len(out)}"


# ---------- q_openlibrary ----------

def test_openlibrary_parst_json(route_net):
    route_net.route("https://openlibrary.org/search.json",
                    route_net.ok_json(OL_JSON))
    out = web.q_openlibrary("linux", 5)
    assert len(out) == 1
    assert out[0]["title"] == "Linux For Dummies"
    assert out[0]["year"] == 1999
    assert "openlibrary.org" in out[0]["url"]
    assert out[0]["source"] == "OpenLibrary"


def test_openlibrary_fehler_leer(route_net, capsys):
    route_net.route("https://openlibrary.org/search.json", exc=route_net.err(503))
    out = web.q_openlibrary("x", 5)
    assert out == []
    assert "openlibrary" in capsys.readouterr().err.lower()


# ---------- q_archive (Internet Archive) ----------

def test_archive_parst_solr(route_net):
    route_net.route("https://archive.org/advancedsearch.php",
                    route_net.ok_json(IA_JSON))
    out = web.q_archive("linux", 5)
    assert len(out) == 1
    assert out[0]["title"] == "Linux Book"
    assert "archive.org/details/linuxbook" in out[0]["url"], \
        f"Details-URL aus identifier: {out[0]['url']}"
    assert out[0]["source"] == "Archive"


def test_archive_fehler_leer(route_net, capsys):
    route_net.route("https://archive.org/advancedsearch.php",
                    exc=route_net.err(403))
    out = web.q_archive("x", 5)
    assert out == []
    assert "archive" in capsys.readouterr().err.lower()


# ---------- q_github ----------

def test_github_parst_repos(route_net):
    route_net.route("https://api.github.com/search/repositories",
                    route_net.ok_json(GH_JSON))
    out = web.q_github("linux python", 5)
    assert len(out) == 1
    assert out[0]["title"] == "0xAX/linux-insides"
    assert out[0]["url"] == "https://github.com/0xAX/linux-insides"
    assert out[0]["source"] == "GitHub"
    assert "32990" in (out[0]["snippet"] or ""), "Stars im Snippet"


def test_github_fehler_leer(route_net, capsys):
    route_net.route("https://api.github.com/search/repositories",
                    exc=route_net.err(403))  # Rate-Limit
    out = web.q_github("linux", 5)
    assert out == []
    assert "github" in capsys.readouterr().err.lower()


# ---------- Register ----------

def test_block7_quellen_im_web_register():
    for key in ("stackexchange", "wikis", "openlibrary", "archive", "github"):
        assert key in web.WEB, f"{key} fehlt im WEB-Register"
        assert key not in web.KEY_QUELLEN_MAP, f"{key} ist key-frei"
        assert callable(web.WEB[key])
