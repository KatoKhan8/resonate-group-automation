#!/usr/bin/env python3
"""TASK-937. The campaign copy path could not see `prior_contact`. Now a lint does.

## WHAT WAS MEASURED ON 10a38310

`grep -c prior_contact` was ZERO in `src/copystages.py`, `src/copyprompts.py`,
`src/generate_campaign.py` and `src/copylint.py`, and `copystages.py:388`
asserted "FIRST TOUCH SHAPE" with no condition on it. So every lead this
pipeline has ever written was told it was writing a first touch - including the
ones the team had already emailed by hand. Across this estate the provider
confirms 912 sends against ONE recorded local touch in 1,582 records.

`prompts/draft.md` and `claims.prior_contact_state` already carry the three
states and the proof rules for them. NOTHING IS RE-DERIVED HERE: the dossier
fixtures are imported from the module that owns them, and the state constants
come from `claims`.

## THE LINT IS THE LOAD-BEARING PART

A prompt is an instruction a model may ignore, and this file's own subject is a
writer that broke rules it had just been told about. A lint cannot be ignored.
So the refusal is asserted on EFFECT - `report["refused"]`, the offender list,
and at the end of the campaign path the sequences being EMPTIED so no caller
can store the copy as a send candidate - and never on a message string.

## BOTH DIRECTIONS, AND THE SECOND ONE IS THE EASY ONE TO GET WRONG

Replacing "we have not met" with "as discussed" is the same defect mirrored. So
every refusal below has its symmetric control beside it: the identical copy
under `not_contacted` is ACCEPTED, because there a first contact really is the
first contact. A rule that refused the claim unconditionally would satisfy half
of this file perfectly and would be a different false statement.

## NO REAL PERSON APPEARS HERE

Every name is invented and every domain is a reserved `.test` or the suite's
own committed `testcorp.com` fixture. No row comes from the corpus.
"""
import json
import unittest
from unittest import mock

from src import (campaignstrategy, claims, copylint, copystages, generate,
                 generate_campaign, offers as offers_mod, secondbrain)
from tests.base import pin_client_config
from tests.test_an_empty_ledger_is_not_a_first_contact import absent_everywhere
from tests.test_changing_an_approved_fact_changes_the_output import (
    _FactAwareModel, _account, _approved_offer, _client_config, _contacts)

# --------------------------------------------------------------------------
# THE FORBIDDEN LIST, FROM `prompts/draft.md`'s `unknown` BRANCH.
#
# Not a new vocabulary: the prompt names these as forbidden under `unknown`
# and the lint is what makes them unavailable. Each is written as a sentence a
# writer would actually produce rather than as the bare phrase, because a rule
# matching a fragment nobody writes is a rule that never fires.
# --------------------------------------------------------------------------
FIRST_TOUCH_SENTENCES = (
    "We have not met, but your margin question is the one I keep asking.",
    "You have not heard from me before, so here is the short version.",
    "This is my first time writing to anyone at your company.",
    "I am reaching out for the first time about how projects are tracked.",
    "I don't think we've connected, so a quick introduction.",
    "Apologies for the cold email, I will keep it to one question.",
    "Just a cold note from someone who reads a lot of agency sites.",
    "Out of the blue, but how is resourcing decided there today?",
    "You don't know me, and that is fine, one question anyway.",
    "We have never spoken, so I will be direct about why I wrote.",
)

#: COPY THAT SAYS NOTHING ABOUT A SHARED HISTORY. The shape `prompts/draft.md`
#: calls honest either way: an observation and a question. Every one of these
#: must pass in every state, or the rule is measuring something else.
SAYS_NOTHING = (
    "Your site says you run event and retail selling for big brands.",
    "How do you decide who is booked next week when margin is tight?",
    "We built Productive so budgets and time tracking talk to each other.",
    "Random one, but where does the current answer come from today?",
    "Could it be worth a look?",
)

#: THE NEAR MISSES, and they are the reason this rule is narrow.
#:
#: A five-step sequence is full of references to ITS OWN earlier steps, and em2
#: legitimately follows up on em1 because we wrote em1. A pattern that read
#: "following up" or "I have not" as a claim about a shared history would
#: refuse every follow-up this pipeline produces.
#: And the one that was MEASURED, 2026-10-02, over production
#: `work/queue.jsonl`: of 4,565 stored cadence steps the only thing a generic
#: `heard from` matched was two follow-ups saying "I have not heard from you",
#: which claims they have not REPLIED. Two false positives out of two matches,
#: so the verb is now scoped to the direction that asserts a first touch.
NEAR_MISSES = (
    "Following up on the note I sent on Monday.",
    "Circling back on my last email, then I will stop.",
    "I have not seen a reply, so I will leave it here.",
    "I have not heard from you, so I will close the file.",
    "We have not heard from you since June, so this is the last one.",
    "You will not need a demo to judge whether this is relevant.",
    "First, the one thing worth knowing about how margin surfaces.",
    "We work with agencies that have never had margin visible mid-project.",
)

PACK = {"facts": [{"snippet": "we run event and retail selling for big "
                              "brands across fourteen markets"}]}

OPENER = ("Hi Dana, the line on your site about event and retail selling "
          "for big brands is what made me write.")

#: Neutral filler. No dash, no buzzword, no specific, no finality, no empty
#: render - so the only rule any test here can move is the new one, and
#: `assertOnlyTheFirstTouchRuleFired` asserts exactly that.
FILLER = "Keeping this short. One question and I will leave it with you."
CLOSER = "Tell me when to come back and I will. Otherwise I will stop here."

SUBJECTS = ("how margin shows up", "how margin shows up",
            "quote against burn", "quote against burn", "one last thought")

RULE = "first_touch_claim_unlicensed"


def lead(state="__absent__", claim=None, where="body2", lead_id="L"):
    """One five-step lead in `generate_campaign`'s own shape.

    `state` of `"__absent__"` omits the key entirely, which is the BLIND
    CALLER - the shape every lead on this path had before TASK-937.
    """
    bodies = [OPENER, FILLER, FILLER, FILLER, CLOSER]
    subjects = list(SUBJECTS)
    ps, linkedin = {}, {}
    if claim:
        if where == "body2":
            bodies[1] = FILLER + " " + claim
        elif where == "body1":
            bodies[0] = OPENER + " " + claim
        elif where == "subject":
            subjects[2] = claim
        elif where == "ps":
            ps = {"em1": claim}
        elif where == "linkedin":
            linkedin = {"msg1": claim}
        else:                                    # pragma: no cover - typo net
            raise AssertionError("no such surface: %r" % where)
    out = {"id": lead_id, "pack": PACK,
           "steps": [{"subject": s, "body": b}
                     for s, b in zip(subjects, bodies)],
           "ps": ps, "linkedin": linkedin}
    if state != "__absent__":
        out["prior_contact"] = state
    return out


def report(*leads):
    return copylint.check_batch(list(leads),
                               {l["id"]: l["pack"] for l in leads})


class _LintCase(unittest.TestCase):

    def fired(self, one_lead):
        rep = report(one_lead)
        return rep["offenders"][RULE], rep["refused"], rep

    def assertOnlyTheFirstTouchRuleFired(self, rep):
        """No other rule moved, so nothing here passes for another reason."""
        other = {name: ids for name, ids in rep["offenders"].items()
                 if ids and name != RULE}
        self.assertEqual({}, other,
                         "another rule fired, so this fixture is not "
                         "isolating %s: %s" % (RULE, other))


class TheControlsComeFirst(_LintCase):
    """Without these every refusal below would be a lint that refuses all."""

    def test_a_clean_lead_passes_in_every_state(self):
        for state in claims.PRIOR_CONTACT_STATES + ("__absent__",):
            with self.subTest(prior_contact=state):
                offenders, refused, rep = self.fired(lead(state))
                self.assertEqual([], offenders)
                self.assertFalse(refused, copylint.report_lines(rep))

    def test_copy_that_says_nothing_about_a_history_passes_in_every_state(self):
        """The shape the prompt calls honest either way."""
        for state in claims.PRIOR_CONTACT_STATES + ("__absent__",):
            for sentence in SAYS_NOTHING:
                with self.subTest(prior_contact=state, sentence=sentence):
                    offenders, refused, rep = self.fired(
                        lead(state, claim=sentence))
                    self.assertEqual([], offenders, sentence)
                    self.assertFalse(refused, copylint.report_lines(rep))

    def test_a_follow_up_referring_to_our_own_earlier_step_passes(self):
        """THE NEAR MISS THAT WOULD HAVE REFUSED EVERY SEQUENCE.

        em2 follows up on em1 because we wrote em1. A history we CREATED is
        not a history nobody can read, and a pattern that could not tell them
        apart would refuse every five-step sequence this pipeline produces.

        Asserted on THIS rule's offender list rather than on the batch verdict:
        two of these sentences are refused by `buzzword` and
        `finality_before_last_step`, which are older rules doing their own
        correct job and are not this module's subject.
        """
        for sentence in NEAR_MISSES:
            with self.subTest(sentence=sentence):
                offenders, _refused, _rep = self.fired(
                    lead("unknown", claim=sentence))
                self.assertEqual([], offenders, sentence)
                self.assertEqual((), copylint.first_touch_claims(sentence))


class AClaimedFirstTouchIsRefused(_LintCase):
    """ACCEPTANCE 1. `contacted` AND `unknown`, which is the whole point."""

    def test_it_is_refused_when_somebody_already_reached_them(self):
        """`contacted`. The sentence is simply FALSE."""
        for sentence in FIRST_TOUCH_SENTENCES:
            with self.subTest(sentence=sentence):
                offenders, refused, rep = self.fired(
                    lead(claims.CONTACTED, claim=sentence))
                self.assertEqual(["L"], offenders, sentence)
                self.assertTrue(refused)
                self.assertOnlyTheFirstTouchRuleFired(rep)

    def test_it_is_refused_when_nobody_can_say(self):
        """`unknown`, AND UNKNOWN IS NOT "no".

        This is the branch the task calls load-bearing: on a worked estate it
        is the common case, and a claim about a shared history nobody has read
        is not licensed by the reading having failed.
        """
        for sentence in FIRST_TOUCH_SENTENCES:
            with self.subTest(sentence=sentence):
                offenders, refused, rep = self.fired(
                    lead(claims.PRIOR_CONTACT_UNKNOWN, claim=sentence))
                self.assertEqual(["L"], offenders, sentence)
                self.assertTrue(refused)
                self.assertOnlyTheFirstTouchRuleFired(rep)

    def test_a_lead_carrying_no_state_at_all_is_refused(self):
        """THE BLIND CALLER, which is every lead this path had before TASK-937.

        Invariant 0: an unreadable authority means UNKNOWN, and UNKNOWN never
        becomes safe. A caller that recorded nothing does not get the lenient
        branch by having recorded nothing.
        """
        for sentence in FIRST_TOUCH_SENTENCES:
            with self.subTest(sentence=sentence):
                offenders, refused, _ = self.fired(lead(claim=sentence))
                self.assertEqual(["L"], offenders, sentence)
                self.assertTrue(refused)

    def test_the_legacy_boolean_is_read_the_way_the_prompt_reads_it(self):
        """`False` IS `unknown`, NOT A PROVEN NEGATIVE, and `True` is contacted.

        `prompts/draft.md` states this mapping and the measurement behind it:
        912 provider-confirmed sends against one recorded local touch, so a
        boolean `false` was very often somebody we had written to.
        """
        for value in (False, True, "false", "true", "", "UNKNOWN", 0, 1,
                      "no idea"):
            with self.subTest(prior_contact=value):
                offenders, refused, _ = self.fired(
                    lead(value, claim=FIRST_TOUCH_SENTENCES[0]))
                self.assertEqual(["L"], offenders,
                                 "prior_contact=%r licensed a first-touch "
                                 "claim" % value)
                self.assertTrue(refused)

    def test_it_is_refused_on_every_surface_a_prospect_reads(self):
        """A body, a subject, a P.S. line and a LinkedIn message.

        The sentence is equally false in a connection note, and the surfaces
        this module used to read only half of are where three earlier rules
        found their offenders.
        """
        for where in ("body1", "body2", "subject", "ps", "linkedin"):
            with self.subTest(surface=where):
                offenders, refused, _ = self.fired(
                    lead("unknown", claim="We have not met.", where=where))
                self.assertEqual(["L"], offenders,
                                 "a first-touch claim in %s was accepted"
                                 % where)
                self.assertTrue(refused)

    def test_the_refusal_names_the_clause_rather_than_only_the_lead(self):
        """A per-lead verdict sends somebody hunting through eleven messages."""
        self.assertEqual(
            ("we have not met",),
            copylint.first_touch_claims("Hi Dana, we have not met, but..."))
        self.assertEqual(
            ("We have not met",),
            copylint.first_touch_claims("We have not met. One question."))


class AGenuineFirstContactMayStillSayItIsTheFirst(_LintCase):
    """ACCEPTANCE 2, THE SYMMETRIC CONTROL, and the easy half to get wrong.

    Swapping one false claim for another is not a fix. On a PROVEN negative -
    the provider asked and answered on both channels, the send history
    reconciling - saying it is the first contact is TRUE, and a lint that
    refused it would be making the opposite false statement.
    """

    def test_every_forbidden_sentence_is_allowed_on_a_proven_negative(self):
        for sentence in FIRST_TOUCH_SENTENCES:
            with self.subTest(sentence=sentence):
                offenders, refused, rep = self.fired(
                    lead(claims.NOT_CONTACTED, claim=sentence))
                self.assertEqual([], offenders,
                                 "a PROVEN first contact was refused for "
                                 "saying so: %r" % sentence)
                self.assertFalse(refused, copylint.report_lines(rep))

    def test_the_falsifier_one_word_of_state_apart(self):
        """The pair that makes the test above a control rather than an exemption.

        The ONLY difference between these two leads is the measured state. If
        the rule had been widened to let a first-touch claim through, or had
        stopped reading the state, exactly one of these two assertions fails.
        """
        sentence = FIRST_TOUCH_SENTENCES[0]
        self.assertEqual([], self.fired(lead(claims.NOT_CONTACTED,
                                             claim=sentence))[0])
        self.assertEqual(["L"], self.fired(lead(claims.PRIOR_CONTACT_UNKNOWN,
                                                claim=sentence))[0])

    def test_it_is_allowed_on_every_surface_on_a_proven_negative(self):
        for where in ("body1", "body2", "subject", "ps", "linkedin"):
            with self.subTest(surface=where):
                offenders, refused, rep = self.fired(
                    lead(claims.NOT_CONTACTED, claim="We have not met.",
                         where=where))
                self.assertEqual([], offenders, where)
                self.assertFalse(refused, copylint.report_lines(rep))


class TheRuleRefusesAndWasNotDemoted(unittest.TestCase):

    def test_it_is_a_refusing_rule_and_not_a_warning(self):
        self.assertIn(RULE, dict(copylint.RULES))
        self.assertNotIn(RULE, copylint.WARNING_RULES)

    def test_heard_from_is_a_claim_in_ONE_direction_only(self):
        """THE MEASURED OVER-FIRE, and the pair that keeps the narrowing honest.

        "You have not heard from me" asserts that nobody has written. "I have
        not heard from you" asserts that they have not REPLIED, which is what a
        follow-up says and is true of a thread we started ourselves. Measured
        2026-10-02 over production `work/queue.jsonl`: 4,565 stored cadence
        steps, and the only matches a direction-blind pattern produced were two
        of the second kind. Both assertions here, or the narrowing is a hole.
        """
        for claim in ("You have not heard from me before.",
                      "You haven't heard from us.",
                      "You've never heard from me."):
            with self.subTest(claim=claim):
                self.assertTrue(copylint.first_touch_claims(claim), claim)
        for not_a_claim in ("I have not heard from you, so I will stop.",
                            "We have not heard from you since June.",
                            "I haven't heard from you on this one."):
            with self.subTest(not_a_claim=not_a_claim):
                self.assertEqual((), copylint.first_touch_claims(not_a_claim),
                                 not_a_claim)

    def test_the_state_normaliser_never_invents_a_proven_negative(self):
        """ONE string licenses the claim, and nothing else may map onto it."""
        for value in (None, True, False, "", "unknown", "contacted", "true",
                      "false", "nope", 0, 1, [], {}, "NOT CONTACTED"):
            with self.subTest(value=value):
                state = copylint.prior_contact_state_of(
                    {"prior_contact": value})
                if str(value) == "not_contacted":       # pragma: no cover
                    continue
                self.assertNotEqual(claims.NOT_CONTACTED, state, repr(value))
        self.assertEqual(claims.NOT_CONTACTED,
                         copylint.prior_contact_state_of(
                             {"prior_contact": "not_contacted"}))
        self.assertEqual(claims.NOT_CONTACTED,
                         copylint.prior_contact_state_of(
                             {"prior_contact": "NOT_CONTACTED"}))

    def test_the_states_are_the_authoritys_own_and_not_a_second_copy(self):
        """A second vocabulary would drift, and the drift would be silent."""
        for state in claims.PRIOR_CONTACT_STATES:
            self.assertEqual(state, copylint.prior_contact_state_of(
                {"prior_contact": state}))


class TheWriterIsToldWhichStateWasMeasured(unittest.TestCase):
    """ACCEPTANCE 3. `copystages` asserts the measured state, or refuses."""

    def block(self, **kw):
        return copystages.writer_user(
            {"name": "Dana Quill", "title": "COO",
             "sender_name": "Ivan"},
            "Northwind Tilery", [{"text": "fourteen markets"}],
            "THE PLAN", "margin while the project runs", "ps_fact",
            True, **kw)

    def test_the_three_states_produce_three_different_instructions(self):
        seen = {state: self.block(prior_contact=state)
                for state in claims.PRIOR_CONTACT_STATES}
        self.assertEqual(3, len({v for v in seen.values()}),
                         "two states gave the writer the same instruction, so "
                         "the shape is not conditional on the state")

    def test_only_the_proven_negative_permits_the_claim(self):
        self.assertIn("MAY say this is the first contact",
                      self.block(prior_contact=claims.NOT_CONTACTED))
        for state in (claims.CONTACTED, claims.PRIOR_CONTACT_UNKNOWN):
            with self.subTest(prior_contact=state):
                self.assertIn("DO NOT", self.block(prior_contact=state))
                self.assertNotIn("MAY say this is the first contact",
                                 self.block(prior_contact=state))

    def test_an_absent_state_is_unknown_and_not_a_clean_slate(self):
        """Invariant 0 at the prompt, the same way the lint reads it."""
        self.assertEqual(self.block(prior_contact="unknown"), self.block())
        self.assertNotEqual(self.block(prior_contact="not_contacted"),
                            self.block())

    def test_the_legacy_boolean_maps_the_way_the_prompt_maps_it(self):
        self.assertEqual(self.block(prior_contact="unknown"),
                         self.block(prior_contact=False))
        self.assertEqual(self.block(prior_contact="contacted"),
                         self.block(prior_contact=True))

    def test_a_state_nobody_can_read_is_refused_rather_than_guessed(self):
        """A writer told something uninterpretable decides the shape itself."""
        for value in ("maybe", "NOT_CONTACTED_YET", 7, "cold"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.block(prior_contact=value)

    def test_the_system_prompt_no_longer_asserts_a_first_touch_outright(self):
        """Asserted on the artefact that reaches the model, which is text.

        A behavioural assertion cannot reach an LLM instruction, and the DEFECT
        WAS THE TEXT: `copystages.py:388` read "FIRST TOUCH SHAPE, not a rigid
        formula" with no condition on it, for every lead. This is the
        regression lock on that line, and it is the only text assertion here.
        """
        body = copystages.WRITER_SYSTEM
        self.assertNotIn("FIRST TOUCH SHAPE,", body,
                         "the unconditional first-touch heading is back")
        self.assertIn("prior_contact", body)
        for state in claims.PRIOR_CONTACT_STATES:
            self.assertIn(state, body,
                          "the writer prompt does not name %r, so it cannot "
                          "branch on it" % state)

    def test_the_skill_the_entrypoint_loads_carries_it(self):
        """The prompt only matters if the loaded skill is this string."""
        from src import skills
        self.assertEqual(copystages.WRITER_SYSTEM,
                         skills.load("cold_email_writing").procedure)


class TheCampaignPathCarriesTheStateIntoTheLint(unittest.TestCase):
    """ACCEPTANCE 1, 2 AND 5 THROUGH `generate_campaign.generate`.

    The EFFECT asserted is the copy that would ship. After
    `MAX_WRITER_ATTEMPTS` refusals `generate_campaign` empties `sequences` and
    `subjects` and holds the contact `copy_refused`, so "never stored as a send
    candidate" is a measurement rather than a comment. No provider is reached
    and no model is called: the writer is a scripted stub.
    """

    def setUp(self):
        campaignstrategy.clear_cache()
        self.addCleanup(campaignstrategy.clear_cache)
        for patch in (
                mock.patch.object(offers_mod, "load",
                                  return_value=_approved_offer()),
                mock.patch.object(secondbrain, "for_task", return_value={
                    "profile": [{"text": "Productive shows project margin in "
                                         "real time",
                                 "source": "config/clients/productive.yaml",
                                 "verified": True}],
                    "customers": [], "messaging": [], "offers": []})):
            patch.start()
            self.addCleanup(patch.stop)

    def run_writer(self, prior_contact=None, claim=None):
        contacts = _contacts()
        if prior_contact is not None:
            contacts[0]["prior_contact"] = prior_contact
        plan = generate_campaign.generate(
            _client_config(), _account(), contacts,
            model=_ClaimingWriter(claim))
        return plan["contacts"][0]

    def test_the_control_clean_copy_produces_a_draft(self):
        """Without this every refusal below is a pipeline that refuses all."""
        got = self.run_writer()
        self.assertIsNone(got.get("hold_kind"), got.get("held"))
        self.assertEqual(5, len([k for k in got["sequences"]
                                 if k.startswith("em")]))

    def test_the_measured_state_is_recorded_on_the_plan(self):
        """A shape nobody can attribute to a state is a shape nobody can audit."""
        self.assertEqual(claims.PRIOR_CONTACT_UNKNOWN,
                         self.run_writer()["prior_contact"])
        self.assertEqual(claims.NOT_CONTACTED,
                         self.run_writer(prior_contact="not_contacted")
                         ["prior_contact"])
        self.assertEqual(claims.CONTACTED,
                         self.run_writer(prior_contact=True)["prior_contact"])

    def test_a_first_touch_claim_under_unknown_never_reaches_a_caller(self):
        """THE EFFECT: the copy that would have shipped is GONE.

        The contact carries no `prior_contact`, which is every contact this
        path had before TASK-937, so the state is `unknown`.
        """
        got = self.run_writer(claim="We have not met, so I will be direct.")
        self.assertEqual("copy_refused", got.get("hold_kind"))
        self.assertEqual({}, got["sequences"])
        self.assertEqual({}, got["subjects"])
        self.assertEqual(generate_campaign.MAX_WRITER_ATTEMPTS,
                         got["gate_attempts"])
        self.assertEqual(["jane@testcorp.com"],
                         got["copylint"]["offenders"][RULE])

    def test_the_same_claim_under_a_proven_negative_ships(self):
        """THE SYMMETRIC CONTROL, end to end, one field apart."""
        got = self.run_writer(prior_contact=claims.NOT_CONTACTED,
                              claim="We have not met, so I will be direct.")
        self.assertIsNone(got.get("hold_kind"),
                          "a PROVEN first contact was refused for saying so: "
                          "%s" % got.get("held"))
        self.assertEqual(1, got["gate_attempts"],
                         "the draft was regenerated, so a gate refused it: %s"
                         % got.get("gate_rejections"))
        self.assertEqual([], got["copylint"]["offenders"][RULE])
        self.assertEqual(5, len([k for k in got["sequences"]
                                 if k.startswith("em")]))

    def test_a_contacted_lead_is_refused_too(self):
        got = self.run_writer(prior_contact=claims.CONTACTED,
                              claim="We have not met, so I will be direct.")
        self.assertEqual("copy_refused", got.get("hold_kind"))
        self.assertEqual({}, got["sequences"])

    def test_the_retry_quotes_the_clause_rather_than_only_the_rule(self):
        """A writer holding eleven messages needs the words, not a rule name."""
        got = self.run_writer(claim="We have not met, so I will be direct.")
        self.assertTrue(got["gate_rejections"])
        self.assertIn("we have not met", got["gate_rejections"][0].lower())

    def test_the_writer_was_told_the_state_before_it_wrote(self):
        """The prompt half, proved on the prompt the pipeline actually sent."""
        contacts = _contacts()
        contacts[0]["prior_contact"] = claims.NOT_CONTACTED
        model = _ClaimingWriter(None)
        generate_campaign.generate(_client_config(), _account(), contacts,
                                   model=model)
        self.assertTrue(model.writer_prompts)
        self.assertIn("prior_contact: not_contacted", model.writer_prompts[0])
        self.assertNotIn("prior_contact: unknown", model.writer_prompts[0])


class _ClaimingWriter(_FactAwareModel):
    """The suite's own stage stub, with ONE sentence added to em2 and msg1.

    Everything else it returns is unchanged, so the only thing that can move a
    contact from a draft to a hold is that sentence and the measured state.
    No network, no real model, no provider.
    """

    def __init__(self, claim=None):
        super().__init__()
        self.claim = claim
        self.writer_prompts = []

    def complete(self, prompt, *a, **kw):
        out = super().complete(prompt, *a, **kw)
        if "write cold outreach" not in str(prompt).lower():
            return out
        self.writer_prompts.append(prompt)
        if not self.claim:
            return out
        data = json.loads(out)
        emails = data.get("emails") or {}
        emails["em2"] = str(emails.get("em2", "")) + " " + self.claim
        data["emails"] = emails
        return json.dumps(data)


class TheDraftPromptGetsTheThreeStateValue(unittest.TestCase):
    """ACCEPTANCE 4. `generate.py:672` and `:694`, and REACHABILITY.

    Before TASK-937 both lines passed `bool(claims.prior_contact(rec,
    contact))`, which reads `rec["events"]` and nothing else. `prompts/draft.md`
    reads a boolean as `unknown`, so no false claim shipped - but the
    first-touch branch was UNREACHABLE, because a boolean has no third value
    and `false` could not mean "proven never contacted". These tests are what
    make "reachable" a measurement.
    """

    def setUp(self):
        pin_client_config(self)
        generate.clear_company_cache()
        self.addCleanup(generate.clear_company_cache)

    def rec(self, events=()):
        return {"id": "northwind-tilery-test", "client": "productive",
                "company": "Northwind Tilery", "domain": "northwind.test",
                "lane": "domains", "state": "verified",
                "events": list(events),
                "contacts": [dict(self.contact())]}

    def contact(self):
        return {"key": "dana", "name": "Dana Quill", "email": "dana@northwind.test",
                "first_name": "Dana", "title": "COO", "persona": "champion",
                "linkedin": "https://www.linkedin.com/in/dana-quill-test"}

    def state(self, step="draft", events=(), dossier=None, on_record=False):
        rec = self.rec(events)
        if on_record:
            rec[generate.RECONTACT_DOSSIER_KEY] = dossier
            dossier = None
        block = generate.context_for(step, rec, self.contact(),
                                     step_key="em1" if step == "draft"
                                     else "day3", dossier=dossier)
        return block["prior_contact"]

    def test_it_is_a_state_and_not_a_boolean(self):
        for step in ("draft", "linkedin_note"):
            with self.subTest(step=step):
                got = self.state(step)
                self.assertNotIsInstance(got, bool)
                self.assertIn(got, claims.PRIOR_CONTACT_STATES)

    def test_an_empty_event_log_is_unknown_and_not_a_proven_negative(self):
        """THE DEFECT, DIRECTLY. 1,581 of 1,582 records look like this."""
        for step in ("draft", "linkedin_note"):
            with self.subTest(step=step):
                self.assertEqual(claims.PRIOR_CONTACT_UNKNOWN,
                                 self.state(step))

    def test_a_confirmed_local_touch_is_contacted(self):
        for step in ("draft", "linkedin_note"):
            with self.subTest(step=step):
                self.assertEqual(
                    claims.CONTACTED,
                    self.state(step, events=[{"type": "email_delivered",
                                              "contact": "dana"}]))

    def test_the_first_touch_branch_IS_reachable_with_a_dossier(self):
        """THE REACHABILITY PROOF, and it is the point of acceptance 4.

        The dossier fixture is `absent_everywhere()` from the module that owns
        it: a provider lookup that ANSWERED and found no lead row, and an inbox
        with no thread. That is the only evidence that licenses the branch, and
        with it the prompt is handed `not_contacted` rather than a boolean.
        """
        for step in ("draft", "linkedin_note"):
            with self.subTest(step=step):
                self.assertEqual(
                    claims.NOT_CONTACTED,
                    self.state(step, dossier=absent_everywhere()))

    def test_the_dossier_may_also_arrive_on_the_record(self):
        """The seam for a caller that already paid for the provider read."""
        self.assertEqual(claims.NOT_CONTACTED,
                         self.state(dossier=absent_everywhere(),
                                    on_record=True))

    def test_an_unreadable_dossier_is_unknown_rather_than_a_guess(self):
        for junk in (None, "", [], 0, "absent"):
            with self.subTest(dossier=junk):
                self.assertEqual(claims.PRIOR_CONTACT_UNKNOWN,
                                 self.state(dossier=junk))

    def test_the_rendered_prompt_carries_the_state_the_model_reads(self):
        """A block key nothing renders is the defect this repo keeps finding."""
        rec = self.rec()
        prompt = generate.render_prompt("draft", rec, self.contact(),
                                        step_key="em1",
                                        dossier=absent_everywhere())
        self.assertIn('"prior_contact": "not_contacted"', prompt)
        plain = generate.render_prompt("draft", rec, self.contact(),
                                       step_key="em1")
        self.assertIn('"prior_contact": "unknown"', plain)


if __name__ == "__main__":
    unittest.main()
