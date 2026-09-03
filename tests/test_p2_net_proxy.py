"""P2 — Transport-Härtung: 200≠Erfolg, Block-Erkennung, Proxy-Retry."""
import json
import sys
import urllib.error
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import net
import proxy


@pytest.fixture(autouse=True)
def reset_transport():
    net._transport = None
    yield
    net._transport = None


# ---------- 200 ≠ Erfolg ----------

def test_200_html_statt_json_ist_fehler(fake_transport, monkeypatch):
    """BASE-Falle: 200 + HTML auf JSON-URL muss als Fehler gelten, nicht als leeres JSON."""
    fake_transport.route("https://base.example/", fake_transport.ok_html(
        "<html><body>Making sure you're not a bot! Anubis</body></html>"))
    monkeypatch.setattr(net, "_transport", fake_transport)

    res = net.get_json("https://base.example/search?format=json")
    assert "_error" in res
    assert "FORMAT" in res["_error"] or "BLOCK" in res["_error"], f"Erwartet Block-Error, bekam: {res}"


def test_200_echtes_json_ok(fake_transport, monkeypatch):
    """Echtes JSON mit 200 = Erfolg."""
    fake_transport.route("https://ok.example/", fake_transport.ok_json({"results": [1]}))
    monkeypatch.setattr(net, "_transport", fake_transport)

    res = net.get_json("https://ok.example/search")
    assert res == {"results": [1]}


def test_429_retry_dann_ok(fake_transport, monkeypatch):
    """429 → Retry mit Backoff → Erfolg. Fake zählt Aufrufe."""
    fake = fake_transport
    calls = {"n": 0}

    class Flaky:
        def open(self, url, timeout=8):
            calls["n"] += 1
            if calls["n"] == 1:
                raise fake.err(429)
            return fake.ok_json({"results": ["nach-retry"]})

    monkeypatch.setattr(net, "_transport", Flaky())
    res = net.get_json("https://flaky.example/")
    assert res == {"results": ["nach-retry"]}
    assert calls["n"] >= 2


def test_block_indicator_erkennt_captcha():
    assert net.block_indicator("<html>captcha required</html>", erwartet="text") is not None
    assert net.block_indicator('{"results": []}', erwartet="json") is None
    assert net.block_indicator("<html>normal page</html>", erwartet="json") is not None


# ---------- Proxy ----------

def test_proxy_verfuegbar_nur_mit_env(monkeypatch):
    """Ohne Env-Credentials: nicht verfügbar, kein Crash."""
    monkeypatch.setenv("PROXY_LOGIN", "")
    monkeypatch.setenv("PROXY_PASSWORD", "")
    # .env nicht lesen können → wir mocken _env direkt
    monkeypatch.setattr(proxy, "_env", lambda name: "")
    assert proxy.available() is False
    assert proxy.fetch("https://x.example/") is None


def test_proxy_kein_importfehler_wenn_net_ohne_proxy():
    """net._try_proxy darf nie crashen, wenn proxy fehlt/kaputt."""
    res = net._try_proxy("https://x.example/", 5)
    assert res is None  # kein Proxy → None, kein Exception
