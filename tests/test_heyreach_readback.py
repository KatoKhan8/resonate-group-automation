"""The readback comparison: expected vs actual, field by field.

TASK-053. The operator's acceptance criterion is:

    WRITE -> READ BACK -> COMPARE -> PASS

This test proves the COMPARE step works:
  1. An identical observed/expected exits with all rows passing.
  2. A genuine mismatch (literal name, double brace, repeated message,
     different node count) produces FAIL rows.
  3. The comparison is driven through `build_rows`, the same function
     the script calls - not a separate test-only path.
"""
import json
import unittest

from src.providers import heyreach
from scripts.heyreach_readback import (
    build_rows, _analyse, _root_to_leaf_paths, _path_messages,
    _repeated_on_path, _strip_bare_ends,
)


def _make_sequence():
    """A small but realistic sequence: CHECK -> MESSAGE -> VIEW -> END."""
    copy = {
        "connection_note": {
            "messages": ["{connection_note}"],
            "fallbackMessage": "hi, would be good to connect",
        },
        "connected_1": {
            "messages": ["{connected_1}"],
            "fallbackMessage": "how are things going",
        },
        "message_2": {
            "messages": ["{message_2}"],
            "fallbackMessage": "glad to hear that",
        },
        "message_3": {
            "messages": ["{message_3}"],
            "fallbackMessage": "worth a quick look",
        },
        "message_4": {
            "messages": ["{message_4}"],
            "fallbackMessage": "happy to leave it here",
        },
        "connected_2": {
            "messages": ["{connected_2}"],
            "fallbackMessage": "most people find that useful",
        },
        "connected_3": {
            "messages": ["{connected_3}"],
            "fallbackMessage": "built this for teams like yours",
        },
        "connected_4": {
            "messages": ["{connected_4}"],
            "fallbackMessage": "no worries if not the right time",
        },
    }
    end_connected = heyreach._node("END", 3, "HOUR")
    msg2 = heyreach._node("MESSAGE", 2, "DAY",
                          heyreach._copy("message_2", copy),
                          nxt=end_connected)
    view_connected = heyreach._node("VIEW_PROFILE", 3, "DAY", nxt=msg2)
    already = heyreach._node("MESSAGE", 3, "HOUR",
                             heyreach._copy("connected_1", copy),
                             nxt=view_connected)

    end_cold = heyreach._node("END", 3, "HOUR")
    msg4 = heyreach._node("MESSAGE", 7, "DAY",
                          heyreach._copy("message_4", copy), nxt=end_cold)
    msg3 = heyreach._node("MESSAGE", 5, "DAY",
                          heyreach._copy("message_3", copy), nxt=msg4)
    connect = heyreach._node("CONNECTION_REQUEST", 1, "DAY",
                             heyreach._copy("connection_note", copy),
                             nxt=msg3)
    follow = heyreach._node("FOLLOW", 3, "HOUR", nxt=connect)
    cold = heyreach._node("VIEW_PROFILE", 3, "HOUR", nxt=follow)

    return heyreach._node("CHECK_IS_CONNECTION", 0, "HOUR",
                          cond=already, nxt=cold)


def _add_provider_ends(node):
    """Simulate what the provider does: add bare END on conditionalNode
    of every MESSAGE node."""
    if not isinstance(node, dict):
        return node
    out = dict(node)
    kind = str(out.get("nodeType") or "")
    if kind in ("MESSAGE", "INMAIL") and out.get("conditionalNode") is None:
        out["conditionalNode"] = {"nodeType": "END",
                                  "actionDelay": 0,
                                  "actionDelayUnit": "HOUR"}
    for key in ("conditionalNode", "unconditionalNode"):
        if isinstance(out.get(key), dict):
            out[key] = _add_provider_ends(out[key])
    return out


class TestReadbackComparisonIdentical(unittest.TestCase):
    """An observed sequence identical to expected passes every row."""

    def setUp(self):
        self.expected = _make_sequence()
        # Simulate what the provider returns: same graph plus bare ENDs
        self.observed = _add_provider_ends(
            json.loads(json.dumps(self.expected)))

    def test_all_rows_pass(self):
        rows = build_rows(self.expected, self.observed)
        failures = [(check, exp, act)
                    for check, exp, act, passed in rows if not passed]
        self.assertEqual(failures, [],
                         f"identical sequences should pass every row, "
                         f"but these failed: {failures}")

    def test_node_count_matches_after_stripping(self):
        """The provider adds bare ENDs; the comparison strips them."""
        rows = build_rows(self.expected, self.observed)
        node_row = [r for r in rows if r[0] == "node_count"][0]
        self.assertTrue(node_row[3], "node_count should pass after stripping")


class TestReadbackComparisonDetectsDifferences(unittest.TestCase):
    """A comparison that cannot fail is the defect this repo keeps finding."""

    def setUp(self):
        self.expected = _make_sequence()

    def test_literal_name_detected(self):
        """A sequence carrying 'jacob' must fail the literal check."""
        observed = json.loads(json.dumps(self.expected))
        # Inject a literal name into the connection request note
        _inject_literal(observed, "jacob")
        rows = build_rows(self.expected, observed)
        literal_rows = [r for r in rows if r[0] == "literal:jacob"]
        self.assertTrue(len(literal_rows) > 0,
                        "should have a literal:jacob check row")
        self.assertFalse(literal_rows[0][3],
                         "literal:jacob should FAIL when jacob is present")

    def test_double_brace_detected(self):
        """A sequence carrying {{double}} braces must fail."""
        observed = json.loads(json.dumps(self.expected))
        _inject_double_brace(observed)
        rows = build_rows(self.expected, observed)
        db_rows = [r for r in rows if r[0] == "double_brace_vars"]
        self.assertTrue(len(db_rows) > 0)
        self.assertFalse(db_rows[0][3],
                         "double_brace_vars should FAIL when {{vars}} present")

    def test_repeated_message_detected(self):
        """The same message on one path must fail."""
        observed = json.loads(json.dumps(self.expected))
        _inject_duplicate_message(observed)
        rows = build_rows(self.expected, observed)
        rep_rows = [r for r in rows if r[0] == "repeated_msg_on_path"]
        self.assertTrue(len(rep_rows) > 0)
        self.assertFalse(rep_rows[0][3],
                         "repeated_msg_on_path should FAIL when a message "
                         "repeats on one path")

    def test_node_count_mismatch_detected(self):
        """Different node counts must fail."""
        observed = json.loads(json.dumps(self.expected))
        # Add an extra node to change the count
        _add_extra_node(observed)
        rows = build_rows(self.expected, observed)
        nc_rows = [r for r in rows if r[0] == "node_count"]
        self.assertTrue(len(nc_rows) > 0)
        self.assertFalse(nc_rows[0][3],
                         "node_count should FAIL when counts differ")

    def test_merge_variable_mismatch_detected(self):
        """Expected has merge vars, observed has literals: must fail."""
        observed = json.loads(json.dumps(self.expected))
        # Replace merge variables with literal text
        _replace_vars_with_literals(observed)
        rows = build_rows(self.expected, observed)
        mv_rows = [r for r in rows if r[0] == "merge_variables"]
        self.assertTrue(len(mv_rows) > 0)
        self.assertFalse(mv_rows[0][3],
                         "merge_variables should FAIL when expected has "
                         "variables but observed has literals")


# --- helpers to mutate a sequence graph for failure tests ---

def _inject_literal(node, name):
    """Put a literal name into the first CONNECTION_REQUEST's messages."""
    if not isinstance(node, dict):
        return
    if str(node.get("nodeType") or "") == "CONNECTION_REQUEST":
        payload = node.get("payload")
        if isinstance(payload, dict):
            msgs = payload.get("messages")
            if isinstance(msgs, list) and msgs:
                payload["messages"] = [f"hi {name}, let's connect"]
                return
    for key in ("conditionalNode", "unconditionalNode"):
        if isinstance(node.get(key), dict):
            _inject_literal(node[key], name)


def _inject_double_brace(node):
    """Put a {{double_brace}} variable into the first MESSAGE."""
    if not isinstance(node, dict):
        return
    if str(node.get("nodeType") or "") == "MESSAGE":
        payload = node.get("payload")
        if isinstance(payload, dict):
            msgs = payload.get("messages")
            if isinstance(msgs, list) and msgs:
                payload["messages"] = ["hi {{first_name}}, let's talk"]
                return
    for key in ("conditionalNode", "unconditionalNode"):
        if isinstance(node.get(key), dict):
            _inject_double_brace(node[key])


def _inject_duplicate_message(node):
    """Make two MESSAGE nodes on the same path carry the same text."""
    if not isinstance(node, dict):
        return
    # Find the unconditional chain (the cold path) and duplicate a message
    if str(node.get("nodeType") or "") == "CHECK_IS_CONNECTION":
        nxt = node.get("unconditionalNode")
        if isinstance(nxt, dict):
            # Walk to the first MESSAGE in the cold path
            _set_same_message_in_chain(nxt)
    for key in ("conditionalNode", "unconditionalNode"):
        if isinstance(node.get(key), dict):
            _inject_duplicate_message(node[key])


def _set_same_message_in_chain(node):
    """Set two MESSAGE nodes in a chain to the same text."""
    if not isinstance(node, dict):
        return
    first_text = None
    current = node
    count = 0
    while isinstance(current, dict):
        if str(current.get("nodeType") or "") == "MESSAGE":
            payload = current.get("payload")
            if isinstance(payload, dict):
                msgs = payload.get("messages")
                if isinstance(msgs, list) and msgs:
                    if first_text is None:
                        first_text = msgs[0]
                    else:
                        payload["messages"] = [first_text]
                        count += 1
                        if count >= 1:
                            return
        nxt = current.get("unconditionalNode")
        if isinstance(nxt, dict):
            current = nxt
        else:
            break


def _add_extra_node(node):
    """Add an extra VIEW_PROFILE node to change the node count."""
    if not isinstance(node, dict):
        return
    if str(node.get("nodeType") or "") == "CHECK_IS_CONNECTION":
        nxt = node.get("unconditionalNode")
        if isinstance(nxt, dict):
            extra = heyreach._node("VIEW_PROFILE", 1, "HOUR", nxt=nxt)
            node["unconditionalNode"] = extra
            return
    for key in ("conditionalNode", "unconditionalNode"):
        if isinstance(node.get(key), dict):
            _add_extra_node(node[key])


def _replace_vars_with_literals(node):
    """Replace {merge_var} messages with literal text."""
    if not isinstance(node, dict):
        return
    kind = str(node.get("nodeType") or "")
    if kind in ("MESSAGE", "CONNECTION_REQUEST"):
        payload = node.get("payload")
        if isinstance(payload, dict):
            msgs = payload.get("messages")
            if isinstance(msgs, list):
                payload["messages"] = [
                    "literal text instead of variable"
                    if (isinstance(m, str) and m.startswith("{"))
                    else m
                    for m in msgs]
    for key in ("conditionalNode", "unconditionalNode"):
        if isinstance(node.get(key), dict):
            _replace_vars_with_literals(node[key])


class TestAnalysisHelpers(unittest.TestCase):
    """The helpers the comparison uses are themselves correct."""

    def test_walk_finds_all_nodes(self):
        seq = _make_sequence()
        info = _analyse(seq)
        self.assertGreater(info["nodes"], 0)
        self.assertIn("MESSAGE", info["node_types"])
        self.assertIn("CHECK_IS_CONNECTION", info["node_types"])

    def test_paths_are_non_empty(self):
        seq = _make_sequence()
        paths = _root_to_leaf_paths(seq)
        self.assertGreater(len(paths), 0)
        for path in paths:
            self.assertGreater(len(path), 0)

    def test_no_repetition_in_clean_sequence(self):
        seq = _make_sequence()
        msgs = _path_messages(seq)
        self.assertFalse(_repeated_on_path(msgs))

    def test_strip_bare_ends_removes_provider_ends(self):
        seq = _make_sequence()
        with_ends = _add_provider_ends(json.loads(json.dumps(seq)))
        nodes_before = len(heyreach.walk_sequence(with_ends)[0])
        stripped = _strip_bare_ends(with_ends, seq)
        nodes_after = len(heyreach.walk_sequence(stripped)[0])
        self.assertLess(nodes_after, nodes_before,
                        "stripping bare ENDs should reduce node count")
        self.assertEqual(nodes_after, len(heyreach.walk_sequence(seq)[0]),
                         "after stripping, node count should match original")


if __name__ == "__main__":
    unittest.main()
