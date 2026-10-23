"""Word-by-word comparison: attacker's public-mempool submitWithdrawal calldata vs. the calldata Yoink's bot forwarded to the bridge (Ronin, 2024-08-06)."""
import sys, json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib")); sys.path.insert(0, str(ROOT / "scripts/bot_re"))
import rawfetch as r, decode_script as D
Y = "0xbce5b8548db486c561948e8a177c8ccaa72810f972cee3909ea50af015a60ad8"; A = "0xb7c3f85abd0b9ede7b64868eeb6778ea4731adb1d49f8640b7e7234e470e96c1"
ytx = r.rpc("eth_getTransactionByHash", [Y], key="tx_" + Y); atx = r.rpc("eth_getTransactionByHash", [A], key="tx_" + A)
p = D.parse(ytx["input"]); y_in = p["ops"][0]["data"]; a_in = atx["input"]
assert p["ops"][0]["to"] == atx["to"]
names = ["receipt.id", "receipt.kind(1=withdrawal)", "mainchain.addr (recipient)", "mainchain.tokenAddr", "mainchain.chainId", "ronin.addr", "ronin.tokenAddr", "ronin.chainId", "info.erc", "info.id", "info.quantity"]
yw = [y_in[10 + 64 * i:10 + 64 * (i + 1)] for i in range((len(y_in) - 10) // 64)]; aw = [a_in[10 + 64 * i:10 + 64 * (i + 1)] for i in range((len(a_in) - 10) // 64)]
rows = []
for i, (a, y) in enumerate(zip(aw, yw)):
    rows.append({"word": i, "field": names[i] if i < len(names) else ("signature-array" if i >= 11 else ""), "attacker": "0x" + a.lstrip("0") if a.strip("0") else "0", "yoink": "0x" + y.lstrip("0") if y.strip("0") else "0", "same": a == y})
out = {"yoink_tx": Y, "attacker_tx": A, "calldata_bytes": [len(y_in) // 2 - 1, len(a_in) // 2 - 1], "words_total": len(yw), "words_different": sum(not x["same"] for x in rows), "diff_words": [x for x in rows if not x["same"]],
       "first_11_words": rows[:11], "signature_words_identical": all(x["same"] for x in rows[11:]),
       "yoink_quantity_usdc": int(yw[10], 16) / 1e6, "attacker_quantity_usdc": int(aw[10], 16) / 1e6}
(ROOT / "research/bot-re/ronin_calldata_diff.json").write_text(json.dumps(out, indent=1))
print(json.dumps({k: v for k, v in out.items() if k != "first_11_words"}, indent=1))
