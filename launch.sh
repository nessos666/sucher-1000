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

# Keys aus Hermes-Env nachladen (falls vorhanden) — ohne Hermes kein Problem
ENV_FILE="$HOME/.hermes/.env"
if [ -f "$ENV_FILE" ]; then
    set -a; . "$ENV_FILE" 2>/dev/null; set +a
fi

echo "╔══════════════════════════════════════════╗"
echo "║        SUCHER-1000 — Multi-Engine         ║"
echo "║  Web-Bündel + 12 Studien-Quellen          ║"
echo "╚══════════════════════════════════════════╝"
echo

# Menü (read -p wie im Plan)
while true; do
    echo "Modus wählen:"
    echo "  1) Web-Suche (Bing+ddgs+Mojeek+Wikipedia+Tavily …)"
    echo "  2) Studien-Suche (OpenAlex, PubMed, arXiv …)"
    echo "  3) Alles (Studien + Web)"
    echo "  4) Setup-Check"
    echo "  0) Ende"
    read -r -p "Auswahl [1-4, 0]: " wahl

    case "$wahl" in
        1) MODUS="web"; break;;
        2) MODUS="studien"; break;;
        3) MODUS="alle"; break;;
        4) exec "$PY" sucher.py --setup;;
        0) echo "Tschüss!"; exit 0;;
        *) echo "  ? Bitte 1-4 oder 0.";;
    esac
done

echo
read -r -p "Suchbegriff: " QUERY
[ -z "$QUERY" ] && QUERY="IT Systemhaus München"
read -r -p "Anzahl Treffer [8]: " N
N="${N:-8}"

echo
exec "$PY" sucher.py "$QUERY" "$N" --modus "$MODUS"
