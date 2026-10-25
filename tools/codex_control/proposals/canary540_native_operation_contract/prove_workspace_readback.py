import importlib.util,json,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('workspace_bookend',Path(__file__).with_name('workspace_readback.PROPOSED.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Proof(unittest.TestCase):
 def test_actual_previously_used_schema_without_echo_substitution(self):
  raw=b'{"data":{"id":123,"workspace":{"id":10,"name":"PRODUCTIVE"}}}'
  self.assertEqual(m.decode_workspace(raw),10)
  for value in [{'workspace_id':10},{'data':{'workspace_id':10}},
                {'data':{'workspace':{'id':True,'name':'PRODUCTIVE'}}},
                {'data':{'workspace':{'id':10,'name':'other'}}},
                {'data':{'workspace':{'id':11,'name':'PRODUCTIVE'}}},
                {'data':{'workspace':{'id':10,'name':'PRODUCTIVE','workspace_id':11}}}]:
   with self.subTest(value=value),self.assertRaises(m.Refused):m.decode_workspace(json.dumps(value).encode())
 def test_duplicate_nonfinite_invalid_and_bounded_json_refuse(self):
  for raw in [b'{"data":{},"data":{}}',b'{"data":{"extra":1e999}}',b'{',b'x'*1048577]:
   with self.subTest(size=len(raw)),self.assertRaises(m.Refused):m.decode_workspace(raw)
if __name__=='__main__':unittest.main()
