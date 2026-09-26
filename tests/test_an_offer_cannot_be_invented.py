"""An offer cannot be invented.

Offers are DATA loaded from `config/clients/productive-offers.yaml`. No code
path in `src/offers.py` constructs an offer from an LLM response, and no
offer names a capability Productive does not have.

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
        self.assertTrue(len(all_offers) > 0,
                        "load() returned no offers")
        for offer_id, offer in all_offers.items():
            self.assertIn("capability", offer,
                          f"offer {offer_id} has no capability")
            self.assertIn("approval_status", offer,
                          f"offer {offer_id} has no approval_status")


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

    def test_every_offer_names_a_confirmed_capability(self):
        for offer_id, offer in offers.load().items():
            cap = offer.get("capability")
            self.assertIn(
                cap, offers.CONFIRMED_CAPABILITIES,
                f"offer {offer_id} names capability {cap!r} which is not in "
                f"Productive's confirmed capabilities")

    def test_six_capabilities_shipped(self):
        caps = {o.get("capability") for o in offers.load().values()}
        self.assertEqual(caps, offers.CONFIRMED_CAPABILITIES,
                         "offers must cover exactly the six confirmed "
                         "capabilities and nothing else")


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


class TestOfferSchema(unittest.TestCase):
    """Every offer carries the full schema from spec section 3E."""

    REQUIRED_FIELDS = {
        "capability", "segment", "persona", "business_problem",
        "value_proposition", "concrete_deliverable", "supporting_evidence",
        "cta", "conditions", "approval_status", "version", "campaigns",
    }

    def test_every_offer_has_all_schema_fields(self):
        for offer_id, offer in offers.load().items():
            present = set(offer.keys())
            missing_fields = self.REQUIRED_FIELDS - present
            self.assertFalse(
                missing_fields,
                f"offer {offer_id} is missing fields: {missing_fields}")


if __name__ == "__main__":
    unittest.main()
