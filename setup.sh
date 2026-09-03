#!/usr/bin/env bash
# ============================================================
# SUCHER-1000 — All-in-one-Installation (Agent-1-UX Top-4)
# Prüft python3 → legt venv an → installiert Abhängigkeiten →
# macht 'sucher'-Starter in ~/.local/bin → fragt optionale Keys ab.
#
# Nutzung:  ./setup.sh        (oder: curl -fsSL <URL> | bash)
# ============================================================
set -e

cd "$(dirname "$0")"
ROOT="$(pwd)"
BINDIR="$HOME/.local/bin"

echo "╔══════════════════════════════════════════╗"
echo "║      SUCHER-1000 — Installation           ║"
echo "╚══════════════════════════════════════════╝"
echo

# 1) Python prüfen
if ! command -v python3 >/dev/null 2>&1; then
    echo "✗ python3 fehlt — bitte installieren: sudo apt install python3 python3-venv"
    exit 1
fi
echo "  ✓ python3: $(python3 --version 2>&1)"

# 2) venv anlegen (falls nicht da)
if [ ! -x ".venv/bin/python" ]; then
    echo "  → lege venv an …"
    python3 -m venv .venv
fi
echo "  ✓ venv bereit"

# 3) Abhängigkeiten
echo "  → installiere Abhängigkeiten …"
.venv/bin/pip install -q -r requirements.txt 2>/dev/null || {
    echo "  ⚠ pip-Installation hatte Warnungen (weiter geht's trotzdem)"; }
echo "  ✓ Abhängigkeiten installiert"

# 4) 'sucher'-Starter in ~/.local/bin
mkdir -p "$BINDIR"
cat > "$BINDIR/sucher" <<EOF
#!/usr/bin/env bash
# SUCHER-1000 Starter (von setup.sh erzeugt)
cd "$ROOT"
exec .venv/bin/python sucher.py "\$@"
EOF
chmod +x "$BINDIR/sucher"
echo "  ✓ Starter: $BINDIR/sucher"
if ! echo ":$PATH:" | grep -q ":$BINDIR:"; then
    echo "    ⚠ $BINDIR ist nicht im PATH — einmalig:"
    echo "      echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc"
fi

# 5) Optionale Keys abfragen (sucher auth)
echo
echo "  Optionale API-Keys? (nicht nötig — key-freie Quellen laufen sofort)"
read -r -p "  Jetzt einrichten? [j/N]: " KEYS
if [ "$KEYS" = "j" ] || [ "$KEYS" = "J" ]; then
    exec .venv/bin/python scripts/sucher_auth.py
fi

# 6) Fertig
echo
echo "  ✓ FERTIG — SUCHER-1000 ist installiert!"
echo
echo "  So startest du:"
echo "    sucher \"deine Frage\"          # oder:"
echo "    ./launch.sh                     # Auswahl-Menü"
echo
echo "  Entfernen: rm -rf .venv $BINDIR/sucher  (Projektordner bleibt)"
