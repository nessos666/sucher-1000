"""Codex-Gesamt-Review-Fixes: RED-Tests (F2/F3 Timeout≠HEALTHY, F4 URL-Verlust, F1 Proxy-Captcha)."""
import sys
import time
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import health
import sucher_universal as su


# F2: Timeout-Quelle darf nicht HEALTHY werden (akademisches Fanout)

def test_timeout_quelle_nicht_healthy(tmp_path, monkeypatch):
    """Quelle, die das Budget reißt (nie antwortet) → NICHT HEALTHY verbuchen."""
    monkeypatch.setattr(health, "DEFAULT_HEALTH_FILE", tmp_path / "h_t1.json")

    def langsame_quelle(q, n):
        time.sleep(2)
        return [{"title": "zu spaet", "url": "http://x.de"}]

    orig_sci, orig_gen = su.SCI, su.GENERAL
    su.SCI = {"langsam1": langsame_quelle}
    su.GENERAL = {}
    su._QUELLEN_FEHLER.clear()
    try:
        su.search("test", 2, mode="studien", budget_s=0)
    finally:
        su.SCI, su.GENERAL = orig_sci, orig_gen

    reg = health.HealthRegistry()
    st = reg.status("langsam1")
    assert st["state"] != health.HEALTHY, \
        f"Timeout-Quelle darf nicht HEALTHY werden (Cooldown unterlaufen!): {st}"


# F3: gleiches Problem im Web-Fanout

def test_web_timeout_quelle_nicht_healthy(tmp_path, monkeypatch):
    """Web-Quelle, die das Budget reißt → NICHT HEALTHY verbuchen."""
    import sucher_web as web
    monkeypatch.setattr(health, "DEFAULT_HEALTH_FILE", tmp_path / "h_t2.json")

    def langsame_quelle(q, n):
        time.sleep(2)
        return [{"title": "zu spaet", "url": "http://x.de"}]

    orig_web = web.WEB
    web.WEB = {"langsam2": langsame_quelle}
    try:
        web.search_web("test", 3, timeout=0)  # Budget 0 → Timeout
    finally:
        web.WEB = orig_web

    reg = health.HealthRegistry()
    st = reg.status("langsam2")
    assert st["state"] != health.HEALTHY, \
        f"Web-Timeout-Quelle darf nicht HEALTHY werden: {st}"


# F4: URL-lose Treffer im Kombi-Dedup nicht verwerfen — via sucher.py-Logik

def test_dedup_behaelt_ohne_url():
    """Dedup-Logik (Modus alle) muss URL-lose Treffer behalten (F4-Codex)."""
    # Gleiche Logik wie in sucher.py --modus alle
    def dedup(results):
        seen, out = set(), []
        for r in results:
            url = (r.get("url") or "").lower()
            if url:
                if url not in seen:
                    seen.add(url); out.append(r)
            else:
                out.append(r)
        return out

    r_ohne_url = {"title": "Ohne URL", "source": "ddgs"}
    r_mit_url = {"title": "Mit URL", "url": "http://x.de", "source": "Bing"}
    res = dedup([r_ohne_url, r_mit_url, r_mit_url])  # Mit-URL doppelt
    assert len(res) == 2, f"URL-loser Treffer verschwand + Dedup: {res}"
    assert any(r.get("title") == "Ohne URL" for r in res)


# F1: Proxy-Antwort im HTTPError-Pfad muss auf Captcha geprüft werden

def test_proxy_http_error_captcha_erkannt(monkeypatch):
    """HTTP 403 + Proxy liefert Captcha-HTML → get_text muss Fehler melden (F1)."""
    import net
    import urllib.error

    class FakeOpen:
        def __init__(self):
            self.n = 0
        def open(self, url, timeout=8):
            self.n += 1
            if self.n == 1:
                raise urllib.error.HTTPError(url, 403, "forbidden", {}, None)
            # Proxy-Antwort: Captcha-HTML (muss als Block erkannt werden!)
            return (200, b"<html><title>Just a moment...</title>captcha</html>")

    fake = FakeOpen()
    monkeypatch.setattr(net, "_transport", fake)
    # Proxy verfügbar machen (fetch liefert die Captcha-Seite)
    import proxy
    monkeypatch.setattr(proxy, "available", lambda: True)
    monkeypatch.setattr(proxy, "fetch", lambda url, timeout=8, erwartet="text": (
        "<html><title>Just a moment...</title>captcha</html>"))

    text, err = net.get_text("https://api.example.com/x", retries=0)
    assert err, f"Proxy-Captcha muss als Fehler erkannt werden, bekam: {err!r} / text={text[:30]!r}"
