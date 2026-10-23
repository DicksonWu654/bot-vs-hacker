"""incident dataset extraction for saddle-2022 -> data/extract/saddle-2022.json (one row).
Run from the project root:  .venv/bin/python scripts/dataset/extract_saddle-2022.py
Every number is read from saved files under data/raw/ (rpc block/receipt/trace, etherscan tokentx/txlist/logs) or from the
race files built from them; the incident.json values are only used to cross-check (discrepancies list).
Pre-Merge incident: in-block evidence only, no relay bids."""
import datetime as dt
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import bvh  # noqa: E402

SLUG = "saddle-2022"
D = f"incidents/{SLUG}"
inc = bvh.load(f"{D}/incident.json")
WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

A1 = "0x2b023d65485c4bb68d781960c2196588d03b871dc9eb1c054f596b7ca6f7da56"
A2 = "0xd9bc83688e8eddde39bd9073c363665b1419d475dd4498e81b52cce41d7c76b3"
A3 = "0xe7e0474793aad11875c131ebd7582c8b73499dd3c5a473b59e6762d4e373d7b8"
R_DEPLOY = "0xf1bc1ab21d717af71801633716f6866330333f5c091b1ed63eddf78325d433ee"
R_CALL = "0x9549c0cb48ec5a5a2c4703cbbbbea5638028b2d8c8adc103220ef1c7fe5e99a3"
R_RETURN = "0x22efe4743cdbd6650e745e3e6ef4f611aa316e81b5b88d5413b0cd19205ab060"
EOA_ATT = "0x63341ba917de90498f3903b199df5699b4a55ac0"
EOA_BOT = "0x811929c3c17dd598172f8078a48540fa23f44b05"
CONTRACT_BOT = "0x0462bee210c7ade1ebb095e5680d61561d86e7b1"

discrepancies = []
rawref_gaps = []


def rcpt(h):
    for pre in ("receipt_", "rcpt_"):
        p = f"data/raw/rpc/{pre}{h}.json"
        if bvh.exists(p):
            j = bvh.load(p)
            return j.get("result", j), p
    raise FileNotFoundError(h)


def trace(h):
    p = f"data/raw/rpc/trace_{h}.json"
    j = bvh.load(p)
    return j.get("result", j), p


def frames(c, out):
    out.append(c)
    for s in c.get("calls") or []:
        frames(s, out)
    return out


def weth_transfers(r):
    out = []
    for l in r["logs"]:
        if l["address"].lower() == WETH and l["topics"][0] == TRANSFER:
            out.append(("0x" + l["topics"][1][-40:], "0x" + l["topics"][2][-40:], int(l["data"], 16) / 1e18))
    return out


def prio_eth(r, blk):
    base = int(bvh.load(f"data/raw/rpc/block_{blk}.json")["result"]["baseFeePerGas"], 16)
    return (int(r["effectiveGasPrice"], 16) - base) * int(r["gasUsed"], 16) / 1e18


def iso(ts):
    return dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---- race file of the bot's block --------------------------------------------------------------------------------
race_path = f"{D}/race_14684434.json"
race = bvh.load(race_path)
blk = race["block"]
by_hash = {t["hash"]: t for t in race["txs"]}
t_call, t_dep = by_hash[R_CALL], by_hash[R_DEPLOY]
assert t_call["index"] == 1 and t_dep["index"] == 0 and t_call["from"] == EOA_BOT
assert t_call["status"] == 1 and t_dep["status"] == 1

# receipts / traces of the four swap-loop txs
rc = {}
for k, h in (("A1", A1), ("A2", A2), ("A3", A3), ("R", R_CALL), ("RD", R_DEPLOY)):
    rc[k] = rcpt(h)
tr = {}
for k, h in (("A1", A1), ("A2", A2), ("A3", A3), ("R", R_CALL)):
    tr[k] = trace(h)

# verify the race-file numbers against the raw receipts / block base fee
prio_call = prio_eth(rc["R"][0], 14684434)
prio_dep = prio_eth(rc["RD"][0], 14684434)
assert abs(prio_call - int(t_call["priority_fee_total_wei"]) / 1e18) < 1e-12, (prio_call, t_call["priority_fee_total_wei"])
assert abs(prio_dep - int(t_dep["priority_fee_total_wei"]) / 1e18) < 1e-12
assert int(t_call["coinbase_transfer_wei"]) == 0 and int(t_dep["coinbase_transfer_wei"]) == 0
prio_total = prio_call + prio_dep

# rescue loot: WETH out of the pool-side holder into the rescue contract, then onto the whitehat EOA
wt = weth_transfers(rc["R"][0])
rescue_weth = wt[-1][2]
assert wt[-1][1] == EOA_BOT and wt[-1][0] == CONTRACT_BOT
tokentx = bvh.load("data/raw/etherscan/saddle_rescue_tokentx.json")["result"]
tt_in = [t for t in tokentx if t["hash"] == R_CALL][0]
tt_out = [t for t in tokentx if t["hash"] == R_RETURN][0]
dec = 10 ** int(tt_in["tokenDecimal"])
assert int(tt_in["value"]) == int(tt_out["value"]), "rescue amount != returned amount"
assert abs(int(tt_in["value"]) / dec - rescue_weth) < 1e-9
returned = int(tt_out["value"]) / dec
ret_block = int(tt_out["blockNumber"])
ret_time = iso(tt_out["timeStamp"])
ret_to = tt_out["to"]
ret_tx_json = bvh.load(f"data/raw/rpc/tx_{R_RETURN}.json")["result"]
assert int(ret_tx_json["blockNumber"], 16) == ret_block and int(ret_tx_json["transactionIndex"], 16) == int(tt_out["transactionIndex"])
# the return tx: WETH.transfer(0xd186540f..., amount) from the whitehat EOA
assert ret_tx_json["to"].lower() == WETH and ret_tx_json["from"].lower() == EOA_BOT
# Is the recipient Saddle's pool owner? (saved eth_call owner() at the rescue block)
owner_raw = None
for p in pathlib.Path(ROOT / "data/raw/rpc").glob("saddle_pool_owner_*"):
    owner_raw = (str(p.relative_to(ROOT)), bvh.load(p)["result"])
owner_addr = ("0x" + owner_raw[1][-40:]) if owner_raw else None

# attacker's three swap-loop attempts
att = []
for k, h, role in (("A1", A1, "attempt 1: swap loop, succeeded"), ("A2", A2, "attempt 2: swap loop, reverted (out of gas on the final WETH transfer)"),
                   ("A3", A3, "attempt 3: swap loop re-sized to the remaining pool, succeeded")):
    r, rp = rc[k]
    tx = {"hash": h, "block": int(r["blockNumber"], 16), "index": int(r["transactionIndex"], 16),
          "status": "success" if r["status"] == "0x1" else "reverted", "role": role}
    fr = frames(tr[k][0], [])
    wtr = [f for f in fr if f["input"][:10] == "0xa9059cbb" and f["to"].lower() == WETH]
    last = wtr[-1]
    tx["weth_final_transfer_eth"] = int(last["input"][74:138], 16) / 1e18  # attempted / executed
    tx["weth_final_transfer_error"] = last.get("error")
    tx["weth_received_by_attacker_eth"] = sum(a for f, to, a in weth_transfers(r) if to == EOA_ATT)
    tx["gas_used"] = int(r["gasUsed"], 16)
    att.append(tx)
a1, a2, a3 = att
assert a1["block"] == 14684307 and a1["index"] == 212 and a2["block"] == 14684432 and a2["index"] == 202 and a3["block"] == 14684518
assert a2["status"] == "reverted" and a2["weth_received_by_attacker_eth"] == 0

# compare the rescue's swap loop with the attacker's attempts (argument words 0-3 = token in/out, dx, minDy; word 4 is a deadline)
def swaps(k):
    return [f["input"][10:10 + 64 * 4] for f in frames(tr[k][0], []) if f["input"][:10] == "0x91695586"]
sr = swaps("R")
cmp = {k: sum(1 for x, y in zip(sr, swaps(k)) if x == y) for k in ("A1", "A2", "A3")}
n_frames = {k: len(frames(tr[k][0], [])) for k in tr}
assert cmp["A2"] == len(sr) == 9 and cmp["A1"] == 0 and cmp["A3"] == 0, cmp
assert set(n_frames.values()) == {403}

# no other tx emitted the swap-loop event (topic 0xc6c1e063...) on the metapool, Etherscan logs 14684000-14686500
logs = bvh.load("data/raw/etherscan/saddle_pool_logs_es.json")["result"]
loop_txs = sorted({(int(l["blockNumber"], 16), l["transactionHash"]) for l in logs if l["topics"][0].startswith("0xc6c1e063")})
assert [h for b, h in loop_txs] == [A1, R_CALL, A3], loop_txs

# deploy facts
att_deploys = {"attack1": (14684300, 157), "attack2": (14684421, 218), "attack3": (14684510, 170)}
funding = inc["attacker"]["funding_tx"]

# discrepancies against incident.json
inc_prio = inc["bots"][0]["priority_fee_gwei"]
if abs(inc_prio - t_call["priority_fee_gwei"]) > 0.01:
    discrepancies.append(f"incident.json priority 179.6 gwei vs race file {t_call['priority_fee_gwei']}")
if abs(inc["bots"][0]["captured"]["amount"] - rescue_weth) > 1e-9:
    discrepancies.append("incident.json captured amount differs from receipt transfer")
discrepancies.append(
    "incident.json says the 'attacker's next attempt' (attempt 3, block 14684518) was NOT pending at 14684434; confirmed: its contract "
    "(0x797418a5) was deployed in block 14684510 (idx 170), 76 blocks after the rescue. No attacker tx is evidenced as pending at 14684434.")
discrepancies.append(
    f"Attempt 2 tried to send {a2['weth_final_transfer_eth']:.6f} WETH; the rescue moved {rescue_weth:.6f} WETH (difference "
    f"{rescue_weth - a2['weth_final_transfer_eth']:.6f} WETH, pool state moved between the blocks; not investigated further).")
discrepancies.append(
    "REKT lists 0xe7e04747 (14684518, success) as the 'second hack tx'; it is attacker attempt 3. The failed second attempt is 0xd9bc8368 (14684432).")

raw = bvh.RawRefs()
rp_ = lambda k: rc[k][1]
raw.add("bot.block", f"data/raw/rpc/block_14684434.json")
raw["bot.position"] = [rp_("R"), "data/raw/rpc/block_14684434.json"]
raw["attacker_block"] = [rp_("A2"), f"data/raw/rpc/block_14684432.json"]
cost_refs = [rp_("R"), rp_("RD"), "data/raw/rpc/block_14684434.json"]
raw["loot.gross_loot_eth"] = [rp_("R"), "data/raw/etherscan/saddle_rescue_tokentx.json"]
raw["loot.coinbase_paid_eth"] = ["data/raw/rpc/trace_block_14684434.json"]
raw["loot.priority_fee_paid_eth"] = cost_refs
raw["loot.bot_net_eth"] = cost_refs + ["data/raw/etherscan/saddle_rescue_tokentx.json"]
fate_refs = ["data/raw/etherscan/saddle_rescue_tokentx.json", f"data/raw/rpc/tx_{R_RETURN}.json"]
raw["fate.returned_by_bot_eth"] = fate_refs
raw["fate.returned_total_eth"] = fate_refs
raw["fate.kept_by_bot_eth"] = fate_refs + ["data/raw/etherscan/saddle_rescue_txlist.json"]
raw["fate.bounty_kept_eth"] = fate_refs + ["data/raw/etherscan/saddle_rescue_txlist.json"]
for web in ("blocksec_saddle_rescue", "blocksec_three_cases", "rekt_saddle_rekt2"):
    raw["web:" + web] = f"data/raw/web-saddle/{web}.html"
raw["att.funding_tx"] = funding["raw"]
for k, (b, i) in att_deploys.items():
    pass
raw["attacker.attack_txs.weth_amounts"] = [rp_("A1"), rp_("A2"), rp_("A3"), tr["A2"][1]]
raw["pool_owner_eth_call"] = owner_raw[0] if owner_raw else None
raw["etherscan.metapool_swap_loop_logs"] = "data/raw/etherscan/saddle_pool_logs_es.json"
rawrefs = {k: v for k, v in raw.items() if v}
for m in raw.missing:
    rawref_gaps.append({"field": m["field"], "why": f"missing file {m['path']}"})

# the pool's own owner is a different Safe from the return recipient: say so plainly
recipient_note = (f"recipient {ret_to} is a Gnosis Safe proxy (Etherscan getsourcecode: GnosisSafeProxy) that is NOT the metapool's owner "
                  f"({owner_addr}); BlockSec states in its own words 'We returned all the rescued funds to Saddle Finance' "
                  "(data/raw/web-saddle/blocksec_three_cases.html); on-chain ownership of the recipient Safe was not independently labelled.")

row = {
    "slug": SLUG,
    "name": inc["name"],
    "date_utc": blk["timestamp_utc"].replace("+00:00", "Z"),
    "chain": "ethereum",
    "orig_verdict": inc["verdict"],
    "race_type_proposed": "post-failure-replay",
    "race_type_reason": ("The rescue (block 14684434) came two blocks AFTER the attacker's attempt 2 reverted in 14684432 and replays that "
                         "reverted attempt's exact swap amounts from a different address; no attacker tx is shown to be pending at 14684434 "
                         "(attempt 3's contract was deployed 76 blocks later)."),
    "one_liner": ("BlockSec's whitehat replayed the attacker's reverted second attempt two blocks later (near-identical contract, same "
                  "amounts), swept 1,356.73 WETH the attacker had left behind and returned all of it."),
    "attacker": {
        "eoa": EOA_ATT, "eoas": [EOA_ATT],
        "contracts": [c.split(" ")[0] for c in inc["attacker"]["contracts"]],
        "funding": "tornado", "funding_tx": funding["hash"],
        "deploy_tx": inc["attacker"]["deploy_tx"]["attack2"], "deploy_block": att_deploys["attack2"][0],
        "deploy_note": "deploy of attack contract 2 (the reverted attempt the rescue replays); attack1/attack3 deploys: "
                       + ", ".join(f"{n} {inc['attacker']['deploy_tx'][n]} (block {b}, idx {i})" for n, (b, i) in att_deploys.items() if n != "attack2"),
        "attack_txs": att,
        "attempt_amounts_note": (f"attempt 1 took {a1['weth_received_by_attacker_eth']:.4f} WETH, attempt 3 took "
                                 f"{a3['weth_received_by_attacker_eth']:.4f} WETH (both received by {EOA_ATT}); attempt 2 would have sent "
                                 f"{a2['weth_final_transfer_eth']:.4f} WETH but its last WETH transfer ran out of gas and the tx reverted"),
        "attacker_total_weth_taken": a1["weth_received_by_attacker_eth"] + a3["weth_received_by_attacker_eth"],
        "none_reason": None,
    },
    "bot": {
        "label": "BlockSec whitehat rescue (Phalcon)", "eoa": EOA_BOT, "contract": CONTRACT_BOT, "tx": R_CALL, "block": 14684434,
        "position": 1, "status": "success", "priority_fee_gwei": t_call["priority_fee_gwei"],
        "deploy_tx": R_DEPLOY, "deploy_position": 0,
        "note": "contract deployed at idx 0 and called at idx 1 of the same block, both at 202.53 gwei gas price (179.6 gwei priority), no coinbase transfer",
    },
    "bots_other": [],
    "evidence_level_mempool": "in-block-only",
    "mempool_note": ("Pre-Merge incident (2022-04-30): mempool-dumpster starts 2023-08-07, Flashbots blocks API answers HTTP 410, so in-block "
                     "evidence only; whether the rescue was a public-pool tx or a MEV-geth bundle cannot be told."),
    "trigger": {"kind": None, "tx": None, "first_seen_utc_ms": None, "first_seen_utc": None, "sources": None,
                "note": "no mempool first-seen exists (pre-archive); the trigger BlockSec reports acting on is the already-mined reverted attempt 2 "
                        f"({A2}, block 14684432); BlockSec writes that its system 'spotted the failed transaction' (blocksec_saddle_rescue.html)."},
    "attacker_block": 14684432,
    "attacker_block_note": ("block of the attacker's reverted attempt 2 (idx 202, status 0), whose parameters the rescue replays; the rescue landed 2 blocks / 25 s "
                            "later (bot block - attacker block = +2: the bot is AFTER the attacker). The attacker's attempt 1 (14684307) succeeded earlier "
                            "and attempt 3 (14684518) succeeded 84 blocks after the rescue."),
    "attacker_reference": {"kind": "attack-tx", "block": 14684432, "tx": A2},
    "auction": bvh.auction_summary(race_path, R_CALL),
    "loot": {
        "scope": "bot-tx",
        "gross_loot_eth": rescue_weth,
        "gross_loot_method": "WETH Transfer event pool-side holder -> rescue contract -> whitehat EOA in the rescue call receipt (1 WETH = 1 ETH)",
        "captured_native": {"amount": rescue_weth, "unit": "WETH", "desc": "WETH swept from the sUSDv2 metapool via the replayed swap loop and held by the whitehat EOA"},
        "captured_usd": None, "captured_usd_source": None,
        "coinbase_paid_eth": 0.0,
        "priority_fee_paid_eth": prio_total,
        "builder_refund_to_bot_eth": None, "builder_payout_to_victim_eth": None,
        "bot_net_eth": rescue_weth - prio_total,
        "loot_note": (f"scope = the rescue call only for gross/captured; priority_fee_paid_eth covers BOTH the contract deploy (idx 0, {prio_dep:.6f} ETH) "
                      f"and the rescue call (idx 1, {prio_call:.6f} ETH) paid to the poolin.com fee recipient; bot_net = gross - priority fees "
                      "(base-fee burn excluded) held BEFORE the return. Net is nominal: the whole amount was returned. USD figure not recomputed "
                      "(BlockSec says ~$3.8M)."),
    },
    "fate": {
        "return_status": "returned",
        "returned_by_bot_eth": returned, "returned_by_builder_eth": None, "returned_total_eth": returned,
        "returned_to": ret_to,
        "returned_desc": (f"{returned:.10f} WETH, exactly the swept amount, sent by the whitehat EOA in {R_RETURN} (block {ret_block}, {ret_time}, "
                          f"about 6.6 h after the rescue). {recipient_note}"),
        "bounty_kept_eth": 0.0,
        "bounty_desc": ("no bounty retained: the returned amount equals the swept amount to the wei and no other WETH movement out of the whitehat EOA "
                        "appears in saddle_rescue_tokentx.json; BlockSec bore the ~0.68 ETH gas premium. Any bounty agreed off-chain would not show here."),
        "kept_by_bot_eth": 0.0,
        "returned_txs": [{"tx": R_RETURN, "eth": returned, "note": "WETH transfer to " + ret_to, "block": ret_block, "time_utc": ret_time}],
        "public_statement": "BlockSec: 'We returned all the rescued funds to Saddle Finance.' (blocksec.com 'how-blocksec-rescued-stolen-funds-from-technical-perspectives-of-three-representative-cases', saved)",
    },
    "raw_refs": rawrefs,
    "rawref_gaps": rawref_gaps,
    "discrepancies": discrepancies,
    "evidence_notes": [
        f"Rescue call {R_CALL[:12]} (14684434 idx 1) and all three attacker swap-loop txs have 403 call frames, the same top selector 0xaf8271f7 and 9 metapool swaps; "
        f"the rescue's 9 swaps carry the same (tokenIn, tokenOut, dx, minDy) words as attempt 2 ({cmp['A2']}/9 identical) and none of attempt 1's or 3's ({cmp['A1']}/9, {cmp['A3']}/9) "
        f"(recomputed from data/raw/rpc/trace_<tx>.json).",
        "Attempt 2 (14684432 idx 202) reverted: execution reverted on the final WETH transfer with 'out of gas' (gas used 2,153,653), so its WETH stayed in the pool; the rescue "
        "(2 blocks later, poolin.com block, 202.5 gwei) swept it. Per incident.json the rescue contract's runtime differs from attacker contract 2 in only 20 bytes (not re-diffed here).",
        f"Attacker's own takes: attempt 1 {a1['weth_received_by_attacker_eth']:.4f} WETH (14684307 idx 212), attempt 3 {a3['weth_received_by_attacker_eth']:.4f} WETH (14684518 idx 282); "
        "attempt 3's contract was deployed in 14684510, 76 blocks after the rescue, so nothing of the attacker's was pending at 14684434.",
        "Only three txs on the metapool emitted the swap-loop event (attempt 1, rescue, attempt 3) in Etherscan logs for 14684000-14686500 (data/raw/etherscan/saddle_pool_logs_es.json); "
        "reverted copies leave no logs and were not enumerated.",
        f"Return: {R_RETURN[:12]} at block {ret_block} moves exactly {returned:.10f} WETH out of the whitehat EOA (saddle_rescue_tokentx.json). In-block evidence only, no mempool.",
    ],
    "incident_dir": D,
}

out = ROOT / "data" / "extract" / f"{SLUG}.json"
out.parent.mkdir(parents=True, exist_ok=True)
json.dump([row], open(out, "w"), indent=1, ensure_ascii=False)
print("wrote", out)
