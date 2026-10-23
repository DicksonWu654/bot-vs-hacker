#!/usr/bin/env python3
"""Phase-2 assembler for incidents/defiplaza-2024 and incidents/ronin-2024.

Reads only data that is already saved under data/raw (RPC, Etherscan, relay bids, mempool-dumpster) plus the race_<block>.json files
produced by scripts/blockrace.py and the local-fork replay outputs in research/defiplaza-ronin/, and writes
incident.json + timeline.json for both incidents. Nothing here fetches from the network.
"""
import datetime as dt, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/lib"))
RAW = ROOT / "data/raw"


def J(p):
    return json.load(open(ROOT / p))


def exists(p):
    return (ROOT / p).exists()


def ref(p):
    """raw ref string; fail loudly if the file is not there."""
    assert exists(p), p
    return p


def utc(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def ts(sec):
    return dt.datetime.fromtimestamp(sec, dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def ev(t_ms, kind, actor, detail, tx=None, raw=None, precision="ms", **extra):
    e = {"t_utc_ms": t_ms, "utc": utc(t_ms) if precision == "ms" else (ts(t_ms // 1000)[:10] if precision == "day" else ts(t_ms // 1000)), "precision": precision, "kind": kind, "actor": actor,
         "detail": detail}
    if tx:
        e["tx"] = tx
    if raw:
        e["raw_ref"] = raw
    e.update(extra)
    return e


def blk_ts(n):
    import rawfetch as rf
    return int(rf.rpc("eth_getBlockByNumber", [hex(n), False], key=f"blk_{n}")["timestamp"], 16)


def auction(race_path, winner_pubkeys=(), note=None):
    d = J(race_path)
    bs = d["bid_summary"]
    rs = d["relays_status"]
    answered = {k: {"delivered_n": v.get("delivered_n"), "bids_n": v.get("bids_n")} for k, v in rs.items() if v.get("delivered_http") == 200 or v.get("bids_http") == 200}
    bids = sorted(d["bids"], key=lambda b: b["timestamp_ms"])
    w = d["winner"]
    # runner-up = highest bid from a builder pubkey other than the winner's pubkey
    wp = {w.get("builder_pubkey")} | set(winner_pubkeys)
    wname = w.get("builder_name")
    others = [b for b in bids if b["builder_pubkey"] not in wp and not (wname and b["builder_name"] == wname)]
    ru = max(others, key=lambda b: int(b["value_wei"])) if (others and w.get("builder_pubkey")) else None
    out = {
        "race_file": race_path,
        "slot": d["slot"] if "slot" in d else None,
        "relays_answered": answered,
        "relays_unavailable": sorted(k for k, v in rs.items() if k not in answered),
        "n_bids_flashbots_relay": bs["n_bids"], "n_builders": bs["n_builders"],
        "first_bid_t_rel_slot_ms": bs["first_bid_t_rel_slot_ms"], "last_bid_t_rel_slot_ms": bs["last_bid_t_rel_slot_ms"],
        "max_bid_eth": bs["max_bid_eth"],
        "winner": {k: w.get(k) for k in ("builder_name", "builder_pubkey", "bid_value_eth", "delivered_by_relays", "proposer_fee_recipient")},
        "proposer_payment_tx": w.get("proposer_payment_tx"),
        "runner_up": None if not ru else {"builder_name": ru["builder_name"], "builder_pubkey": ru["builder_pubkey"], "value_eth": float(ru["value_eth"]),
                                           "t_rel_slot_ms": ru["t_rel_slot_ms"], "block_hash": ru["block_hash"], "num_tx": ru["num_tx"]},
        "note": note or ("runner_up = highest bid of any other builder name in the Flashbots-relay record; it can exceed the delivered bid when it arrived too late / was never requested" if ru else "winner not identifiable from the queried relays; runner_up omitted"),
    }
    return out, d


# ----------------------------------------------------------------------------------------------------------------------------------
# DeFi Plaza
# ----------------------------------------------------------------------------------------------------------------------------------
def defiplaza():
    slug = "defiplaza-2024"
    inc = ROOT / "incidents" / slug
    race, d = auction("incidents/defiplaza-2024/race_20240539.json")
    ymp = J("research/defiplaza-ronin/defiplaza_fork_replay.json")
    flows = J("research/defiplaza-ronin/defiplaza_plaza_net_flows.json")
    mp = J("incidents/defiplaza-2024/race_20240539.json")["mempool"]["txs"]

    YOINK_TX = "0xa245deda8553c6e4c575baff9b50ef35abf4c8f990f8f36897696f896f240e3a"
    ATK_DEPLOY = "0x8f029510dbcc4885d5f5242f3583f4d31f9134d9eddaa30a1afa353f6bd4f7b0"
    ATK_RUN = "0xe00b0998d71b0e657379be196babd1637a653c100e8162853ca6616c3970790d"
    COPY_DEPLOY = "0xbb5dffb00d103d5b9ef3a29eb01c166cd766265fe251e0bd89863d7f2d96ff2a"
    REFUND = "0x2fc1684935de" # prefix, full hash looked up below
    txs = {t["hash"]: t for t in d["txs"]}
    refund_tx = next(t for t in d["txs"] if t["hash"].startswith("0x2fc1684935de"))
    prop_tx = next(t for t in d["txs"] if t["hash"].startswith("0x454219fb25d3"))
    yoink2 = next(t for t in d["txs"] if t["hash"].startswith("0x69b0f8b91914"))

    # mempool per-source first seen (dumpster 2024-07-05)
    mpd = ROOT / "data/raw/mempool-dumpster"
    import duckdb
    con = duckdb.connect()
    slog = {}
    hs = [ATK_DEPLOY, ATK_RUN, COPY_DEPLOY, "0xc1509590b77dc5d3f68b8e61886017e57bbea64e1d725808b8899b893f25c2e6",
          "0x9b840783793438e5c0395dcf5d59e7f273bde8fc8bac64c4f7a4844c11d18275", YOINK_TX]
    inl = ",".join("'" + h + "'" for h in hs)
    for h, t, s in con.execute(f"SELECT hash,timestamp_ms,source FROM read_csv('{ROOT}/data/cache/mempool-dumpster/2024-07-05_sourcelog.csv',header=true,all_varchar=true) WHERE hash IN ({inl}) ORDER BY CAST(timestamp_ms AS BIGINT)").fetchall():
        slog.setdefault(h, []).append({"source": s, "first_seen_ms": int(t)})
    FS_ATK = slog[ATK_DEPLOY][0]["first_seen_ms"]            # 1720185329185
    FS_COPY = slog[COPY_DEPLOY][0]["first_seen_ms"]          # 1720185327984
    assert FS_ATK == 1720185329185 and FS_COPY == 1720185327984
    assert YOINK_TX not in slog  # Yoink's tx never appears in the public mempool

    slot_start_ms = 1720185335000
    bids = sorted(d["bids"], key=lambda b: b["timestamp_ms"])
    yb = [b for b in bids if (b["builder_name"] or "").startswith("I can haz")]
    yoink_first = yb[0]
    flashbots_big = [b for b in bids if b["builder_name"] == "Flashbots" and float(b["value_eth"]) > 50]
    b69 = [b for b in bids if b["builder_name"] == "builder0x69" and float(b["value_eth"]) > 10]

    race["auction_story"] = {
        "attacker_txs_first_seen_ms": FS_ATK, "attacker_first_seen_rel_slot_ms": FS_ATK - slot_start_ms,
        "yoink_builder_first_bid_ms": yoink_first["timestamp_ms"], "yoink_first_bid_delay_after_first_seen_ms": yoink_first["timestamp_ms"] - FS_ATK,
        "yoink_builder_first_bid_eth": float(yoink_first["value_eth"]), "yoink_builder_first_bid_num_tx": yoink_first["num_tx"],
        "yoink_bid_ladder_eth": [round(float(b["value_eth"]), 4) for b in yb], "yoink_bid_ladder_t_rel_slot_ms": [b["t_rel_slot_ms"] for b in yb],
        "winning_bid_eth": race["winner"]["bid_value_eth"], "winning_bid_t_rel_slot_ms": next(b["t_rel_slot_ms"] for b in bids if b["is_winning_block"]),
        "other_builders_jump_to_60eth": [{"t_rel_slot_ms": b["t_rel_slot_ms"], "builder": b["builder_name"], "eth": round(float(b["value_eth"]), 4),
                                          "num_tx": b["num_tx"], "gas_used": b["gas_used"], "block_hash": b["block_hash"]} for b in flashbots_big],
        "builder0x69_bids_over_10eth": [{"t_rel_slot_ms": b["t_rel_slot_ms"], "eth": round(float(b["value_eth"]), 4), "num_tx": b["num_tx"],
                                         "block_hash": b["block_hash"]} for b in b69],
        "winner_margin_eth_over_best_other_builder": round(race["winner"]["bid_value_eth"] - max(float(b["value_eth"]) for b in flashbots_big), 4),
        "winning_block_contains_yoink_tx": True,
        "winning_block_contains_attacker_run_tx": False, "winning_block_contains_attacker_deploy_tx": True,
        "losing bids' contents": "unknown (relays publish hash/num_tx/gas_used/value only). Between 13:15:32.739 and .821 three Flashbots-builder pubkeys (0xa03a000b, 0xa02a0054, 0xa01a0047) jumped from 6.36 ETH to 60.26-62.49 ETH, including a 3-tx 62.4326 ETH block: some bundle paying ~the whole profit reached the Flashbots builders. Whether it is a rival searcher or Yoink's own bundle also sent to Flashbots is NOT determinable from public data (unknown)",
    }

    builder_in = sum(int(t["builder_revenue_wei"] or 0) for t in d["txs"]) / 1e18
    race["builder_accounting"] = {
        "builder_fee_recipient": "0x229b8325bb9ac04602898b7e8989998710235d5f", "builder_extra_data": "I can haz block?",
        "revenue_from_block_eth": round(builder_in, 9), "of_which_yoink_tx0_coinbase": 66.3180915, "of_which_yoink_tx11_coinbase": round(int(yoink2["coinbase_transfer_wei"]) / 1e18, 9),
        "refund_to_bot_eth": int(refund_tx["value_wei"]) / 1e18, "refund_tx": refund_tx["hash"], "refund_tx_index": refund_tx["index"],
        "proposer_payment_eth": int(prop_tx["value_wei"]) / 1e18, "proposer_payment_tx": prop_tx["hash"], "proposer_payment_index": prop_tx["index"],
        "proposer_fee_recipient": prop_tx["to"], "proposer_fee_recipient_note": "0x388C818C... is the Lido Execution Layer Rewards Vault per the DeFi Plaza post on research.lido.fi",
        "builder_net_after_payouts_eth": round(builder_in - (int(refund_tx["value_wei"]) + int(prop_tx["value_wei"])) / 1e18, 6),
    }

    vault_returns = [
        {"what": "USDT swept to vault 0xc70f00cd then sold (Universal Router)", "tx": "0xd7ceb45c4205312a557ac05844d92e302d2e03652a62ee236ac7ae116880159c", "amount": "13,504.300602 USDT -> 4.519460 ETH", "to": "vault EOA 0xc70f00cd7e461686b04b0e912e309beca8b80ea0 (ETH kept)", "utc": ts(1720208147)},
        {"what": "WBTC swept to vault then sold", "tx": "0x8db1e512b06b38cae784cd68646a538f6c383056387d56f3cb89f12710c22111", "amount": "0.24367467 WBTC -> 4.612157 ETH", "to": "vault (ETH kept)", "utc": ts(1720208231)},
        {"what": "USDC swept to vault then sold (12,808.734214 of 13,409.070847)", "tx": "0x50001c27ca5f4a5a89ad85cd48b240e7cfa4fd9be1a012139fb239ca79659c31", "amount": "12,808.734214 USDC -> 4.286220 ETH", "to": "vault (ETH kept)", "utc": ts(1720208375)},
        {"what": "RETURN to DeFi Plaza deployer 0x0422afb5481a21b3fea2c94e08dfad45da1975b7", "tx": "0xb1ddf7e262ceec136f39dcc36509e0203b1536938a6f3c5ae1a26bd0aeba39f0", "amount": "600.336633 USDC", "to": "0x0422afb5481a21b3fea2c94e08dfad45da1975b7", "utc": ts(1720208543)},
        {"what": "RETURN", "tx": "0xd52bc63c573ad8395635e5616576a1f111073e2c232b4ead0cbfb155aaede382", "amount": "13,413.796570 DAI", "to": "0x0422afb5481a21b3fea2c94e08dfad45da1975b7", "utc": ts(1720208663)},
        {"what": "RETURN", "tx": "0xfab945a043d69dcc9c13a39a0ac06b69baed071f205942ea04d7100d172e6c7b", "amount": "257,253.140376 DFP2", "to": "0x0422afb5481a21b3fea2c94e08dfad45da1975b7", "utc": ts(1720208759)},
        {"what": "RETURN", "tx": "0x140d107887461556deaa0839875a8417b5e8abcff9a12e37fd647ea95ee9f533", "amount": "121,266.679431 eXRD", "to": "0x0422afb5481a21b3fea2c94e08dfad45da1975b7", "utc": ts(1720208855)},
    ]
    funds_fate = [
        {"what": "fixed bribe (coinbase.transfer) from Yoink tx to builder fee recipient", "tx": YOINK_TX, "amount": "66.3180915 ETH (msg.value 663180915 x 1e11)", "to": "0x229b8325bb9ac04602898b7e8989998710235d5f ('I can haz block?')"},
        {"what": "builder pays proposer (= winning bid)", "tx": prop_tx["hash"], "amount": "62.540934666 ETH", "to": "0x388c818ca8b9251b393131c08a736a67ccb19297 (Lido Execution Layer Rewards Vault, per Lido forum post)"},
        {"what": "builder refund to Yoink bot contract (block position 12)", "tx": refund_tx["hash"], "amount": "4.761056907 ETH", "to": "0x6980a47bee930a4584b09ee79ebe46484fbdbdd0"},
        {"what": "sweep to Yoink vault in the incident tx", "tx": YOINK_TX, "amount": "13,504.30 USDT, 0.24367467 WBTC, 13,409.07 USDC, 13,413.80 DAI, 257,253.14 DFP2, 121,266.68 eXRD", "to": "0xc70f00cd7e461686b04b0e912e309beca8b80ea0"},
    ] + vault_returns + [
        {"what": "message from DeFi Plaza deployer to Yoink owner EOA (on-chain input data)", "tx": "0x1e34998e96183aa6c0e3eae0dc242008e5ce8d19ee4f5b48d169297d42981f60", "amount": "0 ETH, 762 hex chars of text", "to": "0xfde0d1575ed8e06fbf36256bcdfa1f359281455a", "utc": ts(1720206023)},
        {"what": "NOT FOUND on chain: any ETH return. DeFi Plaza says (research.lido.fi, 2024-08-31) the front-runner 'promptly returned their profits'; observed returns are the 4 token transfers above (about $22.8K at 2024-07-05 prices) while ~13.42 ETH from the sold tokens and the 4.76 ETH builder refund stayed with Yoink's addresses", "tx": None, "amount": "-", "to": "-"},
    ]

    inc_json = {
        "slug": slug, "name": "DeFi Plaza (DefiPlaza V2 DEX, Ethereum)", "date": "2024-07-05", "chain": "ethereum",
        "verdict": "confirmed-onchain",
        "verdict_reason": ("The real attacker is EOA 0x14b362d2... (attack contract 0xa4e8969b..., deployed in tx 0x8f029510... at 13:15:29.185 UTC first-seen together with its run() tx 0xe00b0998...). "
                           "Yoink's tx 0xa245deda... sits at position 0 of block 20240539 and drains the same pool with 25 DeFi Plaza state-changing calls whose calldata and ETH values are byte-identical to what the "
                           "attacker's own contract issues when its deploy+run() are replayed on a local fork of block 20240538; the attacker's deploy landed at position 3 of the same block, but its run() tx never made it into block 20240539 "
                           "and landed one block later (20240540, position 27) reverting on an empty pool. Ordering evidence: attacker txs seen in the public mempool 5.8 s before the slot and 3.0 s before Yoink's builder's first bid; Yoink's own tx never appears in the public mempool."),
        "era": "post-Merge, mempool-dumpster sourcelog + Flashbots relay bids available (other relays: delivered-payload only)",
        "protocol_loss_usd": None,
        "attacker": {
            "eoas": ["0x14b362d2e38250604f21a334d71c13e2ed478467"],
            "possible_second_eoa": {"eoa": "0x907f85291cb5d5ac5a76bb90ef8b62f2ddf69591",
                                    "evidence": "tx 0xbb5dffb0... deployed byte-identical initcode (26,794 hex chars, same 0x5f805460 wrapper selector) with nonce 0, first seen 1,201 ms BEFORE the attacker's own deploy; funded 0.1 ETH at 13:08:11 (tx 0x795f04e8345e...); only ever deployed (contract 0xd2a63475e4207f286f45586ae8d2200f4e64e41b never called). Relationship to 0x14b362d2 is unproven (label: inferred, same tooling)."},
            "contracts": ["0xa4e8969bba1e1d48c30c948de0884cdff43e2d54"],
            "deploy_tx": ATK_DEPLOY,
            "funding_tx": {"tx": "0x4c27e806ded2db44ae20aeb55aab332f427366bbcffefbb31e4016851ada1e1c", "block": 19161592, "utc": "2024-02-05T10:50:59Z", "amount_eth": 0.9856861958564,
                           "source": "0x47ce0c6ed5b0ce3d3a51fdb1c52dc66a7c3c2936 (Tornado Cash 1 ETH pool, address matches the published pool list; second 0.98729 ETH at tx 0xef98b5256c9dced844cfed17774b3bd14ec9428fc4c09fd1e0a7e42f8a63de8d)"},
            "history": "EOA active since 2024-04-05 with many failed 'attack()/pullTokens()/execute()' contract attempts (Etherscan txlist) - a serial exploit hunter, not a one-off",
            "txs": [
                {"hash": ATK_DEPLOY, "block": 20240539, "index": 3, "status": 1, "nonce": 12, "first_seen_ms": FS_ATK, "first_seen_utc": utc(FS_ATK), "priority_fee_gwei": 9.32, "role": "deploy attack contract (13,396-byte initcode)"},
                {"hash": ATK_RUN, "block": 20240540, "index": 27, "status": 0, "nonce": 13, "first_seen_ms": FS_ATK, "first_seen_utc": utc(FS_ATK), "priority_fee_gwei": 8.94, "role": "run() - 'execution reverted' on the drained pool; fork replay shows it succeeds on the pre-Yoink state"},
                {"hash": "0xc1509590b77dc5d3f68b8e61886017e57bbea64e1d725808b8899b893f25c2e6", "block": None, "status": "never mined", "nonce": 12, "first_seen_ms": 1720185329789, "role": "lower-fee version of the deploy (seen 604 ms after the original)"},
                {"hash": "0x9b840783793438e5c0395dcf5d59e7f273bde8fc8bac64c4f7a4844c11d18275", "block": None, "status": "never mined", "nonce": 13, "first_seen_ms": 1720185329789, "role": "lower-fee version of run()"},
            ],
        },
        "bots": [{
            "label": "Yoink", "eoa": "0xfde0d1575ed8e06fbf36256bcdfa1f359281455a", "contract": "0x6980a47bee930a4584b09ee79ebe46484fbdbdd0",
            "vault": "0xc70f00cd7e461686b04b0e912e309beca8b80ea0 (an EOA: it signs the swap/transfer txs)",
            "txs": [{"hash": YOINK_TX, "block": 20240539, "index": 0, "status": 1, "msg_value": 663180915, "gas_used": 7878567, "in_public_mempool": False},
                    {"hash": yoink2["hash"], "block": 20240539, "index": 11, "status": 1, "msg_value": 996, "note": "second Yoink tx in the block (coinbase 0.9463 ETH); not analysed for this incident"}],
            "captured": {"token": "6 assets swept to vault + ETH (profit split not decomposed)",
                         "amount": "13,504.30 USDT, 0.24367467 WBTC, 13,409.07 USDC, 13,413.80 DAI, 257,253.14 DFP2, 121,266.68 eXRD swept; fixed bribe 66.3181 ETH paid out of the ETH proceeds",
                         "usd": round(13504.30 * 1.001 + 0.24367467 * 55257 + 13409.07 * 1.001 + 13413.80 + 257253.14 * 0.02060411 + 121266.68 * 0.02781973), "usd_note": "value of the 6 swept assets only (DefiLlama 2024-07-05 13:15), excluding the ETH proceeds the 66.3181 ETH bribe was paid from"},
            "coinbase_paid_eth": 66.3180915, "priority_fee_gwei": 0.0,
            "replay_evidence": {
                "method": "local anvil fork at block 20240538; attacker's deploy tx input + run() tx input replayed from the attacker EOA (impersonated); DeFi Plaza ('0xe68c1d72...') calls extracted with callTracer from both runs",
                "attacker_run_on_fork": {"status": ymp["run"]["status"], "plaza_eth_after": ymp["plaza_eth_after"], "plaza_eth_before": ymp["plaza_balances_before"]["eth"],
                                         "calls_to_plaza": len(ymp["attacker_calls_to_plaza"])},
                "yoink_calls_to_plaza": len(ymp["yoink_calls_to_plaza"]),
                "diff": "after dropping one STATICCALL balanceOf(0x70a08231) that only the attacker's contract makes, the two call lists match 25/25: same selectors (23 x 0xfe029156, 1 x 0xce359797 with 32,732.54 ETH, 1 x 0xc4ccdeea), same calldata bytes, same ETH values; only msg.sender differs (attacker contract 0xa4e8969b -> Yoink bot 0x6980a47b). Funding differs: Yoink wraps it in a Balancer flashLoan (9 tokens) and an Aave V3 flashLoan; sweeps proceeds to its vault.",
                "files": ["research/defiplaza-ronin/defiplaza_fork_replay.json", "research/defiplaza-ronin/defiplaza_plaza_calls.json", "scripts/bot_re/defiplaza_replay.py"],
                "yoink_script_decode": "research/bot-re/incident_txs.json['defiplaza']: 19 approvals, Balancer flashLoan, 12 swap ops, unwrap, 6 sweeps; bribe rule msg.value>=1000 -> fixed v*1e11 wei (analysis.md section 3 and 4.3)",
            },
            "notes": "No Yoink tx hash is in the public mempool (0 rows in dumpster csv + sourcelog): the bot reacted to the attacker's pending txs, built its block through its own builder, and was delivered via Flashbots + Ultra Sound relays.",
        }],
        "other_racers": [
            {"label": "unresolved: whoever sent the bundle behind the Flashbots-builder 60.26-62.49 ETH bids", "evidence": "relays hide bid contents. At 13:15:32.739-.821 three Flashbots-builder pubkeys jumped from 6.36 ETH to 60.26-62.49 ETH including a 3-tx, 11.09M-gas 62.4326 ETH block. A rival copier OR Yoink's own bundle also routed to Flashbots builders both fit; it lost by 0.0481 ETH to Yoink's final 62.5409 ETH (best 62.4928).", "unknown": True},
            {"label": "builder0x69", "evidence": "13:15:32.527 18.1124 ETH, 111 tx, block 0xbf839e76...; contents unknown (inferred a competing copier or an unrelated arb-heavy block)"},
            {"label": "0x907f8529... deploy of identical initcode", "tx": COPY_DEPLOY, "block": 20240540, "index": 219, "first_seen_ms": FS_COPY},
        ],
        "funds_fate": funds_fate,
        "auction": {**{k: v for k, v in race.items() if k not in ("auction_story", "builder_accounting")}, "story": race["auction_story"], "builder_accounting": race["builder_accounting"]},
        "sources": [
            "https://research.lido.fi/t/defiplaza-exploit-request-for-comment/8241",
            "https://defiplaza.net/blog/post-mortem-of-defiplaza-ethereum-exploit/ (HTTP 404 on 2024-10-21; a mirror was reachable only via search summary)",
            "https://fairyproof.substack.com/p/weekly-blockchain-security-watch-78c",
            "research/bot-re/analysis.md", "research/bot-re/incident_txs.json",
        ],
        "raw_refs": {
            "yoink_trace": ref(f"data/raw/rpc/trace_{YOINK_TX}.json"), "yoink_receipt": ref(f"data/raw/rpc/rcpt_{YOINK_TX}.json"),
            "attacker_deploy_tx": ref(f"data/raw/rpc/tx_{ATK_DEPLOY}.json"), "attacker_run_tx": ref(f"data/raw/rpc/tx_{ATK_RUN}.json"),
            "attacker_run_trace": ref(f"data/raw/rpc/trace_{ATK_RUN}.json"),
            "attacker_txlist": ref("data/raw/etherscan/p2_atk_txlist.json"), "attacker_internal": ref("data/raw/etherscan/p2_atk_txlistinternal.json"),
            "mempool_csv": ref("data/raw/mempool-dumpster/2024-07-05.csv.zip"), "mempool_sourcelog": ref("data/raw/mempool-dumpster/2024-07-05_sourcelog.csv.zip"),
            "race_blocks": ["incidents/defiplaza-2024/race_20240539.json", "incidents/defiplaza-2024/race_20240540.json"],
            "relay_bids_flashbots": ref("data/raw/relay-flashbots/bids_block20240539.json"), "relay_delivered_flashbots": ref("data/raw/relay-flashbots/delivered_block20240539.json"),
            "vault_txlist": ref("data/raw/etherscan/p2_vault_txlist_20240539_20400000.json"), "vault_tokentx": ref("data/raw/etherscan/p2_vault_tokentx_20240539_20400000.json"),
            "bot_txlist": ref("data/raw/etherscan/p2_bot_txlist_20240539_20400000.json"),
            "deployer_0422_tokentx": ref("data/raw/etherscan/p2_0422_tokentx.json"), "deployer_0422_txlist": ref("data/raw/etherscan/p2_0422_txlist.json"),
            "second_eoa_txlist": ref("data/raw/etherscan/p2_907f_txlist.json"),
            "pool_net_flows": "research/defiplaza-ronin/defiplaza_plaza_net_flows.json", "prices": ref("data/raw/defillama/p2_defiplaza_prices_1720185335.json"),
            "lido_thread": ref("data/raw/web-p2/lido_defiplaza_rfc.json"), "fairyproof": ref("data/raw/web-p2/fairyproof_78c.html"),
            "fork_replay": "research/defiplaza-ronin/defiplaza_fork_replay.json",
        },
    }
    # protocol loss: net token USD + net ETH, both from the saved Yoink-tx logs/trace, priced with DefiLlama at the block time
    # (plaza_net_token_usd and eth_net_to_plaza are negative when value left the pool)
    loss = -flows["plaza_net_token_usd"] + (-flows["eth_net_to_plaza"]) * flows["eth_price"]
    inc_json["protocol_loss_usd"] = round(loss, 0)
    inc_json["protocol_loss_basis"] = "net outflow of 15 ERC-20s (16 assets with ETH) from pool 0xe68c1d72... in the Yoink tx, DefiLlama prices at 13:15:35 UTC; DeFi Plaza and Fairyproof say 'all funds' / ~$200K"
    json.dump(inc_json, open(inc / "incident.json", "w"), indent=1)

    # ------------------------------ timeline ------------------------------
    T = []
    T.append(ev(1707130259000, "fund", "attacker 0x14b362d2", "0.9857 ETH from Tornado Cash 1 ETH pool (internal tx; block 19161592); second 0.9873 ETH at 10:57:59", tx="0x4c27e806ded2db44ae20aeb55aab332f427366bbcffefbb31e4016851ada1e1c", raw="data/raw/etherscan/p2_atk_txlistinternal.json", precision="s"))
    T.append(ev(1720184891000, "fund", "unknown -> 0x907f8529 (possible second attacker EOA)", "0.1 ETH from 0x077d360f11... at 13:08:11 (block 20240502)", tx="0x795f04e8345e", raw="data/raw/etherscan/p2_907f_txlist.json", precision="s"))
    T.append(ev(FS_COPY, "mempool_seen", "0x907f8529", "contract-creation tx with byte-identical initcode to the attacker's deploy, nonce 0, tip 1 gwei (lands at idx 219 of block 20240540)", tx=COPY_DEPLOY, raw="data/raw/mempool-dumpster/2024-07-05_sourcelog.csv.zip", per_source=slog[COPY_DEPLOY]))
    T.append(ev(FS_ATK, "mempool_seen", "attacker 0x14b362d2", "deploy of attack contract (nonce 12, tip 9.32 gwei) first seen by 4 of 4 dumpster sources: local/bloxroute .185, chainbound .189, mempoolguru 30.030", tx=ATK_DEPLOY, raw="data/raw/mempool-dumpster/2024-07-05_sourcelog.csv.zip", per_source=slog[ATK_DEPLOY]))
    T.append(ev(FS_ATK, "mempool_seen", "attacker 0x14b362d2", "run() on 0xa4e8969b (nonce 13, tip 8.94 gwei) first seen in the same millisecond as the deploy; sent as a pair", tx=ATK_RUN, raw="data/raw/mempool-dumpster/2024-07-05_sourcelog.csv.zip", per_source=slog[ATK_RUN]))
    T.append(ev(1720185329789, "mempool_seen", "attacker 0x14b362d2", "two lower-fee versions of nonce 12 and 13 (never mined) seen 604 ms later", tx="0xc1509590b77dc5d3f68b8e61886017e57bbea64e1d725808b8899b893f25c2e6 / 0x9b840783793438e5c0395dcf5d59e7f273bde8fc8bac64c4f7a4844c11d18275", raw="data/raw/mempool-dumpster/2024-07-05_sourcelog.csv.zip"))
    T.append(ev(slot_start_ms - 9901, "bid", "blocksmith.org", "first Flashbots-relay bid for slot 9446776 (0.0052 ETH); 73 bids from 9 builders in total", raw="data/raw/relay-flashbots/bids_block20240539.json"))
    pre = [b for b in bids if b["timestamp_ms"] < FS_ATK and float(b["value_eth"]) > 4.5][-1]
    T.append(ev(pre["timestamp_ms"], "bid", pre["builder_name"], f"last >4.5 ETH bid before the attacker txs appear: {float(pre['value_eth']):.4f} ETH, {pre['num_tx']} tx (ordinary block, no incident content)", raw="data/raw/relay-flashbots/bids_block20240539.json"))
    for b in bids:
        v = float(b["value_eth"])
        n = b["builder_name"] or b["builder_pubkey"][:10]
        if b["timestamp_ms"] > FS_ATK and (n.startswith("I can haz") or v > 18 or (n == "Flashbots" and v > 6.3) or b["is_winning_block"]):
            T.append(ev(b["timestamp_ms"], "bid", n, f"{v:.4f} ETH, {b['num_tx']} tx, gas {b['gas_used']}, block {b['block_hash'][:12]}" + (" (WINNING block hash, delivered by Flashbots + Ultra Sound)" if b["is_winning_block"] else "") + (" [pubkey " + b["builder_pubkey"][:10] + "]"),
                        raw="data/raw/relay-flashbots/bids_block20240539.json", t_rel_slot_ms=b["t_rel_slot_ms"], block_hash=b["block_hash"], is_winning=b["is_winning_block"]))
    T.append(ev(slot_start_ms, "block", "proposer (Lido-linked fee recipient)", "block 20240539 timestamp (slot 9446776): pos 0 Yoink 0xa245deda (66.318 ETH coinbase), pos 3 attacker deploy, pos 11 second Yoink tx, pos 12 builder refund 4.761 ETH to bot, pos 13 builder -> proposer 62.5409 ETH", tx=YOINK_TX, raw="data/raw/rpc/block_20240539.json"))
    T.append(ev(slot_start_ms, "tx", "Yoink 0xfde0d157 -> 0x6980a47b", "pos 0: Balancer flashLoan + Aave flashLoan, 25 calls to DeFi Plaza 0xe68c1d72, coinbase.transfer 66.3180915 ETH, sweep to vault", tx=YOINK_TX, raw=f"data/raw/rpc/trace_{YOINK_TX}.json", precision="block"))
    T.append(ev(slot_start_ms, "tx", "attacker 0x14b362d2", "pos 3: deploy of attack contract 0xa4e8969b lands (status 1)", tx=ATK_DEPLOY, raw="incidents/defiplaza-2024/race_20240539.json", precision="block"))
    T.append(ev(slot_start_ms, "tx", "builder 0x229b8325", "pos 12: refund 4.761056907 ETH to Yoink bot", tx=refund_tx["hash"], raw="incidents/defiplaza-2024/race_20240539.json", precision="block"))
    T.append(ev(slot_start_ms, "tx", "builder 0x229b8325", "pos 13: proposer payment 62.540934666 ETH to 0x388C818C (Lido Execution Layer Rewards Vault)", tx=prop_tx["hash"], raw="incidents/defiplaza-2024/race_20240539.json", precision="block"))
    T.append(ev(1720185347000, "tx", "attacker 0x14b362d2", "block 20240540 pos 27: run() lands one block later and reverts (nothing left to drain); fork replay shows it would have succeeded on the pre-Yoink state", tx=ATK_RUN, raw="incidents/defiplaza-2024/race_20240540.json", precision="block"))
    T.append(ev(1720206023000, "message", "DeFi Plaza deployer 0x0422afb5 -> Yoink owner 0xfde0d157", "on-chain text: 'The DefiPlaza exchange was exploited in transaction 0xa245deda... but the attacker was front run by your MEV bot. We're looking to discuss return of stolen funds ... in return for a bounty ... via BlockScan chat'", tx="0x1e34998e96183aa6c0e3eae0dc242008e5ce8d19ee4f5b48d169297d42981f60", raw="data/raw/etherscan/p2_0422_txlist.json", precision="s"))
    for r in vault_returns:
        T.append(ev(int(dt.datetime.strptime(r["utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.UTC).timestamp() * 1000), "return" if r["what"].startswith("RETURN") else "tx", "Yoink vault 0xc70f00cd", f"{r['what']}: {r['amount']}", tx=r["tx"], raw="data/raw/etherscan/p2_vault_tokentx_20240539_20400000.json", precision="s"))
    T.append(ev(1725103080000, "message", "DeFi Plaza team", "Lido forum RFC posted (2024-08-31 ~11:18 local forum time): 'The attacker was front-run, leading to ... 62.5 ETH ending up with the Lido Execution Rewards Vault'; 'We have contacted the front runner and they promptly returned their profits'", raw="data/raw/web-p2/lido_defiplaza_rfc.json", precision="day"))
    T.sort(key=lambda e: e["t_utc_ms"])
    json.dump({"slug": slug, "note": "block-level events share the slot-start timestamp; 'precision': ms (mempool/relay clocks), s (block time), block, day", "events": T}, open(inc / "timeline.json", "w"), indent=1)
    return inc_json


# ----------------------------------------------------------------------------------------------------------------------------------
# Ronin
# ----------------------------------------------------------------------------------------------------------------------------------
def ronin():
    slug = "ronin-2024"
    inc = ROOT / "incidents" / slug
    R = {b: auction(f"incidents/ronin-2024/race_{b}.json")[0] for b in (20468679, 20468790, 20468848, 20468849)}
    RD = {b: J(f"incidents/ronin-2024/race_{b}.json") for b in (20468438, 20468679, 20468790, 20468848, 20468849)}
    mp = J("research/defiplaza-ronin/ronin_mempool_lookup.json")["txs"]
    diff = J("research/defiplaza-ronin/ronin_copies_diff.json")
    BR = "0x64192819ac13ef72bf6b5ae239ac672b43a9af08"
    # ---- hashes
    UPG = "0x855dd3b1194e3b889f4667b6a0996220e350e034d35d3eab29b4f23bc205767e"
    PAUSE = "0x90a1a9011dc2c246631da893f5f9f17ea4e27dbd9a334052a1d53359dfe090c9"
    ETH_COPY = "0x2619570088683e6cc3a38d93c3d98899e5783864e15525d5f5810c11189ba6cb"
    ETH_VICT = "0xc78fb8cd5f7813a3d8abebdc5351aafd5011e8e13c5f6740837eeef9308d1faf"
    R3_COPY = "0x77bb83dd9b25a0af12c0092993ddf1a2f54b77fbcd1dbf1bf33a965ec707268b"
    R3_VICT = "0x56439cf9427a9188d12b35ef4c8b80fc94a8a1dd205789999c000d8035f27afe"
    R3_PAY = "0x72a4daca1f06caf585f45482bbef2a97701525b59ea96f06494796f00b084ea6"
    Y_COPY = "0xbce5b8548db486c561948e8a177c8ccaa72810f972cee3909ea50af015a60ad8"
    Y_VICT = "0xb7c3f85abd0b9ede7b64868eeb6778ea4731adb1d49f8640b7e7234e470e96c1"
    Y_REFUND = "0x43354f3f541e2df3d600b54670fd8e38f28f0850f517b53e5b7d222c34c89bb2"
    Y_PROP = "0xc5eaed361ca3b40863477d1a33b55f630bad5e69ff7364706aa4ade19c35f961"
    ETH_PROP = "0x65c9d305a6152cfe3d64b4c41ec8961f8b28773fd8557e6ef41ba6d5187e75f3"
    R3_PROP = "0x8306cb9b9ed89788b73f54855eb18a00f5daa60e2512be16d4bc4a358144b5d3"
    ETH_RET1 = "0x017e91606e015b441c1fa8b82929d685b99637896ebf96a81c323a32abe8974c"
    ETH_RET2 = "0xacd5202dd0b372bc76a1659524e3899ec4efa4782e98718fd9593b1077be9953"
    Y_WD = "0x8369cdc42b86ea9bbff28eec3d24d4a05bcd3273f5c69c7c76e7dc0858952ff8"
    Y_SAFE = "0x21df45bd48f17cb97f1f2b7f12e298da6ecb418ceedb69c345c934ecaca48d9c"
    E_SAFE1 = "0xf0e1fc14223f7ce20cbcf87c77da8d9ad7ae8b54c409a8270ef6db7ec7bdd272"
    E_SAFE2 = "0xf8f097982bc0f9a8f4279d4132dc91cfe17ab2d4fc70e7f740bc3ed752165601"
    MSG_Y = "0x8d3b20fb3fd22b44c7719a03a6fa33487718db33b258191da3d27a3d9ca1070c"
    MSG_E = "0x945a71565b8d09ba4681c9d77bab4b105eb668d98c86961d277552b166f0f7f7"
    MSG_R3 = "0x9a52f1d44f269abc548b523f58688eb1ae6367cd8adc1f633e65d274caacdf4b"
    tx = {b: {t["hash"]: t for t in RD[b]["txs"]} for b in RD}
    sl = lambda b: (blk_ts(b) or 0)
    fs = lambda h: mp[h]["first_seen_ms"] if mp.get(h) else None
    fs_src = lambda h: mp[h]["per_source_first_seen"] if mp.get(h) else None

    # bids
    def bids_of(b):
        return sorted(RD[b]["bids"], key=lambda x: x["timestamp_ms"])

    yb = [x for x in bids_of(20468848) if (x["builder_name"] or "").startswith("I can haz")]
    nm = lambda x: x["builder_name"] or x["builder_pubkey"][:10]
    y_first = yb[0]
    FS_Y = fs(Y_VICT)

    # block 20468848 accounting
    t848 = RD[20468848]["txs"]
    bot_cb = sum(int(t["coinbase_transfer_wei"] or 0) for t in t848 if t["from"] == "0xfde0d1575ed8e06fbf36256bcdfa1f359281455a") / 1e18
    n_bot = sum(1 for t in t848 if t["from"] == "0xfde0d1575ed8e06fbf36256bcdfa1f359281455a")
    refund = int(tx[20468848][Y_REFUND]["value_wei"]) / 1e18
    prop = int(tx[20468848][Y_PROP]["value_wei"]) / 1e18

    auction_blocks = {
        "20468679 (ETH leg, slot 9676085)": {**R[20468679], "story": {
            "victim_tx_first_seen_ms": fs(ETH_VICT), "victim_first_seen_rel_slot_ms": fs(ETH_VICT) - 1722937043000,
            "first_flashbots_relay_bid_carrying_about_4_ETH": next({"t_rel_slot_ms": b["t_rel_slot_ms"], "builder": nm(b), "eth": round(float(b["value_eth"]), 4), "num_tx": b["num_tx"]} for b in bids_of(20468679) if float(b["value_eth"]) > 3.9),
            "builder_bid_start_by_builder_ge_3.9ETH": {"Flashbots": -71, "Titan": 116, "beaverbuild.org": 192, "rsync-builder.xyz": 266, "builder0x69": 717},
            "winning_bid": "beaverbuild.org 4.043882 ETH delivered by bloXroute regulated (that relay keeps no bid history, so the winning bid's time is unknown); proposer payment tx idx 137 = bid value exactly",
            "yoink_builder_bids": "'I can haz block?' (Yoink's builder pubkey) submitted the highest Flashbots-relay bid of the slot, 5.0329 ETH with only 7 txs, at +649 ms and +757 ms after slot start, i.e. after beaverbuild/Titan/rsync were already bidding ~4.03 ETH; its contents are unknown, and a 7-tx block cannot be a copy of the 100+ tx beaverbuild block (no claim made that it contains an ETH-leg copy)",
            "bribe": "ETH-leg bot paid 3.996093266 ETH (0.1% of 3,996.09375) via coinbase.transfer to beaverbuild fee recipient 0x95222290...; builder passed 4.0439 ETH to proposer 0x4e9Cc05F... ; no refund tx in the block",
            "winning_block_contains_copy_tx": True}},
        "20468790 (copy of user withdrawal id 166632, slot 9676199)": {**R[20468790], "story": {
            "victim_tx_first_seen_ms": fs(R3_VICT), "victim_first_seen_rel_slot_ms": fs(R3_VICT) - 1722938411000,
            "note": "victim tx was first seen 284 ms AFTER the block timestamp, yet the racer's copy is at idx 0 of that block and the victim's own tx is in it at idx 258 reverting: the racer saw the tx earlier than the dumpster's four sources",
            "block_builder": "Titan (extraData 'Titan (titanbuilder.xyz)'), fee recipient 0x4838b106...; Titan's relay (titanrelay.xyz) has no history for 2024, so the delivered bid time/hash is unknown",
            "builder_payment_tx": R3_PROP, "builder_payment_eth": 2.213169569, "racer_bribe": "racer tx #2 (idx 1, 0x72a4daca...) is a self-transfer of 19.29 ETH with gas price ~103,573 gwei x 21,000 gas = 2.175 ETH of priority fee to the builder (90% of the 2.4173 ETH taken)",
            "first_flashbots_relay_bids_ge_2ETH_rel_slot_ms": {"Flashbots": 456, "beaverbuild": 596, "Titan": 645, "I can haz block?": 641},
            "winning_block_contains_copy_tx": True}},
        "20468848 (USDC leg, Yoink, slot 9676257)": {**R[20468848], "story": {
            "victim_tx_first_seen_ms": FS_Y, "victim_first_seen_rel_slot_ms": FS_Y - 1722939107000,
            "yoink_builder_first_bid_ms": y_first["timestamp_ms"], "yoink_first_bid_delay_after_first_seen_ms": y_first["timestamp_ms"] - FS_Y,
            "yoink_bid_ladder": [{"utc": utc(b["timestamp_ms"]), "t_rel_slot_ms": b["t_rel_slot_ms"], "eth": round(float(b["value_eth"]), 4), "num_tx": b["num_tx"], "pubkey": b["builder_pubkey"][:12], "win": b["is_winning_block"]} for b in yb],
            "earlier_competing_bids_eth": {"highest_non_yoink": 1.0845, "builder": "0x87d7fb5c... (73 tx) at 10:11:44.289"},
            "bot_txs_in_block": n_bot, "bot_coinbase_total_eth": round(bot_cb, 9), "builder_refund_to_bot_eth": refund, "refund_tx": Y_REFUND, "proposer_payment_eth": prop, "proposer_payment_tx": Y_PROP,
            "identity_of_builder": "EigenPhi (data/raw/web-p2/eigenphi_yoink_aug2024.html) names the builder as Yoink's own; extraData 'I can haz block?', fee recipient 0x229b8325...; two pubkeys 0x81476ce9 and 0xad251e6b used",
            "winning_block_contains_copy_tx": True}},
        "20468849 (next block, slot 9676258)": {**R[20468849], "story": {
            "victim_tx_landed": Y_VICT, "index": 112, "status": 0, "note": "the user's own USDC withdrawal lands 12 s later and reverts (withdrawal id 166633 already used); built by 0x840c9daf (Flashbots relay), bid 1.1956 ETH"}},
    }

    inc_json = {
        "slug": slug, "name": "Ronin Bridge (Ethereum side), 2024-08-06", "date": "2024-08-06", "chain": "ethereum", "verdict": "confirmed-onchain",
        "verdict_reason": ("There is no hostile attacker. A governance upgrade of the bridge proxy (tx 0x855dd3b1..., 08:48:47) left withdrawals checked in a way that let a modified receipt pass; the first post-upgrade user withdrawals "
                           "became bot bait. Three independent searchers each saw a legitimate user withdrawal (receipt ids 166631-166633) in the public mempool and sent a copy with the recipient (and for two of them the quantity) rewritten, ahead of it: "
                           "ETH leg 0x26195700 (block 20468679 pos 0, 3,996.09375 ETH), a third racer 0x77bb83dd (block 20468790 pos 0, 2.4173 ETH, quantity unchanged) and Yoink 0xbce5b854 (block 20468848 pos 1, 1,998,046.875 USDC). "
                           "Calldata diffs: ETH leg differs from the user's tx in 2 of 76 words, racer 3 in 1 of 67, Yoink in 3 of 61. All three were placed ahead of the user's tx, which stayed pending and later reverted."),
        "era": "post-Merge, mempool-dumpster sourcelog + Flashbots relay bids",
        "protocol_loss_usd": round(3996.09375 * 2452.9 + 1998046.875 * 0.99842514 + 2.417311 * 2452.9),
        "protocol_loss_basis": "3,996.09375 ETH + 1,998,046.875 USDC + 2.4173 ETH at DefiLlama ETH $2,452.9 (09:37:23); The Block/Ronin quote ~$12M",
        "attacker": {
            "note": "no adversarial attacker; the three 'originals' below are users' legitimate pending withdrawals that the searchers copied. The enabling change is the upgrade tx.",
            "enabler_tx": {"hash": UPG, "block": 20468438, "index": next(t["index"] for t in RD[20468438]["txs"] if t["hash"] == UPG), "first_seen_ms": fs(UPG), "utc": "2024-08-06T08:48:47Z", "sender": "0xe880802580a1fbdef67ace39d1b21c5b2c74f059", "to": "0xa71456fa88a5f6a4696d0446e690db4a5913fab0 (calls proxy upgrade to implementation 0xfc274ec92bbb1a1472884558d1b5caac6f8220ee)", "source": "bridge proxy Upgraded(address) log, data/raw/etherscan/p2_ronin_upgraded_logs_etherscan.json; Ronin statement: update 'introduced an issue leading the bridge to misinterpret the required bridge operators vote threshold'"},
            "eoas": ["0x441e6581d1b4869abb80188b9cf5223e77ab0302", "0xfbbf14eaec015bca5a4d1e934ae1796638a17919", "0x5f494a30f1b71b748b71939c18446288168cdaab"],
            "contracts": [], "deploy_tx": None, "funding_tx": None,
            "txs": [
                {"hash": ETH_VICT, "role": "user withdrawal id 166631, 0.35 WETH (copied by the ETH-leg searcher)", "first_seen_ms": fs(ETH_VICT), "first_seen_utc": utc(fs(ETH_VICT)), "per_source": fs_src(ETH_VICT), "landed_block": 20468888, "index": 144, "status": 0, "gas_price_gwei": 2.0},
                {"hash": R3_VICT, "role": "user withdrawal id 166632, 2.4173 WETH (copied by racer 3)", "first_seen_ms": fs(R3_VICT), "first_seen_utc": utc(fs(R3_VICT)), "per_source": fs_src(R3_VICT), "landed_block": 20468790, "index": 258, "status": 0},
                {"hash": Y_VICT, "role": "user withdrawal id 166633, 2,640.820595 USDC (copied by Yoink)", "first_seen_ms": fs(Y_VICT), "first_seen_utc": utc(fs(Y_VICT)), "per_source": fs_src(Y_VICT), "landed_block": 20468849, "index": 112, "status": 0},
            ],
        },
        "bots": [
            {"label": "Yoink", "eoa": "0xfde0d1575ed8e06fbf36256bcdfa1f359281455a", "contract": "0x6980a47bee930a4584b09ee79ebe46484fbdbdd0",
             "txs": [{"hash": Y_COPY, "block": 20468848, "index": 1, "status": 1, "msg_value": 999, "in_public_mempool": False}],
             "captured": {"token": "USDC -> WETH -> ETH", "amount": "1,998,046.875 USDC (swapped inside the tx to 796.4115 ETH)", "usd": round(1998046.875 * 0.99842514)},
             "coinbase_paid_eth": 795.615040934472, "priority_fee_gwei": 0.0,
             "replay_evidence": {"diff_file": "research/bot-re/ronin_calldata_diff.json (bot analysis) + research/defiplaza-ronin/ronin_copies_diff.json", "differing_words": diff["Yoink 0xfde0d157->0x6980a47b vs user 0xb7c3f85a (id 166633)"]["differing_words"],
                                 "identical_words": "58 of 61", "fork_replay": "research/bot-re/fork_replay_results.json (bot analysis)"},
             "notes": "builder is Yoink's own; 21 bot txs in the 24-tx block; builder refunded 791.742 ETH to the bot"},
            {"label": "ETH-leg searcher (general MEV bot 'mmmmMEV')", "eoa": "0x1a56abf4fe95e21c1704cbd5ffc79ea1effa3cc1", "contract": "0x4ab12e7ce31857ee022f273e8580f73335a73c0b",
             "txs": [{"hash": ETH_COPY, "block": 20468679, "index": 0, "status": 1, "msg_value_wei": 1, "selector": "0x972547d7", "in_public_mempool": False}],
             "captured": {"token": "ETH", "amount": "3,996.09375 ETH (= 4000 x (1 - 2^-10))", "usd": round(3996.09375 * 2452.9)},
             "coinbase_paid_eth": 3.996093266077822, "priority_fee_gwei": 0.0,
             "replay_evidence": {"diff": diff["ETH-leg searcher 0x1a56abf4->0x4ab12e7c vs user 0xc78fb8cd (id 166631)"]["differing_words"], "identical_words": "74 of 76",
                                 "call_tree": "EOA -> 0x4ab12e7c -> bridge submitWithdrawal 0x4d0d6673 (delegatecall to implementation 0xfc274ec9...), bridge pays 3,996.09375 ETH to 0x4ab12e7c, which pays 3.99609 ETH to coinbase 0x95222290 (beaverbuild)"},
             "notes": "the calldata rewrite changes only the recipient (word 2) and quantity (word 10); the Ronin-side address word is left as the user's"},
            {"label": "racer 3 (vanity EOA 0x00001b0b)", "eoa": "0x00001b0bcca9bc88774000692def9dd6452afb9f", "contract": "0x02f3d3912f8bd97c4791970aa4cf96dedd05772c",
             "txs": [{"hash": R3_COPY, "block": 20468790, "index": 0, "status": 1, "selector": "0x64558356", "priority_fee_gwei": 0.901569502, "note": "same tip as the victim's gasTipCap 901569502"},
                     {"hash": R3_PAY, "block": 20468790, "index": 1, "status": 1, "note": "self-transfer of 19.29 ETH with gas price ~103,573 gwei: pays 2.175 ETH of priority fee to the builder"}],
             "captured": {"token": "ETH", "amount": "2.417311 ETH (the user's own withdrawal amount, quantity NOT inflated)", "usd": round(2.417311 * 2452.9)},
             "coinbase_paid_eth": 0.0, "priority_fee_gwei": 103573.17, "builder_payment_via_priority_fee_eth": 2.175036667,
             "replay_evidence": {"diff": diff["racer 0x00001b0b->0x02f3d391 vs user 0x56439cf9 (id 166632)"]["differing_words"], "identical_words": "66 of 67"},
             "notes": "no return of the 2.4173 ETH found in the EOA/contract histories through 2024-08-06 22:00 (Etherscan txlist/internal); the vanity EOA was messaged by 0x01bf1d7c at 11:02:59"},
        ],
        "other_racers": [
            {"label": "no further copier found", "evidence": "all Withdrew events of the bridge proxy between the upgrade and the pause (Etherscan getLogs 20468438-20475000): 3 incident txs + 6 small ordinary withdrawals to relayer 0xc9a5643e...; ETH out of the bridge (txlistinternal) and USDC out (tokentx) in 20468300-20470500 match exactly those 3", "raw": "data/raw/etherscan/p2_ronin_bridge_alllogs_20468438_20475000.json"},
            {"label": "Yoink-builder 5.0329 ETH, 7-tx bid on the ETH-leg slot (+649 ms)", "evidence": "highest bid in the Flashbots-relay record; contents unknown, so no claim that Yoink also copied the ETH-leg withdrawal"},
        ],
        "funds_fate": [
            {"what": "ETH-leg: bridge -> bot contract", "tx": ETH_COPY, "amount": "3,996.09375 ETH", "to": "0x4ab12e7c...", "utc": "2024-08-06T09:37:23Z"},
            {"what": "ETH-leg: coinbase tip", "tx": ETH_COPY, "amount": "3.996093266 ETH", "to": "0x95222290dd7278aa3ddd389cc1e1d165cc4bafe5 (beaverbuild)"},
            {"what": "ETH-leg: builder -> proposer", "tx": ETH_PROP, "amount": "4.043882228 ETH", "to": "0x4e9cc05f7f944d618de85396e669922c2cf6813e"},
            {"what": "ETH-leg: test return from bot contract (withdrawTo)", "tx": ETH_RET1, "amount": "1.0 ETH", "to": "0xc6aec68dd6272efcbc74fb5308fe7f070437465e", "utc": "2024-08-06T10:00:11Z"},
            {"what": "ETH-leg: main return (withdrawTo), 22 min after the take, before any contact", "tx": ETH_RET2, "amount": "4,000.0 ETH", "to": "0xc6aec68dd6272efcbc74fb5308fe7f070437465e", "utc": "2024-08-06T10:00:59Z"},
            {"what": "ETH-leg: 0xc6aec68d -> Safe 0x137f31b2...f488 (test)", "tx": E_SAFE1, "amount": "1.0 ETH", "to": "0x137f31b23f9991df465a1d16eccbcaa11ab9f488", "utc": "2024-08-06T15:00:47Z"},
            {"what": "ETH-leg: 0xc6aec68d -> Safe 0x137f31b2...f488", "tx": E_SAFE2, "amount": "3,991.097 ETH", "to": "0x137f31b23f9991df465a1d16eccbcaa11ab9f488", "utc": "2024-08-06T15:04:23Z"},
            {"what": "ETH-leg: kept at 0xc6aec68d (4001 received - 3992.097 forwarded)", "tx": None, "amount": "8.903 ETH (not traced further; press: 'remaining 5 ETH not returned', Cointelegraph/PeckShield)", "to": "0xc6aec68d..."},
            {"what": "racer 3: bridge -> contract -> its EOA", "tx": R3_COPY, "amount": "2.417311 ETH", "to": "0x00001b0bcca9bc88774000692def9dd6452afb9f", "utc": "2024-08-06T10:00:11Z"},
            {"what": "racer 3: builder payment via priority fee of tx#2", "tx": R3_PAY, "amount": "2.175036667 ETH", "to": "Titan builder 0x4838b106..."},
            {"what": "Yoink: bridge -> bot as USDC", "tx": Y_COPY, "amount": "1,998,046.875 USDC", "to": "0x6980a47b...", "utc": "2024-08-06T10:11:47Z"},
            {"what": "Yoink: USDC -> 796.4115 ETH inside the tx; coinbase tip", "tx": Y_COPY, "amount": "795.615040934 ETH", "to": "0x229b8325bb9ac04602898b7e8989998710235d5f (builder)"},
            {"what": "Yoink: builder refund to bot at block pos 22", "tx": Y_REFUND, "amount": "791.742284675 ETH", "to": "0x6980a47b..."},
            {"what": "Yoink: builder -> proposer (= winning bid) at pos 23", "tx": Y_PROP, "amount": "11.04299088 ETH", "to": "0x498fe6625628053e4f97246161fab24aea3dec36"},
            {"what": "Yoink: bot withdrawTo by owner, 17 min after landing, 24 min before Ronin's first message", "tx": Y_WD, "amount": "800.0 ETH", "to": "0x796f09c9667a49bdb2bac2c8f1c2ee3c7576a93f", "utc": "2024-08-06T10:29:11Z"},
            {"what": "Yoink: 0x796f09c9 -> Safe 0x137f31b2...f488", "tx": Y_SAFE, "amount": "792.4557 ETH", "to": "0x137f31b23f9991df465a1d16eccbcaa11ab9f488", "utc": "2024-08-06T17:05:59Z"},
            {"what": "Yoink: left at 0x796f09c9 (800 - 792.4557); no onward tx through block 20490000", "tx": None, "amount": "7.5443 ETH", "to": "0x796f09c9..."},
            {"what": "Ronin message to Yoink owner (input data): 'Hey, thanks a lot for white hat saving user funds today. Can we chat over Blockscan chat?'", "tx": MSG_Y, "amount": "0", "to": "0xfde0d157...", "from": "0x01bf1d7c5e192313c26414e134584275f46271cf", "utc": "2024-08-06T10:53:35Z"},
            {"what": "same message to the ETH-leg EOA", "tx": MSG_E, "amount": "0", "to": "0x1a56abf4...", "from": "0x01bf1d7c5e...", "utc": "2024-08-06T10:54:59Z"},
            {"what": "same message to racer 3's EOA", "tx": MSG_R3, "amount": "0", "to": "0x00001b0b...", "from": "0x01bf1d7c5e...", "utc": "2024-08-06T11:02:59Z"},
            {"what": "Bounty USD 500K: REPORTED only (Ronin statement via press: 'bug bounty program will reward the white hats'; EigenPhi: Yoink and the other whitehat 'shared $500K'). No on-chain bounty payment identified; 0x137f31b2...f488 is a Safe (execTransaction) that received the returns - label 'Ronin-controlled' is inferred from the flow, not from a public tag", "tx": None, "amount": "$500,000", "to": "-"},
            {"what": "Safe re-converted: 785 ETH out to 0x199b51f2c5... (2024-08-08 11:21:35) and 1,954,372 USDC back in (12:50:47) - consistent with Ronin restoring the USDC leg (inferred)", "tx": "0xfb5a52287cf2 / 0x7796ee36f527", "amount": "785 ETH -> 1,954,372 USDC", "to": "0x137f31b2..."},
        ],
        "auction": auction_blocks,
        "sources": [
            "https://www.theblock.co/post/309707/ronin-bridge-pauses", "https://www.bleepingcomputer.com/news/security/ronin-network-hacked-12-million-returned-by-white-hat-hackers/",
            "https://cointelegraph.com/news/ronin-white-hat-attacker-returns-10-million-eth-apparent-accidental-front-run",
            "https://eigenphi.substack.com/p/mev-maestro-yoink-netting-265m-on-59-blocks-in-aug", "research/bot-re/analysis.md section 4.1",
        ],
        "raw_refs": {
            "upgrade_logs": ref("data/raw/etherscan/p2_ronin_upgraded_logs_etherscan.json"), "bridge_all_logs": ref("data/raw/etherscan/p2_ronin_bridge_alllogs_20468438_20475000.json"),
            "bridge_txlist": ref("data/raw/etherscan/p2_ronin_bridge_txlist_20468300_20469600.json"), "bridge_internal": ref("data/raw/etherscan/p2_ronin_bridge_txlistinternal_20468300_20470500.json"),
            "bridge_tokentx": ref("data/raw/etherscan/p2_ronin_bridge_tokentx_20468300_20470500.json"),
            "mempool_lookup": "research/defiplaza-ronin/ronin_mempool_lookup.json", "mempool_csv": ref("data/raw/mempool-dumpster/2024-08-06.csv.zip"), "mempool_sourcelog": ref("data/raw/mempool-dumpster/2024-08-06_sourcelog.csv.zip"),
            "calldata_diffs": "research/defiplaza-ronin/ronin_copies_diff.json",
            "eth_leg_trace": ref(f"data/raw/rpc/trace_{ETH_COPY}.json"), "racer3_trace": ref(f"data/raw/rpc/trace_{R3_COPY}.json"), "yoink_trace": ref(f"data/raw/rpc/trace_{Y_COPY}.json"),
            "race_blocks": [f"incidents/ronin-2024/race_{b}.json" for b in (20468438, 20468679, 20468790, 20468848, 20468849)],
            "ethleg_contract_internal": ref("data/raw/etherscan/p2_ronin_ethleg_contract_txlistinternal_20468600_20480000.json"),
            "ethleg_recv_c6ae": ref("data/raw/etherscan/p2_ronin_ronin_recv_c6ae_txlist_20468000_20480000.json"),
            "yoink_bot_after": ref("data/raw/etherscan/p2_ronin_yoink_bot_after_txlistinternal_20468849_20475000.json"), "yoink_dest_796f": ref("data/raw/etherscan/p2_ronin_yoink_dest_796f_txlist_20468000_20490000.json"),
            "safe_137f31": ref("data/raw/etherscan/p2_ronin_ronin_137f31_txlist_20470000_20520000.json"),
            "racer3_eoa": ref("data/raw/etherscan/p2_ronin_racer3_eoa_txlist_20468000_20472000.json"), "yoink_owner_txlist": ref("data/raw/etherscan/p2_ronin_yoink_owner_txlist_20468848_20472000.json"),
            "prices": ref("data/raw/defillama/p2_ronin_prices_1722937043.json"),
            "press": ["data/raw/web-p2/bleeping_ronin.html", "data/raw/web-p2/cointelegraph_ronin.html", "data/raw/web-p2/eigenphi_yoink_aug2024.html", "data/raw/web-p2/cryptonews_ronin.html"],
        },
    }
    json.dump(inc_json, open(inc / "incident.json", "w"), indent=1)

    # ------------------------------ timeline ------------------------------
    T = []
    S = lambda b: blk_ts(b) * 1000
    T.append(ev(fs(UPG), "mempool_seen", "Ronin governance executor 0xe8808025", "upgrade tx first seen (08:48:47.379, 379 ms after the block timestamp: the dumpster saw it after inclusion)", tx=UPG, raw="research/defiplaza-ronin/ronin_mempool_lookup.json", per_source=fs_src(UPG)))
    T.append(ev(S(20468438), "block", "chain", "block 20468438: bridge proxy upgraded to implementation 0xfc274ec9... (Upgraded log); first block with the faulty vote-threshold check", tx=UPG, raw="data/raw/etherscan/p2_ronin_upgraded_logs_etherscan.json", precision="s"))
    T.append(ev(fs(ETH_VICT), "mempool_seen", "user 0x441e6581", "legit withdrawal id 166631 (0.35 WETH), gas price 2 gwei, first seen 600 ms before the slot start; four sources within 184 ms", tx=ETH_VICT, raw="research/defiplaza-ronin/ronin_mempool_lookup.json", per_source=fs_src(ETH_VICT)))
    b679 = [b for b in bids_of(20468679) if float(b["value_eth"]) > 3.9]
    T.append(ev(b679[0]["timestamp_ms"], "bid", nm(b679[0]), f"first Flashbots-relay bid carrying ~4 ETH ({float(b679[0]['value_eth']):.4f} ETH, {b679[0]['num_tx']} tx): {b679[0]['timestamp_ms'] - fs(ETH_VICT)} ms after the victim tx was first seen", raw="data/raw/relay-flashbots/bids_block20468679.json", t_rel_slot_ms=b679[0]["t_rel_slot_ms"]))
    for key, name in (("Titan", "Titan (titanbuilder.xyz)"), ("beaverbuild.org", "beaverbuild.org"), ("I can haz block?", "I can haz block?")):
        c = next((b for b in b679 if nm(b) == name), None)
        if c:
            T.append(ev(c["timestamp_ms"], "bid", name, f"first ~4+ ETH bid on the ETH-leg slot: {float(c['value_eth']):.4f} ETH, {c['num_tx']} tx" + (" (highest bid of the slot, +%d ms after slot start; contents unknown)" % c["t_rel_slot_ms"] if "haz" in name else ""), raw="data/raw/relay-flashbots/bids_block20468679.json", t_rel_slot_ms=c["t_rel_slot_ms"]))
    T.append(ev(S(20468679), "block", "beaverbuild.org (delivered via bloXroute regulated)", "block 20468679 (slot 9676085): pos 0 ETH-leg copy 0x26195700 takes 3,996.09375 ETH, tips beaverbuild 3.996093 ETH; pos 137 builder pays proposer 4.043882 ETH. Winning bid time unknown (bloXroute keeps no history)", tx=ETH_COPY, raw="incidents/ronin-2024/race_20468679.json", precision="block"))
    T.append(ev(S(20468790), "block", "Titan builder", "block 20468790 (slot 9676199): pos 0 racer-3 copy 0x77bb83dd takes 2.4173 ETH (user's own quantity); pos 1 self-transfer pays builder 2.175 ETH; pos 258 the user's own tx reverts; pos 280 builder pays proposer 2.213170 ETH; also contains ETH-leg bot's 1 ETH test return 0x017e9160 (tx idx in race file)", tx=R3_COPY, raw="incidents/ronin-2024/race_20468790.json", precision="block"))
    T.append(ev(fs(R3_VICT), "mempool_seen", "user 0xfbbf14ea", "legit withdrawal id 166632 (2.4173 WETH) first seen 284 ms AFTER block 20468790's timestamp; the racer's copy is already at idx 0 of that block", tx=R3_VICT, raw="research/defiplaza-ronin/ronin_mempool_lookup.json", per_source=fs_src(R3_VICT)))
    for b in bids_of(20468790):
        if float(b["value_eth"]) >= 2.0:
            T.append(ev(b["timestamp_ms"], "bid", nm(b), f"first >=2 ETH Flashbots-relay bid for slot 9676199: {float(b['value_eth']):.4f} ETH, {b['num_tx']} tx", raw="data/raw/relay-flashbots/bids_block20468790.json", t_rel_slot_ms=b["t_rel_slot_ms"]))
            break
    T.append(ev(S(20468790), "return", "ETH-leg bot owner 0x1a56abf4", "withdrawTo 1.0 ETH test to 0xc6aec68d (tx idx in block 20468790)", tx=ETH_RET1, raw="data/raw/etherscan/p2_ronin_ethleg_contract_txlistinternal_20468600_20480000.json", precision="s"))
    T.append(ev(blk_ts(20468794) * 1000 if blk_ts(20468794) else 1722938459000, "return", "ETH-leg bot owner 0x1a56abf4", "withdrawTo 4,000 ETH to 0xc6aec68d - 22 min after the take, 53 min before Ronin's first message to this EOA", tx=ETH_RET2, raw="data/raw/etherscan/p2_ronin_ethleg_contract_txlistinternal_20468600_20480000.json", precision="s"))
    T.append(ev(fs(Y_VICT), "mempool_seen", "user 0x5f494a30", "legit withdrawal id 166633 (2,640.820595 USDC) first seen: chainbound .233, bloxroute .239, local .280, mempoolguru .407", tx=Y_VICT, raw="research/defiplaza-ronin/ronin_mempool_lookup.json", per_source=fs_src(Y_VICT)))
    for b in bids_of(20468848):
        n = nm(b)
        v = float(b["value_eth"])
        if b["timestamp_ms"] > FS_Y and (n.startswith("I can haz") or v > 1.0):
            T.append(ev(b["timestamp_ms"], "bid", n, f"{v:.4f} ETH, {b['num_tx']} tx, gas {b['gas_used']}, block {b['block_hash'][:12]}, pubkey {b['builder_pubkey'][:10]}" + (" WINNING (delivered by Agnostic, Flashbots, Ultra Sound)" if b["is_winning_block"] else ""),
                        raw="data/raw/relay-flashbots/bids_block20468848.json", t_rel_slot_ms=b["t_rel_slot_ms"], block_hash=b["block_hash"], is_winning=b["is_winning_block"]))
    T.append(ev(S(20468848), "block", "Yoink builder 'I can haz block?'", f"block 20468848 (slot 9676257): 24 txs, 21 from Yoink; pos 1 copy 0xbce5b854 takes 1,998,046.875 USDC, tips builder 795.615 ETH; pos 22 builder refunds {refund:.6f} ETH to the bot; pos 23 builder pays proposer {prop:.6f} ETH", tx=Y_COPY, raw="incidents/ronin-2024/race_20468848.json", precision="block"))
    T.append(ev(S(20468849), "tx", "user 0x5f494a30", "block 20468849 pos 112: the user's own withdrawal lands 12 s later and reverts (id 166633 already used)", tx=Y_VICT, raw="incidents/ronin-2024/race_20468849.json", precision="block"))
    T.append(ev(1722939312114, "mempool_seen", "Ronin ops 0x8b35c5e2", "pause() tx first seen 10:15:12.114", tx=PAUSE, raw="research/defiplaza-ronin/ronin_mempool_lookup.json"))
    T.append(ev(1722939323000, "block", "chain", "block 20468866 10:15:23: bridge Paused (about 38 min after the first take)", tx=PAUSE, raw="data/raw/etherscan/p2_ronin_bridge_alllogs_20468438_20475000.json", precision="s"))
    T.append(ev(fs(ETH_VICT) + 2544600, "tx", "user 0x441e6581", "block 20468888: the ETH-leg victim's own tx finally lands (10:19:47), reverts on the paused bridge", tx=ETH_VICT, raw="data/raw/etherscan/p2_ronin_bridge_txlist_20468300_20469600.json", precision="s"))
    T.append(ev(1722940151000, "return", "Yoink owner 0xfde0d157", "withdrawTo(800 ETH) from bot contract to 0x796f09c9 (block 20468935) - before any contact from Ronin", tx=Y_WD, raw="data/raw/etherscan/p2_ronin_yoink_bot_after_txlistinternal_20468849_20475000.json", precision="s"))
    T.append(ev(1722941615000, "message", "0x01bf1d7c (Ronin-side, inferred)", "on-chain text to Yoink owner: 'Hey, thanks a lot for white hat saving user funds today. Can we chat over Blockscan chat?'", tx=MSG_Y, raw="data/raw/etherscan/p2_ronin_yoink_owner_txlist_20468848_20472000.json", precision="s"))
    T.append(ev(1722941699000, "message", "0x01bf1d7c", "same text to ETH-leg EOA 0x1a56abf4", tx=MSG_E, raw="data/raw/etherscan/p2_ronin_ethleg_eoa_txlist_20468600_20480000.json", precision="s"))
    T.append(ev(1722942179000, "message", "0x01bf1d7c", "same text to racer-3 EOA 0x00001b0b", tx=MSG_R3, raw="data/raw/etherscan/p2_ronin_racer3_eoa_txlist_20468000_20472000.json", precision="s"))
    T.append(ev(1722956447000, "return", "0xc6aec68d (ETH-leg returns)", "1 ETH test to Safe 0x137f31b2...f488", tx=E_SAFE1, raw="data/raw/etherscan/p2_ronin_ronin_137f31_txlist_20470000_20520000.json", precision="s"))
    T.append(ev(1722956663000, "return", "0xc6aec68d (ETH-leg returns)", "3,991.097 ETH to Safe 0x137f31b2...f488 (press: 3,991 ETH returned, ~5 ETH not)", tx=E_SAFE2, raw="data/raw/etherscan/p2_ronin_ronin_137f31_txlist_20470000_20520000.json", precision="s"))
    T.append(ev(1722963959000, "return", "0x796f09c9 (Yoink-side)", "792.4557 ETH to Safe 0x137f31b2...f488 (about the USDC leg's 796.41 ETH value less 3.96 ETH)", tx=Y_SAFE, raw="data/raw/etherscan/p2_ronin_yoink_dest_796f_txlist_20468000_20490000.json", precision="s"))
    T.append(ev(1722945600000, "message", "Ronin / press", "Ronin statements (via The Block, BleepingComputer, Cointelegraph, 2024-08-06/07): ETH returned, USDC to follow, $500K bounty to the white hats (reported, not verified on chain)", raw="data/raw/web-p2/bleeping_ronin.html", precision="day"))
    T.sort(key=lambda e: e["t_utc_ms"])
    json.dump({"slug": slug, "note": "precision: ms = mempool/relay clocks; s = block time; block = all txs of a block share its timestamp; day = press statements without a time", "events": T}, open(inc / "timeline.json", "w"), indent=1)
    return inc_json


if __name__ == "__main__":
    a = defiplaza()
    b = ronin()
    print("defiplaza events ok; loss", a["protocol_loss_usd"])
    print("ronin ok; loss", b["protocol_loss_usd"])
