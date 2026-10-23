"""Mempool-dumpster lookup for the Kelp/rsETH incident (2026-09-15, block 25980525): attacker EOA txs and anything to the exploited executor."""
import sys, json, pathlib, duckdb
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))
import rawfetch as r
U = "https://mempool-dumpster.flashbots.net/ethereum/mainnet/2026-09/2026-09-15.parquet"
ATT = "0x0dc2c5d6b05a317076cf501f7e7be36a5dfe9b66"; EXE = "0x10605ee48ff962952c966277a5d2dac0a0705cb1"; YOINK = "0xfde0d1575ed8e06fbf36256bcdfa1f359281455a"; BOT = "0x80bf7db69556d9521c03461978b8fc731dbbd4e4"
con = duckdb.connect(); con.execute("INSTALL httpfs; LOAD httpfs;")
q = f"""SELECT timestamp, hash, "from", "to", nonce, gasPrice, gasTipCap, gasFeeCap, dataSize, data4Bytes, sources, includedAtBlockHeight, includedBlockTimestamp, inclusionDelayMs
        FROM read_parquet('{U}') WHERE lower("from") IN ('{ATT}','{YOINK}') OR lower("to") IN ('{EXE}','{BOT}') ORDER BY timestamp"""
rows = con.execute(q).fetchall(); cols = [d[0] for d in con.description]
res = [dict(zip(cols, [str(v) if not isinstance(v, (int, type(None), list)) else v for v in row])) for row in rows]
p = r._save("mempool-dumpster", "kelp_attacker_executor_yoink_2026-09-15", "json", json.dumps({"query": q, "source": U, "rows": res}, indent=1).encode(), {"url": U, "method": "duckdb-httpfs-parquet", "status": 200})
print(len(res), p)
for x in res: print(x["timestamp"], x["hash"][:12], x["from"][:10], (x["to"] or "")[:10], x["nonce"], x["data4Bytes"], x["gasFeeCap"], x["sources"], x["includedAtBlockHeight"])
