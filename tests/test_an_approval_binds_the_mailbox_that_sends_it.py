"""An approval covers the WORDS, the MAILBOX and the SIGNATURE. All three.

MEASURED DEFECT, 2026-09-30, against the real gates.

`approval.fingerprint` covered channel, subject, body, note and ps - and
nothing else. So after an approval was granted, swapping the sending mailbox
or the signature block it renders left `eligibility.decide` answering
`eligible`, and the email a real person received was signed by somebody the
approver never blessed. Only BODY and SUBJECT moved the fingerprint.

THE ONLY BACKSTOP WAS THE WRONG SHAPE. `campaigns.approval_is_current` is
consulted inside `eligibility.decide` ONLY when a campaign row is passed, and
`campaign=None` is a supported call that every test in `test_eligibility`
makes. With no campaign the swap sailed through unopposed.

WHY THIS IS NOT A THEORETICAL GAP. Incident B: 64 emails carrying a different
agency's pitch, signed with the operator's name, from mailboxes belonging to
other people. And `config/clients/productive.yaml` says in its own comments
that the 222 sending mailboxes carry owner names the engine does not sign
with. A signature is a claim about who is writing; a claim nobody approved is
precisely what the approval gate exists to refuse.

WHAT IS PINNED HERE, and none of it reads the source:

  (a) the mailbox swapped after approval - REFUSED, with the exact verdict;
  (b) the sender identity, and separately the RENDERED signature, swapped
      after approval - REFUSED;
  (c) both of those with `campaign=None`, so the refusal cannot be coming
      from `campaigns.approval_is_current`;
  (d) THE POSITIVE CONTROL: nothing swapped, still `eligible`. Without this
      every test above would pass under a rule that refuses everything;
  (e) body and subject swaps still refuse exactly as they did before;
  (f) a stamp that never carried the binding is STALE, not grandfathered -
      for EVERY client, including one that declares no sender at all. See
      `AnOldStampIsInvalidForEveryClient` at the bottom of this file for the
      measured hole that rule was written against.
"""
import unittest

from src import (approval, cadence, clients, eligibility as E,
                 sendersignature, store)
from tests.campaignbase import BODIES, SUBJECTS, contact
from tests.test_eligibility import GateTest


def _with_sender(config, **fields):
    """The same client file with a different `sender:` block.

    A dict rather than a file rewrite: `decide` takes the config it judges
    under, and swapping it here is exactly the substitution an operator
    editing `config/clients/<client>.yaml` between approval and send makes.
    """
    block = dict(config.get("sender") or {})
    block.update(fields)
    return dict(config, sender=block)


class ApprovalBindsTheMailbox(GateTest):
    """One record, one genuinely eligible email step, then one swap."""

    def setUp(self):
        super().setUp()
        # The demo client declares a sender; assert it rather than assume it,
        # because every refusal below is meaningless against a client that
        # declares none - `sender_fingerprint` is empty for those by design
        # and this whole suite would pass while proving nothing.
        self.assertTrue((self.config.get("sender") or {}).get("name"),
                        "the fixture client must declare a sending identity")

    # ------------------------------------------------------------- helpers

    def under(self, rec, recs, config, step="day1", **kw):
        """`decide` under a DIFFERENT client config from the approval's.

        `GateTest.decide` pins `self.config`, and the whole question here is
        what happens when the config the gate judges under is not the one the
        approval was taken against.
        """
        return E.decide(rec, rec["contacts"][0], step, recs=recs,
                        config=config, **kw)

    def refused(self, decision, why="held:approval_stale"):
        self.assertEqual(decision["verdict"], E.HELD, decision["reasons"])
        self.assertEqual(decision["reasons"], [why], decision["reasons"])
        self.assertFalse(decision.eligible)

    # ------------------------------------------------- (d) positive control

    def test_nothing_swapped_is_still_eligible(self):
        """THE CONTROL. A rule that refuses everything passes every other
        test in this file; only this one can tell the two apart."""
        rec, recs = self.ready()
        decision = self.decide(rec, recs)
        self.assertTrue(decision.eligible, decision["reasons"])
        self.assertEqual(decision["verdict"], E.ELIGIBLE)
        self.assertEqual(decision["reasons"], [])

    def test_an_unrelated_config_edit_does_not_invalidate_the_approval(self):
        """The binding is the SENDER, not the whole config.

        Without this, "refuses when the config changed at all" would pass
        every swap test here, and every operator edit to an unrelated key
        would silently unapprove the estate.
        """
        rec, recs = self.ready()
        other = dict(self.config, booking_link="https://example.test/other")
        self.assertTrue(self.under(rec, recs, other).eligible)

    # --------------------------------------------------- (a) the mailbox

    def test_the_sending_address_swapped_after_approval_is_refused(self):
        """A different mailbox, the display name left alone.

        `clients.sender_identity` drops `email`, so this is the swap the
        rendered signature cannot see: same name at the bottom of the
        message, a different person's inbox in the From line. Bound anyway,
        because which mailbox sends is part of what was approved.
        """
        rec, recs = self.ready()
        swapped = _with_sender(self.config, email="someone.else@demo.test")
        self.refused(self.under(rec, recs, swapped))

    def test_the_sending_mode_swapped_after_approval_is_refused(self):
        rec, recs = self.ready()
        swapped = _with_sender(self.config, mode="agency")
        self.refused(self.under(rec, recs, swapped))

    # ------------------------------------- (b) the identity and the signature

    def test_the_sender_name_swapped_after_approval_is_refused(self):
        rec, recs = self.ready()
        swapped = _with_sender(self.config, name="Someone Else Entirely")
        self.refused(self.under(rec, recs, swapped))

    def test_the_rendered_signature_swapped_after_approval_is_refused(self):
        """The IDENTITY is untouched; only what it RENDERS moves.

        `sendersignature.compose` is what actually reaches the bottom of the
        body, and its company line is a module constant rather than a config
        field - so this is the one swap that proves the binding covers the
        rendered string and not merely the fields it was built from.
        """
        rec, recs = self.ready()
        before = self.decide(rec, recs)
        self.assertTrue(before.eligible, before["reasons"])
        original = sendersignature.COMPANY_LINE
        sendersignature.COMPANY_LINE = "A Different Company"
        self.addCleanup(setattr, sendersignature, "COMPANY_LINE", original)
        self.refused(self.decide(rec, recs))

    def test_a_linkedin_step_binds_the_sender_too(self):
        """The connection note says who is writing. Same question, same
        answer - the two channels are not allowed to disagree about what an
        approval covers."""
        recs = self.seed_records()
        rec = recs[0]
        rec["contacts"] = [contact("acme-champ", "Champ", "champ@acme.test")]
        timeline = cadence.build(rec, self.config, recs=recs)
        note_key = next(key for key, step in
                        timeline["contacts"]["acme-champ"].items()
                        if step.get("channel") == "linkedin"
                        and (step.get("note") or "").strip())
        from src import approve
        approve.approve_step(rec, "acme-champ", note_key, by="a@b.test",
                             config=self.config)
        store.save(recs)
        recs = store.load()
        rec = recs[0]
        self.assertTrue(
            E.decide(rec, rec["contacts"][0], note_key, recs=recs,
                     config=self.config).eligible,
            "the LinkedIn control must be eligible before the swap")
        swapped = _with_sender(self.config, name="Someone Else Entirely")
        decision = E.decide(rec, rec["contacts"][0], note_key, recs=recs,
                            config=swapped)
        self.assertFalse(decision.eligible)
        self.assertIn(E.HELD_APPROVAL_STALE, decision["reasons"])

    # ------------------------------------------------ (c) with campaign=None

    def test_the_refusal_does_not_need_a_campaign_row(self):
        """The campaign gate cannot be what is refusing: there is no campaign.

        `_campaign` returns early for `campaign=None` and
        `campaigns.approval_is_current` is never reached, so the only thing
        left to refuse is the draft approval itself. Asserted on the reason
        string as well as the verdict: `held:campaign_approval_stale` here
        would mean the campaign gate fired and this test proved nothing.
        """
        rec, recs = self.ready()
        swapped = _with_sender(self.config, name="Someone Else Entirely")
        decision = self.under(rec, recs, swapped, campaign=None)
        self.refused(decision)
        self.assertNotIn(E.HELD_CAMPAIGN_STALE, decision["reasons"])
        self.assertNotIn(E.HELD_CAMPAIGN_UNAPPROVED, decision["reasons"])

    def test_the_mailbox_swap_also_needs_no_campaign_row(self):
        rec, recs = self.ready()
        swapped = _with_sender(self.config, email="someone.else@demo.test")
        decision = self.under(rec, recs, swapped, campaign=None)
        self.refused(decision)
        self.assertNotIn(E.HELD_CAMPAIGN_STALE, decision["reasons"])

    # ---------------------------------------------------- (e) no regression

    def test_a_body_swap_still_refuses(self):
        """The words the approval was always about.

        Swapped for the OTHER step's real body rather than a short string:
        a two-word body is refused by the lint before the approval gate is
        reached, so it would prove the lint works and nothing else.
        """
        rec, recs = self.ready()
        slot = rec["cadence"]["acme-champ"]["day1"]
        slot["body"] = BODIES["day15"].format(first="Champ",
                                              company=rec["company"])
        self.refused(self.decide(rec, recs))

    def test_a_subject_swap_still_refuses(self):
        rec, recs = self.ready()
        slot = rec["cadence"]["acme-champ"]["day1"]
        slot["subject"] = SUBJECTS["day15"].format(company=rec["company"])
        self.refused(self.decide(rec, recs))

    def test_a_step_that_was_never_approved_still_says_so(self):
        """`held:draft_not_approved` and `held:approval_stale` are different
        answers and the swap must not collapse them."""
        rec, recs = self.ready()
        rec["cadence"]["acme-champ"]["day1"].pop("approval")
        self.refused(self.decide(rec, recs), why=E.HELD_APPROVAL_MISSING)

    # -------------------------------------------------- (f) no grandfathering

    def test_a_stamp_taken_before_the_binding_existed_is_stale(self):
        """An approval that never covered the mailbox did not cover it.

        The alternative - treat a missing binding as "fine" - fails OPEN for
        every approval already in the estate, which is the whole population
        this defect was found in.
        """
        rec, recs = self.ready()
        stamp = rec["cadence"]["acme-champ"]["day1"]["approval"]
        self.assertTrue(stamp.pop("sender_fingerprint", None),
                        "approve_step must record the binding")
        self.refused(self.decide(rec, recs))

    # ------------------------------------------- the derived record state

    def test_the_record_falls_back_to_drafted_when_the_sender_changes(self):
        """Derived, never latched. An operator sees `drafted` again rather
        than an `approved` record the send gate silently refuses.

        Every approvable step is approved here, not only the email ones:
        `fully_approved` means all of them, so a record with an unapproved
        LinkedIn note is `drafted` for a reason that has nothing to do with
        the sender and would make this test pass for the wrong one.
        """
        from src import approve
        rec, recs = self.ready()
        approve.approve_record(rec, by="a@b.test", config=self.config)
        self.assertEqual(approve.sync_state(rec, self.config), "approved")
        swapped = _with_sender(self.config, name="Someone Else Entirely")
        self.assertEqual(approve.sync_state(rec, swapped), "drafted")

    def test_neither_releasing_gate_can_be_reached_with_no_config(self):
        """`config=None` is the words-only question, so a gate that forwarded
        a None would grandfather every unbound stamp. Both resolve one.

        Behavioural, not a signature check: the stamps here carry NO binding,
        so each gate is asked with nothing passed in and must still refuse -
        which it can only do by having resolved the client's config itself.
        """
        from src import approve
        rec, recs = self.ready()
        for slot in rec["cadence"]["acme-champ"].values():
            if slot.get("approval"):
                slot["approval"].pop("sender_fingerprint", None)

        # The send gate, called with no config argument at all.
        decision = E.decide(rec, rec["contacts"][0], "day1", recs=recs)
        self.refused(decision)

        # And the derived record state, likewise.
        self.assertFalse(approve.fully_approved(rec),
                         "fully_approved passed None through to the "
                         "words-only question")


class SenderFingerprintIsAFunctionOfTheSender(unittest.TestCase):
    """The primitive, asked directly. No records, no gates."""

    BLOCK = {"mode": "client_rep", "name": "Ada Lovelace", "role": "founder",
             "company": "Demo", "email": "ada@demo.test"}

    def fp(self, **fields):
        block = dict(self.BLOCK)
        block.update(fields)
        return approval.sender_fingerprint({"sender": block})

    def test_it_is_stable(self):
        self.assertEqual(self.fp(), self.fp())

    def test_every_declared_field_moves_it(self):
        base = self.fp()
        for field, value in (("mode", "agency"), ("name", "Grace Hopper"),
                             ("role", "cto"), ("company", "Other"),
                             ("email", "grace@demo.test"),
                             ("title", "Head of Demo"),
                             ("works_on", "margin")):
            self.assertNotEqual(base, self.fp(**{field: value}),
                                f"{field} must move the sender fingerprint")

    def test_whitespace_is_not_a_swap(self):
        self.assertEqual(self.fp(), self.fp(name="  Ada   Lovelace  "))

    #: Every shape that means "this client declares no sending identity".
    #: The starter config writes `mode` only; older files write nothing; a
    #: hand-edited one can put a string where the map belongs.
    NO_SENDER_CONFIGS = ({}, None, {"sender": "Ada"}, {"sender": {}},
                         {"sender": {"mode": ""}}, {"name": "X"})

    def test_no_input_whatever_produces_a_falsy_fingerprint(self):
        """THE PROPERTY THAT CLOSES THE GRANDFATHERING HOLE.

        A stamp that recorded no binding reads as absent. If any input could
        make this function answer `""` or None, that absence would compare
        equal to the answer and a pre-binding stamp would authorize a send.
        Pinned as a property over every no-sender shape rather than as a
        presence check at one call site, because the call site is the thing a
        later edit forgets.
        """
        for config in self.NO_SENDER_CONFIGS:
            fp = approval.sender_fingerprint(config)
            self.assertTrue(fp, f"{config!r} produced a falsy fingerprint")
            self.assertEqual(len(fp), 16, f"{config!r}: not a digest")

    def test_a_client_declaring_no_sender_binds_the_absence(self):
        """All the no-sender shapes render the same thing - nothing - so they
        bind to the same digest, and it is not a declared sender's."""
        digests = {approval.sender_fingerprint(c)
                   for c in self.NO_SENDER_CONFIGS}
        self.assertEqual(len(digests), 1, digests)
        self.assertNotIn(self.fp(), digests,
                         "a declared sender must not collide with the "
                         "declaration of none")

    def test_declaring_a_sender_later_moves_it_off_the_absence(self):
        """So an approval taken while the client had no sender goes stale the
        moment one is declared, rather than silently covering it."""
        self.assertNotEqual(approval.sender_fingerprint({}),
                            approval.sender_fingerprint(
                                {"sender": {"name": "Ada Lovelace"}}))

    def test_an_unreadable_config_does_not_match_a_real_sender(self):
        """Fail closed. `eligibility.decide` falls back to `{}` when the
        client config cannot be loaded, and that must not satisfy a stamp
        taken against a declared mailbox."""
        self.assertNotEqual(approval.sender_fingerprint({}), self.fp())

    def test_the_rendered_signature_is_part_of_the_material(self):
        base = self.fp()
        original = sendersignature.COMPANY_LINE
        sendersignature.COMPANY_LINE = "A Different Company"
        self.addCleanup(setattr, sendersignature, "COMPANY_LINE", original)
        self.assertNotEqual(base, self.fp())


class AnOldStampIsInvalidForEveryClient(unittest.TestCase):
    """REGRESSION, GLM verdict on 8ab8f8dc: `old_stamp` FAIL.

    The first version of this fix bound the mailbox and then let one
    grandfathering path survive. `is_approved` normalized a missing
    `sender_fingerprint` to `""`, and `sender_fingerprint` ALSO answered `""`
    for a client declaring no sender - so `"" == ""` was True and a stamp
    taken before the binding existed authorized a send.

    MEASURED on 8ab8f8dc, the two rows this class carries:

        client = productive (declares a sender)  ->  is_approved  False
        client declares NO sender block          ->  is_approved  True   <- hole

    It did not affect Productive and did not affect the canary. It went
    anyway: the operator's decision was unconditional - no grandfathering,
    old stamps that do not bind the mailbox become invalid for sending and
    require re-approval - and ABSENT == ABSENT is the exact defect shape this
    repository keeps rediscovering, absence of a binding read as positive
    evidence that the binding matches.

    Here as its own class, with no record fixture and no gate, so it states
    the rule about the PRIMITIVE and cannot be made to pass by something
    upstream refusing first.
    """

    STEP = {"channel": "email", "subject": "a subject", "body": "a body"}

    def rec_with(self, stamp):
        return {"cadence": {"c": {"k": dict(self.STEP, approval=stamp)}}}

    def old_stamp(self):
        """Exactly what `approve_step` wrote before the binding existed."""
        return {"by": "operator@example.com", "at": "2026-09-20T00:00:00Z",
                "fingerprint": approval.fingerprint(self.STEP)}

    def test_the_words_hash_on_the_old_stamp_is_genuinely_current(self):
        """Without this the rows below could pass because the WORDS moved,
        which would prove nothing about the mailbox binding."""
        rec = self.rec_with(self.old_stamp())
        self.assertTrue(approval.is_approved(rec, "c", "k"),
                        "the old stamp must still match its own words when "
                        "no config is supplied")

    def test_row_1_productive_declares_a_sender_and_refuses(self):
        rec = self.rec_with(self.old_stamp())
        self.assertFalse(approval.is_approved(
            rec, "c", "k", config=clients.load("productive")))

    def test_row_2_a_client_with_no_declared_sender_refuses_too(self):
        """THE ROW THAT USED TO BE True."""
        rec = self.rec_with(self.old_stamp())
        self.assertFalse(approval.is_approved(rec, "c", "k", config={}))

    def test_every_no_sender_shape_refuses(self):
        """`None` is deliberately absent from this list - see below."""
        rec = self.rec_with(self.old_stamp())
        for config in ({}, {"sender": "Ada"}, {"sender": {}},
                       {"sender": {"mode": ""}}, {"name": "X"}):
            self.assertFalse(
                approval.is_approved(rec, "c", "k", config=config),
                f"an unbound stamp was accepted for config {config!r}")

    def test_config_none_asks_the_words_only_and_is_not_grandfathering(self):
        """`config=None` IS NOT A CLIENT. It is "no config supplied".

        The distinction matters and this test exists so nobody collapses it
        into the rule above. `None` means the caller is asking the question it
        has the inputs for - have these words changed - and the reporting
        surfaces (preview, report, funnel, qa) ask exactly that. `{}` is
        different: it is a config that was supplied and has no sender, and an
        unbound stamp is refused against it.

        That it is not a way back in for a SEND is asserted behaviourally,
        over in `ApprovalBindsTheMailbox`: both gates that can release a step
        resolve a config of their own, so neither reaches here with None.
        """
        rec = self.rec_with(self.old_stamp())
        self.assertTrue(approval.is_approved(rec, "c", "k", config=None))
        self.assertFalse(approval.is_approved(rec, "c", "k", config={}))

    def test_a_stamp_recording_an_empty_binding_refuses_as_well(self):
        """`""` and None are what a missing key looks like after any
        round-trip that drops empty values. Neither is a binding."""
        for value in ("", None, 0, False):
            rec = self.rec_with(dict(self.old_stamp(),
                                     sender_fingerprint=value))
            self.assertFalse(
                approval.is_approved(rec, "c", "k", config={}),
                f"sender_fingerprint={value!r} was accepted as a binding")

    def test_a_client_with_no_sender_can_still_be_approved_properly(self):
        """REQUIREMENT 3, at the primitive. Refuse-and-demand-approval, not
        refuse-forever: a client with nothing to bind still gets a valid
        approval once one is actually taken against it."""
        bound = dict(self.old_stamp(),
                     sender_fingerprint=approval.sender_fingerprint({}))
        rec = self.rec_with(bound)
        self.assertTrue(approval.is_approved(rec, "c", "k", config={}))
        self.assertFalse(approval.is_approved(
            rec, "c", "k", config=clients.load("productive")),
            "a binding taken against no sender must not cover a real one")


if __name__ == "__main__":
    unittest.main()
