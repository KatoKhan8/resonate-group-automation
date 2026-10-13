"""The clock scanner's own controls. C11's pre-registered prerequisites.

WHY THIS MODULE EXISTS
======================
The 2026-10-13 sandbox run was HELD on C11, and the pre-registration in
`resonate-ops/PREREG-C11-wall-clock-2026-10-13.md` names three controls that
must pass BEFORE any further run may be labelled anything:

  1. the scanner fires on all four spellings of the injectable idiom
     (the regex scanner fired on ONE)
  2. `def _utcnow():` is NOT reported as a clock read
  3. a deliberately added unpatched read inside a `SIMULATED_PATH_MODULES`
     module is caught

A scanner that cannot see three of four spellings cannot be used to certify
that they are absent, which is why these are prerequisites rather than extras.

THE MEASURED DEFECT IN THE OLD INSTRUMENT, KEPT AS EVIDENCE
===========================================================
`sandboxclock.unpatched_business_clock_reads` is retained unchanged and is
NOT to be used for a verdict. `report_disagreement` shows why in numbers, and
`TheTwoInstrumentsDisagreeInTheMeasuredWay` pins that difference so the old
one cannot quietly come back into use as an authority.

AND THIS MODULE'S OWN FIRST DRAFTS WERE WRONG TWICE, BOTH CAUGHT HERE
=====================================================================
Recorded because the pattern matters more than the fix:

  * `INJECTABLE_PARAMS` was first written from memory as
    `("now","today","at","as_of")` - carrying `as_of`, which no site in `src/`
    uses, while omitting `on_date`, which three sites in `nightlysourcing`
    use. Three injectable reads were therefore reported as unpatched defects.
    The list is now MEASURED off `src/`.
  * the helper-call rule first promoted every call to a local clock helper to
    `unpatched`, which swept in the four `store.now()` calls inside
    `store.py` - and `store.now` is the PATCHED SEAM. The instrument was
    reporting the fix as the defect. Calls to a seam are now skipped and
    other helper calls are `INDIRECT`, counted once in the helper body.
"""
import importlib.util
import os
import tempfile
import textwrap
import unittest

from src import sandboxclock as REGEX_SCANNER


def _load_scanner():
    """`scripts/clockscan.py` as a module.

    Loaded from disk because `scripts/` is not a package. The scanner
    lives there and NOT in `src/` because this branch asserts
    `git diff <fork> -- src/` is empty - a first draft of it was put in
    `src/sandboxclock.py` and `test_src_is_identical_to_the_fork_point`
    refused it, correctly.
    """
    spec = importlib.util.spec_from_file_location(
        "_clockscan", "scripts/clockscan.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SC = _load_scanner()


#: The four spellings of the injectable idiom that `src/` actually contains.
#: Each is a real shape, not a hypothetical: the assign form is in
#: `executionguard`, the return form in `spendledger.today`, the helper form
#: in `executionguard` three times, the guard form in `copylint`.
FOUR_SPELLINGS = (
    ("assign", """
        def f(now=None):
            x = now or datetime.datetime.now(datetime.timezone.utc)
            return x
    """),
    ("return", """
        def f(now=None):
            return (now or datetime.datetime.now(datetime.timezone.utc)).date()
    """),
    ("helper", """
        def _utcnow():
            return datetime.datetime.now(datetime.timezone.utc)

        def f(now=None):
            age = ((now or _utcnow()) - 0)
            return age
    """),
    ("guard", """
        def f(today=None):
            if today is None:
                today = datetime.date.today()
            return today
    """),
)


def _scan_source(source, filename="probe.py"):
    """Write one module into a throwaway tree and scan only it."""
    folder = tempfile.mkdtemp(prefix="clockscan-")
    path = os.path.join(folder, filename)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("import datetime\n\n" + textwrap.dedent(source))
    return SC.clock_reads(root=folder, only={filename}), path


class TheScannerSeesAllFourSpellingsOfTheIdiom(unittest.TestCase):
    """CONTROL 1 of the pre-registration."""

    def test_every_spelling_is_classified_injectable(self):
        wrong = {}
        for label, source in FOUR_SPELLINGS:
            rows, _path = _scan_source(source)
            injectable = [r for r in rows
                          if r["disposition"] == SC.INJECTABLE]
            if not injectable:
                wrong[label] = [(r["line"], r["disposition"]) for r in rows]
        self.assertEqual(
            {}, wrong,
            "the scanner failed to recognise the injectable idiom in these "
            "spellings, so it cannot certify that they are absent: %r"
            % (wrong,))

    def test_the_old_regex_instrument_fails_this_same_control(self):
        """NEGATIVE CONTROL, and the reason the old scanner is not an
        authority. It must recognise exactly ONE of the four. If it ever
        recognises more, this test is the thing to update - not the verdict
        that was taken with it."""
        seen = {}
        for label, source in FOUR_SPELLINGS:
            line = textwrap.dedent(source)
            seen[label] = bool(REGEX_SCANNER._INJECTABLE_IDIOM.search(line))
        self.assertEqual(
            {"assign": True, "return": False, "helper": False,
             "guard": False}, seen,
            "the regex instrument's measured blind spots have changed: %r"
            % (seen,))


class ADefinitionLineIsNotAClockRead(unittest.TestCase):
    """CONTROL 2 of the pre-registration."""

    SOURCE = """
        def _utcnow():
            return datetime.datetime.now(datetime.timezone.utc)
    """

    def test_the_def_line_is_not_reported(self):
        rows, _path = _scan_source(self.SOURCE)
        on_def = [r for r in rows if r["source"].startswith("def ")]
        self.assertEqual(
            [], on_def,
            "a function signature was reported as a clock read: %r" % (on_def,))

    def test_the_helper_body_is_reported_once(self):
        """The body IS a read and must still be seen - otherwise control 2
        could be satisfied by a scanner that sees nothing."""
        rows, _path = _scan_source(self.SOURCE)
        bodies = [r for r in rows if r["disposition"] == SC.HELPER_BODY]
        self.assertEqual(1, len(bodies), "rows: %r" % (rows,))

    def test_the_old_regex_instrument_reports_the_def_line(self):
        """NEGATIVE CONTROL: the defect being fixed, pinned."""
        self.assertTrue(
            REGEX_SCANNER._CLOCK_RX["utcnow"].search("def _utcnow():"),
            "the regex no longer matches a definition line; the measured "
            "defect has changed and the C11 record needs updating")


class ADeliberateUnpatchedReadIsCaught(unittest.TestCase):
    """CONTROL 3 of the pre-registration: the zero must be falsifiable."""

    #: A read with NO injectable parameter, inside a file named as one of the
    #: simulated-path modules. This is the shape C11a claims is absent.
    SOURCE = """
        def decide(rec, contact):
            cutoff = datetime.datetime.now(datetime.timezone.utc)
            return cutoff
    """

    def test_an_added_read_in_a_named_module_is_reported_unpatched(self):
        rows, _path = _scan_source(self.SOURCE, filename="eligibility.py")
        unpatched = [r for r in rows if r["disposition"] == SC.UNPATCHED]
        self.assertEqual(
            1, len(unpatched),
            "a deliberately added unpatched read in a SIMULATED_PATH_MODULES "
            "module was not reported, so C11a's zero is not falsifiable: %r"
            % (rows,))
        self.assertEqual("decide", unpatched[0]["function"])

    def test_the_real_named_set_holds_no_unpatched_read(self):
        """C11a itself, over the real tree, with control 3 above as its
        falsifiability proof."""
        rows = SC.clock_reads(only=SC.SIMULATED_PATH_MODULES)
        unpatched = [r for r in rows if r["disposition"] == SC.UNPATCHED]
        self.assertEqual(
            [], unpatched,
            "unpatched business-clock reads inside the named simulated-path "
            "modules: %r" % (unpatched,))

    def test_the_named_set_is_not_empty_control(self):
        """And the named scan must actually read something, or the zero above
        is silence rather than a result."""
        rows = SC.clock_reads(only=SC.SIMULATED_PATH_MODULES)
        self.assertGreater(
            len(rows), 0,
            "the named-module scan returned nothing at all, so C11a is "
            "vacuous")


class TheTwoInstrumentsDisagreeInTheMeasuredWay(unittest.TestCase):
    """Pins the difference so the superseded scanner cannot become an
    authority again by accident."""

    def test_the_disagreement_is_the_one_recorded(self):
        report = SC.report_disagreement(only=None)
        self.assertTrue(report["regex_reports_a_def_line"])
        self.assertFalse(report["ast_reports_a_def_line"])
        self.assertGreater(report["ast_rows"], 0)
        self.assertGreater(report["regex_rows"], 0)
        # The AST instrument must DISPOSE of every row it reports; a row with
        # no disposition is the thing C11c forbids.
        rows = SC.clock_reads(only=None)
        undisposed = [r for r in rows if not r.get("disposition")]
        self.assertEqual([], undisposed, "rows with no disposition: %r"
                         % (undisposed,))

    def test_every_disposition_is_one_of_the_declared_set(self):
        declared = {SC.UNPATCHED, SC.INJECTABLE, SC.HELPER_BODY,
                    SC.MODULE_LEVEL, SC.EXEMPT, SC.INDIRECT}
        rows = SC.clock_reads(only=None)
        seen = {r["disposition"] for r in rows}
        self.assertTrue(
            seen <= declared,
            "a disposition outside the declared set appeared: %r"
            % (sorted(seen - declared),))
        self.assertGreater(len(seen), 1,
                           "only one disposition in the whole tree, which "
                           "means the classifier is not classifying")


class ModuleLevelReadsAreNamedBecauseTheyCannotBeInjected(unittest.TestCase):
    """C11d's subject, measured rather than asserted."""

    def test_the_module_level_reads_are_exactly_the_two_measured(self):
        rows = SC.clock_reads(only=None)
        module_level = sorted(
            (os.path.basename(r["file"]), r["line"]) for r in rows
            if r["disposition"] == SC.MODULE_LEVEL)
        self.assertEqual(
            [("demo.py", 20), ("secondbrain.py", 32)], module_level,
            "the set of import-time clock constants has MOVED. These cannot "
            "be injected at all, so each one is a horizon defect until it is "
            "removed or declared: %r" % (module_level,))

    def test_a_module_level_read_is_never_injectable(self):
        """CONTROL: the classifier must not call a module-level read
        injectable just because the module has a function with a `now`
        parameter somewhere."""
        rows, _path = _scan_source("""
            TODAY = datetime.date.today().isoformat()

            def f(now=None):
                return now
        """)
        levels = [r["disposition"] for r in rows]
        self.assertIn(SC.MODULE_LEVEL, levels, "rows: %r" % (rows,))


if __name__ == "__main__":
    unittest.main()
