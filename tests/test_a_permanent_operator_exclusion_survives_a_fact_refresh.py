"""A permanent operator exclusion is not a review and does not go stale.

THE DEFECT, MEASURED 2026-09-28 on a byte-identical copy of the production
queue. 32 companies (TASK-430, campaigns 491-500) were recorded as never to be
enrolled again. The ruling was written as `qualification.human_review`, and
both readers of a human review - `qualify.review_of` and
`dmplan.human_review` - drop a review whose `inputs_fingerprint` no longer
matches the qualification's. All 32 resolved `rejected` through
`qualify.state_of`; move the fingerprint, as any fact refresh does, and **7
stayed `rejected` (the classifier itself says so) and 25 reverted to
`review_required`.**

Staleness is the RIGHT rule for a review that PERMITS and exactly backwards
for one that FORBIDS, so the fix is a separate canonical state rather than a
weakened staleness rule. `src/operatorexclusion.py` carries the design and
why reuse of `agencydnc`, `ingest.load_suppress` and `accountstate` did not
fit.

WHAT THIS MODULE PROVES, and what it deliberately does not. It is hermetic:
it builds its own records and its own register, so it runs anywhere and
cannot touch real state. A passing unit test is NOT the proof that the
exclusion holds in production - `scripts/verify_operator_exclusion_paths.py`
is, run against a copy of the real queue, and its results are recorded in
`docs/PERMANENT-OPERATOR-EXCLUSION-2026-09-28.md`. What this module is for is
the regression: the day somebody removes one of these checks, this goes red.

EVERY GATE TEST HAS ITS CONTROL. A gate that refuses everything proves
nothing about this exclusion, so each path is asked twice - once about an
excluded account and once about an identical account the register has never
heard of - and the control must NOT be refused for this reason.
"""
import hashlib
import json
import os
import shutil
import tempfile
import unittest

from src import (campaigns, channels, dmplan, eligibility, enrich, icp,
                 operatorexclusion as oe, qualify, refresh, revival,
                 run as runner, sequencegate, sequenceplan)

EXCLUDED_DOMAIN = "excluded-by-the-operator.test"
CONTROL_DOMAIN = "never-excluded.test"

BY = "Zvonimir (operator)"
AT = "2026-09-28"
REASON = ("would not pass the ICP gate on the TASK-430 audit and the operator "
          "ruled the account must never be enrolled again")
AUTHORITY = "operator decision B, Zvonimir, 2026-09-28"


def contact(email, key="ck-1"):
    """A contact that would otherwise be fully sendable on both channels."""
    return {"key": key, "email": email, "name": "Dana Reed",
            "first_name": "Dana", "selected": True,
            "linkedin": "https://www.linkedin.com/in/dana-reed/",
            "sendable": True, "verdict": "valid",
            "verification": {"evidence": [
                {"provider": "contactout", "status": "valid", "email": email},
                {"provider": "reoon", "status": "valid", "email": email}]}}


def record(domain, record_id="rec-excluded", status=icp.REVIEW):
    """A record whose CLASSIFIER verdict is `review`.

    `review` on purpose: it is the operator's own acceptance case. For the 25
    companies the classifier called `review`, the classifier must go on saying
    `review` and the prohibition must hold anyway - so a test built on
    `rejected` would prove the easy half and miss the point.
    """
    rec = {
        "id": record_id, "client": "productive", "domain": domain,
        "company": "Excluded Co", "state": "queued",
        "company_facts": {"employees": 120, "country": "HR",
                          "industry": "Other", "domain": domain,
                          "name": "Excluded Co"},
        "contacts": [contact(f"dana@{domain}")],
        "events": [],
        "qualification": {
            "inputs_fingerprint": "FINGERPRINT-V1",
            "at": "2026-09-28T10:00:00+00:00",
            "segment": {}, "persona_plan": {}, "messaging": {},
            "cost_plan": {},
            "verdict": {"icp_status": status, "icp_tier": "REVIEW",
                        "icp_score": 19.0, "icp_confidence": "low",
                        "classification_reasons": ["not enough evidence"]},
            "dm_approved": False,
            # The human review the operator actually recorded, left exactly
            # where it is. It records a true fact and this state does not
            # replace it.
            "human_review": {
                "decision": qualify.REJECT, "by": f"{BY} {AT}", "at": AT,
                "note": "NOT_QUALIFIED by operator decision 2026-09-28",
                "reviewed_status": status, "reviewed_tier": "REVIEW",
                "reviewed_score": 19.0,
                "inputs_fingerprint": "FINGERPRINT-V1"},
        },
    }
    return rec


class ExclusionTest(unittest.TestCase):
    """A disposable register, so nothing here can reach the tracked one."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-exclusion-")
        self.register = os.path.join(self.tmp, "operator-exclusions.jsonl")
        self._prev = os.environ.get("OPERATOR_EXCLUSIONS")
        os.environ["OPERATOR_EXCLUSIONS"] = self.register
        oe.forget()
        self.assertEqual(oe.path(), os.path.abspath(self.register))
        oe.exclude(EXCLUDED_DOMAIN, by=BY, reason=REASON, authority=AUTHORITY,
                   at=AT, task="TASK-430")
        self.rec = record(EXCLUDED_DOMAIN)
        self.control = record(CONTROL_DOMAIN, record_id="rec-control")
        self.contact = self.rec["contacts"][0]
        self.control_contact = self.control["contacts"][0]

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("OPERATOR_EXCLUSIONS", None)
        else:
            os.environ["OPERATOR_EXCLUSIONS"] = self._prev
        oe.forget()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def register_hash(self):
        with open(self.register, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()

    def refresh_the_facts(self, rec):
        """A REAL fact refresh: change the facts, then requalify.

        Not a hand-written fingerprint. `qualify.company` recomputes the
        verdict and restamps `inputs_fingerprint`, which is the thing that
        made the old prohibition evaporate, so the control has to go through
        it rather than around it.
        """
        before = rec["qualification"]["inputs_fingerprint"]
        rec["company_facts"]["employees"] = 899
        rec["company_facts"]["a_new_fact"] = "the facts moved"
        qualify.company(rec, {}, store_result=True)
        after = rec["qualification"]["inputs_fingerprint"]
        self.assertNotEqual(
            before, after,
            "the fingerprint did not move, so this control proves nothing")
        return after


# ------------------------------------------------------- the ten paths

class TheExclusionRefusesAtEveryPath(ExclusionTest):

    def test_1_qualification_and_enrolment(self):
        self.assertEqual(qualify.state_of(self.rec), dmplan.OPERATOR_EXCLUDED)
        self.assertNotEqual(qualify.state_of(self.control),
                            dmplan.OPERATOR_EXCLUDED)

    def test_1b_the_classifier_verdict_is_not_overwritten(self):
        """The whole reason option A was refused."""
        self.assertEqual(
            self.rec["qualification"]["verdict"]["icp_status"], icp.REVIEW)
        qualify.state_of(self.rec)
        self.assertEqual(
            self.rec["qualification"]["verdict"]["icp_status"], icp.REVIEW)
        self.assertEqual(
            qualify.dossier({"record": self.rec,
                             "segment": {}, "verdict":
                                 self.rec["qualification"]["verdict"],
                             "persona_plan": {}})["icp"]["status"],
            icp.REVIEW)

    def test_2_person_enrichment(self):
        verdict = self.rec["qualification"]["verdict"]
        allowed, why = dmplan.may_enrich({}, [], self.rec, verdict, {})
        self.assertFalse(allowed)
        self.assertIn("permanently excluded by operator policy", why)
        self.assertFalse(enrich.person_level_allowed(self.rec)[0])
        # Control: refused too, but for the human review, not for this.
        _, control_why = dmplan.may_enrich(
            {}, [], self.control, self.control["qualification"]["verdict"], {})
        self.assertNotIn("permanently excluded by operator policy", control_why)

    def test_3_email_eligibility(self):
        ok, why = channels.email_verdict(self.rec, self.contact)
        self.assertFalse(ok)
        self.assertEqual(why, channels.OPERATOR_EXCLUDED)
        # THE POSITIVE CONTROL: the identical contact at a domain the register
        # has never heard of is fully sendable, so this gate is not one that
        # refuses everything.
        ok, why = channels.email_verdict(self.control, self.control_contact)
        self.assertTrue(ok, f"the control was refused: {why}")
        self.assertIsNone(why)

    def test_4_linkedin_eligibility(self):
        ok, why = channels.linkedin_verdict(self.rec, self.contact)
        self.assertFalse(ok)
        self.assertEqual(why, channels.OPERATOR_EXCLUDED)
        ok, why = channels.linkedin_verdict(self.control, self.control_contact)
        self.assertTrue(ok, f"the control was refused: {why}")

    def test_5_campaign_planning_and_the_send_gate(self):
        reasons = eligibility.must_not_contact(self.rec, self.contact)
        self.assertEqual(reasons[0], eligibility.BLOCKED_OPERATOR_EXCLUDED)
        campaign = {"campaign_id": "c1", "client": "productive",
                    "record_ids": [self.rec["id"]]}
        ok, detail = campaigns.check_no_operator_excluded_accounts(
            campaign, [self.rec], {})
        self.assertFalse(ok)
        self.assertIn("permanently excluded", detail)
        # Control
        self.assertIsNone(
            eligibility.must_not_contact(self.control, self.control_contact)[0])
        ok, _ = campaigns.check_no_operator_excluded_accounts(
            {"campaign_id": "c2", "client": "productive",
             "record_ids": [self.control["id"]]}, [self.control], {})
        self.assertTrue(ok)

    def test_5b_the_step_decision_blocks(self):
        decided = eligibility.decide(
            self.rec, self.contact, "em1", channel="email", config={},
            step={"channel": "email", "day": 1, "subject": "s", "body": "b"})
        self.assertEqual(decided["verdict"], eligibility.BLOCKED)
        self.assertEqual(decided["reason"],
                         eligibility.BLOCKED_OPERATOR_EXCLUDED)

    def test_5c_every_reason_code_has_a_sentence(self):
        """A code nobody can explain is a bug, and this repo already says so."""
        self.assertIn(eligibility.BLOCKED_OPERATOR_EXCLUDED,
                      eligibility.REASONS)
        self.assertIn(eligibility.BLOCKED_OPERATOR_EXCLUDED, eligibility.HUMAN)
        self.assertIn(channels.OPERATOR_EXCLUDED, channels.REASONS)
        self.assertIn(channels.OPERATOR_EXCLUDED, channels.HUMAN)

    def test_6_sequence_plan_and_the_provider_projections(self):
        account = {"company": "Excluded Co", "domain": EXCLUDED_DOMAIN}
        with self.assertRaises(sequenceplan.PlanRefused):
            sequenceplan.new("productive", account, [])
        # A plan built BEFORE the exclusion was recorded must still not
        # project. This is the one the build-time check cannot catch.
        stale = {"client": "productive", "account": account, "contacts": []}
        with self.assertRaises(sequenceplan.PlanRefused):
            sequenceplan.derive_bison_payload(stale)
        with self.assertRaises(sequenceplan.PlanRefused):
            sequenceplan.derive_heyreach_payload(stale)
        # Control: the same three calls succeed.
        control_account = {"company": "Control", "domain": CONTROL_DOMAIN}
        sequenceplan.new("productive", control_account, [])
        sequenceplan.derive_bison_payload(
            {"client": "productive", "account": control_account,
             "contacts": []})

    def test_6b_the_staging_gate_refuses_the_state(self):
        gate = sequencegate.check(
            {"emails": {"em1": "a body with enough words to be a message"},
             "subjects": {"A": "a subject"}, "hypothesis": "a hypothesis"},
            qualification=qualify.state_of(self.rec))
        self.assertFalse(gate["passed"])
        self.assertTrue(
            [f for f in gate["failures"] if f["check"] == "qualified"],
            f"the qualification check did not fire: "
            f"{[f['check'] for f in gate['failures']]}")

    def test_7_retry_and_reprocess(self):
        assessed = revival.assess(self.rec, config={})
        self.assertEqual(assessed["verdict"], revival.NEVER)
        self.assertEqual(assessed["why"], revival.OPERATOR_EXCLUDED)
        self.assertNotEqual(revival.assess(self.control, config={})["why"],
                            revival.OPERATOR_EXCLUDED)

    def test_8_fact_refresh(self):
        self.assertEqual(refresh.excluded(self.rec), refresh.OPERATOR_EXCLUDED)
        self.assertIsNone(refresh.excluded(self.control))
        self.assertIn(refresh.OPERATOR_EXCLUDED, refresh.EXCLUSION_LABEL)

    def test_9_requalification(self):
        self.refresh_the_facts(self.rec)
        self.assertEqual(qualify.state_of(self.rec), dmplan.OPERATOR_EXCLUDED)

    def test_9b_a_dropped_excluded_record_is_never_returned_to_the_queue(self):
        self.rec["state"] = "dropped"
        self.rec["drop_reason"] = enrich.ICP_REJECTED
        self.assertIsNone(qualify._release_stale_icp_drop(self.rec))
        self.assertEqual(self.rec["state"], "dropped")

    def test_10_regeneration(self):
        self.rec.setdefault("stages", {})
        outcome = runner.stage_generate([self.rec], model=None, spend=True,
                                        notes=[])
        self.assertEqual(outcome["records"], 0)
        self.assertEqual(self.rec["stages"]["generate"]["status"], "refused")
        self.assertIn("permanently excluded",
                      self.rec["stages"]["generate"]["note"])


# ------------------------------------- the critical negative control

class AFactRefreshDoesNotLiftIt(ExclusionTest):

    def test_before_the_refresh_it_blocks(self):
        self.assertTrue(oe.blocks(self.rec))
        self.assertIsNotNone(qualify.review_of(self.rec),
                             "the review starts live; that is the premise")

    def test_the_old_defect_is_real(self):
        """WITHOUT the exclusion, the review alone does not survive.

        This is the control on the whole exercise: if the human review held
        by itself, nothing here would be needed. So the exclusion is removed
        from the register and the record is refreshed, and `state_of` must go
        back to `review_required` - the measured production behaviour.
        """
        os.remove(self.register)
        self.assertFalse(oe.blocks(self.rec))
        self.assertEqual(qualify.state_of(self.rec), dmplan.REJECTED)
        self.refresh_the_facts(self.rec)
        self.assertIsNone(qualify.review_of(self.rec))
        self.assertIsNone(dmplan.human_review(self.rec))
        self.assertEqual(qualify.state_of(self.rec), dmplan.REVIEW_REQUIRED,
                         "the defect this task exists to fix did not reproduce")

    def test_after_the_refresh_every_path_still_blocks(self):
        self.refresh_the_facts(self.rec)
        # The human review MAY legitimately go stale...
        self.assertIsNone(qualify.review_of(self.rec))
        self.assertIsNotNone(qualify.stale_review_of(self.rec))
        self.assertIsNone(dmplan.human_review(self.rec))
        # ...the classifier MAY legitimately change its mind...
        self.assertIn(self.rec["qualification"]["verdict"]["icp_status"],
                      (icp.REVIEW, icp.REJECTED, icp.QUALIFIED, icp.UNKNOWN))
        # ...and the exclusion MUST remain active at every path.
        self.assertEqual(qualify.state_of(self.rec), dmplan.OPERATOR_EXCLUDED)
        self.assertEqual(channels.email_verdict(self.rec, self.contact),
                         (False, channels.OPERATOR_EXCLUDED))
        self.assertEqual(channels.linkedin_verdict(self.rec, self.contact),
                         (False, channels.OPERATOR_EXCLUDED))
        self.assertEqual(
            eligibility.must_not_contact(self.rec, self.contact)[0],
            eligibility.BLOCKED_OPERATOR_EXCLUDED)
        self.assertFalse(dmplan.may_enrich(
            {}, [], self.rec, self.rec["qualification"]["verdict"], {})[0])
        self.assertEqual(refresh.excluded(self.rec), refresh.OPERATOR_EXCLUDED)
        self.assertEqual(revival.assess(self.rec, config={})["verdict"],
                         revival.NEVER)

    def test_even_a_verdict_that_turns_qualified_does_not_lift_it(self):
        """The strongest form: the classifier changes its mind entirely."""
        self.rec["qualification"]["verdict"]["icp_status"] = icp.QUALIFIED
        self.rec["qualification"]["verdict"]["icp_tier"] = icp.TIER_A
        self.rec["qualification"]["human_review"] = None
        self.assertEqual(qualify.state_of(self.rec), dmplan.OPERATOR_EXCLUDED)
        self.assertFalse(enrich.person_level_allowed(self.rec)[0])

    def test_wiping_the_records_qualification_entirely_changes_nothing(self):
        """The exclusion is not stored on the record, so nothing that
        rewrites a record can reach it - a migration, a re-ingest, a batch
        reprocess. Proved by deleting everything the record carries."""
        self.rec.pop("qualification", None)
        self.rec.pop("company_facts", None)
        self.rec.pop("research", None)
        self.rec["state"] = "queued"
        self.assertEqual(qualify.state_of(self.rec), dmplan.OPERATOR_EXCLUDED)
        self.assertTrue(oe.blocks(self.rec))


class NothingAutomatedRemovesIt(ExclusionTest):

    def test_the_register_is_byte_identical_after_every_automated_path(self):
        """THE INVERSE TEST, as a file hash rather than an assertion about
        intent. If no automated path can change the register's bytes, no
        automated path cleared an exclusion."""
        before = self.register_hash()
        qualify.state_of(self.rec)
        qualify.company(self.rec, {}, store_result=True)
        self.refresh_the_facts(self.rec)
        refresh.excluded(self.rec)
        revival.assess(self.rec, config={})
        dmplan.may_enrich({}, [], self.rec,
                          self.rec["qualification"]["verdict"], {})
        enrich.person_level_allowed(self.rec)
        channels.email_verdict(self.rec, self.contact)
        channels.linkedin_verdict(self.rec, self.contact)
        eligibility.must_not_contact(self.rec, self.contact)
        self.rec.setdefault("stages", {})
        runner.stage_generate([self.rec], model=None, spend=True, notes=[])
        campaigns.check_no_operator_excluded_accounts(
            {"campaign_id": "c", "record_ids": [self.rec["id"]]},
            [self.rec], {})
        self.assertEqual(before, self.register_hash())
        self.assertTrue(oe.blocks(self.rec))

    def test_no_module_in_src_calls_lift(self):
        """The guarantee is a call none of the automated paths can make, so
        the check is that none of them makes it. Asserted against the parsed
        source rather than a substring: a comment mentioning `lift` must not
        fail this, and an aliased import must not pass it."""
        import ast

        src = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "src")
        offenders = []
        for root, _dirs, files in os.walk(src):
            for name in files:
                if not name.endswith(".py"):
                    continue
                full = os.path.join(root, name)
                if os.path.abspath(full) == os.path.abspath(
                        oe.__file__):
                    continue                 # the definition itself
                with open(full, encoding="utf-8") as handle:
                    try:
                        tree = ast.parse(handle.read())
                    except SyntaxError:
                        continue
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue
                    fn = node.func
                    if isinstance(fn, ast.Attribute) and fn.attr == "lift":
                        offenders.append(f"{full}:{node.lineno}")
                    elif isinstance(fn, ast.Name) and fn.id == "lift":
                        offenders.append(f"{full}:{node.lineno}")
        self.assertEqual(offenders, [], f"something in src/ calls lift(): "
                                        f"{offenders}")

    def test_a_lift_must_name_the_account_key_it_lifts(self):
        with self.assertRaises(oe.ExclusionRefused):
            oe.lift(EXCLUDED_DOMAIN, by=BY, reason="changed my mind",
                    confirm="not-the-key")
        self.assertTrue(oe.blocks(self.rec))

    def test_an_operator_lift_does_work_and_is_recorded(self):
        """Reversible - by an operator, explicitly, with who, when and why."""
        key = oe.account_key(EXCLUDED_DOMAIN)
        oe.lift(EXCLUDED_DOMAIN, by="Zvonimir (operator)",
                reason="the account was re-approved on 2026-10-01",
                confirm=key, at="2026-10-01")
        self.assertFalse(oe.blocks(self.rec))
        self.assertNotEqual(qualify.state_of(self.rec),
                            dmplan.OPERATOR_EXCLUDED)
        # The history is still readable: the exclusion is not erased.
        ordered, bad = oe.rows()
        self.assertEqual(bad, 0)
        self.assertEqual([r["op"] for r in ordered], [oe.EXCLUDE, oe.LIFT])
        self.assertEqual(ordered[-1]["by"], "Zvonimir (operator)")
        self.assertEqual(ordered[-1]["at"], "2026-10-01")
        self.assertEqual(ordered[-1]["authority"], oe.OPERATOR)

    def test_a_lift_row_that_is_not_an_operators_lifts_nothing(self):
        """Refused at write time is not enough: a row that reached the file
        another way - an editor, a bad merge, a script - must not take effect
        either."""
        with open(self.register, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "op": oe.LIFT, "account": oe.account_key(EXCLUDED_DOMAIN),
                "authority": "batch-reprocess", "by": "the nightly run",
                "reason": "the facts changed", "at": "2026-10-02"}) + "\n")
        self.assertTrue(oe.blocks(self.rec))
        self.assertEqual(qualify.state_of(self.rec), dmplan.OPERATOR_EXCLUDED)

    def test_a_reexclusion_after_a_lift_takes_effect(self):
        key = oe.account_key(EXCLUDED_DOMAIN)
        oe.lift(EXCLUDED_DOMAIN, by=BY, reason="re-approved", confirm=key)
        self.assertFalse(oe.blocks(self.rec))
        oe.exclude(EXCLUDED_DOMAIN, by=BY, reason="excluded again",
                   authority=AUTHORITY)
        self.assertTrue(oe.blocks(self.rec))
        self.assertEqual(len(oe.exclusion_of(self.rec)["history"]), 3)

    def test_a_test_cannot_append_to_the_tracked_register(self):
        """The barrier `store.refuse_production_write` does not cover, because
        this register deliberately lives outside `work/`."""
        with self.assertRaises(oe.ProductionRegisterUnderTest):
            oe.exclude("anything.test", by=BY, reason=REASON,
                       authority=AUTHORITY,
                       file_path=oe.TRACKED_REGISTER)


class TheLastGateBeforeAProviderWriteNamesIt(unittest.TestCase):
    """The execution guard refuses, and under its OWN gate name.

    Reuses `test_compliance_gate`'s harness rather than building a second one:
    it already assembles a real record, a real approved campaign, real sender
    identity and a real readback far enough to reach gate 4, which is where
    this refusal has to happen. A second copy of that setup would drift from
    it. It is DRIVEN rather than SUBCLASSED on purpose - subclassing would
    re-run every compliance test under this module's name.

    WHY THE GATE NAME IS THE ASSERTION. `NotAuthorized` carries `gate`, and
    that word is what a report and an operator read. `_require` raises, so
    whichever check runs first owns the name: asked after the eligibility
    check this refusal would always read `eligibility`, and asked only
    through `SUPPRESSION_REASONS` it would read `suppression`. Either is the
    four origins collapsing into one word at the last gate before a provider
    write. This test is what stops that happening again.
    """

    def setUp(self):
        from tests import test_compliance_gate

        self.harness = test_compliance_gate.ComplianceGateTest("setUp")
        # BOTH, AND IN THIS ORDER. Cleanups registered here run LIFO, so
        # `tearDown` runs first and `doCleanups` second - the order unittest
        # itself uses.
        #
        # `doCleanups` is not optional and its absence is not quiet. The
        # harness's `setUp` calls `pin_client_config`, which monkeypatches
        # `clients.load` and undoes it through `addCleanup` - and a TestCase
        # this module drives rather than RUNS never reaches its own cleanups.
        # Measured: without this line the pinned fixture config leaked for the
        # rest of the process and `test_compliance_gate`'s own
        # `test_the_live_cadence_is_the_canonical_five_plus_five` failed,
        # reading the fixture's cadence as the live one. Exactly the
        # cross-module leak `tests/envisolation.py` exists to catch, and
        # `envisolation` would not have caught it: it restores `os.environ`,
        # and this was a monkeypatched module attribute.
        self.harness.setUp()
        self.addCleanup(self.harness.doCleanups)
        self.addCleanup(self.harness.tearDown)
        self.tmp = tempfile.mkdtemp(prefix="rga-exclusion-guard-")
        self.register = os.path.join(self.tmp, "operator-exclusions.jsonl")
        self._prev = os.environ.get("OPERATOR_EXCLUSIONS")
        os.environ["OPERATOR_EXCLUSIONS"] = self.register
        oe.forget()
        self.addCleanup(self._restore)

    def _restore(self):
        if self._prev is None:
            os.environ.pop("OPERATOR_EXCLUSIONS", None)
        else:
            os.environ["OPERATOR_EXCLUSIONS"] = self._prev
        oe.forget()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_guard_refuses_under_the_operator_exclusion_gate(self):
        from src import executionguard

        oe.exclude(self.harness.rec["domain"], by=BY, reason=REASON,
                   authority=AUTHORITY, at=AT)
        with self.harness._pass_gates_before_compliance():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.harness._authorize_email()
        self.assertEqual(caught.exception.gate, "operator_exclusion",
                         f"the wrong gate fired: {caught.exception.gate}")
        self.assertIn("permanently excluded by operator policy",
                      str(caught.exception))

    def test_without_the_exclusion_a_different_gate_owns_the_refusal(self):
        """THE CONTROL. The same call and the same harness with no exclusion
        recorded: the guard still refuses - this cadence carries no
        unsubscribe affordance - but under a different gate. So the name
        asserted above belongs to this exclusion and is not simply whatever
        this path always says."""
        from src import executionguard

        with self.harness._pass_gates_before_compliance():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.harness._authorize_email()
        self.assertEqual(caught.exception.gate, "compliance",
                         "the control refused somewhere unexpected, so it is "
                         "no longer a control for THIS gate: "
                         f"{caught.exception.gate}")


# --------------------------------------------------------- inspectability

class ItAnswersForItself(ExclusionTest):

    def test_it_says_why_who_when_what_and_which_origin(self):
        answer = oe.explain(self.rec)
        self.assertTrue(answer["permanently_excluded"])
        policy = [row for row in answer["origins"]
                  if row["origin"] == oe.OPERATOR_POLICY]
        self.assertEqual(len(policy), 1)
        row = policy[0]
        self.assertEqual(row["who"], BY)                       # WHO
        self.assertEqual(row["when"], AT)                      # WHEN
        self.assertEqual(row["reason"], REASON)                # WHAT REASON
        self.assertEqual(row["authority"], AUTHORITY)          # AUTHORITY
        self.assertEqual(row["origin"], oe.OPERATOR_POLICY)    # WHICH ORIGIN
        self.assertIn("operator", row["reversibility"])
        self.assertEqual(row["task"], "TASK-430")

    def test_the_four_origins_do_not_collapse_into_one_blocked(self):
        """Each origin has its own reversibility rule, and the answer keeps
        them apart. The classifier's `review` and the human's stale reject
        are both reported, both distinct from the operator policy."""
        self.refresh_the_facts(self.rec)
        origins = {row["origin"]: row for row in oe.explain(self.rec)["origins"]}
        self.assertIn(oe.OPERATOR_POLICY, origins)
        self.assertIn(oe.HUMAN_REVIEW, origins)
        self.assertIn(oe.CLASSIFIER, origins)
        # The human review has gone stale, and says so rather than vanishing.
        self.assertTrue(origins[oe.HUMAN_REVIEW]["stale"])
        self.assertFalse(origins[oe.HUMAN_REVIEW]["blocked"])
        # The classifier still reports whatever it concluded.
        self.assertEqual(origins[oe.CLASSIFIER]["icp_status"],
                         self.rec["qualification"]["verdict"]["icp_status"])
        # Only the operator policy is still blocking.
        self.assertTrue(origins[oe.OPERATOR_POLICY]["blocked"])
        self.assertEqual(
            len({row["reversibility"] for row in origins.values()}), 3)

    def test_the_dossier_carries_it_beside_the_review_and_the_verdict(self):
        entry = {"record": self.rec, "segment": {},
                 "verdict": self.rec["qualification"]["verdict"],
                 "persona_plan": {}}
        dossier = qualify.dossier(entry)
        self.assertEqual(dossier["state"], dmplan.OPERATOR_EXCLUDED)
        self.assertEqual(dossier["operator_exclusion"]["by"], BY)
        self.assertEqual(dossier["icp"]["status"], icp.REVIEW)
        self.assertIsNotNone(dossier["human_review"])

    def test_a_clean_account_says_nothing_blocks_it(self):
        clean = record(CONTROL_DOMAIN, record_id="rec-clean",
                       status=icp.QUALIFIED)
        clean["qualification"]["human_review"] = None
        answer = oe.explain(clean)
        self.assertFalse(answer["permanently_excluded"])
        self.assertEqual(answer["summary"], "nothing blocks this account")

    def test_the_audit_names_nobody(self):
        report = oe.audit()
        self.assertEqual(report["active"], 1)
        self.assertEqual(report["unreadable_rows"], 0)
        self.assertEqual(report["origins"], [oe.OPERATOR_POLICY])
        blob = json.dumps(report)
        self.assertNotIn(EXCLUDED_DOMAIN, blob)

    def test_a_corrupt_row_is_counted_rather_than_silently_dropped(self):
        with open(self.register, "a", encoding="utf-8") as handle:
            handle.write("{not json at all\n")
        self.assertEqual(oe.audit()["unreadable_rows"], 1)
        self.assertTrue(oe.blocks(self.rec))


class TheKeyIsTheAccount(ExclusionTest):

    def test_the_domain_is_normalised_before_it_is_hashed(self):
        for spelling in (EXCLUDED_DOMAIN, EXCLUDED_DOMAIN.upper(),
                         f"https://{EXCLUDED_DOMAIN}/pricing?a=1",
                         f"{EXCLUDED_DOMAIN}."):
            self.assertTrue(oe.blocks({"domain": spelling}), spelling)

    def test_no_plaintext_identifier_is_stored(self):
        with open(self.register, encoding="utf-8") as handle:
            blob = handle.read()
        self.assertNotIn(EXCLUDED_DOMAIN, blob)
        self.assertNotIn("Excluded Co", blob)

    def test_a_record_with_no_domain_is_not_accidentally_excluded(self):
        self.assertFalse(oe.blocks({"domain": ""}))
        self.assertFalse(oe.blocks({}))
        self.assertIsNone(oe.exclusion_of({"domain": None}))

    def test_an_exclusion_with_no_author_or_reason_is_refused(self):
        for kw in ({"by": "", "reason": REASON, "authority": AUTHORITY},
                   {"by": BY, "reason": "", "authority": AUTHORITY},
                   {"by": BY, "reason": REASON, "authority": ""}):
            with self.assertRaises(oe.ExclusionRefused):
                oe.exclude("another.test", **kw)

    def test_an_exclusion_added_after_the_first_read_is_seen(self):
        """THE CACHE MUST NOT BE A STALE PERMIT.

        `resolve` caches on (path, mtime_ns, size) so a gate called per
        contact per step does not re-parse the file six figures of times. An
        exclusion recorded after that first read must still block, or the
        cache is a hole in the guard.
        """
        other = {"domain": "added-later.test"}
        self.assertFalse(oe.blocks(other))          # primes the cache
        oe.exclude("added-later.test", by=BY, reason=REASON,
                   authority=AUTHORITY)
        self.assertTrue(oe.blocks(other),
                        "the cache served a stale permit after a new exclusion")

    def test_a_missing_register_is_never_cached_as_empty(self):
        self.assertTrue(oe.blocks(self.rec))
        os.remove(self.register)
        self.assertFalse(oe.blocks(self.rec))
        oe.exclude(EXCLUDED_DOMAIN, by=BY, reason=REASON, authority=AUTHORITY)
        self.assertTrue(oe.blocks(self.rec))

    def test_an_unknown_origin_is_refused(self):
        with self.assertRaises(oe.ExclusionRefused):
            oe.exclude("another.test", by=BY, reason=REASON,
                       authority=AUTHORITY, origin="vibes")


if __name__ == "__main__":
    unittest.main()
