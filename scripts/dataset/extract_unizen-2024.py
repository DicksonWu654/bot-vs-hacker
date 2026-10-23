"""Extract rows for unizen-2024 -> data/extract/unizen-2024.json (4 sub-rows). Run from project root:
    .venv/bin/python scripts/dataset/extract_unizen-2024.py
Needs incidents/unizen-2024/{incident.json,yoink_txs.json,calldata_diffs.json,mempool_key.json,exploit_txs.json,race_*.json}
(written by scripts/p2_unizen_scan.py, p2_unizen_build.py, p2_unizen_incident.py and blockrace.py)."""
import sys, pathlib, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _x6 import *  # load, iso, write, bvh, ...
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import rawfetch  # noqa: E402

S = "unizen-2024"
D = f"incidents/{S}"
inc = load(f"{D}/incident.json")
ys = {t["tx"]: t for t in load(f"{D}/yoink_txs.json")["txs"]}
mp = load(f"{D}/mempool_key.json")["txs"]
YOINK = "0xfde0d1575ed8e06fbf36256bcdfa1f359281455a"
BOT = "0x6980a47bee930a4584b09ee79ebe46484fbdbdd0"
A3 = "0x2ad8aed847e8d4d3da52aabb7d0f5c25729d10df"
A4 = "0x4e2ce48f0b5d97bfd4be3f6c7b6479db1aa5b365"
T_ADS = "0x2dfc3752e5efe27590d9a54aaabd4658a1f9d4857c46315b9c9bb37da0622f0a"
T_USDT = "0x4a69a272d0de1aaec34ac3489f5ab156b2a4e98412a25efbeacd93b7aa00b969"
T_XI = "0xbe1ffe49a8b83947bcf91b19825591af8d0a5ce6d498f3e1fb3d20bd98eeea56"
COPIES = ["0x73dad216e383b51c589b943288cb25d03d16b8cf984dcea0fd9dbc336f2da1ad", "0xaeb81988bb0b1bcae375f979f9ecb8146d811b42170a8ebe11467625240178a2",
          "0x14328e299167dea78c7f501c85578a6ef0f34cb30e9af796fcf79faa61d75746", "0xde7b7aedf81ff9eb19cab4139a2771e839900cb8c6c6c0c7dea0149432573437"]
SRC = {"0x73dad216": "0xd0bab3e76a55033e4ef47a8a52bea74313eaea3b04a23adc7c7e416d359bc3a0", "0xaeb81988": None, "0x14328e29": None, "0xde7b7aed": None}
A_ADS = "0x44ca0e6b77d75b63e9969323ad4a09509d806e2cc1b812caa001864a5c89ba88"
A_ADS_BAD = "0x143329584d01e998e1b6c32b3a3fbcb9801245354df53b366efb72aa6151ff59"
A_USDT = "0xba300ca5d3239e109295f4412bc856687c60163537b5264c4b0aa372042e5b44"
A_XI_FOLLOW = "0x7234dfac08015dd1a71cf1e831a3a720ed7d3be9e98d38c606b443b6ee8c8b87"
RET_ETH = "0x4f647c4d74a86e5f3719b235e96f55000a04df1e07137eed8baef09dd0c2c074"
RET_ETH_BAD = "0xd06abff5e994e14fa82a4ca0f62e3d799529c7426218d5c6c1a937557818de7c"
RET_USDT = "0xb3482ffed5d6251adebb3ab572bcf1f588775e7c8443506f05557dbf9504521c"
RET_USDC = "0xdac41e4153243240f864656f391736b7d169bce9018c0543019b142b4f8b1def"
MPZ = ["data/raw/mempool-dumpster/2024-03-08.csv.zip", "data/raw/mempool-dumpster/2024-03-08_sourcelog.csv.zip"]
PRICE_F = "data/raw/defillama/unizen_eth_1709935800.json"
ETHP = load(PRICE_F)["coins"]["coingecko:ethereum"]["price"]
scan = {t["hash"]: t for t in load(f"{D}/exploit_txs.json")["txs"]}


def full(prefix):
    return next(h for h in scan if h.startswith(prefix))


def rc_status(h):
    r = rawfetch.rpc("eth_getTransactionReceipt", [h], key=f"rcpt_{h}", source="rpc")
    return "success" if r and r.get("status") == "0x1" else "reverted"


def blkrefs(b):
    return [f"data/raw/rpc/block_{b}.json", f"data/raw/rpc/receipts_{b}.json", f"data/raw/rpc/trace_block_{b}.json"]


def agg(txs):
    g = {"eth": 0, "cb": 0, "rf": 0, "gas": 0, "prio": 0}
    for h in txs:
        y = ys[h]
        g["eth"] += y["weth_withdraw_to_bot_wei"]; g["cb"] += y["coinbase_transfer_wei"]; g["rf"] += y["builder_refund_wei"] or 0
        g["gas"] += y["gas_used"] * y["effective_gas_price_wei"]; g["prio"] += y["gas_used"] * y["max_priority_fee_wei"]
    return {k: v / 1e18 for k, v in g.items()}


def stables(txs):
    out = {"USDT": 0, "USDC": 0}
    for h in txs:
        for s in ys[h]["sweeps"]:
            if s["to"] == "0xc70f00cd7e461686b04b0e912e309beca8b80ea0":
                if s["token"].startswith("0xdac17f"): out["USDT"] += s["amount_raw"] / 1e6
                if s["token"].startswith("0xa0b869"): out["USDC"] += s["amount_raw"] / 1e6
    return out


def mem(h):
    m = mp.get(h)
    return m


def bot_obj(h):
    y = ys[h]
    return {"label": "Yoink", "eoa": YOINK, "contract": BOT, "tx": h, "block": y["block"], "position": y["index"],
            "status": "success" if y["status"] == 1 else "reverted", "priority_fee_gwei": y["max_priority_fee_wei"] / 1e9}


def other_yoink(h, role):
    y = ys[h]
    return {"label": "Yoink (same bot, another tx of this incident)", "eoa": YOINK, "tx": h, "block": y["block"], "position": y["index"], "status": "success", "role": role}


# --- incident-wide return facts (Yoink returns 90% of each asset; see fate) ---------------------------------------------------------------
allt = list(ys)
G = agg(allt); ST = stables(allt)
net_all = G["eth"] - G["cb"] + G["rf"] - G["gas"]
ret_eth, ret_usdt, ret_usdc = 0.29808, 12209.11666, 4327.967358
incident_wide = {
    "yoink_net_eth_side": round(net_all, 6), "yoink_usdt": ST["USDT"], "yoink_usdc": ST["USDC"],
    "returned_eth": ret_eth, "returned_usdt": ret_usdt, "returned_usdc": ret_usdc,
    "returned_fraction_each": {"eth": round(ret_eth / net_all, 4), "usdt": round(ret_usdt / ST["USDT"], 4), "usdc": round(ret_usdc / ST["USDC"], 4)},
    "kept": {"eth": round(net_all - ret_eth, 6), "usdt": round(ST["USDT"] - ret_usdt, 6), "usdc": round(ST["USDC"] - ret_usdc, 6)},
    "returned_usd_at_defillama_price": round(ret_eth * ETHP + ret_usdt + ret_usdc, 0), "net_usd_at_defillama_price": round(net_all * ETHP + ST["USDT"] + ST["USDC"], 0),
    "eth_price_usd": ETHP, "scope": "all seven Yoink txs of this incident (not attributable to a single sub-row)"}
FATE_REFS = ["data/raw/etherscan/unizen_recv_txlist.json", "data/raw/etherscan/unizen_recv_tokentx.json", PRICE_F]
fate_common = {
    "return_status": "partial",
    "returned_by_bot_eth": None, "returned_by_builder_eth": None, "returned_total_eth": None,
    "returned_to": "Unizen's address 0x6003327a621fc16c74baf08229cc45a96e44f9ee (named in Unizen's on-chain message 0x0dc8ce3e, block 19403954)",
    "bounty_kept_eth": None, "bounty_desc": "Unizen's message offered a 20% bounty ('send back 80%'); Yoink returned 90% of its net in each asset and kept 10%",
    "kept_by_bot_eth": None,
    "incident_wide": incident_wide,
    "returned_desc": (f"Incident-wide, not split by row (the seven txs share one return): after Unizen's on-chain message (2024-03-10 09:59:35Z) Yoink sent 'Returning 90% of profits' at 20:38:59Z, but that 0.29808 ETH tx {RET_ETH_BAD[:10]} REVERTED (status 0, gas limit 41,511; the recipient is a contract); the resend {RET_ETH[:10]} (block 19407140, 20:40:11Z) succeeded. "
                      f"The vault 0xc70f00cd then sent 12,209.116660 USDT ({RET_USDT[:10]}, 20:41:59Z) and 4,327.967358 USDC ({RET_USDC[:10]}, 20:43:23Z). That is 90.0% of the 7-tx net in each asset (ETH net {net_all:.6f}, USDT {ST['USDT']:.6f}, USDC {ST['USDC']:.6f}); about ${incident_wide['returned_usd_at_defillama_price']:,.0f} of ${incident_wide['net_usd_at_defillama_price']:,.0f}. "
                      "Yoink refused more (message 0x4840a6a4: 'claw that back from the validators'); the bribe claim is supported for block 19393223 (proposer received 2.4507 ETH) but 3.80 ETH of coinbase payments across the seven blocks came back as builder refunds."),
    "returned_txs": [
        {"tx": RET_ETH, "eth": ret_eth, "note": "Yoink EOA -> Unizen 0x6003327a, 0.29808 ETH (resend; first attempt reverted)", "block": 19407140, "time_utc": "2024-03-10T20:40:11Z"},
        {"tx": RET_ETH_BAD, "eth": None, "note": "first 0.29808 ETH attempt with the message 'Returning 90% of profits': REVERTED, moved nothing", "block": 19407134, "time_utc": "2024-03-10T20:38:59Z"},
        {"tx": RET_USDT, "eth": None, "note": "Yoink vault -> Unizen, 12,209.116660 USDT (not ETH-priced)", "block": 19407149, "time_utc": "2024-03-10T20:41:59Z"},
        {"tx": RET_USDC, "eth": None, "note": "Yoink vault -> Unizen, 4,327.967358 USDC (not ETH-priced)", "block": 19407156, "time_utc": "2024-03-10T20:43:23Z"}],
    "public_statement": "Unizen messages (on-chain, 2024-03-10/11/12): offer of a 20% bounty; the 2024-03-12 message lists exactly these seven Yoink txs ('7 unauthorized transactions') and asks for the remaining ~4,640 USDC/USDT. Yoink 2024-03-12: 'I see 7 txs with an overall profit to me of 0.33 Eth, 13566 USDT, and 4809 USDC', which our trace arithmetic reproduces (0.3312 ETH, 13,565.69 USDT, 4,808.85 USDC)."}
fate_refs = {"fate.return_status": FATE_REFS, "fate.incident_wide": FATE_REFS, "returns_messages": "research/lineages/yoink_messages.json"}

DISC_COMMON = [
    "research/lineages/yoink_messages.json lists 'returned: 0.29808 ETH, tx 0xd06abff5...' but that tx reverted (status 0); the ETH actually arrived in tx 0x4f647c4d... six blocks later.",
    "DeFiHackLabs (UnizenIO, UnizenIO2) presents attacker 0x2ad8aed8 as 'the' attacker with ~$2M; its 78 txs are mostly small pulls, and the ~$2.18M USDT came from a different EOA (0xb660cae1, one tx at 19392761). The PoCs fork at 19393360/19393769 only to reproduce single txs of that attacker (VRA, DMTR).",
    "research/lineages/yoink_more_incidents.json treats 'UnizenIO2 attacker block 19393361' as the reference; Yoink's first tx (19393223) is 138 blocks before it, and its last (19393726) is 365 blocks before UnizenIO's block 19393770.",
]


def row_common(sub, name, tx, rtype, rreason, one):
    y = ys[tx]
    return {"slug": S, "sub": sub, "name": name, "date_utc": y["time_utc"], "chain": "ethereum", "race_type_proposed": rtype, "race_type_reason": rreason, "one_liner": one,
            "bot": bot_obj(tx)}


rows = []

# ======================================================================= pending-ads
y = ys[T_ADS]; g = agg([T_ADS])
mm = mem(A_ADS); mb = mem(A_ADS_BAD)
a = bvh.auction_summary(f"{D}/race_19393726.json", T_ADS)
det = bvh.detection(f"{D}/race_19393726.json", mm["first_seen_ms"], T_ADS)
r = row_common("pending-ads", "Unizen TradeAggregator - Yoink vs 0x13a99ecc's pending ADS pull (Ethereum)", T_ADS, "beat-pending-attack",
    "Yoink's tx (block 19393726, index 0) calls the proxy with the same 23 calldata words as the pending public tx 0x44ca0e6b of 0x13a99ecc except the recipient word; that tx (first seen 23:39:57.990Z, 1,010 ms before the slot) landed one block later (19393727, index 53) and reverted because 7,800 of the victim's 7,801.93 ADS were gone.",
    "Yoink took 7,800 ADS at block 19393726 (index 0), calling the Unizen proxy with the pending public tx's calldata except the recipient, 1.0 s before the slot; the attacker's tx landed next block and reverted. Net +0.273 ETH (coinbase 0.376, builder refund 0.273).")
r.update({
    "orig_verdict": "confirmed-onchain (Yoink beat a still-pending public attacker tx; calldata identical except recipient)",
    "attacker": {"eoa": "0x13a99eccf9f4f1727a6218754b6667aa5113c731", "eoas": ["0x13a99eccf9f4f1727a6218754b6667aa5113c731"], "contracts": [], "funding": "unknown (old active wallet since 2023-12; identity not established)",
                 "funding_tx": None, "deploy_tx": None, "deploy_block": None,
                 "attack_txs": [{"hash": A_ADS_BAD, "block": 19393715, "index": 85, "status": "reverted", "role": "first attempt, nonce 124, input shifted by 4 bytes, public since 23:37:15.017Z, reverted at the proxy"},
                                {"hash": A_ADS, "block": 19393727, "index": 53, "status": "reverted", "role": "well-formed resend, nonce 125 (priority fee 7.26 gwei), public since 23:39:57.990Z, landed one block after Yoink and reverted"}],
                 "none_reason": None,
                 "note": "0x13a99ecc is the sender of the pending tx; its recipient 0x011ee2b5a4ef3e05e11d45a241582ea191a86077 is the recipient of attacker 1's 2.18M USDT tx. Operator identity is not established."},
    "bots_other": [other_yoink(h, "other Yoink tx of the same incident (own sub-row)") for h in (T_USDT, T_XI)],
    "evidence_level_mempool": "measured",
    "mempool_note": "mempool-dumpster 2024-03-08 (6 sources) has the attacker's tx; Yoink's tx is not in it (private flow). First sighting: local node 23:39:57.990Z, chainbound +1 ms, bloxroute +3 ms, eden +6 ms, apool +105 ms, mempoolguru +168 ms.",
    "trigger": {"kind": "attacker-tx", "tx": A_ADS, "first_seen_utc_ms": mm["first_seen_ms"], "first_seen_utc": mm["first_seen_utc"].replace("+00:00", "Z"), "sources": mm["sources"],
                "note": f"The attacker's earlier malformed tx {A_ADS_BAD[:10]} (same victim and amount, public since {mb['first_seen_utc'][11:23]}Z, mined reverted at 19393715) was also visible; the well-formed resend is the one Yoink's call matches word for word (calldata_diffs.json)."},
    "attacker_block": 19393727, "attacker_block_note": "The attacker's tx landed at index 53 of the block after Yoink's (19393727) and reverted.",
    "attacker_reference": {"kind": "attack-tx", "block": 19393727, "tx": A_ADS},
    "auction": a,
    "detection_note": det,
    "loot": {"scope": "bot-tx",
             "gross_loot_eth": round(g["eth"], 6),
             "gross_loot_method": "WETH.withdraw ETH delivered to the Yoink contract in the tx trace after selling 7,800 $ADS (token 0x3106a0a0...) pulled from victim 0x158fb20f",
             "captured_native": {"amount": "7800", "unit": "$ADS", "desc": "7,800 $ADS (18 decimals) pulled from victim 0x158fb20f, sold inside the tx; the victim's remaining balance was 1.929 ADS"},
             "captured_usd": round(g["eth"] * ETHP, 0), "captured_usd_source": f"gross ETH proceeds x DefiLlama ETH price {ETHP:.2f} at 2024-03-08T22:10Z",
             "coinbase_paid_eth": round(g["cb"], 6), "priority_fee_paid_eth": round(g["prio"], 6), "builder_refund_to_bot_eth": round(g["rf"], 6), "builder_payout_to_victim_eth": None,
             "bot_net_eth": round(g["eth"] - g["cb"] + g["rf"] - g["gas"], 6),
             "loot_note": f"gross {g['eth']:.6f} ETH - coinbase {g['cb']:.6f} + builder refund {g['rf']:.6f} (index 14) - gas {g['gas']:.6f} (priority fee 0). The coinbase payment is 98.7% of gross; the builder 'I can haz block?' returned 72.6% of it to the Yoink contract and paid the proposer {eth(y['proposer_payment_wei']):.6f} ETH (index 15)."},
    "fate": {**fate_common},
    "raw_refs": {"bot.block": blkrefs(19393726)[0], "bot.position": blkrefs(19393726)[:2], "attacker_block": blkrefs(19393727)[:2],
                 "trigger.first_seen_utc_ms": MPZ, "evidence_level_mempool": MPZ,
                 "loot.gross_loot_eth": [f"data/raw/rpc/trace_{T_ADS}.json"], "loot.captured_usd": [f"data/raw/rpc/trace_{T_ADS}.json", PRICE_F],
                 "loot.coinbase_paid_eth": [f"data/raw/rpc/trace_{T_ADS}.json", blkrefs(19393726)[2]], "loot.priority_fee_paid_eth": blkrefs(19393726)[:2],
                 "loot.builder_refund_to_bot_eth": blkrefs(19393726)[:2], "loot.bot_net_eth": [f"data/raw/rpc/trace_{T_ADS}.json", *blkrefs(19393726)[:2]],
                 **fate_refs, "calldata_diff": f"{D}/calldata_diffs.json"},
    "rawref_gaps": [{"field": "fate.returned_*", "why": "return is incident-wide (see fate.incident_wide); no per-row split"}],
    "discrepancies": DISC_COMMON,
    "evidence_notes": [
        "calldata_diffs.json: Yoink's proxy call (trace of tx 0x2dfc3752) vs the input of the pending tx 0x44ca0e6b: 23 words, one differs (word 2 = recipient/Info.to: 0x011ee2b5... vs the Yoink contract 0x6980a47b...).",
        f"Race file {D}/race_19393726.json: block 19393726 (23:39:59Z, slot 8593098) built by 'I can haz block?', 16 txs, Yoink index 0, coinbase 0.37629 ETH, builder refund 0.27301 ETH (index 14), proposer payment 0.11376 ETH (index 15). 143 Flashbots bids; winning hash first submitted at +189 ms, i.e. 1,199 ms after the attacker tx was first seen.",
        "Victim balance 7,801.93 ADS (allowance 9,000) at the end of 19393725; 1.93 ADS after Yoink's pull (eth_call archive reads); the attacker's tx in 19393727 reverts at the pull.",
        "Yoink's calldata for the victim contract is the only thing read here (call data into the Unizen proxy); nothing about its own bytecode is used."],
    "incident_dir": D, "bots_other_note": None})
rows.append(r)

# ======================================================================= pending-usdt
y = ys[T_USDT]; g = agg([T_USDT]); st = stables([T_USDT])
mu = mem(A_USDT)
a = bvh.auction_summary(f"{D}/race_19393223.json", T_USDT)
det = bvh.detection(f"{D}/race_19393223.json", mu["first_seen_ms"], T_USDT)
usd = st["USDT"]
r = row_common("pending-usdt", "Unizen TradeAggregator - Yoink vs attacker 4's pending five-wallet USDT tx (Ethereum)", T_USDT, "beat-pending-attack",
    "Attacker 0x4e2ce48f's contract-creation tx 0xba300ca5 (public from 21:52:55.749Z, 3,251 ms before the slot) calls the proxy for five wallets; Yoink's tx at block 19393223 index 0 makes the same-shape proxy calls for the two wallets that still held USDT (8,163.94 + 5,401.75) and the pending tx later landed (19393224, index 80) with all five pulls at 0. Adapted, not byte-copied: recipient and amount words differ.",
    "Yoink took 13,565.69 USDT from the two wallets that a pending public tx of attacker 4 was about to drain (block 19393223, index 0); the attacker's tx landed next block and pulled 0. Yoink paid a flat 3.45 ETH to the coinbase, of which 2.45 reached the proposer.")
r.update({
    "orig_verdict": "confirmed-onchain (Yoink adapted a pending public attacker tx: 2 of its 5 victim calls)",
    "attacker": {"eoa": A4, "eoas": [A4], "contracts": ["0xe617e69a1a0b76bc3a3fd2d993d73faaac427815"], "funding": "EOA 0x4e5b2e1dc63f6b91cb6cd759936495434c7e972f (21:48:23Z, 0.3789 ETH); same funder as attacker 5 0xd440b927; not a known mixer",
                 "funding_tx": "0xc47f156acb386feb201f91be13f483a1abccb6a84ac2cfbea555426219e2748f", "deploy_tx": A_USDT, "deploy_block": 19393224,
                 "attack_txs": [{"hash": "0xf5dd38c76f3bf1c3a71d44fa1fd95536c0c02bf256a807c71d55f4364a980119", "block": 19393216, "index": 38, "status": "reverted", "role": "nonce 0, deploy+call, reverted 'insufficient balance for transfer' before any victim call; public from 21:51:13.461Z"},
                                {"hash": A_USDT, "block": 19393224, "index": 80, "status": "success", "role": "nonce 1: creates the attack contract and calls the proxy for 5 wallets; all five pulls at 0 because the balances were gone (3 drained at 19392761 by attacker 1, 2 by Yoink); landed one block after Yoink"}],
                 "none_reason": None},
    "bots_other": [other_yoink(h, "other Yoink tx of the same incident (own sub-row)") for h in (T_ADS, T_XI)],
    "evidence_level_mempool": "measured",
    "mempool_note": "mempool-dumpster 2024-03-08 has the attacker's tx (bloxroute 21:52:55.749Z, local +14 ms, eden +33 ms, apool +118 ms, mempoolguru +291 ms; included 19393224 after 15,251 ms); Yoink's tx is not in it (private flow).",
    "trigger": {"kind": "attacker-tx", "tx": A_USDT, "first_seen_utc_ms": mu["first_seen_ms"], "first_seen_utc": mu["first_seen_utc"].replace("+00:00", "Z"), "sources": mu["sources"],
                "note": "Slot start 21:52:59Z: the attacker's tx was public 3.25 s before it. Flashbots-relay record bids jump to 2.43 ETH 285 ms after the trigger and the winning builder's step-up to 2.439 ETH comes 443 ms after (detection note)."},
    "attacker_block": 19393224, "attacker_block_note": "The attacker's pending tx landed at index 80 of the block after Yoink's and pulled nothing (calls internally reverted).",
    "attacker_reference": {"kind": "attack-tx", "block": 19393224, "tx": A_USDT},
    "auction": a, "detection_note": det,
    "loot": {"scope": "bot-tx",
             "gross_loot_eth": round(usd / ETHP + g["eth"], 6),
             "gross_loot_method": f"13,565.685175 USDT pulled from two wallets (8,163.939786 + 5,401.745389) valued at DefiLlama ETH price {ETHP:.2f} (2024-03-08T22:10Z); the tx kept the USDT (swept 13,565.685174 to the vault 0xc70f00cd) and sold ~0 ETH worth",
             "captured_native": {"amount": "13565.685175", "unit": "USDT", "desc": "USDT from wallets 0xa340a9fb and 0xa17de4ec, 13,565.685174 swept to the vault"},
             "captured_usd": round(usd, 0), "captured_usd_source": "USDT amount at 1 USD (stablecoin peg assumed)",
             "coinbase_paid_eth": round(g["cb"], 6), "priority_fee_paid_eth": round(g["prio"], 6), "builder_refund_to_bot_eth": round(g["rf"], 6), "builder_payout_to_victim_eth": None,
             "bot_net_eth": round(g["eth"] - g["cb"] + g["rf"] - g["gas"], 6),
             "loot_note": f"ETH side only: the bot paid a flat 3.4521105 ETH (msg.value 34,521,105 x 1e11) from its own float, got 0.999920 back from the builder (block's 10-tx 'I can haz block?', index 8) and gas {g['gas']:.6f}; the proposer received {eth(y['proposer_payment_wei']):.6f} ETH. The gain is the 13,565.69 USDT kept, not in bot_net_eth. Net in USD terms: {usd:,.0f} - {-(g['eth'] - g['cb'] + g['rf'] - g['gas']) * ETHP:,.0f} = {usd + (g['eth'] - g['cb'] + g['rf'] - g['gas']) * ETHP:,.0f}."},
    "fate": {**fate_common},
    "raw_refs": {"bot.block": blkrefs(19393223)[0], "bot.position": blkrefs(19393223)[:2], "attacker_block": blkrefs(19393224)[:2],
                 "trigger.first_seen_utc_ms": MPZ, "evidence_level_mempool": MPZ,
                 "loot.gross_loot_eth": [f"data/raw/rpc/trace_{T_USDT}.json", PRICE_F], "loot.captured_usd": [f"data/raw/rpc/trace_{T_USDT}.json"],
                 "loot.coinbase_paid_eth": [f"data/raw/rpc/trace_{T_USDT}.json", blkrefs(19393223)[2]], "loot.priority_fee_paid_eth": blkrefs(19393223)[:2],
                 "loot.builder_refund_to_bot_eth": blkrefs(19393223)[:2], "loot.bot_net_eth": [f"data/raw/rpc/trace_{T_USDT}.json", *blkrefs(19393223)[:2]],
                 **fate_refs, "calldata_diff": f"{D}/calldata_diffs.json"},
    "rawref_gaps": [{"field": "fate.returned_*", "why": "return is incident-wide (see fate.incident_wide); no per-row split"}],
    "discrepancies": DISC_COMMON + ["Yoink's message 'the 2.45 Eth bribe to Lido' is supported: the proposer was paid 2.450663 ETH in this block; but the coinbase payment was 3.4521 ETH and 0.9999 ETH came back to Yoink's contract from its builder."],
    "evidence_notes": [
        "calldata_diffs.json: Yoink's two proxy calls (wallets 0xa340a9fb, 0xa17de4ec) vs the attacker contract's calls for the same wallets in tx 0xba300ca5: words 0-20 identical (including the UNIZEN-CLI info block and both victim addresses); word 2 (recipient) differs, and words 21-22 (the transferFrom amount tail) differ because the attacker's contract passes the balance it reads at run time (0 after Yoink).",
        "The attacker's tx targets wallets 0x687d124e, 0xa340a9fb, 0xa23846f4, 0xa17de4ec, 0xdaa91e81; 0x687d, 0xa238, 0xdaa9 were already empty after attacker 1's 19392761 tx; a340 held 8,163.939786 and a17d 5,401.745389 USDT at the end of 19393222 (eth_call), both 0 at 19393223.",
        f"Race file {D}/race_19393223.json: slot 8592563, 10-tx block by 'I can haz block?', Yoink index 0; 38 Flashbots bids, winning hash first submitted 1,293 ms before the slot (1,958 ms after the trigger), proposer paid 2.450663 ETH.",
        "Only attacker 4's txs besides Yoink's touch these two wallets (trace scan of every proxy call in 19392000-19394999)."],
    "incident_dir": D})
rows.append(r)

# ======================================================================= pending-xi
y = ys[T_XI]; g = agg([T_XI])
a = bvh.auction_summary(f"{D}/race_19393298.json", T_XI)
fh = full("0x5cfe50df")
r = row_common("pending-xi", "Unizen TradeAggregator - Yoink vs attacker 3's second-half XI pull (Ethereum)", T_XI, "beat-pending-attack",
    "Attacker 0x2ad8aed8 pulled exactly half of wallet 0xd04b7023's XI at 19393297 (nonce 16) and sent the other half as nonce 17, calldata identical to Yoink's except the recipient; Yoink's copy of the first half landed at 19393298 index 0 and nonce 17 landed at 19393300 index 62 and reverted ('Call-Failed'). That nonce 17 was pending when Yoink built is inferred (consecutive nonces, not in the mempool archive), and Yoink's call equally matches the already-landed first half.",
    "Yoink took the second half (1,118,715 XI) of a wallet at block 19393298 (index 0), replaying attacker 0x2ad8aed8's landed first-half call; the attacker's own second-half tx landed two blocks later and reverted. Weakest of the three beat-pending rows: pending-ness not measured.")
r.update({
    "orig_verdict": "confirmed-onchain (weak: Yoink pre-empted the attacker's identical second-half tx; pending-ness inferred)",
    "attacker": {"eoa": A3, "eoas": [A3], "contracts": [], "funding": "0x077d360f11d220e4d5d831430c81c26c9be7c4a4 (0.1773 ETH, 2024-02-29); not a known mixer", "funding_tx": "0xf029f848983ac1cf252d744b9ddffe47379157c132552858e777879ac6f8e6e7", "deploy_tx": None, "deploy_block": None,
                 "attack_txs": [{"hash": fh, "block": 19393297, "index": 83, "status": "success", "role": "first half (50.0% of the wallet's 2,237,430 XI), nonce 16, private (not in mempool-dumpster)"},
                                {"hash": A_XI_FOLLOW, "block": 19393300, "index": 62, "status": "reverted", "role": "second half, nonce 17, priority fee 3 gwei, reverted 'Call-Failed' because the wallet was already empty"}],
                 "none_reason": None},
    "bots_other": [other_yoink(h, "other Yoink tx of the same incident (own sub-row)") for h in (T_ADS, T_USDT)],
    "evidence_level_mempool": "absent-from-archive",
    "mempool_note": "mempool-dumpster 2024-03-08 covers the day but neither attacker tx (0x5cfe50df, 0x7234dfac) nor Yoink's tx is in it. Unknown != none.",
    "trigger": {"kind": None, "tx": None, "first_seen_utc_ms": None, "first_seen_utc": None, "sources": None,
                "note": "No mempool record for the attacker's first or second half; the trigger Yoink copied is either the landed first half (index 83 of the previous block) or the second half in flight - the call content is identical, so this cannot be told apart."},
    "attacker_block": 19393300, "attacker_block_note": "The attacker's second-half tx (nonce 17) landed at index 62 of block 19393300, two blocks after Yoink's, and reverted; its first half landed at 19393297.",
    "attacker_reference": {"kind": "attack-tx", "block": 19393300, "tx": A_XI_FOLLOW},
    "auction": a,
    "loot": {"scope": "bot-tx",
             "gross_loot_eth": round(g["eth"], 6),
             "gross_loot_method": "WETH.withdraw ETH delivered to the Yoink contract after selling 1,118,715.17 XI (token 0x295b4268...) pulled from wallet 0xd04b7023",
             "captured_native": {"amount": "1118715.169744549", "unit": "XI", "desc": "XI (18 decimals) from wallet 0xd04b7023, the other half of its 2,237,430 XI"},
             "captured_usd": round(g["eth"] * ETHP, 0), "captured_usd_source": f"gross ETH proceeds x DefiLlama ETH price {ETHP:.2f} at 2024-03-08T22:10Z",
             "coinbase_paid_eth": round(g["cb"], 6), "priority_fee_paid_eth": round(g["prio"], 6), "builder_refund_to_bot_eth": round(g["rf"], 6), "builder_payout_to_victim_eth": None,
             "bot_net_eth": round(g["eth"] - g["cb"] + g["rf"] - g["gas"], 6),
             "loot_note": f"gross {g['eth']:.6f} ETH - coinbase {g['cb']:.6f} + builder refund {g['rf']:.6f} (index 15) - gas {g['gas']:.6f}; proposer paid {eth(y['proposer_payment_wei']):.6f} ETH."},
    "fate": {**fate_common},
    "raw_refs": {"bot.block": blkrefs(19393298)[0], "bot.position": blkrefs(19393298)[:2], "attacker_block": [f"data/raw/rpc/rcpt_{A_XI_FOLLOW}.json"],
                 "evidence_level_mempool": MPZ,
                 "loot.gross_loot_eth": [f"data/raw/rpc/trace_{T_XI}.json"], "loot.captured_usd": [f"data/raw/rpc/trace_{T_XI}.json", PRICE_F],
                 "loot.coinbase_paid_eth": [f"data/raw/rpc/trace_{T_XI}.json", blkrefs(19393298)[2]], "loot.priority_fee_paid_eth": blkrefs(19393298)[:2],
                 "loot.builder_refund_to_bot_eth": blkrefs(19393298)[:2], "loot.bot_net_eth": [f"data/raw/rpc/trace_{T_XI}.json", *blkrefs(19393298)[:2]],
                 **fate_refs, "calldata_diff": f"{D}/calldata_diffs.json"},
    "rawref_gaps": [{"field": "trigger.first_seen_utc_ms", "why": "neither attacker half is in mempool-dumpster"}, {"field": "fate.returned_*", "why": "return is incident-wide (see fate.incident_wide)"}],
    "discrepancies": DISC_COMMON,
    "evidence_notes": [
        "calldata_diffs.json: Yoink's proxy call vs both attacker txs (first half 0x5cfe50df, second half 0x7234dfac): 23 words, only word 2 (recipient) differs; the amount 1,118,715,169,744,549,188,730,880 is the same in all three.",
        "Wallet 0xd04b7023 held 2,237,430.339 XI at the end of 19393296 (allowance max); after nonce 16 1,118,715.169744549294 XI; after Yoink 0.0000000001 XI (eth_call archive reads).",
        "Same-attacker pattern: from 19393252 to 19393361 eleven of twelve attacker pulls take exactly 50% of the wallet balance (incidents/unizen-2024/attacker_pull_fraction.json); here the attacker queued the second half itself.",
        f"Race file {D}/race_19393298.json: 17-tx block by 'I can haz block?', Yoink index 0, coinbase 0.37548 ETH, refund 0.30513 ETH (index 15), proposer 0.07719 ETH."],
    "incident_dir": D})
rows.append(r)

# ======================================================================= half-copies
g = agg(COPIES); st = stables(COPIES)
first = COPIES[0]
a = bvh.auction_summary(f"{D}/race_19393262.json", first)
pairs = {}
for ah in scan:
    pass
copy_src = {}
for cy in COPIES:
    vp = scan[cy]["effective_third_party_pulls"][0]
    src = [h for h, t in scan.items() if t["sender"] == A3 and t["block"] < scan[cy]["block"] and any(p["victim"] == vp["victim"] and p["token"] == vp["token"] and p["amt"] == vp["amt"] and p["effective"] for p in t["effective_third_party_pulls"])]
    assert len(src) == 1
    copy_src[cy] = src[0]
src0 = copy_src[first]
gross_eth_all = g["eth"]
usd_all = st["USDC"] + st["USDT"] + gross_eth_all * ETHP
r = row_common("half-copies", "Unizen TradeAggregator - Yoink's four late copies of attacker 3's half-balance pulls (Ethereum)", first, "late-copy",
    "Each of the four Yoink txs (19393262, 19393264, 19393342, 19393363, all index 0) pulls the same wallet, token and amount as a tx of attacker 0x2ad8aed8 that had already landed 1 block earlier (2 for the last), with calldata identical except the recipient word. The attacker took exactly 50% in each, so the other half was still there. Attacker txs not seen pending in the public mempool before inclusion.",
    "Four Yoink txs (index 0 of blocks 19393262-19393363) replayed attacker 0x2ad8aed8's half-balance pulls (USDC, USDC, QNT, VRA) 1-2 blocks after they landed, taking the other half; calldata identical but the recipient. Late copies, not front-runs.")
r.update({
    "orig_verdict": "related-not-frontrun (late copies of landed attacker txs)",
    "attacker": {"eoa": A3, "eoas": [A3], "contracts": [], "funding": "0x077d360f11d220e4d5d831430c81c26c9be7c4a4 (0.1773 ETH, 2024-02-29); not a known mixer", "funding_tx": "0xf029f848983ac1cf252d744b9ddffe47379157c132552858e777879ac6f8e6e7", "deploy_tx": None, "deploy_block": None,
                 "attack_txs": [{"hash": copy_src[c], "block": scan[copy_src[c]]["block"], "index": scan[copy_src[c]]["index"], "status": "success", "role": f"pulls 50.0% of a wallet; Yoink's copy {c[:10]} follows at block {ys[c]['block']}"} for c in COPIES],
                 "none_reason": None},
    "bots_other": [other_yoink(c, f"copy of {copy_src[c][:10]} (block {scan[copy_src[c]]['block']}): same wallet, token and amount, calldata identical except the recipient; coinbase {eth(ys[c]['coinbase_transfer_wei']):.4f} ETH, builder refund {eth(ys[c]['builder_refund_wei'] or 0):.4f} ETH, builder {ys[c]['builder_extradata']}") for c in COPIES[1:]]
                   + [{"label": "other copiers of the same attacker's half pulls", "eoa": "0x00bad13f.. / 0x7d671a0d.. / c0ffeebabe.eth (tx-level facts only)", "tx": None, "block": None, "position": 0, "status": "success",
                       "role": "0x00bad13f (19393253), 0x7d671a0d (19393261, 19393293) and c0ffeebabe.eth (19393357) each copied one half pull at index 0 of the next block; see incident.json other_racers and copy_sets.json"}],
    "evidence_level_mempool": "absent-from-archive",
    "mempool_note": "mempool-dumpster 2024-03-08: the attacker txs 0xd0bab3e7, 0x2ee97206 and 0x5cfe50df are not in it; 0xaf663a20 and 0xdd0636e2 appear only in the sourcelog 31 s and 5 s AFTER their block timestamps (not seen pending). Yoink's txs are not in it.",
    "trigger": {"kind": None, "tx": None, "first_seen_utc_ms": None, "first_seen_utc": None, "sources": None,
                "note": "The copied attacker txs had already been mined (1-2 blocks earlier); no pending trigger exists or was measured."},
    "attacker_block": scan[src0]["block"], "attacker_block_note": "Block 19393261 (index 24) for the first copy; the others follow at 19393263, 19393341, 19393361 (see attack_txs).",
    "attacker_reference": {"kind": "attack-tx", "block": scan[src0]["block"], "tx": src0},
    "auction": a,
    "loot": {"scope": "4 txs (0x73dad216, 0xaeb81988, 0x14328e29, 0xde7b7aed)",
             "gross_loot_eth": round(usd_all / ETHP, 6),
             "gross_loot_method": f"4,808.85262 USDC kept + ETH proceeds {gross_eth_all:.6f} (3,026.07 USDC, 62.5 QNT, 41,611 VRA sold in-tx) valued at DefiLlama ETH price {ETHP:.2f}",
             "captured_native": {"amount": "4808.852621 USDC, 3026.068927 USDC, 62.505616 QNT, 41611.328551 VRA", "unit": "mixed", "desc": "other half of four wallets; the first USDC leg is swept to the vault, the rest sold to ETH inside the tx"},
             "captured_usd": round(usd_all, 0), "captured_usd_source": f"USDC at 1 USD + ETH proceeds x {ETHP:.2f}",
             "coinbase_paid_eth": round(g["cb"], 6), "priority_fee_paid_eth": round(g["prio"], 6), "builder_refund_to_bot_eth": round(g["rf"], 6), "builder_payout_to_victim_eth": None,
             "bot_net_eth": round(g["eth"] - g["cb"] + g["rf"] - g["gas"], 6),
             "loot_note": f"sum over the 4 txs, ETH side: gross {g['eth']:.6f} - coinbase {g['cb']:.6f} + refund {g['rf']:.6f} - gas {g['gas']:.6f}; the 4,808.85 USDC kept (tx 0x73dad216, block built by rsync-builder.xyz, no refund) is in captured_usd but not in bot_net_eth. Per-tx numbers are in yoink_txs.json."},
    "fate": {**fate_common},
    "raw_refs": {"bot.block": blkrefs(19393262)[0], "bot.position": blkrefs(19393262)[:2], "attacker_block": blkrefs(scan[src0]["block"])[:2],
                 "evidence_level_mempool": MPZ,
                 "loot.gross_loot_eth": [f"data/raw/rpc/trace_{c}.json" for c in COPIES] + [PRICE_F], "loot.captured_usd": [f"data/raw/rpc/trace_{c}.json" for c in COPIES] + [PRICE_F],
                 "loot.coinbase_paid_eth": [f"data/raw/rpc/trace_{c}.json" for c in COPIES] + [f"data/raw/rpc/trace_block_{ys[c]['block']}.json" for c in COPIES],
                 "loot.priority_fee_paid_eth": [f"data/raw/rpc/receipts_{ys[c]['block']}.json" for c in COPIES],
                 "loot.builder_refund_to_bot_eth": [f"data/raw/rpc/block_{ys[c]['block']}.json" for c in COPIES],
                 "loot.bot_net_eth": [f"data/raw/rpc/trace_{c}.json" for c in COPIES] + [f"data/raw/rpc/block_{ys[c]['block']}.json" for c in COPIES],
                 **fate_refs, "calldata_diff": f"{D}/calldata_diffs.json", "attacker_pull_fraction": f"{D}/attacker_pull_fraction.json"},
    "rawref_gaps": [{"field": "trigger.first_seen_utc_ms", "why": "the copied attacker txs were already mined; no pending trigger"}, {"field": "fate.returned_*", "why": "return is incident-wide (see fate.incident_wide)"}],
    "discrepancies": DISC_COMMON,
    "evidence_notes": [
        "calldata_diffs.json: for each of the four copies all 23 calldata words of Yoink's proxy call equal the attacker's tx input except word 2 (recipient).",
        "attacker_pull_fraction.json: the attacker's pull equals exactly 0.5 of the wallet's balance at the end of the previous block in 11 of 12 txs between 19393252 and 19393361; the copy takes the same amount and leaves the wallet at ~0 (e.g. USDC wallet 0xbf12773b: 9,617.705242 -> 4,808.852621 -> 0).",
        "Block order: attacker 19393261 idx 24 -> Yoink 19393262 idx 0; 19393263 idx 31 -> 19393264 idx 0; 19393341 idx 41 -> 19393342 idx 0; 19393361 idx 42 -> 19393363 idx 0 (block 19393362 skipped). Three other bots copy the same attacker at index 0 of the next block (copy_sets.json).",
        "Blocks 19393262 (rsync-builder.xyz) and 19393363 (Titan) are not Yoink's builder: no refund, full coinbase cost; 19393264 and 19393342 are 'I can haz block?' with 64% and 81% refunds."],
    "incident_dir": D})
rows.append(r)

for rr in rows:
    rr["auction"]["raw_refs"] = {k: v for k, v in rr["auction"].get("raw_refs", {}).items()}
write(S, rows)
