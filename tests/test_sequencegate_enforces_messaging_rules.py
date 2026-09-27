"""The operator's messaging rule, enforced rather than described.

`config/clients/productive-offers.yaml` carries `messaging_rules`, and per
offer `step_objectives` and `ai_capabilities`. Before this, no module in `src/`
read any of them: `grep -rn step_objectives --include=*.py src/` returned
nothing. The rule was data nothing consumed, which is this repository's
signature defect - a value computed correctly that nothing downstream reads.

Every assertion here is on the GATE'S VERDICT for a named check, never on the
text of the source. The tests isolate the three new checks by name, because the
gate runs a dozen other checks and a test asserting on `passed` would pass or
fail for reasons that have nothing to do with the rule under test.
"""
import unittest

from src import sequencegate

# Verbatim from evidence.productive_ai, retrieved 2026-09-27.
TIME_TRACKING_TEXT = ("Productive analyzes calendar events, matches them with "
                      "previous time entries, and automatically fills out "
                      "your time sheets.")
NOTETAKER_TEXT = ("The Notetaker that's integrated directly into your "
                  "workspace. It transcribes, summarizes, and turns action "
                  "items into tasks, so you can go from meeting to work right "
                  "away.")

#: The PyYAML shape: `step_objectives` and `ai_capabilities` as lists of dicts.
OFFER_LIST_SHAPE = {
    "step_objectives": [
        {"step": 1, "objective": "margin visibility"},
        {"step": 2, "objective": "quote versus burn"},
        {"step": 3, "objective": "resource decisions that move margin"},
        {"step": 4, "objective": "Report Intelligence as mechanism"},
        {"step": 5, "objective": "reframe and close"},
    ],
    "ai_capabilities": [
        {"feature": "AI Time Tracking", "page_text": TIME_TRACKING_TEXT},
        {"feature": "AI Notetaker", "page_text": NOTETAKER_TEXT},
        {"feature": "Marble Engine", "page_text": None},
    ],
}

#: The `clients.parse` shape. That parser cannot express a block list at all -
#: only `[a, b]` - so the same data has to arrive as a mapping. Both shapes
#: must produce the same verdict or the gate is reading one loader's accident.
OFFER_MAPPING_SHAPE = {
    "step_objectives": {
        1: "margin visibility",
        2: "quote versus burn",
        3: "resource decisions that move margin",
        4: "Report Intelligence as mechanism",
        5: "reframe and close",
    },
    "ai_capabilities": {
        "AI Time Tracking": {"page_text": TIME_TRACKING_TEXT},
        "AI Notetaker": {"page_text": NOTETAKER_TEXT},
        "Marble Engine": {"page_text": None},
    },
}

RULES = {"max_ai_capabilities_per_message": 1, "ai_required": False}

#: Two customer stories in the real state of all twelve: CLIENT_APPROVED to be
#: named, but page_text null, so nothing about them is licensed.
EVIDENCE_UNLICENSED = {
    "infinum": {"name": "Infinum", "page_text": None},
    "saffron": {"name": "Saffron", "page_text": None},
}


def emails_following_the_spine():
    """One email per objective, each sharing a content word with its own."""
    return {
        "em1": "Margin visibility is usually the thing that arrives late.",
        "em2": "The gap between the quote and the burn is where it shows.",
        "em3": "Resource decisions are what actually move margin week to week.",
        "em4": "Report Intelligence answers that as a mechanism, in plain "
               "language, without digging through reports.",
        "em5": "Happy to reframe this or close it out if the timing is wrong.",
    }


def verdict(emails, offer=OFFER_LIST_SHAPE, rules=RULES, evidence=None,
            linkedin=None, ps=None):
    return sequencegate.check(
        {"emails": emails, "linkedin": linkedin or {}, "ps": ps or {}},
        qualification="QUALIFIED", offer=offer, rules=rules, evidence=evidence)


def failures_for(result, *check_names):
    return [f for f in result["failures"] if f["check"] in check_names]


class StepObjectivesAreEnforced(unittest.TestCase):

    def test_a_sequence_following_the_spine_has_no_objective_failure(self):
        r = verdict(emails_following_the_spine())
        self.assertEqual(failures_for(r, "step_objectives"), [])

    def test_a_step_that_abandons_its_objective_is_refused(self):
        emails = emails_following_the_spine()
        emails["em3"] = ("Just following up on my last note to see whether "
                        "anything has landed on your side.")
        r = verdict(emails)
        got = failures_for(r, "step_objectives")
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["step"], "em3",
                         "the refusal must name the step that broke the spine")

    def test_a_missing_step_the_offer_defines_is_refused(self):
        emails = emails_following_the_spine()
        del emails["em4"]
        r = verdict(emails)
        self.assertEqual([f["step"] for f in
                          failures_for(r, "step_objectives")], ["em4"])

    def test_changing_the_offers_objectives_changes_the_verdict(self):
        """Proof the gate reads the record, not a copy of the spine.

        The same emails are judged against a different offer. If the objectives
        were hardcoded in `sequencegate`, this verdict could not move.
        """
        emails = emails_following_the_spine()
        self.assertEqual(failures_for(verdict(emails), "step_objectives"), [])

        rewritten = {"step_objectives": [
            {"step": 1, "objective": "warehouse logistics throughput"},
            {"step": 2, "objective": "pallet scanning accuracy"},
        ]}
        moved = failures_for(verdict(emails, offer=rewritten),
                             "step_objectives")
        self.assertEqual(sorted(f["step"] for f in moved), ["em1", "em2"])

    def test_both_loader_shapes_agree(self):
        emails = emails_following_the_spine()
        emails["em2"] = "Following up briefly with nothing new to add."
        a = failures_for(verdict(emails, offer=OFFER_LIST_SHAPE),
                         "step_objectives")
        b = failures_for(verdict(emails, offer=OFFER_MAPPING_SHAPE),
                         "step_objectives")
        self.assertEqual([f["step"] for f in a], [f["step"] for f in b])
        self.assertEqual([f["step"] for f in a], ["em2"])

    def test_an_unrecognised_shape_raises_rather_than_disabling_the_check(self):
        """A shape nobody planned for must not silently pass the sequence."""
        with self.assertRaises(ValueError):
            verdict(emails_following_the_spine(),
                    offer={"step_objectives": "margin visibility"})


class AiIsSupportingOnly(unittest.TestCase):

    def test_two_ai_capabilities_in_one_message_are_refused(self):
        emails = emails_following_the_spine()
        emails["em4"] = ("Report Intelligence as a mechanism. AI Time Tracking "
                         "analyzes calendar events and fills out time sheets, "
                         "and the AI Notetaker transcribes meetings and turns "
                         "action items into tasks.")
        r = verdict(emails)
        got = failures_for(r, "ai_supporting_only")
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["step"], "em4")

    def test_exactly_one_ai_capability_is_allowed(self):
        emails = emails_following_the_spine()
        emails["em4"] = ("Report Intelligence as a mechanism. AI Time Tracking "
                         "analyzes calendar events, matches them with previous "
                         "time entries and fills out time sheets.")
        self.assertEqual(
            failures_for(verdict(emails), "ai_supporting_only"), [])

    def test_no_ai_capability_is_allowed_and_never_penalised(self):
        """`ai_required` is false: AI must not be forced into every message."""
        r = verdict(emails_following_the_spine())
        self.assertEqual(
            failures_for(r, "ai_supporting_only", "ai_claim_licensed"), [])

    def test_ai_required_would_refuse_a_message_naming_none(self):
        """The inverse rule works, so the default is a decision not a gap."""
        r = verdict(emails_following_the_spine(),
                    rules={"max_ai_capabilities_per_message": 1,
                           "ai_required": True})
        self.assertTrue(failures_for(r, "ai_supporting_only"))

    def test_the_ceiling_comes_from_the_rules_not_from_the_gate(self):
        emails = emails_following_the_spine()
        emails["em4"] = ("Report Intelligence as a mechanism. AI Time Tracking "
                         "analyzes calendar events, matches them with previous "
                         "time entries and fills out time sheets. The AI "
                         "Notetaker transcribes, summarizes and turns action "
                         "items into tasks.")
        self.assertTrue(failures_for(verdict(emails), "ai_supporting_only"))
        raised = {"max_ai_capabilities_per_message": 2, "ai_required": False}
        self.assertEqual(
            failures_for(verdict(emails, rules=raised), "ai_supporting_only"),
            [])


class AiClaimsTraceToStoredPageText(unittest.TestCase):

    def test_a_feature_with_no_stored_page_text_is_unusable(self):
        emails = emails_following_the_spine()
        emails["em4"] = ("Report Intelligence as mechanism. Marble Engine is "
                         "the engine behind all of it.")
        got = failures_for(verdict(emails), "ai_claim_licensed")
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["step"], "em4")

    def test_a_claim_that_does_not_match_the_page_is_refused(self):
        emails = emails_following_the_spine()
        emails["em4"] = ("Report Intelligence as mechanism. AI Time Tracking "
                         "removes the need for anybody to think about "
                         "administration ever again.")
        got = failures_for(verdict(emails), "ai_claim_licensed")
        self.assertEqual([f["step"] for f in got], ["em4"])

    def test_a_claim_matching_the_stored_page_text_passes(self):
        emails = emails_following_the_spine()
        emails["em4"] = ("Report Intelligence as a mechanism. AI Time Tracking "
                         "analyzes calendar events, matches them with previous "
                         "time entries and fills out time sheets.")
        self.assertEqual(
            failures_for(verdict(emails), "ai_claim_licensed"), [])

    def test_a_customer_with_null_page_text_may_not_be_named_in_copy(self):
        emails = emails_following_the_spine()
        emails["em3"] = ("Resource decisions move margin. Infinum went from 70 "
                         "to 350 people on this.")
        got = failures_for(verdict(emails, evidence=EVIDENCE_UNLICENSED),
                           "ai_claim_licensed")
        self.assertEqual([f["step"] for f in got], ["em3"])

    def test_linkedin_and_ps_are_checked_too(self):
        """Prospect facing is prospect facing, whatever the channel."""
        r = verdict(emails_following_the_spine(),
                    linkedin={"day3": "Marble Engine drives all of this."},
                    ps={"em1": "Saffron did the same."},
                    evidence=EVIDENCE_UNLICENSED)
        steps = {f["step"] for f in failures_for(r, "ai_claim_licensed")}
        self.assertIn("li:day3", steps)
        self.assertIn("ps:em1", steps)


class AnAbsentRuleIsReportedNotPassed(unittest.TestCase):

    def test_no_offer_warns_rather_than_silently_passing(self):
        r = sequencegate.check(
            {"emails": emails_following_the_spine()},
            qualification="QUALIFIED")
        self.assertEqual(failures_for(r, "step_objectives",
                                      "ai_supporting_only",
                                      "ai_claim_licensed"), [])
        self.assertTrue(
            any(w["check"] == "offer_rules" for w in r["warnings"]),
            "an unchecked messaging rule must be reported, not silent")

    def test_an_offer_without_objectives_warns(self):
        r = verdict(emails_following_the_spine(),
                    offer={"ai_capabilities": []})
        self.assertTrue(any(w["check"] == "step_objectives"
                            for w in r["warnings"]))

    def test_the_new_checks_are_declared(self):
        r = verdict(emails_following_the_spine())
        for name in ("step_objectives", "ai_supporting_only",
                     "ai_claim_licensed"):
            self.assertIn(name, r["checks"])


if __name__ == "__main__":
    unittest.main()
