"""A lead is not pushed into a sequence whose copy we cannot render.

`sequence_hazards` has been able to detect this since it was written and
nothing called it. That is the defect this repository keeps producing: a thing
computed correctly that nothing downstream reads. Proven by running it against
the real payload builder on 2026-09-08:

    custom fields on the wire: note, record_id, contact_key, client,
                               sender_id, sender_account_id
    Icebreaker supplied:       False
    hazards:                   [(UNKNOWN_VARIABLE, ['Icebreaker'])]

HeyReach campaign 565765 is the only campaign in the workspace whose copy uses
a non-builtin variable, and it uses `{Icebreaker}`. HeyReach does not error on
a variable it cannot fill - it quietly substitutes `fallbackMessage`. So the
prospect receives copy this system did not write, and the system records a
send. Nothing anywhere reports a problem, which is what makes it worth a gate
rather than a warning.

Only the unknown variable refuses. A Bison handoff and an empty connection note
are real hazards and are returned for a person to weigh: sixteen of this
workspace's campaigns hand off to Bison deliberately, and refusing those would
block working campaigns to no purpose.
"""
import unittest

from src import push, store
from src.providers import heyreach
from tests.test_push import PushTest

PROFILE = "https://www.linkedin.com/in/example"


def message(text):
    return {"nodeType": "MESSAGE",
            "payload": {"messages": [text], "fallbackMessage": "Hi there"}}


def sequence(*nodes):
    """A graph in the shape the provider returns."""
    head = {"nodeType": "CHECK_IS_CONNECTION", "actionDelay": 0,
            "conditionalNode": nodes[0] if nodes else None,
            "unconditionalNode": nodes[1] if len(nodes) > 1 else None}
    return head


# The shape of 565765's first message node, read live on 2026-09-08.
ICEBREAKER = sequence(message("Hey {FIRST_NAME},\n\n{Icebreaker}\n\nWorth 20 minutes?"))
BUILTINS_ONLY = sequence(message("Hi {FIRST_NAME}, a note about {COMPANY}."))
BISON = {"nodeType": "SEND_LEAD_TO_BISON",
         "payload": {"bisonCampaignId": 417, "stopExternalLead": True}}


def row(**over):
    base = {"linkedin_url": PROFILE, "first_name": "Ada", "last_name": "L",
            "company": "Example", "title": "COO", "note": "a note",
            "record_id": "rec-1", "contact_key": "c-1", "client": "demo"}
    base.update(over)
    return base


class TheGateRefusesCopyWeCannotRender(unittest.TestCase):

    def test_a_variable_we_do_not_supply_refuses(self):
        with self.assertRaises(heyreach.SequenceRefused):
            heyreach.refuse_unsupported_sequence(ICEBREAKER, rows=[row()])

    def test_the_refusal_names_the_variable(self):
        with self.assertRaises(heyreach.SequenceRefused) as caught:
            heyreach.refuse_unsupported_sequence(ICEBREAKER, rows=[row()],
                                                 campaign_id="565765")
        said = str(caught.exception)
        self.assertIn("Icebreaker", said)
        self.assertIn("565765", said)

    def test_the_refusal_says_what_would_actually_happen(self):
        """"Unknown variable" is not the danger. The fallback is."""
        with self.assertRaises(heyreach.SequenceRefused) as caught:
            heyreach.refuse_unsupported_sequence(ICEBREAKER, rows=[row()])
        self.assertIn("fallback", str(caught.exception))

    def test_supplying_the_field_clears_the_refusal(self):
        """The gate has to be satisfiable, or it is just a ban."""
        supplied = row(custom_fields={"Icebreaker": "saw your case study"})
        self.assertEqual(
            heyreach.refuse_unsupported_sequence(ICEBREAKER, rows=[supplied]),
            [])

    def test_that_field_actually_reaches_the_wire(self):
        """Otherwise the gate passes on a promise nothing keeps."""
        pair = heyreach.build_lead_pairs(
            [row(custom_fields={"Icebreaker": "saw your case study"})], 1)[0]
        sent = {f["name"]: f["value"] for f in pair["lead"]["customUserFields"]}
        self.assertEqual(sent.get("Icebreaker"), "saw your case study")

    def test_a_builtin_only_sequence_passes(self):
        self.assertEqual(
            heyreach.refuse_unsupported_sequence(BUILTINS_ONLY, rows=[row()]),
            [])

    def test_an_empty_custom_value_is_not_a_supplied_field(self):
        """An empty Icebreaker renders an empty line, which is not better
        than the fallback and must not satisfy the gate."""
        with self.assertRaises(heyreach.SequenceRefused):
            heyreach.refuse_unsupported_sequence(
                ICEBREAKER, rows=[row(custom_fields={"Icebreaker": ""})])

    # ------------------------------------------- what it refuses to refuse

    def test_a_bison_handoff_is_reported_not_refused(self):
        found = heyreach.refuse_unsupported_sequence(
            sequence(message("Hi {FIRST_NAME}"), BISON), rows=[row()])
        self.assertIn(heyreach.BISON_HANDOFF, dict(found))

    def test_sixteen_working_campaigns_are_not_blocked(self):
        """The point of the line above, stated as the consequence."""
        try:
            heyreach.refuse_unsupported_sequence(
                sequence(message("Hi {FIRST_NAME}"), BISON), rows=[row()])
        except heyreach.SequenceRefused:
            self.fail("a deliberate Bison handoff must not refuse a push")


class TheSuppliedFieldListIsDerived(unittest.TestCase):
    """A hand-maintained copy drifts silently in the safe-looking direction:
    a name still listed but no longer sent makes a hazard disappear."""

    def test_it_matches_what_the_builder_produces(self):
        full = row(sender_id="s-1", sender_account_id="a-1")
        pair = heyreach.build_lead_pairs([full], 1)[0]
        self.assertEqual(heyreach.supplied_field_names([full]),
                         [f["name"] for f in pair["lead"]["customUserFields"]])

    def test_it_reports_the_full_contract_not_the_smallest_row(self):
        """`build_lead_pairs` omits falsy fields, so probing with an empty
        row would report a shorter list than the builder can produce."""
        for name in ("note", "record_id", "contact_key", "client",
                     "sender_id", "sender_account_id"):
            self.assertIn(name, heyreach.supplied_field_names())

    def test_a_row_can_add_to_it(self):
        self.assertIn("Icebreaker", heyreach.supplied_field_names(
            [row(custom_fields={"Icebreaker": "x"})]))


class ThePushPathConsumesIt(PushTest):
    """The half that matters. A gate nothing calls is the original defect,
    so this runs against the real estate and the real eligibility path
    rather than a hand-built item that would prove only that the function
    can be called."""

    def linkedin_items(self):
        items, _ = push.collect(store.load(), day=21)
        found = [i for i in items if i["channel"] == "linkedin"]
        self.assertTrue(found, "fixture supplies no LinkedIn item to gate")
        return found

    def test_payloads_refuses_when_the_sequence_needs_more(self):
        with self.assertRaises(heyreach.SequenceRefused):
            push.payloads(self.linkedin_items(),
                          heyreach_campaign_id="565765",
                          heyreach_sequence=ICEBREAKER)

    def test_no_postable_body_survives_the_refusal(self):
        """A refusal after the body exists leaves something that looks ready
        to post."""
        got = None
        try:
            got = push.payloads(self.linkedin_items(),
                                heyreach_campaign_id="565765",
                                heyreach_sequence=ICEBREAKER)
        except heyreach.SequenceRefused:
            pass
        self.assertIsNone(got)

    def test_a_clean_sequence_builds_as_before(self):
        built = push.payloads(self.linkedin_items(), heyreach_campaign_id="1",
                              heyreach_sequence=BUILTINS_ONLY)
        self.assertTrue(built["heyreach"]["count"])

    def test_passing_no_sequence_checks_nothing_and_says_so(self):
        """Recorded rather than asserted as good: `run()` still owes the
        live fetch, and this documents that the gate is opt-in today."""
        built = push.payloads(self.linkedin_items(),
                              heyreach_campaign_id="565765")
        self.assertTrue(built["heyreach"]["count"])


class TheOperatorCommandAnswersBeforeACanary(PushTest):
    """`--check` says the key works. This says the copy works, which is a
    different question and the one that reaches a prospect."""

    def report(self, sequence):
        import io as _io
        import contextlib
        from src.providers import heyreach as hr
        real = hr.campaign_sequence
        hr.campaign_sequence = lambda cid: sequence
        self.addCleanup(setattr, hr, "campaign_sequence", real)
        out = _io.StringIO()
        with contextlib.redirect_stdout(out):
            code = hr.main(["--sequence", "565765"])
        return code, out.getvalue()

    def test_an_unrenderable_campaign_exits_nonzero(self):
        code, _ = self.report(ICEBREAKER)
        self.assertEqual(code, 1)

    def test_it_names_the_variable_and_what_would_happen(self):
        _, said = self.report(ICEBREAKER)
        self.assertIn("Icebreaker", said)
        self.assertIn("fallback", said)

    def test_a_renderable_campaign_exits_zero(self):
        code, said = self.report(BUILTINS_ONLY)
        self.assertEqual(code, 0)
        self.assertIn("ok", said)

    def test_a_bison_handoff_is_a_note_rather_than_a_refusal(self):
        code, said = self.report(sequence(message("Hi {FIRST_NAME}"), BISON))
        self.assertEqual(code, 0)
        self.assertIn("note", said)

    def test_it_says_what_we_supply_so_the_gap_is_actionable(self):
        _, said = self.report(ICEBREAKER)
        self.assertIn("record_id", said)


if __name__ == "__main__":
    unittest.main()
