"""Which copy a touch actually carried, and why nothing knew.

`account.touches` reads `variant_id` off the event and its comment says
attribution depends on it. `variants.journey_of` filters touches on that
id. `variants.results_from` counts exposures from that journey. And
nothing anywhere wrote a variant onto an event.

So every journey was empty, every tally was `{}`, and every experiment
reported INSUFFICIENT_DATA whatever had been sent - which is exactly what
a working evaluator waiting for volume looks like. The screens said "not
enough data yet" and would have said it forever.

The fix is one line's worth of fields on the event, and the tests below
are what stop it being one line's worth of silence again.
"""
import unittest

from src import account, events, push, store, variants
from tests.campaignbase import CampaignTest, contact

STEP = {"channel": "email", "day": 1, "subject": "s", "body": "b",
        "variant_id": "v-b", "variant_style": "casual", "variant_version": 2}

# Fixed, and passed explicitly. `mark_pushed` stamps `store.now()` when it
# is not given a time, so a fixture that let it default was comparing a
# real clock against a hard-coded reply date - it passed until the day the
# clock caught up with the date, and then failed with no code change.
SENT_AT = "2026-01-05T09:00:00+00:00"
REPLIED_AT = "2026-02-01T09:00:00+00:00"


def a_record(**kw):
    rec = {"id": "acme", "company": "Acme", "domain": "acme.test",
           "client": "demo", "events": [], "cadence": {},
           "contacts": [contact("c1", "A Person", "a@acme.test")]}
    rec.update(kw)
    return rec


def push_step(rec, step=None, contact_key="c1", step_key="day1", **kw):
    step = STEP if step is None else step
    rec.setdefault("cadence", {}).setdefault(contact_key, {})[step_key] = \
        dict(step)
    kw.setdefault("at", SENT_AT)
    return push.mark_pushed(
        rec, contact_key, step_key,
        push.push_id(rec, contact_key, step_key, step.get("channel", "email")),
        **kw)


class TheEventRecordsTheCopyItCarried(unittest.TestCase):

    def test_the_variant_reaches_the_event(self):
        rec = a_record()
        push_step(rec)
        entry = next(e for e in rec["events"]
                     if e["type"] == events.PUSH_MARKED)
        self.assertEqual(entry["variant_id"], "v-b")
        self.assertEqual(entry["variant_style"], "casual")
        self.assertEqual(entry["variant_version"], 2)

    def test_the_touch_carries_it_back(self):
        rec = a_record()
        push_step(rec)
        touch = account.touches(rec, "c1", confirmed_only=True)[0]
        self.assertEqual(touch["variant_id"], "v-b")
        self.assertEqual(touch["variant_version"], 2)

    def test_a_step_with_no_variant_records_none(self):
        """Unversioned copy is a real state. It must not acquire a variant
        id it never had."""
        rec = a_record()
        push_step(rec, step={"channel": "email", "day": 1})
        entry = next(e for e in rec["events"]
                     if e["type"] == events.PUSH_MARKED)
        self.assertIsNone(entry.get("variant_id"))
        self.assertEqual(variants.journey_of(rec, "c1"), [])

    def test_the_time_the_caller_gave_reaches_the_event(self):
        """`at` was applied to `step["pushed_at"]` and dropped from the
        event, so the step said when the caller sent it and the event said
        when the code ran. `account.touches` reads the event, and both
        attribution and exposure count from that - a backfill or a replay
        stamped today's date onto every touch it recreated.

        Found by a test that passed for a day and then failed with no code
        change, because the wall clock caught up with a fixture's reply
        date.
        """
        rec = a_record()
        push_step(rec, at="2026-01-05T09:00:00+00:00")
        entry = next(e for e in rec["events"]
                     if e["type"] == events.PUSH_MARKED)
        self.assertEqual(entry["at"], "2026-01-05T09:00:00+00:00")
        self.assertEqual(
            account.touches(rec, "c1", confirmed_only=True)[0]["at"],
            "2026-01-05T09:00:00+00:00")

    def test_without_one_it_is_stamped_now(self):
        """The ordinary path. A real send has no time to be told."""
        from src import store

        rec = a_record()
        push.mark_pushed(rec, "c1", "day1", "acme:c1:day1:email")
        entry = next(e for e in rec["events"]
                     if e["type"] == events.PUSH_MARKED)
        self.assertEqual(entry["at"][:10], store.now()[:10])

    def test_the_sender_is_still_recorded(self):
        """The variant travels for the same reason the sender does, and
        adding one must not have displaced the other."""
        rec = a_record()
        rec["contacts"][0]["sender_assignment"] = {
            "email": {"sender_id": "mark", "display_name": "Mark Weber",
                      "account_id": "inbox-1"}}
        push_step(rec)
        entry = next(e for e in rec["events"]
                     if e["type"] == events.PUSH_MARKED)
        self.assertEqual(entry["sender_id"], "mark")


class TheJourneyIsNoLongerEmpty(unittest.TestCase):

    def test_a_confirmed_touch_is_an_exposure(self):
        rec = a_record()
        push_step(rec)
        found = variants.results_from([rec], "day1")
        self.assertEqual(found["v-b"]["exposures"], 1)

    def test_before_the_fix_it_counted_nothing(self):
        """The shape of the defect, kept as a test. An event written
        without a variant produces an empty journey - which is correct for
        that event, and was what every event looked like."""
        rec = a_record(events=[{
            "type": events.PUSH_MARKED, "contact": "c1", "channel": "email",
            "step": "day1", "at": "2026-08-01T09:00:00+00:00",
            "sender_id": "mark"}])
        self.assertEqual(variants.journey_of(rec, "c1"), [])
        self.assertEqual(variants.results_from([rec], "day1"), {})

    def test_a_planned_touch_is_not_an_exposure(self):
        """A denominator under a message nobody received."""
        rec = a_record(events=[{
            "type": events.PUSH_PREPARED, "contact": "c1",
            "channel": "email", "step": "day1",
            "at": "2026-08-01T09:00:00+00:00", "variant_id": "v-b"}])
        self.assertEqual(variants.journey_of(rec, "c1"), [])

    def test_a_reply_is_credited_to_the_last_variant_before_it(self):
        """Asked of the objective being counted. The default is positive
        replies, so a plain reply is an exposure with no outcome - which is
        correct, and is a different thing from not being counted at all."""
        rec = a_record()
        push_step(rec)
        rec["events"].append({
            "type": events.REPLY_RECEIVED, "contact": "c1",
            "channel": "email", "at": REPLIED_AT})

        default = variants.results_from([rec], "day1")
        self.assertEqual(default["v-b"]["exposures"], 1)
        self.assertEqual(default["v-b"][variants.POSITIVE_REPLIES], 0)

        counted = variants.results_from([rec], "day1",
                                        objective=variants.REPLIES)
        self.assertEqual(counted["v-b"][variants.REPLIES], 1)

    def test_a_positive_reply_is_credited_under_the_default_objective(self):
        rec = a_record()
        push_step(rec)
        rec["events"].append({
            "type": events.POSITIVE_REPLY_DETECTED, "contact": "c1",
            "channel": "email", "at": REPLIED_AT})
        found = variants.results_from([rec], "day1")
        self.assertEqual(found["v-b"][variants.POSITIVE_REPLIES], 1)

    def test_two_variants_are_counted_separately(self):
        rows = []
        for i, variant_id in enumerate(("v-a", "v-b")):
            rec = a_record(id=f"acme{i}")
            push_step(rec, step=dict(STEP, variant_id=variant_id))
            rows.append(rec)
        found = variants.results_from(rows, "day1")
        self.assertEqual(sorted(found), ["v-a", "v-b"])
        self.assertEqual(found["v-a"]["exposures"], 1)
        self.assertEqual(found["v-b"]["exposures"], 1)


class TheCopyThatWentOutIsWhatIsRecorded(unittest.TestCase):

    def test_the_step_as_sent_wins_over_the_step_as_it_stands_now(self):
        """A variant edited after a send would otherwise re-label a message
        nobody sent, and pool two wordings under one id."""
        rec = a_record()
        went_out = dict(STEP, variant_id="v-b", variant_version=2)
        rec.setdefault("cadence", {}).setdefault("c1", {})["day1"] = \
            dict(STEP, variant_id="v-c", variant_version=9)

        push.mark_pushed(rec, "c1", "day1",
                         push.push_id(rec, "c1", "day1", "email"),
                         at=SENT_AT, sent=went_out)
        entry = next(e for e in rec["events"]
                     if e["type"] == events.PUSH_MARKED)
        self.assertEqual(entry["variant_id"], "v-b")
        self.assertEqual(entry["variant_version"], 2)

    def test_without_it_the_stored_step_is_used(self):
        """The ordinary path, where the record still holds what was sent."""
        rec = a_record()
        push_step(rec)
        entry = next(e for e in rec["events"]
                     if e["type"] == events.PUSH_MARKED)
        self.assertEqual(entry["variant_id"], "v-b")

    def test_the_version_distinguishes_two_wordings(self):
        """Same variant id, edited copy. Without the version the two are
        one row and the rate is an average of two different messages."""
        first, second = a_record(id="a1"), a_record(id="a2")
        push_step(first, step=dict(STEP, variant_version=1))
        push_step(second, step=dict(STEP, variant_version=2))
        versions = {variants.journey_of(rec, "c1")[0]["version"]
                    for rec in (first, second)}
        self.assertEqual(versions, {1, 2})


class TheEvaluatorNowHasSomethingToRefuse(CampaignTest):
    """It said INSUFFICIENT_DATA before because nothing reached it. It
    should still say so on small numbers - for the right reason."""

    def test_one_exposure_is_still_not_enough(self):
        rec = a_record()
        push_step(rec)
        found = variants.results_from([rec], "day1")
        node = {"variants": [
            variants.variant("v-a", "short_direct", subject="s", body="b"),
            variants.variant("v-b", "casual", subject="s", body="b")]}
        verdict = variants.evaluate(node, found)
        self.assertEqual(verdict["state"], variants.INSUFFICIENT_DATA)

    def test_the_refusal_names_the_sample_rather_than_the_plumbing(self):
        rec = a_record()
        push_step(rec)
        node = {"variants": [
            variants.variant("v-b", "casual", subject="s", body="b")]}
        verdict = variants.evaluate(node, variants.results_from([rec], "day1"))
        self.assertTrue(verdict["why"])


if __name__ == "__main__":
    unittest.main()
