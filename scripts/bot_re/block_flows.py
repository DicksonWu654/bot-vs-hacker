"""Per-block ETH flow accounting for blocks in which the searcher is also the builder: sum of coinbase payments by the bot txs
vs. refund tx(s) from the builder vs. payment to proposer."""
import sys, json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))
import rawfetch as r

def walk(n, f):
    f(n)
    for c in n.get("calls", []): walk(c, f)

def block_flows(num, owner="0xfde0d1575ed8e06fbf36256bcdfa1f359281455a"):
    b = r.rpc("eth_getBlockByNumber", [hex(num), True], key=f"block_{num}")
    cb = b["miner"].lower(); rows = []; tot_cb = 0
    for t in b["transactions"]:
        fr = t["from"].lower(); to = (t["to"] or "").lower(); row = {"idx": int(t["transactionIndex"], 16), "hash": t["hash"], "from": fr, "to": to, "value_eth": int(t["value"], 16) / 1e18}
        if fr == owner:
            tr = r.rpc("debug_traceTransaction", [t["hash"], {"tracer": "callTracer"}], key="trace_" + t["hash"])
            s = [0, 0]
            def f(n):
                if (n.get("to") or "").lower() == cb and int(n.get("value", "0x0"), 16) and not n.get("error"):
                    s[0] += int(n["value"], 16)
            walk(tr, f); row["eth_to_coinbase"] = s[0] / 1e18; tot_cb += s[0]
        rows.append(row)
    return {"block": num, "coinbase": cb, "timestamp": int(b["timestamp"], 16), "n_tx": len(rows), "sum_coinbase_payments_from_bot_txs_eth": tot_cb / 1e18, "txs": rows}

if __name__ == "__main__":
    out = {n: block_flows(n) for n in (20468848, 25980525)}
    (ROOT / "research/bot-re/block_flows.json").write_text(json.dumps(out, indent=1))
    for n, o in out.items():
        print(n, o["coinbase"], "sum bot->coinbase", o["sum_coinbase_payments_from_bot_txs_eth"])
        for t in o["txs"]:
            if t["from"] == o["coinbase"] or t.get("eth_to_coinbase"):
                print("  ", t["idx"], t["from"][:10], "->", t["to"][:10], t["value_eth"], t.get("eth_to_coinbase"))
