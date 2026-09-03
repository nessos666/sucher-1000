"""OpenCode-6-10-Fixes: RED-Tests für M1 (Teiltreffer), M2 (Marker), M5 (Präfix)."""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import net
import sucher_universal as uni
import sucher_web as web


@pytest.fixture
def route_net(fake_transport, monkeypatch):
    monkeypatch.setattr(net, "_transport", fake_transport)
    monkeypatch.setattr(net, "_try_proxy", lambda *a, **k: None)
    monkeypatch.setattr(net, "_try_proxy_post", lambda *a, **k: None)
    return fake_transport


# --- M1: universaler Fanout verwirft err_lokal-Teiltreffer ---

def test_m1_err_lokal_teiltreffer_bleiben(monkeypatch, tmp_path):
    """Quelle loggt Fehler (DE tot) liefert aber Treffer (EN) → Treffer bleiben."""
    import health
    monkeypatch.setattr(health, "DEFAULT_HEALTH_FILE", tmp_path / "h_m1.json")

    def halb_kaputt(q, n):
        uni._log_quellenfehler("wikimix", "de-lang tot")
        return [{"title": "En-Treffer", "url": "http://e.de", "source": "Wikipedia"}]

    orig_sci, orig_gen = uni.SCI, uni.GENERAL
    uni.SCI, uni.GENERAL = {}, {"wikimix": halb_kaputt}
    try:
        res = uni.search("test", 3, mode="universal")
    finally:
        uni.SCI, uni.GENERAL = orig_sci, orig_gen
    assert any("En-Treffer" in r["title"] for r in res), \
        f"M1: Teiltreffer ging verloren: {res}"
    # Health: Fehler + Treffer → NICHT healthy (F15)
    reg = health.HealthRegistry()
    assert reg.status("wikimix")["state"] != "HEALTHY", \
        "Quelle mit Fehler darf nicht HEALTHY sein"


# --- M2: block_indicator(text) killt echte Treffer-Seiten nicht ---

def test_m2_ergebnisseite_mit_marker_wort_kein_block():
    """Ergebnisseite mit 'Anomaly detection'-Titeln + vielen Links ≠ Botwall."""
    html = "<html><body><h3>Anomaly detection in network traffic</h3>" + \
           "".join(f'<a href="https://site{i}.de/artikel">Treffer {i}</a>'
                   for i in range(10)) + "</body></html>"
    grund = net.block_indicator(html.encode(), erwartet="text")
    assert grund is None, f"M2: echte Ergebnisseite als Block: {grund}"


def test_m2_botwall_ohne_links_bleibt_block():
    """Kompakte Botwall ohne Links → weiterhin BLOCK erkannt."""
    botwall = "<html><head><title>Just a moment...</title></head><body>" + \
              "Checking your browser... Enable JavaScript and cookies" + \
              "</body></html>"
    grund = net.block_indicator(botwall.encode(), erwartet="text")
    assert grund is not None, "M2: Botwall muss weiter erkannt werden"


# --- M5: Präfix-Alias maskiert Fehler (bing vs. bing_news) ---

def test_m5_bing_prefix_maskiert_bing_news_nicht():
    """bing_news-Fehler darf den Zähler von bing NICHT erhöhen."""
    web._WEB_FEHLER.clear()
    web._log_web_error("bing_news", "BLOCK")
    assert web._web_fehler_count("bing") == 0, \
        "M5: bing_news-Fehler darf bing-Zähler nicht erhöhen"
    assert web._web_fehler_count("bing_news") == 1


# --- M4: q_wikis respektiert n (Regression via Fanout) ---

def test_m4_wikis_n_cap(route_net):
    """q_wikis mit n=2 → höchstens 2 Treffer trotz 6 Sub-Projekten."""
    mw = {"query": {"search": [{"title": f"Seite{i}"} for i in range(5)]}}
    for proj in ("de.wikiquote.org", "en.wikiquote.org", "de.wikinews.org",
                 "en.wikinews.org", "de.wikisource.org", "en.wikisource.org"):
        route_net.route(f"https://{proj}/w/api.php", route_net.ok_json(mw))
    out = web.q_wikis("linux", 2)
    assert len(out) <= 2, f"M4: n=2 lieferte {len(out)} Treffer"
