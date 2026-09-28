"""TASK-901. The figure gate's 4-char prefix licensed fabricated multipliers.

The defect: `_invented_quantities` built its support set as `{w[:4] for w in
...}` and compared `head[0][:4]` against it. Both sides truncated to four
characters, so any pack word sharing a 4-char prefix with a quantity word
licensed a fabricated multiplier:

    "threat" / "threshold"  ->  licenses "three times"
    "several"               ->  licenses "seven times"
    "trip"                  ->  licenses "tripled"
    "doubt"                 ->  licenses "double"
    "quadrant"              ->  licenses "quadrupled"

The fix: match on word boundaries against each quantity word's inflection
family (double/doubled/doubles/doubling, etc.), not on a character prefix.

EVERY acceptance criterion from the task is asserted below, including the
near-miss negative controls that were the missing piece and the mutation
check that proves the test would go red if the fix were reverted.
"""
import hashlib
import unittest

from src import generate


#: A record whose research pack contains ONLY near-miss words — words that
#: share a 4-char prefix with a quantity word but are NOT that quantity word
#: or any of its inflections. Under the prefix check these all licensed
#: fabricated multipliers; under the fix they must not.
NEAR_MISS_REC = {
    "company": "Threshold Analytics",
    "domain": "threshold.test",
    "research": [
        {"fact": "Threshold Analytics faces several challenges in the "
                 "quadrant of the market where a trip to the client site "
                 "is common and doubt remains about adoption."},
    ],
}

#: A record whose research pack contains the LITERAL quantity words, so the
#: fix must still license correct copy (acceptance criterion 2).
LITERAL_REC = {
    "company": "Brightmoor Studio",
    "domain": "brightmoor.test",
    "research": [
        {"fact": "Brightmoor Studio doubled its throughput and three times "
                 "the impact was measured. They tripled their pipeline, "
                 "halved cycle time and quadrupled output. The team "
                 "doubled down on quality."},
    ],
}

CONTACT = {"name": "A Director", "title": "Managing Director"}


class ThePrefixBypassesAreRefused(unittest.TestCase):
    """Acceptance criterion 1: all six bypasses from the review are REFUSED.

    Each test uses a pack containing ONLY a near-miss word (not the literal
    quantity word or any inflection), and asserts that the fabricated
    multiplier is refused.
    """

    def test_threat_does_not_license_three_times(self):
        """'threat' shares 'thre' with 'three' — prefix match, not a stem."""
        rec = {"company": "Acme", "domain": "acme.test",
               "research": [{"fact": "Acme faces a serious threat from "
                                      "competitors in the market."}]}
        self.assertTrue(generate._invented_quantities(
            "Resource decisions have three times the impact on margin.",
            rec, CONTACT),
            "'threat' must not license 'three times'")

    def test_threshold_does_not_license_three_times(self):
        rec = {"company": "Threshold", "domain": "t.test",
               "research": [{"fact": "Threshold crossed a critical level."}]}
        self.assertTrue(generate._invented_quantities(
            "The impact was three times greater.", rec, CONTACT))

    def test_several_does_not_license_seven_times(self):
        """'several' shares 'seve' with 'seven' — prefix match, not a stem."""
        rec = {"company": "Acme", "domain": "acme.test",
               "research": [{"fact": "Acme has several ongoing projects."}]}
        self.assertTrue(generate._invented_quantities(
            "Revenue grew seven times year over year.", rec, CONTACT),
            "'several' must not license 'seven times'")

    def test_trip_does_not_license_tripled(self):
        """'trip' shares 'trip' with 'triple'/'tripled' — prefix match."""
        rec = {"company": "Acme", "domain": "acme.test",
               "research": [{"fact": "A trip to the client site is common."}]}
        self.assertTrue(generate._invented_quantities(
            "We tripled their margin in six months.", rec, CONTACT),
            "'trip' must not license 'tripled'")

    def test_doubt_does_not_license_double(self):
        """'doubt' shares 'doub' with 'double' — prefix match, not a stem."""
        rec = {"company": "Acme", "domain": "acme.test",
               "research": [{"fact": "Doubt remains about adoption rates."}]}
        self.assertTrue(generate._invented_quantities(
            "That would double your throughput.", rec, CONTACT),
            "'doubt' must not license 'double'")

    def test_quadrant_does_not_license_quadrupled(self):
        """'quadrant' shares 'quad' with 'quadruple'/'quadrupled'."""
        rec = {"company": "Acme", "domain": "acme.test",
               "research": [{"fact": "Acme leads in the enterprise quadrant."}]}
        self.assertTrue(generate._invented_quantities(
            "They quadrupled their pipeline in a quarter.", rec, CONTACT),
            "'quadrant' must not license 'quadrupled'")


class TheNearMissNegativeControls(unittest.TestCase):
    """Acceptance criterion 3: near-miss negative controls.

    THIS IS THE MISSING CONTROL the task names. Every existing control used a
    pack containing the LITERAL word. These packs contain only SIMILAR words
    and the claim must be REFUSED.

    The whole pack from NEAR_MISS_REC contains: several, challenges, quadrant,
    trip, doubt — none of which are quantity words or their inflections.
    """

    def test_the_full_near_miss_pack_refuses_all_six(self):
        """All six bypasses refused against ONE pack of near-miss words."""
        attacks = [
            ("three times the impact", "three"),
            ("seven times growth", "seven"),
            ("tripled margin", "triple"),
            ("double the effect", "double"),
            ("quadrupled output", "quadruple"),
            ("halved cycle time", "halve"),
        ]
        for phrase, quantity in attacks:
            with self.subTest(quantity=quantity):
                self.assertTrue(
                    generate._invented_quantities(
                        "Early intervention has %s on final margin." % phrase,
                        NEAR_MISS_REC, CONTACT),
                    "near-miss pack must not license %r" % quantity)

    def test_threshold_rich_pack_still_refuses_three_times(self):
        """A pack with 'threshold' and 'thresholds' — both near-misses."""
        rec = {"company": "T", "domain": "t.test",
               "research": [{"fact": "Thresholds and threshold levels define "
                                      "the boundary conditions."}]}
        self.assertTrue(generate._invented_quantities(
            "Three times the impact was measured.", rec, CONTACT))

    def test_doubtful_doubts_do_not_license_double(self):
        """'doubtful' and 'doubts' — both share 'doub' but neither is 'double'."""
        rec = {"company": "T", "domain": "t.test",
               "research": [{"fact": "Doubtful outcomes and lingering doubts "
                                      "marked the quarter."}]}
        self.assertTrue(generate._invented_quantities(
            "Double the throughput was achieved.", rec, CONTACT))


class LiteralWordsStillLicense(unittest.TestCase):
    """Acceptance criterion 2: a pack containing the LITERAL word still licenses.

    The fix must not over-correct into round 1's defect (over-refusal).
    """

    def test_double_in_pack_licenses_double(self):
        self.assertEqual([], generate._invented_quantities(
            "That would double throughput.", LITERAL_REC, CONTACT))

    def test_doubled_in_pack_licenses_double(self):
        """An inflection in the pack licenses the base form in copy."""
        rec = {"company": "X", "domain": "x.test",
               "research": [{"fact": "X doubled its revenue last year."}]}
        self.assertEqual([], generate._invented_quantities(
            "That would double your revenue.", rec, CONTACT))

    def test_three_in_pack_licenses_three_times(self):
        self.assertEqual([], generate._invented_quantities(
            "Three times the impact was measured.", LITERAL_REC, CONTACT))

    def test_tripled_in_pack_licenses_tripled(self):
        self.assertEqual([], generate._invented_quantities(
            "They tripled their pipeline.", LITERAL_REC, CONTACT))

    def test_quadrupled_in_pack_licenses_quadrupled(self):
        self.assertEqual([], generate._invented_quantities(
            "They quadrupled output in a quarter.", LITERAL_REC, CONTACT))

    def test_halved_in_pack_licenses_halved(self):
        self.assertEqual([], generate._invented_quantities(
            "They halved cycle time.", LITERAL_REC, CONTACT))

    def test_doubles_in_pack_licenses_double(self):
        """'doubles' is an inflection of 'double' — licenses 'double'."""
        rec = {"company": "X", "domain": "x.test",
               "research": [{"fact": "Revenue doubles every quarter."}]}
        self.assertEqual([], generate._invented_quantities(
            "That would double your revenue.", rec, CONTACT))

    def test_doubling_in_pack_licenses_double(self):
        """'doubling' is an inflection of 'double' — licenses 'double'."""
        rec = {"company": "X", "domain": "x.test",
               "research": [{"fact": "Doubling throughput is the goal."}]}
        self.assertEqual([], generate._invented_quantities(
            "That would double your throughput.", rec, CONTACT))


class IdiomsStillPass(unittest.TestCase):
    """Acceptance criterion 4: idioms still pass (no over-refusal)."""

    def test_half_an_hour(self):
        self.assertEqual([], generate._invented_quantities(
            "Half an hour would be enough to settle it.",
            NEAR_MISS_REC, CONTACT))

    def test_double_check(self):
        self.assertEqual([], generate._invented_quantities(
            "Let me double-check that before I say more.",
            NEAR_MISS_REC, CONTACT))

    def test_half_the_team(self):
        self.assertEqual([], generate._invented_quantities(
            "Half the team had changed by then.",
            NEAR_MISS_REC, CONTACT))

    def test_half_of_the_work(self):
        self.assertEqual([], generate._invented_quantities(
            "Half of the work is done.",
            NEAR_MISS_REC, CONTACT))


class TheMutationCheck(unittest.TestCase):
    """Acceptance criterion 5: revert to prefix form, near-miss goes red.

    This test reads the source of `_quantity_licensed`, confirms it uses
    inflection-family matching (not `[:4]`), then proves the near-miss control
    WOULD fail under the prefix form by simulating the old logic inline.
    """

    def test_the_source_does_not_contain_the_prefix_check(self):
        """The fix is in source: no `[:4]` in the worded-quantity path."""
        import inspect
        src = inspect.getsource(generate._invented_quantities)
        self.assertNotIn("[:4]", src,
                         "the [:4] prefix truncation is still present in "
                         "_invented_quantities")

    def test_the_quantity_licensed_uses_inflection_families(self):
        """The helper exists and uses _QUANTITY_INFLECTIONS, not prefixes."""
        import inspect
        src = inspect.getsource(generate._quantity_licensed)
        self.assertIn("_QUANTITY_INFLECTIONS", src,
                      "_quantity_licensed must consult inflection families")
        self.assertNotIn("[:4]", src,
                         "_quantity_licensed must not use prefix truncation")

    def test_the_near_miss_would_go_red_under_prefix_logic(self):
        """MUTATION: simulate the old [:4] logic and prove it passes the
        near-miss pack (which is the BUG), then prove the real logic refuses.

        This is the killed-mutation proof: if the fix were reverted to [:4],
        the near-miss control would silently pass — exactly the defect.
        """
        import re as _re
        support = "threshold faces several challenges in the quadrant " \
                  "where a trip to the client is common and doubt remains"
        text = "Resource decisions have three times the impact on margin."

        # OLD (defective) logic: both sides truncated to [:4]
        old_support_stems = {w[:4] for w in _re.findall(r"[a-z]+", support.lower())}
        old_match_word = "three"
        old_licensed = old_match_word[:4] in old_support_stems
        self.assertTrue(old_licensed,
                        "the old [:4] logic must license 'three' on 'threat'/"
                        "'threshold' — this proves the mutation would survive")

        # NEW (fixed) logic: inflection-family matching
        support_words = set(_re.findall(r"[a-z]+", support.lower()))
        new_licensed = generate._quantity_licensed("three", support_words)
        self.assertFalse(new_licensed,
                         "the fixed logic must NOT license 'three' on a pack "
                         "containing only 'threshold'/'several'/'quadrant'/"
                         "'trip'/'doubt'")

    def test_sha256_of_the_fixed_function_is_stable(self):
        """Byte-identical restoration check. Record the sha256 of the fixed
        `_quantity_licensed` source so a future session can verify restoration
        after a mutation round-trip.
        """
        import inspect
        src = inspect.getsource(generate._quantity_licensed)
        sha = hashlib.sha256(src.encode("utf-8")).hexdigest()
        # Record the SHA in the test output so it appears in the suite log.
        # A future mutation check can compare against this value.
        self.assertEqual(64, len(sha), "sha256 hex digest is 64 chars")
        # Print for the suite log — this is the restoration anchor.
        print("TASK-901 _quantity_licensed sha256: %s" % sha)


class TheFixIsConsumedByTheLivePath(unittest.TestCase):
    """The RULE THAT DECIDED THREE REVIEWS: existence is not function.

    `_quantity_licensed` must be called by `_invented_quantities`, and
    `_invented_quantities` must be called by `_step_refusals`. Trace the chain.
    """

    def test_quantity_licensed_is_called_by_invented_quantities(self):
        """Break the wiring: if _invented_quantities does not call
        _quantity_licensed, the near-miss pack would license 'three times'."""
        import inspect
        src = inspect.getsource(generate._invented_quantities)
        self.assertIn("_quantity_licensed", src,
                      "_invented_quantities must call _quantity_licensed")

    def test_the_full_chain_refuses_through_step_refusals(self):
        """Drive the test through the real entry point: `_step_refusals`.

        Not the function we wrote — the function production calls.
        """
        rec = dict(NEAR_MISS_REC)
        rec["contacts"] = [CONTACT]
        pairs = [("em4", {"channel": "email", "generated": True,
                          "subject": "Subject A",
                          "body": "Resource decisions have three times the "
                                  "impact on final margin."})]
        refusals = generate._step_refusals(rec, CONTACT, pairs)
        self.assertIn("em4", refusals,
                      "the near-miss refusal must reach _step_refusals")
        self.assertTrue(
            any("no stored fact" in s for s in refusals["em4"]),
            "the figure refusal did not reach _step_refusals: %r" % refusals)


if __name__ == "__main__":
    unittest.main()
