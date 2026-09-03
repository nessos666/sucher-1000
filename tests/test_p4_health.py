"""P4 — Health-Registry + Cooldown: BROKEN wird übersprungen, Zustand überlebt Neustart."""
import json
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import health
import sucher_universal as su


@pytest.fixture
def reg(tmp_path):
    """Frische Registry in temp-Datei (kein Produktions-Health-File)."""
    return health.HealthRegistry(path=tmp_path / "health_test.json")


def test_unknown_zu_healthy_nach_ok(reg):
    reg.record_outcome("openalex", ok=True)
    assert reg.status("openalex")["state"] == health.HEALTHY


def test_3_fails_machen_broken_mit_cooldown(reg):
    reg.record_outcome("base", ok=False, error="HTTP 403")
    reg.record_outcome("base", ok=False, error="HTTP 403")
    reg.record_outcome("base", ok=False, error="HTTP 403")
    st = reg.status("base")
    assert st["state"] == health.BROKEN
    assert st.get("cooldown_until"), "BROKEN muss Cooldown haben"


def test_broken_ist_skippable(reg):
    for _ in range(3):
        reg.record_outcome("base", ok=False, error="tot")
    skip, grund = reg.is_skippable("base")
    assert skip is True
    assert "BROKEN" in grund


def test_ok_setzt_broken_zurueck_auf_healthy(reg):
    for _ in range(3):
        reg.record_outcome("base", ok=False, error="tot")
    reg.record_outcome("base", ok=True)  # Erfolg
    st = reg.status("base")
    assert st["state"] == health.HEALTHY
    skip, _ = reg.is_skippable("base")
    assert skip is False


def test_health_ueberlebt_neustart(tmp_path):
    """Status in Datei geschrieben → neues Registry-Objekt liest BROKEN."""
    p = tmp_path / "health_persist.json"
    r1 = health.HealthRegistry(path=p)
    for _ in range(3):
        r1.record_outcome("quelle_x", ok=False, error="kaputt")
    r1.save()

    # Neustart simulieren: frisches Objekt, gleiche Datei
    r2 = health.HealthRegistry(path=p)
    assert r2.status("quelle_x")["state"] == health.BROKEN
    skip, _ = r2.is_skippable("quelle_x")
    assert skip is True


def test_no_key_ist_skippable(reg):
    reg.mark_no_key("serpapi")
    skip, grund = reg.is_skippable("serpapi")
    assert skip is True
    assert "NO_KEY" in grund


def test_cooldown_ablauf_erlaubt_wieder(reg, monkeypatch):
    """Nach Cooldown-Ablauf ist die Quelle wieder erlaubt (nächster Versuch)."""
    for _ in range(3):
        reg.record_outcome("quelle_y", ok=False, error="tot")
    assert reg.is_skippable("quelle_y")[0] is True

    # Cooldown in der Vergangenheit setzen → abgelaufen
    entry = reg._data["quelle_y"]
    entry["cooldown_until"] = "2000-01-01T00:00:00"
    reg._data["quelle_y"] = entry
    skip, _ = reg.is_skippable("quelle_y")
    assert skip is False, "Nach Cooldown-Ablauf muss die Quelle wieder laufen dürfen"


# --- Integration: search() respektiert Health (BROKEN wird nicht aufgerufen) ---

def test_search_skippt_broken_quelle(tmp_path, monkeypatch):
    """BROKEN-Quelle darf in search() NICHT aufgerufen werden."""
    calls = {"n": 0}

    def kaputte_quelle(q, n):
        calls["n"] += 1
        return [{"title": "Hätte nicht laufen sollen", "url": "http://x.de"}]

    def ok_quelle(q, n):
        return [{"title": "Ok", "url": "http://ok.de"}]

    # Default-Health-Position auf tmp umleiten (search() nutzt HealthRegistry())
    monkeypatch.setattr(health, "DEFAULT_HEALTH_FILE", tmp_path / "health_default.json")
    reg = health.HealthRegistry()  # nutzt jetzt die tmp-Default-Position
    for _ in range(3):
        reg.record_outcome("kaputt", ok=False, error="HTTP 500")
    reg.save()

    orig_sci, orig_gen = su.SCI, su.GENERAL
    su.SCI = {"kaputt": kaputte_quelle, "ok": ok_quelle}
    su.GENERAL = {}
    try:
        res = su.search("test", 3, mode="studien", budget_s=10)
    finally:
        su.SCI, su.GENERAL = orig_sci, orig_gen
        monkeypatch.undo()

    assert calls["n"] == 0, "BROKEN-Quelle wurde trotzdem aufgerufen (Cooldown-Skip fehlt!)"
    titles = [r["title"] for r in res]
    assert "Ok" in titles, "Gesunde Quelle muss trotzdem liefern"
