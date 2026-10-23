import json, collections, datetime, os
S = 'scratch/'
H = str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'research/lineages')
iso = lambda x: datetime.datetime.fromtimestamp(int(x), datetime.UTC).strftime('%Y-%m-%d')
hub = json.load(open(H + '_a57_hubstats.json'))
codes = json.load(open(H + '_a57_codes.json'))
cre = json.load(open(H + '_creations.json'))
execs = json.load(open(H + '_a57_executors.json'))
w2 = json.load(open(S + 'w2_a57rows.json'))
a57s = json.load(open(S + 'a57_samples.json'))
a69s = json.load(open(S + 'a69_samples.json'))
slim = [json.loads(l) for l in open(S + 'a57_slim.jsonl')]

# ---- proxy activity
slim_callers = collections.defaultdict(lambda: [10**18, 0, 0, 0])
for r in slim:
    e = slim_callers[r[3]]; e[0] = min(e[0], r[2]); e[1] = max(e[1], r[2]); e[2] += 1; e[3] += r[4]
months = collections.Counter(iso(r[2])[:7] for r in slim)
sample_rows = []
for k, r in a57s.items():
    if str(k).startswith('desc') or not r: continue
    span = (int(r[-1]['timeStamp']) - int(r[0]['timeStamp'])) / 86400
    sample_rows.append({'start_block': int(r[0]['blockNumber']), 'date': iso(r[0]['timeStamp']), 'txs': len(r), 'span_days': round(span, 3),
                        'est_txs_per_day': round(len(r) / span) if span > 0 else None,
                        'distinct_callers': len(set(t['from'] for t in r)),
                        'top_execute_target': collections.Counter(('0x' + t['input'][34:74]) for t in r if t['input'].startswith(('0x1cff79cd', '0x78e111f6'))).most_common(2),
                        'failed': sum(1 for t in r if t['isError'] == '1')})
sample_callers = collections.defaultdict(lambda: [10**18, 0, 0])
for r in a57s.values():
    for t in r:
        e = sample_callers[t['from']]; e[0] = min(e[0], int(t['timeStamp'])); e[1] = max(e[1], int(t['timeStamp'])); e[2] += 1
a69callers = collections.defaultdict(lambda: [10**18, 0, 0])
for r in a69s.values():
    for t in r:
        e = a69callers[t['from']]; e[0] = min(e[0], int(t['timeStamp'])); e[1] = max(e[1], int(t['timeStamp'])); e[2] += 1
a57_all = set(slim_callers) | set(sample_callers)
overlap = a57_all & set(a69callers)
a69_rows = []
for k, r in a69s.items():
    if k == 'desc' or not r: continue
    span = (int(r[-1]['timeStamp']) - int(r[0]['timeStamp'])) / 86400
    a69_rows.append({'start_block': int(r[0]['blockNumber']), 'date': iso(r[0]['timeStamp']), 'txs': len(r), 'span_days': round(span, 3), 'distinct_callers': len(set(t['from'] for t in r))})

contracts = []
def C(addr, role, note, created_by=None):
    c = cre.get(addr, {})
    k = codes.get(addr, {})
    contracts.append({'address': addr, 'role': role, 'created': iso(c['timestamp']) if c else None, 'creator': c.get('contractCreator'), 'factory': c.get('contractFactory') or None,
                      'creation_tx': c.get('txHash'), 'runtime_bytes': k.get('size'), 'code_sha256_16': k.get('sha'), 'selectors': k.get('selectors'), 'note': note})
C('0x76aca078357b6be9f13a0e68bcec91d05b796192', 'factory-of-factory', 'First operator deploy (2019-01-22, 4,721 B); selectors 0x29710388/0xf3701da2(address)/0x8e1a55fc; created the executor factory 0xf3c9d00c.')
C('0xf3c9d00c06e6ceef470510ed599bd30569a2ddc6', 'executor factory', 'deploy(bytes) 0x7ed0c3b2 / 0x8bf4515c. EVERY top executor of proxy a57bd001 (30 checked) and the 2021/2022 executors 0x3a518964 and 0x0e113904 were deployed through it.')
C('0xec91d89047e81233bf78c614599c64f179006d9f', 'early helper', '2019-03-07, same 4-selector family as 0x76aca078.')
C('0x31dd6ba1b27992ab0421230df5655d655d990420', 'proxy v0', '2019-03-09 first auth-proxy: execute(address,bytes) 0x1cff79cd + rely/deny + setCache.')
C('0xad9eb619ce1033cc710d9f9806a2330f85875f22', 'proxy v0', '2019-03-09, 1,884 B, same ABI family.')
C('0xa57bd00134b2850b2a1c55860c9e9ea100fdd6cf', 'main proxy ("0xa57")', 'DSProxy-like with wards: execute(address,bytes) 0x1cff79cd (delegatecall into an executor), executeFFsYo 0x78e111f6, rely/deny/wards, setCache. 459k txs counted exactly through 2020-08; sample-density estimate 1-4 million txs 2019-03 .. 2023-03, sparse to 2026-05.')
C('0x9799b475dec92bd99bbdd943013325c36157f383', 'proxy', '2019-09-18, same ABI as 0xa57.')
C('0xfa103c21ea2df71dfb92b0652f8b1d795e51cdef', 'proxy / pass-through router', '2020-01-18, same ABI as 0xa57; the DODO-return USDT passed through it (tx 0x6e743db0..); deployer 0x8641df2d sent it ETH 531 times.')
C('0x0a051c99a3b05533c07e9ad5c11a0ec7e0f9f326', 'other', '2020-05-19, different 18-selector ABI (token/approval helper?).')
C('0x031014f655798f56cf1f9bb4dbd6c2f39a76a46e', 'other', '2021-03-27, single function 0x07388e83(address,uint256,uint256,uint256[]).')
C('0x4cb18386e5d1f34dc6eea834bf3534a970a3f8e7', 'proxy (2022)', '2022-02-26, ABI = a57 family + extras (12 selectors); driven by EOA 0x26bce6ec 32,684 times.')
C('0x95a64fc052fd875a19f9cebbce0aee1faa15bf9a', 'proxy factory (2022)', '2022-06-24, 2,083 B, 0x61ff715f(uint256,bytes) + wards; created 0xa69babef.')
C('0xa69babef1ca67a37ffaf7a485dfff3382056e78c', 'main proxy 2022+ (Earning.Farm bot)', 'ABI superset of 0xa57bd001 (adds batch rely/deny 0x97645e37/0xc9892a5f and 0xfa461e33 callback); 11,793 B. All of the 0xa57 fleet moved here from 2022-08-22.')
C('0x3a518964ff40ee733d30749a213d2e5c9ffb2b8c', 'executor used by Cheetah 2021', 'Created 2021-02-16 by 0x56178a0d via factory 0xf3c9d00c. Interface 0x1cff79cd + 0x80d6c5a1 batch-call + 0xec556889. Received the stolen USDT in DODO tx 0x75d4765d and forwarded it to 0x56178a0d.')
C('0x0e113904cb1d53cabb324927dffae2f8f6705111', 'EF helper 2022', 'Created 2022-08-22 by 0x56178a0d via factory (0x11fb858e..). Same interface as 0x3a518964 (0x1cff79cd, 0x80d6c5a1, 0xec556889) - the vault caller in the Earning.Farm tx.')

eoas = []
def E(addr, role, note):
    h = hub.get(addr)
    d = {'address': addr, 'role': role, 'note': note}
    if h:
        d.update({'txs': h['txs_in_txlist'], 'first_utc': h['first'], 'last_utc': h['last'], 'by_year': h['by_year'], 'top_targets': h['top_targets_of_sent'][:4], 'eth_funders': h['funders'][:6], 'eth_out_to': h['eth_out_to'][:5]})
    eoas.append(d)
E('0x8641df2d7c730a8a24db86693fc39f7a74dd4e9d', 'HUB deployer / root ward', 'Deployed the proxies, the executor factory, 0x95a64fc0 -> 0xa69babef; relied 79 wards on a57bd001. 30.9k txs, mostly 2019-2020.')
E('0x56178a0d5f301baf6cf3e1cd53d9863437345bf9', 'HUB capital/owner wallet', 'Receives Cheetah USDT (DODO 2021), lent 14,707 WETH to EF helper (2022), deployed executors 0x3a518964 / 0x0e113904, funds 8641df2d. Itself an arb EOA with 185k txs.')
E('0x97c54b989236aa60d310b70a09578730bfe58294', 'ward manager', 'Relied 200 wards on a57bd001; deployed executors; funded 0x26bce6ec first (2019-11-10).')
E('0xc6093fd9cc143f9f058938868b2df2daf9a91d28', 'first ward (2019-03-27)', 'First caller of a57bd001 (5,419 txs 2019-03..07); deployed early executors; first funded the Cheetah EOA 0x8a14ce0f on 2020-05-12.')
E('0x8a14ce0fecbefdcc612f340be3324655718ce1c1', 'DODO 2021 "Cheetah" EOA', 'First funded by 0xc6093fd9 (2020-05-12). 2,320 txs to a57bd001, then 63,041 to a69babef (through 2025-12-21).')
E('0x26bce6ecb5b10138e4bf14ac0ffcc8727fef3b2e', 'Earning.Farm 2022 EOA', 'First funded by 0x97c54b98 (2019-11-10). 60,055 txs to a57bd001 (2019-11..2023-03-13), 173,954 to a69babef (2022-08-22..2025-12-24), 32,684 to 0x4cb18386.')
E('0x9787ffbd8ac920317ba43333913419f14489aa5f', 'recurring funder', 'Ward since 2019-08; funds both 0x8a14ce0f (38x, 402 ETH) and 0x26bce6ec (145x, 1,608 ETH); still topping up a69babef in 2026-07.')
E('0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0', 'upstream capital funder', 'Sent 8641df2d 14,091 ETH over 19 txs.')

executors = execs
w2rows = [{k: r[k] for k in ('exploit', 'date', 'exploit_block', 'exploit_tx', 'tx', 'block', 'index', 'rel', 'status', 'from', 'to', 'cb_eth', 'prio', 'score', 'calls_to_victims')} for r in w2]
w2big = sorted([r for r in w2rows if r['cb_eth'] >= 0.5], key=lambda r: -r['cb_eth'])

out = {
 'question': 'Is the DODO 2021 "Cheetah" (EOA 0x8a14ce0f via proxy 0xa57bd001), the Earning.Farm 2022 bot (EOA 0x26bce6ec -> contract 0xa69babef, owner wallet 0x56178a0d) and the anonymous-sender profiles "0xa57 family" one operator?',
 'verdict': 'YES - one operator (high confidence, not proof of identity). It is a large general MEV/arbitrage operation running a fleet of hundreds of EOAs (wards) through a family of auth-proxy contracts and rotating executors; it is not an exploit-hunter. Cheetah and the EF bot are two EOAs/eras of the same deployment.',
 'evidence': [
  {'n': 1, 'fact': '0x8641df2d deployed 0xa57bd001 (2019-03-26, tx 0x0d8fc644..) AND 0x95a64fc0 (2022-06-24) which created 0xa69babef (2022-08-15, tx 0x4d373b2c..). 0xa69babef exposes every selector of 0xa57bd001 plus batch-rely/deny and a callback.'},
  {'n': 2, 'fact': 'Cheetah\'s DODO tx 0x75d4765d.. (block 12000167): 1,139,456.204396 USDT moved bypass contract 0x910fd17b -> executor 0x3a518964 -> 0x56178a0d. 0x56178a0d is the capital wallet that lent 14,707.09 WETH (got 15,187.10 back) in the Earning.Farm tx 0x1f1aba5b.. (block 15746200).', 'refs': ['data/raw/rpc/receipt_0x75d4765d...json', 'incidents/earningfarm-2022/incident.json']},
  {'n': 3, 'fact': '0x56178a0d itself deployed executor 0x3a518964 (2021-02-16) and EF helper 0x0e113904 (2022-08-22), both through the executor factory 0xf3c9d00c; both share the interface 0x1cff79cd/0x80d6c5a1/0xec556889.'},
  {'n': 4, 'fact': 'Executor factory 0xf3c9d00c was created by 0x8641df2d in 2019-01. All 30 top executors of 0xa57bd001 (100% of the 458,903 execute() calls in the complete 2019-03..2020-08 scan) came from it, deployed by wards of the proxy (0xc6093fd9, 0x97c54b98, 0xcedb4f8d, 0xef08524e, 0x00e34a4e, 0x9787ffbd, 0xc39eaabe, 0x8641df2d, 0x519b9ef6).'},
  {'n': 5, 'fact': 'Ward set: 8641df2d (79 calls) and 0x97c54b98 (200 calls) relied 279 distinct EOAs by 2019-11 (581 rely calls through 2020-08). 568 distinct callers by 2020-08; ~370 of the 378 callers seen in 30 sampled a69babef pages also called 0xa57bd001.'},
  {'n': 6, 'fact': 'Cheetah EOA 0x8a14ce0f first funded by ward 0xc6093fd9 (2020-05-12, tx 0x2cd7a97c..); EF EOA 0x26bce6ec first funded by ward 0x97c54b98 (2019-11-10). Both are topped up by the same wallet 0x9787ffbd (38x and 145x) and by hub 0x8641df2d. 0x8a14ce0f sent 62,464 txs to 0xa69babef and 0x26bce6ec 166k: both EOAs drive the EF contract.'},
  {'n': 7, 'fact': 'Migration: 0xa57bd001 traffic stops around 2023-03-13 (last bulk), while every fleet EOA starts calling 0xa69babef on 2022-08-22, a week after its creation (blk 15346875).'},
  {'n': 8, 'fact': 'The 0xa57 proxy and the EF contract are NOT the same bytecode (3,135 B vs 11,793 B): "implementation upgrade" happens at two levels: (a) executor rotation behind the proxy (30+ delegate targets 2019-2022; see executors), (b) proxy replacement by a larger superset (2022-08).'}],
 'caveats': ['Same operator != named identity; no label for the owner of 0x56178a0d/0x8641df2d was sought.',
             'Etherscan txlist is complete for hubs/EOAs; 0xa57bd001 txlist is complete through block 10.59M (2020-08-04, 459,495 txs) then sampled (1,000 consecutive txs every 250k blocks to block 16.96M, plus the newest 2,000); a69babef sampled every 300k blocks. Counts after 2020-08 are estimates from sample density.',
             'Slim 0xa57bd001 rows through 2020-08 are in scratch (not saved raw to avoid GBs); raw pages up to block 9.71M and the sample pages are in data/raw/etherscan/w8_*.',
             'Pre-Aug-2023 = in-block evidence only.'],
 'contracts': contracts,
 'eoas': eoas,
 'proxy_0xa57bd001': {
   'created': '2019-03-26T block 7445835 by 0x8641df2d', 'first_call': '2019-03-27', 'last_tx': {'time': '2026-05-07T11:14:11Z', 'tx': '0x5f2e65f4e735c82d0a3186c1eb55e16461e1b84f7886ab5eec39c851118d907c', 'note': 'plain ETH transfer; last execute() ~2023-03'},
   'complete_scan_through_block': 10591282, 'txs_in_complete_part': len(slim), 'calls_per_month_complete_part': dict(sorted(months.items())),
   'distinct_callers_complete_part': len(slim_callers), 'sample_pages': sorted(sample_rows, key=lambda r: r['start_block']),
   'callers_complete_part_top': sorted(([a, v[2], iso(v[0]), iso(v[1]), v[3]] for a, v in slim_callers.items()), key=lambda x: -x[1])[:40],
   'ward_rely_calls': {'0x8641df2d': 79, '0x97c54b98': 200, 'distinct_wards_by_2019-11': 279}},
 'proxy_0xa69babef': {'created': '2022-08-15 via factory 0x95a64fc0', 'first_call': '2022-08-22', 'last_execute': '2025-12-24 (0x26bce6ec)', 'last_tx': {'time': '2026-07-30T00:15:59Z', 'tx': '0x0e5db9e55509245b22b46f85c3fbb48f9cc8d0ad8476645638ea821661a9caf3', 'note': 'plain ETH top-up by 0x9787ffbd'},
   'sample_pages': sorted(a69_rows, key=lambda r: r['start_block']), 'distinct_callers_in_samples': len(a69callers), 'callers_shared_with_0xa57bd001': len(overlap),
   'top_callers_in_samples': sorted(([a, v[2], iso(v[0]), iso(v[1])] for a, v in a69callers.items()), key=lambda x: -x[1])[:25]},
 'executors_of_0xa57bd001_top30': executors,
 'incidents': {
   'confirmed_replays': [
     {'incident': 'dodo-v2-2021', 'date': '2021-03-08', 'eoa': '0x8a14ce0f', 'proxy': '0xa57bd001', 'txs': ['0x75d4765dd704d82f0bf539da88aff2568da38697f153b14d285abc8749da683f', '0xa8d030494607e16b06dd0c7e97da2b78ebc5a072a8176b19ca57f17044c1a211'], 'level': 'confirmed-onchain (calldata byte-identical to attacker\'s pending withdraw calls; in-block evidence only)', 'take': '1,139,456.204 USDT + 133,548.94 wCRES', 'coinbase_paid_eth': 0, 'outcome': 'RETURNED (USDT leg): see returns'},
     {'incident': 'earningfarm-2022', 'date': '2022-10-14', 'eoa': '0x26bce6ec', 'proxy': '0xa69babef', 'txs': ['0x1f1aba5bef04b7026ae3cb1cb77987071a8aff9592e785dd99860566ccad83d1'], 'level': 'confirmed-onchain (flashloan/deposit calldata identical, third flash loan drains 480.1 ETH; block 15746200 idx 0)', 'take': '480.108 ETH', 'coinbase_paid_eth': 18.717, 'outcome': 'KEPT as far as found'}],
   'w2_scan_family_txs_near_exploits': {'note': 'research/chain-scan (394 DHL attack txs, blocks B-2..B+1) traced 98 txs by the family contracts (79 via 0xa69babef, 15 via 0xa57bd001, others 4cb18386/fa103c21/9799b475). NONE has an argument-level replay (all flagged no_argument_match = post-hack arb/ordinary flow) except EFVault 2022-10-14 (and 2023-02-24 shows two a69babef txs one block before the DHL attack: score -1). Large coinbase payers listed below are probably post-hack arbitrage, not captures.',
       'n_rows': len(w2rows), 'rows_with_coinbase_ge_0.5_eth': w2big, 'all_rows_file': 'research/lineages/a57_w2_rows.json'},
   'not_covered': 'No full-history exploit-replay sweep of the millions of proxy txs was possible (no per-tx traces); only the chain scan +-2-block windows around 394 DHL attack txs and the two known incidents. Absence of other replays is therefore "not found", not "none".'},
 'returns_vs_keeps': {
   'dodo_2021': {'result': 'returned', 'evidence': 'tokentx: 1,139,456.204396 USDT sent 56178a0d -> 0xfa103c21 -> DODO pool 0x95c4f5b83aa70810d4f142d58e5f7242bd891cb0 in tx 0x6e743db045f3738b24c6dedc90bae62c6429f2f7fe8a086394b05a68b8f5867a (block 12004002, 2021-03-09 11:18 UTC; the stolen amount to the wei, 14.3 h after the take); the pool paid it out to 0x96627558c6.. at 16:34 (tx 0x7a694d3624..). The Block reported "Individual A" returned ~1.14M USDT + 411 ETH (https://www.theblock.co/post/97734/dodo-dex-exploit-bug-attack). The 411 ETH leg and the 133,548.94 wCRES leg were not located on-chain.', 'raw': ['data/raw/etherscan/w8_95c4_tokentx_1200.json', 'data/raw/etherscan/w8_fa103_tokentx_12004002.json']},
   'earningfarm_2022': {'result': 'kept (no return found)', 'evidence': 'capital wallet got 15,187.097 WETH back vs 14,707.089 borrowed (+480.008); 18.717 ETH paid to builder; no transfer to the vault or any public statement found (incidents/earningfarm-2022).'},
   'pattern': 'The operator returned only where it was publicly asked and the owner could be identified (DODO had two recoverers, a whitehat go-between); no return evidence in the EF case. Not a consistent "returns hack funds" policy.'}
}
json.dump(out, open(H + 'a57_lineage.json', 'w'), indent=1, ensure_ascii=False)
json.dump(w2rows, open(H + 'a57_w2_rows.json', 'w'), indent=1)
print('ok', len(contracts), len(eoas), len(w2rows), len(w2big), len(overlap), len(a69callers), len(a57_all))
