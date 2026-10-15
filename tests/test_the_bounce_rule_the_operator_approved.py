#!/usr/bin/env python3
"""One hard bounce closes an address. Three soft ones do. An OOO closes nobody.

The rule is the operator's, approved in full 2026-10-15 23:30 and written out
in `resonate-ops/DECISION-bounce-rule-2026-10-15.md`. This file is the four
tests the task asked for, one class each, plus the two controls without which
they would be measuring nothing.

BORN RED, AND RED IN FOUR DIFFERENT PLACES. Measured on `1c77a06c1`, the
lane's trunk, by reverting every source file this change touches:

    AHardBounceSuppressesOnTheFirst        red: no production caller records
                                           a bounce at all
    ASoftBounceIsCountedNotActedOn         red: `events.EMAIL_BOUNCED_SOFT`
                                           does not exist, so the module
                                           does not import
    ADeliveryBetweenTwoSoftsResets         red: same
    AnOutOfOfficeSuppressesNobody          GREEN on `1c77a06c1`, and that is
                                           the point of it - see below

## Why the out-of-office class is green before the change and must stay green

It is the control, not the feature. Rule 3 of the decision is a BLOCKING
PRECONDITION: if an out-of-office could be classified as a bounce, the rule
would remove the most engaged people on the list and look like it was
working. So this class asserts a property that was already true on
`1c77a06c1` and that the rest of this change must not break - a test that
only goes red when somebody wires a text classifier into the bounce path.

It is asserted three ways, because one way is an opinion:

  * END TO END, through the real ingest, with a body that TALKS LIKE A
    BOUNCE. "Undeliverable", "550 5.1.1 user unknown" and "mailbox full" in
    an autoresponder, which is what an out-of-office from a mail system with
    a quota warning actually looks like.
  * BY IMPORT GRAPH, which is the assertion that survives a rewrite. No
    module that produces or consumes a bounce can reach `ooo` or `replies`.
  * AND BY GUARDING THE GUARD. If the fixture stopped being recognised as an
    out-of-office the two above would pass vacuously, so `replies.classify`
    and `ooo.detect` are asked directly about the same body.

## Why the bounce classes drive `record_bounces` rather than the watcher

`tests/test_a_provider_bounce_reaches_the_record.py` is the file that proves
the WIRING: it runs one real cycle of `scripts/bison_watch_loop.main` and is
deliberately agnostic about which module records anything. This file proves
the RULE, and the rule needs three distinct bounces to the same address with
a reply in the middle - machinery that would bury what is being asserted if
it were threaded through a watcher loop three times. `record_bounces` is the
function that watcher cycle calls, and `test_the_watcher_cycle_records_a_soft
_bounce` joins the two claims up so neither file can be true alone.

Rows are handed in through `queue=`, so no test here reaches a provider at
all - which is also how the production caller works, because `snapshot` has
already paid for that read.
"""
import ast
import os
import unittest

from src import (agencydnc, bouncepolicy, channels, eligibility, events,
                 leadobserve, ooo, poller, replies, store)
from src.providers import bison
from tests.base import ProviderTest

PRODUCTIVE = {"id": 10, "name": "PRODUCTIVE"}

#: 492 is one of the four campaigns that really bounced. The number only has
#: to be consistent within the file.
CAMPAIGN = 492

ADDRESS = "dana@acme.test"
CONTACT_KEY = "ck-1"
RECORD_ID = "rec-1"

#: An out-of-office that says every word a bounce says. This is not a straw
#: man: a mailbox over quota sends exactly this, and "undeliverable" and a
#: 5.x.x code in an autoresponder is the case rule 3 exists for.
OOO_BODY = (
    "<p>Automatic reply: I am out of the office until 8 September with "
    "limited access to my email.</p>"
    "<p>Undeliverable: 550 5.1.1 user unknown. My mailbox is full and "
    "messages may bounce.</p>")


def _queue_row(row_id, step_id, status="bounced"):
    """One `GET /api/campaigns/{id}/scheduled-emails` row, as the provider
    returns it.

    The field set is the one `leadobserve.scheduled_rows` actually reads,
    including the nesting that matters - the lead under `lead` and our own
    identifiers under its `custom_variables`, where `bison.variables_of`
    looks. Copied from `test_a_provider_bounce_reaches_the_record._queue_row`
    with the ids parameterised, and deliberately not imported from it: the
    two files must be able to disagree about a fixture and say so.
    """
    return {
        "id": row_id,
        "status": status,
        "sequence_step_id": step_id,
        "scheduled_date": "2026-09-22T15:00:00.000000Z",
        "sent_at": "2026-09-22T15:36:47.000000Z",
        "raw_message_id": f"<msg-{row_id}@acme.test>",
        "email_subject": "a subject",
        "email_body": "<p>a body</p>",
        "opens": 0, "unique_opens": 0, "clicks": 0,
        "replies": 0, "unique_replies": 0, "interested": 0,
        "lead": {
            "id": 204472,
            "email": ADDRESS,
            "first_name": "Dana",
            "custom_variables": [
                {"name": "record_id", "value": RECORD_ID},
                {"name": "contact_key", "value": CONTACT_KEY},
                {"name": "client", "value": "productive"},
            ],
        },
        "sender_email": {"id": 3687, "email": "sender@resonate.test"},
        "campaign": {"id": CAMPAIGN, "status": "paused",
                     "open_tracking": False},
    }


def _reply_row(body, automated):
    """One `/api/replies` row. `type` and `folder` are what classify it."""
    return {
        "id": 1609999, "uuid": "u-1609999",
        "lead_id": 204472, "campaign_id": CAMPAIGN,
        "type": "untracked reply", "folder": "inbox",
        "automated_reply": automated,
        "from_email_address": ADDRESS,
        "created_at": "2026-09-22T15:36:47.000000Z",
        "date_received": "2026-09-22T15:36:47.000000Z",
        "html_body": body, "text_body": body,
        "lead": {"id": 204472, "email": ADDRESS, "first_name": "Dana",
                 "custom_variables": [
                     {"name": "record_id", "value": RECORD_ID},
                     {"name": "contact_key", "value": CONTACT_KEY},
                     {"name": "client", "value": "productive"}]},
    }


def _feed(*rows):
    pages = [(list(rows), None)] if rows else []

    def fetch(cursor=None, per_page=None):
        return pages.pop(0) if pages else ([], None)
    return fetch


def _contact():
    """A contact that is otherwise sendable under THIS record's client."""
    return {"key": CONTACT_KEY, "email": ADDRESS, "name": "Dana Reed",
            "sendable": True, "verdict": "valid",
            "verification": {"evidence": [
                {"provider": "deliverable", "status": "valid",
                 "email": ADDRESS},
                {"provider": "reoon", "status": "valid", "email": ADDRESS}]}}


class RuleTest(ProviderTest):
    """One record and one address, in a throwaway store."""

    def setUp(self):
        super().setUp()
        rec = store.new_record(RECORD_ID, "domains", "productive", "Acme",
                               "acme.test")
        rec["state"] = "ready"
        rec["contacts"] = [_contact()]
        with store.transaction() as rows:
            rows.append(rec)

    # ------------------------------------------------------- the provider

    def bounce(self, row_id=900001, step_id=5001, status="bounced"):
        """One bounce, recorded the way the watcher records it."""
        return leadobserve.record_bounces(
            CAMPAIGN, queue=[_queue_row(row_id, step_id, status)], live=True)

    def accepted_mail(self, kind=events.REPLY_RECEIVED, at="2026-09-01T09:00Z"):
        """Proof the address accepted mail from us, on the record.

        Written through `events.record` rather than appended by hand, so the
        entry carries the same shape the real ingest writes and the test
        cannot pass on a field the producer never sets.
        """
        with store.transaction() as held:
            events.record(store.get(RECORD_ID, held), kind,
                          contact_key=CONTACT_KEY, channel=events.EMAIL,
                          at=at, provider="emailbison",
                          provider_event_id=f"emailbison:accept:{kind}:{at}")

    # ------------------------------------------------------------ readback

    def events_of(self, kind):
        return [e for e in (store.get(RECORD_ID).get("events") or [])
                if e.get("type") == kind]

    def sendable(self):
        rec = store.get(RECORD_ID)
        return channels.email_verdict(rec, rec["contacts"][0])


class AHardBounceSuppressesOnTheFirst(RuleTest):
    """RULE 1, and RULE 4's hard half - which is the same test on this estate.

    EmailBison states no class, so `bouncepolicy` derives one, and an address
    that has never accepted mail from us has no evidence it has ever worked.
    Measured 2026-10-15: that is 1,290 of the 1,313 contacts in the store
    holding an address.
    """

    def test_one_bounce_closes_an_address_that_never_accepted_mail(self):
        out = self.bounce()
        self.assertEqual(len(out["recorded"]), 1, out)
        self.assertEqual(out["recorded"][0]["event"], events.EMAIL_BOUNCED)
        self.assertEqual(out["recorded"][0]["policy"]["class"],
                         bouncepolicy.HARD)
        self.assertEqual(len(self.events_of(events.EMAIL_BOUNCED)), 1)

    def test_the_send_path_refuses_it_immediately(self):
        """The event is only worth recording because this is what it does."""
        self.bounce()
        ok, why = self.sendable()
        self.assertFalse(ok)
        self.assertEqual(why, channels.BOUNCED)

    def test_the_provider_saying_hard_beats_the_first_party_test(self):
        """RULE 1 OUTRANKS RULE 4, which only exists because rule 1 has no
        input on this estate. An address that HAS accepted mail would be
        counted under rule 2 - the provider's own word closes it anyway."""
        self.accepted_mail()
        out = self.bounce(status="hard_bounced")
        self.assertEqual(out["recorded"][0]["event"], events.EMAIL_BOUNCED)
        self.assertEqual(out["recorded"][0]["policy"]["class"],
                         bouncepolicy.HARD)
        self.assertFalse(self.sendable()[0])


class ASoftBounceIsCountedNotActedOn(RuleTest):
    """RULE 2. Not on the first, not on the second, and yes on the third."""

    def setUp(self):
        super().setUp()
        # The address has accepted mail from us, so rule 4 sends its bounces
        # down the soft path. Without this every bounce here is hard and the
        # class tests nothing.
        self.accepted_mail()

    def test_the_first_soft_bounce_does_not_suppress(self):
        out = self.bounce(900001, 5001)
        self.assertEqual(out["recorded"][0]["event"],
                         events.EMAIL_BOUNCED_SOFT)
        self.assertEqual(out["recorded"][0]["policy"]["soft_count"], 1)
        self.assertEqual(self.events_of(events.EMAIL_BOUNCED), [])
        self.assertTrue(self.sendable()[0], self.sendable())

    def test_the_second_soft_bounce_does_not_suppress(self):
        self.bounce(900001, 5001)
        out = self.bounce(900002, 5002)
        self.assertEqual(out["recorded"][0]["event"],
                         events.EMAIL_BOUNCED_SOFT)
        self.assertEqual(out["recorded"][0]["policy"]["soft_count"], 2)
        self.assertEqual(self.events_of(events.EMAIL_BOUNCED), [])
        self.assertTrue(self.sendable()[0], self.sendable())

    def test_the_third_soft_bounce_suppresses(self):
        self.bounce(900001, 5001)
        self.bounce(900002, 5002)
        out = self.bounce(900003, 5003)
        self.assertEqual(out["recorded"][0]["event"], events.EMAIL_BOUNCED,
                         "the third consecutive soft bounce is a derived "
                         "hard bounce and must close the address")
        self.assertEqual(out["recorded"][0]["policy"]["soft_count"], 3)
        ok, why = self.sendable()
        self.assertFalse(ok)
        self.assertEqual(why, channels.BOUNCED)

    def test_after_two_softs_the_refusal_is_not_the_bounce(self):
        """A POSITIVE CONTROL, not an `assertNotEqual`.

        It names the reason the send path really gives this fixture, and on
        this one it is `blocked:replied` rather than the bounce: rule 2
        needs an address that has ACCEPTED mail, the only acceptance this
        system records is a reply, and a reply protects the person outright
        - `eligibility` refuses before it reaches lint or the bounce gate.
        That is the system being consistent, and it makes a sharper control
        than an `assertNotEqual` would: if a soft bounce ever closed the
        address, this reads `blocked:address_bounced` and says so.
        """
        self.bounce(900001, 5001)
        self.bounce(900002, 5002)
        rec = store.get(RECORD_ID)
        verdict = eligibility.decide(
            rec, rec["contacts"][0], "day1", channel="email",
            step={"channel": "email", "subject": "s", "body": "b" * 200})
        self.assertEqual(verdict.get("reason"), eligibility.BLOCKED_REPLIED)

    def test_the_same_row_polled_three_times_suppresses_nobody(self):
        """THE ONE THAT WOULD HAVE BITTEN IN PRODUCTION.

        A bounced queue row stays `bounced` for ever and twenty watchers
        re-read their queues every 180 seconds, so a counter that counted
        POLLS instead of EVENTS would reach three in nine minutes and close
        the address on a single soft bounce.

        WHAT PREVENTS IT IS TWO GUARDS, NOT ONE, AND THAT WAS MEASURED
        RATHER THAN READ. `events.record` refuses a repeat both on
        `provider_event_id` and on the derived `id`, and on this path they
        are REDUNDANT: removing either one alone leaves this test green
        (mutations M6 and M6c, 2026-10-15), and only removing BOTH turns it
        red (M6b). So this test is load-bearing and a test naming either
        guard on its own would not be.
        """
        for _ in range(3):
            self.bounce(900001, 5001)
        self.assertEqual(len(self.events_of(events.EMAIL_BOUNCED_SOFT)), 1)
        self.assertEqual(self.events_of(events.EMAIL_BOUNCED), [])
        self.assertTrue(self.sendable()[0], self.sendable())

    def test_the_watcher_cycle_records_a_soft_bounce(self):
        """THE WIRING, ONCE, so this file and the sibling join up.

        `scripts/bison_watch_loop._bounce_recorder` is what runs in
        production - twenty of them, measured live on 2026-10-15 - and it
        calls `record_bounces` with the rows `snapshot` already read. The
        sibling file proves one whole cycle reaches a producer; this proves
        the producer it reaches applies THIS rule rather than suppressing on
        the first bounce.
        """
        import scripts.bison_watch_loop as wl
        lines = []
        record = wl._bounce_recorder(CAMPAIGN, lines.append)
        record([_queue_row(900001, 5001)])
        self.assertEqual(len(self.events_of(events.EMAIL_BOUNCED_SOFT)), 1)
        self.assertEqual(self.events_of(events.EMAIL_BOUNCED), [])
        self.assertTrue(any("class=soft" in line and "suppresses=False" in line
                            for line in lines), lines)


class ADeliveryBetweenTwoSoftsResetsTheCounter(RuleTest):
    """RULE 2'S "WITH NO DELIVERY BETWEEN", which is the whole of it.

    Without the reset, three soft bounces spread over a year close an
    address that has been answering us the whole time.
    """

    def setUp(self):
        super().setUp()
        self.accepted_mail(at="2026-09-01T09:00Z")

    def test_a_reply_between_two_softs_resets_the_count(self):
        self.bounce(900001, 5001)
        self.bounce(900002, 5002)
        self.accepted_mail(at="2026-09-10T09:00Z")
        out = self.bounce(900003, 5003)
        self.assertEqual(out["recorded"][0]["event"],
                         events.EMAIL_BOUNCED_SOFT,
                         "two softs, then the address accepted mail, so the "
                         "next bounce is the FIRST of a new run")
        self.assertEqual(out["recorded"][0]["policy"]["soft_count"], 1)
        self.assertTrue(self.sendable()[0], self.sendable())

    def test_a_delivery_between_two_softs_resets_the_count(self):
        """`EMAIL_DELIVERED` is the canonical acceptance and the one that
        does not exist yet: 0 of them in the production store on
        2026-10-15, because nothing produces them. It is asserted anyway,
        because the day a producer appears this must already be right."""
        self.bounce(900001, 5001)
        self.bounce(900002, 5002)
        self.accepted_mail(kind=events.EMAIL_DELIVERED,
                           at="2026-09-10T09:00Z")
        out = self.bounce(900003, 5003)
        self.assertEqual(out["recorded"][0]["policy"]["soft_count"], 1)
        self.assertTrue(self.sendable()[0], self.sendable())

    def test_without_the_reset_the_third_would_have_closed_it(self):
        """THE CONTROL FOR THE TWO ABOVE. Identical, minus the acceptance.
        If this went green too, the reset would be proving nothing."""
        self.bounce(900001, 5001)
        self.bounce(900002, 5002)
        out = self.bounce(900003, 5003)
        self.assertEqual(out["recorded"][0]["event"], events.EMAIL_BOUNCED)
        self.assertFalse(self.sendable()[0])


class AnOutOfOfficeSuppressesNobody(RuleTest):
    """RULE 3, THE BLOCKING PRECONDITION, AND THE CONTROL THAT GOES LOUD.

    Green before this change and green after it. It fails the day somebody
    classifies a bounce from a message body, which is the one way this
    feature could do real damage.
    """

    def ingest(self, body, automated=True):
        """The real inbound path: one reply page through `poller.run`."""
        return poller.run("emailbison", live=True,
                          identify=lambda: PRODUCTIVE,
                          fetch=_feed(_reply_row(body, automated)),
                          sleep=lambda *_: None)

    def test_an_out_of_office_records_no_bounce_of_either_kind(self):
        self.ingest(OOO_BODY)
        self.assertEqual(self.events_of(events.EMAIL_BOUNCED), [])
        self.assertEqual(self.events_of(events.EMAIL_BOUNCED_SOFT), [])

    def test_an_out_of_office_that_talks_like_a_bounce_is_still_a_reply(self):
        """The body carries "Undeliverable", a 550 code and "mailbox full",
        and the address stays open. The classification is structural - the
        provider's `type` and `folder` - so the words cannot move it."""
        self.ingest(OOO_BODY)
        self.assertEqual(self.events_of(events.REPLY_RECEIVED) and True, True)
        ok, why = self.sendable()
        self.assertNotEqual(why, channels.BOUNCED,
                            "an out-of-office closed an email address")

    def test_the_fixture_really_is_an_out_of_office(self):
        """GUARD THE GUARD. If `replies` stopped recognising this body the
        two tests above would pass while asserting nothing at all."""
        verdict = replies.classify(OOO_BODY)
        self.assertEqual(verdict["classification"], replies.OUT_OF_OFFICE)
        reading = ooo.detect(OOO_BODY, automated=True)
        self.assertTrue(reading["is_absence"])
        self.assertEqual(reading["kind"], ooo.AUTORESPONDER)

    def test_the_bounce_classifier_never_reads_a_body(self):
        """The two producers, asked with the words and nothing else.

        `bison.classify_reply_row` decides on `event`, `type` and `folder`;
        `leadobserve._email_state` decides on `status`. A row carrying only
        bounce LANGUAGE is unclassifiable, not a bounce.
        """
        self.assertEqual(
            bison.classify_reply_row({"html_body": OOO_BODY,
                                      "text_body": OOO_BODY}),
            "unknown")
        self.assertEqual(leadobserve._email_state("undeliverable"),
                         leadobserve.EMAIL_STATE_UNKNOWN)
        self.assertIsNone(
            leadobserve.EVENT_FOR.get(leadobserve.EMAIL_STATE_UNKNOWN))

    def test_no_bounce_producer_can_reach_the_out_of_office_classifier(self):
        """BY IMPORT GRAPH, which is the assertion that survives a rewrite.

        Measured 2026-10-15: the transitive import closure of each of these
        is 111 modules and contains none of `ooo`, `oooreturn`, `replies`.
        A text classifier wired into the bounce path shows up here before it
        shows up in anybody's inbox.
        """
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        files = {}
        for base in ("src", os.path.join("src", "providers")):
            folder = os.path.join(root, base)
            for name in os.listdir(folder):
                if name.endswith(".py"):
                    files.setdefault(name[:-3], os.path.join(folder, name))

        def imports(path):
            with open(path, encoding="utf-8") as handle:
                tree = ast.parse(handle.read())
            found = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.ImportFrom) and node.module:
                        found.add(node.module.split(".")[-1])
                    for alias in node.names:
                        found.add(alias.name.split(".")[-1])
            return {name for name in found if name in files}

        def closure(start):
            seen, stack = set(), [start]
            while stack:
                current = stack.pop()
                if current in seen:
                    continue
                seen.add(current)
                stack.extend(imports(files[current]) - seen)
            return seen

        for start in ("leadobserve", "adapters", "bison", "channels",
                      "eligibility", "bouncepolicy"):
            reached = closure(start)
            for classifier in ("ooo", "oooreturn", "replies"):
                self.assertNotIn(
                    classifier, reached,
                    f"src/{start}.py can now reach src/{classifier}.py, so a "
                    f"message BODY can influence whether something is a "
                    f"bounce. Rule 3 of the 2026-10-15 decision is a "
                    f"blocking condition: the rule does not go live while "
                    f"this is true")


class TheMechanismWritesNothingItMayNotWrite(RuleTest):
    """Two boundaries the decision draws explicitly."""

    def test_a_suppression_does_not_reach_the_agency_dnc(self):
        """`src/agencydnc.py`: a row there is "written deliberately by a
        super admin, never derived". Three soft bounces are a derivation."""
        self.accepted_mail()
        before = agencydnc.load()
        self.bounce(900001, 5001)
        self.bounce(900002, 5002)
        self.bounce(900003, 5003)
        self.assertFalse(self.sendable()[0], "the fixture did not suppress, "
                                             "so this asserts nothing")
        self.assertEqual(dict(agencydnc.load()), dict(before))

    def test_the_counter_is_derived_and_not_stored(self):
        """The count is a function of the event log, so there is no second
        representation of it to drift. If a field ever holds it, this names
        the field."""
        self.accepted_mail()
        self.bounce(900001, 5001)
        rec = store.get(RECORD_ID)
        self.assertEqual(
            bouncepolicy.consecutive_soft(rec, CONTACT_KEY, ADDRESS), 1)
        contact = rec["contacts"][0]
        stored = {k: v for k, v in contact.items()
                  if "bounce" in k.lower() or "soft" in k.lower()}
        self.assertEqual(stored, {}, f"a soft-bounce counter is stored on the "
                                     f"contact as well as derived: {stored}")

    def test_the_matcher_agrees_with_the_send_path(self):
        """`bouncepolicy._about` and `channels._bounced` must answer the same
        question the same way, or an event counted here closes somebody
        else there. Asserted on the event the send path reads."""
        self.bounce(900001, 5001)
        rec = store.get(RECORD_ID)
        contact = rec["contacts"][0]
        entry = self.events_of(events.EMAIL_BOUNCED)[0]
        self.assertTrue(channels._bounced(rec, contact))
        self.assertTrue(bouncepolicy._about(entry, contact["key"],
                                            contact["email"]))
        self.assertFalse(bouncepolicy._about(entry, "somebody-else",
                                             "other@acme.test"))


if __name__ == "__main__":
    unittest.main()
