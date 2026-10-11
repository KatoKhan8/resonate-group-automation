#!/usr/bin/env python3
"""The phase-2 sandbox: the EXISTING flow, over synthetic prospects, for 60 days.

WHAT THIS IS, AND WHAT IT REFUSES TO BE
=======================================
This is a DRIVER, not an engine. It owns a clock, a fake provider feed and a
state directory, and nothing else. Every decision it reports is taken by the
module that owns it:

    cadence.build          which steps exist for this contact, and their status
    approve.why_not        whether a draft may be approved
    approve.approve_step   the approval itself, with a fingerprint
    eligibility.decide     whether one step may go out right now
    fatigue.contact_check  the per-person hold policy, at the simulated instant
    fatigue.account_check  the per-company hold policy
    push.mark_pushed       the persistence of a send, and the PUSH_MARKED event
    replywatch.poll_once   the real reply watcher: lock, status, checkpoint
    poller.run             the real poll: paging, high-water mark, retry
    inbound.ingest/handle  the real inbound path: classify, pause, suppress
    simulator.simulate     the whole rehearsal, as the preview page computes it
    replaysim.simulate     one inbound event through the real inbound path

There is no `step_due` here, no cadence model, no reply classifier and no
eligibility rule. An earlier draft of this work carried all four and was
deleted, because every measurement it produced would have been a measurement
of itself. If a step cannot be driven without copying its logic, that is
reported as a FINDING about testability and the logic is not copied.

THE SEAMS THIS ADDS, IN FULL
============================
Three, all additive, all inert unless called, none of them in `src/`:

  1. `FakeBison` / `FakeHeyReach` - replace `bison.fetch_replies`,
     `heyreach.conversations` and `poller.IDENTIFY["emailbison"]` AT THE MODULE
     BOUNDARY. `poller.run` documents `fetch` and `identify` as its test seam
     (`src/poller.py:197`, `:322`, `:396`); `replywatch.poll_once` does not
     forward either, so the replacement is made on the module instead and the
     REAL `poll_once` is driven. That exercises the lock, the status file, the
     checkpoint and the health counter for real. Every adapter call is logged.

  2. `sandboxharness.seal_wire(allow=())` + `seal_readbacks()` - already in
     `src/`, added by the phase-2 survey commit. Called before any work, with
     the positive control firing.

  3. `sandboxclock.install(clock)` - already in `src/`. Patches `store.now`
     only, by module attribute, so the queue-lock deadlines keep ticking in
     real time.

Nothing in `src/` is modified by this branch. `git diff task-sandbox-phase2-horizon
-- src/` is empty, and `tests/test_sandbox_run.py` asserts it.

THE CLOCK, EXACTLY
==================
    start  2026-10-06T06:00:00+00:00   Europe/Zagreb 08:00  UTC+2 (CEST)
    end    2026-12-04T06:00:00+00:00   Europe/Zagreb 07:00  UTC+1 (CET)
    step   exactly 24 hours, 60 times; day indices 0..59

A FIXED UTC interval is the point. Europe/Zagreb leaves summer time at
2026-10-25 03:00 local (02:00 UTC+2 -> 01:00 UTC+1), which falls between day
18 (2026-10-24) and day 19 (2026-10-25). Because the interval is fixed in UTC,
the LOCAL hour of every day's work moves from 08:00 to 07:00 at that point -
which is exactly the question a sending window in `Europe/Zagreb` has to
answer, and exactly what a naive clock hides. `SimClock.advance` returns the
crossings and the run asserts it saw one.

FAIL CLOSED
===========
`_boot` refuses to start unless, in this order: the production `work/` files it
promises not to touch actually exist (otherwise the assertion compares None to
None and can never fail); the store has MOVED into the sandbox directory; no
`CAMPAIGNS` override survived the move; the wire is sealed AND a deliberate
call was refused; the readbacks are sealed AND a deliberate call was refused.
Any one of those failing raises `SandboxRefused` before a single record is
read. `tests/test_sandbox_run.py` breaks each one and proves the refusal.

`import unittest` at the top is deliberate and load-bearing: `store.under_test`
reads `sys.modules` for it, and `store.refuse_production_write` - the barrier
every state writer in `work/` calls - returns silently when it is absent. So a
runner that did not import it would have the barrier switched off. That is a
finding in its own right and it is in the report.

  py -3 scripts/sandbox_run.py --mode one --out <dir>
  py -3 scripts/sandbox_run.py --mode full --companies 100 --days 60 --out <dir>
  py -3 scripts/sandbox_run.py --resume --out <dir>
"""
import argparse
import datetime
import json
import os
import sys
import unittest                                             # noqa: F401
import zoneinfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import (account, approve, cadence, campaigns, clients,  # noqa: E402
                 eligibility, events, fatigue, lint, poller, providers, push,
                 quality, replaysim, replywatch, sandboxclock, sandboxharness,
                 simulator, store, verification, waterfall)
from src.providers import ProviderError, bison, heyreach          # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sandbox_fixture                                       # noqa: E402

UTC = datetime.timezone.utc
ZAGREB = zoneinfo.ZoneInfo("Europe/Zagreb")

#: The run's clock, stated rather than derived from "now", so the answers do
#: not change tomorrow. See the module docstring for why this interval.
START = datetime.datetime(2026, 10, 6, 6, 0, tzinfo=UTC)
DAYS = 60
ADVANCE_HOURS = 24
#: The transition the run must cross, asserted rather than assumed.
DST_DATE = datetime.date(2026, 10, 25)

#: The sandbox's fake credentials. Neither is a key: `replywatch.configured`
#: only asks whether the name is non-empty, and the wire is sealed, so a real
#: value would be both unnecessary and a liability.
SANDBOX_ENV = {
    "BISON_KEY": "sandbox-not-a-key",
    "BISON_WORKSPACE_ID": "10",
    "HEYREACH_KEY": "sandbox-not-a-key",
    "REPLY_POLL_ENABLED": "1",
}
#: What the fake `bound_workspace` answers. Must equal BISON_WORKSPACE_ID or
#: the REAL pin check in `poller.run` refuses the poll - which is a control in
#: its own right and is exercised in the tests.
SANDBOX_WORKSPACE = {"id": 10, "name": "Sandbox Workspace"}

APPROVER = "sandbox-operator@example.invalid"

CHECKPOINT_EVERY = 30                 # simulated days. "at least monthly"
KILL_EXIT_CODE = 97                   # distinct, so a kill is not a crash


class SandboxRefused(RuntimeError):
    """The sandbox would not be isolated, so it refused to run.

    Raised before any record is read. Every message names the specific
    condition, because "refused to start" with no reason is how somebody
    disables the check to get past it.
    """


# ===================================================================== seams
#
# The fake providers. Each one is a translation of the sandbox's own schedule
# into the EXACT shape the real adapter reads, and nothing more. Neither
# classifies, pauses, suppresses or decides anything: that is what the real
# path downstream of them is for.

class FakeBison:
    """Stands in for `bison.fetch_replies` at the module boundary.

    Shape confirmed against `adapters.from_emailbison` and
    `bison.classify_reply_row`: a page is `(rows, next_cursor)`; a row carries
    `id`/`uuid`, `folder` ("inbox" or "bounced"), `from_email_address`,
    `date_received`, `automated_reply`, `campaign_id` and
    `custom_variables.{record_id,contact_key,client}`.

    The feed is DESCENDING by `created_at`, because `poller.poll_emailbison`
    documents that the live feed is and stops against the high-water mark on
    that basis. A fake that ascended would exercise a path the provider does
    not have.
    """

    def __init__(self, clock, rows=None, log_path=None):
        self.clock = clock
        self.rows = list(rows or [])
        self.calls = []
        self.log_path = log_path
        #: Days on which the next `fetch_replies` must raise. Consumed, so a
        #: transient failure is transient.
        self.fail_on_days = set()
        self.failures_raised = 0

    # -------------------------------------------------------------- the feed

    def due(self):
        """Rows whose `created_at` is at or before the simulated instant."""
        now = self.clock.now_iso()
        ready = [r for r in self.rows if str(r.get("created_at")) <= now]
        return sorted(ready, key=lambda r: str(r.get("created_at")),
                      reverse=True)

    def fetch_replies(self, cursor=None, per_page=50, path=None):
        entry = {"at": self.clock.now_iso(), "fn": "bison.fetch_replies",
                 "cursor": cursor, "per_page": per_page}
        if self.clock.day_index in self.fail_on_days:
            self.failures_raised += 1
            entry["raised"] = "ProviderError"
            self._log(entry)
            self.calls.append(entry)
            raise ProviderError(
                "sandbox: simulated transient 502 from the reply feed")
        ready = self.due()
        start = 0
        if cursor:
            # The live cursor bounds the page to OLDER rows. Same here: the
            # cursor is the last stamp handed out.
            ready = [r for r in ready if str(r.get("created_at")) < str(cursor)]
        page = ready[start:start + int(per_page)]
        next_cursor = (str(page[-1].get("created_at"))
                       if len(page) == int(per_page) and page else None)
        entry["returned"] = len(page)
        entry["next_cursor"] = next_cursor
        self._log(entry)
        self.calls.append(entry)
        return [dict(r) for r in page], next_cursor

    def bound_workspace(self):
        entry = {"at": self.clock.now_iso(), "fn": "bison.bound_workspace"}
        self._log(entry)
        self.calls.append(entry)
        return dict(SANDBOX_WORKSPACE)

    def _log(self, entry):
        if not self.log_path:
            return
        with open(self.log_path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")


class FakeHeyReach:
    """Stands in for `heyreach.conversations` at the module boundary.

    Shape confirmed against `adapters.from_heyreach`: `(items, totalCount)`,
    and a webhook-shaped item naming its own `eventType` is how a
    `connection_accepted` reaches `events.LINKEDIN_CONNECTED`. Identity comes
    from `customUserFields`, which is what `_heyreach_event` reads.
    """

    def __init__(self, clock, rows=None, log_path=None):
        self.clock = clock
        self.rows = list(rows or [])
        self.calls = []
        self.log_path = log_path

    def due(self):
        now = self.clock.now_iso()
        ready = [r for r in self.rows if str(r.get("lastMessageAt")) <= now]
        return sorted(ready, key=lambda r: str(r.get("lastMessageAt")),
                      reverse=True)

    def conversations(self, offset=0, limit=50, **_kw):
        ready = self.due()
        page = ready[int(offset):int(offset) + int(limit)]
        entry = {"at": self.clock.now_iso(), "fn": "heyreach.conversations",
                 "offset": offset, "limit": limit, "returned": len(page)}
        self.calls.append(entry)
        if self.log_path:
            with open(self.log_path, "a", encoding="utf-8",
                      newline="\n") as handle:
                handle.write(json.dumps(entry, sort_keys=True) + "\n")
        return [dict(r) for r in page], len(ready)


def install_fake_providers(fake_bison, fake_heyreach):
    """Replace the two feed functions and the identity reader. Returns undo.

    By module attribute, which is the boundary `poller` already names as its
    seam. `poller.IDENTIFY` is replaced as well, because `replywatch.poll_once`
    does not forward `identify=` and the REAL pin check must still run against
    something.
    """
    saved = [
        (bison, "fetch_replies", bison.fetch_replies),
        (bison, "bound_workspace", bison.bound_workspace),
        (heyreach, "conversations", heyreach.conversations),
    ]
    bison.fetch_replies = fake_bison.fetch_replies
    bison.bound_workspace = fake_bison.bound_workspace
    heyreach.conversations = fake_heyreach.conversations
    previous_identify = dict(poller.IDENTIFY)
    poller.IDENTIFY["emailbison"] = fake_bison.bound_workspace

    def undo():
        for mod, attr, value in saved:
            setattr(mod, attr, value)
        poller.IDENTIFY.clear()
        poller.IDENTIFY.update(previous_identify)

    return undo


# ================================================================== the feed

#: The inbound shapes the run covers, and the words they arrive in. Taken from
#: `replaysim.SCENARIOS` where they overlap, so the sandbox and the existing
#: rehearsal are asking about the same sentences.
OPT_OUT_TEXT = "Not interested, please remove me from your list."
POSITIVE_TEXT = ("Sounds interesting. Happy to chat - what does your "
                 "availability look like next week?")
NEUTRAL_TEXT = "Happy to connect. What is it you do exactly?"


def _stamp(day_index, hour=5):
    """The ISO instant a feed row claims, on a given simulated day.

    An hour BEFORE the run's own 06:00 working instant, so a row scheduled for
    day N is already due when day N is processed rather than one day late.
    """
    at = START + datetime.timedelta(days=day_index, hours=hour - 6)
    return at.replace(microsecond=0).isoformat()


def bison_row(rec, contact, day_index, kind, text=""):
    """One `/api/replies` row, in the live shape."""
    contact_key = contact["key"]
    identifier = "%s-%s-%s-%d" % (kind, rec["id"], contact_key, day_index)
    return {
        "id": identifier,
        "uuid": identifier,
        "folder": "bounced" if kind == "bounce" else "inbox",
        "type": "bounce" if kind == "bounce" else "reply",
        "from_email_address": contact["email"],
        "email": contact["email"],
        "date_received": _stamp(day_index),
        "created_at": _stamp(day_index),
        "automated_reply": False,
        "campaign_id": "sandbox-bison-1",
        "lead_id": None,
        "text_body": text,
        "custom_variables": {"record_id": rec["id"],
                             "contact_key": contact_key,
                             "client": rec["client"]},
    }


def heyreach_row(rec, contact, day_index, event_type="connection_accepted",
                 text=""):
    identifier = "%s-%s-%d" % (rec["id"], contact["key"], day_index)
    return {
        "id": identifier,
        "conversationId": identifier,
        "eventType": event_type,
        "timestamp": _stamp(day_index),
        "lastMessageAt": _stamp(day_index),
        "profileUrl": contact["linkedin"],
        "linkedInAccountId": "sandbox-seat-1",
        "campaignId": "sandbox-heyreach-1",
        "text": text,
        "customUserFields": [
            {"name": "record_id", "value": rec["id"]},
            {"name": "contact_key", "value": contact["key"]},
            {"name": "client", "value": rec["client"]},
        ],
    }


#: Which companies get which inbound event. Deterministic from the index so a
#: seed reproduces a run, and stated as proportions so a 4-company smoke run
#: covers every shape the 100-company run does.
COHORTS = ("optout", "positive", "bounce", "neutral", "quiet")


def cohort_of(index, total):
    """The cohort of company `index` (1-based) out of `total`.

    Round-robin rather than contiguous blocks: a contiguous block means a
    4-company smoke run touches one cohort and proves nothing about the other
    four, which is how a shape goes untested until the 100-company run.
    """
    return COHORTS[(index - 1) % len(COHORTS)]


def build_feed(recs, schedule_day=None):
    """The whole inbound schedule, and the connection acceptances.

    Returns (bison_rows, heyreach_rows, plan) where `plan` records, per
    record, what is scheduled and when - so the run can assert the effect
    against the intent rather than against itself.
    """
    bison_rows, heyreach_rows, plan = [], [], {}
    for index, rec in enumerate(recs, start=1):
        cohort = cohort_of(index, len(recs))
        contacts = rec.get("contacts") or []
        entry = {"cohort": cohort}
        # Every company's primary contact gets a connection acceptance, early,
        # so the LinkedIn steps gated on `requires: connected` can leave
        # `waiting` and the dependency rule is exercised in both directions.
        for contact in contacts[:2]:
            day = 3 + (index % 4)
            heyreach_rows.append(heyreach_row(rec, contact, day))
            entry.setdefault("accepted", []).append(
                {"contact": contact["key"], "day": day})
        if cohort == "optout" and contacts:
            day = 12 + (index % 6)
            bison_rows.append(bison_row(rec, contacts[0], day, "reply",
                                        OPT_OUT_TEXT))
            entry["optout"] = {"contact": contacts[0]["key"], "day": day}
        elif cohort == "positive" and contacts:
            day = 25 + (index % 8)
            bison_rows.append(bison_row(rec, contacts[0], day, "reply",
                                        POSITIVE_TEXT))
            entry["positive"] = {"contact": contacts[0]["key"], "day": day}
        elif cohort == "bounce" and len(contacts) > 1:
            day = 8 + (index % 5)
            bison_rows.append(bison_row(rec, contacts[1], day, "bounce",
                                        "550 5.1.1 unknown recipient"))
            entry["bounce"] = {"contact": contacts[1]["key"], "day": day}
        elif cohort == "neutral" and contacts:
            day = 18 + (index % 5)
            bison_rows.append(bison_row(rec, contacts[0], day, "reply",
                                        NEUTRAL_TEXT))
            entry["neutral"] = {"contact": contacts[0]["key"], "day": day}
        plan[rec["id"]] = entry
    return bison_rows, heyreach_rows, plan


# ===================================================================== boot

def _inside(path, root):
    path = os.path.abspath(path)
    root = os.path.abspath(root)
    return path == root or path.startswith(root + os.sep)


def _boot(out_dir, start=START, zone=ZAGREB, seal_production=True):
    """Isolate, seal and inject - or refuse. Returns a dict of handles.

    Order matters and is asserted by the tests: production must be PROVABLE
    before anything is sealed, the store must have moved before anything is
    written, and the wire must be sealed before anything is read.
    """
    state_dir = os.path.join(out_dir, "state")
    sandbox_dir = os.path.join(out_dir, "sandbox")
    os.makedirs(state_dir, exist_ok=True)
    os.makedirs(sandbox_dir, exist_ok=True)

    # 1. The files we promise not to touch must EXIST, or the promise is a
    #    check that compares None to None and can never fail.
    if seal_production:
        try:
            sandboxharness.assert_production_exists()
        except sandboxharness.ProductionTouched as exc:
            raise SandboxRefused(str(exc)) from exc
        production_before = sandboxharness.production_fingerprint()
    else:
        production_before = None

    # 2. The store MOVES, and we check that it did rather than that we asked.
    restore_store = store.use_directory(state_dir)
    queue = store.queue_path()
    if not _inside(queue, state_dir):
        restore_store()
        raise SandboxRefused(
            "store.queue_path() is %s, which is not inside the sandbox "
            "directory %s. Refusing to run: in the wrong directory this run "
            "would write client state." % (queue, state_dir))
    # 3. A stale CAMPAIGNS override survives `use_directory` by pointing at an
    #    absolute path, and phase 1 measured that it points campaign state
    #    back at production. Asserted separately because it is a separate file.
    if os.environ.get("CAMPAIGNS"):
        restore_store()
        raise SandboxRefused(
            "a CAMPAIGNS override survived store.use_directory: %r. Campaign "
            "state would be written outside the sandbox."
            % os.environ.get("CAMPAIGNS"))
    campaigns_path = store.campaigns_path()
    if not _inside(campaigns_path, state_dir):
        restore_store()
        raise SandboxRefused(
            "store.campaigns_path() is %s, outside the sandbox directory %s"
            % (campaigns_path, state_dir))

    # 4. The wire, with the control firing. A seal never shown to stop
    #    anything is not a seal.
    undo_wire, wire_calls = sandboxharness.seal_wire(allow=())
    try:
        sandboxharness.assert_wire_sealed()
    except AssertionError as exc:
        undo_wire()
        restore_store()
        raise SandboxRefused(str(exc)) from exc

    # 5. The readbacks, with the control firing too. A readback that silently
    #    returns a default reports a write as confirmed with nothing
    #    confirming it.
    undo_readbacks = sandboxharness.seal_readbacks()
    try:
        bison.campaign("sandbox-control")
    except sandboxharness.NetworkTouched:
        pass
    else:
        undo_readbacks()
        undo_wire()
        restore_store()
        raise SandboxRefused(
            "the readbacks are NOT sealed: a deliberate call to "
            "bison.campaign returned instead of raising, so this run could "
            "report a write as confirmed with nothing confirming it")

    # 6. The clock.
    clock = sandboxclock.SimClock(start, zone=zone)
    undo_clock = sandboxclock.install(clock)
    if store.now() != clock.now_iso():
        undo_clock()
        undo_readbacks()
        undo_wire()
        restore_store()
        raise SandboxRefused(
            "the clock was not injected: store.now() is %s, the simulated "
            "instant is %s" % (store.now(), clock.now_iso()))

    def teardown():
        undo_clock()
        undo_readbacks()
        undo_wire()
        restore_store()

    return {"clock": clock, "wire_calls": wire_calls,
            "production_before": production_before,
            "state_dir": state_dir, "sandbox_dir": sandbox_dir,
            "teardown": teardown}


# ============================================================ the day's work

def _ledger_rows(recs):
    """Every event on every record, normalised and ordered.

    The comparison unit for resume accuracy and for determinism. `at` is kept:
    under the injected clock it is simulated, so it is part of the answer
    rather than noise. `id` is kept because `events.record` derives it from a
    hash of the entry and a duplicate would share it - which is precisely what
    a resume must not produce.
    """
    rows = []
    for rec in recs:
        for entry in rec.get("events") or []:
            rows.append((rec.get("id"), entry.get("contact"),
                         entry.get("type"), entry.get("step"),
                         entry.get("channel"), entry.get("at"),
                         entry.get("id")))
    return sorted(rows, key=lambda row: tuple(str(v) for v in row))


def compare_ledgers(before, after):
    """What changed between two normalised ledgers. Loss and duplication."""
    before_set, after_set = set(before), set(after)
    duplicates = len(after) - len(after_set)
    return {
        "before": len(before), "after": len(after),
        "lost": sorted(before_set - after_set)[:20],
        "lost_count": len(before_set - after_set),
        "gained_count": len(after_set - before_set),
        "duplicated_rows": duplicates,
        "no_lost_state": not (before_set - after_set),
        "no_duplicated_events": duplicates == 0,
    }


def _state_signature(recs):
    """A compact, order-independent fingerprint of what the run has decided.

    Deliberately NOT a hash of the whole queue: `store.save` rewrites rows and
    a byte digest would make a reordered-but-identical state look changed. This
    is the set of facts a resume must preserve.
    """
    import hashlib

    rows = []
    for rec in sorted(recs, key=lambda r: str(r.get("id"))):
        for contact in rec.get("contacts") or []:
            rows.append("|".join((
                str(rec.get("id")), str(contact.get("key")),
                "unsub=%s" % bool(contact.get("unsubscribed")),
                "stopped=%s" % bool(contact.get("stopped")),
                "bounced=%s" % bool((contact.get("bounce") or
                                     contact.get("bounced")) or ""),
            )))
        rows.append("|".join((str(rec.get("id")),
                              "paused=%s" % bool(rec.get("paused")),
                              "state=%s" % rec.get("state"))))
        for key, slots in sorted((rec.get("cadence") or {}).items()):
            for step_key, slot in sorted(slots.items()):
                rows.append("|".join((str(rec.get("id")), key, step_key,
                                      str(slot.get("status")),
                                      str(slot.get("pushed_at")))))
    blob = "\n".join(rows)
    return {"rows": len(rows),
            "md5": hashlib.md5(blob.encode("utf-8")).hexdigest()}


def approve_ready(rec, config, campaign=None, timeline=None, by=APPROVER):
    """Approve every step the REAL gate says may be approved. Nothing else.

    `approve.why_not` is the authority; a step it refuses is left refused and
    the reason is counted. This is the operator's pass, run once per simulated
    day, and it is the reason `held:draft_not_approved` clears over time
    instead of being written into the fixture.
    """
    approved, refused = 0, {}
    if timeline is None:
        timeline = cadence.build(rec, config, campaign=campaign).get("contacts") or {}
    for contact in rec.get("contacts") or []:
        key = contact.get("key")
        for step_key, step in (timeline.get(key) or {}).items():
            if (step.get("status") or "") in ("pushed", "confirmed",
                                              "cancelled"):
                continue
            reason = approve.why_not(rec, key, step_key, step=step,
                                     config=config, campaign=campaign)
            if reason:
                refused[reason] = refused.get(reason, 0) + 1
                continue
            try:
                approve.approve_step(rec, key, step_key, by=by, config=config,
                                     step=step, sync=False, campaign=campaign)
                approved += 1
            except approve.NotApprovable as exc:
                reason = "NotApprovable: %s" % exc
                refused[reason] = refused.get(reason, 0) + 1
    if approved:
        approve.sync_state(rec, config, campaign)
    return approved, refused


def run_day(clock, recs, config, campaigns_by_record, start_days, fakes,
            counters):
    """One simulated day of the EXISTING flow. Returns this day's metrics."""
    day_index = clock.day_index
    metrics = {
        "day_index": day_index,
        "date_utc": clock.at.date().isoformat(),
        "at_utc": clock.now_iso(),
        "local": clock.local().isoformat(),
        "utc_offset_hours": clock.utc_offset_hours(),
        "is_dst": clock.is_dst(),
        "poll": {}, "approved": 0, "approval_refusals": {},
        "pushed": 0, "verdicts": {}, "reasons": {},
        "fatigue_contact": {}, "fatigue_account": {},
        "repeat_contact_same_day": 0, "copy_repeats": 0,
    }

    # ----------------------------------------------------- 1. the reply watcher
    #
    # The REAL `replywatch.poll_once`: it takes the lock, writes the status
    # file, moves the checkpoint and counts the health. `now=` is the injected
    # instant; `env=` is the sandbox's fake credentials, which is the parameter
    # `configured` and `expected_workspace` already accept for exactly this.
    for provider in ("emailbison", "heyreach"):
        status = replywatch.poll_once(provider, max_pages=5, live=True,
                                      env=SANDBOX_ENV, now=clock.now_iso())
        metrics["poll"][provider] = {
            "healthy": status.get("healthy"),
            "ingested": status.get("new_replies_ingested"),
            "duplicates": status.get("duplicates_ignored"),
            "unmatched": status.get("ambiguous_identities"),
            "pages": status.get("pages"),
            "checkpoint": status.get("checkpoint"),
            "error": status.get("last_error"),
            "skipped": status.get("skipped_reason"),
        }

    # `poll_once` -> `poller.run` -> `inbound.ingest` loaded and SAVED its own
    # copy of the queue, so the in-memory list this loop holds is stale. Re-read
    # rather than merge: the file is the state, and a merge here would be a
    # second opinion about what the inbound path decided.
    recs[:] = store.load()
    by_id = {r.get("id"): r for r in recs}

    # ------------------------------------------- 2. approval, then the decision
    paused_set = cadence.paused_domains(recs)
    pushed_today = {}
    bodies_today = {}
    for rec in recs:
        campaign = campaigns_by_record.get(rec.get("id"))
        elapsed = day_index - start_days.get(rec.get("id"), 0)
        if elapsed < 0:
            continue                      # this record has not entered yet
        timeline = cadence.build(rec, config, paused_set=paused_set,
                                 campaign=campaign).get("contacts") or {}
        approved, refusals = approve_ready(rec, config, campaign=campaign,
                                           timeline=timeline)
        metrics["approved"] += approved
        for reason, n in refusals.items():
            metrics["approval_refusals"][reason] = \
                metrics["approval_refusals"].get(reason, 0) + n
        if approved:
            timeline = cadence.build(rec, config, paused_set=paused_set,
                                     campaign=campaign).get("contacts") or {}

        for contact in rec.get("contacts") or []:
            key = contact.get("key")
            for step_key in sorted(timeline.get(key) or {}):
                planned = timeline[key][step_key]
                decision = eligibility.decide(
                    rec, contact, step_key, campaign=campaign, recs=recs,
                    config=config, day=elapsed, timeline=timeline)
                verdict = decision["verdict"]
                metrics["verdicts"][verdict] = \
                    metrics["verdicts"].get(verdict, 0) + 1
                for reason in decision["reasons"] or ():
                    metrics["reasons"][reason] = \
                        metrics["reasons"].get(reason, 0) + 1
                if verdict != eligibility.ELIGIBLE:
                    continue

                # The hold policy, asked at the SIMULATED instant. This is the
                # one place the run passes `at=` into a business rule that
                # takes it, and it is why a 48-hour same-channel hold releases
                # on simulated hour 48 rather than on the wall clock.
                channel = planned.get("channel")
                contact_state = fatigue.contact_check(
                    rec, key, at=clock.at, config=config, channel=channel)
                account_state = fatigue.account_check(
                    rec, at=clock.at, config=config, contact_key=key)
                metrics["fatigue_contact"][contact_state["state"]] = \
                    metrics["fatigue_contact"].get(contact_state["state"], 0) + 1
                metrics["fatigue_account"][account_state["state"]] = \
                    metrics["fatigue_account"].get(account_state["state"], 0) + 1
                if fatigue.BLOCK in (contact_state["state"],
                                     account_state["state"]):
                    metrics["reasons"]["sandbox:fatigue_block"] = \
                        metrics["reasons"].get("sandbox:fatigue_block", 0) + 1
                    continue

                # The REAL persistence of a send. No provider is contacted:
                # `push.mark_pushed` writes the step, the log line and the
                # PUSH_MARKED event, which is exactly what the live path does
                # once a provider has accepted.
                push.mark_pushed(rec, key, step_key, decision["push_id"],
                                 at=clock.now_iso(), day=planned.get("day"))
                metrics["pushed"] += 1
                counters["pushed_total"] += 1
                pushed_today[key] = pushed_today.get(key, 0) + 1
                body = (planned.get("body") or planned.get("note") or "").strip()
                if body:
                    seen = bodies_today.setdefault(key, set())
                    if body in seen:
                        metrics["copy_repeats"] += 1
                    seen.add(body)

    metrics["repeat_contact_same_day"] = sum(
        n - 1 for n in pushed_today.values() if n > 1)
    store.save(recs)
    metrics["records"] = len(recs)
    metrics["events_total"] = sum(len(r.get("events") or []) for r in recs)
    metrics["log_lines_total"] = sum(len(r.get("log") or []) for r in recs)
    metrics["queue_bytes"] = (os.path.getsize(store.queue_path())
                              if os.path.exists(store.queue_path()) else 0)
    metrics["paused_records"] = sum(1 for r in recs if r.get("paused"))
    metrics["unsubscribed_contacts"] = sum(
        1 for r in recs for c in r.get("contacts") or []
        if c.get("unsubscribed"))
    metrics["wire_calls_attempted"] = len(fakes["wire_calls"])
    metrics["adapter_calls"] = (len(fakes["bison"].calls)
                                + len(fakes["heyreach"].calls))
    return metrics


# ============================================================== checkpointing

def write_checkpoint(handles, day_index, clock, state, path):
    """Durable enough to survive a kill. Atomic replace, never in place."""
    payload = {
        "day_index": day_index,
        "at_utc": clock.now_iso(),
        "seed": state["seed"],
        "companies": state["companies"],
        "days": state["days"],
        "start_days": state["start_days"],
        "bison_rows": state["bison_rows"],
        "heyreach_rows": state["heyreach_rows"],
        "plan": state["plan"],
        "campaign_ids": state["campaign_ids"],
        "counters": state["counters"],
        "fail_on_days": sorted(state["fail_on_days"]),
        "signature": _state_signature(store.load()),
        "ledger_len": len(_ledger_rows(store.load())),
    }
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=1, sort_keys=True)
    os.replace(tmp, path)
    return payload


def read_checkpoint(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


# ===================================================================== runs

def _append_jsonl(path, row):
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def _month_of(day_index):
    return day_index // 30


def build_campaigns(recs, config, state_dir, cohort="quiet"):
    """A REAL campaign over one cohort, driven to RUNNING by the real rules.

    Built so the campaign PAUSE can be exercised as the stop button it is:
    `eligibility._campaign` returns `blocked:campaign_stopped` for a paused
    campaign, and `None` for this one until it is paused. Both directions are
    measured; a pause control with no running baseline proves nothing.

    Every transition goes through `campaigns.set_status`, which refuses an
    illegal one, and the fingerprint is computed by `campaigns.fingerprint`
    over the real records - not written by hand, which is how an approval
    that is not current would masquerade as one that is.
    """
    members = [r for i, r in enumerate(recs, start=1)
               if cohort_of(i, len(recs)) == cohort]
    if not members:
        return {}, None
    campaign = campaigns.new_campaign(
        "sandbox-campaign-1", members[0].get("client"), "Sandbox cohort",
        batch_id=members[0].get("batch"), created_by=APPROVER)
    campaign["record_ids"] = [r.get("id") for r in members]
    campaign["bison_campaign_id"] = "sandbox-bison-1"
    campaign["heyreach_campaign_id"] = "sandbox-heyreach-1"
    for status in (campaigns.PREPARING, campaigns.READY_FOR_REVIEW,
                   campaigns.AWAITING_APPROVAL, campaigns.APPROVED,
                   campaigns.LAUNCH_READY, campaigns.RUNNING):
        campaigns.set_status(campaign, status, why="sandbox")
    campaign["approval"] = {"action": "approve", "by": APPROVER,
                            "at": store.now()}
    campaign["fingerprint"] = campaigns.fingerprint(campaign, members, config)
    campaigns.save([campaign])
    return {r.get("id"): campaign for r in members}, campaign


def run_full(out_dir, seed=20261012, companies=100, days=DAYS,
             kill_after_day=None, resume=False, checkpoint_every=CHECKPOINT_EVERY,
             client="productive", quiet=False, seal_production=True):
    """The 60-day run, or the remainder of one. Returns the report dict."""
    handles = _boot(out_dir, seal_production=seal_production)
    clock = handles["clock"]
    sandbox_dir = handles["sandbox_dir"]
    config = clients.load(client)

    days_path = os.path.join(sandbox_dir, "days.jsonl")
    months_path = os.path.join(sandbox_dir, "months.jsonl")
    adapter_log = os.path.join(sandbox_dir, "adapter-calls.jsonl")
    checkpoint_path = os.path.join(sandbox_dir, "checkpoint.json")

    fake_bison = FakeBison(clock, log_path=adapter_log)
    fake_heyreach = FakeHeyReach(clock, log_path=adapter_log)
    undo_fakes = install_fake_providers(fake_bison, fake_heyreach)
    fakes = {"bison": fake_bison, "heyreach": fake_heyreach,
             "wire_calls": handles["wire_calls"]}

    crossings = []
    try:
        if resume:
            saved = read_checkpoint(checkpoint_path)
            first_day = saved["day_index"] + 1
            seed = saved["seed"]
            companies = saved["companies"]
            days = saved["days"]
            start_days = saved["start_days"]
            plan = saved["plan"]
            counters = saved["counters"]
            fake_bison.rows = saved["bison_rows"]
            fake_heyreach.rows = saved["heyreach_rows"]
            fake_bison.fail_on_days = set(saved["fail_on_days"])
            state = {"seed": seed, "companies": companies, "days": days,
                     "start_days": start_days, "plan": plan,
                     "bison_rows": fake_bison.rows,
                     "heyreach_rows": fake_heyreach.rows,
                     "campaign_ids": saved["campaign_ids"],
                     "counters": counters,
                     "fail_on_days": fake_bison.fail_on_days}
            # The clock is re-derived from the day index, never stored as the
            # authority: a resumed run that trusted a stored instant could
            # drift from the day index it also stores and the two would
            # disagree about which day it is.
            for _ in range(first_day):
                crossings.extend(clock.advance(hours=ADVANCE_HOURS))
            recs = store.load()
            rows = campaigns.load()
            campaigns_by_record = {}
            for rid in saved["campaign_ids"].get("record_ids") or ():
                found = campaigns.get(saved["campaign_ids"]["campaign_id"], rows)
                if found:
                    campaigns_by_record[rid] = found
            resumed_from = saved
        else:
            first_day = 0
            recs = sandbox_fixture.build(seed=seed, companies=companies,
                                         client=client,
                                         today=START.date().isoformat(),
                                         config=config)
            store.save(recs)
            import random

            rng = random.Random(seed ^ 0x5A5A)
            start_days = {r["id"]: rng.randrange(0, 10) for r in recs}
            bison_rows, heyreach_rows, plan = build_feed(recs)
            fake_bison.rows = bison_rows
            fake_heyreach.rows = heyreach_rows
            # Two consecutive days of provider failure, mid-run, so the run
            # covers both a transient error AND recovery with no lost rows.
            fake_bison.fail_on_days = {20, 21}
            campaigns_by_record, campaign = build_campaigns(recs, config,
                                                            handles["state_dir"])
            counters = {"pushed_total": 0}
            state = {"seed": seed, "companies": companies, "days": days,
                     "start_days": start_days, "plan": plan,
                     "bison_rows": bison_rows, "heyreach_rows": heyreach_rows,
                     "campaign_ids": {
                         "campaign_id": (campaign or {}).get("campaign_id"),
                         "record_ids": list((campaign or {}).get("record_ids")
                                            or ())},
                     "counters": counters,
                     "fail_on_days": fake_bison.fail_on_days}
            resumed_from = None

        campaign_paused_on = None
        day_metrics = []
        for day_index in range(first_day, days):
            if day_index != clock.day_index:
                raise SandboxRefused(
                    "clock drift: the loop is on day %d and the clock says "
                    "day %d" % (day_index, clock.day_index))
            # The campaign stop button, pressed once, mid-run. Measured in both
            # directions: the days before this show the cohort deciding
            # normally, the days after show every step blocked.
            if day_index == 40 and campaigns_by_record:
                campaign = next(iter(campaigns_by_record.values()))
                campaigns.set_status(campaign, campaigns.PAUSED,
                                     why="sandbox: operator pressed stop")
                campaigns.save([campaign])
                campaign_paused_on = day_index

            metrics = run_day(clock, recs, config, campaigns_by_record,
                              start_days, fakes, counters)
            metrics["month"] = _month_of(day_index)
            day_metrics.append(metrics)
            _append_jsonl(days_path, metrics)
            if not quiet:
                print("  day %2d %s local %s %+g  poll(bison healthy=%s "
                      "ingested=%s) approved=%d pushed=%d paused=%d unsub=%d"
                      % (day_index, metrics["date_utc"],
                         metrics["local"][11:16], metrics["utc_offset_hours"],
                         metrics["poll"]["emailbison"]["healthy"],
                         metrics["poll"]["emailbison"]["ingested"],
                         metrics["approved"], metrics["pushed"],
                         metrics["paused_records"],
                         metrics["unsubscribed_contacts"]))

            due_checkpoint = ((day_index + 1) % checkpoint_every == 0
                              or day_index == days - 1)
            if due_checkpoint:
                written = write_checkpoint(handles, day_index, clock, state,
                                           checkpoint_path)
                if not quiet:
                    print("  CHECKPOINT day %d: %d ledger rows, signature %s"
                          % (day_index, written["ledger_len"],
                             written["signature"]["md5"][:12]))
                if kill_after_day is not None and day_index == kill_after_day:
                    # A REAL kill. `os._exit` runs no finally block, no atexit
                    # handler and no buffer flush beyond what is already on
                    # disk, which is the point: anything the resume recovers
                    # was genuinely durable.
                    sys.stdout.flush()
                    os._exit(KILL_EXIT_CODE)

            if day_index < days - 1:
                crossings.extend(clock.advance(hours=ADVANCE_HOURS))

        report = _finish(handles, fakes, state, day_metrics, crossings,
                         months_path, sandbox_dir, config, resumed_from,
                         campaign_paused_on)
        return report
    finally:
        undo_fakes()
        handles["teardown"]()


def _finish(handles, fakes, state, day_metrics, crossings, months_path,
            sandbox_dir, config, resumed_from, campaign_paused_on):
    recs = store.load()
    months = {}
    for metrics in day_metrics:
        bucket = months.setdefault(metrics["month"], {
            "month": metrics["month"], "days": 0, "pushed": 0, "approved": 0,
            "ingested": 0, "unmatched": 0, "poll_failures": 0,
            "repeat_contact_same_day": 0, "copy_repeats": 0,
            "verdicts": {}, "reasons": {}})
        bucket["days"] += 1
        bucket["pushed"] += metrics["pushed"]
        bucket["approved"] += metrics["approved"]
        for provider, poll in metrics["poll"].items():
            bucket["ingested"] += int(poll.get("ingested") or 0)
            bucket["unmatched"] += int(poll.get("unmatched") or 0)
            if poll.get("error"):
                bucket["poll_failures"] += 1
        bucket["repeat_contact_same_day"] += metrics["repeat_contact_same_day"]
        bucket["copy_repeats"] += metrics["copy_repeats"]
        for name, n in metrics["verdicts"].items():
            bucket["verdicts"][name] = bucket["verdicts"].get(name, 0) + n
        for name, n in metrics["reasons"].items():
            bucket["reasons"][name] = bucket["reasons"].get(name, 0) + n
        bucket["events_total_end"] = metrics["events_total"]
        bucket["queue_bytes_end"] = metrics["queue_bytes"]
        bucket["paused_records_end"] = metrics["paused_records"]
        bucket["unsubscribed_contacts_end"] = metrics["unsubscribed_contacts"]
    for bucket in sorted(months.values(), key=lambda b: b["month"]):
        _append_jsonl(months_path, bucket)

    ledger = _ledger_rows(recs)
    with open(os.path.join(sandbox_dir, "ledger.json"), "w",
              encoding="utf-8", newline="\n") as handle:
        json.dump(ledger, handle, indent=0)

    defects = clock_defects()
    spend = sum(waterfall.spend(rec)["expected"] for rec in recs)
    report = {
        "start_utc": START.isoformat(),
        "end_utc": handles["clock"].now_iso(),
        "zone": str(ZAGREB),
        "days_simulated": len(day_metrics),
        "crossings": sorted(set(crossings)),
        "dst_crossed": any(c.startswith("dst_change") for c in crossings),
        "records": len(recs),
        "contacts": sum(len(r.get("contacts") or []) for r in recs),
        "events_total": sum(len(r.get("events") or []) for r in recs),
        "ledger_rows": len(ledger),
        "ledger_unique": len(set(ledger)),
        "pushed_total": state["counters"]["pushed_total"],
        "paused_records": sum(1 for r in recs if r.get("paused")),
        "unsubscribed_contacts": sum(
            1 for r in recs for c in r.get("contacts") or []
            if c.get("unsubscribed")),
        "wire_calls_attempted": len(fakes["wire_calls"]),
        "wire_calls_allowed": 0,
        "adapter_calls_bison": len(fakes["bison"].calls),
        "adapter_calls_heyreach": len(fakes["heyreach"].calls),
        "provider_failures_simulated": fakes["bison"].failures_raised,
        "credits_spent": spend,
        "campaign_paused_on_day": campaign_paused_on,
        "signature": _state_signature(recs),
        "months": [months[k] for k in sorted(months)],
        "clock_defects": defects,
        "resumed_from": (resumed_from or {}).get("day_index"),
        "optout": optout_audit(recs, state["plan"]),
    }
    sandboxharness.assert_production_unchanged(handles["production_before"]) \
        if handles["production_before"] is not None else None
    report["production_unchanged"] = handles["production_before"] is not None
    with open(os.path.join(sandbox_dir, "report.json"), "w",
              encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=1, sort_keys=True, default=str)
    return report


def optout_audit(recs, plan):
    """OPT-OUT MUST PREVENT EVERY SUBSEQUENT CONTACT. This is the audit.

    Three things have to hold for every opted-out person, and all three are
    read from what the flow actually did rather than from a flag:

      1. the contact carries `unsubscribed`, which is what
         `eligibility._replied` reads
      2. `eligibility.must_not_contact` refuses them - asked directly, so the
         answer does not depend on a step existing
      3. NO `push_marked` event for that contact is dated after the opt-out

    (3) is the one that matters across a resume, because a resumed run that
    reloaded the record without the flag would push again and (1) and (2)
    would then be measuring a record that had already been written to.
    """
    by_id = {r.get("id"): r for r in recs}
    rows = []
    for rid, entry in (plan or {}).items():
        spec = entry.get("optout")
        if not spec:
            continue
        rec = by_id.get(rid)
        if rec is None:
            rows.append({"record_id": rid, "problem": "record vanished"})
            continue
        contact = next((c for c in rec.get("contacts") or []
                        if c.get("key") == spec["contact"]), None)
        if contact is None:
            rows.append({"record_id": rid, "problem": "contact vanished"})
            continue
        reply_at = next((e.get("at") for e in rec.get("events") or []
                         if e.get("type") == events.REPLY_RECEIVED
                         and e.get("contact") == spec["contact"]), None)
        after = [e for e in rec.get("events") or []
                 if e.get("type") == events.PUSH_MARKED
                 and e.get("contact") == spec["contact"]
                 and reply_at and str(e.get("at")) > str(reply_at)]
        refusals = [r for r in eligibility.must_not_contact(rec, contact) if r]
        rows.append({
            "record_id": rid, "contact": spec["contact"],
            "scheduled_day": spec["day"],
            "reply_ingested": bool(reply_at),
            "reply_at": reply_at,
            "unsubscribed": bool(contact.get("unsubscribed")),
            "record_paused": bool(rec.get("paused")),
            "must_not_contact": refusals,
            "pushes_after_optout": len(after),
        })
    ingested = [r for r in rows if r.get("reply_ingested")]
    return {
        "scheduled": len(rows),
        "ingested": len(ingested),
        "unsubscribed": sum(1 for r in ingested if r.get("unsubscribed")),
        "refused_by_eligibility": sum(1 for r in ingested
                                      if r.get("must_not_contact")),
        "pushes_after_optout": sum(r.get("pushes_after_optout") or 0
                                   for r in ingested),
        "all_prevented": bool(ingested) and all(
            r.get("unsubscribed") and r.get("must_not_contact")
            and not r.get("pushes_after_optout") for r in ingested),
        "rows": rows[:10],
    }


def clock_defects():
    """Unpatched business-clock reads, reported with file and line.

    Two scans, because ONE of them is a zero and a zero that was never shown
    able to be non-zero is not a result:

      `named`  - `sandboxclock.SIMULATED_PATH_MODULES`, the hand-kept list the
                 brief asks about. Measured 2026-10-12: ZERO.
      `all`    - the whole of `src/`, which returns 36. That is the positive
                 control for the scanner itself.

    `on_path_but_unnamed` is the finding that matters: modules this run
    actually imported which the named list omits and which DO hold an
    unpatched read. `evidence.py` is the live one - `quality.assess` calls
    `_selected(rec, contact)` with no `today`, which reaches
    `evidence.recheck(item, None)` and `datetime.date.today()`.
    """
    named = sandboxclock.unpatched_business_clock_reads(
        only=sandboxclock.SIMULATED_PATH_MODULES)
    everything = sandboxclock.unpatched_business_clock_reads(only=None)
    loaded = {name.rsplit(".", 1)[-1] + ".py"
              for name in list(sys.modules)
              if name.startswith("src.") and "." in name}
    unnamed = [row for row in everything
               if os.path.basename(row[0]) in loaded
               and os.path.basename(row[0]) not in
               sandboxclock.SIMULATED_PATH_MODULES
               and os.path.basename(row[0]) != "sandboxclock.py"]
    return {
        "named_set_count": len(named),
        "named_set": [{"file": r[0], "line": r[1], "kind": r[2],
                       "source": r[3]} for r in named],
        "all_src_count": len(everything),
        "on_path_but_unnamed_count": len(unnamed),
        "on_path_but_unnamed": [{"file": r[0], "line": r[1], "kind": r[2],
                                 "source": r[3]} for r in unnamed],
    }


def evidence_clock_control(rec, contact, sim_today):
    """PROOF that `quality.assess` re-ages evidence against the REAL clock.

    Not a grep. `evidence.recheck` is called twice on the same stored item -
    once with the simulated date and once the way `quality._selected` calls it,
    with nothing - and the two `age_days` are compared. A difference is the
    defect, measured.
    """
    from src import evidence

    items = rec.get("research") or []
    if not items:
        return {"checked": 0}
    item = items[0]
    simulated = evidence.recheck(item, sim_today)
    wall = evidence.recheck(item)
    return {
        "checked": 1,
        "published_at": item.get("published_at"),
        "simulated_today": sim_today,
        "age_days_with_simulated_today": simulated.get("age_days"),
        "age_days_as_quality_asks": wall.get("age_days"),
        "differs": simulated.get("age_days") != wall.get("age_days"),
        "bucket_simulated": simulated.get("freshness_bucket"),
        "bucket_as_quality_asks": wall.get("freshness_bucket"),
    }


# =========================================================== run-order item i

def run_one(out_dir, client="productive", seal_production=True):
    """ONE contact, ONE simulated day, through the existing flow, in order.

    The steps are NOT reordered to make it pass. The order is the one
    `simulator.simulate` runs and the one `docs/SANDBOX-PHASE2-SURVEY` records:
    record scope, company acceptance, pause state, then per contact quality ->
    channels -> mx -> lint -> duplicates -> timeline, then spend, then
    approval. Whatever that order produces is what is printed, including a
    refusal.
    """
    handles = _boot(out_dir, seal_production=seal_production)
    clock = handles["clock"]
    config = clients.load(client)
    out = {"at_utc": clock.now_iso(), "local": clock.local().isoformat(),
           "utc_offset_hours": clock.utc_offset_hours(),
           "store_queue": store.queue_path(),
           "wire_sealed_control_fired": True}
    try:
        recs = sandbox_fixture.build(seed=1, companies=1, client=client,
                                     today=START.date().isoformat(),
                                     config=config)
        rec = recs[0]
        rec["contacts"] = rec["contacts"][:1]
        contact = rec["contacts"][0]
        store.save(recs)

        out["record_id"] = rec["id"]
        out["contact_key"] = contact["key"]
        out["domain"] = rec["domain"]
        policy = lint.policy_for_record(rec)
        resolved = verification.resolve(contact, policy)
        out["verification"] = {
            "policy_primary": policy.get("primary"),
            "policy_required_confirmations": policy.get("required_confirmations"),
            "sendable": resolved.get("sendable"),
            "confirmation_count": resolved.get("confirmation_count"),
            "confirmed_by": resolved.get("confirmed_by"),
        }
        result = simulator.simulate(recs=recs, client=client,
                                    batch=rec.get("batch"), config=config)
        out["simulator_headline"] = result["headline"]
        card = result["companies"][0]["cards"][0]
        out["card"] = {
            "email_eligible": card["email_eligible"],
            "email_excluded_reason": card["email_excluded_reason"],
            "linkedin_eligible": card["linkedin_eligible"],
            "mode": card["mode"],
            "held": card["held"],
            "personalization_band": card["personalization_quality"].get("band"),
            "timeline_rows": len(card["timeline"]),
            "timeline_not_planned": sum(1 for r in card["timeline"]
                                        if r["status"] == "not_planned"),
        }
        # The DEFECT this exposes, measured rather than asserted: the preview's
        # timeline walks the module constant while the record's cadence is the
        # client's library sequence, so every row reads "not planned".
        built = cadence.build(rec, config, recs=recs).get("contacts") or {}
        out["cadence_build_steps"] = sorted(built.get(contact["key"]) or {})
        out["simulator_timeline_steps"] = [r["step"] for r in card["timeline"]]
        out["simulator_timeline_matches_cadence"] = (
            sorted(out["simulator_timeline_steps"])
            == sorted(out["cadence_build_steps"]))

        approved, refusals = approve_ready(rec, config)
        out["approved"] = approved
        out["approval_refusals"] = refusals
        built = cadence.build(rec, config, recs=recs).get("contacts") or {}
        decisions = []
        for step_key in sorted(built.get(contact["key"]) or {}):
            planned = built[contact["key"]][step_key]
            decision = eligibility.decide(rec, contact, step_key, recs=recs,
                                          config=config, day=0,
                                          timeline=built)
            decisions.append({"step": step_key, "day": planned.get("day"),
                              "channel": planned.get("channel"),
                              "status": planned.get("status"),
                              "verdict": decision["verdict"],
                              "reasons": decision["reasons"]})
        out["decisions"] = decisions
        out["eligible_on_day_0"] = [d["step"] for d in decisions
                                    if d["verdict"] == eligibility.ELIGIBLE]
        out["fatigue_contact"] = fatigue.contact_check(
            rec, contact["key"], at=clock.at, config=config)["state"]
        out["fatigue_account"] = fatigue.account_check(
            rec, at=clock.at, config=config)["state"]
        out["evidence_clock_control"] = evidence_clock_control(
            rec, contact, clock.at.date().isoformat())
        out["wire_calls_attempted"] = len(handles["wire_calls"])
        out["credits_spent"] = waterfall.spend(rec)["expected"]
        if handles["production_before"] is not None:
            sandboxharness.assert_production_unchanged(
                handles["production_before"])
            out["production_unchanged"] = True
        return out
    finally:
        handles["teardown"]()


# ===================================================================== CLI

def main(argv=None):
    p = argparse.ArgumentParser(prog="py -3 scripts/sandbox_run.py",
                               description=__doc__)
    p.add_argument("--mode", choices=("one", "full"), default="full")
    p.add_argument("--out", required=True,
                   help="the sandbox directory. State and metrics live here. "
                        "It must not be inside the production work/.")
    p.add_argument("--seed", type=int, default=20261012)
    p.add_argument("--companies", type=int, default=100)
    p.add_argument("--days", type=int, default=DAYS)
    p.add_argument("--client", default="productive")
    p.add_argument("--checkpoint-every", type=int, default=CHECKPOINT_EVERY)
    p.add_argument("--kill-after-day", type=int, default=None,
                   help="os._exit(%d) immediately after that day's checkpoint. "
                        "A real kill: no finally, no atexit, no flush."
                        % KILL_EXIT_CODE)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    out_dir = os.path.abspath(a.out)
    for protected in store.protected_directories():
        if _inside(out_dir, protected):
            print("REFUSED: --out %s is inside the production state directory "
                  "%s" % (out_dir, protected))
            return 2

    if a.mode == "one":
        result = run_one(out_dir, client=a.client)
        print(json.dumps(result, indent=2, default=str))
        ok = (result["card"]["email_eligible"]
              and result["verification"]["sendable"]
              and result["wire_calls_attempted"] >= 1)
        print("\nRUN-ORDER (i): one contact, one simulated day - %s"
              % ("the flow ran and every verdict came from the owning module"
                 if ok else "SEE THE REFUSALS ABOVE"))
        return 0

    report = run_full(out_dir, seed=a.seed, companies=a.companies,
                      days=a.days, kill_after_day=a.kill_after_day,
                      resume=a.resume, checkpoint_every=a.checkpoint_every,
                      client=a.client, quiet=a.quiet)
    if a.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print("\n==== SANDBOX REPORT ====")
        for field in ("start_utc", "end_utc", "zone", "days_simulated",
                      "dst_crossed", "crossings", "records", "contacts",
                      "events_total", "ledger_rows", "ledger_unique",
                      "pushed_total", "paused_records",
                      "unsubscribed_contacts", "wire_calls_attempted",
                      "wire_calls_allowed", "adapter_calls_bison",
                      "adapter_calls_heyreach", "provider_failures_simulated",
                      "credits_spent", "campaign_paused_on_day",
                      "production_unchanged", "resumed_from"):
            print("  %-28s %s" % (field, report.get(field)))
        print("  optout                       %s" % json.dumps(
            {k: v for k, v in report["optout"].items() if k != "rows"}))
        print("  clock defects (named set)    %d"
              % report["clock_defects"]["named_set_count"])
        print("  clock defects (on path, unnamed) %d"
              % report["clock_defects"]["on_path_but_unnamed_count"])
        for row in report["clock_defects"]["on_path_but_unnamed"]:
            print("      %s:%d  %s  %s"
                  % (row["file"], row["line"], row["kind"], row["source"][:70]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
