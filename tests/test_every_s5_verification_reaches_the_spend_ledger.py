"""S5 buys two credits an address. Every one of them has to reach the ledger.

`verification.verify` gates BOTH ledgers - `waterfall.record_step` per record
and `spendledger.record` per client - behind `if rec is not None`, and
`scripts/stage_s5_verify.py` called it with no `rec` at all. So the most
expensive stage in the funnel was the one stage the spend audit could not see:
~22,000 credits of verification with not one row against them. CLAUDE.md says
a provider call that skips the ledger is invisible to the audit and that an
audit reporting clean because it watched nothing is worse than none, and this
is the shape that produced one.

These tests assert on BEHAVIOUR rather than on the source text: they drive the
runner's own `main()` with the verifier transport replaced, count the calls it
makes, and compare that against the rows the ledger actually holds. A test
that grepped the script for `rec=rec` would pass on a typo'd keyword.

The verifier is replaced at `verification.call`, which is the one seam between
the policy walk and the network, so no test here can spend a credit.
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import spendledger, store, verification            # noqa: E402
from scripts import stage_s5_verify as s5                   # noqa: E402

# Reserved by RFC 2606: nothing here can resolve and nothing here can be
# contacted, which is what `tests/test_fixture_hygiene.py` requires of every
# address in a tracked file.
DOMAINS = ("alpha.test", "beta.test")


class S5LedgerTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(store.use_directory(self.tmp))
        os.makedirs(os.path.join(self.tmp, "stage"), exist_ok=True)
        os.makedirs(os.path.join(self.tmp, "Productive"), exist_ok=True)
        self.calls = []
        self.answers = {}
        self.real_call = verification.call
        verification.call = self._fake_call
        self.addCleanup(setattr, verification, "call", self.real_call)

    def _fake_call(self, provider, email):
        """Count the call, then answer however the test asked us to.

        `charged` is left at its default, so every one of these is a purchase
        the ledger owes a row for - which is the whole question.
        """
        self.calls.append((provider, email))
        status = self.answers.get(provider, verification.S_VALID)
        return verification.result(provider, status, email,
                                   safe_to_send=(status == verification.S_VALID))

    # ------------------------------------------------------------- fixtures

    def write_stage(self, domains=DOMAINS):
        path = os.path.join(self.tmp, "stage", s5.S3_DEFAULT)
        with open(path, "w", encoding="utf-8") as fh:
            for domain in domains:
                fh.write(json.dumps({"domain": domain, "verdict": "in",
                                     "email_channel": True,
                                     "mx": "known_allowed"}) + "\n")
        return path

    def write_source(self, addresses):
        path = s5.source_path()
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write("First Name,Job Title,Company,Url,Work Email\n")
            for address in addresses:
                fh.write(f"Sam,Ops Lead,Acme,,{address}\n")
        return path

    def run_s5(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = s5.main(["--workers", "1", *argv])
        self.assertEqual(0, code, out.getvalue())
        return out.getvalue()

    def journal(self):
        with open(s5.journal_path(), encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    # ---------------------------------------------------------------- tests

    def test_the_ledger_holds_one_row_for_every_provider_call(self):
        self.write_stage()
        self.write_source([f"a@{DOMAINS[0]}", f"b@{DOMAINS[1]}"])

        self.run_s5()

        rows = spendledger.load()
        self.assertTrue(self.calls, "the runner made no provider call at all")
        self.assertEqual(len(self.calls), len(rows),
                         f"{len(self.calls)} calls and {len(rows)} ledger rows")
        for row in rows:
            self.assertEqual("productive", row["client"])
            self.assertEqual(1, row["expected_cost"])
        self.assertEqual({p for p, _ in self.calls},
                         {row["provider"] for row in rows})

    def test_the_run_reports_the_credits_the_ledger_agrees_with(self):
        """Two independent counts of the same spend, and they have to match.

        The journal's per-address `credits` comes from the waterfall ledger on
        the record; the spend ledger is a separate file written per call. If
        the two disagree, a call went round one of them.
        """
        self.write_stage()
        self.write_source([f"a@{DOMAINS[0]}", f"b@{DOMAINS[1]}"])

        self.run_s5()

        self.assertEqual(sum(r["credits"] for r in self.journal()),
                         spendledger.spent("productive"))

    def test_a_repeated_address_in_the_source_is_bought_once(self):
        self.write_stage()
        self.write_source([f"a@{DOMAINS[0]}", f"a@{DOMAINS[0]}",
                           f"b@{DOMAINS[1]}"])

        self.run_s5()

        self.assertEqual(2, len({e for _, e in self.calls}))
        self.assertEqual(2, len(self.calls) // 2)
        self.assertEqual(2, len(self.journal()))

    def test_a_retryable_hold_is_asked_twice_and_then_parked(self):
        """The whole point of the park: a second pass, and no third.

        `reoon says valid but the primary is unknown` is the retryable shape
        that 45.5% of the clean 2026-09-24 arms landed on. Before this, every
        later pass bought it again for ever.
        """
        self.write_stage(DOMAINS[:1])
        self.write_source([f"a@{DOMAINS[0]}"])
        # The primary fails and the secondary says valid, which is exactly the
        # "primary is missing" hold `RETRYABLE` was written for. A transport
        # failure is still CHARGED - only a local refusal is not - so this is
        # a purchase that bought no verdict, which is what makes re-buying it
        # for ever expensive.
        self.answers = {"deliverable": verification.S_ERROR}

        self.run_s5()
        first = self.journal()
        self.assertEqual(1, len(first))
        self.assertTrue(any(flag in first[0]["reason"] for flag in s5.RETRYABLE),
                        first[0]["reason"])
        self.assertFalse(first[0].get("parked"))
        self.assertEqual(1, first[0]["attempt"])

        bought = len(self.calls)
        self.run_s5()                                   # the one retry
        second = self.journal()
        self.assertEqual(2, len(second))
        self.assertEqual(2, second[-1]["attempt"])
        self.assertTrue(second[-1]["parked"])
        self.assertIn("not bought again", second[-1]["parked_reason"])
        self.assertGreater(len(self.calls), bought, "the retry bought nothing")

        bought = len(self.calls)
        self.run_s5()                                   # and no third
        self.assertEqual(bought, len(self.calls),
                         "a parked address was bought again")
        self.assertEqual(2, len(self.journal()))

    def test_a_settled_verdict_is_never_re_bought(self):
        self.write_stage(DOMAINS[:1])
        self.write_source([f"a@{DOMAINS[0]}"])

        self.run_s5()
        bought = len(self.calls)
        self.run_s5()

        self.assertEqual(bought, len(self.calls))

    def test_a_ceiling_refusal_is_not_a_verdict_and_halts_the_run(self):
        """A refused address stays re-askable, and the pass stops asking.

        The ceiling is per client per day, so the address after a refusal is
        refused too. Writing those as verdicts would settle the backlog
        against a budget rather than against the providers - the same class of
        mistake as recording a throttled hold, and a more expensive one.
        """
        self.write_stage()
        self.write_source([f"a@{DOMAINS[0]}", f"b@{DOMAINS[1]}"])
        # A declared ceiling of zero: nothing may be bought at all.
        config = dict(__import__("src.clients", fromlist=["clients"])
                      .load("productive"))
        config["budget"] = {"per_day": 0}
        real_load = s5.clients.load
        s5.clients.load = lambda name: config
        self.addCleanup(setattr, s5.clients, "load", real_load)

        output = self.run_s5()

        self.assertEqual([], self.calls, "a call was made past the ceiling")
        self.assertEqual([], spendledger.load())
        self.assertIn("HALTED", output)
        rows = self.journal()
        # Bounded rather than exactly one: `Executor.map` submits every task
        # up front, so the halt stops what has not STARTED, and whatever is
        # already in flight still comes back refused. What must hold of all of
        # them is that not one is a verdict.
        self.assertTrue(rows)
        for row in rows:
            self.assertIn("durable budget", row["stopped"])
        # Un-settled and un-counted: the next pass asks them again.
        settled, attempts = s5.journal_state()
        self.assertEqual(set(), settled)
        self.assertEqual({}, attempts)


if __name__ == "__main__":
    unittest.main()
