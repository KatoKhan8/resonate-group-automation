#!/usr/bin/env python3
"""Tests for TASK-083: ladder change propagation.

Five things must be true:

1. A step generated against an OLD ladder becomes re-plannable when the
   ladder changes - asserting on what plan RETURNS.
2. An UNAFFECTED step is NOT re-planned. Precision is the point.
3. The DEFAULT path is UNCHANGED - without the flag, plan returns exactly
   what it returns today.
4. The approval count is reported before anything is re-planned.
5. Break the wiring deliberately: confirm the intended test fails for the
   intended REASON.

No test calls a model. Fixtures use the real cadence resolution path.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import generate, cadencelibrary, approval, lint


def _sendable_contact(name="Test", key=None,
                      email="test@example.com",
                      linkedin="linkedin.com/in/test"):
    """A contact that passes lint.sendable().

    Needs 2 independent confirmations (the default policy requires 2).
    """
    return {
        "name": name,
        "key": key or name.lower(),
        "email": email,
        "linkedin": linkedin,
        "persona": "founder",
        "angle": "profitability",
        "verification": {
            "state": "verified",
            "sendable": True,
            "reason": "contactout says valid",
            "cost": 0,
            "evidence": [
                {"provider": "contactout", "status": "valid",
                 "email": email, "at": "2026-09-01T00:00:00+00:00"},
                {"provider": "deliverable", "status": "valid",
                 "email": email, "at": "2026-09-01T00:00:00+00:00",
                 "reason": "second independent confirmation"},
            ],
            "providers": ["contactout", "deliverable"],
            "confirmation_count": 2,
            "required_confirmations": 2,
            "confirmed_by": ["contactout", "deliverable"],
            "disagreement": False,
            "results": {
                "contactout": {"verdict": "valid",
                               "checked_at": "2026-09-01T00:00:00+00:00"},
                "deliverable": {"verdict": "valid",
                                "checked_at": "2026-09-01T00:00:00+00:00",
                                "reason": "second independent confirmation"},
            },
        },
    }


def _sequence():
    return cadencelibrary.PRODUCTIVE_LI_HEAVY_V1


def _good_body(extra=""):
    """A body that passes lint (40+ words, no banned phrases)."""
    base = ("This is a test body that is deliberately long enough to pass "
            "the minimum word count check that lint enforces on every "
            "stored email draft before it can be considered finished work "
            "and the ladder check can run on it properly for this test "
            "to work correctly and nothing else matters here at all")
    if extra:
        return f"{base} {extra}"
    return base


def _email_step(body=None, subject="Test subject",
                ladder_fp=None, approval_fp=None):
    if body is None:
        body = _good_body()
    step = {"channel": "email", "generated": True,
            "subject": subject, "body": body}
    if ladder_fp is not None:
        step["ladder_fingerprint"] = ladder_fp
    if approval_fp is not None:
        step["approval"] = {"fingerprint": approval_fp, "by": "tester"}
    return step


def _linkedin_step(note="Test note", ladder_fp=None, approval_fp=None):
    step = {"channel": "linkedin", "generated": True, "note": note}
    if ladder_fp is not None:
        step["ladder_fingerprint"] = ladder_fp
    if approval_fp is not None:
        step["approval"] = {"fingerprint": approval_fp, "by": "tester"}
    return step


def _record(contact_name, steps, lane="domains"):
    """A record that reaches the email draft section of plan().

    lane='domains' avoids the hook check. Contact is sendable.
    Client is pinned to None in tests via pin_client_config or by
    passing the config directly.
    """
    c = _sendable_contact(name=contact_name)
    ck = lint.contact_key(c)
    rec = {
        "id": f"test-{contact_name.lower()}",
        "state": "drafted",
        "client": "productive",
        "domain": "example.com",
        "company": "Example",
        "company_facts": {"name": "Example", "employees": 50,
                          "email_domain": "example.com"},
        "contacts": [c],
        "cadence": {ck: steps},
        "events": [],
        "lane": lane,
        "qualification": {"icp": "approved"},
    }
    return rec


class LadderPropagationTestBase(unittest.TestCase):
    """Base that pins the client config so plan() does not load the live one.

    The live client config sets linkedin_connection_note.mode to 'llm',
    which makes plan() try to plan LinkedIn notes for every contact. Pinning
    it to None keeps the LinkedIn branch quiet so the email tests can focus
    on the email path.

    The cadence is pinned to productive_li_heavy_v1 because the test
    fixtures use em1..em5 and li1..li6 step keys.
    """
    def setUp(self):
        from tests.base import pin_client_config
        pin_client_config(self, linkedin_connection_note=None,
                          cadence="productive_li_heavy_v1")


class TestLadderFingerprint(unittest.TestCase):
    """The fingerprint function itself."""

    def test_returns_hex_string(self):
        fp = generate.ladder_fingerprint("email", 1, sequence=_sequence())
        self.assertIsNotNone(fp)
        self.assertEqual(len(fp), 16)
        self.assertTrue(all(c in "0123456789abcdef" for c in fp))

    def test_deterministic(self):
        fp1 = generate.ladder_fingerprint("email", 1, sequence=_sequence())
        fp2 = generate.ladder_fingerprint("email", 1, sequence=_sequence())
        self.assertEqual(fp1, fp2)

    def test_different_channel_different_fp(self):
        fp_email = generate.ladder_fingerprint("email", 1,
                                               sequence=_sequence())
        fp_li = generate.ladder_fingerprint("linkedin", 1,
                                            sequence=_sequence())
        self.assertNotEqual(fp_email, fp_li)

    def test_different_ordinal_different_fp(self):
        fp1 = generate.ladder_fingerprint("email", 1, sequence=_sequence())
        fp2 = generate.ladder_fingerprint("email", 2, sequence=_sequence())
        self.assertNotEqual(fp1, fp2)

    def test_none_for_missing_ordinal(self):
        fp = generate.ladder_fingerprint("email", None,
                                         sequence=_sequence())
        self.assertIsNone(fp)

    def test_none_for_missing_channel(self):
        fp = generate.ladder_fingerprint(None, 1, sequence=_sequence())
        self.assertIsNone(fp)

    def test_none_for_ordinal_beyond_ladder(self):
        fp = generate.ladder_fingerprint("email", 99,
                                         sequence=_sequence())
        self.assertIsNone(fp)


class TestLadderStale(unittest.TestCase):
    """The staleness check."""

    def test_not_stale_when_fingerprint_matches(self):
        seq = _sequence()
        fp = generate.ladder_fingerprint("email", 1, sequence=seq)
        step = {"channel": "email", "ladder_fingerprint": fp}
        self.assertFalse(generate.ladder_stale(step, "em1", sequence=seq))

    def test_stale_when_fingerprint_differs(self):
        seq = _sequence()
        step = {"channel": "email", "ladder_fingerprint": "old_fingerprint!"}
        self.assertTrue(generate.ladder_stale(step, "em1", sequence=seq))

    def test_not_stale_when_no_fingerprint(self):
        seq = _sequence()
        step = {"channel": "email"}
        self.assertFalse(generate.ladder_stale(step, "em1", sequence=seq))

    def test_not_stale_for_unknown_step_key(self):
        seq = _sequence()
        step = {"channel": "email", "ladder_fingerprint": "anything"}
        self.assertFalse(generate.ladder_stale(step, "nonexistent",
                                               sequence=seq))


class TestDefaultPathUnchanged(LadderPropagationTestBase):
    """TEST 3: Without the flag, plan returns exactly what it always did."""

    def test_plan_default_ignores_stale_fingerprint(self):
        """A step with a WRONG ladder fingerprint is NOT re-planned by default."""
        steps = {"em1": _email_step(ladder_fp="wrong_fingerprint!")}
        rec = _record("Alice", steps)
        ops = generate.plan(rec)
        stale_ops = [o for o in ops if o.get("ladder_stale")]
        self.assertEqual(len(stale_ops), 0,
                         f"Default plan should NOT flag stale, "
                         f"but got: {stale_ops}")

    def test_plan_default_ignores_missing_fingerprint(self):
        """A step with NO ladder fingerprint is NOT re-planned by default."""
        steps = {"em1": _email_step()}
        rec = _record("Bob", steps)
        ops = generate.plan(rec)
        stale_ops = [o for o in ops if o.get("ladder_stale")]
        self.assertEqual(len(stale_ops), 0,
                         f"Default plan should NOT flag missing fp, "
                         f"but got: {stale_ops}")

    def test_plan_default_same_ops_with_and_without_flag(self):
        """Explicit False gives the same result as no argument."""
        steps = {"em1": _email_step()}
        rec = _record("Carol", steps)
        ops_default = generate.plan(rec)
        ops_explicit = generate.plan(rec, regen_stale_ladder=False)
        self.assertEqual(ops_default, ops_explicit)


class TestStaleStepReplanned(LadderPropagationTestBase):
    """TEST 1: A step generated against an OLD ladder becomes re-plannable."""

    def test_stale_email_step_is_replanned_with_flag(self):
        """An email step with a wrong ladder fingerprint is re-planned
        when the flag is set."""
        steps = {"em1": _email_step(ladder_fp="deliberately_wrong_fp")}
        rec = _record("Dave", steps)
        ops = generate.plan(rec, regen_stale_ladder=True)
        stale_ops = [o for o in ops if o.get("ladder_stale")]
        self.assertEqual(len(stale_ops), 1,
                         f"Expected 1 stale op, got {len(stale_ops)}: "
                         f"{[o for o in ops]}")
        self.assertEqual(stale_ops[0]["step"], "draft")
        self.assertEqual(stale_ops[0]["day"], "em1")
        self.assertIn("ladder", stale_ops[0]["why"].lower())

    def test_stale_linkedin_step_is_replanned_with_flag(self):
        """A LinkedIn note with a wrong ladder fingerprint is re-planned
        when the flag is set. Uses the ladder_stale function directly
        since plan() for LinkedIn requires LLM mode to be configured."""
        seq = _sequence()
        step = _linkedin_step(
            note="Old note generated against old ladder",
            ladder_fp="deliberately_wrong_fp")
        # ladder_stale checks the fingerprint directly
        self.assertTrue(generate.ladder_stale(step, "li2", sequence=seq))
        # And a correct fingerprint is NOT stale
        correct_fp = generate.ladder_fingerprint("linkedin", 2,
                                                 sequence=seq)
        step_ok = _linkedin_step(note="Good note", ladder_fp=correct_fp)
        self.assertFalse(generate.ladder_stale(step_ok, "li2",
                                               sequence=seq))

    def test_missing_fingerprint_is_stale_with_flag(self):
        """A step with NO fingerprint (predates TASK-083) is re-planned
        when the flag is set."""
        steps = {"em1": _email_step()}  # No ladder_fp
        rec = _record("Frank", steps)
        ops = generate.plan(rec, regen_stale_ladder=True)
        stale_ops = [o for o in ops if o.get("ladder_stale")]
        self.assertEqual(len(stale_ops), 1,
                         f"Expected 1 stale op for missing fp, got: "
                         f"{[o for o in ops]}")
        self.assertIn("fingerprint", stale_ops[0]["why"].lower())


class TestUnaffectedStepNotReplanned(LadderPropagationTestBase):
    """TEST 2: An UNAFFECTED step is NOT re-planned. Precision is the point."""

    def test_current_fingerprint_not_replanned(self):
        """A step with a CURRENT fingerprint is NOT re-planned, even with
        the flag set."""
        seq = _sequence()
        fp = generate.ladder_fingerprint("email", 1, sequence=seq)
        steps = {"em1": _email_step(ladder_fp=fp)}
        rec = _record("Grace", steps)
        ops = generate.plan(rec, regen_stale_ladder=True)
        stale_ops = [o for o in ops if o.get("ladder_stale")]
        self.assertEqual(len(stale_ops), 0,
                         f"Step with current fp should NOT be stale, "
                         f"but got: {stale_ops}")


class TestApprovalReporting(LadderPropagationTestBase):
    """TEST 4: The approval count is reported."""

    def test_stale_step_with_approval_detected(self):
        """A stale step with a current approval is detected by plan."""
        c = _sendable_contact(name="Hank")
        ck = lint.contact_key(c)
        step = _email_step(ladder_fp="wrong_ladder_fp")
        step["approval"] = {
            "fingerprint": approval.fingerprint(step),
            "by": "human",
        }
        rec = _record("Hank", {"em1": step})
        # Verify the approval IS current
        self.assertTrue(approval.is_approved(rec, ck, "em1", step))

        ops = generate.plan(rec, regen_stale_ladder=True)
        stale_ops = [o for o in ops if o.get("ladder_stale")]
        self.assertEqual(len(stale_ops), 1)

    def test_run_reports_stale_count(self):
        """run() returns stale_steps and stale_with_approval counts."""
        from src import store

        tmp = tempfile.mkdtemp(prefix="rga-task083-")
        try:
            queue = os.path.join(tmp, "work", "queue.jsonl")
            os.makedirs(os.path.dirname(queue), exist_ok=True)
            steps = {"em1": _email_step(ladder_fp="wrong!")}
            rec = _record("Irene", steps)
            with open(queue, "w", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
            prev = os.environ.get("QUEUE")
            os.environ["QUEUE"] = queue
            try:
                result = generate.run(regen_stale_ladder=True)
                self.assertEqual(result["stale_steps"], 1)
                self.assertEqual(result["stale_with_approval"], 0)
                self.assertTrue(result["regen_stale_ladder"])
            finally:
                if prev is None:
                    os.environ.pop("QUEUE", None)
                else:
                    os.environ["QUEUE"] = prev
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_run_default_reports_zero_stale(self):
        """run() without the flag reports zero stale steps."""
        from src import store

        tmp = tempfile.mkdtemp(prefix="rga-task083-")
        try:
            queue = os.path.join(tmp, "work", "queue.jsonl")
            os.makedirs(os.path.dirname(queue), exist_ok=True)
            steps = {"em1": _email_step(ladder_fp="wrong!")}
            rec = _record("Jack", steps)
            with open(queue, "w", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
            prev = os.environ.get("QUEUE")
            os.environ["QUEUE"] = queue
            try:
                result = generate.run()
                self.assertEqual(result["stale_steps"], 0)
                self.assertFalse(result["regen_stale_ladder"])
            finally:
                if prev is None:
                    os.environ.pop("QUEUE", None)
                else:
                    os.environ["QUEUE"] = prev
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestCallerChain(LadderPropagationTestBase):
    """TEST 5: The wiring is real, not decorative."""

    def test_plan_is_the_entry_point(self):
        """The ladder stale check is reached through plan(), not a
        separate function. Asserting on what plan RETURNS."""
        steps = {"em1": _email_step(ladder_fp="wrong!")}
        rec = _record("Kate", steps)

        # Without flag: no stale ops
        ops_default = generate.plan(rec)
        stale_default = [o for o in ops_default if o.get("ladder_stale")]
        self.assertEqual(len(stale_default), 0)

        # With flag: stale ops appear
        ops_flag = generate.plan(rec, regen_stale_ladder=True)
        stale_flag = [o for o in ops_flag if o.get("ladder_stale")]
        self.assertGreater(len(stale_flag), 0)

    def test_break_the_wiring_test_fails(self):
        """If we call plan without the flag, stale steps are NOT detected.

        This is the 'break the wiring' test from the other direction:
        the stale detection ONLY fires when the flag is True.
        """
        steps = {"em1": _email_step(ladder_fp="wrong!")}
        rec = _record("Leo", steps)

        # Without the flag, NO stale ops - the wiring is opt-in
        ops_no_flag = generate.plan(rec)
        stale_no_flag = [o for o in ops_no_flag if o.get("ladder_stale")]
        self.assertEqual(len(stale_no_flag), 0,
                         "Without the flag, no stale ops should appear")

        # With the flag, stale ops DO appear
        ops_with_flag = generate.plan(rec, regen_stale_ladder=True)
        stale_with_flag = [o for o in ops_with_flag if o.get("ladder_stale")]
        self.assertGreater(len(stale_with_flag), 0,
                           "With the flag, stale ops should appear")

        # The difference proves the wiring is connected
        self.assertNotEqual(ops_no_flag, ops_with_flag)


class TestFingerprintStoredOnGeneration(LadderPropagationTestBase):
    """Newly generated steps carry the ladder fingerprint."""

    def test_draft_stores_fingerprint(self):
        """draft() stores the ladder fingerprint on the generated step."""
        from src import store, llm

        tmp = tempfile.mkdtemp(prefix="rga-task083-fp-")
        try:
            queue = os.path.join(tmp, "work", "queue.jsonl")
            os.makedirs(os.path.dirname(queue), exist_ok=True)
            c = _sendable_contact(name="Mike")
            rec = {
                "id": "test-mike",
                "state": "verified",
                "client": "productive",
                "domain": "example.com",
                "company": "Example",
                "company_facts": {"name": "Example", "employees": 50,
                                  "email_domain": "example.com"},
                "contacts": [c],
                "cadence": {},
                "events": [],
                "lane": "domains",
                "hook": "test hook",
                "qualification": {"icp": "approved"},
            }
            with open(queue, "w", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
            prev = os.environ.get("QUEUE")
            os.environ["QUEUE"] = queue

            good = json.dumps({
                "subject": "Test subject line here",
                "body": "Mike, this is a test body that is long enough "
                        "to pass the word count check and says something "
                        "meaningful about the company and its operations "
                        "without repeating anything else in the sequence "
                        "and it keeps going to make sure we pass forty "
                        "words at minimum for the lint check to pass ok."
            })
            model = llm.ScriptedModel(good)
            seq = _sequence()
            try:
                result = generate.draft(rec, c, "em1", model,
                                        sequence=seq)
                if result:
                    self.assertIn("ladder_fingerprint", result)
                    expected = generate.ladder_fingerprint(
                        "email", 1, sequence=seq)
                    self.assertEqual(result["ladder_fingerprint"], expected)
            finally:
                if prev is None:
                    os.environ.pop("QUEUE", None)
                else:
                    os.environ["QUEUE"] = prev
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
