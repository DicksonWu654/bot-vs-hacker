"""Extract incident dataset row for makina-2026. Run from project root: .venv/bin/python scripts/dataset/extract_makina-2026.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _x5_common import *

S = "makina-2026"
inc = jl(f"incidents/{S}/incident.json")
BOT = "0x935bfb495e33f74d2e9735df1da66ace442ede48"
BOTTX = "0x569733b8016ef9418f0b6bde8c14224d9e759e79301499908ecbcd956a0651f5"
DEPLOY = "0xad945d38ec5dc00f0310b6f22d19da3b8b5063b9f3e7efb38ca6a5cbc6385a39"
HELPER_TX = "0x5ed8d56804e39181fe30b217ca23e740f9bb40185fde6aed6f375e81068f38a9"
FWD = "0x14d2725f4cac331740b053ae49176cec780b556e4aacc3a9f70d77644e97a2a7"
RET = "0x0d23fea549bf8330cf47fabec75ad12b75cf0ade45cce68785067f2bda326a44"
RACE = f"incidents/{S}/race_24273362.json"
race = jl(RACE)
bt = race_tx(race, BOTTX)
blk = race["block"]
tracep = f"data/raw/rpc/trace_{BOTTX}.json"
trace = res(jl(tracep))
rcp_p, rcp = rpc_rcpt(BOTTX)
tx_p, txo = rpc_tx(BOTTX)
dtx_p, dtx = rpc_tx(DEPLOY)

coinbase = eth(bt["coinbase_transfer_wei"])
prio = eth(bt["priority_fee_total_wei"])
gas_total = eth(hx(rcp["gasUsed"]) * hx(rcp["effectiveGasPrice"]))
wd = weth_withdraws(trace)
gross = sum(wd) / 1e18
net = gross - coinbase - gas_total

auc = bvh.auction_summary(RACE, BOTTX)
assert auc["proposer_payment_tx"]
prop_paid = auc["proposer_paid_eth"]

fwd_p, fwd = rpc_tx(FWD)
ret_p, ret = rpc_tx(RET)
ret_r_p, ret_r = rpc_rcpt(RET)
fwd_eth = eth(hx(fwd["value"]))
ret_eth = eth(hx(ret["value"]))
bounty = round(fwd_eth - ret_eth, 6)
assert fwd["to"].lower() == "0xbed26250db2097318386f540fd546acedf7bde25"
assert ret["to"].lower() == "0x62244c74e1d09b3d86ef7342d354b5d7770bde10"
ret_block = hx(ret_r["blockNumber"])
# timestamp of return block from the 0xbed etherscan txlist
tl_p = "data/raw/etherscan/txlist_0xbed26250db2097318386f540fd546acedf7bde25_24000000_25000000.json"
ret_ts = next(int(t["timeStamp"]) for t in jl(tl_p)["result"] if t["hash"].lower() == RET)

disc = []
if abs(coinbase - inc["bots"][0]["coinbase_paid_eth"]) > 1e-6:
    disc.append("coinbase differs from incident.json")
disc.append(f"incident.json says builder->proposer 276.3227 ETH, relay bid 276.32 ETH; consistent (proposer payment tx idx 104 = {prop_paid:.4f} ETH).")
disc.append("incident.json bid_summary.n_builders: race file reports %s distinct builder pubkeys on Flashbots bids vs 10 named in incident.json auction.per_builder (name-grouping)." % auc["n_builders"])

row = {
 "slug": S, "name": inc["name"],
 "date_utc": blk["timestamp_utc"].replace("+00:00", "Z"),
 "chain": "ethereum",
 "orig_verdict": inc["verdict"],
 "race_type_proposed": "deploy-window-copy",
 "race_type_reason": "The attacker deployed its tx.origin-gated attack contract in block 24273361; the EIP-7702 searcher re-implemented the same plan in the next block at position 0, and the attacker's own call was never mined. Confirmed by 77% calldata-byte overlap with the attacker runtime and a 98.6% call-sequence match in a local-fork replay.",
 "one_liner": "Searcher 0x935b ran the attacker's Makina/Curve plan one block after the attacker deployed its contract, before the attacker ever called it, paid 1,299.05 ETH to the builder, and 920.7 ETH was later returned to Makina's Safe.",
 "attacker": {
  "eoa": inc["attacker"]["eoas"][0], "eoas": inc["attacker"]["eoas"],
  "contracts": ["0x2c19b916b29e5170f75628d690623dedcafeca4c", "0xd5e8ac959dca7448c5841d6529582e7d347904b0"],
  "funding": "tornado", "funding_tx": inc["attacker"]["funding_tx"]["hash"],
  "deploy_tx": DEPLOY, "deploy_block": hx(dtx["blockNumber"]),
  "attack_txs": [
   {"hash": HELPER_TX, "block": 24273273, "index": 74, "status": "success", "role": "CREATE helper 0xd5e8ac95 (tx.origin == attacker EOA check)"},
   {"hash": DEPLOY, "block": hx(dtx["blockNumber"]), "index": hx(dtx["transactionIndex"]), "status": "success", "role": "CREATE attack contract 0x2c19b916 (entry F1()); the F1() call itself never landed"},
  ],
  "none_reason": None,
 },
 "bot": {"label": "anon searcher (EIP-7702 account 0x935b)", "eoa": BOT, "contract": "EIP-7702 delegated account (self-call)",
         "tx": BOTTX, "block": blk["number"], "position": bt["index"], "status": "success" if bt["status"] == 1 else "reverted",
         "priority_fee_gwei": bt["priority_fee_gwei"]},
 "bots_other": [],
 "evidence_level_mempool": "absent-from-archive",
 "mempool_note": "mempool-dumpster covers 2026-01-20 (csv.zip) but neither the attacker deploy tx nor the bot tx appears in it (race file mempool.txs[bot].seen=false); 99/105 txs of the bot block were seen. Private flow or missed by sources; unknown != none. Sourcelogs end 2025-07-14, so no source attribution.",
 "trigger": {"kind": None, "tx": None, "first_seen_utc_ms": None, "first_seen_utc": None, "sources": None,
             "note": "No first-seen timestamp for the attacker deploy tx (block 24273361 idx 86) or any attacker call: neither is in mempool-dumpster. The deploy block time (03:40:23Z) and bot block time (03:40:35Z) are 12-s block timestamps only; how/when the bot learned the plan is not shown on-chain."},
 "attacker_block": None,
 "attacker_block_note": "The attacker's F1() call was never mined (EOA nonce stays 2; contract txlist = creation only). No attacker attack tx exists to compare; the reference is the deploy block.",
 "attacker_reference": {"kind": "deploy", "block": hx(dtx["blockNumber"]), "tx": DEPLOY},
 "auction": auc,
 "loot": {
  "scope": "bot-tx",
  "gross_loot_eth": round(gross, 9),
  "gross_loot_method": "sum of WETH.withdraw(uint256) amounts called inside the bot tx call trace (data/raw/rpc/trace_<tx>.json): %s wei" % wd,
  "captured_native": {"amount": round(gross, 6), "unit": "WETH->ETH", "desc": "WETH unwrapped by the bot tx after the pool/Makina manipulation (flash loans of 280,000,000 USDC repaid inside the tx)"},
  "captured_usd": None, "captured_usd_source": None,
  "coinbase_paid_eth": round(coinbase, 9),
  "priority_fee_paid_eth": prio,
  "builder_refund_to_bot_eth": 0.0,
  "builder_payout_to_victim_eth": round(ret_eth, 6),
  "bot_net_eth": round(net, 9),
  "loot_note": "Figures cover the bot tx only. coinbase_paid = direct transfer to block.coinbase (builder fee recipient 0xa6c2) from the trace; bot_net = gross - coinbase - total gas cost (%.9f ETH). builder_refund_to_bot = 0: the bot received no builder refund tx in the block (incident.json; bot balance delta +0.1299 ETH). builder_payout_to_victim = the 920.7 ETH that 0xbed (receiver of the builder's 1,023 ETH forward) sent to Makina's Safe; builder-> proposer was %.4f ETH (the winning bid)." % (gas_total, prop_paid),
 },
 "fate": {
  "return_status": "partial",
  "returned_by_bot_eth": None,
  "returned_by_builder_eth": round(ret_eth, 6),
  "returned_total_eth": round(ret_eth, 6),
  "returned_to": "Makina Safe 0x62244c74e1d09b3d86ef7342d354b5d7770bde10",
  "returned_desc": "Builder fee recipient 0xa6c2 received the %.4f ETH coinbase payment, paid %.4f ETH to the proposer (winning bid) and forwarded %.1f ETH to 0xbed2 (block 24273418, 2026-01-20T03:51:47Z). Makina sent on-chain messages offering a 10%% Safe Harbor bounty to 0xa6c2 and 0xbed2 on 2026-01-20; on 2026-01-22T13:15:11Z (block %d) 0xbed2 sent %.1f ETH to the Makina Safe and kept %.1f ETH. The searcher kept about 0.13 ETH; no return by the searcher found." % (coinbase, prop_paid, fwd_eth, ret_block, ret_eth, bounty),
  "bounty_kept_eth": bounty,
  "bounty_desc": "10%% Safe Harbor bounty retained by 0xbed2 (%.1f x 10%% = %.1f ETH)" % (fwd_eth, bounty),
  "kept_by_bot_eth": round(net, 9),
  "returned_txs": [{"tx": RET, "eth": round(ret_eth, 6), "note": "0xbed2 -> Makina Safe, net of 10% bounty", "block": ret_block, "time_utc": iso(ret_ts)}],
  "public_statement": "Makina post-mortem (2026-02-04): original attacker frontrun by MEV searcher 0x935b at block 24273362; searcher keeps 0.13 ETH, 1299.04 ETH to builder 0xa6c2; 276.32 ETH to proposer, 1023 ETH to 0xbed. https://makinafi.substack.com/p/post-mortem-january-20th-2026-incident",
 },
 "raw_refs": {
  "bot.block": race["raw_refs"]["block"], "bot.position": race["raw_refs"]["block"],
  "loot.gross_loot_eth": tracep,
  "loot.coinbase_paid_eth": race["raw_refs"]["traces"],
  "loot.priority_fee_paid_eth": [race["raw_refs"]["receipts"], race["raw_refs"]["block"]],
  "loot.builder_refund_to_bot_eth": [race["raw_refs"]["block"], race["raw_refs"]["traces"]],
  "loot.builder_payout_to_victim_eth": [ret_p, ret_r_p],
  "loot.bot_net_eth": [tracep, rcp_p],
  "fate.returned_by_builder_eth": ret_p, "fate.returned_total_eth": ret_p, "fate.bounty_kept_eth": [fwd_p, ret_p],
  "fate.kept_by_bot_eth": [tracep, rcp_p],
  "fate.forward_tx_builder_to_0xbed": fwd_p, "fate.return_tx_timestamp": tl_p,
  "deploy_tx": dtx_p, "bot_tx": tx_p, "bot_tx_trace": tracep,
  "postmortem": "data/raw/web-makina/makina_postmortem.html",
 },
 "rawref_gaps": [{"field": "trigger.first_seen_utc_ms", "why": "attacker deploy/call and bot tx are not in mempool-dumpster 2026-01-20; no archive first-seen exists"},
                 {"field": "attacker_block", "why": "attacker call never mined"}],
 "discrepancies": disc,
 "evidence_notes": [
  "Bot calldata (16,835 B) shares 4,992 of 6,470 non-zero bytes (77.2%) in >=16-byte windows verbatim with the attacker's deployed runtime 0x2c19b916 (incident.json bots[0].replay_evidence).",
  "Local-fork replay of the attacker's F1() at block 24273361 (nothing broadcast): non-view protocol call sequence matches the bot tx at ratio 0.9864 (146 vs 148 calls); both take the same 160,590,920.349812 USDC Morpho + 119,409,079.650188 USDC Aave flash loans. Only difference: final USDC->WETH route. Files: incidents/makina-2026/calldiff_attacker_vs_copy.json, incidents/makina-2026/attacker_F1_local_fork_calltrace.json.",
  "Ordering: attacker contract CREATE in block 24273361 idx 86 (03:40:23Z); bot tx block 24273362 position 0 (03:40:35Z); attacker EOA nonce stays 2 so its call never landed. The contract is tx.origin-gated, so the bot re-implemented the plan rather than calling it.",
  "Makina post-mortem and PeckShield agree that searcher 0x935b frontran the attacker; the 920.7 ETH return tx is on-chain (data/raw/rpc/tx_%s.json)." % RET,
  "Not c0ffeebabe; the bot is 0x935bfb49 (EIP-7702 account). No mainnet attacker-call comparison exists; evidence is deployed-code match plus simulation.",
 ],
 "incident_dir": f"incidents/{S}",
}
finish(S, [row])
