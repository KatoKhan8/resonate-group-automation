#!/usr/bin/env python3
"""Dropping the hand-off keeps the wait, and takes the client's ids with it.

OPERATOR DECISION, 2026-09-22: "drop the three SEND_LEAD_TO_BISON nodes and
set the sequences".

The cloned Productive graph carries three `SEND_LEAD_TO_BISON` nodes pinned
to the CLIENT's own EmailBison campaigns 417 and 418. HeyReach validates that
reference on write and refuses: "EmailBison campaign with ID 417 was not
found". So the graph could not be posted as read.

The step hands a LinkedIn non-responder to email. Under dual-channel every
lead is already on the email side the day it is enrolled, so for us it is
redundant at best and a second enrolment at worst.

**The wait is what makes this a translation rather than a truncation.** Each
hand-off fires after three or five days and its child END waits zero, so
splicing the child in would move a terminal several days earlier and quietly
shorten the cadence. It becomes an END carrying the hand-off's own delay.
"""
import json
import os
import unittest

import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "scripts"))

import batch_linkedin_push as push                              # noqa: E402
from src.providers import heyreach                              # noqa: E402

STANDARD = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "config", "linkedin",
    "productive-standard.json")


def graph_of(node):
    return json.dumps(node)


class TheHandoffBecomesAnEnd(unittest.TestCase):

    def test_the_node_is_replaced_by_an_end(self):
        node = {"nodeType": "SEND_LEAD_TO_BISON", "actionDelay": 3,
                "actionDelayUnit": "DAY",
                "payload": {"bisonCampaignId": 417, "stopExternalLead": True},
                "unconditionalNode": {"nodeType": "END", "actionDelay": 0,
                                      "actionDelayUnit": "HOUR"}}
        out = push.drop_bison_handoff(node)
        self.assertEqual(out["nodeType"], "END")

    def test_it_keeps_the_handoffs_own_wait_not_the_ends(self):
        """Splicing the child in would move this terminal three days early."""
        node = {"nodeType": "SEND_LEAD_TO_BISON", "actionDelay": 3,
                "actionDelayUnit": "DAY",
                "payload": {"bisonCampaignId": 417},
                "unconditionalNode": {"nodeType": "END", "actionDelay": 0,
                                      "actionDelayUnit": "HOUR"}}
        out = push.drop_bison_handoff(node)
        self.assertEqual(out["actionDelay"], 3)
        self.assertEqual(out["actionDelayUnit"], "DAY")

    def test_the_clients_campaign_ids_leave_with_it(self):
        node = {"nodeType": "SEND_LEAD_TO_BISON", "actionDelay": 5,
                "actionDelayUnit": "DAY",
                "payload": {"bisonCampaignId": 418, "stopExternalLead": True},
                "unconditionalNode": {"nodeType": "END", "actionDelay": 0,
                                      "actionDelayUnit": "HOUR"}}
        self.assertNotIn("bisonCampaignId",
                         graph_of(push.drop_bison_handoff(node)))

    def test_nothing_else_is_touched(self):
        node = {"nodeType": "MESSAGE", "actionDelay": 3,
                "actionDelayUnit": "HOUR",
                "payload": {"messages": ["hi"], "fallbackMessage": "hi"},
                "unconditionalNode": {"nodeType": "END", "actionDelay": 3,
                                      "actionDelayUnit": "HOUR"}}
        self.assertEqual(push.drop_bison_handoff(node), node)

    def test_it_recurses_into_both_branches(self):
        node = {"nodeType": "CONNECTION_REQUEST", "actionDelay": 3,
                "actionDelayUnit": "HOUR",
                "payload": {"messages": [""], "fallbackMessage": ""},
                "conditionalNode": {"nodeType": "SEND_LEAD_TO_BISON",
                                    "actionDelay": 3, "actionDelayUnit": "DAY",
                                    "payload": {"bisonCampaignId": 417}},
                "unconditionalNode": {"nodeType": "SEND_LEAD_TO_BISON",
                                      "actionDelay": 5,
                                      "actionDelayUnit": "DAY",
                                      "payload": {"bisonCampaignId": 418}}}
        out = push.drop_bison_handoff(node)
        self.assertEqual(out["conditionalNode"]["nodeType"], "END")
        self.assertEqual(out["unconditionalNode"]["nodeType"], "END")
        self.assertNotIn("bisonCampaignId", graph_of(out))


class TheRealGraphIsWritable(unittest.TestCase):

    def setUp(self):
        if not os.path.exists(STANDARD):
            self.skipTest("no stored standard graph on this machine")

    def test_the_standard_carries_no_foreign_campaign_id(self):
        text = graph_of(push.standard_graph())
        self.assertNotIn("SEND_LEAD_TO_BISON", text)
        self.assertNotIn("bisonCampaignId", text)

    def test_the_standard_validates_for_write(self):
        nodes, words = heyreach.validate_sequence_for_write(
            push.standard_graph())
        self.assertGreater(nodes, 10)
        self.assertGreaterEqual(words, 6)

    def test_the_stored_file_still_holds_the_graph_as_read(self):
        """The provider's own words stay on disk untouched; the dropping
        happens on the way out, so the record of what the client runs is not
        edited by a decision about what we run."""
        with open(STANDARD, encoding="utf-8") as handle:
            stored = json.dumps(json.load(handle)["graph"])
        self.assertIn("SEND_LEAD_TO_BISON", stored)


if __name__ == "__main__":
    unittest.main()
