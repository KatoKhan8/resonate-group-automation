"""Fifteen ways the lifecycle could go wrong between one step and the next.

`test_campaign_e2e` walks the path when everything behaves. This walks it
while something changes underneath - which is the only interesting case,
because every one of these is a state that arrives *after* a decision was
made and *before* the thing that decision authorised actually happens.

The shape they share: a campaign is approved on Monday, and on Thursday a
step goes out. Between those two moments a reply can arrive, somebody can
ask to be removed, a sender can leave, a fact can age, a person can change
jobs. If any of those is read at approval time and not again at send time,
the system sends something it would refuse to send if asked.

Each test is named for the failure it prevents rather than the function it
calls, because the failure is what somebody will be looking for.
"""
import unittest

from src import (accountpolicy as ap, approve, cadence, campaigns,
                 eligibility as E, events, evidence, inbound, orchestrator,
                 push, replies, store, tagsync, touch)
from tests.campaignbase import CLIENT, CampaignTest, contact

ADMIN = "U0DEMOADMIN1"
NL = chr(10)


class Attack(CampaignTest):
    """One approved campaign, then something changes."""

    def setUp(self):
        super().setUp()
        self.posted = []

    def post(self, payload, config=None):
        """A Slack workspace that accepts everything, so the flow can be
        watched. `inbound.ingest` needs one; without it the notification
        layer is what the test is measuring rather than the thing under it.
        """
        self.posted.append(payload)
        return {"ok": True, "ts": "171000." + str(len(self.posted))}

    def ready(self, mx_hosts=None):
        from src import mx

        recs = self.seed_records()
        rec = recs[0]
        rec["contacts"] = [contact("acme-champ", "Champ", "champ@acme.test")]
        rec["contacts"][0]["mx"] = mx.decide(
            mx_hosts or ["aspmx.l.google.com"], mx.settings(self.config),
            domain="acme.test")
        self.draft_everything(recs)
        self.approve_drafts(recs)
        store.save(recs)
        return rec, store.load()

    def decide(self, rec, recs, step="day1", **kw):
        return E.decide(rec, rec["contacts"][0], step, recs=recs,
                        config=self.config, **kw)

    def assert_eligible(self, rec, recs, why=""):
        decision = self.decide(rec, recs)
        self.assertTrue(decision.eligible, f"{why}: {decision['reasons']}")

    def assert_stopped(self, rec, recs, reason=None):
        decision = self.decide(rec, recs)
        self.assertFalse(decision.eligible, decision["reasons"])
        if reason:
            self.assertIn(reason, decision["reasons"])
        return decision


class ADecisionMadeEarlierIsNotReusedLater(Attack):

    def test_a_removal_request_after_approval_blocks_the_payload(self):
        """A. The draft is approved and unchanged. The person is not."""
        rec, recs = self.ready()
        self.assert_eligible(rec, recs, "before the removal request")

        rec["contacts"][0]["unsubscribed"] = True
        self.assert_stopped(rec, recs, E.BLOCKED_UNSUBSCRIBED)

    def test_the_payload_builder_refuses_it_too(self):
        """The gate is asked again where the payload is built, so a caller
        that assembled an item by hand still meets it."""
        rec, recs = self.ready()
        rec["contacts"][0]["unsubscribed"] = True
        item = {"record": rec, "contact": rec["contacts"][0],
                "contact_key": "acme-champ", "step_key": "day1",
                "channel": "email", "push_id": "acme:acme-champ:day1:email",
                "step": cadence.build(rec, self.config, recs=recs)
                ["contacts"]["acme-champ"]["day1"]}
        with self.assertRaises(AssertionError):
            push.verify_before_payload(item, recs=recs, config=self.config)

    def test_a_reply_between_step_one_and_step_two_stops_step_two(self):
        """B. The reply is the whole point of a cadence, and the thing most
        likely to arrive between two steps."""
        rec, recs = self.ready()
        rec.setdefault("events", []).append({
            "type": events.REPLY_RECEIVED, "contact": "acme-champ",
            "channel": "email", "at": "2026-08-20T09:00:00+00:00"})
        rec["paused"] = {"since": "2026-08-20T09:00:00+00:00",
                         "reason": "reply_received"}
        store.save([rec])
        decision = self.assert_stopped(rec, store.load())
        # Either code is right and both are more specific than "no": the
        # contact replied, and the company is paused because they did.
        self.assertTrue(
            {E.BLOCKED_REPLIED, E.BLOCKED_COMPANY_PAUSED}
            & set(decision["reasons"]), decision["reasons"])

    def test_a_reply_from_one_person_holds_the_other_decision_maker(self):
        """C. The account is the unit. Somebody answering is a fact about
        the company, not about one mailbox - so the colleague who has heard
        nothing stops too.

        The buyer is asserted eligible first. Without that this passes on a
        record where the buyer was never eligible for some other reason.
        """
        from src import mx

        recs = self.seed_records()
        rec = recs[0]
        rec["contacts"] = [
            contact("acme-champ", "Champ", "champ@acme.test"),
            contact("acme-buyer", "Buyer", "buyer@acme.test")]
        for person in rec["contacts"]:
            person["mx"] = mx.decide(["aspmx.l.google.com"],
                                     mx.settings(self.config),
                                     domain="acme.test")
        self.draft_everything(recs)
        self.approve_drafts(recs)
        store.save(recs)
        recs = store.load()

        before = E.decide(recs[0], recs[0]["contacts"][1], "day1",
                          recs=recs, config=self.config)
        self.assertTrue(before.eligible, before["reasons"])

        recs[0]["paused"] = {"since": "2026-08-20T09:00:00+00:00",
                             "reason": "reply_received"}
        store.save(recs)
        recs = store.load()
        decision = E.decide(recs[0], recs[0]["contacts"][1], "day1",
                            recs=recs, config=self.config)
        self.assertFalse(decision.eligible)
        self.assertIn(E.BLOCKED_COMPANY_PAUSED, decision["reasons"])

    def test_evidence_that_aged_out_between_approval_and_send_holds_it(self):
        """E. The approval is still valid - the words did not change - and
        the fact behind them is no longer current enough to write from."""
        rec, recs = self.ready()
        fact = evidence.make(
            "Acme opened a Vienna delivery office and is hiring four "
            "implementation managers.",
            "https://acme.test/news", "news", "apify", rec["id"],
            published_at="2019-01-01", subject=evidence.COMPANY,
            persona="champion",
            angle_words=["utilisation", "capacity", "delivery"],
            today="2019-01-05")
        rec["research"] = [fact]
        rec["contacts"][0]["personalization"] = {
            "selected_evidence_ids": [fact["evidence_id"]]}
        store.save([rec])
        self.assert_stopped(rec, store.load(), E.HELD_EVIDENCE_AGED_OUT)


class AReplyOnOneChannelStopsTheOther(Attack):
    """The invariant the whole multichannel design rests on.

    A reply arrives on LinkedIn. The email sequence is what has to stop -
    and the email sequence is the one whose payload is about to be built,
    by a different module, from state computed before the reply landed.
    Asserting it on the reply handler proves the handler; asserting it here
    proves the thing that would actually send.

    Tested in both directions because the failure is asymmetric in
    practice: LinkedIn replies arrive through a poller nobody has
    live-validated, and email is the channel with a payload builder.
    """

    def payload_item(self, rec, recs, channel="email", step="day1"):
        return {"record": rec, "contact": rec["contacts"][0],
                "contact_key": "acme-champ", "step_key": step,
                "channel": channel,
                "push_id": f"acme:acme-champ:{step}:{channel}",
                "step": cadence.build(rec, self.config, recs=recs)
                ["contacts"]["acme-champ"][step]}

    def reply_on(self, rec, channel, at="2026-08-20T09:00:00+00:00"):
        """A reply exactly as `events.apply` records one: the receipt, and
        the company hold it causes. Recording only the receipt would test a
        state this system never actually reaches."""
        rec.setdefault("events", []).append({
            "type": events.REPLY_RECEIVED, "contact": "acme-champ",
            "channel": channel, "at": at})
        rec["paused"] = {"since": at, "reason": "reply_received"}
        store.save([rec])
        return store.load()

    def test_a_linkedin_reply_stops_the_email_payload(self):
        rec, recs = self.ready()
        self.assert_eligible(rec, recs, "before the LinkedIn reply")
        recs = self.reply_on(rec, "linkedin")
        with self.assertRaises(AssertionError):
            push.verify_before_payload(self.payload_item(rec, recs),
                                       recs=recs, config=self.config)

    def test_an_email_reply_stops_a_linkedin_step(self):
        rec, recs = self.ready()
        recs = self.reply_on(rec, "email")
        decision = E.decide(rec, rec["contacts"][0], "day3",
                            channel="linkedin", recs=recs, config=self.config)
        self.assertFalse(decision.eligible, decision["reasons"])

    def test_the_channel_the_reply_arrived_on_does_not_narrow_the_stop(self):
        """Whichever channel it came in on, the answer is the same. If the
        two differ, one of them is a sequence still running."""
        answers = {}
        for channel in ("email", "linkedin"):
            rec, recs = self.ready()
            recs = self.reply_on(rec, channel)
            answers[channel] = self.decide(rec, recs).eligible
        self.assertEqual(answers, {"email": False, "linkedin": False})

    def test_a_linkedin_reply_holds_the_colleague_too(self):
        """The account is the unit. Somebody answering on LinkedIn is a
        fact about the company, not about one profile."""
        from src import mx

        recs = self.seed_records()
        rec = recs[0]
        rec["contacts"] = [
            contact("acme-champ", "Champ", "champ@acme.test"),
            contact("acme-buyer", "Buyer", "buyer@acme.test")]
        for person in rec["contacts"]:
            person["mx"] = mx.decide(["aspmx.l.google.com"],
                                     mx.settings(self.config),
                                     domain="acme.test")
        self.draft_everything(recs)
        self.approve_drafts(recs)
        store.save(recs)
        recs = store.load()
        before = E.decide(recs[0], recs[0]["contacts"][1], "day1",
                          recs=recs, config=self.config)
        self.assertTrue(before.eligible, before["reasons"])

        recs[0].setdefault("events", []).append({
            "type": events.REPLY_RECEIVED, "contact": "acme-champ",
            "channel": "linkedin", "at": "2026-08-20T09:00:00+00:00"})
        recs[0]["paused"] = {"since": "2026-08-20T09:00:00+00:00",
                             "reason": "reply_received"}
        store.save(recs)
        recs = store.load()
        decision = E.decide(recs[0], recs[0]["contacts"][1], "day1",
                            recs=recs, config=self.config)
        self.assertFalse(decision.eligible, decision["reasons"])

    def test_it_does_not_depend_on_the_account_pause_being_written(self):
        """Two guards carry this, and they fail for different reasons.

        `_paused` reads the account hold, which is channel-agnostic because
        there is one of it. `_replied` scans the event log for a reply from
        this person and does not look at the channel either. A resumed run,
        a hand-edited record or a pause somebody lifted all leave the second
        one standing, and this is the test that says so - the others would
        pass on the pause alone.
        """
        rec, recs = self.ready()
        rec.setdefault("events", []).append({
            "type": events.REPLY_RECEIVED, "contact": "acme-champ",
            "channel": "linkedin", "at": "2026-08-20T09:00:00+00:00"})
        store.save([rec])
        recs = store.load()
        self.assertIsNone(recs[0].get("paused"),
                          "this test is about the case where it is absent")
        decision = E.decide(recs[0], recs[0]["contacts"][0], "day1",
                            channel="email", recs=recs, config=self.config)
        self.assertFalse(decision.eligible)
        self.assertIn(E.BLOCKED_REPLIED, decision["reasons"])

    def test_the_stop_survives_a_hand_assembled_item(self):
        """A caller that built the item itself, from state it fetched
        before the reply arrived, still meets the gate."""
        rec, recs = self.ready()
        item = self.payload_item(rec, recs)
        recs = self.reply_on(rec, "linkedin")
        with self.assertRaises(AssertionError):
            push.verify_before_payload(item, recs=recs, config=self.config)


class TheWorldChangesBetweenApprovalAndSend(Attack):
    """Phase 5's question, asked of the two states that change quietly.

    A reply is loud - somebody typed it and a screen lit up. These two are
    not. A person changes employer and the mailbox keeps accepting mail; a
    sender is taken off the roster and the assignment stored on the contact
    does not notice.
    """

    def test_a_contact_who_left_the_company_is_stopped(self):
        """D and F. The address still accepts mail, which is exactly why
        nothing downstream would notice on its own."""
        rec, recs = self.ready()
        self.assert_eligible(rec, recs, "before they left")

        outcome = ap.apply_reply(rec, "acme-champ", ap.LEFT_COMPANY,
                                 config=self.config)
        self.assertTrue(outcome, "the policy produced no effect")

        # Asserted on the policy decision as well as on the outcome. Every
        # reply stops the person who sent it, whatever it said - so a test
        # that only checked eligibility would pass with the left-company
        # rule set to `continue`, and would be measuring the general rule
        # rather than this one.
        decision = outcome["effects"]["decision"]
        self.assertEqual(decision["action"], ap.STOP)
        self.assertEqual(decision["scope"], ap.CONTACT)

        store.save([rec])
        recs = store.load()

        decision = E.decide(recs[0], recs[0]["contacts"][0], "day1",
                            recs=recs, config=self.config)
        self.assertFalse(decision.eligible, decision["reasons"])

    def test_leaving_stops_the_person_and_not_the_company(self):
        """Their colleagues may still be right. A stop that took the whole
        account with it would lose every other decision maker."""
        from src import mx

        recs = self.seed_records()
        rec = recs[0]
        rec["contacts"] = [
            contact("acme-champ", "Champ", "champ@acme.test"),
            contact("acme-buyer", "Buyer", "buyer@acme.test")]
        for person in rec["contacts"]:
            person["mx"] = mx.decide(["aspmx.l.google.com"],
                                     mx.settings(self.config),
                                     domain="acme.test")
        self.draft_everything(recs)
        self.approve_drafts(recs)
        store.save(recs)
        recs = store.load()

        ap.apply_reply(recs[0], "acme-champ", ap.LEFT_COMPANY,
                       config=self.config)
        store.save(recs)
        recs = store.load()

        gone = E.decide(recs[0], recs[0]["contacts"][0], "day1", recs=recs,
                        config=self.config)
        colleague = E.decide(recs[0], recs[0]["contacts"][1], "day1",
                             recs=recs, config=self.config)
        self.assertFalse(gone.eligible, gone["reasons"])
        self.assertTrue(colleague.eligible, colleague["reasons"])

    def test_the_assignment_records_a_sender_it_could_not_give(self):
        """D. When no eligible human can carry a channel, the refusal is
        written onto the contact rather than silently leaving the channel
        unassigned - so a later reader can tell "nobody was available"
        from "nobody has looked yet"."""
        from src import assignment

        rec, recs = self.ready()
        person = rec["contacts"][0]
        assignment.ensure(rec, person, CLIENT, rows=[], config=self.config)
        described = assignment.describe(person)
        self.assertIn("unavailable", described)
        self.assertTrue(described["unavailable"],
                        "an empty roster must record why nothing was "
                        "assigned")

    def test_a_payload_never_invents_a_sender(self):
        """The other half. With nothing assigned, the payload carries empty
        sender fields rather than a plausible default - an unassigned
        contact is a real state and the launch checklist is where it is
        refused."""
        from src import assignment

        rec, recs = self.ready()
        person = rec["contacts"][0]
        self.assertEqual(assignment.assigned(person, "email"), None)

        sender = push._sender_of(person, "email")
        self.assertEqual(sender["sender_id"], "")
        self.assertEqual(sender["sender_name"], "")

class HistoryCannotBeRewritten(Attack):

    def test_a_planned_touch_is_not_a_touch(self):
        """M. `push_prepared` is absent from `touch.CONFIRMING_EVENTS` by
        name. Copy may not claim a step that never left."""
        rec, recs = self.ready()
        rec.setdefault("events", []).append({
            "type": events.PUSH_PREPARED, "contact": "acme-champ",
            "channel": "linkedin", "step": "day3",
            "at": "2026-08-20T09:00:00+00:00", "sender_id": "petar"})
        from src import account

        prepared = [row for row in account.touches(rec)
                    if row["event"] == events.PUSH_PREPARED]
        self.assertEqual(len(prepared), 1, "the fixture wrote one")
        self.assertFalse(prepared[0]["confirmed"])
        self.assertNotIn(prepared[0]["state"], touch.CONFIRMED_STATES)
        self.assertEqual(
            [row for row in account.touches(rec, confirmed_only=True)
             if row["event"] == events.PUSH_PREPARED], [])

    def test_a_confirmed_touch_names_whoever_sent_it(self):
        """N. Mark sent it. Anna is assigned now. The history says Mark."""
        from src import account, contextpack

        rec, recs = self.ready()
        rec.setdefault("events", []).append({
            "type": events.PUSH_MARKED, "contact": "acme-champ",
            "channel": "email", "step": "day1",
            "at": "2026-08-10T09:00:00+00:00", "sender_id": "mark"})
        rec["contacts"][0]["sender_assignment"] = {
            "email": {"sender_id": "anna", "display_name": "Anna Fischer"}}
        found = contextpack.account_history(
            rec, CLIENT,
            rows=[{"workspace": CLIENT, "sender_id": "mark",
                   "display_name": "Mark Weber"},
                  {"workspace": CLIENT, "sender_id": "anna",
                   "display_name": "Anna Fischer"}])
        self.assertEqual(found["heard_from"], {"email": ["Mark Weber"]})
        self.assertNotIn("Anna", repr(found))

    def test_a_stale_signal_is_not_described_as_current(self):
        """O. The office is still there. It is not news."""
        from src import observations

        rec, recs = self.ready()
        fact = evidence.make(
            "Acme opened a Vienna delivery office and is hiring four "
            "implementation managers.",
            "https://acme.test/news", "news", "apify", rec["id"],
            published_at="2026-01-01", subject=evidence.COMPANY,
            persona="champion",
            angle_words=["utilisation", "capacity", "delivery"],
            today="2026-01-05")
        rec["research"] = [fact]
        found = observations.resolve(
            observations.COMPANY_EVENT, rec, "acme-champ",
            {"observations": {"company_event": "on"}}, today="2026-08-31")
        self.assertTrue(found)
        self.assertFalse(found["may_call_it_now"])


class OneEventIsCountedOnce(Attack):

    def test_a_duplicate_webhook_produces_one_canonical_event(self):
        """G. Providers redeliver. The second delivery must change nothing."""
        rec, recs = self.ready()
        payload = {"events": [{
            "event": "replied", "id": "bison-evt-dup",
            "email": "champ@acme.test",
            "timestamp": "2026-08-26T10:00:00+00:00",
            "text": "not right now, try me in the spring",
            "custom_variables": {"record_id": rec["id"],
                                 "contact_key": "acme-champ",
                                 "client": CLIENT}}]}
        def replies_on(rows):
            return [e for e in rows[0].get("events") or []
                    if e["type"] == events.REPLY_RECEIVED]

        inbound.ingest(payload, "emailbison", recs=recs, config=self.config,
                       post=self.post)
        store.save(recs)
        self.assertEqual(len(replies_on(store.load())), 1,
                         "the first delivery is recorded")

        # The same payload again, exactly as a provider would redeliver it.
        again = store.load()
        inbound.ingest(payload, "emailbison", recs=again, config=self.config,
                       post=self.post)
        store.save(again)
        self.assertEqual(len(replies_on(store.load())), 1,
                         "the second delivery changes nothing")

    def test_the_same_reply_on_two_transports_is_two_events(self):
        """H. Deduping on anything less than an authoritative id would
        collapse two genuinely different replies from one person."""
        rec, recs = self.ready()
        rec["contacts"][0]["linkedin"] = \
            "https://www.linkedin.com/in/acme-champ"
        store.save([rec])
        recs = store.load()

        inbound.ingest({"events": [{
            "event": "replied", "id": "bison-evt-a",
            "email": "champ@acme.test",
            "timestamp": "2026-08-26T10:00:00+00:00",
            "text": "not right now",
            "custom_variables": {"record_id": rec["id"],
                                 "contact_key": "acme-champ",
                                 "client": CLIENT}}]},
            "emailbison", recs=recs, config=self.config, post=self.post)
        store.save(recs)

        recs = store.load()
        inbound.ingest({"events": [{
            "eventType": "message_reply", "id": "hr-evt-a",
            "profileUrl": "https://www.linkedin.com/in/acme-champ",
            "timestamp": "2026-08-26T11:00:00+00:00",
            "text": "also here",
            "customUserFields": [
                {"name": "record_id", "value": rec["id"]},
                {"name": "contact_key", "value": "acme-champ"},
                {"name": "client", "value": CLIENT}]}]},
            "heyreach", recs=recs, config=self.config, post=self.post)
        store.save(recs)

        kinds = [e for e in store.load()[0].get("events") or []
                 if e["type"] == events.REPLY_RECEIVED]
        self.assertEqual(len(kinds), 2)
        self.assertEqual({e.get("channel") for e in kinds},
                         {"email", "linkedin"})


class ADownstreamFailureCannotUnwindBusinessState(Attack):

    def test_slack_failing_does_not_unpause_the_company(self):
        """I. The pause happens before anything is classified and long
        before anybody is told. Nothing downstream can reach back."""
        def explode(*args, **kwargs):
            raise RuntimeError("slack is down")

        rec, recs = self.ready()
        inbound.ingest({"events": [{
            "event": "replied", "id": "bison-evt-slack",
            "email": "champ@acme.test",
            "timestamp": "2026-08-26T10:00:00+00:00",
            "text": "this is interesting, what does it cost",
            "custom_variables": {"record_id": rec["id"],
                                 "contact_key": "acme-champ",
                                 "client": CLIENT}}]},
            "emailbison", recs=recs, config=self.config, post=explode)

        # `ingest` mutates the records it is handed and leaves the save to
        # the caller, which is what the campaign runner does.
        after = recs[0]
        self.assertTrue(after.get("paused"), "the pause must survive")
        self.assertTrue([e for e in after.get("events") or []
                         if e["type"] == events.REPLY_RECEIVED])

        store.save(recs)
        self.assertTrue(store.load()[0].get("paused"),
                        "and it must survive being written down")
        self.assertEqual(self.posted, [], "Slack was never reached")

    def test_tag_sync_refuses_without_touching_canonical_state(self):
        """J. The outbox records what the providers should be told. What
        they were actually told changes nothing here."""
        rec, recs = self.ready()
        rows = tagsync.enqueue(rec, "acme-champ", CLIENT,
                               outcome="positive_reply")
        self.assertTrue(rows)
        with self.assertRaises(tagsync.TagSyncRefused):
            tagsync.send(rows[0], live=True)
        self.assertEqual(store.load()[0].get("paused"),
                         rec.get("paused"))


class ProviderNamesAreNotIdentity(Attack):

    def test_a_renamed_provider_campaign_keeps_its_linkage(self):
        """K. The mapping is an id. A display name is a label somebody in
        another product can change at any time."""
        campaign, recs = self.ready_campaign()
        orchestrator.map_external(campaign, bison_campaign_id="9001",
                                  heyreach_campaign_id="7001", by=ADMIN)
        self.save_campaign(campaign)

        campaign["name"] = "somebody renamed this in EmailBison"
        self.save_campaign(campaign)

        found = campaigns.get(campaign["campaign_id"], campaigns.load())
        self.assertEqual(found["bison_campaign_id"], "9001")
        self.assertEqual(found["heyreach_campaign_id"], "7001")

    def test_nothing_looks_a_campaign_up_by_its_display_name(self):
        from src import providername

        self.assertFalse(hasattr(providername, "parse"))
        self.assertFalse(hasattr(providername, "lookup"))
        self.assertFalse(hasattr(providername, "match"))


class FiveAtOneCompanyAreFivePeople(Attack):

    def test_a_same_domain_csv_makes_one_company_and_five_contacts(self):
        """L. The failure this replaced discarded rows 2..N as duplicates
        and then built the record from domain alone, so one company arrived
        with zero contacts."""
        from src.web import upload

        header = "company,domain,first_name,last_name,email,title" + NL
        body = "".join(
            "Acme Services,acme.test,Person%d,Example,"
            "person%d@acme.test,Head of Delivery%s" % (i, i, NL)
            for i in range(1, 6))
        parsed = upload.parse((header + body).encode("utf-8"),
                              batch="batch-1", client=CLIENT)

        self.assertEqual(len(parsed["rows"]), 1, "one company")
        self.assertEqual(parsed["contacts"], 5, "five people")
        mailboxes = {c["email"] for c in parsed["rows"][0]["contacts"]}
        self.assertEqual(len(mailboxes), 5, "five distinct mailboxes")

        # And identity is assigned at commit, which is where the
        # original defect was: `commit` built the record from domain
        # and company alone and dropped the parsed contacts.
        from src import identity

        keys = {row["key"] for row in identity.assign_keys([
            {"email": c["email"],
             "name": c["first_name"] + " " + c["last_name"]}
            for c in parsed["rows"][0]["contacts"]])}
        self.assertEqual(len(keys), 5, "five distinct identities")
        self.assertEqual(
            parsed["additional_contacts"], 4,
            "rows 2..5 joined the account rather than being dropped "
            "as duplicates")


if __name__ == "__main__":
    unittest.main()
