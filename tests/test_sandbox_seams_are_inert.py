"""The phase-2 seams change nothing until something calls them.

The operator's constraint on this work is that the production flow is NOT
changed, and that any seam added for the sandbox is "minimal, additive and
behaviour-neutral by default". That is a claim, and a claim needs evidence,
so this module is the evidence.

Four properties, each with a positive control. The controls matter more than
the assertions here: "nothing imports this module" is a zero, and a zero that
has never been shown able to be non-zero is silence rather than a result.
"""
import datetime
import importlib
import os
import unittest

from src import sandboxclock, sandboxharness, store

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")


def _importers_of(module_name, root=SRC):
    """Files under `root` whose AST imports `module_name`.

    AST rather than grep, for the reason CLAUDE.md gives: searching source for
    words produces a test that fails when somebody writes a comment. An import
    is structure; a mention is not.
    """
    import ast

    out = []
    for folder, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(folder, name)
            try:
                with open(path, encoding="utf-8") as handle:
                    tree = ast.parse(handle.read(), filename=path)
            except (OSError, SyntaxError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[-1] == module_name:
                            out.append(path)
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if alias.name == module_name:
                            out.append(path)
    return sorted(set(out))


class TheProductionFlowDoesNotImportTheSeams(unittest.TestCase):
    """Nothing in the flow reaches these modules, so they cannot change it."""

    def test_no_production_module_imports_sandboxclock(self):
        self.assertEqual(
            [], _importers_of("sandboxclock"),
            "a production module imports sandboxclock, so the clock seam is "
            "no longer additive")

    def test_no_production_module_imports_sandboxharness(self):
        self.assertEqual(
            [], _importers_of("sandboxharness"),
            "a production module imports sandboxharness, so the isolation "
            "seam is no longer additive")

    def test_the_importer_scan_can_actually_find_an_import(self):
        """POSITIVE CONTROL for both tests above.

        Without this, the two zeros are indistinguishable from a scanner that
        walks the wrong directory or silently swallows every parse error -
        which is exactly how this repository has produced a false clean
        before.
        """
        found = _importers_of("store")
        self.assertTrue(
            found,
            "the scanner found NO importer of `store`, which cannot be true; "
            "the two zeros above therefore prove nothing")
        self.assertTrue(any(p.endswith("simulator.py") for p in found),
                        "expected src/simulator.py among store's importers")


class ImportingTheSeamsHasNoSideEffect(unittest.TestCase):
    """Import must not patch, seal, or move anything."""

    def test_store_now_is_untouched_by_import(self):
        before = store.now
        importlib.reload(sandboxclock)
        self.assertIs(store.now, before,
                      "importing sandboxclock replaced store.now")

    def test_store_now_still_returns_the_real_clock(self):
        now = store.now()
        year = datetime.datetime.now(datetime.timezone.utc).year
        self.assertTrue(
            str(now).startswith(str(year)),
            "store.now() does not look like the real clock after import: %r"
            % (now,))

    def test_the_transport_is_untouched_by_import(self):
        from src import providers
        importlib.reload(sandboxharness)
        self.assertIs(
            providers._transport, providers._urllib_transport,
            "importing sandboxharness replaced the transport; a module that "
            "seals the wire on import would break every production call")


class TheClockOnlyMovesWhenAsked(unittest.TestCase):
    """`install` is explicit and reversible, and nothing else advances time."""

    def setUp(self):
        self.clock = sandboxclock.SimClock(
            datetime.datetime(2026, 10, 20, 6, 0,
                              tzinfo=datetime.timezone.utc))

    def test_install_then_undo_restores_the_real_clock(self):
        original = store.now
        undo = sandboxclock.install(self.clock)
        try:
            self.assertEqual(store.now(), self.clock.now_iso())
            self.assertIsNot(store.now, original)
        finally:
            undo()
        self.assertIs(store.now, original,
                      "undo did not restore store.now")

    def test_reading_the_clock_does_not_advance_it(self):
        """A read that moved time would make two unrelated reads order-
        dependent, which silently changes every answer downstream."""
        first = self.clock.now()
        for _ in range(5):
            self.clock.now()
            self.clock.now_iso()
            self.clock.local()
        self.assertEqual(first, self.clock.now())

    def test_the_clock_refuses_to_run_backwards(self):
        with self.assertRaises(ValueError):
            self.clock.advance(days=-1)

    def test_a_naive_start_is_refused(self):
        """A naive datetime cannot answer a daylight-saving question."""
        with self.assertRaises(ValueError):
            sandboxclock.SimClock(datetime.datetime(2026, 10, 20, 6, 0))


class TheDstBoundaryIsRealAndIsCrossed(unittest.TestCase):
    """The 2026-10-25 Europe/Zagreb step is computed, not tabulated."""

    def test_the_october_transition_is_found_by_walking(self):
        start = datetime.datetime(2026, 10, 1, tzinfo=datetime.timezone.utc)
        end = datetime.datetime(2026, 11, 5, tzinfo=datetime.timezone.utc)
        steps = sandboxclock.dst_transitions(start, end)
        self.assertEqual(
            1, len(steps),
            "expected exactly one Europe/Zagreb transition in Oct 2026, got %r"
            % (steps,))
        at, before, after = steps[0]
        self.assertEqual("2026-10-25", at.date().isoformat())
        self.assertEqual(2.0, before)
        self.assertEqual(1.0, after)

    def test_advancing_across_it_reports_the_crossing(self):
        clock = sandboxclock.SimClock(
            datetime.datetime(2026, 10, 24, 12, 0,
                              tzinfo=datetime.timezone.utc))
        self.assertEqual(2.0, clock.utc_offset_hours())
        crossed = clock.advance(days=1)
        self.assertEqual(1.0, clock.utc_offset_hours())
        self.assertTrue(any(c.startswith("dst_change") for c in crossed),
                        "crossing the DST step was not reported: %r" % crossed)
        self.assertIn("utc_day_boundary", crossed)

    def test_a_window_with_no_transition_reports_none(self):
        """POSITIVE CONTROL in the other direction: the walker must be able
        to answer zero, or 'one transition' above is not a measurement."""
        start = datetime.datetime(2026, 11, 5, tzinfo=datetime.timezone.utc)
        end = datetime.datetime(2026, 12, 5, tzinfo=datetime.timezone.utc)
        self.assertEqual([], sandboxclock.dst_transitions(start, end))


class TheRealElapsedClockIsDeliberatelyNotFaked(unittest.TestCase):
    """The queue lock must keep ticking in real time."""

    def test_install_does_not_touch_time_monotonic(self):
        import time
        before = time.monotonic
        undo = sandboxclock.install(self.clock_or_new())
        try:
            self.assertIs(
                time.monotonic, before,
                "the simulated clock replaced time.monotonic; the queue lock "
                "deadline would then never expire or would expire instantly")
        finally:
            undo()

    def test_the_exemptions_are_named(self):
        """The omission has to be visible, so a future patch cannot quietly
        add these without this list disagreeing."""
        names = {entry[0] for entry in sandboxclock.REAL_ELAPSED_EXEMPT}
        self.assertIn("src/store.py", names)
        self.assertTrue(
            any("suitelock" in n for n in names),
            "the suite lock's real-elapsed reads are not recorded as exempt")

    def clock_or_new(self):
        return sandboxclock.SimClock(
            datetime.datetime(2026, 10, 20, 6, 0,
                              tzinfo=datetime.timezone.utc))


class TheWireSealIsProvenToFire(unittest.TestCase):
    """A seal that has never stopped anything is not a seal."""

    def test_a_total_seal_refuses_a_deliberate_call(self):
        undo, calls = sandboxharness.seal_wire(allow=())
        try:
            self.assertTrue(sandboxharness.assert_wire_sealed())
            self.assertTrue(calls, "the attempted call was not logged")
        finally:
            undo()

    def test_the_seal_is_removed_again(self):
        from src import providers
        undo, _calls = sandboxharness.seal_wire(allow=())
        undo()
        self.assertIs(providers._transport, providers._urllib_transport)

    def test_assert_wire_sealed_fails_when_the_wire_is_open(self):
        """POSITIVE CONTROL: the assertion must be able to fail.

        Stubs the transport with something that SUCCEEDS, which is what an
        unsealed wire looks like from here, and requires the assertion to
        complain rather than pass.
        """
        from src import providers
        previous = providers.set_transport(
            lambda *_a, **_k: (200, '{"ok": true}'))
        try:
            with self.assertRaises(AssertionError):
                sandboxharness.assert_wire_sealed()
        finally:
            providers.set_transport(previous)


class TheProductionAssertionCanFail(unittest.TestCase):
    """The isolation guarantee is only worth the control behind it."""

    def test_an_unchanged_window_passes(self):
        before = sandboxharness.production_fingerprint()
        self.assertTrue(sandboxharness.assert_production_unchanged(before))

    def test_a_changed_fingerprint_is_caught(self):
        """POSITIVE CONTROL. Mutates the recorded fingerprint rather than the
        real file - the production file is exactly what must not be touched."""
        before = sandboxharness.production_fingerprint()
        tampered = {k: (dict(v) if v else v) for k, v in before.items()}
        target = next(k for k, v in tampered.items() if v)
        tampered[target]["md5"] = "0" * 32
        with self.assertRaises(sandboxharness.ProductionTouched):
            sandboxharness.assert_production_unchanged(tampered, before)

    def test_a_vanishing_file_is_caught_rather_than_read_as_equal(self):
        before = sandboxharness.production_fingerprint()
        target = next(k for k, v in before.items() if v)
        after = dict(before)
        after[target] = None
        with self.assertRaises(sandboxharness.ProductionTouched):
            sandboxharness.assert_production_unchanged(before, after)

    def test_production_files_must_exist_for_the_claim_to_mean_anything(self):
        self.assertTrue(sandboxharness.assert_production_exists())


class SyntheticDomainsAreRecognised(unittest.TestCase):
    def test_invalid_and_example_are_synthetic(self):
        self.assertTrue(sandboxharness.is_synthetic_domain("foo.invalid"))
        self.assertTrue(sandboxharness.is_synthetic_domain("example.com"))

    def test_a_real_looking_domain_is_not(self):
        self.assertFalse(sandboxharness.is_synthetic_domain("acme.com"))
        self.assertFalse(sandboxharness.is_synthetic_domain("productive.io"))

    def test_the_real_client_domain_list_is_not_empty(self):
        """POSITIVE CONTROL for the both-direction fixture assertion: if this
        set were empty, "no real client domain is in the fixture" would be a
        test that cannot fail."""
        domains = sandboxharness.real_client_domains()
        self.assertTrue(
            domains,
            "no real client domains were loaded, so the fixture's "
            "no-real-domain assertion would be vacuous")


if __name__ == "__main__":
    unittest.main()
