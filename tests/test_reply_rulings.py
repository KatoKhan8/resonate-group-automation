"""The operator's three rulings on reply classification, 2026-10-03.

Lane 3 put three questions to the operator (`docs/PHASE2-UNMATCHED-
CLASSIFICATION-2026-10-03.md`, "Odluke za operatera"). All three came back.
This file is the executable form of the answers, and it is written so that
a BLANKET change cannot satisfy it: every ruling has at least one test that
fails without exactly that change, and at least one control that passes
both before and after, so widening a pattern list or promoting a whole
class is caught rather than rewarded.

**Ruling 1 - "a question about the offer" SPLITS.** The broad limb (any
question about the offer) reaches a human. The narrow limb - price, how it
works, a demo, and nothing else - counts toward the primary metric. The two
jobs stop having to agree, which is the whole of the ruling: reachability
is generous because the cost of a false positive is one person reading one
email, and the metric is strict because it is reported outward and the
classifier's corpus-wide precision on `positive` was measured at 38.5%.

**Ruling 2 - a past-failure objection is `objection`, routes to
`needs_a_person`, and is NOT `negative`.** "We tried this before and it did
not work" is a conversation that has started, not a refusal. The operator
accepted the named consequence: it is only real once `objection` carries a
policy, so `objection` leaves `unknown` - the one outcome `OUTCOME_POLICY`
has no entry for - and resolves to one.

**Ruling 3 - an EA redirect HOLDS the cadence for that person AND raises a
referral to the person named.** Volume measured at 3 in 899. The hold was
true before this change only as an accident of `unknown` having no policy;
it is now ruled, named and configurable. The referral is raised through the
same event and the same resolver every other class uses - no activation,
and no new permission.
"""
import unittest

from src import (accountpolicy as ap, account, events, referral, replies,
                 signals, store, tagsync)
from tests.campaignbase import CampaignTest

WS = "productive"
JOHN, SARAH = "john", "sarah"


class RulingTest(CampaignTest):

    def record(self, rid="rulings"):
        rec = store.new_record(rid, "domains", WS, "Acme Ltd", "acme.test")
        rec["contacts"] = [
            {"key": JOHN, "name": "John Smith", "title": "COO",
             "email": "j@acme.test", "selected": True,
             "priority": account.PRIMARY},
            {"key": SARAH, "name": "Sarah Jones", "title": "CEO",
             "email": "s@acme.test", "selected": True,
             "priority": account.SECONDARY},
        ]
        store.save([rec])
        return rec

    def kinds(self, rec):
        return [e.get("type") for e in rec.get("events") or []]

    def event(self, rec, kind):
        for entry in rec.get("events") or []:
            if entry.get("type") == kind:
                return entry
        return None


# --------------------------------------------------------------- ruling 1

#: Narrow by the operator's own words: price, how it works, a demo.
#:
#: Every one of these is classified `question` on master TODAY - measured,
#: not assumed. That matters, because a reply the rules already call
#: `positive` ("what does it cost?" matches POSITIVE_PATTERNS) counted
#: toward the metric before this change and proves nothing about it.
NARROW = (
    "how does this work?",                          # how it works
    "how exactly does it work in practice?",        # how it works
    "what would this cost for a team of twenty?",   # price
    "when could we see a demo?",                    # a demo
)

#: Broad: a question about the offer that is not one of the three. Each one
#: must still reach a human and must not touch the metric.
#:
#: The first is scenario S15, and it is the case the ruling turns on. It
#: asks how the offer would work WITH THEIR OWN TOOLING, which is a
#: question about fit rather than about how the thing works - lane 3's own
#: Q1 listed "how it fits" under the broad reading. Anything not clearly
#: narrow stays broad.
BROAD = (
    "how would this work with the tooling we already run?",
    "can you handle multi-currency invoicing?",
    "what is your company size?",
    "how do you get the data?",
)


class AQuestionAboutTheOfferSplits(RulingTest):

    def test_the_narrow_limb_counts_toward_the_metric(self):
        """Ruling 1, the half that moves a number."""
        for text in NARROW:
            verdict = replies.classify(text)
            self.assertEqual(verdict.get("question_scope"),
                             replies.QUESTION_NARROW, text)
            self.assertTrue(replies.counts_as_positive(verdict), text)

    def test_the_broad_limb_does_not_count_toward_the_metric(self):
        """And this is the half that protects it. 38.5% precision."""
        for text in BROAD:
            verdict = replies.classify(text)
            self.assertEqual(verdict["classification"], replies.QUESTION, text)
            self.assertEqual(verdict.get("question_scope"),
                             replies.QUESTION_BROAD, text)
            self.assertFalse(replies.counts_as_positive(verdict), text)

    def test_a_narrow_phrasing_tied_to_their_own_stack_stays_broad(self):
        """The conservative half of the ruling, and the case that needs it.

        "How does this work?" is narrow. "How does this work WITH OUR
        STACK?" matches the same narrow pattern and is a question about
        FIT, which lane 3's Q1 put under the broad reading. The guard can
        only ever move a reply from narrow to broad, so a mistake in it
        costs the metric a row it may have been owed and can never hand it
        one it is not.
        """
        for text in ("how does this work with our stack?",
                     "how does it work alongside the tools we already use?",
                     "how does this work if we already run Workday?"):
            verdict = replies.classify(text)
            self.assertEqual(verdict["classification"], replies.QUESTION, text)
            self.assertEqual(verdict.get("question_scope"),
                             replies.QUESTION_BROAD, text)
            self.assertFalse(replies.counts_as_positive(verdict), text)

    def test_both_limbs_reach_a_person(self):
        """Reachability is the generous job. Narrow is a SUBSET of broad."""
        for text in NARROW + BROAD:
            verdict = replies.classify(text)
            if verdict["classification"] != replies.QUESTION:
                continue
            outcome = ap.CLASSIFIER_OUTCOME[verdict["classification"]]
            self.assertEqual(outcome, ap.NEEDS_A_PERSON, text)
            plan = ap.effects(outcome)
            self.assertTrue(plan["review"], text)
            self.assertEqual(plan["replier"], ap.HOLD, text)

    def test_a_narrow_question_is_still_not_a_positive_classification(self):
        """The metric moved. The CLASS did not, and must not.

        Promoting the class would fire `POSITIVE_REPLY_DETECTED`, the
        first-human-reply client trigger and `reply.on_positive` - three
        permissions nobody granted. The split exists precisely so the metric
        can move without them.
        """
        for text in NARROW:
            verdict = replies.classify(text)
            self.assertNotEqual(verdict["classification"], replies.POSITIVE,
                                text)

    def test_the_metric_is_recorded_on_the_event_not_recomputed(self):
        rec = self.record("r1-event")
        replies.apply(rec, JOHN, "how does this work?", channel="email")
        entry = self.event(rec, events.REPLY_CLASSIFIED)
        self.assertTrue(entry.get("counts_as_positive"))
        self.assertNotIn(events.POSITIVE_REPLY_DETECTED, self.kinds(rec))

    def test_a_broad_question_records_the_metric_as_false(self):
        rec = self.record("r1-broad")
        replies.apply(rec, JOHN,
                      "how would this work with the tooling we already run?",
                      channel="email")
        entry = self.event(rec, events.REPLY_CLASSIFIED)
        self.assertIs(entry.get("counts_as_positive"), False)
        self.assertEqual(entry.get("question_scope"), replies.QUESTION_BROAD)

    # ------------------------------------------------------- the controls

    def test_only_two_things_count_toward_the_metric(self):
        """THE ANTI-BLANKET CONTROL.

        A change that counted every warm-looking class, or every class with
        a policy, or simply returned True, passes every test above and
        fails this one. The metric is `positive` plus the narrow question
        limb. Nothing else, and that is checked by enumeration rather than
        by example.
        """
        counting = {replies.POSITIVE, replies.QUESTION}
        for category in replies.CATEGORIES:
            verdict = {"classification": category}
            if category in counting:
                continue
            self.assertFalse(replies.counts_as_positive(verdict), category)
        # And a QUESTION only counts on the narrow limb.
        self.assertFalse(replies.counts_as_positive(
            {"classification": replies.QUESTION,
             "question_scope": replies.QUESTION_BROAD}))
        # A verdict carrying no scope at all is not narrow. Missing
        # evidence is never positive evidence.
        self.assertFalse(replies.counts_as_positive(
            {"classification": replies.QUESTION}))
        self.assertFalse(replies.counts_as_positive(None))

    def test_an_ordinary_positive_still_counts_and_still_alerts(self):
        """Control: passes before and after. The metric kept its old half."""
        verdict = replies.classify("sounds good, let's talk next week")
        self.assertEqual(verdict["classification"], replies.POSITIVE)
        self.assertTrue(replies.is_positive(verdict))

    def test_a_refusal_is_untouched_by_any_of_this(self):
        """Control: passes before and after."""
        verdict = replies.classify("not interested, please remove me "
                                   "from your list")
        self.assertIn(verdict["classification"],
                      (replies.UNSUBSCRIBE, replies.NEGATIVE))

    def test_the_question_rule_was_not_widened(self):
        """Control: passes before and after.

        Ruling 1 splits the class. It does not grow it. A reply that was
        not a question yesterday is not one today.
        """
        for text in ("thanks for reaching out", "we are all set for now",
                     "I have passed this on to Mark Reynolds"):
            self.assertNotEqual(replies.classify(text)["classification"],
                                replies.QUESTION, text)


# --------------------------------------------------------------- ruling 2

PAST_FAILURE = (
    "we tried something like this before and it did not work for us",
    "We've tried this before and it didn't work.",
    "we tried an agency like yours last year and it went nowhere",
)


class APastFailureIsAnObjection(RulingTest):

    def test_a_past_failure_classifies_as_an_objection(self):
        for text in PAST_FAILURE:
            self.assertEqual(replies.classify(text)["classification"],
                             replies.OBJECTION, text)

    def test_a_past_failure_is_not_negative(self):
        """The ruling's own words, and the error that would be expensive.

        Control in one direction: it was not `negative` before either, so a
        change that got here by widening NEGATIVE fails.
        """
        for text in PAST_FAILURE:
            self.assertNotEqual(replies.classify(text)["classification"],
                                replies.NEGATIVE, text)

    def test_an_objection_now_carries_a_policy_of_its_own(self):
        """The named consequence the operator accepted.

        Before: `objection` -> `unknown`, the one outcome `OUTCOME_POLICY`
        has no entry for, so `resolve` returned `key: None` and the ruling
        would have been a label and nothing else.
        """
        outcome = ap.CLASSIFIER_OUTCOME[replies.OBJECTION]
        self.assertEqual(outcome, ap.NEEDS_A_PERSON)
        self.assertNotEqual(outcome, ap.UNKNOWN)
        decision = ap.resolve(outcome)
        self.assertIsNotNone(decision["key"])
        self.assertIn(decision["key"], ap.BY_KEY)

    def test_an_objection_routes_to_a_person_and_holds(self):
        rec = self.record("r2-apply")
        replies.apply(rec, JOHN, PAST_FAILURE[0], channel="email")
        entry = self.event(rec, events.REPLY_CLASSIFIED)
        self.assertEqual(entry.get("classification"), replies.OBJECTION)
        self.assertEqual(entry.get("outcome"), ap.NEEDS_A_PERSON)
        contact = {c["key"]: c for c in rec["contacts"]}[JOHN]
        self.assertEqual(ap.contact_state(contact)[0], ap.HOLD)

    def test_an_objection_does_not_count_toward_the_metric(self):
        for text in PAST_FAILURE:
            self.assertFalse(
                replies.counts_as_positive(replies.classify(text)), text)

    # ------------------------------------------------------- the controls

    def test_a_refusal_wearing_an_objection_still_refuses(self):
        """Control: passes before and after.

        "We already use Harvest, no thanks" is a door closing, and NEGATIVE
        ranks above OBJECTION for exactly that reason. A fix that reordered
        the rules to make the past-failure case pass breaks this.
        """
        verdict = replies.classify("we already use Harvest, no thanks")
        self.assertEqual(verdict["classification"], replies.NEGATIVE)

    def test_the_objections_that_already_worked_still_work(self):
        """Control: passes before and after."""
        for text in ("that is too expensive for us",
                     "we already use something for this",
                     "not a priority right now"):
            self.assertEqual(replies.classify(text)["classification"],
                             replies.OBJECTION, text)

    def test_a_past_attempt_with_no_stated_failure_is_not_swept_in(self):
        """FAIL CLOSED. The ruling names a past-FAILURE objection.

        "We tried this before" with nothing about how it went is not a
        stated barrier, and a pattern loose enough to take it would take
        "we tried your competitor before and loved it" with it.
        """
        for text in ("we tried something like this before",
                     "we have tried a few of these over the years"):
            self.assertNotEqual(replies.classify(text)["classification"],
                                replies.OBJECTION, text)

    def test_a_past_failure_never_stops_the_person_permanently(self):
        """It is a conversation that has started. Holding is the most it does."""
        plan = ap.effects(ap.CLASSIFIER_OUTCOME[replies.OBJECTION])
        self.assertEqual(plan["replier"], ap.HOLD)
        self.assertNotEqual(plan["replier"], ap.SUPPRESS)


# --------------------------------------------------------------- ruling 3

EA_NAMING_SOMEBODY = (
    ("I am the executive assistant to Jane Hopkins. Please send anything "
     "for her through me.", "Jane Hopkins"),
    ("I look after Mark Reynolds' diary, please go through me.",
     "Mark Reynolds"),
    ("On behalf of Mr Thomas Grant, please direct all enquiries to me.",
     "Thomas Grant"),
)


class AnEaRedirectHoldsAndRaisesAReferral(RulingTest):

    def test_the_ea_redirect_has_a_named_outcome_with_a_policy(self):
        outcome = ap.CLASSIFIER_OUTCOME[replies.ASSISTANT_REDIRECT]
        self.assertEqual(outcome, ap.NEEDS_A_PERSON)
        self.assertIsNotNone(ap.resolve(outcome)["key"])

    def test_the_ea_redirect_holds_the_cadence_for_that_person(self):
        """Control AND ruling: this held before, as an accident of `unknown`
        having no policy. It must still hold now that it has one."""
        rec = self.record("r3-hold")
        replies.apply(rec, JOHN, EA_NAMING_SOMEBODY[0][0], channel="email")
        contact = {c["key"]: c for c in rec["contacts"]}[JOHN]
        self.assertEqual(ap.contact_state(contact)[0], ap.HOLD)

    def test_the_ea_redirect_raises_a_referral_to_the_person_named(self):
        for text, name in EA_NAMING_SOMEBODY:
            rec = self.record("r3-" + name.replace(" ", "-"))
            verdict = replies.apply(rec, JOHN, text, channel="email")
            self.assertEqual(verdict["verdict"]["classification"],
                             replies.ASSISTANT_REDIRECT, text)
            entry = self.event(rec, events.REFERRAL_MENTIONED)
            self.assertIsNotNone(entry, text)
            self.assertIn(name, entry.get("named") or "", text)

    def test_the_referral_is_raised_and_never_acted_on(self):
        """The 2026-09-22 ruling stands: no automation answers the EA.

        `reply.activate_referred_contact` is reachable from REFERRAL only.
        An EA redirect must not inherit it, and must not become REFERRAL.
        """
        outcome = ap.CLASSIFIER_OUTCOME[replies.ASSISTANT_REDIRECT]
        self.assertNotEqual(outcome, ap.REFERRAL)
        self.assertFalse(ap.effects(outcome)["activate_referred"])
        rec = self.record("r3-noact")
        replies.apply(rec, JOHN, EA_NAMING_SOMEBODY[0][0], channel="email")
        self.assertNotIn(events.REFERRED_CONTACT_ACTIVATED, self.kinds(rec))

    def test_an_ea_redirect_is_never_positive(self):
        """Control: passes before and after. The operator's 2026-09-22 rule."""
        for text, _ in EA_NAMING_SOMEBODY:
            verdict = replies.classify(text)
            self.assertTrue(replies.is_automated(verdict["classification"]))
            self.assertFalse(replies.is_positive(verdict))
            self.assertFalse(replies.counts_as_positive(verdict))

    # ------------------------------------------------------- the controls

    def test_the_referral_cue_list_was_not_widened(self):
        """THE CONTROL THAT STOPS THIS BEING A WIDENING.

        `referral.CUES` decides whether ANY reply is a referral. The
        assistant shapes are a separate list used only for a reply already
        classified `assistant_redirect`, so a reply that was not a referral
        yesterday is not one today.
        """
        for text, _ in EA_NAMING_SOMEBODY:
            body = replies.normalise(text)
            self.assertEqual(referral.evidence(body)["names"], [], text)
            self.assertFalse(replies.mentions_referral(text), text)

    def test_a_reply_that_is_not_an_ea_redirect_raises_nothing(self):
        """Control: passes before and after."""
        rec = self.record("r3-neg")
        replies.apply(rec, JOHN, "not interested, thanks", channel="email")
        self.assertNotIn(events.REFERRAL_MENTIONED, self.kinds(rec))

    def test_an_ea_who_names_nobody_raises_nothing(self):
        """FAIL CLOSED. No name, no referral - not an empty one."""
        rec = self.record("r3-noname")
        replies.apply(rec, JOHN,
                      "I've forwarded your email to our CEO, he'll be in "
                      "touch if interested.", channel="email")
        self.assertEqual(
            replies.classify("I've forwarded your email to our CEO, he'll "
                             "be in touch if interested.")["classification"],
            replies.ASSISTANT_REDIRECT)
        self.assertNotIn(events.REFERRAL_MENTIONED, self.kinds(rec))

    def test_a_removal_request_never_raises_a_referral(self):
        """Control: passes before and after. The worst thing this could do."""
        rec = self.record("r3-dnc")
        replies.apply(rec, JOHN,
                      "please remove our company from your list - "
                      "speak to Dana Reed if you must", channel="email")
        self.assertNotIn(events.REFERRAL_MENTIONED, self.kinds(rec))


# ------------------------------------------- the vocabulary stays canonical

class NoSecondVocabulary(unittest.TestCase):
    """TASK-1004's rule, applied to the outcome these rulings introduce."""

    def test_the_new_outcome_is_in_the_canonical_set(self):
        self.assertIn(ap.NEEDS_A_PERSON, ap.OUTCOMES)
        self.assertIn(ap.NEEDS_A_PERSON, ap.OUTCOME_LABEL)
        self.assertIn(ap.NEEDS_A_PERSON, ap.OUTCOME_POLICY)

    def test_every_outcome_still_has_an_engagement_name(self):
        for outcome in ap.OUTCOMES:
            if outcome == ap.UNKNOWN:
                continue
            self.assertIn(outcome, signals.ENGAGEMENT_SIGNAL, outcome)

    def test_the_new_outcome_is_not_read_as_a_positive_reply(self):
        """Over-claiming the metric is the expensive error, and a signal is
        a place it could happen quietly."""
        self.assertNotEqual(signals.ENGAGEMENT_SIGNAL[ap.NEEDS_A_PERSON],
                            signals.ENGAGED_POSITIVE)
        self.assertNotEqual(signals.ENGAGEMENT_SIGNAL[ap.NEEDS_A_PERSON],
                            signals.ENGAGED_MEETING)

    def test_the_new_outcome_carries_no_positive_tag(self):
        self.assertIn(ap.NEEDS_A_PERSON, tagsync.OUTCOME_TAGS)
        self.assertIn(ap.NEEDS_A_PERSON, tagsync.STAGE_OF)
        self.assertNotIn(tagsync.POSITIVE,
                         tagsync.OUTCOME_TAGS[ap.NEEDS_A_PERSON])

    def test_the_new_outcome_is_no_more_permissive_than_unknown_was(self):
        """The reply is named and routed. Nothing is allowed that was not."""
        named = ap.effects(ap.NEEDS_A_PERSON)
        unknown = ap.effects(ap.UNKNOWN)
        self.assertEqual(named["replier"], unknown["replier"])
        self.assertEqual(named["account"], unknown["account"])
        self.assertEqual(named["review"], unknown["review"])


if __name__ == "__main__":
    unittest.main()
