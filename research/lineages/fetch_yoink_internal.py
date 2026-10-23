import sys; sys.path.insert(0,str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'research/lineages'))
from lib import *
cs=['0x6980a47bee930a4584b09ee79ebe46484fbdbdd0','0x80bf7db69556d9521c03461978b8fc731dbbd4e4','0xd050e0a4838d74769228b49dff97241b4ef3805d','0x6c6b87d44d239b3750bf9badce26a9a0a3d2364e','0x97f0fa1e5bf44f0dbd8dc5ee5e0d017667ae0c34','0x8788a7cfd63cf06d0d7716c6a66f54b58248c896','0x73a987534554c733b8f2af86ea7e9a70f4cde222','0x0d7ad6effd1c6e94e86e4daa7b7c7ef0ab3427d5']
out={}
for c in cs:
    r=txlist_all(c,'txlistinternal','w8')
    out[c]=r
    print(c,len(r),flush=True)
    json.dump(out,open(str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'research/lineages/_yoink_internal.json'),'w'))
print('done',flush=True)
