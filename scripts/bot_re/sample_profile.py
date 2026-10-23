"""Trace a reproducible random sample of the bot's txs and summarise normal business (callTracer only)."""
import sys, json, random, pathlib, collections
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib")); sys.path.insert(0, str(ROOT / "scripts/bot_re"))
import rawfetch as r, decode_script as D

BOTS = {"bot2024_0x6980a47b": "0x6980a47bee930a4584b09ee79ebe46484fbdbdd0", "bot2026_0x80bf7db6": "0x80bf7db69556d9521c03461978b8fc731dbbd4e4"}
KNOWN = json.loads((ROOT / "scripts/bot_re/known_addrs.json").read_text()) if (ROOT / "scripts/bot_re/known_addrs.json").exists() else {}

def walk(n, f, depth=0):
    f(n, depth)
    for c in n.get("calls", []): walk(c, f, depth + 1)

def summarise(h, bot, owner="0xfde0d1575ed8e06fbf36256bcdfa1f359281455a"):
    t = r.rpc("debug_traceTransaction", [h, {"tracer": "callTracer"}], key="trace_" + h)
    rc = r.rpc("eth_getTransactionReceipt", [h], key="receipt_" + h)
    blk = r.rpc("eth_getBlockByNumber", [rc["blockNumber"], False], key="blockhdr_" + str(int(rc["blockNumber"], 16)))
    coinbase = blk["miner"].lower()
    s = {"hash": h, "block": int(rc["blockNumber"], 16), "idx": int(rc["transactionIndex"], 16), "status": int(rc["status"], 16), "gasUsed": int(rc["gasUsed"], 16),
         "coinbase": coinbase, "value": int(t.get("value", "0x0"), 16), "eth_to_coinbase": 0, "eth_from_pools": 0, "eth_to_vault": 0, "targets": collections.Counter(), "revert": t.get("error")}
    def f(n, d):
        to = (n.get("to") or "").lower(); fr = n["from"].lower(); v = int(n.get("value", "0x0"), 16)
        if d == 1 and fr == bot: s["targets"][to] += 1
        if to == coinbase and fr == bot and v: s["eth_to_coinbase"] += v
        if to == bot and v and fr != owner and d >= 1: s["eth_from_pools"] += v
        if fr == bot and to == "0xc70f00cd7e461686b04b0e912e309beca8b80ea0": s["eth_to_vault"] += v
    walk(t, f)
    s["targets"] = dict(s["targets"])
    return s

if __name__ == "__main__":
    dec = json.load(open(ROOT / "research/bot-re/corpus_decoded.json"))
    out = {}
    rnd = random.Random(20261021)
    for name, bot in BOTS.items():
        rows = dec[name]
        ok = [x for x in rows if x["err"] == "0"]; bad = [x for x in rows if x["err"] == "1"]
        pick = rnd.sample(ok, 30) + rnd.sample(bad, 6)
        res = []
        for x in pick:
            try:
                res.append({**summarise(x["hash"], bot), "sig": x["sig"], "msg_value": x["value"], "x": x["x"]})
            except Exception as e:  # noqa
                res.append({"hash": x["hash"], "error": str(e)[:100]})
        out[name] = res
        print(name, len(res), "traced")
    (ROOT / "research/bot-re/sample_profile.json").write_text(json.dumps(out, indent=1))
