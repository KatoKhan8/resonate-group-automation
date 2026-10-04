#!/usr/bin/env python3
"""`sequencegate.role_ladder` IS CALLED on the real stage path.

ENFORCEMENT HERE IS DEFERRED, NOT ABANDONED. OPERATOR DECISION, 2026-10-04.

This module was written to pin a REFUSAL at this seam and it did: three of
the tests below asserted `FactoryRefused`, and the mutation in `REPORT.md`
step 4 killed all three. The operator then saw what enforcement here costs -
87 newly failing test names against 11 for the writer seam, measured by name
on 48 modules against `b3f703cbf` - and decided: enforce the ladder in
`generate_campaign`, where a draft can still be FIXED, and defer the raise
here.

So the assertions below are WEAKER THAN THE INTENDED END STATE and say so.
What this seam does today is take the verdict and REPORT it; what it does not
do is raise on it. `TASK-979` carries the deferred enforcement, and the
reason the deferral survives is named there and in the call site: the 48
already-stored five-step sequences this seam would have protected are behind
the killswitch refusing in `_ensure_leads`, `sending.live` false, and 0 of
3,005 stored approvals still valid.

NOBODY SHOULD READ THESE TESTS AS THE DESIGN. The design is the refusal. A
test that pins "this is not refused" is a record of a decision with a date on
it, and when TASK-979 lands these three invert again.

THE DEFECT THIS CLOSES. `role_ladder` is TASK-964's named artefact - four
refusals, a control, six tests - and it had ZERO production callers. Two hits
for the name in `src/`, and both were comments. `task-copy-exemplars` admits
it under "What is NOT done": "`sequencegate.role_ladder` still has no
production caller. It was not wired." A thing computed correctly that nothing
downstream reads is the defect `CLAUDE.md` names as this repository's
recurring one, and an unwired gate is the purest form of it: every sequence
shaped like the committed artefact - a bump without a thread, non-descending
asks - was accepted by the production path.

WHAT IS ASSERTED, AND WHY EACH HALF IS NEEDED.

  - The ladder IS CALLED, once per lead, with that lead's five bodies. This
    is the assertion an observational gate most needs: a gate that refuses
    nothing decays into a gate that is never called, and nothing else here
    would notice. It is asserted with a spy that counts the calls and reads
    their arguments.

  - A sequence that breaks ONE ladder rule is REPORTED AND NOT REFUSED here,
    and the report says the ladder would have refused it, naming the check
    and the step. Both halves matter: the first is the deferral, the second
    is the evidence that survives it.

  - The SAME fixture, differing in one body only, is not refused EITHER and
    its ladder verdict is clean. Without this the module cannot tell "the
    ladder is quiet because it was deferred" from "the ladder is quiet
    because it reads everything as fine".

  - What the deferral COSTS is pinned as an effect: with the ladder-violating
    copy a live run now gets past every gate above the tenancy check and
    reaches the provider transport, where this module's booby trap stops it.
    Before the deferral it was refused with zero provider contact.

  - Nothing reaches the provider transport on any dry run here.

THE TWO BODIES DIFFER IN ONE RESPECT ONLY. `LADDER_GOOD["em2"]` says
"Following up on my note"; `LADDER_BAD["em2"]` does not. Everything else -
the account, the research, the ICP verdict, the approvals, the other four
steps - is held constant, so a gate that refused on anything else would
refuse both halves and the control would catch it. Measured: the ladder
refuses the bad one on exactly one check, `bump_without_thread` at `em2`, and
refuses the good one on none.
"""
import unittest
from unittest import mock

from src import (approval, bisonfactory, campaigns, icp, providers,
                 sequencegate, store, workspaces)
from tests import packfixture
from tests.base import QueueTest
from tests.test_staging_a_campaign_twice_builds_one import (CID, COMPANY,
                                                            CONFIG, DOMAIN)


class AProviderRequestWasMade(AssertionError):
    """The transport was reached. On a dry run that is always a failure."""


#: The five rungs, keyed the way the cadence and the ladder both read them.
FIVE_STEPS = tuple({"key": key, "day": day, "channel": "email",
                    "generated": True}
                   for key, day in (("em1", 1), ("em2", 4), ("em3", 8),
                                    ("em4", 12), ("em5", 21)))

FIRST = "Ada"

#: em1, THE OFFER, and grounded. The first line leans on `packfixture.own_fact`
#: for the same reason `packfixture.opener` does - `copylint.first_line` reads
#: the first non-empty line of step 1 against the pack - and the rung itself is
#: the paragraph after it, which says what the reader GETS before being asked
#: for anything.
LADDER_EM1 = ("%s, your site says %s %s.\n\n"
              "Most teams that size only see project margin once a project "
              "has closed, which is after the point where anything could be "
              "done about it.\n\n"
              "I can put together a free map of the next four weeks of "
              "bookings against budget, from public data, and leave it with "
              "you.\n\n"
              "Could we book a 30 minute walk-through of it?"
              % (FIRST, COMPANY, packfixture.GROUNDING))

#: em2, A SMALLER PIECE OF THE SAME OFFER, in the same thread. The thread
#: reference is the ONE thing the bad variant drops.
LADDER_EM2 = ("Following up on my note. Would you like to see just the "
              "first fortnight as a single screenshot instead?")

#: em2 WITHOUT its thread reference. Identical but for the opening clause, so
#: the only ladder rule it can break is rule 3.
LADDER_EM2_NO_THREAD = ("Would you like to see just the first fortnight "
                        "as a single screenshot instead?")

#: em3, PROOF: a named party and a number, in the same thread.
LADDER_EM3 = ("Coming back to my note with one number. Mast Studio cut 12 "
              "hours a week of status chasing after putting bookings and "
              "budgets on one view. Is your forward view in one place "
              "today?")

#: em4, AN EASY-ANSWER QUESTION WITH AN EXPLICIT EXIT, in the same thread.
LADDER_EM4 = ("As I mentioned, the map takes an hour to build. Does a "
              "forward view of bookings and budgets sound useful? If it is "
              "not the right time, say the word and I will leave you to "
              "it.")

#: em5, THE BREAKUP, in a NEW thread - so it must NOT reference the old one.
LADDER_EM5 = ("Closing the loop on this one. The map of the next four weeks "
              "is still yours if you want it, and agencies this size usually "
              "plan bookings and budgets in two tools. Worth a reply either "
              "way?")

LADDER_GOOD = {"em1": LADDER_EM1, "em2": LADDER_EM2, "em3": LADDER_EM3,
               "em4": LADDER_EM4, "em5": LADDER_EM5}
LADDER_BAD = dict(LADDER_GOOD, em2=LADDER_EM2_NO_THREAD)

SUBJECTS = {"em1": "how margin shows up", "em2": "how margin shows up",
            "em3": "one number", "em4": "one number",
            "em5": "closing the loop"}


#: The gap AFTER each step, which must equal the cadence's own day gaps -
#: `sequenceplan.derive_bison_sequence` refuses a config that would send on a
#: schedule the cadence does not describe. Days 1/4/8/12/21 give 3/4/4/9, and
#: the last is 1 rather than 0 because the provider rejected 0 on campaign 485.
WAITS = {"em1": 3, "em2": 4, "em3": 4, "em4": 9, "em5": 1}


def five_step_config():
    steps = {}
    for order, key in enumerate(("em1", "em2", "em3", "em4", "em5"), start=1):
        steps[key] = {"order": order, "subject": "{SUBJECT_%d}" % order,
                      "body": "<p>{BODY_%d}</p>" % order,
                      "wait_in_days": WAITS[key]}
    return dict(CONFIG, email_sequence={
        "title": "five rungs", "steps": steps,
        "thread_reply_pattern": [False, True, True, True, True]})


def five_step_record(bodies):
    """One stageable record carrying FIVE approved steps.

    The approvals are stamped over the words themselves, because
    `_certified_copy` hashes what it is about to stage and compares - a
    placeholder fingerprint is refused, and a fixture refused for that reason
    would hide the question this module is asking behind a different answer.
    """
    key = "rec-1-c1"
    cadence = {}
    for step_key, body in bodies.items():
        step = {"channel": "email", "subject": SUBJECTS[step_key],
                "body": body}
        step["approval"] = {"by": "operator", "at": "2026-09-13T00:00:00Z",
                            "fingerprint": approval.fingerprint(step)}
        cadence[step_key] = step
    return {"id": "rec-1", "client": "productive", "domain": DOMAIN,
            "company": COMPANY, "state": "ready",
            "qualification": {"verdict": {"icp_status": icp.QUALIFIED}},
            "research": [packfixture.own_fact("rec-1", DOMAIN, COMPANY)],
            "cadence": {key: cadence},
            "contacts": [{"key": key, "email": "one@example.com",
                          "first_name": FIRST, "last_name": "Tester",
                          "sendable": True, "verified": True}]}


class TheLadderIsAppliedOnTheRealStagePath(QueueTest):

    def setUp(self):
        super().setUp()
        self.requests = []

        def refuse_every_request(method, url, headers, body, timeout):
            self.requests.append((method, url))
            raise AProviderRequestWasMade(
                "a provider request was made: %s %s. This module performs "
                "zero provider writes and zero provider reads" % (method, url))

        providers.set_transport(refuse_every_request)
        self.addCleanup(providers.reset_transport)

        # The killswitch is ON for the tenant, deliberately: if it were what
        # stopped these runs, every assertion below would pass with the
        # ladder inert.
        ws = workspaces.new_workspace("productive", "Productive",
                                      client="productive")
        ws["settings"] = {"policy": {"sending.live": "on"}}
        workspaces.save([ws])

    def given(self, bodies):
        store.save([five_step_record(bodies)])
        row = campaigns.new_campaign(CID, "productive", "Ladder gate test")
        row["cadence_steps"] = [dict(s) for s in FIVE_STEPS]
        row["record_ids"] = ["rec-1"]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        campaigns.save([row])
        return row

    def dry_run(self):
        """The real production entrypoint, zero-write mode. Not a helper."""
        return bisonfactory.stage(CID, config=five_step_config(), live=False)

    def assertNothingReachedTheProvider(self):
        self.assertEqual([], self.requests,
                         "a dry run reached the provider transport")

    # ------------------------------------------- the fixtures are what I say

    def test_the_two_fixtures_differ_only_in_what_the_ladder_sees(self):
        """The A/B is honest, asserted rather than claimed in a comment.

        Four of the five bodies are identical, and the ladder refuses the bad
        one on exactly one check. If a later edit made the bad fixture break a
        second rule, the refusal below would stop being attributable to rule 3
        and this test says so first.
        """
        self.assertEqual(
            {"em1", "em3", "em4", "em5"},
            {k for k in LADDER_GOOD if LADDER_GOOD[k] == LADDER_BAD[k]})
        good = sequencegate.role_ladder(LADDER_GOOD)
        bad = sequencegate.role_ladder(LADDER_BAD)
        self.assertFalse(good["refused"], good["why"])
        self.assertEqual([("bump_without_thread", "em2")],
                         [(f["check"], f["step"]) for f in bad["failures"]])

    # ------------------------------------------------------- the negative test

    def test_the_ladder_is_actually_called_once_per_lead(self):
        """The assertion an OBSERVATIONAL gate needs more than any other.

        A gate that refuses nothing is indistinguishable, from the outside,
        from a gate that is not called - and the second is what the first
        quietly becomes. Every other test in this module would still pass if
        the call were deleted tomorrow. This one would not.

        The arguments are read as well as counted, because a call handed the
        wrong thing answers a different question: this repository has already
        paid for `sequencegate.check` being handed one subject per step
        instead of one per thread.
        """
        self.given(LADDER_BAD)
        seen = []
        real = sequencegate.role_ladder

        def spy(steps):
            seen.append(steps)
            return real(steps)

        with mock.patch.object(sequencegate, "role_ladder", spy):
            self.dry_run()
        self.assertEqual(1, len(seen), "the ladder was not called once")
        self.assertEqual(["em1", "em2", "em3", "em4", "em5"],
                         sorted(seen[0]))
        self.assertEqual(LADDER_BAD["em2"], seen[0]["em2"])
        self.assertNothingReachedTheProvider()

    def test_a_ladder_violating_sequence_is_reported_and_NOT_refused(self):
        """DEFERRED by operator decision, 2026-10-04. Not abandoned.

        Until that decision this asserted `FactoryRefused` naming
        `bump_without_thread` at `em2`, and it passed. Enforcement moved to
        `generate_campaign`, which is the seam that can still fix a draft,
        because enforcing here costs 87 newly failing names against 11 there.

        What is pinned now is BOTH halves of the deferral: the push is no
        longer stopped, AND the verdict that would have stopped it is on the
        report, naming the check and the step. The second half is what makes
        the 48 already-stored sequences auditable on a zero-write dry run
        while the gate is off. See TASK-979.
        """
        self.given(LADDER_BAD)
        report = self.dry_run()
        self.assertIn("dry run: nothing was sent", report["did"])
        self.assertTrue(report["sequencegate"]["passed"],
                        "the ladder is deferred here, so the sequence gate's "
                        "own verdict is the only one that may refuse")
        ladder = report["sequencegate"]["leads"][0]["role_ladder"]
        self.assertTrue(ladder["refused"])
        self.assertEqual([("bump_without_thread", "em2")],
                         [(f["check"], f["step"]) for f in ladder["failures"]])
        self.assertNothingReachedTheProvider()

    def test_what_the_deferral_costs_a_live_run_is_pinned_as_an_effect(self):
        """DEFERRED by operator decision, 2026-10-04. Not abandoned.

        Until that decision this asserted that a live run and a dry run gave
        the IDENTICAL refusal - a dry run rehearsing the real decision, ladder
        included. Both now decline to refuse, so asserting the two agree would
        be satisfied by a stage that does nothing at all.

        So the COST is asserted instead, and as an effect rather than a note:
        a live run on the ladder-violating copy now gets PAST every gate above
        the tenancy check. It dies at `bison.bound_workspace()` - on a missing
        credential in this environment, on the booby-trapped transport in one
        that has a key - and either way it died at the PROVIDER STEP and not
        at a gate. Before the deferral it never reached that line.

        The assertion is "not a `FactoryRefused`" rather than one exception
        type, because which of the two it is depends on whether a key is
        configured and neither answers the question. What answers the question
        is that no gate refused it. That is exactly what TASK-979 closes, and
        it is why the three barriers named in this module's docstring are
        load-bearing today.
        """
        self.given(LADDER_BAD)
        report = self.dry_run()
        self.assertIn("dry run: nothing was sent", report["did"])
        self.assertNothingReachedTheProvider()
        with self.assertRaises(Exception) as caught:
            bisonfactory.stage(CID, config=five_step_config(), live=True)
        self.assertNotIsInstance(
            caught.exception, bisonfactory.FactoryRefused,
            "a gate still refuses this copy, so the deferral is not what this "
            "test is measuring any more: %s" % caught.exception)
        # Cleared so a transport reach in a keyed environment does not fail a
        # later assertion in this test.
        self.requests.clear()

    def test_the_deferred_verdict_is_machine_readable_per_lead(self):
        """DEFERRED by operator decision, 2026-10-04. Not abandoned.

        Until that decision this read the verdict off `FactoryRefused.report`.
        There is no refusal to carry it now, so it is read off the RETURNED
        report - and that is the whole value of keeping the call: an operator
        can ask a zero-write dry run which stored sequences the ladder would
        refuse, and get a parseable answer per lead, before TASK-979 turns the
        refusal back on.

        The rungs and the ask ranks are asserted too, not just the flag, so a
        stub writing `{"refused": True}` and calling nothing could not pass.
        """
        self.given(LADDER_BAD)
        leads = self.dry_run()["sequencegate"]["leads"]
        self.assertEqual(1, len(leads))
        self.assertEqual("rec-1/rec-1-c1", leads[0]["lead"])
        ladder = leads[0]["role_ladder"]
        self.assertTrue(ladder["refused"])
        self.assertEqual([("bump_without_thread", "em2")],
                         [(f["check"], f["step"]) for f in ladder["failures"]])
        self.assertEqual(list(sequencegate.ROLE_LADDER),
                         [ladder["roles"][key]
                          for key in sequencegate.STEP_KEYS])
        self.assertNotIn(None, [ladder["asks"][key]
                                for key in sequencegate.STEP_KEYS])

    # -------------------------------------------------------------- the control

    def test_a_sequence_built_to_the_ladder_reaches_the_projection(self):
        """WITHOUT THIS THE TESTS ABOVE PROVE NOTHING.

        A `stage()` that refused every run would satisfy every negative
        assertion in this module. The same fixture, one body different, must
        run all the way to the dry-run projection and be PROJECTED - five
        steps, no missing copy.
        """
        self.given(LADDER_GOOD)
        report = self.dry_run()
        self.assertFalse(report["live"])
        self.assertIn("dry run: nothing was sent", report["did"])
        self.assertEqual(["em1", "em2", "em3", "em4", "em5"],
                         [step["step_key"]
                          for step in report["plan"]["provider_sequence"]])
        self.assertEqual([], report["plan"]["leads"][0]["missing_copy"])
        self.assertNothingReachedTheProvider()

    def test_the_ladders_verdict_is_on_the_passing_report_too(self):
        """"The ladder holds" and "nobody applied the ladder" must differ.

        The rung each step was credited with is asserted, not just the
        verdict: a stub writing `{"refused": False}` and calling nothing would
        satisfy the flag and could not produce these five roles.
        """
        self.given(LADDER_GOOD)
        report = self.dry_run()
        ladder = report["sequencegate"]["leads"][0]["role_ladder"]
        self.assertFalse(ladder["refused"])
        self.assertEqual([], ladder["failures"])
        self.assertEqual(list(sequencegate.ROLE_LADDER),
                         [ladder["roles"][key]
                          for key in sequencegate.STEP_KEYS])
        ranks = [ladder["asks"][key] for key in sequencegate.STEP_KEYS]
        self.assertNotIn(None, ranks, ranks)
        self.assertEqual(ranks, sorted(ranks, reverse=True), ranks)

    # ------------------------------------------- the ladder is what refuses

    def test_no_other_guard_on_this_path_refuses_the_violating_fixture(self):
        """What the retired bypass test was really for, kept honest.

        It used to patch `role_ladder` to refuse nothing and assert the
        campaign then reached the projection - evidence that the refusal was
        the LADDER's and not another guard firing first. With the raise
        deferred that assertion is now true whatever the ladder says, so it
        could not fail and a test that cannot fail is worse than none.

        What it was protecting is still worth pinning: that NOTHING ELSE on
        this path refuses this fixture. Asserted directly, by running the
        violating campaign with the ladder patched to REFUSE EVERYTHING and
        requiring that the stage still completes - which is only true because
        the raise is deferred, and which will fail the moment TASK-979 turns
        it back on. That is the intended signal: this test is the one that
        tells the next person the deferral is over.
        """
        self.given(LADDER_BAD)
        refuses_everything = {
            "refused": True, "why": "everything",
            "failures": [{"check": "role_unreadable", "step": "em1",
                          "why": "refuses everything, on purpose"}],
            "roles": {}, "asks": {}}
        with mock.patch.object(sequencegate, "role_ladder",
                               return_value=refuses_everything):
            report = self.dry_run()
        self.assertIn("dry run: nothing was sent", report["did"])
        self.assertTrue(report["sequencegate"]["passed"])
        self.assertNothingReachedTheProvider()


if __name__ == "__main__":
    unittest.main()
