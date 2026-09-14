"""The wire that was missing, asserted so the documentation stays true.

For two missions `variants.apply_to_step` had no caller in `src/`, and this
file existed to fail the moment somebody connected it - so that
PRODUCT-GAPS §3d and COPY-EXPERIMENTS §10, which both said it had none,
could not quietly become wrong.

It fired. Both documents have been rewritten and this file now guards the
other direction: the wire exists, it is in the drafting path rather than
somewhere convenient, and nothing has grown a second one.

The behaviour of the wire is `tests/test_variant_cadence_end_to_end.py`.
This is only about its existence and its place.
"""
import ast
import io
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def engine_files():
    for base, _dirs, files in os.walk(os.path.join(ROOT, "src")):
        if "__pycache__" in base:
            continue
        for name in sorted(files):
            if name.endswith(".py") and name != "variants.py":
                yield os.path.join(base, name)


def read(path):
    with io.open(path, encoding="utf-8") as handle:
        return handle.read()


def calls_in(path):
    tree = ast.parse(read(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            yield node.func.attr


class TheSeamIsConnected(unittest.TestCase):

    def callers(self):
        return sorted([os.path.relpath(path, ROOT).replace("\\", "/")
                for path in engine_files()
                if "apply_to_step" in set(calls_in(path))])

    def test_the_drafting_path_calls_it(self):
        """`cadence.expand_step` is where a step's copy is decided, so it
        is where the wording experiment belongs. The factories also call it
        to resolve the variant's words for the provider payload (TASK-022)."""
        callers = self.callers()
        self.assertIn("src/cadence.py", callers)

    def test_the_factories_call_it_too(self):
        """TASK-022: the factories resolve variants and apply them to check
        the approval fingerprint. This is not a second assignment path -
        the factories read the recorded variant_id and apply it."""
        callers = self.callers()
        self.assertIn("src/bisonfactory.py", callers)
        self.assertIn("src/heyreachfactory.py", callers)

    def test_the_caller_set_is_exactly_these_three(self):
        """THE BOUND, restored 2026-09-14 on review.

        This file used to assert `len(callers) == 1`, with the reason: "Two
        callers would be two places a contact could be assigned, and the
        second one would not be sticky with the first." TASK-022 legitimately
        added two callers - the factories RESOLVE a recorded variant rather
        than assigning a new one - and replaced the count with two `assertIn`
        checks.

        That accommodated the change and removed the guard with it: `assertIn`
        passes for any caller set containing these, so a fourth caller, which
        might well be a second assignment path, would arrive unreviewed. The
        original test's purpose was never the number one - it was that every
        caller has been looked at.

        So the set is pinned exactly. A new caller fails here, and adding it
        to this list is the review.
        """
        self.assertEqual(
            self.callers(),
            ["src/bisonfactory.py", "src/cadence.py",
             "src/heyreachfactory.py"])

    def test_it_is_called_from_expand_step(self):
        """Named rather than inferred from the file: `cadence.py` is large
        and the placement is the whole point."""
        tree = ast.parse(read(os.path.join(ROOT, "src", "cadence.py")))
        holders = [fn.name for fn in ast.walk(tree)
                   if isinstance(fn, ast.FunctionDef)
                   and "apply_to_step" in set(
                       n.func.attr for n in ast.walk(fn)
                       if isinstance(n, ast.Call)
                       and isinstance(n.func, ast.Attribute))]
        self.assertEqual(holders, ["expand_step"])

    def test_the_documents_no_longer_claim_it_is_missing(self):
        """Both said the wire had no caller for two missions, and a
        document that is wrong is worse than one that is silent.

        Reading prose is the wrong way to test code and the only way to
        test a document, so this is deliberately narrow: the sentence that
        is now false, named exactly, rather than a search for words that
        happen to be nearby.
        """
        for name in ("PRODUCT-GAPS.md", "COPY-EXPERIMENTS.md"):
            text = " ".join(read(os.path.join(ROOT, name)).split())
            self.assertFalse("apply_to_step has no caller" in text,
                             f"{name} still says the wire is missing")
            # Named, not nearby. This used to forbid the bare phrase
            # "has no caller in `src/`" anywhere in either document, which
            # is the search-for-words-nearby that the docstring above
            # rejects - and it went red the moment PRODUCT-GAPS.md
            # recorded, truthfully, that `orchestrator.freeze`,
            # `agencydnc.add`, `senderidentity.set_active` and
            # `set_cadence_experiment` have no caller either. Those are
            # different subjects and every one of those sentences is
            # correct.
            #
            # The claim this test exists to catch is about the variant
            # seam, so it is bound to the seam's two names. A document
            # that says the wire is missing still fails; a document that
            # says something else is missing does not.
            self.assertFalse("expand_step has no caller" in text,
                             f"{name} still says the wire is missing")


class TheRecordingHalfIsConnected(unittest.TestCase):
    """The other half of the same gap, which was closed first and had
    nothing to record until now."""

    def test_a_step_carrying_a_variant_records_it(self):
        from src import events, push

        rec = {"id": "a1", "client": "demo", "cadence": {}, "events": [],
               "contacts": [{"key": "c1", "name": "A"}]}
        step = {"channel": "email", "day": 1, "variant_id": "v-b",
                "variant_style": "casual", "variant_version": 2}
        rec["cadence"]["c1"] = {"day1": dict(step)}
        push.mark_pushed(rec, "c1", "day1", "a1:c1:day1:email", sent=step)
        entry = next(e for e in rec["events"]
                     if e["type"] == events.PUSH_MARKED)
        self.assertEqual(entry["variant_id"], "v-b")


if __name__ == "__main__":
    unittest.main()
