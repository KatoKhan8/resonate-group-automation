"""A declared ceiling nothing enforces is not a ceiling, and a cohort scoped
by domain is not the cohort.

Two gaps, both opened wider by the operator's 2026-09-25 decision to raise
`per_day` from 5,000 to 15,000 credits.

THE CEILING. `spendledger.check` iterates `per_day` and `total`, then tests
`per_provider_per_day`. `per_run` is in `spendledger.SCOPES`, is returned by
`caps()`, and has no consumer anywhere on a spend path -
`tests/test_the_second_client_runs_on_the_same_engine.py` pins that as a known
LEAK. At `per_day` 5,000 a declared 2,000-per-run ceiling was nearly harmless.
At 15,000 it means one invocation may spend seven and a half times the limit
the client file states, and nothing in the system would say so. The runner
therefore holds ITSELF to the client's declared `per_run`.

THE COHORT. `eligible_domains` filters DOMAINS; the cohort's exclusions -
replied, bounced, in-sequence - are per PERSON. Measured 2026-09-25 against
the provider-confirmed US cold cohort: its S5-eligible domains carry 6,817
pending addresses of which only 6,019 are cohort members, so a domain-scoped
run buys 798 addresses the exclusions had already removed.

These assert on BEHAVIOUR, in the style of the sibling S5 test: they drive
`main()` with the verifier transport replaced and then ask what was actually
BOUGHT - the provider calls made and the spend-ledger rows written. A test
that grepped for the flag name would pass on a filter wired to nothing.
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

# RFC 2606 reserved: nothing here resolves and nothing here can be contacted,
# which is what tests/test_fixture_hygiene.py requires of a tracked file.
DOMAIN = "alpha.test"


class PerRunAndCohortTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(store.use_directory(self.tmp))
        os.makedirs(os.path.join(self.tmp, "stage"), exist_ok=True)
        os.makedirs(os.path.join(self.tmp, "Productive"), exist_ok=True)
        self.calls = []
        self.real_call = verification.call
        verification.call = self._fake_call
        self.addCleanup(setattr, verification, "call", self.real_call)

    def _fake_call(self, provider, email):
        self.calls.append((provider, email))
        return verification.result(provider, verification.S_VALID, email,
                                   safe_to_send=True)

    # ------------------------------------------------------------- fixtures

    def addresses(self, n):
        return [f"c{i:04d}@{DOMAIN}" for i in range(n)]

    def write_stage(self):
        path = os.path.join(self.tmp, "stage", s5.S3_DEFAULT)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"domain": DOMAIN, "verdict": "in",
                                 "email_channel": True,
                                 "mx": "known_allowed"}) + "\n")
        return path

    def write_source(self, addresses):
        with open(s5.source_path(), "w", encoding="utf-8", newline="") as fh:
            fh.write("First Name,Job Title,Company,Url,Work Email\n")
            for address in addresses:
                fh.write(f"Sam,Ops Lead,Acme,,{address}\n")

    def write_cohort(self, addresses, jsonl=True):
        path = os.path.join(self.tmp, "cohort.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            for address in addresses:
                fh.write(json.dumps({"email": address, "domain": DOMAIN})
                         + "\n" if jsonl else address + "\n")
        return path

    def run_s5(self, *argv, workers="1"):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = s5.main(["--workers", workers, *argv])
        self.assertEqual(0, code, out.getvalue())
        return out.getvalue()

    def bought(self):
        """The addresses money was actually spent on, from the ledger side."""
        return {email for _, email in self.calls}

    # ------------------------------------------------------- the cohort gate

    def test_an_address_outside_the_cohort_is_never_bought(self):
        everyone = self.addresses(6)
        cohort, excluded = everyone[:4], everyone[4:]
        self.write_stage()
        self.write_source(everyone)

        self.run_s5("--only", self.write_cohort(cohort))

        self.assertEqual(set(cohort), self.bought())
        for address in excluded:
            self.assertNotIn(address, self.bought(),
                             "an excluded address was bought anyway")

    def test_without_the_gate_the_same_run_buys_the_excluded_addresses(self):
        """The control that makes the test above mean something.

        If `--only` were wired to nothing, the assertion above would still
        need the run to buy exactly the cohort - so this pins that the run
        WOULD otherwise reach wider, and that the flag is what narrows it.
        """
        everyone = self.addresses(6)
        self.write_stage()
        self.write_source(everyone)

        self.run_s5()

        self.assertEqual(set(everyone), self.bought())

    def test_a_plain_address_list_scopes_the_run_too(self):
        everyone = self.addresses(4)
        self.write_stage()
        self.write_source(everyone)
        path = os.path.join(self.tmp, "cohort.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(everyone[:2]) + "\n")

        self.run_s5("--only", path)

        self.assertEqual(set(everyone[:2]), self.bought())

    # -------------------------------------------------------- the per_run cap

    def test_the_pass_halts_at_the_per_run_ceiling(self):
        """Two credits an address, so a ceiling of 6 must stop around three.

        The overshoot is bounded at one address, because the cap is tested
        after each answer - which is the only point the run knows what the
        address actually cost rather than what it was expected to cost.
        """
        self.write_stage()
        self.write_source(self.addresses(40))

        output = self.run_s5("--max-credits", "6")

        spent = spendledger.spent("productive", day=spendledger.today())
        self.assertGreaterEqual(spent, 6, output)
        self.assertLessEqual(spent, 8, f"overshot by more than one address: "
                                       f"{spent} credits\n{output}")
        self.assertIn("HALTED", output)

    def test_the_ceiling_is_not_crossed_at_production_concurrency(self):
        """The bug the single-worker tests could not see.

        `Executor.map` submits every task at once, so at K=8 the workers keep
        buying while the consumer walks results in order. With the cap tested
        only after each answer, a real chunk on 2026-09-25 stopped at 2,044
        credits against a ceiling of 2,000 - twenty-two addresses past it -
        while every test here passed, because they all ran at --workers 1.

        A ceiling that is enforced at one width and not at the width
        production runs at is not enforced. This asserts the ledger total,
        which is the number the audit reads, and it asserts it at K=8.
        """
        self.write_stage()
        self.write_source(self.addresses(400))

        self.run_s5("--max-credits", "40", workers="8")

        spent = spendledger.spent("productive", day=spendledger.today())
        self.assertGreater(spent, 0, "the run bought nothing")
        self.assertLessEqual(
            spent, 40,
            f"crossed the declared per_run ceiling: {spent} credits against "
            f"40. In-flight calls were not reserved before being made.")

    def test_the_halt_leaves_every_bought_address_in_the_journal(self):
        """Stopping must not lose an answer that was already paid for."""
        self.write_stage()
        self.write_source(self.addresses(40))

        self.run_s5("--max-credits", "6")

        with open(s5.journal_path(), encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
        answered = {r["email"] for r in rows if not r.get("stopped")}
        self.assertEqual(self.bought(), answered,
                         "an address was bought and not journalled")

    def test_the_run_can_be_resumed_and_never_re_buys_a_settled_address(self):
        self.write_stage()
        self.write_source(self.addresses(40))

        self.run_s5("--max-credits", "6")
        first = set(self.bought())
        self.calls.clear()
        self.run_s5("--max-credits", "6")

        self.assertTrue(self.bought(), "the resumed pass bought nothing")
        self.assertEqual(set(), first & self.bought(),
                         "the resumed pass re-bought a settled address")

    def test_the_default_ceiling_is_the_clients_declared_per_run(self):
        """Not a number chosen in the runner. If the client file says 2,000,
        that is the cap; if it said 500, the cap would be 500."""
        self.write_stage()
        self.write_source(self.addresses(2))

        output = self.run_s5()

        declared = spendledger.caps(s5.clients.load(s5.CLIENT))["per_run"]
        self.assertIsNotNone(declared, "productive declares no per_run")
        self.assertIn(f"per_run self-enforced at {declared}", output)

    def test_per_run_is_still_not_enforced_by_the_ledger_itself(self):
        """The gap this runner works around, pinned so its removal is noticed.

        If `spendledger.check` ever learns `per_run`, this fails and the
        runner's own cap can become a belt beside a brace rather than the
        only control there is.
        """
        config = {"budget": {"per_run": 1, "per_day": 10_000,
                             "total": 10_000}}
        self.assertIn("per_run", spendledger.SCOPES)
        spendledger.check("productive", config, 500)   # 500 > per_run of 1
