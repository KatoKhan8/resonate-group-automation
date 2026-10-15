"""The empty connection note is a decision, not an accident. TASK 0180
(GLM-C), 2026-10-15.

OPERATOR DECISION, 2026-10-15 22:35: connection requests go out WITHOUT a
note ("može connection request bez poruke" — DECISION-linkedin-connection-
note-2026-10-15.md in resonate-ops). So the CONNECTION_REQUEST node of
`config/linkedin/productive-standard.json` holds `messages: [""]` and
`fallbackMessage: ""`, and that is correct as it stands.

Until that decision, this node read as blocker B3 - unwritten copy. From
that day it reads as a decision. The two are byte-identical on disk, and
nothing in the repository recorded which one it was: the catalogue's own
failure shape, a state indistinguishable from its opposite. This module is
the record. It goes RED if anyone fills the note - not because a note
would be wrong, but because it would be a reversal of a decision made by
nobody. The decision is the operator's to reverse, and reversing it needs
a new one.

Absent and empty are different states and are kept different here: the
node MISSING from the graph is a bigger change than the node's note
being filled, and fails with its own message.

The second direction - our own `li1` render step
(`src/heyreachfactory.py` keys it `role: "connection_note"`), which would
write a note through a path other than this JSON if it were ever wired -
is NOT covered by this pin. Which of the two authorities actually ships
is being measured under `queue/glm/0068`, which had not been dispatched
when this was written (queue root only, no watcher START, no lane entry).
The pin holds the JSON; the li1 direction is uncovered and named as such
in the lane log.

This file pins; it does not permit. The narrowing that ALLOWS an empty
note is `tests/test_a_connection_request_may_carry_no_note.py`, and the
two directions are complements: that one keeps the validator from
refusing the decision, this one keeps the decision from drifting.
"""
import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STANDARD = os.path.join(ROOT, "config", "linkedin",
                        "productive-standard.json")

REVERSES_THE_DECISION = (
    "A filled connection-request note REVERSES an operator decision: on "
    "2026-10-15 22:35 the operator decided connection requests go out "
    "without a note (DECISION-linkedin-connection-note-2026-10-15.md). "
    "Filling it is not a value being wrong and no value change fixes it "
    "back; it needs a NEW operator decision, and until one exists the "
    "note stays empty.")

ABSENT_IS_NOT_EMPTY = (
    "The CONNECTION_REQUEST node is missing from the stored standard "
    "graph. Absent and empty are different states: the operator decision "
    "of 2026-10-15 pins the node's note as EMPTY, with the node present "
    "and the 21-day withdrawal configured on it. A graph without the "
    "node is a different sequence than the one decided on, and restoring "
    "or reshaping it needs its own decision - not a silent edit here.")

DRIFT_ON_THE_SAME_NODE = (
    "toBeWithdrawnAfterDays sits on the same node as the empty-note "
    "decision, and a silent change to it is the same class of drift: the "
    "recorded decision keeps the 21-day withdrawal "
    "(DECISION-linkedin-connection-note-2026-10-15.md).")


def connection_request_nodes(node):
    """Every CONNECTION_REQUEST node in the stored graph, at any depth.

    Walked by nodeType rather than by position, so a re-serialised or
    re-nested file is still read correctly; the shape the decision named
    is the node, not its address.
    """
    found = []
    if isinstance(node, dict):
        if node.get("nodeType") == "CONNECTION_REQUEST":
            found.append(node)
        for key in ("conditionalNode", "unconditionalNode"):
            found.extend(connection_request_nodes(node.get(key)))
    return found


def the_stored_graph():
    # No skip-if-missing: the file is tracked in git, and its absence is
    # the unreadable-authority case - which never reads as a pass.
    with open(STANDARD, encoding="utf-8") as handle:
        return json.load(handle)["graph"]


class TheEmptyNoteIsADecision(unittest.TestCase):

    def the_decided_node(self):
        """The one CONNECTION_REQUEST node the decision was made about.

        Shared by every test below so the absent case is caught once,
        everywhere, with the absent message - a missing node must not
        reach the note assertions and fail with a message about notes.
        """
        nodes = connection_request_nodes(the_stored_graph())
        self.assertEqual(len(nodes), 1, ABSENT_IS_NOT_EMPTY)
        return nodes[0]

    def test_absent_is_not_empty_the_node_itself_is_present(self):
        self.the_decided_node()

    def test_the_note_is_empty_because_the_operator_decided_it(self):
        payload = self.the_decided_node().get("payload") or {}
        self.assertEqual(payload.get("messages"), [""],
                         REVERSES_THE_DECISION)
        self.assertEqual(payload.get("fallbackMessage"), "",
                         REVERSES_THE_DECISION)

    def test_the_withdrawal_window_stays_at_21_days(self):
        self.assertEqual(
            (self.the_decided_node().get("payload") or {}).get(
                "toBeWithdrawnAfterDays"), 21, DRIFT_ON_THE_SAME_NODE)


if __name__ == "__main__":
    unittest.main()
