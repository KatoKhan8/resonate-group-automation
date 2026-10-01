#!/usr/bin/env python3
"""Every name `src/` reads off `personalization` has to exist on it.

WHY THIS EXISTS. Commit f7d4d5cd rewrote `src/personalization.py` into the
L1-L4 ladder and, in the same edit, deleted 343 lines carrying nineteen
public names WITHOUT touching a single caller. Eight of them were still read
from nineteen modules. Nothing caught it, because every caller reaches the
missing name through an attribute lookup that only fails when the line
actually runs: `channels.summarise` and `mx.apply_to_record` - the enrichment
path - both raised AttributeError on a real record, and the suite reported
3,067 errors.

THE LIST IS DERIVED, NOT TYPED. It is walked out of the AST of `src/` on
every run, so a caller added tomorrow is covered tomorrow and a caller
deleted stops being asserted. A hand-written list would have been written
from the same reading that missed the breakage in the first place.

This is a behavioural test, not a source-text one: it asserts that the
attribute RESOLVES on the imported module, and for a name used in call
position that what resolves is callable. It says nothing about what any of
them does - the other test files do that.
"""
import ast
import io
import os
import unittest

from src import personalization as pz

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "src")
MODULE = "personalization"


def _uses(root):
    """{attribute name: {(file, line), ...}} for every read off the module.

    Walks the AST rather than grepping, so a mention inside a docstring or a
    comment - which is how `enrich.py` and `eligibility.py` mention this
    module, and how a grep gets this question wrong - is invisible here.
    Called names are recorded separately so we can also assert callability.
    """
    reads, called = {}, set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in sorted(filenames):
            if not name.endswith(".py"):
                continue
            path = os.path.join(dirpath, name)
            with io.open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), path)

            aliases = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if (node.module or "").endswith(MODULE):
                        # `from .personalization import x` binds the name
                        # directly; it fails at import time, but it is still
                        # a real dependency on the attribute existing.
                        for a in node.names:
                            if a.name != "*":
                                reads.setdefault(a.name, set()).add((path, node.lineno))
                    else:
                        aliases |= {a.asname or a.name for a in node.names
                                    if a.name == MODULE}
                elif isinstance(node, ast.Import):
                    aliases |= {a.asname or a.name.split(".")[-1]
                                for a in node.names if a.name.endswith("." + MODULE)}
            if not aliases:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and \
                        isinstance(node.value, ast.Name) and \
                        node.value.id in aliases:
                    reads.setdefault(node.attr, set()).add((path, node.lineno))
                if isinstance(node, ast.Call) and \
                        isinstance(node.func, ast.Attribute) and \
                        isinstance(node.func.value, ast.Name) and \
                        node.func.value.id in aliases:
                    called.add(node.func.attr)
    return reads, called


class PersonalizationApiIsWhole(unittest.TestCase):

    def test_the_walk_finds_callers_at_all(self):
        """A scanner that finds nothing would pass every assertion below."""
        reads, called = _uses(SRC)
        self.assertGreaterEqual(len(reads), 8, reads)
        self.assertIn("selected_contacts", reads)
        self.assertIn("level_for", called)

    def test_every_name_src_reads_exists_on_the_module(self):
        reads, _ = _uses(SRC)
        missing = []
        for attr in sorted(reads):
            if not hasattr(pz, attr):
                where = ", ".join("%s:%s" % (os.path.relpath(p, SRC), n)
                                  for p, n in sorted(reads[attr]))
                missing.append("%s  <- %s" % (attr, where))
        self.assertEqual([], missing,
                         "src/ calls names personalization does not define:\n  "
                         + "\n  ".join(missing))

    def test_every_called_name_is_callable(self):
        """A restored constant where a function was is still a broken caller."""
        _, called = _uses(SRC)
        self.assertTrue(called)
        for attr in sorted(called):
            self.assertTrue(callable(getattr(pz, attr, None)),
                            "%s is called in src/ but is not callable" % attr)

    def test_both_surfaces_coexist(self):
        """The ladder and the research API are one module, not two eras of it.

        Named explicitly because the failure mode was restoring one by
        deleting the other, in both directions.
        """
        for name in ("level_for", "admitted_rows", "describe",
                     "LEVEL_ACCOUNT_FACT", "LEVEL_ACCOUNT_CONTEXT",
                     "LEVEL_PERSONA", "LEVEL_ICP"):
            self.assertTrue(hasattr(pz, name), name)
        for name in ("selected_contacts", "decide", "apply", "stored",
                     "settings", "plan", "gaps", "company_researched",
                     "person_researched"):
            self.assertTrue(callable(getattr(pz, name, None)), name)


if __name__ == "__main__":
    unittest.main()
