"""SUCHER-1000 Test-Infrastruktur.

FakeTransport: Netz-Mock ohne Zusatz-Lib (stdlib reicht). Routen URL-Präfixe
auf eingefrorene Antworten ODER Exceptions und zählt Aufrufe. Wird zur
LAUFZEIT in net._transport gesetzt (nie zur Import-Zeit — Skill-Pitfall).
"""
from __future__ import annotations

import json
import urllib.error
import uuid
from pathlib import Path

import pytest


class FakeTransport:
    """Ersatz für echte HTTP-Transportschicht. Kein Netz nötig."""

    def __init__(self):
        self.routes = {}   # url-prefix -> Antwort-Objekt ODER Exception
        self.calls = []    # Liste der aufgerufenen URLs (Reihenfolge!)

    def route(self, prefix, answer=None, exc=None):
        """URL-Präfix auf Antwort oder Exception mappen."""
        if exc is not None:
            self.routes[prefix] = ("exc", exc)
        else:
            self.routes[prefix] = ("ok", answer)

    def open(self, url, timeout=8, headers=None):
        """Transport-API: gibt (status, body) zurück oder wirft."""
        self.calls.append(url)
        for prefix, (kind, payload) in self.routes.items():
            if url.startswith(prefix):
                if kind == "exc":
                    raise payload
                return payload
        raise urllib.error.HTTPError(url, 404, "no route", {}, None)

    # -- Helfer für Tests --
    def ok_json(self, data: dict):
        return (200, json.dumps(data).encode())

    def ok_html(self, html: str):
        return (200, html.encode())

    def err(self, code: int):
        return urllib.error.HTTPError("http://x", code, f"err {code}", {}, None)


@pytest.fixture
def fake_transport():
    """Frischer FakeTransport je Test — keine geteilten Routen."""
    return FakeTransport()


@pytest.fixture(autouse=True)
def health_auf_tmp(tmp_path, monkeypatch):
    """P4: JEDER Test leitet die Health-Datei auf tmp um.

    search() erstellt HealthRegistry() mit DEFAULT_HEALTH_FILE — ohne diese
    Umleitung schrieben Fake-Quellen aus Tests in die echte data/health.json.
    """
    import sys
    src = str(Path(__file__).resolve().parents[1] / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    import health
    monkeypatch.setattr(health, "DEFAULT_HEALTH_FILE", tmp_path / "health_test.json")
    yield


@pytest.fixture
def unique_db_path(tmp_path):
    """Eindeutiger SQLite-Pfad je Test (Skill-Pitfall #13/#20)."""
    return tmp_path / f"t_{uuid.uuid4().hex[:8]}.db"
