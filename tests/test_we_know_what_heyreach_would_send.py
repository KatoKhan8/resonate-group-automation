"""What a HeyReach campaign would actually send, read rather than assumed.

`AddLeadsToCampaignV2` adds a lead to an existing campaign. The message the
prospect receives comes from that campaign's sequence, configured in HeyReach,
and our generated note travels only as a custom field. `POST /campaign/GetAll`
returns fourteen fields and none of them is the sequence, so this system had no
way to know what a lead it pushed would be sent - and said so, in a checkpoint,
as though it were unknowable.

It is not. `GET /campaign/GetCampaignSequence?campaignId=` answers 200 with the
whole node graph. Read live against the campaign most likely to be the canary
target, it says three things that no amount of reasoning from the campaign name
would have produced:

1. Every branch ends in `SEND_LEAD_TO_BISON`, handing the lead to EmailBison
   campaigns 417 and 418. **A "LinkedIn-only" canary sends email**, written by
   somebody else, from an estate whose ownership is separately unproven.
2. The message templates interpolate `{Icebreaker}`. `build_lead_pairs` sends a
   custom field named `note`. A name that does not match is not an error -
   HeyReach substitutes its fallback - so the prospect receives copy this
   system did not write while the system records a send.
3. The connection request node carries no text, so a connection note has
   nowhere to go in this campaign at all.

`sequence_hazards` names those three. It returns facts, not a verdict: each one
is something a person has to weigh, and the reason they are gathered rather
than inferred at the call site is that every one is invisible from the campaign
list.
"""
import json
import unittest

from src.providers import heyreach


def sequence(nodes):
    """A minimal graph in the shape the provider returns."""
    return {"nodeType": "CHECK_IS_CONNECTION", "actionDelay": 0,
            "conditionalNode": nodes[0] if nodes else None,
            "unconditionalNode": nodes[1] if len(nodes) > 1 else None}


MESSAGE = {"nodeType": "MESSAGE",
           "payload": {"messages": ["Hey {FIRST_NAME},\n\n{Icebreaker}\n\nWe built X"],
                       "fallbackMessage": "Hey, we built X"}}
BISON = {"nodeType": "SEND_LEAD_TO_BISON",
         "payload": {"bisonCampaignId": 417, "stopExternalLead": True}}
CONNECT_EMPTY = {"nodeType": "CONNECTION_REQUEST",
                 "payload": {"messages": [], "fallbackMessage": ""}}
PLAIN = {"nodeType": "MESSAGE",
         "payload": {"messages": ["Hi {FIRST_NAME}, a note about {COMPANY}."],
                     "fallbackMessage": "Hi there"}}


class SequenceHazards(unittest.TestCase):

    def hazards(self, seq, supplied=("note",)):
        return dict(heyreach.sequence_hazards(seq, supplied_fields=supplied))

    def test_a_bison_handoff_is_named_with_its_campaigns(self):
        found = self.hazards(sequence([MESSAGE, BISON]))
        self.assertIn(heyreach.BISON_HANDOFF, found)
        self.assertEqual(found[heyreach.BISON_HANDOFF], ["417"])

    def test_a_variable_we_do_not_supply_is_named(self):
        found = self.hazards(sequence([MESSAGE]))
        self.assertIn(heyreach.UNKNOWN_VARIABLE, found)
        self.assertEqual(found[heyreach.UNKNOWN_VARIABLE], ["Icebreaker"])

    def test_supplying_that_field_clears_it(self):
        """The fix is to send the field the campaign asks for."""
        found = self.hazards(sequence([MESSAGE]), supplied=("Icebreaker",))
        self.assertNotIn(heyreach.UNKNOWN_VARIABLE, found)

    def test_heyreach_builtins_are_not_reported(self):
        """Otherwise every sequence looks hazardous and the signal is lost."""
        found = self.hazards(sequence([PLAIN]))
        self.assertNotIn(heyreach.UNKNOWN_VARIABLE, found)

    def test_an_empty_connection_request_is_named(self):
        found = self.hazards(sequence([CONNECT_EMPTY]))
        self.assertIn(heyreach.EMPTY_CONNECTION_NOTE, found)

    def test_a_clean_sequence_reports_nothing(self):
        """The guard has to be able to say yes, or it says nothing."""
        self.assertEqual(self.hazards(sequence([PLAIN])), {})

    def test_hazards_are_facts_not_a_verdict(self):
        """Deliberate: each is something a person weighs, so the function
        returns what it found rather than an allow/deny."""
        found = heyreach.sequence_hazards(sequence([MESSAGE, BISON]), ("note",))
        self.assertIsInstance(found, list)
        for what, _detail in found:
            self.assertIsInstance(what, str)


class TheGetRouteIsAllowlisted(unittest.TestCase):

    def test_the_sequence_route_is_on_the_get_allowlist(self):
        self.assertIn("/campaign/GetCampaignSequence", heyreach.READ_GET_ROUTES)

    def test_a_route_off_the_allowlist_is_refused(self):
        """The same discipline the POST side has: an explicit allowlist, so a
        mutation cannot be reached by naming it."""
        with self.assertRaises(heyreach.ProviderError):
            heyreach._read_get("/campaign/AddLeadsToCampaignV2", {})

    def test_the_send_route_is_not_on_either_allowlist(self):
        send = "/campaign/AddLeadsToCampaignV2"
        self.assertNotIn(send, heyreach.READ_GET_ROUTES)
        self.assertNotIn(send, heyreach.READ_ROUTES_ALL)


if __name__ == "__main__":
    unittest.main()
