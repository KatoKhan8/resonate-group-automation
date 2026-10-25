"""Offline acquisition coordinator. No transport, credentials or grant minting.
Injected read_once must validate the full child contract and supervise its process.
Trusted local writer assumption: directory checks are not anchored handles.
"""
import hashlib,json,math,os
from pathlib import Path
import types
HERE=Path(__file__).resolve().parent
PINS={'acquisition_child.PROPOSED.py':'17195b0f60c3cf99815d2cdbd0d071463d04ac3935216b39131c24371b819e6a','material_capture.PROPOSED.py':'8b189f9a9ca12fe831f2ee00ade4ca5761b0dc0b38996a57a8265b673a4f919f','request_manifest.PROPOSED.py':'15c478a9c58ed104d0cebe500f7932e420a366863381181da7e04f4344e5b63b'}
def load(name):
 raw=(HERE/name).read_bytes()
 if hashlib.sha256(raw).hexdigest()!=PINS[name]:raise ValueError('parent dependency drift')
 module=types.ModuleType('private_parent_'+name.replace('.','_'));module.__file__=str(HERE/name)
 exec(compile(raw,module.__file__,'exec'),module.__dict__);return module
class Refused(ValueError):pass
def need(ok,reason):
 if not ok:raise Refused(reason)
def save(root,name,raw):
 path=root/name
 need(not path.is_symlink() and not (hasattr(path,'is_junction') and path.is_junction()),'storage alias')
 if path.exists():need(path.stat().st_nlink==1,'storage hardlink')
 with os.fdopen(os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'wb') as f:
  need(f.write(raw)==len(raw),'storage shortwrite');f.flush();os.fsync(f.fileno())

def capture(grant_raw,expected_grant_sha256,*,lead_ids,clock,monotonic,read_once,workspace_decoder):
 """Claim phase once; return private original bytes paths and parsed components.
 Phase checks here are not a duplicate child grant-authority validator.
 """
 child=load('acquisition_child.PROPOSED.py');manifest_owner=load('request_manifest.PROPOSED.py');material=load('material_capture.PROPOSED.py')
 manifest=manifest_owner.build_manifest(lead_ids)
 first=manifest[0]
 g,root,rid=child.validate_request(grant_raw,expected_grant_sha256,
     **first,request_sha256=manifest_owner.digest(first),clock=clock)
 need(g['lead_ids']==lead_ids and all(type(x)is int for x in g['lead_ids']),'phase supplied lead binding')
 need(all(callable(x) for x in (clock,monotonic,read_once,workspace_decoder)),'callbacks')
 start=monotonic();need(type(start)in(int,float) and math.isfinite(start),'monotonic clock')
 def time_left():
  now=clock();elapsed=monotonic()-start
  need(type(now)in(int,float) and math.isfinite(now) and type(elapsed)in(int,float) and math.isfinite(elapsed) and 0<=elapsed<600 and g['issued_at']<=now<g['expires_at'],'phase deadline')
  need(child.canonical(g['root'])==root and child.identity(root)==g['root_identity'],'phase root replaced')
  return now,min(600-elapsed,g['expires_at']-now)
 now,_=time_left();save(root,'phase.claimed',json.dumps(dict(grant_sha256=expected_grant_sha256,manifest_sha256=g['manifest_sha256']),sort_keys=True).encode())
 owner=material.MaterialCapture(lead_ids,int(now));completed_collections=set();attempts=total=0;receipts=[];bookends=[]
 for request in manifest:
  route=request['route'];page=request['page']
  if route in completed_collections:continue
  now,remaining=time_left();need(attempts<32,'attempt ceiling')
  child.validate_request(grant_raw,expected_grant_sha256,**request,request_sha256=manifest_owner.digest(request),clock=clock)
  ordinal=request['ordinal'];prefix='response-'+str(ordinal)
  save(root,prefix+'.pending',json.dumps(request,sort_keys=True).encode())
  attempts+=1
  # Separate copy protects the pinned manifest from callback mutation.
  observed=read_once(dict(request),remaining)
  now,_=time_left()
  need(type(observed)is dict and set(observed)=={'raw','http_status'},'response schema')
  raw,status=observed['raw'],observed['http_status']
  need(type(raw)is bytes and 0<len(raw)<=1048576 and total+len(raw)<=8388608 and type(status)is int and 200<=status<300,'response boundary')
  total+=len(raw);save(root,prefix+'.private.bin',raw)
  receipt=dict(request,http_status=status,response_sha256=hashlib.sha256(raw).hexdigest(),response_bytes=len(raw),observed_at=int(now),private_file=prefix+'.private.bin')
  save(root,prefix+'.receipt.json',json.dumps(receipt,sort_keys=True).encode());receipts.append(receipt)
  if route=='/users':
   workspace=workspace_decoder(raw);need(type(workspace)is int and workspace==10,'workspace bookend')
   bookends.append(dict(ordinal=ordinal,workspace_id=workspace))
  else:
   need(len(bookends)==1,'before workspace required')
   before=len(owner.components)
   owner.feed(dict(raw=raw,route=route,page=page,observed_at=int(now),http_status=status,workspace_id=10))
   if page is not None and len(owner.components)>before:completed_collections.add(route)
 need([b['ordinal'] for b in bookends]==[1,32],'workspace bookends incomplete')
 result=owner.finish()
 result=dict(status='NO_GO',schema='offline-acquisition-parent/1',material=result,attempts=attempts,response_bytes=total,receipts=receipts,bookends=bookends,
  workspace_bookend_assertions_match=True,producer_authenticated=False,provenance_authenticated=False,source_trust=False,freshness_proven=False,
  readiness=False,snapshot_ready=False,send_allowed=False,write_allowed=False,hard_deadline_enforced=False,
  limitations=['read_once must enforce complete child validation and killable process deadline','caller-supplied workspace decoder assertions are not authenticated evidence','trusted local writer; file fsync is not directory power-loss protection'])
 time_left()
 summary=dict(status='NO_GO',grant_sha256=expected_grant_sha256,attempts=attempts,response_bytes=total,receipt_list_sha256=child.digest(receipts),workspace_bookend_assertions_match=True,provenance_authenticated=False,hard_deadline_enforced=False,readiness=False,send_allowed=False,write_allowed=False)
 save(root,'phase.result.private.json',json.dumps(summary,sort_keys=True).encode())
 return result


if __name__=='__main__':
 import sys
 refused=bool(sys.argv[1:]);print(json.dumps(dict(status='REFUSED_EXECUTION_UNSUPPORTED' if refused else 'PLAN_ONLY',execute_supported=False)))
 raise SystemExit(2 if refused else 0)
