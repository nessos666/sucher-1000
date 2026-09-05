"""Block 15 — FTS5-Archiv-Suche (D1 aus Tiefen-Recherche).

SQLite FTS5-Volltextindex auf sucher.db: Blitz-Suche über alle archivierten
Ergebnisse (864+), BM25-Ranking, Präfix-Suche, case-insensitiv.
RED zuerst — Funktionen existieren noch nicht.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import store as store_mod


@pytest.fixture
def tmp_store(tmp_path):
    """Frische Store-Instanz auf tmp-DB (kein Produktions-Artefakt)."""
    db = tmp_path / "test_archiv.db"
    return store_mod.Store(db)


def _beispiel_ergebnis(title, snippet="", url="https://x.de/a", quelle="OpenAlex"):
    return {"title": title, "snippet": snippet, "url": url,
            "source": quelle, "year": 2020, "doi": None, "is_oa": True}


# ---------- Migration / Existenz ----------

def test_fts5_tabelle_existiert_nach_init(tmp_store):
    """Nach Store()-Init existiert die FTS5-Tabelle (Migration)."""
    conn = sqlite3.connect(tmp_store.db_path)
    try:
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert "ergebnisse_fts" in names, "FTS5-Tabelle fehlt nach Init"
    finally:
        conn.close()


# ---------- Suchen ----------

def test_archiv_suche_titel_token(tmp_store):
    tmp_store.save_ergebnisse("bentonit", [_beispiel_ergebnis(
        "Bentonite water retention in soil", url="https://a.de/1")], modus="studien")
    treffer = tmp_store.archiv_suche("water")
    assert len(treffer) == 1
    assert treffer[0]["title"] == "Bentonite water retention in soil"


def test_archiv_suche_praefix(tmp_store):
    """'benton' findet 'Bentonite' (Präfix-Suche wie fzf)."""
    tmp_store.save_ergebnisse("bentonit", [_beispiel_ergebnis(
        "Bentonite clay swelling", url="https://a.de/1")])
    treffer = tmp_store.archiv_suche("benton")
    assert len(treffer) == 1


def test_archiv_suche_case_insensitive(tmp_store):
    tmp_store.save_ergebnisse("x", [_beispiel_ergebnis(
        "Posttraumatic Growth EMDR", url="https://a.de/1")])
    assert len(tmp_store.archiv_suche("posttraumatic")) == 1
    assert len(tmp_store.archiv_suche("POSTTRAUMATIC")) == 1


def test_archiv_suche_snippet(tmp_store):
    """Snippet-Text ist durchsuchbar."""
    tmp_store.save_ergebnisse("x", [_beispiel_ergebnis(
        "Random title", snippet="studie über emotional neglect bei kindern",
        url="https://a.de/1")])
    treffer = tmp_store.archiv_suche("neglect")
    assert len(treffer) == 1


def test_archiv_suche_ranking_title_vor_snippet(tmp_store):
    """BM25-Gewichtung: Titel-Treffer rankt vor Snippet-Treffer.

    Zwei konkurrierende Treffer: einer mit 'wasser' im Titel, einer nur im
    Snippet — der Titel-Treffer muss vorne stehen (echtes Ranking, OpenCode-6).
    """
    tmp_store.save_ergebnisse("q", [
        _beispiel_ergebnis("Wasser retention Modell", url="https://a.de/1"),
        _beispiel_ergebnis("Bodenstudie generisch", url="https://a.de/2"),
    ])
    conn = sqlite3.connect(tmp_store.db_path)
    conn.execute("UPDATE ergebnisse SET snippet='wasser retention untersuchung' "
                 "WHERE url='https://a.de/2'")
    conn.commit()
    conn.close()
    treffer = tmp_store.archiv_suche("wasser", limit=10)
    urls = [t["url"] for t in treffer]
    assert "https://a.de/1" in urls and "https://a.de/2" in urls
    # Titel-Treffer (a.de/1) rankt vor Snippet-only (a.de/2)
    assert urls.index("https://a.de/1") < urls.index("https://a.de/2"), urls


def test_archiv_suche_bindestrich_kein_not(tmp_store):
    """'trauma-therapie' darf NICHT als 'trauma NOT therapie' matchen
    (FTS5-Operator-Kollision — OpenCode-Finding 1)."""
    tmp_store.save_ergebnisse("q", [
        _beispiel_ergebnis("Trauma Therapie Kombination", url="https://a.de/1"),
        _beispiel_ergebnis("Trauma ohne Therapieinhalt", url="https://a.de/2"),
    ])
    treffer = tmp_store.archiv_suche("trauma-therapie")
    # beide dürfen kommen (Bindestrich = UND beider Wörter), mind. der Titel-
    # Treffer, der beide Wörter enthält
    assert any(t["url"] == "https://a.de/1" for t in treffer)
    # KEIN stilles NOT: a.de/1 (beide Wörter) darf nie fehlen, wenn a.de/2 da ist
    urls = {t["url"] for t in treffer}
    assert "https://a.de/1" in urls


def test_archiv_suche_nur_not_leer(tmp_store):
    """'!kindheit' allein (kein positiver Begriff) → "" → CLI-Hinweis,
    kein FTS5-Syntaxfehler, kein falsches '0 Treffer'-Ranking."""
    tmp_store.save_ergebnisse("q", [_beispiel_ergebnis("Trauma Studie")])
    assert tmp_store.archiv_suche("!kindheit") == []
    assert tmp_store.archiv_suche("trauma !kindheit") != []  # gemischt = ok



def test_archiv_suche_kein_treffer(tmp_store):
    tmp_store.save_ergebnisse("x", [_beispiel_ergebnis("Hallo Welt")])
    assert tmp_store.archiv_suche("zzzqqqyyy") == []


def test_archiv_suche_leerer_begriff(tmp_store):
    tmp_store.save_ergebnisse("x", [_beispiel_ergebnis("Hallo")])
    assert tmp_store.archiv_suche("") == []


def test_archiv_suche_sonderzeichen_kein_crash(tmp_store):
    """FTS5-Syntaxfehler (Klammern etc.) dürfen nicht crashen — leer zurück."""
    tmp_store.save_ergebnisse("x", [_beispiel_ergebnis("Hallo (Welt)")])
    treffer = tmp_store.archiv_suche("hallo (")
    assert isinstance(treffer, list)


# ---------- Mehrwort-Suche ----------

def test_archiv_suche_mehrere_woerter_und(tmp_store):
    """'water retention' = UND-Verknüpfung (beide Wörter müssen vorkommen)."""
    tmp_store.save_ergebnisse("q", [
        _beispiel_ergebnis("Bentonite water retention soil", url="https://a.de/1"),
        _beispiel_ergebnis("Water quality report", url="https://a.de/2"),
    ])
    treffer = tmp_store.archiv_suche("water retention")
    assert len(treffer) == 1
    assert treffer[0]["url"] == "https://a.de/1"


def test_archiv_suche_ergebnisse_anzahl_waechst(tmp_store):
    assert tmp_store.anzahl_ergebnisse() == 0
    tmp_store.save_ergebnisse("q", [_beispiel_ergebnis("Eins")])
    assert tmp_store.anzahl_ergebnisse() == 1
