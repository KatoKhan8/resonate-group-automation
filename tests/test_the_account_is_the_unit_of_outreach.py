"""One company's limit is not one person's limit.

`eligibility._separation` asks whether two touches to *one person* land too
close together. It filters the event log by contact key, so it cannot see a
second decision maker at the same company on the same day - and account-based
outreach is the thing this system claims to do. `ACCOUNT-OUTREACH.md` opens by
saying the account is the unit of outreach.

`fatigue.account_check` asks the company-level question and emits BLOCK when
either limit is past: more than `account.max_touches_per_week` touches across
every contact, or more than `account.max_active_contacts` decision makers
worked at once. `revival` and `oooreturn` have always enforced it.
`eligibility.decide` did not - `fatigue` had no importer in `eligibility` at
all - so the ordinary cadence, which sends far more than either exceptional
path, could put a company past a limit those paths respect.

Determinism is the reason this is a held reason computed from the record rather
than from a clock. `account_check` is called with `at=None`, which makes it
derive its window from the last confirmed touch on the record. That is the same
property `_separation` documents when it uses cadence days instead of a
timestamp: a re-run has to reach the same verdict.
"""
import unittest

from src import eligibility, fatigue


def touched(count, key="a", at="2026-09-08T10:00:00+00:00"):
    """A record whose company has `count` confirmed touches this week.

    `push_marked` is what confirms a touch - `touch.CONFIRMING_EVENTS` maps it
    to `sent`, which is in `CONFIRMED_STATES`. Building the record from the
    event log rather than from an invented `confirmed_touches` key matters:
    `account.graph` is the canonical answer to every account-level question and
    it walks the events, so a fixture that shortcuts it would prove the guard
    works against a shape the system never produces.
    """
    return {
        "id": "acme", "client": "demo", "company": "Acme",
        "state": "ready",
        "contacts": [{"key": key, "name": "Ada L", "title": "COO",
                      "email": "ada@acme.test", "linkedin": "x"}],
        "events": [{"type": "push_marked", "contact": key, "at": at,
                    "channel": "email", "step": f"s{i}", "day": i}
                   for i in range(count)],
    }


class TheCompanyLevelLimitExists(unittest.TestCase):
    """First half: the computation is real and says no."""

    def test_the_weekly_account_limit_has_a_default(self):
        rules = fatigue.limits({})
        self.assertIn("account.max_touches_per_week", rules)
        self.assertTrue(rules["account.max_touches_per_week"]["value"])

    def test_it_is_a_different_question_from_the_per_person_one(self):
        """If these were the same number the account layer would add
        nothing, and the gap would not be worth a guard."""
        rules = fatigue.limits({})
        self.assertNotEqual(rules["account.max_touches_per_week"]["value"],
                            rules["contact.max_touches_per_week"]["value"])


class TheDecisionConsultsIt(unittest.TestCase):
    """Second half, and the one that was missing: the send decision asks."""

    def test_eligibility_has_an_account_fatigue_reason(self):
        self.assertTrue(getattr(eligibility, "HELD_ACCOUNT_FATIGUE", None))

    def test_that_reason_is_in_the_vocabulary(self):
        """`REASONS` is the stable, greppable, countable set of codes."""
        self.assertIn(eligibility.HELD_ACCOUNT_FATIGUE, eligibility.REASONS)

    def test_that_reason_is_explained_to_an_operator(self):
        """A verdict code nobody can read is a verdict nobody acts on.
        `HUMAN` is the prose behind each code."""
        self.assertIn(eligibility.HELD_ACCOUNT_FATIGUE, eligibility.HUMAN)
        self.assertTrue(eligibility.HUMAN[eligibility.HELD_ACCOUNT_FATIGUE])

    def test_the_check_returns_the_reason_when_the_company_is_past_policy(self):
        limit = fatigue.limits({})["account.max_touches_per_week"]["value"]
        rec = touched(limit + 2)
        self.assertEqual(
            eligibility._account_fatigue(rec, rec["contacts"][0], {}),
            eligibility.HELD_ACCOUNT_FATIGUE)

    def test_a_quiet_company_is_not_held(self):
        """Or the guard is a ban and every campaign stops."""
        self.assertIsNone(
            eligibility._account_fatigue(touched(0), {"key": "a"}, {}))

    def test_it_is_deterministic_across_repeated_calls(self):
        """`at` is left None so the window comes from the record. A guard
        that consulted the clock would answer differently on a re-run, which
        is exactly what `_separation` uses cadence days to avoid."""
        rec = touched(fatigue.limits({})["account.max_touches_per_week"]["value"] + 2)
        first = eligibility._account_fatigue(rec, rec["contacts"][0], {})
        second = eligibility._account_fatigue(rec, rec["contacts"][0], {})
        self.assertEqual(first, second)


class TheDecisionItselfHoldsIt(unittest.TestCase):
    """The tests above call `_account_fatigue` directly, and that is not
    enough: deleting the call from `decide` broke none of them, which is the
    same defect - a correct computation nothing consumes - reproduced inside
    the fix for it. These go through `decide`.
    """

    def limit(self):
        return fatigue.limits({})["account.max_touches_per_week"]["value"]

    def decide_for(self, count):
        rec = touched(count)
        rec["contacts"][0]["selected"] = True
        timeline = {"a": {"s99": {"channel": "email", "day": 30,
                                  "subject": "x", "body": "y"}}}
        return eligibility.decide(rec, rec["contacts"][0], "s99",
                                  timeline=timeline, config={})

    def test_a_company_past_its_weekly_limit_is_held(self):
        verdict = self.decide_for(self.limit() + 2)
        self.assertEqual(verdict["verdict"], eligibility.HELD)
        self.assertIn(eligibility.HELD_ACCOUNT_FATIGUE, verdict["reasons"])

    def test_a_quiet_company_is_not_held_for_fatigue(self):
        """Or every campaign stops and the guard is a ban."""
        self.assertNotIn(eligibility.HELD_ACCOUNT_FATIGUE,
                         self.decide_for(0)["reasons"])

    def test_it_is_asked_before_any_content_work(self):
        """A held account should cost no lint and no claim check, and a
        well-linted draft should not make a worked-out company eligible.
        The draft here has no verification evidence at all, so a content
        check reaching it first would say something else."""
        verdict = self.decide_for(self.limit() + 2)
        self.assertEqual(verdict["reasons"], [eligibility.HELD_ACCOUNT_FATIGUE])


if __name__ == "__main__":
    unittest.main()
