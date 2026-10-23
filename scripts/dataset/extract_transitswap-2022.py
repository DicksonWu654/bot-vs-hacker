"""Extract row for transitswap-2022 (Ethereum leg) -> data/extract/transitswap-2022.json. Run from project root: .venv/bin/python scripts/dataset/extract_transitswap-2022.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _x6 import *

S = "transitswap-2022"
inc = load(f"incidents/{S}/incident.json")
r81 = load(f"incidents/{S}/race_15655281.json"); r18 = load(f"incidents/{S}/race_15655118.json")
YO = "0x9f43b61d85af2694976554ad75b295df45ff73f736bda66b8850bcee7c7aa95c"
AT = "0x6f7d546a4e86baa276141c94f58bef2365fdfb0523478d2c4f13398f49616342"
SWEEP = "0xb7882cc1b71614cb106e15f3baea072ada9ccb4183a9ee1ea3897585e994ed6a"
RET = "0x074acda86089731f37e42abda7f970c606509419e557f31d9c8f793dd9981b2d"
MSG = "0x57a98ef275569be4727b2e4109e90aa083a875e2f56983275522a1b74d8130d5"
ACC = "0x3edd298ae34b4dbe5bde5f7f5115d10290cf2006cdcb63c6b626cc9529d21857"
AR = "0x2e9d1f3ef02f1e3dc944b62976427a83f85ad280a42e6eb5b37bb366f6c017d8"
ROUTER = "0xc8d7899f22bc4995c8176e3f2a5ba3f5e87d95e5"
RECV = "0xd989f7b4320c6e69cea3d914444c19ab67d3a35e"
WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
disc = []

y = txrow(r81, YO); a = txrow(r81, AT)
gas_total = y["gas_used"] * y["gas_price_gwei"] * 1e9 / 1e18
prio = eth(y["priority_fee_total_wei"])

# 1. router-call comparison recomputed from the two traces
def tr(h):
    t = load(f"data/raw/rpc/trace_{h}.json"); return t.get("result", t)
def rcalls(h):
    out = []
    def w(c):
        if c.get("to", "").lower() == ROUTER and c["input"][:10] == "0x006de4df": out.append(c)
        for x in c.get("calls") or []: w(x)
    w(tr(h)); return out
ca, cy = rcalls(AT), rcalls(YO)
A_REC, Y_REC = "75f2aba6a44580d7be2c4e42885d4a1917bffd46", "6c6b87d44d239b3750bf9badce26a9a0a3d2364e"
same_len = all(len(p["input"]) == len(q["input"]) for p, q in zip(ca, cy))
words_diff = set()
amt_zero_att = 0
for p, q in zip(ca, cy):
    ia, iy = p["input"].lower().replace(A_REC, Y_REC), q["input"].lower()
    wa = [ia[10 + 64 * k: 10 + 64 * (k + 1)] for k in range((len(ia) - 10) // 64)]
    wy = [iy[10 + 64 * k: 10 + 64 * (k + 1)] for k in range((len(iy) - 10) // 64)]
    d = [k for k in range(len(wa)) if wa[k] != wy[k]]
    words_diff.update(d)
    if int("".join(wa[26:28]), 16) == 0: amt_zero_att += 1
match_ok = len(ca) == len(cy) == 21 and same_len and words_diff <= {26, 27}
if not match_ok:
    disc.append(f"router call recheck: n={len(ca)}/{len(cy)} same_len={same_len} differing words={sorted(words_diff)}")
cd = load(f"incidents/{S}/call_diff.json")

# 2. Yoink's take: UNI taken and WETH out
uni = 0.0; weth_out = None
def walk(c):
    global uni, weth_out
    inp = c.get("input", ""); to = c.get("to", "").lower()
    if to.startswith("0x1f9840a8") and inp[:10] == "0xa9059cbb" and not c.get("error"): uni += int(inp[74:138], 16) / 1e18
    if to == WETH and inp[:10] == "0x2e1a7d4d": weth_out = int(inp[10:74], 16) / 1e18
    for x in c.get("calls") or []: walk(x)
walk(tr(YO))
if abs(uni - 5974.521) > 0.01 or abs(weth_out - 29.3065) > 1e-4:
    disc.append(f"UNI {uni} / WETH {weth_out} vs incident 5,974.5 / 29.3065")
# the second Yoink tx (separate sweep, not part of this race)
sw = txrow(load(f"incidents/{S}/race_15655281.json"), SWEEP) if any(t["hash"] == SWEEP for t in r81["txs"]) else None

# 3. return and messages (etherscan txlists)
tl = res(load("data/raw/etherscan/d989_txlist_all.json"))
ret = [x for x in tl if x["hash"] == RET][0]
assert ret["from"].lower() == "0xfde0d1575ed8e06fbf36256bcdfa1f359281455a" and ret["to"].lower() == RECV
ret_eth = int(ret["value"]) / 1e18
assert ret_eth == 26.505
msgtx = load(f"data/raw/rpc/tx_{MSG}.json"); msgtx = msgtx.get("result", msgtx)
msg_text = bytes.fromhex(msgtx["input"][2:]).decode(errors="replace")
assert "90%" in msg_text and "26.505" in msg_text
msg_block = int(msgtx["blockNumber"], 16)
acc = [x for x in res(load("data/raw/etherscan/d989_msg_17313155.json")) if x["hash"] == ACC][0]
atx = load(f"data/raw/rpc/tx_{AR}.json"); atx = atx.get("result", atx)
att_ret_eth = int(atx["value"], 16) / 1e18
att_ret_block = int(atx["blockNumber"], 16)
bounty = ret_eth / 9.0  # 10% share implied by "90% = 26.505"
bot_net = weth_out - gas_total - 0.0
refund = sum(int(x["value_wei"]) for x in r81["txs"] if x["from"].lower() == r81["block"]["fee_recipient"].lower() and (x["to"] or "").lower() in (y["to"].lower(), y["from"].lower())) / 1e18

# 4. attacker tx list from incident, cross-checked on the two race files
at_txs = []
for t in inc["attacker"]["txs"]:
    at_txs.append({"hash": t["hash"], "block": t["block"], "index": t["index"], "status": "reverted" if t["status"] == "reverted" else "success",
                   "role": "exploit tx (router arbitrary-call -> transferFrom of approved tokens)" + (" - the last, pending when Yoink's block was built; reverted" if t["hash"] == AT else "")})
assert at_txs[-1]["hash"] == AT and at_txs[-1]["index"] == a["index"] == 43
assert txrow(r18, at_txs[0]["hash"])["index"] == at_txs[0]["index"]

a_sum = bvh.auction_summary(f"incidents/{S}/race_15655281.json", YO)
a_sum["auction_note"] = "No MEV-Boost bid history for this block (no relay we can query reports it: vanilla or privately built block, fee recipient 0x4675c7e5, empty extraData). Ordering is explained by priority fee alone: Yoink's 3.000000002 gwei tip (+2 wei over the attacker's 3.0 gwei) puts it ahead of the 3.0-gwei tier, which holds the attacker's tx at index 43."
refs = {
 "bot.block": "data/raw/rpc/block_15655281.json", "bot.position": "data/raw/rpc/block_15655281.json",
 "attacker_block": "data/raw/rpc/block_15655281.json",
 "loot.gross_loot_eth": f"data/raw/rpc/trace_{YO}.json",
 "loot.coinbase_paid_eth": "data/raw/rpc/trace_block_15655281.json",
 "loot.priority_fee_paid_eth": "data/raw/rpc/receipts_15655281.json",
 "loot.builder_refund_to_bot_eth": "data/raw/rpc/block_15655281.json",
 "loot.bot_net_eth": [f"data/raw/rpc/trace_{YO}.json", "data/raw/rpc/receipts_15655281.json"],
 "fate.returned_by_bot_eth": "data/raw/etherscan/d989_txlist_all.json",
 "fate.returned_total_eth": "data/raw/etherscan/d989_txlist_all.json",
 "fate.bounty_kept_eth": [f"data/raw/rpc/tx_{MSG}.json", "data/raw/etherscan/d989_txlist_all.json"],
 "fate.kept_by_bot_eth": [f"data/raw/rpc/trace_{YO}.json", "data/raw/rpc/receipts_15655281.json", "data/raw/etherscan/d989_txlist_all.json"],
 "router_call_comparison": [f"data/raw/rpc/trace_{AT}.json", f"data/raw/rpc/trace_{YO}.json"],
 "messages": [f"data/raw/rpc/tx_{MSG}.json", "data/raw/etherscan/d989_msg_17313155.json"],
 "attacker_return": f"data/raw/rpc/tx_{AR}.json",
}
bots_other = []
if sw:
    bots_other.append({"label": "Yoink", "eoa": sw["from"], "tx": SWEEP, "block": 15655281, "position": sw["index"], "status": "success", "role": "separate Yoink sweep"})
else:
    bots_other.append({"label": "Yoink", "eoa": y["from"], "tx": SWEEP, "block": 15655307, "position": 0, "status": "success",
                       "role": "Yoink's second router tx (block 15655307, index 0): swept 3 further victims (MANA) for 0.869 WETH and paid 0.714 ETH to the builder; its attacker origin was not established, so it is not part of this race (per incident.json; trace in data/raw/rpc/trace_0xb7882cc1....json)"})
row = {
 "slug": S, "name": inc["name"], "date_utc": iso(r81["block"]["timestamp"]), "chain": "ethereum",
 "orig_verdict": inc["verdict"],
 "race_type_proposed": "beat-pending-attack",
 "race_type_reason": "Yoink's tx (index 24) makes the same 21 Transit Swap router calls on the same victims as the attacker's last pending exploit tx (index 43, reverted), with only the recipient changed; it won the block position by a 2-wei higher tip. Scope: only the attacker's last of nine Ethereum txs; the earlier eight landed.",
 "one_liner": "Yoink replayed the Transit Swap attacker's last pending exploit tx (21/21 router calls, recipient swapped) one tier ahead at index 24 of block 15655281 and swapped 5,974.5 UNI to 29.3065 WETH; the attacker's tx reverted. Yoink returned 26.505 ETH 11 months later.",
 "attacker": {"eoa": "0x5f0b31aa37bce387a8b21554a8360c6b8698fbef", "eoas": [e.split(" ")[0] for e in inc["attacker"]["eoas"]],
              "contracts": [inc["attacker"]["contracts"][0]], "funding": "unknown",
              "funding_tx": inc["attacker"]["funding_tx"]["hash"], "deploy_tx": inc["attacker"]["deploy_tx"].split(" ")[0], "deploy_block": 15655094,
              "attack_txs": at_txs, "none_reason": None},
 "bot": {"label": "Yoink", "eoa": y["from"], "contract": y["to"], "tx": YO, "block": 15655281, "position": y["index"],
         "status": "success" if y["status"] == 1 else "reverted", "priority_fee_gwei": y["priority_fee_gwei"]},
 "bots_other": bots_other,
 "evidence_level_mempool": "in-block-only",
 "mempool_note": "In-block evidence only: October 2022 is before the mempool-dumpster archive (starts 2023-08-07), and the block has no MEV-Boost bid history. Yoink's tx looks like an ordinary public tx (type 2, no coinbase payment); whether it saw the attacker's tx pending or inferred the calls from the earlier eight is not shown. Yoink did not front-run the attacker's earlier eight txs.",
 "trigger": {"kind": None, "tx": None, "first_seen_utc_ms": None, "first_seen_utc": None, "sources": None,
             "note": "No mempool first-seen exists (pre-archive). The tx Yoink's calls mirror is the attacker's last tx 0x6f7d546a (index 43 of the same block), the only one of the attacker's nine Ethereum txs that Yoink front-ran."},
 "attacker_block": 15655281,
 "attacker_block_note": "Attacker's last exploit tx 0x6f7d546a is in the same block, index 43 (tip 3.0 gwei), and reverted.",
 "attacker_reference": {"kind": "attack-tx", "block": 15655281, "tx": AT},
 "auction": a_sum,
 "loot": {
   "scope": "bot-tx",
   "gross_loot_eth": round(weth_out, 12),
   "gross_loot_method": f"WETH out of the UNI swap in the Yoink tx (callTracer): {uni:,.3f} UNI taken from 21 router approvals, swapped via a Uniswap pool to {weth_out:.4f} WETH, unwrapped to ETH",
   "captured_native": {"amount": f"{uni:,.3f} UNI -> {weth_out:.6f} WETH", "unit": "UNI->WETH", "desc": "UNI taken by 21 router calls (recipient = Yoink contract 0x6c6b87d4), sold for WETH inside the tx"},
   "captured_usd": None, "captured_usd_source": None,
   "coinbase_paid_eth": 0.0, "priority_fee_paid_eth": round(prio, 12),
   "builder_refund_to_bot_eth": refund, "builder_payout_to_victim_eth": None,
   "bot_net_eth": round(bot_net, 9),
   "loot_note": f"bot_net_eth = {weth_out:.6f} ETH - {gas_total:.6f} ETH gas (1,023,336 gas x 9.065325223 gwei, incl. {prio:.6f} ETH tip); there was no coinbase payment. This covers tx 0x9f43b61d only: Yoink's separate sweep in block 15655307 (0.869 WETH, 0.714 ETH to the builder) is excluded, and Yoink's offer of '90% of the profits (26.505 ETH)' implies a total profit of about 29.45 ETH that includes it. No USD figure is saved for 2022-10-01."},
 "fate": {
   "return_status": "partial",
   "returned_by_bot_eth": ret_eth, "returned_by_builder_eth": None, "returned_total_eth": ret_eth,
   "returned_to": f"Transit Swap funds receiver {RECV}",
   "returned_desc": f"Transit messaged Yoink on-chain on 2022-10-04, 10-06 and 10-07. Yoink replied on-chain on 2022-10-23 (tx 0x57a98ef2, block {msg_block}): 'My bot frontran the real attacker. How about I return 90% of the profits (26.505 Eth) and keep 10% as a bounty?'. Transit accepted on 2023-05-22 (tx 0x3edd298a, block {acc['blockNumber']}). Yoink sent exactly 26.505 ETH to {RECV[:10]} on {iso(ret['timeStamp'])} (tx 0x074acda8, block {ret['blockNumber']}), about 11 months after the offer. Separately, the attacker's recipient address 0x75f2aba6 returned {att_ret_eth:,.0f} ETH to Transit's deployer at block {att_ret_block} (about 2022-10-02, tx 0x2e9d1f3e); that is not Yoink's return.",
   "bounty_kept_eth": round(bounty, 4), "bounty_desc": "10% bounty Yoink proposed to keep and Transit accepted; derived from the message (26.505 ETH = 90% of profits, so about 2.945 ETH), not an on-chain transfer",
   "kept_by_bot_eth": round(bot_net - ret_eth, 6),
   "returned_txs": [{"tx": RET, "eth": ret_eth, "block": int(ret["blockNumber"]), "time_utc": iso(ret["timeStamp"]),
                     "note": "Yoink EOA 0xfde0d157 -> Transit funds receiver 0xd989f7b4, exactly 26.505 ETH"}],
   "public_statement": "On-chain message from Yoink's EOA to Transit's receiver (tx 0x57a98ef2, 2022-10-23): " + msg_text.replace("\n", " ")},
 "raw_refs": refs,
 "rawref_gaps": [{"field": "loot.captured_usd", "why": "no saved ETH/UNI price for 2022-10-01; not converted (incident.json's ~$38K is a rough estimate)"},
                 {"field": "fate.returned_txs[].time_utc of messages", "why": "dates of the three Transit messages (10-04/06/07) are from incident.json, not re-opened"}],
 "discrepancies": disc + [
   "initial incident notes phrased the offer as '90% of 26.505 ETH'; the on-chain message says 26.505 ETH IS the 90% share ('return 90% of the profits (26.505 Eth) and keep 10%'), implying total profits of about 29.45 ETH. Row kept_by_bot_eth is tx-level (gross 29.31 - gas - 26.505), so it differs from the 2.945 ETH bounty.",
   "Yoink's 29.45 ETH profit basis includes a second Yoink tx (0xb7882cc1, block 15655307) whose attacker origin was not established; this row's tx alone is 29.3065 WETH."],
 "evidence_notes": [
   f"21 of 21 router calls (selector 0x006de4df on {ROUTER[:10]}) in Yoink's tx and the attacker's reverted tx have the same length ({len(ca[0]['input'])-2} hex chars) and, after swapping the recipient 0x75f2aba6 -> 0x6c6b87d4, differ only in words {sorted(words_diff)} (the trailing amount field; incidents/transitswap-2022/call_diff.json says it is zero in the attacker's trace because the victim balances were already gone, and the victim's UNI balance in Yoink's); recomputed from data/raw/rpc/trace_<tx>.json, see incidents/transitswap-2022/call_diff.json.",
   "Block 15655281: Yoink index 24, tip 3.000000002 gwei (effective 9.065325223 gwei); attacker index 43, tip 3.0 gwei (9.065325221); block order follows descending tip: the three 3.000000002-gwei txs sit at indexes 23-25, the 3.0-gwei tier follows (incidents/transitswap-2022/race_15655281.json).",
   "The attacker's earlier eight Ethereum txs (blocks 15655118-15655247) all succeeded and were not front-run; Yoink's txs in blocks 15655000-15655400 touch the router only in 15655281 and 15655307.",
   "Yoink took 5,974.52 UNI via the router and sold it for 29.3065 WETH in one tx; no coinbase payment, no relay bid history for the block.",
   f"Return: exactly 26.505 ETH on {iso(ret['timeStamp'])} (tx 0x074acda8) after offering 90% of profits on 2022-10-23 (tx 0x57a98ef2); the attacker's own 3,180 ETH return to Transit (about 2022-10-02) is separate."],
 "incident_dir": f"incidents/{S}",
}
write(S, [row])
