"""Ronin 2024-08-06: word-level calldata diff between each victim withdrawal (public mempool tx) and the three copies that
landed first (calls into the bridge, taken from callTracer). Output: research/defiplaza-ronin/ronin_copies_diff.json"""
import json, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))
import rawfetch as r
BRIDGE = "0x64192819ac13ef72bf6b5ae239ac672b43a9af08"
PAIRS = {
 "ETH-leg searcher 0x1a56abf4->0x4ab12e7c vs user 0xc78fb8cd (id 166631)": ("0x2619570088683e6cc3a38d93c3d98899e5783864e15525d5f5810c11189ba6cb", "0xc78fb8cd5f7813a3d8abebdc5351aafd5011e8e13c5f6740837eeef9308d1faf"),
 "racer 0x00001b0b->0x02f3d391 vs user 0x56439cf9 (id 166632)": ("0x77bb83dd9b25a0af12c0092993ddf1a2f54b77fbcd1dbf1bf33a965ec707268b", "0x56439cf9427a9188d12b35ef4c8b80fc94a8a1dd205789999c000d8035f27afe"),
 "Yoink 0xfde0d157->0x6980a47b vs user 0xb7c3f85a (id 166633)": ("0xbce5b8548db486c561948e8a177c8ccaa72810f972cee3909ea50af015a60ad8", "0xb7c3f85abd0b9ede7b64868eeb6778ea4731adb1d49f8640b7e7234e470e96c1"),
}
def bridge_calls(f, out):
    if (f.get("to") or "").lower() == BRIDGE and f.get("input", "").startswith("0x4d0d6673"):
        out.append(f)
    for c in f.get("calls", []): bridge_calls(c, out)
def words(inp): s = inp[10:]; return [s[i:i + 64] for i in range(0, len(s), 64)]
res = {}
for name, (copy, victim) in PAIRS.items():
    tr = r.rpc("debug_traceTransaction", [copy, {"tracer": "callTracer"}], key=f"trace_{copy}")
    out = []; bridge_calls(tr, out)
    vin = r.rpc("eth_getTransactionByHash", [victim], key=f"tx_{victim}")["input"]
    cin = out[0]["input"]
    wv, wc = words(vin), words(cin)
    d = [{"word": i, "victim": wv[i], "copy": wc[i]} for i in range(min(len(wv), len(wc))) if wv[i] != wc[i]]
    res[name] = {"copy_tx": copy, "victim_tx": victim, "bridge_calls_in_copy": len(out), "victim_words": len(wv), "copy_words": len(wc),
                 "same_length": len(wv) == len(wc), "differing_words": d, "n_identical_words": sum(1 for i in range(min(len(wv), len(wc))) if wv[i] == wc[i]),
                 "note": "word 0..: offset(receipt), offset(sigs), receipt{id,kind,mainchain{addr,token,chainId},ronin{addr,token,chainId},info{erc,id,quantity}}, then sigs array"}
json.dump(res, open(ROOT / "research/defiplaza-ronin/ronin_copies_diff.json", "w"), indent=1)
for k, v in res.items():
    print(k, "len", v["victim_words"], v["copy_words"], "identical", v["n_identical_words"])
    for x in v["differing_words"]: print("   w", x["word"], x["victim"][-24:], "->", x["copy"][-24:])
