"""Per-provider spend ceilings, enforced before a paid call or decoration.

WHAT EACH TEST HERE IS FOR, AND WHAT MAKES IT MEAN ANYTHING

Every assertion below is on an EFFECT: the provider was not called, the
ledger holds this many credits, the refusal names this scope and this key. A
test that grepped for `per_run` in a source file would pass on a ceiling
wired to nothing, which is exactly the defect this file exists to remove -
`per_run` was declared, returned by `caps()`, printed in a preflight, and
enforced by nobody until today.

THE CONCURRENCY PAIR IS THE POINT.
`test_k_workers_cannot_collectively_cross_a_provider_per_run` runs eight real
threads through a rendezvous and asserts the ledger. Its control,
`test_the_same_eight_workers_DO_cross_it_when_they_only_check`, runs the same
eight threads through the check-then-call shape that was there before and
asserts that it CROSSES. The control is the red proof kept live rather than
claimed in a commit message: if reservation were removed the first test
fails, and if the race became impossible the second fails and the first stops
proving anything. Neither can quietly become vacuous.

At K=1 every one of these passes with no reservation at all. That is the
whole history: a real chunk stopped at 2,044 credits against a declared
ceiling of 2,000 on 2026-09-25 while every test passed, because the tests ran
at `--workers 1` and production runs at 8.

TWO CONFIGS, ON PURPOSE. `PROVIDERS_ONLY` is the operator's per-provider
decision with no client ceiling above it, so a provider ceiling can be tested
as itself. `AS_SHIPPED` is that decision under the client ceilings
`config/clients/productive.yaml` actually carries, and the class that uses it
exists to show that those client ceilings bind first and that the refusal
says so. Testing only the first would be testing a configuration that does
not exist.

REDACTION: the only client slug here is a test slug, the only provider names
are vendor names already in the tracked config, and no address, contact key
or company name appears.
"""
import json
import os
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import spendledger, store                            # noqa: E402

CLIENT = "ceiling-test-client"

# A day that is not today, so a seeded row counts towards `total` without
# also consuming `per_day`. Which scope a fixture consumes has to be chosen
# deliberately or a test asserting one ceiling is really asserting another.
EARLIER_DAY = "2026-09-01"

# THE OPERATOR'S FINAL 2026-09-25 DECISION: the per-provider ceilings ARE
# the caps, the client `total` is removed, and a client `per_day` of 200,000
# remains only as a tripwire against a runaway loop.
PROVIDER_DECISION = {
    "cheapverifier": {"total": 100_000, "per_day": 95_000, "per_run": 10_000},
    "deliverable": {"total": 500_000, "per_day": 95_000},
    "reoon": {"total": 500_000, "per_day": 95_000},
    # Deliberately uncapped in THIS ledger, and saying so. An absent key
    # would be refused; this is a decision.
    "contactout": {"total": spendledger.UNLIMITED},
    "apify": {"total": spendledger.UNLIMITED},
}
PROVIDERS_ONLY = {"budget": {"providers": PROVIDER_DECISION}}
AS_SHIPPED = {"budget": {"per_day": 200_000, "providers": PROVIDER_DECISION}}

# What `config/clients/productive.yaml` carried BEFORE the swap. Kept because
# a client-scoped ceiling is still a legal thing for a client file to declare
# and its refusal still has to name itself as the client's.
LEGACY_CLIENT_CAPPED = {"budget": {
    "per_day": 15_000, "per_run": 2_000, "total": 50_000,
    "providers": PROVIDER_DECISION}}

# Ground truth, measured from the ledger on 2026-09-25: (all-time, today).
GROUND_TRUTH = {"deliverable": (8262, 7194), "reoon": (8236, 7171),
                "contactout": (1562, 0), "apify": (447, 0),
                "blitz": (232, 0), "aiark": (70, 0)}


class Ledgered(unittest.TestCase):
    """A disposable ledger, a fresh run, and no holds carried between tests."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-ceiling-")
        self.addCleanup(store.use_directory(self.tmp))
        spendledger._HOLDS.clear()
        self.addCleanup(spendledger._HOLDS.clear)
        self.run_id = spendledger.new_run(f"test-{id(self)}")

    # ---------------------------------------------------------- fixtures

    def seed(self, provider, credits, day=EARLIER_DAY, run_id=False):
        """Put `credits` on the ledger as already committed.

        Written as a row rather than through `record()` so a fixture cannot
        be mistaken for the thing under test, and so the day and run it lands
        in are chosen rather than inherited.
        """
        row = {"at": store.now(), "day": day, "client": CLIENT,
               "provider": provider, "call": "seed",
               "expected_cost": int(credits),
               "run_id": self.run_id if run_id else "an-earlier-run"}
        os.makedirs(os.path.dirname(spendledger.path()), exist_ok=True)
        with open(spendledger.path(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")

    def seed_ground_truth(self):
        for provider, (all_time, today) in GROUND_TRUTH.items():
            if all_time - today:
                self.seed(provider, all_time - today)
            if today:
                self.seed(provider, today, day=spendledger.today())

    def ledger_total(self, provider=None, day=None):
        return spendledger.spent(CLIENT, provider=provider, day=day)

    def race(self, worker, k=8):
        """K real threads, released together. Not a loop."""
        gate = threading.Barrier(k)
        errors = []

        def run(i):
            try:
                gate.wait(timeout=10)
                worker(i)
            except Exception as exc:                          # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=run, args=(i,)) for i in range(k)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        self.assertEqual([], errors, f"a worker raised: {errors}")
        self.assertFalse([t for t in threads if t.is_alive()],
                         "a worker never finished")


# ================================================ 1. refused BEFORE the call

class TheProviderIsNotTouched(Ledgered):
    """A refusal after the call is a receipt, not a control."""

    def setUp(self):
        super().setUp()
        self.calls = []

    def paid_call(self, provider, cost, config=PROVIDERS_ONLY):
        """The shape every spend path must use: reserve, call, settle."""
        with spendledger.holding(CLIENT, config, cost, provider=provider,
                                 call="verify"):
            self.calls.append((provider, cost))
        return "answered"

    def test_a_provider_total_refuses_and_the_provider_is_never_called(self):
        self.seed("cheapverifier", 99_999)           # total ceiling 100,000

        with self.assertRaises(spendledger.BudgetExceeded) as caught:
            self.paid_call("cheapverifier", 2)

        self.assertEqual([], self.calls,
                         "the provider was called and refused afterwards")
        message = str(caught.exception)
        self.assertIn("PROVIDER CEILING", message)
        self.assertIn("cheapverifier", message)
        self.assertIn("total", message)
        self.assertIn("100000", message)

    def test_a_provider_per_day_refuses_and_the_provider_is_never_called(self):
        self.seed("deliverable", 94_999, day=spendledger.today())

        with self.assertRaises(spendledger.BudgetExceeded) as caught:
            self.paid_call("deliverable", 2)

        self.assertEqual([], self.calls)
        message = str(caught.exception)
        self.assertIn("PROVIDER CEILING", message)
        self.assertIn("deliverable", message)
        self.assertIn("per_day", message)
        self.assertIn("95000", message)

    def test_a_provider_per_run_refuses_and_the_provider_is_never_called(self):
        self.seed("cheapverifier", 9_999, day=spendledger.today(),
                  run_id=True)                       # per_run ceiling 10,000

        with self.assertRaises(spendledger.BudgetExceeded) as caught:
            self.paid_call("cheapverifier", 2)

        self.assertEqual([], self.calls)
        message = str(caught.exception)
        self.assertIn("PROVIDER CEILING", message)
        self.assertIn("cheapverifier", message)
        self.assertIn("per_run", message)
        self.assertIn("10000", message)

    def test_an_earlier_runs_spend_does_not_consume_this_runs_per_run(self):
        """The control on the test above: `per_run` must be PER RUN.

        Without this, that assertion would pass just as well on a ceiling
        that counted everything, and `per_run` would quietly be a second
        `total` - which is the opposite of what it is for.
        """
        self.seed("cheapverifier", 9_999, day=spendledger.today(),
                  run_id=False)                      # a DIFFERENT run

        self.assertEqual("answered", self.paid_call("cheapverifier", 2))
        self.assertEqual([("cheapverifier", 2)], self.calls)

    def test_the_refusal_names_the_key_a_person_would_change(self):
        """"Budget exceeded" with no scope is how the wrong number is raised."""
        self.seed("reoon", 499_999)

        with self.assertRaises(spendledger.BudgetExceeded) as caught:
            self.paid_call("reoon", 5)

        self.assertIn("budget.providers.reoon.total", str(caught.exception),
                      "the refusal does not say which key to change")

    def test_a_call_inside_every_provider_ceiling_is_made(self):
        """The control on the whole class. Without it, everything above
        passes on a `check` that refuses unconditionally."""
        self.seed("cheapverifier", 50_000)

        self.assertEqual("answered", self.paid_call("cheapverifier", 100))
        self.assertEqual([("cheapverifier", 100)], self.calls)
        self.assertEqual(50_100, self.ledger_total(provider="cheapverifier"))


# =========================================== 2. the client ceiling binds first

class TheClientCeilingBindsFirstAndSaysSo(Ledgered):
    """A client ceiling outranks every provider ceiling beneath it.

    This was the thing that would have silently defeated the lane: provider
    ceilings of 100,000 and 500,000 mean nothing while a client `total` of
    50,000 sits above them, and a refusal reading "budget exceeded" sends
    somebody to raise the provider ceiling that was never the problem. The
    operator's answer on 2026-09-25 was to REMOVE the client `total` - see
    `TheSwapIsAtomic` below - but the interaction is still real for any
    client file that declares one, so it stays pinned here.
    """

    def test_the_measured_ledger_is_the_numbers_the_operator_was_given(self):
        self.seed_ground_truth()
        self.assertEqual(18_809, self.ledger_total())
        self.assertEqual(14_365, self.ledger_total(day=spendledger.today()))

    def test_a_client_total_refuses_while_every_provider_ceiling_is_fine(self):
        self.seed("deliverable", 49_000)             # client total is 50,000

        with self.assertRaises(spendledger.BudgetExceeded) as caught:
            spendledger.check(CLIENT, LEGACY_CLIENT_CAPPED, 2_000,
                              provider="deliverable")

        message = str(caught.exception)
        self.assertIn("CLIENT CEILING", message)
        self.assertIn("NOT a provider ceiling", message)
        self.assertIn("50000", message)
        self.assertIn("budget.total", message)
        # And the same call under the provider ceilings alone is allowed, so
        # the refusal above really is the client's and not deliverable's.
        self.assertTrue(spendledger.check(CLIENT, PROVIDERS_ONLY, 2_000,
                                          provider="deliverable"))

    def test_the_old_client_per_day_left_635_credits_of_the_measured_15000(self):
        """The ground truth, as a ceiling rather than as a number in a doc.

        14,365 of 15,000 were committed today when the operator was asked.
        This is what the estate would have been able to buy under the old
        client `per_day`, and it is why 15,000 could not stand over three
        provider ceilings of 95,000.
        """
        self.seed_ground_truth()

        self.assertTrue(spendledger.check(CLIENT, LEGACY_CLIENT_CAPPED, 635,
                                          provider="deliverable"))
        with self.assertRaises(spendledger.BudgetExceeded) as caught:
            spendledger.check(CLIENT, LEGACY_CLIENT_CAPPED, 636,
                              provider="deliverable")

        message = str(caught.exception)
        self.assertIn("CLIENT CEILING", message)
        self.assertIn("per_day", message)
        self.assertIn("15000", message)

    def test_the_old_client_per_run_contradicted_cheapverifiers_required_one(self):
        """Not a headroom problem - a direct contradiction, now removed.

        The operator requires CheapVerifier `per_run` 10,000. The client
        `per_run` was 2,000, so a 10,000-credit CheapVerifier run would have
        been refused at 2,001 by a CLIENT ceiling. This pins that the
        refusal says so rather than reading as a CheapVerifier problem, and
        `test_the_shipped_config_carries_no_client_per_run` below pins that
        the contradiction is gone from the file that ships.
        """
        with self.assertRaises(spendledger.BudgetExceeded) as caught:
            spendledger.check(CLIENT, LEGACY_CLIENT_CAPPED, 2_001,
                              provider="cheapverifier")

        message = str(caught.exception)
        self.assertIn("CLIENT CEILING", message)
        self.assertIn("per_run", message)
        self.assertIn("2000", message)
        self.assertIn("budget.per_run", message)
        # The same 2,001 credits are well inside CheapVerifier's own 10,000.
        self.assertTrue(spendledger.check(CLIENT, PROVIDERS_ONLY, 2_001,
                                          provider="cheapverifier"))

    def test_the_sanity_per_day_is_a_tripwire_and_still_refuses(self):
        """200,000 a day is not a budget. It is still a ceiling."""
        self.seed("deliverable", 199_000, day=spendledger.today())

        with self.assertRaises(spendledger.BudgetExceeded) as caught:
            spendledger.check(CLIENT, AS_SHIPPED, 2_000, provider="reoon")

        message = str(caught.exception)
        self.assertIn("CLIENT CEILING", message)
        self.assertIn("200000", message)

    def test_a_call_inside_every_ceiling_client_and_provider_is_allowed(self):
        self.seed_ground_truth()
        self.assertTrue(
            spendledger.check(CLIENT, AS_SHIPPED, 300, provider="cheapverifier"))


# ================================== 2b. the swap, and the state between them

class TheSwapIsAtomic(Ledgered):
    """Client `total` removed AND per-provider totals enforced, together.

    Until 2026-09-25 the client `total` of 50,000 was the ONLY lifetime cap
    this estate had. Removing it one commit before the per-provider totals
    are enforced leaves the account bounded by nothing, and the 200,000/day
    tripwire cannot see a runaway that happens inside a single day.

    So the intermediate state is REFUSED rather than permitted: a config
    carrying neither a client `total` nor a `total` for the provider being
    called raises, loudly, instead of reading `None` as unlimited. A missing
    cap must never parse as an unlimited one.
    """

    def test_a_config_with_no_lifetime_ceiling_anywhere_refuses_the_call(self):
        config = {"budget": {"per_day": 200_000}}    # the intermediate state

        with self.assertRaises(spendledger.MissingCeiling) as caught:
            spendledger.check(CLIENT, config, 1, provider="deliverable")

        message = str(caught.exception)
        self.assertIn("no lifetime ceiling", message)
        self.assertIn("deliverable", message)
        self.assertIn("budget.providers.deliverable.total", message)

    def test_a_provider_nobody_declared_is_refused_not_unbounded(self):
        """The half-done swap: three providers declared, a fourth forgotten."""
        with self.assertRaises(spendledger.MissingCeiling) as caught:
            spendledger.check(CLIENT, PROVIDERS_ONLY, 1, provider="blitz")

        self.assertIn("blitz", str(caught.exception))

    def test_unlimited_written_down_is_a_decision_and_is_allowed(self):
        """The control. An operator CAN say a provider is uncapped; what is
        refused is a ceiling nobody wrote either way."""
        self.assertTrue(spendledger.check(CLIENT, PROVIDERS_ONLY, 50_000,
                                          provider="contactout"))
        self.assertIsNone(
            spendledger.provider_caps(PROVIDERS_ONLY, "contactout")["total"])
        self.assertTrue(spendledger.declares(PROVIDERS_ONLY, "contactout"))

    def test_an_absent_key_and_an_explicit_unlimited_do_not_look_alike(self):
        """Both read `None` as a limit, and that is correct - neither bounds
        anything. They must differ in whether anybody DECIDED it."""
        absent = {"budget": {"providers": {"deliverable": {"per_day": 95_000}}}}

        self.assertIsNone(spendledger.provider_caps(absent, "deliverable")["total"])
        self.assertFalse(spendledger.declares(absent, "deliverable", "total"))
        self.assertTrue(spendledger.declares(PROVIDERS_ONLY, "contactout", "total"))

    def test_a_client_total_still_covers_a_provider_that_declares_none(self):
        """The pre-swap arrangement stays legal: one lifetime cap is enough,
        and which one it is is the operator's choice."""
        config = {"budget": {"total": 50_000,
                             "providers": {"deliverable": {"per_day": 95_000}}}}
        self.assertTrue(spendledger.check(CLIENT, config, 1,
                                          provider="deliverable"))

    def test_a_client_that_declares_no_budget_at_all_is_a_SEPARATE_gap(self):
        """Pinned as it is, so nobody reads the guard above as wider.

        A client file with no `budget` block is the older condition "this
        client declared no ceilings" - `caps()` reports every scope as
        UNLIMITED and always has. This lane did not widen that and does not
        close it: refusing every client that never declared a budget is a
        policy decision, not a side effect of adding per-provider ceilings.
        `config/clients/demo.yaml` and the ContactOut example are both in
        this state. If that changes, this test is the one that says so.
        """
        self.assertTrue(spendledger.check(CLIENT, {}, 1_000_000,
                                          provider="deliverable"))
        self.assertEqual([None] * 4,
                         list(spendledger.caps({}).values()))

    def test_a_free_call_is_not_refused_for_want_of_a_ceiling(self):
        """`people-count` costs nothing. A planning step must not be stopped
        by a budget question that does not apply to it."""
        self.assertTrue(spendledger.check(CLIENT, {"budget": {}}, 0,
                                          provider="deliverable"))

    def test_a_real_crossing_is_still_named_by_its_own_scope(self):
        """The ordering control: `MissingCeiling` is checked LAST.

        A refusal reading "no lifetime ceiling" when the true answer is
        "per_day is exhausted" would send somebody to edit the wrong key.
        """
        config = {"budget": {"providers": {"deliverable": {"per_day": 10}}}}
        self.seed("deliverable", 10, day=spendledger.today())

        with self.assertRaises(spendledger.BudgetExceeded) as caught:
            spendledger.check(CLIENT, config, 1, provider="deliverable")

        self.assertIn("per_day", str(caught.exception))
        self.assertNotIsInstance(caught.exception, spendledger.MissingCeiling)

    def test_missing_ceiling_is_refused_by_every_caller_that_already_exists(self):
        """`MissingCeiling` subclasses `BudgetExceeded` so an estate that
        loses its lifetime cap STOPS, rather than meeting a new exception
        type at the top of a stack trace mid-batch."""
        self.assertTrue(issubclass(spendledger.MissingCeiling,
                                   spendledger.BudgetExceeded))

    # -------------------------------------------- the file that actually ships

    def shipped(self):
        from src import clients
        return clients.load("productive")

    def test_the_shipped_config_declares_no_client_total(self):
        self.assertFalse(spendledger.declares_client(self.shipped(), "total"))

    def test_the_shipped_config_carries_no_client_per_run(self):
        """It contradicted CheapVerifier's required 10,000 outright."""
        self.assertFalse(spendledger.declares_client(self.shipped(), "per_run"))

    def test_the_shipped_config_keeps_the_sanity_per_day_at_200000(self):
        self.assertEqual(200_000, spendledger.caps(self.shipped())["per_day"])

    def test_the_shipped_config_declares_the_operators_provider_ceilings(self):
        config = self.shipped()
        self.assertEqual({"total": 100_000, "per_day": 95_000, "per_run": 10_000},
                         spendledger.provider_caps(config, "cheapverifier"))
        for provider in ("deliverable", "reoon"):
            self.assertEqual(
                {"total": 500_000, "per_day": 95_000, "per_run": None},
                spendledger.provider_caps(config, provider))

    def test_the_shipped_config_leaves_no_declared_provider_without_a_total(self):
        """The swap landed whole: every provider the file names has a
        lifetime ceiling, a number or an explicit `unlimited`."""
        config = self.shipped()
        missing = [p for p in spendledger.provider_names(config)
                   if not spendledger.declares(config, p, "total")]
        self.assertEqual([], missing)

    def test_every_provider_the_ledger_has_ever_paid_is_declared(self):
        """A provider with spend history and no ceiling is the gap the
        refusal above would find in production rather than here.

        Uses the measured ground truth, which is the list of providers this
        estate has actually paid.
        """
        config = self.shipped()
        undeclared = [p for p in GROUND_TRUTH
                      if not spendledger.declares(config, p, "total")]
        self.assertEqual(["aiark", "blitz"], sorted(undeclared),
                         "the set of providers with spend and no declared "
                         "ceiling changed; every one of them is refused on "
                         "its next paid call until an operator declares it")


# ============================================ 3. K workers and one `per_run`

class ParallelWorkersCannotShareTheSameRoom(Ledgered):
    """Eight threads, one ceiling, and a rendezvous so it is not luck.

    The ledger is seeded to 38 against a ceiling of 40 and every worker asks
    for 2. Exactly one of the eight can have it. The sleep between claiming
    and settling is the provider call: it is the window the old
    check-then-record shape left open, and the control test drives the same
    eight threads through that window on purpose.
    """

    CEILING = 40
    COST = 2
    PROVIDER = "cheapverifier"
    # `total: unlimited` so this class tests `per_run` and only `per_run`: a
    # lifetime ceiling has to be DECLARED for any paid call to be allowed at
    # all, and an undeclared one would refuse here for the wrong reason.
    CONFIG = {"budget": {"providers": {"cheapverifier": {
        "per_run": CEILING, "total": spendledger.UNLIMITED}}}}

    def setUp(self):
        super().setUp()
        self.seed(self.PROVIDER, self.CEILING - self.COST,
                  day=spendledger.today(), run_id=True)

    def test_k_workers_cannot_collectively_cross_a_provider_per_run(self):
        refused = []

        def worker(i):
            try:
                hold = spendledger.reserve(CLIENT, self.CONFIG, self.COST,
                                           provider=self.PROVIDER,
                                           call="verify")
            except spendledger.BudgetExceeded:
                refused.append(i)
                return
            time.sleep(0.02)                         # the provider call
            spendledger.settle(hold, self.COST)

        self.race(worker, k=8)

        spent = self.ledger_total(provider=self.PROVIDER)
        self.assertLessEqual(
            spent, self.CEILING,
            f"eight workers crossed the per_run ceiling: {spent} credits "
            f"against {self.CEILING}. Each saw room only one could have, "
            f"which is the 2,044-against-2,000 bug.")
        self.assertEqual(self.CEILING, spent,
                         "the one call that fitted did not happen")
        self.assertEqual(7, len(refused), "more than one worker got through")

    def test_the_same_eight_workers_DO_cross_it_when_they_only_check(self):
        """THE RED PROOF, KEPT LIVE.

        This is the shape the code had before: check, call, record. Same
        eight threads, same rendezvous, same ceiling - and it must CROSS. If
        it stopped crossing, the race would be impossible here and the test
        above would be proving nothing.
        """
        def worker(_i):
            try:
                spendledger.check(CLIENT, self.CONFIG, self.COST,
                                  provider=self.PROVIDER)
            except spendledger.BudgetExceeded:
                return
            time.sleep(0.02)                         # the provider call
            spendledger.record(CLIENT, self.PROVIDER, "verify", self.COST,
                               run_id=self.run_id)

        self.race(worker, k=8)

        spent = self.ledger_total(provider=self.PROVIDER)
        self.assertGreater(
            spent, self.CEILING,
            "check-then-record did NOT overshoot, so this control proves "
            "nothing and the reservation test above proves nothing either")
        self.assertLessEqual(spent, self.CEILING - self.COST + 8 * self.COST,
                             "more was bought than eight workers could buy")
        # HOW FAR PAST IS NOT ASSERTED EXACTLY, and that is honest rather than
        # lazy: how many of the eight get through the window depends on how
        # the scheduler interleaves them, and measured here it is six or
        # seven of eight, not always all eight. Pinning a single number would
        # make this control flaky, and a flaky control gets deleted - taking
        # the proof that the test above means something with it. THAT it
        # crosses is the claim; by exactly how much is the scheduler's.

    def test_a_free_running_race_also_holds_the_ceiling(self):
        """No seeding, no rendezvous: eight workers buy until refused.

        Closer to a real pass than the deterministic case above, and it
        asserts the number the audit reads.
        """
        run = spendledger.new_run("free-running")
        # BOUNDED SO A REMOVED GUARD FAILS RATHER THAN HANGS. The ceiling
        # allows 20 calls in total across all eight workers; 50 EACH is far
        # past anything the ceiling can permit, so reaching the bound is
        # itself the bug. Without it, deleting the guard turns this test into
        # an infinite loop - and a suite that hangs gets killed rather than
        # read, which is a worse failure than a red line.
        #
        # MEASURED, NOT ANTICIPATED. The first version of this test had no
        # bound. Running it with the ceiling removed left eight non-daemon
        # threads spinning after the test method returned; `addCleanup` then
        # put `store` back, and the threads that were still buying wrote
        # FIVE ROWS OF FABRICATED SPEND into the worktree's real
        # `work/spend-ledger.jsonl` - the exact failure `record`'s own
        # comment describes, arriving by a route the write barrier cannot
        # see, because by then the writes were legitimate. Invented credits
        # exhaust a real ceiling. A test that spends money has to be able to
        # stop.
        attempts = 50

        def worker(_i):
            for _ in range(attempts):
                try:
                    hold = spendledger.reserve(CLIENT, self.CONFIG, self.COST,
                                               provider=self.PROVIDER,
                                               call="verify")
                except spendledger.BudgetExceeded:
                    return
                time.sleep(0.002)
                spendledger.settle(hold, self.COST)

        self.race(worker, k=8)

        spent = spendledger.spent(CLIENT, provider=self.PROVIDER, run_id=run)
        self.assertGreater(spent, 0, "the run bought nothing")
        self.assertLessEqual(spent, self.CEILING,
                             f"crossed the ceiling: {spent} of {self.CEILING}")

    def test_nothing_is_left_holding_credits_when_the_race_is_over(self):
        """A leaked hold refuses credits nobody is spending, for ever."""
        def worker(_i):
            try:
                hold = spendledger.reserve(CLIENT, self.CONFIG, self.COST,
                                           provider=self.PROVIDER)
            except spendledger.BudgetExceeded:
                return
            spendledger.settle(hold, self.COST)

        self.race(worker, k=8)

        self.assertEqual([], spendledger.outstanding())


# ==================================== 4. the bulk reservation, held not spent

class ABulkReservationIsCheckedBeforeTheUploadIsCommitted(Ledgered):
    """`/file/upload` answers `creditsReserved` and that is a HOLD.

    The vendor puts credits aside for a job it has not run. Ledgering that as
    spend would make our expected total disagree with the invoice; not
    counting it at all would let a reservation sail past the balance and halt
    a batch in the middle. So: no ledger row, and still refused.
    """

    # The account balance on its own, for the tests about the balance. The
    # per_run ceiling is a different question and has its own class.
    BALANCE_ONLY = {"budget": {"providers": {
        "cheapverifier": {"total": 100_000}}}}

    def setUp(self):
        super().setUp()
        self.committed_uploads = []

    def upload(self, rows, credits_reserved, config=PROVIDERS_ONLY):
        """The seam lane Q's `src/providers/cheapverifier.py` should call.

        The reservation is read from the `/file/upload` response and checked
        BEFORE the upload is committed. On refusal nothing is committed and
        the caller cancels the vendor-side reservation.
        """
        hold = spendledger.reserve_upload(CLIENT, config, "cheapverifier",
                                          credits_reserved)
        self.committed_uploads.append((rows, credits_reserved))
        return hold

    def test_a_reservation_larger_than_the_balance_refuses_the_upload(self):
        self.seed("cheapverifier", 95_000)           # 5,000 left of 100,000

        with self.assertRaises(spendledger.BudgetExceeded) as caught:
            self.upload(4_500, credits_reserved=9_000)

        self.assertEqual([], self.committed_uploads,
                         "the upload was committed against a reservation "
                         "the account cannot pay for")
        message = str(caught.exception)
        self.assertIn("cheapverifier", message)
        self.assertIn("total", message)

    def test_a_reservation_inside_the_balance_lets_the_upload_through(self):
        """The control. Otherwise the test above passes on a seam that
        refuses every upload."""
        self.seed("cheapverifier", 95_000)

        hold = self.upload(500, credits_reserved=1_000)

        self.assertEqual([(500, 1_000)], self.committed_uploads)
        self.assertEqual(1_000, hold.cost)

    def test_a_reservation_is_held_and_is_not_spend(self):
        """Held, not spent: no ledger row, and still counted against a ceiling."""
        before = self.ledger_total(provider="cheapverifier")

        hold = self.upload(2_500, credits_reserved=5_000)

        self.assertEqual(before, self.ledger_total(provider="cheapverifier"),
                         "a held reservation was ledgered as spend, which "
                         "makes our expected total disagree with the invoice")
        self.assertEqual(5_000,
                         spendledger.reserved(CLIENT, provider="cheapverifier"))
        self.assertEqual(5_000,
                         spendledger.committed(CLIENT, provider="cheapverifier"))
        self.assertFalse(hold.resolved)

    def test_the_hold_BITES_or_it_is_only_bookkeeping(self):
        self.seed("cheapverifier", 50_000)
        # Without the hold there is room for this call.
        self.assertTrue(spendledger.check(CLIENT, self.BALANCE_ONLY, 45_000,
                                          provider="cheapverifier"))

        self.upload(20_000, credits_reserved=40_000, config=self.BALANCE_ONLY)

        with self.assertRaises(spendledger.BudgetExceeded):
            spendledger.check(CLIENT, self.BALANCE_ONLY, 45_000,
                              provider="cheapverifier")

    def test_a_completed_job_settles_at_what_it_really_cost(self):
        """The reservation was an estimate; the ledger takes the real number."""
        hold = self.upload(2_500, credits_reserved=5_000)

        spendledger.settle(hold, 4_812)

        self.assertEqual(4_812, self.ledger_total(provider="cheapverifier"))
        self.assertEqual(0,
                         spendledger.reserved(CLIENT, provider="cheapverifier"))

    def test_a_cancelled_upload_releases_the_credits_and_buys_nothing(self):
        hold = self.upload(2_500, credits_reserved=5_000)

        spendledger.release(hold)

        self.assertEqual(0, self.ledger_total(provider="cheapverifier"))
        self.assertEqual(0,
                         spendledger.reserved(CLIENT, provider="cheapverifier"))


# ================================================= 5. the CRITICAL at 10,000

class TheCriticalFiresOnceAndIsVisible(Ledgered):
    """An alert repeated per call is an alert nobody reads."""

    def test_no_critical_while_the_balance_is_healthy(self):
        self.seed("cheapverifier", 50_000)           # 50,000 left
        self.assertEqual([], spendledger.alerts(CLIENT, PROVIDERS_ONLY))
        self.assertEqual([], spendledger.fire_alerts(CLIENT, PROVIDERS_ONLY))

    def test_the_critical_fires_at_ten_thousand_remaining(self):
        self.seed("cheapverifier", 90_000)           # exactly 10,000 left

        fired = spendledger.fire_alerts(CLIENT, PROVIDERS_ONLY)

        self.assertEqual(1, len(fired))
        self.assertEqual("CRITICAL", fired[0]["level"])
        self.assertEqual("cheapverifier", fired[0]["provider"])
        self.assertEqual(10_000, fired[0]["remaining"])
        self.assertIn("Top up", fired[0]["text"])

    def test_only_cheapverifier_has_a_balance_to_run_out_of(self):
        """The control on the threshold: 10,000 is not a magic number for
        every provider, it is CheapVerifier's account balance."""
        self.seed("deliverable", 495_000)            # 5,000 left of 500,000
        self.assertEqual([], spendledger.alerts(CLIENT, PROVIDERS_ONLY))

    def test_it_does_not_spam(self):
        self.seed("cheapverifier", 90_500)           # 9,500 left

        first = spendledger.fire_alerts(CLIENT, PROVIDERS_ONLY)
        again = [spendledger.fire_alerts(CLIENT, PROVIDERS_ONLY)
                 for _ in range(20)]

        self.assertEqual(1, len(first))
        self.assertEqual([[]] * 20, again,
                         "the CRITICAL fired more than once; an alert per "
                         "call is an alert nobody reads")

    def test_it_is_still_VISIBLE_after_it_has_fired(self):
        """Fired once is not the same as hidden. A standing CRITICAL stays in
        the progress block, which is where the operator is looking."""
        self.seed("cheapverifier", 92_000)           # 8,000 left
        spendledger.fire_alerts(CLIENT, PROVIDERS_ONLY)

        self.assertEqual(1, len(spendledger.alerts(CLIENT, PROVIDERS_ONLY)))
        self.assertIn("CRITICAL",
                      spendledger.progress_block(CLIENT, PROVIDERS_ONLY))

    def test_it_re_arms_after_a_top_up(self):
        """A one-shot that never re-arms protects exactly one top-up cycle."""
        self.seed("cheapverifier", 92_000)
        self.assertEqual(1, len(spendledger.fire_alerts(CLIENT, PROVIDERS_ONLY)))

        topped_up = {"budget": {"providers": dict(
            PROVIDER_DECISION,
            cheapverifier={"total": 200_000, "per_day": 95_000,
                           "per_run": 10_000})}}
        self.assertEqual([], spendledger.fire_alerts(CLIENT, topped_up))

        # And down again: the operator must be told a second time.
        self.assertEqual(1, len(spendledger.fire_alerts(CLIENT, PROVIDERS_ONLY)))

    def test_the_marker_is_durable_so_a_second_process_does_not_re_announce(self):
        self.seed("cheapverifier", 92_000)
        spendledger.fire_alerts(CLIENT, PROVIDERS_ONLY)

        self.assertTrue(os.path.exists(spendledger.alerts_path()))
        with open(spendledger.alerts_path(), encoding="utf-8") as fh:
            state = json.load(fh)
        self.assertEqual(1, len(state["fired"]))

    def test_a_held_reservation_counts_against_the_balance_the_alert_reads(self):
        """A 9,000-credit hold is 9,000 credits the account cannot spend
        twice, ledgered or not."""
        self.seed("cheapverifier", 82_000)
        spendledger.reserve_upload(CLIENT, PROVIDERS_ONLY, "cheapverifier",
                                   9_000)

        fired = spendledger.fire_alerts(CLIENT, PROVIDERS_ONLY)

        self.assertEqual(1, len(fired))
        self.assertEqual(9_000, fired[0]["remaining"])


# ========================================= 6. the per-provider PROGRESS block

class EveryProgressBlockCarriesTheBalance(Ledgered):
    """A progress line reporting rows done says how far the batch got and
    nothing about whether it can finish."""

    def test_every_declared_provider_appears_with_its_balance(self):
        self.seed("deliverable", 8_262)
        self.seed("reoon", 8_236)

        block = spendledger.progress_block(CLIENT, AS_SHIPPED)

        for provider in ("cheapverifier", "deliverable", "reoon"):
            self.assertIn(provider, block)
        self.assertIn("491738", block)               # 500,000 - 8,262
        self.assertIn("491764", block)               # 500,000 - 8,236
        self.assertIn("100000 of 100000", block)     # cheapverifier untouched

    def test_the_client_wide_line_is_there_too(self):
        """Because whichever ceiling binds has to be visible.

        Since the swap the client line carries no lifetime cap - the caps
        are the per-provider totals above it - and it SAYS `unlimited`
        rather than showing a number that is not there. The 200,000 sanity
        tripwire is the part of this line that can still stop a run.
        """
        self.seed("deliverable", 18_809, day=spendledger.today())

        block = spendledger.progress_block(CLIENT, AS_SHIPPED)
        line = [ln for ln in block.splitlines() if "CLIENT-WIDE" in ln][0]

        self.assertIn("left unlimited", line)
        self.assertIn("181191", line)                # 200,000 - 18,809

    def test_the_old_client_total_is_still_reported_when_one_is_declared(self):
        """The control. The client line is not hardcoded to `unlimited`."""
        self.seed("deliverable", 18_809)

        block = spendledger.progress_block(CLIENT, LEGACY_CLIENT_CAPPED)
        line = [ln for ln in block.splitlines() if "CLIENT-WIDE" in ln][0]

        self.assertIn("31191 of 50000", line)        # 50,000 - 18,809

    def test_credits_in_flight_are_shown_as_held_not_as_spent(self):
        spendledger.reserve_upload(CLIENT, PROVIDERS_ONLY, "cheapverifier",
                                   7_000)

        block = spendledger.progress_block(CLIENT, PROVIDERS_ONLY)

        self.assertIn("held by calls in flight", block)
        self.assertIn("93000", block)                # 100,000 - 7,000 held

    def test_an_undeclared_ceiling_says_unlimited_rather_than_a_number(self):
        """`None` is unlimited and must SAY so. Deliverable declares no
        `per_run`; printing 0, or a default nobody chose, would both lie."""
        block = spendledger.progress_block(CLIENT, AS_SHIPPED)
        line = [ln for ln in block.splitlines() if "deliverable" in ln][0]
        self.assertIn("run unlimited", line)

    def test_a_standing_critical_rides_along_in_the_block(self):
        self.seed("cheapverifier", 95_000)           # 5,000 left

        block = spendledger.progress_block(CLIENT, PROVIDERS_ONLY)

        self.assertIn("CRITICAL", block)
        self.assertIn("ACCOUNT BALANCE", block)


# ====================================== 7. the seam the rest of the tree uses

class TheSeamIsWiredIntoTheRealSpendPath(Ledgered):
    """Enforcement that lives only in a test file is decoration too."""

    def verify_one(self, charged=True):
        """Drive the real waterfall with the provider transport replaced.

        `src/verification.py` is what `scripts/stage_s5_verify.py` drives at
        `--workers 8`, so it is the path the money actually goes down.
        """
        from src import verification
        seen = {}

        def fake_call(provider, email):
            # ASKED WHILE THE CALL IS IN FLIGHT. This is the whole assertion:
            # at the moment the provider is being called, the credits must
            # already be claimed. Under check-then-record they are not - the
            # ledger learns about them afterwards, which is the window eight
            # workers walked through.
            seen["held"] = spendledger.reserved(CLIENT)
            seen["ledgered"] = spendledger.spent(CLIENT)
            return verification.result(provider, verification.S_VALID, email,
                                       safe_to_send=charged,
                                       charged=charged)

        real = verification.call
        verification.call = fake_call
        self.addCleanup(setattr, verification, "call", real)
        rec = {"id": "r-1", "client": CLIENT}
        # RFC 2606 reserved: nothing here resolves and nothing here can be
        # contacted, which is what tests/test_fixture_hygiene.py requires.
        verification.verify({"email": "nobody@alpha.test", "key": "k-1"},
                            dict(verification.DEFAULT_POLICY,
                                 required_confirmations=1),
                            live=True, rec=rec, config=PROVIDERS_ONLY)
        return seen

    def test_the_credits_are_HELD_while_the_provider_call_is_in_flight(self):
        """Reserve-then-call, not check-then-record, on the real path."""
        seen = self.verify_one()

        self.assertGreater(seen.get("held", 0), 0,
                           "the provider was called with nothing reserved: "
                           "every other worker still sees that room")
        self.assertEqual(0, seen.get("ledgered"),
                         "the call was ledgered before it answered")

    def test_the_hold_becomes_a_ledger_row_once_the_call_answers(self):
        self.verify_one()

        self.assertGreater(self.ledger_total(), 0, "nothing was ledgered")
        self.assertEqual(0, spendledger.reserved(CLIENT),
                         "the hold outlived the call it was taken for")

    def test_a_call_the_provider_did_not_charge_for_releases_its_hold(self):
        """`charged: False` is a call that cost nothing. It must not hold
        credits it did not spend, and must not be ledgered either."""
        self.verify_one(charged=False)

        self.assertEqual(0, spendledger.reserved(CLIENT))
        self.assertEqual(0, self.ledger_total())

    def test_a_raising_provider_call_does_not_leak_its_hold(self):
        """A leaked hold keeps refusing credits nobody is spending."""
        def boom():
            with spendledger.holding(CLIENT, PROVIDERS_ONLY, 500,
                                     provider="cheapverifier", call="verify"):
                raise RuntimeError("the provider raised")

        self.assertRaises(RuntimeError, boom)
        self.assertEqual(0, spendledger.reserved(CLIENT))
        self.assertEqual(0, self.ledger_total())

    def test_the_declared_per_run_is_enforced_by_the_ledger_now(self):
        """The LEAK `tests/test_the_second_client_runs_on_the_same_engine.py`
        pinned open, closed."""
        self.assertIn("per_run", spendledger.SCOPES)
        self.assertRaises(spendledger.BudgetExceeded, spendledger.check,
                          CLIENT, {"budget": {"per_run": 1}}, 1000)

    def test_every_ceiling_reads_the_ledger_through_load(self):
        """THE SEAM LANE S'S `LedgerNotCredible` PLUGS INTO. Owned by lane S.

        An agent's worktree has its own `work/`, which is gitignored and so
        starts EMPTY. Every per-provider `total` here is computed as
        declared-minus-spent, so an empty ledger reads as "nothing spent,
        the whole balance available" - in every worktree at once. That is
        the same shape as an empty expectation matching everything, and it
        would defeat these ceilings without crossing one.

        LANE S OWNS THE PREDICATE, THIS LANE OWNS THE SEAM. There must not
        be two credibility checks each assuming the other ran, so nothing
        here decides whether a ledger is credible. What this pins is that
        there is exactly ONE door to put that check behind: if `load()`
        refuses, no ceiling in this module can be computed without the
        refusal reaching the caller. A ceiling that read the file some other
        way would be a hole lane S's gate could never cover.
        """
        def refuse():
            raise spendledger.LedgerUnreadable("lane S's gate, standing in")

        real = spendledger.load
        spendledger.load = refuse
        self.addCleanup(setattr, spendledger, "load", real)

        for call in (
                lambda: spendledger.check(CLIENT, PROVIDERS_ONLY, 1,
                                          provider="deliverable"),
                lambda: spendledger.reserve(CLIENT, PROVIDERS_ONLY, 1,
                                            provider="deliverable"),
                lambda: spendledger.reserve_upload(CLIENT, PROVIDERS_ONLY,
                                                   "cheapverifier", 1),
                lambda: spendledger.balances(CLIENT, PROVIDERS_ONLY),
                lambda: spendledger.alerts(CLIENT, PROVIDERS_ONLY),
                lambda: spendledger.progress_block(CLIENT, PROVIDERS_ONLY),
        ):
            self.assertRaises(spendledger.LedgerUnreadable, call)

    def test_a_ledger_row_now_says_which_run_bought_it(self):
        """`per_run` could not be enforced from the ledger while every row
        said `run_id: null`."""
        row = spendledger.record(CLIENT, "cheapverifier", "verify", 2)
        self.assertEqual(self.run_id, row["run_id"])


if __name__ == "__main__":
    unittest.main()
