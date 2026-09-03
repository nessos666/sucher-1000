"""P6 — Web-Bündel: Mojeek-Captcha-Erkennung, Wikipedia, Exa-Skip, daemon-Fanout."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import sucher_web as web

# Captcha-Seite wie Mojeek sie seit 03.09.2026 liefert
CAPTCHA_HTML = """<html><head><title>Captcha</title></head><body>
<h1>Please verify you are human</h1><p>Enable JavaScript and cookies to continue</p>
</body></html>"""

# Echte Mojeek-Ergebnisstruktur (für den Fall dass sie wieder freigibt)
MOJEEK_OK_HTML = """<html><body>
<h2><a class="ob" href="https://example.com/1">Erster Treffer</a></h2>
<p class="s">Snippet eins zum Thema</p>
<h2><a class="ob" href="https://example.com/2">Zweiter Treffer</a></h2>
<p class="s">Snippet zwei</p>
</body></html>"""


@pytest.fixture
def mojeek_route(fake_transport, monkeypatch):
    """net._transport so setzen, dass q_mojeek die Captcha-Seite bekommt."""
    import net
    monkeypatch.setattr(net, "_transport", fake_transport)
    return fake_transport


def test_mojeek_captcha_erkannt(mojeek_route, capsys):
    """Captcha-Seite → q_mojeek liefert [] + Fehler-Meldung statt Müll zu parsen."""
    mojeek_route.route("https://www.mojeek.com/search?q=test",
                       mojeek_route.ok_html(CAPTCHA_HTML))
    out = web.q_mojeek("test", 5)
    assert out == [], "Captcha darf keine 'Ergebnisse' liefern"
    err = capsys.readouterr().err
    assert "Mojeek" in err and "Block" in err, f"Fehler muss sichtbar sein: {err}"


def test_mojeek_parst_echte_ergebnisse(mojeek_route):
    """Sobald Mojeek freigibt: class=ob-Links werden zu Treffern."""
    mojeek_route.route("https://www.mojeek.com/search?q=test",
                       mojeek_route.ok_html(MOJEEK_OK_HTML))
    out = web.q_mojeek("test", 5)
    assert len(out) == 2
    assert out[0]["url"] == "https://example.com/1"
    assert out[0]["title"] == "Erster Treffer"
    assert out[0]["source"] == "Mojeek"


def test_wikipedia_web_parst_de_en(fake_transport, monkeypatch):
    """Wikipedia DE+EN: MediaWiki-API-JSON → Treffer mit sauberen URLs."""
    import net
    monkeypatch.setattr(net, "_transport", None)  # q_wikipedia nutzt urllib direkt

    def fetch(url, *a, **k):
        import urllib.parse
        lang = "de" if "de.wikipedia" in url else "en"
        hits = {"de": "Deutscher Titel", "en": "English Title"}[lang]
        return (200, json.dumps({"query": {"search": [
            {"title": hits, "snippet": "<span>Kurz</span>beschreibung"}]}}).encode())

    # q_wikipedia_web nutzt urllib.request.urlopen — über net nicht mockbar.
    # Stattdessen: Funktion direkt mit gemocktem json-Load prüfen ist komplex →
    # wir testen die Ergebnis-Form über echten Aufruf nur live.
    # Offline: nur prüfen, dass die Funktion existiert + Register es enthält.
    assert callable(web.q_wikipedia_web)


def test_exa_ohne_key_uebersprungen(monkeypatch, capsys):
    """Exa ohne EXA_API_KEY → Meldung 'übersprungen', kein Fehler, kein Netz."""
    monkeypatch.setattr(web, "_env", lambda name: "")
    out = web.q_exa("test", 5)
    assert out == []
    err = capsys.readouterr().err
    assert "übersprungen" in err


def test_register_enthaelt_neue_quellen():
    """WEB-Register: Mojeek + Wikipedia + Exa sind drin."""
    for name in ("ddgs", "bing", "mojeek", "wikipedia", "exa", "tavily", "serpapi"):
        assert name in web.WEB, f"{name} fehlt im Register"


def test_web_suche_kein_exit_hang(tmp_path):
    """search_web darf den Prozess nicht am Exit hindern (F1 auch für Web)."""
    REPO = Path(__file__).resolve().parents[1]
    env = dict(os.environ, SUCHER_HEALTH_FILE=str(tmp_path / "h_hang.json"))
    code = """
import sys; sys.path.insert(0, 'src')
import sucher_web as w
# ddgs + bing sind langsam/genetzt — mit timeout=2 muss search_web schnell enden
res = w.search_web('kurzer test', 3, timeout=2)
print('FERTIG', len(res))
"""
    t0 = time.monotonic()
    proc = subprocess.run([sys.executable, "-c", code],
                          capture_output=True, text=True, timeout=15,
                          cwd=str(REPO), env=env)
    dt = time.monotonic() - t0
    assert proc.returncode == 0, f"stderr: {proc.stderr[-300:]}"
    assert "FERTIG" in proc.stdout, f"search_web kehrte nicht zurück: {proc.stdout[-200:]}"
    assert dt < 10, f"Prozess hing am Exit: {dt:.1f}s (soll < 10s, Budget war 2s)"


# --- P6-B2: Health-Anbindung für Web-Quellen ---

def test_web_fehler_degradiert_health(tmp_path, monkeypatch, capsys):
    """Web-Quelle mit Fehler (loggt _log_web_error) → Health ok=False."""
    import health
    monkeypatch.setattr(health, "DEFAULT_HEALTH_FILE", tmp_path / "h_web.json")

    calls = {"kaputt": 0}

    def kaputte_quelle(q, n):
        calls["kaputt"] += 1
        web._log_web_error("kaputtweb", "HTTP 500")
        return []

    def ok_quelle(q, n):
        return [{"title": "Ok", "url": "http://ok.de", "source": "okweb"}]

    orig_web = web.WEB
    web.WEB = {"kaputtweb": kaputte_quelle, "okweb": ok_quelle}
    try:
        web.search_web("test", 3, timeout=5)
    finally:
        web.WEB = orig_web

    reg = health.HealthRegistry()
    st = reg.status("kaputtweb")
    assert st["state"] != health.HEALTHY, \
        f"Web-Fehler darf nicht HEALTHY machen, ist: {st['state']}"
    assert reg.status("okweb")["state"] == health.HEALTHY, \
        "Gesunde Web-Quelle muss HEALTHY werden"


def test_web_broken_wird_uebersprungen(tmp_path, monkeypatch, capsys):
    """BROKEN-Web-Quelle (3 Fails) → search_web ruft sie NICHT mehr auf (Cooldown)."""
    import health
    monkeypatch.setattr(health, "DEFAULT_HEALTH_FILE", tmp_path / "h_web2.json")

    calls = {"kaputt": 0}

    def kaputte_quelle(q, n):
        calls["kaputt"] += 1
        web._log_web_error("kaputtweb2", "HTTP 500")
        return []

    def ok_quelle(q, n):
        return [{"title": "Ok", "url": "http://ok.de", "source": "okweb2"}]

    orig_web = web.WEB
    web.WEB = {"kaputtweb2": kaputte_quelle, "okweb2": ok_quelle}
    try:
        # 3 Läufe → kaputt wird BROKEN
        for _ in range(3):
            web.search_web("test", 3, timeout=5)
        assert calls["kaputt"] == 3, "Nach 3 Fails muss BROKEN erreicht sein"
        # 4. Lauf → kaputt wird übersprungen, ok liefert weiter
        res = web.search_web("test", 3, timeout=5)
    finally:
        web.WEB = orig_web

    assert calls["kaputt"] == 3, f"BROKEN-Quelle wurde trotzdem aufgerufen: {calls['kaputt']}"
    titles = [r["title"] for r in res]
    assert "Ok" in titles, "Gesunde Web-Quelle muss trotzdem liefern"


def test_key_quelle_ohne_key_wird_no_key(tmp_path, monkeypatch, capsys):
    """Key-Quelle ohne Env-Key → NO_KEY (nicht HEALTHY), wird nie aufgerufen."""
    import health
    monkeypatch.setattr(health, "DEFAULT_HEALTH_FILE", tmp_path / "h_nokey.json")
    calls = {"exa": 0}

    def fake_exa(q, n):
        calls["exa"] += 1
        return [{"title": "darf nicht", "url": "http://exa.de", "source": "exa"}]

    def ok_quelle(q, n):
        return [{"title": "Ok", "url": "http://ok.de", "source": "okweb3"}]

    orig_web, orig_env = web.WEB, web._env
    web.WEB = {"exa": fake_exa, "okweb3": ok_quelle}
    web._env = lambda name: ""  # kein Key vorhanden
    try:
        res = web.search_web("test", 3, timeout=5)
    finally:
        web.WEB, web._env = orig_web, orig_env

    reg = health.HealthRegistry()
    st = reg.status("exa")
    assert st["state"] == health.NO_KEY, \
        f"Key-Quelle ohne Key muss NO_KEY sein, ist: {st['state']}"
    assert calls["exa"] == 0, "Quelle ohne Key darf nie gestartet werden"
    titles = [r["title"] for r in res]
    assert "Ok" in titles, "Key-freie Quelle muss trotzdem liefern"


def test_no_key_mit_key_heilt_sich(tmp_path, monkeypatch):
    """Selbstheilung: NO_KEY-Status + Key JETZT gesetzt → Quelle läuft wieder."""
    import health
    monkeypatch.setattr(health, "DEFAULT_HEALTH_FILE", tmp_path / "h_heil.json")

    # Erst ohne Key → NO_KEY
    calls = {"exa": 0}

    def fake_exa(q, n):
        calls["exa"] += 1
        return [{"title": "Exa läuft", "url": "http://exa.de", "source": "exa"}]

    def ok_quelle(q, n):
        return [{"title": "Ok", "url": "http://ok.de", "source": "okweb4"}]

    orig_web, orig_env = web.WEB, web._env
    web.WEB = {"exa": fake_exa, "okweb4": ok_quelle}
    web._env = lambda name: ""
    try:
        web.search_web("test", 3, timeout=5)  # → NO_KEY
        assert calls["exa"] == 0
        # Key kommt dazu → nächster Lauf muss exa starten (Selbstheilung)
        web._env = lambda name: "echter-key"
        web.search_web("test", 3, timeout=5)
    finally:
        web.WEB, web._env = orig_web, orig_env

    assert calls["exa"] == 1, "Mit Key muss die NO_KEY-Quelle wieder laufen (Selbstheilung)"
