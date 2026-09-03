#!/usr/bin/env python3
"""
SUCHER — cache.py: TTL-Such-Cache (Shiraberu-Übernahme)
========================================================
Gleiche Query + Quelle binnen TTL (Default 15 Min) wird aus dem Cache
bedient statt das Netz zu fragen. Spart Quota/Blocks bei Wiederhol-Suchen
und macht health_check/check.sh schneller.

SQLite-basiert (keine neue Abhängigkeit), thread-sicher via eigenem Lock
und kurzen Transaktionen. Tabelle:
  cache(key TEXT PRIMARY KEY, payload TEXT, ts REAL)   -- ts = monotonic? Nein:
Wir speichern WALL-CLOCK epoch, damit der Cache Neustarts überlebt.

Muster aus shiraberu (Go): TTL + max-entries. Wir nutzen TTL + optionales
Aufräumen alter Einträge beim Schreiben.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_DB = Path(os.environ.get("SUCHER_CACHE_DB",
                                        str(BASE / "data" / "sucher_cache.db")))
DEFAULT_TTL_S = 900      # 15 Minuten (shiraberu-Default)
MAX_ENTRIES = 2000

_lock = threading.Lock()


def _conn(db_path):
    conn = sqlite3.connect(str(db_path), timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init(db_path):
    conn = _conn(db_path)
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS cache (
            key TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            ts REAL NOT NULL)""")
        conn.commit()
    finally:
        conn.close()


def _key(quelle: str, query: str, n: int) -> str:
    return f"{quelle}|{query.strip().lower()}|{n}"


def get(quelle: str, query: str, n: int = 8, ttl_s: int = DEFAULT_TTL_S,
        db_path=None) -> list | None:
    """Cache-Treffer zurückgeben ODER None (miss/abgelaufen)."""
    try:
        db = Path(db_path) if db_path else DEFAULT_CACHE_DB
        if not db.exists():
            return None
        with _lock:
            conn = _conn(db)
            try:
                row = conn.execute(
                    "SELECT payload, ts FROM cache WHERE key=?",
                    (_key(quelle, query, n),)).fetchone()
            finally:
                conn.close()
        if not row:
            return None
        payload, ts = row
        if time.time() - ts > ttl_s:
            return None  # abgelaufen
        return json.loads(payload)
    except Exception:
        return None  # Cache-Fehler = kein Treffer, nie crashen


def put(quelle: str, query: str, n: int, results: list, db_path=None) -> None:
    """Ergebnis in den Cache schreiben (max-entries trimmen)."""
    try:
        db = Path(db_path) if db_path else DEFAULT_CACHE_DB
        db.parent.mkdir(parents=True, exist_ok=True)
        _init(db)
        key = _key(quelle, query, n)
        payload = json.dumps(results, ensure_ascii=False)
        with _lock:
            conn = _conn(db)
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    "INSERT OR REPLACE INTO cache (key, payload, ts) VALUES (?,?,?)",
                    (key, payload, time.time()))
                # Aufräumen: alte Einträge löschen wenn über MAX_ENTRIES
                conn.execute("""DELETE FROM cache WHERE key IN (
                    SELECT key FROM cache ORDER BY ts DESC LIMIT -1 OFFSET ?)""",
                    (MAX_ENTRIES,))
                conn.commit()
            except Exception:
                conn.rollback()
            finally:
                conn.close()
    except Exception:
        pass  # Cache-Schreiben nie fatal


def clear(db_path=None) -> None:
    """Nur für Tests: Cache leeren."""
    try:
        db = Path(db_path) if db_path else DEFAULT_CACHE_DB
        if not db.exists():
            return
        with _lock:
            conn = _conn(db)
            try:
                conn.execute("DELETE FROM cache")
                conn.commit()
            finally:
                conn.close()
    except Exception:
        pass
