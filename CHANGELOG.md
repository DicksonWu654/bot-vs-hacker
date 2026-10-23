# Changelog

Dates are the data snapshot date. Corrections are welcome: see the README, "Report a correction".

## 2026-10-21: first public release

Data snapshot through 21 October 2026.

What is in it

- The paper, the interactive site with a replay for every race, the master dataset, the per-incident race files, the longitudinal study and the tooling that produced them. Headline figures are in `data/headline_stats.json`; each links to the saved raw responses in `site/raw/`.
- The paper is also served as `site/paper.html`, next to the interactive site.

How the findings changed while the work was checked

- **Attacker or bot (evolution study, v1 to v2).** The first version of the longitudinal study took the transaction that DeFiHackLabs lists as "the attack" and read its sender as the attacker. A sender-class pass excluded 34 of 315 rows: 28 bot-only, one whitehat and five unknown-sender or non-attack rows. In 35 rows the first listed transaction was non-attacker-sent; one mixed row remains and is measured using its attacker transaction. Makina's 1,299 ETH, DeFi Plaza's 66 ETH and Alkimiya's 51 ETH were bot payments to builders, not attacker bribes. With bots separated, the share of exploits with a direct coinbase payment fell from 11.2% to 7.2% in the Merge-to-2023 era and from 16.3% to 8.4% in 2024-26, and the median transaction index moved from 8.5 to 16.5. Bot-side figures are now reported separately, and the v1 files remain in `data/evolution/` for comparison.
- **One verdict rule for deploy-window copies.** BiFi was first labelled `related-not-frontrun` while Makina, the same pattern, was labelled `confirmed-onchain`. Both now follow one rule: when the attacker deploys a purpose-built contract, its call never lands, and the next block's bot transaction makes the victim calls that a replay of the attacker's deployed code produces, the race is a confirmed deploy-window copy (`data/harmonize_log.json`, `scripts/dataset/harmonize_rules.py`).
- **Ronin 2024 reclassified.** Three bots copied a user's withdrawal that exposed a bug; there was no hostile attacker. It is recorded as `beat-whitehat-or-user` and does not count toward the headline.
- **Return denominators.** Returns are reported against three explicit denominators: the gross taken from the victim, what the bot kept after paying the builder, and the victim's loss. Part of some returns was passed on by builders and is separated from returns made by the bot. A Paraswap partial return and a Blueberry builder residue were found in this step.
- **Off-slot bids.** Relay bid rows that belong to another slot than the race's slot were removed from the race files (`scripts/fix_offslot_bids.py`), and files from relays that no longer answer were dropped. The current raw-link audit is run over the built site before export.
- **Claim-by-claim check of the paper.** 98 claims were checked against the data and 45 were corrected, among them Paraswap and DeFi Plaza returns, the Transit Swap timing and the 0xa57 lineage. The 0xa57 family is one operator: the DODO 2021 bot and the Earning.Farm 2022 bot share contracts and funding.

- **Launch review.** Euler is retained at medium strength and excluded from the headline (19 rows / 15 incidents). Known-zero returns are included in the pooled denominator (14 priced headline rows, three known zeros). Return statuses use the agreed/offered-bounty rule; Punk is partial, Transit and Neemo returned, Unizen partial (incident-wide). Builder payment is presented before and after refunds.

Scope decisions

- The operator behind c0ffeebabe.eth is described through public actions only: which transaction, in which block, what it paid the builder and what was returned. Its transactions appear in the published traces as block-level facts only.
- Pre-August-2023 races carry `in-block-only` evidence because no mempool archive exists for them.
- The anonymous senders that DeFiHackLabs lists as attackers were profiled and are recorded as searchers, a drain-and-return bot and a serial exploiter, not as races (`research/anon-bots/`).

Data handling

- Third-party contact details in decoded on-chain messages (email addresses, chat handles and links) were redacted. Automated pattern scans cover the shipped files and can miss things; tell us if you find one.
- Saved raw responses in `site/raw/` are unmodified except for the c0ffeebabe.eth reductions above, contact/contributor redactions and third-party web pages replaced by link-only stubs (see MANIFEST notes).

Known gaps

- The full raw cache (about 9 GB) is not published; `site/raw/` holds the files the site cites. Scripts re-fetch the rest.
- Compiled with a swarm of AI agents, so there will be mistakes; every number links its saved source; corrections welcome.
