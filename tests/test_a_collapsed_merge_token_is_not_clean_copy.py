"""The fifth shape: a merge token that collapsed INSIDE grammatical copy.

THE FOUR SHAPES `emptyrender` ALREADY HAS ALL NEED A VISIBLE WOUND - an empty
value, the word `None`, a token the provider left behind, a bare `Re:`. This
one leaves none. The sentence is present, grammatical and short of exactly the
word it was built around, and every one of the four returns CLEAN on it.

## THE MEASURED SHAPE, AND WHAT IS AND IS NOT EVIDENCE FOR IT HERE

INTERNAL EmailBison campaign 352 - operator-declared internal on 2026-10-01,
read-only, never written to - carries `{INDUSTRY}` in the subject templates of
parent step 4040's variants. That is a PROVIDER FACT recorded in
`docs/BISON-PROVIDER-TRUTH-2026-09-14.md` lines 240-241:

    "what we see with {INDUSTRY} agencies..."
    "{what we see with {INDUSTRY} agencies|a pattern across {INDU..."

the second of which is the provider's spintax, and both of which that document
records TRUNCATED - so the templates below are the measured prefix and not a
byte-exact copy of the stored string.

The RENDERED side was measured on the live provider on 2026-10-01 and handed to
this task: 88 subject lines reading `what we see with agencies`, which is
`{INDUSTRY}` collapsing to nothing in 100% of that token's uses. THAT COUNT IS
NOT RE-DERIVED HERE and nothing in this repository can re-derive it: the
nearest local record, `docs/BISON-THREAD-FINDINGS-2026-09-15.md` line 327,
tallies the same subject 18 times on 2026-09-15 as `what we see with [redacted]
agencies` - the document redacts the industry slot, so it cannot say whether
that sample was filled or empty. What IS local, checkable and sufficient for
this test file is the SHAPE: this template, that rendered string, and the fact
that the detector returned clean on the pair.

## WHY THE TEMPLATE IS THE WITNESS AND THE RENDERED TEXT IS NOT

`what we see with agencies` is a correct English sentence. No predicate over
that string alone can tell it from copy somebody wrote that way on purpose, and
the control that proves it is in this file: the same sentence with no merge
token behind it must stay CLEAN. The evidence that separates them is the
TEMPLATE - one token, one value, present or absent - and both halves are
obtainable on our path: `bison.sequence_steps` returns the stored
`email_subject`/`email_body` per step id, and `bison.scheduled_emails` returns
the rendered row carrying `sequence_step_id`. Join the two and the question is
decided rather than guessed.

Two witnesses are therefore tested separately, because they fail differently:

    TEMPLATE + VALUE MAP    certain. A token with no value, an empty value or a
                            whitespace value cannot have rendered to anything.
    TEMPLATE + RENDERED     structural. The literal words either side of the
                            token are adjacent in the rendered text, so the
                            token contributed nothing. Certain when that
                            context is found; UNDECIDABLE when it is not,
                            which is what the provider's spintax does to it.

UNDECIDABLE IS NOT CLEAN AND IS NOT A REFUSAL. It is its own answer, and the
test for it asserts that a spintax template neither halts the line nor reports
itself verified.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import emptyrender                                    # noqa: E402


# --- campaign 352, step 4040: the template and the render ------------------

#: `docs/BISON-PROVIDER-TRUTH-2026-09-14.md:240`, truncated there at the
#: ellipsis. Merge token verbatim.
TEMPLATE_352 = "what we see with {INDUSTRY} agencies"

#: The provider's spintax form of the same line, same document, line 241. The
#: braces holding `|` are the provider's variant syntax and NOT merge tokens.
TEMPLATE_352_SPINTAX = (
    "{what we see with {INDUSTRY} agencies|a pattern across {INDUSTRY}}")

#: Measured on the live provider 2026-10-01 and handed to this task: what 88
#: subject lines actually read. Grammatical, unpunctuated at the wound, and
#: short of the one word the line was built around.
LIVE_SUBJECT = "what we see with agencies"

#: The same line with its token resolved - what it was supposed to read.
FILLED_SUBJECT = "what we see with marketing agencies"

#: A lead whose `industry` variable was never set. The 2026-09-23 incident lead
#: (167865) was this shape in a different field: `headline` and `location` and
#: nothing else.
VALUES_MISSING = {"first": "Julian", "company": "Example Agency Ltd"}
VALUES_EMPTY = dict(VALUES_MISSING, industry="")
VALUES_WHITESPACE = dict(VALUES_MISSING, industry="   ")
VALUES_NONE = dict(VALUES_MISSING, industry=None)
VALUES_FILLED = dict(VALUES_MISSING, industry="marketing")

#: `bison.sequence_steps` returns exactly these keys per step. Step 4040 is
#: campaign 352's order-3 parent, `docs/BISON-PROVIDER-TRUTH-2026-09-14.md:238`.
STEPS_352 = [{"id": 4040, "order": 3, "email_subject": TEMPLATE_352,
              "email_body": "<p>{FIRST}, a note about {INDUSTRY} margins.</p>"}]

#: A `scheduled_emails` row as the provider returns it, carrying the rendered
#: copy and the step id that joins it to the template above. The lead's
#: variables are attached under the provider's own `custom_variables` shape -
#: a list of `{name, value}`, which is what `bison.variables_of` reads.
def row_352(subject=LIVE_SUBJECT, body=None, values=VALUES_EMPTY,
            status="scheduled", threaded=False):
    body = ("<p>Julian, a note about margins.</p>" if body is None else body)
    return {"id": 22400001, "sequence_step_id": 4040, "status": status,
            "thread_reply": threaded, "email_subject": subject,
            "email_body": body,
            "lead": {"id": 190068,
                     "custom_variables": [{"name": k, "value": v}
                                          for k, v in values.items()]}}


# --- our own copy, for the false-positive controls -------------------------

#: `scripts/stage_s7_copy.py:105`, read back off campaign 489 on 2026-09-21 -
#: the campaign that sent this project's first two real emails. Four tokens in
#: one paragraph, one of them `{INDUSTRY}`.
OUR_BODY_TEMPLATE = (
    "{FIRST}, I work with {INDUSTRY} teams on {ANGLE}, and I do not know how "
    "{COMPANY} handles it")

OUR_VALUES = {"FIRST": "Julian", "INDUSTRY": "Marketing & Advertising",
              "ANGLE": "profitability", "COMPANY": "Example Agency Ltd"}

OUR_BODY_FILLED = (
    "Julian, I work with Marketing & Advertising teams on profitability, and "
    "I do not know how Example Agency Ltd handles it")

#: The same paragraph with `{INDUSTRY}` collapsed. Still a sentence. Now a
#: claim about nobody.
OUR_BODY_COLLAPSED = (
    "Julian, I work with teams on profitability, and I do not know how "
    "Example Agency Ltd handles it")


class TheLiveShapeIsRefused(unittest.TestCase):
    """Campaign 352's 88 subjects, as the template and the render together."""

    def test_the_rendered_text_alone_cannot_decide_and_says_so(self):
        """THIS IS THE HOLE, AND IT IS NOT CLOSED BY GUESSING.

        No template, no value map: the string is a well-formed sentence and
        the four shapes are right to pass it. This test passes before and
        after the fifth shape exists, and it is here so nobody later 'fixes'
        the hole by banning the sentence.
        """
        self.assertIsNone(emptyrender.classify_subject(LIVE_SUBJECT))
        self.assertIsNone(emptyrender.classify_body(f"<p>{LIVE_SUBJECT}</p>"))

    def test_the_live_pair_is_refused_on_the_value_map(self):
        self.assertEqual(
            emptyrender.classify_subject(LIVE_SUBJECT, template=TEMPLATE_352,
                                         values=VALUES_EMPTY),
            emptyrender.COLLAPSED)

    def test_the_live_pair_is_refused_on_the_template_and_render_alone(self):
        """No value map at all. The words either side of the token are adjacent."""
        self.assertEqual(
            emptyrender.classify_subject(LIVE_SUBJECT, template=TEMPLATE_352),
            emptyrender.COLLAPSED)

    def test_the_live_row_is_refused_when_the_step_is_joined(self):
        faults = dict(emptyrender.classify_row(row_352(), steps=STEPS_352))
        self.assertEqual(faults.get("subject"), emptyrender.COLLAPSED)

    def test_the_refusal_lands_in_pending_where_a_caller_halts(self):
        """A refusal, not a warning: the same bucket the watcher halts on."""
        found = emptyrender.scan([row_352()], steps=STEPS_352)
        self.assertEqual(len(found["pending"]), 1)
        self.assertEqual(found["already"], [])
        self.assertIn(("subject", emptyrender.COLLAPSED),
                      found["pending"][0]["faults"])

    def test_a_scan_with_no_step_templates_cannot_see_it(self):
        """The call shape production uses TODAY, and what it costs.

        `bisonfactory._refuse_blank_render` and `scripts/bison_watch_loop.py`
        both call `scan(rows)` with no steps, so the fifth shape is inert on
        those two paths until they pass the sequence. Asserted rather than
        described, so wiring them cannot be quietly forgotten.
        """
        self.assertEqual(emptyrender.scan([row_352()])["pending"], [])

    def test_the_body_half_of_the_same_row_is_refused_too(self):
        faults = dict(emptyrender.classify_row(
            row_352(body="<p>Julian, a note about margins.</p>"),
            steps=STEPS_352))
        self.assertEqual(faults.get("body"), emptyrender.COLLAPSED)


class TheSentenceSomebodyMeantToWriteStaysClean(unittest.TestCase):
    """The control without which this is a ban on a normal English sentence."""

    def test_the_same_sentence_with_no_merge_token_is_clean(self):
        """Deliberate copy. No token, nothing to collapse, nothing to refuse."""
        self.assertIsNone(emptyrender.classify_subject(
            LIVE_SUBJECT, template=LIVE_SUBJECT, values=VALUES_EMPTY))
        self.assertIsNone(emptyrender.classify_body(
            f"<p>{LIVE_SUBJECT}</p>", template=f"<p>{LIVE_SUBJECT}</p>",
            values=VALUES_EMPTY))

    def test_a_row_whose_template_carries_no_token_is_clean(self):
        steps = [{"id": 4040, "order": 3, "email_subject": LIVE_SUBJECT,
                  "email_body": "<p>A note about margins.</p>"}]
        row = row_352(body="<p>A note about margins.</p>")
        self.assertEqual(emptyrender.classify_row(row, steps=steps), [])

    def test_a_token_that_rendered_to_a_real_value_is_clean(self):
        for values in (VALUES_FILLED, None):
            with self.subTest(values=values):
                self.assertIsNone(emptyrender.classify_subject(
                    FILLED_SUBJECT, template=TEMPLATE_352, values=values))

    def test_our_own_live_opener_renders_clean_on_four_tokens(self):
        """Campaign 489's body, filled. Four tokens, none collapsed."""
        self.assertIsNone(emptyrender.classify_body(
            OUR_BODY_FILLED, template=OUR_BODY_TEMPLATE, values=OUR_VALUES))

    def test_our_own_opener_with_one_token_collapsed_is_refused(self):
        """The same paragraph, one word short, still grammatical."""
        for values in (dict(OUR_VALUES, INDUSTRY=""), None):
            with self.subTest(values=values):
                self.assertEqual(
                    emptyrender.classify_body(OUR_BODY_COLLAPSED,
                                              template=OUR_BODY_TEMPLATE,
                                              values=values),
                    emptyrender.COLLAPSED)

    def test_a_value_the_token_name_differs_from_in_case_is_clean(self):
        """Templates shout `{INDUSTRY}`, the provider stores `industry`.

        A case-sensitive lookup would call every correctly rendered row
        collapsed, which is the false positive that halts a healthy campaign.
        """
        self.assertIsNone(emptyrender.classify_subject(
            FILLED_SUBJECT, template=TEMPLATE_352,
            values={"INDUSTRY": "marketing"}))
        self.assertIsNone(emptyrender.classify_subject(
            FILLED_SUBJECT, template="what we see with {industry} agencies",
            values={"Industry": "marketing"}))


class EveryWayAValueCanBeMissingIsRefused(unittest.TestCase):
    """Absent, empty, whitespace - the provider renders all three to nothing."""

    def test_absent_from_the_value_map_entirely(self):
        self.assertEqual(
            emptyrender.classify_subject(LIVE_SUBJECT, template=TEMPLATE_352,
                                         values=VALUES_MISSING),
            emptyrender.COLLAPSED)

    def test_present_but_the_empty_string(self):
        self.assertEqual(
            emptyrender.classify_subject(LIVE_SUBJECT, template=TEMPLATE_352,
                                         values=VALUES_EMPTY),
            emptyrender.COLLAPSED)

    def test_present_but_whitespace(self):
        self.assertEqual(
            emptyrender.classify_subject(LIVE_SUBJECT, template=TEMPLATE_352,
                                         values=VALUES_WHITESPACE),
            emptyrender.COLLAPSED)

    def test_present_but_None(self):
        self.assertEqual(
            emptyrender.classify_subject(LIVE_SUBJECT, template=TEMPLATE_352,
                                         values=VALUES_NONE),
            emptyrender.COLLAPSED)

    def test_an_empty_value_map_refuses_every_token(self):
        """The 2026-09-23 lead carried two variables and neither was a copy one."""
        self.assertEqual(
            sorted(emptyrender.collapsed_by_values(OUR_BODY_TEMPLATE, {})[0]),
            ["ANGLE", "COMPANY", "FIRST", "INDUSTRY"])

    def test_a_value_that_is_the_word_None_is_refused_as_LITERAL_NONE(self):
        """`None` mid-sentence is not empty, and the whole-value check misses it.

        Factory leads carry the string `'None'` in `body_4..6` today. Inside a
        sentence it reads `I work with None teams`, which the existing
        whole-value `LITERAL_NONE` check cannot see.
        """
        self.assertEqual(
            emptyrender.classify_body(
                "Julian, I work with None teams on profitability, and I do "
                "not know how Example Agency Ltd handles it",
                template=OUR_BODY_TEMPLATE,
                values=dict(OUR_VALUES, INDUSTRY="None")),
            emptyrender.LITERAL_NONE)


class TheRenderedWitnessSaysWhenItCannotTell(unittest.TestCase):
    """UNDECIDABLE is its own answer. It is not clean and it is not a halt."""

    def test_spintax_is_not_decidable_from_the_render_alone(self):
        detail = emptyrender.merge_detail(TEMPLATE_352_SPINTAX,
                                          rendered="a pattern across agencies")
        self.assertEqual(detail["collapsed"], [])
        self.assertEqual(detail["undecided"], ["INDUSTRY"])

    def test_an_undecidable_token_does_not_halt_the_line(self):
        self.assertIsNone(emptyrender.classify_subject(
            "a pattern across agencies", template=TEMPLATE_352_SPINTAX))

    def test_an_undecidable_token_does_not_report_itself_verified(self):
        self.assertEqual(
            emptyrender.classify_merge(TEMPLATE_352_SPINTAX,
                                       rendered="a pattern across agencies"),
            emptyrender.MERGE_UNVERIFIED)

    def test_a_value_map_decides_what_the_render_could_not(self):
        """Spintax defeats the structural witness. The value map still answers."""
        self.assertEqual(
            emptyrender.classify_subject("a pattern across agencies",
                                         template=TEMPLATE_352_SPINTAX,
                                         values=VALUES_EMPTY),
            emptyrender.COLLAPSED)

    def test_coverage_reports_what_was_actually_decided(self):
        """Zero decided is not a pass, exactly as zero rows is not a pass.

        Step 4040 carries `{INDUSTRY}` in BOTH its subject and its body
        template, and both collapsed on this row - so two fields were decided
        and two were refused.
        """
        decided = emptyrender.merge_coverage([row_352()], steps=STEPS_352)
        self.assertEqual(decided["rows"], 1)
        self.assertEqual(decided["fields"], 2)
        self.assertEqual(decided["decided"], 2)
        self.assertEqual(decided["collapsed"], 2)
        self.assertEqual(decided["undecided"], 0)
        self.assertTrue(decided["verified"])

    def test_coverage_with_no_templates_reports_itself_blind(self):
        """The call shape production uses today. It verified NOTHING."""
        blind = emptyrender.merge_coverage([row_352()])
        self.assertEqual(blind["rows"], 1)
        self.assertEqual(blind["fields"], 0)
        self.assertEqual(blind["collapsed"], 0)
        self.assertFalse(blind["verified"])

    def test_coverage_counts_an_undecidable_field_as_undecided(self):
        """Spintax, no value map: looked at, not decided, and not verified."""
        steps = [{"id": 4040, "order": 3,
                  "email_subject": TEMPLATE_352_SPINTAX,
                  "email_body": "<p>A note about margins.</p>"}]
        row = {"id": 1, "sequence_step_id": 4040, "status": "scheduled",
               "thread_reply": False,
               "email_subject": "a pattern across agencies",
               "email_body": "<p>A note about margins.</p>",
               "lead": {"id": 190068}}
        cover = emptyrender.merge_coverage([row], steps=steps)
        self.assertEqual(cover["fields"], 1)
        self.assertEqual(cover["undecided"], 1)
        self.assertEqual(cover["decided"], 0)
        self.assertEqual(cover["collapsed"], 0)
        self.assertFalse(cover["verified"])


class TheDeliberateThreadedExemptionSurvives(unittest.TestCase):
    """`subject_N = ""` on a threaded step is the DESIGN, not a collapsed token.

    `bisonfactory._variables_for` writes an empty subject for threaded
    positions on purpose - the provider prepends `Re:` itself. A fifth shape
    that read that as a collapsed token would halt every healthy follow-up in
    the estate, which is a worse failure than the one it is fixing.
    """

    def test_an_empty_subject_on_a_threaded_row_is_still_allowed(self):
        steps = [{"id": 4770, "order": 2, "email_subject": "{SUBJECT_1}",
                  "email_body": "<p>{BODY_2}</p>"}]
        row = {"id": 22352261, "sequence_step_id": 4770, "status": "scheduled",
               "thread_reply": True, "email_subject": "",
               "email_body": "<p>Julian, the teams I work with.</p>",
               "lead": {"id": 167609, "custom_variables": [
                   {"name": "subject_2", "value": ""},
                   {"name": "body_2", "value": "Julian, the teams I work with."}]}}
        self.assertIsNone(dict(emptyrender.classify_row(row, steps=steps))
                          .get("subject"))

    def test_a_threaded_row_with_real_copy_is_still_checked(self):
        """The exemption is for an ABSENT subject, not for a damaged one."""
        steps = [{"id": 4040, "order": 3, "email_subject": TEMPLATE_352,
                  "email_body": "<p>A note.</p>"}]
        row = row_352(status="scheduled", threaded=True,
                      body="<p>A note.</p>")
        self.assertEqual(
            dict(emptyrender.classify_row(row, steps=steps)).get("subject"),
            emptyrender.COLLAPSED)


class TheFourExistingShapesAreUntouched(unittest.TestCase):
    """Positive controls. The real 2026-09-23 rows, classified as before.

    Every fixture here is the provider's own, from
    `tests/test_a_blank_email_can_never_be_sent_again.py`, and every assertion
    is the verdict that file already demands. If the fifth shape changed any
    of them, this class says which.
    """

    OPENER_BLANK = {"id": 22352262, "sequence_step_id": 4769, "status": "sent",
                    "thread_reply": False, "email_subject": "",
                    "email_body": "<p></p>", "lead": {"id": 167865}}

    FOLLOWUP_BLANK = {"id": 22356508, "sequence_step_id": 4770,
                      "status": "stopped", "thread_reply": True,
                      "email_subject": "Re: ", "email_body": "<p></p>",
                      "lead": {"id": 167865}}

    def test_shape_one_EMPTY_is_unchanged(self):
        faults = dict(emptyrender.classify_row(self.OPENER_BLANK))
        self.assertEqual(faults.get("subject"), emptyrender.EMPTY)
        self.assertEqual(faults.get("body"), emptyrender.EMPTY)
        for value in ("<p></p>", "<br>", "<br/>", "&nbsp;", "  ",
                      "<p><br></p>", "<div>&nbsp;</div>"):
            with self.subTest(value=value):
                self.assertEqual(emptyrender.classify_body(value),
                                 emptyrender.EMPTY)

    def test_shape_two_LITERAL_NONE_is_unchanged(self):
        for value in ("None", "none", " NONE ", "null", "<p>None</p>"):
            with self.subTest(value=value):
                self.assertEqual(emptyrender.classify_body(value),
                                 emptyrender.LITERAL_NONE)

    def test_shape_three_PLACEHOLDER_is_unchanged(self):
        for value in ("<p>{BODY_1}</p>", "{{FIRST_NAME}}, hello"):
            with self.subTest(value=value):
                self.assertEqual(emptyrender.classify_body(value),
                                 emptyrender.PLACEHOLDER)
        self.assertEqual(emptyrender.classify_subject("{SUBJECT_1}"),
                         emptyrender.PLACEHOLDER)

    def test_shape_four_SUBJECT_RE_is_unchanged(self):
        faults = dict(emptyrender.classify_row(self.FOLLOWUP_BLANK))
        self.assertEqual(faults.get("subject"), emptyrender.SUBJECT_RE)
        self.assertEqual(faults.get("body"), emptyrender.EMPTY)

    def test_the_four_still_win_the_label_when_a_template_is_present(self):
        """Shape five is LAST. It names the case the other four cannot see.

        The blank opener's template DID have a collapsed token - that is what
        made it blank - and the right word for what a person received is still
        EMPTY. A relabelling would make the incident's own fixtures read as a
        different fault, and `scripts/qa/check_readback.py` tallies by reason.
        """
        steps = [{"id": 4769, "order": 1, "email_subject": "{SUBJECT_1}",
                  "email_body": "<p>{BODY_1}</p>"}]
        faults = dict(emptyrender.classify_row(self.OPENER_BLANK, steps=steps))
        self.assertEqual(faults.get("subject"), emptyrender.EMPTY)
        self.assertEqual(faults.get("body"), emptyrender.EMPTY)

    def test_a_real_body_containing_a_break_is_still_a_real_body(self):
        self.assertIsNone(
            emptyrender.classify_body("<p>Hello.<br>Second line.</p>"))

    def test_the_default_call_is_byte_identical_to_passing_None(self):
        """No caller that does not opt in may see a different answer."""
        for value in ("", "<p></p>", "None", "{BODY_1}", "Re: ",
                      LIVE_SUBJECT, OUR_BODY_COLLAPSED):
            with self.subTest(value=value):
                self.assertEqual(emptyrender.classify_body(value),
                                 emptyrender.classify_body(value,
                                                           template=None,
                                                           values=None))
                self.assertEqual(
                    emptyrender.classify_subject(value),
                    emptyrender.classify_subject(value, template=None,
                                                 values=None))

    def test_the_scan_entry_still_carries_no_prospect_identifier(self):
        """A caller may log a fifth-shape finding into any channel."""
        entry = emptyrender.scan([row_352()], steps=STEPS_352)["pending"][0]
        self.assertEqual(set(entry), {"row", "lead", "step", "status",
                                      "faults"})
        text = str(entry)
        for leaked in ("Julian", "Example Agency", "@", "agencies"):
            self.assertNotIn(leaked, text)

    def test_summarise_counts_the_fifth_shape_like_the_others(self):
        line = emptyrender.summarise(
            emptyrender.scan([row_352()], steps=STEPS_352))
        self.assertIn(f"subject/{emptyrender.COLLAPSED}", line)


if __name__ == "__main__":
    unittest.main()
