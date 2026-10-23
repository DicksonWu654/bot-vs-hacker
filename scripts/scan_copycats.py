#!/usr/bin/env python3
"""scan_copycats.py -- find addresses that copied / front-ran an exploit, from on-chain data only.

For every exploit tx in an exploit list (see research/chain-scan/extract_exploits.py -> exploits_mainnet.json):
  1. fetch tx, block B and blocks B-2, B-1, B+1 (full txs) and their receipts (eth_getBlockReceipts) through
     rawfetch (everything is cached under data/raw/rpc and logged in MANIFEST.jsonl);
  2. trace the attack tx (callTracer) -> victim set V (net losers of the attacker's profit tokens/ETH, plus the
     DeFiHackLabs-listed victims), the attacker's "victim-facing signature" (target, selector) pairs, contracts
     the attack created, coinbase payments;
  3. pre-filter every other tx in the window by receipt logs / `to` / calldata similarity, then trace the best
     candidates (and the reverted / immediately preceding txs of block B) and score them.

Usage:
  .venv/bin/python scripts/scan_copycats.py --exploits research/chain-scan/exploits_mainnet.json \
        --out research/chain-scan/scan_results.json [--threads 4] [--limit N] [--only NAME_OR_TX]
  .venv/bin/python scripts/scan_copycats.py --tx 0x... [--tx 0x...]      # ad-hoc scan of single txs

Scoring is heuristic and emits *candidates*; every hit must be read by a human (arbitrage bots touching the same
pool and the attacker's own multi-tx / multi-EOA activity are the main false positives and are flagged where
detectable).  Evidence level language follows the evidence levels in the README: this script only ever produces `candidate`s.
"""
import argparse, concurrent.futures as cf, json, os, pathlib, sys, threading, time, traceback

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "lib"))
import rawfetch  # noqa: E402

TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
ZERO = "0x" + "0" * 40
# Selectors that tell us nothing about *how* a victim was attacked (views, ERC20 plumbing, plain swaps, WETH).
GENERIC_SEL = {
    "70a08231", "dd62ed3e", "a9059cbb", "23b872dd", "095ea7b3", "18160ddd", "313ce567", "95d89b41", "06fdde03",
    "0902f1ac", "0dfe1681", "d21220a7", "022c0d9f", "128acb08", "38ed1739", "7ff36ab5", "18cbafe5", "8803dbee",
    "fb3bdb41", "4a25d94a", "5c11d795", "b6f9de95", "791ac947", "d0e30db0", "2e1a7d4d", "5c60da1b", "52d1902d",
    "fa461e33", "e9cbafb0", "5cffe9de", "f04f2707", "ab9c4b5d", "42b0b77c", "1b11d0ff", "490e6cbc", "3593564c",
    "c45a0155", "e6a43905", "5aa6e675", "1a686502", "ac9650d8", "49404b7c", "12210e8a", "4f1ef286", "3659cfe6",
}
ROUTERS = {  # generic swap routers / aggregators: deprioritised when choosing what to trace
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488d", "0xe592427a0aeece92de3edee1f18e0157c05861564",
    "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45", "0x3fc91a3afd70395cd496c647d5a6cc9d4b2b7fad",
    "0x1111111254eeb25477b68fb85ed929f73a960582", "0x1111111254fb6c44bac0bed2854e76f90643097d",
    "0xdef1c0ded9bec7f1a1670819833240f027b25eff", "0x881d40237659c251811cec9c364ef91dc08d300c",
    "0xd9e1ce17f2641f24ae83637ab66a2cca9c378b9f", "0x6131b5fae19ea4f9d964eac0408e4408b66337b5",
    "0x9008d19f58aabd9ed0d60971565aa8510560ab41", "0x000000000022d473030f116ddee9f6b43ac78ba3",
}
INFRA = {  # shared infrastructure: never treated as "the victim" just because the attacker called it
    "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2", "0x7d2768de32b0b80b7a3454c06bdac94a69ddc7a9",
    "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2", "0x398ec7346dcd622edc5ae82352f02be94c62d119",
    "0xba12222222228d8ba445958a75a0704d566bf2c8", "0x5c69bee701ef814a2b6a3edd4b1652cb9cc5aa6f",
    "0x1f98431c8ad98523631ae4a59f267346ea31f984", "0xc36442b4a4522e871399cd717abdd847ab11fe88",
    "0x000000000022d473030f116ddee9f6b43ac78ba3", "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
    "0xdac17f958d2ee523a2206206994597c13d831ec7", "0x6b175474e89094c44da98b954eedeac495271d0f",
    "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984", "0x0000000000000000000000000000000000000000",
    "0x000000000004444c5dc75cb358380d2e3de08a90",
}
KNOWN_ADDR = {  # block builders/coinbases and a few well-known MEV addresses (labels only; extend freely)
    "0xdafea492d9c6733ae3d56b7ed1adb60692c98bc5": "builder:flashbots",
    "0x95222290dd7278aa3ddd389cc1e1d165cc4bafe5": "builder:beaverbuild",
    "0x1f9090aae28b8a3dceadf281b0f12828e676c326": "builder:rsync",
    "0x4838b106fce9647bdf1e7877bf73ce8b0bad5f97": "builder:titan",
    "0xae2fc483527b8ef99eb5d9b44875f005ba1fae13": "mev:jaredfromsubway",
    "0x6b75d8af000000e20b7a7ddf000ba900b4009a80": "mev:jaredfromsubway-bot",
}
LOCK = threading.Lock()
PACE = float(os.environ.get("BVH_PACE", "0.12"))


# ---------------------------------------------------------------- rpc helpers
def _h2i(x):
    return int(x, 16) if isinstance(x, str) else (x or 0)


def call(method, params, key, **kw):
    """rawfetch.rpc with polite pacing and extra backoff; cached responses return immediately."""
    if rawfetch._cached("rpc", key, "json"):
        return rawfetch.rpc(method, params, key=key)
    last = None
    for i in range(4):
        time.sleep(PACE * (1 + i))
        try:
            return rawfetch.rpc(method, params, key=key, **kw)
        except Exception as e:  # noqa: BLE001
            last = e
            msg = str(e)
            if "does not exist" in msg or "invalid argument" in msg.lower():
                raise
            time.sleep(5 * (i + 1))
    raise last


def get_tx(h):
    return call("eth_getTransactionByHash", [h], key=f"eth_getTransactionByHash_{h}")


def get_block(n):
    return call("eth_getBlockByNumber", [hex(n), True], key=f"eth_getBlockByNumber_full_{n}")


def get_receipts(n):
    return call("eth_getBlockReceipts", [hex(n)], key=f"eth_getBlockReceipts_{n}")


def get_trace(h):
    return call("debug_traceTransaction", [h, {"tracer": "callTracer"}], key=f"debug_traceTransaction_callTracer_{h}",
                timeout=240)


# ---------------------------------------------------------------- trace helpers
def walk(t, reverted=False):
    """yield (call, reverted_flag) depth-first; reverted_flag True if the call or an ancestor errored."""
    r = reverted or bool(t.get("error"))
    yield t, r
    for c in t.get("calls") or []:
        yield from walk(c, r)


def trace_facts(trace, coinbase):
    created, eth_net, cb_paid, targets = set(), {}, 0, []
    for c, rev in walk(trace):
        to = (c.get("to") or "").lower()
        if c.get("type") in ("CREATE", "CREATE2") and not rev and to:
            created.add(to)
        v = _h2i(c.get("value"))
        if v and not rev and c.get("type") not in ("DELEGATECALL", "STATICCALL"):
            f = (c.get("from") or "").lower()
            eth_net[f] = eth_net.get(f, 0) - v
            eth_net[to] = eth_net.get(to, 0) + v
            if to == coinbase:
                cb_paid += v
        inp = c.get("input") or "0x"
        targets.append((to, inp[2:10].lower() if len(inp) >= 10 else "", rev, c.get("type"), (c.get("from") or "").lower()))
    return {"created": created, "eth_net": eth_net, "coinbase_paid": cb_paid, "calls": targets}


def victim_calls(trace, Vs):
    """calls into victim contracts: (to, selector, input, reverted)"""
    out = []
    for c, rev in walk(trace):
        to = (c.get("to") or "").lower()
        inp = (c.get("input") or "0x").lower()
        if to in Vs and len(inp) >= 10 and c.get("type") not in ("CREATE", "CREATE2"):
            out.append((to, inp[2:10], inp, rev))
    return out


def arg_match(att_calls, cand_calls):
    """fraction of the attacker's *specific, argument-bearing* victim calls that the candidate repeats with
    identical (exact) or near-identical (word Jaccard >= 0.8) arguments.  Returns (near_frac, exact_frac, n)."""
    base = [(t, s, i) for (t, s, i, rev) in att_calls if not rev and s not in GENERIC_SEL and len(i) > 10]
    seen, uniq = set(), []
    for t, s, i in base:
        if i not in seen:
            seen.add(i); uniq.append((t, s, i))
    if not uniq:
        return 0.0, 0.0, 0
    near = exact = 0
    cc = [(t, s, i) for (t, s, i, rev) in cand_calls]
    for t, s, i in uniq:
        wa = words(i)
        best, ex = 0.0, False
        for (t2, s2, i2) in cc:
            if t2 != t or s2 != s:
                continue
            if i2 == i:
                ex = True; best = 1.0; break
            wb = words(i2)
            if wa or wb:
                best = max(best, len(wa & wb) / len(wa | wb))
        near += best >= 0.8
        exact += ex
    return near / len(uniq), exact / len(uniq), len(uniq)


def token_flows(receipt):
    """per (token, address) net ERC20/721 flow from Transfer logs; success only."""
    net = {}
    if receipt.get("status") != "0x1":
        return net
    for lg in receipt.get("logs", []):
        t = lg.get("topics") or []
        if not t or t[0] != TRANSFER or len(t) < 3:
            continue
        a, b = "0x" + t[1][-40:], "0x" + t[2][-40:]
        if len(t) == 3:
            data = lg.get("data", "0x")
            amt = int(data, 16) if data and data != "0x" else 0
        else:
            amt = 1
        tok = lg["address"].lower()
        for addr, sgn in ((a, -1), (b, 1)):
            if addr == ZERO:
                continue
            net[(tok, addr)] = net.get((tok, addr), 0) + sgn * amt
    return net


def words(inp):
    s = (inp or "0x")[2:]
    body = s[8:]
    return {body[i:i + 64] for i in range(0, len(body) - 63, 64) if body[i:i + 64].strip("0")}


# ---------------------------------------------------------------- core analysis
def block_bundle(n):
    b = get_block(n)
    rc = get_receipts(n)
    for r in rc:
        r.setdefault("status", "0x1")  # pre-Byzantium receipts carry no status field
    rcm = {r["transactionHash"]: r for r in rc}
    return b, rcm


def victim_set(a_from, a_to, trace_f, receipt, dhl_victims, attacker_known):
    bset = {a_from, a_to} | trace_f["created"] | set(attacker_known)
    flows = token_flows(receipt)
    prof, by_tok = {}, {}
    for (tok, addr), v in flows.items():
        by_tok.setdefault(tok, {})[addr] = v
        if addr in bset:
            prof[tok] = prof.get(tok, 0) + v
    V = {}
    for tok, tot in prof.items():
        if tot <= 0:
            continue
        losers = sorted(((v, a) for a, v in by_tok[tok].items() if a not in bset and v < 0))[:3]
        for v, a in losers:
            V[a] = V.get(a, 0) + 1
    eth_tot = sum(v for a, v in trace_f["eth_net"].items() if a in bset)
    if eth_tot > 0:
        for v, a in sorted((v, a) for a, v in trace_f["eth_net"].items() if a not in bset and v < 0)[:3]:
            V[a] = V.get(a, 0) + 1
    ordered = [a for a, _ in sorted(V.items(), key=lambda kv: -kv[1])][:8]
    for a in dhl_victims:
        if a not in ordered and a not in bset:
            ordered.append(a)
    return ordered, {t: p for t, p in prof.items() if p > 0}


def scan_tx(h, meta):
    out = {"attack_tx": h, "exploit": meta.get("name"), "date": meta.get("date"), "file": meta.get("file")}
    tx = get_tx(h)
    if not tx:
        out["error"] = "tx not found on mainnet"
        return out
    B, A_idx = _h2i(tx["blockNumber"]), _h2i(tx["transactionIndex"])
    a_from, a_to = tx["from"].lower(), (tx.get("to") or "").lower()
    blocks = {}
    for n in (B - 2, B - 1, B, B + 1):
        blocks[n] = block_bundle(n)
    bB, rB = blocks[B]
    coinbase = bB["miner"].lower()
    base = _h2i(bB.get("baseFeePerGas"))
    receipt = rB[h]
    out.update(block=B, index=A_idx, attacker_from=a_from, attack_to=a_to, coinbase=coinbase,
               block_txcount=len(bB["transactions"]), status=receipt["status"])
    trace = get_trace(h)
    tf = trace_facts(trace, coinbase)
    dhl_att = {a.lower() for a in meta.get("attacker", []) + meta.get("attack_contract", [])}
    dhl_vic = [a.lower() for a in meta.get("victims", [])]
    V, prof = victim_set(a_from, a_to, tf, receipt, dhl_vic, dhl_att)
    # depth-1 callees of the attack contract that are neither tokens nor shared infra (e.g. the router/vault the
    # attack tx drives) join the "target" set so that attacks whose losers are individual users are still matched
    tok_addrs = {lg["address"].lower() for lg in receipt.get("logs", [])}
    t1c = {}
    for c in trace.get("calls") or []:
        x = (c.get("to") or "").lower()
        if x and c.get("type") not in ("CREATE", "CREATE2") and not c.get("error"):
            t1c[x] = t1c.get(x, 0) + 1
    T1 = [x for x, _ in sorted(t1c.items(), key=lambda kv: -kv[1])
          if x not in tok_addrs and x not in INFRA and x not in ROUTERS and x not in tf["created"]
          and x != a_from and x not in V][:4]
    V = V + T1
    Vs = set(V)
    # attacker's victim-facing signature: specific (victim, selector) pairs of successful calls
    sig_all = {(t, s) for (t, s, rev, ty, fr) in tf["calls"] if t in Vs and not rev and s}
    sig = {(t, s) for (t, s) in sig_all if s not in GENERIC_SEL} or sig_all
    att_vcalls = victim_calls(trace, Vs)
    a_words = words(tx["input"])
    eff = _h2i(receipt.get("effectiveGasPrice"))
    out.update(victims=V, depth1_targets_added=T1, profit_tokens=list(prof)[:6], signature=sorted(f"{t}:{s}" for t, s in sig)[:20],
               attacker_priority_gwei=round((eff - base) / 1e9, 4) if base else None,
               attacker_gas_price_gwei=round(eff / 1e9, 4), attacker_coinbase_paid_wei=tf["coinbase_paid"],
               created_contracts=sorted(tf["created"])[:10], attack_input_len=len(tx["input"]))
    same_actor = {a_from, a_to} | tf["created"] | dhl_att
    same_actor.discard("")
    # ---- window candidates
    cands = []
    own = 0
    popularity = 0
    for n in sorted(blocks):
        b, rc = blocks[n]
        pos_of = {t["hash"]: t["transactionIndex"] for t in b["transactions"]}
        to_counts = {}
        for t in b["transactions"]:
            to_counts[(t.get("to") or "").lower()] = to_counts.get((t.get("to") or "").lower(), 0) + 1
        for t in b["transactions"]:
            th = t["hash"]
            if th == h:
                continue
            frm, to = t["from"].lower(), (t.get("to") or "").lower()
            if frm == a_from:
                own += 1
                continue
            r = rc.get(th)
            if r is None:
                continue
            idx = _h2i(t["transactionIndex"])
            if n < B:
                rel = "earlier_block"
            elif n > B:
                rel = "next_block"
            else:
                rel = "same_block_before" if idx < A_idx else "same_block_after"
            ok = r["status"] == "0x1"
            logs_touch = 0
            for lg in r.get("logs", []):
                if lg["address"].lower() in Vs:
                    logs_touch += 1
                tp = lg.get("topics") or []
                if tp and tp[0] == TRANSFER and len(tp) >= 3 and ("0x" + tp[1][-40:] in Vs or "0x" + tp[2][-40:] in Vs):
                    logs_touch += 1
            w = words(t["input"])
            sim = len(w & a_words) / max(1, len(w | a_words)) if (w and a_words) else 0.0
            embed = len(tx["input"]) >= 250 and tx["input"][10:] in t["input"]
            sig_a = {"to_in_V": to in Vs, "to_attack_contract": bool(to) and to in same_actor,
                     "logs_touch_V": logs_touch, "input_sim": round(sim, 3), "embeds_attack_calldata": embed,
                     "embeds_attacker_addr": a_from[2:] in t["input"].lower()}
            if sig_a["to_in_V"] or logs_touch:
                popularity += 1
            pri = 0
            if sig_a["to_in_V"] or sig_a["to_attack_contract"] or sim >= 0.2 or embed or sig_a["embeds_attacker_addr"]:
                pri = 100
            elif logs_touch:
                pri = 50 if to not in ROUTERS else 40
            elif not ok and n == B:
                pri = 30
            elif rel == "same_block_before" and _h2i(r.get("gasUsed")) > 100000:
                pri = 20
            if not pri:
                continue
            closeness = -abs(n - B) * 1000 - abs(idx - A_idx)
            cands.append((pri, closeness, n, t, r, rel, sig_a, to_counts.get(to, 0)))
    cands.sort(key=lambda c: (-c[0], -c[1]))
    traced, sel = 0, []
    reverted_budget, prev_budget = 10, 8
    for c in cands:
        pri, _, n, t, r, rel, sig_a, _ = c
        if pri >= 50 or (pri == 30 and reverted_budget > 0) or (pri == 20 and prev_budget > 0):
            if pri == 30:
                reverted_budget -= 1
            if pri == 20:
                prev_budget -= 1
            if len(sel) < 28:
                sel.append(c)
    flagged = []
    for pri, _, n, t, r, rel, sig_a, to_count in sel:
        th = t["hash"]
        frm, to = t["from"].lower(), (t.get("to") or "").lower()
        try:
            tr = get_trace(th)
        except Exception as e:  # noqa: BLE001
            tr, terr = None, str(e)[:120]
        rec = {"tx": th, "block": n, "index": _h2i(t["transactionIndex"]), "relative": rel, "from": frm, "to": to,
               "status": "success" if r["status"] == "0x1" else "reverted", "gas_used": _h2i(r.get("gasUsed")),
               "signals": sig_a, "label_from": KNOWN_ADDR.get(frm), "label_to": KNOWN_ADDR.get(to),
               "txs_to_same_target_in_block": to_count}
        bn = blocks[n][0]
        eff_c = _h2i(r.get("effectiveGasPrice"))
        bf = _h2i(bn.get("baseFeePerGas"))
        rec["gas_price_gwei"] = round(eff_c / 1e9, 4)
        rec["priority_fee_gwei"] = round((eff_c - bf) / 1e9, 4) if bf else None
        rec["tx_type"] = t.get("type")
        if tr is None:
            rec["trace_error"] = terr
            tf2 = None
            sel_ov, calls_V, same_c = 0.0, 0, False
        else:
            tf2 = trace_facts(tr, bn["miner"].lower())
            sel_t = {(tt, s) for (tt, s, rev, ty, fr) in tf2["calls"] if tt in Vs and s}
            sel_t_ok = {(tt, s) for (tt, s, rev, ty, fr) in tf2["calls"] if tt in Vs and s and not rev}
            sel_ov_att = len(sig & sel_t) / len(sig) if sig else 0.0
            calls_V = sum(1 for (tt, s, rev, ty, fr) in tf2["calls"] if tt in Vs)
            same_c = bool((tf2["created"] | {to}) & (tf["created"] | {a_to})) or any(
                tt in tf["created"] for (tt, s, rev, ty, fr) in tf2["calls"])
            rec["trace"] = {"calls": len(tf2["calls"]), "calls_to_victims": calls_V,
                            "signature_overlap": round(sel_ov_att, 3),
                            "signature_overlap_success": round(len(sig & sel_t_ok) / len(sig), 3) if sig else 0.0,
                            "touches_attack_created_contracts": same_c,
                            "coinbase_payment_wei": tf2["coinbase_paid"], "top_level_error": tr.get("error"),
                            "top_level_value": _h2i(tr.get("value")), "created": sorted(tf2["created"])[:5]}
            sel_ov = sel_ov_att
        # victim outflow / net gains from logs
        nf = token_flows(r)
        actors = {frm, to} | (tf2["created"] if tf2 else set())
        gains = {}
        for (tok, addr), v in nf.items():
            if addr in actors and v != 0:
                gains[tok] = gains.get(tok, 0) + v
        vout = {tok: -v for (tok, addr), v in nf.items() if addr in Vs and v < 0}
        rec["victim_outflow_tokens"] = {k: str(v) for k, v in list(vout.items())[:6]}
        rec["net_token_gain_raw"] = {k: str(v) for k, v in sorted(gains.items(), key=lambda kv: -abs(kv[1]))[:6] if v}
        if tf2:
            eg = sum(v for a, v in tf2["eth_net"].items() if a in actors)
            rec["net_eth_wei_internal"] = str(eg)
        # ---- score
        sc, why = 0, []
        s = sig_a
        if rec.get("trace", {}).get("calls_to_victims") or s["to_in_V"]:
            sc += 2; why.append("touches victim contract(s)")
        near_f = exact_f = 0.0
        n_argcalls = 0
        if tr is not None:
            near_f, exact_f, n_argcalls = arg_match(att_vcalls, victim_calls(tr, Vs))
            rec["trace"]["victim_call_arg_match"] = {"near_identical_frac": round(near_f, 3),
                                                     "exact_frac": round(exact_f, 3), "attacker_distinct_calls": n_argcalls}
        if n_argcalls and near_f >= 0.5:
            sc += 5 if exact_f >= 0.5 else 4
            why.append(f"repeats {int(near_f*100)}% of attacker's victim calls with {'identical' if exact_f >= 0.5 else 'near-identical'} arguments")
        elif sel_ov >= 0.5:
            sc += 1; why.append(f"same victim-call selectors ({int(sel_ov*100)}%) but different arguments")
        elif sel_ov > 0:
            why.append(f"partial selector overlap {int(sel_ov*100)}%")
        if s["embeds_attack_calldata"]:
            sc += 3; why.append("calldata embeds the attacker's calldata")
        elif s["input_sim"] >= 0.3:
            sc += 2; why.append(f"calldata word-similarity {s['input_sim']}")
        if s["embeds_attacker_addr"]:
            sc += 1; why.append("calldata contains attacker address")
        if vout and any(v > 0 for k, v in gains.items() if k in vout):
            sc += 2; why.append("receives tokens that left the victim")
        if rec["status"] == "reverted" and (calls_V or s["to_in_V"] or sel_ov > 0 or s["input_sim"] >= 0.2):
            sc += 1; why.append("reverted tx aimed at the victim (lost gas war?)")
        if rel in ("same_block_before", "earlier_block"):
            sc += 1
        pf = rec["priority_fee_gwei"]
        if rec.get("trace", {}).get("coinbase_payment_wei", 0) > 0:
            sc += 1; why.append("pays block.coinbase directly (bundle-style)")
        flags = []
        if frm in dhl_att or to in dhl_att or rec.get("trace", {}).get("touches_attack_created_contracts") or s["to_attack_contract"]:
            sc -= 4; flags.append("possible_same_actor (shares attack contract / creations)")
        if rec["label_from"] or rec["label_to"]:
            flags.append("known_label")
        if rec.get("trace") and near_f < 0.5 and not s["embeds_attack_calldata"] and s["input_sim"] < 0.3:
            sc -= 2; flags.append("no_argument_match (likely ordinary pool user / arb)")
        if popularity > 40 and near_f < 0.5:
            sc -= 1; flags.append("victim_touched_by_many_txs")
        rec.update(score=sc, flags=flags, why=why)
        flagged.append(rec)
    flagged.sort(key=lambda r: -r["score"])
    out["popularity_of_victims_in_window"] = popularity
    out["attacker_own_other_txs_in_window"] = own
    out["candidates_prefiltered"] = len(cands)
    out["candidates_traced"] = len(sel)
    out["copycats"] = flagged
    return out


def categorize(c):
    """Interpretation layer on top of the raw score. Returns a list of category strings (empty = not a hit)."""
    t = c.get("trace") or {}
    am = t.get("victim_call_arg_match") or {}
    same_actor = any("possible_same_actor" in f for f in c.get("flags", []))
    sg = c["signals"]
    cats = []
    early = c["relative"] in ("earlier_block", "same_block_before")
    if c["status"] == "success" and am.get("near_identical_frac", 0) >= 0.5 and not same_actor:
        cats.append("replayed_attack_before" if early else "replayed_attack_after")
    if c["status"] == "reverted" and c["relative"] in ("same_block_before", "same_block_after", "earlier_block") \
            and (t.get("signature_overlap", 0) > 0 or am.get("near_identical_frac", 0) > 0 or sg["embeds_attack_calldata"]) \
            and not same_actor and not (t.get("calls_to_victims", 0) == 0 and not sg["embeds_attack_calldata"]):
        cats.append("gas_war_loser_candidate")
    if (sg["embeds_attack_calldata"] or sg["input_sim"] >= 0.5) and not same_actor and "gas_war_loser_candidate" not in cats \
            and "replayed_attack_before" not in cats and "replayed_attack_after" not in cats:
        cats.append("adapted_calldata")
    return cats


def tier(score):
    return "strong" if score >= 8 else "medium" if score >= 5 else "weak"


# ---------------------------------------------------------------- exploit list handling
def resolve_exploit_txs(exp):
    """verify each hash on mainnet; fills exp['tx_info']."""
    info = []
    for h in (exp["txs"] or exp.get("txs_unknown_chain") or []):
        try:
            t = get_tx(h)
        except Exception as e:  # noqa: BLE001
            t = None
        if t:
            info.append({"hash": h, "block": _h2i(t["blockNumber"]), "index": _h2i(t["transactionIndex"]),
                         "from": t["from"].lower(), "to": (t.get("to") or "").lower(), "on_mainnet": True})
        else:
            info.append({"hash": h, "on_mainnet": False})
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exploits")
    ap.add_argument("--out", default="scan_results.json")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--only")
    ap.add_argument("--tx", action="append")
    ap.add_argument("--max-txs-per-exploit", type=int, default=6)
    a = ap.parse_args()
    jobs = []
    if a.tx:
        jobs = [(h, {"name": h}) for h in a.tx]
    else:
        ex = json.load(open(a.exploits))
        ex = ex["exploits"] if isinstance(ex, dict) else ex
        ex = sorted(ex, key=lambda e: e.get("date") or "", reverse=True)
        for e in ex:
            if a.only and a.only.lower() not in (e.get("name", "") + e["file"] + " ".join(e.get("txs", []))).lower():
                continue
            hs = [i["hash"] for i in e.get("tx_info", []) if i.get("on_mainnet")] or e.get("txs", [])
            for h in hs[:a.max_txs_per_exploit]:
                jobs.append((h, e))
        if a.limit:
            jobs = jobs[:a.limit]
    results, done = {}, [0]
    outp = pathlib.Path(a.out)
    if outp.exists():
        try:
            results = {r["attack_tx"]: r for r in json.load(open(outp))}
        except Exception:  # noqa: BLE001
            results = {}

    def work(job):
        h, meta = job
        if h in results and "error" not in results[h]:
            return results[h]
        try:
            r = scan_tx(h, meta)
        except Exception as e:  # noqa: BLE001
            r = {"attack_tx": h, "exploit": meta.get("name"), "date": meta.get("date"), "file": meta.get("file"),
                 "error": f"{type(e).__name__}: {str(e)[:200]}"}
        with LOCK:
            results[h] = r
            done[0] += 1
            top = (r.get("copycats") or [{}])[0].get("score")
            print(f"[{done[0]}/{len(jobs)}] {meta.get('date')} {meta.get('name')} {h[:12]} "
                  f"{'ERR ' + r['error'] if 'error' in r else 'cands=%s top=%s' % (r.get('candidates_traced'), top)}",
                  flush=True)
            if done[0] % 10 == 0:
                outp.write_text(json.dumps(list(results.values()), indent=1))
        return r

    with cf.ThreadPoolExecutor(a.threads) as ex:
        list(ex.map(work, jobs))
    outp.write_text(json.dumps(list(results.values()), indent=1))
    print("wrote", outp, len(results))


if __name__ == "__main__":
    main()
