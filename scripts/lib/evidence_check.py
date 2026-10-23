"""Check one timeline event against the saved raw files it links (the UNION of its links).

Used by audit3.py (files = site/raw/...) and relink_events.py (files = data/raw/..., before publishing).
A raw path is always written 'raw/<source>/<file>' (site-relative); `base` says which tree it is read from.

Checks, per event:
  time     the event's timestamp (second resolution) appears in some linked file (etherscan timeStamp, block timestamp,
           mempool csv timestamp_ms, tx blockTimestamp; for web pages the clock time or the date appears in the text)
  block    every 'block N' in the detail appears as a block number in a linked file
  idx      'block N idx M' pairs match a tx position in a linked file
  amount   every 'X ETH|WETH|USDT|... ' amount appears (ETH call values, tx value, token transfer logs, etherscan rows)
  quote    quoted text appears in a linked file (tx input text or web text)
  tx       the event's tx hash appears in at least one linked file
"""
import json, os, re, csv, html as _h, datetime

from math_expr import arithmetic_value

BASE = None            # set by the caller: directory that contains 'raw/'
_c = {}


def J(p):
    k = (BASE, p)
    if k not in _c:
        _c[k] = json.load(open(os.path.join(BASE, p)))
    return _c[k]


def T(p):
    return open(os.path.join(BASE, p), errors='replace').read()


def h2i(x):
    return int(x, 16) if isinstance(x, str) else x


def E(x):
    return h2i(x) / 1e18


def csvr(p):
    return list(csv.DictReader(open(os.path.join(BASE, p), newline='', encoding='utf-8')))


def new_facts():
    return dict(times=set(), eth=set(), blocks=set(), idx=set(), hashes=set(), text='', n=0, tok=set(), nums=set(), blocks_any=set(), text_any='')


def _revert_text(out):
    # Error(string): 0x08c379a0 + offset + length + utf8
    try:
        if isinstance(out, str) and out.startswith('0x08c379a0') and len(out) >= 10 + 128:
            ln = int(out[10 + 64:10 + 128], 16)
            return bytes.fromhex(out[10 + 128:10 + 128 + 2 * ln]).decode('utf-8', 'replace')
    except Exception:
        pass
    return ''


def _addcall(c, F):
    v = h2i(c.get('value', '0x0') or '0x0')
    if v:
        F['eth'].add(v / 1e18)
    for k_ in ('error', 'revertReason'):
        if isinstance(c.get(k_), str):
            F['text'] += ' ' + c[k_]
    rt = _revert_text(c.get('output'))
    if rt:
        F['text'] += ' ' + rt
    for s in c.get('calls', []) or []:
        _addcall(s, F)


def _tok_from_logs(rcs, F, hs=None):
    for rc in rcs:
        if hs and not any((rc.get('transactionHash') or '').lower().startswith(h) for h in hs):
            continue
        for lg in rc.get('logs', []) or []:
            d = lg.get('data') or ''
            if lg.get('topics') and lg['topics'][0].startswith('0xddf252ad') and len(d) == 66:
                v = int(d, 16)
                for dec in (18, 6, 8, 9, 0):
                    F['tok'].add(round(v / 10 ** dec, 6))


def add_file(F, e, p, hs):
    """Add what raw file p says about the event (hash prefixes hs, lower-case 0x...) to the facts F."""
    F['n'] += 0
    if p.endswith('.html') or p.endswith('.txt'):
        F['text'] += ' ' + _h.unescape(re.sub(r'<[^>]+>', ' ', T(p)))
        F['n'] += 1
        return
    if p.endswith('.csv'):
        rows = csvr(p)
        for r in rows:
            h = (r.get('hash') or '').lower()
            if hs and any(h.startswith(x) for x in hs):
                F['n'] += 1
                if r.get('timestamp_ms'):
                    F['times'].add(int(r['timestamp_ms']))
                F['hashes'].add(h)
        return
    try:
        d = J(p)
    except Exception as ex:
        F['text'] += ' ERR ' + str(ex)
        return
    base = os.path.basename(p)
    r = d.get('result') if isinstance(d, dict) and 'result' in d else d
    # etherscan account list
    if isinstance(r, list) and r and isinstance(r[0], dict) and 'timeStamp' in r[0]:
        for x in r:
            bn_ = x.get('blockNumber')
            if bn_ not in (None, ''):
                F['blocks_any'].add(int(bn_, 16) if isinstance(bn_, str) and bn_.startswith('0x') else int(bn_))
            h = (x.get('hash') or '').lower()
            inp0 = x.get('input') or ''
            if inp0.startswith('0x') and len(inp0) > 74 and len(F['text_any']) < 400000:
                try:
                    tx0 = bytes.fromhex(inp0[2:]).decode('utf-8')
                    if sum(ch.isprintable() or ch in '\n\r\t' for ch in tx0) > 0.9 * len(tx0):
                        F['text_any'] += ' ' + tx0      # a message in another row of the same linked list
                except Exception:
                    pass
            if hs and any(h.startswith(y) for y in hs):
                F['n'] += 1
                ts = x['timeStamp']
                F['times'].add((int(ts, 16) if isinstance(ts, str) and ts.startswith('0x') else int(ts)) * 1000)
                if x.get('blockNumber') not in (None, ''):
                    bn = x['blockNumber']
                    F['blocks'].add(int(bn, 16) if isinstance(bn, str) and bn.startswith('0x') else int(bn))
                if x.get('transactionIndex') not in (None, ''):
                    ti = x['transactionIndex']
                    F['idx'].add(int(ti, 16) if isinstance(ti, str) and ti.startswith('0x') else int(ti))
                dec = int(x['tokenDecimal']) if x.get('tokenDecimal') else 18
                v = x.get('value')
                if isinstance(v, str) and v.startswith('0x'):
                    v = int(v, 16)
                if v not in (None, ''):
                    F['eth'].add(int(v) / 10 ** dec)
                F['hashes'].add(h)
                inp = x.get('input') or ''
                if inp.startswith('0x') and len(inp) > 10:
                    try:
                        F['text'] += ' ' + bytes.fromhex(inp[2:]).decode('utf-8', 'replace')
                    except Exception:
                        pass
        return
    # etherscan logs (getLogs): list of {address, topics, data, blockNumber, timeStamp, transactionHash}
    if isinstance(r, list) and r and isinstance(r[0], dict) and 'topics' in r[0] and 'transactionHash' in r[0]:
        for x in r:
            h = (x.get('transactionHash') or '').lower()
            if hs and any(h.startswith(y) for y in hs):
                F['n'] += 1
                F['blocks'].add(h2i(x['blockNumber']))
                if x.get('timeStamp'):
                    F['times'].add(h2i(x['timeStamp']) * 1000)
                F['hashes'].add(h)
        return
    # trace_block: [{txHash, result}]
    if isinstance(r, list) and r and isinstance(r[0], dict) and 'txHash' in r[0]:
        for k, x in enumerate(r):
            h = (x.get('txHash') or '').lower()
            if hs and any(h.startswith(y) for y in hs):
                F['n'] += 1
                F['idx'].add(k)
                F['hashes'].add(h)
                if x.get('result'):
                    _addcall(x['result'], F)
        return
    # block receipts: list of receipts
    if isinstance(r, list) and r and isinstance(r[0], dict) and 'transactionHash' in r[0] and 'logs' in r[0]:
        sel = [x for x in r if hs and any((x.get('transactionHash') or '').lower().startswith(y) for y in hs)]
        if sel:
            F['n'] += 1
        for x in sel:
            F['blocks'].add(h2i(x['blockNumber']))
            F['idx'].add(h2i(x['transactionIndex']))
            F['hashes'].add(x['transactionHash'].lower())
        _tok_from_logs(sel, F)
        return
    if isinstance(r, dict):
        if 'hash' in r and 'blockNumber' in r and 'input' in r:  # tx
            if not hs or any(r['hash'].lower().startswith(y) for y in hs):
                F['n'] += 1
                F['hashes'].add(r['hash'].lower())
                if r.get('blockNumber'):
                    F['blocks'].add(h2i(r['blockNumber']))
                if r.get('blockTimestamp'):
                    F['times'].add(h2i(r['blockTimestamp']) * 1000)
                if r.get('transactionIndex'):
                    F['idx'].add(h2i(r['transactionIndex']))
                F['eth'].add(E(r['value']))
                inp = r.get('input') or ''
                try:
                    F['text'] += ' ' + bytes.fromhex(inp[2:]).decode('utf-8', 'replace')
                except Exception:
                    pass
            else:           # a different tx of the same story is linked (e.g. the offer message a return refers to): its message text counts as stated text
                try:
                    F['text_any'] += ' ' + bytes.fromhex((r.get('input') or '0x')[2:]).decode('utf-8', 'replace')
                except Exception:
                    pass
            return
        if 'number' in r and 'transactions' in r:  # block
            F['n'] += 1
            F['blocks'].add(h2i(r['number']))
            F['blocks_any'].add(h2i(r['number']))
            F['times'].add(h2i(r['timestamp']) * 1000)
            for k, t in enumerate(r['transactions']):
                if isinstance(t, dict) and hs and any(t['hash'].lower().startswith(y) for y in hs):
                    F['idx'].add(k)
                    F['eth'].add(E(t['value']))
                    F['hashes'].add(t['hash'].lower())
                    inp = t.get('input') or ''
                    try:
                        F['text'] += ' ' + bytes.fromhex(inp[2:]).decode('utf-8', 'replace')
                    except Exception:
                        pass
                elif isinstance(t, str) and hs and any(t.lower().startswith(y) for y in hs):
                    F['idx'].add(k)
                    F['hashes'].add(t.lower())
            if r.get('extraData'):
                try:
                    F['text'] += ' ' + bytes.fromhex(r['extraData'][2:]).decode('utf-8', 'replace')
                except Exception:
                    pass
            return
        if 'from' in r and ('calls' in r or 'gasUsed' in r):  # tx trace
            F['n'] += 1
            _addcall(r, F)
            return
        if 'blockNumber' in r and 'logs' in r:  # receipt
            if not hs or any((r.get('transactionHash') or '').lower().startswith(y) for y in hs):
                F['n'] += 1
                F['blocks'].add(h2i(r['blockNumber']))
                F['idx'].add(h2i(r['transactionIndex']))
                F['hashes'].add(r['transactionHash'].lower())
                _tok_from_logs([r], F)
            return
    F['text'] += ' ' + json.dumps(d)[:300000]
    F['n'] += 1


def file_nums(p):
    out = set()
    if p.endswith('.html') or p.endswith('.txt'):
        t = _h.unescape(re.sub(r'<[^>]+>', ' ', T(p)))
        for m in re.findall(r'\d[\d,]*\.?\d*', t):
            try:
                out.add(float(m.replace(',', '')))
            except Exception:
                pass
        return out
    try:
        d = J(p)
    except Exception:
        return out

    def rec(o):
        if isinstance(o, dict):
            for v in o.values():
                rec(v)
        elif isinstance(o, list):
            for v in o:
                rec(v)
        elif isinstance(o, (int, float)):
            out.add(float(o))
        elif isinstance(o, str):
            if re.fullmatch(r'\d{6,}', o):
                v = int(o)
                for dec in (18, 6, 8, 9):
                    out.add(v / 10 ** dec)
            elif re.fullmatch(r'0x[0-9a-fA-F]{1,24}', o):
                try:
                    for dec in (18, 6, 8):
                        out.add(int(o, 16) / 10 ** dec)
                except Exception:
                    pass
            elif re.fullmatch(r'0x[0-9a-fA-F]+', o) and len(o) >= 66:
                # ABI data / call output: every 32-byte word (after an optional 4-byte selector) is a candidate uint
                body = o[2:]
                if (len(body) - 8) % 64 == 0:
                    body = body[8:]
                for i in range(0, len(body) - 63, 64):
                    try:
                        w = int(body[i:i + 64], 16)
                    except Exception:
                        continue
                    if 0 < w < 1 << 128:
                        for dec in (18, 6, 8):
                            out.add(w / 10 ** dec)
            else:
                for m in re.findall(r'\d[\d,]*\.\d+', o):
                    try:
                        out.add(float(m.replace(',', '')))
                    except Exception:
                        pass
    rec(d)
    return out


DATE_FORMS = [lambda d: d.strftime('%Y-%m-%d'), lambda d: d.strftime('%B %-d, %Y'), lambda d: d.strftime('%-d %B %Y'),
              lambda d: d.strftime('%b %-d, %Y'), lambda d: d.strftime('%-d %b %Y'), lambda d: d.strftime('%d %B %Y'),
              lambda d: d.strftime('%B %d, %Y'), lambda d: d.strftime('%Y%m%d'), lambda d: d.strftime('%B %-d'), lambda d: d.strftime('%b %-d')]

SYMS = r'ETH|WETH|USDT|USDC|DAI|WBTC|stETH|wstETH|osETH|rsETH|msETH|WSZO|USD'


def amounts_in(det):
    out = []
    for m in re.finditer(r'(?<![\w.])(\d[\d,]*\.?\d*)\s*(%s)\b' % SYMS, det):
        try:
            v = float(m.group(1).replace(',', ''))
        except Exception:
            continue
        sym = m.group(2)
        if v == 0 or sym == 'USD':
            continue
        if re.search(r'Tornado Cash\s*$', det[:m.start()]) and sym == 'ETH':
            continue
        dd = len(m.group(1).split('.')[1]) if '.' in m.group(1) else 0
        out.append((m.group(1), v, sym, dd))
    return out


def _all_text(paths):
    ts = []
    for p in paths:
        try:
            if os.path.getsize(os.path.join(BASE, p)) > 60e6:
                continue
            t = T(p)
            if p.endswith(('.html', '.txt', '.md')):
                t = _h.unescape(re.sub(r'<[^>]+>', ' ', t))
            ts.append(t.lower())
        except Exception:
            pass
    return '\n'.join(ts)


def tolf_for(v, dd):
    return lambda x: abs(v - x) <= max(5e-5, abs(x) * 2e-4, (0.55 * 10 ** (-dd) if dd > 0 or v >= 10 else 0))


def check_event(e, paths):
    """Return a list of dicts(label, shown, ok, found, kind, note) for event e given its linked paths."""
    det = e.get('detail') or ''
    out = []
    hs = [x.lower() for x in re.findall(r'0x[0-9a-fA-F]{8,64}', e.get('tx') or '')]
    F = new_facts()
    for p in paths:
        add_file(F, e, p, hs)
    allnums = None

    def nums():
        nonlocal allnums
        if allnums is None:
            allnums = set()
            for p in paths:
                allnums |= file_nums(p)
        return allnums
    if hs and F['n'] == 0:
        out.append(dict(label='tx present in raw', shown=e.get('tx'), ok=False, found=None, kind='file-lacks-value',
                        note='tx hash not found in the linked raw file(s); detail: ' + det[:90]))
        return out
    # ---- time
    t = e.get('t') if 't' in e else e.get('t_utc_ms')
    if 'utc' not in e and e.get('t_utc'):
        e = dict(e, utc=e['t_utc'])
    prec = e.get('prec') if 'prec' in e else e.get('precision')
    if t is not None:
        if F['times']:
            ok_ = t in F['times'] or (t // 1000 * 1000) in F['times'] or t in {x // 1000 * 1000 for x in F['times']}
            out.append(dict(label='time', shown=e.get('utc'), ok=ok_, found=sorted(F['times'])[:3], kind='ok' if ok_ else 'mismatch', note='event.t=%s' % t))
        elif F['text'].strip():
            m = re.search(r'(\d\d:\d\d:\d\d)', e.get('utc') or '')
            hit = bool(m) and m.group(1) in F['text']
            dt = datetime.datetime.fromtimestamp(t / 1000, datetime.timezone.utc)
            dhit = any(f(dt) in F['text'] for f in DATE_FORMS)
            ok_ = hit or dhit
            out.append(dict(label='time in text', shown=e.get('utc'), ok=ok_, found=hit or dhit, kind='ok' if ok_ else 'text-unverified',
                            note='web/text source: clock time or date searched in the file text; prec=%s' % prec))
        elif prec not in ('day', 'reported', 'unknown', None) and (e.get('tx') or e.get('block')):
            out.append(dict(label='time', shown=e.get('utc'), ok=False, found=None, kind='time-not-in-raw',
                            note='no linked file carries a timestamp for this event (prec=%s)' % prec))
    # ---- blocks / idx
    for m in re.finditer(r'block (\d{7,9})(?: idx (\d+))?', det):
        bn = int(m.group(1))
        if F['blocks'] or F['blocks_any']:
            ok_ = bn in F['blocks'] or bn in F['blocks_any']
            out.append(dict(label='block %d' % bn, shown=bn, ok=ok_, found=sorted(F['blocks'])[:6], kind='ok' if ok_ else 'mismatch', note='detail block number vs raw blockNumber (this tx, or any row of a linked list)'))
        elif F['text'] and str(bn) in F['text']:
            out.append(dict(label='block %d' % bn, shown=bn, ok=True, found='in text', kind='ok', note=''))
        if m.group(2) and F['idx']:
            ok_ = int(m.group(2)) in F['idx']
            out.append(dict(label='idx %s' % m.group(2), shown=int(m.group(2)), ok=ok_, found=sorted(F['idx']), kind='ok' if ok_ else 'mismatch', note=''))
    # ---- declared-derived numbers: formula + operands; every operand must occur in the linked files and the formula must give the shown value
    dv = set()
    for it in e.get('derived') or []:
        try:
            m_ = re.match(r'\s*(\d[\d,]*\.?\d*)\s*(\w+|%)?', it['shown'])
            raw_s, sym = m_.group(1), (m_.group(2) or '')
            v_ = float(raw_s.replace(',', ''))
            dd_ = len(raw_s.split('.')[1]) if '.' in raw_s else 0
            txt_ = _all_text(paths)
            vals, miss = {}, []
            for nm, sp in it['ops'].items():
                if 'int' in sp:
                    n_ = int(sp['int'])
                    vals[nm] = n_
                    if not (str(n_) in txt_ or format(n_, 'x') in txt_):
                        miss.append(nm)
                else:
                    vals[nm] = float(sp['str'].replace(',', ''))
                    if sp['str'].lower() not in txt_:
                        miss.append(nm)
            res_ = arithmetic_value(it['expr'], vals)
            okv = tolf_for(v_, dd_)(res_)
            ok_ = (not miss) and okv
            out.append(dict(label='derived %s' % it['shown'], shown=it['shown'], ok=ok_, found=('formula gives %.8g' % res_) + ((' ; operands not in linked files: %s' % miss) if miss else ''),
                            kind='declared-derived' if ok_ else 'derived-check-failed', note='%s = %s' % (it['shown'], it.get('how', it['expr']))))
            if ok_:
                dv.add((raw_s, sym))
        except Exception as ex:
            out.append(dict(label='derived %s' % it.get('shown'), shown=it.get('shown'), ok=False, found=str(ex)[:80], kind='derived-check-failed', note='bad derived spec'))
    # ---- amounts
    for raw_s, v, sym, dd in amounts_in(det):
        if (raw_s, sym) in dv:
            continue
        tolf = tolf_for(v, dd)
        lab = 'amount %s %s' % (raw_s, sym)
        if any(tolf(x) for x in F['eth']) or (sym != 'ETH' and any(tolf(x) for x in F['tok'])) or (sym == 'WETH' and any(tolf(x) for x in F['tok'])):
            out.append(dict(label=lab, shown=v, ok=True, found='present', kind='ok', note=''))
        elif (F['text'] or F['text_any']) and (re.search(r'(?<![\d.,])%s\s*%s\b' % (re.escape(raw_s), sym), F['text'] + ' ' + F['text_any']) or re.search(r'(?<![\d.,])%s\s*%s\b' % (re.escape(raw_s.replace(',', '')), sym), F['text'] + ' ' + F['text_any'])):
            out.append(dict(label=lab, shown=v, ok=True, found='stated in the linked text/message', kind='ok-in-file', note=''))
        elif any(tolf(x) for x in nums()):
            out.append(dict(label=lab, shown=v, ok=True, found='present in linked file (other entry/text)', kind='ok-in-file', note=''))
        else:
            out.append(dict(label=lab, shown=v, ok=False, found=sorted(round(x, 6) for x in F['eth'])[-4:], kind='amount-not-in-raw',
                            note='not found in the linked file(s); detail: ' + det[:140]))
    # ---- quotes
    for m in re.finditer(r'"([^"]{8,})"', det):
        q = m.group(1)[:30]
        if F['text']:
            ok_ = q.lower() in F['text'].lower() or q.replace('...', '')[:20].lower() in F['text'].lower()
            out.append(dict(label='quoted text %r' % q, shown=q, ok=ok_, found=ok_, kind='ok' if ok_ else 'quote-not-in-raw', note='quoted text searched in raw input/text'))
    return out
