"""Offline scratch-only durable journal adapter. No HTTP executor or authority."""
import contextlib,hashlib,json,os,pathlib,tempfile,types
HERE=pathlib.Path(__file__).resolve().parent
DEPS=(('../request_journal.reviewed.UNAPPLIED.py','42e7c94287fff540c4358431bce5ec3d04d1ecf757c33c89a4373b00524affe6'),('../canary540_write_cursor/reviewed/canary_write_cursor.py','fff1bdf41b06cb3f2fff62d7eed10435a1868bd2ed966d0c53363f52c724f539'))
class Refusal(Exception):pass
def need(ok,reason):
 if not ok:raise Refusal(reason)
def clean(x,depth=0,budget=None):
 if budget is None:budget=[10000,262144]
 budget[0]-=1;need(budget[0]>=0 and depth<20,'BOUND')
 if type(x) is dict:
  need(len(x)<=100 and all(type(k)is str for k in x),'BAD_DTO')
  out={}
  for k,v in x.items():
   budget[1]-=len(k.encode('utf-8'));need(budget[1]>=0,'BOUND');out[k]=clean(v,depth+1,budget)
  return out
 if type(x)is list:
  need(len(x)<=100,'BOUND');return [clean(v,depth+1,budget) for v in x]
 need(type(x) is str or type(x) is int or type(x) is bool or type(x) is type(None),'BAD_DTO')
 if type(x)is str:
  need(len(x)<=20000,'BOUND');budget[1]-=len(x.encode('utf-8'));need(budget[1]>=0,'BOUND')
 if type(x)is int:need(abs(x)<=2**53,'BOUND')
 return x
def encode(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')
def digest(x):return hashlib.sha256(encode(x)).hexdigest()
def pairs(xs):
 d={}
 for k,v in xs:need(k not in d,'DUPLICATE');d[k]=v
 return d
def strict(b):
 need(len(b)<=262144,'BOUND')
 return clean(json.loads(b.decode('utf-8'),object_pairs_hook=pairs,parse_float=lambda x:(_ for _ in ()).throw(Refusal('FLOAT')),parse_constant=lambda x:(_ for _ in ()).throw(Refusal('NONFINITE'))))
def safe_file(path):
 need(not path.is_symlink() and not (hasattr(path,'is_junction') and path.is_junction()),'PATH_ALIAS')
 if path.exists():need(path.stat().st_nlink==1,'PATH_ALIAS')
def bounded(path,limit):
 safe_file(path)
 with open(path,'rb') as f:raw=f.read(limit+1)
 need(len(raw)<=limit,'BOUND');return raw
def dependencies():
 modules=[]
 for rel,pin in DEPS:
  path=(HERE/rel).resolve();raw=bounded(path,131072);need(hashlib.sha256(raw).hexdigest()==pin,'DEPENDENCY_PIN')
  m=types.ModuleType('offline_fixed_dependency');exec(compile(raw,str(path),'exec'),m.__dict__);modules.append(m)
 return modules

def root_path(root):
 need(type(root)is str,'SCRATCH_ONLY');p=pathlib.Path(root)
 need(p.is_absolute() and p.exists() and p.is_dir(),'SCRATCH_ONLY')
 need(not p.is_symlink() and p==p.resolve(),'PATH_ALIAS')
 t=pathlib.Path(tempfile.gettempdir()).resolve();need(p!=t and t in p.parents,'SCRATCH_ONLY')
 for name in ('scope.json','requests.jsonl','phase.lock','requests.jsonl.lock'):
  q=p/name;safe_file(q)
 return p
@contextlib.contextmanager
def phase(root):
 p=root_path(root);lock=p/'phase.lock'
 try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 except FileExistsError:raise Refusal('PHASE_LOCKED')
 clean_exit=False
 try:
  os.fsync(fd)  # File-level lock creation durability before any mutation.
  yield p;clean_exit=True
 finally:
  os.close(fd)
  # An interrupted/uncertain phase retains its exclusive lock, even when a
  # fully written journal row is visible after failed fsync. Never auto-recover.
  if clean_exit:os.unlink(lock)
def result(reason,**extra):
 return dict(status='NO_GO',reason=reason,dispatch_permitted=False,write_allowed=False,send_allowed=False,grant_authenticated=False,outcome_authenticated=False,journal_state_scope='LOCAL_CALLER_ASSERTED_ONLY',actual_transport_count=0,**extra)
def scope_doc(header,binding):
 h,b=clean(header),clean(binding)
 need(type(h)is dict and type(b)is dict and set(b)=={'grant_id','plan_sha256','operations'},'BAD_SCOPE')
 ops=b['operations'];need(type(ops)is list and len(ops)==7,'BAD_OPERATIONS')
 reduced=[]
 for op in ops:
  need(type(op)is dict and set(op)=={'method','path','payload'},'BAD_OPERATIONS')
  reduced.append(dict(method=op['method'],path=op['path'],payload_sha256=digest(op['payload'])))
 cb=dict(grant_id=b['grant_id'],plan_sha256=b['plan_sha256'],operations=reduced)
 j,c=dependencies();raw=j._line(h);ev=c.evaluate_write_cursor(raw,h,cb)
 need(ev['sequence_state']=='READY_STRUCTURAL_ONLY','BAD_SCOPE')
 return dict(schema='offline-write-adapter/1',header=h,cursor_binding=cb)
def load(p,pin):
 need(type(pin)is str and len(pin)==64 and all(c in '0123456789abcdef' for c in pin),'BAD_EXPECTED_PIN')
 need((p/'scope.json').is_file() and (p/'requests.jsonl').is_file(),'MISSING_SCOPE_OR_JOURNAL')
 raw=bounded(p/'scope.json',262144);need(hashlib.sha256(raw).hexdigest()==pin,'SCOPE_PIN')
 doc=strict(raw);need(type(doc)is dict and set(doc)=={'schema','header','cursor_binding'},'BAD_SCOPE')
 need(doc['schema']=='offline-write-adapter/1','BAD_SCOPE')
 j,c=dependencies();ev=c.evaluate_write_cursor(j._line(doc['header']),doc['header'],doc['cursor_binding']);need(ev['sequence_state']=='READY_STRUCTURAL_ONLY','SCOPE_BINDING')
 return doc

def initialize(root,header,binding):
 try:
  doc=scope_doc(header,binding);raw=encode(doc);need(len(raw)<=262144,'BOUND');pin=hashlib.sha256(raw).hexdigest()
  with phase(root) as p:
   need(not (p/'scope.json').exists() and not (p/'requests.jsonl').exists() and not (p/'requests.jsonl.lock').exists(),'EXISTING_SCOPE')
   fd=os.open(p/'scope.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
   with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
   j,c=dependencies();h=doc['header'];r=j.initialize(str(p/'requests.jsonl'),baseline_id=h['baseline_id'],baseline_count=h['baseline_count'],hard_cap=h['hard_cap'])
   need(r['status']=='OK','JOURNAL_INITIALIZATION_UNCERTAIN')
   ev=c.evaluate_write_cursor(bounded(p/'requests.jsonl',1048576),h,doc['cursor_binding']);need(ev['sequence_state']=='READY_STRUCTURAL_ONLY','JOURNAL_INITIALIZATION_UNCERTAIN')
  return result('INITIALIZED_OFFLINE',scope_sha256=pin)
 except Exception as e:return result(str(e) if type(e)is Refusal else 'IO_OR_INPUT_UNCERTAIN')
def reserve_next(root,expected_scope_sha256,ordinal,actual_request):
 try:
  need(type(ordinal)is int and 1<=ordinal<=7,'BAD_ORDINAL');request=clean(actual_request)
  need(type(request)is dict and set(request)=={'method','path','payload'},'BAD_REQUEST')
  with phase(root) as p:
   doc=load(p,expected_scope_sha256);j,c=dependencies();h=doc['header'];raw=bounded(p/'requests.jsonl',1048576);ev=c.evaluate_write_cursor(raw,h,doc['cursor_binding'])
   need(ev['sequence_state']=='READY_STRUCTURAL_ONLY' and ev['next_ordinal']==ordinal,'CURSOR_NOT_READY')
   actual=dict(method=request['method'],path=request['path'],payload_sha256=digest(request['payload']))
   need(encode(actual)==encode(doc['cursor_binding']['operations'][ordinal-1]),'REQUEST_BINDING_MISMATCH')
   aid,sc=ev['next_attempt_id'],ev['next_scope_id']
   r=j.reserve(str(p/'requests.jsonl'),baseline_id=h['baseline_id'],baseline_count=h['baseline_count'],hard_cap=h['hard_cap'],attempt_id=aid,scope_id=sc)
   need(r['status']=='RESERVED','RESERVATION_UNCERTAIN')
   after=c.evaluate_write_cursor(bounded(p/'requests.jsonl',1048576),h,doc['cursor_binding']);need(after['sequence_state']=='IN_FLIGHT' and after['attempted_count']==ordinal,'RESERVATION_UNCERTAIN')
  return result('RESERVED_OFFLINE_ONLY',attempt_id=aid,ordinal=ordinal)
 except Exception as e:return result(str(e) if type(e)is Refusal else 'IO_OR_INPUT_UNCERTAIN')
def finish(root,expected_scope_sha256,attempt_id,outcome):
 try:
  need(type(attempt_id)is str and type(outcome)is str and outcome in ('ok','error','unknown','interrupted'),'BAD_FINISH')
  with phase(root) as p:
   doc=load(p,expected_scope_sha256);j,c=dependencies();h=doc['header'];raw=bounded(p/'requests.jsonl',1048576);ev=c.evaluate_write_cursor(raw,h,doc['cursor_binding'])
   need(ev['sequence_state']=='IN_FLIGHT','CURSOR_NOT_IN_FLIGHT')
   # Pending attempt identity is derived from the consumed ordinal, never caller-selected.
   n=ev['attempted_count'];g,b,ops=c._bind(doc['cursor_binding']);wanted=c._derive(g,b,ops)[n-1][1];need(attempt_id==wanted,'ATTEMPT_MISMATCH')
   r=j.finish(str(p/'requests.jsonl'),baseline_id=h['baseline_id'],baseline_count=h['baseline_count'],hard_cap=h['hard_cap'],attempt_id=attempt_id,outcome=outcome)
   need(r['status']=='FINISHED','FINISH_UNCERTAIN')
   after=c.evaluate_write_cursor(bounded(p/'requests.jsonl',1048576),h,doc['cursor_binding']);need(after['sequence_state'] in ('READY_STRUCTURAL_ONLY','COMPLETE','STOPPED'),'FINISH_UNCERTAIN')
  return result('FINISHED_OFFLINE_ONLY',sequence_state=after['sequence_state'])
 except Exception as e:return result(str(e) if type(e)is Refusal else 'IO_OR_INPUT_UNCERTAIN')
