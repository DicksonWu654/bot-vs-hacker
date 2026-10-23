"""Full txlist scan of proxy 0xa57bd001 -> slim jsonl + aggregates. Raw pages before block 9.71M were saved by rawfetch earlier
(data/raw/etherscan/w8_0xa57bd001_txlist_*); later pages are NOT saved raw (volume ~GBs) - only slim fields are kept."""
import sys, json, time, glob, os, fcntl, urllib.request, pathlib, collections
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'research/lineages'))
import lib; rf = lib.rf
A = '0xa57bd00134b2850b2a1c55860c9e9ea100fdd6cf'
S = 'scratch/'
OUT = S + 'a57_slim.jsonl'
KEY = os.environ['ETHERSCAN_API_KEY']

def throttle():
    with open('etherscan.lock', 'a+') as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        lk.seek(0)
        try: last = float(lk.read().strip() or 0)
        except Exception: last = 0.0
        dt = time.time() - last
        if dt < 0.5: time.sleep(0.5 - dt)
        lk.seek(0); lk.truncate(); lk.write(str(time.time())); lk.flush()

def page(sb):
    cache = rf.RAW / 'etherscan' / (rf._safe(f"w8_{A[:10]}_txlist_{sb}_99999999") + '.json')
    if cache.exists():
        j = json.loads(cache.read_bytes())
        if isinstance(j.get('result'), list): return j['result']
    for i in range(30):
        throttle()
        url = f"https://api.etherscan.io/v2/api?chainid=1&module=account&action=txlist&address={A}&startblock={sb}&endblock=99999999&page=1&offset=1000&sort=asc&apikey={KEY}"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=rf.UA), timeout=60) as r:
                j = json.loads(r.read())
        except Exception as e:
            time.sleep(2); continue
        if isinstance(j.get('result'), list): return j['result']
        if j.get('message') == 'No transactions found': return []
        time.sleep(1 + 0.3 * i)
    raise RuntimeError(f'page {sb} failed')

def slim(t):
    inp = t['input']
    return [int(t['blockNumber']), int(t['transactionIndex']), int(t['timeStamp']), t['from'], 1 if t['isError'] == '1' else 0,
            round(int(t['gasPrice']) / 1e9, 3), t['value'] if t['value'] != '0' else 0, inp[:10],
            ('0x' + inp[34:74]) if inp.startswith('0x1cff79cd') or inp.startswith('0x78e111f6') else None, t['hash']]

seen_hash = set()
n = 0
sb = 0
with open(OUT, 'w') as out:
    while True:
        r = page(sb)
        if not r: break
        for t in r:
            if t['hash'] in seen_hash: continue
            seen_hash.add(t['hash']); n += 1
            out.write(json.dumps(slim(t)) + '\n')
        last = int(r[-1]['blockNumber'])
        print(sb, len(r), last, n, flush=True)
        if len(r) < 1000: break
        # next page starts at last block (re-reads that block; dedupe by hash)
        if last == sb:
            sb = last + 1
        else:
            sb = last
print('done', n, flush=True)
