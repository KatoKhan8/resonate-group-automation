"""The reply store can be non-zero, and a store that cannot be written says so.

WHAT WAS WRONG, MEASURED RATHER THAN ASSUMED.

`work/replywatch.json` on 2026-10-11T23:05 reported the EmailBison watcher
`healthy: true`, `pages: 1`, `events_inspected: 0`, `new_replies_ingested: 0`,
and `work/learning-replies.jsonl` had an mtime of 23 September with a newest
`received_at` of 2026-09-22. Three facts were recovered before anything was
changed:

  1. The poll DID read replies. `work/notifications.jsonl` carries 44
     `unmatched_reply_needs_review` rows stamped 2026-10-11T22:23:34, every
     one of them `{"provider": "emailbison", "why": "no record for this
     event", "held": 0}`. So 44 inbound replies came off the feed, through
     the adapter, into `events.apply`, and all 44 came back `unmatched`.

  2. `inbound.handle` returns at `if applied["status"] != "applied"` before
     it ever reaches `replies.apply`. An unmatched reply is therefore never
     classified. `new_replies_ingested` counts `applied` only, so 44 reads
     and 0 attributions is reported as `0`.

  3. Nothing in `src/` wrote the reply store at all. Its only writer was
     `scripts/learning_walk_replies.py`, and that walk pages EmailBison's
     reply feed with a cursor that only ever bounds a page to OLDER rows
     (`poller.poll_emailbison` documents the same property), so it walks
     backwards into history and can never return to the head. Its state file
     sits at `created_at 2026-02-25` with `complete: false`: it is still
     descending through February and will not pass today's replies again.

So the consumer was never called, the verdict was never persisted, and the
one number anybody looked at could not tell "no replies" from "no measurement".

WHAT THESE TESTS PIN. A zero that was never shown able to be non-zero is
silence rather than a result, so both directions are asserted here: a reply
IS stored and counted (twice - attributed and unattributed), and a store that
cannot be written makes the watcher UNHEALTHY instead of reporting zero.

AND THE STORE NOW HAS TWO WRITERS, so both of them deduplicate. The lock
stops a torn line; it does not stop the same reply being written twice, and
`work/learning-replies.state.json` is the only thing standing between the
historical walk and a second pass over the whole feed. `BothWritersDeduplicate`
walks that path with no state file at all. `TheIndexIsBoundedNotRebuiltEachTime`
pins the other half: knowing what is already stored costs the NEW bytes, not
the whole 27.6 MB file, every few minutes, inside the lock the walk waits on.

THE REGRESSION GATE FOR THIS CHANGE IS A COMMAND, and the last class here is
the control that it can disagree with the branch it gates:

    py -3 scripts/regression_reply_ingestion.py --baseline master

SAFETY. `store.use_directory` into a throwaway directory, which now moves the
reply store too (`store.reply_store_path`, `LEARNING_REPLIES`); the wire
sealed at `providers.set_transport` with a positive control that is run in
every poll test; and the MAIN CHECKOUT's `work/queue.jsonl` and
`work/learning-replies.jsonl` md5'd before and after every single test. The
md5 is taken against the main checkout rather than this tree, because this
module normally runs from a linked worktree where `work/` does not exist at
all and comparing None to None is a test that cannot fail.
"""
import hashlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import adapters, poller, providers, replies, replyverdict  # noqa: E402
from src import replywatch, store                                  # noqa: E402
from src.providers import bison                                    # noqa: E402


def _production_root():
    """The MAIN checkout, even when this file sits in a linked worktree."""
    dot = os.path.join(ROOT, ".git")
    if os.path.isdir(dot):
        return ROOT
    with open(dot, encoding="utf-8") as handle:
        pointer = handle.read().strip()
    gitdir = pointer.split(":", 1)[1].strip()
    if not os.path.isabs(gitdir):
        gitdir = os.path.abspath(os.path.join(ROOT, gitdir))
    return os.path.dirname(os.path.dirname(os.path.dirname(gitdir)))


PRODUCTION = _production_root()

#: The queue, and the reply store this task writes to. Both, because the
#: barrier being tested is the one that would have let a fixture reply land
#: in the file the 30-month analysis is computed from.
PRODUCTION_FILES = ("queue.jsonl", "learning-replies.jsonl")

WORKSPACE = {"id": 10, "name": "productive-sandbox"}

CONTACT_EMAIL = "pat@acme.test"
STRANGER_EMAIL = "someone@nowhere.test"

#: Classified NEGATIVE, deliberately. A POSITIVE verdict reaches
#: `orchestrator.positive_reply_notification`, and this module is not the
#: place to exercise that.
NEGATIVE_BODY = "Thanks for reaching out but we are not interested."


def reply_row(reply_id=900999, email=CONTACT_EMAIL, body=NEGATIVE_BODY,
              at="2026-10-11T12:00:00.000000Z"):
    """One row in the shape `GET /api/replies` actually returns.

    Field names and types from `docs/BISON-PROVIDER-TRUTH-2026-09-14.md`,
    which records 750 live rows: `type` is `Untracked Reply`, the folder is
    `Inbox`, the lead is nested, and both `date_received` and `created_at`
    are present. `created_at` is the one `poller.poll_emailbison` marks
    against; `date_received` is the one the adapter stamps the event with.
    """
    return {
        "id": reply_id, "uuid": f"u-{reply_id}",
        "type": "Untracked Reply", "folder": "Inbox",
        "campaign_id": 900900, "lead_id": 900001,
        "scheduled_email_id": 99001,
        "from_email_address": email, "from_name": "Pat Lee",
        "primary_to_email_address": "sender@resonate.test",
        "subject": "Re: a question",
        "text_body": body, "html_body": f"<p>{body}</p>",
        "date_received": at, "created_at": at, "updated_at": at,
        "automated_reply": False, "tracked_reply": False,
        "interested": False, "read": False,
        "lead": {"id": 900001, "email": email},
    }


OUTGOING_ROW = {
    # Our own mail, which this feed also carries. The adapter drops it, so it
    # must not reach the reply store either.
    "id": 900998, "uuid": "u-900998", "type": "Outgoing Email",
    "folder": "Sent", "campaign_id": 900900, "lead_id": 900001,
    "from_email_address": "sender@resonate.test",
    "subject": "a question", "text_body": "Would you be open to a chat?",
    "date_received": "2026-10-11T11:00:00.000000Z",
    "created_at": "2026-10-11T11:00:00.000000Z",
    "automated_reply": False, "interested": False,
    "lead": {"id": 900001, "email": CONTACT_EMAIL},
}


class WireSealed(RuntimeError):
    """A provider call was attempted. Nothing was sent."""


def _md5(path):
    if not os.path.exists(path):
        return None
    digest = hashlib.md5()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SealedStore(unittest.TestCase):
    """Isolation, asserted rather than assumed, before every test."""

    def setUp(self):
        self.prod_paths = {name: os.path.join(PRODUCTION, "work", name)
                           for name in PRODUCTION_FILES}
        for name, path in self.prod_paths.items():
            self.assertTrue(
                os.path.exists(path),
                "production %s not found at %s - the before/after md5 would "
                "be vacuous" % (name, path))
        self.prod = {name: _md5(path)
                     for name, path in self.prod_paths.items()}
        self.assertTrue(all(self.prod.values()))
        self.addCleanup(self._assert_production_untouched)

        self.tmp = tempfile.mkdtemp(prefix="reply-store-")
        self.sandbox = os.path.join(self.tmp, "work")
        before_queue = store.queue_path()
        before_store = store.reply_store_path()
        self.addCleanup(store.use_directory(self.sandbox))

        self.assertNotEqual(store.queue_path(), before_queue)
        self.assertNotEqual(store.reply_store_path(), before_store)
        self.assertIsNone(os.environ.get("LEARNING_REPLIES"))
        for resolved in (store.queue_path(), store.reply_store_path()):
            self.assertTrue(
                os.path.abspath(resolved).startswith(
                    os.path.abspath(self.sandbox)), resolved)
            self.assertNotIn(os.path.abspath(resolved),
                             {os.path.abspath(p)
                              for p in self.prod_paths.values()}, resolved)

        self.wire = []
        previous = providers.set_transport(self._sealed)
        self.addCleanup(providers.set_transport, previous)

    def _sealed(self, method, url, headers, body, timeout):
        self.wire.append({"method": method, "url": str(url)})
        raise WireSealed(f"the wire is sealed: {method} {url}. Nothing was sent.")

    def assert_the_seal_fires(self):
        """A positive control on the seal itself, run inside the poll tests."""
        with self.assertRaises(Exception):
            providers.request("GET", "https://api.emailbison.com/api/v1/ping")
        self.assertTrue(self.wire, "the seal recorded nothing")
        self.wire.clear()

    def _assert_production_untouched(self):
        for name, path in self.prod_paths.items():
            self.assertEqual(
                _md5(path), self.prod[name],
                "production work/%s changed during this test" % name)

    # ------------------------------------------------------------- helpers

    def seed_record(self, email=CONTACT_EMAIL):
        """One record, and deliberately NO provider binding on the contact.

        `inbound._stop_at_provider` only reaches a provider when the contact
        carries `bison_lead_id` or `heyreach_lead_id`. Without them the stop
        is a recorded no-op, which keeps this test off the wire while still
        walking the whole ingest path.
        """
        rec = store.new_record("r1", "domains", "productive", "Acme",
                               "acme.test")
        rec["contacts"] = [{"key": "pat", "name": "Pat Lee", "email": email}]
        with store.transaction() as rows:
            rows.append(rec)
        return rec

    def poll(self, rows, max_pages=1):
        """One EmailBison poll through `replywatch`, no network, no cursor.

        `env` is injected so `configured()` does not read `config/.env` and
        `expected_workspace()` finds no pin; `poller.IDENTIFY` is patched
        because the workspace read is the one call `run` makes before the
        feed.
        """
        self.assert_the_seal_fires()

        def fetch(cursor=None, per_page=None, **_):
            return (list(rows) if not cursor else []), None

        with mock.patch.object(bison, "fetch_replies", fetch), \
                mock.patch.dict(poller.IDENTIFY,
                                {"emailbison": lambda: dict(WORKSPACE)}):
            return replywatch.poll_once("emailbison", max_pages=max_pages,
                                        live=True,
                                        env={"BISON_KEY": "sandbox"})

    def load_walk(self):
        """The historical walker, imported AFTER the store was redirected.

        It resolves `OUT` at import time, so importing it before
        `use_directory` would bind it to the real reply store - which is
        precisely the thing this module md5s to prove it never touched.
        """
        spec = importlib.util.spec_from_file_location(
            "learning_walk_replies",
            os.path.join(ROOT, "scripts", "learning_walk_replies.py"))
        walk = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(walk)
        return walk

    def stored_rows(self):
        path = store.reply_store_path()
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]


class IngestionIsNotInert(SealedStore):

    def test_a_reply_nobody_can_attribute_is_still_stored_and_counted(self):
        """The live case: 44 reads, 0 attributions, and it must not be silent.

        This is the production shape exactly - a reply from an address held
        on no record. `new_replies_ingested` is honestly 0 because nothing
        was attributed, and `replies_stored` is 1 because the reply was
        read, classified and kept.
        """
        self.seed_record()                      # a record, but a stranger wrote
        report = self.poll([reply_row(email=STRANGER_EMAIL)])

        self.assertTrue(report["healthy"], report.get("last_error"))
        self.assertIsNone(report["last_error"])
        self.assertEqual(report["events_inspected"], 1)
        self.assertEqual(report["new_replies_ingested"], 0)
        self.assertEqual(report["ambiguous_identities"], 1)
        self.assertEqual(report["replies_stored"], 1,
                         "an unattributable reply was read and not stored - "
                         "which is the defect this file exists for")

        rows = self.stored_rows()
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0]["reply_id"], 900999)
        self.assertEqual(rows[0]["classification"], replies.NEGATIVE)
        self.assertEqual(rows[0]["classifier"], replies.RULE_HASH)

    def test_a_reply_on_a_record_is_ingested_and_counted(self):
        """And the attributed case still works, and is counted in both places."""
        self.seed_record()
        report = self.poll([reply_row(email=CONTACT_EMAIL)])

        self.assertTrue(report["healthy"], report.get("last_error"))
        self.assertEqual(report["events_inspected"], 1)
        self.assertEqual(report["new_replies_ingested"], 1)
        self.assertEqual(report["replies_stored"], 1)
        self.assertEqual(len(self.stored_rows()), 1)
        self.assertFalse(self.wire, "a provider call was attempted")

    def test_our_own_outgoing_mail_never_reaches_the_reply_store(self):
        """`/api/replies` carries our sends. The store counts replies only."""
        self.seed_record()
        report = self.poll([OUTGOING_ROW])

        self.assertTrue(report["healthy"], report.get("last_error"))
        self.assertEqual(report["events_inspected"], 0)
        self.assertEqual(report["replies_stored"], 0)
        self.assertEqual(self.stored_rows(), [])

    def test_the_same_reply_read_twice_is_stored_once(self):
        """Re-reading the head of the feed is the design, not an accident.

        `poller` starts at the head on every run on purpose, so the store has
        to be idempotent on the provider's own reply id or it grows by a
        duplicate of every reply per poll - which is how
        `learning-replies.jsonl.dupbak.2026-09-22` came to exist - 34,125
        lines carrying 17,700 distinct replies, measured 2026-10-12.
        """
        self.seed_record()
        first = self.poll([reply_row(email=STRANGER_EMAIL)])
        self.assertEqual(first["replies_stored"], 1)

        # A second poll of the same row, with the mark cleared so the row is
        # genuinely re-offered rather than filtered out upstream.
        poller.save_checkpoint("emailbison", None, scope="ws10")
        second = self.poll([reply_row(email=STRANGER_EMAIL)])

        self.assertTrue(second["healthy"], second.get("last_error"))
        self.assertEqual(second["events_inspected"], 1)
        self.assertEqual(second["replies_stored"], 0,
                         "the same reply was stored twice")
        self.assertEqual(len(self.stored_rows()), 1)

    def test_the_walk_and_the_watcher_write_one_store_under_one_key(self):
        """ONE store, two writers, and the same `reply_id` for one reply.

        The historical walk covers the 30 months behind us and the watcher
        covers the head. They have to be the same file keyed the same way, or
        the series has a seam at whatever date the walk last ran and every
        reply near it is counted twice.
        """
        walk = self.load_walk()
        self.assertEqual(os.path.abspath(walk.OUT),
                         os.path.abspath(store.reply_store_path()))

        raw = reply_row(reply_id=900555, email=STRANGER_EMAIL)
        walk._append([json.dumps(walk.trim(raw)) + "\n"])
        self.assertIn("900555", replies.stored_reply_ids())

        self.seed_record()
        report = self.poll([raw])
        self.assertTrue(report["healthy"], report.get("last_error"))
        self.assertEqual(report["events_inspected"], 1)
        self.assertEqual(report["replies_stored"], 0,
                         "the watcher stored a reply the walk already had")
        self.assertEqual(len(self.stored_rows()), 1)


class BothWritersDeduplicate(SealedStore):
    """The walk is a writer too, and the lock alone does not dedupe.

    `work/learning-replies.state.json` is `complete: false` at
    `created_at 2026-02-25`, and it is the only thing standing between the
    walk and a second pass over the whole feed. Lose it, corrupt it, or clear
    it, and the walk restarts at the head and descends through all of history
    - re-appending every historical row AND every head row the watcher has
    already stored. The store is 1.00x today, which is what that mode looks
    like before it is triggered.
    """

    def test_the_walk_does_not_re_store_what_the_watcher_already_has(self):
        """A reply stored by the watcher, then offered to the walk."""
        self.seed_record()
        report = self.poll([reply_row(email=STRANGER_EMAIL)])
        self.assertEqual(report["replies_stored"], 1)
        before = self.stored_rows()
        self.assertEqual(len(before), 1)

        walk = self.load_walk()
        landed = walk._append(
            [json.dumps(walk.trim(reply_row(email=STRANGER_EMAIL))) + "\n"])

        self.assertEqual(landed, 0, "the walk re-stored a reply the watcher "
                                    "had already written")
        self.assertEqual(self.stored_rows(), before,
                         "the store gained a row for a reply it already held")

    def test_a_walk_that_lost_its_state_file_stores_each_reply_once(self):
        """The whole failure path, end to end, with no watcher involved.

        Two full passes over the same page, which is exactly what a restart
        with no `STATE` does. The second must add nothing.
        """
        walk = self.load_walk()
        page = [reply_row(reply_id=900101, email=STRANGER_EMAIL),
                reply_row(reply_id=900102, email=STRANGER_EMAIL),
                reply_row(reply_id=900103, email=STRANGER_EMAIL)]
        lines = [json.dumps(walk.trim(row)) + "\n" for row in page]

        self.assertEqual(walk._append(list(lines)), 3)
        self.assertEqual(walk._append(list(lines)), 0)
        self.assertEqual(len(self.stored_rows()), 3)
        self.assertEqual(
            sorted(r["reply_id"] for r in self.stored_rows()),
            [900101, 900102, 900103])

    def test_one_page_carrying_the_same_reply_twice_stores_it_once(self):
        """A duplicate INSIDE one page, which no on-disk check can catch.

        The provider has handed the same row twice on one page before. The
        index cannot see it - the row is not on disk yet - so both writers
        keep a pending set as well.
        """
        walk = self.load_walk()
        line = json.dumps(walk.trim(reply_row(reply_id=900202))) + "\n"
        self.assertEqual(walk._append([line, line]), 1)
        self.assertEqual(len(self.stored_rows()), 1)

        self.seed_record()
        twice = {"data": [reply_row(reply_id=900303, email=STRANGER_EMAIL),
                          reply_row(reply_id=900303, email=STRANGER_EMAIL)]}
        self.assertEqual(sum(replies.remember(
            adapters.from_emailbison(twice))), 1)
        self.assertEqual(len(self.stored_rows()), 2)

    def test_a_row_too_malformed_to_name_a_reply_is_kept_not_dropped(self):
        """Dropping it would lose a reply because we could not read a line.

        Counted as raw lines rather than parsed rows: one of these two is
        deliberately not JSON, so parsing is the wrong measurement here.
        """
        walk = self.load_walk()
        self.assertEqual(walk._append(['{"not": "a reply row"}\n']), 1)
        self.assertEqual(walk._append(["this is not json at all\n"]), 1)
        with open(store.reply_store_path(), encoding="utf-8") as handle:
            kept = [line for line in handle if line.strip()]
        self.assertEqual(len(kept), 2, kept)
        # And neither of them poisoned the index with a bogus id.
        self.assertEqual(replies.stored_reply_ids(), set())


class TheIndexIsBoundedNotRebuiltEachTime(SealedStore):
    """`stored_reply_ids` parsed the whole store on every poll.

    The store is append-only and only grows: at 179,715 rows / 27.6 MB that
    was a full JSON parse every few minutes, inside the lock the walk waits
    on, for an answer that had changed by a handful of lines. An O(N)-per-poll
    ingest is unbounded cost growth even while the file is perfectly correct,
    which a long-horizon measurement cannot carry.
    """

    def setUp(self):
        super().setUp()
        replies.forget_stored_reply_ids()
        self.addCleanup(replies.forget_stored_reply_ids)

    def _write(self, ids):
        path = store.reply_store_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8", newline="\n") as handle:
            for one in ids:
                handle.write(json.dumps({"reply_id": one}) + "\n")

    def test_only_the_bytes_appended_since_the_last_look_are_parsed(self):
        """Counted by instrumenting `json.loads`, not by timing it."""
        self._write(range(500))
        self.assertEqual(len(replies.stored_reply_ids()), 500)

        self._write(range(500, 503))
        import json as json_module
        real, seen = json_module.loads, []

        def counted(text, *a, **kw):
            seen.append(text)
            return real(text, *a, **kw)

        with mock.patch.object(json_module, "loads", counted):
            found = replies.stored_reply_ids()

        self.assertEqual(len(found), 503)
        self.assertEqual(len(seen), 3,
                         "the whole store was re-parsed for three new rows")

    def test_a_store_that_got_shorter_is_read_from_the_beginning(self):
        """The one change an append-only offset can detect on its own."""
        self._write(range(100))
        self.assertEqual(len(replies.stored_reply_ids()), 100)

        store.write_jsonl(store.reply_store_path(),
                          [{"reply_id": 7}, {"reply_id": 8}])
        self.assertEqual(replies.stored_reply_ids(), {"7", "8"})

    def test_the_snapshot_cannot_be_written_into(self):
        """A caller that mutated the index would poison every later answer."""
        self._write(range(5))
        snapshot = replies.stored_reply_ids()
        snapshot.add("not-a-real-reply")
        self.assertNotIn("not-a-real-reply", replies.stored_reply_ids())

    def test_a_half_written_line_does_not_advance_the_offset(self):
        """A reader outside the lock can arrive mid-append."""
        path = store.reply_store_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps({"reply_id": 1}) + "\n")
            handle.write('{"reply_id": 2, "partia')       # no newline
        self.assertEqual(replies.stored_reply_ids(), {"1"})

        with open(path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write('l": true}\n')
        self.assertEqual(replies.stored_reply_ids(), {"1", "2"})


class AStoreThatCannotBeWritten(SealedStore):
    """THE POSITIVE CONTROL. A failed store write may not read as zero."""

    def test_a_failed_store_write_makes_the_watcher_unhealthy(self):
        """Not `new_replies_ingested: 0` with `healthy: true`.

        The failure is a real filesystem one rather than a patched function:
        `LEARNING_REPLIES` is pointed at a path whose parent directory is an
        ordinary FILE, so every attempt to create it fails. Nothing on the
        write path catches it, so it travels out of `replies.remember`
        through `inbound.ingest` and `poller.run` to `poll_once`, which
        records it as a failure.

        The checkpoint is asserted afterwards for the reason `poll_once`
        documents: a mark advanced past rows that were never stored is a
        reply nobody ever measures.
        """
        self.seed_record()
        blocker = os.path.join(self.sandbox, "not-a-directory")
        os.makedirs(self.sandbox, exist_ok=True)
        with open(blocker, "w", encoding="utf-8") as handle:
            handle.write("this is a file, not a directory\n")
        os.environ["LEARNING_REPLIES"] = os.path.join(blocker, "replies.jsonl")
        self.addCleanup(os.environ.pop, "LEARNING_REPLIES", None)

        report = self.poll([reply_row(email=STRANGER_EMAIL)])

        self.assertFalse(report.get("healthy"),
                         "a reply store that cannot be written was reported "
                         "healthy: %r" % (report,))
        self.assertTrue(report.get("last_error"), report)
        self.assertEqual(report.get("consecutive_failures"), 1)
        # The silent shape this test exists to forbid: a count of zero sitting
        # beside a clean bill of health.
        self.assertFalse(
            report.get("healthy") and report.get("new_replies_ingested") == 0,
            "the watcher reported zero ingested and healthy at the same time")
        self.assertIsNone(poller.cursor_for("emailbison", "ws10"),
                          "the checkpoint advanced over a reply that was "
                          "never stored")

    def test_the_same_page_stores_cleanly_once_the_store_is_writable(self):
        """The control on the control: the failure above was the STORE.

        Same record, same page, same poll - with `LEARNING_REPLIES` left
        alone. A green result here is what makes the red one above evidence
        about the store rather than about the fixture.
        """
        self.seed_record()
        report = self.poll([reply_row(email=STRANGER_EMAIL)])
        self.assertTrue(report["healthy"], report.get("last_error"))
        self.assertEqual(report["replies_stored"], 1)


class AVerdictIsPersistedAndNamed(unittest.TestCase):
    """Defect 2, with no filesystem: the row shape and its backward compatibility."""

    LEGACY_ROW = {"reply_id": 900777, "campaign_id": 900900, "lead_id": 900001,
                  "domain": "oldcorp.test",
                  "received_at": "2026-09-22T12:05:39.000000Z",
                  "interested": False, "automated": True}

    def test_a_stored_row_carries_the_class_the_confidence_and_the_rules(self):
        event = adapters.from_emailbison({"data": [reply_row()]})[0]
        row = replies.store_row(event)

        self.assertEqual(sorted(row), sorted(replies.STORED_FIELDS))
        self.assertEqual(row["classification"], replies.NEGATIVE)
        self.assertIsInstance(row["confidence"], float)
        self.assertGreater(row["confidence"], 0.0)
        self.assertEqual(row["classifier"], replies.RULE_HASH)
        # What `replyverdict` was written to compare, compared.
        self.assertEqual(replyverdict.current_rule_identity(),
                         replies.RULE_HASH)
        self.assertTrue(replyverdict.is_confirmed(row))

    def test_no_body_no_name_and_no_address_is_persisted(self):
        """`classify` returns an excerpt, evidence and a reason. None is kept."""
        event = adapters.from_emailbison({"data": [reply_row()]})[0]
        row = replies.store_row(event)
        text = json.dumps(row)
        for leaked in ("excerpt", "evidence", "reason",
                       NEGATIVE_BODY, "Pat Lee", CONTACT_EMAIL):
            self.assertNotIn(leaked, text, leaked)
        # The domain is deliberately kept - it always was - and it is not the
        # address.
        self.assertEqual(row["domain"], "acme.test")

    def test_a_row_with_no_verdict_is_unknown_and_is_never_confirmed(self):
        """The 179,715 existing rows - all distinct, all unverdicted.

        Measured 2026-10-12: 179,715 non-blank lines, 179,715 carrying a
        `reply_id`, 179,715 distinct, 1.00x. They must not crash a reader and
        must not be counted as classified.
        """
        verdict = replies.stored_verdict(self.LEGACY_ROW)
        self.assertEqual(verdict["classification"], replies.UNKNOWN)
        self.assertEqual(verdict["confidence"], 0.0)
        self.assertIsNone(verdict["classifier"])
        self.assertFalse(verdict["stored"])
        self.assertFalse(replyverdict.is_confirmed(self.LEGACY_ROW))
        # And it is not counted as a positive, whatever else a reader does.
        self.assertEqual(
            replyverdict.split_positives([self.LEGACY_ROW]), (0, 0))

    def test_a_verdict_stored_under_other_rules_is_not_confirmable(self):
        """The whole reason `classifier` is the digest and not `VERSION`."""
        stale = dict(self.LEGACY_ROW, classification=replies.POSITIVE,
                     confidence=0.75, classifier="rules-3")
        self.assertTrue(replies.stored_verdict(stale)["stored"])
        self.assertFalse(replyverdict.is_confirmed(stale))
        self.assertEqual(replyverdict.split_positives([stale]), (0, 1))

    def test_the_historical_walk_stores_the_same_verdict_as_ingestion(self):
        """One store, one schema, from both writers.

        The 30-month horizon is the walk's, not the watcher's: the watcher
        polls the head and the walk is the only thing that reaches February.
        A verdict on one and not the other would make the series discontinuous
        at whatever date the walk last ran.
        """
        walk = SealedStore.load_walk(self)

        raw = reply_row()
        walked = walk.trim(raw)
        ingested = replies.store_row(
            adapters.from_emailbison({"data": [raw]})[0])

        self.assertEqual(sorted(walked), sorted(replies.STORED_FIELDS))
        for field in ("reply_id", "campaign_id", "lead_id", "domain",
                      "classification", "confidence", "classifier"):
            self.assertEqual(walked[field], ingested[field], field)


class TheRegressionGateCanDisagree(unittest.TestCase):
    """`scripts/regression_reply_ingestion.py` must be able to say REGRESSION.

    A gate that only ever agrees with the branch it is gating is not
    evidence. Two things are pinned here, both of them cheap because the
    runs are stubbed: a name failing here and passing at the baseline exits
    non-zero, and a run that produced no unittest summary at all is REFUSED
    rather than read as clean - which is the shape a mis-decoded capture
    takes on this machine, where the default console codepage is cp1250 and
    one non-ASCII byte in a traceback returns None for the whole output.

    The real end-to-end run is not done here: it takes two minutes and
    belongs in the command, not in the suite.
    """

    def _gate(self):
        spec = importlib.util.spec_from_file_location(
            "regression_reply_ingestion",
            os.path.join(ROOT, "scripts", "regression_reply_ingestion.py"))
        gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gate)
        gate._export = lambda ref, into: into
        return gate

    def _verdict(self, gate):
        import contextlib
        sink = io.StringIO()
        with contextlib.redirect_stdout(sink):
            code = gate.main(["--baseline", "master"])
        return code, sink.getvalue()

    def test_a_name_failing_here_and_passing_at_the_baseline_is_a_regression(self):
        gate = self._gate()
        seen = []

        def differing(cwd, modules, verbose=False):
            seen.append(cwd)
            names = ({"a.B.c", "a.B.new"} if len(seen) == 1 else {"a.B.c"})
            return names, "Ran 2 tests | FAILED", "", []

        gate._run = differing
        code, printed = self._verdict(gate)
        self.assertEqual(code, 1)
        self.assertIn("VERDICT: REGRESSION", printed)
        self.assertIn("a.B.new", printed)

    def test_an_identical_failing_set_is_not_a_regression(self):
        gate = self._gate()
        gate._run = lambda cwd, modules, verbose=False: (
            {"a.B.c"}, "Ran 2 tests | FAILED", "", [])
        code, printed = self._verdict(gate)
        self.assertEqual(code, 0)
        self.assertIn("no new failing names", printed)
        self.assertIn("PRE-EXISTING (failing on both): 1", printed)

    def test_a_run_that_read_nothing_is_refused_rather_than_called_clean(self):
        gate = self._gate()
        with mock.patch.object(gate.subprocess, "run") as fake:
            fake.return_value = mock.Mock(stdout="", stderr="", returncode=0)
            with self.assertRaises(SystemExit) as caught:
                gate._run(ROOT, ("tests.test_the_reply_store_is_not_inert",))
        self.assertIn("no unittest summary", str(caught.exception))

    def test_the_gate_covers_every_file_this_change_touched(self):
        """A gate that does not import the changed code proves nothing.

        Asserted against the AST import graph of the modules the gate runs,
        not against the text of the files - searching source for words
        produces a test that fails when somebody writes a comment.
        """
        import ast

        gate = self._gate()
        imported = set()
        for module in gate.MODULES:
            path = os.path.join(ROOT, *module.split(".")) + ".py"
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as handle:
                tree = ast.parse(handle.read(), filename=path)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module == "src":
                    imported.update(alias.name for alias in node.names)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("src."):
                            imported.add(alias.name.split(".", 1)[1])

        for changed in ("inbound", "poller", "adapters", "replies",
                        "replywatch", "store"):
            self.assertIn(changed, imported,
                          "no module the gate runs imports src.%s" % changed)


if __name__ == "__main__":
    unittest.main()
