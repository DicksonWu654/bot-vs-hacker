import json,datetime,collections
Y='0xfde0d1575ed8e06fbf36256bcdfa1f359281455a'
ytx=json.load(open('_yoink_txlist.json'))
ct=json.load(open('_yoink_contract_txlists.json'))
code=json.load(open('scratch/yc_code.json'))
iso=lambda x: datetime.datetime.fromtimestamp(int(x),datetime.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
names={
'0x7309742879fc1ece640345f8231aaef6e789f131':('proto-A','Earliest deployment (first tx of the EOA, 2022-08-25): 6,002 B, 3 selectors 0x9846cd9e (main entry), 0x5b2e9917 withdrawERCTo, 0x205c2878 withdrawTo. No calls in txlist: a test/discarded deploy.'),
'0x8b25d2e6cbbaea59748fd0f62bac3e99cbaa56c4':('proto-B','Second deploy the same day (blk +34): 6,002 B, same 3 selectors, different bytecode hash than proto-A (vanity/constant tweak). No calls in txlist (creation tx only).'),
'0x8788a7cfd63cf06d0d7716c6a66f54b58248c896':('gen0a','First used bot, 2022-08-25: 6,314 B, adds 0x8122835d and 0x93f8c897 drain(bytes) to the 3 core selectors. ~700 txs.'),
'0x6c6b87d44d239b3750bf9badce26a9a0a3d2364e':('gen0b','2022-09-07 contract found in transitswap-2022: 6,731 B, same selector set as gen0a; the busiest of the 2022 pre-gen1 bots (10,4xx txs, Sep-Nov 2022). Predates the "gen1" d050e0a4 by 86 days.'),
'0x638233b8e452d18e89b614bc2277e9f4075184b7':('stub','342 B single-function stub 0x9ed35f56; reverts unless msg.sender address begins 0x6c6b (companion of gen0b 0x6c6b87d4). No direct txs, but its address is embedded in 618 gen0b calldatas, i.e. an in-tx helper target.'),
'0x73a987534554c733b8f2af86ea7e9a70f4cde222':('gen1-pre','8,586 B, same selector set and same size as gen1; deployed 2022-11-30, 2 days before gen1; 51 txs (probably a staging/test copy; inferred).'),
'0xd050e0a4838d74769228b49dff97241b4ef3805d':('gen1','"gen1" of research/bot-re/analysis.md: 8,586 B, no header; main bot Dec 2022 - Aug 2023.'),
'0x68dda7026f6f38bfa33e2778f2fcc2c71f3afec8':('stub','300 B single-function stub 0x9ed35f56; reverts unless msg.sender begins 0xd050 (companion of gen1). No direct txs; address embedded in 666 gen1 calldatas (in-tx helper target).'),
'0x6980a47bee930a4584b09ee79ebe46484fbdbdd0':('gen2','"gen2": 10,318 B, 3 core selectors, header+SSTORE callback store; main bot Aug 2023 - Feb 2025 (Ronin, Kelp-style captures).'),
'0xe6babc8f35f8600cd0ed78c0647656f94053452f':('stub','380 B selector-less forwarder (disassembly: forwards calldata back to msg.sender) gated on caller starting 0x69.. (companion of gen2 0x6980a47b). No direct txs; address in 43 gen2 calldatas.'),
'0x7bac4a2ede0779a1f79a5fefe4fe271b37304e24':('time-claimer','2023-12-11, 16,138 B: selectors 0x9846cd9e plus drain() 0x9890220b and claimed_(address) 0x9d43b53f - likely a one-off claim contract for TIME-token-hack proceeds (inferred from selector names and from message tx 0x273f8e55... pointing TIME holders to it). 3 txs.'),
'0x97f0fa1e5bf44f0dbd8dc5ee5e0d017667ae0c34':('gen2b','2024-10-31, 9,187 B, same 3 core selectors; a second-line bot beside gen2 (~1,600 txs, Oct 2024 - Feb 2025).'),
'0x6b35e95d8c855e8e4687ebafe6ae353b904b005e':('stub','243 B selector-less forwarder gated on caller starting 0x97f0 (companion of gen2b). No direct txs; address in 5 gen2b calldatas.'),
'0x80bf7db69556d9521c03461978b8fc731dbbd4e4':('gen3','"gen3": 9,954 B, 3 core selectors, TSTORE callback store, Uniswap v4; main bot Feb 2025 - present.'),
'0xd942ccb33ab81ee49c707c10ac65616a231b8295':('stub','243 B selector-less forwarder gated on caller starting 0x80bf (companion of gen3). No direct txs; address in 23 gen3 calldatas.'),
'0x0913b172530805af05ff28814ca941bd28b5b4e9':('helper','2025-09-03, 2,085 B: 0x8a788cad gibToken(address) + 0xe4149e48; small token-pull helper.  1 tx.'),
'0x0d7ad6effd1c6e94e86e4daa7b7c7ef0ab3427d5':('gate','2026-05-03, 265 B: single function 0xb4faa01f(uint256) that reverts if balance of gen3 0x80bf7db6 is below the argument (balance-guard probe). Called 170x by Y.'),
}
out=[]
for t in ytx:
    if t['to']!='': continue
    a=t['contractAddress']; txs=ct.get(a,[])
    fy=[x for x in txs if x['from']==Y]
    c=code.get(a,{})
    nm=names.get(a,('?',''))
    out.append({'address':a,'label':nm[0],'created_utc':iso(t['timeStamp']),'created_block':int(t['blockNumber']),'creation_tx':t['hash'],
      'runtime_size_bytes':c.get('size'),'code_sha256_16':c.get('sha'),'selectors':c.get('selectors'),
      'txs_to_contract_total_incl_creation':len(txs),'calls_excluding_creation':len([x for x in txs if x['to']!='']),'calls_by_year':dict(sorted(collections.Counter(iso(x['timeStamp'])[:4] for x in txs if x['to']!='').items())),
      'txs_to_contract_total':len(txs),'txs_from_yoink_eoa':len(fy),'txs_from_others':len(txs)-len(fy),
      'first_tx_utc':iso(txs[0]['timeStamp']) if txs else None,'last_tx_utc':iso(txs[-1]['timeStamp']) if txs else None,
      'reverted_txs':sum(1 for x in txs if x['isError']=='1'),
      'characterization':nm[1],
      'raw_refs':{'creation_txlist':'data/raw/etherscan/w8_0xfde0d157_txlist_*.json','contract_txlist':f'data/raw/etherscan/w8_{a[:10]}_txlist_0_99999999.json','code':f'data/raw/rpc/w8_code_{a}.json'}})
json.dump({'deployer_eoa':Y,'method':'Etherscan v2 txlist of the EOA (to=="" rows, contractAddress), 49,250 txs 2022-08-25..2026-10-21; per-contract txlist; eth_getCode latest; cast selectors. Internal/factory deployments by the bot contracts are not covered.',
  'n_contracts':len(out),'contracts':out},open('yoink_contracts.json','w'),indent=1)
for o in out: print(o['calls_by_year'],o['address'][:10],o['label'],o['created_utc'][:10],o['runtime_size_bytes'],o['txs_to_contract_total'],o['txs_from_yoink_eoa'],o['first_tx_utc'],o['last_tx_utc'],o['reverted_txs'])
