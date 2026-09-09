"""Evidence gets older. Nothing used to notice.

`evidence.make` scores a fact on the day it is found and freezes the answer
onto the row: `age_days`, `freshness_bucket`, `quality`. Every reader since
has trusted those numbers - `usable`, `select`, the dossier, the
personalisation decision, the quality band, the preview - so a fact found in
February was still described as recent in September, because the number
saying it was recent was written in February.

Approval does not catch it. `approval.is_approved` is a fingerprint of the
*text*, and the text does not change when the fact behind it gets old. So an
approved draft stays approved and stays sendable, and step four of a cadence
goes out weeks after step one still saying "recently".

None of this was visible to the suite: the whole of it passed unchanged when
re-ageing was added, which is the argument for this file existing.
"""
import unittest

from src import eligibility as E, evidence, personalization, quality, store
from tests.campaignbase import CampaignTest, contact

FOUND = "2026-02-01"          # the day the fact was published
SOON = "2026-02-10"           # nine days later: fresh
LATER = "2026-06-01"          # four months later: still inside the maximum
MUCH_LATER = "2028-06-01"     # past any freshness policy


def a_fact(published_at=FOUND, today=SOON, fact=None, record="acme",
           contact_key=None, subject=evidence.COMPANY):
    return evidence.make(
        fact or ("Acme opened a Vienna delivery office and is hiring four "
                 "implementation managers to staff it."),
        "https://acme.test/news", "news", "apify", record,
        contact_key=contact_key, published_at=published_at, subject=subject,
        today=today)


class TimeIsTheOnlyThingReDerived(unittest.TestCase):

    def test_a_fact_found_fresh_is_not_fresh_forever(self):
        found = a_fact()
        self.assertEqual(found["freshness_bucket"], evidence.HIGH)
        now = evidence.recheck(found, today=MUCH_LATER)
        self.assertEqual(now["freshness_bucket"], evidence.BACKGROUND)

    def test_the_stored_row_is_not_mutated(self):
        """A reader must not change what the record says. Re-ageing answers
        a question; it does not rewrite the answer to the old one."""
        found = a_fact()
        evidence.recheck(found, today=MUCH_LATER)
        self.assertEqual(found["freshness_bucket"], evidence.HIGH)

    def test_relevance_is_left_exactly_as_scored(self):
        """It is a function of the fact's words against a persona's angle,
        and neither moves while the row sits in state. Re-scoring it would
        need the persona that produced it, which is not on the row."""
        found = a_fact()
        now = evidence.recheck(found, today=MUCH_LATER)
        self.assertEqual(now["relevance_score"], found["relevance_score"])
        self.assertEqual(now["relevance_reasons"], found["relevance_reasons"])

    def test_ageing_never_improves_a_row(self):
        found = a_fact()
        order = {evidence.STRONG: 3, evidence.MEDIUM_Q: 2, evidence.WEAK: 1,
                 evidence.UNUSABLE: 0}
        for day in (SOON, LATER, MUCH_LATER):
            now = evidence.recheck(found, today=day)
            self.assertLessEqual(order[now["quality"]],
                                 order[found["quality"]], day)

    def test_an_undated_fact_does_not_age(self):
        """It was never dated, so there is nothing to grow older. UNKNOWN
        is not a synonym for old and must not decay into one."""
        found = a_fact(published_at=None)
        self.assertEqual(found["freshness_bucket"], evidence.UNKNOWN)
        now = evidence.recheck(found, today=MUCH_LATER)
        self.assertEqual(now["freshness_bucket"], evidence.UNKNOWN)
        self.assertEqual(now["quality"], found["quality"])

    def test_it_says_when_the_verdict_moved_and_which_way(self):
        found = a_fact()
        now = evidence.recheck(found, today=MUCH_LATER)
        self.assertEqual(now["quality_was"], found["quality"])
        self.assertTrue(now["aged_out"])

    def test_aged_out_is_only_true_when_it_crossed_out_of_usable(self):
        """STRONG to MEDIUM is a demotion, not a disqualification, and an
        operator reading `aged_out` needs it to mean the second thing."""
        found = a_fact()
        self.assertIn(found["quality"], evidence.USABLE)
        gentle = evidence.recheck(found, today=LATER)
        self.assertIn(gentle["quality"], evidence.USABLE)
        self.assertFalse(gentle.get("aged_out"))


class BackgroundIsNoLongerComputedAndIgnored(unittest.TestCase):
    """`freshness` has bucketed evidence past the policy maximum as
    BACKGROUND since it was written, and `quality` never read it. A
    three-year-old article could be the sentence a cold email led with, on
    a relevance score alone."""

    def test_a_fact_past_the_maximum_age_is_not_written_from(self):
        old = a_fact(today=MUCH_LATER)
        self.assertEqual(old["freshness_bucket"], evidence.BACKGROUND)
        self.assertNotIn(old["quality"], evidence.USABLE)

    def test_it_is_weak_rather_than_unusable(self):
        """The fact is still true and still belongs on a dossier. What is
        refused is writing from it."""
        old = a_fact(today=MUCH_LATER)
        self.assertEqual(old["quality"], evidence.WEAK)

    def test_relevance_alone_cannot_rescue_it(self):
        self.assertEqual(
            evidence.quality(1.0, evidence.BACKGROUND,
                             "Acme opened a Vienna delivery office."),
            evidence.WEAK)


class TheReadPathReAges(unittest.TestCase):

    def test_usable_re_ages_before_it_filters(self):
        found = a_fact()
        self.assertTrue(evidence.usable([found], today=SOON))
        self.assertFalse(evidence.usable([found], today=MUCH_LATER))

    def test_select_re_ages_too(self):
        found = a_fact()
        self.assertEqual(len(evidence.select([found], today=SOON)), 1)
        self.assertEqual(len(evidence.select([found], today=MUCH_LATER)), 0)

    def test_the_default_is_today_not_the_day_it_was_scored(self):
        """A caller that passes nothing gets the current answer. Evidence
        only gets worse with age, so re-deriving can drop a row and can
        never add one that was not already relevant enough."""
        ancient = a_fact(published_at="2019-01-01", today="2019-01-05")
        self.assertIn(ancient["quality"], evidence.USABLE)
        self.assertFalse(evidence.usable([ancient]))

    def test_personalization_stored_returns_re_aged_rows(self):
        rec = {"research": [a_fact()]}
        rows = personalization.stored(rec, today=MUCH_LATER)
        self.assertEqual(rows[0]["freshness_bucket"], evidence.BACKGROUND)
        self.assertEqual(rec["research"][0]["freshness_bucket"], evidence.HIGH)

    def test_the_quality_band_reads_re_aged_evidence(self):
        """`quality._selected` reads the record by evidence id rather than
        through `personalization.stored`, so it needs the same treatment -
        otherwise `evidence_recency` reports the recency of a decision
        rather than of a fact."""
        found = a_fact()
        rec = {"research": [found]}
        person = {"key": "a", "personalization": {
            "selected_evidence_ids": [found["evidence_id"]]}}
        fresh = quality._selected(rec, person, today=SOON)
        stale = quality._selected(rec, person, today=MUCH_LATER)
        self.assertGreater(quality.evidence_recency(fresh),
                           quality.evidence_recency(stale))


class ADraftIsHeldWhenItsReasonToExistAgesOut(CampaignTest):
    """The end of the chain, and the point of the exercise.

    Approval is a fingerprint of the text. The text does not change when
    the fact behind it does, so an approved draft stays approved - which is
    exactly why nothing else in the system catches this.
    """

    def ready(self, published_at=FOUND, ids=None, research=None):
        recs = self.seed_records()
        rec = recs[0]
        rec["contacts"] = [contact("acme-champ", "Champ", "champ@acme.test")]
        found = a_fact(published_at=published_at, record=rec["id"])
        rec["research"] = [found] if research is None else research
        rec["contacts"][0]["personalization"] = {
            "selected_evidence_ids":
                [found["evidence_id"]] if ids is None else ids}
        self.draft_everything(recs)
        self.approve_drafts(recs)
        store.save(recs)
        return rec, store.load()

    def decide(self, rec, recs, **kw):
        return E.decide(rec, rec["contacts"][0], "day1", recs=recs,
                        config=self.config, **kw)

    def test_a_draft_on_fresh_evidence_is_eligible(self):
        rec, recs = self.ready()
        decision = self.decide(rec, recs)
        self.assertTrue(decision.eligible, decision["reasons"])

    def test_the_same_draft_is_held_once_the_evidence_ages_out(self):
        rec, recs = self.ready(published_at="2019-01-01")
        decision = self.decide(rec, recs)
        self.assertEqual(decision["verdict"], E.HELD, decision["reasons"])
        self.assertIn(E.HELD_EVIDENCE_AGED_OUT, decision["reasons"])

    def test_the_approval_is_still_valid_which_is_why_nothing_caught_it(self):
        """Named because it is the whole mechanism. If the approval had
        gone stale, the existing gate would have held the step already and
        none of this would be needed."""
        from src import approval

        rec, recs = self.ready(published_at="2019-01-01")
        step = approval.stored(rec, "acme-champ", "day1")
        self.assertTrue(approval.is_approved(rec, "acme-champ", "day1", step))
        self.assertIn(E.HELD_EVIDENCE_AGED_OUT,
                      self.decide(rec, recs)["reasons"])

    def test_a_draft_that_leans_on_nothing_is_not_held(self):
        """A decision that selected no evidence fell back to a verified
        company fact and persona pain. Neither ages, and holding every
        fallback message in the estate would be the wrong reading."""
        rec, recs = self.ready(published_at="2019-01-01", ids=[])
        decision = self.decide(rec, recs)
        self.assertNotIn(E.HELD_EVIDENCE_AGED_OUT, decision["reasons"])

    def test_a_draft_citing_evidence_the_record_no_longer_has_is_held(self):
        """Not staleness - a message citing something we cannot produce -
        but the repair is the same one, so the verdict is the same."""
        rec, recs = self.ready(research=[])
        decision = self.decide(rec, recs)
        self.assertEqual(decision["verdict"], E.HELD, decision["reasons"])
        self.assertIn(E.HELD_EVIDENCE_AGED_OUT, decision["reasons"])

    def test_the_reason_tells_an_operator_to_regenerate(self):
        """Not to edit the sentence. A message built around a fact is not
        repaired by deleting the clause that carries it."""
        sentence = E.explain(E.HELD_EVIDENCE_AGED_OUT)
        self.assertIn("regenerate", sentence.lower())
        self.assertNotEqual(sentence, E.HELD_EVIDENCE_AGED_OUT)

    def test_it_is_held_and_never_blocked(self):
        """Held is a queue to work through. This one is fixable by
        regenerating, so it must not be recorded as a decision."""
        rec, recs = self.ready(published_at="2019-01-01")
        self.assertNotEqual(self.decide(rec, recs)["verdict"], E.BLOCKED)


if __name__ == "__main__":
    unittest.main()
