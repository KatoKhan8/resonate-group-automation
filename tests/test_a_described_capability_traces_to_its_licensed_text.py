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


#: The offer's own containment words, read from the operator-approved record.
#: NARROW: `mechanism_text` and `mechanism_secondary_text` only - never the
#: selling fields, whose vocabulary is "margin", "visible", "running".
def _containment():
    offer = offers.load()["OFFER-A-ECONOMIC-BUYER"]
    return [offer.get("mechanism_text"),
            offer.get("mechanism_secondary_text")]


def _pack(caps=None, names=None, containment=True):
    caps = _licensed() if caps is None else caps
    pack = {"facts": list(PACK_FACTS)}
    pack["licensed_names"] = tuple(caps if names is None else names)
    if caps is not None:
        pack["licensed_capabilities"] = dict(caps)
    if containment:
        pack["offer_containment_text"] = _containment()
    return pack


def _violations(text, **kw):
    return copylint.capability_description_violations(text, _pack(**kw))


def _behaviour_only(text, **kw):
    """The gate with the containment authority absent, so only page_text can
    license anything. Every pre-(b) assertion holds here unchanged."""
    kw.setdefault("containment", False)
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

    THE WORDING CHANGED ON 2026-10-01 AND THE OLD ONE IS KEPT, in
    `TheMeasuredCostOfEveryWordLicensed`, as the cost rather than deleted.
    Retiring the coverage ratio for bypass 10 means every content word of a
    clause has to be in the licensed text, and "questions" / "answer" are
    not - the page text says "Ask anything" and "delivers the insights".
    A faithful description still passes; it has to be faithful in the
    licensed text's own words now.
    """

    FAITHFUL = ("Report Intelligence delivers the insights you are looking "
                "for already interpreted, in plain language.")

    def test_the_faithful_description_passes(self):
        self.assertEqual([], _violations(self.FAITHFUL))

    def test_it_passes_through_check_batch(self):
        self.assertFalse(_batch_refused(self.FAITHFUL))

    def test_the_licensed_verb_is_not_collateral(self):
        """REVIEW'S OWN CONTROL for bypass 10, named explicitly: if
        licensing the verb refuses this, the approach is wrong.

        "delivers" is the page text's own verb. It passes, which is what
        separates "the verb must be licensed" from "no verb may be used".
        """
        self.assertEqual([], _violations(
            "Report Intelligence delivers the insights you are looking "
            "for."))

    def test_the_other_capability_is_not_collateral(self):
        """Project Summary, described in its own licensed terms.

        "get", not "gives": the page text says "Get an executive summary".
        One word, and it is the whole difference - see
        `TheMeasuredCostOfEveryWordLicensed`.
        """
        self.assertEqual([], _violations(
            "Project Summary: get an executive summary or a quick recap so "
            "your team can align and move fast."))

    def test_the_rule_is_not_refusing_everything(self):
        """THE CONTROL ON THE CONTROL. A rule that fires on nothing would
        also pass the two above; these must be refused."""
        self.assertTrue(_violations(
            "Project Summary predicts which projects will slip next "
            "quarter."))


class C_MerelyNamingItStillPasses(unittest.TestCase):
    """(c) WHAT IS LEFT OF "naming was always allowed" AFTER THE INVERSION.

    THIS CLASS CHANGED MEANING ON 2026-10-01 AND THE CHANGE IS A POLICY ONE.
    Review asked for the gate's DEFAULT to be inverted: in scope is any
    sentence naming a capability or referring back to one, and an in-scope
    sentence that asserts a predicate must trace or be REFUSED. Under that
    default there is no position test left to decide "object, therefore a
    mention", because the position test WAS the attack surface - seven
    bypasses, five of them reported and two found here in minutes.

    So FOUR of the five sentences that used to pass now refuse - three
    at the inversion and the fourth when the coverage ratio was retired for
    bypass 10. They are
    moved to `REFUSED_AS_MENTIONS` below rather than quietly dropped,
    with what each one costs. `TheMeasuredCostOnRealCopy` is the evidence
    that the cost is zero on the copy that actually exists.

    Offer A's rung 4 is "Report Intelligence as mechanism", and the rung
    still ships: a sentence that names the capability and says what it does
    IN ITS LICENSED WORDS passes - see `B_AFaithfulDescriptionPasses`.
    """

    NAMED = (
        "Report Intelligence is available.",
    )

    #: Mentions the gate refuses. Each asserts nothing false about the
    #: capability, so each is a genuine false positive - and none of them
    #: occurs anywhere in the 4,565 generated steps in the store.
    #:
    #: "Productive includes Report Intelligence and Project Summary" JOINED
    #: THIS LIST on 2026-10-01. It survived the inversion only because
    #: "Productive" happens to appear in Report Intelligence's page text, so
    #: it scraped 1 of 2 against the old 50% ratio - it passed by luck, not
    #: by rule. Retiring the ratio for bypass 10 takes that luck away:
    #: "includes" is a verb the page text does not carry, and under "the
    #: predicate must be licensed" refusing it is the rule working, not a
    #: fault in it. Only the sub-floor mention survives now.
    REFUSED_AS_MENTIONS = (
        "Worth thirty minutes to walk you through Report Intelligence.",
        "Happy to show you Report Intelligence on a call if it is useful.",
        "I can send over what Report Intelligence looks like.",
    )

    #: GIVEN BACK BY THE CONTAINMENT AUTHORITY, 2026-10-01. This is the only
    #: sentence in twelve rounds that went from refused to allowed, and it is
    #: the whole measured loosening of option (b). It is a claim about what
    #: the offer CONTAINS, which the offer file licenses structurally; it was
    #: refused only because the gate was judging it against a feature blurb.
    GIVEN_BACK_BY_THE_OFFER_AUTHORITY = (
        "Productive includes Report Intelligence and Project Summary.",
    )

    def test_a_named_capability_is_not_a_description(self):
        for text in self.NAMED:
            with self.subTest(text=text):
                self.assertEqual([], _violations(text))
                self.assertFalse(_batch_refused(text))

    def test_the_sender_action_mentions_are_now_refused(self):
        """THE COST OF THE INVERSION, PINNED SO IT CANNOT DRIFT QUIETLY.

        Each of these predicates something of the SENDER ("show you",
        "walk you through", "send over") with the capability as the object,
        and each is now refused because no position test survives to say so.
        Deciding object-versus-subject needs syntax; every closed-class
        approximation of it leaked, and the undecided cases now go to
        REFUSE because that is the direction asked for.

        If the operator wants these back, this test and
        `_CAPABILITY_MIN_CONTENT` are the two places to look, and the
        measured price of getting them back is the three live overclaims in
        `TheMeasuredCostOnRealCopy`.
        """
        for text in self.REFUSED_AS_MENTIONS:
            with self.subTest(text=text):
                self.assertTrue(_violations(text))

    def test_a_containment_mention_is_licensed_by_the_offer(self):
        """THE ONE SENTENCE OPTION (b) GAVE BACK.

        It passes on the containment authority, and ONLY on that: with the
        offer's containment text absent it refuses exactly as it did at
        a33adb8b.
        """
        for text in self.GIVEN_BACK_BY_THE_OFFER_AUTHORITY:
            with self.subTest(text=text):
                self.assertEqual([], _violations(text))
                self.assertTrue(_behaviour_only(text))

    def test_the_rung_the_ladder_requires_still_ships(self):
        """The thing `licensed_names` was built to protect.

        Naming the capability is not refused BECAUSE it is named - it is
        refused only when what the sentence says about it is not in the
        licensed text. Said in licensed words, rung 4 passes.
        """
        self.assertEqual([], _violations(
            "Report Intelligence lets you ask anything about your business "
            "data and get the insights back already interpreted."))

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

    def test_position_is_no_longer_consulted_at_all(self):
        """WAS: "position is the discriminator, not the preposition".

        It is now neither. Both of these carry "through" plus the name and
        both are refused, because the inversion asks only whether the
        sentence is IN SCOPE and whether what it says traces. The fronted
        case was bypass 1; the trailing case is the measured price of
        closing it without a position test. See
        `C_MerelyNamingItStillPasses`.
        """
        self.assertTrue(_violations(
            "Through Report Intelligence you can watch margin move in real "
            "time."))
        self.assertTrue(_violations(
            "Worth thirty minutes to walk you through Report Intelligence."))

    def test_a_discourse_marker_now_pulls_the_sentence_into_scope(self):
        """WAS: `that`/`this` deliberately kept out of the pronoun set.

        They are now in, because "Productive includes Report Intelligence,
        which predicts churn" was bypass 7 and a relative pronoun is the
        plainest way to predicate something of the noun beside it. The
        price is this sentence: "That said" is a discourse marker, not a
        reference to the capability, and it is now a false positive.

        Under the inverted default a false positive is the correct failure
        mode and an escape is not, so this is recorded as the price rather
        than fixed with another position rule.
        """
        self.assertTrue(_violations(
            "Productive includes Report Intelligence. That said, we can "
            "walk you through it on a call."))

    def test_a_buried_pronoun_now_counts_as_a_reference(self):
        """WAS: a pronoun buried mid-sentence is not the subject.

        "Any pronoun, any position, any clause" is the instruction, because
        a position budget is what bypasses 2 and 6 walked past one word at
        a time. There is no position left to move the pronoun to, and this
        sentence is what that costs.
        """
        self.assertTrue(_violations(
            "Productive includes Report Intelligence. Happy to send over a "
            "short overview of it whenever suits you."))

    def test_a_sentence_of_sub_floor_fragments_cannot_escape(self):
        """The per-span floor must not become its own hole: split finely
        enough, every span falls under it. The whole-sentence unit is what
        closes that."""
        self.assertTrue(_violations(
            "Report Intelligence watches, predicts, alerts."))


class TheFloorIsNotAnExit(unittest.TestCase):
    """BYPASS 5, reported 2026-10-01: short is not harmless, short is the
    attack.

    `floor = _CAPABILITY_MIN_CONTENT + (1 if continuation else 0)` was 3 for
    a continuation and ran BEFORE both the no-page_text branch and
    `_coverage_failure`, so a two-word claim was trimmed away unexamined.

    I WAS WRONG ABOUT THIS LAST ROUND AND THE PREVIOUS TEST IS DELETED, not
    adjusted. The bump's reasoning - a pronoun is weaker evidence of
    attribution than the name - is sound about WHOSE claim a sentence makes
    and says nothing about WHETHER it makes one. Using it for the second
    question is what shipped "It predicts churn".

    The strings are the reviewer's own, unedited.
    """

    def test_a_two_word_continuation_claim_is_refused(self):
        self.assertTrue(_violations(
            "Productive includes Report Intelligence. It predicts churn."))

    def test_a_two_word_continuation_claim_is_refused_in_any_wording(self):
        self.assertTrue(_violations(
            "Productive includes Report Intelligence. It flags overruns."))

    def test_the_floor_cannot_skip_the_no_page_text_refusal(self):
        """THE SECOND TIME that branch was bypassed rather than reached.

        It now answers a question about the CAPABILITY and sits in front of
        every count, so no length can trim past it.
        """
        v = _violations("Productive includes SmartCap. It predicts churn.",
                        caps={"SmartCap": ""})
        self.assertTrue(v)
        self.assertIn("no licensed page text", " ".join(m for _r, m in v))

    def test_the_longer_continuation_control_still_refuses(self):
        self.assertTrue(_violations(
            "Report Intelligence is included. Right now, it flags budget "
            "overruns as they happen."))

    def test_the_floor_is_gone_and_the_availability_note_still_ships(self):
        """THE FLOOR IS GONE, 2026-10-01, and this is why it could go.

        For three rounds the content floor was the one exemption left, kept
        because at a floor of one "Report Intelligence is available." refused
        - it has a single content word and "available" is not in any feature
        blurb. Review asked whether option (b) had changed that. IT HAD: that
        sentence is a CONTAINMENT claim, and the containment authority
        licenses it. So the floor came out and the availability note still
        ships, on the authority that was always the right one for it.

        What the floor was hiding is now inspected: "Report Intelligence
        predicts." - one content word, a false product claim - was passing.
        """
        self.assertEqual([], _violations("Report Intelligence is available."))
        self.assertTrue(_violations("Report Intelligence predicts."))

    def test_a_one_word_predicate_survives_only_via_containment(self):
        """And it is the CONTAINMENT authority doing it, not a floor.

        With the offer's containment text absent the same sentence refuses,
        which is what proves the floor is not quietly still there.
        """
        self.assertEqual([], _violations("Report Intelligence is available."))
        self.assertTrue(_behaviour_only(
            "Report Intelligence is available."))

    def test_the_cost_of_removing_the_bump_is_stated_not_hidden(self):
        """WHAT THIS ROUND TOOK AWAY.

        A two-content-word continuation that evaluates rather than describes
        is now refused: "It is worth a call" attributes WORTH to the
        capability and the licensed text cannot support it. Last round this
        test asserted the opposite. The copy rewrites to "Worth a call."
        with no pronoun and passes - a cheaper price than letting "It
        predicts churn" through, which is what the bump bought.

        A COPULA CARVE-OUT WAS CONSIDERED AND REJECTED. Exempting "it
        is/are/seems X" at under three content words would restore this
        sentence, and it would also exempt "It is real-time." - two content
        words, and the exact claim the original defect was about. A carve-out
        that readmits the founding overclaim is not a carve-out worth having.
        """
        self.assertTrue(_violations(
            "Report Intelligence is available. It is worth a call."))
        self.assertTrue(_violations(
            "Report Intelligence is available. It is real-time."))
        # AND SINCE 2026-10-01 the pronoun is not needed either: scope is
        # sticky inside a message, so a trailing line that says nothing about
        # the capability is refused too. That is the cost of deleting the
        # referring-expression list, measured at ONE extra sentence across
        # the whole production store. The copy puts the CTA in the next
        # message, or names nothing in this one.
        self.assertTrue(_violations(
            "Report Intelligence is available. Worth a call."))
        self.assertEqual([], _violations("Worth a call."))


class BypassesSixAndSeven(unittest.TestCase):
    """Reported 2026-10-01, reproduced verbatim. The reviewer's strings."""

    def test_6_a_pronoun_past_the_window(self):
        """The window was four words; the pronoun was the fifth."""
        self.assertTrue(_violations(
            "Report Intelligence is included. Over the past quarter, it "
            "flags budget overruns as they happen."))

    def test_6_a_pronoun_past_the_window_again(self):
        self.assertTrue(_violations(
            "Report Intelligence is included. In the last few weeks, it "
            "predicts churn for you."))

    def test_7_a_relative_clause(self):
        """The name is in the sentence but not at its start, so the whole
        sentence fell to the mention branch."""
        self.assertTrue(_violations(
            "Productive includes Report Intelligence, which predicts "
            "churn."))

    def test_7_a_relative_clause_with_no_page_text(self):
        v = _violations("Productive includes SmartCap, which predicts "
                        "churn.", caps={"SmartCap": ""})
        self.assertTrue(v)
        self.assertIn("no licensed page text", " ".join(m for _r, m in v))


class BypassNineTheSubordinateClause(unittest.TestCase):
    """Reported 2026-10-01, reproduced verbatim. The reviewer's strings.

    NOT A SCOPE DEFECT - the inversion held. The sentence was in scope and
    WAS checked, and the coverage test let it through: the clause splitter of
    the day knew coordinators and punctuation but not subordinators, so the
    matrix clause acted as a licensed-vocabulary cushion and the overclaim
    rode in the subordinate clause.

        "Report Intelligence delivers plain language insights about your
         business data that anticipate customer defection."

    deliver / plain / language / insight / business / data are SIX content
    stems straight out of the page text against three that are not: 67%,
    over the bar. With no comma and no coordinator anywhere, the clause unit
    saw ONE clause identical to the sentence and agreed with it.

    I NAMED THIS TWO ROUNDS AGO AND DECLINED IT, on the grounds that
    splitting on subordinators shrinks clauses below the floor and trades
    one hole for another. That was true and it was a reason not to try; the
    hole turned out to be reachable, so it became the thing to solve. See
    `_coverage_failure` for how it was answered: first by judging every clause
    at any length, then - once bypass 10 required every word to be licensed -
    by dropping the clause machinery altogether, because clauses partition
    the sentence's words and the split can no longer change a verdict.
    """

    def test_9_a_that_clause(self):
        self.assertTrue(_violations(
            "Report Intelligence delivers plain language insights about "
            "your business data that anticipate customer defection."))

    def test_9_a_so_clause(self):
        self.assertTrue(_violations(
            "Report Intelligence delivers plain language insights about "
            "your business data so it predicts churn."))

    def test_9_a_because_clause(self):
        self.assertTrue(_violations(
            "Report Intelligence delivers the insights you are looking for "
            "because it predicts churn."))

    def test_the_subordinators_are_not_three_special_cases(self):
        """Each of these is a different subordinator carrying the same
        claim. A fix for `that`, `so` and `because` alone would be the
        enumeration game again at one more remove."""
        for text in (
                "Report Intelligence delivers plain language insights "
                "which forecast churn.",
                "Report Intelligence delivers the insights you are looking "
                "for when margin slips.",
                "Report Intelligence delivers plain language insights if "
                "margin drifts in real time.",
                "Report Intelligence delivers plain language insights "
                "before margin slips away unnoticed.",
                "Report Intelligence delivers plain language insights "
                "although it also forecasts churn.",
                "Report Intelligence delivers plain language insights "
                "since it anticipates customer defection."):
            with self.subTest(text=text):
                self.assertTrue(_violations(text))

    def test_a_one_word_clause_is_judged_not_skipped(self):
        """THE SHRINKING-SPAN PROBLEM, SOLVED RATHER THAN TRADED.

        "that predict" leaves a clause of ONE content word. Under the
        clause floor of the day it was skipped, and the sentence as a whole
        read 2 of 3 covered and passed - the exact hole that was the stated
        reason for not splitting there in the first place. It now refuses for
        a stronger reason: every word must be licensed, and "predict" is not.
        """
        self.assertTrue(_violations(
            "Report Intelligence delivers insights that predict."))

    def test_the_sentence_floor_survives_the_clause_floor_going(self):
        """The caller's content floor is the one exemption left, and this
        is the sentence review named as the line it has to keep shippable."""
        self.assertEqual([], _violations("Report Intelligence is available."))

    def test_a_licensed_subordinate_clause_still_passes(self):
        """THE CONTROL. Splitting more finely must not refuse a faithful
        description that happens to use a subordinator - otherwise this is
        a blanket, not a gate."""
        self.assertEqual([], _violations(
            "Report Intelligence delivers the insights you are looking for "
            "already interpreted, in plain language."))
        self.assertEqual([], _violations(
            "Project Summary: get an executive summary or a quick recap "
            "so your team can align and move fast."))


class BypassTenTheClaimIsInTheVerb(unittest.TestCase):
    """Reported 2026-10-01, reproduced verbatim. The reviewer's strings.

    NOT A REACHABILITY DEFECT, and that is what makes it the most important
    of the ten. The sentence is in scope, it is checked, and the coverage
    RATIO let it through:

        "Report Intelligence monitors your business data."

    `business` and `data` come straight out of the page text; `monitor` is
    the entire assertion, and the licensed text describes asking and
    answering, not watching. Two borrowed object nouns outvoted the one word
    that carried the claim, 2 of 3, and it shipped.

    The previous nine were sentence shapes and could be argued as
    adversarial. This one is not adversarial at all - it is the sentence a
    language model writes by default when asked what a feature does.

    THE RATIO IS RETIRED, not raised: every content word of an in-scope
    clause must now appear in the licensed text. No verb is identified,
    because nothing needs to be - see `copylint._coverage_failure` for the
    predicate-head heuristic that was built, measured, and rejected for
    costing exactly the same while adding a positional proxy.
    """

    def test_10_monitors(self):
        self.assertTrue(_violations(
            "Report Intelligence monitors your business data."))

    def test_10_tracks(self):
        self.assertTrue(_violations(
            "Report Intelligence tracks your business data."))

    def test_10_predicts(self):
        self.assertTrue(_violations(
            "Report Intelligence predicts your business data."))

    def test_10_through_a_pronoun(self):
        self.assertTrue(_violations(
            "Productive includes Report Intelligence. It monitors your "
            "business data."))

    def test_the_verb_is_not_three_special_cases(self):
        """Any unlicensed verb against the same borrowed nouns. A fix for
        monitors/tracks/predicts alone would be a blacklist."""
        for verb in ("watches", "scans", "surveys", "polices", "audits",
                     "anticipates", "forecasts", "diagnoses"):
            text = "Report Intelligence %s your business data." % verb
            with self.subTest(text=text):
                self.assertTrue(_violations(text))

    def test_the_refusal_names_the_verb_that_carried_the_claim(self):
        """The reviewer rewriting this needs to see WHICH word was not
        licensed, not merely that one was not."""
        messages = " ".join(m for _r, m in _violations(
            "Report Intelligence monitors your business data."))
        self.assertIn("monitor", messages)

    def test_a_licensed_verb_with_the_same_nouns_still_passes(self):
        """THE CONTROL THAT SEPARATES THIS FROM A BLANKET. Same subject,
        same object nouns, licensed verb."""
        self.assertEqual([], _violations(
            "Report Intelligence understands your business data."))


class TheMeasuredCostOfEveryWordLicensed(unittest.TestCase):
    """WHAT RETIRING THE RATIO TOOK AWAY, pinned so it cannot drift quietly.

    Three sentences that used to pass now refuse, and every one of them is
    ONE WORD away from passing. None is an overclaim; all three are genuine
    false positives, and all three have a licensed rewrite:

        "...ask Productive QUESTIONS..."   the page says "Ask anything"
        "Project Summary GIVES..."          the page says "Get..."

    The third entry was "Productive INCLUDES Report Intelligence", and option
    (b) GAVE IT BACK on 2026-10-01: it is a claim about what the offer
    contains, not about what the capability does, and the offer file licenses
    it. It moved to `C_MerelyNamingItStillPasses`. The two that remain are
    genuine page_text misses with no other authority behind them.

    Measured on the production store the same day: 7 steps name a
    capability, 7 refused, 0 false positives - none of these three forms
    occurs in any of the 4,565 generated steps. The cost is in copy
    flexibility, not in copy that exists.

    IF THE OPERATOR WANTS THEM BACK, the single place to look is
    `_coverage_failure`'s `if missing:` - restoring a ratio there restores
    all three AND reopens bypass 10, which is the trade in one line.
    """

    NOW_REFUSED = (
        "Report Intelligence is how you ask Productive questions about "
        "your business data and get an interpreted answer.",
        "Project Summary gives an executive summary or a quick recap so "
        "your team can align and move fast.",
    )

    LICENSED_REWRITES = (
        "Report Intelligence delivers the insights you are looking for "
        "already interpreted, in plain language.",
        "Project Summary: get an executive summary or a quick recap so "
        "your team can align and move fast.",
    )

    def test_each_cost_is_real_and_recorded(self):
        for text in self.NOW_REFUSED:
            with self.subTest(text=text):
                self.assertTrue(_violations(text))

    def test_each_one_has_a_licensed_rewrite_that_ships(self):
        """A cost with no way out is a broken gate. Each refusal above has
        a sentence that says the same thing and passes."""
        for text in self.LICENSED_REWRITES:
            with self.subTest(text=text):
                self.assertEqual([], _violations(text))


class ShapesNobodyEnumerated(unittest.TestCase):
    """THE POINT OF THE INVERSION, AND THE ONLY TEST THAT CAN SHOW IT.

    Seven bypasses were found by picking a sentence shape the code did not
    look for: sentence-initial only, fronted PP, anchored pronoun, the
    ratio, the content floor, the four-word window, the relative clause.
    Five were reported; two of them were found here in minutes by trying.
    An enumeration cannot win that game, because the adversary picks the
    shape and the defender lists them.

    So these are shapes NOBODY wrote a rule for. Each must refuse on the
    strength of the inverted default alone - in scope, asserts a predicate,
    does not trace. If any of them passes, the inversion has leaked and the
    gate is back to enumerating.
    """

    UNENUMERATED = (
        "Really Report Intelligence predicts churn.",
        "Report Intelligence, our real-time margin monitor, is included.",
        "Budget overruns are flagged by Report Intelligence as they happen.",
        "What Report Intelligence does is predict churn before it lands.",
        "Report Intelligence's alerts land the moment margin slips.",
        "Not only does Report Intelligence answer questions, it also "
        "predicts churn.",
        "Among the things Report Intelligence does well is spotting margin "
        "drift the instant it starts.",
        "Should margin slip, Report Intelligence tells you straight away.",
        "Few tools watch margin live; Report Intelligence does.",
    )

    def test_each_unenumerated_shape_is_refused(self):
        for text in self.UNENUMERATED:
            with self.subTest(text=text):
                self.assertTrue(
                    _violations(text),
                    "a shape nobody enumerated walked through the gate")

    def test_a_demonstrative_alone_carries_the_reference(self):
        """"Any pronoun" includes the ones that are not `it`.

        Found by mutation: dropping the relative and demonstrative words
        from the referring set broke nothing, because every other test's
        string also contains "it". These two do not.

        AND THE PREAMBLE MATTERS. It was "Productive includes Report
        Intelligence", which stopped discriminating the moment bypass 10
        made "includes" an unlicensed word - the sentence refused on its own
        and the test passed whatever the second sentence did. Found by the
        same mutation surviving a second time. The preamble is now one that
        passes, so only the second sentence can be the reason.
        """
        self.assertEqual([], _violations("Report Intelligence is available."))
        self.assertTrue(_violations(
            "Report Intelligence is available. This predicts churn "
            "for you."))
        self.assertTrue(_violations(
            "Report Intelligence is available. Those flag budget "
            "overruns as they happen."))

    def test_the_longest_name_in_the_sentence_is_the_subject(self):
        """Which capability's page text a sentence is judged against.

        Two names overlap nowhere here, but a sentence can carry both, and
        then the licensed text of ONE of them decides the verdict. The longer
        name wins, because a shorter name can be a substring of a longer one
        and judging "Report Intelligence" against Project Summary's page text
        is judging it against the wrong licence.

        This sentence is licensed by Report Intelligence ("delivers the
        insights you're looking for") and NOT by Project Summary, so it
        passes only if the longer name was chosen. Found by mutation: the
        probe that used to cover this stopped discriminating when bypass 10
        made its "Productive includes ..." preamble refuse on its own.
        """
        self.assertEqual([], _violations(
            "Report Intelligence and Project Summary deliver the insights "
            "you are looking for."))

    def test_an_intervening_sentence_does_not_drop_the_referent(self):
        """BYPASS 8, found by attacking my own fix rather than by review.

        The referent used to be cleared by the first out-of-scope sentence,
        so one neutral sentence between the name and the claim let the
        claim through - the shape game again, with filler as the shape.
        Measured: this exact text PASSED until the clear was removed.

        A capability named once stays referable for the rest of the text.
        There is no sentence count to walk past, which is the only version
        of this with no number in it.
        """
        self.assertTrue(_violations(
            "Report Intelligence is included. We ship on Tuesdays. It "
            "predicts churn."))
        self.assertTrue(_violations(
            "Report Intelligence is included. We ship on Tuesdays. Pricing "
            "is per seat. Later on, it flags every overrun in real time."))

    def test_a_conjunction_is_never_evidence_of_an_overclaim(self):
        """Subordinators have to be FUNCTION words, not content.

        They used to be clause split points, so they never reached the
        coverage test. With the splitter gone they are ordinary sentence
        words, and if they were not in `_FUNCTION_WORDS` this sentence would
        be refused with "since" named as the unlicensed word - a refusal
        whose evidence is a conjunction, which nobody can act on.

        Found by a mutation that pulled them back out of the function set
        and broke nothing.
        """
        self.assertEqual([], _violations(
            "Report Intelligence delivers the insights you are looking "
            "for, since they are already interpreted."))
        self.assertEqual([], _violations(
            "Report Intelligence delivers the insights you are looking for "
            "although they are already interpreted."))

    def test_the_capability_name_is_not_its_own_unlicensed_word(self):
        """A capability's name may not need licensing by its own page text.

        "Report Intelligence" appears nowhere in Report Intelligence's page
        text, so if the name were not dropped from the sentence's content it
        would be refused as unlicensed - and the availability note would
        stop being a mention, because three content words clear the floor
        where one does not.
        """
        self.assertEqual([], _violations("Report Intelligence is available."))
        self.assertEqual([], _violations(
            "Report Intelligence delivers the insights you are looking "
            "for."))

    def test_the_gate_is_still_discriminating_and_not_a_blanket(self):
        """THE CONTROL. Every test above would also pass if the rule
        refused every sentence containing the name."""
        self.assertEqual([], _violations(
            "Report Intelligence lets you ask anything about your business "
            "data and get the insights back already interpreted, in plain "
            "language."))
        self.assertEqual([], _violations("Report Intelligence is available."))


class TheMeasuredCostOnRealCopy(unittest.TestCase):
    """WHAT THE INVERSION COSTS ON THE COPY THAT ACTUALLY EXISTS.

    MEASURED 2026-10-01, read-only, over the production store at
    `work/queue.jsonl`: 1,582 records, 4,565 generated steps.

        steps naming a licensed capability          7
        refused by the gate at e21ad223             4
        refused by the inversion                    7
        refused after the bypass-9 clause split     7   (the same seven)
        refused after the bypass-10 ratio retired   7   (the same seven)
        FALSE POSITIVES among those 7               0

    RE-MEASURED at every tightening, because the operator approves these on
    this number and a stricter gate is only safe if the number holds. It has
    not moved across three of them: same seven steps, same zero. The reason
    is structural rather than lucky - 4,558 of the 4,565 steps never name a
    licensed capability, so they are out of scope and neither clause
    splitting nor retiring the ratio can reach them. Only copy that names a
    capability is exposed to this rule at all, and all of it is already
    refused.

    Every one of the seven is a genuine overclaim of the founding kind, and
    the three the previous gate missed are live copy sitting in the store:

    three different accounts, all on em4 (the rung the offer ladder puts
    Report Intelligence at). The accounts and contacts are deliberately NOT
    named here - `work/` is gitignored because it is 300 real companies and
    92 real contacts, and a test file is not where that leaks. The copy
    itself carries no prospect:

      "Report Intelligence in Productive highlights trends that affect
       margin while a project is running"
      "Report Intelligence in Productive surfaces margin and budget
       anomalies while a project is still open, flagging risks"
      "Report Intelligence in Productive surfaces trends in margin and
       spend, highlighting data you might want to dig into further"

    All three escaped because the lint reads subject and body joined, so
    the name is never sentence-initial - the position test failing on real
    generated copy, not on a probe somebody invented.

    NONE of the three mention forms the inversion newly refuses occurs in
    any of the 4,565 steps. The measured cost of the inversion on real copy
    is zero and its measured benefit is three.

    These are the shapes of those three, pinned. The store is gitignored
    and holds 300 real companies, so the sentences are reproduced here with
    the prospect stripped out rather than read from the file at test time.
    """

    LIVE_OVERCLAIMS = (
        "Report Intelligence in Productive highlights trends that affect "
        "margin while a project is running, so issues don't sit hidden "
        "until the end.",
        "Report Intelligence in Productive surfaces margin and budget "
        "anomalies while a project is still open, flagging risks you can "
        "act on instead of missing them after the fact.",
        "Report Intelligence in Productive surfaces trends in margin and "
        "spend, highlighting data you might want to dig into further.",
    )

    def test_the_three_the_previous_gate_missed_are_refused(self):
        for text in self.LIVE_OVERCLAIMS:
            with self.subTest(text=text):
                self.assertTrue(_violations(text))

    def test_they_are_refused_through_check_batch_too(self):
        for text in self.LIVE_OVERCLAIMS:
            with self.subTest(text=text):
                self.assertTrue(_batch_refused(text))


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

    def test_an_unlicensed_capability_may_not_be_predicated_of_at_all(self):
        """WAS: "fail-closed on the DESCRIPTION, not on the mention".

        With NO licensed text there is nothing that could ever support any
        predication, so under the inversion any in-scope sentence refuses -
        and in-scope no longer depends on position. "Productive includes
        Report Intelligence" asserts inclusion, which the empty page text
        cannot support either.

        THIS IS THE STRICTEST CELL IN THE WHOLE RULE and it is reachable
        only for a capability the operator has declared and not supplied
        text for. Every capability in the real offer library has text - see
        `TheLicensedTextIsReal` - so this cell is empty in production.
        """
        self.assertTrue(_violations(
            "Productive includes Report Intelligence.",
            caps={"Report Intelligence": None}))

    def test_a_capability_nobody_declared_is_not_in_scope(self):
        """The inversion widened WHAT is in scope, not WHICH capabilities.

        An undeclared name is still none of this rule's business, so the
        gate cannot be made to refuse arbitrary copy by inventing a
        capability it was never told about.
        """
        self.assertEqual(
            [], copylint.capability_description_violations(
                "Margin Wizard predicts churn in real time and flags every "
                "overrun as it happens.", {"facts": list(PACK_FACTS)}))

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
        pack = list(packs.values())[0]
        caps = pack.get("licensed_capabilities") or {}
        self.assertIn(LICENSED_PHRASE, caps.get("Report Intelligence") or "")
        # AND THE CONTAINMENT AUTHORITY. Without it the push path refuses the
        # operator's own mandated trial phrasing, which is the whole of what
        # option (b) exists to fix. Found by a mutation that emptied it.
        self.assertIn("premium trial",
                      copylint.offer_containment_text(pack).lower())


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


class TwoLicensingAuthorities(unittest.TestCase):
    """OPERATOR-APPROVED 2026-10-01, option (b). The required list verbatim.

    a33adb8b refused the operator's own mandated phrasing for trial claims:

        "The premium trial includes Report Intelligence."       REFUSED

    It asserts nothing about what Report Intelligence DOES. It asserts what
    the OFFER CONTAINS, and the authority for that is the offer file - which
    asserts it structurally, by listing the capability under that offer's
    `ai_capabilities`. Judging it against `page_text` demanded that
    "premium", "trial" and "includes" appear in a feature blurb where they
    cannot be.

    So: a claim about what the offer CONTAINS is licensed by the offer file;
    a claim about what a capability DOES is licensed by `page_text`, exactly
    as before. THIS IS THE FIRST CHANGE IN TWELVE ROUNDS THAT LOOSENS
    ANYTHING, so the door is held to the width of the offer file by test 4
    below and by `NeitherAuthorityLicensesTheOther`.
    """

    def test_1_the_mandated_trial_phrasing_passes(self):
        self.assertEqual([], _violations(
            "The premium trial includes Report Intelligence."))

    def test_2_both_declared_capabilities_pass(self):
        self.assertEqual([], _violations(
            "The premium trial includes Report Intelligence and Project "
            "Summary."))

    def test_3_a_behaviour_claim_still_needs_page_text(self):
        self.assertTrue(_violations(
            "Report Intelligence monitors your business data."))

    def test_4_naming_the_trial_licenses_nothing_after_it(self):
        """THE TEST THAT STOPS THE OFFER AUTHORITY BEING A LOOPHOLE.

        The containment clause is licensed by the offer; "which predicts
        churn" is a BEHAVIOUR claim and still needs page_text. The sentence
        satisfies neither authority WHOLE, and the two vocabularies are never
        unioned, so it refuses.
        """
        self.assertTrue(_violations(
            "The premium trial includes Report Intelligence, which predicts "
            "churn."))

    def test_5_a_capability_the_offer_does_not_list_is_not_licensed(self):
        """Two readings of "not in the offer file", both refused.

        First: a name the offer never declared, carried inside an otherwise
        licensed trial sentence - it is not a licensed name, so it is not
        dropped, and no authority covers it.
        Second: a declared capability with NO containment text at all, which
        disables the second authority rather than defaulting it.
        """
        self.assertTrue(_violations(
            "The premium trial includes Report Intelligence and Margin "
            "Wizard."))
        self.assertTrue(_behaviour_only(
            "The premium trial includes Report Intelligence."))

    def test_the_other_mandated_wordings_pass_too(self):
        for text in ("Report Intelligence is included in the premium trial.",
                     "Report Intelligence and Project Summary are included "
                     "in the premium trial."):
            with self.subTest(text=text):
                self.assertEqual([], _violations(text))

    def test_a_behaviour_claim_in_containment_clothing_is_refused(self):
        """The containment vocabulary may not carry a behaviour claim."""
        for text in ("The premium trial includes Report Intelligence, which "
                     "monitors margin in real time.",
                     "The premium trial includes Report Intelligence so it "
                     "predicts churn for you.",
                     "The premium trial includes Report Intelligence and it "
                     "flags overruns as they happen."):
            with self.subTest(text=text):
                self.assertTrue(_violations(text))


class NeitherAuthorityLicensesTheOther(unittest.TestCase):
    """The offer file may say what the offer CONTAINS. It may not say what a
    capability DOES, and that is enforced by what is read from it.

    Offer A's selling fields are behaviour vocabulary - `value_proposition`
    is "margin per project while it is running", `cta` is "see project margin
    and budget burn while the project is still running". Reading those into
    the containment authority would hand an overclaim the exact words the
    founding defect was made of, so `offer_containment_text` reads
    `mechanism_text` and `mechanism_secondary_text` and nothing else.
    """

    def test_the_selling_fields_are_not_in_the_containment_authority(self):
        offer = offers.load()["OFFER-A-ECONOMIC-BUYER"]
        words = copylint.offer_containment_text(_pack()).lower()
        for field in ("value_proposition", "concrete_deliverable",
                      "business_problem", "cta"):
            for word in ("margin", "burn", "visible", "running"):
                if word in str(offer.get(field) or "").lower():
                    self.assertNotIn(
                        word, words,
                        "%r reached the containment authority via %s"
                        % (word, field))

    def test_the_offer_vocabulary_cannot_license_a_margin_claim(self):
        self.assertTrue(_violations(
            "Report Intelligence shows margin per project while it is "
            "running."))
        self.assertTrue(_violations(
            "Report Intelligence makes margin visible before a project "
            "closes."))

    def test_the_two_authorities_are_never_unioned(self):
        """ALL OR NOTHING, PER AUTHORITY - the claim the comment makes, pinned.

        This sentence is half containment vocabulary and half licensed
        behaviour vocabulary. Each half is honestly licensed BY A DIFFERENT
        AUTHORITY, and it is refused anyway, because a sentence must satisfy
        one authority WHOLE. Unioning the two would pass it.

        THIS IS A FALSE POSITIVE AND IT IS THE PRICE OF THE NARROW DOOR. A
        union is the obvious loosening and it is declined here: it would let
        offer vocabulary and page_text vocabulary combine into sentences
        neither authority sanctions on its own, which is the loophole review
        named. The copy splits into two sentences and both pass.

        Found by a mutation that unioned them and broke nothing.
        """
        self.assertTrue(_violations(
            "The premium trial includes Report Intelligence, which delivers "
            "the insights you are looking for."))
        # ... and the two-sentence form, which is what the writer does instead
        self.assertEqual([], _violations(
            "The premium trial includes Report Intelligence. It delivers the "
            "insights you are looking for."))

    def test_containment_words_alone_license_nothing(self):
        """The containment vocabulary is only ever licensed ALONGSIDE an
        offer that actually declares the capability.

        With no containment text in the pack the second authority is DISABLED
        rather than falling back to the bare word list - otherwise "included"
        and "covered" would license themselves with no offer behind them.
        Found by a mutation that enabled the word list unconditionally.
        """
        self.assertTrue(_behaviour_only(
            "Report Intelligence is included and covered."))
        self.assertEqual([], _violations(
            "Report Intelligence is included and covered."))

    def test_the_containment_list_is_containment_only(self):
        """A behaviour verb may not be smuggled into the containment list.

        Every word in `_CONTAINMENT_WORDS` expresses the relation "the offer
        has this", and nothing else. Found by a mutation that added
        monitor/predict/flag to it, which no other test noticed.
        """
        self.assertTrue(_violations(
            "Report Intelligence monitors and flags."))
        for word in ("monitor", "predict", "flag", "surface", "track",
                     "deliver", "margin"):
            with self.subTest(word=word):
                self.assertNotIn(word, copylint._CONTAINMENT_WORDS)

    def test_the_containment_authority_adds_nothing_to_behaviour_copy(self):
        """Every behaviour verdict is identical with the authority present
        and absent. If this goes red, (b) changed something it should not."""
        # "Report Intelligence is available." is NOT in this list: it is a
        # containment claim, so the containment authority is exactly what
        # decides it, and `test_a_one_word_predicate_survives_only_via_
        # containment` asserts that directly.
        for text in ("Report Intelligence monitors your business data.",
                     "Report Intelligence delivers the insights you are "
                     "looking for.",
                     "Report Intelligence surfaces margin and budget "
                     "patterns as they happen.",
                     "Report Intelligence understands your business data."):
            with self.subTest(text=text):
                self.assertEqual(
                    bool(_behaviour_only(text)), bool(_violations(text)),
                    "the containment authority changed a behaviour verdict")


class BypassTwelveTheReferentList(unittest.TestCase):
    """Reported 2026-10-01, reproduced verbatim. The last closed-class list.

        "Report Intelligence is available. The feature watches your
         margins in real time."                                 PASSED
        "Report Intelligence is available. The tool predicts churn."  PASSED

    `this capability` was in the referring-expression set and `the feature`
    and `the tool` were not. "The module flags overruns as they happen" was
    refused only BY ACCIDENT, because "they" appears in "as they happen" - a
    list that catches by accident is worse than one that misses, because
    nobody can predict which.

    THE LIST IS DELETED, NOT EXTENDED. Scope is now sticky: once a capability
    is named in a message, every later sentence of that message is in scope
    for it until another capability is named. Nothing is enumerated.
    """

    DEFINITE_NOUN_PHRASES = (
        "Report Intelligence is available. The feature watches your margins "
        "in real time.",
        "Report Intelligence is available. The tool predicts churn for you.",
        "Report Intelligence is available. This capability monitors spend.",
        "Report Intelligence is available. The module flags overruns as they "
        "happen.",
        "Report Intelligence is available. The AI anticipates customer "
        "defection.",
        "The premium trial includes Report Intelligence. The feature watches "
        "your margins in real time.",
    )

    def test_a_definite_noun_phrase_carries_the_reference(self):
        for text in self.DEFINITE_NOUN_PHRASES:
            with self.subTest(text=text):
                self.assertTrue(_violations(text))

    def test_a_sentence_with_no_referring_word_at_all_is_in_scope(self):
        """The hardest form: no pronoun, no definite noun phrase, nothing
        pointing back. Sticky scope does not need one."""
        self.assertTrue(_violations(
            "Report Intelligence is available. Margin alerts arrive the "
            "moment spend drifts."))

    def test_scope_opens_only_after_a_capability_is_named(self):
        """THE CONTROL. Sticky scope must not put a message in scope that
        never names a capability - otherwise every email in the estate is
        judged against a feature blurb."""
        self.assertEqual([], _violations(
            "Margin alerts arrive the moment spend drifts. The tool predicts "
            "churn. We should talk."))

    def test_a_second_capability_takes_over_the_scope(self):
        """"until another capability is named" - a later sentence with NO
        name is judged against the SECOND capability's page text.

        THE THIRD SENTENCE IS THE PROBE and the first version of this test
        did not have one: it stopped at the sentence that names Project
        Summary, which `_named_in` resolves directly, so the hand-over was
        never exercised. A mutation that froze the referent on the FIRST
        capability passed every test in the file. Sentence three carries no
        name and is licensed only by Project Summary's page text.
        """
        self.assertEqual([], _violations(
            "Report Intelligence delivers the insights you are looking for. "
            "Project Summary: get an executive summary or a quick recap. "
            "Get a quick recap so your team can align and move fast."))

    def test_the_hand_over_is_not_a_way_to_launder_a_claim(self):
        """THE CONTROL ON THE HAND-OVER. Naming a second capability must not
        license a claim neither of them supports."""
        self.assertTrue(_violations(
            "Report Intelligence delivers the insights you are looking for. "
            "Project Summary: get an executive summary. It predicts churn."))


class ScopeResetsAtTheMessageBoundary(unittest.TestCase):
    """WHAT MAKES STICKY SCOPE AFFORDABLE, measured rather than assumed.

    MEASURED 2026-10-01 over the production store, read-only. Sticky scope
    over the whole sequence POOLED - which is how `check_batch` used to hand
    copy to this rule - refused 52 extra sentences across the seven real
    sequences that name a capability:

        "Hi <first name>, Ivan here at Productive."
        "Sent you a note by email too."
        "Would a quick example be useful?"
        "Noticed you work with clients scaling up and implementing
         automation."

    Greetings, CTAs and research openers, none of them a capability claim.
    Unusable. Reset at the MESSAGE boundary it refuses ONE extra sentence in
    the whole store - "No guesswork, just the metrics in front of you as
    things change" - a real-time claim and a true positive.

    So `check_batch` calls the rule once per surface. The pooling was the
    defect, not the stickiness.
    """

    def test_a_capability_named_in_one_email_does_not_scope_the_next(self):
        lead = {"id": "ck", "ps": {}, "linkedin": {}, "pack": _pack(),
                "steps": [{"subject": "s1",
                           "body": "Report Intelligence is available."},
                          {"subject": "s2",
                           "body": "Hi Ivana, Ivan here at Productive."},
                          {"subject": "s3", "body": "Sent you a note too."},
                          {"subject": "s4", "body": "Would that be useful?"},
                          {"subject": "s5", "body": "No worries either way."}]}
        report = copylint.check_batch([lead])
        self.assertNotIn(
            "ck",
            report["offenders"].get("capability_description_unsupported")
            or (),
            "a capability named in em1 put a later email's greeting in scope")

    def test_but_an_overclaim_in_a_later_email_is_still_caught(self):
        """THE CONTROL ON THE RESET. Per-surface must not mean unchecked -
        every surface is still read, the boundaries are just respected."""
        lead = {"id": "ck", "ps": {}, "linkedin": {}, "pack": _pack(),
                "steps": [{"subject": "s1", "body": "Hello there."},
                          {"subject": "s2", "body": "Still here."},
                          {"subject": "s3", "body": "Nothing to see."},
                          {"subject": "s4",
                           "body": "Report Intelligence is available. The "
                                   "feature watches your margins in real "
                                   "time."},
                          {"subject": "s5", "body": "No worries either way."}]}
        report = copylint.check_batch([lead])
        self.assertIn(
            "ck",
            report["offenders"].get("capability_description_unsupported")
            or ())

    def test_a_ps_line_is_its_own_surface(self):
        """A P.S. is read with its email but written separately, and it is
        checked on its own rather than inheriting the body's referent."""
        surfaces = copylint.capability_surfaces(
            {"steps": [{"subject": "s", "body": "b"}],
             "ps": {"ps_em1": "Report Intelligence predicts churn."},
             "linkedin": {"connect": "A note."}})
        self.assertIn("Report Intelligence predicts churn.", surfaces)
        self.assertIn("A note.", surfaces)

    def test_every_surface_is_still_reached(self):
        """Nothing may be dropped by the per-surface change. A subject, a
        body, a P.S. and a LinkedIn message each carry an overclaim here and
        each must be caught."""
        for lead in (
                {"id": "ck", "ps": {}, "linkedin": {}, "pack": _pack(),
                 "steps": [{"subject": "Report Intelligence predicts churn",
                            "body": "Hello."}]},
                {"id": "ck", "ps": {}, "linkedin": {}, "pack": _pack(),
                 "steps": [{"subject": "s",
                            "body": "Report Intelligence predicts churn."}]},
                {"id": "ck", "linkedin": {}, "pack": _pack(),
                 "ps": {"ps_em1": "Report Intelligence predicts churn."},
                 "steps": [{"subject": "s", "body": "Hello."}]},
                {"id": "ck", "ps": {}, "pack": _pack(),
                 "linkedin": {"connect":
                              "Report Intelligence predicts churn."},
                 "steps": [{"subject": "s", "body": "Hello."}]}):
            with self.subTest(lead=lead):
                report = copylint.check_batch([lead])
                self.assertIn(
                    "ck",
                    report["offenders"].get(
                        "capability_description_unsupported") or ())


if __name__ == "__main__":
    unittest.main()
