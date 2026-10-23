#!/usr/bin/env python3
"""Drop relay bid rows that belong to another slot than the race's slot from incidents/*/race_*.json (idempotent).

The relay data API filters bidtraces by block_number only, so a row can carry a different slot (a competing proposal for the same height).
blockrace.relay_section now excludes them when a race doc is built; this script applies the same rule to the race docs already on disk,
using the saved raw bid files (which keep every row) to find them, then recomputes the summary fields that depend on the bid list.
"""
import glob, json, os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
APPLY = '--apply' in sys.argv


def main():
    n = 0
    for f in sorted(glob.glob(os.path.join(ROOT, 'incidents/*/race_*.json'))):
        d = json.load(open(f))
        sl = (d.get('block') or {}).get('slot')
        if sl is None or 'bids' not in d:
            continue
        off = []
        for rn, v in (d.get('relays_status') or {}).items():
            p = v.get('raw_bids')
            if not p or not os.path.exists(os.path.join(ROOT, p)):
                continue
            try:
                rows = json.load(open(os.path.join(ROOT, p)))
            except Exception:
                continue
            if not isinstance(rows, list):
                continue
            for x in rows:
                if x.get('slot') is not None and str(x['slot']) != str(sl):
                    off.append({"relay": rn, "slot": x['slot'], "block_hash": x.get('block_hash'), "builder_pubkey": x.get('builder_pubkey'),
                                "value_wei": x.get('value'), "timestamp_ms": x.get('timestamp_ms')})
        bs = d['bid_summary']
        if not off:
            continue
        key = lambda r, b: (r['relay'], r['block_hash'], r['builder_pubkey'], str(r['value_wei']), int(r['timestamp_ms'] or 0))
        offk = {(o['relay'], o['block_hash'], o['builder_pubkey'], str(o['value_wei']), int(o['timestamp_ms'] or 0)) for o in off}
        kept = [b for b in d['bids'] if (b['relay'], b['block_hash'], b['builder_pubkey'], str(b['value_wei']), int(b['timestamp_ms'] or 0)) not in offk]
        if len(kept) + len(off) != len(d['bids']):
            print('!! count mismatch', f, len(kept), len(off), len(d['bids']))
            continue
        d['bids'] = kept
        best, esc = 0, []
        for b in kept:
            v = int(b['value_wei'])
            if v > best:
                best = v
                esc.append({"timestamp_ms": b["timestamp_ms"], "t_rel_slot_ms": b["t_rel_slot_ms"], "relay": b["relay"], "builder_pubkey": b["builder_pubkey"],
                            "builder_name": b.get("builder_name"), "value_eth": b["value_eth"], "block_hash": b["block_hash"], "is_winning_block": b["is_winning_block"]})
        win = [b for b in kept if b['is_winning_block']]
        bs.update({
            "n_bids": len(kept), "n_builders": len({b['builder_pubkey'] for b in kept}),
            "bids_per_relay": {r: s['bids_n'] - sum(1 for o in off if o['relay'] == r) for r, s in d['relays_status'].items() if s.get('bids_n')},
            "first_bid_t_rel_slot_ms": kept[0]['t_rel_slot_ms'] if kept else None, "last_bid_t_rel_slot_ms": kept[-1]['t_rel_slot_ms'] if kept else None,
            "max_bid_eth": max((b['value_eth'] for b in kept), default=None),
            "winning_block_submissions": [{"relay": b['relay'], "t_rel_slot_ms": b['t_rel_slot_ms'], "value_eth": b['value_eth']} for b in win],
            "record_bids": esc, "n_record_bids": len(esc), "n_offslot_excluded": len(off), "offslot_excluded": off})
        n += 1
        print('%s: %d off-slot row(s) dropped (%d kept)' % (os.path.relpath(f, ROOT), len(off), len(kept)))
        if APPLY:
            json.dump(d, open(f, 'w'), indent=1)
    print('race docs changed:', n, '(applied)' if APPLY else '(dry run)')


if __name__ == '__main__':
    main()
