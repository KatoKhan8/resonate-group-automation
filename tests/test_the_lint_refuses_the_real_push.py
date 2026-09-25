#!/usr/bin/env python3
"""The copy lint refuses the REAL push, and the proof is a refusal on the send path.

TASK-290. The original TASK-277 delivery wired the lint into `src/push.py`
through `run_with_copylint`, which nothing called, and proved it with eight
tests that called it directly. The production session rejected that:

  - `run_with_copylint` was called by nothing;
  - `src/push.py` is NOT the send path - its `run()` raises on `live=True`:
    "live push is not implemented in this build... No code here can reach
    EmailBison or HeyReach.";
  - the real path is `scripts/batch1_push.py` -> `bisonfactory.stage`.

THIS FILE asserts on the REAL send path. Every test drives `bisonfactory.stage`
against a fake provider that counts what it was asked to do. None of them
calls the lint directly. What they assert is the EFFECT: the push refuses,
the refusal names the lead and the rule, and the provider was never touched.

## STATUS: ALL GREEN, 2026-09-25

Lane D landed the wiring in `bisonfactory._refuse_copylint` before this file
was written. `_refuse_copylint(plan, recs, report)` is called in `stage()`
BEFORE `bison.bound_workspace()` and before any provider write. Every
assertion below passes because the wiring is already in place.

This file exists so the lane that re-wires (if it ever needs to) can take it
whole. If the wiring is removed, every test here goes red.
"""
import unittest

from src import (approval, bisonfactory, cadence, campaigns, copylint, store,
                 workspaces)
from tests.base import QueueTest
from tests.test_staging_a_campaign_twice_builds_one import FakeBison
from tests.test_staging_refuses_colliding_contacts import patch_collision_empty

CID = "camp-lint-refuses-push"

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
    """A provider that counts the FIRST thing `stage` asks it.

    `bound_workspace` is the tenancy read and it happens before any write.
    A lint that ran after it would still be before the attach, but this
    counter separates "before the provider" from "before the attach."
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
    """Every assertion driven through `bisonfactory.stage`, never through
    `push.run` or the lint directly."""

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

        row = campaigns.new_campaign(CID, "productive", "Lint refuses push")
        row["cadence_steps"] = [dict(s) for s in
                                cadence.steps_for(None, config=CONFIG)]
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

    # --- Rule 1: a batch containing a lead whose copy breaks a lint rule
    #     CANNOT be staged. Assert on the PUSH refusing.

    def test_a_lead_whose_copy_breaks_a_rule_cannot_be_staged(self):
        """The push refuses, not just the lint."""
        self.given(record(body=CLEAN_BODY.replace(
            "That is a visibility problem",
            "That is a visibility problem - and a costly one")))
        said = self.refusal()
        self.assertIn("rec-northwind/rec-northwind-c1", said)
        self.assertIn("dash", said)

    # --- Rule 2: the refusal names the lead and the rule.

    def test_the_refusal_names_the_lead_and_the_rule(self):
        """The sentence an operator reads carries the lint's own words."""
        self.given(record(body=CLEAN_BODY.replace(
            "a visibility problem", "a seamless, robust problem")))
        said = self.refusal()
        self.assertIn("buzzword", said)
        self.assertIn("rec-northwind/rec-northwind-c1", said)

    # --- Rule 3: the lint runs BEFORE any provider write, not after.

    def test_the_lint_runs_before_any_provider_write(self):
        """ISSUE-037 is the counter-example: the blank-render gate refuses
        after the attach and does not roll back."""
        self.given(record(body=CLEAN_BODY.replace(
            "a visibility problem", "a robust problem")))
        self.refusal()
        self.assertEqual(self.bison.touched(), CountingBison.UNTOUCHED)

    # --- Rule 4: a rule added later is enforced automatically.

    def test_a_rule_added_later_is_enforced_without_touching_the_call_site(self):
        """The wiring reads the rule SET, it does not enumerate rules."""
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
        self.assertEqual(self.bison.touched(), CountingBison.UNTOUCHED)


if __name__ == "__main__":
    unittest.main()
