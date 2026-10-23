"""Extract rows for alkemi-2026 -> data/extract/alkemi-2026.json (two sub-rows). Run from project root:
.venv/bin/python scripts/dataset/extract_alkemi-2026.py   then   .venv/bin/python scripts/dataset/check_extract.py alkemi-2026
Row 'wbtc-yoink': Yoink replays an already-reverted WBTC-pool attack tx (post-failure-replay). Row 'eth-vault-copiers': late copies after the DHL attacker."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _x6 import *  # noqa: F401,F403

S = "alkemi-2026"
D = f"incidents/{S}"
inc = load(f"{D}/incident.json")
r81 = load(f"{D}/race_24627181.json")
r80 = load(f"{D}/race_24627180.json")
r79 = load(f"{D}/race_24626979.json")
r55 = load(f"{D}/race_24627055.json")
r85 = load(f"{D}/race_24627185.json")
r82 = load(f"{D}/race_24627182.json")
YO = "0x7acef47065602187de04861aed2cd997111c3e29c8134d370bb0d035f395ec18"
T46 = "0x726bd90c84cd7e1a3dafd54ce968f038f1fe22d0d439bd8a55fbab60f0e5aad2"
DHL = "0xa17001eb39f867b8bed850de9107018a2d2503f95f15e4dceb7d68fff5ef6d9d"
DHLD = "0xcb59da3af2d08e7823e923bd2d3f048c4dce1ed65e6e56c5ad4969b3c2700fe1"
LEFT = "0xef75d0e580a610a7ffa3db20f20a89af0a329e1801fa1642548d8cce9f2b06cc"
COMP = "0xd4ec3e344fe270f34078e8cabc7f7bee36204049bc9c61febce3c1668b8df42c"
MSG = "0x325a67f87a49405154bc7d83e236539143d96381a16611a6bc1ea0b71592ed64"
YC = "0x80bf7db69556d9521c03461978b8fc731dbbd4e4"
VAULT = "0x8125afd067094cd573255f82795339b9fe2a40ab"
disc = []

PRICE = "data/raw/defillama/alkemi2026_eth_price_1773147059.json"
ETHP = load(PRICE)["coins"]["coingecko:ethereum"]["price"]

# ---------------- row 1: Yoink ----------------
y = txrow(r81, YO)
coinbase = eth(y["coinbase_transfer_wei"])
prio = eth(y["priority_fee_total_wei"])
refund_tx = txrow(r81, "0x3533647ba3607b1d7d27cee78f642bc0985cd347e2fc81d7ff671df02a50eac2")
assert refund_tx["from"].lower() == r81["block"]["fee_recipient"].lower() and refund_tx["to"].lower() == YC and refund_tx["index"] == 3
refund = eth(refund_tx["value_wei"])
tr = load(f"data/raw/rpc/trace_{YO}.json")["result"]
gross_wei = []
def walk(c, parent=None):
    # ETH delivered to the Yoink contract by WETH.withdraw after the UniV3 swap = the swap proceeds
    v = int(c.get("value", "0x0"), 16)
    if parent and parent.get("to", "").lower() == "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2" and c.get("to", "").lower() == YC and v and not c.get("error"):
        gross_wei.append(v)
    for x in c.get("calls") or []:
        walk(x, c)
walk(tr)
# the withdraws: 5 ETH (flash-loaned WETH), 2.0 x7 style vault payouts are NOT via WETH; the swap proceeds are the 10.2358... one
gross = max(gross_wei) / 1e18
assert abs(gross - 10.235881010725304) < 1e-12
assert abs(coinbase - gross * 0.999) < 1e-9          # msg.value 999 wei = 999 per mille
bot_net = gross - coinbase + refund
paid = r81["winner"]["bid_value_eth"]
a1 = bvh.auction_summary(f"{D}/race_24627181.json", YO)
t46 = txrow(r80, T46)
assert t46["index"] == 226 and t46["status"] == 0
comp = txrow(r85, COMP)
assert comp["index"] == 305 and comp["status"] == 1
replay = load(f"{D}/replay_diff.json")
assert replay["identical_prefix_lengths"]["yoink_vs_t46"] == 16

BLK81 = "data/raw/rpc/block_24627181.json"
refs1 = {
    "bot.block": BLK81, "bot.position": [BLK81, "data/raw/rpc/receipts_24627181.json"],
    "attacker_block": ["data/raw/rpc/block_24627180.json", "data/raw/rpc/receipts_24627180.json"],
    "loot.gross_loot_eth": f"data/raw/rpc/trace_{YO}.json",
    "loot.captured_usd": [PRICE, f"data/raw/rpc/trace_{YO}.json"],
    "loot.coinbase_paid_eth": ["data/raw/rpc/trace_block_24627181.json", f"data/raw/rpc/trace_{YO}.json"],
    "loot.priority_fee_paid_eth": ["data/raw/rpc/receipts_24627181.json", BLK81],
    "loot.builder_refund_to_bot_eth": BLK81,
    "loot.bot_net_eth": [f"data/raw/rpc/trace_{YO}.json", BLK81, "data/raw/rpc/trace_block_24627181.json"],
    "evidence_level_mempool": ["data/raw/mempool-dumpster/2026-03-10.csv.zip", f"{D}/mempool_coverage.json"],
    "returns_message": f"data/raw/rpc/tx_{MSG}.json",
}
row1 = {
    "slug": S, "sub": "wbtc-yoink", "name": inc["name"] + " - WBTC pool (Yoink)", "date_utc": iso(r81["block"]["timestamp"]), "chain": "ethereum",
    "orig_verdict": inc["verdict"],
    "race_type_proposed": "post-failure-replay",
    "race_type_reason": "Yoink's tx (block 24627181, idx 0) contains the same 16 state-changing Alkemi calls (+2 withdraws) as the deploy+attack tx 0x726bd90c of EOA 0x46c403e3, which was mined one block earlier "
                        "(24627180, idx 226) and reverted out of gas. Nothing of that actor's was pending when Yoink landed; Yoink retried with a higher gas limit. "
                        "The on-chain message sender 0x8366d87b ran a different program (replay_diff.json: 0 shared calls) and its attack tx landed in 24627185, after Yoink's.",
    "one_liner": "Yoink drained Alkemi's WBTC pool (0.299 WBTC, 10.24 ETH) one block after another attacker's identical-call tx ran out of gas; a different bot-hunter later complained Flashbots leaked his tx, but Yoink replayed the reverted one.",
    "attacker": {"eoa": "0x46c403e3dcaf219d9d4de167ccc4e0dd8e81eb72", "eoas": ["0x46c403e3dcaf219d9d4de167ccc4e0dd8e81eb72"],
                 "contracts": ["0xd211ddce0592f2f56633ec5b053f828408c49e3b (nested, caller of Alkemi)", "0x09e9db97 (top-level CREATE of the tx)"],
                 "funding": None, "funding_tx": None, "deploy_tx": T46, "deploy_block": 24627180,
                 "attack_txs": [{"hash": T46, "block": 24627180, "index": 226, "status": "reverted",
                                 "role": "deploy+attack in the constructor, gas limit 14,974,454, tip 37 wei; runs out of gas in the 7th self-liquidation (14,344,401 gas used)"}],
                 "none_reason": None,
                 "first_exploiter_of_alkemi": {"eoa": "0x0ed1c01b8420a965d7bd2374db02896464c91cd7", "tx": DHL, "block": 24626979, "note": "ETH-vault drain 43.45395 ETH, 40 min earlier; a different pool and a different call sequence; see sub-row eth-vault-copiers"}},
    "bot": {"label": "Yoink", "eoa": y["from"], "contract": YC, "tx": YO, "block": 24627181, "position": y["index"], "status": "success", "priority_fee_gwei": y["priority_fee_gwei"]},
    "bots_other": [
        {"label": "message sender (third party WBTC hunter)", "eoa": "0x8366d87bfb60e4f9574bf0f7e3f42744e79c7b76", "contract": "0x54ad675428e704b0e97c147da46f8f8743decb81",
         "tx": COMP, "block": 24627185, "position": comp["index"], "status": "success",
         "role": "deployed at 24627180 idx 2, attack tx landed 4 blocks after Yoink with borrow(WBTC, 0) because the pool was empty; fork replay on the pre-Yoink state takes all 29,980,756 sat WBTC. "
                 "On-chain message to Yoink at block 24627239 (tx 0x325a67f8): 'Fuck you flashbots. Why did you leak my attack transaction to yoink?'. Different call program from Yoink's."},
        {"label": "0x5af00b07 (same helper bytecode as the message sender)", "eoa": "0x5af00b073abb9f88832353bd4c919caaa114c972", "tx": "0xdc32b0cf4268172ab3683b4ee617dbaaab0d8fc81324e8a1f229565a821f7b81",
         "block": 24627182, "position": 2, "status": "success", "role": "took the last 55,199 sat WBTC the block after Yoink (tip 1.5 gwei)"}],
    "evidence_level_mempool": "absent-from-archive",
    "mempool_note": "mempool-dumpster covers 2026-03-10 (csv; no source log in 2026). None of the 10 Alkemi-touching txs, the 4 deploy txs or the message tx appears in it, while 55-63% of the txs of the same blocks do "
                    "(incidents/alkemi-2026/mempool_coverage.json). So the reverted attacker tx, the message sender's pending tx and Yoink's tx are all private flow or missed: when Yoink first saw anything is unknown, not none.",
    "trigger": {"kind": "attacker-tx-landed-reverted", "tx": T46, "first_seen_utc_ms": None, "first_seen_utc": None, "sources": None,
                "note": "The reverted tx was mined at 12:50:47Z (block 24627180). Yoink's builder 'I can haz block?' put the 5-tx block (Yoink tx at idx 0) into its first bid for the next slot at -1178 ms (12:50:57.8Z), "
                        "i.e. 10.8 s after the block time, and won at -1041 ms. No bid from that builder exists for the slot of block 24627180. A Yoink reaction to the message sender's pending tx cannot be excluded or shown."},
    "attacker_block": 24627180,
    "attacker_block_note": "The attacker's tx landed in the block immediately before Yoink's (BuilderNet block, idx 226 of 332) and reverted.",
    "attacker_reference": {"kind": "attack-tx", "block": 24627180, "tx": T46},
    "auction": {**a1, "auction_note": "Winning builder 'I can haz block?' (fee recipient 0x229b8325) built a 5-tx block, bid 1.0353 ETH vs a normal ~0.01 ETH, via the Flashbots relay (single submission at -1041 ms, 10 escalating bids from -1178 ms); delivered by Flashbots and Ultra Sound. "
                                                    "Titan answered with 247 bids (none for that block hash); Ultra Sound/Agnostic/Aestus hold no bids this old."},
    "loot": {
        "scope": "bot-tx", "gross_loot_eth": round(gross, 12),
        "gross_loot_method": "ETH delivered to the Yoink contract by WETH.withdraw after swapping 29,884,523 sat WBTC on Uniswap V3 (WBTC taken from Alkemi: 1.29925557 withdrawn minus 1.0 supplied = 0.29925557; 41,034 sat swapped separately for 0.014 ETH that went back into the Alkemi vault)",
        "captured_native": {"amount": "0.29925557", "unit": "WBTC", "desc": "WBTC taken from Alkemi's WBTC pool via 7 self-liquidations; 0.29884523 swapped to ETH on UniV3"},
        "captured_usd": round(gross * ETHP, 0), "captured_usd_source": f"gross ETH x DefiLlama ETH price {ETHP:.2f} at 1773147060 (block time)",
        "coinbase_paid_eth": coinbase, "priority_fee_paid_eth": prio, "builder_refund_to_bot_eth": refund, "builder_payout_to_victim_eth": None,
        "bot_net_eth": round(bot_net, 6),
        "loot_note": f"bot_net = gross {gross:.6f} - coinbase {coinbase:.6f} + builder refund {refund:.6f} (block idx 3 from 0x229b8325 to the Yoink contract); tip 0, base fee ~0.078 gwei x 12.88M gas ~ 0.001 ETH not deducted. "
                     f"Coinbase = 999 per mille of gross (msg.value 999 wei). The builder passed {paid:.4f} ETH to the proposer, so the 10.2256 ETH coinbase minus 1.0353 proposer minus 9.1907 refund ~ 0 (the remaining ~0.0003 ETH is other txs' fees). "
                     "Yoink's tx was only the WBTC leg; the 43.45 ETH ETH-vault drain 40 minutes earlier is the DHL attacker's.",
    },
    "fate": {
        "return_status": "none-found", "returned_by_bot_eth": None, "returned_by_builder_eth": None, "returned_total_eth": None, "returned_to": None,
        "returned_desc": "No return found: Yoink EOA tx list 24627181-26239901 and Yoink contract internal txs 24627181-24700000 show no transfer to Alkemi's admin 0x5bea205a or to the proxy; Alkemi's admin has no transactions 24626979-26300000. "
                         "The only on-chain message is the complaint to Yoink (block 24627239). Unknown != none.",
        "bounty_kept_eth": None, "bounty_desc": None, "kept_by_bot_eth": None,
        "returned_txs": [{"tx": MSG, "eth": None, "block": 24627239, "time_utc": "2026-03-10T13:02:35Z",
                          "note": "on-chain message from 0x8366d87b to Yoink's EOA (not a return)"}],
        "public_statement": "none found (BlockSec's roundup covers only the 43.45 ETH attack; DeFiHackLabs cites a Blockaid X post, not fetched)"},
    "raw_refs": refs1, "rawref_gaps": [{"field": "trigger.first_seen_utc_ms", "why": "no tx of this race is in mempool-dumpster; first-seen unknown"}],
    "discrepancies": [
        "Prior lead (research/launch-gap/part_2026.json) linked the complaint to 'Alkemi' only by inference and listed Yoink as copying the DHL attacker; the DHL attack tx 0xa17001eb is in a different pool and shares no call with Yoink's tx."],
    "evidence_notes": [
        f"{D}/replay_diff.json: 16 of 16 state-changing Alkemi calls of the reverted tx 0x726bd90c equal Yoink's first 16 (supply 1 WBTC, supply 2.5 ETH, 7x borrow 2 ETH + liquidateBorrow(self) 2.002 ETH); Yoink adds 2 withdraws.",
        "Fork replay (local anvil, block 24627180 state): the reverted tx at its own 14,974,454 gas limit reverts with exactly the on-chain gas used (14,344,401); with a 30M limit it succeeds and sends 29,884,523 sat WBTC to the attacker EOA = the amount Yoink swapped.",
        "The message sender's own attack tx replayed on state after block 24627180 (traceCall) moves all 29,980,756 sat WBTC to 0x460eba8f; on the real state after Yoink it moves 55,199. Its calls share nothing with Yoink's.",
        "Alkemi balances (end of block): WBTC 0.29980756 until 24627180, 0.00055199 after 24627181, 0 after 24627182; ETH vault 44.17125 before 24626979, 0.7173 after, 0 from 24627055.",
        ""],
    "incident_dir": D,
}
row1["attacker"]["eoa"] = "0x46c403e3dcaf219d9d4de167ccc4e0dd8e81eb72"

# ---------------- row 2: late copiers after the DHL attacker ----------------
dl = txrow(r79, DHL)
assert dl["index"] == 3 and dl["status"] == 1
dd = txrow(r79, DHLD)
lf = txrow(r55, LEFT)
assert lf["index"] == 5 and lf["status"] == 1
BOT2 = "0xbf65507df61a410a47be755399ab72ba60cdca44"
VAULT_ = VAULT
trl = load(f"data/raw/rpc/trace_{LEFT}.json")["result"]
gross2 = 0
def walk2(c, ok=True):
    global gross2
    ok = ok and not c.get("error")
    v = int(c.get("value", "0x0"), 16)
    if ok and v and c["from"].lower() == VAULT_ and c.get("to", "").lower() == BOT2:
        gross2 += v
    if ok and v and c["to"].lower() == VAULT_ and c.get("from", "").lower() == BOT2:
        gross2 -= v
    for x in c.get("calls") or []:
        walk2(x, ok)
walk2(trl)
# the walk above sees only vault->bot payouts; the net vault outflow (payouts minus the bot's own supply routed bot->proxy->vault) is in calls_table.json
gross2 = round(next(t for t in load(f"{D}/calls_table.json") if t["hash"] == LEFT)["eth_out_of_alkemi_vault_net"] * 1e18)
rc = [t for t in load("data/raw/rpc/receipts_24627055.json") if False]
gas_cost2 = lf["gas_used"] * lf["gas_price_gwei"] / 1e9
a2 = bvh.auction_summary(f"{D}/race_24627055.json", LEFT)
refs2 = {
    "bot.block": "data/raw/rpc/block_24627055.json", "bot.position": ["data/raw/rpc/block_24627055.json", "data/raw/rpc/receipts_24627055.json"],
    "attacker_block": ["data/raw/rpc/block_24626979.json", "data/raw/rpc/receipts_24626979.json"],
    "loot.gross_loot_eth": [f"data/raw/rpc/trace_{LEFT}.json", f"{D}/calls_table.json"],
    "loot.coinbase_paid_eth": "data/raw/rpc/trace_block_24627055.json",
    "loot.priority_fee_paid_eth": ["data/raw/rpc/receipts_24627055.json", "data/raw/rpc/block_24627055.json"],
    "loot.bot_net_eth": [f"data/raw/rpc/trace_{LEFT}.json", "data/raw/rpc/receipts_24627055.json", "data/raw/rpc/block_24627055.json"],
    "evidence_level_mempool": ["data/raw/mempool-dumpster/2026-03-10.csv.zip", f"{D}/mempool_coverage.json"],
}
row2 = {
    "slug": S, "sub": "eth-vault-copiers", "name": inc["name"] + " - ETH vault copiers", "date_utc": iso(r55["block"]["timestamp"]), "chain": "ethereum",
    "orig_verdict": inc["verdict"],
    "race_type_proposed": "late-copy",
    "race_type_reason": "The DHL-listed attacker's deploy (idx 2) and attack (idx 3) landed together in block 24626979 and drained 43.45395 ETH from the ETH vault. Every other caller of the same sequence landed later: two no-gain copies one block later (24626980, idx 114/115), "
                        "and 0x4c452e82 took the 0.7173 ETH left in the vault 76 blocks (15 min) after. Nobody was ahead of the attacker and none of these is Yoink.",
    "one_liner": "The 43.45 ETH Alkemi ETH-vault drain (block 24626979) was never front-run: all 7 later txs running the self-liquidation call sequence landed 1 to 444 blocks later, the best taking 0.72 ETH of leftovers. Yoink was not involved.",
    "attacker": {"eoa": "0x0ed1c01b8420a965d7bd2374db02896464c91cd7", "eoas": ["0x0ed1c01b8420a965d7bd2374db02896464c91cd7"], "contracts": ["0xe408b52aefb27a2fb4f1cd760a76daa4bf23794b"],
                 "funding": None, "funding_tx": "0xcec7c8eb14e78f1cabc635db28631b9c95b7b61cb18308bde326dafda68eda9f", "deploy_tx": DHLD, "deploy_block": 24626979,
                 "funding_note": "0.09975 ETH from 0xac9f360a... at block 24625237 (2026-03-10T06:19:11Z); source not classified",
                 "attack_txs": [{"hash": DHLD, "block": 24626979, "index": 2, "status": "success", "role": "deploy attack contract 0xe408b52a"},
                                {"hash": DHL, "block": 24626979, "index": 3, "status": "success", "role": "flash loan 51 WETH, supply 50, borrow 39.5, self-liquidate 39.5395, withdraw; +43.45395 ETH to the EOA"}],
                 "none_reason": None},
    "bot": {"label": "anon searcher (0x4c452e82)", "eoa": lf["from"], "contract": BOT2, "tx": LEFT, "block": 24627055, "position": lf["index"], "status": "success", "priority_fee_gwei": lf["priority_fee_gwei"]},
    "bots_other": [
        {"label": "0xb180ef1b -> 0x3dfb97ff (copy 1)", "eoa": "0xb180ef1bf6fb3e9a0b5db4460e4db804e946cc8a", "tx": "0x4054e1d69035afc993ef80774cc83f5feb0b5d2542f9ff7fa1bbf254a6c79ea6", "block": 24626980, "position": 114, "status": "success", "role": "same sequence with a 1 ETH supply; gained nothing"},
        {"label": "0x6bc22cd3 -> 0x3dfb97ff (copy 2)", "eoa": "0x6bc22cd3705b86c1d423d80001721b9c8101d2e1", "tx": "0x7c65ddf1f49c336739d49cc8321346621c2de562448d1a1afdc10a15ac44c4fc", "block": 24626980, "position": 115, "status": "success", "role": "same contract, next index; gained nothing"},
        {"label": "0xc9a5643e", "eoa": "0xc9a5643ed8e4cd68d16fe779d378c0e8e7225a54", "tx": "0x5460ffcd02735127d35e7bddba6eff1e719f6459a04db0b23c9e8e7ef7491b57", "block": 24627182, "position": 0, "status": "success", "role": "copy that collected the 0.014 ETH Yoink had paid into the vault"},
        {"label": "0x000040d6c85a", "eoa": "0x000040d6c85a13a1aa74565fde87e499dc023c6f", "tx": "0x0331c45048016884067e9d0003068a11ac799a197a78e74aa0b87f3d6989159f", "block": 24627423, "position": 106, "status": "reverted", "role": "last copy, 13:39Z"}],
    "evidence_level_mempool": "absent-from-archive",
    "mempool_note": "mempool-dumpster covers 2026-03-10 but neither the attacker's deploy/attack txs nor any copy appears in it (55-63% of the txs of the same blocks do). Private flow or missed; first-seen unknown.",
    "trigger": {"kind": None, "tx": None, "first_seen_utc_ms": None, "first_seen_utc": None, "sources": None, "note": "no pre-inclusion first-seen exists for the attacker or any copier"},
    "attacker_block": 24626979,
    "attacker_block_note": "Attacker's deploy and attack landed together in Titan's block 24626979 (idx 2 and 3), delivered by Ultra Sound.",
    "attacker_reference": {"kind": "attack-tx", "block": 24626979, "tx": DHL},
    "auction": {**a2, "auction_note": "Block 24627055 (Titan builder). The attacker's own block 24626979 has 450 bids (Flashbots 197, Titan 253), winner Titan 0.01125 ETH via Ultra Sound: a routine auction, no bot involved."},
    "loot": {
        "scope": "bot-tx", "gross_loot_eth": round(gross2 / 1e18, 12),
        "gross_loot_method": "net ETH leaving the Alkemi vault 0x8125afd0 in the successful frames of the tx trace (vault payouts minus ETH paid into the vault, which includes the copier's own 50 ETH supply); incidents/alkemi-2026/calls_table.json",
        "captured_native": {"amount": f"{gross2/1e18:.8f}", "unit": "ETH", "desc": "leftover ETH in the Alkemi vault after the 43.45 ETH drain"},
        "captured_usd": None, "captured_usd_source": None,
        "coinbase_paid_eth": eth(lf["coinbase_transfer_wei"]), "priority_fee_paid_eth": eth(lf["priority_fee_total_wei"]), "builder_refund_to_bot_eth": None, "builder_payout_to_victim_eth": None,
        "bot_net_eth": round(gross2 / 1e18 - gas_cost2, 6),
        "loot_note": f"bot_net = gross - gas (gas used {lf['gas_used']} x {lf['gas_price_gwei']:.4f} gwei = {gas_cost2:.6f} ETH, incl. 0.2 gwei tip); Balancer flash loan of 51 WETH repaid in the tx. Attacker's own take: 43.45395 ETH."},
    "fate": {"return_status": "none-found", "returned_by_bot_eth": None, "returned_by_builder_eth": None, "returned_total_eth": None, "returned_to": None,
             "returned_desc": "No return or message found for the copiers or the attacker (attacker EOA scanned to block 24627400 only, it sent 3 ETH to look-alike addresses). Unknown != none.",
             "bounty_kept_eth": None, "bounty_desc": None, "kept_by_bot_eth": None, "returned_txs": [], "public_statement": "BlockSec roundup (loss ~$89K, root cause: self-liquidation + storage overwrite)"},
    "raw_refs": refs2, "rawref_gaps": [{"field": "trigger.first_seen_utc_ms", "why": "no tx in mempool-dumpster"}],
    "discrepancies": [],
    "evidence_notes": [
        "BlockSec weekly roundup (data/raw/web-alkemi/blocksec_roundup_mar9_mar15_2026.html) names tx 0xa170...6d9d as the attack: flash loan 51 WETH, supply, borrow 39.5, self-liquidate 39.5395, withdraw 93.5, profit 43.4 ETH.",
        "trace_filter (toAddress = Alkemi proxy, blocks 24600000-24650000) lists exactly 10 txs; the DHL attack is the first and no earlier call to the proxy exists in 24600000-24626978.",
        "Vault ETH at block ends: 44.17125 (24626978), 0.7173 (24626979), 0 from 24627055."],
    "incident_dir": D,
}
write(S, [row1, row2])
print("row1 net", bot_net, "row2 gross", gross2 / 1e18, "gas", gas_cost2)
