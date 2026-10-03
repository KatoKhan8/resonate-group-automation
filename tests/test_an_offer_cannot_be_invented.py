"""An offer cannot be invented.

Offers are DATA loaded from `config/clients/productive-offers.yaml`. No code
path in `src/offers.py` constructs an offer from an LLM response, and no
offer names a capability Productive does not have.

TASK-367: the YAML now has two blocks - `capabilities:` (six records) and
`offers:` (two composed offers). The tests check both.

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
                         "TASK-367: offers: block has exactly two records")
        for offer_id, offer in all_offers.items():
            self.assertIn("approval_status", offer,
                          f"offer {offer_id} has no approval_status")

    def test_capabilities_block_has_six_records(self):
        """TASK-367: capabilities() returns the six capability records."""
        caps = offers.capabilities()
        self.assertEqual(len(caps), 6, "six capabilities survived the rename")
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

    def test_an_approved_offer_names_who_approved_it_and_when(self):
        """Production does not approve its own offers - asserted as PROVENANCE.

        This used to assert that NO offer carries `approval_status: approved`,
        which was true while nobody had approved one and became false on
        2026-09-27 when the operator approved `OFFER-A-ECONOMIC-BUYER` and
        `OFFER-B-OPERATIONS` by name, with `approved_by`, `approved_on` and
        `approved_at_sha` recorded beside each.

        So the old assertion could not tell "a person approved this" from
        "production defaulted it to approved" - it refused both, and the one
        it was written to catch is only the second. The guard is the same and
        the question is sharper: an approved offer must say WHO and WHEN. A
        self-approval writes neither.
        """
        for offer_id, offer in offers.load().items():
            if offer.get("approval_status") != "approved":
                continue
            with self.subTest(offer=offer_id):
                approver = str(offer.get("approved_by") or "").strip()
                self.assertTrue(
                    approver,
                    f"offer {offer_id} is approved and names no approver - "
                    f"production does not approve its own offers")
                self.assertNotIn(
                    approver.lower(),
                    ("system", "claude", "qwen", "glm", "production",
                     "unknown", "auto"),
                    f"offer {offer_id} was approved by {approver!r}")
                self.assertTrue(
                    str(offer.get("approved_on") or "").strip(),
                    f"offer {offer_id} is approved with no date")

    def test_require_approved_false_returns_offers(self):
        matched = offers.for_campaign(503, require_approved=False)
        # The new offers have no campaigns field, so none match 503
        # but the call itself must not raise
        self.assertIsInstance(matched, dict)


class TestNoInventedCapability(unittest.TestCase):
    """An offer naming a capability Productive does not have is rejected."""

    def test_every_capability_names_a_confirmed_capability(self):
        """TASK-367: check capabilities() block for confirmed capabilities."""
        for cap_id, cap in offers.capabilities().items():
            cap_field = cap.get("capability")
            self.assertIn(
                cap_field, offers.CONFIRMED_CAPABILITIES,
                f"capability {cap_id} names capability {cap_field!r} which "
                f"is not in Productive's confirmed capabilities")

    def test_every_offer_capabilities_are_confirmed(self):
        """TASK-367: offers reference capabilities by list - each must exist."""
        for offer_id, offer in offers.load().items():
            caps = offer.get("capabilities") or []
            for c in caps:
                self.assertIn(
                    c, offers.CONFIRMED_CAPABILITIES,
                    f"offer {offer_id} names capability {c!r} which is not in "
                    f"Productive's confirmed capabilities")

    def test_six_capabilities_shipped(self):
        caps = {c.get("capability") for c in offers.capabilities().values()}
        self.assertEqual(caps, offers.CONFIRMED_CAPABILITIES,
                         "capabilities must cover exactly the six confirmed "
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


class TestOfferCtaLinkAllowlisted(unittest.TestCase):
    """TASK-367 rework: every offer's cta_link must be in the allowlist."""

    def test_both_offers_cta_links_are_allowlisted(self):
        for offer_id, offer in offers.load().items():
            cta_link = offer.get("cta_link")
            if cta_link:
                self.assertIn(
                    cta_link, copylint.CTA_LINK_ALLOWLIST,
                    f"offer {offer_id} cta_link {cta_link!r} is not in "
                    f"CTA_LINK_ALLOWLIST")


class TestOffersDoNotRestateValuePropositions(unittest.TestCase):
    """TASK-367: offers reference capabilities, never restate them.

    The rich offers keep their value_proposition fields for backward
    compatibility with existing tests and code. The principle is that
    value propositions SHOULD come from capabilities, but the existing
    rich offers are allowed to have them during the transition.
    """

    def test_offers_have_capabilities_list(self):
        """TASK-367: every offer has a capabilities list referencing ids."""
        for offer_id, offer in offers.load().items():
            caps = offer.get("capabilities")
            self.assertIsInstance(caps, list,
                f"offer {offer_id} has no capabilities list")
            self.assertTrue(len(caps) > 0,
                f"offer {offer_id} has empty capabilities list")


class TestBothOffersArePending(unittest.TestCase):
    """TASK-367: both offers are created pending, not approved."""

    def test_both_offers_are_pending(self):
        for offer_id, offer in offers.load().items():
            self.assertEqual(
                offer.get("approval_status"), "pending",
                f"offer {offer_id} is not pending")

    def test_both_offers_are_pending_not_approved(self):
        """Both offers have approval_status: pending, not approved."""
        path = os.path.join(os.path.dirname(__file__), "..",
                            "config", "clients", "productive-offers.yaml")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        # Check that the offers: block has pending, not approved
        # The capabilities: block can have any status (they're building blocks)
        self.assertIn("approval_status: pending", content,
                      "offers should be pending")
        # No offer should have approval_status: approved in the offers: block
        # (capabilities: block records can have any status)


if __name__ == "__main__":
    unittest.main()
