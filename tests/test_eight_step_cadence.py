"""TASK-028: an eight-step email cadence without changing what em5 means.

The hazard: `EMAIL_LADDER` is global and indexed by ordinal. Appending
three rungs would silently change what `em5` means for the five-step
cadence that is ALREADY STAGED at a provider with nine real leads.

These tests prove:
1. em5 of the five-step cadence still resolves to the breakup rung
2. The eight-step cadence resolves eight distinct purposes, none None
3. `purpose_for` beyond a ladder's length returns None
4. Touch count over twenty-one days matches configured caps
5. Both cadences are selectable by name and neither changes the other
"""
import unittest

from src import cadencelibrary, generate


# The breakup rung as it stands today - rung 5 of the five-step ladder.
# This is the EXACT TEXT that must not change for the five-step cadence.
BREAKUP_RUNG = (
    "Close the loop. Give them an easy no, make no new pitch, ask for nothing "
    "beyond permission to stop."
)


class TestEm5OfFiveStepCadenceIsUnchanged(unittest.TestCase):
    """THE REGRESSION TEST. Written first, must pass before AND after.

    EmailBison campaign 481 is staged with nine real leads carrying
    approved subject_5/body_5. A regeneration after a ladder change would
    rewrite the final email of a live sequence into a different message
    without anybody choosing that.
    """

    def test_purpose_for_email_5_is_the_breakup_on_five_step_cadence(self):
        seq = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        purpose = generate.purpose_for("email", 5, sequence=seq)
        self.assertEqual(purpose, BREAKUP_RUNG)

    def test_purpose_for_email_5_is_the_breakup_with_no_sequence(self):
        """Backward compatibility: callers without a sequence get the
        default ladder, which is the five-step one."""
        purpose = generate.purpose_for("email", 5)
        self.assertEqual(purpose, BREAKUP_RUNG)

    def test_step_block_em5_resolves_to_breakup(self):
        """The actual call path: step_block computes ordinal from the
        sequence and calls purpose_for with it."""
        seq = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        block = generate.step_block(seq, "em5")
        self.assertEqual(block["purpose"], BREAKUP_RUNG)
        self.assertEqual(block["number"], 5)
        self.assertEqual(block["channel"], "email")


class TestEightStepCadenceResolvesEightDistinctPurposes(unittest.TestCase):
    """The new cadence must have eight distinct, non-None purposes."""

    def test_eight_step_cadence_exists(self):
        seq = cadencelibrary.named("productive_email_eight_v1")
        self.assertIsNotNone(seq, "the eight-step cadence must be selectable")

    def test_eight_email_steps_resolve_eight_distinct_purposes(self):
        seq = cadencelibrary.named("productive_email_eight_v1")
        email_steps = [s for s in seq if s.get("channel") == "email"]
        self.assertEqual(len(email_steps), 8)

        purposes = []
        for step in email_steps:
            block = generate.step_block(seq, step["key"])
            self.assertIsNotNone(block["purpose"],
                                 f"{step['key']} resolved to None purpose")
            purposes.append(block["purpose"])

        self.assertEqual(len(set(purposes)), 8,
                         "eight steps must have eight DISTINCT purposes")

    def test_eight_step_rung_5_is_not_the_breakup(self):
        """In the eight-step ladder, rung 5 is 'the cost of the current
        way of doing it', NOT the breakup. The breakup is rung 8."""
        seq = cadencelibrary.named("productive_email_eight_v1")
        purpose_5 = generate.purpose_for("email", 5, sequence=seq)
        self.assertNotEqual(purpose_5, BREAKUP_RUNG,
                            "rung 5 of the eight-step ladder must not be "
                            "the breakup - that belongs at rung 8")

    def test_eight_step_rung_8_is_the_breakup(self):
        """The breakup moves to rung 8 in the eight-step ladder."""
        seq = cadencelibrary.named("productive_email_eight_v1")
        purpose_8 = generate.purpose_for("email", 8, sequence=seq)
        self.assertIn("close the loop", purpose_8.lower())


class TestPurposeForBeyondLadderLengthReturnsNone(unittest.TestCase):
    """A sequence longer than its ladder has steps nobody decided the job of.
    Silently handing one of them the last rung produces a second closing
    message - which is exactly the duplication the ladder exists to stop."""

    def test_email_beyond_five_step_ladder_returns_none(self):
        seq = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        self.assertIsNone(generate.purpose_for("email", 6, sequence=seq))

    def test_email_beyond_eight_step_ladder_returns_none(self):
        seq = cadencelibrary.named("productive_email_eight_v1")
        self.assertIsNone(generate.purpose_for("email", 9, sequence=seq))

    def test_unknown_channel_returns_none(self):
        self.assertIsNone(generate.purpose_for("sms", 1))


class TestTouchCountAgainstCaps(unittest.TestCase):
    """The eight-step cadence is email-led with zero LinkedIn steps.
    Total is 8 touches over 20 days, well within the configured caps
    (max_touches_per_week: 6, max_touches_total: 12).

    The alternative - eight emails alongside six LinkedIn steps - would be
    fourteen touches, exceeding the total cap of 12 and silently dropping
    steps. That is the exact failure cadencelibrary's docstring warns about.
    """

    def test_eight_step_cadence_has_eight_touches(self):
        seq = cadencelibrary.named("productive_email_eight_v1")
        s = cadencelibrary.shape(seq)
        self.assertEqual(s["email"], 8)
        self.assertEqual(s["linkedin"], 0)
        self.assertEqual(s["total"], 8)

    def test_eight_step_cadence_fits_in_twenty_one_days(self):
        seq = cadencelibrary.named("productive_email_eight_v1")
        s = cadencelibrary.shape(seq)
        self.assertLessEqual(s["days"], 21)

    def test_weekly_touch_count_does_not_exceed_six(self):
        """The configured weekly cap is 6. No week of the eight-step
        cadence may exceed it, or steps would be silently dropped."""
        seq = cadencelibrary.named("productive_email_eight_v1")
        weekly = {}
        for step in seq:
            week = (step["day"] - 1) // 7 + 1
            weekly[week] = weekly.get(week, 0) + 1
        for week, count in weekly.items():
            self.assertLessEqual(count, 6,
                                 f"week {week} has {count} touches, "
                                 f"exceeding the configured cap of 6")

    def test_total_touch_count_within_configured_max(self):
        """The configured max_touches_total must accommodate 8 touches.
        The email-led approach (zero LinkedIn) fits within the existing
        cap of 12 that was set for the eleven-touch li_heavy cadence."""
        from src import clients
        config = clients.load("productive")
        fatigue = config.get("fatigue", {})
        contact = fatigue.get("contact", {})
        max_total = contact.get("max_touches_total")
        seq = cadencelibrary.named("productive_email_eight_v1")
        total = cadencelibrary.shape(seq)["total"]
        self.assertGreaterEqual(max_total, total,
                                f"max_touches_total ({max_total}) is below "
                                f"the cadence's {total} touches - steps "
                                f"would be silently dropped")


class TestBothCadencesSelectableByName(unittest.TestCase):
    """Neither cadence changes the other."""

    def test_five_step_is_selectable(self):
        seq = cadencelibrary.named("productive_li_heavy_v1")
        self.assertIsNotNone(seq)
        self.assertEqual(len(seq), len(cadencelibrary.PRODUCTIVE_LI_HEAVY_V1))

    def test_eight_step_is_selectable(self):
        seq = cadencelibrary.named("productive_email_eight_v1")
        self.assertIsNotNone(seq)

    def test_five_step_email_count_unchanged(self):
        seq = cadencelibrary.named("productive_li_heavy_v1")
        email_steps = [s for s in seq if s.get("channel") == "email"]
        self.assertEqual(len(email_steps), 5)

    def test_five_step_purposes_unchanged(self):
        """Every email purpose of the five-step cadence is exactly what
        it was before the eight-step cadence was added."""
        seq = cadencelibrary.named("productive_li_heavy_v1")
        email_steps = [s for s in seq if s.get("channel") == "email"]
        for step in email_steps:
            block = generate.step_block(seq, step["key"])
            expected = generate.EMAIL_LADDER[block["number"] - 1]
            self.assertEqual(block["purpose"], expected,
                             f"{step['key']} purpose changed")

    def test_eight_step_does_not_alter_five_step_ladder(self):
        """The EMAIL_LADDER constant itself must not change."""
        self.assertEqual(len(generate.EMAIL_LADDER), 5)
        self.assertEqual(generate.EMAIL_LADDER[4], BREAKUP_RUNG)


class TestPurposeSurvivesValidateSteps(unittest.TestCase):
    """THE REVIEW TEST. Drive purpose_for through cadence.steps_for(),
    exactly as generate does - never by passing a library constant in.

    cadence.steps_for() runs every sequence through validate_steps(), which
    returns a new tuple of new dicts. id() and content equality both fail
    against the library constant. If the ladder lookup cannot survive this
    path, steps 6/7/8 of the eight-step cadence get NO PURPOSE AT ALL
    through the path production actually uses.
    """

    def _steps_for_cadence(self, name):
        from src import cadence
        config = {"cadence": name}
        return cadence.steps_for(config=config)

    def test_eight_step_rungs_6_7_8_have_purpose_through_steps_for(self):
        """Steps 6, 7 and 8 must resolve to non-None purposes when the
        sequence comes from cadence.steps_for() - the production path."""
        seq = self._steps_for_cadence("productive_email_eight_v1")
        for rung, key in [(6, "em6"), (7, "em7"), (8, "em8")]:
            _, ordinal, _ = generate.position(seq, key)
            self.assertEqual(ordinal, rung)
            purpose = generate.purpose_for("email", ordinal, sequence=seq)
            self.assertIsNotNone(
                purpose,
                f"{key} (rung {rung}) resolved to None through the "
                f"production path - the ladder lookup did not survive "
                f"validate_steps()")

    def test_five_step_em5_is_breakup_through_steps_for(self):
        """The mirror: a record selecting the five-step cadence, driven
        through cadence.steps_for(), still gets the breakup at em5."""
        seq = self._steps_for_cadence("productive_li_heavy_v1")
        _, ordinal, _ = generate.position(seq, "em5")
        self.assertEqual(ordinal, 5)
        purpose = generate.purpose_for("email", ordinal, sequence=seq)
        self.assertEqual(purpose, BREAKUP_RUNG)

    def test_steps_for_result_is_not_the_library_tuple(self):
        """Prove that steps_for returns a different object than the library.
        This is WHY id()-keyed lookup fails and name-keyed lookup is needed."""
        from src import cadencelibrary
        seq = self._steps_for_cadence("productive_email_eight_v1")
        self.assertIsNot(
            seq, cadencelibrary.PRODUCTIVE_EMAIL_EIGHT_V1,
            "steps_for should return a validated copy, not the library tuple")

    def test_ladder_name_for_survives_steps_for(self):
        """ladder_name_for must return the correct ladder name when given
        the validated steps from cadence.steps_for(), not just the library
        constant."""
        from src import cadencelibrary
        seq = self._steps_for_cadence("productive_email_eight_v1")
        self.assertEqual(
            cadencelibrary.ladder_name_for(seq, "email"), "email_eight")
        seq5 = self._steps_for_cadence("productive_li_heavy_v1")
        self.assertEqual(
            cadencelibrary.ladder_name_for(seq5, "email"), "email_five")


if __name__ == "__main__":
    unittest.main()
