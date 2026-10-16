#!/usr/bin/env python3
"""`python -m src.spendledger` must show the floor, not just the tripwire.

TASK 0077. `report()` has carried `expected_floor` (the numeric KNOWN part)
and `unpriced_rows` (how much is missing) since TASK 0073/0074, but the text
CLI never read them. Measured pre-fix, with one `priced: False` row among
three, this was the ENTIRE answer a person got:

    expected total   UNKNOWN TOTAL - a floor, not a total
    expected today   UNKNOWN TOTAL - a floor, not a total
      glm            UNKNOWN TOTAL - a floor, not a total

Right about the taint, silent about the two numbers a person needs next:
how big the known part is and how much is unaccounted for. This test pins
the repair: when `unpriced_rows` is non-zero the CLI prints an
`expected floor` line carrying both, in words that assume the reader has
never read a brief - "KNOWN PART ONLY ... the true total is HIGHER" - not a
flag a reader must know to look for.

0074's own property travels with it: a fully priced run is BYTE-IDENTICAL to
the pre-fix output (GOLDEN below, captured from the pre-fix bytes). A change
that shifts every existing line is a change nobody can review.

Paired mutants this file is built to separate (TASK 0077 C2):
  - the guard made ALWAYS TRUE (every run prints the floor line, priced
    runs included) is killed ONLY by `test_a_priced_run_is_byte_identical`
    - the priced bytes moved.
  - the guard made ALWAYS FALSE (the floor never reaches the screen again)
    is killed ONLY by `test_the_unpriced_run_names_the_floor_and_its_gap`
    - the line vanishes while every tripwire still prints.

Each kill-set is a different, non-empty, named single row; a mutant that
survives both is a reportable result, not a pass.
"""
import contextlib
import io
import unittest
from unittest import mock

from src import spendledger

DAY = spendledger.today()

ROW = {"client": "t", "provider": "glm", "call": "complete:glm-5.3",
       "day": DAY, "at": DAY + "T00:00:00Z", "unit": "microusd"}

PRICED = [dict(ROW, expected_cost=1000, run_id="r1"),
          dict(ROW, expected_cost=2000, run_id="r1")]

UNPRICED = [dict(ROW, expected_cost=1000, run_id="r1"),
            dict(ROW, expected_cost=2000, run_id="r1"),
            dict(ROW, expected_cost=0, run_id="r1", priced=False)]

# Captured verbatim from the PRE-FIX bytes with these PRICED rows (same
# day, config=None, no --client). The fix is guarded, so this must not move.
GOLDEN = (
    "expected total   3000\n"
    "expected today   3000\n"
    "  glm            3000\n"
    "\n"
    "ceilings\n"
    "  per_run                  UNLIMITED - none declared\n"
    "  per_day                  UNLIMITED - none declared\n"
    "  per_provider_per_day     UNLIMITED - none declared\n"
    "  total                    UNLIMITED - none declared\n"
)


def run_cli(rows):
    """`main([])` with the ledger replaced by `rows`; returns its stdout."""
    buf = io.StringIO()
    with mock.patch.object(spendledger, "load", return_value=rows), \
            contextlib.redirect_stdout(buf):
        spendledger.main([])
    return buf.getvalue()


class TheFloorReachesTheScreen(unittest.TestCase):

    def test_the_unpriced_run_names_the_floor_and_its_gap(self):
        """Born red against the pre-fix bytes: the CLI never printed these.

        The line must carry all three things a person needs - the known
        part's size, how many rows are missing from it, and the direction
        of the truth - without the reader knowing any field name.
        """
        out = run_cli(UNPRICED)
        self.assertIn("expected floor   3000 KNOWN PART ONLY", out)
        self.assertIn("1 unpriced ledger row(s) not counted", out)
        self.assertIn("the true total is HIGHER", out)

    def test_the_tripwires_still_print_alongside_the_floor(self):
        """The repair ADDS the known part; it must not soften 0074's
        tripwires, which are the reason a floor is never mistaken for a
        total in the first line a person reads."""
        out = run_cli(UNPRICED)
        self.assertIn("expected total   UNKNOWN TOTAL - a floor, not a total",
                      out)
        self.assertIn("  glm            UNKNOWN TOTAL - a floor, not a total",
                      out)


class APricedRunDoesNotMove(unittest.TestCase):
    """0074's own property: priced output is byte-identical to pre-fix."""

    def test_a_priced_run_is_byte_identical(self):
        self.assertEqual(run_cli(PRICED), GOLDEN)


if __name__ == "__main__":
    unittest.main()
