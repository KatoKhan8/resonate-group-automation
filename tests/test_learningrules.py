"""Proposed rules, distinguished from unwired code.

Five properties, and every test is one of them:

**A closed vocabulary, enforced.** Unknown statuses and surfaces are refused,
not coerced. A proposal with a typo'd status must not silently become
"proposed" and slip past a rejection that was already recorded.

**A proposal rests on evidence.** A proposal without observation ids is a
preference wearing a proposal's shape. The scheme exists to tell them apart.

**Nothing in code writes an approval.** A programmatic approval attempt
raises. This is the one hard rule, and the test breaks the wiring to prove
the guard is connected.

**A superseded proposal cannot be approved.** The approval path refuses it,
because approving something that was already set aside would create two
truths about one question.

**A rule reaches a surface only from C.** `behind()` returns the approved
rule for a value, or None. An unapproved proposal changes no client answer.
"""
import unittest

from src import learningrules


class ClosedVocabulary(unittest.TestCase):
    """Unknown statuses and surfaces are refused, not coerced."""

    def test_unknown_status_is_refused(self):
        with self.assertRaises(learningrules.LearningRuleError) as ctx:
            learningrules.proposal(
                "p1", observation_ids=["obs1"], surface="copy",
                what="shorten subject lines", status="maybe")
        self.assertIn("unknown status", str(ctx.exception))

    def test_unknown_surface_is_refused(self):
        with self.assertRaises(learningrules.LearningRuleError) as ctx:
            learningrules.proposal(
                "p1", observation_ids=["obs1"], surface="pricing",
                what="change the pricing page")
        self.assertIn("unknown surface", str(ctx.exception))

    def test_known_status_is_accepted(self):
        for status in learningrules.STATUSES:
            entry = learningrules.proposal(
                f"p-{status}", observation_ids=["obs1"], surface="copy",
                what="shorten subject lines", status=status)
            self.assertEqual(entry["status"], status)

    def test_known_surface_is_accepted(self):
        for surface in learningrules.SURFACES:
            entry = learningrules.proposal(
                f"p-{surface}", observation_ids=["obs1"], surface=surface,
                what="change something")
            self.assertEqual(entry["surface"], surface)


class ProposalRestsOnEvidence(unittest.TestCase):
    """A proposal without observation ids is refused."""

    def test_empty_observation_ids_refused(self):
        with self.assertRaises(learningrules.LearningRuleError) as ctx:
            learningrules.proposal(
                "p1", observation_ids=[], surface="copy",
                what="shorten subject lines")
        self.assertIn("observation ids", str(ctx.exception))

    def test_none_observation_ids_refused(self):
        with self.assertRaises(learningrules.LearningRuleError):
            learningrules.proposal(
                "p1", observation_ids=None, surface="copy",
                what="shorten subject lines")

    def test_observation_ids_carried(self):
        entry = learningrules.proposal(
            "p1", observation_ids=["obs-1", "obs-2"], surface="copy",
            what="shorten subject lines")
        self.assertEqual(entry["observation_ids"], ("obs-1", "obs-2"))

    def test_empty_string_in_observation_ids_refused(self):
        with self.assertRaises(learningrules.LearningRuleError):
            learningrules.proposal(
                "p1", observation_ids=["obs-1", ""], surface="copy",
                what="shorten subject lines")


class ProgrammaticApprovalRaises(unittest.TestCase):
    """The one hard rule. Nothing in code writes an approval."""

    def test_approve_raises(self):
        entry = learningrules.proposal(
            "p1", observation_ids=["obs1"], surface="copy",
            what="shorten subject lines")
        with self.assertRaises(learningrules.LearningRuleError) as ctx:
            learningrules.approve(entry, approved_by="bot", reason="looks good")
        self.assertIn("no code path may write an approval",
                      str(ctx.exception))

    def test_approve_raises_even_for_a_valid_proposal(self):
        """The guard fires regardless of the proposal's state."""
        entry = learningrules.proposal(
            "p1", observation_ids=["obs1"], surface="icp",
            what="narrow to agencies of 50+")
        with self.assertRaises(learningrules.LearningRuleError):
            learningrules.approve(entry)


class SupersededCannotBeApproved(unittest.TestCase):
    """A superseded proposal cannot be approved."""

    def test_superseded_proposal_cannot_be_approved(self):
        old = learningrules.proposal(
            "p1", observation_ids=["obs1"], surface="copy",
            what="shorten subject lines")
        new = learningrules.proposal(
            "p2", observation_ids=["obs1", "obs2"], surface="copy",
            what="shorten subject lines to one sentence")
        superseded = learningrules.supersede(old, new)
        self.assertEqual(superseded["status"], learningrules.SUPERSEDED)
        with self.assertRaises(learningrules.LearningRuleError) as ctx:
            learningrules.mark_approved("p1", superseded)
        self.assertIn("superseded", str(ctx.exception))

    def test_only_proposed_may_be_approved(self):
        rejected = learningrules.proposal(
            "p1", observation_ids=["obs1"], surface="copy",
            what="shorten subject lines", status=learningrules.REJECTED)
        with self.assertRaises(learningrules.LearningRuleError):
            learningrules.mark_approved("p1", rejected)


class RuleReachesSurfaceOnlyFromC(unittest.TestCase):
    """behind() returns the approved rule for a value, or None."""

    def test_behind_returns_approved_rule(self):
        rule = learningrules.proposal(
            "p1", observation_ids=["obs1"], surface="copy",
            what="shorten subject lines to one sentence",
            status=learningrules.APPROVED)
        found = learningrules.behind([rule], "copy", "shorten subject lines")
        self.assertEqual(found["id"], "p1")

    def test_behind_returns_none_for_unapproved(self):
        rule = learningrules.proposal(
            "p1", observation_ids=["obs1"], surface="copy",
            what="shorten subject lines",
            status=learningrules.PROPOSED)
        found = learningrules.behind([rule], "copy", "shorten subject lines")
        self.assertIsNone(found)

    def test_behind_returns_none_for_no_match(self):
        rule = learningrules.proposal(
            "p1", observation_ids=["obs1"], surface="copy",
            what="shorten subject lines",
            status=learningrules.APPROVED)
        found = learningrules.behind([rule], "icp", "shorten subject lines")
        self.assertIsNone(found)

    def test_behind_refuses_unknown_surface(self):
        with self.assertRaises(learningrules.LearningRuleError):
            learningrules.behind([], "pricing", "anything")

    def test_approved_for_filters_by_surface(self):
        copy_rule = learningrules.proposal(
            "p1", observation_ids=["obs1"], surface="copy",
            what="shorten subjects", status=learningrules.APPROVED)
        icp_rule = learningrules.proposal(
            "p2", observation_ids=["obs2"], surface="icp",
            what="narrow to agencies", status=learningrules.APPROVED)
        proposed = learningrules.proposal(
            "p3", observation_ids=["obs3"], surface="copy",
            what="longer bodies", status=learningrules.PROPOSED)
        found = learningrules.approved_for(
            [copy_rule, icp_rule, proposed], "copy")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["id"], "p1")

    def test_approved_for_refuses_unknown_surface(self):
        with self.assertRaises(learningrules.LearningRuleError):
            learningrules.approved_for([], "pricing")


class ObservationAddressable(unittest.TestCase):
    """Observations are addressable by id, not recomputed on every read."""

    def test_observation_requires_id(self):
        with self.assertRaises(learningrules.LearningRuleError):
            learningrules.observation("", what="reply rate by cohort")

    def test_observation_requires_what(self):
        with self.assertRaises(learningrules.LearningRuleError):
            learningrules.observation("obs1", what="")

    def test_observation_carries_id(self):
        obs = learningrules.observation("obs-42", what="reply rate by cohort")
        self.assertEqual(obs["id"], "obs-42")


class StatusTransitions(unittest.TestCase):
    """Rejection and supersession follow the vocabulary."""

    def test_reject_a_proposed(self):
        entry = learningrules.proposal(
            "p1", observation_ids=["obs1"], surface="copy",
            what="shorten subject lines")
        rejected = learningrules.reject(
            "p1", entry, rejected_by="operator", reason="not enough data")
        self.assertEqual(rejected["status"], learningrules.REJECTED)

    def test_cannot_reject_a_rejected(self):
        entry = learningrules.proposal(
            "p1", observation_ids=["obs1"], surface="copy",
            what="shorten subject lines", status=learningrules.REJECTED)
        with self.assertRaises(learningrules.LearningRuleError):
            learningrules.reject("p1", entry)

    def test_supersede_a_proposed(self):
        old = learningrules.proposal(
            "p1", observation_ids=["obs1"], surface="copy",
            what="shorten subject lines")
        new = learningrules.proposal(
            "p2", observation_ids=["obs1", "obs2"], surface="copy",
            what="shorten to one sentence")
        result = learningrules.supersede(old, new)
        self.assertEqual(result["status"], learningrules.SUPERSEDED)
        self.assertEqual(result["superseded_by"], "p2")

    def test_cannot_supersede_already_superseded(self):
        old = learningrules.proposal(
            "p1", observation_ids=["obs1"], surface="copy",
            what="shorten subject lines")
        mid = learningrules.proposal(
            "p2", observation_ids=["obs1"], surface="copy",
            what="shorten to one sentence")
        newer = learningrules.proposal(
            "p3", observation_ids=["obs1", "obs2"], surface="copy",
            what="drop the subject line entirely")
        superseded = learningrules.supersede(old, mid)
        with self.assertRaises(learningrules.LearningRuleError):
            learningrules.supersede(superseded, newer)


if __name__ == "__main__":
    unittest.main()
