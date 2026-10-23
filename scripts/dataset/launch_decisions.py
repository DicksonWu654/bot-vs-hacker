"""Publication adjudications from the first launch review; no new trace analysis."""

RETURN_STATUS_RULE = ("returned = everything went back to the victim side except a bounty the victim agreed to or offered; "
                      "partial = some came back, otherwise; none = known zero within the documented search window; unknown = unresolved")
EULER_CAVEAT = ("The copier may be the attacker’s own second account: it was a fresh single-purpose EOA, "
                "kept the attacker’s cash-out wallet and captured nothing. Its own on-chain message is the only claim that it was a bot.")
C0_POLICY = 'Our call-level comparison for c0ffeebabe.eth transactions is withheld by policy; the public traces can be compared by anyone.'


RETURN_STATUSES = {'alkemi-2026/wbtc-yoink': 'none', 'alkemi-2026/eth-vault-copiers': 'unknown', 'alkimiya-2025': 'partial', 'balancer-2025': 'returned', 'bifi-2026': 'none', 'blueberry-2024': 'partial', 'conic-2023/crvusd-pool': 'partial', 'conic-2023/eth-pool': 'none', 'curve-vyper-2023/pETH': 'returned', 'curve-vyper-2023/msETH': 'unknown', 'curve-vyper-2023/CRV-ETH-wave2': 'returned', 'curve-vyper-2023/alETH': 'unknown', 'curve-vyper-2023/CRV-ETH-wave1': 'unknown', 'defiplaza-2024': 'partial', 'dodo-v2-2021': 'partial', 'earningfarm-2022': 'none', 'euler-copybot-2023': 'none', 'kelp-rseth-2026': 'partial', 'makina-2026': 'partial', 'metapool-2025': 'partial', 'mintswap-2024': 'partial', 'neemo-2025': 'returned', 'paraswap-2024': 'partial', 'peapods-2025/second-attempt': 'partial', 'peapods-2025/07-09-followup': 'unknown', 'peapods-2025/oct-leftover': 'partial', 'punk-2021': 'partial', 'ronin-2024/eth-leg': 'returned', 'ronin-2024/racer3': 'none', 'ronin-2024/yoink-usdc': 'partial', 'saddle-2022': 'returned', 'securedfinance-2026': 'none', 'shoco-2023': 'none', 'sushi-rp2-2023': 'partial', 'taopad-2024': 'partial', 'time-2023': 'none', 'transitswap-2022': 'returned', 'uncx-2026/yoink-X': 'partial', 'uncx-2026/zc-copiers': 'unknown', 'unizen-2024/pending-ads': 'partial', 'unizen-2024/pending-usdt': 'partial', 'unizen-2024/pending-xi': 'partial', 'unizen-2024/half-copies': 'partial'}

def apply(row):
    key = row["slug"] + ("/" + row["sub"] if row.get("sub") else "")
    names = {"unizen-2024": "Unizen", "conic-2023": "Conic Finance", "neemo-2025": "Neemo Finance",
             "mintswap-2024": "MintSwap", "metapool-2025": "Meta Pool", "taopad-2024": "TaoPad", "peapods-2025": "Peapods", "punk-2021": "Punk Protocol", "alkemi-2026": "Alkemi Earn", "uncx-2026": "UNCX token vesting"}
    labels = {"pending-usdt": "pending USDT", "pending-ads": "pending ADS", "pending-xi": "pending XI", "half-copies": "later copies",
              "eth-pool": "ETH pool", "crvusd-pool": "crvUSD pool", "oct-leftover": "October leftover", "second-attempt": "July pair 2",
              "07-09-followup": "July follow-up, rejected", "wbtc-yoink": "WBTC pool", "eth-vault-copiers": "ETH-vault copiers", "yoink-X": "Yoink X-token race", "zc-copiers": "ZC-token copiers"}
    if row["slug"] in names:
        row["name"] = names[row["slug"]]
    row["sub_label"] = labels.get(row.get("sub"), row.get("sub"))
    if key == "peapods-2025/oct-leftover":
        row["one_liner"] = "Yoink recovered the October leftover from an earlier Peapods transaction; the protocol later received part of the proceeds."
    if key == "conic-2023/eth-pool":
        row["one_liner"] = "A later ETH-pool transaction followed the first exploit; no return to Conic was established."
    if key == "conic-2023/crvusd-pool":
        row["one_liner"] = "Yoink replayed the crvUSD-pool extraction after the attacker and later returned part of the proceeds under a bounty agreement."
    if key == "kelp-rseth-2026":
        row["evidence_strength_basis"] = "The finishing transaction was never mined and does not appear in the mempool archive; use of the prepared state is established from the public evidence."
        row["caveat"] = "Ultra Sound's delivered payload paid 13.86 ETH while Eureka bid 14.00 ETH. No winning-block submission survives in the retrieved bid history, so the lower delivered value is unexplained by our records; relay timing or bid adjustment could account for it."
    if key == "time-2023":
        row["one_liner"] = row["one_liner"].replace("in one private tx", "in one transaction absent from the archive")
    fate = row["fate"]
    fate["return_status"] = RETURN_STATUSES[key]
    fate["return_status_rule"] = RETURN_STATUS_RULE
    fate["return_status_basis"] = fate.get("returned_desc") or "See the saved incident evidence."
    if key == "kelp-rseth-2026":
        fate["return_status_basis"] += " Partial under the stated rule: 17.6326 rsETH paid to the builder did not return; no bounty was agreed or offered."
    if key == "uncx-2026/zc-copiers":
        fate["return_status_basis"] = "Unknown: the gross take is unpriced and the Base return cannot be attributed to the Ethereum ZC transaction alone."
    if row["verdict"] == "rejected" or key == "peapods-2025/07-09-followup":
        fate["return_status_applicable"] = False
    if fate["return_status"] == "none":
        fate["returned_total_eth"] = 0.0
        fate["returned_by_bot_eth"] = 0.0
        refs = row.setdefault("raw_refs", {})
        refs["fate.returned_total_eth"] = refs.get("fate.return_status") or refs.get("fate.returned_desc") or refs.get("loot.gross_loot_eth") or refs.get("bot.block")
        refs["fate.returned_by_bot_eth"] = refs["fate.returned_total_eth"]
    if key == "euler-copybot-2023":
        row.update(headline=False, evidence_strength="medium", evidence_strength_basis=EULER_CAVEAT, caveat=EULER_CAVEAT, headline_note=EULER_CAVEAT)
    if (row["bot"].get("eoa") or "").lower() == "0xc0ffeebabe5d496b2dde509f9fa189c25cf29671" and row["headline"]:
        attacker = row["attacker"]
        txs = attacker.get("attack_txs") or []
        ref = row.get("attacker_reference") or {}
        target = next((t for t in txs if t.get("hash") == ref.get("tx")), {})
        row["public_ordering"] = {
            "bot_tx": row["bot"]["tx"], "bot_block": row["bot"]["block"], "bot_position": row["bot"]["position"],
            "raced_attacker_tx": target.get("hash") or ref.get("tx"), "attacker_block": target.get("block") or ref.get("block"),
            "attacker_position": target.get("index"),
            "attacker_deploy": next(({k:t.get(k) for k in ("hash", "block", "index")} for t in txs if t.get("hash") == attacker.get("deploy_tx")), None),
            "comparison_policy": C0_POLICY}
        row["comparison_policy"] = C0_POLICY

