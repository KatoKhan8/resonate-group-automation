#!/usr/bin/env python3
"""The batch copy lint is on the REAL send path, and the proof is a refusal.

TASK-277, re-done. The first delivery added `push.run_with_copylint`, wired it
into `src/push.py`, and proved it with eight tests that called it directly.
Three things were wrong with that and they compound:

  - `run_with_copylint` was called by nothing;
  - all eight tests called it directly and none called `push.run`;
  - and `src/push.py` is NOT the send path. Its `run()` raises on `live=True`:
    "live push is not implemented in this build... No code here can reach
    EmailBison or HeyReach."

So the lint was wired into a module that refuses to send, through a function
nobody calls, proved by tests that call it directly. That is the exact defect
the task was written about, reproduced by the fix for it.

THE REAL PATH IS `scripts/batch1_push.py` -> `bisonfactory.stage`, and every
test here drives `bisonfactory.stage` against a fake provider that counts what
it was asked to do. None of them calls the lint, the wiring, or anything below
`stage`. What they assert is the EFFECT: the push refuses, the refusal names
the lead and the rule, and the provider was never touched.

## WHY THE PROVIDER COUNTERS ARE THE ASSERTION

A lint that refuses after the attach is ISSUE-037: the blank-render gate
refuses once the leads are already on the campaign and its refusal does not
roll back. "It raised" is therefore not enough - a gate can raise and still
have left a real campaign holding condemned leads. So every refusal test also
asserts that the fake provider created no campaign, created no lead, attached
nothing, and was not even asked which workspace it was bound to.

## AND WHY ONE OF THESE IS ABOUT IDENTITY

The lint's first rule is that step 1 opens on something the account's own
research supports. `packfacts` decides what "its own" means, and it decides it
by identity rather than presence: measured 2026-09-24, 50 of 71 job rows in
the research pilot belonged to a different company. The last test here gives a
record a perfectly good fact that belongs to somebody else and proves the push
refuses - which is the difference between a pack that is present and a pack
that is this account's.
"""
import unittest

from src import approval, bisonfactory, campaigns, copylint, store, workspaces
from tests.base import QueueTest
from tests.test_staging_a_campaign_twice_builds_one import FakeBison
from tests.test_staging_refuses_colliding_contacts import patch_collision_empty

CID = "camp-copylint"

#: One step, the shape EmailBison campaign 451 actually carries. The sequence
#: LENGTH is what the lint is told to expect, and a test below asserts that -
#: `copylint.STEPS_EXPECTED` is the operator's five-step target and checking a
#: one-step push against it would refuse for a reason that is about the
#: cadence rollout rather than about the copy.
CONFIG = {
    "email_sequence": {"title": "Resonate generated cadence",
                       "subject": "{SUBJECT}", "body": "<p>{BODY}</p>",
                       "wait_in_days": 3},
    "sending_window": {"days": ["monday", "tuesday", "wednesday", "thursday",
                                "friday"],
                       "start": "09:00", "end": "17:00",
                       "timezone": "Europe/Zagreb"},
    "providers": {"emailbison": {"workspace": 10}},
}

#: A fact the account's own site states, on the account's own domain. Nothing
#: here is a real company: `northwind.test` is a reserved TLD and the person
#: is invented, because a test must never carry a real prospect.
OWN_FACT = {
    "fact": "Northwind Studio builds booking software for independent clinics.",
    "source_url": "https://northwind.test/about",
    "source_type": "local_http",
    "record_id": "rec-northwind",
}

#: The same quality of fact, about somebody else, reached on somebody else's
#: domain. Presence-wise this record has research; identity-wise it has none.
SOMEBODY_ELSES_FACT = dict(OWN_FACT,
                           source_url="https://southgale.test/about")

CLEAN_BODY = (
    "Ada, your Northwind Studio page says you build booking software for "
    "independent clinics.\n\n"
    "Most teams that size find the margin question answered after a project "
    "closes rather than while it is running. That is a visibility problem "
    "more than a delivery one.\n\n"
    "Is that roughly how it works for you today?")


def record(rid="rec-northwind", email="ada@northwind.test", first="Ada",
           body=CLEAN_BODY, research=(OWN_FACT,), domain="northwind.test",
           company="Northwind Studio"):
    key = "%s-c1" % rid
    step = {"channel": "email", "subject": "how booking work is tracked",
            "body": body}
    step["approval"] = {"by": "operator", "at": "2026-09-24T00:00:00Z",
                        "fingerprint": approval.fingerprint(step)}
    return {"id": rid, "client": "productive", "domain": domain,
            "company": company, "state": "ready",
            "research": [dict(r, record_id=rid) for r in research],
            "cadence": {key: {"day1": step}},
            "contacts": [{"key": key, "email": email, "first_name": first,
                          "last_name": "Tester", "sendable": True,
                          "verified": True}]}


class CountingBison(FakeBison):
    """The fake provider, plus a count of the FIRST thing `stage` asks it.

    `bound_workspace` is the tenancy read and it happens before any write. A
    lint that ran after it would still be before the attach, and this counter
    is how "before the attach" is told apart from "before the provider".
    """

    def __init__(self):
        super().__init__()
        self.workspace_reads = 0

    def bound_workspace(self):
        self.workspace_reads += 1
        return super().bound_workspace()

    def touched(self):
        return {"workspace_reads": self.workspace_reads,
                "created_campaigns": self.created_campaigns,
                "created_leads": self.created_leads,
                "attached": sum(len(v) for v in self.members.values()),
                "sequences": len(self.steps)}

    UNTOUCHED = {"workspace_reads": 0, "created_campaigns": 0,
                 "created_leads": 0, "attached": 0, "sequences": 0}


class TheCopyLintIsOnTheSendPath(QueueTest):

    def setUp(self):
        super().setUp()
        self.bison = CountingBison()
        self._real = bisonfactory.bison
        bisonfactory.bison = self.bison
        self.addCleanup(setattr, bisonfactory, "bison", self._real)
        patch_collision_empty(self)

        ws = workspaces.new_workspace("productive", "Productive",
                                      client="productive")
        ws["settings"] = {"policy": {"sending.live": "on"}}
        workspaces.save([ws])

        row = campaigns.new_campaign(CID, "productive", "Copy lint test")
        row["record_ids"] = ["rec-northwind"]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        campaigns.save([row])
        self.given(record())

    def given(self, *records):
        store.save(list(records))

    def stage(self):
        return bisonfactory.stage(CID, config=CONFIG, live=True)

    def refusal(self):
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            self.stage()
        return str(caught.exception)

    # ------------------------------------------------------------ the control
    #
    # WITHOUT THIS THE REST PROVES NOTHING. A gate that refuses every batch is
    # indistinguishable from a gate that refuses the right ones, and this
    # repository has shipped a test that could not pass as well as tests that
    # could not fail.

    def test_a_batch_whose_copy_is_clean_is_staged(self):
        report = self.stage()
        self.assertFalse(report["copylint"]["refused"],
                         copylint.report_lines(report["copylint"]))
        self.assertEqual(self.bison.created_leads, 1)
        self.assertEqual(report["provider"]["readback"]["leads"], 1)

    def test_the_lint_is_told_this_plan_s_length_and_not_the_target(self):
        """One step is what this config sends, so one step is what is checked.

        `copylint.STEPS_EXPECTED` is five - the cadence the operator is moving
        to. A wiring that passed the constant would refuse this push for
        `empty_step`, which would be the cadence rollout wearing a copy
        lint's name.
        """
        report = self.stage()
        self.assertEqual(report["copylint"]["steps_expected"],
                         len(report["plan"]["sequence"]))
        self.assertNotEqual(copylint.STEPS_EXPECTED,
                            report["copylint"]["steps_expected"])

    # ------------------------------------------------------- the refusals

    def test_a_lead_whose_copy_breaks_a_rule_cannot_be_pushed(self):
        """Rule 1 of the task: assert on the PUSH refusing."""
        self.given(record(body=CLEAN_BODY.replace(
            "That is a visibility problem",
            "That is a visibility problem - and a costly one")))
        said = self.refusal()
        self.assertIn("rec-northwind/rec-northwind-c1", said)
        self.assertIn("dash", said)

    def test_the_refusal_names_the_lead_and_the_rule_in_the_lint_s_words(self):
        """Rule 2: the sentence a person reads is the LINT's, not ours."""
        self.given(record(body=CLEAN_BODY.replace(
            "a visibility problem", "a seamless, robust problem")))
        said = self.refusal()
        self.assertIn("buzzword", said)
        self.assertIn("a buzzword or banned phrase", said)
        self.assertIn("rec-northwind/rec-northwind-c1", said)

    def test_nothing_reaches_the_provider_when_the_lint_refuses(self):
        """Rule 3: BEFORE any provider write, not after.

        ISSUE-037 is the counter-example this exists against: the blank-render
        gate refuses after the attach and does not roll back, so a refusal
        there leaves a real campaign holding condemned leads.
        """
        self.given(record(body=CLEAN_BODY.replace(
            "a visibility problem", "a robust problem")))
        self.refusal()
        self.assertEqual(self.bison.touched(), CountingBison.UNTOUCHED)

    def test_a_rule_added_to_the_lint_later_is_enforced_here(self):
        """Rule 4: the wiring reads the rule set; it does not enumerate rules.

        A rule is added to this system by adding it to `copylint.RULES` and
        teaching `check_batch` to fire it. Both halves are done here, on a
        rule that did not exist when this wiring was written, and the push has
        to refuse and say its name. A wiring that decided for itself which
        rules mattered would carry the six it knew about and drop this one.
        """
        invented = "a_rule_written_next_week"
        sentence = "a rule nobody had written yet"
        rules, real = copylint.RULES, copylint.check_batch

        def fake(leads, packs=None, **kw):
            found = real(leads, packs, **kw)
            found["refused"] = True
            found["counts"][invented] = len(leads)
            found["offenders"][invented] = sorted(l["id"] for l in leads)
            found["rules"][invented] = sentence
            return found

        copylint.RULES = rules + ((invented, sentence),)
        copylint.check_batch = fake
        self.addCleanup(setattr, copylint, "check_batch", real)
        self.addCleanup(setattr, copylint, "RULES", rules)

        said = self.refusal()
        self.assertIn(invented, said)
        self.assertIn(sentence, said)
        self.assertIn("rec-northwind/rec-northwind-c1", said)
        self.assertEqual(self.bison.touched(), CountingBison.UNTOUCHED)

    # -------------------------------------------------- identity, not presence

    def test_a_lead_with_no_research_at_all_is_refused(self):
        self.given(record(research=()))
        said = self.refusal()
        self.assertIn("step1_without_pack_fact", said)
        self.assertEqual(self.bison.touched(), CountingBison.UNTOUCHED)

    def test_a_fact_that_belongs_to_another_company_supports_nothing(self):
        """The 50-of-71 defect, asserted through the send path.

        This record HAS research, the research is well formed, and its
        snippet contains every word the opener leans on. The only thing wrong
        with it is whose it is. A presence check calls this account covered;
        the push must refuse it.
        """
        self.given(record(research=(SOMEBODY_ELSES_FACT,)))
        said = self.refusal()
        self.assertIn("step1_without_pack_fact", said)
        self.assertIn("rec-northwind/rec-northwind-c1", said)
        self.assertEqual(self.bison.touched(), CountingBison.UNTOUCHED)

    def test_the_same_fact_on_the_account_s_own_domain_does_support_it(self):
        """The other half of the pair, so the test above cannot pass by
        refusing everything: identical words, this account's site, staged."""
        self.given(record(research=(OWN_FACT,)))
        report = self.stage()
        self.assertFalse(report["copylint"]["refused"])
        self.assertEqual(report["copylint"]["leads_with_a_pack"], 1)

    # ------------------------------------------------------------- dry run

    def test_a_dry_run_reports_the_refusal_without_raising(self):
        """A dry run reaches no provider, so it refuses nothing - but it must
        not report silence. The verdict is in the report either way, which is
        how an operator finds out before `--live` rather than during it."""
        self.given(record(research=()))
        report = bisonfactory.stage(CID, config=CONFIG, live=False)
        self.assertTrue(report["copylint"]["refused"])
        self.assertIn("rec-northwind/rec-northwind-c1",
                      report["copylint"]["offenders"]["step1_without_pack_fact"])
        self.assertEqual(self.bison.touched(), CountingBison.UNTOUCHED)


if __name__ == "__main__":
    unittest.main()
