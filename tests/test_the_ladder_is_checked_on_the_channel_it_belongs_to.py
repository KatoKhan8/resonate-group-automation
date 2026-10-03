#!/usr/bin/env python3
"""`li3` overwrote `em3`, so the ladder stopped checking the emails.

`sequencegate._rung_of` reads the digit, so `em3` and `li3` are both rung 3.
The order check built `on_rung[rung] = (step, body)` - keyed by the rung
ALONE - over a sorted list of both channels, so `li3` overwrote `em3` for
every rung whenever LinkedIn was supplied. The order check then examined the
LINKEDIN sequence while reporting on the offer's email spine.

`bisonfactory` passes no `linkedin` key and `generate_campaign` does, so the
same gate answered two different questions depending on which caller asked -
staging enforced the email ladder and generation silently did not. That is
how a rotated set of emails could be written, pass generation, and be refused
two gates later.

AND THE RULE WAS UNSATISFIABLE ON LINKEDIN. Coverage demanded `li3` carry
rung 3's vocabulary while `channels_complement` refused `li3` for being "em3
in shorter form". Measured 2026-09-30 on one contact: both fired five times
in the same ten-attempt run. A step cannot carry a rung's words and also not
resemble the email carrying the same rung's words.

So the ladder is checked on the channel the offer declares it for - the
offer's `step_objectives` are keyed 1..5 and the writer prompt says "keyed 1
to 5 for em1 to em5" - and LinkedIn is REPORTED as unchecked rather than
silently passed, which is this module's convention everywhere else.
"""
import unittest

from src import offers, sequencegate

# After TASK-367 the offer record does not carry step_objectives or
# ai_capabilities. This test constructs a synthetic offer with the Offer A
# spine for sequencegate testing.
OFFER = {
    "persona": "economic_buyer",
    "capabilities": ["profitability", "budgeting"],
    "problem": "margin and budget position invisible until a project closes",
    "mechanism": "demo",
    "cta_link": "https://productive.io/get-started/",
    "approval_status": "pending",
    "step_objectives": {
        1: "margin visibility",
        2: "quote versus burn",
        3: "resource decisions that move margin",
        4: "Report Intelligence as mechanism",
        5: "reframe and close",
    },
    "thread_reply_rungs": [2, 4],
    "ai_capabilities": {
        "Report Intelligence": {
            "page_text": "Ask anything about your business data.",
            "traces_to": "productive_ai",
        },
        "Project Summary": {
            "page_text": "Stay on top of every project.",
            "traces_to": "productive_ai",
        },
    },
}
RULES = offers.messaging_rules()

GOOD = {"em1": "margin visibility while the work is still running",
        "em2": "quote versus burn",
        "em3": "resource decisions that move margin",
        "em4": "Report Intelligence as mechanism",
        "em5": "reframe and close"}

JUNK_LI = {"li1": "unrelated chatter about the weather",
           "li2": "more unrelated chatter", "li3": "still unrelated",
           "li4": "nope", "li5": "nothing"}

ROTATED = {"em1": GOOD["em5"], "em2": GOOD["em1"], "em3": GOOD["em2"],
           "em4": GOOD["em3"], "em5": GOOD["em4"]}


def _objective_failures(sequence):
    verdict = sequencegate.check(sequence, offer=OFFER, messaging_rules=RULES)
    return [f for f in (verdict.get("failures") or ())
            if f.get("check") == "step_objectives"]


class TheEmailLadderIsCheckedWhicheverCallerAsks(unittest.TestCase):
    def test_a_good_ladder_passes_with_no_linkedin(self):
        """The control for the control."""
        self.assertEqual([], _objective_failures({"emails": GOOD}))

    def test_a_rotated_ladder_is_refused_with_no_linkedin(self):
        """Staging's shape. This always worked."""
        self.assertTrue(_objective_failures({"emails": ROTATED}))

    def test_a_rotated_ladder_is_STILL_refused_when_linkedin_is_supplied(self):
        """Generation's shape, and the defect. `li` used to overwrite `em`."""
        failures = _objective_failures({"emails": ROTATED,
                                        "linkedin": JUNK_LI})
        self.assertTrue(failures,
                        "supplying LinkedIn silenced the email ladder")
        self.assertTrue(
            all(str(f.get("step", "")).startswith("em") for f in failures),
            "the ladder reported on a channel it does not govern: %s"
            % [f.get("step") for f in failures])


#: LinkedIn ROTATED against the ladder: `li3` carries rung 1's vocabulary and
#: `li1` carries none of it. That is the exact shape the ORDER half of the
#: check refuses. With the emails perfectly in order, any `step_objectives`
#: failure here can only have come from the order check reading the LinkedIn
#: sequence - which is the defect.
ROTATED_LI = {"li1": "a short hello about nothing in particular",
              "li2": "quote versus burn",
              "li3": "margin visibility while the work is still running",
              "li4": "Report Intelligence as mechanism",
              "li5": "reframe and close"}


class TheOrderCheckReadsTheEmails(unittest.TestCase):
    """Isolates the ORDER half from the COVERAGE half.

    An earlier version of this file asserted only on a rotated EMAIL set,
    and a mutation that restored the overwrite SURVIVED it: the coverage
    check alone already failed those emails, so the test passed without the
    order check being involved at all. Mutation testing caught the weak test,
    which is the whole reason for doing it.
    """

    def test_rotated_linkedin_does_not_produce_a_ladder_failure(self):
        failures = _objective_failures({"emails": GOOD,
                                        "linkedin": ROTATED_LI})
        self.assertEqual(
            [], failures,
            "the order check read the LinkedIn sequence: %s"
            % [(f.get("step"), f.get("why")) for f in failures])


class LinkedinIsNotHeldToTheEmailSpine(unittest.TestCase):
    def test_unrelated_linkedin_does_not_fail_the_ladder(self):
        self.assertEqual([], _objective_failures({"emails": GOOD,
                                                  "linkedin": JUNK_LI}))

    def test_but_it_is_reported_as_unchecked_never_silently_passed(self):
        """Absence reported rather than read as a pass - the module's rule."""
        verdict = sequencegate.check({"emails": GOOD, "linkedin": JUNK_LI},
                                     offer=OFFER, messaging_rules=RULES)
        said = [w for w in (verdict.get("warnings") or ())
                if w.get("check") == "step_objectives"
                and str(w.get("step", "")).startswith("li")]
        self.assertTrue(said, "LinkedIn was skipped without saying so")


class TheAiRulesStillCoverBothChannels(unittest.TestCase):
    """Those are about what a PERSON READS, and were not narrowed."""

    def test_an_ai_capability_on_a_linkedin_step_is_still_refused(self):
        verdict = sequencegate.check(
            {"emails": GOOD,
             "linkedin": dict(JUNK_LI,
                              li1="Report Intelligence answers questions")},
            offer=OFFER, messaging_rules=RULES)
        self.assertTrue(
            [f for f in (verdict.get("failures") or ())
             if f.get("check") == "ai_is_supporting"
             and f.get("step") == "li1"],
            "an AI capability at a non-mechanism rung stopped being refused "
            "on LinkedIn")


if __name__ == "__main__":
    unittest.main()
