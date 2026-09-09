"""A LinkedIn canary may not be called LinkedIn-only on the absence of a string.

THE RULE. A LinkedIn canary is not safe if the selected HeyReach campaign can
hand the lead into EmailBison. `AddLeadsToCampaignV2` looks like a LinkedIn
action; a sequence containing `SEND_LEAD_TO_BISON` hands the person onward to
an EmailBison campaign this system did not write and did not choose. Sixteen of
this workspace's campaigns do that deliberately.

WHY `sequence_hazards` COULD NOT ANSWER IT. It searches `json.dumps(sequence)`
for one literal string, so:

  - the absence of `SEND_LEAD_TO_BISON` is the absence of ONE named node type,
    not the absence of email egress. Four node types are named anywhere in this
    repository; HeyReach's vocabulary is not known here.
  - it never walks the graph, so it cannot tell a complete graph from one whose
    branches it never saw.
  - its verdict was discarded by its only caller.

So `linkedin_only` is an ALLOWLIST over the node types actually reached, and it
fails closed on anything it cannot classify. "We cannot prove this is
LinkedIn-only" and "this sends email" are different facts, both answered False,
distinguished by the reason - and the reason is what a person reads before
authorising a canary.
"""
import unittest

from src import push, store
from src.providers import heyreach
from tests.test_push import PushTest


def node(kind, **fields):
    return dict(nodeType=kind, **fields)


PURE = node("CHECK_IS_CONNECTION",
            conditionalNode=node("MESSAGE", payload={"messages": ["hi"]}),
            unconditionalNode=node("CONNECTION_REQUEST",
                                   payload={"messages": ["hey"]}))

BISON = node("CHECK_IS_CONNECTION",
             conditionalNode=node("MESSAGE", payload={"messages": ["hi"]}),
             unconditionalNode=node("SEND_LEAD_TO_BISON",
                                    payload={"bisonCampaignId": 417}))


class APureLinkedInGraphIsCleared(unittest.TestCase):
    def test_it_is_provably_linkedin_only(self):
        proven, why = heyreach.linkedin_only(PURE)
        self.assertTrue(proven)
        self.assertIn("LinkedIn-only", why)

    def test_the_reason_names_the_nodes_it_cleared(self):
        _, why = heyreach.linkedin_only(PURE)
        for kind in ("CHECK_IS_CONNECTION", "CONNECTION_REQUEST", "MESSAGE"):
            self.assertIn(kind, why)

    def test_a_single_message_node_is_enough(self):
        proven, _ = heyreach.linkedin_only(
            node("MESSAGE", payload={"messages": ["hi"]}))
        self.assertTrue(proven)


class AHandoffIsRefusedAndNamed(unittest.TestCase):
    def test_a_bison_node_is_not_linkedin_only(self):
        proven, why = heyreach.linkedin_only(BISON)
        self.assertFalse(proven)
        self.assertIn("SEND_LEAD_TO_BISON", why)

    def test_the_reason_says_what_the_consequence_is(self):
        _, why = heyreach.linkedin_only(BISON)
        self.assertIn("email this system did not write", why)

    def test_a_handoff_buried_deep_is_still_found(self):
        """The string search would find it too; the walk must not lose it."""
        deep = node("CHECK_IS_CONNECTION",
                    conditionalNode=node(
                        "MESSAGE",
                        unconditionalNode=node(
                            "MESSAGE",
                            conditionalNode=node("SEND_LEAD_TO_BISON"))))
        self.assertFalse(heyreach.linkedin_only(deep)[0])

    def test_a_node_list_is_walked_too(self):
        listed = node("CHECK_IS_CONNECTION",
                      children=[node("MESSAGE"), node("SEND_LEAD_TO_BISON")])
        self.assertFalse(heyreach.linkedin_only(listed)[0])


class ItFailsClosedOnAnythingItCannotClassify(unittest.TestCase):
    """The part a denylist cannot do."""

    def test_an_unrecognised_node_type_is_not_cleared(self):
        proven, why = heyreach.linkedin_only(
            node("CHECK_IS_CONNECTION",
                 conditionalNode=node("SOME_FUTURE_ACTION")))
        self.assertFalse(proven)
        self.assertIn("SOME_FUTURE_ACTION", why)

    def test_an_unknown_node_is_not_called_email(self):
        """Honest about which fact it is. Unprovable is not the same as unsafe."""
        _, why = heyreach.linkedin_only(
            node("CHECK_IS_CONNECTION",
                 conditionalNode=node("SOME_FUTURE_ACTION")))
        self.assertIn("Not proof of email", why)
        self.assertNotIn("hands the lead off", why)

    def test_a_branch_holding_an_id_rather_than_a_node_is_refused(self):
        """A graph we cannot finish walking is a graph we cannot clear."""
        proven, why = heyreach.linkedin_only(
            node("CHECK_IS_CONNECTION", conditionalNode=12345))
        self.assertFalse(proven)
        self.assertIn("could not be walked", why)

    def test_an_unfetched_sequence_is_refused(self):
        for empty in (None, {}, [], ""):
            with self.subTest(value=empty):
                self.assertFalse(heyreach.linkedin_only(empty)[0])

    def test_an_absent_sequence_says_so_rather_than_looking_clean(self):
        _, why = heyreach.linkedin_only(None)
        self.assertIn("proves nothing", why)

    def test_a_typeless_dict_gets_the_precise_reason(self):
        _, why = heyreach.linkedin_only({})
        self.assertIn("nodeType", why)


class TheAllowlistIsAnAllowlist(unittest.TestCase):
    def test_every_cleared_type_is_declared(self):
        _, types, _ = heyreach.walk_sequence(PURE)
        for kind in types:
            self.assertIn(kind, heyreach.LINKEDIN_ONLY_NODES)

    def test_no_egress_node_is_on_the_allowlist(self):
        for kind in heyreach.LINKEDIN_ONLY_NODES:
            self.assertNotIn("BISON", kind.upper())
            self.assertNotIn("EMAIL", kind.upper())

    def test_the_walk_reports_every_node_it_saw(self):
        nodes, types, truncated = heyreach.walk_sequence(PURE)
        self.assertEqual(len(nodes), 3)
        self.assertFalse(truncated)

    def test_a_cycle_does_not_hang_the_walk(self):
        a = node("MESSAGE")
        a["conditionalNode"] = a
        nodes, _, _ = heyreach.walk_sequence(a)
        self.assertEqual(len(nodes), 1)


class TheVerdictReachesTheCaller(unittest.TestCase):
    """It was computed, returned, and discarded at `push.py:301`.

    That is the defect class this repository keeps finding, and on this
    particular value it is the one fact that decides whether a canary is
    LinkedIn-only.
    """

    def test_a_handoff_appears_in_the_hazards(self):
        hazards = heyreach.refuse_unsupported_sequence(BISON, rows=None)
        self.assertIn(heyreach.NOT_LINKEDIN_ONLY,
                      [what for what, _ in hazards])

    def test_a_clean_sequence_reports_no_hazard_at_all(self):
        """A hazard list holds problems. A confirmation in it would make
        "no hazards" impossible and break every caller reading empty as clean.
        """
        self.assertEqual(heyreach.refuse_unsupported_sequence(PURE, rows=None),
                         [])

    def test_the_bison_handoff_is_still_reported_separately(self):
        hazards = heyreach.refuse_unsupported_sequence(BISON, rows=None)
        self.assertIn(heyreach.BISON_HANDOFF, [what for what, _ in hazards])


class ThePayloadCarriesTheVerdict(PushTest):
    """Against the real estate and the real eligibility path.

    `push.payloads` computed this, returned it and dropped it. A reader of the
    payload could not tell a campaign proven LinkedIn-only from one whose
    sequence had never been fetched, which is exactly the distinction a canary
    turns on.
    """

    def linkedin_items(self):
        items, _ = push.collect(store.load(), day=21)
        found = [i for i in items if i["channel"] == "linkedin"]
        self.assertTrue(found, "fixture supplies no LinkedIn item to gate")
        return found

    def test_a_clean_sequence_is_reported_as_proven(self):
        built = push.payloads(self.linkedin_items(), heyreach_campaign_id="1",
                              heyreach_sequence=PURE)
        verdict = built["heyreach"]["sequence"]
        self.assertTrue(verdict["linkedin_only"])
        self.assertIn("LinkedIn-only", verdict["why"])

    def test_a_handoff_is_reported_as_not_proven(self):
        built = push.payloads(self.linkedin_items(), heyreach_campaign_id="1",
                              heyreach_sequence=BISON)
        verdict = built["heyreach"]["sequence"]
        self.assertFalse(verdict["linkedin_only"])
        self.assertIn("SEND_LEAD_TO_BISON", verdict["why"])

    def test_the_handoff_hazard_travels_with_it(self):
        built = push.payloads(self.linkedin_items(), heyreach_campaign_id="1",
                              heyreach_sequence=BISON)
        what = [h["what"] for h in built["heyreach"]["sequence"]["hazards"]]
        self.assertIn(heyreach.BISON_HANDOFF, what)

    def test_no_sequence_is_not_the_same_as_a_clean_one(self):
        """The distinction that makes the field worth carrying."""
        built = push.payloads(self.linkedin_items(),
                              heyreach_campaign_id="565765")
        verdict = built["heyreach"]["sequence"]
        self.assertFalse(verdict["linkedin_only"])
        self.assertIn("no sequence was supplied", verdict["why"])


if __name__ == "__main__":
    unittest.main()
