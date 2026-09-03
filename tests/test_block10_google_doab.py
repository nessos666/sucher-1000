"""Block 10 — Google Scholar (HTML) + Autosuggest + Knowledge Graph + Books + DOAB.

Agenten-Runde 3, live verifiziert 03.09.2026.
- q_google_scholar: HTML-Parsing (gs_ri-Blöcke), key-frei, captcha-Gefahr
- q_autosuggest:   suggestqueries.google.com JSON, key-frei (Vorschläge)
- q_knowledgegraph: Key-optional (GOOGLE_KG_API_KEY, 100k Calls/Tag gratis)
- q_google_books:  Key-optional (GOOGLE_BOOKS_API_KEY, anonym 429)
- q_doab:          DOAB (OA-Bücher) DSpace-REST, key-frei
RED zuerst: Funktionen existieren noch nicht.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import sucher_web as web
import sucher_universal as uni

# --- Google Scholar HTML (echte Struktur) ---
SCHOLAR_HTML = """<html><body>
<div class="gs_r gs_or gs_scl"><div class="gs_ri">
<h3 class="gs_rt"><span class="gs_ctc"><span class="gs_ct1">[BUCH]</span></span>
<a id="x1" href="https://books.google.com/books?id=5pmbEAAAQBAJ">Traumatherapie bei Kindern und Jugendlichen</a></h3>
<div class="gs_a">Landolt · 2023 · Verlag</div>
<div class="gs_rs">Buch über Traumatherapie</div>
</div></div>
<div class="gs_r gs_or gs_scl"><div class="gs_ri">
<h3 class="gs_rt"><a id="x2" href="https://journal.de/ptsd">Neue PTSD-Studie</a></h3>
<div class="gs_a">Miller · 2024</div>
<div class="gs_rs">Wichtige Studie</div>
</div></div>
</body></html>"""

# --- Autosuggest ---
SUGG_JSON = ["trauma therapie",
             ["trauma therapie münchen", "trauma therapie", "trauma therapie nürnberg"]]

# --- Knowledge Graph (Google, Key nötig) ---
KG_JSON = {"itemListElement": [{"result": {
    "name": "Alan Turing", "@type": ["Person"],
    "description": "Computer scientist", "detailedDescription": {"url": "https://x"}},
    "resultScore": 87.5}]}

# --- Google Books (Key nötig) ---
BOOKS_JSON = {"totalItems": 123, "items": [{"volumeInfo": {
    "title": "Linux For Dummies", "publishedDate": "1999-01-01",
    "authors": ["Dee-Ann LeBlanc"], "infoLink": "https://books.google.com/linux"}}]}

# --- DOAB (DSpace-REST) ---
DOAB_JSON = [{"uuid": "4d6e2814", "name": "Trauma and Emergency Surgery",
              "handle": "20.500.12854/90167"}]


@pytest.fixture
def route_net(fake_transport, monkeypatch):
    import net
    monkeypatch.setattr(net, "_transport", fake_transport)
    monkeypatch.setattr(net, "_try_proxy", lambda *a, **k: None)
    monkeypatch.setattr(net, "_try_proxy_post", lambda *a, **k: None)
    return fake_transport


# ---------- q_google_scholar ----------

def test_scholar_parst_html(route_net, monkeypatch):
    route_net.route("https://scholar.google.com/scholar",
                    route_net.ok_html(SCHOLAR_HTML))
    out = web.q_google_scholar("trauma", 5)
    assert len(out) == 2, f"2 Treffer: {len(out)}"
    assert "Traumatherapie" in out[0]["title"]
    assert "books.google.com" in out[0]["url"]
    assert out[0]["year"] == 2023, "Jahr aus gs_a"
    assert out[0]["source"] == "Scholar"


def test_scholar_fehler_leer(route_net, capsys):
    route_net.route("https://scholar.google.com/scholar", exc=route_net.err(429))
    assert web.q_google_scholar("x", 5) == []
    assert "scholar" in capsys.readouterr().err.lower()


# ---------- q_autosuggest ----------

def test_autosuggest_parst(route_net):
    route_net.route("https://suggestqueries.google.com/complete/search",
                    route_net.ok_json(SUGG_JSON))
    out = web.q_autosuggest("trauma therapie", 5)
    assert len(out) == 3, f"3 Vorschläge: {len(out)}"
    assert "münchen" in out[0]["title"]
    assert out[0]["source"] == "GoogleSuggest"


def test_autosuggest_fehler_leer(route_net, capsys):
    route_net.route("https://suggestqueries.google.com/complete/search",
                    exc=route_net.err(503))
    assert web.q_autosuggest("x", 5) == []
    assert "suggest" in capsys.readouterr().err.lower()


# ---------- q_knowledgegraph (Key-optional) ----------

def test_knowledgegraph_ohne_key_uebersprungen(monkeypatch, capsys):
    monkeypatch.setattr(web, "_env", lambda name: "")
    assert web.q_knowledgegraph("turing", 5) == []
    assert "übersprungen" in capsys.readouterr().err.lower()


def test_knowledgegraph_mit_key(route_net, monkeypatch):
    monkeypatch.setattr(web, "_env", lambda name: {
        "GOOGLE_KG_API_KEY": "kgkey"}.get(name, ""))
    route_net.route("https://kgsearch.googleapis.com/v1/entities:search",
                    route_net.ok_json(KG_JSON))
    out = web.q_knowledgegraph("turing", 5)
    assert len(out) == 1
    assert "Alan Turing" in out[0]["title"]
    assert out[0]["source"] == "KnowledgeGraph"


# ---------- q_google_books (Key-optional) ----------

def test_googlebooks_ohne_key_uebersprungen(monkeypatch, capsys):
    monkeypatch.setattr(web, "_env", lambda name: "")
    assert web.q_google_books("linux", 5) == []
    assert "übersprungen" in capsys.readouterr().err.lower()


def test_googlebooks_mit_key(route_net, monkeypatch):
    monkeypatch.setattr(web, "_env", lambda name: {
        "GOOGLE_BOOKS_API_KEY": "gbkey"}.get(name, ""))
    route_net.route("https://www.googleapis.com/books/v1/volumes",
                    route_net.ok_json(BOOKS_JSON))
    out = web.q_google_books("linux", 5)
    assert len(out) == 1
    assert out[0]["title"] == "Linux For Dummies"
    assert out[0]["year"] == 1999
    assert out[0]["source"] == "GoogleBooks"


# ---------- q_doab (SCI) ----------

def test_doab_parst(route_net):
    route_net.route("https://directory.doabooks.org/rest/search",
                    route_net.ok_json(DOAB_JSON))
    out = uni.q_doab("trauma", 5)
    assert len(out) == 1
    assert "Trauma and Emergency" in out[0]["title"]
    assert "doabooks.org" in out[0]["url"]
    assert out[0]["source"] == "DOAB"


def test_doab_fehler_leer(route_net, capsys):
    route_net.route("https://directory.doabooks.org/rest/search",
                    exc=route_net.err(500))
    assert uni.q_doab("x", 5) == []
    assert "doab" in capsys.readouterr().err.lower()


# ---------- Register ----------

def test_block10_register():
    for key in ("google_scholar", "autosuggest"):
        assert key in web.WEB and key not in web.KEY_QUELLEN_MAP, key
    for key in ("knowledgegraph", "google_books"):
        assert key in web.WEB, f"{key} fehlt"
        assert key in web.KEY_QUELLEN_MAP, f"{key} muss Key-optional sein"
    assert "doab" in uni.SCI, "doab fehlt im SCI-Register"
