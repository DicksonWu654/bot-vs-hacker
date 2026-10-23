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
