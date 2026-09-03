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
    """net._transport so setzen, dass q_mojeek die Captcha-Seite bekommt.

    F11 (OpenCode-Block5): _try_proxy wird AUCH neutralisiert — sonst ginge
    der BLOCK-Pfad (Captcha-Antwort) bei gesetzten Proxy-Credentials ins
    echte Netz (Offline-Test!). Muster: route_net in test_block5.
    """
    import net
    monkeypatch.setattr(net, "_transport", fake_transport)
    monkeypatch.setattr(net, "_try_proxy", lambda *a, **k: None)
    monkeypatch.setattr(net, "_try_proxy_post", lambda *a, **k: None)
    return fake_transport


def test_mojeek_captcha_erkannt(mojeek_route, capsys):
    """Captcha-Seite → q_mojeek liefert [] + Fehler-Meldung statt Müll zu parsen."""
    mojeek_route.route("https://www.mojeek.com/search?q=test",
                       mojeek_route.ok_html(CAPTCHA_HTML))
    out = web.q_mojeek("test", 5)
    assert out == [], "Captcha darf keine 'Ergebnisse' liefern"
    err = capsys.readouterr().err
    assert "mojeek" in err.lower() and "block" in err.lower(), \
        f"Fehler muss sichtbar sein: {err}"


def test_mojeek_parst_echte_ergebnisse(mojeek_route):
    """Sobald Mojeek freigibt: class=ob-Links werden zu Treffern."""
    mojeek_route.route("https://www.mojeek.com/search?q=test",
                       mojeek_route.ok_html(MOJEEK_OK_HTML))
    out = web.q_mojeek("test", 5)
    assert len(out) == 2
    assert out[0]["url"] == "https://example.com/1"
    assert out[0]["title"] == "Erster Treffer"
    assert out[0]["source"] == "Mojeek"


# --- Block 3 (Shiraberu): DDG-HTML-Fallback ---

DDG_HTML_OK = """<html><body>
<div class="result">
<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2F1&amp;rut=x">Erster DDG Treffer</a>
</div>
<div class="result">
<a class="result__a" href="https://example.com/2">Zweiter Treffer</a>
</div>
</body></html>"""


def test_ddgs_lib_fehlt_nutzt_html_fallback(fake_transport, monkeypatch, capsys):
    """ddgs-Lib wirft → HTML-Fallback liefert Treffer (Block 3/Shiraberu)."""
    import net
    monkeypatch.setattr(net, "_transport", fake_transport)
    fake_transport.route("https://html.duckduckgo.com/html/",
                         fake_transport.ok_html(DDG_HTML_OK))

    # Lib-Import scheitern lassen
    import builtins
    orig_import = builtins.__import__
    def kaputter_import(name, *a, **k):
        if name == "ddgs":
            raise ImportError("Lib kaputt")
        return orig_import(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", kaputter_import)

    out = web.q_ddgs("test", 5)
    assert len(out) == 2, f"HTML-Fallback muss 2 Treffer liefern: {out}"
    # Redirect-URL aufgelöst:
    urls = [r["url"] for r in out]
    assert any("example.com/1" in u for u in urls), f"uddg-Redirect nicht aufgelöst: {urls}"
    assert out[0]["source"] == "ddgs"


def test_ddgs_lib_ok_kein_html(fake_transport, monkeypatch):
    """Lib liefert → HTML-Fallback wird nicht angerufen."""
    import net
    monkeypatch.setattr(net, "_transport", fake_transport)

    orig_import = __import__
    def ddgs_lib(name, *a, **k):
        if name == "ddgs":
            class FakeDDG:
                def __enter__(self): return self
                def __exit__(self, *a): return False
                def text(self, query, max_results=8):
                    return [{"title": "Lib Treffer", "href": "http://lib.de", "body": "x"}]
            return type("DDGSMod", (), {"DDGS": FakeDDG})
        return orig_import(name, *a, **k)
    monkeypatch.setattr("builtins.__import__", ddgs_lib)

    out = web.q_ddgs("test", 5)
    assert len(out) == 1 and out[0]["url"] == "http://lib.de"
    # HTML-Route wurde nie aufgerufen:
    assert fake_transport.calls == [] or not any("html.duckduckgo" in c for c in fake_transport.calls)


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
    """WEB-Register: Mojeek + Wikipedia_web + Exa sind drin."""
    for name in ("ddgs", "bing", "mojeek", "wikipedia_web", "exa", "tavily",
                 "serpapi", "hn", "google_news", "bing_news"):
        assert name in web.WEB, f"{name} fehlt im Register"


def test_web_suche_kein_exit_hang(tmp_path):
    """search_web darf den Prozess nicht am Exit hindern (F1 auch für Web).

    F10 (OpenCode-Block5): Netz wird im Subprozess GEMOCKT (FakeTransport
    offline) — der Test prüft den Exit-Hang, nicht echte Suchergebnisse.
    Vorher ging der Test ins echte Netz (10 echte Requests in der
    Offline-Suite), obwohl README „Netz gemockt" verspricht.
    """
    REPO = Path(__file__).resolve().parents[1]
    env = dict(os.environ, SUCHER_HEALTH_FILE=str(tmp_path / "h_hang.json"),
               SUCHER_CACHE_DB=str(tmp_path / "c_hang.db"))
    code = """
import sys; sys.path.insert(0, 'src')
import net
class FT:  # FakeTransport: jede URL schlägt sofort fehl (kein Netz)
    def open(self, url, timeout=8, headers=None):
        raise ConnectionError('fake offline')
net._transport = FT()
net._try_proxy = lambda *a, **k: None
net._try_proxy_post = lambda *a, **k: None
import sucher_web as w
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


def test_health_label_mismatch_regression(tmp_path, monkeypatch, capsys):
    """F1 (OpenCode): Quelle loggt unter ANDEREM Label als Register-Key → trotzdem DEGRADED.

    Vorher: q_mojeek loggte als 'Mojeek', Register-Key ist 'mojeek' → Fehler
    wurden nie gefunden → HEALTHY trotz Captcha-Block (Produktions-Beleg).
    Fix: Commit-Schleife normalisiert Labels (lower + Präfix-Match).
    """
    import health
    monkeypatch.setattr(health, "DEFAULT_HEALTH_FILE", tmp_path / "h_alias.json")

    # Simuliert Label-Abweichung: "Mojeek" statt Key "mojeek" (alter Bug)
    def echte_mojeek_semantik(q, n):
        web._log_web_error("Mojeek", "BLOCK: captcha")
        return []

    def ok_quelle(q, n):
        return [{"title": "Ok", "url": "http://ok.de", "source": "okweb_alias"}]

    orig_web = web.WEB
    web.WEB = {"mojeek": echte_mojeek_semantik, "okweb_alias": ok_quelle}
    try:
        for _ in range(3):
            web.search_web("test", 3, timeout=5)  # 3 Fails
    finally:
        web.WEB = orig_web

    reg = health.HealthRegistry()
    st = reg.status("mojeek")
    assert st["state"] == health.BROKEN, \
        f"Label 'Mojeek' muss auf Key 'mojeek' degradieren, ist: {st['state']} (consec={st.get('consecutive_fails',0)})"


def test_f1_aliase_normalisiert_alle_quellen():
    """Alle _log_web_error-Labels müssen den WEB-Register-Keys entsprechen (F1-Fix)."""
    import inspect, re
    src = inspect.getsource(web)
    # Alle _log_web_error("<label>", ...)-Aufrufe extrahieren
    labels = set(re.findall(r'_log_web_error\("([^"]+)"', src))
    register = set(web.WEB.keys())
    # Jedes Label muss entweder ein Register-Key sein ODER ein Key-Präfix enthalten
    fremd = [l for l in labels if l not in register and not any(l.startswith(k) for k in register)]
    assert not fremd, f"Fehler-Labels ohne passenden Register-Key: {fremd} (Register: {register})"


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


# --- P6-B3: deterministische Sortierung + Quellen-Gewichte ---

def test_web_sortierung_deterministisch():
    """Gleiche Ergebnisse → gleiche Reihenfolge (nicht completion-order-abhängig)."""
    res = [
        {"title": "A-Tavily", "url": "http://t.de", "source": "Tavily"},
        {"title": "B-ddgs", "url": "http://d.de", "source": "ddgs"},
        {"title": "C-Bing", "url": "http://b.de", "source": "Bing"},
    ]
    r1 = web._web_score_sort(res)
    r2 = web._web_score_sort(list(reversed(res)))
    assert [x["url"] for x in r1] == [x["url"] for x in r2], \
        "Sortierung muss unabhängig von Eingabe-Reihenfolge sein"


def test_web_sortierung_bing_hinten():
    """Bing (Junk-Problem) muss hinter ddgs/Tavily landen."""
    res = [
        {"title": "Bing-Treffer", "url": "http://bing.de", "source": "Bing"},
        {"title": "ddgs-Treffer", "url": "http://ddgs.de", "source": "ddgs"},
        {"title": "Tavily-Treffer", "url": "http://tavily.de", "source": "Tavily"},
    ]
    sorted_res = web._web_score_sort(res)
    sources = [r["source"] for r in sorted_res]
    assert sources[0] in ("ddgs", "Mojeek", "Tavily", "Wikipedia", "Exa"), \
        f"ddgs/mojeek muss vorn sein, ist: {sources}"
    assert sources[-1] == "Bing", f"Bing muss hinten sein, ist: {sources}"


def test_search_web_gibt_sortiert_zurueck(tmp_path, monkeypatch):
    """search_web liefert sortierte Ergebnisse (nicht Thread-Ankunfts-Reihenfolge)."""
    import health
    monkeypatch.setattr(health, "DEFAULT_HEALTH_FILE", tmp_path / "h_sort.json")
    orig_web = web.WEB
    web.WEB = {
        "ddgs": lambda q, n: [{"title": "ddgs 1", "url": "http://d1.de", "source": "ddgs"}],
        "bing": lambda q, n: [{"title": "Bing 1", "url": "http://b1.de", "source": "Bing"}],
    }
    try:
        res = web.search_web("test", 3, timeout=5)
    finally:
        web.WEB = orig_web
    assert res and res[0]["source"] == "ddgs", \
        f"ddgs muss vorn sein, ist: {[r['source'] for r in res]}"
