"""Block 13 — Quellen-Transparenz: X von Y Quellen lieferten + Diagnose-API."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import sucher_universal as uni
import sucher_web as web


def test_web_diagnose_nach_fanout(fake_transport, monkeypatch):
    """search_web füllt web_diagnose(): geliefert ≤ aktiv."""
    import net
    monkeypatch.setattr(net, "_transport", fake_transport)
    monkeypatch.setattr(net, "_try_proxy", lambda *a, **k: None)
    monkeypatch.setattr(net, "_try_proxy_post", lambda *a, **k: None)

    def ok_quelle(q, n):
        return [{"title": f"T{i}", "url": f"http://ok{i}.de", "source": "OK"}
                for i in range(2)]

    def leere_quelle(q, n):
        return []

    orig = web.WEB
    web.WEB = {"ok1": ok_quelle, "ok2": ok_quelle, "leer": leere_quelle}
    try:
        res = web.search_web("test", 3, timeout=5)
    finally:
        web.WEB = orig
    diag = web.web_diagnose()
    assert diag["geliefert"] == 2, f"2 Quellen lieferten: {diag}"
    assert diag["aktiv"] == 3, f"3 waren aktiv: {diag}"
    assert len(res) >= 2


def test_universal_diagnose_nach_fanout(fake_transport, monkeypatch):
    """search() füllt diagnose(): geliefert ≤ aktiv."""
    import net
    monkeypatch.setattr(net, "_transport", fake_transport)
    monkeypatch.setattr(net, "_try_proxy", lambda *a, **k: None)
    monkeypatch.setattr(net, "_try_proxy_post", lambda *a, **k: None)

    def ok_quelle(q, n):
        return [{"title": "T", "url": "http://ok.de", "source": "OK",
                 "is_oa": True}]

    def leere_quelle(q, n):
        return []

    orig_sci, orig_gen = uni.SCI, uni.GENERAL
    uni.SCI, uni.GENERAL = {"ok": ok_quelle}, {"leer": leere_quelle}
    try:
        uni.search("test", 3, mode="universal", expand=False)
    finally:
        uni.SCI, uni.GENERAL = orig_sci, orig_gen
    diag = uni.diagnose()
    assert diag["geliefert"] >= 1, f"ok-Quelle muss gezählt sein: {diag}"
    assert diag["aktiv"] >= 2


def test_diagnose_keys_vorhanden():
    """Diagnose-Dicts haben immer die erwarteten Schlüssel (kein Crash)."""
    d1 = uni.diagnose()
    d2 = web.web_diagnose()
    for d in (d1, d2):
        assert "geliefert" in d and "aktiv" in d and "abgeschlossen" in d
