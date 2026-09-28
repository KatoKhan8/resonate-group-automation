#!/usr/bin/env python3
"""The LAST step's subject may say it is the last. Nothing else may.

## THE ASYMMETRY THIS CLOSES

`copylint.check_batch` built the surface `finality_before_last_step` reads as

    non_final = "\n".join([str(b) for b in bodies[:-1]] + [subjects, extra])

`bodies[:-1]` exempts the LAST BODY, and the comment beside it says why: there
the sentence is TRUE, because it IS the last step. But `subjects` was the five
subjects pooled into one blob and went in WHOLE, so the LAST STEP'S SUBJECT
never received the exemption its own body already had.

Three statements already in `src/copylint.py` say that is wrong, and none of
them is this module's invention:

  - the rule is NAMED `finality_before_last_step`;
  - its declared sentence is "a step claims to be the last one while a later
    step still sends";
  - `FINALITY_RE`'s own docstring ends "The LAST step is exempt: there, the
    same sentence is true."

Nothing sends after the last step. So finality language in the last step's
subject is true and appropriate, exactly as it already is in the last step's
body. **This is a bug fix, and the tests below are what make that claim
falsifiable rather than asserted**: items 2 to 6 are the teeth, and a change
that bought item 1 by losing any of them would be a hole rather than a fix.

## WHY IT MATTERS NOW

`src/copyprompts.py` instructs the writer, for the canonical five-email
cadence:

    em5  day 21  NEW THREAD, breakup, subject C - short, its own
    subject_breakup C - short, three or four words, no hook, no question

A short breakup subject is precisely what `FINALITY_RE` is built to match. The
verdict of `copylint.check_batch` on generated copy is read by nothing on the
campaign path today, so the false positive is invisible; `TASK-400` makes the
verdict load-bearing, and from that moment a correct lead is regenerated
`MAX_WRITER_ATTEMPTS` times and then HELD. `test_the_breakup_subject_*` below
is that lead, in the shape `generate_campaign` builds.

## WHAT IS AND IS NOT EXERCISED THROUGH `bisonfactory.stage`

A dry run now runs the copy lint, so the last class here drives the real
production entrypoint at `live=False` with the provider transport booby-trapped.
What it can prove there is the BODY half — an earlier body refused, the last
body exempt — because `bisonfactory._copylint_batch` hands the lint
`{"body": ...}` per step and no `subject`, `ps` or `linkedin` key at all. That
is recorded in the handoff ("`_copylint_batch` builds steps with no subject
key, so this defect was unreachable there") and it is NOT changed here: this
module owns `src/copylint.py`, not the factory.

The subject surface is therefore exercised through `copylint.check_batch`
itself, which is the production function `bisonfactory`, `generate_campaign`
and `packfacts` all call, in the exact lead shape `generate_campaign` assembles
around it.

`TASK-400` merged at master `f6979300` while this was being written, so the
`generate_campaign` path where the verdict IS load-bearing is now on master.
The last class here drives it end to end with a stubbed writer, which is what
turns "this would have refused real leads" into a measured before and after.
"""
import json
import unittest
from unittest import mock

from src import (bisonfactory, campaigns, campaignstrategy, copylint,
                 generate_campaign, offers as offers_mod, providers,
                 secondbrain, store, workspaces)
from tests.base import QueueTest
from tests.test_changing_an_approved_fact_changes_the_output import (
    _FactAwareModel, _account, _approved_offer, _client_config, _contacts)
from tests.test_a_dry_run_runs_the_sequence_gate import (ADDS_ITS_OWN_ARGUMENT,
                                                         TWO_STEPS,
                                                         two_step_config,
                                                         two_step_record)
from tests.test_staging_a_campaign_twice_builds_one import CID

#: One pack fact, and an opener that leans on it. Reused verbatim from
#: `tests/test_a_step_may_not_claim_to_be_the_last_one.py` so that a refusal
#: here cannot be `step1_without_pack_fact` wearing another rule's name.
PACK = {"facts": [{"snippet": "we build brands for challenger companies"}]}
OPENER = ("Hi Dana, I was reading the site and the line about we build "
          "brands for challenger companies is what made me write.")

#: Neutral bodies. No dash, no buzzword, no specific, no template variable and
#: no double space, so the only rule any test below can move is the finality
#: one. The control asserts exactly that.
FILLER = "Following up on the note below. Happy to send it over."
CLOSER = "Keeping this one short. Tell me when to come back and I will."

#: Neutral subjects, lowercase as `copystages` mandates. All five are
#: non-empty on purpose: a blank subject leaves a gap in the concatenated
#: render that trips `empty_sentence`, which is `TASK-400`'s defect in
#: `generate_campaign` and not this module's subject.
SUBJECTS = ("how margin shows up", "how margin shows up",
            "quote against burn", "quote against burn",
            "one last thought")

#: FINALITY, in the shape `copyprompts` asks for on em5: short, three or four
#: words, no hook, no question. `FINALITY_RE` matches `closing the loop`.
BREAKUP_SUBJECT = "closing the loop"

#: Finality in a body, and the sentence that actually shipped on 690 leads.
FINALITY_BODY = ("I do not want to keep landing in your inbox, so this is "
                 "the last useful thing I have.")


def lead(subjects=SUBJECTS, bodies=None, ps=None, linkedin=None, lead_id="L"):
    """One five-step lead, in `generate_campaign`'s own shape.

    `steps` carries a subject AND a body per step, `ps` and `linkedin` sit
    beside them. That is what `generate_campaign` assembles for
    `copylint.check_batch`, which is why the finality surface has to be read
    per step rather than over a pool.
    """
    bodies = bodies or (OPENER, FILLER, FILLER, FILLER, CLOSER)
    return {"id": lead_id, "pack": PACK,
            "steps": [{"subject": s, "body": b}
                      for s, b in zip(subjects, bodies)],
            "ps": ps or {},
            "linkedin": linkedin or {}}


def report(*leads):
    return copylint.check_batch(
        list(leads), {l["id"]: l["pack"] for l in leads})


class OnlyTheLastSubjectMayClaimFinality(unittest.TestCase):

    def fired(self, *leads):
        """Did `finality_before_last_step` fire, and did the batch refuse?

        Both, and separately, because a rule firing without refusing would be
        a demotion and a refusal without this rule firing would be some other
        gate answering the question.
        """
        rep = report(*leads)
        return (rep["offenders"]["finality_before_last_step"], rep["refused"],
                rep)

    def assertOnlyFinalityFired(self, rep):
        """No other rule fired, so no test below can pass for another reason."""
        other = {name: ids for name, ids in rep["offenders"].items()
                 if ids and name != "finality_before_last_step"}
        self.assertEqual({}, other,
                         "another rule fired, so this fixture is not isolating "
                         "the finality rule: %s" % other)

    # ------------------------------------------------------------- the control
    #
    # WITHOUT THIS EVERY TEST BELOW PROVES NOTHING. A lint that accepted
    # everything would satisfy item 1 and a lint that refused everything would
    # satisfy items 2 to 6.

    def test_the_control_five_neutral_subjects_are_accepted(self):
        offenders, refused, rep = self.fired(lead())
        self.assertEqual([], offenders)
        self.assertFalse(refused, copylint.report_lines(rep))

    def test_the_control_the_shipped_defect_is_still_refused(self):
        offenders, refused, rep = self.fired(
            lead(bodies=(OPENER, FILLER, FINALITY_BODY, FILLER, CLOSER)))
        self.assertEqual(["L"], offenders)
        self.assertTrue(refused)

    # ---------------------------------------------------------- item 1: the fix

    def test_finality_in_the_last_subject_is_accepted(self):
        """ITEM 1. Nothing sends after step five, so its subject is true."""
        offenders, refused, rep = self.fired(
            lead(subjects=SUBJECTS[:4] + (BREAKUP_SUBJECT,)))
        self.assertEqual([], offenders,
                         "the last step's subject was refused for claiming a "
                         "finality that is true: no later step sends")
        self.assertFalse(refused, copylint.report_lines(rep))
        self.assertOnlyFinalityFired(rep)

    # --------------------------------------------------- items 2 to 6: the teeth

    def test_finality_in_an_earlier_subject_is_still_refused(self):
        """ITEM 2. The same words, one step earlier. Step five still sends.

        This is the pair that makes item 1 a fix rather than an exemption for
        subjects: the ONLY difference from the test above is which step carries
        the breakup subject.
        """
        for index in range(4):
            subjects = list(SUBJECTS)
            subjects[index] = BREAKUP_SUBJECT
            with self.subTest(step=index + 1):
                offenders, refused, rep = self.fired(lead(subjects=subjects))
                self.assertEqual(["L"], offenders,
                                 "step %d's subject claimed finality while "
                                 "later steps still send, and was accepted"
                                 % (index + 1))
                self.assertTrue(refused)
                self.assertOnlyFinalityFired(rep)

    def test_finality_in_an_earlier_body_is_still_refused(self):
        """ITEM 3. The 690-lead defect the rule was written for."""
        for index in range(4):
            bodies = [OPENER, FILLER, FILLER, FILLER, CLOSER]
            bodies[index] = (OPENER if index == 0
                             else "") + " " + FINALITY_BODY
            with self.subTest(step=index + 1):
                offenders, refused, rep = self.fired(lead(bodies=bodies))
                self.assertEqual(["L"], offenders)
                self.assertTrue(refused)
                self.assertOnlyFinalityFired(rep)

    def test_finality_in_a_linkedin_message_is_still_refused(self):
        """ITEM 4. The same bug in a different channel, and TASK-378's point.

        A LinkedIn follow-up is not the last thing the prospect hears from us,
        so "this will be my last message" is false there whatever the email
        steps say. The exemption is positional and LinkedIn text has no
        position in `steps`.
        """
        offenders, refused, rep = self.fired(
            lead(linkedin={"msg1": "This will be my last message."}))
        self.assertEqual(["L"], offenders,
                         "a LinkedIn message claiming finality was accepted")
        self.assertTrue(refused)
        self.assertOnlyFinalityFired(rep)

    def test_finality_in_a_ps_line_is_still_refused(self):
        """ITEM 5. Same argument, the other half of `other_prospect_text`."""
        offenders, refused, rep = self.fired(
            lead(ps={"em1": "P.S. I will stop here if now is wrong."}))
        self.assertEqual(["L"], offenders,
                         "a P.S. line claiming finality was accepted")
        self.assertTrue(refused)
        self.assertOnlyFinalityFired(rep)

    def test_the_last_body_stays_exempt(self):
        """ITEM 6. The exemption that was already right, still right."""
        offenders, refused, rep = self.fired(
            lead(bodies=(OPENER, FILLER, FILLER, FILLER,
                         "Closing the loop on this thread. No reply needed "
                         "and I will stop here.")))
        self.assertEqual([], offenders)
        self.assertFalse(refused, copylint.report_lines(rep))

    def test_a_linkedin_message_is_not_exempted_by_being_last_in_its_dict(self):
        """The exemption must not leak into the pooled surfaces.

        `subject_list[:-1]` drops one entry from the SUBJECTS. `extra` is a
        single flattened string and is never sliced, so the last LinkedIn
        message is read in full. Asserted because "exempt the last one" is
        exactly the kind of rule that grows an off-by-one into a hole.
        """
        offenders, refused, _ = self.fired(
            lead(linkedin={"connect": "hello, worth a connect",
                           "msg1": "One more thought before the week ends.",
                           "msg3": "No more messages from me after today."}))
        self.assertEqual(["L"], offenders)
        self.assertTrue(refused)

    # -------------------------------------------- item 8: prove the point

    def test_the_breakup_subject_copyprompts_asks_for_passes(self):
        """ITEM 8. The lead the pipeline is instructed to produce.

        Five steps, three threads, subjects A/A/B/B/C exactly as
        `generate_campaign` assembles them for this lint, with C the short
        breakup subject `copyprompts.subject_breakup` asks for. Today this is
        REFUSED for `finality_before_last_step` and, once `TASK-400` makes the
        verdict load-bearing, regenerated three times and then HELD.

        Every one of `FINALITY_RE`'s breakup phrasings is tried, because the
        writer is asked for three or four words and is not told which.
        """
        for phrase in ("closing the loop", "my last note", "final note",
                       "last email from me", "one last thing"):
            with self.subTest(subject_breakup=phrase):
                offenders, refused, rep = self.fired(
                    lead(subjects=("how margin shows up", "how margin shows up",
                                   "quote against burn", "quote against burn",
                                   phrase)))
                self.assertEqual([], offenders,
                                 "em5's breakup subject %r was refused" % phrase)
                self.assertFalse(refused, copylint.report_lines(rep))

    def test_that_same_breakup_subject_on_em4_is_refused(self):
        """And the falsifier for the test above, one step apart.

        If `test_the_breakup_subject_copyprompts_asks_for_passes` passed
        because finality stopped being checked in subjects at all, this fails.
        """
        for phrase in ("closing the loop", "my last note", "final note",
                       "last email from me", "one last thing"):
            with self.subTest(subject_breakup=phrase):
                offenders, refused, _ = self.fired(
                    lead(subjects=("how margin shows up", "how margin shows up",
                                   "quote against burn", phrase,
                                   "one last thought")))
                self.assertEqual(["L"], offenders,
                                 "%r on em4 was accepted while em5 still "
                                 "sends" % phrase)
                self.assertTrue(refused)

    # ------------------------------------------------- the rule is unchanged

    def test_it_is_still_a_refusing_rule_and_the_regex_is_untouched(self):
        """No rule was demoted and no pattern was widened to buy item 1."""
        self.assertNotIn("finality_before_last_step", copylint.WARNING_RULES)
        self.assertIn("finality_before_last_step", dict(copylint.RULES))
        self.assertEqual(
            "a step claims to be the last one while a later step still sends",
            dict(copylint.RULES)["finality_before_last_step"])
        # The phrasings the rule was written to catch still match. Asserted on
        # the regex's behaviour, not on its source text.
        for phrase in ("this is the last", "last email", "final note",
                       "I will stop here", "leave you alone",
                       "won't follow up", "no more emails from me",
                       "closing the loop"):
            with self.subTest(phrase=phrase):
                self.assertTrue(copylint.FINALITY_RE.search(phrase), phrase)


class AProviderRequestWasMade(AssertionError):
    """The transport was reached. On a dry run that is always a failure."""


class TheFinalityRuleThroughTheRealSendPath(QueueTest):
    """`bisonfactory.stage(live=False)`, zero provider writes.

    A dry run executes the real decision and safety path, so the copy lint runs
    here. What this class proves is that the BODY half of the rule still has
    teeth through the production entrypoint: an earlier body claiming finality
    refuses the whole stage before any provider write, and the last body does
    not. The subject half is not reachable on this path and is not made
    reachable here - see the module docstring.
    """

    def setUp(self):
        super().setUp()
        self.requests = []

        def refuse_every_request(method, url, headers, body, timeout):
            self.requests.append((method, url))
            raise AProviderRequestWasMade(
                "a provider request was made: %s %s. This run performs zero "
                "provider writes and zero provider reads" % (method, url))

        providers.set_transport(refuse_every_request)
        self.addCleanup(providers.reset_transport)

        # `sending.live` ON deliberately: the killswitch must not be what stops
        # these runs, or the copy lint would be inert and the tests green.
        ws = workspaces.new_workspace("productive", "Productive",
                                      client="productive")
        ws["settings"] = {"policy": {"sending.live": "on"}}
        workspaces.save([ws])

    def given(self, em1_extra="", em2_body=ADDS_ITS_OWN_ARGUMENT):
        rec = two_step_record(em2_body)
        if em1_extra:
            step = rec["cadence"]["rec-1-c1"]["em1"]
            step["body"] = step["body"] + "<p>%s</p>" % em1_extra
            from src import approval
            step["approval"] = {"by": "operator",
                                "at": "2026-09-13T00:00:00Z",
                                "fingerprint": approval.fingerprint(step)}
        store.save([rec])
        row = campaigns.new_campaign(CID, "productive", "Finality dry run")
        row["cadence_steps"] = [dict(s) for s in TWO_STEPS]
        row["record_ids"] = ["rec-1"]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        campaigns.save([row])

    def dry_run(self):
        return bisonfactory.stage(CID, config=two_step_config(), live=False)

    def assertNothingReachedTheProvider(self):
        self.assertEqual([], self.requests,
                         "a dry run reached the provider transport")

    def test_the_booby_trap_actually_fires(self):
        """Every zero-write claim in this class rests on this one."""
        with self.assertRaises(AProviderRequestWasMade):
            providers.request("GET", "http://example.invalid/armed",
                              headers={}, body=None, timeout=1)
        self.assertEqual([("GET", "http://example.invalid/armed")],
                         self.requests)
        self.requests.clear()

    def test_the_control_a_clean_two_step_sequence_is_projected(self):
        """Without this the refusal below is indistinguishable from a gate
        that refuses every dry run."""
        self.given()
        found = self.dry_run()
        self.assertFalse(found["copylint"]["refused"],
                         copylint.report_lines(found["copylint"]))
        self.assertEqual([], found["copylint"]
                             ["offenders"]["finality_before_last_step"])
        self.assertNothingReachedTheProvider()

    def test_a_dry_run_refuses_finality_in_an_earlier_body(self):
        """ITEM 3 through the production entrypoint.

        `em1` of a two-step sequence claims to be the last, `em2` still sends.
        The stage is refused, the refusal names the rule and the lead, and the
        provider transport is never reached.
        """
        self.given(em1_extra=FINALITY_BODY)
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            self.dry_run()
        found = caught.exception.report["copylint"]
        self.assertTrue(found["refused"])
        self.assertEqual(["rec-1/rec-1-c1"],
                         found["offenders"]["finality_before_last_step"])
        self.assertIn("finality_before_last_step", str(caught.exception))
        self.assertNothingReachedTheProvider()

    def test_a_dry_run_leaves_the_last_body_exempt(self):
        """ITEM 6 through the production entrypoint.

        The identical sentence on the LAST step of the same two-step sequence.
        It is true there, the lint does not fire, and the run reaches the
        dry-run projection.
        """
        self.given(em2_body=ADDS_ITS_OWN_ARGUMENT + "<p>%s</p>" % FINALITY_BODY)
        found = self.dry_run()
        self.assertEqual([], found["copylint"]
                             ["offenders"]["finality_before_last_step"])
        self.assertFalse(found["copylint"]["refused"],
                         copylint.report_lines(found["copylint"]))
        self.assertEqual(2, len(found["plan"]["provider_sequence"]))
        self.assertNothingReachedTheProvider()


class _BreakupSubjectModel(_FactAwareModel):
    """The same fact-aware stub, with the writer's subjects under test.

    Everything else it returns is unchanged, so the only thing that can move a
    contact from a draft to a HOLD is which subject carries the breakup line.
    No network, no real model, no provider.
    """

    def __init__(self, breakup=None, alt=None):
        super().__init__()
        self.breakup = breakup
        self.alt = alt

    def complete(self, prompt, *a, **kw):
        out = super().complete(prompt, *a, **kw)
        if "write cold outreach" not in prompt.lower():
            return out
        data = json.loads(out)
        if self.breakup is not None:
            data["subject_breakup"] = self.breakup
        if self.alt is not None:
            data["subject_alt"] = self.alt
        return json.dumps(data)


class TheCopyPathCanProduceABreakupSubject(unittest.TestCase):
    """ITEM 8, end to end, through `generate_campaign.generate`.

    `TASK-400` makes `copylint.check_batch`'s verdict act: a refused draft costs
    the writer another attempt and after `MAX_WRITER_ATTEMPTS` the copy is
    REFUSED, `sequences` and `subjects` are emptied and the contact is held
    `copy_refused`. So on master before this fix, a lead whose em5 subject is
    the breakup line `copyprompts` asks for could not be produced at all.

    `generate_campaign` maps the writer's three subjects onto five steps as
    A, A, B, B, C - so C is em5's, the last step's. That mapping is what makes
    the per-step exemption the right shape rather than a special case.
    """

    def setUp(self):
        campaignstrategy.clear_cache()
        self.addCleanup(campaignstrategy.clear_cache)
        patches = [
            mock.patch.object(offers_mod, "load",
                              return_value=_approved_offer()),
            mock.patch.object(secondbrain, "for_task", return_value={
                "profile": [{"text": "Productive shows project margin in real "
                                     "time",
                             "source": "config/clients/productive.yaml",
                             "verified": True}],
                "customers": [], "messaging": [], "offers": []}),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def run_writer(self, **kw):
        plan = generate_campaign.generate(
            _client_config(), _account(), _contacts(),
            model=_BreakupSubjectModel(**kw))
        return plan["contacts"][0]

    def test_the_control_the_fixtures_own_neutral_subject_produces_a_draft(self):
        """The baseline: this pipeline can produce a lead at all."""
        got = self.run_writer()
        self.assertIsNone(got.get("hold_kind"), got.get("held"))
        self.assertEqual(5, len([k for k in got["sequences"]
                                 if k.startswith("em")]))

    def test_a_breakup_subject_on_em5_now_produces_a_draft(self):
        """ITEM 8. The lead `copyprompts` instructs the writer to produce.

        On master's `copylint` this contact comes back `hold_kind=copy_refused`,
        `gate_attempts=3`, `sequences={}` - correct copy, refused three times
        and then held. Here it produces a full five-step draft on the FIRST
        attempt, and `finality_before_last_step` did not fire.
        """
        got = self.run_writer(breakup="closing the loop")
        self.assertIsNone(got.get("hold_kind"),
                          "the breakup subject copyprompts asks for still "
                          "holds the contact: %s" % got.get("held"))
        self.assertEqual(1, got["gate_attempts"],
                         "the draft needed a regeneration, so a gate refused "
                         "it: %s" % got.get("gate_rejections"))
        self.assertEqual("closing the loop", got["subjects"]["C"])
        self.assertEqual(5, len([k for k in got["sequences"]
                                 if k.startswith("em")]))
        self.assertEqual(
            [], got["copylint"]["offenders"]["finality_before_last_step"])
        self.assertFalse(got["copylint"]["refused"],
                         copylint.report_lines(got["copylint"]))

    def test_the_same_line_on_subject_b_still_holds_the_contact(self):
        """The falsifier, and the rule keeping its teeth on the live path.

        Subject B is em3's AND em4's, and em5 still sends after both. The
        writer is asked three times, refused three times, and the contact is
        held with the sequences emptied so nothing can be stored as a send
        candidate. Without this, the test above would pass just as well for a
        `copylint` that had stopped reading subjects.
        """
        got = self.run_writer(alt="closing the loop")
        self.assertEqual("copy_refused", got.get("hold_kind"))
        self.assertEqual(generate_campaign.MAX_WRITER_ATTEMPTS,
                         got["gate_attempts"])
        self.assertEqual({}, got["sequences"])
        self.assertEqual({}, got["subjects"])
        self.assertIn("a step claims to be the last one while a later step "
                      "still sends", got["held"])


if __name__ == "__main__":
    unittest.main()
