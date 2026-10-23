import sys; sys.path.insert(0,str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'research/lineages'))
from lib import *
tx=json.load(open(str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'research/lineages/_yoink_txlist.json')))
cs=[t['contractAddress'] for t in tx if t['to']=='']
out={}
for c in cs:
    r=txlist_all(c,'txlist','w8')
    out[c]=r
    print(c,len(r),flush=True)
json.dump(out,open(str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'research/lineages/_yoink_contract_txlists.json'),'w'))
print('done',flush=True)
