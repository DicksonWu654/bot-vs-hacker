# auction tooling - auction infrastructure (relays, mempool-dumpster, race reconstructor)

Written 2026-10-21. All fetches go through `scripts/lib/rawfetch.py` (raw body saved under `site/raw/<source>/`, one line
per request in `site/raw/MANIFEST.json`). Python: `python3`.

| script | what |
|---|---|
| `scripts/relays.py` | relay registry + data-API fetchers (`probe`, `coverage`, `retention`, `fetch`, `names`) |
| `scripts/mempool.py` | mempool-dumpster index/download/duckdb lookup (`index`, `fetch`, `lookup`) |
| `scripts/blockrace.py` | one block -> `incidents/<slug>/race.json` |
| `scripts/pooltouch.py` | which txs sent by an address touch given contracts (public-action description) |
| `scripts/lib/rawfetch.py` | added `get_soft` (records 4xx/5xx/network failures too), `download` (streams big files, sha256), `raw_path` |

```
PY=.venv/bin/python
$PY scripts/blockrace.py 17806550 --focus 0xc93eb238ff42632525e990119d3edc7775299a70b56e54d83ec4f53736400964 \
    --watch 0xc897b98272aa23714464ea2a0bd5180f1b8c0025 --slug curve-vyper-2023       # -> incidents/curve-vyper-2023/race.json
$PY scripts/blockrace.py N --out PATH     # --no-mempool / --no-names to skip those steps; pre-Merge blocks work too
$PY scripts/relays.py retention           # how far back each relay serves bids (re-run: retention is shrinking)
$PY scripts/mempool.py lookup 2023-09-05 0x1274b32d...   # downloads csv.zip + sourcelog (~190 MB) once
```

## 1. MEV-Boost relay data API (post-Merge, block >= 15537394 / slot 4700013)

`GET https://<relay>/relay/v1/data/bidtraces/proposer_payload_delivered?block_number=N|slot=|block_hash=|builder_pubkey=|cursor=|limit=`
`GET https://<relay>/relay/v1/data/bidtraces/builder_blocks_received?block_number=N|slot=|block_hash=|builder_pubkey=&limit=`
Bid fields: slot, parent_hash, block_hash, builder_pubkey, proposer_pubkey, proposer_fee_recipient, gas_limit, gas_used,
value (wei), num_tx, block_number, timestamp, `timestamp_ms` (relay receive time), optimistic_submission.
`proposer_payload_delivered` has no timestamp. Slot start = 1606824023 + 12*slot; `t_rel_slot_ms` in race.json is bid time minus that.
The API never returns the *transactions* of any bid, only hashes and counts.

Relay status probed 2026-10-21 (registry in `relays.py`; relay BLS pubkeys from flashbots/relayscan `config-mainnet.yaml`,
saved at `site/raw/relay-sources/`):

| relay | host | status 2026-10 |
|---|---|---|
| Flashbots | boost-relay.flashbots.net | live; **bid history back to at least 2023-07-30** (only relay that has it) |
| Ultra Sound | relay.ultrasound.money | live; bids kept ~30-90 days only; delivered-payload history back to 2023 |
| bloXroute regulated | bloxroute.regulated.blxrbdn.com | live; delivered only since ~2025 (older empty), bids 90-365 d |
| bloXroute max-profit / ethical | bloxroute.{max-profit,ethical}.blxrbdn.com | DNS NXDOMAIN (retired) |
| Agnostic Gnosis | agnostic-relay.net | live; delivered back to 2023, bids ~90 d |
| Aestus | aestus.live | live; delivered history empty before 2026 on cursor queries, bids 90-365 d |
| Titan | titanrelay.xyz (also global./regional./eu.) | live; delivered/bids only from ~2025 (365 d: 500 bids = capped, `relays.py` re-queries with 20x limit) |
| ETHGas | relay.ethgas.com | live, since late 2025 |
| BTCS | relay.btcs.com | answers, last delivery 2025-12-01 (stale) |
| Eden, Manifold/SecureRPC | relay.edennetwork.io, mainnet-relay.securerpc.com | DNS NXDOMAIN (retired) |
| wenmerge, relayooor | relay.wenmerge.com, relayooor.wtf | Cloudflare 522/523 (origin down) |
| Blocknative | builder-relay-mainnet.blocknative.com | resolves but connection times out (retired 2023) |

`relays.py retention` output (cell = number of bids the relay still returns for a block it delivered N days ago):

```
relay                         1h    1d    7d   30d   90d  365d  2023-07-30
flashbots                    180   168   154   111   177   133    125
ultrasound                   998  2877  4131  2134     0     0      0
bloxroute-regulated         1252  1375  2380  3158  2949     0   (no payload)
agnostic                     487   551   590  1006   488     0      0
aestus                       411   470   470   457   474  (none) (none)
titan                        286   388   344   375   378   500+  (none)
ethgas / btcs               ~850 / 43 ... (no 2023 data)
```
**Consequence: for any 2023-era incident only Flashbots bid history exists; relays that delivered the winning block
(Ultra Sound, Agnostic) answer `[]`.** The Flashbots data shows what builders sent *to Flashbots*; the winning bid may be
absent (e.g. block 17806550 was delivered by Ultra Sound, but BuildAI also sent the same block hash to Flashbots at -217 ms
so it is visible). Fetch recent incidents immediately: Ultra Sound/Agnostic drop bids after ~30-90 days.
Better source for 2024-06+: Relayscan bid archive https://bidarchive.relayscan.io (CC0 daily bid files across relays; not yet fetched).
`site/raw/relay-sources/relay_coverage_2026-10-21.txt` (copy in this folder) = delivered-payload coverage matrix from `relays.py coverage`.

**Builder names.** No public pubkey->name table was found (mevboost.pics is a JS app; web search budget was exhausted). Names are
derived and auditable: `relays.resolve_builder_names` finds a payload that pubkey delivered (relay `builder_pubkey=` filter, nearest to
the block), reads that block's `extraData` over RPC and applies relayscan's alias rules (`site/raw/relay-sources/relayscan_vars_builder_aliases.go.txt`);
`Illuminate Dmocratize Dstribute` -> Flashbots. A pubkey that never won on the queried relays stays `name: null` (unknown, not none).
race.json `builder_names` keeps the evidence (relay raw file, block, extraData).

## 2. mempool-dumpster (https://mempool-dumpster.flashbots.net/ethereum/mainnet/YYYY-MM/)

Per UTC day D: `D.parquet` (~700 MB; has rawTx), `D.csv.zip` (~100 MB; first-seen `timestamp_ms` across all sources, `sources`,
inclusion block/delay), `D_sourcelog.csv.zip` (~90 MB; `timestamp_ms,hash,source` = every source's own first sighting),
`D_summary.txt`. Coverage verified from the monthly `index.html` files: **first day 2023-08-07** (csv; parquet from 08-08); sourcelog
**only 2023-08-31 .. 2025-07-14**; later days have csv/parquet but no sourcelog (so only the merged first-seen and the source list).
Sources: local geth ("local"/a-pool), Alchemy, Infura, bloXroute ("blx" in the sourcelog), later Chainbound/Eden/Mempool Guru.
Txs already on-chain when first received are dropped from the csv/parquet (kept only in the sourcelog), and private-flow /
bundle txs never appear: absence means "not seen by these nodes", not "never public".
`mempool.py` downloads csv.zip + sourcelog + summary (not parquet) to `site/raw/mempool-dumpster/`, extracts once to the
regenerable cache `data/cache/` (gitignored) and queries with duckdb. Demo (`mempool_demo_2023-09-05.json`): FloorDAO attack tx
0x1274b32d... first seen 07:25:15.315 UTC by bloXroute, apool +10 ms, included block 18068773; HeavensGate attack tx 0xe28ca1f4... is NOT in the dump (private flow).
**Curve/Vyper (2023-07-30) is outside coverage: mempool is "in-block evidence only"** (`mempool_curve_2023-07-30.json`).

## 3. blockrace.py output (`bvh-race/1`)

`block` (number, hash, timestamp, slot, fee_recipient, extraData), `txs[]` (every tx in order: index, from, to, status, gas_used,
gas_price_gwei, priority_fee_gwei, `coinbase_transfer_wei` = ETH sent to block.miner by non-reverted calls, `builder_revenue_wei`,
`touches_watch`, for focus txs `watch_calls` = calls into watched contracts with selector/value/reverted), `focus_summary`
(position, builder revenue, share of the winning bid), `delivered[]`, `winner` (builder, relays, bid, proposer payment tx
check), `bids[]` sorted by `timestamp_ms` (relay, t_rel_slot_ms, builder_pubkey/name, value, block_hash, num_tx, gas_used,
`is_winning_block`, `contains_focus_txs` = true only for the winning hash, else `"unknown"`), `bid_summary.record_bids` (the
escalation: every bid that set a new best value), `relays_status`, `mempool`, `caveats`, `raw_refs` (value group -> data/raw path;
every bid/delivery row carries its own `raw`). Traces via `debug_traceBlockByNumber` callTracer on eth.drpc.org (works, <1 s),
receipts via `eth_getBlockReceipts`. Not knowable: contents of losing bids; real network arrival time of a block/tx before
Aug 2023; clock skew between relays.

## 4. Pre-Merge Flashbots data (2021-2022 MEV-geth bundles)

`https://blocks.flashbots.net/v1/blocks?block_number=N` is **dead: HTTP 410 "This website has been decommissioned"** (also the
bare path). Saved: `site/raw/flashbots-blocks-api/blocks_13500000.json`. `blockrace.py` still calls it for blocks < 15537394,
parses `transactions[].{bundle_type,bundle_index,coinbase_transfer}` if it ever answers 200, and otherwise falls back to
**inferred** flags (`inferred_bundle_like` = coinbase transfer > 0 and priority fee < 1 gwei) plus real trace-derived coinbase
transfers; both are labelled in `caveats`. Archive leads (not verified; web-search budget ran out, no Wayback use): the
`flashbots/mev-blocks` server dumped `s3://blocks-api/latest_blocks.json(.xz)` (schema = the API's `blocks[]`; the bucket no longer
exists publicly, checked), the Dune `flashbots.*` datasets (docs page 404 on the guessed URL), `flashbots/mev-inspect-*` DB dumps.
Source code saved in `site/raw/flashbots-premerge-sources/`. Needs a follow-up search for a public mirror (Dune/BigQuery/HF/Zenodo).

## 5. Curve/Vyper case: what the data says (2023-07-30)

**The c0ffeebabe front-run is not an alETH or pETH tx.** Scanning every c0ffeebabe.eth (0xc0ffeebabe5d...9671) tx in blocks 17805000-17810500
with traces (`incidents/curve-vyper-2023/c0ffeebabe_pool_touches.json`), exactly two touch a hacked Curve pool, neither alETH
(0xc4c3...) nor pETH (0x9848...):

1. **msETH/ETH pool (0xc897...), block 17806550 (14:50:11 UTC, slot 6992049), tx 0xc93eb238...0964, index 0.** Priority fee 0 but a
   0.1733 ETH coinbase transfer = 47.9 % of the winning bid (0.3618 ETH, BuildAI, delivered by Ultra Sound; BuildAI also sent the same
   block to Flashbots at -217 ms). The same pool-call sequence (add_liquidity 5000 ETH, remove, nested add_liquidity 5000 ETH,
   remove_liquidity_one_coin) is made two blocks later (block 17806552, 24 s later, Flashbots-built, 0.2728 ETH via Flashbots/Agnostic) by tx
   0xe2eb61b1...a22a (index 3, EOA 0x19c784..., contract 0xbdee6f2b..., 37 gwei priority fee, no coinbase transfer), whose add_liquidity/remove calls on the pool revert
   (trace: `error` on those frames; the pool had just been drained by the first tx - cause inferred, not proven). This is the confirmed-onchain pattern (same calls from a different
   address, earlier block); whether 0x19c784 is "the hacker" or a copycat is not established here. Bid auction: `race.json` (161 Flashbots bids).
2. **CRV/ETH pool (0x8301...), block 17808683 (22:00:47 UTC, slot 6994202), tx 0xcd99fadd...2052 (EigenPhi/Decrypt-cited), index 7**,
   priority fee 0, no coinbase transfer, built by eth-builder.com (value 0.5033 ETH, via Flashbots; 125 bids). This is 853 blocks (~2.8 h) AFTER the
   attacker's CRV/ETH exploit (tx 0x2e7dc8b2...477c, block 17807830, index 6, 19:08:23 UTC): a post-hack opportunistic trade on the imbalanced pool, not a
   same-block front-run. c0ffeebabe returned 2879.54 ETH to the Curve deployer 0xc447fcaf... in tx 0xb7675412...54fd (block 17809228); public messages:
   0xc52cce67... (block 17808834, "moving funds to cold wallet ..."), Curve deployer reply 0x65670d8e... ("One tx you front-ran was a hack of CRV/ETH pool. Can refund?").
3. alETH/ETH: exploit tx 0xb676d789...9801 (block 17806772, index 10, from 0xdce5d6b4..., 20 000 ETH Balancer flash loan); pETH: 0xa84aa065...620c
   (block 17806056, index 0; 807 Flashbots bids from 66 pubkeys escalating to 333 ETH, no relay reports delivering the block - it was built by rsync, presumably
   via a relay no longer reachable). Other bots (0x...7f150b, 0x...a84d1a) pulled ETH out of the alETH pool via `exchange` at blocks 17806741/17806742, i.e. before the 17806772 exploit: not c0ffeebabe, candidates for bot analysis.

Files: `incidents/curve-vyper-2023/race.json` (= block 17806550, the msETH front-run) and `race_<block>.json` for 17806552, 17806056,
17806772, 17807830, 17808683.
