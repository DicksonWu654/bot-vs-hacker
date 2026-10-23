import sys, json, time
sys.path.insert(0,str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'research/lineages'))
from lib import *
out=json.load(open(str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'research/lineages/_yoink_cb_all.json')))
top=[o for o in out if o['sel']=='0x9846cd9e' and o['last_out_eth']>=20]
print(len(top),flush=True)
blocks=sorted(set(o['block'] for o in top))
m={}
for b in blocks:
    for i in range(4):
        try:
            r=rf.rpc('eth_getBlockByNumber',[hex(b),False],key=f'w8_block_{b}')
            m[b]=r['miner'].lower(); break
        except Exception as e:
            time.sleep(3)
json.dump(m,open(str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'research/lineages/_miners.json'),'w'))
print('done',len(m),flush=True)
