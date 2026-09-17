#!/usr/bin/env python3
"""The number of touches is a parameter. The invariant is not.

THREE STEPS IS A PRODUCTION-SAFE CONTROL, NOT A FINDING. The live CONTROL V3
runs three because three was audited and approved, and the operator's standing
instruction is that how many touches a cadence should carry is something this
system is supposed to LEARN. So the engine has to hold every safety property
at whatever length the next experiment picks, and the existing coverage pins
the property at exactly the two lengths somebody happened to ship:
`tests/test_threaded_sequence.py` at three and
`tests/test_a_five_step_campaign_sends_five_different_emails.py` at five.

Two tests at two lengths cannot tell "this holds for any N" apart from "this
holds for 3 and 5". That is the gap this module closes. Every test here is a
table over N = 1..6 - one at each end and every length between - so a change
that works at three and breaks at four has somewhere to go red.

WHY THE TABLE STOPS AT SIX. `bison.MAX_SEQUENCE_STEPS` is 6, because six pairs
of copy variables are declared at the provider. Seven is not "a longer cadence
we have not tried", it is a cadence whose seventh step sends with nothing in
it, and the last test in the first class proves the engine refuses it rather
than staging it.

THE PROPERTIES, at every N:

  1. The opener owns the only subject. Every step references `{SUBJECT_1}`.
  2. Steps 2..N are thread replies; step 1 is not.
  3. No `subject_2`..`subject_N` is generated - not in the template written
     to the provider, and not in the variables written to the lead.
  4. Each step gets its own body, and they are all different.
  5. The declared waits reproduce the cadence gaps.
  6. The final wait is never 0. It is inert - nothing follows the last step -
     but it is not ignored: `set_sequence` raised on campaign 485 and left it
     at zero steps.
  7. Nothing writes its own "Re:". EmailBison prepends it, measured by
     TASK-159 across 153 follow-ups, and a hand-built chain is simulated
     threading.

AND THE NEGATIVES AT EVERY N, because a guard that only refuses the shape
somebody already wrote down is not a guard. A follow-up that drops its
`thread_reply` and takes a subject of its own is the pre-2026-09-16 shape and
must be refused at three steps, at four, at five and at six.

THREE OF THOSE NEGATIVES DO NOT HOLD YET AND ARE MARKED `expectedFailure`.
They are not aspirational: each names a shape that reaches the provider today
and each is a real hole, written as the assertion that SHOULD pass so that the
day somebody closes the hole the marker itself goes red and has to be removed.
They are listed on the class that carries them. No source file was changed to
make anything here pass.
"""
import unittest

from src import bisonfactory
from src.bisonfactory import FactoryRefused
from src.providers.bison import LEAD_VARIABLES, MAX_SEQUENCE_STEPS

# The days a six-step cadence would run on, written out rather than computed.
# A test that derives its expectation the same way the code does agrees with
# the code unconditionally.
DAYS = (1, 4, 8, 12, 21, 28)
GAPS = (3, 4, 4, 9, 7)

# One at each end and every length between. 1 is campaign 451's shape, 3 is
# the live CONTROL, 5 is what the five-step module covers, 6 is the ceiling.
LENGTHS = (1, 2, 3, 4, 5, 6)

OPENER_SUBJECT = "{SUBJECT_1}"

# NOT 0. `wait_in_days` on the last step has no successor to wait for, so
# nothing reads it - but the provider is not indifferent to it: campaign 485
# was created and `set_sequence` raised, leaving the campaign at 0 steps.
FINAL_WAIT = 1

assert len(DAYS) == MAX_SEQUENCE_STEPS, (
    "the table must cover exactly the lengths the provider can hold")
assert LENGTHS[-1] == MAX_SEQUENCE_STEPS


def cadence_of(n):
    """An n-step, email-only cadence on the days above."""
    return tuple({"key": f"em{i}", "day": DAYS[i - 1], "channel": "email",
                  "generated": True} for i in range(1, n + 1))


def threaded_config(n, *, drop_thread_at=None, own_subject_at=None,
                    re_prefix_at=None, final_wait=FINAL_WAIT):
    """The threaded n-step shape, with one deliberate break available.

    `drop_thread_at` turns one follow-up back into a new thread.
    `own_subject_at` gives one follow-up a `{SUBJECT_k}` of its own.
    `re_prefix_at` writes a "Re:" the provider would have written itself.

    With all three absent this is the shape both shipped client files carry:
    one opener owning `{SUBJECT_1}`, and every follow-up a thread reply
    referencing that same subject and nothing else.
    """
    steps = {}
    for i in range(1, n + 1):
        subject = OPENER_SUBJECT
        if own_subject_at == i:
            subject = "{SUBJECT_%d}" % i
        if re_prefix_at == i:
            subject = "Re: " + subject
        steps[f"em{i}"] = {
            "order": i,
            "subject": subject,
            "body": "<p>{BODY_%d}</p>" % i,
            "wait_in_days": GAPS[i - 1] if i < n else final_wait,
        }
    pattern = [False] + [True] * (n - 1)
    if drop_thread_at is not None:
        pattern[drop_thread_at - 1] = False
    return {"title": f"Resonate {n}-step",
            "thread_reply_pattern": pattern,
            "steps": steps}


def built(n, **kw):
    return bisonfactory._sequence_steps(threaded_config(n, **kw),
                                        cadence_of(n))


def lead_for(sequence):
    """A lead carrying one approved pair per step of `sequence`."""
    copy = [{"step_key": s["step_key"],
             "subject": f"subject for {s['step_key']}",
             "body": f"<p>body for {s['step_key']}</p>"}
            for s in sequence]
    return {"record_id": "rec-1", "contact_key": "rec-1-c1", "copy": copy,
            "subject": copy[0]["subject"], "body": copy[0]["body"]}


def variables_at(n):
    sequence = built(n)
    written = bisonfactory._variables_for(lead_for(sequence),
                                          {"client": "productive"},
                                          sequence=sequence)
    return {v["name"]: v["value"] for v in written}


class TheInvariantHoldsAtEveryLength(unittest.TestCase):
    """N = 1..6, the same seven properties each time."""

    def test_the_opener_owns_the_only_subject(self):
        """One subject per sequence, however many steps the sequence has."""
        for n in LENGTHS:
            with self.subTest(steps=n):
                steps = built(n)
                self.assertEqual(len(steps), n)
                self.assertEqual({s["email_subject"] for s in steps},
                                 {OPENER_SUBJECT})

    def test_no_numbered_subject_past_the_first_is_in_any_template(self):
        """`{SUBJECT_2}`..`{SUBJECT_6}` are not merge fields this engine writes.

        A template asking for a variable the lead does not carry renders
        nothing, and the read-back agrees the campaign is correct. So the
        absence is checked on the template, not only on the lead.
        """
        for n in LENGTHS:
            with self.subTest(steps=n):
                for step in built(n):
                    for k in range(2, MAX_SEQUENCE_STEPS + 1):
                        self.assertNotIn("{SUBJECT_%d}" % k,
                                         step["email_subject"])

    def test_every_step_after_the_opener_is_a_thread_reply(self):
        """One opener and N-1 continuations, at every N."""
        for n in LENGTHS:
            with self.subTest(steps=n):
                steps = built(n)
                self.assertEqual([s["thread_reply"] for s in steps],
                                 [False] + [True] * (n - 1))

    def test_every_step_gets_its_own_body(self):
        """N steps, N distinct bodies, each numbered for its own position."""
        for n in LENGTHS:
            with self.subTest(steps=n):
                steps = built(n)
                for i, step in enumerate(steps, start=1):
                    self.assertIn("{BODY_%d}" % i, step["email_body"])
                self.assertEqual(len({s["email_body"] for s in steps}), n)

    def test_the_declared_waits_reproduce_the_cadence_gaps(self):
        """Every gap but the last, checked against the days it claims."""
        for n in LENGTHS:
            with self.subTest(steps=n):
                steps = built(n)
                self.assertEqual(tuple(s["wait_in_days"] for s in steps[:-1]),
                                 GAPS[:n - 1])

    def test_the_final_wait_is_never_zero(self):
        """Inert is not the same as accepted - campaign 485 proved it."""
        for n in LENGTHS:
            with self.subTest(steps=n):
                last = built(n)[-1]["wait_in_days"]
                self.assertNotEqual(last, 0)
                self.assertGreaterEqual(last, 1)

    def test_no_step_writes_its_own_re_prefix(self):
        """The provider prepends it. Writing a second one is drift forever."""
        for n in LENGTHS:
            with self.subTest(steps=n):
                for step in built(n):
                    self.assertFalse(
                        step["email_subject"].lower().startswith("re:"))

    def test_the_lead_carries_one_subject_and_a_body_per_step(self):
        """The variables actually written, not the template that reads them.

        `bison._variables` drops empty values, so a follow-up subject is
        absent rather than blank. Either way nothing prospect-facing is held
        under a numbered subject past the first.
        """
        for n in LENGTHS[1:]:  # N=1 uses the unnumbered shape; see below.
            with self.subTest(steps=n):
                held = variables_at(n)
                self.assertEqual(held.get("subject_1"), "subject for em1")
                for k in range(2, MAX_SEQUENCE_STEPS + 1):
                    self.assertFalse(held.get(f"subject_{k}"),
                                     f"subject_{k} was written for a "
                                     f"{n}-step threaded sequence")
                for i in range(1, n + 1):
                    self.assertEqual(held.get(f"body_{i}"),
                                     f"<p>body for em{i}</p>")

    def test_the_lead_carries_no_body_past_the_last_step(self):
        """A lead that used to run longer must not keep the extra words."""
        for n in LENGTHS[1:]:
            with self.subTest(steps=n):
                held = variables_at(n)
                for i in range(n + 1, MAX_SEQUENCE_STEPS + 1):
                    self.assertNotIn(f"body_{i}", held)

    def test_stale_numbered_copy_is_cleared_at_every_length(self):
        """Shrinking from six steps to N leaves N+1..6 on the lead.

        `_variables_for` names only the positions the current sequence reads,
        so the reconciliation never compares - and never clears - the higher
        ones. Measured on campaign 485: ten leads held `subject_4`,
        `subject_5`, `body_4` and `body_5` from a five-step era after the
        campaign had shrunk to three.
        """
        for n in LENGTHS[1:]:
            with self.subTest(steps=n):
                names = {e["name"]: e["value"]
                         for e in bisonfactory._stale_clearances(built(n))}
                for k in range(2, MAX_SEQUENCE_STEPS + 1):
                    self.assertIn(f"subject_{k}", names)
                    self.assertEqual(names[f"subject_{k}"], "")
                for k in range(n + 1, MAX_SEQUENCE_STEPS + 1):
                    self.assertIn(f"body_{k}", names)
                self.assertNotIn("subject_1", names)
                for k in range(1, n + 1):
                    self.assertNotIn(f"body_{k}", names)

    def test_every_variable_every_length_uses_is_declared_at_the_provider(self):
        """A variable the workspace does not hold is a 422 mid-batch."""
        self.assertIn("subject_1", LEAD_VARIABLES)
        for n in LENGTHS:
            with self.subTest(steps=n):
                for i in range(1, n + 1):
                    self.assertIn(f"body_{i}", LEAD_VARIABLES)

    def test_a_length_past_the_declared_variables_is_refused(self):
        """Seven is not a longer cadence. It is a step that sends empty."""
        seventh = cadence_of(MAX_SEQUENCE_STEPS) + (
            {"key": "em7", "day": 35, "channel": "email", "generated": True},)
        block = dict(threaded_config(MAX_SEQUENCE_STEPS)["steps"])
        block["em7"] = {"order": 7, "subject": OPENER_SUBJECT,
                        "body": "<p>{BODY_7}</p>", "wait_in_days": FINAL_WAIT}
        with self.assertRaises(FactoryRefused) as caught:
            bisonfactory._sequence_steps(
                {"steps": block,
                 "thread_reply_pattern": [False] + [True] * 6}, seventh)
        self.assertIn("MAX_SEQUENCE_STEPS", str(caught.exception))


class TheBrokenShapeIsRefusedAtEveryLength(unittest.TestCase):
    """The pre-2026-09-16 shape, at three steps, four, five and six.

    A follow-up that stops being a thread reply AND takes a `{SUBJECT_k}` of
    its own is a second cold open wearing the same campaign's name. It is
    exactly what EmailBison campaign 485 carried - step 2 with
    `Re: {SUBJECT_2}` and step 3 `thread_reply: false` with its own
    `{SUBJECT_3}` - and 485 could not be corrected in place, because
    `set_sequence` APPENDS. So the refusal has to happen before the write.

    THREE HOLES ARE MARKED `expectedFailure` BELOW, and they are the finding
    of this module rather than a caveat on it:

      A. At N=2 nothing is refused at all. The guard runs only when some
         follow-up is STILL threaded, and the only follow-up a two-step
         sequence has is the one being broken - so breaking it turns the
         guard off instead of tripping it.
      B. A follow-up that keeps `thread_reply` but takes its own
         `{SUBJECT_k}` is accepted at every length. `_variables_for` then
         writes that subject as empty, so the step ships an empty subject.
      C. A follow-up may write its own "Re:" at every length.
    """

    def test_dropping_threading_and_taking_a_subject_is_refused(self):
        """N = 3..6, every follow-up position, one at a time."""
        for n in (3, 4, 5, 6):
            for k in range(2, n + 1):
                with self.subTest(steps=n, broken_step=k):
                    with self.assertRaises(FactoryRefused) as caught:
                        built(n, drop_thread_at=k, own_subject_at=k)
                    message = str(caught.exception)
                    self.assertIn("not a thread reply", message)
                    self.assertIn("distinct subject", message)
                    self.assertIn("{SUBJECT_%d}" % k, message)
                    self.assertIn(f"step {k}", message)

    def test_the_refusal_names_the_opener_it_was_measured_against(self):
        """A refusal nobody can act on is a refusal nobody acts on."""
        for n in (3, 5):
            with self.subTest(steps=n):
                with self.assertRaises(FactoryRefused) as caught:
                    built(n, drop_thread_at=n, own_subject_at=n)
                self.assertIn(OPENER_SUBJECT, str(caught.exception))

    def test_a_follow_up_keeping_the_opener_subject_is_not_the_defect(self):
        """Dropping `thread_reply` alone opens a new thread with the SAME
        subject. Odd, and deliberately not what this guard is about: the
        invariant is that only the opener owns A subject, and this shape
        does not introduce a second one.
        """
        for n in LENGTHS[1:]:
            for k in range(2, n + 1):
                with self.subTest(steps=n, unthreaded_step=k):
                    steps = built(n, drop_thread_at=k)
                    self.assertEqual({s["email_subject"] for s in steps},
                                     {OPENER_SUBJECT})

    @unittest.expectedFailure
    def test_hole_a_the_lone_follow_up_of_a_two_step_sequence_is_refused(self):
        """A two-step sequence's only follow-up may break the invariant.

        `_sequence_steps` guards only when `any(thread_reply)` over the
        follow-ups is true. With one follow-up, breaking it makes that false,
        the guard is skipped, and a two-step campaign ships two cold opens
        with two different subjects - the exact shape refused at N=3.

        This asserts the property that SHOULD hold. When the engine is fixed
        so the intended shape is compared against rather than the surviving
        flags, this test passes and the marker above must be deleted.
        """
        with self.assertRaises(FactoryRefused):
            built(2, drop_thread_at=2, own_subject_at=2)

    @unittest.expectedFailure
    def test_hole_b_a_threaded_follow_up_may_not_take_its_own_subject(self):
        """A thread reply carrying `{SUBJECT_k}` is accepted at every length.

        `_variables_for` writes a threaded follow-up's subject as EMPTY, so
        the template asks for `{SUBJECT_k}` and the lead carries no value for
        it. The step ships with an empty subject and the read-back agrees the
        campaign is correct - the failure mode the whole module was written
        against, reached by the one mutation the guard does not look at.

        Asserted at every N so a fix cannot be length-specific.
        """
        refused = []
        for n in LENGTHS[1:]:
            for k in range(2, n + 1):
                try:
                    built(n, own_subject_at=k)
                    refused.append((n, k, False))
                except FactoryRefused:
                    refused.append((n, k, True))
        self.assertTrue(all(r[2] for r in refused),
                        f"accepted a threaded follow-up with its own "
                        f"subject at: {[r[:2] for r in refused if not r[2]]}")

    @unittest.expectedFailure
    def test_hole_c_a_follow_up_may_not_write_its_own_re_prefix(self):
        """"Re:" is the provider's to write, and it writes it.

        TASK-159 measured it across 153 follow-ups. A hand-built prefix is
        simulated threading, `EMAILBISON-COPY-REQUIREMENTS.md` forbids it,
        and campaign 485 carried `Re: {SUBJECT_2}` - so this is a shape that
        reached a real estate, not a hypothetical one. Nothing refuses it.
        """
        refused = []
        for n in LENGTHS[1:]:
            for k in range(2, n + 1):
                try:
                    built(n, re_prefix_at=k)
                    refused.append((n, k, False))
                except FactoryRefused:
                    refused.append((n, k, True))
        self.assertTrue(all(r[2] for r in refused),
                        f"accepted a hand-written Re: at: "
                        f"{[r[:2] for r in refused if not r[2]]}")


class ASingleStepSequenceIsStillARealShape(unittest.TestCase):
    """One step is a length, not a degenerate case.

    EmailBison campaign 451 is staged against the unnumbered shape - top-level
    `subject`, `body` and `wait_in_days` - and has a scheduled send on it.
    That is production evidence, so the shape is not deprecated and a lead
    built in it carries the UNNUMBERED pair.

    ONE SHAPE PER CAMPAIGN, NEVER BOTH. A lead holding `subject` and
    `subject_1` is a lead whose own campaign cannot say which variable its
    template reads, and a reader comparing two leads cannot tell which shape
    either was built in.
    """

    UNNUMBERED = {"subject": "{SUBJECT}", "body": "<p>{BODY}</p>",
                  "wait_in_days": 3}

    def test_the_unnumbered_shape_builds_exactly_one_step(self):
        steps = bisonfactory._sequence_steps(self.UNNUMBERED, cadence_of(1))
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]["email_subject"], "{SUBJECT}")
        self.assertEqual(steps[0]["email_body"], "<p>{BODY}</p>")
        self.assertNotIn("step_key", steps[0])

    def test_the_unnumbered_shape_asks_for_no_numbered_variable(self):
        """`{SUBJECT_1}` on a lead carrying `subject` renders nothing."""
        step = bisonfactory._sequence_steps(self.UNNUMBERED, cadence_of(1))[0]
        for k in range(1, MAX_SEQUENCE_STEPS + 1):
            self.assertNotIn("{SUBJECT_%d}" % k, step["email_subject"])
            self.assertNotIn("{BODY_%d}" % k, step["email_body"])

    def test_a_single_step_lead_carries_the_unnumbered_pair_only(self):
        lead = {"record_id": "rec-1", "contact_key": "rec-1-c1",
                "subject": "the only subject", "body": "<p>the only body</p>",
                "copy": [{"step_key": "em1", "subject": "the only subject",
                          "body": "<p>the only body</p>"}]}
        held = {v["name"]: v["value"] for v in bisonfactory._variables_for(
            lead, {"client": "productive"})}
        self.assertEqual(held["subject"], "the only subject")
        self.assertEqual(held["body"], "<p>the only body</p>")
        for k in range(1, MAX_SEQUENCE_STEPS + 1):
            self.assertNotIn(f"subject_{k}", held)
            self.assertNotIn(f"body_{k}", held)

    def test_a_multi_step_lead_carries_the_numbered_pairs_only(self):
        """The other half of "never both", at every multi-step length."""
        for n in LENGTHS[1:]:
            with self.subTest(steps=n):
                held = variables_at(n)
                self.assertNotIn("subject", held)
                self.assertNotIn("body", held)
                self.assertIn("subject_1", held)

    def test_one_step_has_no_follow_up_to_thread(self):
        """Nothing to continue, so nothing is a continuation."""
        steps = built(1)
        self.assertEqual(len(steps), 1)
        self.assertFalse(steps[0]["thread_reply"])

    @unittest.expectedFailure
    def test_hole_d_a_one_step_steps_block_carries_what_its_template_reads(self):
        """THE LENGTH AT WHICH THE ENGINE DOES NOT GENERALISE.

        A `steps` block with exactly ONE entry is a legal, checked sequence:
        `_sequence_steps` builds it and writes `{SUBJECT_1}` / `{BODY_1}` to
        the provider. But `_variables_for` decides which shape to write from
        the LEAD's copy count (`len(copy) <= 1`) rather than from the shape
        the SEQUENCE declared, so that same lead is given the UNNUMBERED
        `subject` and `body`. The template asks for `subject_1`; the lead
        carries `subject`; the person receives an email with no subject and
        no body, and every read-back agrees the campaign is correct.

        That is the exact failure the five-step module's docstring describes,
        surviving at N=1. It is also the one place "never both shapes" can be
        violated on a single lead: `_stale_clearances` returns nothing for a
        one-step sequence, so a lead shrunk from three steps keeps
        `subject_1..3` and `body_1..3` AND gains `subject` and `body`.

        This asserts what a one-step numbered sequence SHOULD write. No
        source was changed; the marker is the report.
        """
        sequence = built(1)
        self.assertEqual(sequence[0]["email_subject"], OPENER_SUBJECT)
        held = variables_at(1)
        self.assertEqual(held.get("subject_1"), "subject for em1")
        self.assertEqual(held.get("body_1"), "<p>body for em1</p>")
        self.assertNotIn("subject", held)
        self.assertNotIn("body", held)


if __name__ == "__main__":
    unittest.main()
