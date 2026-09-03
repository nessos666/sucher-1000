#!/usr/bin/env python3
"""
SUCHER — ratelimit.py: Pro-Quellen-Drosselung (Shiraberu-Übernahme)
====================================================================
Verhindert, dass dieselbe Quelle zu schnell hintereinander angefragt wird
(DDG/Bing/Mojeek blocken bei Request-Fluten). Thread-sicher: mehrere Worker
können gleichzeitig throttle() aufrufen — pro Quelle wird der letzte
Request-Zeitpunkt gemerkt und bei Bedarf geschlafen.

Muster aus shiraberu (Go, providers/http.go + Rate-Limit):
  Intervall pro Quelle konfigurierbar; Default 150ms zwischen Requests.
"""
from __future__ import annotations

import threading
import time

# Intervall je Quelle in Sekunden (überschreibbar für Tests)
DEFAULT_INTERVAL_S = 0.15
_interval_map: dict = {}
_lock = threading.Lock()
_last_ts: dict = {}


def set_interval(quelle: str, sekunden: float):
    """Intervall für eine Quelle setzen (z.B. ddgs_html = 1.0s)."""
    with _lock:
        _interval_map[quelle] = sekunden


def _interval(quelle: str) -> float:
    return _interval_map.get(quelle, DEFAULT_INTERVAL_S)


def throttle(quelle: str) -> float:
    """Vor einem Request aufrufen: schläft, falls das Intervall seit dem
    letzten Request dieser Quelle noch nicht verstrichen ist.

    Rückgabe: tatsächlich geschlafene Sekunden (0 = sofort erlaubt).
    """
    interval = _interval(quelle)
    if interval <= 0:
        return 0.0
    with _lock:
        last = _last_ts.get(quelle, 0.0)
        now = time.monotonic()
        warte = interval - (now - last)
        if warte > 0:
            _last_ts[quelle] = now + warte  # Reservierung (kein Stampede)
            schlafen = warte
        else:
            _last_ts[quelle] = now
            schlafen = 0.0
    if schlafen > 0:
        time.sleep(schlafen)
    return schlafen


def reset():
    """Nur für Tests: letzten Zeitpunkt löschen."""
    with _lock:
        _last_ts.clear()
