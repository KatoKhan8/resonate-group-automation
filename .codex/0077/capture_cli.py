"""Capture `python -m src.spendledger` text output for two fixtures.

Pre-fix measurement for TASK 0077: what a person sees today when the number
is a floor, and the golden bytes the priced case must stay identical to.
`spendledger.load` is patched, so no ledger on disk is read.
"""
import contextlib
import io
import sys

from src import spendledger

DAY = spendledger.today()

ROW = {"client": "t", "provider": "glm", "call": "complete:glm-5.3",
       "day": DAY, "at": DAY + "T00:00:00Z", "unit": "microusd"}

PRICED = [dict(ROW, expected_cost=1000, run_id="r1"),
          dict(ROW, expected_cost=2000, run_id="r1")]
UNPRICED = [dict(ROW, expected_cost=1000, run_id="r1"),
            dict(ROW, expected_cost=2000, run_id="r1"),
            dict(ROW, expected_cost=0, run_id="r1", priced=False)]


def show(label, rows):
    spendledger.load = lambda: rows
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        spendledger.main([])
    print(f"=== {label} (day {DAY}) ===")
    print(buf.getvalue())
    print(f"=== end {label} ===")


show("PRICED", PRICED)
show("UNPRICED (one row priced: False)", UNPRICED)
