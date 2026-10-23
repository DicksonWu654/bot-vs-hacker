import json,collections,datetime,os
S='scratch/'
iso=lambda x: datetime.datetime.fromtimestamp(int(x),datetime.UTC).strftime('%Y-%m-%d')
res={}
for a in ['0x8641df2d','0x56178a0d','0x97c54b98','0x8a14ce0f','0x26bce6ec','0x267be1c1','0xc6093fd9','0xfa103c21','0xa69babef','0x95a64fc0','0x3a518964']:
    p=S+f'txl_{a}.json'
    if not os.path.exists(p): continue
    tx=json.load(open(p))
    full=tx[0]['from'] if tx and tx[0]['from'].startswith(a) else None
    addr=None
    for t in tx[:200]:
        for k in('from','to'):
            if t[k].startswith(a): addr=t[k]
    me=addr
    sent=[t for t in tx if t['from']==me]
    recv=[t for t in tx if t['to']==me]
    d={'address':me,'txs_in_txlist':len(tx),'sent':len(sent),'received':len(recv),'first':iso(tx[0]['timeStamp']),'last':iso(tx[-1]['timeStamp']),
       'first_tx':tx[0]['hash'],'by_year':dict(sorted(collections.Counter(iso(t['timeStamp'])[:4] for t in tx).items())),
       'top_targets_of_sent':collections.Counter(t['to'] for t in sent).most_common(6),
       'eth_in_from':collections.Counter({}),'funders':[]}
    fin=collections.defaultdict(lambda:[0,0.0])
    for t in recv:
        if t['from']!=me and int(t['value'])>0 and t['isError']=='0':
            fin[t['from']][0]+=1; fin[t['from']][1]+=int(t['value'])/1e18
    d['eth_in_from']=None
    d['funders']=sorted(([k,v[0],round(v[1],3)] for k,v in fin.items()),key=lambda x:-x[2])[:8]
    fout=collections.defaultdict(lambda:[0,0.0])
    for t in sent:
        if int(t['value'])>0 and t['isError']=='0' and t['to']!=me:
            fout[t['to']][0]+=1; fout[t['to']][1]+=int(t['value'])/1e18
    d['eth_out_to']=sorted(([k,v[0],round(v[1],3)] for k,v in fout.items()),key=lambda x:-x[2])[:8]
    d['creations']=[[iso(t['timeStamp']),t['contractAddress']] for t in sent if t['to']=='']
    res[me]=d
    print(me[:10],len(tx),d['first'],d['last'],d['funders'][:3],d['eth_out_to'][:3])
json.dump(res,open('_a57_hubstats.json','w'),indent=1)
