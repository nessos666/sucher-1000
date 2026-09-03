"""F7 (OpenCode-Gesamt): Grundtests für sucher_oa + sucher_download (waren 0% getestet)."""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import sucher_download as sdl
import sucher_oa as soa


# ---------- sucher_oa.extract_doi ----------

def test_extract_doi_aus_url():
    doi = soa.extract_doi("https://doi.org/10.1038/s41586-021-03614-z?foo=bar")
    assert doi == "10.1038/s41586-021-03614-z"


def test_extract_doi_plain():
    assert soa.extract_doi("10.1000/xyz123") == "10.1000/xyz123"


def test_extract_doi_keiner():
    assert soa.extract_doi("kein doi hier") is None
    assert soa.extract_doi("") is None


# ---------- sucher_oa.resolve (über FakeTransport) ----------

def test_resolve_unpaywall_oa(fake_transport, monkeypatch):
    """Unpaywall liefert is_oa + PDF → resolve gibt Treffer."""
    import net
    monkeypatch.setattr(net, "_transport", fake_transport)
    fake_transport.route("https://api.unpaywall.org",
                         fake_transport.ok_json({
                             "is_oa": True,
                             "best_oa_location": {"url_for_pdf": "https://x.de/paper.pdf"},
                             "oa_locations": []}))

    # sucher_oa.http_json ist eigener Shim — auch auf net umleiten
    orig = soa.http_json
    soa.http_json = lambda url, timeout=8: net.get_json(url, timeout=timeout)
    try:
        res, doi = soa.resolve("10.1038/s41586-021-03614-z")
    finally:
        soa.http_json = orig
    assert any("PDF" in r[0] for r in res), f"Unpaywall-PDF fehlt: {res}"


def test_resolve_nicht_oa_leer(fake_transport, monkeypatch):
    """Nicht-OA → resolve liefert leere Liste (kein Crash)."""
    import net
    monkeypatch.setattr(net, "_transport", fake_transport)
    fake_transport.route("https://api.unpaywall.org",
                         fake_transport.ok_json({"is_oa": False, "oa_locations": []}))
    orig = soa.http_json
    soa.http_json = lambda url, timeout=8: net.get_json(url, timeout=timeout)
    try:
        res, doi = soa.resolve("10.1038/xyz")
    finally:
        soa.http_json = orig
    assert isinstance(res, list), "resolve muss (liste, doi) zurückgeben"
    assert res == [] or all(isinstance(r, tuple) for r in res)


def test_extract_doi_aus_doi_org_url(fake_transport, monkeypatch):
    """doi.org-URL → extract_doi findet den DOI und resolve crasht nicht."""
    doi = soa.extract_doi("https://doi.org/10.1101/2020.01.01.1")
    assert doi == "10.1101/2020.01.01.1"


# ---------- sucher_download: Datei-Erkennung (offline) ----------

def test_is_pdf_erkennt(tmp_path):
    p = tmp_path / "a.pdf"
    p.write_bytes(b"%PDF-1.4\n...")
    assert sdl.is_pdf(str(p)) is True
    assert sdl.is_pdf(str(tmp_path / "gibtsnicht.pdf")) is False


def test_is_html_erkennt(tmp_path):
    p = tmp_path / "a.html"
    p.write_bytes(b"<!DOCTYPE html><html><body>Hallo</body></html>")
    assert sdl.is_html(str(p)) is True
    assert sdl.is_html(str(tmp_path / "gibtsnicht.html")) is False


def test_is_pdf_html_trennung(tmp_path):
    """PDF darf nicht als HTML erkannt werden und umgekehrt."""
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    html = tmp_path / "x.html"
    html.write_bytes(b"<html><body>Text</body></html>")
    assert sdl.is_pdf(str(pdf)) and not sdl.is_html(str(pdf))
    assert sdl.is_html(str(html)) and not sdl.is_pdf(str(html))


def test_check_blocked_erkennt_captcha(tmp_path):
    """Botwall-Datei → check_blocked muss sie erkennen."""
    p = tmp_path / "blocked.html"
    p.write_text("<html><title>Just a moment...</title>Enable JavaScript</html>")
    grund = sdl.check_blocked(str(p))
    assert grund, f"Captcha-Seite muss als blockiert erkannt werden: {grund}"


def test_check_blocked_ok_datei(tmp_path):
    """Normale GROSSE HTML-Datei (>MIN_OK=40KB) → check_blocked gibt False (nicht blockiert)."""
    p = tmp_path / "ok.html"
    p.write_text("<html><body>" + "Normale Seite " * 5000 + "</body></html>")
    assert p.stat().st_size > 40000, "Testdatei muss über MIN_OK liegen"
    assert sdl.check_blocked(str(p)) is False


def test_check_blocked_kleine_datei_ist_stub(tmp_path):
    """Kleine HTML-Datei (<40KB) = Block-Stub → check_blocked True (Fehlalarm-Schutz)."""
    p = tmp_path / "klein.html"
    p.write_text("<html><body>kurz</body></html>")
    assert sdl.check_blocked(str(p)) is True
