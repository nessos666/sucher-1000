#!/usr/bin/env python3
"""
SUCHER — store.py (P5): SQLite-Persistenz
==========================================
Ergebnis-Archiv + Laufprotokoll in EINER SQLite-Datei — ablösung des
JSON-Datei-Chaos (ergebnis_*.json bleibt als Export erhalten, aber die DB
ist die Source of Truth).

Tabellen:
  ergebnisse  — ein Treffer je Zeile (query, quelle, title, url, year, ...)
  queries     — ein Suchlauf je Zeile (query, modus, n, ts, treffer)
  provider_health — Health-Status je Quelle (persistente Tabelle statt JSON)

Regeln (Skill: davids-build-methodology):
  - SQLite als Source of Truth, YAML/JSON nur Export
  - Atomare Transaktionen (BEGIN IMMEDIATE → COMMIT/ROLLBACK)
  - INSERT OR REPLACE VERBOTEN für versionierte Daten → UNIQUE + Existenzprüfung
  - UNIQUE(query, url) gegen Duplikate
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
# Env-Override für Tests/Portabilität: SUCHER_DB=/pfad/zur.db
DEFAULT_DB = Path(os.environ.get("SUCHER_DB", str(BASE / "data" / "sucher.db")))

SCHEMA = """
CREATE TABLE IF NOT EXISTS ergebnisse (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    quelle TEXT NOT NULL,
    title TEXT,
    url TEXT,
    year INTEGER,
    doi TEXT,
    is_oa INTEGER DEFAULT 0,
    pdf TEXT,
    snippet TEXT,
    json TEXT,
    ts TEXT NOT NULL,
    UNIQUE(query, url)
);
CREATE TABLE IF NOT EXISTS queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    modus TEXT,
    n INTEGER,
    treffer INTEGER,
    ts TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS provider_health (
    source TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    consecutive_fails INTEGER DEFAULT 0,
    ok_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    last_ok_ts TEXT,
    last_fail_ts TEXT,
    last_error TEXT,
    cooldown_until TEXT
);
"""


def _connect(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


class Store:
    """SQLite-Persistenz für Suchergebnisse + Laufprotokoll."""

    def __init__(self, db_path=None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self):
        conn = _connect(self.db_path)
        try:
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()

    # ---------- Schreiben (atomar) ----------

    def save_ergebnisse(self, query: str, results: list):
        """Einen Suchlauf + alle Treffer atomar speichern. Dedup via UNIQUE(query, url)."""
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        conn = _connect(self.db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO queries (query, modus, n, treffer, ts) VALUES (?,?,?,?,?)",
                (query, "universal", len(results), len(results), ts))
            for r in results:
                url = r.get("url") or ""
                if not url:
                    continue  # ohne URL nicht sinnvoll archivierbar
                conn.execute(
                    """INSERT OR IGNORE INTO ergebnisse
                       (query, quelle, title, url, year, doi, is_oa, pdf, snippet, json, ts)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (query,
                     r.get("source", ""),
                     (r.get("title") or "")[:500],
                     url[:1000],
                     r.get("year"),
                     (r.get("doi") or "")[:200],
                     1 if (r.get("is_oa") or r.get("pdf")) else 0,
                     (r.get("pdf") or "")[:1000],
                     (r.get("snippet") or "")[:1000],
                     json.dumps(r, ensure_ascii=False)[:5000],
                     ts))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def save_health(self, health_data: dict):
        """Health-Registry in Tabelle spiegeln (pro Quelle eine Zeile)."""
        conn = _connect(self.db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            for source, entry in health_data.items():
                conn.execute(
                    """INSERT OR REPLACE INTO provider_health
                       (source, state, consecutive_fails, ok_count, fail_count,
                        last_ok_ts, last_fail_ts, last_error, cooldown_until)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (source,
                     entry.get("state", "UNKNOWN"),
                     entry.get("consecutive_fails", 0),
                     entry.get("ok_count", 0),
                     entry.get("fail_count", 0),
                     entry.get("last_ok_ts"),
                     entry.get("last_fail_ts"),
                     (entry.get("last_error") or "")[:300],
                     entry.get("cooldown_until")))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ---------- Lesen ----------

    def letzte_ergebnisse(self, query: str, limit: int = 20) -> list:
        conn = _connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM ergebnisse WHERE query=? ORDER BY id DESC LIMIT ?",
                (query, limit)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def health_snapshot(self) -> dict:
        conn = _connect(self.db_path)
        try:
            rows = conn.execute("SELECT * FROM provider_health").fetchall()
            return {r["source"]: dict(r) for r in rows}
        finally:
            conn.close()

    def anzahl_ergebnisse(self) -> int:
        conn = _connect(self.db_path)
        try:
            return conn.execute("SELECT COUNT(*) AS c FROM ergebnisse").fetchone()["c"]
        finally:
            conn.close()
