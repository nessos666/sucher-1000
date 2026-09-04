"""Block 14 — Paid-Quellen Runde 2: ZenRows + SearchAPI.io + Firecrawl.

Agenten-Runde 2, live verifiziert 03.09.2026:
- ZenRows:   5.000 Credits/Monat gratis (erneuert, keine Karte), ab $0,36/1k
- SearchAPI: 100 Requests einmalig gratis, $4/1k — 50+ Engines in einem Key
- Firecrawl: 1.000 Credits/Monat gratis (~500 Suchen), Tavily-Ersatz
Key-optional via KEY_QUELLEN_MAP. RED zuerst.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import sucher_web as web

# --- ZenRows SERP (Google-HTML → strukturiert) ---
ZENROWS_JSON = {"results": [
    {"title": "Trauma Therapie", "url": "https://klinik.de/ptbs",
     "snippet": "PTBS Behandlung"}]}

# --- SearchAPI.io (Google engine) ---
SEARCHAPI_JSON = {"organic_results": [
    {"title": "Trauma Guide", "link": "https://guide.de/trauma",
     "snippet": "Ratgeber"}]}

# --- Firecrawl /search ---
FIRECRAWL_JSON = {"success": True, "data": [
    {"title": "Trauma Info", "url": "https://info.de/trauma",
     "description": "Informationen"}]}


@pytest.fixture
def route_net(fake_transport, monkeypatch):
    import net
    monkeypatch.setattr(net, "_transport", fake_transport)
    monkeypatch.setattr(net, "_try_proxy", lambda *a, **k: None)
    monkeypatch.setattr(net, "_try_proxy_post", lambda *a, **k: None)
    return fake_transport


# ---------- ZenRows ----------

def test_zenrows_ohne_key_uebersprungen(monkeypatch, capsys):
    monkeypatch.setattr(web, "_env", lambda name: "")
    assert web.q_zenrows("trauma", 5) == []
    assert "übersprungen" in capsys.readouterr().err.lower()


def test_zenrows_mit_key(route_net, monkeypatch):
    monkeypatch.setattr(web, "_env", lambda name: {
        "ZENROWS_API_KEY": "1abcdef"}.get(name, ""))
    route_net.route("https://api.zenrows.com/v1/", route_net.ok_json(ZENROWS_JSON))
    out = web.q_zenrows("trauma", 5)
    assert len(out) == 1
    assert out[0]["title"] == "Trauma Therapie"
    assert out[0]["source"] == "ZenRows"


def test_zenrows_fehler_leer(route_net, monkeypatch, capsys):
    monkeypatch.setattr(web, "_env", lambda name: {
        "ZENROWS_API_KEY": "1abcdef"}.get(name, ""))
    route_net.route("https://api.zenrows.com/v1/", exc=route_net.err(429))
    assert web.q_zenrows("x", 5) == []
    assert "zenrows" in capsys.readouterr().err.lower()


# ---------- SearchAPI.io ----------

def test_searchapi_ohne_key_uebersprungen(monkeypatch, capsys):
    monkeypatch.setattr(web, "_env", lambda name: "")
    assert web.q_searchapi("trauma", 5) == []
    assert "übersprungen" in capsys.readouterr().err.lower()


def test_searchapi_mit_key(route_net, monkeypatch):
    monkeypatch.setattr(web, "_env", lambda name: {
        "SEARCHAPI_KEY": "skey"}.get(name, ""))
    route_net.route("https://www.searchapi.io/api/v1/search",
                    route_net.ok_json(SEARCHAPI_JSON))
    out = web.q_searchapi("trauma", 5)
    assert len(out) == 1
    assert out[0]["source"] == "SearchAPI"


def test_searchapi_fehler_leer(route_net, monkeypatch, capsys):
    monkeypatch.setattr(web, "_env", lambda name: {
        "SEARCHAPI_KEY": "skey"}.get(name, ""))
    route_net.route("https://www.searchapi.io/api/v1/search",
                    exc=route_net.err(401))
    assert web.q_searchapi("x", 5) == []
    assert "searchapi" in capsys.readouterr().err.lower()


# ---------- Firecrawl ----------

def test_firecrawl_ohne_key_uebersprungen(monkeypatch, capsys):
    monkeypatch.setattr(web, "_env", lambda name: "")
    assert web.q_firecrawl("trauma", 5) == []
    assert "übersprungen" in capsys.readouterr().err.lower()


def test_firecrawl_mit_key(route_net, monkeypatch):
    monkeypatch.setattr(web, "_env", lambda name: {
        "FIRECRAWL_API_KEY": "fkey"}.get(name, ""))
    route_net.route("https://api.firecrawl.dev/v1/search",
                    route_net.ok_json(FIRECRAWL_JSON))
    out = web.q_firecrawl("trauma", 5)
    assert len(out) == 1
    assert out[0]["source"] == "Firecrawl"


def test_firecrawl_fehler_leer(route_net, monkeypatch, capsys):
    monkeypatch.setattr(web, "_env", lambda name: {
        "FIRECRAWL_API_KEY": "fkey"}.get(name, ""))
    route_net.route("https://api.firecrawl.dev/v1/search",
                    exc=route_net.err(403))
    assert web.q_firecrawl("x", 5) == []
    assert "firecrawl" in capsys.readouterr().err.lower()


# ---------- Register ----------

def test_block14_register():
    for key in ("zenrows", "searchapi", "firecrawl"):
        assert key in web.WEB, f"{key} fehlt"
        assert key in web.KEY_QUELLEN_MAP, f"{key} muss Key-optional sein"
