"""F6 (OpenCode-Gesamt): Verwaiste Threads dürfen Health des NÄCHSTEN Laufs nicht verfälschen."""
import sys
import time
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import health
import sucher_universal as su


def test_orphan_thread_verfaelscht_nicht_naechsten_lauf(tmp_path, monkeypatch):
    """Lauf 1 lässt einen langsamen Thread zurück → Lauf 2 mit gesunder Quelle
    darf NICHT als Fehler verbucht werden (F6: Health liest pro-Lauf-Register).

    Szenario: Lauf 1 startet eine Quelle, die erst NACH dem Budget einen Fehler
    loggt (verwaister daemon-Thread). Lauf 2 läuft sofort mit gesunder Quelle.
    Vorher: der späte Fehler landete im globalen Register → Lauf 2 sah ihn.
    """
    monkeypatch.setattr(health, "DEFAULT_HEALTH_FILE", tmp_path / "h_f6.json")

    def spaete_quelle(q, n):
        """Loggt den Fehler erst NACH 1.5s — nach Lauf-1-Budget (0.3s)."""
        time.sleep(1.5)
        su._log_quellenfehler("spaet", "später Fehler")
        return []

    def gesunde_quelle(q, n):
        return [{"title": "Gesund", "url": "http://gesund.de"}]

    orig_sci, orig_gen = su.SCI, su.GENERAL
    try:
        # Lauf 1: nur spaete_quelle, Budget 0.3s → Thread wird verwaist
        su.SCI = {"spaet": spaete_quelle}
        su.GENERAL = {}
        su.search("test", 2, mode="studien", budget_s=0)
        # Kurz warten bis der verwaiste Thread seinen Fehler loggte (global!)
        time.sleep(1.8)
        # Lauf 2: gesunde Quelle — darf NICHT den Fremd-Fehler sehen
        su.SCI = {"gesund": gesunde_quelle}
        su.GENERAL = {}
        su.search("test", 2, mode="studien", budget_s=5)
    finally:
        su.SCI, su.GENERAL = orig_sci, orig_gen

    # Frisches Registry-Objekt liest die Datei (status() liest nur Speicher)
    reg2 = health.HealthRegistry()
    st = reg2.status("gesund")
    assert st["state"] == health.HEALTHY, \
        f"Gesunde Quelle in Lauf 2 darf nicht durch Lauf-1-Orphan degradieren: {st}"


def test_fehler_im_gleichen_lauf_degradiert_weiterhin(tmp_path, monkeypatch):
    """Kontroll-Test: Fehler IM SELBEN Lauf müssen weiterhin degradieren (F6-Regression)."""
    monkeypatch.setattr(health, "DEFAULT_HEALTH_FILE", tmp_path / "h_f6b.json")

    def kaputte_quelle(q, n):
        su._check_fehler("kaputt6", {"_error": "HTTP 500"})
        return []

    def gesunde_quelle(q, n):
        return [{"title": "Ok", "url": "http://ok.de"}]

    orig_sci, orig_gen = su.SCI, su.GENERAL
    su.SCI = {"kaputt6": kaputte_quelle, "gesund6": gesunde_quelle}
    su.GENERAL = {}
    try:
        su.search("test", 2, mode="studien", budget_s=5)
    finally:
        su.SCI, su.GENERAL = orig_sci, orig_gen

    reg2 = health.HealthRegistry()
    assert reg2.status("kaputt6")["state"] != health.HEALTHY, \
        "Kaputte Quelle muss im selben Lauf degradieren (F6 darf das nicht brechen)"
    assert reg2.status("gesund6")["state"] == health.HEALTHY
