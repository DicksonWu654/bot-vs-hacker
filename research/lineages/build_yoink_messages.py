import json,datetime,collections
Y='0xfde0d1575ed8e06fbf36256bcdfa1f359281455a'
ytx=json.load(open('_yoink_txlist.json'))
ct=json.load(open('_yoink_contract_txlists.json'))
conts=set(x['contractAddress'] for x in ytx if x['to']=='')
iso=lambda x: datetime.datetime.fromtimestamp(int(x),datetime.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
def printable(s):
    return len(s)>=3 and sum(1 for ch in s if ch.isprintable() or ch in '\n\r\t')/len(s)>0.93
def dec(inp):
    h=inp[2:]
    if not h: return None,None
    b=bytes.fromhex(h)
    try:
        s=b.replace(b'\xaa',b'\n').decode('utf-8')
        if printable(s): return s,'utf8'+('+0xaa-as-newline' if b'\xaa' in b else '')
    except Exception: pass
    if len(h)%2==0 and h[0]=='0':   # odd-nibble shifted ASCII (seen once: blk 15820283)
        h2=h[1:]+'0' if False else h[1:]
        try:
            b2=bytes.fromhex(h2[:len(h2)//2*2])
            s=b2.replace(b'\xaa',b'\n').decode('utf-8')
            if printable(s): return s,'utf8-after-dropping-first-nibble'
        except Exception: pass
    return None,None
seen=set(); msgs=[]
def consider(t,src):
    if t['hash'] in seen or t['to']=='': return
    if t['to'] in conts and t['from']==Y: return      # bot calls
    if t['from']==Y and t['to']==Y: return           # self cancels
    s,how=dec(t['input'])
    if not s: return
    seen.add(t['hash'])
    direction='from_yoink' if t['from']==Y else 'to_yoink' if t['to']==Y else 'to_yoink_bot_contract'
    msgs.append({'tx':t['hash'],'block':int(t['blockNumber']),'time_utc':iso(t['timeStamp']),'direction':direction,
      'from':t['from'],'to':t['to'],'value_eth':int(t['value'])/1e18,'decode':how,'text':s.strip(),'source':src,'is_error':t['isError']})
for t in ytx: consider(t,'Yoink EOA txlist')
for c,txs in ct.items():
    for t in txs: consider(t,f'txlist of bot contract {c}')
msgs.sort(key=lambda m:m['block'])
json.dump({'yoink_eoa':Y,'decoding':'Etherscan txlist input data decoded as UTF-8 (0xaa byte = newline); one message needed a first-nibble shift. Covers txs of the EOA and txs sent to Yoink bot contracts. Blockscan Chat messages are off-chain and not included.','count':len(msgs),
 'by_direction':dict(collections.Counter(m['direction'] for m in msgs)),'messages':msgs},open('yoink_messages.json','w'),indent=1,ensure_ascii=False)
print(len(msgs),collections.Counter(m['direction'] for m in msgs),collections.Counter(m['decode'] for m in msgs))
