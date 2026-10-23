#!/usr/bin/env python3
"""Rebuild "the race" for one block: ordered transactions + builder auction + mempool first-seen -> race.json.

    blockrace.py BLOCK [--focus HASH ...] [--watch ADDR ...] [--slug curve-vyper-2023] [--out PATH]
                       [--no-mempool] [--no-names]

Output default: incidents/<slug>/race.json (or incidents/_scratch/race_<BLOCK>.json without --slug).

What it combines (every value has a pointer into data/raw via `raw_refs`, see bottom of the file):
  * RPC (eth.drpc.org): block with full txs, eth_getBlockReceipts, debug_traceBlockByNumber(callTracer)
        -> per-tx index/from/to/status/gas price/priority fee/coinbase transfer (value sent to block.miner by successful calls)
  * Relay data API on every relay (relays.py): proposer_payload_delivered (who delivered the block) and
        builder_blocks_received (every bid: timestamp_ms, builder pubkey, value, block_hash, num_tx, gas_used)
  * mempool-dumpster (mempool.py) first-seen per focus tx, when the block's UTC day is >= 2023-08-07; otherwise
        the focus tx is recorded as "in-block evidence only" (no mempool archive exists for that day)
  * Pre-Merge blocks (< 15537394): the Flashbots blocks API (https://blocks.flashbots.net, HTTP 410 since decommission)
        is tried and its answer recorded; if dead, bundle structure is only *inferred* from traces (flagged `inferred`).

What is NOT knowable from public data (recorded in `caveats`): the contents of losing bids. Relays publish only
block_hash/num_tx/gas_used/value for builder_blocks_received, never the transactions, so "did bid X contain the focus
tx?" is `unknown` for every bid except the winning block hash (whose contents we have on-chain).
"""
import argparse, datetime as dt, json, pathlib, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
sys.path.insert(0, str(HERE))
import rawfetch as rf  # noqa: E402
import relays  # noqa: E402
import mempool  # noqa: E402

SCHEMA = "bvh-race/1"


def hx(x):
    return int(x, 16) if isinstance(x, str) and x.startswith("0x") else (int(x) if x is not None else None)


def walk_trace(frame, miner, addrs, out, ok=True):
    """Collect (a) all addresses touched, (b) total wei sent to `miner` by calls that did not revert.
    A frame with an `error` reverts its whole subtree."""
    ok_here = ok and not frame.get("error")
    for k in ("from", "to"):
        if frame.get(k):
            addrs.add(frame[k].lower())
    if ok_here and frame.get("to") and frame["to"].lower() == miner and frame.get("type") in ("CALL", "CALLCODE", "SELFDESTRUCT", None):
        out[0] += hx(frame.get("value", "0x0")) or 0
    for c in frame.get("calls", []) or []:
        walk_trace(c, miner, addrs, out, ok_here)


def watch_calls(frame, watch, out, depth=0, parent_ok=True):
    """Calls INTO watched addresses (selector, value, caller, reverted?) - for describing public interactions with a pool."""
    ok = parent_ok and not frame.get("error")
    if frame.get("to") and frame["to"].lower() in watch:
        out.append({"depth": depth, "type": frame.get("type"), "caller": frame.get("from", "").lower(), "to": frame["to"].lower(),
                    "selector": (frame.get("input") or "")[:10], "value_eth": (hx(frame.get("value", "0x0")) or 0) / 1e18,
                    "reverted": not ok, "error": frame.get("error")})
    for c in frame.get("calls", []) or []:
        watch_calls(c, watch, out, depth + 1, ok)
    return out


def trace_block(number, txs):
    """debug_traceBlockByNumber(callTracer); falls back to per-tx debug_traceTransaction."""
    key = f"trace_block_{number}"
    try:
        res = rf.rpc("debug_traceBlockByNumber", [hex(number), {"tracer": "callTracer"}], key=key, timeout=110, retries=2)
        by_hash = {r["txHash"].lower(): r.get("result") for r in res}
        return by_hash, {"mode": "block", "raw": rf.raw_path("rpc", key)}
    except Exception as e:  # noqa: BLE001
        print(f"[warn] block trace failed ({str(e)[:120]}); falling back to per-tx traces", file=sys.stderr)

    def one(t):
        h = t["hash"].lower()
        return h, rf.rpc("debug_traceTransaction", [h, {"tracer": "callTracer"}], key=f"trace_{h}")

    with ThreadPoolExecutor(max_workers=8) as ex:
        by_hash = dict(ex.map(one, txs))
    return by_hash, {"mode": "per-tx", "raw": {h: rf.raw_path("rpc", f"trace_{h}") for h in by_hash}}


def build_txs(block, receipts, traces, miner, watch, focus):
    base = hx(block["baseFeePerGas"]) if block.get("baseFeePerGas") else 0
    rc = {r["transactionHash"].lower(): r for r in receipts}
    rows = []
    for t in block["transactions"]:
        h = t["hash"].lower()
        r = rc.get(h, {})
        tr = traces.get(h)
        addrs, cb = set(), [0]
        if tr:
            walk_trace(tr, miner, addrs, cb)
        egp = hx(r.get("effectiveGasPrice")) if r else None
        gas_used = hx(r.get("gasUsed")) if r else None
        prio_pg = (egp - base) if egp is not None else None
        row = {
            "index": hx(t["transactionIndex"]), "hash": h, "from": t["from"].lower(), "to": (t["to"] or "").lower() or None,
            "type": hx(t.get("type")), "status": hx(r.get("status")) if r else None,
            "value_wei": str(hx(t["value"])), "selector": t["input"][:10] if len(t["input"]) >= 10 else None,
            "gas_used": gas_used, "gas_price_gwei": egp / 1e9 if egp is not None else None,
            "max_fee_gwei": hx(t["maxFeePerGas"]) / 1e9 if t.get("maxFeePerGas") else None,
            "max_priority_fee_gwei": hx(t["maxPriorityFeePerGas"]) / 1e9 if t.get("maxPriorityFeePerGas") else None,
            "priority_fee_gwei": prio_pg / 1e9 if prio_pg is not None else None,
            "priority_fee_total_wei": str(prio_pg * gas_used) if prio_pg is not None and gas_used is not None else None,
            "coinbase_transfer_wei": str(cb[0]) if tr else None,
            "builder_revenue_wei": str(cb[0] + (prio_pg * gas_used)) if tr and prio_pg is not None and gas_used is not None else None,
            "trace_top_error": (tr or {}).get("error"),
            "n_addresses_touched": len(addrs) if tr else None,
        }
        if watch:
            row["touches_watch"] = sorted(a for a in watch if a in addrs)
        if h in focus:
            row["focus"] = True
            if watch and tr:
                row["watch_calls"] = watch_calls(tr, set(watch), [])
        rows.append(row)
    return rows


def relay_section(block_number, slot, slot_t0, do_names, winner_hash, winner_has_focus):
    data = relays.fetch_block(block_number)
    status, deliveries, bids, offslot = {}, [], [], []
    for rname, v in data["relays"].items():
        d, b = v["delivered"], v["bids"]
        status[rname] = {"host": v["host"],
                         "delivered_http": d["status"], "delivered_n": None if d["items"] is None else len(d["items"]),
                         "bids_http": b["status"], "bids_n": None if b["items"] is None else len(b["items"]),
                         "error": d["error"] or b["error"], "raw_delivered": d["raw"], "raw_bids": b["raw"],
                         "note": relays.BY_NAME[rname]["notes"]}
        if b.get("truncated_warning"):
            status[rname]["warning"] = b["truncated_warning"]
        for it in d["items"] or []:
            deliveries.append({"relay": rname, **{k: it[k] for k in ("slot", "block_hash", "builder_pubkey", "proposer_pubkey",
                               "proposer_fee_recipient", "value", "num_tx", "gas_used", "block_number") if k in it},
                               "raw": d["raw"]})
        for it in b["items"] or []:
            if it.get("slot") is not None and str(it["slot"]) != str(slot):
                # the relay API filters by block number, so a row can belong to another slot (a competing proposal for the same height)
                offslot.append({"relay": rname, "slot": it["slot"], "block_hash": it.get("block_hash"), "builder_pubkey": it.get("builder_pubkey"),
                                "value_wei": it.get("value"), "timestamp_ms": it.get("timestamp_ms")})
                continue
            ts_ms = int(it["timestamp_ms"]) if it.get("timestamp_ms") else (int(it["timestamp"]) * 1000 if it.get("timestamp") else None)
            bids.append({"relay": rname, "timestamp_ms": ts_ms, "t_rel_slot_ms": (ts_ms - slot_t0 * 1000) if ts_ms is not None else None,
                         "builder_pubkey": it["builder_pubkey"], "value_wei": it["value"], "value_eth": int(it["value"]) / 1e18,
                         "block_hash": it["block_hash"], "num_tx": int(it["num_tx"]), "gas_used": int(it["gas_used"]),
                         "optimistic": it.get("optimistic_submission"), "parent_hash": it.get("parent_hash"),
                         "is_winning_block": it["block_hash"].lower() == winner_hash.lower(),
                         "contains_focus_txs": winner_has_focus if it["block_hash"].lower() == winner_hash.lower() else "unknown",
                         "raw": b["raw"]})
    bids.sort(key=lambda x: (x["timestamp_ms"] is None, x["timestamp_ms"] or 0))
    # builder names
    pubkeys = sorted({b["builder_pubkey"] for b in bids} | {d["builder_pubkey"] for d in deliveries})
    names = {}
    if do_names and pubkeys:
        def one(pk):
            return pk, relays.resolve_builder_names([pk], hint_block=block_number)[pk]
        with ThreadPoolExecutor(max_workers=6) as ex:
            names = dict(ex.map(one, pubkeys))
    for b in bids:
        n = names.get(b["builder_pubkey"])
        b["builder_name"] = n["name"] if n else None
    for d in deliveries:
        n = names.get(d["builder_pubkey"])
        d["builder_name"] = n["name"] if n else None
    # escalation = bids that set a new record value (across all relays), in time order
    best, esc = 0, []
    for b in bids:
        v = int(b["value_wei"])
        if v > best:
            best = v
            esc.append({"timestamp_ms": b["timestamp_ms"], "t_rel_slot_ms": b["t_rel_slot_ms"], "relay": b["relay"],
                        "builder_pubkey": b["builder_pubkey"], "builder_name": b["builder_name"], "value_eth": b["value_eth"],
                        "block_hash": b["block_hash"], "is_winning_block": b["is_winning_block"]})
    win_bids = [b for b in bids if b["is_winning_block"]]
    summary = {
        "n_bids": len(bids), "n_builders": len({b["builder_pubkey"] for b in bids}),
        "bids_per_relay": {r: s["bids_n"] - sum(1 for o in offslot if o["relay"] == r) for r, s in status.items() if s["bids_n"]},
        "n_offslot_excluded": len(offslot), "offslot_excluded": offslot,
        "first_bid_t_rel_slot_ms": bids[0]["t_rel_slot_ms"] if bids else None,
        "last_bid_t_rel_slot_ms": bids[-1]["t_rel_slot_ms"] if bids else None,
        "max_bid_eth": max((b["value_eth"] for b in bids), default=None),
        "winning_block_submissions": [{"relay": b["relay"], "t_rel_slot_ms": b["t_rel_slot_ms"], "value_eth": b["value_eth"]} for b in win_bids],
        "record_bids": esc,
        "n_record_bids": len(esc),
    }
    return {"relays_status": status, "delivered": deliveries, "bids": bids, "summary": summary, "builder_names": names}


def run(block_number, focus=(), watch=(), slug=None, out=None, do_mempool=True, do_names=True):
    focus = [f.lower() for f in focus]
    watch = [w.lower() for w in watch]
    block = rf.rpc("eth_getBlockByNumber", [hex(block_number), True], key=f"block_{block_number}")
    if block is None:
        raise SystemExit(f"block {block_number} not found")
    receipts = rf.rpc("eth_getBlockReceipts", [hex(block_number)], key=f"receipts_{block_number}", timeout=110)
    miner = block["miner"].lower()
    ts = hx(block["timestamp"])
    post_merge = block_number >= relays.MERGE_BLOCK
    traces, trace_meta = trace_block(block_number, block["transactions"])
    txs = build_txs(block, receipts, traces, miner, watch, set(focus))
    extra = relays._decode_extra(block["extraData"])
    caveats = []
    raw_refs = {
        "block": rf.raw_path("rpc", f"block_{block_number}"), "receipts": rf.raw_path("rpc", f"receipts_{block_number}"),
        "traces": trace_meta["raw"],
        "block.timestamp|miner|extraData|baseFeePerGas|txs[].from|to|index|value|gas_price|max_fee|max_priority_fee": rf.raw_path("rpc", f"block_{block_number}"),
        "txs[].status|gas_used|gas_price_gwei(effectiveGasPrice)": rf.raw_path("rpc", f"receipts_{block_number}"),
        "txs[].coinbase_transfer_wei|touches_watch|trace_top_error": trace_meta["raw"],
        "slot|slot_start": "derived: (block.timestamp - 1606824023) / 12 (beacon genesis 2020-12-01T12:00:23Z)",
    }
    race = {
        "schema": SCHEMA, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "slug": slug,
        "block": {
            "number": block_number, "hash": block["hash"], "parent_hash": block["parentHash"], "timestamp": ts,
            "timestamp_utc": dt.datetime.fromtimestamp(ts, dt.UTC).isoformat(), "fee_recipient": miner,
            "extra_data": extra, "extra_data_name": relays.alias_from_extradata(extra),
            "base_fee_gwei": hx(block["baseFeePerGas"]) / 1e9 if block.get("baseFeePerGas") else None,
            "gas_used": hx(block["gasUsed"]), "gas_limit": hx(block["gasLimit"]), "tx_count": len(block["transactions"]),
            "era": "post-merge" if post_merge else "pre-merge (PoW)",
        },
        "focus_txs": focus, "watch_addresses": watch, "txs": txs, "caveats": caveats,
    }
    if post_merge:
        slot = relays.slot_of_ts(ts)
        slot_t0 = relays.slot_start(slot)
        race["block"].update({"slot": slot, "slot_start_unix": slot_t0})
        in_block = {t["hash"] for t in txs}
        rs = relay_section(block_number, slot, slot_t0, do_names, block["hash"], all(f in in_block for f in focus) if focus else None)
        race.update({"relays_status": rs["relays_status"], "delivered": rs["delivered"], "bids": rs["bids"],
                     "bid_summary": rs["summary"], "builder_names": rs["builder_names"]})
        for rn, s in rs["relays_status"].items():
            raw_refs[f"relay.{rn}.delivered"] = s["raw_delivered"]
            raw_refs[f"relay.{rn}.bids"] = s["raw_bids"]
        raw_refs["bids[]|delivered[] (each row also has `raw`)"] = "see relay.<name>.bids / relay.<name>.delivered"
        raw_refs["builder_names"] = {pk: v.get("relay_raw") for pk, v in rs["builder_names"].items() if v and v.get("relay_raw")}
        raw_refs["builder_alias_rules"] = "data/raw/relay-sources/relayscan_vars_builder_aliases.go.txt"
        win = [d for d in rs["delivered"] if d["block_hash"].lower() == block["hash"].lower()]
        race["winner"] = {
            "delivered_by_relays": sorted({d["relay"] for d in win}),
            "builder_pubkey": win[0]["builder_pubkey"] if win else None, "builder_name": win[0]["builder_name"] if win else None,
            "bid_value_wei": win[0]["value"] if win else None,
            "bid_value_eth": int(win[0]["value"]) / 1e18 if win else None,
            "proposer_fee_recipient": win[0]["proposer_fee_recipient"] if win else None,
            "proposer_pubkey": win[0]["proposer_pubkey"] if win else None,
        }
        if win:
            pay = [t for t in txs if t["from"] == miner and t["to"] == win[0]["proposer_fee_recipient"].lower()]
            if pay:
                p = pay[-1]
                race["winner"]["proposer_payment_tx"] = {"hash": p["hash"], "index": p["index"], "value_wei": p["value_wei"],
                                                          "matches_bid_value": p["value_wei"] == win[0]["value"]}
        else:
            caveats.append("No relay reports delivering this block hash: privately built / vanilla (non-MEV-Boost) block, or the "
                           "delivering relay no longer serves this slot.")
        caveats.append("Losing bids: relays expose only block_hash/num_tx/gas_used/value for builder_blocks_received, never the "
                       "transactions, so `contains_focus_txs` is `unknown` for every bid except the winning block hash.")
        caveats.append("Bid timestamps are each relay's own receive clock (ms); t_rel_slot_ms is relative to slot start "
                       "(genesis+12*slot). Cross-relay comparison carries the relays' clock skew and network latency.")
        for rn, s in rs["relays_status"].items():
            if s["error"] or s["delivered_n"] == 0 and s["bids_n"] == 0:
                caveats.append(f"relay {rn}: {'unreachable (' + s['error'] + ')' if s['error'] else 'answered but holds no data for this block (did not receive any bid, or dropped old data)'}")
    else:
        race["block"].update({"slot": None})
        fb = rf.get_soft(f"https://blocks.flashbots.net/v1/blocks?block_number={block_number}", source="flashbots-blocks-api",
                         key=f"blocks_{block_number}")
        race["premerge"] = {
            "flashbots_blocks_api": {"http": fb["status"], "raw": fb["path"], "body": (fb["json"] if fb["status"] == 200 else (fb["body"][:200].decode("utf8", "replace")))},
            "note": "Pre-Merge: no relays/slots. Flashbots MEV-geth bundles. blocks.flashbots.net answers HTTP 410 (decommissioned); "
                    "bundle membership below is INFERRED (`inferred_bundle_like`) from coinbase transfers + gas price, not authoritative.",
        }
        raw_refs["premerge.flashbots_blocks_api"] = fb["path"]
        if fb["status"] == 200 and isinstance(fb["json"], dict):
            members = {t["transaction_hash"].lower(): t for b in fb["json"].get("blocks", []) for t in b.get("transactions", [])}
            for t in txs:
                m = members.get(t["hash"])
                t["flashbots"] = ({"bundle_type": m.get("bundle_type"), "bundle_index": m.get("bundle_index"),
                                   "coinbase_transfer": m.get("coinbase_transfer")} if m else None)
        else:
            for t in txs:
                cbt = int(t["coinbase_transfer_wei"] or 0)
                t["inferred_bundle_like"] = bool(cbt > 0 and (t["priority_fee_gwei"] or 0) < 1)
            caveats.append("Flashbots blocks API is dead (HTTP 410); bundle flags are heuristics (coinbase transfer > 0 and priority fee < 1 gwei).")
    # mempool
    if do_mempool and focus:
        day = dt.datetime.fromtimestamp(ts, dt.UTC).date()
        cov = mempool.coverage(day)
        race["mempool"] = {"date": str(day), "coverage": cov, "txs": {}}
        if cov["covered"]:
            lk = mempool.lookup(str(day), focus)
            race["mempool"]["txs"] = lk["txs"]
            for h, v in lk["txs"].items():
                if v:
                    v["seen_before_block_ms"] = ts * 1000 - v["first_seen_ms"]
                    raw_refs[f"mempool.{h}"] = v["raw_refs"]
                    if not v["in_tx_file"] and v["in_sourcelog"]:
                        v["note"] = "only in sourcelog (already on-chain when received)"
                else:
                    race["mempool"]["txs"][h] = {"seen": False, "note": "not in mempool-dumpster for that day: private order flow / "
                                                 "bundle, or sources missed it. Unknown != none."}
            raw_refs["mempool.index"] = cov.get("index_raw")
        else:
            race["mempool"]["evidence_level"] = "in-block evidence only"
            race["mempool"]["txs"] = {h: {"seen": None, "note": cov["reason"]} for h in focus}
            caveats.append(f"Mempool: in-block evidence only - {cov['reason']}")
    # focus summary: where each focus tx sat and what it paid the builder, relative to the winning bid
    fs = []
    byh = {t["hash"]: t for t in txs}
    bid_wei = int(race["winner"]["bid_value_wei"]) if race.get("winner", {}).get("bid_value_wei") else None
    for h in focus:
        t = byh.get(h)
        if not t:
            fs.append({"hash": h, "in_block": False})
            continue
        rev = int(t["builder_revenue_wei"]) if t["builder_revenue_wei"] is not None else None
        fs.append({"hash": h, "in_block": True, "index": t["index"], "of": len(txs), "status": t["status"], "from": t["from"], "to": t["to"],
                   "priority_fee_gwei": t["priority_fee_gwei"], "coinbase_transfer_eth": int(t["coinbase_transfer_wei"] or 0) / 1e18,
                   "builder_revenue_eth": rev / 1e18 if rev is not None else None,
                   "share_of_winning_bid": (rev / bid_wei) if (rev is not None and bid_wei) else None,
                   "watch_calls": t.get("watch_calls")})
    race["focus_summary"] = fs
    race["raw_refs"] = raw_refs
    if out is None:
        d = rf.ROOT / "incidents" / (slug or "_scratch")
        out = d / ("race.json" if slug else f"race_{block_number}.json")
    out = pathlib.Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(race, indent=1))
    return race, out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("block", type=int)
    ap.add_argument("--focus", nargs="*", default=[])
    ap.add_argument("--watch", nargs="*", default=[])
    ap.add_argument("--slug")
    ap.add_argument("--out")
    ap.add_argument("--no-mempool", action="store_true")
    ap.add_argument("--no-names", action="store_true")
    a = ap.parse_args()
    race, out = run(a.block, a.focus, a.watch, a.slug, a.out, not a.no_mempool, not a.no_names)
    b = race["block"]
    print(f"wrote {out}  block {b['number']} slot {b.get('slot')} {b['timestamp_utc']} txs={b['tx_count']}")
    if "bid_summary" in race:
        s = race["bid_summary"]
        print(f"bids={s['n_bids']} builders={s['n_builders']} record_bids={s['n_record_bids']} winner={race['winner']}")


if __name__ == "__main__":
    main()
