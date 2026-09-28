"""TASK-550: the figure gate's 4-char prefix licensed fabricated multipliers.

The defect: `_invented_quantities` built its support set as `{w[:4] for w in
...}` - a four-character PREFIX, not a stem. So any word in the research pack
sharing those four characters licensed a fabricated multiplier:

    "threat" / "threshold"  ->  licenses "three times"
    "several"               ->  licenses "seven times"
    "trip"                  ->  licenses "tripled"
    "doubt"                 ->  licenses "double"
    "quadrant"              ->  licenses "quadrupled"

Six of eight attacks bypassed it. Nothing downstream caught it: `claims.check`
returns `is_claim` False, `copylint.untraceable`, `copylint.check_batch` and
`heyreachfactory.unsupported_claims` all report clean.

The fix: match on word boundaries against each quantity word's inflection
family (double/doubled/doubles, triple/tripled/triples, quadruple/quadrupled,
half/halved ...), not on a character prefix.

Acceptance:
1. All six bypasses above are REFUSED.
2. A pack containing the LITERAL word still LICENSES it (do not over-correct).
3. NEAR-MISS negative controls: pack contains only a SIMILAR word and the
   claim is refused.
4. Idioms still pass: "half an hour", "double-check".
5. Mutation: revert matcher to prefix form; near-miss control must go red.
"""

import unittest

from src import generate


# A record whose research pack contains the NEAR-MISS words that the prefix
# check would have matched, but NOT the literal quantity words.
NEAR_MISS_REC = {
    "company": "Threshold Analytics",
    "domain": "threshold-analytics.test",
    "research": [
        {"fact": "Threshold Analytics faces a threat from automated tools "
                 "and operates in several markets."},
        {"fact": "The team took a trip and had doubt about the quadrant "
                 "restructure."},
    ],
}

# A record whose research pack contains the LITERAL quantity words.
LITERAL_REC = {
    "company": "Brightmoor Studio",
    "domain": "brightmoor.test",
    "research": [
        {"fact": "Brightmoor Studio doubled its delivery throughput and "
                 "tripled margin last year."},
        {"fact": "They quadrupled capacity and halved cycle time."},
        {"fact": "The practice has seen three times the impact and seven "
                 "times the return."},
    ],
}

CONTACT = {"email": "contact@brightmoor.test", "name": "Jesse"}


class Task550PrefixDefectBypassesAreRefused(unittest.TestCase):
    """Acceptance 1: all six bypasses from the review are REFUSED."""

    def test_threat_does_not_license_three_times(self):
        """Pack contains 'threat'; claim is 'three times'. MUST REFUSE."""
        body = "Resource decisions made at 60% budget burn versus 90% have three times the impact on final margin."
        result = generate._invented_quantities(body, NEAR_MISS_REC, CONTACT)
        self.assertTrue(result, "three times must be refused when pack has 'threat' not 'three'")
        self.assertTrue(any("three times" in s for s in result),
                        "refusal must mention 'three times': %r" % result)

    def test_several_does_not_license_seven_times(self):
        """Pack contains 'several'; claim is 'seven times'. MUST REFUSE."""
        body = "Early intervention has seven times the effect on final margin."
        result = generate._invented_quantities(body, NEAR_MISS_REC, CONTACT)
        self.assertTrue(result, "seven times must be refused when pack has 'several' not 'seven'")
        self.assertTrue(any("seven times" in s for s in result),
                        "refusal must mention 'seven times': %r" % result)

    def test_trip_does_not_license_tripled(self):
        """Pack contains 'trip'; claim is 'tripled'. MUST REFUSE."""
        body = "We tripled margin for an agency like yours."
        result = generate._invented_quantities(body, NEAR_MISS_REC, CONTACT)
        self.assertTrue(result, "tripled must be refused when pack has 'trip' not 'triple/tripled'")
        self.assertTrue(any("tripled" in s for s in result),
                        "refusal must mention 'tripled': %r" % result)

    def test_doubt_does_not_license_double(self):
        """Pack contains 'doubt'; claim is 'double'. MUST REFUSE."""
        body = "Early intervention has double the effect on margin."
        result = generate._invented_quantities(body, NEAR_MISS_REC, CONTACT)
        self.assertTrue(result, "double must be refused when pack has 'doubt' not 'double'")
        self.assertTrue(any("double" in s for s in result),
                        "refusal must mention 'double': %r" % result)

    def test_quadrant_does_not_license_quadrupled(self):
        """Pack contains 'quadrant'; claim is 'quadrupled'. MUST REFUSE."""
        body = "We quadrupled capacity in six months."
        result = generate._invented_quantities(body, NEAR_MISS_REC, CONTACT)
        self.assertTrue(result, "quadrupled must be refused when pack has 'quadrant' not 'quadruple'")
        self.assertTrue(any("quadrupled" in s for s in result),
                        "refusal must mention 'quadrupled': %r" % result)

    def test_threshold_does_not_license_three_times(self):
        """Pack contains 'threshold'; claim is 'three times'. MUST REFUSE."""
        body = "That has three times the impact on delivery."
        result = generate._invented_quantities(body, NEAR_MISS_REC, CONTACT)
        self.assertTrue(result, "three times must be refused when pack has 'threshold' not 'three'")
        self.assertTrue(any("three times" in s for s in result),
                        "refusal must mention 'three times': %r" % result)


class Task550LiteralWordStillLicenses(unittest.TestCase):
    """Acceptance 2: a pack containing the LITERAL word still LICENSES it.

    Do not over-correct into round 1's defect (a gate that refuses everything).
    """

    def test_doubled_in_pack_licenses_double(self):
        """Pack says 'doubled'; copy says 'double'. MUST PASS."""
        body = "That would double throughput."
        result = generate._invented_quantities(body, LITERAL_REC, CONTACT)
        self.assertEqual([], result,
                         "pack says 'doubled', copy says 'double' - must be licensed: %r" % result)

    def test_tripled_in_pack_licenses_tripled(self):
        """Pack says 'tripled'; copy says 'tripled'. MUST PASS."""
        body = "We tripled margin last year."
        result = generate._invented_quantities(body, LITERAL_REC, CONTACT)
        self.assertEqual([], result,
                         "pack says 'tripled', copy says 'tripled' - must be licensed: %r" % result)

    def test_quadrupled_in_pack_licenses_quadrupled(self):
        """Pack says 'quadrupled'; copy says 'quadrupled'. MUST PASS."""
        body = "They quadrupled capacity in six months."
        result = generate._invented_quantities(body, LITERAL_REC, CONTACT)
        self.assertEqual([], result,
                         "pack says 'quadrupled', copy says 'quadrupled' - must be licensed: %r" % result)

    def test_halved_in_pack_licenses_halved(self):
        """Pack says 'halved'; copy says 'halved'. MUST PASS."""
        body = "They halved cycle time."
        result = generate._invented_quantities(body, LITERAL_REC, CONTACT)
        self.assertEqual([], result,
                         "pack says 'halved', copy says 'halved' - must be licensed: %r" % result)

    def test_three_times_in_pack_licenses_three_times(self):
        """Pack says 'three times'; copy says 'three times'. MUST PASS."""
        body = "That has three times the impact."
        result = generate._invented_quantities(body, LITERAL_REC, CONTACT)
        self.assertEqual([], result,
                         "pack says 'three times', copy says 'three times' - must be licensed: %r" % result)

    def test_seven_times_in_pack_licenses_seven_times(self):
        """Pack says 'seven times'; copy says 'seven times'. MUST PASS."""
        body = "That has seven times the return."
        result = generate._invented_quantities(body, LITERAL_REC, CONTACT)
        self.assertEqual([], result,
                         "pack says 'seven times', copy says 'seven times' - must be licensed: %r" % result)


class Task550NearMissNegativeControls(unittest.TestCase):
    """Acceptance 3: NEAR-MISS negative controls.

    Every existing control uses a pack containing the literal word. You must
    add controls where the pack contains only a SIMILAR word and the claim is
    refused. This is the missing control that let the prefix defect ship.
    """

    def test_threat_is_near_miss_for_three_not_a_license(self):
        """'threat' shares 4 chars with 'three' but is NOT 'three'."""
        body = "That has three times the impact."
        result = generate._invented_quantities(body, NEAR_MISS_REC, CONTACT)
        self.assertTrue(result, "near-miss 'threat' must not license 'three times'")

    def test_several_is_near_miss_for_seven_not_a_license(self):
        """'several' shares 4 chars with 'seven' but is NOT 'seven'."""
        body = "That has seven times the return."
        result = generate._invented_quantities(body, NEAR_MISS_REC, CONTACT)
        self.assertTrue(result, "near-miss 'several' must not license 'seven times'")

    def test_trip_is_near_miss_for_triple_not_a_license(self):
        """'trip' shares 4 chars with 'triple' but is NOT 'triple'."""
        body = "We tripled margin."
        result = generate._invented_quantities(body, NEAR_MISS_REC, CONTACT)
        self.assertTrue(result, "near-miss 'trip' must not license 'tripled'")

    def test_doubt_is_near_miss_for_double_not_a_license(self):
        """'doubt' shares 4 chars with 'double' but is NOT 'double'."""
        body = "That would double throughput."
        result = generate._invented_quantities(body, NEAR_MISS_REC, CONTACT)
        self.assertTrue(result, "near-miss 'doubt' must not license 'double'")

    def test_quadrant_is_near_miss_for_quadruple_not_a_license(self):
        """'quadrant' shares 4 chars with 'quadruple' but is NOT 'quadruple'."""
        body = "We quadrupled capacity."
        result = generate._invented_quantities(body, NEAR_MISS_REC, CONTACT)
        self.assertTrue(result, "near-miss 'quadrant' must not license 'quadrupled'")

    def test_threshold_is_near_miss_for_three_not_a_license(self):
        """'threshold' shares 4 chars with 'three' but is NOT 'three'."""
        body = "That has three times the impact."
        result = generate._invented_quantities(body, NEAR_MISS_REC, CONTACT)
        self.assertTrue(result, "near-miss 'threshold' must not license 'three times'")


class Task550IdiomsStillPass(unittest.TestCase):
    """Acceptance 4: idioms still pass. Do not over-correct."""

    def test_half_an_hour_is_not_a_quantity_claim(self):
        body = "Half an hour would be enough to settle it."
        result = generate._invented_quantities(body, NEAR_MISS_REC, CONTACT)
        self.assertEqual([], result,
                         "'half an hour' is an idiom, not a quantity claim: %r" % result)

    def test_double_check_is_not_a_quantity_claim(self):
        body = "Let me double-check that before I say more."
        result = generate._invented_quantities(body, NEAR_MISS_REC, CONTACT)
        self.assertEqual([], result,
                         "'double-check' is an idiom, not a quantity claim: %r" % result)

    def test_twice_last_year_is_not_a_quantity_claim(self):
        body = "I wrote twice last year and got no reply."
        result = generate._invented_quantities(body, NEAR_MISS_REC, CONTACT)
        self.assertEqual([], result,
                         "'twice last year' is an idiom, not a quantity claim: %r" % result)

    def test_half_the_team_is_not_a_quantity_claim(self):
        body = "Half the team had changed by then."
        result = generate._invented_quantities(body, NEAR_MISS_REC, CONTACT)
        self.assertEqual([], result,
                         "'half the team' is an idiom, not a quantity claim: %r" % result)


if __name__ == "__main__":
    unittest.main()
