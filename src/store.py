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
    cooldown_until TEXT,
    reason TEXT
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
            # F8: Migration — reason-Spalte für bestehende DBs nachrüsten
            cols = {r[1] for r in conn.execute("PRAGMA table_info(provider_health)")}
            if "reason" not in cols:
                conn.execute("ALTER TABLE provider_health ADD COLUMN reason TEXT")
            # Block 15 (FTS5-Archiv): Volltext-Index über ergebnisse anlegen,
            # falls nicht vorhanden (external content → rebuild aus Tabelle).
            conn.execute(
                """CREATE VIRTUAL TABLE IF NOT EXISTS ergebnisse_fts USING fts5(
                       query, quelle, title, url, doi, snippet,
                       content='ergebnisse', content_rowid='id',
                       tokenize='unicode61')""")
            # Dirty-Tracking: bis wohin ist der FTS-Index gebaut? (OpenCode-4)
            # External-content-FTS spiegelt COUNT/MAX der Quelltabelle → ein
            # Vergleich über die Index-Tabelle selbst ist nicht möglich.
            conn.execute(
                """CREATE TABLE IF NOT EXISTS fts_state (
                       id INTEGER PRIMARY KEY CHECK (id = 1),
                       last_rebuilt_id INTEGER NOT NULL DEFAULT 0)""")
            conn.execute(
                "INSERT OR IGNORE INTO fts_state (id, last_rebuilt_id) VALUES (1, 0)")
            conn.commit()
        finally:
            conn.close()

    # ---------- Schreiben (atomar) ----------

    def save_ergebnisse(self, query: str, results: list, modus: str = "universal"):
        """Einen Suchlauf + alle Treffer atomar speichern. Dedup via UNIQUE(query, url).

        F8 (OpenCode-Gesamt): modus wird durchgereicht (vorher hart 'universal').
        """
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        conn = _connect(self.db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO queries (query, modus, n, treffer, ts) VALUES (?,?,?,?,?)",
                (query, modus, len(results), len(results), ts))
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
        """Health-Registry in Tabelle spiegeln (pro Quelle eine Zeile).

        F8 (OpenCode-Gesamt): löscht Zeilen, die im Registry nicht mehr existieren
        (vorher Drift durch INSERT OR REPLACE ohne Cleanup).
        """
        conn = _connect(self.db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            for source, entry in health_data.items():
                conn.execute(
                    """INSERT OR REPLACE INTO provider_health
                       (source, state, consecutive_fails, ok_count, fail_count,
                        last_ok_ts, last_fail_ts, last_error, cooldown_until, reason)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (source,
                     entry.get("state", "UNKNOWN"),
                     entry.get("consecutive_fails", 0),
                     entry.get("ok_count", 0),
                     entry.get("fail_count", 0),
                     entry.get("last_ok_ts"),
                     entry.get("last_fail_ts"),
                     (entry.get("last_error") or "")[:300],
                     entry.get("cooldown_until"),
                     (entry.get("reason") or "")[:200]))
            # Verwaiste Zeilen löschen (F8: DB = Spiegel der JSON-Registry)
            if health_data:
                conn.execute(
                    "DELETE FROM provider_health WHERE source NOT IN "  # nosec B608 — parametrisiert (?-Platzhalter)
                    f"({','.join('?' * len(health_data))})",
                    list(health_data.keys()))
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

    # ---------- FTS5-Archiv-Suche (Block 15) ----------

    @staticmethod
    def _fts_query(begriff: str) -> str:
        """Freitext → FTS5-MATCH-Query.

        Regeln (fzf/Recherche-Muster, robust gegen Syntax-Fehler):
        - Jedes Wort wird Präfix-Token ('benton' findet 'Bentonite')
        - Mehrere Wörter = UND (implizit in FTS5)
        - Wort mit '!' voran = NOT
        - "exakte phrase" = Phrase (wörtlich)
        - NUR Sonderzeichen bereinigt; Bindestrich wird NICHT als Wortzeichen
          behandelt (FTS5 interpretiert '-x' als NOT → 'trauma-therapie' würde
          still zu 'trauma NOT therapie' → Bindestriche zu Leerzeichen)
        - Nur-Ausschluss-Query (kein positiver Begriff) → "" (CLI meldet das)
        """
        import re
        begriff = begriff.strip()
        if not begriff:
            return ""
        teile = []
        for m in re.finditer(r'"([^"]+)"|(\S+)', begriff):
            phrase, wort = m.group(1), m.group(2)
            if phrase is not None:
                # Phrase: Token bereinigen, als gequotete Phrase einfügen
                p = re.sub(r'[^\wäöüÄÖÜß ]', ' ', phrase, flags=re.UNICODE).strip()
                p = re.sub(r'\s+', ' ', p)
                if p:
                    teile.append(f'"{p}"')
            elif wort:
                neg = wort.startswith("!")
                w = wort.lstrip("!").strip("'")
                # Bindestrich → Leerzeichen (FTS5-Operator-Kollision vermeiden)
                w = re.sub(r'[^\wäöüÄÖÜß]', ' ', w, flags=re.UNICODE).strip()
                w = re.sub(r'\s+', ' ', w)
                for sub in w.split():
                    teile.append(("NOT " if neg else "") + sub + "*")
        # Nur-Ausschluss ohne positiven Begriff: FTS5 bräuchte einen Anker —
        # leer zurückgeben, CLI meldet "nur !-Begriffe" verständlich.
        positive = [t for t in teile if not t.startswith("NOT ")]
        if not positive:
            return ""
        return " ".join(teile)

    def archiv_suche(self, begriff: str, limit: int = 20) -> list:
        """FTS5-Volltextsuche über alle archivierten Ergebnisse.

        Rebuild vor jeder Suche (bei 864 Zeilen <10 ms; immer aktuell, kein
        Trigger-Management). BM25-Ranking mit Spaltengewichten:
        title/url 6×, snippet/doi 3×, query/quelle 1× (Titel-Treffer gewinnen).
        Gibt Dicts wie letzte_ergebnisse zurück (url/title/quelle/ts + score).
        """
        query = self._fts_query(begriff)
        if not query:
            return []
        conn = _connect(self.db_path)
        try:
            # Dirty-Rebuild (OpenCode-Finding 4): Voll-Rebuild bei JEDER Suche
            # wäre O(Archiv) je Query. External-content-FTS kann seinen eigenen
            # Stand nicht per COUNT/MAX(rowid) prüfen (spiegelt Quelltabelle),
            # daher fts_state.last_rebuilt_id: nur rebuilden wenn die ergebnisse-
            # Tabelle seither gewachsen ist (INSERT-only → max(id) reicht).
            max_id = conn.execute(
                "SELECT COALESCE(MAX(id), 0) FROM ergebnisse").fetchone()[0]
            last = conn.execute(
                "SELECT last_rebuilt_id FROM fts_state WHERE id = 1").fetchone()
            if last is None or last[0] < max_id:
                conn.execute("INSERT INTO ergebnisse_fts(ergebnisse_fts) VALUES('rebuild')")
                conn.execute(
                    "UPDATE fts_state SET last_rebuilt_id = ? WHERE id = 1",
                    (max_id,))
                conn.commit()
            rows = conn.execute(
                """SELECT e.id, e.query, e.quelle, e.title, e.url, e.year,
                          e.doi, e.is_oa, e.pdf, e.snippet, e.ts,
                          bm25(ergebnisse_fts, 1.0, 1.0, 6.0, 6.0, 3.0, 3.0) AS score
                   FROM ergebnisse_fts
                   JOIN ergebnisse e ON e.id = ergebnisse_fts.rowid
                   WHERE ergebnisse_fts MATCH ?
                   ORDER BY score LIMIT ?""",
                (query, limit)).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.OperationalError:
            # FTS5-Syntaxfehler trotz Sanitizing → leer statt Crash
            return []
        finally:
            conn.close()
