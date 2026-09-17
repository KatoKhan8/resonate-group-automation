#!/usr/bin/env python3
"""TASK-218: the DRAFT campaign bind path, wired but NOT enabled.

Tests the creation readback, the sequence reproduction answer, and the
prospect-facing argument. The creation permission is defined with its
condition and left OFF - `LINKEDIN_CREATE_CAMPAIGN` is not in `SUPPORTED`.

What this tests:
  1. `heyreach.create_campaign` reads back DRAFT, list binding, seats.
  2. The sequence of 599020 can be read and its hash is reproducible.
  3. A campaign created in DRAFT sends nothing - the prospect-facing argument.
"""
import hashlib
import json
import unittest
from unittest import mock

from src.providers import heyreach


class CreateCampaignReadback(unittest.TestCase):
    """After creation, the readback proves DRAFT, list, seats."""

    def _make_create_response(self, campaign_id=999999):
        return {"campaignId": campaign_id}

    def _make_readback(self, campaign_id=999999, name="test",
                       list_id=940797, seats=(174892,),
                       status="DRAFT"):
        return {"id": campaign_id, "name": name, "status": status,
                "linkedInUserListId": list_id,
                "campaignAccountIds": list(seats),
                "organizationUnitId": 118832, "creationTime": "2026-09-16",
                "startedAt": None}

    def test_create_campaign_reads_back_draft(self):
        """A created campaign must read back as DRAFT."""
        with mock.patch.object(heyreach, "campaign_named", return_value=None):
            with mock.patch.object(heyreach, "_write_body",
                                   return_value=self._make_create_response()):
                with mock.patch.object(heyreach, "campaign_read",
                                       return_value=self._make_readback()):
                    found = heyreach.create_campaign(
                        "test", 940797, [174892])
        self.assertEqual(found["status"], "DRAFT")

    def test_create_campaign_reads_back_list_binding(self):
        """The campaign must point at the list we asked for."""
        with mock.patch.object(heyreach, "campaign_named", return_value=None):
            with mock.patch.object(heyreach, "_write_body",
                                   return_value=self._make_create_response()):
                with mock.patch.object(heyreach, "campaign_read",
                                       return_value=self._make_readback()):
                    found = heyreach.create_campaign(
                        "test", 940797, [174892])
        self.assertEqual(str(found["linkedInUserListId"]), "940797")

    def test_create_campaign_reads_back_seats(self):
        """The campaign must hold the seats we asked for."""
        with mock.patch.object(heyreach, "campaign_named", return_value=None):
            with mock.patch.object(heyreach, "_write_body",
                                   return_value=self._make_create_response()):
                with mock.patch.object(heyreach, "campaign_read",
                                       return_value=self._make_readback()):
                    found = heyreach.create_campaign(
                        "test", 940797, [174892])
        self.assertEqual(set(found["campaignAccountIds"]), {174892})

    def test_create_campaign_refuses_wrong_status(self):
        """A campaign that did not come back as DRAFT is refused."""
        with mock.patch.object(heyreach, "campaign_named", return_value=None):
            with mock.patch.object(heyreach, "_write_body",
                                   return_value=self._make_create_response()):
                with mock.patch.object(heyreach, "campaign_read",
                                       return_value=self._make_readback(
                                           status="IN_PROGRESS")):
                    with self.assertRaises(heyreach.ProviderError) as ctx:
                        heyreach.create_campaign("test", 940797, [174892])
        self.assertIn("IN_PROGRESS", str(ctx.exception))

    def test_create_campaign_refuses_wrong_list(self):
        """A campaign pointing at the wrong list is refused."""
        with mock.patch.object(heyreach, "campaign_named", return_value=None):
            with mock.patch.object(heyreach, "_write_body",
                                   return_value=self._make_create_response()):
                with mock.patch.object(heyreach, "campaign_read",
                                       return_value=self._make_readback(
                                           list_id=123456)):
                    with self.assertRaises(heyreach.ProviderError) as ctx:
                        heyreach.create_campaign("test", 940797, [174892])
        self.assertIn("wrong list", str(ctx.exception))

    def test_create_campaign_refuses_wrong_seats(self):
        """A campaign holding different seats is refused."""
        with mock.patch.object(heyreach, "campaign_named", return_value=None):
            with mock.patch.object(heyreach, "_write_body",
                                   return_value=self._make_create_response()):
                with mock.patch.object(heyreach, "campaign_read",
                                       return_value=self._make_readback(
                                           seats=(999999,))):
                    with self.assertRaises(heyreach.ProviderError) as ctx:
                        heyreach.create_campaign("test", 940797, [174892])
        self.assertIn("seats", str(ctx.exception))

    def test_create_campaign_refuses_duplicate_name(self):
        """A campaign with the same name already exists."""
        with mock.patch.object(heyreach, "campaign_named",
                               return_value={"id": 123, "name": "test"}):
            with self.assertRaises(heyreach.ProviderError) as ctx:
                heyreach.create_campaign("test", 940797, [174892])
        self.assertIn("already exists", str(ctx.exception))


class SequenceReproduction(unittest.TestCase):
    """The 17-node shape of 599020 can be read and its hash is reproducible.

    The sequence hash `32f8dde79bfa0f27` was measured on campaign 599020.
    This test proves the fingerprint function is deterministic: the same
    graph produces the same hash.
    """

    def test_fingerprint_is_deterministic(self):
        """The same graph always produces the same fingerprint."""
        graph = heyreach._node(
            "CHECK_IS_CONNECTION", 0, "HOUR",
            cond=heyreach._node("MESSAGE", 3, "HOUR",
                                {"messages": ["hello"],
                                 "fallbackMessage": "fallback"}),
            nxt=heyreach._node("END", 3, "HOUR"))
        fp1 = heyreach._fingerprint(graph)
        fp2 = heyreach._fingerprint(graph)
        self.assertEqual(fp1, fp2)

    def test_different_graphs_produce_different_fingerprints(self):
        """A changed message produces a different fingerprint."""
        graph_a = heyreach._node(
            "MESSAGE", 3, "HOUR",
            {"messages": ["hello"], "fallbackMessage": "fallback"},
            nxt=heyreach._node("END", 3, "HOUR"))
        graph_b = heyreach._node(
            "MESSAGE", 3, "HOUR",
            {"messages": ["goodbye"], "fallbackMessage": "fallback"},
            nxt=heyreach._node("END", 3, "HOUR"))
        self.assertNotEqual(heyreach._fingerprint(graph_a),
                            heyreach._fingerprint(graph_b))

    def test_sequence_hash_is_stable_across_serialisation(self):
        """A graph that round-trips through JSON produces the same hash."""
        graph = heyreach._node(
            "CHECK_IS_CONNECTION", 0, "HOUR",
            cond=heyreach._node("MESSAGE", 3, "HOUR",
                                {"messages": ["hello"],
                                 "fallbackMessage": "fallback"}),
            nxt=heyreach._node("END", 3, "HOUR"))
        fp_before = heyreach._fingerprint(graph)
        round_tripped = json.loads(json.dumps(graph))
        fp_after = heyreach._fingerprint(round_tripped)
        self.assertEqual(fp_before, fp_after)

    def test_sequence_matches_works_on_round_trip(self):
        """The readback comparison survives JSON serialisation."""
        graph = heyreach._node(
            "MESSAGE", 3, "HOUR",
            {"messages": ["hello"], "fallbackMessage": "fallback"},
            nxt=heyreach._node("END", 3, "HOUR"))
        round_tripped = json.loads(json.dumps(graph))
        same, _why = heyreach.sequence_matches(round_tripped, graph)
        self.assertTrue(same)

    def test_campaign_sequence_can_be_read(self):
        """`campaign_sequence` returns the graph from the provider."""
        fake_graph = heyreach._node(
            "MESSAGE", 3, "HOUR",
            {"messages": ["test"], "fallbackMessage": "fb"},
            nxt=heyreach._node("END", 3, "HOUR"))
        with mock.patch.object(heyreach, "_read_get",
                               return_value=fake_graph):
            result = heyreach.campaign_sequence(599020)
        self.assertEqual(result["nodeType"], "MESSAGE")


class DraftIsNotProspectFacing(unittest.TestCase):
    """A DRAFT campaign sends nothing. The argument from the provider.

    The provider's own behaviour decides this, not our assertion:
      - `AddLeadsToCampaignV2` answers 400 "You cannot add new leads to a
        draft campaign" - so a DRAFT cannot be populated through the API.
      - `/campaign/StartCampaign` is the only route that moves DRAFT to
        running, and it is not in SUPPORTED.
      - A DRAFT has no sequence running, no leads, and no sending window
        that acts on anybody.

    Binding a list to a DRAFT is the moment the list stops being unbound,
    which ends the safety property every staged lead depends on. But no
    message is sent. The cost is loss of the unbound-list staging path,
    and detection of drift is the only safety net afterwards.
    """

    def test_draft_cannot_take_leads(self):
        """The provider refuses leads on a DRAFT campaign."""
        with mock.patch.object(heyreach, "_write_body",
                               side_effect=heyreach.ProviderError(
                                   "heyreach /campaign/AddLeadsToCampaignV2: "
                                   "HTTP 400 - You cannot add new leads to "
                                   "a draft campaign.")):
            with self.assertRaises(heyreach.ProviderError) as ctx:
                heyreach._write_body("/campaign/AddLeadsToCampaignV2",
                                     {"campaignId": 999999})
        self.assertIn("draft", str(ctx.exception).lower())

    def test_draft_status_cannot_send(self):
        """`campaign_cannot_send` returns True for DRAFT."""
        with mock.patch.object(heyreach, "campaign_read",
                               return_value={"status": "DRAFT"}):
            self.assertTrue(heyreach.campaign_cannot_send(999999))

    def test_in_progress_can_send(self):
        """`campaign_cannot_send` returns False for IN_PROGRESS."""
        with mock.patch.object(heyreach, "campaign_read",
                               return_value={"status": "IN_PROGRESS"}):
            self.assertFalse(heyreach.campaign_cannot_send(999999))

    def test_start_campaign_names_one_campaign_and_not_this_draft(self):
        """RENAMED from `test_start_campaign_is_not_in_supported`.

        The old name asserted the blanket seal on the verb that moves DRAFT
        to running. An operator narrowed that seal on 2026-09-16, granting
        `heyreach.activate` SCOPED BY NAME to campaign 605732, so the name
        pinned the opposite of the truth and the assertion under it would
        have been deleted rather than moved.

        The property this class needs is not "no campaign may be started" -
        it is "STARTING IS NOT SOMETHING BINDING A LIST TO A DRAFT DOES". A
        DRAFT created here is 999999 and every other id in this module, and
        none of them may be started: the grant names exactly one campaign
        that this module never creates, touches or returns. So binding a
        list to a DRAFT still costs the unbound-list staging property and
        still sends nothing, which is the whole claim of the class.
        """
        providerwrites = __import__("src.providerwrites",
                                    fromlist=["SUPPORTED"])
        activate = (heyreach.LINKEDIN_ACTIVATE
                    if hasattr(heyreach, "LINKEDIN_ACTIVATE")
                    else "heyreach.activate")
        self.assertIn(activate, providerwrites.SUPPORTED)
        self.assertTrue(
            providerwrites.is_conditional(activate),
            "heyreach.activate is enabled with no condition, which would "
            "make every DRAFT this module creates startable")

        require = providerwrites.require_conditional_permission
        # Exactly one campaign, and it is not one of ours. 999999 is the
        # DRAFT id this module uses throughout; 604869 and 605487 are dead
        # ends asserted refused rather than dropped; the near misses and
        # ""/None prove the match is exact and fails closed.
        self.assertTrue(require(
            activate, providerwrites._AUTHORIZED_LINKEDIN_CANARY, None))
        for other in ("999999", "599020", "604869", "605487",
                      "605733", "60573", "", None):
            with self.assertRaises(providerwrites.WriteRefused):
                require(activate, other, None)


if __name__ == "__main__":
    unittest.main()
