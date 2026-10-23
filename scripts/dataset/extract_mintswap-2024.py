"""Extract mintswap-2024 -> data/extract/mintswap-2024.json. Run from project root with .venv/bin/python, AFTER
scripts/dataset/build_mintswap-2024.py (which writes incidents/mintswap-2024/*.json from saved raw files).
One row: Yoink was the first exploiter of MintSwap's sell-path pricing bug (no separate attacker)."""
import json, pathlib, sys, datetime as dt
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import bvh, rawfetch

SLUG = "mintswap-2024"
D = f"incidents/{SLUG}"
J = lambda p: json.load(open(ROOT / p))
res = lambda d: d.get("result", d)
iso = lambda ts: dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

inc = J(f"{D}/incident.json")
tabs = J(f"{D}/yoink_mintswap_txs.json")
pool = J(f"{D}/pool_history.json")
diff = J(f"{D}/pending_user_call_diff.json")
arb = J(f"{D}/other_bot_0x4ab.json")
race = J(f"{D}/race_19563164.json")
T = tabs["totals"]
rows = tabs["txs"]
BOT_TX = "0xd2337efb820b7bce143bd940f9738b288540a9a88f791177f156bbe2b5b86d20"
BUY_TX = "0x29edec50fbaf213f26b69b97daf8182067f2f292b4123225b0713ed24af0b620"
RETURN_TX = "0x1d3c141c4606fa1083fae092d2a2b92a3edca998d940f4ac2e5cbeb6e292a35c"
OFFER_TX = "0x89af126f81e8cfcc7026da0ff5c203338444fdeff8bb54284ea38af3b18a1055"
NOTICE_TX = "0xfe5020429a451908be819ee7b3dc833115cc32e902e759ea6a8bdc4d8110d5c0"
USER_SELL = "0x2bca4d6150d1c8e852229215dd92a75e2d39b7b41281872e77458c0d266e2ba0"
ROUTER = pool["pool"]
YOINK_EOA = "0xfde0d1575ed8e06fbf36256bcdfa1f359281455a"
LP = "0x5b033ca6ff0465b8857dbf03c9c9d17026eeed00"

tx0 = next(t for t in race["txs"] if t["hash"] == BOT_TX)
assert tx0["index"] == 0 and tx0["status"] == 1 and tx0["from"] == YOINK_EOA
assert pool["first_sell_path_call"]["hash"] == BOT_TX and pool["first_sell_path_call"]["block"] == 19563164
ret_tr = res(J(f"data/raw/rpc/trace_{RETURN_TX}.json"))
assert len(ret_tr["calls"]) == 1 and ret_tr["calls"][0]["to"].lower() == LP and int(ret_tr["calls"][0]["value"], 16) == 91_620_000_000_000_000_000
ret_tx = res(J(f"data/raw/rpc/tx_{RETURN_TX}.json"))
ret_block = int(ret_tx["blockNumber"], 16)
ret_hdr = rawfetch.rpc("eth_getBlockByNumber", [hex(ret_block), False], key=f"blockhdr_{ret_block}", source="rpc")
ret_time = iso(int(ret_hdr["timestamp"], 16))
auction = bvh.auction_summary(f"{D}/race_19563164.json", BOT_TX)
auction["other_blocks"] = inc["auction"]["other_blocks"]
auction["auction_note"] = inc["auction"]["auction_note"]
auction["builder_refund"] = inc["auction"]["builder_refund"]

bal163, bal194 = pool["balances_pool"]["19563163"], pool["balances_pool"]["19563194"]
pool_loss_eth = bal163["eth"] - bal194["eth"]
returned = 91.62
bot_net = T["bot_net_est"]
kept = round(bot_net - returned, 4)
BLK = {n: f"data/raw/rpc/block_{n}.json" for n in (19563164, 19563165, 19563183, 19563184, 19563189, 19563190)}
TR = [f"data/raw/rpc/trace_{r['hash']}.json" for r in rows]
RC = [f"data/raw/rpc/receipt_{r['hash']}.json" for r in rows]
POOLRAW = [f"data/raw/etherscan/txlist_{ROUTER}.json", f"data/raw/etherscan/txlistinternal_{ROUTER}.json", f"data/raw/etherscan/tokentx_{ROUTER}.json"]
BAL = [f"data/raw/rpc/balance_{ROUTER}_19563163.json", f"data/raw/rpc/balance_{ROUTER}_19563194.json"]
MEM = ["data/raw/mempool-dumpster/2024-04-01.csv.zip", "data/raw/mempool-dumpster/2024-04-01_sourcelog.csv.zip"]
refs = {
    "bot.block": [BLK[19563164]], "bot.position": [BLK[19563164]],
    "loot.gross_loot_eth": TR + list(BLK.values()), "loot.coinbase_paid_eth": TR, "loot.priority_fee_paid_eth": RC + list(BLK.values()),
    "loot.builder_refund_to_bot_eth": list(BLK.values()), "loot.bot_net_eth": TR + RC + list(BLK.values()),
    "fate.returned_by_bot_eth": [f"data/raw/rpc/trace_{RETURN_TX}.json"], "fate.returned_total_eth": [f"data/raw/rpc/trace_{RETURN_TX}.json"],
    "fate.bounty_kept_eth": TR + RC + list(BLK.values()) + [f"data/raw/rpc/trace_{RETURN_TX}.json"], "fate.kept_by_bot_eth": TR + RC + list(BLK.values()) + [f"data/raw/rpc/trace_{RETURN_TX}.json"],
    "evidence_level_mempool": MEM, "pool_loss": POOLRAW + BAL,
    "auction": [f"{D}/race_19563164.json"],
}
for k in ("loot.priority_fee_paid_eth",):
    pass

row = {
    "slug": SLUG, "name": inc["name"],
    "date_utc": race["block"]["timestamp_utc"].replace("+00:00", "Z"),
    "chain": "ethereum",
    "orig_verdict": inc["verdict"],
    "race_type_proposed": "bot-was-first-exploiter",
    "race_type_reason": ("The two txs the MintSwap team cites as the hack (0xd2337efb, 0x29edec50) are Yoink's own, index 0 of blocks 19563164/65. The pool's full transfer history shows Yoink's tx is the first call to the sell path ever; "
                         "no other actor sold into the pool until Yoink had drained it (a pool-vs-V2 arbitrage searcher then made two small sells, 0.78 ETH, in blocks 19563191/93). The one third-party tx Yoink beat is an innocent user's still-pending 5,991 vMINT sell "
                         "(public mempool 9.4 s before the block, reverted afterwards); Yoink's call is a different construction (314x the amount, 1 wei min-out, own recipient), so it is not a replay, and a trigger is unproven."),
    "one_liner": "Yoink was the first to exploit MintSwap's vMINT/ETH sell-path pricing bug (swapExactTokensForETH used getAmountIn): 6 pool txs in 6 blocks, about 101.8 ETH net after 110.8 ETH of builder bribes; it returned 91.62 ETH to the LP, keeping a 10% bounty.",
    "attacker": {"eoa": None, "eoas": [], "contracts": [], "funding": "n/a", "funding_tx": None, "deploy_tx": None, "deploy_block": None, "attack_txs": [],
                 "none_reason": "No separate attacker: the txs the MintSwap team cites as the exploit are Yoink's. No other sell-path call exists before them (pool_history.json); a private attacker tx that never landed would be invisible (Unknown != none)."},
    "bot": {"label": "Yoink", "eoa": tx0["from"], "contract": tx0["to"], "tx": BOT_TX, "block": 19563164, "position": tx0["index"], "status": "success",
            "priority_fee_gwei": tx0["priority_fee_gwei"]},
    "bots_other": [
        {"label": "pool-vs-V2 arbitrage searcher EOA 0x1a56abf4 via contract 0x4ab12e7c (not Yoink)", "eoa": arb["eoa"], "tx": [x["hash"] for x in arb["txs"] if not x["before_yoink"]][0], "block": 19563166, "position": [x for x in arb["txs"] if not x["before_yoink"]][0]["index"], "status": "success",
         "role": "late-copy: 2 buy-side arbs at 18:30 and 18:34 (before Yoink, correct buy-side price, +0.14 ETH); 11 txs in blocks 19563166-194 after Yoink, two of which (19563191, 19563193) sell 19,319 and 5,288 vMINT into the pool for 0.62 and 0.16 ETH"},
        {"label": "pending user sell, 0x7a61c7d3 (innocent user)", "eoa": diff["pending_user_tx"]["from"], "tx": USER_SELL, "block": 19563166, "position": diff["pending_user_tx"]["index"], "status": "reverted",
         "role": "collateral, not a racer: public-mempool sell of 5,991.78 vMINT first seen 19:49:25.637, reverted with MintSwap: SLIPPAGE_REACHED after Yoink drained the pool"}],
    "evidence_level_mempool": "measured",
    "mempool_note": ("mempool-dumpster 2024-04-01 (csv + sourcelog) covers the pool's pre-exploit buys, the LP deposit and the user's pending sell (5 sources within 139 ms). None of Yoink's 10 txs is in the archive (private bundles). "
                     "'measured' refers to the user tx and the absence of any other pending sell-path call; Yoink's own first-seen time is not measurable."),
    "trigger": {"kind": None, "tx": None, "first_seen_utc_ms": None, "first_seen_utc": None, "sources": None,
                "note": ("No confirmed trigger. Candidate: user sell %s, first seen %s (5 sources), 9.4 s before block 19563164 and the first and only public call to the sell path. Yoink's router deadline (20:49:25 = 19:49:25 + 3600 s) puts its build "
                         "in the same second, but Yoink builds each MintSwap tx 0-2 s after the previous block (six of six), and its follow-up sells in blocks 19563183/189 had no public trigger at all. Left null so detection-latency stats do not count it." % (USER_SELL[:10], diff["pending_user_tx"]["first_seen_utc"]))},
    "trigger_candidate": {"tx": USER_SELL, "first_seen_utc": diff["pending_user_tx"]["first_seen_utc"], "status": "unproven", "detail_file": f"{D}/pending_user_call_diff.json"},
    "attacker_block": None,
    "attacker_block_note": "No attacker tx exists to compare against.",
    "attacker_reference": {"kind": "none", "block": None, "tx": None},
    "auction": {**auction, "auction_note": auction["auction_note"]},
    "loot": {
        "scope": "campaign: 10 Yoink txs in 6 blocks (19563164, 65, 183, 184, 189, 190)",
        "gross_loot_eth": T["est_gross_all"],
        "gross_loot_method": ("sum over 10 txs of coinbase_paid / (msg.value/1000), the bot analysis bribe rule (research/bot-re/analysis.md). 6 of the 10 txs call the MintSwap pool (est. gross %.3f ETH); the other 4 are same-block Yoink txs that touch the "
                              "Uniswap V2 vMINT/USDT pair but not the pool (est. %.3f ETH). The sum is NOT the pool's loss: the pool lost %.3f ETH + 3.81M vMINT between blocks 19563163 and 19563194; Yoink's net ETH out of the pool was %.3f ETH over the 6 pool txs; "
                              "the difference is value realised on the Uniswap V2 legs around the pool, whose accounting was not examined." % (T["est_gross_pool_txs"], T["est_gross_all"] - T["est_gross_pool_txs"], pool_loss_eth, T["pool_eth_net_to_yoink"])),
        "captured_native": {"amount": f"{T['est_gross_all']:.3f}", "unit": "ETH", "desc": "estimated gross profit of the campaign before the builder bribes"},
        "captured_usd": None, "captured_usd_source": None,
        "coinbase_paid_eth": T["coinbase_paid_all"],
        "priority_fee_paid_eth": T["priority_fee_paid_all"],
        "builder_refund_to_bot_eth": T["builder_refunds_to_yoink"],
        "builder_payout_to_victim_eth": None,
        "bot_net_eth": T["bot_net_est"],
        "loot_note": ("coinbase payments %.3f ETH (6 pool txs: %.3f); builder 'I can haz block?' (0x229b8325) refunded %.3f ETH to Yoink's contract in 6 blocks and paid proposers %.3f ETH; net paid to the validator side %.3f ETH. "
                      "bot_net = est. gross - coinbase + refunds - gas (%.3f ETH) = %.3f ETH, vs Yoink's own message '101.8 Eth' and '~9 Eth sent to validators'. Priority fee is 0 on all 10 txs." % (
                          T["coinbase_paid_all"], T["coinbase_paid_pool_txs"], T["builder_refunds_to_yoink"], T["proposer_payments"], T["net_paid_to_validators_side"], T["gas_cost_all"], T["bot_net_est"])),
    },
    "fate": {
        "return_status": "returned",
        "returned_by_bot_eth": returned, "returned_by_builder_eth": None, "returned_total_eth": returned,
        "returned_to": f"LP {LP} (deposited the pool's 66.4 ETH + 3,997,707 vMINT), as agreed on-chain with the MintSwap team 0x8b1dcb84",
        "returned_desc": ("MintSwap's team sent an on-chain message at %s (tx %s) offering a 10%% bounty; after Yoink asked for the bug to be explained and the team did so, Yoink wrote (tx %s) 'My profit looks to have been 101.8 Eth ... roughly 9 Eth was sent to validators ... will then be returning 91.62 Eth. "
                          "Would prefer to return funds to the liquidity provider 0x5b03'; the team agreed, and Yoink's owner withdrawTo sent 91.62 ETH to 0x5b03 at block %d (%s). 91.62 = 90.0%% of 101.8 ETH; the 10%% bounty (about %.2f ETH) was kept. "
                          "The return exceeds the 66.4 ETH the LP deposited and the %.2f ETH the pool lost. The team's address 0x8b1dcb84 still wrote 'waiting for funds' 29 min after the transfer, which had gone to the LP address the team itself had approved." % (
                              "2024-04-01T22:01:59Z", NOTICE_TX[:10], OFFER_TX[:10], ret_block, ret_time, kept, pool_loss_eth)),
        "bounty_kept_eth": kept, "bounty_desc": "10% bounty offered by the MintSwap team in their on-chain message; Yoink returned 90% of its stated profit and kept the rest",
        "kept_by_bot_eth": kept,
        "returned_txs": [{"tx": RETURN_TX, "eth": returned, "block": ret_block, "time_utc": ret_time, "note": "Yoink contract withdrawTo -> LP 0x5b03 (single CALL of 91.62 ETH in the trace)"}],
        "public_statement": "On-chain only (messages in the Yoink EOA's tx inputs): 'My profit looks to have been 101.8 Eth. In addition, roughly 9 Eth was sent to validators in order to land those txs.' (tx %s)" % OFFER_TX[:10],
    },
    "raw_refs": refs,
    "rawref_gaps": [
        {"field": "trigger.first_seen_utc_ms", "why": "no confirmed trigger; candidate user tx recorded in trigger_candidate"},
        {"field": "loot.gross_loot_eth", "why": "an estimate from the bot analysis bribe rule, not a measured token flow; cross-checked against Yoink's own '101.8 Eth' statement"},
        {"field": "loot.captured_usd", "why": "not priced; the MintSwap team's own figure is ~USD 476,000 (incident.json protocol_loss_usd)"}],
    "discrepancies": [
        "yoink_more_incidents.json lists only the two txs the MintSwap team cited; Yoink's 101.8 ETH profit covers 10 txs in 6 blocks (6 call the pool, 4 touch the V2 pair), found by tracing every Yoink tx in those blocks.",
        "The MintSwap team's message sums '67.85 ETH + 4,446,673 vMINT (~$238,000 each)' - those are the ETH out of the first tx and the vMINT out of the second; the pool actually lost %.2f ETH and 3.81M vMINT." % pool_loss_eth,
        "Yoink says it sent 'roughly 9 Eth to validators'; the coinbase transfers total 110.80 ETH but the builder refunded 101.73 ETH, so the net is 9.07 ETH (proposer payments 9.20 ETH)."],
    "evidence_notes": [
        "incidents/mintswap-2024/pool_history.json: every vMINT transfer into/out of the pool and every ETH transfer (Etherscan txlist/internal/tokentx): LP deposit, 8 buys, 2 reverted buys, then Yoink's sell at 19563164 as the first sell-path call; sell_path_calls lists all 5 (3 Yoink, 2 searcher).",
        "incidents/mintswap-2024/pending_user_call_diff.json: pending user sell vs Yoink's sell call (same function 0x5c7e072b, different amount/min-out/recipient/deadline) and the deadline-minus-3600 build-time evidence.",
        "incidents/mintswap-2024/yoink_mintswap_txs.json: per-tx coinbase, bot analysis-rule gross, gas, per-block builder refund and proposer payment.",
        "Bug source: verified MintSwapPool implementation 0x13a3efac (data/raw/etherscan/source_0x13a3efac2e1feb4dddeced77a4910fcbf914ce76.json): swapExactTokensForETH computes amount0 = getAmountIn(amount1, reserve0, reserve1) where it should use getAmountOut; the team's own message (tx 0x5b90649d) names the same bug.",
        "DeFiHackLabs clone (HEAD 23c7bd83): no MintSwap entry; Yoink's contract 0x6980a47b appears only in the Paraswap, TIME, DeFiPlaza and Erc20transfer entries.",
        "Not examined: the V2-pair-side accounting (who lost the extra ~20-30 ETH Yoink's V2 legs captured); the 4 pair-only Yoink txs are included only because they reconcile Yoink's stated 101.8 ETH."],
    "incident_dir": D,
}
row["raw_refs"] = {k: v for k, v in refs.items() if v}
out = ROOT / "data" / "extract" / f"{SLUG}.json"
json.dump([row], open(out, "w"), indent=1)
print("wrote", out, "gross", T["est_gross_all"], "net", T["bot_net_est"], "kept", kept, "pool_loss", pool_loss_eth)
