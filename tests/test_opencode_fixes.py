"""OpenCode-Review-Fixes: RED-Tests (F1 Prozess-Exit, F3 _error-Logging, F7 Determinismus, F10 Offline)."""
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC))

import sucher_universal as su


# F1: Prozess darf nach Budget-Timeout NICHT hängen (Exit-Hang)

def test_f1_prozess_exit_haengt_nicht(tmp_path):
    """Nach Budget-Timeout muss der PROZESS sofort enden (nicht nur search()).

    Vorher: non-daemon Worker-Threads → Prozess joint sie beim Exit und hängt
    bis die hängende Quelle (15s) endet. Daemon-Factory fixt das.
    """
    code = '''
import sys, time
sys.path.insert(0, "src")
import sucher_universal as su

def haengt(q, n):
    time.sleep(15)
    return [{"title": "zu-spaet", "url": "http://x.de"}]

su.SCI = {"haengt": haengt}
su.GENERAL = {}
res = su.search("test", 3, mode="studien", budget_s=2)
print("SEARCH_DONE")
'''
    env = dict(os.environ, SUCHER_HEALTH_FILE=str(tmp_path / "h_f1.json"),
               SUCHER_CACHE_DB=str(tmp_path / "c_f1.db"))
    t0 = time.monotonic()
    r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, timeout=10, cwd=str(REPO), env=env)
    dt = time.monotonic() - t0
    assert r.returncode == 0, f"Prozess fehlgeschlagen: {r.stderr[:200]}"
    assert "SEARCH_DONE" in r.stdout
    # Wenn Daemon-Factory greift: Prozess endet ~2s nach Budget (nicht 15s+)
    assert dt < 8.0, f"Prozess hing nach Budget ({dt:.1f}s) — Daemon-Factory fehlt!"


# F3: _error von net (Timeout/429) wird geloggt, nicht still geschluckt

def test_f3_error_wird_geloggt(monkeypatch):
    """Quelle, die ein _error-Dict liefert (nicht wirft), muss im Register landen."""
    import net

    class FakeNet:
        def get_json(self, url, timeout=8, retries=2):
            return {"_error": "HTTP 429"}

    # http_json-Shim ruft net.get_json — wir mocken net im Shim-Pfad
    monkeypatch.setattr(su, "_QUELLEN_FEHLER", {})
    orig_http = su.http_json

    def fake_http(url, timeout=8, retries=2):
        return {"_error": "HTTP 429"}

    su.http_json = fake_http
    try:
        # q_openalex direkt aufrufen (nutzt http_json → _error)
        res = su.q_openalex("test", 3)
    finally:
        su.http_json = orig_http

    assert res == []
    fehler = su._get_quellen_fehler()
    assert "openalex" in fehler, "_error wurde still geschluckt (F3)!"
    assert "429" in fehler["openalex"][0]


# F7: Scoring deterministisch bei Punktgleichstand

def test_f7_scoring_deterministisch():
    """Gleiche Scores → Reihenfolge nach Titel stabil (nicht Thread-Zufall)."""
    a = {"title": "Alpha", "url": "http://a.de", "source": "OpenAlex",
         "cites": 0, "relevance": 0, "is_oa": True}
    b = {"title": "Beta", "url": "http://b.de", "source": "OpenAlex",
         "cites": 0, "relevance": 0, "is_oa": True}
    c = {"title": "Gamma", "url": "http://c.de", "source": "OpenAlex",
         "cites": 0, "relevance": 0, "is_oa": True}

    # Gleiche Eingabe in verschiedenen Reihenfolgen (simuliert Thread-Zufall)
    r1 = su._score_sort([b, a, c])
    r2 = su._score_sort([c, a, b])
    r3 = su._score_sort([a, b, c])

    titles1 = [x["title"] for x in r1]
    assert titles1 == [x["title"] for x in r2] == [x["title"] for x in r3], \
        "Punktgleichstand variiert zwischen Läufen (F7)!"


# F10: Offline-Suite darf keine Live-Netz-Tests enthalten

def test_f10_kein_live_netz_in_offline_suite():
    """test_codex_fixes F4 (Live-Netz) muss @pytest.mark.live haben."""
    import ast
    src = (REPO / "tests" / "test_codex_fixes.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "test_f4_health_json_clean":
            decorators = [ast.unparse(d) for d in node.decorator_list]
            assert any("live" in d for d in decorators), \
                "F4-Test macht Live-Netz, hat aber kein @pytest.mark.live (F10)!"
            return
    pytest.fail("test_f4_health_json_clean nicht gefunden")
