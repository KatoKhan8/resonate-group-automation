"""The problem register must not have duplicate issue IDs.

ISSUE-006, ISSUE-011, ISSUE-012 and ISSUE-016 were each taken twice
(2026-09-25 audit). The register's own rule is "numbers are not reused."
This test asserts that, so the next duplicate is caught by running the
suite rather than by noticing.

The checker lives in scripts/register_lint.py; this test drives it
through the standard unittest discovery path.
"""

import re
import unittest
from collections import Counter
from pathlib import Path

REGISTER_PATH = (
    Path(__file__).resolve().parent.parent
    / "docs"
    / "state"
    / "PROBLEM-REGISTER.md"
)

HEADING_RE = re.compile(r"^### ((?:ISSUE|REFUTED)-\d+)", re.MULTILINE)


class TestTheRegisterHasNoDuplicateIds(unittest.TestCase):
    def test_every_issue_id_is_unique(self):
        """Each ### ISSUE-xxx or ### REFUTED-xxx heading must be unique.

        A duplicate means two findings took the same number, which is the
        exact failure mode this test exists to catch. The register's own
        rule: 'Numbers are not reused.'
        """
        text = REGISTER_PATH.read_text(encoding="utf-8")
        ids = HEADING_RE.findall(text)
        self.assertGreater(len(ids), 0, "register has no issue headings")

        counts = Counter(ids)
        dupes = {id_: n for id_, n in counts.items() if n > 1}
        self.assertEqual(
            dupes,
            {},
            f"Duplicate issue IDs in {REGISTER_PATH.name}: "
            + ", ".join(f"{id_} ({n}x)" for id_, n in sorted(dupes.items())),
        )


if __name__ == "__main__":
    unittest.main()
