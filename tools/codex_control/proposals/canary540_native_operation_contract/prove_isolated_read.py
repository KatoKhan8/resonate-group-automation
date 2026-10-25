import base64,copy,hashlib,importlib.util,json,pathlib,subprocess,sys,tempfile,time,unittest
HERE=pathlib.Path(__file__).resolve().parent

def load(name,file):
 spec=importlib.util.spec_from_file_location(name,HERE/file);owner=importlib.util.module_from_spec(spec);spec.loader.exec_module(owner);return owner
I=load('isolated_proof','isolated_read.PROPOSED.py')
C=load('isolated_child','acquisition_child.PROPOSED.py')
M=load('isolated_manifest','request_manifest.PROPOSED.py')
P=load('isolated_parent','acquisition_parent.PROPOSED.py')
F=load('isolated_frames','prove_material_capture.py')
assert hashlib.sha256((HERE/'workspace_readback.PROPOSED.py').read_bytes()).hexdigest()=='e2ddefb5032da3e906e3285844a9165d3d6b388fa4b7abd8d618c3785ecee20f'
W=load('isolated_workspace','workspace_readback.PROPOSED.py')

class Proof(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='isolated-read-proof-');self.base=pathlib.Path(self.tmp.name).resolve();self.root=self.base/'canary540-read-fixture';self.root.mkdir();self.config=self.base/'config';self.config.mkdir();self.env=self.config/'.env'
  self.secret='synthetic-key-never-echo';self.env.write_bytes(('BISON_BASE='+C.BASE+'\nBISON_KEY='+self.secret+'\nUNRELATED=fake-unused\n').encode())
  self.manifest=M.build_manifest([1,2,3,4]);self.fixture=self.root/'fixture.private.json'
  source={(f['route'],f['page']):f for f in F.frames()};responses={}
  for request in self.manifest:
   key=(request['route'],request['page'])
   if request['route']=='/users':raw=json.dumps({'data':{'workspace':{'id':10,'name':'PRODUCTIVE'}}}).encode()
   elif key in source:raw=source[key]['raw']
   else:continue
   url=C.BASE+request['route']+('?page='+str(request['page']) if request['page']is not None else '')
   responses[str(request['ordinal'])]=dict(http_status=200,url=url,raw_b64=base64.b64encode(raw).decode())
  self.fixture.write_bytes(json.dumps(dict(schema='synthetic-isolated-responses/1',responses=responses)).encode())
  now=int(time.time());self.g=dict(schema='canary540-acquisition-child/1',workspace_id=10,campaign_id=540,lead_ids=[1,2,3,4],child_sha256=I.PINS['acquisition_child.PROPOSED.py'],issued_at=now-5,expires_at=now+590,root=str(self.root),root_identity=C.identity(self.root),scope_id='fixture',max_attempts=32,manifest_sha256=M.digest(self.manifest))
  self.grant=json.dumps(self.g).encode();self.grant_pin=I.sha(self.grant)
  self.a=dict(schema='isolated-read-authority/1',child_grant_sha256=self.grant_pin,entry_sha256=I.sha((HERE/'isolated_read.PROPOSED.py').read_bytes()),credential_path=str(self.env),credential_sha256=I.sha(self.env.read_bytes()),transport_mode='SYNTHETIC_ONLY',fixture_path=str(self.fixture),fixture_sha256=I.sha(self.fixture.read_bytes()))
 def tearDown(self):self.tmp.cleanup()
 def launcher(self,a=None,grant=None,grant_pin=None):
  a=self.a if a is None else a;raw=json.dumps(a).encode();return I.IsolatedRead(raw,I.sha(raw),self.grant if grant is None else grant,self.grant_pin if grant_pin is None else grant_pin)
 def workspace(self,raw):
  # Pin SAME pure decoder before use; no fixture-only workspace inference.
  self.assertEqual(I.sha((HERE/'workspace_readback.PROPOSED.py').read_bytes()),'e2ddefb5032da3e906e3285844a9165d3d6b388fa4b7abd8d618c3785ecee20f')
  return W.decode_workspace(raw)
 def test_real_twelve_children_full_phase_private_capture_and_claims(self):
  authority=json.dumps(self.a).encode()
  out=I.capture_phase(authority,I.sha(authority),self.grant,self.grant_pin)
  self.assertTrue(out['source_bound_launcher']);self.assertTrue(out['isolated_callback_supervised']);self.assertEqual(out['transport_mode'],'SYNTHETIC_ONLY')
  self.assertEqual(out['attempts'],12);self.assertFalse(out['readiness']);self.assertFalse(out['producer_authenticated']);self.assertTrue(out['workspace_bookend_assertions_match'])
  for ordinal in (1,2,3,4,5,6,7,15,16,24,25,32):
   self.assertTrue((self.root/('attempt-'+str(ordinal)+'.claimed')).exists());self.assertTrue((self.root/('response-'+str(ordinal)+'.private.bin')).exists())
  self.assertEqual(len(list(self.root.glob('attempt-*.claimed'))),12)
  self.assertNotIn(self.secret,str(out));self.assertFalse(self.launcher().metadata['operator_authority_authenticated'])
 def test_authority_mode_source_and_grant_tamper_before_claim(self):
  for field,value in (('transport_mode','UNKNOWN'),('entry_sha256','a'*64),('child_grant_sha256','a'*64)):
   with self.subTest(field=field),self.assertRaises(ValueError):self.launcher(dict(self.a,**{field:value}))
  with self.assertRaises(ValueError):self.launcher(grant=self.grant+b' ')
  launcher=self.launcher()
  with self.assertRaises(ValueError):launcher(dict(self.manifest[0],route='/leads/1'),20)
  with self.assertRaises(ValueError):launcher(self.manifest[0],True)
  self.assertEqual(list(self.root.glob('attempt-*.claimed')),[])
  from unittest import mock
  authority=json.dumps(self.a).encode()
  with mock.patch.dict(I.PINS,{'workspace_readback.PROPOSED.py':'a'*64}),self.assertRaises(ValueError):
   I.capture_phase(authority,I.sha(authority),self.grant,self.grant_pin)
  self.assertFalse((self.root/'phase.claimed').exists())
 def test_wrong_fixture_and_credential_pin_stop_without_secret_output(self):
  for field in ('fixture_sha256','credential_sha256'):
   with self.subTest(field=field):
    launcher=self.launcher(dict(self.a,**{field:'a'*64}))
    with self.assertRaises(Exception) as ctx:launcher(self.manifest[0],20)
    self.assertNotIn(self.secret,str(ctx.exception))
    self.assertEqual((self.root/'attempt-1.claimed').exists(),field=='credential_sha256')
 def test_duplicate_keys_after_claim_and_generic_child_error(self):
  self.env.write_bytes(('BISON_BASE='+C.BASE+'\nBISON_KEY='+self.secret+'\nBISON_KEY=duplicate\n').encode());self.a['credential_sha256']=I.sha(self.env.read_bytes())
  with self.assertRaises(Exception) as ctx:self.launcher()(self.manifest[0],20)
  self.assertNotIn(self.secret,str(ctx.exception));self.assertTrue((self.root/'attempt-1.claimed').exists())
  completed=subprocess.run([sys.executable,'-I','-B',str(HERE/'isolated_read.PROPOSED.py'),'--child'],input=b'{"invalid":true}',capture_output=True,timeout=10)
  self.assertEqual(completed.returncode,2);self.assertEqual(json.loads(completed.stdout)['status'],'ISOLATED_READ_REFUSED');self.assertNotIn(self.secret.encode(),completed.stdout+completed.stderr);self.assertNotIn(b'Traceback',completed.stderr)
 def test_actual_process_deadline_leaves_parent_phase_sticky(self):
  launcher=self.launcher()
  with self.assertRaises(Exception):P.capture(self.grant,self.grant_pin,lead_ids=[1,2,3,4],clock=time.time,monotonic=time.monotonic,read_once=lambda request,remaining:launcher(request,.001),workspace_decoder=self.workspace)
  self.assertTrue((self.root/'phase.claimed').exists());self.assertTrue((self.root/'response-1.pending').exists())
  with self.assertRaises(FileExistsError):P.capture(self.grant,self.grant_pin,lead_ids=[1,2,3,4],clock=time.time,monotonic=time.monotonic,read_once=launcher,workspace_decoder=self.workspace)
 def test_network_mode_never_executed_by_proofs_and_cli_refuses_execution(self):
  # Constructing a future network capability never reads key or calls transport.
  future=self.launcher(dict(self.a,transport_mode='NETWORK_GET',fixture_path=None,fixture_sha256=None))
  self.assertEqual(future.metadata['transport_mode'],'NETWORK_GET');self.assertEqual(list(self.root.glob('attempt-*.claimed')),[])
  for args,code,status in (([],0,'PLAN_ONLY'),(['--execute-approved'],2,'REFUSED_EXECUTION_UNSUPPORTED')):
   completed=subprocess.run([sys.executable,'-I','-B',str(HERE/'isolated_read.PROPOSED.py'),*args],capture_output=True,timeout=10)
   self.assertEqual(completed.returncode,code);self.assertEqual(json.loads(completed.stdout)['status'],status)
if __name__=='__main__':unittest.main()
