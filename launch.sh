#!/usr/bin/env bash
# ============================================================
# SUCHER-1000 — Launcher (P7)
# Startet den Sucher OHNE Hermes — eigenes venv, eigene Keys.
# Funktioniert auch wenn Hermes updated/failed (Davids Kern-Anforderung).
#
# Nutzung:  ./launch.sh
# ============================================================
cd "$(dirname "$0")"

PY=".venv/bin/python"
if [ ! -x "$PY" ]; then
    echo "✗ venv fehlt — Setup läuft einmalig:"
    python3 -m venv .venv || exit 1
    .venv/bin/pip install -r requirements.txt || exit 1
    echo "✓ venv eingerichtet"
fi

# Keys aus Hermes-Env + Auth-Wizard-keys.env nachladen (falls vorhanden)
for ENV_FILE in "$HOME/.hermes/.env" "$HOME/.config/sucher1000/keys.env"; do
    if [ -f "$ENV_FILE" ]; then
        set -a; . "$ENV_FILE" 2>/dev/null; set +a
    fi
done

echo "╔══════════════════════════════════════════╗"
echo "║        SUCHER-1000 — Multi-Engine         ║"
echo "║  Web-Bündel + 16 Studien-Quellen          ║"
echo "╚══════════════════════════════════════════╝"
echo

# Menü (read -p wie im Plan)
while true; do
    echo "Modus wählen:"
    echo "  1) Web-Suche (Bing+ddgs+Mojeek+Wikipedia+Tavily …)"
    echo "  2) Studien-Suche (OpenAlex, PubMed, arXiv …)"
    echo "  3) Alles (Studien + Web)"
    echo "  4) API-Keys verwalten (sucher auth — optional)"
    echo "  5) Setup-Check"
    echo "  0) Ende"
    read -r -p "Auswahl [1-5, 0]: " wahl

    case "$wahl" in
        1) MODUS="web"; break;;
        2) MODUS="studien"; break;;
        3) MODUS="alle"; break;;
        4) exec "$PY" scripts/sucher_auth.py;;
        5) exec "$PY" sucher.py --setup;;
        0) echo "Tschüss!"; exit 0;;
        *) echo "  ? Bitte 1-5 oder 0.";;
    esac
done

echo
read -r -p "Suchbegriff: " QUERY
[ -z "$QUERY" ] && QUERY="IT Systemhaus München"
read -r -p "Anzahl Treffer [8]: " N
N="${N:-8}"

echo
exec "$PY" sucher.py "$QUERY" "$N" --modus "$MODUS"
