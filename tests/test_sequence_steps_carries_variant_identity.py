"""TASK-073: sequence_steps() preserves variant, variant_from_step, thread_reply.

EmailBison models a message variant as a first-class sequence step. Campaign
352 has 44 sequence steps, 39 carry variant=True, each carries
variant_from_step naming its parent, and all 44 ids are distinct.

`bison.sequence_steps()` was trimming `variant`, `variant_from_step` and
`thread_reply` out of the row before anything downstream could see them.
This is the repository's recurring defect: a thing computed correctly by the
provider that nothing downstream can read.

Every assertion here is on what `sequence_steps()` RETURNS, not on the text
of the source.
"""
import os
import unittest

from src import providers
from src.providers import bison
from tests.base import ProviderTest
from tests.fakebison import FakeBison


class SequenceStepsCarriesVariantIdentity(ProviderTest):
    """The three fields the trimmer discarded are now in the return value."""

    def setUp(self):
        super().setUp()
        os.environ["BISON_BASE"] = "https://emailbison.invalid/api"
        self.fake = FakeBison()
        self.providers.set_transport(self.fake)

    def _inject_steps(self, steps):
        """Create a campaign in the fake and put steps directly into its
        sequence store, bypassing POST.

        The POST handler constructs its own ids and order, which is correct
        for testing writes. Testing reads against campaign 352's real shape
        needs the raw rows the provider would return, with variants carrying
        order=None and variant_from_step set.

        Returns the campaign id the fake assigned.
        """
        cid = self.fake.add_campaign("test-campaign")
        self.fake.sequences[cid] = list(steps)
        return cid

    def test_sequence_steps_returns_variant_fields(self):
        """A step with variant=True, variant_from_step and thread_reply set
        returns all three through sequence_steps()."""
        cid = self._inject_steps([
            {"id": 4035, "order": 1, "active": True,
             "email_subject": "First", "email_body": "<p>Body</p>",
             "wait_in_days": 3,
             "variant": False, "variant_from_step": None,
             "thread_reply": None},
            {"id": 4036, "order": None, "active": True,
             "email_subject": "First (variant A)", "email_body": "<p>Alt</p>",
             "wait_in_days": 3,
             "variant": True, "variant_from_step": 4035,
             "thread_reply": True},
        ])
        result = bison.sequence_steps(cid)
        self.assertEqual(len(result), 2)

        base = result[0]
        self.assertEqual(base["id"], 4035)
        self.assertEqual(base["order"], 1)
        self.assertFalse(base["variant"])
        self.assertIsNone(base["variant_from_step"])
        self.assertIsNone(base["thread_reply"])

        variant = result[1]
        self.assertEqual(variant["id"], 4036)
        self.assertIsNone(variant["order"])
        self.assertTrue(variant["variant"])
        self.assertEqual(variant["variant_from_step"], 4035)
        self.assertTrue(variant["thread_reply"])

    def test_variant_is_distinguishable_from_parent(self):
        """A variant step and its parent are distinguishable by the tuple of
        id, variant flag and variant_from_step - what the function RETURNS."""
        cid = self._inject_steps([
            {"id": 4037, "order": 2, "active": True,
             "email_subject": "Second", "email_body": "<p>Body2</p>",
             "wait_in_days": 3,
             "variant": False, "variant_from_step": None,
             "thread_reply": None},
            {"id": 4038, "order": None, "active": True,
             "email_subject": "Second (variant A)",
             "email_body": "<p>Alt2a</p>",
             "wait_in_days": 3,
             "variant": True, "variant_from_step": 4037,
             "thread_reply": False},
            {"id": 4039, "order": None, "active": True,
             "email_subject": "Second (variant B)",
             "email_body": "<p>Alt2b</p>",
             "wait_in_days": 3,
             "variant": True, "variant_from_step": 4037,
             "thread_reply": True},
        ])
        result = bison.sequence_steps(cid)
        self.assertEqual(len(result), 3)

        identities = [(s["id"], s["variant"], s["variant_from_step"])
                      for s in result]
        self.assertEqual(len(set(identities)), 3,
                         "every step must have a distinct identity tuple")

        base = [s for s in result if not s["variant"]]
        variants = [s for s in result if s["variant"]]
        self.assertEqual(len(base), 1)
        self.assertEqual(len(variants), 2)
        for v in variants:
            self.assertEqual(v["variant_from_step"], base[0]["id"])

    def test_campaign_352_shape_five_base_five_variants_each(self):
        """Campaign 352's real shape, PII removed: five base steps with
        order set, and variants with order=None and variant_from_step naming
        their parent. All ids distinct."""
        cid = self._inject_steps([
            {"id": 4035, "order": 1, "active": True,
             "email_subject": "S1", "email_body": "B1", "wait_in_days": 3,
             "variant": False, "variant_from_step": None,
             "thread_reply": None},
            {"id": 4036, "order": None, "active": True,
             "email_subject": "S1a", "email_body": "B1a", "wait_in_days": 3,
             "variant": True, "variant_from_step": 4035,
             "thread_reply": None},
            {"id": 4037, "order": 2, "active": True,
             "email_subject": "S2", "email_body": "B2", "wait_in_days": 3,
             "variant": False, "variant_from_step": None,
             "thread_reply": None},
            {"id": 4038, "order": None, "active": True,
             "email_subject": "S2a", "email_body": "B2a", "wait_in_days": 3,
             "variant": True, "variant_from_step": 4037,
             "thread_reply": True},
            {"id": 4039, "order": None, "active": True,
             "email_subject": "S2b", "email_body": "B2b", "wait_in_days": 3,
             "variant": True, "variant_from_step": 4037,
             "thread_reply": False},
        ])
        result = bison.sequence_steps(cid)

        all_ids = [s["id"] for s in result]
        self.assertEqual(len(all_ids), len(set(all_ids)),
                         "all step ids must be distinct")

        base = [s for s in result if not s["variant"]]
        variants = [s for s in result if s["variant"]]
        self.assertEqual(len(base), 2)
        self.assertEqual(len(variants), 3)

        for b in base:
            self.assertIsNotNone(b["order"])
            self.assertIsNone(b["variant_from_step"])
        for v in variants:
            self.assertIsNone(v["order"])
            self.assertIsNotNone(v["variant_from_step"])

    def test_fields_are_none_when_provider_omits_them(self):
        """A step from a campaign with no variants still returns the three
        fields, valued None - the key is present, the value is absent."""
        cid = self._inject_steps([
            {"id": 5001, "order": 1, "active": True,
             "email_subject": "Only", "email_body": "<p>One</p>",
             "wait_in_days": 3},
        ])
        result = bison.sequence_steps(cid)
        self.assertEqual(len(result), 1)
        step = result[0]
        self.assertIn("variant", step)
        self.assertIn("variant_from_step", step)
        self.assertIn("thread_reply", step)
        self.assertIsNone(step["variant"])
        self.assertIsNone(step["variant_from_step"])
        self.assertIsNone(step["thread_reply"])


if __name__ == "__main__":
    unittest.main()
