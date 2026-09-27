#!/usr/bin/env python3
"""A dry run EXECUTES the sequence gate, and writes nothing.

THE RULE THIS PINS. Operator, 2026-09-27, recorded in `docs/OPERATING-MODE.md`:

    A dry run means "execute the real decision and safety path without
    provider writes". It NEVER means "skip the safety path because
    `live=false`".

THE DEFECT IT CLOSES. `bisonfactory.stage()` returned before both
`_refuse_copylint` and `_refuse_sequence_gate` when `live=False`, so a
zero-write run never ran the sequence gate at all and the report it handed back
carried no `sequencegate` key to admit it. A check that did not run looks
exactly like a check that passed - which is why a green dry run was evidence of
less than it appeared to be.

It also made `TASK-425` acceptance criterion 3 unsatisfiable. That asks for
offer sequencing "enforced by `sequencegate`, with a negative test", from a run
performing ZERO provider writes, and as the code stood the gate only ran when
writes were allowed: the two halves of the criterion contradicted each other.

WHAT EACH TEST HERE IS FOR, and none of them reads the source:

  - a sequence the gate refuses is REFUSED on a dry run, and the refusal names
    the gate and the step - the negative test criterion 3 asks for;
  - a valid sequence REACHES the dry-run projection instead of being refused
    for lack of a provider, which is the control: without it every test here
    would pass for a `stage()` that refused everything, and this repository has
    shipped one of those;
  - the gate is what refuses. Bypass it and the same bad campaign reaches the
    projection, so the refusal cannot be some other guard firing first;
  - the gate's verdict is ON the dry-run report, per lead, so "it ran" is
    observable rather than inferred from the absence of an exception;
  - and in every one of those cases the provider transport is NEVER reached.

HOW THE ZERO-WRITE CLAIM IS PROVED. `providers.set_transport` installs a
transport that RAISES on any call, so a write arriving at all fails the test
rather than passing quietly. `providers.request` is the single chokepoint every
provider module goes through. The pattern is
`tests/test_sending_live_off_blocks_only_our_new_writes.py`'s.

AND THE REAL `bison` MODULE IS LEFT IN PLACE. Every other staging test swaps
`bisonfactory.bison` for `tests.fakebison`, which is right when the subject is
what the provider is told - but a fake cannot prove that nothing was told to a
provider, only that nothing was told to the fake. Here the module under the
seam is the real one and the wire is the booby trap, so "the transport is never
reached" is a claim about the production path.
"""
import unittest
from unittest import mock

from src import (bisonfactory, campaigns, providers, sequencegate, store,
                 workspaces)
from tests import packfixture
from tests.base import QueueTest
from tests.test_staging_a_campaign_twice_builds_one import (CID, COMPANY,
                                                           CONFIG, record)


class AProviderRequestWasMade(AssertionError):
    """The transport was reached. On a dry run that is always a failure."""


#: Two email steps keyed the way `sequencegate`'s repetition check reads them.
#: It compares `em1`..`em5` only, so a cadence keyed `day1`/`day3` is invisible
#: to it - which is why this module declares its own cadence rather than reusing
#: the single-step `CONFIG` shape.
TWO_STEPS = ({"key": "em1", "day": 1, "channel": "email", "generated": True},
             {"key": "em2", "day": 4, "channel": "email", "generated": True})


def two_step_config():
    return dict(CONFIG, email_sequence={
        "title": "two steps",
        "steps": {"em1": {"order": 1, "subject": "{SUBJECT_1}",
                          "body": "<p>{BODY_1}</p>", "wait_in_days": 3},
                  "em2": {"order": 2, "subject": "{SUBJECT_1}",
                          "body": "<p>{BODY_2}</p>", "wait_in_days": 4}},
        "thread_reply_pattern": [False, True]})


def two_step_record(em2_body):
    """One stageable record whose second step's words are the variable.

    Everything else is held constant - the same account, the same opener, the
    same approvals, the same research, the same ICP verdict - so the only thing
    that can move a run from refused to staged is what `em2` says. A gate that
    refused on anything else would refuse both halves of the pair and the
    control below would catch it.
    """
    from src import approval as _approval

    rec = record("rec-1", "one@example.com", "Ada")
    key = "rec-1-c1"
    opener = {"channel": "email", "subject": "how margin shows up",
              "body": packfixture.html_opener("Ada", COMPANY)}
    opener["approval"] = {"by": "operator", "at": "2026-09-13T00:00:00Z",
                          "fingerprint": _approval.fingerprint(opener)}
    second = {"channel": "email", "subject": "a follow-up", "body": em2_body}
    second["approval"] = {"by": "operator", "at": "2026-09-13T00:00:00Z",
                          "fingerprint": _approval.fingerprint(second)}
    rec["cadence"] = {key: {"em1": opener, "em2": second}}
    return rec


#: `em2` repeating the opener verbatim. A property of the WHOLE SEQUENCE, which
#: is what makes it the right negative case here: `copylint` reads each message
#: on its own and compares first lines ACROSS leads, so a single lead whose
#: follow-up restates its own opener is invisible to it. Only `sequencegate` can
#: refuse this, so a refusal cannot be the copy lint firing one gate earlier.
REPEATS_THE_OPENER = packfixture.html_opener("Ada", COMPANY)

#: The same shape with a follow-up making its own argument.
ADDS_ITS_OWN_ARGUMENT = packfixture.html_followup("em2")


class ADryRunRunsTheSequenceGate(QueueTest):

    def setUp(self):
        super().setUp()
        # THE BOOBY TRAP, installed before anything else so that no part of the
        # setup can reach a provider either.
        self.requests = []

        def refuse_every_request(method, url, headers, body, timeout):
            self.requests.append((method, url))
            raise AProviderRequestWasMade(
                f"a provider request was made: {method} {url}. A dry run "
                f"performs zero provider writes and zero provider reads")

        providers.set_transport(refuse_every_request)
        self.addCleanup(providers.reset_transport)

        # `sending.live` ON for the tenant, deliberately. The killswitch must
        # not be what stops this run: if it were, these tests would pass with
        # the sequence gate inert, which is the exact confusion TASK-426
        # exposed on this path.
        ws = workspaces.new_workspace("productive", "Productive",
                                      client="productive")
        ws["settings"] = {"policy": {"sending.live": "on"}}
        workspaces.save([ws])

    def given(self, em2_body):
        store.save([two_step_record(em2_body)])
        row = campaigns.new_campaign(CID, "productive", "Dry run gate test")
        row["cadence_steps"] = [dict(s) for s in TWO_STEPS]
        row["record_ids"] = ["rec-1"]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        campaigns.save([row])
        return row

    def dry_run(self):
        """The real production entrypoint, zero-write mode. Not a helper."""
        return bisonfactory.stage(CID, config=two_step_config(), live=False)

    def assertNothingReachedTheProvider(self):
        self.assertEqual([], self.requests,
                         "a dry run reached the provider transport")

    # --------------------------------------------------- the trap is armed

    def test_the_booby_trap_actually_fires(self):
        """Every zero-write claim in this module rests on this one.

        `assertEqual([], self.requests)` is satisfied just as well by a trap
        that was never installed, and a test that cannot fail is worse than no
        test - this repository has shipped several. So the trap is fired on
        purpose, through the same `providers.request` chokepoint the provider
        modules go through, and the assertion is that it raises and records.
        """
        with self.assertRaises(AProviderRequestWasMade):
            providers.request("GET", "http://example.invalid/armed",
                              headers={}, body=None, timeout=1)
        self.assertEqual([("GET", "http://example.invalid/armed")],
                         self.requests)
        # Cleared so the trap's own firing does not fail any later assertion in
        # this test.
        self.requests.clear()

    # ------------------------------------------------------- the negative test

    def test_a_bad_sequence_is_refused_on_a_dry_run(self):
        """Criterion 3's negative test. The gate refuses, and it says so.

        The refusal has to be attributable: "it raised" would be satisfied by
        the cadence guard, the qualification check, the tenancy check or the
        copy lint, none of which is evidence that sequencing is enforced. So
        what is asserted is the gate by name, the check by name, and the step.
        """
        self.given(REPEATS_THE_OPENER)
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            self.dry_run()
        message = str(caught.exception)
        self.assertIn("sequence-level gate", message)
        self.assertIn("followup_adds_value", message)
        self.assertIn("em2", message)
        self.assertIn("rec-1/rec-1-c1", message)
        self.assertNothingReachedTheProvider()

    def test_the_refusal_is_the_same_one_a_live_run_would_give(self):
        """Same refusal, same reason. Not a dry-run-shaped approximation.

        `live=True` is compared against `live=False` on the identical campaign.
        The live run is refused by the SAME gate before it reads a workspace, so
        this costs no provider call either - and if the two messages ever drift,
        a dry run has stopped being a rehearsal of the real decision.
        """
        self.given(REPEATS_THE_OPENER)
        with self.assertRaises(bisonfactory.FactoryRefused) as dry:
            self.dry_run()
        with self.assertRaises(bisonfactory.FactoryRefused) as live:
            bisonfactory.stage(CID, config=two_step_config(), live=True)
        self.assertEqual(str(dry.exception), str(live.exception))
        self.assertNothingReachedTheProvider()

    # -------------------------------------------------------------- the control

    def test_a_valid_sequence_reaches_the_dry_run_projection(self):
        """WITHOUT THIS THE TEST ABOVE PROVES NOTHING.

        A `stage()` that refused every dry run would satisfy the negative test
        perfectly. So the same fixture, differing only in what `em2` says, must
        run all the way to the projection - and be projected, not merely not
        refused: the EmailBison payload for both steps is on the report, which
        is what `TASK-425`'s audit artifact reads.
        """
        self.given(ADDS_ITS_OWN_ARGUMENT)
        report = self.dry_run()
        self.assertFalse(report["live"])
        self.assertIn("dry run: nothing was sent", report["did"])
        self.assertEqual(2, len(report["plan"]["provider_sequence"]))
        self.assertEqual(["em1", "em2"],
                         [step["step_key"]
                          for step in report["plan"]["provider_sequence"]])
        self.assertEqual(1, len(report["plan"]["leads"]))
        self.assertEqual([], report["plan"]["leads"][0]["missing_copy"])
        self.assertNothingReachedTheProvider()

    def test_the_gates_verdict_is_on_the_dry_run_report(self):
        """"It ran" is observable, not inferred from the absence of a refusal.

        This is the assertion the defect could not have satisfied: before the
        fix a dry run's report carried no `sequencegate` key at all, so a check
        that never ran was indistinguishable from one that passed. The verdict
        is per LEAD, because the sequence written to the provider is a template
        of merge fields and every lead carries its own words.
        """
        self.given(ADDS_ITS_OWN_ARGUMENT)
        report = self.dry_run()
        verdict = report["sequencegate"]
        self.assertTrue(verdict["passed"])
        self.assertEqual(["rec-1/rec-1-c1"],
                         [entry["lead"] for entry in verdict["leads"]])
        # The per-check detail, so this cannot pass on a stub that writes
        # `{"passed": True}` and calls nothing.
        self.assertTrue(verdict["leads"][0]["checks"],
                        "the report carries no per-check results, so the gate "
                        "was not actually asked")
        self.assertNothingReachedTheProvider()

    def test_the_copy_lint_also_refuses_on_a_dry_run(self):
        """The gate beside it, skipped by the same early return.

        `_refuse_copylint` ran on a dry run and declined to raise, so a run
        could report `refused: true` and still be read as a pass by anything
        looking only at whether it raised. It now refuses in both modes, and
        the structured verdict travels on the refusal so no diagnosis is lost.

        Two leads opening with the SAME sentence: a real copy defect, refused
        by `duplicate_first_line`, and independent of the sequence gate.
        """
        self.given(ADDS_ITS_OWN_ARGUMENT)
        twin = two_step_record(ADDS_ITS_OWN_ARGUMENT)
        twin["id"] = "rec-2"
        twin["contacts"][0]["key"] = "rec-2-c1"
        twin["contacts"][0]["email"] = "two@example.com"
        twin["cadence"] = {"rec-2-c1": twin["cadence"]["rec-1-c1"]}
        store.save([two_step_record(ADDS_ITS_OWN_ARGUMENT), twin])
        with campaigns.transaction() as rows:
            campaigns.get(CID, rows)["record_ids"] = ["rec-1", "rec-2"]

        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            self.dry_run()
        self.assertIn("batch copy lint", str(caught.exception))
        self.assertIn("duplicate_first_line", str(caught.exception))
        found = caught.exception.report["copylint"]
        self.assertTrue(found["refused"])
        self.assertNothingReachedTheProvider()

    # --------------------------------------------- the gate is what refuses

    def test_the_sequence_gate_is_what_refuses_and_not_a_later_guard(self):
        """Bypass the gate and the same bad campaign reaches the projection.

        Without this, `test_a_bad_sequence_is_refused_on_a_dry_run` would pass
        just as happily if some other guard were doing the work and the
        sequence gate were inert - the exact defect TASK-426 exposed, where the
        gate refused on `qualified` first and everything downstream of it was
        unreachable. Asserting on the message is not enough: the message is
        built from the gate's own report, so a gate that refuses for the wrong
        reason still names itself.

        What is measured is therefore an EFFECT. With `sequencegate.check`
        replaced by a verdict that passes everything, the identical campaign -
        the one whose follow-up repeats its opener - must run through to the
        dry-run projection. If it does not, something else is refusing it and
        this module proves nothing about the sequence gate.
        """
        self.given(REPEATS_THE_OPENER)
        with self.assertRaises(bisonfactory.FactoryRefused):
            self.dry_run()

        def passes_everything(sequence, **kwargs):
            return {"passed": True, "checks": [], "failures": [],
                    "warnings": []}

        with mock.patch.object(sequencegate, "check", passes_everything):
            report = self.dry_run()
        self.assertEqual(2, len(report["plan"]["provider_sequence"]),
                         "with the sequence gate bypassed the run still did "
                         "not reach the projection, so the gate is not what "
                         "refuses and these tests prove nothing about it")
        self.assertNothingReachedTheProvider()

    def test_the_gate_is_reached_at_all_on_a_dry_run(self):
        """The narrowest statement of the defect, and the mutation's target.

        Restore the early return and this is the test that fails: execution
        does not reach `sequencegate.check`. It is asserted by call rather than
        by refusal so that it stays true for a campaign the gate PASSES - a dry
        run of a clean campaign must still have asked.
        """
        self.given(ADDS_ITS_OWN_ARGUMENT)
        asked = []
        real = sequencegate.check

        def spy(*a, **kw):
            asked.append(kw.get("qualification"))
            return real(*a, **kw)

        with mock.patch.object(sequencegate, "check", spy):
            self.dry_run()
        self.assertEqual(["qualified"], asked,
                         "a dry run did not reach `sequencegate.check`, or "
                         "reached it without this lead's ICP verdict")
        self.assertNothingReachedTheProvider()


if __name__ == "__main__":
    unittest.main()
