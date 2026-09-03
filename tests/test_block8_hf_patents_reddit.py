"""Block 8 — HuggingFace + Google Patents + Reddit (OAuth, Key-optional).

q_huggingface  HuggingFace Models+Datasets (key-frei JSON, live 03.09.2026)
q_patents      Google Patents XHR-API (key-frei JSON, live 03.09.2026)
q_reddit       Reddit Data-API via OAuth (Key-optional: .json blockt 403 seit
               2026, offizielle API 100 QPM free nach App-Registrierung)

RED zuerst: Funktionen existieren noch nicht.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import sucher_web as web

# --- Echte HuggingFace-Models-Antwort ---
HF_JSON = [{"id": "meta-llama/Llama-3.1-8B-Instruct", "downloads": 5644341,
            "likes": 6769, "tags": ["transformers", "llama"],
            "pipeline_tag": "text-generation"}]

# --- Echte Google-Patents-XHR-Antwort ---
PAT_JSON = {"results": {"total_num_results": 124151,
    "cluster": [{"result": [{"id": "patent/US9324234B2/en", "rank": 0,
        "patent": {"title": "Vehicle comprising multi-operating system",
                   "assignee": "Autoconnect Holdings Llc",
                   "publication_date": "2016-04-26",
                   "inventor": "Dennis Dale"}}]}]}}

# --- Reddit: OAuth-Token-Antwort + Such-Antwort ---
REDDIT_TOKEN = {"access_token": "tok123", "expires_in": 3600}
REDDIT_SEARCH = {"data": {"children": [{"data": {
    "title": "What is the best LLM for coding?",
    "permalink": "/r/LocalLLaMA/comments/abc/what_is_the_best",
    "subreddit": "LocalLLaMA", "score": 321,
    "created_utc": 1750000000, "url": "https://example.com/llm"}}]}}


@pytest.fixture
def route_net(fake_transport, monkeypatch):
    """net._transport auf FakeTransport setzen + Proxy-Fallback AUS (Isolation)."""
    import net
    monkeypatch.setattr(net, "_transport", fake_transport)
    monkeypatch.setattr(net, "_try_proxy", lambda *a, **k: None)
    monkeypatch.setattr(net, "_try_proxy_post", lambda *a, **k: None)
    return fake_transport


# ---------- q_huggingface ----------

def test_huggingface_parst_models(route_net):
    route_net.route("https://huggingface.co/api/models",
                    route_net.ok_json(HF_JSON))
    out = web.q_huggingface("llama", 5)
    assert len(out) == 1
    assert out[0]["title"] == "meta-llama/Llama-3.1-8B-Instruct"
    assert "huggingface.co/meta-llama" in out[0]["url"]
    assert out[0]["source"] == "HuggingFace"
    assert "5.644.341" in (out[0]["snippet"] or ""), \
        f"Downloads im Snippet: {out[0]['snippet']}"


def test_huggingface_fehler_leer(route_net, capsys):
    route_net.route("https://huggingface.co/api/models", exc=route_net.err(429))
    out = web.q_huggingface("llama", 5)
    assert out == []
    assert "huggingface" in capsys.readouterr().err.lower()


# ---------- q_patents (Google Patents XHR) ----------

def test_patents_parst_xhr(route_net):
    route_net.route("https://patents.google.com/xhr/query",
                    route_net.ok_json(PAT_JSON))
    out = web.q_patents("linux", 5)
    assert len(out) == 1
    assert "multi-operating" in out[0]["title"]
    assert "patents.google.com/patent/US9324234B2" in out[0]["url"], \
        f"Patent-URL: {out[0]['url']}"
    assert out[0]["year"] == 2016
    assert out[0]["source"] == "GooglePatents"


def test_patents_fehler_leer(route_net, capsys):
    route_net.route("https://patents.google.com/xhr/query",
                    exc=route_net.err(429))
    out = web.q_patents("x", 5)
    assert out == []
    assert "patents" in capsys.readouterr().err.lower()


# ---------- q_reddit (Key-optional via OAuth) ----------

def test_reddit_ohne_key_wird_uebersprungen(monkeypatch, capsys):
    """Kein REDDIT_CLIENT_ID → [] + übersprungen-Meldung (NO_KEY-Muster)."""
    monkeypatch.setattr(web, "_env", lambda name: "")
    out = web.q_reddit("llm", 5)
    assert out == []
    assert "übersprungen" in capsys.readouterr().err.lower()


def test_reddit_oauth_flow(route_net, monkeypatch, capsys):
    """Mit Key: Token holen → Suche → Treffer."""
    monkeypatch.setattr(web, "_env", lambda name: {
        "REDDIT_CLIENT_ID": "cid123", "REDDIT_CLIENT_SECRET": "csec"}.get(name, ""))
    route_net.route("https://www.reddit.com/api/v1/access_token",
                    route_net.ok_json(REDDIT_TOKEN))
    route_net.route("https://oauth.reddit.com/search",
                    route_net.ok_json(REDDIT_SEARCH))
    out = web.q_reddit("llm", 5)
    assert len(out) == 1
    assert "best LLM" in out[0]["title"]
    assert "reddit.com/r/LocalLLaMA" in out[0]["url"]
    assert out[0]["source"] == "Reddit"


# ---------- Register ----------

def test_block8_quellen_im_register():
    for key in ("huggingface", "patents"):
        assert key in web.WEB, f"{key} fehlt im WEB-Register"
        assert key not in web.KEY_QUELLEN_MAP, f"{key} ist key-frei"
    assert "reddit" in web.WEB, "reddit fehlt"
    assert web.KEY_QUELLEN_MAP.get("reddit") == "REDDIT_CLIENT_ID", \
        "reddit ist Key-optional (REDDIT_CLIENT_ID)"
