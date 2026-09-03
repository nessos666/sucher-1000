"""Block 6 — 4 neue Studien-Quellen (Agenten-Wissen Runde 2, live verifiziert).

q_zenodo    Zenodo/CERN    (key-frei, JSON)
q_datacite  DataCite        (key-frei, JSON — ~40 Mio DOIs)
q_dblp      DBLP Informatik (key-frei, JSON — max 1 req/3s Etikette)
q_openaire  OpenAIRE (EU)   (key-frei, JSON — XML-Hybrid-Struktur)

RED zuerst: Funktionen existieren noch nicht.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import sucher_universal as uni

# --- Echte Zenodo-Antwort (Struktur live geprüft 03.09.2026) ---
ZENODO_JSON = {"hits": {"hits": [{
    "title": "Treatment of High Energy Tibial Plateau Fractures using Hybrid",
    "doi": "10.5281/zenodo.11099085", "links": {"self": "https://zenodo.org/api/records/11099085"},
    "metadata": {"title": "Treatment of High Energy Tibial Plateau Fractures",
                 "publication_date": "2024-03-01", "creators": [{"name": "Mustafa, A."}]}}]}}

# --- Echte DataCite-Antwort ---
DATACITE_JSON = {"data": [{"attributes": {
    "titles": [{"title": "The Scretching Diagnostic Matrix - Advanced Meta"}],
    "doi": "10.5281/zenodo.20686044", "publicationYear": 2026,
    "url": "https://zenodo.org/records/20686044",
    "creators": [{"name": "Smith, Jane"}]}}]}

# --- Echte DBLP-Antwort ---
DBLP_JSON = {"result": {"hits": {"hit": [{"info": {
    "title": "BotMHG: a hybrid deep learning-based graphical approach",
    "year": "2025", "venue": "Neural Comput. Appl.",
    "doi": "10.1007/S00521-025-11402-3",
    "ee": "https://doi.org/10.1007/s00521-025-11402-3"}}]}}}

# --- Echte OpenAIRE-Antwort (XML-Hybrid-JSON) ---
OPENAIRE_JSON = {"response": {"results": {"result": [{"metadata": {
    "oaf:entity": {"oaf:result": {
        "title": [{"$": "Trauma-focused therapy for PTSD"}],
        "dateofacceptance": [{"$": "2023-06-15"}],
        "pid": [{"$": "doi:10.1234/trauma.5678"}],
        "creator": [{"$": "Miller, Jane"}],
        "journal": {"name": [{"$": "Journal of Traumatic Stress"}]},
        "bestaccessright": {"$": "OPEN"}}}
}}]}}}


@pytest.fixture
def route_net(fake_transport, monkeypatch):
    """net._transport auf FakeTransport setzen + Proxy-Fallback AUS (Isolation)."""
    import net
    monkeypatch.setattr(net, "_transport", fake_transport)
    monkeypatch.setattr(net, "_try_proxy", lambda *a, **k: None)
    monkeypatch.setattr(net, "_try_proxy_post", lambda *a, **k: None)
    return fake_transport


# ---------- q_zenodo ----------

def test_zenodo_parst_json(route_net):
    route_net.route("https://zenodo.org/api/records", route_net.ok_json(ZENODO_JSON))
    out = uni.q_zenodo("trauma", 5)
    assert len(out) == 1
    assert "Tibial" in out[0]["title"]
    assert out[0]["year"] == 2024
    assert out[0]["doi"] == "10.5281/zenodo.11099085"
    assert out[0]["source"] == "Zenodo"


def test_zenodo_fehler_leer(route_net, capsys):
    route_net.route("https://zenodo.org/api/records", exc=route_net.err(429))
    out = uni.q_zenodo("trauma", 5)
    assert out == []
    assert "zenodo" in capsys.readouterr().err.lower()


# ---------- q_datacite ----------

def test_datacite_parst_json(route_net):
    route_net.route("https://api.datacite.org/dois", route_net.ok_json(DATACITE_JSON))
    out = uni.q_datacite("matrix", 5)
    assert len(out) == 1
    assert "Scretching" in out[0]["title"]
    assert out[0]["year"] == 2026
    assert out[0]["doi"] == "10.5281/zenodo.20686044"
    assert out[0]["source"] == "DataCite"


def test_datacite_fehler_leer(route_net, capsys):
    route_net.route("https://api.datacite.org/dois", exc=route_net.err(500))
    out = uni.q_datacite("x", 5)
    assert out == []
    assert "datacite" in capsys.readouterr().err.lower()


# ---------- q_dblp ----------

def test_dblp_parst_json(route_net):
    route_net.route("https://dblp.org/search/publ/api", route_net.ok_json(DBLP_JSON))
    out = uni.q_dblp("graph neural", 5)
    assert len(out) == 1
    assert "BotMHG" in out[0]["title"]
    assert out[0]["year"] == 2025
    assert out[0]["venue"] == "Neural Comput. Appl."
    assert "10.1007" in out[0]["doi"]
    assert out[0]["source"] == "DBLP"


def test_dblp_ohne_treffer_leer(route_net):
    """DBLP liefert bei 0 Treffern keine hit-Liste → [] ohne Crash."""
    route_net.route("https://dblp.org/search/publ/api",
                    route_net.ok_json({"result": {"hits": {"hit": []}}}))
    out = uni.q_dblp("xyzxyz", 5)
    assert out == []


# ---------- q_openaire ----------

def test_openaire_parst_json(route_net):
    route_net.route("https://api.openaire.eu/search/publications",
                    route_net.ok_json(OPENAIRE_JSON))
    out = uni.q_openaire("trauma", 5)
    assert len(out) == 1
    assert "Trauma-focused" in out[0]["title"]
    assert out[0]["year"] == 2023
    assert out[0]["doi"] == "10.1234/trauma.5678", "doi:-Präfix wird entfernt"
    assert out[0]["venue"] == "Journal of Traumatic Stress"
    assert out[0]["source"] == "OpenAIRE"


def test_openaire_fehler_leer(route_net, capsys):
    route_net.route("https://api.openaire.eu/search/publications",
                    exc=route_net.err(503))
    out = uni.q_openaire("trauma", 5)
    assert out == []
    assert "openaire" in capsys.readouterr().err.lower()


# ---------- Register ----------

def test_block6_quellen_im_sci_register():
    for key in ("zenodo", "datacite", "dblp", "openaire"):
        assert key in uni.SCI, f"{key} fehlt im SCI-Register"
        assert callable(uni.SCI[key])
