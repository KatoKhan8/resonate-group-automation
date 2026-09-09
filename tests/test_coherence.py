"""Do a contact's email and LinkedIn steps read as one conversation?

The checks here are the ones no existing module was making. `duplicates.py`
compares emails to emails, `cadence.cross_channel_leaks` catches a step naming
the other channel, and `eligibility.decide` judges one step at a time. None of
them looks at the sequence as the prospect experiences it.

Each test below is a message somebody could actually receive.
"""
import unittest

from src import cadence, coherence, duplicates

LONG = ("We run delivery teams across several clients and utilisation is how "
        "the studio gets measured every single month around here.")
OTHER = ("Project margin is the number your board asks about and it is "
         "usually the one that arrives two weeks after the month closes.")


def steps(*rows):
    """(key, day, channel, text) into the shape cadence produces."""
    out = {}
    for key, day, channel, text in rows:
        step = {"day": day, "channel": channel, "status": "eligible"}
        if channel == "linkedin":
            step["note"] = text
        else:
            step["body"] = text
            step["subject"] = "a subject"
        out[key] = step
    return out


def kinds(findings):
    return [f["kind"] for f in findings]


class TestDuplicateAcrossChannels(unittest.TestCase):
    def test_the_same_argument_on_two_channels_is_a_blocker(self):
        found = coherence.duplicate_across_channels(coherence._ordered(
            steps(("day1", 1, "email", LONG), ("day3", 3, "linkedin", LONG))))
        self.assertEqual(kinds(found), ["duplicate_across_channels"])
        self.assertEqual(found[0]["severity"], coherence.BLOCK)

    def test_two_emails_are_left_to_the_module_that_owns_them(self):
        """`duplicates.py` reports same-channel pairs. Two findings for one
        problem makes a reviewer think there are two problems."""
        found = coherence.duplicate_across_channels(coherence._ordered(
            steps(("day1", 1, "email", LONG), ("day5", 5, "email", LONG))))
        self.assertEqual(found, [])

    def test_different_arguments_are_not_flagged(self):
        found = coherence.duplicate_across_channels(coherence._ordered(
            steps(("day1", 1, "email", LONG), ("day3", 3, "linkedin", OTHER))))
        self.assertEqual(found, [])

    def test_two_empty_notes_are_not_a_duplicate(self):
        """Otherwise every short greeting matches every other one."""
        found = coherence.duplicate_across_channels(coherence._ordered(
            steps(("day3", 3, "linkedin", "hi"), ("day8", 8, "linkedin", "hi"))))
        self.assertEqual(found, [])

    def test_the_finding_names_both_steps(self):
        found = coherence.duplicate_across_channels(coherence._ordered(
            steps(("day1", 1, "email", LONG), ("day3", 3, "linkedin", LONG))))
        self.assertEqual(sorted(found[0]["steps"]), ["day1", "day3"])


class TestRepeatedOpening(unittest.TestCase):
    def test_two_steps_opening_the_same_way_are_reported(self):
        found = coherence.repeated_opening(coherence._ordered(steps(
            ("day1", 1, "email",
             "Hi Mara, noticed you opened a Manchester office. " + LONG),
            ("day15", 15, "email",
             "Hi Mara, noticed you opened a Manchester office. " + OTHER))))
        self.assertEqual(kinds(found), ["repeated_opening"])

    def test_a_full_duplicate_is_not_also_reported_as_an_opening(self):
        found = coherence.repeated_opening(coherence._ordered(
            steps(("day1", 1, "email", LONG), ("day5", 5, "email", LONG))))
        self.assertEqual(found, [])

    def test_different_openings_are_not_flagged(self):
        found = coherence.repeated_opening(coherence._ordered(steps(
            ("day1", 1, "email", "Hi Mara, noticed the Manchester office. " + LONG),
            ("day15", 15, "email", "Hi Mara, your note on billable time. " + OTHER))))
        self.assertEqual(found, [])

    def test_a_greeting_alone_is_too_short_to_judge(self):
        found = coherence.repeated_opening(coherence._ordered(
            steps(("day1", 1, "email", "Hi."), ("day5", 5, "email", "Hi."))))
        self.assertEqual(found, [])


class TestRepeatedCta(unittest.TestCase):
    def test_the_same_ask_word_for_word_is_reported(self):
        found = coherence.repeated_cta(coherence._ordered(steps(
            ("day1", 1, "email", LONG + " Worth a look?"),
            ("day5", 5, "email", OTHER + " Worth a look?"))))
        self.assertEqual(kinds(found), ["repeated_cta"])

    def test_asking_once_is_not_a_finding(self):
        found = coherence.repeated_cta(coherence._ordered(steps(
            ("day1", 1, "email", LONG + " Worth a look?"),
            ("day5", 5, "email", OTHER))))
        self.assertEqual(found, [])

    def test_two_different_asks_are_allowed(self):
        """A cadence is allowed to ask more than once. That is what it is."""
        found = coherence.repeated_cta(coherence._ordered(steps(
            ("day1", 1, "email", LONG + " Worth a look?"),
            ("day5", 5, "email", OTHER + " Any interest?"))))
        self.assertEqual(found, [])

    def test_punctuation_and_casing_do_not_hide_a_repeat(self):
        found = coherence.repeated_cta(coherence._ordered(steps(
            ("day1", 1, "email", LONG + " WORTH A LOOK!!"),
            ("day5", 5, "email", OTHER + " worth a look..."))))
        self.assertEqual(kinds(found), ["repeated_cta"])


class TestContradictoryAngles(unittest.TestCase):
    def build(self, *angles):
        out = steps(*[(f"day{i}", i, "email", LONG) for i, _ in enumerate(angles, 1)])
        for (key, step), angle in zip(sorted(out.items()), angles):
            step["angle"] = angle
        return out

    def test_one_angle_is_coherent(self):
        self.assertEqual(coherence.contradictory_angles(
            coherence._ordered(self.build("ops", "ops"))), [])

    def test_two_angles_are_reported(self):
        found = coherence.contradictory_angles(
            coherence._ordered(self.build("ops", "finance")))
        self.assertEqual(kinds(found), ["contradictory_angles"])

    def test_an_unlabelled_step_claims_nothing(self):
        """Absence of a label is not evidence of agreement."""
        rows = steps(("day1", 1, "email", LONG), ("day5", 5, "email", OTHER))
        self.assertEqual(coherence.contradictory_angles(
            coherence._ordered(rows)), [])


class TestOrdering(unittest.TestCase):
    def test_two_channels_on_one_day_is_a_blocker(self):
        found = coherence.ordering_problems(coherence._ordered(
            steps(("a", 3, "email", LONG), ("b", 3, "linkedin", OTHER))))
        self.assertEqual(kinds(found), ["two_channels_one_day"])

    def test_one_channel_twice_on_a_day_is_not_this_check(self):
        found = coherence.ordering_problems(coherence._ordered(
            steps(("a", 3, "email", LONG), ("b", 3, "email", OTHER))))
        self.assertEqual(found, [])

    def test_a_step_with_no_day_is_reported(self):
        rows = steps(("a", 1, "email", LONG))
        rows["a"]["day"] = None
        self.assertEqual(kinds(coherence.ordering_problems(
            coherence._ordered(rows))), ["step_without_a_day"])


class TestAfterTheReply(unittest.TestCase):
    def test_a_live_step_after_the_reply_is_a_blocker(self):
        found = coherence.after_the_pause(coherence._ordered(
            steps(("day8", 8, "email", LONG))), paused_at=5)
        self.assertEqual(kinds(found), ["scheduled_after_reply"])

    def test_a_correctly_paused_step_is_not_a_finding(self):
        rows = steps(("day8", 8, "email", LONG))
        rows["day8"]["status"] = "paused"
        self.assertEqual(coherence.after_the_pause(
            coherence._ordered(rows), paused_at=5), [])

    def test_a_step_before_the_reply_is_untouched(self):
        self.assertEqual(coherence.after_the_pause(coherence._ordered(
            steps(("day1", 1, "email", LONG))), paused_at=5), [])

    def test_a_step_on_the_reply_day_is_included(self):
        """The send and the reply are not ordered within a day, and the safe
        reading of an ambiguous ordering is that it should not have gone."""
        found = coherence.after_the_pause(coherence._ordered(
            steps(("day5", 5, "email", LONG))), paused_at=5)
        self.assertEqual(kinds(found), ["scheduled_after_reply"])

    def test_nothing_is_claimed_when_there_was_no_reply(self):
        self.assertEqual(coherence.after_the_pause(coherence._ordered(
            steps(("day8", 8, "email", LONG))), paused_at=None), [])


class TestIneligibleChannel(unittest.TestCase):
    def test_a_live_step_on_a_closed_channel_is_a_blocker(self):
        found = coherence.ineligible_channel(
            coherence._ordered(steps(("day1", 1, "email", LONG))),
            {"email_eligible": False, "email_excluded_reason": "mx"})
        self.assertEqual(kinds(found), ["ineligible_channel"])

    def test_a_correctly_skipped_step_is_not_a_finding(self):
        rows = steps(("day1", 1, "email", LONG))
        rows["day1"]["status"] = "skipped"
        self.assertEqual(coherence.ineligible_channel(
            coherence._ordered(rows),
            {"email_eligible": False, "email_excluded_reason": "mx"}), [])

    def test_the_other_channel_is_untouched(self):
        found = coherence.ineligible_channel(
            coherence._ordered(steps(("day3", 3, "linkedin", OTHER))),
            {"email_eligible": False, "linkedin_eligible": True})
        self.assertEqual(found, [])

    def test_nothing_is_claimed_without_a_verdict(self):
        self.assertEqual(coherence.ineligible_channel(
            coherence._ordered(steps(("day1", 1, "email", LONG))), None), [])


class TestTheVerdict(unittest.TestCase):
    def test_a_blocker_is_never_averaged_away(self):
        self.assertEqual(coherence.verdict([
            {"severity": coherence.NOTE}, {"severity": coherence.BLOCK},
            {"severity": coherence.REVIEW}]), coherence.BLOCK)

    def test_review_outranks_a_note(self):
        self.assertEqual(coherence.verdict([
            {"severity": coherence.NOTE}, {"severity": coherence.REVIEW}]),
            coherence.REVIEW)

    def test_nothing_found_is_a_pass(self):
        self.assertEqual(coherence.verdict([]), "pass")

    def test_the_summary_counts_every_contact(self):
        summary = coherence.summarise([
            {"verdict": "pass", "findings": []},
            {"verdict": coherence.BLOCK,
             "findings": [{"kind": "repeated_cta", "severity": coherence.BLOCK}]},
        ])
        self.assertEqual(summary["contacts_checked"], 2)
        self.assertEqual(summary["blocked"], 1)
        self.assertEqual(summary["by_kind"], {"repeated_cta": 1})


class TestItReusesRatherThanReimplements(unittest.TestCase):
    def test_normalisation_comes_from_duplicates(self):
        """Two modules with two ideas of "the same text" is two bugs."""
        import inspect
        source = inspect.getsource(coherence)
        self.assertIn("duplicates.normalize", source)
        self.assertIn("duplicates.same_body", source)

    def test_the_leak_check_comes_from_cadence(self):
        import inspect
        self.assertIn("cadence.cross_channel_leaks",
                      inspect.getsource(coherence))

    def test_it_decides_no_eligibility_of_its_own(self):
        """`eligibility.decide` is the one place that answers "may this go".

        Checked on the call graph rather than the text: the module docstring
        names `eligibility.decide` precisely to say it is not this module's
        job, and a substring search cannot tell an explanation from a call.
        """
        import ast
        import inspect
        tree = ast.parse(inspect.getsource(coherence))
        called = {ast.unparse(node.func) for node in ast.walk(tree)
                  if isinstance(node, ast.Call)}
        for banned in ("eligibility.decide", "lint.sendable",
                       "channels.evaluate", "push.payloads"):
            self.assertNotIn(banned, called, banned)


if __name__ == "__main__":
    unittest.main()
