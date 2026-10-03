#!/usr/bin/env python3
"""The writer's retry loop READS `role_ladder`, and a bad rung is rewritten.

The staging gate is the last line before the provider and it has no remedy -
it can only refuse. `generate_campaign` is the one seam where a sequence that
misses a rung can still be FIXED: `failures` drives the retry loop and
`_retry_reasons` puts every distinct refusal into the next prompt. Tonight's
copy is written through this path, so this is where the ladder earns its
keep.

THE DEFECT THIS CLOSES, and it is recorded in `generate_campaign` itself:
`result["sequence_gate"]` is computed and consulted by nothing - "the retry
loop breaks on `copylint` alone, so a sequence the gate REFUSED is returned
exactly like one it passed". `role_ladder` was worse: not computed here at
all, and not called anywhere in `src/`.

THE ONE OBJECTION THAT DOES NOT APPLY TO THE LADDER. That same comment
declines to fold `sequence_gate`'s failures into the retry list because
`offers.py` is single-tenant, so the offer the gate is handed is Productive's
whatever client is generating. `role_ladder(steps)` TAKES NO OFFER - it reads
the five bodies, `sequencegate`'s marker tuples and `config/copy-ask-ladder.
yaml`, none of which is client data. That is asserted below by signature
rather than argued, so a future edit that gave the ladder an offer would fail
here first.

BOTH HALVES, AS EVERYWHERE. A writer whose draft misses a rung is refused and
told which step and why; a writer whose draft climbs the ladder is NOT
refused for the ladder. A gate that refuses every draft would exhaust ten
attempts on good copy and hold every record, which costs ten model calls a
contact and ships nothing.
"""
import inspect
import unittest
from unittest import mock

from src import campaignstrategy, generate_campaign, offers as offers_mod
from src import sequencegate
from tests.test_task400_rework2 import (_CampaignModel, _account,
                                        _approved_offer, _client_config,
                                        _contacts)


# ---------------------------------------------------------------------------
# THE TWO SEQUENCES, GROUNDED IN THIS FIXTURE'S OWN PACK.
#
# They are declared here rather than imported from the staging module, and
# that is a correction the mutation run forced. The staging module's em1 leans
# on `packfixture.GROUNDING`, which THIS fixture's account knows nothing
# about, so `copylint`'s `first_line` rule refused both halves - and two of the
# negative tests below were passing because the COPY LINT refused the draft,
# not because the ladder did. Under the mutation they stayed green, which is
# exactly what a test that cannot fail looks like.
#
# em1's first line now leans on `_account()`'s own source sentence, so the
# lint is satisfied and the ONLY thing that can separate the two runs is em2's
# thread reference. Measured: the good one is refused ZERO times, the bad one
# ten times and always on `bump_without_thread em2`.
# ---------------------------------------------------------------------------

GEN_EM1 = (
    "Jane, your site says TestCorp is a digital marketing agency with 40 "
    "people.\n\n"
    "Most teams that size only see project margin once a project has closed, "
    "which is after the point where anything could be done about it. The "
    "forward view of what is booked against what is budgeted usually lives "
    "in two places, and reconciling them is somebody's week rather than a "
    "report.\n\n"
    "I can put together a free map of the next four weeks of bookings "
    "against budget, from public data, and leave it with you. Nothing to "
    "install and nothing to fill in, and it is yours to keep whether or not "
    "we ever speak again about any of it.\n\n"
    "Could we book a 30 minute walk-through of it?")

#: em2, the smaller piece, IN THE SAME THREAD.
GEN_EM2 = ("Following up on my note. Would you like to see just the first "
           "fortnight as a single screenshot instead?")

#: The same words with the thread reference removed, and nothing else.
GEN_EM2_NO_THREAD = ("Would you like to see just the first fortnight as a "
                     "single screenshot instead?")

GEN_EM3 = ("Coming back to my note with one number. Mast Studio cut 12 hours "
           "a week of status chasing after putting bookings and budgets on "
           "one view. Is your forward view in one place today?")

GEN_EM4 = ("As I mentioned, the map takes an hour to build. Does a forward "
           "view of bookings and budgets sound useful? If it is not the "
           "right time, say the word and I will leave you to it.")

GEN_EM5 = ("Closing the loop on this one. The map of the next four weeks is "
           "still yours if you want it, and agencies this size usually plan "
           "bookings and budgets in two tools. Worth a reply either way?")

LADDER_GOOD = {"em1": GEN_EM1, "em2": GEN_EM2, "em3": GEN_EM3,
               "em4": GEN_EM4, "em5": GEN_EM5}
LADDER_BAD = dict(LADDER_GOOD, em2=GEN_EM2_NO_THREAD)


class _LadderModel(_CampaignModel):
    """The scripted campaign model, writing a sequence I choose.

    Everything above the writer - the ICP answer, the fact extraction, the
    hypothesis, the capability match - is inherited unchanged, so the only
    thing that differs between the two runs below is the five bodies. A
    refusal that came from anywhere else would fire on both.
    """

    def __init__(self, bodies):
        super().__init__()
        self.bodies = bodies

    def _writer_answer(self, prompt, fact):
        answer = super()._writer_answer(prompt, fact)
        answer["emails"] = dict(self.bodies)
        return answer


def _run(bodies):
    campaignstrategy.clear_cache()
    model = _LadderModel(bodies)
    with mock.patch.object(offers_mod, "load",
                           return_value=_approved_offer()):
        plan = generate_campaign.generate(
            _client_config(), _account(), _contacts(),
            model=model, live=False)
    return plan["contacts"][0], model


class TheWriterLoopReadsTheLadder(unittest.TestCase):

    def test_the_ladder_takes_no_offer_and_so_is_client_neutral(self):
        """The reason the single-tenant objection does not reach it.

        Asserted on the signature, not on a comment: `role_ladder(steps)` has
        exactly one parameter, so there is no seam through which one client's
        licensed data could be handed to another's copy.
        """
        self.assertEqual(
            ["steps"],
            list(inspect.signature(sequencegate.role_ladder).parameters))

    # ------------------------------------------------------- the negative test

    def test_a_draft_that_misses_a_rung_is_refused_by_the_writer_loop(self):
        """By effect: the verdict is taken, read, and the draft is rejected.

        The rejection string is the ladder's own `check step: why`, so the
        writer is told WHICH step to rewrite - the difference measured on the
        Rachele canary between a refusal fixed on the next attempt and one
        still present ten attempts later.
        """
        contact, model = _run(LADDER_BAD)
        self.assertTrue(contact["role_ladder"]["refused"])
        self.assertEqual(
            [("bump_without_thread", "em2")],
            [(f["check"], f["step"])
             for f in contact["role_ladder"]["failures"]])
        rejections = contact.get("gate_rejections") or []
        # EVERY attempt was refused, and every one of them for the ladder's
        # reason alone. A rejection list that also carried a copy-lint
        # complaint would make the hold below unattributable - which is how
        # the first version of this module passed under the mutation.
        self.assertEqual(generate_campaign.MAX_WRITER_ATTEMPTS,
                         len(rejections))
        self.assertEqual(
            {"bump_without_thread em2: a same-thread step that never says it "
             "is one reads as a cold email sent twice"},
            set(rejections))

    def test_a_draft_that_misses_a_rung_is_never_stored_as_a_candidate(self):
        """Refused is refused: no sequences survive ten refused attempts.

        `_process_contact` empties `sequences` when every attempt is rejected,
        so "never stored as a send candidate" is a property of the data rather
        than a comment. Without the ladder in `failures` this contact would be
        returned with its five bodies intact.
        """
        contact, model = _run(LADDER_BAD)
        self.assertEqual({}, contact.get("sequences") or {})
        self.assertEqual("copy_refused", contact.get("hold_kind"))
        self.assertIn("no draft passed lint", contact.get("held") or "")

    def test_the_writer_was_told_what_was_wrong_in_its_next_prompt(self):
        """The remedy half: the refusal reaches the model, not just the log.

        This is why the ladder is wired HERE and not only at the stage. A
        refusal the writer never sees cannot produce a better draft.
        """
        contact, model = _run(LADDER_BAD)
        writer_prompts = [p for p in model.calls
                          if "write cold outreach" in p.lower()]
        self.assertGreater(len(writer_prompts), 1,
                           "the writer was never asked a second time")
        self.assertIn("bump_without_thread", "\n".join(writer_prompts[1:]))

    # -------------------------------------------------------------- the control

    def test_a_draft_built_to_the_ladder_is_not_refused_for_the_ladder(self):
        """WITHOUT THIS THE TESTS ABOVE PROVE NOTHING.

        The same pipeline, the same model, five bodies that climb the ladder:
        the ladder's verdict is clean and nothing it produced reaches the
        rejection list. A gate that refused every draft would satisfy every
        assertion above and would hold every record this pipeline writes.
        """
        contact, model = _run(LADDER_GOOD)
        self.assertFalse(contact["role_ladder"]["refused"],
                         contact["role_ladder"].get("failures"))
        self.assertEqual([], generate_campaign.ladder_failures(
            contact["role_ladder"]))
        # ZERO rejections, not merely no ladder ones. This fixture is
        # grounded in its own account's pack, so a draft built to the ladder
        # passes the whole of section G on the FIRST attempt - which is what
        # makes the ten rejections in the negative case attributable.
        self.assertEqual([], contact.get("gate_rejections") or [])
        self.assertIsNone(contact.get("held"))
        self.assertIn("em1", contact.get("sequences") or {})

    def test_the_rung_each_step_was_credited_with_is_on_the_result(self):
        """A stub returning `{"refused": False}` could not produce these."""
        contact, _model = _run(LADDER_GOOD)
        roles = contact["role_ladder"]["roles"]
        self.assertEqual(list(sequencegate.ROLE_LADDER),
                         [roles[key] for key in sequencegate.STEP_KEYS])

    # ----------------------------------------- the empty list is reachable

    def test_ladder_failures_is_empty_for_a_verdict_that_refuses_nothing(self):
        """The half that makes the wiring mean something.

        A translator that never returns an empty list turns the gate into a
        refusal of everything, which is as useless as refusing nothing.
        """
        self.assertEqual([], generate_campaign.ladder_failures(
            sequencegate.role_ladder(LADDER_GOOD)))
        self.assertEqual([], generate_campaign.ladder_failures(None))
        self.assertEqual(
            ["bump_without_thread em2: a same-thread step that never says it "
             "is one reads as a cold email sent twice"],
            generate_campaign.ladder_failures(
                sequencegate.role_ladder(LADDER_BAD)))


if __name__ == "__main__":
    unittest.main()
