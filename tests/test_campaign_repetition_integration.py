"""Integration test: campaign build refuses semantic duplicates.

TASK-043 / TASK-049. The campaign build path (`heyreachfactory._plan`)
must refuse a sequence whose steps rephrase one another within the same
execution path. This test verifies the integration between
`quality.campaign_repetition` and the campaign builder.

THE TEST IS BEHAVIOURAL, NOT SOURCE TEXT. It constructs a record whose
per-lead copy has genuine repetition within one execution path and
verifies that `_plan` refuses. If the call to `campaign_repetition` is
removed from `_plan`, this test fails because the plan succeeds when it
should refuse.
"""
import unittest

from src import heyreachfactory
from tests.test_heyreachfactory import _full_record
from tests.test_the_sequence_belongs_to_nobody import (
    campaign_row, config_with_fallbacks)


def _plan(recs, config=None):
    return heyreachfactory._plan(
        campaign_row([r["id"] for r in recs]), recs,
        config or config_with_fallbacks())


def _record_with_repetition_on_cold_path():
    """A record where message_2 and message_3 are paraphrases.

    message_2 and message_3 are both on the cold execution path
    (the branch a prospect walks when not yet connected). If the
    repetition check is wired, _plan refuses. If the check is
    removed, _plan succeeds - and the test fails.
    """
    rec = _full_record("pat")
    # li2 fills message_2 (cold path) and connected_1 (already-connected).
    # li3 fills message_3 (cold path) and connected_2 (already-connected).
    # Making li2 and li3 paraphrases puts repetition on BOTH paths.
    rec["cadence"]["pat"]["li2"]["note"] = (
        "how do you currently ensure visibility across your "
        "delivery projects and teams?")
    rec["cadence"]["pat"]["li3"]["note"] = (
        "how do you currently ensure visibility into your "
        "delivery projects today?")
    return rec


class TestCampaignBuildRefusesSemanticDuplicates(unittest.TestCase):
    """The campaign build path refuses semantic duplicates within
    each execution path."""

    def test_plan_refuses_repetition_on_its_path(self):
        """_plan refuses when per-lead copy repeats within one path.

        This is the behavioural proof: the real entry point (_plan)
        calls campaign_repetition and refuses on its output. If the
        call is deleted, _plan succeeds and this test fails.
        """
        rec = _record_with_repetition_on_cold_path()
        with self.assertRaises(heyreachfactory.FactoryRefused) as caught:
            _plan([rec])
        self.assertIn("repeats", str(caught.exception))

    def test_plan_succeeds_with_progressive_copy(self):
        """_plan succeeds when each path is genuinely progressive.

        The default fixture (_full_record) has progressive copy within
        each execution path. This test verifies the check does not
        refuse good copy.
        """
        rec = _full_record("pat")
        built = _plan([rec])
        self.assertIn("sequence", built)
        self.assertTrue(built["pushable"])

    def test_the_refusal_names_the_colliding_roles(self):
        """The refusal message names the roles that collided, not the
        step keys. Roles are the unique per-text identifiers; step keys
        are shared when one step fills two roles."""
        rec = _record_with_repetition_on_cold_path()
        with self.assertRaises(heyreachfactory.FactoryRefused) as caught:
            _plan([rec])
        msg = str(caught.exception)
        # The collision is between roles on the same path.
        # li2 fills connected_1 AND message_2; li3 fills connected_2
        # AND message_3. Both paths have the collision; whichever is
        # checked first fires. Accept either naming.
        role_names = {"connected_1", "connected_2", "message_2", "message_3"}
        named = [r for r in role_names if r in msg]
        self.assertTrue(
            len(named) >= 2,
            f"refusal should name colliding roles, got: {msg}")


class TestEveryContactIsChecked(unittest.TestCase):
    """The check read `complete[0]` and called the rest safe by assumption.

    Its justification: "all contacts share the same sequence structure, so if
    one contact's copy is progressive, every contact's is". MEASURED on the
    real Productive cohort 2026-09-14 and false - 2 of the 10 pushable
    contacts carried copy that repeats itself and NEITHER was the first.
    `ranjan-damodar` had seven collisions and the plan was accepted because
    `jacob-faertz` sorted ahead of him.

    Structure is shared between contacts. Words are not: copy is generated per
    contact against that contact's own evidence, in three attempts that can
    each fail differently, and it is the words that repeat.

    It is also the exact defect `4f93f2f` was written about - one contact
    deciding what a whole campaign does - reappearing inside the checker meant
    to prevent it.
    """

    def test_a_later_contact_cannot_hide_behind_a_clean_first_one(self):
        clean = _full_record("pat")
        repeats = _record_with_repetition_on_cold_path()
        repeats["id"] = "second-co"
        repeats["domain"] = "second.test"
        with self.assertRaises(heyreachfactory.FactoryRefused) as caught:
            _plan([clean, repeats])
        self.assertIn("repeats", str(caught.exception))

    def test_the_refusal_names_which_contact(self):
        """"the sequence repeats itself" with ten contacts in the plan sends
        a reader to the wrong one. The message names the record and the
        contact whose copy actually collided."""
        clean = _full_record("pat")
        repeats = _record_with_repetition_on_cold_path()
        repeats["id"] = "second-co"
        repeats["domain"] = "second.test"
        with self.assertRaises(heyreachfactory.FactoryRefused) as caught:
            _plan([clean, repeats])
        self.assertIn("second-co", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
