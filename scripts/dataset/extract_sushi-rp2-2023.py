"""Extract sushi-rp2-2023 -> data/extract/sushi-rp2-2023.json (incident dataset). Run from project root: .venv/bin/python scripts/dataset/extract_sushi-rp2-2023.py
One row. Every figure is recomputed from saved raw files (rpc logs/traces/blocks, etherscan lists) and asserted against incident.json."""
import json, pathlib, sys, glob, datetime, collections
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import bvh

SLUG = "sushi-rp2-2023"
D = f"incidents/{SLUG}"
E18 = 10 ** 18
J = lambda p: json.load(open(ROOT / p))
iso = lambda ts: datetime.datetime.fromtimestamp(int(ts), datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
res = lambda d: d["result"] if isinstance(d, dict) else d

inc = J(f"{D}/incident.json")
BOT_TX = "0xb8f57cf82b7057d9d03f1500e3f0ce46980388c3b13ff317f1c617d932313386"
TRUST_TX = "0x43ff7e01423044cfb501b4fe9ef1386725c0ddc117dadd6e6620cb68bdeaf4f9"
VICTIM = "0x31d3243cfb54b34fc9c73e1cb1137124bd6b13e1"
MSIG = "0x19b3eb3af5d93b77a5619b047de0eed7115a19e7"
YOINK = "0xfde0d1575ed8e06fbf36256bcdfa1f359281455a"
CBABE = "0xc0ffeebabe5d496b2dde509f9fa189c25cf29671"

# ---- race files / tx table (blocks 17007838-17007856 + 17007936)
races = {}
txs = {}
for f in sorted(glob.glob(ROOT.as_posix() + f"/{D}/race_*.json")):
    r = json.load(open(f))
    races[r["block"]["number"]] = r
    for t in r["txs"]:
        txs[t["hash"]] = (r["block"]["number"], t)

# ---- victim WETH pulls (eth_getLogs: WETH Transfer from victim)
LOGS = "data/raw/rpc/sushi_weth_transfers_from_victim_31d3_17007830_17007900.json"
pulls = collections.OrderedDict()
for l in res(J(LOGS)):
    h = l["transactionHash"]
    pulls[h] = pulls.get(h, 0) + int(l["data"], 16) / E18
assert len(res(J(LOGS))) == 18 and abs(sum(pulls.values()) - 1800.0) < 1e-9 and len(pulls) == 11
pull_txs = sorted(pulls, key=lambda h: (txs[h][0], txs[h][1]["index"]))
assert pull_txs[0] == BOT_TX

cb_total = sum(int(txs[h][1]["coinbase_transfer_wei"]) for h in pull_txs) / E18
pf_pull = sum(int(txs[h][1]["priority_fee_total_wei"]) for h in pull_txs) / E18
BUNDLE_TX = "0x09f4af54452dc76082ba1b2a7096b2aa338af1a8ec9573095180b820b2ec6e06"   # c0ffeebabe 17007856 idx 4: gas-price payment tx
bt = txs[BUNDLE_TX][1]
assert bt["from"] == CBABE and bt["coinbase_transfer_wei"] == "0" and txs[BUNDLE_TX][0] == 17007856
bundle_eth = int(bt["priority_fee_total_wei"]) / E18
paid_total = cb_total + pf_pull + bundle_eth
ps = inc["payments_summary"]
assert abs(paid_total - ps["total_paid_to_builders_and_proposers_eth"]) < 1e-9, paid_total
assert abs(cb_total - ps["coinbase_transfers_eth"]) < 1e-9 and abs(pf_pull - ps["priority_fees_eth"]) < 1e-12
share = paid_total / 1800.0

def actor_cb(frm):
    return sum(int(txs[h][1]["coinbase_transfer_wei"]) for h in pull_txs if txs[h][1]["from"] == frm) / E18
y_cb, c_cb = actor_cb(YOINK), actor_cb(CBABE)
assert abs(y_cb - 20.0) < 1e-12 and abs(c_cb - 688.88) < 1e-12
y_pull = sum(pulls[h] for h in pull_txs if txs[h][1]["from"] == YOINK)
c_pull = sum(pulls[h] for h in pull_txs if txs[h][1]["from"] == CBABE)
assert y_pull == 400.0 and c_pull == 1000.0

# ---- returns (etherscan lists + victim inbound)
def find(path, h, key="hash"):
    for x in res(J(path)):
        if x[key].startswith(h):
            return x
TT = "data/raw/etherscan/tokentx_0x31d3243c_17007838_17030000.json"
VTX = "data/raw/etherscan/txlist_0x31d3243c_17007700_17030000.json"
MTX = "data/raw/etherscan/txlist_0x19b3eb3a_17007838_17200000.json"
MINT = "data/raw/etherscan/txlistinternal_0x19b3eb3a_17011000_17100000.json"
t1, t2 = find(TT, "0x6fda1a6de9a5"), find(TT, "0xb76b11ae23c4")
assert t1["from"] == "0x9deff3637e583c7d2bffc7164dc2ca630d0ab7cb" and t1["to"] == VICTIM and t2["to"] == VICTIM
trust_ret = int(t1["value"]) / E18 + int(t2["value"]) / E18
assert trust_ret == 90.0
bs = find(VTX, "0xe9af60755f17")
assert bs["to"] == VICTIM and bs["blockNumber"] == "17009958"
blocksec_ret = int(bs["value"]) / E18
c1, c2 = find(MTX, "0x8de62a554925"), find(MTX, "0x09f2e3864e35")
assert c1["from"] == CBABE and c2["from"] == CBABE and c1["to"] == MSIG and c1["isError"] == "0" and c2["isError"] == "0"
c_ret = (int(c1["value"]) + int(c2["value"])) / E18
y_ok = find(MTX, "0xbefe5711e709"); y_fail = find(MTX, "0x7b6eb36aacdc")
assert y_ok["from"] == YOINK and y_ok["isError"] == "0" and y_fail["isError"] == "1"
y_ret = int(y_ok["value"]) / E18
ms = find(MINT, "0x9d729a490301")
assert ms["from"] == MSIG and ms["to"] == VICTIM
msig_ret = int(ms["value"]) / E18
assert y_ret == 380.0 and abs(c_ret - 305.31898072099295) < 1e-9 and msig_ret == 685.0 and blocksec_ret == 100.0
returned_total = trust_ret + blocksec_ret + msig_ret
assert returned_total == 875.0
bots_to_msig = y_ret + c_ret
c_remainder = c_pull - c_cb - bundle_eth - c_ret
assert abs(c_remainder - 4.801019999999994) < 1e-5, c_remainder
y_remainder = y_pull - y_cb - sum(int(txs[h][1]["priority_fee_total_wei"]) for h in pull_txs if txs[h][1]["from"] == YOINK) / E18 - y_ret

# ---- builder -> bot refund scan (blocks 17007838-17007856 + 17007842 trace): none
bots_addr = {a.lower() for a in (
    YOINK, CBABE, "0x719cdb61e217de6754ee8fc958f2866d61d565cf", "0xc9c5b86993b1a72dca6082b2d34210afe19c7ccf",
    "0xcff8bdf57f4e62c1d4f82420b8a1cad70d5bf383", "0x869238b19ea39a1943ef8ebbc10f25682dc7c47a",
    "0xd050e0a4838d74769228b49dff97241b4ef3805d", "0x2b3bdb6c2479961a8ded16f7f1ddca16cca26a29", "0xf9a001d5b2c7c5e45693b41fcf931b94e680cac4",
    "0xfb3e62b5ac5c843454ce73c31b83ca991417c86b", "0x000000c0524f353223d94fb76efab586a2ff8664", "0x384be939cf8317f6b570815c7f8e95c54ed6aa85",
    "0xaffc8c3cd3ecf8839d4731a2335f868733f9ec90", "0x9deff3637e583c7d2bffc7164dc2ca630d0ab7cb")}
refund_n = 0
for n in (17007838, 17007839, 17007840, 17007841, 17007842, 17007855, 17007856):
    b = J(f"data/raw/rpc/block_{n}.json")["result"]
    for t in b["transactions"]:
        if t["to"] and t["to"].lower() in bots_addr and t["from"].lower() not in bots_addr and int(t["value"], 16) > 0:
            refund_n += 1
for n in (17007839, 17007842):
    for t in J(f"data/raw/rpc/trace_block_{n}.json")["result"]:
        a = t.get("action", {})
        if a.get("to", "").lower() in bots_addr and a.get("from", "").lower() not in bots_addr and int(a.get("value", "0x0"), 16) > 0:
            refund_n += 1
assert refund_n == 0

# ---- bot tx (Yoink first pull) + Trust's pre-empted tx
rb = races[17007838]
bt0 = txs[BOT_TX][1]
assert bt0["index"] == 23 and bt0["status"] == 1 and txs[BOT_TX][0] == 17007838
trust_blk, trust = txs[TRUST_TX]
assert trust_blk == 17007839 and trust["index"] == 54 and trust["status"] == 1
blk839 = J("data/raw/rpc/block_17007839.json")["result"]
tt = next(t for t in blk839["transactions"] if t["hash"] == TRUST_TX)
trust_maxfee = int(tt["maxFeePerGas"], 16) / 1e9
base838 = rb["block"]["base_fee_gwei"]
assert trust_maxfee < base838 and abs(trust_maxfee - 18.87241034) < 1e-8 and abs(base838 - 18.877867443) < 1e-9
assert int(tt["transactionIndex"], 16) == 54

auc = bvh.auction_summary(f"{D}/race_17007838.json", BOT_TX)
assert auc["n_bids"] in (0, None)
a39 = bvh.auction_summary(f"{D}/race_17007839.json")
a42 = bvh.auction_summary(f"{D}/race_17007842.json")
r42 = races[17007842]
i0 = next(t for t in r42["txs"] if t["index"] == 0); i1 = next(t for t in r42["txs"] if t["index"] == 1)
assert i0["from"] == CBABE and i1["from"] == YOINK
auc["auction_note"] = (
    "Bot block 17007838 (slot 6181974) is a vanilla non-MEV-Boost block: no relay delivered it and relays hold no bid history, so there is no auction for "
    "Yoink's first pull itself. The copy auction started in the next blocks. Block 17007839 (builder0x69, delivered via agnostic): %d bids on the Flashbots relay, "
    "winning bid %.2f ETH, of which 107.096 ETH was the three searchers' direct coinbase payments (0x719cdb61 %.2f, Yoink 10, 0xc9c5b869 5.1) paid straight to the "
    "proposer fee recipient 0x388c818c (the block fee recipient). Block 17007842 (beaverbuild.org, delivered via agnostic): %d bids, winning bid %.2f ETH "
    "(proposer payment tx 0xcf3cd767...), made of c0ffeebabe's idx 0 tx (coinbase transfer %.2f ETH) and Yoink's idx 1 tx (10 ETH), %.2f ETH in total to the beaverbuild fee recipient. "
    "These figures are other blocks' race files and are NOT part of this block's auction fields."
) % (a39["n_bids"], a39["winning_bid_eth"], int(txs["0xea3480f1f1d1f0b32283f8f282ce16403fe22ede35c0b71a732193e56c5c45e8"][1]["coinbase_transfer_wei"]) / E18,
     a42["n_bids"], a42["winning_bid_eth"], int(i0["coinbase_transfer_wei"]) / E18, (int(i0["coinbase_transfer_wei"]) + int(i1["coinbase_transfer_wei"])) / E18)
missing_auc = auc.pop("_missing_raw", [])

# ---- other pulling txs -> bots_other
LABEL = {YOINK: "Yoink", CBABE: "c0ffeebabe.eth", "0x719cdb61e217de6754ee8fc958f2866d61d565cf": "searcher 0x719cdb61",
         "0xc9c5b86993b1a72dca6082b2d34210afe19c7ccf": "searcher 0xc9c5b869", "0xcff8bdf57f4e62c1d4f82420b8a1cad70d5bf383": "BlockSec rescue",
         "0x869238b19ea39a1943ef8ebbc10f25682dc7c47a": "Trust (white hat)"}
others = []
for h in pull_txs[1:]:
    blk, t = txs[h]
    role = "pulled %d x 100 WETH from the victim; coinbase transfer %.4f ETH" % (round(pulls[h] / 100), int(t["coinbase_transfer_wei"]) / E18)
    if h == TRUST_TX:
        role = ("white-hat rescue tx that every report calls the original; pulled 100 WETH one block AFTER Yoink's first pull; max fee %.4f gwei was below 17007838 base fee %.4f gwei, so it was pending and "
                "could not be included in 17007838; Trust returned 90 WETH" % (trust_maxfee, base838))
    others.append({"label": LABEL[t["from"]], "eoa": t["from"], "tx": h, "block": blk, "position": t["index"], "status": "success" if t["status"] == 1 else "reverted", "role": role})

# ---- raw refs
RPC = "data/raw/rpc"
refs = {
    "bot.block": f"{RPC}/block_17007838.json", "bot.position": f"{RPC}/block_17007838.json",
    "attacker_block": [f"{RPC}/block_17007839.json", f"{RPC}/block_17007838.json"],
    "loot.gross_loot_eth": LOGS,
    "loot.coinbase_paid_eth": [f"{RPC}/trace_block_{n}.json" for n in (17007838, 17007839, 17007840, 17007841, 17007842, 17007855, 17007856)],
    "loot.priority_fee_paid_eth": [f"{RPC}/receipts_{n}.json" for n in (17007838, 17007839, 17007840, 17007842, 17007856)] + [f"{RPC}/block_{n}.json" for n in (17007838, 17007839, 17007840, 17007842, 17007856)],
    "loot.builder_refund_to_bot_eth": [f"{RPC}/block_{n}.json" for n in (17007838, 17007839, 17007840, 17007841, 17007842, 17007855, 17007856)] + [f"{RPC}/trace_block_17007839.json", f"{RPC}/trace_block_17007842.json"],
    "loot.bot_net_eth": [LOGS] + [f"{RPC}/trace_block_{n}.json" for n in (17007839, 17007840, 17007842, 17007856)] + [f"{RPC}/receipts_17007856.json"],
    "loot.captured_usd": "data/raw/web-curve-sushi/blocksec_sushi_incident_8.html",
    "fate.returned_by_bot_eth": [MTX, "data/raw/etherscan/txlistinternal_0xc0ffeeba_17007800_17060000.json"],
    "fate.returned_total_eth": [TT, VTX, MINT],
    "fate.kept_by_bot_eth": [LOGS, MTX] + [f"{RPC}/trace_block_{n}.json" for n in (17007840, 17007842, 17007856)],
}
for tag in ("0x6fda1a6de9a5", "0xb76b11ae23c4"):
    pass
assert abs(y_remainder) < 0.001
returned_txs = [
    {"tx": t1["hash"], "eth": int(t1["value"]) / E18, "note": "Trust (white hat) returns 10 WETH to the victim", "block": int(t1["blockNumber"]), "time_utc": iso(t1["timeStamp"])},
    {"tx": t2["hash"], "eth": int(t2["value"]) / E18, "note": "Trust (white hat) returns 80 WETH to the victim (total 90 of 100 pulled)", "block": int(t2["blockNumber"]), "time_utc": iso(t2["timeStamp"])},
    {"tx": bs["hash"], "eth": blocksec_ret, "note": "BlockSec rescue returns 100 ETH to the victim (sender 0x00000035...)", "block": int(bs["blockNumber"]), "time_utc": iso(bs["timeStamp"])},
    {"tx": c1["hash"], "eth": int(c1["value"]) / E18, "note": "c0ffeebabe.eth sends 1.0 ETH to the Sushi multisig 0x19b3eb3a", "block": int(c1["blockNumber"]), "time_utc": iso(c1["timeStamp"])},
    {"tx": c2["hash"], "eth": int(c2["value"]) / E18, "note": "c0ffeebabe.eth sends 304.31898 ETH to the Sushi multisig (total 305.31898)", "block": int(c2["blockNumber"]), "time_utc": iso(c2["timeStamp"])},
    {"tx": y_ok["hash"], "eth": y_ret, "note": "Yoink sends 380 ETH to the Sushi multisig (an identical earlier send %s at block %s reverted)" % (y_fail["hash"], y_fail["blockNumber"]), "block": int(y_ok["blockNumber"]), "time_utc": iso(y_ok["timeStamp"])},
    {"tx": ms["hash"], "eth": msig_ret, "note": "Sushi multisig pays 685 ETH to the victim (internal call; equals the 305.319 + 380 received, rounded)", "block": int(ms["blockNumber"]), "time_utc": iso(ms["timeStamp"])},
]
assert returned_txs[-1]["time_utc"] == "2023-04-17T15:39:35Z"

rawref_gaps = [
    {"field": "loot.builder_payout_to_victim_eth", "why": "no builder -> victim pass-through exists in this incident (set null, not 0)"},
    {"field": "fate.returned_by_builder_eth", "why": "no builder return was seen in the victim's inbound lists to block 17030000, but the saved lists do not cover builder-side flows afterwards; left null"},
    {"field": "trigger.first_seen_utc_ms", "why": "no mempool archive before 2023-08-07; Trust's pending tx has no public first-seen time"},
    {"field": "attacker.funding_tx", "why": "Trust is a white hat, not an attacker; funding tx 0x3dfaaf04... is listed in incident.json only for completeness and is not part of the race"},
]
disc = [
    "incident.json lists c0ffeebabe at 689.88 ETH (688.88 coinbase + 1.0 gas-price payment tx 0x09f4af54 at 17007856 idx 4); the coinbase-only figure is 688.88 (10 at 17007840 + 678.88 at 17007842 idx 0). Both reproduce from traces; coinbase_paid_eth here (805.976) excludes the 1.0 ETH gas-price payment, which is in priority_fee_paid_eth (1.0043 = 1.0 + 0.00435 on the 11 pulling txs).",
    "incident.json funds_fate says c0ffeebabe returned 305.31898 ETH in 'tx 0x8de62a55... + 0x09f2e386...': verified (1.0 + 304.31898 ETH to the Sushi multisig). The multisig then paid the victim 685.0, so 0.319 ETH of the bots' 685.319 ETH stayed at the multisig in that tx.",
    "BlockSec 100 ETH is native ETH from 0x00000035... into the victim (txlist, block 17009958); Trust's 90 is WETH (ERC-20). Both are counted 1:1 as ETH-equivalent.",
]
row = {
    "slug": SLUG, "name": inc["name"],
    "date_utc": rb["block"]["timestamp_utc"].replace("+00:00", "Z"),
    "chain": "ethereum",
    "orig_verdict": inc["verdict"],
    "race_type_proposed": "beat-whitehat-or-user",
    "race_type_reason": ("There is no hostile attacker: the tx all reports call the original (0x43ff7e01...) was a white-hat rescue by Trust. Yoink pulled 100 WETH in 17007838 using the same route bytes (only the 20-byte fake-pool address differs), "
                         "one block before Trust's still-pending tx could be included (its max fee was below that block's base fee)."),
    "one_liner": "Yoink copied the white hat Trust's still-pending RouteProcessor2 rescue one block early (17007838 idx 23); the copy frenzy then sent 44.8% of the 1,800 WETH pulled to the block auction, and 875 ETH was later returned.",
    "attacker": {"eoa": None, "eoas": [], "contracts": [], "funding": "n/a", "funding_tx": None, "deploy_tx": None, "deploy_block": None,
                 "attack_txs": [{"hash": TRUST_TX, "block": 17007839, "index": 54, "status": "success",
                                 "role": "white-hat rescue tx by Trust (0x869238b1...), pending when Yoink pulled in 17007838; NOT a hostile attack"}],
                 "none_reason": ("No hostile attacker tx exists in public history: the first pull by anyone is Yoink's (17007838 idx 23), and the tx reports call the original is the white hat Trust's rescue of the victim's approved WETH "
                                 "(incident.json attacker.role). In-block evidence only: no mempool archive before 2023-08-07, so whether anyone else saw the vulnerability earlier is unknown.")},
    "bot": {"label": "Yoink", "eoa": YOINK, "contract": "0xd050e0a4838d74769228b49dff97241b4ef3805d", "tx": BOT_TX, "block": 17007838, "position": 23,
            "status": "success", "priority_fee_gwei": bt0["priority_fee_gwei"]},
    "bots_other": others,
    "evidence_level_mempool": "in-block-only",
    "mempool_note": "In-block evidence only: no mempool archive exists before 2023-08-07 and Trust's pending tx has no public first-seen time. That the tx was pending is inferred from its max fee (18.8724 gwei) being below the 17007838 base fee (18.8779 gwei), which makes it unincludable in that block.",
    "trigger": {"kind": None, "tx": None, "first_seen_utc_ms": None, "first_seen_utc": None, "sources": None,
                "note": "Trigger is presumably Trust's pending rescue tx %s but no first-seen time exists (pre-archive); not filled." % TRUST_TX},
    "attacker_block": 17007839,
    "attacker_block_note": ("Block in which the copied white-hat tx (Trust 0x43ff7e01..., idx 54) landed: 17007839, one block after Yoink's first pull; its max fee (%.5f gwei) < 17007838 base fee (%.5f gwei), so it could not land in 17007838. Not a hostile attacker's block." % (trust_maxfee, base838)),
    "attacker_reference": {"kind": "attack-tx", "block": 17007839, "tx": TRUST_TX},
    "auction": auc,
    "loot": {
        "scope": "all-bots-in-incident",
        "gross_loot_eth": 1800.0,
        "gross_loot_method": "sum of the 18 WETH Transfer logs out of the victim 0x31d3243c in blocks 17007838-17007856 (11 txs), WETH counted 1:1 as ETH",
        "captured_native": {"amount": 1800.0, "unit": "WETH", "desc": "18 pulls of 100 WETH from one wallet's RouteProcessor2 approval across 11 txs by 6 actors"},
        "captured_usd": 3300000.0,
        "captured_usd_source": "BlockSec blog 'about $3.3 million' total loss (reported; saved page data/raw/web-curve-sushi/blocksec_sushi_incident_8.html)",
        "coinbase_paid_eth": cb_total,
        "priority_fee_paid_eth": pf_pull + bundle_eth,
        "builder_refund_to_bot_eth": 0.0,
        "builder_payout_to_victim_eth": None,
        "bot_net_eth": 1800.0 - paid_total,
        "loot_note": ("Scope: all bots in the incident (11 pulling txs), not just Yoink's first tx. Payments to the auction %.3f ETH = %.1f%% of 1,800 (BlockSec's reported 44.5%% reproduces): coinbase transfers %.3f + priority fees on the 11 pulling txs %.5f + "
                      "1.0 ETH gas-price payment tx 0x09f4af54 (c0ffeebabe, 17007856 idx 4). bot_net_eth = 1800 - payments, before gas base fees and before any later return. "
                      "Per actor: Yoink pulled 400 WETH (4 txs) and paid 20.0 ETH to coinbase (10 in 17007839 idx 1, 10 in 17007842 idx 1) plus 0.00088 priority fee; the first tx (17007838) paid 0 coinbase and 0.00044 priority fee. "
                      "c0ffeebabe.eth pulled 1,000 WETH (10 pulls in 3 txs) and paid 688.88 ETH to coinbase (10 in 17007840 idx 1, 678.88 in 17007842 idx 0) + 1.0 ETH gas-price payment. "
                      "searcher 0x719cdb61 pulled 100, coinbase 91.996; searcher 0xc9c5b869 pulled 100, coinbase 5.1; BlockSec rescue pulled 100 (priority fee 0.00289); Trust pulled 100 (priority fee 0.000146). "
                      "kept_by_bot_eth is c0ffeebabe.eth's arithmetic remainder (1000 pulled - 688.88 coinbase - 1.0 gas-price payment - 305.31898 returned = 4.80102 ETH), which may be gas/dust and is not a claim of retention; Yoink's remainder is about -0.0009 ETH (its priority fees). No builder->bot refund transfers in blocks 17007838-17007856 (block + trace scan). In 17007842 beaverbuild.org took 689.235 ETH gross and paid the proposer 689.017 (margin 0.218); about 99.9%% of the auction money reached proposers.") % (paid_total, share * 100, cb_total, pf_pull),
    },
    "fate": {
        "return_status": "partial",
        "returned_by_bot_eth": bots_to_msig,
        "returned_by_builder_eth": None,
        "returned_total_eth": returned_total,
        "returned_to": "victim 0x31d3243c (directly: Trust, BlockSec; via Sushi multisig 0x19b3eb3a: Yoink + c0ffeebabe.eth)",
        "returned_desc": ("875 ETH of 1,800 reached the victim (48.6%): Trust 90 WETH (10 + 80, 2023-04-09 03:37:59 and 03:40:35Z), BlockSec 100 ETH (2023-04-09 09:48:11Z), and 685 ETH from the Sushi multisig on 2023-04-17 15:39:35Z. "
                          "The multisig had received 305.31898 ETH from c0ffeebabe.eth (1.0 at 13:51:59Z + 304.31898 at 13:54:47Z on 2023-04-09) and 380 ETH from Yoink (2023-04-10 19:07:59Z; an identical earlier 380 send reverted). "
                          "Not returned in saved data: searcher 0x719cdb61 (about 8.0 ETH kept after 92.0 paid), searcher 0xc9c5b869 (about 94.9 ETH kept after 5.1 paid), Trust's 10 WETH difference."),
        "bounty_kept_eth": None,
        "bounty_desc": "Trust pulled 100 WETH and returned 90; the 10 WETH difference is not labelled a bounty in any saved source, so not recorded as one.",
        "kept_by_bot_eth": c_remainder,
        "returned_txs": returned_txs,
        "public_statement": "BlockSec (saved forklog page): about 44.5% of the lost funds went to block builders; 'One bot owned by c0ffeebabe.eth even bribed 678 Eth to the builder in one transaction'. Trust (@trust__90) described the tx as a rescue attempt.",
    },
    "raw_refs": refs,
    "rawref_gaps": rawref_gaps,
    "discrepancies": disc,
    "evidence_notes": [
        "Victim WETH Transfer logs (%s): 18 pulls of 100 WETH in 11 txs; the first is Yoink 0xb8f57cf8... at 17007838 idx 23, ahead of Trust's 0x43ff7e01... at 17007839 idx 54." % LOGS,
        "Trust's tx maxFeePerGas 18.87241034 gwei (block_17007839.json) < base fee 18.877867443 gwei of 17007838 (block_17007838.json): unincludable in 17007838, so Yoink pre-empted a still-pending tx; Yoink's own tx used max fee 30.3 gwei, priority 2.0 gwei.",
        "Yoink's route differs from Trust's in the fake-pool address.",
        "Auction: 806.98 ETH to builders/proposers reproduced from traces (incidents/sushi-rp2-2023/race_17007839.json, race_17007840.json, race_17007842.json, race_17007856.json); c0ffeebabe tx facts are tx-level only (block, idx, pulls, coinbase payment, returns).",
        "Bot block 17007838 has no relay bid history (vanilla geth block, nbids 0): incidents/sushi-rp2-2023/race_17007838.json.",
    ],
    "incident_dir": D,
}
# check every raw ref path exists
miss = [p for v in refs.values() for p in (v if isinstance(v, list) else [v]) if not (ROOT / p).exists()]
assert not miss, miss
out = ROOT / "data" / "extract" / f"{SLUG}.json"
json.dump([row], open(out, "w"), indent=1)
print("wrote", out, "missing_auc", missing_auc)
