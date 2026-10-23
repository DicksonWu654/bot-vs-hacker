"""Validate data/extract/<slug>.json (list of rows). Usage: .venv/bin/python scripts/dataset/check_extract.py [slug ...]
Checks: required fields, enum values, every non-null numeric field has raw_refs[field] pointing at existing files incl. >=1 under data/raw/."""
import json, pathlib, sys, re
ROOT = pathlib.Path(__file__).resolve().parents[2]
RACE = {"beat-pending-attack", "deploy-window-copy", "beat-whitehat-or-user", "post-failure-replay", "bot-was-first-exploiter", "late-copy", "no-race"}
MEMP = {"measured", "in-block-only", "absent-from-archive"}
REQ = ["slug", "name", "date_utc", "orig_verdict", "race_type_proposed", "one_liner", "attacker", "bot", "evidence_level_mempool",
       "trigger", "auction", "loot", "fate", "raw_refs", "incident_dir"]
NUMREF = ["bot.block", "bot.position", "attacker_block", "trigger.first_seen_utc_ms", "loot.gross_loot_eth", "loot.coinbase_paid_eth",
          "loot.priority_fee_paid_eth", "loot.builder_refund_to_bot_eth", "loot.builder_payout_to_victim_eth", "loot.bot_net_eth",
          "loot.captured_usd", "fate.returned_by_bot_eth", "fate.returned_by_builder_eth", "fate.returned_total_eth",
          "fate.bounty_kept_eth", "fate.kept_by_bot_eth"]


def get(d, path):
    for k in path.split("."):
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def check(slug):
    p = ROOT / "data" / "extract" / f"{slug}.json"
    errs = []
    if not p.exists():
        return [f"{p} missing"]
    rows = json.load(open(p))
    if not isinstance(rows, list) or not rows:
        return ["not a non-empty list"]
    for r in rows:
        tag = f"{r.get('slug')}/{r.get('sub')}"
        for k in REQ:
            if k not in r:
                errs.append(f"{tag}: missing {k}")
        if r.get("race_type_proposed") not in RACE:
            errs.append(f"{tag}: bad race_type_proposed {r.get('race_type_proposed')}")
        if r.get("evidence_level_mempool") not in MEMP:
            errs.append(f"{tag}: bad evidence_level_mempool")
        if len(r.get("one_liner", "")) > 320:
            errs.append(f"{tag}: one_liner too long")
        refs = r.get("raw_refs") or {}
        for f in NUMREF:
            v = get(r, f)
            if v is None:
                continue
            ref = refs.get(f)
            if not ref:
                errs.append(f"{tag}: no raw_ref for {f}")
                continue
            paths = ref if isinstance(ref, list) else [ref]
            if not any(x.startswith("data/raw/") for x in paths):
                errs.append(f"{tag}: raw_ref for {f} has no data/raw/ path")
            for x in paths:
                if not (ROOT / x).exists():
                    errs.append(f"{tag}: raw_ref for {f} missing file {x}")
        for f, ref in refs.items():
            for x in (ref if isinstance(ref, list) else [ref]):
                if x and not (ROOT / x).exists():
                    errs.append(f"{tag}: raw_refs[{f}] missing file {x}")
        for k in ("bot",):
            b = r.get(k) or {}
            if b.get("tx") and not re.fullmatch(r"0x[0-9a-f]{64}", b["tx"]):
                errs.append(f"{tag}: bot.tx must be a full 66-char lowercase hash")
    return errs


if __name__ == "__main__":
    slugs = sys.argv[1:] or [p.stem for p in sorted((ROOT / "data" / "extract").glob("*.json"))]
    bad = 0
    for s in slugs:
        e = check(s)
        print(s, "OK" if not e else f"{len(e)} problems")
        for x in e:
            print("   ", x)
        bad += len(e)
    sys.exit(1 if bad else 0)
