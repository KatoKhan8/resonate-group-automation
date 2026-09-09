"""Every mutation in the audit must still be able to fire.

`tools/mutation_audit.py` finds a line, replaces it, and checks a test goes
red. When the line moves - a refactor, a new parameter, a reflowed
continuation - the entry stops matching and the audit reports it as
`MISSED (the code moved)`. That is the right report, and it arrives fifty
minutes into a run that nobody starts on an ordinary day.

So the same question is asked here in about a second: does every anchor
still appear exactly once in the file it names?

This found a real one. Threading the campaign through `approve.sync_state`
reflowed the assignment the audit was anchored on, and the entry guarding
"latch the record state instead of deriving it" had been dead ever since -
reporting protection nobody was exercising, which is the failure the audit
exists to prevent, one level up.

It does not run the mutations. It only asserts they could.
"""
import ast
import io
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT = os.path.join(ROOT, "tools", "mutation_audit.py")


def entries():
    """(name, file, guard, removal, tests) for every mutation, read
    statically so importing the tool cannot run anything."""
    tree = ast.parse(io.open(AUDIT, encoding="utf-8").read())
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if getattr(node.targets[0], "id", "") != "MUTATIONS":
            continue
        for element in node.value.elts:
            yield tuple(ast.literal_eval(part) for part in element.elts)
        return
    raise AssertionError("mutation_audit.py has no MUTATIONS list")


class EveryAnchorStillMatches(unittest.TestCase):

    def setUp(self):
        self.rows = list(entries())
        self.sources = {}

    def source(self, path):
        if path not in self.sources:
            with io.open(os.path.join(ROOT, path), encoding="utf-8") as handle:
                self.sources[path] = handle.read()
        return self.sources[path]

    def test_there_are_mutations_to_check(self):
        """So the assertions below cannot pass over an empty list."""
        self.assertGreater(len(self.rows), 300)

    def test_every_guard_appears_exactly_once(self):
        missing, ambiguous = [], []
        for name, path, guard, _removal, _tests in self.rows:
            found = self.source(path).count(guard)
            if found == 0:
                missing.append(f"{name} ({path})")
            elif found > 1:
                ambiguous.append(f"{name} ({path}, {found} matches)")

        self.assertEqual(missing, [], "these mutations can no longer fire; "
                                      "the code moved under them")
        self.assertEqual(ambiguous, [], "these mutations would replace only "
                                        "the first of several matches")

    def test_every_removal_differs_from_the_guard(self):
        """A replacement identical to the original mutates nothing and
        would be reported as caught by whatever the tests already do."""
        same = [name for name, _p, guard, removal, _t in self.rows
                if guard == removal]
        self.assertEqual(same, [])

    def test_every_file_named_exists(self):
        for name, path, _g, _r, _t in self.rows:
            self.assertTrue(os.path.exists(os.path.join(ROOT, path)),
                            f"{name} names {path}, which does not exist")

    def test_every_test_module_named_exists(self):
        for name, _p, _g, _r, tests in self.rows:
            for module in tests.split():
                relative = module.replace(".", os.sep) + ".py"
                self.assertTrue(
                    os.path.exists(os.path.join(ROOT, relative)),
                    f"{name} names {module}, which does not exist")


if __name__ == "__main__":
    unittest.main()
