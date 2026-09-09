"""Cadence expansion and the company pause. BUILD-SPEC section 7, phase 7.

Acceptance test, section 10: a reply on one channel pauses both tracks
company-wide.

Nothing here touches a network, a provider or a model.
"""
import os
import shutil
import tempfile
import unittest

from src import cadence, clients, lint, store
from tests.base import FIXTURES, approve_everything

CONFIG = None


class CadenceTest(unittest.TestCase):
    def setUp(self):
        global CONFIG
        self.tmp = tempfile.mkdtemp(prefix="rga-cadence-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        shutil.copyfile(os.path.join(FIXTURES, "phase7.jsonl"), self.queue)
        self._prev = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue
        CONFIG = clients.load("productive")
        self.config = CONFIG
        approve_everything()

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def rec(self, rid="meridian"):
        return store.get(rid)

    def timeline(self, rid="meridian", recs=None):
        return cadence.build(self.rec(rid), self.config, recs=recs)

    def steps(self, rid="meridian", contact=None):
        t = self.timeline(rid)
        contact = contact or next(iter(t["contacts"]))
        return t["contacts"][contact]


class TestTheTimelineShape(CadenceTest):
    def test_all_seven_steps_on_the_documented_days(self):
        steps = self.steps(contact="ivana-saric")
        self.assertEqual([(k, steps[k]["day"], steps[k]["channel"]) for k in
                          ("day1", "day3", "day5", "day8", "day10", "day15", "day21")],
                         [("day1", 1, "email"), ("day3", 3, "linkedin"),
                          ("day5", 5, "email"), ("day8", 8, "linkedin"),
                          ("day10", 10, "email"), ("day15", 15, "email"),
                          ("day21", 21, "email")])

    def test_exactly_two_emails_are_model_written(self):
        """Section 7: the ratio is the cost per lead at 500 domains."""
        steps = self.steps(contact="ivana-saric")
        emails = [k for k in steps if steps[k]["channel"] == "email"]
        generated = [k for k in emails if steps[k].get("generated")]
        self.assertEqual(sorted(generated), ["day1", "day15"])
        self.assertEqual(len(generated), 2)
        self.assertEqual(sorted(cadence.GENERATED_KEYS), ["day1", "day15"])
        self.assertEqual(len(emails) - len(generated), 3)   # the three templates

    def test_never_two_channels_on_the_same_day_for_one_person(self):
        for rid in ("meridian", "harbourline", "vantage"):
            for key, steps in self.timeline(rid)["contacts"].items():
                self.assertEqual(cadence.channel_conflicts(steps), [], f"{rid}:{key}")

    def test_the_linkedin_note_never_references_the_email(self):
        for rid in ("meridian", "harbourline", "vantage"):
            for key, steps in self.timeline(rid)["contacts"].items():
                self.assertEqual(cadence.cross_channel_leaks(steps), [], f"{rid}:{key}")

    def test_a_leak_would_be_caught_if_one_were_introduced(self):
        leaky = {"day3": {"channel": "linkedin", "note": "replying to my email below"},
                 "day5": {"channel": "email", "subject": "s",
                          "body": "as I said in my LinkedIn connection request"}}
        leaks = cadence.cross_channel_leaks(leaky)
        self.assertGreaterEqual(len(leaks), 2)
        self.assertTrue(any(l.startswith("day3") for l in leaks))
        self.assertTrue(any(l.startswith("day5") for l in leaks))

    def test_the_buyer_track_starts_behind_the_champion(self):
        offset = self.config["personas"]["economic_buyer"]["start_offset_days"]
        champion = self.steps(contact="ivana-saric")
        buyer = self.steps(contact="damir-vukovic")
        self.assertEqual(buyer["day1"]["day"], champion["day1"]["day"] + offset)
        self.assertEqual(buyer["day21"]["day"], champion["day21"]["day"] + offset)

    def test_a_champion_has_no_offset(self):
        self.assertEqual(cadence.track_offset({"persona": "champion"}, self.config), 0)


class TestTemplatesAreExpandedAndLinted(CadenceTest):
    def test_a_template_email_arrives_with_a_real_subject_and_body(self):
        step = self.steps(contact="ivana-saric")["day5"]
        self.assertFalse(step["generated"])
        self.assertEqual(step["template"], "persona_pain")
        self.assertNotIn("{", step["body"])
        self.assertTrue(40 <= len(step["body"].split()) <= 180)

    def test_every_eligible_email_passes_lint(self):
        """The invariant that matters: nothing eligible is unlinted."""
        checked = 0
        for rid in ("meridian", "harbourline", "vantage"):
            rec = self.rec(rid)
            for key, steps in self.timeline(rid)["contacts"].items():
                for step_key, step in steps.items():
                    if step["channel"] != "email" or step["status"] != "eligible":
                        continue
                    self.assertEqual(lint.check(rec, key, step), [],
                                     f"{rid}:{key}:{step_key}")
                    checked += 1
        self.assertGreater(checked, 10)

    def test_an_email_step_that_fails_lint_is_blocked_with_its_reasons(self):
        """A contact with no address gets no email, and the reason is recorded."""
        steps = self.timeline("harbourline")["contacts"]["harriet-vance"]
        self.assertEqual(steps["day5"]["status"], "blocked")

    def test_a_template_variable_that_creates_a_violation_blocks_that_step(self):
        """The expansion is what gets linted, not the template."""
        recs = store.load()
        for rec in recs:
            if rec["id"] == "meridian":
                # An em dash arriving through a variable, not through the template.
                rec["evidence"] = {"ivana-saric": ["month end reconciliation — five offices"]}
        store.save(recs)
        steps = self.steps(contact="ivana-saric")
        self.assertEqual(steps["day5"]["status"], "blocked")
        self.assertIn("em_dash", steps["day5"]["blocked_by"])
        self.assertIn("—", steps["day5"]["body"])

    def test_the_rest_of_the_timeline_continues_when_one_step_is_blocked(self):
        recs = store.load()
        for rec in recs:
            if rec["id"] == "meridian":
                rec["evidence"] = {"ivana-saric": ["a line with an em dash — here"]}
        store.save(recs)
        steps = self.steps(contact="ivana-saric")
        self.assertEqual(steps["day5"]["status"], "blocked")
        for other in ("day1", "day10", "day15", "day21"):
            self.assertEqual(steps[other]["status"], "eligible", other)

    def test_another_company_is_unaffected_by_a_blocked_step(self):
        recs = store.load()
        for rec in recs:
            if rec["id"] == "meridian":
                rec["evidence"] = {"ivana-saric": ["dash — here"]}
        store.save(recs)
        other = self.timeline("harbourline")
        for key in ("rowan-blake", "jesse-hollis"):
            statuses = {s["status"] for s in other["contacts"][key].values()}
            self.assertIn("eligible", statuses, key)
            self.assertNotIn("blocked", statuses, key)

    def test_a_generated_email_that_is_missing_simply_is_not_scheduled(self):
        recs = store.load()
        for rec in recs:
            if rec["id"] == "meridian":
                rec["cadence"]["ivana-saric"].pop("day1")
        store.save(recs)
        self.assertNotIn("day1", self.steps(contact="ivana-saric"))


class TestTheConnectionGate(CadenceTest):
    def test_day_8_waits_until_the_connection_is_accepted(self):
        self.assertEqual(self.steps(contact="ivana-saric")["day8"]["status"], "waiting")

    def test_accepting_the_connection_releases_day_8(self):
        recs = store.load()
        rec = next(r for r in recs if r["id"] == "meridian")
        cadence.record_event(rec, "connection_accepted", "ivana-saric")
        store.save(recs)
        self.assertEqual(self.steps(contact="ivana-saric")["day8"]["status"], "eligible")

    def test_accepting_switches_day_10_to_the_short_variant(self):
        before = self.steps(contact="ivana-saric")["day10"]
        self.assertEqual(before["template"], "comparable_proof")
        recs = store.load()
        rec = next(r for r in recs if r["id"] == "meridian")
        cadence.record_event(rec, "connection_accepted", "ivana-saric")
        store.save(recs)
        after = self.steps(contact="ivana-saric")["day10"]
        self.assertEqual(after["template"], "comparable_proof_short")
        self.assertLess(len(after["body"].split()), len(before["body"].split()))

    def test_the_short_variant_still_passes_lint(self):
        recs = store.load()
        rec = next(r for r in recs if r["id"] == "meridian")
        cadence.record_event(rec, "connection_accepted", "ivana-saric")
        store.save(recs)
        step = self.steps(contact="ivana-saric")["day10"]
        self.assertEqual(lint.check(self.rec(), "ivana-saric", step), [])

    def test_one_contacts_acceptance_does_not_release_another(self):
        recs = store.load()
        rec = next(r for r in recs if r["id"] == "meridian")
        cadence.record_event(rec, "connection_accepted", "ivana-saric")
        store.save(recs)
        self.assertEqual(self.steps(contact="marin-kovac")["day8"]["status"], "waiting")


class TestTheCompanyPause(CadenceTest):
    """The acceptance test: a reply on one channel pauses both tracks company-wide."""

    def pause_with(self, kind, contact):
        recs = store.load()
        rec = next(r for r in recs if r["id"] == "meridian")
        cadence.record_event(rec, kind, contact)
        store.save(recs)
        return self.timeline("meridian")

    def test_a_champion_email_reply_stops_the_buyer_on_both_channels(self):
        timeline = self.pause_with("email_reply", "ivana-saric")
        self.assertTrue(timeline["paused"])
        buyer = timeline["contacts"]["damir-vukovic"]
        self.assertTrue(all(s["status"] == "paused" for s in buyer.values()))
        self.assertEqual({s["channel"] for s in buyer.values()}, {"email", "linkedin"})

    def test_a_champion_linkedin_reply_stops_the_buyer_too(self):
        timeline = self.pause_with("linkedin_reply", "ivana-saric")
        buyer = timeline["contacts"]["damir-vukovic"]
        self.assertTrue(all(s["status"] == "paused" for s in buyer.values()))

    def test_a_buyer_reply_stops_the_champions(self):
        timeline = self.pause_with("email_reply", "damir-vukovic")
        for key in ("ivana-saric", "marin-kovac"):
            self.assertTrue(all(s["status"] == "paused"
                                for s in timeline["contacts"][key].values()), key)

    def test_the_replier_is_paused_as_well_as_everyone_else(self):
        timeline = self.pause_with("email_reply", "ivana-saric")
        self.assertTrue(all(s["status"] == "paused"
                            for s in timeline["contacts"]["ivana-saric"].values()))

    def test_an_unrelated_company_carries_on(self):
        self.pause_with("email_reply", "ivana-saric")
        other = self.timeline("harbourline")
        self.assertIsNone(other["paused"])
        statuses = {s["status"] for steps in other["contacts"].values()
                    for s in steps.values()}
        self.assertIn("eligible", statuses)

    def test_a_connection_accepted_event_does_not_pause_anything(self):
        timeline = self.pause_with("connection_accepted", "ivana-saric")
        self.assertIsNone(timeline["paused"])

    def test_pausing_never_deletes_a_step(self):
        before = {k: sorted(v) for k, v in self.timeline()["contacts"].items()}
        self.pause_with("email_reply", "ivana-saric")
        after = {k: sorted(v) for k, v in self.timeline()["contacts"].items()}
        self.assertEqual(before, after)

    def test_the_pause_is_recorded_with_its_cause_and_is_auditable(self):
        self.pause_with("linkedin_reply", "marin-kovac")
        rec = self.rec()
        self.assertEqual(rec["paused"]["reason"], "linkedin_reply")
        self.assertEqual(rec["paused"]["by"], "marin-kovac")
        self.assertTrue(any("both tracks paused" in e["note"] for e in rec["log"]))
        replies = [e for e in rec["events"] if e["type"] == "linkedin_reply"]
        self.assertEqual(len(replies), 1)
        # the pause itself is an event too, so it can be reported on
        self.assertEqual(len([e for e in rec["events"]
                              if e["type"] == "company_paused"]), 1)

    def test_recording_the_same_reply_twice_is_idempotent(self):
        self.pause_with("email_reply", "ivana-saric")
        first = self.rec()["paused"]
        self.pause_with("email_reply", "ivana-saric")
        self.assertEqual(self.rec()["paused"], first)

    def test_a_second_record_for_the_same_company_is_paused_too(self):
        """Whole company means every record for that company, not one row."""
        recs = store.load()
        twin = dict(recs[0])
        twin["id"] = "meridian-second-list"
        recs.append(twin)
        cadence.record_event(recs[0], "email_reply", "ivana-saric")
        store.save(recs)
        recs = store.load()
        twin_rec = next(r for r in recs if r["id"] == "meridian-second-list")
        twin_rec["events"], twin_rec["paused"] = [], None
        timeline = cadence.build(twin_rec, self.config, recs=recs)
        self.assertTrue(timeline["paused"])

    def test_an_unknown_event_is_refused(self):
        with self.assertRaises(cadence.CadenceError):
            cadence.record_event(self.rec(), "carrier_pigeon", "ivana-saric")


class TestDue(CadenceTest):
    def test_only_steps_whose_day_has_arrived_are_due(self):
        timeline = self.timeline()
        day3 = {(d["contact"], d["step"]) for d in cadence.due(timeline, 3)}
        day21 = {(d["contact"], d["step"]) for d in cadence.due(timeline, 21)}
        self.assertIn(("ivana-saric", "day1"), day3)
        self.assertNotIn(("ivana-saric", "day5"), day3)
        self.assertIn(("ivana-saric", "day5"), day21)

    def test_nothing_is_due_while_the_company_is_paused(self):
        recs = store.load()
        rec = next(r for r in recs if r["id"] == "meridian")
        cadence.record_event(rec, "email_reply", "ivana-saric")
        store.save(recs)
        self.assertEqual(cadence.due(self.timeline(), 30), [])


class TestBlockedRecords(CadenceTest):
    def test_a_dropped_record_has_no_eligible_step(self):
        store.drop("meridian", "suppressed (live account)")
        statuses = {s["status"] for steps in self.timeline()["contacts"].values()
                    for s in steps.values()}
        self.assertEqual(statuses, {"blocked"})

    def test_an_unsendable_contact_gets_no_email_but_may_get_linkedin(self):
        """Unsendable the way the system decides it: from the verdict.

        This used to set `contact["sendable"] = False` and assert the step
        blocked. That passed, and it was asserting the wrong thing - SCHEMA.md
        is explicit that the stored field is a projection and that "editing a
        legacy field cannot flip a decision". `cadence` was the one place that
        read it, so the flag really did flip the decision there and nowhere
        else. See the companion test below.
        """
        from src import verification
        recs = store.load()
        rec = next(r for r in recs if r["id"] == "meridian")
        contact = rec["contacts"][0]
        evidence = [verification.result("contactout", verification.S_INVALID,
                                        contact["email"])]
        verification.apply(contact, verification.decide(evidence), evidence)
        store.save(recs)
        steps = self.steps(contact="ivana-saric")
        self.assertEqual(steps["day1"]["status"], "blocked")
        self.assertEqual(steps["day3"]["status"], "eligible")

    def test_the_stored_sendable_flag_cannot_flip_the_decision(self):
        """The invariant the fix above restores.

        `verification.is_sendable` is the only authority. A contact whose
        evidence says valid stays sendable however the legacy field is edited,
        and one whose evidence says invalid stays unsendable the same way.
        """
        from src import verification
        for flag, status, expected in ((False, verification.S_VALID, "eligible"),
                                       (True, verification.S_INVALID, "blocked")):
            recs = store.load()
            rec = next(r for r in recs if r["id"] == "meridian")
            contact = rec["contacts"][0]
            evidence = [verification.result(p, status, contact["email"])
                        for p in ("contactout", "deliverable")]
            # A fresh estate each pass: `apply` is append-only, so without
            # this the previous status stays and the planted lie is tested
            # against the wrong evidence.
            contact.pop("verification", None)
            verification.apply(contact, verification.decide(evidence), evidence)
            contact["sendable"] = flag          # the lie, planted after the fact
            store.save([])
            store.save(recs)
            self.assertEqual(self.steps(contact="ivana-saric")["day1"]["status"],
                             expected, f"flag={flag} status={status}")

    def test_a_contact_with_no_profile_gets_no_linkedin_step(self):
        recs = store.load()
        rec = next(r for r in recs if r["id"] == "meridian")
        rec["contacts"][0]["linkedin"] = None
        store.save(recs)
        self.assertEqual(self.steps(contact="ivana-saric")["day3"]["status"], "blocked")

    def test_a_dependent_step_on_a_channel_we_cannot_reach_is_blocked(self):
        """Not `waiting`. Day 8 needs an accepted connection, and there is
        nobody to send the request to, so it can never arrive. Reporting
        `waiting` reads to a reviewer as "this happens later" when the honest
        answer is that it never happens at all."""
        recs = store.load()
        rec = next(r for r in recs if r["id"] == "meridian")
        rec["contacts"][0]["linkedin"] = None
        store.save(recs)
        self.assertEqual(self.steps(contact="ivana-saric")["day8"]["status"],
                         "blocked")

    def test_a_dependent_step_still_waits_when_the_profile_is_there(self):
        """The ordering fix must not turn every unaccepted step into a block."""
        self.assertEqual(self.steps(contact="ivana-saric")["day8"]["status"],
                         "waiting")


if __name__ == "__main__":
    unittest.main()
