#!/usr/bin/env python3
"""No path a real prospect can walk may carry the same message twice.

THE DEFECT THIS PINS. `COPY_MAPPING` sent cadence step `li2` to two graph
roles, `connected_1` and `message_2`. The module docstring justified that by
saying the two roles sit on different branches - true of `chain()`, which
builds the post-connection path, and false of `already`, which used both one
after the other. So a prospect who was already a connection received:

    MESSAGE (3 HOUR)  "how do you currently ensure profitability is visible
                       in your projects?"
    MESSAGE (3 DAY)   "how do you currently ensure profitability is visible
                       in your projects?"

Read back from HeyReach campaign 599020 on 2026-09-14, before any lead had
been written into it. The graph itself was never wrong - its own comment says
"already connected -> message straight away, four of them". Four slots wanted
four different messages and the mapping had three to give.

WHY THIS IS A PATH TEST AND NOT A MAPPING TEST. Asserting that
`COPY_MAPPING` has no duplicate values would have passed on the broken build:
the duplication was legal in the mapping (`li2` is genuinely the first message
on both branches) and only became a repeat where the graph placed the two
roles in sequence. The question is about the graph, so the graph is what is
walked - every root-to-leaf path, with the same copy block the factory would
use.

It is also why this asserts on TEXT rather than on role names. A future change
that renames roles but still feeds one step into two adjacent nodes is the
same defect wearing different labels, and this still catches it.
"""
import unittest

from src import heyreachfactory

# ONE DISTINCT SENTENCE PER CADENCE STEP, FANNED OUT THROUGH `COPY_MAPPING` -
# which is exactly what `assemble_linkedin_copy` does with a real record.
#
# The first version of this fixture gave one distinct sentence per ROLE, and
# it was useless: it passed against the broken mapping. The defect is that two
# roles resolve to the same STEP, so a fixture that hands every role its own
# words cannot express it - every path looked distinct because the fixture had
# made it distinct. Building the block the way the factory builds it is what
# makes the repeat appear.
def copy_block(extra=None):
    block = {}
    for step_key, mapping in heyreachfactory.COPY_MAPPING.items():
        roles = mapping["role"]
        roles = (roles,) if isinstance(roles, str) else roles
        text = f"sentence for {step_key}"
        for role in roles:
            block[role] = {"messages": [text], "fallbackMessage": text}
    block.update(extra or {})
    return block


def message_of(node):
    """The prospect-facing string on a node, or None if it sends no words."""
    payload = node.get("payload") or {}
    entries = payload.get("messages")
    if not isinstance(entries, list) or not entries:
        return None
    first = entries[0]
    if isinstance(first, dict):
        # An INMAIL entry is {subject, message}; both are prospect-facing.
        return " | ".join(str(first.get(f) or "")
                          for f in ("subject", "message"))
    return str(first)


def paths(node, walked=()):
    """Every root-to-leaf path through the graph, as lists of nodes.

    Both branch keys are followed: `conditionalNode` is what happens when the
    node's condition holds (a reply, an accepted invite) and
    `unconditionalNode` is what happens otherwise. A prospect walks exactly
    one path, so the invariant is per path and not per graph.
    """
    walked = walked + (node,)
    children = [node[key] for key in ("conditionalNode", "unconditionalNode")
                if isinstance(node.get(key), dict)]
    if not children:
        return [walked]
    out = []
    for child in children:
        out.extend(paths(child, walked))
    return out


class NoPathSendsTheSameWordsTwice(unittest.TestCase):

    def assert_no_repeats(self, sequence):
        found = paths(sequence)
        self.assertTrue(found, "the graph has no paths")
        carried = 0
        for path in found:
            texts = [t for t in (message_of(n) for n in path) if t]
            carried += len(texts)
            duplicates = {t for t in texts if texts.count(t) > 1}
            self.assertEqual(
                duplicates, set(),
                f"a prospect on this path receives {sorted(duplicates)!r} "
                f"more than once. Path: "
                f"{[n.get('nodeType') for n in path]}")
        self.assertTrue(carried, "no node on any path carries words")

    def test_the_default_graph_repeats_nothing(self):
        sequence, _report = heyreachfactory.build_sequence(copy_block())
        self.assert_no_repeats(sequence)

    def test_the_inmail_graph_repeats_nothing(self):
        inmail = {"subject": "subject for inmail",
                  "message": "sentence for inmail"}
        sequence, _report = heyreachfactory.build_sequence(
            copy_block({"inmail": {"messages": [inmail],
                                   "fallbackMessage": inmail}}),
            include_inmail=True)
        self.assert_no_repeats(sequence)

    def test_the_already_connected_path_carries_four_distinct_messages(self):
        """The branch the defect lived on, stated as a positive.

        Four message nodes, four different sentences. Asserting only "no
        repeats" would also pass on a graph that dropped a node to avoid the
        duplicate, and that would be a silent loss of a touch - the failure
        `cadencelibrary` warns about, where a cadence reports eleven touches
        and sends fewer.
        """
        sequence, _report = heyreachfactory.build_sequence(copy_block())
        already = sequence["conditionalNode"]
        texts = []
        node = already
        while isinstance(node, dict):
            text = message_of(node)
            if text:
                texts.append(text)
            node = node.get("unconditionalNode")
        self.assertEqual(len(texts), 4, texts)
        self.assertEqual(len(set(texts)), 4, texts)

    def test_every_role_the_graph_asks_for_resolves_to_one_step(self):
        """The mapping side of the same invariant.

        A role that resolved to two steps would be a step sent twice; a step
        that resolved to no role would be a touch the cadence promises and the
        graph never sends. Both are read off `COPY_MAPPING` rather than
        asserted about its text.
        """
        step_of = {}
        for step_key, mapping in heyreachfactory.COPY_MAPPING.items():
            roles = mapping["role"]
            roles = (roles,) if isinstance(roles, str) else roles
            for role in roles:
                self.assertNotIn(
                    role, step_of,
                    f"role {role!r} is fed by both {step_of.get(role)!r} and "
                    f"{step_key!r}")
                step_of[role] = step_key
        for role in heyreachfactory.REQUIRED_ROLES:
            self.assertIn(role, step_of,
                          f"the graph requires {role!r} and no step fills it")



class TheDeclaredStepListMatchesWhatTheBuilderDemands(unittest.TestCase):
    """`heyreach.SEQUENCE_STEPS` is read by nothing.

    `grep -rn SEQUENCE_STEPS src/ tests/` returns its own definition and
    nothing else. It declares "the steps `linkedin_sequence` needs words for"
    and no code has ever compared that claim to what the builder actually
    asks for - so it is a second representation of `heyreachfactory.
    REQUIRED_ROLES`, free to drift from it.

    It HAD drifted, and both had to be edited by hand on 2026-09-14 when the
    already-connected branch got its own four roles. Two lists of the same
    truth is how the next change updates one of them.

    Rather than delete a useful piece of documentation or refactor two modules
    to share a constant, this makes the claim testable: every role the list
    names is genuinely required, and nothing else is.
    """

    def roles_without(self, missing):
        block = copy_block()
        block.pop(missing, None)
        return block

    def test_every_declared_step_is_actually_required(self):
        from src.providers import heyreach

        declared = [s for s in heyreach.SEQUENCE_STEPS if s != "inmail"]
        self.assertTrue(declared)
        for role in declared:
            with self.subTest(role=role):
                with self.assertRaises(Exception) as caught:
                    heyreachfactory.build_sequence(self.roles_without(role))
                self.assertIn(role, str(caught.exception))

    def test_the_declared_list_matches_the_factory_s_required_roles(self):
        """The two lists must name the same roles, InMail aside - InMail is in
        the provider's list because its graph has a node for it, and out of
        the factory's because no InMail copy is ever approved."""
        from src.providers import heyreach

        self.assertEqual(
            set(heyreach.SEQUENCE_STEPS) - {"inmail"},
            set(heyreachfactory.REQUIRED_ROLES))


if __name__ == "__main__":
    unittest.main()
