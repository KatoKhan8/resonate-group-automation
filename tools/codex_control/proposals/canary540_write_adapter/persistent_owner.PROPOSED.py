"""Review-only persistent local journal facade; no grant/provider authentication.
Trusted local writer assumption: path checks are not anchored directory handles.
"""
import contextlib,contextvars,hashlib,pathlib,time,types
HERE=pathlib.Path(__file__).resolve().parent
ADAPTER_SHA='ee95d38f86dd57254fbc5a94917d15fd0b892b4a7f8442904155e04244c2e5c8'
class Refused(Exception):pass

def need(ok,reason):
 if not ok:raise Refused(reason)

def sha(raw):return hashlib.sha256(raw).hexdigest()

def identity(p):
 s=p.stat();return [str(s.st_dev),str(s.st_ino)]

def canonical(value):
 need(type(value)is str and value and '\0' not in value,'OWNER_PATH')
 p=pathlib.Path(value);need(p.is_absolute() and str(p)==str(p.resolve()) and p.is_dir(),'OWNER_PATH')
 for q in (p,*p.parents):
  need(not q.is_symlink() and not (hasattr(q,'is_junction') and q.is_junction()),'OWNER_ALIAS')
 return p

class PersistentJournal:
 def __init__(self,grant_raw,expected_grant_sha256):
  need(type(grant_raw)is bytes and len(grant_raw)<=262144 and type(expected_grant_sha256)is str and sha(grant_raw)==expected_grant_sha256,'GRANT_PIN')
  raw=(HERE/'adapter.py').read_bytes();need(sha(raw)==ADAPTER_SHA,'ADAPTER_PIN')
  adapter=types.ModuleType('private_persistent_namespace_adapter');adapter.__file__=str(HERE/'adapter.py')
  exec(compile(raw,adapter.__file__,'exec'),adapter.__dict__)
  grant=adapter.strict(grant_raw)
  wanted={'schema','workspace_id','campaign_id','owner_root','journal_name','owner_identity','root_identity','issued_at','expires_at','header_sha256','binding_sha256','scope_sha256'}
  need(type(grant)is dict and set(grant)==wanted and grant['schema']=='persistent-namespace-journal/1','GRANT_SCHEMA')
  need(type(grant['workspace_id'])is int and grant['workspace_id']==10 and type(grant['campaign_id'])is int and grant['campaign_id']==540,'GRANT_CONTEXT')
  name=grant['journal_name'];need(type(name)is str and name.startswith('canary540-') and 10<=len(name)<=64 and all(c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-' for c in name),'JOURNAL_NAME')
  for key in ('owner_identity','root_identity'):
   need(type(grant[key])is list and len(grant[key])==2 and all(type(v)is str and 1<=len(v)<=40 and v.isascii() and v.isdecimal() and (v=='0' or not v.startswith('0')) for v in grant[key]) and grant[key][1]!='0','ROOT_IDENTITY')
  need(type(grant['issued_at'])is int and type(grant['expires_at'])is int and 0<grant['issued_at']<grant['expires_at'],'GRANT_TIME')
  for key in ('header_sha256','binding_sha256','scope_sha256'):
   need(type(grant[key])is str and len(grant[key])==64 and all(c in '0123456789abcdef' for c in grant[key]),'MATERIAL_PIN')
  self._raw=grant_raw;self._pin=expected_grant_sha256;self._grant=grant;self._adapter=adapter
  self._owner=canonical(grant['owner_root']);self._root=self._owner/name
  self._mode=contextvars.ContextVar('persistent_journal_mode',default='none')
  self._validate(str(self._root))
  # Dedicated module namespace: never rebind the shared adapter or its callers.
  adapter.root_path=self._validate
  old_phase=adapter.phase;old_dependencies=adapter.dependencies
  @contextlib.contextmanager
  def phase(root):
   denied=False
   with old_phase(root) as scoped:
    self._validate(root)
    denied=self._mode.get() in ('initialize','reserve') and not self._current()
    if not denied:yield scoped
   if denied:raise adapter.Refusal('GRANT_EXPIRED_OR_NOT_YET_VALID')
  def dependencies():
   journal,cursor=old_dependencies();write=journal._write
   def checked_write(file,blob):
    if self._mode.get() in ('initialize','reserve'):
     need(self._current(),'GRANT_EXPIRED_AT_DURABLE_WRITE')
    return write(file,blob)
   journal._write=checked_write
   return journal,cursor
  adapter.phase=phase;adapter.dependencies=dependencies
 def _current(self):
  return self._grant['issued_at']<=time.time()<self._grant['expires_at']
 def _validate(self,root):
  need(sha(self._raw)==self._pin,'GRANT_PIN')
  # Detect mutation of decoded grant fields as well as raw bytes.
  need(self._adapter.encode(self._grant)==self._adapter.encode(self._adapter.strict(self._raw)),'GRANT_MUTATED')
  need(type(root)is str and pathlib.Path(root)==self._root,'OWNER_ROOT_MISMATCH')
  owner=canonical(self._grant['owner_root']);current=canonical(str(self._root))
  need(current.parent==owner and identity(owner)==self._grant['owner_identity'] and identity(current)==self._grant['root_identity'],'OWNER_REPLACED')
  for name in ('scope.json','requests.jsonl','phase.lock','requests.jsonl.lock'):self._adapter.safe_file(current/name)
  return current
 def _result(self,result):
  return dict(result,storage_scope='PERSISTENT_OWNER_BOUND_LOCAL_ONLY',grant_authenticated=False,producer_authenticated=False,send_allowed=False,write_allowed=False,readiness_clearance=False)
 def _call(self,mode,root,function,*args):
  token=self._mode.set(mode)
  try:
   self._validate(root)
   return self._result(function(root,*args))
  except Exception as exc:
   reason=str(exc) if type(exc)is Refused else 'PERSISTENT_OWNER_IO_OR_INPUT_UNCERTAIN'
   return self._result(self._adapter.result(reason))
  finally:self._mode.reset(token)
 def initialize(self,root,header,binding):
  try:
   h,b=self._adapter.clean(header),self._adapter.clean(binding)
   need(self._adapter.digest(h)==self._grant['header_sha256'] and self._adapter.digest(b)==self._grant['binding_sha256'],'GRANT_MATERIAL_MISMATCH')
   doc=self._adapter.scope_doc(h,b);need(self._adapter.digest(doc)==self._grant['scope_sha256'],'GRANT_SCOPE_MISMATCH')
  except Exception:
   return self._result(self._adapter.result('GRANT_MATERIAL_MISMATCH'))
  return self._call('initialize',root,self._adapter.initialize,h,b)
 def reserve_next(self,root,pin,ordinal,request):
  if type(pin)is not str or pin!=self._grant['scope_sha256']:return self._result(self._adapter.result('GRANT_SCOPE_MISMATCH'))
  return self._call('reserve',root,self._adapter.reserve_next,pin,ordinal,request)
 def finish(self,root,pin,attempt_id,outcome):
  # Existing cursor checks matching pending ID; expiry never creates a new attempt.
  if type(pin)is not str or pin!=self._grant['scope_sha256']:return self._result(self._adapter.result('GRANT_SCOPE_MISMATCH'))
  return self._call('finish',root,self._adapter.finish,pin,attempt_id,outcome)
