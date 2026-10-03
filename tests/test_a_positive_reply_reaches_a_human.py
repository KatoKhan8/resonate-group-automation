"""TASK-1004 - the three ways a reply that wanted a human did not get one.

Everything here drives the REAL synchronous reply path:

    inbound.handle(event)
        -> events.apply            the reply is attributed
        -> replies.apply           it is classified
        -> accountpolicy.apply_reply   the record's state moves
        -> notify.plan             a notification row is WRITTEN, never posted

No provider is called and nothing is posted. `notify.plan` stores a row;
delivery is asserted through a recording transport patched over
`providers.slack.post`, so the text a human would read is measured without
a Slack workspace existing.

Three defects, measured on 2026-10-03 against master 7e8eee41:

1.  `CLASSIFIER_OUTCOME` mapped `question`, `meeting_intent` and
    `interested` to `unknown`. All three held the account - which is safe -
    and raised NOTHING, because `inbound.handle` and `replies.apply` notify
    only on `POSITIVE`. Two thirds of the operator's primary metric reached
    no human at all, and read back as "nobody classified this".

2.  `channels.email_verdict` returned ALLOWED for a contact carrying
    `stopped`. The cross-channel stop rested on `eligibility` alone, so any
    caller asking `channels` directly - `apply_to_record`, `summarise`,
    `evaluate`, `allows` - got a green light for somebody who had answered
    and been stopped.

3.  A referral phrased as "I am not the right person, please talk to X"
    classifies `not_relevant`, which maps to `NOT_ICP`, which resolves to
    `reply.on_negative` and STOPS the referrer - BLOCKED FOREVER under
    CLAUDE.md's rule 2 - while the one fact worth having, the name of the
    person we were handed, reached nobody.

THE CONTROLS ARE THE POINT. A gate that notifies on everything is as
useless as one that notifies on nothing, so every part here carries a
negative: an ordinary decline raises no operator notification, a clean
contact is still allowed on both channels, a `not_relevant` reply naming
nobody still stops, and a removal request that happens to name a colleague
still suppresses the whole account rather than becoming a referral.
"""
import os
import time
import unittest
from unittest import mock

from src import (accountpolicy as ap, channels, eligibility, events, inbound,
                 notify, operatorexclusion, poller, replies, replywatch, store)
from src.providers import slack
from tests.campaignbase import CampaignTest, contact

CLIENT = "demo"
CANARY = "canary"
REFERRER = "canary-champ"
COLLEAGUE = "canary-colleague"

#: One sentence per case, and each one is DISTINCTIVE so the assertion that
#: the text reached the notification cannot pass on a coincidence.
QUESTION = ("How does it work with the stack we already run? "
            "Can you handle multi-currency invoicing?")
MEETING = "Let's meet about this. Pick a time that suits you next Tuesday."
#: NOT "I would like to know more" - that phrase is in `POSITIVE_PATTERNS`
#: and ranks above the analysis taxonomy, so the reply classifies `positive`
#: and would be testing the path that already worked.
INTERESTED = "I find this interesting."
NEGATIVE = "No thanks, not interested."
OUT_OF_OFFICE = "I am out of the office until 14 October with no access to email."
REFERRAL_AS_WRONG_PERSON = (
    "I am not the right person for this - please talk to Sarah Novak, "
    "sarah.novak@acme.test, she owns delivery operations.")
REFERRAL_PLAIN = ("Please talk to Sarah Novak, sarah.novak@acme.test - "
                  "she owns this.")
NOT_RELEVANT_NAMING_NOBODY = "Not relevant, thanks."
REMOVAL_NAMING_A_COLLEAGUE = (
    "Please remove our company from your list entirely. "
    "Talk to Sarah Novak if you must.")

OPS_CHANNEL = "C0LANEP0OPS"


class ReplyPathTest(CampaignTest):
    """One canary record, one selected contact, an isolated notification file."""

    def setUp(self):
        super().setUp()
        # `notify.path()` already follows the queue into the temp directory,
        # but it is pinned explicitly so a change to that default cannot make
        # this file write the real notification log.
        #
        # `operatorexclusion.path()` does NOT follow `store.use_directory`,
        # and `channels._operator_excluded` asks it on every verdict. Left
        # unset, this module reads - and `exclude`/`clear` would edit - the
        # real register.
        self._pin("NOTIFICATIONS", os.path.join(self.tmp, "work",
                                                "notifications.jsonl"))
        self._pin("OPERATOR_EXCLUSIONS", os.path.join(self.tmp, "work",
                                                      "exclusions.json"))
        # An ops channel, so a GLOBAL notification reaches `planned` rather
        # than `unconfigured`. The id is deliberately not a real one and is
        # not in `notify.RETIRED_CHANNELS`.
        self._pin(notify.OPS_CHANNEL_VAR, OPS_CHANNEL)
        self.assertEqual(notify.ops_channel(), OPS_CHANNEL,
                         "the fixture's ops channel did not take, so a GLOBAL "
                         "notification here would be `unconfigured` for a "
                         "reason that has nothing to do with the test")
        self.assertEqual(operatorexclusion.path(),
                         os.path.abspath(os.path.join(self.tmp, "work",
                                                      "exclusions.json")),
                         "the exclusion register did not move: this test "
                         "would read the real one")

    def _pin(self, name, value):
        previous = os.environ.get(name)

        def restore():
            if previous is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = previous

        self.addCleanup(restore)
        os.environ[name] = value

    # ------------------------------------------------------------ fixtures

    def canary(self):
        """A one-person canary record, plus one colleague who never replies.

        The colleague exists so an account-scope effect can be told from a
        contact-scope one, and so a referral can name somebody who is NOT
        already a contact here (Sarah Novak is not on the record).
        """
        self.reset_estate()
        # The notification log is emptied with the estate. A `subTest` loop
        # shares one `setUp`, so without this the second case counts the
        # first case's rows and "exactly one notification" passes or fails on
        # iteration order rather than on behaviour.
        notify.save([])
        rec = store.new_record(CANARY, "cold", CLIENT, "Acme Services",
                               "acme.test")
        rec["state"] = "verified"
        rec["hook"] = "Acme Services runs delivery across several teams"
        rec["company_facts"] = {"industry": "Professional services",
                                "employees": 40}
        rec["contacts"] = [
            contact(REFERRER, "Champ Acme", "champ@acme.test"),
            contact(COLLEAGUE, "Colleague Acme", "colleague@acme.test"),
        ]
        for person in rec["contacts"]:
            person["selected"] = True
        store.save([rec])
        return store.load()[0]

    def reply(self, rec, text, contact_key=REFERRER, at="2026-10-03T09:00:00+00:00",
              provider_event_id=None):
        """Drive the real inbound path for one reply. Returns (outcome, rec)."""
        event = {
            "type": "email_reply",
            "record_id": rec["id"],
            "contact_key": contact_key,
            "client": CLIENT,
            "channel": "email",
            "provider": "emailbison",
            "provider_event_id": provider_event_id or f"lane-p0-{id(text)}",
            "at": at,
            "text": text,
        }
        recs = store.load()
        result = inbound.handle(event, recs)
        store.save(recs)
        return result, next(r for r in store.load() if r["id"] == rec["id"])

    # ------------------------------------------------------------- readers

    def contact_of(self, rec, key=REFERRER):
        return next(c for c in rec["contacts"] if c["key"] == key)

    def classified(self, rec, key=REFERRER):
        """The outcome the event log recorded, read back the way policy reads it.

        `accountpolicy.classify_outcome` is what every later consumer calls,
        so this asserts on the value that is actually consumed rather than on
        the table.
        """
        return ap.classify_outcome(rec, key)

    def notifications(self, event_type=None, destination=None):
        rows = notify.load()
        if event_type is not None:
            rows = [r for r in rows if r.get("type") == event_type]
        if destination is not None:
            rows = [r for r in rows if r.get("destination") == destination]
        return rows

    def operator_notifications(self):
        """Everything that reached the operator's own feed, whatever its kind."""
        return [r for r in notify.load()
                if r.get("destination") == notify.GLOBAL]

    def rendered(self, row):
        """What a human would read, through the recording transport.

        `notify.deliver` builds the Slack payload and hands it to
        `slack.post`. Recording that call is the only honest way to assert
        "the text reaches a human" without posting: the assertion is on the
        bytes the transport was given, not on the stored row.
        """
        posted = []
        with mock.patch.object(slack, "post",
                              side_effect=lambda payload, config=None:
                              posted.append(payload)):
            notify.deliver(row["id"])
        self.assertEqual(len(posted), 1,
                         "the recording transport was never called, so this "
                         "asserts nothing about what a human would read")
        return posted[0]["text"]


# =====================================================================
#
# PART 1 - A REPLY THAT WANTED A PERSON GETS ONE
#
# =====================================================================

class ThreeCategoriesReachedNobody(ReplyPathTest):

    CASES = {"question": QUESTION,
             "meeting_intent": MEETING,
             "interested": INTERESTED}

    def test_each_of_the_three_classifies_as_itself(self):
        """The fixture's premise, asserted before anything is built on it."""
        for expected, text in self.CASES.items():
            with self.subTest(expected):
                self.assertEqual(replies.classify(text)["classification"],
                                 expected)

    def test_none_of_the_three_reads_back_as_unknown(self):
        """Read through `classify_outcome`, which is what consumers call."""
        for name, text in self.CASES.items():
            with self.subTest(name):
                rec = self.canary()
                _, rec = self.reply(rec, text)
                self.assertNotEqual(
                    self.classified(rec), ap.UNKNOWN,
                    f"a {name} reply still reads as unclassified, so every "
                    f"consumer is told nobody read it")

    def test_each_of_the_three_raises_an_operator_notification(self):
        for name, text in self.CASES.items():
            with self.subTest(name):
                rec = self.canary()
                result, rec = self.reply(rec, text)
                rows = self.notifications(notify.REPLY_NEEDS_A_PERSON)
                self.assertEqual(len(rows), 1,
                                 f"a {name} reply raised {len(rows)} "
                                 f"notifications; the operator needs exactly "
                                 f"one")
                self.assertEqual(rows[0]["destination"], notify.GLOBAL)
                self.assertEqual(rows[0]["status"], notify.PLANNED)
                self.assertEqual(rows[0]["severity"], notify.ACTION_REQUIRED)
                self.assertEqual((result.get("notification") or {}).get("id"),
                                 rows[0]["id"],
                                 "inbound.handle did not return the "
                                 "notification it raised, so a caller "
                                 "watching the return value sees nothing")

    def test_the_notification_carries_the_reply_text(self):
        """Not a count, not a category - the words the prospect wrote."""
        for name, text in self.CASES.items():
            with self.subTest(name):
                rec = self.canary()
                self.reply(rec, text)
                row = self.notifications(notify.REPLY_NEEDS_A_PERSON)[0]
                self.assertIn(text, row["payload"].get("reply_text") or "",
                              "the stored payload does not carry the reply")
                self.assertIn(text, self.rendered(row),
                              "the text a human would read does not contain "
                              "the reply, so the notification tells them a "
                              "reply happened and not what it said")

    def test_the_notification_names_the_person_and_the_company(self):
        rec = self.canary()
        self.reply(rec, QUESTION)
        row = self.notifications(notify.REPLY_NEEDS_A_PERSON)[0]
        self.assertEqual(row["payload"].get("company"), "Acme Services")
        self.assertEqual(row["payload"].get("contact_name"), "Champ Acme")
        self.assertEqual(row["ids"].get("record_id"), rec["id"])
        self.assertEqual(row["ids"].get("contact_key"), REFERRER)

    def test_the_account_is_still_held(self):
        """The fix adds a notification. It must not have removed a pause."""
        for name, text in self.CASES.items():
            with self.subTest(name):
                rec = self.canary()
                _, rec = self.reply(rec, text)
                self.assertEqual(ap.account_state(rec)[0], ap.HOLD)
                self.assertEqual(ap.contact_state(self.contact_of(rec))[0],
                                 ap.HOLD)

    def test_the_same_reply_twice_raises_one_notification(self):
        """Idempotent on the provider event, like every other row here."""
        rec = self.canary()
        self.reply(rec, QUESTION, provider_event_id="dup-1")
        rec = next(r for r in store.load() if r["id"] == rec["id"])
        self.reply(rec, QUESTION, provider_event_id="dup-1")
        self.assertEqual(len(self.notifications(notify.REPLY_NEEDS_A_PERSON)),
                         1)


class OnlyTheRepliesThatNeedAPerson(ReplyPathTest):
    """THE CONTROL. A gate that notifies on everything is useless."""

    def test_an_ordinary_negative_reply_raises_no_operator_notification(self):
        rec = self.canary()
        _, rec = self.reply(rec, NEGATIVE)
        self.assertEqual(self.classified(rec), ap.NEGATIVE)
        self.assertEqual(
            self.operator_notifications(), [],
            "an ordinary decline woke the operator: the notification is "
            "firing on everything, which is the same as firing on nothing")

    def test_an_out_of_office_raises_no_operator_notification(self):
        rec = self.canary()
        _, rec = self.reply(rec, OUT_OF_OFFICE)
        self.assertEqual(self.classified(rec), ap.NOT_NOW)
        self.assertEqual(self.operator_notifications(), [])

    def test_a_negative_reply_still_stops_the_person_who_sent_it(self):
        rec = self.canary()
        _, rec = self.reply(rec, NEGATIVE)
        self.assertEqual(ap.contact_state(self.contact_of(rec))[0], ap.STOP)


class TheFifteenMinuteClaim(ReplyPathTest):
    """WHICH PATH. Three different answers exist; this names the one measured.

    The live reply path is SYNCHRONOUS. `replywatch.Watcher` ticks every
    `REPLY_POLL_SECONDS` (default 300), the tick calls `replywatch.poll_once`,
    which calls `poller.run(live=True)`, which calls `inbound.ingest` ->
    `inbound.handle` -> `replies.apply` -> `notify.plan` inside the call. So
    the end-to-end latency is the poller's cycle plus the handling, and there
    is no timer, queue or deferred job between the reply arriving and the
    notification row existing.

    Each link is measured here rather than read, because a previous
    measurement on this machine proved 15 minutes for a module the script
    never called.
    """

    def test_the_notification_exists_when_the_call_returns(self):
        rec = self.canary()
        started = time.monotonic()
        self.reply(rec, QUESTION)
        elapsed = time.monotonic() - started
        self.assertEqual(len(self.notifications(notify.REPLY_NEEDS_A_PERSON)),
                         1, "nothing was raised inside inbound.handle, so the "
                            "latency is whatever a later job happens to be")
        self.assertLess(elapsed, 60.0,
                        "the synchronous handling alone took longer than a "
                        "minute; the 15-minute claim would then rest on it")

    def test_the_poller_cycle_is_inside_fifteen_minutes(self):
        self.assertLessEqual(replywatch.settings({})["interval"], 900)
        self.assertLessEqual(replywatch.DEFAULT_INTERVAL, 900)

    def test_the_watcher_tick_reaches_the_poller(self):
        """`poll_once` really calls `poller.run`. Measured, not read."""
        calls = []

        def recorder(provider, **kw):
            calls.append((provider, kw))
            return {"provider": provider, "live": True, "cursor": None,
                    "outcomes": [], "pages": 0, "events": 0}

        env = {"BISON_KEY": "fixture-not-a-real-key"}
        with mock.patch.object(replywatch.poller, "run", recorder):
            replywatch.poll_once("emailbison", env=env)
        self.assertEqual(len(calls), 1,
                         "replywatch.poll_once did not call poller.run, so "
                         "the poller cycle is not this path's latency")

    def test_the_poller_reaches_inbound_handle(self):
        """`poller.run` really calls `inbound.handle`. Measured, not read."""
        rec = self.canary()
        # The PROVIDER's shape, because `inbound.ingest` translates through
        # `adapters.from_emailbison`. Handing it a neutral event would skip
        # the adapter and prove nothing about the live page.
        page = {"data": [{"id": 1, "uuid": "chain-1", "type": "reply",
                          "folder": "inbox",
                          "from_email_address": "champ@acme.test",
                          "date_received": "2026-10-03T09:00:00+00:00",
                          "text_body": QUESTION,
                          "automated_reply": False,
                          "custom_variables": {"record_id": rec["id"],
                                               "contact_key": REFERRER,
                                               "client": CLIENT}}]}
        seen = []

        def fake_poll(**kw):
            return [page], "cursor-1"

        real_handle = inbound.handle

        def watched(event, recs, **kw):
            seen.append(event)
            return real_handle(event, recs, **kw)

        with mock.patch.dict(poller.POLLERS, {"emailbison": fake_poll}), \
                mock.patch.object(poller, "identity_of",
                                  return_value=(None, None)), \
                mock.patch.object(inbound, "handle", watched):
            poller.run("emailbison", live=True, advance=False)
        self.assertEqual(len(seen), 1,
                         "poller.run ingested nothing, so measuring "
                         "inbound.handle says nothing about the live path")


# =====================================================================
#
# PART 2 - channels AGREES WITH eligibility ABOUT A STOPPED CONTACT
#
# =====================================================================

class AStoppedContactIsBlockedOnBothChannels(ReplyPathTest):

    def stopped_record(self):
        """A record whose replier has been STOPPED by the real policy path."""
        rec = self.canary()
        _, rec = self.reply(rec, NEGATIVE)
        person = self.contact_of(rec)
        self.assertTrue(person.get("stopped"),
                        "the fixture did not actually stop anybody, so what "
                        "follows tests nothing")
        return rec, person

    def test_a_clean_contact_is_allowed_before_anything_stops_them(self):
        """THE POSITIVE CONTROL. Without it a blanket `False` passes."""
        rec = self.canary()
        person = self.contact_of(rec)
        allowed, reason = channels.email_verdict(rec, person, self.config)
        self.assertTrue(allowed, f"the fixture is not sendable at all: {reason}")
        self.assertIsNone(reason)
        allowed, reason = channels.linkedin_verdict(rec, person, self.config)
        self.assertTrue(allowed, f"the fixture has no usable profile: {reason}")

    def test_email_verdict_blocks_a_stopped_contact(self):
        rec, person = self.stopped_record()
        allowed, reason = channels.email_verdict(rec, person, self.config)
        self.assertFalse(allowed,
                         "channels.email_verdict said ALLOWED for somebody "
                         "who has been stopped")
        self.assertEqual(reason, channels.STOPPED)

    def test_linkedin_verdict_blocks_a_stopped_contact(self):
        """The same field, the other channel: the stop is cross-channel."""
        rec, person = self.stopped_record()
        allowed, reason = channels.linkedin_verdict(rec, person, self.config)
        self.assertFalse(allowed)
        self.assertEqual(reason, channels.STOPPED)

    def test_the_mode_a_stopped_contact_resolves_to_is_none(self):
        """`evaluate` is what `apply_to_record` and `summarise` both read."""
        rec, person = self.stopped_record()
        verdict = channels.evaluate(rec, person, self.config)
        self.assertEqual(verdict["mode"], channels.NONE)
        self.assertFalse(channels.allows(rec, person, channels.EMAIL,
                                         self.config))
        self.assertFalse(channels.allows(rec, person, channels.LINKEDIN,
                                         self.config))

    def test_channels_and_eligibility_agree(self):
        """Two authorities, one answer. Disagreeing is the defect itself."""
        rec, person = self.stopped_record()
        self.assertEqual(
            eligibility.must_not_contact(rec, person, self.config)[4],
            eligibility.BLOCKED_CONTACT_STOPPED)
        self.assertFalse(channels.email_verdict(rec, person, self.config)[0])

    def test_the_reason_is_explainable(self):
        """A reason with no entry in `HUMAN` is a reason nobody can read."""
        self.assertIn(channels.STOPPED, channels.REASONS)
        self.assertTrue(channels.explain(channels.STOPPED))

    def test_a_colleague_who_never_replied_is_still_allowed(self):
        """THE CONTROL. A stop on one person is not a stop on the account."""
        rec, _ = self.stopped_record()
        colleague = self.contact_of(rec, COLLEAGUE)
        self.assertFalse(colleague.get("stopped"))
        allowed, reason = channels.email_verdict(rec, colleague, self.config)
        self.assertTrue(allowed,
                        f"a decline from one person closed the channel to a "
                        f"colleague who never replied: {reason}")


# =====================================================================
#
# PART 3 - A REFERRAL IS NEVER A DEAD END
#
# =====================================================================

class AReferralIsNeverBlockedForever(ReplyPathTest):

    def test_the_measured_path_classifies_not_relevant(self):
        """The premise. Referral ranks BELOW not_relevant in `RULES`."""
        self.assertEqual(
            replies.classify(REFERRAL_AS_WRONG_PERSON)["classification"],
            "not_relevant")

    def test_a_referral_phrased_as_wrong_person_holds_rather_than_stops(self):
        rec = self.canary()
        _, rec = self.reply(rec, REFERRAL_AS_WRONG_PERSON)
        person = self.contact_of(rec)
        self.assertEqual(
            ap.contact_state(person)[0], ap.HOLD,
            "somebody handed us a better contact and we stopped them for it")
        self.assertFalse(person.get("stopped"))
        self.assertFalse(person.get("unsubscribed"))
        self.assertEqual(self.classified(rec), ap.REFERRAL,
                         "the reply reads back as something other than a "
                         "referral, so every consumer sees a dead end")

    def test_a_plain_referral_holds_rather_than_stops(self):
        rec = self.canary()
        _, rec = self.reply(rec, REFERRAL_PLAIN)
        self.assertEqual(ap.contact_state(self.contact_of(rec))[0], ap.HOLD)
        self.assertFalse(self.contact_of(rec).get("stopped"))

    def test_the_referral_policy_default_is_hold(self):
        self.assertEqual(ap.policy("reply.on_referral")["action"], ap.HOLD)
        self.assertEqual(ap.effects(ap.REFERRAL)["replier"], ap.HOLD)

    def test_a_referral_is_not_blocked_forever_by_the_eligibility_gate(self):
        """HOLD and STOP are both refusals; only one of them is liftable."""
        rec = self.canary()
        _, rec = self.reply(rec, REFERRAL_AS_WRONG_PERSON)
        person = self.contact_of(rec)
        reasons = eligibility.must_not_contact(rec, person, self.config)
        self.assertNotIn(eligibility.BLOCKED_CONTACT_STOPPED, reasons)
        self.assertIn(eligibility.BLOCKED_CONTACT_PAUSED, reasons)

    def test_the_referral_raises_a_notification_naming_the_person_referred_to(self):
        for name, text in (("not_relevant", REFERRAL_AS_WRONG_PERSON),
                           ("referral", REFERRAL_PLAIN)):
            with self.subTest(name):
                rec = self.canary()
                self.reply(rec, text)
                rows = self.notifications(notify.REFERRAL_RECEIVED)
                self.assertEqual(len(rows), 1,
                                 "nobody was told we were handed a better "
                                 "contact")
                row = rows[0]
                self.assertEqual(row["destination"], notify.GLOBAL)
                self.assertEqual(row["severity"], notify.ACTION_REQUIRED)
                self.assertIn("Sarah Novak",
                              str(row["payload"].get("referred_to") or ""),
                              "the notification does not name the person we "
                              "were handed")
                self.assertIn("Sarah Novak", self.rendered(row))

    def test_the_referral_notification_carries_the_reply_text(self):
        rec = self.canary()
        self.reply(rec, REFERRAL_AS_WRONG_PERSON)
        row = self.notifications(notify.REFERRAL_RECEIVED)[0]
        self.assertIn(REFERRAL_AS_WRONG_PERSON,
                      row["payload"].get("reply_text") or "")


class WhatIsNotAReferral(ReplyPathTest):
    """THE CONTROLS. A referral reading that softens a refusal is worse than
    the dead end it fixes."""

    def test_a_not_relevant_reply_naming_nobody_still_stops(self):
        rec = self.canary()
        _, rec = self.reply(rec, NOT_RELEVANT_NAMING_NOBODY)
        self.assertEqual(self.classified(rec), ap.NOT_ICP)
        self.assertEqual(ap.contact_state(self.contact_of(rec))[0], ap.STOP)
        self.assertEqual(self.notifications(notify.REFERRAL_RECEIVED), [])

    def test_a_decline_naming_a_colleague_is_still_a_decline(self):
        """"Not interested - talk to Sarah" is a refusal that names somebody."""
        rec = self.canary()
        _, rec = self.reply(rec, "Not interested. Talk to Sarah Novak, "
                                 "sarah.novak@acme.test.")
        self.assertEqual(self.classified(rec), ap.NEGATIVE)
        self.assertEqual(ap.contact_state(self.contact_of(rec))[0], ap.STOP)

    def test_a_removal_request_naming_a_colleague_still_suppresses(self):
        """The single worst thing this change could have produced."""
        rec = self.canary()
        _, rec = self.reply(rec, REMOVAL_NAMING_A_COLLEAGUE)
        self.assertIn(self.classified(rec), (ap.ACCOUNT_DNC, ap.UNSUBSCRIBE))
        self.assertEqual(ap.contact_state(self.contact_of(rec))[0], ap.SUPPRESS)
        self.assertEqual(self.notifications(notify.REFERRAL_RECEIVED), [],
                         "a company-wide removal request was turned into a "
                         "queue item naming a colleague")


if __name__ == "__main__":
    unittest.main()
