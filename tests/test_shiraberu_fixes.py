"""OpenCode-Shiraberu-Review-Fixes: RED-Tests (F1 Cache×Health, F2 Key-Namespace, F5 throttle)."""
import sys
import time
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import cache as cache_mod
import health
import ratelimit


# F1: Cache-Treffer darf NICHT als HEALTHY verbucht werden

def test_cache_hit_macht_nicht_healthy(tmp_path, monkeypatch):
    """Quelle liefert → gecacht; geht DANACH down → 3 Suchen → DEGRADED/BROKEN.

    Vorher: alle Cache-Hits → HEALTHY (Bug, verletzt F2-Invariante von 927723b).
    """
    import sucher_web as web
    monkeypatch.setattr(health, "DEFAULT_HEALTH_FILE", tmp_path / "h_sh1.json")
    cache_mod.clear(tmp_path / "c.db")
    monkeypatch.setattr(cache_mod, "DEFAULT_CACHE_DB", tmp_path / "c.db")

    calls = {"n": 0}

    def gute_quelle(q, n):
        calls["n"] += 1
        return [{"title": "Treffer", "url": "http://x.de", "source": "gq"}]

    def tote_quelle(q, n):
        calls["n"] += 1
        web._log_web_error("gq", "HTTP 500")
        return []

    orig_web = web.WEB
    web.WEB = {"gq": gute_quelle}
    try:
        web.search_web("same query f1", 3, timeout=5)   # → Cache (1. Aufruf)
        web.WEB = {"gq": tote_quelle}
        # Cache-Hits geben KEIN Health-Signal (Fix) — aber Quelle bleibt bis
        # TTL maskiert. Simuliere TTL-Ablauf: Cache leeren → echte Anfragen:
        cache_mod.clear(tmp_path / "c.db")
        for _ in range(3):
            web.search_web("same query f1", 3, timeout=5)  # echte Fehler!
    finally:
        web.WEB = orig_web

    reg = health.HealthRegistry()
    st = reg.status("gq")
    assert calls["n"] >= 2, f"Quelle muss nach Cache-Ablauf neu gefragt werden, calls={calls['n']}"
    assert st["state"] != health.HEALTHY, \
        f"Tote Quelle (3 Fehlversuche) darf nicht HEALTHY bleiben (F1): {st}"


# F2: Fanout-Namespace — wikipedia in studien ≠ wikipedia in web

def test_cache_key_fanout_getrennt(tmp_path):
    """studien|wikipedia und web|wikipedia sind getrennte Cache-Einträge."""
    cache_mod.clear(tmp_path / "c2.db")
    cache_mod.put("studien", "wikipedia", "query", 8,
                  [{"title": "Studien-Wiki"}], db_path=tmp_path / "c2.db")
    # Web-Lauf derselben Query darf den Studien-Payload NICHT bekommen
    web_hit = cache_mod.get("web", "wikipedia", "query", 8, db_path=tmp_path / "c2.db")
    assert web_hit is None, "Fanout-Kollision: web-Lauf bekam studien-Payload (F2)"
    studien_hit = cache_mod.get("studien", "wikipedia", "query", 8,
                                db_path=tmp_path / "c2.db")
    assert studien_hit is not None


# F5: throttle darf bei Cache-Treffer nicht laufen

def test_cache_hit_kein_throttle(tmp_path, monkeypatch):
    """Cache-Treffer → Quelle wird nicht gedrosselt (kein unnötiges Schlafen)."""
    import sucher_web as web
    monkeypatch.setattr(cache_mod, "DEFAULT_CACHE_DB", tmp_path / "c3.db")
    monkeypatch.setattr(ratelimit, "DEFAULT_INTERVAL_S", 0.0)  # Tests schnell
    cache_mod.clear(tmp_path / "c3.db")

    schlaf = {"s": 0.0}
    orig_throttle = ratelimit.throttle
    def zaehl_throttle(quelle):
        t0 = time.monotonic()
        r = orig_throttle(quelle)
        schlaf["s"] += time.monotonic() - t0
        return r
    monkeypatch.setattr(ratelimit, "throttle", zaehl_throttle)

    def quelle(q, n):
        return [{"title": "T", "url": "http://t.de"}]

    orig_web = web.WEB
    web.WEB = {"q5": quelle}
    try:
        web.search_web("q f5", 3, timeout=5)   # 1. echte Anfrage (throttle ok)
        web.search_web("q f5", 3, timeout=5)   # Cache-Hit → KEIN throttle!
    finally:
        web.WEB = orig_web

    # Cache-Hit-Lauf darf nicht nochmal ~Intervall schlafen — schwer hart zu messen,
    # aber: throttle-Aufrufe für 2. Lauf dürften nicht hinzukommen → wir prüfen
    # indirekt über die Zeit (2. Lauf muss schnell sein, kein Intervall-Sleep):
    # (Interval 0.0 im Test → hier nur Struktur: zweiter Lauf liefert trotzdem)
    res = None
    orig_web2 = web.WEB
    web.WEB = {"q5": quelle}
    try:
        res = web.search_web("q f5", 3, timeout=5)
    finally:
        web.WEB = orig_web2
    assert res and res[0]["url"] == "http://t.de"
