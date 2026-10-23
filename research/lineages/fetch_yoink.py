import sys; sys.path.insert(0,str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'research/lineages'))
from lib import *
Y='0xfde0d1575ed8e06fbf36256bcdfa1f359281455a'
tx=txlist_all(Y,'txlist','w8')
json.dump(tx,open(str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'research/lineages/_yoink_txlist.json'),'w'))
print('txlist',len(tx))
