"""render.py, and the Phase 2 acceptance test from BUILD-SPEC section 10.

A deliberately bad draft (em dash, [FIRST NAME], "Screenshot attached", 12 words,
filler opener) trips exactly five rules and is absent from emailbison.csv, while
the good records still render.
"""
import csv
import io
import json
import os
import unittest

from src import lint, render, store
from tests.base import QueueTest

BAD = "harbourline"
CLEAN = "meridian"
HELD = "lumen"


class Phase2Base(QueueTest):
    def setUp(self):
        super().setUp()
        self.recs = self.use_fixture("phase2.jsonl")
        self.summary = render.build()
        self.csv_text = self.out_file("emailbison.csv")
        self.html = self.out_file("review.html")
        self.rows = list(csv.DictReader(io.StringIO(self.csv_text)))

    def step(self, rid):
        return next(r for r in lint.check_all(self.recs) if r["id"] == rid)


class TestTheBadDraft(Phase2Base):
    def test_it_is_the_draft_the_spec_describes(self):
        body = self.step(BAD)["step"]["body"]
        self.assertEqual(len(body.split()), 12)
        self.assertIn("—", body)
        self.assertIn("[FIRST NAME]", body)
        self.assertIn("attached", body.lower())
        self.assertIn("i wanted to reach out", body.lower())

    def test_it_trips_exactly_five_rules(self):
        self.assertEqual(set(self.step(BAD)["failures"]),
                         {"em_dash", "placeholder", "attachment",
                          "body_too_short", "filler_phrase"})
        self.assertEqual(len(self.step(BAD)["failures"]), 5)

    def test_nothing_else_about_the_record_is_wrong(self):
        """The five failures are the draft's, not the record's."""
        rec = {r["id"]: r for r in self.recs}[BAD]
        self.assertTrue(rec["diagnosis"]["died_because"])
        self.assertTrue(lint.sendable(rec["contacts"][0]))

    def test_it_is_absent_from_emailbison_csv(self):
        self.assertNotIn("rowan.blake@harbourline.test", self.csv_text)
        self.assertNotIn("picking this back up", self.csv_text)
        self.assertNotIn("[FIRST NAME]", self.csv_text)
        self.assertNotIn(BAD, [row["record_id"] for row in self.rows])

    def test_it_is_red_in_the_review_sheet_with_every_rule_named(self):
        self.assertIn('<article class="failed">', self.html)
        for code in ("em_dash", "placeholder", "attachment",
                     "body_too_short", "filler_phrase"):
            self.assertIn(code, self.html)


class TestGoodRecordsStillRender(Phase2Base):
    def test_the_clean_draft_is_in_emailbison_csv(self):
        row = next(r for r in self.rows if r["record_id"] == CLEAN)
        self.assertEqual(row["email"], "ivana.saric@meridian.test")
        self.assertEqual(row["first_name"], "Ivana")
        self.assertEqual(row["last_name"], "Saric")
        self.assertEqual(row["company"], "Meridian")
        self.assertEqual(row["domain"], "meridian.test")
        self.assertEqual(row["subject"], "five offices, one finance function")
        self.assertEqual(row["lane"], "domains")
        self.assertEqual(row["day"], "day1")
        self.assertIn("month end", row["body"])

    def test_only_the_clean_draft_is_in_the_push_file(self):
        self.assertEqual([r["record_id"] for r in self.rows], [CLEAN])

    def test_the_clean_draft_is_green_in_the_review_sheet(self):
        self.assertIn('<article class="clean">', self.html)
        self.assertIn("five offices, one finance function", self.html)


class TestHeldRecords(Phase2Base):
    def test_held_is_the_only_failure(self):
        self.assertEqual(self.step(HELD)["failures"], ["recipient_not_sendable"])
        self.assertEqual(self.step(HELD)["status"], "held")

    def test_held_stays_out_of_the_push_file(self):
        self.assertNotIn("luka.peric@lumen.test", self.csv_text)
        self.assertNotIn(HELD, [row["record_id"] for row in self.rows])

    def test_held_keeps_its_draft_and_is_visible_amber(self):
        self.assertIn('<article class="held">', self.html)
        self.assertIn("utilisation across four delivery teams", self.html)
        self.assertIn("Lumen", self.html)
        self.assertIn("accept_all", self.html)

    def test_held_state_is_not_written_to_the_queue(self):
        """Phase 4 owns the held transition, not render."""
        self.assertEqual({r["id"]: r["state"] for r in store.load()},
                         {CLEAN: "drafted", HELD: "drafted", BAD: "drafted"})


class TestRenderIsReadOnly(Phase2Base):
    def test_the_queue_is_byte_identical_after_a_render(self):
        with open(self.queue, "rb") as f:
            before = f.read()
        render.build()
        with open(self.queue, "rb") as f:
            self.assertEqual(f.read(), before)


class TestSummary(Phase2Base):
    def test_counts(self):
        s = json.loads(self.out_file("summary.json"))
        self.assertEqual(s["records"], 3)
        self.assertEqual(s["emails"], 3)
        self.assertEqual((s["clean"], s["held"], s["failed"]), (1, 1, 1))
        self.assertEqual(s["lanes"], {"domains": 2, "revive": 1})

    def test_failures_are_listed_per_step(self):
        s = json.loads(self.out_file("summary.json"))
        self.assertEqual(sorted(s["lint_failed"]),
                         ["harbourline:rowan-blake:day1",
                          "lumen:luka-peric:day1"])
        self.assertEqual(len(s["lint_failed"]["harbourline:rowan-blake:day1"]), 5)

    def test_failure_modes_are_counted(self):
        s = json.loads(self.out_file("summary.json"))
        self.assertEqual(s["failure_modes"], {"unanswered_question": 1})


class TestPushFileGuard(QueueTest):
    def test_the_writer_refuses_a_failed_row_even_if_handed_one(self):
        """Belt and braces: clean_steps is the only feed, and the writer re-checks."""
        self.use_fixture("phase2.jsonl")
        results = lint.check_all()
        forced = [dict(r, status="clean") for r in results if r["id"] == BAD]
        os.makedirs(self.out, exist_ok=True)
        path = os.path.join(self.out, "forced.csv")
        with self.assertRaises(AssertionError):
            render.write_emailbison(forced, path)

    def test_a_tripped_guard_leaves_no_half_written_push_file(self):
        self.use_fixture("phase2.jsonl")
        forced = [dict(r, status="clean") for r in lint.check_all()]
        os.makedirs(self.out, exist_ok=True)
        path = os.path.join(self.out, "emailbison.csv")
        with self.assertRaises(AssertionError):
            render.write_emailbison(forced, path)
        self.assertFalse(os.path.exists(path))


class TestDroppedRecordsAreShown(QueueTest):
    def test_a_dropped_record_appears_in_the_review_sheet_and_summary(self):
        self.use_fixture("phase2.jsonl")
        store.drop(HELD, "no address cleared verification")
        render.build()
        self.assertIn("no address cleared verification", self.out_file("review.html"))
        s = json.loads(self.out_file("summary.json"))
        self.assertEqual(s["dropped"], {HELD: "no address cleared verification"})


class TestEmptyQueue(QueueTest):
    def test_render_on_an_empty_queue_writes_a_header_only_csv(self):
        s = render.build()
        self.assertEqual(s["emails"], 0)
        self.assertEqual(self.out_file("emailbison.csv").strip().split("\n"), [
            "email,first_name,last_name,company,domain,title,subject,body,lane,day,record_id"])


class TestUnicodeSurvivesTheCsv(QueueTest):
    def test_croatian_name_round_trips(self):
        recs = self.use_fixture("phase2.jsonl")
        rec = next(r for r in recs if r["id"] == CLEAN)
        rec["contacts"][0]["name"] = "Ivana Šarić"
        # The cadence key is the slug of the contact name, so it moves with it.
        key = lint.contact_key(rec["contacts"][0])
        rec["cadence"][key] = rec["cadence"].pop("ivana-saric")
        store.save(recs)
        render.build()
        self.assertIn("Šarić", self.out_file("emailbison.csv"))

    def test_contact_key_transliterates_rather_than_dropping_letters(self):
        """Phase 6 replaced the ASCII-only slug: ć survives as c, not as nothing."""
        self.assertEqual(lint.contact_key({"name": "Ivana Saric"}), "ivana-saric")
        self.assertEqual(lint.contact_key({"name": "Ivana Šarić"}), "ivana-saric")
        self.assertEqual(lint.contact_key({"name": "Ćuk Šimić"}), "cuk-simic")


if __name__ == "__main__":
    unittest.main()
