r""""What is happening with <domain>" is one question and deserves one answer.

OPERATOR, 2026-09-23: "Account status as a first-class answer: 'what is
happening with <domain>' returns the account status (untouched / sequenced /
engaged / replied / meeting / won / lost / do_not_contact), the personas in
play with their step, last touch, replies by class, and next planned touch;
client-scoped in client channels. Build it on the account status object as
production lands it; until then derive from provider truth and the ledgers
and label the source."

## THE TWO VOCABULARIES, AND WHY THEY ARE NOT ALIASED

`src/account.py` already carries ACTIVE / ENGAGED / PAUSED / SUPPRESSED /
STOPPED / NOT_STARTED. That answers a different question - where one CONTACT
stands for the purposes of whether we may write to them. The operator's list
is a commercial progression for a whole ACCOUNT. They share two words and
mean different things by both.

So `account_status` is a declared PROJECTION over `account.graph()`, which
that module's own docstring calls "the canonical answer to every
account-level question". These tests assert the projection, not a second
walk of the event log.

## WHAT IS ASSERTED

1. **Each state is reachable, from a record in the real shape.** A state
   nothing can produce is a word in a docstring.
2. **`do_not_contact` outranks `meeting`.** It answers "what may we do
   next", not "how far did this get", and an account that met us and then
   asked to be left alone is one we may not write to.
3. **`won` and `lost` are never returned and the answer says so.** Nothing
   in this tree records a deal. An answer that silently never returns two of
   the eight states it advertises is worse than one that names the gap,
   because from the outside the gap looks like "it never happens".
4. **The source is labelled on every answer**, so the day production's
   account-status object lands, the difference is visible rather than
   silent.
5. **Client scope**: another client's domain reads exactly like a domain
   nobody has. Telling those apart IS the disclosure.
6. **Confirmed, not attempted.** The step a persona is "on" comes off the
   last confirmed touch; an attempted step is not one somebody received.

## THE SHAPE BUGS THIS FILE EXISTS TO HAVE CAUGHT

Three, all found by reading `src/account.py` and `src/slackmeetings.py`
rather than by running anything, and all of the same family as the defects
this session has been reporting all day:

- `slackmeetings.by_domain()` returns a LIST of rows, not a count keyed by
  domain. Read as a mapping it raises, the raise is caught, and `meeting`
  becomes a state the function can never return - silently, on the happy
  path.
- `graph()["contacts"]` is a LIST; `by_contact` is the mapping. `.values()`
  on the list raises and every account comes back unreadable.
- A fixture that mocked `graph()` would have hidden both. So the fixtures
  here are RECORDS, in the store's shape, and the real `graph()` runs.
"""
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import events                                          # noqa: E402
from src import slackagenttools as tools                        # noqa: E402
from src import slackscope                                      # noqa: E402


def contact(key="ada", title="Head of Delivery", persona="delivery",
            **over):
    row = {"key": key, "name": "Ada Tester", "title": title,
           "persona": persona, "email": "ada@acme.test", "selected": True}
    row.update(over)
    return row


def touch(kind=events.EMAIL_DELIVERED, key="ada", step=1, day=1,
          at="2026-09-22T09:00:00Z", channel="email", sender_id="s1"):
    """One event in the shape `account.touches` reads."""
    return {"type": kind, "contact": key, "step": step, "day": day,
            "at": at, "channel": channel, "sender_id": sender_id}


def reply_event(key="ada", classification="positive",
                at="2026-09-22T10:00:00Z"):
    return {"type": events.REPLY_RECEIVED, "contact": key, "at": at,
            "classification": classification, "channel": "email"}


def record(domain="acme.test", client="alpha", contacts=None, events_=None,
           **over):
    row = {"id": domain.replace(".", "-"), "lane": "domains",
           "client": client, "company": "Acme", "domain": domain,
           "state": "verified", "contacts": contacts or [contact()],
           "events": events_ or []}
    row.update(over)
    return row


class AccountStatus(unittest.TestCase):

    def setUp(self):
        self._pack = tools.knowledge.pack
        tools.knowledge.pack = lambda *a, **k: {
            "workspaces": {"alpha": {"provider_campaign_ids": []},
                           "beta": {"provider_campaign_ids": []}}}
        self.addCleanup(setattr, tools.knowledge, "pack", self._pack)
        # THE WITNESS CACHE IS MODULE-LEVEL. A verdict left behind by one
        # test decides the next one's answer, which is a test suite that
        # passes for reasons it does not state - and the thing this file
        # exists to argue against.
        tools._LEDGER_WITNESS.clear()
        self.addCleanup(tools._LEDGER_WITNESS.clear)

    def ask(self, rows, domain="acme.test", scope=None, meetings=()):
        scope = scope or slackscope.Scope(slackscope.INTERNAL, source="test")
        with mock.patch.object(tools, "_records", lambda slug: [
                r for r in rows if r.get("client") == slug]), \
                mock.patch.object(tools, "_default_workspace",
                                  lambda: "alpha"), \
                mock.patch("src.slackmeetings.by_domain",
                           lambda workspace=None, **k: list(meetings)):
            return tools.account_status(scope, domain)

    def client(self, workspace="alpha"):
        return slackscope.Scope(slackscope.CLIENT, workspace=workspace,
                                source="test")


# ================================ 1. EVERY STATE IS REACHABLE

class EachStateCanActuallyBeProduced(AccountStatus):

    def test_untouched(self):
        out = self.ask([record()])
        self.assertEqual(out["status"], tools.UNTOUCHED)

    def test_sequenced(self):
        out = self.ask([record(events_=[touch()])])
        self.assertEqual(out["status"], tools.SEQUENCED)

    def test_engaged_is_short_of_a_reply(self):
        out = self.ask([record(events_=[
            touch(kind=events.LINKEDIN_CONNECTED, channel="linkedin")])])
        self.assertEqual(out["status"], tools.ENGAGED)

    def test_replied(self):
        out = self.ask([record(events_=[touch(), reply_event()])])
        self.assertEqual(out["status"], tools.REPLIED)

    def test_meeting(self):
        out = self.ask([record(events_=[touch(), reply_event()])],
                       meetings=[{"domain": "acme.test", "date": "2026-09-20"}])
        self.assertEqual(out["status"], tools.MEETING)

    def test_do_not_contact(self):
        out = self.ask([record(contacts=[contact(suppressed=True)],
                               events_=[touch()])])
        self.assertEqual(out["status"], tools.DO_NOT_CONTACT)

    def test_the_ledger_is_a_list_not_a_mapping(self):
        """THE SHAPE BUG, as one assertion.

        `slackmeetings.by_domain` returns one row per meeting. Read as a
        mapping it raises, the raise is swallowed, and `meeting` silently
        becomes unreachable - which looks exactly like an account that has
        not met anybody.
        """
        out = self.ask([record(events_=[touch(), reply_event()])],
                       meetings=[{"domain": "acme.test", "date": "2026-09-20"},
                                 {"domain": "other.test", "date": "2026-09-21"}])
        self.assertEqual(out["status"], tools.MEETING)
        self.assertIn("1 meeting(s)", " ".join(out["status_evidence"]))


# ============== 1b. THE LEDGER IS THE SOURCE, AND IT MUST BE TRUSTWORTHY

class TheLedgerIsAskedWhetherItIsRecording(AccountStatus):
    """OPERATOR DECISION, 2026-09-23:

    > "Provider-confirmed sends, bounces, replies and HeyReach
    > requests/accepts are written back into the local event ledger by the
    > watchers on every readback (idempotent per provider row id), so
    > account status and accounts-first reporting are computed locally from
    > the ledger, with the provider as a periodic second witness, never as
    > a per-account call. Production owns the write-back; the agent reads
    > the ledger."

    An earlier version of this tool matched each account's addresses
    against the campaign queues. It answered correctly and it is exactly
    the shape this decision rules out: affordable for one domain, ruinous
    for a report over a workspace, and a tool that is affordable for one
    and ruinous for fifty will be used for fifty.

    What is left is ONE question per workspace per TTL: is the ledger
    actually recording sends? Measured on the live store on 2026-09-23 the
    answer was no - 1 `push_marked` and 0 `email_delivered` against 494
    provider-confirmed sends the day before - and the honest behaviour
    while that is true is to WITHHOLD `untouched` rather than assert it.
    """

    def ask_with_witness(self, rows, verdict, domain="acme.test",
                         scope=None):
        scope = scope or slackscope.Scope(slackscope.INTERNAL, source="test")
        with mock.patch.object(tools, "_records", lambda slug: [
                r for r in rows if r.get("client") == slug]), \
                mock.patch.object(tools, "_default_workspace",
                                  lambda: "alpha"), \
                mock.patch.object(tools, "_ledger_carries_sends",
                                  lambda slug, now=None: verdict), \
                mock.patch("src.slackmeetings.by_domain",
                           lambda workspace=None, **k: []):
            return tools.account_status(scope, domain)

    def test_untouched_is_withheld_while_the_ledger_is_blind(self):
        """THE POINT OF THE WHOLE CLASS. An account with nothing in the
        ledger, on a workspace whose ledger is not recording sends, is not
        an untouched account - it is an unanswerable one.

        THE KEY MOVED ON 2026-09-24 AND THE INVARIANT DID NOT. This used to
        assert `out["_error"]`, which is the MECHANISM rather than the
        guarantee: `_error` means "this readback failed", and
        `slackconversation` renders that one line and discards the rest of
        the dict. The readback does not fail - one FIELD has no answer - so
        the reason now travels on `status_unanswerable` and everything the
        account does have survives. See the class below.
        """
        out = self.ask_with_witness([record()], False)
        self.assertIsNone(out["status"])
        self.assertIn("not recording", out["status_unanswerable"])
        self.assertNotIn(
            "_error", out,
            "an unanswerable STATE was reported as a failed READBACK, and "
            "the material builder throws away everything after it.")

    def test_untouched_is_asserted_once_the_ledger_is_trusted(self):
        out = self.ask_with_witness([record()], True)
        self.assertEqual(out["status"], tools.UNTOUCHED)

    def test_a_ledger_touch_answers_even_while_the_witness_says_no(self):
        """Evidence present beats evidence missing. The witness only ever
        licenses the ABSENCE of evidence."""
        out = self.ask_with_witness([record(events_=[touch()])], False)
        self.assertEqual(out["status"], tools.SEQUENCED)

    def test_an_unavailable_witness_is_not_a_failing_one(self):
        """None is not False. A witness that could not be asked has not
        reported a problem, and degrading every answer on a transient
        outage is its own kind of wrong."""
        out = self.ask_with_witness([record()], None)
        self.assertEqual(out["status"], tools.UNTOUCHED)

    def test_the_verdict_is_reported_on_the_answer(self):
        out = self.ask_with_witness([record(events_=[touch()])], False)
        self.assertFalse(out["ledger_carries_sends"])

    def test_the_provider_is_named_as_periodic_never_per_account(self):
        out = self.ask_with_witness([record(events_=[touch()])], True)
        self.assertIn("periodic", out["source"]["provider"])
        self.assertIn("never a per-account call", out["source"]["provider"])

    def test_there_is_no_per_account_provider_call_left(self):
        """The decision, as an assertion. If a later change reintroduces a
        per-account queue walk, this is what should stop it."""
        self.assertFalse(hasattr(tools, "_provider_touches"))


class TheWitnessIsAskedOncePerWindow(AccountStatus):

    def setUp(self):
        super().setUp()
        tools._LEDGER_WITNESS.clear()
        self.addCleanup(tools._LEDGER_WITNESS.clear)

    def witness(self, provider_sent, ledger_events, reads):
        def campaign_by_id(campaign_id):
            reads.append(campaign_id)
            return {"emails_sent": provider_sent}
        rows = [record(events_=[touch()] * ledger_events)]
        return (mock.patch.object(tools.knowledge, "pack", lambda *a, **k: {
                    "workspaces": {"alpha": {"provider_campaign_ids": ["491"]}}}),
                mock.patch.object(tools.readback, "campaign_by_id",
                                  campaign_by_id),
                mock.patch.object(tools, "_records", lambda slug: rows))

    def test_an_empty_ledger_against_a_sending_provider_is_false(self):
        reads = []
        a, b, c = self.witness(494, 1, reads)
        with a, b, c:
            self.assertIs(tools._ledger_carries_sends("alpha"), False)

    def test_a_populated_ledger_is_true(self):
        reads = []
        a, b, c = self.witness(494, 300, reads)
        with a, b, c:
            self.assertIs(tools._ledger_carries_sends("alpha"), True)

    def test_a_workspace_that_has_sent_nothing_proves_nothing(self):
        """Zero sends tells us nothing about whether a send would be
        recorded, so the verdict is None rather than a reassuring True."""
        reads = []
        a, b, c = self.witness(0, 0, reads)
        with a, b, c:
            self.assertIsNone(tools._ledger_carries_sends("alpha"))

    def test_it_is_cached_so_fifty_accounts_cost_one_read(self):
        """The whole reason the per-account call was removed."""
        reads = []
        a, b, c = self.witness(494, 300, reads)
        with a, b, c:
            for _ in range(50):
                tools._ledger_carries_sends("alpha")
        self.assertEqual(len(reads), 1)

    def test_the_cache_expires(self):
        reads = []
        a, b, c = self.witness(494, 300, reads)
        with a, b, c:
            tools._ledger_carries_sends("alpha", now=1000.0)
            tools._ledger_carries_sends(
                "alpha", now=1000.0 + tools.LEDGER_WITNESS_TTL + 1)
        self.assertEqual(len(reads), 2)

    def test_an_unreadable_provider_leaves_it_unestablished(self):
        with mock.patch.object(tools.knowledge, "pack", lambda *a, **k: {
                "workspaces": {"alpha": {"provider_campaign_ids": ["491"]}}}), \
                mock.patch.object(tools.readback, "campaign_by_id",
                                  mock.Mock(side_effect=RuntimeError("no"))):
            self.assertIsNone(tools._ledger_carries_sends("alpha"))


# ================================ 2. PRECEDENCE

class DoNotContactOutranksAGoodOutcome(AccountStatus):

    def test_a_meeting_does_not_override_a_refusal(self):
        """An account that met us and then asked to be left alone is an
        account we may not write to. Ranking the meeting above that is how
        a good outcome becomes a reason to ignore a stop."""
        out = self.ask(
            [record(contacts=[contact(suppressed=True)],
                    events_=[touch(), reply_event()])],
            meetings=[{"domain": "acme.test", "date": "2026-09-20"}])
        self.assertEqual(out["status"], tools.DO_NOT_CONTACT)

    def test_a_meeting_outranks_a_reply(self):
        out = self.ask([record(events_=[touch(), reply_event()])],
                       meetings=[{"domain": "acme.test", "date": "2026-09-20"}])
        self.assertEqual(out["status"], tools.MEETING)

    def test_a_reply_outranks_a_linkedin_acceptance(self):
        out = self.ask([record(events_=[
            touch(kind=events.LINKEDIN_CONNECTED, channel="linkedin"),
            reply_event()])])
        self.assertEqual(out["status"], tools.REPLIED)

    def test_one_stopped_contact_of_two_is_not_do_not_contact(self):
        """The account is only closed when every contact is."""
        out = self.ask([record(
            contacts=[contact(key="ada", suppressed=True),
                      contact(key="ben")],
            events_=[touch(key="ben")])])
        self.assertEqual(out["status"], tools.SEQUENCED)


# ================================ 3. THE TWO WITH NO SOURCE

class WonAndLostAreNeverInvented(AccountStatus):

    def test_they_are_never_returned(self):
        for rows, meetings in (([record()], ()),
                               ([record(events_=[touch(), reply_event()])],
                                [{"domain": "acme.test"}])):
            out = self.ask(rows, meetings=meetings)
            self.assertNotIn(out["status"], (tools.WON, tools.LOST))

    def test_the_answer_names_the_gap(self):
        """Absence of a state is not evidence that it never happens, and
        the only way anybody outside can know is if the answer says so."""
        out = self.ask([record()])
        self.assertEqual(sorted(out["states_without_a_source"]),
                         sorted([tools.WON, tools.LOST]))
        self.assertIn("no source", out["note"])

    def test_the_vocabulary_is_all_eight(self):
        self.assertEqual(len(tools.ACCOUNT_STATES), 8)
        for name in ("untouched", "sequenced", "engaged", "replied",
                     "meeting", "won", "lost", "do_not_contact"):
            self.assertIn(name, tools.ACCOUNT_STATES)


# ================================ 4. THE SOURCE IS LABELLED

class DerivedSaysDerived(AccountStatus):

    def test_it_does_not_claim_to_be_the_production_object(self):
        out = self.ask([record(events_=[touch()])])
        self.assertTrue(
            out["source"]["not_production_account_status_object"])
        self.assertIn("account.graph()", out["source"]["status"])

    def test_the_status_carries_its_evidence(self):
        out = self.ask([record(events_=[touch()])])
        self.assertTrue(out["status_evidence"])
        self.assertIn("confirmed touch", " ".join(out["status_evidence"]))

    def test_an_unreadable_ledger_is_said_rather_than_read_as_no_meetings(self):
        def boom(workspace=None, **k):
            raise RuntimeError("ledger gone")
        scope = slackscope.Scope(slackscope.INTERNAL, source="test")
        with mock.patch.object(tools, "_records",
                               lambda slug: [record(events_=[touch()])]), \
                mock.patch.object(tools, "_default_workspace",
                                  lambda: "alpha"), \
                mock.patch("src.slackmeetings.by_domain", boom):
            out = tools.account_status(scope, "acme.test")
        self.assertIn("could not be read", out["source"]["status"])


# ================================ 5. CLIENT SCOPE

class AnotherClientsAccountReadsLikeNobodys(AccountStatus):

    def test_a_client_cannot_read_another_workspaces_domain(self):
        rows = [record(domain="acme.test", client="beta",
                       events_=[touch(), reply_event()])]
        out = self.ask(rows, scope=self.client("alpha"))
        self.assertEqual(out["matches"], 0)
        self.assertIn("no account matching", out["note"])

    def test_and_a_domain_nobody_has_reads_the_same(self):
        out = self.ask([], domain="nowhere.test", scope=self.client("alpha"))
        self.assertEqual(out["matches"], 0)
        self.assertIn("no account matching", out["note"])

    def test_the_two_answers_are_indistinguishable(self):
        """Word for word, because the difference between them is the leak."""
        theirs = self.ask([record(domain="acme.test", client="beta")],
                          scope=self.client("alpha"))
        nobodys = self.ask([], domain="acme.test",
                           scope=self.client("alpha"))
        self.assertEqual(theirs["note"], nobodys["note"])
        self.assertEqual(theirs["matches"], nobodys["matches"])

    def test_a_client_reads_its_own(self):
        out = self.ask([record(client="alpha", events_=[touch()])],
                       scope=self.client("alpha"))
        self.assertEqual(out["matches"], 1)
        self.assertEqual(out["status"], tools.SEQUENCED)

    def test_the_tool_is_registered_for_both_scopes(self):
        """A tool nothing can call is the failure mode of this whole
        session; the registry is where that is decided."""
        self.assertIn("account_status", tools.REGISTRY)
        _fn, _desc, scopes, argument = tools.REGISTRY["account_status"]
        self.assertIn(slackscope.CLIENT, scopes)
        self.assertIn(slackscope.INTERNAL, scopes)
        self.assertEqual(argument, "a domain")


# ================================ 6. THE DETAIL

class PersonasStepsTouchesAndReplies(AccountStatus):

    def test_the_step_is_the_last_confirmed_one(self):
        out = self.ask([record(events_=[
            touch(step=1, at="2026-09-20T09:00:00Z"),
            touch(step=2, at="2026-09-21T09:00:00Z")])])
        persona = out["personas"][0]
        self.assertEqual(persona["step"], 2)
        self.assertEqual(persona["touches_confirmed"], 2)

    def test_an_unconfirmed_attempt_is_invisible_here_and_it_says_so(self):
        """A LIMIT OF THE ANSWER, asserted rather than implied.

        `account.touches()` is built from `touch.CONFIRMING_EVENTS`, and
        all three of those map to a CONFIRMED state. So an attempt that was
        planned, held, blocked or failed produces NO touch at all - not an
        unconfirmed one. There is no attempted-vs-confirmed distinction to
        report through this reader, and an earlier draft of this tool
        carried a `touches_attempted` field that could never differ from
        `touches_confirmed`. A field that cannot vary is a claim nobody can
        check.

        What matters downstream: a person sitting on a held step reads
        exactly like a person whose sequence has not reached them.
        """
        out = self.ask([record(events_=[
            touch(step=1),
            # A held attempt, in the shape the event log would carry it.
            {"type": "step_held", "contact": "ada", "step": 2,
             "at": "2026-09-22T09:00:00Z", "channel": "email"}])])
        persona = out["personas"][0]
        self.assertEqual(persona["step"], 1)
        self.assertEqual(persona["touches_confirmed"], 1)
        self.assertNotIn("touches_attempted", persona)
        self.assertTrue(out["touches_are_confirmed_only"])
        self.assertIn("held step", out["touch_coverage_note"])

    def test_replies_are_counted_by_class(self):
        out = self.ask([record(events_=[
            touch(),
            reply_event(classification="positive"),
            reply_event(classification="out_of_office",
                        at="2026-09-22T11:00:00Z"),
            reply_event(classification="out_of_office",
                        at="2026-09-22T12:00:00Z")])])
        self.assertEqual(out["replies_by_class"],
                         {"positive": 1, "out_of_office": 2})

    def test_an_unclassified_reply_is_not_folded_into_a_class(self):
        out = self.ask([record(events_=[
            touch(), reply_event(classification=None)])])
        self.assertEqual(out["replies_by_class"], {"unclassified": 1})

    def test_one_reply_with_a_receipt_and_a_verdict_is_ONE_reply(self):
        """MEASURED LIVE, 2026-09-23, and it would have reached a client.

        `account.replies()` returns reply_received AND reply_classified as
        separate rows - it answers "what is on this record", not "how many
        replies". Counted per event, olv.global's single out-of-office came
        back as `{'unclassified': 1, 'out_of_office': 1}`: two replies, one
        of them apparently unlooked-at. Both halves false.
        """
        out = self.ask([record(events_=[
            touch(),
            # The receipt, as the watcher writes it: no classification.
            {"type": events.REPLY_RECEIVED, "contact": "ada",
             "at": "2026-09-22T10:00:00Z", "channel": "email"},
            # The verdict, moments later, on the same reply.
            {"type": events.REPLY_CLASSIFIED, "contact": "ada",
             "at": "2026-09-22T10:00:05Z", "channel": "email",
             "classification": "out_of_office"}])])
        self.assertEqual(out["replies_by_class"], {"out_of_office": 1})

    def test_a_receipt_with_no_verdict_is_still_reported(self):
        """The other half: a reply nobody has classified must not vanish
        just because the double-count was fixed."""
        out = self.ask([record(events_=[
            touch(),
            {"type": events.REPLY_RECEIVED, "contact": "ada",
             "at": "2026-09-22T10:00:00Z", "channel": "email"},
            {"type": events.REPLY_CLASSIFIED, "contact": "ada",
             "at": "2026-09-22T10:00:05Z", "channel": "email",
             "classification": "out_of_office"},
            {"type": events.REPLY_RECEIVED, "contact": "ada",
             "at": "2026-09-23T09:00:00Z", "channel": "email"}])])
        self.assertEqual(out["replies_by_class"],
                         {"out_of_office": 1, "unclassified": 1})

    def test_it_still_counts_right_after_production_fixes_the_source(self):
        """THE HANDOVER TEST, and it is the one that matters here.

        The operator has asked production to fix `account.replies()` at
        source: one row per reply, classified state as a FIELD. The moment
        that lands, the pairing compensation above stops being needed - and
        the naive form of it would start UNDER-counting silently. A contact
        with two classified replies and one nobody has looked at computes
        `spare = 1 - 2 = -1` and drops the unclassified one.

        Under-counting after somebody else's correct fix is a trap laid for
        them, so the shape is detected rather than assumed. This asserts the
        FIXED shape directly.
        """
        fixed_shape = [
            {"contact_key": "ada", "type": "reply_received",
             "classification": "out_of_office", "at": "2026-09-22T10:00:00Z"},
            {"contact_key": "ada", "type": "reply_received",
             "classification": "not_relevant", "at": "2026-09-22T11:00:00Z"},
            {"contact_key": "ada", "type": "reply_received",
             "classification": None, "at": "2026-09-22T12:00:00Z"},
        ]
        self.assertEqual(
            tools._reply_classes(fixed_shape),
            {"out_of_office": 1, "not_relevant": 1, "unclassified": 1})

    def test_the_naive_pairing_would_have_lost_that_unclassified_reply(self):
        """Names the failure the test above prevents, so nobody 'simplifies'
        the shape check away later."""
        paired_shape = [
            {"contact_key": "ada", "type": "reply_received",
             "classification": None, "at": "2026-09-22T10:00:00Z"},
            {"contact_key": "ada", "type": "reply_classified",
             "classification": "out_of_office", "at": "2026-09-22T10:00:05Z"},
            {"contact_key": "ada", "type": "reply_received",
             "classification": None, "at": "2026-09-22T11:00:00Z"},
            {"contact_key": "ada", "type": "reply_classified",
             "classification": "not_relevant", "at": "2026-09-22T11:00:05Z"},
        ]
        # Today's shape: two replies, both classified, no phantom.
        self.assertEqual(tools._reply_classes(paired_shape),
                         {"out_of_office": 1, "not_relevant": 1})

    def test_two_people_replying_are_two_replies(self):
        out = self.ask([record(
            contacts=[contact(key="ada"), contact(key="ben")],
            events_=[touch(),
                     reply_event(key="ada", classification="not_relevant"),
                     reply_event(key="ben", classification="not_relevant")])])
        self.assertEqual(out["replies_by_class"], {"not_relevant": 2})

    def test_the_last_touch_is_a_confirmed_one(self):
        out = self.ask([record(events_=[
            touch(step=1, at="2026-09-20T09:00:00Z")])])
        self.assertIsNotNone(out["last_touch"])
        self.assertEqual(out["last_touch"]["step"], 1)

    def test_no_confirmed_touch_says_so_rather_than_returning_a_planned_one(self):
        out = self.ask([record()])
        self.assertIsNone(out["last_touch"])
        self.assertIn("no confirmed touch", out["last_touch_note"])

    def test_suppressed_people_are_not_in_play(self):
        out = self.ask([record(
            contacts=[contact(key="ada", suppressed=True), contact(key="ben")],
            events_=[touch(key="ben")])])
        self.assertEqual(len(out["personas"]), 2)
        self.assertEqual(out["personas_in_play"], 1)

    def test_the_next_planned_touch_is_refused_rather_than_guessed(self):
        """It lives in the provider's queue, and the honest horizon is
        `weekly_plan`'s three days. A local guess would be our inference
        dressed as the provider's plan."""
        out = self.ask([record(events_=[touch()])])
        self.assertIsNone(out["next_planned_touch"])
        self.assertIn("weekly_plan", out["next_planned_touch_note"])

    def test_a_domain_is_required(self):
        scope = slackscope.Scope(slackscope.INTERNAL, source="test")
        self.assertIn("_error", tools.account_status(scope, None))


if __name__ == "__main__":
    unittest.main()


# ============ 7. AN UNANSWERABLE STATE IS NOT AN UNANSWERABLE ACCOUNT

class WhatSurvivesWhenTheStateCannotBeAsserted(AccountStatus):
    """OPERATOR, 2026-09-24: these questions answer FROM WHAT EXISTS.

    `account_status` used to `return` the moment `_account_state` came back
    None, on an `_error` key. That is not a cosmetic choice:
    `slackconversation`'s material builder renders an `_error` line **and
    discards the rest of the dict**. So "what is happening with <domain>"
    answered with one sentence about a ledger write-back and not one word
    about the account - not the personas, not the last confirmed touch, not
    the replies, not whether they had asked to be left alone.

    None of that depends on the ledger witness. It is all local state.

    **This module already holds the same line one level down**, where
    `unanswerable` is its own count and is never folded into `untouched`.
    These tests are that rule applied to the ANSWER rather than the tally.
    """

    def blind(self, rows, domain="acme.test"):
        """The witness says the ledger is NOT recording this workspace."""
        scope = slackscope.Scope(slackscope.INTERNAL, source="test")
        with mock.patch.object(tools, "_records", lambda slug: [
                r for r in rows if r.get("client") == slug]),                 mock.patch.object(tools, "_default_workspace",
                                  lambda: "alpha"),                 mock.patch.object(tools, "_ledger_carries_sends",
                                  lambda slug, now=None: False),                 mock.patch("src.slackmeetings.by_domain",
                           lambda workspace=None, **k: []):
            return tools.account_status(scope, domain)

    def trusting(self, rows, domain="acme.test"):
        scope = slackscope.Scope(slackscope.INTERNAL, source="test")
        with mock.patch.object(tools, "_records", lambda slug: [
                r for r in rows if r.get("client") == slug]),                 mock.patch.object(tools, "_default_workspace",
                                  lambda: "alpha"),                 mock.patch.object(tools, "_ledger_carries_sends",
                                  lambda slug, now=None: True),                 mock.patch("src.slackmeetings.by_domain",
                           lambda workspace=None, **k: []):
            return tools.account_status(scope, domain)

    def test_the_state_is_still_withheld(self):
        """FIRST, because everything below is only safe while this holds."""
        out = self.blind([record()])
        self.assertIsNone(out["status"])
        self.assertNotEqual(out.get("status"), tools.UNTOUCHED)

    def test_it_is_not_reported_as_a_failed_readback(self):
        out = self.blind([record()])
        self.assertNotIn("_error", out)
        self.assertTrue(out["status_unanswerable"])

    def test_the_personas_survive(self):
        out = self.blind([record(contacts=[contact(), contact(key="bo")])])
        self.assertEqual(len(out["personas"]), 2)
        self.assertEqual({p["contact"] for p in out["personas"]},
                         {"ada", "bo"})

    def test_the_confirmed_touches_survive(self):
        out = self.blind([record(events_=[touch(step=2)])])
        self.assertIsNotNone(out["last_touch"])
        self.assertEqual(out["personas"][0]["step"], 2)

    def test_the_replies_survive(self):
        out = self.blind([record(events_=[touch(), touch(
            kind=events.REPLY_RECEIVED, step=2)])])
        self.assertIn("replies_by_class", out)

    def test_the_caveats_travel_with_it(self):
        """The answer is wider now, so the things it cannot see have to be
        stated in it rather than implied by an absence."""
        out = self.blind([record()])
        self.assertTrue(out["touches_are_confirmed_only"])
        self.assertIn("CONFIRMED touches only", out["touch_coverage_note"])
        self.assertIn("states_without_a_source", out)

    def test_a_trusted_ledger_is_unchanged_by_any_of_this(self):
        """THE CONTROL. If the fall-through had broken the answering path,
        every test in section 1 would still pass - they use `ask`, which
        does not pin the witness."""
        out = self.trusting([record()])
        self.assertEqual(out["status"], tools.UNTOUCHED)
        self.assertNotIn("status_unanswerable", out)

    def test_the_readback_the_model_is_handed_carries_the_account(self):
        """END TO END through the real renderer.

        `tools.render` dumps the whole dict and drops nothing, so the
        defect was never a filter - it was that the fields did not EXIST.
        This asserts they reach the prompt.
        """
        # NO TOUCH. An account WITH one is answerable even while the
        # witness says no - "evidence present beats evidence missing" - so
        # a touched record would test the wrong branch, which is what the
        # first version of this did.
        out = self.blind([record(contacts=[contact(key="ada")])])
        self.assertIsNone(out["status"])
        text = tools.render([("account_status", "acme.test", out)])
        self.assertIn("cannot be asserted", text)
        self.assertIn("ada", text,
                      "the account itself never reached the model")

    def test_the_no_model_path_no_longer_answers_with_the_refusal_alone(self):
        """`deterministic_answer` renders an `_error` line INSTEAD of the
        readback. That is the path taken when the model is down, and it is
        where an `_error` on this tool cost the whole answer."""
        from src import slackconversation as conversation
        out = self.blind([record(contacts=[contact(key="ada")])])
        scope = slackscope.Scope(slackscope.INTERNAL, source="test")
        text = conversation.deterministic_answer(
            [("account_status", "acme.test", out)], scope)
        self.assertNotIn(
            "account_status: the account's STATE cannot", text,
            "the deterministic answer is the refusal line and nothing "
            "else, which is what `_error` on this tool used to produce")
