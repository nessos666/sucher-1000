"""P3 — Parallelität + Gesamtbudget: langsame Quelle blockiert nicht, Budget hart."""
import sys
import time
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import sucher_universal as su


def test_parallel_langsame_quelle_blockiert_nicht():
    """2 Quellen à 3s parallel → ~3s. Sequenziell wären es 6s — das ist der Beweis."""
    def quelle1(q, n):
        time.sleep(3)
        return [{"title": "Quelle1", "url": "http://q1.de"}]

    def quelle2(q, n):
        time.sleep(3)
        return [{"title": "Quelle2", "url": "http://q2.de"}]

    su._QUELLEN_FEHLER.clear()
    # Nur diese 2 Quellen aktiv (kein Netz!)
    orig_sci, orig_gen = su.SCI, su.GENERAL
    su.SCI = {"quelle1": quelle1, "quelle2": quelle2}
    su.GENERAL = {}
    try:
        t0 = time.monotonic()
        res = su.search("test", 3, mode="studien", budget_s=30)
        dt = time.monotonic() - t0
    finally:
        su.SCI, su.GENERAL = orig_sci, orig_gen

    # Parallel: ~3s (nicht 6s Summe). Toleranz 4.5s beweist Parallelität klar.
    assert dt < 4.5, f"Parallel erwartet (~3s), dauerte {dt:.1f}s — läuft noch sequenziell?"
    assert len(res) == 2, f"Beide Quellen müssen liefern, bekam {len(res)}"


def test_gesamtbudget_hart():
    """Quelle hängt 60s → search() endet ≤ budget_s (hier 2s), Teilergebnis bleibt."""
    def haengt(q, n):
        time.sleep(60)
        return [{"title": "Zu-spät", "url": "http://haengt.de"}]

    def schnell(q, n):
        time.sleep(0.05)
        return [{"title": "Rechtzeitig", "url": "http://schnell.de"}]

    su._QUELLEN_FEHLER.clear()
    orig_sci, orig_gen = su.SCI, su.GENERAL
    su.SCI = {"haengt": haengt, "schnell": schnell}
    su.GENERAL = {}
    try:
        t0 = time.monotonic()
        res = su.search("test", 3, mode="studien", budget_s=2)
        dt = time.monotonic() - t0
    finally:
        su.SCI, su.GENERAL = orig_sci, orig_gen

    assert dt < 5.0, f"Budget hart erwartet, dauerte {dt:.1f}s"
    titles = [r["title"] for r in res]
    assert "Rechtzeitig" in titles, "Teilergebnis der schnellen Quelle muss erhalten bleiben"


def test_dedup_nach_fanout():
    """2 Quellen liefern dieselbe URL → nur 1 Ergebnis."""
    def quelle_a(q, n):
        return [{"title": "Gleicher Titel", "url": "http://gleich.de"}]

    def quelle_b(q, n):
        return [{"title": "Gleicher Titel", "url": "http://gleich.de"}]

    orig_sci, orig_gen = su.SCI, su.GENERAL
    su.SCI = {"a": quelle_a, "b": quelle_b}
    su.GENERAL = {}
    try:
        res = su.search("test", 3, mode="studien")
    finally:
        su.SCI, su.GENERAL = orig_sci, orig_gen

    assert len(res) == 1, f"Dedup erwartet (1), bekam {len(res)}"


def test_q_lokal_zeitlimit():
    """q_lokal mit Zeitlimit 0 → sofort leer, kein Hängen über 133GB."""
    res = su.q_lokal("test", 5, zeitlimit_s=0)
    assert isinstance(res, list)
    # Mit 0s Limit darf nichts durchlaufen (oder nur, was vor dem ersten Check kam)
    assert len(res) == 0
