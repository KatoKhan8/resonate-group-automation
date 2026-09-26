"""TASK-343 — the LinkedIn graph follows the canonical cadence days.

The HeyReach sequence graph used to hardcode relative delays between
LinkedIn messages (3 HOUR, 3 DAY, 2 DAY, 5 DAY, 7 DAY). Those numbers
did not come from the canonical cadence graph, so editing the cadence
changed the preview but not the provider payload — §5's "one truth"
was broken on the projection that reaches people.

The fix: every MESSAGE-to-MESSAGE delay in the graph is derived from
consecutive day deltas in ``PRODUCTIVE_LI_HEAVY_V1``. This test proves
that derivation holds and — critically — that changing the canonical
graph changes the provider payload.
"""
import sys
import unittest

sys.path.insert(0, ".")

from src.cadencelibrary import PRODUCTIVE_LI_HEAVY_V1
from src.providers import heyreach
from src import heyreachfactory


def _li_canonical_days():
    """The absolute days of each LinkedIn step in the canonical cadence."""
    return sorted(
        s["day"] for s in PRODUCTIVE_LI_HEAVY_V1
        if s.get("channel") == "linkedin"
    )


def _walk_branch(node, kind_filter=None):
    """Walk the unconditionalNode chain, returning (kind, delay, unit) triples.

    When ``kind_filter`` is set, only nodes of that type are returned.
    """
    result = []
    current = node
    while current and isinstance(current, dict):
        k = current.get("nodeType")
        delay = current.get("actionDelay")
        unit = current.get("actionDelayUnit")
        if kind_filter is None or k == kind_filter:
            result.append((k, delay, unit))
        current = current.get("unconditionalNode")
    return result


def _all_nodes(node):
    """Walk the unconditionalNode chain, returning ALL (kind, delay, unit)."""
    result = []
    current = node
    while current and isinstance(current, dict):
        k = current.get("nodeType")
        delay = current.get("actionDelay")
        unit = current.get("actionDelayUnit")
        result.append((k, delay, unit))
        current = current.get("unconditionalNode")
    return result


def _make_copy():
    """The smallest copy block that satisfies the graph builder."""
    msg = {"messages": ["hello {FIRST_NAME}"], "fallbackMessage": "hi there"}
    note = {"messages": ["let's connect"], "fallbackMessage": "connect"}
    return {
        "connection_note": note,
        "connected_1": msg, "connected_2": msg, "connected_3": msg,
        "connected_4": msg,
        "message_2": msg, "message_3": msg, "message_4": msg,
    }


def _make_copy_with_inmail():
    """Copy block including InMail (subject/message object entries)."""
    base = _make_copy()
    inmail_entry = {"subject": "intro {FIRST_NAME}", "message": "hi {FIRST_NAME}"}
    base["inmail"] = {
        "messages": [inmail_entry],
        "fallbackMessage": {"subject": "intro", "message": "hi there"},
    }
    return base


class TheDelaysComeFromTheCanonicalGraph(unittest.TestCase):
    """Acceptance 1: cumulative equality."""

    def test_derived_delays_match_canonical_deltas(self):
        canonical = _li_canonical_days()
        expected = tuple(
            canonical[i + 1] - canonical[i]
            for i in range(1, len(canonical) - 1)
        )
        self.assertEqual(heyreachfactory._li_message_delays(), expected)
        self.assertEqual(heyreach.li_message_delays_from_cadence(), expected)

    def test_already_connected_cumulative_matches_canonical(self):
        """The already-connected branch MESSAGE delays, accounting for the
        VIEW_PROFILE between connected_2 and connected_3, produce cumulative
        gaps that equal the canonical deltas."""
        d1, d2, d3 = heyreachfactory._li_message_delays()
        seq = heyreachfactory._build_sequence_no_inmail(_make_copy())
        already = seq["conditionalNode"]
        all_nodes = _all_nodes(already)
        messages = [(k, d, u) for k, d, u in all_nodes if k == "MESSAGE"]
        view_profiles = [(k, d, u) for k, d, u in all_nodes
                         if k == "VIEW_PROFILE"]

        day_msg_delays = [d for _, d, u in messages[1:] if u == "DAY"]
        vp_day_delays = [d for _, d, u in view_profiles if u == "DAY"]

        canonical = _li_canonical_days()
        canonical_gaps = tuple(
            canonical[i + 1] - canonical[i]
            for i in range(1, len(canonical) - 1))

        # connected_1 → connected_2: d1 (no intermediate action)
        self.assertEqual(day_msg_delays[0], canonical_gaps[0])
        # connected_2 → connected_3: VIEW_PROFILE(vp_delay) + MESSAGE = d2
        vp_delay = vp_day_delays[0] if vp_day_delays else 0
        effective_gap_2 = vp_delay + day_msg_delays[1]
        self.assertEqual(effective_gap_2, canonical_gaps[1])
        # connected_3 → connected_4: d3 (no intermediate action)
        self.assertEqual(day_msg_delays[2], canonical_gaps[2])


class TheGraphMovesWhenTheCanonicalGraphMoves(unittest.TestCase):
    """Acceptance 2: THE TEST THAT MAKES THIS REAL.

    Monkeypatch one LinkedIn step's day in the canonical graph, rebuild,
    and confirm the provider payload's delay CHANGES with it.
    """

    def test_changing_li4_day_changes_the_provider_payload(self):
        original_day = None
        for step in PRODUCTIVE_LI_HEAVY_V1:
            if step["key"] == "li4":
                original_day = step["day"]
                break
        self.assertIsNotNone(original_day)

        old_delays = heyreachfactory._li_message_delays()

        try:
            # +1 preserves sort order (li4 stays between li3=6 and li5=15)
            step["day"] = original_day + 1
            new_delays = heyreachfactory._li_message_delays()
            self.assertNotEqual(
                new_delays, old_delays,
                "changing li4.day did not change the derived delays — "
                "the graph is still hardcoded")
            # d2 = li4 - li3 increased by 1; d3 = li5 - li4 decreased by 1
            self.assertEqual(new_delays[1], old_delays[1] + 1)
            self.assertEqual(new_delays[2], old_delays[2] - 1)

            seq = heyreachfactory._build_sequence_no_inmail(_make_copy())
            already = seq["conditionalNode"]
            all_nodes = _all_nodes(already)
            messages = [(k, d, u) for k, d, u in all_nodes if k == "MESSAGE"]
            day_delays = [d for _, d, u in messages[1:] if u == "DAY"]
            # The last MESSAGE delay (connected_3 → connected_4) is d3
            self.assertEqual(day_delays[2], new_delays[2])
        finally:
            step["day"] = original_day

        restored = heyreachfactory._li_message_delays()
        self.assertEqual(restored, old_delays)

    def test_changing_li3_day_changes_the_derived_delays(self):
        """A different step change, confirming the derivation is general."""
        original_day = None
        for s in PRODUCTIVE_LI_HEAVY_V1:
            if s["key"] == "li3":
                original_day = s["day"]
                break
        old_delays = heyreachfactory._li_message_delays()
        try:
            # +1 preserves sort order (li3 stays between li2=3 and li4=10)
            s["day"] = original_day + 1
            new_delays = heyreachfactory._li_message_delays()
            self.assertNotEqual(new_delays, old_delays)
            # d1 = li3 - li2 increased by 1; d2 = li4 - li3 decreased by 1
            self.assertEqual(new_delays[0], old_delays[0] + 1)
            self.assertEqual(new_delays[1], old_delays[1] - 1)
        finally:
            s["day"] = original_day
        self.assertEqual(heyreachfactory._li_message_delays(), old_delays)

    def test_heyreach_linkedin_sequence_also_moves(self):
        """The include_inmail path derives delays too."""
        original_day = None
        for s in PRODUCTIVE_LI_HEAVY_V1:
            if s["key"] == "li3":
                original_day = s["day"]
                break
        old_delays = heyreach.li_message_delays_from_cadence()
        try:
            s["day"] = original_day + 1
            new_delays = heyreach.li_message_delays_from_cadence()
            self.assertNotEqual(new_delays, old_delays)
            self.assertEqual(new_delays[0], old_delays[0] + 1)
        finally:
            s["day"] = original_day


class FiveStepsTwoBranchesNothingDropped(unittest.TestCase):
    """Acceptance 3: the graph still carries every node type."""

    def test_all_node_types_present_no_inmail(self):
        seq = heyreachfactory._build_sequence_no_inmail(_make_copy())
        nodes, types, truncated = heyreach.walk_sequence(seq)
        self.assertFalse(truncated)
        expected = {"CHECK_IS_CONNECTION", "MESSAGE", "VIEW_PROFILE",
                    "FOLLOW", "CONNECTION_REQUEST", "END"}
        self.assertTrue(expected.issubset(types),
                        f"missing types: {expected - types}")

    def test_all_node_types_present_with_inmail(self):
        seq = heyreach.linkedin_sequence(_make_copy_with_inmail())
        nodes, types, truncated = heyreach.walk_sequence(seq)
        self.assertFalse(truncated)
        expected = {"CHECK_IS_CONNECTION", "MESSAGE", "VIEW_PROFILE",
                    "FOLLOW", "CONNECTION_REQUEST", "INMAIL",
                    "CHECK_IS_OPEN_PROFILE", "END"}
        self.assertTrue(expected.issubset(types),
                        f"missing types: {expected - types}")

    def test_both_branches_have_four_messages(self):
        seq = heyreachfactory._build_sequence_no_inmail(_make_copy())
        already = seq["conditionalNode"]
        cold = seq["unconditionalNode"]
        already_msgs = _walk_branch(already, "MESSAGE")
        cold_root_msgs = []
        cur = cold
        while cur and isinstance(cur, dict):
            if cur.get("nodeType") == "MESSAGE":
                cold_root_msgs.append(cur)
            cond = cur.get("conditionalNode")
            if cond and isinstance(cond, dict):
                cold_root_msgs.extend(
                    n for n in _walk_branch(cond, "MESSAGE"))
            cur = cur.get("unconditionalNode")
        self.assertEqual(len(already_msgs), 4,
                         f"already-connected has {len(already_msgs)} msgs")
        self.assertGreaterEqual(len(cold_root_msgs), 3,
                                "cold path lost messages")


class ThePreviewHalfWasAlreadyFixed(unittest.TestCase):
    """Acceptance 4: verify in one grep-equivalent assertion."""

    def test_preview_reads_step_day_not_hardcoded(self):
        import inspect
        import src.preview as preview
        source = inspect.getsource(preview)
        self.assertNotIn("1, 3, 8, 14", source)
        self.assertNotIn("1/3/8/14", source)
        self.assertIn('step.get("day")', source)


if __name__ == "__main__":
    unittest.main()
