"""A LinkedIn variant must not be styled as email.

## The bug this pins

`variantgen.APPROACH_TO_STYLE` is keyed by NODE TYPE - "email",
"linkedin_message", "linkedin_followup", "connection_request" - and
`style_for` resolves an unrecognised key by falling back to the EMAIL table:

    APPROACH_TO_STYLE.get(node_type, APPROACH_TO_STYLE["email"]).get(...)

`generate.py` passed `spec.get("channel")`, which is "linkedin". That is not a
node type, so it did not miss the mapping - **it got the wrong channel's
mapping**, silently. Every LinkedIn variant built through `build_variant_set`
was styled as email: `value_led` resolved to `professional` where LinkedIn's
own table says `peer_to_peer`.

A silent fallback on a path that matters is the defect class this repository
keeps rediscovering, and this one is invisible from the outside because both
answers are valid style names.

`cadence.NODE_TYPE_FOR_CHANNEL` is the canonical translation and already
existed - `cadence.variant_node` used it and this path did not.

These assert on RETURNED VALUES, never on source text.
"""

import unittest

from src import cadence, variantgen


class AChannelIsNotANodeType(unittest.TestCase):

    def test_the_linkedin_node_type_gets_the_linkedin_style(self):
        self.assertEqual(
            variantgen.style_for("linkedin_message", "value_led"),
            "peer_to_peer")

    def test_the_email_node_type_gets_the_email_style(self):
        self.assertEqual(
            variantgen.style_for("email", "value_led"), "professional")

    def test_the_two_channels_do_not_resolve_to_the_same_style(self):
        """The property that makes the bug visible at all.

        If these ever agree again, something is resolving both through one
        table - which is exactly what passing a channel did.
        """
        self.assertNotEqual(
            variantgen.style_for("linkedin_message", "value_led"),
            variantgen.style_for("email", "value_led"))

    def test_the_bare_channel_still_resolves_to_the_email_table(self):
        """Documents the trap rather than hiding it.

        `style_for` has NOT been changed to raise on an unknown node type -
        that would be a wider behavioural change than this fix needs, and
        other callers may rely on the fallback. So the fallback is still
        there and still silently wrong for a channel name. The fix is that
        production no longer HANDS it a channel name; this test exists so the
        next reader learns that from a test rather than from a campaign.
        """
        self.assertEqual(variantgen.style_for("linkedin", "value_led"),
                         variantgen.style_for("email", "value_led"))


class TheTranslationIsCanonicalAndShared(unittest.TestCase):

    def test_cadence_holds_the_channel_to_node_type_mapping(self):
        self.assertEqual(
            cadence.NODE_TYPE_FOR_CHANNEL.get("linkedin"), "linkedin_message")
        self.assertEqual(cadence.NODE_TYPE_FOR_CHANNEL.get("email"), "email")

    def test_translating_a_channel_reaches_the_right_style(self):
        """The whole chain, end to end: channel -> node type -> style."""
        node_type = cadence.NODE_TYPE_FOR_CHANNEL["linkedin"]
        self.assertEqual(variantgen.style_for(node_type, "value_led"),
                         "peer_to_peer")

    def test_variant_node_and_the_generator_agree_on_precedence(self):
        """A step may name its own node_type; otherwise the channel decides.

        `cadence.variant_node` has always had that precedence. The generator
        now uses the same one, so the two cannot disagree about which style a
        step gets.
        """
        spec = {"channel": "linkedin", "node_type": "connection_request"}
        self.assertEqual(cadence.variant_node(spec)["type"],
                         "connection_request")
        spec_without = {"channel": "linkedin"}
        self.assertEqual(cadence.variant_node(spec_without)["type"],
                         "linkedin_message")


if __name__ == "__main__":
    unittest.main()
