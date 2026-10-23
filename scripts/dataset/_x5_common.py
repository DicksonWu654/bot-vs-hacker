# Shared extraction helpers for the incident dataset incident dataset.
"""Shared helpers for extract_{makina,bifi,uncx,securedfinance,blueberry} scripts (tx-level facts only)."""
import json, pathlib, sys, datetime
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import bvh  # noqa: E402

WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"


def jl(rel):
    return json.load(open(ROOT / rel))


def ex(rel):
    return (ROOT / rel).exists()


def eth(wei):
    return int(wei) / 1e18


def hx(x):
    return int(x, 16) if isinstance(x, str) else int(x)


def res(d):
    return d["result"] if isinstance(d, dict) and "result" in d else d


def rpc_tx(h):
    p = f"data/raw/rpc/tx_{h}.json"
    return p, res(jl(p))


def rpc_rcpt(h):
    p = f"data/raw/rpc/rcpt_{h}.json"
    return p, res(jl(p))


def walk(node, depth=1):
    """yield (depth, call) over a callTracer tree."""
    yield depth, node
    for c in node.get("calls") or []:
        yield from walk(c, depth + 1)


def race_tx(race, h):
    for t in race["txs"]:
        if t["hash"].lower() == h.lower():
            return t
    raise KeyError(h)


def iso(ts):
    return datetime.datetime.fromtimestamp(int(ts), datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_ms(ms):
    return datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(ms) % 1000:03d}Z"


def weth_withdraws(trace_root, caller=None):
    out = []
    for d, c in walk(trace_root):
        if (c.get("to") or "").lower() == WETH and (c.get("input") or "").startswith("0x2e1a7d4d"):
            if caller is None or c["from"].lower() == caller.lower():
                out.append(int(c["input"][10:74], 16))
    return out


def write_rows(slug, rows):
    p = ROOT / "data" / "extract" / f"{slug}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    json.dump(rows, open(p, "w"), indent=1)
    print("wrote", p, len(rows), "row(s)")


def finish(slug, rows):
    """check missing raw refs"""
    for r in rows:
        a = r.get("auction") or {}
        miss = a.get("_missing_raw")
        if miss:
            r.setdefault("rawref_gaps", []).append({"field": "auction.raw_refs", "why": f"missing files: {miss}"})
    write_rows(slug, rows)


def builder_to(race, targets):
    """sum (wei) of simple-transfer txs in the block sent FROM the block fee recipient TO any of targets (refund check); returns (wei, [hashes])"""
    fr = race["block"]["fee_recipient"].lower()
    tg = {t.lower() for t in targets}
    tot, hs = 0, []
    for t in race["txs"]:
        if t["from"].lower() == fr and (t.get("to") or "").lower() in tg:
            tot += int(t["value_wei"]); hs.append(t["hash"])
    return tot, hs
