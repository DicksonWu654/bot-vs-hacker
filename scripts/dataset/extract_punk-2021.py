"""Extract row for punk-2021 -> data/extract/punk-2021.json (ONE row: white-hat bot 0x3aa27ab2 vs the Punk Protocol attacker, block 12995895).
Run from project root: .venv/bin/python scripts/dataset/extract_punk-2021.py   (needs incidents/punk-2021/* built by incidents/punk-2021/scripts/*)"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _x6 import *

S = "punk-2021"
inc = load(f"incidents/{S}/incident.json")
race = load(f"incidents/{S}/race_12995895.json")
cd = load(f"incidents/{S}/call_diff.json")
an = load(f"incidents/{S}/anvil_replay.json")
BOT_TX = "0x597d11c05563611cb4ad4ed4c57ca53bbe3b7d3fefc37d1ef0724ad58904742b"
ATT_TX = "0x7604c7dd6e9bcdba8bac277f1f8e7c1e4c6bb57afd4ddf6a16f629e8495a0281"
ATT2_TX = "0xa76cd31bcd48869621e7f2698ac8754699026acd0655a6d33280224dabed4cfa"
DEPLOY_TX = "0x2d636161292b293ee1a07da79239d1298828e803f81d525954bb4160f2704c2e"
SWAP_USDC2 = "0x60c0757b82e82c9bb3e658d2d5a49e94630d04eb1bd735077ffed4e60e2403b5"
SWAP_DAI_BOT = "0x129688f8041c32d16eccd244c23b8b8f388343e6783ab596cec356c211135fe4"
RET_USDT = "0xace7c07695ec1bbf917486c3c81ee7de79c04e0309d4f6a149688463e6f83247"
RET_DAI = "0x008dd92f8bcfcee400aed26d13495fbfc8351f9b21289792fc2bb9e771668147"
E = "data/raw/etherscan/"
disc = []

b = txrow(race, BOT_TX); a = txrow(race, ATT_TX)
assert (b["index"], a["index"], b["status"], a["status"]) == (50, 52, 1, 1)
tip = eth(b["priority_fee_total_wei"])                     # tip to the miner (the base fee is burned)
fee_total = b["gas_used"] * b["gas_price_gwei"] * 1e9 / 1e18
coinbase = eth(b["coinbase_transfer_wei"])
assert coinbase == 0.0 and eth(a["coinbase_transfer_wei"]) == 0.0

W = {m: cd["withdraw_amounts"][m]["bot_withdraw"] for m in ("USDC", "USDT", "DAI")}
dust = {m: cd["withdraw_amounts"][m]["attacker_withdraw"] for m in ("USDC", "USDT", "DAI")}
stolen_usd = sum(W.values()); bot_usd = W["USDT"] + W["DAI"]
# recheck the three legs against the bot tx receipt Transfer logs
sent_by_bot = {(t["token"], t["to_addr"]): t["amount"] for t in cd["bot_onward_transfers"]}
assert abs(sent_by_bot[("USDC", "0x1d5a56402425c1099497c1ad715a6b56aaccb72b")] - W["USDC"]) < 1e-9
assert abs(sent_by_bot[("USDT", "0x3aa27ab297a3a753f79c5497569ba2dacc2bc35a")] - W["USDT"]) < 1e-9
assert abs(sent_by_bot[("DAI", "0x3aa27ab297a3a753f79c5497569ba2dacc2bc35a")] - W["DAI"]) < 1e-9

# ETH price = the attacker's own 1inch sale of the USDC 15 minutes later (stablecoins at par)
att_tok = res(load(E + "punk_att_eoa_tokentx.json")); att_int = res(load(E + "punk_att_eoa_txlistinternal.json"))
usdc_sold = [int(t["value"]) / 1e6 for t in att_tok if t["hash"] == SWAP_USDC2 and t["tokenSymbol"] == "USDC"][0]
eth_got = [int(t["value"]) / 1e18 for t in att_int if t["hash"] == SWAP_USDC2][0]
px = usdc_sold / eth_got
toeth = lambda usd: usd / px
bot_int = res(load(E + "punk_bot_eoa_txlistinternal_12994000_13100000.json"))
fee_eth = [int(t["value"]) / 1e18 for t in bot_int if t["hash"] == SWAP_DAI_BOT][0]
assert abs(fee_eth - 319.18431193663764) < 1e-12

bot_tok = res(load(E + "punk_bot_eoa_tokentx_12994000_13100000.json"))
r_usdt = [t for t in bot_tok if t["hash"] == RET_USDT][0]; r_dai = [t for t in bot_tok if t["hash"] == RET_DAI][0]
usdt_ret = int(r_usdt["value"]) / 1e6; dai_ret = int(r_dai["value"]) / 1e18
ret_usd = usdt_ret + dai_ret
assert abs(ret_usd - 4954249.925) < 0.01
cf = an["attacker_alone"][0]["net_token_received_by_eoa"]["attacker EOA"]
assert abs(sum(cf.values()) - 8950039.12) < 0.5
# anvil sanity: bot-then-attacker reproduces the chain
bt = an["bot_then_attacker"]
assert bt[0]["net_token_received_by_eoa"]["bot EOA"]["USDT"] == W["USDT"] and abs(bt[0]["net_token_received_by_eoa"]["attacker EOA"]["USDC"] - W["USDC"]) < 1e-9
assert an["attacker_then_bot"][1]["status"] == 0

rets = [
 {"tx": RET_USDT, "eth": None, "block": int(r_usdt["blockNumber"]), "time_utc": iso(r_usdt["timeStamp"]),
  "note": f"{usdt_ret:,.6f} USDT from the bot EOA 0x3aa27ab2 to Punk's deployer wallet 0xe36cc043 (token; = the bot's 3,000,022.7862 USDT take + 35.594772 USDT from a later separate inflow)"},
 {"tx": RET_DAI, "eth": None, "block": int(r_dai["blockNumber"]), "time_utc": iso(r_dai["timeStamp"]),
  "note": f"{dai_ret:,.6f} DAI from the bot EOA to Punk's deployer wallet (token; = the bot's 2,954,191.544043 DAI take minus the 1,000,000 DAI it kept)"}]

refs = {
 "bot.block": "data/raw/rpc/block_12995895.json", "bot.position": "data/raw/rpc/block_12995895.json",
 "attacker_block": "data/raw/rpc/block_12995895.json",
 "loot.gross_loot_eth": [f"data/raw/rpc/rc_{BOT_TX}.json", f"data/raw/rpc/trace_{BOT_TX}.json", E + "punk_att_eoa_txlistinternal.json", E + "punk_att_eoa_tokentx.json"],
 "loot.coinbase_paid_eth": "data/raw/rpc/trace_block_12995895.json",
 "loot.priority_fee_paid_eth": ["data/raw/rpc/receipts_12995895.json", "data/raw/rpc/block_12995895.json"],
 "loot.bot_net_eth": [f"data/raw/rpc/rc_{BOT_TX}.json", E + "punk_att_eoa_txlistinternal.json", "data/raw/rpc/receipts_12995895.json"],
 "loot.captured_usd": [f"data/raw/rpc/rc_{BOT_TX}.json", E + "punk_bot_eoa_tokentx_12994000_13100000.json"],
 "fate.returned_by_bot_eth": [E + "punk_bot_eoa_tokentx_12994000_13100000.json", E + "punk_att_eoa_txlistinternal.json", E + "punk_att_eoa_tokentx.json"],
 "fate.returned_total_eth": [E + "punk_bot_eoa_tokentx_12994000_13100000.json", E + "punk_att_eoa_txlistinternal.json", E + "punk_att_eoa_tokentx.json"],
 "fate.bounty_kept_eth": [E + "punk_bot_eoa_txlistinternal_12994000_13100000.json", E + "punk_bot_eoa_tokentx_12994000_13100000.json"],
 "fate.kept_by_bot_eth": [E + "punk_bot_eoa_txlistinternal_12994000_13100000.json", E + "punk_bot_eoa_tokentx_12994000_13100000.json"],
 "attacker.funding_tx": E + "punk_att_eoa_txlistinternal.json",
 "attacker.deploy_tx": E + "punk_att_eoa_txlist.json",
 "call_diff": [f"data/raw/rpc/trace_{ATT_TX}.json", f"data/raw/rpc/trace_{BOT_TX}.json", f"data/raw/rpc/rc_{ATT_TX}.json", f"data/raw/rpc/rc_{BOT_TX}.json"],
 "anvil_replay": [f"incidents/{S}/anvil_replay.json"],
 "initialize_scan": inc["raw_refs"]["trace_filter_initialize_scan"],
 "public_statement": ["data/raw/web/punk_rekt.html", "data/raw/web/punk_halborn.html", "data/raw/web/punk_medium_incident_report_wayback.html"],
 "messages": [E + "punk_bot_eoa_txlist_12994000_13100000.json", E + "punk_deployer_txlist_12995000_13100000.json", E + "punk_att_eoa_txlist.json"],
}
one = ("A front-running bot copied the Punk Protocol attacker's pool takeover and landed at index 50 vs his 52 in block 12995895 (43.33 vs 40.00 gwei): "
       "$5.95M USDT+DAI taken, $4.95M returned, $1M kept; it also mis-sent $3.0M USDC to the attacker. Pre-Merge, in-block evidence only.")
assert len(one) <= 320, len(one)
row = {
 "slug": S, "name": inc["name"], "date_utc": iso(race["block"]["timestamp"]), "chain": "ethereum",
 "orig_verdict": inc["verdict"],
 "race_type_proposed": "beat-pending-attack",
 "race_type_reason": ("Bot tx 0x597d11c0 (index 50, 43.33 gwei) replays the attacker's pending tx 0x7604c7dd (index 52, 40.00 gwei, same block): same 9 victim calls in the same pool order "
                      "with identical initialize() arguments except the new forge address; it even leaves the attacker's EOA as the USDC recipient. The attacker's tx still succeeded but "
                      "got dust. Anvil: attacker alone would have received all $8.95M; attacker first makes the bot's tx revert. Ordering is by gas price; no mempool archive in 2021."),
 "one_liner": one,
 "attacker": {"eoa": inc["attacker"]["eoas"][0], "eoas": inc["attacker"]["eoas"], "contracts": ["0x1695ce70da4521cb94dea036e6ebcf1e8a073ee6", "0x1c39e47a2968f166a11c4af9088dd45ccd13b13d"],
              "funding": "tornado", "funding_tx": inc["attacker"]["funding_tx"]["hash"],
              "deploy_tx": DEPLOY_TX, "deploy_block": 12994067,
              "attack_txs": [
                {"hash": DEPLOY_TX, "block": 12994067, "index": 101, "status": "success", "role": "deploys attack contract 0x1695ce70 (41 gwei), 6.9 h before the race"},
                {"hash": ATT_TX, "block": 12995895, "index": 52, "status": "success", "role": "attack tx: initialize+invest+withdrawToForge on the USDC, USDT, DAI pools; succeeded but withdrew only dust because the bot was two slots ahead (40.00 gwei)"},
                {"hash": ATT2_TX, "block": 12996594, "index": 205, "status": "success", "role": "second hit, 45 gwei: 45,100.32 DAI of fresh deposits (~$45K)"}],
              "none_reason": None},
 "bot": {"label": "anonymous white-hat front-running bot (EOA 0x3aa27ab2, contract 0x00000000b2ff)", "eoa": b["from"], "contract": b["to"], "tx": BOT_TX,
         "block": 12995895, "position": b["index"], "status": "success", "priority_fee_gwei": b["priority_fee_gwei"]},
 "bots_other": [],
 "evidence_level_mempool": "in-block-only",
 "mempool_note": ("In-block evidence only: pre-Merge (Aug 2021); mempool-dumpster starts 2023-08-07 so neither tx has a first-seen time. Both are type-2 txs ordered by effective gas price "
                  "(idx 49 43.60, bot 43.33, idx 51 40.27, attacker 40.00 gwei); neither pays the miner directly (no coinbase transfer) and the block's bundle-like txs sit at idx 0-2, so no Flashbots "
                  "bundle is inferred for either tx. The Flashbots blocks API is decommissioned (HTTP 410)."),
 "trigger": {"kind": None, "tx": None, "first_seen_utc_ms": None, "first_seen_utc": None, "sources": None,
             "note": "No mempool first-seen exists (pre-Merge, no archive). The bot's copy is shown by the call tree and by the unrewritten USDC recipient, not by timing; the attacker's contract existed from block 12994067 (~6.9 h) and his tx landed two slots behind the bot in the same block."},
 "attacker_block": 12995895,
 "attacker_block_note": "The attacker's tx 0x7604c7dd landed in the SAME block at index 52 and succeeded (status 1) but withdrew only 0.028802 USDC, 0.036879 USDT, 0.030391 DAI.",
 "attacker_reference": {"kind": "attack-tx", "block": 12995895, "tx": ATT_TX},
 "auction": bvh.auction_summary(f"incidents/{S}/race_12995895.json", BOT_TX),
 "loot": {
   "scope": "bot-tx",
   "gross_loot_eth": round(toeth(stolen_usd), 4),
   "gross_loot_method": (f"All three pool legs the bot tx withdrew (USDC {W['USDC']:,.6f} + USDT {W['USDT']:,.4f} + DAI {W['DAI']:,.4f} = ${stolen_usd:,.2f}, stablecoins at par) divided by "
                         f"{px:,.1f} USD/ETH, the rate of the attacker's own 1inch sale of {usdc_sold:,.4f} USDC for {eth_got:.4f} ETH at 07:10:24Z, 15 min after the race (tx 0x60c0757b). Derived, not an oracle price (+/-0.5%)."),
   "captured_native": {"amount": f"{W['USDT']:,.4f} USDT + {W['DAI']:,.4f} DAI", "unit": "USDT+DAI",
                       "desc": "token transfers from the bot contract 0x00000000b2ff to the bot EOA 0x3aa27ab2 in tx 0x597d11c0; the USDC leg (2,995,824.696852) went to the ATTACKER's EOA 0x1d5a5640 instead"},
   "captured_usd": round(bot_usd, 2),
   "captured_usd_source": "USDT + DAI at par (stablecoins), amounts from the bot tx receipt's Transfer logs; excludes the USDC that the bot's tx sent to the attacker. Same $8.95M total as Punk's incident report / rekt.",
   "coinbase_paid_eth": 0.0, "priority_fee_paid_eth": tip,
   "builder_refund_to_bot_eth": None, "builder_payout_to_victim_eth": None,
   "bot_net_eth": round(toeth(bot_usd) - fee_total, 4),
   "loot_note": (f"Scope = the bot tx. gross_loot_eth covers everything it took from the pools (${stolen_usd:,.0f}); {W['USDC']:,.0f} USDC of that was sent on to the attacker by the bot's copy error, so the bot's own "
                 f"side is ${bot_usd:,.0f} (bot_net_eth = that / {px:,.1f} minus the tx's gas fee {fee_total:.5f} ETH, of which {tip:.5f} ETH tip to the miner and the rest burned as base fee). No coinbase "
                 f"payment. The attacker's tx in the same block paid a {eth(a['priority_fee_total_wei']):.5f} ETH tip and withdrew dust. Counterfactual (anvil): the attacker alone would have received "
                 f"${sum(cf.values()):,.2f}.")},
 "fate": {
   "return_status": "returned",
   "returned_by_bot_eth": round(toeth(ret_usd), 4), "returned_by_builder_eth": None, "returned_total_eth": round(toeth(ret_usd), 4),
   "returned_to": "0xe36cc0432619247ab12f1cdd19bb3e7a24a7f47c (Punk Protocol's deployer wallet, which Punk's report says it moved to a safe wallet 0xec36e967 for compensation)",
   "returned_desc": (f"2021-08-10 19:20:03Z and 19:21:37Z (blocks 12999327, 12999334) the bot EOA sent {usdt_ret:,.6f} USDT and {dai_ret:,.6f} DAI (${ret_usd:,.2f}) to Punk's deployer wallet, after Punk "
                     f"messaged the bot EOA at 12:03Z (it first thought the bot was the attacker) and the bot answered 'I frontran the real attacker' at 13:45Z. Before returning, at 19:17:54Z, the bot sold 1,000,000 DAI "
                     f"for {fee_eth:.4f} ETH on 1inch: the $1M finder's fee Punk agreed ('after paying a fee of 1M DAI up to approximately 16% of the retrieved'). ETH figures here are stablecoin amounts divided by "
                     f"{px:,.1f} USD/ETH (the attacker's 1inch rate). Share of the $8.95M drained: {ret_usd/stolen_usd*100:.1f}%; of the bot's own USDT+DAI take: {ret_usd/bot_usd*100:.1f}%. The $2.996M USDC the bot "
                     f"mis-sent to the attacker was not recovered (sold for 960.3 ETH, 968 ETH to Tornado Cash); the attacker also took 45,100 DAI in a second tx and ignored Punk's on-chain message."),
   "bounty_kept_eth": fee_eth,
   "bounty_desc": "1,000,000 DAI (about 16.8% of the 5.954M the bot held) sold for ETH by the bot EOA before the return, with Punk's agreement",
   "kept_by_bot_eth": fee_eth,
   "returned_txs": rets,
   "public_statement": ("Rekt: 'a whitehat was able to frontrun the transactions and return over half of the funds ... my frontrun was not perfect, as I did end up sending $3M USDC to the original hacker. "
                        "Rewriting txs can be tricky.' Punk incident report (Medium, read via Wayback): 'a white-hat hacker noticed this attempt of attack with a bot and made a transaction, which was executed "
                        "before the original'; recovered $4,954,250 after a 1M DAI fee. On-chain, bot to attacker 2021-08-10T20:08:31Z: 'Fixed the bug in my bot which kept your USDC transfer in place.' Halborn: "
                        "'This bot observed the attacker's transaction and performed it first.'")},
 "raw_refs": refs,
 "rawref_gaps": [
   {"field": "ETH-equivalent figures (gross_loot_eth, bot_net_eth, returned_*_eth)", "why": "stablecoin legs converted at the attacker's own 1inch sale rate (3,119.7 USD/ETH, saved in punk_att_eoa_txlist/txlistinternal/tokentx); no oracle price saved. The bot's own 1inch sale 12 h later implies 3,133.0."},
   {"field": "pending-tx timing", "why": "no mempool archive before 2023-08; whether/when the bot saw the attacker's tx pending cannot be measured"}],
 "discrepancies": inc["discrepancies"] + disc,
 "evidence_notes": [
   "Call diff (incidents/punk-2021/call_diff.json): both txs call USDC, USDT, DAI CompoundModel pools in that order with initialize -> invest -> withdrawToForge; initialize() args 1-5 identical; arg 0 = the bot's own contract vs the attacker's 0x1695ce70.",
   "The bot contract's USDC transfer goes to the ATTACKER EOA 0x1d5a5640 (2,995,824.696852 USDC); USDT and DAI go to the bot EOA. The bot's own message later: 'Fixed the bug in my bot which kept your USDC transfer in place'.",
   "Anvil fork of block 12995894 (incidents/punk-2021/anvil_replay.json): attacker alone = 2,995,824.73 USDC + 3,000,022.82 USDT + 2,954,191.57 DAI; bot then attacker = on-chain figures exactly; attacker then bot = the bot's tx reverts.",
   "trace_filter over blocks 12944900-13000000: initialize() on the three pools was called only by Punk's deployer (at deployment), the bot (idx 50) and the attacker (idx 52 and 205). Nobody else raced.",
   "Attacker had no tx before the bot except the contract deploy (block 12994067) and two Tornado top-ups; his tx was effective 40.00 gwei (maxFee 40 caps maxPriority 25), the bot's 43.33 gwei (maxFee 66.70, tip 13.30).",
   "Pre-Merge, in-block evidence only; no coinbase payments; the block's bundle-like txs are idx 0-2 (inferred label)."],
 "incident_dir": f"incidents/{S}",
}
write(S, [row])
