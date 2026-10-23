"""Decoder for the packed 'script' calldata of selector 0x9846cd9e on the Yoink searcher contracts.

Layout (reverse engineered from runtime bytecode, validated by parsing every tx input to the exact byte):
  selector(4) | x:uint128 | f:uint8 | [if f!=0: token:20 | y:uint128] | nStores:uint8 | stores... | ops...
  op 0x00 CALL        : len:3 | to:20 | data:len
  op 0x01 CALL+value  : len:3 | to:20 | value:16 | data:len
  op 0x02..0x05       : pool:20 | token:20 | a:16 | b:16     (V2 / V3 swap helpers; see analysis.md)
  op 0x06             : token:20                              (pay-in-callback: transfer token to msg.sender)
  op 0x07             : key:4                                 (advance callback-template cursor for selector key)
  op 0x08             : token:20 | min:16                     (require balance>=min, sweep balance-1 to vault)
  op 0x09             : -                                     (WETH.withdraw(balance-1))
  2026 additions (Uniswap v4 era) handled in OPS26 below.
"""
import sys, json, pathlib

OPS24 = {0: "CALL", 1: "CALL_VALUE", 2: "V2_SELL", 3: "V3_SELL", 4: "V2_BUY", 5: "V3_BUY", 6: "PAY_CB", 7: "ADVANCE_CB", 8: "SWEEP", 9: "UNWRAP"}


def i(b):
    return int.from_bytes(b, "big")


def parse_ops(b, p, end):
    """Decode ops in b[p:end]. Returns (ops, ok)."""
    ops = []
    while p < end:
        o = b[p]; p += 1
        if o in (0, 1):
            n = i(b[p:p + 3]); to = "0x" + b[p + 3:p + 23].hex(); p += 23
            ent = {"op": "CALL", "to": to, "len": n}
            if o == 1:
                ent["value"] = i(b[p:p + 16]); p += 16
            ent["data"] = "0x" + b[p:p + n].hex(); p += n
            ent["sel"] = ent["data"][:10]
        elif 2 <= o <= 5:
            ent = {"op": OPS24[o], "pool": "0x" + b[p:p + 20].hex(), "token": "0x" + b[p + 20:p + 40].hex(), "a": i(b[p + 40:p + 56]), "b": i(b[p + 56:p + 72])}; p += 72
        elif o == 6:
            ent = {"op": "PAY_CB", "token": "0x" + b[p:p + 20].hex()}; p += 20
        elif o == 7:
            ent = {"op": "ADVANCE_CB", "key": b[p:p + 4].hex()}; p += 4
        elif o == 8:
            ent = {"op": "SWEEP", "token": "0x" + b[p:p + 20].hex(), "min": i(b[p + 20:p + 36])}; p += 36
        elif o == 9:
            ent = {"op": "UNWRAP"}
        elif o == 10:   # 2026 only: Uniswap v4 swap through PoolManager.unlock
            ent = {"op": "V4_SWAP", "dir": b[p], "token": "0x" + b[p + 1:p + 21].hex(), "fee": i(b[p + 21:p + 24]), "tickSpacing": i(b[p + 24:p + 27]), "a": i(b[p + 27:p + 43]), "b": i(b[p + 43:p + 59])}; p += 59
        elif o == 11:   # 2026 only: second Uniswap v4 swap flavour (same 59-byte layout as op 0x0a; checked by exact-length parse)
            ent = {"op": "V4_SWAP_B", "dir": b[p], "token": "0x" + b[p + 1:p + 21].hex(), "fee": i(b[p + 21:p + 24]), "tickSpacing": i(b[p + 24:p + 27]), "a": i(b[p + 27:p + 43]), "b": i(b[p + 43:p + 59])}; p += 59
        else:
            ent = {"op": f"UNKNOWN_{o:#x}", "rest": b[p - 1:p + 40].hex()}; ops.append(ent); return ops, False
        ops.append(ent)
    return ops, p == end


def parse(inp_hex):
    d = bytes.fromhex(inp_hex[2:])
    assert d[:4].hex() == "9846cd9e", d[:4].hex()
    b = d[4:]
    out = {"x": i(b[0:16]), "f": b[16]}
    p = 17
    if b[16]:
        out["hdr_token"] = "0x" + b[p:p + 20].hex(); out["hdr_y"] = i(b[p + 20:p + 36]); p += 36
    out["nStores"] = b[p]; p += 1
    stores = []
    for _ in range(out["nStores"]):
        key = b[p:p + 4].hex(); p += 4
        ents = []
        while True:
            flag = b[p]; ls = i(b[p + 1:p + 5]); lr = i(b[p + 5:p + 9]); p += 9
            sops, ok = parse_ops(b, p, p + ls); p += ls
            ret = b[p:p + lr]; p += lr
            ents.append({"ret": "0x" + ret.hex(), "script": sops, "script_ok": ok})
            if flag == 0xff:   # 0xff marks the LAST template for this selector; any other value means another follows
                break
        stores.append({"key": key, "entries": ents})
    out["stores"] = stores
    ops, ok = parse_ops(b, p, len(b))
    out["ops"] = ops; out["ok"] = ok and all(e["script_ok"] for s_ in stores for e in s_["entries"])
    return out


if __name__ == "__main__":
    print(json.dumps(parse(sys.argv[1]), indent=1)[:6000])
