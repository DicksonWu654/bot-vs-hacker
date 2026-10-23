"""Validate the curated transaction-level extract used by build_incidents.py.

The reviewed data/extract record is the source for this incident. It records public
transactions, block positions, funds and statements; bot internals are excluded.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))
from publication import scrub_public

if __name__ == "__main__":
    path = ROOT / "data/extract/blueberry-2024.json"
    rows = json.loads(path.read_text())
    assert rows and all(row["slug"] == "blueberry-2024" for row in rows)
    clean = scrub_public(rows)
    path.write_text(json.dumps(clean, indent=1, ensure_ascii=False))
    print("validated curated extract:", path.relative_to(ROOT), len(rows), "row(s)")
