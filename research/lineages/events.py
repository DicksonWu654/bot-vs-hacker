import json,collections
out=json.load(open('_yoink_cb_all.json')); m=json.load(open('_miners.json'))
ytx=json.load(open('_yoink_txlist.json'))
Y='0xfde0d1575ed8e06fbf36256bcdfa1f359281455a'
events=[
('DFX Finance 2022-11-10',15937000,15942921),
('X token LP burn 2022-10-21/24',15797000,15800000),
('Conic Finance 2023-07-21/22',17743400,17743500),
('Unibank 2023-09',18060000,18066862),
('TaoPad 2024-02',19218000,19226632),
('Unizen 2024-03-08/09',19390000,19394743),
('MintSwap 2024-04-01',19560000,19563822),
('Airpuff uniETH 2024-04-05',19585000,19589655),
('GlueX 2024-11',21128000,21138160),
('Peapods 2025-07',22878000,22888679),
('Eywa 2026-02',24362000,24382682),
('2022-09-02 vulnerable contract (7.5 ETH sent)',15452000,15460766),
('2022-09-08 team-up',15495000,15497737),
('2022-09-29 use Flashbots (4.96 ETH sent)',15637000,15641343),
('DANK BOY rug 2024-10-23',21020000,21025474),
('2025-07-07 wrong price',22860000,22867563),
('2026-03-10 leaked attack tx',24620000,24627239),
('2026-05-09 missed zero LP',25050000,25056803),
('2025-11-02 LP mevved',23690000,23710119),
]
res=[]
for name,a,b in events:
    c=[o for o in out if a<=o['block']<=b and o['sel']=='0x9846cd9e' and o['msg_value']>0 and o['last_out_to']!='0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2']
    c.sort(key=lambda o:-o['last_out_eth'])
    print('==',name,a,b,len(c))
    for o in c[:4]:
        print('  ',o['time'][:16],o['block'],o['idx'],o['tx'],o['bot'][:8],o['msg_value'],round(o['last_out_eth'],2),'est_profit',round(o['last_out_eth']/(o['msg_value']/1000),1) if o['msg_value']<1000 else '')
