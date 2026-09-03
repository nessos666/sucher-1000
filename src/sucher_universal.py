#!/usr/bin/env python3
"""
SUCHER — UNIVERSAL (Ausbaustufe 1000+)
Universelle Suche für JEDES Thema/Kontext. Mehrere Modi:
  --modus studien   : nur wissenschaftliche Quellen (OpenAlex/DOAJ/Crossref/EuropePMC/SemanticScholar)
  --modus universal : Studien + Allgemeinwissen (Wikipedia/Wikidata) — breiteste Suche
  --modus alle      : alle verfügbaren Quellen (ohne Einschränkung)
  --quelle NAME     : nur eine bestimmte Quelle
  --list           : verfügbare Quellen anzeigen
Nutzung: python3 sucher_universal.py "suchbegriff" [anzahl] [--modus M] [--quelle Q]
"""
import json
import os
import re
import sys
import threading
import urllib.parse
import urllib.request

UA = {"User-Agent": "Sucher1000/ (mailto:kontakt@sucher1000.example)"}
OUTDIR = "sucher_ergebnisse"
os.makedirs(OUTDIR, exist_ok=True)

# ---------- Fehler-Sichtbarkeit (P1): nie still schlucken ----------
_QUELLEN_FEHLER: dict = {}   # quelle -> (letzter Fehler, anzahl)
_QUELLEN_FEHLER_LOCK = threading.Lock()  # F5/OpenCode: atomarer Zugriff aus Threads

def _log_quellenfehler(quelle, exc):
    """Quellen-Fehler sichtbar machen: sammeln + auf stderr ausgeben.

    Ersetzt stille `except: pass` — der Lauf läuft weiter, aber der Fehler
    ist dokumentiert und am Ende der Suche abrufbar (search() -> diagnostics).
    Thread-sicher (Lock) — Worker-Threads schreiben aus Parallelität (F5).
    """
    msg = str(exc)[:120]
    with _QUELLEN_FEHLER_LOCK:
        _QUELLEN_FEHLER[quelle] = (msg, _QUELLEN_FEHLER.get(quelle, (None, 0))[1] + 1)
    print(f"  ⚠ [{quelle}] Fehler: {msg}", file=sys.stderr)

def _get_quellen_fehler():
    """Diagnose: welche Quellen sind fehlgeschlagen und warum."""
    with _QUELLEN_FEHLER_LOCK:
        return {q: (m, n) for q, (m, n) in _QUELLEN_FEHLER.items() if n > 0}

def _check_fehler(quelle, j):
    """True wenn j ein _error-Dict ist — UND loggt den Fehler (F3/OpenCode).

    Vorher: `if "_error" in j: return []` ohne Logging → Timeout/429 (die
    häufigsten Fehler) erschienen nie im Register, pretty() meldete
    fälschlich „keine Quellen-Fehler" obwohl Quellen tot waren.
    """
    if isinstance(j, dict) and j.get("_error"):
        _log_quellenfehler(quelle, j["_error"])
        return True
    return False


def http_json(url, timeout=8, retries=2):
    """Kompatibilitäts-Shim → net.get_json (P2: 8s-Timeout, Format-Validierung).

    F9 (OpenCode): Default auf 8 korrigiert (war 25, wurde aber ohnehin hart
    auf 8 reduziert) — kein Aufrufer geht mehr von einem falschen Timeout aus.
    """
    import net
    return net.get_json(url, timeout=timeout, retries=retries)

# ---------- Wissenschaftliche Quellen ----------
def q_openalex(query, n=8):
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode({
        "search": query, "per-page": n, "sort": "relevance_score:desc"})
    j = http_json(url)
    if _check_fehler("openalex", j): return []
    out=[]
    for w in j.get("results", []):
        oa = w.get("open_access") or {}
        pl = w.get("primary_location") or {}
        src = pl.get("source") or {}
        out.append({"title": w.get("title") or "", "year": w.get("publication_year"),
            "venue": src.get("display_name") if src else "",
            "is_oa": oa.get("is_oa", False),
            "pdf": oa.get("oa_url") or (w.get("best_oa_location") or {}).get("pdf_url"),
            "doi": w.get("doi"), "source": "OpenAlex", "url": w.get("doi"),
            "cites": w.get("cited_by_count", 0),
            "relevance": (w.get("relevance_score") or 0)})
    return out

def q_crossref(query, n=8):
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode(
        {"query": query, "rows": n, "select": "title,DOI,issued,container-title,URL"})
    j = http_json(url)
    if _check_fehler("crossref", j): return []
    out=[]
    for w in j.get("message", {}).get("items", []):
        # Robust: date-parts kann leer/verschachtelt sein → kein IndexError
        yr = None
        try:
            dp = (w.get("issued",{}) or {}).get("date-parts", None)
            if isinstance(dp, list) and dp and isinstance(dp[0], list) and dp[0]:
                yr = dp[0][0]
        except Exception:
            yr = None
        out.append({"title": (w.get("title") or [""])[0], "year": yr,
            "venue": (w.get("container-title") or [""])[0] if w.get("container-title") else "",
            "is_oa": False, "pdf": None, "doi": w.get("DOI"), "source": "Crossref", "url": w.get("URL")})
    return out

def q_doaj(query, n=8):
    url = "https://doaj.org/api/search/articles/" + urllib.parse.quote(query) + f"?pageSize={n}&page=1"
    j = http_json(url)
    if _check_fehler("doaj", j): return []
    out=[]
    for r in j.get("results", []):
        b=r.get("bibjson",{}); loc=r.get("bibjson",{}).get("link",[{}])
        url_pdf=next((l.get("url") for l in loc if l.get("type")=="fulltext"), None)
        # Robust: identifier kann leer sein
        doi=None
        ids = b.get("identifier") or []
        if ids and isinstance(ids[0], dict):
            doi = ids[0].get("id")
        out.append({"title": b.get("title",""), "year": b.get("year"),
            "venue": b.get("journal",{}).get("title","") if b.get("journal") else "",
            "is_oa": True, "pdf": url_pdf, "doi": doi,
            "source": "DOAJ", "url": url_pdf})
    return out

def q_europepmc(query, n=8):
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urllib.parse.urlencode(
        {"query": query, "format":"json", "pageSize": n, "resultType":"core"})
    j = http_json(url)
    if _check_fehler("europepmc", j): return []
    out=[]
    for r in j.get("resultList",{}).get("result",[]):
        url_pdf=None
        for t in r.get("fullTextUrlList",{}).get("fullTextUrl",[]) if r.get("fullTextUrlList") else []:
            if t.get("availability")=="Open access": url_pdf=t.get("url"); break
        out.append({"title": r.get("title",""), "year": r.get("pubYear"),
            "venue": r.get("journalInfo",{}).get("journal",{}).get("title","") if r.get("journalInfo") else "",
            "is_oa": r.get("isOpenAccess", False), "pdf": url_pdf, "doi": r.get("doi"),
            "source": "EuropePMC", "pmcid": r.get("pmcid"),
            "url": f"https://pmc.ncbi.nlm.nih.gov/articles/{r['pmcid']}/" if r.get("pmcid") else None})
    return out

def q_semanticscholar(query, n=8):
    url = "https://api.semanticscholar.org/graph/v1/paper/search?" + urllib.parse.urlencode(
        {"query": query, "limit": n, "fields":"title,year,venue,openAccessPdf,externalIds,url"})
    j = http_json(url)
    if _check_fehler("semanticscholar", j) or not j.get("data"): return []
    out=[]
    for r in j["data"]:
        oa=r.get("openAccessPdf") or {}
        out.append({"title": r.get("title",""), "year": r.get("year"),
            "venue": r.get("venue",""), "is_oa": bool(oa), "pdf": oa.get("url"),
            "doi": (r.get("externalIds") or {}).get("DOI"), "source":"SemanticScholar", "url": r.get("url")})
    return out

# ---------- Allgemein-Wissen Quellen (universal) ----------
def q_wikipedia(query, n=6):
    """Allgemeine Web-/Wissenssuche (deutsch + englisch)."""
    out=[]
    for lang in ("de","en"):
        url = f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
            {"action":"opensearch","search":query,"limit":n,"format":"json"})
        j = http_json(url)
        if _check_fehler("wikipedia", j) or not isinstance(j, list): continue
        titles = j[1] if len(j) > 1 else []
        descs  = j[2] if len(j) > 2 else []
        urls   = j[3] if len(j) > 3 else []
        for i,t in enumerate(titles):
            out.append({"title": t, "year": None, "venue": f"Wikipedia({lang.upper()})",
                "is_oa": True, "pdf": None, "doi": None, "source": "Wikipedia",
                "url": urls[i] if i < len(urls) else None,
                "snippet": descs[i] if i < len(descs) else ""})
    return out

# ---------- Preprint-Quellen (neu) ----------
def q_arxiv(query, n=6):
    """arXiv-API (Atom-Feed): Preprints Physik/ML/quantitativ.

    F2 (OpenCode): nutzt net.get_text (8s-Cap, Block-Erkennung, Proxy-Fallback)
    statt direktem urlopen(timeout=30) — eine hängende arXiv-Antwort kann das
    Gesamtbudget nicht mehr fressen.
    """
    import net as _net
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(
        {"search_query": f"all:{query}", "max_results": n, "sortBy":"relevance"})
    xml, err = _net.get_text(url)
    if err:
        _log_quellenfehler("arxiv", err)
        return []
    out = []
    for e in re.findall(r"<entry>.*?</entry>", xml, re.DOTALL):
        t = re.search(r"<title>(.*?)</title>", e, re.DOTALL)
        link = re.search(r'<link href="(http[^"]*)"', e)
        summ = re.search(r"<summary>(.*?)</summary>", e, re.DOTALL)
        out.append({
            "title": re.sub(r"\s+"," ",t.group(1).strip()) if t else "",
            "year": None, "venue": "arXiv", "is_oa": True,
            "pdf": None, "doi": None, "source": "arXiv",
            "url": link.group(1) if link else None,
            "snippet": re.sub(r"\s+"," ",summ.group(1))[:150] if summ else ""})
    return out

# ---------- Neu: PubMed / Wikidata / Lokal ----------
def q_pubmed(query, n=6):
    """PubMed (NCBI eutils): biomedizinische Forschung mit PMID/PMCID."""
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode(
        {"db":"pubmed","term":query,"retmax":n,"retmode":"json","sort":"relevance"})
    j = http_json(url)
    if _check_fehler("pubmed", j): return []
    ids = (j.get("esearchresult",{}) or {}).get("idlist",[]) or []
    if not ids: return []
    # Metadaten holen
    u2 = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?" + urllib.parse.urlencode(
        {"db":"pubmed","id":",".join(ids),"retmode":"json"})
    j2 = http_json(u2)
    if _check_fehler("pubmed", j2): return []  # F10: auch 2. Request loggen
    out=[]
    res = (j2.get("result") or {})
    for pid in ids:
        r = res.get(pid,{})
        if not r or not r.get("title"): continue
        doi = ""
        for aid in r.get("articleids",[]) or []:
            if aid.get("idtype")=="doi": doi=aid.get("value","")
        out.append({"title": r.get("title",""), "year": r.get("pubdate","")[:4],
            "venue": (r.get("fulljournalname") or r.get("source") or "PubMed"),
            "is_oa": False, "pdf": None, "doi": doi or None,
            "source":"PubMed", "url": f"https://pubmed.ncbi.nlm.nih.gov/{pid}/",
            "snippet": r.get("description","")[:120]})
    return out

def q_wikidata(query, n=6):
    """Wikidata: strukturierte Wissenseinträge/Entitäten."""
    url = "https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode(
        {"action":"wbsearchentities","search":query,"language":"de","format":"json","limit":n})
    j = http_json(url)
    if _check_fehler("wikidata", j): return []
    out=[]
    for e in (j.get("search") or [])[:n]:
        out.append({"title": e.get("label") or e.get("id"),
            "year": None, "venue":"Wikidata", "is_oa": True, "pdf":None, "doi":None,
            "source":"Wikidata",
            "url": f"https://www.wikidata.org/wiki/{e.get('id')}",
            "snippet": e.get("description","")})
    return out

def q_lokal(query, n=10, zeitlimit_s=3):
    """LOKAL-SUCHE: durchsucht Davids HAUPTLAGER-Wissensbasis (Datei-NAMEN).
    Findet, was DAVID schon hat — vermeidet Doppelrecherche.
    Hinweis (F8/OpenCode): matcht NUR Dateinamen, nicht Datei-Inhalt
    (Inhalts-Suche wäre zu langsam über 133GB).
    P3: hartes Zeitlimit (default 3s) — os.walk über 133GB darf die Suche nie
    blockieren; wird auch INNERHALB großer Verzeichnisse geprüft (F8)."""
    import time as _time
    base = "~//HAUPTLAGER"
    kw = [w.lower() for w in query.split() if len(w)>3]
    hits=[]
    t_start = _time.monotonic()
    for root,dirs,files in os.walk(base):
        if _time.monotonic() - t_start > zeitlimit_s:
            break  # Zeitlimit erreicht — Teilergebnis liefern
        # Tiefe begrenzen + Systemordner auslassen
        if root.count(os.sep)-base.count(os.sep) > 5: dirs[:]=[]
        if any(x in root for x in (".git","node_modules","07_SYSTEM","20_FROZEN")):
            dirs[:]=[]; continue
        for f in files:
            if _time.monotonic() - t_start > zeitlimit_s:
                break  # F8: auch innerhalb eines riesigen Ordners stoppen
            if not f.lower().endswith((".md",".pdf",".txt",".bib")): continue
            name = f.lower()
            if any(k in name for k in kw):
                full=os.path.join(root,f)
                hits.append({"title":f,"year":None,"venue":"Lokal-HAUPTLAGER","is_oa":True,
                    "pdf":None,"doi":None,"source":"Lokal",
                    "url":full,"snippet":os.path.relpath(full,base)[:140]})
                if len(hits)>=n: break
        if len(hits)>=n: break
    return hits

# ---------- Quellen-Register ----------
SCI = {"openalex": q_openalex, "crossref": q_crossref, "doaj": q_doaj,
       "europepmc": q_europepmc, "semanticscholar": q_semanticscholar,
       "arxiv": q_arxiv,
       "pubmed": q_pubmed}   # bioRxiv weggelassen: dessen API hat KEINE Freiwort-Suche (nur DOI/COVID) → leer
GENERAL = {"wikipedia": q_wikipedia, "wikidata": q_wikidata, "lokal": q_lokal}

def resolve_sources(mode):
    """Gibt die aktiven Quellen je Modus zurück."""
    if mode == "studien":   return dict(SCI)
    if mode == "universal": return {**SCI, **GENERAL}
    if mode == "alle":      return {**SCI, **GENERAL}
    return dict(SCI)  # default

def search(query, n=8, mode="universal", only=None, min_year=None, oa_only=False, sort_by="relevance", expand=True, budget_s=30):
    """Suche über alle aktiven Quellen — PARALLEL mit hartem Gesamtbudget (P3).

    - Quellen laufen gleichzeitig (ThreadPool), Gesamtzeit = langsamste Quelle,
      nicht die Summe (vorher: bis 5 Min bei 12×25s sequenziell!)
    - Budget hart: nach budget_s Sekunden wird abgebrochen, Teilergebnisse bleiben
    - Dedup + Scoring NACH dem Fanout → deterministische Reihenfolge
    - Jede Quelle läuft in eigenem Thread; Fehler werden geloggt (P1), nie still
    """
    import queue as _queue
    import threading as _t
    import time as _time

    # F5 (Codex): Fehlerregister pro Lauf — alte Fehler dürfen nicht in neue Suche
    # hineinwirken (vorher: global, nie zurückgesetzt → falsche Diagnosen)
    _QUELLEN_FEHLER.clear()

    active = resolve_sources(mode)
    if only:
        if only in active:
            active = {only: active[only]}
        else:
            # Unbekannte Quelle: Meldung statt still ALLE Quellen zu durchsuchen
            print(f"  ⚠ Unbekannte Quelle '{only}' — verfügbar: {', '.join(active.keys())}", file=sys.stderr)
            return []
    # --- Query-Expansion: engli/DE + Basis ---
    queries = _expand_query(query) if expand else [query]

    # --- Parallel-Fanout: Aufgaben = (Quelle × Query-Variante) ---
    seen, results = set(), []
    budget_ueberschritten = False
    t_start = _time.monotonic()

    # P4: Health-Registry — BROKEN/NO_KEY-Quellen überspringen statt ertragen
    try:
        import health as _health
        _reg = _health.HealthRegistry()
    except Exception:
        _reg = None
    _übersprungen = []
    tasks = []
    for qy in queries:
        for name, fn in active.items():
            if _reg is not None:
                skip, grund = _reg.is_skippable(name)
                if skip:
                    _übersprungen.append((name, grund))
                    continue
            tasks.append((name, fn, qy))
    if _übersprungen:
        for name, grund in _übersprungen:
            print(f"  ⏭ [{name}] übersprungen: {grund}", file=sys.stderr)
    if not tasks:
        return []

    # F1 (OpenCode): eigene DAEMON-Threads statt ThreadPoolExecutor. Py3.11-
    # ThreadPoolExecutor joint beim Prozess-Exit ALLE Worker (auch daemon) via
    # _python_exit → Prozess hängt nach Budget. Daemon-Threads sterben mit dem
    # Interpreter, der Prozess endet sofort.
    ergebnis_q = _queue.Queue()
    threads = []
    for name, fn, qy in tasks:
        def _run(name=name, fn=fn, qy=qy):
            # F6 (OpenCode): Fehler-Zählerstand VOR dem Aufruf merken — der
            # Worker meldet seinen EIGENEN Fehlerstatus im Tupel mit, statt dass
            # der Health-Commit das globale Register liest (das verwaiste
            # Daemon-Threads aus Lauf 1 nach clear() von Lauf 2 verfälschen könnten).
            try:
                with _QUELLEN_FEHLER_LOCK:
                    vorher = _QUELLEN_FEHLER.get(name, (None, 0))[1]
                payload = list(fn(qy, n))
                with _QUELLEN_FEHLER_LOCK:
                    nachher = _QUELLEN_FEHLER.get(name, (None, 0))[1]
                hatte_fehler = nachher > vorher
                ergebnis_q.put((name, "ok" if not hatte_fehler else "err_lokal",
                                payload, hatte_fehler))
            except Exception as e:
                # Fehlertext direkt mitschicken — der Main-Loop loggt GENAU EINMAL
                # (Doppel-Log würde den Text mit leerem payload überschreiben)
                ergebnis_q.put((name, "err", str(e), True))
        t = _t.Thread(target=_run, daemon=True)
        t.start()
        threads.append(t)

    # Ergebnisse einsammeln bis Budget abläuft oder alle fertig sind
    offen = len(tasks)
    quellen_mit_treffern = set()
    quellen_mit_fehler = {}   # F6: quelle -> (fehlertext, hatte_fehler) pro Lauf
    quellen_abgeschlossen = set()  # F2-Codex: nur GEMELDETE Quellen healthen
    while offen > 0 and _time.monotonic() - t_start < budget_s:
        try:
            name, status, payload, hatte_fehler = ergebnis_q.get(timeout=0.2)
            offen -= 1
            quellen_abgeschlossen.add(name)
            if status == "ok":
                if payload:
                    quellen_mit_treffern.add(name)
                for it in payload:
                    key = ((it.get("title") or "") + (it.get("url") or "")).lower()[:90]
                    if key and key not in seen:
                        seen.add(key); results.append(it)
            elif status == "err":
                # Echte Exception — hier loggen (Worker schickt den Text mit)
                _log_quellenfehler(name, payload)
            # status == "err_lokal": q_*-Funktion loggte selbst via _check_fehler
            # → hier NICHT nochmal loggen (würde Text mit leerem payload überschreiben)
            if hatte_fehler and name not in quellen_mit_treffern:
                # Fehlertext aus dem Lauf-Register (nur wenn dieser Lauf ihn setzte)
                with _QUELLEN_FEHLER_LOCK:
                    fehlertext = _QUELLEN_FEHLER.get(name, ("", 0))[0]
                quellen_mit_fehler[name] = fehlertext
        except _queue.Empty:
            continue  # noch keine Antwort — weiter auf Budget warten

    if offen > 0:
        budget_ueberschritten = True
        # Verwaiste Threads NICHT joinen — daemon, sterben mit Prozess (F1)

    # P4-Fix (Codex-Review): Health PRO QUELLE aggregieren, genau EINMAL nach
    # dem Fanout committen — nicht pro (Quelle × Variante):
    #   - Quelle hat Treffer geliefert ODER keinen Fehler geloggt → ok
    #   - Quelle steht im Fehlerregister UND keine Variante lieferte Treffer → Fehler
    # Das verhindert: (a) _error-Fehler als HEALTHY (alter Bug), (b) 3 Varianten =
    # 3 consecutive fails → zu schnelles BROKEN, (c) Completion-Order-Abhängigkeit.
    # F6: Health liest NUR quellen_mit_fehler (pro Lauf vom Worker gemeldet),
    # NICHT das globale _QUELLEN_FEHLER (verwaiste Threads können es verfälschen).
    if _reg is not None:
        try:
            # F2 (Codex-Gesamt): NUR abgeschlossene Quellen committen. Quellen,
            # die das Budget rissen (nie geantwortet), werden NICHT bewertet —
            # vorher wurden sie fälschlich als HEALTHY verbucht (Timeout als
            # Gesundheit kaschiert, unterlief Cooldown/Selbstheilung).
            for name in quellen_abgeschlossen:
                hat_fehler = name in quellen_mit_fehler
                fehlertext = quellen_mit_fehler.get(name, "")
                if hat_fehler and name not in quellen_mit_treffern:
                    _reg.record_outcome(name, ok=False, error=fehlertext)
                else:
                    _reg.record_outcome(name, ok=True)
            _reg.save()
        except Exception:  # noqa: S110 - bewusster Fallback (optional)
            pass
    # --- Filter: min_year ---
    if min_year:
        results = [r for r in results if _ok_year(r.get("year"), min_year)]
    # --- Filter: nur Open Access ---
    if oa_only:
        results = [r for r in results if r.get("is_oa") or r.get("pdf")]
    # --- Cross-Quellen-Scoring (relevanteste zuerst) — NACH Fanout, deterministisch ---
    if sort_by != "jahr":
        results = _score_sort(results)
    else:
        results.sort(key=lambda r: (_to_int(r.get("year")) or 0) if r.get("year") else 0, reverse=True)
    if budget_ueberschritten:
        print(f"  ⚠ Gesamtbudget ({budget_s}s) überschritten — Teilergebnis ({len(results)} Treffer)", file=sys.stderr)
    return results


def _expand_query(query):
    """Query-Expansion: basis + deutsche/englische Varianten + Kernbegriffe."""
    q = query.strip()
    variants = [q]
    # Wichtigste Begriffskombinationen (DE↔EN) mitlösen
    de_en = {
        "mutter": "mother", "toxisch": "toxic", "narzisstisch": "narcissistic",
        "kind": "child", "selbstwert": "self-esteem", "selbstsabotage": "self-sabotage",
        "emotionale vernachlässigung": "emotional neglect",
        "beschämung": "shaming",
    }  # "trauma"="trauma" bewusst weggelassen (DE==EN → redundante Variante)
    # Wenn deutsche Begriffe im Query, englische Ergänzung hinzufügen
    lower = q.lower()
    en_found, de_found = [], []
    for de, en in de_en.items():
        if de.lower() in lower and en not in en_found:
            en_found.append(en)
        if en in lower and de not in de_found:
            de_found.append(de)
    # Kombinierte Variante (EN Begriffe ergänzen)
    if en_found:
        variants.append(q + " " + " ".join(en_found))
    if de_found:
        variants.append(q + " " + " ".join(de_found))
    # Dedup
    seen=set(); out=[]
    for v in variants:
        if v and v not in seen:
            seen.add(v); out.append(v)
        if len(out)>=3: break
    return out

def _score_sort(results):
    """Cross-Quellen-Scoring: gewichtet nach Zitaten (cites), Relevanz, OA, Quelle."""
    # Quelle-Gewicht (Peer-reviewed stärker)
    q_weight = {"OpenAlex":1.0, "EuropePMC":1.0, "Crossref":0.8, "DOAJ":0.8,
                "PubMed":0.9, "arXiv":0.5, "SemanticScholar":0.8,
                "Wikipedia":0.3, "Wikidata":0.3, "Lokal":0.6}
    def score(r):
        cites = r.get("cites") or 0
        rel = r.get("relevance") or 0
        src = q_weight.get(r.get("source"), 0.6)
        oa = 0.15 if (r.get("is_oa") or r.get("pdf")) else 0
        # Zitate log-skaliert (häufig 0), + Relevanz + Quelle + OA
        s = (min(cites, 200) / 40.0) + (rel * 1.5) + src + oa
        return s
    # F7 (OpenCode): deterministisch bei Punktgleichstand — sortiere nach Score,
    # dann nach Titel/URL als stabilem letzten Schlüssel (nicht nach
    # Thread-Completion-Reihenfolge der parallelen Futures)
    return sorted(results, key=lambda r: (score(r), (r.get("title") or "")[:80]), reverse=True)

def _to_int(y):
    try: return int(str(y)[:4])
    except Exception: return None

def _ok_year(y, min_year):
    yi = _to_int(y)
    return yi is not None and yi >= min_year

def pretty(results, mode):
    print(f"\n→ {len(results)} Treffer (Modus: {mode}, dedupl.)\n")
    for r in results:
        oa = "✅ FREI" if r.get("is_oa") else ("🟡 PDF?" if r.get("pdf") else "🔒 geschützt")
        lbl = r.get("title") or "(ohne Titel)"
        cites = f" · 📈{r['cites']}" if r.get("cites") else ""
        print(f"[{oa}] [{r.get('source')}] {lbl}{cites}  ({r.get('year') or ''})")
        if r.get("venue"): print(f"      {r['venue']}")
        if r.get("snippet"): print(f"      {r['snippet']}")
        if r.get("doi"): print(f"      DOI: {r['doi']}")
        if r.get("pdf"): print(f"      PDF: {r['pdf']}")
        if r.get("pmcid"): print(f"      PMC: https://pmc.ncbi.nlm.nih.gov/articles/{r['pmcid']}/")
        if r.get("url") and r.get("source")!="OpenAlex": print(f"      Link: {r['url']}")
        print()
    # Quellen-Fehler am Ende sichtbar machen (P1)
    fehler = _get_quellen_fehler()
    if fehler:
        print("⚠ Quellen-Fehler (diese Quellen lieferten nichts):")
        for q, (m, n) in fehler.items():
            print(f"   - {q}: {m} ({n}×)")

def main():
    argv = sys.argv[1:]
    query = None
    n = 8
    mode = "universal"
    only = None
    min_year = None
    oa_only = False
    sort_by = "relevance"
    md_export = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--modus" and i+1 < len(argv):
            mode = argv[i+1]; i += 2
        elif a == "--quelle" and i+1 < len(argv):
            only = argv[i+1]; i += 2
        elif a == "--jahr" and i+1 < len(argv):
            try: min_year = int(argv[i+1]); i += 2
            except: i += 2
        elif a == "--oa":
            oa_only = True; i += 1
        elif a == "--sort" and i+1 < len(argv):
            sort_by = argv[i+1]; i += 2
        elif a == "--markdown":
            md_export = True; i += 1
        elif a == "--list":
            print("Verfügbare Quellen:\n  WISSENSCHAFT:", ", ".join(SCI.keys()))
            print("  ALLGEMEIN:", ", ".join(GENERAL.keys()))
            print("Modi: studien | universal | alle")
            print("Optionen: --jahr YYYY --oa --sort jahr|relevance --markdown")
            return
        else:
            if query is None:
                query = a
            elif isinstance(a, str) and a.isdigit() and n == 8:
                n = int(a)
            i += 1
    if query is None:
        query = "somatic experiencing trauma"
    res = search(query, n, mode, only, min_year=min_year, oa_only=oa_only, sort_by=sort_by)
    pretty(res, mode)
    base = "ergebnis_" + re.sub(r'\W+','_', query)[:40]
    fn = os.path.join(OUTDIR, base + ".json")
    with open(fn, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(f"→ JSON gespeichert: {fn}")
    if md_export:
        mdfn = os.path.join(OUTDIR, base + ".md")
        with open(mdfn, "w", encoding="utf-8") as f:
            f.write(f"# Suchergebnis: {query}\n_(Modus: {mode}, {len(res)} Treffer)_\n\n")
            for r in res:
                f.write(f"- **{r.get('title','?')}** ({r.get('source','')}, {r.get('year') or ''})\n")
                if r.get("url"): f.write(f"  - {r['url']}\n")
        print(f"→ Markdown gespeichert: {mdfn}")

if __name__ == "__main__":
    main()
