"""Which step a reply followed, and which arm may claim it.

A cadence experiment asking whether seven steps beat four turns almost
entirely on where the replies arrive. If every reply lands by step three,
steps four to seven cost money and buy nothing - and comparing final
totals will never show that, because both arms end up in the same place
and the longer one looks slightly better for having had more chances.

The two things that make the number wrong, both tested here: crediting a
step that was confirmed *after* the reply, and crediting step one for a
reply that followed no confirmed touch at all.
"""
import unittest

from src import cadencearms as arms, cadencereplies as R, events

SEVEN = [{"key": f"s{i}", "day": d, "channel": "email",
          "template": "persona_pain"}
         for i, d in enumerate((1, 3, 7, 12, 18, 25, 35), start=1)]
FOUR = SEVEN[:4]


def an_experiment():
    return arms.experiment("cad-1",
                           [arms.arm("four", "4 steps", FOUR),
                            arms.arm("seven", "7 steps", SEVEN)])


def a_record(rid, arm_id, confirmed=0, reply_at=None, positive=False,
             classification=None, extra_touch_at=None):
    """One contact, `confirmed` steps delivered, optionally a reply."""
    rec = {"id": rid, "client": "demo", "company": rid, "events": [],
           "contacts": [{"key": "a", "name": "A", "email": "a@x.test"}],
           arms.ASSIGNMENT_KEY: {
               "experiment_id": "cad-1", "arm_id": arm_id, "unit": "account",
               "unit_key": rid, "allocation_version": 1,
               "at": "2026-06-01T09:00:00+00:00", "why": "assigned"}}
    steps = SEVEN if arm_id == "seven" else FOUR
    for i in range(confirmed):
        rec["events"].append({
            "type": events.PUSH_MARKED, "contact": "a", "channel": "email",
            "step": steps[i]["key"],
            "at": f"2026-07-{i + 1:02d}T09:00:00+00:00",
            "sender_id": "mark"})
    if extra_touch_at is not None:
        # A step confirmed late - a provider callback that arrived after
        # somebody had already answered.
        rec["events"].append({
            "type": events.PUSH_MARKED, "contact": "a", "channel": "email",
            "step": steps[confirmed]["key"], "at": extra_touch_at,
            "sender_id": "mark"})
    if reply_at:
        rec["events"].append({
            "type": (events.POSITIVE_REPLY_DETECTED if positive
                     else events.REPLY_RECEIVED),
            "contact": "a", "channel": "email", "at": reply_at,
            "classification": classification})
    return rec


def one(rec):
    return R.contact_replies(an_experiment(), rec, rec["contacts"][0])


class AReplyIsPlacedAfterTheStepItFollowed(unittest.TestCase):

    def test_it_names_the_last_confirmed_step_before_the_reply(self):
        rec = a_record("s1", "seven", confirmed=3,
                       reply_at="2026-07-10T09:00:00+00:00")
        found = one(rec)[0]
        self.assertEqual(found["after_step"], "s3")
        self.assertEqual(found["after_step_index"], 3)
        self.assertTrue(found["attributed"])

    def test_the_number_of_steps_seen_is_the_position_not_the_plan(self):
        """Three of seven. The denominator of the incremental question is
        what they saw, never what was scheduled for them."""
        rec = a_record("s1", "seven", confirmed=3,
                       reply_at="2026-07-10T09:00:00+00:00")
        found = one(rec)[0]
        self.assertEqual(found["steps_seen"], 3)
        self.assertEqual(found["planned"], 7)

    def test_it_measures_how_long_the_reply_took(self):
        rec = a_record("s1", "seven", confirmed=3,
                       reply_at="2026-07-10T09:00:00+00:00")
        self.assertEqual(one(rec)[0]["days_to_reply"], 9)

    def test_a_contact_who_has_not_replied_reports_an_empty_list(self):
        """Different from not being in the experiment, and the caller
        needs to tell those apart."""
        self.assertEqual(one(a_record("s1", "seven", confirmed=3)), [])

    def test_a_contact_outside_the_experiment_reports_nothing(self):
        rec = {"id": "x", "client": "demo", "events": [],
               "contacts": [{"key": "a", "email": "a@x.test"}]}
        self.assertIsNone(
            R.contact_replies(an_experiment(), rec, rec["contacts"][0]))


class ALaterStepMayNotClaimAnEarlierReply(unittest.TestCase):
    """The bias that matters. A late confirmation always attaches to a
    later step, so crediting the last touch overall makes long arms look
    better - the exact question the experiment exists to settle."""

    def test_a_step_confirmed_after_the_reply_is_not_credited(self):
        rec = a_record("s1", "seven", confirmed=3,
                       reply_at="2026-07-10T09:00:00+00:00",
                       extra_touch_at="2026-07-20T09:00:00+00:00")
        found = one(rec)[0]
        self.assertEqual(found["after_step"], "s3")

    def test_the_late_step_is_still_an_exposure(self):
        """It reached them. It just did not precede the reply, and those
        are different facts."""
        from src import cadenceexposure

        rec = a_record("s1", "seven", confirmed=3,
                       reply_at="2026-07-10T09:00:00+00:00",
                       extra_touch_at="2026-07-20T09:00:00+00:00")
        found = cadenceexposure.contact_exposure(an_experiment(), rec,
                                                 rec["contacts"][0])
        self.assertEqual(found["reached"], 4)

    def test_a_reply_on_the_same_timestamp_as_a_touch_counts_the_touch(self):
        """A boundary that has to be decided rather than left to sorting.
        Same instant means the message went first."""
        rec = a_record("s1", "seven", confirmed=2,
                       reply_at="2026-07-02T09:00:00+00:00")
        self.assertEqual(one(rec)[0]["after_step"], "s2")


class AReplyThatFollowedNothingIsNotCreditedToStepOne(unittest.TestCase):
    """Inbound arrives. Somebody forwards a message, answers a different
    campaign, or replies to a LinkedIn note nobody has confirmed. Counting
    those against step one credits the opener with replies it never
    earned, and the opener is exactly what an experiment is judging."""

    def test_a_reply_before_any_confirmed_touch_is_unattributed(self):
        rec = a_record("s1", "seven", confirmed=3,
                       reply_at="2026-06-15T09:00:00+00:00")
        found = one(rec)[0]
        self.assertEqual(found["after_step"], R.UNATTRIBUTED)
        self.assertFalse(found["attributed"])
        self.assertIsNone(found["after_step_index"])

    def test_it_says_why(self):
        rec = a_record("s1", "seven", confirmed=3,
                       reply_at="2026-06-15T09:00:00+00:00")
        self.assertIn("no confirmed touch", one(rec)[0]["why_unattributed"])

    def test_a_reply_with_no_timestamp_is_unattributed(self):
        """Missing evidence is never positive evidence."""
        rec = a_record("s1", "seven", confirmed=3)
        rec["events"].append({"type": events.REPLY_RECEIVED, "contact": "a",
                              "channel": "email", "at": None})
        self.assertFalse(one(rec)[0]["attributed"])

    def test_a_contact_with_no_touches_at_all_is_unattributed(self):
        rec = a_record("s1", "seven", confirmed=0,
                       reply_at="2026-07-10T09:00:00+00:00")
        found = one(rec)[0]
        self.assertEqual(found["after_step"], R.UNATTRIBUTED)
        self.assertEqual(found["steps_seen"], 0)


class TheArmRateIsAboutPeople(unittest.TestCase):

    def rows(self, recs, **kw):
        return R.by_arm(an_experiment(), recs, **kw)

    def test_the_denominator_is_who_started_not_who_was_assigned(self):
        """Somebody assigned and never touched has not experienced the
        cadence, and counting them makes an arm look worse in proportion
        to how many people it never reached."""
        recs = [a_record(f"s{i}", "seven", confirmed=2) for i in range(5)]
        recs += [a_record("s-never", "seven", confirmed=0)]
        recs[0] = a_record("s0", "seven", confirmed=2,
                           reply_at="2026-07-10T09:00:00+00:00")
        found = self.rows(recs)["seven"]
        self.assertEqual(found["assigned"], 6)
        self.assertEqual(found["exposed"], 5)
        self.assertAlmostEqual(found["rate"], 1 / 5)

    def test_two_replies_from_one_person_are_one_reply(self):
        """A long arm has more chances to be answered twice. Counting
        messages rather than people would pay it for that."""
        rec = a_record("s0", "seven", confirmed=3,
                       reply_at="2026-07-10T09:00:00+00:00")
        rec["events"].append({"type": events.REPLY_RECEIVED, "contact": "a",
                              "channel": "email",
                              "at": "2026-07-12T09:00:00+00:00"})
        recs = [rec] + [a_record(f"s{i}", "seven", confirmed=3)
                        for i in range(1, 5)]
        self.assertEqual(self.rows(recs)["seven"]["replies"], 1)

    def test_the_first_reply_is_the_one_counted(self):
        """The two replies have to land on different steps, or first and
        last are the same answer and this proves nothing."""
        rec = a_record("s0", "seven", confirmed=5,
                       reply_at="2026-07-03T12:00:00+00:00")
        rec["events"].append({"type": events.REPLY_RECEIVED, "contact": "a",
                              "channel": "email",
                              "at": "2026-07-30T09:00:00+00:00"})
        self.assertEqual(self.rows([rec])["seven"]["after_step"], {"s3": 1})

    def test_it_reports_where_the_replies_arrive(self):
        """The whole argument for running the experiment."""
        recs = [a_record("a", "seven", confirmed=2,
                         reply_at="2026-07-05T09:00:00+00:00"),
                a_record("b", "seven", confirmed=2,
                         reply_at="2026-07-06T09:00:00+00:00"),
                a_record("c", "seven", confirmed=6,
                         reply_at="2026-07-30T09:00:00+00:00")]
        found = self.rows(recs)["seven"]
        self.assertEqual(found["after_step"], {"s2": 2, "s6": 1})
        self.assertEqual(found["median_step"], 2)
        self.assertEqual(found["latest_step"], 6)

    def test_positive_only_counts_positive_replies(self):
        recs = [a_record("a", "seven", confirmed=2,
                         reply_at="2026-07-05T09:00:00+00:00"),
                a_record("b", "seven", confirmed=2,
                         reply_at="2026-07-06T09:00:00+00:00",
                         positive=True)]
        self.assertEqual(self.rows(recs)["seven"]["replies"], 2)
        self.assertEqual(
            self.rows(recs, positive_only=True)["seven"]["replies"], 1)

    def test_an_unattributed_reply_is_counted_and_named(self):
        """It happened. It is in the rate, and it is not in any step's
        column - both of which are true and neither of which may be
        quietly dropped."""
        recs = [a_record("a", "seven", confirmed=2,
                         reply_at="2026-06-15T09:00:00+00:00")]
        found = self.rows(recs)["seven"]
        self.assertEqual(found["replies"], 1)
        self.assertEqual(found["unattributed"], 1)
        self.assertEqual(found["attributed"], 0)
        self.assertIsNone(found["median_step"])

    def test_an_arm_nobody_started_has_no_rate_rather_than_zero(self):
        """Zero per cent and no evidence are different answers."""
        found = self.rows([a_record("a", "seven", confirmed=2)])["four"]
        self.assertEqual(found["exposed"], 0)
        self.assertIsNone(found["rate"])

    def test_both_arms_are_reported_separately(self):
        recs = [a_record("f", "four", confirmed=2,
                         reply_at="2026-07-05T09:00:00+00:00"),
                a_record("s", "seven", confirmed=2)]
        found = self.rows(recs)
        self.assertEqual(found["four"]["replies"], 1)
        self.assertEqual(found["seven"]["replies"], 0)
        self.assertEqual(found["four"]["steps"], 4)
        self.assertEqual(found["seven"]["steps"], 7)


class ItSaysWhatItIsAndIsNot(unittest.TestCase):

    def test_the_journey_travels_with_the_attribution(self):
        """So a last-touch number is never read as a claim about one
        message alone."""
        rec = a_record("s1", "seven", confirmed=3,
                       reply_at="2026-07-10T09:00:00+00:00")
        self.assertIn("journey", one(rec)[0])

    def test_it_writes_no_state(self):
        import inspect

        source = inspect.getsource(R)
        for banned in ("store.save", "store.log", "events.record"):
            self.assertNotIn(banned, source, banned)

    def test_it_does_not_decide_a_winner(self):
        """Attribution says what happened. `variants.evaluate` says what it
        means, and an attributor that also judged could talk itself into a
        verdict."""
        import ast
        import inspect

        imported = set()
        for node in ast.walk(ast.parse(inspect.getsource(R))):
            if isinstance(node, ast.ImportFrom):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
        self.assertNotIn("variants", imported)
        self.assertNotIn("learning", imported)


if __name__ == "__main__":
    unittest.main()
