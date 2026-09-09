""""A note exists" and "the note is the approved note" are different questions.

Only the first was ever asked. `sequence_hazards` flags a connection request
with NO note, and `linkedin_only` proves the channel is LinkedIn. Neither reads
the words.

WHAT THAT COST, MEASURED. A dedicated one-lead canary campaign was built by
hand in the vendor UI on 2026-09-09, with the approved note pasted in by the
operator. Provider read-back showed the graph actually held HeyReach's own
pre-filled placeholder:

    "payload": {"messages": ["Hey, would love to connect!"], ...}

Every check passed. The sequence was provably LinkedIn-only, no hazard fired,
the note was not empty, the lead was the right person and the sender was the
right seat. The one thing nothing compared was the sentence a human would read,
and it was not ours.

The note lives at `payload.messages`. It is not at `message`, `note`, `text` or
`body` - all four were probed against the real graph and none exists, which is
why an extractor guessing at those names would have reported no note at all and
been believed.
"""
import unittest

from src.providers import heyreach

APPROVED = ("hi Dana, i work with Design Services teams on utilisation. "
            "curious how Ninefields handles it at your size. happy to connect.")


def sequence(*notes, node_type="CONNECTION_REQUEST", payload=True):
    """A graph shaped like the real one.

    `GetCampaignSequence` returns the ROOT NODE itself - `nodeType` at the top
    level, children under `conditionalNode` / `unconditionalNode`. There is no
    `steps` array and no `sequence` wrapper; this fixture asserted one at first
    and every test passed vacuously against an empty walk.
    """
    body = {"nodeType": node_type, "actionDelay": 0, "actionDelayUnit": "HOUR",
            "conditionalNode": {"nodeType": "END", "actionDelay": 1},
            "unconditionalNode": {"nodeType": "END", "actionDelay": 5}}
    if payload:
        body["payload"] = {"messages": list(notes), "fallbackMessage": "",
                           "toBeWithdrawnAfterDays": 21}
    return body


class TheApprovedNoteIsAccepted(unittest.TestCase):
    def test_the_exact_note_matches(self):
        ok, why = heyreach.note_matches(sequence(APPROVED), APPROVED)
        self.assertTrue(ok, why)

    def test_trailing_whitespace_from_a_textarea_is_not_an_edit(self):
        ok, why = heyreach.note_matches(
            sequence("  " + APPROVED + "\n\n"), APPROVED)
        self.assertTrue(ok, why)

    def test_the_extractor_reads_payload_messages(self):
        self.assertEqual(heyreach.connection_notes(sequence(APPROVED)),
                         [APPROVED])


class TheVendorPlaceholderIsRefused(unittest.TestCase):
    """The live failure, as a test."""

    def test_the_real_placeholder_that_was_configured_is_caught(self):
        ok, why = heyreach.note_matches(
            sequence("Hey, would love to connect!"), APPROVED)
        self.assertFalse(ok)
        self.assertIn("placeholder", why)

    def test_every_known_placeholder_is_caught(self):
        for note in heyreach.DEFAULT_NOTES:
            with self.subTest(note=note):
                self.assertTrue(heyreach.note_is_placeholder(note))
                ok, _ = heyreach.note_matches(sequence(note), APPROVED)
                self.assertFalse(ok)

    def test_case_and_spacing_do_not_hide_a_placeholder(self):
        for note in ("HEY, WOULD LOVE TO CONNECT!",
                     "  hey,   would love to connect!  "):
            with self.subTest(note=note):
                self.assertTrue(heyreach.note_is_placeholder(note))

    def test_our_own_note_is_not_mistaken_for_a_placeholder(self):
        self.assertFalse(heyreach.note_is_placeholder(APPROVED))


class AnyDifferenceAtAllIsRefused(unittest.TestCase):
    """This is the last check between a rendered draft and a real person."""

    def test_a_changed_word_is_refused(self):
        ok, why = heyreach.note_matches(
            sequence(APPROVED.replace("utilisation", "utilization")), APPROVED)
        self.assertFalse(ok)
        self.assertIn("not the approved note", why)

    def test_a_changed_case_is_refused(self):
        """Case is the copy: the Productive LinkedIn voice is lowercase."""
        ok, _ = heyreach.note_matches(sequence(APPROVED.capitalize()), APPROVED)
        self.assertFalse(ok)

    def test_dropped_punctuation_is_refused(self):
        ok, _ = heyreach.note_matches(
            sequence(APPROVED.replace(".", "")), APPROVED)
        self.assertFalse(ok)

    def test_a_truncated_note_is_refused(self):
        ok, _ = heyreach.note_matches(sequence(APPROVED[:60]), APPROVED)
        self.assertFalse(ok)


class ItFailsClosedOnEveryAmbiguity(unittest.TestCase):
    def test_an_empty_note_is_refused(self):
        ok, why = heyreach.note_matches(sequence(""), APPROVED)
        self.assertFalse(ok)
        self.assertIn("empty", why)

    def test_no_connection_request_is_refused_rather_than_passed(self):
        ok, why = heyreach.note_matches(
            sequence(APPROVED, node_type="MESSAGE"), APPROVED)
        self.assertFalse(ok)
        self.assertIn("no connection-request note", why)

    def test_a_node_with_no_payload_is_refused(self):
        ok, why = heyreach.note_matches(sequence(payload=False), APPROVED)
        self.assertFalse(ok)
        self.assertIn("no connection-request note", why)

    def test_two_notes_are_refused_because_the_winner_is_unknown(self):
        ok, why = heyreach.note_matches(
            sequence(APPROVED, "something else"), APPROVED)
        self.assertFalse(ok)
        self.assertIn("2 connection notes", why)

    def test_an_empty_sequence_is_refused(self):
        for graph in ({}, {"nodeType": "END"}, {"payload": {}}, None):
            with self.subTest(graph=graph):
                ok, _ = heyreach.note_matches(graph, APPROVED)
                self.assertFalse(ok)

    def test_supplying_no_approved_note_is_refused(self):
        """Comparing against nothing must not read as a match."""
        for approved in (None, "", "   "):
            with self.subTest(approved=approved):
                ok, why = heyreach.note_matches(sequence(APPROVED), approved)
                self.assertFalse(ok)
                self.assertIn("no approved note", why)


class TheNoteIsFoundThroughBranches(unittest.TestCase):
    """The real graph nests the next step under conditional/unconditional."""

    def test_a_note_on_a_branched_node_is_read(self):
        graph = {
            "nodeType": "VIEW_PROFILE",
            "unconditionalNode": {
                "nodeType": "CONNECTION_REQUEST",
                "payload": {"messages": [APPROVED]},
                "conditionalNode": {"nodeType": "END"}}}
        self.assertEqual(heyreach.connection_notes(graph), [APPROVED])
        ok, why = heyreach.note_matches(graph, APPROVED)
        self.assertTrue(ok, why)


if __name__ == "__main__":
    unittest.main()
