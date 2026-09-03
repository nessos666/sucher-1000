"""Block 9 — ClinicalTrials + OpenReview + OSF + CORE (SCI) + YouTube (Web).

Agenten-Runde 3, live verifiziert 03.09.2026. David: 'mehr wissenschaftliche
Seiten' + Google-Kleinode (YouTube InnerTube key-frei).
RED zuerst: Funktionen existieren noch nicht.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import sucher_universal as uni
import sucher_web as web

# --- ClinicalTrials v2 ---
CT_JSON = {"studies": [{"protocolSection": {
    "identificationModule": {"briefTitle": "PTSD Treatment Study", "nctId": "NCT03874598",
                             "officialTitle": "PTSD Treatment"},
    "statusModule": {"overallStatus": "RECRUITING"},
    "descriptionModule": {"briefSummary": "Study about trauma therapy"},
    "conditionsModule": {"conditions": ["PTSD"]}}}]}

# --- OpenReview v1 ---
OR_JSON = {"notes": [{"id": "rev1", "content": {"title": "Graph neural networks for physics"},
                      "cdate": 1700000000000}]}

# --- OSF Preprints ---
OSF_JSON = {"data": [{"attributes": {"title": "Trauma Exposure Study", "doi": "10.31219/osf.io/abc"},
                      "links": {"html": "https://osf.io/preprints/abc"}}]}

# --- CORE v3 ---
CORE_JSON = {"totalHits": 383894, "results": [
    {"title": "Childhood trauma in Ohio", "doi": "10.1234/core.5678",
     "yearPublished": 2006, "downloadUrl": "https://core.ac.uk/download/123.pdf"}]}

# --- YouTube InnerTube ---
YT_JSON = {"contents": {"twoColumnSearchResultsRenderer": {"primaryContents": {
    "sectionListRenderer": {"contents": [{"itemSectionRenderer": {"contents": [
        {"videoRenderer": {"videoId": "dQw4w9WgXcQ",
            "title": {"runs": [{"text": "Quantum Computers Explained"}]},
            "lengthText": {"simpleText": "12:34"},
            "ownerText": {"runs": [{"text": "Veritasium"}]}}}]}}]}}}}}


@pytest.fixture
def route_net(fake_transport, monkeypatch):
    import net
    monkeypatch.setattr(net, "_transport", fake_transport)
    monkeypatch.setattr(net, "_try_proxy", lambda *a, **k: None)
    monkeypatch.setattr(net, "_try_proxy_post", lambda *a, **k: None)
    return fake_transport


# ---------- q_clinicaltrials ----------

def test_clinicaltrials_parst(route_net):
    route_net.route("https://clinicaltrials.gov/api/v2/studies",
                    route_net.ok_json(CT_JSON))
    out = uni.q_clinicaltrials("ptsd", 5)
    assert len(out) == 1
    assert "PTSD Treatment" in out[0]["title"]
    assert "NCT03874598" in out[0]["url"]
    assert out[0]["source"] == "ClinicalTrials"
    assert out[0]["doi"] is None


def test_clinicaltrials_fehler_leer(route_net, capsys):
    route_net.route("https://clinicaltrials.gov/api/v2/studies",
                    exc=route_net.err(500))
    assert uni.q_clinicaltrials("x", 5) == []
    assert "clinicaltrials" in capsys.readouterr().err.lower()


# ---------- q_openreview ----------

def test_openreview_parst(route_net):
    route_net.route("https://api.openreview.net/notes/search",
                    route_net.ok_json(OR_JSON))
    out = uni.q_openreview("graph neural", 5)
    assert len(out) == 1
    assert "physics" in out[0]["title"]
    assert "openreview.net/forum?id=rev1" in out[0]["url"]
    assert out[0]["source"] == "OpenReview"


def test_openreview_fehler_leer(route_net, capsys):
    route_net.route("https://api.openreview.net/notes/search",
                    exc=route_net.err(403))
    assert uni.q_openreview("x", 5) == []
    assert "openreview" in capsys.readouterr().err.lower()


# ---------- q_osf ----------

def test_osf_parst(route_net):
    route_net.route("https://api.osf.io/v2/preprints/",
                    route_net.ok_json(OSF_JSON))
    out = uni.q_osf("trauma", 5)
    assert len(out) == 1
    assert "Trauma Exposure" in out[0]["title"]
    assert "10.31219" in (out[0]["doi"] or "")
    assert out[0]["source"] == "OSF"


def test_osf_fehler_leer(route_net, capsys):
    route_net.route("https://api.osf.io/v2/preprints/", exc=route_net.err(503))
    assert uni.q_osf("x", 5) == []
    assert "osf" in capsys.readouterr().err.lower()


# ---------- q_core ----------

def test_core_parst(route_net):
    route_net.route("https://api.core.ac.uk/v3/search/works",
                    route_net.ok_json(CORE_JSON))
    out = uni.q_core("trauma", 5)
    assert len(out) == 1
    assert "Ohio" in out[0]["title"]
    assert out[0]["year"] == 2006
    assert out[0]["source"] == "CORE"


def test_core_fehler_leer(route_net, capsys):
    route_net.route("https://api.core.ac.uk/v3/search/works",
                    exc=route_net.err(429))
    assert uni.q_core("x", 5) == []
    assert "core" in capsys.readouterr().err.lower()


# ---------- q_youtube (Web) ----------

def test_youtube_parst_innertube(route_net):
    route_net.route("https://www.youtube.com/youtubei/v1/search",
                    route_net.ok_json(YT_JSON))
    out = web.q_youtube("quantum", 5)
    assert len(out) == 1
    assert "Quantum Computers" in out[0]["title"]
    assert "youtube.com/watch?v=dQw4w9WgXcQ" in out[0]["url"]
    assert out[0]["source"] == "YouTube"


def test_youtube_fehler_leer(route_net, capsys):
    route_net.route("https://www.youtube.com/youtubei/v1/search",
                    exc=route_net.err(429))
    assert web.q_youtube("x", 5) == []
    assert "youtube" in capsys.readouterr().err.lower()


# ---------- Register ----------

def test_block9_quellen_im_register():
    for key in ("clinicaltrials", "openreview", "osf", "core"):
        assert key in uni.SCI, f"{key} fehlt im SCI-Register"
    assert "youtube" in web.WEB, "youtube fehlt im WEB-Register"
    assert "youtube" not in web.KEY_QUELLEN_MAP
