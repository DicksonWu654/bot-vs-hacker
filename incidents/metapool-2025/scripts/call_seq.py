"""Victim-call sequences of the four Meta Pool exploit txs (traces saved by rawfetch). Library + __main__ print."""
import json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
from rawfetch import rpc

MP = "0x48afbbd342f64ef8a9ab1c143719b63c2ad81710"      # mpETH proxy (ERC4626 vault, impl 0x37474845)
POOL = "0xdf261f967e87b2aa44e18a22f4ace5d7f74f03cc"    # Meta Pool liquid-unstake pool (mpETH <-> ETH)
V3 = "0xcf0e3ab3bc3b4a64f2d169decea24bc17b038278"      # Uniswap V3 mpETH/WETH pool
VICTIMS = {MP, POOL, V3}
NAMES = {"2d2da806": "depositETH(address)", "94bf804d": "mint(uint256,address)", "095ea7b3": "approve(address,uint256)",
         "20168730": "swapmpETHforETH(uint256,uint256)", "128acb08": "swap(address,bool,int256,uint160,bytes) [UniV3 pool]",
         "70a08231": "balanceOf(address)", "a9059cbb": "transfer(address,uint256)", "23b872dd": "transferFrom(address,address,uint256)",
         "c3e8c4fa": "swapETHFormpETH(address)", "ef8b30f7": "previewDeposit(uint256)", "07a2d13a": "convertToAssets(uint256)"}
TXS = {
    "yoink": "0x4f43fc6d674e85f7d306debb4a3d48e7688c2fe5a6332dd9ad57558a15c86ef9",
    "att_test1": "0x691c8070749f00a5a5be3135d3912ff97d0dad05a0fb2b77b235aaa13260f002",
    "att_test2": "0x4858abc51876e1de9f506f34799d4f1852b4255f467b9e1f40951c631ddfa747",
    "att_main": "0x57ee419a001d85085478d04dd2a73daa91175b1d7c11d8a8fb5622c56fd1fa69",
}


def trace(h):
    return rpc("debug_traceTransaction", [h, {"tracer": "callTracer"}], key=f"mp_trace_{h}", timeout=300)


def word(inp, i):
    return int(inp[10 + 64 * i: 10 + 64 * (i + 1)] or "0", 16)


def victim_calls(tr):
    """Calls INTO a victim contract made by a non-victim (the bot / attacker contract or a router), depth-first, no delegatecalls."""
    out = []

    def walk(c, parent_to):
        to = (c.get("to") or "").lower()
        frm = (c.get("from") or "").lower()
        if c.get("type") in ("CALL", "STATICCALL") and to in VICTIMS and frm not in VICTIMS and frm not in {MP}:
            inp = c.get("input", "0x")
            sel = inp[2:10]
            out.append({"to": to, "caller": frm, "type": c["type"], "selector": "0x" + sel, "name": NAMES.get(sel, "?"),
                        "value_eth": int(c.get("value", "0x0"), 16) / 1e18, "words": [hex(word(inp, i)) for i in range(min(3, (len(inp) - 10) // 64))],
                        "error": c.get("error")})
        for x in c.get("calls", []):
            walk(x, to)
    walk(tr, None)
    return out


if __name__ == "__main__":
    for k, h in TXS.items():
        print("==", k, h[:12])
        for c in victim_calls(trace(h)):
            if c["selector"] in ("0x70a08231", "0x07a2d13a", "0xef8b30f7"):
                continue
            print(" ", "STATIC" if c["type"] == "STATICCALL" else "CALL", {MP: "mpETH", POOL: "pool", V3: "v3"}[c["to"]], c["name"], c["value_eth"], c["words"])
