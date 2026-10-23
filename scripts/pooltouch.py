#!/usr/bin/env python3
"""List transactions SENT BY an address in a block range whose callTracer trace touches any watched address.

    pooltouch.py --sender 0xc0ff... --from-block 17806000 --to-block 17809300 --watch POOL1 POOL2 [--out file.json]

Uses Etherscan txlist (via rawfetch.etherscan) for the sender's txs and debug_traceTransaction for each; everything is
saved under data/raw. Intended for describing PUBLIC actions of an address (which tx, which block, which pools it
touched) - it records addresses touched, nothing about contract internals.
"""
import argparse, json, pathlib, sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "lib"))
import rawfetch as rf


def touched(frame, acc):
    for k in ("from", "to"):
        if frame.get(k):
            acc.add(frame[k].lower())
    for c in frame.get("calls", []) or []:
        touched(c, acc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sender", required=True)
    ap.add_argument("--from-block", type=int, required=True)
    ap.add_argument("--to-block", type=int, required=True)
    ap.add_argument("--watch", nargs="+", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    watch = {w.lower() for w in a.watch}
    s = a.sender.lower()
    res = rf.etherscan({"module": "account", "action": "txlist", "address": s, "startblock": a.from_block, "endblock": a.to_block,
                        "sort": "asc"}, key=f"txlist_{s[:10]}_{a.from_block}_{a.to_block}")
    txs = [t for t in res["result"] if t["from"].lower() == s]

    def one(t):
        tr = rf.rpc("debug_traceTransaction", [t["hash"], {"tracer": "callTracer"}], key=f"trace_{t['hash']}")
        acc = set()
        touched(tr, acc)
        return {"block": int(t["blockNumber"]), "index": int(t["transactionIndex"]), "hash": t["hash"], "to": t["to"],
                "status": "ok" if t["isError"] == "0" else "failed", "gas_price_gwei": int(t["gasPrice"]) / 1e9,
                "touches": sorted(watch & acc), "raw_trace": rf.raw_path("rpc", f"trace_{t['hash']}")}

    with ThreadPoolExecutor(max_workers=6) as ex:
        rows = list(ex.map(one, txs))
    hits = [r for r in rows if r["touches"]]
    out = {"sender": s, "range": [a.from_block, a.to_block], "watch": sorted(watch), "n_txs": len(rows), "hits": hits,
           "raw_txlist": rf.raw_path("etherscan", f"txlist_{s[:10]}_{a.from_block}_{a.to_block}")}
    print(json.dumps(out, indent=1))
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
