import copy,hashlib,importlib.util,json,os,pathlib,subprocess,sys,tempfile,time,unittest
from unittest import mock
HERE=pathlib.Path(__file__).resolve().parent

def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
P=module('persistent_owner_proof',HERE/'persistent_owner.PROPOSED.py')
A=module('persistent_unchanged_adapter',HERE/'adapter.py')

def child(data_path,mode):
 data=json.loads(pathlib.Path(data_path).read_text());raw=data['grant'].encode();owner=P.PersistentJournal(raw,data['pin'])
 if 'gate' in data:
  until=time.monotonic()+10
  while not pathlib.Path(data['gate']).exists():
   if time.monotonic()>until:raise RuntimeError('fixture gate timeout')
   time.sleep(.01)
 ordinal=int(mode.removeprefix('reserve'))
 print(json.dumps(owner.reserve_next(data['root'],data['scope'],ordinal,data['binding']['operations'][ordinal-1])))

class Proof(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix='persistent-owner-proof-');self.base=pathlib.Path(self.temp.name).resolve();self.owner=self.base/'owner';self.owner.mkdir();self.root=self.owner/'canary540-fixture';self.root.mkdir()
  self.h=dict(schema='request-journal/1',baseline_id='synthetic-existing3',baseline_count=3,hard_cap=10)
  paths=[('POST','/api/custom-variables')]*2+[('PATCH','/api/leads/'+str(n)) for n in range(11,15)]+[('PUT','/api/campaigns/v1.1/sequence-steps/77')]
  self.b=dict(grant_id='synthetic-no-authority',plan_sha256='a'*64,operations=[dict(method=m,path=p,payload={'synthetic':str(i)}) for i,(m,p) in enumerate(paths)])
  self.scope=A.digest(A.scope_doc(self.h,self.b));now=int(time.time())
  self.g=dict(schema='persistent-namespace-journal/1',workspace_id=10,campaign_id=540,owner_root=str(self.owner),journal_name=self.root.name,owner_identity=P.identity(self.owner),root_identity=P.identity(self.root),issued_at=now-10,expires_at=now+120,header_sha256=A.digest(self.h),binding_sha256=A.digest(self.b),scope_sha256=self.scope)
  self.raw=A.encode(self.g);self.pin=hashlib.sha256(self.raw).hexdigest();self.facade=P.PersistentJournal(self.raw,self.pin)
  self.assertEqual('INITIALIZED_OFFLINE',self.facade.initialize(str(self.root),self.h,self.b)['reason'])
 def tearDown(self):self.temp.cleanup()
 def data(self,gate=None):
  data=dict(grant=self.raw.decode(),pin=self.pin,root=str(self.root),scope=self.scope,binding=self.b)
  if gate:data['gate']=str(gate)
  path=self.base/'child-fixture.json';path.write_text(json.dumps(data));return path
 def env(self):return {k:v for k,v in os.environ.items() if k.upper() in ('SYSTEMROOT','WINDIR','TEMP','TMP','PATH')}
 def invoke(self,mode):
  r=subprocess.run([sys.executable,'-B',str(pathlib.Path(__file__).resolve()),'--child',str(self.data()),mode],env=self.env(),capture_output=True,text=True,timeout=20)
  self.assertEqual(0,r.returncode,r.stderr);return json.loads(r.stdout)
 def test_real_process_restart_keeps_exact_cursor(self):
  first=self.invoke('reserve1');self.assertEqual('RESERVED_OFFLINE_ONLY',first['reason'])
  reopened=P.PersistentJournal(self.raw,self.pin);done=reopened.finish(str(self.root),self.scope,first['attempt_id'],'ok');self.assertEqual('FINISHED_OFFLINE_ONLY',done['reason'])
  second=self.invoke('reserve2');self.assertEqual('RESERVED_OFFLINE_ONLY',second['reason']);self.assertEqual(4,len((self.root/'requests.jsonl').read_bytes().splitlines()))
  self.assertFalse(second['grant_authenticated']);self.assertFalse(second['readiness_clearance'])
 def test_two_real_processes_reserve_same_ordinal_once(self):
  gate=self.base/'start.gate';data=self.data(gate);args=[sys.executable,'-B',str(pathlib.Path(__file__).resolve()),'--child',str(data),'reserve1']
  procs=[subprocess.Popen(args,env=self.env(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0) for _ in range(2)]
  gate.write_text('start');rows=[]
  for process in procs:
   out,err=process.communicate(timeout=20);self.assertEqual(0,process.returncode,err);rows.append(json.loads(out))
  self.assertEqual(1,sum(r['reason']=='RESERVED_OFFLINE_ONLY' for r in rows));self.assertEqual(2,len((self.root/'requests.jsonl').read_bytes().splitlines()))
 def test_expiry_refuses_new_attempt_but_settles_pending(self):
  first=self.facade.reserve_next(str(self.root),self.scope,1,self.b['operations'][0]);self.assertEqual('RESERVED_OFFLINE_ONLY',first['reason'])
  with mock.patch.object(P.time,'time',return_value=self.g['expires_at']+1):
   refused=self.facade.reserve_next(str(self.root),self.scope,2,self.b['operations'][1]);self.assertEqual('GRANT_EXPIRED_OR_NOT_YET_VALID',refused['reason']);self.assertFalse((self.root/'phase.lock').exists())
   done=self.facade.finish(str(self.root),self.scope,first['attempt_id'],'ok');self.assertEqual('FINISHED_OFFLINE_ONLY',done['reason'])
 def test_mutated_grant_or_scope_refuses_without_append(self):
  before=(self.root/'requests.jsonl').read_bytes()
  with self.assertRaises(P.Refused):P.PersistentJournal(self.raw+b' ',self.pin)
  self.facade._grant['campaign_id']=541;r=self.facade.reserve_next(str(self.root),self.scope,1,self.b['operations'][0]);self.assertEqual('GRANT_MUTATED',r['reason'])
  self.assertEqual(before,(self.root/'requests.jsonl').read_bytes())
 def test_replaced_root_identity_refuses_on_restart(self):
  old=self.owner/'canary540-old';self.assertTrue(self.base in self.root.resolve().parents and self.base in old.resolve().parents)
  self.root.rename(old);self.root.mkdir()
  with self.assertRaisesRegex(P.Refused,'OWNER_REPLACED'):P.PersistentJournal(self.raw,self.pin)
 def test_scope_material_and_wrong_owner_path_refuse(self):
  before=(self.root/'requests.jsonl').read_bytes();wrong=copy.deepcopy(self.b);wrong['operations'][0]['payload']['synthetic']='other'
  self.assertEqual('GRANT_MATERIAL_MISMATCH',self.facade.initialize(str(self.root),self.h,wrong)['reason'])
  self.assertEqual('OWNER_ROOT_MISMATCH',self.facade.reserve_next(str(self.owner),self.scope,1,self.b['operations'][0])['reason'])
  self.assertEqual(before,(self.root/'requests.jsonl').read_bytes())
 def test_expiry_at_durable_write_never_appends_and_retains_lock(self):
  before=(self.root/'requests.jsonl').read_bytes()
  with mock.patch.object(P.time,'time',side_effect=[self.g['issued_at']+1,self.g['expires_at']+1]):
   result=self.facade.reserve_next(str(self.root),self.scope,1,self.b['operations'][0])
  self.assertEqual('IO_OR_INPUT_UNCERTAIN',result['reason']);self.assertEqual(before,(self.root/'requests.jsonl').read_bytes());self.assertTrue((self.root/'phase.lock').exists())
 def test_joined_guarded_caller_uses_same_persistent_protocol(self):
  proof=module('joined_native_caller_proof',HERE.parent/'canary540_native_operation_contract/prove_guarded_caller.py')
  inner=proof.Proof();inner.setUp()
  try:
   inner.enabled_fixture();root=self.owner/'canary540-joined';root.mkdir()
   header=dict(schema='request-journal/1',baseline_id='synthetic',baseline_count=0,hard_cap=7)
   binding=dict(grant_id='synthetic-no-auth',plan_sha256=inner.owner.digest(inner.ops),operations=inner.ops)
   scope=A.digest(A.scope_doc(header,binding));grant=dict(self.g,journal_name=root.name,root_identity=P.identity(root),header_sha256=A.digest(header),binding_sha256=A.digest(binding),scope_sha256=scope)
   raw=A.encode(grant);pin=hashlib.sha256(raw).hexdigest();facade=P.PersistentJournal(raw,pin)
   self.assertEqual('INITIALIZED_OFFLINE',facade.initialize(str(root),header,binding)['reason'])
   result=inner.invoke(journal=facade,journal_root=str(root),journal_scope_sha256=scope)
   self.assertTrue(result['journal_settled']);self.assertFalse(result['readiness_clearance']);self.assertEqual(1,inner.calls.count('wire'))
   reopened=P.PersistentJournal(raw,pin);next_request=reopened.reserve_next(str(root),scope,2,inner.ops[1]);self.assertEqual('RESERVED_OFFLINE_ONLY',next_request['reason']);self.assertFalse(next_request['grant_authenticated'])
  finally:inner.tearDown()
 def test_pending_survives_restart_and_never_reinitializes(self):
  first=self.invoke('reserve1');self.assertEqual('RESERVED_OFFLINE_ONLY',first['reason'])
  self.assertEqual('CURSOR_NOT_READY',self.invoke('reserve1')['reason'])
  reopened=P.PersistentJournal(self.raw,self.pin);self.assertEqual('PHASE_LOCKED',reopened.initialize(str(self.root),self.h,self.b)['reason']);self.assertTrue((self.root/'phase.lock').exists())
if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='--child':child(sys.argv[2],sys.argv[3])
 elif sys.argv[1:]==['--portable']:
  names=[name for name in unittest.defaultTestLoader.getTestCaseNames(Proof) if name!='test_joined_guarded_caller_uses_same_persistent_protocol']
  print('Portable storage checks only; source-bound guarded-caller integration is excluded explicitly.',flush=True)
  result=unittest.TextTestRunner().run(unittest.TestSuite(Proof(name) for name in names));raise SystemExit(not result.wasSuccessful())
 else:unittest.main()
