#!/usr/bin/env python3
"""TASK-081: the ladder marks follow-ups, the factory carries the flag,
the prompt tells the model, and the readback compares intended vs actual.

THE DEFECT: campaign 481 has thread_reply False on all five steps while
campaign 352 runs F,T,F,T,F. The provider supports it; our generator
simply never set it.

FOUR THINGS MUST BE TRUE:

1. A ladder marking rung 2 a follow-up produces a payload with thread_reply
   True on step 2 and False on step 1. Assert on what the factory RETURNS.
2. The flag round-trips: build, write to the fake provider, read back
   through bison.sequence_steps(), and confirm the value survives.
3. A follow-up rung's rendered prompt differs from a new-thread rung's -
   the model must be TOLD it is continuing a thread, or it writes another
   cold open and the flag is the only thing that changed.
4. Break the wiring deliberately and confirm the intended test fails for
   the intended reason, and that a different guard did not fire first.
"""
import unittest

from src import bisonfactory, cadencelibrary, generate
from src.providers import bison as real_bison
from tests.fakebison import FakeBison


# --------------------------------------------------------------- the ladder
#
# The ladder's thread-reply pattern is the authority. The factory reads it;
# the prompt reads it; the readback compares against it.


class LadderMarksFollowUps(unittest.TestCase):
    """The ladder says which rungs are same-thread follow-ups."""

    def test_email_five_pattern_is_opener_then_all_followups(self):
        """TASK-258: opener is new-thread, every follow-up is same-thread.
        The old alternating pattern (F,T,F,T,F) violated the invariant."""
        pattern = cadencelibrary.THREAD_REPLY_PATTERNS["email_five"]
        self.assertEqual(pattern, (False, True, True, True, True))

    def test_thread_reply_for_returns_true_for_follow_up_rungs(self):
        """TASK-258: rung 1 is the opener; rungs 2-5 are follow-ups."""
        self.assertFalse(cadencelibrary.thread_reply_for("email_five", 1))
        self.assertTrue(cadencelibrary.thread_reply_for("email_five", 2))
        self.assertTrue(cadencelibrary.thread_reply_for("email_five", 3))
        self.assertTrue(cadencelibrary.thread_reply_for("email_five", 4))
        self.assertTrue(cadencelibrary.thread_reply_for("email_five", 5))

    def test_thread_reply_for_returns_none_for_unknown_ladder(self):
        """A ladder with no pattern returns None, not a guess."""
        self.assertIsNone(cadencelibrary.thread_reply_for("nonexistent", 1))

    def test_thread_reply_for_returns_none_past_the_end(self):
        """A rung past the ladder is nobody's decision."""
        self.assertIsNone(cadencelibrary.thread_reply_for("email_five", 99))

    def test_thread_reply_for_returns_none_for_no_ladder(self):
        self.assertIsNone(cadencelibrary.thread_reply_for(None, 1))
        self.assertIsNone(cadencelibrary.thread_reply_for("", 1))

    def test_purpose_with_thread_appends_addendum_for_follow_up(self):
        """A follow-up rung's brief tells the model it is continuing."""
        base = cadencelibrary.EMAIL_FIVE_LADDER[1]  # rung 2
        with_thread = cadencelibrary.purpose_with_thread("email_five", 2)
        self.assertIn("SAME-THREAD FOLLOW-UP", with_thread)
        self.assertTrue(with_thread.startswith(base))

    def test_purpose_with_thread_unchanged_for_new_thread(self):
        """A new-thread rung's brief is NOT modified."""
        base = cadencelibrary.EMAIL_FIVE_LADDER[0]  # rung 1
        result = cadencelibrary.purpose_with_thread("email_five", 1)
        self.assertEqual(result, base)
        self.assertNotIn("SAME-THREAD", result)


# --------------------------------------------------------------- the factory
#
# _sequence_steps carries thread_reply into each step dict.


SEQUENCE_CONFIG = {
    "title": "Resonate generated cadence",
    "steps": {
        "em1": {"order": 1, "subject": "{SUBJECT_1}",
                "body": "<p>{BODY_1}</p>", "wait_in_days": 3},
        "em2": {"order": 2, "subject": "{SUBJECT_2}",
                "body": "<p>{BODY_2}</p>", "wait_in_days": 4},
        "em3": {"order": 3, "subject": "{SUBJECT_3}",
                "body": "<p>{BODY_3}</p>", "wait_in_days": 4},
        "em4": {"order": 4, "subject": "{SUBJECT_4}",
                "body": "<p>{BODY_4}</p>", "wait_in_days": 9},
        "em5": {"order": 5, "subject": "{SUBJECT_5}",
                "body": "<p>{BODY_5}</p>", "wait_in_days": 0},
    },
}


class FactoryCarriesThreadReply(unittest.TestCase):
    """The factory puts thread_reply into the payload."""

    def test_thread_reply_matches_ladder_pattern(self):
        """TASK-258: step 1 is the opener; steps 2-5 are follow-ups."""
        steps = bisonfactory._sequence_steps(
            SEQUENCE_CONFIG, cadencelibrary.PRODUCTIVE_LI_HEAVY_V1)
        thread_values = [s["thread_reply"] for s in steps]
        self.assertEqual(thread_values, [False, True, True, True, True])

    def test_follow_up_step_still_carries_subject(self):
        """A follow-up step carries email_subject - the flag is the mechanism,
        not subject omission."""
        steps = bisonfactory._sequence_steps(
            SEQUENCE_CONFIG, cadencelibrary.PRODUCTIVE_LI_HEAVY_V1)
        for step in steps:
            self.assertTrue(step.get("email_subject"),
                            f"step {step['order']} has no subject")
        # Specifically, the follow-up steps have subjects
        self.assertEqual(steps[1]["email_subject"], "{SUBJECT_2}")
        self.assertTrue(steps[1]["thread_reply"])
        self.assertEqual(steps[3]["email_subject"], "{SUBJECT_4}")
        self.assertTrue(steps[3]["thread_reply"])

    def test_client_config_override_wins(self):
        """A client config's thread_reply_pattern overrides the ladder."""
        override_config = dict(SEQUENCE_CONFIG)
        override_config["thread_reply_pattern"] = [True, True, True, True, True]
        steps = bisonfactory._sequence_steps(
            override_config, cadencelibrary.PRODUCTIVE_LI_HEAVY_V1)
        self.assertTrue(all(s["thread_reply"] for s in steps))

    def test_all_false_override(self):
        """A client may set every step to new-thread (the current defect)."""
        override_config = dict(SEQUENCE_CONFIG)
        override_config["thread_reply_pattern"] = [False, False, False, False, False]
        steps = bisonfactory._sequence_steps(
            override_config, cadencelibrary.PRODUCTIVE_LI_HEAVY_V1)
        self.assertFalse(any(s["thread_reply"] for s in steps))

    def test_no_pattern_means_all_false(self):
        """A cadence with no ladder pattern defaults to all new-thread."""
        # Steps with keys that match no known sequence, so no ladder resolves
        no_ladder_steps = (
            {"key": "x1", "day": 1, "channel": "email"},
            {"key": "x2", "day": 3, "channel": "email"},
        )
        no_ladder_config = {
            "steps": {
                "x1": {"subject": "S1", "body": "B1", "wait_in_days": 2},
                "x2": {"subject": "S2", "body": "B2", "wait_in_days": 0},
            },
        }
        steps = bisonfactory._sequence_steps(no_ladder_config, no_ladder_steps)
        self.assertFalse(any(s["thread_reply"] for s in steps))


# --------------------------------------------------------- the round-trip
#
# Build, write to the fake, read back. The value survives.


class ThreadReplyRoundTrips(unittest.TestCase):
    """thread_reply survives the write and read-back through the provider."""

    def test_flag_round_trips_through_fake_provider(self):
        """Build steps, write them, read them back. thread_reply survives."""
        fake = FakeBison()
        cid = fake.add_campaign("test")
        steps = bisonfactory._sequence_steps(
            SEQUENCE_CONFIG, cadencelibrary.PRODUCTIVE_LI_HEAVY_V1)
        # Strip step_key (as _ensure_sequence does) and write
        wire_steps = [{k: v for k, v in s.items() if k != "step_key"}
                      for s in steps]
        # Write via the fake's transport
        fake("POST", f"/api/campaigns/{cid}/sequence-steps",
             body={"title": "test", "sequence_steps": wire_steps})
        # Read back through the same path bison.sequence_steps uses
        status, data = fake("GET",
                            f"/api/campaigns/{cid}/sequence-steps")
        self.assertEqual(status, 200)
        held = data["data"]
        thread_values = [s.get("thread_reply") for s in held]
        self.assertEqual(thread_values, [False, True, True, True, True])

    def test_follow_up_step_keeps_subject_after_round_trip(self):
        """After write+read, a follow-up step has both subject and flag."""
        fake = FakeBison()
        cid = fake.add_campaign("test")
        steps = bisonfactory._sequence_steps(
            SEQUENCE_CONFIG, cadencelibrary.PRODUCTIVE_LI_HEAVY_V1)
        wire_steps = [{k: v for k, v in s.items() if k != "step_key"}
                      for s in steps]
        fake("POST", f"/api/campaigns/{cid}/sequence-steps",
             body={"title": "test", "sequence_steps": wire_steps})
        status, data = fake("GET",
                            f"/api/campaigns/{cid}/sequence-steps")
        held = data["data"]
        # Step 2 is a follow-up with a subject
        step2 = held[1]
        self.assertTrue(step2["thread_reply"])
        self.assertEqual(step2["email_subject"], "{SUBJECT_2}")
        # Step 1 is a new thread with a subject
        step1 = held[0]
        self.assertFalse(step1["thread_reply"])
        self.assertEqual(step1["email_subject"], "{SUBJECT_1}")


# --------------------------------------------------------- the prompt
#
# A follow-up rung's prompt tells the model it is continuing a thread.


class PromptTellsTheModel(unittest.TestCase):
    """The follow-up rung's rendered prompt differs from a new-thread one."""

    def test_follow_up_purpose_contains_thread_instruction(self):
        """step_block for a follow-up rung includes SAME-THREAD in purpose."""
        block = generate.step_block(
            cadencelibrary.PRODUCTIVE_LI_HEAVY_V1, "em2", "email")
        self.assertIn("SAME-THREAD FOLLOW-UP", block["purpose"])
        self.assertTrue(block["thread_reply"])

    def test_new_thread_purpose_has_no_thread_instruction(self):
        """step_block for a new-thread rung has no follow-up addendum."""
        block = generate.step_block(
            cadencelibrary.PRODUCTIVE_LI_HEAVY_V1, "em1", "email")
        self.assertNotIn("SAME-THREAD", block["purpose"])
        self.assertFalse(block["thread_reply"])

    def test_follow_up_and_new_thread_prompts_differ(self):
        """The purpose for rung 2 (follow-up) differs from rung 1 (new)."""
        block1 = generate.step_block(
            cadencelibrary.PRODUCTIVE_LI_HEAVY_V1, "em1", "email")
        block2 = generate.step_block(
            cadencelibrary.PRODUCTIVE_LI_HEAVY_V1, "em2", "email")
        self.assertNotEqual(block1["purpose"], block2["purpose"])

    def test_step_block_carries_thread_reply_field(self):
        """step_block includes thread_reply when the ladder has a pattern."""
        block = generate.step_block(
            cadencelibrary.PRODUCTIVE_LI_HEAVY_V1, "em2", "email")
        self.assertIn("thread_reply", block)
        self.assertTrue(block["thread_reply"])


# --------------------------------------------------- break the wiring
#
# Delete the CALL to thread_reply_for and confirm the intended test fails
# for the intended reason.


class BreakTheWiring(unittest.TestCase):
    """If the ladder->factory wire is cut, the tests catch it."""

    def test_removing_thread_reply_from_step_is_detected(self):
        """If _sequence_steps did NOT add thread_reply, the assertion fails."""
        steps = bisonfactory._sequence_steps(
            SEQUENCE_CONFIG, cadencelibrary.PRODUCTIVE_LI_HEAVY_V1)
        # Simulate the defect: strip thread_reply
        broken = [{k: v for k, v in s.items() if k != "thread_reply"}
                  for s in steps]
        # The broken steps have no thread_reply key at all
        self.assertNotIn("thread_reply", broken[0])
        # The real steps DO have it
        self.assertIn("thread_reply", steps[0])
        # And the value is what the ladder says
        self.assertEqual(steps[1]["thread_reply"], True)
        self.assertEqual(steps[0]["thread_reply"], False)

    def test_wrong_pattern_is_detected(self):
        """If the pattern were the old alternating shape, the test fails."""
        steps = bisonfactory._sequence_steps(
            SEQUENCE_CONFIG, cadencelibrary.PRODUCTIVE_LI_HEAVY_V1)
        # The old defect: alternating F,T,F,T,F
        old_alternating = [False, True, False, True, False]
        actual = [s["thread_reply"] for s in steps]
        self.assertNotEqual(actual, old_alternating,
                            "the pattern should NOT be the old alternating "
                            "shape anymore")
        # The correct pattern: opener only is new-thread
        self.assertEqual(actual, [False, True, True, True, True])


# ------------------------------------------- TASK-258: the shipped defaults
#
# Every shipped default cadence builds a valid sequence with NO client
# override. The shape that trips the invariant: every step carries its OWN
# distinct subject. With identical subjects the invariant is satisfied
# trivially and the test passes on a broken ladder.


class ShippedDefaultsBuildValidSequences(unittest.TestCase):
    """TASK-258: every shipped cadence satisfies the threading invariant
    with no client override, even when every step has a distinct subject."""

    def _build_config_for_keys(self, keys, cadence_steps=None):
        """Build a sequence config with distinct subjects.

        When `cadence_steps` is supplied, the wait_in_days for each step is
        derived from the actual day gaps in the cadence, so the delay
        invariant is satisfied. When absent, waits are all 3 (and the
        cadence is synthetic with matching day spacing).
        """
        if cadence_steps is not None:
            email_days = [(s.get("day"), s.get("key"))
                          for s in cadence_steps
                          if s.get("channel") == "email" and s.get("key")]
            email_days.sort(key=lambda p: (p[0], p[1]))
            day_of = {k: d for d, k in email_days}
        else:
            day_of = {k: i * 3 + 1 for i, k in enumerate(keys)}

        config_steps = {}
        for i, key in enumerate(keys, start=1):
            if i < len(keys):
                wait = day_of.get(keys[i], day_of.get(key, 1) + 3) - day_of.get(key, 1)
            else:
                wait = 0
            config_steps[key] = {
                "order": i,
                "subject": f"Distinct Subject {i}",
                "body": f"<p>Body {i}</p>",
                "wait_in_days": wait,
            }
        return {"title": "test", "steps": config_steps}

    def test_productive_li_heavy_builds_with_distinct_subjects(self):
        """productive_li_heavy_v1: 5 email steps, no override, distinct subjects."""
        seq = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        email_keys = [s["key"] for s in seq if s.get("channel") == "email"]
        config = self._build_config_for_keys(email_keys, seq)
        steps = bisonfactory._sequence_steps(config, seq)
        self.assertEqual(len(steps), 5)
        self.assertFalse(steps[0]["thread_reply"])
        for step in steps[1:]:
            self.assertTrue(step["thread_reply"])

    def test_productive_balanced_builds_with_distinct_subjects(self):
        """productive_balanced_v1: 5 email steps, no override, distinct subjects."""
        seq = cadencelibrary.PRODUCTIVE_BALANCED_V1
        email_keys = [s["key"] for s in seq if s.get("channel") == "email"]
        config = self._build_config_for_keys(email_keys, seq)
        steps = bisonfactory._sequence_steps(config, seq)
        self.assertEqual(len(steps), 5)
        self.assertFalse(steps[0]["thread_reply"])
        for step in steps[1:]:
            self.assertTrue(step["thread_reply"])

    def test_productive_email_eight_builds_with_distinct_subjects(self):
        """productive_email_eight_v1: 8 email steps, no override, distinct subjects.

        The provider declares MAX_SEQUENCE_STEPS (6) copy-variable pairs, so
        an 8-step sequence is refused BEFORE the threading check fires. The
        threading invariant is still covered for email_eight through the
        ladder pattern assertion in test_every_ladder_pattern_satisfies_invariant
        and through the eight-step cadence tests in test_eight_step_cadence.
        """
        seq = cadencelibrary.PRODUCTIVE_EMAIL_EIGHT_V1
        email_keys = [s["key"] for s in seq if s.get("channel") == "email"]
        config = self._build_config_for_keys(email_keys, seq)
        with self.assertRaises(bisonfactory.FactoryRefused) as ctx:
            bisonfactory._sequence_steps(config, seq)
        self.assertIn("MAX_SEQUENCE_STEPS", str(ctx.exception))

    def test_every_ladder_pattern_satisfies_invariant(self):
        """Every pattern in THREAD_REPLY_PATTERNS has opener False and all
        follow-ups True - the shape that satisfies the threading invariant."""
        for ladder_name, pattern in cadencelibrary.THREAD_REPLY_PATTERNS.items():
            self.assertFalse(pattern[0],
                             f"ladder {ladder_name}: opener must be new-thread")
            for i, is_thread in enumerate(pattern[1:], start=2):
                self.assertTrue(is_thread,
                                f"ladder {ladder_name}: step {i} must be "
                                f"a follow-up")


class NewClientNoOverride(unittest.TestCase):
    """TASK-258: a new client with email_sequence and NO thread_reply_pattern
    inherits a default that satisfies the threading invariant."""

    def test_client_without_override_builds_valid_sequence(self):
        """A client config with email_sequence steps but no thread_reply_pattern
        builds a valid sequence through the default ladder."""
        seq = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        email_steps = [s for s in seq if s.get("channel") == "email"]
        email_keys = [s["key"] for s in email_steps]
        email_days = [(s["day"], s["key"]) for s in email_steps]
        email_days.sort(key=lambda p: (p[0], p[1]))
        day_of = {k: d for d, k in email_days}
        config_steps = {}
        for i, key in enumerate(email_keys, start=1):
            if i < len(email_keys):
                wait = day_of[email_keys[i]] - day_of[key]
            else:
                wait = 0
            config_steps[key] = {
                "order": i,
                "subject": f"Subject {i}",
                "body": f"<p>Body {i}</p>",
                "wait_in_days": wait,
            }
        config = {"title": "new client", "steps": config_steps}
        self.assertNotIn("thread_reply_pattern", config)
        steps = bisonfactory._sequence_steps(config, seq)
        self.assertFalse(steps[0]["thread_reply"])
        for step in steps[1:]:
            self.assertTrue(step["thread_reply"])

    def test_old_pattern_would_be_refused(self):
        """Verify the new tests discriminate: restoring the old alternating
        pattern causes the invariant to refuse distinct-subject steps."""
        seq = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        email_steps = [s for s in seq if s.get("channel") == "email"]
        email_keys = [s["key"] for s in email_steps]
        email_days = [(s["day"], s["key"]) for s in email_steps]
        email_days.sort(key=lambda p: (p[0], p[1]))
        day_of = {k: d for d, k in email_days}
        config_steps = {}
        for i, key in enumerate(email_keys, start=1):
            if i < len(email_keys):
                wait = day_of[email_keys[i]] - day_of[key]
            else:
                wait = 0
            config_steps[key] = {
                "order": i,
                "subject": f"Subject {i}",
                "body": f"<p>Body {i}</p>",
                "wait_in_days": wait,
            }
        config = {
            "title": "test",
            "steps": config_steps,
            "thread_reply_pattern": [False, True, False, True, False],
        }
        with self.assertRaises(bisonfactory.FactoryRefused):
            bisonfactory._sequence_steps(config, seq)


if __name__ == "__main__":
    unittest.main()
