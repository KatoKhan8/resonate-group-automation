"""Strategy is decided ONCE PER SEGMENT, not once per lead.

TASK-320. The defect: at 50 leads in one segment, Stage E made 50 identical
model calls. The fix: `campaignstrategy.for_segment` caches per
(segment_key, persona) and calls the model exactly once.

These tests use `ScriptedModel` - no real model call is made.
"""
import json
import unittest

from src import campaignstrategy, llm


def _scripted_strategy(**overrides):
    """A canned strategy response for ScriptedModel."""
    base = {
        "target_icp": "digital marketing agency, 20-99 people",
        "segment": "US-East/MktgAdv",
        "persona": "economic_buyer",
        "primary_problem": "project margin invisible until the job is done",
        "primary_offer": "OFFER-PR-001",
        "secondary_offer": "OFFER-BU-001",
        "evidence": [],
        "approved_angles": ["margin visibility", "budget burn"],
        "objective": "get a 15-minute discovery call",
        "cta_strategy": "discovery question at email 3, meeting ask at email 5",
        "disqualification_criteria": "no project delivery, pure SaaS",
    }
    base.update(overrides)
    return json.dumps(base)


class TestStrategyIsSegmentInvariant(unittest.TestCase):
    def setUp(self):
        campaignstrategy.clear_cache()

    def test_same_segment_same_persona_returns_same_strategy_id(self):
        """Acceptance 1: stable per segment."""
        model = llm.ScriptedModel(_scripted_strategy())
        a = campaignstrategy.for_segment(
            "US-East/MktgAdv", "economic_buyer", model=model)
        b = campaignstrategy.for_segment(
            "US-East/MktgAdv", "economic_buyer", model=model)
        self.assertEqual(a["strategy_id"], b["strategy_id"],
                         "strategy regenerated per call")

    def test_model_called_once_for_fifty_leads_in_one_segment(self):
        """Acceptance 2: the measured count. 50 calls, 1 model invocation."""
        model = llm.ScriptedModel(_scripted_strategy())
        for _ in range(50):
            campaignstrategy.for_segment(
                "US-East/MktgAdv", "economic_buyer", model=model)
        self.assertEqual(campaignstrategy.model_call_count(), 1,
                         "model called %d times for 50 leads in one segment, "
                         "expected 1" % campaignstrategy.model_call_count())

    def test_two_segments_get_two_strategies(self):
        """Acceptance 3: keyed on segment, not a global singleton."""
        model = llm.ScriptedModel(
            _scripted_strategy(segment="US-East/MktgAdv"),
            _scripted_strategy(
                segment="UK/SEO",
                primary_problem="SEO deliverables tracked in spreadsheets",
                approved_angles=["delivery transparency"],
            ),
        )
        a = campaignstrategy.for_segment(
            "US-East/MktgAdv", "economic_buyer", model=model)
        b = campaignstrategy.for_segment(
            "UK/SEO", "economic_buyer", model=model)
        self.assertNotEqual(a["strategy_id"], b["strategy_id"],
                            "two segments share a strategy_id")
        self.assertEqual(campaignstrategy.model_call_count(), 2,
                         "expected 2 model calls for 2 different segments")

    def test_no_model_call_when_cached(self):
        """Acceptance 4: the second call does not touch the model."""
        model = llm.ScriptedModel(_scripted_strategy())
        campaignstrategy.for_segment(
            "US-East/MktgAdv", "economic_buyer", model=model)
        self.assertEqual(len(model.prompts), 1)
        campaignstrategy.for_segment(
            "US-East/MktgAdv", "economic_buyer", model=model)
        self.assertEqual(len(model.prompts), 1,
                         "model called again for a cached segment")

    def test_strategy_carries_required_fields(self):
        """The strategy dict has every field the task names."""
        model = llm.ScriptedModel(_scripted_strategy())
        s = campaignstrategy.for_segment(
            "US-East/MktgAdv", "economic_buyer", model=model)
        for field in ("strategy_id", "segment_key", "persona",
                       "primary_problem", "primary_offer",
                       "approved_angles", "objective", "cta_strategy",
                       "disqualification_criteria"):
            self.assertIn(field, s, f"strategy missing field: {field}")

    def test_different_persona_gets_different_strategy(self):
        """Persona is part of the cache key, not just segment."""
        model = llm.ScriptedModel(
            _scripted_strategy(persona="economic_buyer"),
            _scripted_strategy(
                persona="champion",
                primary_offer="OFFER-PM-001",
                approved_angles=["project visibility"],
            ),
        )
        a = campaignstrategy.for_segment(
            "US-East/MktgAdv", "economic_buyer", model=model)
        b = campaignstrategy.for_segment(
            "US-East/MktgAdv", "champion", model=model)
        self.assertNotEqual(a["strategy_id"], b["strategy_id"])
        self.assertEqual(campaignstrategy.model_call_count(), 2)

    def test_clear_cache_forces_fresh_call(self):
        """After clear_cache, the same segment triggers a new model call."""
        model = llm.ScriptedModel(_scripted_strategy(), _scripted_strategy())
        campaignstrategy.for_segment(
            "US-East/MktgAdv", "economic_buyer", model=model)
        self.assertEqual(campaignstrategy.model_call_count(), 1)
        self.assertEqual(len(model.prompts), 1)
        campaignstrategy.clear_cache()
        campaignstrategy.for_segment(
            "US-East/MktgAdv", "economic_buyer", model=model)
        self.assertEqual(campaignstrategy.model_call_count(), 1,
                         "counter reset by clear_cache, so 1 fresh call")
        self.assertEqual(len(model.prompts), 2,
                         "model called again after cache clear")


if __name__ == "__main__":
    unittest.main()
