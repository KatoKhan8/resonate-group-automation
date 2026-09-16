#!/usr/bin/env python3
"""APPROVED MATERIAL A + PROVIDER MATERIAL B, A != B, therefore no activation.

## What this covers that nothing else does

`test_the_provider_holds_what_was_approved` hand-builds BOTH sides of the diff
as literal dicts and mutates one of them. That proves `configdiff.diff` walks a
union and scores a field correctly, and it proves nothing at all about
`approved_heyreach` and `approved_bison` - the functions that turn canonical
state into side A. A diff is only a gate if the side it defends is assembled
from the campaign, the records, the approvals and the sender mapping that a
human actually blessed.

So every case here builds a REAL campaign - real queue records, real
`approve.approve_step` stamps, a real `campaigns.material()` fingerprint - runs
the REAL `compare_heyreach` / `compare_bison`, and mutates only the fake
provider payload. One mutation per test, and each asserts the EXACT SET of
fields that failed, so a test cannot pass because some earlier or unrelated
field happened to fail first.

## The findings are the tests that do not pass

Six mutations this gate cannot see are written as `expectedFailure` rather than
omitted, because a gap nobody wrote down is a gap somebody rediscovers in front
of a client. Every one of them is on the EMAIL channel or on a dimension
neither channel models:

  1. an email campaign with NO approved copy diffs PASS
  2. WHO is in an email campaign does not block - `lead_set` is required on
     HeyReach and not on EmailBison
  3. `compare_bison` can never reach PASS at all
  4. `EmailBison` per-domain send cap - read, then discarded by the `_` prefix
  5. `HeyReach` per-campaign daily limit - no read route exists (documented)
  6. the sending SCHEDULE on either provider - in neither side of the diff, and
     not in `campaigns.material()` either, so it is outside the approval too

(1) is the serious one, and it is the defect `configdiff` exists to prevent
reproduced on the channel nobody tested. `approved_bison` adds every emailable
contact to the approved lead set BEFORE it filters on approval, so a campaign
where nobody approved a single word produces an APPROVED_CONFIG with a
populated lead set and empty copy - and a provider campaign holding those leads
with no active sequence step matches it exactly. `approved_heyreach` refuses
this case by name (`no APPROVED and renderable LinkedIn step ... an unapproved
step is not an approved config`). The email side has no such refusal.

(2) is the same correction this module already made once. `lead_set` was added
to `REQUIRED_HEYREACH` so the diff would assert WHO the provider holds rather
than how many; `REQUIRED_BISON` never got the field, though `provider_bison`
pages the full lead set and `approved_bison` builds one. Swap one address for
another and the report says `lead_set: mismatch` while the verdict never
mentions it, because the count still agrees.

(3) shapes every email test below: `approved_bison` names its steps with
cadence keys (`day1`) and `provider_bison` names them with provider order
(`step1`), and `actions` is in `REQUIRED_BISON`. The two can never be equal, so
`compare_bison` cannot return PASS for any campaign with approved copy. It
fails closed, which is the safe direction, but it means the email half of this
gate has never once been exercised against a match, and it masks every other
email verdict. Email tests therefore assert
`failures == {the standing defect} | {the mutation}`, which flips loudly the
day the naming is reconciled.
"""
import unittest
from unittest import mock

from src import (approve, cadence, campaigns, configdiff, executionguard,
                 providerwrites, store)
from tests.campaignbase import CampaignTest

# Fictional provider identifiers. Nothing here names a real estate, list,
# organisation unit or seat.
HEYREACH_CAMPAIGN = "7001"
HEYREACH_LIST = "5150"
HEYREACH_ORG = "6060"
HEYREACH_SEAT = "4242"
BISON_CAMPAIGN = "9001"
BISON_SEAT = "3131"
BISON_WORKSPACE = 99

# `approved_bison` says `day1`; `provider_bison` says `step1`; `actions` is
# required. Named rather than tolerated, so an email assertion states which
# failure is the mutation under test and which is the standing defect.
STANDING_EMAIL_DEFECT = {"actions"}

# No HeyReach read route exposes a per-campaign daily limit, so the field comes
# back UNVERIFIABLE on every comparison. It is deliberately absent from
# `REQUIRED_HEYREACH`, so it does NOT fail the verdict - which is why the
# LinkedIn campaign below can be PASS while this set is non-empty. Carried in
# every expected set rather than filtered out of `failing()`, because a helper
# that quietly drops unverifiable fields is a helper that would hide the day one
# of them starts mattering.
STANDING_LINKEDIN_UNVERIFIABLE = {"daily_limit"}

ONE_COMPANY = (("acme", "Acme Services", "acme.test"),)


def failing(readback):
    """The set of field names that failed, from the diff's own verdicts.

    Read off `fields` rather than parsed out of the `failures` strings: a test
    that splits a human-readable message on `": "` breaks when somebody
    improves the message, which is the habit CLAUDE.md names.
    """
    return {name for name, row in readback.diff["fields"].items()
            if row["verdict"] in configdiff.FAILING}


class Factory(CampaignTest):
    """One campaign, staged at both providers, with the provider side faked."""

    def assert_blocks(self, readback, expected, standing=frozenset(),
                      blocking=None):
        """The mutation FAILED, for exactly its own fields, and at least one of
        those fields is one the comparison DECLARES REQUIRED.

        The third assertion is not decoration. `failing()` reads raw per-field
        verdicts, and a field's verdict is MISMATCH whether or not it is
        required - so without this, removing a field from `REQUIRED_HEYREACH`
        or `REQUIRED_BISON` leaves every assertion here green while the gate
        stops blocking on it. Measured: deleting `subjects` from
        `REQUIRED_BISON` broke nothing at all until this line existed.

        `blocking` defaults to `expected` and is narrowed only where a field is
        genuinely diffed-but-not-required today. Every such narrowing has a
        companion `expectedFailure` in `MutationsThisGateCannotSee` naming it,
        because a quiet narrowing here would be the same defect one level up.
        """
        blocking = expected if blocking is None else blocking
        self.assertEqual(readback.verdict, configdiff.FAIL)
        self.assertEqual(failing(readback), standing | expected)
        self.assertTrue(blocking, "a mutation that blocks on nothing is not a "
                                  "gate; state the finding instead")
        self.assertLessEqual(
            blocking, set(readback.diff["required"]),
            "the mutated field is reported but not declared required, so it "
            "does not block a launch on its own")
        return readback

    def stage(self, approve_email=True, approve_linkedin=True):
        recs = self.seed_records(companies=ONE_COMPANY)
        self.draft_everything(recs)
        if approve_email:
            self.approve_drafts(recs)
        if approve_linkedin:
            rec = recs[0]
            contact = rec["contacts"][0]
            step = cadence.expand_step(rec, contact, configdiff.LINKEDIN_STEP,
                                       self.config)
            self.assertTrue(step, "the LinkedIn note did not render")
            approve.approve_step(rec, contact["key"], "day3",
                                 by="U0DEMOADMIN1", config=self.config,
                                 step=step)
        store.save(recs)
        recs = store.load()
        campaign = self.make_campaign(recs)
        campaign.update({
            "heyreach_campaign_id": HEYREACH_CAMPAIGN,
            "heyreach_list_id": HEYREACH_LIST,
            "org_unit": HEYREACH_ORG,
            "bison_campaign_id": BISON_CAMPAIGN,
            "workspace": str(BISON_WORKSPACE),
            "provider_delays": [["HOUR", 0]],
        })
        campaign["senders"] = {"email": [{"id": BISON_SEAT, "daily_limit": 40}],
                               "linkedin": [{"id": HEYREACH_SEAT,
                                             "daily_limit": 20}]}
        self.save_campaign(campaign)
        return campaign, recs

    # ------------------------------------------------------------ LinkedIn

    def held_by_heyreach(self, campaign, recs, **mutation):
        """What the provider holds: an exact copy of the approved side, then
        one mutation. Built FROM the approved config on purpose - a fixture
        that restates the note by hand passes when the template changes and the
        approval does not, which is agreement with nobody."""
        approved = configdiff.approved_heyreach(campaign, recs, self.config)
        held = {
            "campaign_id": int(approved["campaign_id"]),
            "name": approved["campaign_name"],
            "status": approved["status"],
            "org_unit": int(approved["org_unit"]),
            "sender_ids": [int(s) for s in sorted(approved["sender_ids"])],
            "list_id": int(approved["list_id"]),
            "note": approved["note"],
            "delay_unit": approved["delays"][0][0],
            "delay": approved["delays"][0][1],
            "leads": sorted(approved["lead_set"]),
            "extra_nodes": (),
        }
        held.update(mutation)
        return held

    def compare_linkedin(self, campaign, recs, **mutation):
        held = self.held_by_heyreach(campaign, recs, **mutation)
        node = {"nodeType": "END"}
        for kind in reversed(held["extra_nodes"]):
            node = {"nodeType": kind, "actionDelayUnit": "DAY",
                    "actionDelay": 1, "unconditionalNode": node}
        graph = {"nodeType": "CONNECTION_REQUEST",
                 "actionDelayUnit": held["delay_unit"],
                 "actionDelay": held["delay"],
                 "payload": {"messages": [held["note"]], "fallbackMessage": ""},
                 "unconditionalNode": node}
        row = {"id": held["campaign_id"], "name": held["name"],
               "status": held["status"],
               "organizationUnitId": held["org_unit"],
               "campaignAccountIds": held["sender_ids"],
               "linkedInUserListId": held["list_id"], "progressStats": {}}
        leads = [{"profile_url": f"https://www.linkedin.com/in/{slug}"}
                 for slug in held["leads"]]
        with mock.patch("src.providers.heyreach.campaign_read",
                        return_value=row), \
             mock.patch("src.providers.heyreach.campaign_sequence",
                        return_value=graph), \
             mock.patch("src.providers.heyreach.campaign_leads",
                        return_value=(leads, len(leads))):
            return configdiff.compare_heyreach(campaign, recs, self.config)

    # --------------------------------------------------------------- email

    def held_by_bison(self, campaign, recs, **mutation):
        approved = configdiff.approved_bison(campaign, recs, self.config)
        held = {
            "campaign_id": int(approved["campaign_id"]),
            "name": approved["campaign_name"],
            "status": approved["status"],
            "workspace": int(approved["workspace"]),
            "sender_ids": [int(s) for s in sorted(approved["sender_ids"])],
            "leads": sorted(approved["lead_set"]),
            "subjects": list(approved["subjects"]),
            "bodies": list(approved["bodies"]),
            "delays": list(approved["delays"]),
            "thread_replies": list(approved.get("thread_replies", ())),
            "max_emails_per_day": approved["max_emails_per_day"],
            "max_new_leads_per_day": approved["max_new_leads_per_day"],
            "per_domain_cap": 3,
        }
        held.update(mutation)
        return held

    def compare_email(self, campaign, recs, **mutation):
        held = self.held_by_bison(campaign, recs, **mutation)
        steps = [{"order": i + 1, "active": True, "email_subject": subject,
                  "email_body": body, "wait_in_days": delay,
                  "thread_reply": tr}
                 for i, (subject, body, delay, tr)
                 in enumerate(zip(held["subjects"], held["bodies"],
                                  held["delays"], held["thread_replies"]))]
        row = {"id": held["campaign_id"], "name": held["name"],
               "status": held["status"],
               "max_emails_per_day": held["max_emails_per_day"],
               "max_new_leads_per_day": held["max_new_leads_per_day"],
               "daily_max_sends_per_receiving_domain": held["per_domain_cap"]}
        base = f"/campaigns/{held['campaign_id']}"
        pages = {
            base: {"data": row},
            f"{base}/sender-emails?page=1": {
                "data": [{"id": i} for i in held["sender_ids"]],
                "meta": {"total": len(held["sender_ids"])}},
            f"{base}/leads?page=1": {
                "data": [{"email": e} for e in held["leads"]],
                "meta": {"total": len(held["leads"])}},
            f"{base}/sequence-steps": {"data": steps},
        }

        def transport(method, url, headers, body=None, timeout=None):
            path = url.split("https://bison.test", 1)[-1]
            if path not in pages:
                raise AssertionError(f"the diff read an unfaked route: {path}")
            return 200, pages[path]

        with mock.patch("src.configdiff.request", side_effect=transport), \
             mock.patch("src.providers.bison.base",
                        return_value="https://bison.test"), \
             mock.patch("src.providers.bison.headers", return_value={}), \
             mock.patch("src.providers.bison.require_workspace",
                        return_value=None), \
             mock.patch("src.providers.bison.bound_workspace",
                        return_value={"id": held["workspace"]}):
            return configdiff.compare_bison(campaign, recs, self.config,
                                            expect_workspace=BISON_WORKSPACE)


class AnExactMatchIsTheOnlyThingThatPasses(Factory):

    def test_the_linkedin_campaign_as_staged_passes(self):
        campaign, recs = self.stage()
        readback = self.compare_linkedin(campaign, recs)
        self.assertEqual(readback.verdict, configdiff.PASS, readback.failures)

    def test_and_it_checked_enough_to_mean_something(self):
        """A diff that examined nothing must not read as agreement."""
        campaign, recs = self.stage()
        readback = self.compare_linkedin(campaign, recs)
        self.assertGreaterEqual(readback.diff["checked"], 12)
        self.assertIn("note", readback.diff["fields"])
        self.assertIn("lead_set", readback.diff["fields"])

    def test_the_approved_side_came_from_canonical_state(self):
        """Side A is the campaign row and the record, never the provider.

        The note asserted here is the one `cadence.expand_step` renders and
        `approve.approve_step` stamped - not a string this test typed - so if
        the approved side were ever built from the provider payload, this would
        still pass and the next test would not.
        """
        campaign, recs = self.stage()
        approved = configdiff.approved_heyreach(campaign, recs, self.config)
        rec = store.get(campaign["record_ids"][0], recs)
        step = cadence.expand_step(rec, rec["contacts"][0],
                                   configdiff.LINKEDIN_STEP, self.config)
        self.assertEqual(approved["note"], " ".join(step["note"].split()))
        self.assertEqual(approved["sender_ids"], frozenset({HEYREACH_SEAT}))
        self.assertEqual(approved["list_id"], HEYREACH_LIST)

    def test_a_provider_holding_the_placeholder_does_not_become_its_approval(self):
        """The live 2026-09-09 defect, through the real approved-side builder."""
        campaign, recs = self.stage()
        readback = self.compare_linkedin(
            campaign, recs, note="Hey, would love to connect!")
        self.assert_blocks(readback, {"note"}, STANDING_LINKEDIN_UNVERIFIABLE)


class OneLinkedInMutationAtATime(Factory):
    """Each mutation fails, and fails for ITS OWN field.

    `assertEqual` on the whole failing set rather than `assertIn` on one name:
    a test that only asserts "something failed" passes when an unrelated field
    is broken, which is how a gate comes to be trusted for a reason that is not
    true.
    """

    def check(self, expected, **mutation):
        campaign, recs = self.stage()
        readback = self.compare_linkedin(campaign, recs, **mutation)
        return self.assert_blocks(readback, expected,
                                  STANDING_LINKEDIN_UNVERIFIABLE)

    def test_wrong_sender(self):
        self.check({"sender_ids"}, sender_ids=[999001])

    def test_an_extra_sender_nobody_approved(self):
        self.check({"sender_ids"}, sender_ids=[int(HEYREACH_SEAT), 999001])

    def test_wrong_lead(self):
        self.check({"lead_set"}, leads=["somebody-else"])

    def test_an_extra_lead(self):
        campaign, recs = self.stage()
        approved = configdiff.approved_heyreach(campaign, recs, self.config)
        readback = self.compare_linkedin(
            campaign, recs, leads=sorted(approved["lead_set"]) + ["a-stranger"])
        # Two fields, and both are the mutation: who is in it and how many.
        self.assert_blocks(readback, {"lead_set", "lead_count"},
                           STANDING_LINKEDIN_UNVERIFIABLE)

    def test_a_missing_lead(self):
        campaign, recs = self.stage()
        readback = self.compare_linkedin(campaign, recs, leads=[])
        self.assert_blocks(readback, {"lead_set", "lead_count"},
                           STANDING_LINKEDIN_UNVERIFIABLE)

    def test_wrong_note(self):
        self.check({"note"}, note="different words entirely")

    def test_a_note_with_one_word_changed(self):
        campaign, recs = self.stage()
        approved = configdiff.approved_heyreach(campaign, recs, self.config)
        altered = approved["note"].replace("curious", "wondering")
        self.assertNotEqual(altered, approved["note"], "the fixture note "
                            "changed shape; pick a word it still contains")
        readback = self.compare_linkedin(campaign, recs, note=altered)
        self.assert_blocks(readback, {"note"}, STANDING_LINKEDIN_UNVERIFIABLE)

    def test_an_empty_note(self):
        self.check({"note"}, note="")

    def test_wrong_delay(self):
        self.check({"delays"}, delay_unit="DAY", delay=3)

    def test_an_extra_sequence_step(self):
        """A MESSAGE node nobody approved. Still provably LinkedIn-only, which
        is the point: `linkedin_only` passes and `actions` is what catches it."""
        readback = self.check({"actions"}, extra_nodes=("MESSAGE",))
        self.assertTrue(readback.provider["linkedin_only"])

    def test_wrong_tenant(self):
        self.check({"org_unit"}, org_unit=999002)

    def test_wrong_list(self):
        """Re-pointing the campaign at the client's production list."""
        self.check({"list_id"}, list_id=999003)

    def test_wrong_campaign(self):
        self.check({"campaign_id"}, campaign_id=999004)

    def test_an_already_activated_campaign(self):
        self.check({"status"}, status="IN_PROGRESS")

    def test_wrong_campaign_name(self):
        self.check({"campaign_name"}, name="somebody else's campaign")


class OneEmailMutationAtATime(Factory):
    """The same discipline on EmailBison, minus the standing `actions` defect.

    Every assertion here adds `STANDING_EMAIL_DEFECT` to the expected set. When
    `approved_bison` and `provider_bison` are reconciled on step naming, every
    one of these fails and says exactly why - which is the behaviour wanted
    from a test that documents a defect rather than tolerating it.
    """

    def check(self, expected, blocking=None, **mutation):
        campaign, recs = self.stage()
        readback = self.compare_email(campaign, recs, **mutation)
        return self.assert_blocks(readback, expected, STANDING_EMAIL_DEFECT,
                                  blocking=blocking)

    def test_wrong_sender(self):
        self.check({"sender_ids"}, sender_ids=[999005])

    def test_a_wrong_email_address_blocks(self):
        """THE FINDING, now closed, and it is the one `configdiff` had already
        corrected on the other channel. `lead_set` was made REQUIRED for
        HeyReach - "the diff now asserts WHO the provider holds rather than
        how many" - and `REQUIRED_BISON` was never given the same field,
        though `provider_bison` reads the whole lead set and `approved_bison`
        builds one. So on email, swapping one person for another was DIFFED,
        REPORTED, and contributed nothing to the verdict, because the count
        still agreed.

        This asserted that behaviour exactly as it was, with the `should` kept
        beside it in `MutationsThisGateCannotSee` as an expected failure. The
        field is required now, so both turn over together.
        """
        campaign, recs = self.stage()
        readback = self.compare_email(campaign, recs,
                                      leads=["someone.else@elsewhere.test"])
        self.assertEqual(
            readback.diff["fields"]["lead_set"]["verdict"], configdiff.MISMATCH)
        self.assertIn("lead_set", readback.diff["required"])
        self.assertNotEqual(readback.verdict, configdiff.PASS,
                            "a campaign staged to the wrong person passed")
        self.assertEqual(readback.diff["fields"]["lead_count"]["verdict"],
                         configdiff.MATCH,
                         "the count agrees, which is why only the identity "
                         "could have caught this")

    def test_an_extra_lead(self):
        """Caught, but on the COUNT rather than on who it is."""
        campaign, recs = self.stage()
        approved = configdiff.approved_bison(campaign, recs, self.config)
        readback = self.compare_email(
            campaign, recs,
            leads=sorted(approved["lead_set"]) + ["stranger@elsewhere.test"])
        self.assert_blocks(readback, {"lead_set", "lead_count"},
                           STANDING_EMAIL_DEFECT, blocking={"lead_count"})

    def test_a_missing_lead(self):
        self.check({"lead_set", "lead_count"}, blocking={"lead_count"},
                   leads=[])

    def test_wrong_subject(self):
        campaign, recs = self.stage()
        approved = configdiff.approved_bison(campaign, recs, self.config)
        subjects = list(approved["subjects"])
        subjects[0] = "a subject nobody approved"
        readback = self.compare_email(campaign, recs, subjects=subjects)
        self.assert_blocks(readback, {"subjects"}, STANDING_EMAIL_DEFECT)

    def test_wrong_body(self):
        campaign, recs = self.stage()
        approved = configdiff.approved_bison(campaign, recs, self.config)
        bodies = list(approved["bodies"])
        bodies[-1] = bodies[-1] + " ps. one more thing nobody approved."
        readback = self.compare_email(campaign, recs, bodies=bodies)
        self.assert_blocks(readback, {"bodies"}, STANDING_EMAIL_DEFECT)

    def test_wrong_delay(self):
        campaign, recs = self.stage()
        approved = configdiff.approved_bison(campaign, recs, self.config)
        delays = list(approved["delays"])
        delays[1] = delays[1] + 4
        readback = self.compare_email(campaign, recs, delays=delays)
        self.assert_blocks(readback, {"delays"}, STANDING_EMAIL_DEFECT)

    def test_an_extra_sequence_step(self):
        campaign, recs = self.stage()
        approved = configdiff.approved_bison(campaign, recs, self.config)
        readback = self.compare_email(
            campaign, recs,
            subjects=list(approved["subjects"]) + ["one more nobody approved"],
            bodies=list(approved["bodies"]) + ["and a body nobody approved"],
            delays=list(approved["delays"]) + [30])
        self.assert_blocks(readback, {"subjects", "bodies", "delays"},
                           STANDING_EMAIL_DEFECT)

    def test_wrong_daily_limit(self):
        """The one limit EmailBison does publish, so the diff can assert it."""
        self.check({"max_emails_per_day"}, max_emails_per_day=2000)

    def test_wrong_new_lead_limit(self):
        self.check({"max_new_leads_per_day"}, max_new_leads_per_day=2000)

    def test_wrong_tenant(self):
        """The credential's binding is chosen in the vendor UI and has moved
        mid-session, which is why this is read from the provider rather than
        assumed from the campaign row."""
        self.check({"workspace"}, workspace=1)

    def test_an_already_activated_campaign(self):
        self.check({"status"}, status="active")


class MutationsThisGateCannotSee(Factory):
    """The findings. Every test here asserts the behaviour that SHOULD hold.

    `expectedFailure`, not `skip`: a skip stays green forever and says nothing,
    while an expected failure becomes an UNEXPECTED SUCCESS - a suite failure -
    the day somebody closes the gap, which is the only way a note like this
    stays true.
    """

    @unittest.expectedFailure
    def test_an_email_campaign_with_no_approved_copy_should_not_pass(self):
        """THE SERIOUS ONE. `approved_bison` runs `leads.add(address)` BEFORE
        it filters on approval, so every emailable contact is in the approved
        lead set whether or not one word of theirs was ever blessed. With no
        approved step the approved copy is empty, and a provider campaign
        holding those leads with no active sequence step matches it exactly.

        The gate whose entire purpose is "the provider holds what was approved"
        therefore certifies a campaign against an approval that does not exist.
        `approved_heyreach` refuses this by name - "an unapproved step is not an
        approved config" - and the email side has no equivalent.
        """
        campaign, recs = self.stage(approve_email=False, approve_linkedin=True)
        readback = self.compare_email(campaign, recs, subjects=[], bodies=[],
                                      delays=[])
        self.assertEqual(readback.verdict, configdiff.FAIL,
                         "a campaign nobody approved any copy for passed the "
                         "provider-agreement gate")

    def test_who_is_in_an_email_campaign_blocks(self):
        """CLOSED. `lead_set` is in `REQUIRED_BISON` now, as it always was in
        `REQUIRED_HEYREACH`.

        The LinkedIn side was corrected for exactly this and the note is still
        in the module: a campaign used to be proven by `lead_count` plus a
        verified list id - "the provider holds one lead" rather than "the
        provider holds this person". `provider_bison` has always paged the full
        lead set and `approved_bison` has always built one, so the stronger
        question is answerable on email today and simply is not asked.

        Until it was, a staged email campaign where one address had been
        swapped for another diffed with `lead_set: mismatch` in the report and
        a verdict that never mentioned it.
        """
        self.assertIn("lead_set", configdiff.REQUIRED_BISON)

    @unittest.expectedFailure
    def test_a_changed_per_domain_send_cap_should_fail(self):
        """`provider_bison` READS `daily_max_sends_per_receiving_domain` and
        then files it under `_per_domain_cap`. `diff` skips every key starting
        `_`, so the field is fetched, carried, printed for a human, and scored
        by nothing. It decides how many people at one company hear from us in a
        day, and the approved side has no opinion about it at all.

        Asserted as a CHANGE to the failing set rather than as a FAIL verdict.
        A bare `assertEqual(verdict, FAIL)` reports an unexpected success here -
        the comparison does fail, on the standing `actions` defect, and would
        pass this test while noticing nothing whatever about the cap.
        """
        campaign, recs = self.stage()
        untouched = failing(self.compare_email(campaign, recs))
        mutated = failing(self.compare_email(campaign, recs,
                                             per_domain_cap=500))
        self.assertNotEqual(mutated, untouched)

    @unittest.expectedFailure
    def test_the_heyreach_daily_limit_should_be_verifiable(self):
        """Structurally impossible today and documented as such: no HeyReach
        read route exposes a per-campaign daily limit, so `provider_heyreach`
        returns UNVERIFIABLE and `REQUIRED_HEYREACH` omits it. The approved
        side DOES state one, from `campaign.daily_volume.linkedin`. Anybody with
        vendor UI access can raise it after approval and nothing here sees it.
        """
        campaign, recs = self.stage()
        readback = self.compare_linkedin(campaign, recs)
        self.assertNotEqual(readback.provider["daily_limit"],
                            configdiff.UNVERIFIABLE)

    @unittest.expectedFailure
    def test_the_sending_schedule_should_be_part_of_the_comparison(self):
        """Neither side of either diff has a schedule field. Both providers
        carry a campaign-level sending window, sending days and a timezone in
        their UIs; nothing here reads one, nothing approves one, and
        `campaigns.sending_config()` does not include the client's
        `scheduling.windows` block either - so the hour a prospect is written
        at is outside the approval AND outside the provider comparison.
        """
        campaign, recs = self.stage()
        readback = self.compare_linkedin(campaign, recs)
        self.assertTrue(
            {"schedule", "sending_window", "sending_days", "timezone"}
            & set(readback.diff["fields"]))

    @unittest.expectedFailure
    def test_compare_bison_should_be_able_to_pass(self):
        """`approved_bison` says `day1`; `provider_bison` says `step1`; both are
        the `actions` field and `actions` is in `REQUIRED_BISON`. No email
        campaign with approved copy can ever reach PASS, so the email half of
        this gate has never been exercised against an exact match."""
        campaign, recs = self.stage()
        readback = self.compare_email(campaign, recs)
        self.assertEqual(readback.verdict, configdiff.PASS, readback.failures)

    def test_the_two_channels_disagree_about_the_expected_status(self):
        """Not expectedFailure, because this one is demonstrable today.

        `provider_status_expected` is ONE scalar on the campaign row, and the
        two providers spell a paused campaign differently - `approved_heyreach`
        defaults to `PAUSED`, `approved_bison` to `paused`. A dual-channel
        campaign cannot carry a value that satisfies both diffs, so setting it
        for one channel breaks the other.
        """
        campaign, recs = self.stage()
        campaign["provider_status_expected"] = "PAUSED"
        self.assertEqual(
            configdiff.approved_heyreach(campaign, recs, self.config)["status"],
            "PAUSED")
        self.assertEqual(
            configdiff.approved_bison(campaign, recs, self.config)["status"],
            "PAUSED")
        # ...and the provider answers lowercase, so the email diff mismatches.
        readback = self.compare_email(campaign, recs, status="paused")
        self.assertIn("status", failing(readback))


class TheFingerprintDoesNotCoverTheSchedule(Factory):
    """`campaigns.material()` is the OTHER half of "no activation without an
    exact match": the diff proves the provider holds side A, and the
    fingerprint proves side A is what a human approved. A field outside both is
    a field that can be changed after approval with no trace anywhere.
    """

    def fingerprints(self, campaign, recs, config=None):
        return campaigns.fingerprint(campaign, recs, config or self.config)

    def test_the_provider_binding_is_covered(self):
        """Already verified; asserted here so the rest of the class has a
        control that proves the comparison is live."""
        campaign, recs = self.stage()
        before = self.fingerprints(campaign, recs)
        missing = object()
        for field, value in (("org_unit", "999006"),
                             ("heyreach_list_id", "999007"),
                             ("workspace", "1"),
                             ("provider_status_expected", "IN_PROGRESS"),
                             ("provider_delays", [["DAY", 3]])):
            was = campaign.get(field, missing)
            campaign[field] = value
            self.assertNotEqual(self.fingerprints(campaign, recs), before,
                                f"{field} is outside the fingerprint")
            if was is missing:
                campaign.pop(field)
            else:
                campaign[field] = was

    def test_the_campaign_name_is_not_covered(self):
        """And both diffs REQUIRE `campaign_name`. Renaming after approval
        leaves the approval current and makes the provider comparison fail, so
        the two halves of the gate disagree about whether anything changed."""
        campaign, recs = self.stage()
        before = self.fingerprints(campaign, recs)
        campaign["name"] = "a different campaign name"
        self.assertEqual(self.fingerprints(campaign, recs), before,
                         "campaign name is now covered - delete this test")
        self.assertIn("campaign_name", configdiff.REQUIRED_HEYREACH)
        self.assertIn("campaign_name", configdiff.REQUIRED_BISON)

    def test_the_client_sending_schedule_is_not_covered(self):
        """`sending_config()` reads six keys and `scheduling` is not one, so a
        client's sending windows, sending days and per-channel hours can all be
        changed after approval without moving the fingerprint."""
        campaign, recs = self.stage()
        before = self.fingerprints(campaign, recs)
        altered = dict(self.config)
        altered["scheduling"] = {"windows": {"email": ["22:00", "23:30"],
                                             "days": [6, 7]}}
        self.assertEqual(self.fingerprints(campaign, recs, altered), before,
                         "the schedule is now covered - delete this test")

    def test_the_client_volume_and_pilot_ceilings_are_not_covered(self):
        """`pilotcaps.configured()` reads `campaign.daily_volume`, `pilot` and
        `fatigue` off the client config. None of the three is in
        `sending_config()`, so how much goes out per day, and how often one
        company may hear from us, are outside the approved material."""
        campaign, recs = self.stage()
        before = self.fingerprints(campaign, recs)
        for key, value in (("pilot", {"enabled": "off"}),
                           ("campaign", {"daily_volume": {"email": 2000}}),
                           ("fatigue", {"account":
                                        {"max_touches_per_week": 40}})):
            altered = dict(self.config)
            altered[key] = value
            self.assertEqual(self.fingerprints(campaign, recs, altered), before,
                             f"config.{key} is now covered - delete this test")


class NoActivationOnAnythingLessThanAnExactMatch(Factory):
    """The diff's verdict has to actually stop the write, not merely exist."""

    def test_activation_is_refused_at_the_write_door_regardless(self):
        """Activation is BLOCKING by construction rather than by a flag, on
        both channels. This is the outermost reason no mutation here can reach
        a prospect, and it is asserted first so the gate tests below are read
        as defence in depth rather than as the only defence."""
        for operation in (providerwrites.LINKEDIN_ACTIVATE,
                          providerwrites.EMAIL_ACTIVATE):
            self.assertFalse(providerwrites.is_supported(operation))
            with self.assertRaises(providerwrites.WriteUnsupported):
                providerwrites.require_supported(operation)

    def test_a_failed_readback_refuses_at_the_readback_gate(self):
        """And the trace proves nothing earlier fired: tenancy, approval and
        campaign_approval all PASSED, and the refusal is the diff's."""
        campaign, recs = self.stage()
        self.approve_campaign(campaign, recs)
        readback = self.compare_linkedin(campaign, recs,
                                         note="Hey, would love to connect!")
        self.assertEqual(readback.verdict, configdiff.FAIL)
        rec = store.get(campaign["record_ids"][0], recs)
        with self.assertRaises(executionguard.NotAuthorized) as caught:
            executionguard.authorize(
                operation=providerwrites.LINKEDIN_ADD_LEAD, channel="linkedin",
                campaign=campaign, rec=rec, contact=rec["contacts"][0],
                step_key="day3", workspace=None, config=self.config, recs=recs,
                readback=readback, reserve=False)
        self.assertEqual(caught.exception.gate, "readback")
        self.assertEqual(caught.exception.passed,
                         ("tenancy", "approval", "campaign_approval"))

    def test_a_passing_readback_for_another_campaign_is_not_this_one(self):
        """A PASS is not transferable. `Readback` carries what it compared."""
        campaign, recs = self.stage()
        self.approve_campaign(campaign, recs)
        readback = self.compare_linkedin(campaign, recs)
        self.assertEqual(readback.verdict, configdiff.PASS, readback.failures)
        readback.campaign_id = "some-other-campaign"
        rec = store.get(campaign["record_ids"][0], recs)
        with self.assertRaises(executionguard.NotAuthorized) as caught:
            executionguard.authorize(
                operation=providerwrites.LINKEDIN_ADD_LEAD, channel="linkedin",
                campaign=campaign, rec=rec, contact=rec["contacts"][0],
                step_key="day3", workspace=None, config=self.config, recs=recs,
                readback=readback, reserve=False)
        self.assertEqual(caught.exception.gate, "readback")

    def test_a_readback_authorises_one_action_only(self):
        campaign, recs = self.stage()
        readback = self.compare_linkedin(campaign, recs)
        readback.spend()
        with self.assertRaises(configdiff.DiffRefused):
            readback.spend()

    # ------------------------------------------------------------- helper

    def approve_campaign(self, campaign, recs):
        """Approve AFTER the provider binding is set, because setting it is
        exactly what would invalidate an earlier approval."""
        from src import orchestrator
        orchestrator.prepare(campaign, recs, self.config)
        orchestrator.request_approval(campaign, recs, self.config)
        orchestrator.decide(campaign, "U0DEMOADMIN1", "approve",
                            fingerprint=campaigns.fingerprint(
                                campaign, recs, self.config),
                            interaction_id="i-readback", config=self.config,
                            recs=recs)
        self.save_campaign(campaign)
        self.assertTrue(campaigns.approval_is_current(campaign, recs,
                                                      self.config))
        return campaign


if __name__ == "__main__":
    unittest.main()
