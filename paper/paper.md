# The Bot Beat the Hacker: Reconstructing On-Chain Races Between Generalized Front-Runners and Exploiters on Ethereum

*Data cut-off 2026-10-21. Incident counts and money flows come from [the incident dataset](https://github.com/DicksonWu654/bot-vs-hacker/blob/main/data/incidents.json) and [headline statistics](https://github.com/DicksonWu654/bot-vs-hacker/blob/main/data/headline_stats.json). The longitudinal measurements use the sender-corrected files in `data/evolution/`.*

Compiled with a swarm of AI agents, so there will be mistakes; every number links its saved source; corrections welcome.

## Abstract

Generalized front-runners can copy a profitable exploit and land before the attacker. We reconstruct 43 races and sub-races across 29 incidents from public transactions, local-fork replays and block-builder auctions. The headline set has 19 rows across 15 incidents, including medium-strength inferences. The beaten party was the original attacker in 8 confirmed and 5 likely cases; 6 rows involved a later exploiter or unresolved loser. Excluding c0ffeebabe.eth rows gives 15 rows across 13 incidents. Our call-level comparison for that operator is withheld by policy; anyone can compare the public traces. Euler is excluded because the copier may have been the attacker using a second account.

Three findings matter for recovery. Builder payments can be large: the mature-PBS headline median was 97.8% of gross before refunds and 26.8% after refunds. In two of 11 mature-PBS headline rows (Blueberry and Makina), the builder side passed most of its payment to the victim. Makina's large payment brings this to 67.5% of all payments pooled; its return followed two days later, after a Safe Harbor bounty negotiation. In the other nine rows, no builder-side payment reached victims in the documented window. Across 14 priced headline rows, including three known-zero returns, 83.1% of gross reached victims (Section 7). Recent attacker transactions are rarely visible in the mempool archive, while constructor execution narrows the copying window. The historical sample is selective. Relay bids measure builder bid response to a public trigger; their contents and the bot's detection time remain unobservable.

## 1 Introduction

In 2020 Robinson and Konstantopoulos described Ethereum as a dark forest: a transaction that reveals a profitable opportunity is seen, copied and outbid before it lands [Robinson20]. Their own rescue attempt was swept by a bot that had copied it. Six years later the forest has private order flow, a builder market, relay auctions and bots that run on all of it. The question has changed. A hacker who sends an exploit through the public mempool is easy prey. Does one who sends it privately, or runs it inside a constructor, still lose races? And if the bot wins, who keeps the money?

We call a bot that wins such a race a *front-runner of the attack*, following BACKRUNNER [Shou24]. Existing evidence is of three kinds, none a set of reconstructed races. Counterfactual replay: STING synthesises counter-exploits and finds a general front-runner can handle 12 of 62 historic attacks [Zhang23]; APE finds 12 apparent whitehat transactions, 10 sent privately [Qin23]. Aggregate counts: BACKRUNNER reports bots intercepted 18 of 158 attack transactions in January 2023 to May 2024 and that 17 of 158 were visible in the public mempool [Shou24]. Practitioner write-ups, which are uneven and often name the bot's transaction as the attack [BlockSec23; Blockfence26]. Missing is the checkable object: for a specific incident, what the attacker did and when, what the bot copied, which block each landed in, what the builder auction looked like, and where the money went.

**Contributions.**

1. *A confirmed-on-chain incident set with per-incident auction reconstruction.* We examined 29 incidents (43 races and sub-races) against a written verdict rule; 15 incidents, 19 races, satisfy the headline test because a bot got there first. Curve contributes three headline rows and two rejected sub-races. For every post-Merge case we rebuilt winning and competing builder bids from relay data and, after August 2023, the attacker's first-seen time where the archive has it.
2. *A race-type taxonomy* separating a bot beating a pending hacker transaction from using the hacker's deployed setup, copying a whitehat, replaying a failed attempt, being the first exploiter, or copying late. Only two of the six are the headline category (19 of the 43 rows; Euler is excluded because the copier's independence is uncertain).
3. *A public reverse-engineering of a generalized front-runner's executor across contract generations* (Yoink, 2022 to 2025; we found no earlier one, but our literature sweep was partial, Section 8.2): a decoded calldata grammar, a bribe rule validated against on-chain payments, and a quantified builder refund round-trip. Section 8.3 defines the publication boundary for a second well-known operator.
4. *Longitudinal attacker-side evidence that the dark forest changed*: mempool exposure, constructor-only exploits, deploy-to-attack gap, gas competition and bribes, with attacker-side and bot-side measurements separated. The separation is itself a finding: sender filtering removes 34 of 315 rows from attacker measurements (Section 6.1).
5. *A dataset and tooling* with saved RPC, relay, mempool and explorer evidence for the site's timestamps and amounts. The published evidence subset is indexed by `site/raw/MANIFEST.json`; a reconstructor can fetch fresh sources to rebuild a race file from a block number.

**Scope.** These are documented wins selected from a much larger, partly invisible population of attacks. BACKRUNNER records 140 attack transactions that bots did not catch; successful interceptions can also erase the attack from the historical record. Our sample establishes individual outcomes. A bot's intent remains unknown: it may copy the same way whether the opportunity is a hack, a bug or a user's mistake.

## 2 Background

**Mempool and generalized front-running.** A pending transaction's calldata is readable by any node, which can execute it against the latest state and see who gains. A *generalized front-runner* automates this: simulate each pending transaction in a fork, find the account that gains, rewrite addresses so the gain lands in the bot's contract, and resubmit with higher priority [Robinson20; Qin22]. Qin et al. gave the first concrete algorithm and estimated 57,037 ETH of replayable profit over 32 months [Qin22]. Against caller checks, APE and EVScope show how a bot can synthesise or patch an adversarial contract [Qin23; Ma25]. If the attack is split into deployment and trigger, the bot must follow both [Zhang23].

**Gas auctions and bundles.** Before December 2020 ordering was won by public gas bidding [Daian19]. Flashbots Auction then let searchers send bundles privately to miners and pay by gas price or a conditional transfer to `block.coinbase`; losing bids are never published [FlashbotsAuction]. From then on a bot's position is mostly bought, and rivals' bids are invisible.

**PBS and MEV-Boost.** Since the Merge (block 15,537,394, slot 4,700,013) *builders* assemble blocks and bid, and *proposers* sign a header [EthereumOrgPoS]. Builders send bids to *relays*, which validate the block (optimistic relays defer validation) and forward the best header to the proposer, who signs before the relay releases the payload [FlashbotsRelay; Neuder23opt]. A slot lasts 12 s. Builders may cancel or replace bids, so the highest received bid is not always the delivered block [Neuder23cancel; FlashbotsWinningBid].

**Relay data APIs.** `builder_blocks_received` lists verified bids without payloads, and `proposer_payload_delivered` the block the proposer got [RelaySpecs]. A row has builder key, block hash, value, transaction count and a relay receive timestamp, never the transactions. Ultra Sound's bid adjustment can lower a delivered bid to the second-best plus one wei [UltraSoundDocs]. We always join the two endpoints and state which relays answered.

**Private order flow.** A transaction sent straight to a builder, bundle service or protected RPC never enters the public mempool. Private flow is a large share of MEV [Weintraub22; Lyu22]. Whitehats use it (10 of 12 in APE [Qin23]), and so do attackers and bots.

## 3 Data and methods

### 3.1 Sources

| Source | Used for | Limits |
|---|---|---|
| DeFiHackLabs (365 mainnet PoCs of 912) | Exploit universe; named "attack tx" | Only exploits someone reproduced; often lists the bot's tx |
| Archive-node traces via `eth.drpc.org` (callTracer, `eth_getBlockReceipts`) | Call trees, positions, coinbase transfers | Rate limits; all responses saved |
| Etherscan v2 API | Transaction lists, labels, token transfers | 10,000-row cap; labels unverified |
| Relay data APIs (Flashbots, Ultra Sound, Agnostic, bloXroute, Aestus, Titan, others) | Bid timeline, winner, proposer payment | Section 3.3 |
| Flashbots mempool-dumpster [Dumpster] | First-seen of public transactions | From 2023-08-07; source drift |
| Postmortems, press, on-chain messages | Context, returns, bounties | `reported` unless re-derived |

Research fetches use `scripts/lib/rawfetch.py`, which writes to the full-cache path `data/raw/<source>/` and logs retrievals in `data/raw/MANIFEST.jsonl`. The full cache is not published. The public export carries a cited subset under `site/raw/`, indexed by `site/raw/MANIFEST.json`. That subset includes reduced block records for c0ffeebabe.eth and link stubs for some third-party web pages; the manifest notes describe these transformations. Dataset references may also identify evidence available only in the full cache.

### 3.2 Evidence levels

**Confirmed on chain**: shown in saved traces or relay responses, with the transaction hash. **Inferred**: follows from confirmed facts under a stated assumption (for example, that a builder and a bot are one operator because the builder refunds the bot in the same block). **Reported**: stated by a postmortem, news item or on-chain message, not re-derived. **Unknown**: not observable with our data; absence from the mempool archive leaves the submission route unknown. For pre-August-2023 incidents there is no mempool archive; we write "in-block evidence only" and never infer a first-seen time.

### 3.3 Limits of the data

- **Relay retention.** Only the Flashbots relay serves bid history for old slots (verified to 2023-07-30). Ultra Sound keeps bids about 30 to 90 days, Agnostic about 90, others 90 to 365. For every 2023 incident only Flashbots bids exist, and the delivering relay may answer an empty list (`relays.py retention`; [Relay analysis]).
- **Bids never reveal contents.** We know builder B bid V at time T, not whether the block held the bot's transaction unless it was the delivered hash. Timestamps are relay receive times and differ between relays.
- **Flashbots blocks API is dead** (HTTP 410). Pre-Merge bundle membership is inferred (coinbase payment above zero with priority fee under 1 gwei) and labelled so.
- **Mempool-dumpster.** Coverage starts 2023-08-07; the per-source log exists only 2023-08-31 to 2025-07-14. Transactions already on chain when first received are dropped, private ones never appear, and the number of sources fell from about seven to three or four, taking the share of ordinary same-block transactions seen from about 86.0% to about 50.0%. We therefore never use an absolute "public share" without a same-block control.
- **Builder bid response.** We time the interval from the trigger's first pre-inclusion archive sighting to the winning builder's first qualifying bid step-up: at least twice its own earlier best and at least 0.5 ETH. The trigger can be an attack, deployment or user withdrawal. Five rows are measurable, three in the headline set. The bot's detection time and the contents of earlier bids remain unknown.
- **Survivorship and first-seen.** DeFiHackLabs holds only exploits someone reproduced, and yearly counts partly track its coverage. "First seen" is the archive's observation, not the bot's.

### 3.4 Verdict rule and taxonomy

An incident is **confirmed on chain** when we identify the attacker and a separate bot, establish that the bot replayed or adapted the attack or used the attacker's on-chain setup, and establish the ordering from saved transaction and block evidence. The comparison uses calldata, call trees or local-fork replay where published. A *deploy-window copy* uses a deployed contract, upgrade or preparation step before the attacker's own finishing call. For c0ffeebabe.eth, our call-level comparison is withheld by policy; anyone can compare the public traces. We publish transaction and outcome facts under Section 8.3. Other verdicts are `related-not-frontrun`, `reported` or `rejected`, with a reason.

| Type | Meaning | Rows | Examples |
|---|---|---|---|
| `beat-pending-attack` | Bot landed before a pending attacker transaction, replaying or adapting it | 15 | Blueberry, DeFi Plaza, Alkimiya, Unizen |
| `deploy-window-copy` | Bot used the attacker's deployed setup before the finishing call | 5 | Makina, Kelp, BiFi, Euler, Neemo |
| `beat-whitehat-or-user` | Bot copied a non-hacker transaction | 4 | Ronin (three rows), Sushi RouteProcessor2 |
| `post-failure-replay` | Attacker's transaction had failed or landed; bot or whitehat replays | 7 | Secured Finance, Saddle, Balancer, TaoPad, Peapods, Alkemi |
| `bot-was-first-exploiter` | No separate attacker; the bot found the bug | 5 | TIME, Paraswap, MintSwap, Meta Pool, Peapods |
| `late-copy` | Copies after the attacker succeeded | 4 | UNCX, Conic, Unizen, Alkemi |
| `no-race` | Rejected sub-race: one actor, nothing replays it | 3 | Curve alETH, Curve CRV/ETH phase 1, Peapods follow-up |

The **headline count** requires a confirmed on-chain copy in either `beat-pending-attack` or `deploy-window-copy`, with a separate operator sufficiently established: 19 rows in 15 incidents, split into 15 pending-attack and four deploy-window rows. The attribution check classifies 8 rows as original-attacker-confirmed and 5 as likely-attacker, so 13 rows involve the initiating attacker; 6 involve a later exploiter or an unresolved loser. Euler's code copy remains `confirmed-onchain` in the dataset, but its unresolved operator identity excludes it from the headline. Across all 43 rows the verdicts remain 24 confirmed on chain, 16 related-not-frontrun and three rejected; the decisions are logged in `data/harmonize_log.json`.

#### 3.4.1 Attribution of the beaten party

The headline test establishes that a bot arrived before a prepared exploit transaction or setup. It does not by itself establish that the beaten party was the original incident attacker. We checked the beaten account's preparation history, deployment lineage, incident attribution and saved transaction evidence. The result is 8 original-attacker-confirmed rows, 5 likely-attacker rows, and 6 rows involving a later exploiter or unresolved loser.

The six later or unresolved rows are Curve/Vyper msETH, Curve/Vyper CRV/ETH wave 2, DeFi Plaza, Unizen pending ADS, Unizen pending USDT and Unizen pending XI. The last row is a known follow-on exploiter, and its pending status is unresolved. The other five are the audit's could-be-another-bot cases. These labels describe attribution of the loser and do not change the copy or ordering verdicts.

Excluding the four c0ffeebabe.eth rows whose call-level comparison is withheld leaves 15 rows in 13 incidents (`sensitivity.excluding_c0ffeebabe_rows`). Eight headline rows have medium-strength evidence (Table 1). In particular, Neemo has no thief drain transaction, and Unizen's pending-XI status is inferred from nonce order and calldata identity. Excluding just these two rows leaves 17 rows in 14 incidents; excluding all eight medium-strength rows leaves 11 rows in 11 incidents. These are different sensitivity cuts. DODO's several races contribute one dataset row, the first race (Section 4.1).

### 3.5 DeFiHackLabs records the bot's transaction

Trusting DeFiHackLabs's attack-transaction label would analyse the wrong party. Of 376 post-London attack transactions, 37 are bundle-style (priority fee zero plus a direct coinbase payment), and in 15 of those 37 the sender is one of the two bots the chain scan matched by address, c0ffeebabe.eth and Yoink [Chain scan]. That is a floor: two of the three searcher profiles in Section 4.4 cover up to seven more listed rows (three and four), which we classed as bot-run exploits rather than races. The address `0xc0ffeebabe5d…` is the listed exploit sender in 9 mainnet entries and `0xfde0d157…` (Yoink) in 6. Alkimiya's header names the real attacker but lists Yoink's `0x9b9a6dd0` as the attack; Paraswap's reported "$24K" loss (secondhand, from a post-mortem we could not retrieve) matches one Yoink transaction (`0x35a73969`, 6.46 ETH); TIME's reported attacker gain of 84.6 ETH equals Yoink's net after its bribe (`0xecdd111a`). The sender classification behind Section 6 finds the same problem at larger scale. Sender filtering removes 34 of 315 rows (28 bot-only, one whitehat and five unknown-sender or non-attack rows); 35 first-listed transactions were not sent by attackers, including one retained mixed row. For c0ffeebabe.eth entries we record only the public transaction facts defined in Section 8.3.

## 4 Incidents

Conventions: block positions are zero-indexed ("idx 0" is the first transaction). `t_rel` is a relay timestamp minus slot start. Transactions are cited by their first 8 hex digits; Appendix A maps them to full hashes and Appendix B lists public sources per incident ([S:name]). Times are UTC. "In-block only" means no mempool archive exists for the date. Money flows are collected in Section 7.1. Display amounts normally use two decimals for ETH and one for percentages; exact arithmetic, small fees and quoted settlement amounts retain the precision needed to check them. Rounded amounts may not sum exactly.

**Table 1. All 43 rows of `data/incidents.json` (29 incidents), by date.**

| # | Date | Incident (sub-race) | Race type | Headline | Verdict | Bot | Block lead | Ordering | Mempool evidence | Strength |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2021-03-08 | DODO V2 | `beat-pending-attack` | yes | confirmed-onchain | Antelope | 0 | same-block-earlier-index | in-block-only | high |
| 2 | 2021-08-10 | Punk Protocol | `beat-pending-attack` | yes | confirmed-onchain | anonymous white-hat bot | 0 | same-block-earlier-index | in-block-only | high |
| 3 | 2022-04-30 | Saddle | `post-failure-replay` | no | related-not-frontrun | BlockSec (whitehat) | -2 | later-block | in-block-only | high |
| 4 | 2022-10-01 | Transit Swap | `beat-pending-attack` | yes | confirmed-onchain | Yoink | 0 | same-block-earlier-index | in-block-only | high |
| 5 | 2022-10-14 | Earning.Farm | `beat-pending-attack` | yes | confirmed-onchain | 0xa57 bot | 0 | same-block-earlier-index | in-block-only | high |
| 6 | 2023-01-19 | SHOCO | `beat-pending-attack` | yes | confirmed-onchain | anon searcher | 0 | same-block-earlier-index | in-block-only | medium |
| 7 | 2023-03-13 | Euler copy bot | `deploy-window-copy` | no | confirmed-onchain | anon searcher | 17 | earlier-block | in-block-only | medium |
| 8 | 2023-04-09 | Sushi RouteProcessor2 | `beat-whitehat-or-user` | no | confirmed-onchain | Yoink | 1 | earlier-block | in-block-only | high |
| 9 | 2023-07-21 | Conic Finance (eth-pool) | `post-failure-replay` | no | related-not-frontrun | anon clone exploiter | -54 | later-block | in-block-only | high |
| 10 | 2023-07-21 | Conic Finance (crvusd-pool) | `late-copy` | no | related-not-frontrun | Yoink | -1 | later-block | in-block-only | high |
| 11 | 2023-07-30 | Curve/Vyper (pETH) | `beat-pending-attack` | yes | confirmed-onchain | anon pETH front-runner | 0 | same-block-earlier-index | in-block-only | high |
| 12 | 2023-07-30 | Curve/Vyper (msETH) | `beat-pending-attack` | yes | confirmed-onchain | c0ffeebabe.eth | 2 | earlier-block | in-block-only | medium |
| 13 | 2023-07-30 | Curve/Vyper (alETH) | `no-race` | no | rejected | none | n/a | n/a | in-block-only | n/a |
| 14 | 2023-07-30 | Curve/Vyper (CRV-ETH-wave1) | `no-race` | no | rejected | none | n/a | n/a | in-block-only | n/a |
| 15 | 2023-07-30 | Curve/Vyper (CRV-ETH-wave2) | `beat-pending-attack` | yes | confirmed-onchain | c0ffeebabe.eth | 3 | earlier-block | in-block-only | medium |
| 16 | 2023-12-06 | TIME | `bot-was-first-exploiter` | no | related-not-frontrun | Yoink | n/a | n/a | absent-from-archive | n/a |
| 17 | 2024-02-14 | TaoPad | `post-failure-replay` | no | related-not-frontrun | Yoink | -21 | later-block | measured | high |
| 18 | 2024-02-23 | Blueberry | `beat-pending-attack` | yes | confirmed-onchain | c0ffeebabe.eth | 1 | earlier-block | measured | high |
| 19 | 2024-03-08 | Unizen (pending-usdt) | `beat-pending-attack` | yes | confirmed-onchain | Yoink | 1 | earlier-block | measured | medium |
| 20 | 2024-03-08 | Unizen (half-copies) | `late-copy` | no | related-not-frontrun | Yoink | -1 | later-block | absent-from-archive | high |
| 21 | 2024-03-08 | Unizen (pending-xi) | `beat-pending-attack` | yes | confirmed-onchain | Yoink | 2 | earlier-block | absent-from-archive | medium |
| 22 | 2024-03-08 | Unizen (pending-ads) | `beat-pending-attack` | yes | confirmed-onchain | Yoink | 1 | earlier-block | measured | high |
| 23 | 2024-03-19 | Paraswap Augustus V6 | `bot-was-first-exploiter` | no | related-not-frontrun | Yoink | n/a | n/a | absent-from-archive | n/a |
| 24 | 2024-04-01 | MintSwap | `bot-was-first-exploiter` | no | related-not-frontrun | Yoink | n/a | n/a | measured | n/a |
| 25 | 2024-07-05 | DeFi Plaza | `beat-pending-attack` | yes | confirmed-onchain | Yoink | 1 | earlier-block | measured | high |
| 26 | 2024-08-06 | Ronin bridge (eth-leg) | `beat-whitehat-or-user` | no | confirmed-onchain | ETH-leg searcher | 209 | earlier-block | measured | high |
| 27 | 2024-08-06 | Ronin bridge (racer3) | `beat-whitehat-or-user` | no | confirmed-onchain | racer 3 | 0 | same-block-earlier-index | measured | high |
| 28 | 2024-08-06 | Ronin bridge (yoink-usdc) | `beat-whitehat-or-user` | no | confirmed-onchain | Yoink | 1 | earlier-block | measured | high |
| 29 | 2025-03-28 | Alkimiya SilicaPools | `beat-pending-attack` | yes | confirmed-onchain | Yoink | 1 | earlier-block | absent-from-archive | high |
| 30 | 2025-06-17 | Meta Pool | `bot-was-first-exploiter` | no | related-not-frontrun | Yoink | n/a | bot-first-exploiter (first attacker tx landed 249 block(s) later; nothing pending, not a race) | absent-from-archive | high |
| 31 | 2025-07-05 | Neemo Finance | `deploy-window-copy` | yes | confirmed-onchain | anon bot 0xb750 | n/a | before-attacker-call-landed (never landed; bot 1 block(s) after upgrade) | absent-from-archive | medium |
| 32 | 2025-07-08 | Peapods Finance (second-attempt) | `post-failure-replay` | no | related-not-frontrun | Yoink | -1 | later-block | absent-from-archive | high |
| 33 | 2025-07-09 | Peapods Finance (07-09-followup) | `no-race` | no | rejected | Yoink | n/a | n/a | absent-from-archive | high |
| 34 | 2025-10-09 | Peapods Finance (oct-leftover) | `bot-was-first-exploiter` | no | related-not-frontrun | Yoink | n/a | n/a | absent-from-archive | medium |
| 35 | 2025-11-03 | Balancer v2 | `post-failure-replay` | no | related-not-frontrun | Bitfinding (whitehat) | -1 | later-block | absent-from-archive | high |
| 36 | 2026-01-20 | Makina DUSD/USDC | `deploy-window-copy` | yes | confirmed-onchain | anon searcher | n/a | before-attacker-call-landed (never landed; bot 1 block(s) after deploy) | absent-from-archive | high |
| 37 | 2026-03-10 | Alkemi Earn (Ethereum) (eth-vault-copiers) | `late-copy` | no | related-not-frontrun | anon searcher | -76 | later-block | absent-from-archive | high |
| 38 | 2026-03-10 | Alkemi Earn (Ethereum) (wbtc-yoink) | `post-failure-replay` | no | related-not-frontrun | Yoink | -1 | later-block | absent-from-archive | medium |
| 39 | 2026-09-05 | Secured Finance | `post-failure-replay` | no | related-not-frontrun | c0ffeebabe.eth | -4 | later-block | measured | medium |
| 40 | 2026-09-15 | Kelp-related rsETH Safe | `deploy-window-copy` | yes | confirmed-onchain | Yoink | n/a | before-attacker-call-landed (never landed; bot 1 block(s) after prepare) | absent-from-archive | medium |
| 41 | 2026-10-14 | UNCX Vesting V2 (yoink-X) | `beat-pending-attack` | yes | confirmed-onchain | Yoink | 1 | earlier-block | absent-from-archive | high |
| 42 | 2026-10-14 | UNCX Vesting V2 (zc-copiers) | `late-copy` | no | related-not-frontrun | c0ffeebabe.eth | -250 | later-block | absent-from-archive | medium |
| 43 | 2026-10-17 | BiFi idle USDT market | `deploy-window-copy` | yes | confirmed-onchain | c0ffeebabe.eth | n/a | before-attacker-call-landed (never landed; bot 1 block(s) after deploy) | absent-from-archive | medium |

*Block lead* is the racing transaction's block minus the bot's block (`blocks_ahead` in the dataset): positive means the bot landed earlier, 0 the same block (the *ordering* column says whether by index), negative later. The racing transaction is the attacker's, except for Sushi (the whitehat's) and Ronin (the copied user's withdrawal, which for the ETH leg finally landed 209 blocks after the copy). It is n/a where the attacker's finishing call never landed (Makina, Kelp, BiFi, Neemo), where the bot was first to use the bug, or where there was no race. For Euler the lead of 17 is to the attacker's first call into its own contract; the copier landed three blocks after the attacker's deployment. *Mempool evidence*: `in-block-only` means the date precedes the archive (2023-08-07); `absent-from-archive` that the archive covers the day but holds neither the attacker's nor the bot's transaction (submission route unknown); `measured` that it holds the trigger transaction with first-seen times. *Strength* is the dataset's `evidence_strength`. The headline has 19 rows in 15 incidents, or 15 rows in 13 incidents excluding c0ffeebabe.eth. The attribution split is 8 confirmed original attackers, 5 likely original attackers and 6 later or unresolved losers. Among the 19 headline rows, the bot landed in the same block ahead of the attacker in six, an earlier block in nine, and before an attacker call that never landed in four. Eight headline rows have medium-strength evidence.

### 4.1 Headline races

**DODO V2, 2021-03-08 (`beat-pending-attack`; races at blocks 12000022, 12000102 and 12000167/12000171; in-block only).** [S:dodo] The attacker abused DODO V2's re-callable `init()`: stage fake tokens in a pool, flash-loan, re-initialise with the fake pair. He staged at block 12000020 (`0xfbf6d830`); his attack `0x4bc4ace3` (132 gwei, idx 176) in 12000022 reverted because the bot "Antelope" (EOA `0x35541875`) had landed a flash loan plus `init()` at idx 4 at 243 gwei and emptied the pool (955,815 WSZO, 259,939 USDT). The `init()` calldata is byte-identical to the attacker's, fake tokens included (confirmed). It repeated at 12000102 (bot idx 0 at 1,883 gwei; attacker `0x0430d5a2` at 600, reverted). When the attacker built a one-transaction stage-and-attack contract (`0x395675b5`, block 12000165, idx 3, 300 gwei), which succeeded, a second bot, "Cheetah" (EOA `0x8a14ce0f` via proxy `0xa57bd001`), took the proceeds by calling its `withdraw` with byte-identical calldata: at idx 1 of 12000167 (`0x75d4765d`, 684 gwei), ahead of the attacker's own call (idx 77, 142 gwei) and of Antelope (idx 4, 652 gwei, out of gas), and again at idx 3 of 12000171 (`0xa8d03049`, 559 gwei against the attacker's 152); Cheetah's takes were 1,139,456 USDT and 133,549 wCRES. The dataset counts DODO as one headline row, the first race (block 12000022); the other races are narrative. Antelope returned most of its takes on 2021-03-10 (all of the WSZO, 296,009 USDT, 101,548 ETHA, 1,000 wCRES and 114.5 ETH; its USDT takes in the two races were larger and the difference is not reconciled); Cheetah's USDT take went back too: the exact 1,139,456.204396 USDT moved from the operator's capital wallet (`0x56178a0d`) through a sibling proxy (`0xfa103c21`) to DODO's pool (`0x95c4f5b8`) in `0x6e743db0` (block 12004002, 2021-03-09 11:18 UTC), 14.3 h after the take (confirmed on chain). The reported total of about $1.89M (USDT plus 411 ETH, per The Block) is only partly located: we did not find the 411 ETH or the 133,549 wCRES on chain.

**[Punk Protocol](https://github.com/DicksonWu654/bot-vs-hacker/blob/main/incidents/punk-2021/incident.json), 2021-08-10 (`beat-pending-attack`).** A white-hat bot landed at idx 50, ahead of the attacker's idx 52 in block 12995895. The copied transaction drained about $8.95M: $5.95M in USDT and DAI reached the bot, while about $3.0M USDC was mis-sent to the attacker. The bot returned $4.95M and kept the agreed $1M bounty. Recovery is partial against the transaction's gross take because the USDC leg stayed with the attacker. In-block evidence only.

**Transit Swap (Ethereum leg), 2022-10-01 (`beat-pending-attack`; in-block only).** [S:transit] The attacker (EOA `0x5f0b31aa`) drained approvals through Transit's router in nine transactions (blocks 15655118 to 15655281). In the last block his `0x6f7d546a` (idx 43, tip 3.0 gwei) reverted. Yoink's `0x9f43b61d`, from its pre-gen1 contract (`0x6c6b87d4`, created 2022-09-07), sits at idx 24 with a 3.000000002 gwei tip: the same 21 router calls on the same 21 victims with only the recipient changed, 5,974.5 UNI swapped to 29.31 WETH. Two wei of tip put it ahead of the whole 3.0 gwei tier (confirmed). The block was not built through MEV-Boost. Transit wrote to Yoink on chain in October 2022. On 2022-10-23 Yoink answered (`0x57a98ef2`): "Sorry, just saw your message. My bot frontran the real attacker. How about I return 90% of the profits (26.505 Eth) and keep 10% as a bounty?". Transit's on-chain acceptance is dated 2023-05-22 (`0x3edd298a`), seven months later, and Yoink paid exactly 26.505 ETH on 2023-09-06 (`0x074acda8`), three and a half months after the acceptance and ten and a half months after the offer.

**Earning.Farm, 2022-10-14 (`beat-pending-attack`; in-block only).** [S:earningfarm] The attacker's `0x4be393b9` (block 15746200, idx 7, 27.9 gwei priority fee) reverted. At idx 0 a bot of the "0xa57" family (EOA `0x26bce6ec`) landed `0x1f1aba5b` with zero priority fee and an 18.72 ETH transfer to the builder; its vault deposit and both Balancer flash-loan calldatas (1,000 ETH) are byte-identical to the attacker's, and it withdrew 480.1 ETH (confirmed). A local-fork replay of the reverted transaction on the pre-bot state pays 480.11 ETH to the attacker's helper; on the post-bot state it reverts. The failed transaction used 2,111,774 of its 5,000,000 gas limit and reverted inside the flash-loan callback. MevRefund's thread links the bot's `0x1f1aba5b` as the attacker's first transaction; the real first attempt is `0x4be393b9`. The attacker retried (`0x160c5950`, block 15746342) and got 268.9 ETH. Flashbots saw 246 bids from 23 builders; the best was about 0.13 ETH until a first bid of 18.8 ETH at t_rel -2.1 s (we infer from its size that it carried the bot's transaction; bid contents are not visible); `builder0x69` won at 18.83 ETH, and the bot's coinbase payment was 99.4% of that bid. The 480.1 ETH went to the owner's capital wallet; we found no return.

**SHOCO, 2023-01-19 (`beat-pending-attack`; in-block only).** [S:shoco] The attacker (EOA `0x14d8ada7`, contract `0x15d684b4` created four minutes earlier) sent swap, `deliver`, `skim` with a Balancer flash loan at block 16440979, idx 15; it reverted (`0x2f2c3c1c`). A generic searcher (EOA `0xe71aca93`) at idx 0 (`0x2e832f04`) ran the same victim calls with its own 1.47 ETH (19 `deliver` calls, 12 `skim` rounds) and took 4.16 ETH gross. A local-fork replay shows the attacker's transaction alone matches the unrounded gross take to the wei; bot-first reproduces the revert (confirmed). The calldata is adapted, not copied, and whether the bot saw the attacker's pending transaction or derived the same calls from the attack contract deployed four minutes earlier cannot be told from our data. The bot's effective gas price (15.61 gwei) was below the attacker's (16.61); ordering came from a 0.09 ETH coinbase payment, 69.4% of the 0.13 ETH winning bid, or 70.8% with the 0.0018 ETH tip (540 Flashbots bids from 45 builders; 12 higher bids too late). The bot kept the funds.

**Curve/Vyper, 2023-07-30 (three `beat-pending-attack` sub-races; in-block only).** [S:curve] A Vyper compiler bug broke reentrancy locks in four pools. Of five sub-races examined, three are confirmed and two rejected (alETH `0xb676d789`, CRV/ETH phase 1 `0x2e7dc8b2`).
- *pETH (block 17806056).* The real attacker (Tornado-funded `0x172f6fde`) deployed at idx 90 (`0xb2dfea6d`) and attacked at idx 91 (`0xb5d91f1e`, reverted). A different address, `0x6ec21d18`, was at idx 0 (`0xa84aa065`) and took 6,106.65 WETH for 0.03 ETH of priority fee (6,106.75 WETH later left its contract, and the 90.0% below is computed on that figure). Its in-transaction `CREATE` initcode matches the attacker's except 20 bytes. Five days later (2023-08-04) 5,495.4 WETH (90.0%) reached JPEG'd's multisig through an intermediary address (the second of two transfers is `0x003b0037`), and the rest was kept as a bounty (JPEG'd's on-chain statement awards 610.6 WETH; the on-chain remainder is 611.35 WETH) (confirmed). No relay reports delivering the block, so the 807 Flashbots bids (up to 333.66 ETH) cannot be tied to it.
- *msETH (17806550).* The raced party, `0x19c7849d`, was a second exploiter adapting the public pETH exploit. c0ffeebabe.eth's transaction `0xc93eb238` was first in the block (idx 0), ahead of second exploiter `0x19c7849d`'s deployment `0x95827369` at idx 10; that second exploiter's call `0xe2eb61b1` followed in block 17806552 at idx 3. It took 866.73 ETH gross and paid 0.17 ETH to the block producer, leaving 866.55 ETH before gas. LlamaRisk also reported a holding of about 960 msETH from this pool; that token holding is outside the ETH-only amount above and has not been independently reconciled here. Contemporary press described the later 1,000 ETH transfer as a cold-wallet move; the victim-return status remains unknown (Section 7.3). A pending deploy/attack sequence or adaptation of the earlier pETH exploit could explain pre-emption before this attacker contract existed. Pending status is inferred from in-block evidence only. Our call-level comparison is withheld by policy; anyone can compare the public traces.
- *CRV/ETH phase 2 (17808683).* The raced party was again the pETH adapter `0x19c7849d`. Both this row and msETH are excluded by the c0ffeebabe.eth sensitivity cut (15 rows / 13 incidents). c0ffeebabe.eth's transaction `0xcd99fadd` was at idx 7, before second exploiter `0x19c7849d`'s deployment `0xccdc1855` at idx 13; that second exploiter's call `0x3079ebb0` followed in block 17808686 at idx 6. It received 2,879.66 ETH and returned 2,879.54 ETH to the Curve deployer (`0xb7675412`, after a 0.1 ETH test transfer), who wrote on chain that one transaction had front-run a CRV/ETH pool hack. As in msETH, a pending deploy/attack sequence or adaptation of the earlier exploit could explain the ordering; pending status is inferred from in-block evidence only. Our call-level comparison is withheld by policy; anyone can compare the public traces.

**Blueberry, 2024-02-23 (`beat-pending-attack`; measured).** [S:blueberry] The public trigger and winning-builder response are both timed here. The attacker (EOA `0x0512ac94`) deployed `0x70b96d02` (`0x8e7b711e`, first seen 02:16:22.769, mined 02:18:11) and broadcast `0xb6748899` publicly, first seen 02:22:09.219 (Chainbound), 1.78 s before slot 8485909, at 0.034 gwei. c0ffeebabe.eth's `0xf0464b01` took idx 0 of block 19287289 at 02:22:11, one block earlier. The attacker's transaction landed in 19287290 (idx 218), succeeded, and received nothing. The transaction took the whole market cash, 8,616 OHM, 913,263 USDC and 6.87 WBTC, valued at 457.68 WETH, equal to the postmortem's reported transaction profit. The winning builder’s first qualifying step-up followed the public trigger by 266 ms. Auction (Flashbots, 108 bids): baseline 0.11 ETH, then 10.1 ETH at t_rel -1736 ms (the bidder was "I can haz block?", not the winning builder), 22.99, 71.7, 81.7, and the winner "Ty For The Block" at 91.04 ETH at -587 ms, a three-transaction block. The bot paid 457.55 ETH to the coinbase; the builder sent 366.51 ETH (80.1%) to the protocol's multisig and 91.04 ETH (19.9%) to the proposer. Our call-level comparison is withheld by policy; anyone can compare the public traces.

**[Unizen](https://github.com/DicksonWu654/bot-vs-hacker/blob/main/incidents/unizen-2024/incident.json), 2024-03-08.** Three headline rows are confirmed: pending ADS (7,800 ADS, block 19393726 idx 0, one block ahead), pending USDT (13,565.685175 USDT, block 19393223 idx 0, one block ahead) and pending XI (1,118,715.169744549 XI, block 19393298 idx 0, two blocks ahead). Pending ADS is high-strength; USDT and XI are medium-strength. XI pending status is inferred from nonce order and calldata identity, without a mempool record. Four half-balance copies landed one to two blocks after the attacker and are late copies. The incident-wide ETH return was 0.30 ETH in successful transaction `0x4f647c4d`; the earlier attempt reverted and moved no funds. The shared return is not allocated among the four rows.

**DeFi Plaza, 2024-07-05 (`beat-pending-attack`; measured).** [S:defiplaza] The attacker (EOA `0x14b362d2`, Tornado-funded) broadcast a deployment (`0x8f029510`) and `run()` (`0xe00b0998`) at 13:15:29.185, seen by all four archive sources, 5.8 s before slot 9446776. Yoink's builder ("I can haz block?") put its first bid on the Flashbots relay 3.013 s later (6.98 ETH), climbed 18.60, 62.48, 62.54 ETH and won. Block 20240539 has Yoink's `0xa245deda` at idx 0 and the attacker's deploy at idx 3; `run()` landed in 20240540 at idx 27 and reverted. On a local fork of 20240538 the attacker's deploy and `run()` drain the pool (4.55 ETH and 15 tokens, about $217K); its 25 state-changing calls match Yoink's byte for byte (selectors, calldata, ETH values), only `msg.sender` differs (confirmed). Yoink paid a fixed 66.32 ETH; its builder passed 62.54 ETH to the Lido execution-layer rewards vault, beating the best rival bid (62.4928) by 0.05 ETH, and refunded 4.76 ETH. No ETH return is visible. After DeFi Plaza's on-chain message (19:00:23) Yoink's vault returned tokens worth about $23K (about 7.7 ETH) within 47 minutes, which is 98.7% of Yoink's estimated net of 7.78 ETH after the 66.3 ETH payment and 4.76 ETH refund, though only 10.5% of the pool's 73.4 ETH loss (gross); the Lido RFC says the front-runner "promptly returned their profits" [Lido24].

**Alkimiya SilicaPools, 2025-03-28 (`beat-pending-attack`; attacker absent from archive).** [S:alkimiya] The attacker (EOA `0xf6ffba5c`) iterated through four contract designs over 52 minutes and deployed the attack contract `0x69af47f3` at block 22146335. Its attack `0xc8875004` (Morpho 10 WBTC flash loan, a uint128 cast bug in `collateralizedMint`, `redeemShort`) landed in 22146341 and reverted; the pool had been emptied a block earlier. Yoink's `0x9b9a6dd0` at idx 0 of 22146340 is a Morpho flash loan with an eight-call script whose seven SilicaPools and index calls match the attacker's call tree call for call; only the caller address and timestamp words differ, and it reuses the attacker's own index contract. A `debug_traceCall` of the attacker's transaction on the 22146339 state yields exactly +114,015,390 sat of WBTC, what Yoink took and swapped for 50.89 ETH (confirmed). Yoink's builder escalated 0.54 to 2.58 ETH in 70 ms (t_rel -1114 to -1048) and won at -891 ms; Yoink paid 50.83 ETH (999 per mille) and was refunded 48.28 ETH. The attacker got nothing; how Yoink learned of the attack is unknown. DeFiHackLabs lists Yoink's transaction as the attack.

**[Neemo](https://github.com/DicksonWu654/bot-vs-hacker/blob/main/incidents/neemo-2025/incident.json), 2025-07-05 (`deploy-window-copy`, medium-strength).** A bot used the open drain function planted by a key-compromise upgrade one block (12 s) after the upgrade, taking 114.53 ETH-equivalent of weETH and returning 91.63 ETH nine days later. The thief never sent a drain transaction. This counts as use of the thief's on-chain setup; there is no thief drain transaction to demonstrate pre-emption.

**Makina DUSD/USDC, 2026-01-20 (`deploy-window-copy`).** [S:makina] The attacker (EOA `0x2f934b0f`, Tornado-funded) deployed a `tx.origin` guard, then the attack contract `0x2c19b916` in block 24273361 idx 86 (`0xad945d38`, 03:40:23). Twelve seconds later, at idx 0 of 24273362, an EIP-7702 searcher account (`0x935bfb49`) ran `0x569733b8`: the same 280M USDC of flash loans (Morpho plus Aave), two rounds of accounting manipulation with DUSD/USDC pool trades, 1,299.05 ETH to the coinbase, 0.13 ETH kept. The attacker's nonce stayed at 2; no call was ever mined. With no attacker calldata on chain, the proof is a code match: 77.0% of the bot's non-zero calldata bytes appear verbatim in the attacker's runtime, and replaying the attacker's `F1()` on a fork gives a protocol call sequence 98.6% identical (confirmed under the deploy-window rule). Builder "0x75" (no public label) won at 276.32 ETH (+974 ms, via Ultra Sound) and forwarded 1,023.0 ETH to `0xbed`, which returned 920.7 ETH to Makina's Safe on 2026-01-22 and kept 102.3 ETH, a 10.0% bounty, after on-chain Safe Harbor messages [Rekt26].

**Kelp-related rsETH Safe, 2026-09-15 (`deploy-window-copy`).** [S:kelp] The victim is a Gnosis Safe (`0x40e93a52`) with a leveraged rsETH position on Aave, not Kelp's protocol. The attacker (EOA `0x0dc2c5d6`, Railgun-funded) deployed an executor `0x10605ee4` (block 25980523) and called `prepare()` (`0x0a7d69ab`, block 25980524, idx 207). Neither transaction appears in the mempool archive. Twelve seconds later Yoink's `0x0e7680b0` took idx 0 of 25980525, called the executor's permissionless function (2,900e18), pulled 2,900 aEthrsETH from the Safe, sold 17.63 rsETH for 18.95 ETH, of which 18.93 ETH went to the coinbase, and swept 2,882.37 rsETH to its vault. It copied no calldata: a read-only `eth_call` shows the function reverts "not prepared" after block 523 and succeeds after block 524, so Yoink needed the attacker's `prepare()` (confirmed). Use of the prepared state is established; pre-emption of an intended finishing transaction is inferred because no such transaction landed and none appears in the archive. In a later round the attacker executed at idx 0 itself (`0x85034238`), so Yoink pre-empted only the first. The delivered-payload record identifies Ultra Sound's builder as the winner at 13.86 ETH, while Eureka bid 14.00 ETH. No winning-block submission survives in the retrieved bid history, so the lower delivered value is unexplained by our records; relay timing or bid adjustment could account for it (Section 2). About 30 h later Yoink's vault returned all 2,882.37 rsETH to `0x8c2aecce`, a signer of the victim Safe.

**UNCX Vesting V2, 2026-10-14 (`beat-pending-attack` for Yoink; later copiers `late-copy`).** [S:uncx] The attacker (EOA `0x78c9b118`) deployed at 14:50 and drained from block 26191745 (`0x35206537`); after three reverted retries, an X-token drain `0xfd6f57ec` landed in block 26191921. It is absent from the mempool archive, so its submission time and route are unknown. Yoink's `0xbf7e5182` took idx 0 of 26191920 (27 lock-and-withdraw iterations, 8.13 ETH to the coinbase); the attacker's X call set landed one block later and reverted ("play failed"), differing from Yoink's only in recipient and block-time arguments (confirmed). A ZC copycat (`0x55b34cd6`) landed later. c0ffeebabe.eth's transaction `0xf57b7dbf` was at idx 0 of block 26191995. At 26191920 bids sat near 0.01 ETH until 0.12 ETH at t_rel -982 ms, then a ladder to 0.84 ETH in 15 ms from +749 ms; Ultra Sound's builder won at 0.84 ETH while collecting 8.14 ETH of transaction revenue. Yoink's vault returned 8.10 ETH and 82,143,476.36 X, keeping exactly 20,000,000 X; c0ffeebabe.eth returned 15.76 ETH on Base; the sum, 23.87 ETH, matches UNCX's reported figure.

**BiFi idle USDT market, 2026-10-17 (`deploy-window-copy`).** [S:bifi] c0ffeebabe.eth's transaction `0x756c6805` was at idx 1 of block 26210256. It took 165,574.51 USDT, swapped to 68.06 WETH, and paid 0.99 ETH to the coinbase. The raced setup was attacker deployment `0x15b47e2c`, block 26210255 idx 333, creating `0x8c0d729d`; no finishing call landed. Our call-level comparison is withheld by policy; anyone can compare the public traces. Titan's 0.99 ETH bid won, while a 1.36 ETH bid from Ultra Sound's builder lost. We found no return; the dataset marks this `none`.

### 4.2 Races against whitehats and users

**Ronin bridge (Ethereum), 2024-08-06 (`beat-whitehat-or-user`).** [S:ronin] Three searchers copied legitimate users' withdrawals. A governance upgrade (`0x855dd3b1`) left the bridge accepting rewritten withdrawal receipts, and three searchers each copied a legitimate user's pending withdrawal (ids 166631 to 166633) and landed first. ETH leg: `0x26195700` at idx 0 of 20468679 took 3,996.09 ETH; the user's `0xc78fb8cd` was first seen at 09:37:22.400 and the copy changes 2 of 76 calldata words. Racer 3 (`0x77bb83dd`, 20468790 idx 0) took 2.42 ETH. Yoink (`0xbce5b854`, 20468848 idx 1) took 1,998,046.875 USDC after the user's `0xb7c3f85a` was first seen at 10:11:40.233 (Section 5.5). The users' own transactions reverted; the pause landed at 10:15:23. The ETH-leg bot returned 4,000 ETH and Yoink withdrew 800 ETH, both before Ronin's first on-chain message (10:53:35); 3,991.097 and 792.46 ETH reached Ronin's Safe. The $500K bounty is reported only [Cointelegraph24Ronin].

**SushiSwap RouteProcessor2, 2023-04-09 (`beat-whitehat-or-user`).** [S:sushi] A router approval let anyone pull a victim's WETH through `processRoute` with a fake V3 pool: 11 transactions, 18 pulls of 100 WETH (1,800 WETH, about $3.3M) in blocks 17007838 to 17007856. Trust initiated a whitehat rescue. Reports call the original attack `0x43ff7e01` (block 17007839 idx 54), but it was sent by a white hat (Trust); Yoink had already pulled 100 WETH a block earlier (`0xb8f57cf8`). Trust's max fee (18.8724 gwei) was below the base fee of Yoink's block (18.8779), so Trust's transaction was still pending and could not have been included there whatever the ordering (it landed one block later, at a base fee of 17.99); Yoink acted on it but did not displace it. Searchers paid 806.98 ETH (44.8%; BlockSec's 44.5% reproduces) to builders and proposers, including 688.88 ETH in 17007842, where c0ffeebabe.eth's transaction (`0x04b166e7`) sat at idx 0 and Yoink (`0x40be81f8`) at idx 1. 875 ETH reached the victim: Trust (90) and BlockSec (100) paid directly, and the Sushi multisig passed on 685.3 ETH, the 305.3 ETH that c0ffeebabe.eth and the 380 ETH that Yoink had sent it. Yoink's 380 ETH went with an on-chain message (`0x7b6eb36a`): "Normally would ask for a 10% bounty for intercepting a blackhat, but seems this was just a dumbhat. Also, NotYoink, stop bribing so much!" In-block only.

### 4.3 Replays, first exploiters and rejected leads

**Saddle, 2022-04-30 (`post-failure-replay`).** [S:saddle] The attacker's second attempt (`0xd9bc8368`, block 14684432) ran out of gas and left funds in the pool. Two blocks later BlockSec's rescue account (`0x811929c3`) ran a contract (bytecode 20 bytes from the attacker's) whose call tree is frame-for-frame identical (403 frames, nine swaps) with that attempt's amounts, swept 1,356.73 WETH and returned it (`0x22efe474`). The attacker then took 557.09 WETH more. The earlier attempt had already landed; BlockSec rescued the remaining funds afterwards. In-block only.

**Secured Finance, 2026-09-05 (`post-failure-replay`).** [S:securedfinance] The attacker (EOA `0xd3ac7b3a`) deployed (`0x3aed40de`, seen 22:41:54.507) and 26 s later sent `0x5d4e4fa9` (seen 22:42:20.456), which a locally building proposer mined in 25914188 and which reverted, out of gas inside the Balancer flash-loan callback. Four blocks and 48 s later c0ffeebabe.eth's `0xcd615986` at idx 0 of 25914192 completed its transaction, sold about 0.9 WBTC for 28.85 ETH and paid 28.84 ETH to the builder (Ultra Sound's builder, whose block was delivered via Titan at 1.28 ETH; it kept 95.6%). The earlier attacker transaction had already failed on chain.

**Balancer v2, 2025-11-03 (`post-failure-replay` / `late-copy`).** [S:balancer] EOA `0x506d1f9e` deployed and ran the rounding-error exploit in one creation transaction (`0x6ed07db1`, block 23717397), then withdrew 6,587 WETH, 6,851 osETH and 4,260 wstETH; a second EOA attacked other pools. The attacker transactions paid about zero tip and mostly never appeared in the public mempool. A bot (`0xc0ffee445a22`; transaction-level facts only, not c0ffeebabe.eth) backran at idx 2, paying 20.6 ETH to Titan's block, of which 0.05 ETH reached the proposer. The whitehat Bitfinding (`0x5af00b07`, matched to BIP-892 by exact amounts) replayed the creation input one block later (`0x1dc60f91`; 3 of 983 words differ), recovered about 260.5 ETH-equivalent in that transaction (about $964K across Bitfinding's three replays) and returned it; the 10.0% bounty was paid 2026-01-15. Every replay lands after the attacker, so "front-ran" means post-inclusion rescue of residual balances.

**TIME token, 2023-12-06 (`bot-was-first-exploiter`).** [S:time] The transaction everyone calls the attack (`0xecdd111a`, block 18730463 idx 0) is Yoink's. It bought TIME, used the thirdweb forwarder so `TIME.multicall(burn)` ran with the Uniswap pool as spoofed sender (62.2 billion TIME burned), and sold: 94.51 WETH out, 4.92 ETH to the coinbase (5.5% of profit), 84.59 ETH kept. CertiK reported an attacker gain of 84.6 ETH, exactly Yoink's net. A `trace_filter` over blocks 18700000 to 18740000 finds one other forwarder multicall, a different bot's copy five hours later (`0x1911be70`, 0.27 WETH). Yoink's transaction is absent from the mempool archive for that day, so we have no attacker transaction to diff against (a private attacker transaction that never landed cannot be excluded); the submission route remains unknown. Flashbots saw 295 bids, quiet until t_rel -2942 ms, then 4.95 ETH and about eight builders within 1 s; the Flashbots builder won at 5.00 ETH; a higher 8.33 ETH bid from "I can haz block?" was never delivered. On 2023-12-11 Yoink funded a contract with 84.1 ETH and posted a message directing TIME holders to an Etherscan contract page to claim funds (`0x273f8e55`; the message transaction itself reverted, but its text remains in the calldata). No other address ever called that contract, and on 2024-01-12 Yoink pulled the 84.1 ETH back (`0x487f7c96`).

**Paraswap Augustus V6, 2024-03-19 (`bot-was-first-exploiter`).** [S:paraswap] Yoink's archive-absent `0x35a73969` (block 19470561, idx 0, 18:25:35) calls Augustus V6's callback entry; Augustus swaps in a V3 pool on behalf of an approving wallet, pulling 12,479.44 OPSEC for 6.46 WETH. A `trace_filter` from the contract's first code (19426044) to 19482000 finds no earlier or same-block call of this kind; the next is 11 h 13 min later. DeFiHackLabs's attack-transaction label and the reported "$24K" (secondhand; see Section 3.5) are this one transaction. Yoink paid 6.45 ETH (99.8%) to the coinbase and received a 4.34 ETH builder refund; the proposer got 2.22 ETH. No bid timeline survives. Net 4.35 ETH for this transaction (4.36 with Yoink's second transaction in the block). Paraswap wrote to Yoink on chain on 2024-03-24 (`0xcaa24228`); about 2.5 hours later Yoink sent 4.34 ETH to the address Paraswap named (`0xa1b1ea50`, block 19508275, 2024-03-25 01:33 UTC), 99.8% of its net and 67.0% of the 6.46 ETH sale. Paraswap thanked Yoink for "sending back half the misappropriated funds" and proposed "a bounty of 10%" on the remaining 90.0% (`0x19a02f97`, 2024-03-25), then wrote (`0xbd43d2de`, 2024-03-26): "0x35a7 took 12,479 OPSEC from the user, which is 6.46 ETH instead of 4.342 ETH that you sent back. Could you please send the rest?" (about 2.12 ETH). Yoink first asked (`0xa645a615`): "Were there any other txs from me other than 0x35a7? If not, then I've already repaid my entire profit (plus some extra from a following arbitrage!) Note the validator payment at the end of the block which limits the funds I'm able to return." It then replied (`0x3d3e7cfe`): "Believe I've explained this already, but lets try one more time. I've already sent you more than 100% of my profits from 0x35a7. Yes the token was sold for 6.45 Eth, but in order to land this tx, I had to pay 2.22 Eth to the validator in a tx at the end of the block. You are, or course, welcome to try and recover the remaining amount from the validator." The block flows agree (2.22 ETH reached the proposer). The DeFiHackLabs comment "frontran by whitehat" is unsupported: Yoink's was the first exploit transaction we can find, though it then returned its net profit (partial against the sale, with the dispute above unresolved: we find no further transfer to the address Paraswap named, through block 19700000).

**Euler copier, 2023-03-13 (`deploy-window-copy`; excluded from the headline).** [S:euler] The attacker (EOA `0xb2698c2d`, Tornado-funded) deployed `0x036cec1a` at block 16817993 (`0x50dc9c91`). One block later a fresh EOA, `0x5f259d0b`, deployed a copy (`0x725db76c`) whose 17,115-byte creation calldata is byte-identical except four copies of the attacker's 20-byte address swapped for its own; the hard-coded cash-out wallet `0xb66cd966` was left in. At idx 0 of 16817996 (`0xc310a0af`, 37.9 gwei tip, no coinbase payment) it called its copy's DAI entry: Aave flash loan of 30M DAI, 38.9M DAI out of Euler, 8,877,507.35 DAI left in the copy. That is the first exploit transaction of the whole hack; the hacker's own first call came 17 blocks later and ran out of gas. When the copier called `withdraw()` (block 16818823), the contract sent all 8,877,507.35 DAI to the hard-coded wallet, the hacker's. The copied transaction delivered funds to the attacker. Position 0 was bought with a 0.07 ETH priority fee (78.0% of the 0.09 ETH winning bid) and no coinbase payment; whether it travelled through the public mempool or a bundle cannot be told (the Flashbots bundle API is dead). "MEV bot" is the copier's own on-chain claim. The fresh, single-purpose account could instead belong to the attacker or an associate: it retained the attacker's cash-out wallet and captured no funds for itself. The code copy and ordering are established, but independence from the attacker is uncertain, so this medium-strength row is outside the headline set. 

**[Conic Finance](https://github.com/DicksonWu654/bot-vs-hacker/blob/main/incidents/conic-2023/incident.json), 2023-07-21.** Yoink copied the crvUSD sandwich in ten consecutive blocks, starting one block after the attacker's successful transaction, taking 125.82 ETH gross, 90.34 ETH net and returning 81.31 ETH. In the separate ETH-pool episode, the first attacker failed in block 17740901; the clone exploiter's drain landed at idx 0 of 17740955, 54 blocks later, and took 1,724.18 ETH. The rows are a late copy and a post-failure replay. In-block evidence only.

**[TaoPad](https://github.com/DicksonWu654/bot-vs-hacker/blob/main/incidents/taopad-2024/incident.json), 2024-02-14 (`post-failure-replay`).** The operator's attempt to pull 29.2 ETH ran out of gas. Yoink replayed the calls four minutes later, netted 26.32 ETH and returned 26.32 ETH the next day after the team contacted it.

**[MintSwap](https://github.com/DicksonWu654/bot-vs-hacker/blob/main/incidents/mintswap-2024/incident.json), 2024-04-01 (`bot-was-first-exploiter`).** Yoink was first to use the vMINT/ETH sell-path bug, across six pool transactions. Its net was 101.80 ETH after builder payments of 110.80 ETH and refunds of 101.73 ETH. It returned 91.62 ETH to the LP.

**[Meta Pool](https://github.com/DicksonWu654/bot-vs-hacker/blob/main/incidents/metapool-2025/incident.json), 2025-06-17 (`bot-was-first-exploiter`).** Yoink was first to use the mpETH mint bug, taking 50.77 ETH gross. It sent 45.79 ETH to Meta Pool, which paid back a 5 ETH reward, leaving 40.79 ETH recovered. The first separate attacker transaction arrived 249 blocks later; no pending attacker transaction is shown. Press descriptions calling this a front-run conflict with the on-chain ordering, and the block lead is undefined.

**[Peapods](https://github.com/DicksonWu654/bot-vs-hacker/blob/main/incidents/peapods-2025/incident.json), 2025-07-08 to 2025-10-09.** Yoink's July drain followed three failed attacker attempts, taking 174,258.313813 USDC one block later and returning 126,891.81 USDC. The 2025-07-09 lead is rejected: none of 36 Yoink transactions touched a Peapods address. In October Yoink swept 8,957.748779 USDC left by a user and returned 1.42 ETH. These are a post-failure replay, a rejected lead and a first-exploiter row; the reported front-run descriptions conflict with the chain evidence.

**[Alkemi](https://github.com/DicksonWu654/bot-vs-hacker/blob/main/incidents/alkemi-2026/incident.json), 2026-03-10.** Yoink took 0.29925557 WBTC, yielding 10.24 ETH gross, one block after another attacker's transaction ran out of gas. Seven ETH-vault copiers arrived one to 444 blocks after the separate 43.45 ETH drain; the best took 0.72 ETH of leftovers. These are post-failure and late-copy rows. The front-run claims conflict with the chain ordering.

### 4.4 Other actors screened and rejected

Three serial senders that DeFiHackLabs lists as attackers were profiled and rejected [Searcher profiles]. `0x7248939f…` is a private-bundle searcher whose three "hacks" are runs 25, 27 and 30 of 48 executions of one swap-back template. `0xd215ffaf…` is a general MEV bot that took funds from unprotected contracts (DAO_SoulMate 134.5 ETH, FLIX 67.6 and others) and returned 84 to 97.0% of the haul in four large cases (inferred from pattern; recomputed from the saved transfer lists). `0x6ce9fa08…` is a real serial exploiter (six exploits in 18 days) that Yoink copied call for call afterwards.

## 5 Anatomy of a front-runner: Yoink

We reverse-engineered one operator's on-chain executor. We chose Yoink (EOA `0xfde0d157…455a`, labelled "MEV Frontrunner Yoink" on Etherscan, a label we have not verified) because Ronin permits a direct comparison of a user's withdrawal and the bot's copy; it has a second confirmed front-run (Kelp); it spans four years and several contract generations; and its runtime bytecode is immutable and identical at the incident block, the block before, and today. The source is unverified but the bytecode is compact (9 to 10 KB) and decompilable (`heimdall`, `evmole`, `cast`, `scripts/bot_re/disasm.py`); all 17,783 gen2 and gen3 inputs parse to the exact byte with the grammar below. We analyse only what is on chain; the off-chain half, how it finds targets and decides, is invisible to us. c0ffeebabe.eth appears in this paper only through public actions (Section 8.3); nothing below concerns its contracts.

### 5.1 Three generations

| | gen1 | gen2 | gen3 |
|---|---|---|---|
| Contract | `0xd050e0a4…` | `0x6980a47b…` | `0x80bf7db6…` |
| Created | 2022-12-02, block 16097930 | 2023-08-31, block 18036360 | 2025-02-08, block 21805063 |
| Runtime size | 8,586 B | 10,318 B | 9,954 B |
| Calldata header | none | yes | yes |
| Callback state | n/a | `SSTORE` | `TSTORE` |
| Uniswap v4 | no | no | yes (ops `0x0a`, `0x0b`) |
| Transactions in corpus | 3,000 sampled | 8,995 | 10,243 |
| Reverted | 1,191 of 2,970 (40.1%) | 69 of 8,148 (0.9%) | 90 of 9,635 (0.9%) |

Sources: `data/raw/etherscan/txlist_*`; `research/bot-re/corpus_stats.json`. An older contract, `0x6c6b87d4` (2022-09-07), appears in Transit Swap and was not analysed. The revert rate fell from 40.0% to under 1.0% between gen1 and gen2, and most remaining reverts have `msg.value == 0` (66 of 69; 73 of 90). We infer, without proof, that gen1 was often sent as ordinary transactions that could fail on chain, and gen2 and gen3 as revert-protected bundles.

### 5.2 The executor is an interpreter

The main entry (selector `0x9846cd9e`) takes a call whose payload is a small program. Callbacks from pools and lenders (`uniswapV3SwapCallback`, Balancer `receiveFlashLoan`, v4 `unlockCallback`) re-enter the contract and run a script embedded in the original call or a template stored for that callback. The gen2/gen3 grammar, recovered by disassembly and checked against every corpus transaction, is:

```
selector | x:uint128 | f:uint8 (+36 B extension if nonzero) | nStores:uint8
 | stores: key:4 then entries [flag:1 | lenScript:4 | lenRet:4 | script | ret], flag 0xff = last
 | ops until end
```

| op | name | layout |
|---|---|---|
| 0 | CALL | len:3, to:20, data |
| 1 | CALL_VALUE | len:3, to:20, value:16, data |
| 2 to 5 | V2/V3 SELL/BUY (names inferred) | pool:20, token:20, a:16, b:16 |
| 6 | PAY_CB | token:20 |
| 7 | ADVANCE_CB | key:4 |
| 8 | SWEEP | token:20, min:16; sends balance minus 1 to the vault |
| 9 | UNWRAP | none |
| 0x0a, 0x0b | V4_SWAP (gen3) | 59 bytes |

Op 0 is the heart of a front-runner: it executes an arbitrary call, so the first op can be the copied victim call with the beneficiary rewritten to the bot contract; the other ops convert the haul to ETH. A Kelp transaction (`0x8dfb264c`) shows a stored seven-op template for callback key `91dd7346`. Gen1 uses the same CALL framing but numbers other ops differently (the gen2 grammar fails on 2,969 of 2,970 gen1 inputs), so we did not decode it. Tokens are swept to the operator's vault EOA (`0xc70f00cd…`).

### 5.3 Profit check and bribe rule

We tested the economics black-box on a local `anvil`; the [published economics results](../site/downloads/yoink/blackbox_results.json) contain the cases below. The local test program is not published. With `S0` and `S1` the contract's balance before and after the script and `x` the header's minimum profit:

```
profit = S1 - S0; require(S1 >= S0 + x) else revert "poor"
msg.value == 0:    no payment
msg.value < 1000:  bribe = profit * v / 1000;   if bribe > profit - x then bribe = (profit - x) / 2
msg.value >= 1000: bribe = v * 1e11 wei
coinbase.transfer(bribe)
```

Tests: `v`=999, `x`=0, profit 1 ETH pays 0.999; `v`=500 pays 0.5; fixed `v`=1000 pays 0.0001; fixed `v`=10,000,000 pays 1; `v`=999 with `x`=0.5 pays 0.25 (halving rule); `x`=2 reverts "poor". The formula reproduces real payments exactly. Ronin: 795.615040934472 ETH equals `floor(796.4114523868589 x 999 / 1000)` (`0xbce5b854`). DeFi Plaza: `v` = 663180915 gives 66.3180915 ETH (`0xa245deda`). Kelp: 18.93122 ETH from 18.95017 ETH (`0x0e7680b0`). TIME: `v` = 55 gives 5.5% of profit, 4.923 ETH (`0xecdd111a`). The bribe is a programmable fraction of realised profit, set per transaction by the off-chain half, and the profit check makes each transaction revert-protected.

### 5.4 The builder round-trip

Across the 11 priced mature-PBS headline rows, the median payment before refunds was 97.8% of gross. Subtracting known builder refunds lowers the median over the same 11 rows to 26.8%. The distribution is split: eight rows paid over 90.0% before refunds, while Neemo, Kelp and BiFi each paid under 2.0%. Six of the eight high-payment rows are Yoink's. In early PBS, the before-refund median was 0.015% over six rows; the after-refund median is 2.3% over only three rows with a known refund figure, so the samples differ. The tiny early-PBS value retains extra precision to avoid rounding a measured payment to zero.

The coinbase transfer measures the payment before refunds. The realised cost is that payment minus the builder refund, with gas accounted for separately. In the Ronin block (20468848) Yoink's 21 transactions made coinbase transfers totalling 802.78525 ETH. The builder then paid 791.74228 ETH back to the bot (idx 22) and 11.04299 ETH to the proposer (idx 23), equal to the relay's delivered value (`research/bot-re/block_flows.json`). EigenPhi states that the builder and Yoink are one entity [EigenPhi24Yoink]; we did not re-derive its analysis. Other races look alike.

| Race | Payment before refund (ETH) | Refunded to bot (ETH) | Payment minus refund (ETH) | Reached proposer (ETH) | Share refunded |
|---|---:|---:|---:|---:|---:|
| Ronin, 20468848 (21 tx) | 802.79 | 791.74 | 11.04 | 11.04 | 98.6% |
| Alkimiya, 22146340 | 50.83 | 48.28 | 2.56 | 2.58 | 95.0% |
| Paraswap, 19470561 | 6.45 | 4.34 | 2.11 | 2.22 | 67.2% |
| DeFi Plaza, 20240539 | 66.32 | 4.76 | 61.56 | 62.54 | 7.2% |

Alkimiya's and Paraswap's refunds cover the whole block, including a second routine Yoink transaction in each; at block level the shares are 94.9% and 66.2%. The observed coinbase transfer sets a payment ceiling. Subtracting a builder refund gives the bot's net payment; the block's proposer bid also includes other transaction revenue, so it can differ from the cost of the incident transaction alone. At a vertically integrated builder, rival bids can determine how much of that ceiling is spent. At DeFi Plaza a rival bid 62.49 ETH and Yoink's builder won at 62.5409, so almost the whole bribe left the bot; at Ronin, with no comparable rival (the highest earlier competing bid was 1.08 ETH), almost all returned. That the builder and bot are one operator is inferred from the in-block refunds, the builder name "I can haz block?" and EigenPhi's statement; no operator statement or on-chain label confirms it, and the Kelp-era fee recipient `0x6c42a0b5…` is not proven to be Yoink's. A reported payment to the builder can therefore overstate the realised cost by an order of magnitude.

### 5.5 Ronin: one copy, word by word

The user's withdrawal `0xb7c3f85a` was first seen in the public mempool at 10:11:40.233. Yoink's builder placed its first bid 4.138 s later (2.82 ETH, 23 transactions); the winning 11.043 ETH bid (24 transactions) arrived at 10:11:45.172 for block 20468848 (10:11:47). The user's transaction landed in the next block and reverted (error selector `0x4f13df61`, which we read as the withdrawal id already being used).

| level | user's transaction | Yoink's transaction |
|---|---|---|
| top | EOA `0x5f494a30…` to bridge `submitWithdrawal` | EOA `0xfde0d157…` to bot `9846cd9e`, value 999 |
| 1 | implementation `DELEGATECALL`, reverts | same bridge call, then `USDC.transfer` of 1,998,046.875 to the bot |
| 2-4 | none | Uniswap V3 `swap`; `WETH.withdraw(796.4114523868589)`; 795.615040934472 ETH to coinbase `0x229b8325…` |

The 1,956-byte payloads differ in 3 of 61 words: two recipient words (the user's EOA becomes the bot contract) and one quantity (`0x9d67b973`, 2,640.82 USDC, becomes `0x1d134dfcd78`, 1,998,046.875 USDC); the 16-signature array is byte-identical (`research/bot-re/ronin_calldata_diff.json`). Fork tests at block 20468847 show that Yoink's input replays successfully after the block's transaction 0 but reverts without it (a hard-coded WETH amount depends on in-block pool state), and that the user's calldata with the recipient words swapped pays the new recipient. Amounts up to 1,999,999.999999 USDC pay in full while 2,000,000 or more succeeds and pays nothing; 1,998,046.875 equals 2,000,000 x (1 - 2^-10), suggesting the bot bisects for the largest payable amount (inferred).

### 5.6 Pipeline, ordinary business and limits

The chain evidence fits six steps: (1) spot a pending transaction that moves value to its callee or sender; (2) substitute addresses and re-size amounts; (3) wrap it as op 0 of a script followed by swap and unwrap ops; (4) choose `msg.value`; (5) simulate on exact in-block state; (6) have the operator's builder place the bundle at idx 0 and escalate the bid. Steps 1 and 5 are not on chain, and Kelp shows a bot that calls the attacker's prepared contract instead of copying a transaction.

Incident transactions are sparse among noise (common calls are V3 `swap`, `WETH.withdraw`, `approve`, Balancer `flashLoan`). A traced sample of 36 transactions per generation (seed 20261021) shows median coinbase payments of 0.0136 ETH (gen2) and 0.0072 ETH (gen3) over all 36 (0.0177 and 0.0082 over the 30 successful transactions in each), and most successes landed in blocks whose fee recipient is `0x229b8325…` or `0x6c42a0b5…`. All five incident transactions we decoded (Ronin, Kelp, DeFi Plaza, UNCX, Alkimiya) sit at position 0 or 1. Limits: "first seen" is the archive's, not Yoink's; ops 2 to 5 names and the bisection are inferences; gen1 was sampled; Etherscan caps lists at 10,000 rows.

## 6 Has the dark forest evolved?

We measure public visibility, constructor-only execution, the lifetime of a fresh attack contract, and price competition on DeFiHackLabs mainnet entries. The sender-corrected measurements come from [the era aggregates](https://github.com/DicksonWu654/bot-vs-hacker/blob/main/data/evolution/by_era_v2.json), [per-exploit records](https://github.com/DicksonWu654/bot-vs-hacker/blob/main/data/evolution/per_exploit_v2.json) and [findings](https://github.com/DicksonWu654/bot-vs-hacker/blob/main/data/evolution/findings_v2.txt). E1 is pre-2021; E2 is 2021 to September 2022; E3 is September 2022 through 2023; E4 is 2024 through 2026. Percentages below retain the precision stored in the aggregates. Fresh deployment gaps cover attacker-owned contracts deployed within seven days of the attack.

### 6.1 Sample and sender classification

Of 365 mainnet entries, 320 have a resolvable transaction and five are duplicate listings, leaving 315 rows before sender filtering. The attacker-only sample has 281 rows; adding four unknown-sender rows gives the sensitivity sample of 285. Sender filtering removes 34 of 315 rows (28 bot-only, one whitehat and five unknown-sender or non-attack rows); 35 first-listed transactions were not sent by attackers, including one retained mixed row. Nine c0ffeebabe.eth listings are classified from the listed sender; these transactions are outside the traced attacker-side sample. Neemo's listed sender `0xb750e316` is a bot and its row is excluded from attacker measurements.

### 6.2 Attacker-side results

| Metric | E1 | E2 | E3 | E4 |
|---|---:|---:|---:|---:|
| Exploits analysed (attacker-only) | 11 | 22 | 82 | 166 |
| Archive-era rows | 0 | 0 | 37 | 166 |
| Resolved public-visibility denominator | 0 | 0 | 37 | 165 |
| Public share of resolved archive rows | n/a | n/a | 8.1% (3/37) | 3.6% (6/165) |
| Same-block neighbours seen | n/a | n/a | 86.5% | 59.4% |
| Constructor exploit | 0.0% | 9.1% | 4.9% | 36.7% |
| Constructor or internal CREATE | 0.0% | 9.1% | 8.5% | 40.4% |
| No watchable window | 0.0% | 9.1% | 9.8% | 50.0% |
| Median fresh deploy-to-attack gap (seconds) | 778.5 (n=6) | 1906 (n=11) | 306 (n=64) | 144 (n=77) |
| Deploy in same block as attack | 0.0% | 0.0% | 1.6% | 20.8% |
| ORIGIN-opcode check | 16.7% (n=6) | 27.3% (n=11) | 29.4% (n=68) | 30.2% (n=86) |
| Any sender guard | 16.7% | 45.5% | 41.2% | 41.9% |
| Coinbase payment inside transaction | 0.0% | 4.5% | 7.3% | 8.4% |
| Zero priority fee but included | 0.0% | 9.1% | 1.2% | 3.0% |
| Median transaction index | 30 | 51.5 | 12 | 16.5 |

The archive-era count includes an unresolved row in E4. Public-visibility shares use the resolved denominator, with the same-block control alongside. No watchable window means a constructor exploit, an internal creation that attacks, or an attack contract deployed in the attack block.

| Year | Rows | Constructor | No watchable window | Median fresh gap, seconds (n) | Median index | Coinbase payment |
|---|---:|---:|---:|---:|---:|---:|
| 2020 | 7 | 0.0% | 0.0% | 903 (5) | 30 | 0.0% |
| 2021 | 10 | 0.0% | 0.0% | 7658 (4) | 39.5 | 0.0% |
| 2022 | 28 | 7.1% | 7.1% | 347 (21) | 8.5 | 7.1% |
| 2023 | 66 | 6.1% | 12.1% | 306 (50) | 13.5 | 7.6% |
| 2024 | 64 | 15.6% | 26.6% | 234 (40) | 21.5 | 4.7% |
| 2025 | 50 | 62.0% | 76.0% | 72 (13) | 7.5 | 10.0% |
| 2026 | 52 | 38.5% | 53.8% | 60 (24) | 8 | 11.5% |

Yearly gaps use the same fresh-contract filter as the era table; n is the number of measured deployment gaps, not the yearly exploit count.

### 6.3 What the data say

Since August 2023, 9 of 202 resolved attacker transactions (4.5%, 95.0% Wilson interval 2.4 to 8.2%) were seen in the public mempool, against 62.5% of ordinary transactions in the same blocks. The yearly controls were 86.5% in 2023, 57.4% in 2025 and 49.7% in 2026. Over BACKRUNNER's shared measurable window, August 2023 through May 2024, we find 8 of 67 exploits public (11.9%), compared with its 17 of 158 attack transactions (10.8%); the units differ.

The constructor share is 0.0% in E1, 9.1% in E2, 4.9% in E3 and 36.7% in E4, reaching 62.0% in 2025 and 38.5% in 2026. Median fresh deployment gaps are 778.5, 1,906, 306 and 144 seconds across the four eras. Attacker coinbase-payment shares are 7.3% in E3 and 8.4% in E4, with overlapping 95.0% Wilson intervals of 3.4 to 15.1% and 5.1 to 13.7%. These payments provide little evidence of a rising attacker trend.

### 6.4 The bot side, separately

Across DeFiHackLabs-listed exploits, the separate bot-side table contains 38 rows: 29 traced bot transactions and nine c0ffeebabe.eth rows identified by sender. E3 contributes 10 bot rows and E4 28; 29 of 38 (76.3%) are at transaction index 0. Among the 29 traced bot transactions, 21 (72.4%) paid a coinbase transfer, totalling 1,490.47 ETH. The median among payers was about 2.63 ETH and the maximum about 1,299 ETH. Zero priority fees occur in 62.1% of traced bot transactions and 2.8% of attacker transactions. These are transactions found in exploit listings, so the sample cannot estimate bot prevalence.

### 6.5 Interpretation and caveats

The attacker sample has low archive visibility and frequent constructor execution. Fresh deployment gaps rise from E1 to E2, then fall through E3 and E4; the pattern varies by era. It cannot explain why attackers changed. Archive coverage also fell, the attack mix changed, and DeFiHackLabs coverage is selective. Sender classes are evidence-ranked. The four unknown-sender rows enter only the sensitivity sample. Before 2023-08-07, exposure is in-block evidence only.

## 7 Who gets the money

### 7.1 Where the bribe goes

A bot's coinbase payment is a visible transfer before refunds. Section 5.4 reports the payment minus the refund alongside it; victim pass-throughs are a separate destination. The table below follows the money where we could trace the block's payments.

| Race | Bot paid coinbase (ETH) | Proposer got | Builder kept or forwarded | Back to bot | To victim via the block |
|---|---|---|---|---|---|
| Blueberry (2024-02) | 457.55 | 91.04 (19.9%) | 366.51 forwarded | 0 | 366.51 to the multisig |
| DeFi Plaza (2024-07) | 66.32 | 62.54 (Lido vault) | about 0 | 4.76 | 0 |
| Ronin, Yoink (2024-08) | 802.79 (21 tx) | 11.04 | about 0 | 791.74 | 0 |
| Paraswap (2024-03) | 6.45 | 2.22 | 0 | 4.34 | 0 |
| Alkimiya (2025-03) | 50.83 | 2.58 | 0 | 48.28 | 0 |
| Makina (2026-01) | 1,299.05 | 276.32 (21.3%) | 1,023.00 forwarded to `0xbed` | 0 | 920.70 returned by `0xbed` after a 10.0% bounty |
| Kelp (2026-09) | 18.93 | 13.86 | 5.07 | 0 | 0 (rsETH later returned) |
| UNCX (2026-10) | 8.13 | 0.84 | about 7.30 (the block paid the builder 8.14 in all) | 0 | 0 (ETH and most X tokens later returned) |
| Secured Finance (2026-09) | 28.84 | 1.28 | 27.56 (95.6%) | about 0 | 0 |
| Earning.Farm (2022-10) | 18.72 | about 18.80 | about 0 | 0 | 0 |
| Sushi RP2 (2023-04, all copiers) | 806.98 (805.98 coinbase plus 1.00 priority fees; 44.8% of 1,800) | about 99.9% of builder-side total | small | not traced | 875 ETH returned by hand |

Four patterns recur. Competition among copiers is a transfer to the proposer: in Sushi about 99.9% of what builders received went on to proposers, and at DeFi Plaza 62.54 of 66.32 ETH reached the Lido execution-layer rewards vault [Lido24]. Second, a builder can refund the bot (Ronin, Alkimiya, Paraswap), so the bribe overstates the cost. Third, in two cases the auction moved money to the victim: Blueberry's builder sent 80.1% of the bot's payment to the protocol's multisig in the same block, and Makina's builder forwarded 1,023 ETH to an address that returned 920.7 ETH. Fourth, builders sometimes keep it: in Secured Finance Ultra Sound's builder kept 95.6%, and in UNCX it kept about 90.0%. Taken together, in the 12 headline rows with a known winning bid the proposer received a median 12.5% of the bot's gross; across 23 bot-transaction rows with bid history the pooled proposer share was 4.5%. The destinations differ by incident: proposer revenue, builder retention, refunds to the bot and victim pass-throughs. The headline split is reported below.

For the 11 mature-PBS headline rows, the total payment before refunds was 1,906.02 ETH. Traced destinations divide it as follows:

| Destination | ETH | Share of payment |
|---|---:|---:|
| Victims via builder/proposer pass-throughs | 1,287.33 | 67.5% |
| Builder refunds to bots | 54.62 | 2.9% |
| Remainder with builders and proposers | 564.08 | 29.6% |

The victim total includes Blueberry's later builder residue and Makina's later return through `0xbed`. The remainder is the residual under these traced flows; later unobserved transfers could change it. Makina's 0.13 ETH was retained from the original take, rather than refunded by the builder. Across all 18 priced headline rows, the pooled payment before refunds was 10.4% of gross. The mature-PBS medians in Section 5.4 use the same 11 rows before and after refunds; broader after-refund aggregates have fewer rows because some refund amounts are unknown.

### 7.2 Norms and frameworks

The SEAL Whitehat Safe Harbor pre-authorises rescue under pre-agreed terms (return within 72 hours, a pre-agreed bounty, and no cover for an attacker who rescues from a second account) and does not mention MEV bots [SEAL]. In practice bots and victims talk by on-chain messages: Transit messaged Yoink three times in October 2022; Makina's 920.7 ETH return followed Safe Harbor messages; DeFi Plaza's message at 19:00:23 was followed by a partial return. Observed bounties are about 10.0%: Curve pETH (610.6 of 6,106.75 WETH), Makina (102.3 of 1,023.0 ETH), Balancer's Bitfinding (paid 2026-01-15); Alkimiya's Safe sent back 13.0% of what Yoink had sent (a bounty only by our reading of the flows); Ronin's $500K bounty is reported only. BlockSec argues that a bot front-running attack transactions counts as an attack itself [BlockSec22]; an Ethereum developer called returning funds "probably a legal grey area" [Unchained23]. Our source sweep found no documented case of a bot pursued for keeping funds; its legal coverage is incomplete.

### 7.3 Public actions of c0ffeebabe.eth

Public, transaction-level facts only. In the CRV/ETH pool the operator received 2,879.66 ETH and returned 2,879.54 ETH the same day to the Curve deployer, after an on-chain message (`0xc52cce67`) reading "moving funds to cold wallet for now, affected protocols can contact via etherscan chat" ([Decrypt23]; [TheBlock23]); the deployer's reply (`0x65670d8e`) asked about a refund. In Blueberry's block the builder's fee recipient, not the bot, sent 366.5 ETH to the protocol's multisig, and the bot's EOA later sent a further 70 ETH to the same multisig (purpose not stated in any source we saw; together 436.6 ETH, 95.4% of the bot transaction's gross, counting a 0.12 ETH residue the builder's fee recipient sent two days later); returned 305.3 ETH in the Sushi episode and 15.76 ETH on Base for UNCX (cross-chain, so not attributable to the one Ethereum transaction alone); and in Secured Finance kept 0.0110 ETH net of gas (0.0115 ETH before gas, about $29) of a 28.85 ETH sale. We found no return for BiFi. For the msETH pool the operator sent 1,000 ETH (after a 0.1 ETH test transfer and a 0.01 ETH reply) to `0xfa9b97d6`. Contemporary press described this as a cold-wallet move [TheBlock23]. We have no verified attribution of that recipient to the victim, so the msETH return remains unknown.

### 7.4 Yoink's record: returns and keeps

Across headline and related cases, the 13 priced Yoink rows, excluding the two campaign-scope rows (Conic crvUSD and MintSwap), include two known-zero returns. They returned 94.6% of gross pooled, with an 80.3% median row and a 0.0% to 99.5% range. The pooled figure weights large takes more heavily. The 12 comparable bot-net rows returned 97.3% pooled, with a 90.2% median and a 0.0% to 100.0% range.

The incident records show the pattern: Transit, Alkimiya, Kelp, UNCX, TaoPad, Meta Pool, Peapods, Ronin, Paraswap and DeFi Plaza have a return of some kind, while TIME kept its proceeds. Unizen's return is incident-wide and includes a successful ETH resend in `0x4f647c4d`; the earlier attempt reverted. Builder pass-throughs are counted in gross returns and excluded from bot-net returns.

### 7.5 Bots that kept funds

Earning.Farm's 0xa57 bot sent 480.1 ETH to the operator's capital wallet (`0x56178a0d`); no return, no statement. The SHOCO bot kept about 4.05 ETH net. The separate Euler case (Section 4.3) spent about 0.61 ETH of gas on a copy that paid 8.88M DAI to the attacker's wallet; the copier's independence remains uncertain.

*The 0xa57 lineage.* The DODO winner "Cheetah" (EOA `0x8a14ce0f`) and the Earning.Farm bot (EOA `0x26bce6ec`) are one operator, with high confidence from address links; real-world identity remains unknown. Cheetah's DODO take went to `0x56178a0d`, the capital wallet that lent 14,707 WETH in the Earning.Farm transaction and that deployed an executor for each episode through the same factory; the hub EOA `0x8641df2d` deployed the 2019 proxy `0xa57bd001` and, through a second factory, the 2022 contract `0xa69babef` (a superset of the proxy's interface) that the Earning.Farm bot called; and both EOAs were funded by the same top-up wallet `0x9787ffbd` (38 and 145 times). The Earning.Farm transaction called `0xa69babef`. The evidence points to a large general MEV operation: the proxy family has had hundreds of authorised EOAs since 2019 (279 added by November 2019; 458,903 `execute()` calls counted exactly through August 2020, later counts estimated from samples), so DODO and Earning.Farm are two entries in a much larger stream, and its only returned case we found is DODO (Section 4.1).

### 7.6 Returns across the headline races

We use one return-status rule: `returned` means everything came back except a bounty the victim agreed to or offered; `partial` means some came back; `none` means a known zero within the documented search window; `unknown` means unresolved. Of the 19 headline rows, four are returned, eleven partial, three none and one unknown. Transit is returned under its accepted bounty agreement; Punk is partial because the USDC sent to the attacker was not recovered. Neemo is returned under the victim's 20.0% bounty offer. Kelp is partial: 17.63 rsETH paid to the builder did not return, and no bounty was agreed or offered. Unizen's three headline rows are partial, sharing one incident-wide return that is unallocated by row.

Known-zero outcomes enter the pooled denominators. The gross headline denominator has 14 priced rows, including BiFi, Earning.Farm and SHOCO at zero. It excludes msETH's unknown return, DODO's unpriced take and the three Unizen rows whose shared return is unallocated. The bot-net denominator removes builder pass-throughs from the numerator and excludes rows with negligible or incomparable net balances; its four zero-return rows include Makina, whose victim recovery came through the builder.

| Sample and denominator | Rows | Returned (ETH-equivalent) | Denominator (ETH-equivalent) | Pooled return | Median row |
|---|---:|---:|---:|---:|---:|
| Headline, gross | 14 | 14,594.09 | 17,557.33 | 83.1% | 81.3% |
| All bot-transaction rows, gross | 28 | 21,088.31 | 25,972.44 | 81.2% | 79.2% |
| Headline, bot net | 12 | 13,228.66 | 14,725.04 | 89.8% | 85.1% |
| All bot-transaction rows, bot net | 25 | 19,722.88 | 23,073.17 | 85.5% | 89.2% |
| Headline excluding c0ffeebabe.eth, gross | 11 | 11,277.82 | 14,151.93 | 79.7% | 80.0% |

Excluding c0ffeebabe.eth rows leaves 15 headline rows in 13 incidents; the 11 with comparable priced gross and known returns include two known-zero rows.

Builder or proposer pass-throughs supplied 1,287.33 ETH of headline returns, or 8.8% of the returned ETH. Those amounts enter gross recovery and are excluded from returns against the bot's own net. Section 7.4 reports Yoink's pooled and median outcomes together. The headline rows with no return found are BiFi, Earning.Farm and SHOCO; msETH remains unknown. Euler is outside the headline set. The medium-strength cases and count sensitivities are listed in Section 3.4.

The all-bot-transaction-row recovery figure also includes two whitehat rescues, Saddle and Balancer/Bitfinding.

## 8 Discussion

### 8.1 Implications for protocols and incident responders

**A small group of operators won the documented races.** Yoink accounts for eight headline rows, c0ffeebabe.eth for four and anonymous searchers for three. Four other operators contribute one each: the pETH front-runner, Antelope, the Earning.Farm 0xa57 bot and the Makina searcher. The headline includes the medium-strength cases described in Section 3.4; that section also gives the count excluding c0ffeebabe.eth.

**Recovery differs across operators.** Across 13 priced transaction-scope Yoink rows, 94.6% of gross reached victims pooled; the Earning.Farm (0xa57), SHOCO and BiFi rows have known-zero returns. Section 7.6 separates victim recovery against gross loss from returns against the bot's own net, including builder pass-throughs and refunds.

**Builder bid response can be measured for public triggers.** The winning builder's first qualifying step-up followed first public sighting by 266 to 4,138 ms across five measured races (median 873 ms); the three headline rows had a 443 ms median. The observations were 266 ms (Blueberry), 3,013 ms (DeFi Plaza's deployment), 873 ms (Ronin ETH withdrawal), 4,138 ms (Ronin USDC withdrawal) and 443 ms (Unizen USDT attack). The upper-bound median to a winning-block submission was 2,888 ms. Bid contents and bot detection times remain unknown. Four of the 11 archive-era headline triggers were publicly observed before inclusion: Blueberry, DeFi Plaza and two Unizen rows.

**Constructor and same-block deployment close the window.** Constructor-only exploits reached 62.0% in 2025, and 76.0% of 2025 rows left no watchable window in the corrected evolution sample. Contract limits, circuit breakers, caps and delayed withdrawals therefore matter more than a race response.

**What responders can do.** Publish a recovery address, an on-chain contact path and Safe Harbor terms in advance. Ask the winning builder and proposer fee recipient about refunds. Treat database attacker labels as provisional until the sender is checked.

### 8.2 Limitations

Coverage: the copy scan used a four-block window, up to 28 traces per transaction (the cap hit in about two thirds of incidents), at most six transactions per proof of concept, and cannot see mempool-level interception. Mainnet only. Archive: no mempool data before 2023-08-07; 2023 relay bids only from Flashbots; bids never reveal contents. Timing: latency numbers cover five rows where the trigger (an attacker transaction or deployment, or a user withdrawal) was in the archive before inclusion, three of them headline races; the measured median is 873 ms and the headline-row median is 443 ms. For the other archive-era races the trigger is absent from the archive, leaving its submission route unknown. Selection: the headline set cannot include races whose attack was front-run so well that it never appears in DeFiHackLabs. Attribution: operator identity rests on address labels and public messages; builder-operator links are inferred. The 2026 incidents are recent and returns may be pending. The literature sweep was partial: about 40 searches found no earlier paper reconstructing individual exploit races.

### 8.3 Ethics and responsible handling

We replayed already-public transactions on local `anvil` forks for verification, including recipient-substitution tests. The published replay scripts reproduce those historical transactions locally. We wrote no new exploits and sent no transactions to live networks.

*c0ffeebabe.eth.* We report transaction hashes, blocks and positions, funds taken or returned, and public statements. Supporting block-level records omit this operator's call-level data. Our call-level comparison is withheld by policy; anyone can compare the public traces. Calldata decodes, per-transaction traces and contract internals are withheld. Sender labels identify these rows in the sender-class summary; they are outside the traced attacker-side sample.

*Operational security.* No transaction was sent to any bot; tests ran on local forks. Section 5 describes Yoink's executor and observed money flows.

*Naming.* We name Yoink, the Makina searcher and others by address because the evidence is public and reproducibility needs it. "Bot" and "front-runner" label observed on-chain behaviour; intent remains unknown. Several bots returned funds and others kept them; we report both and mark inferences.

## 9 Related work

**Generalized front-running and MEV.** Robinson and Konstantopoulos described a "generalized frontrunner" that copies a pending transaction, replaces addresses with its own and follows internal calls from the trace; it swept their own rescue attempt [Robinson20]. samczsun's follow-up rescued the bulk of a contract holding over 25,000 ETH by routing around the public mempool through a mining pool's private endpoint [Samczsun20]. Flash Boys 2.0 introduced priority gas auctions and MEV [Daian19]. Qin et al. gave the first concrete algorithm [Qin22]; Torres et al. measured displacement, insertion and suppression at scale [Torres21]; the Blockchain Imitation Game synthesises adversarial contracts to pass caller checks [Qin23]. These measure extraction from trades; individual exploit-race reconstruction is outside their scope. Further background: DeFiPoser [Zhou21], private-pool and bundle measurements [Weintraub22; Piet22; Li23], and the reordering-defence SoK [Heimbach22]. "Front-running" in Zhang et al. concerns contract vulnerability to transaction ordering [Zhang23combat]; our usage follows BACKRUNNER's footnote [Shou24].

**Front-running attackers as a defence.** STING, FrontDef, FlashGuard, LookAhead and BACKRUNNER build counter-transactions from observed attacks [Zhang23; Deng23; Alhaidari25; Ren24; Shou24]. BACKRUNNER is the closest prior work and the only study we found measuring real outcomes: 18 of 158 attack transactions in 2023-24 were intercepted, 17 were public, and rescued funds were heavily diverted to builders [Shou24]. Its authors run a rescue system and its visibility figure comes from their own nodes plus Blocknative, so it is a lower bound. Relative to it we add named, hash-level incidents; per-incident relay auctions; an independent mempool archive; a taxonomy distinguishing pending-attack races from the other race types; and the fate of the money. Ours is Ethereum only; theirs mixes Ethereum and BSC. BlockSec reports a commercial pipeline and rescues, including a third-party bot whose funds were recovered for the victim [BlockSec23; BlockSec22; BlockSec24].

**Evasion and adversarial dynamics.** EVScope documents 32 evasion strategies in 71 attacks that beat bots [Ma25]; ZenGo's honeypots showed bots follow internal calls and defeat simple proxy hiding [Coindesk20]; sandwich-bot traps, validator-level bait-and-reorder and bot contract bugs show the arms race runs both ways [Worsley21; Blockhead23; Zellic23].

**Block-building auctions.** Post-Merge work covers builder and relay concentration [Heimbach23; Wahrstatter23; Yang25], auction winners [Oz24] and validator timing [Oz23]; relay APIs, cancellations and optimistic submission are specified in primary documents [RelaySpecs; Neuder23cancel; Neuder23opt; UltraSoundDocs]. We found no paper that uses relay bid traces to reconstruct individual exploit races. Adjacent 2026 work covers sandwiches on protected order flow [Heimbach26] and LLM-generated MEV bots [Wen26].

## 10 Conclusion

A bot got there first in 19 headline rows across 15 incidents, including medium-strength inferences. The beaten party was the original attacker in 8 confirmed and 5 likely cases; 6 rows involved a later exploiter or unresolved loser. Excluding c0ffeebabe.eth rows leaves 15 rows across 13 incidents; Euler is outside the headline because the copier may have been the attacker or an associate. The mature-PBS median payment was 97.8% of gross before refunds and 26.8% after refunds. In two of 11 mature-PBS headline rows (Blueberry and Makina), the builder side passed most of its payment to the victim. Makina's large payment brings this to 67.5% of all payments pooled; its return followed two days later, after a Safe Harbor bounty negotiation. In the other nine rows, no builder-side payment reached victims in the documented window. Across 14 priced headline rows, including three known zeros, 83.1% of gross reached victims (Section 7.6). The corrected evolution sample shows low attacker visibility in the public-mempool archive and frequent constructor execution. Rescue by bot remains operator-dependent. Protocols need contract-level limits, a published recovery path and terms that bots can see; researchers need durable relay and mempool archives and explicit sender classification.

## References

Data and analysis files (paths relative to the repository root): [Chain scan] `research/chain-scan/findings.txt`; [Relay analysis] `research/infra/README.md`; selected public transaction evidence in `research/bot-re/`; [Evolution] `data/evolution/findings_v2.txt` and `by_era_v2.json` (v1 is superseded for attacker-side numbers); master dataset `data/incidents.json`, `data/headline_stats.json`, `data/comparison_table.csv`, `data/harmonize_log.json`; [Searcher profiles] `research/anon-bots/profiles.txt`; incident files `incidents/<slug>/{incident.json,timeline.json,summary.txt,race_*.json}`; published source subset `site/raw/` with `site/raw/MANIFEST.json`; the full research cache under `data/raw/`, with retrieval log `MANIFEST.jsonl`, is not published.


[Alhaidari25] A. Alhaidari, B. Palanisamy, P. Krishnamurthy. Protecting DeFi Platforms against Non-Price Flash Loan Attacks (FlashGuard). 2025. [arXiv](https://arxiv.org/abs/2503.01944)

[BlockSec22] BlockSec. Blocked Transit Swap attack: industry's first hacking back to rescue $300,000. 2022. [blocksec.com](https://blocksec.com/blog/blocked-transit-swap-attack-industry-s-first-hacking-back-to-rescue-300-000)

[BlockSec23] BlockSec. How BlockSec rescued stolen funds: technical perspectives of three representative cases. 2023. [blocksec.com](https://blocksec.com/blog/how-blocksec-rescued-stolen-funds-from-technical-perspectives-of-three-representative-cases)

[BlockSec24] BlockSec. How can BlockSec Phalcon prevent hacker attacks on DeFi protocols by using front-running techniques. 2024. [blocksec.com](https://blocksec.com/blog/how-can-block-sec-phalcon-prevent-hacker-attacks-on-de-fi-protocols-by-using-front-running-techniques)

[Blockfence26] M. Williams. MEV Bot Takes $7.8M From rsETH Exploit. Blockfence, 2026. [blockfence.io](https://blockfence.io/mev-bot-takes-7-8m-from-rseth-exploit/)

[Blockhead23] N. Liew. Exploiter front-runs $25M from MEV bots using Ethereum validator. Blockhead, 2023. [blockhead.co](https://www.blockhead.co/2023/04/04/exploiter-front-runs-25m-from-mev-bots-using-ethereum-validator/)

[Cointelegraph24Ronin] Cointelegraph. Ronin white hat attacker returns $10 million ETH after apparent accidental front-run. 2024. [cointelegraph.com](https://cointelegraph.com/news/ronin-white-hat-attacker-returns-10-million-eth-apparent-accidental-front-run)

[Coindesk20] B. Powers. New Research Sheds Light on the Front-Running Bots in Ethereum's Dark Forest (ZenGo "Ethology" research by A. Manuskin). CoinDesk, 2020. [coindesk.com](https://www.coindesk.com/tech/2020/12/29/new-research-sheds-light-on-the-front-running-bots-in-ethereums-dark-forest)

[Daian19] P. Daian et al. Flash Boys 2.0: Frontrunning in Decentralized Exchanges, Miner Extractable Value, and Consensus Instability. IEEE S&P 2020. [arXiv](https://arxiv.org/abs/1904.05234)

[Decrypt23] A. Beganski. How an Ethereum Bot Used Uniswap to Save $5.4 Million From Curve Exploit. Decrypt, 2023. [decrypt.co](https://decrypt.co/150713/how-ethereum-uniswap-save-5-4-million-curve-exploit)

[Deng23] X. Deng et al. A Robust Front-Running Methodology for Malicious Flash-Loan DeFi Attacks (FrontDef). DAPPS 2023. [DOI](https://doi.org/10.1109/DAPPS57946.2023.00015)

[DLNews23] DL News. Conic Finance does not blame auditor PeckShield for hack. 2023. [dlnews.com](https://dlnews.com/articles/defi/conic-finance-does-not-blame-auditor-peckshield-for-hack/) (cited from the candidate survey; not re-fetched)

[Dumpster] Flashbots. mempool-dumpster. [github.com](https://github.com/flashbots/mempool-dumpster)

[EigenPhi24Yoink] EigenPhi. MEV Maestro Yoink netting $2.65M on 59 blocks in Aug. 2024. [eigenphi.substack.com](https://eigenphi.substack.com/p/mev-maestro-yoink-netting-265m-on-59-blocks-in-aug)

[EthereumOrgPoS] ethereum.org. Proof-of-stake. [ethereum.org](https://ethereum.org/en/developers/docs/consensus-mechanisms/pos/)

[FlashbotsAuction] Flashbots. Flashbots Auction overview. [docs.flashbots.net](https://docs.flashbots.net/flashbots-auction/overview)

[FlashbotsRelay] Flashbots. Relay Fundamentals. [docs.flashbots.net](https://docs.flashbots.net/flashbots-mev-boost/relay)

[FlashbotsWinningBid] Flashbots Collective. Winning bid metric from bidtraces API. 2023. [collective.flashbots.net](https://collective.flashbots.net/t/winning-bid-metric-from-bidtraces-api/1275)

[Heimbach22] L. Heimbach, R. Wattenhofer. SoK: Preventing Transaction Reordering Manipulations in Decentralized Finance. 2022. [arXiv](https://arxiv.org/abs/2203.11520)

[Heimbach23] L. Heimbach, L. Kiffer, C. F. Torres, R. Wattenhofer. Ethereum's Proposer-Builder Separation: Promises and Realities. 2023. [arXiv](https://arxiv.org/abs/2305.19037)

[Heimbach26] L. Heimbach et al. No Place to Hide: An Analysis on Protected Order Flow Sandwich Attacks. 2026. [arXiv](https://arxiv.org/abs/2609.28115)

[Li23] Z. Li et al. Demystifying DeFi MEV Activities in Flashbots Bundle. 2023. [arXiv](https://arxiv.org/abs/2312.01091)

[Lido24] Lido research forum. DeFiPlaza exploit: request for comment. 2024. [research.lido.fi](https://research.lido.fi/t/defiplaza-exploit-request-for-comment/8241)

[Lyu22] X. Lyu et al. An Empirical Study on Ethereum Private Transactions and the Security Implications. 2022. [arXiv](https://arxiv.org/abs/2208.02858)

[Ma25] Z. Ma, M. Jiang, F. Luo, X. Luo, Y. Zhou. Surviving in Dark Forest: Towards Evading the Attacks from Front-Running Bots in Application Layer (EVScope). USENIX Security 2025. [usenix.org](https://www.usenix.org/conference/usenixsecurity25/presentation/ma-zuchao)

[Neuder23cancel] M. Neuder, T. Thiery, C. Hager. Bid cancellations considered harmful. 2023. [ethresear.ch](https://ethresear.ch/t/bid-cancellations-considered-harmful/15500)

[Neuder23opt] M. Neuder et al. Optimistic relays. [notes.ethereum.org](https://notes.ethereum.org/@mikeneuder/optimistic-v2)

[Oz23] B. Oz et al. Time Moves Faster When There is Nothing You Anticipate. 2023. [arXiv](https://arxiv.org/abs/2307.05814)

[Oz24] B. Oz, D. Sui, T. Thiery, F. Matthes. Who Wins Ethereum Block Building Auctions and Why? 2024. [arXiv](https://arxiv.org/abs/2407.13931)

[Piet22] J. Piet, J. Fairoze, N. Weaver. Extracting Godl [sic] from the Salt Mines: Ethereum Miners Extracting Value. 2022. [arXiv](https://arxiv.org/abs/2203.15930)

[Qin22] K. Qin, L. Zhou, A. Gervais. Quantifying Blockchain Extractable Value: How dark is the forest? IEEE S&P 2022. [arXiv](https://arxiv.org/abs/2101.05511)

[Qin23] K. Qin et al. The Blockchain Imitation Game (APE). USENIX Security 2023. [usenix.org](https://www.usenix.org/conference/usenixsecurity23/presentation/qin)

[Ren24] S. Ren et al. LookAhead: Preventing DeFi Attacks via Unveiling Adversarial Contracts. 2024. [arXiv](https://arxiv.org/abs/2401.07261)

[Rekt26] Rekt. Makina - Rekt. 2026. [rekt.news](https://rekt.news/makina-rekt)

[RelaySpecs] Flashbots. Relay API specification. [flashbots.github.io](https://flashbots.github.io/relay-specs/)

[Robinson20] D. Robinson, G. Konstantopoulos. Ethereum is a Dark Forest. Paradigm, 2020. [paradigm.xyz](https://www.paradigm.xyz/writing/ethereum-is-a-dark-forest)

[Samczsun20] samczsun. Escaping the Dark Forest. Paradigm, 2020. [paradigm.xyz](https://www.paradigm.xyz/writing/escaping-the-dark-forest)

[SEAL] Security Alliance. SEAL Whitehat Safe Harbor. [frameworks.securityalliance.org](https://frameworks.securityalliance.org/safe-harbor/overview/)

[Shou24] C. Shou et al. BACKRUNNER: Mitigating Smart Contract Attacks in the Real World. 2024. [arXiv](https://arxiv.org/abs/2409.06213)

[TheBlock23] V. Chawla. MEV bot runner 'c0ffeebabe.eth' returns $5.4 million amid Curve exploit. The Block, 2023. [theblock.co](https://www.theblock.co/post/242136/mev-bot-runner-c0ffeebabe-eth-returns-5-4-million-amid-curve-exploit)

[Torres21] C. F. Torres, R. Camino, R. State. Frontrunner Jones and the Raiders of the Dark Forest. USENIX Security 2021. [usenix.org](https://www.usenix.org/system/files/sec21-torres.pdf)

[UltraSoundDocs] ultra sound relay team. Relay docs: data API and bid adjustment. [github.com](https://github.com/ultrasoundmoney/relay-docs)

[Unchained23] S. Sriram. Curve exploit coverage quoting Eric Connor on returning funds. Unchained, 2023. [unchainedcrypto.com](https://unchainedcrypto.com/?p=13238)

[Wahrstatter23] A. Wahrstaetter et al. Time to Bribe: Measuring Block Construction Market. 2023. [arXiv](https://arxiv.org/abs/2305.16468)

[Weintraub22] B. Weintraub et al. A Flash(bot) in the Pan: Measuring Maximal Extractable Value in Private Pools. IMC 2022. [arXiv](https://arxiv.org/abs/2206.04185)

[Wen26] Y. Wen et al. EVAGE: Autonomous MEV Generation and Adaptation via Multi-Agent Harness. 2026. [arXiv](https://arxiv.org/abs/2609.27424)

[Worsley21] N. Worsley (experiment), CryptoNews. DeFi Sandwich Traders Get 'Salmonella'. 2021. [cryptonews.com](https://cryptonews.com/news/defi-sandwich-traders-get-salmonella-9627/) (search snippet only)

[Yang25] S. Yang, K. Nayak, F. Zhang. Decentralization of Ethereum's Builder Market. 2025. [arXiv](https://arxiv.org/abs/2405.01329)

[Zellic23] pepsipu. Your Sandwich Is My Lunch: How to Drain MEV Contracts V2. Zellic, 2023. [zellic.io](https://www.zellic.io/blog/your-sandwich-is-my-lunch-how-to-drain-mev-contracts-v2)

[Zhang23] Z. Zhang et al. Your Exploit is Mine: Instantly Synthesizing Counterattack Smart Contract (STING). USENIX Security 2023. [usenix.org](https://www.usenix.org/conference/usenixsecurity23/presentation/zhang-zhuo-exploit)

[Zhang23combat] W. Zhang et al. Combatting Front-Running in Smart Contracts. 2023. [arXiv](https://arxiv.org/abs/2212.12110)

[Zhou21] L. Zhou et al. On the Just-In-Time Discovery of Profit-Generating Transactions in DeFi Protocols (DeFiPoser). 2021. [arXiv](https://arxiv.org/abs/2103.02228)

## Appendix A: Transaction hash index

Short references in the text (first 8 hex digits) and the full transaction hashes. Each hash appears in the saved incident or race files under `incidents/` and `research/`; published responses are in `site/raw/`; full-cache references use `data/raw/`.

| Short | Full hash |
|---|---|
| `0x003b0037` | `0x003b00378ac52c10200d8fcac0e42138a34e46b9d7c3350ad3372ae0eb141df3` |
| `0x0430d5a2` | `0x0430d5a2dcfb0f9530fe1699e0e86a9526825da5e2072a15c4be734710f56cdb` |
| `0x04b166e7` | `0x04b166e7b4ab5105a8e9c85f08f6346de1c66368687215b0e0b58d6e5002bc32` |
| `0x074acda8` | `0x074acda86089731f37e42abda7f970c606509419e557f31d9c8f793dd9981b2d` |
| `0x0a7d69ab` | `0x0a7d69abe64d99c77741a54639057e077d096bc68cde094a1a05590557f76e56` |
| `0x0e7680b0` | `0x0e7680b06cb8a6f86c149d9ba90d98e3d334e7b072dde03909d43fcfd98a8705` |
| `0x15b47e2c` | `0x15b47e2c0daf723dec64c75b435079d3a1f8a6058b21b9a64dda4844e877a034` |
| `0x160c5950` | `0x160c5950a01b88953648ba90ec0a29b0c5383e055d35a7835d905c53a3dda01e` |
| `0x1911be70` | `0x1911be7020af964e35abfe5a94c9f2a232cc017532c1c14a1dea57c6ac011af3` |
| `0x19a02f97` | `0x19a02f97af7d8165a702c49a6919387bf14c5324853ebb97752084fc813688ec` |
| `0x1dc60f91` | `0x1dc60f917e4d841f281e827cf82f93c7355e08f5855e9ae5b0a1764b38ed4b87` |
| `0x1f1aba5b` | `0x1f1aba5bef04b7026ae3cb1cb77987071a8aff9592e785dd99860566ccad83d1` |
| `0x22efe474` | `0x22efe4743cdbd6650e745e3e6ef4f611aa316e81b5b88d5413b0cd19205ab060` |
| `0x26195700` | `0x2619570088683e6cc3a38d93c3d98899e5783864e15525d5f5810c11189ba6cb` |
| `0x273f8e55` | `0x273f8e55e6e6b7f07cc5834a6ebc5e831b498d33a95d402d1cced5472d3da08d` |
| `0x2e7dc8b2` | `0x2e7dc8b2fb7e25fd00ed9565dcc0ad4546363171d5e00f196d48103983ae477c` |
| `0x2e832f04` | `0x2e832f044b4a0a0b8d38166fe4d781ab330b05b9efa9e72a7a0895f1b984084b` |
| `0x2f2c3c1c` | `0x2f2c3c1c648f6ef0fc3600a91ad389daeb6c76602c4bf0100475696535b6f84f` |
| `0x3079ebb0` | `0x3079ebb01a1eedbf655d038a387b61476dfb2e687d2f21e8c48c8d8e80e0da70` |
| `0x35206537` | `0x352065378c4a41b77e5b6a1e5b5616cd2886c3e1a2c87ed3db8e5ddddc23823d` |
| `0x35a73969` | `0x35a73969f582872c25c96c48d8bb31c23eab8a49c19282c67509b96186734e60` |
| `0x395675b5` | `0x395675b56370a9f5fe8b32badfa80043f5291443bd6c8273900476880fb5221e` |
| `0x3aed40de` | `0x3aed40debf5ca27f53d2450b36b713d43272a40df60623572afaebd0d8fbe270` |
| `0x3d3e7cfe` | `0x3d3e7cfe2bc311c7b9c44c62c29224e4ad55e79e241086ca4689198921b7c427` |
| `0x3edd298a` | `0x3edd298ae34b4dbe5bde5f7f5115d10290cf2006cdcb63c6b626cc9529d21857` |
| `0x40be81f8` | `0x40be81f859227aa952e70fe1f5e8c84feed6aa3c2a4d6bf38125cd6bc222560a` |
| `0x43ff7e01` | `0x43ff7e01423044cfb501b4fe9ef1386725c0ddc117dadd6e6620cb68bdeaf4f9` |
| `0x487f7c96` | `0x487f7c96d538c32741e4eb4ec62cb8a2d8c207d707b1a7d10241373c72528d7b` |
| `0x4bc4ace3` | `0x4bc4ace313f2f5a411a5a560255ba0bba4f4913edb55ed882feaee84a3b1292e` |
| `0x4be393b9` | `0x4be393b9e3936383710c27dc422fb657aeeae266af67ea63ca6c08f062e40b5d` |
| `0x4f647c4d` | `0x4f647c4d74a86e5f3719b235e96f55000a04df1e07137eed8baef09dd0c2c074` |
| `0x50dc9c91` | `0x50dc9c9126519a70319cc312418488145bed4e2ef6e110eb864a97f5beaeca05` |
| `0x55b34cd6` | `0x55b34cd6e8da7e6cfafb91f746c1ae0425b97a29a54c61dbc40d69d0eb9d72fc` |
| `0x569733b8` | `0x569733b8016ef9418f0b6bde8c14224d9e759e79301499908ecbcd956a0651f5` |
| `0x57a98ef2` | `0x57a98ef275569be4727b2e4109e90aa083a875e2f56983275522a1b74d8130d5` |
| `0x5d4e4fa9` | `0x5d4e4fa957af5cbb1c10bae726f71192fe876a8db719ed166edd8e899ce92777` |
| `0x65670d8e` | `0x65670d8e4f08d56971d476b0c68ca745b0749ec7f79f9b79d993ef47cc91b9c6` |
| `0x6e743db0` | `0x6e743db045f3738b24c6dedc90bae62c6429f2f7fe8a086394b05a68b8f5867a` |
| `0x6ed07db1` | `0x6ed07db1a9fe5c0794d44cd36081d6a6df103fab868cdd75d581e3bd23bc9742` |
| `0x6f7d546a` | `0x6f7d546a4e86baa276141c94f58bef2365fdfb0523478d2c4f13398f49616342` |
| `0x725db76c` | `0x725db76cf4bf3bdc72be4f755ed72df4adbc8e4e803c044617cc11e34907ccdc` |
| `0x756c6805` | `0x756c68055af7a0630aa0b56891ba4de14c56c39cbebe99e47eeb4728f4d6ad14` |
| `0x75d4765d` | `0x75d4765dd704d82f0bf539da88aff2568da38697f153b14d285abc8749da683f` |
| `0x77bb83dd` | `0x77bb83dd9b25a0af12c0092993ddf1a2f54b77fbcd1dbf1bf33a965ec707268b` |
| `0x7b6eb36a` | `0x7b6eb36aacdc210a35818a7a5a44ad9aea3e18b2bdc82db300b7b89c6c504f64` |
| `0x85034238` | `0x850342386d7446e3ce479ecc246e843961a46fa6540d279a5ef602d14deb547e` |
| `0x855dd3b1` | `0x855dd3b1194e3b889f4667b6a0996220e350e034d35d3eab29b4f23bc205767e` |
| `0x8dfb264c` | `0x8dfb264ca06fe36347ae806fe7249dd8e7a4d202595ed4a59e6bf8b5adb65345` |
| `0x8e7b711e` | `0x8e7b711ebca73ba583478cd7a55b0496fdfd9222f8b7d0245baee51816aee155` |
| `0x8f029510` | `0x8f029510dbcc4885d5f5242f3583f4d31f9134d9eddaa30a1afa353f6bd4f7b0` |
| `0x95827369` | `0x95827369a933e695832dd73b35097c89d94663722e0589e98f00053af3ed132c` |
| `0x9b9a6dd0` | `0x9b9a6dd05526a8a4b40e5e1a74a25df6ecccae6ee7bf045911ad89a1dd3f0814` |
| `0x9f43b61d` | `0x9f43b61d85af2694976554ad75b295df45ff73f736bda66b8850bcee7c7aa95c` |
| `0xa1b1ea50` | `0xa1b1ea5033611603f6e8e5ce5d566ad6b9ad1cd69476e37091c0d90c56c04f90` |
| `0xa245deda` | `0xa245deda8553c6e4c575baff9b50ef35abf4c8f990f8f36897696f896f240e3a` |
| `0xa645a615` | `0xa645a61524e1cd75b8cd4db956253a804a023ff766d60245d70462ed41b6a278` |
| `0xa84aa065` | `0xa84aa065ce61dbb1eb50ab6ae67fc31a9da50dd2c74eefd561661bfce2f1620c` |
| `0xa8d03049` | `0xa8d030494607e16b06dd0c7e97da2b78ebc5a072a8176b19ca57f17044c1a211` |
| `0xad945d38` | `0xad945d38ec5dc00f0310b6f22d19da3b8b5063b9f3e7efb38ca6a5cbc6385a39` |
| `0xb2dfea6d` | `0xb2dfea6de47e35cc8e660489afb7380a1fa0b978a59c81685d94ff0ca7ce9dfc` |
| `0xb5d91f1e` | `0xb5d91f1e0afc96a52f8c6c28eae405eda7fcc5d34d6d03bdd8b16bd58089e939` |
| `0xb6748899` | `0xb6748899565cff6c01190f507ea83a7d2efdfba13e119fd0f487f74ce899d25f` |
| `0xb676d789` | `0xb676d789bb8b66a08105c844a49c2bcffb400e5c1cfabd4bc30cca4bff3c9801` |
| `0xb7675412` | `0xb76754124fdde090f25129105ed2907e3c62e0db87ecb8ffcefcb1dede0954fd` |
| `0xb7c3f85a` | `0xb7c3f85abd0b9ede7b64868eeb6778ea4731adb1d49f8640b7e7234e470e96c1` |
| `0xb8f57cf8` | `0xb8f57cf82b7057d9d03f1500e3f0ce46980388c3b13ff317f1c617d932313386` |
| `0xbce5b854` | `0xbce5b8548db486c561948e8a177c8ccaa72810f972cee3909ea50af015a60ad8` |
| `0xbd43d2de` | `0xbd43d2dec15cbb6099b6290d4d2fb4d182b59cbb8d42b52b6003d0a64ece0c7c` |
| `0xbf7e5182` | `0xbf7e5182694d0703051951520c176135dac63d772b328468ce783b37dd7a8a7c` |
| `0xc310a0af` | `0xc310a0affe2169d1f6feec1c63dbc7f7c62a887fa48795d327d4d2da2d6b111d` |
| `0xc52cce67` | `0xc52cce67226ca6c9fd85b6081d532171623a4ba2cb78f5f69811e38f82c22f2b` |
| `0xc78fb8cd` | `0xc78fb8cd5f7813a3d8abebdc5351aafd5011e8e13c5f6740837eeef9308d1faf` |
| `0xc8875004` | `0xc8875004a36cb97a40b9d9c8d1a56cf0d6042aec5eb330d17de7d70c8e13d7b4` |
| `0xc93eb238` | `0xc93eb238ff42632525e990119d3edc7775299a70b56e54d83ec4f53736400964` |
| `0xcaa24228` | `0xcaa2422853fd14f5645d762729b6edc41ebdac2dce988123d1b91d98eab37e0f` |
| `0xccdc1855` | `0xccdc1855f4028bf110d98842c1b947606918b958d950fbd6f132b37e37ca4337` |
| `0xcd615986` | `0xcd6159860783d8d481cc4bf4dceddc88acdca6bb08f6445525b2904cfd75b1da` |
| `0xcd99fadd` | `0xcd99fadd7e28a42a063e07d9d86f67c88e10a7afe5921bd28cd1124924ae2052` |
| `0xd9bc8368` | `0xd9bc83688e8eddde39bd9073c363665b1419d475dd4498e81b52cce41d7c76b3` |
| `0xe00b0998` | `0xe00b0998d71b0e657379be196babd1637a653c100e8162853ca6616c3970790d` |
| `0xe2eb61b1` | `0xe2eb61b1ff11e447b791e030039ce89ae294423da1622d0be8c7ec3b2ff1a22a` |
| `0xecdd111a` | `0xecdd111a60debfadc6533de30fb7f55dc5ceed01dfadd30e4a7ebdb416d2f6b6` |
| `0xf0464b01` | `0xf0464b01d962f714eee9d4392b2494524d0e10ce3eb3723873afd1346b8b06e4` |
| `0xf57b7dbf` | `0xf57b7dbfdb24aa811012bbdc4e70c1027c7b2cca6b5d776881a44f488afc6bae` |
| `0xfbf6d830` | `0xfbf6d8305660a2cb2282b94299c51acfc51860a39b1f63a758615492ba40109d` |
| `0xfd6f57ec` | `0xfd6f57ec11b40faea66f42b48e044c173408b0570e706f5ad6286177808da7cc` |

## Appendix B: Public sources by incident (cited as [S:name])

- [S:dodo] [halborn.com](https://halborn.com/explained-the-dodo-dex-hack-march-2021) ; [chaincatcher.com](https://www.chaincatcher.com/en/article/2060103) ; [theblock.co](https://www.theblock.co/post/97734/dodo-dex-exploit-bug-attack)
- [S:transit] [blocksec.com](https://blocksec.com/blog/how-we-recover-the-stolen-funds-for-transitswap-and-babyswap) ; [transaction 0x57a98ef2](https://etherscan.io/tx/0x57a98ef275569be4727b2e4109e90aa083a875e2f56983275522a1b74d8130d5) ; [rekt.news](https://rekt.news/transit-swap-rekt/) ; [web3isgoinggreat.com](https://web3isgoinggreat.com/single/transit-swap-hacked-for-21-million-hacker-returns-large-portion) ; [DeFiHackLabs source](https://raw.githubusercontent.com/SunWeb3Sec/DeFiHackLabs/main/past/2022/README.md)
- [S:earningfarm] [DeFiHackLabs source](https://raw.githubusercontent.com/SunWeb3Sec/DeFiHackLabs/main/src/test/2022-10/EFLeverVault_exp.sol) ; [DeFiHackLabs source](https://raw.githubusercontent.com/SunWeb3Sec/DeFiHackLabs/main/past/2022/README.md) ; [twitter.com](https://twitter.com/MevRefund/status/1580917351217627136) ; [twitter.com](https://twitter.com/danielvf/status/1580936010556661761) ; [web3isgoinggreat.com](https://web3isgoinggreat.com/single/earningfarm-exploited-for-971000)
- [S:shoco] [github.com](https://github.com/SunWeb3Sec/DeFiHackLabs/blob/main/src/test/2023-01/SHOCO_exp.sol) ; [transaction 0x2e832f04](https://etherscan.io/tx/0x2e832f044b4a0a0b8d38166fe4d781ab330b05b9efa9e72a7a0895f1b984084b) ; [transaction 0x2f2c3c1c](https://etherscan.io/tx/0x2f2c3c1c648f6ef0fc3600a91ad389daeb6c76602c4bf0100475696535b6f84f) ; [Flashbots relay bids](https://boost-relay.flashbots.net/relay/v1/data/bidtraces/builder_blocks_received?block_number=16440979)
- [S:euler] [transaction 0xc310a0af](https://etherscan.io/tx/0xc310a0affe2169d1f6feec1c63dbc7f7c62a887fa48795d327d4d2da2d6b111d) ; [address 0x5F259D0b](https://etherscan.io/address/0x5F259D0b76665c337c6104145894F4D1D2758B8c) ; [certik.com](https://www.certik.com/resources/blog/4iSrYY6HoaYxk1aKyjFb5v-euler-finance-incident-analysis) ; [eigenphi.substack.com](https://eigenphi.substack.com/p/200-million-heist-unmasked-unraveling) ; [Flashbots relay bids](https://boost-relay.flashbots.net/relay/v1/data/bidtraces/builder_blocks_received?block_number=16817996)
- [S:curve] [curve.substack.com](https://curve.substack.com/p/july-31-2023-snekbit) ; [metronomedao.medium.com](https://metronomedao.medium.com/vyper-curve-exploit-post-mortem-6a42d6d9fa07) ; [DeFiHackLabs source](https://raw.githubusercontent.com/SunWeb3Sec/DeFiHackLabs/main/past/2023/README.md) ; [theblock.co](https://www.theblock.co/post/242136/mev-bot-runner-c0ffeebabe-eth-returns-5-4-million-amid-curve-exploit)
- [S:sushi] [blocksec.com](https://blocksec.com/blog/8-sushi-swap-incident-a-clumsy-rescue-attempt-leads-to-a-series-of-copycat-attacks) ; [blockworks.com](https://blockworks.com/news/sushiswap-3-million-hack) ; [forklog.com](https://forklog.com/en/news/blocksec-recovers-100-eth-stolen-from-sushiswap-hacker) ; [crypto.news](https://crypto.news/exclusive-hacker-behind-sushiswaps-preemptive-sifu-hack-explained-how-it-was-done/) ; [DeFiHackLabs source](https://raw.githubusercontent.com/SunWeb3Sec/DeFiHackLabs/main/src/test/2023-04/Sushi_Router_exp.sol)
- [S:time] [github.com](https://github.com/SunWeb3Sec/DeFiHackLabs/blob/main/src/test/2023-12/TIME_exp.sol) ; [certik.com](https://www.certik.com/blog/time) ; [blog.openzeppelin.com](https://blog.openzeppelin.com/arbitrary-address-spoofing-vulnerability-erc2771context-multicall-public-disclosure) ; [beosin.com](https://beosin.com/resources/unveiling-the-ethereum-time-contract-hack-exploiting-erc2771-protocol-vulnerabilities-for%C2%A0profit) ; [explorer.phalcon.xyz](https://explorer.phalcon.xyz/tx/eth/0xecdd111a60debfadc6533de30fb7f55dc5ceed01dfadd30e4a7ebdb416d2f6b6)
- [S:blueberry] [medium.com](https://medium.com/@blueberryprotocol/2-22-24-exploit-post-mortem-6f6be7c1dcc3) ; [medium.com](https://medium.com/@OKLinkData/oklink-analysis-blueberry-protocol-foundation-c47513a05db4) ; [cointelegraph.com](https://cointelegraph.com/news/defi-protocol-blueberry-pauses-after-exploit) ; [x.com](https://x.com/blueberryFDN/status/1760872935982879030) ; [web3isgoinggreat.com](https://www.web3isgoinggreat.com/single/blueberry-protocol-narrowly-avoids-1-3-million-hack)
- [S:paraswap] [veloradex.medium.com](https://veloradex.medium.com/post-mortem-augustus-v6-vulnerability-of-march-20th-2024-5df663a4bf01) ; [medium.com](https://medium.com/neptune-mutual/analysis-of-the-paraswap-exploit-1f97c604b4fe) ; [github.com](https://github.com/SunWeb3Sec/DeFiHackLabs/blob/main/src/test/2024-03/Paraswap_exp.sol) ; [cointelegraph.com](https://cointelegraph.com/news/paraswap-hack-augustus-v6-contract-vulnerability) ; [x.com](https://x.com/VeloraDEX/status/1770313086072742263)
- [S:defiplaza] [defiplaza.net](https://defiplaza.net/blog/post-mortem-of-defiplaza-ethereum-exploit/) ; [research.lido.fi](https://research.lido.fi/t/defiplaza-exploit-request-for-comment/8241) ; [fairyproof.substack.com](https://fairyproof.substack.com/p/weekly-blockchain-security-watch-78c)
- [S:ronin] [theblock.co](https://www.theblock.co/post/309707/ronin-bridge-pauses) ; [bleepingcomputer.com](https://www.bleepingcomputer.com/news/security/ronin-network-hacked-12-million-returned-by-white-hat-hackers/) ; [cointelegraph.com](https://cointelegraph.com/news/ronin-white-hat-attacker-returns-10-million-eth-apparent-accidental-front-run) ; [eigenphi.substack.com](https://eigenphi.substack.com/p/mev-maestro-yoink-netting-265m-on-59-blocks-in-aug)
- [S:alkimiya] [DeFiHackLabs source](https://raw.githubusercontent.com/SunWeb3Sec/DeFiHackLabs/main/src/test/2025-03/Alkimiya_io_exp.sol) ; [blog.verichains.io](https://blog.verichains.io/p/alkimiya-hack-analysis) ; [olympix.substack.com](https://olympix.substack.com/p/96k-could-have-been-saved-if-only) ; [reports.zellic.io](https://reports.zellic.io/publications/alkimiya/findings/critical-silicapools-fake-pool-could-drain-all-the-pools-tokens)
- [S:makina] [makinafi.substack.com](https://makinafi.substack.com/p/post-mortem-january-20th-2026-incident) ; [x.com](https://x.com/makinafi/status/2014349539847573565) ; [x.com](https://x.com/PeckShieldAlert/status/2013468943193645085) ; [decrypt.co](https://decrypt.co/355132/ethereum-defi-platform-makina-hit-by-flash-loan-exploit-loses-4m-in-eth) ; [quillaudits.com](https://www.quillaudits.com/blog/hack-analysis/makina-4m-hack-explained) ; [ambcrypto.com](https://ambcrypto.com/makina-recovers-majority-of-funds-from-exploit-as-whitehat-process-returns-920-eth/) ; [rekt.news](https://rekt.news/makina-rekt)
- [S:kelp] [thedefiant.io](https://thedefiant.io/news/hacks/mev-bot-front-runs-7-8-million-rseth-exploit-on-ethereum) ; [cointelegraph.com](https://cointelegraph.com/news/mev-bot-intercepts-77m-in-rseth-from-ethereum-wallet-exploit) ; [forklog.com](https://forklog.com/en/mev-bot-intercepts-7-73-million-withdrawal-from-safe-wallet/) ; [unchainedcrypto.com](https://unchainedcrypto.com/a-bot-robbed-the-hacker-who-drained-7-8-million-in-rseth-from-a-safe-wallet/) ; [blockfence.io](https://blockfence.io/mev-bot-takes-7-8m-from-rseth-exploit/) ; [shattered.io](https://shattered.io/mev-bot-yoink-front-runs-7-8-million-ethereum-hack-2026/)
- [S:uncx] [cryptobriefing.com](https://cryptobriefing.com/uncx-network-vesting-pool-exploited/) ; [phemex.com](https://phemex.com/news/article/uncx-discloses-smart-token-vesting-v2-crosschain-exploit-worth-807k-100239) ; [gncrypto.news](https://www.gncrypto.news/news/uncx-vesting-v2-exploit-drains-1-49-million-across-4-chains/) ; [odaily.news](https://www.odaily.news/en/newsflash/525326) ; [thebreachledger.substack.com](https://thebreachledger.substack.com/p/patterns-that-repeated-across-chains)
- [S:bifi] No public postmortem was located; evidence is on-chain only (`incidents/bifi-2026/`).
- [S:saddle] [blocksec.com](https://blocksec.com/blog/blocked-saddle-finance-attack-industry-s-first-influential-blocking-to-rescue-3-800-000) ; [rekt.news](https://rekt.news/saddle-finance-rekt2/) ; [theblock.co](https://www.theblock.co/news/regulation/2022-04-30-stablecoin-dex-saddle-finance-hacked-for-10-million-144491)
- [S:securedfinance] [kucoin.com](https://www.kucoin.com/news/flash/defi-lending-market-secured-finance-hit-by-attack-losing-104-000) ; [kucoin.com](https://www.kucoin.com/news/flash/secured-fi-lending-market-hacked-losing-104-000) ; [techflowpost.com](https://www.techflowpost.com/en-US/newsletter/135195)
- [S:balancer] [forum.balancer.fi](https://forum.balancer.fi/t/bip-892-distribution-of-rescued-funds-from-balancer-v2-november-3rd-2025-attacks/6883) ; [theblock.co](https://www.theblock.co/post/380751/balancer-recovered-funds-distribution) ; [x.com](https://x.com/Balancer/status/1990856260988670132) ; [dlnews.com](https://www.dlnews.com/articles/defi/stakewise-uses-loophole-to-take-back-funds-from-balancer-hacker/) ; [ambcrypto.com](https://ambcrypto.com/balancer-recovers-45-7m-after-121m-hack-but-bal-stays-down-24/)

Mempool-dumpster files, relay responses and permitted traces in the public subset are indexed by `site/raw/MANIFEST.json`. Source paths under `data/raw/` refer to the full research cache; per-race files are `incidents/<slug>/race_<block>.json`.

## Appendix C: Reproduction

The published data and cited source subset support inspection of the reported results. `site/raw/MANIFEST.json` records the published files and any reductions or link stubs. References to the full research cache may require a fresh retrieval.

Rebuilding the research pipeline requires Python 3.12, the relevant dependencies and a full cache or a new fetch. `scripts/blockrace.py BLOCK --focus TX... --watch ADDR... --slug SLUG` fetches and writes a race reconstruction. `scripts/relays.py {probe,coverage,retention,fetch,names}` and `scripts/mempool.py {index,fetch,lookup}` query external APIs and populate `data/raw/`; they require network access. The published `site/raw/` subset alone is insufficient to run `scripts/evolution.py relabel`, which also needs the unpublished working cache. `scripts/dataset/build_incidents.py --no-writeback` inspects the committed dataset and checks its raw references without rewriting it. A full dataset rebuild writes derived files and requires the research inputs; use a disposable copy for that workflow. `scripts/bot_re/` contains local-fork verification and disassembly tools with additional tool and archive-RPC requirements. Relay retention limits can prevent a fresh fetch from reproducing an old auction.
