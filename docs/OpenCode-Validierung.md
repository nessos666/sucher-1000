# OpenCode-Validierung für SUCHER 1000

## Status (durch Hermes bereits validiert)
- ✅ Alle Module kompilieren (`py_compile`) — keine Syntaxfehler
- ✅ End-to-End: `python3 sucher.py "posttraumatic growth" 3` → 17 Treffer
- ✅ Die 10 Verbesserungen getestet (PubMed, Wikidata, Lokal, --jahr, --oa, --sort, --markdown)

## OpenCode-Validierung (du führst sie aus — braucht deinen Key)
OpenCode ist installiert, aber braucht die Env-Variable `OPENROUTER_API_KEY` (nur du hast den Key;
Hermes-Agent darf Secrets nicht auslesen/weiterreichen).

### Einmalig: Key setzen (Shell)
```bash
export OPENROUTER_API_KEY="dein-openrouter-key"    # der Key aus deiner Hermes-Config/.env
```

### Code reviewen
```bash
cd ~/HAUPTLAGER/03_PROJEKTE/42_Sucher_Tool
opencode run "Prüfe src/*.py und sucher.py auf Bugs, Laufzeitfehler und Verbesserungen. Kurz (DE), max 15 Zeilen."
```
- `opencode` wird unter `~/.local/bin/opencode` gefunden (bestätigt).
- Modell-Konfig: OpenRouter (`deepseek-v4-flash`), siehe `~/.opencode/opencode.json`.

## Warum Hermes OpenCode nicht direkt ausführt
Die Auth schlägt fehl, weil `OPENROUTER_API_KEY` nicht in der Umgebung des Agents gesetzt ist und
Hermes Keys nicht manuell aus der Config liest (Datenschutz). Deshalb: skeptischer, aber du führst
den finalen OpenCode-Review einmalig selbst aus — danach ist die zweite, unabhängige Prüfung abgeschlossen.

## Module zu prüfen
| Datei | Rolle |
|---|---|
| `sucher.py` | Haupt-Einstieg (Pipeline suche→OA→download→log) |
| `src/sucher_universal.py` | 9 Wissenschafts- + 3 Allgemein-Quellen + Filter/Optionen |
| `src/sucher_oa.py` | OA-Resolver (Unpaywall/OpenAlex/EuropePMC) |
| `src/sucher_download.py` | curl→Browser-Engine-Fallback, PDF-Erkennung |