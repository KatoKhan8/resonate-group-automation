"""Company research, person research, and exactly what the model was shown.

The question these have to answer is "why did the system write this sentence?".
That means every fact carries provenance, an absence is recorded as an absence,
and the evidence list the model saw is the evidence list the page shows.
"""
import unittest

from src import dossier, evidence, personalization, synthetic
from tests.campaignbase import CampaignTest


class DossierTest(CampaignTest):
    def records(self, size=56):
        return synthetic.dataset(size, self.config)

    def first(self, shape, size=56):
        recs = self.records(size)
        return recs[synthetic.indices_of(shape, size)[0]]


class TestTheThreeObjects(DossierTest):
    def test_the_dossier_carries_all_three_by_name(self):
        rec = self.first("clean_multichannel")
        built = dossier.build(rec, rec["contacts"][0], self.config)
        for name in ("company_research", "person_research",
                     "personalization_evidence"):
            self.assertIn(name, built)

    def test_company_and_person_research_are_separate_objects(self):
        rec = self.first("clean_multichannel")
        built = dossier.build(rec, rec["contacts"][0], self.config)
        self.assertNotEqual(built["company_research"],
                            built["person_research"])
        self.assertIn("structured", built["company_research"])
        self.assertIn("role", built["person_research"])

    def test_company_research_keeps_structured_data_separate_from_facts(self):
        rec = self.first("clean_multichannel")
        result = dossier.company_research(rec)
        self.assertIn("industry", result["structured"])
        self.assertIsInstance(result["facts"], list)

    def test_person_research_includes_role_which_needs_no_web_request(self):
        rec = self.first("clean_multichannel")
        result = dossier.person_research(rec, rec["contacts"][0])
        self.assertTrue(result["role"]["title"])
        self.assertTrue(result["role"]["persona"])


class TestProvenance(DossierTest):
    def test_every_fact_carries_where_it_came_from(self):
        rec = self.first("clean_multichannel")
        for row in dossier.company_research(rec)["facts"]:
            for field in ("source_type", "source_url", "provider",
                          "published_at"):
                self.assertIn(field, row["provenance"])

    def test_a_fact_with_no_source_still_says_so_rather_than_hiding(self):
        rec = self.first("clean_multichannel")
        rec["research"][0]["source_url"] = None
        row = dossier.company_research(rec)["facts"][0]
        self.assertIsNone(row["provenance"]["source_url"])

    def test_no_raw_provider_payload_reaches_the_dossier(self):
        rec = self.first("clean_multichannel")
        rec["research"][0]["raw"] = {"secret": "should never appear"}
        built = dossier.build(rec, rec["contacts"][0], self.config)
        self.assertNotIn("should never appear", str(built))


class TestAbsenceIsRecorded(DossierTest):
    def test_a_person_with_no_public_content_says_so_explicitly(self):
        rec = self.first("clean_multichannel")
        result = dossier.person_research(rec, rec["contacts"][0])
        self.assertFalse(result["available"])
        self.assertTrue(result["unavailable_because"])

    def test_nothing_is_inferred_from_that_absence(self):
        rec = self.first("clean_multichannel")
        result = dossier.person_research(rec, rec["contacts"][0])
        self.assertEqual(result["facts"], [])
        self.assertEqual(result["fact_count"], 0)

    def test_a_hook_alone_is_still_something_to_lead_with(self):
        """No retained research is not the same as nothing to say."""
        rec = self.first("no_research")
        self.assertEqual(rec["research"], [])
        lines = dossier.why_this_company(rec, self.config)
        self.assertIn(rec["hook"], lines)

    def test_a_record_with_neither_research_nor_hook_says_so(self):
        rec = self.first("no_research")
        rec["hook"] = None
        lines = dossier.why_this_company(rec, self.config)
        self.assertTrue(any("nothing specific" in line for line in lines),
                        lines)

    def test_the_person_summary_names_the_fallback_when_content_is_missing(self):
        rec = self.first("clean_multichannel")
        lines = dossier.why_this_person(rec, rec["contacts"][0], self.config)
        self.assertTrue(any("leans on the role" in line for line in lines))


class TestWhatTheModelSaw(DossierTest):
    def test_the_selected_list_is_what_the_decision_named(self):
        rec = self.first("clean_multichannel")
        contact = rec["contacts"][0]
        result = dossier.personalization_evidence(rec, contact, self.config)
        self.assertEqual(result["selected_evidence_ids"],
                         contact["personalization"]["selected_evidence_ids"])

    def test_it_reports_how_many_were_considered_not_only_chosen(self):
        rec = self.first("clean_multichannel")
        result = dossier.personalization_evidence(rec, rec["contacts"][0],
                                                  self.config)
        self.assertGreaterEqual(result["considered"], len(result["selected"]))

    def test_it_carries_the_angle_persona_and_reason(self):
        rec = self.first("clean_multichannel")
        result = dossier.personalization_evidence(rec, rec["contacts"][0],
                                                  self.config)
        for field in ("persona", "angle", "pain_point", "reason_for_contact"):
            self.assertIn(field, result)

    def test_evidence_deleted_after_selection_is_surfaced_not_swallowed(self):
        rec = self.first("clean_multichannel")
        contact = rec["contacts"][0]
        contact["personalization"]["selected_evidence_ids"] = ["ev-that-is-gone"]
        result = dossier.personalization_evidence(rec, contact, self.config)
        self.assertEqual(result["dangling_evidence_ids"], ["ev-that-is-gone"])
        self.assertEqual(result["selected"], [])

    def test_nothing_outside_the_selection_appears_in_it(self):
        rec = self.first("clean_multichannel")
        contact = rec["contacts"][0]
        rec["research"].append(evidence.make(
            "An unrelated fact nobody selected.", "https://x.test/other",
            "careers_page", "apify", rec["id"], published_at="2026-08-01",
            today=synthetic.TODAY))
        result = dossier.personalization_evidence(rec, contact, self.config)
        facts = [row["fact"] for row in result["selected"]]
        self.assertNotIn("An unrelated fact nobody selected.", facts)


class TestItStaysReadOnly(DossierTest):
    def test_it_calls_no_provider(self):
        rec = self.first("clean_multichannel")
        dossier.build(rec, rec["contacts"][0], self.config)
        self.assertEqual(self.cassette.calls, [])

    def test_it_writes_nothing_to_the_store(self):
        import inspect
        source = inspect.getsource(dossier)
        for banned in ("store.save", "store.patch", "personalization.apply"):
            self.assertNotIn(banned, source, banned)

    def test_for_record_covers_the_selected_contacts(self):
        rec = self.first("clean_multichannel")
        built = dossier.for_record(rec, self.config)
        self.assertEqual(len(built),
                         len(personalization.selected_contacts(rec,
                                                               self.config)))


if __name__ == "__main__":
    unittest.main()
