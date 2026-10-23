"""Explicit return denominators for data/incidents.json `fate` (added 2026-10-21 after the paper fact-check).

Why: `fate.returned_pct` was always returned_total_eth / gross_loot_eth, but "gross" (everything the bot tx took from the
victim, before the bribe) and "the bot's net" (after the coinbase payment +/- builder refund) tell different stories
(DeFi Plaza: 10.5% of gross, 98.7% of the bot's net). Every row now carries both, plus the builder/proposer pass-through
and a victim-loss denominator. All values are ETH-equivalents already present in the row (loot / fate fields); the only
new chain facts are the corrections in OVERRIDES below.

New `fate` fields (all computed in apply(); null when a figure is unknown, never 0 for "unknown"):
  returned_by_builder_or_proposer_eth  alias of returned_by_builder_eth: ETH a builder / proposer-side recipient passed to the
                                       victim (Blueberry builder -> multisig; Makina builder -> 0xbed -> Safe). null when none seen.
  returned_by_bot_side_eth             returned_total_eth - builder part: what the row's own actors (bot; for Sushi RP2 also the
                                       whitehats) got back to the victim, net of any bounty they sent back or kept out of the return.
  returned_pct_of_gross                returned_total_eth / loot.gross_loot_eth * 100. Equals the legacy `returned_pct` (kept, identical).
  returned_pct_of_bot_net              returned_by_bot_side_eth / loot.bot_net_eth * 100 (bot_net = gross - coinbase - gas + builder
                                       refund). null where the net is ~0 or excludes the main proceeds (see returned_pct_of_bot_net_note).
  victim_loss_eth, victim_loss_basis   ETH-equivalent the victim lost to this tx; equals gross_loot_eth wherever gross is measured at
                                       the victim side (most rows), overridden where it is not.
  returned_pct_of_victim_loss          returned_total_eth / victim_loss_eth * 100.
  returned_pct_note                    caveat on the figures of the row (token legs, scope, >100%).
"""
import copy

# --------------------------------------------------------------------------------------------------------------------
# Corrections found by the 2026-10-21 chain re-check / consistency sweep. Applied on top of data/extract/*.json in
# build_incidents.build_rows (the extract files are intermediate and stay as the extraction scripts wrote them).
# --------------------------------------------------------------------------------------------------------------------
_R = "data/raw/rpc/"
_E = "data/raw/etherscan/"
PARA_RET = "0xa1b1ea5033611603f6e8e5ce5d566ad6b9ad1cd69476e37091c0d90c56c04f90"
PARA_MSG1 = "0xcaa2422853fd14f5645d762729b6edc41ebdac2dce988123d1b91d98eab37e0f"
PARA_MSG2 = "0x19a02f97af7d8165a702c49a6919387bf14c5324853ebb97752084fc813688ec"
PARA_MSG3 = "0xbd43d2dec15cbb6099b6290d4d2fb4d182b59cbb8d42b52b6003d0a64ece0c7c"
PARA_REPLY1 = "0xa645a61524e1cd75b8cd4db956253a804a023ff766d60245d70462ed41b6a278"
PARA_REPLY2 = "0x3d3e7cfe2bc311c7b9c44c62c29224e4ad55e79e241086ca4689198921b7c427"
PARA_SAFE = "0x66E90d840D7C4F3473E25dD8ca361747058c6Db0"
_PARA_RET_REFS = [_R + f"tx_{PARA_RET}.json", _R + f"receipt_{PARA_RET}.json", _R + "block_19508275_full.json",
                  _E + "para_return_addr_txlist.json"]
_PARA_MSG_REFS = [_R + f"tx_{h}.json" for h in (PARA_MSG1, PARA_MSG2, PARA_MSG3, PARA_REPLY1, PARA_REPLY2)] + \
                 [_E + "para_yoink_eoa_txlist_19470000_19530000.json"]
BB_RESIDUE = "0x111102a20a2007b1461c8206d544b4cee8c1702a6aadf584c5355b0fb3052091"

OVERRIDES = {
    ("paraswap-2024", None): {
        "one_liner": ("Yoink was the first to exploit Paraswap Augustus V6's missing callback caller check, pulling 12,479 OPSEC (6.46 WETH) "
                      "from one approving wallet 11 hours before anyone else; after Paraswap's on-chain message it sent 4.342 ETH (99.8% of "
                      "its 4.35 ETH net, 67% of the 6.46 ETH sale) to the Safe Paraswap named, and declined to send the rest."),
        "fate": {
            "return_status": "partial",
            "returned_by_bot_eth": 4.342, "returned_by_builder_eth": None, "returned_total_eth": 4.342,
            "returned_to": (f"{PARA_SAFE}: the address Paraswap named in its on-chain message {PARA_MSG1[:10]} (block 19507521, 2024-03-24T23:00:59Z) and "
                            "the Safe Wallet that Velora's help-centre article names as holding the funds of its white-hat operation"),
            "returned_desc": (f"2024-03-24T23:00:59Z Paraswap's EOA 0xe85ad062 wrote to Yoink's EOA (tx {PARA_MSG1[:10]}, block 19507521): reply by email or "
                              f"transfer the funds directly to {PARA_SAFE}, deadline 2024-03-27 23:00 UTC. 2024-03-25T01:33:35Z (block 19508275, "
                              f"about 2.5 h later) Yoink's EOA 0xfde0d157 sent 4.342 ETH to that address (tx {PARA_RET}, a plain transfer, status 1). "
                              f"2024-03-25T22:20:35Z Paraswap ({PARA_MSG2[:10]}): 'Thank you for sending back half the misappropriated funds ... we would like to "
                              f"propose a bounty of 10% ... transfer the remaining 90%'. 2024-03-26T15:48:11Z Paraswap ({PARA_MSG3[:10]}): '0x35a7 took 12,479 OPSEC "
                              f"from the user, which is 6.46 ETH instead of 4.342 ETH that you sent back. Could you please send the rest?'. Yoink replied on chain "
                              f"({PARA_REPLY1[:10]}, {PARA_REPLY2[:10]}) that it had already repaid its entire profit and 'more than 100% of my profits', and that "
                              "2.22 ETH went to the validator at the end of the block ('welcome to try and recover the remaining amount from the validator'). "
                              "No further Yoink -> Paraswap transfer appears in the Safe's normal and internal tx lists (blocks 19470000-19700000) or in Yoink's EOA "
                              "tx list to 2024-05-24 (block 19936023). So the return is 4.342 ETH = 67.2% of the 6.4633 ETH sale proceeds (gross), 99.8% of the bot tx's "
                              "4.3499 ETH net (99.6% of the 4.3591 ETH block-level net incl. Yoink's second tx), and Paraswap's own message puts the gap at 2.12 ETH. "
                              "99.8% of the proceeds went to the coinbase; the builder refunded 4.3369 ETH of that to Yoink (67%) and passed 2.2229 ETH to the proposer."),
            "bounty_kept_eth": None,
            "bounty_desc": "no bounty agreed: Paraswap proposed 10% on the remaining 90% (0x19a02f97) and then asked for the remaining ~2.12 ETH; Yoink declined; net kept = bot net minus the return",
            "kept_by_bot_eth": round(4.349856326462 - 4.342, 12),
            "returned_txs": [
                {"tx": PARA_MSG1, "eth": None, "note": "Paraswap EOA 0xe85ad062 -> Yoink EOA: asks for the funds, names the Safe", "block": 19507521, "time_utc": "2024-03-24T23:00:59Z"},
                {"tx": PARA_RET, "eth": 4.342, "note": f"Yoink EOA 0xfde0d157 -> {PARA_SAFE} (the Safe named by Paraswap)", "block": 19508275, "time_utc": "2024-03-25T01:33:35Z"},
                {"tx": PARA_MSG2, "eth": None, "note": "Paraswap: thanks for half; proposes 10% bounty, asks for the remaining 90%", "block": 19514410, "time_utc": "2024-03-25T22:20:35Z"},
                {"tx": PARA_REPLY1, "eth": None, "note": "Yoink: already repaid its entire profit; validator payment limits what it can return", "block": 19515720, "time_utc": None},
                {"tx": PARA_MSG3, "eth": None, "note": "Paraswap: 6.46 ETH instead of 4.342 ETH; please send the rest", "block": 19519593, "time_utc": "2024-03-26T15:48:11Z"},
                {"tx": PARA_REPLY2, "eth": None, "note": "Yoink: sent more than 100% of its profit; 2.22 ETH went to the validator", "block": 19522575, "time_utc": None},
            ],
            "public_statement": ("Paraswap's own on-chain messages to Yoink (0xcaa24228, 0x19a02f97, 0xbd43d2de, quoted in returned_desc); Velora help-centre article "
                                 f"'On the Augustus V6 Vulnerability of March 20th, 2024' (saved): funds secured by its white-hat operation 'were transferred to a Safe Wallet with the address {PARA_SAFE}'. "
                                 "The Velora post-mortem on Medium returned HTTP 403 here (saved as the 403 body) and was not read. DeFiHackLabs and Etherscan label the actor a whitehat; "
                                 "on-chain it was the first exploiter and returned its net profit only after being contacted."),
        },
        "raw_refs": {
            "fate.return_status": _PARA_RET_REFS + _PARA_MSG_REFS,
            "fate.returned_by_bot_eth": _PARA_RET_REFS + [_PARA_MSG_REFS[0]],
            "fate.returned_total_eth": _PARA_RET_REFS,
            "fate.kept_by_bot_eth": ["data/raw/rpc/trace_0x35a73969f582872c25c96c48d8bb31c23eab8a49c19282c67509b96186734e60.json", "data/raw/rpc/block_19470561.json"] + _PARA_RET_REFS,
            "fate.no_further_return_check": [_E + "para_return_addr_txlist.json", _E + "para_return_addr_txlistinternal.json",
                                             _E + "para_yoink_eoa_txlist_19470000_19530000.json", _E + "para_yoink_eoa_txlist_19530000_20500000.json"],
            "fate.public_statement": ["data/raw/web-paraswap/velora_help_article_9145463.html", "data/raw/web-paraswap/velora_postmortem_augustus_v6.html"] + _PARA_MSG_REFS[:3],
        },
        "rawref_gaps_drop": ["fate.returned_*"],
        "rawref_gaps_add": [{"field": "fate.public_statement", "why": "Velora's Medium post-mortem is HTTP 403 from this host (the 403 body is saved); the help-centre article and Paraswap's on-chain messages are used instead"}],
    },
    ("blueberry-2024", None): {
        "fate": {
            "returned_by_builder_eth": 366.626810481, "returned_total_eth": 436.626810481,
            "returned_desc_replace": ("Total to the multisig 436.5069 ETH = 95.4% of the gross.",
                                      f"The builder's fee recipient 0x25b71878 also sent a 0.11996 ETH residue to the multisig in block 19289339 (tx {BB_RESIDUE}), so the builder returned "
                                      "366.6268 ETH (Blueberry's own X post reports about 366.6 ETH returned to the multisig) and the total to the multisig is 436.6268 ETH = 95.40% of the gross (corrected 2026-10-21 from 436.5069 / 95.37%)."),
        },
        "raw_refs": {"fate.returned_by_builder_eth": [_R + "block_19287289.json", _R + "trace_block_19287289.json", _R + f"tx_{BB_RESIDUE}.json", _R + f"receipt_{BB_RESIDUE}.json"],
                     "fate.returned_total_eth": [_R + "block_19287289.json", _R + "tx_0x55f8a7df75c02c9dca98f8749a0bd3d4b3f31fffce06c6e5f796e919ff42b434.json", _R + f"tx_{BB_RESIDUE}.json"]},
        "returned_txs_add": [{"tx": BB_RESIDUE, "eth": 0.119960133088, "note": "builder fee recipient 0x25b71878 -> Blueberry multisig (residue, block 19289339)", "block": 19289339, "time_utc": None}],
    },
    ("defiplaza-2024", None): {
        # no value change; the chain re-derivation (2026-10-21) adds raw refs for the return receipts and the bot-contract balance check
        "raw_refs_extra": {
            "fate.returned_pct_of_bot_net": [_R + "receipt_0xb1ddf7e262ceec136f39dcc36509e0203b1536938a6f3c5ae1a26bd0aeba39f0.json",
                                             _R + "dp_bal_yoink_contract_20240538.json", _R + "dp_bal_yoink_contract_20240539.json",
                                             _R + "tx_0x1e34998e96183aa6c0e3eae0dc242008e5ce8d19ee4f5b48d169297d42981f60.json"],
        },
        "returned_pct_note": ("Same return, three denominators: 10.46% of the 73.39 ETH pool loss (gross; 66.32 ETH of it was paid to the coinbase and 62.54 ETH of that went to the Lido "
                              "vault), 98.66% of Yoink's 7.78 ETH net. Re-derived on chain 2026-10-21: the four vault -> deployer return transfers (19:42-19:47 UTC, blocks 20242465-20242491, "
                              "receipts saved) are worth $22,689 = 7.679 ETH at the row's 13:15 prices; the bot contract's ETH balance fell 13.364 ETH over block 20240539 "
                              "(-18.129 ETH in the tx + 4.761 ETH builder refund); the USDT, WBTC and 12,808.73 USDC swept to the vault were sold for 13.417 ETH before the returns, "
                              "which roughly refilled that shortfall. Upper-bound net (gross - coinbase + refund, before swap slippage and fees) is 11.83 ETH, of which the return is 64.9%."),
    },
}

# --------------------------------------------------------------------------------------------------------------------
# Per-row exceptions for the derived percentages.
# --------------------------------------------------------------------------------------------------------------------
BOT_NET_NOT_MEANINGFUL = {
    ("blueberry-2024", None): "bot-tx net is 0.0464 ETH (gross 457.68 - coinbase 457.55 - gas 0.09) but the bot's EOA sent 70 ETH from other funds, so a share of net is not meaningful (ratio about 1,500x); the builder, not the bot, returned the rest",
    ("uncx-2026", "yoink-X"): "bot_net_eth (0.0041) counts only the ETH side of the tx; Yoink's net is mostly the 102,143,476 X tokens swept to its vault (unpriced). The 8.10 ETH returned exceeds the ETH-side net; token leg: 82,143,476.36 of 102,143,476.36 X returned = 80.42%, 20,000,000 X (19.58%) kept",
}
VICTIM_LOSS_OVERRIDE = {   # (value or None, basis)
    ("earningfarm-2022", None): (480.008083, "net of the 0.1 ETH the bot's helper had deposited into the vault first (480.1081 ETH paid out - 0.1 ETH deposit)"),
    ("balancer-2025", None): (None, "not set: the Balancer incident's loss is far larger than this rescue replay (260.5 ETH-equivalent of the 3 assets it took); the row's own take is the denominator of returned_pct_of_gross"),
    ("uncx-2026", "yoink-X"): (None, "not set: the victim lost X tokens (unpriced) plus ETH-side proceeds; gross_loot_eth is the ETH side only"),
}
PCT_NOTES = {
    ("alkimiya-2025", None): "returned_total_eth is net of the 6.3287 ETH that came back to Yoink (inferred bounty); Yoink sent 48.3287 ETH, 95.0% of its gross.",
    ("balancer-2025", None): "whitehat rescue replay; returned_total_eth is net of the 10% bounty paid by the DAO; bot_net is the rescued value before it was returned.",
    ("curve-vyper-2023", "pETH"): "returned_total_eth is the 5,495.4 WETH reaching JPEG'd; the 10% bounty (about 610.6 WETH) was kept as agreed.",
    ("kelp-rseth-2026", None): "ETH-equivalents use the in-tx swap rate (1.074724 ETH/rsETH); the other 17.63 rsETH paid the builder tip, so returned/gross counts that tip as unreturned.",
    ("makina-2026", None): "the bot itself returned nothing of its 0.13 ETH net; the 920.7 ETH came from the builder chain (0xbed2 kept a 102.3 ETH bounty out of the 1,023.0 ETH the builder forwarded).",
    ("ronin-2024", "eth-leg"): "the bot contract sent 4,001 ETH (more than this tx's gross; it also held other proceeds); 3,992.097 ETH reached Ronin's Safe.",
    ("ronin-2024", "yoink-usdc"): "800 ETH was withdrawn by the bot contract, 792.456 ETH reached Ronin's Safe; bot_net attributes the whole 791.74 ETH block refund to this tx (attributing the block's net outlay instead gives 785.37 ETH, and 100.9% returned).",
    ("saddle-2022", None): "above 100% of net because bot_net is nominal (gross minus the priority fees BlockSec paid for the rescue); the whole rescued amount was returned.",
    ("sushi-rp2-2023", None): "incident-wide scope: gross 1,800 ETH is everything the 11 pulling txs took, bot_net is that minus all payments to the auction, and returned_total_eth (875) also includes the whitehats Trust (90) and BlockSec (100).",
    ("transitswap-2022", None): "Yoink offered 90% of its profit (26.505 ETH) and kept 10% as bounty, paid 2023-09-06.",
    ("uncx-2026", "yoink-X"): "ETH leg only for the gross comparison: the 8.10335 ETH returned is compared with the 8.14 ETH ETH-side gross; the X-token leg is 80.42% returned.",
}


def _num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def _pct(a, b):
    a, b = _num(a), _num(b)
    if a is None or not b:
        return None
    return round(100.0 * a / b, 3)


def key_of(o):
    return (o["slug"], o.get("sub"))


def apply_overrides(o):
    """Merge OVERRIDES into the extracted row before any derived field is computed."""
    ov = OVERRIDES.get(key_of(o))
    if not ov:
        return
    if "one_liner" in ov:
        o["one_liner_agent"] = o["one_liner"]
        o["one_liner"] = ov["one_liner"]
    F = o["fate"]
    for k, v in (ov.get("fate") or {}).items():
        if k == "returned_desc_replace":
            old, new = v
            d0 = F.get("returned_desc") or ""
            F["returned_desc"] = d0.replace(old, new) if old in d0 else d0 + " " + new
        else:
            F[k] = copy.deepcopy(v)
    if ov.get("returned_txs_add"):
        have = {t.get("tx") for t in F.get("returned_txs") or []}
        F["returned_txs"] = (F.get("returned_txs") or []) + [t for t in ov["returned_txs_add"] if t["tx"] not in have]
    rr = o.setdefault("raw_refs", {})
    for k, v in (ov.get("raw_refs") or {}).items():
        rr[k] = list(v)
    if ov.get("rawref_gaps_drop") or ov.get("rawref_gaps_add"):
        gaps = [g for g in (o.get("rawref_gaps") or []) if g.get("field") not in (ov.get("rawref_gaps_drop") or [])]
        o["rawref_gaps"] = gaps + list(ov.get("rawref_gaps_add") or [])
    o.setdefault("fate_overrides", []).append("2026-10-21 returns re-check: " + (", ".join(sorted((ov.get("fate") or {}).keys())) or "raw_refs only"))


def apply(o):
    """Compute the explicit-denominator fields on o['fate'] (after returned_total_eth and the legacy returned_pct exist)."""
    F, L = o["fate"], o["loot"]
    k = key_of(o)
    G, N = _num(L.get("gross_loot_eth")), _num(L.get("bot_net_eth"))
    R, B = _num(F.get("returned_total_eth")), _num(F.get("returned_by_builder_eth"))
    F["returned_by_builder_or_proposer_eth"] = B
    bot_side = None if R is None else round(R - (B or 0.0), 12)
    F["returned_by_bot_side_eth"] = bot_side
    F["returned_pct_of_gross"] = _pct(R, G)
    F["returned_pct"] = F["returned_pct_of_gross"]          # legacy alias, identical by construction
    note = []
    if k in BOT_NET_NOT_MEANINGFUL:
        F["returned_pct_of_bot_net"] = None
        note.append("returned_pct_of_bot_net not meaningful: " + BOT_NET_NOT_MEANINGFUL[k])
    else:
        F["returned_pct_of_bot_net"] = _pct(bot_side, N) if (N is not None and N > 0.05) else None
        if bot_side is not None and N is not None and N <= 0.05 and F["returned_pct_of_bot_net"] is None:
            note.append(f"returned_pct_of_bot_net not computed: bot_net_eth {N} is under 0.05 ETH")
    if k in VICTIM_LOSS_OVERRIDE:
        vl, basis = VICTIM_LOSS_OVERRIDE[k]
    elif G is not None:
        vl = G
        basis = ("sum of the victim's outflows to the bot txs of this incident (all-bots scope) = gross_loot_eth" if L.get("scope") == "all-bots-in-incident"
                 else "ETH-equivalent that left the victim in the bot tx = gross_loot_eth (gross is measured at the victim side)")
    else:
        vl, basis = None, "not set: loot not priced in ETH"
    F["victim_loss_eth"] = vl
    F["victim_loss_basis"] = basis
    F["returned_pct_of_victim_loss"] = _pct(R, vl)
    if k in PCT_NOTES:
        note.append(PCT_NOTES[k])
    ov = OVERRIDES.get(k) or {}
    if ov.get("returned_pct_note"):
        note.append(ov["returned_pct_note"])
    if F["returned_pct_of_bot_net"] is not None and F["returned_pct_of_bot_net"] > 100.0:
        note.append("above 100%: returned exceeds the tx-level net (see the row's loot_note)")
    F["returned_pct_note"] = " ".join(note) or None
    for kk, v in (ov.get("raw_refs_extra") or {}).items():
        o.setdefault("raw_refs", {})[kk] = list(v)


# figures that must carry a raw_ref (added to the audit's `must` list and to the union() derivation in build_incidents)
NEW_FATE_FIELDS = ["fate.returned_by_builder_or_proposer_eth", "fate.returned_by_bot_side_eth", "fate.returned_pct_of_gross",
                   "fate.returned_pct_of_bot_net", "fate.victim_loss_eth", "fate.returned_pct_of_victim_loss"]


# --------------------------------------------------------------------------------------------------------------------
# Documentation written into data/harmonize_log.json
# --------------------------------------------------------------------------------------------------------------------
BEFORE = {   # legacy values replaced by the 2026-10-21 corrections
    "paraswap-2024": {"return_status": "none-found", "returned_total_eth": None, "returned_pct": None, "kept_by_bot_eth": 4.349856326462},
    "blueberry-2024": {"return_status": "partial", "returned_by_builder_eth": 366.50685, "returned_total_eth": 436.50685, "returned_pct": 95.373},
}

SWEEP = [
    {"row": "paraswap-2024", "kind": "fixed (data wrong)",
     "finding": f"fate said none-found. Chain: tx {PARA_RET} (block 19508275, 2024-03-25T01:33:35Z, idx 0x60) sent 4.342 ETH from Yoink's EOA 0xfde0d157 to {PARA_SAFE}, "
                f"the address Paraswap named in its on-chain message {PARA_MSG1} (2024-03-24T23:00:59Z) and the Safe Velora's help-centre article names as holding its white-hat operation's funds. "
                "Paraswap later asked for the other ~2.12 ETH (0xbd43d2de) and Yoink declined (0x3d3e7cfe); no further transfer found to 2024-05-24. The earlier search had looked at the approving wallet's inbound traces, not Paraswap's named address.",
     "after": {"return_status": "partial", "returned_total_eth": 4.342, "returned_pct_of_gross": 67.179, "returned_pct_of_bot_net": 99.819, "returned_pct_of_victim_loss": 67.179}},
    {"row": "blueberry-2024", "kind": "fixed (small omission)",
     "finding": "incidents/blueberry-2024/incident.json funds_fate lists a second builder-side return, 0.11996 ETH from the fee recipient 0x25b71878 to the multisig in block 19289339 (tx 0x111102a2, verified on chain), "
                "which the dataset omitted; with it the builder returned 366.6268 ETH (Blueberry's own X post reports about 366.6 ETH returned to the multisig).",
     "after": {"returned_by_builder_eth": 366.626810481, "returned_total_eth": 436.626810481, "returned_pct_of_gross": 95.399}},
    {"row": "defiplaza-2024", "kind": "re-derived, data was right; prose conflated denominators",
     "finding": "Chain re-derivation: pool loss 73.39 ETH (15 tokens, DefiLlama 13:15 prices, ETH $2954.6); Yoink paid 66.318 ETH to the coinbase, got 4.761 ETH back, bot_net 7.78 ETH "
                "(the contract's ETH balance fell 13.364 ETH over block 20240539 = -18.129 + 4.761). Four vault -> DeFi Plaza deployer transfers (19:42-19:47 UTC, receipts saved) = $22,689 = 7.679 ETH. "
                "So 10.46% of gross (the pool loss) and 98.66% of Yoink's net are BOTH correct; no ETH was returned, and the 62.54 ETH the builder paid the proposer (Lido vault) is not a return.",
     "after": {"returned_pct_of_gross": 10.464, "returned_pct_of_bot_net": 98.657, "returned_pct_of_victim_loss": 10.464}},
    {"row": "uncx-2026/yoink-X", "kind": "caveat added", "finding": "returned_pct 99.548 compares the 8.10335 ETH returned with the 8.14 ETH ETH-side gross while the real net is mostly 102.14M X tokens; token leg 82.14M returned = 80.42%. Share of bot net set to null."},
    {"row": "blueberry-2024", "kind": "caveat added", "finding": "share of bot-tx net is not meaningful (net 0.0464 ETH vs 70 ETH sent from other funds); set to null."},
    {"row": "ronin-2024/eth-leg + yoink-usdc", "kind": "checked, unchanged", "finding": "returned_by_bot_eth (4,001 / 800) is what the bot contract sent; returned_total_eth (3,992.097 / 792.456) is what reached Ronin's Safe; pct uses the latter."},
    {"row": "alkimiya-2025", "kind": "checked, unchanged", "finding": "returned_total_eth 42.0 is net of the 6.3287 ETH that came back to Yoink; 82.54% of gross, 86.90% of bot net (paper: 87%)."},
    {"row": "makina-2026", "kind": "checked, unchanged", "finding": "70.87% of gross is entirely builder-chain (0xbed2) money; the bot returned nothing of its own 0.13 ETH net (0.0% of bot net)."},
    {"row": "sushi-rp2-2023", "kind": "checked, unchanged", "finding": "875 ETH = Trust 90 + BlockSec 100 + 685 via the Sushi multisig (c0ffeebabe 305.3 + Yoink 380); incident-wide scope, not pooled; no builder or proposer return found. kept_by_bot_eth (4.80) is c0ffeebabe.eth's own arithmetic remainder, not an incident-wide figure, which is the one consistency_check exception."},
    {"row": "dodo-v2-2021", "kind": "checked, unchanged", "finding": "Antelope row has no ETH-priced gross, so no percentages; Cheetah's USDT return (1,139,456 USDT, tx 0x6e743db0) is verified in the fact-check but belongs to another bot."},
    {"row": "paper section 7.1 table", "kind": "checked", "finding": "all coinbase / proposer / refund / pass-through numbers match the dataset except Kelp 'Builder kept or forwarded 5.09': dataset coinbase 18.9312 - proposer 13.8630 = 5.07 (5.09 = swap proceeds 18.9502 - 13.8630)."},
]

RETURNS_DECISIONS = [
    "fate.returned_pct is kept and set equal to fate.returned_pct_of_gross for every row (it was already returned_total_eth / gross_loot_eth; the old name hid the denominator). Values identical except the two corrected rows (Paraswap null -> 67.179, Blueberry 95.373 -> 95.399).",
    "added fate.returned_pct_of_gross, returned_pct_of_bot_net, returned_by_builder_or_proposer_eth, returned_by_bot_side_eth, victim_loss_eth (+victim_loss_basis), returned_pct_of_victim_loss, returned_pct_note; every one has a raw_refs entry (data/rawref_audit.json fields_without_raw_ref is empty)",
    "Paraswap: return_status none-found -> partial; 4.342 ETH returned (see returns_schema.OVERRIDES and harmonize_log.json -> returns_schema.sweep); fact-check 2026-10-21 had flagged it",
    "Blueberry: builder residue 0.11996 ETH added to returned_by_builder_eth; returned_total_eth 436.50685 -> 436.626810481",
    "DeFi Plaza: no value change; 10.464% of gross and 98.66% of bot net are both published, with the chain re-derivation in returned_pct_note",
]


def consistency_checks(rows):
    """Internal checks of the fate block; returned list is informational (empty = all pass)."""
    bad = []
    for o in rows:
        F, L, k = o["fate"], o["loot"], f"{o['slug']}/{o.get('sub')}"
        R, B, N = _num(F.get("returned_total_eth")), _num(F.get("returned_by_builder_eth")), _num(L.get("bot_net_eth"))
        if F.get("returned_pct") != F.get("returned_pct_of_gross"):
            bad.append((k, "returned_pct != returned_pct_of_gross"))
        if R is not None and abs(R - (F["returned_by_bot_side_eth"] + (B or 0))) > 1e-9:
            bad.append((k, "returned_total != bot_side + builder"))
        st = F.get("return_status")
        if st == "none-found" and R:
            bad.append((k, "status none-found but returned_total_eth set"))
        if st in ("returned", "partial") and R is None and not (o["slug"] == "dodo-v2-2021" or k.startswith("uncx-2026/zc")):
            bad.append((k, "status returned/partial without ETH figure"))
        kept = _num(F.get("kept_by_bot_eth"))
        if R is not None and kept is not None and N is not None and abs(kept + (R - (B or 0)) - N) > max(0.2, 0.001 * abs(N)):
            bad.append((k, f"kept_by_bot_eth {kept} + bot-side return {R - (B or 0):.4f} != bot_net {N:.4f}"))
    return bad


# --------------------------------------------------------------------------------------------------------------------
# Idempotent patch of the Paraswap per-incident files (incident.json, timeline.json, summary.txt) so they agree with the dataset.
# --------------------------------------------------------------------------------------------------------------------
def patch_paraswap_files(root):
    import json, re
    d = root / "incidents" / "paraswap-2024"
    # --- incident.json
    p = d / "incident.json"
    inc = json.load(open(p))
    vr = inc.get("verdict_reason", "")
    new_tail = ("Returns (corrected 2026-10-21): after Paraswap's on-chain message (block 19507521, 2024-03-24T23:00:59Z) Yoink sent 4.342 ETH to the Safe Paraswap named "
                f"({PARA_SAFE}) in tx {PARA_RET} (block 19508275, 2024-03-25T01:33:35Z): 67.2% of the 6.4633 ETH sale, 99.8% of the bot tx's 4.3499 ETH net. "
                "Paraswap asked for the remaining ~2.12 ETH and a 10% bounty split; Yoink declined (2.22 ETH went to the validator); no further transfer found to 2024-05-24. "
                "The 'whitehat' label (DeFiHackLabs header, Etherscan) is still not supported by the sequence of events: Yoink was the first exploiter and returned its net profit only after being contacted.")
    m = re.search(r'The "whitehat" label.*?full-history check not done\)\.', vr, re.S)
    if m:
        vr = vr[:m.start()] + new_tail + vr[m.end():]
    elif "Returns (corrected 2026-10-21)" not in vr:
        vr = vr + " " + new_tail
    inc["verdict_reason"] = vr
    have = {x.get("tx") for x in inc.get("funds_fate", [])}
    add = [
        {"what": f"RETURN: Yoink EOA -> {PARA_SAFE} (the Safe Paraswap named in its message {PARA_MSG1[:10]}; Velora's help-centre article names it as the white-hat operation's Safe), 2024-03-25T01:33:35Z, plain transfer",
         "tx": PARA_RET, "amount_eth": 4.342, "to": PARA_SAFE.lower(), "block": 19508275},
        {"what": "Paraswap EOA 0xe85ad062 asks for the rest: '0x35a7 took 12,479 OPSEC from the user, which is 6.46 ETH instead of 4.342 ETH that you sent back. Could you please send the rest?'",
         "tx": PARA_MSG3, "amount_eth": None, "to": "Yoink EOA 0xfde0d157", "block": 19519593},
        {"what": "Yoink's reply: 'I've already sent you more than 100% of my profits from 0x35a7 ... I had to pay 2.22 Eth to the validator'; no further transfer to Paraswap's Safe found (normal + internal tx lists to block 19700000, Yoink EOA tx list to 2024-05-24)",
         "tx": PARA_REPLY2, "amount_eth": None, "to": "Paraswap EOA 0xe85ad062", "block": 19522575},
    ]
    ff = inc.get("funds_fate", [])
    inc["funds_fate"] = [x for x in ff if not str(x.get("what", "")).startswith("victim 0x0cc396f5 received")] + [x for x in add if x["tx"] not in have] + \
                        [x for x in ff if str(x.get("what", "")).startswith("victim 0x0cc396f5 received")]
    rr = inc.setdefault("raw_refs", {})
    rr["return_tx"] = _R + f"tx_{PARA_RET}.json"
    rr["return_receipt"] = _R + f"receipt_{PARA_RET}.json"
    rr["return_block_19508275"] = _R + "block_19508275_full.json"
    rr["paraswap_messages_txlist"] = _E + "para_yoink_eoa_txlist_19470000_19530000.json"
    rr["return_safe_txlist"] = _E + "para_return_addr_txlist.json"
    rr["velora_help_article"] = "data/raw/web-paraswap/velora_help_article_9145463.html"
    json.dump(inc, open(p, "w"), indent=1, ensure_ascii=False)
    # --- timeline.json
    tp = d / "timeline.json"
    tl = json.load(open(tp))
    evs = [
        (1711321259000, "2024-03-24T23:00:59.000Z", "message", "Paraswap EOA 0xe85ad062", f"on-chain message to Yoink's EOA: reply by email or transfer the funds directly to {PARA_SAFE}; deadline 2024-03-27 23:00 UTC", PARA_MSG1, 19507521),
        (1711330415000, "2024-03-25T01:33:35.000Z", "return", "Yoink 0xfde0d157...", f"4.342 ETH sent to the Safe Paraswap named ({PARA_SAFE[:10]}...): 67.2% of the 6.4633 ETH sale, 99.8% of the bot tx's net", PARA_RET, 19508275),
        (1711405235000, "2024-03-25T22:20:35.000Z", "message", "Paraswap EOA 0xe85ad062", "'Thank you for sending back half the misappropriated funds ... propose a bounty of 10% ... transfer the remaining 90%'", PARA_MSG2, 19514410),
        (1711421015000, "2024-03-26T02:43:35.000Z", "message", "Yoink 0xfde0d157...", "'I've already repaid my entire profit (plus some extra from a following arbitrage!). Note the validator payment at the end of the block'", PARA_REPLY1, 19515720),
        (1711468091000, "2024-03-26T15:48:11.000Z", "message", "Paraswap EOA 0xe85ad062", "'0x35a7 took 12,479 OPSEC from the user, which is 6.46 ETH instead of 4.342 ETH that you sent back. Could you please send the rest?'", PARA_MSG3, 19519593),
        (1711504583000, "2024-03-27T01:56:23.000Z", "message", "Yoink 0xfde0d157...", "'I've already sent you more than 100% of my profits from 0x35a7 ... I had to pay 2.22 Eth to the validator ... welcome to try and recover the remaining amount from the validator'", PARA_REPLY2, 19522575),
    ]
    have_tx = {e.get("tx") for e in tl if isinstance(e, dict)}
    new = [{"t_utc_ms": ms, "t_utc": t, "kind": k, "actor": a, "detail": dtl, "tx": tx, "raw_ref": _R + f"tx_{tx}.json", "block": blk}
           for ms, t, k, a, dtl, tx, blk in evs if tx not in have_tx]
    if new:
        tail = [e for e in tl if e.get("t_utc_ms") is None and e is tl[-1]]
        body = [e for e in tl if e not in tail]
        tl = body + new + tail
        json.dump(tl, open(tp, "w"), indent=1, ensure_ascii=False)
    # --- summary.txt
    sp = d / "summary.txt"
    s = open(sp).read()
    old = "No return to the victim or Paraswap found (checked 4 days of victim inbound traces)."
    repl = ("Return (corrected 2026-10-21): after Paraswap's on-chain message Yoink sent 4.342 ETH (tx 0xa1b1ea50..., block 19508275, 2024-03-25 01:33 UTC) to the Safe Paraswap named: 67.2% of the 6.46 ETH sale, "
            "99.8% of its 4.35 ETH net. Paraswap asked for the remaining ~2.12 ETH; Yoink declined, citing the 2.22 ETH validator payment.")
    if old in s:
        open(sp, "w").write(s.replace(old, repl))
