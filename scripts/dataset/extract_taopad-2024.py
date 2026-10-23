"""Extract incident dataset row for taopad-2024 -> data/extract/taopad-2024.json. Run from project root:
   .venv/bin/python incidents/taopad-2024/scripts/build_incident.py   (builds incident.json / call_diff.json / timeline.json)
   .venv/bin/python scripts/dataset/extract_taopad-2024.py"""
import sys, pathlib, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _x6 import *

S = "taopad-2024"
D = f"incidents/{S}"
inc = load(f"{D}/incident.json")
rY, rF = load(f"{D}/race_19226503.json"), load(f"{D}/race_19226482.json")
Y = "0x5853b7a0b09f600baf44317ccc311382c9bc5d954b21968ac0ee3cbae3481c3e"
F = "0xced2c7fa5eaf5dc0829b6fcbd8ab979e4dd267b9677911351a852db73f537b2d"
RET = "0xa03463523f384d4240a10829577d807789861a71d2d7886701a4073ebb799c32"
YOINK = "0xfde0d1575ed8e06fbf36256bcdfa1f359281455a"
n = inc["numbers"]
ty, tf = txrow(rY, Y), txrow(rF, F)
assert ty["index"] == 0 and ty["status"] == 1 and ty["from"] == YOINK and tf["index"] == 0 and tf["status"] == 0
assert eth(ty["coinbase_transfer_wei"]) == n["coinbase"]
# builder refund to the bot: any tx in the block from the coinbase to the Yoink contract? (check)
cb = rY["block"]["fee_recipient"].lower()
refund = sum(int(t["value_wei"]) for t in rY["txs"] if t["from"].lower() == cb and (t["to"] or "").lower() == inc["bots"][0]["contract"]) / 1e18
assert refund == 0.0
mem = rF["mempool"]["txs"][F]
auction = bvh.auction_summary(f"{D}/race_19226503.json", Y)
mrefs = ["data/raw/mempool-dumpster/2024-02-14.csv.zip", "data/raw/mempool-dumpster/2024-02-14_sourcelog.csv.zip"]
TY, TF = f"data/raw/rpc/trace_{Y}.json", f"data/raw/rpc/trace_{F}.json"
ret_dt = iso(int(load("data/raw/rpc/block_hdr_19233454.json")["result"]["timestamp"], 16))
kept = n["net"] - n["ret"]
yb_ts = int(load("data/raw/rpc/block_hdr_19226503.json")["result"]["timestamp"], 16)
gap_first_seen_s = yb_ts - mem["first_seen_ms"] / 1000

refs = {
    "bot.block": "data/raw/rpc/block_19226503.json",
    "bot.position": ["data/raw/rpc/block_19226503.json", "data/raw/rpc/receipts_19226503.json"],
    "attacker_block": "data/raw/rpc/block_19226482.json",
    "trigger.first_seen_utc_ms": mrefs + [f"{D}/race_19226482.json"],
    "loot.gross_loot_eth": [TY, f"data/raw/rpc/rcpt_{Y}.json"],
    "loot.coinbase_paid_eth": [TY, "data/raw/rpc/trace_block_19226503.json"],
    "loot.priority_fee_paid_eth": ["data/raw/rpc/receipts_19226503.json", "data/raw/rpc/block_19226503.json"],
    "loot.builder_refund_to_bot_eth": ["data/raw/rpc/block_19226503.json", "data/raw/rpc/trace_block_19226503.json"],
    "loot.bot_net_eth": [TY, f"data/raw/rpc/rcpt_{Y}.json", "data/raw/rpc/block_hdr_19226503.json"],
    "fate.returned_by_bot_eth": [f"data/raw/rpc/tx_{RET}.json", f"data/raw/rpc/rcpt_{RET}.json"],
    "fate.returned_total_eth": [f"data/raw/rpc/tx_{RET}.json", f"data/raw/rpc/rcpt_{RET}.json"],
    "fate.kept_by_bot_eth": [TY, f"data/raw/rpc/tx_{RET}.json"],
    "evidence_level_mempool": mrefs,
    "operator_tx_trace": TF, "bot_tx_trace": TY, "operator_tx": f"data/raw/rpc/tx_{F}.json", "bot_tx": f"data/raw/rpc/tx_{Y}.json",
    "calldata_compare": f"{D}/call_diff.json",
    "token_calls_trace_filter": "data/raw/rpc/taopad_tf_token_19226300_19226700.json",
    "operator_txlist": "data/raw/etherscan/taopad_victim_txlist_19200000_19240000.json",
    "yoink_txlist_messages": "data/raw/etherscan/taopad_yoink_txlist_19226000_19234000.json",
    "token_source": "data/raw/etherscan/taopad_source_0x5483dc6abda5f094865120b2d251b5744fc2ecb5.json",
}

row = {
    "slug": S, "name": inc["name"], "date_utc": rY["block"]["timestamp_utc"].replace("+00:00", "Z"), "chain": "ethereum",
    "orig_verdict": inc["verdict"], "race_type_proposed": "post-failure-replay",
    "race_type_reason": "The counterparty is the TaoPad operator (not a hacker). Its tx failed on chain (out of gas, block 19226482); Yoink replayed the same victim-protocol call sequence 21 blocks / 252 s later with a higher gas limit. Nothing was pending in between and no other tx called the vulnerable function.",
    "one_liner": "TaoPad's own operator tx to pull the token's 29.2 ETH tax balance ran out of gas; Yoink replayed its calls 4 min later (net 26.32 ETH) and returned it all the next day after the team wrote to it.",
    "attacker": {"eoa": None, "eoas": [], "contracts": [], "funding": "n/a", "funding_tx": None, "deploy_tx": None, "deploy_block": None, "attack_txs": [],
                 "none_reason": inc["attacker"]["none_reason"]},
    "counterparty": inc["counterparty"],
    "bot": {"label": "Yoink", "eoa": YOINK, "contract": inc["bots"][0]["contract"], "tx": Y, "block": 19226503, "position": ty["index"], "status": "success",
            "priority_fee_gwei": ty["priority_fee_gwei"]},
    "bots_other": [],
    "evidence_level_mempool": "measured",
    "mempool_note": "mempool-dumpster covers 2024-02-14 (csv + sourcelog). The operator's failed tx was seen publicly by 6 sources (first 13:23:12.276Z, local), 10.7 s before inclusion. Yoink's tx 0x5853b7a0 is not in the archive (private flow), so its own first-seen / bid time is unknown.",
    "trigger": {"kind": None, "tx": F, "first_seen_utc_ms": mem["first_seen_ms"], "first_seen_utc": mem["first_seen_utc"].replace("+00:00", "Z"),
                "sources": mem["sources"],
                "note": f"kind is null on purpose: the first-seen above is the OPERATOR's public tx, but Yoink did not pre-empt it as a pending tx. It was mined and failed (block 19226482, 13:23:23Z) {inc['numbers'] and 252} s before Yoink's block 19226503 (13:27:35Z; {gap_first_seen_s:.1f} s after first seen), with no operator tx pending in between. Recorded to document the gap, not as a trigger."},
    "attacker_block": 19226482,
    "attacker_block_note": "The racing tx is the operator's reverted execute() at block 19226482 index 0; Yoink landed 21 blocks AFTER it (blocks_ahead = -21).",
    "attacker_reference": {"kind": "attack-tx", "block": 19226482, "tx": F},
    "auction": {**auction, "auction_note": "138 bids / 21 builders on Flashbots' archive. The winning block (blockbeelder via Ultrasound, 1.4032 ETH to the proposer, contains Yoink's tx) was submitted once at +380 ms; best other bid 0.0222 ETH (beaverbuild, +320 ms): the block was ~63x the next best bid. The bot's own submission time and whether other builders also held its bundle are unknown (relays do not publish bid contents). Not a competition for a pending attacker tx."},
    "loot": {
        "scope": "bot-tx",
        "gross_loot_eth": round(n["gross"], 12),
        "gross_loot_method": "WETH.withdraw ETH delivered to Yoink's contract in the tx trace (29.5056 ETH: 29.1789 from the TPAD token's accumulated ETH balance sold through the in-tx Uniswap V3 pool + 0.3267 recovered liquidity) minus the 1.0 ETH working capital it sent into the router/position manager. This is also the 'profit' of Yoink's per-mille bribe rule: 49/1000 x 28.5056 = 1.3968 = the coinbase transfer.",
        "captured_native": {"amount": round(n["tax_eth"], 6), "unit": "ETH", "desc": "ETH balance of the TPAD token contract (accumulated trading taxes), swapped via a pool created inside the tx and withdrawn as WETH"},
        "captured_usd": None, "captured_usd_source": None,
        "coinbase_paid_eth": round(n["coinbase"], 12),
        "priority_fee_paid_eth": ty["priority_fee_total_wei"] / 1e18 if isinstance(ty["priority_fee_total_wei"], int) else eth(ty["priority_fee_total_wei"]),
        "builder_refund_to_bot_eth": 0.0,
        "builder_payout_to_victim_eth": None,
        "bot_net_eth": round(n["net"], 12),
        "loot_note": f"bot_net = gross {n['gross']:.4f} - coinbase {n['coinbase']:.4f} - gas {n['gas']:.4f} (29.38M gas at base fee 26.71 gwei, priority fee 0) = {n['net']:.4f} ETH. No builder refund in this block (13 txs; the only builder-sent tx is the proposer payment).",
    },
    "fate": {
        "return_status": "returned",
        "returned_by_bot_eth": n["ret"], "returned_by_builder_eth": None, "returned_total_eth": n["ret"],
        "returned_to": "taopad.eth 0x98915686e23032a1d3b8596badd7fadf147d5c00 (the operator wallet that sent the failed tx)",
        "returned_desc": f"Yoink sent exactly 26.32 ETH to taopad.eth on {ret_dt} (block 19233454, tx {RET[:10]}...) with the message 'Thanks for the explanation, sent back the entire bot profit.' 99.98% of the bot's net {n['net']:.4f} ETH, 92.3% of the 28.5056 ETH gross after working capital (the bribe and gas are sunk). Sequence: TaoPad messaged Yoink at 2024-02-14T13:54:59Z (27 min after the tx); Yoink asked for details 'to make sure it wasn't a failed rug attempt' (20:50:47Z); TaoPad explained at 2024-02-15 09:26-09:37Z; Yoink returned at 12:53:35Z.",
        "bounty_kept_eth": None, "bounty_desc": "No bounty; Yoink kept only the ~0.0042 ETH difference between the 26.32 round number and its 26.3242 net.",
        "kept_by_bot_eth": round(kept, 12),
        "returned_txs": [{"tx": RET, "eth": n["ret"], "note": "Yoink -> taopad.eth, 'sent back the entire bot profit'", "block": 19233454, "time_utc": ret_dt}],
        "public_statement": "On-chain messages only (research/lineages/yoink_messages.json; decoded from the Yoink EOA txlist). TaoPad: 'we have been frontran by your bot' / 'we have to extract the rewards ourselves taking advantage of this vulnerability'; Yoink: 'Thanks for the explanation, sent back the entire bot profit.'",
    },
    "raw_refs": refs,
    "rawref_gaps": [
        {"field": "trigger (Yoink)", "why": "Yoink's tx is not in mempool-dumpster; what triggered it (operator's public tx, helper deployment, setPoolFee or independent discovery) is unknown"},
        {"field": "protocol_loss_usd", "why": "no USD price source saved; 29.18 ETH is the TPAD tax balance taken"},
        {"field": "earlier third-party TPAD exploit", "why": "TaoPad says the token was exploited weeks earlier; not identified or verified here; no web source fetched (search budget exhausted)"},
    ],
    "discrepancies": [
        "yoink_more_incidents.json calls this 'not an exploit by Yoink: it front-ran the project extracting its own rewards'. The chain shows a replay AFTER the project's tx had already failed (21 blocks, 252 s later), not a front-run of a pending tx.",
        "TaoPad's message says its tx failed because it 'was frontran'. Its tx reverted out of gas on its own (gas limit 29,792,302; the failing frame is the second swap, which needed more than the ~10.06M gas it was given); Yoink's equivalent swap used 10,041,501 with a 30,000,000 limit.",
        f"leads file est_profit 28.506 ETH is the gross-profit estimate (coinbase / 0.049); the bot's net after bribe and gas is {n['net']:.4f} ETH.",
    ],
    "evidence_notes": [
        f"{D}/call_diff.json: 9 victim-protocol calls of Yoink's tx pair one-to-one with calls of the operator's tx (same target, selector; 4 byte-identical after normalising the two contracts; the others differ in swap/mint deadline = each tx's block timestamp, one amount-bound word, approve amount). The ETH amounts 0.6667 + 0.3333 and distribute(0) are identical. The operator's trace stops at the second swap (out of gas); Yoink's continues with decreaseLiquidity/collect and two WETH.withdraw.",
        "data/raw/rpc/taopad_tf_token_19226300_19226700.json: the only calls to TPAD.distribute (0x91c05b0b) in blocks 19226300-19226700 are the operator's reverted one (19226482) and Yoink's (19226503): no other racer, no earlier exploiter in the window.",
        "data/raw/etherscan/taopad_victim_txlist_19200000_19240000.json: operator nonces 451 (fund deployer, 19226381), 453 (execute, failed), 452 setPoolFee(100) at 19226402 before, 454 setPoolFee(0) at 19226577 after Yoink: no pending operator tx between the failure and Yoink.",
        "TPAD token source (verified on Etherscan): distribute(uint256 amountOutMinimum) is public, swaps the contract's whole ETH balance to the reward token through Uniswap V3 at the operator-set poolFee with the caller's minimum-out. TaoPad set poolFee to 0 after the incident ('so nobody could exploit Tpad contract again').",
    ],
    "incident_dir": D,
}
row["trigger"]["note"] = row["trigger"]["note"].replace(f"{inc['numbers'] and 252} s", "252 s")
write(S, [row])
