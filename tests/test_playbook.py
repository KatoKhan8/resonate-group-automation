"""PLAYBOOK.md is a contract, so it is checked rather than trusted.

A document that states rules the code does not enforce is worse than no
document: it tells a reader the system is safe in ways it is not. These tests
do two things. They assert the file exists and still names each rule the
project instructions promise it names, and - where the rule is mechanically
checkable - they assert the code still behaves the way the document says.

The second half is the point. Anyone can keep prose alive; what rots is the
agreement between prose and behaviour.
"""
import os
import re
import unittest

from src import dmplan, icp, push, routing, store, waterfall

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAYBOOK = os.path.join(ROOT, "PLAYBOOK.md")


def text():
    with open(PLAYBOOK, encoding="utf-8") as f:
        return f.read()


class TestItExists(unittest.TestCase):
    """CLAUDE.md and BUILD-SPEC both point at this file by name."""

    def test_the_playbook_is_present(self):
        self.assertTrue(os.path.exists(PLAYBOOK),
                        "CLAUDE.md names PLAYBOOK.md as the operating contract")

    def test_it_is_not_a_stub(self):
        self.assertGreater(len(text()), 4000)

    def test_the_documents_it_points_at_all_exist(self):
        for name in re.findall(r"`([A-Z][A-Z-]+\.md)`", text()):
            self.assertTrue(os.path.exists(os.path.join(ROOT, name)), name)


class TestItNamesEveryRuleItWasAskedTo(unittest.TestCase):
    """One assertion per topic, so a deletion is a named failure."""

    TOPICS = {
        "company-first qualification": "company first",
        "productive icp": "qualif",
        "evidence discipline": "missing information is never positive",
        "contactout-first": "contactout is first",
        "paid fallback discipline": "fallback",
        "persona routing": "persona routing",
        "channel eligibility": "reachability is two verdicts",
        "mx filtering": "mimecast",
        "research discipline": "apify",
        "personalisation discipline": "claims.py",
        "approval gates": "approval gates",
        "local-time scheduling": "iana",
        "reply/pause behaviour": "pauses",
        "no guessing": "guessed timezone is worse",
        "no silent drops": "never delete a queue record",
        "live-send safety": "livesendnotenabled",
    }

    def test_every_required_topic_is_covered(self):
        body = text().lower()
        for topic, marker in self.TOPICS.items():
            self.assertIn(marker, body, f"PLAYBOOK.md no longer covers {topic}")


class TestTheClaimsAreStillTrue(unittest.TestCase):
    """Where the document states a fact about the code, check the code."""

    def test_live_send_really_does_refuse(self):
        with self.assertRaises(push.LiveSendNotEnabled):
            push.run(live=True)

    def test_the_record_states_are_the_ones_documented(self):
        body = text()
        for state in ("queued", "enriched", "verified", "drafted", "approved",
                      "pushed", "dropped", "held"):
            self.assertIn(state, body, state)
            self.assertIn(state, store.STATES, state)

    def test_the_qualification_substates_are_the_ones_documented(self):
        body = text()
        for state in dmplan.STATES:
            self.assertIn(state, body, state)

    def test_the_five_persona_families_are_the_ones_documented(self):
        body = text()
        for family in routing.PERSONA_FAMILIES:
            self.assertIn(family, body, family)

    def test_the_tier_caps_are_the_ones_documented(self):
        """The document promises A:3, B:2, C:1, review and rejected 0."""
        caps = routing.DEFAULT_CAPS
        self.assertEqual(caps[icp.TIER_A], 3)
        self.assertEqual(caps[icp.TIER_B], 2)
        self.assertEqual(caps[icp.TIER_C], 1)
        self.assertEqual(caps[icp.TIER_REVIEW], 0)
        self.assertEqual(caps[icp.TIER_NOT_ICP], 0)

    def test_every_fallback_reason_listed_is_a_real_one(self):
        """A reason in the document that the code does not know is a lie."""
        from src import enrich
        body = text()
        for reason in re.findall(r"\b(contactout_[a-z_]+|public_evidence_\w+)\b",
                                 body):
            self.assertIn(reason, enrich.FALLBACK_REASONS, reason)

    def test_contactout_really_is_first_at_every_stage(self):
        for stage in waterfall.STAGE_NAMES:
            self.assertTrue(waterfall.contactout_is_first(stage), stage)

    def test_only_qualified_companies_may_be_enriched(self):
        self.assertEqual(tuple(dmplan.ENRICHABLE), (dmplan.DM_APPROVED,))


if __name__ == "__main__":
    unittest.main()
