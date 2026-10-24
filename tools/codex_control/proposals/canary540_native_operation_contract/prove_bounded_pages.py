import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('bounded_pages', Path(__file__).with_name('bounded_pages.PROPOSED.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def frame(rows, page=1, total=2, per=1):
    return json.dumps({'data':rows,'meta':{'current_page':page,'total':total,
        'per_page':per,'last_page':max(1,(total+per-1)//per)}}).encode()

def feed(owner, raw, page=1, **kwargs):
    args=dict(page=page,workspace_id=10,observed_at=100+page,
              http_status=200,endpoint='/custom-variables')
    args.update(kwargs)
    owner.feed(raw,**args)

def finish(owner, **kwargs):
    args=dict(workspace_id=10,observed_at=103,unique_field='name')
    args.update(kwargs)
    return owner.finish(**args)

class BoundedPagesProof(unittest.TestCase):
    def test_lossless_two_pages_and_empty_inventory(self):
        owner=m.PageAssembly(10,100)
        first={'name':'one','value':None,'custom_variables':[{'name':'x','value':None},{'name':'x','value':'again'}]}
        feed(owner,frame([first]))
        feed(owner,frame([{'name':'two','value':'original'}],2),2)
        result=finish(owner)
        self.assertEqual(result['rows'][0],first)
        self.assertEqual(len(result['receipts']),2)
        self.assertEqual(result['inventory'], {'workspace_id':10,'complete':True,'declared_names':['one','two']})
        self.assertFalse(result['producer_authenticated'])
        self.assertFalse(result['freshness_proven'])
        self.assertFalse(result['readiness'])
        with self.assertRaises(m.AcquisitionRefused): finish(owner)
        empty=m.PageAssembly(10,100)
        feed(empty,frame([],total=0))
        self.assertEqual(finish(empty)['rows'],[])

    def test_cross_page_alias_and_missing_page_fail_terminal(self):
        owner=m.PageAssembly(10,100)
        feed(owner,frame([{'name':'ONE'}]))
        feed(owner,frame([{'name':'one'}],2),2)
        with self.assertRaises(m.AcquisitionRefused): finish(owner)
        missing=m.PageAssembly(10,100)
        feed(missing,frame([{'name':'one'}]))
        with self.assertRaises(m.AcquisitionRefused): finish(missing)
        with self.assertRaises(m.AcquisitionRefused): feed(missing,frame([{'name':'two'}],2),2)

    def test_drift_bounds_and_transport_fail_closed(self):
        cases=[dict(workspace_id=True),dict(workspace_id=11),dict(http_status=401),
               dict(endpoint='/leads'),dict(observed_at=161),dict(page=2)]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                owner=m.PageAssembly(10,100)
                with self.assertRaises(m.AcquisitionRefused): feed(owner,frame([{'name':'one'}]),**kwargs)
                with self.assertRaises(m.AcquisitionRefused): feed(owner,frame([{'name':'one'}]))
        for raw in [frame([{'name':'one','workspace_id':True}]),frame([],total=2),
                    b'{"data":[],"data":[],"meta":{}}',b'{"data":[NaN],"meta":{}}',
                    frame([{'name':'one','value':float('inf')}]).replace(b'Infinity',b'1e999'),
                    frame([{'name':'one'}]).replace(b'"data":',b'"workspace_id":11,"data":')]:
            with self.subTest(raw=raw):
                with self.assertRaises(m.AcquisitionRefused): feed(m.PageAssembly(10,100),raw)
        drift=m.PageAssembly(10,100)
        feed(drift,frame([{'name':'one'}]))
        with self.assertRaises(m.AcquisitionRefused): feed(drift,frame([{'name':'two'}],2,total=3),2)
        with self.assertRaises(m.AcquisitionRefused): feed(m.PageAssembly(10,100,max_bytes=10),frame([{'name':'one'}]))

    def test_extra_page_bookend_and_bool_metadata(self):
        owner=m.PageAssembly(10,100)
        feed(owner,frame([{'name':'one'}],total=1))
        with self.assertRaises(m.AcquisitionRefused): feed(owner,frame([],2,total=1),2)
        owner=m.PageAssembly(10,100)
        feed(owner,frame([{'name':'one'}],total=1))
        with self.assertRaises(m.AcquisitionRefused): finish(owner,workspace_id=11)
        owner=m.PageAssembly(10,100)
        feed(owner,frame([{'id':1,'name':'one'}],total=1))
        with self.assertRaises(m.AcquisitionRefused): finish(owner,unique_field='id')
        data=json.loads(frame([{'name':'one'}],total=1))
        data['meta']['total']=True
        with self.assertRaises(m.AcquisitionRefused): feed(m.PageAssembly(10,100),json.dumps(data).encode())

class SingleObservationProof(unittest.TestCase):
    def parse(self, data, route='/campaigns/v1.1/540/sequence-steps', **kw):
        args=dict(route=route,http_status=200,workspace_id=10)
        args.update(kw)
        return m.decode_single_response(json.dumps({'data':data}).encode(),**args)

    def test_v11_preserves_actual_types_and_extra_metadata_without_title_guess(self):
        data={'sequence_id':77,'sequence_steps':[{'id':88,'order':'1','wait_in_days':'3',
            'attachments':[],'active':True,'variant_from_step_id':None}]}
        result=self.parse(data)
        self.assertEqual(result['data'],data)
        self.assertIn('sequence_title',result['missing_authority'])
        self.assertFalse(result['snapshot_ready'])
        self.assertFalse(result['producer_authenticated'])
        data['title']='Observed title'
        self.assertNotIn('sequence_title',self.parse(data)['missing_authority'])
        self.assertFalse(self.parse(data)['snapshot_ready'])

    def test_full_lead_duplicates_null_and_fields_survive(self):
        data={'id':101,'email':'synthetic@example.invalid','custom_variables':[
            {'name':'copy','value':None},{'name':'copy','value':'second','extra':True}],
            'lead_campaign_data':[{'id':123}]}
        result=self.parse(data,'/leads/101',lead_id=101)
        self.assertEqual(result['data'],data)
        self.assertIn('canonical_identity_binding',result['missing_authority'])
        with self.assertRaises(m.AcquisitionRefused): self.parse(data,'/leads/102',lead_id=102)

    def test_campaign_count_never_substitutes_for_member_pages(self):
        result=self.parse({'id':540,'status':'Paused','total_leads':0},'/campaigns/540')
        self.assertIn('exhaustive_membership',result['missing_authority'])
        self.assertFalse(result['snapshot_ready'])

    def test_single_response_scope_and_malformed_matrix(self):
        good={'sequence_id':77,'sequence_steps':[{'id':88}]}
        for kw in [dict(http_status=401),dict(workspace_id=True),dict(route='/campaigns/541'),dict(lead_id=True)]:
            with self.subTest(kw=kw):
                with self.assertRaises(m.AcquisitionRefused): self.parse(good,**kw)
        for data in [dict(good,sequence_id=True),dict(good,title=None),
                     dict(good,workspace_id=11),dict(good,sequence_steps=[{'id':88},{'id':88}])]:
            with self.subTest(data=data):
                with self.assertRaises(m.AcquisitionRefused): self.parse(data)
        for raw in [b'{"data":{},"data":{}}',b'{"data":{"value":1e999}}']:
            with self.assertRaises(m.AcquisitionRefused):
                m.decode_single_response(raw,route='/campaigns/540',http_status=200,workspace_id=10)

class MembershipProof(unittest.TestCase):
    endpoint='/campaigns/540/leads'
    def member_feed(self,owner,raw,page=1):
        owner.feed(raw,page=page,workspace_id=10,observed_at=100+page,http_status=200,endpoint=self.endpoint)
    def test_empty_or_full_membership_comes_from_exhaustive_pages(self):
        empty=m.PageAssembly(10,100,endpoint=self.endpoint)
        self.member_feed(empty,frame([],total=0))
        self.assertEqual(finish(empty,unique_field='id')['attached_lead_ids'],[])
        full=m.PageAssembly(10,100,endpoint=self.endpoint)
        row={'id':101,'campaign_id':540,'custom_variables':[{'name':'one','value':None}]}
        self.member_feed(full,frame([row]))
        self.member_feed(full,frame([{'id':102}],2),2)
        result=finish(full,unique_field='id')
        self.assertEqual(result['attached_lead_ids'],[101,102])
        self.assertEqual(result['rows'][0],row)
        self.assertFalse(result['readiness'])
        self.assertFalse(result['producer_authenticated'])
    def test_membership_duplicates_foreign_and_missing_pages_refuse(self):
        for row in [{'id':True},{'id':101,'campaign_id':541},{'id':101,'campaign_id':True}]:
            owner=m.PageAssembly(10,100,endpoint=self.endpoint)
            with self.assertRaises(m.AcquisitionRefused):
                self.member_feed(owner,frame([row],total=1))
                finish(owner,unique_field='id')
        for raw in [frame([],total=0).replace(b'"data":',b'"campaign_id":541,"data":'),
                    frame([],total=0).replace(b'"total":',b'"campaign_id":true,"total":')]:
            with self.assertRaises(m.AcquisitionRefused):
                self.member_feed(m.PageAssembly(10,100,endpoint=self.endpoint),raw)
        duplicate=m.PageAssembly(10,100,endpoint=self.endpoint)
        self.member_feed(duplicate,frame([{'id':101}]))
        self.member_feed(duplicate,frame([{'id':101}],2),2)
        with self.assertRaises(m.AcquisitionRefused): finish(duplicate,unique_field='id')
        partial=m.PageAssembly(10,100,endpoint=self.endpoint)
        self.member_feed(partial,frame([{'id':101}]))
        with self.assertRaises(m.AcquisitionRefused): finish(partial,unique_field='id')

if __name__=='__main__': unittest.main()
