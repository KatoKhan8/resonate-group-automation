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
    eligibility.must_not_contact  whether this person hears anything further
    fatigue.contact_check  the per-person hold policy, at the simulated instant
    fatigue.account_check  the per-company hold policy
    push.mark_pushed       the persistence of a send, and the PUSH_MARKED event
    replywatch.poll_once   the REAL reply watcher: lock, status, checkpoint
    poller.run             the real poll: paging, high-water mark, retry
    inbound.ingest/handle  the real inbound path: classify, pause, suppress
    replies.classify       the reply classifier
    accountpolicy.effects  what a classified reply does to the replier/account
    simulator.simulate     the whole rehearsal, as the preview page computes it

There is no `step_due` here, no cadence model, no reply classifier and no
eligibility rule. An earlier draft of this work carried all four and was
deleted, because every measurement it produced would have been a measurement
of itself. Where a step cannot be driven without copying its logic, that is
reported as a FINDING about testability and the logic is NOT copied.

WHAT THE 60-DAY RUN IS FOR, AND WHAT IT IS NOT FOR
==================================================
Operator narrowing of 2026-10-12: the 60-day run is for MECHANICAL properties
only - the clock, state growth, holds, duplicate contact, and crash/resume.

Everything classifier-dependent is reported separately, by `--mode replies`,
and is labelled UNVERIFIED. A separate lane's classifier work was refused by
adversarial review and the ingestion fix is unreviewed; nothing here depends on
`task-removal-union-2026-10-12` or `task-reply-ingestion-2026-10-12`, and the
mechanical results stand without them. The 60-day feed therefore uses only the
one inbound shape whose handling is settled - an EXPLICIT removal request - so
that a contested classification cannot move a mechanical number.

THE SEAMS THIS ADDS, IN FULL
============================
Three, all additive, all inert unless called, and NONE of them in `src/`.
`git diff task-sandbox-phase2-horizon -- src/` is empty and
`tests/test_sandbox_run.py` asserts it.

  1. `FakeBison` / `FakeHeyReach` replace `bison.fetch_replies`,
     `bison.bound_workspace`, `heyreach.conversations` and
     `poller.IDENTIFY["emailbison"]` AT THE MODULE BOUNDARY. `poller.run`
     documents `fetch` and `identify` as its test seam (`src/poller.py:197`,
     `:322`, `:396`), but `replywatch.poll_once` does not forward either - so
     the replacement is made on the module and the REAL `poll_once` is driven.
     That exercises the lock, the status file, the checkpoint, the workspace
     pin and the health counter for real. Every adapter call is logged to
     `sandbox/adapter-calls.jsonl`.

  2. `sandboxharness.seal_wire(allow=())` + `seal_readbacks()` - already in
     `src/`, added by the phase-2 survey commit. Called before any work, with
     the positive control firing in both cases.

  3. `sandboxclock.install(clock)` - already in `src/`. Patches `store.now`
     only, by module attribute, so the queue-lock deadlines keep ticking in
     real time.

THE FIXTURE IS NOT MINE
=======================
`docs/sandbox/fixture-seed-{1,2}.json`, from
`task-sandbox-fixture-2026-10-12` at `2ebc2188`: 100 companies x 3 contacts =
300 records, six cohorts of 50, `.invalid` domains only, byte-identical per
seed. I wrote a stand-in generator while that branch was empty and DELETED it
when the real one landed, because two generators are two representations of
one thing.

Two things about that fixture change what this runner has to do, and both are
findings rather than fixture bugs:

  * `rec["cadence_steps"]` IS INERT. `cadence.steps_for` reads
    `(campaign or {}).get(CADENCE_KEY)` - it is a CAMPAIGN key, not a record
    key - and with no campaign it falls through to `_named_sequence(config)`
    and then `cadencelibrary.named(config["cadence"])`. Productive names
    `productive_li_heavy_v1`, so the sequence that actually runs is TEN steps
    keyed `li1,em1,...,li5,em5`, not the fixture's seven `day1..day21`.

  * NINE OF THOSE TEN STEPS ARE `generated`, and `cadence.expand_step`
    returns None for a generated step whose slot holds no `body` (email) or
    `note` (linkedin). Measured against the fixture as it ships: the timeline
    is `li1..li5` only, em1..em5 are ABSENT, and `approve.why_not` says
    `empty note` for li2..li5. So the email path is unreachable until the
    phase-5 writer's output exists, and the writer needs a model this run must
    not call.

    `install_phase5_copy` therefore writes copy into
    `rec["cadence"][contact_key][step_key]` - the exact slot the real writer
    writes - rendered by `cadence.render` over `cadence.TEMPLATES` with
    `cadence.template_vars`, plus `optout.append_opt_out`. The repository's own
    words, through the repository's own renderer, zero model calls. The
    per-step template choice is measured against the REAL word contract
    (`lint.STEP_WORD_CONTRACT`), not guessed - see EMAIL_TEMPLATE_FOR_STEP.

THE CLOCK, EXACTLY
==================
    start  2026-10-12T06:00:00+00:00   Europe/Zagreb 08:00  UTC+2 (CEST)
    end    2026-12-10T06:00:00+00:00   Europe/Zagreb 07:00  UTC+1 (CET)
    step   exactly 24 hours, 59 advances over 60 days; indices 0..59

A FIXED UTC interval is the point. Europe/Zagreb leaves summer time at
2026-10-25 03:00 local (02:00 UTC+2 -> 01:00 UTC+1), which falls between day
12 (2026-10-24) and day 13 (2026-10-25). Because the interval is fixed in UTC,
the LOCAL hour of every day's work moves from 08:00 to 07:00 at that point -
which is exactly the question a `sending_window` in `Europe/Zagreb` has to
answer and exactly what a naive clock hides. `SimClock.advance` returns the
crossings and the run asserts it saw one. The window matches the fixture's own
declared window (`docs/sandbox/FIXTURE.md`: 2026-10-12 to 2026-12-10).

FAIL CLOSED
===========
`_boot` refuses to start unless, in this order: the production `work/` files
this run promises not to touch actually EXIST (otherwise the assertion
compares None to None and could never fail); the store has MOVED into the
sandbox directory; no `CAMPAIGNS` override survived the move; the wire is
sealed AND a deliberate call was refused; the readbacks are sealed AND a
deliberate call was refused; the clock is installed AND `store.now()` agrees
with it. Any one failing raises `SandboxRefused` before a record is read, and
`tests/test_sandbox_run.py` breaks each one and proves the refusal.

`import unittest` at the top is deliberate and LOAD-BEARING: `store.under_test`
reads `sys.modules` for it, and `store.refuse_production_write` - the barrier
every state writer in `work/` calls - RETURNS SILENTLY when it is absent. A
plain script therefore runs with that barrier switched off. That is a finding
in its own right and it is in the report.

  py -3 scripts/sandbox_run.py --mode one     --out <dir>
  py -3 scripts/sandbox_run.py --mode replies --out <dir>
  py -3 scripts/sandbox_run.py --mode full    --out <dir> --seed 1
  py -3 scripts/sandbox_run.py --mode full    --out <dir> --resume
"""
import argparse
import copy
import datetime
import json
import os
import sys
import unittest                                             # noqa: F401
import zoneinfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import (accountpolicy, approval, approve, cadence,  # noqa: E402
                 campaigns, clients, eligibility, events, fatigue, lint,
                 notify, optout,
                 poller, push, replies, replywatch, sandboxclock,
                 sandboxharness, simulator, store, verification, waterfall)
from src.providers import ProviderError, bison, heyreach          # noqa: E402

UTC = datetime.timezone.utc
ZAGREB = zoneinfo.ZoneInfo("Europe/Zagreb")

#: The run's clock, stated rather than derived from "now", so the answers do
#: not change tomorrow. Matches the fixture's declared window.
START = datetime.datetime(2026, 10, 12, 6, 0, tzinfo=UTC)
DAYS = 60
ADVANCE_HOURS = 24
#: The transition the run must cross. Asserted, not assumed.
DST_DATE = datetime.date(2026, 10, 25)

FIXTURE_DIR = os.path.join(ROOT, "docs", "sandbox")

#: The sandbox's fake credentials. Neither is a key: `replywatch.configured`
#: only asks whether the name is non-empty, and the wire is sealed, so a real
#: value would be both unnecessary and a liability.
SANDBOX_ENV = {
    "BISON_KEY": "sandbox-not-a-key",
    "BISON_WORKSPACE_ID": "10",
    "HEYREACH_KEY": "sandbox-not-a-key",
    "REPLY_POLL_ENABLED": "1",
}
#: What the fake `bound_workspace` answers. It must equal BISON_WORKSPACE_ID or
#: the REAL pin check inside `poller.run` refuses the poll - which is itself a
#: control, exercised in the tests.
SANDBOX_WORKSPACE = {"id": 10, "name": "Sandbox Workspace"}

APPROVER = "sandbox-operator@example.invalid"

CHECKPOINT_EVERY = 30                 # simulated days. "at least monthly"
KILL_EXIT_CODE = 97                   # distinct, so a kill is not a crash

#: Which template renders each generated EMAIL step. MEASURED, not chosen:
#: every shipped template was rendered under both of Productive's persona
#: families and counted with `lint.countable_words` over the body WITH the
#: opt-out line appended, against `lint.STEP_WORD_CONTRACT`
#: (em1 60-90, em2 45-90, em3 60-90, em4 45-90, em5 45-90). champion /
#: economic_buyer:
#:
#:   comparable_proof         87 /  87   <- em1
#:   comparable_proof_short   59 /  59   <- em2
#:   rung3_champion           88 /  86   <- em3
#:   close_champion           62 /  67   <- em4
#:   breakup                  75 /  80   <- em5
#:   close_economic_buyer     57 /  62
#:   persona_pain             97 / 102   OVER em1/em3's ceiling of 90
#:   rung3_economic_buyer    107 / 105   OVER
#:   angle_shift_champion    129 / 129   OVER
#:   angle_shift_economic_buyer 124/129  OVER
#:
#: THAT FOUR OF THE TEN SHIPPED EMAIL TEMPLATES BREAK THE SHIPPED WORD
#: CONTRACT IS A FINDING, and it is in the report. One consequence lands here:
#: the contract-satisfying set is persona-INDEPENDENT, because the
#: economic-buyer variant of the day-8 rung (`rung3_economic_buyer`) is 105
#: words against a ceiling of 90. So em3 renders `rung3_champion` for both
#: families rather than the persona-matched variant, and the sandbox says so
#: instead of selecting a template that would be blocked by the real lint.
EMAIL_TEMPLATE_FOR_STEP = {
    "em1": "comparable_proof",
    "em2": "comparable_proof_short",
    "em3": "rung3_champion",
    "em4": "close_champion",
    "em5": "breakup",
}

#: Templates whose rendered body exceeds its step's ceiling under at least one
#: persona. Kept as data so the test asserts the finding rather than restating
#: it, and so a template that is fixed stops being listed here.
EMAIL_TEMPLATES_OVER_CONTRACT = ("persona_pain", "rung3_economic_buyer",
                                 "angle_shift_champion",
                                 "angle_shift_economic_buyer")
LI_NOTE_TEMPLATE = {"li1": "linkedin_intro"}
LI_FOLLOWUP_TEMPLATE = "linkedin_followup"


class SandboxRefused(RuntimeError):
    """The sandbox would not be isolated, so it refused to run.

    Raised before any record is read. Every message names the specific
    condition, because "refused to start" with no reason is how somebody
    disables the check to get past it.
    """


# ===================================================================== seams

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
        #: Simulated days on which `fetch_replies` must raise. The transient
        #: provider error. Consumed by nothing: the day set is the schedule.
        self.fail_on_days = set()
        self.failures_raised = 0

    def due(self):
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
        if cursor:
            # The live cursor bounds the page to OLDER rows; same here.
            ready = [r for r in ready if str(r.get("created_at")) < str(cursor)]
        page = ready[:int(per_page)]
        next_cursor = (str(page[-1].get("created_at"))
                       if page and len(page) == int(per_page) else None)
        entry["returned"] = len(page)
        entry["next_cursor"] = next_cursor
        self._log(entry)
        self.calls.append(entry)
        return [copy.deepcopy(r) for r in page], next_cursor

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
        return [copy.deepcopy(r) for r in page], len(ready)


def install_fake_providers(fake_bison, fake_heyreach):
    """Replace the two feed functions and the identity reader. Returns undo."""
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


# ================================================================== fixture

def fixture_path(seed):
    return os.path.join(FIXTURE_DIR, "fixture-seed-%d.json" % seed)


def load_fixture(seed=1, path=None):
    """The fixture lane's records. Never generated here.

    Refuses rather than falling back to a generator: a run that silently
    invented its own prospects would not be comparable with the other lane's
    tests, and "300 records" would stop meaning the same 300 records.
    """
    path = path or fixture_path(seed)
    if not os.path.exists(path):
        raise SandboxRefused(
            "no fixture at %s. The sandbox does not generate prospects: it "
            "reads docs/sandbox/fixture-seed-<N>.json from "
            "task-sandbox-fixture-2026-10-12." % path)
    with open(path, encoding="utf-8") as handle:
        blob = json.load(handle)
    recs = blob.get("queue_records")
    if not isinstance(recs, list) or not recs:
        raise SandboxRefused("%s carries no queue_records" % path)
    for rec in recs:
        if not sandboxharness.is_synthetic_domain(rec.get("domain")):
            raise SandboxRefused(
                "fixture record %s has a non-synthetic domain %r; refusing to "
                "run" % (rec.get("id"), rec.get("domain")))
    return copy.deepcopy(recs), blob


#: `cadence.TEMPLATES` names its persona variants by FAMILY (`champion`,
#: `economic_buyer`), and `product_words` resolves `{capability}` from
#: `capability_by_persona` keyed the same way. The fixture carries the family
#: in `contact["persona"]` and the job title in `contact["title"]`.
FAMILIES = ("champion", "economic_buyer")


def install_phase5_copy(recs, config, sequence=None):
    """Write the client's own rendered copy into the slot the writer writes.

    THIS IS THE ONE PLACE THE RUNNER PUTS WORDS ON A RECORD, and it is
    fixture data in exactly the sense the synthetic verification evidence is:
    it stands in for an output this run cannot obtain, because obtaining it
    needs a model and the wire is sealed. It invents nothing - every sentence
    is a shipped template rendered by `cadence.render` from
    `cadence.template_vars` - and it is written to
    `rec["cadence"][contact_key][step_key]`, which is the slot
    `approve.approve_step`, `cadence.expand_step` and `push` all already read.

    IT ALSO FILLS `rec["hook"]`, and that is a FIXTURE FINDING rather than a
    preference. Measured 2026-10-12 on `fixture-seed-1.json`: `hook` is `null`
    on all 100 records and `lane` is `cold` on all 100, and
    `src/lint.py:756` is

        if lane == "cold" and not rec.get("hook"): fails.add("cold_no_hook")

    so `eligibility.decide` answers `blocked:lint_failed, blocked:lint:
    cold_no_hook` on EVERY email step. A sandbox that used the fixture
    verbatim would therefore measure a LinkedIn-only estate and might not
    notice - the same shape the survey recorded for the missing verification
    evidence.

    The hook is taken from the record's OWN company-level evidence fact rather
    than composed, so it asserts nothing the record does not already carry.
    `hook` is pipeline output (research/enrichment), not provider data, so
    filling it here is completing the pipeline's own prior stage and not
    faking a provider.

    Returns a report, because the alternative is a silent partial install and
    a timeline nobody can explain.
    """
    installed, refused, hooks = 0, {}, 0
    for rec in recs:
        if not (rec.get("hook") or "").strip():
            company_fact = next(
                (item.get("fact") for item in rec.get("research") or []
                 if item.get("subject") == "company" and item.get("fact")),
                None)
            if company_fact:
                rec["hook"] = company_fact.strip()
                hooks += 1
            else:
                refused["no company evidence to take a hook from"] = \
                    refused.get("no company evidence to take a hook from",
                                0) + 1
        seq = sequence or cadence.steps_for(None, config, rec, None)
        facts = [item.get("fact") for item in rec.get("research") or []
                 if item.get("fact")]
        for contact in rec.get("contacts") or []:
            key = lint.contact_key(contact)
            family = contact.get("persona")
            if family not in FAMILIES:
                refused["persona not a template family: %r" % (family,)] = \
                    refused.get("persona not a template family: %r"
                                % (family,), 0) + 1
                continue
            values = cadence.template_vars(rec, contact, config)
            slots = rec.setdefault("cadence", {}).setdefault(key, {})
            li_index = 0
            for spec in seq:
                if not spec.get("generated"):
                    continue
                step_key = spec["key"]
                if spec["channel"] == "email":
                    name = EMAIL_TEMPLATE_FOR_STEP.get(step_key)
                    if name is None:
                        refused["no measured template for %s" % step_key] = \
                            refused.get("no measured template for %s"
                                        % step_key, 0) + 1
                        continue
                    rendered = cadence.render(
                        cadence.TEMPLATES[name], values)
                    slots[step_key] = {
                        "channel": "email",
                        "subject": rendered.get("subject"),
                        "body": optout.append_opt_out(rendered.get("body")),
                        "generated": True}
                else:
                    name = LI_NOTE_TEMPLATE.get(step_key,
                                                LI_FOLLOWUP_TEMPLATE)
                    rendered = cadence.render(cadence.TEMPLATES[name], values)
                    note = (rendered.get("note") or "").strip()
                    if facts:
                        # Varied by the record's OWN evidence, one fact per
                        # step, so the duplicate detector has distinct bodies
                        # to judge rather than five copies of one note.
                        note = "%s (%s)" % (
                            note, facts[li_index % len(facts)][:90].rstrip())
                    li_index += 1
                    slots[step_key] = {"channel": "linkedin",
                                       "note": note[:300], "generated": True}
                installed += 1
    return {"installed": installed, "hooks_filled": hooks,
            "refused": refused}


# ================================================================== the feed

#: The one inbound shape whose handling is SETTLED, used by the 60-day
#: mechanical run. Explicit, unambiguous, and classified `unsubscribe` with
#: three matched phrases. Nothing mechanical in this run depends on a
#: contested classification.
EXPLICIT_REMOVAL = ("Please remove me from your list and do not contact me "
                    "again.")

#: The four scenarios the operator made mandatory on 2026-10-12. Each names
#: what it SHOULD and should NOT trigger across the three axes that must not be
#: conflated. The expectation is the operator's rule, written here so the
#: measurement can disagree with it - which, for (a), it does.
#:
#:   classification     what the text was judged to be
#:   cadence_stop       the sequence stops sending to this person
#:   permanent_optout   the person is suppressed forever
#:   human_review       a person has to look before anything else goes out
#:
#: "An ambiguous case must end in HUMAN REVIEW, not in a confident verdict. A
#: held-for-review outcome is a PASS; a confident false positive is a FAIL even
#: when it is safe."
REPLY_CASES = {
    "a_positive_with_unsubscribe_footer": {
        "text": "Sounds great, Thursday works. You can unsubscribe from our "
                "mailing list at any time.",
        "why": "a warm yes carrying an ordinary unsubscribe footer. The "
               "expensive direction: a buying signal turned into a permanent "
               "suppression.",
        "expect": {"cadence_stop": True, "permanent_optout": False,
                   "human_review": True},
    },
    "b_question_with_stop_and_blocking": {
        "text": "How do we stop spam filters blocking your invoices?",
        "why": "a product question containing both 'stop' and 'blocking' and "
               "which is not an opt-out at all.",
        "expect": {"cadence_stop": True, "permanent_optout": False,
                   "human_review": True},
    },
    "c_positive_contract_no_further_emails": {
        "text": "No further emails needed - just send the contract.",
        "why": "a contract request that also asks for no more email. A stop, "
               "but emphatically not a removal.",
        "expect": {"cadence_stop": True, "permanent_optout": False,
                   "human_review": True},
    },
    "d_explicit_removal": {
        "text": EXPLICIT_REMOVAL,
        "why": "the settled case. This one SHOULD suppress.",
        "expect": {"cadence_stop": True, "permanent_optout": True,
                   "human_review": False},
    },
}


def _stamp(day_index, hour=5):
    """The ISO instant a feed row claims, on a given simulated day.

    An hour BEFORE the run's own 06:00 working instant, so a row scheduled for
    day N is already due when day N is processed rather than one day late.
    """
    at = START + datetime.timedelta(days=day_index, hours=hour - 6)
    return at.replace(microsecond=0).isoformat()


def bison_row(record_id, client, contact_key, email, day_index, kind,
              text="", suffix=""):
    """One `/api/replies` row, in the live shape.

    `custom_variables` is how identity reaches `events.apply`; omitting
    `record_id`/`contact_key` is how the unattributed path is reached, which
    is a deliberate case below rather than an accident.
    """
    identifier = "%s-%s-%s-%d%s" % (kind, record_id or "none",
                                    contact_key or "none", day_index, suffix)
    custom = {"client": client}
    if record_id:
        custom["record_id"] = record_id
    if contact_key:
        custom["contact_key"] = contact_key
    return {
        "id": identifier,
        "uuid": identifier,
        "folder": "bounced" if kind == "bounce" else "inbox",
        "type": "bounce" if kind == "bounce" else "reply",
        "from_email_address": email,
        "email": email,
        "date_received": _stamp(day_index),
        "created_at": _stamp(day_index),
        "automated_reply": False,
        "campaign_id": "sandbox-bison-1",
        "lead_id": None,
        "text_body": text,
        "custom_variables": custom,
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


#: Round-robin rather than contiguous blocks: a contiguous block means a
#: 5-company smoke run touches one cohort and proves nothing about the other
#: four, which is how a shape goes untested until the big run.
COHORTS = ("removal", "bounce", "unattributed", "quiet", "accepted_only")


def cohort_of(index):
    return COHORTS[(index - 1) % len(COHORTS)]


def build_feed(recs):
    """The whole inbound schedule. Mechanical shapes only.

    Returns (bison_rows, heyreach_rows, plan). `plan` records the INTENT so
    the run can assert the effect against what was scheduled rather than
    against itself.
    """
    bison_rows, heyreach_rows, plan = [], [], {}
    for index, rec in enumerate(recs, start=1):
        cohort = cohort_of(index)
        contacts = rec.get("contacts") or []
        entry = {"cohort": cohort}
        # Every company's first two contacts get a connection acceptance,
        # early, so the LinkedIn steps gated on `requires: connected` can
        # leave `waiting` and the dependency rule is exercised BOTH ways.
        for contact in contacts[:2]:
            day = 2 + (index % 4)
            heyreach_rows.append(heyreach_row(rec, contact, day))
            entry.setdefault("accepted", []).append(
                {"contact": contact["key"], "day": day})
        if cohort == "removal" and contacts:
            day = 14 + (index % 6)
            bison_rows.append(bison_row(
                rec["id"], rec["client"], contacts[0]["key"],
                contacts[0]["email"], day, "reply", EXPLICIT_REMOVAL))
            entry["removal"] = {"contact": contacts[0]["key"], "day": day}
        elif cohort == "bounce" and len(contacts) > 1:
            day = 8 + (index % 5)
            bison_rows.append(bison_row(
                rec["id"], rec["client"], contacts[1]["key"],
                contacts[1]["email"], day, "bounce",
                "550 5.1.1 unknown recipient"))
            entry["bounce"] = {"contact": contacts[1]["key"], "day": day}
        elif cohort == "unattributed" and contacts:
            # NO record_id and NO contact_key, and an address that matches no
            # contact. `inbound.py:429` returns before the classify/store step
            # for exactly this, and the run proves what IS retained.
            day = 20 + (index % 4)
            bison_rows.append(bison_row(
                None, rec["client"], None,
                "alias-%04d@%s" % (index, rec["domain"]), day, "reply",
                EXPLICIT_REMOVAL))
            entry["unattributed"] = {"day": day,
                                     "email": "alias-%04d@%s"
                                              % (index, rec["domain"])}
        plan[rec["id"]] = entry
    return bison_rows, heyreach_rows, plan


# ===================================================================== boot

def _inside(path, root):
    path = os.path.abspath(path)
    root = os.path.abspath(root)
    return path == root or path.startswith(root + os.sep)


def _boot(out_dir, start=START, zone=ZAGREB, seal_production=True):
    """Isolate, seal and inject - or refuse. Returns a dict of handles.

    The ORDER is asserted by the tests: production must be PROVABLE before
    anything is sealed, the store must have moved before anything is written,
    and the wire must be sealed before anything is read.
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

    # 2. The store MOVES, and we check that it DID rather than that we asked.
    restore_store = store.use_directory(state_dir)
    undo = [restore_store]

    def _refuse(message):
        for fn in reversed(undo):
            fn()
        raise SandboxRefused(message)

    queue = store.queue_path()
    if not _inside(queue, state_dir):
        _refuse("store.queue_path() is %s, which is not inside the sandbox "
                "directory %s. Refusing to run: in the wrong directory this "
                "run would write client state." % (queue, state_dir))
    # 3. A stale CAMPAIGNS override survives `use_directory` - phase 1
    #    measured that it points campaign state back at production.
    if os.environ.get("CAMPAIGNS"):
        _refuse("a CAMPAIGNS override survived store.use_directory: %r. "
                "Campaign state would be written outside the sandbox."
                % os.environ.get("CAMPAIGNS"))
    if not _inside(store.campaigns_path(), state_dir):
        _refuse("store.campaigns_path() is %s, outside the sandbox directory "
                "%s" % (store.campaigns_path(), state_dir))

    # EVERYTHING FROM HERE PUTS THE PROCESS BACK ON ANY EXCEPTION, not only on
    # the refusals this function raises itself. Measured 2026-10-12: a control
    # that stubbed out `seal_readbacks` made `bison.campaign` raise
    # `MissingKey` - a worktree has no `config/.env` - which `_boot` did not
    # catch, so the undo list never ran and the INJECTED CLOCK leaked into
    # every test that followed. One of them then reported the wall clock as
    # the simulated instant and passed for the wrong reason.
    try:
        # 4. The wire, with the control firing. A seal never shown to stop
        #    anything is not a seal.
        undo_wire, wire_calls = sandboxharness.seal_wire(allow=())
        undo.append(undo_wire)
        try:
            sandboxharness.assert_wire_sealed()
        except AssertionError as exc:
            _refuse(str(exc))

        # 5. The readbacks, with the control firing too. A readback that
        #    silently returns a default reports a write as confirmed with
        #    nothing confirming it.
        undo.append(sandboxharness.seal_readbacks())
        try:
            bison.campaign("sandbox-control")
        except sandboxharness.NetworkTouched:
            pass
        else:
            _refuse("the readbacks are NOT sealed: a deliberate call to "
                    "bison.campaign returned instead of raising, so this run "
                    "could report a write as confirmed with nothing "
                    "confirming it")

        # 6. The clock.
        clock = sandboxclock.SimClock(start, zone=zone)
        undo.append(sandboxclock.install(clock))
        if store.now() != clock.now_iso():
            _refuse("the clock was not injected: store.now() is %s, the "
                    "simulated instant is %s" % (store.now(), clock.now_iso()))
    except SandboxRefused:
        raise                                  # `_refuse` already unwound
    except BaseException:
        for fn in reversed(undo):
            fn()
        raise

    def teardown():
        for fn in reversed(undo):
            fn()

    return {"clock": clock, "wire_calls": wire_calls,
            "production_before": production_before,
            "state_dir": state_dir, "sandbox_dir": sandbox_dir,
            "teardown": teardown}


# ====================================================== ledgers and signatures

def _ledger_rows(recs):
    """Every event on every record, normalised and ordered.

    The comparison unit for resume accuracy and for determinism. `at` is kept:
    under the injected clock it is simulated, so it is part of the answer
    rather than noise. `id` is kept because `events.record` derives it from a
    hash of the entry, and a duplicate would share it - which is exactly what
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
    """What changed between two normalised ledgers: loss and duplication."""
    before_set, after_set = set(before), set(after)
    duplicates = len(after) - len(after_set)
    return {
        "before": len(before), "after": len(after),
        "lost": sorted(str(r) for r in before_set - after_set)[:20],
        "lost_count": len(before_set - after_set),
        "gained_count": len(after_set - before_set),
        "duplicated_rows": duplicates,
        "no_lost_state": not (before_set - after_set),
        "no_duplicated_events": duplicates == 0,
    }


def state_signature(recs):
    """An order-independent fingerprint of what the run has DECIDED.

    Deliberately NOT a digest of the queue file: `store.save` rewrites rows and
    a byte digest would make a reordered-but-identical state look changed.
    These are the facts a resume must preserve.
    """
    import hashlib

    rows = []
    for rec in sorted(recs, key=lambda r: str(r.get("id"))):
        for contact in rec.get("contacts") or []:
            rows.append("|".join((
                str(rec.get("id")), str(contact.get("key")),
                "unsub=%s" % bool(contact.get("unsubscribed")),
                "stopped=%s" % bool(contact.get("stopped")),
                "paused=%s" % bool(contact.get("paused")))))
        rows.append("|".join((
            str(rec.get("id")),
            "recpaused=%s" % bool(rec.get("paused")),
            "review=%s" % bool((rec.get("review") or {}).get("open")),
            "state=%s" % rec.get("state"))))
        for key, slots in sorted((rec.get("cadence") or {}).items()):
            for step_key, slot in sorted(slots.items()):
                rows.append("|".join((str(rec.get("id")), key, step_key,
                                      str(slot.get("status")),
                                      str(slot.get("pushed_at")))))
    blob = "\n".join(rows)
    return {"rows": len(rows),
            "md5": hashlib.md5(blob.encode("utf-8")).hexdigest()}


# ============================================================ the day's work

def approve_ready(rec, config, campaign=None, timeline=None, by=APPROVER):
    """Approve every step the REAL gate says may be approved. Nothing else.

    `approve.why_not` is the authority; a step it refuses stays refused and the
    reason is counted. This is the operator's pass, run once per simulated day,
    and it is why `held:draft_not_approved` clears over time rather than being
    written into the fixture.
    """
    approved, refused, already = 0, {}, 0
    if timeline is None:
        timeline = cadence.build(rec, config,
                                 campaign=campaign).get("contacts") or {}
    for contact in rec.get("contacts") or []:
        key = contact.get("key")
        for step_key, step in (timeline.get(key) or {}).items():
            if (step.get("status") or "") in ("pushed", "confirmed",
                                              "cancelled"):
                continue
            # ALREADY APPROVED IS NOT RE-APPROVED, and this is a correction to
            # the harness rather than a shortcut. `approval.is_approved` is the
            # authority: it compares the stored stamp's fingerprint against the
            # step in hand, so it says "yes, THESE words, by that person".
            #
            # Without it the daily pass re-stamped every still-approved step,
            # `approve.approve_step` recorded a fresh DRAFT_APPROVED event each
            # time - `events.record` derives its id from the entry including
            # `at`, and `at` is a new simulated instant every day, so nothing
            # deduplicated it - and a 60-day run accumulated 54,029 events and
            # a 22 MB queue by day 33. State growth per simulated month is one
            # of the things this run exists to MEASURE, and almost all of that
            # growth was the harness talking to itself.
            if approval.is_approved(rec, key, step_key, step=step,
                                    config=config):
                already += 1
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
                label = "NotApprovable: %s" % exc
                refused[label] = refused.get(label, 0) + 1
    if approved:
        approve.sync_state(rec, config, campaign)
    return approved, refused, already


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
        "repeat_contact_step_twice": 0, "already_approved": 0,
    }

    # -------------------------------------------------- 1. the reply watcher
    #
    # The REAL `replywatch.poll_once`: it takes the cross-process lock, writes
    # the status file, moves the checkpoint and counts the health. `now=` is
    # the injected instant; `env=` is the sandbox's fake credentials, which is
    # the parameter `configured` and `expected_workspace` already accept for
    # exactly this purpose.
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
    # copy of the queue, so the list this loop holds is stale. Re-read rather
    # than merge: the file is the state, and a merge here would be a second
    # opinion about what the inbound path decided.
    recs[:] = store.load()

    # ---------------------------------------- 2. approval, then the decision
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
        approved, refusals, already = approve_ready(rec, config,
                                                    campaign=campaign,
                                                    timeline=timeline)
        metrics["approved"] += approved
        metrics["already_approved"] += already
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

                # The hold policy, asked at the SIMULATED instant. This is
                # where `at=` reaches a business rule that takes one, and it
                # is why a 48-hour same-channel hold releases on simulated
                # hour 48 rather than on the wall clock.
                channel = planned.get("channel")
                contact_state = fatigue.contact_check(
                    rec, key, at=clock.at, config=config, channel=channel)
                account_state = fatigue.account_check(
                    rec, at=clock.at, config=config, contact_key=key)
                for bucket, state in (("fatigue_contact",
                                       contact_state["state"]),
                                      ("fatigue_account",
                                       account_state["state"])):
                    metrics[bucket][state] = metrics[bucket].get(state, 0) + 1
                if fatigue.BLOCK in (contact_state["state"],
                                     account_state["state"]):
                    metrics["reasons"]["sandbox:fatigue_block"] = \
                        metrics["reasons"].get("sandbox:fatigue_block", 0) + 1
                    continue

                # The REAL persistence of a send. No provider is contacted:
                # `push.mark_pushed` writes the step, the log line and the
                # PUSH_MARKED event, which is what the live path does once a
                # provider has accepted a payload.
                already = sum(
                    1 for e in rec.get("events") or []
                    if e.get("type") == events.PUSH_MARKED
                    and e.get("contact") == key and e.get("step") == step_key)
                push.mark_pushed(rec, key, step_key, decision["push_id"],
                                 at=clock.now_iso(), day=planned.get("day"))
                if already:
                    metrics["repeat_contact_step_twice"] += 1
                metrics["pushed"] += 1
                counters["pushed_total"] += 1
                pushed_today[key] = pushed_today.get(key, 0) + 1
                body = (planned.get("body") or planned.get("note")
                        or "").strip()
                if body:
                    seen = bodies_today.setdefault(key, set())
                    if body in seen:
                        metrics["copy_repeats"] += 1
                    seen.add(body)

    # The operator's re-approval, after the day's step approvals have moved
    # the campaign's material. See `refresh_campaign_approval`. Skipped once
    # the campaign is stopped: re-approving a paused campaign would be the
    # harness undoing the stop button it is here to test.
    seen = set()
    for campaign in campaigns_by_record.values():
        key = id(campaign)
        if key in seen or campaign.get("status") == campaigns.PAUSED:
            continue
        seen.add(key)
        refresh_campaign_approval(campaign, recs, config)

    metrics["repeat_contact_same_day"] = sum(
        n - 1 for n in pushed_today.values() if n > 1)
    store.save(recs)
    metrics["records"] = len(recs)
    metrics["events_total"] = sum(len(r.get("events") or []) for r in recs)
    # THE EVENT LOG IS APPEND-ONLY, SO THIS NUMBER MAY NEVER GO DOWN.
    #
    # Checked every day rather than only at the two checkpoints the ledger
    # comparison uses, because measured 2026-10-12 on a pre-fix run the total
    # went 1,992 -> 2,003 -> 1,985 -> 1,964 across the resume boundary while a
    # two-point comparison of day 11 against the final state reported NO LOST
    # STATE. It was not reproducible once the redundant daily re-approval was
    # removed, and it may have been an artefact of it - but a two-point
    # comparison that cannot see a dip in between is the wrong instrument
    # whatever caused it, so the dip is now a per-day measurement and is
    # carried into the report rather than inferred.
    #
    # Recorded, not raised: a run that aborts here produces no report, and the
    # report is the evidence.
    previous = counters.get("events_total_last")
    metrics["events_total_previous"] = previous
    metrics["state_regression"] = (previous is not None
                                   and metrics["events_total"] < previous)
    if metrics["state_regression"]:
        counters.setdefault("state_regressions", []).append(
            {"day_index": day_index, "was": previous,
             "now": metrics["events_total"]})
    counters["events_total_last"] = metrics["events_total"]
    metrics["log_lines_total"] = sum(len(r.get("log") or []) for r in recs)
    metrics["queue_bytes"] = (os.path.getsize(store.queue_path())
                              if os.path.exists(store.queue_path()) else 0)
    metrics["paused_records"] = sum(1 for r in recs if r.get("paused"))
    metrics["review_open"] = sum(
        1 for r in recs if (r.get("review") or {}).get("open"))
    metrics["unsubscribed_contacts"] = sum(
        1 for r in recs for c in r.get("contacts") or []
        if c.get("unsubscribed"))
    metrics["stopped_contacts"] = sum(
        1 for r in recs for c in r.get("contacts") or []
        if c.get("stopped"))
    metrics["wire_calls_attempted"] = len(fakes["wire_calls"])
    metrics["adapter_calls"] = (len(fakes["bison"].calls)
                                + len(fakes["heyreach"].calls))
    return metrics


# ============================================================== checkpointing

def write_checkpoint(day_index, clock, state, path):
    """Durable enough to survive a kill. Atomic replace, never in place."""
    recs = store.load()
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
        "signature": state_signature(recs),
        "ledger": _ledger_rows(recs),
    }
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=1, sort_keys=True)
    os.replace(tmp, path)
    return payload


def read_checkpoint(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _append_jsonl(path, row):
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def _month_of(day_index):
    return day_index // 30


# ================================================================= campaigns

def build_campaign(recs, config, cohort="quiet"):
    """A REAL campaign over one cohort, driven to RUNNING by the real rules.

    Built so the campaign PAUSE can be exercised as the stop button it is:
    `eligibility._campaign` answers `blocked:campaign_stopped` for a paused
    campaign and `None` for this one until it is paused. Both directions are
    measured - a pause control with no running baseline proves nothing.

    Every transition goes through `campaigns.set_status`, which REFUSES an
    illegal one, and the fingerprint is computed by `campaigns.fingerprint`
    over the real records rather than written by hand, which is how an
    approval that is not current would masquerade as one that is.
    """
    members = [r for i, r in enumerate(recs, start=1)
               if cohort_of(i) == cohort]
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
    refresh_campaign_approval(campaign, recs, config)
    return {r.get("id"): campaign for r in members}, campaign


def refresh_campaign_approval(campaign, recs, config):
    """Re-take the approval against the campaign's CURRENT material.

    NOT a convenience, and not a weakening. `campaigns.approval_is_current`
    compares the stored fingerprint against `campaigns.fingerprint`, which
    rebuilds the cadence for every record the campaign names - so the daily
    approval pass, which writes an `approval` stamp onto each step, MOVES the
    campaign's material and the campaign approval legitimately goes stale.
    Measured: without this, every member of the campaign cohort answers
    `held:campaign_approval_stale` from the second simulated day onward, and
    the pause control would then have no running baseline to compare against.

    That staleness is the real rule doing its job - "the campaign changed
    after it was approved" - and the honest response is the one an operator
    would make: look at it again and re-approve. So this re-stamps through
    `campaigns.fingerprint` over the real records, exactly as
    `build_campaign` does, and never writes a fingerprint by hand.
    """
    # THE FINGERPRINT GOES ON THE APPROVAL STAMP, and that is not a detail:
    # `campaigns.approval_is_current` compares
    # `campaign["approval"]["fingerprint"]`, NOT `campaign["fingerprint"]`.
    # Writing only the latter - which the first version of this did - leaves
    # the approval permanently stale and every step answers
    # `held:campaign_approval_stale` with a campaign that looks approved.
    #
    # `recs` is the WHOLE record set, the same one `eligibility.decide` is
    # given, because `material` computes `cadence.paused_domains(recs)` and a
    # narrower set can produce a different `paused` on a timeline - two
    # fingerprints of the same campaign that disagree for no reason the
    # campaign can see.
    stamp = campaigns.fingerprint(campaign, recs, config)
    campaign["approval"] = {"action": "approve", "by": APPROVER,
                            "at": store.now(), "fingerprint": stamp}
    campaign["fingerprint"] = stamp
    campaigns.save([campaign])
    return campaign


# ============================================================== clock defects

def clock_defects():
    """Unpatched business-clock reads, reported with file and line.

    TWO scans, because one of them is a zero and a zero that was never shown
    able to be non-zero is not a result:

      `named_set`  `sandboxclock.SIMULATED_PATH_MODULES`, the hand-kept list
                   the brief asks about. Measured 2026-10-12: ZERO.
      `all_src`    the whole of `src/`: 36. That is the positive control for
                   the scanner itself - it demonstrably fires.

    `on_path_but_unnamed` is the finding that matters: modules this process
    actually IMPORTED which the named list omits and which DO hold an
    unpatched read. Loaded is a superset of executed and this says so; the
    one that is PROVEN executed is `evidence.py:106`, by
    `evidence_clock_control` below, which measures the wrong answer rather
    than inferring it from a grep.
    """
    named = sandboxclock.unpatched_business_clock_reads(
        only=sandboxclock.SIMULATED_PATH_MODULES)
    everything = sandboxclock.unpatched_business_clock_reads(only=None)
    loaded = {name.rsplit(".", 1)[-1] + ".py" for name in list(sys.modules)
              if name.startswith("src.")}
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


def status_policy_control(rec, contact):
    """PROOF that the TIMELINE and the SEND GATE disagree about sendability.

    `src/cadence.py:1354` is

        if spec["channel"] == "email" and not lint.sendable(contact):
            return "blocked"

    - `lint.sendable` with NO policy, so it answers under
    `verification.DEFAULT_POLICY`, where `primary` is `contactout`. Productive
    moved primary to `deliverable` and dropped ContactOut from verification;
    `eligibility._email_checks`, `approve.why_not`, `push` and `campaigns` all
    pass `verification.policy_for(config)`, and the comments in the first two
    document this exact defect as having been found and fixed one layer along.
    `cadence.status_for` is the caller that still asks the default.

    The consequence, measured here: every email step on a Productive record
    reports `status: "blocked"` in the timeline a reviewer reads and the
    approval graph walks, while `eligibility.decide` - the authority on
    whether it may go out - answers `eligible` on the same step at the same
    instant. Two answers to one question, and the one a person sees is the
    wrong one.

    Both are called here rather than described, so this is a measurement.
    """
    return {
        "lint_sendable_no_policy": lint.sendable(contact),
        "lint_sendable_client_policy": lint.sendable(
            contact, lint.policy_for_record(rec)),
        "default_policy_primary": verification.DEFAULT_POLICY.get("primary"),
        "client_policy_primary": lint.policy_for_record(rec).get("primary"),
        "disagree": (lint.sendable(contact)
                     != lint.sendable(contact, lint.policy_for_record(rec))),
    }


def evidence_clock_control(rec, sim_today):
    """PROOF, not a grep, that evidence re-ageing reads the REAL clock.

    `quality.assess` calls `_selected(rec, contact)` with no `today`
    (`src/quality.py:350`), which reaches `evidence.recheck(item, None)`
    (`src/quality.py:216`) and `datetime.date.today()`
    (`src/evidence.py:106`). `assess` has no `today`/`at` parameter at all, so
    a caller cannot inject one.

    Measured here by calling `recheck` twice on the SAME stored item - once
    with the simulated date, once the way `quality` calls it - and comparing
    `age_days`. A difference is the defect.
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


# ============================================== run-order (i): one, one day

def run_one(out_dir, seed=1, client="productive", seal_production=True):
    """ONE contact, ONE simulated day, through the existing flow, in order.

    The flow's steps are NOT reordered. The order is `simulator.simulate`'s own
    - record scope, company acceptance, pause state, then per contact
    quality -> channels -> mx -> lint -> duplicates -> timeline, then spend,
    then approval - and whatever it produces is what is printed, refusals
    included.

    Day 0 and day 1 are both reported. On day 0 nothing is due, because the
    first step of `productive_li_heavy_v1` is day 1; reporting day 0 as a pass
    would be reading the convention backwards, and skipping it would be hiding
    the step that holds.
    """
    handles = _boot(out_dir, seal_production=seal_production)
    clock = handles["clock"]
    config = clients.load(client)
    out = {"at_utc": clock.now_iso(), "local": clock.local().isoformat(),
           "utc_offset_hours": clock.utc_offset_hours(),
           "store_queue": store.queue_path(),
           "store_campaigns": store.campaigns_path(),
           "wire_sealed_control_fired": True,
           "readbacks_sealed_control_fired": True,
           "store_barrier_active": store.under_test()}
    try:
        recs, _blob = load_fixture(seed)
        recs = recs[:1]
        rec = recs[0]
        rec["contacts"] = rec["contacts"][:1]
        contact = rec["contacts"][0]
        out["fixture"] = os.path.basename(fixture_path(seed))
        out["copy_install"] = install_phase5_copy(recs, config)
        store.save(recs)

        out["record_id"] = rec["id"]
        out["contact_key"] = contact["key"]
        out["domain"] = rec["domain"]
        policy = lint.policy_for_record(rec)
        resolved = verification.resolve(contact, policy)
        out["verification"] = {
            "policy_primary": policy.get("primary"),
            "policy_required_confirmations":
                policy.get("required_confirmations"),
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
            "mode": card["mode"], "held": card["held"],
            "personalization_band":
                card["personalization_quality"].get("band"),
            "timeline_rows": len(card["timeline"]),
            "timeline_not_planned": sum(1 for r in card["timeline"]
                                        if r["status"] == "not_planned"),
        }
        # THE DEFECT THIS EXPOSES, measured rather than asserted: the
        # preview's timeline walks `cadence.STEPS` while the record's real
        # sequence is the client's library cadence, so every row reads
        # "not planned" and the preview shows none of the ten real steps.
        built = cadence.build(rec, config, recs=recs).get("contacts") or {}
        out["cadence_build_steps"] = sorted(built.get(contact["key"]) or {})
        out["simulator_timeline_steps"] = [r["step"] for r in card["timeline"]]
        out["simulator_timeline_matches_cadence"] = (
            sorted(out["simulator_timeline_steps"])
            == sorted(out["cadence_build_steps"]))

        approved, refusals, _already = approve_ready(rec, config)
        out["approved"] = approved
        out["approval_refusals"] = refusals

        def decide_all(day):
            timeline = cadence.build(rec, config,
                                     recs=recs).get("contacts") or {}
            rows = []
            for step_key in sorted(timeline.get(contact["key"]) or {}):
                planned = timeline[contact["key"]][step_key]
                decision = eligibility.decide(rec, contact, step_key,
                                              recs=recs, config=config,
                                              day=day, timeline=timeline)
                rows.append({"step": step_key, "day": planned.get("day"),
                             "channel": planned.get("channel"),
                             "status": planned.get("status"),
                             "verdict": decision["verdict"],
                             "reasons": decision["reasons"],
                             # Carried from the decision that authorised it.
                             # Re-deciding after the first push would ask a
                             # record that has already changed, and
                             # `_already_pushed` would then answer `blocked`
                             # with no push_id - which is the right answer to
                             # the wrong question.
                             "push_id": decision.get("push_id")})
            return rows

        out["day_0"] = {"decisions": decide_all(0)}
        out["day_0"]["eligible"] = [d["step"] for d in out["day_0"]["decisions"]
                                    if d["verdict"] == eligibility.ELIGIBLE]
        crossings = clock.advance(hours=ADVANCE_HOURS)
        out["advanced"] = {"crossings": crossings,
                           "at_utc": clock.now_iso(),
                           "local": clock.local().isoformat()}
        out["day_1"] = {"decisions": decide_all(1)}
        out["day_1"]["eligible"] = [d["step"] for d in out["day_1"]["decisions"]
                                    if d["verdict"] == eligibility.ELIGIBLE]
        pushed = []
        for row in out["day_1"]["decisions"]:
            if row["verdict"] != eligibility.ELIGIBLE:
                continue
            push.mark_pushed(rec, contact["key"], row["step"],
                             row["push_id"], at=clock.now_iso(),
                             day=row["day"])
            pushed.append(row["step"])
        out["day_1"]["pushed"] = pushed
        store.save(recs)
        out["events_after"] = [e.get("type") for e in rec.get("events") or []]
        out["fatigue_contact"] = fatigue.contact_check(
            rec, contact["key"], at=clock.at, config=config)["state"]
        out["fatigue_account"] = fatigue.account_check(
            rec, at=clock.at, config=config)["state"]
        out["evidence_clock_control"] = evidence_clock_control(
            rec, clock.at.date().isoformat())
        out["status_policy_control"] = status_policy_control(rec, contact)
        out["wire_calls_attempted"] = len(handles["wire_calls"])
        out["wire_calls_allowed"] = 0
        out["credits_spent"] = waterfall.spend(rec)["expected"]
        if handles["production_before"] is not None:
            sandboxharness.assert_production_unchanged(
                handles["production_before"])
            out["production_unchanged"] = True
        return out
    finally:
        handles["teardown"]()


# ================================ run-order: the four mandatory reply shapes

def _eligible_steps(rec, contact_key, config, day):
    """Which steps `eligibility.decide` would let out right now.

    The measurement unit for CADENCE STOP. Comparing this set before and after
    a reply is the only honest proof that the reply changed anything - which is
    the argument `replaysim.simulate` makes in its own source, and it is why
    this asks `eligibility.decide` rather than reading a pause field.
    """
    timeline = cadence.build(rec, config, recs=[rec]).get("contacts") or {}
    contact = next((c for c in rec.get("contacts") or []
                    if c.get("key") == contact_key), None)
    out = set()
    if contact is None:
        return out
    for step_key in timeline.get(contact_key) or {}:
        decision = eligibility.decide(rec, contact, step_key, recs=[rec],
                                      config=config, day=day,
                                      timeline=timeline)
        if decision["verdict"] == eligibility.ELIGIBLE:
            out.add(step_key)
    return out


def _axes(rec, contact_key, eligible_before, eligible_after):
    """THE THREE THINGS THAT MUST NOT BE CONFLATED, read independently.

    A reply can legitimately stop a cadence without being a permanent opt-out,
    and an ambiguous reply must end in HUMAN REVIEW rather than in a confident
    verdict. So these are four separate reads of four separate pieces of state,
    and no one of them is inferred from another:

    classification     the `REPLY_CLASSIFIED` event's own word, as persisted.
                       Reported UNVERIFIED everywhere: the classifier lane's
                       work was refused by adversarial review and nothing here
                       depends on it.
    cadence_stop       a step that WAS eligible is not eligible now. Measured
                       by set difference. Asserting a pause field would prove
                       the field, not the effect.
    permanent_optout   `contact["unsubscribed"]`, written only by
                       `accountpolicy._suppress_contact`, which documents
                       itself as permanent and outranking every other contact
                       state. Nothing in the pipeline lifts it.
    human_review       `rec["review"]["open"]`, written only by
                       `accountpolicy._require_review`.
    """
    contact = next((c for c in rec.get("contacts") or []
                    if c.get("key") == contact_key), None) or {}
    classified = [e for e in rec.get("events") or []
                  if e.get("type") == events.REPLY_CLASSIFIED
                  and e.get("contact") == contact_key]
    received = [e for e in rec.get("events") or []
                if e.get("type") == events.REPLY_RECEIVED
                and e.get("contact") == contact_key]
    before, after = set(eligible_before), set(eligible_after)
    return {
        "reply_received_event": bool(received),
        "verdict_persisted": bool(classified),
        "classification": (classified[-1].get("classification")
                           if classified else None),
        "classification_outcome": (classified[-1].get("outcome")
                                   if classified else None),
        "eligible_before": sorted(before),
        "eligible_after": sorted(after),
        # A stop is only demonstrable when something was going out. With an
        # empty `before` this is False and says so, rather than reporting a
        # vacuous pass.
        "cadence_stop": bool(before) and not (before & after),
        "permanent_optout": bool(contact.get("unsubscribed")),
        "contact_stopped": bool(contact.get("stopped")),
        "contact_paused": bool(contact.get("paused")),
        "record_paused": bool(rec.get("paused")),
        "human_review": bool((rec.get("review") or {}).get("open")),
    }


def reply_scenarios(out_dir, seed=1, client="productive",
                    seal_production=True):
    """The four mandatory shapes, each through the REAL ingestion entry point.

    `replaysim.simulate` is deliberately NOT used. It calls `inbound.handle`
    directly with an event it built itself, so on its own it does not prove
    that the WATCHER calls ingestion, that a verdict is PERSISTED into
    `work/`, or that an unattributed reply is retained. Each case is therefore
    driven through `replywatch.poll_once` with a PROVIDER-SHAPED row, and
    those three things are asserted separately.

    The measured fact that makes this necessary: `src/inbound.py:429` is
    `if applied["status"] != "applied": return outcome`, which returns BEFORE
    the classify/store step whenever a reply cannot be attributed.

    EACH CASE GETS ITS OWN SIMULATED DAY. That is not cosmetic: the first run
    of this probe put four rows on one instant and the REAL high-water mark
    filtered three of them out as already-seen, reporting three empty cases.
    A rising stamp per case is what the live feed produces, and it is what
    keeps the checkpoint exercised instead of worked around.
    """
    handles = _boot(out_dir, seal_production=seal_production)
    clock = handles["clock"]
    config = clients.load(client)
    adapter_log = os.path.join(handles["sandbox_dir"], "adapter-calls.jsonl")
    fake_bison = FakeBison(clock, log_path=adapter_log)
    fake_heyreach = FakeHeyReach(clock, log_path=adapter_log)
    undo_fakes = install_fake_providers(fake_bison, fake_heyreach)
    results = {"cases": {}, "unattributed": {}, "ingestion_entry": {},
               "window": {}}
    try:
        all_recs, _blob = load_fixture(seed)
        # One fresh record per case plus one for the unattributed probe. A
        # shared record would carry the first case's pause into every case
        # after it, which is `replaysim.run_all`'s own documented reason for
        # working on copies.
        names = list(REPLY_CASES)
        chosen = all_recs[:len(names) + 1]
        install_phase5_copy(chosen, config)
        store.save(chosen)

        # Bring each record to a state where steps ARE eligible, using the
        # real approval pass and the real connection acceptance, so that
        # "cadence stop" is measured against something that was going out.
        fake_heyreach.rows = [heyreach_row(rec, rec["contacts"][0], 0)
                              for rec in chosen]
        status_li = replywatch.poll_once("heyreach", max_pages=5, live=True,
                                         env=SANDBOX_ENV,
                                         now=clock.now_iso())
        results["connection_acceptance"] = {
            "healthy": status_li.get("healthy"),
            "ingested": status_li.get("new_replies_ingested")}
        # Far enough in that the cadence's later steps are due, so there is a
        # sequence left to stop.
        for _ in range(20):
            clock.advance(hours=ADVANCE_HOURS)
        recs = store.load()
        for rec in recs:
            approve_ready(rec, config)
        store.save(recs)
        recs = store.load()
        by_id = {r["id"]: r for r in recs}
        results["window"] = {"day_index": clock.day_index,
                             "at_utc": clock.now_iso(),
                             "local": clock.local().isoformat(),
                             "utc_offset_hours": clock.utc_offset_hours()}

        for position, name in enumerate(names):
            spec = REPLY_CASES[name]
            rid = chosen[position]["id"]
            rec_before = by_id[rid]
            contact = rec_before["contacts"][0]
            day = clock.day_index
            before = _eligible_steps(rec_before, contact["key"], config, day)
            fake_bison.rows = [bison_row(rid, rec_before["client"],
                                         contact["key"], contact["email"],
                                         day, "reply", spec["text"],
                                         suffix="-" + name)]
            status = replywatch.poll_once("emailbison", max_pages=5,
                                          live=True, env=SANDBOX_ENV,
                                          now=clock.now_iso())
            after_recs = store.load()
            rec_after = next(r for r in after_recs if r["id"] == rid)
            after = _eligible_steps(rec_after, contact["key"], config, day)
            axes = _axes(rec_after, contact["key"], before, after)
            expect = spec["expect"]
            per_axis = {axis: (axes[axis] == expect[axis]) for axis in expect}
            results["cases"][name] = {
                "text": spec["text"], "why": spec["why"],
                "record_id": rid, "contact": contact["key"],
                "day_index": day,
                "watcher_ingested": status.get("new_replies_ingested"),
                "watcher_events_inspected": status.get("events_inspected"),
                "watcher_healthy": status.get("healthy"),
                "watcher_checkpoint": status.get("checkpoint"),
                "axes": axes, "expected": expect, "per_axis_pass": per_axis,
                "pass": all(per_axis.values()),
                "classification_is_unverified": True,
            }
            # A rising stamp, as a live feed produces. See the docstring.
            clock.advance(hours=ADVANCE_HOURS)
            by_id = {r["id"]: r for r in store.load()}

        # ---------------------------------------- the unattributed reply path
        rec_un = chosen[len(names)]
        unknown_address = "alias-nobody@%s" % rec_un["domain"]
        day = clock.day_index
        before_notes = len(notify.load())
        fake_bison.rows = [bison_row(None, rec_un["client"], None,
                                     unknown_address, day, "reply",
                                     EXPLICIT_REMOVAL, suffix="-unattrib")]
        status = replywatch.poll_once("emailbison", max_pages=5, live=True,
                                      env=SANDBOX_ENV, now=clock.now_iso())
        after_recs = store.load()
        traces = [(r["id"], e.get("type")) for r in after_recs
                  for e in r.get("events") or []
                  if str(e.get("provider_event_id") or "").endswith(
                      "-unattrib")]
        rows = notify.load()
        unmatched_notes = [n for n in rows
                           if n.get("type") == notify.UNMATCHED_REPLY]
        results["unattributed"] = {
            "address": unknown_address,
            "day_index": day,
            "watcher_ran": status.get("healthy"),
            "events_inspected": status.get("events_inspected"),
            "ingested_as_applied": status.get("new_replies_ingested"),
            "reported_unmatched": status.get("ambiguous_identities"),
            # (1) did ingestion see it at all
            "ingestion_saw_it": bool(status.get("events_inspected")),
            # (2) is a verdict persisted - measured, not assumed
            "reply_event_persisted_on_any_record": bool(traces),
            "classification_persisted": any(
                t[1] == events.REPLY_CLASSIFIED for t in traces),
            # (3) is it retained somewhere durable a person will see
            "notification_rows_before": before_notes,
            "notification_rows_after": len(rows),
            "unmatched_notification_rows": len(unmatched_notes),
            "retained_as_notification": bool(unmatched_notes),
            "notification_destination": sorted(
                {n.get("destination") for n in unmatched_notes}),
        }
        results["unattributed"]["finding"] = (
            "src/inbound.py:429 - `if applied[\"status\"] != \"applied\": "
            "return outcome` - returns before the classify/store step for an "
            "unattributable reply. MEASURED HERE: ingestion saw it (%s), it "
            "was reported unmatched (%s), %d durable UNMATCHED_REPLY "
            "notification row(s) were written, and NO reply event and NO "
            "classification were persisted on any record (%s). So the arrival "
            "IS retained and visible to a person; the reply's TEXT and "
            "VERDICT are not retained in work/ at all."
            % (results["unattributed"]["ingestion_saw_it"],
               results["unattributed"]["reported_unmatched"],
               results["unattributed"]["unmatched_notification_rows"],
               bool(traces)))

        # --------------------------------- the three ingestion-entry asserts
        results["ingestion_entry"] = {
            # (i) the watcher really does call ingestion
            "watcher_calls_ingestion": any(
                c["fn"] == "bison.fetch_replies" for c in fake_bison.calls),
            "watcher_fetch_calls": sum(
                1 for c in fake_bison.calls
                if c["fn"] == "bison.fetch_replies"),
            "workspace_pin_checked": any(
                c["fn"] == "bison.bound_workspace" for c in fake_bison.calls),
            "every_case_was_ingested": all(
                case["axes"]["reply_received_event"]
                for case in results["cases"].values()),
            # (ii) a verdict is persisted for an attributable reply
            "verdict_persisted_for_attributed": all(
                case["axes"]["verdict_persisted"]
                for case in results["cases"].values()),
            # (iii) an unattributed reply is retained, not silently dropped
            "unattributed_retained_not_dropped":
                results["unattributed"]["retained_as_notification"],
            "unattributed_verdict_persisted":
                results["unattributed"]["classification_persisted"],
        }
        results["wire_calls_attempted"] = len(handles["wire_calls"])
        results["adapter_calls"] = (len(fake_bison.calls)
                                    + len(fake_heyreach.calls))
        if handles["production_before"] is not None:
            sandboxharness.assert_production_unchanged(
                handles["production_before"])
            results["production_unchanged"] = True
        return results
    finally:
        undo_fakes()
        handles["teardown"]()


def audit_finished_run(out_dir, client="productive", seal_production=True):
    """Measure a FINISHED run's own final state, with the owning modules.

    Separate from the run because two of the questions the brief asks cannot
    be answered honestly by a per-day counter:

    COPY REPETITION FOR THE SAME PERSON. `run_day`'s `copy_repeats` compares
    the bodies pushed to one contact WITHIN one simulated day, which with a
    distinct template per step is structurally zero and therefore proves very
    little. `duplicates.for_contact` is the module that owns the question -
    it compares every pair of a contact's email steps, body and subject, with
    `duplicates.substantive` doing the normalisation - and this asks it over
    the state the run actually produced.

    REPEAT CONTACT TO THE SAME PERSON. Counted from the PUSH_MARKED events on
    the record rather than from a running total, because the event ledger is
    what a resume has to preserve and what reporting reads. Two figures, kept
    apart: the same person touched more than once (expected - that is a
    cadence), and the same person touched on the same STEP more than once
    (must be zero; `eligibility._already_pushed` and `push.already_pushed`
    are what keep it there, and a resume boundary is where it would break).

    Read-only: it boots sealed and clocked like everything else, but writes
    nothing to the state directory.
    """
    from src import duplicates

    handles = _boot(out_dir, seal_production=seal_production)
    config = clients.load(client)
    try:
        recs = store.load()
        if not recs:
            raise SandboxRefused(
                "no records under %s - audit reads a FINISHED run's state and "
                "there is none here" % os.path.join(out_dir, "state"))
        paused_set = cadence.paused_domains(recs)
        bodies, subjects, per_contact_findings = 0, 0, 0
        contacts_with_duplicate_body = []
        touches = {}
        step_touches = {}
        for rec in recs:
            timeline = cadence.build(rec, config,
                                     paused_set=paused_set).get("contacts") or {}
            for contact in rec.get("contacts") or []:
                key = contact.get("key")
                findings = duplicates.for_contact(rec, key, timeline, config)
                for finding in findings:
                    per_contact_findings += 1
                    if finding["code"] == duplicates.DUPLICATE_BODY:
                        bodies += 1
                        contacts_with_duplicate_body.append(
                            "%s:%s %s" % (rec["id"], key, finding["steps"]))
                    elif finding["code"] == duplicates.DUPLICATE_SUBJECT:
                        subjects += 1
            for entry in rec.get("events") or []:
                if entry.get("type") != events.PUSH_MARKED:
                    continue
                who = (rec["id"], entry.get("contact"))
                touches[who] = touches.get(who, 0) + 1
                slot = (rec["id"], entry.get("contact"), entry.get("step"))
                step_touches[slot] = step_touches.get(slot, 0) + 1
        repeated = {who: n for who, n in touches.items() if n > 1}
        twice = {slot: n for slot, n in step_touches.items() if n > 1}
        return {
            "records": len(recs),
            "contacts": sum(len(r.get("contacts") or []) for r in recs),
            "people_touched_at_all": len(touches),
            "people_touched_more_than_once": len(repeated),
            "max_touches_to_one_person": max(touches.values()) if touches else 0,
            "same_step_pushed_twice": len(twice),
            "same_step_pushed_twice_examples": sorted(
                "%s:%s:%s x%d" % (a, b, c, n)
                for (a, b, c), n in list(twice.items())[:10]),
            "duplicate_body_findings": bodies,
            "duplicate_subject_findings": subjects,
            "duplicate_body_examples": contacts_with_duplicate_body[:10],
            "duplicates_module": "src/duplicates.py:for_contact",
        }
    finally:
        handles["teardown"]()


# ================================================== run-order (iii): 60 days

def run_full(out_dir, seed=1, days=DAYS, kill_after_day=None, resume=False,
             checkpoint_every=CHECKPOINT_EVERY, client="productive",
             quiet=False, seal_production=True, companies=None):
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
            days = saved["days"]
            start_days = saved["start_days"]
            plan = saved["plan"]
            counters = saved["counters"]
            fake_bison.rows = saved["bison_rows"]
            fake_heyreach.rows = saved["heyreach_rows"]
            fake_bison.fail_on_days = set(saved["fail_on_days"])
            state = {"seed": seed, "companies": saved["companies"],
                     "days": days, "start_days": start_days, "plan": plan,
                     "bison_rows": fake_bison.rows,
                     "heyreach_rows": fake_heyreach.rows,
                     "campaign_ids": saved["campaign_ids"],
                     "counters": counters,
                     "fail_on_days": fake_bison.fail_on_days}
            # The clock is RE-DERIVED from the day index, never trusted from
            # the file: a resumed run that trusted a stored instant could
            # drift from the day index it also stores, and the two would then
            # disagree about which day it is.
            for _ in range(first_day):
                crossings.extend(clock.advance(hours=ADVANCE_HOURS))
            recs = store.load()
            rows = campaigns.load()
            found = campaigns.get(saved["campaign_ids"]["campaign_id"], rows) \
                if saved["campaign_ids"].get("campaign_id") else None
            campaigns_by_record = {
                rid: found
                for rid in saved["campaign_ids"].get("record_ids") or ()
                if found}
            resumed_from = saved
        else:
            first_day = 0
            recs, _blob = load_fixture(seed)
            if companies:
                recs = recs[:companies]
            install_phase5_copy(recs, config)
            store.save(recs)
            import random

            rng = random.Random(seed ^ 0x5A5A)
            start_days = {r["id"]: rng.randrange(0, 8) for r in recs}
            bison_rows, heyreach_rows, plan = build_feed(recs)
            fake_bison.rows = bison_rows
            fake_heyreach.rows = heyreach_rows
            # Two consecutive days of provider failure, mid-run, so the run
            # covers both the transient error AND recovery with no lost rows.
            fake_bison.fail_on_days = {24, 25}
            campaigns_by_record, campaign = build_campaign(recs, config)
            counters = {"pushed_total": 0}
            state = {"seed": seed, "companies": len(recs), "days": days,
                     "start_days": start_days, "plan": plan,
                     "bison_rows": bison_rows,
                     "heyreach_rows": heyreach_rows,
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
            # The campaign stop button, pressed once, mid-run. Measured in
            # both directions: the days before show the cohort deciding
            # normally, the days after show every step blocked.
            if day_index == 40 and campaigns_by_record:
                campaign = next(iter(campaigns_by_record.values()))
                if campaign.get("status") != campaigns.PAUSED:
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
                print("  day %2d %s local %s %+g  bison(ok=%s in=%s) "
                      "approved=%-4d pushed=%-4d paused=%-3d unsub=%-3d "
                      "review=%d"
                      % (day_index, metrics["date_utc"],
                         metrics["local"][11:16], metrics["utc_offset_hours"],
                         metrics["poll"]["emailbison"]["healthy"],
                         metrics["poll"]["emailbison"]["ingested"],
                         metrics["approved"], metrics["pushed"],
                         metrics["paused_records"],
                         metrics["unsubscribed_contacts"],
                         metrics["review_open"]))

            if ((day_index + 1) % checkpoint_every == 0
                    or day_index == days - 1):
                written = write_checkpoint(day_index, clock, state,
                                           checkpoint_path)
                if not quiet:
                    print("  CHECKPOINT day %d: %d ledger rows, signature %s"
                          % (day_index, len(written["ledger"]),
                             written["signature"]["md5"][:12]))
                if kill_after_day is not None and day_index == kill_after_day:
                    # A REAL kill. `os._exit` runs no finally block, no atexit
                    # handler and no buffer flush beyond what is already on
                    # disk - the point being that anything the resume recovers
                    # was genuinely durable.
                    sys.stdout.flush()
                    os._exit(KILL_EXIT_CODE)

            if day_index < days - 1:
                crossings.extend(clock.advance(hours=ADVANCE_HOURS))

        return _finish(handles, fakes, state, day_metrics, crossings,
                       months_path, sandbox_dir, config, resumed_from,
                       campaign_paused_on)
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
            "repeat_contact_same_day": 0, "repeat_contact_step_twice": 0,
            "copy_repeats": 0, "verdicts": {}, "reasons": {}})
        bucket["days"] += 1
        bucket["pushed"] += metrics["pushed"]
        bucket["approved"] += metrics["approved"]
        for poll in metrics["poll"].values():
            bucket["ingested"] += int(poll.get("ingested") or 0)
            bucket["unmatched"] += int(poll.get("unmatched") or 0)
            if poll.get("error"):
                bucket["poll_failures"] += 1
        for field in ("repeat_contact_same_day", "repeat_contact_step_twice",
                      "copy_repeats"):
            bucket[field] += metrics[field]
        for name, n in metrics["verdicts"].items():
            bucket["verdicts"][name] = bucket["verdicts"].get(name, 0) + n
        for name, n in metrics["reasons"].items():
            bucket["reasons"][name] = bucket["reasons"].get(name, 0) + n
        for field in ("events_total", "queue_bytes", "paused_records",
                      "unsubscribed_contacts", "stopped_contacts",
                      "review_open", "log_lines_total"):
            bucket["%s_end" % field] = metrics[field]
    for bucket in sorted(months.values(), key=lambda b: b["month"]):
        _append_jsonl(months_path, bucket)

    ledger = _ledger_rows(recs)
    with open(os.path.join(sandbox_dir, "ledger.json"), "w",
              encoding="utf-8", newline="\n") as handle:
        json.dump([list(row) for row in ledger], handle, indent=0)

    spend = sum(waterfall.spend(rec)["expected"] for rec in recs)
    report = {
        "start_utc": START.isoformat(),
        "end_utc": handles["clock"].now_iso(),
        "zone": str(ZAGREB),
        "seed": state["seed"],
        "days_simulated": len(day_metrics),
        "crossings": sorted(set(crossings)),
        "dst_crossed": any(c.startswith("dst_change") for c in crossings),
        "records": len(recs),
        "contacts": sum(len(r.get("contacts") or []) for r in recs),
        "events_total": sum(len(r.get("events") or []) for r in recs),
        "ledger_rows": len(ledger),
        "ledger_unique": len(set(ledger)),
        "no_duplicated_events": len(ledger) == len(set(ledger)),
        # Every day of the run, not two points of it. See `run_day`.
        "state_regressions": state["counters"].get("state_regressions") or [],
        "event_total_monotonic": not (
            state["counters"].get("state_regressions") or []),
        "pushed_total": state["counters"]["pushed_total"],
        "paused_records": sum(1 for r in recs if r.get("paused")),
        "review_open": sum(1 for r in recs
                           if (r.get("review") or {}).get("open")),
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
        "signature": state_signature(recs),
        "months": [months[k] for k in sorted(months)],
        "clock_defects": clock_defects(),
        "evidence_clock_control": evidence_clock_control(
            recs[0], handles["clock"].at.date().isoformat()) if recs else {},
        "status_policy_control": (status_policy_control(
            recs[0], recs[0]["contacts"][0]) if recs else {}),
        "resumed_from": (resumed_from or {}).get("day_index"),
        "removal_audit": removal_audit(recs, state["plan"]),
        "store_barrier_active": store.under_test(),
    }
    if handles["production_before"] is not None:
        sandboxharness.assert_production_unchanged(handles["production_before"])
        report["production_unchanged"] = True
    else:
        report["production_unchanged"] = None
    with open(os.path.join(sandbox_dir, "report.json"), "w",
              encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=1, sort_keys=True, default=str)
    return report


def removal_audit(recs, plan):
    """AN EXPLICIT REMOVAL MUST PREVENT EVERY SUBSEQUENT CONTACT.

    The named pass criterion, and it is audited from what the flow actually did
    rather than from a flag. Four things, each independent:

      1. the reply was ingested at all (a `REPLY_RECEIVED` event exists)
      2. the contact carries `unsubscribed` - the PERMANENT opt-out field that
         `eligibility._replied` reads
      3. `eligibility.must_not_contact` refuses them. Asked directly, so the
         answer does not depend on a step existing
      4. NO `push_marked` event for that contact is dated AFTER the reply

    (4) is the one that matters across a resume: a resumed run that reloaded
    the record without the flag would push again, and (2) and (3) would then be
    measuring a record that had already been written to.
    """
    by_id = {r.get("id"): r for r in recs}
    rows = []
    for rid, entry in (plan or {}).items():
        spec = entry.get("removal")
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
        rows.append({
            "record_id": rid, "contact": spec["contact"],
            "scheduled_day": spec["day"],
            "reply_ingested": bool(reply_at), "reply_at": reply_at,
            "unsubscribed": bool(contact.get("unsubscribed")),
            "record_paused": bool(rec.get("paused")),
            "must_not_contact": [r for r in
                                 eligibility.must_not_contact(rec, contact)
                                 if r],
            "pushes_after_removal": len(after),
        })
    ingested = [r for r in rows if r.get("reply_ingested")]
    return {
        "scheduled": len(rows),
        "ingested": len(ingested),
        "unsubscribed": sum(1 for r in ingested if r.get("unsubscribed")),
        "refused_by_eligibility": sum(1 for r in ingested
                                      if r.get("must_not_contact")),
        "pushes_after_removal": sum(r.get("pushes_after_removal") or 0
                                    for r in ingested),
        "all_prevented": bool(ingested) and all(
            r.get("unsubscribed") and r.get("must_not_contact")
            and not r.get("pushes_after_removal") for r in ingested),
        "rows": rows[:10],
    }


# ===================================================================== CLI

def _print_report(report):
    print("\n==== SANDBOX REPORT ====")
    for field in ("start_utc", "end_utc", "zone", "seed", "days_simulated",
                  "dst_crossed", "crossings", "records", "contacts",
                  "events_total", "ledger_rows", "ledger_unique",
                  "no_duplicated_events", "event_total_monotonic",
                  "state_regressions", "pushed_total", "paused_records",
                  "unsubscribed_contacts", "review_open",
                  "wire_calls_attempted", "wire_calls_allowed",
                  "adapter_calls_bison", "adapter_calls_heyreach",
                  "provider_failures_simulated", "credits_spent",
                  "campaign_paused_on_day", "production_unchanged",
                  "store_barrier_active", "resumed_from"):
        print("  %-30s %s" % (field, report.get(field)))
    print("  %-30s %s" % ("signature", report["signature"]["md5"]))
    print("  %-30s %s" % ("removal (explicit opt-out)", json.dumps(
        {k: v for k, v in report["removal_audit"].items() if k != "rows"})))
    print("  %-30s %s" % ("evidence clock control",
                          json.dumps(report["evidence_clock_control"])))
    print("  %-30s %s" % ("status/eligibility policy",
                          json.dumps(report["status_policy_control"])))
    print("  %-30s %d (positive control: %d over all of src/)"
          % ("clock defects, named set",
             report["clock_defects"]["named_set_count"],
             report["clock_defects"]["all_src_count"]))
    print("  %-30s %d" % ("clock defects, on path & unnamed",
                          report["clock_defects"]["on_path_but_unnamed_count"]))
    for row in report["clock_defects"]["on_path_but_unnamed"]:
        print("      %s:%d  %s  %s"
              % (os.path.relpath(row["file"], ROOT), row["line"], row["kind"],
                 row["source"][:66]))
    print("\n  per-month state growth")
    print("      %-5s %-5s %-7s %-7s %-8s %-9s %-7s %-6s %-7s"
          % ("month", "days", "pushed", "approvd", "ingested", "events", "bytes",
             "paused", "unsub"))
    for bucket in report["months"]:
        print("      %-5s %-5s %-7s %-7s %-8s %-9s %-7s %-6s %-7s"
              % (bucket["month"], bucket["days"], bucket["pushed"],
                 bucket["approved"], bucket["ingested"],
                 bucket.get("events_total_end"),
                 bucket.get("queue_bytes_end"),
                 bucket.get("paused_records_end"),
                 bucket.get("unsubscribed_contacts_end")))
    print("  repeat contact (same person, same day, >1 push): %s"
          % sum(b["repeat_contact_same_day"] for b in report["months"]))
    print("  repeat contact (same person, SAME STEP twice):   %s"
          % sum(b["repeat_contact_step_twice"] for b in report["months"]))
    print("  copy repetition (same body twice to one person): %s"
          % sum(b["copy_repeats"] for b in report["months"]))


def main(argv=None):
    p = argparse.ArgumentParser(prog="py -3 scripts/sandbox_run.py",
                               description=__doc__)
    p.add_argument("--mode",
                   choices=("one", "replies", "full", "audit"),
                   default="full")
    p.add_argument("--out", required=True,
                   help="the sandbox directory. State and metrics live here, "
                        "and it must not be inside the production work/.")
    p.add_argument("--seed", type=int, default=1,
                   help="which docs/sandbox/fixture-seed-<N>.json to read")
    p.add_argument("--days", type=int, default=DAYS)
    p.add_argument("--companies", type=int, default=None,
                   help="truncate the fixture. For smoke runs only; the "
                        "reported run uses all 100.")
    p.add_argument("--client", default="productive")
    p.add_argument("--checkpoint-every", type=int, default=CHECKPOINT_EVERY)
    p.add_argument("--kill-after-day", type=int, default=None,
                   help="os._exit(%d) immediately after that day's "
                        "checkpoint. A real kill: no finally, no atexit."
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
        result = run_one(out_dir, seed=a.seed, client=a.client)
        print(json.dumps(result, indent=2, default=str))
        print("\nRUN-ORDER (i): one contact, one simulated day.")
        print("  day 0 eligible: %s   (nothing is due: li1/em1 are cadence "
              "day 1)" % result["day_0"]["eligible"])
        print("  day 1 eligible: %s" % result["day_1"]["eligible"])
        print("  day 1 pushed:   %s" % result["day_1"]["pushed"])
        return 0

    if a.mode == "audit":
        result = audit_finished_run(out_dir, client=a.client)
        print(json.dumps(result, indent=2, default=str))
        return 0

    if a.mode == "replies":
        result = reply_scenarios(out_dir, seed=a.seed, client=a.client)
        print(json.dumps(result, indent=2, default=str))
        print("\n==== THE FOUR MANDATORY REPLY SHAPES ====")
        print("Classification is UNVERIFIED: the classifier lane's work was "
              "refused by adversarial review and nothing here depends on it.")
        print("  %-38s %-12s %-6s %-7s %-7s %s"
              % ("case", "class", "stop", "optout", "review", "verdict"))
        for name, case in result["cases"].items():
            axes = case["axes"]
            print("  %-38s %-12s %-6s %-7s %-7s %s"
                  % (name[:38], axes["classification"], axes["cadence_stop"],
                     axes["permanent_optout"], axes["human_review"],
                     "PASS" if case["pass"] else "FAIL"))
        for name, case in result["cases"].items():
            if not case["pass"]:
                print("\n  FAIL %s" % name)
                print("       %s" % case["why"])
                for axis, ok in case["per_axis_pass"].items():
                    if not ok:
                        print("       %-18s measured %s, expected %s"
                              % (axis, case["axes"][axis],
                                 case["expected"][axis]))
        print("\n  ingestion entry point: %s"
              % json.dumps(result["ingestion_entry"]))
        print("  unattributed reply: %s"
              % json.dumps({k: v for k, v in result["unattributed"].items()
                            if k != "finding"}))
        print("  %s" % result["unattributed"]["finding"])
        return 0

    report = run_full(out_dir, seed=a.seed, days=a.days,
                      kill_after_day=a.kill_after_day, resume=a.resume,
                      checkpoint_every=a.checkpoint_every, client=a.client,
                      quiet=a.quiet, companies=a.companies)
    if a.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        _print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
