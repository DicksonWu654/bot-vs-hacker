"""Single source of truth for the incident dataset harmonization decisions (verdict, race_type, headline).

ONE verdict rule (applied to every row, see data/harmonize_log.json for each change):
  confirmed-onchain    on-chain evidence that the bot tx replays/adapts another actor's tx, or uses that actor's own on-chain setup
                       (deployed contract / prepare()), AND the bot is first (earlier block; same block earlier index; or before
                       the other actor's call ever landed). A replay of the attacker's DEPLOYED code that reproduces the bot's
                       victim calls is one evidence method in deploy-window cases. The c0ffeebabe.eth rows publish transaction ordering, funds and statements only.
  related-not-frontrun bot tx is related to the incident but is not first: post-failure replay/rescue, late copy, or the bot was
                       itself the first exploiter (no other actor's tx to beat).
  rejected             sub-race where no racer exists or the claim fails.
  reported             postmortem/press claim only, not verified on-chain.
Headline ("the bot beat the hacker") = verdict confirmed-onchain AND race_type in {beat-pending-attack, deploy-window-copy}, excluding Euler because operator identity is unresolved.
`no-race` is an added race_type value used only for rejected sub-races where nobody raced the attacker.
"""

HEADLINE_TYPES = {"beat-pending-attack", "deploy-window-copy"}

# (slug, sub) -> dict(verdict, race_type, why)
RULES = {
    ("alkimiya-2025", None): dict(verdict="confirmed-onchain", race_type="beat-pending-attack",
        why="Yoink landed at idx 0 of 22146340 with the attacker's 7 SilicaPools calls (+ the attacker's own index contract); the attacker's tx landed one block later and reverted."),
    ("balancer-2025", None): dict(verdict="related-not-frontrun", race_type="post-failure-replay",
        why="Every replay (Bitfinding whitehat 23717398; copiers) landed AFTER the attacker's tx 23717397 on the same pool: post-inclusion rescue of residual balances, not pre-emption."),
    ("bifi-2026", None): dict(verdict="confirmed-onchain", race_type="deploy-window-copy",
        why=('The attacker deployed a purpose-built contract in block 26210255 and never called it. The next block contains c0ffeebabe.eth at position 1, with the market funds removed and 0.9868 ETH paid to the builder. Classification retains the recorded deploy-window result; only transaction, block, position and funds are published.')),
    ("blueberry-2024", None): dict(verdict="confirmed-onchain", race_type="beat-pending-attack",
        why='c0ffeebabe.eth landed at position 0 of block 19287289. The attacker transaction was public from 02:22:09.219 UTC, landed in block 19287290 and received nothing.'),
    ("curve-vyper-2023", "pETH"): dict(verdict="confirmed-onchain", race_type="beat-pending-attack",
        why="0x6ec21d18 at idx 0 of 17806056 ran a byte-copy (20 bytes differ) of the attacker's CREATE initcode; the real attacker's tx at idx 91 reverted."),
    ("curve-vyper-2023", "msETH"): dict(verdict="confirmed-onchain", race_type="beat-pending-attack",
        why="c0ffeebabe idx 0 of 17806550 lands before that actor's contract deploy (idx 10, same block); the attacker's attack call two blocks later found the pool empty (top-level success, net zero)."),
    ("curve-vyper-2023", "CRV-ETH-wave2"): dict(verdict="confirmed-onchain", race_type="beat-pending-attack",
        why="c0ffeebabe idx 7 of 17808683 lands before that actor's contract deploy (idx 13, same block); go() (17808686) reverted at the exchange. Curve's deployer wrote on-chain that the front-run tx was a hack of the CRV/ETH pool."),
    ("curve-vyper-2023", "alETH"): dict(verdict="rejected", race_type="no-race",
        why="No racer in the alETH window; sub-race rejected."),
    ("curve-vyper-2023", "CRV-ETH-wave1"): dict(verdict="rejected", race_type="no-race",
        why="No racer in CRV/ETH phase 1; sub-race rejected."),
    ("defiplaza-2024", None): dict(verdict="confirmed-onchain", race_type="beat-pending-attack",
        why="Yoink idx 0 of 20240539 replays the attacker's 25 DeFi Plaza calls byte for byte while the attacker's still-pending run() landed in 20240540 and reverted."),
    ("dodo-v2-2021", None): dict(verdict="confirmed-onchain", race_type="beat-pending-attack",
        why="Antelope's init() calldata is byte-identical to the attacker's; bot idx 4 (243 gwei) vs attacker idx 176 (132 gwei) in 12000022; the attacker's tx reverted."),
    ("earningfarm-2022", None): dict(verdict="confirmed-onchain", race_type="beat-pending-attack",
        why="Bot idx 0 of 15746200 makes byte-identical flashLoan/deposit calldata to the attacker's idx 7 in the same block; the attacker's tx reverted."),
    ("euler-copybot-2023", None): dict(verdict="confirmed-onchain", race_type="deploy-window-copy",
        why="The copier deployed a bytecode copy (4x20 bytes differ) one block after the attacker's deploy and ran the DAI-market entry point 17 blocks before the hacker's first call; it captured nothing (proceeds went to the hard-coded attacker wallet)."),
    ("kelp-rseth-2026", None): dict(verdict="confirmed-onchain", race_type="deploy-window-copy",
        why="Yoink called the attacker's own prepared executor one block after prepare(); eth_call shows it reverts before prepare() and succeeds after; the attacker's finishing tx never landed."),
    ("makina-2026", None): dict(verdict="confirmed-onchain", race_type="deploy-window-copy",
        why="Searcher tx at idx 0 of the block after the attacker's contract deploy; local replay of the attacker's deployed F1() matches the bot's protocol call sequence 98.6%; the attacker's call never landed."),
    ("paraswap-2024", None): dict(verdict="related-not-frontrun", race_type="bot-was-first-exploiter",
        why="Yoink's tx is the first call of this kind on chain (trace_filter over 55k blocks); no hacker tx exists to beat."),
    ("ronin-2024", "eth-leg"): dict(verdict="confirmed-onchain", race_type="beat-whitehat-or-user",
        why="Bot copied a legitimate user's pending withdrawal (2 of 76 calldata words changed) and landed first; there is no hostile attacker (bots were the exploiters, then returned)."),
    ("ronin-2024", "racer3"): dict(verdict="confirmed-onchain", race_type="beat-whitehat-or-user",
        why="Bot copied a user's pending withdrawal (1 word changed) and landed first; no hostile attacker."),
    ("ronin-2024", "yoink-usdc"): dict(verdict="confirmed-onchain", race_type="beat-whitehat-or-user",
        why="Yoink copied a user's pending USDC withdrawal and landed first via its builder; no hostile attacker."),
    ("saddle-2022", None): dict(verdict="related-not-frontrun", race_type="post-failure-replay",
        why="BlockSec's rescue replayed the attacker's reverted attempt 2 two blocks AFTER it was mined; no attacker tx was pending at 14684434."),
    ("securedfinance-2026", None): dict(verdict="related-not-frontrun", race_type="post-failure-replay",
        why="Bot completed the attack 4 blocks (48 s) after the attacker's public tx was mined and had failed out of gas."),
    ("shoco-2023", None): dict(verdict="confirmed-onchain", race_type="beat-pending-attack",
        why="Bot idx 0 vs attacker idx 15 in the same block; the same victim calls adapted (not byte-copied); bot gain equals the attacker's counterfactual gain to the wei; the attacker's tx reverted."),
    ("sushi-rp2-2023", None): dict(verdict="confirmed-onchain", race_type="beat-whitehat-or-user",
        why="Yoink's pull in 17007838 pre-empted white hat Trust's still-pending rescue (max fee below that block's base fee); route bytes identical except the fake-pool address. There is no hostile attacker."),
    ("time-2023", None): dict(verdict="related-not-frontrun", race_type="bot-was-first-exploiter",
        why="The tx called 'the attack' is Yoink's own; no separate attacker tx exists to diff against."),
    ("transitswap-2022", None): dict(verdict="confirmed-onchain", race_type="beat-pending-attack",
        why="Yoink idx 24 (3.000000002 gwei) replays the attacker's last pending tx (idx 43, reverted) with 21/21 router calls identical bar the recipient. It did not front-run the attacker's 8 earlier successful txs."),
    ("uncx-2026", "yoink-X"): dict(verdict="confirmed-onchain", race_type="beat-pending-attack",
        why="Yoink idx 0 of 26191920 makes the same 26 X-token calls as the attacker, whose identical call set landed one block later and reverted."),
    ("uncx-2026", "zc-copiers"): dict(verdict="related-not-frontrun", race_type="late-copy",
        why="ZC copiers (incl. c0ffeebabe at 26191995) landed 248 blocks after the attacker's ZC drain at 26191745."),
}

# Headline caveats surfaced next to the flag
HEADLINE_NOTES = {
    ("euler-copybot-2023", None): "Copy-of-contract: the copier captured nothing (proceeds went to the attacker's hard-coded wallet); the hacker's own DAI-market call never ran.",
    ("transitswap-2022", None): "Front-ran only the attacker's last (9th) tx; the 8 earlier successful txs were not front-run.",
    ("shoco-2023", None): "Calls adapted rather than copied; whether the bot saw the pending tx or the deployed contract is unknowable (in-block evidence only).",
    ("bifi-2026", None): 'Deploy-window classification from transaction ordering and funds; the attacker contract was never called.',
    ("makina-2026", None): "Deploy-window copy; replay evidence is a deployed-code match + local-fork simulation (the attacker's call never landed).",
    ("kelp-rseth-2026", None): "Used the attacker's own prepared contract; ordering vs the attacker's finishing tx is inferred (that tx was private and never mined).",
    ("alkimiya-2025", None): "How Yoink saw the attacker's tx is unknown (absent from the mempool archive).",
}

# Evidence strength of the replay/ordering claim (high = call-for-call/byte-level match on mainnet traces or bytecode, ordering shown on chain;
# medium = adapted calls or local-fork simulation only, or ordering inferred; n/a = not a replay claim)
STRENGTH = {
    ("alkimiya-2025", None): ("high", "call-for-call match of 8-call script vs attacker's call tree + attacker-state counterfactual; how Yoink saw the tx unknown"),
    ("balancer-2025", None): ("high", "99.7% identical creation input; but landing order is AFTER the attacker"),
    ("bifi-2026", None): ("medium", 'Transaction ordering and market funds support the recorded deploy-window classification; no call-level comparison is published.'),
    ("blueberry-2024", None): ("high", 'The attacker transaction was public with a measured first-seen time; block positions and funds establish the ordering.'),
    ("curve-vyper-2023", "pETH"): ("high", "bot's in-tx CREATE initcode equals the attacker's deploy initcode except 20 bytes"),
    ("curve-vyper-2023", "msETH"): ("medium", "bot landed before the later actor's deploy; the later call found the pool empty"),
    ("curve-vyper-2023", "CRV-ETH-wave2"): ("medium", "Block positions, funds and the Curve deployer's on-chain refund request."),
    ("curve-vyper-2023", "alETH"): ("n/a", "no racer"),
    ("curve-vyper-2023", "CRV-ETH-wave1"): ("n/a", "no racer"),
    ("defiplaza-2024", None): ("high", "25/25 state-changing calls byte-identical to a fork replay of the attacker's deploy+run; attacker deploy first seen public"),
    ("dodo-v2-2021", None): ("high", "init() calldata byte-identical; in-block evidence only"),
    ("earningfarm-2022", None): ("high", "flashLoan/deposit calldata byte-identical, same block; phase C: replay of the attacker's reverted tx on the pre-bot state pays the same 480.108 ETH the bot took"),
    ("euler-copybot-2023", None): ("medium", "The copier may be the attacker’s own second account; its own on-chain message is the only bot attribution"),
    ("kelp-rseth-2026", None): ("medium", "bot called the attacker's own prepared contract; eth_call shows revert before prepare() and success after; attacker's finishing tx was private and never mined so ordering is inferred"),
    ("makina-2026", None): ("high", "77% of the bot's non-zero calldata bytes appear in the attacker's runtime; fork replay of attacker F1() matches 98.6% of protocol calls"),
    ("paraswap-2024", None): ("n/a", "no other actor"),
    ("ronin-2024", "eth-leg"): ("high", "2 of 76 calldata words changed vs the user's pending tx"),
    ("ronin-2024", "racer3"): ("high", "1 calldata word changed vs the user's tx"),
    ("ronin-2024", "yoink-usdc"): ("high", "calldata diff vs the user's pending tx, user tx first seen public"),
    ("saddle-2022", None): ("high", "frame-for-frame identical 403-frame call tree; but landed after the attacker's attempt"),
    ("securedfinance-2026", None): ("medium", 'The transaction landed four blocks and 48 seconds after the attacker transaction failed.'),
    ("shoco-2023", None): ("medium", "adapted (not copied) victim calls; bot's gain equals the attacker's counterfactual to the wei; in-block evidence only"),
    ("sushi-rp2-2023", None): ("high", "Yoink's route matches Trust's except the fake-pool address; Trust's max fee below block base fee"),
    ("time-2023", None): ("n/a", "no other actor"),
    ("transitswap-2022", None): ("high", "21/21 router calls identical bar recipient; in-block evidence only"),
    ("uncx-2026", "yoink-X"): ("high", "attacker's identical X call set landed one block later and reverted"),
    ("uncx-2026", "zc-copiers"): ("medium", "c0ffeebabe landed 250 blocks after the attacker; late copy"),
}


# one-liner corrections applied on top of the extraction scripts' text
ONE_LINER_FIXES = {
    ("time-2023", None): "Yoink was the first to exploit TIME's thirdweb forwarder bug, taking 89.5 ETH gross (84.6 ETH after a 4.92 ETH builder tip) from the TIME/WETH pool in one private tx; its later 84.1 ETH 'recovery' escrow paid out nothing and Yoink withdrew it back.",
}


# --- gap-fill incidents (phase C): one JSON file per slug in scripts/dataset/gapfill_rules/<slug>.json ---
# Each file: [{"slug":..., "sub": null|str, "verdict":..., "race_type":..., "why":..., "strength": ["high|medium|n/a", "basis"],
#              "headline_note": null|str, "one_liner_fix": null|str}]
import json as _json, pathlib as _pl
for _f in sorted((_pl.Path(__file__).resolve().parent / "gapfill_rules").glob("*.json")):
    for _r in _json.load(open(_f)):
        _k = (_r["slug"], _r.get("sub"))
        RULES[_k] = dict(verdict=_r["verdict"], race_type=_r["race_type"], why=_r["why"])
        STRENGTH[_k] = tuple(_r["strength"])
        if _r.get("headline_note"):
            HEADLINE_NOTES[_k] = _r["headline_note"]
        if _r.get("one_liner_fix"):
            ONE_LINER_FIXES[_k] = _r["one_liner_fix"]
