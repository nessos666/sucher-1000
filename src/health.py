#!/usr/bin/env python3
"""
SUCHER — health.py (P4): Health-Registry + Cooldown
=====================================================
Zeichnet pro Quelle Erfolg/Fehler auf und führt Status-Übergänge aus.
BROKEN-Quellen werden mit Cooldown ÜBERSPRUNGEN statt ertragen — das ist der
Unterschied zwischen „statischem Health-Check" und echtem Selbstheilungs-Fallback.

Zustände (Agent-3-Architektur):
  UNKNOWN  → HEALTHY (1 ok) → DEGRADED (2 consecutive fails)
           → BROKEN (3+ fails, cooldown 60 min) → DISABLED (manuell)
           → NO_KEY (Key-Quelle ohne Env)
  Erfolg setzt auf HEALTHY zurück.

Persistenz: data/health.json (SQLite folgt in P5 — gleiche Struktur als Tabelle).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

# Zustände
UNKNOWN = "UNKNOWN"
HEALTHY = "HEALTHY"
DEGRADED = "DEGRADED"
BROKEN = "BROKEN"
DISABLED = "DISABLED"
NO_KEY = "NO_KEY"

COOLDOWN_S = 3600  # 60 Minuten

BASE = Path(__file__).resolve().parents[1]
# Env-Override für Tests/Portabilität: SUCHER_HEALTH_FILE=/pfad/health.json
DEFAULT_HEALTH_FILE = Path(os.environ.get("SUCHER_HEALTH_FILE",
                                           str(BASE / "data" / "health.json")))

# Grenzen (nur Konstanten — Logik in record_outcome)
MAX_FAILS_DEGRADED = 2   # ab 2 consecutive fails → DEGRADED
MAX_FAILS_BROKEN = 3     # ab 3 → BROKEN + Cooldown


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


class HealthRegistry:
    """Status-Registry mit JSON-Persistenz. Thread-sicher via Lock."""

    def __init__(self, path=None):
        self.path = Path(path) if path else DEFAULT_HEALTH_FILE
        self._lock = __import__("threading").Lock()
        self._data = self._load()

    # ---------- Persistenz ----------

    def _load(self) -> dict:
        try:
            if self.path.exists():
                return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def save(self):
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=1),
                           encoding="utf-8")
            tmp.replace(self.path)

    # ---------- Kern-API ----------

    def record_outcome(self, source: str, ok: bool, error: str = "", latency_ms: float = 0.0):
        """Erfolg/Fehler einer Quelle aufzeichnen → Status-Übergang."""
        with self._lock:
            entry = self._data.get(source, {})
            state = entry.get("state", UNKNOWN)
            consec = entry.get("consecutive_fails", 0)
            ok_count = entry.get("ok_count", 0)
            fail_count = entry.get("fail_count", 0)

            if state == DISABLED:
                return  # manuell deaktiviert — nichts ändern

            if ok:
                entry.update({
                    "state": HEALTHY,
                    "consecutive_fails": 0,
                    "ok_count": ok_count + 1,
                    "last_ok_ts": _now(),
                    "last_error": "",
                    "avg_latency_ms": latency_ms,
                })
            else:
                consec += 1
                fail_count += 1
                if consec >= MAX_FAILS_BROKEN:
                    new_state = BROKEN
                    entry["cooldown_until"] = _now_plus(COOLDOWN_S)
                elif consec >= MAX_FAILS_DEGRADED:
                    new_state = DEGRADED
                else:
                    new_state = state if state in (DEGRADED, BROKEN) else UNKNOWN
                entry.update({
                    "state": new_state,
                    "consecutive_fails": consec,
                    "fail_count": fail_count,
                    "last_fail_ts": _now(),
                    "last_error": error[:200],
                })
            self._data[source] = entry

    def mark_no_key(self, source: str):
        """Key-Quelle ohne Env-Key → NO_KEY (übersprungen, kein Fehler)."""
        with self._lock:
            self._data[source] = {"state": NO_KEY, "reason": "kein Env-Key",
                                  "last_fail_ts": _now()}

    def disable(self, source: str):
        with self._lock:
            self._data[source] = {"state": DISABLED, "reason": "manuell",
                                  "last_fail_ts": _now()}

    # ---------- Abfragen ----------

    def status(self, source: str) -> dict:
        with self._lock:
            return dict(self._data.get(source, {"state": UNKNOWN}))

    def is_skippable(self, source: str) -> tuple[bool, str]:
        """Soll die Quelle übersprungen werden? (True, Grund)

        BROKEN + Cooldown abgelaufen → NICHT mehr skippen (Cooldown vorbei).
        NO_KEY/DISABLED → immer skippen.
        """
        with self._lock:
            entry = self._data.get(source, {})
            state = entry.get("state", UNKNOWN)
            if state in (NO_KEY, DISABLED):
                return True, f"{state}: {entry.get('reason', '')}"
            if state == BROKEN:
                cd = entry.get("cooldown_until", "")
                if cd and cd > _now():
                    return True, f"BROKEN bis {cd} (Cooldown)"
                # Cooldown abgelaufen → nächster Versuch erlaubt
                return False, ""
            if state == DEGRADED:
                return False, ""  # DEGRADED läuft noch (nächster Fail macht BROKEN)
            return False, ""

    def snapshot(self) -> dict:
        with self._lock:
            return {k: dict(v) for k, v in self._data.items()}


def _now_plus(seconds: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() + seconds))
