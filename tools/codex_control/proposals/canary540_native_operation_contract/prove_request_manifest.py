import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('request_slots',Path(__file__).with_name('request_manifest.PROPOSED.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class ManifestProof(unittest.TestCase):
    def test_exact_prepared_scope_has32_slots_and_both_bookends(self):
        rows=m.build_manifest([101,102,103,104])
        self.assertEqual(len(rows),32)
        self.assertEqual(rows[0],{'ordinal':1,'route':'/users','page':None})
        self.assertEqual(rows[-1],{'ordinal':32,'route':'/users','page':None})
        self.assertEqual([r['page'] for r in rows if r['route']=='/campaigns/540/leads'],list(range(1,9)))
        self.assertEqual(rows[14]['route'],'/campaigns/v1.1/540/sequence-steps')
        for row in rows:self.assertEqual(m.require_request([101,102,103,104],row),row)
        rows[1]['route']='/leads/999'
        self.assertEqual(m.build_manifest([101,102,103,104])[1]['route'],'/leads/101')

    def test_slot_binding_refuses_bool_route_query_extra_and_other_cohort(self):
        base=m.build_manifest([101,102,103,104])[6]
        for extra in [dict(ordinal=True),dict(page=True),dict(page=9),dict(route='/custom-variables'),
                      dict(route='/campaigns/540/leads?search=x'),dict(method='POST')]:
            with self.subTest(extra=extra):
                with self.assertRaises(m.ManifestRefused):m.require_request([101,102,103,104],dict(base,**extra))
        with self.assertRaises(m.ManifestRefused):m.require_request([201,102,103,104],m.build_manifest([101,102,103,104])[1])
        for ids in ([True,2,3,4],[1,1,3,4],[1,2,3],[1,2,3,9007199254740992]):
            with self.assertRaises(m.ManifestRefused):m.build_manifest(ids)

if __name__=='__main__':unittest.main()
