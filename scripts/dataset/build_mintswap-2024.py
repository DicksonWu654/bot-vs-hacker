"""Build incidents/mintswap-2024/{pool_history,yoink_mintswap_txs,other_bot_0x4ab,pending_user_call_diff,incident,timeline}.json
from files already saved under data/raw/ (rpc traces/blocks, etherscan lists, mempool-dumpster) and the race_*.json files.
Run from project root: .venv/bin/python scripts/dataset/build_mintswap-2024.py
Everything numeric is recomputed from saved raw responses; missing RPC objects are fetched through rawfetch (cached)."""
import json, pathlib, sys, datetime as dt
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
sys.path.insert(0, str(ROOT / "scripts"))
import rawfetch as rf, bvh

SLUG = "mintswap-2024"
D = ROOT / "incidents" / SLUG
E18 = 10 ** 18
ROUTER = "0xd8d5b0775a992d1ba9f1b9f43c976a2c1f50bfde"       # MintSwapPool proxy (vMINT/ETH), impl 0x13a3efac...
IMPL = "0x13a3efac2e1feb4dddeced77a4910fcbf914ce76"
FACTORY = "0x9c7ddb3672b90881f95553f7ea4d0034846e8411"
VMINT = "0xd7b2c1a7f3c67fb0ea57a7ef29bc1f18d7be3195"
PAIR = "0x4ed8973e1d76c41f6dd82673f43b4ad85ed04123"          # Uniswap V2 vMINT/USDT
YOINK_EOA = "0xfde0d1575ed8e06fbf36256bcdfa1f359281455a"
YOINK_C = "0x6980a47bee930a4584b09ee79ebe46484fbdbdd0"
LP = "0x5b033ca6ff0465b8857dbf03c9c9d17026eeed00"
TEAM = "0x8b1dcb843c5d9465726baec345200b541b777562"
ARB_EOA = "0x1a56abf4fe95e21c1704cbd5ffc79ea1effa3cc1"
ARB_C = "0x4ab12e7ce31857ee022f273e8580f73335a73c0b"
USER_SELL = "0x2bca4d6150d1c8e852229215dd92a75e2d39b7b41281872e77458c0d266e2ba0"
RETURN_TX = "0x1d3c141c4606fa1083fae092d2a2b92a3edca998d940f4ac2e5cbeb6e292a35c"
LP_ADD = "0xcef01834b1985db09e576242238798fcc909981812086de05a7be4c3b1785408"

# (hash, block, role) Yoink txs that call the MintSwap pool
Y_ROUTER = [
    ("0xd2337efb820b7bce143bd940f9738b288540a9a88f791177f156bbe2b5b86d20", 19563164, "sell vMINT into pool (sell-path bug), flash-loan funded"),
    ("0x29edec50fbaf213f26b69b97daf8182067f2f292b4123225b0713ed24af0b620", 19563165, "buy vMINT from the emptied pool, sell on Uniswap V2"),
    ("0x45685ad9bd5da6d6a51b42c4b1010cd7a79a9be72429cdffc57a609b577d9bd5", 19563183, "sell vMINT into pool again (ETH added by other arbs)"),
    ("0x18e3b5e39f3af4040422316f5eb9d3ebec49f19bf3a0516184e737d3dba496df", 19563184, "buy vMINT back from pool"),
    ("0xa6aeb74dcefe4da4660309cdd7d796fe379e2b839e93fb819770dabe6d7c8fb3", 19563189, "sell vMINT into pool again"),
    ("0x41a7e2b2900c1e0561454f67443df509b06b6be6ba6774c32a6e8cb03b08ab06", 19563190, "buy vMINT back from pool"),
]
# Yoink txs in the same blocks that touch the vMINT/USDT V2 pair but not the MintSwap pool
Y_PAIR = [
    ("0xd257eed0a1467c9297ed9f2cd9df7b7f382ae04d4d66cb643bb48cebef6117f5", 19563164),
    ("0x2b9b60ad71ae9a88ba26822762a68fd6167d8da11a39bfc701f07270226d64ce", 19563165),
    ("0xa5392605b2c8f4a6453ca4f76b47328536e4ec46660aacdd6f8cd71d10682e67", 19563183),
    ("0x99fb754087149366cc0eb34ff61db47839725efc08c5073f4c491c114a36d67d", 19563184),
]
MSG = {
    "team_notice": "0xfe5020429a451908be819ee7b3dc833115cc32e902e759ea6a8bdc4d8110d5c0",
    "yoink_verify_ask": "0xa6ee1306de2451c3fc3665dd95ff0c5791bb901984e667e51c19438af70c8965",
    "team_bug_explained": "0x5b90649d3a00f17ecd49ad3ac572fca7a41388c96f0fff9452762fc2e90d24ac",
    "yoink_profit_offer": "0x89af126f81e8cfcc7026da0ff5c203338444fdeff8bb54284ea38af3b18a1055",
    "team_accepts_lp": "0xfa9ca31cf92d130eab2c864a08308849e41b4f7941a2d41c3d1346f2046e9ceb",
    "team_waiting": "0x704b79655829ba35f0f8478b2176cc5c9a579bfbfe288b1077f75e8662f585a2",
    "yoink_already_sent": "0x07473e4c9cfddd270f2d2e153072afbe73b37771fef08a59e8d1f1cfae1bba9a",
}

J = lambda p: json.load(open(ROOT / p))
res = lambda d: d.get("result", d)
iso = lambda ts: dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
isoms = lambda ms: dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
rpc = rf.rpc


def tx_(h):
    return rpc("eth_getTransactionByHash", [h], key=f"tx_{h}")


def rc_(h):
    return rpc("eth_getTransactionReceipt", [h], key=f"receipt_{h}")


def tr_(h):
    return rpc("debug_traceTransaction", [h, {"tracer": "callTracer"}], key=f"trace_{h}")


def hdr(n):
    return rpc("eth_getBlockByNumber", [hex(n), False], key=f"blockhdr_{n}")


def full(n):
    return rpc("eth_getBlockByNumber", [hex(n), True], key=f"block_{n}")


def walk(c, fn, parent=None):
    fn(c, parent)
    for x in c.get("calls", []):
        walk(x, fn, c)


def flows(tr, miner):
    """CALL-type value flows only (DELEGATECALL echoes the parent's value and must not be counted)."""
    f = {"router_in": 0, "router_out": 0, "coinbase": 0, "sell_calls": 0, "buy_calls": 0}

    def fn(c, p):
        if c.get("error") or c["type"] != "CALL":
            return
        v = int(c.get("value") or "0x0", 16)
        to, fr = c.get("to", "").lower(), c.get("from", "").lower()
        if to == ROUTER and v:
            f["router_in"] += v
        if fr == ROUTER and v:
            f["router_out"] += v
        if to == miner and v:
            f["coinbase"] += v
        if to == ROUTER and c.get("input", "").startswith("0x5c7e072b"):
            f["sell_calls"] += 1
        if to == ROUTER and c.get("input", "").startswith("0xffee770f"):
            f["buy_calls"] += 1
    walk(tr, fn)
    return f


# ---------------------------------------------------------------------------------------------------- Yoink tx table
blocks = sorted({b for _, b, *_ in Y_ROUTER} | {b for _, b in Y_PAIR})
BLK = {n: full(n) for n in blocks}
rows = []
for kind, lst in (("router", Y_ROUTER), ("pair-only", Y_PAIR)):
    for item in lst:
        h, n = item[0], item[1]
        role = item[2] if kind == "router" else "same-block Yoink tx touching the vMINT/USDT V2 pair but not the MintSwap pool"
        b = BLK[n]
        miner = b["miner"].lower()
        t = next(x for x in b["transactions"] if x["hash"] == h)
        tr = tr_(h)
        s = json.dumps(tr).lower()
        f = flows(tr, miner)
        v = int(t["value"], 16)
        cb = f["coinbase"] / E18
        est_gross = cb / (v / 1000) if v < 1000 else None
        rcpt = rc_(h)
        gas_used = int(rcpt["gasUsed"], 16); egp = int(rcpt["effectiveGasPrice"], 16); base = int(b["baseFeePerGas"], 16)
        assert rcpt["status"] == "0x1"
        rows.append({
            "hash": h, "block": n, "index": int(t["transactionIndex"], 16), "kind": kind, "role": role,
            "msg_value_permille": v, "from": t["from"], "to": t["to"],
            "priority_fee_gwei": int(t.get("maxPriorityFeePerGas") or "0x0", 16) / 1e9 if t.get("maxPriorityFeePerGas") else None,
            "gas_price_gwei": int(t["gasPrice"], 16) / 1e9,
            "touches_mintswap_pool": ROUTER[2:] in s, "touches_vmint_pair": PAIR[2:] in s,
            "pool_eth_out": round(f["router_out"] / E18, 12), "pool_eth_in": round(f["router_in"] / E18, 12),
            "pool_sell_calls": f["sell_calls"], "pool_buy_calls": f["buy_calls"],
            "coinbase_paid_eth": round(cb, 12), "gas_used": gas_used, "gas_cost_eth": gas_used * egp / E18, "priority_fee_paid_eth": gas_used * (egp - base) / E18,
            "est_gross_profit_eth_w4_rule": round(est_gross, 6) if est_gross else None,
            "raw": {"trace": f"data/raw/rpc/trace_{h}.json", "block": f"data/raw/rpc/block_{n}.json", "receipt": f"data/raw/rpc/receipt_{h}.json"},
        })
per_block = []
for n in blocks:
    b = BLK[n]
    miner = b["miner"].lower()
    bt = [x for x in b["transactions"] if x["from"].lower() == miner]
    refund = next(x for x in bt if x["to"].lower() == YOINK_C)
    prop = bt[-1]
    assert prop["to"].lower() != YOINK_C
    per_block.append({
        "block": n, "timestamp_utc": iso(int(b["timestamp"], 16)), "builder_fee_recipient": miner, "extra_data": bytes.fromhex(b["extraData"][2:]).decode("utf8", "replace"),
        "yoink_coinbase_paid_eth": round(sum(r["coinbase_paid_eth"] for r in rows if r["block"] == n), 12),
        "builder_refund_to_yoink_contract_eth": int(refund["value"], 16) / E18, "builder_refund_tx": refund["hash"], "refund_index": int(refund["transactionIndex"], 16),
        "proposer_payment_eth": int(prop["value"], 16) / E18, "proposer_payment_tx": prop["hash"], "proposer_payment_to": prop["to"], "proposer_payment_index": int(prop["transactionIndex"], 16),
        "raw": f"data/raw/rpc/block_{n}.json"})
tot = lambda k, sel=lambda r: True: sum(r[k] or 0 for r in rows if sel(r))
T = {
    "n_txs": len(rows),
    "n_pool_txs": sum(1 for r in rows if r["touches_mintswap_pool"]),
    "pool_eth_out": round(tot("pool_eth_out"), 9), "pool_eth_in": round(tot("pool_eth_in"), 9),
    "pool_eth_net_to_yoink": round(tot("pool_eth_out") - tot("pool_eth_in"), 9),
    "coinbase_paid_all": round(tot("coinbase_paid_eth"), 9),
    "coinbase_paid_pool_txs": round(tot("coinbase_paid_eth", lambda r: r["touches_mintswap_pool"]), 9),
    "gas_cost_all": round(tot("gas_cost_eth"), 9), "priority_fee_paid_all": round(tot("priority_fee_paid_eth"), 12),
    "est_gross_all": round(tot("est_gross_profit_eth_w4_rule"), 6),
    "est_gross_pool_txs": round(tot("est_gross_profit_eth_w4_rule", lambda r: r["touches_mintswap_pool"]), 6),
    "builder_refunds_to_yoink": round(sum(p["builder_refund_to_yoink_contract_eth"] for p in per_block), 9),
    "proposer_payments": round(sum(p["proposer_payment_eth"] for p in per_block), 9),
}
T["net_paid_to_validators_side"] = round(T["coinbase_paid_all"] - T["builder_refunds_to_yoink"], 9)
T["bot_net_est"] = round(T["est_gross_all"] - T["coinbase_paid_all"] + T["builder_refunds_to_yoink"] - T["gas_cost_all"], 6)
T["note"] = ("est_gross = coinbase / (msg.value/1000) from the bot analysis bribe rule (research/bot-re/analysis.md); the sum of builder refunds (101.73 ETH) and of proposer payments "
             "(9.20 ETH) reconcile with Yoink's own message: 'profit looks to have been 101.8 Eth ... roughly 9 Eth was sent to validators'.")
json.dump({"txs": rows, "per_block": per_block, "totals": T}, open(D / "yoink_mintswap_txs.json", "w"), indent=1)

# ---------------------------------------------------------------------------------------------------- pool history
txl = J(f"data/raw/etherscan/txlist_{ROUTER}.json")["result"]
itl = J(f"data/raw/etherscan/txlistinternal_{ROUTER}.json")["result"]
tkl = J(f"data/raw/etherscan/tokentx_{ROUTER}.json")["result"]
ev = {}
for x in tkl:
    e = ev.setdefault(x["hash"], {"hash": x["hash"], "block": int(x["blockNumber"]), "time_utc": iso(x["timeStamp"]), "vmint_to_pool": 0.0, "vmint_from_pool": 0.0, "eth_to_pool": 0.0, "eth_from_pool": 0.0, "counterparty": None, "direct_caller": None, "function": None, "status": "success"})
    amt = int(x["value"]) / E18
    if x["to"].lower() == ROUTER:
        e["vmint_to_pool"] += amt; e["counterparty"] = x["from"]
    else:
        e["vmint_from_pool"] += amt; e["counterparty"] = x["to"]
for x in itl:
    if x["type"] != "call" or int(x["value"]) == 0:
        continue
    e = ev.setdefault(x["hash"], {"hash": x["hash"], "block": int(x["blockNumber"]), "time_utc": iso(x["timeStamp"]), "vmint_to_pool": 0.0, "vmint_from_pool": 0.0, "eth_to_pool": 0.0, "eth_from_pool": 0.0, "counterparty": None, "direct_caller": None, "function": None, "status": "success"})
    v = int(x["value"]) / E18
    if x["to"].lower() == ROUTER:
        e["eth_to_pool"] += v; e["counterparty"] = e["counterparty"] or x["from"]
    else:
        e["eth_from_pool"] += v; e["counterparty"] = e["counterparty"] or x["to"]
for x in txl:
    e = ev.setdefault(x["hash"], {"hash": x["hash"], "block": int(x["blockNumber"]), "time_utc": iso(x["timeStamp"]), "vmint_to_pool": 0.0, "vmint_from_pool": 0.0, "eth_to_pool": 0.0, "eth_from_pool": 0.0, "counterparty": None, "direct_caller": None, "function": None, "status": "success"})
    e["direct_caller"] = x["from"]; e["function"] = x["functionName"].split("(")[0] or x["input"][:10]
    e["status"] = "reverted" if x["isError"] == "1" else "success"
    if e["status"] == "success" and int(x["value"]) and not e["eth_to_pool"]:
        e["eth_to_pool"] += int(x["value"]) / E18   # direct EOA call: ETH is tx.value, not an internal transfer
    e["index"] = int(x["transactionIndex"]) if x.get("transactionIndex") else None


def actor(addr):
    a = (addr or "").lower()
    return {YOINK_C: "Yoink contract", ARB_C: "arb searcher contract 0x4ab12e7c (EOA 0x1a56abf4)", LP: "LP 0x5b03"}.get(a, "user/other")


hist = []
for e in sorted(ev.values(), key=lambda e: (e["block"], e.get("index") or 0)):
    if e["hash"] == LP_ADD:
        e["classification"] = "LP deposit (pool created by factory create2 in the same tx)"
    elif e["status"] == "reverted":
        e["classification"] = "reverted call to pool"
    elif e["vmint_to_pool"] and e["eth_from_pool"]:
        e["classification"] = "SELL vMINT -> ETH (swapExactTokensForETH, the buggy path)"
    elif e["vmint_from_pool"] and e["eth_to_pool"]:
        e["classification"] = "BUY vMINT with ETH (swapExactETHForTokens, correct formula)"
    elif e["vmint_to_pool"] and not e["eth_from_pool"]:
        e["classification"] = "vMINT in, no ETH out"
    else:
        e["classification"] = "LP removal / other"
    e["actor"] = actor(e["counterparty"])
    e["counterparty_label"] = actor(e["counterparty"])
    hist.append(e)
sells = [e for e in hist if e["classification"].startswith("SELL")]
first_sell = sells[0]
pool_bal = {}
for n in (19560840, 19563163, 19563164, 19563165, 19563194):
    b = rpc("eth_getBalance", [ROUTER, hex(n)], key=f"balance_{ROUTER}_{n}")
    t = rpc("eth_call", [{"to": VMINT, "data": "0x70a08231" + "0" * 24 + ROUTER[2:]}, hex(n)], key=f"vmint_bal_{ROUTER}_{n}")
    pool_bal[str(n)] = {"eth": int(b, 16) / E18, "vmint": int(t, 16) / E18}
pool = {"pool": ROUTER, "impl": IMPL, "factory": FACTORY, "token": VMINT, "uniswap_v2_pair": PAIR,
        "history": hist, "first_sell_path_call": {"hash": first_sell["hash"], "block": first_sell["block"], "actor": first_sell["actor"]},
        "n_sell_path_calls_total": len(sells),
        "sell_path_calls": [{"hash": e["hash"], "block": e["block"], "actor": e["actor"], "vmint_in": round(e["vmint_to_pool"], 4), "eth_out": round(e["eth_from_pool"], 6)} for e in sells],
        "balances_pool": pool_bal,
        "note": "Built from Etherscan txlist / txlistinternal / tokentx of the pool (every vMINT transfer into or out of the pool and every ETH transfer) plus eth_getBalance / balanceOf at fixed blocks. Before block 19563164 no vMINT is ever transferred INTO the pool except the LP deposit, so no call to the sell path exists before Yoink's tx 0xd2337efb.",
        "raw": {"txlist": f"data/raw/etherscan/txlist_{ROUTER}.json", "internal": f"data/raw/etherscan/txlistinternal_{ROUTER}.json", "tokentx": f"data/raw/etherscan/tokentx_{ROUTER}.json"}}
json.dump(pool, open(D / "pool_history.json", "w"), indent=1)

# ---------------------------------------------------------------------------------------------------- second searcher 0x4ab12e7c
arb_hashes = sorted({x["hash"] for x in itl if ARB_C in (x["from"].lower(), x["to"].lower())}, key=lambda h: next(int(x["blockNumber"]) for x in itl if x["hash"] == h))
arb = []
for h in arb_hashes:
    t = tx_(h); n = int(t["blockNumber"], 16); b = hdr(n); miner = b["miner"].lower()
    tr = tr_(h)
    f = {"in": 0, "out": 0, "cb": 0, "sell": 0}

    def fn(c, p):
        if c.get("error") or c["type"] != "CALL":
            return
        v = int(c.get("value") or "0x0", 16)
        to, fr = c.get("to", "").lower(), c.get("from", "").lower()
        if to == ROUTER and v: f["in"] += v
        if fr == ROUTER and to == ARB_C and v: f["out"] += v
        if to == miner and v: f["cb"] += v
        if to == ROUTER and c.get("input", "").startswith("0x5c7e072b"): f["sell"] += 1
    walk(tr, fn)
    arb.append({"hash": h, "block": n, "index": int(t["transactionIndex"], 16), "time_utc": iso(int(b["timestamp"], 16)), "eoa": t["from"], "contract": t["to"],
                "pool_eth_in": round(f["in"] / E18, 6), "pool_eth_out": round(f["out"] / E18, 6), "sell_path_calls": f["sell"], "coinbase_paid_eth": round(f["cb"] / E18, 6),
                "before_yoink": n < 19563164, "raw": {"trace": f"data/raw/rpc/trace_{h}.json", "tx": f"data/raw/rpc/tx_{h}.json"}})
json.dump({"eoa": ARB_EOA, "contract": ARB_C, "txs": arb,
           "note": "Public-label note: Etherscan names this contract's entry method 'mmmmMEV()' and Yoink's 'yoink()'. Two small tx BEFORE Yoink only buy vMINT from the pool with ETH at the pool's correct buy-side price and sell it on the Uniswap V2 pair (ordinary pool-vs-V2 arbitrage, net +0.1247 and +0.0173 ETH), they never call the sell path. 11 txs AFTER Yoink's first tx arb the displaced price; two of them (blocks 19563191, 19563193) call the sell path with 19,319 and 5,288 vMINT (0.619 and 0.160 ETH out).",
           "pool_history_ref": "incidents/mintswap-2024/pool_history.json"}, open(D / "other_bot_0x4ab.json", "w"), indent=1)

# ---------------------------------------------------------------------------------------------------- pending user sell vs Yoink sell
ut = tx_(USER_SELL); ur = rc_(USER_SELL); utr = tr_(USER_SELL)
yh = Y_ROUTER[0][0]
ytr = tr_(yh)
ycalls = []
walk(ytr, lambda c, p: ycalls.append(c) if c.get("to", "").lower() == ROUTER and c["type"] == "CALL" else None)
yin = ycalls[0]["input"]


def dec_sell(i):
    w = [int(i[10 + 64 * k:10 + 64 * (k + 1)], 16) for k in range(4)]
    return {"selector": i[:10], "amount1_vmint_in": w[0] / E18, "amount0min_eth_out_min": w[1] / E18, "to": "0x" + hex(w[2])[2:].zfill(40), "deadline": w[3], "deadline_utc": iso(w[3])}


mem = J("data/raw/mempool-dumpster/index_2024-04.html".replace("index_2024-04.html", "index_2024-04.html")) if False else None
sys.path.insert(0, str(ROOT / "scripts"))
import mempool
ml = mempool.lookup("2024-04-01", [USER_SELL, Y_ROUTER[0][0], Y_ROUTER[1][0]])
mu = ml["txs"][USER_SELL]
blk164 = hdr(19563164); blk163 = hdr(19563163); blk166 = hdr(19563166)
yd = dec_sell(yin)
pool_at_163 = pool_bal["19563163"]
quote = pool_at_163["eth"] * 1000 * 5991.780915423277 / ((pool_at_163["vmint"] - 5991.780915423277) * 997)
diff = {
    "contract": ROUTER, "function": "swapExactTokensForETH(uint256 amount1, uint256 amount0min, address to, uint256 deadline) = 0x5c7e072b",
    "pending_user_tx": {"hash": USER_SELL, "from": ut["from"], "first_seen_utc": mu["first_seen_utc"], "sources": mu["sources"], "per_source_first_seen_ms": mu["per_source_first_seen"],
                        "included_block": int(ut["blockNumber"], 16), "index": int(ut["transactionIndex"], 16), "status": "reverted", "revert": utr.get("revertReason"),
                        "max_fee_gwei": int(ut["maxFeePerGas"], 16) / 1e9, "max_priority_gwei": int(ut["maxPriorityFeePerGas"], 16) / 1e9, "nonce": int(ut["nonce"], 16),
                        "decoded": dec_sell(ut["input"]), "calldata": ut["input"],
                        "quote_with_buggy_formula_eth_at_block_19563163": quote,
                        "note": "Seller 0x7a61c7d3 bought these 5,991.78 vMINT for 0.1 ETH at block 19561170 (13:06:49). amount0min = 98.6% of the buggy getAmountIn quote."},
    "yoink_tx_first_sell_call": {"hash": yh, "block": 19563164, "decoded": yd, "calldata": yin,
                                 "note": "This sell call is one step inside Yoink's script: flash loan -> Uniswap V3 -> V2 buy of vMINT -> THIS call -> swap ETH back -> repay."},
    "diff": {
        "same_function": True,
        "amount1": f"user {5991.780915:.2f} vMINT vs Yoink {yd['amount1_vmint_in']:.2f} vMINT (x{yd['amount1_vmint_in'] / 5991.780915423277:.0f}); Yoink's amount is 49.3% of the pool's vMINT balance at block 19563163 ({pool_at_163['vmint']:.0f})",
        "amount0min": f"user {ut and dec_sell(ut['input'])['amount0min_eth_out_min']:.4f} ETH vs Yoink {yd['amount0min_eth_out_min']} (1 wei)",
        "to": "user's own EOA vs Yoink's contract",
        "deadline": f"user {iso(dec_sell(ut['input'])['deadline'])} vs Yoink {yd['deadline_utc']} = {iso(yd['deadline'] - 3600)} + 3600 s",
    },
    "timing": {"block_19563163_utc": iso(int(blk163["timestamp"], 16)), "user_tx_first_seen_utc": mu["first_seen_utc"], "yoink_tx_build_time_utc_from_deadline_minus_3600": iso(yd["deadline"] - 3600),
               "block_19563164_utc": iso(int(blk164["timestamp"], 16)), "block_19563166_utc": iso(int(blk166["timestamp"], 16)),
               "user_tx_seconds_before_block_19563164": int(blk164["timestamp"], 16) - mu["first_seen_ms"] / 1000},
    "yoink_deadline_convention": "Across all six Yoink txs that call the pool the router deadline equals (second the tx was built) + 3600 s: built at 19:49:25, 19:49:36, 19:53:11, 19:53:25, 19:54:25, 19:54:36 UTC, i.e. 0-2 s after the previous block's timestamp each time (blocks 19563163, 64, 182, 183, 188, 189). The user tx first-seen second (19:49:25.637) equals the build second of Yoink's first tx, but that second is also 2 s after block 19563163, the normal build offset, so the match is consistent with a trigger and does not prove one.",
    "verdict_on_trigger": "unproven. The pending user sell is the first and only public call to the vulnerable function anywhere before Yoink's tx; Yoink's follow-up sells in blocks 19563183 and 19563189 had no new public trigger, so Yoink's pipeline can find this without one.",
    "raw": {"user_tx": f"data/raw/rpc/tx_{USER_SELL}.json", "user_trace": f"data/raw/rpc/trace_{USER_SELL}.json", "yoink_trace": f"data/raw/rpc/trace_{yh}.json",
            "mempool_csv": "data/raw/mempool-dumpster/2024-04-01.csv.zip", "mempool_sourcelog": "data/raw/mempool-dumpster/2024-04-01_sourcelog.csv.zip"},
}
json.dump(diff, open(D / "pending_user_call_diff.json", "w"), indent=1)
json.dump({"lookup": ml}, open(D / "mempool_lookup_2024-04-01.json", "w"), indent=1)
print("tables written", json.dumps(T, indent=1))
print("first sell", first_sell["hash"], first_sell["block"], first_sell["actor"], "sells total", len(sells))
print("pool balances", json.dumps(pool_bal))
print("diff", json.dumps(diff["diff"], indent=1)); print(json.dumps(diff["timing"], indent=1))
print("quote", quote)


# ====================================================================================================== incident.json + timeline.json
AUCT = {}
for n, tx in ((19563164, Y_ROUTER[0][0]), (19563165, Y_ROUTER[1][0]), (19563183, Y_ROUTER[2][0])):
    a = bvh.auction_summary(f"incidents/{SLUG}/race_{n}.json", tx)
    AUCT[n] = a
ret_tx = tx_(RETURN_TX); ret_n = int(ret_tx["blockNumber"], 16); ret_hdr = hdr(ret_n); ret_tr = tr_(RETURN_TX)
assert ret_tr["calls"][0]["to"].lower() == LP and int(ret_tr["calls"][0]["value"], 16) == 91_620_000_000_000_000_000
ret_time = iso(int(ret_hdr["timestamp"], 16))
msgs = {}
for k, h in MSG.items():
    t = tx_(h); n = int(t["blockNumber"], 16)
    msgs[k] = {"tx": h, "block": n, "time_utc": iso(int(hdr(n)["timestamp"], 16)), "from": t["from"], "to": t["to"], "text": bytes.fromhex(t["input"][2:]).decode("utf8", "replace").strip()}
lp_rm = "0xfb022f2e3fdc6d9b5c7fc921ba6b784d32b0267c398dbb98a29fd6c739565872"
lp_rm_time = iso(int(hdr(19574328)["timestamp"], 16))
other_pool_rm = "0x8e9c4093b8ad"   # prefix only used in prose; full hash fetched below
op = next(x for x in J("data/raw/etherscan/txlist_0xdb177ca4c1d4610e54770727a0213fa9e9eb302d.json")["result"] if x["blockNumber"] == "19563212")
OP_POOL = "0xdb177ca4c1d4610e54770727a0213fa9e9eb302d"

yd_rows = {r["hash"]: r for r in rows}
bl = {p["block"]: p for p in per_block}
pu = diff["pending_user_tx"]
RAWR = lambda *p: list(p)

bots = [{
    "label": "Yoink (gen2 contract)", "eoa": YOINK_EOA, "contract": YOINK_C,
    "txs": [r["hash"] for r in rows if r["touches_mintswap_pool"]],
    "followon_txs_touching_vmint_pair": [r["hash"] for r in rows if not r["touches_mintswap_pool"]],
    "captured": {"token": "ETH", "amount": T["bot_net_est"], "usd": None,
                 "basis": "sum of est. gross (coinbase / (msg.value/1000), bot analysis rule) over 10 txs minus 110.796 ETH coinbase minus gas plus 101.729 ETH builder refunds; Yoink's own message says 101.8 ETH"},
    "coinbase_paid_eth": T["coinbase_paid_all"], "coinbase_paid_pool_txs_eth": T["coinbase_paid_pool_txs"], "priority_fee_gwei": 0.0,
    "builder_refund_to_bot_eth": T["builder_refunds_to_yoink"],
    "replay_evidence": "None needed: there is no other attacker. The first call to the pool's sell path anywhere is Yoink's tx 0xd2337efb (block 19563164 index 0); see pool_history.json. Its relation to the pending user sell 0x2bca4d61 is in pending_user_call_diff.json (same function, different args; trigger unproven).",
    "notes": "Method (public trace): flash-loan USDC (Balancer) -> Uniswap V3 USDC/USDT -> buy 1.88M vMINT on the Uniswap V2 vMINT/USDT pair -> sell it to the MintSwap pool (67.86 ETH out) -> ETH->USDC on Uniswap V3 -> repay; follow-up txs buy vMINT back from the emptied pool for 5.98 ETH (4.45M vMINT) and sell it on V2. Bug (from the verified source, MintSwapPool 0x13a3efac): swapExactTokensForETH prices the sale with getAmountIn(amount1, reserve0=ETH, reserve1=tokens) instead of getAmountOut, so ETH out = reserveETH*amount1*1000/((reserveToken-amount1)*997), unbounded as amount1 approaches the pool's token balance."}]
other_racers = [
    {"label": "arb searcher EOA 0x1a56abf4 via contract 0x4ab12e7c (Etherscan method 'mmmmMEV()'; project note: the Ronin ETH-leg searcher, not Yoink)", "role": "pre-existing arbitrageur of the pool vs the V2 pair, and a late sell-path user after Yoink",
     "before_yoink": [x["hash"] for x in arb if x["before_yoink"]], "after_yoink": [x["hash"] for x in arb if not x["before_yoink"]],
     "detail": "2 txs at 18:30:47 and 18:34:35 (blocks 19562775, 19562794) buy vMINT from the pool for 2.135 and 0.807 ETH and sell it on the V2 pair (net +0.125, +0.017 ETH): buy side only, no sell-path call. 11 txs in blocks 19563166-19563194 (all after Yoink's first tx, interleaved with Yoink's later txs) arb the displaced price; the txs in 19563191 and 19563193 sell 19,319 and 5,288 vMINT into the pool for 0.619 and 0.161 ETH (late use of the same bug, ~0.8 ETH). Their txs are private (not in the mempool archive) except a 19:37:12 owner call to 0x4ab12e7c.",
     "classification": "late-copy of the sell path, small (0.78 ETH out of the pool)"},
    {"label": "pending user sell 0x7a61c7d3 (innocent user)", "tx": USER_SELL, "role": "collateral: public-mempool sell of 5,991.78 vMINT, first seen 9.4 s before Yoink's block; reverted with MintSwap: SLIPPAGE_REACHED in block 19563166 index 356 after the pool had been drained"},
    {"label": "LP 0x908d3a91 (second pool 0xdb177ca4)", "tx": op["hash"], "role": "withdrew 30.917 ETH from the factory's third pool at block 19563212 (19:59:11, 10 min after Yoink's first tx); that pool (31 ETH, same implementation) was never drained"},
]
funds = [
    {"what": "Yoink returned to the LP", "tx": RETURN_TX, "block": ret_n, "time_utc": ret_time, "amount_eth": 91.62, "to": LP,
     "note": "owner withdrawTo from the Yoink contract to LP 0x5b03 (the address that deposited 66.4 ETH + 3,997,707 vMINT), as agreed in the on-chain thread; 90% of Yoink's stated 101.8 ETH profit (the MintSwap team's offer was a 10% bounty)"},
    {"what": "builder refunds to Yoink contract", "tx": [p["builder_refund_tx"] for p in per_block], "amount_eth": T["builder_refunds_to_yoink"], "to": YOINK_C,
     "note": "builder 'I can haz block?' (0x229b8325) pays this back at the end of each of the 6 blocks"},
    {"what": "proposer payments", "tx": [p["proposer_payment_tx"] for p in per_block], "amount_eth": T["proposer_payments"], "to": "the six proposers' fee recipients",
     "note": "this is the '~9 ETH sent to validators' in Yoink's message; coinbase 110.80 ETH minus refunds 101.73 = 9.07 ETH net; the builder keeps the 0.14 ETH difference"},
    {"what": "kept by Yoink (bounty)", "amount_eth": round(T["bot_net_est"] - 91.62, 3), "note": "bot_net estimate minus 91.62 returned; using Yoink's own 101.8 it is 10.18 ETH = the 10% bounty the team offered"},
]
inc = {
    "slug": SLUG, "name": "MintSwap vMINT/ETH pool: sell-path pricing bug (swapExactTokensForETH uses getAmountIn)", "date": "2024-04-01", "chain": "ethereum",
    "verdict": "related-not-frontrun", "race_type": "bot-was-first-exploiter", "headline": False, "era": "mature-pbs-2024-26",
    "verdict_reason": ("No separate attacker exists. The 'attack' txs the MintSwap team cites (0xd2337efb, 0x29edec50) are Yoink's own, landing at index 0 of blocks 19563164/19563165. Etherscan's complete transfer history of the pool shows no vMINT sold into it "
                       "before Yoink's tx (the sell path was never called by anyone, pre-exploit the pool saw the LP deposit, 8 successful buys (6 users, 2 small arb buys) and 2 reverted user buys), and no other actor sold into it until after Yoink: 2 small sells by another searcher in blocks 19563191/19563193 (late copy, 0.78 ETH). "
                       "The only third-party tx Yoink beat is an innocent user's still-pending 5,991 vMINT sell (public mempool, first seen 19:49:25.637, 9.4 s before the block), which reverted afterwards; Yoink's tx is a different construction (314x the amount, min-out 1 wei, own recipient), "
                       "so it is not a replay, and whether that sighting triggered the bot is unproven (its follow-up sells had no trigger). Yoink's txs are private (absent from mempool-dumpster); Unknown != none for a private attacker tx, but none was found on chain."),
    "protocol_loss_usd": 476000,
    "protocol_loss_basis": "reported by the MintSwap team's on-chain message ('67.85 ETH (~$238,000) + 4,446,673 vMINT (~$238,000)'); independent check: the pool held 69.54 ETH + 3,817,624 vMINT at block 19563163 and 0.056 ETH + 3,507 vMINT at 19563194",
    "attacker": {"eoas": [], "contracts": [], "deploy_tx": None, "funding_tx": None, "txs": [], "none_reason": "no separate attacker found; see verdict_reason"},
    "pool": {"address": ROUTER, "implementation": IMPL, "factory": FACTORY, "token": VMINT, "created_tx": LP_ADD, "created_block": 19560840, "created_utc": iso(1711972859),
             "balances": pool_bal, "bug_source": "https://etherscan.io/address/0xd8d5b0775a992d1ba9f1b9f43c976a2c1f50bfde#code (verified; impl 0x13a3efac...)", "second_pool_not_drained": OP_POOL},
    "bots": bots, "other_racers": other_racers, "funds_fate": funds,
    "yoink_txs": rows, "per_block": per_block, "totals": T,
    "trigger_candidate": {"tx": USER_SELL, "first_seen_utc": pu["first_seen_utc"], "sources": pu["sources"], "status": "unproven", "detail_file": "incidents/mintswap-2024/pending_user_call_diff.json"},
    "mempool": {"archive": "mempool-dumpster 2024-04-01 (csv + sourcelog)", "yoink_txs_seen": False,
                "note": "None of Yoink's 10 txs is in the archive (private bundles). The archive does contain the pool's pre-exploit buys, the LP deposit, and the user's pending sell 0x2bca4d61 (5 sources within 140 ms). Nothing in the archive calls the pool's sell path before Yoink's block other than that user tx."},
    "auction": {**{k: v for k, v in AUCT[19563164].items() if k != "escalation"}, "escalation": AUCT[19563164].get("escalation"),
                "other_blocks": {str(n): {k: a[k] for k in ("block", "slot", "n_bids", "n_builders", "first_bid_ms_rel_slot", "last_bid_ms_rel_slot", "winning_bid_eth", "winning_builder", "runner_up_other_builder", "runner_up_other_builder_eth", "proposer_paid_eth", "proposer_payment_tx")} for n, a in AUCT.items() if n != 19563164},
                "builder_refund": "In every block the winning builder 'I can haz block?' (0x229b8325) pays back most of Yoink's coinbase transfers to Yoink's contract with a tx near the end of the block (about 91.8% overall; table in yoink_mintswap_txs.json); the rest goes to the proposer.",
                "auction_note": "Block 19563164: 9 Flashbots-relay bids (other relays hold no bids that old); six EigenPhi/other bids at 0.037-0.043 ETH until the Flashbots builder jumps to 1.5613 ETH at -3861 ms (19:49:31.1), 'I can haz block?' wins with 1.6898 ETH at -2779 ms. Same pattern in 19563165 (5.759 ETH) and 19563183 (0.4667 ETH)."},
    "messages": msgs,
    "sources": ["https://etherscan.io/tx/" + MSG["team_notice"], "https://etherscan.io/tx/" + MSG["yoink_profit_offer"], "https://etherscan.io/tx/" + RETURN_TX,
                "https://etherscan.io/address/" + ROUTER, "https://etherscan.io/tx/" + Y_ROUTER[0][0], "https://etherscan.io/tx/" + Y_ROUTER[1][0],
                "research/lineages/yoink_more_incidents.json (MintSwap entry)", "research/lineages/yoink_messages.json",
                "DeFiHackLabs clone (data/raw/defihacklabs_clone/repo, HEAD 23c7bd83): no MintSwap/vMINT entry"],
    "defihacklabs": "No MintSwap entry (grep for mintswap/vMINT/0xd8d5b0775a99/0x4ab12e7c in the clone returns nothing; src/test/2024-04 lists 25 incidents, none is MintSwap). Yoink's contract 0x6980a47b appears only in the Paraswap, TIME, DeFiPlaza and Erc20transfer entries.",
    "raw_refs": {"pool_history": "incidents/mintswap-2024/pool_history.json", "etherscan_pool": [f"data/raw/etherscan/txlist_{ROUTER}.json", f"data/raw/etherscan/txlistinternal_{ROUTER}.json", f"data/raw/etherscan/tokentx_{ROUTER}.json"],
                 "traces": {r["hash"]: f"data/raw/rpc/trace_{r['hash']}.json" for r in rows}, "blocks": {str(n): f"data/raw/rpc/block_{n}.json" for n in blocks},
                 "races": {str(n): f"incidents/{SLUG}/race_{n}.json" for n in (19563164, 19563165, 19563183)}, "return_trace": f"data/raw/rpc/trace_{RETURN_TX}.json",
                 "mempool": ["data/raw/mempool-dumpster/2024-04-01.csv.zip", "data/raw/mempool-dumpster/2024-04-01_sourcelog.csv.zip"]},
}
json.dump(inc, open(D / "incident.json", "w"), indent=1)

# ---------------------------------------------------------------------------- timeline
R = lambda *p: [x for x in p]
tl = []
add = lambda t, kind, actor, detail, tx=None, raw=None, ms=None, block=None: tl.append({k: v for k, v in {"t_utc": t, "t_utc_ms": ms, "block": block, "kind": kind, "actor": actor, "detail": detail, "tx": tx, "raw_ref": raw}.items() if v is not None})
add(iso(int(hdr(19560417)["timestamp"], 16)), "deploy", "MintSwap deployer 0x1461e2d9", "MintSwap factory 0x9c7ddb36 creates the pool implementation 0x13a3efac (tx 0xee6e5bb1...)", block=19560417, raw=f"data/raw/etherscan/txlistinternal_{FACTORY}.json")
add(iso(1711972859), "fund", "LP 0x5b03", "creates the vMINT/ETH pool 0xd8d5b077 (factory create2) and deposits 66.4 ETH + 3,997,707 vMINT in one tx; the pool is live and funded from this moment", tx=LP_ADD, block=19560840, raw=f"data/raw/etherscan/txlistinternal_{FACTORY}.json")
add("2024-04-01T12:04:55Z", "tx", "user 0x908d3a91", "first swap: 0.01 ETH -> 600 vMINT (correct buy-side maths). Six user buys (plus two arb buys) reach the pool before Yoink", tx="0x121712ff183d80034f9f6c4e2536fa5ecfc7afeae268bcaf98b3e8d1d1eededf", block=19560860, raw="incidents/mintswap-2024/pool_history.json")
add("2024-04-01T13:06:49Z", "tx", "user 0x7a61c7d3", "buys 5,991.78 vMINT for 0.1 ETH (the tokens it later tries to sell)", tx="0x7ecbb1f8869d0dde1a4b632d7ad52c90bf45b4f893a486214945de3ee2618f8a", block=19561170, raw="incidents/mintswap-2024/pool_history.json")
add(iso(int(hdr(19562775)["timestamp"], 16)), "tx", "arb searcher 0x1a56abf4 / 0x4ab12e7c", "first non-user contact: buys 123,694 vMINT for 2.135 ETH and sells on the V2 pair (+0.125 ETH). Buy side only; no sell-path call", tx=arb[0]["hash"], block=19562775, raw="incidents/mintswap-2024/other_bot_0x4ab.json")
add(iso(int(hdr(19563074)["timestamp"], 16)), "tx", "user 0x674992b8", "last user buy before the exploit: 0.044 ETH -> 2,415 vMINT", tx="0x2dcf40dc6bc2658c42bafac893f171428149fcbb54a6b401a2e855c0d45987c0", block=19563074, raw="incidents/mintswap-2024/pool_history.json")
add(iso(int(blk163["timestamp"], 16)), "block", "", "block 19563163: pool holds 69.54 ETH and 3,817,624 vMINT; no vMINT has ever been sold into it", block=19563163, raw=f"data/raw/rpc/balance_{ROUTER}_19563163.json")
add(isoms(1712000965637), "mempool_seen", "user 0x7a61c7d3", "public mempool: sell of 5,991.78 vMINT via swapExactTokensForETH (min out 0.1081 ETH), first seen by bloxroute 19:49:25.637, chainbound +14 ms, eden +45 ms, local +108 ms, mempoolguru +139 ms. First and only public call to the sell path before Yoink; max priority fee 0.04 gwei", tx=USER_SELL, ms=1712000965637, raw="data/raw/mempool-dumpster/2024-04-01_sourcelog.csv.zip")
add("2024-04-01T19:49:25Z", "tx", "Yoink", "build time of Yoink's first MintSwap tx, from its router deadline 20:49:25 minus 3600 s (same convention as its other five MintSwap txs, built 0-2 s after each new block)", tx=Y_ROUTER[0][0], raw=f"data/raw/rpc/trace_{Y_ROUTER[0][0]}.json")
a = AUCT[19563164]
for b in json.load(open(D / "race_19563164.json"))["bids"]:
    if b["value_eth"] > 1 and b["builder_name"] in ("Flashbots", "I can haz block?"):
        add(isoms(b["timestamp_ms"]), "bid", b["builder_name"], f"Flashbots-relay bid for slot 8764746: {b['value_eth']:.4f} ETH{' (winning block)' if b['is_winning_block'] else ''}; earlier bids since -5690 ms were 0.037-0.043 ETH", ms=b["timestamp_ms"], raw="data/raw/relay-flashbots/bids_block19563164.json")
add(iso(int(blk164["timestamp"], 16)), "block", "builder 'I can haz block?'", "block 19563164 (slot 8764746), builder 0x229b8325 delivered via flashbots/ultrasound/agnostic; Yoink tx 0xd2337efb at index 0: sells 1,882,581 vMINT into the pool, 67.86 ETH out of a pool that held 69.54; pays 14.369 ETH to the coinbase", tx=Y_ROUTER[0][0], block=19563164, raw="incidents/mintswap-2024/race_19563164.json")
add(iso(int(blk164["timestamp"], 16)), "tx", "Yoink", "same block, index 12: 12.517 ETH coinbase bribe tx touching the V2 vMINT/USDT pair (not the MintSwap pool)", tx=Y_PAIR[0][0], block=19563164, raw=f"data/raw/rpc/trace_{Y_PAIR[0][0]}.json")
add(iso(int(blk164["timestamp"], 16)), "return", "builder 0x229b8325", f"refunds {bl[19563164]['builder_refund_to_yoink_contract_eth']:.4f} ETH to Yoink's contract (index 13) and pays the proposer {bl[19563164]['proposer_payment_eth']:.4f} ETH (index 14)", tx=bl[19563164]["builder_refund_tx"], block=19563164, raw="data/raw/rpc/block_19563164.json")
add("2024-04-01T19:49:36Z", "tx", "Yoink", "build time of its second MintSwap tx (deadline 20:49:36 minus 3600 s), 1 s after block 19563164", tx=Y_ROUTER[1][0], raw=f"data/raw/rpc/trace_{Y_ROUTER[1][0]}.json")
add(iso(int(hdr(19563165)["timestamp"], 16)), "block", "builder 'I can haz block?'", "block 19563165, Yoink index 0: buys 4,446,674 vMINT from the emptied pool for 5.984 ETH (pool had 1.68 ETH), sells them on V2 -> 60.55 ETH, pays 54.507 ETH to the coinbase; builder refunds 56.066 ETH, proposer gets 5.759 ETH", tx=Y_ROUTER[1][0], block=19563165, raw="incidents/mintswap-2024/race_19563165.json")
add(iso(int(blk166["timestamp"], 16)), "tx", "user 0x7a61c7d3", "the pending sell finally lands (index 356) and reverts: MintSwap: SLIPPAGE_REACHED (pool already drained)", tx=USER_SELL, block=19563166, raw=f"data/raw/rpc/trace_{USER_SELL}.json")
add(iso(int(hdr(19563166)["timestamp"], 16)), "tx", "arb searcher 0x1a56abf4 / 0x4ab12e7c", "starts a run of 11 txs (blocks 19563166-19563194) buying vMINT from the drained pool and selling on V2; two of them (19563191, 19563193) use the sell path for 0.62 and 0.16 ETH", tx=arb[2]["hash"], block=19563166, raw="incidents/mintswap-2024/other_bot_0x4ab.json")
add(iso(int(hdr(19563183)["timestamp"], 16)), "block", "Yoink", "block 19563183 index 0: Yoink sells 363,899 vMINT into the pool again (12.897 ETH out, ETH that the searcher's buys had put back); 6.152 ETH coinbase", tx=Y_ROUTER[2][0], block=19563183, raw="incidents/mintswap-2024/race_19563183.json")
add(iso(int(hdr(19563184)["timestamp"], 16)), "block", "Yoink", "block 19563184 index 0: buys 963,002 vMINT back for 1.446 ETH; 13.228 ETH coinbase", tx=Y_ROUTER[3][0], block=19563184, raw=f"data/raw/rpc/trace_{Y_ROUTER[3][0]}.json")
add(iso(int(hdr(19563189)["timestamp"], 16)), "block", "Yoink", "block 19563189: sells 55,251 vMINT (1.786 ETH out); 0.818 ETH coinbase", tx=Y_ROUTER[4][0], block=19563189, raw=f"data/raw/rpc/trace_{Y_ROUTER[4][0]}.json")
add(iso(int(hdr(19563190)["timestamp"], 16)), "block", "Yoink", "block 19563190: last Yoink tx on the pool, buys 130,910 vMINT for 0.5 ETH; 1.722 ETH coinbase", tx=Y_ROUTER[5][0], block=19563190, raw=f"data/raw/rpc/trace_{Y_ROUTER[5][0]}.json")
add(iso(int(hdr(19563194)["timestamp"], 16)), "block", "", "block 19563194: pool left with 0.056 ETH and 3,507 vMINT", block=19563194, raw=f"data/raw/rpc/balance_{ROUTER}_19563194.json")
add(iso(int(hdr(19563212)["timestamp"], 16)), "tx", "LP 0x908d3a91", "removes 30.917 ETH from the factory's other 31 ETH pool (0xdb177ca4, same implementation); never drained", tx=op["hash"], block=19563212, raw="data/raw/etherscan/txlistinternal_0xdb177ca4c1d4610e54770727a0213fa9e9eb302d.json")
for k in ("team_notice", "yoink_verify_ask", "team_bug_explained", "yoink_profit_offer", "team_accepts_lp"):
    m = msgs[k]
    add(m["time_utc"], "message", "MintSwap team 0x8b1dcb84" if m["from"].lower() == TEAM else "Yoink", m["text"][:420], tx=m["tx"], block=m["block"], raw=f"data/raw/rpc/tx_{m['tx']}.json")
add(ret_time, "return", "Yoink", "returns 91.62 ETH to LP 0x5b03 (owner withdrawTo, 90% of its stated 101.8 ETH profit)", tx=RETURN_TX, block=ret_n, raw=f"data/raw/rpc/trace_{RETURN_TX}.json")
for k in ("team_waiting", "yoink_already_sent"):
    m = msgs[k]
    add(m["time_utc"], "message", "MintSwap team 0x8b1dcb84" if m["from"].lower() == TEAM else "Yoink", m["text"][:300], tx=m["tx"], block=m["block"], raw=f"data/raw/rpc/tx_{m['tx']}.json")
add(lp_rm_time, "tx", "LP 0x5b03", "removeLiquidity on the drained pool: 0.056 ETH + 3,497 vMINT", tx=lp_rm, block=19574328, raw=f"data/raw/etherscan/txlist_{ROUTER}.json")
tl.sort(key=lambda e: (e.get("t_utc_ms") or 0) if False else e["t_utc"])
json.dump({"note": "Mempool coverage: mempool-dumpster 2024-04-01 (measured for public txs; Yoink's txs are private and absent). Times are block timestamps unless t_utc_ms is given (relay or mempool receive times).", "events": tl}, open(D / "timeline.json", "w"), indent=1)
print("incident + timeline written; events:", len(tl))
