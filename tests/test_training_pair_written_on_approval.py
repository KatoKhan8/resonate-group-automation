"""TASK-310: every APPROVED file feeds work/training/.

Two things this test proves:
1. A pair IS written when the operator approves a review file.
2. A pair is NOT written when there is no approval.

The capture hooks reviewapproval.record(), which is the only function that
knows an approval happened. The pipeline runs whether or not the operator
ever approves, and that is exactly the distinction that matters.
"""
import json
import os
import tempfile
import unittest

from src import store, training, reviewapproval


class TrainingPairWrittenOnApproval(unittest.TestCase):
    """A pair is written on approval and NOT written without one."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(store.use_directory(self.tmp))
        # Point OUT at the temp directory so the review file lands there.
        os.environ["OUT"] = os.path.join(self.tmp, "out")
        os.makedirs(os.environ["OUT"], exist_ok=True)
        self.addCleanup(lambda: os.environ.pop("OUT", None))

    def _make_record(self, email="prospect@example.test"):
        """A minimal record with one contact."""
        return {
            "id": "rec-001",
            "company": "Acme Corp",
            "domain": "acme.test",
            "lane": "cold",
            "hook": "They posted about margin visibility",
            "state": "drafted",
            "research": [
                {"field": "margin_signal", "text": "Margin visible after 6pm"},
                {"field": "team_size", "text": "12-person delivery team"},
            ],
            "contacts": [{
                "name": "Jane Prospect",
                "title": "Head of Delivery",
                "email": email,
                "verdict": "verified",
                "angle": "margin_visible_late",
                "persona": "delivery_leader",
            }],
            "cadence": {},
            "events": [],
        }

    def _write_review_file(self, recs):
        """Write a minimal review HTML from the records.

        Instead of calling render.build() (which needs full lint results),
        write a minimal HTML file with the expected structure.
        """
        from src import lint
        review_path = os.path.join(os.environ["OUT"], "review.html")
        cards = []
        for rec in recs:
            for contact in rec.get("contacts") or []:
                email = contact.get("email", "")
                key = lint.contact_key(contact)
                cadence = (rec.get("cadence") or {}).get(key, {})
                # Find the first email step.
                step = None
                for step_key, step_data in cadence.items():
                    if step_data.get("channel") == "email":
                        step = step_data
                        break

                if step:
                    status = "clean"
                    subject = step.get("subject", "")
                    body = step.get("body", "")
                else:
                    status = "held"
                    subject = ""
                    body = ""

                card = f'''<article class="{status}">
  <header>
    <div class=top><h2>{rec.get("company", "")}</h2>
      <span class=lane>{rec.get("lane", "")}</span>
      <span class=day>day1</span>
      <span class="tag {status}">{"clean" if status == "clean" else "held, address not cleared"}</span></div>
    <div class=meta>{contact.get("name", "")} &middot; {contact.get("title", "")} &middot; <code>{email}</code> &middot; {contact.get("verdict", "")}</div>
  </header>
  <p class=why>{rec.get("hook", "")}</p>
  <div class=subject>{subject}</div>
  <pre>{body}</pre>
  <footer class="{status}">passes every rule</footer>
</article>
'''
                cards.append(card)

        html = f'''<!doctype html><meta charset=utf-8>
<title>Batch review</title>
<div class=wrap>
<h1>Batch review</h1>
<div class=sum><b>{len(cards)}</b> generated email(s)</div>
{"".join(cards)}
</div>
'''
        with open(review_path, "w", encoding="utf-8") as f:
            f.write(html)
        return review_path

    def test_pair_is_written_on_approval(self):
        """An approval writes one training pair per lead in the review file."""
        rec = self._make_record()
        # Store the record so render.build() can find it.
        store.save([rec])
        # Generate a dummy cadence step so the review file has content.
        # The contact key is based on the name slug: "jane-prospect".
        rec["cadence"] = {
            "jane-prospect": {
                "day1": {
                    "channel": "email",
                    "generated": True,
                    "subject": "margin visibility after hours",
                    "body": "Hi Jane,\n\nSaw your post about margin visibility.\n\nBest",
                }
            }
        }
        store.save([rec])

        review_path = self._write_review_file([rec])
        self.assertTrue(os.path.exists(review_path))

        review_hash = reviewapproval.file_hash(review_path)

        # Before approval: no pairs.
        self.assertEqual(training.count()["pairs"], 0)

        # Approve.
        row = reviewapproval.record(
            campaign="camp-123",
            review_hash=review_hash,
            by="zvonimir",
        )

        # After approval: at least one pair.
        result = training.count()
        self.assertGreater(result["pairs"], 0)
        self.assertGreater(result["approved"], 0)

        # The pair has the expected structure.
        pairs_path = training.path()
        with open(pairs_path, encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]
        self.assertEqual(len(lines), result["pairs"])

        pair = lines[0]
        self.assertEqual(pair["campaign"], "camp-123")
        self.assertEqual(pair["review_hash"], review_hash)
        self.assertEqual(pair["approval_by"], "zvonimir")
        self.assertEqual(pair["record_id"], "rec-001")
        self.assertFalse(pair["held"])
        self.assertIn("input", pair)
        self.assertIn("output", pair)
        self.assertIn("company", pair["input"])
        self.assertIn("subject", pair["output"])

    def test_pair_is_not_written_without_approval(self):
        """No approval means no pair, even if the review file exists."""
        rec = self._make_record()
        store.save([rec])
        rec["cadence"] = {
            "jane-prospect": {
                "day1": {
                    "channel": "email",
                    "generated": True,
                    "subject": "test subject",
                    "body": "Test body",
                }
            }
        }
        store.save([rec])

        review_path = self._write_review_file([rec])
        self.assertTrue(os.path.exists(review_path))

        # No approval call.
        result = training.count()
        self.assertEqual(result["pairs"], 0)
        self.assertEqual(result["approved"], 0)

    def test_pair_not_written_when_hash_mismatches(self):
        """If the review file has been overwritten, the hash won't match."""
        rec = self._make_record()
        store.save([rec])
        rec["cadence"] = {
            "jane-prospect": {
                "day1": {
                    "channel": "email",
                    "generated": True,
                    "subject": "test subject",
                    "body": "Test body",
                }
            }
        }
        store.save([rec])

        review_path = self._write_review_file([rec])
        original_hash = reviewapproval.file_hash(review_path)

        # Overwrite the review file with different content.
        with open(review_path, "w", encoding="utf-8") as f:
            f.write("<html>different content</html>")

        # Approve with the OLD hash.
        reviewapproval.record(
            campaign="camp-123",
            review_hash=original_hash,
            by="zvonimir",
        )

        # No pairs written because the hash doesn't match.
        result = training.count()
        self.assertEqual(result["pairs"], 0)

    def test_held_lead_captured_separately(self):
        """A held lead is captured with held=true."""
        rec = self._make_record()
        store.save([rec])
        # No cadence step -> the lead will be "held" in the review.
        review_path = self._write_review_file([rec])
        review_hash = reviewapproval.file_hash(review_path)

        reviewapproval.record(
            campaign="camp-123",
            review_hash=review_hash,
            by="zvonimir",
        )

        result = training.count()
        # The held lead is captured.
        self.assertGreater(result["pairs"], 0)
        self.assertGreater(result["held"], 0)

    def test_count_returns_progress_toward_target(self):
        """The counter shows how many pairs, how far from 5,000."""
        result = training.count()
        self.assertIn("pairs", result)
        self.assertIn("held", result)
        self.assertIn("approved", result)
        self.assertIn("remaining", result)
        self.assertEqual(result["pairs"], 0)
        self.assertEqual(result["remaining"], training.TARGET)


if __name__ == "__main__":
    unittest.main()
