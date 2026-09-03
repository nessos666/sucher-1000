"""Rate-Limit (Shiraberu-Übernahme): pro-Quellen-Drosselung + Integration in Worker."""
import sys
import time
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import ratelimit


def test_erster_request_sofort():
    ratelimit.reset()
    ratelimit.set_interval("testq", 0.3)
    t0 = time.monotonic()
    ratelimit.throttle("testq")
    assert time.monotonic() - t0 < 0.1, "Erster Request muss sofort durch"


def test_zweiter_request_wartet():
    ratelimit.reset()
    ratelimit.set_interval("testq", 0.3)
    ratelimit.throttle("testq")  # sofort
    t0 = time.monotonic()
    gewartet = ratelimit.throttle("testq")  # muss ~0.3s warten
    dt = time.monotonic() - t0
    assert gewartet >= 0.25, f"Zweiter Request muss warten, schlief nur {gewartet:.2f}s"
    assert dt >= 0.25, f"Zweiter Request zu schnell: {dt:.2f}s"


def test_verschiedene_quellen_unabhaengig():
    ratelimit.reset()
    ratelimit.set_interval("q1", 0.3)
    ratelimit.set_interval("q2", 0.0)  # q2 unlimitiert
    ratelimit.throttle("q1")
    t0 = time.monotonic()
    ratelimit.throttle("q2")  # andere Quelle → sofort
    assert time.monotonic() - t0 < 0.1, "Verschiedene Quellen dürfen sich nicht blocken"


def test_intervall_0_kein_warten():
    ratelimit.reset()
    ratelimit.set_interval("q3", 0.0)
    t0 = time.monotonic()
    ratelimit.throttle("q3")
    ratelimit.throttle("q3")
    assert time.monotonic() - t0 < 0.1, "Intervall 0 = kein Warten"


def test_thread_sicherheit():
    """Parallele throttle-Aufrufe derselben Quelle dürfen nicht crashen."""
    ratelimit.reset()
    ratelimit.set_interval("q4", 0.05)
    fehler = []

    def arbeiter():
        try:
            for _ in range(5):
                ratelimit.throttle("q4")
        except Exception as e:
            fehler.append(e)

    import threading
    threads = [threading.Thread(target=arbeiter) for _ in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert not fehler, f"Thread-Race: {fehler}"
