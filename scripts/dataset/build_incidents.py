"""incident dataset merge: data/extract/*.json (per-incident facts) + harmonize_rules -> data/incidents.json, comparison_table.csv,
headline_stats.json, harmonize_log.json, rawref_audit.json, and the write-back of race_type/verdict/headline into incidents/*/incident.json.

Run from project root:  .venv/bin/python scripts/dataset/build_incidents.py [--no-writeback]
"""
import csv, datetime as dt, glob, json, pathlib, statistics, sys, copy
if "--no-writeback" in sys.argv:
    sys.dont_write_bytecode = True
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import bvh
from publication import scrub_public
from harmonize_rules import RULES, HEADLINE_TYPES, HEADLINE_NOTES, STRENGTH, ONE_LINER_FIXES
import returns_schema as RS   # explicit return denominators + 2026-10-21 chain corrections
import launch_decisions as LD
from returns_schema import RETURNS_DECISIONS

ROOT = bvh.ROOT
MERGE_BLOCK = 15537394
ERA_ORDER = ["pre-2021", "mev-geth-2021-22", "early-pbs-2022-23", "mature-pbs-2024-26"]
ORDER = {"slug": 0}
GAS_NOTE = "priority_fee_paid_eth is the bot tx's own gas priority fee"


def era_of(date_utc, block):
    d = date_utc[:10]
    if d < "2021-01-01":
        return "pre-2021"
    if block < MERGE_BLOCK:
        return "mev-geth-2021-22"
    if d < "2024-01-01":
        return "early-pbs-2022-23"
    return "mature-pbs-2024-26"


def num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def pct(a, b):
    a, b = num(a), num(b)
    if a is None or not b:
        return None
    return round(100.0 * a / b, 3)


def ordering(row):
    b = row["bot"].get("block")
    if b is None:
        return None
    ab = row.get("attacker_block")
    ref = row.get("attacker_reference") or {}
    if ab is None:
        if ref.get("kind") in ("deploy", "prepare", "upgrade"):
            return "before-attacker-call-landed (never landed; bot %d block(s) after %s)" % (b - ref["block"], ref["kind"]) if ref.get("block") else "before-attacker-call-landed"
        return None
    if b < ab:
        return "earlier-block"
    if b > ab:
        return "later-block"
    aidx = None
    for t in (row["attacker"].get("attack_txs") or []):
        if t.get("block") == ab and t.get("index") is not None:
            aidx = t["index"] if aidx is None else min(aidx, t["index"]) if t.get("status") != "never-landed" else aidx
    if aidx is not None and row["bot"]["position"] is not None:
        return "same-block-earlier-index" if row["bot"]["position"] < aidx else "same-block-later-index"
    return "same-block"


def detection(row):
    tr = row.get("trigger") or {}
    ms = tr.get("first_seen_utc_ms")
    rf = (row.get("auction") or {}).get("raw_refs", {}).get("race_file")
    out = {"attacker_first_seen_utc_ms": None, "bot_first_bid_utc_ms": None, "detection_delay_ms": None,
           "detection_method": None, "detection_delay_ub_ms": None, "detection_candidates": None}
    if not ms or not rf or not tr.get("kind"):
        out["detection_method"] = "not measurable: " + ("no pre-inclusion mempool first-seen of the trigger tx" if not ms else ("no bid history" if not rf else "bot did not react to the trigger"))
        return out
    d = bvh.detection(rf, ms, row["bot"].get("tx"))
    if d is None:
        out["detection_method"] = "not measurable: no bid history for the bot's block"
        return out
    ss = d["winning_builder_first_stepup"]
    jp = d["first_big_jump"]
    fw = d["first_winning_block_submission"]
    sl = bvh.slot_start_ms(row["auction"]["slot"])
    if ss:
        out["detection_delay_ms"] = ss["delay_ms"]
        out["bot_first_bid_utc_ms"] = sl + ss["ms_rel_slot"]
        out["detection_method"] = ("winning-builder-first-stepup (first bid by the builder that won the block, after the trigger, worth >= max(2x its own best earlier bid, 0.5 ETH); "
                                   "bid contents unknown; trigger = %s first seen in the public mempool)" % tr["kind"])
    elif jp:
        out["detection_delay_ms"] = jp["delay_ms"]
        out["bot_first_bid_utc_ms"] = sl + jp["ms_rel_slot"]
        out["detection_method"] = "first-big-bid-jump (first record bid after the trigger >= max(5x earlier best, 0.5 ETH); any builder; contents unknown)"
    if fw:
        out["detection_delay_ub_ms"] = fw["delay_ms"]
    out["attacker_first_seen_utc_ms"] = ms
    out["detection_candidates"] = d
    return out


def build_rows():
    rows = []
    for f in sorted(glob.glob(str(ROOT / "data/extract/*.json"))):
        for r in scrub_public(json.load(open(f))):
            rows.append(r)
    out = []
    log = []
    for r in rows:
        key = (r["slug"], r.get("sub"))
        rule = RULES.get(key)
        if not rule:
            raise SystemExit(f"no harmonize rule for {key}")
        o = copy.deepcopy(r)
        rf = (o["auction"].get("raw_refs") or {}).get("race_file")
        if rf:  # recompute with the current helper so improvements flow through; keep the agent's note
            note = o["auction"].get("auction_note")
            o["auction"] = bvh.auction_summary(rf, o["bot"].get("tx"))
            if note:
                o["auction"]["auction_note"] = note
        o["verdict"] = rule["verdict"]
        o["race_type"] = rule["race_type"]
        o["verdict_reason"] = rule["why"]
        o["headline"] = bool(rule["verdict"] == "confirmed-onchain" and rule["race_type"] in HEADLINE_TYPES)
        if key in ONE_LINER_FIXES:
            o["one_liner_agent"] = o["one_liner"]
            o["one_liner"] = ONE_LINER_FIXES[key]
        o["headline_note"] = HEADLINE_NOTES.get(key)
        o["evidence_strength"], o["evidence_strength_basis"] = STRENGTH[key]
        o["blocks"] = {}
        o["era"] = era_of(o["date_utc"], o["bot"].get("block") or (o.get("auction") or {}).get("block") or o.get("attacker_block"))
        ab = o.get("attacker_block")
        o["blocks_ahead"] = (ab - o["bot"]["block"]) if (ab is not None and o["bot"].get("block") is not None) else None
        o["blocks_ahead_note"] = "attacker_block - bot.block: positive = the bot landed that many blocks BEFORE the attacker's racing tx; 0 = same block (see ordering)"
        if rule["race_type"] == "beat-whitehat-or-user":
            o["blocks_ahead_note"] += "; here attacker_block is the block where the copied USER/whitehat tx finally landed or failed (it may have sat pending far longer than the bot waited)"
        o["ordering"] = ordering(o)
        if rule["race_type"] == "bot-was-first-exploiter" and o["blocks_ahead"] is not None:
            # gap-fill rule: the bot was first to use the bug; nothing of the attacker's was pending, so "blocks ahead" would read as a race win
            o["first_attacker_tx_blocks_after_bot"] = o["blocks_ahead"]
            o["blocks_ahead"] = None
            o["ordering"] = "bot-first-exploiter (first attacker tx landed %d block(s) later; nothing pending, not a race)" % o["first_attacker_tx_blocks_after_bot"]
            o["blocks_ahead_note"] += "; null for bot-was-first-exploiter rows: the attacker's first tx (attacker_block) landed %d blocks after the bot with nothing pending, so this is not a lead over a pending tx (see first_attacker_tx_blocks_after_bot)" % o["first_attacker_tx_blocks_after_bot"]
        o.update(detection(o))
        # loot derived
        L = o["loot"]
        gross = num(L.get("gross_loot_eth"))
        paid = None
        if num(L.get("coinbase_paid_eth")) is not None or num(L.get("priority_fee_paid_eth")) is not None:
            paid = (num(L.get("coinbase_paid_eth")) or 0) + (num(L.get("priority_fee_paid_eth")) or 0)
        L["paid_to_block_producer_eth"] = paid
        L["pct_to_builder"] = pct(paid, gross)
        prop = num(o["auction"].get("proposer_paid_eth"))
        L["proposer_paid_eth"] = prop
        L["pct_to_proposer"] = pct(prop, gross) if (L.get("scope") == "bot-tx" and o["auction"].get("bot_tx_in_winning_block")) else None
        L["bot_net"] = num(L.get("bot_net_eth"))
        L["builder_refund_eth"] = L.get("builder_refund_to_bot_eth")   # schema alias
        RS.apply_overrides(o)
        LD.apply(o)
        F = o["fate"]
        if num(F.get("returned_total_eth")) is None and (num(F.get("returned_by_bot_eth")) is not None or num(F.get("returned_by_builder_eth")) is not None):
            F["returned_total_eth"] = (num(F.get("returned_by_bot_eth")) or 0) + (num(F.get("returned_by_builder_eth")) or 0)
        F["returned_pct"] = pct(F.get("returned_total_eth"), gross) if gross else None
        RS.apply(o)   # returned_pct_of_gross (== returned_pct), _of_bot_net, _of_victim_loss, builder pass-through
        F["bounty_kept"] = F.get("bounty_kept_eth")
        F["kept_by_bot"] = F.get("kept_by_bot_eth")
        o["headline_flag_rule"] = "verdict == confirmed-onchain and race_type in {beat-pending-attack, deploy-window-copy}, excluding Euler (operator identity unresolved)"
        # merge raw refs
        rr = dict(o.get("raw_refs") or {})
        for k, v in (o["auction"].get("raw_refs") or {}).items():
            rr["auction." + k] = v
        def union(*keys):
            out = []
            for k in keys:
                v = rr.get(k)
                for x in (v if isinstance(v, list) else [v] if v else []):
                    if x not in out:
                        out.append(x)
            return out or None
        arf = o["auction"].get("raw_refs") or {}
        bids_refs = [v for k, v in arf.items() if k.startswith("relay_bids") or k.startswith("relay_delivered")]
        for dk, src in (("blocks_ahead", union("bot.block", "attacker_block")), ("ordering", union("bot.block", "bot.position", "attacker_block")),
                        ("loot.paid_to_block_producer_eth", union("loot.coinbase_paid_eth", "loot.priority_fee_paid_eth")),
                        ("loot.pct_to_builder", union("loot.coinbase_paid_eth", "loot.priority_fee_paid_eth", "loot.gross_loot_eth")),
                        ("loot.pct_to_proposer", (union("loot.gross_loot_eth") or []) + bids_refs if L.get("pct_to_proposer") is not None else None),
                        ("fate.returned_pct", union("fate.returned_total_eth", "fate.returned_by_bot_eth", "loot.gross_loot_eth")),
                        ("fate.returned_pct_of_gross", union("fate.returned_total_eth", "fate.returned_by_bot_eth", "loot.gross_loot_eth")),
                        ("fate.returned_by_builder_or_proposer_eth", union("fate.returned_by_builder_eth") if F.get("returned_by_builder_or_proposer_eth") is not None else None),
                        ("fate.returned_by_bot_side_eth", union("fate.returned_total_eth", "fate.returned_by_builder_eth") if F.get("returned_by_bot_side_eth") is not None else None),
                        ("fate.returned_pct_of_bot_net", (union("fate.returned_total_eth", "fate.returned_by_builder_eth", "loot.bot_net_eth", "fate.returned_pct_of_bot_net") or []) if F.get("returned_pct_of_bot_net") is not None else None),
                        ("fate.victim_loss_eth", union("loot.gross_loot_eth") if F.get("victim_loss_eth") is not None else None),
                        ("fate.returned_pct_of_victim_loss", (union("fate.returned_total_eth", "loot.gross_loot_eth") or []) if F.get("returned_pct_of_victim_loss") is not None else None),
                        ("detection_delay_ms", (union("trigger.first_seen_utc_ms") or []) + bids_refs if o.get("detection_delay_ms") is not None else None),
                        ("detection_delay_ub_ms", (union("trigger.first_seen_utc_ms") or []) + bids_refs if o.get("detection_delay_ub_ms") is not None else None),
                        ("attacker_first_seen_utc_ms", union("trigger.first_seen_utc_ms") if o.get("attacker_first_seen_utc_ms") else None),
                        ("bot_first_bid_utc_ms", bids_refs if o.get("bot_first_bid_utc_ms") else None)):
            if src and all(x for x in src):
                rr[dk] = src
        o["raw_refs"] = rr
        log.append({"slug": o["slug"], "sub": o.get("sub"), "orig_verdict": o.get("orig_verdict"), "verdict": o["verdict"],
                    "race_type_proposed": o.get("race_type_proposed"), "race_type": o["race_type"], "headline": o["headline"]})
        out.append(o)
    return out, log



CSV_COLS = ["slug", "sub", "name", "date_utc", "era", "verdict", "race_type", "headline", "bot_label", "bot_tx", "bot_block", "bot_position",
            "attacker_block", "blocks_ahead", "ordering", "evidence_level_mempool", "detection_delay_ms", "detection_method_short",
            "n_bids", "winning_bid_eth", "winning_builder", "gross_loot_eth", "coinbase_paid_eth", "pct_to_builder", "pct_to_proposer",
            "returned_total_eth", "returned_pct", "returned_pct_of_gross", "returned_pct_of_bot_net", "returned_by_builder_or_proposer_eth",
            "returned_pct_of_victim_loss", "bounty_kept_eth", "kept_by_bot_eth", "return_status", "one_liner"]


def csv_row(o):
    A, L, F = o["auction"], o["loot"], o["fate"]
    m = o.get("detection_method") or ""
    return {
        "slug": o["slug"], "sub": o.get("sub") or "", "name": o["name"], "date_utc": o["date_utc"], "era": o["era"], "verdict": o["verdict"],
        "race_type": o["race_type"], "headline": "yes" if o["headline"] else "no", "bot_label": o["bot"].get("label"), "bot_tx": o["bot"].get("tx"),
        "bot_block": o["bot"].get("block"), "bot_position": o["bot"].get("position"), "attacker_block": o.get("attacker_block"),
        "blocks_ahead": o.get("blocks_ahead"), "ordering": o.get("ordering"), "evidence_level_mempool": o["evidence_level_mempool"],
        "detection_delay_ms": o.get("detection_delay_ms"), "detection_method_short": m.split(" (")[0] if m else "",
        "n_bids": A.get("n_bids"), "winning_bid_eth": A.get("winning_bid_eth"), "winning_builder": A.get("winning_builder"),
        "gross_loot_eth": L.get("gross_loot_eth"), "coinbase_paid_eth": L.get("coinbase_paid_eth"), "pct_to_builder": L.get("pct_to_builder"),
        "pct_to_proposer": L.get("pct_to_proposer"), "returned_total_eth": F.get("returned_total_eth"), "returned_pct": F.get("returned_pct"),
        "returned_pct_of_gross": F.get("returned_pct_of_gross"), "returned_pct_of_bot_net": F.get("returned_pct_of_bot_net"),
        "returned_by_builder_or_proposer_eth": F.get("returned_by_builder_or_proposer_eth"), "returned_pct_of_victim_loss": F.get("returned_pct_of_victim_loss"),
        "bounty_kept_eth": F.get("bounty_kept_eth"), "kept_by_bot_eth": F.get("kept_by_bot_eth"), "return_status": F.get("return_status"),
        "one_liner": o["one_liner"],
    }


def write_csv(rows):
    with open(ROOT / "data/comparison_table.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS)
        w.writeheader()
        for o in rows:
            w.writerow(csv_row(o))


def rawref_audit(rows):
    checked, missing = 0, []
    for o in rows:
        for k, v in (o.get("raw_refs") or {}).items():
            for p in (v if isinstance(v, list) else [v]):
                if not p:
                    continue
                if "not published" in p or "full cache only" in p:
                    continue
                checked += 1
                if not (ROOT / p).exists():
                    missing.append({"slug": o["slug"], "sub": o.get("sub"), "field": k, "path": p})
    gaps = [{"slug": o["slug"], "sub": o.get("sub"), **g} for o in rows for g in (o.get("rawref_gaps") or [])]
    # coverage: every non-null numeric/measured field of the table must have a raw_ref entry
    must = ["bot.block", "bot.position", "attacker_block", "blocks_ahead", "detection_delay_ms", "detection_delay_ub_ms", "attacker_first_seen_utc_ms",
            "bot_first_bid_utc_ms", "loot.gross_loot_eth", "loot.coinbase_paid_eth", "loot.priority_fee_paid_eth", "loot.paid_to_block_producer_eth",
            "loot.pct_to_builder", "loot.pct_to_proposer", "loot.builder_refund_to_bot_eth", "loot.builder_payout_to_victim_eth", "loot.bot_net_eth",
            "loot.captured_usd", "fate.returned_by_bot_eth", "fate.returned_by_builder_eth", "fate.returned_total_eth", "fate.returned_pct",
            "fate.bounty_kept_eth", "fate.kept_by_bot_eth", "trigger.first_seen_utc_ms"] + RS.NEW_FATE_FIELDS
    def get(o, path):
        for k in path.split("."):
            o = o.get(k) if isinstance(o, dict) else None
        return o
    uncovered = [{"slug": o["slug"], "sub": o.get("sub"), "field": f} for o in rows for f in must if get(o, f) is not None and not (o.get("raw_refs") or {}).get(f)]
    aud_fields = ["n_bids", "winning_bid_eth", "winning_builder", "runner_up_eth", "proposer_paid_eth", "first_bid_ms_rel_slot"]
    unc_a = [{"slug": o["slug"], "sub": o.get("sub"), "field": "auction." + f} for o in rows for f in aud_fields
             if o["auction"].get(f) is not None and not (o["auction"].get("raw_refs") or {}).get("race_file")]
    manifest = set()
    mp = ROOT / "data/raw/MANIFEST.jsonl"
    if mp.exists():
        for line in open(mp):
            try:
                manifest.add(json.loads(line)["path"])
            except Exception:
                pass
    not_in_manifest = sorted({p for o in rows for v in (o.get("raw_refs") or {}).values() for p in (v if isinstance(v, list) else [v])
                              if p and p.startswith("data/raw/") and p not in manifest})
    return {"generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "refs_checked": checked, "missing_files": missing,
            "fields_without_raw_ref": uncovered + unc_a, "declared_gaps": gaps,
            "refs_not_in_published_manifest": not_in_manifest,
            "note": "missing_files / fields_without_raw_ref must be empty; refs_not_in_published_manifest are existing files saved by the extraction scripts' RPC/etherscan helpers without a MANIFEST line (informational)."}


def normalize_label(l):
    l = (l or "").lower()
    for k, v in (("peth front", "Curve pETH front-runner 0x6ec2"), ("yoink", "Yoink"), ("c0ffeebabe", "c0ffeebabe.eth"), ("0xa57", "0xa57 (Earning.Farm bot)"), ("antelope", "Antelope (DODO)"),
                 ("blocksec", "BlockSec (whitehat)"), ("bitfinding", "Bitfinding (whitehat)"), ("eip-7702", "Makina searcher 0x935b"),
                 ("mmmmmev", "Ronin ETH-leg searcher"), ("racer 3", "Ronin racer 3")):
        if k.lower() in l:
            return v
    if l.strip() in ("none", ""):
        return "none"
    return "anon searcher"


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def returns_stats(rows):
    """Headline return statistics under all three denominators (see returns_schema.py). Bot-tx scope rows only (Sushi RP2 is
    incident-wide and listed apart); pooled = sum(numerator)/sum(denominator) in ETH-equivalents, median = median of row percentages."""
    rk = lambda o: f"{o['slug']}{'/' + o['sub'] if o.get('sub') else ''}"
    bt = [o for o in rows if o["loot"].get("scope") == "bot-tx"]
    yoink = lambda o: normalize_label(o["bot"].get("label")) == "Yoink"
    bases = {
        "gross": dict(pct="returned_pct_of_gross", num=lambda o: o["fate"]["returned_total_eth"], den=lambda o: o["loot"]["gross_loot_eth"],
                      desc="returned_total_eth (reached the victim side, from the bot AND any builder pass-through, net of bounty) / gross_loot_eth taken from the victim in the bot tx"),
        "bot_net": dict(pct="returned_pct_of_bot_net", num=lambda o: o["fate"]["returned_by_bot_side_eth"], den=lambda o: o["loot"]["bot_net_eth"],
                        desc="returned_by_bot_side_eth (builder pass-through excluded) / loot.bot_net_eth (gross - coinbase - gas + builder refund); rows with a ~0 or non-comparable net are excluded"),
        "victim_loss": dict(pct="returned_pct_of_victim_loss", num=lambda o: o["fate"]["returned_total_eth"], den=lambda o: o["fate"]["victim_loss_eth"],
                            desc="returned_total_eth / victim_loss_eth (the victim's ETH-equivalent loss to the bot tx; equals gross except Earning.Farm, Balancer and UNCX)"),
    }
    def block(rs, b):
        rs = [o for o in rs if num(o["fate"].get(b["pct"])) is not None]
        if not rs:
            return {"rows": 0}
        vals = [o["fate"][b["pct"]] for o in rs]
        n_, d_ = sum(b["num"](o) for o in rs), sum(b["den"](o) for o in rs)
        return {"rows": len(rs), "known_zero_rows": sum(b["num"](o) == 0 for o in rs), "pooled_pct": pct(n_, d_), "sum_returned_eth": round(n_, 4), "sum_denominator_eth": round(d_, 4),
                "median_row_pct": round(med(vals), 3), "min_row_pct": min(vals), "max_row_pct": max(vals),
                "per_row": {rk(o): o["fate"][b["pct"]] for o in rs}}
    out = {"definitions": {k: v["desc"] for k, v in bases.items()},
           "legacy_alias": "fate.returned_pct == fate.returned_pct_of_gross for every row (documented in harmonize_log.json)"}
    for name, b in bases.items():
        out[name] = {"all_bot_tx_rows": block(bt, b), "headline_rows": block([o for o in bt if o["headline"]], b),
                     "yoink_rows": block([o for o in bt if yoink(o)], b)}
    H = [o for o in rows if o["headline"]]
    out["headline_rows_returned_by_builder_or_proposer"] = {
        "rows": {rk(o): o["fate"]["returned_by_builder_or_proposer_eth"] for o in H if num(o["fate"].get("returned_by_builder_or_proposer_eth"))},
        "sum_eth": round(sum(o["fate"]["returned_by_builder_or_proposer_eth"] for o in H if num(o["fate"].get("returned_by_builder_or_proposer_eth"))), 4),
        "share_of_headline_returned_eth_pct": pct(sum(o["fate"]["returned_by_builder_or_proposer_eth"] for o in H if num(o["fate"].get("returned_by_builder_or_proposer_eth"))),
                                                  sum(o["fate"]["returned_total_eth"] for o in H if num(o["fate"].get("returned_total_eth")) and num(o["loot"].get("gross_loot_eth")) and o["loot"].get("scope") == "bot-tx"))}
    out["rows_without_bot_net_pct_but_with_return"] = {rk(o): (o["fate"].get("returned_pct_note") or "")[:300] for o in bt
                                                       if num(o["fate"].get("returned_total_eth")) is not None and num(o["fate"].get("returned_pct_of_bot_net")) is None}
    out["incident_wide_rows_not_pooled"] = {rk(o): {"returned_total_eth": o["fate"].get("returned_total_eth"), "returned_pct_of_gross": o["fate"].get("returned_pct_of_gross"),
                                                    "returned_pct_of_bot_net": o["fate"].get("returned_pct_of_bot_net")} for o in rows if o["loot"].get("scope") != "bot-tx"}
    out["headline_rows_by_status"] = {rk(o): o["fate"].get("return_status") for o in H}
    return out


def stats(rows, sensitivity=True):
    def cnt(key, sel=lambda o: True):
        c = {}
        for o in rows:
            if sel(o):
                v = key(o)
                c[v] = c.get(v, 0) + 1
        return dict(sorted(c.items(), key=lambda kv: -kv[1]))
    H = [o for o in rows if o["headline"]]
    slugs = lambda rs: sorted({o["slug"] for o in rs})
    def botkey(o):
        return normalize_label(o["bot"].get("label")) or o["bot"].get("label") or "unknown"
    meas = [o for o in rows if o.get("detection_delay_ms") is not None]
    # loot: use only bot-tx scope for share-of-loot to avoid mixing incident totals with single-tx numbers
    def tot(sel, f):
        return round(sum(f(o) for o in rows if sel(o)), 6)
    both_all = [o for o in rows if num(o["loot"].get("gross_loot_eth")) and o["loot"].get("paid_to_block_producer_eth") is not None]
    both = [o for o in both_all if o["loot"].get("scope") == "bot-tx"]   # pooled figures use single-bot-tx rows only
    both_h = [o for o in both if o["headline"]]
    def pooled(rs):
        g = sum(o["loot"]["gross_loot_eth"] for o in rs)
        pd_ = sum(o["loot"]["paid_to_block_producer_eth"] for o in rs)
        known = [o for o in rs if num(o["loot"].get("builder_refund_to_bot_eth")) is not None]
        net = [o["loot"]["paid_to_block_producer_eth"] - o["loot"]["builder_refund_to_bot_eth"] for o in known]
        after = {"rows": len(known), "sum_paid_minus_refund_eth": round(sum(net), 4),
                 "pooled_pct": pct(sum(net), sum(o["loot"]["gross_loot_eth"] for o in known)),
                 "median_row_pct": med([pct(n, o["loot"]["gross_loot_eth"]) for n, o in zip(net, known)])}
        return {"rows": len(rs), "sum_paid_eth": round(pd_, 4), "sum_gross_eth": round(g, 4), "pooled_pct": pct(pd_, g),
                "after_refunds": after,
                "median_row_pct": med([o["loot"]["pct_to_builder"] for o in rs])}
    prop_rows = [o for o in both if o["loot"].get("pct_to_proposer") is not None]
    ret_rows = [o for o in rows if num(o["fate"].get("returned_total_eth")) is not None and num(o["loot"].get("gross_loot_eth")) and o["loot"].get("scope") == "bot-tx"]
    ret_rows_h = [o for o in ret_rows if o["headline"]]
    out = {
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "counts": {
            "rows": len(rows), "incidents": len({o["slug"] for o in rows}),
            "headline_rows": len(H), "headline_incidents": len(slugs(H)), "headline_incident_slugs": slugs(H),
            "headline_definition": "verdict == confirmed-onchain AND race_type in {beat-pending-attack, deploy-window-copy}; Euler excluded because operator identity is unresolved",
            "by_verdict": cnt(lambda o: o["verdict"]), "by_race_type": cnt(lambda o: o["race_type"]),
            "by_era": cnt(lambda o: o["era"]), "by_bot": cnt(botkey),
            "by_evidence_level_mempool": cnt(lambda o: o["evidence_level_mempool"]),
            "headline_by_race_type": cnt(lambda o: o["race_type"], lambda o: o["headline"]),
            "headline_by_era": cnt(lambda o: o["era"], lambda o: o["headline"]),
            "headline_by_bot": cnt(botkey, lambda o: o["headline"]),
            "verdict_by_race_type": {rt: cnt(lambda o: o["verdict"], lambda o, rt=rt: o["race_type"] == rt) for rt in sorted({o["race_type"] for o in rows})},
        },
        "ordering": cnt(lambda o: (o.get("ordering") or "n/a").split(" (")[0], lambda o: o["headline"]),
        "blocks_ahead": {"headline_rows_with_value": {f"{o['slug']}{'/' + o['sub'] if o.get('sub') else ''}": o["blocks_ahead"] for o in H if o.get("blocks_ahead") is not None},
                         "definition": "attacker_block - bot.block (positive = bot landed earlier)"},
        "loot": {
            "note": "gross_loot_eth = ETH-equivalent extracted by the bot tx(s) of each row before paying the builder (priced inside the tx where possible); rows whose loot is not priced in ETH (DODO, Euler, ZC copiers, alETH/CRV wave 1) are excluded from every ETH total. Sushi RP2 is an incident-wide figure (scope all-bots-in-incident) and is reported separately.",
            "rows_with_gross_bot_tx_scope": len([o for o in rows if num(o["loot"].get("gross_loot_eth")) and o["loot"].get("scope") == "bot-tx"]),
            "total_gross_loot_eth_bot_tx_scope": round(sum(o["loot"]["gross_loot_eth"] for o in rows if num(o["loot"].get("gross_loot_eth")) and o["loot"].get("scope") == "bot-tx"), 4),
            "total_gross_loot_eth_headline_rows": round(sum(o["loot"]["gross_loot_eth"] for o in H if num(o["loot"].get("gross_loot_eth"))), 4),
            "headline_rows_without_eth_price": [f"{o['slug']}{'/' + o['sub'] if o.get('sub') else ''}" for o in H if not num(o["loot"].get("gross_loot_eth"))],
            "sushi_rp2_incident_wide": {"gross_loot_eth": next((o["loot"]["gross_loot_eth"] for o in rows if o["slug"] == "sushi-rp2-2023"), None),
                                       "returned_eth": next((o["fate"]["returned_total_eth"] for o in rows if o["slug"] == "sushi-rp2-2023"), None)},
            "total_returned_eth_bot_tx_scope": round(sum(o["fate"]["returned_total_eth"] for o in ret_rows), 4),
            "returned_pct_of_gross_bot_tx_rows_with_both": pct(sum(o["fate"]["returned_total_eth"] for o in ret_rows), sum(o["loot"]["gross_loot_eth"] for o in ret_rows)),
            "rows_with_return_figure": len(ret_rows),
            "returned_headline_rows": {"rows": len(ret_rows_h), "known_zero_rows": sum(o["fate"]["returned_total_eth"] == 0 for o in ret_rows_h), "returned_eth": round(sum(o["fate"]["returned_total_eth"] for o in ret_rows_h), 4),
                                       "gross_eth": round(sum(o["loot"]["gross_loot_eth"] for o in ret_rows_h), 4),
                                       "pct": pct(sum(o["fate"]["returned_total_eth"] for o in ret_rows_h), sum(o["loot"]["gross_loot_eth"] for o in ret_rows_h))},
            "median_row_returned_pct": med([o["fate"]["returned_pct"] for o in ret_rows]),
            "returns": returns_stats(rows),
            "return_status_counts": cnt(lambda o: o["fate"].get("return_status")),
            "return_status_counts_headline": cnt(lambda o: o["fate"].get("return_status"), lambda o: o["headline"]),
            "total_captured_usd_reported_where_known": round(sum(o["loot"]["captured_usd"] for o in rows if num(o["loot"].get("captured_usd"))), 0),
            "captured_usd_caveat": "sum of per-row headline/pool-loss USD figures from the postmortems cited in raw_refs; definitions differ (pool loss vs bot take), so treat as an order of magnitude only",
        },
        "block_producer_share": {
            "definition": "bot tx's direct coinbase transfers + its gas priority fee, as % of the bot's gross loot (before any builder refund/pass-through). Pooled = sum/sum over single-bot-tx rows with a priced loot.",
            "all_rows": pooled(both), "headline_rows": pooled(both_h),
            "by_era_headline": {e: pooled([o for o in both_h if o["era"] == e]) for e in ERA_ORDER if [o for o in both_h if o["era"] == e]},
            "by_bot_headline": {b: pooled([o for o in both_h if (normalize_label(o["bot"].get("label")) or "") == b]) for b in sorted({normalize_label(o["bot"].get("label")) for o in both_h})},
            "sushi_rp2_incident_wide_pct_to_builders_and_proposers": next((o["loot"]["pct_to_builder"] for o in rows if o["slug"] == "sushi-rp2-2023"), None),
            "proposer_share": {"definition": "winning bid (the proposer payment) / bot gross loot; bot-tx scope rows whose tx is in the winning block and whose bid history exists",
                                "rows": len(prop_rows), "pooled_pct": pct(sum(o["loot"]["proposer_paid_eth"] for o in prop_rows), sum(o["loot"]["gross_loot_eth"] for o in prop_rows)),
                                "median_row_pct": med([o["loot"]["pct_to_proposer"] for o in prop_rows]),
                                "headline_rows": len([o for o in prop_rows if o["headline"]]),
                                "headline_median_row_pct": med([o["loot"]["pct_to_proposer"] for o in prop_rows if o["headline"]])},
            "per_row": {f"{o['slug']}{'/' + o['sub'] if o.get('sub') else ''}": {"headline": o["headline"], "pct_to_builder": o["loot"]["pct_to_builder"], "pct_to_proposer": o["loot"]["pct_to_proposer"],
                                                                                 "builder_refund_to_bot_eth": o["loot"].get("builder_refund_to_bot_eth"), "builder_payout_to_victim_eth": o["loot"].get("builder_payout_to_victim_eth")} for o in both_all},
        },
        "detection_delay": {
            "definition": "ms from the first pre-inclusion public-mempool sighting of the trigger tx (attacker tx/deploy or the user's withdrawal) to the first bid of the builder that won the block with a step-up (>=2x its own earlier best and >=0.5 ETH); contents of non-winning bids are not visible",
            "n_measured": len(meas), "median_ms": med([o["detection_delay_ms"] for o in meas]),
            "measured": [{"row": f"{o['slug']}{'/' + o['sub'] if o.get('sub') else ''}", "trigger": o["trigger"]["kind"], "delay_ms": o["detection_delay_ms"], "upper_bound_ms": o.get("detection_delay_ub_ms"),
                          "method": (o.get("detection_method") or "").split(" (")[0]} for o in meas],
            "median_upper_bound_ms": med([o.get("detection_delay_ub_ms") for o in meas]),
            "headline_rows_measured": [f"{o['slug']}{'/' + o['sub'] if o.get('sub') else ''}" for o in meas if o["headline"]],
            "median_ms_headline_rows": med([o["detection_delay_ms"] for o in meas if o["headline"]]),
            "min_ms": min([o["detection_delay_ms"] for o in meas]) if meas else None, "max_ms": max([o["detection_delay_ms"] for o in meas]) if meas else None,
            "unmeasurable_reason": "attacker/bot txs of most archive-era incidents were absent from mempool-dumpster; before 2023-08-07 no mempool archive exists",
        },
        "mempool_visibility_in_our_set": {
            "dumpster_era_rows": len([o for o in rows if o["evidence_level_mempool"] in ("measured", "absent-from-archive")]),
            "attacker_or_user_trigger_seen_public_before_inclusion": len([o for o in rows if (o.get("trigger") or {}).get("first_seen_utc_ms")]),
            "rows": [f"{o['slug']}{'/' + o['sub'] if o.get('sub') else ''}" for o in rows if (o.get("trigger") or {}).get("first_seen_utc_ms")],
        },
        "auction": {
            "median_n_bids_where_known": med([o["auction"].get("n_bids") for o in rows if o["auction"].get("n_bids")]),
            "median_winning_bid_eth_headline_where_known": med([o["auction"].get("winning_bid_eth") for o in H if o["auction"].get("winning_bid_eth") is not None and o["auction"].get("n_bids")]),
        },
    }
    if sensitivity:
        reduced = [o for o in H if normalize_label(o["bot"].get("label")) != "c0ffeebabe.eth"]
        ss = stats(reduced, sensitivity=False)
        for basis in ("gross", "bot_net", "victim_loss"):
            ss["loot"]["returns"][basis].pop("all_bot_tx_rows", None)
        out["sensitivity"] = {"excluding_c0ffeebabe_rows": {
            "rows": len(reduced), "incidents": len(slugs(reduced)),
            "definition": "Headline rows excluding the four c0ffeebabe.eth rows whose call-level comparison is withheld by publication policy",
            "loot": ss["loot"], "block_producer_share": ss["block_producer_share"]}}
    return out


def backrunner(rows):
    """BACKRUNNER (arXiv 2409.06213) comparison. Our window figure is recomputed from data/evolution/per_exploit_v2.json exactly as
    scripts/evolution.py relabel does for findings_v2.txt (attacker-only, mempool-dumpster measurable, block before 2024-06-01)."""
    out = {"source": "arXiv 2409.06213 (BACKRUNNER), attack txs Jan 2023 - May 2024 as quoted in data/evolution/findings.txt",
           "backrunner_paper": {"attack_txs": 158, "visible_in_public_mempool": 17, "public_pct": round(100 * 17 / 158, 1), "intercepted_by_their_own_bots": 18,
                                "intercepted_pct": round(100 * 18 / 158, 1), "constructor_attack_txs": 4, "deployed_1s_before_trigger": "50 of 54"}}
    pv2 = ROOT / "data/evolution/per_exploit_v2.json"
    if pv2.exists():
        d = json.load(open(pv2))["exploits"]
        lim = dt.datetime(2024, 6, 1, tzinfo=dt.timezone.utc).timestamp()
        att = [r for r in d if r.get("sender_class") == "attacker" and r.get("attacker_side_status") == "measured" and r.get("status") == "ok"]
        win = [r for r in att if r["exposure"]["method"] == "mempool-dumpster" and r["block_ts"] < lim]
        pub = sum(1 for r in win if r["exposure"]["label"] == "public")
        res = sum(1 for r in win if r["exposure"]["label"] in ("public", "private-bundle"))
        allw = [r for r in att if r["exposure"]["method"] == "mempool-dumpster"]
        apub = sum(1 for r in allw if r["exposure"]["label"] == "public")
        ares = sum(1 for r in allw if r["exposure"]["label"] in ("public", "private-bundle"))
        v1 = json.load(open(ROOT / "data/evolution/per_exploit.json"))["exploits"]
        v1w = [r for r in v1 if r.get("status") == "ok" and r["exposure"]["method"] == "mempool-dumpster" and r["block_ts"] < lim]
        v1p = sum(1 for r in v1w if r["exposure"]["label"] == "public")
        v1r = sum(1 for r in v1w if r["exposure"]["label"] in ("public", "private-bundle"))
        out["ours_w6_v2_same_window_attacker_only"] = {
            "window": "2023-08-07 .. 2024-05-31 (earliest mempool-dumpster data to the end of BACKRUNNER's window)", "unit": "exploits (first attacker tx), not txs",
            "resolved": res, "public": pub, "public_pct": pct(pub, res), "v1_all_senders": {"resolved": v1r, "public": v1p, "public_pct": pct(v1p, v1r)},
            "source_file": "data/evolution/per_exploit_v2.json"}
        out["ours_w6_v2_all_dumpster_era_attacker_only"] = {"window": "2023-08-07 .. 2026-10", "resolved": ares, "public": apub, "public_pct": pct(apub, ares),
                                                           "note": "ordinary txs in the same blocks were seen 62.5% (86% in 2023H2, ~50% in 2025-26), see by_era_v2.json attacker_only.overall"}
    hl = [o for o in rows if o["headline"] and o["evidence_level_mempool"] in ("measured", "absent-from-archive")]
    seen = [o for o in hl if (o.get("trigger") or {}).get("first_seen_utc_ms")]
    out["ours_incident_set"] = {
        "definition": "headline races (bot beat the hacker) from 2023-08-07 on, where the mempool archive covers the day",
        "headline_races_in_dumpster_era": len(hl), "attacker_trigger_tx_seen_public_before_inclusion": len(seen),
        "seen": [f"{o['slug']}{'/' + o['sub'] if o.get('sub') else ''}" for o in seen],
        "not_seen": [f"{o['slug']}{'/' + o['sub'] if o.get('sub') else ''}" for o in hl if o not in seen],
        "reading": "most bot wins in the archive era were against attackers whose txs never appeared in the public mempool: the bots' view of the attacker is a private/builder-side or on-chain-setup (deploy/prepare) view, not the public pool BACKRUNNER measures"}
    out["comparability_notes"] = [
        "BACKRUNNER counts attack TRANSACTIONS and detects interception with its own bots/nodes; we count EXPLOITS and detect copies from on-chain evidence, so 'intercepted 18/158' has no counterpart here (see findings_v2.txt, EXTERNAL COMPARISON and strongest-evidence point 7 for the chain scan).",
        "Public-visibility shares agree in the overlapping window (BACKRUNNER 10.8%; ours 11.9% attacker-only v2, 10.7% v1), and fall to 4.5% over the whole dumpster era."]
    return out


def writeback(rows, log_changes):
    by_slug = {}
    for o in rows:
        by_slug.setdefault(o["slug"], []).append(o)
    changes = []
    for slug, rs in by_slug.items():
        p = ROOT / "incidents" / slug / "incident.json"
        d = json.load(open(p))
        prim = next((o for o in rs if o["verdict"] == "confirmed-onchain" and o["headline"]), None) or next((o for o in rs if o["verdict"] == "confirmed-onchain"), rs[0])
        before = (d.get("harmonized") or {}).get("before") or {"verdict": d.get("verdict"), "race_type": d.get("race_type"), "headline": d.get("headline")}
        old_v, old_rt, old_h = before["verdict"], before["race_type"], before["headline"]
        d["verdict_original"] = old_v
        d["verdict"] = prim["verdict"]
        d["race_type"] = prim["race_type"]
        d["headline"] = any(o["headline"] for o in rs)
        d["headline_text"] = prim["one_liner"]
        d["verdict_rule"] = "harmonized 2026-10-21: see scripts/dataset/harmonize_rules.py and data/harmonize_log.json"
        if len(rs) > 1:
            d["sub_rows"] = [{"sub": o.get("sub"), "verdict": o["verdict"], "race_type": o["race_type"], "headline": o["headline"], "bot": o["bot"].get("label"),
                              "bot_tx": o["bot"].get("tx"), "bot_block": o["bot"].get("block"), "blocks_ahead": o.get("blocks_ahead")} for o in rs]
        else:
            d.pop("sub_rows", None)
        d["harmonized"] = {"before": before, "verdict_reason": prim["verdict_reason"], "headline_note": prim.get("headline_note"),
                           "dataset_rows": [(o["slug"] + ("/" + o["sub"] if o.get("sub") else "")) for o in rs]}
        json.dump(d, open(p, "w"), indent=1, ensure_ascii=False)
        ch = []
        if old_v != d["verdict"]:
            ch.append({"field": "verdict", "old": old_v, "new": d["verdict"]})
        if old_rt != d["race_type"]:
            ch.append({"field": "race_type", "old": old_rt, "new": d["race_type"]})
        if old_h != d["headline"]:
            ch.append({"field": "headline", "old": old_h, "new": d["headline"]})
        changes.append({"slug": slug, "incident_json": str(p.relative_to(ROOT)), "changes": ch, "semantic_change": ("verdict meaning changed (related-not-frontrun -> confirmed-onchain)" if (d["verdict_original"] or "").startswith("related-not-frontrun") and d["verdict"] == "confirmed-onchain" else None),
                        "rows": [{"sub": o.get("sub"), "verdict": o["verdict"], "race_type": o["race_type"], "headline": o["headline"], "reason": o["verdict_reason"]} for o in rs]})
    return changes


def gapfill_block(rows):
    """Phase C gap-fill: rows added from scripts/dataset/gapfill_rules/*.json plus the decisions in research/launch-gap/gapfill_notes.json."""
    slugs = sorted(p.stem for p in (ROOT / "scripts/dataset/gapfill_rules").glob("*.json"))
    notes = ROOT / "research/launch-gap/gapfill_notes.json"
    out = json.load(open(notes)) if notes.exists() else {}
    out["new_rows"] = [{"slug": o["slug"], "sub": o.get("sub"), "date_utc": o["date_utc"], "verdict": o["verdict"], "race_type": o["race_type"], "headline": o["headline"],
                        "bot": o["bot"].get("label"), "bot_tx": o["bot"].get("tx"), "bot_block": o["bot"].get("block"), "reason": o["verdict_reason"]}
                       for o in rows if o["slug"] in slugs]
    pre = ROOT / "research/launch-gap/pre_gapfill_dataset.json"
    if pre.exists():
        pr = json.load(open(pre))["rows"]
        out["before"] = {"rows": len(pr), "incidents": len({r["slug"] for r in pr}), "headline_rows": sum(r["headline"] for r in pr),
                         "headline_incidents": len({r["slug"] for r in pr if r["headline"]})}
        out["after"] = {"rows": len(rows), "incidents": len({o["slug"] for o in rows}), "headline_rows": sum(o["headline"] for o in rows),
                        "headline_incidents": len({o["slug"] for o in rows if o["headline"]})}
    return out


def main():
    wb = "--no-writeback" not in sys.argv
    if not wb:
        rows = json.load(open(ROOT / "data/incidents.json"))
        audit = rawref_audit(rows)
        print("read-only: rows", len(rows), "headline", sum(o["headline"] for o in rows), "missing raw", len(audit["missing_files"]))
        return
    rows, log = build_rows()
    json.dump(rows, open(ROOT / "data/incidents.json", "w"), indent=1)
    json.dump({"generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "rows": len(rows),
               "definitions": {
                   "era": "pre-2021 (date < 2021-01-01) | mev-geth-2021-22 (to the Merge, block 15537394) | early-pbs-2022-23 (Merge to 2023-12-31) | mature-pbs-2024-26 (2024-01-01 on); same eras as evolution study E1-E4",
                   "headline": "verdict == confirmed-onchain AND race_type in {beat-pending-attack, deploy-window-copy}, excluding Euler (operator identity unresolved)",
                   "fate.return_status": LD.RETURN_STATUS_RULE,
                   "verdict": "see scripts/dataset/harmonize_rules.py docstring",
                   "race_type": "beat-pending-attack | deploy-window-copy | beat-whitehat-or-user | post-failure-replay | bot-was-first-exploiter | late-copy | no-race (added: rejected sub-races where nobody raced)",
                   "blocks_ahead": "attacker_block - bot.block (positive = bot landed that many blocks BEFORE the attacker's racing tx; 0 = same block, see ordering; negative = bot landed after). null when the attacker's call never landed (deploy-window copies; see attacker_reference) or there is no attacker",
                   "slot_start": "1606824023 + 12 * slot (unix s); auction.escalation = record-bid curve [[ms relative to slot start, ETH]], max 60 points (largest jumps kept)",
                   "detection_delay_ms": "trigger first seen in the public mempool (mempool-dumpster, earliest source) -> first bid by the WINNING builder's pubkey after the trigger worth >= max(2x its own best earlier bid, 0.5 ETH); relays never reveal losing-bid contents so this is a proxy; detection_delay_ub_ms = trigger -> first submission of the winning block hash (contents verified)",
                   "loot.gross_loot_eth": "ETH-equivalent the bot tx extracted before paying the builder",
                   "loot.pct_to_builder": "(bot tx coinbase transfers + priority fee) / gross_loot_eth * 100; the builder may pass most on (see auction.proposer_paid_eth, builder_refund, builder_payout_to_victim)",
                   "loot.pct_to_proposer": "winning bid / gross_loot_eth * 100 (bot-tx scope, bot tx in the winning block, bid history available)",
                   "fate.returned_pct": "returned_total_eth / gross_loot_eth * 100, where returned_total_eth reached the victim/protocol side out of the row's proceeds (bot returns + builder pass-through; net of any bounty the bot kept)",
                   "fate.returned_pct_of_gross": "returned_total_eth / loot.gross_loot_eth * 100 (gross = ETH-equivalent the bot tx took from the victim, before the coinbase payment). fate.returned_pct is kept and is IDENTICAL to this field for every row",
                   "fate.returned_pct_of_bot_net": "fate.returned_by_bot_side_eth / loot.bot_net_eth * 100 (bot_net = gross - coinbase - gas + builder refund; builder/proposer pass-through excluded from the numerator). null where bot_net is under 0.05 ETH or excludes the main proceeds (see fate.returned_pct_note)",
                   "fate.returned_by_builder_or_proposer_eth": "ETH a builder / proposer-side recipient passed on to the victim (Blueberry builder -> multisig 366.63; Makina builder -> 0xbed2 -> Safe 920.7); null = none seen",
                   "fate.returned_by_bot_side_eth": "returned_total_eth - returned_by_builder_or_proposer_eth: returned by the row's own actors (for Sushi RP2 also the whitehats), net of bounty",
                   "fate.victim_loss_eth / returned_pct_of_victim_loss": "victim's ETH-equivalent loss to the bot tx (equals gross_loot_eth except Earning.Farm = gross - 0.1 ETH deposit; null for Balancer, UNCX) and returned_total_eth / that * 100",
                   "evidence_level_mempool": "measured | in-block-only (before 2023-08-07, no archive) | absent-from-archive (archive covers the day, the attacker/bot txs are not in it)"}},
              open(ROOT / "data/incidents_meta.json", "w"), indent=1)
    json.dump(rows, open(ROOT / "data/incidents.json", "w"), indent=1)
    write_csv(rows)
    audit = rawref_audit(rows)
    json.dump(audit, open(ROOT / "data/rawref_audit.json", "w"), indent=1)
    st = stats(rows)
    st["backrunner_comparison"] = backrunner(rows)
    json.dump(st, open(ROOT / "data/headline_stats.json", "w"), indent=1)
    print("rows", len(rows), "headline", st["counts"]["headline_rows"], "missing raw", len(audit["missing_files"]))
    if wb:
        ch = writeback(rows, log)
        RS.patch_paraswap_files(ROOT)   # keeps incidents/paraswap-2024/{incident,timeline}.json + summary.txt in line with the corrected fate
        json.dump({"generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "rule": __import__("harmonize_rules").__doc__.strip(),
                   "decisions": [
                       "BiFi: related-not-frontrun -> confirmed-onchain / deploy-window-copy (same rule as Makina; see RULES['bifi-2026'])",
                       "Curve: one row per sub-race; pETH, msETH, CRV-ETH-wave2 confirmed; alETH, CRV-ETH-wave1 rejected (no-race)",
                       "Sushi RP2: Yoink pre-empted Trust's whitehat rescue -> beat-whitehat-or-user (not headline)",
                       "Ronin: bots copied users' pending withdrawals -> beat-whitehat-or-user (not headline), 3 rows",
                       "UNCX: split into Yoink X front-run (confirmed, beat-pending-attack) and ZC copiers (related-not-frontrun, late-copy)",
                       "blocks_ahead := attacker_block - bot.block (positive = bot earlier); brief wording was 'bot block - attacker block'",
                       "added race_type value 'no-race' for rejected sub-races with no racer",
                       *RETURNS_DECISIONS],
                   "gapfill_phase_c": gapfill_block(rows),
                   "per_incident": ch, "per_row": log,
                   "returns_schema": {"doc": RS.__doc__.strip(), "legacy_alias": "fate.returned_pct == fate.returned_pct_of_gross (identical for all rows)",
                                      "before_values_replaced": RS.BEFORE, "sweep": RS.SWEEP, "consistency_check_exceptions": RS.consistency_checks(rows),
                                      "stats_block": "data/headline_stats.json -> loot.returns"}}, open(ROOT / "data/harmonize_log.json", "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
