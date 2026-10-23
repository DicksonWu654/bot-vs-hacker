#!/usr/bin/env python3
"""Flashbots mempool-dumpster access: first-seen timestamp + sources for transaction hashes.

Archive: https://mempool-dumpster.flashbots.net/ethereum/mainnet/YYYY-MM/   (CC-0; github.com/flashbots/mempool-dumpster)
Per UTC day D (files for the previous day are uploaded 04:00-04:30 UTC):
    D.parquet               ~700-800 MB; tx metadata + rawTx (timestamp, hash, from, to, ..., sources[], rawTx)
    D.csv.zip               ~100 MB;  same metadata WITHOUT rawTx; one row per unique tx, `timestamp_ms` = first seen by ANY
                            source, `sources` = space-separated list of sources that saw it
    D_sourcelog.csv.zip     ~90 MB;   timestamp_ms,hash,source : one row per (tx, source) first sighting -> per-source
                            first-seen times (this is what shows who saw a tx first). Present 2023-08-31 .. mid-2025
                            (check `index`); absent before and for later months in the listing.
    D_summary.txt           ~2 kB
Coverage: first day 2023-08-07 (csv) / 2023-08-08 (parquet). NOTHING exists for July 2023 or earlier.
Caveat (README): transactions that were already on-chain when received are dropped from D.csv/parquet (kept only in the
sourcelog), so private/Flashbots-bundle txs never appear in the public mempool files at all.

We download csv.zip + sourcelog (about 190 MB/day), not the parquet (use --parquet if rawTx is needed), stream them
into data/raw/mempool-dumpster/ via rawfetch.download (sha256 -> MANIFEST), extract once into data/cache/ (derived,
regenerable, not committed) and query with duckdb.

CLI
    mempool.py index YYYY-MM                       list files published for a month (saves index.html raw)
    mempool.py fetch YYYY-MM-DD [--parquet]        download day files
    mempool.py lookup YYYY-MM-DD HASH [HASH ...]   first seen (any source) + per-source first-seen + inclusion info
Library: lookup(date, hashes) -> {hash: {...} | None}; coverage(date) -> dict
"""
import argparse, datetime as dt, json, pathlib, re, sys, zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "lib"))
import rawfetch as rf  # noqa: E402

BASE = "https://mempool-dumpster.flashbots.net/ethereum/mainnet"
SRC = "mempool-dumpster"
CACHE = rf.ROOT / "data" / "cache" / "mempool-dumpster"
FIRST_DAY = dt.date(2023, 8, 7)


def index(month):
    """Listing for YYYY-MM -> {date: [file kinds]}. Raw index.html saved."""
    x = rf.get_soft(f"{BASE}/{month}/index.html", source=SRC, key=f"index_{month}", ext="html")
    names = re.findall(r'href=(\d{4}-\d{2}-\d{2}[^ >]*)', x["body"].decode("utf8", "replace"))
    days = {}
    for n in names:
        d, kind = n[:10], n[10:].lstrip("_.") or "?"
        days.setdefault(d, []).append(kind)
    return {"raw": x["path"], "status": x["status"], "days": days}


def coverage(date):
    date = dt.date.fromisoformat(date) if isinstance(date, str) else date
    if date < FIRST_DAY:
        return {"date": str(date), "covered": False, "reason": f"mempool-dumpster starts {FIRST_DAY}; no data before"}
    idx = index(date.strftime("%Y-%m"))
    kinds = idx["days"].get(str(date), [])
    return {"date": str(date), "covered": bool(kinds), "files": kinds, "index_raw": idx["raw"]}


def fetch_day(date, parquet=False, sourcelog=True):
    date = str(date)
    month = date[:7]
    cov = coverage(date)
    if not cov["covered"]:
        raise SystemExit(f"no mempool-dumpster files for {date}: {cov}")
    want = ["csv.zip", "summary.txt"] + (["sourcelog.csv.zip"] if sourcelog else []) + (["parquet"] if parquet else [])
    out = {}
    for k in want:
        if k not in cov["files"]:
            print(f"  (not published: {k})", file=sys.stderr)
            continue
        name = f"{date}.{k}" if k in ("csv.zip", "parquet") else f"{date}_{k}"
        out[k] = rf.download(f"{BASE}/{month}/{name}", SRC, name)
    return out


def _extract(date, zipname, csvname):
    CACHE.mkdir(parents=True, exist_ok=True)
    dst = CACHE / csvname
    if not dst.exists():
        src = rf.RAW / SRC / zipname
        with zipfile.ZipFile(src) as z, z.open(z.namelist()[0]) as f, open(dst.with_suffix(".part"), "wb") as o:
            while chunk := f.read(1 << 22):
                o.write(chunk)
        dst.with_suffix(".part").replace(dst)
    return dst


def lookup(date, hashes):
    """First-seen + per-source first-seen for each hash, with the raw files the numbers come from."""
    import duckdb
    date = str(date)
    hashes = [h.lower() for h in hashes]
    cov = coverage(date)
    if not cov["covered"]:
        return {"coverage": cov, "txs": {h: None for h in hashes}}
    files = fetch_day(date)
    meta_csv = _extract(date, f"{date}.csv.zip", f"{date}.csv")
    con = duckdb.connect()
    inlist = ",".join("'" + h + "'" for h in hashes)
    meta = {r[0]: r for r in con.execute(
        f"SELECT lower(hash), timestamp_ms, \"from\", \"to\", gas_price, gas_tip_cap, gas_fee_cap, sources, included_at_block_height, "
        f"included_block_timestamp_ms, inclusion_delay_ms FROM read_csv('{meta_csv}', header=true, all_varchar=true) "
        f"WHERE lower(hash) IN ({inlist})").fetchall()}
    slog = {}
    if "sourcelog.csv.zip" in files:
        slog_csv = _extract(date, f"{date}_sourcelog.csv.zip", f"{date}_sourcelog.csv")
        for h, ts, s in con.execute(
                f"SELECT lower(hash), timestamp_ms, source FROM read_csv('{slog_csv}', header=true, all_varchar=true) "
                f"WHERE lower(hash) IN ({inlist}) ORDER BY CAST(timestamp_ms AS BIGINT)").fetchall():
            slog.setdefault(h, []).append({"source": s, "first_seen_ms": int(ts)})
    raw = {k: str(v.relative_to(rf.ROOT)) for k, v in files.items()}
    out = {}
    for h in hashes:
        m, s = meta.get(h), slog.get(h)
        if not m and not s:
            out[h] = None
            continue
        out[h] = {
            "first_seen_ms": int(m[1]) if m else s[0]["first_seen_ms"],
            "first_seen_utc": dt.datetime.fromtimestamp((int(m[1]) if m else s[0]["first_seen_ms"]) / 1000, dt.UTC).isoformat(),
            "sources": (m[7] or "").split() if m else None,
            "per_source_first_seen": s,   # None when sourcelog not published for that day
            "included_at_block": int(m[8]) if m and m[8] else None,
            "included_block_timestamp_ms": int(m[9]) if m and m[9] else None,
            "inclusion_delay_ms": int(m[10]) if m and m[10] else None,
            "in_tx_file": bool(m), "in_sourcelog": bool(s),
            "raw_refs": {"tx_csv": raw.get("csv.zip"), "sourcelog": raw.get("sourcelog.csv.zip"), "summary": raw.get("summary.txt")},
        }
    return {"coverage": cov, "txs": out}


def find_date_for_tx_block(block_ts):
    return dt.datetime.fromtimestamp(block_ts, dt.UTC).date()


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("index"); p.add_argument("month")
    p = sp.add_parser("fetch"); p.add_argument("date"); p.add_argument("--parquet", action="store_true")
    p = sp.add_parser("lookup"); p.add_argument("date"); p.add_argument("hashes", nargs="+")
    a = ap.parse_args()
    if a.cmd == "index":
        r = index(a.month)
        for d, k in sorted(r["days"].items()):
            print(d, " ".join(sorted(k)))
    elif a.cmd == "fetch":
        print(json.dumps({k: str(v) for k, v in fetch_day(a.date, parquet=a.parquet).items()}, indent=1))
    else:
        print(json.dumps(lookup(a.date, a.hashes), indent=1))


if __name__ == "__main__":
    main()
