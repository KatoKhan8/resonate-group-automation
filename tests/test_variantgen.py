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
    """Five variants that ARE materially different in structure.

    Structural diversity:
      v1: statement / question   (21 words)
      v2: question  / statement  (32 words)
      v3: statement / question   (7 words - very short, ratio 0.33 vs v1)
      v4: question  / statement  (10 words - short, ratio 0.50 vs v2)
      v5: statement / statement  (28 words)
    No pair shares both (opening, CTA) at similar length.
    """
    return [
        variants.variant("em1_concise_direct", "short_direct",
                         subject="quick question",
                         body="Acme spends Monday mornings rebuilding "
                              "utilisation reports by hand. Productive "
                              "shows it in one view.\n"
                              "Worth a look?"),
        variants.variant("em1_conversational", "casual",
                         subject="hey Anna",
                         body="How does Acme handle resource planning "
                              "across the delivery team right now?\n"
                              "We have been working with similar-sized "
                              "agencies and the Monday rebuild problem "
                              "comes up every single time. Might be "
                              "worth a conversation."),
        variants.variant("em1_problem_led", "problem_led",
                         subject="the Monday problem",
                         body="Spreadsheets break on Monday.\n"
                              "Sound familiar?"),
        variants.variant("em1_observation_led", "consultative",
                         subject="saw Acme is hiring",
                         body="Growing the team?\n"
                              "We help agencies like Acme keep "
                              "visibility as they scale."),
        variants.variant("em1_value_led", "professional",
                         subject="what Productive joins up for Acme",
                         body="Productive connects time tracking, project "
                              "visibility and profitability in one view. "
                              "For a 25-person agency, Monday reporting "
                              "drops from hours to minutes and the team "
                              "stops rebuilding what the spreadsheet "
                              "already knew.\n"
                              "Here is how it works."),
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


class JSONContractInPrompt(unittest.TestCase):
    """The variant prompt carries the JSON contract from the template."""

    def test_email_variant_prompt_contains_json_instruction(self):
        prompt = variantgen.variant_prompt(
            "concise_direct", "draft", "Ask about utilisation",
            {"company": "Acme"})
        self.assertIn("Return JSON only", prompt)

    def test_email_variant_prompt_contains_subject_body_schema(self):
        prompt = variantgen.variant_prompt(
            "concise_direct", "draft", "Ask about utilisation",
            {"company": "Acme"})
        self.assertIn("subject", prompt)
        self.assertIn("body", prompt)

    def test_linkedin_variant_prompt_contains_note_schema(self):
        prompt = variantgen.variant_prompt(
            "concise_direct", "linkedin_note", "Open a conversation",
            {"company": "Acme"})
        self.assertIn("Return JSON only", prompt)
        self.assertIn("note", prompt)

    def test_variant_prompt_reuses_template_not_inline_copy(self):
        """The prompt starts with the same template render_prompt uses."""
        from src.generate import prompt_text
        for step in ("draft", "linkedin_note"):
            prompt = variantgen.variant_prompt(
                "concise_direct", step, "purpose", {"company": "Acme"})
            template = prompt_text(step)
            self.assertTrue(
                prompt.startswith(template),
                f"variant_prompt for {step} does not start with the template")

    def test_variant_prompt_includes_approach_after_template(self):
        prompt = variantgen.variant_prompt(
            "problem_led", "draft", "purpose", {"company": "Acme"})
        self.assertIn("## Approach: Problem-led", prompt)


class StructuralClonesCollide(unittest.TestCase):
    """Two structurally identical variants COLLIDE even with low word overlap."""

    def test_same_opening_same_cta_collides_despite_different_words(self):
        """Both open with a question, both close with a question.
        Different vocabulary, same structure, similar length = collision."""
        entries = [
            variants.variant("v1", "short_direct",
                             subject="utilization",
                             body="Do you track utilisation at Acme?\n"
                                  "Worth a quick look?"),
            variants.variant("v2", "casual",
                             subject="resource planning",
                             body="Has the team considered resourcing "
                                  "for delivery?\n"
                                  "Worth a deeper look?"),
        ]
        result = variantgen.are_materially_different(entries, "email")
        self.assertFalse(result["different"],
                         "same opening (question) + same CTA (question) "
                         "must collide")

    def test_same_opening_same_cta_statement_pair(self):
        """Both open with a statement, both close with a statement."""
        entries = [
            variants.variant("v1", "short_direct",
                             subject="efficiency",
                             body="Acme spends too long on Monday "
                                  "reporting each week.\n"
                                  "Productive fixes that."),
            variants.variant("v2", "professional",
                             subject="visibility",
                             body="Most agencies lose half a day to "
                                  "spreadsheets every week.\n"
                                  "A single view changes that."),
        ]
        result = variantgen.are_materially_different(entries, "email")
        self.assertFalse(result["different"],
                         "same opening (statement) + same CTA (statement) "
                         "must collide")

    def test_near_identical_opening_same_length_collides(self):
        """em3 variants 1 and 4: nearly identical opening, same length,
        both statements. Must collide."""
        entries = [
            variants.variant("em3_v1", "short_direct",
                             subject="budgets",
                             body="Productive is one place where an "
                                  "agency's budgets, time tracking, "
                                  "resourcing and delivery come together "
                                  "in a single view.\n"
                                  "Worth exploring for Acme?"),
            variants.variant("em3_v4", "consultative",
                             subject="operations",
                             body="Productive is one place where an "
                                  "agency's financial planning, resource "
                                  "allocation, project tracking and "
                                  "profitability meet.\n"
                                  "Happy to share more if useful."),
        ]
        result = variantgen.are_materially_different(entries, "email")
        self.assertFalse(result["different"],
                         "near-identical opening, same length: must collide")

    def test_different_opening_different_cta_passes(self):
        """One opens with a question and closes with a statement; the other
        opens with a statement and closes with a question. No collision."""
        entries = [
            variants.variant("v1", "short_direct",
                             subject="planning",
                             body="Acme handles resource planning in "
                                  "spreadsheets.\n"
                                  "Worth a look at something simpler?"),
            variants.variant("v2", "casual",
                             subject="resource visibility",
                             body="How does the team track who is working "
                                  "on what?\n"
                                  "We built something that might help."),
        ]
        result = variantgen.are_materially_different(entries, "email")
        self.assertTrue(result["different"],
                        "different opening AND different CTA: should pass")

    def test_same_opening_different_length_passes(self):
        """Both open with a statement but one is 3x the other and they
        close differently. Different CTA means no structural collision."""
        entries = [
            variants.variant("v1", "short_direct",
                             subject="quick note",
                             body="Acme could save time on Monday "
                                  "reporting.\n"
                                  "Worth a look?"),
            variants.variant("v2", "professional",
                             subject="detailed proposal",
                             body="After reviewing how agencies of your "
                                  "size typically handle resource planning "
                                  "and utilisation tracking across multiple "
                                  "projects and teams, I noticed several "
                                  "patterns that Productive addresses "
                                  "directly.\n"
                                  "Here is how it works."),
        ]
        result = variantgen.are_materially_different(entries, "email")
        self.assertTrue(result["different"],
                        "same opening but different CTA and very different "
                        "length: should pass")


class LadderDoesNotPrescribeForm(unittest.TestCase):
    """TASK-087: The ladder's rung purpose must not prescribe message form.

    If the purpose says "asks a question" or "is a statement", every
    variant approach collapses to the same structure regardless of its
    own structural instructions. The ladder describes the JOB; the
    approach describes the FORM.
    """

    def test_linkedin_rung_2_does_not_say_asks_a_question(self):
        """Rung 2 used to say 'this message asks a question about how
        they handle one specific part of their operation today'. That
        made every variant open with a question."""
        purpose = cadencelibrary.LINKEDIN_DEFAULT_LADDER[1]
        self.assertNotIn("asks a question", purpose.lower())

    def test_linkedin_rung_4_does_not_say_is_a_statement(self):
        """Rung 4 used to say 'it is a statement, not a question'. That
        prescribed the form for every variant."""
        purpose = cadencelibrary.LINKEDIN_DEFAULT_LADDER[3]
        self.assertNotIn("is a statement", purpose.lower())

    def test_linkedin_rung_5_does_not_say_one_question(self):
        """Rung 5 used to say 'in one line and one question'. That
        prescribed the CTA form for every variant."""
        purpose = cadencelibrary.LINKEDIN_DEFAULT_LADDER[4]
        self.assertNotIn("one question", purpose.lower())

    def test_linkedin_ladder_still_has_six_rungs(self):
        self.assertEqual(len(cadencelibrary.LINKEDIN_DEFAULT_LADDER), 6)

    def test_variant_prompt_has_structural_authority_rule(self):
        """The prompt tells the model the approach controls structure."""
        prompt = variantgen.variant_prompt(
            "concise_direct", "linkedin_note",
            "Establish how they handle resourcing.",
            {"company": "Acme"})
        self.assertIn("Approach section above controls your message "
                       "structure", prompt)

    def test_two_approaches_differ_only_in_approach_section(self):
        """The ONLY difference between two approach prompts is the
        approach section. The purpose and rules are identical.

        This proves the approach is the sole structural differentiator:
        if two prompts produce the same structure, the approach
        descriptions are insufficient (not the ladder)."""
        purpose = "Establish how they handle resourcing."
        context = {"company": "Acme"}
        prompt_a = variantgen.variant_prompt(
            "concise_direct", "linkedin_note", purpose, context)
        prompt_b = variantgen.variant_prompt(
            "conversational", "linkedin_note", purpose, context)

        # Extract the purpose section from each
        def extract_purpose_section(prompt):
            parts = prompt.split("## This step's job")
            self.assertEqual(len(parts), 2, "prompt missing job section")
            return parts[1].split("## Record context")[0]

        purpose_a = extract_purpose_section(prompt_a)
        purpose_b = extract_purpose_section(prompt_b)
        self.assertEqual(purpose_a, purpose_b,
                         "purpose section should be identical for both "
                         "approaches (it is shared)")


class TASK114RegressionPins(unittest.TestCase):
    """TASK-114: regression tests that pin the variant path cannot rot.

    Each test guards a specific property that was broken in TASK-084 and
    TASK-087. The tests assert on what functions RETURN, not on the text
    of the source. Each test is accompanied by counterfactual evidence
    showing it would have caught the original defect.
    """

    # -------------------------------------------------- 1. Prompt carries schema
    #
    # TASK-084 Defect 1: variant_prompt() built a prompt that never told the
    # model to return JSON and never gave it the shape. LinkedIn variants
    # failed with SchemaError because the model returned prose.
    #
    # The fix: variant_prompt() now calls generate.prompt_text(step) to
    # prepend the same template render_prompt uses. The JSON contract and
    # schema come from one place.
    #
    # This test would have caught the defect: if variant_prompt() did not
    # call generate.prompt_text(step), the prompt would not start with the
    # template and would not contain "Return JSON only".

    def test_email_prompt_starts_with_template_and_carries_json_contract(self):
        """The email variant prompt starts with the draft template and
        carries the JSON contract. If variant_prompt() built its own prompt
        without the template, this would fail."""
        prompt = variantgen.variant_prompt(
            "concise_direct", "draft", "Ask about utilisation",
            {"company": "Acme"})
        from src.generate import prompt_text
        template = prompt_text("draft")
        self.assertTrue(prompt.startswith(template),
                        "variant_prompt must prepend the template; without it "
                        "the model gets no JSON schema")
        self.assertIn("Return JSON only", prompt)
        self.assertIn('"subject"', prompt)
        self.assertIn('"body"', prompt)

    def test_linkedin_prompt_starts_with_template_and_carries_note_schema(self):
        """The LinkedIn variant prompt starts with the linkedin_note template
        and carries the note schema. If variant_prompt() built its own prompt
        without the template, LinkedIn variants would fail with SchemaError
        (as they did in TASK-084)."""
        prompt = variantgen.variant_prompt(
            "concise_direct", "linkedin_note", "Open a conversation",
            {"company": "Acme"})
        from src.generate import prompt_text
        template = prompt_text("linkedin_note")
        self.assertTrue(prompt.startswith(template),
                        "variant_prompt must prepend the template; without it "
                        "LinkedIn variants fail with SchemaError")
        self.assertIn("Return JSON only", prompt)
        self.assertIn('"note"', prompt)
        # LinkedIn template does NOT carry subject/body
        self.assertNotIn('"subject"', prompt)
        self.assertNotIn('"body"', prompt)

    def test_prompt_contract_cannot_drift_between_draft_and_variant(self):
        """The variant prompt and the normal draft prompt share the same
        template. If someone added a new schema field to the template, both
        paths would get it. If someone removed it, both would lose it.
        This test pins that they cannot drift apart."""
        from src.generate import prompt_text
        for step in ("draft", "linkedin_note"):
            variant_prompt_text = variantgen.variant_prompt(
                "concise_direct", step, "purpose", {"company": "Acme"})
            template = prompt_text(step)
            # The variant prompt must start with the template
            self.assertTrue(variant_prompt_text.startswith(template),
                            f"variant_prompt for {step} does not start with "
                            f"the template; the two paths have drifted")

    # -------------------------------------------------- 2. Arms structurally different
    #
    # TASK-084 Defect 2: are_materially_different() compared WORD OVERLAP
    # against a threshold. It passed structural clones that shared opening
    # type and CTA type but had different words.
    #
    # TASK-087 measured the real collapsed output: four LinkedIn variants,
    # all opening with a question, all closing with a question, word counts
    # 27-32. The old check said "materially different". The new check says
    # "NOT materially different" and refuses them.
    #
    # This fixture is built from the real collapsed output TASK-087 measured.
    # If are_materially_different() used word overlap instead of structure,
    # this test would pass (incorrectly).

    def test_real_collapsed_output_from_task087_is_refused(self):
        """Four LinkedIn variants from the real TASK-087 collapsed output:
        all open with a question, all close with a question, word counts
        27-32. The diversity check MUST refuse these. If it used word overlap,
        it would pass them (the old defect)."""
        # These are paraphrases of the actual TASK-087 output for li2.
        # All four open with a question and close with a question.
        entries = [
            variants.variant("li2_concise_direct", "short_direct",
                             note="hi jacob, this is a quick note from "
                                  "someone working with agencies on "
                                  "resourcing visibility. how do you "
                                  "currently get visibility on who is "
                                  "working on what at ogpartner?"),
            variants.variant("li2_conversational", "casual",
                             note="hi jacob, this is a quick one from me "
                                  "at Productive. how do you currently get "
                                  "visibility on who is working on what "
                                  "across the delivery team?"),
            variants.variant("li2_problem_led", "professional",
                             note="hi jacob, this is a quick note from "
                                  "someone working on agency resourcing "
                                  "visibility. how do you currently handle "
                                  "resource planning across projects?"),
            variants.variant("li2_value_led", "peer_to_peer",
                             note="hi jacob, this is a quick one from me "
                                  "at Productive. how do you currently get "
                                  "visibility on who is working on what "
                                  "and how long things take?"),
        ]
        result = variantgen.are_materially_different(entries, "linkedin_message")
        self.assertFalse(result["different"],
                         "TASK-087 collapsed output must be refused; if this "
                         "passes, the diversity check is using word overlap "
                         "instead of structure (the TASK-084 defect)")
        # Verify the check identified the structural collision
        self.assertTrue(len(result["pairs"]) > 0,
                        "the check should identify at least one structural "
                        "collision")

    def test_four_question_question_variants_are_not_an_experiment(self):
        """The operator's requirement: 'A = Hey John, B = Hi John, C = Hello
        John is not an experiment.' Four variants that all open with a
        question and close with a question are one variant, not four."""
        entries = [
            variants.variant("v1", "short_direct",
                             subject="quick question",
                             body="Do you track utilisation at Acme?\n"
                                  "Worth a look?"),
            variants.variant("v2", "casual",
                             subject="hey Anna",
                             body="How does Acme handle resource planning?\n"
                                  "Let me know."),
            variants.variant("v3", "problem_led",
                             subject="the Monday problem",
                             body="How do you handle Monday reporting?\n"
                                  "Sound familiar?"),
            variants.variant("v4", "professional",
                             subject="visibility",
                             body="How does the team track who is working "
                                  "on what?\n"
                                  "Happy to share more."),
        ]
        result = variantgen.are_materially_different(entries, "email")
        self.assertFalse(result["different"],
                         "four variants that all open with a question and "
                         "close with a question are NOT an experiment")

    # -------------------------------------------------- 3. observation_led both directions
    #
    # The observation-led variant is the dangerous one. A model asked for an
    # observation-led message with no observation available will invent one.
    # So approaches_available() returns only the approaches the record can
    # support, and observation_led is absent when no licensed observation
    # exists.
    #
    # This test pins BOTH directions: absent without evidence, present with
    # evidence. A test that only proves it is absent would pass if it were
    # removed entirely.

    def test_observation_led_absent_without_evidence(self):
        """A record with no licensed observation produces no observation_led
        variant. If this test passed when observation_led was removed entirely,
        it would not be testing anything."""
        rec = _rec()
        contact = _contact(rec)
        available = variantgen.approaches_available(rec, contact, "email")
        obs = next((a for a in available
                    if a["approach"] == "observation_led"), None)
        self.assertIsNotNone(obs,
                             "observation_led must be in the available list "
                             "(with available=False); if it were removed "
                             "entirely, this would pass trivially")
        self.assertFalse(obs["available"],
                         "observation_led must be unavailable without evidence")
        self.assertIn("no licensed observation", obs.get("why", ""),
                      "the reason must be stated")

    def test_observation_led_present_with_evidence(self):
        """A record WITH a licensed observation produces an observation_led
        variant. This is the other direction: a test that only proves it is
        absent would pass if it were removed entirely."""
        from src import evidence as ev

        rec = _rec()
        contact = _contact(rec)
        # Add a licensed observation
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
        obs = next((a for a in available
                    if a["approach"] == "observation_led"), None)
        self.assertIsNotNone(obs,
                             "observation_led must be in the available list")
        self.assertTrue(obs["available"],
                        "observation_led must be available WITH evidence")
        self.assertIn("evidence", obs,
                      "the evidence must be carried on the decision")

    def test_build_variant_set_skips_observation_led_without_evidence(self):
        """build_variant_set() skips observation_led when no evidence exists.
        This pins the generation path, not just the availability check."""
        rec = _rec()
        contact = _contact(rec)
        sequence = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        result = variantgen.build_variant_set(
            rec, contact, "email", "em1", sequence=sequence)
        skipped = result["skipped"]
        obs_skipped = [s for s in skipped
                       if s["approach"] == "observation_led"]
        self.assertEqual(len(obs_skipped), 1,
                         "observation_led must be skipped without evidence")
        # Verify the other four approaches are NOT skipped
        non_obs_skipped = [s for s in skipped
                           if s["approach"] != "observation_led"]
        self.assertEqual(len(non_obs_skipped), 0,
                         "no other approach should be skipped")

    def test_build_variant_set_includes_observation_led_with_evidence(self):
        """build_variant_set() includes observation_led when evidence exists.
        This is the other direction of the pin."""
        from src import evidence as ev

        rec = _rec()
        contact = _contact(rec)
        # Add a licensed observation
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
        sequence = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        # Use a fake model that returns valid data
        fake = _fake_llm_ask([
            ({"subject": "quick question",
              "body": "Hi Anna, do you track utilisation at Acme?"}, 1, []),
            ({"subject": "hey Anna",
              "body": "hey, how does Acme handle resource planning?"}, 1, []),
            ({"subject": "Monday mornings",
              "body": "Most agency founders spend Monday rebuilding "
                      "utilisation by hand."}, 1, []),
            ({"subject": "saw the Vienna office",
              "body": "Saw Acme opened a new Vienna office. "
                      "How are you keeping visibility as you scale?"}, 1, []),
            ({"subject": "what Productive joins up",
              "body": "Productive connects time tracking and profitability."},
             1, []),
        ])
        result = variantgen.build_variant_set(
            rec, contact, "email", "em1", sequence=sequence,
            llm_ask=fake)
        # observation_led should NOT be in the skipped list
        skipped = result["skipped"]
        obs_skipped = [s for s in skipped
                       if s["approach"] == "observation_led"]
        self.assertEqual(len(obs_skipped), 0,
                         "observation_led must NOT be skipped with evidence")
        # And it should be in the generated list
        generated_approaches = [g["approach"] for g in result["generated"]]
        self.assertIn("observation_led", generated_approaches,
                      "observation_led must be generated with evidence")


if __name__ == "__main__":
    unittest.main()
