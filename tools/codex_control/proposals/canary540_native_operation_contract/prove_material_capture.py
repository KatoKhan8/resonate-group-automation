import copy, importlib.util, json
from pathlib import Path
import unittest
P=Path(__file__).with_name('material_capture.PROPOSED.py')
s=importlib.util.spec_from_file_location('material_proof',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

def frame(data,route,page=None,now=100):
 return dict(raw=json.dumps({'data':data}).encode(),route=route,page=page,observed_at=now,http_status=200,workspace_id=10)
def collection(rows,route,page=1,total=None,now=100):
 total=len(rows) if total is None else total
 x=frame(rows,route,page,now);x['raw']=json.dumps({'data':rows,'meta':dict(total=total,current_page=page,last_page=max(1,total),per_page=1)}).encode();return x

def frames():
 leads=[frame(dict(id=i,custom_variables=[{'name':'x','value':None},{'name':'x','value':'duplicate'}]),'/leads/'+str(i)) for i in range(1,5)]
 return leads+[frame(dict(id=540,status='Paused',total_leads=0),'/campaigns/540'),
  collection([], '/campaigns/540/leads'),
  frame(dict(sequence_id=77,sequence_steps=[dict(id=1,order='1',wait_in_days='0',attachments=[])]),'/campaigns/v1.1/540/sequence-steps'),
  collection([dict(id=2741)],'/campaigns/540/sender-emails'),
  collection([dict(name='one')],'/custom-variables',total=2),
  collection([dict(name='two')],'/custom-variables',page=2,total=2)]

class Proof(unittest.TestCase):
 def test_joined_components_preserve_duplicates_types_and_missing_authority(self):
  owner=m.MaterialCapture([1,2,3,4],100)
  for x in frames():owner.feed(x)
  out=owner.finish();self.assertEqual(out['attempts'],10);self.assertFalse(out['snapshot_ready']);self.assertFalse(out['producer_authenticated'])
  self.assertEqual(len(out['receipts']),10);self.assertFalse(out['workspace_bookends_verified'])
  self.assertEqual(out['receipts'][0]['route'],'/leads/1');self.assertEqual(out['receipts'][0]['http_status'],200)
  self.assertEqual(len(out['receipts'][0]['response_sha256']),64)
  components=out['components'];self.assertEqual(components[0]['observation']['data']['custom_variables'][0]['value'],None)
  self.assertEqual(len(components[0]['observation']['data']['custom_variables']),2)
  self.assertEqual(components[5]['observation']['attached_lead_ids'],[])
  self.assertEqual(components[6]['observation']['data']['sequence_steps'][0]['order'],'1')
  self.assertIn('sequence_title',components[6]['observation']['missing_authority'])
  self.assertEqual(components[-1]['observation']['inventory']['declared_names'],['one','two'])
  with self.assertRaises(m.Refused):owner.finish()
 def test_partial_wrong_route_malformed_and_page_timeout_are_terminal(self):
  owner=m.MaterialCapture([1,2,3,4],100);owner.feed(frames()[0])
  with self.assertRaises(m.Refused):owner.finish()
  with self.assertRaises(m.Refused):owner.feed(frames()[1])
  for mutate in (lambda fs:fs[0].update(route='/leads/9'),lambda fs:fs[0].update(raw=b'{'),
                 lambda fs:fs[-1].update(observed_at=161),lambda fs:fs[0].update(workspace_id=True),
                 lambda fs:fs[-1].update(page=1)):
   fs=frames();mutate(fs);owner=m.MaterialCapture([1,2,3,4],100)
   with self.assertRaises((m.Refused,ValueError)):
    for x in fs:owner.feed(x)
   with self.assertRaises(m.Refused):owner.finish()
 def test_aggregate_and_global_time_bounds(self):
  fs=frames()
  # Pad valid JSON without changing decoded material; each response <1MiB.
  for x in fs:x['raw']+=b' '*(1048576-100-len(x['raw']))
  owner=m.MaterialCapture([1,2,3,4],100)
  with self.assertRaises(m.Refused):
   for x in fs:owner.feed(x)
  self.assertGreater(owner.bytes_seen,7*1048576)
  fs=frames();fs[3]['observed_at']=701;owner=m.MaterialCapture([1,2,3,4],100)
  with self.assertRaises(m.Refused):
   for x in fs:owner.feed(x)
 def test_binding_and_extra_frame_refuse(self):
  for ids in ([1,1,3,4],[True,2,3,4],[1,2,3]):
   with self.assertRaises(m.Refused):m.MaterialCapture(ids,100)
  owner=m.MaterialCapture([1,2,3,4],100)
  for x in frames():owner.feed(x)
  with self.assertRaises(m.Refused):owner.feed(frames()[0])
  with self.assertRaises(m.Refused):owner.finish()
if __name__=='__main__':unittest.main()
