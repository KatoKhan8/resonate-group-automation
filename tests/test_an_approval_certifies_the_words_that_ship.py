"""D1: an approval certifies the words that SHIP, or nothing ships.

An approval fingerprint is a statement about words. Until this file it was
possible for that statement to be true of one set of words while a different
set was the one staged to EmailBison and sent to a real person:

  1. `approve.approve_step` took the fingerprint over the freshly expanded
     step and then copied that step's fields onto the stored slot only
     `if field not in slot`. A slot that already held older generated copy
     kept it and got the new stamp anyway, so the stamp certified words the
     slot did not contain.

  2. `bisonfactory._resolve_step_copy` has two branches. The VARIANT branch
     compared the fingerprint to the words it was about to return. The
     NO-VARIANT branch returned the slot's words after checking only that an
     approval EXISTED, so it shipped whatever the slot held under whatever
     stamp happened to be on it.

Measured 2026-09-16 on the live estate, campaign `productive-email-control-v2`:
`_plan` returned ten leads, `missing_copy` empty on all ten, and the body on
the wire for every one of the thirty steps was the model-generated text that
the audited CONTROL copy had replaced. The stamp said CONTROL; the words said
otherwise; nothing asked.

The invariant these tests hold down:

    approved CONTROL fingerprint + different stored copy  ->  REFUSE

and the refusal is by construction rather than by inspection: every branch
that turns a stored step into stageable copy goes through
`bisonfactory._certified_copy`, which hashes the entry's OWN subject and body
- the strings that become `{SUBJECT_N}` and `{BODY_N}` on the lead - and
compares that to the stamp. There is no path that stages words the hash did
not cover, and a missing stamp, a stamp with no fingerprint, and a fingerprint
that does not match all return the same None.

THE THREADING INVARIANT IS UNTOUCHED AND CHECKED HERE TOO: the opener owns the
only subject, the follow-ups are thread replies with a body and no independent
subject, and no `Re:` is simulated anywhere.
"""
import copy as _copy
import unittest

from src import approval, approve, bisonfactory, cadence, lint
from tests.campaignbase import CampaignTest, contact

# The shape the live defect was found in: a campaign carrying its own cadence
# of TEMPLATE email steps, over records whose slots hold older generated copy.
CONTROL_CADENCE = [
    {"key": "em1", "day": 1, "channel": "email", "template": "persona_pain"},
    {"key": "em2", "day": 5, "channel": "email",
     "template": "comparable_proof"},
    {"key": "em3", "day": 10, "channel": "email", "template": "breakup"},
]
CONTROL_KEYS = tuple(s["key"] for s in CONTROL_CADENCE)

# The provider sequence those steps are written to. Only the opener carries a
# subject of its own; the follow-ups are thread replies that reference
# `{SUBJECT_1}` and let EmailBison prepend `Re:` itself.
PROVIDER_SEQUENCE = [
    {"order": 1, "step_key": "em1", "email_subject": "{SUBJECT_1}",
     "email_body": "<p>{BODY_1}</p>", "wait_in_days": 4,
     "thread_reply": False},
    {"order": 2, "step_key": "em2", "email_subject": "{SUBJECT_1}",
     "email_body": "<p>{BODY_2}</p>", "wait_in_days": 5,
     "thread_reply": True},
    {"order": 3, "step_key": "em3", "email_subject": "{SUBJECT_1}",
     "email_body": "<p>{BODY_3}</p>", "wait_in_days": 1,
     "thread_reply": True},
]

# The words the CONTROL copy replaced. Any string will do as long as it is not
# what the campaign's templates render, which the fixtures assert rather than
# assume.
STALE_SUBJECT = "a question about {company}"
STALE_BODY = (
    "Hi {first},\n\n"
    "{company} describes itself as a full-service agency delivering "
    "data-driven work for its clients.\n\n"
    "We help teams like yours see delivery margin while the work is still "
    "running, rather than a fortnight after it ends.\n\n"
    "Worth a short conversation?\n")


class CertifiedCopyTest(CampaignTest):
    """One record, one contact, three template steps, a campaign cadence."""

    def setUp(self):
        super().setUp()
        self.recs = self.seed_records()
        self.rec = self.recs[0]
        self.contact_key = self.rec["contacts"][0]["key"]
        self.campaign = {"campaign_id": "control-v2",
                         cadence.CADENCE_KEY: _copy.deepcopy(CONTROL_CADENCE)}
        self.stale_copy(self.rec)

    # -------------------------------------------------------------- fixtures

    def stale_copy(self, rec, contact_key=None):
        """Write the OLD generated words into the campaign's step slots.

        This is TASK-210's starting point: the slots already hold model
        written copy, and the operator is about to approve the CONTROL text
        that replaces it.
        """
        contact_key = contact_key or rec["contacts"][0]["key"]
        person = lint.find_contact(rec, contact_key)
        first = (person.get("name") or "there").split()[0]
        slots = rec.setdefault("cadence", {}).setdefault(contact_key, {})
        for key in CONTROL_KEYS:
            slots[key] = {
                "channel": "email", "generated": True,
                "subject": STALE_SUBJECT.format(company=rec["company"]),
                "body": STALE_BODY.format(first=first,
                                          company=rec["company"]),
            }
        return rec

    def expanded(self, rec=None, contact_key=None):
        """The steps the CAMPAIGN expands - the words an operator is shown."""
        rec = rec if rec is not None else self.rec
        contact_key = contact_key or self.contact_key
        timeline = cadence.build(rec, self.config, campaign=self.campaign)
        return timeline["contacts"].get(contact_key) or {}

    def approve_control(self, rec=None, contact_key=None):
        """Approve the campaign-expanded steps, the way the operator did."""
        rec = rec if rec is not None else self.rec
        contact_key = contact_key or rec["contacts"][0]["key"]
        built = self.expanded(rec, contact_key)
        stamps = {}
        for key in CONTROL_KEYS:
            stamps[key] = approve.approve_step(
                rec, contact_key, key, by="operator", config=self.config,
                step=built[key], sync=False, campaign=self.campaign)
        return stamps

    def staged(self, rec=None, contact_key=None):
        """What `_approved_copy` would put on the lead: (copy, missing)."""
        rec = rec if rec is not None else self.rec
        contact_key = contact_key or self.contact_key
        return bisonfactory._approved_copy(
            rec, contact_key, PROVIDER_SEQUENCE, rec["id"],
            cadence_steps=_copy.deepcopy(CONTROL_CADENCE),
            campaign=self.campaign, config=self.config)


class TheFixtureModelsTheDefect(CertifiedCopyTest):
    """The setup is the live shape, not a shape built to pass."""

    def test_the_campaign_expands_words_the_slots_do_not_hold(self):
        """Without this, every negative test below would be vacuous: the
        stale copy and the CONTROL copy have to actually differ."""
        built = self.expanded()
        for key in CONTROL_KEYS:
            slot = approval.stored(self.rec, self.contact_key, key)
            self.assertTrue((built[key].get("body") or "").strip())
            self.assertNotEqual(built[key]["body"], slot["body"],
                                f"{key}: the campaign expands the same body "
                                f"the slot already holds, so this fixture "
                                f"cannot show the defect")


class ApprovedCopyStages(CertifiedCopyTest):
    """POSITIVE: what an operator approved is what is staged."""

    def test_the_approved_control_words_stage_and_pass(self):
        self.approve_control()
        copy, missing = self.staged()
        self.assertEqual(missing, [])
        self.assertEqual([entry["step_key"] for entry in copy],
                         list(CONTROL_KEYS))

    def test_the_staged_words_are_the_words_that_were_fingerprinted(self):
        """The staged string is the one the stamp was taken over - checked
        against the expanded step the operator saw, not against the slot the
        stager read."""
        built = self.expanded()
        stamps = self.approve_control()
        copy, _missing = self.staged()
        by_key = {entry["step_key"]: entry for entry in copy}
        for key in CONTROL_KEYS:
            self.assertEqual(by_key[key]["subject"], built[key]["subject"])
            self.assertEqual(by_key[key]["body"], built[key]["body"])
            # And the stamp really is a hash of those exact words.
            self.assertEqual(
                stamps[key]["fingerprint"],
                approval.fingerprint({"channel": "email",
                                      "subject": by_key[key]["subject"],
                                      "body": by_key[key]["body"],
                                      "note": built[key].get("note")}))

    def test_approval_leaves_the_slot_holding_what_it_certified(self):
        """The root cause, closed: after approving, the stored slot and the
        stamp on it agree. They did not before - the slot kept the words it
        already had."""
        self.approve_control()
        for key in CONTROL_KEYS:
            slot = approval.stored(self.rec, self.contact_key, key)
            self.assertEqual(approval.fingerprint(slot),
                             slot["approval"]["fingerprint"],
                             f"{key}: the slot holds words its own approval "
                             f"does not cover")

    def test_only_the_opener_owns_a_subject_on_the_wire(self):
        """The threading invariant, over certified copy: `subject_1` carries
        the opener's subject, the follow-ups carry a body and an empty
        subject, and nothing simulates `Re:`."""
        self.approve_control()
        copy, missing = self.staged()
        self.assertEqual(missing, [])
        lead = {"record_id": self.rec["id"], "contact_key": self.contact_key,
                "copy": copy, "subject": copy[0]["subject"],
                "body": copy[0]["body"]}
        values = {v["name"]: v["value"] for v in bisonfactory._variables_for(
            lead, {"client": "demo"}, sequence=PROVIDER_SEQUENCE)}
        self.assertEqual(values["subject_1"], copy[0]["subject"])
        # `bison._variables` drops empties, so a follow-up subject is absent
        # rather than blank. Either way the follow-up owns no subject.
        self.assertEqual(values.get("subject_2", ""), "")
        self.assertEqual(values.get("subject_3", ""), "")
        for position, entry in enumerate(copy, start=1):
            self.assertEqual(values[f"body_{position}"], entry["body"])
        for name, value in values.items():
            self.assertFalse(str(value).lower().startswith("re:"),
                             f"{name} simulates a threaded reply")


class AnApprovalCannotCertifyOtherWords(CertifiedCopyTest):
    """NEGATIVE: every way the stamp and the words can disagree refuses."""

    def assertRefused(self, why, rec=None, contact_key=None):
        copy, missing = self.staged(rec, contact_key)
        self.assertEqual(copy, [], why)
        self.assertEqual(sorted(missing), sorted(CONTROL_KEYS), why)

    def test_the_live_defect_shape_refuses(self):
        """THE MEASURED CASE. A stamp taken over the campaign-expanded CONTROL
        text, sitting on a slot that still holds the generated copy it was
        meant to replace. This is what staged ten leads clean."""
        built = self.expanded()
        for key in CONTROL_KEYS:
            slot = self.rec["cadence"][self.contact_key][key]
            slot["approval"] = {
                "by": "operator", "at": "2026-09-16T00:00:00",
                "fingerprint": approval.fingerprint(built[key])}
            # The slot keeps the stale words - what `field not in slot` did.
            self.assertNotEqual(slot["body"], built[key]["body"])
        self.assertRefused("a CONTROL fingerprint certified generated copy")

    def test_a_body_edited_after_approval_refuses(self):
        self.approve_control()
        slot = self.rec["cadence"][self.contact_key]["em1"]
        slot["body"] = slot["body"] + "\n\nP.S. one more thing.\n"
        copy, missing = self.staged()
        self.assertIn("em1", missing)
        self.assertNotIn("em1", [entry["step_key"] for entry in copy])

    def test_a_subject_edited_after_approval_refuses(self):
        self.approve_control()
        slot = self.rec["cadence"][self.contact_key]["em1"]
        slot["subject"] = "an entirely different subject line"
        copy, missing = self.staged()
        self.assertIn("em1", missing)
        self.assertNotIn("em1", [entry["step_key"] for entry in copy])

    def test_a_missing_fingerprint_refuses(self):
        """An approval that records nothing about the words it was given for
        certifies nothing. It must not read as "approved"."""
        self.approve_control()
        for key in CONTROL_KEYS:
            self.rec["cadence"][self.contact_key][key]["approval"] = {
                "by": "operator", "at": "2026-09-16T00:00:00"}
        self.assertRefused("an approval with no fingerprint passed")

    def test_no_approval_at_all_refuses(self):
        for key in CONTROL_KEYS:
            self.rec["cadence"][self.contact_key][key].pop("approval", None)
        self.assertRefused("an unapproved step staged")

    def test_an_approval_for_another_contacts_words_refuses(self):
        """A stamp is not a token that can be moved. Two records, each
        correctly approved, and one's stamp on the other's step refuses -
        because the words underneath it are the other person's."""
        other = self.recs[1]
        self.stale_copy(other)
        other_key = other["contacts"][0]["key"]
        self.approve_control()
        self.approve_control(other, other_key)

        mine = self.rec["cadence"][self.contact_key]["em1"]
        theirs = other["cadence"][other_key]["em1"]
        self.assertNotEqual(mine["body"], theirs["body"],
                            "the two contacts were approved for identical "
                            "words, so moving the stamp proves nothing")
        # Both stage cleanly before the swap.
        self.assertEqual(self.staged()[1], [])
        self.assertEqual(self.staged(other, other_key)[1], [])

        theirs["approval"] = _copy.deepcopy(mine["approval"])
        copy, missing = self.staged(other, other_key)
        self.assertIn("em1", missing)
        self.assertNotIn("em1", [entry["step_key"] for entry in copy])

    def test_a_step_whose_stored_copy_is_another_steps_words_refuses(self):
        """em2's approval over em2's words, with em3's body underneath it."""
        self.approve_control()
        slots = self.rec["cadence"][self.contact_key]
        self.assertNotEqual(slots["em2"]["body"], slots["em3"]["body"])
        slots["em2"]["body"] = slots["em3"]["body"]
        copy, missing = self.staged()
        self.assertIn("em2", missing)
        self.assertNotIn("em2", [entry["step_key"] for entry in copy])


class TheSingleStepShapeIsCertifiedToo(CertifiedCopyTest):
    """The `step_key is None` sequence shape reads the earliest approved
    email step, and it was checking existence only as well."""

    SINGLE = [{"order": 1, "email_subject": "{SUBJECT}",
               "email_body": "<p>{BODY}</p>", "wait_in_days": 3}]

    def single(self):
        return bisonfactory._approved_copy(
            self.rec, self.contact_key, self.SINGLE, self.rec["id"],
            cadence_steps=_copy.deepcopy(CONTROL_CADENCE),
            campaign=self.campaign, config=self.config)

    def test_the_certified_opener_stages(self):
        self.approve_control()
        copy, missing = self.single()
        self.assertEqual(missing, [])
        self.assertEqual(copy[0]["step_key"], "em1")

    def test_an_uncertified_opener_refuses_rather_than_falling_through(self):
        """And it does NOT walk on to em2. A later step's words in the
        opener's place is a message arriving out of order."""
        self.approve_control()
        self.rec["cadence"][self.contact_key]["em1"]["body"] += " edited"
        copy, missing = self.single()
        self.assertEqual(copy, [])
        self.assertEqual(len(missing), 1)


class TheStageRefusesNotJustTheReport(CertifiedCopyTest):
    """`_approved_copy` reports; `_ensure_leads` is what refuses. The report
    is only useful if the refusal follows from it."""

    def test_uncertified_copy_stops_the_whole_stage(self):
        built = self.expanded()
        for key in CONTROL_KEYS:
            slot = self.rec["cadence"][self.contact_key][key]
            slot["approval"] = {
                "by": "operator", "at": "2026-09-16T00:00:00",
                "fingerprint": approval.fingerprint(built[key])}
        copy, missing = self.staged()
        plan = {"leads": [{"record_id": self.rec["id"],
                           "contact_key": self.contact_key,
                           "email": self.rec["contacts"][0]["email"],
                           "first_name": "Champ", "copy": copy,
                           "missing_copy": missing, "unsupported_copy": [],
                           "subject": "", "body": ""}],
                "sequence": PROVIDER_SEQUENCE}
        report = {"did": [], "plan": {"name": "x"}, "provider": {}}
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            bisonfactory._ensure_leads("9001", self.campaign, plan, report)
        self.assertIn("no approved copy", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
