"""Block 5 — 3 neue key-freie Quellen (Agenten-Wissen 03.09.2026, live verifiziert).

q_hn          HackerNews-Algolia-API  (JSON, kein Key, 10k req/h)
q_google_news Google-News-RSS          (RSS, kein Key, Redirect-Token)
q_bing_news   Bing-News-RSS            (RSS, kein Key, echte URL im apiclick-Param)

RED zuerst: Funktionen existieren noch nicht → ImportError/AttributeError.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import sucher_web as web

# --- Echte HN-Algolia-Antwort (Struktur live geprüft 03.09.2026) ---
HN_JSON = {
    "nbHits": 1234,
    "hits": [
        {"title": "Uv is the best thing to happen to the Python ecosystem in a decade",
         "url": "https://emily.space/posts/251023-uv", "objectID": "45751400",
         "points": 2214, "author": "todsacerdoti",
         "created_at": "2025-10-29T18:57:29Z"},
        {"title": "Ask HN: Best resources for learning Rust?", "url": None,
         "objectID": "999", "points": 42, "author": "rustfan",
         "created_at": "2026-01-01T10:00:00Z"},
    ],
}

# --- Echte Google-News-RSS-Antwort (Redirect-Token, HTML-Entities) ---
GOOGLE_NEWS_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>"ki agenten" - Google News</title>
<item><title>Open AI: Was beim Angriff auf Hugging Face geschah - SZ.de</title>
<link>https://news.google.com/rss/articles/CBMiTOKEN?oc=5</link>
<description>Rund 700 von OpenAI eingesetzte KI-Agenten sollen sich verb&#252;ndet haben</description>
<pubDate>Wed, 03 Sep 2026 10:00:00 GMT</pubDate></item>
<item><title>KI-Agenten im Mittelstand - Handelsblatt</title>
<link>https://news.google.com/rss/articles/CBMiTOKEN2?oc=5</link>
<description>Immer mehr Firmen setzen auf Agenten</description>
<pubDate>Wed, 03 Sep 2026 09:00:00 GMT</pubDate></item>
</channel></rss>"""

# --- Echte Bing-News-RSS-Antwort (apiclick-Link mit encoded url=) ---
BING_NEWS_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>ki agenten - Bing News</title>
<item><title>Angriff auf Hugging Face &#8211; 700 KI-Agenten verb&#252;nden sich</title>
<link>http://www.bing.com/news/apiclick.aspx?ref=FexRss&amp;url=https%3a%2f%2fwww.msn.com%2fde-de%2fnachrichten%2fangriff&amp;c=123</link>
<description>Rund 700 von OpenAI eingesetzte KI-Agenten sollen</description>
<pubDate>Wed, 03 Sep 2026 08:00:00 GMT</pubDate></item>
<item><title>Zweite News</title>
<link>http://www.bing.com/news/apiclick.aspx?ref=FexRss&amp;url=https%3a%2f%2fwww.spiegel.de%2fartikel</link>
<description>Beschreibung zwei</description>
<pubDate>Wed, 03 Sep 2026 07:00:00 GMT</pubDate></item>
</channel></rss>"""


@pytest.fixture
def route_net(fake_transport, monkeypatch):
    """net._transport auf FakeTransport setzen + Proxy-Fallback AUS.

    Sonst macht ein simulierter 403/429 einen ECHTEN Proxy-Retry (Credentials
    in Env) → Test ginge ins echte Netz. (Isolations-Muster wie conftest.)
    """
    import net
    monkeypatch.setattr(net, "_transport", fake_transport)
    monkeypatch.setattr(net, "_try_proxy", lambda *a, **k: None)
    monkeypatch.setattr(net, "_try_proxy_post", lambda *a, **k: None)
    return fake_transport


# ---------- q_hn: HackerNews-Algolia ----------

def test_hn_parst_json(route_net):
    route_net.route("https://hn.algolia.com/api/v1/search",
                    route_net.ok_json(HN_JSON))
    out = web.q_hn("python", 5)
    assert len(out) == 2, f"2 HN-Treffer erwartet: {out}"
    assert out[0]["title"].startswith("Uv is the best")
    assert out[0]["url"] == "https://emily.space/posts/251023-uv"
    assert out[0]["source"] == "HackerNews"
    assert out[0]["year"] == 2025, "Jahr aus created_at"
    assert "2214" in (out[0]["snippet"] or ""), "Punkte im Snippet"


def test_hn_ask_ohne_url_bekommt_item_link(route_net):
    """Ask-HN hat kein url-Feld → news.ycombinator.com/item?id=ObjectID."""
    route_net.route("https://hn.algolia.com/api/v1/search",
                    route_net.ok_json(HN_JSON))
    out = web.q_hn("rust", 5)
    ask = [r for r in out if "999" in (r["url"] or "")]
    assert ask, f"Ask-HN-Treffer muss Item-Link haben: {out}"
    assert ask[0]["url"] == "https://news.ycombinator.com/item?id=999"


def test_hn_fehler_liefert_leer_und_meldet(route_net, capsys):
    route_net.route("https://hn.algolia.com/api/v1/search",
                    exc=route_net.err(429))
    out = web.q_hn("python", 5)
    assert out == []
    err = capsys.readouterr().err
    assert "hn" in err.lower(), f"Fehler sichtbar: {err}"


# ---------- q_google_news: Google-News-RSS ----------

def test_google_news_parst_rss(route_net):
    route_net.route("https://news.google.com/rss/search",
                    route_net.ok_html(GOOGLE_NEWS_RSS))
    out = web.q_google_news("ki agenten", 5)
    assert len(out) == 2, f"2 Google-News erwartet: {out}"
    assert out[0]["title"].startswith("Open AI:")
    assert out[0]["url"].startswith("https://news.google.com/rss/articles/"), \
        "Redirect-Token bleibt (RSS-Reader-Muster)"
    assert "SZ.de" in out[0]["title"] or "SZ.de" in (out[0]["snippet"] or "")


def test_google_news_html_entities_aufgeloest(route_net):
    route_net.route("https://news.google.com/rss/search",
                    route_net.ok_html(GOOGLE_NEWS_RSS))
    out = web.q_google_news("ki agenten", 5)
    joined = " ".join(r["title"] + (r["snippet"] or "") for r in out)
    assert "&#" not in joined, f"Entities müssen aufgelöst sein: {joined}"
    assert "verbündet" in joined, "ü aus &#252; dekodiert"


def test_google_news_fehler_leer(route_net, capsys):
    route_net.route("https://news.google.com/rss/search", exc=route_net.err(403))
    out = web.q_google_news("ki", 5)
    assert out == []
    assert "google" in capsys.readouterr().err.lower()


# ---------- q_bing_news: Bing-News-RSS ----------

def test_bing_news_parst_rss_und_loest_apiclick_url(route_net):
    route_net.route("https://www.bing.com/news/search",
                    route_net.ok_html(BING_NEWS_RSS))
    out = web.q_bing_news("ki agenten", 5)
    assert len(out) == 2, f"2 Bing-News erwartet: {out}"
    urls = [r["url"] for r in out]
    assert any("msn.com" in u for u in urls), f"echte URL aus apiclick-Param: {urls}"
    assert not any("apiclick" in u for u in urls), "apiclick-Wrapper entfernt"
    joined = " ".join(r["title"] for r in out)
    assert "&#" not in joined and "verbünden" in joined, \
        f"Entities dekodiert: {joined}"


def test_bing_news_fehler_leer(route_net, capsys):
    route_net.route("https://www.bing.com/news/search", exc=route_net.err(500))
    out = web.q_bing_news("ki", 5)
    assert out == []
    assert "bing" in capsys.readouterr().err.lower()


# ---------- Fanout-Integration (OpenCode-Finding 7: Cache×Health×Fanout) ----------

def test_neue_quellen_im_register():
    """Alle 3 neuen Quellen sind im WEB-Register + key-frei (kein KEY_QUELLEN_MAP)."""
    for key in ("hn", "google_news", "bing_news"):
        assert key in web.WEB, f"{key} fehlt im WEB-Register"
        assert key not in web.KEY_QUELLEN_MAP, f"{key} ist key-frei"
        assert callable(web.WEB[key])


def test_fanout_liefert_hn_treffer(route_net):
    """search_web mit nur hn → Treffer kommen durch den ganzen Fanout-Pfad."""
    route_net.route("https://hn.algolia.com/api/v1/search",
                    route_net.ok_json(HN_JSON))
    res = web.search_web("python", 5, only="hn")
    assert any(r["source"] == "HackerNews" for r in res), \
        f"HN-Treffer durch Fanout: {res}"
