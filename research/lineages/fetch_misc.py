import sys; sys.path.insert(0,str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'research/lineages'))
from lib import *
import datetime
f=lambda x: datetime.datetime.fromtimestamp(int(x),datetime.UTC).strftime('%Y-%m-%d')
for a in ['0x8641df2d7c730a8a24db86693fc39f7a74dd4e9d','0x97c54b989236aa60d310b70a09578730bfe58294','0x56178a0d5f301baf6cf3e1cd53d9863437345bf9']:
    tx=txlist_all(a,'txlist','w8')
    json.dump(tx,open(f'scratch/txl_{a[:10]}.json','w'))
    print(a,len(tx), f(tx[0]['timeStamp']) if tx else None, f(tx[-1]['timeStamp']) if tx else None, flush=True)
