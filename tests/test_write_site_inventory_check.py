"""The write-site inventory check, proved in its failing states first.

TASK 0220. scripts/check_write_site_inventory.py re-derives the write-site
inventory from the tree and exits non-zero when a site is neither through
the door nor on the named exemption list. These tests pin the contract:

  - a new bypass is a VIOLATION (exit 1), not a refusal and not silence;
  - an unparseable file is a REFUSAL (exit 2) - fail-closed, never skip;
  - a second site under an already-admitted key is a new bypass;
  - a door transport is classified DOOR and is nobody's violation;
  - wiring the T1 pair (glm-a TASK 0072) retires two exemption entries,
    and the check says so loudly instead of counting silently;

and one real-tree test: the actual repository verifies - 58 sites, 38
through the door, 20 not, tiers 5/15, zero refusals, zero violations.
That last test IS the inventory; it moves only with the tree and the
exemption table together, which is the whole design. (TASK 0240 moved
bisonfactory's sender attach from the exemption list to the door side,
35/23→36/22. gates-0020 retired two T1 exemptions when TASK 0072's
batch_activate.py and resume_487.py went through the door, 36/22→38/20.)

The synthetic trees are minimal on purpose: the real tree's 58 sites are
noise when the question is whether one crafted site fires one rule.

Per-GATES-0070: assertions A, B, C are separated into independent test
methods so that each can be evaluated individually against mutations that
target ONLY one assertion's subject matter.
"""
import contextlib
import importlib.util
import io
import os
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SCRIPT = os.path.join(ROOT, "scripts", "check_write_site_inventory.py")

_spec = importlib.util.spec_from_file_location(
    "check_write_site_inventory", _SCRIPT)
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)


def _capture_output(root):
    """Run the script and return (code, stdout)."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = check.main(root=root)
    return code, buffer.getvalue()


class SyntheticTree(unittest.TestCase):
    """Synthetic fixture tests — these must survive every mutation of the
    real-tree assertions because they exercise the engine, not its numbers."""

    def _run(self, files):
        with tempfile.TemporaryDirectory() as tmp:
            for directory in ("src", "scripts"):
                os.makedirs(os.path.join(tmp, directory),
                            exist_ok=True)
            for rel, text in files.items():
                path = os.path.join(tmp, rel)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8",
                          newline="\n") as handle:
                    handle.write(text)
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = check.main(root=tmp)
        return code, buffer.getvalue()

    def test_a_bare_unregistered_site_is_a_new_bypass(self):
        code, out = self._run({
            "scripts/anon.py": "bison.pause_campaign(1)\n",
        })
        self.assertEqual(code, 1, out)
        self.assertIn("anon.py bison.pause_campaign (1 site(s)) is "
                      "neither through the door nor on the exemption list",
                      out)
        self.assertIn("THIS IS A NEW BYPASS", out)

    def test_the_same_site_is_reported_to_the_brake_question_too(self):
        code, out = self._run({
            "scripts/anon.py": "bison.pause_campaign(1)\n",
        })
        self.assertEqual(code, 1, out)
        self.assertIn("anon.py:1 bison.pause_campaign is UNBRACED", out)

    def test_an_unparseable_file_refuses_rather_than_skips(self):
        code, out = self._run({
            "src/broken.py": "def (:\n",
        })
        self.assertEqual(code, 2, out)
        self.assertIn("REFUSED", out)
        self.assertIn("broken.py", out)

    def test_a_second_site_under_an_admitted_key_is_a_new_bypass(self):
        code, out = self._run({
            "scripts/make_481_inert.py":
                "def main():\n    bison.stop_lead('481')\n",
        })
        self.assertEqual(code, 1, out)
        self.assertIn("make_481_inert.py bison.stop_lead: exemption pins "
                      "2 site(s), the tree holds 1", out)

    def test_a_door_transport_is_classified_door_and_is_no_violation(self):
        code, out = self._run({
            "scripts/via_door.py":
                "providerwrites.perform(\n"
                "    'heyreach.pause',\n"
                "    transport=lambda: heyreach.pause_campaign(1),\n"
                ")\n",
        })
        self.assertIn("via_door.py:3 heyreach.pause_campaign DOOR-in-call",
                      out)
        door_lines = [line for line in out.splitlines()
                      if "via_door.py" in line]
        self.assertTrue(door_lines, out)
        for line in door_lines:
            self.assertNotIn("VIOLATION", line)
        reasons = [line for line in out.splitlines()
                   if "VIOLATION" in line]
        for line in reasons:
            self.assertNotIn("via_door.py:3", line)

    def test_wiring_the_t1_pair_retires_two_entries_loudly(self):
        # Pre-gates-0020: an empty tree makes the T1 exemptions stale so the
        # check says so loudly. gates-0020 retired those entries on
        # origin/master, so the T1-specific assertions are no longer live;
        # the test still proves the general "empty tree -> stale exemptions ->
        # exit 1" contract.
        code, out = self._run({
            "scripts/placeholder.py": "# no write sites\n",
        })
        self.assertEqual(code, 1, out)
        self.assertIn("stale exemption", out)


class RealTree(unittest.TestCase):
    """Real-tree assertions are separated by GATES-0070 into independent
    methods so that each assertion class gets a distinct per-assertion
    verdict against mutations. This prevents a collateral failure in one
    assertion from masking another, and prevents a single assertIn from
    short-circuiting later assertions before they can evaluate."""

    # ------------------------------------------------------------------
    # Assertion A: EXEMPTIONS dict has no retired T1 entries
    # Subject: check.EXEMPTIONS content (two keys removed by gates-0020)
    # ------------------------------------------------------------------
    def test_A_exemption_retirement(self):
        """A: Two T1 exemption entries were retired — batch_activate and
        resume_487 must NOT appear in EXEMPTIONS."""
        # Re-import to get fresh module state (EXEMPTIONS is an import-time
        # constant, so importing again ensures we read the current dict)
        spec = importlib.util.spec_from_file_location(
            "check_write_site_inventory_fresh", _SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        t1_keys = [k for k in mod.EXEMPTIONS if k[0] in
                   ("batch_activate", "resume_487")]
        self.assertEqual(len(t1_keys), 0,
                         f"A violated: {t1_keys} still in EXEMPTIONS after "
                         "gates-0020")

    # ------------------------------------------------------------------
    # Assertion B: pin location moved 1898 -> 2008
    # Subject: expected string contains bisonfactory.py:2008 not 1898
    # ------------------------------------------------------------------
    def test_B_pin_location(self):
        """B: Pin at bisonfactory.py:2008. The factory's attach is now at
        2008 (moved from 1898 by gates-0020); asserting the old location
        is how B fails."""
        code, out = _capture_output(check.ROOT)
        self.assertEqual(code, 0, out)
        self.assertIn("bisonfactory.py:2008 bison.attach_senders "
                      "DOOR-by-name", out)
        # Negative guard: the OLD location must not appear.
        self.assertNotIn("bisonfactory.py:1898", out)

    # ------------------------------------------------------------------
    # Assertion C1: CONTROL count strings (denominator + tier sums)
    # Subject: exact "through the door: N", "NOT through the door: N",
    #          "T1 X  T2 Y  T3 Z" strings printed by the inventory
    # ------------------------------------------------------------------
    def test_C1_control_counts(self):
        """C1: CONTROL denominator and tier-count strings match reality.
        'through the door: 38 (22 in-call, 16 by-name)',
        'NOT through the door: 20', 'T1 0 T2 5 T3 15 sum 20'."""
        code, out = _capture_output(check.ROOT)
        self.assertEqual(code, 0, out)
        for ctrl in ("CONTROL 1 - denominator",
                     "CONTROL 2 - tiers of the not-door sites",
                     "CONTROL 3 - integrity"):
            self.assertIn(ctrl, out)
        self.assertIn("write sites: 58 (floor 50)", out)
        self.assertIn("through the door: 38 (22 in-call, 16 by-name)", out)
        self.assertIn("NOT through the door: 20", out)
        self.assertIn("T1 0  T2 5  T3 15  (registered sites sum 20)", out)
        self.assertIn("refusals: 0 (must be 0)", out)
        self.assertIn("violations: 0 (must be 0)", out)
        self.assertIn("EXIT 0 - the inventory verifies", out)

    # ------------------------------------------------------------------
    # Assertion C2: T1 tier-anchor labels (WIRED/T1 -> DOOR-in-call/door)
    # Subject: batch_activate.py and resume_487.py lines show
    #          DOOR-in-call, op=EMAIL_RESUME, facing=False, tier=door
    # ------------------------------------------------------------------
    def test_C2_tier_anchors(self):
        """C2: T1 anchor assertion — the two T1 sites wired through the
        door by GLM-C TASK 0072 now show DOOR-in-call tier=door rather
        than WIRED tier=T1."""
        _, out = _capture_output(check.ROOT)
        t1_lines = [line for line in out.splitlines()
                    if line.strip().startswith(("batch_activate.py:",
                                                 "resume_487.py:"))]
        self.assertEqual(len(t1_lines), 2, out)
        for line in t1_lines:
            self.assertIn("bison.resume_campaign DOOR-in-call", line)
            self.assertIn("op=EMAIL_RESUME facing=False tier=door", line)

    # ------------------------------------------------------------------
    # Additional anchors (survive A/B/C mutations — integrity scaffold)
    # ------------------------------------------------------------------
    def test_T2_T3_anchors_integrity(self):
        """T2/T3 anchors: invariant scaffolding that survives any
        A/B/C-level mutation and confirms the full inventory renders."""
        code, out = _capture_output(check.ROOT)
        self.assertEqual(code, 0, out)
        for anchor in ("linkedin_activate.py:160 "
                       "heyreach.activate_campaign WIRED",
                       "linkedin_activate.py:164 "
                       "heyreach.activate_campaign WIRED"):
            self.assertIn(anchor, out)
        for line in out.splitlines():
            if ("linkedin_activate.py:1" in line
                    and "activate_campaign" in line):
                self.assertIn("tier=T2", line)
                self.assertIn("facing=True", line)
        self.assertIn("bisonfactory.py:2008 bison.attach_senders "
                      "DOOR-by-name", out)
        self.assertIn("make_481_inert.py:144 bison.stop_lead EXEMPT-brake",
                      out)
        self.assertIn("make_481_inert.py:163 bison.stop_lead EXEMPT-brake",
                      out)
        self.assertIn("probe_list_staging.py:173 "
                      "heyreach.add_leads_to_list WIRED", out)
        for line in out.splitlines():
            if "probe_list_staging.py:1" in line:
                self.assertIn("tier=T3", line)
        for line in out.splitlines():
            if "heyreach.start_campaign" in line:
                self.assertIn(
                    "op=LINKEDIN_ACTIVATE,LINKEDIN_START_EMPTY_FOR_STAGING",
                    line)
                self.assertIn("facing=True|False", line)

    # Full regression guard — runs everything via one method call
    def test_full_real_tree_verifies(self):
        """Full regression: all assertions pass together."""
        self.test_A_exemption_retirement()
        self.test_B_pin_location()
        self.test_C1_control_counts()
        self.test_C2_tier_anchors()
        self.test_T2_T3_anchors_integrity()


if __name__ == "__main__":
    unittest.main()
