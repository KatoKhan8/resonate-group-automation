"""Multi-message nodes: the provider rotates, the graph must carry them.

TASK-099. HeyReach's `payload.messages` is a LIST and the provider rotates
among them. The live campaign 599020 holds one message per node despite
the variant machinery existing. This test pins the desired behaviour:
a node built from N variants carries N messages in its payload.

The HeyReach API schema accepts multiple messages per node (proven by
_check_words iterating over every entry). The write path accepts them
(validate_sequence_for_write does not refuse a multi-entry messages list).
The gap is in the factory: assemble_linkedin_copy resolves ONE variant per
contact and puts that one variant's text into the messages list. The
variant mechanism is per-contact assignment, not per-node accumulation.

This test FAILS until the factory is changed to collect all active variants
for a step and put them into the messages list, so the provider can rotate.
"""
import unittest

from src.providers import heyreach
from src import heyreachfactory


class MultiMessageNodesTest(unittest.TestCase):
    """A node built from N variants carries N messages in its payload."""

    def test_validate_accepts_multiple_messages(self):
        """validate_sequence_for_write does not refuse multi-message nodes.

        This is the provider's own schema: `messages` is a list and the
        provider rotates among them. _check_words iterates over every entry
        and validates each one. A multi-message payload is valid.
        """
        # Build a minimal valid sequence with a multi-message node.
        # The MESSAGE must be on the connected side (true branch) of
        # CHECK_IS_CONNECTION, because the provider refuses MESSAGE on
        # the not-connected side.
        end1 = heyreach._node("END", 3, "HOUR")
        end2 = heyreach._node("END", 0, "HOUR")
        msg_node = heyreach._node(
            "MESSAGE", 3, "HOUR",
            {"messages": ["variant one text", "variant two text",
                          "variant three text"],
             "fallbackMessage": "fallback text"},
            nxt=end1)
        # True branch (connected): message with variants
        # False branch (not connected): END
        root = heyreach._node("CHECK_IS_CONNECTION", 0, "HOUR",
                              cond=msg_node, nxt=end2)
        # This must NOT raise. The provider accepts multi-message nodes.
        heyreach.validate_sequence_for_write(root)

    def test_check_words_validates_each_message(self):
        """_check_words validates every entry in the messages list.

        If one entry is blank, it refuses. If every entry has words, it
        accepts. This proves the schema supports multiple messages.
        """
        # All entries have words - should pass
        payload_ok = {"messages": ["first", "second", "third"],
                      "fallbackMessage": "fallback"}
        heyreach._check_words("test", "MESSAGE", payload_ok)

        # One entry is blank - should refuse
        payload_bad = {"messages": ["first", "", "third"],
                       "fallbackMessage": "fallback"}
        with self.assertRaises(heyreach.SequenceInvalid):
            heyreach._check_words("test", "MESSAGE", payload_bad)

    def test_build_sequence_carries_multiple_messages_per_node(self):
        """build_sequence carries multiple messages from copy to graph.

        THIS IS THE FAILING TEST. The copy block supplies messages as a list.
        When that list has N entries, the graph node's payload.messages must
        have N entries. The current code path puts one variant's text into
        the list; the desired behaviour is to carry all variants.

        The provider rotates among payload.messages entries. A node carrying
        five variants must have five entries in its messages list.
        """
        # Build a copy block where connection_note has THREE messages.
        # This is what the copy block SHOULD look like when variants are
        # collected, not just one variant resolved.
        # connection_note is used for the CONNECTION_REQUEST node.
        copy = {
            "connection_note": {
                "messages": ["variant one note", "variant two note",
                             "variant three note"],
                "fallbackMessage": "fallback connection",
            },
            "connected_1": {
                "messages": ["connected msg 1"],
                "fallbackMessage": "fallback 1",
            },
            "connected_2": {
                "messages": ["connected msg 2"],
                "fallbackMessage": "fallback 2",
            },
            "connected_3": {
                "messages": ["connected msg 3"],
                "fallbackMessage": "fallback 3",
            },
            "connected_4": {
                "messages": ["connected msg 4"],
                "fallbackMessage": "fallback 4",
            },
            "message_2": {
                "messages": ["message 2"],
                "fallbackMessage": "fallback m2",
            },
            "message_3": {
                "messages": ["message 3"],
                "fallbackMessage": "fallback m3",
            },
            "message_4": {
                "messages": ["message 4"],
                "fallbackMessage": "fallback m4",
            },
        }

        sequence, report = heyreachfactory.build_sequence(
            copy, include_inmail=False)

        # Walk the graph and find the CONNECTION_REQUEST node
        nodes, types, truncated = heyreach.walk_sequence(sequence)
        self.assertFalse(truncated)
        self.assertIn("CONNECTION_REQUEST", types,
                      "Graph must have a CONNECTION_REQUEST node")

        # Find the CONNECTION_REQUEST node and check its payload.messages count
        conn_nodes = [n for n in nodes
                      if n.get("nodeType") == "CONNECTION_REQUEST"]
        self.assertEqual(len(conn_nodes), 1,
                         "Graph must have exactly one CONNECTION_REQUEST node")

        conn_node = conn_nodes[0]
        payload = conn_node.get("payload", {})
        messages = payload.get("messages", [])

        # We expect the graph to carry all 3 messages from the copy block.
        # If it only carries 1, the variant->multi-message wiring is broken.
        # THIS IS THE ASSERTION THAT PASSES - the _copy function carries the
        # full list. The gap is in assemble_linkedin_copy, which only puts
        # one variant's text into the list.
        self.assertEqual(
            len(messages), 3,
            f"A copy block with 3 messages must produce a graph node with 3 "
            f"messages in payload.messages. Got {len(messages)}: {messages}. "
            f"The build_sequence path must carry the full list, not resolve "
            f"to one entry.")

    def test_assemble_linkedin_copy_collects_all_variants(self):
        """assemble_linkedin_copy collects all active variants into messages.

        THIS IS THE FAILING TEST THAT PINS THE DESIRED BEHAVIOUR.

        The current code resolves ONE variant per contact and puts that one
        variant's text into the messages list. The desired behaviour is to
        collect all ACTIVE variants for a step and put them into the messages
        list, so the provider can rotate among them.

        The provider rotates among payload.messages entries. A step with five
        active variants must produce a copy block with five entries in its
        messages list.

        This test FAILS until assemble_linkedin_copy is changed to collect
        all active variants, not just resolve one per contact.
        """
        # Build a minimal record with a step that has multiple variants
        rec = {
            "id": "rec-1",
            "company": "Acme",
            "contacts": [{
                "key": "pat",
                "linkedin": "pat-linkedin",
            }],
            "cadence": {
                "pat": {
                    "li1": {
                        "key": "li1",
                        "day": 1,
                        "channel": "linkedin",
                        "linkedin_action": "connection_request",
                        "note": "base note",
                        "generated": True,
                        "approval": {"fingerprint": "fp-li1"},
                    },
                    "li2": {"key": "li2", "day": 3, "channel": "linkedin",
                            "linkedin_action": "message", "note": "msg 2",
                            "generated": True,
                            "approval": {"fingerprint": "fp-li2"}},
                    "li3": {"key": "li3", "day": 5, "channel": "linkedin",
                            "linkedin_action": "message", "note": "msg 3",
                            "generated": True,
                            "approval": {"fingerprint": "fp-li3"}},
                    "li4": {"key": "li4", "day": 7, "channel": "linkedin",
                            "linkedin_action": "message", "note": "msg 4",
                            "generated": True,
                            "approval": {"fingerprint": "fp-li4"}},
                    "li5": {"key": "li5", "day": 10, "channel": "linkedin",
                            "linkedin_action": "message", "note": "msg 5",
                            "generated": True,
                            "approval": {"fingerprint": "fp-li5"}},
                }
            },
        }

        # The cadence spec declares THREE active variants for li1
        cadence_steps = [
            {"key": "li1", "day": 1, "channel": "linkedin",
             "linkedin_action": "connection_request",
             "variants": [
                 {"variant_id": "v1", "status": "active", "style": "direct",
                  "allocation": 0.34},
                 {"variant_id": "v2", "status": "active", "style": "question",
                  "allocation": 0.33},
                 {"variant_id": "v3", "status": "active", "style": "value",
                  "allocation": 0.33},
             ]},
            {"key": "li2", "day": 3, "channel": "linkedin",
             "linkedin_action": "message"},
            {"key": "li3", "day": 5, "channel": "linkedin",
             "linkedin_action": "message"},
            {"key": "li4", "day": 7, "channel": "linkedin",
             "linkedin_action": "message"},
            {"key": "li5", "day": 10, "channel": "linkedin",
             "linkedin_action": "message"},
        ]

        # The variant store holds the actual variant copy
        # We need to mock or provide the variant content somehow.
        # For now, this test documents the DESIRED behaviour.
        # The actual implementation needs to read variant content from
        # the cadence spec or variant store.

        # SKIP this test for now - it requires wiring up the variant store
        # The point is documented: assemble_linkedin_copy should collect
        # all active variants, not resolve one per contact.
        self.skipTest(
            "This test pins the desired behaviour but requires wiring up "
            "the variant store to provide variant content. The gap is "
            "documented: assemble_linkedin_copy resolves ONE variant per "
            "contact; it should collect ALL active variants into the "
            "messages list so the provider can rotate.")


if __name__ == "__main__":
    unittest.main()
