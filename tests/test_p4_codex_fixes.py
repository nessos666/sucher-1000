"""P4-Fix (Codex-Review): _error-Fehler degradieren Health + Query-Expansion zählt nicht mehrfach."""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import health
import sucher_universal as su


# Finding 1: _error-basierte Fehler (keine Exception) müssen Health degradieren

def test_error_pfad_komplett_via_search(tmp_path, monkeypatch):
    """End-to-End: q_*-Funktion mit http_json→_error → Health ok=False."""
    monkeypatch.setattr(health, "DEFAULT_HEALTH_FILE", tmp_path / "health_e2.json")

    orig_http = su.http_json
    orig_sci, orig_gen = su.SCI, su.GENERAL

    def http_429(url, timeout=8, retries=2):
        return {"_error": "HTTP 429"}

    def q_fake_openalex(query, n=8):
        j = http_429("https://api.openalex.org/x")
        if su._check_fehler("openalex", j):
            return []
        return [{"title": "t", "url": "http://t.de"}]

    su.http_json = http_429
    su.SCI = {"openalex": q_fake_openalex}
    su.GENERAL = {}
    su._QUELLEN_FEHLER.clear()
    try:
        su.search("test", 2, mode="studien", budget_s=10)
    finally:
        su.http_json = orig_http
        su.SCI, su.GENERAL = orig_sci, orig_gen

    reg = health.HealthRegistry()
    st = reg.status("openalex")
    assert st["state"] in (health.UNKNOWN, health.DEGRADED), \
        f"429 muss degradieren, ist: {st['state']}"


# Finding 2: Query-Expansion (3 Varianten) zählt als EIN Fehler, nicht 3

def test_query_expansion_zaehlt_einmal(tmp_path, monkeypatch):
    """3 fehlgeschlagene Varianten derselben Quelle = 1 Fail, nicht 3 → nie BROKEN in 1 Lauf."""
    monkeypatch.setattr(health, "DEFAULT_HEALTH_FILE", tmp_path / "health_q.json")

    def kaputt(q, n):
        su._check_fehler("kaputtq", {"_error": f"HTTP 500 {q}"})
        return []

    orig_sci, orig_gen = su.SCI, su.GENERAL
    orig_expand = su._expand_query
    su.SCI = {"kaputtq": kaputt}
    su.GENERAL = {}
    su._QUELLEN_FEHLER.clear()
    # 3 Query-Varianten erzwingen
    su._expand_query = lambda q: [q, q + " variant2", q + " variant3"]
    try:
        su.search("test", 2, mode="studien", budget_s=10)
    finally:
        su.SCI, su.GENERAL = orig_sci, orig_gen
        su._expand_query = orig_expand

    reg = health.HealthRegistry()
    st = reg.status("kaputtq")
    assert st["state"] != health.BROKEN, \
        f"3 Varianten = 1 Fehler (nicht BROKEN), ist: {st['state']} (consec={st.get('consecutive_fails',0)})"
    assert st.get("consecutive_fails", 0) == 1, \
        f"consecutive_fails muss 1 sein (eine Quelle pro Lauf), ist: {st.get('consecutive_fails')}"


def test_gemischte_varianten_erfolg_gewinnt(tmp_path, monkeypatch):
    """1 von 3 Varianten erfolgreich → Quelle HEALTHY (nicht completion-order-abhängig)."""
    monkeypatch.setattr(health, "DEFAULT_HEALTH_FILE", tmp_path / "health_mix.json")

    def gemischt(q, n):
        if "okvariante" in q:
            return [{"title": "Erfolg", "url": "http://ok.de"}]
        su._check_fehler("gemischt", {"_error": "HTTP 500"})
        return []

    orig_sci, orig_gen = su.SCI, su.GENERAL
    orig_expand = su._expand_query
    su.SCI = {"gemischt": gemischt}
    su.GENERAL = {}
    su._QUELLEN_FEHLER.clear()
    su._expand_query = lambda q: [q, q + " okvariante", q + " wieder-fehler"]
    try:
        su.search("test", 2, mode="studien", budget_s=10)
    finally:
        su.SCI, su.GENERAL = orig_sci, orig_gen
        su._expand_query = orig_expand

    reg = health.HealthRegistry()
    st = reg.status("gemischt")
    assert st["state"] == health.HEALTHY, \
        f"Erfolg bei 1 Variante muss HEALTHY geben, ist: {st['state']}"
