"""Local anvil replay (fork of block 12995894, the state the block-12995895 txs started from) of the Punk Protocol attacker tx and the
white-hat bot tx. Writes incidents/punk-2021/anvil_replay.json. Nothing is broadcast; senders are impersonated on the local fork.

  anvil --fork-url https://eth.drpc.org --fork-block-number 12995894 --port 8563 --base-fee 0 --gas-price 0 --order fifo --hardfork london
  .venv/bin/python incidents/punk-2021/scripts/anvil_replay.py

Scenarios (one block each, both txs in the same block in the stated order):
  attacker_alone   : only the attacker's tx 0x7604c7dd (what the attacker would have received if nothing had been in front of it)
  bot_then_attacker: bot tx 0x597d11c0 then attacker tx (the on-chain order)
  attacker_then_bot: attacker first, bot second (the order the attacker intended)
"""
import json, pathlib, sys, time, urllib.request
ROOT = pathlib.Path(__file__).resolve().parents[3]
A = "0x7604c7dd6e9bcdba8bac277f1f8e7c1e4c6bb57afd4ddf6a16f629e8495a0281"
B = "0x597d11c05563611cb4ad4ed4c57ca53bbe3b7d3fefc37d1ef0724ad58904742b"
URL = "http://127.0.0.1:8563"
TOK = {"0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": ("USDC", 6), "0xdac17f958d2ee523a2206206994597c13d831ec7": ("USDT", 6),
       "0x6b175474e89094c44da98b954eedeac495271d0f": ("DAI", 18)}
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
NAME = {"0x1d5a56402425c1099497c1ad715a6b56aaccb72b": "attacker EOA", "0x1695ce70da4521cb94dea036e6ebcf1e8a073ee6": "attacker contract",
        "0x3aa27ab297a3a753f79c5497569ba2dacc2bc35a": "bot EOA", "0x00000000b2ff98680adaf8a3e382176bbfc34c8f": "bot contract"}


def call(m, p):
    r = urllib.request.urlopen(urllib.request.Request(URL, json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p}).encode(),
                                                      {"Content-Type": "application/json"}), timeout=900)
    j = json.loads(r.read())
    if "error" in j:
        raise RuntimeError(j["error"])
    return j["result"]


def tx(h):
    d = json.load(open(ROOT / f"data/raw/rpc/tx_{h}.json"))
    return d.get("result", d)


def send(h):
    t = tx(h)
    call("anvil_impersonateAccount", [t["from"]]); call("anvil_setBalance", [t["from"], hex(10 ** 20)])
    return call("eth_sendTransaction", [{"from": t["from"], "to": t["to"], "value": t["value"], "data": t["input"], "gas": hex(30_000_000), "gasPrice": "0x0"}])


def summarize(hashes):
    res = []
    for h, rh in hashes:
        rc = None
        for _ in range(30):
            rc = call("eth_getTransactionReceipt", [rh])
            if rc:
                break
            time.sleep(0.5)
        tr = []
        for lg in rc["logs"]:
            if lg["topics"][0] == TRANSFER and lg["address"].lower() in TOK and len(lg["topics"]) == 3:
                s, d = TOK[lg["address"].lower()]
                f, to = "0x" + lg["topics"][1][26:], "0x" + lg["topics"][2][26:]
                tr.append({"token": s, "from": NAME.get(f, f), "to": NAME.get(to, to), "amount": int(lg["data"], 16) / 10 ** d})
        net = {}
        for x in tr:
            if x["to"] in ("attacker EOA", "bot EOA"):
                net.setdefault(x["to"], {}).setdefault(x["token"], 0.0)
                net[x["to"]][x["token"]] += x["amount"]
        res.append({"onchain_tx": h, "status": int(rc["status"], 16), "gasUsed": int(rc["gasUsed"], 16), "block": int(rc["blockNumber"], 16),
                    "net_token_received_by_eoa": net})
    return res


def scenario(order):
    snap = call("evm_snapshot", [])
    call("evm_setAutomine", [False])
    hs = [(h, send(h)) for h in order]
    call("evm_mine", [])
    call("evm_setAutomine", [True])
    out = summarize(hs)
    call("evm_revert", [snap])
    return out


def main():
    out = {"schema": "bvh-anvil/1", "fork_block": 12995894,
           "note": "Block 12995895 contains no other tx touching the three Punk CompoundModel pools (trace_filter, data/raw/rpc/punk_tf_test.json), so the fork state at the end of 12995894 is the pre-state for both txs. Gas price 0, senders impersonated; token movements are read from the receipts' Transfer logs.",
           "attacker_tx": A, "bot_tx": B}
    out["attacker_alone"] = scenario([A])
    out["bot_then_attacker"] = scenario([B, A])
    out["attacker_then_bot"] = scenario([A, B])
    json.dump(out, open(ROOT / "incidents/punk-2021/anvil_replay.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


main()
