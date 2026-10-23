import json,collections,datetime
Y='0xfde0d1575ed8e06fbf36256bcdfa1f359281455a'
internal=json.load(open('_yoink_internal.json'))
ytx=json.load(open('_yoink_txlist.json'))
ct=json.load(open('_yoink_contract_txlists.json'))
tx={}
for c,txs in ct.items():
    for t in txs: tx[t['hash']]=t
for t in ytx: tx[t['hash']]=t
iso=lambda x: datetime.datetime.fromtimestamp(int(x),datetime.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
per=collections.defaultdict(list)
for bot,rows in internal.items():
    for r in rows:
        if r['isError']=='0' and r['from']==bot and int(r['value'])>0 and r['type']=='call':
            per[r['hash']].append((r['traceId'],r['to'],int(r['value'])))
out=[]
for h,lst in per.items():
    t=tx.get(h)
    if not t or t['from']!=Y: continue
    # last outgoing (coinbase pay is last); exclude transfers to Y itself
    cand=[x for x in lst if x[1]!=Y]
    if not cand: continue
    last=cand[-1]
    val=int(t['value'])
    out.append({'tx':h,'block':int(t['blockNumber']),'idx':int(t['transactionIndex']),'time':iso(t['timeStamp']),'bot':t['to'],'msg_value':val,'last_out_to':last[1],'last_out_eth':last[2]/1e18,'n_out':len(cand),'sum_out_eth':sum(x[2] for x in cand)/1e18,'gas_price_gwei':int(t['gasPrice'])/1e9,'sel':t['input'][:10]})
out.sort(key=lambda x:-x['last_out_eth'])
json.dump(out,open('_yoink_cb_all.json','w'))
print(len(out))
for o in out[:60]:
    print(o['time'][:10],o['block'],o['idx'],o['tx'][:12],o['bot'][:8],'val',o['msg_value'],'cb',round(o['last_out_eth'],3),'sum',round(o['sum_out_eth'],3),o['n_out'])
