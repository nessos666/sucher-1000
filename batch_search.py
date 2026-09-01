#!/usr/bin/env python3
"""
BATCH-STUDIENSUCHE — führt mehrere präzise Queries aus und sammelt Ergebnisse.
Nutzung: python3 batch_search.py
"""
import sys, os, json, time, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import studien_search as ss

# Präzise Kern-Themen (David 2026)
QUERIES = {
    "vegetotherapie_reich": "Wilhelm Reich vegetotherapy character analysis body",
    "bioenergetik_lowen": "bioenergetic analysis Lowen body psychotherapy",
    "koerpertherapie_kptbs": "body oriented therapy complex PTSD somatic",
    "emdr_koerper": "EMDR body oriented complex PTSD mechanisms",
    "somatic_experiencing": "somatic experiencing trauma effectiveness",
    "polyvagal_regulation": "polyvagal theory nervous system regulation trauma",
    "bindungstrauma_koerper": "attachment trauma body brain disconnect",
    "trauma_lernen_anpassung": "trauma learning adaptation posttraumatic growth",
}

def run():
    os.makedirs("batch_results", exist_ok=True)
    all_results = {}
    for name, q in QUERIES.items():
        print(f"\n{'='*60}\n### {name}: {q}")
        res = ss.search(q, n=8)
        # nur frei ladbare + mit PDF behalten fürs Herunterladen
        free = [r for r in res if r.get("is_oa") or r.get("pdf")]
        print(f"  → {len(res)} Treffer, {len(free)} frei/PDF")
        all_results[name] = {"query": q, "results": res}
        with open(f"batch_results/{name}.json", "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        time.sleep(1)
    # Gesamt-Index
    with open("batch_results/INDEX.json", "w", encoding="utf-8") as f:
        json.dump({k: {"query": v["query"], "count": len(v["results"])} for k, v in all_results.items()}, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Batch fertig. Ergebnisse in batch_results/ ({len(QUERIES)} Themen)")

if __name__ == "__main__":
    run()