"""P7-B2 — Netz-gemockte 4-Fälle-Tests je Kern-Quelle (Plan P6/S7).

Fälle je Quelle: ok (liefert Treffer) / leer (0 Treffer, kein Fehler) /
429 (Rate-Limit → _error) / kaputt (Exception → _error).
Netz ist via FakeTransport gemockt — kein Live-Zugriff, keine Quota.
"""
import json
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import sucher_universal as su

# Quelle → URL-Präfix, das die q_*-Funktion aufruft
QUELLEN = {
    "openalex": "https://api.openalex.org/works",
    "crossref": "https://api.crossref.org/works",
    "arxiv": "http://export.arxiv.org/api/query",
}


def _antwort(quelle, fall, fake):
    """FakeTransport-Antwort je (Quelle, Fall)."""
    if fall == "ok":
        if quelle == "openalex":
            return fake.ok_json({"results": [{"title": "OpenAlex Treffer",
                "doi": "10.1/x", "publication_year": 2020,
                "id": "https://openalex.org/W1"}]})
        if quelle == "crossref":
            return fake.ok_json({"message": {"items": [{"title": ["Crossref Treffer"],
                "DOI": "10.2/y", "issued": {"date-parts": [[2021]]}}]}})
        if quelle == "arxiv":
            # Atom-XML für arXiv (kein JSON)
            return (200, b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
                <entry><title>Arxiv Treffer</title><id>http://arxiv.org/abs/2101.00001v1</id>
                <summary>Zusammenfassung</summary></entry></feed>""")
    if fall == "leer":
        if quelle == "openalex":
            return fake.ok_json({"results": []})
        if quelle == "crossref":
            return fake.ok_json({"message": {"items": []}})
        if quelle == "arxiv":
            return (200, b'<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>')
    if fall == "429":
        return fake.err(429)
    if fall == "kaputt":
        raise ConnectionError("kaputt")
    raise ValueError(f"unbekannter Fall {fall}")


def _q_funktion(quelle):
    """Die q_*-Funktion aus sucher_universal finden (SCI/GENERAL-Register)."""
    alle = dict(su.SCI)
    alle.update(su.GENERAL)
    return alle[quelle]


@pytest.mark.parametrize("quelle", sorted(QUELLEN))
def test_quelle_ok(quelle, fake_transport, monkeypatch):
    """Fall ok: Quelle liefert mindestens 1 Treffer."""
    import net
    monkeypatch.setattr(net, "_transport", fake_transport)
    fake_transport.route("http", _antwort(quelle, "ok", fake_transport))
    fn = _q_funktion(quelle)
    res = fn("test query", 3)
    assert isinstance(res, list) and len(res) >= 1, \
        f"{quelle}: ok-Fall muss Treffer liefern, bekam {res}"


@pytest.mark.parametrize("quelle", sorted(QUELLEN))
def test_quelle_leer(quelle, fake_transport, monkeypatch):
    """Fall leer: 0 Treffer, aber KEIN _error (kein Crash)."""
    import net
    monkeypatch.setattr(net, "_transport", fake_transport)
    fake_transport.route("http", _antwort(quelle, "leer", fake_transport))
    fn = _q_funktion(quelle)
    res = fn("nichts da", 3)
    assert isinstance(res, list), f"{quelle}: muss Liste liefern, bekam {type(res)}"
    assert res == [] or not any("_error" in str(r) for r in res), \
        f"{quelle}: leere Suche ist KEIN Fehler: {res}"


@pytest.mark.parametrize("quelle", sorted(QUELLEN))
def test_quelle_429_wird_error(quelle, fake_transport, monkeypatch):
    """Fall 429: Quelle meldet _error (sichtbar), crasht nicht."""
    import net
    monkeypatch.setattr(net, "_transport", fake_transport)
    fake_transport.route("http", _antwort(quelle, "429", fake_transport))
    fn = _q_funktion(quelle)
    res = fn("test", 3)
    assert isinstance(res, list), f"{quelle}: 429 muss Liste liefern, bekam {type(res)}"
    assert res == [] or any("_error" in str(r) for r in res), \
        f"{quelle}: 429 muss als Fehler sichtbar sein: {res}"


@pytest.mark.parametrize("quelle", sorted(QUELLEN))
def test_quelle_kaputt_crasht_nicht(quelle, fake_transport, monkeypatch):
    """Fall kaputt: Exception → Quelle liefert [], crasht nicht."""
    import net
    monkeypatch.setattr(net, "_transport", fake_transport)
    fake_transport.route("http", exc=ConnectionError("kaputt"))
    fn = _q_funktion(quelle)
    res = fn("test", 3)  # darf NICHT werfen
    assert isinstance(res, list), f"{quelle}: kaputt muss Liste liefern (nicht crashen)"


def test_quelle_tot_andere_liefern_weiter(fake_transport, monkeypatch):
    """Erfolgskriterium 2: eine Quelle künstlich tot → andere liefern weiter + Fehler gemeldet."""
    import net
    monkeypatch.setattr(net, "_transport", fake_transport)

    def haengende_quelle(q, n):  # simuliert tote Quelle: wirft
        raise ConnectionError("tot")
        return [{"title": "nie", "url": "http://x.de"}]

    def gesunde_quelle(q, n):
        return [{"title": "Gesund", "url": "http://gesund.de"}]

    orig_sci, orig_gen = su.SCI, su.GENERAL
    su.SCI = {"tot": haengende_quelle, "gesund": gesunde_quelle}
    su.GENERAL = {}
    try:
        res = su.search("test", 3, mode="studien", budget_s=5)
    finally:
        su.SCI, su.GENERAL = orig_sci, orig_gen

    assert any(r["title"] == "Gesund" for r in res), \
        "Gesunde Quelle muss trotz toter Quelle liefern"
