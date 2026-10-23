import sys, json
sys.path.insert(0,str(__import__('pathlib').Path(__file__).resolve().parents[3] / 'scripts/lib'))
import rawfetch as rf
def trace(h):
    return rf.rpc("debug_traceTransaction",[h,{"tracer":"callTracer","tracerConfig":{"withLog":True}}],f"trace_tx_{h}")
def tx(h): return rf.rpc("eth_getTransactionByHash",[h],f"tx_{h}")
def rcpt(h): return rf.rpc("eth_getTransactionReceipt",[h],f"receipt_{h}")
def pr(f,d=0,maxd=99):
    ind='  '*d
    inp=f.get('input','')
    print(f"{ind}{f['type']} {f.get('from','')[:10]}->{f.get('to','')[:42]} val={int(f.get('value','0x0'),16)/1e18:.6g} sel={inp[:10]} len={(len(inp)-2)//2} {'ERR:'+f['error']+' '+str(f.get('revertReason','')) if f.get('error') else ''}")
    if d<maxd:
        for c in f.get('calls',[]) or []: pr(c,d+1,maxd)
if __name__=='__main__':
    h=sys.argv[1]; maxd=int(sys.argv[2]) if len(sys.argv)>2 else 99
    pr(trace(h),0,maxd)
