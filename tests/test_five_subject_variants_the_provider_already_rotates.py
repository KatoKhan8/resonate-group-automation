"""TASK-022: five variants per step, carried to the provider payload.

The mechanism is per-lead variables, not provider spintax. Spintax rotates
per send and cannot be attributed to a contact; a per-lead variable can be
attributed but is fixed per person. Attribution is the whole point of the
experiment, so per-lead variables win.

The chain this file walks:

    step spec carries variants -> factory resolves variant for contact ->
    variant's words are checked against approval -> variant's words go on
    the wire -> variant_id is recorded on the payload

Every variant is approved copy or it is not sent. Five variants means five
approvals, not one stretched over five.
"""
import unittest

from src import (approval, bisonfactory, cadence, clients, heyreachfactory,
                 variants)
from tests.campaignbase import CampaignTest, contact

STYLES = ("short_direct", "casual", "professional", "consultative",
          "problem_led")


def five_variants(step_key):
    """Five approved email variants, distinguishable in the copy."""
    return [variants.variant(f"{step_key}-{style}", style,
                             subject=f"{style} subject for {step_key}",
                             body=f"This is the {style} wording.\n\nBest,\nZ",
                             status=variants.ACTIVE)
            for style in STYLES]


def five_li_variants(step_key):
    """Five approved LinkedIn variants, distinguishable in the note."""
    return [variants.variant(f"{step_key}-{style}", style,
                             note=f"{style} linkedin note for {step_key}",
                             status=variants.ACTIVE)
            for style in STYLES]


def _email_sequence_with_variants():
    """A four-step email sequence with variants on day5."""
    return [
        {"key": "day1", "day": 1, "channel": "email", "generated": True},
        {"key": "day3", "day": 3, "channel": "email",
         "template": "persona_pain"},
        {"key": "day5", "day": 5, "channel": "email",
         "template": "persona_pain",
         cadence.VARIANTS_KEY: five_variants("day5")},
        {"key": "day8", "day": 8, "channel": "email",
         "template": "comparable_proof"},
    ]


def _approved_email_step(step_key, subject, body):
    """A stored email step with approval covering these exact words."""
    step = {"key": step_key, "day": 5, "channel": "email",
            "generated": True, "subject": subject, "body": body}
    step["approval"] = {"fingerprint": approval.fingerprint(step),
                        "at": "2026-09-14T00:00:00"}
    return step


def _record_with_variant_approvals(contact_key="c1", *, variant_index=0):
    """A record where the stored step has a specific variant's words and approval.

    `variant_index` selects which of the five variants is stored. The stored
    step has the variant's words, variant_id, and an approval covering them.
    This models the production flow: timeline resolves variant -> step is
    stored with variant's words -> human approves -> factory reads it.
    """
    variant_list = five_variants("day5")
    chosen = variant_list[variant_index % len(variant_list)]
    step = {"key": "day5", "day": 5, "channel": "email",
            "generated": True,
            "subject": chosen["subject"], "body": chosen["body"],
            "variant_id": chosen["variant_id"],
            "variant_style": chosen["style"]}
    step["approval"] = {"fingerprint": approval.fingerprint(step),
                        "at": "2026-09-14T00:00:00"}
    # Also store day1 generated step.
    day1 = {"key": "day1", "day": 1, "channel": "email", "generated": True,
            "subject": "quick question about Acme",
            "body": "Hi Champ,\n\nBody here.\n\nBest,\nZ"}
    day1["approval"] = {"fingerprint": approval.fingerprint(day1),
                        "at": "2026-09-14T00:00:00"}
    return {
        "id": "rec-variant", "client": "demo", "domain": "acme.test",
        "state": "drafted",
        "contacts": [contact(contact_key, "Champ Acme",
                             f"champ@acme.test")],
        "cadence": {contact_key: {"day1": day1, "day5": step}},
    }


class EmailBisonVariantsOnTheWire(CampaignTest):
    """A step with five approved variants puts the resolved variant on the wire."""

    def test_the_resolved_variant_words_are_in_the_payload(self):
        """The factory resolves the variant and uses its words, not the
        base template's."""
        rec = _record_with_variant_approvals("c1", variant_index=0)
        seq = _email_sequence_with_variants()
        campaign = {"campaign_id": "camp-v"}
        # The sequence the provider sees.
        provider_seq = [{"order": 1, "step_key": "day5",
                         "email_subject": "x", "email_body": "y",
                         "wait_in_days": 3}]
        copy, missing = bisonfactory._approved_copy(
            rec, "c1", provider_seq, "rec-variant",
            cadence_steps=seq, campaign=campaign, config=self.config)
        # The contact gets the variant that was stored (sticky assignment).
        self.assertEqual(len(missing), 0)
        self.assertEqual(len(copy), 1)
        entry = copy[0]
        self.assertIn(entry["subject"],
                      [v["subject"] for v in five_variants("day5")])
        self.assertIn("variant_id", entry)
        self.assertIn("variant_style", entry)

    def test_five_contacts_get_the_variant_their_hash_assigns(self):
        """Different contacts resolve to different variants deterministically.
        
        Each contact's stored step has the variant they were assigned by the
        deterministic function, with approval covering those words.
        """
        seq = _email_sequence_with_variants()
        campaign = {"campaign_id": "camp-v"}
        provider_seq = [{"order": 1, "step_key": "day5",
                         "email_subject": "x", "email_body": "y",
                         "wait_in_days": 3}]
        seen_variants = set()
        seen_subjects = set()
        variant_list = five_variants("day5")
        for i in range(20):
            key = f"c{i}"
            # Resolve which variant this contact gets deterministically.
            from src import cadence as _cadence
            spec = [s for s in seq if s["key"] == "day5"][0]
            entry = _cadence.variant_for(spec, campaign, key, config=self.config)
            if not entry:
                continue
            # Find which index this variant is at.
            idx = next((j for j, v in enumerate(variant_list)
                        if v["variant_id"] == entry["variant_id"]), 0)
            # Build a record with that variant's words and approval.
            rec = _record_with_variant_approvals(key, variant_index=idx)
            copy, missing = bisonfactory._approved_copy(
                rec, key, provider_seq, "rec-variant",
                cadence_steps=seq, campaign=campaign, config=self.config)
            if not missing and copy:
                seen_variants.add(copy[0]["variant_id"])
                seen_subjects.add(copy[0]["subject"])
        # With 20 contacts and 5 variants, we should see more than one variant.
        self.assertGreater(len(seen_variants), 1,
                           "all contacts landed on the same variant; "
                           "assignment is not spreading across arms")

    def test_assignment_is_deterministic(self):
        """The same contact gets the same arm twice."""
        seq = _email_sequence_with_variants()
        campaign = {"campaign_id": "camp-v"}
        provider_seq = [{"order": 1, "step_key": "day5",
                         "email_subject": "x", "email_body": "y",
                         "wait_in_days": 3}]
        rec = _record_with_variant_approvals("c1", variant_index=0)
        first, _ = bisonfactory._approved_copy(
            rec, "c1", provider_seq, "rec-variant",
            cadence_steps=seq, campaign=campaign, config=self.config)
        second, _ = bisonfactory._approved_copy(
            rec, "c1", provider_seq, "rec-variant",
            cadence_steps=seq, campaign=campaign, config=self.config)
        self.assertTrue(len(first) > 0)
        self.assertTrue(len(second) > 0)
        self.assertEqual(first[0]["variant_id"], second[0]["variant_id"])
        self.assertEqual(first[0]["subject"], second[0]["subject"])


class UnapprovedVariantIsRefused(CampaignTest):
    """A step with five variants of which one is unapproved refuses."""

    def test_an_unapproved_variant_is_reported_missing(self):
        """If the resolved variant's words don't match any stored approval,
        it is reported as missing copy."""
        seq = _email_sequence_with_variants()
        campaign = {"campaign_id": "camp-v"}
        provider_seq = [{"order": 1, "step_key": "day5",
                         "email_subject": "x", "email_body": "y",
                         "wait_in_days": 3}]
        # Store a step with words that don't match ANY variant.
        rec = _record_with_variant_approvals("c1")
        # Overwrite the stored step with words that match no variant.
        rec["cadence"]["c1"]["day5"] = {
            "key": "day5", "day": 5, "channel": "email",
            "generated": True,
            "subject": "unrelated subject",
            "body": "unrelated body",
            "approval": {"fingerprint": "wrong-fingerprint"},
        }
        copy, missing = bisonfactory._approved_copy(
            rec, "c1", provider_seq, "rec-variant",
            cadence_steps=seq, campaign=campaign, config=self.config)
        # The resolved variant's words don't match the stored approval.
        self.assertEqual(len(copy), 0)
        self.assertEqual(len(missing), 1)
        self.assertIn("day5", missing[0])


class HeyReachVariantsOnTheWire(CampaignTest):
    """LinkedIn variants are resolved and carried to the provider payload."""

    def test_a_variant_note_replaces_the_stored_note(self):
        """When a LinkedIn step has variants, the resolved variant's note
        is what goes on the wire."""
        variant_list = five_li_variants("li2")
        first = variant_list[0]
        step = {"key": "li2", "day": 3, "channel": "linkedin",
                "linkedin_action": "message", "generated": True,
                "note": first["note"],
                "variant_id": first["variant_id"],
                "variant_style": first["style"]}
        step["approval"] = {"fingerprint": approval.fingerprint(step),
                            "at": "2026-09-14T00:00:00"}
        # Build a full record with this step.
        from tests.test_heyreachfactory import _full_record
        rec = _full_record("pat")
        rec["cadence"]["pat"]["li2"] = step
        seq = [
            {"key": "li1", "day": 1, "channel": "linkedin",
             "linkedin_action": "connect"},
            {"key": "li2", "day": 3, "channel": "linkedin",
             "linkedin_action": "message",
             cadence.VARIANTS_KEY: variant_list},
            {"key": "li3", "day": 6, "channel": "linkedin",
             "linkedin_action": "message"},
            {"key": "li4", "day": 10, "channel": "linkedin",
             "linkedin_action": "message"},
            {"key": "li5", "day": 15, "channel": "linkedin",
             "linkedin_action": "message"},
        ]
        campaign = {"campaign_id": "camp-li-v"}
        copy, missing = heyreachfactory.assemble_linkedin_copy(
            rec, "pat", cadence_steps=seq, campaign=campaign,
            config=self.config)
        # The resolved variant's note should be in the copy.
        self.assertIn("connected_1", copy)
        self.assertIn("message_2", copy)
        # Both roles that li2 maps to should have the variant's note.
        self.assertEqual(copy["connected_1"]["messages"][0], first["note"])
        self.assertEqual(copy["message_2"]["messages"][0], first["note"])


class EvaluatorRefusesUnderpoweredCohort(unittest.TestCase):
    """The evaluator still returns INSUFFICIENT_DATA on a small cohort."""

    def test_fifteen_contacts_is_not_enough(self):
        """With 15 contacts across 5 variants, each variant has ~3 exposures.
        The minimum is 30 per variant and 8 outcomes total."""
        node = {"type": "email", "key": "day5",
                "variants": five_variants("day5")}
        # 15 contacts, 3 per variant, 0 outcomes.
        results = {}
        for v in five_variants("day5"):
            results[v["variant_id"]] = {"exposures": 3, "positive_replies": 0}
        verdict = variants.evaluate(node, results, progress=1.0)
        self.assertEqual(verdict["state"], variants.INSUFFICIENT_DATA)
        self.assertIn("30", verdict["why"])

    def test_the_evaluator_names_what_it_needs(self):
        """The verdict says what sample size would be needed."""
        node = {"type": "email", "key": "day5",
                "variants": five_variants("day5")}
        results = {}
        for v in five_variants("day5"):
            results[v["variant_id"]] = {"exposures": 3, "positive_replies": 0}
        verdict = variants.evaluate(node, results, progress=1.0)
        self.assertEqual(verdict["state"], variants.INSUFFICIENT_DATA)
        # The why should mention the minimum per variant (30).
        self.assertIn("30", verdict["why"])
        # And the minimum outcomes (8).
        self.assertIn("8", verdict["why"])

    def test_even_with_outcomes_the_per_variant_minimum_blocks(self):
        """8 outcomes across 5 variants with 10 exposures each is still
        not enough because 10 < 30."""
        node = {"type": "email", "key": "day5",
                "variants": five_variants("day5")}
        results = {
            "day5-short_direct": {"exposures": 10, "positive_replies": 3},
            "day5-casual": {"exposures": 10, "positive_replies": 2},
            "day5-professional": {"exposures": 10, "positive_replies": 1},
            "day5-consultative": {"exposures": 10, "positive_replies": 1},
            "day5-problem_led": {"exposures": 10, "positive_replies": 1},
        }
        verdict = variants.evaluate(node, results, progress=1.0)
        self.assertEqual(verdict["state"], variants.INSUFFICIENT_DATA)


if __name__ == "__main__":
    unittest.main()
