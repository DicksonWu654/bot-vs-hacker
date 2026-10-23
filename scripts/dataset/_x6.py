# Extraction helpers for the additional incident rows consolidated by build_incidents.py.
"""Small shared helpers for the six incident dataset extract scripts (defiplaza, dodo, earningfarm, euler-copybot, shoco, transitswap)."""
import json, pathlib, sys, datetime
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import bvh  # noqa: E402


def load(p):
    return json.load(open(ROOT / p))


def eth(wei):
    return int(wei) / 1e18


def txrow(race, h):
    h = h.lower()
    for t in race["txs"]:
        if t["hash"].lower() == h:
            return t
    raise KeyError(h)


def iso(ts):
    return datetime.datetime.fromtimestamp(int(ts), datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def check_paths(refs):
    miss = []
    for f, v in refs.items():
        for x in (v if isinstance(v, list) else [v]):
            if x and not (ROOT / x).exists():
                miss.append((f, x))
    return miss


def write(slug, rows):
    for r in rows:
        miss = check_paths(r["raw_refs"])
        if miss:
            print("MISSING RAW FILES", miss)
        am = r["auction"].pop("_missing_raw", None)
        if am:
            print("auction missing raw", am)
    out = ROOT / "data" / "extract" / f"{slug}.json"
    json.dump(rows, open(out, "w"), indent=1)
    print("wrote", out, len(rows), "row(s)")


def res(d):
    """etherscan-style file -> list of rows"""
    return d["result"] if isinstance(d, dict) and "result" in d else d
