import json,datetime
out={o['tx']:o for o in json.load(open('_yoink_cb_all.json'))}
msgs=json.load(open('yoink_messages.json'))['messages']
ytx=json.load(open('_yoink_txlist.json'))
byh={t['hash']:t for t in ytx}
ct=json.load(open('_yoink_contract_txlists.json'))
for c,txs in ct.items():
    for t in txs: byh.setdefault(t['hash'],t)
def full(prefix):
    r=[h for h in byh if h.startswith(prefix)]
    assert len(r)==1,(prefix,r); return r[0]
def txinfo(h):
    t=byh[h]; o=out.get(h)
    scale=1.0
    d={'tx':h,'block':int(t['blockNumber']),'index':int(t['transactionIndex']),'time_utc':datetime.datetime.fromtimestamp(int(t['timeStamp']),datetime.UTC).strftime('%Y-%m-%dT%H:%M:%SZ'),'bot_contract':t['to'],'msg_value':t['value'],'status':'reverted' if t['isError']=='1' else 'success'}
    if o:
        d['coinbase_or_last_out_eth']=round(o['last_out_eth'],4)
        v=int(t['value'])
        if 0<v<1000: d['est_profit_eth_from_permille_rule']=round(o['last_out_eth']/(v/1000),3)
    return d
def window(a,b,botmin=1):
    r=[h for h,o in out.items() if a<=o['block']<=b and o['msg_value']>0 and o['sel']=='0x9846cd9e' and o['last_out_to']!='0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2']
    return sorted(r,key=lambda h:(out[h]['block'],out[h]['idx']))
def msg(prefix):
    m=[x for x in msgs if x['tx'].startswith(prefix)]; assert m,prefix; return m[0]
def mref(prefix):
    m=msg(prefix); return {'tx':m['tx'],'time_utc':m['time_utc'],'direction':m['direction'],'quote':m['text'][:240]}
E=[]
def add(**k): E.append(k)
dfx=[h for h in window(15941742,15941770) if out[h]['last_out_eth']>=1]
add(name='DFX Finance reentrancy (2022-11-10)',confidence='probable',in_our_incident_list=False,
    why='DHL attack tx 0x6bfd9e28.. at block 15941704 idx 72; Yoink gen0b (0x6c6b87d4) made 8 coinbase-paying txs in blocks 15941742-15941768 (37-64 blocks after the attacker), then funded its bot with 65 ETH (tx 0xe3b1af6c0d2f..). Victim message + Yoink reply "I frontran the real attacker" (2022-11-11).',
    yoink_txs=[txinfo(h) for h in dfx], total_coinbase_eth=round(sum(out[h]['last_out_eth'] for h in dfx),2),
    messages=[mref('0x0611b4d7'),mref('0xe72e71ed'),mref('0x24cb5728')],returned='not located (DFX asked for return; Yoink replied it would email)',note='gen0b bribe encoding is absolute (msg.value*1e11 wei), not per-mille.')
add(name='"$X" token LP-token burn mishap (2022-10-21)',confidence='strong',in_our_incident_list=False,
    why='Victim quoted tx hash 0xa1bca7d2ef.. (message 0xfd4aab0f.. / sender 0xb790a054..) is Yoink bot tx at idx 4; Yoink later states ~33 ETH profit, ~630 ETH holder losses, and declined to return ("botched LP token burn for X token").',
    yoink_txs=[txinfo(full('0xa1bca7d2ef'))],
    messages=[mref('0x7948d4ac'),mref('0xfd4aab0f'),mref('0x706ddb9a'),mref('0x702652cf')],returned='declined (message 2022-10-24); earlier offered 90% (2022-10-23) for Transit, a different incident')
add(name='Conic Finance crvUSD/ETH omnipool (2023-07-21)',confidence='strong',in_our_incident_list=False,
    why='DHL Conic02 attacker block 17743470; Yoink gen1 (0xd050e0a4) made 10 consecutive-block txs 17743471-17743480 (idx 0/4), ~1.4-2.7 ETH coinbase each; Yoink states it took 125.82 ETH, spent 35.48 ETH on gas/bribes, returned 81.307 ETH (10% bounty kept by agreement).',
    yoink_txs=[txinfo(h) for h in window(17743471,17743480)],
    messages=[mref('0x6382dad8'),mref('0xaf1535ea'),mref('0x9074a688'),mref('0xd9f71838')],
    returned=[{'eth':81.307,'tx':full('0xf56f34a092'),'note':'Yoink bot internal transfer to conicfinance.eth, block 17756778'}])
add(name='UniBank (2023-09-04)',confidence='probable',in_our_incident_list=False,
    why='Victim message "nice job man, lesson learnt" 2023-09-05 01:00; Yoink gen1 tx at 2023-09-04 21:22 with ~22.8 ETH coinbase (est. profit ~30.6 ETH); Yoink did not return (asked owner to email).',
    yoink_txs=[txinfo(full('0x632d90a9cd'))],messages=[mref('0x8171baab'),mref('0xc8f132b0')],returned='none located')
add(name='TaoPad reward extraction (2024-02-14)',confidence='strong',in_our_incident_list=False,
    why='Victim quoted Yoink tx 0x5853b7a0.. and their failed tx; Yoink returned 26.32 ETH ("entire bot profit") on 2024-02-15. Not an exploit by Yoink: it front-ran the project extracting its own rewards via a known bug.',
    yoink_txs=[txinfo(full('0x5853b7a0b0'))],messages=[mref('0x1c900a5c'),mref('0x20d4929e'),mref('0xa0346352')],returned=[{'eth':26.32,'tx':full('0xa034635252') if False else [h for h in byh if h.startswith('0xa03463523f')][0]}])
uz=[full(p) for p in ['0x2dfc3752e5','0xde7b7aedf8','0x14328e2991','0xbe1ffe49a8','0xaeb81988bb','0x73dad216e3','0x4a69a272d0']]
add(name='Unizen exploit (2024-03-08/09)',confidence='strong',in_our_incident_list=False,
    why='The 7 tx hashes in Unizen\'s message are Yoink gen2 txs in blocks 19393223-19393726 (DHL UnizenIO2 attacker block 19393361, UnizenIO 19393770). Yoink states profit 0.33 ETH + 13,566 USDT + 4,809 USDC; returned 90% of ETH profit (0.29808 ETH) and refused the rest (validator bribes).',
    yoink_txs=[txinfo(h) for h in uz],messages=[mref('0x0dc8ce3e'),mref('0xd06abff5'),mref('0x4840a6a4')],
    returned=[{'eth':0.29808,'tx':[h for h in byh if h.startswith('0xd06abff5')][0]},{'eth':0.12,'tx':[h for h in byh if h.startswith('0xc55c11a4')][0],'note':'2024-03-09 "Sent back bot profit, unfortunately most wasted on validator bribe" to 0xe2588450.. (event not identified; may be Unizen-related)'}])
add(name='MintSwap (2024-04-01)',confidence='strong',in_our_incident_list=False,
    why='Both tx hashes in MintSwap\'s message are Yoink gen2 txs (blocks 19563164/19563165); coinbase 14.4 + 54.5 ETH. Yoink: profit 101.8 ETH, ~9 ETH to validators; returned 91.62 ETH to the LP 0x5b03.. (tx 0x1d3c141c..).',
    yoink_txs=[txinfo(full('0xd2337efb82')),txinfo(full('0x29edec50fb'))],messages=[mref('0xfe502042'),mref('0x89af126f'),mref('0x07473e4c')],
    returned=[{'eth':91.62,'tx':full('0x1d3c141c46')}])
add(name='Airpuff uniETH vault (2024-04-05)',confidence='strong (but disputed as exploit)',in_our_incident_list=False,
    why='Airpuff\'s two hashes are Yoink gen2 txs (blocks 19588496/19588910, 33.6 and 22.8 ETH coinbase, 99.9% bribe). Yoink: "not sure I\'d classify a simple sandwich as an exploit"; no return seen.',
    yoink_txs=[txinfo(full('0xb8a5927f66')),txinfo(full('0x73ce81455c'))],messages=[mref('0x328eeb58'),mref('0xb3b3776a')],returned='none located')
add(name='Disputed: VY token tax-address (2024-04-03)',confidence='weak',in_our_incident_list=False,why='Student asks refund of VY purchase; Yoink: "not clear to me that the VY stuff was a hack". No tx identified.',yoink_txs=[],messages=[mref('0xed2745af'),mref('0xfe6d770d')],returned='none')
add(name='DANK BOY token rug-by-bug (2024-10-23)',confidence='strong',in_our_incident_list=False,
    why='Deployer message 03:04 UTC 2024-10-23; Yoink gen2 tx at 02:42 (block 21025366, 5.61 ETH coinbase). Yoink alleges serial rugger and sent 2.33 ETH "Courtesy of rugger" to 0x9d727911.. on 2024-10-28.',
    yoink_txs=[txinfo(full('0x6b37f89e83'))],messages=[mref('0xad7a3749'),mref('0xc7ca329b'),mref('0x7916c7b3')],returned=[{'eth':2.33,'tx':full('0x7916c7b30b'),'note':'donated to third party, not to the victim'}])
add(name='Erc20transfer access-control (DHL 2024-10-22)',confidence='probable',in_our_incident_list=False,
    why='DHL attack tx 0x7f2540af.. IS a Yoink gen2 tx (block 21019772 idx 0, 99.9% bribe, 5.57 ETH to coinbase) - the PoC lists the bot, not the attacker. Needs attacker identification.',
    yoink_txs=[txinfo(full('0x7f2540af4a'))],messages=[],returned='unknown')
add(name='SASHAToken price manipulation (DHL 2024-10-06)',confidence='weak-probable',in_our_incident_list=False,
    why='Yoink gen2 txs idx 0-2 in the block after DHL exploit block 20905302 (value 997/991/965).',
    yoink_txs=[txinfo(h) for h in ['0x03f1b8f1','0x1a640931','0x621b5b6a'] for h in [[x for x in byh if x.startswith(h)][0]]],messages=[],returned='unknown')
add(name='XBridge logic flaw (DHL 2024-04-24)',confidence='weak',in_our_incident_list=False,why='Yoink gen2 tx idx 13 in the DHL exploit block 19723701 (value 595).',yoink_txs=[txinfo([x for x in byh if x.startswith('0x32724a3c')][0])],messages=[],returned='unknown')
add(name='Peapods Finance (2025-07-09)',confidence='probable',in_our_incident_list=False,
    why='Peapods message 2025-07-10 offers 10% bounty; Yoink gen3 made 4 consecutive txs at block 22883324 (idx 1-4; 8.6/4.3/1.9/1.5 ETH coinbase) on 2025-07-09 18:09 UTC. Second Peapods message 2025-10-09: ~2 ETH leftover in the leverage manager; Yoink returned 1.416285 ETH (profit minus 10%) tx 0xcd6d475f...',
    yoink_txs=[txinfo(h) for h in sorted(window(22883324,22883324),key=lambda h:-out[h]['last_out_eth'])[:6]],messages=[mref('0xf24a9464'),mref('0x0a5694d3'),mref('0xcd6d475f')],returned=[{'eth':1.416285,'tx':full('0xcd6d475f')}])
add(name='Eywa (2026-02-01..03)',confidence='weak',in_our_incident_list=False,
    why='Eywa message (block 24382682) says tokens Yoink received came from an exploit; Eywa gives block 24364392 as time zero. Yoink gen3 big txs 2026-02-03 18:23 (23.7 ETH) and 18:41 (12.7 ETH) and 2026-02-01 18:27 (3.8 ETH) are candidates only.',
    yoink_txs=[txinfo(full('0xa931df3e66')),txinfo(full('0x2ff37310de')),txinfo(full('0x8b13422271'))],messages=[mref('0x7dc2fab0')],returned='unknown')
add(name='Attacker complaining Flashbots leaked tx to Yoink (2026-03-10)',confidence='probable',in_our_incident_list=False,
    why='Message at block 24627239 ("Why did you leak my attack transaction to yoink?"); Yoink gen3 tx at block 24627181 idx 0 (58 blocks earlier) paid 10.23 ETH coinbase (99.9% bribe).',
    yoink_txs=[txinfo(full('0x7acef47065'))],messages=[mref('0x325a67f8')],returned='none')
add(name='Early-days unmatched returns (2022-09)',confidence='weak',in_our_incident_list=False,
    why='2022-09-02 Yoink sent 7.5 ETH to 0xd74918a7.. ("Your contract is vulnerable, revoke permissions... Returning most of the funds as Eth"); candidate capture: gen0a tx 0x74d4ce54.. (2022-09-02 02:20, block 15456497 idx 0, 6.07 ETH coinbase). 2022-09-29 4.96 ETH sent to 0xeb9485f9.. "Please use Flashbots next time" - no capture tx identified.',
    yoink_txs=[txinfo(full('0x74d4ce5442'))],messages=[mref('0xb34c5e2c'),mref('0x94810459')],returned=[{'eth':7.5,'tx':full('0xb34c5e2cef')},{'eth':4.96,'tx':full('0x948104594d')}])
known=['ronin-2024','kelp-rseth-2026','defiplaza-2024','uncx-2026','time-2023','transitswap-2022','paraswap-2024','alkimiya-2025','sushi-rp2-2023','makina-2026','curve-vyper-2023','balancer-2025','securedfinance-2026','bifi-2026']
# big unexplained
big=[o for o in out.values() if o['sel']=='0x9846cd9e' and 990<=o['msg_value']<1000 and o['last_out_eth']>=60]
big.sort(key=lambda o:o['block'])
tr=json.load(open('scratch/yoink_cand_traces.json')) if True else {}
unexp=[]
for o in big:
    d=txinfo(o['tx']); t=tr.get(o['tx']); d['trace_calls']=t['n_calls'] if t else None
    unexp.append(d)
json.dump({'yoink_eoa':'0xfde0d1575ed8e06fbf36256bcdfa1f359281455a','method':'(1) 98 decoded on-chain messages (yoink_messages.json) matched to Yoink bot txs by quoted hashes and timing; (2) DeFiHackLabs exploit blocks (research/chain-scan/exploits_mainnet.json) +-3..5 blocks vs Yoink bot txs; (3) bot internal-transfer lists (coinbase = last outgoing ETH transfer, msg.value>0). Candidates only, not verified: no victim-call/calldata diffs done. Per-mille profit estimate only valid for gen2/gen3 (msg.value<1000); gen0/gen1 use absolute bribes.',
 'evidence_level':'candidate (in-block / message evidence only; pre-Aug-2023 has no mempool archive)',
 'already_in_incident_list_reference':known,'candidates':E,
 'unattributed_large_captures':{'filter':'gen2/gen3 txs with msg.value 990-999 per-mille and last outgoing ETH >= 60 (coinbase pay ~ whole profit). Most are probably market-dislocation arbs/liquidations, not exploit captures; listed so nothing is missed.','rows':unexp}},open('yoink_more_incidents.json','w'),indent=1,ensure_ascii=False)
print(len(E),len(unexp))
for e in E: print(e['name'][:50],e['confidence'],len(e['yoink_txs']))
