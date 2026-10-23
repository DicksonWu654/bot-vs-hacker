"""Extract alkimiya-2025 -> data/extract/alkimiya-2025.json (incident dataset). Run from project root with .venv/bin/python."""
import json, pathlib, sys, datetime
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import bvh

SLUG = "alkimiya-2025"
D = f"incidents/{SLUG}"
BOT_TX = "0x9b9a6dd05526a8a4b40e5e1a74a25df6ecccae6ee7bf045911ad89a1dd3f0814"
ATT_TX = "0xc8875004a36cb97a40b9d9c8d1a56cf0d6042aec5eb330d17de7d70c8e13d7b4"
RETURN_TX = "0x540aa4f9933ad28f5704db41cfc99df88ade963275be28b38bc8a644484756a5"
BOUNTY_TX = "0x59d55f0809298a2964ce419da0b72f8c118e2c527abbba9f25b63c97df27e99d"
FORWARD_TX = "0xb0def0ac0afc654dae186248457e9cd96b98e6a41d09ea44c1b9c209cdca22b1"
REFUND_TX = "0xac6c9ec1b77f3084ac5345813bfa48e4d9cdd67d9309305ce6dfaff69a7cbd11"
E18 = 10 ** 18
iso = lambda ts: datetime.datetime.fromtimestamp(int(ts), datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
J = lambda p: json.load(open(ROOT / p))

inc = J(f"{D}/incident.json")
race = J(f"{D}/race_22146340.json")
race_att = J(f"{D}/race_22146341.json")
tx0 = next(t for t in race["txs"] if t["hash"] == BOT_TX)
att = next(t for t in race_att["txs"] if t["hash"] == ATT_TX)
assert tx0["index"] == 0 and att["index"] == 275 and att["status"] == 0

# gross loot from the saved trace: WETH.withdraw callback value into the Yoink contract, then the coinbase transfer
tr = J("data/raw/rpc/alk_trace_" + BOT_TX + ".json")["result"]
bot_contract = tr["to"].lower()
cb = race["block"]["fee_recipient"].lower()
gross_wei = cb_wei = None
def walk(c, parent=None):
    global gross_wei, cb_wei
    v = int(c.get("value") or "0x0", 16)
    if parent and parent.get("to", "").lower() == "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2" and c.get("to", "").lower() == bot_contract and v:
        gross_wei = v
    if c.get("to", "").lower() == cb and v and c.get("type") == "CALL":
        cb_wei = (cb_wei or 0) + v
    for x in c.get("calls", []):
        walk(x, c)
walk(tr)
gross = gross_wei / E18
coinbase = cb_wei / E18
assert cb_wei == int(tx0["coinbase_transfer_wei"])
refund_tx = next(t for t in race["txs"] if t["hash"] == REFUND_TX)
refund = int(refund_tx["value_wei"]) / E18
assert refund_tx["from"].lower() == cb and refund_tx["to"].lower() == bot_contract and refund_tx["index"] == 3
prio = int(tx0["priority_fee_total_wei"]) / E18
net = gross - coinbase + refund

# return flows from etherscan raw files
def find(file, h):
    for x in J(f"data/raw/etherscan/{file}")["result"]:
        if x.get("hash") == h:
            return x
ret = find("alk_62e3_txlist.json", RETURN_TX)
bounty = find("alk_62e3_internal.json", BOUNTY_TX)
fwd = find("alk_txl_0xe6ab1d88.json", FORWARD_TX)
assert ret["from"] == "0xfde0d1575ed8e06fbf36256bcdfa1f359281455a" and ret["to"] == "0x62e30d1969faf92dc8a3c22a1552eb83763eb372"
assert bounty["from"] == "0x62e30d1969faf92dc8a3c22a1552eb83763eb372" and fwd["to"] == "0xfde0d1575ed8e06fbf36256bcdfa1f359281455a"
returned = int(ret["value"]) / E18
bounty_eth = int(bounty["value"]) / E18
fwd_eth = int(fwd["value"]) / E18
net_returned = round(returned - bounty_eth, 10)
# Safe funded by the SilicaPools owner/deployer 0x3bd5f5f3 (basis for the 'Alkimiya-affiliated' inference)
fund = find("alk_62e3_txlist.json", "0x83ea1a1fa2741f542fe3aafa09fe9304f82c7ea2ff5ee44a55f3a672c9612dc4")
assert fund["from"] == "0x3bd5f5f368bdfdb86b0513b36b80569b7c90555c"
kept = net - net_returned

auction = bvh.auction_summary(f"{D}/race_22146340.json", BOT_TX)
RT, TR, RC = "data/raw/rpc/trace_block_22146340.json", "data/raw/rpc/alk_trace_" + BOT_TX + ".json", "data/raw/rpc/receipts_22146340.json"
BLK = "data/raw/rpc/block_22146340.json"
ES = lambda f: f"data/raw/etherscan/{f}"
MP = "data/raw/mempool-dumpster/2025-03-28_sourcelog.csv.zip"
refs = {
    "bot.block": [BLK], "bot.position": [BLK, RC], "attacker_block": ["data/raw/rpc/block_22146341.json", "data/raw/rpc/receipts_22146341.json"],
    "loot.gross_loot_eth": [TR], "loot.coinbase_paid_eth": [TR, RT], "loot.priority_fee_paid_eth": [RC, BLK],
    "loot.builder_refund_to_bot_eth": [BLK, TR], "loot.bot_net_eth": [TR, BLK],
    "fate.returned_by_bot_eth": [ES("alk_62e3_txlist.json"), "data/raw/rpc/alk_tx_" + RETURN_TX + ".json"],
    "fate.returned_by_builder_eth": None,
    "fate.returned_total_eth": [ES("alk_62e3_txlist.json"), ES("alk_62e3_internal.json"), ES("alk_txl_0xe6ab1d88.json")],
    "fate.bounty_kept_eth": [ES("alk_62e3_internal.json"), ES("alk_txl_0xe6ab1d88.json")],
    "fate.kept_by_bot_eth": [TR, BLK, ES("alk_62e3_txlist.json"), ES("alk_62e3_internal.json")],
    "evidence_level_mempool": [MP, "data/raw/mempool-dumpster/2025-03-28.csv.zip"],
    "loot.captured_usd": ["data/raw/web-alkimiya/verichains_alkimiya.html"],
    "attacker.safe_funding": [ES("alk_62e3_txlist.json")],
}
refs = {k: v for k, v in refs.items() if v}
rawref_gaps = [{"field": "trigger.first_seen_utc_ms", "why": "attacker config/attack txs and Yoink tx are absent from mempool-dumpster for 2025-03-28 (private flow or missed); first-seen unknown"}]

row = {
    "slug": SLUG, "name": inc["name"],
    "date_utc": race["block"]["timestamp_utc"].replace("+00:00", "Z"),
    "chain": "ethereum",
    "orig_verdict": inc["verdict"],
    "race_type_proposed": "beat-pending-attack",
    "race_type_reason": "Yoink (block 22146340, index 0) replayed the attacker's whole victim call tree from its own contract, one block before the attacker's own attack tx (22146341, index 275) landed and reverted. Attacker's tx was never seen in the public mempool, so how Yoink saw it is unknown.",
    "one_liner": "Yoink copied the Alkimiya attacker's 7-call exploit (reusing its fake-index contract) one block ahead of the attacker's own tx, which then reverted; Yoink returned 48.33 ETH to a Safe and got 6.33 ETH back as bounty.",
    "attacker": {
        "eoa": inc["attacker"]["eoas"][0], "eoas": inc["attacker"]["eoas"],
        "contracts": ["0x69af47f33d19428c206bb46fea2119719dbd3556", "0x9188738a7ca1e4b2af840a77e8726cc6dcbe7bdb",
                      "0x21ace8eac604afb3a5fab23824177fed9b9ea72c", "0x7e0141a4fbcd7363baff42d8862d68b1b5343003", "0x9e31bf60d7d2e2cfcbb48c4e3ba5e70b890024ac"],
        "funding": "tornado",
        "funding_tx": "0x2a0a0a6f35b2b0e6ca6e2251be0ea4e10f19c40ca645c6cac23a5696266fbdfa",
        "deploy_tx": inc["attacker"]["deploy_tx"], "deploy_block": 22146335,
        "attack_txs": [
            {"hash": "0xb34340614221ae8bbeacc9ead14c212b7cc71a56f2e452e9f23e976a1887dcf7", "block": 22146328, "index": 163, "status": "success", "role": "deploy fake pool-index contract 0x9188738a (later reused by Yoink)"},
            {"hash": inc["attacker"]["deploy_tx"], "block": 22146335, "index": 220, "status": "success", "role": "deploy final attack contract 0x69af47f3"},
            {"hash": "0xbf757045feaa99b06f70ac1bba2bca69181a2893d9c640e1635f850d9d05a1dd", "block": 22146338, "index": 77, "status": "success", "role": "configure attack contract to point at the index"},
            {"hash": ATT_TX, "block": 22146341, "index": att["index"], "status": "reverted", "role": "attack(): reverted because Yoink had already drained the pool one block earlier"},
        ],
        "none_reason": None,
        "funding_note": "EOA first funded 2023-10-21 by two 0.1 ETH Tornado Cash withdrawals (per incident.json; first listed here).",
    },
    "bot": {"label": "Yoink", "eoa": tx0["from"], "contract": bot_contract, "tx": BOT_TX, "block": 22146340,
            "position": tx0["index"], "status": "success", "priority_fee_gwei": tx0["priority_fee_gwei"]},
    "bots_other": [],
    "evidence_level_mempool": "absent-from-archive",
    "mempool_note": "mempool-dumpster covers 2025-03-28 (csv + sourcelog present) but neither the attacker's config/attack txs nor Yoink's tx appear (private flow or missed; the dumpster held 163 of 325 txs of block 22146341). First-seen of the attacker tx is unknown, not none.",
    "trigger": {"kind": None, "tx": None, "first_seen_utc_ms": None, "first_seen_utc": None, "sources": None,
                "note": "No pre-inclusion first-seen exists; the attacker's on-chain setup (deploys 22146328/22146335, config 22146338) was public before Yoink's block, so the trigger may have been that setup or the attacker's private attack tx. Unknown."},
    "attacker_block": 22146341,
    "attacker_block_note": f"Attacker's own attack tx {ATT_TX} landed at index 275 of block 22146341 (beaverbuild, 1 gwei priority) and reverted.",
    "attacker_reference": {"kind": "attack-tx", "block": 22146341, "tx": ATT_TX},
    "auction": {**auction, "auction_note": "Winning builder 'I can haz block?' (fee recipient 0x229b8325, also sends the refund tx). Yoink-builder pubkeys' earliest bid already held the 5-tx block incl. the hack tx (0.54 ETH at -1114 ms); when Yoink first saw the attacker tx is unknown. Titan relay answered with 500 bids (API cap) and 309 Titan bids are timestamped after slot start; Ultrasound/Agnostic delivered but hold no bids."},
    "loot": {
        "scope": "bot-tx",
        "gross_loot_eth": round(gross, 12),
        "gross_loot_method": "WETH.withdraw value delivered to the Yoink contract in the bot tx trace, after a UniV3 swap of the 1.14015390 WBTC (114,015,390 sat) taken from the pool",
        "captured_native": {"amount": "1.14015390", "unit": "WBTC", "desc": "114,015,390 sat WBTC swapped to ETH on UniV3 WBTC/WETH in the same tx"},
        "captured_usd": inc["protocol_loss_usd"], "captured_usd_source": "Verichains post: \"loss of approximately $95.5K\" (data/raw/web-alkimiya/verichains_alkimiya.html); headline loss, not recomputed",
        "coinbase_paid_eth": round(coinbase, 12),
        "priority_fee_paid_eth": prio,
        "builder_refund_to_bot_eth": round(refund, 12),
        "builder_payout_to_victim_eth": None,
        "bot_net_eth": round(net, 12),
        "loot_note": "Scope is the bot tx 0x9b9a6dd0 (index 0): gross 50.885 ETH, 999/1000 sent to the coinbase (50.834), priority fee 0. The builder's refund tx (index 3, 48.278 ETH) is a block-level remainder after the 2.576 ETH proposer payment, so it also covers Yoink's second routine tx (index 2, 0.0202 ETH coinbase); bot_net = gross - coinbase + refund is the incident's own figure and matches the 48.3287 ETH later sent to the Safe. Effective proposer payment was 5.07% of block coinbase payments.",
    },
    "fate": {
        "return_status": "partial",
        "returned_by_bot_eth": round(returned, 10),
        "returned_by_builder_eth": None,
        "returned_total_eth": net_returned,
        "returned_to": "Safe 0x62e30d1969faf92dc8a3c22a1552eb83763eb372 (1/1 Safe, owner 0x751edd97; funded 2024-07-14 by SilicaPools owner/deployer 0x3bd5f5f3, so Alkimiya-affiliated is an inference)",
        "returned_desc": f"2025-03-30T04:41:11Z Yoink EOA sent {returned} ETH to the Safe. 2025-03-31T03:07:23Z the Safe sent {bounty_eth} ETH to 0xe6ab1d88, which forwarded {fwd_eth:.6f} ETH to the Yoink EOA at 03:09:59Z. Net returned = {returned} - {bounty_eth} = {net_returned} ETH. INFERENCE: the 6.3287 ETH is read as a bounty (about 13% of the return) from on-chain flows only; no public statement from Alkimiya or Yoink was found. Net retention by Yoink is about the bounty plus the 0.1% fee kept in tx0.",
        "bounty_kept_eth": round(fwd_eth, 10),
        "bounty_desc": "6.3287 ETH sent back from the Safe via 0xe6ab1d88 to the Yoink EOA (6.328687 ETH received after a 21000-gas forward); inferred bounty, not stated publicly.",
        "kept_by_bot_eth": round(kept, 6),
        "returned_txs": [
            {"tx": RETURN_TX, "eth": round(returned, 10), "note": "Yoink EOA -> Safe 0x62e30d19", "block": int(ret["blockNumber"]), "time_utc": iso(ret["timeStamp"])},
            {"tx": BOUNTY_TX, "eth": round(bounty_eth, 10), "note": "Safe -> 0xe6ab1d88 (inferred bounty)", "block": int(bounty["blockNumber"]), "time_utc": iso(bounty["timeStamp"])},
            {"tx": FORWARD_TX, "eth": round(fwd_eth, 10), "note": "0xe6ab1d88 -> Yoink EOA (bounty forwarded)", "block": int(fwd["blockNumber"]), "time_utc": iso(fwd["timeStamp"])},
        ],
        "public_statement": None,
    },
    "raw_refs": refs, "rawref_gaps": rawref_gaps,
    "discrepancies": [],
    "evidence_notes": [
        f"{D}/replay_diff.json: Yoink's 8-call Morpho flashLoan callback matches the attacker's call tree call-for-call (collateralizedMint, 2x safeTransferFrom, index.2ee79ded, startPool, endPool, redeemShort); only the caller address and timestamp words (0x67e6c18b vs 0x67e6c197) differ.",
        "Yoink reuses the attacker-deployed fake pool-index contract 0x9188738a (deployed by the attacker EOA in block 22146328).",
        "Counterfactual: debug_traceCall of the attacker's tx on state after block 22146339 succeeds with net +114,015,390 sat WBTC, exactly Yoink's swap amount (data/raw/rpc/alk_simA_22146339.json); on state after 22146340 it reverts (alk_simA_22146340.json).",
        "Attacker's real attack tx 0xc8875004 landed one block later (22146341, index 275) and reverted.",
        "No public-mempool first-seen exists for the attacker's attack tx, so pre-emption of a public pending tx is unproven.",
    ],
    "incident_dir": D,
}
# discrepancy checks against incident.json
inc_net = next(b for b in inc["bots"])["net_retained_eth_before_return"]
if abs(inc_net - net) > 1e-4:
    row["discrepancies"].append(f"bot_net {net} vs incident.json {inc_net}")
out = ROOT / "data" / "extract" / f"{SLUG}.json"
json.dump([row], open(out, "w"), indent=1)
print("wrote", out, "gross", gross, "coinbase", coinbase, "refund", refund, "net", net, "net_returned", net_returned, "kept", kept)
