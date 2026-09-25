#!/usr/bin/env python3
"""What this client has already spent, durably, across runs.

## The hole this fills

`enrich.Budget` is the only spend control there is, and it lives in memory for
the length of one invocation. So `--cap 260` means "260 credits in THIS run"
and nothing anywhere remembers the last one. On 2026-09-10 I ran three passes
over the same cohort at cap 260 each; every one was individually within
budget, and no part of the system could have told you the total.

`pilotcaps` bounds VOLUME - companies, contacts, sends per day - which is a
different question and does not bound money at all. A single company can cost
one credit or forty depending on how far down the waterfall it goes.

There is also no monetary budget anywhere in this repository. Searched for on
2026-09-10: no per-day cap, no per-provider cap, no total. The only "$5" in
the tree is a fixture string in BUILD-SPEC about a client's negotiating
position.

## Ceilings are PER PROVIDER as well as per client (2026-09-25)

A client-wide ceiling cannot express "CheapVerifier's 100,000 is the actual
account balance and running it dry halts a batch mid-flight, while
Deliverable's 500,000 is a policy number". Those are different kinds of
number and they needed different knobs, so `budget.providers.<name>` now
declares `total`, `per_day` and `per_run` for one provider and `check()`
enforces them BEFORE the call.

**The client ceilings still bind first, and that is deliberate.** A provider
ceiling of 100,000 under a client `total` of 50,000 is decoration: the run
halts at the client number with a refusal that has nothing to do with the
provider. So every refusal now says which SCOPE it came from in as many
words - `PROVIDER CEILING` or `CLIENT CEILING` - because the failure mode
this module exists to prevent is somebody reading "budget exceeded" and
raising the wrong number.

## `per_run` is enforced HERE now, by reservation

`per_run` sat in `SCOPES`, was returned by `caps()`, and had no consumer on
any spend path; `tests/test_the_second_client_runs_on_the_same_engine.py`
pinned that as a known LEAK and `scripts/stage_s5_verify.py` worked around it
by holding itself to the number. On 2026-09-25 a chunk stopped at 2,044
credits against a declared ceiling of 2,000 - twenty-two addresses past it -
while every test passed, because the tests ran at `--workers 1` and
production runs at 8.

**A cap tested after the answer can only ever report an overshoot.** So a
caller RESERVES before it asks (`reserve` / `holding`), the reservation
counts against every ceiling from the moment it is taken, and K parallel
workers therefore cannot each see room only one of them can have. That
property now lives in this module rather than in each runner, because a
control re-implemented per caller is a control that is missing from the
caller that forgot.

## A reservation is HELD, not SPENT

CheapVerifier's `/file/upload` answers `creditsReserved`: credits the vendor
has put aside for a job it has not run. Per the vendor's own spec that is a
hold, not a charge, so `reserve_upload` writes NO ledger row - and still
refuses the upload if the hold would cross a ceiling. Ledgering a hold as
spend would make the ledger disagree with the invoice; not counting it at all
would let a 40,000-credit reservation sail past a 10,000-credit balance.

## What this does NOT do

**It does not choose a budget.** A ceiling nobody agreed to is not a safety
control, it is a number that will be raised the first time it is
inconvenient, and inventing one would make an operator's decision look like
an engineering default. `caps()` returns whatever the client config states
and `None` where it states nothing, and `None` means unlimited and SAYS so.

It also does not record observed cost. Expected and observed are different
claims - that is `costs.py`'s whole premise - and this ledger holds the
expected side only, at the moment of the call, which is the only moment the
system reliably knows anything.

## Fail-safe

An unreadable ledger REFUSES rather than allowing. A spend control that opens
when its own state is missing is a spend control that fails exactly when
something is already wrong.
"""
import argparse
import contextlib
import datetime
import json
import os
import threading
import uuid

from . import store

# Where a client's declared ceilings live, if it declares any.
CONFIG_KEY = "budget"

# The per-provider block inside it: `budget.providers.<provider>.<scope>`.
PROVIDERS_KEY = "providers"

# The ceilings this module understands. Each is credits, per the scope named,
# and each is None unless the client config says otherwise.
SCOPES = ("per_run", "per_day", "per_provider_per_day", "total")

# The scopes a single provider may declare for itself. `per_provider_per_day`
# is absent on purpose: inside a provider block "per_day" already means "this
# provider, per day", and two spellings of one ceiling is how they drift.
PROVIDER_SCOPES = ("per_run", "per_day", "total")

# A MISSING CEILING MUST NEVER PARSE AS AN UNLIMITED ONE.
#
# This is the whole hazard in the 2026-09-25 swap. The client `total` of
# 50,000 was the only lifetime cap the estate had; per-provider totals
# replace it. Between those two facts there is a state - client `total`
# removed, provider totals not yet declared - in which every ceiling reads
# `None`, `None` reads as unlimited, and nothing at all bounds the account.
# It is the same class as an empty expectation matching everything and an
# empty ledger reading as an unspent budget.
#
# So `None` from an ABSENT key is now refused on a paid call, and a provider
# that is deliberately uncapped says so IN THE CONFIG with this word. An
# operator's decision to leave ContactOut uncapped is a declaration; a key
# somebody forgot is not, and the two must not look alike.
UNLIMITED = "unlimited"

# WHERE A PROVIDER `total` IS AN ACCOUNT BALANCE RATHER THAN A POLICY NUMBER,
# AND HOW CLOSE TO EMPTY IS AN EMERGENCY.
#
# CheapVerifier's 100,000 is the money actually in the account. Reaching it
# does not mean "the ceiling worked", it means a batch stops in the middle
# with rows bought and rows not, and the operator finds out from the halt.
# 10,000 remaining is roughly one large batch of warning - enough time to top
# up before the next one, which is the whole point of alerting on a balance
# rather than on a failure.
CRITICAL_REMAINING = {"cheapverifier": 10_000}

# THIS LEDGER DOES NOT SPEAK ONE UNIT, AND PRETENDING IT DOES IS A LIE AN
# OPERATOR READS.
#
# `researchpack/actors.py` prices every Apify actor run in INTEGER CENTS -
# its own comment says "in the same integer cents the rest of the spend
# ledger speaks", which was never true of the rest of it - and writes that
# figure into these rows. Every other provider writes CREDITS. So Apify's
# 447 all-time is 447 cents and Deliverable's 8,262 is 8,262 credits, and a
# ceiling is in whatever unit its provider's rows are in.
#
# NOTHING HERE CONVERTS. Picking a rate is an operator's decision, not a
# default; what this does is refuse to print one number as though the two
# were the same thing. The client-wide totals DO sum both, which is why the
# client `per_day` is a tripwire rather than a budget - see
# docs/MERGE-REQUEST-2026-09-25-PER-PROVIDER-CEILINGS.md.
DEFAULT_UNIT = "credits"
LEDGER_UNITS = {"apify": "cents", "anthropic": "microusd",
                "groq": "microusd", "openrouter": "microusd"}

#: MICRO-DOLLARS, AND THE REASON IS ARITHMETIC RATHER THAN TASTE.
#:
#: `record` stores `expected_cost` as an INT, and every ceiling, `spent()` and
#: all 17,937 existing rows depend on that. Sonnet costs $0.00256 per lead.
#: Measured:
#:
#:     one lead     $0.00256  -> int() -> 0
#:     50 leads     $0.128    -> int() -> 0
#:     1,000 leads  $2.56     -> int() -> 2
#:
#: So a dollar-denominated provider writing its native amount into that column
#: ledgers an entire nightly cohort as ZERO: spend fully visible in the file
#: and invisible to every control, which is the `per_run` defect in new
#: clothes. Micro-dollars keep the column integral and lose no precision.
#:
#: Making `expected_cost` a float instead would change behaviour for every
#: provider in order to fix one.
MICRO = 1_000_000


def to_micro_usd(usd):
    """Dollars -> integer micro-dollars. $0.00256 -> 2560."""
    return int(round(float(usd or 0) * MICRO))


#: USD per one unit of a provider's native currency. `None` means NOBODY HAS
#: PRICED IT, and that is a real answer: `usd_estimate` then comes back None
#: with `rate_source: "unknown"` rather than carrying an invented conversion.
#: A report that sums a made-up rate is the defect this table exists to end.
USD_PER_UNIT = {
    "microusd": 1.0 / MICRO,     # exact, by construction
    "cents": 0.01,               # exact, by definition
    "credits": None,             # differs per provider and per plan
}


def usd_estimate(expected_cost, unit, rate=None):
    """`(usd_estimate, rate, rate_source)`. None where nobody has priced it."""
    if rate is not None:
        return float(expected_cost or 0) * float(rate), float(rate), "caller"
    known = USD_PER_UNIT.get(unit)
    if known is None:
        return None, None, "unknown"
    return float(expected_cost or 0) * known, known, "unit_definition"


def unit_for(provider):
    """What this provider's rows are denominated in, BY CONVENTION.

    A display lookup, not a claim stamped on anything. It is how a row
    written before units existed gets read; a row that carries its own
    `unit` is believed over this table, always.
    """
    return LEDGER_UNITS.get(provider, DEFAULT_UNIT)


def row_unit(row):
    """One row's unit: what it says, else its provider's convention.

    Most of the 17,937 rows on disk predate `unit` entirely. A missing unit
    is read as the convention rather than as an error, because refusing to
    read history would turn every ceiling off.
    """
    if isinstance(row, dict) and row.get("unit"):
        return row["unit"]
    return unit_for((row or {}).get("provider"))


class BudgetExceeded(RuntimeError):
    """A durable ceiling would be crossed. Refused, never trimmed."""


class MissingCeiling(BudgetExceeded):
    """There is no lifetime ceiling covering this call, so it is refused.

    A SUBCLASS OF `BudgetExceeded` ON PURPOSE. Every existing caller already
    catches that and treats it as "do not make this call" - `enrich.spend`
    and the verification waterfall both do - so an estate that loses its
    lifetime cap stops spending instead of discovering a new exception type
    at the top of a stack trace mid-batch. Fails closed, everywhere, with no
    new wiring.
    """


class LedgerUnreadable(RuntimeError):
    """The spend state could not be read, so no spend may be authorised."""


def path():
    """Beside the queue, so spend and the records it bought move together."""
    return os.path.abspath(os.environ.get("SPEND_LEDGER")
                           or os.path.join(os.path.dirname(store.queue_path()),
                                           "spend-ledger.jsonl"))


def alerts_path():
    """Derived from `path()`, NOT from its own environment override.

    `tests/test_invariants.py` requires every state file to move together
    when `store.use_directory` points the tree somewhere else. Deriving this
    from the ledger's directory means it moves with the ledger by
    construction, and there is no second override to forget.
    """
    return os.path.join(os.path.dirname(path()), "spend-alerts.json")


def load():
    try:
        return store.read_jsonl(path())
    except FileNotFoundError:
        return []
    except Exception as e:                       # a corrupt ledger is not empty
        raise LedgerUnreadable(
            f"{path()} could not be read ({type(e).__name__}). Refusing to "
            f"authorise spend against unknown state.") from None


def today(now=None):
    return (now or datetime.datetime.now(datetime.timezone.utc)).date().isoformat()


# ---------------------------------------------------------------- the run

# WHAT "PER RUN" MEANS, SPELLED OUT, BECAUSE THE CEILING IS ONLY AS GOOD AS
# THE SCOPE IT COUNTS OVER.
#
# A run is one invocation. Ledger rows carry `run_id` so the count survives
# across the processes of a single orchestrated pass (set `RUN_ID` in the
# environment and every child agrees), and defaults to a per-process id so a
# plain `python -m ...` still has an identity rather than counting nothing.
#
# A LONG-LIVED PROCESS MUST CALL `new_run()` PER PASS. Nothing in this tree
# does today - the three `*_watch_loop.py` daemons never reach a spend path,
# checked 2026-09-25 - but a daemon that starts spending and never rolls its
# run id would accumulate against `per_run` until it halted, which would look
# like the ceiling misbehaving rather than like a missing call.
_RUN = None
_LOCK = threading.RLock()


def current_run():
    """This invocation's identity, for `per_run`."""
    global _RUN
    named = os.environ.get("RUN_ID")
    if named:
        return named
    with _LOCK:
        if _RUN is None:
            _RUN = "run-" + uuid.uuid4().hex[:12]
        return _RUN


def new_run(name=None):
    """Start a fresh run. A long-lived process calls this once per pass."""
    global _RUN
    with _LOCK:
        _RUN = name or ("run-" + uuid.uuid4().hex[:12])
        return _RUN


def record(client, provider, call, expected_cost, run_id=None, at=None,
           rows=None, unit=None, **extra):
    """Append one expected charge. Called at the moment of the call.

    Returns the row, so a caller can log it. Appending rather than updating a
    running total on purpose: a total is a derived number and a derived number
    that disagrees with its inputs is the thing nobody can debug.

    `run_id` DEFAULTS TO THE CURRENT RUN rather than to None. It was None on
    every row written before 2026-09-25, which is precisely why `per_run`
    could not be enforced from the ledger: the rows did not say which run
    bought them.

    `**extra` merges additional fields into the row - actual token usage from
    a model response, for example.  A model call that records only an estimate
    when the provider returned actual counts is recording the wrong thing.
    """
    row = {"at": at or store.now(), "day": today(),
           "client": client, "provider": provider, "call": call,
           "expected_cost": int(expected_cost or 0),
           "run_id": run_id or current_run()}
    # THE UNIT, WHEN THE WRITER KNOWS IT - AND ABSENT WHEN IT DOES NOT.
    #
    # This column is unit-ambiguous and has already produced a wrong number:
    # `researchpack/actors.py` writes Apify costs in integer CENTS where
    # Deliverable and Reoon write CREDITS, and a report summed 18,809 /
    # 14,365 / 31,191 across both as though they were one thing. TASK-308
    # adds DOLLARS as a third.
    #
    # NOT DEFAULTED, DELIBERATELY. Stamping `credits` on every row that does
    # not say otherwise would retrofit a claim onto providers whose unit is
    # the operator's call and a separate task - TASK-308 says so in as many
    # words - and a guess written down is indistinguishable from a
    # measurement a week later. So a writer that knows passes it, a writer
    # that does not leaves the row exactly as it has always been, and
    # `row_unit` reads the absence as this provider's convention.
    if unit:
        row["unit"] = unit
    # `usd_estimate` IS WHAT REPORTS SUM. Operator decision, 2026-09-25:
    # every row carries provider, native unit and usd_estimate, and reports
    # sum only the last. It is written from the unit the writer declared, so
    # a row with no unit gets no estimate rather than one derived from a
    # convention nobody stamped - see the comment above on not defaulting.
    #
    # `None` IS A REAL VALUE HERE. Credits are not dollars and the rate
    # differs per provider and per plan, so an unpriced unit yields None with
    # `rate_source: "unknown"`. A report that sums an invented conversion is
    # exactly the defect the unit column was added to end, one column left.
    if unit:
        estimate, rate_used, source = usd_estimate(row["expected_cost"], unit)
        row["usd_estimate"] = estimate
        row["rate"] = rate_used
        row["rate_source"] = source
    row.update(extra)
    # OUTSIDE THE BARRIER UNTIL NOW, AND IT COST REAL CLIENT STATE.
    #
    # This builds its own append rather than going through `store.write_jsonl`,
    # so it never asked `refuse_production_write` - the same way `mx`, `poller`
    # and `replywatch` had to be made to ask for themselves. `path()` falls
    # back to `dirname(store.queue_path())`, so any test that reaches a paid
    # call without isolating the store writes the operator's real ledger.
    #
    # Measured the hour this guard was added: wiring verification into the
    # ledger made exactly that happen, and 19 rows of fabricated spend -
    # deliverable, reoon, contactout - landed in the client's real
    # `work/spend-ledger.jsonl`. Fabricated spend is worse here than in most
    # files, because `check()` reads this to refuse the NEXT call: invented
    # credits exhaust a real ceiling.
    #
    # Before `os.makedirs`, so the refusal lands before any filesystem change.
    store.refuse_production_write(path())
    # A first run on a fresh deployment has no directory yet, and the spend
    # control refusing to record because of that would be the worst possible
    # failure: the call still happens, and nothing counts it.
    os.makedirs(os.path.dirname(path()), exist_ok=True)
    # ONE WRITER AT A TIME, AND IT IS NOT A PRECAUTION.
    #
    # This was a bare append, which is atomic only by luck. On 2026-09-24 S5
    # was wired into this ledger and ran eight workers against it; 1,957 rows
    # in, one write TORE - the file kept a complete row and then an orphaned
    # eleven-byte tail, `id": null}`, with the head of its own row gone.
    #
    # The consequence is the whole reason this needs a lock rather than a
    # tolerant reader. `load()` refuses an unreadable ledger instead of
    # reading it as empty, and `check()` reads it before every paid call - so
    # ONE torn byte sequence stopped every verification for that client, and
    # the run that caused it bought nothing further. That refusal is correct
    # and stays: a spend control that opens when its own state is damaged is
    # the failure this module was written against. What must not happen is
    # the damage, and the damage is a write that two threads can interleave.
    #
    # `store.lock` rather than a `threading.Lock`, because the writers are in
    # different PROCESSES as often as in different threads - the enrich loops,
    # the monitors and this stage all bill the same client - and an in-process
    # lock would have looked like a fix while leaving the cross-process race
    # exactly where it was. It is an exclusive-create advisory lock held for
    # one append, microseconds, and it reclaims a lock left by a dead process.
    #
    # AND IT WAS SILENTLY DELETED ONCE, WHICH IS WHY THIS PARAGRAPH EXISTS.
    # The per-provider-ceilings change rewrote this whole file from a copy
    # read BEFORE the rebase that brought the lock in. A whole-file write of
    # a stale read does not conflict - it just reverts - so the money path
    # lost its cross-process lock and no test in the lane noticed, because
    # the lane's own tests all isolate the store and never race two writers
    # on one append. `tests/test_two_writers_cannot_tear_the_spend_ledger.py`
    # is what caught it: `test_a_held_lock_blocks_the_append_rather_than_
    # racing_it` went red with "QueueLocked not raised", and the concurrent
    # writer test lost seven of 480 rows. The two-writer test was already
    # there and already correct; nothing about it needed changing.
    #
    # `_LOCK` in this module is a DIFFERENT lock and does not replace this
    # one. That one serialises reservations inside one process so K workers
    # cannot each see the same room; this one serialises the APPEND across
    # processes so the bytes of two rows cannot interleave. Neither covers
    # the other's case.
    with store.lock(for_path=path()):
        with open(path(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def spent(client=None, day=None, provider=None, rows=None, run_id=None):
    """Expected credits already committed, filtered as asked.

    LEDGERED credits only. Calls in flight are `reserved()`; the number both
    ceilings are checked against is `committed()`.

    `client=None` counts every tenant together, which is almost never what a
    caller wants - `actionledger.count_on` had the same default and it was a
    real bug there. Named here rather than fixed, because a spend REPORT
    across all clients is legitimate and a spend CHECK across all clients is
    not; `check()` below requires a client.
    """
    rows = load() if rows is None else rows
    total = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if client is not None and row.get("client") != client:
            continue
        if day is not None and row.get("day") != day:
            continue
        if provider is not None and row.get("provider") != provider:
            continue
        if run_id is not None and row.get("run_id") != run_id:
            continue
        total += int(row.get("expected_cost") or 0)
    return total


# ------------------------------------------------------- reservations

class Hold:
    """Credits claimed by a call that has not answered yet.

    Held, not spent. It counts against every ceiling from the moment it is
    taken and writes no ledger row until `settle`. That ordering is the whole
    mechanism: a worker that reserves first cannot be one of eight workers
    that each saw the same room.
    """

    __slots__ = ("token", "client", "provider", "call", "run_id", "day",
                 "cost", "kind", "resolved", "unit")

    def __init__(self, client, provider, call, run_id, day, cost, kind,
                 unit=None):
        self.token = uuid.uuid4().hex
        self.client, self.provider, self.call = client, provider, call
        self.run_id, self.day, self.cost, self.kind = run_id, day, cost, kind
        # Carried from the reservation to the ledger row so a held call
        # cannot settle in a different unit from the one it was checked in.
        self.unit = unit
        self.resolved = False

    def __repr__(self):                                       # pragma: no cover
        return (f"<Hold {self.kind} {self.cost} {self.provider} "
                f"{'resolved' if self.resolved else 'outstanding'}>")


# token -> Hold. Guarded by `_LOCK`, which is also the lock `reserve` takes
# across check-then-register: two workers must not both pass the check.
_HOLDS = {}


def reserved(client=None, day=None, provider=None, run_id=None):
    """Credits outstanding on calls that have not answered yet."""
    with _LOCK:
        total = 0
        for hold in _HOLDS.values():
            if hold.resolved:
                continue
            if client is not None and hold.client != client:
                continue
            if day is not None and hold.day != day:
                continue
            if provider is not None and hold.provider != provider:
                continue
            if run_id is not None and hold.run_id != run_id:
                continue
            total += hold.cost
        return total


def outstanding():
    """Every unresolved hold. For a progress line or a post-mortem."""
    with _LOCK:
        return [h for h in _HOLDS.values() if not h.resolved]


def committed(client, day=None, provider=None, run_id=None, rows=None):
    """Ledgered spend PLUS credits held by calls still in flight.

    THE NUMBER EVERY CEILING IS CHECKED AGAINST. Checking against `spent()`
    alone is what let eight workers cross a 2,000-credit ceiling by 22
    addresses: each of them read a ledger that did not yet know about the
    other seven.
    """
    return (spent(client, day=day, provider=provider, rows=rows,
                  run_id=run_id)
            + reserved(client, day=day, provider=provider, run_id=run_id))


def caps(config):
    """The client's declared ceilings, and `None` where it declares none.

    `None` is UNLIMITED and is reported as such rather than defaulted to a
    number somebody would have to discover by hitting it.
    """
    declared = (config or {}).get(CONFIG_KEY) or {}
    return {scope: _limit(declared.get(scope)) for scope in SCOPES}


def declares_client(config, scope="total"):
    """Did the client block DECIDE this ceiling, or simply not carry it?"""
    return scope in ((config or {}).get(CONFIG_KEY) or {})


def _limit(value):
    """A declared ceiling as a number, or `None` for no ceiling.

    The explicit `unlimited` and an absent key both come back `None` here,
    because neither bounds anything. Which of the two it was is a different
    question, and `declares` is the one that answers it.
    """
    if value is None or value == UNLIMITED:
        return None
    return value


def declares(config, provider, scope="total"):
    """Did anybody DECIDE this ceiling, as opposed to leaving it out?

    The distinction `_limit` throws away and the swap depends on. An operator
    writing `total: unlimited` has made a decision; a missing key is a
    decision nobody made, and `check` refuses on the second.
    """
    declared = (config or {}).get(CONFIG_KEY) or {}
    block = (declared.get(PROVIDERS_KEY) or {}).get(provider) or {}
    return scope in block


def provider_caps(config, provider):
    """One provider's own ceilings, and `None` where it declares none.

    Independent of `caps()`: a provider block says what THIS provider may
    spend, and the client block says what the tenant may spend across all of
    them. Both are enforced and neither substitutes for the other - see
    `check`, and the ordering note there.
    """
    declared = (config or {}).get(CONFIG_KEY) or {}
    block = (declared.get(PROVIDERS_KEY) or {}).get(provider) or {}
    return {scope: _limit(block.get(scope)) for scope in PROVIDER_SCOPES}


def provider_names(config):
    """Every provider the config declares a ceiling for."""
    declared = (config or {}).get(CONFIG_KEY) or {}
    return sorted((declared.get(PROVIDERS_KEY) or {}).keys())


def check(client, config, cost, provider=None, rows=None, day=None,
          run_id=None):
    """May this client spend `cost` more? Raises `BudgetExceeded` if not.

    Every ceiling is checked and the FIRST one crossed is the one named, so
    the refusal says which limit applied rather than that some limit did.

    THE ORDER IS PROVIDER-FIRST, AND THE MESSAGES SAY WHICH SCOPE THEY CAME
    FROM. When a provider ceiling and a client ceiling would both refuse, the
    provider one is the more specific fact and is the one reported. When only
    the client one refuses - which is what happens whenever the client
    `total` is smaller than the provider ceilings beneath it - the message
    says `CLIENT CEILING` and names the provider it was NOT about, because
    "budget exceeded" with no scope is how somebody raises the wrong number.

    Reservations count. `committed()` is ledger + in-flight, so a worker that
    called `reserve` is visible to the next worker's check before its call
    has answered.
    """
    if not client:
        raise BudgetExceeded(
            "a spend check needs a client; an unscoped budget is one client "
            "paying for another's run")
    rows = load() if rows is None else rows
    day = day or today()
    run_id = run_id or current_run()
    cost = int(cost or 0)

    if provider:
        declared = provider_caps(config, provider)
        for scope, already, where in (
                ("per_run",
                 committed(client, provider=provider, run_id=run_id, rows=rows),
                 f"in this run ({run_id})"),
                ("per_day",
                 committed(client, provider=provider, day=day, rows=rows),
                 f"today ({day})"),
                ("total",
                 committed(client, provider=provider, rows=rows),
                 "all time"),
        ):
            limit = declared.get(scope)
            if limit is not None and already + cost > limit:
                raise BudgetExceeded(
                    f"PROVIDER CEILING: {provider} {scope} is {limit} for "
                    f"{client}; {already} credit(s) are already committed to "
                    f"{provider} {where} and this call expects {cost}. "
                    f"Refused before the provider was called. Raise "
                    f"budget.providers.{provider}.{scope} if this is wrong.")

    ceilings = caps(config)
    for scope, already, where in (
            ("per_run", committed(client, run_id=run_id, rows=rows),
             f"in this run ({run_id})"),
            ("per_day", committed(client, day=day, rows=rows),
             f"today ({day})"),
            ("total", committed(client, rows=rows), "in total"),
    ):
        limit = ceilings.get(scope)
        if limit is not None and already + cost > limit:
            raise BudgetExceeded(
                f"CLIENT CEILING: the client-wide {scope} for {client} is "
                f"{limit} - this is NOT a provider ceiling, and the call was "
                f"to {provider or 'an unnamed provider'}; {already} credit(s) "
                f"are already committed {where} across ALL providers and this "
                f"call expects {cost}. Raise budget.{scope} if this is wrong, "
                f"not budget.providers.{provider or '<provider>'}.{scope}.")

    limit = ceilings.get("per_provider_per_day")
    if limit is not None and provider:
        already = committed(client, day=day, provider=provider, rows=rows)
        if already + cost > limit:
            raise BudgetExceeded(
                f"CLIENT CEILING: budget.per_provider_per_day is {limit} for "
                f"{client} - the client-wide default that applies to EVERY "
                f"provider, not {provider}'s own ceiling; {already} credit(s) "
                f"are already committed to {provider} today ({day}) and this "
                f"call expects {cost}.")

    # LAST, AND ONLY FOR A CALL THAT COSTS SOMETHING: IS ANYTHING BOUNDING
    # THE LIFETIME OF THIS SPEND AT ALL?
    #
    # Last so that a real crossing is still named by its own scope - a
    # refusal reading "no lifetime ceiling" when the true answer is "per_day
    # is exhausted" would send somebody to edit the wrong key.
    #
    # The swap that makes this necessary: the client `total` was the estate's
    # only lifetime cap and per-provider `total` replaces it. Land one
    # without the other and every ceiling reads `None`, `None` reads as
    # unlimited, and the account is bounded by nothing. A per_day tripwire
    # does not catch that - a runaway inside one day is exactly the case it
    # cannot see.
    #
    # `unlimited` written in the config satisfies this and a missing key does
    # not, because a decision and an omission must not look alike.
    #
    # SCOPED TO A CLIENT THAT DECLARES A BUDGET AT ALL, AND THAT BOUNDARY IS
    # DELIBERATE. A `budget` block is a statement that this client's spend is
    # governed; once it is, the lifetime ceiling has to be there. A client
    # file with NO `budget` block is the older, separate condition "this
    # client declared no ceilings", which `caps()` already reports as
    # UNLIMITED in as many words and which this lane did not widen and does
    # not close - `config/clients/demo.yaml` and the ContactOut example are
    # both in that state today. Named in
    # docs/MERGE-REQUEST-2026-09-25-PER-PROVIDER-CEILINGS.md rather than
    # quietly turned into a refusal here, because refusing every client that
    # has never declared a budget is a policy decision and not a side effect
    # of adding per-provider ceilings.
    governed = bool((config or {}).get(CONFIG_KEY))
    if cost > 0 and governed and not declares_client(config, "total"):
        if not provider:
            raise MissingCeiling(
                f"no lifetime ceiling covers this call for {client}: the "
                f"client block declares no budget.total and the call names "
                f"no provider, so nothing bounds it. Declare budget.total, "
                f"or name the provider so its budget.providers.<name>.total "
                f"applies. An absent ceiling is not an unlimited one.")
        if not declares(config, provider, "total"):
            raise MissingCeiling(
                f"no lifetime ceiling covers {provider} for {client}: the "
                f"client block declares no budget.total and there is no "
                f"budget.providers.{provider}.total. Declare one, or write "
                f"`total: {UNLIMITED}` there if {provider} is deliberately "
                f"uncapped. An absent ceiling is not an unlimited one - it "
                f"is a ceiling somebody forgot, and this refuses rather than "
                f"spending against it.")
    return True


def reserve(client, config, cost, provider=None, call=None, run_id=None,
            day=None, kind="call", rows=None, unit=None):
    """Claim `cost` credits BEFORE the call, or refuse. Returns a `Hold`.

    The check and the claim happen under one lock. That is the entire
    difference between a ceiling that holds at K=8 and one that holds at K=1:
    without it, eight workers each read the ledger, each see room for one
    more address, and eight addresses are bought against room for one.

    The hold is NOT a ledger row. Call `settle` when the provider answers -
    with what it actually cost, if that is known - or `release` if it never
    did.
    """
    cost = int(cost or 0)
    run_id = run_id or current_run()
    day = day or today()
    with _LOCK:
        check(client, config, cost, provider=provider, rows=rows, day=day,
              run_id=run_id)
        hold = Hold(client, provider, call, run_id, day, cost, kind, unit)
        _HOLDS[hold.token] = hold
        return hold


def settle(hold, actual_cost=None, call=None):
    """The call answered. Write what it cost and drop the hold.

    The ledger row is appended BEFORE the hold is dropped, so the committed
    total never dips below reality for the moment in between - which is a
    moment another worker's `check` can land in.
    """
    with _LOCK:
        if hold.resolved:
            raise RuntimeError("this hold was already settled or released")
        cost = hold.cost if actual_cost is None else int(actual_cost or 0)
        row = record(hold.client, hold.provider, call or hold.call, cost,
                     run_id=hold.run_id, unit=hold.unit)
        hold.resolved = True
        _HOLDS.pop(hold.token, None)
        return row


def release(hold):
    """The call never happened, or the vendor released the reservation.

    No ledger row: nothing was bought. A hold that is neither settled nor
    released is a credit this process will keep refusing to spend, which
    fails closed - the safe direction - but is still a leak, so every caller
    should use `holding()` unless it has a reason not to.
    """
    with _LOCK:
        if hold.resolved:
            return None
        hold.resolved = True
        _HOLDS.pop(hold.token, None)
        return None


@contextlib.contextmanager
def holding(client, config, cost, provider=None, call=None, run_id=None,
            day=None, kind="call", rows=None, unit=None):
    """Reserve, do the call, settle. The shape every spend path should use.

    On the way out it settles at the reserved cost unless the body already
    settled at the real one; on an exception it releases, because a call that
    raised bought nothing this side of the wire can prove.
    """
    hold = reserve(client, config, cost, provider=provider, call=call,
                   run_id=run_id, day=day, kind=kind, rows=rows, unit=unit)
    try:
        yield hold
    except BaseException:
        release(hold)
        raise
    if not hold.resolved:
        settle(hold)


def reserve_upload(client, config, provider, credits_reserved, call=None,
                   run_id=None, day=None, rows=None):
    """THE BULK SEAM. `/file/upload` answers `creditsReserved`: check it FIRST.

    The vendor's spec calls this a hold, not a charge - the credits are put
    aside for a job that has not run. So:

      * it writes NO ledger row (a hold is not spend, and ledgering it would
        make our expected total disagree with the invoice), and
      * it is still REFUSED if it would cross a ceiling, because a
        40,000-credit reservation against a 10,000-credit balance is a batch
        that halts in the middle whether or not we call it spend.

    Call this after `/file/upload` reports the reservation and BEFORE the
    upload is committed. On refusal, do not commit; cancel the reservation
    with the vendor. On completion, `settle(hold, actual)` with what the job
    really cost, which is the number that reaches the ledger.
    """
    return reserve(client, config, credits_reserved, provider=provider,
                   call=call or "file/upload", run_id=run_id, day=day,
                   kind="reservation", rows=rows)


# ------------------------------------------------------------- balances

def _remaining(limit, used):
    return None if limit is None else limit - used


def balances(client, config, rows=None, day=None, run_id=None):
    """Per provider: what is declared, what is gone, what is left.

    `remaining` against `total` is the number that matters for CheapVerifier,
    because there the `total` IS the account balance. For a provider whose
    `total` is a policy number it is still the right number to show; it just
    is not money in an account.
    """
    rows = load() if rows is None else rows
    day = day or today()
    run_id = run_id or current_run()
    names = set(provider_names(config))
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("client") != client:
            continue
        if row.get("provider"):
            names.add(row["provider"])
    for hold in outstanding():
        if hold.client == client and hold.provider:
            names.add(hold.provider)

    out = {}
    for provider in sorted(names):
        declared = provider_caps(config, provider)
        all_time = spent(client, provider=provider, rows=rows)
        held = reserved(client, provider=provider)
        out[provider] = {
            "provider": provider,
            "ceilings": declared,
            "spent_all_time": all_time,
            "spent_today": spent(client, provider=provider, day=day, rows=rows),
            "spent_this_run": spent(client, provider=provider, run_id=run_id,
                                    rows=rows),
            "held": held,
            "remaining": _remaining(declared.get("total"), all_time + held),
            "remaining_today": _remaining(
                declared.get("per_day"),
                committed(client, provider=provider, day=day, rows=rows)),
            "remaining_this_run": _remaining(
                declared.get("per_run"),
                committed(client, provider=provider, run_id=run_id, rows=rows)),
            "critical_at": CRITICAL_REMAINING.get(provider),
            "balance_is_money": provider in CRITICAL_REMAINING,
            "unit": unit_for(provider),
            # WHAT THE ROWS THEMSELVES SAY, which is not always one thing.
            # A provider whose rows carry two units has a ceiling that means
            # nothing - you cannot subtract cents from credits - and that
            # has to be visible rather than averaged into a total.
            "units_seen": sorted({
                row_unit(r) for r in rows
                if isinstance(r, dict) and r.get("client") == client
                and r.get("provider") == provider}),
        }
    return out


def client_balance(client, config, rows=None, day=None, run_id=None):
    """The client-wide row. Reported beside the providers on purpose.

    A per-provider block that showed only providers would hide the ceiling
    that actually binds: with a client `total` of 50,000 under provider
    ceilings of 100,000 and 500,000, the client line is the one that stops
    the run.
    """
    rows = load() if rows is None else rows
    day = day or today()
    run_id = run_id or current_run()
    ceilings = caps(config)
    return {
        "client": client,
        "ceilings": ceilings,
        "spent_all_time": spent(client, rows=rows),
        "spent_today": spent(client, day=day, rows=rows),
        "spent_this_run": spent(client, run_id=run_id, rows=rows),
        "held": reserved(client),
        "remaining": _remaining(ceilings.get("total"), committed(client, rows=rows)),
        "remaining_today": _remaining(ceilings.get("per_day"),
                                      committed(client, day=day, rows=rows)),
        "remaining_this_run": _remaining(
            ceilings.get("per_run"),
            committed(client, run_id=run_id, rows=rows)),
    }


def _cell(remaining, limit):
    if limit is None:
        return "unlimited"
    return f"{remaining} of {limit}"


def progress_block(client, config, rows=None, day=None, run_id=None):
    """The per-provider balance that belongs in every PROGRESS block.

    A progress line that reports rows done and not credits left tells you how
    far the batch got and nothing about whether it can finish.
    """
    rows = load() if rows is None else rows
    lines = [f"PROVIDER BALANCE  client={client}  run={run_id or current_run()}"
             f"  (expected spend, each row in ITS OWN unit)"]
    for provider, b in balances(client, config, rows=rows, day=day,
                                run_id=run_id).items():
        marker = "  <-- ACCOUNT BALANCE" if b["balance_is_money"] else ""
        if len(b["units_seen"]) > 1:
            marker = ("  <-- ROWS IN " + " AND ".join(b["units_seen"]).upper()
                      + "; THIS CEILING CANNOT MEAN ANYTHING") + marker
        lines.append(
            f"  {provider:<16} left {_cell(b['remaining'], b['ceilings']['total'])}"
            f"   today {_cell(b['remaining_today'], b['ceilings']['per_day'])}"
            f"   run {_cell(b['remaining_this_run'], b['ceilings']['per_run'])}"
            f"   [{b['unit']}]{marker}")
        if b["held"]:
            lines.append(f"  {'':<16} ({b['held']} credit(s) held by calls in "
                         f"flight, not yet ledgered)")
    c = client_balance(client, config, rows=rows, day=day, run_id=run_id)
    mixed = len({b["unit"] for b in balances(client, config, rows=rows,
                                             day=day, run_id=run_id).values()})
    lines.append(
        f"  {'CLIENT-WIDE':<16} left {_cell(c['remaining'], c['ceilings']['total'])}"
        f"   today {_cell(c['remaining_today'], c['ceilings']['per_day'])}"
        f"   run {_cell(c['remaining_this_run'], c['ceilings']['per_run'])}"
        f"   [{'MIXED UNITS - a tripwire, not an amount' if mixed > 1 else DEFAULT_UNIT}]")
    for alert in alerts(client, config, rows=rows):
        lines.append("  " + alert["text"])
    return "\n".join(lines)


# --------------------------------------------------------------- alerts

def alerts(client, config, rows=None):
    """Every CRITICAL that is TRUE right now. Says nothing about firing.

    Separated from `fire_alerts` so the condition can be asserted without a
    state file in the way, and so a progress block can restate a standing
    CRITICAL every time without that counting as a new alert.
    """
    out = []
    for provider, b in balances(client, config, rows=rows).items():
        threshold, remaining = b["critical_at"], b["remaining"]
        if threshold is None or remaining is None:
            continue
        if remaining > threshold:
            continue
        out.append({
            "level": "CRITICAL",
            "client": client,
            "provider": provider,
            "remaining": remaining,
            "threshold": threshold,
            "key": f"{client}:{provider}:remaining_at_or_below_{threshold}",
            "text": (f"CRITICAL: {provider} has {remaining} credit(s) left of "
                     f"{b['ceilings']['total']} for {client}, at or below the "
                     f"{threshold} alert threshold. Top up before the next "
                     f"batch - at this balance a batch halts part-finished, "
                     f"with rows bought and rows not."),
        })
    return out


def _alert_state():
    try:
        with open(alerts_path(), encoding="utf-8") as fh:
            state = json.load(fh)
        return state if isinstance(state, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:                                 # noqa: BLE001
        # A damaged marker file must not silence the alert. Losing the
        # "already fired" memory costs a repeated CRITICAL; trusting it
        # costs the CRITICAL entirely, and one of those two is recoverable.
        return {}


def _write_alert_state(state):
    store.refuse_production_write(alerts_path())
    os.makedirs(os.path.dirname(alerts_path()), exist_ok=True)
    tmp = alerts_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=1, sort_keys=True)
    os.replace(tmp, alerts_path())


def fire_alerts(client, config, rows=None):
    """The alerts that have NOT been announced yet. Fires once, re-arms once.

    ONCE, NOT EVERY CALL. `check()` runs per call, and a CRITICAL repeated
    per call is a CRITICAL nobody reads - the alert that cried wolf is the
    same defect as no alert. The marker is durable, so it survives the
    process that first saw the balance.

    RE-ARMS ON A TOP-UP. When the balance climbs back above the threshold the
    marker is cleared, so the NEXT time it falls the operator is told again.
    A one-shot that never re-arms is a one-shot that protects exactly one
    top-up cycle.
    """
    live = alerts(client, config, rows=rows)
    state = _alert_state()
    fired = state.get("fired") or {}
    active = {a["key"]: a for a in live}

    fresh = [a for key, a in active.items() if key not in fired]
    stale = [key for key in fired if key not in active]

    if fresh or stale:
        for key in stale:                             # balance recovered
            fired.pop(key, None)
        for a in fresh:
            fired[a["key"]] = {"at": store.now(), "remaining": a["remaining"],
                               "threshold": a["threshold"],
                               "provider": a["provider"]}
        state["fired"] = fired
        _write_alert_state(state)
    return fresh


def report(client=None, config=None, rows=None):
    """What has been committed, against what was declared."""
    rows = load() if rows is None else rows
    ceilings = caps(config) if config is not None else dict.fromkeys(SCOPES)
    by_provider, by_day = {}, {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        if client is not None and row.get("client") != client:
            continue
        cost = int(row.get("expected_cost") or 0)
        by_provider[row.get("provider")] = by_provider.get(row.get("provider"), 0) + cost
        by_day[row.get("day")] = by_day.get(row.get("day"), 0) + cost
    return {
        "client": client,
        "expected_total": sum(by_day.values()),
        "expected_today": by_day.get(today(), 0),
        "by_provider": by_provider,
        "by_day": by_day,
        "ceilings": ceilings,
        "provider_ceilings": {p: provider_caps(config, p)
                              for p in provider_names(config)},
        "balances": (balances(client, config, rows=rows)
                     if client and config is not None else {}),
        "unlimited": [s for s, v in ceilings.items() if v is None],
        "held": reserved(client) if client else reserved(),
        "note": "expected credits only. What the providers actually charged "
                "is a different question and belongs to src/costs.py",
    }


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.spendledger")
    p.add_argument("--client")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    from . import clients
    config = None
    if a.client:
        try:
            config = clients.load(a.client)
        except Exception:
            config = {}
    out = report(a.client, config)
    if a.json:
        print(json.dumps(out, indent=1))
        return 0
    print(f"expected total   {out['expected_total']}")
    print(f"expected today   {out['expected_today']}")
    for provider, cost in sorted(out["by_provider"].items(),
                                 key=lambda kv: -kv[1]):
        print(f"  {str(provider):<14} {cost}")
    print("\nceilings")
    for scope, limit in out["ceilings"].items():
        print(f"  {scope:<24} {'UNLIMITED - none declared' if limit is None else limit}")
    if out["provider_ceilings"]:
        print("\nper-provider ceilings")
        for provider, declared in out["provider_ceilings"].items():
            shown = ", ".join(
                f"{s}={'unlimited' if v is None else v}"
                for s, v in declared.items())
            print(f"  {provider:<16} {shown}")
    if a.client and config is not None:
        print()
        print(progress_block(a.client, config))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
