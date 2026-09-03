# SUCHER-1000 — Universal-Websucher

> **Eine Suche — viele Quellen parallel.** Web + Wissenschaft in einem
> Kommandozeilen-Tool. **Funktioniert IMMER**: Fällt eine Quelle aus oder
> blockt (Captcha/403/429), liefern die anderen weiter — und das Tool merkt
> sich, welche Quelle krank ist, und überspringt sie 60 Minuten lang
> (Selbstheilung).
>
> Hinweis: Die Zahl `n` ist **pro Quelle** — bei 10 Web-Quellen liefert
> `sucher.py "…" 3 --modus web` bis zu ~30 Treffer (dedupliziert). Wer
> wenige Treffer will, nimmt kleinere `n` oder `--quelle <name>`.

Web-Suche (**10 Quellen**: ddgs, Bing, Mojeek, Wikipedia DE+EN, HackerNews,
Google News, Bing News — alle key-frei; + optionale Tavily/Exa/SerpApi)
**und** wissenschaftliche Suche (OpenAlex, PubMed, arXiv, Crossref, DOAJ,
EuropePMC, SemanticScholar, Wikidata) in **einem** Befehl.

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

# Setup prüfen / Quellen anzeigen
.venv/bin/python sucher.py --setup
.venv/bin/python sucher.py --sources
```

## 🔑 Optionale Keys (nicht nötig zum Loslegen)

Alle Kern-Quellen sind key-frei. Zusätzliche Quellen (Tavily, Exa, SerpApi)
aktivierst du mit Keys — siehe `.env.example`. Fehlt ein Key, wird die Quelle
übersprungen (Meldung, kein Fehler).

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

- **121 automatisierte Tests** (Netz gemockt — offline reproduzierbar)
- Profi-Quality-Gate: `./check.sh` → Syntax + mypy + ruff + bandit + pytest
- Von 2 unabhängigen KI-Reviewern auditiert (Codex + OpenCode), alle Findings behoben
- Jeder Block einzeln committet — saubere, nachvollziehbare Historie

## 📁 Projektstruktur

```
sucher.py               ← CLI-Einstieg
launch.sh               ← Menü-Launcher
check.sh                ← Quality-Gate (1 Befehl)
src/
  sucher_universal.py   ← 10 akademische Quellen + Parallel-Fanout
  sucher_web.py         ← Web-Bündel (10 Quellen) + Fallbacks
  net.py                ← Gehärteter Transport (8s, Retry, Botwall-Erkennung)
  health.py             ← Health-Registry + Cooldown
  cache.py              ← TTL-Such-Cache
  ratelimit.py          ← Pro-Quellen-Drosselung
  store.py              ← SQLite-Archiv
tests/                  ← 19 Test-Dateien, 121 Tests
docs/                   ← Pläne + Reviews + Audits
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
