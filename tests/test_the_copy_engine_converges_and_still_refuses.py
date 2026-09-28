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


#: A pack that literally contains "doubled" and "twice", so the support half of
#: the worded-quantity check has something to find. B1's whole defect was that
#: the branch never looked.
SUPPORTED_REC = {
    "company": "Brightmoor Studio", "domain": "brightmoor.test",
    "research": [
        {"fact": "Brightmoor Studio doubled its delivery throughput and "
                 "halved cycle time, twice audited."},
        {"fact": "Brightmoor Studio moved to 2 week cycles in 2016."},
    ],
}


class AWordedQuantityIsCheckedAgainstTheSupportSet(unittest.TestCase):
    """B1. The branch refused on match alone and never consulted `stored`.

    THE NEGATIVE CONTROLS THAT WERE MISSING ARE THE POINT OF THIS CLASS.
    The first round shipped a POSITIVE control for `_WORDED_QUANTITY` and no
    negative one - every negative control in the file exercised the NUMERIC
    branch - so a check that could not pass looked tested. Its refusal
    sentence asserted "no stored fact supports" without looking at one.
    """

    def test_a_worded_quantity_the_pack_supports_is_not_refused(self):
        """NEGATIVE CONTROL. The pack says "doubled"; "double" is licensed."""
        self.assertEqual([], generate._invented_quantities(
            "That would double throughput.", SUPPORTED_REC, CONTACT))

    def test_twice_is_not_refused_when_the_pack_says_twice(self):
        self.assertEqual([], generate._invented_quantities(
            "It was audited twice.", SUPPORTED_REC, CONTACT))

    def test_ordinary_english_is_not_a_quantity_claim(self):
        """NEGATIVE CONTROL. Each of these was measured refusing real copy,
        costing a writer attempt and then a hold - in exactly the register a
        re-engagement sequence writes in.
        """
        for text in ("Let me double-check that before I say more.",
                     "I wrote twice last year and got no reply.",
                     "Half an hour would be enough to settle it.",
                     "Half the team had changed by then.",
                     "Half of the work is done."):
            with self.subTest(text=text):
                self.assertEqual([], generate._invented_quantities(
                    text, REC, CONTACT), text)

    def test_it_still_refuses_an_unsupported_multiplier(self):
        """POSITIVE CONTROL. The gate keeps its whole purpose."""
        for text in ("Resource decisions have three times the impact.",
                     "Early intervention has double the effect on margin.",
                     "We tripled margin for an agency like yours.",
                     "That halved their reporting time."):
            with self.subTest(text=text):
                self.assertTrue(generate._invented_quantities(
                    text, REC, CONTACT), text)

    def test_an_idiom_does_not_exempt_a_real_multiplier_beside_it(self):
        """NO BYPASS. The idiom test is by POSITION; testing for presence
        anywhere in the text would let one "double-check" license every
        fabricated multiplier in the same message.
        """
        self.assertTrue(generate._invented_quantities(
            "Let me double-check. Also it has three times the impact.",
            REC, CONTACT))


class TheDateExemptionDoesNotExemptRatios(unittest.TestCase):
    """B2. `\\d{1,2}/\\d{1,2}` read a fabricated ratio as a date.

    The gate's own founding example drove straight through it: `60/90` carries
    the SAME TWO FIGURES as the `60% ... 90%` form it was built to refuse, one
    character of punctuation apart.
    """

    def test_a_bare_ratio_is_refused(self):
        for text in ("Decisions at a 60/90 burn split differ sharply.",
                     "We normally see a 70/30 split in margin recovery.",
                     "Early intervention gives a 90/10 recovery rate."):
            with self.subTest(text=text):
                self.assertTrue(generate._invented_quantities(
                    text, REC, CONTACT), text)

    def test_the_percent_form_of_the_same_figures_still_refuses(self):
        """The control that keeps the two rows comparable."""
        self.assertTrue(generate._invented_quantities(
            "Decisions at 60% burn versus 90% differ sharply.", REC, CONTACT))

    def test_a_full_slashed_date_is_still_exempt(self):
        """NEGATIVE CONTROL. Narrowing the exemption must not remove it."""
        self.assertEqual([], generate._invented_quantities(
            "We spoke on 17/10/2024 about the key.", REC, CONTACT))

    def test_a_year_in_a_date_context_is_exempt(self):
        """F1. A third false refusal of the same class as the day number."""
        for text in ("We last spoke in October 2024 about this.",
                     "The practice has been running since 2019.",
                     "Nothing has been decided since Q1 2025.",
                     "On 17 October Jesse asked to run the key."):
            with self.subTest(text=text):
                self.assertEqual([], generate._invented_quantities(
                    text, REC, CONTACT), text)

    def test_a_four_digit_COUNT_is_not_exempt(self):
        """The exemption is a date context, not any four digits. Without this
        `"we work with 2024 agencies"` would be licensed by the year branch.
        """
        self.assertTrue(generate._invented_quantities(
            "We work with 2024 agencies in your market.", REC, CONTACT))


class AnInventedFigureIsRefusedOnLinkedInToo(unittest.TestCase):
    """B3, and the one that reaches a person.

    The figure gate was wired into the EMAIL branch of `_step_refusals` only.
    `heyreachfactory` maps `li1..li5` onto `connection_note` and
    `connected_1..4` from this record's own cadence, and this branch widened
    that surface from four notes to five.
    """

    BAD_NOTE = ("We cut delivery overhead by 73% across 41 studios "
                "and tripled margin last year, which is the pattern worth "
                "knowing about here.")

    def test_a_linkedin_note_with_an_invented_figure_is_refused(self):
        refusals = generate._step_refusals(
            dict(REC, contacts=[LI_CONTACT]), LI_CONTACT,
            [("li4", {"channel": "linkedin", "generated": True,
                      "note": self.BAD_NOTE})])
        self.assertIn("li4", refusals,
                      "an invented figure on LinkedIn was stored with no "
                      "refusal: %r" % refusals)
        self.assertTrue(any("no stored fact" in s for s in refusals["li4"]))

    def test_nothing_else_catches_it_which_is_why_this_gate_exists(self):
        """The reason the email-only wiring was a real hole and not a
        duplicate: `copylint.untraceable` returns nothing for this note.
        """
        from src import copylint
        self.assertEqual([], copylint.untraceable(
            self.BAD_NOTE, {"facts": [{"snippet": "an agency in Amsterdam"}]}))

    def test_a_clean_linkedin_note_is_not_refused(self):
        """NEGATIVE CONTROL. Wiring the gate to a second channel must not
        refuse correct notes there.
        """
        self.assertEqual({}, generate._step_refusals(
            dict(REC, contacts=[LI_CONTACT]), LI_CONTACT,
            [("li4", {"channel": "linkedin", "generated": True,
                      "note": "Noticed the Amsterdam agency work. "
                              "Worth a look at how this runs while a "
                              "project is still open?"})]))


class ThePSIsGatedWithTheBodyItShipsUnder(unittest.TestCase):
    """F3b. `step["ps"]` sat outside the gated text, so the one newly-plumbed
    prospect-facing surface was the one surface no content gate inspected.
    """

    BODY = ("Noticed the Amsterdam agency work and wanted to ask one "
            "thing about how projects are tracked while they are still open, "
            "because that timing is usually where the useful conversation is "
            "and it is the part that tends to get decided late in practice.")

    def _refusals(self, ps=None):
        step = {"channel": "email", "generated": True,
                "subject": "a question", "body": self.BODY}
        if ps:
            step["ps"] = ps
        return generate._step_refusals(
            dict(REC, contacts=[LI_CONTACT]), LI_CONTACT, [("em1", step)])

    def test_the_body_alone_is_clean(self):
        """The baseline, so the next test isolates the P.S. and nothing else."""
        self.assertEqual({}, self._refusals())

    def test_an_invented_figure_in_the_ps_is_refused(self):
        refusals = self._refusals(
            ps="P.S. we cut delivery overhead by 73% across 41 studios.")
        self.assertIn("em1", refusals,
                      "the P.S. bypassed every content gate: %r" % refusals)
        self.assertTrue(any("73" in s for s in refusals["em1"]))

    def test_a_clean_ps_is_not_refused(self):
        """NEGATIVE CONTROL."""
        self.assertEqual({}, self._refusals(
            ps="P.S. the Amsterdam practice looked like the busiest part."))


class TheTenantGuardMatchesOnTheProductionPath(unittest.TestCase):
    """B4. The guard compared a display name with a filename slug.

    `clients.load("productive")["name"]` is `'Productive'` and the offers
    tenant is `'productive'`, so the comparison was never true - and
    `src/generate.py` always passes the CONFIG DICT, so the sequence gate's
    verdict went unread on the only path production generates copy through.
    Mutation M7 surviving was this hole seen from the other side.
    """

    def test_the_display_name_and_the_slug_really_do_differ(self):
        """The premise, asserted rather than assumed - it is the whole bug."""
        from src import clients
        config = clients.load("productive")
        self.assertEqual("Productive", config.get("name"))
        self.assertEqual("productive",
                         generate_campaign._offer_library_tenant())
        self.assertNotEqual(config.get("name"),
                            generate_campaign._offer_library_tenant())

    def test_a_config_dict_resolves_to_the_tenant_slug(self):
        from src import clients
        self.assertEqual(
            generate_campaign._offer_library_tenant(),
            generate_campaign._client_slug(clients.load("productive")),
            "the production (dict) path does not match the offers tenant, so "
            "the sequence-gate read is inert exactly as it was")

    def test_an_explicit_client_key_wins_over_the_display_name(self):
        self.assertEqual("acme", generate_campaign._client_slug(
            {"client": "acme", "name": "Totally Different Ltd"}))

    def test_another_clients_config_does_not_match_the_tenant(self):
        """THE GUARD MUST STILL DECLINE. Fixing the match must not make it
        match everything - that would apply Productive's approved ladder to a
        client that never approved it, which is the fault the guard exists for.
        """
        for config in ({"name": "Acme Corp"}, {"name": "Harbourline"},
                       {"client": "contactout", "name": "Productive"}):
            with self.subTest(config=config):
                self.assertNotEqual(
                    generate_campaign._offer_library_tenant(),
                    generate_campaign._client_slug(config))

    def test_an_unreadable_client_declines_rather_than_guessing(self):
        self.assertIsNone(generate_campaign._client_slug(None))
        self.assertIsNone(generate_campaign._client_slug({}))


class TheSequenceGateVerdictReachesTheRetryLoop(unittest.TestCase):
    """M7, and it is the branch's HEADLINE CLAIM asserted end to end.

    The unit tests above prove the tenant guard WOULD match. They do not prove
    the gate's failures reach `failures`, and that gap is exactly why mutation
    M7 - "the sequencegate verdict is no longer read in the retry loop" -
    survived a green suite twice: once against the original mismatched guard
    (where it was true in production) and once against the fixed one.

    So this drives `generate_campaign.generate` on the PRODUCTION shape - the
    config DICT, not the literal string - with copy that violates the offer's
    approved ladder, and asserts the refusal is named in `gate_rejections`.
    A caller whose copy the gate refuses must see it cost an attempt.
    """

    @staticmethod
    def _account():
        return {"company": "TestCorp", "domain": "testcorp.test",
                "persona": "champion", "segment": "productive",
                "sources": [{"text": "TestCorp opened a second office in "
                                     "Zagreb and is hiring.",
                             "url": "https://testcorp.test/news"}]}

    @staticmethod
    def _contacts():
        return [{"email": "jane@testcorp.test", "first_name": "Jane",
                 "last_name": "Doe", "title": "CEO",
                 "contact_key": "jane-doe",
                 "linkedin": "https://linkedin.test/in/janedoe"}]

    def _run(self, client):
        from tests.base import CampaignModel
        # Copy that says nothing about ANY rung of either approved ladder, so
        # `step_objectives` is the check that must speak. Long enough to clear
        # lint's 40-word floor, so the refusal cannot come from length.
        filler = (
            "Wanted to ask one thing about how the team keeps track of what "
            "is happening while the work is still open, because that is "
            "usually where the useful conversation sits and it tends to get "
            "decided late rather than early in my experience of this. %s")
        seqs = {k: filler % k for k in ("em1", "em2", "em3", "em4", "em5")}
        seqs.update({k: "A short note about the second office in Zagreb, "
                        "nothing more than that. %s" % k
                     for k in ("connect", "msg1", "msg2", "msg3", "msg4")})
        subs = {"A": "a question about tracking", "B": "b", "C": "c"}
        return generate_campaign.generate(
            client, self._account(), self._contacts(),
            model=CampaignModel((seqs, subs)), live=False)

    def test_the_gate_is_read_when_the_client_is_a_config_dict(self):
        """THE PRODUCTION SHAPE. `src/generate.py` always passes the dict."""
        from src import clients
        plan = self._run(clients.load("productive"))
        entry = plan["contacts"][0]
        rejections = " ".join(entry.get("gate_rejections") or ())
        self.assertIn(
            "sequencegate", rejections,
            "the sequence gate's verdict did not reach the retry loop on the "
            "DICT path, which is the only path production uses. "
            "held=%r rejections=%r"
            % (entry.get("held"), entry.get("gate_rejections")))

    def test_the_gate_is_read_when_the_client_is_a_slug_string(self):
        """The other caller shape, so neither branch can regress alone."""
        plan = self._run("productive")
        entry = plan["contacts"][0]
        self.assertIn("sequencegate",
                      " ".join(entry.get("gate_rejections") or ()))

    def test_the_refused_contact_stores_no_copy(self):
        """Decision 2: a draft that failed a gate is never a send candidate."""
        from src import clients
        entry = self._run(clients.load("productive"))["contacts"][0]
        self.assertEqual("copy_refused", entry.get("hold_kind"))
        self.assertEqual({}, entry.get("sequences"))
        self.assertEqual({}, entry.get("subjects"))

    def _run_missing(self, drop):
        """The same run with one required writer element withheld."""
        from src import clients
        from tests.base import CampaignModel
        filler = (
            "Wanted to ask one thing about how the team keeps track of what "
            "is happening while the work is still open, because that is "
            "usually where the useful conversation sits and it tends to get "
            "decided late rather than early in my experience of this. %s")
        seqs = {k: filler % k for k in ("em1", "em2", "em3", "em4", "em5")}
        seqs.update({k: "A short note about the second office in Zagreb. %s"
                        % k
                     for k in ("connect", "msg1", "msg2", "msg3", "msg4")})
        seqs.update({k: "ps for " + k for k in ("ps_em1", "ps_em3")})
        seqs.pop(drop, None)
        plan = generate_campaign.generate(
            clients.load("productive"), self._account(), self._contacts(),
            model=CampaignModel((seqs, {"A": "a question about tracking",
                                        "B": "b", "C": "c"})), live=False)
        return " ".join(plan["contacts"][0].get("gate_rejections") or ())

    def test_a_withheld_linkedin_message_costs_an_attempt(self):
        """M8. `missing_required` must reach `failures`, not just the result.

        Mutation M8 - "missing_required no longer reaches failures" - survived
        a green suite because every shortfall test asserted on
        `_content_shortfall` or `_campaign_validator` in isolation. Neither
        proves `generate_campaign`'s OWN harvest-time list is consumed, and
        that list is the one that refuses an element the writer returned
        empty.
        """
        self.assertIn("msg4", self._run_missing("msg4"),
                      "a withheld fifth LinkedIn message did not reach the "
                      "refusal list")

    def test_a_withheld_ps_costs_an_attempt(self):
        """The other half of `missing_required`, same reason.

        The P.S. is BLANKED IN THE WRITER'S ANSWER rather than dropped from
        the fixture, because `tests.base.writer_answer` now supplies a default
        P.S. when the sequences carry none - so omitting the key proves
        nothing about the empty case.
        """
        import json as _json
        from src import clients
        from tests.base import CampaignModel

        class _NoPS(CampaignModel):
            def complete(self, prompt, *a, **kw):
                out = super().complete(prompt, *a, **kw)
                if "write cold outreach" not in prompt.lower():
                    return out
                data = _json.loads(out)
                data["ps"] = {"em1": "", "em3": ""}
                return _json.dumps(data)

        filler = (
            "Wanted to ask one thing about how the team keeps track of what "
            "is happening while the work is still open, because that is "
            "usually where the useful conversation sits and it tends to get "
            "decided late rather than early in my experience of this. %s")
        seqs = {k: filler % k for k in ("em1", "em2", "em3", "em4", "em5")}
        seqs.update({k: "A short note about the second office in Zagreb. %s"
                        % k
                     for k in ("connect", "msg1", "msg2", "msg3", "msg4")})
        plan = generate_campaign.generate(
            clients.load("productive"), self._account(), self._contacts(),
            model=_NoPS((seqs, {"A": "a question about tracking",
                                "B": "b", "C": "c"})), live=False)
        rejections = " ".join(
            plan["contacts"][0].get("gate_rejections") or ())
        self.assertIn("P.S.", rejections,
                      "an empty required P.S. did not reach the refusal list")
        self.assertIn("em1", rejections)

    def test_another_clients_config_is_not_judged_by_this_ladder(self):
        """THE GUARD STILL DECLINES, which is the half that must not regress.

        `offers.py` is single-tenant and hands Productive's offer to every
        client, so without a working guard this ladder would refuse copy for a
        client that never approved it.
        """
        plan = self._run({"name": "Acme Corp", "sender": {"name": "Ivan"},
                          "product": {"capabilities": {}}})
        rejections = " ".join(
            plan["contacts"][0].get("gate_rejections") or ())
        self.assertNotIn("sequencegate step_objectives", rejections)


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


class TheRepetitionGateMeasuresWhatTheStepsSay(unittest.TestCase):
    """`_quality_of` compares BODIES across steps, not `subject + body`.

    Under one thread the subject is identical on every step by construction, so
    including it added a constant to all ten pairwise comparisons. This is the
    proof that removing it did NOT hollow the check out - which is the exact
    failure mode this repository's own `no_repetition/subjects` history warns
    about, where a "fix" made a check structurally incapable of firing.
    """

    def _reasons(self, bodies, subject="one shared subject"):
        stored = {k: {"channel": "email", "generated": True,
                      "subject": subject, "body": b}
                  for k, b in bodies.items()}
        rec = {"company": "Brightmoor Studio", "domain": "brightmoor.test",
               "contacts": [LI_CONTACT],
               "cadence": {generate.lint.contact_key(LI_CONTACT): stored}}
        return generate._quality_of(rec, LI_CONTACT, stored,
                                    sorted(bodies)[0], LI_CONFIG)

    #: Bodies must be LINT-CLEAN or they are not siblings at all.
    #: `_quality_of` excludes a stored step that fails lint - "a sibling that
    #: fails lint is not a sibling" - so a body under `lint.MIN_WORDS` (40)
    #: silently empties the comparison set and the gate cannot fire for a
    #: reason that has nothing to do with repetition. The first version of
    #: these tests did exactly that and reported a green "no collision", which
    #: is the check-that-cannot-fire shape they exist to rule out.
    A_LONG = (
        "Margin per project is visible while the work is still running, "
        "instead of arriving after the invoice is drafted and the month has "
        "already closed on the engagement. That timing is the whole "
        "difference, because a conversation about scope or team shape is "
        "only useful while there is still room to have it, and the numbers "
        "that would prompt it are the ones nobody sees until later.")
    B_SAME_ARGUMENT = (
        "Margin per project becomes visible while the work is running, not "
        "after the invoice is drafted once the month is closed. The timing "
        "is the difference that matters here, because a conversation about "
        "scope or team shape is only useful while there is still room to "
        "have it, and the numbers prompting it are the ones nobody sees "
        "until later in the engagement.")
    C_DIFFERENT_ARGUMENT = (
        "Deciding who is booked a sprint ahead is a short planning horizon "
        "when the clients on the other side expect dates they can rely on "
        "for months. Agencies working that way often find the commitment "
        "and the certainty pull against each other, and the place it shows "
        "first is usually a delivery promise nobody wanted to renegotiate.")

    def test_it_still_fires_on_two_steps_with_the_same_body(self):
        """POSITIVE CONTROL. Identical arguments must always collide."""
        self.assertTrue(
            self._reasons({"em1": self.A_LONG, "em2": self.A_LONG}),
            "identical bodies did not collide")

    def test_it_still_fires_when_the_bodies_genuinely_repeat(self):
        """POSITIVE CONTROL with different words and the same argument."""
        self.assertTrue(
            self._reasons({"em1": self.A_LONG,
                           "em2": self.B_SAME_ARGUMENT}),
            "a genuinely repetitive pair did not collide")

    def test_a_shared_subject_alone_does_not_collide_two_distinct_steps(self):
        """THE BIAS THIS REMOVES. Two steps that argue different things must
        not be refused because one thread gives them the same subject.
        """
        self.assertEqual(
            [], self._reasons({"em1": self.A_LONG,
                               "em2": self.C_DIFFERENT_ARGUMENT},
                              subject="brightmoor sprint ahead resourcing"),
            "a shared subject refused two steps that argue different things")

    #: THE PAIR THAT SITS IN THE WINDOW, and it has to be this one.
    #:
    #: M3 - "repetition gate back to `subject + body` siblings" - survived a
    #: green suite because the fixtures above are far enough apart that the
    #: subject cannot tip them: a test that passes under BOTH inputs proves
    #: nothing about which input is used. This is the real measured pair from
    #: `tests/test_generate.py` before it was rewritten, and its margin is the
    #: whole finding:
    #:
    #:     bodies only                       43.8%   clean
    #:     with the shared opener subject    50.0%   COLLISION
    #:
    #: One shared word from a constant, landing exactly on the threshold.
    NEAR_MISS_A = (
        "On 17 October Jesse asked to run the key against a realistic "
        "list of companies and our reply asked whether five thousand credits "
        "would do and then pivoted to booking a call. That question was never "
        "actually answered, which is the reason this stopped rather than "
        "anything about the price. The limit on that test key was around "
        "fifty credits, far too low to test anything real, and we never "
        "engaged the developer Jesse mentioned had the docs.")
    NEAR_MISS_B = (
        "The other loose end is the developer Jesse said was holding "
        "the API docs. Nobody here ever went to them, so the test stayed "
        "blocked at our end as much as yours. If I go straight to that "
        "developer with a key and the docs question, is there anything you "
        "would rather I did not do?")
    SHARED_SUBJECT = "friday capacity planning"

    def test_the_near_miss_pair_is_clean_on_bodies(self):
        """The pair measured at 43.8% must PASS - it is under the threshold.

        This is the test M3 kills: revert the siblings to `subject + body` and
        the shared opener subject takes this pair to 50.0% and it collides.
        """
        self.assertEqual(
            [], self._reasons({"em1": self.NEAR_MISS_A,
                               "em2": self.NEAR_MISS_B},
                              subject=self.SHARED_SUBJECT),
            "the 43.8% pair was refused, which means the constant subject is "
            "back in the comparison")

    def test_the_same_pair_still_collides_when_the_bodies_do_repeat(self):
        """The control beside it: the window is narrow, not absent. Replace
        one body with a restatement of the other and the gate fires.
        """
        self.assertTrue(
            self._reasons({"em1": self.NEAR_MISS_A,
                           "em2": self.NEAR_MISS_A + " Worth a look?"},
                          subject=self.SHARED_SUBJECT))


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
