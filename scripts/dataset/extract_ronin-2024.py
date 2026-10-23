"""Extract ronin-2024 -> data/extract/ronin-2024.json (incident dataset): 3 rows (eth-leg, racer3, yoink-usdc).
Run from project root: .venv/bin/python scripts/dataset/extract_ronin-2024.py
Figures are recomputed from saved raw files (rpc blocks/traces/receipts, etherscan lists, defillama prices, mempool-dumpster via race files) and asserted."""
import json, pathlib, sys, datetime
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import bvh

SLUG = "ronin-2024"
D = f"incidents/{SLUG}"
E18 = 10 ** 18
J = lambda p: json.load(open(ROOT / p))
res = lambda d: d["result"] if isinstance(d, dict) and "result" in d else d
iso = lambda ts: datetime.datetime.fromtimestamp(int(ts), datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
isoms = lambda ms: datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (ms % 1000)
BRIDGE = "0x64192819ac13ef72bf6b5ae239ac672b43a9af08"
SAFE = "0x137f31b23f9991df465a1d16eccbcaa11ab9f488"
SRC4 = ["chainbound", "bloxroute", "local", "mempoolguru"]
inc = J(f"{D}/incident.json")
races = {n: J(f"{D}/race_{n}.json") for n in (20468679, 20468790, 20468848, 20468849)}
txs = {}
for n, r in races.items():
    for t in r["txs"]:
        txs.setdefault(t["hash"], (n, t))
PRICES = "data/raw/defillama/p2_ronin_prices_1722937043.json"
pr = J(PRICES)["coins"]
ETHUSD = pr["coingecko:ethereum"]["price"]
USDCUSD = pr["ethereum:0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"]["price"]
assert ETHUSD == 2452.9

ES = "data/raw/etherscan/"
def elist(f):
    return res(J(ES + f))
def efind(f, prefix):
    for x in elist(f):
        if x["hash"].startswith(prefix):
            return x
    raise KeyError(prefix)

def no_refund(block_no, bot_addrs):
    """no tx/internal transfer of ETH from a non-bot address into a bot address in this block (block + trace_block scan)."""
    bots = {a.lower() for a in bot_addrs}
    b = J(f"data/raw/rpc/block_{block_no}.json")["result"]
    for t in b["transactions"]:
        if t["to"] and t["to"].lower() in bots and t["from"].lower() not in bots and int(t["value"], 16) > 0:
            return False
    for t in J(f"data/raw/rpc/trace_block_{block_no}.json")["result"]:
        a = t.get("action", {})
        if a.get("to", "").lower() in bots and a.get("from", "").lower() not in bots and int(a.get("value", "0x0"), 16) > 0 and t.get("type") == "call":
            # the bridge pays the bot (the take itself); only count transfers NOT from the bridge proxy
            if a.get("from", "").lower() != BRIDGE:
                return False
    return True

def calldata_diff(bot_tx, user_tx):
    def walk(c, out):
        if c.get("to", "").lower() == BRIDGE and c.get("input", "")[:10] == "0x4d0d6673":
            out.append(c)
        for x in c.get("calls", []) or []:
            walk(x, out)
    out = []
    walk(res(J(f"data/raw/rpc/trace_{bot_tx}.json")), out)
    assert len(out) == 1
    u = res(J(f"data/raw/rpc/tx_{user_tx}.json"))["input"][10:]
    b = out[0]["input"][10:]
    uw = [u[i:i + 64] for i in range(0, len(u), 64)]
    bw = [b[i:i + 64] for i in range(0, len(b), 64)]
    assert len(uw) == len(bw)
    return [i for i in range(len(uw)) if uw[i] != bw[i]], len(uw)

def user_receipt(h):
    r = res(J(f"data/raw/rpc/rcpt_{h}.json"))
    return int(r["blockNumber"], 16), int(r["transactionIndex"], 16), int(r["status"], 16)

def message(file, prefix):
    x = efind(file, prefix)
    assert x["from"].lower().startswith("0x01bf1d7c")
    return x, bytes.fromhex(x["input"][2:]).decode()

def base_row(sub, name, bot_tx, race_no, user_tx, bot_meta, extra):
    r = races[race_no]
    n, t = txs[bot_tx]
    assert n == race_no and t["status"] == 1
    a = bvh.auction_summary(f"{D}/race_{race_no}.json", bot_tx)
    miss = a.pop("_missing_raw")
    assert not miss
    ub, ui, us = user_receipt(user_tx)
    ut = res(J(f"data/raw/rpc/tx_{user_tx}.json"))
    um = races[race_no]["mempool"]["txs"][user_tx] if user_tx in races[race_no]["mempool"]["txs"] else None
    return r, t, a, (ub, ui, us), ut

rows = []

# ================= Row 1: ETH leg =================
BOT1 = "0x2619570088683e6cc3a38d93c3d98899e5783864e15525d5f5810c11189ba6cb"
USER1 = "0xc78fb8cd5f7813a3d8abebdc5351aafd5011e8e13c5f6740837eeef9308d1faf"
r1, t1, a1, (ub1, ui1, us1), ut1 = base_row("eth-leg", None, BOT1, 20468679, USER1, None, None)
assert t1["index"] == 0 and (ub1, ui1, us1) == (20468888, 144, 0)
bot1_eoa, bot1_ct = "0x1a56abf4fe95e21c1704cbd5ffc79ea1effa3cc1", "0x4ab12e7ce31857ee022f273e8580f73335a73c0b"
assert t1["from"] == bot1_eoa and t1["to"] == bot1_ct
EL = "p2_ronin_ethleg_contract_txlistinternal_20468600_20480000.json"
take1 = next(x for x in elist(EL) if x["hash"] == BOT1 and x["from"].lower() == BRIDGE and x["to"].lower() == bot1_ct)
gross1 = int(take1["value"]) / E18
assert gross1 == 3996.09375
cb1 = int(t1["coinbase_transfer_wei"]) / E18
assert abs(cb1 - 3.996093266077822) < 1e-12 and t1["priority_fee_total_wei"] == "0"
assert no_refund(20468679, [bot1_eoa, bot1_ct])
diff1, nw1 = calldata_diff(BOT1, USER1)
assert diff1 == [2, 10] and nw1 == 76
seen1 = races[20468679]["mempool"]["txs"][USER1]
assert seen1["first_seen_ms"] == 1722937042400 and seen1["seen_before_block_ms"] == 600
user_maxfee1 = int(ut1["maxFeePerGas"], 16) / 1e9
assert user_maxfee1 == 2.0 and r1["block"]["base_fee_gwei"] > user_maxfee1
test1 = next(x for x in elist(EL) if x["hash"].startswith("0x017e91606e01"))
main1 = next(x for x in elist(EL) if x["hash"].startswith("0xacd5202dd0b3"))
assert test1["to"].lower().startswith("0xc6aec68d") and main1["to"].lower().startswith("0xc6aec68d")
ret1_bot = (int(test1["value"]) + int(main1["value"])) / E18
assert ret1_bot == 4001.0 and iso(main1["timeStamp"]) == "2024-08-06T10:00:59Z" and iso(test1["timeStamp"]) == "2024-08-06T10:00:11Z"
C6 = "p2_ronin_ronin_recv_c6ae_txlist_20468000_20480000.json"
s1a = efind(C6, "0xf0e1fc14"); s1b = efind(C6, "0xf8f097982bc0")
assert s1a["to"].lower() == SAFE and s1b["to"].lower() == SAFE
ret1_safe = (int(s1a["value"]) + int(s1b["value"])) / E18
assert abs(ret1_safe - 3992.097) < 1e-9
msg1, txt1 = message("p2_ronin_ethleg_eoa_txlist_20468600_20480000.json", "0x945a7156")
net1 = gross1 - cb1
usd1 = gross1 * ETHUSD
RPC = "data/raw/rpc/"
refs1 = {
    "bot.block": RPC + "block_20468679.json", "bot.position": RPC + "block_20468679.json",
    "attacker_block": [RPC + f"rcpt_{USER1}.json", RPC + f"tx_{USER1}.json"],
    "trigger.first_seen_utc_ms": ["data/raw/mempool-dumpster/2024-08-06.csv.zip", "data/raw/mempool-dumpster/2024-08-06_sourcelog.csv.zip"],
    "loot.gross_loot_eth": [ES + EL, RPC + f"trace_{BOT1}.json"],
    "loot.coinbase_paid_eth": [RPC + "trace_block_20468679.json", RPC + f"trace_{BOT1}.json"],
    "loot.priority_fee_paid_eth": [RPC + "receipts_20468679.json", RPC + "block_20468679.json"],
    "loot.builder_refund_to_bot_eth": [RPC + "block_20468679.json", RPC + "trace_block_20468679.json"],
    "loot.bot_net_eth": [ES + EL, RPC + "trace_block_20468679.json"],
    "loot.captured_usd": [PRICES, ES + EL],
    "fate.returned_by_bot_eth": ES + EL,
    "fate.returned_total_eth": ES + C6,
    "fate.kept_by_bot_eth": [ES + EL, ES + C6],
}
a1["auction_note"] = (
    "Winning block: beaverbuild.org, bid %.4f ETH delivered by bloXroute-regulated (that relay keeps no bid history, so the winning bid's own submission time is unknown); proposer payment tx %s (idx 137) equals the bid. "
    "Highest bid seen on the Flashbots relay was %.4f ETH from builder 'I can haz block?' (Yoink's builder; only 7 txs, +649 ms after slot start), contents unknown, so no claim that Yoink also copied this withdrawal. "
    "The copy tx paid %.6f ETH (0.1%% of the take) by coinbase transfer to the beaverbuild fee recipient. Winning-block submission times are not available, so detection delay cannot be measured from the Flashbots bid record alone."
) % (a1["winning_bid_eth"], a1["proposer_payment_tx"], a1["max_bid_eth"], cb1)
rows.append({
    "slug": SLUG, "sub": "eth-leg", "name": "Ronin Bridge (Ethereum side) 2024-08-06 - ETH leg: 3,996 ETH copied from a user's pending withdrawal",
    "date_utc": r1["block"]["timestamp_utc"].replace("+00:00", "Z"), "chain": "ethereum", "orig_verdict": inc["verdict"],
    "race_type_proposed": "beat-whitehat-or-user",
    "race_type_reason": ("After a governance upgrade (tx 0x855dd3b1..., 08:48:47) the bridge accepted rewritten withdrawal receipts. The bot copied a legitimate user's pending 0.35 WETH withdrawal (id 166631) with only the recipient and quantity words changed "
                         "(2 of 76 calldata words) and landed it first; the user's own tx stayed unincludable (max fee 2.0 gwei below the 2.6177 gwei base fee) and reverted at 20468888 after the pause."),
    "one_liner": "A searcher copied a user's pending 0.35 WETH Ronin bridge withdrawal after a faulty upgrade, rewriting recipient and amount to take 3,996 ETH, then sent 4,001 ETH back 23 minutes later; no hostile attacker.",
    "attacker": {"eoa": None, "eoas": [], "contracts": [], "funding": "n/a", "funding_tx": None, "deploy_tx": None, "deploy_block": None,
                 "attack_txs": [{"hash": USER1, "block": ub1, "index": ui1, "status": "reverted",
                                 "role": "legitimate user withdrawal id 166631 by 0x441e6581 (0.35 WETH) that the bot copied; not an attack; stayed pending and reverted on the paused bridge"}],
                 "none_reason": ("No hostile attacker: the 'original' is a user's legitimate pending withdrawal. The enabling event is the governance upgrade tx 0x855dd3b1194e3b889f4667b6a0996220e350e034d35d3eab29b4f23bc205767e "
                                 "(block 20468438, 08:48:47Z) of the bridge proxy to implementation 0xfc274ec9..., which Ronin said 'introduced an issue leading the bridge to misinterpret the required bridge operators vote threshold'. "
                                 "The three bots were the ones to exploit it, and all returned funds except racer 3 (no return found).")},
    "bot": {"label": "ETH-leg searcher (mmmmMEV)", "eoa": bot1_eoa, "contract": bot1_ct, "tx": BOT1, "block": 20468679, "position": t1["index"], "status": "success", "priority_fee_gwei": t1["priority_fee_gwei"]},
    "bots_other": [],
    "evidence_level_mempool": "measured",
    "mempool_note": "The user's pending tx was seen by four mempool-dumpster sources (first 09:37:22.400, 600 ms before the bot block's slot start); the bot's own tx is not in the archive (private order flow / bundle).",
    "trigger": {"kind": "user-tx", "tx": USER1, "first_seen_utc_ms": seen1["first_seen_ms"], "first_seen_utc": isoms(seen1["first_seen_ms"]), "sources": SRC4,
                "note": "User withdrawal id 166631 first seen in the public mempool 600 ms before the slot of the bot's block; the first ~4 ETH bid on the Flashbots relay (4.0209 ETH, 132 tx) arrived 529 ms after it (timeline.json); the user's tx later landed at 20468888 idx 144 and reverted."},
    "attacker_block": ub1,
    "attacker_block_note": ("Block where the copied user withdrawal finally landed (and reverted, bridge paused at 10:15:23). The user tx (max fee 2.0 gwei) was below the base fee (%.4f gwei) of the bot block, so it could not land there; "
                            "the bot landed %d blocks (about 42 min) before it." % (r1["block"]["base_fee_gwei"], ub1 - 20468679)),
    "attacker_reference": {"kind": "attack-tx", "block": ub1, "tx": USER1},
    "auction": a1,
    "loot": {
        "scope": "bot-tx", "gross_loot_eth": gross1, "gross_loot_method": "internal ETH transfer bridge proxy -> bot contract inside the bot tx (txlistinternal and trace)",
        "captured_native": {"amount": gross1, "unit": "ETH", "desc": "native ETH paid by the bridge to the bot contract (= 4000 x (1 - 2^-10))"},
        "captured_usd": round(usd1, 2), "captured_usd_source": "gross ETH x DefiLlama ETH $%s at 09:37:23 (%s)" % (ETHUSD, PRICES),
        "coinbase_paid_eth": cb1, "priority_fee_paid_eth": 0.0, "builder_refund_to_bot_eth": 0.0, "builder_payout_to_victim_eth": None,
        "bot_net_eth": net1,
        "loot_note": "Scope: the bot tx only. Coinbase transfer %.6f ETH (0.1%% of the take) to beaverbuild's fee recipient 0x95222290; priority fee 0 (max priority 0). No builder -> bot refund in the block (block + trace scan). bot_net = gross - coinbase, before gas base fee and before the later return." % cb1,
    },
    "fate": {
        "return_status": "returned", "returned_by_bot_eth": ret1_bot, "returned_by_builder_eth": None, "returned_total_eth": ret1_safe,
        "returned_to": "bot contract -> 0xc6aec68d... (4001 ETH) -> Safe 0x137f31b2...f488 (3,992.097 ETH); the Safe's Ronin ownership is inferred from the flow, not from a public tag",
        "returned_desc": ("The bot contract sent 1.0 ETH (test, 10:00:11Z) and 4,000 ETH (10:00:59Z, 23 min after the take) to 0xc6aec68d..., 52 min before Ronin's first on-chain message (10:54:59Z to this EOA). "
                          "0xc6aec68d forwarded 1.0 ETH (15:00:47Z) and 3,991.097 ETH (15:04:23Z) to Safe 0x137f31b2...f488; 8.903 ETH of the 4,001 received was not traced further. "
                          "The bot returned 4,001 ETH against 3,996.09 ETH taken, i.e. more than it took."),
        "bounty_kept_eth": None,
        "bounty_desc": "A $500,000 bounty is reported by press quoting Ronin (Bleeping Computer, Cointelegraph); no on-chain bounty payment was found, so none is recorded.",
        "kept_by_bot_eth": 0.0,
        "returned_txs": [
            {"tx": test1["hash"], "eth": 1.0, "note": "bot contract -> 0xc6aec68d (test return)", "block": int(test1["blockNumber"]), "time_utc": iso(test1["timeStamp"])},
            {"tx": main1["hash"], "eth": 4000.0, "note": "bot contract withdrawTo 4,000 ETH -> 0xc6aec68d", "block": int(main1["blockNumber"]), "time_utc": iso(main1["timeStamp"])},
            {"tx": s1a["hash"], "eth": 1.0, "note": "0xc6aec68d -> Safe 0x137f31b2 (test)", "block": int(s1a["blockNumber"]), "time_utc": iso(s1a["timeStamp"])},
            {"tx": s1b["hash"], "eth": int(s1b["value"]) / E18, "note": "0xc6aec68d -> Safe 0x137f31b2", "block": int(s1b["blockNumber"]), "time_utc": iso(s1b["timeStamp"])},
        ],
        "public_statement": "Ronin (via Bleeping Computer, saved page): the white hats 'have fully returned the stolen funds' and will receive a $500,000 bounty. On-chain text from 0x01bf1d7c to this EOA at %s: '%s'" % (iso(msg1["timeStamp"]), txt1),
    },
    "raw_refs": refs1, "rawref_gaps": [
        {"field": "fate.returned_by_builder_eth", "why": "builders did not return anything; no builder -> victim flow exists in this incident (null, not 0)"},
        {"field": "loot.builder_payout_to_victim_eth", "why": "not applicable: no builder pass-through to the protocol"}],
    "discrepancies": ["The bot's 4,001 ETH first-hop return is larger than its 3,996.09375 ETH take; 8.903 ETH stayed at 0xc6aec68d (4,001 received - 3,992.097 forwarded) and is not traced further."],
    "evidence_notes": [
        "Calldata diff (recomputed here from trace_%s.json inner submitWithdrawal call vs tx_%s.json input): only words 2 (recipient) and 10 (quantity) differ, 74 of 76 words identical; the user's quantity 0.35e18 becomes 3,996.09375e18." % (BOT1, USER1),
        "The copy is at position 0 of block 20468679 (09:37:23Z); the user's own tx first seen 09:37:22.400, max fee 2.0 gwei < base fee %.4f gwei, landed 20468888 idx 144 status 0 (reverted after the 10:15:23 pause)." % r1["block"]["base_fee_gwei"],
        "Bridge logs of all Withdrew events between the upgrade and the pause show only these three copies plus 6 small ordinary withdrawals (incidents/ronin-2024/incident.json other_racers; data/raw/etherscan/p2_ronin_bridge_alllogs_20468438_20475000.json).",
        "Governance upgrade tx 0x855dd3b1... at block 20468438 idx 127 is the enabling event (incidents/ronin-2024/incident.json attacker.enabler_tx; data/raw/etherscan/p2_ronin_upgraded_logs_etherscan.json)."],
    "incident_dir": D,
})

# ================= Row 2: racer 3 =================
BOT2 = "0x77bb83dd9b25a0af12c0092993ddf1a2f54b77fbcd1dbf1bf33a965ec707268b"
BRIBE2 = "0x72a4daca1f06caf585f45482bbef2a97701525b59ea96f06494796f00b084ea6"
USER2 = "0x56439cf9427a9188d12b35ef4c8b80fc94a8a1dd205789999c000d8035f27afe"
r2, t2, a2, (ub2, ui2, us2), ut2 = base_row("racer3", None, BOT2, 20468790, USER2, None, None)
assert t2["index"] == 0 and (ub2, ui2, us2) == (20468790, 258, 0)
bot2_eoa, bot2_ct = "0x00001b0bcca9bc88774000692def9dd6452afb9f", "0x02f3d3912f8bd97c4791970aa4cf96dedd05772c"
assert t2["from"] == bot2_eoa and t2["to"] == bot2_ct
tb2 = txs[BRIBE2][1]
assert tb2["index"] == 1 and tb2["from"] == bot2_eoa and tb2["to"] == bot2_eoa
R3I = "p2_ronin_racer3_eoa_txlistinternal_20468000_20472000.json"
take2 = next(x for x in elist(R3I) if x["hash"] == BOT2)
gross2 = int(take2["value"]) / E18
bridge_i = next(x for x in elist("p2_ronin_bridge_txlistinternal_20468300_20470500.json") if x["hash"] == BOT2)
assert bridge_i["from"].lower() == BRIDGE and bridge_i["to"].lower() == bot2_ct and int(bridge_i["value"]) == int(take2["value"])
pf2 = int(t2["priority_fee_total_wei"]) / E18
bribe2 = int(tb2["priority_fee_total_wei"]) / E18
assert abs(bribe2 - 2.175036666911094) < 1e-12 and t2["coinbase_transfer_wei"] == "0"
diff2, nw2 = calldata_diff(BOT2, USER2)
assert diff2 == [2] and nw2 == 67
seen2 = races[20468790]["mempool"]["txs"][USER2]
assert seen2["first_seen_ms"] == 1722938411284 and seen2["seen_before_block_ms"] == -284
assert no_refund(20468790, [bot2_eoa, bot2_ct])
pay2 = txs["0x8306cb9b9ed89788b73f54855eb18a00f5daa60e2512be16d4bc4a358144b5d3"][1]
msg2, txt2 = message("p2_ronin_racer3_eoa_txlist_20468000_20472000.json", "0x9a52f1d4")
# racer 3 EOA balance flows: confirm no onward return of the take in the saved lists (EOA txlist + internal)
big_out = [x for x in elist("p2_ronin_racer3_eoa_txlist_20468000_20472000.json") if x["from"].lower() == bot2_eoa and x["to"].lower() not in (bot2_eoa, bot2_ct) and int(x["value"]) > 0]
assert not big_out
net2 = gross2 - pf2 - bribe2
refs2 = {
    "bot.block": RPC + "block_20468790.json", "bot.position": RPC + "block_20468790.json",
    "attacker_block": [RPC + f"rcpt_{USER2}.json", RPC + f"tx_{USER2}.json"],
    "loot.gross_loot_eth": [ES + R3I, ES + "p2_ronin_bridge_txlistinternal_20468300_20470500.json"],
    "loot.coinbase_paid_eth": [RPC + "trace_block_20468790.json", RPC + f"trace_{BOT2}.json"],
    "loot.priority_fee_paid_eth": [RPC + "receipts_20468790.json", RPC + "block_20468790.json"],
    "loot.builder_refund_to_bot_eth": [RPC + "block_20468790.json", RPC + "trace_block_20468790.json"],
    "loot.bot_net_eth": [ES + R3I, RPC + "receipts_20468790.json", RPC + "block_20468790.json"],
    "loot.captured_usd": [PRICES, ES + R3I],
}
a2["auction_note"] = (
    "The winning block hash and bid cannot be identified (the delivering relay, Titan's, keeps no 2024 history), so the winner/runner-up fields are null; %d bids from %d builders were seen on the Flashbots relay, highest %.4f ETH. "
    "Block builder: Titan (extraData 'Titan (titanbuilder.xyz)'), fee recipient 0x4838b106; builder -> proposer payment tx %s (idx 280) = %.6f ETH. "
    "The racer paid the builder through a second tx in its bundle (idx 1, %s): a 19.29 ETH self-transfer with gas price ~103,573 gwei x 21,000 gas = %.6f ETH of priority fee, 90%% of the 2.4173 ETH taken."
) % (a2["n_bids"], a2["n_builders"], a2["max_bid_eth"], pay2["hash"], int(pay2["value_wei"]) / E18, BRIBE2, bribe2)
rows.append({
    "slug": SLUG, "sub": "racer3", "name": "Ronin Bridge (Ethereum side) 2024-08-06 - racer 3: 2.4173 ETH, a user's own withdrawal redirected",
    "date_utc": r2["block"]["timestamp_utc"].replace("+00:00", "Z"), "chain": "ethereum", "orig_verdict": inc["verdict"],
    "race_type_proposed": "beat-whitehat-or-user",
    "race_type_reason": ("A third searcher copied a legitimate user's pending 2.4173 WETH withdrawal (id 166632), changing one calldata word (recipient) of 67, and placed the copy at position 0 of the block that also contains the user's own tx (idx 258, reverted). "
                         "No hostile attacker; the bridge accepted the rewritten receipt because of the governance upgrade."),
    "one_liner": "Racer 3 copied a user's pending 2.4173 ETH Ronin bridge withdrawal, changing only the recipient, and landed first in the same block (user's own tx reverted at idx 258); no return of the take was found.",
    "attacker": {"eoa": None, "eoas": [], "contracts": [], "funding": "n/a", "funding_tx": None, "deploy_tx": None, "deploy_block": None,
                 "attack_txs": [{"hash": USER2, "block": ub2, "index": ui2, "status": "reverted",
                                 "role": "legitimate user withdrawal id 166632 by 0xfbbf14ea (2.4173 WETH) that racer 3 copied; reverted in the same block behind the copy"}],
                 "none_reason": "No hostile attacker: the 'original' is a user's legitimate pending withdrawal; the enabling event is the governance upgrade tx 0x855dd3b1... (block 20468438, 08:48:47Z) that left the bridge accepting rewritten receipts."},
    "bot": {"label": "racer 3 (vanity EOA 0x00001b0b)", "eoa": bot2_eoa, "contract": bot2_ct, "tx": BOT2, "block": 20468790, "position": t2["index"], "status": "success", "priority_fee_gwei": t2["priority_fee_gwei"]},
    "bots_other": [],
    "evidence_level_mempool": "measured",
    "mempool_note": "The user's tx is in the archive (four sources, first 10:00:11.284) but 284 ms AFTER the block's slot start, although the user's own tx is included in that block at idx 258: the archive's sources saw it later than the racer did, so the archived first-seen time is not a usable pre-inclusion trigger. The racer's own tx is not in the archive.",
    "trigger": {"kind": "user-tx", "tx": USER2, "first_seen_utc_ms": None, "first_seen_utc": None, "sources": SRC4,
                "note": "Archive first-seen of the user tx is 1722938411284 (10:00:11.284Z), 284 ms after the bot block's slot start (seen_before_block_ms = -284), so it is not a pre-inclusion trigger and is left null here; the racer evidently saw the tx earlier than the four archive sources."},
    "attacker_block": ub2,
    "attacker_block_note": "Same block as the bot: the user's own withdrawal landed at idx 258 behind the copy at idx 0 and reverted (the receipt id was already used).",
    "attacker_reference": {"kind": "attack-tx", "block": ub2, "tx": USER2},
    "auction": a2,
    "loot": {
        "scope": "bot-tx", "gross_loot_eth": gross2, "gross_loot_method": "internal ETH transfer bridge proxy -> racer contract inside the bot tx (bridge txlistinternal), forwarded to the racer EOA in the same tx",
        "captured_native": {"amount": gross2, "unit": "ETH", "desc": "the user's own withdrawal amount (quantity NOT inflated), redirected to the racer contract"},
        "captured_usd": round(gross2 * ETHUSD, 2), "captured_usd_source": "gross ETH x DefiLlama ETH $%s at 09:37:23 (%s)" % (ETHUSD, PRICES),
        "coinbase_paid_eth": 0.0, "priority_fee_paid_eth": pf2 + bribe2, "builder_refund_to_bot_eth": 0.0, "builder_payout_to_victim_eth": None,
        "bot_net_eth": net2,
        "loot_note": "Scope: the bot tx plus its companion payment tx in the same bundle (idx 1). No coinbase transfer; priority_fee_paid_eth = %.6f (copy tx at 0.9016 gwei) + %.6f (idx 1, gas price ~103,573 gwei x 21,000 gas) = %.6f ETH, paid to the Titan builder. bot_net = gross - priority fees, before gas base fee. No builder -> bot refund in the block." % (pf2, bribe2, pf2 + bribe2),
    },
    "fate": {
        "return_status": "none-found", "returned_by_bot_eth": None, "returned_by_builder_eth": None, "returned_total_eth": None,
        "returned_to": None,
        "returned_desc": ("No return of the 2.4173 ETH was found in the saved Etherscan lists of the racer EOA and contract through 2024-08-06 22:00 (the take was forwarded to the EOA in the same tx; the EOA kept trading). "
                          "Ronin sent this EOA the same on-chain text as the other two at %s ('%s'). Unknown != none: later activity was not traced." % (iso(msg2["timeStamp"]), txt2)),
        "bounty_kept_eth": None, "bounty_desc": None, "kept_by_bot_eth": None,
        "returned_txs": [], "public_statement": None,
    },
    "raw_refs": refs2, "rawref_gaps": [
        {"field": "trigger.first_seen_utc_ms", "why": "archive first-seen (10:00:11.284) is after the bot block's slot start, so not a pre-inclusion trigger; left null on purpose"},
        {"field": "auction.winning_bid_eth", "why": "delivering relay (Titan) holds no 2024 history; winner not identifiable"},
        {"field": "fate.returned_total_eth", "why": "no return found in saved lists; later activity not traced"}],
    "discrepancies": [],
    "evidence_notes": [
        "Calldata diff (recomputed from trace_%s.json inner submitWithdrawal call vs tx_%s.json input): only word 2 (recipient) differs, 66 of 67 words identical; the quantity is the user's own." % (BOT2, USER2),
        "Block 20468790 (Titan builder): copy at idx 0 (priority fee = the user's 0.9016 gwei tip), bribe tx at idx 1, user's own tx at idx 258 reverted (data/raw/rpc/receipts_20468790.json).",
        "Bridge logs show no further copier between the upgrade and the pause (data/raw/etherscan/p2_ronin_bridge_alllogs_20468438_20475000.json)."],
    "incident_dir": D,
})

# ================= Row 3: Yoink USDC =================
BOT3 = "0xbce5b8548db486c561948e8a177c8ccaa72810f972cee3909ea50af015a60ad8"
USER3 = "0xb7c3f85abd0b9ede7b64868eeb6778ea4731adb1d49f8640b7e7234e470e96c1"
REFUND3 = "0x43354f3f541e2df3d600b54670fd8e38f28f0850f517b53e5b7d222c34c89bb2"
r3, t3, a3, (ub3, ui3, us3), ut3 = base_row("yoink-usdc", None, BOT3, 20468848, USER3, None, None)
assert t3["index"] == 1 and (ub3, ui3, us3) == (20468849, 112, 0)
yoink_eoa, yoink_ct = "0xfde0d1575ed8e06fbf36256bcdfa1f359281455a", "0x6980a47bee930a4584b09ee79ebe46484fbdbdd0"
assert t3["from"] == yoink_eoa and t3["to"] == yoink_ct
usdc_in = next(x for x in elist("p2_ronin_bridge_tokentx_20468300_20470500.json") if x["hash"] == BOT3)
usdc_amt = int(usdc_in["value"]) / 10 ** int(usdc_in["tokenDecimal"])
assert usdc_amt == 1998046.875 and usdc_in["to"].lower() == yoink_ct and usdc_in["tokenSymbol"] == "USDC"
YB = "p2_ronin_yoink_bot_txlistinternal_20468848_20472000.json"
sw = next(x for x in elist(YB) if x["hash"] == BOT3 and x["from"].lower() == "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2" and x["to"].lower() == yoink_ct)
gross3 = int(sw["value"]) / E18      # WETH.withdraw proceeds of the USDC -> WETH swap inside the tx
cb3_tr = next(x for x in elist(YB) if x["hash"] == BOT3 and x["from"].lower() == yoink_ct and x["to"].lower() == "0x229b8325bb9ac04602898b7e8989998710235d5f")
cb3 = int(t3["coinbase_transfer_wei"]) / E18
assert int(cb3_tr["value"]) == int(t3["coinbase_transfer_wei"]) and abs(gross3 - 796.4114523868589) < 1e-12
rf = txs[REFUND3][1]
assert rf["index"] == 22 and rf["from"] == "0x229b8325bb9ac04602898b7e8989998710235d5f" and rf["to"] == yoink_ct and txs[REFUND3][0] == 20468848
refund3 = int(rf["value_wei"]) / E18
bot_cb_block = sum(int(t["coinbase_transfer_wei"]) for t in r3["txs"] if t["from"] == yoink_eoa) / E18
n_bot_txs = sum(1 for t in r3["txs"] if t["from"] == yoink_eoa)
assert abs(refund3 - 791.742284675237) < 1e-9 and n_bot_txs == 21
assert abs((bot_cb_block - refund3) - a3["winning_bid_eth"]) < 1e-4, (bot_cb_block, refund3, a3["winning_bid_eth"])
diff3, nw3 = calldata_diff(BOT3, USER3)
assert diff3 == [2, 5, 10] and nw3 == 61
seen3 = races[20468848]["mempool"]["txs"][USER3]
assert seen3["first_seen_ms"] == 1722939100233
rel3 = seen3["first_seen_ms"] - a3["slot_start_utc_ms"]
assert rel3 == -6767
prio3 = 0.0
net3 = gross3 - cb3 + refund3
usd3 = usdc_amt * USDCUSD
w800 = efind("p2_ronin_yoink_dest_796f_txlistinternal_20468000_20490000.json", "0x8369cdc42b86")
assert w800["from"].lower() == yoink_ct and w800["to"].lower().startswith("0x796f09c9") and int(w800["value"]) == 800 * E18 and iso(w800["timeStamp"]) == "2024-08-06T10:29:11Z"
f792 = efind("p2_ronin_yoink_dest_796f_txlist_20468000_20490000.json", "0x21df45bd48f1")
assert f792["to"].lower() == SAFE and f792["from"].lower().startswith("0x796f09c9")
ret3_safe = int(f792["value"]) / E18
assert abs(ret3_safe - 792.45569) < 1e-9 and iso(f792["timeStamp"]) == "2024-08-06T17:05:59Z"
msg3, txt3 = message("p2_ronin_yoink_owner_txlist_20468848_20472000.json", "0x8d3b20fb")
bider = [b for b in (bvh.load(f"{D}/race_20468848.json").get("bids") or []) if b["builder_pubkey"].startswith("0x81476ce973")]
first_yb = min(bider, key=lambda b: b["timestamp_ms"])
delay3 = first_yb["timestamp_ms"] - seen3["first_seen_ms"]
assert delay3 == 4138 and abs(first_yb["value_eth"] - 2.8198) < 1e-3
refs3 = {
    "bot.block": RPC + "block_20468848.json", "bot.position": RPC + "block_20468848.json",
    "attacker_block": [RPC + f"rcpt_{USER3}.json", RPC + f"tx_{USER3}.json"],
    "trigger.first_seen_utc_ms": ["data/raw/mempool-dumpster/2024-08-06.csv.zip", "data/raw/mempool-dumpster/2024-08-06_sourcelog.csv.zip"],
    "loot.gross_loot_eth": [ES + YB, RPC + f"trace_{BOT3}.json"],
    "loot.coinbase_paid_eth": [RPC + "trace_block_20468848.json", RPC + f"trace_{BOT3}.json"],
    "loot.priority_fee_paid_eth": [RPC + "receipts_20468848.json", RPC + "block_20468848.json"],
    "loot.builder_refund_to_bot_eth": [RPC + "block_20468848.json", RPC + "trace_block_20468848.json"],
    "loot.bot_net_eth": [ES + YB, RPC + "trace_block_20468848.json"],
    "loot.captured_usd": [PRICES, ES + "p2_ronin_bridge_tokentx_20468300_20470500.json"],
    "fate.returned_by_bot_eth": ES + "p2_ronin_yoink_dest_796f_txlistinternal_20468000_20490000.json",
    "fate.returned_total_eth": ES + "p2_ronin_ronin_137f31_txlist_20470000_20520000.json",
    "fate.kept_by_bot_eth": [ES + "p2_ronin_yoink_dest_796f_txlistinternal_20468000_20490000.json", ES + YB],
}
a3["auction_note"] = (
    "Yoink's own builder ('I can haz block?', two pubkeys 0x81476ce9... and 0xad251e6b...) built the winning block: %d bids, winning bid %.4f ETH = proposer payment tx %s. Its first bid (%.4f ETH, 23 txs) came %d ms after the user's tx was first seen, then 5.8531, 8.1001 and the winning 11.043 ETH (-1828 ms rel. slot). "
    "The best competing non-Yoink bid was %.4f ETH (73 txs). The bot block holds %d Yoink txs of 24; the bot paid %.6f ETH of coinbase in total and the builder (0x229b8325, same owner per EigenPhi) refunded %.6f ETH in tx %s (idx 22), so the net outlay of the whole block was the %.4f ETH paid to the proposer."
) % (a3["n_bids"], a3["winning_bid_eth"], a3["proposer_payment_tx"], first_yb["value_eth"], delay3, a3["runner_up_other_builder_eth"], n_bot_txs, bot_cb_block, refund3, REFUND3, a3["winning_bid_eth"])
rows.append({
    "slug": SLUG, "sub": "yoink-usdc", "name": "Ronin Bridge (Ethereum side) 2024-08-06 - USDC leg: Yoink takes 1,998,046.875 USDC",
    "date_utc": r3["block"]["timestamp_utc"].replace("+00:00", "Z"), "chain": "ethereum", "orig_verdict": inc["verdict"],
    "race_type_proposed": "beat-whitehat-or-user",
    "race_type_reason": ("Yoink copied a legitimate user's pending 2,640.82 USDC withdrawal (id 166633) with recipient, a second recipient word and quantity changed (3 of 61 calldata words), swapped the 1,998,046.875 USDC to 796.41 ETH inside the same tx, and landed in the block before the user's own tx (which reverted at 20468849). "
                         "No hostile attacker; the bridge accepted the rewritten receipt after the governance upgrade."),
    "one_liner": "Yoink copied a user's pending Ronin bridge USDC withdrawal, inflating it to 1.998M USDC (796 ETH after an in-tx swap) behind an 11 ETH builder bid with a 791.7 ETH builder refund, and returned about 792 ETH to a Safe that day.",
    "attacker": {"eoa": None, "eoas": [], "contracts": [], "funding": "n/a", "funding_tx": None, "deploy_tx": None, "deploy_block": None,
                 "attack_txs": [{"hash": USER3, "block": ub3, "index": ui3, "status": "reverted",
                                 "role": "legitimate user withdrawal id 166633 by 0x5f494a30 (2,640.82 USDC) that Yoink copied; landed one block later and reverted (receipt id already used)"}],
                 "none_reason": "No hostile attacker: the 'original' is a user's legitimate pending withdrawal; the enabling event is the governance upgrade tx 0x855dd3b1... (block 20468438, 08:48:47Z). Yoink's builder wrote the winning block."},
    "bot": {"label": "Yoink", "eoa": yoink_eoa, "contract": yoink_ct, "tx": BOT3, "block": 20468848, "position": t3["index"], "status": "success", "priority_fee_gwei": t3["priority_fee_gwei"]},
    "bots_other": [],
    "evidence_level_mempool": "measured",
    "mempool_note": "The user's pending tx was seen by four mempool-dumpster sources (first 10:11:40.233, 6.767 s before the bot block's slot start); Yoink's own tx is not in the archive (it sat in Yoink's own builder's block).",
    "trigger": {"kind": "user-tx", "tx": USER3, "first_seen_utc_ms": seen3["first_seen_ms"], "first_seen_utc": isoms(seen3["first_seen_ms"]), "sources": SRC4,
                "note": "User withdrawal id 166633 first seen 10:11:40.233Z; Yoink's builder first bid 4,138 ms later (10:11:44.371Z, %.4f ETH) and the winning 11.043 ETH bid was at 10:11:45.172Z." % first_yb["value_eth"]},
    "attacker_block": ub3,
    "attacker_block_note": "Block in which the copied user withdrawal landed and reverted (idx 112), one block (12 s) after the bot's block.",
    "attacker_reference": {"kind": "attack-tx", "block": ub3, "tx": USER3},
    "auction": a3,
    "loot": {
        "scope": "bot-tx", "gross_loot_eth": gross3,
        "gross_loot_method": "ETH-equivalent of the 1,998,046.875 USDC taken: WETH.withdraw proceeds (796.4115 WETH) of the USDC -> WETH swap on the pool 0x88e6a0c2 inside the bot tx (txlistinternal + tokentx)",
        "captured_native": {"amount": usdc_amt, "unit": "USDC", "desc": "USDC paid by the bridge proxy to the Yoink contract (user's request was 2,640.820595 USDC)"},
        "captured_usd": round(usd3, 2), "captured_usd_source": "USDC x DefiLlama USDC $%.6f at 09:37:23 (%s)" % (USDCUSD, PRICES),
        "coinbase_paid_eth": cb3, "priority_fee_paid_eth": prio3, "builder_refund_to_bot_eth": refund3, "builder_payout_to_victim_eth": None,
        "bot_net_eth": net3,
        "loot_note": ("Scope: the bot tx only. Coinbase transfer %.6f ETH to Yoink's own builder 0x229b8325; the builder refunded %.6f ETH to the bot in tx %s (idx 22). "
                      "The refund reimburses ALL 21 Yoink txs in this 24-tx block (their coinbase transfers total %.6f ETH; coinbase total - refund = %.6f ETH ~ the proposer payment). bot_net = gross - coinbase + refund = %.4f ETH attributes the whole refund to this tx; "
                      "attributing the block's whole net outlay (the %.4f ETH proposer payment) to it instead would give %.4f ETH. Before gas base fee and before the later return.")
                     % (cb3, refund3, REFUND3, bot_cb_block, bot_cb_block - refund3, net3, a3["winning_bid_eth"], gross3 - a3["winning_bid_eth"]),
    },
    "fate": {
        "return_status": "returned", "returned_by_bot_eth": 800.0, "returned_by_builder_eth": None, "returned_total_eth": ret3_safe,
        "returned_to": "Yoink bot contract -> 0x796f09c9... (800 ETH) -> Safe 0x137f31b2...f488 (792.45569 ETH); the Safe's Ronin ownership is inferred from the flow, not from a public tag",
        "returned_desc": ("The bot contract's withdrawTo sent 800 ETH to 0x796f09c9... at 10:29:11Z (block 20468935, 17 min after landing, 24 min before Ronin's first on-chain message at 10:53:35Z); 0x796f09c9 forwarded 792.45569 ETH to Safe 0x137f31b2...f488 at 17:05:59Z; 7.5443 ETH stayed at 0x796f09c9 with no onward tx through block 20490000. "
                          "The 800 ETH is the bot contract's total withdrawal, larger than this tx's net (the contract also holds proceeds of other txs). The take was in USDC, returned as ETH; the Safe later swapped 785 ETH back to 1,954,372 USDC (inferred as Ronin restoring the USDC leg)."),
        "bounty_kept_eth": None,
        "bounty_desc": "A $500,000 bounty is reported by press (EigenPhi: Yoink and the other white hat 'shared $500K'); no on-chain bounty payment was found, so none is recorded.",
        "kept_by_bot_eth": 0.0,
        "returned_txs": [
            {"tx": w800["hash"], "eth": 800.0, "note": "Yoink bot contract withdrawTo -> 0x796f09c9", "block": int(w800["blockNumber"]), "time_utc": iso(w800["timeStamp"])},
            {"tx": f792["hash"], "eth": ret3_safe, "note": "0x796f09c9 -> Safe 0x137f31b2", "block": int(f792["blockNumber"]), "time_utc": iso(f792["timeStamp"])},
        ],
        "public_statement": "Ronin on-chain text from 0x01bf1d7c to the Yoink owner at %s: '%s'. Ronin (via Bleeping Computer, saved page): the white hats 'have fully returned the stolen funds' with a $500,000 bounty." % (iso(msg3["timeStamp"]), txt3),
    },
    "raw_refs": refs3, "rawref_gaps": [
        {"field": "fate.returned_by_builder_eth", "why": "builder (Yoink's own) refunded the bot, not the victim; no builder -> protocol flow (null, not 0)"},
        {"field": "loot.builder_payout_to_victim_eth", "why": "not applicable"}],
    "discrepancies": [
        "incident.json loot 'coinbase_paid_eth' 795.615040934472 matches; the refund 791.742284675237 reimburses the whole block (21 Yoink txs, coinbase total %.6f ETH), not only this tx." % bot_cb_block,
        "Yoink's 800 ETH withdrawal is larger than this tx's net %.4f ETH; it also covers other proceeds of the contract." % net3],
    "evidence_notes": [
        "Calldata diff (recomputed from trace_%s.json inner submitWithdrawal call vs tx_%s.json input): words 2 and 5 (both recipient slots) and 10 (quantity) differ, 58 of 61 words identical; quantity 2,640.820595 USDC becomes 1,998,046.875 USDC." % (BOT3, USER3),
        "Block 20468848 (24 txs, Yoink's builder 'I can haz block?'): Yoink copy at idx 1, builder refund at idx 22, builder -> proposer 11.043 ETH at idx 23; the user's own tx lands in 20468849 idx 112 status 0 (data/raw/rpc/receipts_20468849.json).",
        "Yoink's builder first bid %d ms after the user tx was first seen (data/raw/relay-flashbots/bids_block20468848.json via incidents/ronin-2024/race_20468848.json)." % delay3,
        "The research/defiplaza-ronin/ronin_copies_diff.json and research/bot-re/fork_replay_results.json files cited in incident.json are not data/raw; the diffs above were recomputed from data/raw/rpc traces and tx inputs."],
    "incident_dir": D,
})

# ---- check refs, write
for row in rows:
    miss = [p for v in row["raw_refs"].values() for p in (v if isinstance(v, list) else [v]) if not (ROOT / p).exists()]
    assert not miss, (row["sub"], miss)
out = ROOT / "data" / "extract" / f"{SLUG}.json"
json.dump(rows, open(out, "w"), indent=1)
print("wrote", out, len(rows), "rows")
