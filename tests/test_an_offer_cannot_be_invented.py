"""An offer cannot be invented.

Offers are DATA loaded from `config/clients/productive-offers.yaml`. No code
path in `src/offers.py` constructs an offer from an LLM response, and no
offer names a capability Productive does not have.

After TASK-367 the file has TWO blocks:
- `capabilities:` holds six capability records (the old `offers:` block,
  renamed). Each has a `capability` field, a value proposition, and no
  mechanism.
- `offers:` holds two offer records. Each references capability ids and
  does NOT restate value propositions.

The guards:
- An offer referencing a capability Productive does not have.
- `approval_status` defaulting to approved.
- `missing()` returning empty while no case study exists.
- A cta_link not in the allowlist.
"""
import ast
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import offers, copylint


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
                         "offers block must hold exactly two records")
        for offer_id, offer in all_offers.items():
            self.assertIn("approval_status", offer,
                          f"offer {offer_id} has no approval_status")

    def test_capabilities_block_has_six_records(self):
        """The capabilities block holds the six confirmed capabilities."""
        caps = offers.capabilities()
        self.assertEqual(len(caps), 6,
                         "capabilities block must hold exactly six records")
        for cap_id, cap in caps.items():
            self.assertIn("capability", cap,
                          f"capability {cap_id} has no capability field")
            self.assertIn("approval_status", cap,
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

    def test_both_offers_are_pending(self):
        """Neither offer is approved. Production does not approve its own
        offers and the operator has not yet approved them."""
        for offer_id, offer in offers.load().items():
            self.assertEqual(
                offer.get("approval_status"), "pending",
                f"offer {offer_id} is {offer.get('approval_status')!r}, "
                f"expected pending")

    def test_no_offer_is_approved_in_repo(self):
        """Grep-equivalent: no offer in the loaded data has approval_status
        set to approved. This catches a accidental edit setting one."""
        for offer_id, offer in offers.load().items():
            self.assertNotEqual(
                offer.get("approval_status"), "approved",
                f"offer {offer_id} is approved - operator has not approved "
                f"either offer yet")


class TestNoInventedCapability(unittest.TestCase):
    """An offer referencing a capability Productive does not have is
    rejected."""

    def test_every_offer_capabilities_are_confirmed(self):
        for offer_id, offer in offers.load().items():
            for cap in (offer.get("capabilities") or []):
                self.assertIn(
                    cap, offers.CONFIRMED_CAPABILITIES,
                    f"offer {offer_id} references capability {cap!r} which "
                    f"is not in Productive's confirmed capabilities")

    def test_six_capabilities_in_capabilities_block(self):
        caps = {c.get("capability") for c in offers.capabilities().values()}
        self.assertEqual(caps, offers.CONFIRMED_CAPABILITIES,
                         "capabilities block must cover exactly the six "
                         "confirmed capabilities and nothing else")


class TestOffersDoNotRestateValueProposition(unittest.TestCase):
    """An offer references capability ids; it does not restate the value
    proposition. The sentences stay in capabilities: where they are
    CLIENT_APPROVED verbatim."""

    def test_no_value_proposition_in_offers(self):
        for offer_id, offer in offers.load().items():
            self.assertNotIn(
                "value_proposition", offer,
                f"offer {offer_id} restates value_proposition - it should "
                f"reference capability ids only")


class TestCtaLinkAllowlisted(unittest.TestCase):
    """Every offer's cta_link must be in the copylint allowlist. A future
    offer cannot reintroduce a non-allowlisted link silently."""

    def test_both_offers_cta_link_in_allowlist(self):
        for offer_id, offer in offers.load().items():
            cta_link = offer.get("cta_link", "")
            self.assertIn(
                cta_link, copylint.CTA_LINK_ALLOWLIST,
                f"offer {offer_id} cta_link {cta_link!r} is not in the "
                f"allowlist: {sorted(copylint.CTA_LINK_ALLOWLIST)}")


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

    def test_missing_returns_five_gaps(self):
        gaps = offers.missing()
        self.assertEqual(len(gaps), 5,
                         f"expected 5 gaps, got {len(gaps)}")


class TestBookADemoNotInConfig(unittest.TestCase):
    """The withdrawn book-a-demo URL must not appear in config or src.
    TASK-354 removed it; TASK-367 rework confirms it stays gone."""

    def test_no_book_a_demo_in_offers(self):
        path = os.path.join(
            os.path.dirname(__file__), "..", "config", "clients",
            "productive-offers.yaml")
        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read()
        self.assertNotIn(
            "book-a-demo", content,
            "productive-offers.yaml contains 'book-a-demo' - that URL was "
            "withdrawn by TASK-354")


if __name__ == "__main__":
    unittest.main()
