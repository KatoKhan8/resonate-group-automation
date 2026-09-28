"""P0-B. The copy engine's Pareto fixes, and the proof each gate STILL refuses.

Every test here answers one of two questions, and the second matters more:

    1. Does the fix do what it claims on the input that was measured failing?
    2. CAN THE GATE STILL FAIL, AND ON WHAT INPUT?

A test that only shows copy getting through would be indistinguishable from a
loosened gate, which is the failure mode this repository's own history names:
the first `no_repetition/subjects` "fix" made the check structurally incapable
of firing and an adversarial review caught it, not the author. So every
tightening below is paired with a POSITIVE control (it fires on bad copy) and a
NEGATIVE control (it does not fire on good copy). A check that cannot fail is
not a check.

The failing inputs are not invented. They are lifted verbatim from
`docs/TASK-425-ONE-ACCOUNT-DRY-RUN-ARTIFACT.md` on
`origin/task-425-one-account-dry-run` (head `2d54e274`), which is the run this
task exists to explain.
"""
import unittest

from src import cadencelibrary, claims, copystages, generate, generate_campaign


#: The real `em4` body from the certified run. Three fabricated quantities -
#: `60%`, `90%` and `three times` - and nothing in the pack supports any of
#: them. Operator defect 4, 2026-09-28.
EM4_INVENTED_FIGURES = (
    "Resource decisions made at 60% budget burn versus 90% have three times "
    "the impact on final margin. The timing of when you adjust team "
    "allocation or scope determines whether a struggling project recovers or "
    "continues bleeding profitability. Early intervention preserves margins "
    "that late adjustments cannot recover. When do you typically make "
    "resource adjustments on struggling projects?")

#: The pack the run actually had, reduced to the two facts that carry figures.
#: `2` and `2016` are STORED, so copy may use them - that is what makes the
#: negative control meaningful rather than vacuous.
REC = {
    "company": "Brightmoor Studio",
    "domain": "brightmoor.test",
    "research": [
        {"fact": "Brightmoor Studio has moved to 2 week delivery cycles "
                 "across concurrent client projects, with resourcing decided "
                 "a sprint ahead."},
        {"fact": "Brightmoor Studio is a product design and engineering "
                 "agency in Amsterdam that launched its healthcare practice "
                 "in 2016."},
    ],
}
CONTACT = {"name": "A Director", "title": "Managing Director"}

#: A SENDABLE contact on a profile, because both halves are load-bearing.
#: `_candidate_steps` and `_content_shortfall` refuse to build email candidates
#: for an address `verification.is_sendable` rejects - correctly, and it is
#: recomputed from the evidence rather than read from `sendable`, so the
#: evidence list is what has to be here.
LI_CONTACT = {"key": "ck-brightmoor-1", "name": "A Director",
              "email": "a@brightmoor.test",
              "linkedin": "https://linkedin.test/in/a",
              "sendable": True, "verdict": "valid",
              "verification": {"evidence": [
                  {"provider": "contactout", "status": "valid",
                   "email": "a@brightmoor.test"},
                  {"provider": "reoon", "status": "valid",
                   "email": "a@brightmoor.test"}]}}
LI_REC = {"company": "Brightmoor Studio", "domain": "brightmoor.test",
          "contacts": [LI_CONTACT]}
#: `cadence` is what `cadence.steps_for` reads to select the sequence. Without
#: it the module default (`productive_balanced_v1`, steps `day1`/`day15`) runs
#: and a test asserting on `li5` would be asserting against the wrong cadence.
LI_CONFIG = {"cadence": "productive_li_heavy_v1",
             "linkedin_connection_note": {"mode": "llm"}}


def _sequences(**over):
    base = {k: "body for " + k for k in ("em1", "em2", "em3", "em4", "em5")}
    base.update({k: "note for " + k for k in
                 ("connect", "msg1", "msg2", "msg3", "msg4")})
    base.update(over)
    return {"sequences": base, "subjects": {"A": "Subject A", "B": "B",
                                            "C": "C"}}


class AnInventedFigureIsRefused(unittest.TestCase):
    """`_invented_quantities`: the gate that should have fired and did not.

    ISSUE-050. `claims.check_sentence` already carries the right refusal and
    `claims.is_claim` discards the sentence before it can run, so an impersonal
    fabricated benchmark passed both claim gates. Fixed in the GENERATOR's
    refusal path, leaving `claims.py` and `copylint.py` untouched.
    """

    def test_the_pre_existing_gates_really_are_blind_to_it(self):
        """The negative control for the whole fix: without it, nothing objects.

        If this ever goes green on its own, `claims.py` has been widened and
        this test's reason for existing has moved.
        """
        self.assertEqual([], claims.check(EM4_INVENTED_FIGURES, REC, CONTACT))

    def test_the_rule_was_always_right_only_its_input_selection_was_wrong(self):
        """Handed the sentence directly, the EXISTING gate refuses it.

        This is the evidence that this is an inputs defect and not a missing
        rule - which is what licenses fixing it without touching the gate.
        """
        sentence = EM4_INVENTED_FIGURES.split(". ")[0] + "."
        support = claims.support_text(REC, CONTACT)
        ok, why = claims.check_sentence(sentence, support)
        self.assertFalse(ok)
        self.assertIn("appears in no stored fact", why)

    def test_it_fires_on_every_fabricated_quantity_in_the_real_em4(self):
        found = " | ".join(generate._invented_quantities(
            EM4_INVENTED_FIGURES, REC, CONTACT))
        self.assertIn("60", found)
        self.assertIn("90", found)
        self.assertIn("three times", found)

    def test_a_quantity_spelled_as_words_is_still_a_quantity(self):
        """`three times` is invisible to every digit-based detector here.

        `claims.NUMBER` and `copylint.SPECIFIC_RES` are both digit patterns, so
        `3x` was catchable and `three times` was not.
        """
        for phrase in ("double the impact", "twice the margin",
                       "three times the effect", "a tenfold difference"):
            with self.subTest(phrase=phrase):
                self.assertTrue(generate._invented_quantities(
                    "Early intervention has %s on final margin." % phrase,
                    REC, CONTACT))

    def test_it_does_not_refuse_a_figure_the_pack_supports(self):
        """THE NEGATIVE CONTROL. A gate that refuses every number is useless.

        `2` and `2016` are in the record's own research, so copy may use them.
        """
        for body in (
                "You moved to 2 week delivery cycles, a short horizon.",
                "Since 2016 the healthcare practice has run on retainers."):
            with self.subTest(body=body):
                self.assertEqual(
                    [], generate._invented_quantities(body, REC, CONTACT))

    def test_it_does_not_refuse_copy_with_no_figure_at_all(self):
        self.assertEqual([], generate._invented_quantities(
            "Resourcing a sprint ahead collides with retained clients who "
            "expect predictable delivery.", REC, CONTACT))

    def test_a_one_character_figure_is_exempt_deliberately(self):
        """Matching `claims.check_sentence`'s own `len(cleaned) >= 2`.

        "a 5 minute call" is not a benchmark and refusing it would refuse
        almost every sentence a writer produces.
        """
        self.assertEqual([], generate._invented_quantities(
            "Worth a 5 minute look at how this works?", REC, CONTACT))

    def test_a_figure_licensed_by_the_PLANS_facts_is_not_refused(self):
        """THE SUPPORT SET MUST BE THE ONE THE COPY WAS LICENSED FROM.

        On the campaign path the extracted facts live on the plan, not on the
        record, and `claims.support_text` reads only the record. Measured
        2026-09-28: a fixture whose fact is "TestCorp is a digital marketing
        agency with 40 people" had its correct use of `40` refused as
        "the figure 40 appears in no stored fact". A false refusal of licensed
        copy, and the same wrong-inputs defect this whole task keeps finding.
        """
        body = "TestCorp has 40 people, which is where this gets interesting."
        bare = {"company": "TestCorp", "domain": "testcorp.test"}
        self.assertTrue(
            generate._invented_quantities(body, bare, CONTACT),
            "with no pack the figure must still be refused")
        pack = generate._pack_support(
            {"facts": [{"text": "TestCorp is a digital marketing agency with "
                                "40 people"}]})
        self.assertEqual(
            [], generate._invented_quantities(body, bare, CONTACT, pack),
            "a figure the plan's own facts support must not be refused")

    def test_the_pack_does_not_license_a_figure_it_never_mentions(self):
        """THE NEGATIVE CONTROL for the broadened support set: widening it to
        the plan's facts must not turn it into a set that licenses anything.
        """
        pack = generate._pack_support(
            {"facts": [{"text": "TestCorp is a digital marketing agency with "
                                "40 people"}]})
        self.assertTrue(generate._invented_quantities(
            "Agencies recover 15% of lost margin.", REC, CONTACT, pack))

    def test_the_refusal_reaches_the_step_refusal_path(self):
        """Computed correctly and read by nobody is this repo's own defect.

        So the check is asserted THROUGH `_step_refusals`, which is what the
        regeneration loop actually consults, not in isolation.
        """
        pairs = [("em4", {"channel": "email", "generated": True,
                          "subject": "Subject A",
                          "body": EM4_INVENTED_FIGURES})]
        refusals = generate._step_refusals(
            dict(REC, contacts=[CONTACT]), CONTACT, pairs)
        self.assertIn("em4", refusals)
        self.assertTrue(
            any("no stored fact" in s for s in refusals["em4"]),
            "the figure refusal did not reach _step_refusals: %r" % refusals)


class ADeclaredStepThatNothingFilledIsARefusal(unittest.TestCase):
    """`_content_shortfall`. Operator defect 2: `li5` rendered nothing, 4 of 5.

    `_candidate_steps` broke out of its loop at the fifth LinkedIn step because
    `_PLAN_LINKEDIN_ORDER` held four writer keys, so the run stored four notes
    for a five-note cadence and reported success.
    """

    def test_the_cadence_really_does_declare_five_linkedin_steps(self):
        """The premise, asserted rather than assumed."""
        li = [s["key"] for s in cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
              if s["channel"] == "linkedin"]
        self.assertEqual(["li1", "li2", "li3", "li4", "li5"], li)

    def test_a_five_step_cadence_is_now_fillable_end_to_end(self):
        """li5 maps to a real note instead of being dropped by a `break`."""
        pairs = dict(generate._candidate_steps(
            _sequences(), cadencelibrary.PRODUCTIVE_LI_HEAVY_V1,
            LI_REC, LI_CONTACT, LI_CONFIG))
        self.assertIn("li5", pairs)
        self.assertEqual("note for msg4", pairs["li5"]["note"])

    def test_no_shortfall_when_the_writer_fills_every_step(self):
        self.assertEqual([], generate._content_shortfall(
            _sequences(), cadencelibrary.PRODUCTIVE_LI_HEAVY_V1,
            LI_REC, LI_CONTACT, LI_CONFIG))

    def test_an_empty_step_is_named_and_refused(self):
        """POSITIVE CONTROL. `msg2` empty must refuse, naming the cadence step.

        `msg2` is the third writer key, so it fills `li3`.
        """
        out = generate._content_shortfall(
            _sequences(msg2=""), cadencelibrary.PRODUCTIVE_LI_HEAVY_V1,
            LI_REC, LI_CONTACT, LI_CONFIG)
        self.assertTrue(any("li3" in s and "empty" in s for s in out),
                        "an empty note was not refused: %r" % out)

    def test_an_empty_email_step_is_named_and_refused(self):
        out = generate._content_shortfall(
            _sequences(em4=""), cadencelibrary.PRODUCTIVE_LI_HEAVY_V1,
            LI_REC, LI_CONTACT, LI_CONFIG)
        self.assertTrue(any("em4" in s and "empty" in s for s in out),
                        "an empty email was not refused: %r" % out)

    def test_a_step_no_writer_key_can_fill_is_refused_as_a_contract_gap(self):
        """THE `contract` BRANCH, which a mutation proved was untested.

        Restoring the original silent `break` did NOT fail this class until
        this test existed: with five writer keys against a five-step cadence
        the contract branch never triggers, so every test here exercised only
        the `empty` branch. A green suite that cannot fail on the defect it was
        written for is the trap this repository has paid for before.

        So the cadence is given a SIXTH LinkedIn step - one no writer key can
        reach - and the shortfall must name it and say a retry will not help.
        """
        six = tuple(list(cadencelibrary.PRODUCTIVE_LI_HEAVY_V1) + [
            {"key": "li6", "day": 18, "channel": "linkedin",
             "linkedin_action": "message", "requires": "connected",
             "generated": True}])
        out = generate._content_shortfall(
            _sequences(), six, LI_REC, LI_CONTACT, LI_CONFIG)
        self.assertTrue(
            any("li6" in s and "contract" in s for s in out),
            "an unfillable cadence step was not refused: %r" % out)

    def test_the_two_shortfall_kinds_are_told_apart(self):
        """`contract` cannot be retried; `empty` can. An operator reading a
        hold needs to know which, and collapsing them is how "regenerate" gets
        recommended for something regeneration cannot fix.
        """
        six = tuple(list(cadencelibrary.PRODUCTIVE_LI_HEAVY_V1) + [
            {"key": "li6", "day": 18, "channel": "linkedin",
             "linkedin_action": "message", "requires": "connected",
             "generated": True}])
        out = generate._content_shortfall(
            _sequences(msg2=""), six, LI_REC, LI_CONTACT, LI_CONFIG)
        self.assertTrue(any("li3" in s and "empty" in s for s in out), out)
        self.assertTrue(any("li6" in s and "contract" in s for s in out), out)

    def test_a_contact_with_no_linkedin_profile_is_not_refused_for_notes(self):
        """NEGATIVE CONTROL. The writer is TOLD to return empty LinkedIn
        strings for a contact with no profile, so absence is correct there and
        refusing it would hold every email-only contact.
        """
        bare = {"name": "B", "email": "b@brightmoor.test"}
        self.assertEqual([], generate._content_shortfall(
            _sequences(connect="", msg1="", msg2="", msg3="", msg4=""),
            cadencelibrary.PRODUCTIVE_LI_HEAVY_V1,
            {"company": "B", "domain": "brightmoor.test", "contacts": [bare]},
            bare, LI_CONFIG))

    def test_the_shortfall_reaches_the_validator_that_costs_an_attempt(self):
        """The consumer link. A shortfall nothing reads is not a refusal."""
        validate = generate._campaign_validator(LI_REC, LI_CONFIG, None)
        out = validate({"contact_key": generate.lint.contact_key(LI_CONTACT),
                        **_sequences(msg2="")})
        self.assertTrue(any("li3" in s for s in out),
                        "the shortfall did not reach _campaign_validator: %r"
                        % out)


class ThePSIsCarriedOntoTheStep(unittest.TestCase):
    """Operator defect 1: no P.S. on any message, anywhere in the artifact.

    The writer produced it, `generate_campaign` harvested it, and
    `_candidate_steps` built a step dict that had no P.S. field at all.
    """

    def test_the_ps_reaches_em1_and_em3(self):
        pairs = dict(generate._candidate_steps(
            _sequences(ps_em1="P.S. one.", ps_em3="P.S. three."),
            cadencelibrary.PRODUCTIVE_LI_HEAVY_V1))
        self.assertEqual("P.S. one.", pairs["em1"].get("ps"))
        self.assertEqual("P.S. three.", pairs["em3"].get("ps"))

    def test_the_writer_is_told_the_ps_is_required(self):
        self.assertIn("REQUIRED", copystages.WRITER_SYSTEM)

    def test_the_writer_is_asked_for_the_fifth_linkedin_message(self):
        self.assertIn("msg4", copystages.WRITER_SYSTEM)


class OneThreadIsOneSubject(unittest.TestCase):
    """ISSUE-054, ruled by the operator 2026-09-28: "Same subject across one
    thread is correct threading."

    `_PLAN_SUBJECT_OF` was the third and unsourced answer - three threads -
    against a config and a provider projection that both say one.
    """

    def test_productives_declared_pattern_yields_one_subject(self):
        derived = generate._plan_subject_of(
            None, {"email_sequence": {
                "thread_reply_pattern": [False, True, True, True, True]}})
        self.assertEqual({"em1": "A", "em2": "A", "em3": "A", "em4": "A",
                          "em5": "A"}, derived)

    def test_a_client_that_really_opens_three_threads_still_gets_three(self):
        """THE CAPABILITY IS NOT REMOVED, only the hardcoded assumption.

        This is what separates "derived from the cadence" from "pinned to one
        thread": a client declaring three starters is served without a code
        change.
        """
        derived = generate._plan_subject_of(
            None, {"email_sequence": {
                "thread_reply_pattern": [False, True, False, True, False]}})
        self.assertEqual({"em1": "A", "em2": "A", "em3": "B", "em4": "B",
                          "em5": "C"}, derived)

    def test_an_unknown_pattern_falls_back_to_one_thread(self):
        """Fail-closed: the threading invariant refuses a follow-up carrying a
        distinct subject, so guessing "new thread" manufactures refused copy.
        """
        self.assertEqual({"em1": "A", "em2": "A", "em3": "A", "em4": "A",
                          "em5": "A"}, generate._plan_subject_of(None, None))

    def test_every_stored_step_carries_the_openers_subject(self):
        pairs = dict(generate._candidate_steps(
            _sequences(), cadencelibrary.PRODUCTIVE_LI_HEAVY_V1))
        for key in ("em1", "em2", "em3", "em4", "em5"):
            self.assertEqual("Subject A", pairs[key]["subject"], key)

    def test_the_thread_map_groups_steps_sharing_a_subject(self):
        threads = generate_campaign._threads_for(
            {"em1": "S", "em2": "S", "em3": "S"})
        self.assertEqual({"S"}, set(threads.values()))


class TheRetryBlockCarriesEveryEarlierRefusal(unittest.TestCase):
    """The non-convergence engine: `RETRY_BLOCK % rejected[-1]`.

    Attempt 3 was told only what attempt 2 broke, so it was free to
    reintroduce attempt 1's failure - and the artifact's c3 shows exactly that
    walk: channels_complement, then all-five repetition, then empty steps.
    """

    def test_every_earlier_failure_is_still_named_on_the_last_attempt(self):
        rejected = [
            "sequencegate channels_complement/msg3: asks a question email "
            "already asked",
            "em1: this repeats another step in the sequence",
        ]
        block = generate_campaign._cumulative_retry_block(rejected)
        self.assertIn("channels_complement", block)
        self.assertIn("repeats another step", block)

    def test_the_last_only_block_was_the_defect(self):
        """The control: the OLD block drops the first attempt's reason.

        Asserted so the improvement is measured rather than asserted.
        """
        old = generate_campaign.RETRY_BLOCK % "em1: this repeats another step"
        self.assertNotIn("channels_complement", old)

    def test_identical_failures_are_not_repeated_in_the_prompt(self):
        """The same rule firing three times is ONE thing to fix."""
        same = "sequencegate step_objectives/em5: pursues none"
        block = generate_campaign._cumulative_retry_block([same, same, same])
        self.assertEqual(1, block.count(same))

    def test_it_says_that_what_was_not_named_was_acceptable(self):
        """The sentence that stops the oscillation. Without it a full rewrite
        is the model's safest reading and every cross-step relationship is
        re-rolled.
        """
        block = generate_campaign._cumulative_retry_block(["anything"])
        self.assertIn("acceptable", block)

    def test_it_still_forbids_patching_the_offending_sentence(self):
        """OPERATOR DECISION 1 is not traded away for convergence."""
        block = generate_campaign._cumulative_retry_block(["anything"])
        self.assertIn("Do not", block)
        self.assertIn("patch", block)


class TheWriterIsToldWhatTheGatesEnforce(unittest.TestCase):
    """The dominant upstream cause: the ladder was data the writer could not
    act on, and `step_objectives` measures LEXICAL coverage per rung.
    """

    OFFER = {"step_objectives": {"1": "margin visibility",
                                 "2": "quote versus burn",
                                 "3": "resource decisions that move margin",
                                 "4": "Report Intelligence as mechanism",
                                 "5": "reframe and close"},
             "ai_capabilities": {"Report Intelligence": {}}}

    def test_every_rung_is_named_against_its_own_step(self):
        brief = generate_campaign._ladder_brief(self.OFFER, "OFFER-A")
        for rung, text in self.OFFER["step_objectives"].items():
            self.assertIn("em%s" % rung, brief)
            self.assertIn(text, brief)

    def test_it_states_the_lexical_rule_the_gate_actually_applies(self):
        brief = generate_campaign._ladder_brief(self.OFFER, "OFFER-A")
        self.assertIn("own words", brief)

    def test_a_mechanism_rung_is_named_as_conditional_not_required(self):
        """The gate WARNS on a mechanism rung rather than refusing it, so
        telling the writer it is required would push an AI capability into copy
        the operator's own rule says is never forced.
        """
        brief = generate_campaign._ladder_brief(self.OFFER, "OFFER-A")
        self.assertIn("CONDITIONAL", brief)

    def test_a_client_with_no_declared_ladder_gets_no_ladder_at_all(self):
        """`offers.py` is single-tenant. A client whose library declares no
        objectives must never be written against another client's spine.
        """
        self.assertEqual("", generate_campaign._ladder_brief({}, None))
        self.assertEqual("", generate_campaign._ladder_brief(None, None))

    def test_the_channel_rule_names_both_refusals(self):
        self.assertIn("question", generate_campaign.CHANNEL_BRIEF)
        self.assertIn("shorter form", generate_campaign.CHANNEL_BRIEF)


if __name__ == "__main__":
    unittest.main()
