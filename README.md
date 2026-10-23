# The Bot Beat the Hacker

When a smart contract is exploited, the attacker is not the only one who can read the exploit. A generalized front-runner, a bot that copies a profitable transaction and swaps in its own beneficiary, can sometimes land its copy first. This repository reconstructs those races on Ethereum, second by second: 29 incidents split into 43 races, with the block-builder auction rebuilt from relay bid traces and the attacker's first-seen time from the Flashbots mempool archive wherever those exist. In 15 incidents (19 races) a bot beat the hacker, with the recorded verdicts. Euler is excluded because the copier may be the attacker’s own second account.

- Live site: https://bot-beat-the-hacker.shadow654.chatgpt.site (source in `site/`)
- Paper: https://bot-beat-the-hacker.shadow654.chatgpt.site/paper.html (also `paper/paper.md` here)
- Repository: https://github.com/DicksonWu654/bot-vs-hacker

Compiled with a swarm of AI agents, so there will be mistakes; every number links its saved source; corrections welcome. See "Report a correction" below.

## Headline numbers

| Finding | Figure |
|:---|:---|
| Races reconstructed | 43 races in 29 incidents, each with a written verdict rule and a race type |
| A bot beat the hacker | 19 races in 15 incidents: 15 where the bot's transaction landed before a pending attack, 4 where it used the attacker's own deployed setup first |
| How the bot landed first | 9 races in an earlier block, 6 in the same block at an earlier position, 4 before the attacker's call ever landed |
| Builder bid response (ms) | 5 measurable races, 266 to 4138 ms (median 873 ms), from the trigger's first public sighting to the winning builder's first step-up bid |
| Public mempool | the trigger was seen publicly before inclusion in 8 of 28 races from August 2023 onward |
| Builder payment before refunds | mature-PBS median 97.8% of gross; after refunds, 26.8% (11 priced headline rows) |
| Returns | bots returned a pooled 83.1% of the gross over 14 headline races (3 with known zero), and 89.8% of what they kept after paying the builder over 12; returns are voluntary and sometimes late or absent |

The payment distribution is split: Neemo (0.018%), Kelp (0.607%) and BiFi (1.45%) paid under 2%. Refunds change realised cost: Ronin’s block paid 802.79 ETH before a 791.74 ETH refund (11.04 ETH after, 98.6% refunded); Alkimiya 50.83 → 2.56 ETH (95.0% refunded); Paraswap 6.45 → 2.11 ETH; DeFi Plaza 66.32 → 61.56 ETH. These are the paper §5.4 figures; some refunds cover other transactions in the block. In two of 11 mature-PBS headline rows (Blueberry and Makina), the builder side passed most of its payment to the victim. Makina's large payment brings this to 67.5% of all payments pooled; its return followed two days later, after a Safe Harbor bounty negotiation. In the other nine rows, no builder-side payment reached victims in the documented window. Pooled, 1,287.3 ETH of 1,906.0 ETH reached victims; 54.6 ETH was refunded to bots, leaving about 564.1 ETH with builders and proposers.

Sensitivity: excluding the four c0ffeebabe.eth rows gives 15 headline rows in 13 incidents. Our call-level comparison for those rows is withheld by publication policy; anyone can compare the public traces. Each row publishes the raced attacker transaction hash and the blocks and positions. The Curve ordering predates the mempool archive, so pending visibility is inferred from in-block evidence only.

Return status follows one rule: **returned** = everything went back to the victim side except a bounty the victim agreed to or offered; **partial** = some came back, otherwise; **none** = known zero within the documented search window; **unknown** = unresolved. Unizen is partial at incident level; its return is unallocated across rows. Headline statuses are 4 returned, 11 partial, 3 none and 1 unknown. Gross pooled return percentages include known zeros and exclude unknown or unpriced returns.

Figures are read from `data/headline_stats.json` at export time. The paper defines each one and gives its denominator.

## Browse

`site/` is a self-contained static site with relative links. Open `site/index.html`, or serve the folder:

```
python3 -m http.server -d site 8000
```

It has an animated three-lane replay for every race (`incident.html?slug=...`), the comparison table, an explainer, the evolution study ("has the dark forest changed?") and the methods page. Replay timelines show entries fully backed by published responses; omitted entries remain in the source incident records and the page reports their count. Every timestamp and amount on a race page links to the saved raw response in `site/raw/`. The pages load two typefaces from Google Fonts and fall back to system fonts when offline.

## What is where

| Path | What it is |
|:---|:---|
| `paper/paper.md`, `site/paper.html` | The paper, as Markdown and as a rendered page |
| `site/` | The built site. `site/data/` holds the JSON the pages read, `site/downloads/` the downloadable tables, `site/raw/` the 1353 saved evidence files (excluding the manifest) that the site cites (`site/raw/MANIFEST.json` lists origin, hash and upstream URL for each) |
| `data/incidents.json`, `data/comparison_table.csv` | The master dataset: one row per race, with verdict, race type, attacker, bot, auction, loot, fate and source references, with unpublished full-cache sources explicitly marked |
| `data/headline_stats.json`, `data/harmonize_log.json`, `data/rawref_audit.json` | Aggregates, the log of verdict decisions, and the public-tree raw-reference audit (existing paths or explicit full-cache-only markers) |
| `data/extract/` | Per-incident facts that feed the master dataset |
| `data/evolution/` | The longitudinal study: `per_exploit_v2.json`, `by_era_v2.json`, `sender_class.json`, `findings_v2.txt`, and the v1 files it replaced |
| `incidents/<slug>/` | Per incident: `incident.json`, `timeline.json`, `summary.txt` and `race_<block>.json` (ordered transactions, relay bids, mempool first-seen) |
| `research/` | Chain scan of historic exploits, relay and mempool tooling notes, selected Yoink transaction evidence (`bot-re/`), anonymous-sender profiles, the 0xa57 and Yoink lineages, DeFi Plaza and Ronin replays, candidate lists, bibliography |
| `scripts/` | Fetching (`lib/rawfetch.py`, `relays.py`, `mempool.py`), reconstruction (`blockrace.py`), scanning (`scan_copycats.py`, `pooltouch.py`, `evolution.py`), dataset builders (`dataset/`), bot analysis tools (`bot_re/`) |

## Reproduce

Python 3.12 or newer. `pip install -r requirements.txt` installs duckdb (mempool lookups) and markdown (the paper page).

Runs from this repository, without the full cache:

```
python3 scripts/ci_check.py
python3 scripts/dataset/check_launch.py
python3 scripts/dataset/build_incidents.py --no-writeback  # read-only audit; writes no files
python3 scripts/export_paper.py                          # regenerates the paper page
```

Needs a full re-fetch (about 9 GB), including evolution intermediates:

```
export ETHERSCAN_API_KEY=...       # Etherscan fetches only
export BVH_RPC_URL=https://...     # an archive RPC
python3 scripts/blockrace.py BLOCK --slug SLUG --focus TXHASH
python3 scripts/dataset/check_extract.py
python3 scripts/dataset/build_incidents.py
python3 scripts/evolution.py relabel
python3 site/build_data.py
```

Every external response is fetched through `scripts/lib/rawfetch.py`, which saves the body under `data/raw/<source>/<key>` and logs the request in `data/raw/MANIFEST.jsonl`. The full cache is about 9 GB and is not published; `site/raw/` is the subset the site cites, so numbers displayed on the site link to their saved evidence. Some third-party pages use link stubs and policy reductions are documented in MANIFEST notes. Re-running a fetch recreates the cache. Relays and archives age out old data, so some early fetches may not repeat.

## Evidence levels

- `confirmed-onchain`: the same or adapted calldata from a different address, in the same or an earlier block, shown in traces; or, for a deploy-window copy, a replay of the attacker's deployed code that matches the bot's calls.
- `related-not-frontrun`: the bot acted on the same attack but after the attacker's transaction landed, or the evidence stops short of a copy.
- `rejected`: examined and ruled out, with the reason in the incident file.
- Mempool evidence: `measured` (first-seen time from the archive), `in-block-only` (before August 2023 no mempool archive exists, so only on-chain order is available), `absent-from-archive` (the transaction was private or missed).
- Unknown is recorded as unknown.

## Limitations

- Relays publish the value, size and builder of losing bids, never their transactions, so the auction shows who paid how much and when, not what the losing blocks contained.
- The mempool archive starts on 2023-08-07; earlier races rest on in-block evidence.
- The incident set is 29 incidents found through post-mortems, press and DeFiHackLabs. It describes the races that left a trace, and exploits that were front-run so well they vanished from the record are not in it.
- For c0ffeebabe.eth, the repository describes public actions only: which transaction, in which block, what it paid the builder and what was returned.
- Return figures come from on-chain transfers and public statements, and a return is voluntary; the paper separates gross, bot-net and victim-loss denominators.

## Sources and third-party data

Incident facts and context come from public sources cited per row and in the paper: post-mortems, rekt.news, DeFiHackLabs, block explorers, MEV-Boost relay data APIs, the Flashbots mempool-dumpster and blocks datasets, and the academic work listed in the paper's references. These belong to their owners. Files in `site/raw/` are unmodified except c0ffeebabe.eth trace reductions, third-party web pages replaced by link-only stubs, and contact/contributor redactions (see MANIFEST notes).

## Report a correction

Open an issue at https://github.com/DicksonWu654/bot-vs-hacker/issues. The most useful report names the incident (`slug` in `data/incidents.json`), says which field or sentence is wrong, and links a source that shows the right value. Accepted corrections are listed in `CHANGELOG.md`.

## Licence

- Code (`scripts/`, research and incident scripts, `site/*.html`, `site/assets/`, `site/build_data.py`) is MIT: see `LICENSE`.
- Data and text (`data/`, `incidents/`, `research/` documents, `paper/`, `site/data/`, `site/downloads/`) are CC BY 4.0: see `LICENSE-DATA`. Attribute as "The Bot Beat the Hacker".
- Third-party material is outside our licence grant: on-chain bytecode in `research/bot-re/code/`, saved third-party API responses and source extracts in `site/raw/`, and quoted messages keep their owners’ terms. DeFiHackLabs source extracts are attributed link stubs; we grant no rights in their UNLICENSED source.
