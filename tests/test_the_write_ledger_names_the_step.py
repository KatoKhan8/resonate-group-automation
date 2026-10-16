"""The write-ledger row names the step, or says UNKNOWN loudly.

TASK 0230, section 2. pilotcaps filed that `step=` is recorded on no row
anywhere. Measured: TRUE for the write ledger - the row `providerwrites._
ledger` writes held `at/operation/outcome/campaign/tenant/by/detail/pid/
argv` and nothing else, on every exit, since 2026-09-24. It is FALSE for
the ACTION ledger, whose `reserve()` rows have always REQUIRED `step_key`
(src/actionledger.py) - the step was reserved before the write and then
dropped from the row that recorded the write itself. When a prospect
replies, that is exactly the join that is missing.

These tests pin the contract the brief demands:

  - a write whose caller holds an Authorization records that
    authorization's `step_key` (and its `key`) on the row, on EVERY exit -
    refusal included, and the refusal these tests use is the door refusing
    for want of the step copy, which is the sharpest case: the row names
    the step even as the door rejects the write for not seeing its words;
  - a write with no authorization records `step: UNKNOWN` and `key:
    UNKNOWN`, and the row is STILL WRITTEN - a ledger with an honest
    UNKNOWN is usable, a ledger with a dropped row is not, and a
    plausible-looking default is worse than either;
  - the change is additive: the row still carries everything it always
    carried, so every existing reader still parses it.
"""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import executionguard, providerwrites, store  # noqa: E402


class _Ledgered(unittest.TestCase):
    """Point the ledger at a throwaway file. Never the real `work/`."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-step-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.path = os.path.join(self.tmp, "provider-writes.jsonl")
        self._old = os.environ.get(providerwrites.PROVIDER_WRITES_LEDGER)
        os.environ[providerwrites.PROVIDER_WRITES_LEDGER] = self.path
        self.addCleanup(self._restore)

    def _restore(self):
        if self._old is None:
            os.environ.pop(providerwrites.PROVIDER_WRITES_LEDGER, None)
        else:
            os.environ[providerwrites.PROVIDER_WRITES_LEDGER] = self._old

    def rows(self):
        if not os.path.exists(self.path):
            return []
        with io.open(self.path, encoding="utf-8") as fh:
            return [json.loads(l) for l in fh if l.strip()]


class AWriteWithAKnownStepRecordsIt(_Ledgered):

    def test_on_the_refusal_exit(self):
        """The door refuses this write for want of the step copy - and the
        row still names WHICH step the write was for.

        `LINKEDIN_ADD_LEAD` is SUPPORTED and prospect-facing, so `perform`
        demands an Authorization and then `_require_approved_words` demands
        the rendered step. Handing the token and not the copy is a refusal,
        and the refusal is the sharpest case this file has: the ledger names
        the step at the very moment the door rejects the write for not
        seeing its words. No campaign is bound and no transport runs; the
        refusal fires before either could matter."""
        authorization = executionguard.Authorization(
            key="rec1:jane-doe:li1:linkedin",
            operation=providerwrites.LINKEDIN_ADD_LEAD,
            channel="linkedin", workspace="productive",
            campaign_id="c605732", sender_id="s1", rec_id="rec1",
            contact_key="jane-doe", step_key="li1", fingerprint="f1",
            gates=(), at="2026-10-16T00:00:00Z")
        with self.assertRaises(providerwrites.WriteRefused) as caught:
            providerwrites.perform(
                providerwrites.LINKEDIN_ADD_LEAD, campaign="c605732",
                authorization=authorization, payload={},
                transport=lambda p: None, readback=lambda: {}, expected=None,
                by="test")
        self.assertIn("no `step`", str(caught.exception))
        rows = self.rows()
        self.assertEqual(1, len(rows), "the refusal left no ledger row")
        self.assertEqual("li1", rows[0]["step"])
        self.assertEqual("rec1:jane-doe:li1:linkedin", rows[0]["key"])
        self.assertEqual("refused", rows[0]["outcome"])


class AWriteWithNoStepRecordsUnknownAndStaysWritten(_Ledgered):

    def test_unknown_is_loud_not_blank_and_not_a_dropped_row(self):
        """A sealed verb refuses before any authorization is consulted, so
        the writer genuinely does not know a step. The row must still land,
        and its step must be the sentinel UNKNOWN - not an empty string
        that reads like a clean miss, not a null a report skips over, and
        not the row's absence, which is the one thing worse than a wrong
        answer: it is no answer."""
        with self.assertRaises(providerwrites.WriteRefused):
            providerwrites.perform(
                providerwrites.EMAIL_RESUME, campaign="c491", by="test",
                payload={}, transport=lambda p: None,
                readback=lambda: {}, expected={})
        rows = self.rows()
        self.assertEqual(1, len(rows),
                         "a write with no step dropped its row")
        self.assertEqual("UNKNOWN", rows[0]["step"])
        self.assertEqual("UNKNOWN", rows[0]["key"])

    def test_a_direct_ledger_call_defaults_to_unknown_too(self):
        """`_ledger` keeps its own UNKNOWN default so a caller that writes
        a row without going through `perform` cannot record a blank step by
        accident. The zero-argument call must stay a TypeError - that is a
        pinned contract in test_a_resume_leaves_a_ledger_row, and this
        change must not soften it."""
        with self.assertRaises(TypeError):
            providerwrites._ledger()
        providerwrites._ledger("bison.resume", "refused", campaign="c491")
        row = self.rows()[0]
        self.assertEqual("UNKNOWN", row["step"])
        self.assertEqual("UNKNOWN", row["key"])


class TheChangeIsAdditive(_Ledgered):

    def test_the_row_still_carries_what_it_always_did(self):
        """Everything the row held before TASK 0230 still holds, with the
        same shapes: `at` UTC-Z, the verb, the outcome, the campaign, the
        caller, the detail, the pid and the argv. A reader that parsed the
        file yesterday parses it today; new keys are additive, old keys are
        untouched."""
        with self.assertRaises(providerwrites.WriteRefused):
            providerwrites.perform(
                providerwrites.EMAIL_RESUME, campaign="c491", by="operator",
                payload={}, transport=lambda p: None,
                readback=lambda: {}, expected={})
        row = self.rows()[0]
        self.assertTrue(row["at"].endswith("Z"))
        self.assertEqual("bison.resume", row["operation"])
        self.assertEqual("refused", row["outcome"])
        self.assertEqual("c491", row["campaign"])
        self.assertEqual("operator", row["by"])
        self.assertTrue(row["detail"])
        self.assertIsInstance(row["pid"], int)
        self.assertIsInstance(row["argv"], list)
        # And the ledger file itself is one JSON object per line, exactly
        # as before - additive keys, not a new format.
        with io.open(self.path, encoding="utf-8") as fh:
            lines = [l for l in fh.read().splitlines() if l.strip()]
        self.assertEqual(1, len(lines))
        self.assertEqual(row, json.loads(lines[0]))

    def test_the_ledger_still_honours_the_production_barrier(self):
        """The row must not land in real client state, and honouring the
        barrier still means quietly not writing - the ledger must never
        change the verdict it records. The step changes nothing about
        that."""
        target = os.path.join(store.PRODUCTION_WORK, "provider-writes.jsonl")
        before = os.path.exists(target)
        os.environ[providerwrites.PROVIDER_WRITES_LEDGER] = target
        providerwrites._ledger("bison.resume", "refused", campaign="c491",
                               step="em1", key="rec1:jane-doe:em1:email")
        self.assertEqual(before, os.path.exists(target),
                         "the ledger wrote into real client state")


if __name__ == "__main__":
    unittest.main()
