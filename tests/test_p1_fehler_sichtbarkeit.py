"""P1 — Fehler-Sichtbarkeit: stille Exceptions sind sichtbar + --quelle-Filter korrekt."""
import importlib
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import sucher_universal as su


def test_stiller_fehler_wird_sichtbar(monkeypatch, capsys):
    """Eine Quelle, die eine Exception wirft, muss im Fehler-Register landen."""
    def kaputte_quelle(q, n):
        raise ConnectionError("Simulierter Netzfehler")

    # Nur die kaputte Quelle aktiv lassen
    monkeypatch.setattr(su, "SCI", {"kaputt": kaputte_quelle})
    monkeypatch.setattr(su, "GENERAL", {})
    su._QUELLEN_FEHLER.clear()

    su.search("test", 3, mode="studien")

    fehler = su._get_quellen_fehler()
    assert "kaputt" in fehler, "Fehler wurde still geschluckt!"
    assert "Simulierter Netzfehler" in fehler["kaputt"][0]


def test_unbekannte_quelle_laeuft_nicht_still_alle(monkeypatch):
    """--quelle mit unbekanntem Namen darf NICHT still alle Quellen durchsuchen."""
    def quelle_a(q, n):
        return [{"title": "A-Treffer", "url": "http://a.de"}]

    monkeypatch.setattr(su, "SCI", {"a": quelle_a})
    monkeypatch.setattr(su, "GENERAL", {})

    # Unbekannte Quelle 'xyz' → muss [] liefern (nicht alle!)
    res = su.search("test", 3, mode="studien", only="xyz")
    assert res == [], "Unbekannte Quelle durchsuchte still ALLE Quellen!"


def test_bekannte_quelle_only_filtert(monkeypatch):
    """--quelle mit bekanntem Namen darf NUR diese Quelle nutzen."""
    def quelle_a(q, n):
        return [{"title": "A-Treffer", "url": "http://a.de"}]

    def quelle_b(q, n):
        return [{"title": "B-Treffer", "url": "http://b.de"}]

    monkeypatch.setattr(su, "SCI", {"a": quelle_a, "b": quelle_b})
    monkeypatch.setattr(su, "GENERAL", {})

    res = su.search("test", 3, mode="studien", only="a")
    titles = [r["title"] for r in res]
    assert titles == ["A-Treffer"], f"Nur Quelle 'a' erwartet, bekam: {titles}"
