"""A GLM review call that carries no source reviews nothing, and costs a call.

THIS IS A REGRESSION TEST FOR A DEFECT THAT ALREADY FIRED, not a hypothetical.

`glm_review` builds each prompt as `question.format(name=..., source=...)`.
`str.format` silently ignores a keyword the template does not mention, so a
question template with no `{source}` placeholder produces a prompt containing
the question and no code at all. The call is made, the tokens are spent, and
the model answers about code it was never shown.

`ATTRIBUTION_QUESTION` was exactly that, and it ran live on 2026-09-21 against
`inbound._positively_not_ours` and `inbound.handle`. The receipt is in
`docs/GLM-REVIEW-ATTRIBUTION-2026-09-21.md`:

    'prompt_tokens': 312
    'prompt_tokens': 312

Two different functions, byte-identical prompts, because the prompt did not
depend on which function was under review. Every other target in that
directory varies with its function - 1823, 752, 2172, 1078, 400 - because the
source is in the prompt. The model said so itself in that document: "I cannot
construct a concrete drop without the body of `_positively_not_ours`".

So the guard is not "the template should have a placeholder". It is: THE
RENDERED PROMPT MUST CONTAIN THE FUNCTION'S SOURCE, checked against the
rendered text rather than against the template, because that is the thing the
model actually reads.
"""
import inspect
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts import glm_review                                   # noqa: E402


class EveryTargetShowsTheModelTheCode(unittest.TestCase):
    """Built from `_targets()` itself, so a target added later is covered."""

    def test_every_target_renders_a_prompt_holding_its_own_source(self):
        targets = glm_review._targets()
        self.assertTrue(targets, "no review targets at all")
        for target, (question, functions) in sorted(targets.items()):
            for name, fn in functions:
                with self.subTest(target=target, function=name):
                    prompt = glm_review.build_prompt(question, name, fn)
                    source = inspect.getsource(fn)
                    self.assertIn(
                        source, prompt,
                        f"{target}/{name}: the rendered prompt does not "
                        f"contain the function's source")

    def test_two_functions_in_one_target_do_not_render_the_same_prompt(self):
        """The 312/312 receipt, as a property.

        Identical prompts for different functions is the observable symptom,
        and it is worth asserting separately: a template could contain
        `{source}` and still be rendered with the wrong function's body by a
        future refactor of the loop.
        """
        for target, (question, functions) in sorted(
                glm_review._targets().items()):
            if len(functions) < 2:
                continue
            rendered = [glm_review.build_prompt(question, name, fn)
                        for name, fn in functions]
            with self.subTest(target=target):
                self.assertEqual(
                    len(set(rendered)), len(rendered),
                    f"{target}: two functions rendered the same prompt")


class ARenderedPromptWithoutSourceIsRefused(unittest.TestCase):

    def test_a_template_with_no_placeholder_refuses(self):
        def victim():
            return "a body the model must be shown"

        with self.assertRaises(glm_review.PromptCarriesNoSource) as caught:
            glm_review.build_prompt(
                "Review {name}. There is no placeholder here.",
                "victim", victim)
        self.assertIn("victim", str(caught.exception))

    def test_the_refusal_names_the_remedy_rather_than_only_the_fault(self):
        def victim():
            return 1

        with self.assertRaises(glm_review.PromptCarriesNoSource) as caught:
            glm_review.build_prompt("no placeholder", "victim", victim)
        self.assertIn("{source}", str(caught.exception))

    def test_a_template_that_does_carry_the_placeholder_is_built(self):
        def victim():
            return "shown"

        prompt = glm_review.build_prompt(
            "Review {name}:\n{source}\nEnd.", "victim", victim)
        self.assertIn(inspect.getsource(victim), prompt)
        self.assertIn("victim", prompt)

    def test_refusal_happens_before_any_call_is_made(self):
        """A dry run must surface this, or it is only found by paying for it.

        `build_prompt` is reached on the dry-run path too - `main` builds every
        prompt before it checks `--live` - so a broken template is a non-zero
        exit without a credential, without a network call and without a
        charge.
        """
        source = inspect.getsource(glm_review.main)
        built = source.index("build_prompt")
        live = source.index("args.live")
        self.assertLess(
            built, live,
            "prompts must be built (and so checked) before --live is consulted")


class TheOutputBudgetDefaultsTo16k(unittest.TestCase):
    """PROBLEM-REGISTER ISSUE-008.

    Both targets of the last review came back `finish_reason='length'` with an
    EMPTY completion. The adapter refused them rather than returning "", which
    is correct, and the cost is a wasted call either way.

    `glm-5.3` spends most of its output budget on REASONING tokens - the
    attribution run above burned 6,592 reasoning tokens of 7,266 completion -
    so the budget is not a limit on the answer, it is a limit on the thinking
    that precedes it. 6,000 was not enough for a real target twice.
    """

    def test_glm_review_asks_for_16k(self):
        self.assertEqual(glm_review.DEFAULT_MAX_TOKENS, 16000)

    def test_the_default_survives_argument_parsing(self):
        self.assertEqual(glm_review.parse_args([]).max_tokens, 16000)

    def test_the_budget_is_inside_the_adapter_ceiling(self):
        """Asking for more than the adapter allows is silently clamped."""
        from src.providers import glm
        self.assertLessEqual(glm_review.DEFAULT_MAX_TOKENS, glm.MAX_TOKENS_CAP)


class TheSafetyAuditHarnessHasTheSameGuard(unittest.TestCase):
    """The two harnesses are the same shape and share the same two defects.

    A guard that exists in one of two near-identical scripts is how the next
    review gets run with no source in it. `glm_audit_safety` has one question
    template rather than six, so it is less exposed - but it renders the same
    way and defaulted to the same 6,000.
    """

    def test_the_audit_harness_also_refuses_a_sourceless_prompt(self):
        from scripts import glm_audit_safety

        def victim():
            return 1

        with self.assertRaises(glm_audit_safety.PromptCarriesNoSource):
            glm_audit_safety.build_prompt("no placeholder", "victim", victim)

    def test_the_audit_harness_also_asks_for_16k(self):
        from scripts import glm_audit_safety
        self.assertEqual(glm_audit_safety.DEFAULT_MAX_TOKENS, 16000)


if __name__ == "__main__":
    unittest.main()
