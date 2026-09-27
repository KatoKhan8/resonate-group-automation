#!/usr/bin/env python3
"""`bisonfactory.stage` hands the sequence gate every input it asks for.

TASK-426. `6fa49014` wired `sequencegate.check` into `bisonfactory` and called
it with ONE of its five inputs. The four it left out were `qualification`,
`facts`, `capability` and `batch_capabilities`, and the first of those is fatal
by design: the gate refuses when no qualification is supplied, because "absence
is refused rather than read as qualified". So from 2026-09-26 15:27 every
`stage()` refused for every input, no campaign could be staged, and five safety
guards downstream of the gate - the killswitch among them - could not be
reached by the tests that exist to prove them.

WHAT THIS MODULE PINS, and none of it reads the source.

  - a qualified lead whose account's own research supports its opener stages,
    through the real entrypoint, and the gate's verdict is on the report;
  - a company this system marked `rejected` is refused ON the `qualified`
    check and nothing reaches the provider. That is what makes the threaded
    qualification load-bearing rather than decorative: it is not enough for an
    argument to be passed, a real value has to be able to refuse;
  - a company nobody ever qualified is refused too, on the same check.
    Absence stays a refusal. Asserted separately so this fix cannot have been
    achieved by weakening the check that was blocking it;
  - the facts the gate traces claims against are THIS account's, read off the
    record. Take the record's research away and the same copy is refused on
    `claims_supported`;
  - the capability the client configured for this contact's persona reaches
    the gate, observed by the warning the gate can only raise if it was handed
    one, and a persona the client configured nothing for stays None rather
    than becoming a guess;
  - every lead is checked, not only the first;
  - the gate's own repetition check actually fires on this path now.
"""
import unittest

from src import bisonfactory, cadence, campaigns, icp, store, workspaces
from tests import packfixture
from tests.base import QueueTest
from tests.test_staging_a_campaign_twice_builds_one import (
    CID, COMPANY, CONFIG, DOMAIN, FakeBison, record)
from tests.test_staging_refuses_colliding_contacts import patch_collision_empty


def _verdict(status):
    return {"verdict": {"icp_status": status}}


#: A client file whose product block names a capability per persona. `CONFIG`
#: carries no `product` block at all, which is the case where
#: `cadence.product_words` resolves nothing - so a test about the capability
#: reaching the gate needs a config that actually configures one.
CAPABILITY_CONFIG = dict(
    CONFIG,
    product={"name": "Productive",
             "capabilities": {"resourcing": "who is booked on what next week"},
             "capability_by_persona": {"champion": ["resourcing"]}})


class _StagingCase(QueueTest):
    """A live workspace, a fake provider, and no collision estate."""

    def setUp(self):
        super().setUp()
        self.bison = FakeBison()
        self.bison.DAYS = FakeBison.DAYS
        self._real = bisonfactory.bison
        bisonfactory.bison = self.bison
        self.addCleanup(setattr, bisonfactory, "bison", self._real)
        patch_collision_empty(self)

        ws = workspaces.new_workspace("productive", "Productive",
                                      client="productive")
        ws["settings"] = {"policy": {"sending.live": "on"}}
        workspaces.save([ws])

    def _campaign(self, record_ids, config=None):
        row = campaigns.new_campaign(CID, "productive", "Gate input test")
        row["cadence_steps"] = [dict(s) for s in cadence.steps_for(
            None, config=config or CONFIG)]
        row["record_ids"] = list(record_ids)
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        campaigns.save([row])
        return row

    def _nothing_reached_the_provider(self):
        self.assertEqual(self.bison.created_campaigns, 0,
                         "a campaign was created before the gate refused")
        self.assertEqual(self.bison.created_leads, 0,
                         "a lead was created before the gate refused")


class StagingHandsTheGateItsInputs(_StagingCase):

    # ------------------------------------------------------------- positive

    def test_a_qualified_lead_with_its_own_research_stages(self):
        """The whole point: `stage()` can succeed again.

        The gate's verdict per lead is recorded on the report, so this asserts
        the gate RAN and passed rather than that nothing happened.
        """
        store.save([record("rec-1", "one@example.com", "Ada")])
        self._campaign(["rec-1"])
        report = bisonfactory.stage(CID, config=CONFIG, live=True)
        self.assertTrue(report["sequencegate"]["passed"])
        self.assertEqual([entry["lead"]
                          for entry in report["sequencegate"]["leads"]],
                         ["rec-1/rec-1-c1"])
        self.assertEqual(self.bison.created_leads, 1)

    # ---------------------------------------------------- the qualification

    def test_a_rejected_company_is_refused_on_the_qualified_check(self):
        """A real verdict has to be able to refuse or the input is decorative.

        This system's own word for a company it assessed and turned down is
        `rejected`, and a sequence for one should not exist.
        """
        rec = record("rec-1", "one@example.com", "Ada")
        rec["qualification"] = _verdict(icp.REJECTED)
        store.save([rec])
        self._campaign(["rec-1"])
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            bisonfactory.stage(CID, config=CONFIG, live=True)
        self.assertIn("qualified", str(caught.exception))
        self.assertIn("rejected", str(caught.exception))
        self._nothing_reached_the_provider()

    def test_a_company_held_for_review_is_refused_too(self):
        """`review` is a person's queue, not permission to write."""
        rec = record("rec-1", "one@example.com", "Ada")
        rec["qualification"] = _verdict(icp.REVIEW)
        store.save([rec])
        self._campaign(["rec-1"])
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            bisonfactory.stage(CID, config=CONFIG, live=True)
        self.assertIn("qualified", str(caught.exception))
        self._nothing_reached_the_provider()

    def test_a_company_nobody_qualified_is_still_refused(self):
        """Absence is refused rather than read as qualified.

        Asserted separately from the rejected case on purpose: the fix for
        TASK-426 must not have been achieved by letting an absent
        qualification through, and a record with no `qualification` block at
        all is the shape that would prove it had been.
        """
        rec = record("rec-1", "one@example.com", "Ada")
        rec.pop("qualification")
        store.save([rec])
        self._campaign(["rec-1"])
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            bisonfactory.stage(CID, config=CONFIG, live=True)
        self.assertIn("qualified", str(caught.exception))
        self._nothing_reached_the_provider()

    def test_the_plan_carries_each_leads_own_verdict(self):
        """Two companies, two verdicts, and the plan keeps them apart."""
        first = record("rec-1", "one@example.com", "Ada")
        second = record("rec-2", "two@example.com", "Grace")
        second["qualification"] = _verdict(icp.REJECTED)
        store.save([first, second])
        row = self._campaign(["rec-1", "rec-2"])
        plan = bisonfactory._plan(row, store.load(), CONFIG)
        by_lead = {lead["record_id"]: lead["qualification"]
                   for lead in plan["leads"]}
        self.assertEqual(by_lead["rec-1"], "qualified")
        self.assertEqual(by_lead["rec-2"], "rejected")

    def test_a_refusal_names_the_lead_and_not_only_the_first_one(self):
        """Every lead is checked. Lead one being fine proves nothing about two.

        The call site checked the first lead and staged the rest, on the
        grounds that the sequence is campaign-level. It is not: every lead
        carries its own words, its own account's facts and its own company's
        verdict.
        """
        first = record("rec-1", "one@example.com", "Ada")
        second = record("rec-2", "two@example.com", "Grace")
        second["qualification"] = _verdict(icp.REJECTED)
        store.save([first, second])
        self._campaign(["rec-1", "rec-2"])
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            bisonfactory.stage(CID, config=CONFIG, live=True)
        message = str(caught.exception)
        self.assertIn("rec-2/rec-2-c1", message)
        self.assertNotIn("rec-1/rec-1-c1", message,
                         "the lead that passed was named in the refusal")
        self._nothing_reached_the_provider()

    # ------------------------------------------------------------ the facts

    #: A capitalised pair is what `copylint.specifics_in` extracts, so a claim
    #: naming one is a claim that has to trace to a fact. The default fixture
    #: opener deliberately carries no figure, date or capitalised pair - it was
    #: written to pass the lint's other rules - so a test about the FACTS has to
    #: give the copy something checkable to trace.
    NAMED_TEAM = "Delivery Ops"

    def _record_making_a_checkable_claim(self):
        from src import approval as _approval

        rec = record("rec-1", "one@example.com", "Ada")
        key = "rec-1-c1"
        stored = dict(rec["cadence"][key]["day1"])
        stored.pop("approval", None)
        stored["body"] = stored["body"].replace(
            "</p>", " Your %s team is why I am writing.</p>" % self.NAMED_TEAM)
        stored["approval"] = {"by": "operator", "at": "2026-09-13T00:00:00Z",
                              "fingerprint": _approval.fingerprint(stored)}
        rec["cadence"][key]["day1"] = stored
        rec["research"] = [dict(
            packfixture.own_fact("rec-1", DOMAIN, COMPANY),
            fact="%s runs delivery scheduling for independent clinics with a "
                 "%s team." % (COMPANY, self.NAMED_TEAM))]
        return rec

    def test_the_gate_traces_claims_against_the_accounts_own_research(self):
        """Take the research away and the same copy is refused.

        `_refuse_sequence_gate` is asked directly, with the record's own fact
        present and then with its research removed, so the only thing that
        changes between a pass and a `claims_supported` refusal is what the
        record carries. The batch copy lint is not in the way here, which is
        what makes this a test of the FACTS the gate is handed rather than of
        the lint.
        """
        store.save([self._record_making_a_checkable_claim()])
        row = self._campaign(["rec-1"])
        recs = store.load()
        plan = bisonfactory._plan(row, recs, CONFIG)

        report = {}
        bisonfactory._refuse_sequence_gate(plan, recs, report)
        self.assertTrue(report["sequencegate"]["passed"],
                        report["sequencegate"]["leads"])

        stripped = [dict(r, research=[]) for r in recs]
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            bisonfactory._refuse_sequence_gate(plan, stripped, {})
        self.assertIn("claims_supported", str(caught.exception))

    # ------------------------------------------------------- the capability

    def test_the_configured_capability_reaches_the_gate(self):
        """Observed by the warning the gate can only raise if it was handed one.

        `sequencegate` warns when the chosen capability appears nowhere in the
        emails. The fixture's copy is about project margin and never mentions
        who is booked next week, so a gate given this client's capability says
        so - and a gate given nothing cannot.
        """
        rec = record("rec-1", "one@example.com", "Ada")
        rec["contacts"][0]["persona"] = "champion"
        store.save([rec])
        row = self._campaign(["rec-1"], config=CAPABILITY_CONFIG)
        recs = store.load()
        plan = bisonfactory._plan(row, recs, CAPABILITY_CONFIG)
        self.assertEqual(plan["leads"][0]["capability"],
                         "who is booked on what next week")

        report = {}
        bisonfactory._refuse_sequence_gate(plan, recs, report)
        warnings = report["sequencegate"]["leads"][0]["warnings"]
        self.assertTrue([w for w in warnings
                         if w["check"] == "capability_matches"
                         and w["step"] == "em1"],
                        "the gate raised no capability warning, so it was "
                        "given no capability")

    def test_an_unconfigured_persona_gets_no_invented_capability(self):
        """None, not a guess. The gate skips the check rather than matching
        against something nobody chose."""
        rec = record("rec-1", "one@example.com", "Ada")
        rec["contacts"][0]["persona"] = "nobody_configured_this"
        store.save([rec])
        row = self._campaign(["rec-1"], config=CAPABILITY_CONFIG)
        plan = bisonfactory._plan(row, store.load(), CAPABILITY_CONFIG)
        self.assertIsNone(plan["leads"][0]["capability"])

    # ------------------------------------------------ the batch-level check

    def test_the_unchecked_batch_question_is_reported_not_hidden(self):
        """`batch_capabilities` is deliberately not supplied, and says so.

        There is no copy-engine stage D on this path: the capability is a
        deterministic function of the contact's persona and the client's file,
        so a single-persona cohort legitimately shares one capability and
        handing the list over would refuse five real campaigns for a defect
        they do not have. The gate's own answer for a caller that cannot answer
        the question is a warning, and this asserts the warning is present
        rather than the silence that would read as "stage D is choosing".
        """
        store.save([record("rec-1", "one@example.com", "Ada")])
        row = self._campaign(["rec-1"])
        recs = store.load()
        report = {}
        bisonfactory._refuse_sequence_gate(
            bisonfactory._plan(row, recs, CONFIG), recs, report)
        warnings = report["sequencegate"]["leads"][0]["warnings"]
        self.assertTrue([w for w in warnings
                         if w["check"] == "capability_matches"
                         and w["step"] == "batch"])


class TheGatesOwnChecksNowFireOnThisPath(_StagingCase):
    """The wiring existed to deliver these, and none of them could run."""

    #: Two email steps keyed the way `sequencegate`'s repetition check reads
    #: them. It compares `em1`..`em5` only, so a cadence keyed `day1`/`day3`
    #: is invisible to it - which is why this case declares its own cadence
    #: rather than reusing the single-step `CONFIG` shape.
    TWO_STEPS = ({"key": "em1", "day": 1, "channel": "email",
                  "generated": True},
                 {"key": "em2", "day": 4, "channel": "email",
                  "generated": True})

    def _two_step_config(self):
        return dict(CONFIG, email_sequence={
            "title": "two steps",
            "steps": {"em1": {"order": 1, "subject": "{SUBJECT_1}",
                              "body": "<p>{BODY_1}</p>", "wait_in_days": 3},
                      "em2": {"order": 2, "subject": "{SUBJECT_1}",
                              "body": "<p>{BODY_2}</p>", "wait_in_days": 4}},
            "thread_reply_pattern": [False, True]})

    def _two_step_record(self, em2_body):
        from src import approval as _approval

        rec = record("rec-1", "one@example.com", "Ada")
        key = "rec-1-c1"
        opener = {"channel": "email", "subject": "how margin shows up",
                  "body": packfixture.html_opener("Ada", COMPANY)}
        opener["approval"] = {"by": "operator", "at": "2026-09-13T00:00:00Z",
                              "fingerprint": _approval.fingerprint(opener)}
        second = {"channel": "email", "subject": "a follow-up",
                  "body": em2_body}
        second["approval"] = {"by": "operator", "at": "2026-09-13T00:00:00Z",
                              "fingerprint": _approval.fingerprint(second)}
        rec["cadence"] = {key: {"em1": opener, "em2": second}}
        return rec

    def _plan_for(self, em2_body):
        store.save([self._two_step_record(em2_body)])
        config = self._two_step_config()
        row = campaigns.new_campaign(CID, "productive", "Repetition test")
        row["cadence_steps"] = [dict(s) for s in self.TWO_STEPS]
        row["record_ids"] = ["rec-1"]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        campaigns.save([row])
        recs = store.load()
        return bisonfactory._plan(row, recs, config), recs

    def test_a_follow_up_that_repeats_the_opener_is_refused_by_step(self):
        """The repetition check, on the real staging path, naming the step.

        This is the failure the wiring existed to catch - five emails making
        one argument - and it could not fire while the gate refused on
        `qualified` first.
        """
        plan, recs = self._plan_for(packfixture.html_opener("Ada", COMPANY))
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            bisonfactory._refuse_sequence_gate(plan, recs, {})
        message = str(caught.exception)
        self.assertIn("followup_adds_value", message)
        self.assertIn("em2", message)

    def test_a_follow_up_that_adds_something_passes(self):
        """The same shape with a follow-up of its own argument is not refused.

        Without this the test above would pass for a gate that refuses
        everything, which is exactly the state this task was sent to fix.
        """
        plan, recs = self._plan_for(packfixture.html_followup("em2"))
        report = {}
        bisonfactory._refuse_sequence_gate(plan, recs, report)
        self.assertTrue(report["sequencegate"]["passed"],
                        report["sequencegate"]["leads"])


if __name__ == "__main__":
    unittest.main()
