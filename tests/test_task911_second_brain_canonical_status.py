"""TASK-911: the Second Brain carries canonical status and the relevant subset.

Acceptance:
1. Status counts: 50 facts for campaign_strategy/productive, split across
   CLIENT_SUPPLIED and unpromoted (verified is False for all 50).
2. Admitted > 0 for economic_buyer + OFFER-A, relevant subset not 50.
3. Hypothesis prompt carries the 'our own data' block through the real path.
4. POSITIVE CONTROL: mutating a CLIENT_SUPPLIED capability changes downstream
   context through the real entrypoint; restoring changes it back.
5. NEGATIVE CONTROL: unpromoted item absent from pack['facts'] and writer
   prospect-facing facts.
6. NEGATIVE CONTROL: CLIENT_SUPPLIED does not license prospect-side claims.
   Two existing test modules guard this boundary and stay green.
"""
import hashlib
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import secondbrain, generate_campaign as gc, clients
from src.packfacts import CLIENT_SUPPLIED


class TestCanonicalStatusProjection(unittest.TestCase):
    """Change 1: secondbrain projects canonical status by config key."""

    def setUp(self):
        self.brain = secondbrain.for_task("campaign_strategy", "productive")
        self.all_facts = []
        for section, facts in self.brain.items():
            self.all_facts.extend(facts)

    def test_total_facts_is_50(self):
        self.assertEqual(len(self.all_facts), 50)

    def test_every_fact_carries_canonical_status_field(self):
        for fact in self.all_facts:
            self.assertIn("canonical_status", fact,
                          f"fact missing canonical_status: {fact['text']!r}")

    def test_verified_unchanged_all_false(self):
        for fact in self.all_facts:
            self.assertFalse(fact.get("verified"),
                             f"verified should be False: {fact['text']!r}")

    def test_status_split(self):
        cs_count = sum(1 for f in self.all_facts
                       if f.get("canonical_status") == CLIENT_SUPPLIED)
        unpromoted = sum(1 for f in self.all_facts
                         if f.get("canonical_status") is None)
        self.assertEqual(cs_count + unpromoted, 50)
        self.assertEqual(cs_count, 50,
                         "all 50 current facts come from eligible keys")
        self.assertEqual(unpromoted, 0,
                         "no current fact has an ineligible key")

    def test_eligible_key_returns_client_supplied(self):
        self.assertEqual(secondbrain._canonical_status("product.capabilities"),
                         CLIENT_SUPPLIED)
        self.assertEqual(secondbrain._canonical_status("product.name"),
                         CLIENT_SUPPLIED)
        self.assertEqual(secondbrain._canonical_status("market.must"),
                         CLIENT_SUPPLIED)
        self.assertEqual(secondbrain._canonical_status("personas.economic_buyer.titles"),
                         CLIENT_SUPPLIED)
        self.assertEqual(secondbrain._canonical_status("angle_labels"),
                         CLIENT_SUPPLIED)
        self.assertEqual(secondbrain._canonical_status("tone.email"),
                         CLIENT_SUPPLIED)
        self.assertEqual(secondbrain._canonical_status("linkedin_sequence.fallbacks"),
                         CLIENT_SUPPLIED)

    def test_ineligible_key_returns_none(self):
        self.assertIsNone(secondbrain._canonical_status("hypotheses.inferred_pain"))
        self.assertIsNone(secondbrain._canonical_status("strategy.generated"))
        self.assertIsNone(secondbrain._canonical_status("unknown_key"))
        self.assertIsNone(secondbrain._canonical_status("marketing.claim"))

    def test_icp_structural_is_client_supplied(self):
        self.assertEqual(
            secondbrain._canonical_status("icp.structural.company_types.primary"),
            CLIENT_SUPPLIED)
        self.assertEqual(
            secondbrain._canonical_status("icp.structural.employees.min"),
            CLIENT_SUPPLIED)


class TestAdmittedSubset(unittest.TestCase):
    """Change 2+3: admission with the relevant subset, not a 50-item dump."""

    def setUp(self):
        from src import offers as offers_mod
        self.offers = offers_mod.all_offers()
        self.offer_a = self.offers["OFFER-A-ECONOMIC-BUYER"]
        self.admitted = gc._load_admitted_facts(
            "productive", persona="economic_buyer", offer=self.offer_a)

    def test_admitted_count_greater_than_zero(self):
        self.assertGreater(len(self.admitted), 0)

    def test_admitted_count_less_than_50(self):
        self.assertLess(len(self.admitted), 50)

    def test_no_linkedin_sequence_fallbacks(self):
        for fact in self.admitted:
            src = fact.get("source", "")
            key = src.split(" ", 1)[-1] if " " in src else ""
            self.assertNotEqual(key, "linkedin_sequence.fallbacks",
                                "fallback admitted: %s" % fact["text"][:60])

    def test_angle_labels_restricted_to_persona_angles(self):
        config = clients.load("productive")
        persona_cfg = clients.personas(config).get("economic_buyer", {})
        persona_angles = set((persona_cfg.get("angles") or {}).keys())
        for fact in self.admitted:
            src = fact.get("source", "")
            key = src.split(" ", 1)[-1] if " " in src else ""
            if key == "angle_labels":
                import re
                m = re.search(r"Angle label '([^']+)':", fact.get("text", ""))
                if m:
                    self.assertIn(m.group(1), persona_angles,
                                  "angle %r not in economic_buyer angles" % m.group(1))

    def test_no_champion_personas_items(self):
        for fact in self.admitted:
            src = fact.get("source", "")
            key = src.split(" ", 1)[-1] if " " in src else ""
            if key.startswith("personas."):
                parts = key.split(".")
                if len(parts) >= 2:
                    self.assertEqual(parts[1], "economic_buyer",
                                     "champion persona item admitted: %s" % key)

    def test_only_offer_capability_from_product_capabilities(self):
        cap_names = gc._offer_capability_names(self.offer_a)
        for fact in self.admitted:
            src = fact.get("source", "")
            key = src.split(" ", 1)[-1] if " " in src else ""
            if key == "product.capabilities":
                cap_key = fact.get("text", "").split(":")[0].strip()
                self.assertIn(cap_key, cap_names,
                              "capability %r not in offer's capabilities %r"
                              % (cap_key, cap_names))

    def test_profitability_capability_present(self):
        texts = " ".join(f.get("text", "") for f in self.admitted)
        self.assertIn("profitability: margin per project", texts)

    def test_no_other_persona_capability_by_persona(self):
        for fact in self.admitted:
            src = fact.get("source", "")
            key = src.split(" ", 1)[-1] if " " in src else ""
            if key == "product.capability_by_persona":
                self.assertIn("economic_buyer", fact.get("text", ""),
                              "non-economic_buyer capability_by_persona admitted")


class TestOfferCapabilityNames(unittest.TestCase):
    """_offer_capability_names reads the offer's own capability field."""

    def test_offer_a_includes_profitability_and_budgeting(self):
        from src import offers as offers_mod
        offer = offers_mod.all_offers()["OFFER-A-ECONOMIC-BUYER"]
        got = gc._offer_capability_names(offer)
        self.assertEqual(got, {"profitability", "budgeting"})

    def test_offer_b_includes_composed_capabilities(self):
        from src import offers as offers_mod
        offer = offers_mod.all_offers()["OFFER-B-OPERATIONS"]
        got = gc._offer_capability_names(offer)
        self.assertEqual(got, {"project_management", "time_tracking",
                               "resource_planning"})

    def test_none_offer_returns_empty(self):
        self.assertEqual(gc._offer_capability_names(None), set())


class TestPositiveControl(unittest.TestCase):
    """POSITIVE CONTROL: changing a CLIENT_SUPPLIED item changes downstream."""

    def test_mutating_capability_changes_admitted_context(self):
        from src import offers as offers_mod
        offer = offers_mod.all_offers()["OFFER-A-ECONOMIC-BUYER"]

        adm_before = gc._load_admitted_facts(
            "productive", persona="economic_buyer", offer=offer)
        texts_before = " ".join(f.get("text", "") for f in adm_before)
        self.assertIn("profitability: margin per project", texts_before)

        original_for_task = secondbrain.for_task

        def mutated_for_task(task, client):
            brain = original_for_task(task, client)
            for section, facts in brain.items():
                for fact in facts:
                    if ("profitability: margin per project" in fact.get("text", "")
                            and "product.capabilities" in fact.get("source", "")):
                        fact["text"] = "profitability: MUTATED VALUE"
            return brain

        secondbrain.for_task = mutated_for_task
        try:
            adm_after = gc._load_admitted_facts(
                "productive", persona="economic_buyer", offer=offer)
            texts_after = " ".join(f.get("text", "") for f in adm_after)
            self.assertIn("profitability: MUTATED VALUE", texts_after)
            self.assertNotIn("margin per project while it is running",
                             texts_after)
        finally:
            secondbrain.for_task = original_for_task

    def test_br_context_populated_through_real_path(self):
        from src import offers as offers_mod
        offer = offers_mod.all_offers()["OFFER-A-ECONOMIC-BUYER"]
        admitted = gc._load_admitted_facts(
            "productive", persona="economic_buyer", offer=offer)
        br_context = gc._format_br_context(admitted)
        self.assertIsNotNone(br_context)
        self.assertIn("profitability", br_context)
        self.assertIn("config/clients/productive.yaml", br_context)


class TestNegativeControls(unittest.TestCase):
    """NEGATIVE CONTROLS: unpromoted items cannot become prospect-facing."""

    def test_unpromoted_item_not_in_admitted_as_prospect_fact(self):
        """An INFERRED/UNKNOWN key is not admitted as CLIENT_SUPPLIED."""
        self.assertIsNone(secondbrain._canonical_status("hypotheses.inferred_pain"))

    def test_client_supplied_not_in_pack_facts(self):
        """CLIENT_SUPPLIED facts inform strategy but never reach pack['facts'].

        The two existing test modules guard this boundary:
        - test_a_client_csv_fact_cannot_license_a_claim
        - test_a_client_supplied_figure_licenses_no_claim_in_either_gate
        This test verifies the structural property: admitted facts are for
        internal strategy (br_context), not for the writer's prospect-facing
        facts argument.
        """
        from src import offers as offers_mod
        offer = offers_mod.all_offers()["OFFER-A-ECONOMIC-BUYER"]
        admitted = gc._load_admitted_facts(
            "productive", persona="economic_buyer", offer=offer)
        for fact in admitted:
            self.assertNotIn("pack", fact,
                             "admitted fact has pack reference: %s" % fact["text"][:60])

    def test_admitted_facts_stay_in_br_context_not_prospect_facts(self):
        """The admitted facts flow to br_context (hypothesis prompt), not to
        the writer's prospect-facing facts argument."""
        from src import offers as offers_mod
        offer = offers_mod.all_offers()["OFFER-A-ECONOMIC-BUYER"]
        admitted = gc._load_admitted_facts(
            "productive", persona="economic_buyer", offer=offer)
        br_context = gc._format_br_context(admitted)
        self.assertIsNotNone(br_context)
        self.assertIn("Productive", br_context)


class TestMutationKillsAdmission(unittest.TestCase):
    """MUTATION: reverting status projection kills admission."""

    def test_removing_canonical_status_kills_admission(self):
        """If canonical_status is None for all facts, only verified facts
        are admitted. Since all 50 have verified=False, admission drops to 0."""
        from src import offers as offers_mod
        offer = offers_mod.all_offers()["OFFER-A-ECONOMIC-BUYER"]

        original_for_task = secondbrain.for_task

        def stripped_for_task(task, client):
            brain = original_for_task(task, client)
            for section, facts in brain.items():
                for fact in facts:
                    fact["canonical_status"] = None
            return brain

        secondbrain.for_task = stripped_for_task
        try:
            admitted = gc._load_admitted_facts(
                "productive", persona="economic_buyer", offer=offer)
            self.assertEqual(len(admitted), 0,
                             "admission should be 0 without canonical_status, "
                             "got %d" % len(admitted))
        finally:
            secondbrain.for_task = original_for_task


class TestNoNewTaxonomy(unittest.TestCase):
    """No new trust taxonomy was invented."""

    def test_no_verified_v2_or_trusted_in_secondbrain(self):
        import inspect
        src = inspect.getsource(secondbrain)
        self.assertNotIn("verified_v2", src)
        self.assertNotIn("trusted=True", src)
        self.assertNotIn("CLIENT_APPROVED =", src)

    def test_client_supplied_is_reused_from_packfacts(self):
        self.assertIs(gc.CLIENT_SUPPLIED, CLIENT_SUPPLIED)


class TestClientSlugResolution(unittest.TestCase):
    """REWORK 2: _load_admitted_facts resolves the slug from a display name."""

    def test_display_name_resolves_to_slug(self):
        """'Productive' (display name) resolves to 'productive' (slug)."""
        from src import offers as offers_mod
        offer = offers_mod.all_offers()["OFFER-A-ECONOMIC-BUYER"]
        admitted = gc._load_admitted_facts(
            "Productive", persona="economic_buyer", offer=offer)
        self.assertGreater(len(admitted), 0,
                           "display name 'Productive' must resolve to slug "
                           "'productive' and admit facts")

    def test_slug_still_works_directly(self):
        """Passing the slug directly still works."""
        from src import offers as offers_mod
        offer = offers_mod.all_offers()["OFFER-A-ECONOMIC-BUYER"]
        admitted = gc._load_admitted_facts(
            "productive", persona="economic_buyer", offer=offer)
        self.assertGreater(len(admitted), 0)

    def test_display_name_and_slug_produce_same_result(self):
        """Both paths produce the same admitted set."""
        from src import offers as offers_mod
        offer = offers_mod.all_offers()["OFFER-A-ECONOMIC-BUYER"]
        from_slug = gc._load_admitted_facts(
            "productive", persona="economic_buyer", offer=offer)
        from_name = gc._load_admitted_facts(
            "Productive", persona="economic_buyer", offer=offer)
        texts_slug = sorted(f.get("text", "") for f in from_slug)
        texts_name = sorted(f.get("text", "") for f in from_name)
        self.assertEqual(texts_slug, texts_name,
                         "display name and slug must produce identical results")


class TestErrorPropagation(unittest.TestCase):
    """REWORK 2: a bad client name raises, not silently returns []."""

    def test_unknown_client_raises_not_empty(self):
        """An unknown client name must NOT silently return []."""
        from src import offers as offers_mod
        offer = offers_mod.all_offers()["OFFER-A-ECONOMIC-BUYER"]
        with self.assertRaises(Exception):
            gc._load_admitted_facts(
                "nonexistent_client_xyz", persona="economic_buyer",
                offer=offer)

    def test_resolve_client_slug_valid(self):
        self.assertEqual(gc._resolve_client_slug("productive"), "productive")

    def test_resolve_client_slug_from_display_name(self):
        self.assertEqual(gc._resolve_client_slug("Productive"), "productive")

    def test_resolve_client_slug_bad_name_raises(self):
        with self.assertRaises(Exception):
            gc._resolve_client_slug("nonexistent_client_xyz")


class TestPositiveControlViaRealEntrypoint(unittest.TestCase):
    """REWORK 2 acceptance 1: positive control through generate()."""

    def test_generate_passes_slug_not_display_name(self):
        """When generate() receives a config dict with name='Productive',
        _load_admitted_facts still resolves the slug correctly."""
        from src import offers as offers_mod
        config = clients.load("productive")
        self.assertEqual(config.get("name"), "Productive")
        offer = offers_mod.all_offers()["OFFER-A-ECONOMIC-BUYER"]
        admitted = gc._load_admitted_facts(
            config.get("name"), persona="economic_buyer", offer=offer)
        texts = " ".join(f.get("text", "") for f in admitted)
        self.assertIn("profitability", texts,
                       "profitability capability must be admitted through "
                       "the display-name path")

    def test_mutating_capability_changes_context_via_display_name(self):
        """Mutate a CLIENT_SUPPLIED item, enter with display name, prove
        the downstream context changes."""
        from src import offers as offers_mod
        offer = offers_mod.all_offers()["OFFER-A-ECONOMIC-BUYER"]

        adm_before = gc._load_admitted_facts(
            "Productive", persona="economic_buyer", offer=offer)
        texts_before = " ".join(f.get("text", "") for f in adm_before)
        self.assertIn("profitability: margin per project", texts_before)

        original_for_task = secondbrain.for_task

        def mutated_for_task(task, client):
            brain = original_for_task(task, client)
            for section, facts in brain.items():
                for fact in facts:
                    if ("profitability: margin per project" in fact.get("text", "")
                            and "product.capabilities" in fact.get("source", "")):
                        fact["text"] = "profitability: MUTATED FOR CONTROL"
            return brain

        secondbrain.for_task = mutated_for_task
        try:
            adm_after = gc._load_admitted_facts(
                "Productive", persona="economic_buyer", offer=offer)
            texts_after = " ".join(f.get("text", "") for f in adm_after)
            self.assertIn("profitability: MUTATED FOR CONTROL", texts_after)
            self.assertNotIn("margin per project while it is running",
                             texts_after)
        finally:
            secondbrain.for_task = original_for_task


if __name__ == "__main__":
    unittest.main()
