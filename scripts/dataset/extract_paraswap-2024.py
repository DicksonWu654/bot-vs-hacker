"""Extract paraswap-2024 -> data/extract/paraswap-2024.json. Run from project root with .venv/bin/python.
One row: Yoink was the first exploiter (no separate attacker). Receipts of the later independent actors are fetched via rawfetch (cached)."""
import json, pathlib, sys, glob
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import bvh, rawfetch

SLUG = "paraswap-2024"
D = f"incidents/{SLUG}"
BOT_TX = "0x35a73969f582872c25c96c48d8bb31c23eab8a49c19282c67509b96186734e60"
TX1 = "0xaed21758134ab27c8866dd5d82c04186609bed7549a75c80422496764c1fee58"
REFUND_TX = "0x3574e4241410bcce0b91f4faf77934d2d593410168ee7da6170e70044fcc7f1c"
E18 = 10 ** 18
J = lambda p: json.load(open(ROOT / p))

inc = J(f"{D}/incident.json")
race = J(f"{D}/race_19470561.json")
txs = {t["hash"]: t for t in race["txs"]}
tx0 = txs[BOT_TX]
assert tx0["index"] == 0 and tx0["status"] == 1 and tx0["from"] == "0xfde0d1575ed8e06fbf36256bcdfa1f359281455a"

# gross proceeds: WETH.withdraw ETH delivered to the Yoink contract in the tx trace; coinbase transfer
TRACE = f"data/raw/rpc/trace_{BOT_TX}.json"
tr = J(TRACE)["result"]
contract = tr["to"].lower()
cb = race["block"]["fee_recipient"].lower()
gross_wei = cb_wei = 0
def walk(c, parent=None):
    global gross_wei, cb_wei
    v = int(c.get("value") or "0x0", 16)
    if parent and parent.get("to", "").lower() == "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2" and c.get("to", "").lower() == contract and v:
        gross_wei += v
    if c.get("to", "").lower() == cb and v:
        cb_wei += v
    for x in c.get("calls", []):
        walk(x, c)
walk(tr)
assert cb_wei == int(tx0["coinbase_transfer_wei"])
gross, coinbase = gross_wei / E18, cb_wei / E18
rf = txs[REFUND_TX]
assert rf["from"].lower() == cb and rf["to"].lower() == contract and rf["index"] == 13
refund = int(rf["value_wei"]) / E18
prio = int(tx0["priority_fee_total_wei"]) / E18
net = gross - coinbase + refund
tx1_cb = int(txs[TX1]["coinbase_transfer_wei"]) / E18
proposer_pay = int(txs[race["winner"]["proposer_payment_tx"]["hash"]]["value_wei"]) / E18

# captured token amount from the trace: OPSEC transferFrom (victim -> pool); amount word in the calldata
opsec_amt = None
def find_tf(c):
    global opsec_amt
    if (c.get("input") or "").startswith("0x23b872dd") and c["input"][2 + 8 + 24:2 + 8 + 64] == "0cc396f558aae5200bb0abb23225accafca31e27":
        opsec_amt = int(c["input"][2 + 8 + 128:2 + 8 + 192], 16) / E18
    for x in c.get("calls", []):
        find_tf(x)
find_tf(tr)

# victim-side checks (saved trace_filter results)
v_in = J("data/raw/rpc/para_victim_in_19470562_19490000.json")
v_in = v_in.get("result", v_in)
y_to_v = J("data/raw/rpc/para_yoink_to_victim_19470561_19475000.json")
y_to_v = y_to_v.get("result", y_to_v)
assert len(y_to_v) == 0 and all(x["action"]["from"].lower() == "0x3fc91a3afd70395cd496c647d5a6cc9d4b2b7fad" for x in v_in)
v_in_eth = sum(int(x["action"]["value"], 16) for x in v_in) / E18

# direct (traceAddress length <= 1) calls of Augustus callback selector 0xfa461e33 in all saved trace_filter chunks
direct = []
for f in glob.glob(str(ROOT / "data/raw/rpc/para_tf_*.json")):
    res = json.load(open(f)); res = res.get("result", res)
    for x in res:
        if (x["action"].get("input") or "").startswith("0xfa461e33") and len(x["traceAddress"]) <= 1:
            direct.append((x["blockNumber"], x["transactionPosition"], x["transactionHash"]))
direct.sort()
assert direct[0][2] == BOT_TX and direct[1][0] == 19473885

auction = bvh.auction_summary(f"{D}/race_19470561.json", BOT_TX)

# later independent actors: statuses from receipts
def status(h):
    r = rawfetch.rpc("eth_getTransactionReceipt", [h], key=f"rcpt_{h}", source="rpc")
    return "success" if r and r.get("status") == "0x1" else "reverted"
bots_other = [{"label": "Yoink (same bot, 2nd tx)", "eoa": tx0["from"], "tx": TX1, "block": 19470561, "position": 1, "status": "success" if txs[TX1]["status"] == 1 else "reverted",
               "role": "post-exploit arbitrage of the V3/V2 price tx0 had moved; 0.098 ETH to coinbase"}]
for o in inc["other_racers"]:
    bots_other.append({"label": "independent later actor", "eoa": o["eoa"], "tx": o["tx"], "block": o["block"], "position": o["index"], "status": status(o["tx"]),
                       "role": f"{o['time_utc']}: {o['what']}. {o['verdict']}"})

BLK, RC, RT = "data/raw/rpc/block_19470561.json", "data/raw/rpc/receipts_19470561.json", "data/raw/rpc/trace_block_19470561.json"
VIN, YTV = "data/raw/rpc/para_victim_in_19470562_19490000.json", "data/raw/rpc/para_yoink_to_victim_19470561_19475000.json"
refs = {
    "bot.block": [BLK], "bot.position": [BLK, RC],
    "loot.gross_loot_eth": [TRACE], "loot.coinbase_paid_eth": [TRACE, RT], "loot.priority_fee_paid_eth": [RC, BLK],
    "loot.builder_refund_to_bot_eth": [BLK, RT], "loot.bot_net_eth": [TRACE, BLK],
    "fate.kept_by_bot_eth": [TRACE, BLK],
    "evidence_level_mempool": ["data/raw/mempool-dumpster/2024-03-19.csv.zip", "data/raw/mempool-dumpster/2024-03-19_sourcelog.csv.zip"],
    "fate.return_status": [VIN, YTV],
}
refs = {k: v for k, v in refs.items() if v}

row = {
    "slug": SLUG, "name": inc["name"],
    "date_utc": race["block"]["timestamp_utc"].replace("+00:00", "Z"),
    "chain": "ethereum",
    "orig_verdict": inc["verdict"],
    "race_type_proposed": "bot-was-first-exploiter",
    "race_type_reason": "Yoink's tx is the first direct call to Augustus V6's uniswapV3SwapCallback entry in the scanned range; no earlier or same-block attacker tx exists, and the next such call is 11 h 13 min later by independent actors who did not replay Yoink's calldata.",
    "one_liner": "Yoink was the first to exploit Paraswap Augustus V6's missing callback caller check, pulling 12,479 OPSEC (6.46 WETH) from one approving wallet 11 hours before anyone else; no return to the victim or Paraswap found.",
    "attacker": {"eoa": None, "eoas": [], "contracts": [], "funding": "n/a", "funding_tx": None, "deploy_tx": None, "deploy_block": None,
                 "attack_txs": [], "none_reason": "No hostile attacker earlier than or in the same block as the bot: Yoink's tx is the first direct callback call in blocks 19426044-19481999; the later actors (from 2024-03-20 05:38 UTC) are independent users of the same bug."},
    "bot": {"label": "Yoink", "eoa": tx0["from"], "contract": contract, "tx": BOT_TX, "block": 19470561, "position": tx0["index"], "status": "success",
            "priority_fee_gwei": tx0["priority_fee_gwei"]},
    "bots_other": bots_other,
    "evidence_level_mempool": "absent-from-archive",
    "mempool_note": "mempool-dumpster covers 2024-03-19 (csv and sourcelog present); Yoink's tx 0x35a73969 is not in it (private flow). There is no attacker tx to look up.",
    "trigger": {"kind": None, "tx": None, "first_seen_utc_ms": None, "first_seen_utc": None, "sources": None,
                "note": "No trigger tx: the bot found the bug itself; no attacker or user tx preceded it."},
    "attacker_block": None,
    "attacker_block_note": "No attacker tx exists to compare against; the first independent use of the bug is block 19473885 (2024-03-20T05:38:47Z), after the bot.",
    "attacker_reference": {"kind": "none", "block": None, "tx": None},
    "auction": {**auction, "auction_note": "No bid history: Flashbots has no bids for this slot (proposer not registered there) and Ultrasound's 2024-03 bids have expired; only the delivered payload (Ultrasound, builder 'I can haz block?', 2.2229 ETH to the proposer) exists."},
    "loot": {
        "scope": "bot-tx",
        "gross_loot_eth": round(gross, 12),
        "gross_loot_method": "WETH.withdraw ETH delivered to the Yoink contract in the bot tx trace, from selling 12,479.437 OPSEC (pulled from victim wallet 0x0cc396f5 by Augustus V6) into Uniswap V3 pool 0x45f4d604",
        "captured_native": {"amount": f"{opsec_amt:.6f}" if opsec_amt else "12479.437104", "unit": "OPSEC", "desc": "OPSEC transferFrom the approving wallet 0x0cc396f5 to the V3 pool, sold for 6.4633 WETH"},
        "captured_usd": None, "captured_usd_source": None,
        "coinbase_paid_eth": round(coinbase, 12),
        "priority_fee_paid_eth": prio,
        "builder_refund_to_bot_eth": round(refund, 12),
        "builder_payout_to_victim_eth": None,
        "bot_net_eth": round(net, 12),
        "loot_note": f"Scope is tx0 (index 0): gross {gross:.4f} ETH, 99.8% ({coinbase:.4f}) paid to the coinbase, priority fee 0. The builder refund (index 13, {refund:.4f} ETH) is a block-level remainder: coinbase payments in the block are {coinbase + tx1_cb:.4f} ETH (tx0 + tx1), proposer got {proposer_pay:.4f} ETH, so the refund also covers Yoink's arbitrage tx1 (net +0.0092 ETH). bot_net = gross - coinbase + refund; with tx1 included the incident's figure is 4.359 ETH.",
    },
    "fate": {
        "return_status": "none-found",
        "returned_by_bot_eth": None, "returned_by_builder_eth": None, "returned_total_eth": None,
        "returned_to": None,
        "returned_desc": f"No return to the victim wallet 0x0cc396f5 or to Paraswap/Velora found. Checked: no Yoink -> victim transfer in blocks 19470561-19475000 (trace_filter, empty) and the victim's inbound ETH to block 19490000 is only two transfers from 0x3fc91a3a ({v_in_eth:.3f} ETH total, blocks 19470763 and 19471472, source unknown and not shown to be a Yoink or Paraswap return). Full-history check of Yoink's later flows was not done. 'None found' is not 'none'.",
        "bounty_kept_eth": None, "bounty_desc": None,
        "kept_by_bot_eth": round(net, 12),
        "returned_txs": [],
        "public_statement": "Velora post-mortem (not retrievable here, HTTP 403) reportedly lists ~$24K initial loss matching this tx; DeFiHackLabs and Etherscan label the actor a whitehat, which on-chain behaviour does not support.",
    },
    "raw_refs": refs,
    "rawref_gaps": [
        {"field": "trigger.first_seen_utc_ms", "why": "no trigger tx exists; Yoink's own tx is not in mempool-dumpster"},
        {"field": "auction.bids", "why": "no bid history for slot 8670726 (Flashbots had no bids, Ultrasound history expired)"},
        {"field": "fate.returned_*", "why": "full-history trace of Yoink's later flows not done; Velora post-mortem not fetchable"},
    ],
    "discrepancies": [
        "DeFiHackLabs/press date the incident 2024-03-20 (Paraswap pause); the first on-chain abuse is this tx on 2024-03-19 18:25:35Z.",
        f"incident.json 'Yoink net 4.359 ETH' includes tx1 (+0.0092) and the whole builder refund; the row's bot_net for tx0 only is {net:.5f} ETH.",
    ],
    "evidence_notes": [
        f"{TRACE}: tx0 = Yoink contract -> Augustus V6 0x00000000fdac... selector 0xfa461e33 (callback entry) at depth 1 with no Augustus swap above it; Augustus then calls V3 pool 0x45f4d604 swap(recipient = Yoink) and pulls OPSEC from the victim wallet via transferFrom; WETH.withdraw then coinbase transfer.",
        f"Across the 253 saved trace_filter chunks (blocks 19426044-19481999, toAddress = Augustus) the earliest call to 0xfa461e33 at trace depth <= 1 is this tx ({direct[0][0]}/{direct[0][1]}); the next is block {direct[1][0]} (11 h 13 min later), then 19474732.",
        "incidents/paraswap-2024/callback_calldata_words.json: same selector and layout in the later actors' calls but different victim/token/amount, so they are independent uses of the bug, not replays of Yoink's calldata.",
        "Bribe rule: msg.value 998 (per mille) x 6.4633 WETH = 6.4504 ETH, equal to the coinbase transfer in the trace; builder 'I can haz block?' then refunded 4.3369 ETH at index 13.",
    ],
    "incident_dir": D,
}
out = ROOT / "data" / "extract" / f"{SLUG}.json"
json.dump([row], open(out, "w"), indent=1)
print("wrote", out, "gross", gross, "coinbase", coinbase, "refund", refund, "net", net, "opsec", opsec_amt, "v_in", v_in_eth, "direct", direct[:3])
