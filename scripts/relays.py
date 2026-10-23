#!/usr/bin/env python3
"""MEV-Boost relay data-API access: who delivered a block, and every bid every relay received for it.

All HTTP goes through lib/rawfetch.get_soft, so each response (including 4xx/5xx and empty `[]` answers, which are
evidence that a relay holds nothing for that block) is saved verbatim under data/raw/relay-<name>/ with a MANIFEST line.

CLI
    relays.py probe  [--block N]           which relays answer today, and what each says for block N
    relays.py coverage                      delivered-payload coverage per relay at sample dates (cursor probes)
    relays.py retention                     how far back each relay still serves builder_blocks_received (bid history)
    relays.py fetch  BLOCK                  delivered + bids for BLOCK from every live relay (prints summary)
    relays.py names  PUBKEY [PUBKEY..]      resolve builder pubkeys -> names

Library
    fetch_block(block_number, slot=None) -> {"slot", "relays": {name: {"delivered": {...}, "bids": {...}}}}
    resolve_builder_names(pubkeys, hint_block=None) -> {pubkey: {"name", "evidence", ...}}

Relay data API (https://flashbots.github.io/relay-specs/ "Data API", served at /relay/v1/data/bidtraces/...):
    proposer_payload_delivered?slot= | block_hash= | block_number= | builder_pubkey= | proposer_pubkey= | cursor= | limit=
    builder_blocks_received?slot= | block_hash= | block_number= | builder_pubkey= | limit=
Fields of a bid: slot, parent_hash, block_hash, builder_pubkey, proposer_pubkey, proposer_fee_recipient, gas_limit,
gas_used, value (wei), num_tx, block_number, timestamp, timestamp_ms, optimistic_submission.
`timestamp_ms` is the relay's receive time of the submission (relay clock, ms). Slot t=0 is genesis + slot*12s.
"""
import argparse, json, pathlib, sys, time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "lib"))
import rawfetch as rf  # noqa: E402

GENESIS = 1606824023
MERGE_SLOT = 4700013  # first post-Merge slot (block 15537394 is the first PoS block, 2022-09-15)
MERGE_BLOCK = 15537394


def slot_start(slot):
    return GENESIS + int(slot) * 12


def slot_of_ts(ts):
    return (int(ts) - GENESIS) // 12


# Relay registry. `pubkey` = relay BLS pubkey as listed in flashbots/relayscan config-mainnet.yaml (saved raw under
# data/raw/relay-sources/). `alive_2026` is what the probe on 2026-10-21 found (updated by `probe`; keep notes honest).
RELAYS = [
    dict(name="flashbots", host="boost-relay.flashbots.net", operator="Flashbots",
         pubkey="0xac6e77dfe25ecd6110b8e780608cce0dab71fdd5ebea22a16c0205200f2f8e2e3ad3b71d3499c54ad14d6c21b41a37ae",
         notes="Live; full builder_blocks_received history back to at least Jul 2023 (verified 17808683). Default limit 100; use limit=500."),
    dict(name="ultrasound", host="relay.ultrasound.money", operator="Ultra Sound (Ultrasound Money)",
         pubkey="0xa1559ace749633b997cb3fdacffb890aeebdb0f5a3b6aaa7eeeaf1a38af0a8fe88b9e4b1f61f236d2e64d95733327a62",
         notes="Live. Also served at relay-analytics.ultrasound.money. Bids may carry timestamp_ms from its own clock."),
    dict(name="bloxroute-max-profit", host="bloxroute.max-profit.blxrbdn.com", operator="bloXroute",
         pubkey="0x8b5d2e73e2a3a55c6c87b8b6eb92e0149a125c852751db1422fa951e42a09b82c142c3ea98d0d9930b056a3bc9896b8f",
         notes="DNS NXDOMAIN in 2026 (relay retired); historical data not reachable via this host."),
    dict(name="bloxroute-regulated", host="bloxroute.regulated.blxrbdn.com", operator="bloXroute",
         pubkey="0xb0b07cd0abef743db4260b0ed50619cf6ad4d82064cb4fbec9d3ec530f7c5e6793d9f286c4e082c0244ffb9f2658fe88",
         notes="Host answers 200 but returned [] for Jul 2023 (OFAC-filtered relay; may have dropped old data)."),
    dict(name="bloxroute-ethical", host="bloxroute.ethical.blxrbdn.com", operator="bloXroute",
         pubkey=None, notes="Retired relay; DNS NXDOMAIN in 2026."),
    dict(name="eden", host="relay.edennetwork.io", operator="Eden Network",
         pubkey="0xb3ee7afcf27f1f1259ac1787876318c6584ee353097a50ed84f51a1f21a323b3736f271a895c7ce918c038e4265918be",
         notes="DNS NXDOMAIN in 2026 (relay shut down)."),
    dict(name="agnostic", host="agnostic-relay.net", operator="Agnostic Gnosis",
         pubkey="0xa7ab7a996c8584251c8f925da3170bdfd6ebc75d50f5ddc4050a6fdc77f2a3b5fce2cc750d0865e05d7228af97d69561",
         notes="Live."),
    dict(name="aestus", host="aestus.live", operator="Aestus",
         pubkey="0xa15b52576bcbf1072f4a011c0f99f9fb6c66f3e1ff321f11f461d15e31b1cb359caa092c71bbded0bae5b5ea401aab7e",
         notes="Live (also mainnet.aestus.live)."),
    dict(name="titan", host="titanrelay.xyz", operator="Titan",
         pubkey="0x8c4ed5e24fe5c6ae21018437bde147693f68cda427cd1122cf20819c30eda7ed74f72dece09bb313f2a1855595ab677d",
         notes="Live. Also global.titanrelay.xyz / regional.titanrelay.xyz / eu.titanrelay.xyz (same operator, same pubkey)."),
    dict(name="ethgas", host="relay.ethgas.com", operator="ETHGas",
         pubkey="0x88ef3061f598101ca713d556cf757763d9be93d33c3092d3ab6334a36855b6b4a4020528dd533a62d25ea6648251e62e",
         notes="Live; newer relay (2025+), no 2023 data."),
    dict(name="btcs", host="relay.btcs.com", operator="BTCS",
         pubkey="0xb66921e917a8f4cfc3c52e10c1e5c77b1255693d9e6ed6f5f444b71ca4bb610f2eff4fa98178efbf4dd43a30472c497e",
         notes="Live; newer relay, no 2023 data."),
    dict(name="manifold", host="mainnet-relay.securerpc.com", operator="Manifold / SecureRPC",
         pubkey=None, notes="DNS NXDOMAIN in 2026 (relay retired); no historical access."),
    dict(name="wenmerge", host="relay.wenmerge.com", operator="wenmerge.com",
         pubkey=None, notes="Cloudflare 522 (origin down) in 2026."),
    dict(name="blocknative", host="builder-relay-mainnet.blocknative.com", operator="Blocknative",
         pubkey=None, notes="Retired (Blocknative closed the relay in 2023); host unreachable."),
    dict(name="relayooor", host="relayooor.wtf", operator="Relayooor",
         pubkey=None, notes="Retired community relay; host unreachable / non-API."),
]
BY_NAME = {r["name"]: r for r in RELAYS}


def _bt(relay, endpoint, **q):
    qs = "&".join(f"{k}={v}" for k, v in q.items())
    return f"https://{relay['host']}/relay/v1/data/bidtraces/{endpoint}?{qs}"


def _call(relay, endpoint, key, **q):
    return rf.get_soft(_bt(relay, endpoint, **q), source=f"relay-{relay['name']}", key=key, timeout=25)


def _norm(x):
    """Common shape for a relay response."""
    j = x["json"]
    return {"status": x["status"], "error": x["error"], "raw": x["path"],
            "items": j if isinstance(j, list) else None,
            "message": None if isinstance(j, list) else (x["body"][:200].decode("utf8", "replace") if x["body"] else None)}


def fetch_delivered(relay, block_number):
    return _norm(_call(relay, "proposer_payload_delivered", f"delivered_block{block_number}", block_number=block_number))


def fetch_bids(relay, block_number, limit=500):
    r = _norm(_call(relay, "builder_blocks_received", f"bids_block{block_number}", block_number=block_number, limit=limit))
    if r["items"] is not None and len(r["items"]) >= limit:
        # some relays (observed: titan) cap at the requested limit; retry once with a 20x limit and keep the larger answer
        big = _norm(_call(relay, "builder_blocks_received", f"bids_block{block_number}_limit{limit * 20}", block_number=block_number,
                          limit=limit * 20))
        if big["items"] is not None and len(big["items"]) > len(r["items"]):
            r = big
        if len(r["items"]) >= limit * 20 or (big["items"] is not None and len(big["items"]) == len(r["items"]) and len(r["items"]) == limit):
            r["truncated_warning"] = f"returned {len(r['items'])} == requested limit; may be truncated"
    return r


def fetch_block(block_number, only=None):
    """Delivered payload + all received bids for `block_number` from every relay (parallel). Dead hosts are reported,
    not hidden. Returns {"relays": {name: {"delivered":..., "bids":...}}}."""
    rels = [r for r in RELAYS if not only or r["name"] in only]

    def one(r):
        return r["name"], {"host": r["host"], "delivered": fetch_delivered(r, block_number), "bids": fetch_bids(r, block_number)}

    with ThreadPoolExecutor(max_workers=len(rels)) as ex:
        return {"block_number": int(block_number), "relays": dict(ex.map(one, rels))}


# ----------------------------------------------------------------------------------------------------- coverage
def coverage_probe(relay, slots):
    """For each slot, ask for the newest payload delivered at or before `slot` (cursor). Shows whether a relay keeps
    history that old: the returned slot is the nearest delivery <= cursor, or empty if nothing older exists."""
    out = []
    for s in slots:
        x = _norm(_call(relay, "proposer_payload_delivered", f"cursor{s}", cursor=s, limit=1))
        it = (x["items"] or [None])[0]
        out.append({"cursor_slot": s, "status": x["status"], "error": x["error"],
                    "nearest_slot": int(it["slot"]) if it else None, "block_number": int(it["block_number"]) if it else None,
                    "raw": x["raw"]})
    return out


def cmd_coverage():
    # sample dates: Merge, 2023-01-01, 2023-07-30, 2024-01-01, 2025-01-01, 2026-01-01, ~now
    pts = {"merge(2022-09-15)": MERGE_SLOT + 10, "2023-01-01": slot_of_ts(1672531200), "2023-07-30": slot_of_ts(1690754447),
           "2024-01-01": slot_of_ts(1704067200), "2025-01-01": slot_of_ts(1735689600), "2026-01-01": slot_of_ts(1767225600),
           "now": slot_of_ts(time.time()) - 5}
    res = {}
    with ThreadPoolExecutor(max_workers=len(RELAYS)) as ex:
        for r, c in zip(RELAYS, ex.map(lambda r: coverage_probe(r, list(pts.values())), RELAYS)):
            res[r["name"]] = c
    print(f"{'relay':22s}" + "".join(f"{k:>20s}" for k in pts))
    for n, c in res.items():
        row = ""
        for p in c:
            row += f"{('ERR' if p['error'] else (p['status'] if p['nearest_slot'] is None else p['nearest_slot'])):>20}"
        print(f"{n:22s}{row}")
    print("\n(cell = slot of nearest payload delivered at/before the cursor slot; 200 = answered but empty/none; ERR = host down)")
    return res


def cmd_retention(live=("flashbots", "ultrasound", "bloxroute-regulated", "agnostic", "aestus", "titan", "ethgas", "btcs")):
    """How far back does builder_blocks_received (the bid history) go per relay? For each age, take the newest payload
    that relay delivered at/before that time, then ask the same relay for all bids for that block."""
    ages = {"1h": 3600, "1d": 86400, "7d": 7 * 86400, "30d": 30 * 86400, "90d": 90 * 86400, "365d": 365 * 86400, "2023-07-30": None}
    now = time.time()

    def one(rn):
        r = BY_NAME[rn]
        row = {}
        for lab, age in ages.items():
            slot = slot_of_ts(now - age) if age else 6994202
            d = _norm(_call(r, "proposer_payload_delivered", f"cursor{slot}", cursor=slot, limit=1))
            it = (d["items"] or [None])[0]
            if not it:
                row[lab] = "no payload"
                continue
            b = fetch_bids(r, int(it["block_number"]))
            row[lab] = f"{len(b['items'])} bids" if b["items"] is not None else f"HTTP{b['status']}"
        return rn, row

    with ThreadPoolExecutor(max_workers=len(live)) as ex:
        res = dict(ex.map(one, live))
    print(f"{'relay':22s}" + "".join(f"{k:>14s}" for k in ages))
    for rn, row in res.items():
        print(f"{rn:22s}" + "".join(f"{row[k]:>14s}" for k in ages))
    return res


# ------------------------------------------------------------------------------------------------ builder names
# Alias rules copied from flashbots/relayscan vars/builder_aliases.go (saved raw: data/raw/relay-sources/
# relayscan_vars_builder_aliases.go.txt). Name is derived from the *delivered block's extraData*.
def alias_from_extradata(extra):
    e = extra or ""
    import re
    if "penguinbuild.org" in e: return "penguinbuild.org"
    if "builder0x69" in e: return "builder0x69"
    if "rsync" in e: return "rsync-builder.xyz"
    if re.search("s[0-9]+e[0-9].*(t|f)", e): return "bob the builder"
    if "BuilderNet" in e: return "BuilderNet"
    if e.startswith("Illuminate Dmocratize Dstribute"): return "Flashbots"  # the Flashbots builder's own extraData tagline
    return e.strip()


def _decode_extra(h):
    try:
        return bytes.fromhex(h[2:]).decode("utf8", "replace").strip("\x00")
    except Exception:  # noqa: BLE001
        return h


def resolve_builder_names(pubkeys, hint_block=None, relays=("flashbots", "ultrasound", "titan", "agnostic", "aestus")):
    """pubkey -> {name, extra_data, evidence}. Public pubkey->name tables are not published by the relays, so we derive:
    find a payload this pubkey *delivered* (relay data API `builder_pubkey=` filter, nearest to hint_block's slot), read
    that block's extraData over RPC and apply relayscan's alias rules. Evidence (relay raw file + block raw file) is
    returned so the mapping is auditable. Unknown stays unknown (name=None)."""
    out = {}
    cursor = None
    if hint_block:
        blk = rf.rpc("eth_getBlockByNumber", [hex(int(hint_block)), False], key=f"block_hdr_{hint_block}")
        cursor = slot_of_ts(int(blk["timestamp"], 16)) + 1  # newest delivery at/just before the race slot
    for pk in pubkeys:
        found = None
        for rn in relays:
            r = BY_NAME[rn]
            q = dict(builder_pubkey=pk, limit=1)
            if cursor:
                q["cursor"] = cursor
            x = _norm(_call(r, "proposer_payload_delivered", f"builder_{pk[:12]}_c{cursor}", **q))
            if x["items"]:
                it = x["items"][0]
                bn = int(it["block_number"])
                blk = rf.rpc("eth_getBlockByNumber", [hex(bn), False], key=f"block_hdr_{bn}")
                extra = _decode_extra(blk["extraData"])
                found = {"name": alias_from_extradata(extra), "extra_data": extra, "via_relay": rn,
                         "delivered_block": bn, "relay_raw": x["raw"], "fee_recipient_of_block": blk["miner"],
                         "evidence": f"pubkey delivered block {bn} via {rn}; block extraData={extra!r}"}
                break
        out[pk] = found or {"name": None, "evidence": "no delivered payload found for this pubkey on queried relays (never won, "
                                                       "or relay does not keep that history)"}
    return out


# --------------------------------------------------------------------------------------------------------- CLI
def cmd_probe(block):
    res = fetch_block(block)
    print(f"block {block}")
    for n, v in res["relays"].items():
        d, b = v["delivered"], v["bids"]
        def s(x):
            if x["error"]: return "DOWN(" + x["error"][:40] + ")"
            if x["items"] is None: return f"HTTP{x['status']} {x['message']}"
            return f"HTTP{x['status']} n={len(x['items'])}"
        print(f"  {n:22s} delivered: {s(d):45s} bids: {s(b)}")
    return res


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("probe"); p.add_argument("--block", type=int, default=17808683)
    sp.add_parser("coverage")
    sp.add_parser("retention")
    p = sp.add_parser("fetch"); p.add_argument("block", type=int)
    p = sp.add_parser("names"); p.add_argument("pubkeys", nargs="+"); p.add_argument("--hint-block", type=int)
    a = ap.parse_args()
    if a.cmd in ("probe", "fetch"):
        cmd_probe(a.block if a.cmd == "fetch" else a.block)
    elif a.cmd == "coverage":
        cmd_coverage()
    elif a.cmd == "retention":
        cmd_retention()
    elif a.cmd == "names":
        print(json.dumps(resolve_builder_names(a.pubkeys, a.hint_block), indent=1))


if __name__ == "__main__":
    main()
