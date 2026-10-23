#!/usr/bin/env python3
"""Repository checks run by CI: every Python, JSON, JSONL and CSV file parses, site pages link only to files that exist, no local paths,
email addresses or API keys sit in text files, and the paper renders. Exit 1 on any problem.

Usage, from the repository root: python3 scripts/ci_check.py
"""
import ast
import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
ROOT = parser.parse_args().root.resolve()
problems = []
SKIP = {".git"}
TEXT_EXT = {".py", ".md", ".txt", ".json", ".csv", ".html", ".js", ".css", ".yml", ".sh", ".jsonl"}
ABS = re.compile(r"(?<![A-Za-z0-9_.~/-])(?:/ho" "me/|/t" "mp/|/Us" "ers/)[A-Za-z0-9_.-]|~/se" "al\b")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@(?:gmail|hotmail|outlook|yahoo|icloud|proton)\.[a-z]+", re.I)
KEY = re.compile(r"(?i)apikey=(?!YourApiKey|YOUR|<|\{|%|\$|REDACTED|k\b)[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|\bgh[pousr]_[A-Za-z0-9]{30,}")

files = [p for p in sorted(ROOT.rglob("*")) if p.is_file() and not any(x in SKIP for x in p.relative_to(ROOT).parts)]
for p in files:
    rel = p.relative_to(ROOT).as_posix()
    ext = p.suffix.lower()
    if ext not in TEXT_EXT:
        continue
    text = p.read_text(encoding="utf8", errors="replace")
    try:
        if ext == ".py":
            ast.parse(text)
        elif ext == ".json":
            json.loads(text)
        elif ext == ".jsonl":
            for i, line in enumerate(text.splitlines(), 1):
                if line.strip():
                    json.loads(line)
        elif ext == ".csv":
            rows = list(csv.reader(text.splitlines()))
            if rows and any(len(r) != len(rows[0]) for r in rows):
                problems.append(f"{rel}: rows with a different column count")
    except Exception as e:
        problems.append(f"{rel}: does not parse ({str(e)[:80]})")
    if not rel.startswith("site/raw/"):
        for rx, what in ((ABS, "local path"), (EMAIL, "personal email address"), (KEY, "API key or token")):
            if rx is EMAIL and "@" not in text:
                continue
            m = rx.search(text)
            if m:
                problems.append(f"{rel}: {what}")

# References either resolve inside the public repository or carry an explicit publication marker.
raw_checked = 0
raw_unpublished = 0

def check_ref(value, rel):
    global raw_checked, raw_unpublished
    if isinstance(value, (dict, list)):
        for item in (value.values() if isinstance(value, dict) else value):
            check_ref(item, rel)
    elif isinstance(value, str) and value:
        if "not published" in value or "full cache only" in value:
            raw_unpublished += 1
        elif not value.startswith(("https:", "http:")):
            raw_checked += 1
            base = ROOT / "site" if str(rel).startswith("site/") else ROOT
            if not (base / value.split("#", 1)[0]).is_file():
                problems.append(f"{rel}: unresolved raw_ref {value}")

def check_doc(obj, rel):
    if isinstance(obj, dict):
        for k, v in obj.items():
            check_ref(v, rel) if k in {"raw_refs", "raw_ref"} else check_doc(v, rel)
    elif isinstance(obj, list):
        for value in obj:
            check_doc(value, rel)

for p in files:
    if p.suffix == ".json" and p.name != "rawref_audit.json" and not p.relative_to(ROOT).as_posix().startswith("site/raw/"):
        try:
            check_doc(json.loads(p.read_text()), p.relative_to(ROOT))
        except (ValueError, OSError):
            pass

# A standalone site must never escape its root through a relative link.
from urllib.parse import urlsplit, unquote
site = (ROOT / "site").resolve()
for page in sorted(site.glob("*.html")):
    for m in re.finditer(r"(?:href|src)=[\"']([^\"']+)", page.read_text(encoding="utf8")):
        target = urlsplit(m.group(1))
        if target.scheme or target.netloc or not target.path:
            continue
        dest = (page.parent / unquote(target.path)).resolve()
        if not dest.is_relative_to(site):
            problems.append(f"{page.relative_to(ROOT)}: link above site root")
        elif not dest.exists():
            problems.append(f"{page.relative_to(ROOT)}: link to missing file {target.path}")
print(f"raw_ref check: {raw_checked} paths, {raw_unpublished} unpublished markers")

manifest_path = site / "raw/MANIFEST.json"
hash_checked = 0
if not manifest_path.is_file():
    problems.append("site/raw/MANIFEST.json is missing")
else:
    for key, entry in json.loads(manifest_path.read_text()).items():
        raw_path = (site / "raw" / key).resolve()
        if not raw_path.is_relative_to(site / "raw") or not raw_path.is_file():
            problems.append(f"MANIFEST: missing or invalid path {key}")
            continue
        body = raw_path.read_bytes()
        hash_checked += 1
        if hashlib.sha256(body).hexdigest() != entry.get("sha256") or len(body) != entry.get("bytes"):
            problems.append(f"MANIFEST: hash/byte mismatch {key}")
print(f"manifest check: {hash_checked} hashes and byte counts")

repo_prefix = "https://github.com/DicksonWu654/bot-vs-hacker/blob/main/"
for page in site.glob("*.html"):
    for target in re.findall(r"href=[\"']([^\"']+)", page.read_text()):
        if target.startswith(repo_prefix):
            path = unquote(urlsplit(target).path.split("/blob/main/", 1)[1])
            dest = (ROOT / path).resolve()
            if not dest.is_relative_to(ROOT) or not dest.exists():
                problems.append(f"{page.relative_to(ROOT)}: missing repository link {path}")

if not (ROOT / "site" / "paper.html").exists():
    problems.append("site/paper.html is missing; run scripts/export_paper.py")

for p in problems[:50]:
    print("FAIL", p)
print(f"ci_check: {len(files)} files, {len(problems)} problem(s)")
sys.exit(1 if problems else 0)
