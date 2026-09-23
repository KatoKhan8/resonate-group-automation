#!/usr/bin/env python3
"""A batch holds a whole-queue snapshot for its whole length. What arrives
while it is running must still be there when it finishes.

`test_a_stop_survives_a_concurrent_run` closed the case where a stale snapshot
LIFTS a stop on a record it already held: `refuse_history_loss` compares the
events and the stop flags of every record present in both copies. Both guards
say, in as many words, that a record ABSENT from the new set is somebody
else's rule - "removal is a different rule with a different guard". There is
no such guard, and `run.run` is the caller that needs it: it loads every
record once, walks the batch across minutes of provider I/O, and writes the
whole snapshot back at `CHECKPOINT_EVERY` records and again at the end, with
no digest and no merge.

REPRODUCED on 2026-09-12 against an isolated estate, two processes, nothing
crashing and no race to lose:

  * a record ingested mid-batch - carrying paid verification evidence, an
    unsubscribed contact and a reply event - was gone after the next
    checkpoint. Neither guard objected: both skip records that are absent.
  * `store.drop(rid, "competitor - do not contact")`, applied mid-batch, came
    back as `state: queued` with `drop_reason: None`. A drop is the sanctioned
    way to remove a record from a batch, and the batch undid it. It is not
    caught because `drop` writes to `log`, and the history guard reads
    `events` and the contact stop flags.
  * three decision-makers bought mid-batch for a record the batch was holding
    were erased. `refuse_evidence_loss` indexes `verification.evidence`, so a
    person-level purchase that has not been verified yet is unprotected.

`repo.save_records` already shows what the right shape is - it takes
`store.transaction()`, upserts by id and extends with what it has not seen -
so the runner is the outlier rather than the pattern.

The last class here is the other half of the same window: `checkpoint()` is
called from the stage loop with no `try`, so ANY refusal from `store.save` -
`QueueLocked` after ten seconds of contention, `HistoryLost` from a reply that
landed - aborts the whole run and discards every record's work, including the
records that came before the refusal. Measured: a reply persisted 1s into a
twelve-record batch left zero records enriched, while the durable spend ledger
kept every charge. That is the exact loss `CHECKPOINT_EVERY` was chosen from,
made total instead of bounded to four records.
"""
import os
import unittest
from unittest import mock

from src import actionledger, campaigns, enrich, identity, push, run, store
from tests.base import QueueTest, refuse_writes, write_as_another_process


def a_record(rid="acct-one", domain="one.example"):
    rec = store.new_record(rid, "cold", "acme", "Company %s" % rid, domain)
    rec["contacts"] = [{"key": "dana-example", "name": "Dana Example",
                        "email": "dana@%s" % domain,
                        "title": "Head of Operations"}]
    return rec


class WhatArrivedDuringTheBatch(QueueTest):
    """`QueueTest` rather than `use_directory`, which redirects the whole
    process and does not put it back. The two state files these tests reach
    besides the queue default to the queue's own directory, so they only have
    to be un-pinned for the length of the test."""

    def setUp(self):
        super().setUp()
        self._pinned = {k: os.environ.pop(k, None)
                        for k in ("CAMPAIGNS", "ACTION_LEDGER")}
        store.append([a_record("r0"), a_record("r1", "two.example")])

    def tearDown(self):
        for key, value in self._pinned.items():
            if value is not None:
                os.environ[key] = value
        super().tearDown()

    def test_a_record_ingested_mid_batch_survives_the_checkpoint(self):
        snapshot = store.load()                    # the batch loads the queue

        arrived = a_record("r-arrived", "arrived.example")
        arrived["contacts"][0]["unsubscribed"] = True
        arrived["events"] = [{"id": "ev-reply", "type": "reply_received",
                              "contact": "dana-example", "at": store.now()}]
        store.append([arrived])                    # a second process ingests

        store.save(snapshot)                       # the batch checkpoints

        self.assertIsNotNone(
            store.get("r-arrived"),
            "the batch wrote a snapshot taken before this record existed and "
            "deleted it, with its reply and its unsubscribe")

    def test_a_drop_applied_mid_batch_is_not_reverted(self):
        snapshot = store.load()
        store.drop("r1", "competitor - do not contact")

        store.save(snapshot)

        self.assertEqual(store.get("r1")["state"], "dropped")
        self.assertEqual(store.get("r1")["drop_reason"],
                         "competitor - do not contact")

    def test_contacts_bought_mid_batch_are_not_erased(self):
        snapshot = store.load()
        with store.lock():
            live = store.load()
            store.get("r0", live)["contacts"].extend([
                {"key": "sam-example", "name": "Sam Example",
                 "email": "sam@one.example", "title": "Director"},
                {"key": "ali-example", "name": "Ali Example",
                 "email": "ali@one.example", "title": "Director"}])
            write_as_another_process(live)

        store.save(snapshot)

        self.assertEqual(
            len(store.get("r0")["contacts"]), 3,
            "two paid decision-makers with no verification evidence yet were "
            "erased by the batch snapshot; only evidence is guarded")


class ABatchCheckpointsMoreThanOnce(QueueTest):
    """The merge above is right for ONE checkpoint. A batch fires many.

    The snapshot's baseline is what tells an edit this caller made from a
    stale copy of somebody else's. If it stays at the opening read, then at
    every later checkpoint the caller re-asserts every field it has ever
    touched rather than the ones it has touched since - and `state` is the
    field the enrich stage always writes. So the drop reversion the merge was
    built to stop comes back through the second checkpoint, with a window of
    the whole batch instead of one interval.

    The baseline therefore moves to what was just written, and only when the
    write actually happened.
    """

    def setUp(self):
        super().setUp()
        self._pinned = {k: os.environ.pop(k, None)
                        for k in ("CAMPAIGNS", "ACTION_LEDGER")}
        store.append([a_record("r0"), a_record("r1", "two.example")])

    def tearDown(self):
        for key, value in self._pinned.items():
            if value is not None:
                os.environ[key] = value
        super().tearDown()

    def test_a_drop_after_the_first_checkpoint_is_not_reverted_by_the_second(self):
        held = store.load()                       # the batch loads once
        store.get("r1", held)["state"] = "enriched"
        store.save(held)                          # checkpoint 1
        self.assertEqual(store.get("r1")["state"], "enriched")

        store.drop("r1", "competitor - do not contact")    # another process

        store.get("r0", held)["state"] = "enriched"        # more batch work
        store.save(held)                          # checkpoint 2

        row = store.get("r1")
        self.assertEqual(row["state"], "dropped",
                         "checkpoint 2 re-asserted an edit it had already "
                         "persisted, and reverted the drop")
        self.assertEqual(row["drop_reason"], "competitor - do not contact")
        self.assertEqual(store.get("r0")["state"], "enriched",
                         "the batch's own later work was lost")

    def test_a_refused_checkpoint_leaves_the_edit_pending(self):
        """The other half of the ordering: rebasing before the write would
        make a refused checkpoint look persisted, and the retry would stop
        re-asserting it."""
        held = store.load()
        store.get("r0", held)["state"] = "enriched"

        restore = refuse_writes()
        try:
            with self.assertRaises(store.QueueLocked):
                store.save(held)
        finally:
            restore()

        store.save(held)                          # the next checkpoint retries
        self.assertEqual(store.get("r0")["state"], "enriched",
                         "a refused write rebased anyway, so the retry "
                         "thought the edit was already on disk")

    def test_the_shared_serialisation_produces_the_same_baseline(self):
        """`merge_onto` hands `rebase` the serialisation it already computed,
        because doing it twice was 18-28% of the cost of a save and `save` is
        98% of the wall time of a resumed run. An optimisation on the field
        that decides whether a drop gets reverted has to produce exactly the
        same answer as the slow path, so that is asserted rather than
        assumed."""
        held = store.load()
        store.get("r0", held)["state"] = "enriched"
        store.save(held)
        shared = dict(held.baseline)

        again = store.load()
        store.get("r0", again)["state"] = "enriched"
        again._serialised = None          # force the recompute
        store.Snapshot.rebase(again)
        self.assertEqual(shared, again.baseline)

    def test_a_refused_write_leaves_no_stale_handover(self):
        """The hazard the handover introduces: `merge_onto` runs, the write
        refuses, `rebase` is never called. The serialisation it handed over
        must not survive to be believed by a later rebase, or the edit would
        look persisted when nothing was written."""
        held = store.load()
        store.get("r0", held)["state"] = "enriched"

        restore = refuse_writes()
        try:
            with self.assertRaises(store.QueueLocked):
                store.save(held)
        finally:
            restore()

        store.save(held)
        self.assertEqual(store.get("r0")["state"], "enriched",
                         "the refused write's handover was believed, so the "
                         "retry thought the edit was already on disk")

    def test_a_row_with_no_id_is_refused_rather_than_vanishing(self):
        """A row the merge cannot address was written nowhere and raised
        nothing, which is the failure mode this whole class exists to remove."""
        held = store.load()
        held.append({"company": "no id here"})
        with self.assertRaises(ValueError):
            store.save(held)
        self.assertEqual(len(store.load()), 2, "the file was written anyway")


class EveryPerRecordStageCheckpoints(QueueTest):
    """`CHECKPOINT_EVERY` is worth nothing to a stage that never calls it.

    `stage_enrich` and `stage_qualify` took a `checkpoint` and used it.
    `stage_personas` and `stage_generate` did not take one at all, and `run()`
    called them without one - so a kill inside them re-did everything they had
    done. MEASURED on a 1,000-record estate: 503 records worked, ZERO saves.

    `generate` is the expensive one: it is the model stage, so the work lost
    is the work that cost money and minutes. Both take a checkpoint now, and
    the assertion below is on the stage functions rather than on `run()`,
    because what broke was the argument not being passed.
    """

    def setUp(self):
        super().setUp()
        self._pinned = {k: os.environ.pop(k, None)
                        for k in ("CAMPAIGNS", "ACTION_LEDGER")}
        store.append([a_record("r%d" % n, "co%d.example" % n) for n in range(6)])

    def tearDown(self):
        for key, value in self._pinned.items():
            if value is not None:
                os.environ[key] = value
        super().tearDown()

    def test_every_per_record_stage_accepts_a_checkpoint(self):
        import inspect
        for name in ("stage_enrich", "stage_qualify", "stage_personas",
                     "stage_generate"):
            with self.subTest(stage=name):
                params = inspect.signature(getattr(run, name)).parameters
                self.assertIn("checkpoint", params,
                              f"{name} cannot persist anything mid-stage")

    def test_personas_calls_the_checkpoint_it_is_given(self):
        calls = {"n": 0}
        recs = store.load()
        run.stage_personas(recs, [], checkpoint=lambda: calls.__setitem__(
            "n", calls["n"] + 1))
        self.assertGreater(calls["n"], 0,
                           "stage_personas took a checkpoint and never called "
                           "it, which is the same as not taking one")

    def test_generate_calls_the_checkpoint_it_is_given(self):
        calls = {"n": 0}
        recs = store.load()
        run.stage_generate(recs, None, False, [],
                           checkpoint=lambda: calls.__setitem__(
                               "n", calls["n"] + 1))
        self.assertGreater(calls["n"], 0,
                           "the model stage cannot persist what it paid for")

    def test_run_passes_one_to_both(self):
        """The half that actually broke: the stages were fixed once before and
        `run()` still called them without the argument."""
        seen = {}
        for name in ("stage_personas", "stage_generate"):
            real = getattr(run, name)

            def spy(*a, _name=name, _real=real, **kw):
                seen[_name] = kw.get("checkpoint")
                return _real(*a, **kw)

            setattr(run, name, spy)
            self.addCleanup(setattr, run, name, real)
        run.run(stages=("personas", "generate"), spend=False)
        for name in ("stage_personas", "stage_generate"):
            self.assertIsNotNone(seen.get(name),
                                 f"run() called {name} with no checkpoint")


class ACheckpointRefusalIsNotABatchFailure(QueueTest):
    """One refused write must cost the records it covers, not the batch.

    `run.run`'s own docstring: "A stage that fails on one record fails that
    record only: the other 499 carry on." `checkpoint()` is outside that
    promise - it is called from the stage loop with no handler, so the refusal
    leaves the process by way of the stage, the timer and `run()` itself.
    """

    def setUp(self):
        super().setUp()
        self._pinned = {k: os.environ.pop(k, None)
                        for k in ("CAMPAIGNS", "ACTION_LEDGER")}
        store.append([a_record("r%d" % n, "co%d.example" % n)
                      for n in range(12)])

    def tearDown(self):
        for key, value in self._pinned.items():
            if value is not None:
                os.environ[key] = value
        super().tearDown()

    def test_a_locked_queue_does_not_discard_the_whole_batch(self):
        real_save, calls = store.save, {"n": 0}

        def flaky(recs, *a, **kw):
            calls["n"] += 1
            if calls["n"] == 1:                    # ten seconds of contention
                raise store.QueueLocked(
                    "another process has held queue.jsonl.lock for more than "
                    "10.0s. Nothing was written.")
            return real_save(recs, *a, **kw)

        def planned(rec, config=None):
            rec.setdefault("company_facts", {})["probed"] = True
            return []

        with mock.patch.object(store, "save", flaky), \
                mock.patch.object(enrich, "plan", planned):
            report = run.run(stages=("enrich",), spend=False)

        self.assertIn("enrich", report)
        probed = [r["id"] for r in store.load()
                  if (r.get("company_facts") or {}).get("probed")]
        self.assertTrue(
            probed,
            "one refused checkpoint aborted the run and discarded every "
            "record's work, including the eleven records that were never "
            "covered by the refused write")


class ACampaignStopSurvivesAConcurrentWrite(QueueTest):
    """`campaigns.jsonl` has no `refuse_history_loss`.

    `interactions.decide` loads the whole campaign file, runs
    `orchestrator.decide` and writes the snapshot back with
    `campaigns.save(rows)`; `repo.save_campaign` does the row-scoped version of
    the same thing with a row object loaded before the work started. Either
    one erases a `freeze` written in between - and `freeze` is the stop button
    that `eligibility` reads to block every step of the campaign.
    """

    def setUp(self):
        super().setUp()
        self._pinned = {"CAMPAIGNS": os.environ.pop("CAMPAIGNS", None)}
        campaigns.save([campaigns.new_campaign("cmp-1", "acme", "Batch One")])

    def tearDown(self):
        if self._pinned["CAMPAIGNS"] is not None:
            os.environ["CAMPAIGNS"] = self._pinned["CAMPAIGNS"]
        super().tearDown()

    def test_a_freeze_is_not_erased_by_a_stale_campaign_snapshot(self):
        rows = campaigns.load()                    # the approver's snapshot

        with campaigns.transaction() as live:      # somebody hits stop
            campaigns.freeze(campaigns.get("cmp-1", live),
                             "client asked us to stop today", by="operator")
        self.assertTrue(campaigns.is_frozen(campaigns.get("cmp-1")))

        held = campaigns.get("cmp-1", rows)
        held["approval"] = {"by": "reviewer", "at": store.now()}
        campaigns.save(rows)                       # the approver writes back

        self.assertTrue(
            campaigns.is_frozen(campaigns.get("cmp-1")),
            "the approval write lifted a freeze nobody lifted")


class OneHumanIsOneProspect(QueueTest):
    """The ledger key is per RECORD, so one person in two records is two keys.

    `push.push_id` is `rec:contact:step:channel`, and `actionledger.reserve`
    refuses a repeat of a KEY. So the same human, reachable through two queue
    records - the account appeared twice in the upload under two domains, or a
    parent and a subsidiary - is two reservations and two prospect-facing
    actions. `collision` catches this by READING THE PROVIDER, which is
    exactly what is unavailable in the timeout and crash cases this ledger
    exists for.

    The ledger already computes the answer and does not consult it:
    `contacts_reached` returns `{'dana-example'}` after the first send.

    What reserve needs is a canonical person identity rather than the
    within-record contact key - `agencydnc.keys_for` already derives one from
    the email and the LinkedIn URL - because a name slug alone would make two
    different people called Dana Example block each other. Both contacts here
    carry the same strong identity, so they are the same human under any
    canonicalisation.
    """

    def setUp(self):
        super().setUp()
        self._pinned = {"ACTION_LEDGER": os.environ.pop("ACTION_LEDGER", None)}
        self.common = dict(channel="linkedin", workspace="acme",
                           campaign_id="cmp-1", sender_id="snd-1",
                           step_key="s1", operation="heyreach.add_lead",
                           fingerprint="fp-1")

    def tearDown(self):
        if self._pinned["ACTION_LEDGER"] is not None:
            os.environ["ACTION_LEDGER"] = self._pinned["ACTION_LEDGER"]
        super().tearDown()

    @unittest.expectedFailure
    def test_a_second_record_may_not_reserve_the_same_human(self):
        """ABSENT - `reserve` has no canonical person to refuse on.

        Not data loss, and not fixed with the three defects above: this one is
        duplicate outreach, and closing it means giving the ledger a person
        identity rather than a within-record contact key. Left red and named
        rather than quietly dropped - the day `reserve` keys on
        `identity.contact_key`, this turns into an unexpected success and says
        so. PRODUCT-GAPS.md carries the entry.
        """
        person = {"name": "Dana Example", "email": "dana@one.example",
                  "linkedin": "https://www.linkedin.com/in/dana-example"}
        key = identity.contact_key(dict(person))

        first = push.push_id({"id": "acct-one"}, key, "s1", "linkedin")
        actionledger.reserve(first, rec_id="acct-one", contact_key=key,
                             **self.common)
        actionledger.settle(first, actionledger.SENT, why="accepted")

        self.assertEqual(actionledger.contacts_reached(channel="linkedin",
                                                       workspace="acme"),
                         {key})

        second = push.push_id({"id": "acct-two"}, key, "s1", "linkedin")
        with self.assertRaises(actionledger.ActionRefused):
            actionledger.reserve(second, rec_id="acct-two", contact_key=key,
                                 **self.common)


if __name__ == "__main__":
    unittest.main()
