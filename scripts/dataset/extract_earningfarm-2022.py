"""Extract row for earningfarm-2022 -> data/extract/earningfarm-2022.json. Run from project root: .venv/bin/python scripts/dataset/extract_earningfarm-2022.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _x6 import *

S = "earningfarm-2022"
inc = load(f"incidents/{S}/incident.json")
cd = load(f"incidents/{S}/call_diff.json")
r0 = load(f"incidents/{S}/race_15746200.json")
r2 = load(f"incidents/{S}/race_15746342.json")
BOT = "0x1f1aba5bef04b7026ae3cb1cb77987071a8aff9592e785dd99860566ccad83d1"
ATK = "0x4be393b9e3936383710c27dc422fb657aeeae266af67ea63ca6c08f062e40b5d"
ATK2 = "0x160c5950a01b88953648ba90ec0a29b0c5383e055d35a7835d905c53a3dda01e"
VAULT = "0xe39fd820b58f83205db1d9225f28105971c3d309"
CAP = "0x56178a0d5f301baf6cf3e1cd53d9863437345bf9"
HELPER = "0x0e113904cb1d53cabb324927dffae2f8f6705111"
BOTADDR = {"0x26bce6ecb5b10138e4bf14ac0ffcc8727fef3b2e", "0xa69babef1ca67a37ffaf7a485dfff3382056e78c", HELPER, CAP}
disc = []

b = txrow(r0, BOT); a = txrow(r0, ATK); a2 = txrow(r2, ATK2)
coinbase = eth(b["coinbase_transfer_wei"]); prio = eth(b["priority_fee_total_wei"])
gas_cost = b["gas_used"] * b["gas_price_gwei"] * 1e9 / 1e18  # whole gas fee incl. burned base fee

# trace: vault -> helper ETH, WETH loan from / repayment to the capital wallet
tr = load(f"data/raw/rpc/trace_{BOT}.json"); tr = tr.get("result", tr)
vault_out = []; loan_out = loan_back = None
def walk(c):
    global loan_out, loan_back
    v = int(c.get("value", "0x0"), 16)
    if v and not c.get("error") and c["from"].lower() == VAULT and c["to"].lower() == HELPER:
        vault_out.append(v)
    inp = c.get("input", "")
    if inp.startswith("0x23b872dd") and CAP[2:] in inp[:10 + 64].lower() and c["to"].lower().startswith("0xc02aaa39"):
        loan_out = int(inp[-64:], 16)
    if inp.startswith("0xa9059cbb") and CAP[2:] in inp[10:10 + 64].lower() and c["to"].lower().startswith("0xc02aaa39"):
        loan_back = int(inp[-64:], 16)
    for x in c.get("calls") or []: walk(x)
walk(tr)
vault_to_helper = vault_out[-1] / 1e18  # the final (withdraw-leg) transfer
if abs(vault_to_helper - inc["bots"][0]["captured"]["amount"]) > 1e-9:
    disc.append(f"vault->helper {vault_to_helper} vs incident.json {inc['bots'][0]['captured']['amount']}")
cap_net = (loan_back - loan_out) / 1e18
dep_in = 0.1  # the helper's own 0.1 ETH vault.deposit inside the tx (call_diff.json); it is part of the vault->helper payout
if abs(cap_net - (vault_to_helper - dep_in)) > 1e-6:
    disc.append(f"capital wallet net {cap_net} != vault->helper {vault_to_helper} - 0.1 deposit")
bot_net = cap_net - coinbase - gas_cost

# builder refund to bot: any tx from the fee recipient to a bot address in the block?
fr = r0["block"]["fee_recipient"].lower()
refund = sum(int(t["value_wei"]) for t in r0["txs"] if t["from"].lower() == fr and (t["to"] or "").lower() in BOTADDR) / 1e18

# return search: anything from bot addresses INTO the vault after the exploit block (saved etherscan files, endblock=99999999)
found = []
for f, kind in [("efvault_txlist_after", "txlist"), ("efvault_txlistinternal_after", "internal"), ("efvault_tokentx_after", "tokentx")]:
    for x in res(load(f"data/raw/etherscan/{f}.json")):
        if x["to"].lower() == VAULT and x["from"].lower() in BOTADDR and x["hash"] != BOT:
            found.append((f, x["hash"]))
rng = {f: (res(load(f"data/raw/etherscan/{f}.json"))[-1]["blockNumber"]) for f in ["efvault_txlist_after", "efvault_txlistinternal_after", "efvault_tokentx_after"]}
return_none = not found
if found:
    disc.append(f"possible return txs found: {found}")

mevb = inc["mevbot_a47b_clarification"]
a_pri = a["priority_fee_gwei"]
refs = {
 "bot.block": "data/raw/rpc/block_15746200.json", "bot.position": "data/raw/rpc/block_15746200.json",
 "attacker_block": "data/raw/rpc/block_15746200.json",
 "loot.gross_loot_eth": f"data/raw/rpc/trace_{BOT}.json",
 "loot.coinbase_paid_eth": "data/raw/rpc/trace_block_15746200.json",
 "loot.priority_fee_paid_eth": "data/raw/rpc/receipts_15746200.json",
 "loot.builder_refund_to_bot_eth": "data/raw/rpc/block_15746200.json",
 "loot.bot_net_eth": [f"data/raw/rpc/trace_{BOT}.json", "data/raw/rpc/receipts_15746200.json", "data/raw/rpc/trace_block_15746200.json"],
 "fate.kept_by_bot_eth": [f"data/raw/rpc/trace_{BOT}.json", "data/raw/rpc/receipts_15746200.json", "data/raw/rpc/trace_block_15746200.json"],
 "fate.search": ["data/raw/etherscan/efvault_txlist_after.json", "data/raw/etherscan/efvault_txlistinternal_after.json", "data/raw/etherscan/efvault_tokentx_after.json"],
 "capital_wallet_flow": f"data/raw/rpc/trace_{BOT}.json",
 "attacker_landing_block_15746342": "data/raw/rpc/block_15746342.json",
 "phase_c_counterfactual_replay": ["data/raw/rpc/debug_traceCall_atkfailed_pre_block_15746199_state_v3.json", "data/raw/rpc/debug_traceCall_atkfailed_post_block_15746200_state_v3.json"],
 "phase_c_secondary_sources": ["data/raw/web/threadreader_mevrefund.html", "data/raw/web/threadreader_supremacy.html", "data/raw/web/threadreader_danielvf_1580936010556661761.html", "data/raw/web/web3isgoinggreat_earningfarm.html"],
}
row = {
 "slug": S, "name": inc["name"], "date_utc": iso(r0["block"]["timestamp"]), "chain": "ethereum",
 "orig_verdict": inc["verdict"],
 "race_type_proposed": "beat-pending-attack",
 "race_type_reason": "The 0xa57 bot's tx is at index 0 of block 15746200 and makes vault-facing calls (deposit calldata and both Balancer flashLoan calldatas) byte-identical to the attacker's tx at index 7 of the same block, which then reverted. The attacker's nine earlier txs never touched the vault.",
 "one_liner": "At block 15746200 the '0xa57' bot's tx (index 0, zero tip, 18.717 ETH to the builder) replayed the Earning.Farm exploit calls from the attacker's pending tx (index 7, reverted) and took 480.1 ETH; the attacker retried and got 268.9 ETH. No return to Earning.Farm found.",
 "attacker": {"eoa": inc["attacker"]["eoas"][0], "eoas": inc["attacker"]["eoas"],
              "contracts": [c.split(" ")[0] for c in inc["attacker"]["contracts"]], "funding": "unknown",
              "funding_tx": inc["attacker"]["funding_tx"]["hash"], "deploy_tx": inc["attacker"]["deploy_tx"].split(" ")[0], "deploy_block": 15624367,
              "attack_txs": [
                {"hash": ATK, "block": 15746200, "index": a["index"], "status": "reverted", "role": "first exploit attempt (27.9 gwei tip); reverted after the bot had emptied the vault at index 0"},
                {"hash": ATK2, "block": r2["block"]["number"], "index": a2["index"], "status": "success", "role": "retry after the failed attempt; vault -> helper 268.8968 ETH"}],
              "none_reason": None},
 "bot": {"label": "0xa57", "eoa": b["from"], "contract": b["to"], "tx": BOT, "block": 15746200, "position": b["index"],
         "status": "success" if b["status"] == 1 else "reverted", "priority_fee_gwei": b["priority_fee_gwei"]},
 "bots_other": [],
 "evidence_level_mempool": "in-block-only",
 "mempool_note": "In-block evidence only: October 2022 is before the mempool-dumpster archive (starts 2023-08-07), so the attacker tx's first-seen time is unknown. The bot sits at index 0 with zero priority fee and an 18.717 ETH coinbase transfer, i.e. bundle-style inclusion (inferred; the Flashbots bundle API is gone).",
 "trigger": {"kind": None, "tx": None, "first_seen_utc_ms": None, "first_seen_utc": None, "sources": None,
             "note": "No mempool first-seen exists (pre-archive). The only visible source of the bot's call sequence is the attacker's pending tx 0x4be393b9 (idx 7 of the same block); nothing in the attacker's nine earlier txs touched the vault."},
 "attacker_block": 15746200,
 "attacker_block_note": "Attacker's tx 0x4be393b9 was in the same block (index 7, priority fee 27.9 gwei) and reverted at the second flashLoan callback. His retry landed in block 15746342 (index 2) for 268.9 ETH.",
 "attacker_reference": {"kind": "attack-tx", "block": 15746200, "tx": ATK},
 "auction": bvh.auction_summary(f"incidents/{S}/race_15746200.json", BOT),
 "loot": {
   "scope": "bot-tx",
   "gross_loot_eth": round(vault_to_helper, 6),
   "gross_loot_method": "ETH sent by the vault 0xe39fd820 to the bot's helper 0x0e113904 in the withdraw leg of the bot tx (callTracer); includes the 0.1 ETH the helper had deposited",
   "captured_native": {"amount": vault_to_helper, "unit": "ETH", "desc": "vault -> helper 0x0e113904, wrapped to WETH and returned to the capital wallet 0x56178a0d"},
   "captured_usd": None, "captured_usd_source": None,
   "coinbase_paid_eth": coinbase, "priority_fee_paid_eth": prio,
   "builder_refund_to_bot_eth": refund, "builder_payout_to_victim_eth": None,
   "bot_net_eth": round(bot_net, 6),
   "loot_note": f"gross_loot_eth {vault_to_helper:.4f} is the vault's payout to the helper; the helper had first put 0.1 ETH into the vault (deposit), so the net gain was {cap_net:.4f} ETH: the capital wallet 0x56178a0d lent {loan_out/1e18:,.3f} WETH to the helper and received {loan_back/1e18:,.3f} WETH back. bot_net_eth = {cap_net:.4f} - {coinbase:.4f} ETH coinbase - {gas_cost:.4f} ETH gas (2,573,638 gas x 13.1648 gwei, all base fee since the tip is 0). The 18.717 ETH bribe was paid from the bot contract's own ETH balance (it received no ETH in the tx), not out of the loot. The builder (builder0x69) passed 18.8254 ETH to the proposer and kept almost nothing; no builder refund to the bot. USD value not stated in a saved file (a web3isgoinggreat figure of ~$623K is not saved)."},
 "fate": {
   "return_status": "none-found" if return_none else "unknown",
   "returned_by_bot_eth": None, "returned_by_builder_eth": None, "returned_total_eth": None,
   "returned_to": None,
   "returned_desc": f"No return to Earning.Farm found. The 480.1 ETH went to the bot owner's capital wallet 0x56178a0d as WETH in the same tx. Scanning the vault's saved Etherscan lists after block 15746200 (txlist to block {rng['efvault_txlist_after']}, internal to {rng['efvault_txlistinternal_after']}, token transfers to {rng['efvault_tokentx_after']}) finds no transfer from the bot EOA/contract/helper/capital wallet into the vault other than the 0.1 ETH deposit inside the exploit tx itself. No public statement from the bot or its owner was found. 'Unknown' is not 'none': an off-chain return or a payment from another address would not show here.",
   "bounty_kept_eth": None, "bounty_desc": None, "kept_by_bot_eth": round(bot_net, 6),
   "returned_txs": [], "public_statement": None},
 "raw_refs": refs, "rawref_gaps": [{"field": "loot.captured_usd", "why": "no saved price file for the 2022-10-14 ETH price; not converted"}],
 "discrepancies": disc + [
   "Only the vault-facing calls were diffed (deposit + 2 flashLoan calldatas + callbacks identical, call_diff.json); the entry paths differ (bot: EOA -> 0xa69babef; attacker: EOA -> 0x140cca42 -> 0x8663fbfc).",
   "Link of the 'a57' label to EOA 0x26bce6ec/contract 0xa69babef is circumstantial (incident.json bots[0].notes).",
   f"DeFiHackLabs 'MEVBOTa47b' (tx {mevb['tx'][:10]}, block {mevb['block']}) is a DIFFERENT incident: a new EOA drained a different MEV bot (0x00000000000a47b1...) the day before; no relation to the 0xa57 bot found."],
 "evidence_notes": [
   "Victim calls in the bot tx and the attacker's reverted tx are byte-identical: vault.deposit(0.1 ETH) calldata 0xb6b55f25..., and both Balancer flashLoan calldatas (recipient = vault, 1000 ETH, userData '0x1'/'0x2') plus the callbacks (incidents/earningfarm-2022/call_diff.json).",
   "The bot makes a third flashLoan + withdraw (0x2e1a7d4d) that the attacker's tx never reached; the attacker's tx reverted at its second flashLoan callback after the vault was emptied at index 0.",
   "The attacker's nine earlier txs from the same contract never touched the vault, so the pending tx is the only visible source of the call sequence; the claim is in-block evidence only (no 2022 mempool archive).",
   f"Bid ladder: 246 relay bids from 23 builders; best bid was ~0.13 ETH until the bot tx appeared, then 18.8 ETH; builder0x69 won with 18.825 ETH, the bot's coinbase transfer 18.717 ETH being 99.4% of it (incidents/earningfarm-2022/race_15746200.json).",
   "Attacker's retry landed in block 15746342 for 268.9 ETH (race_15746342.json); the MEVa47b clarification is a separate incident.",
   "Phase C (EFLeverVault cross-check, 2026-10-21): debug_traceCall of the attacker's reverted tx 0x4be393b9 (same sender, calldata, 5M gas) on the state before block 15746200 succeeds and the vault pays 480.108 ETH to the attacker's helper, which is the bot's take; on the post-15746200 state the same call reverts. The attacker's withdraw argument in that replay (0.09498041404 EF) is within 2e-9 of the bot's. The attacker's tx used 2,111,774 of 5,000,000 gas and reverted inside the flashLoan callback, before withdraw (raw: data/raw/rpc/debug_traceCall_atkfailed_pre_block_15746199_state_v3.json, ..._post_block_15746200_state_v3.json).",
   "Phase C: MevRefund (2022-10-14) wrote that the attacker's first transaction was front-run by 0xa57 while the second got through for 268 ETH, but its first link 0x1f1aba5b is the bot's tx (the attacker's actual first, reverted, tx is 0x4be393b9); Supremacy_CA: 480 ETH to the MEV bot and 268 ETH to the hackers; DeFiHackLabs lists 0x1f1aba5b as 'frontrun bot' and 0x160c5950 as 'exploiter'. Saved: data/raw/web/threadreader_mevrefund.html, threadreader_supremacy.html, threadreader_danielvf_1580936010556661761.html, web3isgoinggreat_earningfarm.html. The incident is also known as EFLeverVault; the event date is 2022-10-14 11:58:47 UTC (block 15746200)."],
 "incident_dir": f"incidents/{S}",
}
write(S, [row])
