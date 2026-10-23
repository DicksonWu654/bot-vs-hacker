import sys; sys.path.insert(0,str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'research/lineages'))
from lib import *
import datetime
f=lambda x: datetime.datetime.fromtimestamp(int(x),datetime.UTC).strftime('%Y-%m-%d')
S='scratch/'
# a69babef sampling + first/last
A='0xa69babef1ca67a37ffaf7a485dfff3382056e78c'
res={}
sb=15346000
while sb<26500000:
    j=es({'module':'account','action':'txlist','address':A,'startblock':sb,'endblock':99999999,'page':1,'offset':1000,'sort':'asc'},f'w8_a69sample_{sb}')
    r=j.get('result')
    if not isinstance(r,list) or not r: break
    res[sb]=r
    print('a69',sb,len(r),r[0]['blockNumber'],r[-1]['blockNumber'],f(r[0]['timeStamp']),f(r[-1]['timeStamp']),flush=True)
    sb=max(int(r[-1]['blockNumber'])+1,sb+300000)
for p in (1,):
    j=es({'module':'account','action':'txlist','address':A,'startblock':0,'endblock':99999999,'page':p,'offset':1000,'sort':'desc'},f'w8_a69desc_p{p}')
    if isinstance(j.get('result'),list): res['desc']=j['result']
json.dump(res,open(S+'a69_samples.json','w'))
print('a69 done',flush=True)
for a in ['0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0','0xc6093fd9cc143f9f058938868b2df2daf9a91d28','0xfa103c21ea2df71dfb92b0652f8b1d795e51cdef','0x95a64fc052fd875a19f9cebbce0aee1faa15bf9a','0x3a518964ff40ee733d30749a213d2e5c9ffb2b8c']:
    try:
        tx=txlist_all(a,'txlist','w8')
    except Exception as e:
        print(a,'ERR',e,flush=True); continue
    json.dump(tx,open(f'{S}txl_{a[:10]}.json','w'))
    print(a,len(tx), f(tx[0]['timeStamp']) if tx else None, f(tx[-1]['timeStamp']) if tx else None, flush=True)
print('done',flush=True)
