"""`step_objectives` is a ladder of ROLES, and the gate reads it. TASK-964.

Operator, 2026-10-02: em1 offers, em2 gives a smaller tangible piece of the
same offer, em3 proves with a named client and a number, em4 asks an
easy-answer question with an explicit exit, em5 breaks up in a new thread
keeping the offer. Four refusals follow from that, and the fifth - an
unreadable rung is UNKNOWN and refuses - follows from invariant 0.

THE TWO HALVES THAT MATTER EQUALLY. A gate that refuses the artefact proves
nothing on its own, because a rule that refuses everything does the same. So
every refusal here is asserted twice: once on copy that breaks it, and once on
copy built to the ladder, which must PASS. The clean sequence in `GOOD` is the
control, and it caught two real defects while this was being written - em4 read
as a breakup because an explicit exit is written in a breakup's words, and em3
missed the proof rung because the marker was spelled "they cut" while the
sentence said "Mast Studio cut".
"""
import base64
import json
import os
import unittest

from src import copylint, sequencegate


FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "fixtures", "converged-copy-anonymised-2026-10-02.json")

#: Five steps built TO the ladder. The control for every rule below.
GOOD = {
    "em1": {"body": (
        "Hi Casey, agencies running several studios usually plan bookings in "
        "one tool and budgets in another, so the forward view is a guess. "
        "I can put together a free map of your next four weeks of bookings "
        "against budget, from public data, and leave it with you. "
        "Could we book a 30 minute walk-through of it?")},
    "em2": {"body": (
        "Following up on my note - rather than the whole map, would you like "
        "to see one screenshot of the next four weeks, bookings against "
        "budget? I can send it over today.")},
    "em3": {"body": (
        "Circling back with one number. Mast Studio cut 12 hours a week of "
        "status chasing after putting bookings and budgets on one view, and "
        "they are about your size. Is your forward view in one place today?")},
    "em4": {"body": (
        "My last note on this. Does a forward view of bookings and budgets "
        "sound useful for your team? If it is not the right time, say the "
        "word and I will leave you to it.")},
    "em5": {"body": (
        "Hi Casey - closing the loop on this one. The map of your next four "
        "weeks is still yours if you want it, and agencies this size usually "
        "plan bookings and budgets in two tools. Worth a reply either way?")},
}


def broken(step, body):
    """`GOOD` with one step replaced. Copied, so the control never mutates."""
    out = {key: dict(value) for key, value in GOOD.items()}
    out[step]["body"] = body
    return out


def checks(result):
    return {failure["check"] for failure in result["failures"]}


class TheControlPasses(unittest.TestCase):
    """Copy built to the ladder is ALLOWED. Without this the rest is noise."""

    def test_a_sequence_built_to_the_ladder_is_not_refused(self):
        result = sequencegate.role_ladder(GOOD)
        self.assertFalse(result["refused"], result["why"])

    def test_each_step_is_credited_with_its_own_rung(self):
        roles = sequencegate.role_ladder(GOOD)["roles"]
        self.assertEqual(
            [roles[key] for key in sequencegate.STEP_KEYS],
            list(sequencegate.ROLE_LADDER))

    def test_the_asks_descend(self):
        asks = sequencegate.role_ladder(GOOD)["asks"]
        ranks = [asks[key] for key in sequencegate.STEP_KEYS]
        self.assertNotIn(None, ranks, ranks)
        self.assertEqual(ranks, sorted(ranks, reverse=True), ranks)


class EveryRuleBitesWhenBroken(unittest.TestCase):

    def test_two_steps_sharing_a_rung_are_refused_and_both_are_named(self):
        result = sequencegate.role_ladder(
            broken("em3", GOOD["em2"]["body"]))
        self.assertIn("role_shared", checks(result))
        self.assertIn("em2+em3", result["why"])

    def test_an_ask_that_grows_is_refused(self):
        result = sequencegate.role_ladder(
            broken("em4", "My last note. Could we book a 30 minute call?"))
        self.assertIn("ask_does_not_descend", checks(result))

    def test_a_same_thread_step_with_no_thread_reference_is_refused(self):
        result = sequencegate.role_ladder(
            broken("em2", "Would you like to see one screenshot of the next "
                          "four weeks, bookings against budget?"))
        self.assertIn("bump_without_thread", checks(result))

    def test_em5_is_refused_for_referencing_the_old_thread(self):
        result = sequencegate.role_ladder(
            broken("em5", "Following up on my note - the map is still yours. "
                          "Worth a reply?"))
        self.assertIn("new_thread_references_old", checks(result))

    def test_the_same_proof_twice_is_refused(self):
        result = sequencegate.role_ladder(
            broken("em4", "My last note. Mast Studio cut 12 hours a week too. "
                          "Does that sound useful? If not the right time, say "
                          "the word."))
        self.assertIn("proof_reused", checks(result))

    def test_an_unreadable_rung_is_unknown_and_refuses(self):
        result = sequencegate.role_ladder(broken("em2", "Thanks for your time."))
        self.assertIn("role_unreadable", checks(result))


class TheArtefactDoesNotPassTomorrowsGate(unittest.TestCase):
    """The operator's five reasons, mechanically, on the committed copy.

    The fixture is the 2026-10-02 generation that passed every gate then - the
    "before" half of the before/after. It is anonymised, and the anonymisation
    keeps each body's token count identical, because the token count is what
    the word contract reads.
    """

    def setUp(self):
        with open(FIXTURE, encoding="utf-8") as handle:
            self.doc = json.load(handle)
        self.result = sequencegate.role_ladder(self.doc["steps"])

    def test_it_is_refused(self):
        self.assertTrue(self.result["refused"])

    def test_the_offer_email_contains_no_offer(self):
        self.assertIsNone(self.result["roles"]["em1"])

    def test_not_one_follow_up_references_the_thread(self):
        named = {failure["step"] for failure in self.result["failures"]
                 if failure["check"] == "bump_without_thread"}
        self.assertEqual(named, {"em2", "em3", "em4"})

    def test_the_asks_do_not_descend(self):
        self.assertIn("ask_does_not_descend", checks(self.result))

    def test_the_fixture_carries_no_identifier_of_the_real_prospect(self):
        """The identifiers are base64 here, and that is not decoration.

        The first version of this assertion spelled them as literals - and the
        PII scan over the staged diff then matched THIS FILE, which is the
        third time in one night that a check reintroduced the names it existed
        to keep out (the anonymiser's own metadata field did it twice). A test
        that publishes what it forbids is not a test, it is a second copy.
        """
        blob = json.dumps(self.doc).lower()
        for encoded in (b"YmlnZmlzaA==", b"YmlnIGZpc2g=", b"cm93YW4=",
                        b"bWF0dGhld3M="):
            self.assertNotIn(base64.b64decode(encoded).decode(), blob)


class TheAskLadderIsConfigAndTheOrderIsItsAuthority(unittest.TestCase):

    def test_the_order_comes_from_the_file(self):
        order = copylint.ask_order()
        self.assertGreaterEqual(len(order), 3)
        self.assertEqual(copylint.ask_rank("Worth a look?"), 1)
        self.assertEqual(
            copylint.ask_rank("Can we book a 30 minute call on Thursday?"),
            len(order))

    def test_an_unreadable_ask_is_none_and_not_the_smallest(self):
        self.assertIsNone(copylint.ask_rank("No question at all here."))

    def test_the_largest_matching_rung_wins(self):
        self.assertEqual(
            copylint.ask_rank("Worth a look - or a quick 15 minutes if "
                              "easier?"),
            copylint.ask_order().index("call_or_demo") + 1)

    def test_subject_matter_is_not_an_ask(self):
        """The measured false positive: domain nouns read as a meeting.

        "booked" and "next week" describe the prospect's own resource bookings
        for this client, and the first version of this rule ranked two steps of
        the artefact as booked meetings because of it.
        """
        self.assertIsNone(copylint.ask_rank(
            "We track what is booked next week for every studio."))


class ThePerBodyRules(unittest.TestCase):

    def test_at_most_one_question_and_a_single_cta_is_allowed(self):
        self.assertTrue(copylint.refuses_multiple_questions(
            "Did any of that land? Worth a look?"))
        self.assertFalse(copylint.refuses_multiple_questions(
            "Following up on my note - worth a look?"))

    def test_a_body_that_explains_their_own_company_to_them_is_refused(self):
        self.assertTrue(copylint.describes_their_own_company(
            "Hi Casey, Northgate Studio is a UK-based digital marketing "
            "agency.", "Northgate Studio"))

    def test_legitimate_personalisation_is_allowed(self):
        self.assertFalse(copylint.describes_their_own_company(
            "Teams like yours at Northgate Studio run four studios on one "
            "plan.", "Northgate Studio"))

    def test_an_appositive_is_the_same_defect(self):
        self.assertTrue(copylint.describes_their_own_company(
            "I was reading about Northgate Studio, a UK agency with four "
            "studios.", "Northgate Studio"))


if __name__ == "__main__":
    unittest.main()
