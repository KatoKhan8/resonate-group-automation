#!/usr/bin/env python3
"""TASK-0250. `bounce_history` answered UNKNOWN to every world, including one
holding the bounce.

## THE PREMISE DID NOT SURVIVE, AND THAT IS THE FINDING

TASK-0220's own headline says:

    "a bounce that was never recorded makes the preflight's `bounce_history`
     cell read PASS, not UNKNOWN"

TASK-0250 was dispatched to repair that - to make the cell answer UNKNOWN
when its authority is absent, empty or resolved against the wrong tree, the
way TASK-0190 did for `store.load()`. **All three were ALREADY UNKNOWN.**
`bounce_history` declares `needs: ("queue",)`, so TASK-0190's authority gate
covers it, and the cell names the resolved path in every one of the three.
Measured in all four worlds before a line was changed; the table is
`test_the_four_worlds_this_cell_was_asked_about`.

The sentence is right about `channels._bounced` and wrong about the CELL.
`_bounced` really does answer `False` for a missing event, and on the SEND
path - `channels.email_verdict`, `eligibility.decide` - that `False` is
exactly as dangerous as TASK-0220 said. It never reached this cell, because
the cell was not asking.

## WHAT WAS ACTUALLY BROKEN, AND IT IS THE OPPOSITE DEFECT

The rule carried `ask: None`. So in the ONE world that matters - queue
PRESENT_POPULATED, the record supplied, an `EMAIL_BOUNCED` event sitting in
its `events` list - the cell read:

    UNKNOWN   "this rule has no form that can be evaluated without a record
               or a provider read"

A rule that cannot report an exclusion present in its own input is an
instrument that only ever refuses. The brief named the hazard itself: that is
as useless as one that only ever passes, and it is harder to see, because
every control built for the other seven rows is satisfied by it.

## WHAT IS PINNED HERE

    C1   PRESENT_EMPTY        UNKNOWN, path named        (already true)
    C2   PRESENT_POPULATED    EXCLUDED, event named      (TASK-0250's repair)
    C3   ABSENT               UNKNOWN, path named        (already true)
    C4   OUTSIDE_TREE         UNKNOWN, BOTH paths named  (already true)

C2 is the one that could not pass. C1, C3 and C4 are pinned anyway, in this
file, for `bounce_history` BY NAME: they were covered only by a loop over
all fourteen queue rules, and a loop is where a single rule's regression
hides.

PASS is unreachable for this rule and that is deliberate, not an oversight -
`WHAT_WOULD_ANSWER["bounce_recorder"]` says what would make it reachable.
`test_pass_is_unreachable_and_the_reason_is_named` pins both halves, so the
refusal cannot outlive its reason.

## NO REAL ADDRESS IS IN THIS FILE

Reserved domains only, asserted on this module's own bytes.
"""
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import bouncepolicy, channels, events, preflight         # noqa: E402

RULE = "bounce_history"

#: Reserved domain. The address is also what `preflight._CONTROL_BOUNCED`
#: uses, so a grep for it finds the control and the test together.
BOUNCED = "already-bounced-control@example.test"


class _Plant(unittest.TestCase):
    """A temp tree of planted authorities, and one queue record in it."""

    def setUp(self):
        from src import operatorexclusion

        self.tmp = tempfile.mkdtemp(prefix="rga-0250-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.addCleanup(operatorexclusion.forget)
        operatorexclusion.forget()

    def plant(self, empty=(), bounced=None, remove_queue=False):
        """(state, paths, contact).

        `bounced` None leaves the filler queue plant alone; True/False
        rewrites it as one real record with or without the bounce event, read
        back through `store.read_jsonl` so the record handed to `evaluate` is
        the authority's own row.
        """
        state, paths = preflight._planted_state(self.tmp, empty=empty)
        rec = None
        if bounced is not None:
            rec = preflight._bounce_queue_row(paths["queue"], bounced=bounced)
        if remove_queue:
            os.remove(paths["queue"])
        state = preflight._planted_state(self.tmp, paths=paths)[0]
        contact = {"key": "control-8", "email": BOUNCED,
                   "domain": "example.test",
                   # A RECORD IS ALWAYS SUPPLIED. Without one the cell is
                   # UNKNOWN for a different reason - `needs_record` - and
                   # every assertion below would be green by accident.
                   "record": rec if rec is not None else {
                       "id": "r-1", "domain": "example.test", "events": []}}
        return state, paths, contact

    def cell(self, state, paths, contact):
        with preflight._pointed(paths):
            row = preflight.evaluate(contact, state=state, channel="email")
        return row["cells"][RULE]


class TheFourWorlds(_Plant):
    """Step 2 of the brief: the four answers, as measured, in one table."""

    def test_the_four_worlds_this_cell_was_asked_about(self):
        observed = {}

        state, paths, contact = self.plant(remove_queue=True)
        observed["ABSENT"] = (state["queue"]["state"],
                              self.cell(state, paths, contact)["cell"])

        state, paths, contact = self.plant(empty=("queue",))
        observed["PRESENT_EMPTY"] = (state["queue"]["state"],
                                     self.cell(state, paths, contact)["cell"])

        state, paths, contact = self.plant(bounced=True)
        other = tempfile.mkdtemp(prefix="rga-0250-other-")
        self.addCleanup(shutil.rmtree, other, ignore_errors=True)
        elsewhere = os.path.join(other, "queue.planted")
        shutil.copyfile(paths["queue"], elsewhere)
        resolvers = {n: (lambda _p=paths[n]: _p)
                     for n in preflight.AUTHORITY_NAMES}
        resolvers["queue"] = (lambda: elsewhere)
        outside = preflight.authorities(resolvers=resolvers, root=self.tmp)
        observed["OUTSIDE_TREE"] = (
            outside["queue"]["state"],
            self.cell(outside, paths, contact)["cell"])

        observed["PRESENT_POPULATED"] = (state["queue"]["state"],
                                         self.cell(state, paths,
                                                   contact)["cell"])

        self.assertEqual(
            {"ABSENT": (preflight.ABSENT, preflight.UNKNOWN),
             "PRESENT_EMPTY": (preflight.PRESENT_EMPTY, preflight.UNKNOWN),
             "OUTSIDE_TREE": (preflight.OUTSIDE_TREE, preflight.UNKNOWN),
             # THE ONE THAT MOVED. Everything else in this table was already
             # true before TASK-0250 changed a line.
             "PRESENT_POPULATED": (preflight.PRESENT_POPULATED,
                                   preflight.EXCLUDED)},
            observed)


class C1ThePresentAndEmptyAuthority(_Plant):

    def test_an_empty_queue_makes_this_cell_unknown_and_names_the_path(self):
        state, paths, contact = self.plant(empty=("queue",))
        cell = self.cell(state, paths, contact)
        self.assertEqual(preflight.UNKNOWN, cell["cell"])
        self.assertIn("PRESENT_EMPTY", cell["why"])
        self.assertIn(paths["queue"], cell["why"])
        self.assertIn("WHICH MEANS", cell["why"])

    def test_c1_goes_red_when_the_empty_check_is_mutated_away(self):
        """THE MUTATION: `ANSWERABLE` is the one place the empty check
        lives. Widen it to accept PRESENT_EMPTY and C1's assertion must
        fail - and the cell stops naming the path at all, because the gate
        no longer fires."""
        state, paths, contact = self.plant(empty=("queue",), bounced=None)
        with mock.patch.object(
                preflight, "ANSWERABLE",
                (preflight.PRESENT_POPULATED, preflight.PRESENT_EMPTY)):
            # `authorities` is unaffected - the STATE is still PRESENT_EMPTY.
            # What moves is whether `evaluate` treats it as an answer.
            blinded = self.cell(state, paths, contact)
        self.assertEqual(preflight.PRESENT_EMPTY, state["queue"]["state"])
        self.assertNotIn("PRESENT_EMPTY", blinded["why"])
        self.assertNotIn(paths["queue"], blinded["why"])


class C2ThePopulatedAuthorityWithARealBounceRow(_Plant):
    """The control that proves the instrument can say something else."""

    def test_a_recorded_bounce_is_excluded_with_the_event_named(self):
        state, paths, contact = self.plant(bounced=True)
        cell = self.cell(state, paths, contact)
        self.assertEqual(preflight.PRESENT_POPULATED,
                         state["queue"]["state"])
        self.assertEqual(1, state["queue"]["records"])
        self.assertEqual(preflight.EXCLUDED, cell["cell"])
        self.assertIn("EMAIL_BOUNCED", cell["why"])
        # AND THE RECORD CAME OUT OF THE AUTHORITY, not out of this test.
        self.assertEqual([events.EMAIL_BOUNCED],
                         [e["type"] for e in contact["record"]["events"]])

    def test_the_whole_table_reports_it_as_an_exclusion(self):
        """A cell nothing totals is a cell nobody reads."""
        state, paths, contact = self.plant(bounced=True)
        with preflight._pointed(paths):
            out = preflight.assess([contact], state=state,
                                   control_rows=[{"ok": True}])
        self.assertEqual(1, out["totals"]["excluded"])
        self.assertEqual([RULE], out["rows"][0]["excluded_by"])
        self.assertEqual(preflight.EXCLUDED, out["rows"][0]["verdict"])

    def test_c2_goes_red_when_the_ask_is_reverted_to_none(self):
        """THE MUTATION THAT IS THE DEFECT ITSELF: put `ask: None` back.

        C2 must fail. C1, C3 and C4 must NOT - they are satisfied by the
        broken rule, which is exactly why C2 had to exist.
        """
        weakened = tuple(dict(r, ask=None) if r["name"] == RULE else r
                         for r in preflight.RULES)
        state, paths, contact = self.plant(bounced=True)
        with mock.patch.object(preflight, "RULES", weakened):
            broken = self.cell(state, paths, contact)
        self.assertEqual(preflight.UNKNOWN, broken["cell"])
        self.assertIn("no form that can be evaluated", broken["why"])
        # The other three, under the same mutation, do not move.
        for label, kwargs in (("C1", {"empty": ("queue",)}),
                              ("C3", {"remove_queue": True})):
            with self.subTest(control=label):
                st, pa, co = self.plant(**kwargs)
                with mock.patch.object(preflight, "RULES", weakened):
                    self.assertEqual(preflight.UNKNOWN,
                                     self.cell(st, pa, co)["cell"])

    def test_c2_goes_red_when_the_ask_refuses_everybody(self):
        """And the other direction, which is the subtler break: an `ask`
        that always answers `Undecided` passes C1, C3 and C4 and is the
        instrument this estate shipped once already."""
        def never(ctx):
            return preflight.Undecided("planted: answers nothing")

        weakened = tuple(dict(r, ask=never) if r["name"] == RULE else r
                         for r in preflight.RULES)
        state, paths, contact = self.plant(bounced=True)
        with mock.patch.object(preflight, "RULES", weakened):
            broken = self.cell(state, paths, contact)
        self.assertEqual(preflight.UNKNOWN, broken["cell"])
        self.assertIn("planted: answers nothing", broken["why"])

    def test_the_ask_reads_the_decider_the_row_declares(self):
        """Through `channels._bounced`, not a second reading of what a
        bounce is. Blind the decider and the cell must stop excluding -
        otherwise this rule has grown its own copy of the question."""
        state, paths, contact = self.plant(bounced=True)
        with mock.patch.object(channels, "_bounced", lambda rec, c: False):
            blinded = self.cell(state, paths, contact)
        self.assertEqual(preflight.UNKNOWN, blinded["cell"])
        self.assertEqual(preflight.EXCLUDED,
                         self.cell(state, paths, contact)["cell"])


class C3TheAuthorityRemovedEntirely(_Plant):

    def test_an_absent_queue_makes_this_cell_unknown_and_names_the_path(self):
        state, paths, contact = self.plant(remove_queue=True)
        cell = self.cell(state, paths, contact)
        self.assertEqual(preflight.ABSENT, state["queue"]["state"])
        self.assertEqual(preflight.UNKNOWN, cell["cell"])
        self.assertIn("ABSENT", cell["why"])
        self.assertIn(paths["queue"], cell["why"])
        self.assertFalse(os.path.exists(paths["queue"]))

    def test_c3_goes_red_when_absent_falls_back_to_an_answer(self):
        """THE MUTATION: let ABSENT license an answer - the "default" an
        absent file is tempting to fall back to. C3 goes red; C2 stays
        green, which is what makes this a kill and not a blanket break."""
        state, paths, contact = self.plant(remove_queue=True)
        with mock.patch.object(
                preflight, "ANSWERABLE",
                (preflight.PRESENT_POPULATED, preflight.ABSENT)):
            blinded = self.cell(state, paths, contact)
        self.assertNotIn("ABSENT", blinded["why"])
        self.assertNotIn(paths["queue"], blinded["why"])
        # C2 under the same mutation: untouched.
        st, pa, co = self.plant(bounced=True)
        with mock.patch.object(
                preflight, "ANSWERABLE",
                (preflight.PRESENT_POPULATED, preflight.ABSENT)):
            self.assertEqual(preflight.EXCLUDED,
                             self.cell(st, pa, co)["cell"])


class C4TheAuthorityResolvedAgainstAnotherTree(_Plant):
    """The one TASK-0190 found hardest, and the one a lane worktree lives in.

    A POPULATED queue at the same relative path in a DIFFERENT tree. The
    verdict must be UNKNOWN - not that tree's answer, and not this record's
    either, because the authority state the cell rests on came from the wrong
    checkout.
    """

    def elsewhere(self, paths):
        other = tempfile.mkdtemp(prefix="rga-0250-other-")
        self.addCleanup(shutil.rmtree, other, ignore_errors=True)
        target = os.path.join(other, "queue.planted")
        shutil.copyfile(paths["queue"], target)
        return target

    def state_pointed_outside(self, paths, target):
        resolvers = {n: (lambda _p=paths[n]: _p)
                     for n in preflight.AUTHORITY_NAMES}
        resolvers["queue"] = (lambda: target)
        return preflight.authorities(resolvers=resolvers, root=self.tmp)

    def test_a_populated_queue_in_another_tree_is_unknown_with_both_paths(
            self):
        state, paths, contact = self.plant(bounced=True)
        target = self.elsewhere(paths)
        self.assertTrue(os.path.getsize(target) > 0)
        outside = self.state_pointed_outside(paths, target)
        cell = self.cell(outside, paths, contact)
        self.assertEqual(preflight.OUTSIDE_TREE, outside["queue"]["state"])
        self.assertEqual(preflight.UNKNOWN, cell["cell"])
        self.assertIn("HARD REFUSAL", cell["why"])
        # BOTH PATHS. A refusal naming one of them cannot be checked.
        self.assertIn(target, cell["why"])
        self.assertIn(self.tmp, cell["why"])

    def test_c4_goes_red_when_the_tree_check_is_mutated_away(self):
        """THE MUTATION: `_inside` always True - the "resolve it anyway"
        repair. The refusal disappears and the other tree's POPULATED file
        licenses the verdict, which is the whole hazard."""
        state, paths, contact = self.plant(bounced=True)
        target = self.elsewhere(paths)
        with mock.patch.object(preflight, "_inside",
                               lambda root, path: True):
            outside = self.state_pointed_outside(paths, target)
            blinded = self.cell(outside, paths, contact)
        self.assertEqual(preflight.PRESENT_POPULATED,
                         outside["queue"]["state"])
        self.assertNotIn("HARD REFUSAL", blinded["why"])
        self.assertEqual(preflight.EXCLUDED, blinded["cell"])


class ThePassThatIsNotReachable(_Plant):
    """Both halves, so neither the refusal nor its reason can be lost."""

    def test_pass_is_unreachable_and_the_reason_is_named(self):
        state, paths, contact = self.plant(bounced=False)
        cell = self.cell(state, paths, contact)
        self.assertEqual(preflight.PRESENT_POPULATED,
                         state["queue"]["state"])
        # `channels._bounced` says False here, and a PASS would be reporting
        # that False as a fact about the address.
        self.assertFalse(channels._bounced(contact["record"], contact))
        self.assertEqual(preflight.UNKNOWN, cell["cell"])
        self.assertIn("NOT A PASS", cell["why"])
        self.assertIn("ZERO readers", cell["why"])
        # THE EMITTING MODULE, NOT THE FAILURE STRING ITSELF. TASK-0220 pins
        # zero occurrences of that string under `src/` and counts hits in
        # `tests/` too, so quoting it here would have made this file a
        # permanent false positive in the one search that proves the
        # recorder's failure has no reader. Named rather than quoted - and
        # `src/preflight.py` carries the same note at `_ask_bounce_history`.
        self.assertIn("bison_watch_loop.py", cell["why"])

    def test_the_soft_count_is_reported_rather_than_rounded_to_none(self):
        """The row declares `bouncepolicy.decide for the hard/soft split`.
        Two softs recorded is a materially different UNKNOWN from none."""
        state, paths, contact = self.plant(bounced=False)
        contact["record"]["events"] = [
            {"type": events.EMAIL_BOUNCED_SOFT, "contact": "control-8"},
            {"type": events.EMAIL_BOUNCED_SOFT, "contact": "control-8"}]
        limit = bouncepolicy.thresholds()["soft_bounces_before_suppression"]
        cell = self.cell(state, paths, contact)
        self.assertEqual(preflight.UNKNOWN, cell["cell"])
        self.assertIn("2 consecutive soft bounce(s) recorded, of %d" % limit,
                      cell["why"])

    def test_a_soft_count_that_raises_is_uncounted_not_zero(self):
        """A raise in the decoration may not lose the refusal, and may not
        be reported as `none` either."""
        def boom(rec, key, address):
            raise RuntimeError("planted")

        state, paths, contact = self.plant(bounced=False)
        with mock.patch.object(bouncepolicy, "consecutive_soft", boom):
            cell = self.cell(state, paths, contact)
        self.assertEqual(preflight.UNKNOWN, cell["cell"])
        self.assertIn("UNCOUNTED (RuntimeError)", cell["why"])


class TheControlsInTheModuleItself(unittest.TestCase):
    """The repair has to be visible in the report, or it is unwired."""

    def test_controls_eight_and_nine_hold_and_the_number_is_nine(self):
        rows = preflight.controls()
        self.assertEqual(9, len(rows))
        self.assertEqual([preflight.PRESENT_POPULATED, 1, preflight.EXCLUDED,
                          True, 1], rows[7]["observed"])
        self.assertEqual([preflight.PRESENT_POPULATED, 1, preflight.UNKNOWN,
                          True], rows[8]["observed"])

    def test_control_eight_is_control_nine_with_exactly_one_event(self):
        """The pair's only difference, stated in the rows themselves."""
        rows = preflight.controls()
        self.assertIn("RECORDED bounce", rows[7]["control"])
        self.assertIn("NO bounce event", rows[8]["control"])
        self.assertIn("EXCLUDES EVERYBODY", rows[8]["note"])

    def _weakened(self, ask):
        return tuple(dict(r, ask=ask) if r["name"] == RULE else r
                     for r in preflight.RULES)

    def test_the_old_ask_none_breaks_both_controls_and_for_two_reasons(self):
        """THE KILL, AT THE CONTROL LEVEL - AND NOT THE ONE I EXPECTED.

        I wrote this test asserting that `ask: None` - the state this rule
        shipped in - fails control 8 and leaves 9 green, since an unasked
        rule still answers UNKNOWN. **It fails BOTH**, and the reason is
        worth keeping: each control's fourth observation watches the cell's
        REASON, not only its verdict. So 8 fails on the verdict (UNKNOWN
        where EXCLUDED is demanded) and 9 fails on the reason alone (UNKNOWN
        is right, but a rule with no ask cannot name the recorder). Measured,
        corrected, and asserted as the two different failures they are.
        """
        with mock.patch.object(preflight, "RULES", self._weakened(None)):
            rows = preflight.controls()
        eight, nine = rows[7], rows[8]
        self.assertFalse(eight["ok"], "a rule with no ask passed control 8")
        self.assertFalse(nine["ok"], "a rule with no ask passed control 9")
        # 8's VERDICT moved; 9's did not, and only its reason cell did.
        self.assertEqual(preflight.UNKNOWN, eight["observed"][2])
        self.assertEqual(preflight.UNKNOWN, nine["observed"][2])
        self.assertFalse(eight["observed"][3])
        self.assertFalse(nine["observed"][3])

    def test_a_rule_that_excludes_everybody_with_the_right_words_fails_nine(
            self):
        """THE DISCRIMINATING MUTATION FOR 9, and it has to carry the right
        reason or 8 reddens too and proves nothing.

        An `ask` that returns the real exclusion sentence for EVERY contact
        satisfies control 8 completely - verdict, event name and the
        headline's `1 EXCLUDED`. Only control 9 catches it.
        """
        def always(ctx):
            return ("this address has a recorded EMAIL_BOUNCED event - "
                    "planted: and so does everybody else")

        with mock.patch.object(preflight, "RULES", self._weakened(always)):
            rows = preflight.controls()
        self.assertTrue(rows[7]["ok"],
                        "control 8 should be satisfied by a rule that fires "
                        "on everyone - that is exactly why 9 exists: %r"
                        % (rows[7]["observed"],))
        self.assertFalse(rows[8]["ok"],
                         "a rule that excludes everybody passed control 9")
        self.assertEqual(preflight.EXCLUDED, rows[8]["observed"][2])

    def test_a_rule_that_refuses_everybody_with_the_right_words_fails_eight(
            self):
        """And the mirror, which is the instrument this estate has shipped
        once: an `ask` that answers the real UNKNOWN sentence to everybody
        satisfies control 9 completely. Only control 8 catches it."""
        def never(ctx):
            return preflight.Undecided(
                "planted: refuses everybody - %s"
                % preflight.WHAT_WOULD_ANSWER["bounce_recorder"])

        with mock.patch.object(preflight, "RULES", self._weakened(never)):
            rows = preflight.controls()
        self.assertTrue(rows[8]["ok"],
                        "control 9 should be satisfied by a rule that "
                        "refuses everyone - that is why 8 exists: %r"
                        % (rows[8]["observed"],))
        self.assertFalse(rows[7]["ok"],
                         "an all-UNKNOWN rule passed control 8")
        self.assertEqual(preflight.UNKNOWN, rows[7]["observed"][2])


class NoRealAddressIsInThisFile(unittest.TestCase):
    """The same assertion TASK-0190's module makes on its own bytes."""

    RESERVED = ("example.test", "example.invalid", "example.com",
                "example.org", "other.invalid", "resonategroup.co")

    def test_no_real_address_in_this_file_or_the_new_control(self):
        found = set()
        for path in (os.path.abspath(__file__),
                     os.path.join(ROOT, "src", "preflight.py")):
            with open(path, encoding="utf-8") as handle:
                for hit in re.findall(r"[\w.+-]+@[\w.-]+\.\w+",
                                      handle.read()):
                    domain = hit.split("@", 1)[1].rstrip(".,'\")")
                    if not domain.endswith(self.RESERVED):
                        found.add(hit)
        self.assertEqual(set(), found)


if __name__ == "__main__":
    unittest.main()
