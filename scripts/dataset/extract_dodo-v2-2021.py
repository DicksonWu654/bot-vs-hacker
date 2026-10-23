"""Extract row for dodo-v2-2021 -> data/extract/dodo-v2-2021.json (ONE row: Antelope vs Hippo at block 12000022). Run from project root."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _x6 import *

S = "dodo-v2-2021"
inc = load(f"incidents/{S}/incident.json")
r22 = load(f"incidents/{S}/race_12000022.json")
r102 = load(f"incidents/{S}/race_12000102.json")
r167 = load(f"incidents/{S}/race_12000167.json")
r171 = load(f"incidents/{S}/race_12000171.json")
r1452 = load(f"incidents/{S}/race_12001452.json")
ANT = "0xff9b3b2cb09d149762fcffc56ef71362bec1ef6a7d68727155c2d68f395ac1e8"
HIP = "0x4bc4ace313f2f5a411a5a560255ba0bba4f4913edb55ed882feaee84a3b1292e"
STAGE = "0xfbf6d8305660a2cb2282b94299c51acfc51860a39b1f63a758615492ba40109d"
disc = []

a_row = txrow(r22, ANT); h_row = txrow(r22, HIP)
fee = int(a_row["priority_fee_total_wei"]) / 1e18  # pre-London: whole gas fee

# loot from pool 0xfb609b68 token transfers in the Antelope tx
pt = res(load("data/raw/etherscan/dodo_pool_0xfb609b_tokentx.json"))
loot = {}
for x in pt:
    if x["hash"] == ANT and x["from"].lower().startswith("0xfb609b68"):
        loot[x["tokenSymbol"]] = int(x["value"]) / 10 ** int(x["tokenDecimal"])
assert abs(loot["WSZO"] - 955815.5419888108) < 1e-6 and abs(loot["USDT"] - 259939.363143) < 1e-6, loot

# init() calldata comparison between the Antelope tx and the attacker's tx (callTracer)
def calls(h, to_prefix, sel):
    t = load(f"data/raw/rpc/trace_{h}.json"); t = t.get("result", t)
    out = []
    def w(c):
        if c.get("to", "").lower().startswith(to_prefix) and c.get("input", "")[:10] == sel:
            out.append(c["input"])
        for x in c.get("calls") or []: w(x)
    w(t); return out
ia = calls(ANT, "0xfb609b68", "0x5039972a"); ih = calls(HIP, "0xfb609b68", "0x5039972a")
init_equal = bool(ia) and ia == ih
if not init_equal:
    disc.append("init() calldata in Antelope vs Hippo txs NOT byte-identical on recheck")

# returns by Antelope to 0xdad3e839
rt = res(load("data/raw/etherscan/dodo_recovery_tokentx.json"))
rets = []
want = {"0xf339a7081e", "0x3388d9fd4c", "0xcf047d3f83", "0x5c145b8ce5"}
for x in rt:
    if x["hash"][:12] in want and x["from"].lower().startswith("0x35541875"):
        amt = int(x["value"]) / 10 ** int(x["tokenDecimal"])
        rets.append({"tx": x["hash"], "eth": None, "block": int(x["blockNumber"]), "time_utc": iso(x["timeStamp"]),
                     "note": f"{amt:,.6f} {x['tokenSymbol']} from Antelope EOA 0x35541875 to 0xdad3e839 (token; not converted to ETH)"})
assert len(rets) == 4
et = [x for x in res(load("data/raw/etherscan/dodo_recovery_txlist.json")) if x["hash"].startswith("0xd9984c36")][0]
eth_ret = int(et["value"]) / 1e18
rets.append({"tx": et["hash"], "eth": eth_ret, "block": int(et["blockNumber"]), "time_utc": iso(et["timeStamp"]),
             "note": "114.50682 ETH from Antelope EOA 0x35541875 to 0xdad3e839"})
assert abs(eth_ret - 114.50682) < 1e-9

def brow(race, h, label, role, eoa=None):
    t = txrow(race, h)
    return {"label": label, "eoa": t["from"], "tx": h, "block": race["block"]["number"], "position": t["index"],
            "status": "success" if t["status"] == 1 else "reverted", "role": role + f" ({t['gas_price_gwei']:.2f} gwei)"}
others = [
 brow(r102, "0x0b062361e16a2ea0942cc1b4462b6584208c8c864609ff73aaa640aaa2d92428", "Antelope",
      "second win on pool 0xfd87ab87 (ETHA/USDT), block 12000102 index 0; Hippo's attack 0x0430d5a2 at index 4 (600 gwei) reverted"),
 brow(r167, "0x75d4765dd704d82f0bf539da88aff2568da38697f153b14d285abc8749da683f", "Cheetah",
      "block 12000167 index 1: replays Hippo's pending withdraw(USDT) call on his own bypass contract 0x910fd17b via proxy 0xa57bd001 (inner calldata byte-identical per incident.json); Hippo's own withdraw 0x14084fba at index 77 (142 gwei) got 0; took 1,139,456.204 USDT"),
 brow(r167, "0xbfe6df9308df38661b817cb56da5cacca468e894472a291d6e17d2eb7ab4e24b", "Antelope",
      "block 12000167 index 4: replayed the same withdraw(USDT) call at 652.17 gwei, behind Cheetah's 684.25 gwei, and ran out of gas"),
 brow(r171, "0xa8d030494607e16b06dd0c7e97da2b78ebc5a072a8176b19ca57f17044c1a211", "Cheetah",
      "block 12000171 index 3: replays Hippo's pending withdraw(wCRES) on 0x910fd17b; Hippo's own withdraw 0x021a2bd6 at index 78 got 0; took 133,548.939 wCRES"),
 brow(r1452, "0x561f7ccb27b9928df33fa97c2fb99ea3750593e908f9f0f8baf22ec7ca0c5c4a", "Antelope",
      "block 12001452 index 1: DIFFERENT race (pool 0x236116ff vs fresh EOA 0x3984e3a7), not Hippo's; listed because folklore attributes its 8.1 ETH fee to this incident"),
 brow(r1452, "0x4151a5051d34dcec0bc95458a7e7140381f91f0681f3839b741714714b1d4760", "Cheetah",
      "block 12001452 index 3: lost to Antelope on the same other pool (inner call reverted, nothing captured)"),
]
# fix: for Cheetah 12001452 tx status is 1 with inner revert; keep status as reported by receipt

ant_other_eoa = a_row["from"]
refs = {
 "bot.block": "data/raw/rpc/block_12000022.json", "bot.position": "data/raw/rpc/block_12000022.json",
 "attacker_block": "data/raw/rpc/receipts_12000022.json",
 "loot.coinbase_paid_eth": "data/raw/rpc/trace_block_12000022.json",
 "loot.priority_fee_paid_eth": ["data/raw/rpc/receipts_12000022.json", "data/raw/rpc/block_12000022.json"],
 "loot.captured_native": "data/raw/etherscan/dodo_pool_0xfb609b_tokentx.json",
 "fate.returned": ["data/raw/etherscan/dodo_recovery_tokentx.json", "data/raw/etherscan/dodo_recovery_txlist.json"],
 "attacker.funding_tx": "data/raw/etherscan/dodo_hippo_txlist.json",
 "public_statement": "data/raw/web/chaincatcher_2060103.html",
 "init_calldata_comparison": [f"data/raw/rpc/trace_{ANT}.json", f"data/raw/rpc/trace_{HIP}.json"],
}
row = {
 "slug": S, "name": inc["name"], "date_utc": iso(r22["block"]["timestamp"]), "chain": "ethereum",
 "orig_verdict": inc["verdict"],
 "race_type_proposed": "beat-pending-attack",
 "race_type_reason": "Antelope's flashLoan+init() tx (index 4, 243 gwei) calls pool.init() with calldata byte-identical to the attacker's pending tx and drains the pool the attacker had staged one block earlier; the attacker's tx at index 176 (132 gwei) in the same block reverted. Ordering is by gas price in the public mempool.",
 "one_liner": "Antelope, a generic flash-loan bot, replayed the DODO attacker's init() call at index 4 of block 12000022 and took 955,815 WSZO + 259,939 USDT; the attacker's tx at index 176 reverted. Antelope later returned most of its takes. Pre-Merge, in-block evidence only.",
 "attacker": {"eoa": "0x368a6558255bccac517da5106647d8182c571b23", "eoas": inc["attacker"]["eoas"], "contracts": [c.split(" ")[0] for c in inc["attacker"]["contracts"]],
              "funding": "unknown", "funding_tx": inc["attacker"]["funding_tx"]["hash"],
              "deploy_tx": inc["attacker"]["deploy_tx"]["main"], "deploy_block": 11999896,
              "attack_txs": [
                {"hash": STAGE, "block": 12000020, "index": 117, "status": "success", "role": "stage: moves 965,470.24 fake FDO + 262,565.01 fake FUSDT into pool 0xfb609b68 (131 gwei)"},
                {"hash": HIP, "block": 12000022, "index": h_row["index"], "status": "reverted", "role": "attack tx: flashLoan + callback init(FDO,FUSDT,...) on the staged pool; reverted because Antelope had already drained it"}],
              "none_reason": None},
 "bot": {"label": "Antelope", "eoa": a_row["from"], "contract": a_row["to"], "tx": ANT, "block": 12000022, "position": a_row["index"],
         "status": "success" if a_row["status"] == 1 else "reverted", "priority_fee_gwei": a_row["priority_fee_gwei"]},
 "bots_other": others,
 "evidence_level_mempool": "in-block-only",
 "mempool_note": "In-block evidence only: pre-Merge (March 2021), mempool-dumpster starts 2023-08-07, so no first-seen time exists for the attacker's tx. The race is decided by gas price (243 vs 132 gwei), not by a builder auction; no coinbase payments in any tx.",
 "trigger": {"kind": None, "tx": None, "first_seen_utc_ms": None, "first_seen_utc": None, "sources": None,
             "note": "No mempool first-seen exists (pre-Merge, no archive). The attacker's stage tx landed in block 12000020 and his attack tx 0x4bc4ace3 was in the same block 12000022 as Antelope's; the stage (fake tokens sitting in the pool) was visible on chain two blocks earlier."},
 "attacker_block": 12000022,
 "attacker_block_note": "Attacker's attack tx 0x4bc4ace3 landed in the SAME block (index 176, 132 gwei) and reverted behind Antelope's index-4 tx. The attacker's stage tx was in block 12000020.",
 "attacker_reference": {"kind": "attack-tx", "block": 12000022, "tx": HIP},
 "auction": bvh.auction_summary(f"incidents/{S}/race_12000022.json", ANT),
 "loot": {
   "scope": "bot-tx",
   "gross_loot_eth": None,
   "gross_loot_method": "not priced: WSZO has no price in our data and the incident gives no ETH/USD conversion for this pool; not invented",
   "captured_native": {"amount": f"{loot['WSZO']:,.4f} WSZO + {loot['USDT']:,.6f} USDT", "unit": "WSZO+USDT", "desc": "token transfers from pool 0xfb609b68 (WSZO/USDT crowdpool) to Antelope's contract 0x00000000e84f in tx 0xff9b3b2c"},
   "captured_usd": None, "captured_usd_source": None,
   "coinbase_paid_eth": 0.0, "priority_fee_paid_eth": fee,
   "builder_refund_to_bot_eth": None, "builder_payout_to_victim_eth": None, "bot_net_eth": None,
   "loot_note": "incident.json states no USD value for this pool's loot. The 259,939 USDT leg is about $259.9K at par; the WSZO leg is unpriced. DODO's postmortem totals roughly $3.8M across all pools. priority_fee_paid_eth is the whole gas fee (pre-London: gasUsed x gasPrice = 183,815 x 243.1 gwei); there are no coinbase payments. This row covers the Antelope tx only; the wider incident (other pools, Cheetah's USDT/wCRES) is in bots_other and incident.json."},
 "fate": {
   "return_status": "partial",
   "returned_by_bot_eth": None, "returned_by_builder_eth": None, "returned_total_eth": None,
   "returned_to": "0xdad3e839ba4a48faf54f3aa187d8b6b8646e6224 (recovery wallet per incident.json; presumed DODO side)",
   "returned_desc": "Antelope's EOA returned, on 2021-03-10 00:26-00:39 UTC (blocks 12007525-12007572), 955,815.54 WSZO (all of this row's WSZO), 101,548.43 ETHA, 1,000 wCRES, 296,009 USDT and 114.50682 ETH to 0xdad3e839 (verified in the saved Etherscan files). Antelope took 259,939 + 326,070 USDT in the two DODO races, so the USDT return is not a full match and was not reconciled. Cheetah's ~$1.89M return is reported by DODO's postmortem; no matching on-chain return was found. Token returns are not converted to ETH here.",
   "bounty_kept_eth": None, "bounty_desc": None, "kept_by_bot_eth": None,
   "returned_txs": rets,
   "public_statement": "DODO postmortem (via ChainCatcher translation): 'Mr. Antelope' anonymously emailed on March 10 offering to return funds (about $1.2 million); 'Mr. Cheetah' returned $1.89 million around March 9 21:00 Beijing time. Postmortem calls Antelope's bot a 'Universal Trading Bot' that automatically front-ran Hippo."},
 "raw_refs": refs,
 "rawref_gaps": [{"field": "fate.returned_by_bot_eth / returned_total_eth", "why": "returns are mostly tokens (WSZO, ETHA, wCRES, USDT) with no price source in the saved data; only the 114.50682 ETH leg is ETH-denominated (see returned_txs)"},
                 {"field": "loot.captured_usd / gross_loot_eth", "why": "incident.json states no USD for this pool; WSZO unpriced"},
                 {"field": "Cheetah return", "why": "reported only, no on-chain return tx located"}],
 "discrepancies": disc + [
   "initial incident notes placed Cheetah at 12000165/12001452; on chain Cheetah's wins are blocks 12000167 (index 1, tx 0x75d4765d) and 12000171 (index 3, tx 0xa8d03049). Block 12000165 holds the ATTACKER's bypass attack (index 3); 12001452 is Cheetah losing to Antelope on a different pool.",
   "Antelope's 12001452 tx (93,148 gwei, 8.128 ETH fee) is not the Hippo race; the postmortem's '90,000 gwei / 8 ETH' folklore refers to it.",
   "The 114.5 ETH Antelope returned is not tied to any priced take in the saved data (ETH-equivalent of the token returns is unknown)."],
 "evidence_notes": [
   f"pool.init() (selector 0x5039972a) calldata in Antelope's tx 0xff9b3b2c and the attacker's reverted tx 0x4bc4ace3 is {'byte-identical' if init_equal else 'NOT identical'} (522 hex chars each, same pool 0xfb609b68, incl. the attacker's fake FDO/FUSDT) -- checked from data/raw/rpc/trace_<tx>.json.",
   "The flashLoan frames differ only in assetTo/data and by 99 wei in amounts: Antelope's tx is an adapted replay with its own contract and callback, not a byte copy (incidents/dodo-v2-2021/incident.json bots[0].replay_evidence).",
   "Block 12000022: Antelope index 4 at 243.1 gwei (status success), attacker index 176 at 132 gwei (reverted); the attacker had staged the fake tokens in block 12000020 (race_12000022.json, race_12000020.json).",
   "Same pattern in block 12000102: Antelope index 0 at 1883 gwei vs the attacker's index 4 at 600 gwei (reverted). Cheetah replayed the attacker's own withdraw calldata in blocks 12000167/12000171 (race_12000167.json, race_12000171.json).",
   "Pre-Merge: no coinbase payments and no mempool archive; ordering is gas-price based."],
 "incident_dir": f"incidents/{S}",
}
write(S, [row])
