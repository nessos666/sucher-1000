# SUCHER-1000 — Universal-Websucher

> **Eine Suche — viele Quellen parallel.** Web + Wissenschaft in einem
> Kommandozeilen-Tool. **Funktioniert IMMER**: Fällt eine Quelle aus oder
> blockt (Captcha/403/429), liefern die anderen weiter — und das Tool merkt
> sich, welche Quelle krank ist, und überspringt sie 60 Minuten lang
> (Selbstheilung).
>
> Hinweis: Die Zahl `n` ist **pro Quelle** — bei 24 Web-Quellen liefert
> `sucher.py "…" 3 --modus web` bis zu ~72 Treffer (dedupliziert). Wer
> wenige Treffer will, nimmt kleinere `n` oder `--quelle <name>`.

Web-Suche (**24 Quellen**: ddgs, Bing, Mojeek, Wikipedia, HackerNews,
Google News, Bing News, StackExchange, Wikiquote/Wikinews/Wikisource,
OpenLibrary, Internet Archive, GitHub, HuggingFace, Google Patents, YouTube,
Google Scholar, Google Autosuggest — key-frei; + Tavily/Exa/SerpApi/Reddit/
KnowledgeGraph/GoogleBooks als Key-optional)
**und** wissenschaftliche Suche (OpenAlex, PubMed, arXiv, Crossref, DOAJ,
EuropePMC, SemanticScholar, Zenodo, DataCite, DBLP, OpenAIRE, ClinicalTrials,
OpenReview, OSF, CORE, DOAB + Wikipedia/Wikidata) in **einem** Befehl.

---

## 🚀 Schnellstart (30 Sekunden)

```bash
# 1. Klonen + venv einrichten
git clone <dein-repo-url> sucher-1000
cd sucher-1000
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. Loslegen — fertig! (kein API-Key nötig)
.venv/bin/python sucher.py "Körpertherapie PTBS München" 8 --modus web
```

Einfacher: `./launch.sh` (Menü: Web / Studien / Alles).

## 🎯 Beispiele

```bash
# Web-Suche (mehrere Engines parallel)
.venv/bin/python sucher.py "IT Systemhaus München" 5 --modus web

# Wissenschaftliche Suche
.venv/bin/python sucher.py "posttraumatic growth EMDR" 5 --modus studien

# ALLES: Web + Studien zusammen (parallel, dedupliziert)
.venv/bin/python sucher.py "Trauma Therapie" 5 --modus alle

# Nur eine Quelle
.venv/bin/python sucher.py "KI Agenten" 5 --quelle openalex

# 🔎 Archiv-Suche (lokal, kein Netz): durchsucht ALLE gespeicherten Suchen
.venv/bin/python sucher.py --archiv 'bentonit'          # Präfix: findet 'Bentonite'
.venv/bin/python sucher.py --archiv 'water retention'   # UND: beide Wörter nötig
.venv/bin/python sucher.py --archiv 'trauma !kindheit'  # NOT: ohne 'kindheit'

# Setup prüfen / Quellen anzeigen
.venv/bin/python sucher.py --setup
.venv/bin/python sucher.py --sources
```

## 🔑 Optionale Keys (nicht nötig zum Loslegen)

Alle Kern-Quellen sind key-frei. Zusätzliche Quellen (Tavily, Exa, SerpApi,
Reddit, KnowledgeGraph, GoogleBooks, Serper, You.com) aktivierst du mit Keys —
**am einfachsten über den Assistenten** (Eingabe verdeckt + Live-Test):

```bash
.venv/bin/python scripts/sucher_auth.py            # Status aller Key-Quellen
.venv/bin/python scripts/sucher_auth.py --add serper  # Key setzen + testen
```

Oder manuell: siehe `.env.example` — Keys kommen aus der Umgebung, aus
`~/.hermes/.env` ODER `~/.config/sucher1000/keys.env` (vom Assistenten
geschrieben, chmod 600). Fehlt ein Key, wird die Quelle übersprungen
(Meldung mit Key-URL, kein Fehler).

## 🧠 Warum „funktioniert IMMER"?

| Mechanismus | Was es tut |
|---|---|
| **Multi-Engine-Bündel** | 4+ key-freie Web-Quellen parallel — eine blockt, andere liefern |
| **Health-Registry** | Quelle 3× krank → 60 Min Cooldown (übersprungen statt ertragen) |
| **Selbstheilung** | Nach Cooldown wird die Quelle wieder probiert — erholt sie sich, ist sie wieder aktiv |
| **Captcha-Erkennung** | Botwall-Antworten werden erkannt und gemeldet, nicht als „0 Treffer" verkauft |
| **Hartes Budget** | Max 30s Gesamtsuche, 8s pro Request — nie ewiges Hängen |
| **TTL-Cache** | Gleiche Suche binnen 15 Min = aus Cache (schnell, kein Netz) |
| **Rate-Limiting** | Pro Quelle gedrosselt — weniger Block-Risiko |
| **SQLite-Archiv** | Jede Suche wird gespeichert (`data/sucher.db`) |
| **Hermes-unabhängig** | Eigenes venv, kein Server, keine Cloud — überlebt jedes Update |

## 🩺 Qualität

- **206 automatisierte Tests** (Netz gemockt — offline reproduzierbar)
- Profi-Quality-Gate: `./check.sh` → Syntax + mypy + ruff + bandit + pytest
- Von 2 unabhängigen KI-Reviewern auditiert (Codex + OpenCode), alle Findings behoben
- Jeder Block einzeln committet — saubere, nachvollziehbare Historie
- Golden-Query-Check: `python scripts/golden_check.py` → 12 Themen, echte Live-Messung
  der Treffer-Qualität (Report in `docs/audits/`)

## 💡 Tipp: Ergebnis-Archiv durchsuchen (Linux)

SUCHER speichert jede Suche als strukturierte Datei (`--out <ordner>`), oft auch im
SQLite-Archiv. Zum schnellen Durchsuchen gespeicherter Ergebnisse im Terminal:

```bash
# Aliase + ss()-Funktion einmalig einrichten (in ~/.bashrc):
alias bat='batcat'   # Ubuntu: bat heißt batcat
alias fd='fdfind'    # Ubuntu: fd heißt fdfind

# 1) Blitz-Suche im Ergebnis-Ordner (10× schneller als grep):
rg --smart-case "PTBS" ergebnisse/

# 2) Interaktives Live-Filtern mit Vorschau (fzf + bat):
rg --no-heading "bentonit" ergebnisse/ | fzf --preview 'bat --color=always {1}'
```

Voraussetzung (einmalig): `sudo apt install ripgrep fzf bat fd-find`
Details: `docs/recherche_linux_suchverbesserung_20260904.md`

## 📁 Projektstruktur

```
setup.sh                ← All-in-one-Installation (venv + sucher-Starter)
sucher.py               ← CLI-Einstieg (Begrüßung + interaktiver Assistent)
launch.sh               ← Menü-Launcher
check.sh                ← Quality-Gate (Syntax+mypy+ruff+bandit+pytest)
scripts/
  sucher_auth.py        ← API-Key-Assistent (verdeckte Eingabe + Live-Test)
  health_check.py       ← Quellen-Health-Check (parallel)
src/
  sucher_universal.py   ← 16 akademische Quellen + Parallel-Fanout
  sucher_web.py         ← Web-Bündel (26 Quellen) + Fallbacks
  net.py                ← Gehärteter Transport (8s, Retry, Botwall-Erkennung)
  health.py             ← Health-Registry + Cooldown
  cache.py              ← TTL-Such-Cache
  ratelimit.py          ← Pro-Quellen-Drosselung
  store.py              ← SQLite-Archiv
tests/                  ← 29 Test-Dateien, 192 Tests
docs/                   ← Pläne + Reviews (Codex/OpenCode) + Audits
wissen/                 ← Recherche-Wissen (Quellen, Marktlage, Pitfalls)
```

## 📜 Lizenz

MIT — frei nutzbar, veränderbar, weitergebbar. (Siehe LICENSE.)

## 🙋 FAQ

**Muss ich Hermes/OpenAI installieren?** Nein. Nur Python 3.11+ und Internet.

**Werden meine Suchen gespeichert?** Lokal in `data/sucher.db` (SQLite) — nur
auf deinem Rechner.

**Was, wenn eine Quelle blockt?** Andere liefern weiter. Die blockende Quelle
wird erkannt, gemeldet und für 60 Min übersprungen (Health-Cooldown).
