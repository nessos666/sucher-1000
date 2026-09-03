#!/usr/bin/env bash
# ============================================================
# SUCHER-1000 — Quality-Gate (P7)
# Ein Befehl prüft: Syntax → Tests → Live-Smoke.
# Läuft NUR im Repo-venv (.venv) — Hermes-unabhängig.
#
# Nutzung:  ./check.sh            (alles)
#           ./check.sh tests      (nur offline-Tests)
#           ./check.sh live       (nur Live-Smoke)
# Exit-Code 0 = alles grün.
# ============================================================
set -uo pipefail
cd "$(dirname "$0")"

PY=".venv/bin/python"
if [ ! -x "$PY" ]; then
    echo "✗ venv fehlt — erst: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

PASS=0
FAIL=0
note() { echo "── $*"; }
ok()   { echo "  ✓ $*"; PASS=$((PASS+1)); }
bad()  { echo "  ✗ $*"; FAIL=$((FAIL+1)); }

# 1) Syntax aller Module
note "Syntax-Check (py_compile)"
for f in sucher.py src/*.py scripts/*.py; do
    if [ -f "$f" ]; then
        "$PY" -m py_compile "$f" && ok "Syntax $f" || bad "Syntax $f"
    fi
done

# 2) Offline-Tests (Netz gemockt, kein Live-Zugriff)
if [ "${1:-}" != "live" ]; then
    note "Offline-Tests (pytest)"
    if timeout 180 "$PY" -m pytest tests/ -q -m "not live" 2>&1 | tail -4; then
        ok "pytest offline"
    else
        bad "pytest offline — Fehler oben"
    fi
fi

# 3) Live-Smoke (1 echte Suche, beide Modi)
if [ "${1:-}" != "tests" ]; then
    note "Live-Smoke (Web-Bündel, 20s Budget)"
    out=$(timeout 60 "$PY" sucher.py "IT Systemhaus München" 2 --modus web 2>&1)
    if echo "$out" | grep -q "Treffer"; then
        n=$(echo "$out" | grep -oE "[0-9]+ Treffer" | head -1)
        ok "Live-Web-Suche: $n"
    else
        bad "Live-Web-Suche lieferte nichts: $(echo "$out" | tail -2)"
    fi

    note "Live-Smoke (Studien, 20s Budget)"
    out=$(timeout 60 "$PY" sucher.py "posttraumatic growth" 2 --modus studien 2>&1)
    if echo "$out" | grep -q "Treffer"; then
        n=$(echo "$out" | grep -oE "[0-9]+ Treffer" | head -1)
        ok "Live-Studien-Suche: $n"
    else
        bad "Live-Studien-Suche lieferte nichts: $(echo "$out" | tail -2)"
    fi
fi

echo
echo "═══════════════════════════════"
echo "  Quality-Gate: $PASS ok, $FAIL fehler"
echo "═══════════════════════════════"
[ "$FAIL" -eq 0 ]
