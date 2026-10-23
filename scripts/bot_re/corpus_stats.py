"""Decode every 0x9846cd9e tx sent to the two Yoink bot contracts (from saved Etherscan txlist pages) and aggregate."""
import sys, json, glob, collections, pathlib, statistics
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/bot_re"))
import decode_script as D

def load(prefix):
    rows = []
    for f in sorted(glob.glob(str(ROOT / f"data/raw/etherscan/txlist_{prefix}*.json"))):
        j = json.load(open(f))
        if isinstance(j.get("result"), list):
            rows += j["result"]
    seen = {}
    for t in rows: seen[t["hash"]] = t
    return sorted(seen.values(), key=lambda t: (int(t["blockNumber"]), int(t["transactionIndex"])))

def run(name, prefix):
    rows = load(prefix)
    main = [t for t in rows if t["methodId"] == "0x9846cd9e"]
    C = collections.Counter(); ops = collections.Counter(); sels = collections.Counter(); val = collections.Counter()
    okc = 0; fail = 0; res = []
    for t in main:
        try:
            p = D.parse(t["input"])
        except Exception as e:  # noqa
            C["parse_exception"] += 1; continue
        okc += p["ok"]
        sig = tuple(o["op"] for o in p["ops"])
        ops.update(set(sig)); 
        for o in p["ops"]:
            if o["op"] == "CALL": sels[(o["sel"])] += 1
        v = int(t["value"]); val[v if v < 10**6 else "big"] += 1
        res.append({"hash": t["hash"], "block": int(t["blockNumber"]), "idx": int(t["transactionIndex"]), "err": t["isError"], "value": v, "ok": p["ok"], "x": p["x"], "f": p["f"], "nStores": p["nStores"], "sig": ",".join(sig)})
    out = {"name": name, "txs_total": len(rows), "txs_main": len(main), "parse_exact": okc, "reverted": sum(r_["err"] == "1" for r_ in res),
           "op_presence": dict(ops.most_common()), "top_call_selectors": dict(sels.most_common(25)), "value_hist": {str(k): v for k, v in val.most_common(12)}, "with_stores": sum(r_["nStores"] > 0 for r_ in res)}
    sigc = collections.Counter(r_["sig"] for r_ in res); out["top_signatures"] = dict(sigc.most_common(15))
    return out, res

if __name__ == "__main__":
    outs = {}; allres = {}
    for name, prefix in [("bot2024_0x6980a47b", "bot2024"), ("bot2026_0x80bf7db6", "bot2026")]:
        o, res = run(name, prefix); outs[name] = o; allres[name] = res
    d = ROOT / "research/bot-re"
    json.dump(outs, open(d / "corpus_stats.json", "w"), indent=1)
    json.dump(allres, open(d / "corpus_decoded.json", "w"))
    print(json.dumps(outs, indent=1)[:6000])
