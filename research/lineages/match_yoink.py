import json, collections
tx = json.load(open(str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'research/lineages/_yoink_txlist.json')))
Y = '0xfde0d1575ed8e06fbf36256bcdfa1f359281455a'
conts = set(x['contractAddress'] for x in tx if x['to'] == '')
ex = json.load(open(str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'research/chain-scan/exploits_mainnet.json')))['exploits']
byblk = collections.defaultdict(list)
for t in tx:
    if t['from'] == Y and t['to'] in conts:
        byblk[int(t['blockNumber'])].append(t)
out = []
seen = set()
for e in ex:
    for ti in e.get('tx_info', []):
        b = ti.get('block')
        if not b:
            continue
        for d in range(-3, 6):
            if b + d in byblk:
                k = (e['name'], b + d)
                if k in seen:
                    continue
                seen.add(k)
                out.append({'name': e['name'], 'date': e['date'], 'exploit_tx': ti['hash'], 'exploit_block': b, 'delta': d,
                            'yoink': [{'hash': t['hash'], 'idx': t['transactionIndex'], 'value': t['value'], 'err': t['isError'], 'to': t['to']} for t in byblk[b + d]]})
json.dump(out, open(str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'research/lineages/_yoink_dhl_blockmatch.json'), 'w'), indent=1)
for o in out:
    print(o['name'][:30], o['date'], o['exploit_block'], o['delta'], [(y['hash'][:10], y['idx'], y['value'], y['err']) for y in o['yoink']][:3])
print(len(out))
