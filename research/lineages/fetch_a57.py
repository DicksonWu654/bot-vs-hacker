import sys; sys.path.insert(0,str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'research/lineages'))
from lib import *
A='0xa57bd00134b2850b2a1c55860c9e9ea100fdd6cf'
tx=txlist_all(A,'txlist','w8')
json.dump(tx,open('scratch/a57_tx.json','w'))
print('a57',len(tx),flush=True)
