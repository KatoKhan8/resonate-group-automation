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

and one real-tree test: the actual repository verifies - 58 sites, 35
through the door, 23 not, tiers 2/6/15, zero refusals, zero violations.
That last test IS the inventory; it moves only with the tree and the
exemption table together, which is the whole design.

The synthetic trees are minimal on purpose: the real tree's 58 sites are
noise when the question is whether one crafted site fires one rule.
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


class SyntheticTree(unittest.TestCase):

    def _run(self, files):
        with tempfile.TemporaryDirectory() as tmp:
            # Both walker directories exist even when the fixture only
            # writes into one: a missing src/ is itself a refusal the
            # check is contract-bound to raise, and these tests are
            # asking about violations, not about the walker's legs.
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
        # The same fixture, the other invariant: a door-clean inventory
        # must not let a brake bypass hide inside it. 0210 owns the
        # question; this check still names it.
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
        # make_481_inert's two stop_lead sites are exempt BY 0210 DESIGN
        # and pinned at exactly two. One site under the key is not a
        # pass - it is a count mismatch, because a changed count under a
        # pinned key means sites appeared or disappeared.
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
        # The synthetic tree failing on its stale entries is expected;
        # the door site simply must not be among the reasons.
        reasons = [line for line in out.splitlines()
                   if "VIOLATION" in line]
        for line in reasons:
            self.assertNotIn("via_door.py:3", line)

    def test_wiring_the_t1_pair_retires_two_entries_loudly(self):
        # The designed handshake with glm-a TASK 0072: when batch_activate
        # and resume_487 go through the door, their exemption entries go
        # stale and this check fails until the table is edited in the
        # same commit. An empty tree is that future state.
        code, out = self._run({
            "scripts/placeholder.py": "# no write sites\n",
        })
        self.assertEqual(code, 1, out)
        self.assertIn("stale exemption batch_activate.py "
                      "bison.resume_campaign (T1)", out)
        self.assertIn("stale exemption resume_487.py "
                      "bison.resume_campaign (T1)", out)
        self.assertIn("T1 0 ", out)


class RealTree(unittest.TestCase):

    def test_the_real_tree_verifies(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = check.main(root=check.ROOT)
        out = buffer.getvalue()
        self.assertEqual(code, 0, out)

        for control in ("CONTROL 1 - denominator",
                        "CONTROL 2 - tiers of the not-door sites",
                        "CONTROL 3 - integrity"):
            self.assertIn(control, out)

        # CONTROL 1: the re-derived denominator at HEAD e84108f5d.
        self.assertIn("write sites: 58 (floor 50)", out)
        self.assertIn("through the door: 35 (20 in-call, 15 by-name)", out)
        self.assertIn("NOT through the door: 23", out)

        # CONTROL 2: the tiers of the 23, summing to 23.
        self.assertIn("T1 2  T2 6  T3 15  (registered sites sum 23)", out)

        # CONTROL 3: nothing refused, nothing violated.
        self.assertIn("refusals: 0 (must be 0)", out)
        self.assertIn("violations: 0 (must be 0)", out)
        self.assertIn("EXIT 0 - the inventory verifies", out)

        # The two T1 sites are glm-a's TASK 0072, tier-pinned so the
        # lanes cannot collide on the same lines silently.
        t1_lines = [line for line in out.splitlines()
                    if line.strip().startswith(("batch_activate.py:",
                                                 "resume_487.py:"))]
        self.assertEqual(len(t1_lines), 2, out)
        for line in t1_lines:
            self.assertIn("bison.resume_campaign WIRED", line)
            self.assertIn("op=EMAIL_RESUME facing=False tier=T1", line)

        # T2 anchors, at the lines the lane entry names.
        for anchor in ("linkedin_activate.py:160 "
                       "heyreach.activate_campaign WIRED",
                       "linkedin_activate.py:164 "
                       "heyreach.activate_campaign WIRED",
                       "bisonfactory.py:1884 bison.attach_senders WIRED"):
            self.assertIn(anchor, out)
        for line in out.splitlines():
            if ("linkedin_activate.py:1" in line
                    and "activate_campaign" in line):
                self.assertIn("tier=T2", line)
                self.assertIn("facing=True", line)
            if "bisonfactory.py:1884" in line:
                self.assertIn("tier=T2", line)
                self.assertIn("op=EMAIL_ASSIGN_SENDER facing=False", line)

        # Brake-design exemptions, pinned at their two sites.
        self.assertIn("make_481_inert.py:144 bison.stop_lead EXEMPT-brake",
                      out)
        self.assertIn("make_481_inert.py:163 bison.stop_lead EXEMPT-brake",
                      out)

        # A T3 anchor: the unbound-list staging sites.
        self.assertIn("probe_list_staging.py:173 "
                      "heyreach.add_leads_to_list WIRED", out)
        for line in out.splitlines():
            if "probe_list_staging.py:1" in line:
                self.assertIn("tier=T3", line)

        # The two-operation verb prints both candidates, both facings.
        for line in out.splitlines():
            if "heyreach.start_campaign" in line:
                self.assertIn(
                    "op=LINKEDIN_ACTIVATE,LINKEDIN_START_EMPTY_FOR_STAGING",
                    line)
                self.assertIn("facing=True|False", line)


if __name__ == "__main__":
    unittest.main()
