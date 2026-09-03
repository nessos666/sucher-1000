"""P5 — SQLite-Persistenz: store.py Roundtrip, Dedup, Health-Spiegelung."""
import json
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import store as store_mod


@pytest.fixture
def st(tmp_path):
    """Frischer Store in tmp-DB (kein Produktions-sucher.db)."""
    return store_mod.Store(db_path=tmp_path / "sucher_test.db")


def test_schema_wird_angelegt(st):
    """Store-Anlage erzeugt alle 3 Tabellen."""
    import sqlite3
    conn = sqlite3.connect(str(st.db_path))
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"ergebnisse", "queries", "provider_health"} <= tables


def test_save_und_lesen_roundtrip(st):
    res = [{"title": "Test-Studie", "url": "http://a.de/1", "source": "OpenAlex",
            "year": 2020, "doi": "10.1/x", "is_oa": True}]
    st.save_ergebnisse("test query", res)
    back = st.letzte_ergebnisse("test query")
    assert len(back) == 1
    assert back[0]["title"] == "Test-Studie"
    assert back[0]["quelle"] == "OpenAlex"


def test_dedup_bei_gleicher_query_url(st):
    """2× gleiche (query, url) → nur 1 Zeile (UNIQUE)."""
    res = [{"title": "Duplikat", "url": "http://dup.de", "source": "A"}]
    st.save_ergebnisse("q", res)
    st.save_ergebnisse("q", res)
    assert st.anzahl_ergebnisse() == 1


def test_verschiedene_queries_getrennt(st):
    st.save_ergebnisse("q1", [{"title": "A", "url": "http://a.de", "source": "A"}])
    st.save_ergebnisse("q2", [{"title": "B", "url": "http://b.de", "source": "B"}])
    assert st.anzahl_ergebnisse() == 2


def test_health_spiegelung(st):
    health_data = {
        "openalex": {"state": "HEALTHY", "consecutive_fails": 0, "ok_count": 5},
        "base": {"state": "BROKEN", "consecutive_fails": 3,
                 "last_error": "HTTP 403", "cooldown_until": "2026-09-04T00:00:00"},
    }
    st.save_health(health_data)
    snap = st.health_snapshot()
    assert snap["openalex"]["state"] == "HEALTHY"
    assert snap["base"]["state"] == "BROKEN"
    assert snap["base"]["consecutive_fails"] == 3


def test_json_feld_enthaelt_volles_result(st):
    res = [{"title": "Voll", "url": "http://v.de", "source": "X",
            "snippet": "langer text", "custom": "feld"}]
    st.save_ergebnisse("q", res)
    back = st.letzte_ergebnisse("q")
    parsed = json.loads(back[0]["json"])
    assert parsed["custom"] == "feld"
    assert parsed["title"] == "Voll"


# --- F8 (OpenCode-Gesamt): Drift, modus, reason ---

def test_modus_wird_gespeichert(st):
    """save_ergebnisse muss modus durchreichen (nicht hart 'universal')."""
    import sqlite3
    st.save_ergebnisse("webquery", [{"title": "A", "url": "http://a.de", "source": "ddgs"}],
                       modus="web")
    conn = sqlite3.connect(str(st.db_path))
    modus = conn.execute("SELECT modus FROM queries WHERE query='webquery'").fetchone()[0]
    conn.close()
    assert modus == "web", f"modus muss 'web' sein, ist: {modus}"


def test_health_drift_wird_bereinigt(st):
    """Verwaiste Health-Zeilen werden beim nächsten save_health gelöscht (F8)."""
    st.save_health({"echte_quelle": {"state": "HEALTHY"}})
    # Alte Zeile 'haengt' (Artefakt) ist noch in der DB
    import sqlite3
    conn = sqlite3.connect(str(st.db_path))
    conn.execute("INSERT INTO provider_health (source, state) VALUES ('haengt', 'HEALTHY')")
    conn.commit()
    conn.close()
    # Nächstes save_health mit nur echten Quellen → Artefakt verschwindet
    st.save_health({"echte_quelle": {"state": "HEALTHY"}})
    snap = st.health_snapshot()
    assert "haengt" not in snap, "Verwaiste Health-Zeile muss gelöscht werden (Drift!)"
    assert "echte_quelle" in snap


def test_health_reason_wird_persistiert(st):
    """NO_KEY-reason darf nicht verloren gehen (F8: reason-Spalte)."""
    st.save_health({"tavily": {"state": "NO_KEY", "reason": "kein Env-Key"}})
    snap = st.health_snapshot()
    assert snap["tavily"]["state"] == "NO_KEY"
    assert snap["tavily"]["reason"] == "kein Env-Key", \
        f"reason muss persistiert werden, ist: {snap['tavily'].get('reason')}"
