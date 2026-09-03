"""TTL-Cache (Shiraberu-Übernahme): Treffer/Miss/TTL/Roundtrip."""
import json
import sys
import time
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import cache as cache_mod


@pytest.fixture
def c(tmp_path):
    """Frischer Cache in tmp-DB."""
    db = tmp_path / "cache_test.db"
    cache_mod.clear(db)
    return db


def test_put_get_roundtrip(c):
    res = [{"title": "Treffer", "url": "http://x.de", "source": "ddgs"}]
    cache_mod.put("ddgs", "test query", 8, res, db_path=c)
    back = cache_mod.get("ddgs", "test query", 8, db_path=c)
    assert back == res, f"Roundtrip kaputt: {back}"


def test_miss_bei_anderer_query(c):
    cache_mod.put("ddgs", "query A", 8, [{"title": "A", "url": "http://a.de"}], db_path=c)
    assert cache_mod.get("ddgs", "query B", 8, db_path=c) is None


def test_miss_bei_anderer_quelle(c):
    cache_mod.put("ddgs", "query", 8, [{"title": "A", "url": "http://a.de"}], db_path=c)
    assert cache_mod.get("bing", "query", 8, db_path=c) is None


def test_ttl_ablauf(c):
    res = [{"title": "Alt", "url": "http://a.de"}]
    cache_mod.put("ddgs", "query", 8, res, db_path=c)
    # TTL = -1 → sofort abgelaufen
    assert cache_mod.get("ddgs", "query", 8, ttl_s=-1, db_path=c) is None
    # Normaler TTL → Treffer
    assert cache_mod.get("ddgs", "query", 8, db_path=c) == res


def test_gross_klein_schreibung_normalisiert(c):
    cache_mod.put("ddgs", "Große Query", 8, [{"title": "X", "url": "http://x.de"}], db_path=c)
    assert cache_mod.get("ddgs", "große query", 8, db_path=c) is not None, \
        "Query-Suche muss case-insensitiv sein"


def test_n_zahlt_zum_key(c):
    cache_mod.put("ddgs", "query", 5, [{"title": "X", "url": "http://x.de"}], db_path=c)
    assert cache_mod.get("ddgs", "query", 8, db_path=c) is None, \
        "n=5 und n=8 sind verschiedene Caches"


def test_cache_fehler_crasht_nicht(tmp_path):
    """Ungültige DB → get gibt None, put crasht nicht."""
    db = tmp_path / "kaputt.db"
    db.write_text("kein sqlite")
    assert cache_mod.get("ddgs", "query", 8, db_path=db) is None
    cache_mod.put("ddgs", "query", 8, [{"title": "X", "url": "http://x.de"}], db_path=db)
    # Nach put mit kaputter Datei: neuer Versuch darf nicht crashen
    cache_mod.get("ddgs", "query", 8, db_path=db)
