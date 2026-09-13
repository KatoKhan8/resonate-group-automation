"""lint.py: every rule in BUILD-SPEC section 6, one test at a time."""
import unittest

from src import lint

BODY_40 = " ".join(["word"] * 40)


def body(n):
    return " ".join(["word"] * n)


def contact(confirmed=True, **kw):
    """A contact carrying the evidence a really-verified one carries.

    `confirmed=True` means two independent providers said valid, which is what
    the default policy requires. Passing `confirmed=False` leaves only the
    legacy fields, which is one confirmation and therefore not sendable - the
    shape a record enriched before double verification has.
    """
    from src import verification
    c = {"name": "Ivana Saric", "title": "Head of Finance",
         "email": "ivana.saric@meridian.test", "angle": "finance", "verdict": "valid",
         "reoon": None}
    c.update(kw)
    if confirmed and c.get("verdict") == "valid" and c.get("email"):
        evidence = [verification.result("contactout", verification.S_VALID,
                                        c["email"]),
                    verification.result("deliverable", verification.S_VALID,
                                        c["email"])]
        verification.apply(c, verification.decide(evidence), evidence)
    return c


def record(lane="cold", contacts=None, subject="a subject that is fine",
           text=BODY_40, key="ivana-saric", **kw):
    r = {"id": "meridian", "lane": lane, "client": "productive", "company": "Meridian",
         "domain": "meridian.test", "state": "drafted", "drop_reason": None,
         "contacts": [contact()] if contacts is None else contacts,
         "diagnosis": None, "hook": "raised a seed round in May", "log": [],
         "cadence": {key: {"day1": {"channel": "email", "generated": True,
                                    "subject": subject, "body": text}}}}
    r.update(kw)
    return r


def fails(**kw):
    r = record(**kw)
    key = next(iter(r["cadence"]))
    return lint.check(r, key, r["cadence"][key]["day1"])


class TestCleanBaseline(unittest.TestCase):
    def test_a_clean_draft_trips_nothing(self):
        self.assertEqual(fails(), [])


class TestRecipient(unittest.TestCase):
    def test_recipient_must_be_in_this_records_own_contact_list(self):
        self.assertIn("recipient_not_on_record", fails(key="someone-else"))

    def test_contact_with_no_address(self):
        self.assertIn("recipient_missing", fails(contacts=[contact(email="")]))

    def test_recipient_must_be_sendable(self):
        self.assertIn("recipient_not_sendable",
                      fails(contacts=[contact(verdict="unknown")]))


class TestSendability(unittest.TestCase):
    """Section 6.1, including the catch-all trap from section 9."""

    def test_valid_is_sendable(self):
        self.assertTrue(lint.sendable(contact(verdict="valid")))

    def test_one_valid_alone_is_not_sendable(self):
        """Section 6.1 says what a good address looks like. The policy says
        how many independent providers have to say so, and that is two."""
        self.assertFalse(lint.sendable(contact(confirmed=False, verdict="valid")))

    def test_invalid_and_unknown_are_not(self):
        self.assertFalse(lint.sendable(contact(verdict="invalid")))
        self.assertFalse(lint.sendable(contact(verdict="unknown")))

    def test_accept_all_needs_a_passing_reoon(self):
        """The 6.1 rule itself, isolated from the confirmation count: a
        catch-all clears only where Reoon's own safety field says so."""
        from src import verification
        single = dict(verification.DEFAULT_POLICY, required_confirmations=1)

        def decide(reoon):
            c = contact(confirmed=False, verdict="accept_all", reoon=reoon)
            return verification.decide(verification.all_evidence(c),
                                       single)["sendable"]

        safe = {"is_deliverable": True, "is_safe_to_send": True, "overall_score": 92}
        unsafe = {"is_deliverable": True, "is_safe_to_send": False, "overall_score": 75}
        self.assertTrue(decide(safe))
        self.assertFalse(decide(unsafe))
        self.assertFalse(decide(None))
        self.assertFalse(decide({"is_deliverable": True}))

    def test_a_catch_all_cleared_by_reoon_alone_is_held_under_the_real_policy(self):
        safe = {"is_deliverable": True, "is_safe_to_send": True, "overall_score": 92}
        self.assertFalse(lint.sendable(contact(confirmed=False,
                                               verdict="accept_all", reoon=safe)))

    def test_missing_contact_is_not_sendable(self):
        self.assertFalse(lint.sendable(None))
        self.assertFalse(lint.sendable({}))


class TestDashes(unittest.TestCase):
    def test_the_draft_prompt_lists_every_banned_phrase(self):
        """A rule lint enforces and the prompt never states is a coin flip.

        Measured 2026-09-13 across the twenty-account cohort: `em5` - the
        step whose job is to close the loop - failed lint three times on
        `filler_phrase` for almost every record and was never stored, so no
        contact could be staged. The model reached for "just following up"
        and "circling back" because a closing message naturally does, and
        the prompt said only "No filler openers".

        The phrases are listed in `prompts/draft.md` rather than templated
        in, which makes this a second representation of `BANNED_PHRASES`.
        This test is what stops the two drifting - cheaper than a templating
        change and it fails the moment somebody adds a phrase to one and not
        the other.
        """
        import os

        from src import generate

        with open(os.path.join(generate.PROMPTS, "draft.md"),
                  encoding="utf-8") as f:
            prompt = f.read().lower()
        for phrase in lint.BANNED_PHRASES:
            self.assertIn(phrase, prompt,
                          f"lint refuses {phrase!r} and the prompt never says so")

    def test_a_curly_apostrophe_fails(self):
        """Two of sixteen generated drafts carried one and passed.

        It is the character that becomes "you?re" the moment anything in the
        chain guesses the wrong encoding, and that is how it was found.
        """
        self.assertIn("em_dash", fails(text=BODY_40 + " you’re right"))

    def test_a_non_breaking_hyphen_fails(self):
        """Not a hyphen to a client without the glyph. A box."""
        self.assertIn("em_dash", fails(text=BODY_40 + " month‑end"))

    def test_an_accented_name_is_not_substituted_punctuation(self):
        """Mueller and strasse are somebody's name and somebody's street.

        A rule refusing every non-ASCII character would refuse half the
        market this client sells to, which is why the constant lists five
        substitutions for characters already on the keyboard rather than a
        codepoint range.
        """
        self.assertNotIn("em_dash",
                         fails(text=BODY_40 + " Müller on the straße"))

    def test_em_dash_in_body(self):
        self.assertIn("em_dash", fails(text=BODY_40 + " word—word"))

    def test_en_dash_in_body(self):
        self.assertIn("em_dash", fails(text=BODY_40 + " word–word"))

    def test_dash_in_subject(self):
        self.assertIn("em_dash", fails(subject="picking this up — quickly"))

    def test_hyphen_is_fine(self):
        self.assertNotIn("em_dash", fails(text=BODY_40 + " month-end"))


class TestAttachments(unittest.TestCase):
    def test_real_attachment_talk_fails(self):
        for phrase in ("Screenshot attached.", "please find attached the deck",
                       "I've attached the rate card", "attached is the list",
                       "the attachment explains it", "deck attached"):
            self.assertIn("attachment", fails(text=BODY_40 + " " + phrase), phrase)

    def test_the_idiom_passes(self):
        """Section 6.2 calls this out by name: do not naively match 'attach'."""
        self.assertNotIn("attachment", fails(text=BODY_40 + " with no pitch attached"))


class TestPlaceholders(unittest.TestCase):
    def test_square_curly_and_angle_placeholders_fail(self):
        for ph in ("[FIRST NAME]", "{company}", "<their metric>"):
            self.assertIn("placeholder", fails(text=BODY_40 + " " + ph), ph)

    def test_a_url_is_not_a_placeholder(self):
        self.assertNotIn("placeholder",
                         fails(text=BODY_40 + " <https://example.com/get-started/>"))

    def test_a_placeholder_in_the_subject_fails(self):
        """Section 6.2 does not scope this rule to the body."""
        self.assertIn("placeholder", fails(subject="a question for [FIRST NAME]"))
        self.assertIn("placeholder", fails(subject="{company} and month end"))

    def test_a_url_in_the_subject_is_not_a_placeholder(self):
        self.assertNotIn("placeholder", fails(subject="<https://example.com/>"))


class TestLength(unittest.TestCase):
    def test_word_count_boundaries(self):
        self.assertIn("body_too_short", fails(text=body(39)))
        self.assertNotIn("body_too_short", fails(text=body(40)))
        self.assertNotIn("body_too_long", fails(text=body(180)))
        self.assertIn("body_too_long", fails(text=body(181)))

    def test_subject_boundaries(self):
        self.assertNotIn("subject_too_long", fails(subject="s" * 59))
        self.assertIn("subject_too_long", fails(subject="s" * 60))
        self.assertIn("subject_missing", fails(subject=""))


class TestHardWrap(unittest.TestCase):
    def test_a_wrapped_paragraph_fails(self):
        self.assertIn("hard_wrapped", fails(text=body(20) + "\n" + body(20)))

    def test_blank_line_separated_paragraphs_pass(self):
        self.assertNotIn("hard_wrapped", fails(text=body(20) + "\n\n" + body(20)))

    def test_trailing_newlines_are_not_a_wrap(self):
        self.assertNotIn("hard_wrapped", fails(text=BODY_40 + "\n\n"))

    def test_crlf_paragraphs_are_not_a_false_wrap(self):
        """git on Windows converts line endings; CRLF is still one line per paragraph."""
        self.assertNotIn("hard_wrapped", fails(text=body(20) + "\r\n\r\n" + body(20)))
        self.assertIn("hard_wrapped", fails(text=body(20) + "\r\n" + body(20)))


class TestFiller(unittest.TestCase):
    def test_every_banned_phrase_is_caught(self):
        for phrase in lint.BANNED_PHRASES:
            self.assertIn("filler_phrase", fails(text=phrase + " " + BODY_40), phrase)

    def test_case_is_ignored(self):
        self.assertIn("filler_phrase", fails(text="Just Following Up. " + BODY_40))


class TestLaneRules(unittest.TestCase):
    def test_revive_needs_a_diagnosis(self):
        self.assertIn("revive_no_diagnosis", fails(lane="revive", diagnosis=None))
        self.assertNotIn("revive_no_diagnosis",
                         fails(lane="revive",
                               diagnosis={"died_because": "asked a question, never answered"}))

    def test_cold_needs_a_hook(self):
        self.assertIn("cold_no_hook", fails(lane="cold", hook=None))
        self.assertNotIn("cold_no_hook", fails(lane="cold"))

    def test_domains_needs_an_angle_on_every_contact(self):
        self.assertIn("domains_contact_no_angle",
                      fails(lane="domains", contacts=[contact(angle=None)]))
        self.assertNotIn("domains_contact_no_angle", fails(lane="domains"))


class TestStepSelection(unittest.TestCase):
    def test_linkedin_steps_are_not_linted(self):
        r = record()
        r["cadence"]["ivana-saric"]["day3"] = {
            "channel": "linkedin", "note": "hi petra, short note"}
        self.assertEqual([day for _, day, _ in lint.email_steps(r)], ["day1"])

    def test_unexpanded_templates_are_not_linted(self):
        r = record()
        r["cadence"]["ivana-saric"]["day5"] = {
            "channel": "email", "template": "ops_pain", "vars": {"line": "x"}}
        self.assertEqual([day for _, day, _ in lint.email_steps(r)], ["day1"])


class TestUnshippableRecords(unittest.TestCase):
    """A dropped record must never ship, however clean its draft is.

    Regression: lint checked the draft and the recipient but never the record's
    own state, so a suppressed live account with a clean draft reached
    emailbison.csv. Section 9, trap 6.
    """

    def test_a_dropped_record_fails_however_clean_the_draft(self):
        self.assertEqual(fails(), [])
        self.assertIn("record_dropped",
                      fails(state="dropped", drop_reason="suppressed (live account)"))

    def test_an_already_pushed_record_is_not_sent_twice(self):
        self.assertIn("record_already_pushed", fails(state="pushed"))

    def test_being_dropped_is_a_hard_failure_not_an_amber_hold(self):
        self.assertEqual(lint.classify(["record_dropped"]), "failed")

    def test_a_live_state_ships_normally(self):
        for state in ("queued", "enriched", "verified", "drafted", "approved", "held"):
            self.assertEqual(fails(state=state), [], state)


class TestClassify(unittest.TestCase):
    def test_three_outcomes(self):
        self.assertEqual(lint.classify([]), "clean")
        self.assertEqual(lint.classify(["recipient_not_sendable"]), "held")
        self.assertEqual(lint.classify(["em_dash"]), "failed")
        self.assertEqual(lint.classify(["recipient_not_sendable", "em_dash"]), "failed")


class TestCodesAreStable(unittest.TestCase):
    def test_failures_are_sorted_and_deduped(self):
        got = fails(text="i wanted to reach out. circling back. " + body(2))
        self.assertEqual(got, sorted(set(got)))
        self.assertEqual(got.count("filler_phrase"), 1)


if __name__ == "__main__":
    unittest.main()
