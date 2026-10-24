"""Proposed GET-only child primitive. No credential reader or execute CLI.
Caller-supplied grant pins do not authenticate operator authority or provenance.
Trusted local writer assumption: path checks are not anchored directory handles.
"""
import hashlib, json, math, os
from pathlib import Path
BASE='https://send.resonategroup.co/api'
class Refused(ValueError):pass

def need(ok,reason):
 if not ok:raise Refused(reason)
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def strict(raw):
 need(type(raw)is bytes and len(raw)<=65536,'GRANT_BOUND')
 def pairs(items):
  out={}
  for k,v in items:need(k not in out,'DUPLICATE_KEY');out[k]=v
  return out
 try:return json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_float=lambda _:(_ for _ in ()).throw(Refused('FLOAT')),parse_constant=lambda _:(_ for _ in ()).throw(Refused('NONFINITE')))
 except Refused:raise
 except Exception:raise Refused('GRANT_JSON') from None

def canonical(value):
 need(type(value)is str and value and '\0' not in value,'ROOT')
 p=Path(value);need(p.is_absolute() and str(p)==str(p.resolve()) and p.is_dir(),'ROOT')
 for q in (p,*p.parents):need(not q.is_symlink() and not (hasattr(q,'is_junction') and q.is_junction()),'ROOT_ALIAS')
 return p

def identity(path):
 s=path.stat();return [str(s.st_dev),str(s.st_ino)]

def request_spec(route,page,leads):
 need(type(route)is str,'ROUTE')
 collections=('/campaigns/540/leads','/campaigns/540/sender-emails','/custom-variables')
 singles=('/users','/campaigns/540','/campaigns/v1.1/540/sequence-steps')+tuple('/leads/'+str(x) for x in leads)
 if route in collections:need(type(page)is int and 1<=page<=8,'PAGE')
 else:need(route in singles and page is None,'ROUTE_OR_QUERY')
 return dict(route=route,page=page)

def run_child(grant_raw,expected_grant_sha256,*,ordinal,route,page,request_sha256,clock,key_reader,transport):
 """Claim once, read key once, invoke transport once; never retries/cleans claim."""
 need(type(expected_grant_sha256)is str and hashlib.sha256(grant_raw).hexdigest()==expected_grant_sha256,'GRANT_PIN')
 g=strict(grant_raw)
 keys={'schema','workspace_id','campaign_id','lead_ids','child_sha256','issued_at','expires_at','root','root_identity','scope_id','max_attempts','manifest_sha256'}
 need(type(g)is dict and set(g)==keys and g['schema']=='canary540-acquisition-child/1','GRANT_SCHEMA')
 need(type(g['workspace_id'])is int and g['workspace_id']==10 and type(g['campaign_id'])is int and g['campaign_id']==540,'CONTEXT')
 leads=g['lead_ids'];need(type(leads)is list and len(leads)==4 and all(type(x)is int and 0<x<=9007199254740991 for x in leads) and len(set(leads))==4,'LEADS')
 need(type(g['child_sha256'])is str and g['child_sha256']==hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'CHILD_PIN')
 need(type(g['issued_at'])is int and type(g['expires_at'])is int and 0<g['issued_at']<g['expires_at'] and g['expires_at']-g['issued_at']<=600,'EXPIRY_SCHEMA')
 need(type(g['max_attempts'])is int and g['max_attempts']==32 and type(ordinal)is int and 1<=ordinal<=32,'ORDINAL')
 scope=g['scope_id'];need(type(scope)is str and 1<=len(scope)<=64 and all(c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-' for c in scope),'SCOPE')
 root=canonical(g['root']);need(root.name=='canary540-read-'+scope,'ROOT_NAME')
 rid=g['root_identity'];need(type(rid)is list and len(rid)==2 and all(type(x)is str and x.isascii() and x.isdecimal() and 1<=len(x)<=40 and (x=='0' or not x.startswith('0')) for x in rid) and rid[1]!='0' and identity(root)==rid,'ROOT_IDENTITY')
 request_spec(route,page,leads)
 import types
 manifest_path=Path(__file__).with_name('request_manifest.PROPOSED.py')
 manifest_raw=manifest_path.read_bytes()
 need(hashlib.sha256(manifest_raw).hexdigest()=='15c478a9c58ed104d0cebe500f7932e420a366863381181da7e04f4344e5b63b','MANIFEST_SOURCE_PIN')
 manifest_owner=types.ModuleType('pinned_child_request_manifest')
 exec(compile(manifest_raw,str(manifest_path),'exec'),manifest_owner.__dict__)
 manifest=manifest_owner.build_manifest(leads)
 need(type(g['manifest_sha256'])is str and g['manifest_sha256']==digest(manifest),'MANIFEST_PIN')
 spec=dict(ordinal=ordinal,route=route,page=page)
 manifest_owner.require_request(leads,spec)
 need(type(request_sha256)is str and request_sha256==digest(spec),'REQUEST_PIN')
 need(callable(clock) and callable(key_reader) and callable(transport),'CALLBACKS')
 def remaining():
  now=clock();need(type(now)in(int,float) and math.isfinite(now) and g['issued_at']<=now<g['expires_at'],'EXPIRED');return g['expires_at']-now
 remaining()
 # Revalidate root immediately before exclusive claim. A hostile local writer is out of scope.
 need(canonical(g['root'])==root and identity(root)==rid,'ROOT_REPLACED')
 claim=root/('attempt-'+str(ordinal)+'.claimed')
 need(not claim.is_symlink() and not (hasattr(claim,'is_junction') and claim.is_junction()),'CLAIM_ALIAS')
 if claim.exists():need(claim.stat().st_nlink==1,'CLAIM_ALIAS')
 try:fd=os.open(claim,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 except FileExistsError:raise Refused('ALREADY_CLAIMED') from None
 with os.fdopen(fd,'wb') as f:
  row=json.dumps(dict(scope_id=scope,ordinal=ordinal,request_sha256=request_sha256),sort_keys=True).encode()
  need(f.write(row)==len(row),'CLAIM_WRITE');f.flush();os.fsync(f.fileno())
 remaining()
 key=key_reader();need(type(key)is str and 1<=len(key)<=8192 and '\r' not in key and '\n' not in key,'KEY')
 timeout=min(20,remaining())
 url=BASE+route+('?'+'page='+str(page) if page is not None else '')
 response=transport(url,{'Authorization':'Bearer '+key,'Accept':'application/json'},timeout,1048576)
 need(type(response)is dict and set(response)=={'http_status','url','raw'},'RESPONSE_SCHEMA')
 need(response['url']==url,'REDIRECT')
 need(type(response['http_status'])is int and 200<=response['http_status']<300,'HTTP_REFUSED')
 need(type(response['raw'])is bytes and len(response['raw'])<=1048576,'RESPONSE_BOUND')
 remaining()
 return dict(schema='canary540-child-response/1',ordinal=ordinal,route=route,page=page,
  http_status=response['http_status'],raw=response['raw'],response_sha256=hashlib.sha256(response['raw']).hexdigest(),
  response_bytes=len(response['raw']),producer_authenticated=False,freshness_proven=False,readiness=False,send_allowed=False,write_allowed=False)

def urllib_get(url,headers,timeout,max_bytes):
 """Standard GET transport; called only by an explicitly authorized future parent."""
 import urllib.request, urllib.error, urllib.parse
 need(type(url)is str and url.startswith(BASE+'/') and '#' not in url,'TRANSPORT_ENDPOINT')
 parsed=urllib.parse.urlsplit(url)
 route=parsed.path[len('/api'):]
 if route in ('/campaigns/540/leads','/campaigns/540/sender-emails','/custom-variables'):
  need(parsed.query in tuple('page='+str(n) for n in range(1,9)),'TRANSPORT_QUERY')
 else:
  token=route.removeprefix('/leads/')
  need(not parsed.query and (route in ('/users','/campaigns/540','/campaigns/v1.1/540/sequence-steps') or
       route.startswith('/leads/') and token.isascii() and token.isdecimal() and not token.startswith('0') and len(token)<=16 and 0<int(token)<=9007199254740991),'TRANSPORT_ROUTE')
 need(type(timeout)in(int,float) and math.isfinite(timeout) and 0<timeout<=20 and type(max_bytes)is int and max_bytes==1048576,'TRANSPORT_BOUND')
 need(type(headers)is dict and set(headers)=={'Authorization','Accept'} and headers['Accept']=='application/json' and
      type(headers['Authorization'])is str and headers['Authorization'].startswith('Bearer ') and 7<len(headers['Authorization'])<=8199 and
      '\r' not in headers['Authorization'] and '\n' not in headers['Authorization'],'TRANSPORT_HEADERS')
 class NoRedirect(urllib.request.HTTPRedirectHandler):
  def redirect_request(self,*args,**kwargs):return None
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
 req=urllib.request.Request(url,method='GET',headers=headers)
 try:
  with opener.open(req,timeout=timeout) as response:
   raw=response.read(max_bytes+1)
   return dict(http_status=response.status,url=response.geturl(),raw=raw)
 except urllib.error.HTTPError as exc:
  with exc:return dict(http_status=exc.code,url=exc.geturl(),raw=b'')

if __name__=='__main__':
 import sys
 refused=bool(sys.argv[1:])
 print(json.dumps(dict(status='REFUSED_EXECUTION_UNSUPPORTED' if refused else 'PLAN_ONLY',execute_supported=False,send_allowed=False,write_allowed=False)))
 raise SystemExit(2 if refused else 0)
