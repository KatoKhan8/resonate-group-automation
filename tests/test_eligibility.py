"""The central gate: what it refuses, and what it refuses to be talked out of.

The adversarial class is the important one. Every test there sets a stored
field to the value that would mean "yes" while a real condition says no, and
the gate must still refuse. That is the difference between a check and a
guarantee.
"""
import unittest

from src import (accountpolicy as ap, cadence, campaigns, dedupe,
                 eligibility as E, events, lint,
                 mx, orchestrator, push, store)
from tests.campaignbase import CLIENT, CampaignTest, contact

GOOGLE = ["aspmx.l.google.com"]
PROOFPOINT = ["mx1.pphosted.com"]


class GateTest(CampaignTest):
    def ready(self, mx_hosts=GOOGLE, day=21):
        """A record where one email step is genuinely eligible."""
        recs = self.seed_records()
        rec = recs[0]
        rec["contacts"] = [contact("acme-champ", "Champ", "champ@acme.test")]
        if mx_hosts is not None:
            rec["contacts"][0]["mx"] = mx.decide(
                mx_hosts, mx.settings(self.config), domain="acme.test")
        self.draft_everything(recs)
        self.approve_drafts(recs)
        store.save(recs)
        return rec, store.load()

    def decide(self, rec, recs, step="day1", **kw):
        contact_obj = rec["contacts"][0]
        return E.decide(rec, contact_obj, step, recs=recs, config=self.config,
                        **kw)


class TestTheHappyPath(GateTest):
    def test_a_clean_step_is_eligible(self):
        rec, recs = self.ready()
        decision = self.decide(rec, recs)
        self.assertTrue(decision.eligible, decision["reasons"])
        self.assertEqual(decision["verdict"], E.ELIGIBLE)

    def test_it_carries_the_logical_push_id(self):
        rec, recs = self.ready()
        decision = self.decide(rec, recs)
        self.assertEqual(decision["push_id"], "acme:acme-champ:day1:email")

    def test_the_decision_is_falsey_unless_eligible(self):
        rec, recs = self.ready()
        self.assertTrue(bool(self.decide(rec, recs)))
        rec["paused"] = {"since": "x", "reason": "reply_received"}
        self.assertFalse(bool(self.decide(rec, recs)))

    def test_a_linkedin_step_is_decided_separately(self):
        rec, recs = self.ready()
        decision = self.decide(rec, recs, step="day3")
        self.assertEqual(decision["channel"], "linkedin")


class TestBlocked(GateTest):
    def blocked(self, expected, mutate, step="day1"):
        rec, recs = self.ready()
        mutate(rec)
        decision = self.decide(rec, recs, step=step)
        self.assertEqual(decision["verdict"], E.BLOCKED, decision["reasons"])
        self.assertIn(expected, decision["reasons"])

    def test_a_dropped_record(self):
        self.blocked(E.BLOCKED_DROPPED,
                     lambda r: r.update(state="dropped", drop_reason="out of geo"))

    def test_a_paused_company(self):
        self.blocked(E.BLOCKED_COMPANY_PAUSED,
                     lambda r: r.update(paused={"since": "x", "reason": "reply"}))

    def test_a_paused_contact(self):
        self.blocked(E.BLOCKED_CONTACT_PAUSED,
                     lambda r: r["contacts"][0].update(paused=True))

    def test_any_reply_at_all(self):
        def reply(rec):
            events.record(rec, events.REPLY_RECEIVED, contact_key="acme-champ",
                          channel="email")
        self.blocked(E.BLOCKED_REPLIED, reply)

    def test_an_unsubscribe(self):
        self.blocked(E.BLOCKED_UNSUBSCRIBED,
                     lambda r: r["contacts"][0].update(unsubscribed=True))

    def test_a_duplicate_identity(self):
        self.blocked(E.BLOCKED_DUPLICATE,
                     lambda r: r["contacts"][0].update(
                         duplicate_of={"record_id": "other", "contact_key": "x"}))

    def test_an_excluded_contact(self):
        self.blocked(E.BLOCKED_NOT_SELECTED,
                     lambda r: r["contacts"][0].update(excluded=True))

    def test_an_already_pushed_step(self):
        def pushed(rec):
            push.mark_pushed(rec, "acme-champ", "day1",
                             "acme:acme-champ:day1:email")
        self.blocked(E.BLOCKED_ALREADY_PUSHED, pushed)

    def test_a_missing_recipient(self):
        self.blocked(E.BLOCKED_NO_RECIPIENT,
                     lambda r: r["contacts"][0].pop("email"))

    def test_a_suppressed_domain(self):
        rec, recs = self.ready()
        decision = self.decide(rec, recs, suppressed={"acme.test"})
        self.assertEqual(decision["verdict"], E.BLOCKED)
        self.assertIn(E.BLOCKED_SUPPRESSED, decision["reasons"])

    def test_a_linkedin_step_with_no_profile(self):
        rec, recs = self.ready()
        rec["contacts"][0]["linkedin"] = None
        decision = self.decide(rec, recs, step="day3")
        self.assertEqual(decision["verdict"], E.BLOCKED)
        self.assertIn(E.BLOCKED_NO_PROFILE, decision["reasons"])


class TestHeld(GateTest):
    def test_an_unverified_recipient_is_held_not_blocked(self):
        """Nobody has been asked: no evidence, and no legacy verdict either."""
        rec, recs = self.ready()
        rec["contacts"][0]["verification"] = {"state": "unknown", "evidence": []}
        rec["contacts"][0].pop("verdict", None)
        rec["contacts"][0].pop("reoon", None)
        decision = self.decide(rec, recs)
        self.assertEqual(decision["verdict"], E.HELD)
        self.assertIn(E.HELD_VERIFICATION_UNKNOWN, decision["reasons"])

    def test_a_half_confirmed_recipient_says_so_rather_than_unknown(self):
        """One provider answered and the policy wants two. That is a different
        problem from nobody answering, and it gets its own reason."""
        from src import verification
        rec, recs = self.ready()
        evidence = [verification.result("contactout", verification.S_VALID,
                                        rec["contacts"][0]["email"])]
        # A fixture built in a given state. `apply` is append-only, so a
        # shorter list would merge with what `ready()` already stored.
        rec["contacts"][0].pop("verification", None)
        verification.apply(rec["contacts"][0],
                           verification.decide(evidence), evidence)
        decision = self.decide(rec, recs)
        self.assertEqual(decision["verdict"], E.HELD)
        self.assertIn(E.HELD_INSUFFICIENT_CONFIRMATIONS, decision["reasons"])

    def test_a_dns_failure_is_held(self):
        rec, recs = self.ready(mx_hosts=None)
        rec["contacts"][0]["mx"] = mx.decide([], mx.settings(self.config),
                                             status=mx.DNS_FAILURE,
                                             domain="acme.test")
        decision = self.decide(rec, recs)
        self.assertEqual(decision["verdict"], E.HELD)
        self.assertIn(E.HELD_DNS_FAILURE, decision["reasons"])

    def test_an_unapproved_draft_is_held(self):
        rec, recs = self.ready()
        for steps in rec["cadence"].values():
            for step in steps.values():
                step.pop("approval", None)
        decision = self.decide(rec, recs)
        self.assertEqual(decision["verdict"], E.HELD)

    def test_a_step_that_is_not_due_is_held(self):
        rec, recs = self.ready()
        decision = self.decide(rec, recs, step="day21", day=1)
        self.assertEqual(decision["verdict"], E.HELD)
        self.assertIn(E.HELD_NOT_DUE, decision["reasons"])

    def test_an_unapproved_campaign_is_held(self):
        rec, recs = self.ready()
        campaign = self.make_campaign(recs)
        decision = self.decide(rec, recs, campaign=campaign)
        self.assertEqual(decision["verdict"], E.HELD)
        self.assertIn(E.HELD_CAMPAIGN_UNAPPROVED, decision["reasons"])

    def test_a_stale_campaign_approval_is_held(self):
        """Changed underneath, without going through the orchestrator - which
        would have cleared the approval outright. This is the sneakier case:
        the approval is still sitting there, and it no longer applies."""
        campaign, recs, _ = self.approved_campaign()
        recs = store.load()
        recs[0]["contacts"].append(contact("acme-extra", "Extra",
                                           "extra@acme.test"))
        store.save(recs)
        recs = store.load()
        rec = recs[0]
        decision = E.decide(rec, rec["contacts"][0], "day1", recs=recs,
                            config=self.config, campaign=campaign)
        self.assertEqual(decision["verdict"], E.HELD)
        self.assertIn(E.HELD_CAMPAIGN_STALE, decision["reasons"])

    def test_a_missing_provider_mapping_is_held(self):
        """Approved with no external campaign, so the approval is current and
        the mapping is the only thing missing."""
        rec, recs = self.ready()
        campaign = self.make_campaign(recs, external=False)
        campaign["approval"] = {
            "action": "approve", "by": "U0DEMOADMIN1",
            "fingerprint": campaigns.fingerprint(campaign, recs, self.config)}
        campaign["status"] = campaigns.APPROVED
        decision = self.decide(rec, recs, campaign=campaign)
        self.assertEqual(decision["verdict"], E.HELD)
        self.assertIn(E.HELD_NO_MAPPING, decision["reasons"])

    def test_a_waiting_dependency_is_held(self):
        rec, recs = self.ready()
        decision = self.decide(rec, recs, step="day8")
        self.assertEqual(decision["verdict"], E.HELD)
        self.assertIn(E.HELD_AWAITING_DEPENDENCY, decision["reasons"])


class TestSkipped(GateTest):
    def test_a_blocked_gateway_skips_the_email_channel(self):
        rec, recs = self.ready(mx_hosts=PROOFPOINT)
        decision = self.decide(rec, recs)
        self.assertEqual(decision["verdict"], E.SKIPPED)
        self.assertIn(E.SKIPPED_EMAIL_CHANNEL, decision["reasons"])
        self.assertIn(E.BLOCKED_MX, decision["reasons"])

    def test_the_linkedin_step_survives_a_blocked_gateway(self):
        rec, recs = self.ready(mx_hosts=PROOFPOINT)
        decision = self.decide(rec, recs, step="day3")
        self.assertNotEqual(decision["verdict"], E.SKIPPED)

    def test_a_step_that_does_not_exist_is_skipped(self):
        rec, recs = self.ready()
        decision = self.decide(rec, recs, step="day99")
        self.assertEqual(decision["verdict"], E.SKIPPED)
        self.assertIn(E.SKIPPED_NO_STEP, decision["reasons"])



class TestSomethingArrivingBetweenSteps(GateTest):
    """The scenario the pre-send recheck exists for.

    Context is assembled when a campaign is built. Step 4 may be prepared
    days after step 1, and everything that matters can change in between:
    the person replies, somebody asks to be removed, a colleague at the
    same account says stop.

    `push.verify_before_payload` recomputes rather than trusting what was
    decided earlier, and these assert the recompute actually catches each
    case rather than that the function is called.
    """

    def test_a_reply_between_steps_stops_the_next_one(self):
        rec, recs = self.ready()
        self.assertTrue(self.decide(rec, recs).eligible)

        events.record(rec, events.REPLY_RECEIVED,
                      contact_key="acme-champ", channel="email",
                      at="2026-02-01T09:00:00Z",
                      provider_event_id="r-between-1")
        store.save([rec])

        decision = self.decide(rec, store.load())
        self.assertFalse(decision.eligible)

    def test_a_removal_request_between_steps_stops_the_next_one(self):
        rec, recs = self.ready()
        self.assertTrue(self.decide(rec, recs).eligible)

        ap.apply_reply(rec, "acme-champ", ap.UNSUBSCRIBE, workspace=CLIENT)
        store.save([rec])

        decision = self.decide(rec, store.load())
        self.assertFalse(decision.eligible)

    def test_a_company_wide_stop_reaches_a_colleague(self):
        """The multi-DM case: one person's removal request is the
        company's, and the next step to somebody else must not go."""
        rec, recs = self.ready()
        rec["contacts"].append(
            contact("acme-second", "Second", "second@acme.test"))
        store.save([rec])

        ap.apply_reply(rec, "acme-champ", ap.ACCOUNT_DNC, workspace=CLIENT)
        store.save([rec])

        rec = store.get(rec["id"])
        colleague = [c for c in rec["contacts"]
                     if c["key"] == "acme-second"][0]
        decision = E.decide(rec, colleague, "day1", recs=store.load(),
                            config=self.config)
        self.assertFalse(decision.eligible)

    def test_the_recheck_is_what_catches_it_not_the_earlier_plan(self):
        """A payload built from a plan made before the reply must still
        refuse. This is the guard, rather than the ordering of callers."""
        rec, recs = self.ready()
        item = {"record": rec, "contact": rec["contacts"][0],
                "step_key": "day1", "channel": "email",
                "push_id": "p1", "step": {"channel": "email"}}

        events.record(rec, events.REPLY_RECEIVED,
                      contact_key="acme-champ", channel="email",
                      at="2026-02-01T09:00:00Z",
                      provider_event_id="r-between-2")
        store.save([rec])
        item["record"] = store.get(rec["id"])

        with self.assertRaises(AssertionError):
            push.verify_before_payload(item, recs=store.load(),
                                       config=self.config)


class TestTamperingChangesNothing(GateTest):
    """Every one of these sets a stored field to the value that means yes."""

    def refuses(self, mutate, step="day1"):
        rec, recs = self.ready()
        mutate(rec)
        decision = self.decide(rec, recs, step=step)
        self.assertFalse(decision.eligible,
                         f"tampering worked: {decision['reasons']}")
        return decision

    def test_setting_sendable_true_on_a_paused_company(self):
        def tamper(rec):
            rec["paused"] = {"since": "x", "reason": "reply_received"}
            rec["contacts"][0]["sendable"] = True
            rec["contacts"][0]["verification"] = {"state": "verified"}
        self.refuses(tamper)

    def test_setting_sendable_true_on_an_unverified_contact(self):
        """The flag has no vote, and neither does the state. The evidence does."""
        from src import verification

        def tamper(rec):
            contact = rec["contacts"][0]
            evidence = [verification.result("contactout", verification.S_INVALID,
                                            contact["email"])]
            contact.pop("verification", None)   # a fixture, not a downgrade
            verification.apply(contact, verification.decide(evidence), evidence)
            contact["sendable"] = True
            contact["verification"]["state"] = verification.VERIFIED
            contact["verification"]["sendable"] = True
        decision = self.refuses(tamper)
        self.assertIn(E.BLOCKED_NOT_SENDABLE, decision["reasons"])

    def test_writing_a_verified_state_over_no_evidence_changes_nothing(self):
        from src import verification

        def tamper(rec):
            contact = rec["contacts"][0]
            contact.pop("verdict", None)
            contact.pop("reoon", None)
            contact["verification"] = {"state": verification.VERIFIED,
                                       "sendable": True, "evidence": [],
                                       "confirmation_count": 2}
            contact["sendable"] = True
        decision = self.refuses(tamper)
        self.assertIn(E.HELD_VERIFICATION_UNKNOWN, decision["reasons"])

    def test_setting_state_ready_on_a_dropped_record(self):
        def tamper(rec):
            rec["drop_reason"] = "out of geo"
            rec["state"] = "ready"
        self.refuses(tamper)

    def test_flipping_the_mx_verdict(self):
        rec, recs = self.ready(mx_hosts=PROOFPOINT)
        rec["contacts"][0]["mx"]["email_cadence_allowed"] = True
        rec["contacts"][0]["mx"]["status"] = mx.KNOWN_ALLOWED
        rec["contacts"][0]["mx"]["security_provider"] = None
        decision = self.decide(rec, recs)
        self.assertFalse(decision.eligible)
        self.assertIn(E.BLOCKED_MX, decision["reasons"])

    def test_forging_a_draft_approval(self):
        def tamper(rec):
            for steps in rec["cadence"].values():
                for step in steps.values():
                    step["approval"] = {"by": "me", "fingerprint": "made-up"}
                    step["body"] = "Completely different words now.\n"
        self.refuses(tamper)

    def test_forging_a_campaign_approval(self):
        rec, recs = self.ready()
        campaign = self.make_campaign(recs)
        campaign["approval"] = {"action": "approve", "by": "me",
                                "fingerprint": "made-up"}
        campaign["status"] = campaigns.APPROVED
        decision = self.decide(rec, recs, campaign=campaign)
        self.assertFalse(decision.eligible)
        self.assertIn(E.HELD_CAMPAIGN_STALE, decision["reasons"])

    def test_clearing_a_duplicate_flag_but_not_the_reason(self):
        """duplicate_of is the field that means it; clearing the reason alone
        changes nothing."""
        def tamper(rec):
            rec["contacts"][0]["duplicate_of"] = {"record_id": "x",
                                                  "contact_key": "y"}
            rec["contacts"][0]["duplicate_reason"] = None
        self.refuses(tamper)

    def test_a_tampered_body_in_the_payload_is_still_linted(self):
        """The gate checks the words being sent, not a rebuilt copy."""
        rec, recs = self.ready()
        evil = {"channel": "email", "day": 1, "generated": True,
                "subject": "hi", "body": "too short"}
        decision = E.decide(rec, rec["contacts"][0], "day1", recs=recs,
                            config=self.config, step=evil)
        self.assertFalse(decision.eligible)
        self.assertIn(E.BLOCKED_LINT, decision["reasons"])

    def test_an_unsupported_claim_in_the_payload_is_caught(self):
        rec, recs = self.ready()
        evil = dict(rec["cadence"]["acme-champ"]["day1"])
        evil["body"] = ("Hi Champ,\n\nCongratulations on your Series B and the "
                        "400 new hires across twelve countries. Most operations "
                        "leads we speak to lose the better part of a day every "
                        "month reconciling time before they can answer a "
                        "question anyone actually asked about it.\n\n"
                        "Is that roughly how it works with you today?\n")
        decision = E.decide(rec, rec["contacts"][0], "day1", recs=recs,
                            config=self.config, step=evil)
        self.assertFalse(decision.eligible)
        self.assertIn(E.BLOCKED_UNSUPPORTED_CLAIM, decision["reasons"])


class TestThePayloadBuildersRefuse(GateTest):
    """Defence in depth: the builder consults the gate, it does not re-derive."""

    def item(self, rec, step_key="day1", channel="email"):
        step = rec["cadence"]["acme-champ"][step_key]
        step.setdefault("channel", channel)
        step.setdefault("day", 1)
        return {"record": rec, "contact": rec["contacts"][0],
                "contact_key": "acme-champ", "step_key": step_key,
                "step": step, "channel": channel,
                "push_id": f"acme:acme-champ:{step_key}:{channel}"}

    def test_emailbison_refuses_a_paused_company(self):
        rec, recs = self.ready()
        rec["paused"] = {"since": "x", "reason": "reply_received"}
        with self.assertRaises(AssertionError):
            push.emailbison_rows([self.item(rec)])

    def test_emailbison_refuses_a_replied_company(self):
        rec, recs = self.ready()
        events.record(rec, events.REPLY_RECEIVED, contact_key="acme-champ")
        with self.assertRaises(AssertionError) as e:
            push.emailbison_rows([self.item(rec)])
        self.assertIn(E.BLOCKED_REPLIED, str(e.exception))

    def test_emailbison_refuses_a_duplicate(self):
        rec, recs = self.ready()
        rec["contacts"][0]["duplicate_of"] = {"record_id": "x", "contact_key": "y"}
        with self.assertRaises(AssertionError):
            push.emailbison_rows([self.item(rec)])

    def test_a_clean_item_still_builds(self):
        rec, recs = self.ready()
        rows = push.emailbison_rows([self.item(rec)])
        self.assertEqual(len(rows), 1)

    def test_the_builder_delegates_rather_than_re_deriving(self):
        import inspect
        source = inspect.getsource(push.verify_before_payload)
        self.assertIn("eligibility.decide", source)


class TestBatching(GateTest):
    def test_every_step_of_every_contact_is_decided(self):
        rec, recs = self.ready()
        rows = E.for_record(rec, recs=recs, config=self.config)
        self.assertGreaterEqual(len(rows), 5)
        for row in rows:
            self.assertIn(row["decision"]["verdict"], E.VERDICTS)

    def test_the_summary_counts_verdicts_and_reasons(self):
        rec, recs = self.ready(mx_hosts=PROOFPOINT)
        summary = E.summarise(E.for_record(rec, recs=recs, config=self.config))
        self.assertGreater(summary["counts"][E.SKIPPED], 0)
        self.assertIn(E.SKIPPED_EMAIL_CHANNEL, summary["reasons"])

    def test_require_raises_with_the_reasons(self):
        rec, recs = self.ready()
        rec["paused"] = {"since": "x", "reason": "reply_received"}
        with self.assertRaises(E.NotEligible) as e:
            E.require(rec, rec["contacts"][0], "day1", recs=recs,
                      config=self.config)
        self.assertIn(E.BLOCKED_COMPANY_PAUSED, str(e.exception))

    def test_every_reason_code_is_namespaced_by_its_verdict(self):
        for reason in E.REASONS:
            self.assertRegex(reason, r"^(blocked|held|skipped):")

    def test_every_reason_code_has_a_sentence_a_person_can_read(self):
        """A screen that prints a bare code is a screen printing its internals.

        The codes are vocabulary and the sentences are prose, kept apart on
        purpose - but a code with no sentence means somebody added a reason
        and left every reviewer to guess what it meant.
        """
        missing = [r for r in E.REASONS if r not in E.HUMAN]
        self.assertEqual(missing, [], f"reason codes with no sentence: {missing}")

    def test_no_sentence_describes_a_code_that_no_longer_exists(self):
        stale = [r for r in E.HUMAN if r not in E.REASONS]
        self.assertEqual(stale, [], f"sentences for removed codes: {stale}")

    def test_an_unknown_code_comes_back_rather_than_being_swallowed(self):
        """Hiding a code nobody can explain behind an empty cell keeps it a bug."""
        self.assertEqual(E.explain("blocked:something_new"),
                         "blocked:something_new")
        self.assertEqual(E.explain(None), "")

    def test_held_and_blocked_read_as_different_jobs(self):
        """A block needs a different contact; a hold needs one more thing to
        happen. A reviewer has to be able to tell which they are looking at."""
        self.assertIn("needs one more call",
                      E.explain(E.HELD_INSUFFICIENT_CONFIRMATIONS))
        self.assertIn("needs a better address",
                      E.explain(E.HELD_VERIFICATION_UNKNOWN))


if __name__ == "__main__":
    unittest.main()


class ATerminalStepIsNeverSentAgain(GateTest):
    """`stepstate` names three terminal states and only one of them was
    being read.

    `push.already_pushed` and `cadence.status_for` both spelled the rule as
    `== "pushed"`, which is the only terminal state anything currently
    writes - so a step recorded as `confirmed` (the provider said it went)
    or `cancelled` (a human or a reply ended it) answered "not sent yet"
    and could go out a second time.

    Nothing writes those two today. `DATABASE-MIGRATION.md` names
    `stepstate.STATES` as the vocabulary of the status column, and
    `confirmed` is what a provider callback would naturally write, so the
    first thing to produce one would have found this instead of these
    tests.
    """
    from src import stepstate as _stepstate

    def mark(self, rec, state):
        rec.setdefault("cadence", {}).setdefault(
            "acme-champ", {}).setdefault("day1", {})["status"] = state
        store.save([rec] + [r for r in store.load() if r["id"] != rec["id"]])
        return store.load()

    def test_every_terminal_state_blocks_the_step(self):
        from src import stepstate

        for state in stepstate.TERMINAL:
            rec, recs = self.ready()
            recs = self.mark(rec, state)
            decision = self.decide(rec, recs)
            self.assertEqual(decision["verdict"], E.BLOCKED, state)
            self.assertIn(E.BLOCKED_ALREADY_PUSHED, decision["reasons"], state)

    def test_a_non_terminal_state_does_not(self):
        """The other half: this must refuse terminal states, not every
        state that is not `eligible`."""
        from src import stepstate

        for state in (stepstate.HELD, stepstate.BLOCKED, stepstate.PENDING):
            rec, recs = self.ready()
            recs = self.mark(rec, state)
            self.assertNotIn(E.BLOCKED_ALREADY_PUSHED,
                             self.decide(rec, recs)["reasons"], state)

    def test_the_rule_is_read_from_stepstate_rather_than_spelled_out(self):
        """A second copy of "which states are final" is a second thing to
        get wrong, and the one that gets forgotten is the one guarding the
        expensive mistake.

        Asserted structurally - both modules ask `stepstate` - rather than
        by searching the source for the old literal. The first version did
        search, and failed on the docstring that quotes the literal to
        explain what it replaced: a test that reads prose is a test that
        fails when somebody writes some.
        """
        import ast
        import inspect

        from src import cadence, push

        for module in (push, cadence):
            calls = {
                node.func.value.id + "." + node.func.attr
                for node in ast.walk(ast.parse(inspect.getsource(module)))
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)}
            self.assertIn("stepstate.is_terminal", calls, module.__name__)

    def test_a_rebuild_does_not_move_a_terminal_step(self):
        from src import cadence, stepstate

        for state in stepstate.TERMINAL:
            rec, recs = self.ready()
            recs = self.mark(rec, state)
            timeline = cadence.build(rec, self.config, recs=recs)
            step = timeline["contacts"]["acme-champ"]["day1"]
            self.assertEqual(step["status"], state)

    def test_the_skip_list_names_the_state_rather_than_guessing(self):
        """"cancelled" and "already pushed" are different things to
        somebody reading a skip list."""
        from src import push, stepstate

        rec, recs = self.ready()
        recs = self.mark(rec, stepstate.CANCELLED)
        _, skipped = push.collect(recs, day=21, client=CLIENT)
        reasons = [row["why"] for row in skipped
                   if row.get("step") == "day1"]
        self.assertTrue(reasons)
        self.assertIn("cancelled", " ".join(reasons))
