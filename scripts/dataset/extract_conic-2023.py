"""Extract rows for conic-2023 -> data/extract/conic-2023.json (TWO rows: sub 'crvusd-pool' = Yoink's ten-block replay, sub 'eth-pool' = clone after a failed first attempt).
Run from project root (after incidents/conic-2023/scripts/analyze.py and write_incident.py):  .venv/bin/python scripts/dataset/extract_conic-2023.py
Everything is recomputed from saved raw RPC/Etherscan files (data/raw/rpc-conic, data/raw/etherscan/conic_*) and the race files; asserts cross-check the analysis JSONs.
Pre-Aug-2023: in-block evidence only. Yoink = EOA 0xfde0d157 (gen1 bot 0xd050e0a4; decoding in research/bot-re/analysis.md). No c0ffeebabe content."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _x6 import *

S = "conic-2023"
inc = load(f"incidents/{S}/incident.json")
y10 = load(f"incidents/{S}/yoink_10txs.json")
crv = load(f"incidents/{S}/victim_call_diff_crvusd.json")
ed = load(f"incidents/{S}/victim_call_diff_eth.json")
R = lambda k: f"data/raw/rpc-conic/{k}.json"  # noqa: E731
rows_y = y10["rows"]
BOTC = "0xd050e0a4838d74769228b49dff97241b4ef3805d"
YEOA = "0xfde0d1575ed8e06fbf36256bcdfa1f359281455a"
A1 = "0x37acd17a80a5f95728459bfea85cb2e1f64b4c75cf4a4c8dcb61964e26860882"
Y1 = rows_y[0]["tx"]
RET = y10["returned_tx"]
cva = inc["attacker"]["crvusd_pool_attacker"]
ea = inc["attacker"]["eth_pool_first_attacker"]
ec = inc["attacker"]["eth_pool_clone_exploiter"]

# ---- sanity asserts against the saved data
assert len(rows_y) == 10 and [r["block"] for r in rows_y] == list(range(17743471, 17743481))
assert abs(y10["sum_eth"]["gross"] - 125.82415) < 1e-4 and abs(y10["sum_gas_plus_coinbase_eth"] - 35.48275) < 1e-4 and abs(y10["sum_eth"]["net"] - 90.34139) < 1e-4
assert abs(y10["returned_to_conicfinance_eth"] - 81.307251) < 1e-9
# builder refund to the bot in the four blocks with race files
refund_blocks = {}
for b in (17743471, 17743472, 17743476, 17743480):
    rr = load(f"incidents/{S}/race_{b}.json")
    fr = rr["block"]["fee_recipient"].lower()
    refund_blocks[b] = sum(int(t["value_wei"]) for t in rr["txs"] if t["from"].lower() == fr and (t["to"] or "").lower() in (BOTC, YEOA)) / 1e18
assert all(v == 0 for v in refund_blocks.values()), refund_blocks
prio = [r["priority_fee_gwei"] for r in rows_y]
assert all(abs(p) < 1e-9 for p in prio)

# ---------------------------------------------------------------------------------------------- row 1: crvUSD pool / Yoink
a_sum1 = bvh.auction_summary(f"incidents/{S}/race_17743471.json", Y1)
a_sum1["auction_note"] = ("Block 17743471 (first Yoink copy, rsync-builder.xyz) is not recorded by any relay that answered (Flashbots bid history: 0 bids; delivered-payload lists empty), "
                          "so the bid curve is empty. Block 17743472 (second copy, 'I can haz block?') has 57 Flashbots-relay bids, winning bid 2.43348 ETH at -1,180 ms; "
                          "17743476 (rsync, 272 bids, 1.93396 ETH) and 17743480 ('I can haz block?', 19 bids, 2.29313 ETH) are in incident.json auction_summary.yoink_blocks.")
net1 = y10["sum_eth"]["net"]
kept1 = y10["kept_by_yoink_eth"]
refs1 = {
 "bot.block": R(f"conic_tx_{Y1}"), "bot.position": R(f"conic_tx_{Y1}"), "attacker_block": R(f"conic_tx_{A1}"),
 "loot.gross_loot_eth": [R(f"trace_{r['tx']}") for r in rows_y],
 "loot.coinbase_paid_eth": [R(f"trace_{r['tx']}") for r in rows_y],
 "loot.priority_fee_paid_eth": [R(f"conic_rcpt_{r['tx']}") for r in rows_y] + [R(f"conic_blockhdr_{r['block']}") for r in rows_y],
 "loot.builder_refund_to_bot_eth": [f"data/raw/rpc/block_{b}.json" for b in (17743471, 17743472, 17743476, 17743480)] + [f"incidents/{S}/race_{b}.json" for b in (17743471, 17743472, 17743476, 17743480)],
 "loot.bot_net_eth": [R(f"trace_{r['tx']}") for r in rows_y] + [R(f"conic_rcpt_{r['tx']}") for r in rows_y],
 "fate.returned_by_bot_eth": R(f"trace_{RET}"), "fate.returned_total_eth": R(f"trace_{RET}"),
 "fate.bounty_kept_eth": [R(f"trace_{RET}")] + [R(f"trace_{r['tx']}") for r in rows_y],
 "fate.kept_by_bot_eth": [R(f"trace_{RET}")] + [R(f"trace_{r['tx']}") for r in rows_y],
 "attacker_call_diff": f"incidents/{S}/victim_call_diff_crvusd.json", "yoink_ten_txs": f"incidents/{S}/yoink_10txs.json",
 "yoink_message_tx": R("conic_tx_0xaf1535ea5bee7ccbc048eafd1fe0771c31cde51d065e6abc2c4aa2c1f9d264ff"),
 "conic_messages": [R(f"conic_tx_{h}") for h in ("0x6382dad8f1f08c90aa74a01bae2ec414161821b276f8955cb8dddc68856c03ce", "0x9074a68818751bcfe88c22f483784bf686481ee8b7b3f81e00b03d36628a4b47",
                                                "0xd9f718386aa359cd5f2d15619a3a536eb3d17eb10c0cac78106440b3d4c92ce5")],
 "other_copiers_scan": "data/raw/etherscan/conic_logs_omnipool_17743300_17743700.json",
 "attacker_funding_and_internal": "data/raw/etherscan/conic_conic02_attacker_txlistinternal.json", "attacker_txlist": "data/raw/etherscan/conic_conic02_attacker_txlist.json",
 "dhl_poc": "data/raw/web-conic/dhl_conic02.txt", "press": ["data/raw/web-conic/rekt.html", "data/raw/web-conic/dlnews.html", "data/raw/web-conic/certik.html"],
}
row1 = {
 "slug": S, "sub": "crvusd-pool",
 "name": "Conic Finance crvUSD omnipool sandwich - Yoink replays the attacker's exploit ten times, starting one block after the attacker's own successful tx",
 "date_utc": iso(rows_y[0]["timestamp_utc"]), "chain": "ethereum",
 "orig_verdict": "related-not-frontrun", "race_type_proposed": "late-copy",
 "race_type_reason": ("Yoink gen1's victim-call sequence and round-number parameters equal the attacker's (flash loan, crvUSD create_loan, Curve swaps, Conic deposit/withdraw, tricrypto exit), "
                      "but its first copy is at block 17743471 idx 0, one block after the attacker's tx succeeded at 17743470 idx 4. Nothing of the attacker's was pending: his next tx came 22 blocks later. Late copy."),
 "one_liner": (f"Yoink gen1 replayed the Conic crvUSD sandwich in 10 consecutive blocks (17743471-80; idx 0, once idx 4) starting one block AFTER the attacker's tx landed; gross {y10['sum_eth']['gross']:.2f} ETH, "
               f"net {net1:.2f}, returned 81.307 (90%) to Conic. Attacker's own take: 13.58 ETH."),
 "attacker": {"eoa": cva["eoa"], "eoas": [cva["eoa"]], "contracts": cva["contracts"], "funding": "Tornado Cash 1 ETH pool", "funding_tx": cva["funding_txs"][0],
              "deploy_tx": cva["deploy_txs"][0]["tx"], "deploy_block": 17743464,
              "attack_txs": [{"hash": t["hash"], "block": t["block"], "index": t["index"], "status": t["status"],
                              "role": t.get("note") or ("profit %.4f ETH" % t["profit_eth"] if t.get("profit_eth") else "")} for t in cva["txs"]],
              "none_reason": None},
 "bot": {"label": "Yoink", "eoa": YEOA, "contract": BOTC, "tx": Y1, "block": 17743471, "position": 0, "status": "success", "priority_fee_gwei": 0.0,
         "n_txs": 10, "tx_list": [r["tx"] for r in rows_y]},
 "bots_other": [],
 "evidence_level_mempool": "in-block-only",
 "mempool_note": ("In-block evidence only: 2023-07-21 is before the mempool-dumpster archive (starts 2023-08-07). The attacker's tx (idx 4, 1 gwei tip, in a full block) looks like public-mempool flow "
                  "but that is not shown. Yoink's first inclusion is the next block either way, so no front-run is possible to establish."),
 "trigger": {"kind": None, "tx": None, "first_seen_utc_ms": None, "first_seen_utc": None, "sources": None,
             "note": "No mempool first-seen exists. The attacker's tx 0x37acd17a landed at 2023-07-21T19:01:35Z (block 17743470); Yoink's first copy is in the next block (19:01:47Z)."},
 "attacker_block": 17743470,
 "attacker_block_note": "Attacker tx 0x37acd17a at block 17743470 idx 4 (success, +11.5626 ETH); Yoink first copy at 17743471 idx 0.",
 "attacker_reference": {"kind": "attack-tx", "block": 17743470, "tx": A1},
 "auction": a_sum1,
 "loot": {"scope": "bot-10-txs", "gross_loot_eth": y10["sum_eth"]["gross"],
          "gross_loot_method": "sum over the ten Yoink txs of the ETH value received by the bot contract from the Curve tricrypto exit (successful CALL frames in callTracer traces)",
          "captured_native": {"amount": y10["sum_eth"]["gross"], "unit": "ETH", "desc": "ETH out of the tricrypto exit after replaying the sandwich; value comes from Conic crvUSD pool LPs"},
          "captured_usd": None, "captured_usd_source": None,
          "coinbase_paid_eth": y10["sum_eth"]["coinbase"], "priority_fee_paid_eth": 0.0, "builder_refund_to_bot_eth": 0.0, "builder_payout_to_victim_eth": None,
          "bot_net_eth": net1,
          "loot_note": (f"bot_net = gross {y10['sum_eth']['gross']:.5f} - coinbase {y10['sum_eth']['coinbase']:.5f} - gas {y10['sum_eth']['gas']:.5f} (all base fee: every tx had a 0 gwei tip) = {net1:.5f} ETH; "
                        "matches Yoink's on-chain message (125.82415 / 35.48275 / 90.34139) to <1e-5 ETH. Coinbase per tx = msg.value per mille of gross (109-215 per mille). "
                        "Builder refund checked only in the four blocks with race files (none); six blocks unchecked. The attacker's own take over two successful txs was 13.581 ETH.")},
 "fate": {"return_status": "returned", "returned_by_bot_eth": y10["returned_to_conicfinance_eth"], "returned_by_builder_eth": None, "returned_total_eth": y10["returned_to_conicfinance_eth"],
          "returned_to": "conicfinance.eth 0xedaeb101f34d767f263c0fe6b8d494e3d071f0ba (deployer of the crvUSD pool)",
          "returned_desc": (f"Conic messaged Yoink on-chain (2023-07-22T16:43:59Z), Yoink replied with its accounting (23:34:47Z), Conic offered a 10% bounty (07-23 14:05:35Z); the bot contract's withdrawTo paid 81.307251 ETH "
                            f"to conicfinance.eth at 2023-07-23T15:42:59Z (block 17756778). That is {y10['returned_pct_of_net']:.2f}% of the {net1:.3f} ETH net, {y10['returned_to_conicfinance_eth']/y10['sum_eth']['gross']*100:.1f}% of gross."),
          "bounty_kept_eth": kept1, "bounty_desc": "10% of Yoink's net by agreement (Conic's message: 'a bounty of 10% of your profits')", "kept_by_bot_eth": kept1,
          "returned_txs": [{"tx": RET, "eth": y10["returned_to_conicfinance_eth"], "block": 17756778, "time_utc": "2023-07-23T15:42:59Z", "note": "bot contract withdrawTo(conicfinance.eth, 81.307251 ETH)"}],
          "public_statement": "on-chain messages (4 txs) between conicfinance.eth and the Yoink EOA, saved under data/raw/rpc-conic/"},
 "raw_refs": refs1,
 "rawref_gaps": [{"field": "loot.captured_usd", "why": "no saved ETH price for 2023-07-21; not converted"},
                 {"field": "loot.builder_refund_to_bot_eth", "why": "checked in 4 of the 10 blocks (race files); 17743473-75, -77-79 not scanned for builder->bot transfers"}],
 "discrepancies": [
   "w1 candidates.json called this 'captured value from the attacker's imbalance (not a copy)': the call-by-call diff (victim_call_diff_crvusd.json) shows a replay of the attacker's exploit, but after, not before, the attacker landed.",
   "DeFiHackLabs dates Conic02 2023-07-22; the tx is 2023-07-21T19:01:35Z.",
   "Loss figures conflict: DeFiHackLabs ~$934K, CertiK/Rekt ~$300K. On chain the profit-taking txs sum to 13.58 ETH (attacker) + 125.82 ETH (Yoink gross)."],
 "evidence_notes": [
   "Victim-call diff, attacker tx 0x37acd17a vs Yoink tx 0x64910b0a: 8/8 Conic pool calls, 2/2 crvUSD controller calls, 11/11 crvUSD-USDC swaps, 10/10 crvUSD-USDT swaps, 1/1 tricrypto exit have the same target+selector in order; identical calldata for 2/2 controller calls, 5/11 and 5/10 Curve swaps (the round-number ones), 1/8 Conic calls (first 47M crvUSD deposit); the rest are balance-derived and differ by ~0.1%.",
   "Balancer flash loan tokens/amounts identical (12,000,000 USDC, 80,000 WETH, 9,000,000 USDT); recipient and userData differ.",
   "Yoink's ten txs fill ~21.2M gas each (70% of the block) and push the base fee from 35.6 to 103.5 gwei; Yoink stops after 17743480 (reason unknown).",
   "The attacker's own retries: 17743492 (idx 2) reverted, redeployed at 17743514, 17743521 reverted, 17743531 succeeded for 2.018 ETH; we do not claim Yoink caused the reverts (they are nested out-of-gas).",
   "No other address replayed the pattern: Etherscan getLogs on the pool (17743300-17743700) shows 12 multi-event txs = attacker 2 + Yoink 10."],
 "incident_dir": f"incidents/{S}",
}

# ---------------------------------------------------------------------------------------------- row 2: ETH pool / clone
CL_ATK, OR_ATK = ed["clone"]["attack_tx"], ed["original"]["attack_tx"]
rc = load(rp := f"incidents/{S}/race_17740955.json")
cr = txrow(rc, CL_ATK)
a_sum2 = bvh.auction_summary(f"incidents/{S}/race_17740955.json", CL_ATK)
gas_c = ed["clone"]["gas_used"] * cr["gas_price_gwei"] * 1e9 / 1e18
gross2 = 1724.175115775667
refs2 = {
 "bot.block": R(f"conic_tx_{CL_ATK}"), "bot.position": R(f"conic_tx_{CL_ATK}"), "attacker_block": R(f"conic_tx_{OR_ATK}"),
 "loot.gross_loot_eth": ["data/raw/etherscan/conic_ethattacker_hist_txlistinternal.json", R(f"trace_{CL_ATK}")],
 "loot.coinbase_paid_eth": R(f"trace_{CL_ATK}"), "loot.priority_fee_paid_eth": R(f"conic_rcpt_{CL_ATK}"),
 "loot.builder_refund_to_bot_eth": ["data/raw/rpc/block_17740955.json", f"incidents/{S}/race_17740955.json"],
 "loot.bot_net_eth": ["data/raw/etherscan/conic_ethattacker_hist_txlistinternal.json", R(f"conic_rcpt_{CL_ATK}")],
 "fate.kept_by_bot_eth": ["data/raw/etherscan/conic_ethattacker_hist_txlistinternal.json", "data/raw/etherscan/conic_ethattacker_after_txlist.json"],
 "calldata_and_bytecode_diff": f"incidents/{S}/victim_call_diff_eth.json",
 "original_attack_trace": R(f"trace_{OR_ATK}"), "clone_attack_trace": R(f"trace_{CL_ATK}"),
 "creation_txs": [R(f"conic_tx_{ed['original']['deploy_tx']}"), R(f"conic_tx_{ed['clone']['deploy_tx']}")],
 "eth_pool_multi_event_scan": "data/raw/etherscan/conic_logs_ethpool_17740000_17743500_p1.json",
 "conic_messages_to_loot_address": ["data/raw/etherscan/conic_ethattacker_after_txlist.json", "data/raw/etherscan/conic_3d32_txlist.json"],
 "press": ["data/raw/web-conic/rekt.html", "data/raw/web-conic/certik.html", "data/raw/web-conic/dlnews.html"],
 "dhl_poc": "data/raw/web-conic/dhl_conic.txt",
}
row2 = {
 "slug": S, "sub": "eth-pool",
 "name": "Conic Finance ETH omnipool (read-only reentrancy) - an anonymous clone redeploys the first attacker's contract after its attempt reverted and takes 1,724 ETH",
 "date_utc": iso(rc["block"]["timestamp"]), "chain": "ethereum",
 "orig_verdict": "related-not-frontrun", "race_type_proposed": "post-failure-replay",
 "race_type_reason": ("The first attacker's attack tx (0x97a8315e, block 17740901 idx 4) reverted out of gas. 51 blocks later a different EOA deployed a clone of his contract (creation code identical except one 20-byte "
                      "beneficiary address) and sent identical calldata, succeeding at idx 0 of 17740955. The original had nothing pending (two txs ever); the clone came after the failure, not before the attack."),
 "one_liner": ("ETH omnipool: the first attacker's tx reverted (out of gas, block 17740901). 51 blocks later an unknown EOA redeployed a 1-address-diff clone of his contract, sent identical calldata and took 1,724 ETH at idx 0 of 17740955. Not returned."),
 "attacker": {"eoa": ea["eoa"], "eoas": [ea["eoa"]], "contracts": [ea["contract"]], "funding": "Tornado Cash 1 ETH pool", "funding_tx": ea["funding_tx"],
              "deploy_tx": ea["deploy_tx"], "deploy_block": 17740893,
              "attack_txs": [{"hash": OR_ATK, "block": 17740901, "index": 4, "status": "reverted", "role": "attack 0x52558bb0; out of gas inside a nested Curve call; 27.64M gas limit"}],
              "none_reason": None},
 "bot": {"label": "anon clone exploiter (not a known bot)", "eoa": ec["eoa"], "contract": ec["contract"], "tx": CL_ATK, "block": 17740955, "position": 0, "status": "success",
         "priority_fee_gwei": 3.0},
 "bots_other": [],
 "evidence_level_mempool": "in-block-only",
 "mempool_note": "In-block evidence only (2023-07-21, before the archive). Whether the clone's operator saw the failed tx pending, mined, or the deployed contract is unknown; the 51-block gap (~10 min) fits a human or slow pipeline, not a reflex bot.",
 "trigger": {"kind": None, "tx": None, "first_seen_utc_ms": None, "first_seen_utc": None, "sources": None,
             "note": "No mempool first-seen. The trigger is the first attacker's contract (deployed 2023-07-21T10:22:47Z, block 17740893) and its reverted attack tx (10:24:23Z, block 17740901)."},
 "attacker_block": 17740901,
 "attacker_block_note": "First attacker's attack tx 0x97a8315e at block 17740901 idx 4 (reverted); the clone's attack is 54 blocks later at 17740955 idx 0.",
 "attacker_reference": {"kind": "attack-tx", "block": 17740901, "tx": OR_ATK},
 "auction": a_sum2,
 "loot": {"scope": "bot-tx", "gross_loot_eth": gross2,
          "gross_loot_method": "ETH sent by the clone contract to its EOA in the attack tx (Etherscan internal list; the contract received 22,059.86 + 1,798.53 + 1,701.46 ETH of flash-loaned/withdrawn WETH and repaid the loans)",
          "captured_native": {"amount": gross2, "unit": "ETH", "desc": "net ETH extracted from the Conic ETH omnipool via read-only reentrancy"},
          "captured_usd": None, "captured_usd_source": None,
          "coinbase_paid_eth": 0.0, "priority_fee_paid_eth": round(cr["priority_fee_total_wei"] and int(cr["priority_fee_total_wei"]) / 1e18, 9), "builder_refund_to_bot_eth": 0.0,
          "builder_payout_to_victim_eth": None, "bot_net_eth": round(gross2 - gas_c, 9),
          "loot_note": f"bot_net = gross {gross2:.6f} - attack-tx gas {gas_c:.6f} ETH (20.14M gas x 22.27 gwei, of which 0.0604 ETH tip) = {gross2-gas_c:.6f} ETH; deployment gas (3.0 gwei tip, block 17740952) not subtracted. No coinbase transfer."},
 "fate": {"return_status": "none-found", "returned_by_bot_eth": None, "returned_by_builder_eth": None, "returned_total_eth": None, "returned_to": None,
          "returned_desc": ("Not returned. 1,726.59 ETH was forwarded to 0x3d32c5a2 four minutes later (block 17740980) and, on 2023-07-31 (blocks 17812383-17812515), 300+300+400+400+327 ETH went on to 0x160b431b... "
                            "(destination not attributed by us). Conic sent on-chain messages on 2023-07-22, 07-23 (offer of a 10% white-hat deal, citing Yoink's return) and 2023-08-08 (10% bounty for identifying information); no reply seen."),
          "bounty_kept_eth": None, "bounty_desc": "no bounty agreement", "kept_by_bot_eth": round(gross2 - gas_c, 9), "returned_txs": [],
          "public_statement": "Conic on-chain messages only (data/raw/etherscan/conic_ethattacker_after_txlist.json, conic_3d32_txlist.json)"},
 "raw_refs": refs2,
 "rawref_gaps": [{"field": "loot.captured_usd", "why": "no saved ETH price for 2023-07-21; not converted"}],
 "discrepancies": [
   "CertiK and DeFiHackLabs name 0x8d67db0b as 'the attacker'; Rekt (with the failed tx 0x97a8315e) identifies 0x10db234e as the original and 0x8d67db0b as a front-runner. On chain Rekt is right on identity; but it is a post-failure clone, not a front-run of a pending tx.",
   "Funding-link caveat: both EOAs were Tornado-funded; a same-operator second wallet is not excluded (why a clone with a new beneficiary instead of re-calling the first contract with more gas argues for a different operator)."],
 "evidence_notes": [
   f"Creation code of the two attack contracts: {ed['creation_code_bytes'][0]} bytes each, {ed['creation_code_differing_bytes']} bytes differ (one address at offset 1370: 0x10db234e... -> 0x8d67db0b...).",
   "Attack calldata byte-identical: selector 0x52558bb0, args 19700, 240, 3000, 180.",
   f"Trace diff: {ed['trace_frames'][0]} vs {ed['trace_frames'][1]} frames, type/target/selector sequence similarity {ed['frame_sequence_similarity_type_target_selector']}; first {ed['identical_leading_frames']} frames fully identical; the clone has {ed['frames_only_in_clone']} extra frames (the tail the original never reached).",
   "Original: gas limit 27.64M, 24.05M burned, OOG in a nested call to a Curve pool; clone: gas limit 29.5M, 20.14M used. The cause is inferred from the trace; no fork replay was run.",
   "Etherscan getLogs on the ETH pool for 17740000-17743500: only the clone tx emits the multi-event pattern."],
 "incident_dir": f"incidents/{S}",
}
write(S, [row1, row2])
