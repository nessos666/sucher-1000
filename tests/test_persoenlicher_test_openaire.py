"""Persönlicher Test-Fund: OpenAIRE pid/title können int statt dict sein."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import sucher_universal as uni


def test_openaire_pid_int_crasht_nicht(fake_transport, monkeypatch, capsys):
    """Realer Live-Fund (Health-Audit): 'int' object has no attribute
    'startswith' — pid-Eintrag war int statt dict mit $. Darf nicht crashen."""
    import net
    monkeypatch.setattr(net, "_transport", fake_transport)
    monkeypatch.setattr(net, "_try_proxy", lambda *a, **k: None)
    monkeypatch.setattr(net, "_try_proxy_post", lambda *a, **k: None)

    # OpenAIRE-JSON mit pid=12345 (int) + title als Einzel-dict
    j = {"response": {"results": {"result": [{"metadata": {
        "oaf:entity": {"oaf:result": {
            "title": {"$": "Trauma Studie"},
            "dateofacceptance": {"$": "2024-01-01"},
            "pid": 12345,
            "creator": {"$": "Miller, J."},
            "journal": {"name": {"$": "Journal X"}}}}}}]}}}
    fake_transport.route("https://api.openaire.eu/search/publications",
                         fake_transport.ok_json(j))
    out = uni.q_openaire("trauma", 5)
    assert len(out) == 1, f"muss 1 Treffer liefern, bekam: {out}"
    assert out[0]["title"] == "Trauma Studie"
    assert out[0]["year"] == 2024
    assert out[0]["doi"] is None, "int-pid ergibt keinen DOI"
    assert "Fehler" not in capsys.readouterr().err
