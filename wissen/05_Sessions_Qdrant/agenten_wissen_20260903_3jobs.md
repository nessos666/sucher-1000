# Agenten-Wissen 03.09.2026 (3 Subagenten, live-verifiziert)

Drei parallele Recherche-Agenten (deleg_21cdde20) haben neues Wissen für
SUCHER-1000 gesammelt. ALLE Quellen-Status-Aussagen wurden am 03.09.2026 per
Live-Probe (deutsche Server-IP) geprüft.

---

## A) UX für Nicht-Programmierer (Agent 1) — Top-10-Prioritäten

1. **Begrüßung statt Fehlerwand** bei Aufruf ohne Argumente: deutsche Kurzanleitung
   mit 1-2 Beispielen + Angebot Dialog-Modus (Muster: jq, clig.dev)
2. **Interaktiver Such-Assistent** (nur wenn TTY): Schritt-für-Schritt-Fragen,
   nummerierte Ergebnisse, dann Aktion: Browser öffnen (Nr.) / Datei speichern /
   Neue Suche. Menüs verhindern Tippfehler (questionary/gum)
3. **Konfig-Wizard `sucher config`** (rclone-config-Muster): Key einmalig abfragen
   (unsichtbar), Verbindung testen, Quellen an/aus, Cache leeren
4. **setup.sh All-in-one**: prüft python3, legt venv an, installiert deps, fragt
   optionalen Key interaktiv (ohne Echo), schreibt .env (chmod 600), erzeugt
   `sucher`-Starter in ~/.local/bin, set -e + trap, Deinstall-Hinweis
5. **Einzeiler-Installation + Doppelklick**: `curl -fsSL <URL> | bash` + Desktop-
   Datei (Sucher-starten.desktop) für Nutzer ohne Terminal-Gewohnheit
6. **Fehlermeldungen 100% Deutsch**: „Was ist passiert? / Warum? / So behebst du
   es" — kein Traceback im Normalmodus; Bug-Report-URL bei unerwarteten Fehlern
7. **Farben + Fortschritt + Zusammenfassung**: Grün/Gelb/Rot/Cyan semantisch,
   „Prüfe Quelle 3/10…", nach Lauf „9 von 10 Quellen, 1 gesperrt"
8. **Demo im README**: asciinema/GIF nach dem Titel, Beispiel-Ausgabe, 3 Copy-
   Paste-Befehle, Try-it-online (GitHub-Codespaces)
9. **Hilfe/Cheatsheet/Web-Doku auf Deutsch**: `--help` mit Beispielen zuerst,
   `sucher hilfe <thema>` (tldr-Stil), `sucher version`/`sucher check`
10. **UX-Checkliste** als docs/UX-CHECKLISTE.md mit Vorbild-Tools (gh, rclone,
    httpie, gum) — vor Release gegenprüfen + 1-2 echte Laien testen lassen

## B) Neue Such-Quellen fürs Bündel (Agent 2) — live geprüft, Top-8

| Rang | Quelle | Status 03.09.2026 | Key | Typ |
|---|---|---|---|---|
| 1 | **HackerNews-Algolia-API** | ✅ 200, Treffer | keiner | JSON, 10k req/h |
| 2 | **Google-News-RSS** | ✅ 200 (hl=de) | keiner | RSS (Redirect-Tokens auflösen!) |
| 3 | **Marginalia-Search (api2)** | ✅ lebt (public=429 geteilt) | public/frei | JSON, Small-Web |
| 4 | **You.com API Free** | ✅ (ohne Key 403 → Account-Key nötig) | frei, 100/Tag | JSON |
| 5 | **Bing-News-RSS** | ✅ 200 | keiner | RSS (gleicher format=rss-Trick) |
| 6 | **GDELT DOC-2.0** | ⚠️ Timeouts heute | keiner | JSON, weltweite News |
| 7 | **Reddit Data-API** (offiziell OAuth) | .json=403! | App-Registrierung frei | JSON, 100qpm |
| 8 | **MetaGer** | ⚠️ JSON-API unbelegt | anon. Key | nur Prüfauftrag |

**Verworfen (mit Begründung):** Brave (Free-Tier tot 02/2026, Karte), Yahoo
(BOSS tot 2016, =Bing-Duplikat), Startpage (Voll-Botwall), Qwant (DataDome+
ToS-grau), Ecosia (kein API), Kagi ($12/1000, Karte), Presearch (Key+Paid),
Mojeek-API (nur paid — HTML schon drin).
**Kontext:** Bing-API offiziell tot (11.08.2025), aber Bing-RSS-Trick lebt;
Google-CSE stirbt 01.01.2027.

## C) Echtes Suchen testen + Qualität messen (Agent 3) — Top-8

1. **Test-Ebenen trennen**: Offline-Suite (Record/Replay via VCR.py) pro Commit;
   separater Live-Runner; manuelle Sichtprüfung. Nie Live-Tests in normale Suite!
2. **Golden-Query-Set** (30-100 Queries aus Davids Alltag + erwartete Domains
   als Ground Truth): Assertion „erwartete Domain in Top-5", nicht exakter Rang
3. **TREC-Format übernehmen, nicht Drop-in** (Live-Web ≠ fixes Korpus): eigenes
   Mini-qrels-Set mit Mini-Pooling
4. **Metriken ehrlich**: Precision@k + MRR@k (erste relevante Domain), KPI =
   Expected-Domain-Hit-Rate in Top-10; 0 ≠ UNKNOWN unterscheiden
5. **Menschliche Bewertung institutionalisieren**: 20-50 Queries × Top-5,
   Google-QRG-Skala (Fully/HM/MM/Fails); LLM nur Prefilter
6. **Reproduzierbares Harness**: Query-Set-Version, Zeitstempel, Tool-Commit,
   Label-Version loggen; gleiche Query 2× laufen (Rauschen messen)
7. **Canary-Check je Quelle**: bekannte URL + Content-Fingerprint über
   Produktionspfad, MIT Cache-Bypass, Retry vor Alert, Quarantäne
8. **Rhythmus**: Commit=offline schnell; täglich Cron 03:00=Live-Smoke+
   Canaries; wöchentlich=volles Benchmark (Precision@k/MRR); monatlich=Fehler-
   Taxonomie reviewen

---

## Nächste umsetzbare Schritte (konsolidiert, priorisiert)

**Block A (UX Laien):** (1) Dialog-Modus in launch.sh, (2) deutsche Fehlertexte,
(3) Fortschritt X-von-Y in pretty()
**Block B (neue Quellen):** (1) q_hn (HackerNews, key-frei, JSON), (2)
q_google_news (RSS, Redirect-Auflösung), (3) q_bing_news (RSS) — alle 3 mit
bestehender net.py-Infrastruktur machbar
**Block C (Testing):** (1) Live-Runner-Skript (scripts/live_check.py) mit
Golden-Queries, (2) Canary je Quelle, (3) VCR-Record/Replay für die 5
Live-markierten Tests
