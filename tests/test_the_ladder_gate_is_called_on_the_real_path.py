#!/usr/bin/env python3
"""`sequencegate.role_ladder` IS CALLED, and its refusal STOPS the push.

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

  - A sequence that breaks ONE ladder rule is REFUSED by the real staging
    entrypoint, and the refusal names the check and the step. "It raised"
    would be satisfied by the cadence guard, the qualification check, the
    tenancy check, the copy lint or `sequencegate.check`, none of which is
    evidence that the LADDER was consulted.

  - The SAME fixture, differing in one body only, is NOT refused and reaches
    the dry-run projection. Without this half the test above is satisfied by
    a gate that refuses everything, which is exactly as useless as one that
    refuses nothing - and this repository has shipped both.

  - The ladder's verdict is ON the report, per lead, with the rung each step
    was credited with. "It ran" is then observable rather than inferred from
    the absence of an exception, which is the distinction a check that did
    not run and a check that passed otherwise collapse into.

  - Nothing reaches the provider transport in either case.

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

    def test_a_ladder_violating_sequence_is_refused_by_the_real_path(self):
        """The refusal, by effect, through `bisonfactory.stage`.

        Attributable: the gate by name, the LADDER's check by name, and the
        step. No other gate on this path emits `bump_without_thread`.
        """
        self.given(LADDER_BAD)
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            self.dry_run()
        message = str(caught.exception)
        self.assertIn("sequence-level gate", message)
        self.assertIn("bump_without_thread", message)
        self.assertIn("em2", message)
        self.assertIn("rec-1/rec-1-c1", message)
        self.assertNothingReachedTheProvider()

    def test_the_refusal_is_the_same_one_a_live_run_would_give(self):
        """A dry run rehearses the real decision, ladder included."""
        self.given(LADDER_BAD)
        with self.assertRaises(bisonfactory.FactoryRefused) as dry:
            self.dry_run()
        with self.assertRaises(bisonfactory.FactoryRefused) as live:
            bisonfactory.stage(CID, config=five_step_config(), live=True)
        self.assertEqual(str(dry.exception), str(live.exception))
        self.assertNothingReachedTheProvider()

    def test_the_ladders_verdict_is_on_the_refusals_report(self):
        """`FactoryRefused` carries the report, so the verdict is parseable.

        A caller that has to read the refusal out of the prose of an exception
        message is reading prose, which is the reason `_refuse_copylint` puts
        its own verdict on the report.
        """
        self.given(LADDER_BAD)
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            self.dry_run()
        leads = caught.exception.report["sequencegate"]["leads"]
        self.assertEqual(1, len(leads))
        ladder = leads[0]["role_ladder"]
        self.assertTrue(ladder["refused"])
        self.assertEqual([("bump_without_thread", "em2")],
                         [(f["check"], f["step"]) for f in ladder["failures"]])

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

    def test_bypassing_the_ladder_lets_the_same_bad_sequence_through(self):
        """The refusal is the LADDER's, not some other guard firing first.

        `role_ladder` is replaced by a verdict that refuses nothing, and the
        identical campaign then reaches the projection. This is the mutation
        the manual mutation performs, pinned here so a future edit that makes
        some other gate refuse this fixture is caught as a change of meaning
        rather than silently keeping the test green.
        """
        self.given(LADDER_BAD)
        allows_everything = {"refused": False, "why": "", "failures": [],
                             "roles": {}, "asks": {}}
        with mock.patch.object(sequencegate, "role_ladder",
                               return_value=allows_everything):
            report = self.dry_run()
        self.assertIn("dry run: nothing was sent", report["did"])
        self.assertNothingReachedTheProvider()


if __name__ == "__main__":
    unittest.main()
