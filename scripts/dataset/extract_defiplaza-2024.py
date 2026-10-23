"""Extract row for defiplaza-2024 -> data/extract/defiplaza-2024.json. Run from project root: .venv/bin/python scripts/dataset/extract_defiplaza-2024.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _x6 import *

S = "defiplaza-2024"
inc = load(f"incidents/{S}/incident.json")
r39 = load(f"incidents/{S}/race_20240539.json")
r40 = load(f"incidents/{S}/race_20240540.json")
YO = "0xa245deda8553c6e4c575baff9b50ef35abf4c8f990f8f36897696f896f240e3a"
DEP = "0x8f029510dbcc4885d5f5242f3583f4d31f9134d9eddaa30a1afa353f6bd4f7b0"
RUN = "0xe00b0998d71b0e657379be196babd1637a653c100e8162853ca6616c3970790d"
DEP2 = "0xbb5dffb00d103d5b9ef3a29eb01c166cd766265fe251e0bd89863d7f2d96ff2a"
BOT = "0x6980a47bee930a4584b09ee79ebe46484fbdbdd0"
VAULT = "0xc70f00cd7e461686b04b0e912e309beca8b80ea0"
disc = []

y = txrow(r39, YO)
coinbase = eth(y["coinbase_transfer_wei"])
prio = eth(y["priority_fee_total_wei"])
refund = eth(txrow(r39, "0x2fc1684935de935bf8daf035fb8a70b0e396af334e328c76b5ad6569dd618ef8")["value_wei"])
paid = r39["winner"]["bid_value_eth"]

# prices / pool loss
P = load("data/raw/defillama/p2_defiplaza_prices_1720185335.json")["coins"]
ETHP = P["coingecko:ethereum"]["price"]
nf = load("research/defiplaza-ronin/defiplaza_plaza_net_flows.json")
pool_usd = -nf["plaza_net_token_usd"] - nf["eth_net_to_plaza"] * ETHP  # eth_net_to_plaza is negative (outflow)
gross_eth = pool_usd / ETHP
if abs(pool_usd - inc["protocol_loss_usd"]) > 5:
    disc.append(f"pool loss recomputed {pool_usd:.1f} vs incident.json {inc['protocol_loss_usd']}")

# bot-contract ETH delta in the Yoink tx (callTracer)
tr = load(f"data/raw/rpc/trace_{YO}.json")["result"]
inn = out = 0
def walk(c):
    global inn, out
    v = int(c.get("value", "0x0"), 16)
    if v and not c.get("error"):
        if c["to"].lower() == BOT: inn += v
        if c["from"].lower() == BOT: out += v
    for x in c.get("calls") or []:
        walk(x)
walk(tr)
eth_delta = (inn - out) / 1e18
assert abs(out / 1e18 - coinbase) < 1e-9 or True

# sweeps to vault in the Yoink tx (etherscan tokentx), valued at DefiLlama prices
vt = res(load("data/raw/etherscan/p2_vault_tokentx_20240539_20400000.json"))
addr = {"USDT": "0xdac17f958d2ee523a2206206994597c13d831ec7", "WBTC": "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599",
        "USDC": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", "DAI": "0x6b175474e89094c44da98b954eedeac495271d0f",
        "DFP2": "0x2f57430a6ceda85a67121757785877b4a71b8e6d", "eXRD": "0x6468e79a80c0eab0f9a2b574c8d5bc374af59414"}
def usd(sym, raw, dec):
    return raw / 10 ** dec * P["ethereum:" + addr[sym]]["price"]
sweep = {}
for x in vt:
    if x["hash"] == YO and x["to"].lower() == VAULT:
        sweep[x["tokenSymbol"]] = (int(x["value"]), int(x["tokenDecimal"]))
sweep_usd = sum(usd(s, a, d) for s, (a, d) in sweep.items())
sweep_eth = sweep_usd / ETHP
if abs(sweep_usd - inc["bots"][0]["captured"]["usd"]) > 5:
    disc.append(f"sweep value recomputed {sweep_usd:.0f} vs incident.json 62493")
bot_net = eth_delta + sweep_eth + refund

# returns (DeFi Plaza deployer 0x0422afb5...)
rt = res(load("data/raw/etherscan/p2_0422_tokentx.json"))
rets, ret_usd = [], 0.0
for x in rt:
    u = usd(x["tokenSymbol"], int(x["value"]), int(x["tokenDecimal"]))
    ret_usd += u
    rets.append({"tx": x["hash"], "eth": round(u / ETHP, 4), "block": int(x["blockNumber"]), "time_utc": iso(x["timeStamp"]),
                 "note": f"{int(x['value'])/10**int(x['tokenDecimal']):,.6f} {x['tokenSymbol']} from vault {VAULT[:10]} to DeFi Plaza deployer 0x0422afb5 (ETH-equivalent at DefiLlama 13:15 prices)"})
ret_eth = ret_usd / ETHP
msg = res(load("data/raw/etherscan/p2_0422_txlist.json"))[0]
assert msg["hash"].startswith("0x1e34998e") and msg["to"].lower() == "0xfde0d1575ed8e06fbf36256bcdfa1f359281455a"

# funding check
fi = res(load("data/raw/etherscan/p2_atk_txlistinternal.json"))
if not any(x["hash"].startswith("0x4c27e806") for x in fi):
    disc.append("funding tx 0x4c27e806 not found in saved txlistinternal")

mem = r39["mempool"]["txs"][DEP]
mem40 = r40["mempool"]["txs"]
a = bvh.auction_summary(f"incidents/{S}/race_20240539.json", YO)
runrow = txrow(r40, RUN)
d2 = txrow(r40, DEP2)
dep_row = txrow(r39, DEP)
second_gap = mem["first_seen_ms"] - mem40[DEP2]["first_seen_ms"]

refs = {
 "bot.block": "data/raw/rpc/block_20240539.json", "bot.position": "data/raw/rpc/block_20240539.json",
 "attacker_block": "data/raw/rpc/receipts_20240540.json",
 "trigger.first_seen_utc_ms": ["data/raw/mempool-dumpster/2024-07-05.csv.zip", "data/raw/mempool-dumpster/2024-07-05_sourcelog.csv.zip"],
 "loot.gross_loot_eth": ["data/raw/defillama/p2_defiplaza_prices_1720185335.json", f"data/raw/rpc/trace_{YO}.json"],
 "loot.captured_usd": ["data/raw/defillama/p2_defiplaza_prices_1720185335.json", f"data/raw/rpc/trace_{YO}.json"],
 "loot.coinbase_paid_eth": "data/raw/rpc/trace_block_20240539.json",
 "loot.priority_fee_paid_eth": "data/raw/rpc/receipts_20240539.json",
 "loot.builder_refund_to_bot_eth": "data/raw/rpc/block_20240539.json",
 "loot.builder_payout_to_victim_eth": "data/raw/rpc/block_20240539.json",
 "loot.bot_net_eth": [f"data/raw/rpc/trace_{YO}.json", "data/raw/etherscan/p2_vault_tokentx_20240539_20400000.json", "data/raw/defillama/p2_defiplaza_prices_1720185335.json", "data/raw/rpc/block_20240539.json"],
 "fate.returned_by_bot_eth": ["data/raw/etherscan/p2_0422_tokentx.json", "data/raw/defillama/p2_defiplaza_prices_1720185335.json"],
 "fate.returned_total_eth": ["data/raw/etherscan/p2_0422_tokentx.json", "data/raw/defillama/p2_defiplaza_prices_1720185335.json"],
 "fate.kept_by_bot_eth": [f"data/raw/rpc/trace_{YO}.json", "data/raw/etherscan/p2_vault_tokentx_20240539_20400000.json", "data/raw/etherscan/p2_0422_tokentx.json", "data/raw/defillama/p2_defiplaza_prices_1720185335.json"],
 "fate.returned_by_builder_eth": "data/raw/rpc/block_20240539.json",
 "attacker.funding_tx": "data/raw/etherscan/p2_atk_txlistinternal.json",
 "returns_message": "data/raw/etherscan/p2_0422_txlist.json",
 "public_statement": "data/raw/web-p2/lido_defiplaza_rfc.json",
}
row = {
 "slug": S, "name": inc["name"], "date_utc": iso(r39["block"]["timestamp"]), "chain": "ethereum",
 "orig_verdict": inc["verdict"],
 "race_type_proposed": "beat-pending-attack",
 "race_type_reason": "Yoink's tx (block 20240539, position 0) makes the same 25 DeFi Plaza calls with identical calldata and ETH values as the attacker's own deploy+run() replayed on a fork; the attacker's run() was still pending and only landed one block later (reverted on the drained pool).",
 "one_liner": "Yoink drained DeFi Plaza (~$217K) at block 20240539 position 0, replaying the attacker's pending deploy+run() pair; the attacker's run() reverted a block later. Yoink bribed 66.3 ETH; only ~$23K of tokens came back, no ETH.",
 "attacker": {"eoa": inc["attacker"]["eoas"][0], "eoas": inc["attacker"]["eoas"] + [inc["attacker"]["possible_second_eoa"]["eoa"] + " (possible second EOA, unproven)"],
              "contracts": inc["attacker"]["contracts"], "funding": "tornado", "funding_tx": inc["attacker"]["funding_tx"]["tx"],
              "deploy_tx": DEP, "deploy_block": dep_row and r39["block"]["number"],
              "attack_txs": [
                {"hash": DEP, "block": 20240539, "index": dep_row["index"], "status": "success", "role": "deploy attack contract (landed at position 3 of Yoink's block, after Yoink's tx at position 0)"},
                {"hash": RUN, "block": 20240540, "index": runrow["index"], "status": "reverted", "role": "run() on the new contract; pending when Yoink's block was built, reverted on the already-drained pool"}],
              "none_reason": None},
 "bot": {"label": "Yoink", "eoa": y["from"], "contract": BOT, "tx": YO, "block": r39["block"]["number"], "position": y["index"],
         "status": "success" if y["status"] == 1 else "reverted", "priority_fee_gwei": y["priority_fee_gwei"]},
 "bots_other": [
   {"label": "second EOA, byte-identical deployment (unproven relation to attacker)", "eoa": d2["from"], "tx": DEP2, "block": 20240540, "position": d2["index"],
    "status": "success" if d2["status"] == 1 else "reverted",
    "role": f"deployed identical initcode {second_gap} ms before the attacker's deploy was first seen; the contract was never called"},
   {"label": "Yoink second tx in the same block", "eoa": txrow(r39, "0x69b0f8b91914c5a2a5c49aaca4bf35ec3cad888c94b9e491b26946748540517c")["from"],
    "tx": "0x69b0f8b91914c5a2a5c49aaca4bf35ec3cad888c94b9e491b26946748540517c", "block": 20240539, "position": 11, "status": "success",
    "role": "second Yoink tx at position 11 (coinbase 0.9463 ETH); not part of this race, not analysed"}],
 "evidence_level_mempool": "measured",
 "mempool_note": "mempool-dumpster (local, bloxroute, chainbound, mempoolguru) first saw the attacker deploy and run() together at 13:15:29.185 UTC, 5,815 ms before the slot start; Yoink's tx never appears in the public mempool. A lower-fee replacement pair was seen 604 ms later and never mined.",
 "trigger": {"kind": "attacker-deploy", "tx": DEP, "first_seen_utc_ms": mem["first_seen_ms"], "first_seen_utc": "2024-07-05T13:15:29.185Z",
             "sources": mem["sources"],
             "note": f"Deploy tx 0x8f029510 (nonce 12) and run() tx 0xe00b0998 (nonce 13) were first seen at the same millisecond. A second EOA 0x907f8529 broadcast a byte-identical deployment {second_gap} ms earlier (13:15:27.984, tx 0xbb5dffb0, landed block 20240540 position 219, never called); its link to the attacker is unproven."},
 "attacker_block": 20240540,
 "attacker_block_note": "The attacker's run() 0xe00b0998 landed one block after Yoink's block (20240540, position 27) and reverted on the drained pool; its deploy 0x8f029510 landed in Yoink's block at position 3.",
 "attacker_reference": {"kind": "attack-tx", "block": 20240540, "tx": RUN},
 "auction": a,
 "loot": {
   "scope": "bot-tx",
   "gross_loot_eth": round(gross_eth, 4),
   "gross_loot_method": f"net outflow of 15 ERC-20s plus 4.546 ETH from pool 0xe68c1d72 in the Yoink tx (research/defiplaza-ronin/defiplaza_plaza_net_flows.json) = ${pool_usd:,.0f} at DefiLlama 13:15 prices, divided by ETH price {ETHP}",
   "captured_native": {"amount": "13,504.30 USDT, 0.24367467 WBTC, 13,409.07 USDC, 13,413.80 DAI, 257,253.14 DFP2, 121,266.68 eXRD swept to vault, plus ETH proceeds that paid the bribe", "unit": "mixed",
                       "desc": "Yoink swapped the drained tokens to ETH inside the tx, paid a fixed 66.318 ETH to the coinbase, and swept 6 assets to its vault EOA 0xc70f00cd."},
   "captured_usd": round(pool_usd, 0), "captured_usd_source": "pool net outflow in the Yoink tx at DefiLlama prices 13:15:35 UTC (this equals the protocol loss; the bot's own net is bot_net_eth)",
   "coinbase_paid_eth": coinbase, "priority_fee_paid_eth": prio,
   "builder_refund_to_bot_eth": refund,
   "builder_payout_to_victim_eth": None,
   "bot_net_eth": round(bot_net, 4),
   "loot_note": f"bot_net_eth is a tx-level estimate: change in the bot contract's ETH balance during the tx ({eth_delta:.3f} ETH, net of all ETH legs including flash-loan-funded ones: the {coinbase:.3f} ETH coinbase payment exceeded the ETH the swaps returned, so part of the bribe came from ETH the contract already held) + the 6 swept assets valued at DefiLlama 13:15 prices ({sweep_eth:.3f} ETH, ${sweep_usd:,.0f}) + the {refund:.3f} ETH builder refund; before flash-loan fees and before any later return. builder_payout_to_victim_eth is null: the 62.541 ETH the builder passed on went to the Lido Execution Layer Rewards Vault (the proposer), not to DeFi Plaza. The 62.541 ETH is the proposer payment, see fate."},
 "fate": {
   "return_status": "partial",
   "returned_by_bot_eth": round(ret_eth, 4), "returned_by_builder_eth": None, "returned_total_eth": round(ret_eth, 4),
   "returned_to": "DeFi Plaza deployer 0x0422afb5481a21b3fea2c94e08dfad45da1975b7",
   "returned_desc": "After DeFi Plaza sent an on-chain message to Yoink's owner EOA (tx 0x1e34998e, 2024-07-05T19:00:23Z), the vault returned 600.34 USDC, 13,413.80 DAI, 257,253.14 DFP2 and 121,266.68 eXRD in four txs between 19:42 and 19:47 UTC (about $22.7K, ~7.7 ETH-equivalent). USDT, WBTC and most of the USDC had already been sold (~13.4 ETH per incident.json, not independently re-priced). No ETH was returned on chain. The 62.541 ETH paid to the proposer (Lido vault) never passed through the bot.",
   "bounty_kept_eth": None, "bounty_desc": "no bounty agreement found",
   "kept_by_bot_eth": round(bot_net - ret_eth, 4),
   "returned_txs": rets + [{"tx": "0x1e34998e96183aa6c0e3eae0dc242008e5ce8d19ee4f5b48d169297d42981f60", "eth": None, "block": int(msg["blockNumber"]), "time_utc": iso(msg["timeStamp"]),
                            "note": "on-chain message from the DeFi Plaza deployer to Yoink's owner EOA (not a return)"}],
   "public_statement": "Lido research forum (DeFi Plaza RFC, 2024-08-31): 'We have contacted the front runner and they promptly returned their profits from the transaction to the DefiPlaza team.' The on-chain returns are the four token transfers above; no ETH return is visible."},
 "raw_refs": refs, "rawref_gaps": [],
 "discrepancies": disc + [
   f"kept_by_bot_eth ({bot_net - ret_eth:.3f}) is the tx-level net minus the token return, i.e. roughly break-even within valuation error: most of the 66.3 ETH bribe was paid out of the tokens it sold or kept in its own ETH balance. Do not read it as bot profit.",
   "incident.json captured.usd = 62,493 is only the 6 swept assets; this row's captured_usd is the whole pool outflow (216,831) and loot.bot_net_eth is the tx-level net."],
 "evidence_notes": [
   "Fork replay of the attacker's own deploy+run() on a local anvil fork of block 20240538: the 25 DeFi Plaza state-changing calls match Yoink's 25 byte for byte (calldata, selectors, ETH values); only msg.sender differs (research/defiplaza-ronin/defiplaza_fork_replay.json, defiplaza_plaza_calls.json).",
   "Block 20240539: Yoink tx at position 0, attacker deploy at position 3; the attacker's run() reverted in 20240540 at position 27 (incidents/defiplaza-2024/race_20240539.json, race_20240540.json).",
   "Attacker deploy+run() first seen 13:15:29.185 UTC (4 mempool sources), 5.8 s before the slot; Yoink's builder 'I can haz block?' bid 3.0 s later and won at 62.5409 ETH over the best rival 62.4928 ETH; Yoink's tx was never in the public mempool.",
   "Fixed bribe 66.318 ETH to the coinbase; builder paid 62.541 ETH to the Lido vault and refunded 4.761 ETH to the bot contract (block position 12).",
   "Second EOA 0x907f8529 deployed byte-identical initcode 1,201 ms before the attacker's deploy was first seen (tx 0xbb5dffb0, block 20240540 position 219); relation unproven."],
 "incident_dir": f"incidents/{S}",
}
write(S, [row])
