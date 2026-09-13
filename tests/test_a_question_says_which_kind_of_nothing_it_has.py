#!/usr/bin/env python3
"""Three different nothings, and the one answer that is never given.

With one live send in the estate the only honest output is a correctly
recorded observation and INSUFFICIENT_DATA. That is easy to assert and it
is not the interesting part. The interesting part is that "nothing" has
three shapes here and they need opposite fixes:

    no confirmed action at all        nothing has been sent yet
    actions, dimension never written  NOT_INSTRUMENTED - fix the producer
    actions, dimension present        INSUFFICIENT_DATA - wait, or send more

This repository's named recurring defect is a thing computed correctly that
nothing downstream reads, and its worked example is an evaluator that
reported INSUFFICIENT_DATA for ever because nothing wrote the field it read
- indistinguishable, from outside, from an evaluator waiting for volume.
So `answer()` must tell those two apart, and the evidence question must
report NOT_INSTRUMENTED today and stop the moment the evidence ids appear
on the event.

The thresholds are `src/variants.py`'s, and nothing here may loosen them.
The case that matters is the one the copy experiment was written for: five
replies against four is not a winner.
"""
import unittest

from src import events, leadobserve, outcomes, store, variants
from tests.base import QueueTest

TOUCH_AT = "2026-09-14T13:19:05+00:00"
REPLY_AT = "2026-09-15T09:00:00+00:00"


def a_record(rid, persona="economic_buyer", angle="founder", replied=False,
             positive=False, touches=None, client="productive", **contact):
    """One account, one decision maker, and the touches they received."""
    person = {"key": "p", "name": "A Person", "email": f"p@{rid}.test",
              "persona": persona, "angle": angle}
    person.update(contact)
    rec = {"id": rid, "client": client, "domain": f"{rid}.test",
           "company": rid, "contacts": [person], "events": [],
           "cadence": {"p": {}}}
    for entry in touches if touches is not None else [{}]:
        # Every touched step carries copy, so a length question is answering
        # about the message rather than about a hole in the fixture.
        rec["cadence"]["p"][entry.get("step", "day1")] = {
            "channel": "email", "subject": "s", "body": "one two three"}
        rec["events"].append({
            "type": events.PUSH_MARKED, "contact": "p",
            "channel": entry.get("channel", "email"),
            "step": entry.get("step", "day1"),
            "at": entry.get("at", TOUCH_AT),
            **{k: v for k, v in entry.items()
               if k not in ("channel", "step", "at")}})
    if replied or positive:
        rec["events"].append({
            "type": (events.POSITIVE_REPLY_DETECTED if positive
                     else events.REPLY_RECEIVED),
            "contact": "p", "channel": "email", "at": REPLY_AT})
    return rec


def an_estate(per_cell, outcomes_by_cell, field="persona"):
    """`per_cell` accounts in each named cell, with that many positives."""
    recs = []
    for cell, wanted in outcomes_by_cell.items():
        for i in range(per_cell):
            recs.append(a_record(f"{cell}-{i}", positive=i < wanted,
                                 **{field: cell}))
    return recs


def look(recs):
    return outcomes.observations(recs, campaign_rows=[], provider_rows=[])


class OneObservationIsRecordedAndConcludesNothing(unittest.TestCase):

    def setUp(self):
        self.rows = look([a_record("hotsoup")])

    def test_the_action_is_captured_with_its_dimensions(self):
        row = self.rows[0]
        self.assertEqual(row["account"]["record_id"], "hotsoup")
        self.assertEqual(row["person"]["contact_key"], "p")
        self.assertEqual(row["person"]["persona"], "economic_buyer")
        self.assertEqual(row["person"]["angle"], "founder")
        self.assertEqual(row["channel"], "email")
        self.assertEqual(row["step"], "day1")
        self.assertEqual(row["at"], TOUCH_AT)

    def test_delivery_is_not_reported_rather_than_confirmed(self):
        """No surface says a mailbox accepted it, so nothing claims one
        did - and `not_reported` is not the same word as `bounced`."""
        self.assertEqual(self.rows[0]["delivery"], outcomes.NOT_REPORTED)
        self.assertFalse(self.rows[0]["bounced"])

    def test_a_persona_read_today_is_marked_as_read_today(self):
        self.assertEqual(self.rows[0]["person"]["provenance"],
                         outcomes.INFERRED)

    def test_the_confidence_is_the_weakest_dimension_not_the_best(self):
        row = self.rows[0]
        self.assertEqual(row["evidence"]["provenance"], outcomes.ABSENT)
        self.assertEqual(row["confidence"], outcomes.ABSENT)

    def test_every_question_answers_insufficient_or_not_instrumented(self):
        for found in outcomes.answers(self.rows):
            self.assertIn(found["state"],
                          (variants.INSUFFICIENT_DATA,
                           outcomes.NOT_INSTRUMENTED), found["key"])
            self.assertNotEqual(found["state"], variants.WINNER)
            self.assertIsNone(found.get("leader"))

    def test_an_empty_estate_says_nothing_has_been_sent(self):
        found = outcomes.answer("persona", [])
        self.assertEqual(found["state"], variants.INSUFFICIENT_DATA)
        self.assertIn("no confirmed provider-backed action", found["why"])


class NotInstrumentedIsNotTheSameAsNotEnough(unittest.TestCase):

    def test_evidence_is_not_instrumented_and_says_what_to_record(self):
        found = outcomes.answer("evidence", look([a_record("hotsoup")]))
        self.assertEqual(found["state"], outcomes.NOT_INSTRUMENTED)
        self.assertIn("evidence_ids on the confirming event", found["needs"])

    def test_recording_the_evidence_ids_changes_the_answer(self):
        """The consumer is wired, proved by making the producer exist.

        A reader for a field nothing writes is the defect this whole module
        is about, so the read is exercised rather than asserted."""
        rec = a_record("hotsoup", touches=[{"evidence_ids": ["ev-1"]}])
        rec["contacts"][0]["personalization"] = {"level": "recent_event",
                                                 "quality": "high"}
        rows = look([rec])
        self.assertEqual(rows[0]["evidence"]["ids"], ["ev-1"])
        self.assertEqual(rows[0]["evidence"]["provenance"], outcomes.RECORDED)
        found = outcomes.answer("evidence", rows)
        self.assertEqual(found["state"], variants.INSUFFICIENT_DATA)

    def test_a_decision_on_the_contact_is_inferred_not_recorded(self):
        """The personalization decision is overwritten by the next
        generation, so it is not what the sent message used."""
        rec = a_record("hotsoup")
        rec["contacts"][0]["personalization"] = {
            "selected_evidence_ids": ["ev-9"], "level": "company_fact"}
        rows = look([rec])
        self.assertEqual(rows[0]["evidence"]["provenance"], outcomes.INFERRED)

    def test_a_first_touch_has_no_spacing_and_that_is_not_a_gap(self):
        """Spacing needs a previous touch. Reporting the first one as an
        instrumentation failure would send somebody to fix working code."""
        found = outcomes.answer("spacing", look([a_record("hotsoup")]))
        self.assertEqual(found["state"], variants.INSUFFICIENT_DATA)
        self.assertEqual(found["units"], 0)
        self.assertEqual(found["not_applicable"], 1)

    def test_spacing_is_measured_once_there_are_two_touches(self):
        rec = a_record("hotsoup", touches=[
            {"step": "day1", "at": "2026-09-14T09:00:00+00:00"},
            {"step": "day8", "at": "2026-09-19T09:00:00+00:00"}])
        found = outcomes.answer("spacing", look([rec]))
        self.assertEqual(found["state"], variants.INSUFFICIENT_DATA)
        self.assertEqual(found["units"], 1)
        self.assertEqual([r["variant_id"] for r in found["cells"]],
                         ["4_to_7_days"])


class TheThresholdsAreTheEvaluatorsOwn(unittest.TestCase):

    def answer(self, per_cell, outcomes_by_cell):
        return outcomes.answer("persona",
                               look(an_estate(per_cell, outcomes_by_cell)))

    def test_one_short_of_the_minimum_per_cell_settles_nothing(self):
        rules = variants.settings()
        short = int(rules["minimum_per_variant"]) - 1
        found = self.answer(short, {"economic_buyer": 12, "champion": 0})
        self.assertEqual(found["state"], variants.INSUFFICIENT_DATA)

    def test_five_replies_against_four_is_not_a_winner(self):
        """The case the copy experiment was written for. Nine outcomes
        clears the outcome floor and the lift does not clear 30%."""
        found = self.answer(30, {"economic_buyer": 5, "champion": 4})
        self.assertEqual(found["state"], variants.LEADING)
        self.assertNotEqual(found["state"], variants.WINNER)

    def test_too_few_outcomes_settles_nothing_however_many_exposures(self):
        found = self.answer(60, {"economic_buyer": 4, "champion": 3})
        self.assertEqual(found["state"], variants.INSUFFICIENT_DATA)
        self.assertIn("outcome(s) in total", found["why"])

    def test_a_real_separation_is_called(self):
        found = self.answer(30, {"economic_buyer": 12, "champion": 0})
        self.assertEqual(found["state"], variants.WINNER)
        self.assertEqual(found["leader"], "economic_buyer")

    def test_the_minimum_is_variants_own_numbers(self):
        rules = variants.settings()
        minimum = outcomes.minimum_for(outcomes.QUESTION["persona"])
        self.assertEqual(minimum["per_cell"], rules["minimum_per_variant"])
        self.assertEqual(minimum["outcomes"], rules["minimum_outcomes"])
        self.assertEqual(minimum["lift"], rules["minimum_lift"])
        self.assertEqual(minimum["total_units"],
                         minimum["cells"] * rules["minimum_per_variant"])

    def test_every_rate_carries_its_denominator(self):
        found = self.answer(30, {"economic_buyer": 12, "champion": 0})
        for row in found["cells"]:
            self.assertIn("exposures", row)
            self.assertIn("outcomes", row)
            self.assertIsNotNone(row["low"])
            self.assertIsNotNone(row["high"])


class AnOutcomeIsCreditedToTheTouchBeforeIt(unittest.TestCase):

    def test_the_last_confirmed_touch_before_the_reply_takes_the_credit(self):
        rec = a_record("hotsoup", positive=True, touches=[
            {"step": "day1", "at": "2026-09-01T09:00:00+00:00"},
            {"step": "day8", "at": "2026-09-14T09:00:00+00:00"}])
        found = outcomes.answer("length", look([rec]))
        credited = sum(r["outcomes"] for r in found["cells"])
        self.assertEqual(found["units"], 2)
        self.assertEqual(credited, 1)

    def test_a_person_is_counted_once_however_many_touches_they_got(self):
        rec = a_record("hotsoup", positive=True, touches=[
            {"step": "day1", "at": "2026-09-01T09:00:00+00:00"},
            {"step": "day8", "at": "2026-09-14T09:00:00+00:00"}])
        found = outcomes.answer("persona", look([rec]))
        self.assertEqual(found["units"], 1)
        self.assertEqual(found["outcomes"], 1)

    def test_a_reply_before_the_touch_is_not_that_touchs_outcome(self):
        rec = a_record("hotsoup", positive=True, touches=[
            {"step": "day8", "at": "2026-09-20T09:00:00+00:00"}])
        rows = look([rec])
        self.assertFalse(rows[0]["reply"]["replied"])


class ProviderTruthWinsWhereItExists(unittest.TestCase):

    def observation(self):
        rec = a_record("hotsoup", touches=[{"scheduled_email_id": 22303345}])
        provider = [{"provider": leadobserve.EMAILBISON, "campaign_id": "451",
                     "scheduled_email_id": 22303345, "state": "sent",
                     "raw_status": "sent", "at": "2026-09-14T13:20:00+00:00",
                     "subject_chars": 51, "body_chars": 491, "body_words": 85,
                     "sender_account_id": 3948, "open_tracking": False,
                     "opens": 0, "sender_email": "s@example.test"}]
        return outcomes.observations([rec], campaign_rows=[],
                                     provider_rows=provider)[0]

    def test_the_length_measured_is_what_the_provider_rendered(self):
        row = self.observation()
        self.assertEqual(row["message"]["body_words"], 85)
        self.assertEqual(row["message"]["provenance"], outcomes.ATTRIBUTED)

    def test_the_provider_status_travels_with_the_observation(self):
        row = self.observation()
        self.assertEqual(row["provider_status"], "sent")
        self.assertTrue(row["attributable"])

    def test_opens_carry_whether_they_were_measured_at_all(self):
        row = self.observation()
        self.assertEqual(row["opens"], 0)
        self.assertIs(row["open_tracking"], False)

    def test_without_a_provider_row_the_length_is_only_inferred(self):
        rows = look([a_record("hotsoup")])
        self.assertEqual(rows[0]["message"]["provenance"], outcomes.INFERRED)


class WhatIsMissingIsCountedRatherThanSearchedFor(unittest.TestCase):

    def test_the_dimensions_nothing_holds_are_named(self):
        missing = outcomes.missing_dimensions(look([a_record("hotsoup")]))
        self.assertEqual(missing.get("evidence"), 1)
        self.assertEqual(missing.get("variant"), 1)

    def test_a_dimension_that_is_recorded_is_not_reported_missing(self):
        rec = a_record("hotsoup", touches=[{"variant_id": "B",
                                            "variant_style": "casual",
                                            "evidence_ids": ["ev-1"]}])
        missing = outcomes.missing_dimensions(look([rec]))
        self.assertNotIn("variant", missing)
        self.assertNotIn("evidence", missing)

    def test_it_counts_actions_rather_than_answering_yes_or_no(self):
        """One of two sends missing a variant id and both missing it are
        different sizes of the same problem."""
        rows = look([a_record("a"),
                     a_record("b", touches=[{"variant_id": "B"}])])
        self.assertEqual(outcomes.missing_dimensions(rows)["variant"], 1)


class NothingPlannedIsCountedAsAnAction(unittest.TestCase):

    def test_a_prepared_payload_is_not_an_observation(self):
        """`push_prepared` is the most dangerous near-miss in the
        vocabulary and `touch.py` excludes it by name."""
        rec = a_record("hotsoup", touches=[])
        rec["events"] = [{"type": events.PUSH_PREPARED, "contact": "p",
                          "channel": "email", "step": "day1", "at": TOUCH_AT}]
        self.assertEqual(look([rec]), [])

    def test_an_approved_draft_is_not_an_observation(self):
        rec = a_record("hotsoup", touches=[])
        rec["events"] = [{"type": events.DRAFT_APPROVED, "contact": "p",
                          "channel": "email", "step": "day1", "at": TOUCH_AT}]
        self.assertEqual(look([rec]), [])

    def test_a_step_marked_then_delivered_is_one_action(self):
        rec = a_record("hotsoup")
        rec["events"].append({"type": events.EMAIL_DELIVERED, "contact": "p",
                              "channel": "email", "step": "day1",
                              "at": "2026-09-14T13:25:00+00:00"})
        rows = look([rec])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["delivery"], outcomes.CONFIRMED)


class TheRunReportIsDerivedAndNeverTypedIn(QueueTest):
    """Every stage names the canonical state it is read from, and a stage
    nothing can observe says so rather than reporting a zero that reads as
    a result."""

    def report(self, recs):
        store.save(recs)
        return outcomes.run_report(recs=recs, campaign_rows=[])

    def stage(self, report, name):
        return next(r for r in report["stages"] if r["stage"] == name)

    def test_the_stages_are_the_ones_the_operator_asked_for(self):
        report = self.report([a_record("hotsoup")])
        self.assertEqual([r["stage"] for r in report["stages"]],
                         list(outcomes.STAGES))

    def test_sent_moves_when_a_confirmed_touch_appears(self):
        empty = self.report([a_record("hotsoup", touches=[])])
        self.assertEqual(self.stage(empty, "SENT")["count"], 0)
        one = outcomes.run_report(recs=[a_record("hotsoup")],
                                  campaign_rows=[])
        self.assertEqual(self.stage(one, "SENT")["count"], 1)

    def test_delivered_is_marked_unobservable_rather_than_zero(self):
        report = self.report([a_record("hotsoup")])
        row = self.stage(report, "DELIVERED")
        self.assertFalse(row["observable"])
        self.assertIn("sent", row["note"])

    def test_meetings_are_marked_unobservable_too(self):
        report = self.report([a_record("hotsoup")])
        self.assertFalse(self.stage(report, "MEETINGS")["observable"])

    def test_every_stage_names_the_state_it_is_read_from(self):
        report = self.report([a_record("hotsoup")])
        for row in report["stages"]:
            self.assertTrue(row["truth"], row["stage"])

    def test_bugs_and_replays_are_refused_rather_than_invented(self):
        report = self.report([a_record("hotsoup")])
        self.assertFalse(report["bugs"]["observable"])
        self.assertFalse(report["replays"]["observable"])
        self.assertNotIn("count", report["bugs"])

    def test_a_provider_saying_running_while_we_say_draft_is_reported(self):
        campaign = {"campaign_id": "canary", "client": "productive",
                    "status": "draft", "record_ids": ["hotsoup"],
                    "bison_campaign_id": 451}
        store.save([a_record("hotsoup")])
        with store.file_transaction(leadobserve.path()) as rows:
            rows.append({"provider": leadobserve.EMAILBISON,
                         "campaign_id": "451", "campaign_status": "active",
                         "scheduled_email_id": 1, "state": "scheduled",
                         "at": "2026-09-13T09:00:00+00:00"})
        report = outcomes.run_report(recs=[a_record("hotsoup")],
                                     campaign_rows=[campaign])
        found = report["campaign_disagreements"]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["provider_status"], "active")
        self.assertEqual(found[0]["local_status"], "draft")


if __name__ == "__main__":
    unittest.main()
