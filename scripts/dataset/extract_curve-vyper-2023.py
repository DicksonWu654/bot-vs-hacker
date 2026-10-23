"""incident dataset extraction for curve-vyper-2023 -> data/extract/curve-vyper-2023.json (FIVE rows, one per sub-race).
Run from the project root:  .venv/bin/python scripts/dataset/extract_curve-vyper-2023.py
Rows (sub): pETH, msETH, CRV-ETH-wave2, alETH, CRV-ETH-wave1.
Every block position / status / priority fee / coinbase transfer / value flow is recomputed here from the saved raw RPC files
(data/raw/rpc/block_<N>.json, receipts_<N>.json, trace_block_<N>.json) and asserted equal to the race files; return transfers come
from the saved Etherscan txlists / tokentx. Pre-Aug-2023: in-block evidence only (no mempool archive).
The two c0ffeebabe.eth rows use the curated transaction-level extracts (block, position, funds and public statements).
"""
import datetime as dt
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import bvh  # noqa: E402

SLUG = "curve-vyper-2023"
D = f"incidents/{SLUG}"
inc = bvh.load(f"{D}/incident.json")
SUBS = {s["id"]: s for s in inc["sub_races"]}
S_PETH, S_MS, S_AL, S_C1, S_C2 = list(SUBS)  # order in incident.json
WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
E_COFFEE = "0xc0ffeebabe5d496b2dde509f9fa189c25cf29671"
POOLSEQ = bvh.load(f"{D}/pool_call_sequences.json")
MEMP_NOTE = ("Pre-Aug-2023 (2023-07-30): mempool-dumpster starts 2023-08-07, so in-block evidence only; no first-seen time for any tx "
             "in this incident. Flashbots-relay bid history exists for the blocks (other relays answered empty).")
NOMEMP_TRIGGER = {"kind": None, "tx": None, "first_seen_utc_ms": None, "first_seen_utc": None, "sources": None,
                  "note": "no mempool archive for 2023-07-30 (starts 2023-08-07); trigger time unknowable"}

discrepancies_all = []


# ---------------------------------------------------------------------------------------------------------------------
# raw helpers
# ---------------------------------------------------------------------------------------------------------------------
_cache = {}


def _j(path):
    if path not in _cache:
        j = bvh.load(path)
        _cache[path] = j.get("result", j) if isinstance(j, dict) and "result" in j else j
    return _cache[path]


def block(n):
    return _j(f"data/raw/rpc/block_{n}.json")


def receipts(n):
    return _j(f"data/raw/rpc/receipts_{n}.json")


def traces(n):
    return _j(f"data/raw/rpc/trace_block_{n}.json")


def frames(c, out=None):
    out = [] if out is None else out
    out.append(c)
    for s in c.get("calls") or []:
        frames(s, out)
    return out


def hx(v):
    return int(v, 16)


def iso(ts):
    return dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def txinfo(n, h):
    """position/status/fees/coinbase of tx h in block n, recomputed from raw block + receipts + block trace."""
    b = block(n)
    idx = [i for i, t in enumerate(b["transactions"]) if t["hash"].lower() == h.lower()]
    assert len(idx) == 1, (n, h)
    i = idx[0]
    t, r = b["transactions"][i], receipts(n)[i]
    assert r["transactionHash"].lower() == h.lower() and hx(r["transactionIndex"]) == i
    base = hx(b["baseFeePerGas"])
    prio_wei = (hx(r["effectiveGasPrice"]) - base) * hx(r["gasUsed"])
    tr = traces(n)[i]
    tr = tr.get("result", tr)
    fr = frames(tr)
    miner = b["miner"].lower()
    cb = sum(hx(f.get("value", "0x0")) for f in fr if (f.get("to") or "").lower() == miner and not f.get("error"))
    inner_err = [f for f in fr[1:] if f.get("error")]
    return {"hash": h.lower(), "block": n, "index": i, "status": "success" if r["status"] == "0x1" else "reverted",
            "from": t["from"].lower(), "to": (t["to"] or "").lower() or None, "gas_used": hx(r["gasUsed"]),
            "priority_fee_gwei": (hx(r["effectiveGasPrice"]) - base) / 1e9, "priority_fee_eth": prio_wei / 1e18,
            "coinbase_eth": cb / 1e18, "n_inner_errors": len(inner_err), "top_error": tr.get("error"),
            "frames": fr, "input": t["input"], "miner": miner, "ts": hx(b["timestamp"])}


def eth_flow(fr, frm, to):
    """sum of native value moved by successful calls frm -> to."""
    return sum(hx(f.get("value", "0x0")) for f in fr
               if (f.get("from") or "").lower() == frm.lower() and (f.get("to") or "").lower() == to.lower() and not f.get("error")) / 1e18


def logs_transfers(n, h, token=None):
    b = block(n)
    i = [k for k, t in enumerate(b["transactions"]) if t["hash"].lower() == h.lower()][0]
    out = []
    for l in receipts(n)[i]["logs"]:
        if l["topics"] and l["topics"][0] == TRANSFER and len(l["topics"]) == 3 and (token is None or l["address"].lower() == token):
            out.append({"token": l["address"].lower(), "from": "0x" + l["topics"][1][-40:], "to": "0x" + l["topics"][2][-40:],
                        "amount": hx(l["data"]) / 1e18})
    return out


def race_tx(race_path, h):
    r = bvh.load(race_path)
    t = [x for x in r["txs"] if x["hash"].lower() == h.lower()]
    assert len(t) == 1
    return r, t[0]


def check_vs_race(info, race_path):
    r, t = race_tx(race_path, info["hash"])
    assert r["block"]["number"] == info["block"] and t["index"] == info["index"], (info["hash"], t["index"], info["index"])
    assert (t["status"] == 1) == (info["status"] == "success")
    assert abs(int(t["priority_fee_total_wei"]) / 1e18 - info["priority_fee_eth"]) < 1e-12, (info["hash"], t["priority_fee_total_wei"], info["priority_fee_eth"])
    assert abs(int(t["coinbase_transfer_wei"]) / 1e18 - info["coinbase_eth"]) < 1e-12, (info["hash"], t["coinbase_transfer_wei"], info["coinbase_eth"])
    assert abs(t["priority_fee_gwei"] - info["priority_fee_gwei"]) < 1e-6


def pub(i):
    """public subset of a txinfo for output"""
    return {k: i[k] for k in ("hash", "block", "index", "status")}


def find_in_lists(paths, h):
    """find a tx hash in saved etherscan list files; return (record, path)."""
    for p in paths:
        if not bvh.exists(p):
            continue
        d = bvh.load(p)
        for t in (d["result"] if isinstance(d, dict) else d):
            if (t.get("hash") or "").lower() == h.lower():
                return t, p
    return None, None


def etherscan_text(rec):
    inp = rec.get("input", "0x")
    if inp in ("0x", "") or len(inp) > 4000:
        return None
    try:
        return bytes.fromhex(inp[2:]).decode("utf8")
    except Exception:  # noqa: BLE001
        return None


def pool_seq(key):
    return [(c["selector"], c["value_eth"], c["args"][0] if c["args"] else None, c["error"] != "") for c in POOLSEQ[key]]


def raw_for_tx(n, extra=()):
    return [f"data/raw/rpc/block_{n}.json", f"data/raw/rpc/receipts_{n}.json", f"data/raw/rpc/trace_block_{n}.json", *extra]


def finish_row(row, refs, rawref_gaps):
    clean = {}
    for k, v in refs.items():
        if v is None:
            continue
        paths = v if isinstance(v, list) else [v]
        paths = [p for p in dict.fromkeys(paths) if p]
        for p in paths:
            if not (ROOT / p).exists():
                rawref_gaps.append({"field": k, "why": f"missing file {p}"})
        clean[k] = paths if len(paths) > 1 else paths[0]
    row["raw_refs"] = clean
    row["rawref_gaps"] = rawref_gaps
    return row


# ---------------------------------------------------------------------------------------------------------------------
# funding facts (verified in saved txlists)
# ---------------------------------------------------------------------------------------------------------------------
def funding(h, lists, expect_from_prefix=None):
    rec, path = find_in_lists(lists, h)
    if rec is None:
        return None, None
    if expect_from_prefix:
        assert rec["from"].lower().startswith(expect_from_prefix.lower()), rec["from"]
    return rec, path


ATT = {
    "peth": dict(eoa="0x172f6fdefeb079e435f22c918a919540f4721e60", contract="0x6a1a7578e36cf0838c77f59d1f029873b8e0ff77",
                 funding_tx="0x56ca0a0cff2ac75906e8ab0ea406fa263fac6a0e68e0ddef521bfe04b35eed64",
                 lists=["data/raw/etherscan/txlistinternal_0x172f6fde_0_17806100.json", "data/raw/etherscan/txlist_0x172f6fde_0_17830000.json"],
                 pref="0x12d66f87"),
    "adapter": dict(eoa="0x19c7849d10333188678fad560d2436cec11071a6",
                    funding_tx="0x5fbd45fddec6d8705bf78e4f364b2d7b90f7fa63d7bf471f0004c2830f1cccbc",
                    lists=["data/raw/etherscan/txlist_0x19c7849d_0_17830000.json", "data/raw/etherscan/txlistinternal_0x19c7849d_0_17806100.json"], pref="0xdfd5293d"),
    "aleth": dict(eoa="0xdce5d6b41c32f578f875efffc0d422c57a75d7d8", contract="0x30fb95794a2051abe30a67892b3a1fa73947aee5",
                  funding_tx="0xc0e6169ccab4fc39c0dd09d065d1ecc7980b23c46559c31c1200a2a1fac639b1",
                  lists=["data/raw/etherscan/txlist_0xdce5d6b4_0_17830000.json", "data/raw/etherscan/txlistinternal_0xdce5d6b4_0_17806100.json"], pref="0x512cb8bb"),
    "crv1": dict(eoa="0xb752def3a1fded45d6c4b9f4a8f18e645b41b324", contract="0x83e056ba00beae4d8aa83deb326a90a4e100d0c1",
                 funding_tx="0x756cf2da292c3511735ee67e566bbf8209990724949852b2ee582a332e725b27",
                 lists=["data/raw/etherscan/txlistinternal_0xb752def3_0_17806100.json", "data/raw/etherscan/txlist_0xb752def3_17800000_17812000.json"], pref="0xa757328f"),
}


def att_funding(key, label_if_found, gaps, refs, prefix):
    a = ATT[key]
    rec, path = funding(a["funding_tx"], a["lists"], a["pref"])
    if rec is None:
        gaps.append({"field": f"{prefix}attacker.funding_tx", "why": "funding tx not found in the saved etherscan lists (hash taken from incident.json)"})
        return "unknown"
    refs[f"{prefix}attacker.funding_tx"] = path
    return label_if_found


# =====================================================================================================================
# ROW 1: pETH
# =====================================================================================================================
def row_peth():
    sub = SUBS[S_PETH]
    gaps, refs, disc = [], {}, []
    N = 17806056
    race_path = f"{D}/race_{N}.json"
    race = bvh.load(race_path)
    BOT = "0xa84aa065ce61dbb1eb50ab6ae67fc31a9da50dd2c74eefd561661bfce2f1620c"
    ATT_DEP = "0xb2dfea6de47e35cc8e660489afb7380a1fa0b978a59c81685d94ff0ca7ce9dfc"
    ATT_ATK = "0xb5d91f1e0afc96a52f8c6c28eae405eda7fcc5d34d6d03bdd8b16bd58089e939"
    bot, dep, atk = txinfo(N, BOT), txinfo(N, ATT_DEP), txinfo(N, ATT_ATK)
    for i in (bot, dep, atk):
        check_vs_race(i, race_path)
    assert (bot["index"], dep["index"], atk["index"]) == (0, 90, 91) and atk["status"] == "reverted" and bot["status"] == "success"
    assert bot["from"] == "0x6ec21d1868743a44318c3c259a6d4953f9978538" and atk["from"] == ATT["peth"]["eoa"] == dep["from"]
    assert bot["coinbase_eth"] == 0.0
    # the front-runner's tx pulls the WETH out of the pETH pool via its in-tx-created helper
    wt = logs_transfers(N, BOT, WETH)
    bot_contract = bot["to"]
    gross = [t for t in wt if t["to"] == bot_contract][-1]["amount"]
    # initcode comparison (public: the attacker's deploy tx vs the CREATE frame inside the front-runner's tx)
    creates = [f for f in bot["frames"] if f["type"] == "CREATE"]
    ic_bot = creates[0]["input"] if creates else None
    ic_att = dep["input"]
    cmp_note = None
    if ic_bot:
        a, b = bytes.fromhex(ic_att[2:]), bytes.fromhex(ic_bot[2:])
        diff = [i for i in range(min(len(a), len(b))) if a[i] != b[i]]
        cmp_note = {"len_attacker_deploy": len(a), "len_frontrunner_create": len(b), "differing_bytes": len(diff),
                    "differing_range": [diff[0], diff[-1]] if diff else None}
        assert len(a) == len(b) and len(diff) == 20, cmp_note
    # call sequences (victim-pool calls, from the existing scan file): same selectors and fixed 40,000 ETH arguments
    s_bot, s_att = pool_seq("pETH_bot"), pool_seq("pETH_attacker")
    # other racers in this block pair
    dep2 = txinfo(17806057, "0x3fbe0c28fe252a218399dc38d44fbd2f7c3e039ef08eb07c9581c371cda6583f")
    cp_dep = txinfo(17806058, "0x95e8d7c388cdebac568e3ddab2a8e1e24e90497c5685455f888f3f699c49ca8f")
    cp_atk = txinfo(17806058, "0xfe07ef76b96624643be6e5ab68c4001330732154ab786f23dd3cf979b0bf4461")
    check_vs_race(dep2, f"{D}/race_17806057.json")
    check_vs_race(cp_dep, f"{D}/race_17806058.json")
    check_vs_race(cp_atk, f"{D}/race_17806058.json")
    assert (dep2["index"], cp_dep["index"], cp_atk["index"]) == (14, 0, 2)
    dep2_ic = bytes.fromhex(dep2["input"][2:])
    ic_diff2 = sum(1 for x, y in zip(dep2_ic, bytes.fromhex(ic_att[2:])) if x != y)
    # fate: tokentx files
    tt1 = bvh.load("data/raw/etherscan/tokentx_0x6ec21d18_17806056_17860000.json")["result"]
    tt2 = bvh.load("data/raw/etherscan/tokentx_0x9d1ec337_17839000_17900000.json")["result"]
    recv = [t for t in tt1 if t["to"].lower() == bot["from"] and t["tokenSymbol"] == "WETH"][0]
    recv_amt = int(recv["value"]) / 1e18
    to_op = [t for t in tt1 if t["from"].lower() == bot["from"] and t["tokenSymbol"] == "WETH"]
    op2 = to_op[0]["to"].lower()
    sent_out = sum(int(t["value"]) for t in to_op) / 1e18
    safe = "0x51c2cef9efa48e08557a361b52db34061c025a1b"
    ret = [t for t in tt2 if t["from"].lower() == op2 and t["to"].lower() == safe and t["tokenSymbol"] == "WETH"]
    assert len(ret) == 2
    returned = sum(int(t["value"]) for t in ret) / 1e18
    assert abs(returned - 5495.4) < 1e-9
    remainder = sent_out - returned
    msg_rec, msg_path = find_in_lists(["data/raw/etherscan/txlist_0x6ec21d18_17830000_17900000.json", "data/raw/etherscan/txlist_0x7a271674_17800000_17900000.json"],
                                      [t for t in [x["hash"] for x in bvh.load("data/raw/etherscan/txlist_0x6ec21d18_17830000_17900000.json")["result"] if x["blockNumber"] == "17844761"]][0])
    msg = etherscan_text(msg_rec)
    assert msg and "5,495.4" in msg and "610.6" in msg, msg
    msg_hash = msg_rec["hash"]
    msg_block = int(msg_rec["blockNumber"])
    tl6 = bvh.load("data/raw/etherscan/txlist_0x6ec21d18_0_17830000.json")["result"]
    prior_n = sum(1 for t in tl6 if int(t["blockNumber"]) < N)
    prior_same = sum(1 for t in tl6 if int(t["blockNumber"]) < N and t["to"].lower() == bot_contract)
    if prior_n != 167:
        disc.append(f"incident.json says the front-runner EOA had 167 prior txs; the saved txlist (data/raw/etherscan/txlist_0x6ec21d18_0_17830000.json) shows {prior_n} before block {N}.")
    disc.append("auction tooling treated idx 0 (0xa84aa065) as the attacker. On chain it is a front-runner whose in-tx CREATE initcode equals the real attacker's deploy tx "
                f"initcode byte for byte except {cmp_note['differing_bytes']} bytes; the real attacker (0x172f6fde, Tornado-funded) is at idx 90/91 and its attack reverted.")
    disc.append(f"Bounty: JPEG'd's on-chain statement (block {msg_block}) says a 10% bounty of 610.6 WETH was awarded; the on-chain remainder after the 5,495.4 WETH return "
                f"is {remainder:.4f} WETH ({sent_out:.4f} moved out of the front-runner EOA, which had received {recv_amt:.4f} from the contract; the contract-to-EOA move of "
                f"{recv_amt:.4f} exceeds the {gross:.4f} WETH taken in the exploit tx by {recv_amt - gross:.4f} WETH of pre-existing balance). Raw value used for bounty_kept_eth.")
    disc.append("incident.json reports 'returned 90%': 5,495.4 / 6,106.75 = 89.99%; against the 6,106.65 WETH taken in the exploit tx it is 89.99% as well.")
    fund_label = att_funding("peth", "tornado", gaps, refs, "")
    peth_att = ATT["peth"]
    refs.update({
        "bot.block": [f"data/raw/rpc/block_{N}.json"],
        "bot.position": raw_for_tx(N),
        "attacker_block": raw_for_tx(N),
        "loot.gross_loot_eth": [f"data/raw/rpc/receipts_{N}.json", f"data/raw/rpc/trace_block_{N}.json"],
        "loot.coinbase_paid_eth": [f"data/raw/rpc/trace_block_{N}.json", f"data/raw/rpc/block_{N}.json"],
        "loot.priority_fee_paid_eth": [f"data/raw/rpc/receipts_{N}.json", f"data/raw/rpc/block_{N}.json"],
        "loot.bot_net_eth": [f"data/raw/rpc/receipts_{N}.json", f"data/raw/rpc/block_{N}.json"],
        "fate.returned_by_bot_eth": ["data/raw/etherscan/tokentx_0x9d1ec337_17839000_17900000.json"],
        "fate.returned_total_eth": ["data/raw/etherscan/tokentx_0x9d1ec337_17839000_17900000.json"],
        "fate.bounty_kept_eth": ["data/raw/etherscan/tokentx_0x6ec21d18_17806056_17860000.json", "data/raw/etherscan/tokentx_0x9d1ec337_17839000_17900000.json"],
        "fate.kept_by_bot_eth": ["data/raw/etherscan/tokentx_0x6ec21d18_17806056_17860000.json", "data/raw/etherscan/tokentx_0x9d1ec337_17839000_17900000.json"],
        "fate.public_statement": "data/raw/etherscan/txlist_0x6ec21d18_17830000_17900000.json",
        "bots_other.positions": ["data/raw/rpc/block_17806057.json", "data/raw/rpc/block_17806058.json"],
    })
    rets = [{"tx": t["hash"], "eth": int(t["value"]) / 10 ** int(t["tokenDecimal"]), "note": "WETH from the front-runner's second address 0x9d1ec337 to the JPEG'd Safe " + safe,
             "block": int(t["blockNumber"]), "time_utc": iso(t["timeStamp"])} for t in ret]
    row = {
        "slug": SLUG, "sub": "pETH", "name": "Curve/Vyper reentrancy: pETH-ETH (JPEG'd) pool - byte-copy front-runner vs the real attacker",
        "date_utc": race["block"]["timestamp_utc"].replace("+00:00", "Z"), "chain": "ethereum",
        "orig_verdict": sub["verdict"],
        "race_type_proposed": "beat-pending-attack",
        "race_type_reason": ("The front-runner's tx sits at idx 0 of block 17806056 and its in-tx CREATE initcode is a copy of the attacker's deploy initcode (20 bytes differ); "
                             "the real attacker's deploy (idx 90) and attack (idx 91) are later in the SAME block and the attack reverted because the pool was already drained."),
        "one_liner": ("An unrelated address copied the pETH attacker's contract and landed at block position 0, ahead of the attacker's own deploy and attack at positions 90 and 91 "
                      "(which reverted); it took 6,106.65 WETH and returned 90% to JPEG'd."),
        "attacker": {"eoa": peth_att["eoa"], "eoas": [peth_att["eoa"]], "contracts": [peth_att["contract"]], "funding": fund_label,
                     "funding_tx": peth_att["funding_tx"], "deploy_tx": ATT_DEP, "deploy_block": N,
                     "attack_txs": [
                         {**pub(dep), "role": "attacker contract deploy (priority fee %.3f gwei)" % dep["priority_fee_gwei"]},
                         {**pub(atk), "role": "attacker attack call start(): reverted (pool already emptied by the front-runner); priority fee %.3f gwei" % atk["priority_fee_gwei"]}],
                     "none_reason": None},
        "bot": {"label": "pETH front-runner (anon, not c0ffeebabe)", "eoa": bot["from"], "contract": bot_contract, "tx": BOT, "block": N, "position": bot["index"],
                "status": bot["status"], "priority_fee_gwei": bot["priority_fee_gwei"]},
        "bots_other": [
            {"label": "msETH actor's byte-copy deploy (0x19c7849d)", "eoa": dep2["from"], "tx": dep2["hash"], "block": dep2["block"], "position": dep2["index"], "status": dep2["status"],
             "role": f"deployed the pETH attacker's initcode ({ic_diff2} bytes differ) one block later; no attack call on pETH (later adapted for msETH / CRV-ETH)"},
            {"label": "second copycat, re-implementation (0x79310104)", "eoa": cp_dep["from"], "tx": cp_dep["hash"], "block": cp_dep["block"], "position": cp_dep["index"], "status": cp_dep["status"],
             "role": "deploy of its own re-implemented contract, 2 blocks after the exploit"},
            {"label": "second copycat attack call", "eoa": cp_atk["from"], "tx": cp_atk["hash"], "block": cp_atk["block"], "position": cp_atk["index"], "status": cp_atk["status"],
             "role": "late copy 2 blocks after: top level ok, flash-loan leg reverted internally, net nothing; paid %.3f gwei priority" % cp_atk["priority_fee_gwei"]},
        ],
        "evidence_level_mempool": "in-block-only", "mempool_note": MEMP_NOTE, "trigger": NOMEMP_TRIGGER,
        "attacker_block": N,
        "attacker_block_note": (f"attacker's racing attack tx {ATT_ATK[:12]} at idx 91 of the SAME block (reverted); its deploy {ATT_DEP[:12]} is at idx 90. "
                                "bot block - attacker block = 0, bot position 0 vs 91."),
        "attacker_reference": {"kind": "attack-tx", "block": N, "tx": ATT_ATK},
        "auction": bvh.auction_summary(race_path, BOT),
        "loot": {"scope": "bot-tx", "gross_loot_eth": gross,
                 "gross_loot_method": "WETH Transfer events in the front-runner tx receipt: WETH paid to the front-runner's contract (1 WETH = 1 ETH)",
                 "captured_native": {"amount": gross, "unit": "WETH", "desc": "WETH from the pETH-ETH pool (via a flash-loaned 80,000 WETH round trip) to the front-runner's contract"},
                 "captured_usd": None, "captured_usd_source": None,
                 "coinbase_paid_eth": bot["coinbase_eth"], "priority_fee_paid_eth": bot["priority_fee_eth"],
                 "builder_refund_to_bot_eth": None, "builder_payout_to_victim_eth": None,
                 "bot_net_eth": gross - bot["priority_fee_eth"] - bot["coinbase_eth"],
                 "loot_note": ("won position 0 with a plain gas bid: %.3f gwei priority, no coinbase transfer, %.6f ETH to the builder (rsync-builder.xyz block; no delivered-payload record on any reachable relay). "
                               "bot_net = gross - priority fee - coinbase (base-fee burn excluded), before the later return. USD not computed." % (bot["priority_fee_gwei"], bot["priority_fee_eth"]))},
        "fate": {"return_status": "returned", "returned_by_bot_eth": returned, "returned_by_builder_eth": None, "returned_total_eth": returned,
                 "returned_to": safe + " (JPEG'd DAO multisig, per JPEG'd's on-chain statement)",
                 "returned_desc": (f"On 2023-08-04 the operator moved {sent_out:.4f} WETH to a second address ({op2}), which sent {returned:.1f} WETH to the JPEG'd Safe in two txs "
                                   f"(blocks {rets[0]['block']} and {rets[1]['block']}, finishing {rets[1]['time_utc']}); the rest was kept as the agreed white-hat bounty. JPEG'd's team had messaged the "
                                   "operator on chain at block 17808132 and promised no legal action on return."),
                 "bounty_kept_eth": remainder, "bounty_desc": f"on-chain remainder {remainder:.4f} WETH; JPEG'd's statement says a 10% bounty of 610.6 WETH was awarded (see discrepancies)",
                 "kept_by_bot_eth": remainder, "returned_txs": rets,
                 "public_statement": f"JPEG'd DAO on-chain message (tx {msg_hash}, block {msg_block}): " + msg},
        "evidence_notes": [
            f"The front-runner's in-tx CREATE initcode vs the real attacker's deploy tx input: {cmp_note['len_attacker_deploy']} bytes each, {cmp_note['differing_bytes']} differing bytes in one run "
            f"({cmp_note['differing_range'][0]}-{cmp_note['differing_range'][1]}) = the 20-byte beneficiary address (recomputed from data/raw/rpc/block_{N}.json and trace_block_{N}.json).",
            f"Block {N}: front-runner idx 0 (success, {bot['priority_fee_gwei']:.3f} gwei priority), attacker deploy idx 90 and attack idx 91 ({atk['priority_fee_gwei']:.3f} gwei; reverted) - recomputed from raw block/receipts.",
            f"Victim-pool call sequences (incidents/{SLUG}/pool_call_sequences.json): front-runner {len(s_bot)} pool calls vs attacker {len(s_att)}; same first four selectors and the same 40,000 ETH add_liquidity amounts (the attacker's last call reverted).",
            "The attacker's contract was funded and deployed by a fresh Tornado-funded EOA with only two txs ever (incident.json); the front-runner EOA is a 2022-era account (%d earlier txs in its saved txlist, %d of them to the same contract 0x9420f882) whose only tx touching the four Curve pools in 17793000-17806500 is this one (pooltouch_0x6ec21d18.json, incident.json)." % (prior_n, prior_same),
            "No relay holds a delivered-payload record for block 17806056 (data/raw/relay-flashbots/delivered_block17806056.json etc.); winner unknown, so the auction block has no winning bid.",
        ],
        "incident_dir": D,
    }
    row["discrepancies"] = disc
    return finish_row(row, refs, gaps)


# =====================================================================================================================
# ROW 2: msETH
# =====================================================================================================================
def curated_row(sub):
    rows = json.loads((ROOT / "data/extract/curve-vyper-2023.json").read_text())
    return next(row for row in rows if row.get("sub") == sub)


def row_ms():
    return curated_row("msETH")


def row_c2():
    return curated_row("CRV-ETH-wave2")


def rejected_common(sub, subname, sub_id, N, ATK, att_key, role, reason, one_liner, nm, extra_other, extra_evidence, extra_disc, fate_desc, bot_other_refs=None):
    gaps, refs, disc = [], {}, list(extra_disc)
    race_path = f"{D}/race_{N}.json"
    race = bvh.load(race_path)
    atk = txinfo(N, ATK)
    check_vs_race(atk, race_path)
    a = ATT[att_key]
    contract = a["contract"]
    to_eoa = eth_flow(atk["frames"], atk["to"], a["eoa"])
    fund_label = att_funding(att_key, "eoa-transfer", gaps, refs, "")
    refs.update({"attacker_block": raw_for_tx(N)})
    row = {
        "slug": SLUG, "sub": subname, "name": nm,
        "date_utc": race["block"]["timestamp_utc"].replace("+00:00", "Z"), "chain": "ethereum",
        "orig_verdict": sub["verdict"],
        "race_type_proposed": "bot-was-first-exploiter",
        "race_type_reason": (reason + " PLACEHOLDER: the taxonomy has no 'no race' value; the nearest is bot-was-first-exploiter (the sole actor is the exploiter itself). "
                             "The harmonized verdict is 'rejected' (no racer), so this must not count as a bot win or be headlined."),
        "one_liner": one_liner,
        "attacker": {"eoa": a["eoa"], "eoas": [a["eoa"]], "contracts": [contract], "funding": fund_label, "funding_tx": a["funding_tx"],
                     "deploy_tx": extra_other.get("deploy_tx"), "deploy_block": extra_other.get("deploy_block"),
                     "attack_txs": [{**pub(atk), "role": role + "; priority fee %.3f gwei" % atk["priority_fee_gwei"], "priority_fee_gwei": atk["priority_fee_gwei"],
                                     "priority_fee_paid_eth": atk["priority_fee_eth"], "coinbase_eth": atk["coinbase_eth"], "eth_received_by_attacker_eoa": to_eoa}],
                     "none_reason": None},
        "bot": {"label": "none", "eoa": None, "contract": None, "tx": None, "block": None, "position": None, "status": None, "priority_fee_gwei": None},
        "bots_other": extra_other.get("bots_other", []),
        "evidence_level_mempool": "in-block-only", "mempool_note": MEMP_NOTE, "trigger": NOMEMP_TRIGGER,
        "attacker_block": N,
        "attacker_block_note": f"block of the sole actor's exploit tx {ATK[:12]} (idx {atk['index']}); no other actor replays the sequence, so there is no bot block (bot block - attacker block undefined).",
        "attacker_reference": {"kind": "attack-tx", "block": N, "tx": ATK},
        "auction": bvh.auction_summary(race_path, None),
        "loot": {"scope": "bot-tx", "gross_loot_eth": None, "gross_loot_method": "no bot tx in this sub-race",
                 "captured_native": {"amount": None, "unit": None, "desc": "no bot"}, "captured_usd": None, "captured_usd_source": None,
                 "coinbase_paid_eth": None, "priority_fee_paid_eth": None, "builder_refund_to_bot_eth": None, "builder_payout_to_victim_eth": None, "bot_net_eth": None,
                 "loot_note": extra_other["loot_note"].format(to_eoa=to_eoa, prio=atk["priority_fee_eth"])},
        "fate": {"return_status": "not-applicable", "returned_by_bot_eth": None, "returned_by_builder_eth": None, "returned_total_eth": None, "returned_to": None,
                 "returned_desc": fate_desc, "bounty_kept_eth": None, "bounty_desc": None, "kept_by_bot_eth": None, "returned_txs": [], "public_statement": None},
        "evidence_notes": [x.replace("@IDX@", str(atk["index"])).replace("@PRIO@", "%.1f" % atk["priority_fee_gwei"]) for x in extra_evidence],
        "incident_dir": D,
    }
    row["discrepancies"] = disc
    return finish_row(row, refs, gaps), atk, to_eoa


def row_aleth():
    sub = SUBS[S_AL]
    N = 17806772
    ATK = "0xb676d789bb8b66a08105c844a49c2bcffb400e5c1cfabd4bc30cca4bff3c9801"
    # Alchemix-side whitehat withdrawals recorded in incident.json -> look them up in the saved pool txlist
    wh = []
    for h in ("0x3d92f0152b582304b3068d9c779d4793152703a9baf3d4c4ce0e0a8a7161a4ef", "0x20d00acdfbaeffa5fe618ecbcbb8c13df80133cb6d964f9a7ab6a5a7b0d796f3",
              "0x1fd303a0475b1836f7cf53cf9a88e5eff990dbd3100247f3c109f8aac60306a6", "0x5dbd9c4291833047250e2812f81cb02d66872867ef7877332782753d481431f4"):
        txj, rj = bvh.load(f"data/raw/rpc/tx_{h}.json")["result"], bvh.load(f"data/raw/rpc/receipt_{h}.json")["result"]
        wh.append({"label": "pre-exploit pool withdrawal (reported Alchemix-side white hat, unverified; not racing)", "eoa": txj["from"].lower(), "tx": h, "block": hx(rj["blockNumber"]),
                   "position": hx(rj["transactionIndex"]), "status": "success" if rj["status"] == "0x1" else "reverted",
                   "role": "withdrawal from the alETH pool before the exploit, via contract " + (txj["to"] or "").lower()})
    # the attacker's returns (context): alETH + ETH sent to 0x9e2b6378 on 2023-08-04
    tl = bvh.load("data/raw/etherscan/txlist_0xdce5d6b4_17806000_17860000.json")["result"]
    eth_to = [t for t in tl if t["to"].lower() == "0x9e2b6378ee8ad2a4a95fe481d63caba8fb0ebbf9" and int(t["value"]) > 0]
    eth_sum_aug4 = sum(int(t["value"]) for t in eth_to if int(t["blockNumber"]) < 17850000) / 1e18
    tt = bvh.load("data/raw/etherscan/tokentx_0xdce5d6b4_17806700_17860000.json")["result"]
    aleth_ret = [t for t in tt if t["from"].lower() == "0xdce5d6b41c32f578f875efffc0d422c57a75d7d8" and t["to"].lower() == "0x9e2b6378ee8ad2a4a95fe481d63caba8fb0ebbf9"]
    aleth_sum = sum(int(t["value"]) / 10 ** int(t["tokenDecimal"]) for t in aleth_ret)
    s = pool_seq("alETH_attacker")
    row, atk, to_eoa = rejected_common(
        sub, "alETH", S_AL, N, ATK, "aleth",
        "attacker exploit tx (swap/loop on the alETH pool)",
        "No racer: every tx calling the alETH pool in blocks 17805900-17809000 was inspected (incident.json: 39 txs) and exactly one carries the reentrancy sequence, the attacker's own at idx 10; No second actor is recorded for this sub-race.",
        ("alETH pool: the only reentrancy exploit tx is the attacker's own at block position 10 (3 gwei priority); no bot or copier touched this sequence before or after it. Rejected as a race."),
        "Curve/Vyper reentrancy: alETH-ETH (Alchemix) pool - sole actor, no racer (rejected)",
        {"deploy_tx": "0xf7704b5c4dabd8e6f94391b48467fedfcf02f5d5820fa4d737be464515fc1fc0", "deploy_block": 17806760, "bots_other": wh,
         "loot_note": "no bot tx; for reference the sole actor's own exploit tx moved {to_eoa:.4f} ETH to its EOA and paid {prio:.6f} ETH priority fee to the builder (3 gwei priority). It also held ~4,820 alETH (see fate note)."},
        [
            f"The alETH sub-race has no racer in the recorded window.",
            f"Exploit tx {ATK[:12]} at idx @IDX@ of {N} with @PRIO@ gwei priority; the attacker deployed its final contract 12 blocks earlier (17806760 idx 64) after earlier deploy/test iterations at 17806549, 17806688, 17806727 (incident.json).",
            "Four earlier txs from Alchemix-side accounts withdrew from the pool (17806708-17806760); public reports call them white hats who 'only got 2/3 of the way through' - interpretation, not verified; they are not copies of the exploit sequence.",
            "txs that never reached the pool (early reverts) are not enumerable from pool-touch scans, so 'no racer' means no racer among txs that touched the pool.",
        ],
        [f"The attacker later returned alETH and ETH to 0x9e2b6378 (Alchemix-side); saved txlists show {aleth_sum:,.2f} alETH and {eth_sum_aug4:,.1f} ETH sent there before block 17850000; purpose of the additional 5,000 ETH sent on 2023-08-05 is not verified (incident.json)."],
        "not-applicable: no bot in this sub-race. Context: the sole actor (0xdce5d6b4, who calls itself a white hat) sent back %.2f alETH and %.1f ETH to 0x9e2b6378 (Alchemix-side) around 2023-08-04, per the saved txlist/tokentx files." % (aleth_sum, eth_sum_aug4))
    row["attacker"]["note"] = "self-described white hat per its on-chain messages (incident.json), not verified"
    row["raw_refs"].update({"bots_other.positions": [f"data/raw/rpc/receipt_{w['tx']}.json" for w in row["bots_other"]], "fate.context": ["data/raw/etherscan/txlist_0xdce5d6b4_17806000_17860000.json", "data/raw/etherscan/tokentx_0xdce5d6b4_17806700_17860000.json"]})
    return row


def row_c1():
    sub = SUBS[S_C1]
    N = 17807830
    ATK = "0x2e7dc8b2fb7e25fd00ed9565dcc0ad4546363171d5e00f196d48103983ae477c"
    row, atk, to_eoa = rejected_common(
        sub, "CRV-ETH-wave1", S_C1, N, ATK, "crv1",
        "attacker exploit tx on the CRV/ETH pool (add/remove-liquidity loops, 10,000 WETH Balancer flash)",
        "No racer: the attacker deployed its contract at 17807829 idx 84 and attacked at 17807830 idx 6; no other tx in 17807700-17808000 replays the sequence (incident.json scan).",
        "CRV/ETH pool, first wave: the sole actor deployed and attacked within two blocks (position 6, 1 gwei priority); nothing replays it. The pool's leftover funds were taken hours later in the wave-2 race.",
        "Curve/Vyper reentrancy: CRV/ETH pool, first wave - sole actor, no racer (rejected)",
        {"deploy_tx": None, "deploy_block": 17807829, "bots_other": [],
         "loot_note": "no bot tx; for reference the sole actor's own exploit tx (gas used 11,366,004) paid {prio:.6f} ETH priority fee (1 gwei) and sent no ETH to its EOA directly; the net take is not summed (token and ETH flows pass through its contract, e.g. the pool paid 33,680.49 ETH to the contract in the tx before the flash loan was repaid)."},
        [
            f"The attacker's deploy is at 17807829 idx 84 (incident.json; deploy tx hash not recorded there) and the attack at 17807830 idx @IDX@; with a 11.37M-gas tx at 1 gwei priority the attacker paid builders only 0.0114 ETH (recomputed).",
            "No other tx in 17807700-17808000 replays the sequence (incident.json scan); the same pool was attacked again in the wave-2 race 853 blocks (2.84 h) later, where c0ffeebabe pre-empted the adapter 0x19c7849d.",
            "auction tooling's 'post-hack trade' label for tx 0x2e7dc8b2 is wrong in the opposite direction: it is the original CRV/ETH reentrancy attack.",
        ],
        ["auction tooling reading of 0x2e7dc8b2 as a 'post-hack trade' is rejected; it is the CRV/ETH pool's first-wave exploit (incident.json w3_claims_checked)."],
        "not-applicable: no bot in this sub-race; no return recorded for this sole actor in the saved data (not searched beyond the incident file).")
    row["attacker"]["deploy_note"] = "deploy tx hash not recorded in incident.json (block 17807829 idx 84)"
    return row


def main():
    rows = [row_peth(), row_ms(), row_c2(), row_aleth(), row_c1()]
    out = ROOT / "data" / "extract" / f"{SLUG}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    json.dump(rows, open(out, "w"), indent=1, ensure_ascii=False)
    print("wrote", out, [r["sub"] for r in rows])


if __name__ == "__main__":
    main()
