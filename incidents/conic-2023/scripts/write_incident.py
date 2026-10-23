"""Write incidents/conic-2023/incident.json, timeline.json from saved raw data + analyze.py outputs.
Run after analyze.py:  .venv/bin/python incidents/conic-2023/scripts/write_incident.py"""
import json, pathlib, sys, datetime as dt
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
sys.path.insert(0, str(ROOT / "incidents" / "conic-2023" / "scripts"))
import rawfetch as rf  # noqa: E402
import analyze as A  # noqa: E402

D = ROOT / "incidents" / "conic-2023"
ld = lambda p: json.load(open(ROOT / p))  # noqa: E731
iso = lambda ts: dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
es = lambda k: ld(rf.raw_path("etherscan", k))["result"]  # noqa: E731
hdr = lambda b: rf.rpc("eth_getBlockByNumber", [hex(b), False], key=f"conic_blockhdr_{b}", source="rpc-conic")  # noqa: E731
ts = lambda b: iso(A.hx(hdr(b)["timestamp"]))  # noqa: E731
rp = lambda k, s="rpc-conic": rf.raw_path(s, k)  # noqa: E731

crv = ld("incidents/conic-2023/victim_call_diff_crvusd.json")
y10 = ld("incidents/conic-2023/yoink_10txs.json")
eth = ld("incidents/conic-2023/victim_call_diff_eth.json")
race = lambda b: ld(f"incidents/conic-2023/race_{b}.json")  # noqa: E731

# ---- hash lookups from saved Etherscan lists
c02 = {x["hash"]: x for x in es("conic_conic02_attacker_txlist")}
c02_int = es("conic_conic02_attacker_txlistinternal")
atk_h = {(int(x["blockNumber"]), x["input"][:10], int(x["transactionIndex"])): x["hash"] for x in c02.values()}
fund_hashes = [x["hash"] for x in c02_int if x["from"].lower() == "0x47ce0c6ed5b0ce3d3a51fdb1c52dc66a7c3c2936"]
clone_hist = es("conic_ethattacker_hist_txlist")
clone_after = es("conic_ethattacker_after_txlist")
clone_int = es("conic_ethattacker_hist_txlistinternal")
tc_fund_clone = [x for x in clone_int if x["blockNumber"] == "17725270"][0]["hash"]
three = es("conic_3d32_txlist")
moves = [x for x in three if x["from"].lower() == "0x3d32c5a2e592c7b17e16bddc87eab75f33ae3010" and x["to"].lower().startswith("0x160b431b")]
orig_int = es("conic_origattacker_txlistinternal")
tc_fund_orig = orig_int[0]["hash"]
laundering = [x for x in c02.values() if x["input"].startswith("0x13d98d13")]

A1, A2, A3, A4 = (atk_h[(17743470, "0x4c741db9", 4)], atk_h[(17743492, "0x4c741db9", 2)], atk_h[(17743521, "0x4c741db9", 2)], atk_h[(17743531, "0x4c741db9", 5)])
SETUP1, SETUP2 = atk_h[(17743467, "0x12424e3f", 84)], atk_h[(17743516, "0x12424e3f", 68)]
DEP1, DEP2 = atk_h[(17743464, "0x60806040", 98)], atk_h[(17743514, "0x60806040", 74)]
LAST = atk_h[(17743628, "0x5f1bbb2f", 0)]
CON2 = "0x17e0329d8ffe9b4cb1f740110a42ecb541179d9e"
attacker_gross = 11.562597740138712507 + 2.018288974295397285

# ---- Yoink aggregates
rows = y10["rows"]
fb = []  # auction per Yoink block (from race files that exist)
for b in (17743471, 17743472, 17743476, 17743480):
    try:
        r = race(b)
    except FileNotFoundError:
        continue
    last = r["txs"][-1]
    fb.append({"block": b, "builder_extra_data": r["block"]["extra_data"], "fee_recipient": r["block"]["fee_recipient"], "slot": r["block"]["slot"],
               "relay_bid_data": r["bid_summary"]["bids_per_relay"], "n_bids": r["bid_summary"]["n_bids"], "n_builders": r["bid_summary"]["n_builders"],
               "winning_bid_eth": r["winner"].get("bid_value_eth"), "winning_builder": r["winner"].get("builder_name"),
               "delivered_by_relays": r["winner"].get("delivered_by_relays"),
               "last_tx_in_block": {"index": last["index"], "from": last["from"], "to": last["to"], "value_eth": int(last["value_wei"]) / 1e18, "note": "builder-to-proposer payment"},
               "yoink_coinbase_eth": [f["coinbase_transfer_eth"] for f in r["focus_summary"]],
               "raw_ref": f"incidents/conic-2023/race_{b}.json"})

verdict_reason = (
    "No bot beat a pending attacker tx in either Conic pool. (1) crvUSD pool: Yoink gen1 replays the attacker's sandwich (same Balancer flash loan, same crvUSD "
    "create_loan, same Curve swap and Conic deposit/withdraw sequence with identical round-number sizes, amounts re-derived from live balances) ten times in "
    "blocks 17743471-17743480, starting ONE BLOCK AFTER the attacker's own successful tx (17743470 idx 4). Copy: confirmed. Order: after, so late-copy, not a front-run. "
    "(2) ETH pool (read-only reentrancy): the first attacker 0x10db234e deployed a contract and its attack tx reverted (out of gas, block 17740901); 51 blocks / ~10 min later "
    "0x8d67db0b redeployed the SAME creation code (one 20-byte address differs) and sent the identical calldata, succeeding at idx 0 of 17740955 for 1,724 ETH: "
    "post-failure-replay by an anonymous clone exploiter, not a bot beating a pending attack, and not returned. Neither case is 'post-hack arbitrage of an imbalance': "
    "the crvUSD copy is a replay of the attacker's exploit calls. In-block evidence only (no mempool archive before 2023-08-07)."
)

inc = {
    "slug": "conic-2023",
    "name": "Conic Finance omnipools, 2023-07-21: ETH pool read-only reentrancy (cloned after a failed first attempt) and crvUSD pool sandwich (replayed ten times by Yoink)",
    "date": "2023-07-21",
    "chain": "ethereum",
    "era": "early-pbs-2022-23; before the 2023-08-07 mempool archive, so in-block evidence only; Flashbots-relay bid history exists for most blocks",
    "verdict": "related-not-frontrun",
    "race_type": "late-copy",
    "headline": False,
    "verdict_reason": verdict_reason,
    "verdict_rule": "confirmed-onchain needs the bot first (earlier block / earlier index / before the attacker's call landed). Here the copier is second in both pools.",
    "protocol_loss_usd": {
        "eth_pool": "1,724.175 ETH taken by the clone tx (on-chain); press: ~$3.25M (DeFiHackLabs), $3.3M (Rekt), 1,724 ETH / $3.2M (CertiK)",
        "crvusd_pool": ("press: ~$300K taken (CertiK; Conic post-mortem via Rekt/DL News: attacker deposited ~$600K, withdrew ~$900K); DeFiHackLabs headline ~$934K. "
                        f"On-chain, the profit-taking txs we traced sum to {attacker_gross:.3f} ETH (attacker, 2 successful txs) + {y10['sum_eth']['gross']:.3f} ETH (Yoink gross, 10 txs). "
                        "No USD conversion is saved, so no USD figure of ours is given."),
    },
    "attacker": {
        "eth_pool_first_attacker": {
            "eoa": A.OE, "contract": A.OC, "deploy_tx": A.O_DEP, "deploy_block": 17740893, "deploy_index": 6,
            "funding": "Tornado Cash 1 ETH pool (0x47ce0c6e...2936) -> EOA, 0.98282 ETH, block 17740718 idx 22 (relayer-style withdrawal via router 0xd90e2f92...)",
            "funding_tx": tc_fund_orig,
            "txs": [{"hash": A.O_ATK, "block": 17740901, "index": 4, "status": "reverted",
                     "note": "selector 0x52558bb0, Aave+Balancer flash loans, Curve add/remove_liquidity, re-entrant ConicEthPool.withdraw; out of gas inside a nested Curve call; gas limit 27.64M, 24.05M burned; max priority 20 gwei (13.7 effective) = 0.73 ETH wasted",
                     "raw_ref": rp(f"trace_{A.O_ATK}")}],
            "only_two_txs_ever": True,
            "source_for_identity": "Rekt: 'Original failed tx (1st attack): 0x97a8315e...; Original exploiter address: 0x10db234e...'. We verified both on-chain.",
        },
        "eth_pool_clone_exploiter": {
            "eoa": A.CE, "contract": A.CC, "deploy_tx": A.C_DEP, "deploy_block": 17740952, "deploy_index": 3,
            "funding": "Tornado Cash 1 ETH pool -> EOA 0.98702 ETH on 2023-07-19 block 17725270 (about 52 hours before the first attacker's funding; the EOA also made unrelated deploy+call txs on 2023-07-20 at blocks 17731866-68 and 17732907-40)",
            "funding_tx": tc_fund_clone,
            "labels_reported": "'LadyPepe Token Exploiter' (BlockSec label via Rekt); CertiK names it 'Attacker'. Not verified by us.",
            "attack_tx": A.C_ATK, "attack_block": 17740955, "attack_index": 0,
            "loot_eth": 1724.175115775667, "proceeds_forwarded_to": "0x3d32c5a2e592c7b17e16bddc87eab75f33ae3010 ('Conic Finance Exploiter 2')",
        },
        "crvusd_pool_attacker": {
            "eoa": "0xb6369f59fc24117b16742c9dfe064894d03b3b80", "contracts": [A.A_CON, CON2],
            "funding": "Tornado Cash 1 ETH pool -> EOA, two withdrawals (0.96831 ETH block 17743378; 0.97064 ETH block 17743451)", "funding_txs": fund_hashes,
            "deploy_txs": [{"tx": DEP1, "block": 17743464, "index": 98, "contract": A.A_CON}, {"tx": DEP2, "block": 17743514, "index": 74, "contract": CON2}],
            "setup_txs": [{"tx": SETUP1, "block": 17743467, "index": 84, "note": "approvals (0x12424e3f)"}, {"tx": SETUP2, "block": 17743516, "index": 68}],
            "txs": [
                {"hash": A1, "block": 17743470, "index": 4, "status": "success", "profit_eth": 11.562597740138712, "gas_price_gwei": 36.574, "priority_fee_gwei": 1.0, "gas_used": 21658306},
                {"hash": A2, "block": 17743492, "index": 2, "status": "reverted", "note": "nested out of gas in the withdraw path; gas limit 25.28M, 24.46M used; 60.6 gwei"},
                {"hash": A3, "block": 17743521, "index": 2, "status": "reverted", "note": "out of gas in a staticcall (contract 2)"},
                {"hash": A4, "block": 17743531, "index": 5, "status": "success", "profit_eth": 2.018288974295397, "gas_used": 22293140},
                {"hash": LAST, "block": 17743628, "index": 0, "status": "reverted", "note": "selector 0x5f1bbb2f, 1.12M gas, 45.9 gwei"}],
            "total_profit_eth_two_successes": round(attacker_gross, 9),
            "laundering": f"9 x 1 ETH deposits to Tornado Cash router 0xd90e2f92... between blocks 17748821 and 17748913 (2023-07-22 12:59-13:18Z), tx e.g. {laundering[0]['hash']}",
        },
    },
    "sub_races": [
        {
            "id": "eth-pool", "pool": "0xbb787d6243a8d450659e09ea6fd82f1c859691e9", "date_utc": "2023-07-21T10:35:11Z", "block": 17740955,
            "verdict": "related-not-frontrun", "race_type": "post-failure-replay",
            "verdict_reason": ("The first attacker's attack tx (block 17740901 idx 4) reverted. 51 blocks (~10 min) later a different EOA deployed a byte-for-byte clone of the first attacker's contract "
                               "(creation code differs in exactly one 20-byte address, the beneficiary), sent identical calldata (0x52558bb0, args 19700/240/3000/180) and succeeded at idx 0 of 17740955, taking 1,724.175 ETH. "
                               "Nothing of the first attacker was pending in between (his EOA made only two txs ever). Not returned."),
            "calldata_diff": "incidents/conic-2023/victim_call_diff_eth.json",
            "assumption": "Clone operator assumed distinct from the first attacker (redeployed instead of re-calling the first contract; separate Tornado funding about 52 hours earlier; older EOA with unrelated deploy history). A second wallet of the same operator is not excluded.",
        },
        {
            "id": "crvusd-pool", "pool": "0x369cbc5c6f139b1132d3b91b87241b37fc5b971f", "date_utc": "2023-07-21T19:01:47Z", "block": 17743471,
            "verdict": "related-not-frontrun", "race_type": "late-copy",
            "verdict_reason": ("Yoink gen1 (EOA 0xfde0d157, contract 0xd050e0a4) replays the attacker's sandwich in ten consecutive blocks 17743471-17743480 at idx 0 (idx 4 once). "
                               "The attacker's own tx 0x37acd17a landed at 17743470 idx 4 and succeeded, so the copy comes after. Call-by-call diff: every state-changing call (Balancer flash loan, crvUSD create_loan/repay, "
                               "Curve crvUSD/USDC and crvUSD/USDT swaps, Conic deposit/withdraw, tricrypto exit) has the same target and selector in the same order; round-number sizes are identical, "
                               "state-derived sizes differ in the 3rd-4th digit."),
            "calldata_diff": "incidents/conic-2023/victim_call_diff_crvusd.json",
        },
    ],
    "bots": [
        {
            "label": "Yoink", "eoa": "0xfde0d1575ed8e06fbf36256bcdfa1f359281455a", "contract": A.YBOT, "generation": "gen1 (created 2022-12-02, block 16097930)",
            "txs": [{"hash": r["tx"], "block": r["block"], "index": r["index"], "status": "success", "msg_value_wei": r["msg_value_wei"], "gross_eth": round(r["gross_eth"], 9),
                     "coinbase_paid_eth": round(r["coinbase_paid_eth"], 9), "gas_cost_eth": round(r["gas_cost_eth"], 9), "net_eth": round(r["net_eth"], 9),
                     "builder": r["builder_extra_data"]} for r in rows],
            "captured": {"token": "ETH", "gross_amount": y10["sum_eth"]["gross"], "net_amount": y10["sum_eth"]["net"], "usd": None},
            "coinbase_paid_eth": y10["sum_eth"]["coinbase"], "gas_cost_eth": y10["sum_eth"]["gas"],
            "priority_fee_gwei": 0.0,
            "replay_evidence": "incidents/conic-2023/victim_call_diff_crvusd.json (attacker tx 0x37acd17a vs Yoink tx 0x64910b0a)",
            "bribe_rule_check": "coinbase / gross equals msg.value per mille (131 -> 0.131 etc.), the same rule research/bot-re/analysis.md derived for gen2/gen3 (checked on all ten txs, yoink_10txs.json).",
            "notes": ("Ten copies in ten blocks; each tx used ~21.2M gas (70% of the block), which also pushed the base fee from 35.6 to 103.5 gwei (blocks 17743470 to 17743481). "
                      "Coinbase went to the block's builder: rsync-builder.xyz, 'I can haz block?' (0x229b8325, the builder EigenPhi attributes to Yoink per research/bot-re/analysis.md) and builder0x69. "
                      "Yoink stopped after 17743480; why is unknown (Conic paused deposits at some point; we did not time it)."),
        },
        {
            "label": "anon clone exploiter (not a known bot)", "eoa": A.CE, "contract": A.CC, "txs": [
                {"hash": A.C_DEP, "block": 17740952, "index": 3, "status": "success", "role": "deploy clone (21,970-byte creation code, one 20-byte diff)"},
                {"hash": A.C_ATK, "block": 17740955, "index": 0, "status": "success", "gas_limit": 29500000, "gas_used": eth["clone"]["gas_used"], "priority_fee_gwei": 3.0, "coinbase_paid_eth": 0.0}],
            "captured": {"token": "ETH", "amount": 1724.175115775667, "usd": None}, "coinbase_paid_eth": 0.0, "priority_fee_gwei": 3.0,
            "replay_evidence": "incidents/conic-2023/victim_call_diff_eth.json", "notes": "Keeps the funds; ignored four on-chain messages from Conic (2023-07-22, -23, -08-08 offering a 10% bounty)."},
    ],
    "other_racers": [
        {"what": "crvUSD pool: other txs emitting the 4x deposit/withdraw pattern between blocks 17743300 and 17743700",
         "result": "only the attacker's two successes and Yoink's ten (Etherscan getLogs on the pool, data/raw/etherscan/conic_logs_omnipool_17743300_17743700.json). the other 25 pool txs in that window emit a single event each (ordinary deposits/withdrawals)."},
        {"what": "ETH pool: other multi-event txs on ConicEthPool 17740000-17743500", "result": "only the clone tx 0x8b74995d (data/raw/etherscan/conic_logs_ethpool_17740000_17743500_p1.json)."},
        {"what": "attacker's own later attempts on the crvUSD pool", "result": "0x8478a956 (17743492) and 0xc8818aa3 (17743521) reverted; 0xc08bfee8 (17743531) succeeded for 2.018 ETH after redeploying a new contract."}],
    "funds_fate": [
        {"what": "Yoink returned 90.0% of its net to Conic", "tx": y10["returned_tx"], "block": 17756778, "amount_eth": y10["returned_to_conicfinance_eth"], "to": "0xedaeb101f34d767f263c0fe6b8d494e3d071f0ba (conicfinance.eth, deployer of the crvUSD pool)",
         "detail": f"net {y10['sum_eth']['net']:.5f} ETH = gross {y10['sum_eth']['gross']:.5f} - coinbase {y10['sum_eth']['coinbase']:.5f} - gas {y10['sum_eth']['gas']:.5f}; kept {y10['kept_by_yoink_eth']:.5f} ETH (10% bounty by agreement)"},
        {"what": "coinbase payments of Yoink's ten txs went to builders, who pass them on to the proposer", "amount_eth": y10["sum_eth"]["coinbase"],
         "detail": "block 17743471: builder (rsync) paid proposer 1.70579 ETH in the last tx against Yoink's 1.64844 ETH coinbase; 17743472: 'I can haz block?' bid/paid 2.43348 ETH against 2.44970 ETH. No builder refund tx to Yoink seen in 17743471/17743472."},
        {"what": "ETH-pool loot not returned", "tx": "0x388a60c2958cd6dd5f8b9efe8163938700fcdc4ac40b8e70d07d27163b07acf3", "amount_eth": 1726.5914693180482, "to": "0x3d32c5a2e592c7b17e16bddc87eab75f33ae3010 (block 17740980)",
         "detail": "then 300+300+400+400+327 ETH from 0x3d32c5a2 to 0x160b431b... on 2023-07-31 (blocks 17812383-17812515); destination not attributed by us"},
        {"what": "crvUSD attacker's take", "amount_eth": round(attacker_gross, 6), "detail": "laundered via Tornado Cash (9 x 1 ETH deposits, 2023-07-22)"}],
    "auction_summary": {
        "relays_that_answered": "Flashbots (bid history 2023); Ultra Sound, Agnostic, bloXroute-regulated, Aestus, Titan, ETHGas, BTCS answered with no data for most blocks; Eden, Manifold, bloXroute max-profit/ethical, Blocknative unreachable or timed out",
        "yoink_blocks": fb,
        "reading": ("17743471 (first copy): no relay recorded this block, builder rsync-builder.xyz, proposer paid 1.7058 ETH in the last tx, of which Yoink's coinbase transfer was 1.6484 ETH (96.6%). "
                    "17743472: 57 Flashbots-relay bids, first at -9.9 s, winning bid 2.4335 ETH at -1.18 s from 'I can haz block?' (Yoink's coinbase 2.4497 ETH). "
                    "Bid contents are not public, so whether a given bid contained the Yoink tx is unknown except for the winning block."),
        "attacker_block_17743470": {"builder": "Made on the moon by Blocknative", "winning_bid_eth": 0.2379, "n_bids": 192, "attacker_tx_priority_fee_gwei": 1.0, "attacker_index": 4,
                                    "note": "low-priority tx at idx 4 of a full block: consistent with the public mempool but not proven (no archive for 2023-07-21)"},
        "eth_pool_clone_block_17740955": {"builder": "rsync-builder.xyz", "winning_submission_eth": 0.12459, "winning_submission_t_rel_slot_ms": 231, "n_bids": 273, "clone_index": 0, "clone_priority_fee_gwei": 3.0},
    },
    "claims_checked": [
        {"claim": "w1 candidates.json: 'Yoink captured value from attacker's imbalance, not a copy'", "result": "WRONG for the call content: Yoink's victim-call sequence and round-number parameters equal the attacker's (victim_call_diff_crvusd.json). It is a copy, but a late one (next block)."},
        {"claim": "w1 candidates.json: 'crvUSD-pool attacker tx not identified'", "result": "Identified: EOA 0xb6369f59, contract 0x486cb3f6, tx 0x37acd17a (also DeFiHackLabs Conic02)."},
        {"claim": "yoink_more_incidents.json: Yoink gen1 made 10 consecutive-block txs 17743471-17743480, idx 0/4, ~1.4-2.7 ETH coinbase", "result": "CONFIRMED (coinbase 1.380-2.690 ETH)."},
        {"claim": "Yoink took 125.82 ETH, spent 35.48 on gas/bribes, returned 81.307, kept 10%", "result": f"CONFIRMED to <1e-5 ETH: gross {y10['sum_eth']['gross']:.5f}, coinbase+gas {y10['sum_gas_plus_coinbase_eth']:.5f}, net {y10['sum_eth']['net']:.5f}; returned {y10['returned_to_conicfinance_eth']:.6f} = {y10['returned_pct_of_net']:.2f}% of net"},
        {"claim": "Rekt: 'Both attacks were frontrun'", "result": "Not as front-runs. ETH pool: a clone exploit after the first attacker's attempt had already reverted. crvUSD pool: Yoink copied after the attacker's tx had landed."},
        {"claim": "CertiK: crvUSD loss was MEV arbitrage of an imbalance caused by the first exploit", "result": "Not supported: the crvUSD pool was sandwiched by a separate Tornado-funded attacker with his own contract, flash loan and loop (DeFiHackLabs Conic02 PoC matches the trace); Yoink copied that."},
        {"claim": "DL News/Conic: the bot 'unwittingly' traded against the imbalance", "result": "Conic's own on-chain message says 'your bot has replicated an attack'. The calls are a replay; what Yoink 'knew' is not observable."},
        {"claim": "DeFiHackLabs date 2023-07-22 for Conic02", "result": "The tx is 2023-07-21T19:01:35Z (block 17743470)."}],
    "sources": [
        "https://rekt.news/conic-finance-rekt/", "https://dlnews.com/articles/defi/conic-finance-does-not-blame-auditor-peckshield-for-hack/",
        "https://www.certik.com/resources/blog/conic-finance-incident-analysis", "https://medium.com/@ConicFinance/post-mortem-eth-and-crvusd-omnipool-exploits-c9c7fa213a3d (Cloudflare-blocked when fetched; content via Rekt/DL News/CertiK)",
        "https://github.com/SunWeb3Sec/DeFiHackLabs (src/test/2023-07/Conic02_exp.sol, Conic_exp.sol)", "https://etherscan.io/tx/" + A.C_ATK, "https://etherscan.io/tx/" + A1,
        "https://etherscan.io/tx/" + y10["returned_tx"]],
    "raw_refs": {
        "crvusd_attacker_trace": rp(f"trace_{A1}"), "yoink_first_trace": rp(f"trace_{A.Y_TXS[0]}"), "eth_original_trace": rp(f"trace_{A.O_ATK}"), "eth_clone_trace": rp(f"trace_{A.C_ATK}"),
        "yoink_return_trace": rp(f"trace_{y10['returned_tx']}"), "web_rekt": "data/raw/web-conic/rekt.html", "web_dlnews": "data/raw/web-conic/dlnews.html", "web_certik": "data/raw/web-conic/certik.html",
        "dhl_conic02_poc": "data/raw/web-conic/dhl_conic02.txt", "dhl_conic_poc": "data/raw/web-conic/dhl_conic.txt"},
    "mempool_evidence": "in-block evidence only (mempool-dumpster starts 2023-08-07; blockrace.py recorded 'no data before' for every focus tx)",
}
json.dump(inc, open(D / "incident.json", "w"), indent=1)

# ------------------------------------------------------------------------------------------------ timeline
T = []
def ev(block, kind, actor, detail, tx=None, raw=None, t=None, rel=None):
    e = {"t_utc": t or ts(block), "t_precision": "block timestamp (second resolution); no sub-block time available", "block": block, "kind": kind, "actor": actor, "detail": detail}
    if tx: e["tx"] = tx
    if raw: e["raw_ref"] = raw
    if rel is not None: e["t_rel_slot_ms"] = rel
    T.append(e)

ev(17725270, "fund", "clone exploiter 0x8d67db0b", "Tornado Cash 1 ETH pool pays 0.98702 ETH to the EOA that will later clone the first attacker's contract", tc_fund_clone, rp("conic_blockhdr_17725270"))
ev(17740718, "fund", "first ETH-pool attacker 0x10db234e", "Tornado Cash 1 ETH pool pays 0.98282 ETH", tc_fund_orig, "data/raw/etherscan/conic_origattacker_txlistinternal.json")
ev(17740893, "deploy", "first ETH-pool attacker 0x10db234e", "deploys attack contract 0xdac434f8 (21,970-byte creation code), idx 6", A.O_DEP, rp(f"conic_tx_{A.O_DEP}"))
ev(17740901, "tx", "first ETH-pool attacker 0x10db234e", "attack tx 0x52558bb0 REVERTS (out of gas in a nested Curve call; gas limit 27.64M); idx 4, builder0x69 block, 13.7 gwei effective tip", A.O_ATK, rp(f"trace_{A.O_ATK}"))
ev(17740947, "tx", "clone exploiter 0x8d67db0b", "unwraps 3.15 WETH to ETH for gas", "0x813f6cb1ae3f745f1bfb21228819afe937b354e4b85194bf4e1b626903c11915", "data/raw/etherscan/conic_ethattacker_hist_txlistinternal.json")
ev(17740952, "deploy", "clone exploiter 0x8d67db0b", "deploys 0x743599ba: SAME creation code as the failed attacker's contract except one 20-byte address (offset 1370); idx 3, 51 blocks (~10 min) after the failed attack", A.C_DEP, "incidents/conic-2023/victim_call_diff_eth.json")
ev(17740955, "tx", "clone exploiter 0x8d67db0b", "attack tx, identical calldata (0x52558bb0; 19700, 240, 3000, 180), idx 0 of an rsync-builder block, 3 gwei tip, 29.5M gas limit / 20.14M used: SUCCESS, 1,724.175 ETH to the EOA", A.C_ATK, "incidents/conic-2023/race_17740955.json")
ev(17740955, "bid", "rsync-builder.xyz", "winning submission to the Flashbots relay at +231 ms, 0.12459 ETH (proposer payment tx 0xf699a28d in the block's last position); relay delivered-payload record not found for this slot", None, "incidents/conic-2023/race_17740955.json", rel=231)
ev(17740980, "return", "clone exploiter 0x8d67db0b", "forwards 1,726.59 ETH to 0x3d32c5a2 (not returned)", "0x388a60c2958cd6dd5f8b9efe8163938700fcdc4ac40b8e70d07d27163b07acf3", "data/raw/etherscan/conic_ethattacker_after_txlist.json")
for h in fund_hashes:
    b = 17743378 if h.startswith("0x4e2678") else 17743451
    ev(b, "fund", "crvUSD attacker 0xb6369f59", "Tornado Cash 1 ETH pool pays ~0.97 ETH", h, "data/raw/etherscan/conic_conic02_attacker_txlistinternal.json")
ev(17743464, "deploy", "crvUSD attacker 0xb6369f59", "deploys attack contract 0x486cb3f6 (idx 98, Titan block)", DEP1, "incidents/conic-2023/race_17743464.json")
ev(17743467, "tx", "crvUSD attacker 0xb6369f59", "setup tx (approvals), idx 84", SETUP1, "incidents/conic-2023/race_17743467.json")
ev(17743470, "tx", "crvUSD attacker 0xb6369f59", "attack tx: Balancer flash loan 12M USDC / 80,000 WETH / 9M USDT, 4 sandwich rounds on the Conic crvUSD pool; idx 4, 1 gwei tip, 21.66M gas; SUCCESS, +11.5626 ETH", A1, "incidents/conic-2023/race_17743470.json")
ev(17743470, "bid", "Made on the moon by Blocknative", "winning bid 0.23792 ETH delivered via Agnostic; 192 Flashbots-relay bids, first at -9.8 s", None, "incidents/conic-2023/race_17743470.json")
for r in rows:
    ev(r["block"], "tx", "Yoink 0xfde0d157", f"copy #{rows.index(r)+1}: replays the attacker's sandwich via bot 0xd050e0a4; idx {r['index']}; gross {r['gross_eth']:.4f} ETH, coinbase {r['coinbase_paid_eth']:.4f} to {r['builder_extra_data']}, gas {r['gas_cost_eth']:.4f}; net {r['net_eth']:.4f} ETH",
       r["tx"], r["raw_refs"][0])
ev(17743471, "block", "rsync-builder.xyz", "builder pays proposer 1.70579 ETH in the block's last tx; no relay recorded this block", None, "incidents/conic-2023/race_17743471.json")
ev(17743472, "bid", "'I can haz block?'", "winning bid 2.43348 ETH at -1,180 ms (57 Flashbots-relay bids; first at -9,949 ms)", None, "incidents/conic-2023/race_17743472.json", rel=-1180)
ev(17743492, "tx", "crvUSD attacker 0xb6369f59", "retry with contract 1 REVERTS (nested out of gas), idx 2, 60.6 gwei", A2, "incidents/conic-2023/race_17743492.json")
ev(17743514, "deploy", "crvUSD attacker 0xb6369f59", "deploys second attack contract 0x17e0329d, idx 74", DEP2, rp(f"conic_blockhdr_17743514"))
ev(17743516, "tx", "crvUSD attacker 0xb6369f59", "second setup tx, idx 68", SETUP2, rp("conic_blockhdr_17743516"))
ev(17743521, "tx", "crvUSD attacker 0xb6369f59", "attack with contract 2 REVERTS (out of gas), idx 2", A3, rp("conic_blockhdr_17743521"))
ev(17743531, "tx", "crvUSD attacker 0xb6369f59", "attack with contract 2 SUCCEEDS, idx 5, +2.0183 ETH", A4, "incidents/conic-2023/race_17743531.json")
ev(17748821, "tx", "crvUSD attacker 0xb6369f59", "begins 9 x 1 ETH deposits into the Tornado Cash router (to block 17748913)", laundering[0]["hash"], "data/raw/etherscan/conic_conic02_attacker_txlist.json")
ev(17749857, "message", "conicfinance.eth", "on-chain message to the ETH-pool clone EOA 0x8d67db0b ('another attempt at trying to contact you...')", "0x4704290baebde66e5f7f644e773e6293b9dc9c9148bdd6f62ac000f27e1df5b4", rp("conic_tx_0x4704290baebde66e5f7f644e773e6293b9dc9c9148bdd6f62ac000f27e1df5b4"))
ev(17749937, "message", "conicfinance.eth", "to Yoink: 'Your bot has replicated an attack on Conic Finance ... open to returning these funds in exchange for a bounty?'", "0x6382dad8f1f08c90aa74a01bae2ec414161821b276f8955cb8dddc68856c03ce", rp("conic_tx_0x6382dad8f1f08c90aa74a01bae2ec414161821b276f8955cb8dddc68856c03ce"))
ev(17751975, "message", "Yoink 0xfde0d157", "'my bot took 125.82415 Eth while spending 35.48275 in gas fees and bribes, leaving 90.34139 to return. ... Would appreciate a bounty'", "0xaf1535ea5bee7ccbc048eafd1fe0771c31cde51d065e6abc2c4aa2c1f9d264ff", rp("conic_tx_0xaf1535ea5bee7ccbc048eafd1fe0771c31cde51d065e6abc2c4aa2c1f9d264ff"))
ev(17756297, "message", "conicfinance.eth", "agrees the numbers, offers 10% bounty, asks for 81.307251 ETH to conicfinance.eth", "0x9074a68818751bcfe88c22f483784bf686481ee8b7b3f81e00b03d36628a4b47", rp("conic_tx_0x9074a68818751bcfe88c22f483784bf686481ee8b7b3f81e00b03d36628a4b47"))
ev(17756778, "return", "Yoink 0xfde0d157", "bot contract withdrawTo: 81.307251 ETH to conicfinance.eth (90.0% of net 90.341; Yoink keeps 9.034 ETH)", y10["returned_tx"], rp(f"trace_{y10['returned_tx']}"))
ev(17757958, "message", "conicfinance.eth", "'Thank you very much for returning the funds so quickly.'", "0xd9f718386aa359cd5f2d15619a3a536eb3d17eb10c0cac78106440b3d4c92ce5", rp("conic_tx_0xd9f718386aa359cd5f2d15619a3a536eb3d17eb10c0cac78106440b3d4c92ce5"))
ev(17758024, "message", "conicfinance.eth", "to 0x3d32c5a2 (ETH-pool loot): cites Yoink's return and offers a 24 h white-hat deal", "0x5cf6288c7940150e3624c3459f26f837109262002add2f89488b07b64b0ef3a8", rp("conic_tx_0x5cf6288c7940150e3624c3459f26f837109262002add2f89488b07b64b0ef3a8"))
for m in moves:
    ev(int(m["blockNumber"]), "tx", "0x3d32c5a2 (ETH-pool loot)", f"sends {int(m['value'])/1e18:.0f} ETH to 0x160b431b... (onward destination not attributed)", m["hash"], "data/raw/etherscan/conic_3d32_txlist.json")
T.sort(key=lambda e: (e["block"], 0 if e["kind"] in ("fund", "deploy") else 1))
json.dump(T, open(D / "timeline.json", "w"), indent=1)
print("wrote incident.json, timeline.json;", len(T), "events")
