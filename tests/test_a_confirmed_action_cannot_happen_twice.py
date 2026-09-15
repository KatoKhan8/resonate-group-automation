#!/usr/bin/env python3
"""The duplication law, end to end, against the real modules.

    AUTHORIZED ACTION
      -> PROVIDER CONFIRMED SUCCESS
      -> DURABLE TOUCH RECORDED
      -> RESTART
      -> THE SAME LOGICAL ACTION ATTEMPTED AGAIN
      -> REFUSED

Every link of that chain was present on 2026-09-11 except the middle one, and
without it the two ends could not see each other.

`touch.CONFIRMING_EVENTS` maps `events.PUSH_MARKED` to SENT. Its only writer
was `push.mark_pushed`, and `push.run(live=True)` raises - so no live send
could reach it. `providerwrites.perform` settled the action ledger and
recorded nothing on the record. The ledger key is per STEP
(`rec:contact:step:channel`), so it refused a repeat of the same step and
nothing else: `push.already_pushed`, `eligibility._separation` and
`fatigue.contact_check` were all blind to a send that had actually happened,
and a different step to the same person passed every gate.

Two more things had to be true for the record of that touch to mean anything.
`store.refuse_history_loss` counted events rather than identifying them, so a
stale worker that appended one event of its own could erase a confirmed touch
at an equal count - and `store.transaction()`, the path the touch is written
on, ran no guards at all. Both are pinned here, because a touch that a
concurrent save can quietly delete is not a durable touch.
"""
import contextlib
import datetime
import unittest
from unittest import mock

from src import approval, account, actionledger, collision, eligibility, events
from src import executionguard, fatigue, linkedin, providerwrites, push, store
from src.providers import heyreach
from src import campaigns
from tests.base import QueueTest

# TASK-137: `LINKEDIN_ADD_LEAD` IS NOW CONDITIONALLY SUPPORTED, so `perform`
# refuses it unless a provider read proves the destination campaign cannot
# send. This module uses that operation as its vehicle for a different
# question, so it names a DRAFT destination and fakes the one read the
# condition makes. It does NOT stub the condition itself - the predicate runs,
# on a real status string. Every test here failed loudly when the gate landed,
# which is how it is known to be reached from this path.
DRAFT_DESTINATION = 599020
CANON = "productive-linkedin-production-v1"
# PAUSED, not DRAFT: the provider answers 400 "You cannot add new leads to
# a draft campaign", so DRAFT is the one state it refuses.
DRAFT_ROW = {"id": DRAFT_DESTINATION, "status": "PAUSED", "name": "test",
             "organizationUnitId": "174892"}
CANON_ROW = {"campaign_id": CANON, "client": "productive",
             "heyreach_campaign_id": str(DRAFT_DESTINATION),
             "provider_status_expected": "PAUSED",
             "provider_note": "{connection_note}",
             "provider_actions": ["CHECK_IS_CONNECTION", "MESSAGE"]}

OP = providerwrites.LINKEDIN_ADD_LEAD
PROFILE = "https://www.linkedin.com/in/dana-oyelaran"


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)



# `perform` refuses a prospect-facing write whose payload does not carry the
# words the authorization approved. These tests are about the ACTION LEDGER -
# that one confirmed action cannot happen twice - so they satisfy that check
# rather than trip it, or the words guard fires first and the refusal being
# measured never happens.
STEP = {"channel": "linkedin", "note": "a note somebody approved"}
APPROVED = {"note": STEP["note"]}

class Spy:
    """A transport that records its calls and never reaches a network."""

    def __init__(self, raises=None):
        self.calls = []
        self.raises = raises

    def __call__(self, payload=None):
        self.calls.append(payload)
        if self.raises:
            raise self.raises
        return {"ok": True}


class DuplicationTest(QueueTest):

    REC = "kw-1"
    CONTACT = "dana"
    STEP = "day3"

    def setUp(self):
        super().setUp()
        store.save([self.record()])

    def record(self, rid=None, **over):
        rec = dict(store.new_record(rid or self.REC, "cold", "productive",
                                    "Kestrel Wharf Studio",
                                    "kestrelwharf.test"),
                   contacts=[{"key": self.CONTACT, "name": "Dana Oyelaran",
                              "title": "Operations Director",
                              "linkedin": PROFILE}])
        rec.update(over)
        return rec

    def key_for(self, rid=None, step=None):
        return push.push_id({"id": rid or self.REC}, self.CONTACT,
                            step or self.STEP, "linkedin")

    def reserve(self, rid=None, step=None, campaign="canary"):
        key = self.key_for(rid, step)
        actionledger.reserve(
            key, channel="linkedin", workspace="productive",
            campaign_id=campaign, sender_id=116968, rec_id=rid or self.REC,
            contact_key=self.CONTACT, step_key=step or self.STEP,
            operation="linkedin_connection_request", fingerprint="fp-1",
            provider_workspace=10)
        return key

    def authorization(self, key, rid=None, step=None):
        return executionguard.Authorization(
            key=key, channel="linkedin",
            # The OPERATION this token drives, not the cadence step it came
            # from. A token is proof of the action it names.
            operation=OP,
            rec_id=rid or self.REC, contact_key=self.CONTACT,
            step_key=step or self.STEP, sender_id=116968,
            fingerprint=approval.fingerprint(STEP))

    @contextlib.contextmanager
    def enabled(self):
        """The sealed route opened, and only the freshness re-check stubbed.

        `revalidate` needs a whole approved estate and is pinned by call order
        in `test_a_stop_beats_an_authorization`, so stubbing it cannot hide
        its removal. Nothing else here is stubbed: the ledger, the store, the
        guards and `push.mark_pushed` are all the real ones.
        """
        with mock.patch.object(providerwrites, "SUPPORTED", (OP,)), \
             mock.patch.object(providerwrites,
                               "CAMPAIGN_LEVEL_STAGING_IS_PROVEN",
                               True), \
             mock.patch.object(heyreach, "campaign_read",
                               return_value=dict(DRAFT_ROW)), \
             mock.patch.object(campaigns, "require",
                               return_value=dict(CANON_ROW)), \
             mock.patch.object(executionguard, "revalidate",
                               lambda *a, **kw: True):
            yield

    def send(self, key, rid=None, step=None, readback=None, expected=None,
             raises=None):
        spy = Spy(raises=raises)
        with self.enabled():
            result = providerwrites.perform(
                OP, provider_campaign_id=DRAFT_DESTINATION, campaign=CANON,
                authorization=self.authorization(key, rid, step),
                transport=spy, step=STEP, payload=APPROVED,
                readback=lambda: (readback if readback is not None
                                  else {"leads": 1}),
                expected=expected if expected is not None else {"leads": 1})
        return result, spy

    def confirmed(self, rid=None):
        """Confirmed touches for this contact, read back FROM DISK."""
        rec = store.get(rid or self.REC)
        return account.touches(rec, self.CONTACT, confirmed_only=True)


class AFirstActionIsAllowed(DuplicationTest):
    """A. A guard that refuses the first action is an outage, not a guard."""

    def test_a_legitimate_action_passes_and_reaches_the_provider(self):
        key = self.reserve()
        result, spy = self.send(key)
        self.assertEqual(result["class"], providerwrites.ACCEPTED)
        self.assertEqual(len(spy.calls), 1)
        self.assertEqual(actionledger.state_of(key), actionledger.SENT)

    def test_nothing_is_recorded_before_the_action(self):
        self.reserve()
        self.assertEqual(self.confirmed(), [])
        self.assertFalse(push.already_pushed(store.get(self.REC),
                                             self.CONTACT, self.STEP))


class ConfirmedSuccessWritesExactlyOneTouch(DuplicationTest):
    """B. One provider-confirmed action, one durable touch. Not two, not none."""

    def test_a_confirmed_send_writes_the_canonical_touch(self):
        key = self.reserve()
        self.send(key)
        touches = self.confirmed()
        self.assertEqual(len(touches), 1)
        self.assertEqual(touches[0]["channel"], "linkedin")
        self.assertEqual(touches[0]["contact_key"], self.CONTACT)
        self.assertTrue(touches[0]["confirmed"])

    def test_it_is_the_event_the_rest_of_the_system_reads(self):
        key = self.reserve()
        self.send(key)
        kinds = [e["type"] for e in store.get(self.REC)["events"]]
        self.assertIn(events.PUSH_MARKED, kinds)
        self.assertEqual(kinds.count(events.PUSH_MARKED), 1)

    def test_recording_it_again_appends_nothing(self):
        """`events.record` dedupes on a deterministic id, so reconciliation
        may replay this safely. Exactly once means exactly once."""
        key = self.reserve()
        self.send(key)
        auth = self.authorization(key)
        providerwrites._record_confirmed_touch(auth)
        providerwrites._record_confirmed_touch(auth)
        self.assertEqual(len(self.confirmed()), 1)

    def test_the_step_is_marked_so_already_pushed_can_see_it(self):
        key = self.reserve()
        self.send(key)
        self.assertTrue(push.already_pushed(store.get(self.REC),
                                            self.CONTACT, self.STEP))


class TheTouchSurvivesARestart(DuplicationTest):
    """C. Written to disk, not to a process. A restart reads the same answer."""

    def test_it_is_on_disk_not_in_memory(self):
        key = self.reserve()
        self.send(key)
        # Nothing cached: read the file back exactly as a new process would.
        reloaded = {r["id"]: r for r in store.load()}[self.REC]
        confirmed = account.touches(reloaded, self.CONTACT,
                                    confirmed_only=True)
        self.assertEqual(len(confirmed), 1)

    def test_the_ledger_and_the_record_agree_after_a_reload(self):
        key = self.reserve()
        self.send(key)
        self.assertEqual(actionledger.state_of(key), actionledger.SENT)
        self.assertEqual(len(self.confirmed()), 1)


class TheSecondAttemptIsRefused(DuplicationTest):
    """D. The whole point. After a confirmed send, ask again and be told no."""

    def test_the_same_key_cannot_be_reserved_again(self):
        key = self.reserve()
        self.send(key)
        with self.assertRaises(actionledger.ActionRefused):
            self.reserve()

    def test_the_ledger_refuses_before_any_provider_write(self):
        """Refused BEFORE the transport, which is the only refusal that
        counts: a message cannot be unsent."""
        key = self.reserve()
        _, first = self.send(key)
        self.assertEqual(len(first.calls), 1)
        spy = Spy()
        with self.enabled():
            with self.assertRaises(providerwrites.WriteRefused):
                providerwrites.perform(
                    OP, provider_campaign_id=DRAFT_DESTINATION, campaign=CANON,
                    authorization=self.authorization(key),
                    transport=spy, step=STEP, payload=APPROVED,
                    readback=lambda: {"leads": 1},
                    expected={"leads": 1})
        self.assertEqual(spy.calls, [], "the provider was called a second time")

    def test_a_fresh_authorization_object_does_not_help(self):
        """A new token for a settled action is still a settled action."""
        key = self.reserve()
        self.send(key)
        spy = Spy()
        with self.enabled():
            with self.assertRaises(providerwrites.WriteRefused):
                providerwrites.perform(
                    OP, provider_campaign_id=DRAFT_DESTINATION, campaign=CANON,
                    authorization=self.authorization(key),
                    transport=spy, step=STEP, payload=APPROVED,
                    readback=lambda: {"leads": 1},
                    expected={"leads": 1})
        self.assertEqual(spy.calls, [])

    def test_a_sent_key_cannot_be_settled_into_something_reservable(self):
        """The rule was walkable in two steps instead of one.

        `reserve` refuses a key in `UNRESERVABLE`, and `SENT` is in it. But
        `settle` took any settlement at all, and `state_of` reads the LATEST
        row - so `settle(key, FAILED)` after a confirmed send left the state
        as `failed`, which is in neither BLOCKING nor TERMINAL, and the key
        was reservable again. The durable record that a real person had been
        contacted was gone, which is precisely what this ledger exists to
        keep.
        """
        key = self.reserve()
        self.send(key)
        self.assertEqual(actionledger.state_of(key), actionledger.SENT)

        with self.assertRaises(actionledger.ActionRefused) as caught:
            actionledger.settle(key, actionledger.FAILED, why="retrying")
        self.assertIn("terminal", str(caught.exception))

        self.assertEqual(actionledger.state_of(key), actionledger.SENT,
                         "the refused settlement changed the state anyway")
        with self.assertRaises(actionledger.ActionRefused):
            self.reserve()

    def test_settling_sent_twice_is_still_idempotent(self):
        """The other half: a repeated confirmation of the SAME outcome is a
        duplicate report, not a regression, and must not raise."""
        key = self.reserve()
        self.send(key)
        again = actionledger.settle(key, actionledger.SENT, why="same news")
        self.assertEqual(again["state"], actionledger.SENT)
        self.assertEqual(actionledger.state_of(key), actionledger.SENT)

    def test_the_person_is_visible_to_fatigue_afterwards(self):
        """A DIFFERENT step has a different ledger key, so the ledger cannot
        refuse it. The confirmed touch is what does."""
        key = self.reserve()
        self.send(key)
        verdict = fatigue.contact_check(store.get(self.REC), self.CONTACT,
                                        at=utcnow().isoformat())
        self.assertEqual(verdict["state"], fatigue.BLOCK)
        self.assertIn("since the last touch",
                      " ".join(f["why"] for f in verdict["findings"]))


class AnAliasIsTheSamePerson(DuplicationTest):
    """E. One human, six spellings of one URL. All one identity."""

    ALIASES = (
        "https://www.linkedin.com/in/dana-oyelaran",
        "https://www.linkedin.com/in/dana-oyelaran/",
        "http://linkedin.com/in/Dana-Oyelaran",
        "https://uk.linkedin.com/in/dana-oyelaran?trk=nav",
        "https://www.linkedin.com/in/dana-oyelaran#experience",
        "https://www.linkedin.com/in/dana%2Doyelaran",
    )

    def test_every_spelling_collapses_to_one_key(self):
        keys = {collision.profile_slug(u) for u in self.ALIASES}
        self.assertEqual(len(keys), 1, f"aliases split into {keys}")
        self.assertEqual(keys.pop(), "dana-oyelaran")

    def test_the_collision_gate_and_the_canonicaliser_agree(self):
        """Two definitions of one identity is the defect. A fragment or a
        percent-encoded dash used to clear the wrong-person gate."""
        for url in self.ALIASES:
            with self.subTest(url=url[:48]):
                self.assertEqual(collision.profile_slug(url),
                                 linkedin.key(url))

    def test_a_non_profile_url_is_unanswerable_not_equal(self):
        """Two blanks must not compare equal and clear each other."""
        for url in ("https://www.linkedin.com/", "",
                    "https://www.linkedin.com/company/kestrel"):
            with self.subTest(url=url):
                self.assertEqual(collision.profile_slug(url), "")


class AnotherCampaignIsNotAFreshStart(DuplicationTest):
    """F. The ledger key carries the step and the campaign does not appear in
    it at all, so a second campaign cannot be stopped by the ledger. Person
    level is what has to hold."""

    def test_a_different_step_has_a_different_ledger_key(self):
        """Stated as a fact about the design, so the next reader knows why the
        confirmed touch carries the weight it does."""
        first = self.reserve()
        self.assertNotEqual(first, self.key_for(step="day8"))

    def test_the_confirmed_touch_refuses_the_second_campaign(self):
        key = self.reserve()
        self.send(key)
        rec = store.get(self.REC)
        verdict = fatigue.contact_check(rec, self.CONTACT,
                                        at=utcnow().isoformat())
        self.assertEqual(verdict["state"], fatigue.BLOCK)

    def test_the_touch_is_keyed_to_the_person_not_the_campaign(self):
        key = self.reserve()
        self.send(key)
        touches = account.touches(store.get(self.REC), self.CONTACT,
                                  confirmed_only=True)
        self.assertEqual([t["contact_key"] for t in touches], [self.CONTACT])


class AFailedActionWritesNoTouch(DuplicationTest):
    """G. A touch is a thing that happened. A failure is not one."""

    def test_a_transport_exception_records_nothing(self):
        key = self.reserve()
        with self.assertRaises(providerwrites.WriteUnverified):
            self.send(key, raises=TimeoutError("read timed out"))
        self.assertEqual(self.confirmed(), [])
        self.assertEqual(actionledger.state_of(key), actionledger.UNRESOLVED)

    def test_a_readback_that_disagrees_records_nothing(self):
        key = self.reserve()
        with self.assertRaises(providerwrites.WriteUnverified):
            self.send(key, readback={"leads": 0}, expected={"leads": 1})
        self.assertEqual(self.confirmed(), [])
        self.assertEqual(actionledger.state_of(key), actionledger.UNRESOLVED)

    def test_an_empty_expectation_certifies_nothing(self):
        """Asking for nothing is not the same as getting what you asked for.
        `{}` used to classify ACCEPTED and settle the ledger to SENT."""
        key = self.reserve()
        with self.assertRaises(providerwrites.WriteUnverified):
            self.send(key, readback={"leads": 1}, expected={})
        self.assertEqual(self.confirmed(), [])
        self.assertEqual(actionledger.state_of(key), actionledger.UNRESOLVED)


class AnAmbiguousResultIsNotRetried(DuplicationTest):
    """H. The provider may or may not have acted. That is not a reason to
    find out by doing it again."""

    def test_unresolved_cannot_be_reserved_again(self):
        key = self.reserve()
        with self.assertRaises(providerwrites.WriteUnverified):
            self.send(key, raises=TimeoutError("read timed out"))
        with self.assertRaises(actionledger.ActionRefused):
            self.reserve()

    def test_unresolved_never_becomes_clear_on_its_own(self):
        key = self.reserve()
        with self.assertRaises(providerwrites.WriteUnverified):
            self.send(key, raises=TimeoutError("timed out"))
        self.assertEqual(actionledger.state_of(key), actionledger.UNRESOLVED)
        with self.assertRaises(Exception):
            actionledger.require_clear(key)

    def test_a_second_attempt_never_reaches_the_transport(self):
        key = self.reserve()
        with self.assertRaises(providerwrites.WriteUnverified):
            self.send(key, raises=TimeoutError("timed out"))
        spy = Spy()
        with self.enabled():
            with self.assertRaises(providerwrites.WriteRefused):
                providerwrites.perform(
                    OP, provider_campaign_id=DRAFT_DESTINATION, campaign=CANON,
                    authorization=self.authorization(key),
                    transport=spy, step=STEP, payload=APPROVED,
                    readback=lambda: {"leads": 1},
                    expected={"leads": 1})
        self.assertEqual(spy.calls, [])


class AStopOutranksTheCadence(DuplicationTest):
    """I. Recording touches must not have promoted cadence above a reply."""

    def test_a_reply_blocks_the_next_step(self):
        rec = self.record()
        rec["contacts"][0]["stopped"] = True
        store.save([rec])
        verdict = eligibility.decide(store.get(self.REC),
                                     store.get(self.REC)["contacts"][0],
                                     "day8", channel="linkedin")
        self.assertNotEqual(verdict.get("state"), "eligible")

    def test_a_pause_blocks_the_next_step(self):
        rec = self.record()
        rec["paused"] = {"why": "they replied", "at": utcnow().isoformat()}
        store.save([rec])
        verdict = eligibility.decide(store.get(self.REC),
                                     store.get(self.REC)["contacts"][0],
                                     "day8", channel="linkedin")
        self.assertNotEqual(verdict.get("state"), "eligible")

    def test_a_confirmed_touch_does_not_lift_a_stop(self):
        key = self.reserve()
        self.send(key)
        rec = store.get(self.REC)
        rec["contacts"][0]["stopped"] = True
        store.save([rec])
        verdict = eligibility.decide(store.get(self.REC),
                                     store.get(self.REC)["contacts"][0],
                                     "day8", channel="linkedin")
        self.assertNotEqual(verdict.get("state"), "eligible")


class AStaleWorkerCannotEraseIt(DuplicationTest):
    """J. A touch a concurrent save can delete is not a durable touch.

    `refuse_history_loss` counted events, and fired only when the new snapshot
    held FEWER. A stale worker appends events of its own, so one append
    against one lost touch was a tie - and a tie passed.
    """

    def test_an_equal_count_snapshot_cannot_drop_the_touch(self):
        key = self.reserve()
        self.send(key)
        stale = self.record()          # a copy loaded before the send
        # An event of its OWN, which is what makes the counts tie: a stale
        # worker is a worker doing work. Verified 1 event against 1.
        events.record(stale, events.DRAFT_GENERATED, contact_key=self.CONTACT)
        with self.assertRaises(store.HistoryLost):
            store.save([stale])
        self.assertEqual(len(self.confirmed()), 1)

    def test_a_smaller_snapshot_is_still_refused(self):
        key = self.reserve()
        self.send(key)
        with self.assertRaises(store.HistoryLost):
            store.save([self.record()])
        self.assertEqual(len(self.confirmed()), 1)

    def test_a_legitimate_append_still_writes(self):
        """A guard that refuses every write is an outage."""
        key = self.reserve()
        self.send(key)
        rec = store.get(self.REC)
        rec.setdefault("log", []).append({"what": "something later"})
        store.save([rec])
        self.assertEqual(len(self.confirmed()), 1)

    def test_the_transaction_path_runs_the_guard_too(self):
        """The touch is written inside `store.transaction()`, which ran no
        guards at all - so the write that records it was itself the write
        least protected from erasing something."""
        key = self.reserve()
        self.send(key)
        with self.assertRaises(store.HistoryLost):
            with store.transaction() as recs:
                recs[:] = [self.record()]
        self.assertEqual(len(self.confirmed()), 1)


class TheWeekIsMeasuredFromTheProposedAction(DuplicationTest):
    """The window origin, pinned at its boundary.

    `_within_week(confirmed, at or last["at"])` anchored to the most recent
    touch when no `at` was given, and `_hours_between` returns an ABSOLUTE
    difference - so the window was seven days either side of a historical
    anchor rather than a trailing week, and three touches a year ago stayed
    "three touches this week" for ever.
    """

    def touched_at(self, *hours_ago):
        rec = self.record()
        for n, hours in enumerate(hours_ago, start=1):
            events.record(rec, events.PUSH_MARKED, contact_key=self.CONTACT,
                          channel="linkedin", step=f"day{n}", day=n,
                          at=(utcnow()
                              - datetime.timedelta(hours=hours)).isoformat(),
                          sender_id="anna", id=f"t{n}")
        return rec

    def test_inside_the_week_counts(self):
        rec = self.touched_at(167, 100, 30)
        verdict = fatigue.contact_check(rec, self.CONTACT,
                                        at=utcnow().isoformat())
        self.assertEqual(verdict["state"], fatigue.BLOCK)
        self.assertIn("in the last week",
                      " ".join(f["why"] for f in verdict["findings"]))

    def test_outside_the_week_does_not(self):
        rec = self.touched_at(169, 200, 400)
        verdict = fatigue.contact_check(rec, self.CONTACT,
                                        at=utcnow().isoformat())
        self.assertNotIn("in the last week",
                         " ".join(f["why"] for f in verdict["findings"]))

    def test_a_year_old_cluster_is_not_this_week(self):
        rec = self.touched_at(8800, 8790, 8780)
        verdict = fatigue.contact_check(rec, self.CONTACT,
                                        at=utcnow().isoformat())
        self.assertNotIn("in the last week",
                         " ".join(f["why"] for f in verdict["findings"]))

    def test_an_absent_at_means_now_not_the_last_touch(self):
        rec = self.touched_at(8800, 8790, 8780)
        self.assertEqual(fatigue.contact_check(rec, self.CONTACT)["state"],
                         fatigue.OK)


if __name__ == "__main__":
    unittest.main()
