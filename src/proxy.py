#!/usr/bin/env python3
"""
SUCHER — proxy.py (P2): DataImpulse-Proxy-Wrapper
==================================================
Optionaler Proxy-Retry für geblockte Quellen. Credentials NUR aus Env
(never im Code — Skill-Regel). Kein Import-Fehler wenn Proxy fehlt:
Aufrufer (net.py) fängt alles und fällt auf "kein Proxy verfügbar" zurück.

Env:
  PROXY_LOGIN / PROXY_PASSWORD   (in ~/.hermes/.env vorhanden)
  DATAIMPULSE_URL                (optional: volle URL überschreibt)

Host: gw.dataimpulse.com:823 (DeepWeb-Tool-Referenz)
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

HOST = "gw.dataimpulse.com"
PORT = "823"

UA = {"User-Agent": "Sucher1000/ (mailto:kontakt@sucher1000.example)"}


def _env(name: str) -> str:
    """Key aus Env lesen (auch ~/.hermes/.env als Fallback)."""
    v = os.environ.get(name, "")
    if not v:
        try:
            p = os.path.expanduser("~/.hermes/.env")
            if os.path.exists(p):
                for line in open(p, encoding="utf-8"):
                    if line.startswith(name + "="):
                        v = line.strip().split("=", 1)[1]
                        break
        except Exception:
            pass
    return (v or "").strip()


def available() -> bool:
    """Proxy konfiguriert? (Login+Passwort vorhanden)"""
    return bool(_env("PROXY_LOGIN") and _env("PROXY_PASSWORD"))


def proxy_url() -> str:
    """Proxy-URL aus Env bauen. Credentials NIE hardcoded."""
    full = _env("DATAIMPULSE_URL")
    if full:
        return full
    login = _env("PROXY_LOGIN")
    pw = _env("PROXY_PASSWORD")
    return f"http://{login}:{pw}@{HOST}:{PORT}"


def fetch(url: str, timeout: int = 8, erwartet: str = "json"):
    """1× Request über Proxy. Rückgabe: JSON ODER None (Proxy scheiterte).

    Erwartet "json" → parst JSON; "text" → gibt Body-Text zurück.
    """
    if not available():
        return None
    try:
        handler = urllib.request.ProxyHandler({
            "http": proxy_url(),
            "https": proxy_url(),
        })
        opener = urllib.request.build_opener(handler)
        req = urllib.request.Request(url, headers=UA)
        with opener.open(req, timeout=timeout) as r:
            body = r.read()
        if erwartet == "json":
            # Validierung: muss JSON sein, sonst gilt Proxy als erfolglos
            probe = body[:2000].decode("utf-8", "ignore").lstrip()
            if not probe.startswith(("{", "[")):
                return None
            return json.loads(body.decode("utf-8", "replace"))
        return body.decode("utf-8", "ignore")
    except Exception:
        return None
