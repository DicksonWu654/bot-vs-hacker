"""Extract incident dataset row for metapool-2025 -> data/extract/metapool-2025.json. Run from project root:
   .venv/bin/python incidents/metapool-2025/scripts/build_incident.py   (builds incident.json / call_diff.json / timeline.json)
   .venv/bin/python scripts/dataset/extract_metapool-2025.py
   .venv/bin/python scripts/dataset/check_extract.py metapool-2025"""
import sys, pathlib, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _x6 import *

S = "metapool-2025"
D = f"incidents/{S}"
inc = load(f"{D}/incident.json")
n = inc["numbers"]
rY, rT1, rT2, rM, rC = (load(f"{D}/race_{b}.json") for b in (22722394, 22722643, 22722653, 22722911, 22722912))
Y = "0x4f43fc6d674e85f7d306debb4a3d48e7688c2fe5a6332dd9ad57558a15c86ef9"
T1 = "0x691c8070749f00a5a5be3135d3912ff97d0dad05a0fb2b77b235aaa13260f002"
T2 = "0x4858abc51876e1de9f506f34799d4f1852b4255f467b9e1f40951c631ddfa747"
MAIN = "0x57ee419a001d85085478d04dd2a73daa91175b1d7c11d8a8fb5622c56fd1fa69"
WD = "0xd1e3ab7353626a273f62ce26378317a20cf12923450ca7279620344f45075949"
RET = "0x3a21cb34c7ca1b0a662f3105a57305bd5d4b8ba7faafc1e05070b370b28ce035"
REW = "0xbd02fdab07f42ed0a21cc4e1464642f3b51805ea4d66aac1fa4cb4ea57e73ccc"
YOINK = "0xfde0d1575ed8e06fbf36256bcdfa1f359281455a"
MPOOL = "0x8c89569355f321a91655ca520fc09be5f6b0ec4d"
ty, t1, tm = txrow(rY, Y), txrow(rT1, T1), txrow(rM, MAIN)
assert ty["index"] == 0 and ty["status"] == 1 and ty["from"] == YOINK and t1["index"] == 91 and tm["index"] == 0
assert eth(ty["coinbase_transfer_wei"]) == n["coinbase_eth"]
cb = rY["block"]["fee_recipient"].lower()
refund = sum(int(t["value_wei"]) for t in rY["txs"] if t["from"].lower() == cb and (t["to"] or "").lower() in (inc["bots"][0]["contract"], YOINK))
assert refund == 0
auction = bvh.auction_summary(f"{D}/race_22722394.json", Y)
mrefs = ["data/raw/mempool-dumpster/2025-06-17.csv.zip", "data/raw/mempool-dumpster/2025-06-17_sourcelog.csv.zip"]
TY = f"data/raw/rpc/mp_trace_{Y}.json"
RAWE = lambda f: f"data/raw/etherscan/{f}"
ret_ts = iso(next(x for x in load(RAWE("mp2_0xfde0d1_txlist.json"))["result"] if x["hash"] == RET)["timeStamp"])
rew_ts = iso(next(x for x in load(RAWE("mp_M_txlist.json"))["result"] if x["hash"] == REW)["timeStamp"])
gap1, gapm = n["gap_yoink_to_first_attacker_tx_s"], n["gap_yoink_to_main_tx_s"]

refs = {
    "bot.block": "data/raw/rpc/block_22722394.json",
    "bot.position": ["data/raw/rpc/block_22722394.json", "data/raw/rpc/receipts_22722394.json"],
    "attacker_block": ["data/raw/rpc/block_22722643.json", "data/raw/rpc/receipts_22722643.json", f"data/raw/rpc/mp_tx_{T1}.json"],
    "loot.gross_loot_eth": [TY, f"data/raw/rpc/mp_rcpt_{Y}.json"],
    "loot.coinbase_paid_eth": [TY, "data/raw/rpc/trace_block_22722394.json"],
    "loot.priority_fee_paid_eth": ["data/raw/rpc/receipts_22722394.json", "data/raw/rpc/block_22722394.json"],
    "loot.builder_refund_to_bot_eth": ["data/raw/rpc/block_22722394.json", "data/raw/rpc/trace_block_22722394.json"],
    "loot.bot_net_eth": [TY, f"data/raw/rpc/mp_rcpt_{Y}.json", "data/raw/rpc/block_22722394.json"],
    "loot.captured_usd": ["data/raw/web-metapool/territoriobitcoin_metapool.html"],
    "fate.returned_by_bot_eth": [RAWE("mp2_0xfde0d1_txlist.json"), f"data/raw/rpc/mp_tx_{RET}.json"],
    "fate.returned_total_eth": [RAWE("mp2_0xfde0d1_txlist.json"), RAWE("mp_M_txlist.json")],
    "fate.bounty_kept_eth": [RAWE("mp_M_txlist.json"), f"data/raw/rpc/mp_tx_{REW}.json"],
    "fate.kept_by_bot_eth": [TY, RAWE("mp2_0xfde0d1_txlist.json"), RAWE("mp_M_txlist.json")],
    "evidence_level_mempool": mrefs,
    "bot_tx_trace": TY, "attacker_test1_trace": f"data/raw/rpc/mp_trace_{T1}.json", "attacker_test2_trace": f"data/raw/rpc/mp_trace_{T2}.json",
    "attacker_main_trace": f"data/raw/rpc/mp_trace_{MAIN}.json", "call_diff": f"{D}/call_diff.json",
    "attacker_txlists": [RAWE("mp_att_txlist.json"), RAWE("mp_att_txlistinternal.json"), RAWE("mp_d085_txlist.json"), RAWE("mp_d085_txlistinternal.json")],
    "mint_event_history": inc["raw_refs"]["mint_event_history"],
    "pool_state_before_yoink": ["data/raw/rpc/mp_poolbal_22722393.json", "data/raw/rpc/mp_poolbal_22722394.json", "data/raw/rpc/mp_v3weth_22722393.json", "data/raw/rpc/mp_v3weth_22722394.json"],
    "attacker_balances": ["data/raw/rpc/mp_ebal_A_22722393.json", "data/raw/rpc/mp_ebal_A_22722910.json", "data/raw/rpc/mp_ebal_D_22722393.json"],
    "meta_pool_admin_identity": [RAWE("mp_creation.json"), RAWE("mp_M_txlist.json")],
    "vault_balance_latest": "data/raw/rpc/mp_vaultbal_latest.json",
    "press_sources": ["data/raw/web-metapool/quillaudits_metapool_analysis.html", "data/raw/web-metapool/quillaudits_roundup_june2025.html",
                      "data/raw/web-metapool/solidityscan_metapool.html", "data/raw/web-metapool/territoriobitcoin_metapool.html",
                      "data/raw/web-metapool/cointelegraph_metapool.html", "data/raw/web-metapool/defihacklabs_MetaPool_exp.sol.txt"],
}

row = {
    "slug": S, "name": inc["name"], "date_utc": rY["block"]["timestamp_utc"].replace("+00:00", "Z"), "chain": "ethereum",
    "orig_verdict": inc["verdict"], "race_type_proposed": "bot-was-first-exploiter",
    "race_type_reason": (f"Yoink's tx (block 22722394, index 0, 06:18:59Z) is the first use of the mpETH mint-without-deposit bug on chain (all 381 mpETH mint events before it are fee or staking mints). "
                         f"The human attacker's first exploit tx is a test run {gap1//60} min later (block 22722643, EOA 0xd08559ce) and the main flash-loan tx {gapm//3600} h {gapm%3600//60:02d} min later (block 22722911); the main-tx EOA held 0.0008 ETH until the test proceeds arrived. "
                         "No attacker tx was pending when Yoink landed, so Yoink neither front-ran nor replayed anything; the attacker's txs share the call grammar but no contract or calldata with Yoink's. Press 'Yoink front-ran the attacker' is loose wording for 'Yoink got there first'."),
    "one_liner": "Yoink was the first to exploit Meta Pool's mpETH mint() bug (50.77 ETH gross, block 22722394), 50 min before the attacker's first test run and 1 h 44 min before its main tx; it returned its net 45.79 ETH and received a 5 ETH reward.",
    "attacker": {"eoa": inc["attacker"]["eoas"][0], "eoas": inc["attacker"]["eoas"], "contracts": inc["attacker"]["contracts"],
                 "funding": "unknown: EOA 0xd08559ce funded 2025-04-06 by unlabelled EOA 0xb0086e13 (0.0298 ETH), it funded 0x48f1d0f5 (0.001 ETH, 2025-04-29); no mixer seen",
                 "funding_tx": inc["attacker"]["funding_tx"], "deploy_tx": MAIN, "deploy_block": 22722911,
                 "attack_txs": [{"hash": t["hash"], "block": t["block"], "index": t["index"], "status": t["status"], "role": t["role"]} for t in inc["attacker"]["txs"]],
                 "none_reason": None,
                 "note": "The attacker is a LATER second-comer relative to Yoink (see race_type_reason). Cluster = EOAs 0xd08559ce (tests, funds the other) + 0x48f1d0f5 (main tx); proceeds parked at 0x45dd46c4 (23.68 ETH in 4 transfers)."},
    "bot": {"label": "Yoink", "eoa": YOINK, "contract": inc["bots"][0]["contract"], "tx": Y, "block": 22722394, "position": ty["index"], "status": "success",
            "priority_fee_gwei": ty["priority_fee_gwei"]},
    "bots_other": [{"label": "c0ffeebabe.eth (public tx-level facts only)", "eoa": "0xc0ffeebabe5d496b2dde509f9fa189c25cf29671", "tx": "0x22a4bdce5c1dd68b3106fc488b1c3e1353f6af35243214170c9258c4bd34505a",
                    "block": 22722912, "position": 0, "role": "transaction in block 22722912 at position 0, one block after the attacker; 0.0285 ETH returned to its EOA and 0.00315 ETH paid to the builder; trigger unknown"}],
    "evidence_level_mempool": "absent-from-archive",
    "mempool_note": "mempool-dumpster covers 2025-06-17 (csv + sourcelog; 974,844 unique txs; it held 25 of the 60 other txs of block 22722911). None of Yoink's tx, the attacker's three txs or c0ffeebabe's tx is in it (private flow), and no tx touching the mpETH proxy, unstake pool or V3 pool was public before 10:03Z. First-seen of every exploit tx is unknown, not none; for Yoink there was nothing public to react to.",
    "trigger": {"kind": None, "tx": None, "first_seen_utc_ms": None, "first_seen_utc": None, "sources": None,
                "note": "No trigger exists: no attacker tx or other Meta Pool tx was pending or on chain before Yoink's block that Yoink could have copied. The bug had been exploitable since the Dec 2023 implementation (pool balances unchanged for months); what made Yoink act at 06:18Z is unknown."},
    "attacker_block": 22722643,
    "attacker_block_note": f"Block of the attacker cluster's FIRST exploit tx (test run 0x691c8070, index 91, 07:08:59Z). attacker_block - bot.block = 249 means Yoink was 249 blocks (50 min) EARLIER, not that it beat a pending tx. The attacker's main tx landed at 22722911 index 0 (8:02:59Z).",
    "attacker_reference": {"kind": "attack-tx", "block": 22722643, "tx": T1},
    "auction": {**auction, "auction_note": "628 bids from 28 builders answered (Flashbots 128, Titan 500 = API cap; bloXroute-regulated delivered only, no bid history). The winning Titan block was delivered by bloXroute-regulated (5.0133 ETH to the proposer) and Yoink's 4.975 ETH payment is 99.2% of it; the winning block hash is not among the captured bids (Titan list capped). Record bids jump 0.14 -> 0.64 ETH at -1.19 s and to 5.1 ETH by +0.96 s. Not a competition for a pending attacker tx: no detection delay is defined."},
    "loot": {
        "scope": "bot-tx",
        "gross_loot_eth": round(n["gross_eth"], 12),
        "gross_loot_method": "ETH received by the Yoink contract from the unstake pool (103.256 ETH over 5 swaps) + WETH.withdraw from the V3 leg (37.510 ETH) minus the 90 ETH Uniswap v4 flash loan repaid in the same tx",
        "captured_native": {"amount": round(n["gross_eth"], 6), "unit": "ETH", "desc": "13.256 ETH net from the Meta Pool unstake pool (after its own 90 ETH deposit) + 37.510 WETH from the UniV3 mpETH/WETH pool; plus 28.926 unbacked mpETH swept to its vault (not counted)"},
        "captured_usd": 117000,
        "captured_usd_source": "Meta Pool's X post of 2025-06-21 as quoted by Territorio Bitcoin: 'the entire amount recovered by MEV Frontrunner [email redacted] - approximately $117,000 USD'; this is the recovered 45.79 ETH, not the gross (data/raw/web-metapool/territoriobitcoin_metapool.html)",
        "coinbase_paid_eth": round(n["coinbase_eth"], 12),
        "priority_fee_paid_eth": 0.0,
        "builder_refund_to_bot_eth": 0.0,
        "builder_payout_to_victim_eth": None,
        "bot_net_eth": round(n["net_eth"], 12),
        "loot_note": f"bot_net = gross {n['gross_eth']:.6f} - coinbase {n['coinbase_eth']:.6f} - gas {n['gas_eth']:.6f} (557,718 gas at base fee 0.391 gwei, priority fee 0) = {n['net_eth']:.6f} ETH. Coinbase / gross = 0.098000 exactly = tx value 98 wei read as per-mille (research/bot-re/analysis.md bribe rule). No builder refund in the 176-tx block (Titan's only transfers out are the proposer payment and small payouts to others).",
    },
    "fate": {
        "return_status": "returned",
        "returned_by_bot_eth": 45.79, "returned_by_builder_eth": None, "returned_total_eth": round(n["net_returned_eth"], 10),
        "returned_to": "0x8c89569355f321a91655ca520fc09be5f6b0ec4d: the Meta Pool admin EOA (deployed the mpETH implementation 0x37474845 in tx 0xc9aafccf, block 18851324; called toggleWhitelistEnabled() on mpETH at block 22723221)",
        "returned_desc": (f"2025-06-19T19:33:47Z Yoink withdrew 45.79 ETH from its contract (tx {WD[:10]}...), and at 19:39:23Z (block 22740672, tx {RET[:10]}...) sent exactly 45.79 ETH to Meta Pool's admin EOA = gross 50.7663 - 4.9751 builder bribe = 45.7912 ETH, rounded down. "
                          f"{rew_ts}: Meta Pool sent 5 ETH back to Yoink (tx {REW[:10]}...). Net returned to Meta Pool = 45.79 - 5.00 = 40.79 ETH. Meta Pool's X post (2025-06-21, quoted second-hand): 'From Exploit to Recovery: How 45 ETH Were Saved Thanks to Ethical Hackers'; ~$117k. "
                          "The 28.926 unbacked mpETH that Yoink's tx swept to its vault 0xc70f00cd is still there (no outbound mpETH transfer in Etherscan's token history; balance unchanged at the latest block), so the return covers the ETH leg only. The attacker returned nothing."),
        "bounty_kept_eth": 5.0, "bounty_desc": "5 ETH reward paid by the Meta Pool admin EOA to the Yoink EOA on 2025-06-20 (press: 'Meta Pool granted the group a reward of 5 ETH').",
        "kept_by_bot_eth": round(n["kept_by_bot_eth"], 6),
        "returned_txs": [
            {"tx": WD, "eth": 45.79, "note": "Yoink contract -> Yoink EOA withdrawTo", "block": 22740644, "time_utc": "2025-06-19T19:33:47Z"},
            {"tx": RET, "eth": 45.79, "note": "Yoink EOA -> Meta Pool admin EOA 0x8c895693", "block": 22740672, "time_utc": ret_ts},
            {"tx": REW, "eth": 5.0, "note": "Meta Pool admin EOA -> Yoink EOA (reward)", "block": 22745667, "time_utc": rew_ts},
        ],
        "public_statement": "Meta Pool X post 2025-06-21 'From Exploit to Recovery: How 45 ETH Were Saved Thanks to Ethical Hackers' ... 'the entire amount recovered by MEV Frontrunner [email redacted] - approximately $117,000 USD - was promptly returned to Meta Pool' (second-hand via Territorio Bitcoin, saved HTML; the original post was not retrievable). Yoink itself: no on-chain message found.",
    },
    "raw_refs": refs,
    "rawref_gaps": [
        {"field": "trigger (Yoink)", "why": "Yoink's tx is private flow (absent from mempool-dumpster); what made it act at 06:18Z is unknown. No public or on-chain precursor exists."},
        {"field": "attacker funding", "why": "0xb0086e13 funding of 0xd08559ce is an unlabelled one-tx EOA; no deeper tracing done"},
        {"field": "Meta Pool original post", "why": "the X post is only available quoted in the Territorio Bitcoin article; no first-party copy was fetchable"},
        {"field": "protocol_loss_usd", "why": "no USD price source saved; press figure $132k used only as context in incident.json"},
        {"field": "earlier private exploit", "why": "a private tx that never landed, or an exploit through another wrapper leaving no mint event, would be invisible (Unknown != none)"},
    ],
    "discrepancies": [
        "QuillAudits (analysis + June roundup), SolidityScan and Territorio Bitcoin say Yoink 'front-ran' the attacker. On chain Yoink landed 50 min before the attacker's first exploit tx and 1 h 44 min before the main one; no attacker tx was pending, so it is first-exploiter, not front-runner.",
        "DeFiHackLabs (MetaPool_exp.sol) lists 0x57ee419a as the attack, loss 25k USD, and does not mention Yoink or the earlier test txs 0x691c8070 / 0x4858abc5 (listed as 'attack transactions' by SolidityScan).",
        f"Press loss ~52.5 ETH (37.51 WETH + ~15 ETH). Traces: Yoink's tx gross {n['gross_eth']:.2f} ETH; attacker cluster realised {n['attacker_realised_eth']:.2f} ETH, of which about 10 WETH was a third party's swap into the V3 pool at block 22722814.",
        "QuillAudits roundup: 'retrieve $117k worth of assets as the attack was frontrun'. Retrieved = Yoink's 45.79 ETH net of a 4.975 ETH bribe, minus a 5 ETH reward Meta Pool paid; Meta Pool's net recovery is 40.79 ETH.",
    ],
    "evidence_notes": [
        f"{D}/call_diff.json: Yoink and the attacker's three txs call the same three victim contracts with the same exploit core (mint with 0 ETH -> pool.swapmpETHforETH after approve(pool,max) -> V3 leg); Yoink and the attacker's main tx both open with depositETH of flash-loaned ETH (Uniswap v4 90 ETH vs Balancer 200 WETH). No contract, recipient or amount is shared.",
        "data/raw/etherscan/mp_mintlogs_*.json: 381 mpETH mint (Transfer from 0x0) events before Yoink's block: 351 fee mints to 0xcab282ec and 30 mints to the vault itself, all from direct calls to the proxy with no top-level mint() selector; the first mint() abuse is Yoink's tx.",
        "data/raw/rpc/mp_poolbal_* / mp_v3weth_*: the V3 pool held 37.514 WETH unchanged from at least block 22.0M (Mar 2025) to Yoink's block, the unstake pool 15.154 ETH from block 22.70M (it had 50 ETH at 22.0M, 19 ETH at 22.5M); both are ~empty after Yoink (0.038 ETH, 0.004 WETH). So the bug was profitable for months, not newly profitable at 06:18Z.",
        "data/raw/rpc/mp_ebal_A_*: the main-tx EOA 0x48f1d0f5 had 0.00083 ETH at block 22722393 and 1.674 ETH at 22722910 (test-run proceeds); the main tx has a 29.1M gas limit at 1.02 gwei (~0.03 ETH).",
        "Address poisoning noise right after the return: 0x8c83812d... (looks like 0x8c895693) sent 0 ETH to Yoink at block 22740676 and 0xfde5a157... (looks like Yoink) sent 0 ETH to Meta Pool at 22740677; neither is a real party.",
    ],
    "incident_dir": D,
}
write(S, [row])
