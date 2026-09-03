"""Block 12 — Laien-UX: sucher ohne Argumente zeigt Begrüßung statt Usage-Error."""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_sucher_ohne_argumente_zeigt_begruessung():
    """Kein Query → freundliche deutsche Anleitung (kein Usage-Error/Exit≠0)."""
    proc = subprocess.run([sys.executable, "sucher.py"],
                          capture_output=True, text=True, timeout=30,
                          cwd=str(REPO), input="")
    assert proc.returncode == 0, f"Exit≠0: {proc.stderr[-200:]}"
    assert "SUCHER-1000" in proc.stdout
    assert "Klimawandel" in proc.stdout or "so einfach" in proc.stdout.lower(), \
        "Beispiele müssen sichtbar sein (Laien-UX)"
    assert "Usage" not in proc.stdout, "kein roher argparse-Usage-Error"


def test_sucher_mit_query_laeuft_wie_vorher(tmp_path):
    """Mit Query → normale Suche (Regression: Umbau main→_suche)."""
    env = dict(__import__("os").environ,
               SUCHER_DB=str(tmp_path / "ux.db"),
               SUCHER_HEALTH_FILE=str(tmp_path / "ux_health.json"),
               SUCHER_CACHE_DB=str(tmp_path / "ux_cache.db"),
               SUCHER_FAKE_NET="1")
    proc = subprocess.run(
        [sys.executable, "sucher.py", "zzzqqqxxyyy", "1", "--modus", "web"],
        capture_output=True, text=True, timeout=60, cwd=str(REPO), env=env)
    assert proc.returncode == 0, f"CLI crashte: {proc.stderr[-300:]}"
    assert "SUCHER 1000" in proc.stdout
