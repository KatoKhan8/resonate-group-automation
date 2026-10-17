"""The four adoption conditions of the cross-witness pin check (qwen-coder/0190)
are each LOAD-BEARING in the reference implementation (qwen-coder/0220):
removing exactly one condition moves at least one verdict on a synthetic
fixture. Also asserted: the zero-digest-marker spoof shape fails CLOSED
(REFUSE with an UNPARSEABLE detail, never ACCEPT), a legitimate re-pin still
ACCEPTs (the check is not a refuse-machine), and unreadable input is NEITHER
(a crash is never a verdict).

Hermetic by construction: every fixture is synthetic bytes in a temporary
directory, the implementation is exec'd from its source bytes (no bytecode
cache, no import side effects), and nothing outside the repository is read.
Honest limit, carried from 0190: both witnesses are agent-writable; the check
converts silent concurrent mutation into an auditable lane event; it is NOT a
root of trust.
"""
import hashlib
import os
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_PATH = os.path.join(ROOT, "scripts", "cross_witness_ref.py")
ANCHOR = "TASK synthetic/0001"


def _load_check():
    with open(SRC_PATH, "rb") as f:
        src = f.read()
    ns = {"__name__": "cross_witness_ref_under_test"}
    exec(compile(src, "cross_witness_ref.py", "exec"), ns)
    return ns["cross_witness_check"]


CROSS = _load_check()

INSTRUMENT = b"# synthetic instrument for the cross-witness reference tests\n"
HEADER = "## 2026-10-17 - " + ANCHOR + " - synthetic test entry"


def record_line(digest, tail="by the test - synthetic"):
    return "`%s` (pin recorded to `pin.txt` %s)" % (digest, tail)


def prose_marker_line(n):
    return ("a prose sentence quoting the marker (pin recorded to with zero "
            "backticked digests (line %d, synthetic)" % n)


def filler(n):
    return "filler line %d - synthetic, no marker text, no digests" % n


class CrossWitnessRefBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.digest = hashlib.sha256(INSTRUMENT).hexdigest()

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, name, data):
        p = os.path.join(self.dir, name)
        with open(p, "wb") as f:
            f.write(data)
        return p

    def fixture(self, lane_lines, instrument=INSTRUMENT, pin_digest=None):
        ip = self._write("instrument.py", instrument)
        pp = self._write("pin.txt",
                         (pin_digest or hashlib.sha256(instrument).hexdigest()
                          ).encode("ascii"))
        lp = self._write("lane.md",
                         ("\n".join(lane_lines) + "\n").encode("utf-8"))
        return (ip, pp, lp)

    def run_check(self, paths, **kwargs):
        log = []
        kwargs.setdefault("anchor", ANCHOR)
        verdict, detail, values = CROSS(*paths, log.append, **kwargs)
        return verdict, detail, values, log

    def pristine_doc(self):
        return [HEADER, "", record_line(self.digest), "", filler(5), ""]


class TestAdoptedBehaviour(CrossWitnessRefBase):
    def test_pristine_three_way_agreement_accepts(self):
        v, d, vals, _ = self.run_check(self.fixture(self.pristine_doc()))
        self.assertEqual(v, "ACCEPT")
        self.assertEqual(vals["lane_effective"], self.digest)
        self.assertEqual(vals["lane_line"], 3)
        self.assertIn("both witnesses agree", d)

    def test_co_mutation_pin_and_bytes_alone_refuse(self):
        # pin rewritten to agree with mutated bytes; the landed record still
        # carries the old digest -> the lane witness refuses (0190 arm 2).
        mutated = INSTRUMENT + b"# co-mutated\n"
        v, d, _, _ = self.run_check(
            self.fixture(self.pristine_doc(), instrument=mutated))
        self.assertEqual(v, "REFUSE")
        self.assertIn("lane entry witness line 3", d)

    def test_pin_only_rewrite_refuses_naming_the_pin_witness(self):
        # 0190 arm 4 shape: measured == lane != pin (the entry-before-pin
        # interruption direction B).
        fake = hashlib.sha256(b"SYNTHETIC-PIN-ONLY-TEST").hexdigest()
        v, d, _, _ = self.run_check(
            self.fixture(self.pristine_doc(), pin_digest=fake))
        self.assertEqual(v, "REFUSE")
        self.assertIn("pin file witness", d)

    def test_lane_only_rewrite_refuses_naming_the_lane_witness(self):
        # 0190 arm 5 shape: measured == pin != lane.
        doc = [HEADER, "", record_line(
            hashlib.sha256(b"SYNTHETIC-LANE-ONLY-TEST").hexdigest()), ""]
        v, d, _, _ = self.run_check(self.fixture(doc))
        self.assertEqual(v, "REFUSE")
        self.assertIn("lane entry witness line 3", d)

    def test_legit_repin_latest_record_wins_and_accepts(self):
        # 0190 arm 6 shape: new bytes + pin updated + NEW record appended in a
        # new entry AFTER the anchor; latest record wins -> ACCEPT, not a
        # refuse-machine.
        new_instr = INSTRUMENT + b"# legitimately re-pinned\n"
        new_digest = hashlib.sha256(new_instr).hexdigest()
        doc = [HEADER, "", record_line(self.digest), "",
               "## SIMULATED-RE-PIN-ENTRY (synthetic)", "",
               record_line(new_digest, "by the re-pin task - synthetic"), ""]
        v, d, vals, _ = self.run_check(
            self.fixture(doc, instrument=new_instr, pin_digest=new_digest))
        self.assertEqual(v, "ACCEPT")
        self.assertEqual(vals["record_lines"], [3, 7])
        self.assertEqual(vals["lane_line"], 7)

    def test_zero_digest_marker_lines_fail_closed_never_accept(self):
        # The spoof shape: census shows marker lines beyond the record, and
        # only the record carries a digest. Everything agrees numerically, yet
        # the in-section zero-digest marker line is UNPARSEABLE -> REFUSE.
        doc = [HEADER, "", record_line(self.digest), "",
               "## later synthetic entry quoting the rule", "",
               prose_marker_line(7), "", filler(9), "", prose_marker_line(11),
               ""]
        v, d, _, _ = self.run_check(self.fixture(doc))
        self.assertEqual(v, "REFUSE")
        self.assertIn("UNPARSEABLE", d)
        self.assertIn("line 7", d)
        self.assertNotEqual(v, "ACCEPT")

    def test_two_digests_on_one_marker_line_fails_closed(self):
        other = hashlib.sha256(b"SYNTHETIC-SECOND-DIGEST-TEST").hexdigest()
        line = "`%s` (pin recorded to `pin.txt` - and also `%s` inline)" % (
            self.digest, other)
        doc = [HEADER, "", line, ""]
        v, d, _, _ = self.run_check(self.fixture(doc))
        self.assertEqual(v, "REFUSE")
        self.assertIn("carries 2 backticked 64-hex digests", d)

    def test_missing_anchor_fails_closed(self):
        doc = self.pristine_doc()
        v, d, _, _ = self.run_check(self.fixture(doc), anchor="TASK absent/999")
        self.assertEqual(v, "REFUSE")
        self.assertIn("anchor", d)
        self.assertIn("occurs on 0 lines", d)

    def test_twice_occurring_anchor_fails_closed(self):
        doc = self.pristine_doc() + [HEADER, ""]
        v, d, _, _ = self.run_check(self.fixture(doc))
        self.assertEqual(v, "REFUSE")
        self.assertIn("occurs on 2 lines", d)

    def test_no_record_in_section_fails_closed(self):
        doc = [HEADER, "", filler(3), ""]
        v, d, _, _ = self.run_check(self.fixture(doc))
        self.assertEqual(v, "REFUSE")
        self.assertIn("MISSING", d)

    def test_unreadable_input_is_neither_not_a_verdict(self):
        v, d, _, log = self.run_check(
            (os.path.join(self.dir, "absent.py"),
             os.path.join(self.dir, "absent.txt"),
             os.path.join(self.dir, "absent.md")))
        self.assertEqual(v, "NEITHER")
        self.assertTrue(any(l.startswith("NEITHER: unreadable input")
                            for l in log))
        self.assertIn("FileNotFoundError", d)


class TestConditionsAreLoadBearing(CrossWitnessRefBase):
    """Each condition, removed alone, moves at least one verdict."""

    def test_condition1_removal_moves_a_verdict(self):
        # Section anchoring: prose quoting the marker BEFORE the anchor is
        # invisible to the adopted check (ACCEPT) and makes an unanchored
        # whole-file scan fail closed (REFUSE) - 0190's recorded "safe but
        # noisy" rationale.
        doc = [prose_marker_line(1), "", filler(3), HEADER, "",
               record_line(self.digest), "", filler(8), ""]
        paths = self.fixture(doc)
        v_ref, _, _, _ = self.run_check(paths)
        v_mut, d_mut, _, _ = self.run_check(paths, anchored=False)
        self.assertEqual(v_ref, "ACCEPT")
        self.assertEqual(v_mut, "REFUSE")
        self.assertIn("UNPARSEABLE", d_mut)
        self.assertIn("line 1", d_mut)

    def test_condition2_removal_moves_a_verdict(self):
        # Line-START canonical pattern: a prose line INSIDE the section that
        # quotes the marker and exactly one agreeing digest is refused by the
        # adopted check (not a canonical record) but ACCEPTED by an
        # anywhere-in-line parse - the permissive direction, which is why the
        # condition was adopted.
        prose_with_digest = ("a prose sentence quoting the digest `%s` and "
                             "the marker (pin recorded to inline - synthetic"
                             % self.digest)
        doc = [HEADER, "", record_line(self.digest), "", filler(5), "",
               prose_with_digest, ""]
        paths = self.fixture(doc)
        v_ref, d_ref, _, _ = self.run_check(paths)
        v_mut, _, _, _ = self.run_check(paths, line_start=False)
        self.assertEqual(v_ref, "REFUSE")
        self.assertIn("does not start with the canonical record pattern", d_ref)
        self.assertEqual(v_mut, "ACCEPT")

    def test_condition3_removal_moves_both_interruption_verdicts(self):
        # Entry-before-pin ordering (both witnesses required): removing it
        # (order-blind, a single witness suffices) ACCEPTs the pin-only
        # rewrite AND the co-mutation.
        fake = hashlib.sha256(b"SYNTHETIC-PIN-ONLY-TEST").hexdigest()
        paths = self.fixture(self.pristine_doc(), pin_digest=fake)
        v_ref, _, _, _ = self.run_check(paths)
        v_mut, _, _, _ = self.run_check(paths, both_witnesses=False)
        self.assertEqual(v_ref, "REFUSE")
        self.assertEqual(v_mut, "ACCEPT")
        mutated = INSTRUMENT + b"# co-mutated\n"
        cpaths = self.fixture(self.pristine_doc(), instrument=mutated)
        v_ref2, _, _, _ = self.run_check(cpaths)
        v_mut2, _, _, _ = self.run_check(cpaths, both_witnesses=False)
        self.assertEqual(v_ref2, "REFUSE")
        self.assertEqual(v_mut2, "ACCEPT")

    def test_condition4_removal_moves_the_repin_verdict(self):
        # Latest-wins: removing it (first record wins) turns the legitimate
        # re-pin into a REFUSE - the append-only lane semantics break.
        new_instr = INSTRUMENT + b"# legitimately re-pinned\n"
        new_digest = hashlib.sha256(new_instr).hexdigest()
        doc = [HEADER, "", record_line(self.digest), "",
               "## SIMULATED-RE-PIN-ENTRY (synthetic)", "",
               record_line(new_digest, "by the re-pin task - synthetic"), ""]
        paths = self.fixture(doc, instrument=new_instr, pin_digest=new_digest)
        v_ref, _, _, _ = self.run_check(paths)
        v_mut, _, vals, _ = self.run_check(paths, latest_wins=False)
        self.assertEqual(v_ref, "ACCEPT")
        self.assertEqual(v_mut, "REFUSE")
        self.assertEqual(vals["lane_line"], 3)  # first record, stale digest


if __name__ == "__main__":
    unittest.main()
