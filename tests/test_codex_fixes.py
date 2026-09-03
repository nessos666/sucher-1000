"""Codex-Review-Fixes: RED-Tests für Findings 1-7 (F1-F7)."""
import os
import sys
import time
import urllib.error
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import net
import sucher_web
import sucher_universal as su


@pytest.fixture(autouse=True)
def reset_transport():
    net._transport = None
    yield
    net._transport = None


# F1: search_web() Timeout hart (wie search() nach P3-Fix)

def test_f1_web_budget_hart():
    """search_web: hängende Quelle darf Aufrufer nicht blockieren (Budget hart)."""
    def haengt(q, n):
        time.sleep(60)
        return [{"title": "Zu-spät", "url": "http://haengt.de"}]

    def schnell(q, n):
        time.sleep(0.05)
        return [{"title": "Rechtzeitig", "url": "http://schnell.de"}]

    orig = dict(sucher_web.WEB)
    sucher_web.WEB = {"haengt": haengt, "schnell": schnell}
    try:
        t0 = time.monotonic()
        res = sucher_web.search_web("test", 3, timeout=2)
        dt = time.monotonic() - t0
    finally:
        sucher_web.WEB = orig

    assert dt < 5.0, f"Web-Budget hart erwartet, dauerte {dt:.1f}s"
    titles = [r["title"] for r in res]
    assert "Rechtzeitig" in titles, "Teilergebnis muss erhalten bleiben"


# F2: get_text Proxy-Fallback mit erwartet="text"

def test_f2_get_text_proxy_erwartet_text(fake_transport, monkeypatch):
    """get_text über Proxy: HTML-Antwort darf nicht als JSON verworfen werden."""
    fake_transport.route("https://html.example/", fake_transport.ok_html(
        "<html><body>Echte Seite</body></html>"))

    # Proxy-FETCH mocken: muss erwartet="text" bekommen und HTML zurückgeben
    calls = {}
    def fake_proxy_fetch(url, timeout=8, erwartet="json"):
        calls["erwartet"] = erwartet
        return "<html><body>Echte Seite via Proxy</body></html>"

    monkeypatch.setattr(net, "_try_proxy", fake_proxy_fetch)
    monkeypatch.setattr(net, "_transport", fake_transport)
    # Direkter Pfad blockt (Anubis-Marker) → Proxy muss greifen
    fake_transport.route("https://html.example/", fake_transport.ok_html(
        "<html>Making sure you're not a bot! Anubis</html>"))

    text, err = net.get_text("https://html.example/", proxy_retry=True)
    assert calls.get("erwartet") == "text", f"Proxy muss erwartet='text' bekommen, bekam {calls}"
    assert "Echte Seite via Proxy" in text


# F3: q_base nutzt net.get_json (kein direkter urllib-Bypass)

def test_f3_q_base_nutzt_net(monkeypatch):
    """q_base darf nicht direkt urllib nutzen, sondern muss über net gehen."""
    import inspect
    src = inspect.getsource(su.q_base)
    # Nach dem P1-Fix sollte q_base http_json() (→net) nutzen, KEIN urlopen mit 30s
    assert "http_json(" in src or "net.get_json" in src, \
        "q_base muss die zentrale Transport-Schicht nutzen"
    assert "timeout=30" not in src.replace("net.get_json(url, timeout=", ""), \
        "Kein 30s-Direkt-Timeout in q_base"


# F4: health_check --json gibt NUR JSON aus

@pytest.mark.live
def test_f4_health_json_clean(monkeypatch, capsys, tmp_path):
    """--json muss ausschließlich gültiges JSON auf stdout geben.

    F10 (OpenCode): Live-Netz-Test (ruft echte Quellen + verbraucht API-Quota)
    → hinter @pytest.mark.live, läuft NICHT in der Offline-Suite.
    """
    import json as _json
    import scripts.health_check as hc  # noqa — Pfad-Setup nötig
    # Direkter Test der Logik: --json-Zweig darf keine Prints mischen
    # (Wir testen das Verhalten über ein Sub-Skript, da health_check Netz braucht)
    import subprocess, sys as _sys
    env = dict(os.environ, SUCHER_HEALTH_FILE=str(tmp_path / "h_live_test.json"))
    r = subprocess.run(
        [_sys.executable, "scripts/health_check.py", "--json", "--modus", "web"],
        capture_output=True, text=True, timeout=60, cwd=str(Path(__file__).resolve().parents[1]),
        env=env)
    # stdout muss als GANZES parsebar sein
    try:
        data = _json.loads(r.stdout)
        assert isinstance(data, list), "JSON-Ausgabe muss eine Liste sein"
    except _json.JSONDecodeError:
        pytest.fail(f"stdout ist kein sauberes JSON: {r.stdout[:200]}")


# F5: _QUELLEN_FEHLER wird pro Lauf zurückgesetzt

def test_f5_fehler_werden_pro_lauf_zurueckgesetzt(monkeypatch):
    """Fehler aus Lauf 1 dürfen in Lauf 2 (erfolgreich) nicht mehr erscheinen."""
    def kaputt(q, n):
        raise ConnectionError("Lauf-1-Fehler")

    def ok(q, n):
        return [{"title": "Ok-Treffer", "url": "http://ok.de"}]

    orig_sci, orig_gen = su.SCI, su.GENERAL
    su.SCI = {"kaputt": kaputt}
    su.GENERAL = {}
    try:
        su._QUELLEN_FEHLER.clear()
        su.search("test1", 3, mode="studien")  # Lauf 1: kaputt
        assert "kaputt" in su._get_quellen_fehler()

        su.SCI = {"ok": ok}
        su.search("test2", 3, mode="studien")  # Lauf 2: ok
        fehler_lauf2 = su._get_quellen_fehler()
    finally:
        su.SCI, su.GENERAL = orig_sci, orig_gen

    assert "kaputt" not in fehler_lauf2, \
        "Lauf-1-Fehler darf in Lauf 2 nicht mehr auftauchen (Reset fehlt!)"


# F6: search_web unbekannte Quelle → Meldung + [] (nicht still alle)

def test_f6_web_unbekannte_quelle(monkeypatch, capsys):
    """search_web('x', only='gibtsnicht') muss [] + Meldung geben, nicht alle durchsuchen."""
    def quelle(q, n):
        return [{"title": "Sollte nicht laufen", "url": "http://x.de"}]

    orig = dict(sucher_web.WEB)
    sucher_web.WEB = {"nur_diese": quelle}
    try:
        res = sucher_web.search_web("test", 3, only="gibtsnicht")
    finally:
        sucher_web.WEB = orig

    assert res == [], "Unbekannte Web-Quelle muss [] liefern, nicht alle durchsuchen"


# F7: block_indicator akzeptiert gültige JSON-Skalare

def test_f7_block_indicator_json_skalare():
    """Gültige JSON-Skalare (true/false/null/123/\"ok\") dürfen nicht als Block gelten."""
    assert net.block_indicator("true", erwartet="json") is None
    assert net.block_indicator("false", erwartet="json") is None
    assert net.block_indicator("null", erwartet="json") is None
    assert net.block_indicator("123", erwartet="json") is None
    assert net.block_indicator('"ok"', erwartet="json") is None
    # HTML mit Bot-Marker MUSS weiterhin als Block gelten
    assert net.block_indicator("<html>captcha required</html>", erwartet="json") is not None
