"""Punk Protocol 2021-08-10: victim-call diff between the bot (front-run) tx and the attacker's tx, from saved callTracer traces
and receipts. Writes incidents/punk-2021/call_diff.json. Run from project root:  .venv/bin/python incidents/punk-2021/scripts/call_diff.py

Only the calls into the three Punk CompoundModel contracts and the token transfers that follow are compared (public tx-level facts).
"""
import json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from keccak_sel import selector  # noqa: E402

ATT = "0x7604c7dd6e9bcdba8bac277f1f8e7c1e4c6bb57afd4ddf6a16f629e8495a0281"
BOT = "0x597d11c05563611cb4ad4ed4c57ca53bbe3b7d3fefc37d1ef0724ad58904742b"
ATT_EOA = "0x1d5a56402425c1099497c1ad715a6b56aaccb72b"
ATT_C = "0x1695ce70da4521cb94dea036e6ebcf1e8a073ee6"
BOT_EOA = "0x3aa27ab297a3a753f79c5497569ba2dacc2bc35a"
BOT_C = "0x00000000b2ff98680adaf8a3e382176bbfc34c8f"
MODELS = {"0x3bc6aa2d25313ad794b2d67f83f21d341cc3f5fb": ("USDC", "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", 6),
          "0x1f3b04c8c96a31c7920372ffa95371c80a4bfb0d": ("USDT", "0xdac17f958d2ee523a2206206994597c13d831ec7", 6),
          "0x929cb86046e421abf7e1e02de7836742654d49d6": ("DAI", "0x6b175474e89094c44da98b954eedeac495271d0f", 18)}
SIG = {selector("initialize(address,address,address,address,address,address)"): "initialize(forge,token,cToken,comp,comptroller,uniRouterV2)",
       selector("invest()"): "invest()",
       selector("withdrawToForge(uint256)"): "withdrawToForge(amount)"}
assert set(SIG) == {"0xcc2a9a5b", "0xe8b5e51f", "0x7b9967a5"}, SIG
TOK = {v[1]: (v[0], v[2]) for v in MODELS.values()}
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def L(p):
    d = json.load(open(ROOT / p))
    return d.get("result", d) if isinstance(d, dict) else d


def victim_calls(h):
    t = L(f"data/raw/rpc/trace_{h}.json")
    out = []

    def w(c, ok=True):
        okh = ok and not c.get("error")
        to = (c.get("to") or "").lower()
        if to in MODELS and c.get("input", "")[:10] in SIG:
            inp = c["input"]
            words = [inp[10 + 64 * i:74 + 64 * i] for i in range((len(inp) - 10) // 64)]
            args = [int(x, 16) if inp[:10] == "0x7b9967a5" else "0x" + x[24:] for x in words]
            out.append({"model": MODELS[to][0], "model_addr": to, "caller": c["from"].lower(), "call": SIG[inp[:10]], "selector": inp[:10],
                        "args": args, "reverted": not okh})
        for x in c.get("calls") or []:
            w(x, okh)
    w(t)
    return out


def transfers(h):
    rc = L(f"data/raw/rpc/rc_{h}.json")
    out = []
    for lg in rc["logs"]:
        if lg["topics"][0] == TRANSFER and lg["address"].lower() in TOK and len(lg["topics"]) == 3:
            sym, dec = TOK[lg["address"].lower()]
            out.append({"token": sym, "from": "0x" + lg["topics"][1][26:], "to": "0x" + lg["topics"][2][26:],
                        "amount": int(lg["data"], 16) / 10 ** dec, "raw": int(lg["data"], 16)})
    return out


def who(a):
    return {ATT_C: "attacker contract", ATT_EOA: "attacker EOA", BOT_C: "bot contract", BOT_EOA: "bot EOA"}.get(a, a[:10])
    

def main():
    va, vb = victim_calls(ATT), victim_calls(BOT)
    ta, tb = transfers(ATT), transfers(BOT)
    # pair calls by (model, call name); the attacker's tx has a second initialize per model (restoring Punk's forge)
    pairs = []
    for m in ("USDC", "USDT", "DAI"):
        for name in ("initialize(forge,token,cToken,comp,comptroller,uniRouterV2)", "invest()", "withdrawToForge(amount)"):
            a = [c for c in va if c["model"] == m and c["call"] == name]
            b = [c for c in vb if c["model"] == m and c["call"] == name]
            pairs.append({"model": m, "call": name,
                          "bot": [{"args": c["args"], "reverted": c["reverted"], "caller": who(c["caller"])} for c in b],
                          "attacker": [{"args": c["args"], "reverted": c["reverted"], "caller": who(c["caller"])} for c in a]})
    # equality analysis on initialize: args[1:] identical?
    init_same_rest = True; init_forge = {}
    for m in ("USDC", "USDT", "DAI"):
        b0 = [c for c in vb if c["model"] == m and c["call"].startswith("initialize")][0]
        a0 = [c for c in va if c["model"] == m and c["call"].startswith("initialize")][0]
        a1 = [c for c in va if c["model"] == m and c["call"].startswith("initialize")][1]
        init_same_rest &= (b0["args"][1:] == a0["args"][1:] == a1["args"][1:])
        init_forge[m] = {"bot": b0["args"][0], "attacker_first": a0["args"][0], "attacker_second_restores": a1["args"][0]}
    assert init_same_rest
    amounts = {}
    for m, (sym, tok, dec) in {k: v for k, v in zip(("USDC", "USDT", "DAI"), MODELS.values())}.items():
        b = [c for c in vb if c["model"] == m and c["call"].startswith("withdrawToForge")][0]["args"][0]
        a = [c for c in va if c["model"] == m and c["call"].startswith("withdrawToForge")][0]["args"][0]
        amounts[m] = {"bot_withdraw_raw": b, "bot_withdraw": b / 10 ** dec, "attacker_withdraw_raw": a, "attacker_withdraw": a / 10 ** dec}
    # onward transfers (token sent out of the executing contract)
    def onward(tr, frm):
        return [{"token": t["token"], "to": who(t["to"]), "to_addr": t["to"], "amount": t["amount"]} for t in tr if t["from"] == frm]
    out = {
        "schema": "bvh-calldiff/1", "slug": "punk-2021", "block": 12995895,
        "bot_tx": BOT, "bot_index": 50, "attacker_tx": ATT, "attacker_index": 52,
        "method": "callTracer traces (data/raw/rpc/trace_<tx>.json) filtered to calls into the three CompoundModel contracts; selectors "
                  "resolved with keccak256 of the verified-source signatures; token movements from the receipts' ERC-20 Transfer logs.",
        "models": {v[0]: k for k, v in MODELS.items()},
        "victim_call_sequence": {"bot": [f"{c['model']}.{c['call'].split('(')[0]}" for c in vb],
                                 "attacker": [f"{c['model']}.{c['call'].split('(')[0]}" for c in va]},
        "pairs": pairs,
        "initialize_forge_argument": init_forge,
        "initialize_other_five_args_identical_in_bot_and_attacker": init_same_rest,
        "withdraw_amounts": amounts,
        "differences": [
            "initialize(): argument 0 (the new 'forge' = the address allowed to withdraw) is the bot's own contract 0x00000000b2ff... in the bot tx and the attacker's contract 0x1695ce70... in the attacker tx. Arguments 1-5 (token, cToken, COMP, Comptroller, Uniswap V2 router) are identical for all three pools.",
            "Per pool the call order is initialize -> invest -> withdrawToForge in both txs, pools in the same order (USDC, USDT, DAI).",
            "withdrawToForge(amount): the bot passes the pools' full balances (2,995,824.696852 USDC; 3,000,022.7862 USDT; 2,954,191.544043 DAI). The attacker's calldata contains no amounts and his contract withdrew whatever was left after the bot: 0.028802 USDC, 0.036879 USDT, 0.030391 DAI.",
            "After the withdrawal the bot's contract sends USDT and DAI to the bot EOA 0x3aa27ab2 but sends the USDC to the ATTACKER's EOA 0x1d5a5640 (the recipient was not rewritten): 2,995,824.696852 USDC.",
            "The attacker's tx additionally re-calls initialize() on each pool to put Punk's own forge address back (0x0a548513 / 0x0d73ad70 / 0xc9309a61, the addresses Punk's deployer set at deployment), which is why the pools kept working for deposits after the block.",
        ],
        "bot_onward_transfers": onward(tb, BOT_C),
        "attacker_onward_transfers": onward(ta, ATT_C),
        "bot_tx_all_token_transfers": tb, "attacker_tx_all_token_transfers": ta,
        "raw_refs": {"traces": [f"data/raw/rpc/trace_{ATT}.json", f"data/raw/rpc/trace_{BOT}.json"],
                     "receipts": [f"data/raw/rpc/rc_{ATT}.json", f"data/raw/rpc/rc_{BOT}.json"],
                     "txs": [f"data/raw/rpc/tx_{ATT}.json", f"data/raw/rpc/tx_{BOT}.json"],
                     "model_source": "data/raw/etherscan/punk_usdc_model_source.json"},
    }
    json.dump(out, open(ROOT / "incidents/punk-2021/call_diff.json", "w"), indent=1)
    print(json.dumps({k: out[k] for k in ("victim_call_sequence", "initialize_forge_argument", "withdraw_amounts", "bot_onward_transfers", "attacker_onward_transfers")}, indent=1))


if __name__ == "__main__":
    main()
