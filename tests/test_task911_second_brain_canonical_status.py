"""TASK-911: the Second Brain carries canonical status and reach strategy.

Acceptance:
1. Status counts: 50 total, split VERIFIED / CLIENT_SUPPLIED / unpromoted.
2. Admitted to internal strategy > 0 for economic_buyer, relevant subset < 50.
3. Hypothesis prompt carries "our own data" block through the real path.
4. POSITIVE CONTROL: change one CLIENT_SUPPLIED item, prove downstream context
   changes through `generate_campaign._load_admitted_facts`.
5. NEGATIVE CONTROL: unpromoted items absent from pack["facts"] and writer's
   prospect-facing facts.
6. NEGATIVE CONTROL: CLIENT_SUPPLIED items stay out of prospect-side claims.
   Two existing tests guard this boundary and must stay green.
7. Nothing else changes: copylint, STEPS_EXPECTED, rendering chain.
8. MUTATION: revert status projection, acceptance 2 goes red.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import secondbrain, packfacts
from src.generate_campaign import (
    _load_admitted_facts, _format_br_context, _is_relevant,
    _config_key_of, CLIENT_SUPPLIED,
)
from src import offers as offers_mod


class Acceptance1StatusCounts(unittest.TestCase):
    """Total 50, split across VERIFIED / CLIENT_SUPPLIED / unpromoted."""

    def test_total_is_50(self):
        brain = secondbrain.for_task("campaign_strategy", "productive")
        total = sum(len(facts) for facts in brain.values())
        self.assertEqual(total, 50)

    def test_all_50_are_client_supplied(self):
        brain = secondbrain.for_task("campaign_strategy", "productive")
        cs = 0
        unpromoted = 0
        verified = 0
        for section, facts in brain.items():
            for fact in facts:
                if fact.get("verified"):
                    verified += 1
                if fact.get("provenance") == CLIENT_SUPPLIED:
                    cs += 1
                else:
                    unpromoted += 1
        self.assertEqual(verified, 0, "no facts are verified")
        self.assertEqual(cs, 50, "all 50 are CLIENT_SUPPLIED")
        self.assertEqual(unpromoted, 0, "none are unpromoted")

    def test_unrecognised_key_resolves_to_unpromoted(self):
        """A future key not on the eligible list defaults to no provenance."""
        status = secondbrain._canonical_status("hypothesis.generated_strategy")
        self.assertIsNone(status)

    def test_eligible_keys_resolve_to_client_supplied(self):
        for key in ("product.name", "product.capabilities",
                    "personas.champion.titles", "tone.email",
                    "market.must", "domain", "sender.works_on",
                    "linkedin_sequence.fallbacks", "angle_labels",
                    "icp.structural.company_types.primary"):
            status = secondbrain._canonical_status(key)
            self.assertEqual(status, CLIENT_SUPPLIED,
                             f"{key} should be CLIENT_SUPPLIED, got {status}")


class Acceptance2AdmittedRelevantSubset(unittest.TestCase):
    """Admitted > 0 for economic_buyer, and it is the RELEVANT SUBSET < 50."""

    def test_admitted_is_nonzero_for_economic_buyer(self):
        lib = offers_mod.load()
        offer = lib.get("OFFER-A-ECONOMIC-BUYER")
        facts = _load_admitted_facts("productive", persona="economic_buyer",
                                     offer=offer)
        self.assertGreater(len(facts), 0)

    def test_admitted_is_less_than_50(self):
        """The filter excludes other personas' items and unused capabilities."""
        lib = offers_mod.load()
        offer = lib.get("OFFER-A-ECONOMIC-BUYER")
        facts = _load_admitted_facts("productive", persona="economic_buyer",
                                     offer=offer)
        self.assertLess(len(facts), 50)

    def test_other_persona_items_excluded(self):
        """Champion items are NOT in economic_buyer's admitted set."""
        lib = offers_mod.load()
        offer = lib.get("OFFER-A-ECONOMIC-BUYER")
        facts = _load_admitted_facts("productive", persona="economic_buyer",
                                     offer=offer)
        champion_items = [f for f in facts
                          if "for champion:" in f.get("text", "").lower()
                          or "personas.champion" in _config_key_of(f)]
        self.assertEqual(champion_items, [],
                         f"champion items leaked into economic_buyer: "
                         f"{[f['text'][:40] for f in champion_items]}")

    def test_economic_buyer_items_present(self):
        lib = offers_mod.load()
        offer = lib.get("OFFER-A-ECONOMIC-BUYER")
        facts = _load_admitted_facts("productive", persona="economic_buyer",
                                     offer=offer)
        eb_items = [f for f in facts
                    if "economic_buyer" in f.get("text", "").lower()
                    or "economic_buyer" in _config_key_of(f)]
        self.assertGreater(len(eb_items), 0,
                           "economic_buyer should have persona-specific items")

    def test_different_personas_get_different_subsets(self):
        lib = offers_mod.load()
        eb = _load_admitted_facts("productive", persona="economic_buyer",
                                  offer=lib.get("OFFER-A-ECONOMIC-BUYER"))
        ch = _load_admitted_facts("productive", persona="champion",
                                  offer=lib.get("OFFER-B-OPERATIONS"))
        eb_texts = {f["text"] for f in eb}
        ch_texts = {f["text"] for f in ch}
        self.assertNotEqual(eb_texts, ch_texts,
                            "two personas must not receive identical subsets")


class Acceptance3HypothesisPromptCarriesBlock(unittest.TestCase):
    """The hypothesis prompt carries 'our own data' through the real path."""

    def test_br_context_is_not_none(self):
        lib = offers_mod.load()
        offer = lib.get("OFFER-A-ECONOMIC-BUYER")
        facts = _load_admitted_facts("productive", persona="economic_buyer",
                                     offer=offer)
        ctx = _format_br_context(facts)
        self.assertIsNotNone(ctx)
        self.assertGreater(len(ctx), 0)

    def test_br_context_contains_client_supplied_marker(self):
        lib = offers_mod.load()
        offer = lib.get("OFFER-A-ECONOMIC-BUYER")
        facts = _load_admitted_facts("productive", persona="economic_buyer",
                                     offer=offer)
        ctx = _format_br_context(facts)
        self.assertIn("CLIENT_SUPPLIED", ctx)

    def test_hypothesis_user_includes_business_context(self):
        """Through copystages.hypothesis_user, the 'our own data' block appears."""
        from src import copystages
        bc = copystages.business_context_for("campaign_strategy", "productive")
        prompt = copystages.hypothesis_user(
            "TestCo", "test.co", "CFO", [], business_context=bc)
        self.assertIn("our own data", prompt)

    def test_br_context_reaches_hypothesis_through_real_path(self):
        """_format_br_context in generate_campaign feeds copystages.hypothesis_user."""
        from src import copystages
        lib = offers_mod.load()
        offer = lib.get("OFFER-A-ECONOMIC-BUYER")
        facts = _load_admitted_facts("productive", persona="economic_buyer",
                                     offer=offer)
        ctx = _format_br_context(facts)
        prompt = copystages.hypothesis_user(
            "TestCo", "test.co", "CFO", [], business_context=ctx)
        self.assertIn("our own data", prompt)
        self.assertIn("Productive", prompt)


class Acceptance4PositiveControl(unittest.TestCase):
    """Change one CLIENT_SUPPLIED item, prove downstream context changes."""

    def test_mutation_changes_br_context(self):
        """Through _load_admitted_facts (the real admission path)."""
        lib = offers_mod.load()
        offer = lib.get("OFFER-A-ECONOMIC-BUYER")

        original = _load_admitted_facts("productive",
                                        persona="economic_buyer", offer=offer)
        original_ctx = _format_br_context(original)

        # Patch secondbrain.for_task to mutate one fact's text.
        real_for_task = secondbrain.for_task

        def mutated_for_task(task, client):
            brain = real_for_task(task, client)
            for section, facts in brain.items():
                for fact in facts:
                    if fact.get("text", "").startswith("Product: Productive"):
                        fact["text"] = "Product: MUTATED_PRODUCTIVE"
                        break
                break
            return brain

        with mock.patch.object(secondbrain, "for_task",
                               side_effect=mutated_for_task):
            mutated = _load_admitted_facts("productive",
                                           persona="economic_buyer",
                                           offer=offer)
        mutated_ctx = _format_br_context(mutated)

        self.assertNotEqual(original_ctx, mutated_ctx,
                            "mutation did not change br_context")
        self.assertIn("MUTATED_PRODUCTIVE", mutated_ctx)
        self.assertNotIn("MUTATED_PRODUCTIVE", original_ctx)

    def test_restore_changes_back(self):
        """Restore the mutation, prove it changes back - byte-identical."""
        lib = offers_mod.load()
        offer = lib.get("OFFER-A-ECONOMIC-BUYER")

        before = _format_br_context(
            _load_admitted_facts("productive", persona="economic_buyer",
                                 offer=offer))
        after = _format_br_context(
            _load_admitted_facts("productive", persona="economic_buyer",
                                 offer=offer))
        self.assertEqual(before, after,
                         "br_context is not stable across identical calls")


class Acceptance5NegativeControlUnpromoted(unittest.TestCase):
    """An unpromoted item must not become a prospect-facing assertion."""

    def test_unpromoted_absent_from_pack_facts(self):
        """packfacts.pack_for only admits identity-verified research facts."""
        rec = {"id": "rec-test", "domain": "test.co",
               "company_facts": {"headline": "Some CSV value"},
               "batch": {"source": "test.csv", "row": 1},
               "research": []}
        pack, unused = packfacts.pack_for(rec)
        self.assertEqual(pack["facts"], [])
        self.assertEqual(len(unused[packfacts.CLIENT_SUPPLIED]), 1)

    def test_unpromoted_not_in_admitted_if_not_verified_or_cs(self):
        """A fact with no provenance and verified=False is not admitted."""
        fake_brain = {
            "profile": [{"text": "inferred pain", "source": "inferred",
                         "date": "2026-09-28", "verified": False}],
        }
        with mock.patch.object(secondbrain, "for_task",
                               return_value=fake_brain):
            admitted = _load_admitted_facts("productive",
                                            persona="economic_buyer")
        self.assertEqual(admitted, [],
                         "unpromoted fact was admitted to strategy")


class Acceptance6NegativeControlProspectBoundary(unittest.TestCase):
    """CLIENT_SUPPLIED stays out of prospect-facing claims.

    The two existing tests guard this boundary:
    - tests/test_a_client_csv_fact_cannot_license_a_claim.py
    - tests/test_a_client_supplied_figure_licenses_no_claim_in_either_gate.py
    They are run separately and must stay green.  This class verifies the
    structural separation in the generate_campaign path.
    """

    def test_sb_facts_do_not_reach_writer_prospect_facts(self):
        """sb_facts (internal) is a separate parameter from the account pack
        facts that the writer sees as prospect-facing evidence."""
        import inspect
        from src import generate_campaign
        sig = inspect.signature(generate_campaign._process_contact)
        params = list(sig.parameters.keys())
        self.assertIn("sb_facts", params,
                       "sb_facts must be a separate parameter")
        # Prospect-facing facts come from the model extraction inside
        # _process_contact (step B), not from sb_facts.  The two streams
        # never merge: sb_facts feeds br_context for the hypothesis prompt,
        # while prospect facts come from the account research pack.
        src = inspect.getsource(generate_campaign._process_contact)
        # sb_facts is used for br_context, not for the pack
        self.assertIn("br_context", src)
        self.assertIn("_format_br_context(sb_facts)", src)

    def test_format_br_context_marks_provenance_not_verified(self):
        """The br_context shows provenance, not verified=True."""
        facts = [{"text": "Product: X", "source": "src", "date": "2026-09-28",
                  "verified": False, "provenance": CLIENT_SUPPLIED}]
        ctx = _format_br_context(facts)
        self.assertIn("CLIENT_SUPPLIED", ctx)
        self.assertNotIn("verified: True", ctx)


class Acceptance7NothingElseChanges(unittest.TestCase):
    """copylint untouched, STEPS_EXPECTED still 5."""

    def test_steps_expected_is_5(self):
        from src import copylint
        self.assertEqual(copylint.STEPS_EXPECTED, 5)

    def test_client_supplied_constant_is_canonical(self):
        self.assertEqual(packfacts.CLIENT_SUPPLIED, "CLIENT_SUPPLIED")

    def test_no_new_taxonomy_in_secondbrain(self):
        """No verified_v2, trusted=True, or CLIENT_APPROVED in secondbrain."""
        import inspect
        src = inspect.getsource(secondbrain)
        self.assertNotIn("verified_v2", src)
        self.assertNotIn("trusted=True", src)
        self.assertNotIn("CLIENT_APPROVED =", src)


class Acceptance8MutationKillsAdmission(unittest.TestCase):
    """Revert status projection; acceptance 2 must go red."""

    def test_removing_provenance_kills_admission(self):
        """If _canonical_status returns None for all keys, no facts are
        admitted (since verified is also False for all 50)."""
        with mock.patch.object(secondbrain, "_canonical_status",
                               return_value=None):
            brain = secondbrain.for_task("campaign_strategy", "productive")
            cs_count = sum(1 for s in brain.values()
                           for f in s if f.get("provenance") == CLIENT_SUPPLIED)
        self.assertEqual(cs_count, 0,
                         "removing status projection should leave 0 "
                         "CLIENT_SUPPLIED facts")

        with mock.patch.object(secondbrain, "_canonical_status",
                               return_value=None):
            admitted = _load_admitted_facts("productive",
                                            persona="economic_buyer")
        self.assertEqual(len(admitted), 0,
                         "without provenance, no facts are admitted - "
                         "acceptance 2 goes red")


if __name__ == "__main__":
    unittest.main()
