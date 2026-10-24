# canary_write_cursor.py -- pure offline structural evaluator (synthetic spec).
import hashlib
import json
import re

_ID = re.compile(r'[A-Za-z0-9_.-]{1,64}', re.A)
_H = re.compile(r'[0-9a-f]{64}', re.A)
_NUM = re.compile(r'[1-9][0-9]{0,17}', re.A)
_MAXI = 2 ** 53
_HK = {'schema', 'baseline_id', 'baseline_count', 'hard_cap'}
_RK = {'t', 'n', 'attempt_id', 'scope_id'}
_FK = {'t', 'attempt_id', 'outcome'}
_OUT = ('ok', 'error', 'unknown', 'interrupted')
_PFX = ('/api/leads/', '/api/campaigns/v1.1/sequence-steps/')


class _Bad(Exception):
    pass


def _req(cond, code='MALFORMED_INPUT'):
    if not cond:
        raise _Bad(code)


def _exact(d, keys):
    # Type-check keys before any hashing/set building (no hostile hooks).
    if type(d) is not dict:
        return False
    for k in d:
        if type(k) is not str:
            return False
    return set(d) == keys


def _id(s):
    return type(s) is str and _ID.fullmatch(s) is not None


def _h(s):
    return type(s) is str and _H.fullmatch(s) is not None


def _int(v, lo):
    return type(v) is int and lo <= v <= _MAXI


def _hdr(d):
    _req(_exact(d, _HK), 'BAD_HEADER')
    _req(type(d['schema']) is str and d['schema'] == 'request-journal/1',
         'BAD_HEADER')
    _req(_id(d['baseline_id']), 'BAD_HEADER')
    _req(_int(d['baseline_count'], 0) and _int(d['hard_cap'], 1), 'BAD_HEADER')
    return dict(d)


def _bind(b):
    _req(_exact(b, {'grant_id', 'plan_sha256', 'operations'}), 'BAD_BINDING')
    g, p, ops = b['grant_id'], b['plan_sha256'], b['operations']
    _req(_id(g) and _h(p), 'BAD_BINDING')
    _req(type(ops) is list and len(ops) == 7, 'BAD_OPERATIONS')
    clean, ids = [], set()
    for i, op in enumerate(ops):
        _req(_exact(op, {'method', 'path', 'payload_sha256'}), 'BAD_OPERATIONS')
        m, path, ph = op['method'], op['path'], op['payload_sha256']
        _req(type(m) is str and type(path) is str and _h(ph), 'BAD_OPERATIONS')
        if i < 2:
            _req(m == 'POST' and path == '/api/custom-variables', 'BAD_OPERATIONS')
        else:
            meth, pre = ('PATCH', _PFX[0]) if i < 6 else ('PUT', _PFX[1])
            _req(m == meth and path.startswith(pre), 'BAD_OPERATIONS')
            tail = path[len(pre):]
            _req(_NUM.fullmatch(tail) is not None, 'BAD_OPERATIONS')
            if i < 6:
                _req(tail not in ids, 'BAD_OPERATIONS')
                ids.add(tail)
        clean.append({'method': m, 'path': path, 'payload_sha256': ph})
    return g, p, clean


def _derive(g, p, ops):
    out = []
    for i in range(1, 8):
        doc = {'grant_id': g, 'plan_sha256': p, 'ordinal': i,
               'operation': ops[i - 1]}
        s = json.dumps(doc, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False).encode('utf-8')
        sc = hashlib.sha256(s).hexdigest()
        out.append((sc, 'w' + sc[:63]))
    return out


def _bad(*_a):
    raise _Bad('MALFORMED_INPUT')


def _pint(s):
    _req(len(s) <= 18)
    return int(s)


def _pairs(pairs):
    d = {}
    for k, v in pairs:
        _req(k not in d)
        d[k] = v
    return d


def _rows(raw):
    _req(type(raw) is bytes and 0 < len(raw) <= 1048576, 'BAD_RAW')
    _req(b'\r' not in raw, 'BAD_RAW')
    parts = raw.split(b'\n')
    _req(parts[-1] == b'' and len(parts) >= 2, 'TRUNCATED')
    parts.pop()
    _req(len(parts) <= 4096, 'TOO_MANY_ROWS')
    rows = []
    for ln in parts:
        _req(0 < len(ln) <= 4096, 'BAD_ROW')
        r = json.loads(ln.decode('utf-8'), object_pairs_hook=_pairs,
                       parse_constant=_bad, parse_float=_bad, parse_int=_pint)
        _req(type(r) is dict, 'BAD_ROW')
        for k, v in r.items():
            k.encode('utf-8')
            _req(type(v) in (str, int), 'BAD_ROW')
            if type(v) is str:
                v.encode('utf-8')
        rows.append(r)
    return rows


def _out(state, reasons, att=None, nxt=None):
    return {
        'status': 'NO_GO', 'write_allowed': False, 'send_allowed': False,
        'grant_authenticated': False, 'producer_authenticated': False,
        'coverage_proven': False, 'approval_required': True,
        'validation_scope': 'CALLER_JOURNAL_STRUCTURE_ONLY',
        'sequence_state': state,
        'reason_codes': list(reasons) + ['NO_AUTHORITY_GRANTED'],
        'attempted_count': att,
        'next_ordinal': nxt[0] if nxt else None,
        'next_attempt_id': nxt[1] if nxt else None,
        'next_scope_id': nxt[2] if nxt else None,
    }


def _eval(raw, header, binding):
    eh = _hdr(header)
    g, p, ops = _bind(binding)
    rows = _rows(raw)
    _req(_hdr(rows[0]) == eh, 'HEADER_MISMATCH')
    D = _derive(g, p, ops)
    res, pend, stop, reasons = 0, None, False, []
    for r in rows[1:]:
        if stop and 'ROWS_AFTER_STOP' not in reasons:
            reasons.append('ROWS_AFTER_STOP')
        t = r.get('t')
        if t == 'r':
            _req(_exact(r, _RK), 'BAD_RESERVATION')
            _req(pend is None, 'RESERVE_WHILE_PENDING')
            n = r['n']
            _req(type(n) is int and n == res + 1, 'SEQUENCE_GAP')
            _req(n <= 7, 'BEYOND_SEQUENCE')
            _req(r['scope_id'] == D[n - 1][0] and
                 r['attempt_id'] == D[n - 1][1], 'BINDING_MISMATCH')
            res, pend = n, r['attempt_id']
        elif t == 'f':
            _req(_exact(r, _FK), 'BAD_FINISH')
            _req(pend is not None, 'FINISH_WITHOUT_RESERVATION')
            _req(r['attempt_id'] == pend, 'FINISH_MISMATCH')
            _req(r['outcome'] in _OUT, 'BAD_OUTCOME')
            pend = None
            if r['outcome'] != 'ok':
                stop = True
                reasons.append('NON_OK_OUTCOME')
        else:
            raise _Bad('BAD_ROW')
    remaining = eh['hard_cap'] - eh['baseline_count'] - res
    _req(not (res > 0 and remaining < 0), 'CAP_OVERRUN')
    if stop:
        return _out('STOPPED', reasons, res)
    if pend is not None:
        return _out('IN_FLIGHT', ['PENDING_RESERVATION'], res)
    if res == 7:
        return _out('COMPLETE', ['SEQUENCE_COMPLETE'], res)
    if remaining <= 0:
        return _out('STOPPED', ['CAP_EXHAUSTED'], res)
    sc, at = D[res]
    return _out('READY_STRUCTURAL_ONLY', ['STRUCTURAL_ONLY'], res,
                (res + 1, at, sc))


def evaluate_write_cursor(raw, header, binding):
    try:
        return _eval(raw, header, binding)
    except _Bad as e:
        return _out('INVALID', [e.args[0]])
    except Exception:
        return _out('INVALID', ['MALFORMED_INPUT'])
