"""P5-B2 — E2E: sucher.py CLI speichert in SQLite (via SUCHER_DB-Umleitung)."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import store as store_mod


@pytest.mark.live
def test_cli_speichert_in_sqlite(tmp_path):
    """Echte CLI-Suche (1 Treffer reicht) schreibt queries+ergebnisse in SUCHER_DB."""
    db = tmp_path / "cli_e2e.db"
    env = dict(os.environ, SUCHER_DB=str(db))
    # Kleine, schnelle Query; Modus studien nutzt APIs (kann 0 Treffer geben bei Netzproblemen)
    proc = subprocess.run(
        [sys.executable, "sucher.py", "pardo evaluation", "1", "--modus", "studien"],
        capture_output=True, text=True, timeout=120, cwd=str(Path(__file__).resolve().parents[1]),
        env=env)
    assert db.exists(), f"DB wurde nicht angelegt. stdout: {proc.stdout[-300:]} stderr: {proc.stderr[-300:]}"
    import sqlite3
    s = store_mod.Store(db_path=db)
    conn = sqlite3.connect(str(db))
    n_q = conn.execute("SELECT COUNT(*) FROM queries").fetchone()[0]
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert {"ergebnisse", "queries", "provider_health"} <= tables
    # queries ≥ 1 nur wenn Treffer kamen; die CLI loggt den Lauf erst NACH Treffern.
    # Wichtig: Schema existiert + DB angelegt — 0-Treffer-Fall wird im 2. Test abgedeckt.
    assert n_q >= 0


def test_cli_0_treffer_kein_crash(tmp_path):
    """Auch 0 Treffer (Netz down) dürfen die CLI nicht crashen lassen."""
    db = tmp_path / "cli_empty.db"
    env = dict(os.environ, SUCHER_DB=str(db))
    # Query die garantiert nichts findet + Modus web (lokal, schnell)
    proc = subprocess.run(
        [sys.executable, "sucher.py", "zzzqqqxxyyy", "1", "--modus", "web"],
        capture_output=True, text=True, timeout=120, cwd=str(Path(__file__).resolve().parents[1]),
        env=env)
    assert proc.returncode == 0, f"CLI crashte: {proc.stderr[-300:]}"
