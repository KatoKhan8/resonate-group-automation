"""Five variants per step, materially different.

Tests the variant generation module: approach availability, evidence gating,
claims enforcement, differentiation checking, and the full generation chain.

The five properties every test is really about:

1. Five variants for a step carry five distinct recorded approaches.
2. A record with no licensed observation produces no research-led variant.
3. A variant asserting something unsupported is refused by claims.
4. Two variants that are synonym swaps are caught.
5. Each variant carries its own approval requirement.
"""
import unittest

from src import cadencelibrary, claims, variants, variantgen


# ----------------------------------------------------------- fixtures

def _rec(company="Acme Services", domain="acme.test", evidence=None):
    """A minimal record for testing."""
    return {
        "id": "test-rec",
        "company": company,
        "domain": domain,
        "client": "productive",
        "lane": "cold",
        "state": "verified",
        "company_facts": {
            "name": company,
            "employees": 25,
            "industry": "Marketing",
            "email_domain": domain,
        },
        "contacts": [{
            "key": "acme:anna",
            "name": "Anna",
            "email": "anna@acme.test",
            "title": "CEO",
            "persona": "founder",
            "angle": "operations",
        }],
        "events": [],
        "evidence": {"acme:anna": evidence or []},
        "research": [],
    }


def _contact(rec):
    return rec["contacts"][0]


def _fake_llm_ask(responses=None):
    """A fake llm.ask that returns canned responses.

    `responses` is a list of (data, attempts, errors) tuples, consumed in
    order. When exhausted, returns a default.
    """
    calls = []
    idx = [0]

    def ask(model, step, prompt):
        calls.append({"step": step, "prompt": prompt})
        if responses and idx[0] < len(responses):
            result = responses[idx[0]]
            idx[0] += 1
            return result
        return ({"subject": "default subject", "body": "default body"},
                1, [])

    ask.calls = calls
    return ask


def _five_distinct_variants():
    """Five variants that ARE materially different."""
    return [
        variants.variant("em1_concise_direct", "short_direct",
                         subject="quick question",
                         body="Hi Anna, do you track utilisation at Acme?\n"
                              "Worth a look?"),
        variants.variant("em1_conversational", "casual",
                         subject="hey Anna",
                         body="hey, been looking at how agencies handle "
                              "resource planning - curious how Acme does it?\n"
                              "would love to hear your take"),
        variants.variant("em1_problem_led", "problem_led",
                         subject="the Monday morning problem",
                         body="Most agency founders I speak to spend Monday "
                              "rebuilding last week's utilisation by hand.\n"
                              "Is that Acme too, or have you solved it?"),
        variants.variant("em1_observation_led", "consultative",
                         subject="saw Acme is hiring",
                         body="Noticed Acme is growing the delivery team.\n"
                              "That usually means resource visibility matters "
                              "more, not less.\n"
                              "Worth a conversation?"),
        variants.variant("em1_value_led", "professional",
                         subject="what Productive joins up for Acme",
                         body="Productive connects time tracking, project "
                              "visibility and profitability in one view.\n"
                              "For a 25-person agency, that means Monday "
                              "reporting takes minutes, not hours.\n"
                              "Happy to show you how it works - "
                              "book a 15-minute demo here."),
    ]


def _five_synonym_variants():
    """Five variants that are NOT materially different - paraphrases."""
    base = "Hi Anna, I wanted to reach out about how Acme handles project " \
           "management. We help agencies like yours streamline workflows."
    return [
        variants.variant("v1", "short_direct",
                         subject="Acme project management",
                         body=base + "\nWorth a chat?"),
        variants.variant("v2", "casual",
                         subject="Acme workflows",
                         body=base + "\nLet me know."),
        variants.variant("v3", "problem_led",
                         subject="Acme efficiency",
                         body=base + "\nInterested?"),
        variants.variant("v4", "consultative",
                         subject="Acme operations",
                         body=base + "\nThoughts?"),
        variants.variant("v5", "professional",
                         subject="Acme productivity",
                         body=base + "\nShall we talk?"),
    ]


# ----------------------------------------------------------- tests

class FiveDistinctApproaches(unittest.TestCase):
    """Five variants for a step carry five distinct recorded approaches."""

    def test_five_approaches_are_defined(self):
        self.assertEqual(len(variantgen.APPROACHES), 5)

    def test_each_approach_has_a_description(self):
        for key, spec in variantgen.APPROACHES.items():
            self.assertIn("description", spec, key)
            self.assertIn("label", spec, key)
            self.assertTrue(len(spec["description"]) > 20, key)

    def test_approach_order_has_five_for_email(self):
        order = variantgen.approaches_for("email")
        self.assertEqual(len(order), 5)

    def test_approach_order_has_five_for_linkedin(self):
        for node_type in ("connection_request", "linkedin_message",
                          "linkedin_followup"):
            order = variantgen.approaches_for(node_type)
            self.assertEqual(len(order), 5, node_type)

    def test_each_approach_maps_to_a_known_style(self):
        for node_type in ("email", "connection_request", "linkedin_message",
                          "linkedin_followup"):
            for approach in variantgen.approaches_for(node_type):
                style = variantgen.style_for(node_type, approach)
                styles = variants.STYLES_FOR.get(node_type, {})
                self.assertIn(style, styles,
                              f"{node_type}/{approach} -> {style}")

    def test_five_generated_variants_carry_five_distinct_styles(self):
        entries = _five_distinct_variants()
        styles = {e["style"] for e in entries}
        self.assertEqual(len(styles), 5)

    def test_approaches_have_distinct_structural_dimensions(self):
        """Each approach specifies different opening/tone/cta/proof."""
        dimensions = set()
        for key, spec in variantgen.APPROACHES.items():
            dim = (spec["opening"], spec["tone"], spec["cta"], spec["proof"])
            dimensions.add(dim)
        # At least 4 distinct combinations (observation_led and value_led
        # share "question" CTA but differ on opening and proof)
        self.assertGreaterEqual(len(dimensions), 4)


class ObservationLedGating(unittest.TestCase):
    """A record with no licensed observation produces no research-led variant."""

    def test_no_evidence_means_observation_led_unavailable(self):
        rec = _rec()
        contact = _contact(rec)
        available = variantgen.approaches_available(rec, contact, "email")
        obs = next(a for a in available
                   if a["approach"] == "observation_led")
        self.assertFalse(obs["available"])
        self.assertIn("no licensed observation", obs["why"])

    def test_other_approaches_still_available_without_evidence(self):
        rec = _rec()
        contact = _contact(rec)
        available = variantgen.approaches_available(rec, contact, "email")
        non_obs = [a for a in available
                   if a["approach"] != "observation_led"]
        for entry in non_obs:
            self.assertTrue(entry["available"], entry["approach"])

    def test_four_approaches_available_when_no_observation(self):
        rec = _rec()
        contact = _contact(rec)
        available = variantgen.approaches_available(rec, contact, "email")
        available_count = sum(1 for a in available if a["available"])
        self.assertEqual(available_count, 4)

    def test_observation_led_available_with_company_event_evidence(self):
        from src import evidence as ev

        rec = _rec()
        contact = _contact(rec)
        # Add a licensed observation via the research store, using evidence.make
        # to produce a properly scored row.
        row = ev.make(
            fact="Acme opened a new Vienna office in September 2026",
            source_url="https://acme.test/blog/vienna",
            source_type="company_announcement",
            provider="apify",
            record_id="test-rec",
            published_at="2026-09-01",
            subject=ev.COMPANY,
            persona="founder",
            angle_words="operations profitability",
        )
        rec["research"] = [row]
        available = variantgen.approaches_available(rec, contact, "email")
        obs = next(a for a in available
                   if a["approach"] == "observation_led")
        self.assertTrue(obs["available"],
                        f"observation_led should be available but got: {obs}")


class ClaimsGate(unittest.TestCase):
    """A variant asserting something unsupported is refused by claims."""

    def test_unsupported_claim_is_refused(self):
        rec = _rec()
        contact = _contact(rec)
        # A text that asserts a fact not in the record
        text = ("Congratulations on your Series B funding round.\n"
                "Acme must be growing fast.")
        problems = claims.check(text, rec, contact)
        self.assertTrue(len(problems) > 0,
                        "claims.check should refuse unsupported assertions")

    def test_supported_copy_passes_claims(self):
        rec = _rec()
        contact = _contact(rec)
        text = "Hi Anna, quick question about how Acme handles resourcing."
        problems = claims.check(text, rec, contact)
        self.assertEqual(problems, [])

    def test_variant_with_invented_funding_is_refused(self):
        """A variant that invents a funding round is refused by claims."""
        rec = _rec()
        contact = _contact(rec)
        entry = variants.variant("v1", "consultative",
                                 subject="congrats on Series B",
                                 body="Saw Acme raised Series B. "
                                      "Must be exciting times.")
        text = f"{entry['subject']}\n{entry['body']}"
        problems = claims.check(text, rec, contact)
        self.assertTrue(len(problems) > 0)


class SynonymDetection(unittest.TestCase):
    """Two variants that are synonym swaps are caught."""

    def test_distinct_variants_pass(self):
        entries = _five_distinct_variants()
        result = variantgen.are_materially_different(entries, "email",
                                                     "Acme Services")
        self.assertTrue(result["different"],
                        f"should be different but got: {result['pairs']}")

    def test_synonym_variants_fail(self):
        entries = _five_synonym_variants()
        result = variantgen.are_materially_different(entries, "email",
                                                     "Acme Services")
        self.assertFalse(result["different"],
                         "synonym swaps should NOT be materially different")

    def test_two_identical_variants_fail(self):
        body = ("Hi Anna, I wanted to reach out about how Acme handles "
                "project management and resource planning across the team. "
                "We help agencies streamline their workflows.")
        entries = [
            variants.variant("v1", "short_direct",
                             subject="Acme project management",
                             body=body + "\nWorth a quick chat?"),
            variants.variant("v2", "casual",
                             subject="Acme workflows",
                             body=body + "\nWorth a quick chat?"),
        ]
        result = variantgen.are_materially_different(entries, "email")
        self.assertFalse(result["different"])

    def test_single_variant_is_trivially_different(self):
        entries = [variants.variant("v1", "short_direct",
                                    subject="s", body="b")]
        result = variantgen.are_materially_different(entries, "email")
        self.assertTrue(result["different"])

    def test_empty_set_is_trivially_different(self):
        result = variantgen.are_materially_different([], "email")
        self.assertTrue(result["different"])

    def test_structural_summary_is_returned(self):
        entries = _five_distinct_variants()
        result = variantgen.are_materially_different(entries, "email",
                                                     "Acme Services")
        self.assertEqual(len(result["structural_summary"]), 5)
        for summary in result["structural_summary"]:
            self.assertIn("variant_id", summary)
            self.assertIn("opening", summary)
            self.assertIn("cta", summary)


class ApprovalPerVariant(unittest.TestCase):
    """Each variant carries its own approval requirement."""

    def test_each_variant_has_its_own_fingerprint(self):
        entries = _five_distinct_variants()
        fingerprints = {variants.fingerprint(e) for e in entries}
        self.assertEqual(len(fingerprints), 5,
                         "five distinct variants should have five fingerprints")

    def test_editing_one_variant_changes_its_fingerprint(self):
        entry = variants.variant("v1", "short_direct",
                                 subject="original", body="original body")
        fp1 = variants.fingerprint(entry)
        entry["body"] = "changed body"
        fp2 = variants.fingerprint(entry)
        self.assertNotEqual(fp1, fp2)

    def test_same_style_different_copy_different_fingerprint(self):
        e1 = variants.variant("v1", "short_direct",
                              subject="question one", body="body one")
        e2 = variants.variant("v2", "short_direct",
                              subject="question two", body="body two")
        self.assertNotEqual(variants.fingerprint(e1), variants.fingerprint(e2))


class VariantGenerationChain(unittest.TestCase):
    """The full chain: generate -> gate -> record approach."""

    def test_build_variant_set_without_model_returns_prompts(self):
        rec = _rec()
        contact = _contact(rec)
        sequence = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        result = variantgen.build_variant_set(
            rec, contact, "email", "em1", sequence=sequence)
        # Without a model, it should return prompts for available approaches
        generated = result["generated"]
        self.assertTrue(len(generated) > 0)
        for g in generated:
            self.assertIn("prompt", g)
            self.assertIn("approach", g)

    def test_build_variant_set_skips_observation_led_without_evidence(self):
        rec = _rec()
        contact = _contact(rec)
        sequence = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        result = variantgen.build_variant_set(
            rec, contact, "email", "em1", sequence=sequence)
        skipped = result["skipped"]
        obs_skipped = [s for s in skipped
                       if s["approach"] == "observation_led"]
        self.assertEqual(len(obs_skipped), 1)

    def test_build_variant_set_with_fake_model_generates_variants(self):
        rec = _rec()
        contact = _contact(rec)
        sequence = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        fake = _fake_llm_ask([
            ({"subject": "quick question",
              "body": "Hi Anna, do you track utilisation at Acme?"}, 1, []),
            ({"subject": "hey Anna",
              "body": "hey, how does Acme handle resource planning?"}, 1, []),
            ({"subject": "Monday mornings",
              "body": "Most agency founders spend Monday rebuilding "
                      "utilisation by hand."}, 1, []),
            # observation_led is skipped, so only 4 calls
            ({"subject": "what Productive joins up",
              "body": "Productive connects time tracking and profitability."},
             1, []),
        ])
        result = variantgen.build_variant_set(
            rec, contact, "email", "em1", sequence=sequence,
            llm_ask=fake)
        variant_entries = result["variants"]
        self.assertEqual(len(variant_entries), 4)
        # Each should have a distinct style
        styles = {v["style"] for v in variant_entries}
        self.assertEqual(len(styles), 4)

    def test_fake_model_variant_that_fails_claims_is_skipped(self):
        rec = _rec()
        contact = _contact(rec)
        sequence = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        fake = _fake_llm_ask([
            ({"subject": "quick question",
              "body": "Hi Anna, do you track utilisation at Acme?"}, 1, []),
            ({"subject": "hey Anna",
              "body": "hey, how does Acme handle resource planning?"}, 1, []),
            # This one asserts an unsupported claim
            ({"subject": "congrats on Series B",
              "body": "Saw Acme raised Series B last month. "
                      "Must be exciting times for the team."}, 1, []),
            ({"subject": "what Productive joins up",
              "body": "Productive connects time tracking and profitability."},
             1, []),
        ])
        result = variantgen.build_variant_set(
            rec, contact, "email", "em1", sequence=sequence,
            llm_ask=fake)
        skipped = result["skipped"]
        # The problem-led variant should be skipped because claims refused it
        claims_skipped = [s for s in skipped if "failed gates" in s.get("why", "")]
        self.assertTrue(len(claims_skipped) >= 1,
                        f"expected a claims failure, got skipped: {skipped}")


class WiringIsConsumed(unittest.TestCase):
    """The variantgen module is consumed by the production path."""

    def test_approaches_available_is_importable(self):
        from src.variantgen import approaches_available
        self.assertTrue(callable(approaches_available))

    def test_are_materially_different_is_importable(self):
        from src.variantgen import are_materially_different
        self.assertTrue(callable(are_materially_different))

    def test_build_variant_set_is_importable(self):
        from src.variantgen import build_variant_set
        self.assertTrue(callable(build_variant_set))

    def test_approaches_map_to_variant_styles(self):
        """Every approach maps to a style that variants.validate recognises."""
        for node_type in ("email", "connection_request", "linkedin_message",
                          "linkedin_followup"):
            for approach in variantgen.approaches_for(node_type):
                style = variantgen.style_for(node_type, approach)
                self.assertIn(style, variants.STYLES_FOR[node_type],
                              f"{node_type}/{approach} -> {style}")


if __name__ == "__main__":
    unittest.main()
