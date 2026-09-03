"""Smoke-Test: Test-Infrastruktur funktioniert (kein Netz nötig)."""
import urllib.error


def test_fake_transport_ok_json(fake_transport):
    fake_transport.route("https://api.example.org/",
                         fake_transport.ok_json({"results": [{"id": 1}]}))
    status, body = fake_transport.open("https://api.example.org/search?q=x")
    assert status == 200
    assert b'"id": 1' in body


def test_fake_transport_zählt_aufrufe(fake_transport):
    fake_transport.route("https://a.example/", fake_transport.ok_json({}))
    fake_transport.open("https://a.example/1")
    fake_transport.open("https://a.example/2")
    assert len(fake_transport.calls) == 2


def test_fake_transport_wirft_exception(fake_transport):
    fake_transport.route("https://blocked.example/", exc=fake_transport.err(403))
    import pytest
    with pytest.raises(urllib.error.HTTPError):
        fake_transport.open("https://blocked.example/x")


def test_unique_db_pfad(unique_db_path):
    assert str(unique_db_path).endswith(".db")
