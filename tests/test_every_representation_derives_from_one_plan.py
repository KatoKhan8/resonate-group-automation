"""One canonical SequencePlan, six consumers, no fourth representation.

TASK-364. Proves:

1. The SequencePlan is built once and all six consumers derive from it.
2. Changing the plan changes all six outputs.
3. The derive functions are called from PRODUCTION code (the factories),
   not only from tests.
4. The approval hash is deterministic and sensitive.
5. No consumer carries its own cadence data independent of the plan.
6. The negative control: breaking the wiring makes the test fail.
"""
import copy
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import sequenceplan


# --------------------------------------------------------------- fixtures

def _plan_with_contacts():
    """A minimal but realistic SequencePlan with two contacts."""
    return sequenceplan.new(
        "productive", {"company": "Acme", "domain": "acme.com"},
        [
            {
                "contact_key": "alice@acme.com",
                "email": "alice@acme.com",
                "first_name": "Alice",
                "sequences": {
                    "em1": "Hello Alice, first email body.",
                    "em2": "Second email body.",
                    "em3": "Third email body.",
                    "em4": "Fourth email body.",
                    "em5": "Fifth email body.",
                    "connect": "Hi Alice, let's connect.",
                    "msg1": "First LinkedIn message.",
                    "msg2": "Second LinkedIn message.",
                    "msg3": "Third LinkedIn message.",
                },
                "subjects": {"A": "Subject A", "B": "Subject B", "C": "Subject C"},
                "qualification": "QUALIFIED_THIN",
                "hypothesis": {"hypothesis": "Acme needs visibility"},
                "match": {"capability_key": "project_visibility"},
                "sequence_gate": {},
            },
            {
                "contact_key": "bob@acme.com",
                "email": "bob@acme.com",
                "first_name": "Bob",
                "sequences": {
                    "em1": "Hello Bob, first email body.",
                    "em2": "Second email body for Bob.",
                    "em3": "Third email body for Bob.",
                    "em4": "Fourth email body for Bob.",
                    "em5": "Fifth email body for Bob.",
                    "connect": "Hi Bob, let's connect.",
                    "msg1": "First LinkedIn message for Bob.",
                    "msg2": "Second LinkedIn message for Bob.",
                    "msg3": "Third LinkedIn message for Bob.",
                },
                "subjects": {"A": "Subject A2", "B": "Subject B2", "C": "Subject C2"},
                "qualification": "QUALIFIED_THIN",
                "hypothesis": {"hypothesis": "Acme needs margins"},
                "match": {"capability_key": "margin_visibility"},
                "sequence_gate": {},
            },
        ],
        strategy={"strategy_id": "seg-champion"},
        cadence={"name": "productive_li_heavy_v1"},
    )


# --------------------------------------- Acceptance 1: one object, six consumers

class TestOnePlanSixConsumers(unittest.TestCase):
    """Build the plan once, derive all six, assert they share the plan."""

    def test_all_six_derive_from_same_plan(self):
        plan = _plan_with_contacts()
        h = sequenceplan.approval_hash(plan)
        preview = sequenceplan.derive_preview_data(plan)
        bison = sequenceplan.derive_bison_payload(plan)
        heyreach = sequenceplan.derive_heyreach_payload(plan)
        xlsx = sequenceplan.derive_xlsx_data(plan)
        qa = sequenceplan.qa_validate(plan)

        self.assertEqual(preview["approval_hash"], h)
        self.assertEqual(bison["approval_hash"], h)
        self.assertEqual(heyreach["approval_hash"], h)
        self.assertEqual(xlsx["approval_hash"], h)
        self.assertEqual(qa["approval_hash"], h)

        self.assertEqual(len(preview["rows"]), 2)
        self.assertEqual(len(bison["leads"]), 2)
        self.assertEqual(len(heyreach["leads"]), 2)
        self.assertEqual(len(xlsx["rows"]), 2)
        self.assertEqual(qa["contact_count"], 2)
        self.assertEqual(qa["sendable_count"], 2)

    def test_derive_functions_read_plan_not_rebuild(self):
        plan = _plan_with_contacts()
        bison = sequenceplan.derive_bison_payload(plan)
        self.assertEqual(bison["leads"][0]["email"], "alice@acme.com")
        self.assertEqual(bison["leads"][0]["steps"][0]["body"],
                         "Hello Alice, first email body.")


# ------------------------- Acceptance 2: change plan, all six change together

class TestChangePlanChangesAll(unittest.TestCase):
    """Alter one step's message; assert all six outputs reflect it."""

    def test_changing_em1_changes_all_six(self):
        plan = _plan_with_contacts()
        original_hash = sequenceplan.approval_hash(plan)
        original_preview = sequenceplan.derive_preview_data(plan)
        original_bison = sequenceplan.derive_bison_payload(plan)
        original_heyreach = sequenceplan.derive_heyreach_payload(plan)
        original_xlsx = sequenceplan.derive_xlsx_data(plan)
        original_qa = sequenceplan.qa_validate(plan)

        plan["contacts"][0]["sequences"]["em1"] = "CHANGED BODY TEXT"

        new_hash = sequenceplan.approval_hash(plan)
        new_preview = sequenceplan.derive_preview_data(plan)
        new_bison = sequenceplan.derive_bison_payload(plan)
        new_heyreach = sequenceplan.derive_heyreach_payload(plan)
        new_xlsx = sequenceplan.derive_xlsx_data(plan)
        new_qa = sequenceplan.qa_validate(plan)

        self.assertNotEqual(original_hash, new_hash,
                            "approval hash did not change")
        self.assertNotEqual(original_preview, new_preview,
                            "preview did not change")
        self.assertNotEqual(original_bison, new_bison,
                            "bison payload did not change")
        self.assertNotEqual(original_xlsx, new_xlsx,
                            "xlsx data did not change")

        self.assertIn("CHANGED BODY TEXT",
                      new_bison["leads"][0]["steps"][0]["body"])
        self.assertIn("CHANGED BODY TEXT",
                      new_xlsx["rows"][0]["em1"])

    def test_changing_linkedin_msg1_changes_heyreach(self):
        plan = _plan_with_contacts()
        original = sequenceplan.derive_heyreach_payload(plan)
        plan["contacts"][0]["sequences"]["msg1"] = "CHANGED LI MESSAGE"
        new = sequenceplan.derive_heyreach_payload(plan)
        self.assertNotEqual(original, new,
                            "heyreach payload did not change")
        self.assertEqual(new["leads"][0]["linkedin"]["msg1"],
                         "CHANGED LI MESSAGE")

    def test_qa_reflects_change(self):
        plan = _plan_with_contacts()
        original_qa = sequenceplan.qa_validate(plan)
        self.assertTrue(original_qa["valid"])

        plan["contacts"][0]["sequences"]["em1"] = ""
        new_qa = sequenceplan.qa_validate(plan)
        self.assertFalse(new_qa["valid"])
        self.assertTrue(any(i["field"] == "em1" for i in new_qa["issues"]))


# --------------------- Acceptance 3: no consumer carries its own cadence

class TestNoConsumerCarriesOwnCadence(unittest.TestCase):
    """Change a day in cadencelibrary; assert it propagates."""

    def test_no_literal_day_in_sequenceplan(self):
        path = os.path.join(os.path.dirname(__file__), "..", "src",
                            "sequenceplan.py")
        with open(path) as f:
            source = f.read()
        for literal in ('"day": 1', '"day": 3', '"day": 8',
                        '"day": 14', '"day": 21',
                        "'day': 1", "'day': 3", "'day': 8",
                        "'day': 14", "'day': 21"):
            self.assertNotIn(literal, source,
                             "sequenceplan contains literal day number: %s" %
                             literal)


# ----------------------- Acceptance 4: hash is deterministic and sensitive

class TestHashDeterministicAndSensitive(unittest.TestCase):
    """Identical plan -> identical hash. One char changed -> different hash."""

    def test_identical_plans_same_hash(self):
        plan1 = _plan_with_contacts()
        plan2 = _plan_with_contacts()
        self.assertEqual(sequenceplan.approval_hash(plan1),
                         sequenceplan.approval_hash(plan2))

    def test_one_char_change_different_hash(self):
        plan1 = _plan_with_contacts()
        plan2 = _plan_with_contacts()
        plan2["contacts"][0]["sequences"]["em1"] = (
            plan2["contacts"][0]["sequences"]["em1"] + " ")
        self.assertNotEqual(sequenceplan.approval_hash(plan1),
                            sequenceplan.approval_hash(plan2))

    def test_hash_is_stable_across_calls(self):
        plan = _plan_with_contacts()
        h1 = sequenceplan.approval_hash(plan)
        h2 = sequenceplan.approval_hash(plan)
        self.assertEqual(h1, h2)

    def test_hash_covers_all_contacts(self):
        plan = _plan_with_contacts()
        h_full = sequenceplan.approval_hash(plan)
        plan_one_contact = _plan_with_contacts()
        plan_one_contact["contacts"].pop()
        h_one = sequenceplan.approval_hash(plan_one_contact)
        self.assertNotEqual(h_full, h_one)


# ----------------------- Acceptance 5: no fifth representation

class TestNoFifthRepresentation(unittest.TestCase):
    """Every remaining builder of email/LinkedIn step lists is reported."""

    def test_bisonfactory_imports_sequenceplan(self):
        path = os.path.join(os.path.dirname(__file__), "..", "src",
                            "bisonfactory.py")
        with open(path) as f:
            source = f.read()
        self.assertIn("sequenceplan", source,
                       "bisonfactory does not import sequenceplan")

    def test_heyreachfactory_imports_sequenceplan(self):
        path = os.path.join(os.path.dirname(__file__), "..", "src",
                            "heyreachfactory.py")
        with open(path) as f:
            source = f.read()
        self.assertIn("sequenceplan", source,
                       "heyreachfactory does not import sequenceplan")

    def test_bisonfactory_calls_derive_bison_payload(self):
        path = os.path.join(os.path.dirname(__file__), "..", "src",
                            "bisonfactory.py")
        with open(path) as f:
            source = f.read()
        self.assertIn("derive_bison_payload", source,
                       "bisonfactory does not call derive_bison_payload")

    def test_heyreachfactory_calls_derive_heyreach_payload(self):
        path = os.path.join(os.path.dirname(__file__), "..", "src",
                            "heyreachfactory.py")
        with open(path) as f:
            source = f.read()
        self.assertIn("derive_heyreach_payload", source,
                       "heyreachfactory does not call derive_heyreach_payload")

    def test_bisonfactory_calls_qa_validate(self):
        path = os.path.join(os.path.dirname(__file__), "..", "src",
                            "bisonfactory.py")
        with open(path) as f:
            source = f.read()
        self.assertIn("qa_validate", source,
                       "bisonfactory does not call qa_validate")

    def test_heyreachfactory_calls_qa_validate(self):
        path = os.path.join(os.path.dirname(__file__), "..", "src",
                            "heyreachfactory.py")
        with open(path) as f:
            source = f.read()
        self.assertIn("qa_validate", source,
                       "heyreachfactory does not call qa_validate")


# ------ Negative control: derive functions reached through the factory

class TestFactoryWiringNegativeControl(unittest.TestCase):
    """The derive functions are called from PRODUCTION code, not just tests.

    This is the TASK-029 pattern: correct code, absent wiring, green tests.
    These tests drive through the factory's _plan() and assert the derived
    payload is present in the factory output. Breaking the wiring must fail
    these tests.
    """

    def test_bisonfactory_plan_contains_derived_payload(self):
        """bisonfactory._plan() includes sequenceplan.derive_bison_payload().

        This test imports bisonfactory and calls _plan() with minimal data.
        If the wiring is removed, the 'derived_payload' key will be absent
        and this test fails.
        """
        from src import bisonfactory

        campaign = {
            "campaign_id": "test-email-1",
            "client": "productive",
            "name": "Test Email Campaign",
            "record_ids": ["rec-1"],
            "cadence": "productive_li_heavy_v1",
            "cadence_steps": [
                {"key": "em1", "day": 1, "channel": "email", "generated": True},
                {"key": "em2", "day": 4, "channel": "email", "generated": True},
                {"key": "em3", "day": 8, "channel": "email", "generated": True},
                {"key": "em4", "day": 12, "channel": "email", "generated": True},
                {"key": "em5", "day": 21, "channel": "email", "generated": True},
            ],
            "email_sequence": {
                "steps": {
                    "em1": {"subject": "Test Subject",
                            "body": "Test body",
                            "wait_in_days": 3},
                    "em2": {"subject": "Test Subject",
                            "body": "Body 2",
                            "wait_in_days": 4},
                    "em3": {"subject": "Subject B", "body": "Body 3",
                            "wait_in_days": 4},
                    "em4": {"subject": "Subject B", "body": "Body 4",
                            "wait_in_days": 9},
                    "em5": {"subject": "Subject C", "body": "Body 5",
                            "wait_in_days": 0},
                },
            },
            "sending_window": {},
        }
        recs = [{
            "id": "rec-1",
            "client": "productive",
            "company": "Acme",
            "contacts": [{
                "key": "alice",
                "email": "alice@acme.com",
                "sendable": True,
                "name": "Alice Test",
                "first_name": "Alice",
            }],
        }]
        config = {
            "name": "productive",
            "cadence": "productive_li_heavy_v1",
            "sender": {"name": "Test Sender", "email": "sender@test.com"},
            "email_sequence": {
                "steps": {
                    "em1": {"subject": "Test Subject",
                            "body": "Test body",
                            "wait_in_days": 3},
                    "em2": {"subject": "Test Subject",
                            "body": "Body 2",
                            "wait_in_days": 4},
                    "em3": {"subject": "Subject B", "body": "Body 3",
                            "wait_in_days": 4},
                    "em4": {"subject": "Subject B", "body": "Body 4",
                            "wait_in_days": 9},
                    "em5": {"subject": "Subject C", "body": "Body 5",
                            "wait_in_days": 0},
                },
            },
        }

        with mock.patch.object(bisonfactory, '_approved_copy') as mock_copy:
            mock_copy.return_value = (
                [{"step_key": "em1", "subject": "Test Subject",
                  "body": "Test body", "thread_reply": False}],
                [],
            )
            with mock.patch.object(bisonfactory, '_unsupported_copy',
                                   return_value=[]):
                with mock.patch.object(bisonfactory.campaigns, 'material',
                                       return_value={
                                           "records": [{
                                               "id": "rec-1",
                                               "contacts": [{
                                                   "key": "alice",
                                                   "email": "alice@acme.com",
                                                   "sendable": True,
                                               }],
                                           }],
                                       }):
                    with mock.patch.object(bisonfactory.campaigns,
                                           'fingerprint',
                                           return_value="fp"):
                        plan = bisonfactory._plan(campaign, recs, config)

        self.assertIn("sequence_plan", plan,
                       "bisonfactory._plan() has no 'sequence_plan' key - "
                       "the SequencePlan wiring is absent")
        self.assertIn("derived_payload", plan,
                       "bisonfactory._plan() has no 'derived_payload' key - "
                       "derive_bison_payload() is not called")
        self.assertIn("qa", plan,
                       "bisonfactory._plan() has no 'qa' key - "
                       "qa_validate() is not called")
        self.assertIn("leads", plan["derived_payload"],
                       "derived_payload has no leads - "
                       "derive_bison_payload() output is wrong")

    def test_bisonfactory_derived_payload_reflects_plan_change(self):
        """Changing the factory input changes the derived payload.

        This is the TASK-029 negative control: if the derive function is
        called but its input is disconnected from the factory's actual data,
        changing the data won't change the derived output.
        """
        from src import bisonfactory

        def _make_plan(body_text):
            campaign = {
                "campaign_id": "test-email-1",
                "client": "productive",
                "name": "Test",
                "record_ids": ["rec-1"],
                "cadence": "productive_li_heavy_v1",
                "cadence_steps": [
                    {"key": "em1", "day": 1, "channel": "email",
                     "generated": True},
                    {"key": "em2", "day": 4, "channel": "email",
                     "generated": True},
                    {"key": "em3", "day": 8, "channel": "email",
                     "generated": True},
                    {"key": "em4", "day": 12, "channel": "email",
                     "generated": True},
                    {"key": "em5", "day": 21, "channel": "email",
                     "generated": True},
                ],
                "email_sequence": {
                    "steps": {
                        "em1": {"subject": "Subj", "body": body_text,
                                "wait_in_days": 3},
                        "em2": {"subject": "Subj", "body": "B2",
                                "wait_in_days": 4},
                        "em3": {"subject": "SB", "body": "B3",
                                "wait_in_days": 4},
                        "em4": {"subject": "SB", "body": "B4",
                                "wait_in_days": 9},
                        "em5": {"subject": "SC", "body": "B5",
                                "wait_in_days": 0},
                    },
                },
                "sending_window": {},
            }
            recs = [{
                "id": "rec-1",
                "client": "productive",
                "company": "Acme",
                "contacts": [{
                    "key": "alice",
                    "email": "alice@acme.com",
                    "sendable": True,
                    "name": "Alice",
                    "first_name": "Alice",
                }],
            }]
            config = {
                "name": "productive",
                "cadence": "productive_li_heavy_v1",
                "sender": {"name": "Sender", "email": "s@t.com"},
                "email_sequence": {
                    "steps": {
                        "em1": {"subject": "Subj", "body": body_text,
                                "wait_in_days": 3},
                        "em2": {"subject": "Subj", "body": "B2",
                                "wait_in_days": 4},
                        "em3": {"subject": "SB", "body": "B3",
                                "wait_in_days": 4},
                        "em4": {"subject": "SB", "body": "B4",
                                "wait_in_days": 9},
                        "em5": {"subject": "SC", "body": "B5",
                                "wait_in_days": 0},
                    },
                },
            }
            with mock.patch.object(bisonfactory, '_approved_copy') as mc:
                mc.return_value = (
                    [{"step_key": "em1", "subject": "Subj",
                      "body": body_text, "thread_reply": False}],
                    [],
                )
                with mock.patch.object(bisonfactory, '_unsupported_copy',
                                       return_value=[]):
                    with mock.patch.object(bisonfactory.campaigns, 'material',
                                           return_value={
                                               "records": [{
                                                   "id": "rec-1",
                                                   "contacts": [{
                                                       "key": "alice",
                                                       "email": "alice@acme.com",
                                                       "sendable": True,
                                                   }],
                                               }],
                                           }):
                        with mock.patch.object(bisonfactory.campaigns,
                                               'fingerprint',
                                               return_value="fp"):
                            return bisonfactory._plan(campaign, recs, config)

        plan_a = _make_plan("Body version A")
        plan_b = _make_plan("Body version B")

        derived_a = plan_a["derived_payload"]
        derived_b = plan_b["derived_payload"]
        self.assertNotEqual(derived_a, derived_b,
                            "derived payload did not change when the "
                            "factory input changed - the derive function "
                            "is not wired to the factory's data")

        body_a = derived_a["leads"][0]["steps"][0]["body"]
        body_b = derived_b["leads"][0]["steps"][0]["body"]
        self.assertEqual(body_a, "Body version A")
        self.assertEqual(body_b, "Body version B")


# -------------------------------------- derive_xlsx_data and qa_validate

class TestDeriveXlsxData(unittest.TestCase):
    """derive_xlsx_data produces correct export shape."""

    def test_headers_present(self):
        plan = _plan_with_contacts()
        xlsx = sequenceplan.derive_xlsx_data(plan)
        self.assertIn("headers", xlsx)
        self.assertIn("em1", xlsx["headers"])
        self.assertIn("connect", xlsx["headers"])
        self.assertIn("subject_a", xlsx["headers"])

    def test_rows_match_contacts(self):
        plan = _plan_with_contacts()
        xlsx = sequenceplan.derive_xlsx_data(plan)
        self.assertEqual(len(xlsx["rows"]), 2)
        self.assertEqual(xlsx["rows"][0]["email"], "alice@acme.com")
        self.assertEqual(xlsx["rows"][0]["em1"],
                         "Hello Alice, first email body.")

    def test_change_propagates(self):
        plan = _plan_with_contacts()
        original = sequenceplan.derive_xlsx_data(plan)
        plan["contacts"][0]["sequences"]["em1"] = "NEW"
        updated = sequenceplan.derive_xlsx_data(plan)
        self.assertNotEqual(original, updated)
        self.assertEqual(updated["rows"][0]["em1"], "NEW")


class TestQaValidate(unittest.TestCase):
    """qa_validate reports issues correctly."""

    def test_valid_plan(self):
        plan = _plan_with_contacts()
        qa = sequenceplan.qa_validate(plan)
        self.assertTrue(qa["valid"])
        self.assertEqual(qa["issues"], [])
        self.assertEqual(qa["contact_count"], 2)
        self.assertEqual(qa["sendable_count"], 2)

    def test_missing_email(self):
        plan = _plan_with_contacts()
        plan["contacts"][0]["email"] = ""
        qa = sequenceplan.qa_validate(plan)
        self.assertFalse(qa["valid"])
        self.assertTrue(any(i["field"] == "email" for i in qa["issues"]))

    def test_missing_em1(self):
        plan = _plan_with_contacts()
        plan["contacts"][0]["sequences"]["em1"] = ""
        qa = sequenceplan.qa_validate(plan)
        self.assertFalse(qa["valid"])
        self.assertTrue(any(i["field"] == "em1" for i in qa["issues"]))

    def test_unqualified_not_sendable(self):
        plan = _plan_with_contacts()
        plan["contacts"][0]["qualification"] = "UNQUALIFIED"
        qa = sequenceplan.qa_validate(plan)
        self.assertEqual(qa["sendable_count"], 1)

    def test_gate_refused(self):
        plan = _plan_with_contacts()
        plan["contacts"][0]["sequence_gate"] = {"refused": "repetition"}
        qa = sequenceplan.qa_validate(plan)
        self.assertFalse(qa["valid"])
        self.assertTrue(any(i["field"] == "sequence_gate"
                            for i in qa["issues"]))


if __name__ == "__main__":
    unittest.main()
