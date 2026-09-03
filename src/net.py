#!/usr/bin/env python3
"""
SUCHER — net.py (P2): Gehärteter Transport
===========================================
Zentrale HTTP-Schicht für ALLE Quellen. Ersetzt das heutige http_json in
sucher_universal.py mit denselben Rückgabe-Semantiken ({"_error": ...}),
aber gehärtet:

- 8s-Timeout hart (heute 25s × 12 sequenziell = bis 5 Min!)
- Format-Validierung: HTTP 200 ≠ Erfolg. Wer JSON anfordert und HTML/Captcha
  bekommt (BASE-Anubis-Falle!), erhält {"_error": "FORMAT: ..."}.
- Retry mit Backoff bei 429/5xx
- Test-Hook `_transport`: Tests setzen zur LAUFZEIT einen FakeTransport
  (nie Import-Zeit — Skill-Pitfall), dann wird kein Netz gebraucht.
- Proxy-Fallback: block_indicator + optionaler Retry über DataImpulse (proxy.py)

Rückgabe-Vertrag (kompatibel zu http_json):
  Erfolg  → das geparste JSON (dict/list)
  Fehler  → {"_error": "<grund>"}   — NIE Exception nach außen (außer _transport)
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

# ---------- Konfiguration ----------
UA = {"User-Agent": "Sucher1000/ (mailto:kontakt@sucher1000.example)"}
TIMEOUT_S = 8          # hart pro Request (heute 25s!)
RETRIES = 2
BACKOFF_429_S = 1.0    # kurz, nicht 5s

# Block-Marker: Body enthält Captcha/Botwall-Texte → zählt als Block
_BLOCK_MARKER = re.compile(
    r"(captcha|unusual traffic|access denied|attention required|"
    r"just a moment|verify you are human|anubis|making sure you're not a bot|"
    r"cf-chl|cf-browser-verification|enable javascript and cookies)",
    re.I,
)

# Test-Hook: Tests setzen net._transport zur LAUFZEIT (nie Import-Zeit).
_transport = None


def _open(url: str, timeout: int = TIMEOUT_S):
    """Echter Öffner ODER FakeTransport (wenn Test-Hook gesetzt).

    WICHTIG: gibt die Bytes zurück (nicht die Response) — die Response wird
    im with-Block geschlossen; wer sie nach außen gibt, liest 0 Bytes.
    FakeTransport liefert (status, body)-Tupel — _decode_body behandelt beide.
    """
    if _transport is not None:
        return _transport.open(url, timeout=timeout)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ---------- Block-Erkennung ----------

def block_indicator(body, erwartet="json"):
    """Erkennt Block-/Botwall-Antworten.

    - erwartet="json": Body muss JSON sein; HTML/Captcha = Block.
      Prüfung über ECHTEN json.loads-Versuch (nicht Präfixe) — gültige
      JSON-Skalare (true/false/null/123/"ok") gelten nicht als Block (F7).
    - erwartet="text": Body darf HTML sein; Captcha-Marker = Block
    Gibt den Grund zurück (str) oder None wenn kein Block.
    """
    if isinstance(body, bytes):
        probe_text = body.decode("utf-8", "ignore")
        probe = probe_text[:4000].lower()
    else:
        probe_text = str(body)
        probe = probe_text[:4000].lower()

    if erwartet == "json":
        # JSON anfordern: echter Parse-Versuch. Gültiges JSON (auch Skalare) = ok.
        try:
            import json as _json
            _json.loads(probe_text)
            return None  # echtes JSON — kein Block, egal welche Marker drin sind
        except Exception:
            # Kein JSON → prüfen ob HTML/Bot-Marker (dann Block) oder nur leeres/anders
            stripped = probe_text.lstrip()
            if stripped and not stripped.startswith(("{", "[")):
                return f"FORMAT: JSON erwartet, bekam Nicht-JSON ({len(body)} Bytes)"
    m = _BLOCK_MARKER.search(probe)
    if m:
        return f"BLOCK: '{m.group(0)}'"
    return None


def _decode_body(resp) -> bytes:
    """Body als Bytes normalisieren.

    - Echter Transport (net._open): liefert schon Bytes (im with gelesen)
    - FakeTransport: (status, body)-Tupel
    """
    if isinstance(resp, tuple) and len(resp) == 2:  # FakeTransport: (status, body)
        return resp[1] if isinstance(resp[1], bytes) else str(resp[1]).encode()
    if isinstance(resp, bytes):
        return resp
    if hasattr(resp, "read"):
        return resp.read()
    return str(resp).encode()


# ---------- Öffentliche API (kompatibel zu http_json) ----------

def get_json(url, timeout=TIMEOUT_S, retries=RETRIES, proxy_retry=True):
    """JSON laden mit Format-Validierung + Retry. Rückgabe: dict/list ODER {"_error": ...}.

    Vertrag (F6/OpenCode): garantiert dict ODER list. Gültige JSON-Skalare
    (true/123/"ok") sind zwar kein Block (F7/Codex), aber für Such-APIs nutzlos
    → werden als _error zurückgegeben, damit keine q_*-Funktion crasht.
    """
    last = None
    for i in range(retries + 1):
        try:
            body = _decode_body(_open(url, timeout=timeout))
            grund = block_indicator(body, erwartet="json")
            if grund:
                last = grund
                # Proxy-Retry nur 1× bei Block (wenn aktiviert + verfügbar)
                if proxy_retry and i == 0:
                    proxied = _try_proxy(url, timeout)
                    if proxied is not None:
                        return proxied
                continue
            parsed = json.loads(body.decode("utf-8", "replace"))
            if not isinstance(parsed, (dict, list)):
                # JSON-Skalar: kein Block, aber vertragswidrig → Fehler (F6)
                return {"_error": f"FORMAT: JSON-Skalar ({type(parsed).__name__}), erwarte Objekt/Liste"}
            return parsed
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < retries:
                time.sleep(BACKOFF_429_S)
                continue
            last = f"HTTP {e.code}"
            if proxy_retry and i == 0 and e.code in (403, 429):
                proxied = _try_proxy(url, timeout)
                if proxied is not None:
                    return proxied
        except Exception as e:
            last = str(e)[:80]
            if i < retries:
                time.sleep(0.5)
                continue
    return {"_error": last or "timeout"}


def post_json(url, payload: dict, timeout=TIMEOUT_S, retries=RETRIES,
              headers=None, proxy_retry=True):
    """POST-JSON mit gleicher Härtung wie get_json (F4/OpenCode-Gesamt).

    Für Tavily/Exa (POST-APIs) — 8s-Cap, Retry, Block-Erkennung, Proxy-Fallback.
    Rückgabe: dict/list ODER {"_error": ...}  (dict | list)
    """
    last = None
    data = json.dumps(payload).encode()
    for i in range(retries + 1):
        try:
            hdr = dict(UA)
            hdr["Content-Type"] = "application/json"
            if headers:
                hdr.update(headers)
            req = urllib.request.Request(url, data=data, headers=hdr)
            if _transport is not None:
                resp = _transport.open(url, timeout=timeout)
                body = _decode_body(resp)
            else:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    body = r.read()
            grund = block_indicator(body, erwartet="json")
            if grund:
                last = grund
                if proxy_retry and i == 0:
                    proxied = _try_proxy_post(url, payload, timeout, headers)
                    if proxied is not None:
                        return proxied
                continue
            parsed = json.loads(body.decode("utf-8", "replace"))
            if not isinstance(parsed, (dict, list)):
                return {"_error": f"FORMAT: JSON-Skalar ({type(parsed).__name__})"}
            return parsed
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < retries:
                time.sleep(BACKOFF_429_S)
                continue
            last = f"HTTP {e.code}"
            if proxy_retry and i == 0 and e.code in (403, 429):
                proxied = _try_proxy_post(url, payload, timeout, headers)
                if proxied is not None:
                    return proxied
        except Exception as e:
            last = str(e)[:80]
            if i < retries:
                time.sleep(0.5)
                continue
    return {"_error": last or "timeout"}


def _try_proxy_post(url, payload, timeout, headers=None):
    """POST über Proxy — 1× Versuch, None wenn kein Proxy."""
    try:
        import proxy
        return proxy.fetch_post(url, payload, timeout=timeout,
                                erwartet="json", headers=headers)
    except Exception:
        return None


def get_text(url, timeout=TIMEOUT_S, retries=RETRIES, proxy_retry=True):
    """HTML/Text laden mit Block-Erkennung. Rückgabe: (text, error_or_None)."""
    last = None
    for i in range(retries + 1):
        try:
            body = _decode_body(_open(url, timeout=timeout))
            grund = block_indicator(body, erwartet="text")
            if grund:
                last = grund
                if proxy_retry and i == 0:
                    proxied = _try_proxy(url, timeout, erwartet="text")
                    if proxied is not None:
                        # F4 (OpenCode): Proxy-Text-Antwort auch auf Block prüfen —
                        # Captcha/Botwall vom Proxy darf nicht als Erfolg gelten
                        pgrund = block_indicator(proxied, erwartet="text")
                        if pgrund:
                            last = f"proxy:{pgrund}"
                        else:
                            return proxied, None
                continue
            return body.decode("utf-8", "ignore"), None
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if proxy_retry and i == 0 and e.code in (403, 429):
                proxied = _try_proxy(url, timeout, erwartet="text")
                if proxied is not None:
                    return proxied, None
        except Exception as e:
            last = str(e)[:80]
            if i < retries:
                time.sleep(0.5)
                continue
    return "", last or "timeout"


def _try_proxy(url, timeout, erwartet="json"):
    """1× identischer Request über DataImpulse-Proxy (neue IP). None wenn kein Proxy.

    erwartet wird an proxy.fetch durchgereicht: "json" parst JSON,
    "text" gibt den HTML-Body zurück (F2 — vorher immer json → Text-Pfad kaputt).
    """
    try:
        import proxy
        return proxy.fetch(url, timeout=timeout, erwartet=erwartet)
    except Exception:
        return None
