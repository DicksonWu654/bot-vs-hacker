import sys, json, time
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'scripts/lib'))
import rawfetch as rf

_last = [0.0]
def es(params, key):
    p = rf.RAW / 'etherscan' / (rf._safe(key) + '.json')
    if p.exists():
        j = json.loads(p.read_bytes())
        if not (j.get('status') == '0' and 'rate' in str(j.get('result', '')).lower()):
            return j
    import fcntl
    for i in range(30):
        with open('etherscan.lock', 'a+') as lk:
            fcntl.flock(lk, fcntl.LOCK_EX)
            lk.seek(0)
            try: last = float(lk.read().strip() or 0)
            except Exception: last = 0.0
            dt = time.time() - last
            if dt < 0.5: time.sleep(0.5 - dt)
            lk.seek(0); lk.truncate(); lk.write(str(time.time())); lk.flush()
        j = rf.etherscan(params, key, refresh=True)
        if isinstance(j, dict) and j.get('status') == '0' and 'rate' in str(j.get('result','')).lower():
            time.sleep(1.0 + i * 0.3); continue
        return j
    return j

def txlist_all(addr, action='txlist', tag='w8', startblock=0, endblock=99999999, offset=10000):
    """paginate by block range (page*offset limited to 10000 results)."""
    out = []
    sb = startblock
    n = 0
    while True:
        key = f"{tag}_{addr[:10]}_{action}_{sb}_{endblock}"
        j = es({'module':'account','action':action,'address':addr,'startblock':sb,'endblock':endblock,'page':1,'offset':offset,'sort':'asc'}, key)
        res = j.get('result')
        if not isinstance(res, list):
            if j.get('message') == 'No transactions found': break
            raise RuntimeError(f"{key}: {j}")
        out += res
        if len(res) < min(offset, 1000): break
        last = int(res[-1]['blockNumber'])
        # drop trailing block (may be partial) and restart from that block
        out = [r for r in out if int(r['blockNumber']) < last]
        sb = last
    return out
