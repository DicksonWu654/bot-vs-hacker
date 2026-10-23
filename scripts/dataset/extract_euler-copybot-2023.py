"""Extract row for euler-copybot-2023 -> data/extract/euler-copybot-2023.json. Run from project root: .venv/bin/python scripts/dataset/extract_euler-copybot-2023.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _x6 import *

S = "euler-copybot-2023"
inc = load(f"incidents/{S}/incident.json")
bd = load(f"incidents/{S}/bytecode_diff.json")
r93 = load(f"incidents/{S}/race_16817993.json"); r94 = load(f"incidents/{S}/race_16817994.json")
r96 = load(f"incidents/{S}/race_16817996.json"); r13 = load(f"incidents/{S}/race_16818013.json")
r24 = load(f"incidents/{S}/race_16818024.json")
ATKDEP = "0x50dc9c9126519a70319cc312418488145bed4e2ef6e110eb864a97f5beaeca05"
CPYDEP = "0x725db76cf4bf3bdc72be4f755ed72df4adbc8e4e803c044617cc11e34907ccdc"
CALL = "0xc310a0affe2169d1f6feec1c63dbc7f7c62a887fa48795d327d4d2da2d6b111d"
CPYDEP2 = "0x684f82f596f8d211b85893abf85a9e1d9d686bfd5c17131467f93eb782bd1d2d"
ATKFAIL = "0xa476fad72c8f4ee15fd2d75ecda4701d8f3ac74431aa453521f13a01c8688142"
ATKOK = "0x47ac3527d02e6b9631c77fad1cdee7bfa77a8a7bfd4880dccbda5146ace4088f"
WD = "0xdae809e4a1ddf77c39d44a4acfe6165bedbc19a385c4b241242cc9bd582a80b9"
MSG = "0x44b559c86ca8ccac5c16df507516ef19c06042a48cdbd865cb9db4c52d15ea17"
DAI = "0x6b175474e89094c44da98b954eedeac495271d0f"
COPY1 = "0xebc29199c817dc47ba12e3f86102564d640cbf99"
HARD = "0xb66cd966670d962c227b3eaba30a872dbfb995db"
disc = []

def rtx(h):
    t = load(f"data/raw/rpc/tx_{h}.json"); return t.get("result", t)
def tr(h):
    t = load(f"data/raw/rpc/trace_tx_{h}.json"); return t.get("result", t)

# 1. bytecode diff recomputed from the two creation txs
a_in, c_in = rtx(ATKDEP)["input"], rtx(CPYDEP)["input"]
assert len(a_in) == len(c_in)
diff = [i for i in range(2, len(a_in), 2) if a_in[i:i+2] != c_in[i:i+2]]
n_diff = len(diff)
offs = sorted({(i - 2) // 2 for i in diff})
starts = [o for o in offs if o - 1 not in offs]
if n_diff != bd["n_diff_bytes"] or starts != [r[0] for r in bd["regions"]]:
    disc.append(f"recomputed creation-calldata diff {n_diff} bytes at {starts} vs bytecode_diff.json {bd['n_diff_bytes']} at {[r[0] for r in bd['regions']]}")
ba, bc = "b2698c2d99ad2c302a95a8db26b08d17a77cedd4", "5f259d0b76665c337c6104145894f4d1d2758b8c"
chk = all(a_in[2 + 2 * s: 2 + 2 * (s + 20)].lower() == ba and c_in[2 + 2 * s: 2 + 2 * (s + 20)].lower() == bc for s in starts)
assert chk and n_diff == 80 and len(starts) == 4, (n_diff, starts)
hard_in_both = HARD[2:] in a_in.lower() and HARD[2:] in c_in.lower()
assert hard_in_both

# 2. DAI flows in the copier's call (callTracer)
t = tr(CALL)
flows = []
def walk(c):
    inp = c.get("input", "")
    if c.get("to", "").lower() == DAI and inp[:10] in ("0xa9059cbb", "0x23b872dd") and not c.get("error"):
        if inp[:10] == "0xa9059cbb": f, to, amt = c["from"], "0x" + inp[34:74], int(inp[74:138], 16)
        else: f, to, amt = "0x" + inp[34:74], "0x" + inp[98:138], int(inp[138:202], 16)
        flows.append((f.lower(), to.lower(), amt / 1e18))
    for x in c.get("calls") or []: walk(x)
walk(t)
flash = [x for x in flows if x[1] == COPY1 and x[0].startswith("0x028171bc")][0][2]
out_euler = [x for x in flows if x[1] == COPY1 and x[0].startswith("0xa0b3ee89")][0][2]
repay = [x for x in flows if x[0] == COPY1 and x[1].startswith("0x028171bc")][0][2]
into_euler = sum(x[2] for x in flows if x[1].startswith("0x27182842"))
sent_out = sum(x[2] for x in flows if x[0] == COPY1 and not x[1].startswith("0x028171bc"))  # DAI the copy sends on toward Euler (via a helper)
net_dai = flash + out_euler - sent_out - repay
euler_net_loss = out_euler - into_euler
if abs(net_dai - 8877507.35) > 0.01:
    disc.append(f"net DAI left in copy {net_dai} vs 8,877,507.35")
# withdraw trace: DAI to hard-coded wallet
wdt = tr(WD); wd_out = []
def walk2(c):
    inp = c.get("input", "")
    if c.get("to", "").lower() == DAI and inp[:10] == "0xa9059cbb":
        wd_out.append(("0x" + inp[34:74], int(inp[74:138], 16) / 1e18))
    for x in c.get("calls") or []: walk2(x)
walk2(wdt)
assert wd_out[0][0] == HARD and abs(wd_out[0][1] - net_dai) < 1e-3, (wd_out, net_dai)
assert wdt["from"].lower() == "0x5f259d0b76665c337c6104145894f4d1d2758b8c"
wd_block = int((load(f"data/raw/rpc/receipt_{WD}.json").get("result") or load(f"data/raw/rpc/receipt_{WD}.json"))["blockNumber"], 16)
msg_block = int((load(f"data/raw/rpc/receipt_{MSG}.json").get("result") or load(f"data/raw/rpc/receipt_{MSG}.json"))["blockNumber"], 16)
msg_text = bytes.fromhex(rtx(MSG)["input"][2:]).decode(errors="replace")

# 3. rows
c = txrow(r96, CALL); cd1 = txrow(r94, CPYDEP); cd2 = txrow(r13, CPYDEP2)
ad = txrow(r93, ATKDEP); af = txrow(r13, ATKFAIL); ao = txrow(r24, ATKOK)
tip_eth = eth(c["priority_fee_total_wei"]); gas_eth = c["gas_used"] * c["gas_price_gwei"] * 1e9 / 1e18
a = bvh.auction_summary(f"incidents/{S}/race_16817996.json", CALL)
if abs(a["winning_bid_eth"] - 0.0942500397113145) > 1e-12:
    disc.append("winning bid differs from incident.json")
share = tip_eth / a["winning_bid_eth"]

refs = {
 "bot.block": "data/raw/rpc/block_16817996.json", "bot.position": "data/raw/rpc/block_16817996.json",
 "attacker_block": "data/raw/rpc/block_16818013.json",
 "loot.captured_usd": [f"data/raw/rpc/trace_tx_{CALL}.json"],
 "loot.coinbase_paid_eth": "data/raw/rpc/trace_block_16817996.json",
 "loot.priority_fee_paid_eth": "data/raw/rpc/receipts_16817996.json",
 "loot.builder_refund_to_bot_eth": "data/raw/rpc/block_16817996.json",
 "loot.bot_net_eth": [f"data/raw/rpc/trace_tx_{WD}.json", f"data/raw/rpc/trace_tx_{CALL}.json"],
 "fate.kept_by_bot_eth": [f"data/raw/rpc/trace_tx_{WD}.json", f"data/raw/rpc/trace_tx_{CALL}.json"],
 "creation_calldata_diff": [f"data/raw/rpc/tx_{ATKDEP}.json", f"data/raw/rpc/tx_{CPYDEP}.json"],
 "copier_withdraw": [f"data/raw/rpc/trace_tx_{WD}.json", f"data/raw/rpc/receipt_{WD}.json"],
 "copier_message": [f"data/raw/rpc/tx_{MSG}.json", f"data/raw/rpc/receipt_{MSG}.json"],
 "attacker_first_call": [f"data/raw/rpc/receipt_{ATKFAIL}.json", "data/raw/rpc/trace_block_16818013.json"],
 "attacker_deploy": "data/raw/rpc/block_16817993.json",
}
row = {
 "slug": S, "name": inc["name"], "date_utc": iso(r96["block"]["timestamp"]), "chain": "ethereum",
 "orig_verdict": inc["verdict"],
 "race_type_proposed": "deploy-window-copy",
 "race_type_reason": "The copier deployed a byte-near-identical copy of the attacker's exploit contract one block after the attacker's deploy (4 x 20-byte address swaps) and used its DAI-market entry point at the top of block 16817996, 17 blocks before the attacker's first (failed) call. It is the attacker's own on-chain setup being used before the attacker's call, not a calldata replay.",
 "one_liner": "A fresh EOA copied the Euler attacker's exploit contract one block after its deploy, swapping only the owner address, and ran its DAI-market entry point at block 16817996 position 0: 8,877,507 DAI out of Euler. Funds went to the attacker's hard-coded wallet; the copier captured nothing.",
 "attacker": {"eoa": "0xb2698c2d99ad2c302a95a8db26b08d17a77cedd4", "eoas": ["0xb2698c2d99ad2c302a95a8db26b08d17a77cedd4", HARD + " (hard-coded cash-out wallet in both contracts)"],
              "contracts": ["0x036cec1a199234fc02f72d29e596a09440825f1c"], "funding": "tornado",
              "funding_tx": inc["attacker"]["funding_tx"]["tx"], "deploy_tx": ATKDEP, "deploy_block": 16817993,
              "attack_txs": [
                {"hash": ATKDEP, "block": 16817993, "index": ad["index"], "status": "success", "role": "deploy the exploit contract 0x036cec1a (3 gwei tip)"},
                {"hash": ATKFAIL, "block": 16818013, "index": af["index"], "status": "reverted", "role": "attacker's first call (WETH-market entry 0xa91864d4); out of gas in the Aave delegatecall; 17 blocks after the copier's DAI-market exploit"},
                {"hash": ATKOK, "block": 16818024, "index": ao["index"], "status": "success", "role": "attacker's first successful call (WETH market, 20,895 WETH flash loan)"}],
              "none_reason": None},
 "bot": {"label": "anon searcher", "eoa": c["from"], "contract": c["to"], "tx": CALL, "block": 16817996, "position": c["index"],
         "status": "success" if c["status"] == 1 else "reverted", "priority_fee_gwei": c["priority_fee_gwei"]},
 "bots_other": [
   {"label": "anon searcher (copier)", "eoa": cd1["from"], "tx": CPYDEP, "block": 16817994, "position": cd1["index"], "status": "success",
    "role": f"deploy of the copy contract {COPY1} (creation calldata identical to the attacker's except 4 x 20 bytes), one block after the attacker's deploy; tip {cd1['priority_fee_gwei']:.1f} gwei"},
   {"label": "anon searcher (copier)", "eoa": cd2["from"], "tx": CPYDEP2, "block": 16818013, "position": cd2["index"], "status": "success",
    "role": "second byte-identical copy deployed in the same block as the attacker's first failed call; never successfully called (calls by other addresses reverted). A causal link to the attacker's out-of-gas failure is not shown."}],
 "evidence_level_mempool": "in-block-only",
 "mempool_note": "In-block evidence only: March 2023 is before the mempool-dumpster archive (starts 2023-08-07). It is unknown whether the copier saw the attacker's deploy in the public mempool or only after block 16817993 landed, 12 s before the copy deploy was included.",
 "trigger": {"kind": None, "tx": None, "first_seen_utc_ms": None, "first_seen_utc": None, "sources": None,
             "note": "No mempool first-seen exists (pre-archive). Reference event is the attacker's deploy tx 0x50dc9c91 in block 16817993 (2023-03-13T08:50:23Z)."},
 "attacker_block": 16818013,
 "attacker_block_note": "Block of the attacker's FIRST call to its own contract (tx 0xa476fad7, index 44, WETH-market entry, out of gas); its first success was block 16818024 (tx 0x47ac3527). This is 17 blocks AFTER the copier's DAI-market exploit; the attacker never called the DAI entry point. The race is the whole deployed contract, so attacker_reference is the deploy.",
 "attacker_reference": {"kind": "deploy", "block": 16817993, "tx": ATKDEP},
 "auction": a,
 "loot": {
   "scope": "bot-tx",
   "gross_loot_eth": None,
   "gross_loot_method": "not converted: the proceeds are DAI and no ETH/DAI price is saved for this block; not invented",
   "captured_native": {"amount": f"{net_dai:,.2f}", "unit": "DAI", "desc": f"net DAI left in the copy contract {COPY1}: {out_euler:,.2f} DAI from Euler plus {flash:,.0f} DAI Aave flash loan minus {sent_out:,.0f} DAI the copy sent into Euler minus {repay:,.0f} DAI repaid; later sent by the copy's withdraw() to the attacker's hard-coded wallet {HARD}"},
   "captured_usd": round(net_dai, 2), "captured_usd_source": "DAI at par (stablecoin), amount from the callTracer trace of tx 0xc310a0af; same figure as incident.json routed_to_hacker_usd (8,877,507). This went to the hacker's wallet, not to the copier.",
   "coinbase_paid_eth": 0.0, "priority_fee_paid_eth": round(tip_eth, 8),
   "builder_refund_to_bot_eth": 0.0, "builder_payout_to_victim_eth": None,
   "bot_net_eth": 0.0,
   "loot_note": f"bot_net_eth is 0: the copier captured nothing. The DAI sat in its copy until the copier itself called withdraw() (tx 0xdae809e4, block {wd_block}), which sent all {wd_out[0][1]:,.2f} DAI to the wallet baked into the creation code ({HARD}, the attacker's wallet). Costs are NOT netted: the attack tx cost {gas_eth:.4f} ETH of gas ({tip_eth:.4f} ETH tip + base fee), about 0.61 ETH across all the copier's txs per incident.json. Euler's net DAI-market loss in this tx was {euler_net_loss:,.2f} DAI (Euler paid out {out_euler:,.2f} DAI and received {into_euler:,.0f} DAI); the whole Euler hack is about $197M (PeckShield figure, not re-verified here). No coinbase transfer: the tip ({tip_eth:.4f} ETH) is {share*100:.0f}% of the {a['winning_bid_eth']:.5f} ETH winning bid, so position 0 came from the public gas-price auction, not a bundle. No builder refund seen."},
 "fate": {
   "return_status": "none-found",
   "returned_by_bot_eth": None, "returned_by_builder_eth": None, "returned_total_eth": None,
   "returned_to": None,
   "returned_desc": f"Nothing reached Euler from this row. The copier's contract can only pay the address hard-coded in its bytecode, so its withdraw() (block {wd_block}, about 2 h 47 min after the exploit) sent all {wd_out[0][1]:,.2f} DAI to the attacker's wallet. The copier's on-chain message (tx 0x44b559c8, block {msg_block}) says it tried to return the money and 'unfortunately it sent the money to the hacker's address'. Any later return by the Euler hacker to Euler is outside this row and not covered by our saved files.",
   "bounty_kept_eth": None, "bounty_desc": None, "kept_by_bot_eth": 0.0,
   "returned_txs": [],
   "public_statement": "On-chain message from the copier EOA to itself (tx 0x44b559c8): " + msg_text.replace("\n", " ")},
 "raw_refs": refs,
 "rawref_gaps": [{"field": "loot.gross_loot_eth", "why": "proceeds are DAI; no saved ETH price for the block; left null"},
                 {"field": "attacker.funding", "why": "Tornado funding per incident.json (tx 0x4ec892aa, block 16817962) taken from the incident, not re-opened here"}],
 "discrepancies": disc + [
   "attacker_block (16818013) is AFTER the bot block (16817996): the attacker's first call came 17 blocks later, so blocks_ahead from attacker_block would be negative. The meaningful reference is the attacker's deploy (16817993), which the bot's deploy copy followed by one block and the bot's exploit by three.",
   "Strictly the copier did not replay an attacker tx: it re-deployed the attacker's contract with its own owner constant and called an entry point (0x863df8af, DAI) the attacker never called. Whether the attacker would have used that entry point is unknown."],
 "evidence_notes": [
   f"Creation calldata of the copier's deploy (tx 0x725db76c, block 16817994) and the attacker's deploy (tx 0x50dc9c91, block 16817993) is {len(a_in)//2-1:,} bytes each and differs in exactly {n_diff} bytes = four 20-byte occurrences of the attacker EOA 0xb2698c2d replaced by 0x5f259d0b at offsets {starts}; the hard-coded 0xb66cd966 is in both (recomputed from data/raw/rpc/tx_*.json; incidents/euler-copybot-2023/bytecode_diff.json). Both deploys used exactly 4,181,203 gas.",
   f"Block 16817996 position 0: tx 0xc310a0af calls the copy's entry 0x863df8af: Aave V2 flash loan {flash:,.0f} DAI, {out_euler:,.2f} DAI out of Euler, {repay:,.0f} DAI repaid, {net_dai:,.2f} DAI left in the copy (trace in data/raw/rpc/trace_tx_0xc310a0af....json).",
   "The attacker's first call to its own contract used the WETH entry 0xa91864d4 in block 16818013 and ran out of gas; its first success was block 16818024. It never called the DAI entry point 0x863df8af, which exists in its identical bytecode.",
   f"Copier's withdraw() (tx 0xdae809e4, block {wd_block}) transfers {wd_out[0][1]:,.2f} DAI to 0xb66cd966, the address hard-coded in both contracts; calls to the copies by other EOAs reverted (incident.json).",
   "Ordering: tip 37.9 gwei vs 17.5 gwei for index 1, no coinbase payment; winning builder Flashbots, 0.09425 ETH. Owner claim 'MEV bot' rests only on the copier's own on-chain message; on-chain it is a fresh single-purpose EOA."],
 "incident_dir": f"incidents/{S}",
}
write(S, [row])
