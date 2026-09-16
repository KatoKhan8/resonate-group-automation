"""A graph read from HeyReach must be writable again.

`set_sequence`'s docstring records the asymmetry: the provider normalises, so
"a UI-built graph carries `conditionalNode: END` on message nodes and a
written one does not". `validate_sequence_for_write` therefore refuses a graph
read straight back from `GetCampaignSequence` - correctly, because a MESSAGE
is not a branching node and must not carry a `conditionalNode`.

Measured 2026-09-16 while reproducing campaign 599020's sequence onto the
canary 604869. `sequence_for_write` strips exactly that and nothing else.
"""
import unittest

from src.providers import heyreach


class SequenceForWrite(unittest.TestCase):

    def test_an_end_terminator_is_stripped_from_a_message(self):
        read = {"nodeType": "MESSAGE", "actionDelay": 3,
                "payload": {"messages": ["{connected_1}"]},
                "conditionalNode": {"nodeType": "END", "actionDelay": 0}}
        out = heyreach.sequence_for_write(read)
        self.assertNotIn("conditionalNode", out)

    def test_a_branching_node_keeps_its_branches(self):
        """CHECK_IS_CONNECTION is allowed to branch, so nothing is removed."""
        read = {"nodeType": "CHECK_IS_CONNECTION",
                "conditionalNode": {"nodeType": "END"},
                "unconditionalNode": {"nodeType": "MESSAGE",
                                      "payload": {"messages": ["x"]}}}
        out = heyreach.sequence_for_write(read)
        self.assertIn("conditionalNode", out)
        self.assertEqual(out["conditionalNode"]["nodeType"], "END")

    def test_a_real_successor_is_never_dropped(self):
        """Only an END child goes. A real successor IS the sequence, and
        dropping one would silently shorten what a prospect receives."""
        read = {"nodeType": "MESSAGE", "payload": {"messages": ["a"]},
                "conditionalNode": {"nodeType": "MESSAGE",
                                    "payload": {"messages": ["b"]}}}
        out = heyreach.sequence_for_write(read)
        self.assertIn("conditionalNode", out)
        self.assertEqual(out["conditionalNode"]["payload"]["messages"], ["b"])

    def test_the_input_is_not_mutated(self):
        read = {"nodeType": "MESSAGE", "payload": {"messages": ["a"]},
                "conditionalNode": {"nodeType": "END"}}
        heyreach.sequence_for_write(read)
        self.assertIn("conditionalNode", read)

    def test_it_recurses_into_both_branches(self):
        read = {"nodeType": "CHECK_IS_CONNECTION",
                "conditionalNode": {
                    "nodeType": "MESSAGE", "payload": {"messages": ["a"]},
                    "conditionalNode": {"nodeType": "END"}},
                "unconditionalNode": {
                    "nodeType": "MESSAGE", "payload": {"messages": ["b"]},
                    "conditionalNode": {"nodeType": "END"}}}
        out = heyreach.sequence_for_write(read)
        self.assertNotIn("conditionalNode", out["conditionalNode"])
        self.assertNotIn("conditionalNode", out["unconditionalNode"])


if __name__ == "__main__":
    unittest.main()
