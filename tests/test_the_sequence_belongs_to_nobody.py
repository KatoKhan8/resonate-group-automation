#!/usr/bin/env python3
"""A HeyReach sequence is campaign-level, so it may say nothing about one lead.

THE INCIDENT THIS PINS, and it was caught one call before it happened.

`heyreachfactory._plan` built the campaign graph like this:

    complete = [c for c in per_contact if not c["missing"]]
    copy_block = complete[0]["copy"]          # the FIRST eligible contact
    sequence, touch_report = build_sequence(copy_block, ...)

One contact's approved, personalised words became the whole campaign's copy,
as literal strings with no merge fields. Read back from HeyReach campaign
599020 on 2026-09-14, whose canonical row names FOURTEEN records:

    CONNECTION_REQUEST  "hi jacob, as a founder, you know the importance of
                         having profitability visible on monday. let's connect!"
    MESSAGE             "...how are you currently managing this at &Partner?"

`jacob` is `ogpartner-dk`/`jacob-faertz`, who sorted first. Enabling
`LINKEDIN_ADD_LEAD` would have sent thirteen people at thirteen other
companies a connection note addressing them as Jacob.

WHY `_plan` HAD NO TESTS AND THAT IS THE POINT. `tests/test_heyreachfactory.py`
covers the mapping, the refusals, the graph shape and the write door - 36 tests
- and calls neither `_plan` nor `stage`. Every piece was correct and the
function that assembled them was never asked what it produced. That is the
defect shape CLAUDE.md names: a thing computed correctly that nothing
downstream checks.

So these tests assert on what `_plan` RETURNS, and the central one is negative:
no contact's own sentence may appear anywhere in the graph.
"""
import json
import unittest

from src import heyreachfactory
from tests.test_heyreachfactory import _full_record, _record_missing_step


def config_with_fallbacks(**overrides):
    """A client config carrying a fallback for every required role."""
    fallbacks = {role: f"fallback for {role}"
                 for role in heyreachfactory.REQUIRED_ROLES}
    fallbacks.update(overrides)
    return {"name": "Test", "linkedin_sequence": {"fallbacks": fallbacks}}


def campaign_row(record_ids):
    return {"campaign_id": "c1", "client": "productive",
            "name": "test", "record_ids": list(record_ids),
            "heyreach_campaign_id": "599020"}


def plan(recs, config=None):
    return heyreachfactory._plan(
        campaign_row([r["id"] for r in recs]), recs,
        config or config_with_fallbacks())


class TheGraphCarriesNobodysWords(unittest.TestCase):

    def test_no_contacts_sentence_appears_in_the_sequence(self):
        """THE REGRESSION. This is the whole incident in one assertion."""
        rec = _full_record("brooke")
        built = plan([rec])
        blob = json.dumps(built["sequence"])
        for step_key, step in rec["cadence"]["brooke"].items():
            note = (step.get("note") or "").strip()
            if not note:
                continue
            with self.subTest(step=step_key):
                self.assertNotIn(
                    note, blob,
                    f"{step_key}'s approved words are baked into the "
                    f"campaign-level graph; every other lead would receive "
                    f"copy written for this one")

    def test_the_sequence_carries_a_variable_for_every_required_role(self):
        built = plan([_full_record()])
        blob = json.dumps(built["sequence"])
        for role in heyreachfactory.REQUIRED_ROLES:
            with self.subTest(role=role):
                self.assertIn("{" + role + "}", blob)

    def test_two_contacts_share_one_graph_and_keep_their_own_words(self):
        """The property that makes a campaign-level sequence safe at all."""
        first = _full_record("brooke")
        second = _full_record("carla")
        second["id"] = "beta"
        second["cadence"]["carla"]["li1"]["note"] = "Hi Carla, quite different."

        built = plan([first, second])
        fields = {c["contact_key"]: c["custom_fields"]
                  for c in built["contacts"]}
        self.assertEqual(set(fields), {"brooke", "carla"})
        self.assertNotEqual(fields["brooke"]["connection_note"],
                            fields["carla"]["connection_note"])
        self.assertEqual(fields["carla"]["connection_note"],
                         "Hi Carla, quite different.")
        # And exactly one graph, mentioning neither of them.
        blob = json.dumps(built["sequence"])
        self.assertNotIn("Carla", blob)
        self.assertNotIn("Brooke", blob)

    def test_the_graph_does_not_change_when_the_first_contact_changes(self):
        """`complete[0]` was the bug. Reordering must be a no-op now."""
        first = _full_record("brooke")
        second = _full_record("carla")
        second["id"] = "beta"
        second["cadence"]["carla"]["li1"]["note"] = "Totally different words."
        forwards = plan([first, second])["sequence"]
        backwards = plan([second, first])["sequence"]
        self.assertEqual(json.dumps(forwards), json.dumps(backwards))


class AnIncompleteContactDoesNotDecideWhatTheCampaignSays(unittest.TestCase):

    def test_an_incomplete_contact_is_reported_and_not_pushable(self):
        good = _full_record("brooke")
        bad = _record_missing_step("li3", "carla")
        bad["id"] = "beta"
        built = plan([good, bad])
        pushable = {c["contact_key"] for c in built["pushable"]}
        self.assertEqual(pushable, {"brooke"})
        self.assertTrue(any(m[0] == "carla" for m in built["missing"]))

    def test_the_sequence_is_unaffected_by_an_incomplete_contact(self):
        """Before this change an incomplete contact could not be tolerated at
        all: the graph came from a contact, so a missing step was a campaign
        problem. Now it is only that lead's problem."""
        good = _full_record("brooke")
        bad = _record_missing_step("li3", "carla")
        bad["id"] = "beta"
        alone = plan([good])["sequence"]
        together = plan([good, bad])["sequence"]
        self.assertEqual(json.dumps(alone), json.dumps(together))


class TheFallbackIsTheClientsAndNotThisModules(unittest.TestCase):

    def test_a_missing_fallback_refuses_and_names_the_role(self):
        config = config_with_fallbacks()
        del config["linkedin_sequence"]["fallbacks"]["connected_4"]
        with self.assertRaises(heyreachfactory.FactoryRefused) as caught:
            plan([_full_record()], config)
        self.assertIn("connected_4", str(caught.exception))

    def test_no_fallbacks_at_all_refuses(self):
        with self.assertRaises(heyreachfactory.FactoryRefused):
            plan([_full_record()], {"name": "Test"})

    def test_the_fallback_reaches_the_graph(self):
        """It has to be IN the graph, not merely configured - HeyReach reads
        `fallbackMessage` off the node when a variable will not fill."""
        built = plan([_full_record()])
        blob = json.dumps(built["sequence"])
        for role in heyreachfactory.REQUIRED_ROLES:
            with self.subTest(role=role):
                self.assertIn(f"fallback for {role}", blob)


class InMailIsRefusedRatherThanHalfWired(unittest.TestCase):

    def test_include_inmail_refuses_and_says_why(self):
        """An INMAIL carries a subject AND a message, so it needs two
        variables per lead. Neither is wired and no InMail copy is ever
        approved, so this refuses rather than sending one of the two."""
        with self.assertRaises(heyreachfactory.FactoryRefused) as caught:
            heyreachfactory._plan(
                campaign_row(["acme"]), [_full_record()],
                config_with_fallbacks(), include_inmail=True)
        self.assertIn("InMail", str(caught.exception))

    def test_the_plan_reports_inmail_as_absent(self):
        self.assertFalse(plan([_full_record()])["inmail_included"])


if __name__ == "__main__":
    unittest.main()
