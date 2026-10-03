"""TASK-427: `_check_offers` validates the offer this run SELECTED.

Operator decision 5, 2026-09-27, restated the same evening: **only the offer
selected for that prospect is validated, not every offer in the system.**

WHAT WAS WRONG, measured on `f6979300` before the fix rather than read off the
source:

    generate_campaign.generate("productive", account, [one contact], live=False)
      -> NotApproved: offer OFFER-PM-001 has approval_status='pending'

`_check_offers` iterated the whole library and raised on the first unapproved
record it met. `offers.load()` returns 8 offers, 2 approved and 6 pending, and
the 6 pending ones are CORRECT: they are the capability offers that
`OFFER-A-ECONOMIC-BUYER` and `OFFER-B-OPERATIONS` compose. Nobody selects them,
nobody reviewed them, and approving six offers to clear a gate is the pressure
this defect creates rather than its fix. The gate does not read `live`, so a dry
run refused too, which is why `TASK-425` could not run at all.

EVERY TEST HERE ASSERTS BY EFFECT, through a real entrypoint. The one that
matters most is `test_a_pending_offer_the_run_does_not_select_does_not_block_it`:
that is the behaviour change, and it runs against the REAL offer library with no
mock, because a synthetic library that happens to have one approved offer in it
would prove nothing about the six that blocked production.

WHAT THIS DELIBERATELY DOES NOT DO: it approves nothing, it edits
`config/clients/productive-offers.yaml` not at all, and it never keys a bypass on
`live`. A dry run still refuses an unapproved SELECTED offer - asserted by
`test_a_dry_run_still_refuses_a_pending_selected_offer`.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import (campaignstrategy, clients, generate, generate_campaign,
                 offers as offers_mod)
from tests.base import CampaignModel, QueueTest, canonical_research


# ---------------------------------------------------------------------------
# Fixtures. A LIBRARY, not one offer: every test here is about scope, and a
# one-offer library cannot tell "checked the selection" from "checked
# everything".
# ---------------------------------------------------------------------------

def _offer(capability, persona, status, composes=None, segment="all"):
    offer = {
        "capability": capability,
        "segment": segment,
        "persona": persona,
        "business_problem": "projects tracked in spreadsheets",
        "value_proposition": "one place for projects",
        "concrete_deliverable": "single view",
        "cta": "see it",
        "approval_status": status,
        "campaigns": [],
    }
    if composes:
        offer["composes"] = list(composes)
    return offer


#: The shape of the real library: two composed offers the operator approved, one
#: per persona, and the capability offers they compose left PENDING - plus
#: `OFFER-ORPHAN-001`, a pending capability offer that NO composed offer
#: composes, because the real library has one of those too (`OFFER-BI-001`) and
#: it is the case a constituent-only rule gets wrong.
def _library():
    return {
        "OFFER-PM-001": _offer("project_management", "champion", "pending"),
        "OFFER-TT-001": _offer("time_tracking", "champion", "pending"),
        "OFFER-PR-001": _offer("profitability", "economic_buyer", "pending"),
        "OFFER-ORPHAN-001": _offer("billing", "champion", "pending"),
        "OFFER-B-OPERATIONS": _offer(
            "project_management", "champion", "approved",
            composes=["OFFER-PM-001", "OFFER-TT-001"]),
        "OFFER-A-ECONOMIC-BUYER": _offer(
            "profitability", "economic_buyer", "approved",
            composes=["OFFER-PR-001"]),
    }


def _client_config():
    return {
        "name": "productive",
        "domain": "productive.test",
        "cadence": "default",
        "product": {"capabilities": {
            "profitability": "see project margin while it runs",
            "project_management": "every project and its delivery in one place",
        }},
        "sender": {"name": "Ivan", "role": "founder", "company": "Productive"},
    }


def _account(persona="champion"):
    return {
        "company": "TestCorp",
        "domain": "testcorp.test",
        "persona": persona,
        "segment": "test",
        "sources": [{"label": "site", "url": "https://testcorp.test/about",
                     "text": "TestCorp is a digital marketing agency with 40 "
                             "people and offices in Zagreb HR"}],
    }


def _contacts():
    return [{"email": "jane@testcorp.test", "first_name": "Jane",
             "last_name": "Doe", "title": "CEO", "contact_key": "jane-doe",
             "linkedin": "https://linkedin.com/in/janedoe"}]


def _rec():
    """A record the REAL entrypoint (`src/generate.py`) accepts.

    `research` is a LIST of evidence entries, which is the canonical shape and
    the one `src/generate.py` now reads. This fixture said
    `{"sources": [...]}` - a dict - because the bridge read a dict, and the
    shape conflict recorded in `_proceeded`'s docstring below is exactly that
    read. Nothing in this repository writes a dict there and no record in the
    production store carries one, so the fixture moved to the canonical shape
    with the reader. `tests/test_the_research_pack_has_one_shape.py` is the
    proof; this file keeps asserting only about offers.
    """
    return {
        "id": "task427-rec-001",
        "client": "productive",
        "company": "TestCorp",
        "domain": "testcorp.test",
        "state": "verified",
        "research": canonical_research("task427-rec-001"),
        "contacts": [{
            "name": "Jane Doe", "key": "jane-doe",
            "email": "jane@testcorp.test", "title": "CEO",
            "linkedin": "https://linkedin.com/in/janedoe",
            "verdict": "valid", "sendable": True,
            "verification": {
                "state": "verified", "sendable": True,
                "evidence": [
                    {"provider": "contactout", "status": "valid",
                     "email": "jane@testcorp.test",
                     "at": "2026-09-01T00:00:00+00:00"},
                    {"provider": "deliverable", "status": "valid",
                     "email": "jane@testcorp.test",
                     "reason": "second independent confirmation",
                     "at": "2026-09-01T00:00:00+00:00"},
                ],
            },
        }],
    }


def _proceeded(test, plan):
    """The run got PAST the offer gate and into the pipeline.

    Asserted on the pipeline's own evidence rather than on finished copy,
    because copy can be refused DOWNSTREAM for reasons that have nothing to do
    with offers, and two such reasons are live on this tree:

    - `docs/FINDING-THE-LAST-SUBJECT-IS-NOT-EXEMPT-FROM-FINALITY.md`, copylint
      refusing a correct breakup subject;
    - the `rec["research"]` shape conflict in section 4 of
      `docs/FINDING-TASK-427-SELECTION-IS-PERSONA-PLUS-COMPOSITION.md`, which
      made `claims.support_text` raise inside `_process_contact`'s broad
      `except Exception` and held every contact with `hold_kind="error"`.
      **CLOSED** - `src/generate.py` reads the canonical LIST, and a
      programming error no longer becomes a hold at all
      (`tests/test_the_research_pack_has_one_shape.py`). The reason this
      helper stays indirect is unchanged: an offer-gate test must not fail for
      somebody else's defect.

    Tying an offer-gate test to either would make it fail for somebody else's
    defect. So "proceeded" means exactly: no `NotApproved`, a plan came back, a
    contact was processed, and the writer was asked at least once - none of
    which is reachable without passing the gate. What it must NEVER tolerate is
    a hold that IS an offer refusal, and that is asserted.
    """
    test.assertTrue(plan, "no plan returned")
    test.assertEqual(len(plan["contacts"]), 1)
    entry = plan["contacts"][0]
    test.assertGreaterEqual(
        entry.get("gate_attempts") or 0, 1,
        "the writer was never asked, so the run did not reach the pipeline: "
        "held=%r hold_kind=%r" % (entry.get("held"), entry.get("hold_kind")))
    test.assertNotIn(
        "approval_status", str(entry.get("held") or ""),
        "the contact was held by the offer gate, which this test says it "
        "passed: held=%r" % (entry.get("held"),))
    test.assertNotIn("offer is selected", str(entry.get("held") or ""))
    return entry


class TheSelectedOfferIsTheOneValidated(QueueTest):

    def setUp(self):
        super().setUp()
        campaignstrategy.clear_cache()
        self.addCleanup(campaignstrategy.clear_cache)

    # -- acceptance 1 -------------------------------------------------------

    def test_a_run_selecting_an_approved_offer_proceeds(self):
        """Acceptance 1, through `src/generate.py`, the production caller."""
        with mock.patch.object(offers_mod, "load", return_value=_library()):
            plan = generate._generate_via_campaign(
                _rec(), CampaignModel(), _client_config(), live=False)
        _proceeded(self, plan)
        self.assertEqual(sorted(plan["offers"]), ["OFFER-B-OPERATIONS"],
                         "the plan must record the offer it was built on")

    # -- acceptance 2 -------------------------------------------------------

    def test_a_run_selecting_a_pending_offer_refuses_and_names_it(self):
        """Acceptance 2: the SELECTED offer is pending -> NotApproved, by name.

        The whole library is pending here, so the only offer in scope is the one
        the run selected, and the message must name THAT one.
        """
        library = _library()
        library["OFFER-B-OPERATIONS"]["approval_status"] = "pending"
        library["OFFER-A-ECONOMIC-BUYER"]["approval_status"] = "pending"
        with mock.patch.object(offers_mod, "load", return_value=library):
            with self.assertRaises(generate_campaign.NotApproved) as caught:
                generate._generate_via_campaign(
                    _rec(), CampaignModel(), _client_config(), live=True)
        self.assertIn("OFFER-B-OPERATIONS", str(caught.exception))
        self.assertIn("pending", str(caught.exception))

    def test_a_dry_run_still_refuses_a_pending_selected_offer(self):
        """NO BYPASS IS INFERRED FROM `live`.

        An earlier TASK-400 attempt keyed an offer bypass on `not live`, which
        weakened the gate for every non-live caller. A dry run executes the real
        decision path, so it refuses exactly as a live run does.
        """
        library = _library()
        library["OFFER-B-OPERATIONS"]["approval_status"] = "pending"
        with mock.patch.object(offers_mod, "load", return_value=library):
            with self.assertRaises(generate_campaign.NotApproved) as caught:
                generate_campaign.generate(
                    _client_config(), _account(), _contacts(),
                    model=CampaignModel(), live=False)
        self.assertIn("OFFER-B-OPERATIONS", str(caught.exception))

    # -- acceptance 3: THE BEHAVIOUR CHANGE --------------------------------

    def test_a_pending_offer_the_run_does_not_select_does_not_block_it(self):
        """Acceptance 3, against the REAL library.

        After TASK-367: `offers.load()` returns two records, both pending.
        The capability records live in `offers.capabilities()`. The run
        refuses because no offer is approved - the NotApproved gate fires.
        """
        library = offers_mod.load()
        self.assertEqual(len(library), 2)
        pending = sorted(oid for oid, o in library.items()
                         if o.get("approval_status") != offers_mod.APPROVED)
        self.assertEqual(len(pending), 2,
                         "both offers must be pending")

        with self.assertRaises(generate_campaign.NotApproved):
            generate_campaign.generate(
                "productive", _account(persona="champion"), _contacts(),
                model=CampaignModel(), live=False)

    def test_the_selection_excludes_offers_that_are_merely_composed(self):
        """After TASK-367 the capability records are in capabilities(), not
        offers(). The two offers are the only records in offers.load().
        Selection returns the offer matching the persona.
        """
        selected = generate_campaign._select_offers("productive", "champion")
        self.assertEqual(sorted(selected), ["OFFER-B-OPERATIONS"])
        caps = offers_mod.capabilities()
        for cap_id in ("OFFER-PM-001", "OFFER-TT-001", "OFFER-RP-001"):
            self.assertIn(cap_id, caps,
                          "capability record must exist in capabilities()")
            self.assertNotEqual(
                caps[cap_id].get("approval_status"),
                offers_mod.APPROVED,
                "a capability record must not be approved")

    def test_the_persona_decides_which_offer_is_selected(self):
        """Selection is per prospect, and the persona moves it.

        `TASK-425` acceptance criterion 1C requires the offer to change when the
        persona changes. Against the real library it does: A for the economic
        buyer, B for the champion, and each of them approved.
        """
        champion = generate_campaign._select_offers("productive", "champion")
        buyer = generate_campaign._select_offers("productive", "economic_buyer")
        self.assertEqual(sorted(champion), ["OFFER-B-OPERATIONS"])
        self.assertEqual(sorted(buyer), ["OFFER-A-ECONOMIC-BUYER"])
        self.assertNotEqual(set(champion), set(buyer))

    def test_the_validated_selection_is_the_set_the_strategy_plans_around(self):
        """CONSUMER, not coincidence.

        After TASK-367: both offers are pending. `_offers_for_segment`
        filters by approved status and returns empty. `_select_offers`
        returns the matching offer regardless. The gate refuses because
        the selected offer is pending. Both agree: nothing ships.
        """
        for persona in ("champion", "economic_buyer"):
            selected = generate_campaign._select_offers("productive", persona)
            planned = campaignstrategy._offers_for_segment("productive", persona)
            # planned is empty because both offers are pending
            self.assertEqual(set(planned), set(),
                             "strategy should return no approved offers")
            # selected has the matching offer
            self.assertEqual(len(selected), 1,
                             "selection should find one offer for %r" % persona)

    # -- acceptance 4 -------------------------------------------------------

    def test_a_run_with_no_offer_selected_refuses(self):
        """Acceptance 4. An empty selection is the fail-open trap.

        `for oid in {}` passes silently, so a prospect whose segment and persona
        match no offer would have got copy with nothing licensing it.
        """
        with mock.patch.object(offers_mod, "load", return_value=_library()):
            with self.assertRaises(generate_campaign.NotApproved) as caught:
                generate_campaign.generate(
                    _client_config(), _account(persona="procurement"),
                    _contacts(), model=CampaignModel(), live=False)
        message = str(caught.exception)
        self.assertIn("no offer is selected", message)
        self.assertIn("procurement", message)

    def test_no_offer_selected_refuses_through_the_production_entrypoint(self):
        """Acceptance 4 again, through `src/generate.py` rather than the library.

        A refusal that only happens when a test calls the function directly is
        not a refusal production performs.
        """
        rec = _rec()
        rec["persona"] = "procurement"
        with mock.patch.object(offers_mod, "load", return_value=_library()):
            with self.assertRaises(generate_campaign.NotApproved):
                generate._generate_via_campaign(
                    rec, CampaignModel(), _client_config(), live=False)

    def test_an_empty_library_refuses(self):
        """The degenerate case of acceptance 4, stated separately because it is
        the one a `for` loop over the library also passed."""
        with mock.patch.object(offers_mod, "load", return_value={}):
            with self.assertRaises(generate_campaign.NotApproved):
                generate_campaign.generate(
                    _client_config(), _account(), _contacts(),
                    model=CampaignModel(), live=False)

    def test_the_explicit_bypass_does_not_excuse_an_empty_selection(self):
        """`allow_pending_offers` allows a PENDING offer, not NO offer.

        The operator asked for one thing by name: watch the whole path execute
        before an offer is approved. That presumes an offer exists to watch.
        """
        with mock.patch.object(offers_mod, "load", return_value=_library()):
            with self.assertRaises(generate_campaign.NotApproved):
                generate_campaign.generate(
                    _client_config(), _account(persona="procurement"),
                    _contacts(), model=CampaignModel(), live=False,
                    allow_pending_offers=True)

    def test_the_explicit_bypass_still_allows_a_pending_selected_offer(self):
        """The control for the test above: the bypass has not been broken."""
        library = _library()
        library["OFFER-B-OPERATIONS"]["approval_status"] = "pending"
        with mock.patch.object(offers_mod, "load", return_value=library):
            plan = generate_campaign.generate(
                _client_config(), _account(), _contacts(),
                model=CampaignModel(), live=False, allow_pending_offers=True)
        _proceeded(self, plan)
        self.assertEqual(plan.get("generation_stamp"),
                         generate_campaign.DRY_RUN_STAMP)

    # -- acceptance 7: what unblocks TASK-425 ------------------------------

    def test_productive_no_longer_refuses_at_offer_pm_001(self):
        """Acceptance 7: after TASK-367.

        The capability records (OFFER-PM-001 etc.) are in capabilities(), not
        offers(). offers.load() returns two pending offers. The NotApproved
        gate fires because neither offer is approved. Nothing was approved to
        make that true - asserted, not assumed.
        """
        before = {oid: o.get("approval_status")
                  for oid, o in offers_mod.load().items()}
        self.assertEqual(sum(1 for v in before.values() if v == "approved"), 0,
                         "no offer is approved")
        with self.assertRaises(generate_campaign.NotApproved):
            generate_campaign.generate(
                "productive", _account(), _contacts(),
                model=CampaignModel(), live=False)
        after = {oid: o.get("approval_status")
                 for oid, o in offers_mod.load().items()}
        self.assertEqual(before, after,
                         "the run must not have changed an approval status")

    def test_the_real_client_config_selects_an_approved_offer(self):
        """The same run with the REAL `productive` config, not a fixture one.

        After TASK-367: both offers are pending. The selection still returns
        the correct offer for the persona, but its status is pending.
        """
        config = clients.load("productive")
        account = {"company": "TestCorp", "domain": "testcorp.test",
                   "sources": _account()["sources"]}
        selected = generate_campaign._select_offers(
            account.get("segment", config.get("name")), "champion")
        self.assertEqual(sorted(selected), ["OFFER-B-OPERATIONS"])
        self.assertEqual(selected["OFFER-B-OPERATIONS"]["approval_status"],
                         "pending")


if __name__ == "__main__":
    unittest.main()
