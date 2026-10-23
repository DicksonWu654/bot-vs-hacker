"""Extract kelp-rseth-2026 -> data/extract/kelp-rseth-2026.json (incident dataset, one row). Run from project root:
  .venv/bin/python scripts/dataset/extract_kelp-rseth-2026.py
Requires data/raw/rpc/ethcall2_exec_882d_arbitrary_at_25980523.json (the 'not prepared' revert, fetched during incident dataset because the
incident.json reference was missing; saved via rawfetch._save with the original request params)."""
import json, pathlib, sys, datetime
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import bvh

SLUG = "kelp-rseth-2026"
D = f"incidents/{SLUG}"
E18 = 10 ** 18
J = lambda p: json.load(open(ROOT / p))
res = lambda d: d["result"] if isinstance(d, dict) and "result" in d else d
iso = lambda ts: datetime.datetime.fromtimestamp(int(ts), datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
RPC, ES = "data/raw/rpc/", "data/raw/etherscan/"
inc = J(f"{D}/incident.json")
BOT = "0x0e7680b06cb8a6f86c149d9ba90d98e3d334e7b072dde03909d43fcfd98a8705"
BOT2 = "0x16b9ddf976b805e20e08ff49e3f1d01ac7605814fb489f8795c7d95fbc3eeb45"
PREP = "0x0a7d69abe64d99c77741a54639057e077d096bc68cde094a1a05590557f76e56"
DEPLOY = "0x946e318b52474d8832451abf7716f65822f4562acb25a6ce453b159055904c69"
BURN = "0xe8c2776814ec291e160ac433abe96def4c3ff10e380f5d42e324e27b8463ee4f"
FUND = "0xd07ce4dc6acf73501467cda47400ea5768b3fa7093cca9f634ef33203b38717c"
ATT, EXEC = "0x0dc2c5d6b05a317076cf501f7e7be36a5dfe9b66", "0x10605ee48ff962952c966277a5d2dac0a0705cb1"
YEOA, YCT = "0xfde0d1575ed8e06fbf36256bcdfa1f359281455a", "0x80bf7db69556d9521c03461978b8fc731dbbd4e4"
VAULT, OWNER = "0xc70f00cd7e461686b04b0e912e309beca8b80ea0", "0x8c2aeccef3b3634d039c96993577f80d3278fee8"
SAFE = "0x40e93a52f6af9fcd3b476aedadd7feabd9f7aba8"
POOLMGR = "0x000000000004444c5dc75cb358380d2e3de08a90"
RSETH = "0xa1290d69c65a6fe4df752f95823fae25cb99e5a7"

races = {n: J(f"{D}/race_{n}.json") for n in (25980523, 25980524, 25980525)}
r5 = races[25980525]
txs = {t["hash"]: t for t in r5["txs"]}
t0 = txs[BOT]
assert t0["index"] == 0 and t0["status"] == 1 and t0["from"] == YEOA and t0["to"] == YCT and r5["block"]["number"] == 25980525
cb = int(t0["coinbase_transfer_wei"]) / E18
assert abs(cb - 18.93122243326834) < 1e-12 and t0["priority_fee_total_wei"] == "0"
t2 = txs[BOT2]
assert t2["index"] == 3 and t2["status"] == 1 and t2["from"] == "0x492d255234c83f2ddc5aa904d8a9db6743e9f046"
cb2 = int(t2["coinbase_transfer_wei"]) / E18

# ---- Yoink tx trace: call into the attacker's executor + the in-tx swap
tr = res(J(RPC + f"trace_{BOT}.json"))
calls = []
def walk(c, out):
    out.append(c)
    for x in c.get("calls", []) or []:
        walk(x, out)
allc = []; walk(tr, allc)
ex = [c for c in allc if c.get("to", "").lower() == EXEC]
assert len(ex) == 1 and ex[0]["from"].lower() == YCT and ex[0]["input"][:10] == "0x882d6bfa" and not ex[0].get("error")
assert int(ex[0]["input"][10:74], 16) == 2900 * E18
tr2 = res(J(RPC + f"trace_{BOT2}.json")); a2 = []; walk(tr2, a2)
ex2 = [c for c in a2 if c.get("to", "").lower() == EXEC]
assert len(ex2) == 1 and ex2[0]["input"][:10] == "0x882d6bfa" and ex2[0].get("error") == "execution reverted"
swap_in = swap_out = None
rc = res(J(RPC + f"rcpt_{BOT}.json"))
T = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
pulled = to_yoink = to_pm = to_vault = None
for l in rc["logs"]:
    if l["topics"][0] == T and len(l["topics"]) == 3 and l["address"].lower() == RSETH and l["data"] != "0x":
        frm, to, v = "0x" + l["topics"][1][-40:], "0x" + l["topics"][2][-40:], int(l["data"], 16)
        if frm == EXEC and to == YCT: to_yoink = v
        if frm == YCT and to == POOLMGR: to_pm = v
        if frm == YCT and to == VAULT: to_vault = v
assert to_yoink and to_pm and to_vault and abs(to_pm + to_vault - to_yoink) < 10**6  # wei-level rounding (199 wei) in the token transfers
pm_back = [int(c["value"], 16) for c in allc if c.get("from", "").lower() == POOLMGR and c.get("to", "").lower() == YCT and int(c.get("value", "0x0"), 16) > 0]
assert len(pm_back) == 1
swap_eth = pm_back[0] / E18
swap_rs = to_pm / E18
rate = swap_eth / swap_rs                 # ETH per rsETH, from the swap inside the bot tx
pulled_rs = to_yoink / E18
vault_rs = to_vault / E18
assert abs(vault_rs - 2882.367408826118) < 1e-12 and abs(swap_rs - 17.632591173879632) < 1e-12 and abs(pulled_rs - 2899.9999999999977) < 1e-9
gross = pulled_rs * rate
net = gross - cb
leftover = swap_eth - cb
assert abs(pulled_rs - swap_rs - vault_rs) < 1e-9

# ---- eth_call test (state after block N): 522 no code, 523 reverts 'not prepared', 524 succeeds
c522 = J(RPC + "ethcall2_exec_882d_arbitrary_at_25980522.json")
c523 = J(RPC + "ethcall2_exec_882d_arbitrary_at_25980523.json")
c524 = J(RPC + "ethcall2_exec_882d_arbitrary_at_25980524.json")
assert c522["result"] == "0x" and "not prepared" in c523["error"]["message"] and c524["result"].startswith("0x0000") and len(c524["result"]) > 10
assert int(c524["result"][2:66], 16) >= 2899 * E18

# ---- attacker side
atx = {t["hash"]: t for t in res(J(ES + "k_txlist_0x0dc2c5d6b05a317076cf501f7e7be36a5dfe9b66.json"))}
assert atx[DEPLOY]["nonce"] == "2" and atx[PREP]["nonce"] == "3" and atx[BURN]["nonce"] == "4" and atx[BURN]["to"].lower() == ATT and atx[BURN]["value"] == "0"
assert atx[PREP]["to"].lower() == EXEC and atx[PREP]["input"][:10] == "0xd28cebb8" and atx[PREP]["blockNumber"] == "25980524"
assert not [h for h in atx.values() if h["isError"] != "0"]       # no reverted tx on the attacker EOA
fund = next(x for x in res(J(ES + "k_txlistinternal_0x0dc2c5d6b05a317076cf501f7e7be36a5dfe9b66.json")) if x["hash"] == FUND)
assert fund["from"].lower() == "0xac9f360ae85469b27aeddeafc579ef2d052ad405" and fund["blockNumber"] == "25976003"
rp = races[25980524]; pt = next(t for t in rp["txs"] if t["hash"] == PREP)
assert pt["index"] == 207 and pt["status"] == 1
dp = next(t for t in races[25980523]["txs"] if t["hash"] == DEPLOY)
assert dp["index"] == 155 and dp["to"] is None and dp["status"] == 1
mp = J(f"{D}/mempool_lookup_2026-09-15.json")
assert all(v is None for v in mp.values()) and BOT in mp and PREP in mp
mp2 = J("data/raw/mempool-dumpster/kelp_attacker_executor_yoink_2026-09-15.json")
assert mp2["rows"] == []

# ---- builder side
pay = txs["0x29e6d2a277e9d34261139f5987f9acf25c7f7a45ede6100a65b442027894fd65"]
assert pay["index"] == 26 and pay["from"] == r5["block"]["fee_recipient"]
pay_eth = int(pay["value_wei"]) / E18
bld_rev = sum(int(x["builder_revenue_wei"]) for x in r5["txs"]) / E18
a = bvh.auction_summary(f"{D}/race_25980525.json", BOT)
miss = a.pop("_missing_raw"); assert not miss
assert abs(pay_eth - a["winning_bid_eth"]) < 1e-9
bots_addr = {YEOA, YCT, VAULT}
refund_n = 0
b = J(RPC + "block_25980525.json")["result"]
for t in b["transactions"]:
    if t["to"] and t["to"].lower() in bots_addr and t["from"].lower() not in bots_addr and int(t["value"], 16) > 0:
        refund_n += 1
for t in J(RPC + "trace_block_25980525.json")["result"]:
    x = t.get("action", {})
    if x.get("to", "").lower() == YCT and x.get("from", "").lower() not in bots_addr and int(x.get("value", "0x0"), 16) > 0 and x.get("from", "").lower() != POOLMGR:
        refund_n += 1
assert refund_n == 0
a["auction_note"] = (
    "Winning block: builder.ultrasound.money, bid %.4f ETH delivered by the ultrasound relay only (that relay publishes no bids, so the winning block's submission time is unknown); builder -> proposer payment tx %s (idx 26) equals the bid. "
    "Higher bids existed but were not chosen: the highest visible bid was %.4f ETH (Eureka, +1416 ms via agnostic / +1469 ms via flashbots). Block builder revenue %.4f ETH of which the builder kept %.4f ETH (%.1f%%); "
    "Yoink's coinbase transfer was %.4f ETH (paid out of 17.63 rsETH swapped on Uniswap v4). 51 builders and 5,937 bids from 6 relays; no builder -> bot refund in this block."
) % (a["winning_bid_eth"], pay["hash"], a["max_bid_eth"], bld_rev, bld_rev - pay_eth, (bld_rev - pay_eth) / bld_rev * 100, cb)

# ---- returns
vt = {x["hash"]: x for x in res(J(ES + "c70f_rseth_real_tokentx.json"))}
R1 = "0x03d31426be57673645f3da0de091135383e09ea7f376b55e5457bdc0267c9ac7"
R2 = "0xe1615caa9f8fe328f6d336a8f4006a54b9342ea6b1cfb3a7fa4e733dbd120c6e"
assert vt[R1]["to"].lower() == OWNER and vt[R2]["to"].lower() == OWNER and vt[R1]["from"].lower() == VAULT and vt[R2]["from"].lower() == VAULT
ret_rs = (int(vt[R1]["value"]) + int(vt[R2]["value"])) / E18
assert abs(ret_rs - vault_rs) < 1e-12
eg = res(J(RPC + "ethcall_0x40e93a52f6af9fcd3b476aedadd7feabd9f7aba8_getOwners_latest.json"))
owners = ["0x" + eg[2 + 128 + 24 + i * 64: 2 + 128 + 64 + i * 64] for i in range(3)]
assert OWNER in owners, owners
ret_eth = ret_rs * rate
t_ret1, t_ret2 = int(vt[R2]["timeStamp"]), int(vt[R1]["timeStamp"])
hours = (int(vt[R2]["timeStamp"]) - r5["block"]["timestamp"]) / 3600
rows_refs = {
    "bot.block": RPC + "block_25980525.json", "bot.position": RPC + "block_25980525.json",
    "loot.gross_loot_eth": [RPC + f"trace_{BOT}.json", RPC + f"rcpt_{BOT}.json"],
    "loot.coinbase_paid_eth": [RPC + "trace_block_25980525.json", RPC + f"trace_{BOT}.json"],
    "loot.priority_fee_paid_eth": [RPC + "receipts_25980525.json", RPC + "block_25980525.json"],
    "loot.builder_refund_to_bot_eth": [RPC + "block_25980525.json", RPC + "trace_block_25980525.json"],
    "loot.bot_net_eth": [RPC + f"trace_{BOT}.json", RPC + f"rcpt_{BOT}.json", RPC + "trace_block_25980525.json"],
    "loot.captured_usd": "data/raw/web-w4/cryptonews_yoink_kelp.html",
    "fate.returned_by_bot_eth": [ES + "c70f_rseth_real_tokentx.json", RPC + f"rcpt_{BOT}.json"],
    "fate.returned_total_eth": [ES + "c70f_rseth_real_tokentx.json", RPC + "ethcall_0x40e93a52f6af9fcd3b476aedadd7feabd9f7aba8_getOwners_latest.json"],
    "fate.kept_by_bot_eth": [RPC + f"trace_{BOT}.json"],
    "executor_not_prepared_test": [RPC + "ethcall2_exec_882d_arbitrary_at_25980522.json", RPC + "ethcall2_exec_882d_arbitrary_at_25980523.json", RPC + "ethcall2_exec_882d_arbitrary_at_25980524.json"],
}
row = {
    "slug": SLUG, "name": "Kelp-related rsETH holder Safe exploit 2026-09-15 (Uniswap v4 module): Yoink uses the attacker's prepared executor",
    "date_utc": r5["block"]["timestamp_utc"].replace("+00:00", "Z"), "chain": "ethereum", "orig_verdict": inc["verdict"],
    "race_type_proposed": "deploy-window-copy",
    "race_type_reason": ("The attacker deployed an executor (0x10605ee4, block 25980523) and called prepare() (block 25980524); one block later Yoink called the executor's own permissionless function (selector 0x882d6bfa, 2900e18) at position 0 "
                         "and pulled 2,900 aEthrsETH out of the victim Safe. No calldata was copied; an eth_call shows the function reverts 'not prepared' before prepare() and succeeds after it, so Yoink used the attacker's on-chain setup before the attacker's finishing call ever landed."),
    "one_liner": "One block after the attacker's prepare() tx, Yoink called the attacker's own executor and pulled 2,900 rsETH from a holder's Safe, paying a 18.93 ETH builder tip; 2,882.37 rsETH went back to a Safe signer about 30 hours later.",
    "attacker": {"eoa": ATT, "eoas": [ATT], "contracts": [EXEC], "funding": "railgun", "funding_tx": FUND, "deploy_tx": DEPLOY, "deploy_block": 25980523,
                 "attack_txs": [
                     {"hash": DEPLOY, "block": 25980523, "index": 155, "status": "success", "role": "deploys executor 0x10605ee4 (nonce 2)"},
                     {"hash": PREP, "block": 25980524, "index": 207, "status": "success", "role": "prepare() 0xd28cebb8 on the executor (nonce 3); makes the executor's function callable by anyone"},
                     {"hash": None, "block": None, "index": None, "status": "never-landed",
                      "role": "attacker's finishing call (inferred, nonce 4): never mined and invisible (private flow); nonce 4 was burned by self-transfer %s at block 25980578" % BURN}],
                 "none_reason": None},
    "bot": {"label": "Yoink", "eoa": YEOA, "contract": YCT, "tx": BOT, "block": 25980525, "position": t0["index"], "status": "success", "priority_fee_gwei": t0["priority_fee_gwei"]},
    "bots_other": [{"label": "second searcher (0x492d2552, self-calling EOA)", "eoa": "0x492d255234c83f2ddc5aa904d8a9db6743e9f046", "tx": BOT2, "block": 25980525, "position": t2["index"], "status": "success",
                    "role": "called the same executor function 0x882d6bfa three positions after Yoink in the same block; its inner call reverted (executor already drained) while the outer tx succeeded and paid %.6f ETH to the coinbase; identity and strategy not analysed" % cb2}],
    "evidence_level_mempool": "absent-from-archive",
    "mempool_note": "mempool-dumpster covers 2026-09-15 (1,025,816 rows) but holds none of the 19 attacker txs, Yoink's txs or the second searcher's txs (queried by from/to and by hash): all private flow. Whether Yoink saw the prepare tx in block 25980524 (public chain state) or in private order flow cannot be separated.",
    "trigger": {"kind": None, "tx": None, "first_seen_utc_ms": None, "first_seen_utc": None, "sources": None,
                "note": "The trigger was the attacker's prepare() tx %s (block 25980524, idx 207), which has no mempool first-seen (private); the attacker's deploy tx is also absent from the archive." % PREP},
    "attacker_block": None,
    "attacker_block_note": "The attacker's finishing call never landed (no reverted tx exists on the attacker EOA; nonce 4 was burned by a self-transfer at 25980578), so there is no attacker block for the race; the reference is the prepare() tx instead.",
    "attacker_reference": {"kind": "prepare", "block": 25980524, "tx": PREP},
    "auction": a,
    "loot": {
        "scope": "bot-tx", "gross_loot_eth": gross,
        "gross_loot_method": "%.10f rsETH pulled out of the victim Safe (Aave aEthrsETH redeemed to rsETH) x %.6f ETH per rsETH, the rate of the swap inside the same tx (%.6f rsETH -> %.6f ETH from the Uniswap v4 PoolManager)" % (pulled_rs, rate, swap_rs, swap_eth),
        "captured_native": {"amount": pulled_rs, "unit": "rsETH", "desc": "2,900 aEthrsETH redeemed to rsETH from the victim Safe %s; %.6f rsETH swapped to ETH for the builder tip, %.6f rsETH sent to vault EOA %s" % (SAFE, swap_rs, vault_rs, VAULT)},
        "captured_usd": 7810000.0, "captured_usd_source": "PeckShield alert quoted in the saved crypto.news article ('~$7.81M $rsETH', press, not recomputed); the saved Parameter and crypto.news pages say about $7.8 million",
        "coinbase_paid_eth": cb, "priority_fee_paid_eth": 0.0, "builder_refund_to_bot_eth": 0.0, "builder_payout_to_victim_eth": None,
        "bot_net_eth": net,
        "loot_note": ("Scope: the bot tx only. ETH-equivalent uses the in-tx swap rate (%.6f ETH/rsETH), not a market price, so it is an approximation. Coinbase transfer %.6f ETH to the block fee recipient 0x6c42a0b5 (builder.ultrasound.money), funded by the %.6f ETH swap proceeds (%.6f ETH left unspent in the Yoink contract). "
                      "priority fee 0 (max priority 0). No builder -> bot refund (block + trace scan). Yoink's second tx in the block (idx 1) is a routine pool backrun and is not part of this row. bot_net = gross - coinbase, before gas base fee and before the later return.") % (rate, cb, swap_eth, leftover),
    },
    "fate": {
        "return_status": "returned", "returned_by_bot_eth": ret_eth, "returned_by_builder_eth": None, "returned_total_eth": ret_eth,
        "returned_to": "%s: an EOA that is one of the 3 owners (threshold 1) of the victim Safe %s (owner list from eth_call getOwners; the person is not identified)" % (OWNER, SAFE),
        "returned_desc": ("Yoink's vault EOA %s returned the whole 2,882.367408826118 rsETH it received (100%% of the vault's receipt, 99.39%% of the 2,900 pulled; the other 17.6326 rsETH paid the builder tip) to %s in two txs: 1.0 rsETH (test) at %s and 2,881.367408826118 rsETH at %s, about %.1f hours after the take. "
                          "ETH-equivalent is rsETH x %.6f (in-tx swap rate). Later Aave liquidations of the Safe (including Yoink's own at 25980901, 157.7 aEthrsETH) are separate and not part of this row. KelpDAO reportedly restricted the vault address for 24 h (press), which may relate to the timing; not established."
                          % (VAULT, OWNER, iso(vt[R1]["timeStamp"]), iso(vt[R2]["timeStamp"]), hours, rate)),
        "bounty_kept_eth": None, "bounty_desc": "No bounty found; the whole vault receipt was returned.",
        "kept_by_bot_eth": leftover,
        "returned_txs": [
            {"tx": R1, "eth": 1.0 * rate, "note": "vault -> Safe owner 0x8c2aecce: 1.0 rsETH (test); ETH-equivalent at the in-tx swap rate", "block": int(vt[R1]["blockNumber"]), "time_utc": iso(vt[R1]["timeStamp"])},
            {"tx": R2, "eth": (int(vt[R2]["value"]) / E18) * rate, "note": "vault -> Safe owner 0x8c2aecce: 2,881.367408826118 rsETH; ETH-equivalent at the in-tx swap rate", "block": int(vt[R2]["blockNumber"]), "time_utc": iso(vt[R2]["timeStamp"])},
        ],
        "public_statement": "KelpDAO (via saved Parameter article): restricted the address holding the recovered funds for 24 hours and said its core contracts remained secure. The saved crypto.news article records that, at the time, the vault address's owner was not identified and no return was described.",
    },
    "raw_refs": rows_refs, "rawref_gaps": [
        {"field": "attacker_block", "why": "the attacker's finishing call never landed; null by design (attacker_reference = prepare tx)"},
        {"field": "trigger.first_seen_utc_ms", "why": "attacker deploy/prepare txs and all bot txs are absent from the mempool-dumpster 2026-09-15 file (private flow)"},
        {"field": "fate.returned_by_builder_eth", "why": "no builder return exists; builder kept 5.09 ETH of its block revenue (null, not 0)"},
        {"field": "loot.captured_usd", "why": "USD figure is press-reported (PeckShield via crypto.news, ~$7.81M); no priced raw feed was saved for rsETH on 2026-09-15"}],
    "discrepancies": [
        "incident.json raw_refs list data/raw/rpc/ethcall2_exec_882d_arbitrary_at_25980523.json but the file did not exist; it was fetched during this extraction (eth_call at block 25980523 reverts 'execution reverted: not prepared') and saved with its request params. The 25980522 files return '0x' because the executor is not deployed yet (deployed in 25980523), so they show no revert.",
        "incident.json bots[0].captured.usd is 7,700,000 and protocol_loss_usd 7,730,000 (cites Blockaid/CoinTelegraph, page not saved); the saved crypto.news/Parameter pages quote ~$7.81M (PeckShield) / $7.8M. The saved value is used here.",
        "ETH-equivalents use the in-tx swap rate %.6f ETH per rsETH (not a market price)." % rate],
    "evidence_notes": [
        "Yoink's contract calls the attacker's executor %s selector 0x882d6bfa with (2900e18,0,0) inside tx %s (data/raw/rpc/trace_%s.json); no calldata of any attacker tx is reused." % (EXEC, BOT, BOT),
        "eth_call of the same function from an arbitrary address: no code at state 25980522 ('0x'), reverts 'execution reverted: not prepared' at 25980523, succeeds (returns 2900e18-scale values) at 25980524 (data/raw/rpc/ethcall2_exec_882d_arbitrary_at_25980522.json, ..._23.json, ..._24.json).",
        "Attacker txs from the EOA's Etherscan list: deploy 25980523 idx 155 (nonce 2), prepare() 25980524 idx 207 (nonce 3), burned nonce 4 at 25980578; no reverted tx exists on the EOA; funded by a Railgun unshield at 25976003 (data/raw/etherscan/k_txlist_0x0dc2c5d6b05a317076cf501f7e7be36a5dfe9b66.json).",
        "Second searcher 0x492d2552 (idx 3, same block) called the same executor function and its inner call reverted: incidents/kelp-rseth-2026/race_25980525.json and data/raw/rpc/trace_%s.json." % BOT2,
        "Return: vault tokentx shows 2,882.367408826118 rsETH in (25980525) and 1.0 + 2,881.367408826118 out to 0x8c2aecce on 2026-09-16 (data/raw/etherscan/c70f_rseth_real_tokentx.json); 0x8c2aecce is in the Safe's getOwners list."],
    "incident_dir": D,
}
miss = [p for v in row["raw_refs"].values() for p in (v if isinstance(v, list) else [v]) if not (ROOT / p).exists()]
assert not miss, miss
out = ROOT / "data" / "extract" / f"{SLUG}.json"
json.dump([row], open(out, "w"), indent=1)
print("wrote", out, "rate", rate, "gross", gross, "net", net, "ret_eth", ret_eth, "leftover", leftover)
