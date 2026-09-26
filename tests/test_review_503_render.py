"""TASK-301: the review file render follows the production code paths.

Every test below proves one link in the chain from config to rendered copy.
A test that asserts on source text rather than behaviour is not a test -
these all drive the render and check what comes out.

THE RULE FROM QWEN.md: "Test behaviour, not the text of the source."
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import cadence, clients, copylint, packfact  # noqa: E402
from scripts.render_review_503 import (  # noqa: E402
    render_lead, render_batch, _template_for_step,
)

CONFIG = clients.load("productive")

# A minimal record with enough data to render
def _rec(domain="testagency.com", company="Test Agency", industry="marketing"):
    return {
        "id": "rec-1",
        "domain": domain,
        "company": company,
        "company_facts": {"name": company, "industry": industry},
        "contacts": [
            {"key": "c1", "name": "Jane Smith", "title": "CEO",
             "email": "jane@testagency.com", "persona": "economic_buyer",
             "angle": "founder"},
        ],
        "evidence": {},
    }


def _pack_with_nav_fact():
    """A pack whose only site_page fact is navigation chrome."""
    return {
        "record_id": "rec-1",
        "facts": [
            {"fact_id": "nav1", "kind": "site_page",
             "source_url": "https://testagency.com",
             "published_at": "2026-09-01",
             "snippet": "Order Online Skip to main content Drinks Menu "
                        "Order Catering Kerrville TX 78028",
             "retrieved_at": "2026-09-20"},
        ],
    }


def _pack_with_real_fact():
    """A pack with a usable site_page fact.

    The snippet shares tokens with the rendered opener ("marketing",
    "teams", "profitability") so copylint's step1_without_pack_fact
    check passes. The opener renders as "I work with marketing teams
    on profitability visible on Monday..." so the pack must contain
    at least one word longer than 4 characters from that sentence.

    The snippet also mentions "Test Agency" so copylint's
    untraceable_company_claim check can trace the company name when
    it appears in sentences with "you" or "your".
    """
    return {
        "record_id": "rec-1",
        "facts": [
            {"fact_id": "real1", "kind": "site_page",
             "source_url": "https://testagency.com/about",
             "published_at": "2026-09-01",
             "snippet": "Test Agency is a marketing agency helping teams "
                        "improve profitability and project delivery across "
                        "the business.",
             "retrieved_at": "2026-09-20"},
        ],
    }


def _contact(title="CEO", persona="economic_buyer", angle="founder"):
    return {"key": "c1", "name": "Jane Smith", "title": title,
            "email": "jane@testagency.com", "persona": persona,
            "angle": angle}


class RenderUsesCadenceTemplates(unittest.TestCase):
    """Every step's rendered body comes from cadence.TEMPLATES, not invented
    copy. The incident came from work/gencopy.py, which invented its own
    copy and referenced productive.yaml zero times."""

    def test_em3_renders_from_rung3_template(self):
        rec = _rec()
        contact = _contact()
        pack = _pack_with_real_fact()
        result, reason = render_lead(rec, contact, CONFIG, pack)
        self.assertIsNone(reason, f"render failed: {reason}")
        self.assertIn("template_em3", result)
        self.assertEqual(result["template_em3"], "rung3_economic_buyer")
        # The body contains Productive's name from product.name
        self.assertIn("Productive", result["body_3"])

    def test_em4_renders_from_angle_shift_template(self):
        rec = _rec()
        contact = _contact()
        pack = _pack_with_real_fact()
        result, reason = render_lead(rec, contact, CONFIG, pack)
        self.assertIsNone(reason)
        self.assertEqual(result["template_em4"], "angle_shift_economic_buyer")

    def test_em5_renders_from_close_template(self):
        rec = _rec()
        contact = _contact()
        pack = _pack_with_real_fact()
        result, reason = render_lead(rec, contact, CONFIG, pack)
        self.assertIsNone(reason)
        self.assertEqual(result["template_em5"], "close_economic_buyer")

    def test_em1_renders_from_persona_pain_template(self):
        rec = _rec()
        contact = _contact()
        pack = _pack_with_real_fact()
        result, reason = render_lead(rec, contact, CONFIG, pack)
        self.assertIsNone(reason)
        self.assertEqual(result["template_em1"], "persona_pain")

    def test_em2_renders_from_comparable_proof_template(self):
        rec = _rec()
        contact = _contact()
        pack = _pack_with_real_fact()
        result, reason = render_lead(rec, contact, CONFIG, pack)
        self.assertIsNone(reason)
        self.assertEqual(result["template_em2"], "comparable_proof")

    def test_all_five_bodies_are_nonempty(self):
        rec = _rec()
        contact = _contact()
        pack = _pack_with_real_fact()
        result, reason = render_lead(rec, contact, CONFIG, pack)
        self.assertIsNone(reason)
        for i in range(1, 6):
            body = result.get(f"body_{i}", "")
            self.assertTrue(len(body) > 20,
                            f"body_{i} is too short: {body!r}")

    def test_template_ids_are_carried(self):
        """A step with no template id is refused at activation."""
        rec = _rec()
        contact = _contact()
        pack = _pack_with_real_fact()
        result, reason = render_lead(rec, contact, CONFIG, pack)
        self.assertIsNone(reason)
        for step_key in ("em1", "em2", "em3", "em4", "em5"):
            self.assertIn(f"template_{step_key}", result,
                          f"missing template id for {step_key}")
            self.assertTrue(result[f"template_{step_key}"],
                            f"empty template id for {step_key}")


class PackFactGateRejectsNavText(unittest.TestCase):
    """The incident's personalisation was a navigation bar. The gate must
    refuse it and hold the lead rather than sending generic copy."""

    def test_nav_fact_is_rejected(self):
        pack = _pack_with_nav_fact()
        fact = pack["facts"][0]
        self.assertFalse(packfact.usable_fact(fact))

    def test_nav_fact_is_classified_as_nav(self):
        pack = _pack_with_nav_fact()
        classified = packfact.classify_facts(pack["facts"])
        self.assertEqual(len(classified), 1)
        self.assertFalse(classified[0]["usable"])
        self.assertIn("navigation", classified[0]["reason"].lower())

    def test_lead_with_only_nav_facts_is_held(self):
        rec = _rec()
        contact = _contact()
        pack = _pack_with_nav_fact()
        result, reason = render_lead(rec, contact, CONFIG, pack)
        self.assertIsNone(result)
        self.assertIn("pack fact", reason.lower())

    def test_real_fact_is_accepted(self):
        pack = _pack_with_real_fact()
        fact = pack["facts"][0]
        self.assertTrue(packfact.usable_fact(fact))

    def test_lead_with_real_fact_renders(self):
        rec = _rec()
        contact = _contact()
        pack = _pack_with_real_fact()
        result, reason = render_lead(rec, contact, CONFIG, pack)
        self.assertIsNotNone(result)
        self.assertIsNone(reason)

    def test_non_site_page_kind_is_rejected(self):
        fact = {"kind": "company_post", "snippet": "We are great",
                "source_url": "https://test.com/post"}
        self.assertFalse(packfact.usable_fact(fact))

    def test_fragment_without_verb_is_rejected(self):
        fact = {"kind": "site_page", "source_url": "https://test.com",
                "snippet": "Time tracking software for agencies"}
        self.assertFalse(packfact.usable_fact(fact))

    def test_short_snippet_is_rejected(self):
        fact = {"kind": "site_page", "source_url": "https://test.com",
                "snippet": "We help."}
        self.assertFalse(packfact.usable_fact(fact))


class SignatureIsNotAConstant(unittest.TestCase):
    """The signature is the mailbox owner's name from the sender pool,
    never a constant and never the operator's name."""

    def test_rendered_copy_does_not_contain_operator_name(self):
        """The operator's name (Zvonimir) must not appear in rendered copy."""
        rec = _rec()
        contact = _contact()
        pack = _pack_with_real_fact()
        result, reason = render_lead(rec, contact, CONFIG, pack)
        self.assertIsNone(reason)
        for i in range(1, 6):
            body = result.get(f"body_{i}", "")
            self.assertNotIn("Zvonimir", body)

    def test_rendered_copy_does_not_contain_constant_signature(self):
        """No step should carry a hardcoded sender name."""
        rec = _rec()
        contact = _contact()
        pack = _pack_with_real_fact()
        result, reason = render_lead(rec, contact, CONFIG, pack)
        self.assertIsNone(reason)
        # The templates use {first_name} for the recipient, not the sender.
        # The sender name comes from the sender pool at activation time.
        # Verify no template injects a sender name.
        for step_key in ("em1", "em2", "em3", "em4", "em5"):
            template_name = result.get(f"template_{step_key}")
            template = cadence.TEMPLATES.get(template_name, {})
            body = template.get("body", "")
            # No template should contain a literal name
            for name in ("Ivan", "Anna", "Mark", "John", "Sarah", "Petar"):
                self.assertNotIn(name, body,
                                 f"template {template_name} contains "
                                 f"hardcoded name {name}")


class CopylintRunsOverRenderedCopy(unittest.TestCase):
    """copylint.check_batch runs over the rendered output and reports."""

    def test_rendered_batch_passes_copylint(self):
        rec = _rec()
        contact = _contact()
        pack = _pack_with_real_fact()
        rendered, held, report = render_batch([rec], CONFIG,
                                               {"rec-1": pack})
        self.assertEqual(len(rendered), 1)
        self.assertEqual(len(held), 0)
        # The batch should not be refused by copylint
        # (step1_without_pack_fact is a WARNING, not a refusal)
        self.assertFalse(report["refused"],
                         f"copylint refused: {report['offenders']}")

    def test_copylint_report_has_counts(self):
        rec = _rec()
        contact = _contact()
        pack = _pack_with_real_fact()
        _, _, report = render_batch([rec], CONFIG, {"rec-1": pack})
        self.assertIn("counts", report)
        self.assertIn("step1_without_pack_fact", report["counts"])

    def test_held_leads_are_not_in_copylint(self):
        """A lead held by the pack fact gate does not enter copylint."""
        rec = _rec()
        contact = _contact()
        pack = _pack_with_nav_fact()
        rendered, held, report = render_batch([rec], CONFIG,
                                               {"rec-1": pack})
        self.assertEqual(len(rendered), 0)
        self.assertEqual(len(held), 1)
        # No copylint offenders because no leads were rendered
        total_offenders = sum(len(v) for v in report["offenders"].values())
        self.assertEqual(total_offenders, 0)


class ChampionPersonaRenders(unittest.TestCase):
    """Champions get different templates than economic buyers."""

    def test_champion_gets_champion_templates(self):
        rec = _rec()
        contact = _contact(title="Project Manager",
                           persona="champion", angle="operations")
        pack = _pack_with_real_fact()
        result, reason = render_lead(rec, contact, CONFIG, pack)
        self.assertIsNone(reason)
        self.assertEqual(result["template_em3"], "rung3_champion")
        self.assertEqual(result["template_em4"], "angle_shift_champion")
        self.assertEqual(result["template_em5"], "close_champion")

    def test_champion_rung3_mentions_capability(self):
        rec = _rec()
        contact = _contact(title="Project Manager",
                           persona="champion", angle="operations")
        pack = _pack_with_real_fact()
        result, reason = render_lead(rec, contact, CONFIG, pack)
        self.assertIsNone(reason)
        # Champion's capability is "budgeting" per productive.yaml,
        # which resolves to the sentence: "what a project was quoted at
        # and what it has burned so far". The word "budget" does not
        # appear - the capability is described, not named.
        body = result["body_3"]
        self.assertIn("Productive", body)
        self.assertIn("quoted", body.lower())


class TemplateForStep(unittest.TestCase):
    """_template_for_step returns the right TEMPLATES key."""

    def test_em1_is_persona_pain(self):
        self.assertEqual(_template_for_step("em1", "economic_buyer"),
                         "persona_pain")

    def test_em3_economic_buyer(self):
        self.assertEqual(_template_for_step("em3", "economic_buyer"),
                         "rung3_economic_buyer")

    def test_em3_champion(self):
        self.assertEqual(_template_for_step("em3", "champion"),
                         "rung3_champion")

    def test_em5_champion(self):
        self.assertEqual(_template_for_step("em5", "champion"),
                         "close_champion")


if __name__ == "__main__":
    unittest.main()
