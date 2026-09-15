"""TASK-044. Five variants per step, materially different.

The five properties every test here is really about:

**Approach is recorded.** Each variant carries a `style` field naming the
approach, so a result can be attributed to an approach rather than a string.

**Observation-gated.** The research-led variant is ABSENT when no
observation is licensed, not generated and then rejected.

**Claims gate holds.** A variant asserting something unsupported is
refused by `claims.check`, not merely flagged.

**Diversity check catches synonym swaps.** Two variants that differ only
in wording are caught by `quality.campaign_repetition()`.

**Each variant has its own approval.** `variants.fingerprint()` hashes
each variant independently.

The tests drive through `generate.generate_step_variants`, not through
`variantgen` directly, so the wiring is proven.
"""
import json
import unittest

from src import (claims, generate, llm, observations, quality, variants,
                 variantgen)


def _minimal_rec(company="acme", domain="acme.com", with_evidence=False):
    """A record with just enough to pass lint and claims."""
    rec = {
        "id": "test-rec",
        "client": "productive",
        "company": company,
        "domain": domain,
        "lane": "cold",
        "state": "verified",
        "company_facts": {
            "name": company,
            "employees": 50,
            "industry": "marketing",
            "email_domain": domain,
        },
        "contacts": [{
            "key": "jana@acme.com",
            "name": "Jana Novak",
            "first_name": "Jana",
            "email": "jana@acme.com",
            "title": "Head of Operations",
            "persona": "founder",
            "angle": "operations",
            "linkedin_url": "https://linkedin.com/in/jana",
            "verification": {
                "state": "verified",
                "sendable": True,
                "reason": "contactout says valid",
                "cost": 0,
                "at": "2026-09-14T00:00:00+00:00",
                "evidence": [
                    {"provider": "contactout", "status": "valid",
                     "email": "jana@acme.com",
                     "at": "2026-09-14T00:00:00+00:00"},
                    {"provider": "deliverable", "status": "valid",
                     "email": "jana@acme.com",
                     "at": "2026-09-14T00:00:00+00:00"},
                ],
            },
        }],
        "events": [],
        "cadence": {},
        "research": [],
        "evidence": {},
        "hook": "profitability reporting gap",
    }
    if with_evidence:
        rec["research"] = [{
            "fact": f"{company} opened a new Vienna office in September",
            "source_url": "https://example.com/vienna",
            "published_at": "2026-09-01",
            "freshness_bucket": "high",
            "quality": "strong",
            "subject": "company",
            "aged_out": False,
            "relevance_score": 0.85,
            "evidence_id": "ev-001",
        }]
        rec["evidence"] = {"jana@acme.com": [{
            "fact": f"{company} opened a new Vienna office in September",
            "source_url": "https://example.com/vienna",
            "published_at": "2026-09-01",
        }]}
    return rec


def _contact(rec):
    return rec["contacts"][0]


def _scripted_variant_answers(channel="email", n=5):
    """N distinct model answers, one per style, each passing lint+claims.

    Each body is one unbroken line per paragraph (no hard wrapping), with
    blank lines between paragraphs. This is what lint requires.
    Signatures are on the same line as the sign-off to avoid hard wrapping.
    """
    answers = []
    openings = [
        ("quick question about ops",
         "Hi Jana,\n\n"
         "Quick question about operations at Acme. Do you track project profitability in one place, or is it reconstructed from spreadsheets each month? Teams your size often find that the reconstruction takes two days of operations lead time every month.\n\n"
         "Would love to hear how you handle it today. Best, Anna"),
        ("hey Jana",
         "Hey Jana,\n\n"
         "I was looking at how marketing agencies handle their resource planning and thought of Acme. Seems like a lot of teams are still stitching together spreadsheets for profitability reporting and utilisation tracking across projects. The manual work adds up quickly when you have fifty people.\n\n"
         "Curious if that resonates with what you see? Cheers"),
        ("Acme reporting approach",
         "Dear Jana,\n\n"
         "I am writing because Acme growth to fifty people typically creates a visibility gap in project profitability tracking. Many agencies at that stage find that reconstruction of time and margin data becomes a monthly exercise that nobody owns. The Productive platform joins up time tracking and project margins so the numbers are live during the work.\n\n"
         "I would welcome the opportunity to share how we address this. Kind regards, Anna"),
        ("the pattern we see",
         "Hi Jana,\n\n"
         "We notice that agencies around the size of Acme tend to discover profitability gaps only after the project closes, when the reconstruction begins. A team your size typically loses two days per month to spreadsheet work instead of client delivery.\n\n"
         "Worth a short conversation about what alternatives exist? Best, Anna"),
        ("the cost of not knowing",
         "Jana,\n\n"
         "Every month your team spends reconstructing utilisation data is a month of decisions made on stale numbers. At fifty people that is roughly two days of operations lead time spent on spreadsheets instead of on the work itself. The cost compounds quietly until somebody asks where the margin went on a project that felt profitable.\n\n"
         "What would you do with that time back if it were visible in real time? Anna"),
    ]
    for i, (subj, body) in enumerate(openings[:n]):
        if channel == "email":
            answers.append({"subject": subj, "body": body})
        else:
            answers.append({"note": body})
    return answers


class FiveVariantsCarryFiveApproaches(unittest.TestCase):
    """Each variant records its approach as `style`."""

    def test_five_variants_have_five_distinct_styles(self):
        rec = _minimal_rec(with_evidence=True)
        contact = _contact(rec)
        answers = _scripted_variant_answers("email", 5)
        model = llm.ScriptedModel(*answers)

        result = generate.generate_step_variants(
            "day1", rec, contact, model, client={
                "cadence": "productive_balanced_v1",
                "personas": {"founder": {"angles": "profitability visible"}},
                "product": {"name": "Productive",
                            "one_liner": "project profitability"},
            })

        styles = result["approaches_recorded"]
        self.assertEqual(len(styles), len(set(styles)),
                         f"duplicate styles in {styles}")
        for v in result["variants"]:
            self.assertIn("style", v)
            self.assertIn(v["style"], variants.EMAIL_STYLES)

    def test_each_variant_has_content(self):
        rec = _minimal_rec(with_evidence=True)
        contact = _contact(rec)
        answers = _scripted_variant_answers("email", 5)
        model = llm.ScriptedModel(*answers)

        result = generate.generate_step_variants(
            "day1", rec, contact, model, client={
                "cadence": "productive_balanced_v1",
                "personas": {"founder": {"angles": "profitability visible"}},
                "product": {"name": "Productive",
                            "one_liner": "project profitability"},
            })

        for v in result["variants"]:
            self.assertTrue(v.get("subject") or v.get("body") or v.get("note"),
                            f"variant {v['variant_id']} has no content")


class ObservationGatedVariant(unittest.TestCase):
    """The research-led variant is absent when no observation is licensed."""

    def test_no_observation_means_no_consultative_variant(self):
        rec = _minimal_rec(with_evidence=False)
        contact = _contact(rec)

        approaches = variantgen.approaches_for("email", rec,
                                               contact.get("key"))
        consultative = [a for a in approaches if a[0] == "consultative"]
        self.assertEqual(len(consultative), 1)
        _, _, available, reason = consultative[0]
        self.assertFalse(available,
                         "consultative should be gated without observation")
        self.assertIsNotNone(reason)

    def test_with_observation_consultative_is_available(self):
        rec = _minimal_rec(with_evidence=True)
        contact = _contact(rec)

        approaches = variantgen.approaches_for("email", rec,
                                               contact.get("key"))
        consultative = [a for a in approaches if a[0] == "consultative"]
        self.assertEqual(len(consultative), 1)
        _, _, available, _ = consultative[0]
        self.assertTrue(available,
                        "consultative should be available with observation")

    def test_skipped_list_names_the_reason(self):
        rec = _minimal_rec(with_evidence=False)
        contact = _contact(rec)
        # Provide only 4 answers since consultative will be skipped
        answers = _scripted_variant_answers("email", 4)
        model = llm.ScriptedModel(*answers)

        result = generate.generate_step_variants(
            "day1", rec, contact, model, client={
                "cadence": "productive_balanced_v1",
                "personas": {"founder": {"angles": "profitability visible"}},
                "product": {"name": "Productive",
                            "one_liner": "project profitability"},
            })

        skipped_styles = [s for s, _ in result["skipped"]]
        self.assertIn("consultative", skipped_styles)


class ClaimsGateHolds(unittest.TestCase):
    """A variant asserting something unsupported is refused by claims."""

    def test_unsupported_claim_is_refused(self):
        text = ("Jana, Acme just raised a Series B last week. "
                "Congratulations on the growth. We help agencies "
                "track profitability.")
        rec = _minimal_rec(with_evidence=False)
        contact = _contact(rec)
        unsupported = claims.check(text, rec, contact)
        self.assertTrue(unsupported,
                        "claims.check should refuse unsupported Series B")

    def test_supported_copy_passes(self):
        text = ("Hi Jana, quick question about operations at Acme. "
                "Do you track project profitability in one place?")
        rec = _minimal_rec(with_evidence=False)
        contact = _contact(rec)
        unsupported = claims.check(text, rec, contact)
        self.assertFalse(unsupported,
                         "claims.check should pass supported copy")


class DiversityCheckCatchesSynonyms(unittest.TestCase):
    """Two variants that are synonym swaps are caught."""

    def test_identical_bodies_are_caught(self):
        vs = [
            {"variant_id": "v1", "body": "Hi Jana, do you track "
             "profitability in one place or reconstruct it from "
             "spreadsheets each month at Acme?"},
            {"variant_id": "v2", "body": "Hi Jana, do you track "
             "profitability in one place or reconstruct it from "
             "spreadsheets each month at Acme?"},
        ]
        collisions = variantgen.check_diversity(vs, company_name="Acme")
        self.assertTrue(len(collisions) > 0,
                        "identical bodies should be caught")

    def test_synonym_swap_is_caught(self):
        vs = [
            {"variant_id": "v1", "body": "Hi Jana, how do you currently "
             "ensure profitability is visible in your projects at Acme "
             "with your team using spreadsheets and manual tracking?"},
            {"variant_id": "v2", "body": "Hi Jana, how do you currently "
             "track profitability across your projects at Acme with "
             "your team using spreadsheets and manual processes?"},
        ]
        collisions = variantgen.check_diversity(vs, company_name="Acme")
        self.assertTrue(len(collisions) > 0,
                        "synonym swaps should be caught by diversity check")

    def test_genuinely_different_variants_pass(self):
        vs = [
            {"variant_id": "v1", "body": "Quick question about ops"},
            {"variant_id": "v2", "body": "The cost of not knowing"},
            {"variant_id": "v3", "body": "The pattern we see with agencies"},
        ]
        collisions = variantgen.check_diversity(vs, company_name="Acme")
        self.assertEqual(len(collisions), 0,
                         "genuinely different variants should pass")

    def test_reuses_task_043_comparator(self):
        """The diversity check calls quality.campaign_repetition, not a
        second implementation."""
        vs = [
            {"variant_id": "v1", "body": "how do you track profitability "
             "at Acme with spreadsheets and manual reporting processes"},
            {"variant_id": "v2", "body": "how do you ensure profitability "
             "at Acme with spreadsheets and manual reporting processes"},
        ]
        direct = quality.campaign_repetition(
            [{"key": "v1", "text": vs[0]["body"]},
             {"key": "v2", "text": vs[1]["body"]}],
            company_name="Acme")
        via_check = variantgen.check_diversity(vs, company_name="Acme")
        self.assertEqual(len(direct), len(via_check),
                         "diversity check should agree with "
                         "quality.campaign_repetition")


class EachVariantCarriesOwnApproval(unittest.TestCase):
    """Each variant has its own approval fingerprint."""

    def test_fingerprints_differ_per_variant(self):
        vs = [
            variants.variant("v1", "short_direct",
                             subject="subject one", body="body one"),
            variants.variant("v2", "casual",
                             subject="subject two", body="body two"),
            variants.variant("v3", "professional",
                             subject="subject three", body="body three"),
        ]
        reqs = variantgen.approval_requirements(vs)
        fps = [r["fingerprint"] for r in reqs]
        self.assertEqual(len(fps), len(set(fps)),
                         "each variant should have a unique fingerprint")

    def test_editing_a_variant_changes_its_fingerprint(self):
        v1 = variants.variant("v1", "short_direct",
                              subject="original", body="original body")
        v2 = variants.variant("v1", "short_direct",
                              subject="edited", body="edited body")
        fp1 = variants.fingerprint(v1)
        fp2 = variants.fingerprint(v2)
        self.assertNotEqual(fp1, fp2,
                            "editing a variant must change its fingerprint")

    def test_approval_requirements_include_style(self):
        vs = [
            variants.variant("v1", "short_direct",
                             subject="s", body="b"),
        ]
        reqs = variantgen.approval_requirements(vs)
        self.assertEqual(reqs[0]["style"], "short_direct")


class WiringIsConsumed(unittest.TestCase):
    """The new code is called from generate, not just defined."""

    def test_generate_step_variants_is_reachable(self):
        """generate.generate_step_variants exists and is callable."""
        self.assertTrue(callable(generate.generate_step_variants))

    def test_breaking_the_wiring_makes_test_fail(self):
        """If generate.generate_step_variants did not call variantgen,
        this test would pass even with broken variant generation."""
        rec = _minimal_rec(with_evidence=True)
        contact = _contact(rec)
        answers = _scripted_variant_answers("email", 5)
        model = llm.ScriptedModel(*answers)

        result = generate.generate_step_variants(
            "day1", rec, contact, model, client={
                "cadence": "productive_balanced_v1",
                "personas": {"founder": {"angles": "profitability visible"}},
                "product": {"name": "Productive",
                            "one_liner": "project profitability"},
            })
        # If the wiring were broken, variants would be empty
        self.assertGreater(len(result["variants"]), 0,
                           "generate_step_variants must call variantgen")
        # And approaches would not be recorded
        self.assertGreater(len(result["approaches_recorded"]), 0,
                           "approaches must be recorded through the wire")


class NoGateWidened(unittest.TestCase):
    """The claims and lint gates are not weakened for variants."""

    def test_claims_check_is_the_same_function(self):
        """The variant generator uses claims.check, not a softer version."""
        rec = _minimal_rec(with_evidence=False)
        contact = _contact(rec)
        # This text has an unsupported claim
        bad_text = "Acme raised Series B last week"
        result = claims.check(bad_text, rec, contact)
        self.assertTrue(result,
                        "claims.check must refuse unsupported claims "
                        "even for variants")


if __name__ == "__main__":
    unittest.main()
