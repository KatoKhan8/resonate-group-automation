import hashlib,importlib.util,json,pathlib,tempfile,unittest
from unittest import mock
HERE=pathlib.Path(__file__).resolve().parent

def load(name,file):
 spec=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
P=load('parent_proof','acquisition_parent.PROPOSED.py')
F=load('material_frames','prove_material_capture.py')
M=load('parent_manifest','request_manifest.PROPOSED.py')
C=load('parent_child','acquisition_child.PROPOSED.py')
class Proof(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='parent-offline-proof-');self.root=pathlib.Path(self.tmp.name).resolve()/'canary540-read-fixture';self.root.mkdir();self.calls=[]
  self.leads=[1,2,3,4];self.manifest=M.build_manifest(self.leads)
  self.grant=dict(schema='canary540-acquisition-child/1',workspace_id=10,campaign_id=540,lead_ids=self.leads,child_sha256=hashlib.sha256((HERE/'acquisition_child.PROPOSED.py').read_bytes()).hexdigest(),issued_at=100,expires_at=700,root=str(self.root),root_identity=C.identity(self.root),scope_id='fixture',max_attempts=32,manifest_sha256=M.digest(self.manifest))
  self.frames={(f['route'],f['page']):f for f in F.frames()}
 def tearDown(self):self.tmp.cleanup()
 def wire(self,request,remaining):
  self.assertTrue((self.root/'phase.claimed').exists());self.assertTrue((self.root/('response-'+str(request['ordinal'])+'.pending')).exists())
  self.assertLessEqual(remaining,600);self.calls.append(request)
  raw=json.dumps({'workspace':10}).encode() if request['route']=='/users' else self.frames[(request['route'],request['page'])]['raw']
  return dict(raw=raw,http_status=200)
 def invoke(self,**overrides):
  raw=json.dumps(self.grant).encode();args=dict(lead_ids=self.leads,clock=lambda:150,monotonic=lambda:0,read_once=self.wire,workspace_decoder=lambda raw:json.loads(raw)['workspace']);args.update(overrides)
  return P.capture(raw,hashlib.sha256(raw).hexdigest(),**args)
 def test_complete_joined_twelve_calls_exact_slots_and_private_originals(self):
  out=self.invoke();self.assertEqual(out['attempts'],12);self.assertEqual([r['ordinal'] for r in self.calls],[1,2,3,4,5,6,7,15,16,24,25,32])
  self.assertTrue(out['workspace_bookend_assertions_match']);self.assertFalse(out['source_trust']);self.assertFalse(out['readiness']);self.assertFalse(out['hard_deadline_enforced'])
  self.assertEqual(out['material']['components'][5]['observation']['attached_lead_ids'],[])
  for receipt in out['receipts']:
   raw=(self.root/receipt['private_file']).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),receipt['response_sha256']);self.assertEqual(len(raw),receipt['response_bytes'])
  summary=json.loads((self.root/'phase.result.private.json').read_bytes())
  self.assertEqual(summary['attempts'],12);self.assertFalse(summary['readiness']);self.assertFalse(summary['provenance_authenticated'])
  self.assertEqual(summary['receipt_list_sha256'],C.digest(out['receipts']))
  with self.assertRaises(FileExistsError):self.invoke()
  self.assertEqual(len(self.calls),12)
 def test_wrong_workspace_auth_and_malformed_paging_stop_once_sticky(self):
  with self.assertRaises(ValueError):self.invoke(workspace_decoder=lambda _:True)
  self.assertEqual(len(self.calls),1)
  with self.assertRaises(FileExistsError):self.invoke()
  self.assertEqual(len(self.calls),1)
 def test_auth_error_and_malformed_collection_stop_before_followups(self):
  for mode in ('auth','paging'):
   with tempfile.TemporaryDirectory(prefix='parent-fault-') as tmp:
    root=pathlib.Path(tmp).resolve()/'canary540-read-fixture';root.mkdir();self.root=root;self.grant.update(root=str(root),root_identity=C.identity(root));self.calls=[]
    def wire(request,remaining):
     observed=self.wire(request,remaining)
     if mode=='auth':observed['http_status']=401
     elif request['ordinal']==7:observed['raw']=b'{"data":[],"meta":{"total":1,"current_page":1,"last_page":1,"per_page":1}}'
     return observed
    with self.assertRaises(ValueError):self.invoke(read_once=wire)
    self.assertEqual(len(self.calls),1 if mode=='auth' else 7)
    self.assertTrue((root/'phase.claimed').exists())
 def test_storage_failure_and_aggregate_bounds_keep_uncertainty(self):
  original=P.save
  def fail(root,name,raw):
   if name.endswith('.private.bin'):raise OSError('fixture disk failure')
   return original(root,name,raw)
  with mock.patch.object(P,'save',side_effect=fail),self.assertRaises(OSError):self.invoke()
  self.assertEqual(len(self.calls),1);self.assertTrue((self.root/'response-1.pending').exists())
  with tempfile.TemporaryDirectory(prefix='parent-large-') as tmp:
   self.root=pathlib.Path(tmp).resolve()/'canary540-read-fixture';self.root.mkdir();self.grant.update(root=str(self.root),root_identity=C.identity(self.root));self.calls=[]
   def large(request,remaining):
    result=self.wire(request,remaining);result['raw']+=b' '*(1048576-100-len(result['raw']));return result
   with self.assertRaises(ValueError):self.invoke(read_once=large)
   self.assertEqual(len(self.calls),9);self.assertFalse((self.root/'response-16.private.bin').exists())
 def test_monotonic_deadline_callback_exception_and_grant_refuse(self):
  times=iter([0,0,601])
  with self.assertRaises(ValueError):self.invoke(monotonic=lambda:next(times))
  self.assertEqual(self.calls,[]);self.assertTrue((self.root/'phase.claimed').exists())
  with tempfile.TemporaryDirectory(prefix='parent-grant-') as tmp:
   self.root=pathlib.Path(tmp).resolve()/'canary540-read-fixture';self.root.mkdir();self.grant.update(root=str(self.root),root_identity=C.identity(self.root));self.calls=[]
   self.grant['workspace_id']=True
   with self.assertRaises(ValueError):self.invoke()
   self.assertEqual(list(self.root.iterdir()),[])
   self.grant['workspace_id']=10
   def uncertain(request,remaining):self.calls.append(request);raise OSError('fixture child uncertain')
   with self.assertRaises(OSError):self.invoke(read_once=uncertain)
   self.assertEqual(len(self.calls),1);self.assertTrue((self.root/'response-1.pending').exists())
   with self.assertRaises(FileExistsError):self.invoke()
   self.assertEqual(len(self.calls),1)
if __name__=='__main__':unittest.main()
