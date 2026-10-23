"""Extract row for shoco-2023 -> data/extract/shoco-2023.json. Run from project root: .venv/bin/python scripts/dataset/extract_shoco-2023.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _x6 import *

S = "shoco-2023"
inc = load(f"incidents/{S}/incident.json")
r = load(f"incidents/{S}/race.json")
rep = load(f"incidents/{S}/anvil_replay.json")
BOT = "0x2e832f044b4a0a0b8d38166fe4d781ab330b05b9efa9e72a7a0895f1b984084b"
ATK = "0x2f2c3c1c648f6ef0fc3600a91ad389daeb6c76602c4bf0100475696535b6f84f"
CONTRACT = "0x000000000000660def84e69995117c0176ba446e"
WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
disc = []

b = txrow(r, BOT); a = txrow(r, ATK)
coinbase = eth(b["coinbase_transfer_wei"]); tip = eth(b["priority_fee_total_wei"])
gas_total = b["gas_used"] * b["gas_price_gwei"] * 1e9 / 1e18

# bot trace: WETH deposit (working capital) and withdraw
t = load(f"data/raw/rpc/trace_tx_{BOT}.json"); t = t.get("result", t)
dep = wd = None
def walk(c):
    global dep, wd
    if c["to"].lower() == WETH and c.get("input", "")[:10] == "0xd0e30db0": dep = int(c["value"], 16)
    if c["to"].lower() == WETH and c.get("input", "")[:10] == "0x2e1a7d4d": wd = int(c["input"][10:74], 16)
    for x in c.get("calls") or []: walk(x)
walk(t)
gross = (wd - dep) / 1e18
if abs(gross - 4.158888932826055) > 1e-12:
    disc.append(f"gross recomputed {gross!r} vs incident 4.158888932826055")

# counterfactual: attacker's tx alone on the anvil fork
at = load(f"incidents/{S}/anvil_attacker_alone_trace.json"); at = at.get("result", at)
awd = []
def walk2(c):
    if c["to"].lower() == WETH and c.get("input", "")[:10] == "0x2e1a7d4d": awd.append(int(c["input"][10:74], 16))
    for x in c.get("calls") or []: walk2(x)
walk2(at)
cf = awd[0] / 1e18
assert rep["A_alone_at_start_of_block"]["status"] == "0x1"
assert rep["B_then_A"][1]["status"] == "0x0" and rep["B_then_A"][0]["status"] == "0x1"

# bot contract balance delta across the block
bal = lambda blk: int(load(f"data/raw/rpc/bal_0x000000000000660deF84E69995117c0176bA446E_{blk}.json")["result"], 16) / 1e18
b0, b1 = bal(16440978), bal(16440979)
if abs((b1 - b0) - (gross - coinbase)) > 1e-9:
    disc.append(f"contract balance delta {b1-b0} != gross - coinbase {gross-coinbase}")
bot_net = gross - coinbase - gas_total
refund = sum(int(x["value_wei"]) for x in r["txs"] if x["from"].lower() == r["block"]["fee_recipient"].lower() and (x["to"] or "").lower() in (CONTRACT, b["from"].lower())) / 1e18

a_sum = bvh.auction_summary(f"incidents/{S}/race.json", BOT)
share = coinbase / a_sum["winning_bid_eth"]
refs = {
 "bot.block": "data/raw/rpc/block_16440979.json", "bot.position": "data/raw/rpc/block_16440979.json",
 "attacker_block": "data/raw/rpc/block_16440979.json",
 "loot.gross_loot_eth": [f"data/raw/rpc/trace_tx_{BOT}.json"],
 "loot.coinbase_paid_eth": "data/raw/rpc/trace_block_16440979.json",
 "loot.priority_fee_paid_eth": "data/raw/rpc/receipts_16440979.json",
 "loot.builder_refund_to_bot_eth": "data/raw/rpc/block_16440979.json",
 "loot.bot_net_eth": [f"data/raw/rpc/trace_tx_{BOT}.json", "data/raw/rpc/trace_block_16440979.json", "data/raw/rpc/receipts_16440979.json"],
 "fate.kept_by_bot_eth": [f"data/raw/rpc/trace_tx_{BOT}.json", "data/raw/rpc/trace_block_16440979.json", "data/raw/rpc/receipts_16440979.json"],
 "bot_contract_balance": [f"data/raw/rpc/bal_0x000000000000660deF84E69995117c0176bA446E_{x}.json" for x in (16440978, 16440979, 16441000, 16445000, 16460000, 16480000, 16500000, 16600000)],
 "anvil_replay": [f"incidents/{S}/anvil_replay.json", f"incidents/{S}/anvil_attacker_alone_trace.json"],
}
row = {
 "slug": S, "name": inc["name"], "date_utc": iso(r["block"]["timestamp"]), "chain": "ethereum",
 "orig_verdict": inc["verdict"],
 "race_type_proposed": "beat-pending-attack",
 "race_type_reason": "A generic searcher bot's tx at index 0 of block 16440979 runs the same victim calls (router swap, SHOCO.deliver, pair.skim, WETH->ETH) as the attacker's tx at index 15, which then reverted. A local fork replay shows the attacker's tx alone succeeds with the identical gain, and bot-first-then-attacker reproduces the revert.",
 "one_liner": f"At block 16440979 a generic searcher bot (index 0, 0.092 ETH coinbase) ran the SHOCO deliver/skim exploit calls ahead of the attacker's tx (index 15, reverted) and kept {gross:.4f} ETH gross, about {bot_net:.2f} ETH net. Fork replay: the attacker alone would have got the same {cf:.4f} ETH.",
 "attacker": {"eoa": inc["attacker"]["eoas"][0], "eoas": inc["attacker"]["eoas"],
              "contracts": [x.split(" ")[0] for x in inc["attacker"]["contracts"]], "funding": "unknown",
              "funding_tx": inc["attacker"]["funding_tx"]["txs"][0], "deploy_tx": inc["attacker"]["deploy_tx"], "deploy_block": 16440959,
              "attack_txs": [{"hash": ATK, "block": 16440979, "index": a["index"], "status": "reverted",
                              "role": "attack call 0xb05f303c via Balancer flash loan; reverted with ds-math-sub-underflow at pair.skim after the bot had drained the pair (tip 3 gwei)"}],
              "none_reason": None},
 "bot": {"label": "anon searcher", "eoa": b["from"], "contract": b["to"], "tx": BOT, "block": 16440979, "position": b["index"],
         "status": "success" if b["status"] == 1 else "reverted", "priority_fee_gwei": b["priority_fee_gwei"]},
 "bots_other": [],
 "evidence_level_mempool": "in-block-only",
 "mempool_note": "In-block evidence only: January 2023 is before the mempool-dumpster archive (starts 2023-08-07). Whether the bot saw the attacker's pending tx or found the bug from the attack contract deployed four minutes earlier (block 16440959) is unknowable. The bot's index-0 placement despite a lower effective gas price (15.61 vs 16.61 gwei) and a 0.092 ETH coinbase transfer suggests bundle-style placement (inferred; Flashbots bundle API is gone).",
 "trigger": {"kind": None, "tx": None, "first_seen_utc_ms": None, "first_seen_utc": None, "sources": None,
             "note": "No mempool first-seen exists. The attacker's contract 0x15d684b4 was deployed in block 16440959 (2023-01-19T12:50:11Z) and its attack tx 0x2f2c3c1c landed in the same block as the bot's tx."},
 "attacker_block": 16440979,
 "attacker_block_note": "Attacker's attack tx 0x2f2c3c1c is in the same block as the bot's, at index 15 (tip 3 gwei, effective 16.61 gwei); it reverted.",
 "attacker_reference": {"kind": "attack-tx", "block": 16440979, "tx": ATK},
 "auction": a_sum,
 "loot": {
   "scope": "bot-tx",
   "gross_loot_eth": round(gross, 15),
   "gross_loot_method": f"WETH withdrawn to the bot contract ({wd/1e18:.12f}) minus the ETH it wrapped as working capital ({dep/1e18:.12f}), from the callTracer trace; the pair's WETH was the only asset taken",
   "captured_native": {"amount": round(gross, 15), "unit": "ETH", "desc": "WETH out of the SHOCO/WETH Uniswap V2 pair, unwrapped to ETH in the bot contract"},
   "captured_usd": None, "captured_usd_source": None,
   "coinbase_paid_eth": coinbase, "priority_fee_paid_eth": round(tip, 12),
   "builder_refund_to_bot_eth": refund, "builder_payout_to_victim_eth": None,
   "bot_net_eth": round(bot_net, 9),
   "loot_note": f"bot_net_eth = {gross:.6f} gross - {coinbase:.6f} ETH coinbase - {gas_total:.6f} ETH gas (incl. {tip:.6f} ETH tip) = {bot_net:.6f} ETH. The bot contract's balance rose {b0:.4f} -> {b1:.4f} ETH across the block (= gross - coinbase). The coinbase payment is {share*100:.1f}% of the {a_sum['winning_bid_eth']:.4f} ETH winning bid ({(coinbase+tip)/a_sum['winning_bid_eth']*100:.1f}% counting the tip, the figure in incident.json). No builder refund in the block. No USD figure is saved for 2023-01-19."},
 "fate": {
   "return_status": "none-found",
   "returned_by_bot_eth": None, "returned_by_builder_eth": None, "returned_total_eth": None, "returned_to": None,
   "returned_desc": "No return or bounty found. The proceeds stayed in the bot contract: its ETH balance is unchanged at blocks 16440979, 16441000 and 16445000 and later moves are not attributable (the contract is a shared 'MEV Bot' used by other EOAs). No public statement found.",
   "bounty_kept_eth": None, "bounty_desc": None, "kept_by_bot_eth": round(bot_net, 9),
   "returned_txs": [], "public_statement": None},
 "raw_refs": refs,
 "rawref_gaps": [{"field": "loot.captured_usd", "why": "no saved ETH price for 2023-01-19; not converted"}],
 "discrepancies": disc + [
   "Not a calldata copy: the attacker used a Balancer flash loan and one deliver/skim cycle (36-byte calldata); the bot self-funded 1.4676 ETH and ran 12 skim rounds with 19 deliver calls (7,780-byte calldata, own format, not decoded). The match is the victim-facing call pattern and the identical gross gain.",
   "The attacker's reverted tx cost 0.005252 ETH of gas (incident.json); his forgone gain equals the bot's gross to the wei per the fork replay."],
 "evidence_notes": [
   f"Fork replay at block 16440978 (incidents/shoco-2023/anvil_replay.json, anvil_attacker_alone_trace.json): the attacker's tx alone succeeds and unwraps {cf!r} ETH of WETH, equal to the bot's gross {gross!r}; bot-first-then-attacker reproduces the attacker's revert; attacker-first-then-bot makes the bot revert.",
   "Both txs make the same victim-facing calls: Uniswap V2 router swapTokensForExactTokens WETH->SHOCO from pair 0x806b6c68, SHOCO.deliver (0x3bd5d173), pair.skim (0xbc25cf77) to the caller, then WETH->ETH (incident.json bots[0].replay_evidence). Only these two txs in the block touched the pair or token.",
   "Block 16440979: bot at index 0 (effective 15.61 gwei, coinbase 0.0921 ETH), attacker at index 15 (16.61 gwei, 3 gwei tip, reverted). Winning builder Flashbots delivered 0.1327 ETH; the winning block arrived 843 ms before the slot (race.json).",
   "The attacker's attack contract was created four minutes earlier (block 16440959, tx 0xf656affc), so a pending attack tx, the deployed contract, or independent discovery are all possible sources for the bot (unknowable).",
   "Bot is a generic searcher (contract 0x...660d is a shared MEV bot used by other EOAs), not Yoink or c0ffeebabe."],
 "incident_dir": f"incidents/{S}",
}
write(S, [row])
