"""What a contact received, as against what they were assigned.

One assertion in this file matters more than the rest:

    A contact assigned to a seven-step arm who replies after three
    confirmed steps must never be reported as having received seven.

It is the easy error to make. The arm says seven, the assignment says
seven, and nothing in the record disagrees out loud. Every rate in a
cadence experiment has one of these counts underneath it, so getting it
wrong does not produce a wrong number in one place - it produces a
comparison between the arm somebody configured and the arm somebody else
actually ran.
"""
import unittest

from src import (accountpolicy as ap, cadencearms as arms,
                 cadenceexposure as exposure, events)

SEVEN = [{"key": f"s{i}", "day": d, "channel": "email",
          "template": "persona_pain"}
         for i, d in enumerate((1, 3, 7, 12, 18, 25, 35), start=1)]
FOUR = SEVEN[:4]


def an_experiment(**kw):
    return arms.experiment("cad-1",
                           [arms.arm("four", "4 steps", FOUR),
                            arms.arm("seven", "7 steps", SEVEN)], **kw)


def a_record(rid="acme", confirmed=0, steps=None, contacts=None):
    """A record whose contact has `confirmed` steps genuinely delivered."""
    rec = {"id": rid, "client": "demo", "company": "Acme",
           "domain": "acme.test", "events": [],
           "contacts": contacts if contacts is not None else
                       [{"key": "a", "name": "A Person",
                         "email": "a@acme.test"}]}
    for i in range(confirmed):
        key = (steps or SEVEN)[i]["key"]
        rec["events"].append({
            "type": events.PUSH_MARKED, "contact": "a", "channel": "email",
            "step": key, "at": f"2026-0{i + 1}-01T09:00:00+00:00",
            "sender_id": "mark"})
    return rec


def put_in(rec, arm_id, contact=None, exp_id="cad-1"):
    holder = contact if contact is not None else rec
    holder[arms.ASSIGNMENT_KEY] = {
        "experiment_id": exp_id, "arm_id": arm_id, "unit": "account",
        "unit_key": rec.get("id"), "allocation_version": 1,
        "at": "2026-01-01T09:00:00+00:00", "why": "assigned"}
    return rec


def replied(rec, positive=True, at="2026-04-15T09:00:00+00:00"):
    rec.setdefault("events", []).append({
        "type": (events.POSITIVE_REPLY_DETECTED if positive
                 else events.REPLY_RECEIVED),
        "contact": "a", "channel": "email", "at": at})
    rec["paused"] = {"since": at, "reason": "reply_received"}
    return rec


def look(rec, exp=None, contact=None):
    exp = exp or an_experiment()
    return exposure.contact_exposure(
        exp, rec, contact or rec["contacts"][0])


class TheInvariant(unittest.TestCase):
    """Seven assigned, three received. Three."""

    def setUp(self):
        self.rec = replied(put_in(a_record(confirmed=3), "seven"))
        self.found = look(self.rec)

    def test_it_reports_what_was_received_not_what_was_assigned(self):
        self.assertEqual(self.found["reached"], 3)

    def test_the_arm_length_is_carried_separately(self):
        """Both numbers survive. The comparison needs to know the arm has
        seven steps *and* that this contact got three."""
        self.assertEqual(self.found["planned"], 7)

    def test_it_is_not_completed(self):
        self.assertNotEqual(self.found["state"], exposure.COMPLETED)
        self.assertEqual(self.found["state"], exposure.STOPPED_EARLY)

    def test_it_names_the_steps_that_never_happened(self):
        self.assertEqual(self.found["not_reached"], ["s4", "s5", "s6", "s7"])

    def test_it_says_why_it_stopped(self):
        self.assertEqual(self.found["terminated"], exposure.POSITIVE)
        self.assertTrue(self.found["termination_label"])

    def test_it_is_censored_by_an_outcome_rather_than_by_safety(self):
        """The arm did not finish and the reason it did not finish is the
        thing the experiment was looking for. Dropping these observations
        biases everything; calling them incomplete runs is as wrong as
        calling them complete ones."""
        self.assertTrue(self.found["censored"])
        self.assertEqual(self.found["censored_by"], "outcome")


class TheStates(unittest.TestCase):

    def test_assigned_and_nothing_sent(self):
        found = look(put_in(a_record(confirmed=0), "seven"))
        self.assertEqual(found["state"], exposure.ASSIGNED)
        self.assertFalse(found["started"])
        self.assertEqual(found["reached"], 0)

    def test_part_way_through_and_still_running(self):
        found = look(put_in(a_record(confirmed=3), "seven"))
        self.assertEqual(found["state"], exposure.IN_PROGRESS)
        self.assertTrue(found["started"])
        self.assertFalse(found["censored"])

    def test_every_step_confirmed_is_completed(self):
        found = look(put_in(a_record(confirmed=7), "seven"))
        self.assertEqual(found["state"], exposure.COMPLETED)
        self.assertEqual(found["reached"], 7)
        self.assertEqual(found["not_reached"], [])

    def test_a_four_step_arm_completes_at_four(self):
        """The same three confirmed steps mean different things in
        different arms. Four steps is most of a four-step arm and less
        than half of a seven."""
        rec = put_in(a_record(confirmed=4, steps=FOUR), "four")
        found = look(rec)
        self.assertEqual(found["state"], exposure.COMPLETED)
        self.assertEqual(found["planned"], 4)

    def test_an_unassigned_contact_is_not_a_zero_exposure_participant(self):
        """Counting them as one would put every contact in the estate in
        the denominator."""
        self.assertIsNone(look(a_record(confirmed=2)))

    def test_an_assignment_to_an_arm_that_no_longer_exists_is_not_one(self):
        rec = put_in(a_record(confirmed=2), "an-arm-that-was-removed")
        self.assertIsNone(look(rec))

    def test_an_assignment_from_another_experiment_is_not_this_one(self):
        rec = put_in(a_record(confirmed=2), "seven", exp_id="cad-OTHER")
        self.assertIsNone(look(rec))


class OnlyConfirmedTouchesCount(unittest.TestCase):

    def test_a_prepared_step_is_not_exposure(self):
        """A denominator under a message nobody received makes a long arm
        look worse than it is."""
        rec = put_in(a_record(confirmed=2), "seven")
        rec["events"].append({
            "type": events.PUSH_PREPARED, "contact": "a", "channel": "email",
            "step": "s3", "at": "2026-03-01T09:00:00+00:00"})
        found = look(rec)
        self.assertEqual(found["reached"], 2)
        self.assertIn("s3", found["not_reached"])

    def test_both_confirmation_guards_are_present(self):
        """`confirmed_only=True` and the state check are each sufficient,
        so removing either alone changes no behaviour and no behavioural
        test can tell them apart. Asserted structurally instead, because
        the duplication is deliberate: a guard that exists once is a guard
        one refactor away from gone."""
        import inspect

        source = inspect.getsource(exposure._confirmed_steps)
        self.assertIn("confirmed_only=True", source)
        self.assertIn("CONFIRMED_STATES", source)

    def test_a_hand_assembled_row_still_meets_the_state_check(self):
        """The reason the second guard is worth keeping: a caller that did
        not come through `account.touches`."""
        rows = exposure._confirmed_steps(
            {"events": [{"type": events.PUSH_PREPARED, "contact": "a",
                         "channel": "email", "step": "s1",
                         "at": "2026-01-01T09:00:00+00:00"}]}, "a")
        self.assertEqual(rows, [])

    def test_one_step_delivered_twice_is_one_exposure(self):
        """A step marked sent and then reported delivered is one message."""
        rec = put_in(a_record(confirmed=2), "seven")
        rec["events"].append({
            "type": events.EMAIL_DELIVERED, "contact": "a",
            "channel": "email", "step": "s1",
            "at": "2026-01-02T09:00:00+00:00"})
        self.assertEqual(look(rec)["reached"], 2)

    def test_a_step_from_another_sequence_is_not_credited(self):
        """A confirmed touch on a key this arm does not contain came from
        a different sequence - an earlier campaign, or the legacy cadence -
        and crediting it borrows another campaign's history."""
        rec = put_in(a_record(confirmed=2), "seven")
        rec["events"].append({
            "type": events.PUSH_MARKED, "contact": "a", "channel": "email",
            "step": "day21", "at": "2026-03-01T09:00:00+00:00"})
        found = look(rec)
        self.assertEqual(found["reached"], 2)
        self.assertNotIn("day21", [s["key"] for s in found["steps"]])

    def test_the_steps_carry_what_was_sent(self):
        rec = put_in(a_record(confirmed=1), "seven")
        rec["events"][0]["variant_id"] = "v-b"
        rec["events"][0]["variant_version"] = 2
        step = look(rec)["steps"][0]
        self.assertEqual(step["variant_id"], "v-b")
        self.assertEqual(step["sender_id"], "mark")


class SafetyOutranksTheExperiment(unittest.TestCase):
    """Every one of these stops the sequence, and they do not all mean the
    same thing about the arm."""

    def stopped(self, mutate, confirmed=2):
        rec = put_in(a_record(confirmed=confirmed), "seven")
        mutate(rec)
        return look(rec)

    def test_a_removal_request_stops_it(self):
        found = self.stopped(
            lambda r: r["contacts"][0].update(unsubscribed=True))
        self.assertEqual(found["terminated"], exposure.UNSUBSCRIBED)
        self.assertEqual(found["censored_by"], "safety")

    def test_a_company_wide_removal_stops_it(self):
        found = self.stopped(
            lambda r: r.update(suppression={"unsubscribed": True}))
        self.assertEqual(found["terminated"], exposure.ACCOUNT_SUPPRESSED)
        self.assertEqual(found["censored_by"], "safety")

    def test_a_dropped_record_stops_it(self):
        found = self.stopped(lambda r: r.update(state="dropped"))
        self.assertEqual(found["terminated"], exposure.DROPPED)

    def test_a_hold_from_somebody_else_at_the_account_stops_it(self):
        """Not a result for this contact. Somebody else replied."""
        found = self.stopped(
            lambda r: r.update(paused={"since": "x", "reason": "reply"}))
        self.assertEqual(found["terminated"], exposure.ACCOUNT_HELD)
        self.assertEqual(found["censored_by"], "safety")

    def test_a_removal_request_outranks_a_reply(self):
        """A contact who both replied and asked to be removed is reported
        as removed: that is the fact deciding what happens next, and the
        reply is already counted as an outcome elsewhere."""
        rec = replied(put_in(a_record(confirmed=2), "seven"))
        rec["contacts"][0]["unsubscribed"] = True
        self.assertEqual(look(rec)["terminated"], exposure.UNSUBSCRIBED)

    def test_this_contacts_own_reply_reads_as_the_reply(self):
        """A hold caused by their own reply must not be reported as
        somebody else's - the pause and the reply are the same event."""
        rec = replied(put_in(a_record(confirmed=2), "seven"))
        self.assertEqual(look(rec)["terminated"], exposure.POSITIVE)

    def test_a_plain_reply_is_a_reply(self):
        rec = replied(put_in(a_record(confirmed=2), "seven"), positive=False)
        found = look(rec)
        self.assertEqual(found["terminated"], exposure.REPLIED)
        self.assertTrue(found["replied"])
        self.assertFalse(found["positive"])

    def test_nothing_stopping_it_reports_nothing(self):
        found = look(put_in(a_record(confirmed=2), "seven"))
        self.assertIsNone(found["terminated"])
        self.assertIsNone(found["censored_by"])

    def test_a_completed_arm_is_not_censored_even_if_they_replied(self):
        """Censoring means the arm did not finish. This one did."""
        rec = replied(put_in(a_record(confirmed=7), "seven"))
        found = look(rec)
        self.assertEqual(found["state"], exposure.COMPLETED)
        self.assertFalse(found["censored"])


class TheDenominatorsAreDifferentOnPurpose(unittest.TestCase):

    def estate(self):
        """Five accounts in the seven-step arm, at five different points."""
        recs = []
        for i, (confirmed, stop) in enumerate((
                (0, None), (2, None), (7, None), (3, "reply"),
                (1, "unsubscribed"))):
            rec = put_in(a_record(f"co-{i}", confirmed=confirmed), "seven")
            if stop == "reply":
                replied(rec)
            elif stop == "unsubscribed":
                rec["contacts"][0]["unsubscribed"] = True
            recs.append(rec)
        return recs

    def test_started_is_out_of_assigned(self):
        found = exposure.summarise(an_experiment(), self.estate())
        seven = next(a for a in found["arms"] if a["arm_id"] == "seven")
        self.assertEqual(seven["assigned"], 5)
        self.assertEqual(seven["started"], 4)

    def test_completed_is_out_of_started(self):
        """A contact suppressed before step one never ran the arm, and
        counting them against it makes an arm look worse in proportion to
        how many were stopped before it began."""
        found = exposure.summarise(an_experiment(), self.estate())
        seven = next(a for a in found["arms"] if a["arm_id"] == "seven")
        self.assertEqual(seven["completed"], 1)
        self.assertAlmostEqual(seven["completion_rate"], 1 / 4)

    def test_touches_are_counted_not_assumed_from_the_arm_length(self):
        """0 + 2 + 7 + 3 + 1. Assuming seven each would give 35."""
        found = exposure.summarise(an_experiment(), self.estate())
        seven = next(a for a in found["arms"] if a["arm_id"] == "seven")
        self.assertEqual(seven["touches"], 13)

    def test_terminations_are_broken_out_by_reason(self):
        found = exposure.summarise(an_experiment(), self.estate())
        seven = next(a for a in found["arms"] if a["arm_id"] == "seven")
        self.assertEqual(seven["terminations"][exposure.POSITIVE], 1)
        self.assertEqual(seven["terminations"][exposure.UNSUBSCRIBED], 1)

    def test_outcome_and_safety_censoring_are_counted_apart(self):
        """Both stop the sequence and they mean opposite things about the
        arm. One is the result; the other is the arm never being run."""
        found = exposure.summarise(an_experiment(), self.estate())
        seven = next(a for a in found["arms"] if a["arm_id"] == "seven")
        self.assertEqual(seven["censored_by_outcome"], 1)
        self.assertEqual(seven["censored_by_safety"], 1)

    def test_an_arm_nobody_is_in_reports_zero_rather_than_vanishing(self):
        found = exposure.summarise(an_experiment(), self.estate())
        four = next(a for a in found["arms"] if a["arm_id"] == "four")
        self.assertEqual(four["assigned"], 0)
        self.assertIsNone(four["completion_rate"])

    def test_a_rate_with_no_denominator_is_none_rather_than_zero(self):
        """Zero per cent and no data are different, and a chart cannot
        tell them apart once one has been written as the other."""
        found = exposure.summarise(an_experiment(), [])
        for row in found["arms"]:
            self.assertIsNone(row["completion_rate"])
            self.assertIsNone(row["touches_per_started"])

    def test_the_summary_explains_which_denominator_it_used(self):
        found = exposure.summarise(an_experiment(), [])
        self.assertIn("out of started", found["note"])


class ItDecidesNothingAndWritesNothing(unittest.TestCase):

    def test_it_writes_no_state(self):
        import inspect

        source = inspect.getsource(exposure)
        for banned in ("store.save", "store.log", "events.record",
                       "urlopen", "providers."):
            self.assertNotIn(banned, source, banned)

    def test_it_does_not_mutate_the_records_it_reads(self):
        import copy

        recs = [replied(put_in(a_record(confirmed=3), "seven"))]
        before = copy.deepcopy(recs)
        exposure.summarise(an_experiment(), recs)
        self.assertEqual(recs, before)


if __name__ == "__main__":
    unittest.main()


class APlannedTouchIsNotAnExposure(unittest.TestCase):
    """The invariant this module is named for, with an actual planned
    touch in the record.

    Written after a mutation run: removing *both* confirmation checks from
    `_confirmed_steps` changed nothing, because every fixture in this file
    creates confirmed events only. The rule was stated in the docstring, in
    a comment, and twice in the code, and asserted nowhere.
    """

    def assigned(self, rec):
        exp = an_experiment()
        arms.assign(exp, rec)
        return exposure.contact_exposure(exp, rec, rec["contacts"][0])

    def planned(self, key, kind=events.PUSH_PREPARED):
        return {"type": kind, "contact": "a", "channel": "email",
                "step": key, "at": "2026-07-01T09:00:00+00:00",
                "sender_id": "mark"}

    def test_a_prepared_push_does_not_count_as_reached(self):
        rec = a_record(confirmed=2)
        rec["events"].append(self.planned("s3"))
        self.assertEqual(self.assigned(rec)["reached"], 2)

    def test_an_approved_draft_does_not_count_as_reached(self):
        """Approved is further along than prepared and still not a touch."""
        rec = a_record(confirmed=2)
        rec["events"].append(self.planned("s3", events.DRAFT_APPROVED))
        self.assertEqual(self.assigned(rec)["reached"], 2)

    def test_the_planned_step_is_listed_as_not_reached(self):
        rec = a_record(confirmed=2)
        rec["events"].append(self.planned("s3"))
        self.assertIn("s3", self.assigned(rec)["not_reached"])

    def test_it_does_not_appear_among_the_steps_they_received(self):
        rec = a_record(confirmed=2)
        rec["events"].append(self.planned("s3"))
        self.assertNotIn("s3", [row["key"]
                                for row in self.assigned(rec)["steps"]])

    def test_a_contact_with_only_planned_touches_has_not_started(self):
        """The denominator case. Somebody with a whole cadence prepared and
        nothing sent is assigned, not exposed."""
        rec = a_record(confirmed=0)
        for step in SEVEN:
            rec["events"].append(self.planned(step["key"]))
        found = self.assigned(rec)
        self.assertEqual(found["reached"], 0)
        self.assertFalse(found["started"])
        self.assertEqual(found["state"], exposure.ASSIGNED)

    def test_and_a_confirmed_one_does_count(self):
        """So the four refusals above are about confirmation rather than
        about the events being ignored altogether."""
        rec = a_record(confirmed=2)
        rec["events"].append({
            "type": events.EMAIL_DELIVERED, "contact": "a",
            "channel": "email", "step": "s3",
            "at": "2026-07-01T09:00:00+00:00", "sender_id": "mark"})
        self.assertEqual(self.assigned(rec)["reached"], 3)
