"""LOCAL anvil fork (block 20240538 = parent of the race block): replay the DeFi Plaza attacker's own deploy + run() txs and
compare their DeFiPlaza call sequence with Yoink's tx 0xa245deda... Nothing is broadcast; every tx goes to the local anvil only."""
import json, subprocess, sys, time, urllib.request, pathlib, os
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))
import rawfetch as r
PORT = 8611; URL = f"http://127.0.0.1:{PORT}"
ATK = "0x14b362d2e38250604f21a334d71c13e2ed478467"
DEPLOY = "0x8f029510dbcc4885d5f5242f3583f4d31f9134d9eddaa30a1afa353f6bd4f7b0"
RUN = "0xe00b0998d71b0e657379be196babd1637a653c100e8162853ca6616c3970790d"
YOINK = "0xa245deda8553c6e4c575baff9b50ef35abf4c8f990f8f36897696f896f240e3a"
PLAZA = "0xe68c1d72340aeefe5be76eda63ae2f4bc7514110"
def rpc(m, p, timeout=600):
    req = urllib.request.Request(URL, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p}).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())
def send(frm, to, data, gas=30_000_000):
    tx = {"from": frm, "data": data, "gas": hex(gas), "gasPrice": "0x0"}
    if to: tx["to"] = to
    x = rpc("eth_sendTransaction", [tx])
    if "error" in x: return {"error": x["error"]["message"][:200]}
    for _ in range(300):
        rc = rpc("eth_getTransactionReceipt", [x["result"]])["result"]
        if rc: return {"status": int(rc["status"], 16), "gasUsed": int(rc["gasUsed"], 16), "hash": x["result"], "contractAddress": rc.get("contractAddress")}
        time.sleep(0.2)
def plaza_calls(f, out):
    if (f.get("to") or "").lower() == PLAZA:
        out.append({"sel": f.get("input", "")[:10], "value_eth": int(f.get("value", "0x0"), 16) / 1e18, "from": f["from"], "err": f.get("error"), "data": f.get("input", "")})
    for c in f.get("calls", []): plaza_calls(c, out)
def main():
    dep = r.rpc("eth_getTransactionByHash", [DEPLOY], key="tx_" + DEPLOY)
    run = r.rpc("eth_getTransactionByHash", [RUN], key="tx_" + RUN)
    ytr = r.rpc("debug_traceTransaction", [YOINK, {"tracer": "callTracer"}], key=f"trace_{YOINK}")
    yc = []; plaza_calls(ytr, yc)
    p = subprocess.Popen([os.path.expanduser("~/.foundry/bin/anvil"), "--port", str(PORT), "--silent", "--fork-url", "https://eth.drpc.org", "--fork-block-number", "20240538",
                          "--block-base-fee-per-gas", "0", "--no-rate-limit"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = {"fork_block": 20240538, "note": "local fork only, nothing broadcast"}
    try:
        for _ in range(60):
            try: rpc("eth_blockNumber", []); break
            except Exception: time.sleep(1)
        out["attacker_nonce_at_fork"] = int(rpc("eth_getTransactionCount", [ATK, "latest"])["result"], 16)
        rpc("anvil_setBalance", [ATK, hex(10**20)]); rpc("anvil_impersonateAccount", [ATK])
        out["deploy"] = send(ATK, None, dep["input"])
        out["plaza_balances_before"] = {"eth": int(rpc("eth_getBalance", [PLAZA, "latest"])["result"], 16) / 1e18}
        out["run"] = send(ATK, run["to"], run["input"])
        tr = rpc("debug_traceTransaction", [out["run"]["hash"], {"tracer": "callTracer"}])["result"]
        ac = []; plaza_calls(tr, ac)
        out["plaza_eth_after"] = int(rpc("eth_getBalance", [PLAZA, "latest"])["result"], 16) / 1e18
        out["attacker_calls_to_plaza"] = [{k: v for k, v in c.items() if k != "data"} for c in ac]
        out["yoink_calls_to_plaza"] = [{k: v for k, v in c.items() if k != "data"} for c in yc]
        out["same_selector_sequence"] = [c["sel"] for c in ac] == [c["sel"] for c in yc]
        out["calldata_equal_per_call"] = [a["data"] == b["data"] for a, b in zip(ac, yc)]
        out["attacker_trace_len"] = len(json.dumps(tr))
        json.dump({"attacker_full_calls": ac, "yoink_full_calls": yc}, open(ROOT / "research/defiplaza-ronin/defiplaza_plaza_calls.json", "w"), indent=1)
    finally:
        p.terminate()
    json.dump(out, open(ROOT / "research/defiplaza-ronin/defiplaza_fork_replay.json", "w"), indent=1)
    print(json.dumps(out, indent=1)[:3500])
main()
