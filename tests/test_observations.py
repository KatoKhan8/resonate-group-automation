"""What a message may say it noticed, and everything it may not.

The failure this guards against is a generator that mentions what the
system merely knows. A signal moves priority; it is not a citation. A fact
without a link cannot be defended when the recipient asks where we saw it.
A fact that has aged out is still true and is no longer news. Each of those
is a real thing in state, each is refused, and each refusal says which one
it was - because "the system did not mention it" and "the system decided
not to mention it" look identical from outside.
"""
import unittest

from src import evidence, observations, signals
from tests.campaignbase import CampaignTest

TODAY = "2026-08-31"
RECENT = "2026-08-01"
OLD = "2026-01-01"
ANCIENT = "2019-01-01"

FACT = ("Acme opened a Vienna delivery office and is hiring four "
        "implementation managers to staff it.")

ON = {"observations": {"company_event": "on", "company_attribute": "on",
                       "person_role": "on", "person_content": "on"}}


def a_fact(published_at=RECENT, subject=evidence.COMPANY, contact_key=None,
           url="https://acme.test/news", fact=FACT, authored=False,
           today=RECENT, angle_words=("utilisation", "capacity", "delivery",
                                      "resourcing")):
    # The angle words are passed because relevance is scored against them.
    # Without them an undated fact scores below the usable line on its own,
    # and a test meaning to isolate the *date* rule would be measuring
    # relevance instead.
    return evidence.make(fact, url, "news", "apify", "a1",
                         contact_key=contact_key, published_at=published_at,
                         subject=subject, authored_by_person=authored,
                         persona="champion", angle_words=list(angle_words),
                         today=today)


def a_record(research=(), **kw):
    rec = {"id": "a1", "company": "Acme", "domain": "acme.test",
           "client": "productive", "research": list(research),
           "contacts": [{"key": "a", "name": "A Person", "selected": True}]}
    rec.update(kw)
    return rec


class Observations(CampaignTest):

    def resolve(self, kind, rec, contact="a", config=ON, today=TODAY):
        return observations.resolve(kind, rec, contact, config, today)


class ASignalIsNeverASentence(Observations):
    """Signals move priority, timing and which angle a campaign leads with.
    None of that requires stating them, and none of them can be stated."""

    def note(self, rec, kind=signals.FUNDING, observed_at=RECENT):
        return signals.record(signals.signal(
            "productive", kind, record_id=rec["id"],
            evidence="A EUR 12m Series B announced on their newsroom.",
            source=signals.MANUAL, observed_at=observed_at,
            created_by="op@productive.test"))

    def test_a_signal_licenses_nothing(self):
        rec = a_record()
        self.note(rec)
        for kind in observations.TYPES:
            self.assertFalse(self.resolve(kind, rec), kind)

    def test_the_refusal_is_visible_rather_than_silent(self):
        """A system that silently declines to mention something looks
        exactly like a system that never knew it."""
        rec = a_record()
        self.note(rec)
        quiet = observations.withheld(rec, "productive", ON, TODAY)
        kinds = [row["kind"] for row in quiet]
        self.assertIn("signal", kinds)
        for row in quiet:
            self.assertTrue(row["why"])

    def test_the_reason_names_what_a_signal_is_missing(self):
        rec = a_record()
        self.note(rec)
        row = next(r for r in observations.withheld(rec, "productive", ON,
                                                    TODAY)
                   if r["kind"] == "signal")
        self.assertIn("source", row["why"])

    def test_a_signal_does_not_become_evidence_by_being_recent(self):
        rec = a_record()
        self.note(rec, observed_at=TODAY)
        self.assertFalse(self.resolve(observations.COMPANY_EVENT, rec))

    def test_a_signal_cannot_support_a_sentence_in_the_draft_checker_either(self):
        """The invariant this whole module rests on. `claims.support_text`
        is the blob a finished draft is checked against, and a signal must
        not be in it - otherwise a sentence about hiring would pass the end
        gate even though nothing here would license it."""
        from src import claims

        rec = a_record()
        self.note(rec, kind=signals.HIRING_SURGE)
        support = claims.support_text(rec)
        self.assertNotIn("series b", support)
        self.assertNotIn("hiring_surge", support)


class AFactWeCannotPointAtIsNotUsable(Observations):

    def test_evidence_with_no_source_url_is_refused(self):
        rec = a_record([a_fact(url="")])
        found = self.resolve(observations.COMPANY_EVENT, rec)
        self.assertFalse(found)
        self.assertIn("source", found["why"])

    def test_the_refusal_is_different_from_having_nothing(self):
        """Different problems with different fixes: one needs research, the
        other needs the link recording."""
        nothing = self.resolve(observations.COMPANY_EVENT, a_record())
        unlinked = self.resolve(observations.COMPANY_EVENT,
                                a_record([a_fact(url="")]))
        self.assertNotEqual(nothing["why"], unlinked["why"])
        self.assertEqual(unlinked["known"], 1)

    def test_it_appears_under_what_is_known_and_unspoken(self):
        rec = a_record([a_fact(url="")])
        quiet = observations.withheld(rec, "productive", ON, TODAY)
        self.assertTrue([r for r in quiet if r["kind"] == "evidence"])


class AgeingIsRespectedAtLicenceTime(Observations):

    def test_a_fact_that_aged_out_licenses_nothing(self):
        rec = a_record([a_fact(published_at=ANCIENT, today=ANCIENT)])
        found = self.resolve(observations.COMPANY_EVENT, rec)
        self.assertFalse(found)
        self.assertTrue(found["aged_out"])

    def test_the_reason_says_it_aged_rather_than_that_it_was_weak(self):
        """Two different problems. One is fixed by re-researching the
        company; the other never will be."""
        rec = a_record([a_fact(published_at=ANCIENT, today=ANCIENT)])
        self.assertIn("aged out",
                      self.resolve(observations.COMPANY_EVENT, rec)["why"])

    def test_the_stored_verdict_is_not_trusted(self):
        """The row says `strong` because that was true when it was found.
        The licence is granted today."""
        row = a_fact(published_at=ANCIENT, today=ANCIENT)
        self.assertIn(row["quality"], evidence.USABLE)
        self.assertFalse(self.resolve(observations.COMPANY_EVENT,
                                      a_record([row])))


class RecentIsItselfAClaim(Observations):

    def test_a_fresh_fact_may_be_called_current(self):
        found = self.resolve(observations.COMPANY_EVENT,
                             a_record([a_fact(published_at=RECENT)]))
        self.assertTrue(found)
        self.assertTrue(found["may_call_it_now"])
        self.assertIsNone(found["why_not_now"])

    def test_an_older_fact_may_be_stated_but_not_as_news(self):
        """The office is still there. It is not news."""
        found = self.resolve(observations.COMPANY_EVENT,
                             a_record([a_fact(published_at=OLD, today=OLD)]))
        self.assertTrue(found)
        self.assertFalse(found["may_call_it_now"])
        self.assertIn("not recent enough", found["why_not_now"])

    def test_an_undated_fact_never_earns_it(self):
        """A wrong "last month" is a small lie they can check against their
        own calendar."""
        found = self.resolve(observations.COMPANY_ATTRIBUTE,
                             a_record([a_fact(published_at=None)]))
        self.assertTrue(found)
        self.assertFalse(found["may_call_it_now"])
        self.assertIn("no date", found["why_not_now"])

    def test_a_dated_type_refuses_an_undated_fact_outright(self):
        """Saying they *did* something asserts a when."""
        found = self.resolve(observations.COMPANY_EVENT,
                             a_record([a_fact(published_at=None)]))
        self.assertFalse(found)


class TheSubjectMustMatch(Observations):

    def test_a_company_fact_does_not_license_a_person_observation(self):
        rec = a_record([a_fact(subject=evidence.COMPANY)])
        self.assertFalse(self.resolve(observations.PERSON_ROLE, rec))

    def test_a_person_fact_does_not_license_a_company_observation(self):
        rec = a_record([a_fact(subject=evidence.PERSON, contact_key="a")])
        self.assertFalse(self.resolve(observations.COMPANY_ATTRIBUTE, rec))

    def test_one_persons_evidence_does_not_license_a_claim_about_another(self):
        rec = a_record([a_fact(subject=evidence.PERSON, contact_key="a")])
        self.assertTrue(self.resolve(observations.PERSON_ROLE, rec,
                                     contact="a"))
        self.assertFalse(self.resolve(observations.PERSON_ROLE, rec,
                                      contact="b"))

    def test_quoting_them_needs_something_they_wrote(self):
        rec = a_record([a_fact(subject=evidence.PERSON, contact_key="a",
                               authored=False)])
        self.assertFalse(self.resolve(observations.PERSON_CONTENT, rec))

        rec = a_record([a_fact(subject=evidence.PERSON, contact_key="a",
                               authored=True)])
        self.assertTrue(self.resolve(observations.PERSON_CONTENT, rec))


class PermissionIsNotObligation(Observations):

    def test_a_switched_off_type_is_refused_even_with_evidence(self):
        rec = a_record([a_fact()])
        found = self.resolve(observations.COMPANY_EVENT, rec,
                             config={"observations": {"company_event": "off"}})
        self.assertFalse(found)
        self.assertIn("switched off", found["why"])

    def test_that_refusal_is_distinguishable_from_having_no_evidence(self):
        """Different questions with different answers: one is a setting,
        the other is research that has not happened."""
        off = self.resolve(observations.COMPANY_EVENT, a_record([a_fact()]),
                           config={"observations": {"company_event": "off"}})
        empty = self.resolve(observations.COMPANY_EVENT, a_record())
        self.assertNotEqual(off["why"], empty["why"])

    def test_person_level_types_are_off_by_default(self):
        """Conservative, and widening it is a deliberate campaign setting."""
        for kind in (observations.PERSON_ROLE, observations.PERSON_CONTENT):
            on, _ = observations.allowed_by_policy(kind, {})
            self.assertFalse(on, kind)

    def test_every_type_has_a_switch_and_a_sentence(self):
        for kind in observations.TYPES:
            self.assertIn(kind, observations.POLICY_KEYS)
            label, doing, minimum = observations.OBSERVATIONS[kind]
            self.assertTrue(label and doing and minimum)


class ARefusalAlwaysCarriesItsReason(Observations):

    def test_no_decision_is_a_bare_boolean(self):
        rec = a_record([a_fact()])
        for kind in observations.TYPES:
            found = self.resolve(kind, rec)
            self.assertTrue(found["why"], kind)

    def test_a_refused_decision_is_falsey(self):
        self.assertFalse(bool(self.resolve(observations.COMPANY_EVENT,
                                           a_record())))

    def test_available_returns_the_refused_ones_too(self):
        """"Why can this message not mention their funding round" is a
        question an operator asks."""
        rows = observations.available(a_record(), "a", ON, TODAY)
        self.assertEqual(len(rows), len(observations.TYPES))
        self.assertTrue(all(not r["allowed"] for r in rows))
        self.assertTrue(all(r["why"] for r in rows))

    def test_the_summary_says_knowing_and_saying_are_different(self):
        found = observations.summarise(a_record(), "a", ON, TODAY,
                                       "productive")
        self.assertIn("different", found["note"])
        self.assertIn("withheld", found["counts"])


class ItDecidesNothingAndAsksNobody(unittest.TestCase):

    def test_it_writes_no_state_and_calls_no_provider(self):
        import inspect

        source = inspect.getsource(observations)
        for banned in ("store.save", "store.log", "events.record",
                       "providers.request", "urlopen", "requests.",
                       "from . import llm", "anthropic", "openai"):
            self.assertNotIn(banned, source, banned)

    def test_it_does_not_read_a_stored_quality_directly(self):
        """It goes through `personalization.stored`, which re-ages. Reading
        `rec["research"]` here would grant a licence on a verdict written
        the day the fact was found."""
        import inspect

        source = inspect.getsource(observations)
        self.assertNotIn('rec.get("research")', source)
        self.assertNotIn('rec["research"]', source)


if __name__ == "__main__":
    unittest.main()
