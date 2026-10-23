#!/usr/bin/env python3
"""evolution study "Has the dark forest evolved?" -- attacker-side longitudinal measurements for every Ethereum-mainnet exploit.

Input : research/chain-scan/exploits_mainnet.json (chain scan's DeFiHackLabs extraction: attack tx hashes, block, index, from, to,
        attacker / attack-contract / victim addresses).
Output: data/evolution/{work/*.json, per_exploit.json, by_era.json}; raw responses under data/raw/ (rawfetch).

Stages (each is cached and idempotent):
  txs       fetch tx + full block for every attack tx (RPC), build work/txs.json
  traces    callTracer trace of the attack tx itself (only), eth_getCode of the attack contract, Etherscan contract
            creation (deploy tx) and verified-source lookups, build work/traces.json
  mempool   stream mempool-dumpster day files (Aug 2023+), keep only rows for our txs and a per-block control sample
            (every tx in the same block), build work/mempool.json
  analyze   per_exploit.json + by_era.json
  all       run all of the above
  senders   (evolution study v2) latest nonce of every sender of a listed tx at block 26243670 -> work/sender_nonces.json (bot-likeness signal)
  relabel   (evolution study v2) sender-class pass: sender_class.json, per_exploit_v2.json, by_era_v2.json, findings_v2.txt.  Reads only cached data
            (+ incidents/*/incident.json, w1/w7 research, the DeFiHackLabs clone); never writes the v1 outputs.

Rules: never analyse c0ffeebabe.eth's bot; txs sent by 0xc0ffeebabe... are never fetched or traced here, they
are listed as `excluded_txs` with the reason.  All fetches go through scripts/lib/rawfetch.py.

Usage: .venv/bin/python scripts/evolution.py all [--threads 4] [--limit N]
"""
import argparse, collections, concurrent.futures as cf, datetime as dt, hashlib, json, pathlib, re, statistics, sys, threading
import time, urllib.request, zlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
sys.path.insert(0, str(ROOT / "scripts"))
import rawfetch as rf  # noqa: E402
import scan_copycats as sc  # noqa: E402  (paced + retrying RPC helpers shared with chain scan; cache keys are identical)

W_6 = ROOT / "research" / "evolution"
WORK = W_6 / "work"
EXPLOITS = ROOT / "research" / "chain-scan" / "exploits_mainnet.json"
HITS = ROOT / "research" / "chain-scan" / "hits.json"
SCAN = ROOT / "research" / "chain-scan" / "scan_results.json"
C0FFEE = "0xc0ffeebabe"
MERGE_BLOCK = 15537394
LONDON_BLOCK = 12965000
DUMPSTER = "https://mempool-dumpster.flashbots.net/ethereum/mainnet"
DUMPSTER_FIRST_DAY = dt.date(2023, 8, 7)
LOCK = threading.Lock()


# --------------------------------------------------------------------------------------------- keccak (selectors only)
def keccak256(data: bytes) -> bytes:
    RC = [0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000, 0x000000000000808B,
          0x0000000080000001, 0x8000000080008081, 0x8000000000008009, 0x000000000000008A, 0x0000000000000088,
          0x0000000080008009, 0x000000008000000A, 0x000000008000808B, 0x800000000000008B, 0x8000000000008089,
          0x8000000000008003, 0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
          0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008]
    rotc = [1, 3, 6, 10, 15, 21, 28, 36, 45, 55, 2, 14, 27, 41, 56, 8, 25, 43, 62, 18, 39, 61, 20, 44]
    piln = [10, 7, 11, 17, 18, 3, 5, 16, 8, 21, 24, 4, 15, 23, 19, 13, 12, 2, 20, 14, 22, 9, 6, 1]
    M = (1 << 64) - 1
    rol = lambda x, n: ((x << n) | (x >> (64 - n))) & M
    rate = 136
    p = bytearray(data) + b"\x01"
    p += b"\x00" * ((-len(p)) % rate)
    p[-1] |= 0x80
    st = [0] * 25
    for off in range(0, len(p), rate):
        for i in range(rate // 8):
            st[i] ^= int.from_bytes(p[off + 8 * i: off + 8 * i + 8], "little")
        for rnd in range(24):
            bc = [st[i] ^ st[i + 5] ^ st[i + 10] ^ st[i + 15] ^ st[i + 20] for i in range(5)]
            for i in range(5):
                t = bc[(i + 4) % 5] ^ rol(bc[(i + 1) % 5], 1)
                for j in range(0, 25, 5):
                    st[j + i] ^= t
            t = st[1]
            for i in range(24):
                j = piln[i]
                b0 = st[j]
                st[j] = rol(t, rotc[i])
                t = b0
            for j in range(0, 25, 5):
                bc = st[j:j + 5]
                for i in range(5):
                    st[j + i] ^= (~bc[(i + 1) % 5]) & bc[(i + 2) % 5] & M
            st[0] ^= RC[rnd]
    return b"".join(x.to_bytes(8, "little") for x in st[:4])


def selector(sig):
    return "0x" + keccak256(sig.encode()).hex()[:8]


assert keccak256(b"").hex() == "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"
assert selector("transfer(address,uint256)") == "0xa9059cbb"

# flash-loan entry points (call made to the lender) and callbacks (call made by the lender back into the attacker)
FL_ENTRY = {selector(s): p for s, p in {
    "flashLoan(address,address[],uint256[],uint256[],address,bytes,uint16)": "aave",
    "flashLoanSimple(address,address,uint256,bytes,uint16)": "aave-v3",
    "flashLoan(address,address[],uint256[],bytes)": "balancer",
    "flashLoan(address,address,uint256,bytes)": "erc3156 (maker/others)",
    "flashLoan(address,uint256,bytes)": "morpho",
    "flash(address,uint256,uint256,bytes)": "uniswap-v3-flash",
    "flashLoan(uint256,uint256,address,bytes)": "dodo",
    "flashLoan(address[],uint256[],bytes)": "generic",
}.items()}
FL_CALLBACK = {selector(s): p for s, p in {
    "uniswapV2Call(address,uint256,uint256,bytes)": "uniswap-v2-flashswap",
    "uniswapV3FlashCallback(uint256,uint256,bytes)": "uniswap-v3-flash",
    "receiveFlashLoan(address[],uint256[],uint256[],bytes)": "balancer",
    "executeOperation(address[],uint256[],uint256[],address,bytes)": "aave",
    "executeOperation(address,uint256,uint256,bytes)": "aave-v1",
    "executeOperation(address,address,uint256,uint256,address,bytes)": "aave-v3",
    "onFlashLoan(address,address,uint256,uint256,bytes)": "erc3156 (maker/others)",
    "onMorphoFlashLoan(uint256,bytes)": "morpho",
    "callFunction(address,(address,uint256),bytes)": "dydx",
    "DPPFlashLoanCall(address,uint256,uint256,bytes)": "dodo",
    "DVMFlashLoanCall(address,uint256,uint256,bytes)": "dodo",
    "DSPFlashLoanCall(address,uint256,uint256,bytes)": "dodo",
}.items()}


# --------------------------------------------------------------------------------------------- small helpers
def h2i(x):
    return int(x, 16) if isinstance(x, str) and x else (x or 0)


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def jdump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1, sort_keys=False))
    tmp.replace(path)


def jload(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def rel(key_source, key, ext="json"):
    p = rf.RAW / rf._safe(key_source) / f"{rf._safe(key)}.{ext}"
    return str(p.relative_to(rf.ROOT)) if p.exists() else None


def era_of(block, ts):
    y = dt.datetime.fromtimestamp(ts, dt.UTC).year
    if y < 2021:
        return "E1 pre-2021 (public mempool)"
    if block < MERGE_BLOCK:
        return "E2 2021-Sep2022 (MEV-geth bundles)"
    if y < 2024:
        return "E3 Sep2022-2023 (early PBS)"
    return "E4 2024-2026 (mature PBS / private flow)"


def disasm_flags(code_hex, attackers):
    """Opcode-aware scan of runtime bytecode (PUSH data skipped)."""
    b = bytes.fromhex(code_hex[2:]) if code_hex and code_hex != "0x" else b""
    # strip solidity/vyper CBOR metadata tail if the length suffix is plausible
    body = b
    if len(b) > 2:
        n = int.from_bytes(b[-2:], "big")
        if 20 < n < 120 and len(b) > n + 2 and b[-n - 2:-n - 1] in (b"\xa1", b"\xa2", b"\xa3", b"\xa4", b"\xa5"):
            body = b[:-n - 2]
    ops, push20, i = [], set(), 0
    while i < len(body):
        o = body[i]
        ops.append((i, o))
        if 0x60 <= o <= 0x7F:
            n = o - 0x5F
            if o == 0x73:
                push20.add("0x" + body[i + 1:i + 21].hex())
            i += n
        i += 1
    seq = [o for _, o in ops]
    origin = seq.count(0x32)
    caller = seq.count(0x33)
    # CALLER ... EQ within 24 opcodes (typical `require(msg.sender == X)` or `onlyOwner`), and ORIGIN ... EQ likewise
    def near(opc, win=24):
        c = 0
        for k, o in enumerate(seq):
            if o == opc and 0x14 in seq[k + 1:k + win]:
                c += 1
        return c
    atk = {a.lower() for a in attackers if a}
    return {"code_size": len(b), "origin_ops": origin, "origin_eq_ops": near(0x32), "caller_ops": caller,
            "caller_eq_ops": near(0x33), "selfdestruct_op": seq.count(0xFF), "create_ops": seq.count(0xF0) + seq.count(0xF5),
            "delegatecall_ops": seq.count(0xF4), "callvalue_ops": seq.count(0x34),
            "solc_metadata": len(body) != len(b), "hardcoded_attacker_addr": sorted(push20 & atk),
            "n_push20_consts": len(push20)}


# --------------------------------------------------------------------------------------------- stage: txs
def load_exploits():
    d = json.load(open(EXPLOITS))
    out = []
    for e in d["exploits"]:
        txi = [t for t in e.get("tx_info", []) if t.get("on_mainnet")]
        keep, excl = [], []
        for t in txi:
            if (t.get("from") or "").lower().startswith(C0FFEE):
                excl.append({"hash": t["hash"], "reason": "sent by c0ffeebabe.eth (publication policy: not analysed)"})
            else:
                keep.append(t)
        keep.sort(key=lambda t: (t["block"], t["index"]))
        e = dict(e)
        e["_keep"] = keep
        e["_excl"] = excl
        out.append(e)
    return out


def stage_txs(exploits, threads, limit=None):
    out = jload(WORK / "txs.json", {})
    todo = []
    for e in exploits:
        for t in e["_keep"]:
            if t["hash"] not in out:
                todo.append(t)
    if limit:
        todo = todo[:limit]
    blocks_done = {}

    def one(t):
        h = t["hash"]
        tx = sc.get_tx(h)
        if not tx or not tx.get("blockNumber"):
            return h, {"error": "tx not found"}
        n = h2i(tx["blockNumber"])
        with LOCK:
            blk = blocks_done.get(n)
        if blk is None:
            blk = sc.get_block(n)
            with LOCK:
                blocks_done[n] = blk
        txs = blk["transactions"]
        base = h2i(blk.get("baseFeePerGas")) if blk.get("baseFeePerGas") else None
        tips = sorted(max(0, h2i(x["gasPrice"]) - (base or 0)) for x in txs)
        gp = h2i(tx["gasPrice"])
        mine = next(x for x in txs if x["hash"].lower() == h.lower())
        eff = h2i(mine["gasPrice"])
        rec = {
            "hash": h.lower(), "block": n, "index": h2i(tx["transactionIndex"]), "from": tx["from"].lower(),
            "to": (tx["to"] or "").lower() or None, "nonce": h2i(tx["nonce"]), "type": h2i(tx.get("type")),
            "input_len": (len(tx["input"]) - 2) // 2, "input_sel": tx["input"][:10] if len(tx["input"]) >= 10 else None,
            "value_wei": h2i(tx["value"]), "gas_limit": h2i(tx["gas"]), "effective_gas_price_wei": eff,
            "max_fee_wei": h2i(tx.get("maxFeePerGas")) if tx.get("maxFeePerGas") else None,
            "max_priority_wei": h2i(tx.get("maxPriorityFeePerGas")) if tx.get("maxPriorityFeePerGas") else None,
            "base_fee_wei": base, "tip_wei": max(0, eff - (base or 0)),
            "block_ts": h2i(blk["timestamp"]), "miner": blk["miner"].lower(), "block_extra": blk.get("extraData"),
            "block_tx_count": len(txs), "block_hashes": [x["hash"].lower() for x in txs],
            "block_median_tip_wei": int(statistics.median(tips)) if tips else 0,
            "tip_rank_in_block": sum(1 for x in tips if x < max(0, eff - (base or 0))) / max(1, len(tips)),
            "raw_refs": {"tx": rel("rpc", f"eth_getTransactionByHash_{h}"),
                         "block": rel("rpc", f"eth_getBlockByNumber_full_{n}")},
        }
        return h, rec

    n = 0
    with cf.ThreadPoolExecutor(threads) as ex:
        for fut in cf.as_completed([ex.submit(one, t) for t in todo]):
            try:
                h, rec = fut.result()
            except Exception as ex_:  # noqa: BLE001
                print("tx error", repr(ex_)[:150], file=sys.stderr)
                continue
            out[h] = rec
            n += 1
            if n % 25 == 0:
                print(f"  txs {n}/{len(todo)}", file=sys.stderr)
                jdump(WORK / "txs.json", out)
    jdump(WORK / "txs.json", out)
    return out


# --------------------------------------------------------------------------------------------- stage: traces
def walk_nodes(t, depth=0, parent=None, dead=False):
    dead = dead or bool(t.get("error"))
    yield t, depth, parent, dead
    for c in t.get("calls") or []:
        yield from walk_nodes(c, depth + 1, t, dead)


def subtree_count(t):
    return 1 + sum(subtree_count(c) for c in t.get("calls") or [])


def trace_features(trace, txrec, ex):
    victims = {v.lower() for v in ex.get("victims", [])}
    miner = txrec["miner"]
    root_create = trace.get("type") in ("CREATE", "CREATE2")
    nodes = list(walk_nodes(trace))
    calls = [n for n in nodes[1:] if n[0].get("type") in ("CALL", "STATICCALL", "DELEGATECALL", "CALLCODE")]
    creates = [n for n in nodes[1:] if n[0].get("type") in ("CREATE", "CREATE2")]
    fl, fl_cb = set(), set()
    bribe = 0
    victim_called = False
    for node, depth, parent, dead in nodes[1:]:
        to = (node.get("to") or "").lower()
        inp = node.get("input") or ""
        sel = inp[:10]
        if sel in FL_ENTRY and node.get("type") == "CALL":
            fl.add(FL_ENTRY[sel])
        if sel in FL_CALLBACK:
            fl_cb.add(FL_CALLBACK[sel])
        if to == miner and not dead and node.get("type") == "CALL":
            bribe += h2i(node.get("value"))
        if to in victims and node.get("type") in ("CALL", "DELEGATECALL", "STATICCALL"):
            victim_called = True
    # constructor exploit: root tx IS a CREATE and its init code makes calls (to a victim, or >= 3 calls)
    root_calls = len(calls)
    constructor_attack = bool(root_create and (victim_called or root_calls >= 3))
    # deploy-and-attack via an internal CREATE (factory / executor): created contract's own subtree makes calls
    internal_create_attack = False
    internal_create_calls = 0
    for node, depth, parent, dead in creates:
        if dead:
            continue
        sub = subtree_count(node) - 1
        if sub >= 3 or any((c.get("to") or "").lower() in victims for c, *_ in walk_nodes(node)):
            internal_create_attack = True
            internal_create_calls = max(internal_create_calls, sub)
    first_ext = None
    for node, depth, parent, dead in nodes[1:]:
        if node.get("type") == "CALL" and (node.get("to") or "").lower() not in (txrec["from"],):
            first_ext = (node.get("to") or "").lower()
            break
    return {
        "root_type": trace.get("type"), "root_error": trace.get("error"), "gas_used": h2i(trace.get("gasUsed")),
        "n_calls": root_calls, "n_creates_inside": len(creates), "max_depth": max(d for _, d, _, _ in nodes),
        "selfdestruct_nodes": sum(1 for n in nodes if n[0].get("type") == "SELFDESTRUCT"),
        "constructor_attack": constructor_attack, "internal_create_attack": internal_create_attack,
        "internal_create_calls": internal_create_calls, "victim_called": victim_called,
        "flashloan_entry": sorted(fl), "flashloan_callback": sorted(fl_cb), "flashloan": sorted(fl | fl_cb),
        "coinbase_bribe_wei": bribe, "trace_created_addr": (trace.get("to") or "").lower() if root_create else None,
        "root_value_wei": h2i(trace.get("value")),
    }


def eth_get_code(addr, block):
    key = f"eth_getCode_{addr}_{block}"
    return sc.call("eth_getCode", [addr, hex(block)], key=key)


SRC_FLAGS = {
    "tx_origin": r"tx\.origin",
    "msg_sender_eq": r"msg\.sender\s*(==|!=)",
    "only_owner": r"onlyOwner|require\s*\(\s*(msg\.sender|_msgSender\(\))\s*==\s*(owner|admin|_owner)",
    "block_number_or_ts_check": r"block\.(number|timestamp)\s*(>|<|==|>=|<=)",
}


def etherscan_safe(params, key):
    for i in range(4):
        try:
            r = rf.etherscan(params, key=key)
            if isinstance(r, dict) and isinstance(r.get("result"), str) and "rate limit" in r["result"].lower():
                time.sleep(2 * (i + 1))
                rf.etherscan(params, key=key, refresh=True)
                continue
            return r
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (i + 1))
    return {"status": "0", "message": "fetch failed", "result": repr(last)[:200]}


def creation_lookup(addrs):
    """Etherscan v2 getcontractcreation in batches of 5 -> {addr: {creator, txHash, blockNumber, timestamp, factory}}"""
    res = {}
    addrs = sorted({a.lower() for a in addrs if a})
    for i in range(0, len(addrs), 5):
        batch = addrs[i:i + 5]
        key = "creation_" + hashlib.sha1(",".join(batch).encode()).hexdigest()[:16]
        time.sleep(0.25)
        r = etherscan_safe({"module": "contract", "action": "getcontractcreation", "contractaddresses": ",".join(batch)}, key)
        if isinstance(r.get("result"), list):
            for x in r["result"]:
                res[x["contractAddress"].lower()] = {**{k: x.get(k) for k in ("contractCreator", "txHash", "blockNumber", "timestamp", "contractFactory")},
                                                     "raw_ref": rel("etherscan", key)}
        for a in batch:
            res.setdefault(a, {"raw_ref": rel("etherscan", key), "missing": True})
    return res


def source_lookup(addr):
    key = f"source_{addr}"
    time.sleep(0.25)
    r = etherscan_safe({"module": "contract", "action": "getsourcecode", "address": addr}, key)
    out = {"raw_ref": rel("etherscan", key), "verified": False}
    try:
        x = r["result"][0]
        src = x.get("SourceCode") or ""
        out["verified"] = bool(src)
        out["contract_name"] = x.get("ContractName")
        out["compiler"] = x.get("CompilerVersion")
        out["is_proxy"] = x.get("Proxy") == "1"
        out["source_flags"] = {k: bool(re.search(p, src)) for k, p in SRC_FLAGS.items()} if src else None
        out["source_len"] = len(src)
    except Exception as e:  # noqa: BLE001
        out["error"] = repr(e)[:120]
    return out


def stage_traces(exploits, txs, threads, limit=None):
    out = jload(WORK / "traces.json", {})
    todo = [(e, t) for e in exploits for t in e["_keep"] if t["hash"].lower() in txs and "error" not in txs[t["hash"].lower()]
            and t["hash"].lower() not in out]
    if limit:
        todo = todo[:limit]

    def one(args):
        e, t = args
        h = t["hash"].lower()
        rec = txs[h]
        trace = sc.get_trace(h)
        feat = trace_features(trace, rec, e)
        feat["raw_ref_trace"] = rel("rpc", f"debug_traceTransaction_callTracer_{h}")
        # attacker-side contract that received the tx: created address (constructor) or tx.to
        feat["target"] = feat["trace_created_addr"] or rec["to"]
        return h, feat

    n = 0
    with cf.ThreadPoolExecutor(threads) as ex:
        for fut in cf.as_completed([ex.submit(one, a) for a in todo]):
            try:
                h, feat = fut.result()
            except Exception as e_:  # noqa: BLE001
                print("trace error", repr(e_)[:160], file=sys.stderr)
                continue
            out[h] = feat
            n += 1
            if n % 25 == 0:
                print(f"  traces {n}/{len(todo)}", file=sys.stderr)
                jdump(WORK / "traces.json", out)
    jdump(WORK / "traces.json", out)

    # ---- contract-level facts: creation tx, bytecode, verified source (once per distinct target)
    ct = jload(WORK / "contracts.json", {})
    targets = {}
    for e in exploits:
        for t in e["_keep"]:
            h = t["hash"].lower()
            if h in out and out[h]["target"]:
                targets[out[h]["target"]] = (h, e)
    need = [a for a in targets if a not in ct]
    if limit:
        need = need[:limit]
    cre = creation_lookup(need)
    print(f"  contracts: {len(need)} new", file=sys.stderr)

    def contract(a):
        h, e = targets[a]
        rec = txs[h]
        atk = set(x.lower() for x in e.get("attacker", [])) | {rec["from"]}
        code = eth_get_code(a, rec["block"])
        d = {"address": a, "has_code_at_attack_block": code not in (None, "0x"),
             "code_hash": hashlib.sha256((code or "").encode()).hexdigest()[:16],
             "code_ref": rel("rpc", f"eth_getCode_{a}_{rec['block']}")}
        d.update(disasm_flags(code, atk))
        d["creation"] = cre.get(a)
        if d["has_code_at_attack_block"]:
            d["source"] = source_lookup(a)
        else:
            d["source"] = None
        return a, d

    n = 0
    with cf.ThreadPoolExecutor(min(threads, 3)) as ex:
        for fut in cf.as_completed([ex.submit(contract, a) for a in need]):
            try:
                a, d = fut.result()
            except Exception as e_:  # noqa: BLE001
                print("contract error", repr(e_)[:160], file=sys.stderr)
                continue
            ct[a] = d
            n += 1
            if n % 25 == 0:
                print(f"  contracts {n}/{len(need)}", file=sys.stderr)
                jdump(WORK / "contracts.json", ct)
    jdump(WORK / "contracts.json", ct)

    # ---- deploy tx block/timestamp (creation tx may live in a different block than the attack)
    dep = jload(WORK / "deploy_txs.json", {})
    want = {}
    for a, d in ct.items():
        c = d.get("creation") or {}
        if c.get("txHash") and c["txHash"].lower() not in dep:
            want[c["txHash"].lower()] = a

    def depfetch(h):
        tx = sc.get_tx(h)
        if not tx or not tx.get("blockNumber"):
            return h, {"error": "not found"}
        n_ = h2i(tx["blockNumber"])
        blk = sc.call("eth_getBlockByNumber", [hex(n_), False], key=f"eth_getBlockByNumber_hdr_{n_}")
        return h, {"block": n_, "ts": h2i(blk["timestamp"]), "from": tx["from"].lower(), "to": (tx["to"] or "").lower() or None,
                   "index": h2i(tx["transactionIndex"]), "raw_refs": {"tx": rel("rpc", f"eth_getTransactionByHash_{h}"),
                                                                        "block_hdr": rel("rpc", f"eth_getBlockByNumber_hdr_{n_}")}}

    with cf.ThreadPoolExecutor(threads) as ex:
        for fut in cf.as_completed([ex.submit(depfetch, h) for h in want]):
            try:
                h, d = fut.result()
                dep[h] = d
            except Exception as e_:  # noqa: BLE001
                print("deploy error", repr(e_)[:160], file=sys.stderr)
    jdump(WORK / "deploy_txs.json", dep)
    return out, ct, dep


# --------------------------------------------------------------------------------------------- stage: mempool
def stream_day(date, hashes, control_by_block):
    """Stream the dumpster day CSV; return rows for `hashes` (full parsed row) and first-seen for the control hashes.
    Keeps nothing but the matched rows on disk (the full file is ~100 MB zipped / 300 MB CSV); the sha256 + size of the
    complete stream are written to MANIFEST so the extract can be tied to the exact upstream bytes."""
    url = f"{DUMPSTER}/{date[:7]}/{date}.csv.zip"
    ctrl = {h for hs in control_by_block.values() for h in hs}
    want = set(hashes)
    rows, ctrl_seen = {}, {}
    sha = hashlib.sha256()
    total = 0
    req = urllib.request.Request(url, headers=rf.UA)
    d = None
    buf = b""
    hdr_done = False
    rem = b""
    nlines = 0
    with urllib.request.urlopen(req, timeout=180) as r:
        status = r.status
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            sha.update(chunk)
            total += len(chunk)
            if not hdr_done:
                buf += chunk
                if len(buf) < 30:
                    continue
                nlen, elen = int.from_bytes(buf[26:28], "little"), int.from_bytes(buf[28:30], "little")
                if len(buf) < 30 + nlen + elen:
                    continue
                assert buf[:4] == b"PK\x03\x04" and int.from_bytes(buf[8:10], "little") == 8, "unexpected zip layout"
                d = zlib.decompressobj(-zlib.MAX_WBITS)
                chunk = buf[30 + nlen + elen:]
                hdr_done = True
            if d.eof:
                continue
            data = rem + d.decompress(chunk)
            lines = data.split(b"\n")
            rem = lines.pop()
            for ln in lines:
                nlines += 1
                if ln[:9] == b"timestamp":
                    continue
                f = ln.split(b",", 2)
                if len(f) < 3:
                    continue
                hh = f[1].decode()
                if hh in want:
                    rows[hh] = ln.decode()
                elif hh in ctrl:
                    ctrl_seen[hh] = int(f[0])
    rec = {"path": None, "sha256": sha.hexdigest(), "bytes": total, "url": url, "method": "GET", "status": status,
           "retrieved_at": now(), "note": "streamed; only matching rows kept (see data/raw/mempool-dumpster/extract_<date>.json)"}
    with LOCK, open(rf.MANIFEST, "a") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rows, ctrl_seen, {"url": url, "sha256_of_zip": sha.hexdigest(), "zip_bytes": total, "csv_lines": nlines}


HDR = ["timestamp_ms", "hash", "chain_id", "from", "to", "value", "nonce", "gas", "gas_price", "gas_tip_cap", "gas_fee_cap",
       "data_size", "data_4bytes", "sources", "included_at_block_height", "included_block_timestamp_ms", "inclusion_delay_ms",
       "tx_type"]


def stage_mempool(exploits, txs, threads, limit=None):
    out = jload(WORK / "mempool.json", {"days": {}, "tx": {}, "blocks": {}})
    by_day = collections.defaultdict(lambda: {"hashes": set(), "blocks": {}})
    for e in exploits:
        for t in e["_keep"]:
            h = t["hash"].lower()
            r = txs.get(h)
            if not r or "error" in r:
                continue
            d = dt.datetime.fromtimestamp(r["block_ts"], dt.UTC).date()
            if d < DUMPSTER_FIRST_DAY:
                continue
            days = [d]
            # a tx that sat in the pool across midnight would be first-seen in the previous day's file
            if r["block_ts"] % 86400 < 600 and d - dt.timedelta(days=1) >= DUMPSTER_FIRST_DAY:
                days.append(d - dt.timedelta(days=1))
            for dd in days:
                by_day[str(dd)]["hashes"].add(h)
                if dd == d:
                    by_day[str(dd)]["blocks"][r["block"]] = [x for x in r["block_hashes"] if x != h]
    todo = [d for d in sorted(by_day) if d not in out["days"]]
    if limit:
        todo = todo[:limit]
    print(f"  mempool: {len(todo)} days to stream ({len(by_day)} total)", file=sys.stderr)

    def one(d):
        for attempt in range(3):
            try:
                rows, ctrl, meta = stream_day(d, by_day[d]["hashes"], by_day[d]["blocks"])
                break
            except Exception as e_:  # noqa: BLE001
                err = repr(e_)[:200]
                time.sleep(5 * (attempt + 1))
        else:
            return d, {"error": err}
        rows_p = {h: dict(zip(HDR, ln.split(","))) for h, ln in rows.items()}
        extract = {"date": d, "source": meta, "header": HDR, "rows": rows, "control_first_seen_ms": ctrl,
                   "control_blocks": {str(b): len(hs) for b, hs in by_day[d]["blocks"].items()}}
        ep = rf.RAW / "mempool-dumpster" / f"extract_{d}.json"
        ep.write_text(json.dumps(extract))
        meta["extract"] = str(ep.relative_to(rf.ROOT))
        return d, {"meta": meta, "rows": rows_p, "ctrl": ctrl}

    n = 0
    with cf.ThreadPoolExecutor(threads) as ex:
        futs = {ex.submit(one, d): d for d in todo}
        for fut in cf.as_completed(futs):
            d, res = fut.result()
            out["days"][d] = res.get("meta") or {"error": res.get("error")}
            if "rows" in res:
                for h, row in res["rows"].items():
                    prev = out["tx"].get(h)
                    if not prev or int(row["timestamp_ms"]) < int(prev["timestamp_ms"]):
                        out["tx"][h] = {**row, "day_file": d, "extract": res["meta"]["extract"]}
                for b, hs in by_day[d]["blocks"].items():
                    seen = sum(1 for h in hs if h in res["ctrl"])
                    out["blocks"][str(b)] = {"others_in_block": len(hs), "others_seen_public": seen, "day_file": d}
            n += 1
            print(f"  mempool {n}/{len(todo)} {d} {'ERR ' + out['days'][d].get('error', '') if 'error' in out['days'][d] else ''}",
                  file=sys.stderr)
            jdump(WORK / "mempool.json", out)
    jdump(WORK / "mempool.json", out)
    return out


# --------------------------------------------------------------------------------------------- stage: analyze
def classify_exposure(rec, feat, mp):
    """Return (label, confidence, evidence[]) for one attack tx."""
    ts = rec["block_ts"]
    day = dt.datetime.fromtimestamp(ts, dt.UTC).date()
    ev = []
    tip_gwei = rec["tip_wei"] / 1e9
    bribe = feat["coinbase_bribe_wei"] if feat else 0
    if day >= DUMPSTER_FIRST_DAY:
        dayrec = mp["days"].get(str(day))
        if not dayrec or "error" in dayrec:
            return "unknown", "none", ["mempool-dumpster day file unavailable/failed"], {}
        m = mp["tx"].get(rec["hash"])
        blk = mp["blocks"].get(str(rec["block"]), {})
        if m:
            first = int(m["timestamp_ms"])
            lead_ms = ts * 1000 - first
            srcs = m["sources"].split()
            dd = {"first_seen_ms": first, "lead_before_block_ts_ms": lead_ms, "sources": srcs, "n_sources": len(srcs),
                  "inclusion_delay_ms": int(m["inclusion_delay_ms"]) if m.get("inclusion_delay_ms") else None,
                  "extract": m["extract"], "day_file": m["day_file"]}
            if lead_ms > 0:
                excl = len(srcs) == 1
                ev.append(f"seen in public mempool {lead_ms/1000:.1f}s before block timestamp by {', '.join(srcs)}")
                if excl:
                    ev.append("exclusive to one source (could be semi-private order flow, e.g. bloXroute/Eden)")
                if not srcs:
                    ev.append("dumpster row has an empty sources field (source attribution missing)")
                return "public", ("low" if not srcs else "medium" if excl else "high"), ev, dd
            ev.append(f"first seen {-lead_ms/1000:.1f}s AFTER block timestamp (cannot have been actionable before inclusion)")
            return "private-bundle", "medium", ev, dd
        ev.append("absent from mempool-dumpster day file (never seen by any source before inclusion)")
        if blk:
            ev.append(f"control: {blk['others_seen_public']}/{blk['others_in_block']} other txs in the same block were seen")
        if bribe:
            ev.append(f"attacker paid {bribe/1e18:.4f} ETH to block.coinbase")
        return "private-bundle", "high" if blk and blk["others_in_block"] and blk["others_seen_public"] / blk["others_in_block"] > 0.5 else "medium", ev, {}
    # ---- no public-mempool archive before 2023-08-07: heuristics from the tx itself
    h = heuristic_signals(rec, feat)
    if h["strong"]:
        return "private-bundle", "heuristic-strong", h["strong"] + h["weak"], {}
    if len(h["weak"]) >= 2:
        return "private-bundle", "heuristic-weak", h["weak"], {}
    if rec["block"] < 11_400_000:  # before Flashbots Auction had any share (alpha: Nov-Dec 2020, mainnet bundles from ~Jan 2021)
        return "public", "era-prior", ["pre-Flashbots: only direct miner deals existed; no private-bundle signals"], {}
    ev = ["no public-mempool archive before 2023-08-07; no private-bundle signal found (tip " +
          f"{tip_gwei:.2f} gwei, rank {rec['tip_rank_in_block']:.2f}, index {rec['index']})"] + h["weak"]
    return "unknown", "no-signal", ev, {}


def heuristic_signals(rec, feat):
    """Private-bundle signals visible in the block itself.  Calibrated against mempool-dumpster ground truth in
    data/evolution/calibration.json: strong signals have precision 0.8-1.0 but recall of only ~10% on ordinary txs,
    so 'no signal' must never be read as 'public'."""
    pre_london = rec["block"] < LONDON_BLOCK
    bribe = feat["coinbase_bribe_wei"] if feat else 0
    tip_gwei = rec["tip_wei"] / 1e9
    strong, weak = [], []
    if pre_london and rec["effective_gas_price_wei"] == 0:
        strong.append("gas price 0 (Flashbots-bundle signature)")
    if (not pre_london) and rec["tip_wei"] == 0:
        strong.append("priority fee 0 with tx included (bundle/builder-direct signature)")
    if bribe > 0 and rec["tip_wei"] <= rec["block_median_tip_wei"]:
        strong.append(f"direct coinbase payment of {bribe/1e18:.4f} ETH with gas tip <= block median ({tip_gwei:.2f} gwei)")
    elif bribe > 0:
        weak.append(f"coinbase payment {bribe/1e18:.4f} ETH")
    lhf = rec.get("later_higher_frac")
    if lhf is not None and lhf >= 0.9 and rec["index"] / max(1, rec["block_tx_count"]) < 0.5:
        strong.append(f"out-of-order: {lhf:.0%} of later txs in the block pay a higher tip yet this tx sits at index {rec['index']}")
    if rec["index"] == 0:
        weak.append("tx index 0 (top of block)")
    elif rec["index"] <= 2:
        weak.append(f"tx index {rec['index']} (near top of block)")
    if rec["tip_rank_in_block"] <= 0.25 and rec["index"] < 5:
        weak.append("low tip yet near top of block")
    return {"strong": strong, "weak": weak, "flagged": bool(strong) or len(weak) >= 2}


def add_later_higher(txs):
    """later_higher_frac = share of txs AFTER this one in its block that pay a strictly higher tip (price-sorted blocks ~0)."""
    for h, r in txs.items():
        if "error" in r or "later_higher_frac" in r:
            continue
        blk = sc.get_block(r["block"])
        base = h2i(blk.get("baseFeePerGas")) if blk.get("baseFeePerGas") else 0
        tips = [max(0, h2i(t["gasPrice"]) - base) for t in blk["transactions"]]
        i = r["index"]
        later = tips[i + 1:]
        r["later_higher_frac"] = (sum(1 for x in later if x > tips[i]) / len(later)) if later else 0.0


def build_rows(exploits, txs, traces, contracts, deploys, mp, hits):
    rows = []
    for e in exploits:
        keep = [t for t in e["_keep"] if t["hash"].lower() in txs and "error" not in txs[t["hash"].lower()]]
        row = {"id": e["file"], "name": e["name"], "date": e["date"], "chain": "mainnet",
               "attackers_listed": e.get("attacker", []), "attack_contracts_listed": e.get("attack_contract", []),
               "victims_listed": e.get("victims", []), "excluded_txs": e["_excl"]}
        if not keep:
            row.update({"status": "no-mainnet-tx", "note": "DeFiHackLabs entry has no resolvable mainnet attack tx"})
            rows.append(row)
            continue
        # primary tx: earliest tx that is not a pure deploy (a CREATE tx with no inner calls)
        def is_pure_deploy(t):
            f = traces.get(t["hash"].lower())
            return bool(f and f["root_type"] in ("CREATE", "CREATE2") and not f["constructor_attack"])
        cands = [t for t in keep if not is_pure_deploy(t)]
        prim = (cands or keep)[0]
        h = prim["hash"].lower()
        rec, feat = txs[h], traces.get(h)
        row["status"] = "ok" if feat else "no-trace"
        row.update({"primary_tx": h, "block": rec["block"], "tx_index": rec["index"], "block_ts": rec["block_ts"],
                    "block_time_utc": dt.datetime.fromtimestamp(rec["block_ts"], dt.UTC).isoformat(),
                    "year": dt.datetime.fromtimestamp(rec["block_ts"], dt.UTC).year,
                    "era": era_of(rec["block"], rec["block_ts"]), "attacker_eoa": rec["from"]})
        # ---- exposure
        lab, conf, ev, dd = classify_exposure(rec, feat, mp)
        row["exposure"] = {"label": lab, "confidence": conf, "evidence": ev, "dumpster": dd or None,
                           "method": "mempool-dumpster" if rec["block_ts"] >= 1691366400 else "heuristic (no archive)"}
        day = str(dt.datetime.fromtimestamp(rec["block_ts"], dt.UTC).date())
        blk = mp["blocks"].get(str(rec["block"]))
        row["exposure"]["block_control"] = blk
        row["exposure"]["heuristic"] = heuristic_signals(rec, feat)
        # ---- techniques
        t = {}
        if feat:
            t.update({"constructor_exploit": feat["constructor_attack"], "internal_create_exploit": feat["internal_create_attack"],
                      "tx_to_null": rec["to"] is None, "n_calls": feat["n_calls"], "flashloan": feat["flashloan"],
                      "uses_flashloan": bool(feat["flashloan"]), "selfdestruct_in_tx": feat["selfdestruct_nodes"] > 0,
                      "coinbase_bribe_wei": feat["coinbase_bribe_wei"], "coinbase_bribe_eth": feat["coinbase_bribe_wei"] / 1e18,
                      "tx_reverted": bool(feat["root_error"])})
        t.update({"gas_price_gwei": rec["effective_gas_price_wei"] / 1e9, "tip_gwei": rec["tip_wei"] / 1e9,
                  "block_median_tip_gwei": rec["block_median_tip_wei"] / 1e9, "tip_rank_in_block": rec["tip_rank_in_block"],
                  "base_fee_gwei": (rec["base_fee_wei"] or 0) / 1e9, "tx_type": rec["type"]})
        # attack contract facts
        tgt = feat["target"] if feat else rec["to"]
        c = contracts.get(tgt) if tgt else None
        atk_set = {a.lower() for a in e.get("attacker", [])} | {rec["from"]}
        role = None
        if feat and feat["root_type"] in ("CREATE", "CREATE2"):
            role = "created-in-this-tx"
        elif not c or not c["has_code_at_attack_block"]:
            role = "eoa-or-no-code"
        else:
            cre = (c.get("creation") or {})
            dtx = deploys.get((cre.get("txHash") or "").lower())
            owned = (dtx and dtx.get("from") in atk_set) or (cre.get("contractCreator") or "").lower() in atk_set or tgt in {x.lower() for x in e.get("attack_contract", [])}
            vic = {v.lower() for v in e.get("victims", [])}
            role = "attacker-contract" if owned else ("victim-called-directly" if tgt in vic else "third-party-contract")
        t["target"] = tgt
        t["target_role"] = role
        if c:
            cre = c.get("creation") or {}
            dtx = deploys.get((cre.get("txHash") or "").lower())
            if dtx and "error" not in dtx:
                t["deploy_tx"] = cre["txHash"].lower()
                t["deploy_block"] = dtx["block"]
                t["deploy_same_tx"] = cre["txHash"].lower() == h
                t["deploy_gap_blocks"] = rec["block"] - dtx["block"]
                t["deploy_gap_s"] = rec["block_ts"] - dtx["ts"]
                t["deploy_fresh_le_7d"] = t["deploy_gap_s"] <= 7 * 86400
                t["deployer_eq_attacker"] = dtx["from"] in atk_set
            t["bytecode"] = {k: c.get(k) for k in ("code_size", "origin_ops", "origin_eq_ops", "caller_ops", "caller_eq_ops",
                                                    "selfdestruct_op", "solc_metadata", "hardcoded_attacker_addr", "n_push20_consts",
                                                    "has_code_at_attack_block", "code_ref")}
            s = c.get("source")
            t["verified_source"] = bool(s and s.get("verified"))
            t["source_flags"] = s.get("source_flags") if s else None
            t["origin_check"] = bool(c.get("origin_eq_ops")) or bool(s and s.get("source_flags") and s["source_flags"].get("tx_origin"))
            t["hardcoded_attacker_addr"] = bool(c.get("hardcoded_attacker_addr"))
            t["sender_guard"] = bool(t["origin_check"] or t["hardcoded_attacker_addr"] or
                                     (s and s.get("source_flags") and (s["source_flags"].get("only_owner") or s["source_flags"].get("msg_sender_eq"))))
            t["caller_eq_weak"] = bool(c.get("caller_eq_ops"))
        # ---- multi-tx
        att_txs = [x["hash"].lower() for x in keep]
        t["n_attack_txs_listed"] = len(att_txs)
        t["attack_txs"] = att_txs
        t["multi_tx"] = len(att_txs) >= 3
        if len(att_txs) > 1:
            t["span_blocks"] = txs[att_txs[-1]]["block"] - txs[att_txs[0]]["block"]
        row["techniques"] = t
        # ---- per-tx exposure for every listed tx (compact)
        row["all_txs"] = []
        for x in keep:
            hh = x["hash"].lower()
            r2, f2 = txs[hh], traces.get(hh)
            lab2, conf2, ev2, _ = classify_exposure(r2, f2, mp)
            row["all_txs"].append({"hash": hh, "block": r2["block"], "index": r2["index"], "exposure": lab2, "confidence": conf2,
                                   "constructor": bool(f2 and f2["constructor_attack"]), "bribe_eth": (f2["coinbase_bribe_wei"] / 1e18) if f2 else None})
        # ---- outcome
        row["outcome"] = hits.get(e["file"], {"frontrun_candidate": "pending (chain scan not finished)" if not hits else "unscannable"})
        # ---- raw refs
        row["raw_refs"] = {"tx": rec["raw_refs"]["tx"], "block": rec["raw_refs"]["block"],
                           "trace": feat.get("raw_ref_trace") if feat else None,
                           "code": c.get("code_ref") if c else None,
                           "creation": (c.get("creation") or {}).get("raw_ref") if c else None,
                           "source": (c.get("source") or {}).get("raw_ref") if c and c.get("source") else None,
                           "deploy_tx": (deploys.get(t.get("deploy_tx", "")) or {}).get("raw_refs") if t.get("deploy_tx") else None,
                           "mempool_extract": row["exposure"]["dumpster"]["extract"] if row["exposure"]["dumpster"] else
                           (mp["days"].get(day, {}) or {}).get("extract")}
        rows.append(row)
    seen_prim = {}
    for r in rows:  # DeFiHackLabs sometimes lists one incident twice (e.g. Conic / Conic2): keep the first, exclude repeats from stats
        if r.get("status") == "ok":
            if r["primary_tx"] in seen_prim:
                r["status"] = "duplicate-primary-tx"
                r["duplicate_of"] = seen_prim[r["primary_tx"]]
            else:
                seen_prim[r["primary_tx"]] = r["id"]
    return rows


def load_hits():
    """file -> outcome from chain scan coverage.json (status per mainnet entry) + hits.json (copycat candidates with strength)."""
    cov = ROOT / "research" / "chain-scan" / "coverage.json"
    if not (cov.exists() and HITS.exists()):
        return {}, None
    c = json.load(open(cov))
    rank = {"strong": 3, "medium": 2, "weak": 1}
    out = {}
    for r in c["entries"]:
        if r["status"] == "scanned_hit":
            best = max((x["strength"] for x in r.get("best", [])), key=lambda s: rank.get(s, 0), default="weak")
            out[r["file"]] = {"frontrun_candidate": "yes" if best in ("strong", "medium") else "weak-only", "best_strength": best,
                              "best": r.get("best"), "source": "research/chain-scan/coverage.json + hits.json (candidates, not confirmed)"}
        elif r["status"] == "scanned_nohit":
            out[r["file"]] = {"frontrun_candidate": "none-found", "source": "research/chain-scan/coverage.json"}
        else:
            out[r["file"]] = {"frontrun_candidate": "unscannable", "reason": r.get("reason"), "source": "research/chain-scan/coverage.json"}
    return out, "w2 coverage.json + hits.json"


# --------------------------------------------------------------------------------------------- stage: calibrate
def stage_calibrate(exploits):
    """Ground-truth the block-level heuristics and the dumpster's own coverage drift, using every OTHER tx in the exploit blocks
    (public = seen in dumpster before the block timestamp).  Output: calibration.json."""
    txs = jload(WORK / "txs.json", {})
    ext = {}
    for f in (rf.RAW / "mempool-dumpster").glob("extract_*.json"):
        d = json.load(open(f))
        ext[d["date"]] = d
    blocks = {}
    for r in txs.values():
        if "error" not in r:
            blocks[r["block"]] = r
    data = []
    for b, r in blocks.items():
        day = str(dt.datetime.fromtimestamp(r["block_ts"], dt.UTC).date())
        if day not in ext:
            continue
        seen, rows = ext[day]["control_first_seen_ms"], ext[day]["rows"]
        blk = sc.get_block(b)
        base = h2i(blk.get("baseFeePerGas")) if blk.get("baseFeePerGas") else 0
        T = blk["transactions"]
        n = len(T)
        tips = [max(0, h2i(t["gasPrice"]) - base) for t in T]
        for i, t in enumerate(T):
            hh = t["hash"].lower()
            fs = seen.get(hh) or (int(rows[hh].split(",")[0]) if hh in rows else None)
            later = tips[i + 1:]
            data.append({"day": day, "b": b, "idx": i, "n": n, "tip": tips[i], "pub": fs is not None and fs < r["block_ts"] * 1000,
                         "lhf": (sum(1 for x in later if x > tips[i]) / len(later)) if later else 0.0,
                         "is_exploit": hh in {h for h in txs}})
    ctrl = [d for d in data if not d["is_exploit"]]
    out = {"generated": now(), "n_control_txs": len(ctrl), "n_blocks": len({d["b"] for d in ctrl}),
           "note": "control = every other tx in the blocks that contain a mempool-era exploit tx; 'seen' = first seen by a dumpster source before block timestamp"}
    q = collections.defaultdict(lambda: [0, 0])
    for d in ctrl:
        k = d["day"][:4] + "Q" + str((int(d["day"][5:7]) - 1) // 3 + 1)
        q[k][0] += 1
        q[k][1] += d["pub"]
    out["control_seen_pct_by_quarter"] = {k: {"n": v[0], "seen_pct": round(100 * v[1] / v[0], 1)} for k, v in sorted(q.items())}
    rules = {"tip==0": lambda d: d["tip"] == 0, "out_of_order(lhf>=.9 & idx<n/2)": lambda d: d["lhf"] >= .9 and d["idx"] / d["n"] < .5,
             "idx==0": lambda d: d["idx"] == 0, "idx<=2": lambda d: d["idx"] <= 2,
             "tip==0 OR out_of_order": lambda d: d["tip"] == 0 or (d["lhf"] >= .9 and d["idx"] / d["n"] < .5)}
    out["heuristic_vs_dumpster_truth"] = {}
    for label, sub in (("2023-08..2023-12", [d for d in ctrl if d["day"] < "2024-01-01"]), ("2024+", [d for d in ctrl if d["day"] >= "2024-01-01"])):
        priv = [d for d in sub if not d["pub"]]
        res = {"n": len(sub), "not_seen_pct": pct(len(priv), len(sub))}
        for nm, rule in rules.items():
            fl = [d for d in sub if rule(d)]
            res[nm] = {"flagged": len(fl), "precision_private": pct(sum(1 for d in fl if not d["pub"]), len(fl)),
                       "recall_private": pct(sum(1 for d in fl if not d["pub"]), len(priv))}
        out["heuristic_vs_dumpster_truth"][label] = res
    # dumpster-side coverage evidence: summary files for the 15th of the middle month of each quarter (tiny, saved raw)
    cov = {}
    for y in range(2023, 2027):
        for m in (2, 5, 8, 11):
            dday = dt.date(y, m, 15)
            if dday < dt.date(2023, 8, 15) or dday > dt.date(2026, 10, 17):
                continue
            x = rf.get_soft(f"{DUMPSTER}/{dday:%Y-%m}/{dday}_summary.txt", source="mempool-dumpster", key=f"summary_{dday}", ext="txt")
            t = x["body"].decode("utf8", "replace")
            g = lambda pat: (re.search(pat, t) or [None, None])[1]
            cov[str(dday)] = {"unique_txs": g(r"Unique transactions:\s+([\d,]+)"), "included_on_chain": g(r"Included on-chain:\s+([\d,]+)"),
                              "sources": g(r"Sources:\s+(.*)"), "raw": x["path"], "status": x["status"]}
    out["dumpster_summary_by_quarter"] = cov
    jdump(W_6 / "calibration.json", out)
    print(json.dumps(out["control_seen_pct_by_quarter"]))
    return out


def pct(n, d):
    return round(100 * n / d, 1) if d else None


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def agg(rows):
    ok = [r for r in rows if r.get("status") == "ok"]
    ex = [r["exposure"] for r in ok]
    lab = collections.Counter(x["label"] for x in ex)
    lab_d = collections.Counter(x["label"] for x in ex if x["method"] == "mempool-dumpster")
    strict = collections.Counter(x["label"] for x in ex if x["confidence"] in ("high", "medium"))
    T = [r["techniques"] for r in ok]
    # lead time before block (dumpster era)
    leads = [x["dumpster"]["lead_before_block_ts_ms"] / 1000 for x in ex if x.get("dumpster") and x["label"] == "public"]
    resolved = lab["public"] + lab["private-bundle"]
    non_ctor = [t for t in T if not t.get("constructor_exploit")]
    gaps = [t["deploy_gap_s"] for t in non_ctor if t.get("target_role") == "attacker-contract" and t.get("deploy_gap_s") is not None and t.get("deploy_fresh_le_7d")]
    gaps_all = [t["deploy_gap_s"] for t in non_ctor if t.get("target_role") == "attacker-contract" and t.get("deploy_gap_s") is not None]
    gap_blocks = [t["deploy_gap_blocks"] for t in non_ctor if t.get("target_role") == "attacker-contract" and t.get("deploy_gap_s") is not None and t.get("deploy_fresh_le_7d")]
    atk_ctr = [t for t in non_ctor if t.get("target_role") == "attacker-contract"]
    ctrl = [(r["exposure"]["block_control"]) for r in ok if r["exposure"].get("block_control")]
    base_seen = sum(c["others_seen_public"] for c in ctrl)
    base_all = sum(c["others_in_block"] for c in ctrl)
    fr = [r for r in ok if (r.get("outcome") or {}).get("frontrun_candidate") == "yes"]
    fr_known = [r for r in ok if (r.get("outcome") or {}).get("frontrun_candidate") in ("yes", "none-found", "weak-only")]
    return {
        "n_exploits_total": len(rows), "n_with_mainnet_tx_and_trace": len(ok),
        "exposure_counts_all": dict(lab), "exposure_counts_high_med_confidence": dict(strict),
        "public_pct_of_resolved": pct(lab["public"], resolved), "private_pct_of_resolved": pct(lab["private-bundle"], resolved),
        "n_resolved": resolved, "n_unknown": lab["unknown"],
        "private_pct_lower_bound_of_all": pct(lab["private-bundle"], len(ok)),
        "public_pct_upper_bound_of_all": pct(lab["public"] + lab["unknown"], len(ok)),
        "dumpster_era_n": sum(1 for x in ex if x["method"] == "mempool-dumpster"),
        "dumpster_attacker_seen_pct": pct(lab_d["public"], lab_d["public"] + lab_d["private-bundle"]),
        "dumpster_control_seen_pct": pct(base_seen, base_all),
        "dumpster_relative_visibility": (round((lab_d["public"] / max(1, lab_d["public"] + lab_d["private-bundle"])) / (base_seen / base_all), 3) if base_all and (lab_d["public"] + lab_d["private-bundle"]) else None),
        "dumpster_excess_invisibility_pts": (round(100 * (1 - (lab_d["public"] / max(1, lab_d["public"] + lab_d["private-bundle"]))) - 100 * (1 - base_seen / base_all), 1) if base_all and (lab_d["public"] + lab_d["private-bundle"]) else None),
        "heuristic_flagged_pct_all": pct(sum(1 for r in ok if r["exposure"]["heuristic"]["flagged"]), len(ok)),
        "public_lead_time_s_median": med(leads), "public_lead_time_s_n": len(leads),
        "control_other_txs_seen_public_pct": pct(base_seen, base_all), "control_blocks_n": len(ctrl),
        "constructor_exploit_n": sum(1 for t in T if t.get("constructor_exploit")),
        "constructor_exploit_pct": pct(sum(1 for t in T if t.get("constructor_exploit")), len(T)),
        "internal_create_exploit_pct": pct(sum(1 for t in T if t.get("internal_create_exploit")), len(T)),
        "same_tx_deploy_and_attack_pct": pct(sum(1 for t in T if t.get("constructor_exploit") or t.get("internal_create_exploit")), len(T)),
        "attacker_contract_n": len(atk_ctr),
        "deploy_gap_s_median_fresh_le7d": med(gaps), "deploy_gap_blocks_median_fresh_le7d": med(gap_blocks),
        "deploy_gap_s_median_all": med(gaps_all), "deploy_gap_n": len(gaps),
        "deploy_gap_le_60s_pct": pct(sum(1 for g in gaps if g <= 60), len(gaps)),
        "deploy_gap_same_block_pct": pct(sum(1 for b in gap_blocks if b == 0), len(gap_blocks)),
        "direct_call_or_no_contract_pct": pct(sum(1 for t in non_ctor if t.get("target_role") in ("eoa-or-no-code", "victim-called-directly", "third-party-contract")), len(non_ctor)),
        "origin_check_pct_of_attacker_contracts": pct(sum(1 for t in atk_ctr if t.get("origin_check")), len(atk_ctr)),
        "sender_guard_pct_of_attacker_contracts": pct(sum(1 for t in atk_ctr if t.get("sender_guard")), len(atk_ctr)),
        "hardcoded_attacker_addr_pct": pct(sum(1 for t in atk_ctr if t.get("hardcoded_attacker_addr")), len(atk_ctr)),
        "unverified_pct_of_attacker_contracts": pct(sum(1 for t in atk_ctr if not t.get("verified_source")), len(atk_ctr)),
        "coinbase_bribe_pct": pct(sum(1 for t in T if t.get("coinbase_bribe_wei", 0) > 0), len(T)),
        "coinbase_bribe_eth_median_when_paid": med([t["coinbase_bribe_eth"] for t in T if t.get("coinbase_bribe_wei", 0) > 0]),
        "flashloan_pct": pct(sum(1 for t in T if t.get("uses_flashloan")), len(T)),
        "multi_tx_ge3_pct": pct(sum(1 for t in T if t.get("multi_tx")), len(T)),
        "tip_gwei_median": med([t["tip_gwei"] for t in T]), "gas_price_gwei_median": med([t["gas_price_gwei"] for t in T]),
        "tip_zero_pct": pct(sum(1 for t in T if t["tip_gwei"] == 0), len(T)),
        "tip_rank_in_block_median": med([t["tip_rank_in_block"] for t in T]),
        "tx_index_median": med([r["tx_index"] for r in ok]), "tx_index_0_pct": pct(sum(1 for r in ok if r["tx_index"] == 0), len(ok)),
        "frontrun_candidates_strong_n": sum(1 for r in ok if (r.get("outcome") or {}).get("best_strength") == "strong"),
        "frontrun_candidates_n": len(fr), "frontrun_scanned_n": len(fr_known),
        "frontrun_candidate_pct_of_scanned": pct(len(fr), len(fr_known)),
    }


def quarterly(rows):
    g = collections.defaultdict(list)
    for r in rows:
        if r.get("status") == "ok" and r["exposure"]["method"] == "mempool-dumpster":
            d = dt.datetime.fromtimestamp(r["block_ts"], dt.UTC)
            g[f"{d.year}Q{(d.month - 1) // 3 + 1}"].append(r)
    out = {}
    for k, v in sorted(g.items()):
        a = agg(v)
        out[k] = {kk: a[kk] for kk in ("n_exploits_total", "exposure_counts_all", "dumpster_attacker_seen_pct", "dumpster_control_seen_pct",
                                         "dumpster_relative_visibility", "constructor_exploit_pct", "coinbase_bribe_pct")}
    return out


def stage_analyze(exploits):
    txs, traces = jload(WORK / "txs.json", {}), jload(WORK / "traces.json", {})
    contracts, deploys = jload(WORK / "contracts.json", {}), jload(WORK / "deploy_txs.json", {})
    mp = jload(WORK / "mempool.json", {"days": {}, "tx": {}, "blocks": {}})
    add_later_higher(txs)
    jdump(WORK / "txs.json", txs)
    hits, hits_src = load_hits()
    rows = build_rows(exploits, txs, traces, contracts, deploys, mp, hits)
    jdump(W_6 / "per_exploit.json", {"generated": now(), "n": len(rows), "outcome_source": hits_src,
                                     "definitions": DEFS, "exploits": rows})
    by_era, by_year = {}, {}
    for r in rows:
        if r.get("status") != "ok":
            continue
        by_era.setdefault(r["era"], []).append(r)
        by_year.setdefault(str(r["year"]), []).append(r)
    out = {"generated": now(), "outcome_source": hits_src, "definitions": DEFS,
           "overall": agg(rows),
           "by_era": {k: agg(v) for k, v in sorted(by_era.items())},
           "by_year": {k: agg(v) for k, v in sorted(by_year.items())},
           "dumpster_era_only_by_year": {k: agg([r for r in v if r["exposure"]["method"] == "mempool-dumpster"])
                                         for k, v in sorted(by_year.items()) if any(r["exposure"]["method"] == "mempool-dumpster" for r in v)},
           "dumpster_era_by_quarter": quarterly(rows),
           "calibration_file": "data/evolution/calibration.json",
           "external_evidence": {
               "BACKRUNNER arXiv:2409.06213": "bots intercepted 18/158 attack txs (Jan 2023-May 2024); 17/158 attack txs visible in public mempool; 4 constructor attacks in 1.5 years; 50/54 attacks deployed >=1s before trigger",
               "APE (Qin et al.)": "10 of 12 whitehat attack txs were privately propagated"}}
    jdump(W_6 / "by_era.json", out)
    print(json.dumps({k: out["by_era"][k] for k in out["by_era"]}, indent=1)[:6000])
    return rows


DEFS = {
    "exposure.label": "public = tx hash present in mempool-dumpster day file with first_seen < block timestamp (Aug 2023+). "
                      "private-bundle = absent from dumpster (Aug 2023+) or first seen after block ts; before Aug 2023 only heuristic "
                      "signals (gas price 0 / zero tip / coinbase payment with low tip / top-of-block). unknown = pre-Aug-2023 with no private signal "
                      "(consistent with public, NOT proof). public/era-prior only before block 11.4M.",
    "constructor_exploit": "attack tx is a contract creation whose init code makes the exploit calls (calls a listed victim or >= 3 inner calls)",
    "internal_create_exploit": "tx.to is a contract but the trace contains an internal CREATE/CREATE2 whose subtree makes >= 3 calls or hits a victim",
    "deploy_gap": "creation tx (Etherscan getcontractcreation) of the attack contract -> attack tx; medians use attacker-owned contracts deployed <= 7 days earlier",
    "origin_check": "ORIGIN opcode followed by EQ within 24 opcodes in runtime bytecode, or `tx.origin` in verified source",
    "sender_guard": "origin_check OR attacker/deployer address hard-coded (PUSH20) in bytecode OR verified source has onlyOwner / msg.sender ==",
    "coinbase_bribe": "sum of ETH value of CALLs to block.coinbase (fee recipient) inside the attack tx trace",
    "flashloan": "call to a known flash-loan entry selector (Aave, Balancer, ERC-3156, Uniswap V3 flash, Morpho, DODO) or a flash callback "
                 "(uniswapV2Call, receiveFlashLoan, executeOperation, onFlashLoan, ...) inside the trace",
    "control_other_txs_seen_public_pct": "share of the OTHER txs in the same blocks that the dumpster saw before inclusion = baseline for 'visible' (Aug 2023+)",
    "front-run": "from chain scan scan_results/hits.json copycat candidates with score >= 5 (medium/strong tiers); candidates not confirmations",
}


# --------------------------------------------------------------------------------------------- stage: senders (evolution study v2)
PIN_BLOCK = 26243670  # chain head when the v2 relabel pass was run (2026-10-21); every "latest nonce" below is read at this block


def stage_senders(exploits, threads=4):
    """eth_getTransactionCount(sender, PIN_BLOCK) for every sender of a listed attack tx -> work/sender_nonces.json.
    Used only as a bot-likeness signal (long-lived, still-active accounts vs one-shot exploit wallets)."""
    out = jload(WORK / "sender_nonces.json", {})
    txs = jload(WORK / "txs.json", {})
    todo = sorted({txs[t["hash"].lower()]["from"] for e in exploits for t in e["_keep"]
                   if t["hash"].lower() in txs and "error" not in txs[t["hash"].lower()]} - set(out))

    def one(a):
        n = sc.call("eth_getTransactionCount", [a, hex(PIN_BLOCK)], key=f"eth_getTransactionCount_{a}_{PIN_BLOCK}")
        return a, h2i(n)

    with cf.ThreadPoolExecutor(threads) as ex:
        for fut in cf.as_completed([ex.submit(one, a) for a in todo]):
            try:
                a, n = fut.result()
            except Exception as ex_:  # noqa: BLE001
                print("nonce error", repr(ex_)[:150], file=sys.stderr)
                continue
            out[a] = n
    jdump(WORK / "sender_nonces.json", out)
    return out

# --------------------------------------------------------------------------------------------- stage: relabel (evolution study v2)
# Sender-class relabel pass.  DeFiHackLabs "attack txs" are any hashes in a PoC header; many were sent by MEV bots (which
# copied or raced the attacker), by whitehat rescuers, or are not attack txs at all (approvals, init calls, refund batches).
# v1 (per_exploit.json / by_era.json / findings.txt) is left byte-identical; this stage writes sender_class.json,
# per_exploit_v2.json, by_era_v2.json and findings_v2.txt next to it.
DHL_CLONE = pathlib.Path("data/raw/defihacklabs_clone/repo")
H40 = re.compile(r"0x[0-9a-fA-F]{40}")
WHITEHAT_PAT = re.compile(r"white-?hat|rescue|bitfinding|blocksec", re.I)
BOTLIKE_KIND = re.compile(r"copy|copier|replay|arbitrage|arb |searcher|bot|front", re.I)
CLASSES = ("attacker", "bot", "whitehat", "unknown")

# addr -> (class, label, kind, evidence, confidence).  Later layers override earlier ones (attackers < racers < bots < whitehats).
BOT_EXTRA = {
    "0xfde0d1575ed8e06fbf36256bcdfa1f359281455a": ("Yoink", "searcher", "Etherscan label 'MEV Frontrunner Yoink'; incidents/{alkimiya,defiplaza,kelp-rseth,ronin,paraswap,time,uncx,transitswap,sushi-rp2}"),
    "0xc0ffeebabe5d496b2dde509f9fa189c25cf29671": ("c0ffeebabe.eth", "searcher", "public ENS label; sender match only (publication policy: txs never fetched or traced)"),
    "0x935bfb495e33f74d2e9735df1da66ace442ede48": ("Makina MEV searcher 0x935b", "searcher", "Makina post-mortem 'MEV searcher (0x935b)'; incidents/makina-2026"),
    "0x26bce6ecb5b10138e4bf14ac0ffcc8727fef3b2e": ("0xa57 family MEV bot (Earning.Farm)", "searcher", "incidents/earningfarm-2022; w1 recurring_bots; w4 shortlist; ~125k nonce"),
    "0x5f259d0b76665c337c6104145894f4d1d2758b8c": ("Euler copier 0x5F259D0b", "copier", "incidents/euler-copybot-2023 (self-described MEV bot, copied the exploit)"),
    "0xe71aca93c0e0721f8250d2d0e4f883aa1c020361": ("SHOCO generic searcher", "searcher", "incidents/shoco-2023; w1 recurring_bots; w4 shortlist"),
    "0x7248939f65bdd23aab9eaab1bc4a4f909567486e": ("anonymous MEV bot A", "searcher", "research/anon-bots/profiles.txt section A: 5,189-tx private-bundle searcher, DHL rows are 3 of 48 runs of one swap-back template"),
    "0xd215ffaf0f85fb6f93f11e49bd6175ad58af0dfd": ("anonymous MEV bot 0xd215", "searcher", "research/anon-bots/profiles.txt section B: ~9,000-tx general MEV bot, vanity-hash 0xbeef txs"),
    "0x43debe92a7a32dca999593fad617dbd2e6b080a5": ("copycat bot 0x43debe92", "copier", "research/anon-bots/profiles.txt section B: replayed the INUMI drain one block after d215"),
    "0xc9a5643ed8e4cd68d16fe779d378c0e8e7225a54": ("arbitrage bot 0xc9a5643e", "searcher", "incidents/balancer-2025 racers (arb bots incl. 0xc9a5643e); sends 2 DHL rows (BBT, Scorch) from a 2,555-nonce account"),
    "0x6ec21d1868743a44318c3c259a6d4953f9978538": ("pETH front-runner (Curve01)", "frontrunner", "incidents/curve-vyper-2023 ('pETH front-runner (not c0ffeebabe)'); Etherscan label Frontrunner (JPEGd_69 Exploit); returned ~90%"),
}
ATTACKER_EXTRA = {
    "0x6ce9fa08f139f5e48bc607845e57efe9aa34c9f6": "research/anon-bots/profiles.txt section C: serial exploiter (finds bugs itself; fresh contract per target); copied afterwards by Yoink",
    "0x8d67db0b205e32a5dd96145f022fa18aae7dc8aa": "research/candidates (Conic ETH-pool attacker per CertiK skyline)",
    "0x50275e0b7261559ce1644014d4b78d4aa63be836": "research/candidates (KyberSwap Elastic main exploiter per Rekt)",
}
WHITEHAT_EXTRA = {
    "0x0000003502aa61a5f1b1fdadff2cf947dfda526e": ("BlockSec Whitehat Ops 2", "Etherscan label (research/candidates paraspace-2023-03; recurring_bots)"),
}
# tx-level overrides, keyed by the first 10 hex chars of the hash.  role 'non-attack' = the listed tx is not an attack tx.
TX_OVERRIDES = {
    "0x8df54ebe": {"role": "non-attack", "why": "coinbase: v1 'primary' is a third-party approve sent by an account that is neither the listed attacker nor the attack contract's creator (the real attack tx is the listed 0x33b2cb5b from the DHL attacker)"},
    "0x53fd9277": {"role": "non-attack", "why": "NomadBridge: the protocol's own initialize() call (sender is the contract deployer), not one of the copycat drains"},
    "0x62d280ab": {"role": "non-attack", "why": "AkutarNFT: refund batch sent by a third party after the lock-up bug, not the exploit"},
}


def build_registry():
    """addr -> {class,label,kind,evidence,confidence}.  Incident files are the evidence source; a snapshot is saved so that a
    re-run is stable while incident.json files are being edited elsewhere."""
    snap = WORK / "sender_registry.json"
    reg = {}
    try:
        for f in sorted((ROOT / "incidents").glob("*/incident.json")):
            d = json.loads(f.read_text())
            slug = d.get("slug", f.parent.name)
            at = d.get("attacker")
            if isinstance(at, dict):
                for e in at.get("eoas") or []:
                    a = (e if isinstance(e, str) else (e.get("address") or "")).lower()
                    m = H40.findall(a)
                    if m:
                        reg[m[0].lower()] = {"class": "attacker", "label": f"attacker ({slug})", "kind": "exploiter", "confidence": "high",
                                             "evidence": f"incidents/{slug}: listed under attacker.eoas"}
            for o in d.get("other_racers") or []:
                if isinstance(o, dict) and o.get("eoa") and BOTLIKE_KIND.search(str(o.get("kind") or "")) and not re.search(r"unknown", str(o.get("kind") or ""), re.I):
                    reg[o["eoa"].lower()] = {"class": "bot", "label": str(o.get("label"))[:70], "kind": "racer/copier", "confidence": "medium",
                                             "evidence": f"incidents/{slug}: other_racers ({str(o.get('kind'))[:60]})"}
            for b in d.get("bots") or []:
                if isinstance(b, dict) and b.get("eoa"):
                    lab = str(b.get("label") or "")
                    cls = "whitehat" if WHITEHAT_PAT.search(lab) else "bot"
                    reg[b["eoa"].lower()] = {"class": cls, "label": lab[:70], "kind": "whitehat rescuer" if cls == "whitehat" else "bot", "confidence": "high",
                                             "evidence": f"incidents/{slug}: bots[] '{lab[:60]}'"}
        for a, ev in ATTACKER_EXTRA.items():
            reg.setdefault(a, {"class": "attacker", "label": "attacker (verified)", "kind": "exploiter", "confidence": "high", "evidence": ev})
        for a, (lab, kind, ev) in BOT_EXTRA.items():
            reg[a] = {"class": "bot", "label": lab, "kind": kind, "confidence": "high", "evidence": ev}
        for a, (lab, ev) in WHITEHAT_EXTRA.items():
            reg[a] = {"class": "whitehat", "label": lab, "kind": "whitehat rescuer", "confidence": "high", "evidence": ev}
        jdump(snap, reg)
    except Exception as ex_:  # noqa: BLE001
        print("registry: using snapshot because", repr(ex_)[:120], file=sys.stderr)
        reg = jload(snap, {})
    return reg


def poc_addresses(exploits):
    """file -> every address mentioned in the DeFiHackLabs PoC source (cached so a re-run does not need the clone)."""
    cache_p = WORK / "poc_addresses.json"
    cache = jload(cache_p, {})
    for e in exploits:
        if e["file"] in cache:
            continue
        p = DHL_CLONE / e["file"]
        if p.exists():
            cache[e["file"]] = sorted({a.lower() for a in H40.findall(p.read_text(errors="replace"))})
    jdump(cache_p, cache)
    return cache


def classify_txs(exploits, txs, traces, contracts, nonces, reg, poc):
    """-> {hash: record} for every listed mainnet tx we fetched, plus one record per c0ffeebabe tx (sender match only).
    Rule order: tx override -> address registry -> R1 -> R1b -> R2 -> R3 -> default attacker."""
    rows_of = collections.defaultdict(set)  # sender -> exploit names (recurring-sender sweep)
    paid_bribe = set()  # senders with at least one listed tx that paid block.coinbase
    for e in exploits:
        for t in e["_keep"]:
            r = txs.get(t["hash"].lower())
            if r and "error" not in r:
                rows_of[r["from"]].add(e["name"])
                if (traces.get(t["hash"].lower()) or {}).get("coinbase_bribe_wei", 0) > 0:
                    paid_bribe.add(r["from"])
    out = {}
    members = collections.defaultdict(list)  # exploit id -> hashes (a hash can be listed by two DHL entries)
    for e in exploits:
        listed = {a.lower() for a in e.get("attacker", [])}
        listed_ctr = {a.lower() for a in e.get("attack_contract", [])}
        in_poc = set(poc.get(e["file"], []))
        for t in e["_keep"]:
            h = t["hash"].lower()
            rec = txs.get(h)
            if not rec or "error" in rec:
                continue
            f = traces.get(h)
            s = rec["from"]
            nonce, latest = rec["nonce"], nonces.get(s)
            bribe = (f["coinbase_bribe_wei"] / 1e18) if f else 0.0
            tipg = rec["tip_wei"] / 1e9
            to = rec["to"]
            tgt = (f["target"] if f and f.get("target") else to)
            c = contracts.get(tgt) if tgt else None
            creator = ((c or {}).get("creation") or {}).get("contractCreator", "")
            is_creator = (to is None) or (creator.lower() == s) or (s in listed_ctr)
            E_A = s in listed
            facts = {"sender": s, "sender_nonce_at_tx": nonce, "sender_latest_nonce": latest, "idx": rec["index"], "bribe_eth": round(bribe, 6), "tip_gwei": round(tipg, 4),
                     "sender_in_dhl_attacker_header": E_A, "sender_deployed_or_listed_attack_contract": bool(is_creator),
                     "sender_in_poc_source": s in in_poc, "n_exploit_rows_for_sender": len(rows_of[s])}
            role, ov = "attack", TX_OVERRIDES.get(h[:10])
            if ov:
                rec_c = {"class": "unknown", "confidence": "high", "label": None, "evidence": [ov["why"]]}
                role = ov["role"]
            elif s in reg:
                g = reg[s]
                rec_c = {"class": g["class"], "confidence": g["confidence"], "label": g["label"], "evidence": [g["evidence"]]}
            elif nonce >= 1000 and rec["index"] == 0 and (bribe > 0 or tipg >= 100):
                rec_c = {"class": "bot", "confidence": "low", "label": None, "evidence": [
                    f"R1: sender had sent {nonce} txs before this one (latest {latest}), tx index 0 and " + (f"{bribe:.3f} ETH coinbase payment" if bribe > 0 else f"{tipg:.0f} gwei tip") + ": searcher profile"]}
            elif nonce >= 1000 and len(rows_of[s]) >= 2 and s in paid_bribe:
                rec_c = {"class": "bot", "confidence": "low", "label": None, "evidence": [
                    f"R1b: sender recurs in {len(rows_of[s])} DHL rows with coinbase payments and {nonce}+ prior txs (latest nonce {latest})"]}
            elif nonce >= 1000 and (latest or 0) >= 2000:
                rec_c = {"class": "unknown", "confidence": "low", "label": None, "evidence": [
                    f"R2: long-lived busy account (nonce {nonce} at the tx, {latest} now) without the searcher signature; could be a copycat exploiter or a bot"]}
            elif listed and not E_A and not is_creator and s not in in_poc:
                rec_c = {"class": "unknown", "confidence": "low", "label": None, "evidence": [
                    "R3: DHL names attacker(s) but this sender is not among them, did not deploy the attack contract and is absent from the PoC source"]}
            else:
                if E_A and is_creator and nonce < 1000:
                    conf = "medium"
                    why = f"sender is the DHL-listed attacker and deployed/owns the attack contract (nonce {nonce} at the tx)"
                else:
                    conf = "low"
                    why = "default: no bot/whitehat evidence; " + ("sender is the DHL-listed attacker" if E_A else "sender not in the DHL header") + \
                          ("" if is_creator else ", did not deploy the attack contract") + f" (nonce {nonce} at the tx)"
                rec_c = {"class": "attacker", "confidence": conf, "label": None, "evidence": [why]}
            if rec_c["class"] == "attacker" and len(rows_of[s]) >= 2:
                rec_c["evidence"].append(f"sender recurs in {len(rows_of[s])} DHL rows (serial exploiter or operator)")
            members[e["file"]].append(h)
            if h in out:
                continue
            out[h] = {"hash": h, "id": e["file"], "name": e["name"], "block": rec["block"], "index": rec["index"], "tx_role": role,
                      "sender_class": rec_c["class"], "confidence": rec_c["confidence"], "label": rec_c["label"], "evidence": rec_c["evidence"], "facts": facts,
                      "measured": True}
        for x in e["_excl"]:  # c0ffeebabe txs: class from the DHL sender only
            ti = next((q for q in e["tx_info"] if q["hash"].lower() == x["hash"].lower()), {})
            h = x["hash"].lower()
            members[e["file"]].append(h)
            out[h] = {"hash": h, "id": e["file"], "name": e["name"], "block": ti.get("block"), "index": ti.get("index"), "tx_role": "attack",
                      "sender_class": "bot", "confidence": "high", "label": "c0ffeebabe.eth", "measured": False,
                      "evidence": ["sender address in the DHL tx listing is c0ffeebabe.eth (public ENS label); tx not fetched or traced (publication policy); only block and index from the DHL listing"],
                      "facts": {"sender": (ti.get("from") or "").lower(), "idx": ti.get("index")}}
    return out, members


def wilson(k, n, z=1.96):
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return [round(100 * max(0, c - h), 1), round(100 * min(1, c + h), 1)]


def no_watchable_window(t):
    """constructor exploit, internal CREATE that attacks, or attack contract deployed in the same block as the attack"""
    return bool(t.get("constructor_exploit") or t.get("internal_create_exploit") or
                (t.get("target_role") == "attacker-contract" and t.get("deploy_gap_blocks") == 0))


def agg2(rows):
    """v1 `agg` plus counts, Wilson 95% intervals and the 'no watchable window' share."""
    a = agg(rows)
    ok = [r for r in rows if r.get("status") == "ok"]
    T = [r["techniques"] for r in ok]
    ex = [r["exposure"] for r in ok]
    lab = collections.Counter(x["label"] for x in ex)
    labd = collections.Counter(x["label"] for x in ex if x["method"] == "mempool-dumpster")
    non_ctor = [t for t in T if not t.get("constructor_exploit")]
    gap_b = [t["deploy_gap_blocks"] for t in non_ctor if t.get("target_role") == "attacker-contract" and t.get("deploy_gap_s") is not None and t.get("deploy_fresh_le_7d")]
    atk_ctr = [t for t in non_ctor if t.get("target_role") == "attacker-contract"]
    n = len(T)
    nw = sum(1 for t in T if no_watchable_window(t))
    k = {"constructor_exploit_pct": (sum(1 for t in T if t.get("constructor_exploit")), n),
         "same_tx_deploy_and_attack_pct": (sum(1 for t in T if t.get("constructor_exploit") or t.get("internal_create_exploit")), n),
         "no_watchable_window_pct": (nw, n),
         "coinbase_bribe_pct": (sum(1 for t in T if t.get("coinbase_bribe_wei", 0) > 0), n),
         "tip_zero_pct": (sum(1 for t in T if t["tip_gwei"] == 0), n),
         "public_pct_of_resolved": (lab["public"], lab["public"] + lab["private-bundle"]),
         "dumpster_attacker_seen_pct": (labd["public"], labd["public"] + labd["private-bundle"]),
         "deploy_gap_same_block_pct": (sum(1 for b in gap_b if b == 0), len(gap_b)),
         "origin_check_pct_of_attacker_contracts": (sum(1 for t in atk_ctr if t.get("origin_check")), len(atk_ctr)),
         "flashloan_pct": (sum(1 for t in T if t.get("uses_flashloan")), n)}
    a["no_watchable_window_n"] = nw
    a["no_watchable_window_pct"] = pct(nw, n)
    a["counts"] = {kk: {"k": v[0], "n": v[1]} for kk, v in k.items()}
    a["wilson95_pct"] = {kk: wilson(*v) for kk, v in k.items()}
    a["pre_aug2023_labels"] = dict(collections.Counter(x["label"] for x in ex if x["method"] != "mempool-dumpster"))
    a["own_contract_attacks_n"] = len(atk_ctr)
    return a


def group_by(rows, keyf):
    g = collections.defaultdict(list)
    for r in rows:
        if r.get("status") == "ok":
            g[keyf(r)].append(r)
    return dict(sorted(g.items()))


def half_of(r):
    d = dt.datetime.fromtimestamp(r["block_ts"], dt.UTC)
    return f"{d.year}H{1 if d.month <= 6 else 2}"


def quarter_of(r):
    d = dt.datetime.fromtimestamp(r["block_ts"], dt.UTC)
    return f"{d.year}Q{(d.month - 1) // 3 + 1}"


def exposure_series(rows, keyf):
    """dumpster-era exposure per period: attacker public/private counts vs the same-block control (ordinary txs)."""
    g = collections.defaultdict(list)
    for r in rows:
        if r.get("status") == "ok" and r["exposure"]["method"] == "mempool-dumpster":
            g[keyf(r)].append(r)
    out = {}
    for k_, v in sorted(g.items()):
        a = agg(v)
        c = collections.Counter(r["exposure"]["label"] for r in v)
        res = c["public"] + c["private-bundle"]
        out[k_] = {"n": len(v), "public": c["public"], "private_bundle": c["private-bundle"], "unknown": c["unknown"],
                   "attacker_seen_pct": a["dumpster_attacker_seen_pct"], "attacker_seen_wilson95": wilson(c["public"], res),
                   "control_seen_pct": a["dumpster_control_seen_pct"], "relative_visibility": a["dumpster_relative_visibility"],
                   "excess_invisibility_pts": a["dumpster_excess_invisibility_pts"],
                   "constructor_exploit_pct": a["constructor_exploit_pct"], "coinbase_bribe_pct": a["coinbase_bribe_pct"]}
    return out


def table_block(rows):
    """overall / by_era / by_year / by_half / dumpster_era_by_quarter for one population of rows."""
    return {"overall": agg2(rows),
            "by_era": {k_: agg2(v) for k_, v in group_by(rows, lambda r: r["era"]).items()},
            "by_year": {k_: agg2(v) for k_, v in group_by(rows, lambda r: str(r["year"])).items()},
            "by_half": {k_: agg2(v) for k_, v in group_by(rows, half_of).items()},
            "dumpster_era_by_quarter": exposure_series(rows, quarter_of),
            "dumpster_era_by_half": exposure_series(rows, half_of)}


def eth_inflow_proxy(feat, rec):
    """Gross-value proxy for a bot tx: ETH received by the tx target contract (or the sender) from anyone other than themselves,
    summed over non-reverted calls.  Includes ETH from WETH unwrapping and any ETH flash principal, so it OVERSTATES revenue and the
    bribe share computed from it is a LOWER bound.  None if the trace file is missing."""
    p = ROOT / (feat.get("raw_ref_trace") or "")
    if not feat.get("raw_ref_trace") or not p.exists():
        return None
    j = json.loads(p.read_text())
    root = j.get("result", j)
    own = {x for x in (feat.get("target"), feat.get("trace_created_addr"), (rec["to"] or "").lower(), rec["from"]) if x}
    tot = 0

    def walk(n, dead):
        nonlocal tot
        dead = dead or bool(n.get("error"))
        v = h2i(n.get("value")) if n.get("value") else 0
        if v > 0 and not dead and (n.get("to") or "").lower() in own and (n.get("from") or "").lower() not in own:
            tot += v
        for c in n.get("calls") or []:
            walk(c, dead)

    walk(root, False)
    return tot / 1e18


def agg_bot(recs):
    """bot-side statistics.  recs = compact bot rows; `measured` False rows (c0ffeebabe) only carry block/index/era."""
    m = [r for r in recs if r["measured"]]
    n, nm = len(recs), len(m)
    idx0 = sum(1 for r in recs if r["tx_index"] == 0)
    paid = [r for r in m if r["bribe_eth"] > 0]
    sh = [r["bribe_share_of_eth_inflow"] for r in paid if r.get("bribe_share_of_eth_inflow") is not None]
    dm = [r for r in m if r["exposure_method"] == "mempool-dumpster"]
    dl = collections.Counter(r["exposure"] for r in dm)
    res = dl["public"] + dl["private-bundle"]
    tot_b = sum(r["bribe_eth"] for r in paid)
    tot_in = sum(r["eth_inflow_proxy"] for r in paid if r.get("eth_inflow_proxy") is not None and r.get("bribe_share_of_eth_inflow") is not None)
    tot_bs = sum(r["bribe_eth"] for r in paid if r.get("eth_inflow_proxy") is not None and r.get("bribe_share_of_eth_inflow") is not None)
    return {"n_rows": n, "n_measured": nm, "n_not_measured_actions_only": n - nm,
            "tx_index_0_n": idx0, "tx_index_0_pct": pct(idx0, n), "tx_index_0_wilson95": wilson(idx0, n),
            "tx_index_median": med([r["tx_index"] for r in recs]),
            "bribe_paid_n": len(paid), "bribe_paid_pct_of_measured": pct(len(paid), nm), "bribe_paid_wilson95": wilson(len(paid), nm),
            "bribe_eth_total": round(tot_b, 3), "bribe_eth_median_when_paid": med([r["bribe_eth"] for r in paid]),
            "bribe_eth_max": max([r["bribe_eth"] for r in paid], default=None),
            "bribe_share_of_eth_inflow_median": med(sh), "bribe_share_n": len(sh),
            "bribe_share_of_eth_inflow_aggregate": (round(tot_bs / tot_in, 3) if tot_in else None),
            "tip_zero_pct_of_measured": pct(sum(1 for r in m if r["tip_gwei"] == 0), nm),
            "tip_gwei_median": med([r["tip_gwei"] for r in m]),
            "exposure_counts": dict(collections.Counter(r["exposure"] for r in m)),
            "dumpster_era_n": len(dm), "dumpster_seen_public_pct": pct(dl["public"], res), "dumpster_private_n": dl["private-bundle"],
            "dumpster_public_n": dl["public"],
            "constructor_n": sum(1 for r in m if r["constructor"]), "internal_create_n": sum(1 for r in m if r["internal_create"]),
            "flashloan_pct": pct(sum(1 for r in m if r["flashloan"]), nm)}


def large_bribes(rows, thr=5.0):
    out = []
    for r in rows:
        if r.get("status") == "ok" and r["techniques"].get("coinbase_bribe_eth", 0) >= thr:
            out.append({"name": r["name"], "date": r["date"], "bribe_eth": round(r["techniques"]["coinbase_bribe_eth"], 3), "era": r["era"][:2],
                        "tip_gwei": round(r["techniques"]["tip_gwei"], 3), "tx": r["primary_tx"], "tx_index": r["tx_index"],
                        "sender_class": r.get("sender_class"), "confidence": r.get("sender_class_confidence")})
    return sorted(out, key=lambda x: -x["bribe_eth"])


DEFS_V2 = {
    "sender_class": "class of the account that SENT a DeFiHackLabs-listed tx: attacker (the exploiter), bot (MEV searcher / copier / front-runner / "
                    "arbitrage bot that raced or replayed the exploit), whitehat (rescuer or security firm), unknown (sender cannot be placed). "
                    "tx_role 'non-attack' marks listed hashes that are not attack txs (approve, init, refund batch); they join no aggregate.",
    "rule_order": "tx override -> address registry (incident files, w1/w7 research, DHL header) -> R1 (>=1000 prior txs, tx index 0, coinbase payment or "
                  ">=100 gwei tip -> bot, low) -> R1b (>=1000 prior txs, recurs in >=2 rows, pays coinbase -> bot, low) -> R2 (>=1000 prior txs and >=2000 "
                  "now, no searcher signature -> unknown, low) -> R3 (DHL names attackers, sender is not one, did not deploy the attack contract, absent from "
                  "the PoC source -> unknown, low) -> default attacker (medium if sender is the DHL attacker AND deployed the attack contract AND <1000 prior txs; "
                  "else low).  Registry hits are high confidence.",
    "mixed_rows": "A row may list an attacker tx and a bot tx.  The attacker's tx (earliest non-pure-deploy) drives every attacker-side statistic; the bot's tx "
                  "goes to the bot-side table.  If a row lists ONLY bot / whitehat / non-attack txs, the attacker's own tx is unlisted: attacker-side fields are "
                  "'not measured' and the row is excluded from attacker aggregates (it stays in the bot-side table).",
    "attacker_only": "rows whose measured tx is sender_class == attacker (any confidence).",
    "sensitivity_incl_unknown": "attacker_only plus rows whose only attack-role txs are sender_class == unknown (their earliest such tx is measured).",
    "bot_side": "rows with at least one attack-role tx of sender_class == bot; one record per exploit (earliest bot tx).  c0ffeebabe.eth txs are classified from "
                "the DHL sender only and carry block/index; nothing else was fetched.",
    "bribe_share_of_eth_inflow": "coinbase payment / ETH received by the bot's target contract or sender from third parties in the non-reverted part of the trace. "
                                 "The denominator includes unwrapped WETH and ETH flash principal, so the share is a LOWER bound of bribe / gross.",
    "no_watchable_window": "constructor exploit, internal CREATE that attacks, or attack contract deployed in the same block as the attack",
    "tx_index_0": "position 0 in the block (top of block); for bot rows computed over every row including the unmeasured c0ffeebabe ones",
}
V2_METRICS = ["n_with_mainnet_tx_and_trace", "constructor_exploit_pct", "same_tx_deploy_and_attack_pct", "no_watchable_window_pct",
              "deploy_gap_s_median_fresh_le7d", "deploy_gap_same_block_pct", "coinbase_bribe_pct", "coinbase_bribe_eth_median_when_paid",
              "public_pct_of_resolved", "dumpster_attacker_seen_pct", "dumpster_control_seen_pct", "dumpster_relative_visibility",
              "tx_index_median", "tx_index_0_pct", "tip_gwei_median", "tip_zero_pct", "flashloan_pct", "origin_check_pct_of_attacker_contracts",
              "sender_guard_pct_of_attacker_contracts", "unverified_pct_of_attacker_contracts", "multi_tx_ge3_pct", "frontrun_candidates_n"]
MEASURED_FIELDS = ["status", "primary_tx", "block", "tx_index", "block_ts", "block_time_utc", "year", "era", "attacker_eoa", "exposure", "techniques",
                   "outcome", "raw_refs"]
NOT_MEASURED = "not measured"


def stage_relabel(exploits):
    required = (WORK / "txs.json", WORK / "traces.json", WORK / "contracts.json", WORK / "deploy_txs.json", WORK / "mempool.json", WORK / "sender_nonces.json", W_6 / "per_exploit.json")
    if any(not path.is_file() for path in required):
        raise SystemExit("evolution.py relabel needs the full cache and unpublished working intermediates; the public subset is insufficient. Re-fetch the research inputs first.")
    import copy
    txs, traces = jload(WORK / "txs.json", {}), jload(WORK / "traces.json", {})
    contracts, deploys = jload(WORK / "contracts.json", {}), jload(WORK / "deploy_txs.json", {})
    mp = jload(WORK / "mempool.json", {"days": {}, "tx": {}, "blocks": {}})
    nonces = jload(WORK / "sender_nonces.json", {})
    hits, hits_src = load_hits()
    reg = build_registry()
    poc = poc_addresses(exploits)
    cls, members = classify_txs(exploits, txs, traces, contracts, nonces, reg, poc)
    v1 = build_rows(exploits, txs, traces, contracts, deploys, mp, hits)
    v1_disk = jload(W_6 / "per_exploit.json")["exploits"]
    reproduced = json.dumps(v1, sort_keys=True) == json.dumps(v1_disk, sort_keys=True)
    dup_ids = {r["id"] for r in v1 if r["status"] == "duplicate-primary-tx"}
    v1_by_id = {r["id"]: r for r in v1}
    by_name = {e["file"]: e for e in exploits}

    def attack_hashes(e):  # attack-role fetched txs of one exploit, ordered
        return [t["hash"].lower() for t in e["_keep"] if t["hash"].lower() in cls and cls[t["hash"].lower()]["tx_role"] == "attack"]  # noqa

    A = {e["file"]: {h for h in attack_hashes(e) if cls[h]["sender_class"] == "attacker"} for e in exploits}
    U = {e["file"]: {h for h in attack_hashes(e) if cls[h]["sender_class"] == "unknown"} for e in exploits}
    B = {e["file"]: {h for h in attack_hashes(e) if cls[h]["sender_class"] == "bot"} for e in exploits}
    W = {e["file"]: {h for h in attack_hashes(e) if cls[h]["sender_class"] == "whitehat"} for e in exploits}

    def view(pick):
        ex2 = []
        for e in exploits:
            e2 = dict(e)
            e2["_keep"] = [t for t in e["_keep"] if pick(e, t["hash"].lower())]
            ex2.append(e2)
        rows = build_rows(ex2, txs, traces, contracts, deploys, mp, hits)
        for r in rows:
            if r["id"] in dup_ids and r.get("status") == "ok":
                r["status"] = "duplicate-primary-tx"
            if r.get("primary_tx") in cls:
                c = cls[r["primary_tx"]]
                r["sender_class"], r["sender_class_confidence"], r["sender_label"] = c["sender_class"], c["confidence"], c["label"]
        return rows

    att_rows = {r["id"]: r for r in view(lambda e, h: h in A[e["file"]])}
    sen_rows = {r["id"]: r for r in view(lambda e, h: h in A[e["file"]] or (not A[e["file"]] and h in U[e["file"]]))}
    bot_rows_full = {r["id"]: r for r in view(lambda e, h: h in B[e["file"]])}
    wh_rows = {r["id"]: r for r in view(lambda e, h: h in W[e["file"]])}

    # ---------------- per-exploit v2 rows
    v2 = []
    for r in v1:
        e = by_name[r["id"]]
        r2 = copy.deepcopy(r)
        mine = [cls[h] for h in dict.fromkeys(members[r["id"]])]
        mine.sort(key=lambda x: (x["block"] or 0, x["index"] or 0))
        for x in r2.get("all_txs", []):
            c = cls[x["hash"]]
            x.update({"sender": c["facts"]["sender"], "sender_class": c["sender_class"], "sender_class_confidence": c["confidence"],
                      "sender_label": c["label"], "tx_role": c["tx_role"]})
        for x in mine:
            if not x["measured"]:
                r2.setdefault("all_txs", []).append({"hash": x["hash"], "block": x["block"], "index": x["index"], "sender": x["facts"]["sender"],
                                                     "sender_class": "bot", "sender_class_confidence": "high", "sender_label": "c0ffeebabe.eth",
                                                     "tx_role": "attack", "not_fetched": "publication policy: c0ffeebabe.eth txs are never fetched or traced"})
        atk = [x for x in mine if x["tx_role"] == "attack"]
        classes_present = sorted({x["sender_class"] for x in atk})
        nonatk = [x["hash"] for x in mine if x["tx_role"] != "attack"]
        r2["v1_status"] = r["status"]
        r2["v1_primary"] = {"tx": r.get("primary_tx"), "sender_class": cls[r["primary_tx"]]["sender_class"] if r.get("primary_tx") in cls else None,
                            "tx_role": cls[r["primary_tx"]]["tx_role"] if r.get("primary_tx") in cls else None}
        r2["tx_classes_present"] = classes_present
        r2["non_attack_txs"] = nonatk
        if not mine:
            r2.update({"sender_class": None, "sender_class_confidence": None, "sender_class_evidence": ["DHL lists no resolvable mainnet tx"], "row_kind": "no-tx",
                       "attacker_side_status": "no tx"})
            v2.append(r2)
            continue
        kind_set = set(classes_present)
        r2["row_kind"] = ("mixed" if len(kind_set) > 1 else f"{next(iter(kind_set))}-only") if kind_set else "non-attack-only"
        if A[r["id"]]:
            r2["sender_class_row_source"] = "attacker-view primary"
            ar = att_rows[r["id"]]
            for k_ in MEASURED_FIELDS:
                r2[k_] = copy.deepcopy(ar.get(k_))
            if r2["status"] == "duplicate-primary-tx":
                r2["duplicate_of"] = ar.get("duplicate_of") or r.get("duplicate_of")
            pc = cls[ar["primary_tx"]]
            r2["attacker_side_status"] = "measured"
            r2["primary_changed_vs_v1"] = ar["primary_tx"] != r.get("primary_tx")
        elif U[r["id"]]:
            ar = sen_rows[r["id"]]
            for k_ in MEASURED_FIELDS:
                r2[k_] = copy.deepcopy(ar.get(k_))
            pc = cls[ar["primary_tx"]]
            r2["attacker_side_status"] = "sender unknown: excluded from attacker_only, included in sensitivity_incl_unknown"
            r2["primary_changed_vs_v1"] = ar["primary_tx"] != r.get("primary_tx")
        else:
            pc = cls[r["primary_tx"]] if r.get("primary_tx") in cls else (atk[0] if atk else mine[0])
            if r.get("primary_tx") and r["status"] != "no-mainnet-tx":
                r2["listed_tx_measures_not_attacker"] = {k_: r2.get(k_) for k_ in ("primary_tx", "tx_index", "attacker_eoa", "exposure", "techniques", "outcome")}
                for k_ in ("tx_index", "attacker_eoa", "exposure", "techniques"):
                    r2[k_] = NOT_MEASURED
                r2["status"] = "not-measured"
            else:
                r2["status"] = r["status"]
            r2["attacker_side_status"] = ("not measured: the only listed attack tx(s) were sent by " + "/".join(sorted(kind_set or {"non-attack senders"})) +
                                          "; no attacker-class tx is listed (a bot-run exploit, or a copy/race of an attacker tx the DHL PoC does not list)")
            r2["primary_changed_vs_v1"] = False
        r2["sender_class"] = pc["sender_class"]
        r2["sender_class_confidence"] = pc["confidence"]
        r2["sender_class_evidence"] = pc["evidence"]
        r2["sender_label"] = pc["label"]
        r2["sender_class_facts"] = pc["facts"]
        v2.append(r2)

    v2_ok = [r for r in v2 if r.get("v1_status") == "ok"]
    # ---------------- aggregation populations
    att_pop = [r for r in v2 if r["status"] == "ok" and r["attacker_side_status"] == "measured"]
    sen_pop = [r for r in v2 if r["status"] == "ok" and (r["attacker_side_status"] == "measured" or str(r["attacker_side_status"]).startswith("sender unknown"))]
    # rows for aggregation must carry era/year/etc from the measured fields -> they do (merged above)
    # ---------------- bot side
    bots_recs = []
    for e in exploits:
        rid = e["file"]
        if rid in dup_ids or not B[rid] and not any(not cls[h]["measured"] for h in members[rid]):
            continue
        br = bot_rows_full.get(rid)
        if br and br.get("status") == "ok":
            h = br["primary_tx"]
            c, rec, feat, t = cls[h], txs[h], traces.get(h), br["techniques"]
            infl = eth_inflow_proxy(feat, rec) if feat else None
            b = t.get("coinbase_bribe_eth", 0.0)
            bots_recs.append({"id": rid, "name": br["name"], "date": br["date"], "era": br["era"], "year": br["year"], "block_ts": br["block_ts"], "measured": True,
                              "bot": c["label"] or c["facts"]["sender"], "bot_address": c["facts"]["sender"], "bot_confidence": c["confidence"], "tx": h,
                              "block": br["block"], "tx_index": br["tx_index"], "tip_gwei": t["tip_gwei"], "bribe_eth": b,
                              "eth_inflow_proxy": None if infl is None else round(infl, 4),
                              "bribe_share_of_eth_inflow": (round(b / infl, 4) if infl and b > 0 else None),
                              "exposure": br["exposure"]["label"], "exposure_confidence": br["exposure"]["confidence"], "exposure_method": br["exposure"]["method"],
                              "constructor": bool(t.get("constructor_exploit")), "internal_create": bool(t.get("internal_create_exploit")),
                              "flashloan": bool(t.get("uses_flashloan")), "n_bot_txs": len(B[rid]),
                              "attacker_tx_also_listed": bool(A[rid]), "v1_primary_was_bot_tx": r_primary_is(v1_by_id[rid], B[rid])})
        else:
            for x in (cls[h] for h in dict.fromkeys(members[rid])):
                if not x["measured"]:
                    d = e["date"]
                    bl = x["block"]
                    year = int(str(d)[:4])
                    era = "E1 pre-2021 (public mempool)" if year < 2021 else "E2 2021-Sep2022 (MEV-geth bundles)" if bl < MERGE_BLOCK else "E3 Sep2022-2023 (early PBS)" if year < 2024 else "E4 2024-2026 (mature PBS / private flow)"
                    bots_recs.append({"id": rid, "name": e["name"], "date": d, "era": era, "year": year, "measured": False, "bot": "c0ffeebabe.eth",
                                      "bot_address": x["facts"]["sender"], "bot_confidence": "high", "tx": x["hash"], "block": bl, "tx_index": x["index"],
                                      "attacker_tx_also_listed": bool(A[rid]), "v1_primary_was_bot_tx": False,
                                      "note": "sender match only; tx not fetched or traced (publication policy)"})
    bot_side = {"definition": DEFS_V2["bot_side"], "records": bots_recs, "overall": agg_bot(bots_recs),
                "by_era": {k_: agg_bot(v) for k_, v in sorted(group_recs(bots_recs, "era").items())},
                "by_year": {k_: agg_bot(v) for k_, v in sorted(group_recs(bots_recs, "year").items())},
                "by_bot": {k_: agg_bot(v) for k_, v in sorted(group_recs(bots_recs, "bot").items(), key=lambda kv: -len(kv[1]))},
                "large_bribes_ge_5_eth": sorted([{"name": r["name"], "bot": r["bot"], "bribe_eth": r["bribe_eth"], "eth_inflow_proxy": r["eth_inflow_proxy"],
                                                  "bribe_share_of_eth_inflow": r["bribe_share_of_eth_inflow"]} for r in bots_recs if r["measured"] and r["bribe_eth"] >= 5],
                                               key=lambda x: -x["bribe_eth"]),
                "bribe_share_note": DEFS_V2["bribe_share_of_eth_inflow"]}
    return dict(v1=v1, v2=v2, cls=cls, members=members, reg=reg, A=A, U=U, B=B, W=W, att_pop=att_pop, sen_pop=sen_pop, bot_side=bot_side, reproduced=reproduced,
                dup_ids=dup_ids, hits_src=hits_src, v1_by_id=v1_by_id, att_rows=att_rows, sen_rows=sen_rows, bot_rows_full=bot_rows_full, wh_rows=wh_rows, exploits=exploits)


def r_primary_is(v1row, hashes):
    return bool(v1row.get("primary_tx") and v1row["primary_tx"] in hashes)


def group_recs(recs, key):
    g = collections.defaultdict(list)
    for r in recs:
        g[str(r[key]) if key == "year" else r[key]].append(r)
    return g


def stage_relabel_write(res):
    v1, v2, cls, reg = res["v1"], res["v2"], res["cls"], res["reg"]
    bot_side = res["bot_side"]
    att_pop, sen_pop = res["att_pop"], res["sen_pop"]
    v1_ok = [r for r in v1 if r["status"] == "ok"]
    v1_disk_by_era = jload(W_6 / "by_era.json")
    # ---------------- sender_class.json
    sc_rows = []
    for r in v2:
        txl = []
        for x in sorted((cls[h] for h in dict.fromkeys(res["members"][r["id"]])), key=lambda x: (x["block"] or 0, x["index"] or 0)):
            txl.append({"hash": x["hash"], "block": x["block"], "index": x["index"], "from": x["facts"]["sender"], "sender_class": x["sender_class"],
                        "confidence": x["confidence"], "tx_role": x["tx_role"], "label": x["label"], "evidence": x["evidence"],
                        "facts": {k_: v for k_, v in x["facts"].items() if k_ != "sender"}})
        sc_rows.append({"id": r["id"], "name": r["name"], "date": r["date"], "v1_status": r["v1_status"], "primary_tx": r.get("primary_tx"),
                        "from": (r.get("sender_class_facts") or {}).get("sender"), "sender_class": r["sender_class"],
                        "sender_class_confidence": r["sender_class_confidence"], "sender_class_evidence": r["sender_class_evidence"],
                        "sender_label": r.get("sender_label"), "row_kind": r["row_kind"], "attacker_side_status": r["attacker_side_status"],
                        "v1_primary_tx": r["v1_primary"]["tx"], "v1_primary_sender_class": r["v1_primary"]["sender_class"],
                        "v1_primary_tx_role": r["v1_primary"]["tx_role"], "txs": txl})
    jdump(W_6 / "sender_class.json", {"generated": now(), "definitions": {k_: DEFS_V2[k_] for k_ in ("sender_class", "rule_order", "mixed_rows")},
                                     "registry_size": len(reg), "pin_block_for_latest_nonce": PIN_BLOCK, "rows": sc_rows})
    # ---------------- per_exploit_v2.json
    jdump(W_6 / "per_exploit_v2.json", {"generated": now(), "n": len(v2), "definitions": DEFS_V2, "outcome_source": res["hits_src"], "exploits": v2})
    # ---------------- counts
    ok2 = [r for r in v2 if r["v1_status"] == "ok"]
    cnt_rowclass = collections.Counter(r["sender_class"] for r in ok2)
    cnt_kind = collections.Counter(r["row_kind"] for r in ok2)
    cnt_att = collections.Counter(("measured" if r["attacker_side_status"] == "measured" else "sender-unknown" if str(r["attacker_side_status"]).startswith("sender unknown") else "not-measured") for r in ok2)
    txc = collections.Counter(("non-attack" if x["tx_role"] != "attack" else x["sender_class"]) for x in cls.values())
    txc_unmeasured = sum(1 for x in cls.values() if not x["measured"])
    bots = collections.defaultdict(lambda: {"rows": [], "n_txs": 0, "rows_v1_primary": []})
    pairs = [(rid, cls[h]) for rid, hs in res["members"].items() for h in dict.fromkeys(hs) if rid not in res["dup_ids"]]
    for rid, x in pairs:
        if x["sender_class"] == "bot" and x["tx_role"] == "attack":
            b = bots[x["facts"]["sender"]]
            b["label"] = x["label"] or (reg.get(x["facts"]["sender"]) or {}).get("label")
            b["confidence"] = x["confidence"]
            b["rule"] = "registry" if x["facts"]["sender"] in reg else "heuristic " + (x["evidence"][0][:2])
            b["n_txs"] += 1
            nm = res["v1_by_id"][rid]["name"]
            if nm not in b["rows"]:
                b["rows"].append(nm)
            if res["v1_by_id"][rid].get("primary_tx") == x["hash"] and nm not in b["rows_v1_primary"]:
                b["rows_v1_primary"].append(nm)
    bots_out = sorted(({"address": a, **{k_: v for k_, v in b.items()}, "n_rows": len(b["rows"]), "n_rows_where_v1_primary_was_this_bot": len(b["rows_v1_primary"])}
                       for a, b in bots.items()), key=lambda x: (-x["n_rows"], x["address"]))
    wh = collections.defaultdict(lambda: {"rows": []})
    for rid, x in pairs:
        if x["sender_class"] == "whitehat" and x["tx_role"] == "attack":
            w = wh[x["facts"]["sender"]]
            w["label"] = x["label"]
            nm = res["v1_by_id"][rid]["name"]
            if nm not in w["rows"]:
                w["rows"].append(nm)
    non_attack = [{"name": res["v1_by_id"][rid]["name"], "tx": x["hash"], "why": x["evidence"][0]} for rid, x in pairs if x["tx_role"] != "attack"]
    counts = {"rows_in_v1_sample": len(v1_ok), "by_row_sender_class": dict(cnt_rowclass), "by_row_kind": dict(cnt_kind),
              "attacker_side": dict(cnt_att),
              "other_v1_rows": {"duplicate_listings_excluded": sum(1 for r in v2 if r["v1_status"] == "duplicate-primary-tx"),
                                "no_mainnet_tx": sum(1 for r in v2 if r["v1_status"] == "no-mainnet-tx"),
                                "of_which_only_a_c0ffeebabe_tx_listed": sum(1 for r in v2 if r["v1_status"] == "no-mainnet-tx" and r["row_kind"] == "bot-only")},
              "txs_by_class": dict(txc), "txs_not_fetched_c0ffeebabe": txc_unmeasured,
              "rows_whose_v1_primary_tx_was_not_attacker_class": sum(1 for r in ok2 if r["v1_primary"]["sender_class"] != "attacker" or r["v1_primary"]["tx_role"] != "attack"),
              "bots_relabelled": bots_out,
              "whitehats": [{"address": a, **w, "n_rows": len(w["rows"])} for a, w in wh.items()],
              "non_attack_txs": non_attack}
    # ---------------- tables
    att = table_block(att_pop)
    att["large_bribes_ge_5_eth"] = large_bribes(att_pop)
    sen = table_block(sen_pop)
    sen["large_bribes_ge_5_eth"] = large_bribes(sen_pop)
    # v1 reproduced
    v1_tab = {"overall": agg2(v1_ok), "by_era": {k_: agg2(v) for k_, v in group_by(v1, lambda r: r["era"]).items()},
              "by_year": {k_: agg2(v) for k_, v in group_by(v1, lambda r: str(r["year"])).items()},
              "by_half": {k_: agg2(v) for k_, v in group_by(v1, half_of).items()}}
    v1_check = all(v1_tab["overall"][k_] == v1_disk_by_era["overall"][k_] for k_ in v1_disk_by_era["overall"] if k_ != "n_exploits_total")
    vs = {}
    for scope, a1, a2 in ([("overall", v1_tab["overall"], att["overall"])] +
                          [(k_, v1_tab["by_era"].get(k_), att["by_era"].get(k_)) for k_ in v1_tab["by_era"]] +
                          [(k_, v1_tab["by_year"].get(k_), att["by_year"].get(k_)) for k_ in v1_tab["by_year"]] +
                          [(k_, v1_tab["by_half"].get(k_), att["by_half"].get(k_)) for k_ in v1_tab["by_half"]]):
        d = {}
        for m in V2_METRICS:
            x1, x2 = (a1 or {}).get(m), (a2 or {}).get(m)
            d[m] = {"v1": x1, "v2": x2, "delta": (round(x2 - x1, 3) if isinstance(x1, (int, float)) and isinstance(x2, (int, float)) else None)}
        vs[scope[:2] if scope.startswith("E") else scope] = d
    changes = []
    for r in ok2:
        v1p = r["v1_primary"]
        if r["attacker_side_status"] != "measured" or r.get("primary_changed_vs_v1") or v1p["sender_class"] != "attacker" or v1p["tx_role"] != "attack":
            v1r = res["v1_by_id"][r["id"]]
            t1 = v1r.get("techniques") or {}
            changes.append({"name": r["name"], "date": r["date"], "v1_primary_tx": v1p["tx"], "v1_primary_sender_class": v1p["sender_class"], "v1_primary_tx_role": v1p["tx_role"],
                            "v1_primary_sender_label": cls[v1p["tx"]]["label"] if v1p["tx"] in cls else None,
                            "v1_era": v1r.get("era", "")[:2], "v1_exposure": (v1r.get("exposure") or {}).get("label"), "v1_constructor": t1.get("constructor_exploit"),
                            "v1_bribe_eth": round(t1.get("coinbase_bribe_eth", 0), 3), "v1_tx_index": v1r.get("tx_index"),
                            "v2_attacker_side_status": r["attacker_side_status"], "v2_primary_tx": r.get("primary_tx") if r["status"] == "ok" else None,
                            "v2_sender_class": r["sender_class"], "v2_row_kind": r["row_kind"]})
    out = {"generated": now(), "definitions": DEFS_V2, "v1_reproduced_from_cached_data": res["reproduced"], "v1_overall_matches_by_era_json": v1_check,
           "sender_class_counts": counts, "attacker_only": att, "bot_side": bot_side,
           "v1_vs_v2": {"note": "scope -> metric -> {v1, v2 (attacker_only), delta}; v1 recomputed from per_exploit.json rows with the same functions", "scopes": vs},
           "sensitivity_incl_unknown": sen, "changed_rows": changes, "group_effects": group_effects(res), "v1_tables_recomputed": v1_tab}
    bot_side["bribe_share_of_gross_known_from_incidents"] = BOT_GROSS_FROM_INCIDENTS
    jdump(W_6 / "by_era_v2.json", out)
    return out



BOT_GROSS_FROM_INCIDENTS = [
    # name in per_exploit_v2, bribe (coinbase payment, ETH), gross basis, share, source.  Only values the incident files state or derive exactly.
    {"name": "makina", "bribe_eth": 1299.05, "gross": "1,299.18 ETH unwrapped WETH (bot net +0.13 ETH)", "share": 0.9999, "source": "incidents/makina-2026 bots[0].coinbase_share_of_gross"},
    {"name": "Paraswap", "bribe_eth": 6.4504, "gross": "6.4633 ETH proceeds", "share": 0.998, "source": "incidents/paraswap-2024 bribe_rule_check: msg.value 998/1000 per-mille"},
    {"name": "TIME", "bribe_eth": 4.9232, "gross": "89.513 ETH net profit", "share": 0.055, "source": "incidents/time-2023 bribe_rule_check: msg.value 55/1000 per-mille"},
    {"name": "SHOCO", "bribe_eth": 0.0921, "gross": "4.159 ETH gross", "share": 0.0221, "source": "incidents/shoco-2023 bots[0].bribe_share_of_gross_profit"},
    {"name": "Alkimiya_io", "bribe_eth": 50.834, "gross": "WBTC loot; ETH leg not decomposed", "share": None,
     "note": "builder refunded 48.278 ETH in the same block: effective bribe to the proposer 2.576 ETH (5.1% of the coinbase payment)", "source": "incidents/alkimiya-2025 bots[0]"},
    {"name": "DeFiPlaza", "bribe_eth": 66.318, "gross": "6 swept assets (~62.5k USD) plus the ETH the bribe was paid from; profit split not decomposed", "share": None, "source": "incidents/defiplaza-2024 bots[0].captured"},
    {"name": "RsETHSafeModule", "bribe_eth": 18.931, "gross": "2,900 rsETH out of the Safe (~7.7M USD); 17.63 rsETH sold to pay the bribe", "share": 0.0061, "note": "share = 17.63 / 2,900 rsETH, by token amount", "source": "incidents/kelp-rseth-2026 bots[0].captured"},
]


def group_of(cls_rec):
    """presentation group of a bot-class tx record"""
    a = cls_rec["facts"]["sender"]
    names = {"0xfde0d1575ed8e06fbf36256bcdfa1f359281455a": "Yoink", "0x935bfb495e33f74d2e9735df1da66ace442ede48": "Makina searcher 0x935b",
             "0xd215ffaf0f85fb6f93f11e49bd6175ad58af0dfd": "anonymous MEV bot 0xd215", "0x7248939f65bdd23aab9eaab1bc4a4f909567486e": "anonymous MEV bot A",
             "0xc9a5643ed8e4cd68d16fe779d378c0e8e7225a54": "arbitrage bot 0xc9a5643e"}
    if cls_rec["sender_class"] == "whitehat":
        return "whitehat (BlockSec)"
    if cls_rec["sender_class"] == "bot":
        if a in names:
            return names[a]
        return "other named bots/copiers" if cls_rec["confidence"] == "high" else "low-confidence bots (R1/R1b heuristics)"
    return "non-attack / unknown-sender"


def group_effects(res):
    """For every relabelled group: its v1 contribution and the effect of removing ONLY that group from the v1 sample."""
    v1_ok = [r for r in res["v1"] if r["status"] == "ok"]
    cls = res["cls"]
    groups = collections.defaultdict(list)
    for r in v1_ok:
        p = r.get("primary_tx")
        c = cls.get(p)
        if c and (c["sender_class"] != "attacker" or c["tx_role"] != "attack"):
            groups[group_of(c)].append(r)
    base = {"E3": agg2([r for r in v1_ok if r["era"].startswith("E3")]), "E4": agg2([r for r in v1_ok if r["era"].startswith("E4")]), "all": agg2(v1_ok)}
    out = []
    for g, rs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        names = {r["name"] for r in rs}
        rest = [r for r in v1_ok if r["name"] not in names]
        e3, e4, al = agg2([r for r in rest if r["era"].startswith("E3")]), agg2([r for r in rest if r["era"].startswith("E4")]), agg2(rest)
        bribes = [r["techniques"].get("coinbase_bribe_eth", 0) for r in rs]
        out.append({"group": g, "n_rows": len(rs), "rows": sorted(names), "eras": dict(collections.Counter(r["era"][:2] for r in rs)),
                    "v1_contribution": {"rows_with_coinbase_payment": sum(1 for b in bribes if b > 0), "coinbase_eth_sum": round(sum(bribes), 3),
                                        "tx_index_0": sum(1 for r in rs if r["tx_index"] == 0), "zero_tip": sum(1 for r in rs if r["techniques"]["tip_gwei"] == 0),
                                        "constructor": sum(1 for r in rs if r["techniques"].get("constructor_exploit")),
                                        "public": sum(1 for r in rs if r["exposure"]["label"] == "public"),
                                        "dumpster_private": sum(1 for r in rs if r["exposure"]["method"] == "mempool-dumpster" and r["exposure"]["label"] == "private-bundle")},
                    "effect_of_removing_only_this_group": {
                        "E3_coinbase_bribe_pct": [base["E3"]["coinbase_bribe_pct"], e3["coinbase_bribe_pct"]],
                        "E4_coinbase_bribe_pct": [base["E4"]["coinbase_bribe_pct"], e4["coinbase_bribe_pct"]],
                        "E4_tx_index_median": [base["E4"]["tx_index_median"], e4["tx_index_median"]],
                        "E4_tip_zero_pct": [base["E4"]["tip_zero_pct"], e4["tip_zero_pct"]],
                        "E4_constructor_pct": [base["E4"]["constructor_exploit_pct"], e4["constructor_exploit_pct"]],
                        "E4_origin_check_pct": [base["E4"]["origin_check_pct_of_attacker_contracts"], e4["origin_check_pct_of_attacker_contracts"]],
                        "dumpster_attacker_seen_pct": [base["all"]["dumpster_attacker_seen_pct"], al["dumpster_attacker_seen_pct"]]}})
    return out


def _p(x, d=1):
    return "n/a" if x is None else (f"{x:.{d}f}%" if x % 1 or d else f"{x:.0f}%")


def _pc(x):  # compact percent
    if x is None:
        return "n/a"
    return f"{x:.0f}%" if abs(x - round(x)) < 0.05 or x >= 10 else f"{x:.1f}%"


def _ci(a, key):
    w = a["wilson95_pct"].get(key)
    return f" [{w[0]:.0f}-{w[1]:.0f}]" if w else ""


def _dur(s):
    if s is None:
        return "n/a"
    if s < 120:
        return f"{s:.0f} s"
    if s < 7200:
        return f"{s / 60:.1f} min" if s < 3600 else f"{s / 3600:.1f} h"
    return f"{s / 3600:.1f} h"


def write_findings_v2(res, out):
    A = out["attacker_only"]
    S = out["sensitivity_incl_unknown"]
    B = out["bot_side"]
    C = out["sender_class_counts"]
    VS = out["v1_vs_v2"]["scopes"]
    GE = out["group_effects"]
    ov = A["overall"]
    eras = sorted(A["by_era"])
    E = {k[:2]: A["by_era"][k] for k in eras}
    Y = A["by_year"]
    H = A["by_half"]
    L = []
    w = L.append
    ncs = ov["counts"]["dumpster_attacker_seen_pct"]
    pub_names = sorted(r["name"] for r in res["att_pop"] if r["exposure"]["method"] == "mempool-dumpster" and r["exposure"]["label"] == "public")
    # BACKRUNNER window (Aug 2023 - May 2024) on the attacker-only population
    lim = dt.datetime(2024, 6, 1, tzinfo=dt.UTC).timestamp()
    win = [r for r in res["att_pop"] if r["exposure"]["method"] == "mempool-dumpster" and r["block_ts"] < lim]
    win_pub = sum(1 for r in win if r["exposure"]["label"] == "public")
    win_res = sum(1 for r in win if r["exposure"]["label"] in ("public", "private-bundle"))
    v1w = [r for r in res["v1"] if r.get("status") == "ok" and r["exposure"]["method"] == "mempool-dumpster" and r["block_ts"] < lim]
    v1w_pub = sum(1 for r in v1w if r["exposure"]["label"] == "public")
    v1w_res = sum(1 for r in v1w if r["exposure"]["label"] in ("public", "private-bundle"))
    cands = sorted(r["name"] for r in res["att_pop"] if (r.get("outcome") or {}).get("frontrun_candidate") == "yes")
    wlo = dt.datetime(2023, 1, 1, tzinfo=dt.UTC).timestamp()
    in_win = [r for r in res["att_pop"] if wlo <= r["block_ts"] < lim]
    nwin_all = len(in_win)
    cwin = sum(1 for r in in_win if (r.get("outcome") or {}).get("frontrun_candidate") == "yes")
    # control by half
    ctl = {k_: v["control_seen_pct"] for k_, v in A["dumpster_era_by_half"].items()}
    rv = {k_: v["relative_visibility"] for k_, v in A["dumpster_era_by_half"].items()}
    nbot = C["by_row_sender_class"].get("bot", 0)
    nmeas = C["attacker_side"].get("measured", 0)
    nunk = C["attacker_side"].get("sender-unknown", 0)
    nnm = C["attacker_side"].get("not-measured", 0)
    bo = B["overall"]

    w("evolution study v2: Has the dark forest evolved? (attacker-side longitudinal measurement, sender-class corrected)")
    w("")
    w(f"Generated {out['generated']} by scripts/evolution.py (stage: relabel).  Supersedes findings.txt for any attacker-side number; v1 files are kept unchanged.")
    w("Data: sender_class.json (class of every listed tx and of every exploit row, with evidence), per_exploit_v2.json (v1 rows + sender class; mixed rows measured on the")
    w("attacker's tx), by_era_v2.json (attacker_only, bot_side, v1_vs_v2, sensitivity_incl_unknown, group_effects, changed_rows).")
    w("")
    w("HEADLINE")
    w(f"The attacker-side trend survives the correction, and part of it gets sharper; the 'bribes and gas' half does not.  v1 mixed MEV bots, whitehats and")
    nout = nbot + C['by_row_sender_class'].get('whitehat', 0) + C['by_row_sender_class'].get('unknown', 0)
    w(f"non-attack txs into the attacker sample: of the 315 analysed exploit rows, {nout} had no attacker-sent tx at all and drop out ({nbot} bot-only rows, {C['by_row_sender_class'].get('whitehat', 0)} whitehat, {C['by_row_sender_class'].get('unknown', 0)} unknown-sender or non-attack)")
    w(f"({C['rows_whose_v1_primary_tx_was_not_attacker_class']} rows had a first listed tx that was not an attacker's: those {nout} plus {C['rows_whose_v1_primary_tx_was_not_attacker_class'] - nout} mixed row whose first tx was a bot's but which also lists an attacker tx, so it stays and is measured on that tx).  The corrected attacker sample has {nmeas} rows")
    w(f"({nmeas + nunk} counting {nunk} unknown-sender rows in the sensitivity run).")
    w(f"Visibility: since Aug 2023 {ncs['k']} of {ncs['n']} resolved attacker txs ({_pc(ov['dumpster_attacker_seen_pct'])}, 95% {ov['wilson95_pct']['dumpster_attacker_seen_pct'][0]:.1f}-{ov['wilson95_pct']['dumpster_attacker_seen_pct'][1]:.1f}%) were seen in the public mempool, against")
    w(f"{_pc(ov['dumpster_control_seen_pct'])} of ordinary txs in the same blocks (86% in 2023 H2, 48-59% in 2025-26): attackers are about {1 / ov['dumpster_relative_visibility']:.0f}x less visible than their neighbours (v1: 4.4%).")
    w(f"Mechanics: constructor-only exploits {_pc(E['E1']['constructor_exploit_pct'])} (E1) -> {_pc(E['E2']['constructor_exploit_pct'])} (E2) -> {_pc(E['E3']['constructor_exploit_pct'])} (E3) -> {_pc(E['E4']['constructor_exploit_pct'])} (E4);"
      f" {_pc(Y['2024']['constructor_exploit_pct'])} (2024) -> {_pc(Y['2025']['constructor_exploit_pct'])} (2025) -> {_pc(Y['2026']['constructor_exploit_pct'])} (2026 YTD).  Median fresh deploy-to-attack gap {_dur(E['E1']['deploy_gap_s_median_fresh_le7d'])}/{_dur(E['E2']['deploy_gap_s_median_fresh_le7d'])} (E1/E2) -> {_dur(E['E3']['deploy_gap_s_median_fresh_le7d'])} -> {_dur(E['E4']['deploy_gap_s_median_fresh_le7d'])};")
    w(f"{_pc(Y['2025']['no_watchable_window_pct'])} of 2025 exploits left a bot no watchable window (v1: 71%).")
    w(f"What does NOT survive: the 'attackers bribe builders' story.  Attacker coinbase payments are {_pc(E['E3']['coinbase_bribe_pct'])} (E3) and {_pc(E['E4']['coinbase_bribe_pct'])} (E4), not 11% and 16%, with no rise from 2023 to 2024;")
    w(f"the big payments (Makina 1,299 ETH, DeFiPlaza 66, Alkimiya 51, Kelp 19, Earning.Farm 19, NUM 10) were MEV bots paying builders.  The median tx index no longer falls monotonically")
    w(f"(E3 {E['E3']['tx_index_median']:g}, E4 {E['E4']['tx_index_median']:g}; 2024 {Y['2024']['tx_index_median']:g} vs 2025 {Y['2025']['tx_index_median']:g}), because the top-of-block rows were bots.")
    w("Limit unchanged: exposure cannot be measured directly before 2023-08-07; before that date it is 'in-block evidence only'.")
    w("")
    w("SAMPLE")
    w("DeFiHackLabs mainnet entries: 365. 320 have a resolvable mainnet tx, 5 are duplicate listings (excluded) -> 315 analysed in v1.  9 entries list a tx sent by c0ffeebabe.eth:")
    w("those txs were never fetched or traced (publication policy) and are classed bot from the DHL sender alone: BiFi, SecuredFi, DRLVaultV3, AnyswapWETHPermit, BlueberryProtocol,")
    w(f"SwarmMarkets, WiseLending, ERC20TokenBank, Sushi_Router (8 of them have no other listed tx, so they are outside the 315; BiFi's listed attacker deploy tx stays in the attacker sample).")
    w(f"Sender classes (tx level, attack-role): attacker {C['txs_by_class'].get('attacker', 0)}, bot {C['txs_by_class'].get('bot', 0)} (incl. 9 c0ffeebabe), whitehat {C['txs_by_class'].get('whitehat', 0)}, unknown {C['txs_by_class'].get('unknown', 0)}; non-attack hashes {C['txs_by_class'].get('non-attack', 0)}.")
    w(f"Row level (315): attacker {C['by_row_sender_class'].get('attacker', 0)}, bot {nbot}, whitehat {C['by_row_sender_class'].get('whitehat', 0)}, unknown {C['by_row_sender_class'].get('unknown', 0)};  row kinds: {', '.join(f'{k} {v}' for k, v in sorted(C['by_row_kind'].items()))}.")
    w(f"Attacker side: measured {nmeas}; sender-unknown {nunk} (kept out of attacker_only, added back in sensitivity_incl_unknown); not measured {nnm} (only a bot / whitehat / non-attack tx is listed).")
    w("Mixed rows (an attacker tx AND a bot tx listed, e.g. EFLeverVault): the attacker's tx drives every attacker-side number and the bot's tx goes to the bot-side table.  A bot tx never")
    w("substitutes for an unlisted attacker tx: those rows are 'not measured' and drop out of attacker aggregates.  Doing it this way costs sample size but cannot manufacture attacker behaviour.")
    w("")
    w("Relabelled bots (rows = DHL exploit rows whose listed tx was sent by them):")
    for b in C["bots_relabelled"]:
        w(f"  {b['label'] or b['address']:<40} {b['address'][:12]}  rows {b['n_rows']:>2}  conf {b['confidence']:<6} {b['rule']}")
    for x in C["whitehats"]:
        w(f"  whitehat: {x['label']} {x['address'][:12]}  rows {x['n_rows']}: {', '.join(x['rows'])}")
    w("")
    w("WHAT CHANGED VS v1 (named row groups and their effect; 'alone' = remove only that group from the v1 sample)")
    for g in GE:
        ef = g["effect_of_removing_only_this_group"]
        vc = g["v1_contribution"]
        w(f"- {g['group']}: {g['n_rows']} rows ({', '.join(f'{k} {v}' for k, v in sorted(g['eras'].items()))}): {', '.join(g['rows'][:14])}{' ...' if len(g['rows']) > 14 else ''}")
        w(f"    v1 counted: {vc['rows_with_coinbase_payment']} coinbase payments totalling {vc['coinbase_eth_sum']:g} ETH, {vc['tx_index_0']} at tx index 0, {vc['zero_tip']} zero-tip, {vc['constructor']} constructor, {vc['public']} public, {vc['dumpster_private']} dumpster-private.")
        w(f"    alone: E3 bribe share {ef['E3_coinbase_bribe_pct'][0]}% -> {ef['E3_coinbase_bribe_pct'][1]}%; E4 bribe share {ef['E4_coinbase_bribe_pct'][0]}% -> {ef['E4_coinbase_bribe_pct'][1]}%; E4 median tx index {ef['E4_tx_index_median'][0]:g} -> {ef['E4_tx_index_median'][1]:g}; E4 zero-tip {ef['E4_tip_zero_pct'][0]}% -> {ef['E4_tip_zero_pct'][1]}%; E4 constructor {ef['E4_constructor_pct'][0]}% -> {ef['E4_constructor_pct'][1]}%; seen-in-mempool {ef['dumpster_attacker_seen_pct'][0]}% -> {ef['dumpster_attacker_seen_pct'][1]}%")
    w("Named cases:")
    w("- Makina (1,299.05 ETH 'bribe', Jan 2026): sent by MEV searcher 0x935b (Makina post-mortem); the coinbase payment was 99.99% of its 1,299.18 ETH gross (bot net +0.13 ETH).  Row is bot-only: the exploiter's own tx is not in the DHL listing, so")
    w("  the row is 'not measured' and leaves E4.  It was the single largest 'attacker bribe' in v1 and is now a bot-side number.")
    w("- Hopelend (263.9 ETH, Oct 2023): STAYS attacker (sender is the DHL-listed attacker, a fresh account with 51 prior txs, tx index 0).  Confidence medium: a 264 ETH payment at index 0 is a")
    w("  searcher-shaped tx, but nothing identifies the sender as a bot, and the attacker could have bought builder priority like a bot does.  If it were a bot it would drop out as well.")
    w("- DeFiPlaza (66.3 ETH, Jul 2024): Yoink's tx (fixed 66.3 ETH bribe paid out of the ETH proceeds).  Bot-side.")
    w("- Anyswap (33.95 ETH, Jan 2022): STAYS attacker, confidence LOW (DHL-listed attacker, 73 prior txs, index 0, zero tip; no incident file).  It is the only E2 coinbase payer, so E2's 'bribe share' is 1 of 22.")
    w("- Ambient (33.9 ETH, Jun 2026): stays attacker, low confidence (DHL-listed attacker, but it did not deploy the attack contract; vanity-prefix address, 14 prior txs, tx index 1); ResupplyFi 10 ETH and GFOX 8.9 ETH stay.")
    w("- Large attacker-side coinbase payments now: " + "; ".join(f"{x['name']} {x['bribe_eth']:g} ETH ({x['confidence']})" for x in A["large_bribes_ge_5_eth"]) + ".")
    w("- Rows moved to unknown-sender (sensitivity only): " + ", ".join(sorted(r["name"] for r in res["v2"] if str(r.get("attacker_side_status", "")).startswith("sender unknown"))) + ".  coinbase: v1's 'primary' was a third-party approve;")
    w("  the listed attacker tx is kept but its account has 3,493 prior txs, so it is unknown rather than attacker.  Nomad's v1 primary was the protocol's own initialize call; Akutar's was a refund batch.")
    w("")
    w("RESULTS BY ERA, attacker-only (95% Wilson intervals in brackets; 'fresh' gap = attacker-owned contract deployed <= 7 days before the attack)")
    w("")
    cols = ["E1", "E2", "E3", "E4"]

    def line(lbl, f, width=26):
        w(f"{lbl:<42}" + "".join(f"{f(E[c]):<{width}}" for c in cols))

    def cell_pub(a):
        k = a["counts"]["dumpster_attacker_seen_pct"]
        return f"{_pc(a['dumpster_attacker_seen_pct'])}{_ci(a, 'dumpster_attacker_seen_pct')} ({k['k']}/{k['n']})" if k["n"] else "n/a"
    w(f"{'Metric':<42}" + "".join(f"{c:<26}" for c in cols))
    line("Exploits analysed (attacker-only)", lambda a: f"{a['n_with_mainnet_tx_and_trace']}")
    w(f"{'  v1 n (all senders)':<42}" + "".join(f"{VS[c]['n_with_mainnet_tx_and_trace']['v1']:<26}" for c in cols))
    line("Measured (dumpster) exploits", lambda a: f"{a['dumpster_era_n']}")
    line("Public share of measured", cell_pub)
    line("Same-block neighbours seen (control)", lambda a: _pc(a["dumpster_control_seen_pct"]) if a["dumpster_control_seen_pct"] is not None else "n/a")
    line("Pre-Aug-2023 labels (public|private|unk)", lambda a: f"{a['pre_aug2023_labels'].get('public', 0)}|{a['pre_aug2023_labels'].get('private-bundle', 0)}|{a['pre_aug2023_labels'].get('unknown', 0)}")
    line("Constructor exploit", lambda a: f"{_pc(a['constructor_exploit_pct'])}{_ci(a, 'constructor_exploit_pct')}")
    line("Constructor or internal CREATE", lambda a: f"{_pc(a['same_tx_deploy_and_attack_pct'])}{_ci(a, 'same_tx_deploy_and_attack_pct')}")
    line("No watchable window", lambda a: f"{_pc(a['no_watchable_window_pct'])}{_ci(a, 'no_watchable_window_pct')}")
    line("Median fresh deploy->attack gap (n)", lambda a: f"{_dur(a['deploy_gap_s_median_fresh_le7d'])} (n={a['deploy_gap_n']})")
    line("Deploy in same block as attack", lambda a: _pc(a["deploy_gap_same_block_pct"]) if a["deploy_gap_same_block_pct"] is not None else "n/a")
    line("ORIGIN-opcode check (lower bound, n own)", lambda a: f"{_pc(a['origin_check_pct_of_attacker_contracts'])} ({a['own_contract_attacks_n']})")
    line("Any sender guard", lambda a: _pc(a["sender_guard_pct_of_attacker_contracts"]))
    line("Attack contract unverified", lambda a: _pc(a["unverified_pct_of_attacker_contracts"]))
    line("Coinbase bribe inside the tx", lambda a: f"{_pc(a['coinbase_bribe_pct'])}{_ci(a, 'coinbase_bribe_pct')}")
    line("Zero priority fee but included", lambda a: _pc(a["tip_zero_pct"]))
    line("Median priority fee (gwei)", lambda a: f"{a['tip_gwei_median']:.2f}" if a["tip_gwei_median"] < 10 else f"{a['tip_gwei_median']:.0f}")
    line("Median tx index in block", lambda a: f"{a['tx_index_median']:g}")
    line("Tx index 0", lambda a: _pc(a["tx_index_0_pct"]))
    line("Flash loan used", lambda a: _pc(a["flashloan_pct"]))
    line("3+ attack txs listed", lambda a: _pc(a["multi_tx_ge3_pct"]))
    line("chain scan copycat candidates (medium/strong)", lambda a: f"{a['frontrun_candidates_n']}/{a['frontrun_scanned_n']}")
    w("v1 -> v2 for the same cells (v1 / v2): constructor E4 " + f"{VS['E4']['constructor_exploit_pct']['v1']}% / {VS['E4']['constructor_exploit_pct']['v2']}%; bribe E3 {VS['E3']['coinbase_bribe_pct']['v1']}% / {VS['E3']['coinbase_bribe_pct']['v2']}%, E4 {VS['E4']['coinbase_bribe_pct']['v1']}% / {VS['E4']['coinbase_bribe_pct']['v2']}%;")
    w(f"  tx index E4 {VS['E4']['tx_index_median']['v1']:g} / {VS['E4']['tx_index_median']['v2']:g}; zero-tip E4 {VS['E4']['tip_zero_pct']['v1']}% / {VS['E4']['tip_zero_pct']['v2']}%; ORIGIN check E4 {VS['E4']['origin_check_pct_of_attacker_contracts']['v1']}% / {VS['E4']['origin_check_pct_of_attacker_contracts']['v2']}%; gap E2 {_dur(VS['E2']['deploy_gap_s_median_fresh_le7d']['v1'])} / {_dur(VS['E2']['deploy_gap_s_median_fresh_le7d']['v2'])}.")
    w("")
    w("BY YEAR, attacker-only")
    w(f"{'Year':<6}{'n':<5}{'Constructor':<18}{'No watchable window':<24}{'Public share (dumpster era)':<34}{'Median fresh gap':<18}{'Bribe':<8}{'Median tip':<11}{'Median idx'}")
    for y in ("2020", "2021", "2022", "2023", "2024", "2025", "2026"):
        a = Y[y]
        k = a["counts"]["dumpster_attacker_seen_pct"]
        pub = f"{_pc(a['dumpster_attacker_seen_pct'])}{_ci(a, 'dumpster_attacker_seen_pct')} ({k['k']}/{k['n']})" if k["n"] else "n/a"
        w(f"{y:<6}{a['n_with_mainnet_tx_and_trace']:<5}{_pc(a['constructor_exploit_pct']) + _ci(a, 'constructor_exploit_pct'):<18}{_pc(a['no_watchable_window_pct']) + _ci(a, 'no_watchable_window_pct'):<24}{pub:<34}{_dur(a['deploy_gap_s_median_fresh_le7d']) + ' (n=' + str(a['deploy_gap_n']) + ')':<18}{_pc(a['coinbase_bribe_pct']):<8}{a['tip_gwei_median']:<11.2f}{a['tx_index_median']:g}")
    w("No watchable window = constructor, internal CREATE/CREATE2 that attacks, or attack contract deployed in the same block as the attack.")
    w("Half-years, constructor share: " + ", ".join(f"{k_} {_pc(v['constructor_exploit_pct'])} [{v['wilson95_pct']['constructor_exploit_pct'][0]:.0f}-{v['wilson95_pct']['constructor_exploit_pct'][1]:.0f}] (n={v['n_with_mainnet_tx_and_trace']})" for k_, v in H.items() if k_ >= "2024"))
    w("Dumpster-era exposure by half-year (attacker seen / resolved vs ordinary txs seen): " + "; ".join(f"{k_} {v['public']}/{v['public'] + v['private_bundle']} vs {v['control_seen_pct']}%" for k_, v in A["dumpster_era_by_half"].items()))
    w("")
    w("BOT SIDE (rows whose listed tx was sent by an MEV bot / copier / front-runner; c0ffeebabe rows carry block and index only)")
    w(f"Rows: {bo['n_rows']} ({bo['n_measured']} traced + {bo['n_not_measured_actions_only']} c0ffeebabe by sender match).  By era: " + ", ".join(f"{k_[:2]} {v['n_rows']}" for k_, v in B["by_era"].items()) + ".  By bot: " + ", ".join(f"{k_} {v['n_rows']}" for k_, v in list(B["by_bot"].items())[:8]) + ", others 1 each.")
    w(f"Tx index 0: {bo['tx_index_0_n']} of {bo['n_rows']} ({_pc(bo['tx_index_0_pct'])}, 95% {bo['tx_index_0_wilson95'][0]:.0f}-{bo['tx_index_0_wilson95'][1]:.0f}%); attacker-only: {_pc(ov['tx_index_0_pct'])}.")
    w(f"Coinbase payment: {bo['bribe_paid_n']} of {bo['n_measured']} traced bot txs ({_pc(bo['bribe_paid_pct_of_measured'])}, 95% {bo['bribe_paid_wilson95'][0]:.0f}-{bo['bribe_paid_wilson95'][1]:.0f}%), total {bo['bribe_eth_total']:g} ETH, median when paid {bo['bribe_eth_median_when_paid']:.2f} ETH, max {bo['bribe_eth_max']:.0f} ETH (Makina);")
    w(f"  attacker-only: {_pc(ov['coinbase_bribe_pct'])}, median when paid {ov['coinbase_bribe_eth_median_when_paid']:.2f} ETH.  Zero priority fee: {_pc(bo['tip_zero_pct_of_measured'])} of traced bot txs (attackers {_pc(ov['tip_zero_pct'])}); median tip {bo['tip_gwei_median']:g} gwei.")
    w("  Bribe as a share of gross, only where an incident file states or derives gross: " + "; ".join((f"{x['name']} {100 * x['share']:.2f}%" if x["share"] > 0.99 else f"{x['name']} {100 * x['share']:.1f}%") if x["share"] is not None else f"{x['name']} (gross not decomposed)" for x in BOT_GROSS_FROM_INCIDENTS) + ".")
    w("  Yoink's bribe is a per-mille of msg.value chosen by the sender (Paraswap 998/1000, TIME 55/1000), i.e. a setting, not a bid.  Alkimiya: the Yoink-affiliated builder refunded 48.28 of the 50.83 ETH in the same block, so the effective bribe was 2.58 ETH.")
    w("  A generic ETH-inflow ratio is also stored per bot row (bot_side.records[].bribe_share_of_eth_inflow) but it is unreliable when the loot is not ETH (Alkimiya WBTC, Kelp rsETH) and for wrapped flash principal; do not quote it.")
    w(f"Exposure (traced, dumpster era {bo['dumpster_era_n']}): {bo['dumpster_public_n']} public, {bo['dumpster_private_n']} not seen before inclusion; no bot tx used a constructor ({bo['constructor_n']}), {bo['internal_create_n']} internal CREATE; flash loan {_pc(bo['flashloan_pct'])}.")
    w("Bot rows by era: E3 " + str(B["by_era"][[k_ for k_ in B["by_era"] if k_.startswith("E3")][0]]["n_rows"]) + ", E4 " + str(B["by_era"][[k_ for k_ in B["by_era"] if k_.startswith("E4")][0]]["n_rows"]) + ", none before Sep 2022: these are DHL rows that are bot txs, not a count of bot activity (DHL does not list bots; selection is by which txs happened to be in a PoC header).")
    w("")
    w("STRONGEST EVIDENCE OF EVOLUTION (v1's seven points, re-checked)")
    cs = ov["counts"]["dumpster_attacker_seen_pct"]
    w(f"1. Visibility gap -- HOLDS.  Attacker txs seen in the public mempool before inclusion: {cs['k']} of {cs['n']} ({_pc(ov['dumpster_attacker_seen_pct'])}; v1 10 of 227) vs {_pc(ctl['2023H2'])} of")
    w(f"   neighbouring txs in 2023 H2 and {_pc(ctl['2025H2'])}/{_pc(ctl['2026H1'])}/{_pc(ctl['2026H2'])} in 2025 H2/2026.  The {len(pub_names)} public ones: {', '.join(pub_names)}; seen a median {ov['public_lead_time_s_median']:.1f} s before the block timestamp (n={ov['public_lead_time_s_n']}).")
    w("   By half-year attacker public/resolved: " + ", ".join(f"{k_} {v['public']}/{v['public'] + v['private_bundle']}" for k_, v in A["dumpster_era_by_half"].items()) + ".  The bot rows removed were all private, so the shift is small; the control comparison is unchanged.")
    w(f"2. Constructor shift -- HOLDS, a little stronger.  {_pc(E['E1']['constructor_exploit_pct'])} (2020-21), {_pc(Y['2022']['constructor_exploit_pct'])} (2022), {_pc(Y['2023']['constructor_exploit_pct'])} (2023), {_pc(Y['2024']['constructor_exploit_pct'])} (2024), {_pc(H['2025H1']['constructor_exploit_pct'])} (2025H1), {_pc(H['2025H2']['constructor_exploit_pct'])} (2025H2), {_pc(H['2026H1']['constructor_exploit_pct'])}/{_pc(H['2026H2']['constructor_exploit_pct'])} (2026H1/H2).  The 2024 -> 2025 jump is outside the intervals ({Y['2024']['wilson95_pct']['constructor_exploit_pct']} vs {Y['2025']['wilson95_pct']['constructor_exploit_pct']}).  No bot row was a constructor exploit, so removing bots raises the share.")
    w(f"3. The window closes -- HOLDS.  Median fresh gap: {_dur(E['E1']['deploy_gap_s_median_fresh_le7d'])}/{_dur(E['E2']['deploy_gap_s_median_fresh_le7d'])} (E1/E2) -> {_dur(E['E3']['deploy_gap_s_median_fresh_le7d'])} (E3) -> {_dur(Y['2025']['deploy_gap_s_median_fresh_le7d'])} (2025, n={Y['2025']['deploy_gap_n']}) -> {_dur(Y['2026']['deploy_gap_s_median_fresh_le7d'])} (2026, n={Y['2026']['deploy_gap_n']}).")
    w(f"   Same-block deploy {_pc(Y['2025']['deploy_gap_same_block_pct'])} of own-contract attacks in 2025 and {_pc(Y['2026']['deploy_gap_same_block_pct'])} in 2026.  The E2 median rose from 23 to {_dur(E['E2']['deploy_gap_s_median_fresh_le7d'])} because Nomad's copycat drains left the sample; E1/E2 are tiny.")
    w(f"4. Gas competition stopped -- PARTLY HOLDS.  Median priority fee {Y['2021']['tip_gwei_median']:.0f} gwei (2021) -> {Y['2023']['tip_gwei_median']:.1f} (2023) -> {Y['2024']['tip_gwei_median']:.2f} (2024) -> {Y['2025']['tip_gwei_median']:.2f} (2025) -> {Y['2026']['tip_gwei_median']:.2f} (2026), still falling, but ordinary tips fell too.")
    w(f"   The tx-index half does NOT hold: median index {E['E2']['tx_index_median']:g} (E2), {E['E3']['tx_index_median']:g} (E3), {E['E4']['tx_index_median']:g} (E4); by year 2022 {Y['2022']['tx_index_median']:g}, 2023 {Y['2023']['tx_index_median']:g}, 2024 {Y['2024']['tx_index_median']:g}, 2025 {Y['2025']['tx_index_median']:g}, 2026 {Y['2026']['tx_index_median']:g}")
    w(f"   (v1 E4 8.5): bots were the ones sitting at index 0.  Zero-tip-included is {_pc(E['E4']['tip_zero_pct'])} of E4 attackers (v1 10.5%): it was a bot signature.")
    w(f"5. Bribes appear -- DOES NOT HOLD as an attacker trend.  Attacker coinbase payments: {_pc(E['E1']['coinbase_bribe_pct'])} (E1), {_pc(E['E2']['coinbase_bribe_pct'])} (E2, 1 row), {_pc(E['E3']['coinbase_bribe_pct'])} (E3), {_pc(E['E4']['coinbase_bribe_pct'])} (E4); by year 2022 {_pc(Y['2022']['coinbase_bribe_pct'])}, 2023 {_pc(Y['2023']['coinbase_bribe_pct'])}, 2024 {_pc(Y['2024']['coinbase_bribe_pct'])}, 2025 {_pc(Y['2025']['coinbase_bribe_pct'])}, 2026 {_pc(Y['2026']['coinbase_bribe_pct'])}.")
    w(f"   Intervals overlap everywhere (E3 {E['E3']['wilson95_pct']['coinbase_bribe_pct']}, E4 {E['E4']['wilson95_pct']['coinbase_bribe_pct']}).  Hopelend 264 ETH and Anyswap 34 ETH stay; Makina, DeFiPlaza and the rest are bot payments.  A mild rise in 2025-26 (10-12%) is within noise.")
    w(f"6. What did not change -- HOLDS, cleaner.  Flash loan {_pc(E['E3']['flashloan_pct'])} (E3) / {_pc(E['E4']['flashloan_pct'])} (E4) / by year {', '.join(_pc(Y[y]['flashloan_pct']) for y in ('2022', '2023', '2024', '2025', '2026'))}; unverified attack contracts {_pc(E['E3']['unverified_pct_of_attacker_contracts'])}-{_pc(E['E4']['unverified_pct_of_attacker_contracts'])}.")
    w(f"   ORIGIN check: v1 showed a rise to {VS['E4']['origin_check_pct_of_attacker_contracts']['v1']}% in E4; attacker-only it is {_pc(E['E1']['origin_check_pct_of_attacker_contracts'])}/{_pc(E['E2']['origin_check_pct_of_attacker_contracts'])}/{_pc(E['E3']['origin_check_pct_of_attacker_contracts'])}/{_pc(E['E4']['origin_check_pct_of_attacker_contracts'])} (E1-E4): the bot contracts carried the guard.")
    w(f"7. chain scan copycat candidates -- HOLDS (still no resolvable trend).  {E['E2']['frontrun_candidates_n']}/{E['E2']['frontrun_scanned_n']} (E2), {E['E3']['frontrun_candidates_n']}/{E['E3']['frontrun_scanned_n']} (E3), {E['E4']['frontrun_candidates_n']}/{E['E4']['frontrun_scanned_n']} (E4): {', '.join(cands)}.  Nomad (E2) and RsETHSafeModule dropped out of the")
    w("   attacker sample (unknown-sender and bot-only rows); candidates are candidates, not confirmations.")
    w("")
    w("HEADLINE NUMBERS, v1 -> v2 (attacker-only)")
    def vv(sc, m, f=lambda x: x):
        x = VS[sc][m]
        return f"{f(x['v1'])} -> {f(x['v2'])}"
    pc1 = lambda x: "n/a" if x is None else f"{x:.1f}%"
    w("  Constructor share        E1 " + vv("E1", "constructor_exploit_pct", pc1) + ";  E2 " + vv("E2", "constructor_exploit_pct", pc1) + ";  E3 " + vv("E3", "constructor_exploit_pct", pc1) + ";  E4 " + vv("E4", "constructor_exploit_pct", pc1))
    w("                           2024 " + vv("2024", "constructor_exploit_pct", pc1) + ";  2025 " + vv("2025", "constructor_exploit_pct", pc1) + ";  2026 " + vv("2026", "constructor_exploit_pct", pc1))
    w("  No watchable window      2025 " + vv("2025", "no_watchable_window_pct", pc1) + ";  2026 " + vv("2026", "no_watchable_window_pct", pc1))
    w("  Median fresh gap         E1 " + vv("E1", "deploy_gap_s_median_fresh_le7d", _dur) + ";  E2 " + vv("E2", "deploy_gap_s_median_fresh_le7d", _dur) + ";  E3 " + vv("E3", "deploy_gap_s_median_fresh_le7d", _dur) + ";  E4 " + vv("E4", "deploy_gap_s_median_fresh_le7d", _dur) + ";  2025 " + vv("2025", "deploy_gap_s_median_fresh_le7d", _dur) + ";  2026 " + vv("2026", "deploy_gap_s_median_fresh_le7d", _dur))
    w("  Same-block deploy        2025 " + vv("2025", "deploy_gap_same_block_pct", pc1) + ";  2026 " + vv("2026", "deploy_gap_same_block_pct", pc1))
    w("  Coinbase bribe share     overall " + vv("overall", "coinbase_bribe_pct", pc1) + ";  E3 " + vv("E3", "coinbase_bribe_pct", pc1) + ";  E4 " + vv("E4", "coinbase_bribe_pct", pc1) + ";  2024 " + vv("2024", "coinbase_bribe_pct", pc1))
    w("  Public share (dumpster)  overall " + vv("overall", "dumpster_attacker_seen_pct", pc1) + ";  E3 " + vv("E3", "dumpster_attacker_seen_pct", pc1) + ";  E4 " + vv("E4", "dumpster_attacker_seen_pct", pc1) + ";  2025 " + vv("2025", "dumpster_attacker_seen_pct", pc1))
    w("  Median tx index          E3 " + vv("E3", "tx_index_median") + ";  E4 " + vv("E4", "tx_index_median") + ";  Tx index 0: E4 " + vv("E4", "tx_index_0_pct", pc1))
    w("  Zero-tip included        E4 " + vv("E4", "tip_zero_pct", pc1) + ";  ORIGIN check E4 " + vv("E4", "origin_check_pct_of_attacker_contracts", pc1) + ";  copycat candidates overall " + vv("overall", "frontrun_candidates_n"))
    w("")
    w("SENSITIVITY: attacker + unknown-sender rows (by_era_v2.json -> sensitivity_incl_unknown)")
    SE = {k[:2]: v for k, v in S["by_era"].items()}
    w(f"n by era: " + ", ".join(f"{c} {SE[c]['n_with_mainnet_tx_and_trace']}" for c in cols) + f".  Constructor E4 {_pc(SE['E4']['constructor_exploit_pct'])} (attacker-only {_pc(E['E4']['constructor_exploit_pct'])}); bribe E4 {_pc(SE['E4']['coinbase_bribe_pct'])} ({_pc(E['E4']['coinbase_bribe_pct'])}); dumpster seen {_pc(S['overall']['dumpster_attacker_seen_pct'])} ({_pc(ov['dumpster_attacker_seen_pct'])});")
    w(f"median fresh gap E2 {_dur(SE['E2']['deploy_gap_s_median_fresh_le7d'])} ({_dur(E['E2']['deploy_gap_s_median_fresh_le7d'])}), E4 {_dur(SE['E4']['deploy_gap_s_median_fresh_le7d'])} ({_dur(E['E4']['deploy_gap_s_median_fresh_le7d'])}).  Conclusions do not change.")
    w("")
    w("EXTERNAL COMPARISON")
    w(f"- BACKRUNNER (arXiv 2409.06213): 17 of 158 attack txs visible in the public mempool, Jan 2023 - May 2024 (10.8%).  Ours, exploit level, attacker-only, overlapping measurable window Aug 2023 - May 2024:")
    w(f"  {win_pub} of {win_res} public ({100 * win_pub / win_res:.1f}%) (v1, all senders: {v1w_pub} of {v1w_res}, {100 * v1w_pub / v1w_res:.1f}%).  They still agree.  Their 'bots intercepted 18/158' is not comparable to chain scan's candidates; chain scan finds {cwin} medium/strong")
    w(f"  candidates among the {nwin_all} attacker-only exploits dated Jan 2023 - May 2024 (v1: 0 of 109 all-sender rows).  BACKRUNNER saw 4 constructor attack txs in 1.5 years; we count constructor exploits per exploit, not per tx.")
    w(f"- APE (Qin et al.): 10 of 12 whitehat attack txs private (83%).  Our dumpster-era attackers are {100 - ov['dumpster_attacker_seen_pct']:.1f}% private against {_pc(ov['dumpster_control_seen_pct'])} for neighbours,")
    w("  so private submission is the norm for adversaries too.  The one whitehat row (BlockSec, Paraspace) predates the archive and cannot be compared; the 9 c0ffeebabe rows are bot-side and unanalysed.")
    w("")
    w("CAVEATS")
    w("1. Sender class is evidence-ranked, not ground truth.  High confidence = the address is named in an incident file, w1/w7 research, or (c0ffeebabe) the DHL sender;")
    w(f"   low confidence = a heuristic (R1/R1b/R2/R3 in definitions.rule_order).  Low-confidence bots: {', '.join(sorted(b['rows'][0] if len(b['rows']) == 1 else '/'.join(b['rows']) for b in C['bots_relabelled'] if b['confidence'] == 'low'))}.")
    w("   The sensitivity run only adds back unknown-sender rows; we did not run a variant that returns the low-confidence bot rows to attacker (their weight is the 'low-confidence bots' group above:")
    w("   E4 bribe share 16.3% -> 14.7% and zero-tip 10.5% -> 8.7% if only they are removed from v1).  A busy account (>=1000 prior txs) is not automatically a bot: some 'unknown' rows could be experienced exploiters.")
    w("   Some bot rows are bot-run exploits, not copies or races of a human attacker: the w7 profiles find 0xd215 and 0x7248 first and sole actors on their DHL rows (unprotected rescue-style functions; a swap-back template),")
    w("   no bot-vs-hacker race.  They are 'attacks' in the DHL sense but the actor is a general MEV bot, so they are kept off the attacker side; whoever counts bot-run exploits as attackers should use the v1 columns for them.")
    w("2. Hopelend (264 ETH) and Ambient (33.9 ETH) are the two largest attacker-side payments and both have searcher-shaped txs (index 0 / 1, zero or low tip, big coinbase payment).  They stay attacker because")
    w("   no bot identification exists; they could be wrongly kept.  Anyswap is low confidence.")
    w("3. 'Not measured' rows (29 in the 315) hide attackers: when only a bot's tx is listed we do not know when or how the real attacker acted, so attacker-side numbers describe exploits for which")
    w("   DeFiHackLabs listed the attacker's own tx.  If bots mostly win races, exploits lost to bots are over-represented among the unmeasured.")
    w("4. The bot-side table is not a census of bots: it contains only bot txs that happened to be in a DHL PoC header.  Counts by era mean nothing about bot prevalence.  c0ffeebabe rows have no analysis by publication policy.")
    w("5. No direct exposure data before 2023-08-07 (same as v1).  Pre-Aug-2023 labels are heuristic, 'unknown' is not 'public'; the dumpster drifted (sources 7 -> 3-4), hence the same-block control.")
    w("6. Survivorship/selection (DeFiHackLabs coverage), small cells (E1 n=11, E2 n=22), constructor/guard detection lower bounds: unchanged from v1 (findings.txt caveats 3, 5-7).")
    w("   v1's row convention is also unchanged: the measured tx is the earliest listed non-deploy tx of the chosen sender class, which can be a setup step (Unilend: the pledge and share-transfer txs by the")
    w("   PoC's second attacker account precede the draining tx), so timing columns for multi-step incidents describe the first step.")
    w("7. The latest-nonce signal was read at block 26243670 (2026-10-21); it separates long-lived accounts from one-shot wallets and is not an identity test.")
    w("")
    w("REPRODUCE")
    w("  .venv/bin/python scripts/evolution.py relabel     (reads cached work/*.json, incidents/*/incident.json, w1/w7 research and the DHL clone; writes sender_class.json,")
    w("                                                      per_exploit_v2.json, by_era_v2.json, findings_v2.txt; v1 files are never written)")
    w("  .venv/bin/python scripts/evolution.py senders     (only if new senders appear: latest nonce at block 26243670 via scripts/lib/rawfetch + RPC)")
    w("Evidence snapshots: work/sender_registry.json (address registry), work/poc_addresses.json (addresses in each PoC), work/sender_nonces.json.")
    (W_6 / "findings_v2.txt").write_text("\n".join(L) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["txs", "traces", "mempool", "calibrate", "analyze", "all", "senders", "relabel"])
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--mp-threads", type=int, default=4)
    a = ap.parse_args()
    exploits = load_exploits()
    WORK.mkdir(parents=True, exist_ok=True)
    if a.stage in ("txs", "all"):
        stage_txs(exploits, a.threads, a.limit)
    txs = jload(WORK / "txs.json", {})
    if a.stage in ("mempool", "all"):
        stage_mempool(exploits, txs, a.mp_threads, a.limit)
    if a.stage in ("traces", "all"):
        stage_traces(exploits, txs, a.threads, a.limit)
    if a.stage in ("calibrate", "all"):
        stage_calibrate(exploits)
    if a.stage in ("analyze", "all"):
        stage_analyze(exploits)
    if a.stage == "senders":
        stage_senders(exploits, a.threads)
    if a.stage == "relabel":
        res = stage_relabel(exploits)
        stage_relabel_write(res)
        write_findings_v2(res, jload(W_6 / "by_era_v2.json"))


if __name__ == "__main__":
    main()
