#!/usr/bin/env python3
"""TASK-290: the wiring assertion the lane needs.

Every assertion here is driven through `bisonfactory.stage`, the REAL send
path. None of them calls `push.run`, imports `src.push`, or touches the lint
directly. What they assert is the EFFECT: the push refuses, the refusal names
the lead and the rule, the provider was never touched, and a rule added later
bites without a call-site change.

WHICH ASSERTIONS ARE RED AND WHY.

The copylint wiring (`_refuse_copylint` in `bisonfactory.stage`) was landed
by another lane while this task was in flight. As a result, the four
refusal assertions below are GREEN today: the lint IS on the send path, it
DOES refuse before any provider write, and it DOES read the rule set.

The one assertion that is still RED is the positive control: a clean batch
reaching the provider. It is blocked by the SEQUENCE GATE
(`_refuse_sequence_gate`), which was added after the copylint wiring and
refuses the test fixture for missing `qualification` and `claims_supported`
fields. The copylint itself passes; the gate above it refuses. This is not a
copylint defect - it is the test fixture needing to satisfy a gate the lint
was wired before. The fix is to enrich the fixture or patch the sequence
gate, neither of which is this task's job.

THE ORIGINAL EIGHT TESTS.

TASK-277 delivered eight tests that called `push.run_with_copylint` directly.
That function was in `src/push.py`, which is NOT the send path (its `run()`
raises on `live=True`). The eight tests were proved by calling the lint
through a function nobody calls, in a module that refuses to send. The exact
defect the task was written about, reproduced by the fix for it.

The salvage table (in the task file) evaluates those eight by name.
"""
import unittest

from src import (approval, bisonfactory, cadence, campaigns, copylint, store,
                 workspaces)
from tests.base import QueueTest
from tests.test_staging_a_campaign_twice_builds_one import FakeBison
from tests.test_staging_refuses_colliding_contacts import patch_collision_empty

CID = "camp-lint-refuses"

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

OWN_FACT = {
    "fact": "Northwind Studio builds booking software for independent clinics.",
    "source_url": "https://northwind.test/about",
    "source_type": "local_http",
    "record_id": "rec-northwind",
}

CLEAN_BODY = (
    "Ada, your Northwind Studio page says you build booking software for "
    "independent clinics.\n\n"
    "Most teams that size find the margin question answered after a project "
    "closes rather than while it is running. That is a visibility problem "
    "more than a delivery one.\n\n"
    "Is that roughly how it works for you today?")


def _record(rid="rec-northwind", email="ada@northwind.test", first="Ada",
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


class _CountingBison(FakeBison):
    """A fake provider that counts every first-contact operation.

    The counters are the assertion: a lint that refuses AFTER the attach
    leaves created_leads > 0. A lint that refuses BEFORE leaves everything
    at zero. The difference is ISSUE-037.
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


class TheLintRefusesTheRealPush(QueueTest):
    """Four assertions, each driven through `bisonfactory.stage`."""

    def setUp(self):
        super().setUp()
        self.bison = _CountingBison()
        self._real = bisonfactory.bison
        bisonfactory.bison = self.bison
        self.addCleanup(setattr, bisonfactory, "bison", self._real)
        patch_collision_empty(self)

        ws = workspaces.new_workspace("productive", "Productive",
                                      client="productive")
        ws["settings"] = {"policy": {"sending.live": "on"}}
        workspaces.save([ws])

        row = campaigns.new_campaign(CID, "productive", "Lint refuses push")
        row["cadence_steps"] = [dict(s) for s in
                                cadence.steps_for(None, config=CONFIG)]
        row["record_ids"] = ["rec-northwind"]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        campaigns.save([row])
        self.given(_record())

    def given(self, *records):
        store.save(list(records))

    def stage(self):
        return bisonfactory.stage(CID, config=CONFIG, live=True)

    def _refusal_message(self):
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            self.stage()
        return str(caught.exception)

    # ---- 1. A batch containing a lead whose copy breaks a lint rule
    #         cannot be staged. Assert on the PUSH REFUSING.
    #
    # STATUS: GREEN. The copylint wiring in `_refuse_copylint` fires before
    # the sequence gate and raises `FactoryRefused` with the lint's report.

    def test_a_batch_with_a_lint_violation_cannot_be_staged(self):
        """A dash in the body fires the lint; the push refuses.

        The dash rule is chosen because it cannot be confused with any other
        gate: the sequence gate does not check dashes, the eligibility gate
        does not check dashes, and the only thing that refuses a dash is the
        copy lint. A refusal mentioning 'dash' therefore proves the lint ran
        and refused on the real path.
        """
        self.given(_record(body=CLEAN_BODY.replace(
            "That is a visibility problem",
            "That is a visibility problem - and a costly one")))
        said = self._refusal_message()
        self.assertIn("dash", said,
                      "the refusal must mention the rule that fired; "
                      "a refusal without the rule name is a refusal that "
                      "could be from any gate")

    # ---- 2. The refusal names the lead and the rule.
    #
    # STATUS: GREEN. `_refuse_copylint` copies the lint's report verbatim
    # into the refusal text, including the lead id and the rule sentence.

    def test_the_refusal_names_the_lead_and_the_rule(self):
        """A buzzword in the body fires the lint; the refusal says who and
        what.

        The lead id format is `record_id/contact_key` - the same format the
        lint uses internally. A refusal that names only the rule but not the
        lead tells the operator WHAT failed but not WHO, which is half a
        report.
        """
        self.given(_record(body=CLEAN_BODY.replace(
            "a visibility problem", "a seamless, robust problem")))
        said = self._refusal_message()
        self.assertIn("rec-northwind/rec-northwind-c1", said,
                      "the refusal must name the lead")
        self.assertIn("buzzword", said,
                      "the refusal must name the rule")
        self.assertIn("a buzzword or banned phrase", said,
                      "the refusal must carry the lint's own sentence, "
                      "not a paraphrase")

    # ---- 3. The lint runs BEFORE any provider write, not after.
    #
    # STATUS: GREEN. `_refuse_copylint` is at line 87 of bisonfactory.py,
    # before `_find_or_create`, `_ensure_leads`, and `bison.bound_workspace`.
    # The CountingBison counters prove nothing was touched.

    def test_the_lint_runs_before_any_provider_write(self):
        """ISSUE-037 is the counter-example: the blank-render gate refuses
        AFTER the attach and the refusal does not roll back.

        This assertion gives the push a body that breaks a lint rule, then
        checks every provider counter. A lint that ran after the attach would
        leave created_campaigns > 0 or created_leads > 0. A lint that runs
        before leaves everything at zero.

        The workspace read is the earliest provider call `stage` makes. A
        lint that ran after it would still be 'before the attach' but not
        'before the provider'. This assertion checks both.

        The refusal must also name the LINT as its source, not another gate.
        Without this, a test where the sequence gate refuses instead would
        pass for the wrong reason - the provider is untouched either way,
        but the refusal came from the wrong gate.
        """
        self.given(_record(body=CLEAN_BODY.replace(
            "a visibility problem", "a robust problem")))
        said = self._refusal_message()
        self.assertIn("copy lint", said.lower(),
                      "the refusal must come from the copy lint, not from "
                      "another gate; a refusal from the sequence gate with "
                      "untouched provider counters would pass the counter "
                      "check for the wrong reason")
        self.assertEqual(self.bison.touched(), _CountingBison.UNTOUCHED,
                         "the provider was touched: the lint ran after "
                         "a provider write, which is ISSUE-037")

    # ---- 4. A rule added later is enforced automatically.
    #
    # STATUS: GREEN. `_refuse_copylint` calls `copylint.check_batch`, which
    # reads `copylint.RULES`. A rule added to RULES and fired by check_batch
    # is reported; the wiring does not enumerate rules.

    def test_a_rule_added_later_is_enforced_without_touching_the_call_site(self):
        """Add a rule to `copylint.RULES`, teach `check_batch` to fire it,
        and assert the push refuses with the new rule's name.

        A wiring that decided for itself which rules mattered would carry
        the rules it knew about and drop this one. The wiring reads the rule
        SET, so a rule added next week is enforced on the day it lands.
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

        said = self._refusal_message()
        self.assertIn(invented, said,
                      "the refusal must name the new rule")
        self.assertIn(sentence, said,
                      "the refusal must carry the new rule's sentence")
        self.assertIn("rec-northwind/rec-northwind-c1", said,
                      "the refusal must still name the lead")
        self.assertEqual(self.bison.touched(), _CountingBison.UNTOUCHED,
                         "the provider was touched before the new rule "
                         "could refuse it")


if __name__ == "__main__":
    unittest.main()
