"""Extract peapods-2025 -> data/extract/peapods-2025.json (3 rows). Run from project root with .venv/bin/python.
Numbers are recomputed from saved raw responses (data/raw/rpc/peap_*, data/raw/etherscan/peap_*, block/receipt/trace dumps)."""
import json, pathlib, sys, datetime
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import bvh

SLUG = "peapods-2025"
D = f"incidents/{SLUG}"
E18 = 10 ** 18
J = lambda p: json.load(open(ROOT / p))
iso = lambda ts: datetime.datetime.fromtimestamp(int(ts), datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

YOINK = "0xfde0d1575ed8e06fbf36256bcdfa1f359281455a"
VAULT = "0xc70f00cd7e461686b04b0e912e309beca8b80ea0"
TEAM = "0x21fe3e26e824783ca7e374355a8d30ae8bbf6e37"
WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
ATT_EOA = "0x277da2d1ce5601c0f0133515c19da314fc52a846"
ATT_C = "0x7212de58f97ad6c28623752479acaeb6b15ad006"
Y_TX = "0xff8e9226091d513fc936ecc670030eba03f34dbe60cd012122bd18be44248d32"
Y_TX1 = "0xeb420caf54b0e2a2f2bacd90130793300cb4bd2f1f7bd8563d6d31abc846f8ad"
Y_TX2 = "0xfb557c19bfb4433cde8c17994605938dd2d94e3b864913accc54268a11efd405"
ATT_TXS = {
    22873986: "0xeff836fa1ce60f04b94544fa424764101323f1f7c8ab8265b4bd34e9fa84f8db",
    22874007: "0xdc77441724cbdda85ae9b3ae9f34d82307a12ea1e728750411dd4e35679f7f62",
    22874008: "0x505db20226ec0eaa3d20e2972cbb14772ffe8da9669349684042c82b33f7f9ed",
    22874009: "0xa03582cc1b84b1c56ad59d503a54e43e1a599d38d64eb52acfdcf571492fb2f1",
    22874015: "0x12b1dc098f75b661d0b1bc2db71588e0aa95a2e66be742b3abfeec678d86bf7d",
    22874016: "0x03986527138815646e56082789fd6dd0f20faa7c3abc758abe58a5e9f5a811ad",
}
OCT_TX = "0xe00aea94c4f9374f1a005a9f5832f0d36b3e8cd1f6f5407ee6cb629461ecbbde"
OCT_USER = "0x60b2c65c3fded55a34bde7b99f0b5e1ef9d7a91c5ad6afc31fcd29e15bf9c8f1"
OCT_RET = "0xcd6d475f859cddeb637906c668dc616f1f470033bdb44f4b99c40eb84dacd3e6"
JUL9_TX = "0xd685d0741cf257493c8d804a0daca45f48284ffac1bf749f63326699781ffd6e"


def trace(h):
    return J(f"data/raw/rpc/peap_trace_{h}.json")["result"]


def tx_flows(h, wallet):
    """(ETH received by wallet via value-bearing CALLs, ETH sent by wallet, WETH.deposit value paid by wallet)"""
    r = [0, 0, 0]

    def w(c):
        v = int(c.get("value", "0x0"), 16)
        if v and c["type"] == "CALL":
            if c.get("to", "").lower() == wallet:
                r[0] += v
            if c.get("from", "").lower() == wallet:
                r[1] += v
                if c.get("to", "").lower() == WETH and c.get("input", "").startswith("0xd0e30db0"):
                    r[2] += v
        for x in c.get("calls", []):
            w(x)
    w(trace(h))
    return [x / E18 for x in r]


# ============================================================ row 1: second-attempt (July, block 22874010)
inc = J(f"{D}/incident.json")
race10 = J(f"{D}/race_22874010.json")
tx10 = {t["hash"]: t for t in race10["txs"]}
y0 = tx10[Y_TX]
assert y0["index"] == 0 and y0["status"] == 1 and y0["from"] == YOINK
BOT = y0["to"].lower()
cb0 = int(y0["coinbase_transfer_wei"]) / E18
cb_blk = sum(int(tx10[h]["coinbase_transfer_wei"]) for h in (Y_TX, Y_TX1, Y_TX2)) / E18
assert abs(cb0 - 11.4944269) < 1e-9 and y0["priority_fee_gwei"] == 0.0
gas0 = y0["gas_used"] * y0["gas_price_gwei"] / 1e9
prio0 = int(y0["priority_fee_total_wei"]) / E18
assert [t["index"] for t in race10["txs"]] == [0, 1, 2, 3] and race10["txs"][3]["hash"] == race10["winner"]["proposer_payment_tx"]["hash"]
prop_pay = int(race10["txs"][3]["value_wei"]) / E18
vt = J("data/raw/etherscan/peap_vault_tokentx_22874000_22960000.json")["result"]
gross_usdc = int(next(x for x in vt if x["hash"] == Y_TX and x["to"].lower() == VAULT)["value"]) / 1e6
swap1 = next(x for x in vt if x["blockNumber"] == "22889148" and x["from"].lower() == VAULT)
ret = next(x for x in vt if x["blockNumber"] == "22889167" and x["to"].lower() == TEAM)
swap2 = next(x for x in vt if x["blockNumber"] == "22928685" and x["from"].lower() == VAULT)
swap1_usdc, ret_usdc, swap2_usdc = (int(x["value"]) / 1e6 for x in (swap1, ret, swap2))
vi = J("data/raw/etherscan/peap_vault_txlistinternal_22874010_22960000.json")["result"]
eth1 = int(next(x for x in vi if x["blockNumber"] == "22889148")["value"]) / E18
eth2 = int(next(x for x in vi if x["blockNumber"] == "22928685")["value"]) / E18
assert abs(gross_usdc - 174258.313813) < 1e-6 and abs(eth1 - 11.95248) < 1e-9
assert abs(0.9 * (gross_usdc - swap1_usdc) - ret_usdc) < 0.01 and abs(gross_usdc - swap1_usdc - ret_usdc - swap2_usdc) < 0.01
# USDC -> ETH-equivalent at the vault's own cost-recovery swap rate (3 min before the return). Not a market oracle.
rate = eth1 / swap1_usdc
gross_eq, ret_eq = gross_usdc * rate, ret_usdc * rate
bot_net_eq = gross_eq - cb0 - gas0
lend_before = int(J("data/raw/rpc/peap_usdc_bal_3717e340_22874009.json")["result"], 16) / 1e6
lend_after = int(J("data/raw/rpc/peap_usdc_bal_3717e340_22874010.json")["result"], 16) / 1e6
assert 463970 < lend_before < 463971 and 115704 < lend_after < 115705
cd = J(f"{D}/call_diff.json")
assert all(v["sequence_identical_after_role_normalisation"] for v in cd["attacker_attempts"].values())
n_calls = cd["yoink"]["n_state_changing_calls"]
assert n_calls == 42
vtx = J("data/raw/etherscan/peap_vault_txlist_22874010_22960000.json")["result"]
reply = next(x for x in vtx if x["blockNumber"] == "22889139")
reply_text = bytes.fromhex(reply["input"][2:]).decode()
assert reply_text.startswith("Frontran 0x277da2D1") and "11.95248" in reply_text
auction10 = bvh.auction_summary(f"{D}/race_22874010.json", Y_TX)
att_list = J("data/raw/etherscan/peap_att_txlist.json")["result"]
att_ts = {x["hash"]: (int(x["blockNumber"]), int(x["transactionIndex"]), x["isError"], x["timeStamp"]) for x in att_list}
for b, h in ATT_TXS.items():
    assert att_ts[h][0] == b
att_attack_txs = [{"hash": h, "block": att_ts[h][0], "index": att_ts[h][1], "status": "success",
                   "role": {22873986: "attack 1 on pair 1 (WETH market): +78.1864 ETH, outside this row's scope",
                            22874007: "attempt on pair 2 (USDC market): pair-2 leg reverted inside try/catch, no profit",
                            22874008: "attempt on pair 2: same, no profit", 22874009: "attempt on pair 2: same, no profit; last attempt before Yoink",
                            22874015: "attempt after Yoink: 'zero token' (opportunity gone), no profit",
                            22874016: "attempt after Yoink: 'zero token', no profit"}[b]} for b, h in ATT_TXS.items()]
BLK10, RC10, TB10 = "data/raw/rpc/block_22874010.json", "data/raw/rpc/receipts_22874010.json", "data/raw/rpc/trace_block_22874010.json"
Y_TRACE = f"data/raw/rpc/peap_trace_{Y_TX}.json"
VT, VI, VTX = "data/raw/etherscan/peap_vault_tokentx_22874000_22960000.json", "data/raw/etherscan/peap_vault_txlistinternal_22874010_22960000.json", "data/raw/etherscan/peap_vault_txlist_22874010_22960000.json"
ATTL = "data/raw/etherscan/peap_att_txlist.json"
MD = ["data/raw/mempool-dumpster/2025-07-08.csv.zip", "data/raw/mempool-dumpster/2025-07-08_sourcelog.csv.zip"]
refs1 = {
    "bot.block": [BLK10], "bot.position": [BLK10, RC10], "attacker_block": [ATTL, "data/raw/rpc/block_hdr_22874010.json"],
    "loot.gross_loot_eth": [VT, VI], "loot.coinbase_paid_eth": [Y_TRACE, TB10], "loot.priority_fee_paid_eth": [RC10, BLK10],
    "loot.builder_refund_to_bot_eth": [BLK10, TB10], "loot.bot_net_eth": [VT, VI, Y_TRACE, RC10], "loot.captured_usd": [VT],
    "fate.returned_by_bot_eth": [VT, VI], "fate.returned_total_eth": [VT, VI], "fate.bounty_kept_eth": [VT, VI],
    "fate.kept_by_bot_eth": [VT, VI], "evidence_level_mempool": MD,
    "loot.captured_native": [VT], "fate.returned_usdc": [VT], "fate.cost_recovery_sale": [VT, VI],
    "call_diff": [f"data/raw/rpc/peap_trace_{Y_TX}.json"] + [f"data/raw/rpc/peap_trace_{h}.json" for b, h in ATT_TXS.items() if 22874007 <= b <= 22874009],
    "lender_vault_drain": ["data/raw/rpc/peap_usdc_bal_3717e340_22874009.json", "data/raw/rpc/peap_usdc_bal_3717e340_22874010.json"],
    "counterfactual_sim": ["data/raw/rpc/peap_simA_22874009.json", "data/raw/rpc/peap_simA_22874010.json", "data/raw/rpc/peap_simA_22874014.json"],
    "press": ["data/raw/web-peapods/quadriga_peapods.html"],
}
row1 = {
    "slug": SLUG, "sub": "second-attempt",
    "name": "Peapods Finance: Yoink's USDC-market exploit after the attacker's three failed attempts",
    "date_utc": race10["block"]["timestamp_utc"].replace("+00:00", "Z"), "chain": "ethereum",
    "orig_verdict": "related-not-frontrun",
    "race_type_proposed": "post-failure-replay",
    "race_type_reason": (f"The attacker's three pair-2 attempts (blocks 22874007-09) had already landed and each reverted inside its try/catch; Yoink's tx (22874010 idx 0, 12 s later) made the same {n_calls} state-changing calls "
                         "(role-normalised, similarity 1.0, same 10M USDC Morpho loan, same swap sizes) and its borrow passed. No attacker tx is shown pending, and the attacker's calldata on the pre-Yoink state still reverts."),
    "one_liner": ("After the attacker's pair-1 exploit (+78.19 ETH) and three reverted pair-2 attempts, Yoink replayed the same 42-call recipe one block later and took 174,258 USDC with an 11.49 ETH bribe; "
                  "it returned 126,892 USDC (90% after cost). No pending attacker tx is shown."),
    "attacker": {"eoa": ATT_EOA, "eoas": [ATT_EOA], "contracts": [ATT_C],
                 "funding": f"0.3896 ETH internal transfer from contract 0xe7351fd7 at block 22872913 (source unlabelled)",
                 "funding_tx": inc["attacker"]["funding_tx"], "deploy_tx": inc["attacker"]["deploy_tx"], "deploy_block": inc["attacker"]["deploy_block"],
                 "attack_txs": att_attack_txs},
    "bot": {"label": "Yoink", "eoa": YOINK, "contract": BOT, "tx": Y_TX, "block": 22874010, "position": 0, "status": "success", "priority_fee_gwei": 0.0},
    "bots_other": [
        {"label": "Yoink (same bot, 2nd tx)", "eoa": YOINK, "tx": Y_TX1, "block": 22874010, "position": 1, "status": "success",
         "role": "post-exploit Curve/pxETH arbitrage of the prices tx0 moved; 0.4800 ETH to coinbase"},
        {"label": "Yoink (same bot, 3rd tx)", "eoa": YOINK, "tx": Y_TX2, "block": 22874010, "position": 2, "status": "success",
         "role": "small generic arbitrage; 0.0133 ETH to coinbase"}],
    "evidence_level_mempool": "absent-from-archive",
    "mempool_note": ("mempool-dumpster covers 2025-07-08 (csv and sourcelog); none of the attacker's txs or Yoink's tx0 appears in it (private flow or missed; the archive held 44% / 65% of the txs in sampled blocks 22873986 / 22874007). "
                     "Unknown is not none: nothing can be said about whether an attacker tx was pending."),
    "trigger": {"kind": "attack-tx", "tx": ATT_TXS[22874009], "first_seen_utc_ms": None, "first_seen_utc": None, "sources": None,
                "note": "Not a measured trigger. The most recent on-chain attacker pair-2 attempt before Yoink was 22874009 (12 s earlier, reverted internally). Auction timeline: first large bid (4.91 ETH, beaverbuild) 6.1 s after that block was sealed, so the trigger could be that tx or the bot's own watch of the Peapods pairs; unknown."},
    "attacker_block": 22874009,
    "attacker_block_note": "Last attacker pair-2 attempt (landed, reverted internally). Earlier success: pair 1 at 22873986 idx 4 (+78.1864 ETH), which Phalcon labels the 'Attack Transaction'.",
    "attacker_reference": {"kind": "attack-tx", "block": 22874009, "tx": ATT_TXS[22874009]},
    "auction": auction10,
    "loot": {
        "scope": "bot-tx",
        "gross_loot_eth": round(gross_eq, 6),
        "gross_loot_method": f"ETH-equivalent of 174,258.313813 USDC at the Yoink vault's own cost-recovery swap rate on 2025-07-10 ({swap1_usdc:,.2f} USDC -> {eth1} ETH, tx {swap1['hash'][:10]}, 3 min before the return); not a market oracle. The take itself is USDC.",
        "captured_native": {"amount": f"{gross_usdc:.6f}", "unit": "USDC", "desc": "borrowAsset on Peapods/Fraxlend pair 0xca1154bb (516,065.925 USDC borrowed, loan repaid inside the tx); 174,258.313813 USDC swept to the Yoink vault 0xc70f00cd"},
        "captured_usd": round(gross_usdc, 2), "captured_usd_source": "USDC treated as $1",
        "coinbase_paid_eth": round(cb0, 12),
        "priority_fee_paid_eth": prio0,
        "builder_refund_to_bot_eth": 0.0,
        "builder_payout_to_victim_eth": None,
        "bot_net_eth": round(bot_net_eq, 6),
        "loot_note": (f"Scope is tx0. bot_net = gross (ETH-equivalent) - tx0 coinbase ({cb0:.4f}) - gas ({gas0:.5f}); priority fee 0 and no builder refund (block has 3 Yoink txs + the proposer payment). "
                      f"Coinbase paid by all three Yoink txs in the block is {cb_blk:.4f} ETH (builder paid the proposer {prop_pay:.4f}); Yoink's own message says it paid 11.95248 ETH, which differs from the measured 11.9877 by 0.0352 ETH (unreconciled). "
                      "tx1's arbitrage profit is not credited here."),
    },
    "fate": {
        "return_status": "returned",
        "returned_by_bot_eth": round(ret_eq, 6), "returned_by_builder_eth": None, "returned_total_eth": round(ret_eq, 6),
        "returned_usdc": ret_usdc,
        "returned_to": f"Peapods team address {TEAM} (the address that messaged the bot and attacker)",
        "returned_desc": (f"2025-07-10: Peapods offered a 10% white-hat bounty (tx 0xf24a9464, block 22888679). The Yoink vault replied on chain (tx {reply['hash'][:10]}): '{reply_text[:140]}...'. It sold {swap1_usdc:,.2f} USDC for {eth1} ETH (cost recovery), "
                          f"then sent {ret_usdc:,.2f} USDC to the team (tx {ret['hash'][:10]}, block 22889167) = exactly 90% of the remaining {gross_usdc - swap1_usdc:,.2f} USDC; {ret_usdc / gross_usdc * 100:.1f}% of the gross take. "
                          "returned_*_eth are ETH-equivalents at the cost-recovery swap rate; the real return was in USDC (returned_usdc)."),
        "bounty_kept_eth": eth2, "bounty_desc": f"{swap2_usdc:,.2f} USDC (10% of the post-cost amount) kept, sold for {eth2} ETH on 2025-07-16 (tx {swap2['hash'][:10]})",
        "kept_by_bot_eth": eth2,
        "returned_txs": [{"tx": ret["hash"], "usdc": ret_usdc, "block": 22889167, "time_utc": iso(ret["timeStamp"]), "note": "vault -> Peapods team address"},
                         {"tx": swap1["hash"], "usdc": swap1_usdc, "eth_received": eth1, "block": 22889148, "note": "cost-recovery sale (not a return)"},
                         {"tx": swap2["hash"], "usdc": swap2_usdc, "eth_received": eth2, "block": 22928685, "note": "bounty sale (not a return)"}],
        "public_statement": "on-chain messages: Peapods (tx 0xf24a9464, 0xf051e900, thanks 0xd49d8e52) and the Yoink vault reply (0xa1856637); BlockSec/Phalcon via Quadriga calls tx0 'Second Transaction Which Was Front-run'.",
    },
    "raw_refs": refs1,
    "rawref_gaps": [
        {"field": "trigger.first_seen_utc_ms", "why": "neither side's txs are in mempool-dumpster; no trigger measured"},
        {"field": "attacker revert cause", "why": "pair-2 borrowAsset reverts with custom error 0xed27783c(uint256) (arg = borrow + 1 unit); the attacker contract and the pair's error are not decoded from verified source"},
        {"field": "fate.returned_*_eth / loot.gross_loot_eth", "why": "USDC amounts converted at the vault's own swap rate, not a market price feed"},
    ],
    "discrepancies": [
        "Phalcon/BlockSec (via Quadriga) and Peapods' thank-you message say Yoink front-ran the attacker's second attempt; on-chain the attacker's pair-2 attempts had already landed and failed before Yoink's tx, and none of them was pre-empted.",
        "Press loss figure (~$200k, ~78 ETH) is the attacker's pair-1 take; Yoink's 174,258 USDC from pair 2 is additional (lender vault 0x3717e340 fell from 463,970.31 to 115,704.36 USDC in this block).",
        f"Yoink's stated cost of winning the block (11.95248 ETH) vs measured coinbase total {cb_blk:.5f} ETH.",
    ],
    "evidence_notes": [
        f"incidents/{SLUG}/call_diff.json: the attacker's blocks 22874007/08/09 pair-2 callbacks equal Yoink's 42 state-changing calls role-for-role (ratio 1.0); borrow sizes differ at the 7th digit (attacker 516,041.99 / 516,065.93 / 516,041.99 vs Yoink 516,065.925 USDC).",
        "debug_traceCall of the attacker's calldata on the state after 22874009 (just before Yoink) still reverts in borrowAsset; on the state after 22874010 and 22874014 it stops at 'zero token'. So Yoink did exhaust the opportunity, but the attacker's own tx was not shown to succeed without it.",
        f"Auction (slot {race10['block']['slot']}): winning builder 'I can haz block?' via Flashbots, 12.4423 ETH to the proposer; first >4 ETH bid appears 6.1 s after the attacker's last attempt block.",
        "Bribe rule: msg.value 114944269 (>=1000) is a fixed bribe of v x 1e11 wei = 11.4944269 ETH, equal to the coinbase transfer in the trace.",
    ],
    "incident_dir": D,
}

# ============================================================ row 2: 07-09 follow-up (rejected)
race9 = J(f"{D}/race_22883324.json")
tx9 = {t["hash"]: t for t in race9["txs"]}
j9 = tx9[JUL9_TX]
assert j9["index"] == 1 and j9["from"] == YOINK and j9["status"] == 1
yoink_idx = [t["index"] for t in race9["txs"] if t["from"] == YOINK]
BLK9, RC9, TB9 = "data/raw/rpc/block_22883324.json", "data/raw/rpc/receipts_22883324.json", "data/raw/rpc/trace_block_22883324.json"
auction9 = bvh.auction_summary(f"{D}/race_22883324.json", JUL9_TX)
row2 = {
    "slug": SLUG, "sub": "07-09-followup",
    "name": "Peapods Finance: Yoink txs of 2025-07-09 (block 22883324), rejected",
    "date_utc": race9["block"]["timestamp_utc"].replace("+00:00", "Z"), "chain": "ethereum",
    "orig_verdict": "rejected",
    "race_type_proposed": "late-copy",
    "race_type_reason": "Placeholder value for the schema; the row is rejected (verdict rejected, race_type no-race in the rules file). Yoink's 36 txs in block 22883324 touch none of 102 Peapods-specific addresses (pairs, vaults, pods, leverage manager, team admin targets); no attacker or user Peapods tx is in or before the block to copy.",
    "one_liner": "A 2025-07-09 Yoink lead for Peapods: the block holds 36 Yoink txs (idx 1-4 the big ones) but none touches any of 102 Peapods addresses; the txs are stablecoin-pool arbitrage. Rejected: not a Peapods capture.",
    "attacker": {"eoa": None, "eoas": [], "contracts": [], "funding": "n/a", "funding_tx": None, "deploy_tx": None, "deploy_block": None, "attack_txs": [],
                 "none_reason": "No attacker: the Peapods attacker's last tx was 2025-07-08 and no Peapods exploit tx exists in this block."},
    "bot": {"label": "Yoink", "eoa": YOINK, "contract": j9["to"].lower(), "tx": JUL9_TX, "block": 22883324, "position": 1, "status": "success", "priority_fee_gwei": j9["priority_fee_gwei"], "n_txs": len(yoink_idx)},
    "bots_other": [],
    "evidence_level_mempool": "absent-from-archive",
    "mempool_note": "mempool-dumpster covers 2025-07-09 (csv and sourcelog); Yoink's tx idx 1 is not in it. Irrelevant to the verdict: nothing Peapods-related is in the block.",
    "trigger": {"kind": None, "tx": None, "first_seen_utc_ms": None, "first_seen_utc": None, "sources": None, "note": "No trigger: not a Peapods event."},
    "attacker_block": None,
    "attacker_block_note": "No attacker tx.",
    "attacker_reference": {"kind": "none", "block": None, "tx": None},
    "auction": auction9,
    "loot": {"scope": "not-peapods", "gross_loot_eth": None, "gross_loot_method": None, "captured_native": None, "captured_usd": None, "captured_usd_source": None,
             "coinbase_paid_eth": None, "priority_fee_paid_eth": None, "builder_refund_to_bot_eth": None, "builder_payout_to_victim_eth": None, "bot_net_eth": None,
             "loot_note": "Not computed: the block is ordinary Yoink arbitrage and not part of the Peapods incident. (Yoink tx idx 1 paid 8.57 ETH to the coinbase on its own arbitrage; unrelated.)"},
    "fate": {"return_status": "not-applicable", "returned_by_bot_eth": None, "returned_by_builder_eth": None, "returned_total_eth": None, "returned_to": None,
             "returned_desc": "Nothing to return: no Peapods funds involved.", "bounty_kept_eth": None, "bounty_desc": None, "kept_by_bot_eth": None, "returned_txs": [], "public_statement": None},
    "raw_refs": {"bot.block": [BLK9], "bot.position": [BLK9, RC9], "evidence_level_mempool": ["data/raw/mempool-dumpster/2025-07-09.csv.zip", "data/raw/mempool-dumpster/2025-07-09_sourcelog.csv.zip"],
                 "touch_check": [TB9]},
    "rawref_gaps": [{"field": "touch_check", "why": "102 Peapods addresses compared with every address in block 22883324's call traces; the address list is in incident.json notes / this script's run, built from the team-admin call targets and the July trace addresses minus common infrastructure"}],
    "discrepancies": ["Yoink's own messages dated the Peapods incident 2025-07-09 in the lead list; the on-chain Peapods event is 2025-07-08 (block 22874010) and its return was agreed on 2025-07-10."],
    "evidence_notes": [
        f"Yoink txs in block 22883324 at indexes {yoink_idx[:6]}...; the block was built by 'I can haz block?' (18.6 ETH bid, Ultrasound); idx 1's calls are USDC/USDT/PYUSD and pool operations (stablecoin-pool arbitrage), not Peapods contracts.",
    ],
    "incident_dir": D,
}

# ============================================================ row 3: October leftover (Yoink sweep of a stranded USDC balance)
race_o = J(f"{D}/race_23540182.json")
to_ = {t["hash"]: t for t in race_o["txs"]}
o0 = to_[OCT_TX]
assert o0["index"] == 0 and o0["status"] == 1 and o0["from"] == YOINK
OBOT = o0["to"].lower()
refund_tx = next(t for t in race_o["txs"] if t["index"] == 1)
assert refund_tx["from"].lower() == race_o["block"]["fee_recipient"].lower() and refund_tx["to"].lower() == OBOT
o_cb = int(o0["coinbase_transfer_wei"]) / E18
o_ref = int(refund_tx["value_wei"]) / E18
o_in, o_out, o_dep = tx_flows(OCT_TX, OBOT)
assert abs(o_dep - 0.2339383300) < 1e-9
o_gross = o_in - o_dep          # proceeds net of the 0.2339 ETH the tx itself wrapped into WETH
o_gas = o0["gas_used"] * o0["gas_price_gwei"] / 1e9
o_net = o_gross - o_cb + o_ref - o_gas
oret = next(x for x in J("data/raw/etherscan/peap_peateam_txlist_22800000.json")["result"] if x["hash"] == OCT_RET)
o_returned = int(oret["value"]) / E18
assert abs(0.9 * o_net - o_returned) < 1e-4, (o_net, o_returned)
lm_before = int(J("data/raw/rpc/peap_usdc_bal_LM_23540181.json")["result"], 16) / 1e6
lm_after = int(J("data/raw/rpc/peap_usdc_bal_LM_23540182.json")["result"], 16) / 1e6
assert abs(lm_before - 8957.748779) < 1e-6 and lm_after == 0
auction_o = bvh.auction_summary(f"{D}/race_23540182.json", OCT_TX)
BLKo, RCo, TBo = "data/raw/rpc/block_23540182.json", "data/raw/rpc/receipts_23540182.json", "data/raw/rpc/trace_block_23540182.json"
O_TRACE = f"data/raw/rpc/peap_trace_{OCT_TX}.json"
OTEAM = "data/raw/etherscan/peap_peateam_txlist_22800000.json"
LMB = ["data/raw/rpc/peap_usdc_bal_LM_23540181.json", "data/raw/rpc/peap_usdc_bal_LM_23540182.json"]
user_tx = J(f"data/raw/rpc/peap_tx_{OCT_USER}.json")["result"]
assert int(user_tx["blockNumber"], 16) == 23540172 and int(user_tx["transactionIndex"], 16) == 1
user_blk_ts = int(J("data/raw/rpc/peap_blkhdr_23540172.json")["result"]["timestamp"], 16)
row3 = {
    "slug": SLUG, "sub": "oct-leftover",
    "name": "Peapods Finance: Yoink sweeps a user's stranded 8,957 USDC from the LeverageManager (2025-10-09)",
    "date_utc": race_o["block"]["timestamp_utc"].replace("+00:00", "Z"), "chain": "ethereum",
    "orig_verdict": "related-not-frontrun",
    "race_type_proposed": "bot-was-first-exploiter",
    "race_type_reason": ("A user's removeLeverage tx (block 23540172) left 8,957.748779 USDC in the LeverageManager. Yoink swept it 10 blocks (~2 min) later via a different function, first and alone; "
                         "there is no attacker and no pending tx to beat. It is a first-sweeper case with a good-faith return, not a race."),
    "one_liner": ("A user's removeLeverage left 8,957.75 USDC in the Peapods LeverageManager; Yoink swept it 10 blocks later (idx 0, 1.80 ETH coinbase, builder refund 1.57 ETH) and returned 1.4163 ETH, 90% of its net. No attacker; not a race."),
    "attacker": {"eoa": None, "eoas": [], "contracts": [], "funding": "n/a", "funding_tx": None, "deploy_tx": None, "deploy_block": None, "attack_txs": [],
                 "none_reason": "No attacker: the leftover was created by an ordinary user's removeLeverage tx; Yoink was the first to sweep it."},
    "bot": {"label": "Yoink", "eoa": YOINK, "contract": OBOT, "tx": OCT_TX, "block": 23540182, "position": 0, "status": "success", "priority_fee_gwei": 0.0},
    "bots_other": [{"label": "other sweeper (NOT Yoink)", "eoa": "0x095308cba8df44b1f2abfd01335ce410fc63a23f", "tx": "0x08a4a6906eaa798fa23fccdebbee4d1b59655d91874cbdcb2af99294d0fc3ea5", "block": 23540671, "position": 4, "status": "success",
                    "role": "swept a separate 39,452.26 USDC leftover from user removeLeverage 0x17e0086c (block 23540670); Peapods messaged this address too. Not part of Yoink's row."}],
    "evidence_level_mempool": "absent-from-archive",
    "mempool_note": "mempool-dumpster covers 2025-10-09 (csv); Yoink's tx is not in it (private flow). The user's tx 0x60b2c65c is the on-chain trigger; whether Yoink saw it pending is unknown.",
    "trigger": {"kind": "user-tx", "tx": OCT_USER, "first_seen_utc_ms": None, "first_seen_utc": None, "sources": None,
                "note": f"User removeLeverage tx {OCT_USER[:10]} landed at block 23540172 idx 1 ({iso(user_blk_ts)}); Yoink's sweep is 10 blocks later. Nothing shows Yoink replayed the user's calldata: it called a different LeverageManager function (0x8bf0f8f8)."},
    "attacker_block": None,
    "attacker_block_note": "No attacker; the user tx that stranded the funds is block 23540172.",
    "attacker_reference": {"kind": "user-tx", "block": 23540172, "tx": OCT_USER},
    "auction": auction_o,
    "loot": {
        "scope": "bot-tx",
        "gross_loot_eth": round(o_gross, 12),
        "gross_loot_method": f"ETH received by the Yoink contract in the tx trace ({o_in:.6f}) minus the {o_dep:.6f} ETH the tx itself wrapped into WETH.deposit; the take is the 8,957.748779 USDC left in the LeverageManager, sold inside the tx",
        "captured_native": {"amount": f"{lm_before:.6f}", "unit": "USDC", "desc": "USDC balance of LeverageManager 0x4e6ef371 before the tx (eth_call balanceOf at block 23540181), 0 after"},
        "captured_usd": round(lm_before, 2), "captured_usd_source": "USDC treated as $1",
        "coinbase_paid_eth": round(o_cb, 12),
        "priority_fee_paid_eth": int(o0["priority_fee_total_wei"]) / E18,
        "builder_refund_to_bot_eth": round(o_ref, 12),
        "builder_payout_to_victim_eth": None,
        "bot_net_eth": round(o_net, 12),
        "loot_note": f"Scope is the single Yoink tx. bot_net = gross - coinbase + builder refund - gas ({o_gas:.6f} ETH at {o0['gas_price_gwei']} gwei). The block has 3 txs: Yoink idx 0, the builder's refund idx 1 ({o_ref:.4f} ETH to the bot contract) and the proposer payment idx 2. "
                     f"Coinbase msg.value 999 (per mille rule) = {o_cb:.4f} ETH; the refund returned most of it, so the bot ended with {o_net:.4f} ETH. Gross is the measured ETH received by the bot contract in the trace ({o_in:.4f}) minus the {o_dep:.4f} ETH the tx wrapped into WETH; Yoink's own return (1.416285 ETH) is exactly 90% of the net computed this way, which supports treating the wrapped amount as a cost. The ETH value of the 8,957.75 USDC is not separately priced.",
    },
    "fate": {
        "return_status": "returned",
        "returned_by_bot_eth": o_returned, "returned_by_builder_eth": None, "returned_total_eth": o_returned,
        "returned_to": f"Peapods team address {TEAM}",
        "returned_desc": f"Peapods messaged Yoink on 2025-10-09 16:43:59Z (tx 0x0a5694d3, block 23541447: 'we see you were able to fetch the ~2 ETH leftover ... from a previous user's tx'). Yoink returned {o_returned} ETH at 17:46:23Z (tx {OCT_RET[:10]}, block 23541758) with the message 'Returning profits minus 10% bounty': {o_returned / o_net * 100:.2f}% of its {o_net:.4f} ETH net.",
        "bounty_kept_eth": round(o_net - o_returned, 12), "bounty_desc": "10% of Yoink's net by agreement in the Peapods message", "kept_by_bot_eth": round(o_net - o_returned, 12),
        "returned_txs": [{"tx": OCT_RET, "eth": o_returned, "block": 23541758, "time_utc": iso(oret["timeStamp"]), "note": "Yoink -> Peapods team address, message 'Returning profits minus 10% bounty'"}],
        "public_statement": "on-chain message from Peapods (tx 0x0a5694d3) and Yoink's return message (tx 0xcd6d475f).",
    },
    "raw_refs": {"bot.block": [BLKo], "bot.position": [BLKo, RCo], "loot.gross_loot_eth": [O_TRACE], "loot.coinbase_paid_eth": [O_TRACE, TBo],
                 "loot.priority_fee_paid_eth": [RCo, BLKo], "loot.builder_refund_to_bot_eth": [BLKo, TBo], "loot.bot_net_eth": [O_TRACE, BLKo, RCo],
                 "loot.captured_usd": LMB, "loot.captured_native": LMB, "fate.returned_by_bot_eth": [OTEAM], "fate.returned_total_eth": [OTEAM],
                 "fate.bounty_kept_eth": [OTEAM, O_TRACE], "fate.kept_by_bot_eth": [OTEAM, O_TRACE],
                 "evidence_level_mempool": ["data/raw/mempool-dumpster/2025-10-09.csv.zip"],
                 "trigger": [f"data/raw/rpc/peap_tx_{OCT_USER}.json", "data/raw/rpc/peap_blkhdr_23540172.json"]},
    "rawref_gaps": [{"field": "trigger.first_seen_utc_ms", "why": "Yoink's tx and the user's tx are not in mempool-dumpster for 2025-10-09; no first-seen time"},
                    {"field": "other sweeper", "why": "the 39,452 USDC sweep by 0x095308cb (block 23540671) is not Yoink and is excluded from this row"}],
    "discrepancies": ["Peapods' message says '~2 ETH leftover'; the leftover was 8,957.75 USDC and Yoink's gross trace proceeds were 2.04 ETH (1.81 ETH net of its own WETH wrap), of which most was paid to the coinbase and then refunded by the builder."],
    "evidence_notes": ["The leftover existed for 10 blocks; a Yoink tx at idx 0 of the next sweepable block took it. The user's removeLeverage (0xc359770d) and Yoink's call (0x8bf0f8f8) are different entry points, so this is not calldata replay.",
                       "Yoink's other Oct txs (23541082 idx 0, 23541094 idx 2) are generic arbitrage/liquidation and are not part of this row."],
    "incident_dir": D,
}

out = ROOT / "data" / "extract" / f"{SLUG}.json"
json.dump([row1, row2, row3], open(out, "w"), indent=1)
print("wrote", out, "| row1 gross_eq", round(gross_eq, 4), "ret_eq", round(ret_eq, 4), "bot_net_eq", round(bot_net_eq, 4), "cb0", cb0, "cb_blk", cb_blk, "rate", rate,
      "| row3 gross", round(o_gross, 6), "net", round(o_net, 6), "returned", o_returned, "cb", o_cb, "ref", o_ref)
