"""The phase-2 sandbox runner, with a positive control on every key check.

WHY EVERY ASSERTION HERE IS PAIRED
==================================
This repository has already shipped a harness that printed "0 failures" off
the back of five swallowed exceptions, and a suite baseline that was compared
by COUNT while the set underneath it changed. So the rule this file works to is
the operator's: **a zero that was never shown able to be non-zero is not a
result.**

Every check below therefore comes in two parts: the assertion, and a control
that deliberately breaks the thing being checked and proves THE SAME CHECKER
reports the problem. Where the control is in a separate test it is named
`..._control`, and its docstring names which assertion it guards.

WHAT THIS FILE DOES NOT DO
==========================
It does not run the 60-day simulation. That is `scripts/sandbox_run.py --mode
full`, it takes tens of minutes, and its output is the artefact. These tests
exercise the mechanisms the run depends on, plus two short end-to-end runs in
SUBPROCESSES - one killed mid-flight - because a kill cannot be tested in the
process doing the asserting.

    py -3 -m unittest tests.test_sandbox_phase1 tests.test_sandbox_run -v
"""
import copy
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from src import (accountpolicy, cadence, clients, eligibility, evidence,  # noqa: E402
                 lint, providers, replies, sandboxclock, sandboxharness,
                 store, verification)
from src.providers import bison                                   # noqa: E402

import sandbox_run                                               # noqa: E402

#: The COMMIT this work was forked from, not the branch name. `src/` must be
#: byte-identical to it: the whole premise is that the production flow was
#: driven, not changed.
#:
#: A SHA AND NOT A BRANCH, and that is this repository's own rule - "a
#: reference bound to something that can move is not a reference". Measured
#: 2026-10-12: `task-sandbox-phase2-horizon` advanced five commits while this
#: work was in progress, one of them merging
#: `origin/task-secondbrain-ablation-2026-10-12` which ADDS
#: `src/brainattribution.py`. Comparing against the branch name therefore
#: reported `src/` as changed by 423 deleted lines this branch never touched.
BASE_COMMIT = "574863579f483e7ba7a0dba72a0ddbeca432fca8"

UTC = datetime.timezone.utc


class SandboxCase(unittest.TestCase):
    """A throwaway sandbox directory per test, and the env put back."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sbx-test-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.saved_env = dict(os.environ)

        def restore_env():
            os.environ.clear()
            os.environ.update(self.saved_env)

        self.addCleanup(restore_env)

    def boot(self, **kw):
        handles = sandbox_run._boot(self.tmp, **kw)
        self.addCleanup(handles["teardown"])
        return handles


# ===================================================================== boot

class BootFailsClosed(SandboxCase):
    """`_boot` refuses before a record is read, and each refusal is proven."""

    def test_boot_isolates_and_injects(self):
        handles = self.boot()
        state = os.path.join(self.tmp, "state")
        self.assertTrue(sandbox_run._inside(store.queue_path(), state),
                        store.queue_path())
        self.assertTrue(sandbox_run._inside(store.campaigns_path(), state),
                        store.campaigns_path())
        self.assertIsNone(os.environ.get("CAMPAIGNS"))
        self.assertEqual(store.now(), handles["clock"].now_iso())
        # The barrier `store.refuse_production_write` consults. Inert in a
        # plain script; `sandbox_run` imports unittest for exactly this.
        self.assertTrue(store.under_test())

    def test_boot_refuses_when_the_store_did_not_move_control(self):
        """Guards `test_boot_isolates_and_injects`'s queue_path assertion."""
        original = store.use_directory

        def no_op(path):
            os.makedirs(path, exist_ok=True)
            return lambda: None

        store.use_directory = no_op
        self.addCleanup(setattr, store, "use_directory", original)
        with self.assertRaises(sandbox_run.SandboxRefused) as caught:
            sandbox_run._boot(self.tmp)
        self.assertIn("not inside the sandbox directory", str(caught.exception))

    def test_boot_refuses_a_surviving_campaigns_override_control(self):
        """The phase-1 finding: a stale CAMPAIGNS points state at production."""
        original = store.use_directory

        def leaky(path):
            restore = original(path)
            os.environ["CAMPAIGNS"] = os.path.join(ROOT, "work",
                                                   "campaigns.jsonl")
            return restore

        store.use_directory = leaky
        self.addCleanup(setattr, store, "use_directory", original)
        with self.assertRaises(sandbox_run.SandboxRefused) as caught:
            sandbox_run._boot(self.tmp)
        self.assertIn("CAMPAIGNS override survived", str(caught.exception))

    def test_boot_refuses_when_the_wire_is_not_sealed_control(self):
        """A seal that lets a call through must abort the boot.

        The stand-in transport RETURNS rather than reaching anything: a
        control that proved the seal by opening a real socket would be the one
        thing this whole run promises not to do.
        """
        original_seal = sandboxharness.seal_wire
        original_transport = providers.set_transport(
            lambda method, url, headers=None, body=None, timeout=None:
            (200, {"ok": True, "why": "test stand-in; no socket was opened"}))
        self.addCleanup(providers.set_transport, original_transport)
        sandboxharness.seal_wire = lambda allow=(): (lambda: None, [])
        self.addCleanup(setattr, sandboxharness, "seal_wire", original_seal)
        with self.assertRaises(sandbox_run.SandboxRefused) as caught:
            sandbox_run._boot(self.tmp)
        self.assertIn("wire is NOT sealed", str(caught.exception))

    def test_boot_refuses_when_readbacks_are_not_sealed_control(self):
        """A readback that returns a default must abort the boot.

        `bison.campaign` is stubbed to a benign dict rather than left to the
        real one: in a worktree there is no `config/.env`, so the real call
        raises `MissingKey` before the transport and the control would pass
        for the wrong reason.
        """
        original_seal = sandboxharness.seal_readbacks
        original_campaign = bison.campaign
        sandboxharness.seal_readbacks = lambda: (lambda: None)
        bison.campaign = lambda *a, **k: {"id": 1, "why": "test stand-in"}
        self.addCleanup(setattr, bison, "campaign", original_campaign)
        self.addCleanup(setattr, sandboxharness, "seal_readbacks",
                        original_seal)
        with self.assertRaises(sandbox_run.SandboxRefused) as caught:
            sandbox_run._boot(self.tmp)
        self.assertIn("readbacks are NOT sealed", str(caught.exception))

    def test_a_failure_inside_boot_leaves_no_clock_installed(self):
        """Measured regression: a control that made `bison.campaign` raise
        `MissingKey` left the INJECTED CLOCK installed, and the next test read
        the simulated instant as the wall clock and passed for the wrong
        reason. `_boot` now unwinds on any exception."""
        original_seal = sandboxharness.seal_readbacks
        original_campaign = bison.campaign
        sandboxharness.seal_readbacks = lambda: (lambda: None)

        def explode(*_a, **_k):
            raise RuntimeError("boot blew up after the clock was installed")

        bison.campaign = explode
        self.addCleanup(setattr, bison, "campaign", original_campaign)
        self.addCleanup(setattr, sandboxharness, "seal_readbacks",
                        original_seal)
        before = store.now
        with self.assertRaises(RuntimeError):
            sandbox_run._boot(self.tmp)
        self.assertIs(store.now, before)
        self.assertIsNone(os.environ.get("QUEUE"))

    def test_boot_refuses_when_the_clock_is_not_injected_control(self):
        original = sandboxclock.install
        sandboxclock.install = lambda clock: (lambda: None)
        self.addCleanup(setattr, sandboxclock, "install", original)
        with self.assertRaises(sandbox_run.SandboxRefused) as caught:
            sandbox_run._boot(self.tmp)
        self.assertIn("clock was not injected", str(caught.exception))

    def test_boot_refuses_when_production_state_is_absent_control(self):
        """Without this the isolation claim compares None to None forever."""
        empty = tempfile.mkdtemp(prefix="sbx-noprod-")
        self.addCleanup(shutil.rmtree, empty, ignore_errors=True)
        original = sandboxharness.production_root
        sandboxharness.production_root = lambda: empty
        self.addCleanup(setattr, sandboxharness, "production_root", original)
        with self.assertRaises(sandbox_run.SandboxRefused) as caught:
            sandbox_run._boot(self.tmp)
        self.assertIn("refusing to claim isolation", str(caught.exception))

    def test_the_cli_refuses_an_out_dir_inside_production(self):
        protected = store.protected_directories()[0]
        code = sandbox_run.main(["--mode", "one", "--out",
                                 os.path.join(protected, "sandbox")])
        self.assertEqual(code, 2)


# ============================================================= wire and spend

class TheWireIsSealed(SandboxCase):

    def test_every_host_is_refused_and_the_control_fires(self):
        handles = self.boot()
        self.assertTrue(sandboxharness.assert_wire_sealed())
        with self.assertRaises(sandboxharness.NetworkTouched):
            providers.request("GET", "https://api.heyreach.io/api/public/x", {})
        self.assertGreaterEqual(len(handles["wire_calls"]), 2)

    def test_an_allowed_host_makes_the_control_fail_control(self):
        """Guards the test above: the control must be capable of NOT firing.

        `providers._urllib_transport` is stubbed first, because `seal_wire`
        forwards an ALLOWED host to it - and a control that proved the seal by
        reaching api.emailbison.com would be the one thing this run promises
        not to do. With the forward stubbed, `assert_wire_sealed` gets a
        response instead of `NetworkTouched` and raises AssertionError, which
        is the whole claim: the control can fail.
        """
        original = providers._urllib_transport
        providers._urllib_transport = (
            lambda method, url, headers=None, body=None, timeout=None:
            (200, {"ok": True, "why": "test stand-in; no socket was opened"}))
        self.addCleanup(setattr, providers, "_urllib_transport", original)
        undo, calls = sandboxharness.seal_wire(allow=("api.emailbison.com",))
        self.addCleanup(undo)
        with self.assertRaises(AssertionError) as caught:
            sandboxharness.assert_wire_sealed()
        self.assertIn("NOT sealed", str(caught.exception))
        self.assertEqual(len(calls), 1)

    def test_readbacks_raise(self):
        self.boot()
        for call in (lambda: bison.campaign("1"),
                     lambda: bison.campaign_lead_count("1")):
            with self.assertRaises(sandboxharness.NetworkTouched):
                call()

    def test_the_run_spends_no_credits(self):
        from src import waterfall

        self.boot()
        recs, _blob = sandbox_run.load_fixture(1)
        self.assertEqual(
            sum(waterfall.spend(r)["expected"] for r in recs[:20]), 0)

    def test_a_spend_row_makes_the_credit_check_non_zero_control(self):
        """Guards `test_the_run_spends_no_credits`: zero must be falsifiable."""
        from src import waterfall

        recs, _blob = sandbox_run.load_fixture(1)
        poisoned = copy.deepcopy(recs[0])
        # `waterfall.ledger` is `rec["waterfall"]` and it is a LIST of calls.
        poisoned["waterfall"] = [
            {"provider": "contactout", "stage": "person",
             "expected_cost": 3, "actual_cost": None}]
        self.assertEqual(waterfall.spend(poisoned)["expected"], 3)
        self.assertEqual(waterfall.spend(recs[1])["expected"], 0)


# ===================================================== production untouched

class ProductionIsUntouched(SandboxCase):

    def _fake_root(self):
        root = tempfile.mkdtemp(prefix="sbx-prod-")
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        os.makedirs(os.path.join(root, "work"))
        for name in ("queue.jsonl", "campaigns.jsonl"):
            with open(os.path.join(root, "work", name), "w",
                      encoding="utf-8") as handle:
                handle.write('{"id": "x"}\n')
        return root

    def test_an_unchanged_window_passes(self):
        root = self._fake_root()
        before = sandboxharness.production_fingerprint(root)
        self.assertTrue(sandboxharness.assert_production_unchanged(
            before, root=root))

    def test_a_changed_byte_is_detected_control(self):
        """Guards every `assert_production_unchanged` in the runner."""
        root = self._fake_root()
        before = sandboxharness.production_fingerprint(root)
        with open(os.path.join(root, "work", "queue.jsonl"), "a",
                  encoding="utf-8") as handle:
            handle.write('{"id": "y"}\n')
        with self.assertRaises(sandboxharness.ProductionTouched):
            sandboxharness.assert_production_unchanged(before, root=root)

    def test_a_vanished_file_is_detected_control(self):
        root = self._fake_root()
        before = sandboxharness.production_fingerprint(root)
        os.remove(os.path.join(root, "work", "campaigns.jsonl"))
        with self.assertRaises(sandboxharness.ProductionTouched):
            sandboxharness.assert_production_unchanged(before, root=root)

    def test_the_real_production_files_survive_a_boot(self):
        before = sandboxharness.production_fingerprint()
        handles = self.boot()
        recs, _blob = sandbox_run.load_fixture(1)
        store.save(recs[:5])
        handles["teardown"]()
        self.addCleanup(lambda: None)      # teardown already run
        sandboxharness.assert_production_unchanged(before)


# ====================================================================== clock

class TheInjectedClock(SandboxCase):

    def test_the_window_crosses_the_zagreb_dst_change(self):
        clock = sandboxclock.SimClock(sandbox_run.START,
                                      zone=sandbox_run.ZAGREB)
        self.assertEqual(clock.utc_offset_hours(), 2.0)
        self.assertEqual(clock.local().strftime("%H:%M"), "08:00")
        crossings, dst_days = [], []
        for _ in range(sandbox_run.DAYS - 1):
            crossed = clock.advance(hours=sandbox_run.ADVANCE_HOURS)
            crossings.extend(crossed)
            if any(c.startswith("dst_change") for c in crossed):
                dst_days.append((clock.day_index, clock.at.date()))
        self.assertIn("dst_change:+2->+1", crossings)
        self.assertEqual([d for _i, d in dst_days], [sandbox_run.DST_DATE])
        self.assertEqual(clock.utc_offset_hours(), 1.0)
        # The whole point of a FIXED UTC interval: the LOCAL hour moves.
        self.assertEqual(clock.local().strftime("%H:%M"), "07:00")
        self.assertEqual(clock.at.date(), datetime.date(2026, 12, 10))

    def test_a_window_after_the_transition_sees_no_crossing_control(self):
        """Guards the test above: `dst_crossed` must be falsifiable."""
        clock = sandboxclock.SimClock(
            datetime.datetime(2026, 11, 2, 6, 0, tzinfo=UTC),
            zone=sandbox_run.ZAGREB)
        crossings = []
        for _ in range(20):
            crossings.extend(clock.advance(hours=24))
        self.assertFalse([c for c in crossings if c.startswith("dst_change")])

    def test_store_now_follows_the_simulated_clock(self):
        handles = self.boot()
        clock = handles["clock"]
        self.assertEqual(store.now(), clock.now_iso())
        clock.advance(days=5)
        self.assertEqual(store.now(), clock.now_iso())
        self.assertTrue(store.now().startswith("2026-10-17"))

    def test_install_and_undo_move_store_now_both_ways_control(self):
        """Guards the test above: the clock assertion must be falsifiable.

        Self-contained rather than relying on "nothing else installed a
        clock". An earlier version asserted only the uninstalled direction and
        PASSED while a leaked clock from another test was still installed -
        because that clock's instant happened to be the run's own start date,
        which is also today. Installing and undoing in one test cannot be
        fooled that way.
        """
        clock = sandboxclock.SimClock(
            datetime.datetime(2031, 3, 4, 11, 22, tzinfo=UTC))
        before = store.now
        undo = sandboxclock.install(clock)
        try:
            self.assertEqual(store.now(), clock.now_iso())
            self.assertTrue(store.now().startswith("2031-03-04"))
        finally:
            undo()
        self.assertIs(store.now, before)
        self.assertNotEqual(store.now(), clock.now_iso())

    def test_the_named_module_set_holds_no_unpatched_business_clock_read(self):
        rows = sandboxclock.unpatched_business_clock_reads(
            only=sandboxclock.SIMULATED_PATH_MODULES)
        self.assertEqual(rows, [], "unpatched business-clock reads: %r" % rows)

    def test_the_scanner_can_report_a_read_control(self):
        """Guards the zero above. A scanner that finds nothing anywhere is
        indistinguishable from a broken scanner."""
        rows = sandboxclock.unpatched_business_clock_reads(only=None)
        self.assertGreater(len(rows), 0)
        files = {os.path.basename(r[0]) for r in rows}
        self.assertIn("evidence.py", files)


class EvidenceReAgeingReadsTheRealClock(SandboxCase):
    """A measured defect, not a grep: `quality.assess` takes no clock."""

    def test_the_two_answers_differ(self):
        """The simulated date is the run's END, not its start.

        It matters, and it is this repository's own "a name-diff needs both
        sides of midnight" lesson: the run STARTS on 2026-10-12, which is also
        the real date this was written, so a control anchored at the start
        measured `differs: False` and would have reported the defect absent on
        exactly one day of the year. The run reaches 2026-12-10, and the
        wall-clock answer is wrong by however far the simulation has travelled.
        """
        recs, _blob = sandbox_run.load_fixture(1)
        sim_end = (sandbox_run.START + datetime.timedelta(
            days=sandbox_run.DAYS - 1)).date().isoformat()
        control = sandbox_run.evidence_clock_control(recs[0], sim_end)
        self.assertEqual(control["checked"], 1)
        self.assertTrue(control["differs"], control)
        drift = (control["age_days_with_simulated_today"]
                 - control["age_days_as_quality_asks"])
        self.assertEqual(
            drift,
            (datetime.date.fromisoformat(sim_end)
             - datetime.date.today()).days,
            "the gap between the simulated and the wall-clock answer is "
            "exactly how far the simulation has travelled: %r" % (control,))

    def test_quality_assess_has_no_clock_parameter(self):
        import inspect

        from src import quality

        params = inspect.signature(quality.assess).parameters
        self.assertNotIn("today", params)
        self.assertNotIn("at", params)
        # And `_selected` DOES take one, which is what makes it injectable one
        # layer down and uninjectable from `assess`.
        self.assertIn("today", inspect.signature(quality._selected).parameters)

    def test_the_same_today_gives_the_same_answer_control(self):
        """Guards `test_the_two_answers_differ`: `differs` must be able to be
        False, or it is measuring nothing."""
        recs, _blob = sandbox_run.load_fixture(1)
        item = recs[0]["research"][0]
        real_today = datetime.date.today().isoformat()
        self.assertEqual(evidence.recheck(item, real_today).get("age_days"),
                         evidence.recheck(item).get("age_days"))


# ============================================================== verification

class VerificationPolicyIsExercisedNotBypassed(SandboxCase):
    """The survey's three cases, re-measured against the landed fixture."""

    def setUp(self):
        super().setUp()
        recs, _blob = sandbox_run.load_fixture(1)
        self.rec = recs[0]
        self.contact = self.rec["contacts"][0]
        self.policy = lint.policy_for_record(self.rec)

    def test_two_independent_confirmations_make_it_sendable(self):
        self.assertEqual(self.policy["primary"], "deliverable")
        self.assertEqual(self.policy["required_confirmations"], 2)
        resolved = verification.resolve(self.contact, self.policy)
        self.assertTrue(resolved["sendable"])
        self.assertEqual(resolved["confirmation_count"], 2)
        self.assertEqual(sorted(resolved["confirmed_by"]),
                         ["deliverable", "reoon"])

    def test_one_confirmation_alone_is_not_sendable_control(self):
        one = copy.deepcopy(self.contact)
        one["verification"]["evidence"] = [
            e for e in one["verification"]["evidence"]
            if e["provider"] == "deliverable"]
        self.assertFalse(verification.is_sendable(one, self.policy))

    def test_evidence_for_a_different_address_is_not_sendable_control(self):
        other = copy.deepcopy(self.contact)
        for entry in other["verification"]["evidence"]:
            entry["email"] = "someone.else@elsewhere.invalid"
        self.assertFalse(verification.is_sendable(other, self.policy))

    def test_a_stored_sendable_flag_does_nothing(self):
        bare = copy.deepcopy(self.contact)
        bare["verification"] = {}
        bare["sendable"] = True
        self.assertFalse(verification.is_sendable(bare, self.policy))


# =================================================================== fixture

class TheFixtureIsReadNotGenerated(SandboxCase):

    def test_it_loads_the_landed_artefact(self):
        recs, blob = sandbox_run.load_fixture(1)
        self.assertEqual(len(recs), 100)
        self.assertTrue(all(len(r["contacts"]) == 3 for r in recs))
        self.assertEqual(blob["seed"], 1)
        self.assertEqual(blob["data_credits_spent"], 0)

    def test_both_seeds_exist_and_differ(self):
        one, _ = sandbox_run.load_fixture(1)
        two, _ = sandbox_run.load_fixture(2)
        self.assertNotEqual([r["domain"] for r in one],
                            [r["domain"] for r in two])

    def test_a_missing_fixture_is_refused_control(self):
        with self.assertRaises(sandbox_run.SandboxRefused):
            sandbox_run.load_fixture(999)

    def test_every_domain_is_synthetic(self):
        recs, _blob = sandbox_run.load_fixture(1)
        bad = [r["domain"] for r in recs
               if not sandboxharness.is_synthetic_domain(r["domain"])]
        self.assertEqual(bad, [])

    def test_a_real_domain_in_the_fixture_is_refused_control(self):
        """Guards the test above. Poisons a COPY on disk, never the artefact."""
        recs, blob = sandbox_run.load_fixture(1)
        blob["queue_records"] = recs[:2]
        blob["queue_records"][0]["domain"] = "productive.io"
        path = os.path.join(self.tmp, "poisoned.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(blob, handle)
        with self.assertRaises(sandbox_run.SandboxRefused) as caught:
            sandbox_run.load_fixture(path=path)
        self.assertIn("non-synthetic domain", str(caught.exception))


class TwoMeasuredFindingsAboutDrivingTheFixture(SandboxCase):

    def setUp(self):
        super().setUp()
        self.config = clients.load("productive")
        recs, _blob = sandbox_run.load_fixture(1)
        self.rec = recs[0]

    def test_the_records_cadence_steps_key_is_inert(self):
        """`cadence_steps` on a RECORD changes nothing: it is a CAMPAIGN key."""
        stored = [s["key"] for s in self.rec["cadence_steps"]]
        resolved = [s["key"] for s in cadence.steps_for(
            None, self.config, self.rec, self.rec["contacts"][0])]
        self.assertEqual(stored, [s["key"] for s in cadence.STEPS])
        self.assertNotEqual(sorted(stored), sorted(resolved))
        self.assertEqual(resolved, ["li1", "em1", "li2", "em2", "li3", "em3",
                                    "li4", "em4", "li5", "em5"])
        # And the proof that it is the CAMPAIGN key that bites.
        as_campaign = {"cadence_steps": list(self.rec["cadence_steps"])}
        self.assertEqual(
            [s["key"] for s in cadence.steps_for(as_campaign, self.config,
                                                 self.rec, None)],
            stored)

    def test_a_null_hook_blocks_every_email_step(self):
        """`src/lint.py:756`. The fixture ships `hook: null`, lane `cold`."""
        self.assertIsNone(self.rec.get("hook"))
        self.assertEqual(self.rec.get("lane"), "cold")
        contact = self.rec["contacts"][0]
        step = {"channel": "email", "subject": "s",
                "body": "b " * 70 + "\n\nreply STOP"}
        self.assertIn("cold_no_hook",
                      lint.check(self.rec, contact["key"], step))

    def test_installing_the_copy_clears_the_hook_and_fills_the_slots(self):
        report = sandbox_run.install_phase5_copy([self.rec], self.config)
        self.assertEqual(report["hooks_filled"], 1)
        self.assertEqual(report["refused"], {})
        self.assertTrue((self.rec.get("hook") or "").strip())
        # Nine of the ten steps are `generated`; one (li1) names a template.
        for contact in self.rec["contacts"]:
            slots = self.rec["cadence"][contact["key"]]
            self.assertEqual(len(slots), 9, sorted(slots))
        built = cadence.build(self.rec, self.config,
                              recs=[self.rec]).get("contacts") or {}
        key = self.rec["contacts"][0]["key"]
        self.assertEqual(sorted(built[key]),
                         ["em1", "em2", "em3", "em4", "em5",
                          "li1", "li2", "li3", "li4", "li5"])

    def test_without_the_copy_the_email_steps_are_absent_control(self):
        """Guards the test above: `expand_step` drops a wordless generated
        step, so the fixture verbatim measures a LinkedIn-only estate."""
        built = cadence.build(self.rec, self.config,
                              recs=[self.rec]).get("contacts") or {}
        key = self.rec["contacts"][0]["key"]
        self.assertEqual(sorted(built[key]),
                         ["li1", "li2", "li3", "li4", "li5"])

    def _words(self, name, family):
        from src import optout

        contact = dict(self.rec["contacts"][0], persona=family)
        values = cadence.template_vars(self.rec, contact, self.config)
        rendered = cadence.render(cadence.TEMPLATES[name], values)
        return len(lint.countable_words(
            optout.append_opt_out(rendered["body"])))

    def test_the_chosen_email_templates_satisfy_the_real_word_contract(self):
        for family in ("champion", "economic_buyer"):
            for step_key, name in sandbox_run.EMAIL_TEMPLATE_FOR_STEP.items():
                low, _target, high = lint.STEP_WORD_CONTRACT[step_key]
                words = self._words(name, family)
                self.assertTrue(low <= words <= high,
                                "%s/%s %s: %d words, contract %d-%d"
                                % (step_key, family, name, words, low, high))

    def test_four_shipped_templates_break_the_shipped_contract(self):
        """A FINDING, asserted rather than restated.

        It is also the control for the test above: if no template could ever
        exceed a ceiling, that test would be measuring nothing. The
        economic-buyer variant of the day-8 rung is the one with a consequence
        here - it is 105 words against 90, which is why em3 renders
        `rung3_champion` for both persona families rather than the
        persona-matched variant.
        """
        ceiling = lint.STEP_WORD_CONTRACT["em1"][2]
        for name in sandbox_run.EMAIL_TEMPLATES_OVER_CONTRACT:
            worst = max(self._words(name, f)
                        for f in ("champion", "economic_buyer"))
            self.assertGreater(worst, ceiling,
                               "%s is %d words, ceiling %d"
                               % (name, worst, ceiling))
        self.assertGreater(
            max(self._words("rung3_economic_buyer", f)
                for f in ("champion", "economic_buyer")),
            lint.STEP_WORD_CONTRACT["em3"][2])


# ========================================== the timeline disagrees with the gate

class TheTimelineAndTheSendGateDisagree(SandboxCase):
    """`src/cadence.py:1354` asks `lint.sendable` with no client policy."""

    def test_the_two_answers_differ(self):
        recs, _blob = sandbox_run.load_fixture(1)
        rec, contact = recs[0], recs[0]["contacts"][0]
        control = sandbox_run.status_policy_control(rec, contact)
        self.assertTrue(control["disagree"], control)
        self.assertFalse(control["lint_sendable_no_policy"])
        self.assertTrue(control["lint_sendable_client_policy"])
        self.assertEqual(control["default_policy_primary"], "contactout")
        self.assertEqual(control["client_policy_primary"], "deliverable")

    def test_the_effect_reaches_the_timeline_status(self):
        config = clients.load("productive")
        recs, _blob = sandbox_run.load_fixture(1)
        rec = recs[0]
        sandbox_run.install_phase5_copy([rec], config)
        handles = self.boot()
        store.save([rec])
        from src import approve

        sandbox_run.approve_ready(rec, config)
        built = cadence.build(rec, config, recs=[rec]).get("contacts") or {}
        key = rec["contacts"][0]["key"]
        contact = rec["contacts"][0]
        # The timeline says blocked...
        self.assertEqual(built[key]["em1"]["status"], "blocked")
        # ...and `eligibility.decide`, which passes the client policy, does
        # not. Two answers to one question at one instant.
        handles["clock"].advance(days=1)
        decision = eligibility.decide(rec, contact, "em1", recs=[rec],
                                      config=config, day=1, timeline=built)
        self.assertEqual(decision["verdict"], eligibility.ELIGIBLE,
                         decision["reasons"])

    def test_a_contactout_confirmation_removes_the_disagreement_control(self):
        """Guards the test above: `disagree` must be falsifiable. Adding the
        provider the DEFAULT policy wants makes both answers agree, which is
        what identifies the policy as the cause rather than the address."""
        recs, _blob = sandbox_run.load_fixture(1)
        rec = recs[0]
        contact = copy.deepcopy(rec["contacts"][0])
        contact["verification"]["evidence"].append(
            verification.result("contactout", verification.S_VALID,
                                contact["email"], reason="control"))
        control = sandbox_run.status_policy_control(rec, contact)
        self.assertTrue(control["lint_sendable_no_policy"])
        self.assertFalse(control["disagree"], control)


# ============================================= the runner consumes the authorities

class TheRunnerGoesThroughTheRealModules(SandboxCase):
    """Not a source search. Each authority is replaced with a raiser and the
    runner is required to blow up, which proves the call is on the path."""

    def _one_record_day(self):
        config = clients.load("productive")
        recs, _blob = sandbox_run.load_fixture(1)
        recs = recs[:1]
        sandbox_run.install_phase5_copy(recs, config)
        handles = self.boot()
        store.save(recs)
        fake_bison = sandbox_run.FakeBison(handles["clock"])
        fake_heyreach = sandbox_run.FakeHeyReach(handles["clock"])
        undo = sandbox_run.install_fake_providers(fake_bison, fake_heyreach)
        self.addCleanup(undo)
        return (handles, config, recs,
                {"bison": fake_bison, "heyreach": fake_heyreach,
                 "wire_calls": handles["wire_calls"]})

    def test_a_day_runs(self):
        handles, config, recs, fakes = self._one_record_day()
        metrics = sandbox_run.run_day(handles["clock"], recs, config, {},
                                      {recs[0]["id"]: 0}, fakes,
                                      {"pushed_total": 0})
        self.assertTrue(metrics["poll"]["emailbison"]["healthy"])
        self.assertGreater(metrics["approved"], 0)
        self.assertIn("day_index", metrics)

    def test_eligibility_decide_is_on_the_path_control(self):
        handles, config, recs, fakes = self._one_record_day()
        original = eligibility.decide

        def raiser(*a, **k):
            raise RuntimeError("eligibility.decide was called")

        eligibility.decide = raiser
        self.addCleanup(setattr, eligibility, "decide", original)
        with self.assertRaises(RuntimeError) as caught:
            sandbox_run.run_day(handles["clock"], recs, config, {},
                                {recs[0]["id"]: 0}, fakes,
                                {"pushed_total": 0})
        self.assertIn("eligibility.decide was called", str(caught.exception))

    def test_cadence_build_is_on_the_path_control(self):
        handles, config, recs, fakes = self._one_record_day()
        original = cadence.build

        def raiser(*a, **k):
            raise RuntimeError("cadence.build was called")

        cadence.build = raiser
        self.addCleanup(setattr, cadence, "build", original)
        with self.assertRaises(RuntimeError):
            sandbox_run.run_day(handles["clock"], recs, config, {},
                                {recs[0]["id"]: 0}, fakes,
                                {"pushed_total": 0})

    def test_the_watcher_is_on_the_path_and_calls_the_feed(self):
        handles, config, recs, fakes = self._one_record_day()
        contact = recs[0]["contacts"][0]
        fakes["bison"].rows = [sandbox_run.bison_row(
            recs[0]["id"], recs[0]["client"], contact["key"],
            contact["email"], 0, "reply", sandbox_run.EXPLICIT_REMOVAL)]
        sandbox_run.run_day(handles["clock"], recs, config, {},
                            {recs[0]["id"]: 0}, fakes, {"pushed_total": 0})
        self.assertTrue(any(c["fn"] == "bison.fetch_replies"
                            for c in fakes["bison"].calls))
        self.assertTrue(any(c["fn"] == "bison.bound_workspace"
                            for c in fakes["bison"].calls))
        stored = store.load()
        contact_after = next(c for c in stored[0]["contacts"]
                             if c["key"] == contact["key"])
        self.assertTrue(contact_after.get("unsubscribed"))

    def test_the_real_feed_never_returns_data_control(self):
        """Guards the test above: it is the FAKE that carried the reply.

        A run that forgot to install it gets a REFUSAL, never rows. Which
        refusal depends on the tree: in a linked worktree there is no
        `config/.env`, so `providers.key` raises `MissingKey` before the
        transport is reached and the wire seal never gets a turn. Both are
        refusals and the assertion is about what does NOT come back.
        """
        self.boot()
        with self.assertRaises((sandboxharness.NetworkTouched,
                                providers.MissingKey,
                                providers.ProviderError)) as caught:
            bison.fetch_replies()
        self.assertNotIsInstance(caught.exception, (list, tuple))


# ================================================== the workspace pin is real

class TheWorkspacePinIsEnforced(SandboxCase):

    def _poll(self, workspace_id):
        from src import replywatch

        handles = self.boot()
        recs, _blob = sandbox_run.load_fixture(1)
        store.save(recs[:1])
        fake_bison = sandbox_run.FakeBison(handles["clock"])
        fake_bison.bound_workspace = lambda: {"id": workspace_id,
                                              "name": "control"}
        fake_heyreach = sandbox_run.FakeHeyReach(handles["clock"])
        undo = sandbox_run.install_fake_providers(fake_bison, fake_heyreach)
        self.addCleanup(undo)
        return replywatch.poll_once("emailbison", max_pages=1, live=True,
                                    env=sandbox_run.SANDBOX_ENV,
                                    now=handles["clock"].now_iso())

    def test_the_matching_workspace_polls(self):
        status = self._poll(10)
        self.assertTrue(status["healthy"], status)

    def test_a_mismatched_workspace_is_refused_control(self):
        status = self._poll(99)
        self.assertFalse(status["healthy"], status)
        self.assertIn("WrongWorkspace", status["last_error"])


# ========================================= classification / stop / opt-out

class TheThreeAxesAreIndependent(SandboxCase):
    """A reply may stop a cadence without being a permanent opt-out, and an
    ambiguous reply must end in a person. These are four different reads."""

    def test_the_classifier_outcomes_for_the_four_mandatory_shapes(self):
        measured = {}
        for name, spec in sandbox_run.REPLY_CASES.items():
            verdict = replies.classify(spec["text"])
            outcome = accountpolicy.CLASSIFIER_OUTCOME.get(
                verdict["classification"], accountpolicy.UNKNOWN)
            plan = accountpolicy.effects(outcome)
            measured[name] = (verdict["classification"], plan["replier"],
                              plan["account"], plan["review"])
        # UNVERIFIED: recorded as measured on this branch, not endorsed.
        self.assertEqual(
            measured["b_question_with_stop_and_blocking"][1:],
            (accountpolicy.HOLD, accountpolicy.HOLD, True))
        self.assertEqual(
            measured["c_positive_contract_no_further_emails"][1:],
            (accountpolicy.HOLD, accountpolicy.HOLD, True))
        self.assertEqual(
            measured["d_explicit_removal"][1],
            accountpolicy.SUPPRESS)

    def test_a_positive_reply_with_an_unsubscribe_footer_is_suppressed(self):
        """THE DEFECT, pinned.

        "Sounds great, Thursday works. You can unsubscribe from our mailing
        list at any time." is classified `unsubscribe` at confidence 0.95 and
        the replier is SUPPRESSED - permanently - with NO human review. A
        buying signal became a permanent opt-out silently.

        Asserted as the CURRENT behaviour deliberately, so that a future fix
        makes this test fail and somebody has to come and read this docstring.
        The operator's rule is that a confident false positive is a FAIL even
        when it is "safe", and that an ambiguous reply must end in review.
        """
        text = sandbox_run.REPLY_CASES[
            "a_positive_with_unsubscribe_footer"]["text"]
        verdict = replies.classify(text)
        self.assertEqual(verdict["classification"], replies.UNSUBSCRIBE)
        self.assertGreaterEqual(verdict["confidence"], 0.9)
        plan = accountpolicy.effects(accountpolicy.CLASSIFIER_OUTCOME[
            verdict["classification"]])
        self.assertEqual(plan["replier"], accountpolicy.SUPPRESS)
        self.assertFalse(plan["review"])

    def test_the_same_sentence_without_the_footer_is_not_suppressed_control(self):
        """Guards the test above: it is the FOOTER that causes it, not the
        warmth of the reply. Without the footer nothing suppresses."""
        verdict = replies.classify("Sounds great, Thursday works.")
        self.assertNotEqual(verdict["classification"], replies.UNSUBSCRIBE)
        plan = accountpolicy.effects(accountpolicy.CLASSIFIER_OUTCOME.get(
            verdict["classification"], accountpolicy.UNKNOWN))
        self.assertNotEqual(plan["replier"], accountpolicy.SUPPRESS)

    def test_axes_report_a_stop_without_an_optout(self):
        rec = {"id": "r", "contacts": [{"key": "c"}], "events": [
            {"type": "reply_classified", "contact": "c",
             "classification": "question", "outcome": "unknown"}],
            "review": {"open": True}}
        axes = sandbox_run._axes(rec, "c", {"em1", "em2"}, set())
        self.assertTrue(axes["cadence_stop"])
        self.assertFalse(axes["permanent_optout"])
        self.assertTrue(axes["human_review"])
        self.assertTrue(axes["verdict_persisted"])

    def test_axes_report_an_optout_when_there_is_one_control(self):
        rec = {"id": "r", "contacts": [{"key": "c", "unsubscribed": True}],
               "events": [], "review": {}}
        axes = sandbox_run._axes(rec, "c", {"em1"}, {"em1"})
        self.assertTrue(axes["permanent_optout"])
        # And a stop is NOT claimed when nothing stopped.
        self.assertFalse(axes["cadence_stop"])
        self.assertFalse(axes["verdict_persisted"])

    def test_axes_never_claim_a_stop_from_an_empty_before_set_control(self):
        """A vacuous pass is the failure mode this guards: with nothing
        eligible beforehand, every reply would "stop the cadence"."""
        rec = {"id": "r", "contacts": [{"key": "c"}], "events": [],
               "review": {}}
        self.assertFalse(
            sandbox_run._axes(rec, "c", set(), set())["cadence_stop"])


# ======================================= the real ingestion entry point

class TheRealIngestionEntryPoint(unittest.TestCase):
    """`replaysim.simulate` alone proves none of these three things.

    The probe runs ONCE for the class: it drives five real polls through
    `replywatch.poll_once` and each one rebuilds a cadence, so per-test setup
    would cost five times as much for the same measurement.
    """

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="sbx-replies-")
        cls.saved_env = dict(os.environ)
        cls.result = sandbox_run.reply_scenarios(cls.tmp, seed=1)

    @classmethod
    def tearDownClass(cls):
        os.environ.clear()
        os.environ.update(cls.saved_env)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_the_watcher_actually_calls_ingestion(self):
        entry = self.result["ingestion_entry"]
        self.assertTrue(entry["watcher_calls_ingestion"])
        self.assertGreaterEqual(entry["watcher_fetch_calls"], 4)
        self.assertTrue(entry["workspace_pin_checked"])
        self.assertTrue(entry["every_case_was_ingested"])

    def test_a_verdict_is_persisted_for_an_attributable_reply(self):
        self.assertTrue(
            self.result["ingestion_entry"]["verdict_persisted_for_attributed"])
        for name, case in self.result["cases"].items():
            self.assertIsNotNone(case["axes"]["classification"], name)

    def test_an_unattributed_reply_is_retained_not_dropped(self):
        un = self.result["unattributed"]
        self.assertTrue(un["ingestion_saw_it"])
        self.assertEqual(un["reported_unmatched"], 1)
        self.assertTrue(un["retained_as_notification"])
        self.assertGreaterEqual(un["unmatched_notification_rows"], 1)

    def test_an_unattributed_replys_text_and_verdict_are_not_retained(self):
        """`src/inbound.py:429`. The finding, measured: the ARRIVAL is kept,
        the content and the classification are not."""
        un = self.result["unattributed"]
        self.assertFalse(un["reply_event_persisted_on_any_record"])
        self.assertFalse(un["classification_persisted"])

    def test_three_of_the_four_shapes_behave_and_one_does_not(self):
        cases = self.result["cases"]
        self.assertFalse(cases["a_positive_with_unsubscribe_footer"]["pass"])
        for name in ("b_question_with_stop_and_blocking",
                     "c_positive_contract_no_further_emails",
                     "d_explicit_removal"):
            self.assertTrue(cases[name]["pass"], cases[name])


# ===================================================== campaign stop button

class ThePausedCampaignIsAStopButton(SandboxCase):

    def test_pausing_blocks_a_step_the_running_campaign_allowed(self):
        from src import campaigns

        config = clients.load("productive")
        handles = self.boot()
        recs, _blob = sandbox_run.load_fixture(1)
        recs = recs[:5]
        sandbox_run.install_phase5_copy(recs, config)
        store.save(recs)
        by_record, campaign = sandbox_run.build_campaign(recs, config,
                                                         cohort="quiet")
        self.assertIsNotNone(campaign)
        members = [r for r in recs if r["id"] in by_record]
        self.assertTrue(members)
        rec = members[0]
        for member in members:
            sandbox_run.approve_ready(member, config, campaign=campaign)
        # The step approvals just moved the campaign's material, so the
        # campaign approval is legitimately stale. See
        # `refresh_campaign_approval`: this is what the operator looking again
        # amounts to, and without it the baseline below is
        # `held:campaign_approval_stale` and the pause proves nothing.
        sandbox_run.refresh_campaign_approval(campaign, recs, config)
        self.assertTrue(campaigns.approval_is_current(campaign, recs, config))
        handles["clock"].advance(days=1)
        timeline = cadence.build(rec, config, recs=recs,
                                 campaign=campaign).get("contacts") or {}
        contact = rec["contacts"][0]
        running = eligibility.decide(rec, contact, "li1", campaign=campaign,
                                     recs=recs, config=config, day=1,
                                     timeline=timeline)
        self.assertEqual(running["verdict"], eligibility.ELIGIBLE,
                         running["reasons"])
        campaigns.set_status(campaign, campaigns.PAUSED, why="test")
        paused = eligibility.decide(rec, contact, "li1", campaign=campaign,
                                    recs=recs, config=config, day=1,
                                    timeline=timeline)
        self.assertEqual(paused["verdict"], eligibility.BLOCKED)
        self.assertIn(eligibility.BLOCKED_CAMPAIGN_STOPPED, paused["reasons"])


# ============================================= transient provider failure

class ATransientProviderErrorLosesNothing(SandboxCase):

    def test_the_checkpoint_does_not_move_and_the_row_arrives_later(self):
        from src import poller, replywatch

        config = clients.load("productive")
        handles = self.boot()
        clock = handles["clock"]
        recs, _blob = sandbox_run.load_fixture(1)
        recs = recs[:1]
        sandbox_run.install_phase5_copy(recs, config)
        store.save(recs)
        contact = recs[0]["contacts"][0]
        fake_bison = sandbox_run.FakeBison(clock)
        fake_bison.rows = [sandbox_run.bison_row(
            recs[0]["id"], recs[0]["client"], contact["key"],
            contact["email"], 0, "reply", sandbox_run.EXPLICIT_REMOVAL)]
        fake_bison.fail_on_days = {0}
        undo = sandbox_run.install_fake_providers(
            fake_bison, sandbox_run.FakeHeyReach(clock))
        self.addCleanup(undo)

        failed = replywatch.poll_once("emailbison", max_pages=1, live=True,
                                      env=sandbox_run.SANDBOX_ENV,
                                      now=clock.now_iso())
        self.assertFalse(failed["healthy"], failed)
        # `poller.with_retry` exhausts MAX_ATTEMPTS and re-raises as PollError,
        # which is what `replywatch.poll_once` records. Asserting the wrapper's
        # own words rather than the inner class is what makes this a test of
        # the real retry path.
        self.assertIn("gave up after 3 attempt", failed["last_error"])
        self.assertIn("simulated transient 502", failed["last_error"])
        self.assertIsNone(poller.cursor_for("emailbison", "ws10"))
        self.assertGreaterEqual(fake_bison.failures_raised, 1)
        self.assertFalse(any(c.get("unsubscribed")
                             for c in store.load()[0]["contacts"]))

        # The failure was transient: the same row is re-read and applied.
        fake_bison.fail_on_days = set()
        clock.advance(days=1)
        ok = replywatch.poll_once("emailbison", max_pages=1, live=True,
                                  env=sandbox_run.SANDBOX_ENV,
                                  now=clock.now_iso())
        self.assertTrue(ok["healthy"], ok)
        self.assertEqual(ok["new_replies_ingested"], 1)
        self.assertTrue(any(c.get("unsubscribed")
                            for c in store.load()[0]["contacts"]))


# =============================================== ledgers, resume, determinism

class LedgerComparisonCanFail(SandboxCase):
    """The comparison used for resume accuracy and for determinism."""

    LEDGER = [("r1", "c1", "push_marked", "em1", "email", "T1", "i1"),
              ("r1", "c1", "push_marked", "li1", "linkedin", "T1", "i2")]

    def test_identical_ledgers_agree(self):
        report = sandbox_run.compare_ledgers(self.LEDGER, list(self.LEDGER))
        self.assertTrue(report["no_lost_state"])
        self.assertTrue(report["no_duplicated_events"])

    def test_a_lost_row_is_detected_control(self):
        report = sandbox_run.compare_ledgers(self.LEDGER, self.LEDGER[:1])
        self.assertFalse(report["no_lost_state"])
        self.assertEqual(report["lost_count"], 1)

    def test_a_duplicated_row_is_detected_control(self):
        report = sandbox_run.compare_ledgers(
            self.LEDGER, self.LEDGER + [self.LEDGER[0]])
        self.assertFalse(report["no_duplicated_events"])
        self.assertEqual(report["duplicated_rows"], 1)

    def test_the_state_signature_moves_when_state_moves_control(self):
        recs, _blob = sandbox_run.load_fixture(1)
        recs = recs[:3]
        first = sandbox_run.state_signature(recs)
        recs[0]["contacts"][0]["unsubscribed"] = True
        second = sandbox_run.state_signature(recs)
        self.assertNotEqual(first["md5"], second["md5"])

    def test_the_state_signature_ignores_record_order(self):
        recs, _blob = sandbox_run.load_fixture(1)
        recs = recs[:3]
        self.assertEqual(sandbox_run.state_signature(recs)["md5"],
                         sandbox_run.state_signature(
                             list(reversed(recs)))["md5"])


def _run_sandbox(args, expect=0):
    """A sandbox run in a SUBPROCESS, because a kill cannot be tested in the
    process doing the asserting - `os._exit` would take the test runner."""
    proc = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, "sandbox_run.py")] + args,
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace")
    if proc.returncode != expect:
        raise AssertionError(
            "sandbox_run %s exited %d, expected %d\nSTDOUT\n%s\nSTDERR\n%s"
            % (" ".join(args), proc.returncode, expect, proc.stdout[-4000:],
               proc.stderr[-4000:]))
    return proc


class KillAndResume(SandboxCase):
    """Run-order item (ii): kill after a checkpoint, resume, prove no loss and
    no duplicates. A real `os._exit`, in a real second process."""

    DAYS = 18
    EVERY = 6
    KILL_AFTER = 11
    COMPANIES = 6

    def setUp(self):
        super().setUp()
        self.out = os.path.join(self.tmp, "run")
        self.common = ["--out", self.out, "--seed", "1",
                       "--companies", str(self.COMPANIES),
                       "--days", str(self.DAYS),
                       "--checkpoint-every", str(self.EVERY), "--quiet"]

    def test_the_kill_resumes_with_no_lost_state_and_no_duplicates(self):
        _run_sandbox(self.common + ["--kill-after-day",
                                    str(self.KILL_AFTER)],
                     expect=sandbox_run.KILL_EXIT_CODE)
        checkpoint = sandbox_run.read_checkpoint(
            os.path.join(self.out, "sandbox", "checkpoint.json"))
        self.assertEqual(checkpoint["day_index"], self.KILL_AFTER)
        before = [tuple(row) for row in checkpoint["ledger"]]
        self.assertGreater(len(before), 0)

        proc = _run_sandbox(self.common + ["--resume", "--json"])
        report = json.loads(proc.stdout[proc.stdout.index("{"):])
        self.assertEqual(report["resumed_from"], self.KILL_AFTER)
        self.assertEqual(report["days_simulated"],
                         self.DAYS - self.KILL_AFTER - 1)

        with open(os.path.join(self.out, "sandbox", "ledger.json"),
                  encoding="utf-8") as handle:
            after = [tuple(row) for row in json.load(handle)]
        comparison = sandbox_run.compare_ledgers(before, after)
        self.assertTrue(comparison["no_lost_state"], comparison["lost"])
        self.assertTrue(comparison["no_duplicated_events"], comparison)
        self.assertGreater(comparison["gained_count"], 0,
                           "the resumed half did nothing, so this proves "
                           "nothing about resuming")

    def test_the_comparison_would_catch_a_loss_control(self):
        """Guards the test above with the same checker on a poisoned input."""
        before = [("r", "c", "push_marked", "em1", "email", "T", "i")]
        self.assertFalse(
            sandbox_run.compare_ledgers(before, [])["no_lost_state"])

    def test_an_explicit_removal_survives_the_resume_boundary(self):
        """THE NAMED PASS CRITERION: an opt-out prevents every subsequent
        contact, INCLUDING AFTER A RESUME.

        The removal cohort is scheduled on simulated days 14-19, which this
        configuration crosses AFTER the kill at day 11 - so the suppression is
        written by the RESUMED process and then has to hold for the rest of
        the run.
        """
        _run_sandbox(self.common + ["--kill-after-day",
                                    str(self.KILL_AFTER)],
                     expect=sandbox_run.KILL_EXIT_CODE)
        proc = _run_sandbox(self.common + ["--resume", "--json"])
        report = json.loads(proc.stdout[proc.stdout.index("{"):])
        audit = report["removal_audit"]
        self.assertGreater(audit["ingested"], 0,
                           "no removal reply was ingested, so this test "
                           "proves nothing: %r" % (audit,))
        self.assertEqual(audit["ingested"], audit["unsubscribed"])
        self.assertEqual(audit["ingested"], audit["refused_by_eligibility"])
        self.assertEqual(audit["pushes_after_removal"], 0)
        self.assertTrue(audit["all_prevented"], audit)

    def test_the_removal_audit_can_fail_control(self):
        """Guards the criterion above: `all_prevented` must be falsifiable."""
        rec = {"id": "r", "client": "productive", "state": "approved",
               "contacts": [{"key": "c", "email": "a@b.invalid"}],
               "events": [{"type": "reply_received", "contact": "c",
                           "at": "2026-10-20T06:00:00+00:00"},
                          {"type": "push_marked", "contact": "c",
                           "at": "2026-10-21T06:00:00+00:00"}]}
        plan = {"r": {"removal": {"contact": "c", "day": 14}}}
        audit = sandbox_run.removal_audit([rec], plan)
        self.assertEqual(audit["ingested"], 1)
        self.assertFalse(audit["rows"][0]["unsubscribed"])
        self.assertEqual(audit["rows"][0]["pushes_after_removal"], 1)
        self.assertFalse(audit["all_prevented"])


class TwoRunsWithTheSameSeedAgree(SandboxCase):
    """Run-order item (iv). Normalised event ledger and final state."""

    ARGS = ["--seed", "1", "--companies", "4", "--days", "8",
            "--checkpoint-every", "4", "--quiet", "--json"]

    def _run(self, name, extra=()):
        out = os.path.join(self.tmp, name)
        proc = _run_sandbox(["--out", out] + self.ARGS + list(extra))
        report = json.loads(proc.stdout[proc.stdout.index("{"):])
        with open(os.path.join(out, "sandbox", "ledger.json"),
                  encoding="utf-8") as handle:
            ledger = [tuple(row) for row in json.load(handle)]
        return report, ledger

    def test_the_ledger_and_the_signature_match(self):
        first_report, first_ledger = self._run("a")
        second_report, second_ledger = self._run("b")
        self.assertEqual(first_ledger, second_ledger)
        self.assertEqual(first_report["signature"], second_report["signature"])
        self.assertEqual(first_report["pushed_total"],
                         second_report["pushed_total"])
        self.assertGreater(len(first_ledger), 0,
                           "an empty ledger would match itself trivially")

    def test_a_different_seed_disagrees_control(self):
        """Guards the test above: equality must be falsifiable."""
        _report, first_ledger = self._run("c")
        out = os.path.join(self.tmp, "d")
        proc = _run_sandbox(["--out", out, "--seed", "2", "--companies", "4",
                             "--days", "8", "--checkpoint-every", "4",
                             "--quiet", "--json"])
        json.loads(proc.stdout[proc.stdout.index("{"):])
        with open(os.path.join(out, "sandbox", "ledger.json"),
                  encoding="utf-8") as handle:
            other = [tuple(row) for row in json.load(handle)]
        self.assertNotEqual(first_ledger, other)


# ============================================ the production flow is unchanged

class TheProductionFlowIsUnchanged(unittest.TestCase):

    def _git(self, *args):
        return subprocess.run(["git"] + list(args), cwd=ROOT,
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace")

    def test_src_is_identical_to_the_fork_point(self):
        proc = self._git("diff", "--stat", BASE_COMMIT, "--", "src/")
        self.assertEqual(proc.returncode, 0,
                         "cannot resolve %s: %s"
                         % (BASE_COMMIT, proc.stderr.strip()[:300]))
        self.assertEqual(proc.stdout.strip(), "",
                         "src/ changed; the sandbox drives the flow and does "
                         "not modify it:\n%s" % proc.stdout)

    def test_the_diff_check_can_detect_a_change_control(self):
        """Guards the test above: an empty diff must be falsifiable, by the
        SAME command on a directory that really did change."""
        proc = self._git("diff", "--stat", BASE_COMMIT, "--", "scripts/")
        self.assertEqual(proc.returncode, 0, proc.stderr[:300])
        self.assertIn("sandbox_run.py", proc.stdout,
                      "scripts/ must differ from the fork point - this "
                      "file's own runner lives there")

    def test_nothing_in_src_imports_the_sandbox(self):
        """The seams are inert: the production flow does not know they exist."""
        import re

        offenders = []
        pattern = re.compile(r"\b(sandboxclock|sandboxharness|sandbox_run)\b")
        for folder, dirs, files in os.walk(os.path.join(ROOT, "src")):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in files:
                if not name.endswith(".py") or name.startswith("sandbox"):
                    continue
                path = os.path.join(folder, name)
                with open(path, encoding="utf-8", errors="replace") as handle:
                    for i, line in enumerate(handle, 1):
                        if pattern.search(line) and "import" in line:
                            offenders.append("%s:%d %s"
                                             % (path, i, line.strip()))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
