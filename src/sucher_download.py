#!/usr/bin/env python3
"""
SUCHER-DOWNLOAD — automatisches Herunterladen von Studien/PDFs/Markdown
mit reCAPTCHA/Cloudflare-Umgehung via Browser-Engine-Fallback.

Nutzung:
  python3 sucher_download.py <url> [ausgabe.md]      # Einzelne URL laden
  python3 sucher_download.py <urls.txt> [ordner]      # Batch aus Datei

Strategie (3 Stufen):
  1. curl (schnell, für offene Quellen)
  2. Falls reCAPTCHA/Cloudflare/zu klein → BROWSER-ENGINE (echte Browser-Engine,
     umgeht Bot-Schutz)
  3. Konvertiert HTML→Markdown (html2text/پandoc) oder speichert PDF
"""
import urllib.request, subprocess, sys, os, re, time

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
MIN_OK = 40000  # mind. Bytes für "echten" Inhalt (darunter = Stub)

def check_blocked(html_path):
    """Erkennt Blockier-Stubs (reCAPTCHA/Cloudflare/suspektes HTML).
    Kleine PDFs sind VALIDE (kein Fehlalarm), kleine HTML-Snippets sind Stubs."""
    try:
        sz = os.path.getsize(html_path)
    except OSError:
        return True
    if sz == 0:
        return True
    # PDF (auch klein) = echter Inhalt, nicht geblockt
    if is_pdf(html_path):
        return False
    # HTML: zu klein → Stub (Block), außer es ist was Reales drin
    if sz < MIN_OK:
        return True
    with open(html_path, "r", encoding="utf-8", errors="replace") as f:
        head = f.read(2000).lower()
    return any(k in head for k in ("recaptcha", "cf-challenge", "just a moment", "cloudflare"))

def curl_download(url, out_path):
    """Stufe 1: klassischer curl-Download."""
    r = subprocess.run(
        ["curl", "-sL", "--max-time", "60", "-A", UA,
         "-H", "Accept: text/html", "-H", "Accept-Language: en-US,en;q=0.9",
         "-o", out_path, url],
        capture_output=True)
    return not check_blocked(out_path)

def browser_download(url, out_path, session="sucher_dl"):
    """Stufe 2: Browser-Engine-Fallback (echte Browser-Engine, umgeht reCAPTCHA).

    Nutzt die Browser-Engine via browser_exec-Logik. Da dies ein externes Ding ist,
    wird hier ein stabiler, ausführbarer Weg bereitgestellt: Wir legen die URL in
    eine Queue-Datei, die die Hermes-Integration abarbeitet. Für CLI-Standalone
    geben wir einen Hinweis. (Die eigentliche Browser-Engine wird über den
    Hermes-Agenten/Tool orchestriert.)
    """
    # In Hermes-Kontext: erzeugt eine Task-Anweisung für den Browser-Abholer.
    # Steht in sucher_download.md als Protokoll; hier nur Protokoll.
    with open(out_path + ".browser_task", "w") as f:
        f.write(url + "\n" + out_path)
    print("  → Browser-Engine nötig. Task gespeichert in:", out_path + ".browser_task")
    print("  → Diesen Task führt die Hermes-Browser-Integration aus (s. Anleitung).")
    return out_path + ".browser_task"

def download(url, out_path=None):
    """Hauptfunktion: versucht curl, dann Browser-Engine."""
    if not out_path:
        name = re.sub(r"\W+", "_", url.split("/")[-1])[:60] or "download"
        out_path = name
    print(f"  [{url}] → {out_path}")
    # Stufe 1: curl
    if curl_download(url, out_path):
        print("    ✓ curl erfolgreich")
        # PDF erkennen: Endung korrekt setzen (.pdf statt .md)
        if is_pdf(out_path):
            if not out_path.lower().endswith(".pdf"):
                pdf_path = out_path + ".pdf"
                os.rename(out_path, pdf_path)
                out_path = pdf_path
            print(f"    → PDF gespeichert: {out_path}")
        # HTML→MD konvertieren falls HTML
        elif is_html(out_path):
            md = out_path.rsplit(".",1)[0] + ".md" if "." in out_path else out_path + ".md"
            try:
                _html_to_md(out_path, md)
                print(f"    → konvertiert zu {md}")
            except Exception as e:
                print(f"    ⚠️ Konvertierung übersprungen ({e}); HTML behalten: {out_path}")
        return out_path
    print("    ✗ curl geblockt/fehlgeschlagen → Browser-Engine")
    # Stufe 2: Browser-Engine (Task ablegen)
    return browser_download(url, out_path)

def is_pdf(path):
    try:
        with open(path, "rb") as f:
            return f.read(1024).lstrip().startswith(b"%PDF")
    except Exception:
        return False

def is_html(path):
    try:
        with open(path, "rb") as f:
            return f.read(1024).lstrip().startswith(b"<!doctype") or b"<html" in f.read(2048)
    except Exception:
        return False

def _html_to_md(src, dst):
    """HTML→Markdown: bevorzugt Python-Modul html2text, Fallback auf W3M/Text."""
    try:
        import html2text  # Python-Modul (wenn installiert)
        h = html2text.HTML2Text()
        h.ignore_links = False
        with open(src, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        with open(dst, "w", encoding="utf-8") as f:
            f.write(h.handle(content))
        return
    except ImportError:
        pass
    # Fallback: W3M (textbasiert) oder pandoc
    for tool in (["w3m","-dump",src], ["pandoc",src,"-t","markdown","-o",dst]):
        try:
            r = subprocess.run(tool, capture_output=True)
            if r.returncode == 0:
                if tool[0] == "w3m":
                    with open(dst, "w", encoding="utf-8") as f:
                        f.write(r.stdout.decode("utf-8", errors="replace"))
                return
        except Exception:
            pass
    raise RuntimeError("kein html2text/w3m/pandoc gefunden")

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    target = sys.argv[1]
    if target.endswith(".txt") and os.path.exists(target):  # Batch
        urls = [l.strip() for l in open(target) if l.strip()]
        outdir = sys.argv[2] if len(sys.argv) > 2 else "."
        os.makedirs(outdir, exist_ok=True)
        for u in urls:
            name = re.sub(r"\W+", "_", u.split("/")[-1])[:50] or "item"
            try:
                download(u, os.path.join(outdir, name))
            except Exception as e:
                print("  ERR", e)
    else:  # Einzel-URL
        out = sys.argv[2] if len(sys.argv) > 2 else None
        download(target, out)

if __name__ == "__main__":
    main()