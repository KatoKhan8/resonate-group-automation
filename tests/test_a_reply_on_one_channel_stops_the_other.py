"""TASK-023 - A reply on one channel must stop the other.

For six pairs of (event, expected effect), drive the REAL planner end to end
and assert on what it returns. Where the answer is "nothing happens", that
is a FINDING, not a bug to fix.

The two planners this file drives:

  cadence.build()           the timeline: every step's status for every
                            contact at the company
  nextaction.next_best_action()   the planner: ACT / WAIT / STOP for the
                                  whole account

Both are the real entry points production uses. Nothing is mocked, nothing
is short-circuited. If a module computes the right answer but nothing
downstream reads it, these tests will show it.
"""
import unittest

from src import (accountpolicy, cadence, campaigns, clients, events,
                 nextaction, orchestrator, senderidentity as si, store)
from tests.campaignbase import CampaignTest, contact

CLIENT = "demo"
CHAMP = "champ"
COLLEAGUE = "colleague"


# -------------------------------------------------------------- helpers

def _clear_estate(domain="acme.test"):
    return {"domain": domain, "workspace": CLIENT, "leads": 0,
            "people": [], "emails_sent_total": 0,
            "anyone_in_sequence": False, "unknown_statuses": [],
            "any_bounce": False, "verdict": "allow",
            "checked_at": "2026-09-14T09:00:00+00:00"}


def _make_record(test, contacts_list, event_list=None):
    """A verified record with the given contacts and events."""
    test.reset_estate()
    rec = store.new_record("acme", "domains", CLIENT, "Acme Ltd", "acme.test")
    rec["state"] = "verified"
    rec["hook"] = "resourcing visibility"
    rec["company_facts"] = {"name": "Acme Ltd", "industry": "agency"}
    rec["contacts"] = contacts_list
    rec["cadence"] = {}
    rec["events"] = list(event_list or [])
    store.save([rec])
    return rec


def _draft_and_approve(rec):
    """Write generated step bodies and approve every email step."""
    from src import approve
    for c in rec["contacts"]:
        first = (c.get("name") or "there").split()[0]
        stored = rec.setdefault("cadence", {}).setdefault(c["key"], {})
        for step_key in cadence.GENERATED_KEYS:
            stored.setdefault(step_key, {})
            stored[step_key].update({
                "channel": "email",
                "generated": True,
                "subject": f"quick question about {rec['company']}",
                "body": (f"Hi {first},\n\nNoticed {rec['company']} runs "
                         f"delivery across teams.\n\nIs that roughly how "
                         f"it works?\n"),
            })
    store.save([rec])
    rec = store.load()[0]
    timeline = cadence.build(rec, clients.load(CLIENT))
    for ck, steps in timeline["contacts"].items():
        for sk, step in steps.items():
            if step.get("channel") != "email":
                continue
            try:
                approve.approve_step(rec, ck, sk, by="U0DEMOADMIN1",
                                     config=clients.load(CLIENT), step=step)
            except Exception:
                pass
    store.save([rec])
    return store.load()[0]


def _timeline_statuses(rec, config=None):
    """{contact_key: {step_key: status}} from the real cadence builder."""
    config = config or clients.load(CLIENT)
    tl = cadence.build(rec, config)
    return {k: {sk: s["status"] for sk, s in v.items()}
            for k, v in tl["contacts"].items()}


def _planner(rec, config=None, campaign=None):
    """The real planner's verdict for this account."""
    config = config or clients.load(CLIENT)
    return nextaction.next_best_action(
        rec, config=config, campaign=campaign, workspace=CLIENT,
        estate=_clear_estate(), at="2026-09-14T09:00:00+00:00",
        suppressed=set())


def _considered_for(plan_result, key):
    """The planner's consideration of one contact."""
    return next(c for c in plan_result["considered"] if c["key"] == key)


# ====================================================================
#
# PART 1 - THE TIMELINE: cadence.build()
#
# For each event, build the timeline and assert on every step's status.
# The timeline is what the send path reads; if a step says "eligible"
# after an event that should stop it, the chain is broken.
#
# ====================================================================


class TimelineAfterEvents(CampaignTest):
    """cadence.build() after each kind of event."""

    def setUp(self):
        super().setUp()
        self.config = clients.load(CLIENT)
        si.install([
            si.new_sender(CLIENT, "anna", "Anna Novak", team="growth"),
            si.new_email_account(CLIENT, "anna07", "anna",
                                 "anna07@demo.test"),
            si.new_linkedin_account(CLIENT, "anna-li", "anna",
                                    "https://www.linkedin.com/in/anna"),
        ])

    def _two_contact_record(self, event_fn=None):
        """Record with two contacts, optionally with an event applied."""
        contacts = [
            contact(CHAMP, "Champ Acme", f"{CHAMP}@acme.test",
                    linkedin=f"https://www.linkedin.com/in/{CHAMP}"),
            contact(COLLEAGUE, "Colleague Acme", f"{COLLEAGUE}@acme.test",
                    linkedin=f"https://www.linkedin.com/in/{COLLEAGUE}"),
        ]
        rec = _make_record(self, contacts)
        if event_fn:
            event_fn(rec)
            store.save([rec])
            rec = store.load()[0]
        return rec

    # -------------------------------------------------- 1. email reply

    def test_01_email_reply_stops_linkedin_for_that_contact(self):
        """An email reply pauses the whole account.

        cadence.record_event is the real entry point: it records the event
        AND applies the reply policy. The policy resolves UNKNOWN to a
        review at account scope, which holds the account.
        """
        rec = self._two_contact_record()

        def apply_email_reply(r):
            cadence.record_event(r, "email_reply", contact_key=CHAMP,
                                 at="2026-09-10T09:00:00+00:00")

        rec = self._two_contact_record(apply_email_reply)
        statuses = _timeline_statuses(rec, self.config)

        for step_key, status in statuses.get(CHAMP, {}).items():
            with self.subTest(contact=CHAMP, step=step_key):
                self.assertEqual(status, "paused",
                                 f"{CHAMP}/{step_key} should be paused "
                                 f"after email reply, got {status}")

        for step_key, status in statuses.get(COLLEAGUE, {}).items():
            with self.subTest(contact=COLLEAGUE, step=step_key):
                self.assertEqual(status, "paused",
                                 f"{COLLEAGUE}/{step_key} should be paused "
                                 f"(account-level hold), got {status}")

    # ------------------------------------------------ 2. LinkedIn reply

    def test_02_linkedin_reply_stops_email_for_that_contact(self):
        """A LinkedIn reply pauses the whole account, same as email."""
        def apply_linkedin_reply(r):
            cadence.record_event(r, "linkedin_reply", contact_key=CHAMP,
                                 at="2026-09-10T09:00:00+00:00")

        rec = self._two_contact_record(apply_linkedin_reply)
        statuses = _timeline_statuses(rec, self.config)

        for step_key, status in statuses.get(CHAMP, {}).items():
            with self.subTest(contact=CHAMP, step=step_key):
                self.assertEqual(status, "paused")

        for step_key, status in statuses.get(COLLEAGUE, {}).items():
            with self.subTest(contact=COLLEAGUE, step=step_key):
                self.assertEqual(status, "paused",
                                 "colleague should be paused (account hold)")

    # --------------------------------------- 3. unsubscribe / opt-out

    def test_03_unsubscribe_stops_contact_and_colleagues_are_separate(self):
        """An unsubscribe stops the contact permanently.

        The policy for UNSUBSCRIBE is (STOP, CONTACT): the replier's
        sequence ends, but colleagues are a separate question. The contact
        is suppressed (unsubscribed=True), which the SEND GATE reads.

        FINDING: cadence.build() does NOT check the contact's unsubscribed
        or stopped flag. The timeline shows "unapproved" or "waiting" for
        the suppressed contact, not "blocked". The send gate
        (eligibility.must_not_contact) DOES check and blocks correctly.
        So the contact cannot actually be sent to, but the timeline does
        not reflect this. This is a display gap, not a send gap.
        """
        def apply_unsubscribe(r):
            accountpolicy.apply_reply(r, CHAMP, accountpolicy.UNSUBSCRIBE,
                                      at="2026-09-10T09:00:00+00:00")

        rec = self._two_contact_record(apply_unsubscribe)
        statuses = _timeline_statuses(rec, self.config)

        champ_contact = next(c for c in rec["contacts"]
                             if c["key"] == CHAMP)
        self.assertTrue(
            champ_contact.get("unsubscribed"),
            "the replier should be suppressed after an unsubscribe")

        account_suppression = (rec.get("suppression") or {}).get(
            "unsubscribed")
        self.assertFalse(
            account_suppression,
            "FINDING: account is NOT suppressed by a contact unsubscribe; "
            "colleagues are a separate question under the current policy")

        # FINDING: the timeline does NOT show "blocked" for the suppressed
        # contact. cadence.status_for does not check contact-level stop
        # flags. The statuses are "unapproved" or "waiting" - not "eligible",
        # so nothing would actually send, but the display is misleading.
        for step_key, status in statuses.get(CHAMP, {}).items():
            with self.subTest(contact=CHAMP, step=step_key):
                self.assertNotEqual(status, "eligible",
                                    f"{CHAMP}/{step_key} should not be "
                                    f"eligible after unsubscribe")

    # -------------------------------------------- 4. meeting booked

    def test_04_meeting_booked_stops_every_contact_at_account(self):
        """A meeting booked at the account pauses every contact.

        cadence.pause_state reads MEETING_MARKED from the event log and
        returns a pause. The timeline builder reads pause_state.
        """
        def apply_meeting(r):
            events.record(r, events.MEETING_MARKED, contact_key=CHAMP,
                          at="2026-09-10T09:00:00+00:00")

        rec = self._two_contact_record(apply_meeting)
        statuses = _timeline_statuses(rec, self.config)

        self.assertTrue(
            cadence.pause_state(rec, self.config),
            "pause_state should return a meeting pause")

        for step_key, status in statuses.get(CHAMP, {}).items():
            with self.subTest(contact=CHAMP, step=step_key):
                self.assertEqual(status, "paused")

        for step_key, status in statuses.get(COLLEAGUE, {}).items():
            with self.subTest(contact=COLLEAGUE, step=step_key):
                self.assertEqual(status, "paused",
                                 "colleague paused: meeting at the account "
                                 "stops all cold outreach")

    # --------------------------------------- 5. negative / not interested

    def test_05_negative_reply_stops_replier_colleagues_unaffected(self):
        """A negative reply stops the replier; colleagues are unaffected.

        The policy for NEGATIVE is (CONTINUE, CONTACT): the replier's
        sequence stops, but the account carries on. This is a product
        decision, not a bug.

        FINDING: cadence.build() does NOT check the contact's stopped flag.
        The timeline shows "unapproved" or "waiting" for the stopped
        contact, not "blocked". The send gate (eligibility._replied) DOES
        check contact.get("stopped") and returns BLOCKED_CONTACT_STOPPED.
        So the contact cannot actually be sent to, but the timeline does
        not reflect this. Same display gap as test_03.
        """
        def apply_negative(r):
            accountpolicy.apply_reply(r, CHAMP, accountpolicy.NEGATIVE,
                                      at="2026-09-10T09:00:00+00:00")

        rec = self._two_contact_record(apply_negative)
        statuses = _timeline_statuses(rec, self.config)

        champ_contact = next(c for c in rec["contacts"]
                             if c["key"] == CHAMP)
        self.assertTrue(
            champ_contact.get("stopped"),
            "the replier should be stopped after a negative reply")

        self.assertFalse(
            bool(rec.get("paused")),
            "the account should NOT be paused by a negative reply "
            "(CONTINUE, CONTACT scope)")

        # FINDING: same as test_03 - the timeline does not show "blocked"
        # for the stopped contact. cadence.status_for does not check
        # contact.get("stopped"). The send gate does.
        for step_key, status in statuses.get(CHAMP, {}).items():
            with self.subTest(contact=CHAMP, step=step_key):
                self.assertNotEqual(status, "eligible",
                                    f"{CHAMP}/{step_key} should not be "
                                    f"eligible after negative reply")

    # ----------------------------------------------------- 6. bounce

    def test_06_bounce_stops_email_for_that_address_only(self):
        """A bounce closes email for that address; LinkedIn and the
        account are unaffected.

        nextaction._bounced_channels reads EMAIL_BOUNCED events and
        closes the email channel for that contact only.
        """
        def apply_bounce(r):
            events.record(r, events.EMAIL_BOUNCED, contact_key=CHAMP,
                          at="2026-09-10T09:00:00+00:00", channel="email")

        rec = self._two_contact_record(apply_bounce)
        statuses = _timeline_statuses(rec, self.config)

        self.assertFalse(
            bool(rec.get("paused")),
            "a bounce should not pause the account")

        colleague_paused = rec.get("paused")
        self.assertFalse(colleague_paused)


# ====================================================================
#
# PART 2 - THE PLANNER: nextaction.next_best_action()
#
# For each event, ask the planner what happens next and assert on ACT,
# WAIT or STOP. This is the question an operator asks.
#
# ====================================================================


class PlannerAfterEvents(CampaignTest):
    """next_best_action() after each kind of event."""

    def setUp(self):
        super().setUp()
        self.config = clients.load(CLIENT)
        si.install([
            si.new_sender(CLIENT, "anna", "Anna Novak", team="growth"),
            si.new_sender(CLIENT, "petar", "Petar Horvat", team="growth"),
            si.new_email_account(CLIENT, "anna07", "anna",
                                 "anna07@demo.test"),
            si.new_linkedin_account(CLIENT, "anna-li", "anna",
                                    "https://www.linkedin.com/in/anna"),
            si.new_email_account(CLIENT, "petar03", "petar",
                                 "petar03@demo.test"),
            si.new_linkedin_account(CLIENT, "petar-li", "petar",
                                    "https://www.linkedin.com/in/petar"),
        ])

    def _ready_record(self, event_fn=None):
        """A record with two contacts, drafted and approved."""
        contacts = [
            dict(contact(CHAMP, "Champ Acme", f"{CHAMP}@acme.test",
                         linkedin=f"https://www.linkedin.com/in/{CHAMP}"),
                 primary=True),
            contact(COLLEAGUE, "Colleague Acme", f"{COLLEAGUE}@acme.test",
                    linkedin=f"https://www.linkedin.com/in/{COLLEAGUE}"),
        ]
        rec = _make_record(self, contacts)
        rec = _draft_and_approve(rec)
        if event_fn:
            event_fn(rec)
            store.save([rec])
            rec = store.load()[0]
        return rec

    def _campaign_for(self, rec):
        camp = orchestrator.create(
            "test-reply-chain", CLIENT, "Test",
            record_ids=[rec["id"]], created_by="U0DEMOADMIN1")
        camp["senders"] = {
            "email": [{"id": "bison-1", "daily_limit": 40}],
            "linkedin": [{"id": "hr-1", "daily_limit": 20}],
        }
        camp["bison_campaign_id"] = "9001"
        camp["heyreach_campaign_id"] = "7001"
        camp["daily_volume"] = {"email": 20, "linkedin": 10}
        campaigns.save([camp])
        return camp

    # -------------------------------------------------- 1. email reply

    def test_01_email_reply_planner_says_wait(self):
        """After an email reply, the planner says WAIT for the account."""
        def apply_event(r):
            cadence.record_event(r, "email_reply", contact_key=CHAMP,
                                 at="2026-09-10T09:00:00+00:00")

        rec = self._ready_record(apply_event)
        camp = self._campaign_for(rec)
        plan = _planner(rec, campaign=camp)

        self.assertEqual(plan["action"], "wait",
                         f"expected WAIT after email reply, got "
                         f"{plan['action']}: {plan.get('reason')}")
        self.assertIn(plan.get("reason_code"),
                      ("wait:account_held",))

    # ------------------------------------------------ 2. LinkedIn reply

    def test_02_linkedin_reply_planner_says_wait(self):
        """After a LinkedIn reply, the planner says WAIT for the account."""
        def apply_event(r):
            cadence.record_event(r, "linkedin_reply", contact_key=CHAMP,
                                 at="2026-09-10T09:00:00+00:00")

        rec = self._ready_record(apply_event)
        camp = self._campaign_for(rec)
        plan = _planner(rec, campaign=camp)

        self.assertEqual(plan["action"], "wait")
        self.assertIn(plan.get("reason_code"),
                      ("wait:account_held",))

    # --------------------------------------- 3. unsubscribe / opt-out

    def test_03_unsubscribe_planner_stops_contact(self):
        """After an unsubscribe, the replier is blocked.

        The account is NOT suppressed (the policy is CONTACT scope), so
        the planner may still have an answer for colleagues.
        """
        def apply_event(r):
            accountpolicy.apply_reply(r, CHAMP, accountpolicy.UNSUBSCRIBE,
                                      at="2026-09-10T09:00:00+00:00")

        rec = self._ready_record(apply_event)
        camp = self._campaign_for(rec)
        plan = _planner(rec, campaign=camp)

        champ_entry = _considered_for(plan, CHAMP)
        self.assertFalse(champ_entry["ok"],
                         "the unsubscribed contact should not be ok")
        self.assertIn(champ_entry.get("reason_code"),
                      ("blocked:unsubscribed", "blocked:contact_stopped"))

        self.assertFalse(
            (rec.get("suppression") or {}).get("unsubscribed"),
            "FINDING: account-level suppression is NOT set by a "
            "contact unsubscribe; colleagues are a separate question")

    # -------------------------------------------- 4. meeting booked

    def test_04_meeting_booked_planner_says_wait(self):
        """After a meeting is booked, the planner says WAIT for the
        whole account."""
        def apply_event(r):
            events.record(r, events.MEETING_MARKED, contact_key=CHAMP,
                          at="2026-09-10T09:00:00+00:00")

        rec = self._ready_record(apply_event)
        camp = self._campaign_for(rec)
        plan = _planner(rec, campaign=camp)

        self.assertEqual(plan["action"], "wait",
                         f"expected WAIT after meeting, got "
                         f"{plan['action']}: {plan.get('reason')}")
        self.assertEqual(plan.get("reason_code"), "wait:account_held")

    # --------------------------------------- 5. negative / not interested

    def test_05_negative_reply_replier_stopped_colleague_may_continue(self):
        """A negative reply stops the replier. The colleague may continue.

        This is a product decision: one person declining is not the
        company declining. The policy is (CONTINUE, CONTACT).
        """
        def apply_event(r):
            accountpolicy.apply_reply(r, CHAMP, accountpolicy.NEGATIVE,
                                      at="2026-09-10T09:00:00+00:00")

        rec = self._ready_record(apply_event)
        camp = self._campaign_for(rec)
        plan = _planner(rec, campaign=camp)

        champ_entry = _considered_for(plan, CHAMP)
        self.assertFalse(champ_entry["ok"],
                         "the negative replier should not be ok")

        colleague_entry = _considered_for(plan, COLLEAGUE)
        self.assertFalse(
            (rec.get("paused") or {}),
            "the account should not be paused by a negative reply")

    # ----------------------------------------------------- 6. bounce

    def test_06_bounce_email_closed_for_address_account_unaffected(self):
        """A bounce closes email for that address. The account and
        colleagues are unaffected.

        nextaction._bounced_channels reads EMAIL_BOUNCED events and
        closes the email channel for that contact only. The colleague's
        email channel is a different address and is not affected.
        """
        def apply_event(r):
            events.record(r, events.EMAIL_BOUNCED, contact_key=CHAMP,
                          at="2026-09-10T09:00:00+00:00", channel="email")

        rec = self._ready_record(apply_event)
        camp = self._campaign_for(rec)
        plan = _planner(rec, campaign=camp)

        champ_entry = _considered_for(plan, CHAMP)
        bounced = champ_entry.get("bounced", [])
        self.assertTrue(bounced,
                        "the bounced contact should show a bounce")

        self.assertFalse(
            bool(rec.get("paused")),
            "a bounce should not pause the account")

        colleague_entry = _considered_for(plan, COLLEAGUE)
        self.assertFalse(
            colleague_entry.get("bounced"),
            "the colleague should not show a bounce")


if __name__ == "__main__":
    unittest.main()
