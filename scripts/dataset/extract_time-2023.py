"""Extract time-2023 -> data/extract/time-2023.json. Run from project root with .venv/bin/python.
One row: Yoink was the first exploiter (no separate attacker). Fetches (cached) the header of the block of the escrow withdrawal via rawfetch."""
import json, pathlib, sys, datetime
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import bvh, rawfetch

SLUG = "time-2023"
D = f"incidents/{SLUG}"
BOT_TX = "0xecdd111a60debfadc6533de30fb7f55dc5ceed01dfadd30e4a7ebdb416d2f6b6"
COPY_TX = "0x1911be7020af964e35abfe5a94c9f2a232cc017532c1c14a1dea57c6ac011af3"
ESC_DEPLOY = "0x8e0a4d9d67859270a49f58e5a99096fb33b5302b4f948160328df4afcc94054a"
ESC_FUND = "0xbfcf25531feb6d06af2628ddedee29bbbef2668fdbe296aca7f4215422ec4ba2"
ESC_MSG = "0xbd3eb26447f850cd44f1e66daafaad096c83b207acb725999625c7f463f38a80"
ESC_WD = "0x487f7c96d538c32741e4eb4ec62cb8a2d8c207d707b1a7d10241373c72528d7b"
ESCROW = "0x7bac4a2ede0779a1f79a5fefe4fe271b37304e24"
WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
E18 = 10 ** 18
J = lambda p: json.load(open(ROOT / p))
iso = lambda ts: datetime.datetime.fromtimestamp(int(ts), datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
res = lambda d: d.get("result", d)

inc = J(f"{D}/incident.json")
race = J(f"{D}/race_18730463.json")
race2 = J(f"{D}/race_18732002.json")
txs = {t["hash"]: t for t in race["txs"]}
tx0 = txs[BOT_TX]
assert tx0["index"] == 0 and tx0["status"] == 1 and tx0["from"] == "0xfde0d1575ed8e06fbf36256bcdfa1f359281455a"
cp = next(t for t in race2["txs"] if t["hash"] == COPY_TX)

# proceeds from the saved trace: WETH.deposit value in (own capital), WETH.withdraw ETH out, coinbase transfer
TRACE = f"data/raw/rpc/trace_{BOT_TX}.json"
tr = res(J(TRACE))
contract = tr["to"].lower()
cb = race["block"]["fee_recipient"].lower()
w_in = w_out = cb_wei = 0
def walk(c, parent=None):
    global w_in, w_out, cb_wei
    v = int(c.get("value") or "0x0", 16)
    to = c.get("to", "").lower()
    if to == WETH and c.get("input", "").startswith("0xd0e30db0"):
        w_in += v
    if parent and parent.get("to", "").lower() == WETH and to == contract and v:
        w_out += v
    if to == cb and v:
        cb_wei += v
    for x in c.get("calls", []):
        walk(x, c)
walk(tr)
assert cb_wei == int(tx0["coinbase_transfer_wei"])
w_in, w_out = w_in / E18, w_out / E18
gross = w_out - w_in          # WETH out of the pool minus the 5 ETH Yoink put in
coinbase = cb_wei / E18
prio = int(tx0["priority_fee_total_wei"]) / E18
refund_txs = [t for t in race["txs"] if t["from"].lower() == cb and t["to"] and t["to"].lower() in (contract, tx0["from"])]
refund = sum(int(t["value_wei"]) for t in refund_txs) / E18   # none
net = gross - coinbase + refund

# escrow story, verified against saved files
def tx_(h):
    return res(J(f"data/raw/rpc/tx_{h}.json"))
fund = tx_(ESC_FUND); wd = tx_(ESC_WD); msg = tx_(ESC_MSG); dep = tx_(ESC_DEPLOY)
assert fund["to"].lower() == ESCROW and int(fund["value"], 16) == 84_100_000_000_000_000_000 and int(fund["blockNumber"], 16) == 18765364
assert wd["to"].lower() == ESCROW and wd["from"].lower() == tx0["from"] and wd["input"].startswith("0x9890220b")
wd_tr = res(J(f"data/raw/rpc/trace_{ESC_WD}.json"))
assert len(wd_tr["calls"]) == 1 and wd_tr["calls"][0]["to"].lower() == tx0["from"] and int(wd_tr["calls"][0]["value"], 16) == 84_100_000_000_000_000_000
msg_rc = res(J(f"data/raw/rpc/receipt_{ESC_MSG}.json"))
assert msg_rc["status"] == "0x0"
bal = {}
for b in ("18765364", "18790000", "18900000", "19200000"):
    bal[b] = int(res(J(f"data/raw/rpc/bal_{ESCROW}_{b}.json")), 16) / E18
assert bal["18765364"] == bal["18790000"] == bal["18900000"] == 84.1 and bal["19200000"] == 0.0
wd_block = int(wd["blockNumber"], 16)
wd_hdr = rawfetch.rpc("eth_getBlockByNumber", [hex(wd_block), False], key=f"block_hdr_{wd_block}", source="rpc")
wd_time = iso(int(wd_hdr["timestamp"], 16))
tl = {x["hash"]: x for x in J("data/raw/etherscan/time_claim_7bac_txlist.json")["result"]}
dep_time, fund_time = iso(tl[ESC_DEPLOY]["timeStamp"]), iso(tl[ESC_FUND]["timeStamp"])
msg_block = int(msg["blockNumber"], 16)

auction = bvh.auction_summary(f"{D}/race_18730463.json", BOT_TX)

BLK, RC, RT = "data/raw/rpc/block_18730463.json", "data/raw/rpc/receipts_18730463.json", "data/raw/rpc/trace_block_18730463.json"
ESCRAW = [f"data/raw/rpc/trace_{ESC_WD}.json", f"data/raw/rpc/tx_{ESC_FUND}.json", f"data/raw/rpc/bal_{ESCROW}_18900000.json", f"data/raw/rpc/bal_{ESCROW}_19200000.json"]
refs = {
    "bot.block": [BLK], "bot.position": [BLK, RC],
    "loot.gross_loot_eth": [TRACE], "loot.coinbase_paid_eth": [TRACE, RT], "loot.priority_fee_paid_eth": [RC, BLK],
    "loot.builder_refund_to_bot_eth": [BLK, RT], "loot.bot_net_eth": [TRACE, BLK],
    "fate.kept_by_bot_eth": [TRACE, BLK] + ESCRAW,
    "evidence_level_mempool": ["data/raw/mempool-dumpster/2023-12-06.csv.zip", "data/raw/mempool-dumpster/2023-12-06_sourcelog.csv.zip"],
    "fate.return_status": ESCRAW,
}

row = {
    "slug": SLUG, "name": inc["name"],
    "date_utc": race["block"]["timestamp_utc"].replace("+00:00", "Z"),
    "chain": "ethereum",
    "orig_verdict": inc["verdict"],
    "race_type_proposed": "bot-was-first-exploiter",
    "race_type_reason": "The tx everyone analyses as the TIME hack is Yoink's own (block 18730463, index 0); the only other forwarder-multicall tx in blocks 18700000-18740000 is a different bot's copy about 5 hours later (block 18732002). No attacker tx exists to beat or replay (a private, never-landed one would be invisible).",
    "one_liner": "Yoink was the first to exploit TIME's thirdweb forwarder bug, taking 89.5 ETH net from the TIME/WETH pool in one private tx; its later 84.1 ETH 'recovery' escrow paid out nothing and was withdrawn back by Yoink.",
    "attacker": {"eoa": None, "eoas": [], "contracts": [], "funding": "n/a", "funding_tx": None, "deploy_tx": None, "deploy_block": None,
                 "attack_txs": [], "none_reason": "No separate attacker: Yoink's tx is the tx that DeFiHackLabs, CertiK and SharkTeam analyse as the attack (84.59 ETH = Yoink's net); the only other exploit-shaped tx is a later copy by an unrelated bot."},
    "bot": {"label": "Yoink", "eoa": tx0["from"], "contract": contract, "tx": BOT_TX, "block": 18730463, "position": tx0["index"], "status": "success",
            "priority_fee_gwei": tx0["priority_fee_gwei"]},
    "bots_other": [{"label": "later copy by a different bot (not Yoink)", "eoa": cp["from"], "tx": COPY_TX, "block": 18732002, "position": cp["index"], "status": "success" if cp["status"] == 1 else "reverted",
                    "role": "independent re-use ~5 h later (2023-12-07T04:21:47Z): same forwarder 0xc82bbe41 -> TIME multicall -> spoofed pool sender, but different req.from, transfer() instead of burn(), Universal-Router-style tx; took 0.274 WETH from the already drained pool (forwarder_call_diff.json)"}],
    "evidence_level_mempool": "absent-from-archive",
    "mempool_note": "mempool-dumpster covers 2023-12-06 (csv + sourcelog) and nothing in it touches the forwarder, TIME token, the pool or Yoink; Yoink's tx is private. The copy bot's tx is not in the 2023-12-07 dump either.",
    "trigger": {"kind": None, "tx": None, "first_seen_utc_ms": None, "first_seen_utc": None, "sources": None,
                "note": "No trigger tx: no attacker or user tx preceded Yoink's."},
    "attacker_block": None,
    "attacker_block_note": "No attacker tx exists to compare against; the only other exploit-shaped tx is the later independent copy at block 18732002 (see bots_other).",
    "attacker_reference": {"kind": "none", "block": None, "tx": None},
    "auction": {**auction, "auction_note": "Flashbots relay kept 295 bids (other relays hold none). Baseline bids 0.0013-0.28 ETH until -2942 ms, then the Flashbots builder bids 4.953 ETH and about 8 builders follow within 1 s (the 4.92 ETH Yoink coinbase payment is in every top bid, inferred from value level only). Winner: Flashbots builder 5.0011 ETH at -155 ms. A higher 8.33 ETH bid from 'I can haz block?' was never delivered (reason unknown). No builder refund."},
    "loot": {
        "scope": "bot-tx",
        "gross_loot_eth": round(gross, 12),
        "gross_loot_method": f"WETH.withdraw ETH delivered to the Yoink contract in the trace ({w_out:.6f}) minus the {w_in:.1f} ETH Yoink wrapped as its own capital at the start of the tx = net WETH taken from the TIME/WETH V2 pool (62.2 billion TIME burned from the pool via the spoofed multicall sender, then TIME sold back)",
        "captured_native": {"amount": f"{gross:.6f}", "unit": "ETH", "desc": f"net WETH out of Uniswap V2 TIME/WETH pool 0x760dc1e0 ({w_out:.6f} out, {w_in:.1f} in)"},
        "captured_usd": None, "captured_usd_source": None,
        "coinbase_paid_eth": round(coinbase, 12),
        "priority_fee_paid_eth": prio,
        "builder_refund_to_bot_eth": refund,
        "builder_payout_to_victim_eth": None,
        "bot_net_eth": round(net, 12),
        "loot_note": "Scope is the bot tx 0xecdd111a (index 0). Coinbase bribe 4.9232 ETH = msg.value 55 per mille of the 89.5135 ETH profit; priority fee 0. No builder refund (no transfer from the Flashbots fee recipient to Yoink in the block). bot_net 84.5902 ETH equals CertiK's reported 84.6 ETH 'attacker' gain.",
    },
    "fate": {
        "return_status": "none-found",
        "returned_by_bot_eth": None, "returned_by_builder_eth": None, "returned_total_eth": None,
        "returned_to": None,
        "returned_desc": f"No return to TIME holders or the project found. On {fund_time[:10]} Yoink funded a contract {ESCROW} with 84.1 ETH (block 18765364) and posted a notice to TIME holders (tx {ESC_MSG[:10]}, block {msg_block}, REVERTED so visible only in its input) that funds could be recovered there. The escrow balance was exactly 84.1 ETH at blocks 18765364, 18790000 and 18900000; on {wd_time[:10]} (block {wd_block}) Yoink's owner call 0x9890220b sent the whole 84.1 ETH back to the Yoink EOA (a single outbound transfer in the trace), and the balance is 0 from block 19200000. So the 84.1 ETH offer was never paid out. Only this escrow route and the funds-flow samples were checked; other later flows of the 84.59 ETH were not traced, hence 'none-found' rather than 'none'.",
        "bounty_kept_eth": None, "bounty_desc": None,
        "kept_by_bot_eth": round(net, 12),
        "returned_txs": [],
        "escrow_txs": [
            {"tx": ESC_DEPLOY, "eth": 0.0, "note": "Yoink EOA deploys escrow contract 0x7bac4a2e", "block": int(dep["blockNumber"], 16), "time_utc": dep_time},
            {"tx": ESC_FUND, "eth": 84.1, "note": "Yoink EOA funds escrow with 84.1 ETH (not a return)", "block": 18765364, "time_utc": fund_time},
            {"tx": ESC_MSG, "eth": 0.0, "note": "on-chain notice to TIME holders, reverted (status 0)", "block": msg_block, "time_utc": None},
            {"tx": ESC_WD, "eth": 84.1, "note": "Yoink owner call pulls all 84.1 ETH back to the Yoink EOA", "block": wd_block, "time_utc": wd_time},
        ],
        "public_statement": None,
    },
    "raw_refs": refs,
    "rawref_gaps": [
        {"field": "trigger.first_seen_utc_ms", "why": "no trigger tx; Yoink's own tx is not in mempool-dumpster"},
        {"field": "fate.returned_total_eth", "why": "only the escrow route was checked; later flows of the 84.59 ETH not traced"},
    ],
    "discrepancies": [],
    "evidence_notes": [
        f"{TRACE}: Yoink contract wraps 5 ETH, buys TIME on the V2 router, calls forwarder 0xc82bbe41 whose inner TIME.multicall delegatecalls burn() with the pool address appended (spoofed sender), syncs the pool, sells TIME back, unwraps {w_out:.4f} ETH and pays {coinbase:.4f} ETH to the coinbase.",
        "incidents/time-2023/yoink_decoded_ops.json: bot analysis-grammar decode of Yoink's script (its own construction, not adapted from any attacker tx); bribe rule 55/1000 x 89.5135 = 4.9232 ETH matches the coinbase transfer.",
        "incidents/time-2023/forwarder_call_diff.json: the copy bot's forwarder call has a different req.from and calls transfer() not burn(), so it is an independent later re-use, not a replay by or of Yoink.",
        "trace_filter over blocks 18700000-18739999 (data/raw/rpc/time_tf_*) finds only these two multicall-through-forwarder txs (per incident.json); neither is in the 2023-12-06/07 mempool dumps.",
    ],
    "incident_dir": D,
}
row["raw_refs"] = {k: v for k, v in refs.items() if v}
out = ROOT / "data" / "extract" / f"{SLUG}.json"
json.dump([row], open(out, "w"), indent=1)
print("wrote", out, "gross", gross, "w_out", w_out, "w_in", w_in, "coinbase", coinbase, "refund", refund, "net", net, "wd", wd_block, wd_time)
