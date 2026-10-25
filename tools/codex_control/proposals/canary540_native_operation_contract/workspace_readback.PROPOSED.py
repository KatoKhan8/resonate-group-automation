"""Pure /users workspace bookend schema, not authenticated tenancy evidence.
Identity rule matches the previously pinned workspace parser; no old runner import.
"""
import hashlib
import json
from pathlib import Path
import types

_raw=Path(__file__).with_name('bounded_pages.PROPOSED.py').read_bytes()
if hashlib.sha256(_raw).hexdigest()!='c1760e58473a515016427848dedd960612b687a38e03e130eaf615ec84dd7c37':
    raise ValueError('workspace JSON decoder source drift')
_pages=types.ModuleType('workspace_json_decoder')
exec(compile(_raw,'pinned workspace JSON decoder','exec'),_pages.__dict__)
Refused=_pages.AcquisitionRefused


def decode_workspace(raw):
    if type(raw) is not bytes or not raw or len(raw)>1048576:
        raise Refused('workspace response bound')
    try:
        v=json.loads(raw.decode('utf-8'),object_pairs_hook=_pages._object,
            parse_float=_pages._float,
            parse_constant=lambda _: (_ for _ in ()).throw(Refused('nonfinite JSON')))
        if type(v) is not dict or type(v.get('data')) is not dict:
            raise Refused('workspace response shape')
        data=v['data'];workspace=data.get('workspace')
        if (type(workspace) is not dict or type(workspace.get('id')) is not int
                or workspace['id']!=10 or type(workspace.get('name')) is not str
                or workspace['name']!='PRODUCTIVE'):
            raise Refused('workspace identity mismatch')
        for record in (v,data,workspace):
            if 'workspace_id' in record and (type(record['workspace_id']) is not int or record['workspace_id']!=10):
                raise Refused('workspace identity contradiction')
        return 10
    except Exception as exc:
        if isinstance(exc,Refused):raise
        raise Refused('invalid workspace JSON') from None
