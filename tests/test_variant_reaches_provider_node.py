"""TASK-099: a node built from N variants carries N messages.

The HeyReach `payload.messages` field is a list. The comment at
``heyreach.SEQUENCE_STEPS`` says this is where five variants land and the
provider rotates them. TASK-022 built the variant machinery. This test pins
the missing link: that the factory actually puts all N approved variants
into the messages list, not just the one the contact was assigned.

The test FAILS against the current code. ``assemble_linkedin_copy`` resolves
one variant per contact and writes a single-element list. The fix is to
collect every approved variant's text into the role's messages list so the
provider can rotate them.
"""
import unittest

from src import approval, cadence, heyreachfactory, variants


STYLES = ("short_direct", "casual", "professional", "consultative",
          "problem_led")


def five_li_variants(step_key):
    return [variants.variant(f"{step_key}-{style}", style,
                             note=f"{style} linkedin note for {step_key}",
                             status=variants.ACTIVE)
            for style in STYLES]


def _approved_step_with_variant(step_key, variant, day=3, action="message"):
    """A stored step whose words and approval match one specific variant."""
    step = {"key": step_key, "day": day, "channel": "linkedin",
            "linkedin_action": action, "generated": True,
            "note": variant["note"],
            "variant_id": variant["variant_id"],
            "variant_style": variant["style"]}
    step["approval"] = {"fingerprint": approval.fingerprint(step),
                        "at": "2026-09-14T00:00:00"}
    return step


def _record_with_all_variants_approved(contact_key="pat"):
    """A record where li2 has five variants, each independently approved.

    Each variant is stored as a separate step with its own approval. In
    production the cadence holds one step with five variant entries; the
    factory reads the variant list from the spec and resolves one per
    contact. This test builds the spec the same way.
    """
    variant_list = five_li_variants("li2")
    # The stored step uses the first variant's words (sticky assignment).
    stored = _approved_step_with_variant("li2", variant_list[0])

    base_steps = {
        "li1": {"key": "li1", "day": 1, "channel": "linkedin",
                "linkedin_action": "connect", "generated": True,
                "note": "Hi, would love to connect",
                "approval": {"fingerprint": "fp-li1",
                             "at": "2026-09-14T00:00:00"}},
        "li2": stored,
        "li3": {"key": "li3", "day": 6, "channel": "linkedin",
                "linkedin_action": "message", "generated": True,
                "note": "Following up on my earlier note",
                "approval": {"fingerprint": "fp-li3",
                             "at": "2026-09-14T00:00:00"}},
        "li4": {"key": "li4", "day": 10, "channel": "linkedin",
                "linkedin_action": "message", "generated": True,
                "note": "One more thought on your ops pipeline",
                "approval": {"fingerprint": "fp-li4",
                             "at": "2026-09-14T00:00:00"}},
        "li5": {"key": "li5", "day": 15, "channel": "linkedin",
                "linkedin_action": "message", "generated": True,
                "note": "Last note from me - worth a conversation?",
                "approval": {"fingerprint": "fp-li5",
                             "at": "2026-09-14T00:00:00"}},
    }

    return {
        "id": "rec-multi-variant", "client": "demo", "domain": "acme.test",
        "contacts": [{"key": contact_key, "name": "Pat Morgan",
                      "linkedin": f"https://linkedin.com/in/{contact_key}"}],
        "cadence": {contact_key: base_steps},
    }, variant_list


class NodeCarriesAllVariants(unittest.TestCase):
    """A step with N approved variants puts N messages on the node.

    The HeyReach provider rotates messages in the ``payload.messages`` list
    itself. The factory must place every approved variant's text there, not
    just the one the contact was assigned. Assignment per contact is for
    attribution; the provider list is for rotation. Both are needed.
    """

    def test_five_variants_produce_five_messages_in_the_copy_block(self):
        """When li2 has five approved variants, the copy block for the roles
        li2 maps to (connected_1 and message_2) must carry five messages,
        not one."""
        rec, variant_list = _record_with_all_variants_approved("pat")
        campaign = {"campaign_id": "camp-multi-v"}
        seq = [
            {"key": "li1", "day": 1, "channel": "linkedin",
             "linkedin_action": "connect"},
            {"key": "li2", "day": 3, "channel": "linkedin",
             "linkedin_action": "message",
             cadence.VARIANTS_KEY: variant_list},
            {"key": "li3", "day": 6, "channel": "linkedin",
             "linkedin_action": "message"},
            {"key": "li4", "day": 10, "channel": "linkedin",
             "linkedin_action": "message"},
            {"key": "li5", "day": 15, "channel": "linkedin",
             "linkedin_action": "message"},
        ]
        copy, missing = heyreachfactory.assemble_linkedin_copy(
            rec, "pat", cadence_steps=seq, campaign=campaign)

        # li2 maps to both connected_1 and message_2.
        # Each must carry all five variant texts.
        for role in ("connected_1", "message_2"):
            self.assertIn(role, copy,
                          f"{role} missing from copy block")
            messages = copy[role]["messages"]
            self.assertEqual(
                len(messages), 5,
                f"{role} carries {len(messages)} message(s) but the step "
                f"has 5 approved variants. The provider rotates the "
                f"messages list itself; all variants must be present. "
                f"Got: {messages!r}")

    def test_the_variant_texts_are_the_approved_notes(self):
        """Each message in the list is one variant's approved note."""
        rec, variant_list = _record_with_all_variants_approved("pat")
        campaign = {"campaign_id": "camp-multi-v2"}
        seq = [
            {"key": "li1", "day": 1, "channel": "linkedin",
             "linkedin_action": "connect"},
            {"key": "li2", "day": 3, "channel": "linkedin",
             "linkedin_action": "message",
             cadence.VARIANTS_KEY: variant_list},
            {"key": "li3", "day": 6, "channel": "linkedin",
             "linkedin_action": "message"},
            {"key": "li4", "day": 10, "channel": "linkedin",
             "linkedin_action": "message"},
            {"key": "li5", "day": 15, "channel": "linkedin",
             "linkedin_action": "message"},
        ]
        copy, missing = heyreachfactory.assemble_linkedin_copy(
            rec, "pat", cadence_steps=seq, campaign=campaign)

        expected_notes = {v["note"] for v in variant_list}
        actual_notes = set(copy.get("message_2", {}).get("messages", []))
        self.assertEqual(actual_notes, expected_notes,
                         "the messages list does not contain exactly the "
                         "five variant notes")

    def test_a_step_without_variants_still_carries_one_message(self):
        """A step with no variants is unchanged: one message in the list."""
        rec, _ = _record_with_all_variants_approved("pat")
        campaign = {"campaign_id": "camp-no-variant"}
        seq = [
            {"key": "li1", "day": 1, "channel": "linkedin",
             "linkedin_action": "connect"},
            {"key": "li2", "day": 3, "channel": "linkedin",
             "linkedin_action": "message"},
            {"key": "li3", "day": 6, "channel": "linkedin",
             "linkedin_action": "message"},
            {"key": "li4", "day": 10, "channel": "linkedin",
             "linkedin_action": "message"},
            {"key": "li5", "day": 15, "channel": "linkedin",
             "linkedin_action": "message"},
        ]
        copy, missing = heyreachfactory.assemble_linkedin_copy(
            rec, "pat", cadence_steps=seq, campaign=campaign)

        # li3 has no variants: exactly one message.
        self.assertEqual(len(copy["message_3"]["messages"]), 1)


if __name__ == "__main__":
    unittest.main()
