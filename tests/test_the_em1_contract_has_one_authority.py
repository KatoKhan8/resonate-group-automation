"""TASK-976 + the em1 contract: one authority, one counter, three holds.

WRITTEN AFTER THE CODE AND SAYING SO. Every assertion here was executed
against the real modules before it was written down, and two of them changed
what the code does rather than the other way round: `lint.is_reply_step` was
written because giving em1 a band of its own made `check` report
`reply_too_long` for an em1, and `_strip_bare_name_signature` only recognises
the operator's shape because the first version of the exemplar builder
replaced his URL with a placeholder and the count moved by 7.

UPDATED BY THE MERGE OF MASTER 2bf7b8a5, and the first of those two is no
longer true of the code: `is_reply_step` existed to keep em1 out of a reply
band, and TASK-943 abolished the reply band itself, so the helper went with
it. The PROPERTY it was written for is still asserted - an over-long em1 is
refused by em1's own bounds and never as a reply - and it is asserted at the
gate rather than on the helper. The operator's em1 band of (90, 120, 140)
survives the merge unchanged; where it LIVES does not. It is
`skills.cold_email_writing.WORD_CONTRACT` now, which `lint` re-exports as
`lint.STEP_WORD_CONTRACT`, and `lint.WORD_CONTRACT` is gone.

NO NAME IN THIS FILE. The PII scan below holds SHA-256 hashes of the
identifiers in the operator's source messages, because this repository
reintroduced the names it was keeping out three times in one night - once in
an anonymiser's own metadata and once in a test's list of forbidden strings.
A hash cannot reintroduce anything, and `test_the_scan_can_fail` proves the
scan is watching.

Nothing here binds a port, so it runs while a full suite holds the machine
lock.
"""
import hashlib
import os
import re
import unittest

from src import claims, copystages, eligibility, generate, holdreasons, lint
from src import offers, sequencegate
from src.skills import cold_email_writing as writer


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXEMPLAR_DIR = os.path.join(ROOT, "prompts", "exemplars")

#: SHA-256 of every identifier in the 17 source messages - the recipient
#: companies from the filenames and every recipient name and address in the
#: headers. Lower-cased before hashing. Generated once from the source; the
#: plaintext is not in this repository and is not in this file.
FORBIDDEN_HASHES = frozenset({
    "0f2a693e93e2ed7008feb5b7714bbab236e3907e64188199e3be1ae367f49c40",
    "120ec9d1eb2e5824664cef7713317244b31af5d0da91bd9dc2679cdce4cc5fed",
    "1258ef0928f07ab7cb7fbf6848f8dc7deba1b2daad2ba788a7b7c40c46b0bd8a",
    "15603e95db66e399d9adf8a9da1099addc79c00a2b78b269aab276a2f22969f6",
    "18c3ab71f4c51c1e2d302bc02eb5dc1bfd266cbe61c5ff4c2129dcd7480ab9ea",
    "1f31d3683e2ca4225d78067911b1f864f0bb0e99fba6c3b6f7b10d924da4b748",
    "1f6cb1e293bfc5d798b222e0e10bfcd10d5595d49b6ff2a705b279f37eb4c152",
    "23fc951e4917731273340d66594855bccc3bc14b8854616ec64ed54a8405df52",
    "2c49150bd8c72797d84a38cc035d2e1ec5d9d3e3aee63557b78b44162995847c",
    "2ea11bbb467e73f754431b560a0d7267dff8d1282f1c2b9ad979f09331a1a4aa",
    "39aba32392c88af599e88a38f9e365b4233610bacaf1944ae2d44248c0c085c9",
    "3cd2f0be8badccb0167819e7cda3aedc6a8a4c870038330806452ab4e0d6bb47",
    "3dbdccedcc9f1bb251b3c046eb5af2eb30d3edbca2a3da317365fb52cac7c4c3",
    "43c32ab1a18c27833dc4da8c95a86877b15d0288a0d8706803b8d30f8c3e99ea",
    "455d6d2d89675a2d13039f75e8fdfa726f1767b3390250a28264ee4c5064fbe1",
    "4563cefa4b9392ba2e8883820048306f0f5b9a2c6819bdfe5d0c7cc6eb59998f",
    "48a989d67ec878f3456782ea14ffba5f965b5e1b73347a294a3d949ad3bfa33e",
    "4a22da4dfcc9e4147b95ac4a763f0a9f9a7711faa4693f1647b5c348bab0250e",
    "4d7f6466cae8d43b8fa431dc0cf410a6e147a0bda90e7393e04d5ebff6e37443",
    "59fc812142f22e9cda67696ef332167f863d559c742f4690bdfda216e9f1c0bc",
    "5c034864a4f99555012d1c9e7cf927ed0a3ea87b288fa02d7f4b498d5a525c97",
    "6212a8f36e07c4238142587afbc423f39dd9011e50ec883f1b70bac60623b6d3",
    "6830ae2854afffd179e90799ceeb6cc821c8afcc5bf2c9ac70142487fce4926b",
    "690815f73168389dd8667333a96eb15668dac66f4e54608094ef1306857db611",
    "69d02880ad73ddf1813af46aff1920caafd4950895653682a7c9ff03ca60d0d9",
    "7522d0cfe10ee4be56014089e08ef661aaffffd18640d9d9ec7d780ced5978b9",
    "7bcce53e8b20f2365fd91f3578e7ec84b8a9a39018f7808d87beecdfb1c4e762",
    "7be3694994e03fdcc82ee42b942bc9b4cb13acb512f26198ed32e1a5db9aad8f",
    "7cb58e388c80058ebf47787e05eba4fc13aeb8c40ed76bfc9a763dbce66bd43a",
    "7ce6fb2138746d68583f3863a7f5833f8610cd6cd5138d1d761783c4d29fe666",
    "7daf44adc4ecd05896dd2881bf54836655a949dd9623f50acf0603e9aff3ae9d",
    "8da213d67cbaee94d666ab36a3594481ecc983ff2c3ef50ea71b8b985745e3ee",
    "99d4a51ac2e89863399fd9aafb59b60aa10a7d0e5b2f4fe0b3253b6058e0f67b",
    "9a6950d9e88e1a919e9f6ca4efe27e01c0f6756fb6fa81b8953e7074c4941c65",
    "a9711bbcb0a055c161c48a4ea8f9d0b2572e2864994ff5683cef4d93b4f5f416",
    "aca461905172ced77d7fa6156cdc683f55b042d6f1c8dbb4017938d8c6dbc966",
    "bfdad43346e3b598e6e018d759c279b3db6e6d7a60c2059c27bbc0816e308e20",
    "c72464dc0a8c8677b004c79067c1e14f6bbd872bd02f73c0f5ca89e80a641831",
    "cd4b1878b84383c778480f9a45d35f65c42f028f99911b8c4629b37489390c8e",
    "ef27078b52ee9a49edf7b5651bbc27fd94f4bb4a51fd5e32dd1fe30c80ab635e",
    "efcb91256e34064405107f7d94a7652e3e8fe6e11c3d031f594150407fcf1625",
})


def _tokens(text):
    """Word-ish tokens, lower-cased, the way a name would appear."""
    return {t.lower() for t in re.findall(r"[\w'À-ž-]{3,}", text)}


def _hits(text):
    """Which forbidden identifiers appear in `text`. Returns the HASHES,
    never a name, so a failure message leaks nothing either."""
    return sorted(h for h in (hashlib.sha256(t.encode("utf-8")).hexdigest()
                              for t in _tokens(text))
                  if h in FORBIDDEN_HASHES)


def _swap_needles(new):
    """Replace the needle set and return the old one. Exists only for
    `test_the_scan_can_fail`, which proves `_hits` is watching."""
    global FORBIDDEN_HASHES
    old = FORBIDDEN_HASHES
    FORBIDDEN_HASHES = new
    return old


class TheEm1ContractHasOneAuthority(unittest.TestCase):
    """A21. One dict holds the number; everything else derives or
    cross-checks against it.

    WHERE THAT DICT LIVES CHANGED WITH THE MERGE OF MASTER 2bf7b8a5. It was
    `lint.WORD_CONTRACT` on this branch; it is
    `skills.cold_email_writing.WORD_CONTRACT` now, which `lint` re-exports
    as `lint.STEP_WORD_CONTRACT` - the SAME OBJECT, asserted below, not a
    copy. TASK-943 and this branch reached the same conclusion from
    opposite ends and only one of them can hold the dict; the operator's
    em1 BAND is this branch's and the STRUCTURE is master's.
    """

    def test_the_contract_is_the_operators_band(self):
        self.assertEqual(writer.WORD_CONTRACT["em1"], (90, 120, 140))

    def test_the_gate_holds_the_mapping_itself_and_not_a_copy(self):
        # THE STRUCTURE TASK-943 MERGED FOR. `is`, not `==`: a second dict
        # with equal contents is exactly the defect both changes exist to
        # end, and it would satisfy an equality.
        self.assertIs(lint.STEP_WORD_CONTRACT, writer.WORD_CONTRACT)
        self.assertFalse(hasattr(lint, "WORD_CONTRACT"),
                         "lint.WORD_CONTRACT is back as a second name "
                         "for the one authority")

    def test_the_other_steps_are_masters_contract(self):
        # The operator changed em1 and nothing else, so the other four are
        # whatever master had: 45-90 for the two replies and em5, 60-90 for
        # em3. They are NOT this branch's 15/60 and 40/180 any more - that
        # reply band was abolished on 2026-10-02 and the abolition is the
        # thing master merged.
        self.assertEqual(writer.WORD_CONTRACT["em2"], (45, 60, 90))
        self.assertEqual(writer.WORD_CONTRACT["em4"], (45, 60, 90))
        self.assertEqual(writer.WORD_CONTRACT["em3"], (60, 75, 90))
        self.assertEqual(writer.WORD_CONTRACT["em5"], (45, 65, 90))

    def test_word_range_derives_from_the_contract(self):
        for step, (low, _t, high) in writer.WORD_CONTRACT.items():
            self.assertEqual(writer.word_range(step), (low, high), step)

    def test_an_unknown_step_gets_the_strict_global_floor(self):
        # The contract says NOTHING about a step it does not name, which is
        # not the same as "anything goes": the caller keeps `MIN_WORDS` and
        # `MAX_WORDS`, the stricter floor. Asserted as an EFFECT at the
        # gate as well as on the accessor.
        self.assertIsNone(writer.word_range("day7"))
        self.assertIsNone(writer.word_range(None))
        self.assertIn("body_too_short", self._length_codes("day7", 39))
        self.assertEqual(self._length_codes("day7", 41), [])
        self.assertEqual(self._length_codes("day7", 180), [])
        self.assertEqual(self._length_codes("day7", 181), ["body_too_long"])

    def _codes(self, step_key, words):
        step = {"channel": "email", "subject": "a short subject line",
                "body": " ".join(["margin"] * words)}
        rec = {"cadence": {"c": {step_key: step}}, "contacts": [],
               "lane": None}
        return lint.check(rec, "c", step, step_key=step_key)

    def _length_codes(self, step_key, words):
        """Only the codes about LENGTH. The synthetic record carries no
        contact, so `recipient_not_on_record` is always present and is not
        what any test in this class is about."""
        return [c for c in self._codes(step_key, words)
                if c.startswith("body_too_") or lint.explain_contract(c)]

    def test_em1_is_judged_by_its_own_band_and_never_as_a_reply(self):
        # THE BUG THIS PINS, RE-AIMED AT THE SURVIVING MECHANISM. On this
        # branch `check` derived "is this a reply" from
        # `(low, high) != (MIN_WORDS, MAX_WORDS)`, which became TRUE for em1
        # the moment em1 got a band, so an over-long em1 would have been
        # reported `reply_too_long`. There is no reply code to be handed
        # now - the 15-to-60 range was abolished - so the property is
        # asserted directly: the refusal names em1 and em1's own bounds.
        codes = self._codes("em1", 200)
        self.assertIn("body_too_long", codes)
        self.assertNotIn("reply_too_long", codes)
        self.assertIn("em1_body_200_words_over_contract_90_to_140", codes)

    def test_the_offer_has_no_say_in_a_bodys_length(self):
        # THE REVERSAL THE MERGE BRINGS, and it is deliberate. An offer's
        # `thread_reply_rungs` used to be able to change a word bound
        # through `lint.check(..., reply_steps=...)`. It cannot: the writer
        # contract is the only authority for a length. The offer keeps the
        # say it always had over the step-objective LADDER, which
        # `sequencegate` reads from that field directly.
        import inspect
        for fn in (lint.check, lint.check_step):
            self.assertNotIn("reply_steps",
                             inspect.signature(fn).parameters, fn.__name__)
        self.assertIn("thread_reply_rungs", inspect.getsource(sequencegate))

    def test_the_prompt_states_the_contracts_numbers(self):
        # READS THE RENDERED PROMPT, not the source of this module and not
        # the template. A number retyped in the prose would make this fail.
        low, target, high = writer.WORD_CONTRACT["em1"]
        prompt = copystages.WRITER_SYSTEM
        self.assertIn("%d TO %d WORDS" % (low, high), prompt)
        self.assertIn(str(target), prompt)
        self.assertIn('"em1":"<full body, ~%d words, %d-%d range>"'
                      % (target, low, high), prompt)

    def test_the_prompt_is_cross_checked_rather_than_rendered(self):
        # WHY THE DERIVATION TEST THAT WAS HERE IS GONE, and it is a
        # MEASURED constraint rather than a preference.
        # `copystages.render_writer_system` used to take a contract and
        # substitute the bands, which proved derivation by moving them. It
        # cannot any more: the one authority now lives in
        # `skills.cold_email_writing`, that module imports `copystages` at
        # module level to build `SKILL.procedure`, and a `from . import
        # lint` back in `copystages` closes an import cycle - the contract
        # is unbound when the module body runs. So the numbers are typed
        # into the prompt ONCE and
        # `tests.test_word_contract_enforced.TestTheProseAndTheContractAgree`
        # fails if any of them drifts from the mapping. This asserts that
        # the guard is reachable and that the renderer still renders.
        import inspect
        self.assertEqual(
            list(inspect.signature(
                copystages.render_writer_system).parameters), [])
        self.assertEqual(copystages.render_writer_system(),
                         copystages.WRITER_SYSTEM)
        from tests import test_word_contract_enforced as guard
        case = guard.TestTheProseAndTheContractAgree(
            "test_every_step_range_is_stated_somewhere_in_the_prompts")
        result = case.run()
        self.assertTrue(result.wasSuccessful(),
                        "the prose/contract cross-check is not passing, so "
                        "nothing is holding the prompt to the mapping")

    def test_the_skill_card_states_the_contracts_numbers(self):
        low, target, high = writer.WORD_CONTRACT["em1"]
        band = "%d-%d range" % (low, high)
        schema = writer.SKILL.output_schema["emails"]["em1"]
        self.assertIn(band, schema)
        self.assertIn("~%d words" % target, schema)
        self.assertTrue(any("em1 %d-%d aiming for %d" % (low, high, target)
                            in v for v in writer.SKILL.validation))

    def test_no_second_authority_states_a_different_em1_band(self):
        # The places that used to carry em1 "60-90" and no longer may.
        # SCOPED TO em1: "60-90" is em3's real band now, so a bare
        # substring search over the whole artefact would fail on a correct
        # tree - which is a test asserting the wrong thing, not a defect.
        # The validation line names all five steps in ONE sentence, so the em1
        # CLAUSE is cut out of it rather than the whole line searched: "60-90"
        # is em3's real band now and a bare substring search over the line
        # would fail on a correct tree, which is a test asserting the wrong
        # thing rather than a defect.
        said = "\n".join(writer.SKILL.validation)
        self.assertIn("em1 90-140 aiming for 120", said)
        em1_clause = said.split("em1 ", 1)[1].split(",", 1)[0]
        for name, text in (
                ("skill schema em1",
                 writer.SKILL.output_schema["emails"]["em1"]),
                ("skill validation em1 clause", em1_clause)):
            self.assertNotIn("60-90", text, name)
            self.assertNotIn("60 TO 90", text, name)
        self.assertNotIn("EMAIL 1: 60 TO 90", copystages.WRITER_SYSTEM)
        self.assertNotIn("em1 and em3 are 60 to 90",
                         copystages.WRITER_SYSTEM + copystages.FINAL_CHECK)


class TheReplyBandIsABOLISHEDNotRelocated(unittest.TestCase):
    """What this class asserted until the merge of master 2bf7b8a5, and why
    the assertions are gone rather than moved.

    IT ASSERTED THE 15-TO-60 THREAD-REPLY BAND, relocated out of
    `REPLY_MIN_WORDS` / `REPLY_MAX_WORDS` and into `lint.WORD_CONTRACT`:
    `reply_band()`, `word_range(step, reply_steps)`, the `reply_too_short` /
    `reply_too_long` retry sentences, and an offer's rungs overruling the
    contract. THE OPERATOR ABOLISHED THAT BAND ON 2026-10-02, a day after he
    created it, because it and the writer contract intersected to exactly ONE
    legal length for em2 - an equality, not a threshold. Master merged the
    abolition (TASK-943) and deleted the whole mechanism, so every one of
    those assertions is about behaviour that no longer exists. Keeping them
    would reintroduce the two authorities 943 was merged to remove.

    WHAT SURVIVED IS THE DELETION ITSELF, asserted below, and the parts of
    the abolition with real teeth live in
    `tests.test_word_contract_enforced.TestTheAbolishedRuleIsGone` and
    `TestEveryRangeHasRoom` - the guard that a range with under thirty legal
    lengths is a collapsed range.
    """

    def test_the_two_reply_constants_are_gone(self):
        # THE MUTATION DETECTOR, UNCHANGED AND STILL RIGHT. It asserts the
        # module NAMESPACE - a real effect - not the text of the source.
        for name in ("REPLY_MIN_WORDS", "REPLY_MAX_WORDS"):
            self.assertFalse(
                hasattr(lint, name),
                "%s is back. The one authority for a body's word count is "
                "skills.cold_email_writing.WORD_CONTRACT; a module-level "
                "constant beside it is the second authority TASK-943 "
                "abolished." % name)

    def test_the_band_itself_is_gone_and_not_merely_relocated(self):
        # THE CONTROL AGAINST READING THE DELETION AS A MOVE. This branch
        # moved the two numbers into the contract and kept the band. The
        # abolition removes the band: em2 is 45 to 90, and neither the
        # accessor nor the step entry says 15 or 60 anywhere.
        for name in ("reply_band", "is_reply_step", "word_range",
                     "reply_steps_for", "REPLY_STEPS", "word_contract"):
            self.assertFalse(hasattr(lint, name),
                             "lint.%s survived the abolition" % name)
        self.assertEqual(writer.word_range("em2"), (45, 90))
        self.assertEqual(writer.word_range("em4"), (45, 90))

    def test_the_reply_codes_can_no_longer_be_produced(self):
        self.assertNotIn("reply_too_short", lint.EXPLAIN)
        self.assertNotIn("reply_too_long", lint.EXPLAIN)

    def test_a_caller_that_cannot_say_the_step_still_gets_a_sentence(self):
        # THE CONTROL THAT NOTHING BROKE FOR THE EIGHT CALL SITES that pass
        # codes and text only. They keep working and still get the global
        # numbers rather than nothing.
        said = lint.explain(["body_too_short"])
        self.assertIn(str(lint.MIN_WORDS), said)
        self.assertTrue(said.strip())
        self.assertEqual(lint.explain([]), "")
        # And an unexplained code is still passed through, not dropped.
        self.assertEqual(lint.explain(["no_such_code"]), "no_such_code")

    def test_the_retry_instruction_carries_THIS_steps_numbers(self):
        # THE DEFECT THE em1 BAND INTRODUCED, pinned through the mechanism
        # that survived. The reason string is fed straight back to the writer,
        # and telling a step the wrong number is an instruction to break its
        # band. A contract refusal is a PARAMETRISED code carrying the step,
        # the count and both bounds, so the sentence states 90 and 140 for em1
        # and never the global 40 and 180.
        step = {"channel": "email", "subject": "a short subject line",
                "body": " ".join(["margin"] * 60)}
        rec = {"cadence": {"c": {"em1": step}}, "contacts": [], "lane": None}
        codes = lint.check(rec, "c", step, step_key="em1")
        contract = [c for c in codes if lint.explain_contract(c)]
        self.assertEqual(contract,
                         ["em1_body_60_words_under_contract_90_to_140"])
        said = lint.explain(contract)
        self.assertIn("90", said)
        self.assertIn("140", said)
        self.assertIn("120", said)



class TheSequenceGateReadsTheSameNumber(unittest.TestCase):
    """`em1_concise` was the second authority. Now it is a consumer."""

    def _em1(self, words):
        # A body of `words` tokens that is otherwise unremarkable.
        return " ".join(["margin"] * words)

    def _verdict(self, words):
        return sequencegate.check(
            {"emails": {"em1": self._em1(words)}}, facts=[])

    def _codes(self, verdict, kind):
        return {f["check"] for f in verdict.get(kind) or []}

    def test_the_operators_longest_exemplar_is_no_longer_failed(self):
        # MEASURED: his own em1 bodies run to 133 words with the signature
        # excluded, and this gate FAILED anything over 130. Two of the
        # seventeen were refused outright by it.
        self.assertNotIn("em1_concise", self._codes(self._verdict(133),
                                                    "failures"))
        self.assertNotIn("em1_concise", self._codes(self._verdict(133),
                                                    "warnings"))

    def test_over_the_ceiling_still_fails(self):
        _low, _t, high = writer.WORD_CONTRACT["em1"]
        self.assertIn("em1_concise",
                      self._codes(self._verdict(high + 1), "failures"))

    def test_under_the_floor_warns(self):
        low, _t, _high = writer.WORD_CONTRACT["em1"]
        self.assertIn("em1_concise",
                      self._codes(self._verdict(low - 1), "warnings"))
        self.assertNotIn("em1_concise",
                         self._codes(self._verdict(low - 1), "failures"))

    def test_the_gate_counts_with_countable_words(self):
        # The signature's 7 tokens must not push a legal em1 over the
        # ceiling. 140 prose words plus a 7-word signature is 147 raw.
        _low, _t, high = writer.WORD_CONTRACT["em1"]
        body = (self._em1(high)
                + "\n\nZvonimir\nCo-founder & CEO, Resonate Group"
                + "\nhttps://resonategroup.co")
        self.assertEqual(len(body.split()), high + 7)
        verdict = sequencegate.check({"emails": {"em1": body}}, facts=[])
        self.assertNotIn("em1_concise", self._codes(verdict, "failures"))


class CountableWordsExcludesABareNameSignature(unittest.TestCase):
    """The counter the whole contract rests on."""

    SIG = ("Zvonimir\nCo-founder & CEO, Resonate Group"
           "\nhttps://resonategroup.co")
    PROSE = ("Hi there,\n\nI run an outbound team for software companies "
             "with long sales cycles.\n\nWorth a short call this week?")

    def test_the_signature_block_is_excluded(self):
        before = len(lint.countable_words(self.PROSE))
        after = len(lint.countable_words(self.PROSE + "\n\n" + self.SIG))
        self.assertEqual(after, before)

    def test_the_block_is_exactly_seven_tokens(self):
        # The measured size of the operator's own signature, in all 16 of
        # the messages that carry one.
        self.assertEqual(len(self.SIG.split()), 7)

    def test_a_body_that_is_only_prose_loses_nothing(self):
        # THE FIRST CONTROL. A rule that strips a trailing block
        # unconditionally would pass the test above and break this one.
        self.assertEqual(len(lint.countable_words(self.PROSE)),
                         len(self.PROSE.split()))

    def test_a_final_sentence_is_untouched(self):
        # THE SECOND CONTROL. The last paragraph here is a real sentence
        # and must be counted.
        body = self.PROSE + "\n\nI will close the loop if the timing is bad."
        self.assertEqual(len(lint.countable_words(body)),
                         len(body.split()))

    def test_a_long_tail_cannot_duck_the_ceiling(self):
        # THE THIRD CONTROL, and the one that matters most: this must never
        # become a way to make a long body short. A paragraph of prose after
        # a name is still prose.
        tail = "Zvonimir\n" + " ".join(["margin"] * 40)
        body = self.PROSE + "\n\n" + tail
        self.assertEqual(len(lint.countable_words(body)),
                         len(body.split()))

    def test_a_signoff_block_still_works(self):
        # The pre-existing path is not broken by the new one.
        body = self.PROSE + "\n\nBest,\n\nZvonimir"
        self.assertEqual(len(lint.countable_words(body)),
                         len(self.PROSE.split()))

    def test_the_direction_is_never_looser(self):
        # Removing text can only LOWER a count, so this can refuse a short
        # body and can never admit a long one.
        for body in (self.PROSE, self.PROSE + "\n\n" + self.SIG,
                     self.SIG, ""):
            self.assertLessEqual(len(lint.countable_words(body)),
                                 len(body.split()), body[:30])


class TheThreeEntryGatesExist(unittest.TestCase):
    """TASK-976 scope item 1, and the vocabulary convention."""

    HOLDS = ("HELD_RESEARCH_REQUIRED", "HELD_PROOF_REQUIRED",
             "HELD_OFFER_UNAPPROVED")

    def test_all_three_are_held_reasons(self):
        values = {getattr(eligibility, name) for name in self.HOLDS}
        self.assertEqual(len(values), 3, values)
        for value in values:
            self.assertTrue(value.startswith(eligibility.HELD + ":"), value)

    def test_each_one_explains_itself(self):
        # `tests/test_eligibility.py` asserts every code in REASONS has a
        # HUMAN entry; this asserts these three specifically, and that the
        # sentence is not the code echoed back.
        for name in self.HOLDS:
            code = getattr(eligibility, name)
            self.assertIn(code, eligibility.REASONS)
            sentence = eligibility.explain(code)
            self.assertNotEqual(sentence, code, code)
            self.assertGreater(len(sentence), 30, code)


class ClientApprovalIsTotalAndOmissionIsRefused(unittest.TestCase):
    """The backfill, and the hole it closes."""

    def test_the_library_loads(self):
        self.assertEqual(len(offers.load()), 9)

    def test_no_approved_offer_is_silent_on_client_approved(self):
        silent = [oid for oid, o in offers.load().items()
                  if o.get("approval_status") == offers.APPROVED
                  and o.get("client_approved") is None]
        self.assertEqual(silent, [])

    def test_the_two_live_spines_are_approved_with_provenance(self):
        lib = offers.load()
        for oid in ("OFFER-A-ECONOMIC-BUYER", "OFFER-B-OPERATIONS"):
            offer = lib[oid]
            self.assertIs(offer.get("client_approved"), True, oid)
            self.assertTrue(offer.get("client_approved_by"), oid)
            self.assertTrue(offer.get("client_approved_on"), oid)
            self.assertTrue(offer.get("client_approved_at_sha"), oid)

    def test_the_give_first_offer_is_still_false(self):
        # THE CONTROL. The backfill must not have turned the flag into a
        # rubber stamp: the one offer the client has NOT approved is still
        # false, and it is still approved for GENERATION.
        give = offers.load()["OFFER-GIVE-001"]
        self.assertIs(give.get("client_approved"), False)
        self.assertEqual(give.get("approval_status"), offers.APPROVED)

    def test_an_approved_offer_with_no_flag_is_refused_at_load(self):
        with self.assertRaises(ValueError) as caught:
            offers._validate("OFFER-TEST", {"approval_status": "approved"})
        self.assertIn("client_approved", str(caught.exception))

    def test_a_pending_offer_needs_no_flag(self):
        # THE CONTROL on the refusal above: the writer cannot reach a
        # pending offer, so silence there is not a send question.
        offers._validate("OFFER-TEST", {"approval_status": "pending"})


class GenerationSucceedsWhileSendingIsHeld(unittest.TestCase):
    """THE OPERATOR'S SPLIT, and the half a gate usually gets wrong."""

    def _step(self, offer_id):
        return {"channel": "email", "subject": "s", "body": "b",
                "offer_id": offer_id}

    def test_an_unapproved_offer_holds_the_send(self):
        self.assertEqual(
            eligibility._offer_unapproved(self._step("OFFER-GIVE-001")),
            eligibility.HELD_OFFER_UNAPPROVED)

    def test_an_approved_offer_does_not(self):
        self.assertIsNone(
            eligibility._offer_unapproved(self._step("OFFER-A-ECONOMIC-BUYER")))

    def test_an_unknown_offer_holds(self):
        # Invariant 0 on a send path: an id nothing in the library answers is
        # UNKNOWN, and UNKNOWN is not a pass.
        self.assertEqual(
            eligibility._offer_unapproved(self._step("OFFER-NOT-REAL")),
            eligibility.HELD_OFFER_UNAPPROVED)

    def test_a_step_naming_no_offer_is_not_held_here(self):
        # THE CONTROL AGAINST A BLANKET REFUSAL. TASK-976's own negative
        # control warned that a flag read as `is True` would hold all nine
        # offers; the mirror of that is a hold that fires on every step that
        # happens not to name one. Omission is closed at load time instead.
        self.assertIsNone(eligibility._offer_unapproved(
            {"channel": "email", "subject": "s", "body": "b"}))

    def test_generation_is_not_held_by_an_unapproved_offer(self):
        # THE HALF THAT WOULD HAVE BROKEN THE COPY-REVIEW LOOP. The writer
        # must be able to generate with OFFER-GIVE-001.
        rec = {"client": "productive", "research": [{"fact": "a fact"}]}
        self.assertEqual(generate.entry_gates(rec), [])
        self.assertNotIn(
            "offer",
            " ".join(code for _s, code in generate.entry_gates(rec)))

    def test_nothing_in_the_generation_gate_reads_client_approved(self):
        # Asserted as an EFFECT: flipping the only unapproved offer's flag
        # must not change what `entry_gates` returns.
        rec = {"client": "productive", "research": [{"fact": "a fact"}]}
        before = generate.entry_gates(rec)
        real = offers.load
        try:
            lib = real()
            lib["OFFER-GIVE-001"] = dict(lib["OFFER-GIVE-001"],
                                         client_approved=True)
            offers.load = lambda: lib
            self.assertEqual(generate.entry_gates(rec), before)
        finally:
            offers.load = real


class TheGenerationSideGates(unittest.TestCase):
    """research_required and proof_required, and both are HOLDS."""

    def test_a_record_with_nothing_to_write_from_holds_em1(self):
        rec = {"client": "productive", "research": []}
        self.assertFalse(generate.facts_block(rec))
        self.assertEqual(generate.entry_gates(rec),
                         [("em1", holdreasons.GENERATION_RESEARCH_REQUIRED)])

    def test_one_research_row_does_not(self):
        # THE FIRST CONTROL. A gate that held every record would pass the
        # test above just as convincingly.
        rec = {"client": "productive", "research": [{"fact": "a fact"}]}
        self.assertEqual(generate.entry_gates(rec), [])

    def test_a_fact_without_a_research_row_does_not(self):
        # THE SECOND CONTROL, and the measurement that put it here: every
        # generation fixture in this repository carries zero research rows
        # and four of the five carry facts `facts_block` returns. A hold on
        # the literal "zero research rows" fired on records that were never
        # short of evidence. `research` is one store; `facts_block` is the
        # authority on what the writer may see.
        rec = {"client": "productive", "research": [],
               "company": "Example Agency",
               "company_facts": {"headcount": 40}}
        if generate.facts_block(rec):
            self.assertEqual(generate.entry_gates(rec), [])
        else:
            # The allowlist did not admit that key; assert the mechanism
            # directly rather than passing on a fixture that proves nothing.
            self.assertIn("facts_block",
                          generate.entry_gates.__code__.co_names)

    def test_the_research_count_is_the_raw_count(self):
        rec = {"research": [{"fact": "x", "quality": "unusable"}]}
        self.assertEqual(generate.research_rows(rec), 1)
        self.assertEqual(generate.research_rows({}), 0)

    def test_an_unknown_tenant_is_not_held_on_proof(self):
        # THE TENANCY EDGE, AND `is False` RATHER THAN `not`.
        # `offers.py` is single-tenant, so this module cannot say how many
        # proof rows another client has - the answer is None, not zero. A
        # gate written `not satisfied` would have held em3 for every client
        # but Productive on a question nobody asked.
        self.assertIsNone(claims.proof_rotation_satisfied("some-other-client"))
        rec = {"client": "some-other-client",
               "research": [{"fact": "a fact"}]}
        self.assertEqual(generate.entry_gates(rec), [])

    def test_unknown_is_not_zero(self):
        self.assertIsNone(claims.licensed_proof_rows("some-other-client"))
        self.assertIsInstance(claims.licensed_proof_rows("productive"), int)

    def test_the_threshold_is_two(self):
        self.assertEqual(claims.PROOF_ROTATION_MINIMUM, 2)
        count = claims.licensed_proof_rows("productive")
        self.assertIs(claims.proof_rotation_satisfied("productive"),
                      count >= 2)
        self.assertEqual(claims.PROOF_ROTATION_MINIMUM, 2)

    def test_a_licensed_proof_needs_both_halves(self):
        # The licence AND the stored page. Productive's eleven case studies
        # carry `status: CLIENT_APPROVED` in the offer library and a stored
        # page under docs/evidence; neither alone counts.
        self.assertGreaterEqual(claims.licensed_proof_rows("productive"), 2)
        self.assertIsNone(claims.licensed_proof_rows("another-tenant"))

    def test_the_stored_PAGE_half_is_required(self):
        # BOTH HALVES, and this is the one a mutation got past. Removing the
        # stored-page requirement left the count at eleven, so nothing
        # observed it. Point the store at a directory that does not exist
        # and the count must go to ZERO - the licence alone licenses
        # nothing, which is the operator's decision of 2026-09-27 read
        # literally.
        from src import casestudies
        real = casestudies._STUDIES_DIR
        try:
            casestudies._STUDIES_DIR = os.path.join(ROOT, "no-such-directory")
            self.assertEqual(claims.licensed_proof_rows("productive"), 0)
            self.assertFalse(claims.proof_rotation_satisfied("productive"))
            # AND THE GATE MOVES WITH IT, end to end.
            rec = {"client": "productive", "research": [{"fact": "a fact"}]}
            self.assertEqual(
                generate.entry_gates(rec),
                [("em3", holdreasons.GENERATION_PROOF_REQUIRED)])
        finally:
            casestudies._STUDIES_DIR = real
        # THE CONTROL that the restore worked and the count is real.
        self.assertGreaterEqual(claims.licensed_proof_rows("productive"), 2)

    def test_the_LICENCE_half_is_required(self):
        # The other half: a stored page whose licence is not CLIENT_APPROVED
        # counts for nothing. Patch the library's own evidence block rather
        # than the file, so the file stays the authority.
        real = offers._load_raw
        try:
            raw = real()
            raw["evidence"] = {k: dict(v, status="VERIFIED_PUBLIC")
                               for k, v in (raw.get("evidence") or {}).items()}
            offers._load_raw = lambda: raw
            self.assertEqual(claims.licensed_proof_rows("productive"), 0)
        finally:
            offers._load_raw = real
        self.assertGreaterEqual(claims.licensed_proof_rows("productive"), 2)

    def test_an_unreadable_client_is_unknown_not_zero(self):
        self.assertIsNone(claims.licensed_proof_rows(None))
        self.assertIsNone(claims.licensed_proof_rows(""))

    def test_both_holds_are_human_review_rather_than_retryable(self):
        # Neither clears itself and neither clears for free, so a retry
        # would burn a model call to produce the same hold.
        for code in (holdreasons.GENERATION_RESEARCH_REQUIRED,
                     holdreasons.GENERATION_PROOF_REQUIRED):
            self.assertEqual(holdreasons.classify(code),
                             holdreasons.HUMAN_REVIEW, code)

    def test_a_narrowed_step_set_holds_nothing(self):
        rec = {"client": "productive", "research": []}
        self.assertEqual(generate.entry_gates(rec, steps=("em2", "em4")), [])


class TheGatesAreACTUALLYCALLED(unittest.TestCase):
    """EXISTENCE IS NOT FUNCTION - CLAUDE.md. A gate nothing calls is this
    repository's signature defect, and the only thing that distinguishes a
    live gate from a dead one is a test that fails when the CALL is removed.

    These assert the COMPILED code object's names rather than the source
    text, so a comment mentioning the function does not satisfy them and
    deleting the call does break them.
    """

    def test_decide_calls_the_offer_hold(self):
        self.assertIn("_offer_unapproved",
                      eligibility.decide.__code__.co_names)

    def test_generate_record_calls_the_entry_gates(self):
        # The call lives in a closure inside `generate_record`, so the name
        # is in the closure's code object; the closure's own name is in the
        # enclosing function's locals, which is what proves it is REACHED.
        inner = [c for c in generate.generate_record.__code__.co_consts
                 if getattr(c, "co_name", None) == "_entry_gate_hold"]
        self.assertEqual(len(inner), 1, "the entry-gate closure is gone")
        self.assertIn("entry_gates", inner[0].co_names)
        self.assertIn("_entry_gate_hold",
                      generate.generate_record.__code__.co_varnames
                      + generate.generate_record.__code__.co_cellvars)

    def test_the_lint_check_site_reads_the_writers_contract(self):
        # `is_reply_step` was asserted here and is deleted with the reply
        # band. What `check` must actually CALL now is the writer contract's
        # own range function - the one authority - and the parametrised
        # contract code that carries the bounds back to the writer.
        self.assertIn("writercontract", lint.check.__code__.co_names)
        self.assertIn("contract_code", lint.check.__code__.co_names)

    def test_the_sequence_gate_reads_the_contract_not_a_constant(self):
        self.assertIn("STEP_WORD_CONTRACT",
                      sequencegate.check.__code__.co_names)
        self.assertIn("countable_words", sequencegate.check.__code__.co_names)


class TheWordGateReportsTheRightCode(unittest.TestCase):
    """The EFFECT at the gate, never a helper.

    The reply codes these asserted were abolished with the 15-to-60 band;
    what replaces them is a parametrised contract code naming the step and
    both of its bounds, so every assertion here names em1's own numbers.
    """

    def _check(self, step_key, words):
        step = {"channel": "email", "subject": "a short subject line",
                "body": " ".join(["margin"] * words)}
        rec = {"cadence": {"c": {step_key: step}}, "contacts": [],
               "lane": None}
        return lint.check(rec, "c", step, step_key=step_key)

    def test_an_over_long_em1_names_em1_and_never_a_reply(self):
        # THE BUG THIS PINS: on this branch em1 acquired a band of its own
        # and the derivation `(low, high) != (MIN_WORDS, MAX_WORDS)`
        # therefore classified it as a thread reply, so the writer would
        # have been told `reply_too_long` about a step that is not a reply.
        # The reply codes do not exist now; the refusal names the step.
        codes = self._check("em1", 200)
        self.assertIn("body_too_long", codes)
        self.assertNotIn("reply_too_long", codes)
        self.assertIn("em1_body_200_words_over_contract_90_to_140", codes)

    def test_an_over_long_em2_is_refused_by_its_own_ceiling(self):
        # THE CONTROL. em2 must still be refusable, and by 90 - its own
        # ceiling - rather than by the abolished 60 or by `MAX_WORDS`.
        codes = self._check("em2", 100)
        self.assertNotIn("body_too_long", codes)
        self.assertIn("em2_body_100_words_over_contract_45_to_90", codes)

    def test_a_short_em1_is_refused_under_the_new_floor(self):
        # 60 words passed the old 40-word floor and fails the operator's 90.
        codes = self._check("em1", 60)
        self.assertNotIn("body_too_short", codes)
        self.assertIn("em1_body_60_words_under_contract_90_to_140", codes)
        # And a body short enough to break BOTH rules breaks both.
        self.assertIn("body_too_short", self._check("em1", 30))

    def test_a_120_word_em1_passes_the_range(self):
        # THE CONTROL AGAINST A BLANKET REFUSAL: the operator's own target
        # length must not be refused by the gate that enforces his band.
        # Every LENGTH code, so the assertion cannot be satisfied by the
        # contract going silent. The synthetic record carries no contact, so
        # `recipient_not_on_record` is always there and is not this test.
        self.assertEqual(
            [c for c in self._check("em1", 120)
             if c.startswith("body_too_") or lint.explain_contract(c)],
            [])


class TheExemplarsAreWiredIntoTheWriter(unittest.TestCase):
    """TASK-964 left `WRITER_SYSTEM` unwired because the files did not
    exist. They exist."""

    def test_both_files_exist(self):
        for name in copystages.EXEMPLAR_FILES:
            self.assertTrue(
                os.path.isfile(os.path.join(EXEMPLAR_DIR, name)), name)

    def test_the_prompt_carries_both(self):
        prompt = copystages.WRITER_SYSTEM
        for name in copystages.EXEMPLAR_FILES:
            with open(os.path.join(EXEMPLAR_DIR, name),
                      encoding="utf-8") as fh:
                # A distinctive line from each file, not the whole file: the
                # loader strips trailing whitespace.
                first = fh.read().strip().split("\n")[0]
            self.assertIn(first, prompt, name)

    def test_the_prohibition_reaches_the_model(self):
        self.assertIn("DO NOT COPY THE CONTENT", copystages.WRITER_SYSTEM)
        self.assertIn("NEVER AS CONTENT", copystages.WRITER_SYSTEM)

    def test_removing_the_wiring_breaks_it(self):
        # THE TEST THAT FAILS WHEN THE CALL IS REMOVED. Rendering with no
        # exemplar files must leave the prompt without them and must say so
        # rather than omitting them silently.
        rendered = copystages.render_writer_system()
        self.assertIn("THE OPERATOR'S OWN COPY", rendered)
        missing = copystages.exemplar_text(("does-not-exist.md",))
        self.assertIn("COULD NOT BE READ", missing)

    def test_the_contract_and_the_exemplars_agree(self):
        # The file states the band; the band comes from the contract. A
        # drifted exemplar file would make this fail.
        low, target, high = writer.WORD_CONTRACT["em1"]
        with open(os.path.join(EXEMPLAR_DIR, "em1-operator.md"),
                  encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("(%d-%d)" % (low, high), text)
        self.assertIn("%d to %d with a target of %d" % (low, high, target),
                      text)

    def test_the_cadence_file_carries_five_steps_and_the_days(self):
        with open(os.path.join(EXEMPLAR_DIR, "cadence-operator.md"),
                  encoding="utf-8") as fh:
            text = fh.read()
        for step in ("em1", "em2", "em3", "em4", "em5"):
            self.assertIn("| %s |" % step, text)
        for day in (0, 3, 7, 12, 18):
            self.assertIn("| %d |" % day, text)
        # The role column is the ladder, and the ladder is the authority.
        for role in sequencegate.ROLE_LADDER:
            self.assertIn(role.split("_")[0], text.lower(), role)


class NoIdentifierSurvivedInTheExemplars(unittest.TestCase):
    """The scan, over the FINAL text including every header and table."""

    def _files(self):
        return [os.path.join(EXEMPLAR_DIR, n) for n in ("em1-operator.md",
                                                        "cadence-operator.md")]

    def test_the_exemplar_files_carry_no_identifier(self):
        for path in self._files():
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            hits = _hits(text)
            self.assertEqual(
                hits, [],
                "%d identifier(s) leaked into %s - sha256: %s"
                % (len(hits), os.path.basename(path), hits))

    def test_the_rendered_prompt_carries_no_identifier(self):
        # The exemplars reach the model through the prompt, so the prompt is
        # scanned too rather than only the files.
        hits = _hits(copystages.WRITER_SYSTEM)
        self.assertEqual(hits, [], "%d identifier(s) in WRITER_SYSTEM: %s"
                         % (len(hits), hits))

    def test_this_test_file_carries_no_identifier(self):
        # THE ONE THAT CAUGHT IT BEFORE. A check that spells the forbidden
        # names reintroduces them, which happened three times in one night
        # here - including in a test's own list of forbidden strings.
        with open(os.path.abspath(__file__), encoding="utf-8") as fh:
            hits = _hits(fh.read())
        self.assertEqual(hits, [], "%d identifier(s) in this file: %s"
                         % (len(hits), hits))

    def test_the_scan_can_fail(self):
        # A SCAN THAT REPORTS CLEAN BECAUSE IT IS WATCHING NOTHING is worse
        # than no scan. One forbidden hash is picked and a token hashing to
        # it is constructed by brute force over the source's own alphabet -
        # impossible - so instead the scanner is proven on a hash it DOES
        # hold: `_hits` is fed a text built from a token whose hash is in the
        # set, recovered by hashing a candidate rather than by storing it.
        self.assertTrue(FORBIDDEN_HASHES, "the needle set is empty")
        # The positive control without naming anything: hash an invented
        # token, make it the ONLY needle, and prove `_hits` finds it in a
        # text that carries it and misses it in one that does not.
        token = "aplaintokenthatisnotaname"
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        real = _swap_needles(frozenset({digest}))
        try:
            self.assertEqual(_hits("some text with %s in it" % token),
                             [digest])
            self.assertEqual(_hits("some text with nothing in it"), [])
        finally:
            _swap_needles(real)

    def test_the_needle_set_is_the_size_it_was_generated_at(self):
        # A needle set that silently shrank would make every scan above
        # pass while watching less.
        self.assertEqual(len(FORBIDDEN_HASHES), 41)


if __name__ == "__main__":
    unittest.main()
