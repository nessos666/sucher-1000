"""Block 11 — Auth-Wizard (scripts/sucher_auth.py): Keys speichern/laden/testen."""
import importlib.util
import os
import sys
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "sucher_auth", "scripts/sucher_auth.py")
sa = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sa)


def test_keys_speichern_und_laden(tmp_path):
    """Key wird geschrieben + mit chmod 600 gelesen."""
    sa.KEYS_DIR = tmp_path / ".config" / "sucher1000"
    sa.KEYS_FILE = sa.KEYS_DIR / "keys.env"
    sa._speichere_keys({"SERPER_API_KEY": "dummy123"})
    keys = sa._lade_keys()
    assert keys.get("SERPER_API_KEY") == "dummy123"
    st = os.stat(sa.KEYS_FILE)
    assert st.st_mode & 0o777 == 0o600, f"chmod 600 erwartet: {oct(st.st_mode)}"


def test_remove_key(tmp_path):
    sa.KEYS_DIR = tmp_path / ".config" / "sucher1000"
    sa.KEYS_FILE = sa.KEYS_DIR / "keys.env"
    sa._speichere_keys({"SERPER_API_KEY": "dummy123", "YOUCOM_API_KEY": "y"})
    sa.KEY_QUELLEN = {"serper": ("SERPER_API_KEY", "u", "ep")}
    sa._lade_keys()
    keys = sa._lade_keys()
    keys.pop("SERPER_API_KEY", None)
    sa._speichere_keys(keys)
    assert "SERPER_API_KEY" not in sa._lade_keys()
    assert sa._lade_keys().get("YOUCOM_API_KEY") == "y"


def test_status_zeile_zeigt_key_hinweis():
    """Fehlender Key → Hinweis mit --add Befehl (UX: nächster Schritt)."""
    line = sa._status_zeile("serper", "SERPER_API_KEY", "https://serper.dev", "ep", {})
    assert "Key fehlt" in line
    assert "--add serper" in line


def test_env_liest_keys_env(monkeypatch, tmp_path):
    """sucher_web._env liest die keys.env-Datei des Wizards (Integration)."""
    import sucher_web as web
    sa.KEYS_DIR = tmp_path / ".config" / "sucher1000"
    sa.KEYS_FILE = sa.KEYS_DIR / "keys.env"
    sa._speichere_keys({"SERPER_API_KEY": "aus_keysenv"})
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    # _env prüft ~/.hermes/.env + ~/.config — HOME umbiegen reicht für keys.env
    val = web._env("SERPER_API_KEY")
    assert val == "aus_keysenv", f"_env muss keys.env lesen: {val!r}"
