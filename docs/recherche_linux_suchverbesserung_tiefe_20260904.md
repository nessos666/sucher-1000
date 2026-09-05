# Recherche TIEFE: Suchfunktionen verbessern — Algorithmen + System-Ebene

**Datum:** 04.09.2026 · **Projekt:** SUCHER-1000 (42_Sucher_Tool)
**Auftrag:** David — gleiche Thema, eine Ebene TIEFER (nach Basis-Recherche
`recherche_linux_suchverbesserung_20260904.md`)
**Fokus Ebenen:** (1) Suchalgorithmen, (2) Index-Engines, (3) Linux-System-Tuning,
(4) Ist-Zustand auf Davids Rechner

---

## 1. Ist-Zustand auf Davids Rechner (gemessen, nicht geraten)

| Check | Ergebnis | Bewertung |
|---|---|---|
| ulimit (offene Dateien) | **1.048.576** | ✅ schon hoch — parallele Fanouts kein FD-Problem |
| systemd-resolved | **aktiv** | ✅ DNS-Cache läuft bereits |
| SQLite FTS5 | **verfügbar** (built-in) | ✅ kein Zusatz-Paket nötig |
| sucher.db | **864 archivierte Ergebnisse**, 33 Queries | 💎 Datenschatz für FTS-Index |

**Kernerkenntnis:** Die System-Ebene ist schon gut. Der größte ungenutzte Hebel
ist **FTS5 auf die 864 archivierten Ergebnisse** — lokale Blitz-Suche über alles,
was SUCHER je gefunden hat.

---

## 2. Ebene 1 — Suchalgorithmen (wie fzf intern wirklich rechnet)

### 2.1 FuzzyMatchV2 (fzf, timothya.com — visualisiert)

fzf behandelt Fuzzy-Matching als **Optimierungsproblem**: Von allen Arten, ein
Muster durch den Text zu fädeln, gewinnt die höchste Punktzahl. Implementierung:
modifizierter **Smith-Waterman** (Dynamic Programming) — keine Zeichen-Omissionen,
nur Lücken-Wahl.

**Die Scoring-Tabelle (wörtlich aus fzf-Code):**
| Signal | Konstante | Wert | Bedeutung |
|---|---|---|---|
| Zeichen-Treffer | scoreMatch | +16 | Basis-Belohnung |
| Lücke beginnt | scoreGapStart | −3 | Strafe beim Öffnen |
| Lücke läuft weiter | scoreGapExtension | −1 | billiger als neue Lücke |
| Wortgrenze | bonusBoundary | +8 | Treffer am Wortanfang zählt |
| Nach Whitespace/BOS | bonusBoundaryWhite | +10 | stärkste Grenze |
| Nach `/ , : ; \|` | bonusBoundaryDelimiter | +9 | Pfad/CSV-Trenner |
| camelCase/Zahl | bonusCamel123 | +7 | implizite Grenze im Wort |
| Aufeinanderfolgend | bonusConsecutive | +4 | „foob" trifft „foobar", nicht „foo-bar" |
| Erster Buchstabe | bonusFirstCharMultiplier | ×2 | das erste getippte Zeichen wiegt mehr |

**Design-Prinzip:** Grenz-Bonus ist kalibriert, von ~8 Zeichen Lücke aufgehoben
zu werden → fzf bleibt Fuzzy-Finder, kein Akronym-Matcher: kurze dichte Treffer
schlagen weit gespannte Grenz-Hopper.

**4 Phasen je Aufruf:**
1. ASCII-Gate: billiger Zwei-Zeiger-Scan findet Fenster; wenn unmöglich → sofort −1
2. Bonuses + erste DP-Zeile: B[i] pro Position (klassenabhängig, einmal berechnet)
3. DP-Füllung mit Rekurrenz `H[i][j] = max(H[i-1][j-1]+match+bonus, H[i][j-1]+gap, 0)`
4. Backtrace über H + C-Matrix (Consecutive-Runs) → Match-Positionen

**Cross-Keystroke-Cache (die Killer-Optimierung):** Wenn Query „foo" → „foob"
(strikte Erweiterung), dann enthält jeder „foob"-Kandidat zwingend „foo" → fzf
re-scored nur die Überlebenden, nicht das ganze Korpus. Bei 100k Items mit 50
Treffern: 100k×Query-Länge pro Tastendruck → **50×Query-Länge nach dem ersten
Tastendruck**.

**Pattern-Grammatik (übertragbar auf jede CLI-Suche):**
- `foo bar` = UND (beide fuzzy, Scores summiert)
- `'foo` = exakter Substring (kein Fuzzy)
- `^foo` / `foo$` = Anfang/Ende
- `!foo` = Negation
- `'src ^algo` = „enthält 'src' UND beginnt mit algo"

**Tiebreaker:** gleicher Score → kürzerer Text gewinnt, dann frühere Position.

### 2.2 BM25 (arpitbhayani.me + GeeksforGeeks — Ranking)

**Kern-Einsicht:** TF-IDF ist linear — ein Dokument, das „photosynthesis" 200×
nennt, scoret doppelt so hoch wie 100×. Aber Relevanz **sättigt**: Die ersten
Vorkommen sind starke Evidenz, jedes weitere trägt weniger bei, irgendwann fast
nichts. BM25 modelliert das:

```
score(D,Q) = Σ IDF(q) · (f·(k1+1)) / (f + k1·(1 − b + b·|D|/avgdl))
IDF(q) = ln((N − n(q) + 0.5) / (n(q) + 0.5))
```

- `k1` (≈1.2–2.0): Term-Frequency-Sättigung
- `b` (≈0.75): Dokumentlängen-Normalisierung — **bei gleicher TF gewinnt das
  kürzere Dokument** (meist gewünscht bei variierenden Längen)

### 2.3 Was das für SUCHER heißt
- **Query-Grammatik** (`'exakt`, `^start`, `!ausschluss`) wäre ein CLI-Add-on
  für die Filterung lokaler Treffer — Muster von fzf direkt übernehmbar
- **Scoring mit Grenz-Bonus** statt nacktem Substring-Match für Titel-Ranking
- **Inkrementeller Cache** existiert bei uns schon als TTL-Cache (anderer Zweck:
  Netz statt UI) — fzf-Muster zeigt: Query-Präfix-Cache würde Live-Filtern
  von 100k Ergebnissen erst möglich machen

---

## 3. Ebene 2 — Index-Engines (SQLite FTS5 = der Gewinner für SUCHER)

### 3.1 Warum FTS5 statt LIKE
- `LIKE '%term%'` = „lies alles, prüfe jede Zeile" (CPU-Scan, kein Ranking)
- FTS5 = **Inverted Index** („springe direkt zu den Zeilen mit dem Term") —
  bei 50k+ Zeilen massiv schneller

### 3.2 FTS5-Fähigkeiten (thelinuxcode.com, geprüft)
| Feature | SQL |
|---|---|
| Virtuelle Tabelle | `CREATE VIRTUAL TABLE x USING fts5(titel, snippet, content=..., content_rowid=...)` |
| BM25-Ranking built-in | `SELECT ... ORDER BY bm25(x)` (niedriger = besser) |
| Spalten-Gewichte | `bm25(x, 2.0, 0.5)` — Titel wichtiger als Snippet |
| UND/ODER/NICHT | `MATCH 'python AND paced'` |
| Phrase | `MATCH '"self paced"'` |
| Präfix (Autocomplete) | `MATCH 'pyth*'` |
| Spalten-Scoping | `MATCH 'titel:python'` |
| Highlight/Snippet | `highlight(x, 1, '[', ']')`, `snippet(x, ...)` |
| Sync via Triggers | INSERT/UPDATE/DELETE-Trigger halten FTS aktuell |
| Porter-Stemming | Tokenizer-Option: „searching"/„searched" → „search" |

**Praxis-Checkliste der Quelle:** kanonische Tabelle + External-Content-FTS +
3 Trigger (insert/update/delete) + `MATCH`-Muster + bm25-Sortierung + Golden-
Query-Eval-Set (20–50 echte Suchen + LLM-Vorschläge für Gewichte + deterministische
Tests) — **unsere golden_queries.json ist genau so ein Eval-Set!**

### 3.3 Meilisearch/Typesense/Elasticsearch (nur als Kontext)
- Meilisearch (Rust), Typesense (C++): „80 % von ES-Funktionalität zu 20 % der
  Kosten", halten Index im RAM, typo-tolerant, für Instant-Search gebaut
- Elasticsearch (Lucene): verteilt, skalierbar, aber Overhead
- **Für SUCHER irrelevant** — FTS5 in der vorhandenen SQLite-DB reicht für
  864→100k Zeilen; keine neue Engine nötig (0€-Prinzip, kein Server)

---

## 4. Ebene 3 — Linux-System-Tuning (DNS, ulimit, TCP)

### 4.1 DNS-Caching (oneuptime.com)
| Lookup-Stufe | Typische Latenz |
|---|---|
| Lokaler Cache-Hit | <1 ms |
| Resolver-Cache-Hit | 1–10 ms |
| Volle Auflösung | 50–200 ms |

**Bei 30+ parallelen Requests an 30+ verschiedene Domains = bis zu 30 volle
Auflösungen** (50–200 ms je) — spürbar! Aber: **systemd-resolved ist bei David
aktiv** → Caching läuft schon. Prüfen: `resolvectl statistics`.

**Python-App-Ebene (optional, wenn viele Requests an gleiche Domains):**
Monkeypatch von `socket.getaddrinfo` mit TTL-Cache (300s) + Lock — Code aus der
Quelle direkt übernehmbar. Für SUCHER: viele Quellen = viele Domains, aber jede
Domain 1× pro Suche → **App-Level-Cache lohnt nur bei Wiederhol-Suchen**; der
TTL-Cache (15 Min) deckt das bereits ab.

### 4.2 ulimit / offene Dateien (venkat.eu)
- Jede Verbindung = 1 File-Descriptor (Linux unterscheidet nicht Datei/Socket)
- Default oft 1024 → „too many open files" ab ~600 parallelen Requests
- Soft/Hard-Limit: `ulimit -Sn` / `ulimit -Hn`
- Diagnose laufender Prozess: `cat /proc/PID/limits | grep "Max open files"`,
  `ls /proc/PID/fd | wc -l` (Zähler), `ss -tnp | grep pid=PID` (Sockets),
  CLOSE_WAIT-Haufen = Leak
- **Bei David: ulimit = 1.048.576 — kein Handlungsbedarf**

### 4.3 TCP-Sysctls (venkat.eu, Referenz)
```
net.ipv4.tcp_tw_reuse = 1        # TIME_WAIT-Sockets wiederverwenden
net.ipv4.tcp_fin_timeout = 5     # schnelleres Schließen
net.ipv4.tcp_max_orphans = 32768
net.ipv4.ip_local_port_range = 1025 61000   # viele ausgehende Ports
```
Nur bei Massen-Verbindungen relevant — SUCHER-Fanout (30–40 gleichzeitig) ist
davon weit entfernt; nicht anfassen.

---

## 5. Was wir daraus für SUCHER-1000 nehmen (Tiefen-Ebene)

### D1 — FTS5-Volltext-Index auf sucher.db (größter Hebel, 0€)
864 archivierte Ergebnisse → `ergebnisse`-Tabelle hat schon Struktur. Neues
Feature `sucher --archiv "begriff"`: FTS5-Index über Titel/Snippet/URL, BM25-
Ranking, `'exakt`/`!ausschluss`-Grammatik (fzf-Muster), Highlight. **Nutzt
vorhandene DB, kein neuer Server, kein Key.**
→ Umsetzung: Migration + FTS5-View + CLI-Flag + RED-Tests (feste Praxis).

### D2 — Query-Grammatik für Treffer-Filter (fzf-Muster)
`^start`, `'exakt`, `!negation`, `a AND b` in der lokalen Filterung — kleine
Parser-Funktion, direkt testbar.

### D3 — Golden-Set als Gewichts-Eval nutzen (FTS5-Empfehlung deckt sich)
thelinuxcode empfiehlt: „Golden-Queries + LLM-Gewichtsvorschläge + deterministische
Tests". **Unsere golden_queries.json ist exakt dieses Eval-Set** — damit FTS5-
Spaltengewichte kalibrieren (Titel > Snippet > URL).

### D4 — Kein Handlungsbedarf (gemessen):
- ulimit 1M ✅ · systemd-resolved ✅ · TCP-Sysctls: nicht nötig
- Meilisearch/Typesense: Overkill für 100k-Zeilen-SQLite

*Bericht aus Tiefen-Recherche (04.09.2026). Quellen: timothya.com (fzf-Algorithmus,
visualisiert), arpitbhayani.me + GeeksforGeeks (BM25), thelinuxcode.com (FTS5 in
Praxis), oneuptime.com (DNS-Caching), venkat.eu (File-Descriptors/ulimit).*
