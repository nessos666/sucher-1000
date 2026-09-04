#!/usr/bin/env python3
"""SUCHER-1000 Auth-Wizard — API-Keys verwalten (Agent-3-UX, rclone-Muster).

Keys werden in ~/.config/sucher1000/keys.env gespeichert (chmod 600) und von
sucher_web._env automatisch mitgelesen. Ohne Key wird eine Quelle übersprungen
(NO_KEY-Mechanik) — dieser Wizard macht das Setzen + Testen bequem.

Befehle:
  sucher_auth.py               → interaktives Menü (Status aller Key-Quellen)
  sucher_auth.py --list        → Statusübersicht
  sucher_auth.py --add serper  → Key für Quelle setzen (verdeckt) + Live-Test
  sucher_auth.py --test-all    → alle gesetzten Keys live testen
  sucher_auth.py --remove X    → Key entfernen

Nutzung (Hermes-frei, venv):
  .venv/bin/python scripts/sucher_auth.py
"""
import argparse
import getpass
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))

# Quelle → (Env-Name, Anbieter-URL, Test-Endpoint-Beschreibung)
KEY_QUELLEN = {
    "tavily":      ("TAVILY_API_KEY",      "https://tavily.com",            "POST api.tavily.com/search"),
    "exa":         ("EXA_API_KEY",         "https://exa.ai",                "POST api.exa.ai/search"),
    "serpapi":     ("SERPAPI_API_KEY",     "https://serpapi.com",           "GET serpapi.com/search.json"),
    "reddit":      ("REDDIT_CLIENT_ID",    "https://www.reddit.com/prefs/apps", "OAuth reddit.com (ID+Secret)"),
    "knowledgegraph": ("GOOGLE_KG_API_KEY", "https://console.cloud.google.com", "GET kgsearch.googleapis.com"),
    "google_books": ("GOOGLE_BOOKS_API_KEY", "https://console.cloud.google.com", "GET googleapis.com/books"),
    "serper":      ("SERPER_API_KEY",      "https://serper.dev/api-key",    "POST google.serper.dev/search"),
    "youcom":      ("YOUCOM_API_KEY",      "https://you.com/platform",      "POST api.you.com/v1/search"),
    "zenrows":     ("ZENROWS_API_KEY",     "https://app.zenrows.com/register", "GET api.zenrows.com (Google-SERP)"),
    "searchapi":   ("SEARCHAPI_KEY",       "https://www.searchapi.io/dashboard", "POST searchapi.io/api/v1/search"),
    "firecrawl":   ("FIRECRAWL_API_KEY",   "https://www.firecrawl.dev",     "POST firecrawl.dev/v1/search"),
}

KEYS_DIR = Path.home() / ".config" / "sucher1000"
KEYS_FILE = KEYS_DIR / "keys.env"


def _lade_keys():
    """keys.env → dict (Env-Namen ohne Wert = vorhanden?)."""
    d = {}
    if KEYS_FILE.exists():
        for line in KEYS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                d[k.strip()] = v.strip()
    return d


def _speichere_keys(d):
    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    lines = ["# SUCHER-1000 API-Keys (chmod 600 — nicht teilen!)\n"]
    for k, v in sorted(d.items()):
        lines.append(f"{k}={v}\n")
    KEYS_FILE.write_text("".join(lines), encoding="utf-8")
    os.chmod(KEYS_FILE, 0o600)


def _status_zeile(quelle, envname, url, test_endpoint, keys):
    val = keys.get(envname, "")
    if val:
        return f"  [✓ aktiv] {quelle:15s} ({envname} gesetzt)"
    return (f"  [✗ Key fehlt] {quelle:15s} → {url}\n"
            f"              setzen mit: sucher_auth.py --add {quelle}")


def _live_test(quelle, envname):
    """Echten Endpoint mit Key testen — 1 Query, Timeout 10s."""
    try:
        import sucher_web as web
        fn = web.WEB.get(quelle)
        if not fn:
            return False, f"Unbekannte Quelle {quelle}"
        # _env liest os.environ + ~/.hermes/.env — hier keys.env als Quelle ergänzen
        keys = _lade_keys()
        if envname in keys:
            os.environ[envname] = keys[envname]
        res = list(fn("SUCHER auth test", 1))
        if res:
            return True, f"OK: {len(res)} Ergebnis (z. B. '{res[0].get('title','')[:40]}')"
        return False, "Keine Ergebnisse (Key evtl. ungültig oder Quelle leer)"
    except Exception as e:
        return False, f"Fehler: {e}"


def main():
    ap = argparse.ArgumentParser(description="SUCHER-1000 Auth-Wizard")
    ap.add_argument("--list", action="store_true", help="Status aller Key-Quellen")
    ap.add_argument("--add", metavar="QUELLE", help="Key setzen + live testen")
    ap.add_argument("--test-all", action="store_true", help="Alle Keys live testen")
    ap.add_argument("--remove", metavar="QUELLE", help="Key entfernen")
    args = ap.parse_args()

    if args.list or not (args.add or args.test_all or args.remove):
        print("=== SUCHER-1000 Key-Status (optional, Bezahl-/Key-Quellen) ===")
        print(f"  Datei: {KEYS_FILE}\n")
        keys = _lade_keys()
        for quelle, (envname, url, ep) in sorted(KEY_QUELLEN.items()):
            print(_status_zeile(quelle, envname, url, ep, keys))
        print("\n  Tipp: key-freie Quellen brauchen keinen Key (laufen immer).")
        return

    if args.add:
        quelle = args.add.lower()
        if quelle not in KEY_QUELLEN:
            print(f"Unbekannte Quelle '{quelle}'. Verfügbar: {', '.join(KEY_QUELLEN)}")
            sys.exit(1)
        envname, url, ep = KEY_QUELLEN[quelle]
        print(f"\n=== Key für '{quelle}' setzen ===")
        print(f"  Anbieter: {url}")
        print(f"  Endpoint-Test: {ep}")
        print(f"  Free-Tier-Infos: siehe {url}\n")
        val = getpass.getpass(f"  API-Key für {quelle} (Eingabe verdeckt, leer = abbrechen): ")
        if not val.strip():
            print("  Abgebrochen.")
            return
        keys = _lade_keys()
        keys[envname] = val.strip()
        _speichere_keys(keys)
        print(f"  ✓ Gespeichert ({KEYS_FILE}, chmod 600)")
        print("  → Live-Test läuft…")
        ok, msg = _live_test(quelle, envname)
        if ok:
            print(f"  ✓ {msg}")
        else:
            print(f"  ✗ {msg}")
            print(f"    Key trotzdem gespeichert — prüfe: {url}")

    if args.test_all:
        print("\n=== Live-Test aller gesetzten Keys ===")
        keys = _lade_keys()
        for quelle, (envname, url, ep) in sorted(KEY_QUELLEN.items()):
            if not keys.get(envname):
                continue
            ok, msg = _live_test(quelle, envname)
            print(f"  {'✓' if ok else '✗'} {quelle}: {msg}")
        print("  Fertig.")

    if args.remove:
        quelle = args.remove.lower()
        if quelle not in KEY_QUELLEN:
            print(f"Unbekannte Quelle '{quelle}'")
            sys.exit(1)
        envname = KEY_QUELLEN[quelle][0]
        keys = _lade_keys()
        if keys.pop(envname, None):
            _speichere_keys(keys)
            print(f"  ✓ Key für '{quelle}' entfernt.")
        else:
            print(f"  Kein Key für '{quelle}' gesetzt.")


if __name__ == "__main__":
    main()
