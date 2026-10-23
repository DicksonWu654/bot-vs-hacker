"""Extract incident dataset row for neemo-2025 -> data/extract/neemo-2025.json. Run from project root:
  .venv/bin/python scripts/dataset/extract_neemo-2025.py
Requires incidents/neemo-2025/{incident.json,race_22855567/8/9.json,call_diff.json,impl_diff.json,attacker_replay_local_fork.json,mempool_lookup_2025-07-05.json}."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _x5_common import *

S = "neemo-2025"
inc = jl(f"incidents/{S}/incident.json")
BOT = "0xb750e3165de458eae09904cc7fad099632860b0f"
ROUTER = "0x1a61249f6f4f9813c55aa3b02c69438607272ed3"
KEY = "0x7e9b11d0aa215e0f1a7f62534c7c93fc340d493d"
BOTTX = "0xa57ec56af91ec70517ca71ca50101958d9c2ec9fdb61edcf35a9081c375725c2"
UPG = "0xcd4a637da42ef5db0b7b6a1592c99a594530852f91e806d8c12ce0b587579373"
IMPLTX = "0x1040fe774fb487caa0102e876d13c5850e7181b6ee6cdf383a5cffd3d004e486"
A53 = "0xc8c2c1e8513604fa4a26d05a99dac0e4d5db32d7e6e23c386ddded2c64bcca27"
A97 = "0x6d5a765f8583b05134fcd588426e99b585ba045970f4b78ae7e19a7aafc5be0d"
RET_TEST = "0x9fce819f59a0e61d1b8571aaa1a4fb06bd037ae8f1263b0de4fe7cbccc17db23"
RET_MAIN = "0x0aede3f295d97291f22589b7dc71e783ee8ae6cc816f55c698376ee4c5362de9"
NEEMO_RET = "0x1671e4e1e610d4c5e693fc83f567a9f802287212"
RACE = f"incidents/{S}/race_22855569.json"
race = jl(RACE)
bt = race_tx(race, BOTTX)
blk = race["block"]
tracep = f"data/raw/rpc/trace_{BOTTX}.json"
trace = res(jl(tracep))
rcp_p, rcp = rpc_rcpt(BOTTX)
tx_p, txo = rpc_tx(BOTTX)
upg_p, upg = rpc_tx(UPG)
impl_p, impltx = rpc_tx(IMPLTX)
assert txo["from"].lower() == BOT and txo["to"].lower() == ROUTER and hx(txo["transactionIndex"]) == 0
assert upg["from"].lower() == KEY and hx(upg["blockNumber"]) == 22855568 and hx(txo["blockNumber"]) == 22855569

coinbase = eth(bt["coinbase_transfer_wei"])
prio = eth(bt["priority_fee_total_wei"])
gas_total = eth(hx(rcp["gasUsed"]) * hx(rcp["effectiveGasPrice"]))
wd = weth_withdraws(trace)
gross = sum(wd) / 1e18
net = gross - coinbase - gas_total
refund_wei, refund_txs = builder_to(race, [BOT, ROUTER])

auc = bvh.auction_summary(RACE, BOTTX)
assert auc["proposer_payment_tx"] and auc["bot_tx_in_winning_block"]
prop_paid = auc["proposer_paid_eth"]

rt_p, rt = rpc_tx(RET_TEST)
rm_p, rm = rpc_tx(RET_MAIN)
rtr_p, rtr = rpc_rcpt(RET_TEST)
rmr_p, rmr = rpc_rcpt(RET_MAIN)
assert rt["from"].lower() == BOT and rm["from"].lower() == BOT and rt["to"].lower() == NEEMO_RET and rm["to"].lower() == NEEMO_RET
assert hx(rtr["status"]) == 1 and hx(rmr["status"]) == 1
r_test, r_main = eth(hx(rt["value"])), eth(hx(rm["value"]))
returned = round(r_test + r_main, 6)
bounty = round(gross - returned, 6)
kept_net = round(net - returned, 9)
pct_ret = round(100 * returned / gross, 3)
hdr = lambda b: res(jl(f"data/raw/rpc/block_hdr_{b}.json"))
t_test, t_main = hx(hdr(hx(rtr["blockNumber"]))["timestamp"]), hx(hdr(hx(rmr["blockNumber"]))["timestamp"])
b_test, b_main = hx(rtr["blockNumber"]), hx(rmr["blockNumber"])
assert pct_ret == 80.0 or abs(pct_ret - 80.0) < 0.01
mp = jl(f"incidents/{S}/mempool_lookup_2025-07-05.json")
cd = jl(f"incidents/{S}/call_diff.json")
assert cd["same_call_sequence"] and cd["calls_differing_only_in_recipient_argument"] == 4 and cd["calls_with_identical_calldata"] == 2

disc = [
 "DeFiHackLabs-style trackers list the bot tx 0xa57ec56a as 'the attack' (data/evolution/per_exploit.json unverified_54cd_exp, attacker_eoa 0xb750e316). The key thief is 0x7e9b11d0; the bot is a different, long-running address.",
 "Neemo's message (and Defimon post 1475) cites 176.57 ETH sent to 0x4ec65e4d. That figure is the key-holder side (12.27 + 160.9 + 3.4 ETH, all on-chain), not the bot's haul: the bot took 114.534 ETH (106.929 weETH). The two sets of funds are separate.",
 "Defimon (post 1476) and the bot's own on-chain message both say the bot called the function 'a block later / before the original attacker'. On-chain, no attacker call to 0x03b79c24 exists at all (trace_filter, blocks 22855560-22862000, and the full Etherscan tx list), so the 'before' rests on the function being the attacker's, not on a competing tx.",
 "The bot statement quoted by Neemo ('no involvement ... automated software scanning the blockchain') is not an on-chain tx from the bot EOA; only two later bot messages (blocks 22919941, 22919987) were found.",
 "Neemo's post-mortem (medium.com/@neemo_fi/...) returned HTTP 403 and was not read.",
]
row = {
 "slug": S, "name": inc["name"],
 "date_utc": blk["timestamp_utc"].replace("+00:00", "Z"),
 "chain": "ethereum",
 "orig_verdict": inc["verdict"],
 "race_type_proposed": "deploy-window-copy",
 "race_type_reason": "The key thief's proxy upgrade (block 22855568) installed an implementation with an unprotected drain function; the bot called it in the next block at position 0, before the thief ever did (the thief never called it). Confirmed by identical victim-side calls in a local-fork replay of the thief's own call (only the recipient differs). Strength medium: no thief drain tx, pending or reverted, exists to prove a race.",
 "one_liner": "A bot called the open drain function (0x03b79c24) that a key thief's proxy upgrade had added, one block (12 s) later, before the thief ever used it: 114.53 ETH of weETH for 0.02 ETH in fees. It returned 91.634 ETH (80%) to Neemo nine days later.",
 "attacker": {
  "eoa": KEY, "eoas": [KEY],
  "contracts": ["0xbc4b1d58b28c497b7afda6fb90fe1471fa0672cc"],
  "funding": "non-tornado (0x067cbde2, the address that created and upgraded the same proxy in Feb 2025)",
  "funding_tx": inc["attacker"]["funding_tx"]["hash"],
  "deploy_tx": IMPLTX, "deploy_block": hx(impltx["blockNumber"]),
  "attack_txs": [
   {"hash": IMPLTX, "block": 22855567, "index": 107, "status": "success", "role": "CREATE malicious implementation 0xbc4b1d58 (old implementation + 3 new selectors incl. 0x03b79c24)"},
   {"hash": UPG, "block": 22855568, "index": 130, "status": "success", "role": "proxy 0x54cd2346 upgradeToAndCall(0xbc4b1d58, 0x) with the compromised admin key"},
   {"hash": A53, "block": 22855612, "index": 158, "status": "success", "role": "calls new selector 0x53474b2c() (writes one constant); after the bot drain"},
   {"hash": A97, "block": 22855836, "index": 123, "status": "success", "role": "calls new selector 0x97e44edc(attacker) (CCIP send from the proxy's WETH dust); after the bot drain"},
  ],
  "none_reason": None,
 },
 "bot": {"label": "anon bot 0xb750 (executor 0x1a61249f)", "eoa": BOT, "contract": ROUTER, "tx": BOTTX, "block": blk["number"], "position": bt["index"],
         "status": "success" if bt["status"] == 1 else "reverted", "priority_fee_gwei": bt["priority_fee_gwei"]},
 "bots_other": [],
 "evidence_level_mempool": "absent-from-archive",
 "mempool_note": "mempool-dumpster and its sourcelog cover 2025-07-05, and see 52-58% of the txs in blocks 22855567-22855569, but neither the upgrade tx, the bot tx, nor any of the thief's or the bot's other queried txs (9 txs) appear: private order flow or missed. Unknown != none. The bot's reaction time to the upgrade cannot be measured; only that its tx is in the next block (12 s later, same slot cadence).",
 "trigger": {"kind": None, "tx": None, "first_seen_utc_ms": None, "first_seen_utc": None, "sources": None,
             "note": "The trigger was the thief's upgrade tx 0xcd4a637d (block 22855568 idx 130, 21:03:23Z), which is not in mempool-dumpster, so there is no first-seen timestamp; the bot's tx is in the next block (21:03:35Z). Block timestamps are 12-s resolution."},
 "attacker_block": None,
 "attacker_block_note": "The thief never called the drain function 0x03b79c24 (no successful, reverted or other call to it in trace_filter of blocks 22855560-22862000 or the Etherscan tx list), so there is no attacker drain block. The reference is the upgrade.",
 "attacker_reference": {"kind": "upgrade", "block": 22855568, "tx": UPG},
 "auction": auc,
 "loot": {
  "scope": "bot-tx",
  "gross_loot_eth": round(gross, 9),
  "gross_loot_method": "sum of WETH.withdraw(uint256) amounts in the bot tx call trace (data/raw/rpc/trace_<tx>.json): %s wei; equals the 114.534059890882 ETH the executor paid to the bot EOA in the same tx" % wd,
  "captured_native": {"amount": round(gross, 6), "unit": "WETH->ETH", "desc": "106.929468097270451433 weETH taken from the proxy and swapped to WETH on a Uniswap V3 weETH/WETH pool inside the tx, then unwrapped"},
  "captured_usd": None, "captured_usd_source": None,
  "coinbase_paid_eth": round(coinbase, 9),
  "priority_fee_paid_eth": prio,
  "builder_refund_to_bot_eth": round(refund_wei / 1e18, 9),
  "builder_payout_to_victim_eth": None,
  "bot_net_eth": round(net, 9),
  "loot_note": "Figures cover the bot tx only. Cost = priority fee %.7f ETH (150 gwei x 137,752 gas) plus base fee, total gas %.9f ETH; no direct coinbase transfer. bot_net = gross - coinbase - total gas (before the later return). builder_refund_to_bot = 0: no tx from the block fee recipient 0xdadb0d80 (BuilderNet) to the bot or its executor in the block. The priority fee is %.0f%% of the %.4f ETH winning bid paid to the proposer." % (prio, gas_total, 100 * prio / prop_paid, prop_paid),
 },
 "fate": {
  "return_status": "returned",
  "returned_by_bot_eth": returned,
  "returned_by_builder_eth": None,
  "returned_total_eth": returned,
  "returned_to": "Neemo address 0x1671e4e1e610d4c5e693fc83f567a9f802287212 (named in Neemo's on-chain message tx 0xcd07f576, block 22915421)",
  "returned_desc": "On 2025-07-13 and 07-14 Neemo (0xdf902f5c) sent on-chain messages offering a 20%% bounty for the return of 80%%, then named 0x1671e4e1 as the destination for '91.634 ETH'. On 2025-07-14 the bot EOA sent 1.0 ETH (test, block %d) and 90.634 ETH (block %d) there = %.3f ETH = %.1f%% of the %.4f ETH it received; Neemo confirmed receipt in a message at block 22917927. The bot kept %.4f ETH (the 20%% bounty)." % (b_test, b_main, returned, pct_ret, gross, bounty),
  "bounty_kept_eth": bounty,
  "bounty_desc": "20%% white-hat bounty offered by Neemo in its on-chain messages (txs 0x1d75316b, 0x5d2b0846): 114.534060 - 91.634 = %.6f ETH" % bounty,
  "kept_by_bot_eth": kept_net,
  "returned_txs": [
   {"tx": RET_TEST, "eth": round(r_test, 6), "note": "bot EOA -> Neemo 0x1671e4e1, test transfer", "block": b_test, "time_utc": iso(t_test)},
   {"tx": RET_MAIN, "eth": round(r_main, 6), "note": "bot EOA -> Neemo 0x1671e4e1, main transfer", "block": b_main, "time_utc": iso(t_main)},
  ],
  "public_statement": "Defimon post 1476 (citing Neemo's post-mortem): 'the new implementation introduced a function to drain funds (0x03b79c24) which didn't have any access controls. The exploiter is actually a bot who instantly discovered this function and called it before the original attacker in the next block after the upgrade.' [contact redacted]; the bot's own on-chain message (tx 0xc2511fb4, block 22919941) says the same.",
 },
 "raw_refs": {
  "bot.block": race["raw_refs"]["block"], "bot.position": race["raw_refs"]["block"],
  "loot.gross_loot_eth": tracep,
  "loot.coinbase_paid_eth": race["raw_refs"]["traces"],
  "loot.priority_fee_paid_eth": [race["raw_refs"]["receipts"], race["raw_refs"]["block"]],
  "loot.builder_refund_to_bot_eth": [race["raw_refs"]["block"], race["raw_refs"]["traces"]],
  "loot.bot_net_eth": [tracep, rcp_p],
  "fate.returned_by_bot_eth": [rt_p, rm_p], "fate.returned_total_eth": [rt_p, rm_p],
  "fate.bounty_kept_eth": [tracep, rt_p, rm_p], "fate.kept_by_bot_eth": [tracep, rcp_p, rt_p, rm_p],
  "deploy_tx": impl_p, "upgrade_tx": upg_p, "bot_tx": tx_p, "bot_tx_trace": tracep,
  "return_receipts": [rtr_p, rmr_p],
  "attacker_proxy_calls_tracefilter": "data/raw/rpc/tracefilter_to_0x54cd23460df45559fd5feeaada7ba25f89c13525_22855560_22856500.json",
  "attacker_txlist": "data/raw/etherscan/txlist_0x7e9b11d0aa215e0f1a7f62534c7c93fc340d493d.json",
  "proxy_txlist_after": "data/raw/etherscan/txlist_0x54cd23460df45559fd5feeaada7ba25f89c13525_22855570_latest.json",
  "mempool_csv": "data/raw/mempool-dumpster/2025-07-05.csv.zip", "mempool_sourcelog": "data/raw/mempool-dumpster/2025-07-05_sourcelog.csv.zip",
  "implementation_code": "data/raw/rpc/code_0xbc4b1d58_22855568.json", "previous_implementation_code": "data/raw/rpc/code_0x9b1f0379_22855567.json",
  "defimon_1475": "data/raw/web-neemo/defimon_1475.html", "defimon_1476": "data/raw/web-neemo/defimon_1476.html",
  "postmortem_403": "data/raw/web-neemo/neemo_postmortem_medium.html",
 },
 "rawref_gaps": [{"field": "trigger.first_seen_utc_ms", "why": "the upgrade tx and the bot tx are not in mempool-dumpster 2025-07-05 (day covered, sourcelog present); no archive first-seen exists"},
                 {"field": "attacker_block", "why": "the thief never called the drain function; no attacker drain tx exists"},
                 {"field": "loot.captured_usd", "why": "no USD price source saved for 2025-07-05; amounts given in ETH"}],
 "discrepancies": disc,
 "evidence_notes": [
  "Implementation diff (incidents/neemo-2025/impl_diff.json): new implementation 0xbc4b1d58 = previous implementation 0x9b1f0379 (verified StakingManagerL1) + exactly 3 selectors: 0x03b79c24(address) [no msg.sender check; transfers the proxy's whole weETH balance to the argument], 0x53474b2c() [writes one constant], 0x97e44edc(address) [Chainlink CCIP send from the proxy's WETH dust].",
  "Call diff (incidents/neemo-2025/call_diff.json): bot's victim-side subtree (6 calls: proxy -> delegatecall impl -> weETH.balanceOf -> weETH.transfer, plus delegatecalls into weETH's implementation) vs. the key-holder EOA calling 03b79c24(itself) on a local anvil fork at block 22855568: identical call sequence, 2 of 6 calls byte-identical, 4 differ only in the 20-byte recipient argument; both move 106.929468097270451433 weETH.",
  "Local-fork replay (attacker_replay_local_fork.json, nothing broadcast): the bot's exact calldata reproduces the mainnet gas (137,752) and empties the proxy; a fresh unrelated address can do the same (no access control); the thief's real follow-up selectors 0x53474b2c / 0x97e44edc do not move weETH; a thief call to 0x03b79c24 after the bot moves 0 weETH.",
  "Ordering: thief CREATE block 22855567 idx 107 (21:03:11Z); upgrade block 22855568 idx 130 (21:03:23Z, Titan block); bot tx block 22855569 idx 0 (21:03:35Z, BuilderNet block delivered by Ultra Sound, winning bid 0.0342 ETH, bot priority fee 150 gwei vs. next highest 20 gwei).",
  "Calls to the proxy in blocks 22855560-22862000 (trace_filter incl. reverted): upgrade, bot drain, 0x53474b2c (22855612), 0x97e44edc (22855836) - nothing else. Later: 0x67a28887 calls 0x97e44edc (2026-07-17), 0x8c8aaebd calls 0x03b79c24 (2026-09-28, moved 0).",
  "Thief-side proceeds are separate: 176.57 ETH = 12.27 (key-holder EOA) + 160.9 + 3.4 (0x198b2c4e) to collection address 0x4ec65e4d, then 176.4 ETH into Tornado Router; the ETH arrived via contracts such as 0x5c7bcd6e (implementation named Ethereum_SpokePool). Not part of the bot's take.",
  "Not c0ffeebabe and not Yoink. Bot EOA 0xb750 has sent ~700 routine txs to the same executor since 2024-06-30 (e.g. at block 22855567 idx 63 and four txs before); the Neemo tx differs in priority fee (150 gwei vs. ~0.34 gwei gas price) and calldata size (566 B vs 1,342 B). No on-chain link to the key holder or the collection address was found.",
 ],
 "incident_dir": f"incidents/{S}",
}
finish(S, [row])
