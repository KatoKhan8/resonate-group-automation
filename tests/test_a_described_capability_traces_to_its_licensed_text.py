#!/usr/bin/env python3
"""Naming a licensed capability was licensed. Describing it was not.

MEASURED 2026-09-30, on live copy:

    "Report Intelligence in Productive surfaces margin and budget patterns
     AS THEY HAPPEN, FLAGGING trends you might want to act on early. It
     HIGHLIGHTS when something could be impacting margin RIGHT IN THE
     MOMENT."

Its licensed source, `offer.ai_capabilities['Report Intelligence'].page_text`
in `config/clients/productive-offers.yaml`, says only:

    "Ask anything about your business data. Productive understands it and
     delivers the insights you're looking for already interpreted, in plain
     language."

A PULL-based question-answering feature described as PROACTIVE REAL-TIME
MONITORING. No gate caught it. `copylint.licensed_names` exempts the
capability NAME from `untraceable_company_claim`, and nothing traced the
DESCRIPTION back to `page_text` - `_claim_supported` is wired only to case
studies.

THE MECHANISM IS COVERAGE BY THE LICENSED TEXT, WHICH IS WHY IT IS NOT A
BLACKLIST. Nothing enumerates the wrong words. The support set is derived
from the capability's own page text, so the overclaim AND a synonym of it
are refused for the same reason: neither "surfaces"/"flagging" nor
"spots"/"alerting" is anywhere in the licensed text. That is `test_d`.

THE SECOND HALF: `claims.is_claim()` returned False for all nineteen
sentences of the same five-email sequence, including the only hard factual
assertion in it. `TheOfficesSentenceIsAClaim` pins what that was and what it
now does.
"""
import unittest

from src import claims, copylint, offers

OVERCLAIM = (
    "Report Intelligence in Productive surfaces margin and budget patterns "
    "as they happen, flagging trends you might want to act on early. It "
    "highlights when something could be impacting margin right in the "
    "moment."
)

#: The phrase that has to appear in a refusal for the refusal to be useful:
#: it is the licensed text, and it is what the rewrite has to be built from.
LICENSED_PHRASE = "Ask anything about your business data"

OPENER = ("Your site describes AZoNetwork as running email marketing, "
          "content and webinar services across its network.")

PACK_FACTS = [{"snippet": "AZoNetwork runs email marketing, content and "
                          "webinar services across its network of science "
                          "sites."}]


def _licensed():
    """The REAL licensed text, read from the operator-approved offer library.

    Not a fixture. A fixture here would be a page text somebody invented to
    match the assertion, which is the failure mode this whole module is
    about.
    """
    offer = offers.load()["OFFER-A-ECONOMIC-BUYER"]
    caps = offer.get("ai_capabilities") or {}
    return {str(n): (v or {}).get("page_text") for n, v in caps.items()}


def _pack(caps=None, names=None):
    caps = _licensed() if caps is None else caps
    pack = {"facts": list(PACK_FACTS)}
    pack["licensed_names"] = tuple(caps if names is None else names)
    if caps is not None:
        pack["licensed_capabilities"] = dict(caps)
    return pack


def _violations(text, **kw):
    return copylint.capability_description_violations(text, _pack(**kw))


def _batch_refused(text, **kw):
    """End to end through `check_batch`, which is what production calls."""
    pack = _pack(**kw)
    lead = {"id": "ck", "ps": {}, "linkedin": {}, "pack": pack,
            "steps": [{"subject": "s1", "body": OPENER + " " + text}]
            + [{"subject": "s%d" % i,
                "body": "A neutral filler sentence for step %d." % i}
               for i in range(2, 6)]}
    report = copylint.check_batch([lead])
    return "ck" in (report["offenders"]
                    .get("capability_description_unsupported") or ())


class TheLicensedTextIsReal(unittest.TestCase):
    """If this goes red every assertion below is about invented data."""

    def test_the_offer_library_carries_the_page_text(self):
        caps = _licensed()
        self.assertIn("Report Intelligence", caps)
        self.assertIn(LICENSED_PHRASE, caps["Report Intelligence"])

    def test_the_licensed_text_says_nothing_about_real_time_flagging(self):
        low = caps_low = _licensed()["Report Intelligence"].lower()
        for word in ("surface", "flag", "highlight", "as they happen",
                     "real-time", "alert", "monitor", "trend"):
            self.assertNotIn(word, caps_low, low)


class A_TheOverclaimIsRefused(unittest.TestCase):
    """(a) NEGATIVE CONTROL - the measured sentence, verbatim."""

    def test_it_is_refused(self):
        self.assertTrue(_violations(OVERCLAIM),
                        "the measured overclaim still passes")

    def test_the_refusal_names_the_capability_and_the_licensed_text(self):
        messages = " ".join(m for _r, m in _violations(OVERCLAIM))
        self.assertIn("Report Intelligence", messages)
        self.assertIn(LICENSED_PHRASE, messages,
                      "the refusal does not show what the copy MAY say")

    def test_it_is_refused_through_check_batch(self):
        """A rule nothing calls is not a gate."""
        self.assertTrue(_batch_refused(OVERCLAIM))

    def test_the_second_sentence_is_attributed_too(self):
        """'It highlights ...' carries the claim and not the name.

        Without pronoun carry-over the overclaim is evaded by putting the
        name in one sentence and the claim in the next.
        """
        self.assertTrue(_violations(
            "We built Report Intelligence. It flags margin trends the "
            "instant they appear."))


class B_AFaithfulDescriptionPasses(unittest.TestCase):
    """(b) POSITIVE CONTROL.

    Without this, a rule that refused every capability mention would pass
    every other test in this file.
    """

    def test_the_faithful_description_passes(self):
        self.assertEqual([], _violations(
            "Report Intelligence is how you ask Productive questions about "
            "your business data and get an interpreted answer."))

    def test_it_passes_through_check_batch(self):
        self.assertFalse(_batch_refused(
            "Report Intelligence is how you ask Productive questions about "
            "your business data and get an interpreted answer."))

    def test_the_other_capability_is_not_collateral(self):
        """Project Summary, described in its own licensed terms."""
        self.assertEqual([], _violations(
            "Project Summary gives an executive summary or a quick recap so "
            "your team can align and move fast."))

    def test_the_rule_is_not_refusing_everything(self):
        """THE CONTROL ON THE CONTROL. A rule that fires on nothing would
        also pass the two above; these must be refused."""
        self.assertTrue(_violations(
            "Project Summary predicts which projects will slip next "
            "quarter."))


class C_MerelyNamingItStillPasses(unittest.TestCase):
    """(c) Naming was always allowed - Offer A's rung 4 IS the name.

    `licensed_names` exists because the lint refused the approved ladder.
    Nothing here may undo that.
    """

    NAMED = (
        "Worth thirty minutes to walk you through Report Intelligence.",
        "Productive includes Report Intelligence and Project Summary.",
        "Report Intelligence is available.",
        "Happy to show you Report Intelligence on a call if it is useful.",
        "I can send over what Report Intelligence looks like.",
    )

    def test_a_named_capability_is_not_a_description(self):
        for text in self.NAMED:
            with self.subTest(text=text):
                self.assertEqual([], _violations(text))
                self.assertFalse(_batch_refused(text))

    def test_the_name_exemption_is_untouched(self):
        """The rule this task must not weaken: the NAME is still not an
        untraceable specific about the prospect."""
        pack = _pack()
        self.assertEqual(
            [], copylint.untraceable(
                "Report Intelligence answers a question about your own "
                "data.", pack))


class D_ASynonymEvasionIsStillRefused(unittest.TestCase):
    """(d) THE PROOF IT IS NOT A BLACKLIST.

    Every content word of the original overclaim is replaced. A list of bad
    words would let these through; coverage by the licensed text does not,
    because a synonym of an unlicensed claim is another unlicensed claim.
    """

    EVASIONS = (
        "Report Intelligence spots margin and budget signals the moment "
        "they emerge and alerts you to shifts worth acting on early.",
        "Report Intelligence watches margin and budget movements live and "
        "warns you about swings you may wish to address sooner.",
        "Report Intelligence continuously monitors profitability and raises "
        "an early signal whenever a project starts drifting.",
    )

    def test_each_evasion_is_refused(self):
        for text in self.EVASIONS:
            with self.subTest(text=text):
                self.assertTrue(_violations(text))
                self.assertTrue(_batch_refused(text))

    def test_no_evasion_word_is_named_in_the_module(self):
        """The refusal is not driven by any word this module knows.

        Asserted on BEHAVIOUR, not source text: strip the evasion's
        vocabulary out of the copy entirely and rebuild the same claim from
        words nobody chose in advance - it is still refused, because the
        licensed text still does not contain them.
        """
        self.assertTrue(_violations(
            "Report Intelligence tells you the instant a job starts eating "
            "its own contingency."))


class TheFourBypasses(unittest.TestCase):
    """REPORTED 2026-10-01 by review, reproduced verbatim against this code.

    All four PASSED the first version of the gate. None of them is arguable:
    three are structural escapes from attribution, and the fourth is the
    coverage test itself averaging an unlicensed claim down against licensed
    vocabulary.

    The strings are the reviewer's own, unedited, so a regression is caught
    by the exact probe that found it.
    """

    def test_1_a_fronted_instrument_phrase_is_a_description(self):
        """`_capability_subject` wanted the name at the START of the
        sentence, so any fronted phrase dropped to the mention branch -
        which sets the referent and `continue`s with NO coverage check."""
        self.assertTrue(_violations(
            "With Report Intelligence, you can watch margin and budget "
            "patterns as they happen."))

    def test_2_a_pronoun_after_an_adverbial_is_still_the_subject(self):
        """The continuation test was anchored at `^`, so a pronoun with any
        word in front of it escaped."""
        self.assertTrue(_violations(
            "Report Intelligence is included. Right now, it flags budget "
            "overruns as they happen."))

    def test_3_a_fronted_phrase_also_walked_past_the_fail_closed_path(self):
        """The same escape as 1, and worse: it never reached the
        no-page_text refusal that exists for exactly this case."""
        v = _violations(
            "With SmartCap you can predict churn in real time.",
            caps={"SmartCap": ""})
        self.assertTrue(v)
        self.assertIn("no licensed page text", " ".join(m for _r, m in v))
        self.assertIn("SmartCap", " ".join(m for _r, m in v))

    def test_4_a_conjoined_claim_may_not_average_itself_down(self):
        """THE ONE THAT MATTERS MOST. The sentence WAS inspected;
        understands/business/data are licensed, predicts/churn are not, and
        3 of 5 cleared the bar. An unlicensed verb rode in on licensed
        nouns."""
        v = _violations(
            "Report Intelligence understands your business data and "
            "predicts churn.")
        self.assertTrue(v)
        self.assertIn("predict", " ".join(m for _r, m in v))

    def test_the_two_baselines_still_behave(self):
        """The reviewer's own controls. A fix that refused everything would
        pass all four tests above."""
        self.assertTrue(_violations(
            "Report Intelligence surfaces margin and budget patterns as "
            "they happen, flagging trends early."))
        self.assertEqual([], _violations(
            "You can ask Productive anything about your business data and "
            "get an interpreted answer."))

    def test_a_fronted_phrase_is_not_the_same_as_a_trailing_one(self):
        """POSITION is the discriminator, not the preposition. Both of
        these carry "through" plus the name; only the fronted one
        characterises the capability."""
        self.assertTrue(_violations(
            "Through Report Intelligence you can watch margin move in real "
            "time."))
        self.assertEqual([], _violations(
            "Worth thirty minutes to walk you through Report Intelligence."))

    def test_a_discourse_marker_is_not_a_reference_to_the_capability(self):
        """`that`/`this` were candidates for the continuation set and are
        deliberately out: this sentence refers to a call, not a feature, and
        refusing it would be the guard stopping honest copy."""
        self.assertEqual([], _violations(
            "Productive includes Report Intelligence. That said, we can "
            "walk you through it on a call."))

    def test_a_pronoun_buried_mid_sentence_is_not_the_subject(self):
        self.assertEqual([], _violations(
            "Productive includes Report Intelligence. Happy to send over a "
            "short overview of it whenever suits you."))

    def test_a_short_pronoun_sentence_is_a_mention_not_a_description(self):
        """THE CALIBRATION THE CONTINUATION FLOOR EXISTS FOR, pinned.

        A pronoun is weaker evidence of attribution than the name, so a
        continuation needs one more content word before it counts as
        characterising behaviour. "It is worth a look" carries two and
        asserts nothing; "It flags budget overruns as they happen" carries
        four and asserts plenty. Found by mutation: lowering the floor to
        the ordinary one went unnoticed by every other test here.

        "a call" and not "a look": `_stem` folds the page text's "looking"
        to "look", so a sentence ending "worth a look" is HALF covered and
        passes on coverage whatever the floor is - it would have pinned
        nothing. The probe has to be two content words the licensed text
        does not carry, or it is not a probe of the floor.
        """
        self.assertEqual([], _violations(
            "Productive includes Report Intelligence. It is worth a call."))
        self.assertTrue(_violations(
            "Productive includes Report Intelligence. It flags budget "
            "overruns as they happen."))

    def test_a_sentence_of_sub_floor_fragments_cannot_escape(self):
        """The per-span floor must not become its own hole: split finely
        enough, every span falls under it. The whole-sentence unit is what
        closes that."""
        self.assertTrue(_violations(
            "Report Intelligence watches, predicts, alerts."))


class FailsClosed(unittest.TestCase):
    """No stored page text is a REFUSAL, never a pass.

    The same contract `case_study_unsupported` holds: an empty store refuses
    every claim. This was the defect the case-study rework fixed, and it is
    not reintroduced here by a different door.
    """

    def test_a_described_capability_with_no_page_text_is_refused(self):
        v = _violations(OVERCLAIM, caps={"Report Intelligence": None})
        self.assertTrue(v)
        self.assertIn("no licensed page text", " ".join(m for _r, m in v))

    def test_an_empty_page_text_is_refused(self):
        self.assertTrue(_violations(OVERCLAIM,
                                    caps={"Report Intelligence": ""}))

    def test_a_pack_carrying_only_names_refuses_a_description(self):
        """A pack built before this rule existed carries `licensed_names`
        and no text. That refuses, it does not quietly pass."""
        pack = {"facts": list(PACK_FACTS),
                "licensed_names": ("Report Intelligence",)}
        self.assertTrue(
            copylint.capability_description_violations(OVERCLAIM, pack))

    def test_naming_it_is_still_allowed_with_no_page_text(self):
        """Fail-closed on the DESCRIPTION, not on the mention."""
        self.assertEqual([], _violations(
            "Productive includes Report Intelligence.",
            caps={"Report Intelligence": None}))

    def test_a_pack_with_no_capabilities_is_not_this_rule_s_business(self):
        self.assertEqual(
            [], copylint.capability_description_violations(
                OVERCLAIM, {"facts": list(PACK_FACTS)}))


class TheProductionPackCarriesTheText(unittest.TestCase):
    """A gate is only wired if the caller supplies what it reads.

    `bisonfactory` and `generate_campaign` both build the lint pack. Both set
    `licensed_names`; until now neither set the text, so the rule would have
    refused every description as unverifiable.
    """

    def test_the_rule_is_in_the_rules_table(self):
        self.assertIn("capability_description_unsupported",
                      dict(copylint.RULES))

    def test_check_batch_reports_the_rule(self):
        report = copylint.check_batch([])
        self.assertIn("capability_description_unsupported", report["counts"])

    def test_licensed_capabilities_reads_the_pack(self):
        caps = copylint.licensed_capabilities(_pack())
        self.assertIn(LICENSED_PHRASE, caps["Report Intelligence"])

    def test_bisonfactory_builds_a_pack_carrying_the_licensed_text(self):
        """The push path. Asserted on the pack it BUILDS, not on its source.

        Without this the rule is wired and starved: every description on
        the push path would refuse as unverifiable, which is safe and
        useless.
        """
        from src import bisonfactory
        plan = {"client": "productive",
                "leads": [{"record_id": "r1", "contact_key": "c1",
                           "persona": "economic_buyer",
                           "copy": [{"body": "x"}]}]}
        _leads, packs = bisonfactory._copylint_batch(plan, [{"id": "r1"}])
        caps = list(packs.values())[0].get("licensed_capabilities") or {}
        self.assertIn(LICENSED_PHRASE, caps.get("Report Intelligence") or "")


class TheMeasuredCostOfFailingClosed(unittest.TestCase):
    """WHAT THIS CHANGE TAKES AWAY, pinned so nobody discovers it live.

    "Report Intelligence answers a question about your own data" is a
    FAITHFUL paraphrase of the licensed text and is now REFUSED, because
    neither "answers" nor "question" appears in that text and the gate has
    no way to know that asking and answering are converses. Fail-closed
    means refusing what cannot be verified.

    The rewrite is not a widening of the rule, it is the copy: say it in the
    licensed vocabulary. `B_AFaithfulDescriptionPasses` is that sentence.
    """

    def test_the_old_rung_four_wording_is_now_refused(self):
        self.assertTrue(_violations(
            "Report Intelligence answers a question about your own data."))

    def test_and_the_licensed_wording_of_the_same_rung_passes(self):
        self.assertEqual([], _violations(
            "Report Intelligence lets you ask anything about your business "
            "data and get the insights back already interpreted, in plain "
            "language."))


class TheOfficesSentenceIsAClaim(unittest.TestCase):
    """(e) STEP 2. `is_claim` returned False, so nothing was ever checked.

    MEASURED 2026-09-30: False for all nineteen sentences of a five-email
    sequence, including the only hard factual assertion about the prospect.

    THE CAUSE IS A DEFECT, NOT INTENDED SCOPE. Every `EVENT_WORDS` entry is
    tested with `w in low`, a SUBSTRING test, and the list carried the
    SINGULAR "office in". "offices in" does not contain "office in" - the
    `s` sits between them - and the sentence carries no figure, no month and
    no second-person assertion, so the guard returned False before anything
    else ran. Opening an office is exactly the class of checkable event this
    list exists for; one letter decided whether it was caught.
    """

    BARE = {"id": "r1", "company": "OBE", "domain": "obe.com",
            "company_facts": {}, "research": [], "events": []}
    SENTENCE = ("OBE has offices in Los Angeles, New York, San Francisco, "
                "and London.")

    def test_it_is_now_recognised_as_a_claim(self):
        self.assertTrue(claims.is_claim(self.SENTENCE))

    def test_and_is_refused_when_nothing_stored_supports_it(self):
        problems = claims.check(self.SENTENCE, self.BARE)
        self.assertTrue(problems, "verify reported clean having inspected "
                                  "nothing")
        self.assertIn("offices in", problems[0]["why"])

    def test_and_passes_when_the_record_actually_holds_the_offices(self):
        """THE CONTROL. A rule that refused it either way would be a
        vocabulary filter, not a claim check."""
        rec = dict(self.BARE, company_facts={
            "offices": ["Los Angeles", "New York", "San Francisco",
                        "London"]})
        self.assertEqual([], claims.check(self.SENTENCE, rec))

    def test_the_singular_was_never_broken_and_still_is_not(self):
        self.assertTrue(claims.is_claim("OBE has an office in London."))

    def test_verify_now_inspects_the_sentence(self):
        self.assertTrue(claims.verify(
            {"subject": "OBE", "body": self.SENTENCE}, self.BARE))

    def test_a_long_supported_office_sentence_is_not_refused(self):
        """THE SECOND DEFECT, found by fixing the first.

        `support` is a token join of structured facts, so the BIGRAM
        "offices in" can never appear in it however completely the record
        knows the answer, and every office claim fell through to
        `_is_paraphrase` - a ratio over the whole sentence, which fails on
        any long one. The moment the plural started matching, three TRUE
        stored steps in `tests/fixtures/phase7.jsonl` were refused.

        This is that sentence's shape, against a record that holds the
        offices. A gate that refuses it is a gate somebody switches off.
        """
        rec = dict(self.BARE, company_facts={
            "offices": ["Zagreb HR", "Varazdin HR", "Rijeka HR",
                        "Beograd RS", "Ljubljana SI"]})
        self.assertEqual([], claims.check(
            "You run finance across five offices in three countries, which "
            "is the point where month end stops being an afternoon and "
            "starts being a week.", rec))

    def test_the_glue_preposition_is_all_that_is_dropped(self):
        """The event noun itself must still be in support.

        Only the trailing preposition of a multi-word event phrase is
        dropped. A record that knows nothing about offices still refuses
        both the plural and the singular.
        """
        self.assertTrue(claims.check("OBE has an office in London.",
                                     self.BARE))
        self.assertFalse(claims._event_supported("offices in", "obe obe.com"))
        self.assertTrue(claims._event_supported(
            "offices in", "offices zagreb hr rijeka hr"))

    def test_a_single_word_event_gets_no_preposition_relief(self):
        """"raised", "acquired", "hiring" carry no glue word and must not
        be softened by this at all."""
        for word in ("raised", "acquired", "hiring", "series b"):
            with self.subTest(word=word):
                self.assertFalse(
                    claims._event_supported(word, "obe advertising zagreb"))

    def test_ordinary_copy_is_not_newly_refused(self):
        """The fix is one plural. It is not a widened classifier."""
        for text in ("We help teams like yours see margin sooner.",
                     "How do you track project margin today?",
                     "I will keep this short.",
                     "Most operations leads we speak to lose a day a month."):
            with self.subTest(text=text):
                self.assertEqual([], claims.check(text, self.BARE))


if __name__ == "__main__":
    unittest.main()
