# OpenCode-Review Blöcke 11–14 (04.09.2026)

**Reviewer:** OpenCode (deepseek-v4-flash), read-only
**Scope:** q_zenrows/q_searchapi/q_firecrawl, web_diagnose, _WEB_WEIGHT,
KEY_QUELLEN_MAP, golden_check.py, search()-Fanout
**Kontext:** 206 Tests grün, Gate 18/18, Kern-Anforderung „liefert immer etwas"

## Verdict: APPROVE-WITH-NITS

Die drei q_*-Funktionen sind API-korrekt, fehler-robust und getestet
(tests/test_block14_paid2.py). Labels matchen exakt die Register-Keys,
Alias-Normalisierung greift nicht falsch. Request-Shapes/Response-Keys
(ZenRows `results`/GET-autoparse, SearchAPI `organic_results`, Firecrawl `data`)
gegen Tests + Sibling-Quellen verifiziert.

## Findings

### F1 — MINOR (Security, GEFIXT): ZenRows-Key-Leak an Proxy-Fallback
Key steckt in der URL (`q_zenrows`). `net.get_json` macht bei 403/429 einen
Proxy-Retry mit derselben URL → Drittanbieter-Proxy bekäme `apikey=…`.
Bei monatlich erneuerbarem Key ist 403 realistisch.
**Fix (umgesetzt):** `net.get_json(url, timeout=12, proxy_retry=False)` —
ZenRows-Fehler werden direkt behandelt, kein Proxy-Retry mit Key-URL.
q_searchapi/q_firecrawl nicht betroffen (Key im Header).

### F2 — NIT (Concurrency, AKZEPTIERT): web_diagnose Mischzustand
Drei Keys werden in `search_web` ohne `_WEB_FEHLER_LOCK` geschrieben,
`web_diagnose()` liest ungeschützt → theoretisch Mischzustand (neues
`geliefert` + altes `aktiv`). Nur Diagnose, GIL-mäßig kein Crash, bei
Single-Thread-CLI real nie sichtbar. **Bewusste Entscheidung:** nicht fixen
(Diagnose-Anzeige toleriert 1-Lauf-Versatz; Lock würde Fanout unnötig bremsen).

### F3 — NIT (Stale, AKZEPTIERT): web_diagnose bei frühen Rückkehren
`search_web` returned bei unbekanntem `only` und `not active` ohne Diagnose-
Dict-Update → meldet vorherigen Lauf. **Bewusste Entscheidung:** nicht fixen
(CLI zeigt Diagnose nur nach erfolgreicher Suche; frühe Rückkehr = kein neuer
Lauf = alter Stand ist korrekt informativ).

## Verifikation
- Request-Shapes gegen Live-Doku geprüft (Firecrawl/SearchAPI-Docs via WebFetch)
- Fehlerpfade laufen über net-`_error` → `_log_web_error`
- Nicht laufend ausgeführt (keine Keys in Review-Umgebung)
