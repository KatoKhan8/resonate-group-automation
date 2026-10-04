"""TASK-934: step-scoped rewrite keeps clean siblings fixed.

Five tests, each named after the guard it verifies:

1. A failing step among clean siblings is rewritten and the siblings are
   BYTE-IDENTICAL afterwards.
2. A rewrite that makes a sibling fail is REFUSED and nothing is stored.
3. Bounded retries per step, then HELD with the exact reason.
4. The approval hash covers the final full sequence, not a step.
5. A sequence that never converges stores nothing.
"""
import json
import unittest

from src import (copystages, generate_campaign, lint, llm,
                 sequenceplan)


def _good_sequences():
    """A set of sequences that pass copylint."""
    return {
        "em1": "Your team runs on projects and the margin is invisible "
               "until the work is done. Productive shows it while the "
               "work is running.",
        "em2": "The overrun shows up in the weekly report, not in the "
               "daily standup. Productive surfaces it early.",
        "em3": "Most project tools track tasks. Productive tracks the "
               "money behind the tasks.",
        "em4": "A project that looks healthy can still burn its budget "
               "in a week. Productive catches it.",
        "em5": "If this sounds useful, I can show you a live view of "
               "a project's margin in under five minutes.",
        "connect": "Would like to connect about how Productive helps "
                   "agencies track project margin.",
        "msg1": "Thanks for connecting. Productive shows agencies "
                "their project margin in real time.",
        "msg2": "Most agencies lose margin on projects that look "
                "healthy on the surface.",
        "msg3": "Happy to share how other agencies use Productive "
                "to catch overruns early.",
    }


def _good_subjects():
    return {"A": "Your project margin, live",
            "B": "The overrun nobody sees coming",
            "C": "One last thought on margin"}


def _contact():
    return {
        "email": "rowan@harbourline.test",
        "first_name": "Rowan",
        "last_name": "Blake",
        "title": "Head of Delivery",
        "contact_key": "rowan-blake",
        "sender_name": "Jamie Chen",
        "linkedin": "https://linkedin.com/in/rowanblake",
    }


def _facts():
    return [
        {"text": "Harbourline is a digital agency with 40 staff",
         "source_url": "https://harbourline.test/about"},
        {"text": "They specialise in Shopify builds",
         "source_url": "https://harbourline.test/services"},
    ]


class _CountingModel:
    """A model that returns scripted answers and counts calls."""

    def __init__(self, answers=None):
        self._answers = list(answers or [])
        self.calls = 0

    @property
    def name(self):
        return "test-counting"

    def complete(self, prompt, temperature=0, client=None, config=None,
                 max_tokens=None):
        self.calls += 1
        if self._answers:
            return self._answers.pop(0)
        return "{}"


def _make_result(sequences=None, subjects=None):
    """A contact result shaped like `_process_contact` output."""
    seqs = sequences or _good_sequences()
    subjs = subjects or _good_subjects()
    return {
        "contact_key": "rowan-blake",
        "email": "rowan@harbourline.test",
        "first_name": "Rowan",
        "title": "Head of Delivery",
        "sequences": dict(seqs),
        "subjects": dict(subjs),
        "facts": _facts(),
        "hypothesis": {"hypothesis": "margin visibility"},
        "match": {"capability_key": "report_intelligence"},
        "qualification": "QUALIFIED_THIN",
        "held": None,
        "sequence_gate": {},
        "copylint": {},
        "hold_kind": None,
        "gate_attempts": 0,
        "gate_rejections": [],
        "writer_parse_refusals": [],
    }


class TestStepScopedRewriteKeepsSiblingsFixed(unittest.TestCase):
    """TEST 1: one failing step is rewritten, siblings are byte-identical."""

    def test_failing_step_rewritten_siblings_unchanged(self):
        # em3 has a dash, which the validate callback refuses.
        # The other steps are clean.
        result = _make_result()
        # Introduce a dash in em3 so the validate callback refuses it.
        result["sequences"]["em3"] = ("Most project tools track tasks "
                                      "- not deadlines. Productive tracks "
                                      "the money behind the tasks.")
        original_em1 = result["sequences"]["em1"]
        original_em2 = result["sequences"]["em2"]
        original_em4 = result["sequences"]["em4"]
        original_em5 = result["sequences"]["em5"]
        original_em3 = result["sequences"]["em3"]

        # The validate callback refuses em3 for a dash.
        def validate(res):
            body = res["sequences"].get("em3", "")
            if " - " in body or " \u2013 " in body:
                return ["em3: dash found"]
            return []

        # The step-scoped rewrite model returns a clean em3.
        rewrite_answer = json.dumps({"em3": "Most project tools track "
                                     "tasks. Productive tracks the money "
                                     "behind the tasks, not just the "
                                     "deadlines."})
        model = _CountingModel([rewrite_answer])

        ok = generate_campaign._rewrite_failing_steps(
            result, model, _contact(), "Harbourline", _facts(),
            "{}", "Report Intelligence", "Jamie Chen", None,
            "productive", validate, None, None, None)

        self.assertTrue(ok, "step-scoped rewrite should converge")
        # The siblings are BYTE-IDENTICAL.
        self.assertEqual(result["sequences"]["em1"], original_em1)
        self.assertEqual(result["sequences"]["em2"], original_em2)
        self.assertEqual(result["sequences"]["em4"], original_em4)
        self.assertEqual(result["sequences"]["em5"], original_em5)
        # em3 was rewritten (different from the original dash version).
        self.assertNotEqual(result["sequences"]["em3"], original_em3)


class TestRewriteThatBreaksSiblingIsRefused(unittest.TestCase):
    """TEST 2: a rewrite that makes a sibling fail is REFUSED."""

    def test_sibling_breakage_refuses_everything(self):
        result = _make_result()
        # em3 has a dash.
        result["sequences"]["em3"] = "Bad - draft with dash"

        # The rewrite for em3 is clean, but it causes em1 to fail.
        rewrite_answer = json.dumps({"em3": "Clean rewrite of em3"})

        attempt = [0]

        def validate_with_sibling_break(res):
            attempt[0] += 1
            failures = []
            em3 = res["sequences"].get("em3", "")
            if "Clean rewrite" in em3:
                # The rewrite succeeded but now em1 fails (simulated).
                failures.append("em1: repetition detected with em3")
            elif " - " in em3:
                failures.append("em3: dash found")
            return failures

        model = _CountingModel([rewrite_answer])

        ok = generate_campaign._rewrite_failing_steps(
            result, model, _contact(), "Harbourline", _facts(),
            "{}", "Report Intelligence", "Jamie Chen", None,
            "productive", validate_with_sibling_break, None, None, None)

        self.assertFalse(ok, "sibling breakage should refuse")
        self.assertEqual(result["hold_kind"], "copy_refused")
        self.assertEqual(result["sequences"], {})
        self.assertEqual(result["subjects"], {})
        # THE MUTATION CHECK: the hold message must name sibling breakage.
        self.assertIn("sibling", result["held"].lower(),
                      "hold message must name sibling breakage, got: %s"
                      % result["held"])


class TestBoundedRetriesThenHeld(unittest.TestCase):
    """TEST 3: bounded retries per step, then HELD with exact reason."""

    def test_exhausted_rewrites_hold_with_reason(self):
        result = _make_result()
        result["sequences"]["em3"] = "Bad - draft"

        def validate(res):
            body = res["sequences"].get("em3", "")
            if " - " in body or "Bad" in body:
                return ["em3: dash or bad content"]
            return []

        # Every rewrite answer still fails.
        bad_answers = [
            json.dumps({"em3": "Still - bad"}),
            json.dumps({"em3": "Also - bad"}),
            json.dumps({"em3": "Bad again"}),
        ]
        model = _CountingModel(bad_answers)

        ok = generate_campaign._rewrite_failing_steps(
            result, model, _contact(), "Harbourline", _facts(),
            "{}", "Report Intelligence", "Jamie Chen", None,
            "productive", validate, None, None, None)

        self.assertFalse(ok, "exhausted rewrites should not converge")
        self.assertEqual(result["hold_kind"], "copy_refused")
        self.assertEqual(result["sequences"], {})
        # The hold message names the step and the retry count.
        self.assertIn("em3", result["held"])
        self.assertIn(str(generate_campaign.MAX_STEP_REWRITES),
                      result["held"])

    def test_retries_are_bounded_not_unbounded(self):
        result = _make_result()
        result["sequences"]["em3"] = "Bad - draft"

        call_count = [0]

        def validate(res):
            call_count[0] += 1
            return ["em3: always fails"]

        # Provide more answers than the limit to prove the limit is enforced.
        answers = [json.dumps({"em3": "attempt %d" % i})
                   for i in range(20)]
        model = _CountingModel(answers)

        generate_campaign._rewrite_failing_steps(
            result, model, _contact(), "Harbourline", _facts(),
            "{}", "Report Intelligence", "Jamie Chen", None,
            "productive", validate, None, None, None)

        # The model should be called at most MAX_STEP_REWRITES times.
        self.assertLessEqual(model.calls,
                             generate_campaign.MAX_STEP_REWRITES)


class TestApprovalHashCoversFullSequence(unittest.TestCase):
    """TEST 4: the approval hash covers the final full sequence, not a step."""

    def test_hash_changes_when_any_step_changes(self):
        plan_a = sequenceplan.new(
            "productive",
            {"company": "Harbourline", "domain": "harbourline.test"},
            [{
                "contact_key": "rowan-blake",
                "email": "rowan@harbourline.test",
                "sequences": _good_sequences(),
                "subjects": _good_subjects(),
            }],
        )
        hash_a = sequenceplan.approval_hash(plan_a)

        # Change ONE step.
        plan_b = sequenceplan.new(
            "productive",
            {"company": "Harbourline", "domain": "harbourline.test"},
            [{
                "contact_key": "rowan-blake",
                "email": "rowan@harbourline.test",
                "sequences": {**_good_sequences(),
                              "em3": "completely different text"},
                "subjects": _good_subjects(),
            }],
        )
        hash_b = sequenceplan.approval_hash(plan_b)

        self.assertNotEqual(hash_a, hash_b,
                            "changing one step must change the hash")

    def test_hash_is_stable_for_same_sequence(self):
        plan = sequenceplan.new(
            "productive",
            {"company": "Harbourline", "domain": "harbourline.test"},
            [{
                "contact_key": "rowan-blake",
                "email": "rowan@harbourline.test",
                "sequences": _good_sequences(),
                "subjects": _good_subjects(),
            }],
        )
        self.assertEqual(sequenceplan.approval_hash(plan),
                         sequenceplan.approval_hash(plan))


class TestNonConvergingSequenceStoresNothing(unittest.TestCase):
    """TEST 5: a sequence that never converges stores nothing."""

    def test_never_converging_stores_nothing(self):
        result = _make_result()
        result["sequences"]["em3"] = "Bad - draft"

        def validate(res):
            return ["em3: always fails no matter what"]

        answers = [json.dumps({"em3": "attempt %d" % i})
                   for i in range(generate_campaign.MAX_STEP_REWRITES + 5)]
        model = _CountingModel(answers)

        ok = generate_campaign._rewrite_failing_steps(
            result, model, _contact(), "Harbourline", _facts(),
            "{}", "Report Intelligence", "Jamie Chen", None,
            "productive", validate, None, None, None)

        self.assertFalse(ok)
        self.assertEqual(result["sequences"], {},
                         "non-converging sequence stores nothing")
        self.assertEqual(result["subjects"], {},
                         "non-converging sequence stores no subjects")
        self.assertEqual(result["hold_kind"], "copy_refused")


class TestStepRewritePrompt(unittest.TestCase):
    """The step-scoped prompt shows siblings as fixed context."""

    def test_prompt_names_the_step_and_shows_siblings(self):
        prompt = copystages.step_rewrite_user(
            "em3", "email",
            _good_sequences(), _good_subjects(),
            _facts(), "Harbourline",
            {"name": "Rowan Blake", "title": "Head of Delivery"},
            "Jamie Chen", "{}", "Report Intelligence",
            "em3: dash found")

        self.assertIn("Rewriting ONE step: em3", prompt)
        self.assertIn("FIXED", prompt)
        self.assertIn("em1", prompt)
        self.assertIn("em2", prompt)
        # em3 is NOT shown as fixed (it is the one being rewritten).
        self.assertNotIn("### em3 (FIXED)", prompt)
        self.assertIn("dash found", prompt)

    def test_prompt_asks_for_one_key_only(self):
        prompt = copystages.step_rewrite_user(
            "msg1", "linkedin",
            _good_sequences(), _good_subjects(),
            _facts(), "Harbourline",
            {"name": "Rowan Blake", "title": "Head of Delivery"},
            "Jamie Chen", "{}", "Report Intelligence",
            "msg1: too short")

        self.assertIn('"msg1"', prompt)
        self.assertIn("Do NOT return the other steps", prompt)


class TestIdentifyFailingSteps(unittest.TestCase):
    """The step identifier parses failure sentences correctly."""

    def test_identifies_step_by_name_in_sentence(self):
        result = _make_result()
        failures = ["em3: dash found (' - ')"]
        failing = generate_campaign._identify_failing_steps(
            failures, result)
        self.assertIn("em3", failing)

    def test_unlocatable_failure_attributed_to_all(self):
        result = _make_result()
        failures = ["general quality issue"]
        failing = generate_campaign._identify_failing_steps(
            failures, result)
        # When the step cannot be identified, all steps are attributed.
        self.assertTrue(len(failing) > 1)


class TestStepChannel(unittest.TestCase):
    """The channel detector classifies step keys correctly."""

    def test_email_steps(self):
        self.assertEqual(generate_campaign._step_channel("em1"), "email")
        self.assertEqual(generate_campaign._step_channel("em5"), "email")
        self.assertEqual(generate_campaign._step_channel("ps_em1"), "email")

    def test_linkedin_steps(self):
        for key in generate_campaign.LINKEDIN_WRITER_KEYS:
            self.assertEqual(generate_campaign._step_channel(key),
                             "linkedin")


if __name__ == "__main__":
    unittest.main()
