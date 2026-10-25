"""Source-bound isolated read launcher proposal. External pins are not authority.
No execute CLI; synthetic tests use temporary credentials and fixture bytes only.
Trusted local writer assumption; no hostile process-tree sandbox.
"""
import base64,hashlib,json,math,os
from pathlib import Path
import sys,types
HERE=Path(__file__).resolve().parent
PINS={'acquisition_child.PROPOSED.py':'17195b0f60c3cf99815d2cdbd0d071463d04ac3935216b39131c24371b819e6a','bounded_subprocess.PROPOSED.py':'c0a32e6e8793807c16b6f97a90d5fd4b732c1f8c5d5733228406822ca830d3bb','acquisition_parent.PROPOSED.py':'ad695442c4a17c343d03a14ed5fdd5d247cb1989c897ead3fb334cacc6405a5b','workspace_readback.PROPOSED.py':'e2ddefb5032da3e906e3285844a9165d3d6b388fa4b7abd8d618c3785ecee20f'}
class Refused(ValueError):pass
def need(ok,reason):
 if not ok:raise Refused(reason)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def load(name):
 raw=(HERE/name).read_bytes();need(sha(raw)==PINS[name],'DEPENDENCY_PIN')
 owner=types.ModuleType('private_isolated_'+name.replace('.','_'));owner.__file__=str(HERE/name)
 exec(compile(raw,owner.__file__,'exec'),owner.__dict__);return owner

def pinned_file(path,expected,limit,root=None):
 child=load('acquisition_child.PROPOSED.py')
 need(type(path)is str and type(expected)is str and len(expected)==64 and all(c in '0123456789abcdef' for c in expected),'FILE_PIN_SCHEMA')
 p=Path(path);need(p.is_absolute() and str(p)==str(p.resolve()) and p.is_file(),'FILE_PATH')
 child.canonical(str(p.parent))
 need(not p.is_symlink() and not (hasattr(p,'is_junction') and p.is_junction()) and p.stat().st_nlink==1,'FILE_ALIAS')
 if root is not None:need(root in p.parents,'FILE_ROOT')
 with p.open('rb') as f:raw=f.read(limit+1)
 need(0<len(raw)<=limit and sha(raw)==expected,'FILE_PIN')
 return raw

def authority(raw,pin,grant_raw,grant_pin):
 child=load('acquisition_child.PROPOSED.py')
 need(type(raw)is bytes and type(pin)is str and sha(raw)==pin,'AUTHORITY_PIN')
 a=child.strict(raw)
 need(type(a)is dict and set(a)=={'schema','child_grant_sha256','entry_sha256','credential_path','credential_sha256','transport_mode','fixture_path','fixture_sha256'} and a['schema']=='isolated-read-authority/1','AUTHORITY_SCHEMA')
 need(type(grant_raw)is bytes and type(grant_pin)is str and sha(grant_raw)==grant_pin and a['child_grant_sha256']==grant_pin,'CHILD_GRANT_PIN')
 need(a['entry_sha256']==sha(Path(__file__).read_bytes()),'ENTRY_PIN')
 need(a['transport_mode'] in ('SYNTHETIC_ONLY','NETWORK_GET') and type(a['transport_mode'])is str,'MODE')
 for key in ('credential_sha256','child_grant_sha256','entry_sha256'):
  need(type(a[key])is str and len(a[key])==64 and all(c in '0123456789abcdef' for c in a[key]),'AUTHORITY_HASH_SCHEMA')
 need(type(a['credential_path'])is str and Path(a['credential_path']).name=='.env','CREDENTIAL_SOURCE')
 if a['transport_mode']=='NETWORK_GET':need(a['fixture_path']is None and a['fixture_sha256']is None,'NETWORK_FIXTURE_REFUSED')
 else:need(type(a['fixture_path'])is str and type(a['fixture_sha256'])is str,'FIXTURE_SOURCE')
 return a

def key_reader(a,child):
 # Invoked ONLY by existing child.run_child after durable attempt reservation.
 raw=pinned_file(a['credential_path'],a['credential_sha256'],65536)
 values={}
 for line in raw.decode('utf-8-sig').splitlines():
  name,sep,value=line.partition('=');name=name.strip()
  if sep and name in ('BISON_KEY','BISON_BASE'):
   need(name not in values,'DUPLICATE_CREDENTIAL_FIELD')
   value=value.strip()
   if value.startswith(('\"',"'")):
    need(len(value)>=2 and value[-1]==value[0],'CREDENTIAL_QUOTES');value=value[1:-1]
   need(value and '\r' not in value and '\n' not in value,'CREDENTIAL_VALUE')
   values[name]=value
 need(set(values)=={'BISON_KEY','BISON_BASE'} and values['BISON_BASE']==child.BASE,'CREDENTIAL_FIELDS')
 return values['BISON_KEY']

def child_call(payload):
 child=load('acquisition_child.PROPOSED.py')
 need(type(payload)is dict and set(payload)=={'authority_b64','authority_sha256','grant_b64','grant_sha256','request'},'PAYLOAD_SCHEMA')
 def decode(value):
  need(type(value)is str and len(value)<=87384,'PAYLOAD_BOUND');return base64.b64decode(value,validate=True)
 grant_raw=decode(payload['grant_b64']);auth_raw=decode(payload['authority_b64'])
 a=authority(auth_raw,payload['authority_sha256'],grant_raw,payload['grant_sha256'])
 request=payload['request'];need(type(request)is dict and set(request)=={'ordinal','route','page'},'REQUEST_SCHEMA')
 import time
 g,root,_=child.validate_request(grant_raw,payload['grant_sha256'],**request,request_sha256=child.digest(request),clock=time.time)
 fixture=None
 if a['transport_mode']=='SYNTHETIC_ONLY':
  raw=pinned_file(a['fixture_path'],a['fixture_sha256'],16777216,root)
  # Reuse strict duplicate/integer-only JSON semantics with a separate file bound.
  need(len(raw)<=16777216,'FIXTURE_BOUND')
  def pairs(items):
   out={}
   for k,v in items:need(k not in out,'FIXTURE_DUPLICATE');out[k]=v
   return out
  fixture=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_float=lambda _:(_ for _ in ()).throw(Refused('FIXTURE_FLOAT')),parse_constant=lambda _:(_ for _ in ()).throw(Refused('FIXTURE_NONFINITE')))
  need(type(fixture)is dict and set(fixture)=={'schema','responses'} and fixture['schema']=='synthetic-isolated-responses/1' and type(fixture['responses'])is dict and len(fixture['responses'])<=32,'FIXTURE_SCHEMA')
  for ordinal,row in fixture['responses'].items():
   need(type(ordinal)is str and ordinal.isascii() and ordinal.isdecimal() and not ordinal.startswith('0') and len(ordinal)<=2 and 1<=int(ordinal)<=32,'FIXTURE_ORDINAL')
   need(type(row)is dict and set(row)=={'http_status','url','raw_b64'} and type(row['http_status'])is int and 100<=row['http_status']<=599 and type(row['url'])is str and len(row['url'])<=2048 and type(row['raw_b64'])is str and len(row['raw_b64'])<=1398104,'FIXTURE_ROW_SCHEMA')
   need(len(base64.b64decode(row['raw_b64'],validate=True))<=1048576,'FIXTURE_RESPONSE_BOUND')
 def synthetic(url,headers,timeout,bound):
  row=fixture['responses'].get(str(request['ordinal']))
  need(type(row)is dict and set(row)=={'http_status','url','raw_b64'} and type(row['raw_b64'])is str and len(row['raw_b64'])<=1398104,'FIXTURE_ROW')
  return dict(http_status=row['http_status'],url=row['url'],raw=base64.b64decode(row['raw_b64'],validate=True))
 observed=child.run_child(grant_raw,payload['grant_sha256'],**request,request_sha256=child.digest(request),clock=time.time,
   key_reader=lambda:key_reader(a,child),transport=synthetic if fixture is not None else child.urllib_get)
 return dict(schema='isolated-read-response/1',request=request,transport_mode=a['transport_mode'],
  http_status=observed['http_status'],raw_b64=base64.b64encode(observed['raw']).decode(),response_sha256=observed['response_sha256'],response_bytes=observed['response_bytes'],
  producer_authenticated=False,source_authority_authenticated=False,freshness_proven=False,readiness=False,send_allowed=False,write_allowed=False)

class IsolatedRead:
 def __init__(self,authority_raw,authority_sha256,grant_raw,grant_sha256):
  self.authority=authority(authority_raw,authority_sha256,grant_raw,grant_sha256)
  self.auth_raw,self.auth_pin,self.grant_raw,self.grant_pin=authority_raw,authority_sha256,grant_raw,grant_sha256
  self.metadata=dict(source_bound=True,operator_authority_authenticated=False,producer_authenticated=False,readiness=False,transport_mode=self.authority['transport_mode'])
 def __call__(self,request,remaining_seconds):
  need(type(remaining_seconds)in(int,float) and math.isfinite(remaining_seconds) and remaining_seconds>0,'CALLBACK_DEADLINE')
  child=load('acquisition_child.PROPOSED.py');supervisor=load('bounded_subprocess.PROPOSED.py')
  child.validate_request(self.grant_raw,self.grant_pin,**request,request_sha256=child.digest(request),clock=__import__('time').time)
  payload=dict(authority_b64=base64.b64encode(self.auth_raw).decode(),authority_sha256=self.auth_pin,grant_b64=base64.b64encode(self.grant_raw).decode(),grant_sha256=self.grant_pin,request=request)
  raw=supervisor.run_trusted_child([sys.executable,'-I','-B',str(Path(__file__).resolve()),'--child'],json.dumps(payload,separators=(',',':')).encode(),timeout_seconds=min(30,remaining_seconds),max_stdout=2097152)
  need(len(raw)<=2097152,'CHILD_ENVELOPE_BOUND')
  # strict() has a grant-sized bound; response payload uses its own bounded JSON decoder.
  def pairs(items):
   out={}
   for k,v in items:need(k not in out,'RESPONSE_DUPLICATE');out[k]=v
   return out
  result=json.loads(raw.decode(),object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(Refused('RESPONSE_NONFINITE')))
  keys={'schema','request','transport_mode','http_status','raw_b64','response_sha256','response_bytes','producer_authenticated','source_authority_authenticated','freshness_proven','readiness','send_allowed','write_allowed'}
  need(type(result)is dict and set(result)==keys and result['schema']=='isolated-read-response/1' and child.digest(result['request'])==child.digest(request) and result['transport_mode']==self.authority['transport_mode'],'CHILD_ENVELOPE')
  need(all(result[k]is False for k in ('producer_authenticated','source_authority_authenticated','freshness_proven','readiness','send_allowed','write_allowed')),'CHILD_AUTHORITY_FLAGS')
  need(type(result['raw_b64'])is str and len(result['raw_b64'])<=1398104,'CHILD_RAW_BOUND');body=base64.b64decode(result['raw_b64'],validate=True)
  need(0<len(body)<=1048576 and type(result['response_bytes'])is int and len(body)==result['response_bytes'] and sha(body)==result['response_sha256'] and type(result['http_status'])is int and 200<=result['http_status']<300,'CHILD_RESPONSE')
  return dict(raw=body,http_status=result['http_status'])

def capture_phase(authority_raw,authority_sha256,grant_raw,grant_sha256):
 """Source-bound phase path; external pins are still not operator authority.
 Network use requires a separate fresh exact-scope operator decision.
 """
 import time
 # Check every executable owner before phase/storage/credential side effects.
 parent=load('acquisition_parent.PROPOSED.py')
 workspace=load('workspace_readback.PROPOSED.py')
 load('bounded_subprocess.PROPOSED.py')
 child=load('acquisition_child.PROPOSED.py')
 read=IsolatedRead(authority_raw,authority_sha256,grant_raw,grant_sha256)
 grant=child.strict(grant_raw)
 result=parent.capture(grant_raw,grant_sha256,lead_ids=grant.get('lead_ids'),
    clock=time.time,monotonic=time.monotonic,read_once=read,
    workspace_decoder=workspace.decode_workspace)
 result.update(transport_mode=read.authority['transport_mode'],source_bound_launcher=True,
    isolated_callback_supervised=True,operator_authority_authenticated=False)
 return result

def main():
 if sys.argv[1:]==['--child']:
  try:
   raw=sys.stdin.buffer.read(65537);need(len(raw)<=65536,'STDIN_BOUND')
   result=child_call(load('acquisition_child.PROPOSED.py').strict(raw))
   print(json.dumps(result,separators=(',',':'),allow_nan=False));return 0
  except BaseException:
   print(json.dumps(dict(status='ISOLATED_READ_REFUSED',readiness=False,send_allowed=False,write_allowed=False)));return 2
 print(json.dumps(dict(status='REFUSED_EXECUTION_UNSUPPORTED' if sys.argv[1:] else 'PLAN_ONLY',execute_supported=False)))
 return 2 if sys.argv[1:] else 0
if __name__=='__main__':raise SystemExit(main())
