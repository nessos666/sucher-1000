# 04 — Pitfalls & Fixes: Websuche (gesammelt aus Qdrant-Sessions + Skills)

> Alles, was je schiefging und der Fix, der funktionierte. Quelle: Qdrant-Sessions
> (session-technical/session-project), SUCHER-V2.0-Lessons, DeepWeb-Audits, Hermes-Skills.

## 1. Hermes-web_search zeigt auf totes Backend (KRITISCH — 03.09.2026 gelöst)

**Symptom:** `web_search` liefert leer oder nur Wikipedia. „Geht Google, geht nicht."
**Ursache:** `config.yaml` → `search_backend: searxng`. SearXNG aggregiert öffentliche
Engines — nach Nutzung blocken sie alle (Brave „too many requests", DDG timeout,
Mojeek/Qwant „access denied", Startpage CAPTCHA). Nur Wikipedia antwortet.
**Fix:** Keys lagen ungenutzt in der Hermes-Env-Datei (`BRAVE_SEARCH_API_KEY`,
`TAVILY_API_KEY`). Gesetzt via:
```bash
hermes config set web.search_backend brave-free   # Search = Google-Qualität
hermes config set web.backend brave-free
# extract_backend: tavily war schon gesetzt (Key vorhanden)
```
**Verifiziert:** 2 Suchanfragen × 5 echte Treffer (IT-Systemhäuser, PTBS-Kliniken).
**Regel:** Config-Datei ist gegen Agent-Schreibzugriff geschützt → IMMER `hermes config set` nutzen.

## 2. „Ohne Limit, ohne Block" existiert nicht

Jede Engine blockt/drosselt unauthentifizierte Anfragen (Geschäftsmodell).
Claude Code/Codex „können immer suchen", weil deren **Server** bezahlte APIs nutzen.
Lösung ist nie ein Zauber-Tool, sondern: **Redundanz + Fallback-Kette + API-Keys + Proxy-ready.**

## 3. Brave-Free Monatslimit (schon einmal passiert — 17.07.2026)

**Symptom:** HTTP 402 nach ~1 Monat intensiver Nutzung.
**Fix damals:** `search_backend: brave-free → ddgs` (aus Qdrant-Nugget).
**Regel:** Wenn wieder 402/leer → `hermes config set web.search_backend ddgs`. DDGS läuft nachweislich.

## 4. HTTP 200 heißt nicht „Quelle funktioniert"

BASE (base-search.net) antwortet 200, liefert aber eine **Anubis-Botwall-HTML** statt JSON
→ Parser gibt still 0 Treffer. **Fix:** Roh-Bytes prüfen — `json.loads` muss klappen UND
erwartete Keys müssen da sein. Nie den 2xx-Status allein vertrauen.

## 5. SearXNG-Engines werden cyclisch blockiert

Google 403 (`SearxEngineAccessDeniedException`, suspended 180s), DDG CAPTCHA `wt-wt`.
Nach 12h intensiver Nutzung (15+ Suchen/Stunde). **Fix:** Nicht als alleinigen Fallback
nutzen; lokale Docker-Instanz als ERSTE in der Liste (öffentliche Instanzen waren 08/2026
alle tot). Startpage/Bing als Notnagel (schlechtere Qualität, aber stabil).

## 6. Wikipedia opensearch gibt ARRAY zurück, nicht dict

`[query,[titles],[desc],[urls]]` — `j.get(1)` crasht mit `AttributeError`.
**Fix:** `if not isinstance(j, list): continue`; dann `titles = j[1] if len(j)>1 else []`.
Sonst läuft ein kaputter `--quelle wikipedia`-Filter still ALLE Quellen statt nur Wikipedia.

## 7. Flag-Parsing: `index("--quelle")` mispaart Werte

Wenn der Wert auch in der Query auftaucht → falsche Paarung. **Fix:** Single-pass while-loop,
Flag + Wert zusammen konsumieren.

## 8. SSRF-Schutz darf nicht still scheitern

`import ipaddress` vergessen → NameError wird von `except: pass` verschluckt → ALLE URLs
geblockt. **Fix:** `pyflakes src/*.py` nach jeder Änderung. Fail CLOSED: DNS-Fail = Block.

## 9. Silent `except: pass` = stille Fehlerquelle

14+ solcher Blöcke akkumulierten sich in DeepWeb_Tool. Engine scheint zu laufen, liefert
aber 0. **Fix:** Zentraler Logger (`research_log.log_silent`) — loggt, persistiert, raised nie.

## 10. DDGS-Bot-Erkennung

DDGS CLI liefert zeitweise Müll (Metzgerei-/Porno-Treffer bei Firmensuche). **Fix:**
sofort auf SUCHER-Tool oder Bing-HTML wechseln. Python-Lib `ddgs` ist stabiler als CLI.

## 11. Google CSE gibt es nicht in Hermes (Stand 07/2026)

Recherche-Ergebnis aus Qdrant: „Kein Google-CSE-Support in Hermes. Verfügbare Backends:
ddgs, brave-free, searxng, tavily, firecrawl..." — Google Custom Search API war auf der
Todo-Liste, Setup pending.

## 12. Such-Infrastruktur-Audit (38 Searcher) — Methode

Phase 1 Inventar → Phase 2 Health Check (gleiche Queries, messen: erreichbar/HTTP/CAPTCHA/
Rate-Limit/echte-Firmenquote/Junkquote/Duplikate/Laufzeit) → Phase 3+ Ursachen → Ampel.
Report: `reports/search_infrastructure_inventory_2026.md` (12 Searcher dokumentiert).
