"""The offer's `cta_link` reaches the prospect, and a sequence without it is refused.

THE DEFECT, MEASURED 2026-09-30. Not one of the five generated canary emails
contained a URL. `offer.cta_link` was declared in
`config/clients/productive-offers.yaml` (`https://productive.io/get-started/`)
and read by NOTHING except `src/copylint.py`, which only validates URLs that
are already present - `check_cta_links([])` returns a clean verdict for an
empty list, so the CTA rules passed vacuously on copy with no CTA at all.

`src/copyprompts.py` tells the writer "NEVER write a URL" and that rule is
CORRECT and stays: a model asked for a URL retypes it and gets it wrong
(measured 2026-09-25). So the link is CONFIG, appended by
`trailingcontent.compose` - the one composer that already owns the signature
and the opt-out - and verified on the COMPOSED output by
`sequencegate.check_cta`, which `bisonfactory._refuse_missing_cta` runs against
the exact projection `_ensure_leads` is about to write.

WHAT IS ASSERTED HERE, and why each one is a separate test rather than one
happy path:

  (a) an offer with a cta_link produces composed output containing it, exactly
      once per email that should carry it
  (b) NEGATIVE CONTROL: composed output missing the CTA is REFUSED
  (c) the injected URL is byte-identical to the config value - no model-typed
      URL, no trailing-slash drift
  (d) an offer with NO cta_link does not crash and injects nothing
  (e) the existing trailing-content order (body / signature / P.S. / opt-out)
      is preserved, asserted on the FULL composed string
  (f) no unresolved placeholder is introduced

NO PROVIDER IS CALLED AND NO STORE FILE IS WRITTEN. Every test here works on
dicts and strings; the one that drives `bisonfactory._refuse_missing_cta`
builds its plan by hand and the function raises before any transport exists.
"""
import unittest
from unittest import mock

from src import bisonfactory, copylint, offers, optout, sequencegate
from src import trailingcontent


LINK = "https://productive.io/get-started/"

#: An offer record in the shape `src/offers.py` loads one. Only the two fields
#: this feature reads are stated; a fuller fixture would be inventing an offer,
#: which `offers.py`'s own docstring forbids.
OFFER_WITH_LINK = {"cta_link": LINK, "thread_reply_rungs": [2, 4]}
OFFER_NO_LINK = {"capability": "billing"}

SIG = "Anna Kowalski\nHead of Delivery, Productive"
BODY = "Margin on a fixed scope project is usually invisible until it closes."
PS = "Worth a look either way."

#: Five steps, threaded the way the productive cadence is: em2 replies inside
#: em1's thread and em4 inside em3's.
SEQUENCE = [{"step_key": "em1", "thread_reply": False},
            {"step_key": "em2", "thread_reply": True},
            {"step_key": "em3", "thread_reply": False},
            {"step_key": "em4", "thread_reply": True},
            {"step_key": "em5", "thread_reply": False}]

THREADS = {"em1": "em1", "em2": "em1", "em3": "em3",
           "em4": "em3", "em5": "em5"}


def _lead(steps=("em1", "em2", "em3", "em4", "em5")):
    return {"record_id": "rec-1", "contact_key": "c-1",
            "persona": "economic_buyer",
            "copy": [{"step_key": key, "subject": "Subject %s" % key,
                      "body": "%s (%s)" % (BODY, key), "ps": ""}
                     for key in steps]}


def _variables(lead, offer, sequence=SEQUENCE):
    """The projection `_ensure_leads` writes, as {name: value}.

    `_offer_for` is patched rather than the offer library edited: this asserts
    what `_variables_for` does with an offer, not what the operator's file
    currently says. Test (c) below is the one that pins the real config value.
    """
    with mock.patch.object(bisonfactory, "_offer_for",
                           return_value=("OFFER-TEST", offer)):
        held = bisonfactory._variables_for(
            lead, {"client": "productive"}, sequence=sequence,
            sender={"name": "Anna Kowalski", "role": "Head of Delivery",
                    "company": "Productive"})
    return {v["name"]: v["value"] for v in held}


# ------------------------------------------------- (a) it is actually there

class TestTheLinkIsInTheComposedOutput(unittest.TestCase):
    """(a) An offer with a cta_link produces composed output containing it,
    exactly once per email that should carry it."""

    def test_compose_appends_the_link(self):
        out = trailingcontent.compose(BODY, ps=PS, signature=SIG,
                                      cta_link=LINK)
        self.assertIn(LINK, out)

    def test_compose_appends_it_exactly_once(self):
        """COUNT, never `in`. An `in` check passes for one occurrence or
        three, and three URLs in one email is the defect's mirror image."""
        out = trailingcontent.compose(BODY, ps=PS, signature=SIG,
                                      cta_link=LINK)
        self.assertEqual(out.count(LINK), 1)

    def test_the_projection_carries_it_on_every_thread_starter(self):
        """The STAGED variables - not a re-composition - carry the link.

        `_variables_for` is what `_ensure_leads` writes to EmailBison, so this
        is the string a prospect would read.
        """
        held = _variables(_lead(), OFFER_WITH_LINK)
        for position in (1, 3, 5):
            body = held["body_%d" % position]
            self.assertEqual(body.count(LINK), 1,
                             "body_%d must carry the CTA exactly once, "
                             "carried it %d time(s)"
                             % (position, body.count(LINK)))

    def test_the_projection_keeps_it_off_every_thread_reply(self):
        """em2 and em4 reply inside a thread. A reply already carrying a
        signature and a compliance footer reads as bulk mail with a link
        under it, and the offer library records the same decision as
        `thread_reply_rungs: [2, 4]` (operator, Zvonimir, 2026-09-30)."""
        held = _variables(_lead(), OFFER_WITH_LINK)
        for position in (2, 4):
            self.assertEqual(held["body_%d" % position].count(LINK), 0,
                             "body_%d is a thread reply and must carry no "
                             "CTA link" % position)

    def test_a_single_step_lead_carries_it(self):
        """A one-step sequence opens its own thread, so it gets the link."""
        held = _variables(_lead(steps=("em1",)), OFFER_WITH_LINK,
                          sequence=SEQUENCE[:1])
        self.assertEqual(held["body"].count(LINK), 1)

    def test_the_gate_passes_what_the_projection_produced(self):
        """End to end: the composed output the staging path produces is
        accepted by the gate that guards it."""
        held = _variables(_lead(), OFFER_WITH_LINK)
        composed = {"em%d" % n: held["body_%d" % n] for n in range(1, 6)}
        result = sequencegate.check_cta(composed, OFFER_WITH_LINK,
                                        threads=THREADS)
        self.assertTrue(result["passed"], result["failures"])


# ----------------------------------------- (b) the negative control, refused

class TestTheGateRefusesCopyWithNoCTA(unittest.TestCase):
    """(b) NEGATIVE CONTROL: composed output missing the CTA is REFUSED."""

    def test_a_starter_without_the_link_is_refused_by_name(self):
        composed = {"em1": BODY, "em2": BODY, "em3": BODY + "\n\n" + LINK,
                    "em4": BODY, "em5": BODY + "\n\n" + LINK}
        result = sequencegate.check_cta(composed, OFFER_WITH_LINK,
                                        threads=THREADS)
        self.assertFalse(result["passed"])
        self.assertEqual([f["step"] for f in result["failures"]], ["em1"])
        self.assertEqual(result["failures"][0]["check"], "cta_present")

    def test_no_step_carrying_it_is_refused(self):
        composed = {"em%d" % n: BODY for n in range(1, 6)}
        result = sequencegate.check_cta(composed, OFFER_WITH_LINK,
                                        threads=THREADS)
        self.assertFalse(result["passed"])
        self.assertEqual({f["step"] for f in result["failures"]},
                         {"em1", "em3", "em5"})

    def test_absent_composed_output_is_refused_not_passed(self):
        """FAIL CLOSED. The commonest way to ship this defect is for the
        composing path to stop passing the link through; a gate handed
        nothing must refuse rather than go quiet."""
        for empty in (None, {}):
            result = sequencegate.check_cta(empty, OFFER_WITH_LINK,
                                            threads=THREADS)
            self.assertFalse(result["passed"],
                             "composed=%r must be refused" % (empty,))
            self.assertEqual(result["failures"][0]["check"], "cta_present")

    def test_a_duplicate_link_is_refused(self):
        """EXACTLY ONE CTA. Two copies of the ask in one email is not the
        same defect but it is refused by the same rule."""
        composed = dict.fromkeys(("em2", "em4"), BODY)
        for key in ("em1", "em3", "em5"):
            composed[key] = "%s\n\n%s\n\n%s" % (BODY, LINK, LINK)
        result = sequencegate.check_cta(composed, OFFER_WITH_LINK,
                                        threads=THREADS)
        self.assertFalse(result["passed"])
        self.assertEqual({f["step"] for f in result["failures"]},
                         {"em1", "em3", "em5"})

    def test_a_reply_carrying_the_link_is_refused(self):
        composed = {"em1": BODY + "\n\n" + LINK, "em2": BODY + "\n\n" + LINK,
                    "em3": BODY + "\n\n" + LINK, "em4": BODY,
                    "em5": BODY + "\n\n" + LINK}
        result = sequencegate.check_cta(composed, OFFER_WITH_LINK,
                                        threads=THREADS)
        self.assertFalse(result["passed"])
        self.assertEqual([f["step"] for f in result["failures"]], ["em2"])

    def test_the_staging_gate_raises_when_the_composer_is_broken(self):
        """THE REAL NEGATIVE CONTROL: break the injection, not the fixture.

        `trailingcontent.append_cta` is replaced with a no-op, which is
        exactly what the estate looked like before this change. The staging
        gate must refuse, and it must refuse before any provider object
        exists - `_refuse_missing_cta` is called with no transport, no
        workspace and no campaign id.
        """
        plan = {"leads": [_lead()], "provider_sequence": SEQUENCE,
                "sender": {"name": "Anna Kowalski", "company": "Productive"}}
        report = {"client": "productive"}
        real = trailingcontent.append_cta
        try:
            trailingcontent.append_cta = lambda body, cta_link: body or ""
            with mock.patch.object(bisonfactory, "_offer_for",
                                   return_value=("OFFER-TEST",
                                                 OFFER_WITH_LINK)):
                with self.assertRaises(bisonfactory.FactoryRefused) as caught:
                    bisonfactory._refuse_missing_cta(
                        {"client": "productive"}, plan, [], report)
        finally:
            trailingcontent.append_cta = real
        self.assertIn("CTA link", str(caught.exception))
        self.assertFalse(report["cta_gate"]["passed"])

    def test_the_staging_gate_passes_when_the_composer_works(self):
        """The same call, unbroken, does not raise - so the test above
        failed for the reason it names and not because the fixture is
        unstageable."""
        plan = {"leads": [_lead()], "provider_sequence": SEQUENCE,
                "sender": {"name": "Anna Kowalski", "company": "Productive"}}
        report = {"client": "productive"}
        with mock.patch.object(bisonfactory, "_offer_for",
                               return_value=("OFFER-TEST", OFFER_WITH_LINK)):
            bisonfactory._refuse_missing_cta(
                {"client": "productive"}, plan, [], report)
        self.assertTrue(report["cta_gate"]["passed"])


# ------------------------------- the thread map is an input, not an option

class TestTheThreadMapIsRequired(unittest.TestCase):
    """NAMED REGRESSION of the fail-open default found 2026-09-30.

    The first version of `check_cta` defaulted with
    `starter = (threads or {}).get(step, step) == step`. That is strict for
    the PRESENCE half - every step must then carry the link - and LAX for the
    PROHIBITION half, because `not starter` can never be true, so the reply
    rule could not fire at all. The two halves of one guard disagreed about
    what the default meant.

    Reproduced exactly as reported: with the map, a reply carrying the link is
    refused; without it, the same sequence passed. Latent rather than live -
    `bisonfactory._refuse_missing_cta` does pass the map - but a guard whose
    safety depends on a caller remembering an optional argument is a guard the
    next caller will bypass.
    """

    #: The reported reproduction, verbatim.
    REPRO = {"em1": BODY + "\n\n" + LINK, "em2": BODY + "\n\n" + LINK}

    def test_with_the_map_a_reply_carrying_the_link_is_refused(self):
        """The control half of the reproduction: this always worked."""
        result = sequencegate.check_cta(
            self.REPRO, OFFER_WITH_LINK,
            threads={"em1": "em1", "em2": "em1"})
        self.assertFalse(result["passed"])
        self.assertEqual([f["step"] for f in result["failures"]], ["em2"])

    def test_without_the_map_the_same_reply_is_still_refused(self):
        """THE HOLE. `threads=None` returned passed=True on the identical
        composed output. It must now refuse."""
        result = sequencegate.check_cta(self.REPRO, OFFER_WITH_LINK)
        self.assertFalse(result["passed"],
                         "threads=None must not pass a reply carrying the CTA")

    def test_without_the_map_the_refusal_names_the_missing_input(self):
        """It refuses on the missing INPUT, not by guessing which step is a
        reply - so an operator is told to pass the map rather than to rewrite
        correct copy."""
        result = sequencegate.check_cta(self.REPRO, OFFER_WITH_LINK)
        self.assertEqual([f["step"] for f in result["failures"]], ["sequence"])
        self.assertIn("thread map", result["failures"][0]["why"])

    def test_an_empty_map_is_the_same_as_none(self):
        """`_thread_map` returns `{}` for a plan with no provider sequence.
        An empty classifier classifies nothing."""
        result = sequencegate.check_cta(self.REPRO, OFFER_WITH_LINK,
                                        threads={})
        self.assertFalse(result["passed"])
        self.assertEqual([f["step"] for f in result["failures"]], ["sequence"])

    def test_a_perfect_sequence_without_the_map_is_also_refused(self):
        """FAIL CLOSED MEANS FAIL CLOSED. Copy that would pass with the map
        is still refused without it: the gate is not allowed to enforce the
        knowable subset of its rule silently."""
        composed = {"em1": BODY + "\n\n" + LINK, "em2": BODY,
                    "em3": BODY + "\n\n" + LINK, "em4": BODY,
                    "em5": BODY + "\n\n" + LINK}
        self.assertTrue(sequencegate.check_cta(
            composed, OFFER_WITH_LINK, threads=THREADS)["passed"])
        self.assertFalse(sequencegate.check_cta(
            composed, OFFER_WITH_LINK)["passed"])

    def test_a_step_missing_from_the_map_is_refused_by_name(self):
        """THE SAME HOLE ONE LEVEL DOWN. `threads.get(step, step) == step`
        read an unmapped step as a starter, so a reply the map happened not to
        name was exempt from the prohibition. Reported and reproduced:
        `threads={'em1': 'em1'}` passed the identical composed output."""
        result = sequencegate.check_cta(self.REPRO, OFFER_WITH_LINK,
                                        threads={"em1": "em1"})
        self.assertFalse(result["passed"])
        self.assertEqual([f["step"] for f in result["failures"]], ["em2"])
        self.assertIn("not in the thread map",
                      result["failures"][0]["why"])

    def test_an_unmapped_step_is_refused_even_carrying_no_link(self):
        """It is refused for being unclassifiable, not for what it carries -
        otherwise the refusal would depend on the very thing that cannot be
        decided."""
        result = sequencegate.check_cta(
            {"em1": BODY + "\n\n" + LINK, "em2": BODY}, OFFER_WITH_LINK,
            threads={"em1": "em1"})
        self.assertFalse(result["passed"])
        self.assertEqual([f["step"] for f in result["failures"]], ["em2"])

    def test_an_offer_with_no_link_still_needs_no_map(self):
        """The early return for an offer declaring no CTA sits ABOVE the
        thread-map requirement: there is nothing to classify, and requiring an
        input for a rule that does not apply would refuse every capability
        offer in the library."""
        result = sequencegate.check_cta({"em1": BODY}, OFFER_NO_LINK)
        self.assertTrue(result["passed"])

    def test_the_production_path_supplies_the_map(self):
        """The reason this was latent rather than live, pinned so it stays
        that way: `_thread_map` answers for the plan and
        `_refuse_missing_cta` hands it over."""
        plan = {"provider_sequence": SEQUENCE}
        self.assertEqual(bisonfactory._thread_map(plan), THREADS)

    def test_an_unnamed_projection_node_is_not_keyed_under_none(self):
        """FOUND BY THIS FIX, 2026-09-30, across 28 staging tests.

        `sequenceplan.derive_bison_sequence` writes `step_key` and
        `thread_reply` together or writes NEITHER. `_thread_map` keyed an
        unnamed node under `None`, and the refusal message then rendered the
        map's keys with `sorted()` and raised
        `TypeError: expected str instance, NoneType found` - a diagnostic
        that crashed the gate instead of refusing through it.
        """
        plan = {"provider_sequence": [{"order": 1, "email_subject": "s"},
                                      {"order": 2, "email_subject": "s"}]}
        self.assertEqual(bisonfactory._thread_map(plan), {})

    def test_the_refusal_message_survives_a_non_string_key(self):
        """A gate must refuse, not raise. Even handed a map this ill-formed,
        `check_cta` returns a verdict."""
        result = sequencegate.check_cta(
            {"em1": BODY}, OFFER_WITH_LINK, threads={None: None, 2: 2})
        self.assertFalse(result["passed"])
        self.assertEqual([f["step"] for f in result["failures"]], ["em1"])

    def test_an_unnamed_projection_means_no_replies_not_no_information(self):
        """The counterpart, and the reason the fix is not "refuse harder".

        A projection naming no step declares no `thread_reply` either, so
        every step is its own conversation - which is exactly how
        `_variables_for` composes it. The staging gate reads that as one
        thread per step and passes copy that carries the link on all of them;
        it does not refuse for an absence that is really a statement.
        """
        unnamed = [{"order": n, "email_subject": "s"} for n in range(1, 6)]
        plan = {"leads": [_lead()], "provider_sequence": unnamed,
                "sender": {"name": "Anna Kowalski", "company": "Productive"}}
        report = {"client": "productive"}
        with mock.patch.object(bisonfactory, "_offer_for",
                               return_value=("OFFER-TEST", OFFER_WITH_LINK)):
            bisonfactory._refuse_missing_cta(
                {"client": "productive"}, plan, [], report)
        self.assertTrue(report["cta_gate"]["passed"])
        # And it is not passing vacuously: every step really carries the link.
        self.assertEqual(
            {f["step"] for f in report["cta_gate"]["leads"][0]["failures"]},
            set())

    def test_a_partly_named_projection_still_refuses_the_unnamed_steps(self):
        """The ambiguous case stays refused: some nodes named and some not is
        a malformed projection, not a non-threaded one."""
        partial = [{"order": 1, "step_key": "em1", "thread_reply": False},
                   {"order": 2, "email_subject": "s"},
                   {"order": 3, "step_key": "em3", "thread_reply": False},
                   {"order": 4, "email_subject": "s"},
                   {"order": 5, "step_key": "em5", "thread_reply": False}]
        plan = {"leads": [_lead()], "provider_sequence": partial,
                "sender": {"name": "Anna Kowalski", "company": "Productive"}}
        report = {"client": "productive"}
        with mock.patch.object(bisonfactory, "_offer_for",
                               return_value=("OFFER-TEST", OFFER_WITH_LINK)):
            with self.assertRaises(bisonfactory.FactoryRefused):
                bisonfactory._refuse_missing_cta(
                    {"client": "productive"}, plan, [], report)
        self.assertEqual(
            {f["step"] for f in report["cta_gate"]["leads"][0]["failures"]},
            {"em2", "em4"})


# ------------------------------------------- (c) byte-identical to the config

class TestTheURLIsTheConfigValue(unittest.TestCase):
    """(c) The injected URL is byte-identical to the config value."""

    def test_the_offer_library_declares_it(self):
        offer = offers.load()["OFFER-A-ECONOMIC-BUYER"]
        self.assertEqual(offer["cta_link"], LINK)

    def test_both_composed_offers_declare_the_same_one(self):
        """`the single CTA is https://productive.io/get-started/` - the offer
        library's own stamp, 2026-09-27."""
        loaded = offers.load()
        self.assertEqual(loaded["OFFER-A-ECONOMIC-BUYER"]["cta_link"],
                         loaded["OFFER-B-OPERATIONS"]["cta_link"])

    def test_the_composed_body_carries_the_config_value_byte_for_byte(self):
        """No model typed this. Read the file, compose, and require the exact
        bytes - a substring test would pass for a link with a query string
        bolted on."""
        declared = offers.load()["OFFER-A-ECONOMIC-BUYER"]["cta_link"]
        out = trailingcontent.compose(BODY, ps=PS, signature=SIG,
                                      cta_link=declared)
        urls = copylint.extract_urls(out)
        self.assertEqual(urls, [declared])

    def test_no_trailing_slash_drift(self):
        """The composer copies the string. It does not add, remove or
        normalise a trailing slash, which is the commonest way a retyped URL
        differs from the licensed one."""
        for variant in (LINK, LINK.rstrip("/")):
            out = trailingcontent.compose(BODY, cta_link=variant)
            self.assertEqual(copylint.extract_urls(out), [variant])

    def test_the_composed_link_is_on_copylints_allowlist(self):
        """The allowlist is an allowlist of exactly one (operator,
        2026-09-26). What the composer emits must be on it."""
        declared = offers.load()["OFFER-A-ECONOMIC-BUYER"]["cta_link"]
        out = trailingcontent.compose(BODY, ps=PS, signature=SIG,
                                      cta_link=declared)
        verdict = copylint.check_cta_links(copylint.extract_urls(out),
                                           resolve=False)
        self.assertEqual(verdict["not_allowlisted"], [])
        self.assertEqual(verdict["allowlisted"], [declared])


# ------------------------------------------------ (d) an offer with no link

class TestAnOfferWithNoLink(unittest.TestCase):
    """(d) An offer with NO cta_link does not crash and injects nothing."""

    def test_compose_without_a_link_is_unchanged(self):
        with_arg = trailingcontent.compose(BODY, ps=PS, signature=SIG,
                                           cta_link=None)
        without = trailingcontent.compose(BODY, ps=PS, signature=SIG)
        self.assertEqual(with_arg, without)

    def test_an_empty_string_link_injects_nothing(self):
        out = trailingcontent.compose(BODY, ps=PS, signature=SIG, cta_link="")
        self.assertEqual(copylint.extract_urls(out), [])

    def test_the_projection_carries_no_url(self):
        held = _variables(_lead(), OFFER_NO_LINK)
        for position in range(1, 6):
            self.assertEqual(
                copylint.extract_urls(held["body_%d" % position]), [])

    def test_no_offer_at_all_does_not_crash(self):
        held = _variables(_lead(), None)
        self.assertEqual(copylint.extract_urls(held["body_1"]), [])

    def test_the_gate_passes_an_offer_declaring_none(self):
        """Nothing to enforce is not the same as nothing checked, and this
        gate must not invent a link for an offer that declares none."""
        for offer in (OFFER_NO_LINK, {}, None):
            result = sequencegate.check_cta({"em1": BODY}, offer)
            self.assertTrue(result["passed"])
            self.assertIsNone(result["cta_link"])

    def test_an_empty_body_is_not_turned_into_a_bare_url(self):
        """An email consisting of one URL is worse than the defect. The
        empty body is refused upstream and this must not disguise it."""
        self.assertEqual(trailingcontent.append_cta("", LINK), "")


# ------------------------------------------------- (e) the order is preserved

class TestTheOrderIsPreserved(unittest.TestCase):
    """(e) body / signature / P.S. / opt-out is preserved, asserted on the
    FULL composed string rather than on four `assertIn`s."""

    def test_the_full_string_without_a_link_is_exactly_as_before(self):
        self.assertEqual(
            trailingcontent.compose(BODY, ps=PS, signature=SIG),
            "%s\n\n%s\n\nP.S. %s\n\n%s"
            % (BODY, SIG, PS, optout.OPT_OUT_LINE))

    def test_the_full_string_with_a_link_places_it_above_the_sign_off(self):
        """The link is part of the ASK, so it sits above the signature: a
        reader who has reached the sign-off has finished reading. Below the
        opt-out it would read as footer boilerplate."""
        self.assertEqual(
            trailingcontent.compose(BODY, ps=PS, signature=SIG,
                                    cta_link=LINK),
            "%s\n\n%s\n\n%s\n\nP.S. %s\n\n%s"
            % (BODY, LINK, SIG, PS, optout.OPT_OUT_LINE))

    def test_the_relative_order_of_the_other_four_is_unchanged(self):
        out = trailingcontent.compose(BODY, ps=PS, signature=SIG,
                                      cta_link=LINK)
        self.assertLess(out.index(BODY), out.index(LINK))
        self.assertLess(out.index(LINK), out.index(SIG))
        self.assertLess(out.index(SIG), out.index("P.S. " + PS))
        self.assertLess(out.index("P.S. " + PS),
                        out.index(optout.OPT_OUT_LINE))

    def test_the_link_does_not_duplicate_the_ps_or_the_opt_out(self):
        out = trailingcontent.compose(BODY, ps=PS, signature=SIG,
                                      cta_link=LINK)
        self.assertEqual(out.count("P.S."), 1)
        self.assertEqual(out.count(optout.OPT_OUT_LINE), 1)
        self.assertEqual(out.count(SIG), 1)

    def test_the_order_holds_in_the_projection_too(self):
        """The two surfaces compose through one function, so the staged body
        is the same string the renderer would produce."""
        held = _variables(_lead(steps=("em1",)), OFFER_WITH_LINK,
                          sequence=SEQUENCE[:1])
        body = held["body"]
        self.assertLess(body.index(LINK), body.index("Anna Kowalski"))
        self.assertLess(body.index("Anna Kowalski"),
                        body.index(optout.OPT_OUT_LINE))


# ------------------------------------- (f) no unresolved placeholder appears

class TestNoUnresolvedPlaceholder(unittest.TestCase):
    """(f) No unresolved placeholder is introduced.

    `copylint.UNRENDERED_RE` is the repository's own definition of a merge
    field that survived into a body, and `EMPTY_SENTENCE_RES` of a variable
    that rendered to nothing. Reusing them rather than writing a second
    opinion: two definitions of "unrendered" would drift.
    """

    def test_the_composed_body_carries_no_merge_field(self):
        out = trailingcontent.compose(BODY, ps=PS, signature=SIG,
                                      cta_link=LINK)
        self.assertIsNone(copylint.UNRENDERED_RE.search(out))

    def test_the_composed_body_carries_no_empty_sentence(self):
        out = trailingcontent.compose(BODY, ps=PS, signature=SIG,
                                      cta_link=LINK)
        for rule in copylint.EMPTY_SENTENCE_RES:
            self.assertIsNone(rule.search(out), rule.pattern)

    def test_every_staged_body_is_clean(self):
        held = _variables(_lead(), OFFER_WITH_LINK)
        for name, value in sorted(held.items()):
            if not name.startswith("body"):
                continue
            self.assertIsNone(copylint.UNRENDERED_RE.search(value), name)
            for rule in copylint.EMPTY_SENTENCE_RES:
                self.assertIsNone(rule.search(value),
                                  "%s: %s" % (name, rule.pattern))


if __name__ == "__main__":
    unittest.main()
