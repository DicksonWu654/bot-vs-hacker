#!/usr/bin/env python3
"""Render paper/paper.md to site/paper.html (shipped as scripts/export_paper.py).

The page is self-contained (inline CSS, no external requests) and links back to the interactive site, so a static host
that serves site/ serves the paper at /paper.html. The renderer is python-markdown only (pip install markdown), so the
same input gives the same HTML on every machine with the same markdown version.

Usage, from the repository root: python3 scripts/export_paper.py
"""
import sys
import re
from pathlib import Path

try:
    import markdown
except ImportError:
    sys.exit("export_paper.py needs python-markdown: pip install markdown")

ROOT = Path(__file__).resolve().parent.parent
paper = ROOT / "paper/paper.md"
if not paper.exists():
    paper = ROOT / "article/paper.md"
text = paper.read_text(encoding="utf8")
sys.path.insert(0, str(ROOT / "scripts/export" if (ROOT / "scripts/export").is_dir() else ROOT / "scripts"))
from paper_paths import public_paper
text = public_paper(text)
CSS = (".paper{max-width:76rem;padding-top:48px;padding-bottom:64px}"
       ".paper h1{font-size:clamp(32px,5vw,56px);margin-bottom:28px}"
       ".paper h2{margin-top:1.8em}.paper h3{margin-top:1.5em}"
       ".paper p,.paper li{max-width:76ch;overflow-wrap:anywhere}"
       ".paper table{border-collapse:collapse;font:14px/1.45 var(--mono);margin:1em 0;display:block;overflow-x:auto}"
       ".paper th,.paper td{border:1px solid var(--line);padding:.4em .6em;vertical-align:top}"
       ".paper th{background:var(--bg3)}.paper pre{overflow-x:auto;max-width:100%}"
       ".paper code{overflow-wrap:anywhere}")
body = markdown.markdown(text, extensions=["tables", "toc"])
body = body.replace('href="../site/', 'href="')
body = re.sub(r'(href=["\'])\.\./(data|incidents|research)/([^"\']+)',
              lambda m: m.group(1) + "https://github.com/DicksonWu654/bot-vs-hacker/blob/main/" + m.group(2) + "/" + m.group(3), body)
page = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>The Bot Beat the Hacker: paper</title>'
        '<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 32 32\'%3E%3Crect width=\'32\' height=\'32\' rx=\'6\' fill=\'%23070d0b\'/%3E%3Cpath d=\'M16 6l8 10-8 10-8-10z\' fill=\'%233ddc97\'/%3E%3C/svg%3E">'
        '<link rel="stylesheet" href="assets/style.css">'
        f'<style>{CSS}</style></head><body><main id="main" class="wrap paper">'
        f'{body}</main><script src="assets/common.js"></script>'
        '<script>BVH.chrome("paper.html");</script></body></html>\n')
(ROOT / "site" / "paper.html").write_text(page, encoding="utf8")
print("site/paper.html written (markdown %s)" % markdown.__version__)
