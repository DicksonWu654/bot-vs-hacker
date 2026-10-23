#!/usr/bin/env python3
"""scan_results.json + exploits_mainnet.json -> hits.json, coverage.json, recurring.json
hit = candidate with a category from scan_copycats.categorize() or raw score >= 5.
coverage.json lists EVERY mainnet exploit entry as scanned_hit / scanned_nohit / unscannable (denominator for BACKRUNNER cross-check)."""
import json, pathlib, sys, collections
here = pathlib.Path(__file__).parent
sys.path.insert(0, str(here.parents[1] / "scripts"))
import scan_copycats as sc

res = json.load(open(here / "scan_results.json"))
byhash = {r["attack_tx"]: r for r in res}
expl = json.load(open(here / "exploits_mainnet.json"))["exploits"]

def strength(c, cats):
    am = (c.get("trace") or {}).get("victim_call_arg_match") or {}
    if any(k.startswith("replayed_attack") for k in cats) and am.get("exact_frac", 0) >= 0.5: return "strong"
    if c["signals"]["embeds_attack_calldata"] and c["relative"] != "earlier_block": return "strong" if c["status"] == "reverted" or c["relative"] != "next_block" else "medium"
    if "adapted_calldata" in cats and not c["signals"]["embeds_attack_calldata"]: return "weak"  # word-similarity only
    if cats: return "medium" if any(k.startswith("replayed") or k == "adapted_calldata" for k in cats) else "weak"
    return "weak"

hits, cov = [], []
for e in expl:
    txs = [i["hash"] for i in e.get("tx_info", []) if i.get("on_mainnet")]
    scanned = [byhash[h] for h in txs[:6] if h in byhash and "error" not in byhash[h]]
    row = {"name": e["name"], "date": e["date"], "file": e["file"], "dhl_txs": e["txs"] or e["txs_unknown_chain"]}
    if not scanned:
        row.update(status="unscannable", reason="no tx hash in PoC header" if not row["dhl_txs"] else "tx not found on mainnet / scan error")
        cov.append(row); continue
    inc_hits = []
    for r in scanned:
        cs = []
        for c in r["copycats"]:
            cats = sc.categorize(c)
            if cats or c["score"] >= 5:
                c = dict(c, categories=cats, strength=strength(c, cats)); cs.append(c)
        if cs:
            inc_hits.append({k: r.get(k) for k in ("exploit", "date", "file", "attack_tx", "block", "index", "attacker_from", "attack_to",
                "coinbase", "victims", "attacker_priority_gwei", "attacker_gas_price_gwei", "attacker_coinbase_paid_wei",
                "popularity_of_victims_in_window", "attacker_own_other_txs_in_window")} | {"name": e["name"], "copycats": cs})
    hits += inc_hits
    row.update(status="scanned_hit" if inc_hits else "scanned_nohit", txs_scanned=len(scanned),
               blocks=[r["block"] for r in scanned], candidates_traced=sum(r["candidates_traced"] for r in scanned),
               bundle_style_attack_tx=any(r["attacker_coinbase_paid_wei"] > 0 and (r["attacker_priority_gwei"] or 0) <= 0.01 for r in scanned),
               attacker_from=sorted({r["attacker_from"] for r in scanned}),
               best=[{"tx": c["tx"], "relative": c["relative"], "cats": c["categories"], "strength": c["strength"]} for h in inc_hits for c in h["copycats"][:3]][:5])
    cov.append(row)

# recurring senders (same EOA is the DHL attack-tx sender in >=3 incidents, or a candidate in >=3)
snd = collections.defaultdict(set); cand = collections.defaultdict(set)
for r in res:
    if "error" in r: continue
    snd[r["attacker_from"]].add(r["exploit"])
    for c in r["copycats"]:
        t = c.get("trace", {})
        if c["score"] >= 1 and (t.get("signature_overlap", 0) > 0 or c["signals"]["input_sim"] >= 0.3):
            cand[c["from"]].add(r["exploit"])
rec = {"dhl_attack_tx_sender_in_>=3_incidents": {a: sorted(v) for a, v in snd.items() if len(v) >= 3},
       "candidate_sender_in_>=3_incidents": {a: sorted(v) for a, v in cand.items() if len(v) >= 3}}
post = [r for r in res if "error" not in r and r["block"] >= 12965000]
bundle = [{"name": r["exploit"], "date": r["date"], "tx": r["attack_tx"], "block": r["block"], "index": r["index"], "from": r["attacker_from"],
           "coinbase_paid_eth": r["attacker_coinbase_paid_wei"] / 1e18} for r in post
          if r["attacker_coinbase_paid_wei"] > 0 and (r["attacker_priority_gwei"] or 0) <= 0.01]
rec["bundle_style_attack_txs"] = {"post_london_scanned": len(post), "count": len(bundle), "list": sorted(bundle, key=lambda b: b["date"])}
(here / "recurring.json").write_text(json.dumps(rec, indent=1))
(here / "hits.json").write_text(json.dumps({"definition": "candidates with a scan_copycats.categorize() category or score>=5; evidence level is 'candidate' until verified by hand",
                                            "n_incidents_with_hits": len({h['attack_tx'] for h in hits}), "hits": hits}, indent=1))
cnt = collections.Counter(c["status"] for c in cov)
(here / "coverage.json").write_text(json.dumps({"counts": dict(cnt), "mainnet_entries": len(cov), "entries": cov}, indent=1))
print(dict(cnt), "hit incidents(tx):", len({h['attack_tx'] for h in hits}))
