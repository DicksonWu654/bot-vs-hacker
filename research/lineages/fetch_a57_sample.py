import sys; sys.path.insert(0,str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'research/lineages'))
from lib import *
A='0xa57bd00134b2850b2a1c55860c9e9ea100fdd6cf'
res={}
sb=9710085
while sb<24000000:
    j=es({'module':'account','action':'txlist','address':A,'startblock':sb,'endblock':99999999,'page':1,'offset':1000,'sort':'asc'},f'w8_a57sample_{sb}')
    r=j.get('result')
    if not isinstance(r,list) or not r:
        print('empty after',sb,flush=True)
        # skip ahead
        sb+=400000
        if sb>24000000: break
        continue
    res[sb]=r
    print(sb,len(r),r[0]['blockNumber'],r[-1]['blockNumber'],r[0]['timeStamp'],r[-1]['timeStamp'],flush=True)
    last=int(r[-1]['blockNumber'])
    if len(r)<1000: break
    sb=max(last+1, sb+250000)
# latest pages
for p in (1,2):
    j=es({'module':'account','action':'txlist','address':A,'startblock':0,'endblock':99999999,'page':p,'offset':1000,'sort':'desc'},f'w8_a57desc_p{p}')
    r=j.get('result'); 
    if isinstance(r,list): res[f'desc{p}']=r; print('desc',p,len(r),r[0]['blockNumber'],r[-1]['blockNumber'],flush=True)
json.dump(res,open('scratch/a57_samples.json','w'))
print('done',flush=True)
