"""Two holes an independent model found by attacking the copy guards.

`approval.fingerprint` hashes exactly four things - channel, subject, body,
note. Everything else on a step is outside it. That is fine as long as nothing
outside it ever reaches a prospect, and on 2026-09-17 two paths did.

The guards had just been written and verified by the session that wrote them,
which is the same shape of mistake as `is_approved`'s three-argument form
comparing a stored step to itself and agreeing unconditionally. So a different
model was asked to defeat them - not to review them - and it produced a
mechanism for each, not an opinion.

  1. `bisonfactory._certified_copy` merges `extra` AFTER proving the
     fingerprint. A caller passing `subject` or `body` there would overwrite
     certified words with uncertified ones, and every layer downstream would
     report success. LATENT, not live: the one caller passes variant metadata.
     But "no caller does this today" is a fact about today's callers.

  2. `heyreachfactory._step_copy` returned `step["message"]` for InMail, and
     fell back to it for ordinary messages. `message` is not hashed, so a step
     approved and then edited in that field recomputes to the SAME stamp and
     certifies. LIVE, on the channel that is sending right now.

THE FIX IS FAIL-CLOSED, NOT A WIDER HASH. Hashing `message` and
`linkedin_action` is the clean answer and it invalidates every stored approval
on both lanes - an operator decision. Refusing to return words the stamp does
not cover costs nothing and can be done while a channel is live.
"""
import unittest

from src import approval, bisonfactory, heyreachfactory


def approved(step):
    """The step, with an approval that genuinely covers its own words."""
    out = dict(step)
    out["approval"] = {"by": "operator",
                       "fingerprint": approval.fingerprint(out)}
    return out


class ExtraIsMetadataAndMayNeverBeCopy(unittest.TestCase):
    """`_certified_copy`'s `extra` is merged after the proof."""

    def step(self):
        return approved({"channel": "email", "subject": "approved subject",
                         "body": "approved body"})

    def test_the_certified_copy_is_the_approved_copy(self):
        entry = bisonfactory._certified_copy(self.step(), "em1")
        self.assertEqual(entry["subject"], "approved subject")
        self.assertEqual(entry["body"], "approved body")

    def test_metadata_still_rides_along(self):
        """The legitimate use - variant identity - is unaffected."""
        entry = bisonfactory._certified_copy(
            self.step(), "em1", extra={"variant_id": "v7",
                                       "variant_style": "direct"})
        self.assertEqual(entry["variant_id"], "v7")
        self.assertEqual(entry["subject"], "approved subject")

    def test_copy_in_extra_is_refused_not_merged(self):
        """THE DEFEAT. Passing body through `extra` would land it in the entry
        after the fingerprint was checked against the step's own words."""
        for field in ("subject", "body", "note", "message"):
            with self.assertRaises(bisonfactory.FactoryRefused) as caught:
                bisonfactory._certified_copy(
                    self.step(), "em1",
                    extra={field: "words nobody approved"})
            self.assertIn(field, str(caught.exception))

    def test_the_refusal_names_the_step(self):
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            bisonfactory._certified_copy(self.step(), "em3",
                                         extra={"body": "unapproved"})
        self.assertIn("em3", str(caught.exception))


class TheFingerprintDoesNotCoverMessage(unittest.TestCase):
    """`message` is outside the hash, so it may not reach a prospect."""

    def test_the_hash_really_does_not_cover_message(self):
        """The premise, asserted rather than assumed - if this ever becomes
        false, the guards below are belt-and-braces and can be revisited."""
        one = {"channel": "linkedin", "note": "hello", "message": "alpha"}
        two = {"channel": "linkedin", "note": "hello", "message": "beta"}
        self.assertEqual(approval.fingerprint(one), approval.fingerprint(two))

    def test_an_inmail_body_edited_after_approval_yields_nothing(self):
        """THE DEFEAT. Approve an InMail, replace `message`, and the stamp
        still verifies because the field was never hashed."""
        step = approved({"channel": "linkedin", "linkedin_action": "inmail",
                         "subject": "Intro", "note": "approved body",
                         "body": ""})
        self.assertIsNotNone(heyreachfactory._step_copy(step))
        step["message"] = "Get 50% off today only - link"
        self.assertEqual(approval.fingerprint(step),
                         step["approval"]["fingerprint"])   # still verifies
        self.assertIsNone(heyreachfactory._step_copy(step))

    def test_an_inmail_whose_body_is_the_approved_note_still_works(self):
        step = approved({"channel": "linkedin", "linkedin_action": "inmail",
                         "subject": "Intro", "note": "approved body",
                         "body": ""})
        self.assertEqual(heyreachfactory._step_copy(step),
                         {"subject": "Intro", "message": "approved body"})

    def test_a_message_step_never_falls_back_to_message(self):
        """The second half of the same hole: an empty `note` used to fall
        through to `message`, which nothing certifies."""
        step = approved({"channel": "linkedin", "linkedin_action": "message",
                         "note": "", "body": ""})
        step["message"] = "unapproved words"
        self.assertEqual(approval.fingerprint(step),
                         step["approval"]["fingerprint"])
        self.assertIsNone(heyreachfactory._step_copy(step))

    def test_a_message_step_still_returns_its_approved_note(self):
        step = approved({"channel": "linkedin", "linkedin_action": "message",
                         "note": "the approved sentence", "body": ""})
        self.assertEqual(heyreachfactory._step_copy(step),
                         "the approved sentence")

    def test_a_connect_step_is_unaffected(self):
        """`note` IS hashed, so the connection note path never had the hole."""
        step = approved({"channel": "linkedin", "linkedin_action": "connect",
                         "note": "the approved note", "body": ""})
        self.assertEqual(heyreachfactory._step_copy(step),
                         "the approved note")


class TheFingerprintDoesNotCoverWhoApproved(unittest.TestCase):
    """The third thing outside the hash, and the one that had 84 instances.

    The fingerprint answers "have these words changed since approval". It
    cannot answer "did a person approve them" - and on a `generated: true`
    step the words never move, so a stamp the system wrote for itself agrees
    with the hash forever. Measured across the estate on 2026-09-17: 84
    approvals written `by: "claude"`, 83 of them on generated steps.
    """

    def test_a_machine_name_is_not_accountable(self):
        for who in ("claude", "qwen", "glm", "grok", "system", "assistant",
                    "fixture", "unknown", "", None, "  "):
            self.assertFalse(approval.is_accountable_approver(who), repr(who))

    def test_an_address_is_accountable(self):
        for who in ("someone@example.com",
                    "someone@example.com (operator authorisation "
                    "2026-09-16)",
                    "  Someone@Example.COM  "):
            self.assertTrue(approval.is_accountable_approver(who), repr(who))

    def test_a_declared_operator_arm_is_accountable(self):
        for who in ("operator", "operator-control-arm", "OPERATOR"):
            self.assertTrue(approval.is_accountable_approver(who), repr(who))

    def test_something_merely_shaped_like_an_address_is_not_enough(self):
        """`a@b` has no dot in its domain; an accountable identity is one
        somebody could actually be reached at."""
        for who in ("a@b", "@example.com", "claude@", "claude @ example"):
            self.assertFalse(approval.is_accountable_approver(who), repr(who))

    def test_a_self_recorded_email_approval_certifies_nothing(self):
        step = {"channel": "email", "subject": "S", "body": "the words"}
        step["approval"] = {"by": "claude",
                            "fingerprint": approval.fingerprint(step)}
        # The hash agrees - that was never the question.
        self.assertEqual(approval.fingerprint(step),
                         step["approval"]["fingerprint"])
        self.assertIsNone(bisonfactory._certified_copy(step, "em1"))

    def test_a_self_recorded_linkedin_approval_certifies_nothing(self):
        """The lane where it would have been permanent."""
        step = {"channel": "linkedin", "linkedin_action": "connect",
                "generated": True, "note": "the words"}
        step["approval"] = {"by": "claude",
                            "fingerprint": approval.fingerprint(step)}
        self.assertEqual(approval.fingerprint(step),
                         step["approval"]["fingerprint"])
        self.assertIsNone(heyreachfactory._step_copy(step))

    def test_the_same_words_from_a_person_do_certify(self):
        """The other half: the gate must not refuse everything."""
        step = {"channel": "linkedin", "linkedin_action": "connect",
                "generated": True, "note": "the words"}
        step["approval"] = {"by": "operator",
                            "fingerprint": approval.fingerprint(step)}
        self.assertEqual(heyreachfactory._step_copy(step), "the words")


if __name__ == "__main__":
    unittest.main()
