#!/usr/bin/env python3
"""The offer's approved ladder is a GATE, and a sequence that breaks it is
REFUSED.

`TASK-425` acceptance criterion 3, operator, 2026-09-27:

    Offer sequencing as step objectives, enforced by `sequencegate`, WITH A
    NEGATIVE TEST. A: margin visibility -> quote versus burn -> resource
    decisions that move margin -> Report Intelligence as mechanism ONLY if it
    strengthens the angle -> reframe and close. B: project visibility -> time ->
    resourcing -> AI Time Tracking as mechanism ONLY if it strengthens the angle
    -> one operational view.

WHAT WAS THERE BEFORE. `messaging_rules` in
`config/clients/productive-offers.yaml` recorded `enforced_by: sequencegate
checks step_objectives` on one line and `enforcement_status:
DATA_ONLY_NOT_YET_ENFORCED` on the next. A rule written down and read by nothing,
which is this repository's signature defect appearing in its own configuration.

WHAT EACH TEST HERE IS FOR, and none of them reads the source:

  - the ladder in order PASSES, which is the control. Without it every negative
    test below would be satisfied by a check that refuses everything, and this
    repository has shipped one of those;
  - a ROTATED ladder is REFUSED, and the refusal names the check, the rung and
    the step - the negative test criterion 3 asks for;
  - two swapped steps are refused, in three different permutations, so the
    refusal is not a property of one arrangement;
  - the ladder is read from the OFFER RECORD, so a run against Offer B is
    checked against Offer B's spine and not Offer A's;
  - an absent offer is reported as UNCHECKED and never as a pass, which is the
    difference between "the ladder holds" and "nobody looked";
  - at most one AI capability per message, and NONE is valid: `ai_required:
    false` is in the same block and a message with no AI capability must not be
    penalised;
  - an AI capability at a rung whose objective does not name one is refused,
    which is the structural form of the forbidden direction the library records;
  - and the whole thing runs through `bisonfactory.stage(live=False)` as well,
    because a check proved only by calling it directly is a check with no
    production consumer - `tests/test_a_dry_run_runs_the_sequence_gate.py` is the
    module that made that path reachable at all.

WHY THE COPY HERE IS WRITTEN AND NOT GENERATED. The gate is what is under test,
and a model's output is not a fixture: it varies between runs, and a test whose
input varies cannot distinguish a gate that changed from a model that did. The
sentences below are the shortest thing that carries each rung's own vocabulary.
"""
import unittest
from unittest import mock

from src import (approval, bisonfactory, cadence, campaigns, offers, providers,
                 sequencegate, store, workspaces)
from tests.base import QueueTest
from tests import task425fixture as fixture

#: THE LADDER, IN ORDER, one short paragraph per rung of Offer A. Each carries
#: the words of its own objective and as few of any other rung's as the sense
#: allows - which is exactly what the gate measures and what the writer prompt
#: now asks for.
IN_ORDER = {
    "em1": ("Most agencies your size only see project margin once a job has "
            "finished. Margin visibility while the work is still running is a "
            "different question, and it is the one this note is about."),
    "em2": ("The gap I keep hearing about is the distance between the quote "
            "and the burn. One number is agreed at the start and another one "
            "shows up at the end, and finance and delivery read different "
            "sheets."),
    "em3": ("The decisions that actually move margin are resourcing "
            "decisions. Who is booked on which piece of work next week, and "
            "what happens when a scope shifts halfway through a sprint."),
    "em4": ("A plain language answer about your own data, already "
            "interpreted, rather than a report somebody has to build first."),
    "em5": ("If the reframe is wrong that is worth knowing. Happy to close "
            "this thread out, and to pick it up later if the timing changes."),
}

ORDER = ("em1", "em2", "em3", "em4", "em5")

#: The client's own five email days, and the waits they imply. Pinned here
#: rather than loaded so that editing the client's LinkedIn fallbacks cannot
#: break a test about the offer ladder.
EMAIL_DAYS = (1, 4, 8, 12, 21)
EMAIL_WAITS = (3, 4, 4, 9, 1)


def rotated(bodies):
    """Every rung carrying the NEXT rung's words. A ladder out of order."""
    return {key: bodies[ORDER[(i + 1) % len(ORDER)]]
            for i, key in enumerate(ORDER)}


def swapped(bodies, a, b):
    out = dict(bodies)
    out[a], out[b] = bodies[b], bodies[a]
    return out


def subjects_of(bodies):
    """One distinct subject per step, so `no_repetition` is not what fires."""
    return {key: "subject for %s" % key for key in bodies}


class TheLadderIsAGate(unittest.TestCase):
    """The gate, asked directly. No store, no provider, no model."""

    def setUp(self):
        self.library = offers.load()
        self.rules = offers.messaging_rules()
        self.offer_a = self.library["OFFER-A-ECONOMIC-BUYER"]
        self.offer_b = self.library["OFFER-B-OPERATIONS"]

    def check(self, bodies, offer=None, **kw):
        return sequencegate.check(
            {"emails": bodies, "subjects": subjects_of(bodies)},
            qualification="qualified",
            offer=self.offer_a if offer is None else offer,
            messaging_rules=self.rules, **kw)

    def ladder_failures(self, result):
        return [f for f in result["failures"]
                if f["check"] == "step_objectives"]

    # ------------------------------------------------------------- the control

    def test_the_ladder_in_order_raises_no_ladder_failure(self):
        """WITHOUT THIS EVERY TEST BELOW PROVES NOTHING.

        A check that refused every sequence would satisfy all of them. The same
        five paragraphs, in the order the operator approved, must raise no
        `step_objectives` failure at all.
        """
        self.assertEqual([], self.ladder_failures(self.check(IN_ORDER)))

    def test_a_theme_word_in_a_later_step_is_not_a_ladder_failure(self):
        """The failure mode the first version of this check had.

        Rung 1 of Offer A is "margin visibility", which is the theme of the
        whole offer, so every step of a margin campaign legitimately touches it.
        A close that mentions it is still a close.
        """
        bodies = dict(IN_ORDER)
        bodies["em5"] = (bodies["em5"] +
                         " Margin visibility may already be handled here.")
        self.assertEqual([], self.ladder_failures(self.check(bodies)))

    # -------------------------------------------------------- the negative test

    def test_a_rotated_ladder_is_refused(self):
        """Criterion 3's negative test, in its strongest form.

        Every rung carries the next rung's words, so no rung's vocabulary is at
        its own step. The refusal has to be ATTRIBUTABLE: "it failed" would be
        satisfied by the qualification check or the claim check, neither of which
        is evidence that sequencing is enforced. So what is asserted is the check
        by name, and that the failures name steps.
        """
        result = self.check(rotated(IN_ORDER))
        failures = self.ladder_failures(result)
        self.assertFalse(result["passed"])
        self.assertTrue(failures, "a rotated ladder raised no step_objectives "
                                  "failure, so the ladder is not enforced")
        for failure in failures:
            self.assertIn(failure["step"], ORDER)
            self.assertTrue(failure["why"])

    def test_every_swap_of_two_rungs_is_refused(self):
        """Three permutations, so the refusal is not a property of one.

        A single arrangement passing would be a coincidence; three failing for
        their own named reasons is the check working.
        """
        for a, b in (("em1", "em3"), ("em2", "em5"), ("em2", "em3")):
            with self.subTest(swap=(a, b)):
                failures = self.ladder_failures(
                    self.check(swapped(IN_ORDER, a, b)))
                self.assertTrue(
                    failures,
                    "swapping %s and %s raised no ladder failure" % (a, b))

    def test_the_refusal_names_the_rung_and_its_objective(self):
        """An operator has to know WHICH message to rewrite.

        `sequencegate` exists because "regenerate everything" hides which
        message was wrong. So the failure carries the rung number and the
        operator's own words for it, not a rule name.
        """
        failures = self.ladder_failures(self.check(rotated(IN_ORDER)))
        joined = " ".join(f["why"] for f in failures)
        self.assertIn("margin visibility", joined)
        self.assertIn("rung", joined)

    # ---------------------------------------------------- the offer is the ladder

    def test_offer_b_is_checked_against_offer_bs_own_spine(self):
        """The ladder comes from the OFFER RECORD, not from this module.

        Offer A's five paragraphs judged against Offer B's spine must fail:
        Offer B's rungs are project visibility, time, resourcing, AI Time
        Tracking and one operational view, and Offer A's copy pursues none of
        them in that order. If this passed, the gate would be reading a ladder
        that is not the offer's.
        """
        result = self.check(IN_ORDER, offer=self.offer_b)
        self.assertTrue(self.ladder_failures(result))

    def test_an_absent_offer_is_reported_as_unchecked_and_never_as_a_pass(self):
        """The difference between "the ladder holds" and "nobody looked".

        A caller that hands over no offer has not had its sequencing checked,
        and criterion 3 would be decorative on every unwired caller if that
        rendered as a pass.
        """
        result = sequencegate.check(
            {"emails": IN_ORDER, "subjects": subjects_of(IN_ORDER)},
            qualification="qualified")
        self.assertEqual([], self.ladder_failures(result))
        warnings = [w for w in result["warnings"]
                    if w["check"] == "step_objectives"]
        self.assertTrue(warnings, "no offer was supplied and the gate said "
                                  "nothing about it")
        self.assertIn("NOT checked", " ".join(w["why"] for w in warnings))

    # --------------------------------------------------------------- AI capability

    def test_a_message_with_no_ai_capability_is_not_penalised(self):
        """`ai_required: false`, and this is the half a strict reading breaks.

        None of the five paragraphs above names an AI capability, and the
        operator's rule is that none is ever forced. A gate that required one at
        the mechanism rung would be the "AI feature first" direction the same
        block forbids, enforced by us.
        """
        result = self.check(IN_ORDER)
        self.assertEqual([], [f for f in result["failures"]
                              if f["check"].startswith("ai_")])

    def test_two_ai_capabilities_in_one_message_are_refused(self):
        """`max_ai_capabilities_per_message: 1`, read from the library."""
        bodies = dict(IN_ORDER)
        bodies["em4"] = ("Report Intelligence answers a question about the "
                         "data, and Project Summary recaps a project without "
                         "anyone digging through updates.")
        result = self.check(bodies)
        named = [f for f in result["failures"]
                 if f["check"] == "ai_one_per_message"]
        self.assertTrue(named)
        self.assertEqual("em4", named[0]["step"])

    def test_an_ai_capability_at_a_rung_that_does_not_name_one_is_refused(self):
        """The forbidden direction, made structural.

        The library records it as "ai feature first, then invent a problem
        around it". Rung 1 states the problem and rung 4 carries the mechanism,
        so an AI feature in rung 1 IS leading with the feature.
        """
        bodies = dict(IN_ORDER)
        bodies["em1"] = ("Report Intelligence gives margin visibility in plain "
                         "language while a project is still running, which is "
                         "a different question from seeing it afterwards.")
        result = self.check(bodies)
        named = [f for f in result["failures"]
                 if f["check"] == "ai_is_supporting"]
        self.assertTrue(named)
        self.assertEqual("em1", named[0]["step"])


class AProviderRequestWasMade(AssertionError):
    """The transport was reached. On a dry run that is always a failure."""


class TheLadderIsEnforcedOnTheProductionPath(QueueTest):
    """The same gate, through `bisonfactory.stage(live=False)`.

    A CHECK PROVED ONLY BY CALLING IT DIRECTLY IS A CHECK WITH NO PRODUCTION
    CONSUMER, which is the defect `CLAUDE.md` names as this repository's
    recurring one. So the ladder is broken in a record's STORED, APPROVED copy
    and the production staging entrypoint is asked to stage it.

    The real `bison` module stays in place and the transport is booby-trapped, so
    "nothing reached a provider" is a claim about the production path rather than
    about a fake. The trap is fired on purpose in its own test, because
    `assertEqual([], requests)` is satisfied just as well by a trap that was
    never installed.
    """

    APPROVER = "ladder-fixture@example.test"

    def setUp(self):
        super().setUp()
        self.requests = []

        def refuse_every_request(method, url, headers, body, timeout):
            self.requests.append((method, url))
            raise AProviderRequestWasMade(
                "a provider request was made: %s %s" % (method, url))

        providers.set_transport(refuse_every_request)
        self.addCleanup(providers.reset_transport)

        # `sending.live` ON for the tenant, deliberately: if the killswitch were
        # what stopped this run, these tests would pass with the ladder inert.
        workspace = workspaces.new_workspace("productive", "Productive",
                                             client="productive")
        workspace["settings"] = {"policy": {"sending.live": "on"}}
        workspaces.save([workspace])

        self.config = self.five_email_config()
        row = campaigns.new_campaign(fixture.CAMPAIGN_ID, "productive",
                                     "ladder gate test")
        # DECLARED ON THE CAMPAIGN, not inherited. `_plan` refuses a campaign
        # with no `cadence_steps`, and the DAYS have to reproduce the declared
        # waits: `sequenceplan` matches each step's `wait_in_days` to the gap
        # between its cadence day and the next, keyed by step, and refuses a
        # mismatch. These are the client's own five email days.
        row["cadence_steps"] = [
            {"key": key, "day": day, "channel": "email", "generated": True}
            for key, day in zip(ORDER, EMAIL_DAYS)]
        row["record_ids"] = [fixture.RECORD_ID]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        campaigns.save([row])

    @staticmethod
    def five_email_config():
        """The five threaded email steps, pinned rather than loaded.

        Loading `config/clients/productive.yaml` would make this test fail when
        somebody edits the client's LinkedIn fallbacks, which it is not about.
        The shape is the client's: one subject variable, `thread_reply` on every
        follow-up.
        """
        steps = {}
        for position, key in enumerate(ORDER, start=1):
            steps[key] = {"order": position, "subject": "{SUBJECT_1}",
                          "body": "<p>{BODY_%d}</p>" % position,
                          "wait_in_days": EMAIL_WAITS[position - 1]}
        return {
            "name": "productive",
            "product": {"name": "Productive",
                        "capabilities": {"profitability":
                                         "margin per project while it is "
                                         "running, not after it closes"},
                        "capability_by_persona": {"economic_buyer":
                                                  ["profitability"]}},
            "email_sequence": {"title": "ladder test", "steps": steps,
                               "thread_reply_pattern": [False, True, True,
                                                        True, True]},
            "sending_window": {"days": ["monday"], "start": "09:00",
                               "end": "17:00", "timezone": "Europe/Zagreb"},
            "providers": {"emailbison": {"workspace": 10}},
        }

    def given(self, bodies):
        """One record whose approved copy is exactly these five bodies."""
        rec = fixture.record()
        rec["persona"] = fixture.PERSONA_ECONOMIC_BUYER
        rec["contacts"] = rec["contacts"][:1]
        contact_key = rec["contacts"][0]["key"]
        steps = {}
        for key in ORDER:
            step = {"channel": "email", "generated": True,
                    "subject": "subject for %s" % key,
                    "body": bodies[key]}
            step["approval"] = {"by": self.APPROVER,
                                "at": "2026-09-28T00:00:00Z",
                                "fingerprint": approval.fingerprint(step)}
            steps[key] = step
        rec["cadence"] = {contact_key: steps}
        store.save([rec])
        return rec

    def stage(self):
        return bisonfactory.stage(fixture.CAMPAIGN_ID, config=self.config,
                                  live=False)

    def assertNothingReachedTheProvider(self):
        self.assertEqual([], self.requests,
                         "a dry run reached the provider transport")

    def test_the_booby_trap_actually_fires(self):
        """Every zero-write claim in this class rests on this one."""
        with self.assertRaises(AProviderRequestWasMade):
            providers.request("GET", "http://example.invalid/armed",
                              headers={}, body=None, timeout=1)
        self.assertEqual([("GET", "http://example.invalid/armed")],
                         self.requests)
        self.requests.clear()

    def test_the_ladder_in_order_reaches_the_dry_run_projection(self):
        """THE CONTROL. Without it the refusal below proves nothing.

        A `stage()` that refused everything would satisfy the negative test
        perfectly, and the gate's verdict has to be ON the report with the lead
        counted: present with `leads: []` is a gate asked about nobody.
        """
        self.given(IN_ORDER)
        report = self.stage()
        self.assertFalse(report["live"])
        self.assertIn("sequencegate", report)
        verdict = report["sequencegate"]
        self.assertTrue(verdict["passed"])
        self.assertEqual(1, len(verdict["leads"]),
                         "the gate was asked about no lead, which is not a pass")
        self.assertEqual("OFFER-A-ECONOMIC-BUYER", verdict["leads"][0]["offer"])
        self.assertEqual(5, len(report["plan"]["provider_sequence"]))
        self.assertNothingReachedTheProvider()

    def test_a_rotated_ladder_is_refused_on_a_dry_run(self):
        """Criterion 3's negative test, on the production path.

        The refusal names the gate, the check and a step, because a refusal that
        says only "it failed" would be satisfied by the cadence guard, the
        qualification check or the copy lint, none of which is evidence that
        sequencing is enforced.
        """
        self.given(rotated(IN_ORDER))
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            self.stage()
        message = str(caught.exception)
        self.assertIn("sequence-level gate", message)
        self.assertIn("step_objectives", message)
        self.assertTrue(any(key in message for key in ORDER),
                        "the refusal named no step, so an operator does not "
                        "know which message to rewrite")
        self.assertNothingReachedTheProvider()

    def test_the_gate_is_what_refuses_and_not_a_later_guard(self):
        """Bypass the gate and the same broken campaign reaches the projection.

        Asserting on the message is not enough: the message is built from the
        gate's own report, so a gate refusing for the wrong reason still names
        itself. What is measured is an EFFECT.
        """
        self.given(rotated(IN_ORDER))
        with self.assertRaises(bisonfactory.FactoryRefused):
            self.stage()

        def passes_everything(sequence, **kwargs):
            return {"passed": True, "checks": [], "failures": [],
                    "warnings": []}

        with mock.patch.object(sequencegate, "check", passes_everything):
            report = self.stage()
        self.assertEqual(5, len(report["plan"]["provider_sequence"]),
                         "with the sequence gate bypassed the run still did "
                         "not reach the projection, so the gate is not what "
                         "refuses and this test proves nothing about it")
        self.assertNothingReachedTheProvider()

    def test_the_offer_reaches_the_gate_from_the_contacts_persona(self):
        """The wiring, asserted by EFFECT rather than by reading the call.

        A contact whose persona selects Offer B is checked against Offer B's
        spine, so the identical copy that passes for the economic buyer is
        refused for the operations persona. If the offer were not reaching the
        gate, both would pass.
        """
        rec = self.given(IN_ORDER)
        rec["persona"] = fixture.PERSONA_OPERATIONS
        rec["contacts"][0]["persona"] = fixture.PERSONA_OPERATIONS
        store.save([rec])
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            self.stage()
        self.assertIn("step_objectives", str(caught.exception))
        self.assertNothingReachedTheProvider()


if __name__ == "__main__":
    unittest.main()
