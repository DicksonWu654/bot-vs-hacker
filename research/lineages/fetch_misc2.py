import sys; sys.path.insert(0,str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'research/lineages'))
from lib import *
import datetime
f=lambda x: datetime.datetime.fromtimestamp(int(x),datetime.UTC).strftime('%Y-%m-%d')
S='scratch/'
for a in ['0x8a14ce0fecbefdcc612f340be3324655718ce1c1','0x26bce6ecb5b10138e4bf14ac0ffcc8727fef3b2e','0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0','0xc6093fd9cc143f9f058938868b2df2daf9a91d28','0xfa103c21ea2df71dfb92b0652f8b1d795e51cdef','0xa69babef1ca67a37ffaf7a485dfff3382056e78c','0x95a64fc052fd875a19f9cebbce0aee1faa15bf9a','0x3a518964ff40ee733d30749a213d2e5c9ffb2b8c']:
    tx=txlist_all(a,'txlist','w8')
    json.dump(tx,open(f'{S}txl_{a[:10]}.json','w'))
    print(a,len(tx), f(tx[0]['timeStamp']) if tx else None, f(tx[-1]['timeStamp']) if tx else None, flush=True)
print('done',flush=True)
