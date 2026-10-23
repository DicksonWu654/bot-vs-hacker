"""Shared helpers for the incident dataset master dataset (data/incidents.json).

Everything computed from race files (incidents/<slug>/race_<block>.json, schema bvh-race/1) goes through here so every
incident is measured the same way:

  auction_summary(race_path, bot_tx)         -> auction block of the schema (relays, bids, winner, runner-up, escalation)
  escalation(race, max_points=60)            -> [[t_rel_slot_ms, eth], ...] record-bid curve, slot start = genesis + 12*slot
  detection(race_path, trigger_ms, bot_tx)   -> detection delay (two labelled methods)
  RawRefs                                    -> collects {field: data/raw/... path}, verifies the file exists

Definitions (also written into data/incidents.json -> _meta.definitions):
  slot start         = 1606824023 + 12 * slot  (== block timestamp of the block built for that slot)
  record-bid curve   = bids (all answering relays, ordered by relay receive time) that exceed every earlier bid
  winning_bid_eth    = value of the delivered payload (relay proposer_payload_delivered) == builder->proposer payment tx
  runner_up_eth      = best bid for a DIFFERENT block hash that arrived no later than the last submission of the winning
                       hash (a bid that arrives later could not have been compared by the proposer in the same query)
  runner_up_other_builder_eth = same, restricted to a different builder (pubkey and name) than the winner
  detection (a)      = first record bid at/after the trigger whose value >= max(5 x pre-trigger best bid, 0.5 ETH)
                       ("first-big-bid-jump", block contents unknown)
  detection (c)      = first bid of the WINNING builder's pubkey after the trigger worth >= max(2 x its own best pre-trigger bid,
                       0.5 ETH) ("winning-builder-first-stepup", contents unknown; PRIMARY when it exists)
  detection (b)      = first submission of the winning block hash minus trigger ("winning-block-first-submission",
                       contents verified: it is an UPPER bound on when the bot's builder first had the bot tx in a bid)
"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
GENESIS = 1606824023


def load(path):
    p = pathlib.Path(path)
    if not p.is_absolute():
        p = ROOT / p
    if not p.exists() and "data/raw/" in str(path):
        p = ROOT / "site/raw" / str(path).split("data/raw/", 1)[1]
    return json.load(open(p))


def exists(rel):
    return (ROOT / rel).exists()


class RawRefs(dict):
    """dict field -> repo-relative path under data/raw (or incidents/ for derived race files). Use .add(field, path)."""
    missing = None

    def __init__(self):
        super().__init__()
        self.missing = []

    def add(self, field, path):
        if path is None:
            return
        if not (ROOT / path).exists():
            self.missing.append({"field": field, "path": path})
        self[field] = path
        return path


def slot_start_ms(slot):
    return (GENESIS + 12 * int(slot)) * 1000


def escalation(race, max_points=60):
    bs = race.get("bid_summary") or {}
    rec = bs.get("record_bids")
    if rec is None:
        bids = sorted(race.get("bids") or [], key=lambda b: b["timestamp_ms"])
        rec, best = [], -1.0
        for b in bids:
            if b["value_eth"] > best:
                best = b["value_eth"]
                rec.append(b)
    pts = [[r["t_rel_slot_ms"], r["value_eth"]] for r in rec]
    if len(pts) <= max_points:
        return pts
    inner = list(range(1, len(pts) - 1))
    inner.sort(key=lambda i: pts[i][1] - pts[i - 1][1], reverse=True)
    keep = sorted(set([0, len(pts) - 1] + inner[: max_points - 2]))
    return [pts[i] for i in keep]


def _relays(race):
    out = []
    for name, st in (race.get("relays_status") or {}).items():
        if (st.get("bids_n") or 0) > 0 or (st.get("delivered_n") or 0) > 0:
            out.append(name)
    return out


def auction_summary(race_path, bot_tx=None):
    race = load(race_path)
    rr = RawRefs()
    rr.add("race_file", race_path)
    bs = race.get("bid_summary") or {}
    bids = race.get("bids") or []
    win = race.get("winner") or {}
    wh = None
    for b in bids:
        if b.get("is_winning_block"):
            wh = b["block_hash"]
            break
    if wh is None and race.get("delivered"):
        wh = race["delivered"][0].get("block_hash")
    wsubs = [b for b in bids if wh and b["block_hash"] == wh]
    wsubs.sort(key=lambda b: b["timestamp_ms"])
    win_first = wsubs[0]["t_rel_slot_ms"] if wsubs else None
    win_last = wsubs[-1]["t_rel_slot_ms"] if wsubs else None
    ru = None
    if wh and win_last is not None:
        cand = [b for b in bids if b["block_hash"] != wh and b["t_rel_slot_ms"] <= win_last]
        if cand:
            ru = max(cand, key=lambda b: b["value_eth"])
    ru2 = None
    if wh and win_last is not None:
        wname = win.get("builder_name")
        wpk = win.get("builder_pubkey")
        cand2 = [b for b in bids if b["block_hash"] != wh and b["t_rel_slot_ms"] <= win_last and b["builder_pubkey"] != wpk
                 and not (wname and b.get("builder_name") == wname)]
        if cand2:
            ru2 = max(cand2, key=lambda b: b["value_eth"])
    wval = win.get("bid_value_eth")
    late_higher = [b for b in bids if wval is not None and b["value_eth"] > wval and win_last is not None and b["t_rel_slot_ms"] > win_last]
    in_block = None
    if bot_tx:
        in_block = any(t["hash"].lower() == bot_tx.lower() for t in race.get("txs", []))
    for r in race.get("raw_refs", {}).items():
        pass
    for rname, st in (race.get("relays_status") or {}).items():
        if (st.get("bids_n") or 0) > 0 and st.get("raw_bids"):
            rr.add(f"relay_bids:{rname}", st["raw_bids"])
        if (st.get("delivered_n") or 0) > 0 and st.get("raw_delivered"):
            rr.add(f"relay_delivered:{rname}", st["raw_delivered"])
    caps = [c for c in race.get("caveats", []) if "cap" in c.lower() or "truncat" in c.lower()]
    a = {
        "block": race["block"]["number"], "slot": race["block"].get("slot"),
        "slot_start_utc_ms": slot_start_ms(race["block"]["slot"]) if race["block"].get("slot") else None,
        "relays_answered": _relays(race),
        "n_bids": bs.get("n_bids"), "n_builders": bs.get("n_builders"),
        "bids_per_relay": bs.get("bids_per_relay"),
        "first_bid_ms_rel_slot": bs.get("first_bid_t_rel_slot_ms"), "last_bid_ms_rel_slot": bs.get("last_bid_t_rel_slot_ms"),
        "winning_bid_eth": wval, "winning_builder": win.get("builder_name"),
        "winning_builder_pubkey": win.get("builder_pubkey"), "winning_relays": win.get("delivered_by_relays"),
        "winning_first_submission_ms_rel_slot": win_first, "winning_last_submission_ms_rel_slot": win_last,
        "runner_up_eth": ru["value_eth"] if ru else None,
        "runner_up_builder": (ru or {}).get("builder_name"), "runner_up_ms_rel_slot": (ru or {}).get("t_rel_slot_ms"),
        "runner_up_other_builder_eth": ru2["value_eth"] if ru2 else None,
        "runner_up_other_builder": (ru2 or {}).get("builder_name") or ((ru2 or {}).get("builder_pubkey", "") or "")[:12] or None,
        "runner_up_other_builder_ms_rel_slot": (ru2 or {}).get("t_rel_slot_ms"),
        "n_higher_bids_after_winner": len(late_higher),
        "max_bid_eth": bs.get("max_bid_eth"),
        "proposer_paid_eth": wval if (win.get("proposer_payment_tx") or {}).get("matches_bid_value") else None,
        "proposer_payment_tx": (win.get("proposer_payment_tx") or {}).get("hash"),
        "bot_tx_in_winning_block": in_block,
        "escalation": escalation(race),
        "bid_data_note": ("; ".join(caps) if caps else None),
    }
    if wh is None or not bids:
        a["bid_data_note"] = ((a["bid_data_note"] + "; ") if a["bid_data_note"] else "") + "no bid history available for this block (pre-Merge or relays hold no data)"
    a["raw_refs"] = dict(rr)
    a["_missing_raw"] = rr.missing
    return a


def detection(race_path, trigger_ms, bot_tx=None):
    """trigger_ms = unix ms when the attacker (or user) tx was first seen in the public mempool (measured)."""
    race = load(race_path)
    slot = race["block"]["slot"]
    rel = trigger_ms - slot_start_ms(slot)
    bids = sorted(race.get("bids") or [], key=lambda b: b["timestamp_ms"])
    if not bids:
        return None
    pre = [b["value_eth"] for b in bids if b["t_rel_slot_ms"] <= rel]
    base = max(pre) if pre else 0.0
    thr = max(5 * base, 0.5)
    best = -1.0
    jump = None
    for b in bids:
        if b["value_eth"] > best:
            best = b["value_eth"]
            if b["t_rel_slot_ms"] >= rel and b["value_eth"] >= thr and jump is None:
                jump = b
    wh = next((b["block_hash"] for b in bids if b.get("is_winning_block")), None)
    wpk = (race.get("winner") or {}).get("builder_pubkey")
    bstep = None
    if wpk:
        mine = [b for b in bids if b["builder_pubkey"] == wpk]
        mpre = [b["value_eth"] for b in mine if b["t_rel_slot_ms"] <= rel]
        mthr = max(2 * (max(mpre) if mpre else 0.0), 0.5)
        bstep = next((b for b in mine if b["t_rel_slot_ms"] > rel and b["value_eth"] >= mthr), None)
    first_win = next((b for b in bids if wh and b["block_hash"] == wh), None)
    out = {
        "trigger_ms_rel_slot": rel,
        "baseline_best_bid_eth": base, "jump_threshold_eth": thr,
        "winning_builder_first_stepup": ({"ms_rel_slot": bstep["t_rel_slot_ms"], "eth": bstep["value_eth"], "builder": bstep.get("builder_name"),
                                          "relay": bstep["relay"], "delay_ms": bstep["t_rel_slot_ms"] - rel} if bstep else None),
        "first_big_jump": ({"ms_rel_slot": jump["t_rel_slot_ms"], "eth": jump["value_eth"], "builder": jump.get("builder_name"),
                            "relay": jump["relay"], "delay_ms": jump["t_rel_slot_ms"] - rel} if jump else None),
        "first_winning_block_submission": ({"ms_rel_slot": first_win["t_rel_slot_ms"], "eth": first_win["value_eth"],
                                            "builder": first_win.get("builder_name"), "delay_ms": first_win["t_rel_slot_ms"] - rel} if first_win else None),
    }
    return out
