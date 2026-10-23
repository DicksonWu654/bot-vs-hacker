"""Extract balancer-2025 (mainnet leg) -> data/extract/balancer-2025.json. Run from project root with .venv/bin/python.
ONE row: bot = Bitfinding whitehat replay 0x1dc60f91 (block 23717398 idx 2). Fetches (once, cached) two exchange-rate eth_calls
at block 23717398 via scripts/lib/rawfetch.py to express wstETH / osETH in ETH-equivalents."""
import json, pathlib, sys, datetime
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import bvh, rawfetch

SLUG = "balancer-2025"
D = f"incidents/{SLUG}"
BOT_TX = "0x1dc60f917e4d841f281e827cf82f93c7355e08f5855e9ae5b0a1764b38ed4b87"
BOT_EOA = "0x5af00b073abb9f88832353bd4c919caaa114c972"
A1 = "0x6ed07db1a9fe5c0794d44cd36081d6a6df103fab868cdd75d581e3bd23bc9742"
E18 = 10 ** 18
J = lambda p: json.load(open(ROOT / p))
iso = lambda ts: datetime.datetime.fromtimestamp(int(ts), datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

inc = J(f"{D}/incident.json")
race = J(f"{D}/race_23717398.json")
race_att = J(f"{D}/race_23717397.json")
txs = {t["hash"]: t for t in race["txs"]}
bundle = [t for t in race["txs"] if t["from"] == BOT_EOA]
assert [t["index"] for t in bundle] == [2, 3, 4] and txs[BOT_TX]["index"] == 2 and txs[BOT_TX]["to"] is None
a1 = next(t for t in race_att["txs"] if t["hash"] == A1)
assert a1["index"] == 1 and a1["status"] == 1

# replay-diff (recomputed from saved tx inputs)
def inp(h):
    d = J(f"data/raw/rpc-balancer2025/tx_{h}.json")
    return (d.get("result", d))["input"][2:]
ia, ib = inp(A1), inp(BOT_TX)
assert len(ia) == len(ib)
diff_words = [i // 64 for i in range(0, len(ia), 64) if ia[i:i + 64] != ib[i:i + 64]]
n_words = -(-len(ia) // 64)

# priority fee / coinbase for the 3-tx Bitfinding bundle (race file, derived from block+receipts+trace)
prio = sum(int(t["priority_fee_total_wei"]) for t in bundle) / E18
coinbase = sum(int(t["coinbase_transfer_wei"]) for t in bundle) / E18
fr = race["block"]["fee_recipient"].lower()
refund_txs = [t for t in race["txs"] if t["from"].lower() == fr and t["to"] and t["to"].lower() in (BOT_EOA, "0xdb8986fd3ff03182bd5fac4a8338ad6e6136fbf4")]
refund = sum(int(t["value_wei"]) for t in refund_txs) / E18   # 0.0: no builder -> bot transfer in the block

# exchange rates at the block of the replay (saved by rawfetch.rpc)
blk = hex(23717398)
r_wst = int(rawfetch.rpc("eth_call", [{"to": "0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0", "data": "0x035faf82"}, blk],
                         key="bal_rate_wsteth_stEthPerToken_23717398", source="rpc-balancer2025"), 16) / E18
r_os = int(rawfetch.rpc("eth_call", [{"to": "0x2A261e60FB14586B474C208b1B7AC6D0f5000306", "data": "0x07a2d13a" + hex(E18)[2:].rjust(64, "0")}, blk],
                        key="bal_rate_osETH_convertToAssets_23717398", source="rpc-balancer2025"), 16) / E18
RATE_WST = "data/raw/rpc-balancer2025/bal_rate_wsteth_stEthPerToken_23717398.json"
RATE_OS = "data/raw/rpc-balancer2025/bal_rate_osETH_convertToAssets_23717398.json"

# token flows of Bitfinding (etherscan tokentx)
tt = J("data/raw/etherscan/bal_0x5af00b07_tokentx.json")["result"]
amt = lambda x: int(x["value"]) / 10 ** int(x["tokenDecimal"])
H_WD, H_OS = "0x0d6f2d90c543e137b59318d6c557f772fa638da757c2c8c095c7076d6fbb159d", "0xaa52c3a7a0d5"
weth = next(amt(x) for x in tt if x["hash"] == H_WD and x["tokenSymbol"] == "WETH")
wst = next(amt(x) for x in tt if x["hash"] == H_WD and x["tokenSymbol"] == "wstETH")
os_x = next(x for x in tt if x["hash"].startswith(H_OS) and x["tokenSymbol"] == "osETH")
osb = amt(os_x)
bpt = next(amt(x) for x in tt if x["hash"].startswith(H_OS) and x["tokenSymbol"] == "osETH/wETH-BPT")
# the later withdrawal tx must be a call into the contract created by the replay tx
tl = J("data/raw/etherscan/bal_0x5af00b07_txlist.json")["result"]
wd2 = next(x for x in tl if x["hash"].startswith(H_OS))
assert wd2["to"].lower() == "0xdb8986fd3ff03182bd5fac4a8338ad6e6136fbf4"
# returns to DAO multisig
ret = {x["tokenSymbol"]: x for x in tt if x["from"].lower() == BOT_EOA and x["to"].lower() == "0x10a19e7ee7d7f8a52822f6817de8ea18204f2e4f"}
assert abs(amt(ret["wstETH"]) - wst) < 1e-12 and abs(amt(ret["osETH"]) - osb) < 1e-12 and amt(ret["WETH"]) >= weth

gross = weth + wst * r_wst + osb * r_os          # stETH treated as 1 ETH
bounty = 0.10 * gross
net_ret = gross - bounty

bt = J("data/raw/etherscan/bal_bitf_bounty_tokentx.json")["result"]
b0 = [x for x in bt if x["hash"].startswith("0xaa0de3c2ea")]
assert len(b0) == 5 and b0[0]["blockNumber"] == "24237348"
b_time = iso(b0[0]["timeStamp"])
bip = json.dumps(J("data/raw/balancer-web/bip892_6883.json"))
assert "963,832" in bip and "Bitfinding" in bip

auction = bvh.auction_summary(f"{D}/race_23717398.json", BOT_TX)

BLK, RC, TR = "data/raw/rpc/block_23717398.json", "data/raw/rpc/receipts_23717398.json", "data/raw/rpc/trace_block_23717398.json"
TT, TL = "data/raw/etherscan/bal_0x5af00b07_tokentx.json", "data/raw/etherscan/bal_0x5af00b07_txlist.json"
BIP = "data/raw/balancer-web/bip892_6883.json"
refs = {
    "bot.block": [BLK], "bot.position": [BLK, RC],
    "attacker_block": ["data/raw/rpc/block_23717397.json", "data/raw/rpc/receipts_23717397.json"],
    "loot.gross_loot_eth": [TT, RATE_WST, RATE_OS, "data/raw/rpc-balancer2025/tx_%s.json" % BOT_TX],
    "loot.coinbase_paid_eth": [TR, BLK], "loot.priority_fee_paid_eth": [RC, BLK],
    "loot.builder_refund_to_bot_eth": [BLK, RC], "loot.bot_net_eth": [TT, RATE_WST, RATE_OS],
    "fate.returned_by_bot_eth": [TT, RATE_WST, RATE_OS], "fate.returned_total_eth": [TT, RATE_WST, RATE_OS, BIP],
    "fate.bounty_kept_eth": ["data/raw/etherscan/bal_bitf_bounty_tokentx.json", BIP],
    "fate.kept_by_bot_eth": ["data/raw/etherscan/bal_bitf_bounty_tokentx.json", BIP],
    "loot.aggregate_bitfinding_mainnet_usd": [BIP],
    "evidence_level_mempool": ["data/raw/mempool-dumpster/2025-11-03.csv.zip", "data/raw/mempool-dumpster/index_2025-11.html"],
}
refs = {k: v for k, v in refs.items() if v}

def other(label, eoa, tx, block, pos, status, role):
    return {"label": label, "eoa": eoa, "tx": tx, "block": block, "position": pos, "status": status, "role": role}

bots_other = [
    other("0xc0ffee445a22 (backrun arbitrage; tx-level facts only, NOT c0ffeebabe.eth)", "0xc0ffee445a22e6228cfb77ec0483c426fc856161",
          "0x4b6b5fb9aa779c7662793a2613dca48f6e4afd15037b1acf2be4355cb032ed63", 23717397, 2, "success",
          "same-block backrun directly after the attacker tx (idx 1): paid 20.596 ETH to the block fee recipient (Titan) while only 0.0502 ETH reached the proposer; arbitrage, not a replay"),
    other("0x240926d7 (backrun arbitrage)", "0x240926d7f0000006608b59d3952a5b64d3877d15",
          "0xfd261ed26272fa1e084066aae99aa0141c403b0e76ce3ffaebe14adae9a6e9eb", 23717398, 1, "success",
          "backrun arbitrage directly before Bitfinding in the same block; 17.602 ETH to coinbase, most of the 18.169 ETH winning bid"),
    other("Bitfinding (same whitehat, 2nd replay)", BOT_EOA, "0xa4ee77dbc66c" , 23717631, 13, "success", "replay of attacker A3 (0x8e260bf8, block 23717627), 4 blocks later"),
    other("Bitfinding (same whitehat, 3rd replay)", BOT_EOA, "0xed0c8654af36", 23717709, 2, "success", "replay of attacker A9 (0x2a0ead4e, block 23717706), 3 blocks later"),
    other("0x7bb28442 (copycat)", "0x7bb284421d3eafde4d45ee5e420c3269f87fa4fb", "0xe1d5f36f0aa6f6a07865ac4feaae5bda839f489372eb3ece7d53fb10100a1eb1", 23717399, 0, "success",
          "creation tx with A1 input (same 3-word diff) 2 blocks after A1, after Bitfinding drained the pools; paid 0.8166 ETH to coinbase (idx 4); net ~0"),
    other("0x7bb28442 (copycat)", "0x7bb284421d3eafde4d45ee5e420c3269f87fa4fb", "0x78ef0d388ab399dca877af4eb1eca244375456c1c75f07229e1f1c26abf4c596", 23717401, 1, "success", "second copy, 4 blocks after A1"),
    other("0x87a16382 (copy of A9)", "0x87a1638239a404487ade18800d2c8f1ea641e0fd", "0x32a604f4404bdda461e9bddbd9a2e62f1c9f01f4850cbed38bf1b47f334f22ef", 23717709, 1, "success",
          "replay of A9 (rsETH/WETH pool) 3 blocks after A9, 7.03 gwei priority, ahead of Bitfinding (idx 2) in that block"),
    other("0xedecee64 (late copier)", "0xedecee6406859724f369a2d11752dbfbf27d1aa0", "0x766569fdd544f2a4c0b1350dc9a04067697e7c5183b68ab0b0ce50b817df6c50", 23717911, 9, "success", "3 txs in blocks 23717911-23717950; small residues only (first tx shown)"),
    other("0x5b1a6bd4 (late copier, DAO-notified)", "0x5b1a6bd46852d298e0cfbbe556f8bb646995545e", "0xaf786f37c9d96ddfb0da98eafd2e79f4cd64b531284a9eed7f0c509f7c36a4b4", 23717997, 1, "success", "8 exploit-shaped creation txs 23717997-23718264 (first shown); took BPT tokens"),
    other("0xf49632e3 (exploit-shaped runs, DAO-notified)", "0xf49632e3e0f19935d579a403f637ca75e05e4543", "0x14fb45dd869208edffcb221add152a20292283be172ddb6ccfd2d73e3710b6f4", 23717662, 11, "success", "9 creation txs on pools the attacker did not touch; zero internal-balance delta (first shown)"),
    other("0x642cf741", "0x642cf74148c33820872c5e943a2bb538a0530f33", "0xd9ea231fc39b7c2e2b30289cb67691e47cc15665912c5dbd9392a507b3e71257", 23717978, 0, "success", "exploit-shaped run, zero internal-balance gain (2 txs; first shown)"),
    other("0x6949b0aa (public copy, reverted)", "0x6949b0aa93c0f21e0ff0f44935649f332d33208a", "0x6d021cb5468ca0fc0a1d60576af0c977c34754216143c03780dcdd2815c31808", 23718000, 84, "reverted", "public-mempool copy, out of gas; a second one reverted at 23718015 idx 103"),
    other("Yoink (post-hack arbitrage)", "0xfde0d1575ed8e06fbf36256bcdfa1f359281455a", "0xd8dd6cbcbb" , 23718188, 0, "success", "ordinary rebalancing arbitrage 2 h 38 m after A1; not a replay"),
]
# resolve abbreviated hashes against the incident file
full = {}
for b in inc["bots"]:
    for t in b["txs"]:
        full[t["hash"][:12]] = t["hash"]
for b in inc["other_racers"]:
    for t in b.get("txs", []):
        full[t["hash"][:12]] = t["hash"]
for b in bots_other:
    if len(b["tx"]) < 66:
        b["tx"] = full[b["tx"][:12]]
    assert len(b["tx"]) == 66, b

row = {
    "slug": SLUG, "name": inc["name"],
    "date_utc": race["block"]["timestamp_utc"].replace("+00:00", "Z"),
    "chain": "ethereum",
    "orig_verdict": inc["verdict"],
    "race_type_proposed": "post-failure-replay",
    "race_type_reason": "The attacker's creation tx (block 23717397, idx 1) had already landed and drained the pools; Bitfinding replayed the same creation input one block later (23717398, idx 2) to rescue residual balances, so it did not pre-empt anything. Replay confirmed on-chain (3 of 983 words differ).",
    "one_liner": "Balancer v2 mainnet: whitehat Bitfinding replayed the attacker's exploit input one block after it landed, rescued about 260 ETH-equivalent in this tx, and returned it to the DAO; a 10% bounty was paid on 2026-01-15.",
    "attacker": {
        "eoa": inc["attacker"]["eoas"][0]["address"], "eoas": [e["address"] for e in inc["attacker"]["eoas"]],
        "contracts": ["0x54b53503c0e2173df29f8da735fbd45ee8aba30d", "0x9c49fd8a06657928758f9921ff036aebd3636ad0", "0x399a8e046bc0e9dddd0e757a09af748d03d80e54", "0x7374fa9d1c12aa5a46a89800c37e7f47e3636bdd", "0x11986fb1709652d906b73c8f55e5634aaed84a0a"],
        "funding": "unknown",
        "funding_tx": inc["attacker"]["funding_tx"]["tx"], "deploy_tx": A1, "deploy_block": 23717397,
        "attack_txs": [
            {"hash": A1, "block": 23717397, "index": 1, "status": "success", "role": "A1: contract creation, exploit in constructor (osETH/WETH and wstETH/WETH pools drained into Vault internal balance); the racing attacker tx"},
            {"hash": "0xd155207261712c35fa3d472ed1e51bfcd816e616dd4f517fa5959836f5b48569", "block": 23717404, "index": 193, "status": "success", "role": "A2: stage-1 withdrawal of 6,587 WETH / 6,851 osETH / 4,260 wstETH from the Vault to the beneficiary"},
        ],
        "none_reason": None,
        "funding_note": "EOA1 first funded 2025-11-02 with 2.99985 ETH from 0x5babe600 (payout-style wallet, not Tornado Cash, type not verified). A second EOA 0x766a892f (same beneficiary 0xaa760d53) attacked other pools from block 23717522.",
    },
    "bot": {"label": "Bitfinding (whitehat; identity matched to BIP-892 by exact amounts)", "eoa": BOT_EOA, "contract": "0xdb8986fd3ff03182bd5fac4a8338ad6e6136fbf4",
            "tx": BOT_TX, "block": 23717398, "position": 2, "status": "success", "priority_fee_gwei": txs[BOT_TX]["priority_fee_gwei"]},
    "bots_other": bots_other,
    "evidence_level_mempool": "absent-from-archive",
    "mempool_note": "mempool-dumpster covers 2025-11-03 (csv only; no sourcelog published for the month) but neither the attacker's A1 nor any Bitfinding tx is in it (private flow or missed). First-seen of A1 and of the replay is unknown. Only four later attacker txs (A8-A9b) were seen publicly, and they were not pre-empted.",
    "trigger": {"kind": None, "tx": None, "first_seen_utc_ms": None, "first_seen_utc": None, "sources": None,
                "note": "A1 was never seen in the public mempool; Bitfinding reacted to the landed A1 (or a private view of it) one block later. No pre-inclusion first-seen exists."},
    "attacker_block": 23717397,
    "attacker_block_note": f"Attacker A1 {A1} landed at idx 1 of block 23717397 (07:46:47Z, built by Titan); the Bitfinding replay is in the next block, 12 s later.",
    "attacker_reference": {"kind": "attack-tx", "block": 23717397, "tx": A1},
    "auction": {**auction, "auction_note": "Block 23717398 was delivered by bloxroute-regulated from an unlabelled builder pubkey (bid 18.169 ETH, mostly the 17.602 ETH coinbase payment of the 0x240926d7 backrun at idx 1); the Bitfinding bundle (idx 2-4) paid 2 gwei priority (0.0584 ETH) and no coinbase transfer. For the attacker's own block 23717397 (race_23717397.json): Titan-built, delivered via ultrasound, bid 0.0502 ETH, with the 0xc0ffee445a22 backrun paying 20.596 ETH to the fee recipient at idx 2; the winning block's bids there are not retrievable."},
    "loot": {
        "scope": "bot-tx",
        "gross_loot_eth": round(gross, 6),
        "gross_loot_method": f"Assets taken by the replay contract 0xdb8986fd (created by 0x1dc60f91): {weth:.6f} WETH and {wst:.6f} wstETH withdrawn in idx 4 (tx 0x0d6f2d90) plus {osb:.6f} osETH withdrawn from its Vault internal balance on 2025-11-08 (tx 0xaa52c3a7, a call into the same contract). wstETH valued at stEthPerToken {r_wst:.6f} (stETH taken as 1 ETH), osETH at OsTokenVaultController.convertToAssets {r_os:.6f}, both eth_call at block 23717398. {bpt:.4f} osETH/wETH-BPT also withdrawn in 0xaa52c3a7 is NOT valued and not in this figure.",
        "captured_native": {"amount": f"{weth:.6f} WETH + {wst:.6f} wstETH + {osb:.6f} osETH (+ {bpt:.4f} osETH/wETH-BPT, unvalued)", "unit": "WETH+wstETH+osETH", "desc": "rescued by the creation-tx replay contract; the weETH, rETH and 0.144 WETH of Bitfinding's ~$964K total came from its later replays at 23717631 and 23717709"},
        "captured_usd": None, "captured_usd_source": None,
        "aggregate_bitfinding_mainnet_usd": 963832,
        "aggregate_bitfinding_mainnet_usd_source": "BIP-892 'Total Recovered (USD at the time of recovery)', Bitfinding, Ethereum Mainnet: $963,832 (all three replay bundles together, not this tx alone)",
        "coinbase_paid_eth": coinbase,
        "priority_fee_paid_eth": round(prio, 9),
        "builder_refund_to_bot_eth": refund,
        "builder_payout_to_victim_eth": None,
        "bot_net_eth": round(gross, 6),
        "loot_note": "Scope: the Bitfinding replay of A1 (tx 0x1dc60f91 at idx 2 plus its two follow-up txs at idx 3-4, same EOA and block); coinbase and priority fee are summed over those three txs. Bitfinding paid 2 gwei priority (0.058352 ETH), no coinbase transfer, and received no builder refund (no transfer from the fee recipient to the bot in the block). bot_net is the gross rescued value held before it was returned to the DAO multisig; it is a whitehat rescue, not profit. ETH-equivalents use on-chain exchange rates at block 23717398 (see method) so they are approximate. The attacker's own take (6,587 WETH / 6,851 osETH / 4,260 wstETH in A2) is a different scope.",
    },
    "fate": {
        "return_status": "returned",
        "returned_by_bot_eth": round(gross, 6),
        "returned_by_builder_eth": None,
        "returned_total_eth": round(net_ret, 6),
        "returned_to": "Balancer DAO multisig 0x10A19e7eE7d7F8a52822f6817de8ea18204F2e4f",
        "returned_desc": f"Bitfinding returned its mainnet recoveries to the DAO multisig: wstETH 10.956795 (block 23722968, 2025-11-04), WETH 136.000912 (block 23722994, 2025-11-04; includes 0.144 WETH from its third replay), osETH 105.208208 (block 23756834, 2025-11-08), plus rETH and weETH from its second replay. Balancer's post-mortem put the total at about $964K ($963,832 in BIP-892). The DAO paid the 10% whitehat bounty to 0xc3C7ccE1962B7a744847933CC3abD50b67ff5402 on {b_time[:10]} (tx 0xaa0de3c2, block 24237348). Row-level ETH-equivalents (this tx's three assets only): returned in full = {gross:.4f}; net of the 10% bounty = {net_ret:.4f}.",
        "bounty_kept_eth": round(bounty, 6),
        "bounty_desc": f"10% bounty on the whole Bitfinding mainnet return, paid by the DAO {b_time} (13.6001 WETH, 1.0957 wstETH, 0.6617 weETH, 0.6225 rETH, 10.5208 osETH); the figure here is 10% of this row's {gross:.4f} ETH-equivalent.",
        "kept_by_bot_eth": round(bounty, 6),
        "returned_txs": [
            {"tx": "0xf6e3db8ff335aa3859ad2686a339920a718a5db64390cda1295f8f84fb7f7bed", "eth": None, "note": "10.956795 wstETH Bitfinding -> DAO multisig", "block": 23722968, "time_utc": "2025-11-04T02:27:11Z"},
            {"tx": "0x1c20be7a609b53011cc569fc33d04ace7a4616de6efbf1c7bc1a72cd4f2909c9", "eth": None, "note": "136.000912 WETH Bitfinding -> DAO multisig (this row's share 135.857)", "block": 23722994, "time_utc": "2025-11-04T02:32:23Z"},
            {"tx": "0x60687df48ac95b49e3952c6bb8a5f08b6d9959b26e6f56d24319c6499fd475ce", "eth": None, "note": "105.208208 osETH Bitfinding -> DAO multisig", "block": 23756834, "time_utc": "2025-11-08T20:09:35Z"},
            {"tx": b0[0]["hash"], "eth": None, "note": "DAO multisig pays 10% bounty to Bitfinding recipient 0xc3C7ccE1 (five tokens)", "block": 24237348, "time_utc": b_time},
        ],
        "public_statement": "Balancer post-mortem (quoted by AMBCrypto): Bitfinding alone front-ran attackers on Ethereum Mainnet for $964,000; BIP-892 lists Bitfinding's mainnet recovery as $963,832 with a 10% bounty.",
    },
    "raw_refs": refs,
    "rawref_gaps": [
        {"field": "trigger.first_seen_utc_ms", "why": "A1 and all Bitfinding txs are absent from mempool-dumpster for 2025-11-03; first-seen unknown"},
        {"field": "auction.winning bid of attacker block 23717397", "why": "ultrasound bid history aged out; winning-block bids not retrievable (bot block 23717398 has 762 bids)"},
        {"field": "loot.osETH/wETH-BPT", "why": "45.015 BPT withdrawn in 0xaa52c3a7 not valued and not seen returned in Bitfinding's token transfers; fate unknown"},
    ],
    "discrepancies": [
        "incident.json lists 0x7bb28442 priority_fee_gwei 0.1214/0.1273; the race files show gas price = base fee, i.e. priority fee 0.0 (0.1214 is the base fee of the block).",
        "Bitfinding identity is by exact amount match to BIP-892 (the EOA is not printed there); the whole-incident $963,832 covers three replay bundles, only the first is this row.",
        f"Replay diff recomputed from data/raw/rpc-balancer2025 tx inputs: {len(diff_words)} of {n_words} 32-byte words differ (word indexes {diff_words}), matching incident.json.",
    ],
    "evidence_notes": [
        f"Bitfinding creation input vs attacker A1 input: same length (31,427 bytes), {len(diff_words)} of {n_words} words differ (indexes {diff_words}: beneficiary and owner address constants 0xaa760d53/0x506d1f9e -> 0x5af00b07); recomputed from data/raw/rpc-balancer2025/tx_<hash>.json.",
        "Same call shape on the same pools (0xdacf5fa1 osETH/WETH and 0x93d19926): 12 Vault staticcalls, 2 batchSwap-selector calls, 2 manageUserBalance calls; the idx 4 tx withdraws from the new contract's Vault internal balance (incidents/balancer-2025/race_23717398.json focus txs).",
        "Landing order: A1 at 23717397 idx 1, Bitfinding 23717398 idx 2-4; every replay on the same pool lands in a later block than the attacker, so this is a post-inclusion rescue (post-failure-replay), not pre-emption.",
        "Funds trail: tokentx of 0x5af00b07 shows the Vault paying out to it and the returns to the DAO multisig 0x10a19e7e; the bounty tx 0xaa0de3c2 (2026-01-15) in bal_bitf_bounty_tokentx.json matches BIP-892.",
        "0xc0ffee445a22 backrun at 23717397 idx 2 is an arbitrage next to A1 (tx-level facts only; not c0ffeebabe.eth).",
    ],
    "incident_dir": D,
}
# fix: use the full hash of the bounty tx from the saved file
row["fate"]["returned_txs"][3]["tx"] = b0[0]["hash"]
out = ROOT / "data" / "extract" / f"{SLUG}.json"
json.dump([row], open(out, "w"), indent=1)
print("wrote", out, "gross", gross, "net", net_ret, "prio", prio, "coinbase", coinbase, "refund", refund, "rates", r_wst, r_os, "diff", diff_words)
