"""One campaign intent, at most one provider campaign. Attacked, not assumed.

THE TWO INVARIANTS UNDER TEST

    one logical campaign intent  -> at most one ACTIVE provider campaign
    one logical prospect action  -> at most one provider action

The second one has a durable mechanism: `actionledger` reserves
`rec:contact:step:channel` before the write and refuses an open, unresolved or
sent key. The first one has NOTHING. There is no create route in this build, so
nothing here is broken today in production terms - which is exactly why it is
worth writing the tests now, while the cost of being wrong is a diff rather
than a client's inbox.

Everything below runs against a FAKE provider held in memory. No route in
`providerwrites.SUPPORTED` is enabled except inside one test, which restores it
in `addCleanup`, and the fake transport is the only thing it can reach.

WHAT IS ASSERTED, AND WHAT IS MERELY DOCUMENTED

Tests without a marker assert what the code does TODAY. Tests marked
`@unittest.expectedFailure` describe behaviour this build does NOT have; they
are here so the design is executable rather than a paragraph, and so that the
day somebody implements it, the test turns green and tells them. A green run of
this module therefore means "today's behaviour is as described", NOT "campaign
creation is exactly-once".
"""
import unittest

from src import (actionledger, campaigns, configdiff, eligibility, mapping,
                 orchestrator, providerwrites, push, store)
from tests.base import ProviderTest
from tests.campaignbase import CLIENT, CampaignTest


# --------------------------------------------------------------- the fake

class FakeProvider:
    """An outreach provider with the three habits that break idempotency:

      * it assigns the id, so the id only exists in the response;
      * it accepts a duplicate create without complaint;
      * it fills in its own defaults where a field was not set.

    `lose_response` models the only failure that matters: the provider ACTED
    and the caller never learned what it did.
    """

    PLACEHOLDER_NOTE = "Hey, would love to connect!"

    def __init__(self, lose_response=False, reject=(), duplicate=()):
        self.campaigns = {}
        self.next_id = 900
        self.creates = 0
        self.lose_response = lose_response
        self.reject = set(reject)
        self.duplicate = set(duplicate)

    # -- writes ----------------------------------------------------------
    def create_campaign(self, payload):
        self.creates += 1
        self.next_id += 1
        cid = str(self.next_id)
        self.campaigns[cid] = {
            "id": cid,
            "name": payload.get("name"),
            "status": "draft",
            "leads": [],
            "senders": [],
            # The provider's own default copy, exactly as a vendor UI
            # pre-fills it. Nobody asked for this sentence.
            "note": payload.get("note") or self.PLACEHOLDER_NOTE,
            "delays": payload.get("delays") or {"step2": 3},
        }
        if self.lose_response:
            raise TimeoutError("read timed out after the provider acted")
        return dict(self.campaigns[cid])

    def add_leads(self, cid, leads):
        """Partial acceptance, the normal case at any real batch size."""
        accepted, refused = [], []
        for lead in leads:
            address = lead.get("email") or lead.get("linkedin_url")
            if address in self.reject:
                refused.append({"lead": address, "why": "invalid"})
                continue
            self.campaigns[cid]["leads"].append(address)
            if address in self.duplicate:
                self.campaigns[cid]["leads"].append(address)
            accepted.append(address)
        return {"accepted": len(accepted), "refused": refused}

    def rename(self, cid, name):
        self.campaigns[cid]["name"] = name

    # -- reads -----------------------------------------------------------
    def by_id(self, cid):
        return dict(self.campaigns.get(str(cid)) or {}) or None

    def listing(self):
        return [dict(c) for c in self.campaigns.values()]


# ------------------------------------------------- 1. intent identity

class AnIntentIsNotAName(ProviderTest):
    """`mapping` resolves "is this campaign ours" by matching the campaign
    NAME. A name is a label: an operator may change it, and two campaigns may
    share one."""

    def setUp(self):
        super().setUp()
        self.provider = FakeProvider()
        self.provider.create_campaign({"name": "demo Q3 revive"})
        self.mine = "901"

    def fetch(self):
        return self.provider.listing()

    def test_the_id_resolves_and_the_name_decides(self):
        found = mapping.check_bison(self.mine, expected_name=CLIENT,
                                    fetch=self.fetch)
        self.assertEqual(found["state"], mapping.OK)

    def test_renaming_in_the_vendor_ui_makes_our_own_campaign_foreign(self):
        """An operator renames the campaign. Nothing about the binding moved -
        the id is the same campaign with the same leads - and the mapping
        check now calls it a mismatch."""
        self.provider.rename(self.mine, "paused - do not use")
        found = mapping.check_bison(self.mine, expected_name=CLIENT,
                                    fetch=self.fetch)
        self.assertEqual(found["state"], mapping.MISMATCH)

    def test_a_duplicate_is_indistinguishable_from_the_original(self):
        """Two provider campaigns, same name, both created from one intent.
        Every question `mapping` can ask answers the same for both, so nothing
        here can say which one is the live campaign - or that there are two."""
        self.provider.create_campaign({"name": "demo Q3 revive"})
        first = mapping.check_bison("901", expected_name=CLIENT, fetch=self.fetch)
        second = mapping.check_bison("902", expected_name=CLIENT, fetch=self.fetch)
        self.assertEqual(first["state"], mapping.OK)
        self.assertEqual(second["state"], mapping.OK)
        self.assertEqual(len(self.provider.listing()), 2)

    @unittest.expectedFailure
    def test_a_provider_campaign_carries_the_intent_id(self):
        """DESIRED, NOT PRESENT. A provider campaign should be resolvable to
        the canonical intent that created it, without reading its name. There
        is no such lookup: `mapping` has campaign-id and name, and nothing
        else."""
        resolve = getattr(mapping, "intent_of")         # does not exist
        self.assertEqual(resolve(self.provider.by_id("901")), "camp-1")


# ------------------------------------- 2. the create has no durable half

class ACreateWritesNothingDurableFirst(ProviderTest):
    """`providerwrites.perform` reserves nothing for a non-prospect-facing
    operation, and creating a campaign is one. `key` is None, so no row is
    written before the call and nothing is settled after it."""

    def setUp(self):
        super().setUp()
        self.provider = FakeProvider()
        self._restore = providerwrites.SUPPORTED
        self.addCleanup(setattr, providerwrites, "SUPPORTED", self._restore)
        providerwrites.SUPPORTED = (providerwrites.EMAIL_CREATE_CAMPAIGN,)

    def create(self, name="camp-1"):
        return providerwrites.perform(
            providerwrites.EMAIL_CREATE_CAMPAIGN,
            payload={"name": name},
            transport=self.provider.create_campaign,
            readback=lambda: self.provider.by_id(self.provider.next_id),
            expected={"name": name})

    def test_the_sealed_build_refuses_a_create_at_all(self):
        """The baseline that makes every other finding a future one rather
        than a live one: with SUPPORTED restored, nothing can create."""
        providerwrites.SUPPORTED = self._restore
        with self.assertRaises(providerwrites.WriteUnsupported):
            self.create()
        self.assertEqual(self.provider.creates, 0)

    def test_one_intent_created_twice_makes_two_provider_campaigns(self):
        """THE DUPLICATE. Nothing in the call refuses the second attempt,
        because nothing recorded the first."""
        self.create()
        self.create()
        self.assertEqual(self.provider.creates, 2)
        self.assertEqual(len(self.provider.listing()), 2)

    def test_a_create_writes_no_ledger_key(self):
        result = self.create()
        self.assertIsNone(result["key"])
        self.assertEqual(actionledger.load(), [])

    def test_a_lost_response_and_no_attempt_leave_identical_local_state(self):
        """The question reconciliation exists to answer, asked of today's
        state: after a create whose response was lost, local state is byte
        identical to a create that never happened."""
        before = (actionledger.load(), campaigns.load())
        lossy = FakeProvider(lose_response=True)
        with self.assertRaises(providerwrites.WriteUnverified):
            providerwrites.perform(
                providerwrites.EMAIL_CREATE_CAMPAIGN,
                payload={"name": "camp-1"},
                transport=lossy.create_campaign,
                readback=lambda: lossy.by_id(lossy.next_id),
                expected={"name": "camp-1"})
        # The provider DID create it.
        self.assertEqual(len(lossy.listing()), 1)
        # And nothing local knows.
        self.assertEqual((actionledger.load(), campaigns.load()), before)

    @unittest.expectedFailure
    def test_a_second_create_for_a_bound_intent_is_refused(self):
        """DESIRED, NOT PRESENT. The campaign equivalent of
        `actionledger.reserve`: an intent whose binding is open or bound may
        not be created again."""
        reserve = getattr(campaigns, "reserve_binding")  # does not exist
        reserve("camp-1", channel="email", provider="bison")
        with self.assertRaises(Exception):
            reserve("camp-1", channel="email", provider="bison")


# --------------------------------------- 3. nothing reconciles an orphan

class AnOrphanIsNeverFound(CampaignTest):
    """A provider campaign whose id was never persisted is invisible. The one
    drift detector in the build, `configdiff`, is addressed BY that id."""

    def test_the_drift_detector_needs_the_binding_the_crash_lost(self):
        campaign, _recs = self.ready_campaign()
        campaign["heyreach_campaign_id"] = None
        with self.assertRaises(configdiff.DiffRefused):
            configdiff.approved_heyreach(campaign, recs=store.load(),
                                         config=self.config)

    def test_provider_default_copy_is_caught_only_for_a_bound_campaign(self):
        """The positive control. Given a binding, `diff` does catch the vendor
        placeholder - which is the defect it was written for. Without one the
        same drift is unreachable, as the test above shows."""
        provider = FakeProvider()
        provider.create_campaign({"name": "camp-1"})
        approved = {"campaign_id": "901", "note": "Hi there, worth a word?"}
        observed = {"campaign_id": "901",
                    "note": provider.by_id("901")["note"]}
        found = configdiff.diff(approved, observed, ("campaign_id", "note"))
        self.assertEqual(found["verdict"], configdiff.FAIL)
        self.assertEqual(found["fields"]["note"]["verdict"], configdiff.MISMATCH)

    def test_a_changed_delay_is_drift_like_any_other_field(self):
        approved = {"campaign_id": "901", "delays": {"step2": 2}}
        observed = {"campaign_id": "901", "delays": {"step2": 3}}
        found = configdiff.diff(approved, observed, ("campaign_id", "delays"))
        self.assertEqual(found["verdict"], configdiff.FAIL)

    @unittest.expectedFailure
    def test_reconciliation_separates_never_created_from_lost_response(self):
        """DESIRED, NOT PRESENT. Given the provider's campaign list and the
        canonical intents, something should classify each side: bound,
        orphaned (at the provider, bound to nothing), lost (attempted locally,
        not found), duplicated (two provider campaigns for one intent)."""
        reconcile = getattr(campaigns, "reconcile_bindings")  # does not exist
        provider = FakeProvider()
        provider.create_campaign({"name": "camp-1"})
        provider.create_campaign({"name": "camp-1"})
        self.assertEqual(reconcile([], provider.listing())["duplicated"],
                         ["camp-1"])


# ------------------------- 4. two intents may name one provider campaign

class TwoCampaignsMayNameOneProviderCampaign(CampaignTest):
    """`orchestrator.map_external` writes the id an operator typed. Nothing
    asks whether another campaign already has it."""

    def test_the_same_provider_id_may_be_mapped_twice(self):
        first, recs = self.ready_campaign(campaign_id="camp-1")
        second = orchestrator.create("camp-2", CLIENT, "Second",
                                     record_ids=[], created_by="U0DEMOADMIN1",
                                     rows=[])
        orchestrator.map_external(first, bison_campaign_id="901",
                                  by="U0DEMOADMIN1")
        orchestrator.map_external(second, bison_campaign_id="901",
                                  by="U0DEMOADMIN1")
        self.assertEqual(first["bison_campaign_id"],
                         second["bison_campaign_id"])
        # And both pass the launch checklist's mapping question.
        ok_first, _ = campaigns.check_external_mapping(first, recs, self.config)
        self.assertTrue(ok_first)

    @unittest.expectedFailure
    def test_a_provider_campaign_belongs_to_one_intent(self):
        """DESIRED, NOT PRESENT. A launch check that refuses a binding another
        campaign already holds."""
        check = getattr(campaigns, "check_binding_is_unique")  # does not exist
        first, recs = self.ready_campaign(campaign_id="camp-1")
        second = orchestrator.create("camp-2", CLIENT, "Second", rows=[])
        second["bison_campaign_id"] = first["bison_campaign_id"]
        campaigns.save([first, second])
        ok, _why = check(second, recs, self.config)
        self.assertFalse(ok)


# -------------------------- 5. a record in two campaigns loses its stops

class ARecordInTwoCampaignsLosesItsStopButton(CampaignTest):
    """THE WORST OF THESE. `campaigns.by_record` maps a record claimed by two
    live campaigns to None, and None means "no campaign", not "ambiguous". The
    freeze, the pause, the rejection and the approval all live on the campaign
    object, so a record in two campaigns is a record with none of them."""

    def setUp(self):
        super().setUp()
        self.campaign, self.recs, _result = self.approved_campaign("camp-1")

    def verdict(self):
        """The real chain: resolve the record's campaign the way `push.collect`
        does, then ask the only authority on whether a step may go."""
        recs = store.load()
        rec = recs[0]
        contact = rec["contacts"][0]
        resolved = campaigns.by_record(campaigns.load()).get(rec["id"])
        decision = eligibility.decide(rec, contact, "day1", channel="email",
                                      campaign=resolved, recs=recs,
                                      config=self.config)
        return resolved, decision

    def shadow_campaign(self):
        """What a duplicate creation leaves behind: a second live campaign
        listing the same records."""
        shadow = orchestrator.create("camp-2", CLIENT, "Duplicate intent",
                                     record_ids=list(self.campaign["record_ids"]),
                                     created_by="U0DEMOADMIN1", rows=[])
        campaigns.save([self.campaign, shadow])
        return shadow

    def test_the_approved_campaign_sends(self):
        """The baseline: one campaign, approved, and the step is eligible."""
        resolved, decision = self.verdict()
        self.assertEqual(resolved["campaign_id"], "camp-1")
        self.assertEqual(decision["verdict"], eligibility.ELIGIBLE)

    def test_one_campaign_frozen_stops_the_step(self):
        """The control. With one campaign, the freeze is seen."""
        campaigns.freeze(self.campaign, "somebody replied", by="U0DEMOADMIN1")
        campaigns.save([self.campaign])
        _resolved, decision = self.verdict()
        self.assertEqual(decision["reasons"],
                         [eligibility.BLOCKED_CAMPAIGN_FROZEN])

    def test_a_second_campaign_claiming_the_record_lifts_the_freeze(self):
        """THE ATTACK. Freeze the campaign, then add a second campaign over
        the same records - which is exactly what a duplicated intent produces.
        The record now resolves to NO campaign, and the freeze is not
        consulted by anything."""
        campaigns.freeze(self.campaign, "somebody replied", by="U0DEMOADMIN1")
        campaigns.save([self.campaign])
        self.shadow_campaign()

        resolved, decision = self.verdict()
        self.assertIsNone(resolved,
                          "a record in two campaigns resolves to no campaign")
        self.assertEqual(decision["verdict"], eligibility.ELIGIBLE)
        self.assertNotIn(eligibility.BLOCKED_CAMPAIGN_FROZEN,
                         decision["reasons"] or [])

    def test_the_same_lift_happens_for_a_paused_campaign(self):
        self.campaign["status"] = campaigns.PAUSED
        campaigns.save([self.campaign])
        _resolved, paused = self.verdict()
        self.assertEqual(paused["reasons"],
                         [eligibility.BLOCKED_CAMPAIGN_STOPPED])

        self.shadow_campaign()
        resolved, decision = self.verdict()
        self.assertIsNone(resolved)
        self.assertEqual(decision["verdict"], eligibility.ELIGIBLE)

    def test_a_terminal_campaign_needs_no_duplicate_to_lose_its_stops(self):
        """THE SAME HOLE, WITHOUT A DUPLICATE. `by_record` skips every campaign
        in a terminal status, so a REJECTED campaign claims none of its
        records - and a record with no campaign is a record with no campaign
        gate. `eligibility.BLOCKED_CAMPAIGN_REJECTED` exists and cannot be
        reached this way."""
        self.campaign["approval"] = {"action": "reject", "by": "U0DEMOADMIN1"}
        self.campaign["status"] = campaigns.REJECTED
        campaigns.save([self.campaign])

        resolved, decision = self.verdict()
        self.assertIsNone(resolved, "a rejected campaign claims no records")
        self.assertEqual(decision["verdict"], eligibility.ELIGIBLE)

    def test_the_rejection_is_seen_only_when_the_campaign_is_handed_over(self):
        """The gate itself works. It is the RESOLUTION that loses it, which is
        why this is a wiring defect rather than a missing rule."""
        self.campaign["approval"] = {"action": "reject", "by": "U0DEMOADMIN1"}
        self.campaign["status"] = campaigns.REJECTED
        campaigns.save([self.campaign])
        recs = store.load()
        decision = eligibility.decide(recs[0], recs[0]["contacts"][0], "day1",
                                      channel="email", campaign=self.campaign,
                                      recs=recs, config=self.config)
        self.assertEqual(decision["reasons"],
                         [eligibility.BLOCKED_CAMPAIGN_REJECTED])

    def test_a_rejected_campaigns_records_are_still_collected_for_a_push(self):
        """End of the chain: `push.collect` is what builds the batch, and it
        resolves the campaign exactly as above."""
        self.campaign["approval"] = {"action": "reject", "by": "U0DEMOADMIN1"}
        self.campaign["status"] = campaigns.REJECTED
        campaigns.save([self.campaign])
        ready, _skipped = push.collect(store.load(), day=21, client=CLIENT,
                                       campaign_rows=campaigns.load())
        self.assertTrue(ready, "a rejected campaign's steps are still ready")
        self.assertTrue(all(item["campaign"] is None for item in ready))

    @unittest.expectedFailure
    def test_a_rejected_campaign_stops_its_records(self):
        """DESIRED, NOT PRESENT. Rejecting a campaign should stop the records
        it names, not release them to the default cadence."""
        self.campaign["approval"] = {"action": "reject", "by": "U0DEMOADMIN1"}
        self.campaign["status"] = campaigns.REJECTED
        campaigns.save([self.campaign])
        _resolved, decision = self.verdict()
        self.assertTrue(str(decision["verdict"]).startswith("blocked"))

    @unittest.expectedFailure
    def test_an_ambiguous_membership_blocks_rather_than_defaults(self):
        """DESIRED, NOT PRESENT. Ambiguity on a safety path must fail closed.
        Two campaigns claiming one record should stop that record, not free
        it."""
        campaigns.freeze(self.campaign, "somebody replied", by="U0DEMOADMIN1")
        campaigns.save([self.campaign])
        self.shadow_campaign()
        _resolved, decision = self.verdict()
        self.assertTrue(str(decision["verdict"]).startswith("blocked"))


# ------------------------------- 6. two workers creating simultaneously

class TwoWorkersCreatingAtOnce(CampaignTest):
    """`orchestrator.create` is read-modify-write with no lock across the
    three. `campaigns.save` rewrites the whole file, and `file_transaction`
    runs none of the loss guards `store.transaction` runs."""

    def test_a_concurrent_create_erases_the_other_campaign(self):
        first, _recs = self.ready_campaign(campaign_id="camp-1")
        first["bison_campaign_id"] = "901"
        self.save_campaign(first)

        # Worker B loaded the file BEFORE worker A saved. The classic stale
        # read-modify-write, spelled out rather than raced, so it is
        # deterministic.
        stale = []
        second = orchestrator.create("camp-2", CLIENT, "Other segment",
                                     record_ids=[], created_by="U0DEMOADMIN1",
                                     rows=stale)
        campaigns.save(stale)

        surviving = {c["campaign_id"] for c in campaigns.load()}
        self.assertEqual(surviving, {"camp-2"})
        self.assertIsNone(campaigns.get("camp-1"),
                          "an approved campaign and its provider binding were "
                          "erased by an unrelated create")
        self.assertEqual(second["campaign_id"], "camp-2")

    def test_two_stale_savers_keep_only_the_later_edit(self):
        """The shape `interactions.apply` has: load the rows, do slow work -
        `orchestrator.decide` fingerprints every record in the campaign - then
        `campaigns.save(rows)` the list read before that work. Two decisions
        in flight at once, and only the later one survives."""
        first, _recs = self.ready_campaign(campaign_id="camp-1")
        second = orchestrator.create("camp-2", CLIENT, "Other segment",
                                     record_ids=[], created_by="U0DEMOADMIN1",
                                     rows=[])
        campaigns.save([first, second])

        worker_a = campaigns.load()
        worker_b = campaigns.load()
        campaigns.get("camp-1", worker_a)["status"] = campaigns.PAUSED
        campaigns.get("camp-2", worker_b)["name"] = "renamed by B"
        campaigns.save(worker_a)
        campaigns.save(worker_b)

        rows = campaigns.load()
        self.assertEqual(campaigns.get("camp-2", rows)["name"], "renamed by B")
        self.assertNotEqual(campaigns.get("camp-1", rows)["status"],
                            campaigns.PAUSED,
                            "worker A's pause was overwritten by worker B")

    @unittest.expectedFailure
    def test_a_campaign_row_cannot_be_dropped_by_a_writer_that_never_saw_it(self):
        """DESIRED, NOT PRESENT. `store.transaction` refuses a queue write
        that loses history. `file_transaction`, which campaigns use, has no
        such guard."""
        first, _recs = self.ready_campaign(campaign_id="camp-1")
        self.save_campaign(first)
        with self.assertRaises(Exception):
            campaigns.save([])


# --------------------------- 7. lead population is a batch with no ledger

class PartialPopulationIsNotRecoverable(CampaignTest):
    """Leads go up as ONE body of N. `actionledger` reserves one key per
    prospect action, so a batch write has one outcome for N actions: the
    provider's per-lead answer has nowhere to go."""

    def setUp(self):
        super().setUp()
        self.campaign, self.recs, _r = self.approved_campaign("camp-1")

    def payload_for(self):
        ready, _skipped = push.collect(store.load(), day=21, client=CLIENT,
                                       campaign_rows=campaigns.load())
        return push.payloads(ready, bison_campaign_id="901"), ready

    def test_n_prospect_actions_travel_as_one_request(self):
        prepared, _ready = self.payload_for()
        leads = prepared["emailbison"]["body"]["leads"]
        self.assertGreaterEqual(len(leads), 2)
        self.assertEqual(prepared["emailbison"]["method"], "POST")
        # One endpoint, one body, N actions.
        self.assertEqual(prepared["emailbison"]["count"], len(leads))

    def test_one_body_carries_one_address_many_times(self):
        """The email side has no per-person guard. `heyreach_rows` keeps a
        `seen` set and refuses "the same profile twice in one push";
        `emailbison_rows` has no equivalent, so the default `--day 21` batch
        carries one lead row per STEP - the same person, five times, in one
        request to one campaign."""
        prepared, _ready = self.payload_for()
        addresses = [lead["email"]
                     for lead in prepared["emailbison"]["body"]["leads"]]
        self.assertGreater(len(addresses), len(set(addresses)))
        worst = max(addresses.count(a) for a in set(addresses))
        self.assertGreater(worst, 1,
                           "one address appears more than once in one body")

    def test_the_linkedin_side_does_guard_this(self):
        """The asymmetry, asserted rather than asserted about. Same records,
        same batch: LinkedIn holds one pair per profile."""
        prepared, _ready = self.payload_for()
        pairs = prepared["heyreach"]["body"]["accountLeadPairs"]
        profiles = [p["lead"]["profileUrl"] for p in pairs]
        self.assertEqual(len(profiles), len(set(profiles)))

    def test_a_partially_accepted_batch_records_nothing_per_lead(self):
        """Seven of ten, the failure mode named in the mission. The provider
        tells us exactly which lead it refused; nothing consumes that."""
        prepared, _ready = self.payload_for()
        leads = prepared["emailbison"]["body"]["leads"]
        refused = leads[0]["email"]
        refused_rows = sum(1 for lead in leads if lead["email"] == refused)
        provider = FakeProvider(reject=[refused])
        provider.create_campaign({"name": "camp-1"})
        result = provider.add_leads("901", leads)

        self.assertEqual(result["accepted"], len(leads) - refused_rows)
        self.assertEqual(len(result["refused"]), refused_rows)
        # Not one row anywhere says which person reached the provider.
        self.assertEqual(actionledger.load(), [])
        for rec in store.load():
            for c in rec.get("contacts") or []:
                self.assertFalse(push.already_pushed(rec, c["key"], "day1"))

    def test_a_retry_of_the_batch_sends_the_accepted_leads_again(self):
        """THE DUPLICATE PROSPECT ACTION. Because the accepted half was never
        recorded, the obvious recovery - resend the batch - re-adds everybody
        who landed the first time."""
        prepared, _ready = self.payload_for()
        leads = prepared["emailbison"]["body"]["leads"]
        provider = FakeProvider(reject=[leads[0]["email"]])
        provider.create_campaign({"name": "camp-1"})
        provider.add_leads("901", leads)
        survivor = next(lead["email"] for lead in leads
                        if lead["email"] != leads[0]["email"])
        landed = provider.by_id("901")["leads"].count(survivor)

        provider.reject = set()                      # the address was fixed
        provider.add_leads("901", leads)             # naive recovery

        self.assertEqual(provider.by_id("901")["leads"].count(survivor),
                         landed * 2,
                         "everybody who landed the first time landed again")

    def test_a_provider_side_duplicate_is_not_visible_locally(self):
        prepared, _ready = self.payload_for()
        leads = prepared["emailbison"]["body"]["leads"]
        twice = leads[0]["email"]
        plain = FakeProvider()
        plain.create_campaign({"name": "camp-1"})
        plain.add_leads("901", leads)
        expected = plain.by_id("901")["leads"].count(twice)

        provider = FakeProvider(duplicate=[twice])
        provider.create_campaign({"name": "camp-1"})
        provider.add_leads("901", leads)
        self.assertEqual(provider.by_id("901")["leads"].count(twice),
                         expected * 2)
        # And nothing local can tell the two estates apart.
        self.assertEqual(actionledger.load(), [])

    @unittest.expectedFailure
    def test_each_lead_in_a_batch_is_reserved_before_the_batch(self):
        """DESIRED, NOT PRESENT. A batch write should reserve one ledger key
        per lead and settle each from the provider's per-lead answer."""
        settle = getattr(providerwrites, "settle_batch")   # does not exist
        settle({"accepted": [], "refused": []})


if __name__ == "__main__":
    unittest.main()
