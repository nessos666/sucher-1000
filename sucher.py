#!/usr/bin/env python3
"""
SUCHER 1000 — Haupt-Einstiegspunkt (das große Tool)

Eine Pipeline, alles in einem Ziel-Ordner:
  SUCHE (multi-API) → OA-Resolver (freie Version) → DOWNLOAD (curl→Browser) → SORTIEREN → LOG.

Nutzung:
  python3 sucher.py "suchbegriff" [anzahl] [--modus M] [--out ORDNER]
  python3 sucher.py --setup        # Umgebung checken + Dependencies
  python3 sucher.py --sources      # Quellen anzeigen
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime

# Pfade (relativ zu diesem Skript → überlebt Verschieben)
BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "src")
DEFAULT_OUT = os.path.join(BASE, "ergebnisse")
LOG_FILE = os.path.join(BASE, "ergebnisse", "sucher_log.md")

sys.path.insert(0, SRC)

def log(msg, level="INFO"):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] [{level}] {msg}\n")

def ensure_src_imports():
    """Importiert die Module aus src/ (nach dem Umzug)."""
    try:
        import store
        import sucher_download
        import sucher_oa
        import sucher_universal
        import sucher_web
        return sucher_universal, sucher_oa, sucher_download, sucher_web, store
    except ImportError as e:
        log(f"Import-Fehler: {e}", "ERROR"); raise

def main():
    ap = argparse.ArgumentParser(description="SUCHER 1000 — großes Studien-Tool")
    ap.add_argument("query", nargs="?", help="Suchbegriff")
    ap.add_argument("n", nargs="?", type=int, default=8, help="Anzahl (default 8)")
    ap.add_argument("--modus", default="universal", help="studien|universal|alle|web")
    ap.add_argument("--out", default=DEFAULT_OUT, help="Zielordner")
    ap.add_argument("--download", action="store_true", help="Automatisch frei ladbare herunterladen")
    ap.add_argument("--setup", action="store_true", help="Umgebung prüfen")
    ap.add_argument("--sources", action="store_true", help="Quellen anzeigen")
    args = ap.parse_args()

    if args.setup:
        print("=== SUCHER 1000 — Setup-Check ===")
        for mod in ("sucher_universal","sucher_oa","sucher_download","sucher_web","store","health"):
            try:
                __import__(mod); print(f"  ✓ {mod}")
            except ImportError:
                print(f"  ✗ {mod} (fehlt)")
        print("  Ziel:", DEFAULT_OUT); return

    if args.sources:
        src_list = os.path.join(SRC, "sucher_universal.py")
        subprocess.run([sys.executable, src_list, "--list"])  # F9: venv statt System-python3
        print("\n  WEB-BÜNDEL (Multi-Engine, --modus web):")
        subprocess.run([sys.executable, "-c",
            "import sys; sys.path.insert(0, '" + SRC + "'); import sucher_web; sucher_web.list_web()"])
        return

    if not args.query:
        print(__doc__); return

    su, soa, sdl, sw, st = ensure_src_imports()
    os.makedirs(args.out, exist_ok=True)

    t0 = time.time()
    print(f"\n🔍 SUCHER 1000 — Suche: {args.query!r} (Modus: {args.modus}, n={args.n})\n")

    # 1) SUCHE
    log(f"Suche start: {args.query} (modus={args.modus})")
    if args.modus == "alle":
        # F3 (OpenCode-Gesamt): 'alle' = Studien + Web-Bündel parallel (Kombi)
        import threading
        ergebnisse = {}
        def _studien():
            ergebnisse["studien"] = su.search(args.query, args.n, mode="universal")
        def _web():
            ergebnisse["web"] = sw.search_web(args.query, args.n)
        t1 = threading.Thread(target=_studien, daemon=True); t1.start()
        t2 = threading.Thread(target=_web, daemon=True); t2.start()
        t1.join(timeout=35); t2.join(timeout=35)
        results = ergebnisse.get("studien", []) + ergebnisse.get("web", [])
        # Dedup über URL (F4-Codex: Treffer OHNE URL nicht verwerfen — nur
        # nicht deduplizieren; vorher verschwanden sie komplett)
        seen, dedup = set(), []
        for r in results:
            url = (r.get("url") or "").lower()
            if url:
                if url not in seen:
                    seen.add(url); dedup.append(r)
            else:
                dedup.append(r)  # ohne URL: übernehmen, kein Dedup möglich
        results = dedup
    elif args.modus == "web":
        # Web-Bündel: mehrere Web-Such-Quellen parallel (sucher_web)
        results = sw.search_web(args.query, args.n)
    else:
        results = su.search(args.query, args.n, mode=args.modus)
    if not results:
        print("  Keine Treffer — Netzwerk/Quellen gerade evtl. instabil (560/429).")
        log("Suche: 0 Treffer (Quellen evtl. down)", "WARN")
        return
    su.pretty(results, args.modus)
    print(f"  → {len(results)} Treffer\n")

    # 2) OA-Resolver für Treffer mit DOI (freie Version finden)
    if args.download:
        print("  --- OA-Resolver (freie Version suchen) ---")
        for r in results:
            doi = r.get("doi")
            if not doi: continue
            oares, _ = soa.resolve(doi)
            if oares:
                r["_oa"] = oares[0]  # beste freie Version merken
                print(f"    {r['title'][:45]} → 🟢 {oares[0][1][:70]}")

    # 3) Ausgabe als JSON sortiert speichern
    fname = "ergebnis_" + re.sub(r'\W+', '_', args.query)[:40] + ".json"
    fn = os.path.join(args.out, fname)
    with open(fn, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    log(f"Ergebnis gespeichert: {fn} ({len(results)} Treffer)")
    print(f"\n  💾 Ergebnis: {fn}")

    # 4) P5: SQLite-Archiv — jede Suche + Health in data/sucher.db
    try:
        store_inst = st.Store()
        store_inst.save_ergebnisse(args.query, results, modus=args.modus)
        try:
            import health as _health_mod
            reg = _health_mod.HealthRegistry()
            store_inst.save_health(reg._data)
        except Exception:  # noqa: S110 - bewusster Fallback (optional)
            pass  # Health optional — DB-Hauptzweck ist das Ergebnis-Archiv
        db_stat = f" (DB: {store_inst.anzahl_ergebnisse()} archiviert)"
        print(f"  🗄  SQLite-Archiv: data/sucher.db{db_stat}")
    except Exception as e:
        log(f"SQLite-Archiv fehlgeschlagen: {e}", "WARN")
        print("  ⚠ SQLite-Archiv fehlgeschlagen (JSON bleibt erhalten)")

    print(f"  ⏱ {time.time()-t0:.1f}s\n")
    print("  Tipp: --download lädt frei ladbare automatisch in --out.")

    if args.download:
        print("\n  --- Frei ladbare herunterladen ---")
        for i, r in enumerate(results):
            # URL bestimmen: zuerst OA-Resolver-Ergebnis, sonst das PDF-Feld
            url = None
            oa_res = r.get("_oa")
            if isinstance(oa_res, tuple) and len(oa_res) > 1:
                url = oa_res[1]
            elif r.get("pdf"):
                url = r["pdf"]
            if not url: continue
            name = re.sub(r"\W+","_", r.get("title","download"))[:50]   # OHNE Endung — Downloader entscheidet
            try:
                res = sdl.download(url, os.path.join(args.out, name))
                log(f"Download: {r.get('title','')[:40]} → {res}")
            except Exception as e:
                log(f"Download-Fehler {url}: {e}", "ERROR")

if __name__ == "__main__":
    main()
