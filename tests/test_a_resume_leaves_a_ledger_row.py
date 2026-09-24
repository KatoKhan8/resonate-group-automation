"""Every write through the door leaves a row — a refused one most of all.

## What was true before 2026-09-24

`providers._log_refusal` wrote the REFUSALS and nothing wrote the successes.
So `work/provider-write-refusals.jsonl` grew only when the system said no,
and a write that worked left no trace anywhere. An audit that records one
half of a decision cannot answer "what did this process do", which is the
only question anybody asks it.

And `orchestrator.resume` did not go through the door at all. It cleared the
local pause, wrote a local event, and **never told the provider**. A resumed
campaign therefore read RUNNING locally while EmailBison still had it paused
— and because `perform` was never called, there was no ledger row anywhere
to notice the divergence. A LinkedIn resume was worse: it did nothing and
said nothing, which is indistinguishable from a resume that worked.

## Why the resume verbs are declared and sealed

Resuming is the verb that puts a paused sequence back in front of people. It
is a sending action, so enabling it is an operator authorization and not the
write layer's to grant — CLAUDE.md records one such grant already spent, on
487, and says it must not be used again.

`heyreach.resume` additionally has **no route to enable**: `/campaign/Resume`
answers 400 and is deliberately absent from `heyreach.WRITE_ROUTES`.

Declaring them sealed is not a half-measure. A sealed verb refuses **by
name** and leaves a row, which is strictly better than the silence it
replaces.
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

from src import providerwrites, store  # noqa: E402


class _Ledgered(unittest.TestCase):
    """Point the ledger at a throwaway file. Never the real `work/`."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-ledger-")
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


class ARefusalIsAnEventAndNotAnAbsence(_Ledgered):

    def test_a_sealed_verb_leaves_a_row(self):
        """The row that did not exist before. `bison.resume` is declared and
        not supported, so this refuses — and the refusal is the thing worth
        recording."""
        with self.assertRaises(providerwrites.WriteRefused):
            providerwrites.perform(
                providerwrites.EMAIL_RESUME, campaign="c491",
                payload={"campaign_id": "491"},
                transport=lambda p: None, readback=lambda: {}, expected={})
        rows = self.rows()
        self.assertEqual(1, len(rows), "the refusal left no ledger row")
        self.assertEqual("bison.resume", rows[0]["operation"])
        self.assertEqual("refused", rows[0]["outcome"])
        self.assertEqual("c491", rows[0]["campaign"])

    def test_the_row_says_which_verb_and_why(self):
        """A row that does not name the operation cannot answer 'what did
        this process do'."""
        with self.assertRaises(providerwrites.WriteRefused):
            providerwrites.perform(
                providerwrites.LINKEDIN_RESUME, campaign="c605732",
                payload={}, transport=lambda p: None,
                readback=lambda: {}, expected={})
        row = self.rows()[0]
        self.assertEqual("heyreach.resume", row["operation"])
        self.assertTrue(row["detail"], "the refusal reason was not recorded")

    def test_a_transport_that_raises_is_recorded_as_failed(self):
        """Not every unhappy path is a refusal, and they must not read the
        same in the ledger."""
        def boom(_p):
            raise RuntimeError("the provider hung up")
        try:
            providerwrites.perform(
                providerwrites.EMAIL_PAUSE, campaign="c491",
                payload={"campaign_id": "491"}, transport=boom,
                readback=lambda: {"status": "paused"},
                expected={"status": "paused"})
        except Exception:
            pass
        outcomes = [r["outcome"] for r in self.rows()]
        self.assertTrue(outcomes, "nothing was recorded at all")
        self.assertNotIn("refused", outcomes,
                         "a transport failure was filed as a refusal")

    def test_every_row_carries_when_and_who(self):
        with self.assertRaises(providerwrites.WriteRefused):
            providerwrites.perform(
                providerwrites.EMAIL_RESUME, campaign="c491", by="operator",
                payload={}, transport=lambda p: None,
                readback=lambda: {}, expected={})
        row = self.rows()[0]
        self.assertTrue(row["at"].endswith("Z"))
        self.assertEqual("operator", row["by"])

    def test_the_ledger_never_turns_a_refusal_into_a_crash(self):
        """A full disk or a read-only volume must not convert a refusal into
        an exception some caller catches and retries around."""
        # A path whose PARENT is a regular file: `makedirs` cannot create it
        # and `open` cannot write it. A null byte would be rejected by
        # os.environ itself, which would test this test and not the code.
        blocker = os.path.join(self.tmp, "a-file-not-a-directory")
        with io.open(blocker, "w", encoding="utf-8") as fh:
            fh.write("x")
        os.environ[providerwrites.PROVIDER_WRITES_LEDGER] = os.path.join(
            blocker, "nested", "x.jsonl")
        with self.assertRaises(providerwrites.WriteRefused):
            providerwrites.perform(
                providerwrites.EMAIL_RESUME, campaign="c491", payload={},
                transport=lambda p: None, readback=lambda: {}, expected={})


    def test_the_barrier_is_not_swallowed(self):
        """A guard whose refusal is caught and discarded is not a guard.

        The first version of `_ledger` used a bare `except Exception: pass`,
        copied from `providers._log_refusal`. That would have swallowed
        `ProductionStateUnderTest` - the barrier that stops a test writing
        real client state - making the busiest writer in the repository the
        one that quietly bypassed it."""
        target = os.path.join(store.PRODUCTION_WORK, "provider-writes.jsonl")
        before = os.path.exists(target)
        os.environ[providerwrites.PROVIDER_WRITES_LEDGER] = target
        # It returns quietly. The barrier is honoured by the row NOT landing
        # in real client state - and re-raising here would make the ledger
        # decide the outcome of the write it is only supposed to record.
        providerwrites._ledger("bison.resume", "refused", campaign="c491")
        self.assertEqual(before, os.path.exists(target),
                         "the ledger wrote into real client state")

    def test_a_bug_in_the_ledger_surfaces_instead_of_hiding(self):
        """The bare except hid a NameError in this very function - `_store`
        used without being imported - so every call raised and not one row
        was written. Nothing failed, because nothing asserted a row existed."""
        with self.assertRaises(TypeError):
            providerwrites._ledger()


class AResumeLeavesARow(_Ledgered):
    """The operator's test, at the level that writes the row."""

    CAMPAIGN = {"campaign_id": "c491", "client": "productive",
                "bison_campaign_id": "491", "heyreach_campaign_id": "605732"}

    def test_a_resume_leaves_a_row_for_each_channel(self):
        from src import orchestrator
        out = orchestrator._resume_at_providers(dict(self.CAMPAIGN), "operator")
        rows = self.rows()
        self.assertEqual(2, len(rows), "a resume did not leave one row per channel")
        self.assertEqual({"bison.resume", "heyreach.resume"},
                         {r["operation"] for r in rows})
        for r in rows:
            self.assertEqual("refused", r["outcome"],
                             "a sealed verb performed instead of refusing")
        self.assertFalse(out["email"]["resumed"])
        self.assertFalse(out["linkedin"]["resumed"])

    def test_it_classifies_instead_of_raising(self):
        """A resume that cannot reach the provider is still a local resume.
        Losing the local state change would trade a visible divergence for an
        invisible one."""
        from src import orchestrator
        out = orchestrator._resume_at_providers(dict(self.CAMPAIGN), "operator")
        for channel in ("email", "linkedin"):
            self.assertTrue(out[channel]["attempted"])
            self.assertIn("error", out[channel])

    def test_a_campaign_naming_no_provider_is_not_an_error(self):
        """Never staged on a channel is not a failure and must not read as
        one."""
        from src import orchestrator
        out = orchestrator._resume_at_providers(
            {"campaign_id": "c1", "bison_campaign_id": "491"}, "operator")
        self.assertFalse(out["linkedin"]["attempted"])
        self.assertIn("names no", out["linkedin"]["why"])
        self.assertEqual(1, len(self.rows()),
                         "a channel that was never staged left a row")


class TheResumeVerbsAreDeclaredAndSealed(unittest.TestCase):

    def test_both_are_declared(self):
        """Declared so that asking refuses BY NAME rather than raising an
        unknown-operation error nobody can act on."""
        for verb in (providerwrites.EMAIL_RESUME,
                     providerwrites.LINKEDIN_RESUME):
            self.assertIn(verb, providerwrites.OPERATIONS)
            channel, facing, why = providerwrites.describe(verb)
            self.assertIn(channel, ("email", "linkedin"))
            self.assertTrue(why.strip())

    def test_neither_is_supported(self):
        """Enabling a resume is an operator authorization: it is the verb
        that puts a paused sequence back in front of people. CLAUDE.md
        records the 487 grant as spent."""
        for verb in (providerwrites.EMAIL_RESUME,
                     providerwrites.LINKEDIN_RESUME):
            self.assertNotIn(verb, providerwrites.SUPPORTED)

    def test_the_linkedin_entry_says_there_is_no_route(self):
        """It is sealed for a second, stronger reason than the email one, and
        the difference matters to whoever considers enabling it."""
        _c, _f, why = providerwrites.describe(providerwrites.LINKEDIN_RESUME)
        self.assertIn("no route", why.lower())


class TheLedgerMovesWithTheRestOfTheState(unittest.TestCase):

    def test_it_is_in_the_move_together_set(self):
        """`store.STATE_OVERRIDES` exists because a module added and
        forgotten here keeps pointing at the real `work/` while every other
        file moves to a temp one — and a test that writes into the
        developer's queue is the kind of thing discovered by losing a
        batch."""
        self.assertIn("PROVIDER_WRITES_LEDGER", store.STATE_OVERRIDES)

    def test_it_defaults_beside_the_queue(self):
        self.assertEqual(os.path.dirname(os.path.abspath(store.queue_path())),
                         os.path.dirname(providerwrites.ledger_path()))


if __name__ == "__main__":
    unittest.main()
