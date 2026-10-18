"""A NEW provider write that does not pass `providerwrites.perform` fails here.

OPERATOR DECISION D, 2026-10-14. Measured that day: **58 mutating provider call
sites, 32 pass the door, 26 do not** - 9 in `src/bisonfactory.py` and 17 across
9 scripts. That number is not being fixed in one move, so it is PINNED: the 26
are recorded in `scripts/known_write_bypasses.json` and this module fails when a
27th appears.

BOTH SIDES ARE DERIVED, NEITHER IS TYPED. The current set comes from
`scripts/write_path_denominator.py` at test time; the baseline was written by
`scripts/regen_write_bypass_baseline.py` from that same analyzer, which itself
derives the set of mutating provider functions by closure over each provider's
own call graph. No list of filenames or function names appears in either.

That matters because the instrument this replaces did exactly the opposite.
`sink_token_split.py` carried fourteen hardcoded script basenames and reported
"0 scripts with a token-free write" while SEVEN scripts with ungated provider
writes sat outside its own denominator - `batch_linkedin_push`,
`probe_list_staging`, `linkedin_activate`, `make_481_inert`, `batch_activate`,
`batch_linkedin_reconcile`, `resume_487`. See `resonate-ops/THE-CATALOGUE.md`
entry 7, and item 2 of the three shapes: a hand-kept denominator.

WHAT THIS MODULE DELIBERATELY DOES NOT CLAIM. It does not say the 26 are safe.
It says their number may not grow unnoticed. Whether a given write SHOULD be
gated is the operator's B decision, which turns on two questions and not one:
can PERFORMING this write reach a person, and can REFUSING it reach a person? A
safety write - a pause, a stop-lead, any halt - must fail OPEN, so gating one is
worse than leaving it ungated. This module therefore pins the count in both
directions and takes no view on which side of the line a site belongs.

THE VACUOUS-PASS GUARD IS THE POINT OF `TheInstrumentIsNotDegenerate`. If the
analyzer ever returned an empty set of mutating functions, every count would be
zero, zero is not greater than the baseline, and this module would pass while
watching nothing - the exact shape of the four controls found unable to fail in
this repository. So the analyzer is checked for signs of life BEFORE its answer
is believed.
"""
import collections
import importlib.util
import io
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(ROOT, "scripts", "known_write_bypasses.json")
ANALYZER = os.path.join(ROOT, "scripts", "write_path_denominator.py")
REGEN = "py -3 -B scripts/regen_write_bypass_baseline.py"


def _analyzer():
    spec = importlib.util.spec_from_file_location(
        "write_path_denominator_under_test", ANALYZER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["write_path_denominator_under_test"] = module
    spec.loader.exec_module(module)
    return module


def _measure():
    module = _analyzer()
    writers = module.mutating_functions(ROOT)
    rows = module.call_sites(ROOT, writers)
    counts = collections.Counter(
        "%s::%s::%s" % (rel, where, call)
        for verdict, rel, _line, call, where in rows if verdict == "BYPASS")
    verdicts = collections.Counter(v for v, *_ in rows)
    return writers, rows, counts, verdicts


class TheInstrumentIsNotDegenerate(unittest.TestCase):
    """Signs of life, checked before any answer below is believed."""

    @classmethod
    def setUpClass(cls):
        cls.writers, cls.rows, cls.counts, cls.verdicts = _measure()

    def test_the_analyzer_and_the_baseline_both_exist(self):
        self.assertTrue(os.path.exists(ANALYZER), ANALYZER)
        self.assertTrue(os.path.exists(BASELINE),
                        "%s is missing; regenerate with: %s"
                        % (BASELINE, REGEN))

    def test_both_providers_contribute_mutating_functions(self):
        """An empty set would make every count below zero and this file inert."""
        self.assertIn("bison", self.writers)
        self.assertIn("heyreach", self.writers)
        for provider, functions in self.writers.items():
            self.assertGreater(
                len(functions), 5,
                "%s contributed only %d mutating functions; the call-graph "
                "closure has probably broken, and a degenerate analyzer makes "
                "every assertion in this module vacuous"
                % (provider, len(functions)))

    def test_known_write_verbs_are_found(self):
        """A positive control. These four reach a provider by inspection, so an
        analyzer that cannot see them is not measuring what it claims."""
        self.assertIn("create_campaign", self.writers["bison"])
        self.assertIn("resume_campaign", self.writers["bison"])
        self.assertIn("add_leads_to_list", self.writers["heyreach"])
        self.assertIn("set_sequence", self.writers["heyreach"])

    def test_it_classifies_both_ways(self):
        """A classifier that answered one way for everything would be useless in
        whichever direction it happened to pick."""
        self.assertGreater(self.verdicts["gated"], 0,
                           "nothing was found passing the door")
        self.assertGreater(self.verdicts["BYPASS"], 0,
                           "nothing was found bypassing the door - if that is "
                           "genuinely true, this module has done its job and "
                           "should be retired, not relaxed")

    def test_there_are_write_paths_at_all(self):
        self.assertGreater(len(self.rows), 20,
                           "only %d provider write paths found in the whole "
                           "tree; discovery has broken" % len(self.rows))


class NoNewWriteBypassesTheDoor(unittest.TestCase):
    """The assertion decision D asked for."""

    @classmethod
    def setUpClass(cls):
        cls.writers, cls.rows, cls.counts, cls.verdicts = _measure()
        cls.baseline = json.loads(io.open(BASELINE, encoding="utf-8").read())
        cls.known = collections.Counter(cls.baseline["sites"])

    def test_no_bypassing_call_site_is_new(self):
        """THE TEST THAT GOES RED WHEN AN UNGATED WRITE IS ADDED."""
        added = sorted(set(self.counts) - set(self.known))
        self.assertEqual(
            [], added,
            "new provider write(s) that do NOT pass providerwrites.perform:\n  "
            + "\n  ".join(added)
            + "\n\nEither route the write through `perform` with a gate, or - if "
              "it is a SAFETY write whose refusal could let a message reach a "
              "person (a pause, a stop-lead, a halt) - leave it ungated and "
              "record it deliberately with `%s`, saying so in the commit "
              "message. Do NOT regenerate the baseline to make this green."
            % REGEN)

    def test_no_existing_site_gained_occurrences(self):
        """A second ungated write in a function that already had one."""
        grew = {key: (self.known[key], self.counts[key])
                for key in self.counts
                if key in self.known and self.counts[key] > self.known[key]}
        self.assertEqual(
            {}, grew,
            "these functions gained ungated provider writes (baseline, now): "
            "%s" % grew)

    def test_the_baseline_has_not_fallen_behind_the_code(self):
        """The other direction, so the baseline cannot silently drift.

        A site that has disappeared is good news - something got gated, or the
        script was retired - but it must be RECORDED, or the baseline slowly
        becomes a list of things that no longer exist and stops constraining
        anything. That is `CAPS_ENFORCED_ELSEWHERE` naming absent keys, which is
        catalogue entry 2.
        """
        gone = sorted(set(self.known) - set(self.counts))
        shrunk = {key: (self.known[key], self.counts[key])
                  for key in self.known
                  if key in self.counts and self.counts[key] < self.known[key]}
        self.assertEqual(
            ([], {}), (gone, shrunk),
            "the baseline names bypassing writes that are no longer there.\n"
            "gone: %s\nshrunk (baseline, now): %s\n\nIf you gated or retired "
            "them, regenerate with `%s` and say which in the commit message."
            % (gone, shrunk, REGEN))

    def test_the_total_agrees_with_the_enumeration(self):
        """The 263-vs-267 lesson, applied here: a stored total and a stored list
        must not be able to disagree."""
        self.assertEqual(sum(self.known.values()),
                         self.baseline["total_bypassing_call_sites"],
                         "the baseline's own total disagrees with its own "
                         "enumeration; regenerate with: %s" % REGEN)

    def test_the_baseline_is_not_empty(self):
        """An empty baseline would make `added` equal every bypass found, so
        this would fail loudly rather than pass - but an empty baseline paired
        with a degenerate analyzer would pass. Both are refused."""
        self.assertGreater(sum(self.known.values()), 0,
                           "the baseline records no bypassing writes at all; "
                           "regenerate with: %s" % REGEN)


if __name__ == "__main__":
    unittest.main()
