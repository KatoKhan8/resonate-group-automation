import copy,hashlib,importlib.util,json,pathlib,tempfile,threading,unittest
from concurrent.futures import ThreadPoolExecutor
P=pathlib.Path(__file__).with_name('acquisition_child.PROPOSED.py')
s=importlib.util.spec_from_file_location('child_proof',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
q=pathlib.Path(__file__).with_name('request_manifest.PROPOSED.py');s=importlib.util.spec_from_file_location('manifest_proof',q);manifest=importlib.util.module_from_spec(s);s.loader.exec_module(manifest)
class Proof(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='acquisition-child-proof-');self.root=pathlib.Path(self.tmp.name).resolve()/'canary540-read-fixture';self.root.mkdir();self.calls=[]
  self.g=dict(schema='canary540-acquisition-child/1',workspace_id=10,campaign_id=540,lead_ids=[1,2,3,4],child_sha256=hashlib.sha256(P.read_bytes()).hexdigest(),issued_at=100,expires_at=200,root=str(self.root),root_identity=m.identity(self.root),scope_id='fixture',max_attempts=32,manifest_sha256=m.digest(manifest.build_manifest([1,2,3,4])))
 def tearDown(self):self.tmp.cleanup()
 def key(self):
  self.assertTrue((self.root/'attempt-1.claimed').exists());self.calls.append('key');return 'synthetic-private-key'
 def wire(self,url,headers,timeout,bound):
  self.calls.append('wire');self.assertEqual(headers['Authorization'],'Bearer synthetic-private-key');self.assertEqual(timeout,20);return dict(http_status=200,url=url,raw=b'{"data":[]}')
 def invoke(self,g=None,**kwargs):
  grant=self.g if g is None else g;raw=json.dumps(grant).encode()
  args=dict(ordinal=1,route='/users',page=None,request_sha256=m.digest(dict(ordinal=1,route='/users',page=None)),clock=lambda:150,key_reader=self.key,transport=self.wire);args.update(kwargs)
  return m.run_child(raw,hashlib.sha256(raw).hexdigest(),**args)
 def test_claim_precedes_key_response_and_duplicate_refusal(self):
  out=self.invoke();self.assertEqual(self.calls,['key','wire']);self.assertFalse(out['producer_authenticated']);self.assertEqual(out['raw'],b'{"data":[]}')
  with self.assertRaises(ValueError):self.invoke()
  self.assertEqual(self.calls,['key','wire'])
  claim=json.loads((self.root/'attempt-1.claimed').read_bytes());self.assertNotIn('synthetic-private-key',str(claim))
 def test_grant_expiry_tamper_scope_and_bool_before_claim_or_key(self):
  for field,value in [('workspace_id',True),('campaign_id',541),('child_sha256','a'*64),('issued_at',True),('expires_at',701),('lead_ids',[1,1,3,4]),('manifest_sha256','a'*64),('root_identity',['1','2'])]:
   with self.subTest(field=field),self.assertRaises(ValueError):self.invoke(g=dict(self.g,**{field:value}))
  for kwargs in (dict(clock=lambda:200),dict(route='/leads/1'),dict(ordinal=True),dict(page=True),dict(request_sha256='a'*64)):
   with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):self.invoke(**kwargs)
  raw=json.dumps(self.g).encode()
  with self.assertRaises(ValueError):m.run_child(raw+b' ',hashlib.sha256(raw).hexdigest(),ordinal=1,route='/users',page=None,request_sha256='a'*64,clock=lambda:150,key_reader=self.key,transport=self.wire)
  self.assertEqual(self.calls,[]);self.assertEqual(list(self.root.iterdir()),[])
 def test_two_simultaneous_same_ordinal_only_one_key_and_wire(self):
  gate=threading.Barrier(2)
  def run():
   gate.wait()
   try:self.invoke();return True
   except ValueError:return False
  with ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(lambda _:run(),range(2)))
  self.assertEqual(sum(out),1);self.assertEqual(self.calls.count('key'),1);self.assertEqual(self.calls.count('wire'),1)
 def test_downstream_failure_keeps_claim_no_retry(self):
  def failed(*args):self.calls.append('wire');raise OSError('uncertain')
  with self.assertRaises(OSError):self.invoke(transport=failed)
  with self.assertRaises(ValueError):self.invoke()
  self.assertEqual(self.calls,['key','wire']);self.assertTrue((self.root/'attempt-1.claimed').exists())
 def test_oversize_redirect_and_late_expiry_never_retry(self):
  for response in (dict(http_status=200,url=m.BASE+'/users',raw=b'x'*1048577),dict(http_status=200,url='https://other.invalid/users',raw=b'{}'),dict(http_status=302,url=m.BASE+'/users',raw=b''),dict(http_status=429,url=m.BASE+'/users',raw=b'')):
   with tempfile.TemporaryDirectory(prefix='child-fault-') as t:
    root=pathlib.Path(t).resolve()/'canary540-read-fixture';root.mkdir();g=dict(self.g,root=str(root),root_identity=m.identity(root));calls=[]
    def key():calls.append('key');return 'fake'
    def wire(*a):calls.append('wire');return response
    with self.assertRaises(ValueError):self.invoke(g=g,key_reader=key,transport=wire)
    with self.assertRaises(ValueError):self.invoke(g=g,key_reader=key,transport=wire)
    self.assertEqual(calls,['key','wire']);self.assertTrue((root/'attempt-1.claimed').exists())
  times=iter([150,150,200])
  with self.assertRaises(ValueError):self.invoke(clock=lambda:next(times))
  self.assertEqual(self.calls,['key']);self.assertTrue((self.root/'attempt-1.claimed').exists())
 def test_root_alias_and_replacement_refuse(self):
  g=dict(self.g,root=str(self.root/'..'/'canary540-read-fixture'))
  with self.assertRaises(ValueError):self.invoke(g=g)
  old=self.root.with_name('old');self.root.rename(old);self.root.mkdir()
  with self.assertRaises(ValueError):self.invoke()
  self.assertEqual(self.calls,[])
 def test_standard_factory_uses_fake_opener_only_and_no_hidden_request(self):
  import urllib.request
  from unittest import mock
  observed=[]
  class Response:
   status=200
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def geturl(self):return m.BASE+'/users'
   def read(self,bound):observed.append(('read',bound));return b'{}'
  class Opener:
   def open(self,request,timeout):
    observed.append(('open',request.get_method(),request.full_url,timeout));return Response()
  def build(*handlers):
   self.assertEqual(handlers[0].proxies,{})
   self.assertIsNone(handlers[1].redirect_request(None,None,302,None,None,None))
   return Opener()
  headers={'Authorization':'Bearer fake-secret','Accept':'application/json'}
  with mock.patch.object(urllib.request,'build_opener',side_effect=build):
   response=m.urllib_get(m.BASE+'/users',headers,20,1048576)
   self.assertEqual(set(response),{'http_status','url','raw'});self.assertNotIn('fake-secret',str(response))
   for suffix in ('/users?page=1','/custom-variables?page=9','/custom-variables?page=1&extra=1','/leads/01','/users#fragment'):
    with self.subTest(suffix=suffix),self.assertRaises(ValueError):m.urllib_get(m.BASE+suffix,headers,20,1048576)
  self.assertEqual(observed,[('open','GET',m.BASE+'/users',20),('read',1048577)])
 def test_real_subprocess_cli_refuses_all_execution_arguments(self):
  import subprocess,sys
  # A fresh interpreter blocks socket construction before running the actual CLI.
  wrapper="import runpy,socket,sys; socket.socket=lambda *a,**k: (_ for _ in ()).throw(AssertionError('network forbidden')); sys.argv=[sys.argv[1]]+sys.argv[2:]; runpy.run_path(sys.argv[0],run_name='__main__')"
  for arguments,code,status in (([],0,'PLAN_ONLY'),(['--execute-approved'],2,'REFUSED_EXECUTION_UNSUPPORTED'),(['--child'],2,'REFUSED_EXECUTION_UNSUPPORTED')):
   completed=subprocess.run([sys.executable,'-I','-B','-c',wrapper,str(P),*arguments],capture_output=True,text=True,timeout=10)
   self.assertEqual(completed.returncode,code,completed.stderr)
   result=json.loads(completed.stdout);self.assertEqual(result['status'],status);self.assertFalse(result['execute_supported']);self.assertFalse(result['send_allowed'])
   self.assertNotIn('synthetic-private-key',completed.stdout)
 def test_shared_preclaim_validation_has_no_attempt_or_key_side_effect(self):
  raw=json.dumps(self.g).encode()
  grant,root,rid=m.validate_request(raw,hashlib.sha256(raw).hexdigest(),ordinal=1,route='/users',page=None,request_sha256=m.digest(dict(ordinal=1,route='/users',page=None)),clock=lambda:150)
  self.assertEqual(root,self.root);self.assertEqual(rid,self.g['root_identity']);self.assertEqual(grant,self.g)
  self.assertEqual(list(self.root.iterdir()),[]);self.assertEqual(self.calls,[])
if __name__=='__main__':unittest.main()
