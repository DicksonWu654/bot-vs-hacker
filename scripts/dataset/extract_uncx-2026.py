"""Extract incident dataset rows for uncx-2026 (sub yoink-X, sub zc-copiers). Run from project root: .venv/bin/python scripts/dataset/extract_uncx-2026.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _x5_common import *
from collections import Counter

S = "uncx-2026"
inc = jl(f"incidents/{S}/incident.json")
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
V = "0xa98f06312b7614523d0f5e725e15fd20fb1b99f5"  # vesting contract all copiers call
ATT_EOA = "0x78c9b11853e4f183a34c63ffd1924d2319a2f5b3"
ATT_CON = "0x6cebdf095172b355121b93962017975c4601f26c"
ATT_DEPLOY = "0x477c8060aa22478b436d6120ffe5954775cb02974acd09d7c52ae1500b73d4d9"
ATT_FUND = "0x52fe1a5aa857a3e6f6f0c12f559019da382c294238601b967a74b03c01c5b93b"
ATT_ZC = "0x352065378c4a41b77e5b6a1e5b5616cd2886c3e1a2c87ed3db8e5ddddc23823d"   # 26191745 pos 1
ATT_X = "0xfd6f57ec11b40faea66f42b48e044c173408b0570e706f5ad6286177808da7cc"    # 26191921 pos 3
YOINK_EOA, YOINK_CON, YOINK_VAULT = "0xfde0d1575ed8e06fbf36256bcdfa1f359281455a", "0x80bf7db69556d9521c03461978b8fc731dbbd4e4", "0xc70f00cd7e461686b04b0e912e309beca8b80ea0"
YOINK_TX = "0xbf7e5182694d0703051951520c176135dac63d772b328468ce783b37dd7a8a7c"
CP1_EOA, CP1_CON = "0x053d984eab3240cdf7c53b8b7846159f8146e99b", "0x4a78cf73fd86e961d825937466b937b8b82207a8"
CP1_TX = "0x55b34cd6e8da7e6cfafb91f746c1ae0425b97a29a54c61dbc40d69d0eb9d72fc"
C0_EOA, C0_CON = "0xc0ffeebabe5d496b2dde509f9fa189c25cf29671", "0xe08d97e151473a848c3d9ca3f323cb720472d015"
C0_TX = "0xf57b7dbfdb24aa811012bbdc4e70c1027c7b2cca6b5d776881a44f488afc6bae"
RET_ETH = "0x07614e32f26762ef90d3010f8f4460302a6689ab4444c62015fb04cb2edc02d2"
RET_X = "0xf0ae2cd77698882e35437500891907327765f4e36f33c7dcd88683be7c757301"
RET_BASE = "0x7ed6c60ca8b53e259c1d327a03d6e3242ba88a9c2b98f8ccb3ebca9ff60d37ca"
X_TOKEN = "0x140007c65535aa9c3801ea3bbd3f83c378c7f457"
ZC_TOKEN_PFX = "0x4e67db19"

R = {b: jl(f"incidents/{S}/race_{b}.json") for b in (26191745, 26191787, 26191867, 26191903, 26191920, 26191921, 26191993, 26191995)}
rp = lambda b: f"incidents/{S}/race_{b}.json"
a_ = lambda t: "0x" + t[-40:]


def receipt_of(block, h):
    p = R[block]["raw_refs"]["receipts"]
    for rc in res(jl(p)):
        if rc["transactionHash"].lower() == h:
            return p, rc
    raise KeyError(h)


def trace_of(block, h):
    p = R[block]["raw_refs"]["traces"]
    for x in res(jl(p)):
        if x["txHash"].lower() == h:
            return p, x["result"]
    raise KeyError(h)


def victim_calls(root):
    return [c for d, c in walk(root) if (c.get("to") or "").lower() == V]


def dec9(v):
    return f"{v // 10**9}.{v % 10**9:09d}"


def block_builder_revenue(race):
    return sum(int(t["builder_revenue_wei"]) for t in race["txs"]) / 1e18


# ---------- shared attacker block ----------
att_txs = []
for t in inc["attacker"]["txs"]:
    r = R[t["block"]]
    rt = race_tx(r, t["hash"])
    att_txs.append({"hash": t["hash"], "block": t["block"], "index": rt["index"], "status": "success" if rt["status"] == 1 else "reverted",
                    "role": {26191745: "first/original drain (EDGEN, ZC, LO0P, PAAL, pepecoin); the ZC leg is what the ZC copiers replay later",
                             26191787: "retry on uPEG, reverted 'play failed'", 26191867: "retry on uPEG, reverted 'play failed'", 26191903: "retry on uPEG, reverted 'play failed'",
                             26191921: "attacker's own X-token drain; reverted 'play failed' one block after Yoink took X"}[t["block"]]})
attacker = {"eoa": ATT_EOA, "eoas": [ATT_EOA], "contracts": [ATT_CON, "0xf6d072254eb8a9b06e0ba21221b498332c1bc35e", "0xc6471f377870bb058b99eb7bab690c3f801aa7b9"],
            "funding": "EOA 0x6d2afff4 (not identified as a mixer)", "funding_tx": ATT_FUND, "deploy_tx": ATT_DEPLOY, "deploy_block": 26191446,
            "attack_txs": att_txs, "none_reason": None}
attacker_raw = {"attacker.txs": [R[b]["raw_refs"]["block"] for b in (26191745, 26191787, 26191867, 26191903, 26191921)]}
EXTRA_REFS = {"uncx_report_phemex": "data/raw/web-w4/uncx2026_phemex_uncx_807k.html", "uncx_report_odaily": "data/raw/web-w4/uncx2026_odaily_525326.html"}
ptn = "UNCX report (Phemex, Odaily, 2026-10-17): \"a white-hat hacker returned 82,143,476 X tokens and 23.8682 ETH\" (single combined figure for all actors). Our on-chain sum: 8.10335 ETH (Yoink vault, Ethereum) + 15.764813 ETH (c0ffeebabe EOA, Base) = 23.868163 ETH; matches numerically, attribution to two actors is ours, not the report's."

# ================= ROW 1: Yoink vs attacker X =================
rY = R[26191920]; bY = rY["block"]; tY = race_tx(rY, YOINK_TX)
pY_tr, rootY = trace_of(26191920, YOINK_TX)
pY_rc, rcY = receipt_of(26191920, YOINK_TX)
vY = victim_calls(rootY)
selY = Counter(c["input"][:10] for c in vY)
fees = sum(hx(c.get("value", "0x0")) for c in vY) / 1e18
weth_in = x_vault = 0
for l in rcY["logs"]:
    if l["topics"] and l["topics"][0] == TRANSFER and len(l["topics"]) == 3:
        f, t, v = a_(l["topics"][1]), a_(l["topics"][2]), int(l["data"], 16)
        if l["address"].lower() == WETH and t == YOINK_CON: weth_in += v
        if l["address"].lower() == X_TOKEN and f == YOINK_CON and t == YOINK_VAULT: x_vault += v
gross_y = weth_in / 1e18 - fees
coin_y = eth(tY["coinbase_transfer_wei"])
gas_y = eth(hx(rcY["gasUsed"]) * hx(rcY["effectiveGasPrice"]))
net_y = gross_y - coin_y - gas_y
ref_wei, _ = builder_to(rY, [YOINK_EOA, YOINK_CON, YOINK_VAULT])
# attacker's X tx
rA = R[26191921]; pA_tr, rootA = trace_of(26191921, ATT_X)
vA = victim_calls(rootA)
selA = Counter(c["input"][:10] for c in vA)
yl = [c for c in vY if c["input"].startswith("0x0c558e44")]; al = [c for c in vA if c["input"].startswith("0x0c558e44")]
w = lambda c: [c["input"][10:][k:k + 64] for k in range(0, len(c["input"]) - 10, 64)]
dpos = Counter()
n_cmp = min(len(yl), len(al))
for cy, ca in zip(yl, al):
    for k, (u, v) in enumerate(zip(w(cy), w(ca))):
        if u != v: dpos[k] += 1
att_x = race_tx(rA, ATT_X)
# returns
t_ret_eth_p, t_ret_eth = rpc_tx(RET_ETH)
t_ret_x_p, t_ret_x = rpc_tx(RET_X)
rc_ret_x = res(jl(f"data/raw/rpc/receipt_{RET_X}.json"))
ret_eth_y = eth(hx(t_ret_eth["value"]))
ret_x = int(rc_ret_x["logs"][0]["data"], 16)
assert rc_ret_x["logs"][0]["address"].lower() == X_TOKEN
ret_eth_blk, ret_x_blk = hx(t_ret_eth["blockNumber"]), hx(t_ret_x["blockNumber"])
hdr_e = res(jl(f"data/raw/rpc/blockhdr_{ret_eth_blk}.json")); hdr_x = res(jl(f"data/raw/rpc/blockhdr_{ret_x_blk}.json"))
kept_x = (x_vault - ret_x) / 1e9
aucY = bvh.auction_summary(rp(26191920), YOINK_TX)
revY = block_builder_revenue(rY)
mb = max(rY["bids"], key=lambda b: b["value_eth"])
byhash_p = "data/raw/relay-titan/bids_byhash_26191920.json"
bh = jl(byhash_p)
win_ms = min(int(x["timestamp_ms"]) for x in bh)
win_rel = win_ms - aucY["slot_start_utc_ms"]
aucY["auction_note"] = ("Winner %s %.6f ETH. The helper's winning-hash submission fields are null here because the Titan/Ultra Sound bid lists omit the winning hash; a by-hash query of the Titan relay (%s) shows it first submitted at +%d ms of the slot. The block's txs paid the builder fee recipient %.4f ETH in total (Yoink's coinbase transfer alone %.4f ETH) against a %.4f ETH payment to the proposer (tx idx 139): the builder kept the difference. Record bids sat in the 0.0x ETH range until a 0.118 ETH bid at -982 ms, then climbed to ~0.84 ETH from +749 ms (auction.escalation). The highest bid seen (%.4f ETH, %s, +%d ms, %s txs) was for a different block hash and was not delivered."
                       % (aucY["winning_builder"], aucY["winning_bid_eth"], byhash_p, win_rel, revY, coin_y, aucY["winning_bid_eth"], mb["value_eth"], mb.get("builder_name"), mb["t_rel_slot_ms"], mb.get("num_tx")))

disc_common = []
disc_y = [
 "incident.json says the attacker's X tx had '82 victim calls all reverted'; the saved trace shows the tx root reverted with 'play failed' (status 0) and only %d of the %d sub-calls into the vesting contract carry their own error flag (the rest roll back with the tx)." % (sum(1 for c in vA if c.get("error")), len(vA)),
 "Yoink net ETH: gross %.6f - coinbase %.6f - gas %.6f = %.6f ETH, yet the vault later returned %.5f ETH: the returned ETH exceeds the tx's net ETH, so it came from vault balance (source not examined)." % (gross_y, coin_y, gas_y, net_y, ret_eth_y),
]

row1 = {
 "slug": S, "sub": "yoink-X", "name": "UNCX Smart Token Vesting V2 - Yoink vs the attacker's X-token drain (Ethereum)",
 "date_utc": bY["timestamp_utc"].replace("+00:00", "Z"), "chain": "ethereum",
 "orig_verdict": "confirmed-onchain (Yoink front-run of the attacker's X-token drain)",
 "race_type_proposed": "beat-pending-attack",
 "race_type_reason": "Yoink's tx at block 26191920 position 0 makes the same lock/withdraw victim calls on token X as the attacker's own tx, which landed one block later (26191921) and reverted ('play failed') because X was already taken. That the attacker's tx was pending when Yoink built is inferred (private flow, no mempool record), not shown.",
 "one_liner": "Yoink's tx took the X-token drain in block 26191920 (pos 0); the attacker's identical call set landed one block later and reverted. Yoink's wallet later returned 8.10335 ETH and 82,143,476.36 X, keeping exactly 20,000,000 X.",
 "attacker": attacker,
 "bot": {"label": "Yoink", "eoa": YOINK_EOA, "contract": YOINK_CON, "tx": YOINK_TX, "block": bY["number"], "position": tY["index"],
         "status": "success" if tY["status"] == 1 else "reverted", "priority_fee_gwei": tY["priority_fee_gwei"]},
 "bots_other": [],
 "evidence_level_mempool": "absent-from-archive",
 "mempool_note": "mempool-dumpster covers 2026-10-14 (901,612 txs) but neither Yoink's tx nor any attacker tx (1745, 787, 867, 903, 921) is in it (race files mempool.txs[hash].seen=false): all private flow or missed. Unknown != none.",
 "trigger": {"kind": None, "tx": None, "first_seen_utc_ms": None, "first_seen_utc": None, "sources": None,
             "note": "The attacker's X tx (0xfd6f57ec..., block 26191921 pos 3, priority 9.70 gwei) has no mempool first-seen, so the claim that it was pending when Yoink built block 26191920 is an inference from the one-block-later landing and identical call set, not a measurement."},
 "attacker_block": 26191921,
 "attacker_block_note": "Block in which the attacker's racing X-token tx landed and reverted ('play failed'): one block AFTER the bot (26191920). The attacker's first drain (ZC etc.) landed earlier at block 26191745 and is the other sub-race's reference.",
 "attacker_reference": {"kind": "attack-tx", "block": 26191921, "tx": ATT_X},
 "auction": aucY,
 "loot": {
  "scope": "bot-tx", "gross_loot_eth": round(gross_y, 9),
  "gross_loot_method": "ETH-side proceeds of the Yoink tx: WETH Transfer log from the V2 pair into Yoink's contract (%.9f WETH) minus %.2f ETH of lock fees sent as value with the %d 0x0c558e44 calls into the vesting contract (trace). Excludes the X tokens swept to the vault." % (weth_in / 1e18, fees, selY["0x0c558e44"]),
  "captured_native": {"amount": dec9(x_vault), "unit": "X", "desc": "X (9 decimals, 0x140007c6...) swept from Yoink's contract to its vault 0xc70f00cd, plus the ETH-side proceeds in gross_loot_eth"},
  "captured_usd": None, "captured_usd_source": None,
  "coinbase_paid_eth": round(coin_y, 9), "priority_fee_paid_eth": eth(tY["priority_fee_total_wei"]),
  "builder_refund_to_bot_eth": round(ref_wei / 1e18, 9), "builder_payout_to_victim_eth": None,
  "bot_net_eth": round(net_y, 9),
  "loot_note": "Bot tx only. ETH side: gross %.6f ETH (= coinbase / 0.999), coinbase %.6f ETH (%.2f%% of gross) to builder.ultrasound.money's fee recipient, gas %.6f ETH, net %.6f ETH. The tx also moved %s X to the vault. No builder->Yoink transfer in the block." % (gross_y, coin_y, 100 * coin_y / gross_y, gas_y, net_y, dec9(x_vault)),
 },
 "fate": {
  "return_status": "partial", "returned_by_bot_eth": round(ret_eth_y, 6), "returned_by_builder_eth": None, "returned_total_eth": round(ret_eth_y, 6),
  "returned_to": "0x32f0eb068fd804195629a2cbee30a7e9ce58c4cb (proxy contract, identity not verified)",
  "returned_desc": "Yoink's vault %s returned %.5f ETH (tx %s, block %d, %s) and %s X (tx %s, block %d, %s) to 0x32f0eb06, i.e. about two days after the attack, keeping exactly %.0f X of the %s X it had swept (%.2f%%). returned_total_eth counts only the ETH; the X are not priced here." % (YOINK_VAULT[:10], ret_eth_y, RET_ETH[:10], ret_eth_blk, iso(hx(hdr_e["timestamp"])), dec9(ret_x), RET_X[:10], ret_x_blk, iso(hx(hdr_x["timestamp"])), kept_x, dec9(x_vault), 100 * kept_x / (x_vault / 1e9)),
  "bounty_kept_eth": None, "bounty_desc": "exactly %.0f X (%.2f%% of the swept X) retained by the Yoink vault; no public statement of a bounty agreement found, so this is the retained amount, not a confirmed bounty" % (kept_x, 100 * kept_x / (x_vault / 1e9)),
  "kept_by_bot_eth": None,
  "returned_txs": [{"tx": RET_ETH, "eth": round(ret_eth_y, 6), "note": "Yoink vault -> 0x32f0eb06, ETH", "block": ret_eth_blk, "time_utc": iso(hx(hdr_e["timestamp"]))},
                   {"tx": RET_X, "eth": None, "note": "Yoink vault -> 0x32f0eb06, %s X tokens (not ETH-priced)" % dec9(ret_x), "block": ret_x_blk, "time_utc": iso(hx(hdr_x["timestamp"]))}],
  "public_statement": ptn,
 },
 "raw_refs": {
  "bot.block": rY["raw_refs"]["block"], "bot.position": rY["raw_refs"]["block"],
  "attacker_block": rA["raw_refs"]["block"],
  "loot.gross_loot_eth": [pY_rc, pY_tr], "loot.coinbase_paid_eth": rY["raw_refs"]["traces"],
  "loot.priority_fee_paid_eth": [rY["raw_refs"]["receipts"], rY["raw_refs"]["block"]],
  "loot.builder_refund_to_bot_eth": [rY["raw_refs"]["block"], rY["raw_refs"]["traces"]],
  "loot.bot_net_eth": [pY_rc, pY_tr],
  "fate.returned_by_bot_eth": t_ret_eth_p, "fate.returned_total_eth": t_ret_eth_p,
  "fate.return_x_tx": [t_ret_x_p, f"data/raw/rpc/receipt_{RET_X}.json"], "fate.return_times": [f"data/raw/rpc/blockhdr_{ret_eth_blk}.json", f"data/raw/rpc/blockhdr_{ret_x_blk}.json"],
  "attacker_x_tx_trace": pA_tr, **EXTRA_REFS,
 },
 "rawref_gaps": [{"field": "trigger.first_seen_utc_ms", "why": "attacker's X tx and Yoink's tx are not in mempool-dumpster 2026-10-14"},
                 {"field": "fate.bounty_kept_eth", "why": "retained asset is 20,000,000 X (no ETH valuation taken)"}],
 "discrepancies": disc_y,
 "evidence_notes": [
  "Victim-call diff (saved block traces %s idx 0 vs %s idx 3): the attacker's X tx makes %d lock calls (0x0c558e44) and Yoink makes %d; for the %d lock calls compared pairwise, calldata differs only in word 2 (recipient), word 8 and word 11 (block-timestamp-derived time args); all other words, including the per-call amount, are identical (differing words per call: %s)." % (pY_tr, pA_tr, len(al), len(yl), n_cmp, dict(dpos)),
  "Yoink victim calls by selector: %s (value 0.05 ETH per lock = %.2f ETH). Attacker X tx victim calls: %s; it reverted 'play failed' at block 26191921 pos 3 after paying %.4f ETH in priority fees (9.70 gwei)." % (dict(selY), fees, dict(selA), eth(att_x["priority_fee_total_wei"])),
  "Ordering: Yoink block 26191920 pos 0 (16:24:59Z) vs attacker X tx block 26191921 pos 3 (16:25:11Z): bot one block earlier. No mempool record of either tx.",
  "Returns: ETH tx %s (block %d) and X tx %s (block %d) from Yoink's vault to 0x32f0eb06; 20,000,000 X retained exactly." % (RET_ETH[:10], ret_eth_blk, RET_X[:10], ret_x_blk),
 ],
 "incident_dir": f"incidents/{S}",
}

# ================= ROW 2: ZC copiers (late copy) =================
row2 = next(row for row in jl(f"data/extract/{S}.json") if row.get("sub") == "zc-copiers")
finish(S, [row1, row2])
