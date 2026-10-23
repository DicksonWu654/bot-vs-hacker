import sys, json, time
sys.path.insert(0,str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'research/lineages'))
from lib import *
out=json.load(open(str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'research/lineages/_yoink_cb_all.json')))
c=[o for o in out if o['sel']=='0x9846cd9e' and 990<=o['msg_value']<1000 and o['last_out_eth']>=30]
c+= [o for o in out if o['tx'].startswith('0xa1bca7d2ef') or o['tx'].startswith('0xde27218967')]
res={}
SKIP={'0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2'}
def walk(n,depth,acc):
    for ch in n.get('calls',[]) or []:
        acc.append((depth,ch.get('type'),ch.get('from'),ch.get('to'),(ch.get('input') or '')[:10],int(ch.get('value','0x0'),16)/1e18,bool(ch.get('error'))))
        walk(ch,depth+1,acc)
for o in c:
    h=o['tx']
    try:
        tr=rf.rpc('debug_traceTransaction',[h,{'tracer':'callTracer'}],key=f'w8_trace_{h}')
    except Exception as e:
        print(h,'ERR',str(e)[:80]); time.sleep(3); continue
    acc=[]; walk(tr,1,acc)
    res[h]={'meta':o,'calls':acc[:400],'n_calls':len(acc)}
    tg={}
    for d,ty,fr,to,sel,val,err in acc:
        if to and to not in SKIP and to!=o['bot'] and ty in('CALL','STATICCALL','DELEGATECALL'):
            tg.setdefault((to,sel),0); tg[(to,sel)]+=1
    top=sorted(tg.items(),key=lambda kv:-kv[1])[:8]
    print(o['time'][:10],h[:12],o['block'],o['idx'],'cb',round(o['last_out_eth'],1),'ncalls',len(acc),[(k[0][:10],k[1],v) for k,v in top],flush=True)
json.dump(res,open('scratch/yoink_cand_traces.json','w'))
