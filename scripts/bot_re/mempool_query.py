"""Query Flashbots mempool-dumpster parquet remotely (HTTP range reads) for the txs relevant to the Ronin replay. Result saved raw + MANIFEST."""
import sys, json, pathlib, duckdb
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))
import rawfetch as r
U = "https://mempool-dumpster.flashbots.net/ethereum/mainnet/2024-08/2024-08-06.parquet"
BRIDGE = "0x64192819ac13ef72bf6b5ae239ac672b43a9af08"
con = duckdb.connect(); con.execute("INSTALL httpfs; LOAD httpfs;")
q = f"""SELECT timestamp, hash, "from", "to", nonce, gasPrice, gasTipCap, gasFeeCap, dataSize, data4Bytes, sources, includedAtBlockHeight, includedBlockTimestamp, inclusionDelayMs
        FROM read_parquet('{U}') WHERE lower("to") = '{BRIDGE}' AND data4Bytes = '0x4d0d6673' ORDER BY timestamp"""
rows = con.execute(q).fetchall(); cols = [d[0] for d in con.description]
res = [dict(zip(cols, [str(v) if not isinstance(v, (int, type(None), list)) else v for v in row])) for row in rows]
p = r._save("mempool-dumpster", "ronin_submitWithdrawal_2024-08-06", "json", json.dumps({"query": q, "source": U, "rows": res}, indent=1).encode(),
            {"url": U, "method": "duckdb-httpfs-parquet", "status": 200})
print(len(res), p)
for x in res: print(x["timestamp"], x["hash"][:12], x["from"][:12], x["nonce"], x["gasFeeCap"], x["sources"], x["includedAtBlockHeight"], x["inclusionDelayMs"])
