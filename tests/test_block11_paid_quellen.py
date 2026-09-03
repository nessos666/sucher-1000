"""Block 11 — Paid-Quellen als Option: Serper + You.com.

Agenten-Runde 2, live verifiziert 03.09.2026 (403/401 ohne Key = Endpoint lebt).
Serper: 2.500 Credits einmalig gratis, $1/1k — You.com: 100 Queries/Tag dauerhaft.
Key-optional via KEY_QUELLEN_MAP (NO_KEY-Mechanik). RED zuerst.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import sucher_web as web

# --- Echte Serper-Antwort (Google-SERP) ---
SERPER_JSON = {"organic": [
    {"title": "PTBS Behandlung", "link": "https://klinik.de/ptbs",
     "snippet": "Behandlung der PTBS"}]}

# --- Echte You.com-Antwort ---
YOU_JSON = {"web": {"results": [
    {"title": "Trauma Therapy Guide", "url": "https://therapie.de/trauma",
     "description": "Leitfaden"}]}}


@pytest.fixture
def route_net(fake_transport, monkeypatch):
    import net
    monkeypatch.setattr(net, "_transport", fake_transport)
    monkeypatch.setattr(net, "_try_proxy", lambda *a, **k: None)
    monkeypatch.setattr(net, "_try_proxy_post", lambda *a, **k: None)
    return fake_transport


def test_serper_ohne_key_uebersprungen(monkeypatch, capsys):
    monkeypatch.setattr(web, "_env", lambda name: "")
    assert web.q_serper("trauma", 5) == []
    assert "übersprungen" in capsys.readouterr().err.lower()


def test_serper_mit_key(route_net, monkeypatch):
    monkeypatch.setattr(web, "_env", lambda name: {
        "SERPER_API_KEY": "skey"}.get(name, ""))
    route_net.route("https://google.serper.dev/search", route_net.ok_json(SERPER_JSON))
    out = web.q_serper("trauma", 5)
    assert len(out) == 1
    assert out[0]["title"] == "PTBS Behandlung"
    assert out[0]["url"] == "https://klinik.de/ptbs"
    assert out[0]["source"] == "Serper"


def test_serper_fehler_leer(route_net, monkeypatch, capsys):
    monkeypatch.setattr(web, "_env", lambda name: {
        "SERPER_API_KEY": "skey"}.get(name, ""))
    route_net.route("https://google.serper.dev/search", exc=route_net.err(403))
    assert web.q_serper("x", 5) == []
    assert "serper" in capsys.readouterr().err.lower()


def test_youcom_ohne_key_uebersprungen(monkeypatch, capsys):
    monkeypatch.setattr(web, "_env", lambda name: "")
    assert web.q_youcom("trauma", 5) == []
    assert "übersprungen" in capsys.readouterr().err.lower()


def test_youcom_mit_key(route_net, monkeypatch):
    monkeypatch.setattr(web, "_env", lambda name: {
        "YOUCOM_API_KEY": "ykey"}.get(name, ""))
    route_net.route("https://api.you.com/v1/search", route_net.ok_json(YOU_JSON))
    out = web.q_youcom("trauma", 5)
    assert len(out) == 1
    assert "Trauma Therapy" in out[0]["title"]
    assert out[0]["source"] == "You.com"


def test_block11_register():
    for key in ("serper", "youcom"):
        assert key in web.WEB, f"{key} fehlt"
        assert key in web.KEY_QUELLEN_MAP, f"{key} muss Key-optional sein"
