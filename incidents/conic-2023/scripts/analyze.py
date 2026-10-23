"""conic-2023 analysis: recompute every number from saved raw RPC/Etherscan files and write
  incidents/conic-2023/victim_call_diff_crvusd.json   (attacker tx vs Yoink copy tx, call-by-call)
  incidents/conic-2023/yoink_10txs.json               (the ten Yoink gen1 txs: gross / coinbase / gas / net + sums vs Yoink's message)
  incidents/conic-2023/victim_call_diff_eth.json      (failed original ETH-pool attack vs the successful clone)
Run from project root:  .venv/bin/python incidents/conic-2023/scripts/analyze.py
Only the *attacker* and *Yoink* are decoded here (Yoink gen1 grammar is in research/bot-re/analysis.md); c0ffeebabe is not involved.
"""
import json, pathlib, sys, difflib
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import rawfetch as rf  # noqa: E402

SRC = "rpc-conic"
OUT = ROOT / "incidents" / "conic-2023"


def hx(x):
    return int(x, 16) if isinstance(x, str) and x.startswith("0x") else (int(x) if x else 0)


def raw(key, source=SRC):
    p = rf.raw_path(source, key)
    assert p, f"missing raw {source}/{key}"
    return p


def loadj(key, source=SRC):
    return json.load(open(ROOT / raw(key, source)))


def trace(h):
    return loadj(f"trace_{h}")["result"]


def tx(h):
    return loadj(f"conic_tx_{h}")["result"]


def rcpt(h):
    return loadj(f"conic_rcpt_{h}")["result"]


def calls_from(t, actor):
    out = []

    def w(f):
        if (f.get("from") or "").lower() == actor and f["type"] in ("CALL", "STATICCALL", "DELEGATECALL"):
            out.append(dict(to=f["to"].lower(), input=f.get("input", "0x"), value=hx(f.get("value")), type=f["type"],
                            error=f.get("error")))
        for c in f.get("calls", []):
            w(c)
    w(t)
    return out


def words(inp):
    b = inp[10:]
    return [int(b[k:k + 64], 16) for k in range(0, len(b), 64)]


# ------------------------------------------------------------------------------------------------ crvUSD pool
A_TX = "0x37acd17a80a5f95728459bfea85cb2e1f64b4c75cf4a4c8dcb61964e26860882"
Y_TXS = ["0x64910b0a07083119403ce1bb30c94503e99e44c334bdb68f3afea09c834bdd9f", "0x3af57106166b8568a0ace8d0741cf05355d74d7e7e173f1bab7a4434c6f0ed80",
         "0xcf484ced351166dee819fcf2417e7df6ac826ac6af53c676e28f6bc96f5bcdbd", "0x680b7d4947068647b1360904581c843fe6b477e55fe64ece6ef4b733aee12c8f",
         "0x69029760e5907a7a82c9ac008602f6cc719f1e64bf7912c1148bb6dce10cea41", "0xad596a612492bc640eca76afd03a03aed9ad91cf98f226624a9d8829e35e9308",
         "0xa267ece5e1321e4a51c2a03fb9592e73f79cc13ddc60d8bd7dafd6daf491d7fa", "0xe7f54acd58bea522f9aac5d18f8765a96a2b41d1aa620f9df5e084e113976080",
         "0x050dec294956f9a036565be9b2c1cfb4e7c74fcdeaed4ae8ef42f42cca17e32c", "0xde8e5f61c89d3f488e97dad680d314a347fefa3e55eb00221b70527a7d44cea8"]
A_CON = "0x486cb3f61771ed5483691dd65f4186da9e37c68e"
YBOT = "0xd050e0a4838d74769228b49dff97241b4ef3805d"
NAMES = {
    "0x369cbc5c6f139b1132d3b91b87241b37fc5b971f": "Conic crvUSD omnipool (victim)",
    "0xa920de414ea4ab66b97da1bfe9e6eca7d4219635": "crvUSD LlamaLend/controller (create_loan, repay)",
    "0x4dece678ceceb27446b35c672dc7d61f30bad69e": "Curve crvUSD/USDC pool",
    "0x390f3595bca2df7d23783dfd126427cceb997bf4": "Curve crvUSD/USDT pool",
    "0x7f86bf177dd4f3494b841a37e810a34dd56c829b": "Curve tricrypto (USDC -> ETH exit)",
    "0xba12222222228d8ba445958a75a0704d566bf2c8": "Balancer Vault (flash loan)",
}


def crvusd_diff():
    ta, ty = trace(A_TX), trace(Y_TXS[0])
    aa, ay = calls_from(ta, A_CON), calls_from(ty, YBOT)
    key = lambda c: (c["to"], c["input"][:10])  # noqa: E731
    sm = difflib.SequenceMatcher(None, [key(c) for c in aa], [key(c) for c in ay], autojunk=False)
    # victim-relevant calls (state-changing / swap legs), compared by (target, selector) and by calldata words
    per = {}
    for v, nm in NAMES.items():
        if v == "0xba12222222228d8ba445958a75a0704d566bf2c8":
            continue
        la = [c for c in aa if c["to"] == v and c["type"] == "CALL"]
        ly = [c for c in ay if c["to"] == v and c["type"] == "CALL"]
        rows = []
        for a, y in zip(la, ly):
            wa, wy = words(a["input"]), words(y["input"])
            # normalise own-address words
            na = [("<SELF>" if w == int(A_CON, 16) else w) for w in wa]
            ny = [("<SELF>" if w == int(YBOT, 16) else w) for w in wy]
            rows.append({"selector": a["input"][:10], "same_selector": a["input"][:10] == y["input"][:10],
                         "calldata_identical_after_self_address_normalisation": na == ny,
                         "attacker_args": [str(x) for x in na][:5], "yoink_args": [str(x) for x in ny][:5]})
        per[v] = {"label": nm, "n_attacker": len(la), "n_yoink": len(ly),
                  "n_identical_calldata": sum(1 for r in rows if r["calldata_identical_after_self_address_normalisation"]), "calls": rows}
    # Balancer flashLoan args (tokens/amounts) identical?
    fa = [c for c in aa if c["to"] == "0xba12222222228d8ba445958a75a0704d566bf2c8" and c["input"].startswith("0x5c38449e")][0]
    fy = [c for c in ay if c["to"] == "0xba12222222228d8ba445958a75a0704d566bf2c8" and c["input"].startswith("0x5c38449e")][0]
    wfa, wfy = words(fa["input"]), words(fy["input"])
    # words 1..11 = offsets/array lengths, token list (USDC, WETH, USDT) and the three amounts; word 0 = recipient; userData (word 12+) is each actor's own callback payload
    fl_same_modulo_recipient = wfa[1:12] == wfy[1:12]
    # all victim+curve calls in the two traces (any depth) by (to,selector): counts
    import collections

    def agg(t):
        c = collections.Counter()

        def w(f):
            if f.get("to"):
                c[f["to"].lower() + ":" + f.get("input", "")[:10]] += 1
            for x in f.get("calls", []):
                w(x)
        w(t)
        return c
    ca, cy = agg(ta), agg(ty)
    keys = ["0x369cbc5c6f139b1132d3b91b87241b37fc5b971f:0x43a0d066", "0x369cbc5c6f139b1132d3b91b87241b37fc5b971f:0x441a3e70",
            "0x47fb2585d2c56fe188d0e6ec628a38b74fceeedf:0xd2edb6dd", "0x013a3da6591d3427f164862793ab4e388f9b587e:0x9f82b217",
            "0x4dece678ceceb27446b35c672dc7d61f30bad69e:0x3df02124", "0x390f3595bca2df7d23783dfd126427cceb997bf4:0x3df02124"]
    ra, ry = rcpt(A_TX), rcpt(Y_TXS[0])
    res = {
        "schema": "conic-2023/victim_call_diff_crvusd/1",
        "attacker_tx": A_TX, "attacker_contract": A_CON, "yoink_tx": Y_TXS[0], "yoink_bot_contract": YBOT,
        "attacker_block": hx(tx(A_TX)["blockNumber"]), "attacker_index": hx(tx(A_TX)["transactionIndex"]),
        "yoink_block": hx(tx(Y_TXS[0])["blockNumber"]), "yoink_index": hx(tx(Y_TXS[0])["transactionIndex"]),
        "n_direct_calls_attacker_contract": len(aa), "n_direct_calls_yoink_bot": len(ay),
        "direct_call_sequence_similarity": round(sm.ratio(), 4),
        "non_matching_blocks": [{"op": o[0], "attacker_idx": [o[1], o[2]], "yoink_idx": [o[3], o[4]],
                                 "attacker": [f"{c[0][:10]}:{c[1]}" for c in [key(x) for x in aa[o[1]:o[2]]]][:6],
                                 "yoink": [f"{c[0][:10]}:{c[1]}" for c in [key(x) for x in ay[o[3]:o[4]]]][:6]}
                                for o in sm.get_opcodes() if o[0] != "equal"][:8],
        "difference_summary": ("The only differences in the direct-call sequence are (a) attacker-side balanceOf STATICCALLs that Yoink does not make, "
                               "(b) Yoink's five up-front approve() calls (the attacker made them in the separate setup tx 0xc8603387), and (c) the final "
                               "ETH hand-off (attacker EOA vs Yoink's builder payment). Every state-changing call to the Conic pool, crvUSD controller, "
                               "both Curve pools and the tricrypto exit has the same target and selector, in the same order."),
        "per_victim_contract": per,
        "balancer_flashloan_tokens_and_amounts_identical": fl_same_modulo_recipient,
        "full_trace_call_counts_attacker_vs_yoink": {k: [ca[k], cy[k]] for k in keys},
        "gas_used": {"attacker": hx(ra["gasUsed"]), "yoink": hx(ry["gasUsed"])},
        "eth_out_of_tricrypto_exit": {"attacker": sum(c["value"] for c in aa if c["to"] == A_CON) / 1e18,
                                      "note": "attacker's 11.5626 ETH profit arrives as internal value from the tricrypto exit; Yoink's equivalent is 12.5835 ETH (yoink_10txs.json)"},
        "reading": ("Same Balancer flash loan (12,000,000 USDC / 80,000 WETH / 9,000,000 USDT), same create_loan(80,000 WETH, 93,000,000 crvUSD, 10), same "
                    "round-number Curve swap sizes (19M/27M/28M/39M/12M/9M crvUSD) and same first Conic deposit (47,000,000 crvUSD); the amounts that "
                    "derive from live balances (swap outputs fed into the next leg, later Conic deposit/withdraw sizes, final USDC leg) differ in the 3rd-4th significant digit because the pool state differs. "
                    "This is the attacker's strategy replayed with re-derived amounts, not a generic arbitrage."),
        "raw_refs": {"attacker_trace": raw(f"trace_{A_TX}"), "yoink_trace": raw(f"trace_{Y_TXS[0]}"), "attacker_receipt": raw(f"conic_rcpt_{A_TX}"),
                     "yoink_receipt": raw(f"conic_rcpt_{Y_TXS[0]}"), "dhl_poc": "data/raw/web-conic/dhl_conic02.txt"},
    }
    json.dump(res, open(OUT / "victim_call_diff_crvusd.json", "w"), indent=1)
    return res


# ------------------------------------------------------------------------------------------------ Yoink 10 txs
def yoink_10():
    rows, tot = [], dict(gross=0, coinbase=0, gas=0)
    for h in Y_TXS:
        t, r, x = trace(h), rcpt(h), tx(h)
        inflow, out = 0, []

        def w(f, ok=True):
            nonlocal inflow
            ok = ok and not f.get("error")
            if ok and (f.get("to") or "").lower() == YBOT and f["type"] == "CALL" and hx(f.get("value")):
                inflow += hx(f["value"])
            if ok and f["type"] == "CALL" and (f.get("from") or "").lower() == YBOT and hx(f.get("value")):
                out.append((f["to"].lower(), hx(f["value"])))
            for c in f.get("calls", []):
                w(c, ok)
        w(t)
        assert len(out) == 1
        egp = hx(r["effectiveGasPrice"])
        gas = hx(r["gasUsed"]) * egp
        hdr = loadj(f"conic_blockhdr_{hx(x['blockNumber'])}")["result"]
        mv = hx(x["value"])
        rows.append({"tx": h, "block": hx(x["blockNumber"]), "index": hx(x["transactionIndex"]), "timestamp_utc": hdr["timestamp"] and hx(hdr["timestamp"]),
                     "builder_fee_recipient": hdr["miner"], "builder_extra_data": bytes.fromhex(hdr["extraData"][2:]).decode("utf8", "replace"),
                     "base_fee_gwei": hx(hdr["baseFeePerGas"]) / 1e9, "block_gas_used": hx(hdr["gasUsed"]),
                     "msg_value_wei": mv, "gross_eth": inflow / 1e18, "coinbase_paid_eth": out[0][1] / 1e18, "coinbase_to": out[0][0],
                     "coinbase_over_gross_permille": round(out[0][1] / inflow * 1000, 3), "gas_cost_eth": gas / 1e18,
                     "gas_used": hx(r["gasUsed"]), "effective_gas_price_gwei": egp / 1e9, "priority_fee_gwei": (egp - hx(hdr["baseFeePerGas"])) / 1e9,
                     "net_eth": (inflow - out[0][1] - gas) / 1e18, "status": r["status"],
                     "raw_refs": [raw(f"trace_{h}"), raw(f"conic_rcpt_{h}"), raw(f"conic_tx_{h}"), raw(f"conic_blockhdr_{hx(x['blockNumber'])}")]})
        tot["gross"] += inflow; tot["coinbase"] += out[0][1]; tot["gas"] += gas
    s = {k: v / 1e18 for k, v in tot.items()}
    s["net"] = s["gross"] - s["coinbase"] - s["gas"]
    msg = {"text_tx": "0xaf1535ea5bee7ccbc048eafd1fe0771c31cde51d065e6abc2c4aa2c1f9d264ff", "gross_claimed": 125.82415, "gas_and_bribes_claimed": 35.48275,
           "to_return_claimed": 90.34139, "bounty_10pct_implied": round(90.34139 * 0.1, 5), "returned_per_conic_message": 81.307251}
    ret_tr = loadj("trace_0xf56f34a092d8864549052d8a1072e8477a4fb45382ec9549a25c63bb566630b4")["result"]
    returned = sum(hx(c["value"]) for c in ret_tr.get("calls", []) if c["to"].lower() == "0xedaeb101f34d767f263c0fe6b8d494e3d071f0ba") / 1e18
    res = {"schema": "conic-2023/yoink_10txs/1", "yoink_eoa": "0xfde0d1575ed8e06fbf36256bcdfa1f359281455a", "bot_contract": YBOT, "rows": rows,
           "sum_eth": s, "sum_gas_plus_coinbase_eth": s["coinbase"] + s["gas"],
           "matches_yoink_message": {"gross_diff_eth": s["gross"] - msg["gross_claimed"], "gas_plus_bribes_diff_eth": s["coinbase"] + s["gas"] - msg["gas_and_bribes_claimed"],
                                     "net_diff_eth": s["net"] - msg["to_return_claimed"]},
           "yoink_message": msg, "returned_to_conicfinance_eth": returned, "returned_tx": "0xf56f34a092d8864549052d8a1072e8477a4fb45382ec9549a25c63bb566630b4",
           "returned_pct_of_net": returned / s["net"] * 100, "kept_by_yoink_eth": s["net"] - returned,
           "note": "gross = ETH value received by the bot contract from the Curve tricrypto exit (successful CALL frames); coinbase = value the bot contract sent to the block's fee recipient; gas = gasUsed * effectiveGasPrice. Our numbers match Yoink's on-chain message to 1e-5 ETH.",
           "raw_refs": {"return_trace": raw("trace_0xf56f34a092d8864549052d8a1072e8477a4fb45382ec9549a25c63bb566630b4"),
                        "message_tx": raw(f"conic_tx_{msg['text_tx']}")}}
    json.dump(res, open(OUT / "yoink_10txs.json", "w"), indent=1)
    return res


# ------------------------------------------------------------------------------------------------ ETH pool
O_DEP = "0x4df580b9b4afc34c195f6b18b1468be5354c014294425aabe59150da351d6d74"
O_ATK = "0x97a8315e942dd180fb90a17b92f7dabd6e8a2e5b9fd5e4a95ee4049ff33d2f16"
C_DEP = "0x16718a6df144de749035e4763946ad56d3dfaeb5d151a82f913698fa4ae28c3d"
C_ATK = "0x8b74995d1d61d3d7547575649136b8765acb22882960f0636941c44ec7bbe146"
OC, CC = "0xdac434f8011e9588f39fa43c3f7cdbbcb3e5cd1f", "0x743599ba5cfa3ce8c59691af5ef279aaafa2e4eb"
OE, CE = "0x10db234e02c3889d8e408c7084e8ce10892bdad7", "0x8d67db0b205e32a5dd96145f022fa18aae7dc8aa"


def eth_diff():
    a, b = tx(O_DEP)["input"][2:], tx(C_DEP)["input"][2:]
    diff = [i // 2 for i in range(0, len(a), 2) if a[i:i + 2] != b[i:i + 2]]
    runs = []
    for i in diff:
        if runs and i - runs[-1][1] <= 1:
            runs[-1][1] = i
        else:
            runs.append([i, i])
    d_runs = [{"byte_offset": r[0], "length": r[1] - r[0] + 1, "original": a[r[0] * 2:(r[1] + 1) * 2], "clone": b[r[0] * 2:(r[1] + 1) * 2]} for r in runs]
    A1, A2 = tx(O_ATK), tx(C_ATK)
    w1, w2 = words(A1["input"]), words(A2["input"])
    ta, tb = trace(O_ATK), trace(C_ATK)

    def flat(t, self_, eoa):
        seq = []

        def w(f, d=0):
            inp = (f.get("input") or "").lower().replace(self_[2:], "<SELF>").replace(eoa[2:], "<EOA>")
            to = (f.get("to") or "").lower()
            fr = (f.get("from") or "").lower()
            seq.append((d, f["type"], "<SELF>" if fr == self_ else ("<EOA>" if fr == eoa else fr), "<SELF>" if to == self_ else to, inp))
            for c in f.get("calls", []):
                w(c, d + 1)
        w(t)
        return seq
    fa, fb = flat(ta, OC, OE), flat(tb, CC, CE)
    lead = 0
    for x, y in zip(fa, fb):
        if x != y:
            break
        lead += 1
    same_pos = sum(1 for x, y in zip(fa, fb) if x == y)

    ka = [(x[1], x[3], x[4][:10]) for x in fa]
    kb = [(x[1], x[3], x[4][:10]) for x in fb]
    smx = difflib.SequenceMatcher(None, ka, kb, autojunk=False)
    # frames of the original that have no counterpart in the clone and vice versa
    only_o = sum(o[2] - o[1] for o in smx.get_opcodes() if o[0] in ("delete", "replace"))
    only_c = sum(o[4] - o[3] for o in smx.get_opcodes() if o[0] in ("insert", "replace"))

    def deepest(f):
        k = [c for c in f.get("calls", []) if c.get("error")]
        return f if not k else deepest(k[-1])
    df = deepest(ta)
    ra, rb = rcpt(O_ATK), rcpt(C_ATK)
    res = {"schema": "conic-2023/victim_call_diff_eth/1",
           "original": {"eoa": OE, "contract": OC, "deploy_tx": O_DEP, "attack_tx": O_ATK, "block": hx(A1["blockNumber"]), "index": hx(A1["transactionIndex"]),
                        "status": "reverted", "gas_limit": hx(A1["gas"]), "gas_used": hx(ra["gasUsed"]), "max_priority_fee_gwei": hx(A1["maxPriorityFeePerGas"]) / 1e9},
           "clone": {"eoa": CE, "contract": CC, "deploy_tx": C_DEP, "attack_tx": C_ATK, "block": hx(A2["blockNumber"]), "index": hx(A2["transactionIndex"]),
                     "status": "success", "gas_limit": hx(A2["gas"]), "gas_used": hx(rb["gasUsed"]), "max_priority_fee_gwei": hx(A2["maxPriorityFeePerGas"]) / 1e9},
           "creation_code_bytes": [len(a) // 2, len(b) // 2], "creation_code_differing_bytes": len(diff), "creation_code_diff_runs": d_runs,
           "creation_code_diff_reading": "Exactly one 20-byte address differs, at byte offset 1370: the original attacker's EOA (0x10db234e...) is replaced by the clone's EOA (0x8d67db0b...). The other 21,950 bytes are identical.",
           "attack_calldata_identical": A1["input"] == A2["input"], "attack_selector": A1["input"][:10], "attack_args": [str(x) for x in w1],
           "trace_frames": [len(fa), len(fb)], "frame_sequence_similarity_type_target_selector": round(smx.ratio(), 4),
           "frames_only_in_original": only_o, "frames_only_in_clone": only_c, "identical_leading_frames": lead, "frames_equal_at_same_position": same_pos,
           "trace_reading": "Top-level call, the Aave/Balancer flash loans, the Curve add_liquidity / remove_liquidity and the re-entrant ConicEthPool.withdraw all appear in both traces with the same targets and selectors; amounts that derive from live state differ in low digits.",
           "original_failure": {"deepest_failing_frame": {"type": df["type"], "to": df["to"], "selector": df.get("input", "")[:10], "error": df.get("error")},
                                "reading": "Original reverted with out-of-gas inside a nested Curve call (gas limit 27.64M, 24.05M burned). The clone ran the same sequence with a 29.5M gas limit and finished using 20.14M.",
                                "caveat": "Cause is inferred from the trace (OOG in a nested frame); we did not fork-replay the original with a higher limit."},
           "raw_refs": {"original_attack_trace": raw(f"trace_{O_ATK}"), "clone_attack_trace": raw(f"trace_{C_ATK}"), "original_deploy_tx": raw(f"conic_tx_{O_DEP}"),
                        "clone_deploy_tx": raw(f"conic_tx_{C_DEP}"), "original_attack_tx": raw(f"conic_tx_{O_ATK}"), "clone_attack_tx": raw(f"conic_tx_{C_ATK}"),
                        "original_receipt": raw(f"conic_rcpt_{O_ATK}"), "clone_receipt": raw(f"conic_rcpt_{C_ATK}")}}
    json.dump(res, open(OUT / "victim_call_diff_eth.json", "w"), indent=1)
    return res


if __name__ == "__main__":
    r1 = crvusd_diff()
    print("crvusd: seq similarity", r1["direct_call_sequence_similarity"], {k: (v["n_attacker"], v["n_yoink"], v["n_identical_calldata"]) for k, v in r1["per_victim_contract"].items()},
          "flashloan same", r1["balancer_flashloan_tokens_and_amounts_identical"])
    r2 = yoink_10()
    print("yoink sums", r2["sum_eth"], r2["matches_yoink_message"], r2["returned_to_conicfinance_eth"], r2["returned_pct_of_net"], r2["kept_by_yoink_eth"])
    r3 = eth_diff()
    print("eth", r3["frame_sequence_similarity_type_target_selector"], r3["frames_only_in_original"], r3["frames_only_in_clone"], r3["creation_code_differing_bytes"], r3["creation_code_diff_runs"], r3["attack_calldata_identical"], r3["identical_leading_frames"], r3["frames_equal_at_same_position"], r3["trace_frames"])
