"""TASK-360: no model slug may live outside the central policy.

The policy file (`config/model_policy.yaml`) is the ONLY place model
slugs are declared.  Provider adapters read their allowlists and
defaults from it through `src/modelrouter.py`.  A slug found as a
string literal anywhere in `src/` fails this test.

Three traps this test handles explicitly:

1. A slug in a comment or docstring is NOT a violation.  The test
   parses with `ast` and checks string literals, not raw lines.
   Docstrings (the first Expr/Constant in a module, class or function
   body) are excluded.

2. `tests/` legitimately names models in fixtures and assertions.
   The test scans `src/` only.

3. The policy file itself is where slugs live.  It is excluded by
   path, not by pattern.

## The guard must be seen to fail

A guard never seen to fail is not known to work.  `test_planted_violation`
writes a scratch module with a known slug, confirms the scan FAILS and
names the file and line, then deletes the scratch and confirms green.
All three runs are asserted.
"""
import ast
import os
import sys
import tempfile
import textwrap
import unittest

_SRC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "src")

_POLICY_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "config")


def _docstring_lines(source):
    """Return the set of line numbers that are docstrings.

    A docstring is the first statement in a module, class or function
    body, and it is an Expr node whose value is a string Constant.
    Comments are already absent from the AST.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    lines = set()

    def _mark_docstring(body):
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            node = body[0]
            for ln in range(node.lineno, (node.end_lineno or node.lineno) + 1):
                lines.add(ln)

    _mark_docstring(tree.body)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            _mark_docstring(node.body)
    return lines


def _scan(src_dir, slugs):
    """Walk `src_dir` for string literals that are known model slugs.

    Returns a list of (path, lineno, slug) hits.
    """
    hits = []
    for root, _dirs, files in os.walk(src_dir):
        for fn in sorted(files):
            if not fn.endswith(".py"):
                continue
            path = os.path.join(root, fn)
            with open(path, encoding="utf-8") as fh:
                source = fh.read()
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue
            doc_lines = _docstring_lines(source)
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Constant)
                        and isinstance(node.value, str)):
                    continue
                if node.value not in slugs:
                    continue
                if node.lineno in doc_lines:
                    continue
                hits.append((path, node.lineno, node.value))
    return hits


def _load_slugs():
    """Read the policy's slug set through the router."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from src import modelrouter
    modelrouter.reload()
    return modelrouter.all_slugs()


class TestNoModelSlugOutsidePolicy(unittest.TestCase):
    """The production scan: zero hits in a clean tree."""

    def test_no_slug_in_src(self):
        slugs = _load_slugs()
        self.assertTrue(slugs, "the policy has no slugs to check against")
        hits = _scan(_SRC_DIR, slugs)
        if hits:
            detail = "\n".join(
                f"  {path}:{lineno}: {slug!r}"
                for path, lineno, slug in hits)
            self.fail(
                f"model slug(s) found outside the policy:\n{detail}\n"
                f"All model slugs must live in config/model_policy.yaml "
                f"and be read through src/modelrouter.py.")

    def test_docstring_does_not_trip(self):
        """Acceptance 4: a slug in a docstring or comment is not a hit."""
        slugs = _load_slugs()
        sample = textwrap.dedent('''\
            """Module docstring mentioning glm-5.3 in passing."""

            def f():
                """This function used to use grok-4.6 but no more."""
                # claude-sonnet-4-20250514 is a comment, not a violation
                return 42
        ''')
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sample.py")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(sample)
            hits = _scan(tmp, slugs)
        self.assertEqual(hits, [],
                         f"docstring/comment slug tripped the scan: {hits}")

    def test_planted_violation_is_caught(self):
        """Acceptance 3: the guard is seen to fail.

        Plant a slug in a scratch module, confirm the scan FAILS and
        names the file and line, remove the plant, confirm green.
        """
        slugs = _load_slugs()
        plant_slug = "claude-sonnet-4-20250514"
        self.assertIn(plant_slug, slugs,
                      f"{plant_slug!r} is not in the policy slug set")

        with tempfile.TemporaryDirectory() as tmp:
            plant_path = os.path.join(tmp, "scratch.py")

            # --- plant present: scan must FAIL ---
            with open(plant_path, "w", encoding="utf-8") as fh:
                fh.write(f'MODEL = "{plant_slug}"\n')
            hits = _scan(tmp, slugs)
            self.assertTrue(hits, "scan did not catch the planted violation")
            found_paths = [h[0] for h in hits]
            found_linenos = [h[1] for h in hits]
            found_slugs = [h[2] for h in hits]
            self.assertIn(plant_path, found_paths,
                          "scan did not name the planted file")
            self.assertIn(1, found_linenos,
                          "scan did not name the planted line")
            self.assertIn(plant_slug, found_slugs,
                          "scan did not name the planted slug")

            # --- plant removed: scan must PASS ---
            os.remove(plant_path)
            hits_after = _scan(tmp, slugs)
            self.assertEqual(hits_after, [],
                             f"scan still reports hits after plant removed: "
                             f"{hits_after}")


if __name__ == "__main__":
    unittest.main()
