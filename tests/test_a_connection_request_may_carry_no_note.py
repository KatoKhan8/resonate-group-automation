#!/usr/bin/env python3
"""A connection request may carry no note. A message may never be blank.

OPERATOR DECISION, 2026-09-22: "allow the note-less connection request".

`validate_sequence_for_write` refused a payload with no non-empty `messages`
on MESSAGE, INMAIL and CONNECTION_REQUEST alike, because "that reaches a real
person as a blank". True of the first two. Not true of the third: LinkedIn
sends a request with no note, which is what happens whenever somebody clicks
Connect without writing anything, and it is what Productive's best campaign
does - 565765, 129 accepted of 951 requests, 13.6%.

These tests pin the narrowing so it stays a narrowing. The absence of a note
is permitted; a half-written one is not, and nothing about MESSAGE or INMAIL
moved.
"""
import unittest

from src.providers import heyreach


def end(delay=3):
    return {"nodeType": "END", "actionDelay": delay, "actionDelayUnit": "HOUR"}


def request(messages=None, fallback=None, **payload):
    """A CONNECTION_REQUEST is a BRANCHING node: accepted or not.

    So it must carry both children. The first version of this fixture gave
    it only `unconditionalNode` and the validator refused it for that -
    correctly, and nothing to do with the note.
    """
    body = {"messages": messages if messages is not None else [""],
            "fallbackMessage": fallback if fallback is not None else ""}
    body.update(payload)
    return {"nodeType": "CONNECTION_REQUEST", "actionDelay": 3,
            "actionDelayUnit": "HOUR", "payload": body,
            "conditionalNode": end(), "unconditionalNode": end()}


def message(messages, fallback="hello there"):
    return {"nodeType": "MESSAGE", "actionDelay": 3, "actionDelayUnit": "HOUR",
            "payload": {"messages": messages, "fallbackMessage": fallback},
            "unconditionalNode": end()}


class ANoteLessRequestIsAllowed(unittest.TestCase):

    def test_an_empty_note_passes(self):
        heyreach.validate_sequence_for_write(request())

    def test_no_messages_key_at_all_passes(self):
        node = request()
        node["payload"].pop("messages")
        heyreach.validate_sequence_for_write(node)

    def test_the_clients_own_standard_graph_passes(self):
        """The graph this decision exists for. Read from the provider on
        2026-09-21 and stored verbatim; it is the thing that was refused."""
        import json
        import os
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "config", "linkedin",
            "productive-standard.json")
        if not os.path.exists(path):          # the file is the client's, not
            self.skipTest("no stored standard graph on this machine")
        with open(path, encoding="utf-8") as handle:
            graph = json.load(handle)["graph"]
        # Made writable first, exactly as the push script does. A graph read
        # from the provider carries its normalisation and is not a graph you
        # can post back unchanged.
        heyreach.validate_sequence_for_write(
            heyreach.sequence_for_write(graph))

    def test_a_note_that_is_written_must_be_real(self):
        """Permitted is the ABSENCE of a note, not a half-written one."""
        with self.assertRaises(heyreach.SequenceInvalid):
            heyreach.validate_sequence_for_write(
                request(messages=["hi {FIRST_NAME}", "   "],
                        fallback="hi there"))

    def test_a_written_note_still_needs_its_fallback(self):
        with self.assertRaises(heyreach.SequenceInvalid):
            heyreach.validate_sequence_for_write(
                request(messages=["hi {FIRST_NAME}"], fallback=""))

    def test_a_note_of_the_wrong_type_is_still_refused(self):
        with self.assertRaises(heyreach.SequenceInvalid):
            heyreach.validate_sequence_for_write(request(messages=[{"a": 1}]))


class NothingAboutAMessageMoved(unittest.TestCase):

    def test_an_empty_message_is_still_refused(self):
        with self.assertRaises(heyreach.SequenceInvalid):
            heyreach.validate_sequence_for_write(message([""]))

    def test_a_whitespace_message_is_still_refused(self):
        with self.assertRaises(heyreach.SequenceInvalid):
            heyreach.validate_sequence_for_write(message(["   "]))

    def test_a_message_with_no_messages_key_is_still_refused(self):
        node = message(["hello"])
        node["payload"].pop("messages")
        with self.assertRaises(heyreach.SequenceInvalid):
            heyreach.validate_sequence_for_write(node)

    def test_a_real_message_still_passes(self):
        heyreach.validate_sequence_for_write(message(["hello {FIRST_NAME}"]))


if __name__ == "__main__":
    unittest.main()
