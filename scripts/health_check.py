#!/usr/bin/env python3
"""
SUCHER-1000 — Read-only Health-Check (P0)
==========================================
Misst ALLE Quellen mit EINER Standard-Query: erreichbar? Treffer? Latenz? Fehler?
NUR MESSEN — baut nichts um, ändert keine Config, schreibt nur den Report.

Nutzung:
  python3 scripts/health_check.py                # akademisch + allgemein + web
  python3 scripts/health_check.py --modus web    # nur Web-Bündel
  python3 scripts/health_check.py --json         # als JSON (für Audit)

Ergebnis: docs/audits/quellen_health_2026.md (oder --json auf stdout).
"""
import os, sys, time, json, re
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "src")
sys.path.insert(0, SRC)

QUERY = "posttraumatic growth"
N = 3
TIMEOUT_PER = 12

def _measure(name, fn):
    """Eine Quelle einmal ausführen: Treffer/Fehler/Latenz messen."""
    t0 = time.time()
    try:
        res = fn(QUERY, N) or []
        lat = round(time.time() - t0, 1)
        if not res:
            return {"quelle": name, "status": "0 Treffer", "treffer": 0,
                    "latenz_s": lat, "fehler": None}
        return {"quelle": name, "status": "OK", "treffer": len(res),
                "latenz_s": lat, "fehler": None,
                "beispiel": res[0].get("title", "")[:60]}
    except Exception as e:
        lat = round(time.time() - t0, 1)
        return {"quelle": name, "status": "FEHLER", "treffer": 0,
                "latenz_s": lat, "fehler": str(e)[:100]}

def main():
    only_web = "--modus" in sys.argv and sys.argv[sys.argv.index("--modus")+1] == "web"
    as_json = "--json" in sys.argv

    # Akademische + allgemeine Quellen (sucher_universal)
    import sucher_universal as su
    akad = {}
    for name, fn in su.SCI.items():
        akad[name] = fn
    general = {k: fn for k, fn in su.GENERAL.items() if k != "lokal"}

    # Web-Bündel (sucher_web)
    import sucher_web as sw
    web = dict(sw.WEB)

    ergebnisse = []
    if not only_web:
        for grp, srcs in (("WISSENSCHAFT", akad), ("ALLGEMEIN", general)):
            for name, fn in srcs.items():
                ergebnisse.append(_measure(name, fn))
        ergebnisse.append(_measure("lokal", su.GENERAL["lokal"]))
    for name, fn in web.items():
        ergebnisse.append(_measure(name, fn))

    # F4 (Codex): --json muss AUSSCHLIESSLICH gültiges JSON auf stdout geben.
    if as_json:
        print(json.dumps(ergebnisse, ensure_ascii=False, indent=2))
        return

    # Text-/Report-Modus: erst jetzt die menschenlesbare Ausgabe
    print(f"Health-Check SUCHER-1000 (Query: {QUERY!r}, n={N}) — {datetime.now():%H:%M:%S}\n")
    if not only_web:
        for grp, names in (("WISSENSCHAFT", list(akad)), ("ALLGEMEIN", list(general))):
            print(f"== {grp} ==")
            for name in names:
                r = next((x for x in ergebnisse if x["quelle"] == name), None)
                if not r: continue
                f = r["fehler"] or ""
                print(f"  [{r['status']:11s}] {name:15s} {r['treffer']:2d} Treffer "
                      f"{r['latenz_s']:>5.1f}s{f'  {f}' if f else ''}")
        r = next((x for x in ergebnisse if x["quelle"] == "lokal"), None)
        if r:
            print(f"\n== LOKAL (Offline-Rettungsanker) ==")
            print(f"  [{r['status']:11s}] {r['quelle']:15s} {r['treffer']:2d} Treffer {r['latenz_s']:>5.1f}s")
        print()

    print("== WEB-BÜNDEL ==")
    for name in web:
        r = next((x for x in ergebnisse if x["quelle"] == name), None)
        if not r: continue
        f = r["fehler"] or ""
        print(f"  [{r['status']:11s}] {name:10s} {r['treffer']:2d} Treffer "
              f"{r['latenz_s']:>5.1f}s{f'  {f}' if f else ''}")

    # Report schreiben
    outdir = os.path.join(BASE, "docs", "audits")
    os.makedirs(outdir, exist_ok=True)
    fn_out = os.path.join(outdir, "quellen_health_2026.md")
    with open(fn_out, "w", encoding="utf-8") as f:
        f.write(f"# Quellen-Health-Check SUCHER-1000 — {datetime.now():%Y-%m-%d %H:%M}\n\n")
        f.write(f"Query: `{QUERY}` · n={N} · Timeout {TIMEOUT_PER}s/Quelle · Read-only (kein Umbau)\n\n")
        f.write("| Quelle | Status | Treffer | Latenz | Fehler |\n")
        f.write("|--------|--------|:-------:|:------:|--------|\n")
        for r in ergebnisse:
            f.write(f"| {r['quelle']} | {r['status']} | {r['treffer']} | "
                    f"{r['latenz_s']}s | {r['fehler'] or '-'} |\n")
        f.write("\n## Status-Legende\n")
        f.write("- **OK** = liefert Treffer · **0 Treffer** = erreichbar, aber nichts gefunden\n")
        f.write("- **FEHLER** = Quelle blockt/crasht (Fehlertext = Ursache)\n\n")
    print(f"\n→ Report: {fn_out}")

if __name__ == "__main__":
    main()
