"""An offer cannot be invented.

Offers are DATA loaded from `config/clients/productive-offers.yaml`. No code
path in `src/offers.py` constructs an offer from an LLM response, and no
offer names a capability Productive does not have.

TASK-367: two blocks, two jobs. `capabilities:` holds the six confirmed
capability records. `offers:` holds persona-to-offer records that reference
capability ids without restating value propositions.

The four false-pass guards from TASK-318:
- An offer naming a capability Productive does not have.
- An invented deliverable, discount, guarantee or commercial term.
- `approval_status` defaulting to approved.
- `missing()` returning empty while no case study exists.
"""
import ast
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import offers


class TestOfferIsDataNotGenerated(unittest.TestCase):
    """No code path in src/offers.py builds an offer from an LLM response."""

    def test_offers_module_has_no_llm_import(self):
        """The offers module does not import any generation or LLM module."""
        path = os.path.join(os.path.dirname(__file__), "..", "src", "offers.py")
        with open(path, "r", encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        forbidden = {"generate", "copyprompts", "copystages", "llm",
                      "openai", "anthropic", "copyengine"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(
                        alias.name.split(".")[0], forbidden,
                        f"offers.py imports {alias.name!r} - offers are data, "
                        f"never generated")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    self.assertNotIn(
                        node.module.split(".")[0], forbidden,
                        f"offers.py imports from {node.module!r} - offers are "
                        f"data, never generated")

    def test_load_reads_only_from_yaml(self):
        """load() reads from the YAML file, not from any generated source."""
        all_offers = offers.load()
        self.assertIsInstance(all_offers, dict)
        self.assertEqual(len(all_offers), 2,
                         "load() should return exactly two offers")
        for offer_id, offer in all_offers.items():
            self.assertIn("persona", offer,
                          f"offer {offer_id} has no persona")
            self.assertIn("capabilities", offer,
                          f"offer {offer_id} has no capabilities list")
            self.assertIn("approval_status", offer,
                          f"offer {offer_id} has no approval_status")

    def test_capabilities_block_has_six_records(self):
        """capabilities() returns the six confirmed capability records."""
        caps = offers.capabilities()
        self.assertEqual(len(caps), 6, "lost a capability")
        for cap_id, record in caps.items():
            self.assertIn("capability", record,
                          f"capability {cap_id} has no capability field")
            self.assertIn("value_proposition", record,
                          f"capability {cap_id} has no value_proposition")
            self.assertIn("approval_status", record,
                          f"capability {cap_id} has no approval_status")


class TestApprovalRefusal(unittest.TestCase):
    """An unapproved offer cannot reach copy generation. A refusal, not a
    warning - same shape as reviewapproval."""

    def test_unapproved_offer_raises_for_campaign_503(self):
        ok = False
        try:
            offers.for_campaign(503, require_approved=True)
        except offers.NotApproved:
            ok = True
        self.assertTrue(ok, "an unapproved offer reached a campaign")

    def test_approval_status_is_not_defaulted_to_approved(self):
        for offer_id, offer in offers.load().items():
            self.assertNotEqual(
                offer.get("approval_status"), "approved",
                f"offer {offer_id} has approval_status='approved' - "
                f"production does not approve its own offers")

    def test_require_approved_false_returns_unapproved(self):
        matched = offers.for_campaign(503, require_approved=False)
        self.assertTrue(len(matched) > 0,
                        "campaign 503 should have offers assigned")
        for offer_id, offer in matched.items():
            self.assertNotEqual(
                offer.get("approval_status"), "approved",
                f"offer {offer_id} should not be approved")


class TestNoInventedCapability(unittest.TestCase):
    """An offer naming a capability Productive does not have is rejected."""

    def test_every_offer_capabilities_are_confirmed(self):
        """Every capability id in every offer is a confirmed capability."""
        for offer_id, offer in offers.load().items():
            for cap in offer.get("capabilities", []):
                self.assertIn(
                    cap, offers.CONFIRMED_CAPABILITIES,
                    f"offer {offer_id} names capability {cap!r} which is not "
                    f"in Productive's confirmed capabilities")

    def test_six_capabilities_in_capabilities_block(self):
        """The capabilities block covers exactly the six confirmed caps."""
        caps = {r.get("capability") for r in offers.capabilities().values()}
        self.assertEqual(caps, offers.CONFIRMED_CAPABILITIES,
                         "capabilities block must cover exactly the six "
                         "confirmed capabilities and nothing else")

    def test_billing_is_not_in_any_offer(self):
        """billing is a capability but not placed in any offer - operator
        decision pending."""
        for offer_id, offer in offers.load().items():
            self.assertNotIn(
                "billing", offer.get("capabilities", []),
                f"offer {offer_id} contains billing - operator has not "
                f"placed it in an offer")


class TestOffersReferenceNeverRestate(unittest.TestCase):
    """An offer references capability ids; it never restates a value
    proposition. Copying a sentence into the offer creates a second truth."""

    def test_no_offer_has_value_proposition(self):
        for offer_id, offer in offers.load().items():
            self.assertNotIn(
                "value_proposition", offer,
                f"offer {offer_id} has a value_proposition - offers "
                f"reference capabilities, they do not restate them")

    def test_no_offer_has_business_problem(self):
        for offer_id, offer in offers.load().items():
            self.assertNotIn(
                "business_problem", offer,
                f"offer {offer_id} has a business_problem - offers use "
                f"'problem', not the capability's 'business_problem'")


class TestMissingIsNotEmpty(unittest.TestCase):
    """missing() returns what the client must supply. It is never empty
    while no case study exists."""

    def test_missing_is_not_empty(self):
        gaps = offers.missing()
        self.assertTrue(len(gaps) > 0,
                        "missing() returned empty while no case study exists")

    def test_missing_includes_case_studies(self):
        gap_names = [g["gap"] for g in offers.missing()]
        self.assertTrue(
            any("case stud" in g.lower() for g in gap_names),
            f"missing() does not list customer case studies: {gap_names}")

    def test_missing_includes_demo_link(self):
        gap_names = [g["gap"] for g in offers.missing()]
        self.assertTrue(
            any("demo" in g.lower() for g in gap_names),
            f"missing() does not list a demo link: {gap_names}")

    def test_missing_returns_five_gaps(self):
        gaps = offers.missing()
        self.assertEqual(len(gaps), 5,
                         f"expected 5 gaps, got {len(gaps)}")


class TestOfferSchema(unittest.TestCase):
    """Every offer carries the TASK-367 persona-to-offer schema."""

    REQUIRED_FIELDS = {
        "persona", "capabilities", "problem", "mechanism",
        "cta_link", "approval_status",
    }

    def test_every_offer_has_all_schema_fields(self):
        for offer_id, offer in offers.load().items():
            present = set(offer.keys())
            missing_fields = self.REQUIRED_FIELDS - present
            self.assertFalse(
                missing_fields,
                f"offer {offer_id} is missing fields: {missing_fields}")

    def test_both_offers_are_pending(self):
        for offer_id, offer in offers.load().items():
            self.assertEqual(
                offer.get("approval_status"), "pending",
                f"offer {offer_id} should be pending, got "
                f"{offer.get('approval_status')!r}")

    def test_offer_a_names_economic_buyer(self):
        offer = offers.load().get("OFFER-A-ECONOMIC-BUYER")
        self.assertIsNotNone(offer, "OFFER-A-ECONOMIC-BUYER missing")
        self.assertEqual(offer["persona"], "economic_buyer")
        self.assertEqual(offer["capabilities"], ["profitability", "budgeting"])
        self.assertEqual(offer["mechanism"], "demo")

    def test_offer_b_names_champion(self):
        offer = offers.load().get("OFFER-B-OPERATIONS")
        self.assertIsNotNone(offer, "OFFER-B-OPERATIONS missing")
        self.assertEqual(offer["persona"], "champion")
        self.assertEqual(offer["capabilities"],
                         ["project_management", "time_tracking", "resource_planning"])
        self.assertEqual(offer["mechanism"], "free_trial")


class TestOfferForPersona(unittest.TestCase):
    """offer_for_persona resolves the right offer for each persona."""

    def test_economic_buyer_gets_offer_a(self):
        result = offers.offer_for_persona("economic_buyer")
        self.assertIsNotNone(result)
        oid, offer = result
        self.assertEqual(oid, "OFFER-A-ECONOMIC-BUYER")

    def test_champion_gets_offer_b(self):
        result = offers.offer_for_persona("champion")
        self.assertIsNotNone(result)
        oid, offer = result
        self.assertEqual(oid, "OFFER-B-OPERATIONS")

    def test_unknown_persona_returns_none(self):
        result = offers.offer_for_persona("nobody")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
