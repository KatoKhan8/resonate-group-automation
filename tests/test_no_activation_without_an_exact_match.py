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

Mutations this gate cannot see are written as `expectedFailure` rather than
omitted, because a gap nobody wrote down is a gap somebody rediscovers in front
of a client. Six were recorded. THREE ARE NOW CLOSED, and each closed one is
kept here as a positive assertion rather than deleted, so a regression brings
the finding back rather than removing the only record of it:

  1. CLOSED - an email campaign with NO approved copy used to diff PASS. It is
     `DiffRefused` now: `test_an_email_campaign_with_no_approved_copy_is_refused`
  2. CLOSED - WHO is in an email campaign now blocks; `lead_set` is in
     `REQUIRED_BISON`: `test_who_is_in_an_email_campaign_blocks`
  3. CLOSED - `compare_bison` can reach PASS (TASK-215 reconciled `day1` with
     `step1`): `test_the_email_campaign_as_staged_passes`
  4. OPEN - `EmailBison` per-domain send cap: read, then discarded by the `_`
     prefix, so nothing scores it
  5. OPEN - `HeyReach` per-campaign daily limit: no read route exists
  6. OPEN - the sending SCHEDULE on either provider: in neither side of the
     diff, and not in `campaigns.material()` either, so it is outside the
     approval too
  7. OPEN, and new with the threaded shape - `config["email_sequence"]` IS
     side A of the email sequence comparison and is NOT in
     `campaigns.sending_config()`, so it can be rewritten after approval
     without moving the fingerprint:
     `test_the_email_sequence_is_not_covered_and_it_defines_side_a`

(3) was the one that hid the rest. While no email campaign could reach PASS,
every email verdict below was FAIL whatever the fixture did, so a mutation test
on that channel proved only that FAIL was still FAIL. The unmutated email
comparison is now asserted to PASS, which is what makes each email mutation
below a statement about that mutation.

(4) is now the serious one and it got worse when (3) closed: the email
comparison reaches PASS with a per-domain send cap of 500 the approved side has
no opinion about. It decides how many people at one company hear from us in a
day.

(2) was the same correction this module had already made once. `lead_set` was
added to `REQUIRED_HEYREACH` so the diff would assert WHO the provider holds
rather than how many; `REQUIRED_BISON` did not get the field for a while,
though `provider_bison` pages the full lead set and `approved_bison` builds
one. Until it did, swapping one address for another produced
`lead_set: mismatch` in the report and a verdict that never mentioned it,
because the count still agreed.

## WHAT THE FIXTURE OWES THE COMPARISON

The provider side is built FROM the approved side and then mutated once. That
is deliberate - a fixture that restates the copy by hand agrees with nobody the
day a template changes - but it has one cost, and the cost is the whole risk in
a module like this: a field the fixture copies and no test mutates is a field
being compared to itself.

So every field the fixture supplies has a mutation that must catch it, and the
two added with the threaded shape are no exception. `thread_replies` has
`test_a_follow_up_that_stopped_being_a_thread_reply`; the per-lead custom
variables have `test_a_lead_holding_copy_nobody_approved`. The invariant they
encode - ONLY THE OPENER OWNS A SUBJECT, every step referencing `{SUBJECT_1}`,
`subject_2..N` never generated - is asserted directly on the approved side by
`test_only_the_opener_carries_a_subject_variable`, so a later step regaining a
subject of its own is caught even though both sides of the diff would still
agree about it.
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

# THE STANDING EMAIL DEFECT IS CLOSED, AND THIS IS DELIBERATELY STILL HERE.
#
# It used to be `{"actions"}`: `approved_bison` named its steps with cadence
# keys (`day1`) and `provider_bison` named them with provider order (`step1`),
# `actions` is in `REQUIRED_BISON`, and the two could never be equal - so no
# email campaign could reach PASS and every email assertion below had to carry
# the standing failure alongside its own mutation.
#
# TASK-215 reconciled the naming: both sides now say `step{order}`. The set is
# empty, which is what "an email mutation fails for its own field and nothing
# else" means, and the name is kept so the day another standing defect appears
# there is one place to put it rather than nine expected sets to widen.
STANDING_EMAIL_DEFECT = frozenset()

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
            # THE THREADED SHAPE. `(False, True, True, ...)` - only the opener
            # starts a thread and every follow-up continues it, which is the
            # TASK-219 invariant. A fixture that left this off made the
            # provider look like a campaign of five unthreaded emails each
            # owning its own subject, which is the shape the invariant exists
            # to forbid.
            "thread_replies": list(approved["thread_replies"]),
            # PER-LEAD CUSTOM VARIABLES, email -> {subject_1, body_1..body_N}.
            # This is where the approval fingerprint is enforced at the
            # provider: the sequence carries placeholders and the words each
            # prospect receives travel as custom variables on the lead. A
            # fixture that served leads with no variables made every email
            # comparison fail on `lead_copy` before any mutation was reached.
            "lead_copy": {email: dict(values) for email, values
                          in (approved["_lead_copy"] or {}).items()},
            "max_emails_per_day": approved["max_emails_per_day"],
            "max_new_leads_per_day": approved["max_new_leads_per_day"],
            "per_domain_cap": 3,
        }
        held.update(mutation)
        return held

    def compare_email(self, campaign, recs, **mutation):
        held = self.held_by_bison(campaign, recs, **mutation)
        # INDEXED, NOT ZIPPED. `zip` stops at the shortest list, so a mutation
        # that lengthens `subjects`/`bodies`/`delays` without lengthening
        # `thread_replies` would have been silently truncated back to the
        # approved length and the extra step would never reach the provider
        # side at all - a fixture that makes a mutation undetectable.
        steps = []
        for i in range(len(held["subjects"])):
            threaded = held["thread_replies"][i] \
                if i < len(held["thread_replies"]) else False
            steps.append({"order": i + 1, "active": True,
                          "email_subject": held["subjects"][i],
                          "email_body": held["bodies"][i],
                          "wait_in_days": held["delays"][i],
                          "thread_reply": threaded})
        row = {"id": held["campaign_id"], "name": held["name"],
               "status": held["status"],
               "max_emails_per_day": held["max_emails_per_day"],
               "max_new_leads_per_day": held["max_new_leads_per_day"],
               "daily_max_sends_per_receiving_domain": held["per_domain_cap"]}
        base = f"/campaigns/{held['campaign_id']}"
        # `provider_bison` pages the campaign's leads for the ADDRESSES and
        # then reads each lead individually for its CUSTOM VARIABLES - the
        # campaign leads route does not carry them. A lead row with no `id` is
        # skipped by that second read, so a fixture without ids produced an
        # empty `_lead_variables` and every approved lead came back MISSING.
        lead_ids = {email: 8000 + i for i, email in enumerate(held["leads"])}
        pages = {
            base: {"data": row},
            f"{base}/sender-emails?page=1": {
                "data": [{"id": i} for i in held["sender_ids"]],
                "meta": {"total": len(held["sender_ids"])}},
            f"{base}/leads?page=1": {
                "data": [{"id": lead_ids[e], "email": e}
                         for e in held["leads"]],
                "meta": {"total": len(held["leads"])}},
            f"{base}/sequence-steps": {"data": steps},
        }
        for email, lead_id in lead_ids.items():
            values = held["lead_copy"].get(email) or {}
            pages[f"/leads/{lead_id}"] = {
                "data": {"id": lead_id, "email": email,
                         "custom_variables": [{"name": k, "value": v}
                                              for k, v in sorted(values.items())]}}

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

    def test_the_email_campaign_as_staged_passes(self):
        """THE FINDING THAT CLOSED, and it was the one that masked the others.

        `approved_bison` used to name its steps with cadence keys (`day1`) and
        `provider_bison` with provider order (`step1`), and `actions` is in
        `REQUIRED_BISON` - so no email campaign with approved copy could ever
        reach PASS. This was an `expectedFailure` for exactly that reason. The
        email half of the gate failed closed, which is the safe direction, and
        it meant the half had never once been exercised against a match: every
        email verdict below was FAIL whatever the fixture did.

        TASK-215 reconciled the naming and compared like for like - sequence
        placeholders against placeholders, declared waits against waits,
        per-lead custom variables against the approved resolved copy. So this
        is a real assertion now, and it is the control the mutations need: a
        mutation test only means something if the unmutated case passes.
        """
        campaign, recs = self.stage()
        readback = self.compare_email(campaign, recs)
        self.assertEqual(readback.verdict, configdiff.PASS, readback.failures)

    def test_and_the_email_diff_checked_enough_to_mean_something(self):
        """The same control the LinkedIn side has. A PASS from a comparison
        that examined three fields is not agreement."""
        campaign, recs = self.stage()
        readback = self.compare_email(campaign, recs)
        self.assertGreaterEqual(readback.diff["checked"], 12)
        for field in ("lead_set", "subjects", "bodies", "delays",
                      "thread_replies", "actions"):
            self.assertIn(field, readback.diff["fields"])
        # And the per-lead copy was actually read, rather than skipped because
        # the provider offered nothing to compare.
        self.assertTrue(readback.provider["_lead_variables"])
        self.assertEqual(set(readback.provider["_lead_variables"]),
                         set(readback.approved["_lead_copy"]))

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
        """Three fields, and all three are the mutation: who, how many, and
        whose approved words the provider is no longer holding. A lead the
        provider does not have has no custom variables either, and
        `lead_copy` says so by hashed address rather than by count."""
        self.check({"lead_set", "lead_count", "lead_copy"},
                   blocking={"lead_count"}, leads=[])

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
        """A sixth email nobody approved, caught on every dimension it moves.

        `thread_replies` and `actions` are in the set because they are not
        decoration: the extra step is a sixth `step{order}` the approved side
        does not name, and it opens a NEW THREAD with a subject of its own -
        the exact shape TASK-219's invariant forbids. A test that expected
        only the copy fields would pass just as readily against a provider
        that had lost the threading, which is a different defect wearing the
        same failure.
        """
        campaign, recs = self.stage()
        approved = configdiff.approved_bison(campaign, recs, self.config)
        readback = self.compare_email(
            campaign, recs,
            subjects=list(approved["subjects"]) + ["one more nobody approved"],
            bodies=list(approved["bodies"]) + ["and a body nobody approved"],
            delays=list(approved["delays"]) + [30])
        self.assert_blocks(
            readback,
            {"subjects", "bodies", "delays", "actions", "thread_replies"},
            STANDING_EMAIL_DEFECT)

    def test_a_follow_up_that_stopped_being_a_thread_reply(self):
        """ONLY THE OPENER OWNS A SUBJECT, asserted as a mutation.

        `thread_replies` and `lead_copy` are the two fields this module's
        fixture now supplies from the approved side, and a field a fixture
        supplies and nothing mutates is a field being compared to itself. This
        is the mutation for the first of them.

        A follow-up whose `thread_reply` flag is gone at the provider starts a
        NEW THREAD. It still carries `{SUBJECT_1}` in this fixture, so the
        subjects agree and the copy agrees - the flag is the whole difference,
        and `thread_replies` is the only field that can see it.
        """
        campaign, recs = self.stage()
        approved = configdiff.approved_bison(campaign, recs, self.config)
        threads = list(approved["thread_replies"])
        self.assertTrue(threads[1], "the fixture sequence is not threaded; "
                                    "this mutation has nothing to undo")
        threads[1] = False
        readback = self.compare_email(campaign, recs, thread_replies=threads)
        self.assert_blocks(readback, {"thread_replies"},
                           STANDING_EMAIL_DEFECT)

    def test_a_lead_holding_copy_nobody_approved(self):
        """The mutation for the other supplied field.

        The sequence at the provider carries PLACEHOLDERS; the words a
        prospect actually receives are custom variables on the lead. So a
        campaign can hold the approved template, the approved people and the
        approved limits, and still send something nobody blessed. Nothing in
        the sequence diff can see that - `lead_copy` is the only field that
        compares the resolved words.
        """
        campaign, recs = self.stage()
        approved = configdiff.approved_bison(campaign, recs, self.config)
        copy = {email: dict(values)
                for email, values in approved["_lead_copy"].items()}
        address = sorted(copy)[0]
        self.assertIn("body_1", copy[address], "the fixture lead carries no "
                                               "body_1 to alter")
        copy[address]["body_1"] += "\n\nps. a line nobody approved."
        readback = self.compare_email(campaign, recs, lead_copy=copy)
        # Not `assert_blocks`: `lead_copy` is not in `REQUIRED_BISON` because
        # it is not scored by `diff()` at all. `compare_bison` sets the verdict
        # to FAIL directly when a lead's variables disagree, which is stronger
        # than membership of the required tuple - there is no way to report
        # this field without failing on it. Asserted as that, rather than
        # squeezed into a helper whose last assertion would be false here.
        self.assertEqual(readback.verdict, configdiff.FAIL)
        self.assertEqual(failing(readback),
                         STANDING_EMAIL_DEFECT | {"lead_copy"})
        detail = readback.diff["fields"]["lead_copy"]["detail"]
        self.assertTrue(any("body_1" in line for line in detail), detail)
        self.assertFalse(any(address in line for line in detail),
                         "the diff logged a prospect address in clear")

    def test_only_the_opener_carries_a_subject_variable(self):
        """The invariant stated on the APPROVED side, not just diffed.

        `subject_2..N` must not exist. If a later step ever regained its own
        subject variable, `thread_replies` would still agree and the copy
        would still agree - the fixture would simply carry one more variable
        on both sides and nothing here would notice. This is the assertion
        that notices.
        """
        campaign, recs = self.stage()
        approved = configdiff.approved_bison(campaign, recs, self.config)
        self.assertEqual(approved["thread_replies"][0], False,
                         "the opener must start the thread")
        self.assertTrue(all(approved["thread_replies"][1:]),
                        "every follow-up must continue the opener's thread")
        self.assertEqual(set(approved["subjects"]), {"{SUBJECT_1}"},
                         "every step must reference the opener's subject")
        for address, values in approved["_lead_copy"].items():
            extra = {k for k in values if k.startswith("subject_")
                     and k != "subject_1"}
            self.assertEqual(extra, set(), "a follow-up owns a subject "
                                           "variable of its own")
            self.assertIn("subject_1", values)

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

    def test_an_email_campaign_with_no_approved_copy_is_refused(self):
        """THE SERIOUS ONE, AND IT IS CLOSED. Kept as an assertion, not
        deleted, because it is the defect this whole module exists to prevent.

        `approved_bison` used to run `leads.add(address)` BEFORE it filtered on
        approval, so every emailable contact was in the approved lead set
        whether or not one word of theirs had been blessed. With no approved
        step the approved copy was empty, and a provider campaign holding those
        leads with no active sequence step matched it exactly - so the gate
        whose entire purpose is "the provider holds what was approved"
        certified a campaign against an approval that did not exist.
        `approved_heyreach` had refused this by name from the start; the email
        side had no equivalent.

        It refuses now, and it refuses rather than merely FAILING, which is the
        stronger answer: `DiffRefused` means the question could not be asked,
        and `executionguard` cannot mistake it for a comparison that ran. A
        FAIL verdict would have been enough to block, but it would also have
        claimed a diff had been performed against an approval that is not there.
        """
        campaign, recs = self.stage(approve_email=False, approve_linkedin=True)
        with self.assertRaises(configdiff.DiffRefused) as caught:
            self.compare_email(campaign, recs, subjects=[], bodies=[],
                               delays=[])
        self.assertIn("approved", str(caught.exception))
        # And the refusal is about the APPROVAL, not about the campaign row -
        # the SAME campaign and the SAME records compare fine the moment the
        # copy is approved. Asserted because "it refused" is only interesting
        # if the thing it refused could otherwise have been compared.
        self.approve_drafts(recs)
        store.save(recs)
        recs = store.load()
        self.assertEqual(self.compare_email(campaign, recs).verdict,
                         configdiff.PASS)

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

        THIS BECAME THE SERIOUS ONE when the `actions` naming was reconciled.
        While `compare_bison` could never reach PASS, a campaign with a cap
        nobody approved was blocked anyway, for an unrelated reason. It reaches
        PASS now, so a per-domain send cap of 500 on an approved campaign is
        certified by the gate.

        Still asserted as a CHANGE to the failing set rather than as a FAIL
        verdict, so that the day the cap IS scored this reports an unexpected
        success naming the cap, rather than being satisfiable by any other
        field that happens to fail alongside it.
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

    def test_the_email_sequence_is_not_covered_and_it_defines_side_a(self):
        """A FINDING, and it is a different shape from the four above.

        `approved_bison` builds the expected SEQUENCE - the subjects, the
        bodies, the declared waits and the thread-reply pattern - by calling
        `bisonfactory._sequence_steps(config["email_sequence"], ...)`. That
        block is side A of the email half of this gate.

        `campaigns.sending_config()` reads six keys and `email_sequence` is not
        one of them. So editing the sequence after approval moves WHAT THE GATE
        EXPECTS, in the same direction and by the same amount as the provider
        would have to move to keep agreeing with it, while the approval stays
        current and the fingerprint does not budge.

        The other four findings here are fields outside the comparison. This
        one is a field that defines the comparison and is still outside the
        approval, which is worse: the two halves of "no activation without an
        exact match" are supposed to be independent, and here one of them can
        be rewritten without disturbing the other.

        Asserted as the behaviour that HOLDS today rather than as an
        `expectedFailure`, so it turns over loudly the day `sending_config()`
        is given the key.
        """
        campaign, recs = self.stage()
        before = self.fingerprints(campaign, recs)
        altered = dict(self.config)
        sequence = {k: dict(v) for k, v
                    in (self.config["email_sequence"]["steps"]).items()}
        sequence["day1"]["body"] = "<p>{BODY_1}</p><p>and a line nobody blessed</p>"
        altered["email_sequence"] = dict(self.config["email_sequence"],
                                         steps=sequence)
        self.assertEqual(
            self.fingerprints(campaign, recs, altered), before,
            "the email sequence is covered by the approval now - delete this "
            "test and say so in the module docstring")
        # And the edit really does move the side the gate compares against.
        self.assertNotEqual(
            configdiff.approved_bison(campaign, recs, altered)["bodies"],
            configdiff.approved_bison(campaign, recs, self.config)["bodies"],
            "the sequence edit changed nothing, so this proves nothing")


class NoActivationOnAnythingLessThanAnExactMatch(Factory):
    """The diff's verdict has to actually stop the write, not merely exist."""

    def test_activation_names_exactly_one_campaign_on_each_channel(self):
        """THE STRONGER STATEMENT THAT REPLACED "ACTIVATION IS IMPOSSIBLE".

        This used to assert that `LINKEDIN_ACTIVATE` and `EMAIL_ACTIVATE` were
        both unsupported, which was the outermost reason no mutation in this
        module could reach a prospect. On 2026-09-16 the operator authorized
        both, each SCOPED TO ONE CAMPAIGN - see
        `OPERATOR-AUTHORIZATION-2026-09-16.md`.

        Deleting the assertion would have quietly dropped the guarantee.
        Membership of `SUPPORTED` alone is a CHANNEL-WIDE LICENCE: on email it
        would admit campaign 481, which holds people already written to under
        a sequence nobody approved here; on LinkedIn it would admit the
        client's own in-progress campaigns. So what is asserted is the scope:
        the verb is enabled, the condition exists, and the condition refuses
        every campaign but the named one - including the right provider
        campaign offered under the wrong canonical row, which is how a send
        reaches a campaign nobody approved.
        """
        for operation in (providerwrites.LINKEDIN_ACTIVATE,
                          providerwrites.EMAIL_ACTIVATE):
            self.assertTrue(providerwrites.is_supported(operation))
            self.assertTrue(
                providerwrites.is_conditional(operation),
                f"{operation} is supported and unconditional, which is a "
                f"licence over every campaign on the channel")

    def test_email_activation_refuses_every_campaign_but_the_authorized_one(self):
        """RE-SCOPED to the v3 rebuild, and the provider slot is UNPINNED.

        485 must not be activated - its sequence violates the threading
        invariant and `set_sequence` appends, so it cannot be corrected - and
        the replacement's provider id does not exist until the provider assigns
        it. `_AUTHORIZED_EMAIL_CAMPAIGN` therefore carries None in the provider
        slot, meaning "resolve it from `bison_campaign_id` on the named row".

        The binding check is PRESERVED, not dropped, which is what this asserts:
        the canonical row must be the named one, the row must actually be bound,
        and the provider id must be the one it is bound to. An unbound row
        authorizes nothing at all - the fail-closed case that matters, because
        it is the state the row is in before the campaign exists.
        """
        require = providerwrites.require_conditional_permission
        want_provider, want_canonical = providerwrites._AUTHORIZED_EMAIL_CAMPAIGN
        self.assertIsNone(want_provider)

        # A row that is not the named one is refused whatever it names.
        for provider_id in ("481", "485", "9999", None):
            with self.assertRaises(providerwrites.WriteRefused):
                require(providerwrites.EMAIL_ACTIVATE, provider_id,
                        "productive-email-control-v2")
            with self.assertRaises(providerwrites.WriteRefused):
                require(providerwrites.EMAIL_ACTIVATE, provider_id, None)

        # The named row, but unbound: nothing to check against, so nothing is
        # permitted. This is the state before the campaign is created.
        with mock.patch.object(campaigns, "get",
                               return_value={"campaign_id": want_canonical}):
            with self.assertRaises(providerwrites.WriteRefused) as caught:
                require(providerwrites.EMAIL_ACTIVATE, "485", want_canonical)
            self.assertIn("bison_campaign_id", str(caught.exception))

        # The named row, bound: that provider campaign and no other.
        bound = {"campaign_id": want_canonical, "bison_campaign_id": 4242}
        with mock.patch.object(campaigns, "get",
                               return_value=bound):
            self.assertTrue(require(providerwrites.EMAIL_ACTIVATE, "4242",
                                    want_canonical))
            for other in ("485", "481", "424", "42420", "", None):
                with self.assertRaises(providerwrites.WriteRefused):
                    require(providerwrites.EMAIL_ACTIVATE, other,
                            want_canonical)

    def test_linkedin_activation_refuses_every_campaign_but_the_canary(self):
        require = providerwrites.require_conditional_permission
        with self.assertRaises(providerwrites.WriteRefused):
            require(providerwrites.LINKEDIN_ACTIVATE, HEYREACH_CAMPAIGN, None)
        with self.assertRaises(providerwrites.WriteRefused):
            require(providerwrites.LINKEDIN_ACTIVATE, "599020", None)
        # RE-SCOPED 2026-09-16: the operator's grant moved from 604869 to
        # 605487, and the condition moved with it. 604869 is asserted REFUSED
        # rather than dropped - its bound list holds one contact whose account
        # `collision.account_policy` holds, so it must not start.
        for other in ("604869", "605487"):
            with self.assertRaises(providerwrites.WriteRefused):
                require(providerwrites.LINKEDIN_ACTIVATE, other, None)
        self.assertTrue(require(providerwrites.LINKEDIN_ACTIVATE, "605732",
                                None))

    def test_the_campaign_under_test_here_could_never_be_activated(self):
        """The property the old assertion actually carried, kept.

        Every campaign in this module is the fictional demo one, and neither
        channel's condition names it. So no mutation here can reach a
        prospect even if every gate below it were removed.
        """
        require = providerwrites.require_conditional_permission
        campaign, _recs = self.stage()
        with self.assertRaises(providerwrites.WriteRefused):
            require(providerwrites.EMAIL_ACTIVATE, BISON_CAMPAIGN,
                    campaign["campaign_id"])
        with self.assertRaises(providerwrites.WriteRefused):
            require(providerwrites.LINKEDIN_ACTIVATE, HEYREACH_CAMPAIGN,
                    campaign["campaign_id"])

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
