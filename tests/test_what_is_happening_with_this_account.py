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


# ================ 1b. THE PROVIDER IS THE OTHER WITNESS, AND IT KNOWS MORE

class TheLocalLogIsNotTheOnlyWitness(AccountStatus):
    """MEASURED ON THE LIVE ESTATE, 2026-09-23. Against 494
    provider-confirmed sends the day before, the local store carried:

        push_marked 1 · email_delivered 0 · linkedin_connected 0

    `account.graph()` is built from exactly those three events, so an
    account this workspace emailed yesterday reads `untouched` from local
    state alone. A first draft of this tool did precisely that over 400 live
    records: 399 untouched, 1 sequenced.

    Telling a client nothing has happened on an account we wrote to is the
    worst version of the confidently-empty failure, because it is confident,
    it is client-facing, and nothing errors.
    """

    def ask_with_provider(self, rows, sends, domain="acme.test", scope=None):
        scope = scope or slackscope.Scope(slackscope.INTERNAL, source="test")
        with mock.patch.object(tools, "_records", lambda slug: [
                r for r in rows if r.get("client") == slug]), \
                mock.patch.object(tools, "_default_workspace",
                                  lambda: "alpha"), \
                mock.patch.object(tools, "_provider_touches",
                                  lambda slug, emails: sends), \
                mock.patch("src.slackmeetings.by_domain",
                           lambda workspace=None, **k: []):
            return tools.account_status(scope, domain)

    SEND = {"campaign_id": "491", "email": "ada@acme.test",
            "sent_at": "2026-09-22T13:05:00Z", "status": "sent"}

    def test_a_provider_send_beats_an_empty_local_log(self):
        out = self.ask_with_provider([record()], [self.SEND])
        self.assertEqual(out["status"], tools.SEQUENCED)
        self.assertEqual(out["provider_confirmed_sends"], 1)

    def test_the_disagreement_is_reported_not_smoothed_over(self):
        """Somebody should learn that the local log is not recording
        sends. Quietly preferring the provider hides a broken writer."""
        out = self.ask_with_provider([record()], [self.SEND])
        self.assertIn("the local event log carries none",
                      out["witness_disagreement"])

    def test_no_provider_send_and_no_local_touch_is_untouched(self):
        out = self.ask_with_provider([record()], [])
        self.assertEqual(out["status"], tools.UNTOUCHED)
        self.assertNotIn("witness_disagreement", out)

    def test_an_unreadable_provider_is_not_an_untouched_account(self):
        """`None` is unreadable. Returning `untouched` here would be a
        guess dressed as an answer, in a client channel."""
        out = self.ask_with_provider([record()], None)
        self.assertIsNone(out["status"])
        self.assertIn("could not be read", out["_error"])

    def test_a_local_touch_stands_even_if_the_provider_is_unreadable(self):
        out = self.ask_with_provider([record(events_=[touch()])], None)
        self.assertEqual(out["status"], tools.SEQUENCED)

    def test_unreadable_queues_with_no_hits_never_read_as_zero(self):
        """`_provider_touches` itself: the one combination that must not
        come back as a clean empty list."""
        with mock.patch.object(tools.knowledge, "pack", lambda *a, **k: {
                "workspaces": {"alpha": {"provider_campaign_ids": ["491"]}}}), \
                mock.patch.object(tools.readback, "queue",
                                  mock.Mock(side_effect=RuntimeError("no"))):
            self.assertIsNone(
                tools._provider_touches("alpha", ["ada@acme.test"]))

    def test_a_readable_queue_with_no_match_is_an_honest_empty(self):
        with mock.patch.object(tools.knowledge, "pack", lambda *a, **k: {
                "workspaces": {"alpha": {"provider_campaign_ids": ["491"]}}}), \
                mock.patch.object(tools.readback, "queue",
                                  lambda cid: [{"lead": {"email": "x@y.test"},
                                                "sent_at": "2026-09-22"}]):
            self.assertEqual(
                tools._provider_touches("alpha", ["ada@acme.test"]), [])

    def test_a_queued_row_that_never_sent_is_not_a_touch(self):
        """`sent_at` is the witness, not membership. Enrolled is not sent."""
        with mock.patch.object(tools.knowledge, "pack", lambda *a, **k: {
                "workspaces": {"alpha": {"provider_campaign_ids": ["491"]}}}), \
                mock.patch.object(tools.readback, "queue",
                                  lambda cid: [{"lead": {"email":
                                                         "ada@acme.test"},
                                                "status": "scheduled"}]):
            self.assertEqual(
                tools._provider_touches("alpha", ["ada@acme.test"]), [])


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
