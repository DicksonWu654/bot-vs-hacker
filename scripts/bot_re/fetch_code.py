"""Fetch runtime bytecode of the two Yoink bot contracts at incident blocks + latest; save raw + .hex files."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import rawfetch as r
OUT = pathlib.Path(__file__).resolve().parents[2] / "research" / "bot-re" / "code"
OUT.mkdir(parents=True, exist_ok=True)
targets = {
    "bot2024_0x6980a47b": ("0x6980a47bee930a4584b09ee79ebe46484fbdbdd0", [20468847, 20468848, "latest"]),
    "bot2026_0x80bf7db6": ("0x80bf7db69556d9521c03461978b8fc731dbbd4e4", [25980524, 25980525, "latest"]),
}
for name, (addr, blocks) in targets.items():
    for b in blocks:
        tag = b if b == "latest" else hex(b)
        code = r.rpc("eth_getCode", [addr, tag], key=f"code_{addr}_{b}")
        (OUT / f"{name}_{b}.hex").write_text(code)
        print(name, b, len(code) // 2 - 1 if code != "0x" else 0, "bytes")
    src = r.etherscan({"module": "contract", "action": "getsourcecode", "address": addr}, key=f"src_{addr}")
    print(name, "etherscan verified:", bool(src["result"][0].get("SourceCode")), src["result"][0].get("ContractName"))
