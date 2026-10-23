"""Compact basic-block disassembler for runtime bytecode hex files. Usage: disasm.py file.hex [start_hex end_hex]"""
import sys, pathlib
OPS = {0:"STOP",1:"ADD",2:"MUL",3:"SUB",4:"DIV",5:"SDIV",6:"MOD",7:"SMOD",8:"ADDMOD",9:"MULMOD",0xa:"EXP",0xb:"SIGNEXTEND",
0x10:"LT",0x11:"GT",0x12:"SLT",0x13:"SGT",0x14:"EQ",0x15:"ISZERO",0x16:"AND",0x17:"OR",0x18:"XOR",0x19:"NOT",0x1a:"BYTE",0x1b:"SHL",0x1c:"SHR",0x1d:"SAR",
0x20:"KECCAK",0x30:"ADDRESS",0x31:"BALANCE",0x32:"ORIGIN",0x33:"CALLER",0x34:"CALLVALUE",0x35:"CALLDATALOAD",0x36:"CALLDATASIZE",0x37:"CALLDATACOPY",
0x38:"CODESIZE",0x39:"CODECOPY",0x3a:"GASPRICE",0x3b:"EXTCODESIZE",0x3c:"EXTCODECOPY",0x3d:"RETURNDATASIZE",0x3e:"RETURNDATACOPY",0x3f:"EXTCODEHASH",
0x40:"BLOCKHASH",0x41:"COINBASE",0x42:"TIMESTAMP",0x43:"NUMBER",0x44:"PREVRANDAO",0x45:"GASLIMIT",0x46:"CHAINID",0x47:"SELFBALANCE",0x48:"BASEFEE",
0x50:"POP",0x51:"MLOAD",0x52:"MSTORE",0x53:"MSTORE8",0x54:"SLOAD",0x55:"SSTORE",0x56:"JUMP",0x57:"JUMPI",0x58:"PC",0x59:"MSIZE",0x5a:"GAS",0x5b:"JUMPDEST",0x5f:"PUSH0",
0xa0:"LOG0",0xa1:"LOG1",0xa2:"LOG2",0xa3:"LOG3",0xa4:"LOG4",0xf0:"CREATE",0xf1:"CALL",0xf2:"CALLCODE",0xf3:"RETURN",0xf4:"DELEGATECALL",0xf5:"CREATE2",0xfa:"STATICCALL",0xfd:"REVERT",0xfe:"INVALID",0xff:"SELFDESTRUCT"}
for i in range(1,33): OPS[0x5f+i]=f"PUSH{i}"
for i in range(1,17): OPS[0x7f+i]=f"DUP{i}"; OPS[0x8f+i]=f"SWAP{i}"
def disasm(code):
    i=0; out=[]
    while i<len(code):
        op=code[i]; n=OPS.get(op,f"OP_{op:02x}")
        if 0x60<=op<=0x7f:
            k=op-0x5f; d=code[i+1:i+1+k].hex(); out.append((i,n,d)); i+=1+k
        else: out.append((i,n,"")); i+=1
    return out
if __name__=="__main__":
    code=bytes.fromhex(pathlib.Path(sys.argv[1]).read_text().strip()[2:])
    lo=int(sys.argv[2],16) if len(sys.argv)>2 else 0; hi=int(sys.argv[3],16) if len(sys.argv)>3 else len(code)
    line=[];start=None
    for off,n,d in disasm(code):
        if off<lo or off>=hi: continue
        if n=="JUMPDEST" and line: print(f"{start:04x}: "+" ".join(line)); line=[]
        if not line: start=off
        line.append(n if not d else (f"{n.replace('PUSH','P')}:{d}" if len(d)<=8 else f"{n.replace('PUSH','P')}:{d[:12]}..{len(d)//2}B"))
        if n in("JUMP","JUMPI","STOP","RETURN","REVERT","INVALID","SELFDESTRUCT"):
            print(f"{start:04x}: "+" ".join(line)); line=[]
    if line: print(f"{start:04x}: "+" ".join(line))
