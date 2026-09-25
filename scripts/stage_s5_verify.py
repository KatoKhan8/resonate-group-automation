"""S5: two independent fresh verifications per address, over the staging journal.

USES THE PRODUCTION PATH UNCHANGED. `verification.verify` already encodes
every safety rule batch 1 requires - `required_confirmations: 2`,
`disagreement: hold`, and `sendable` assigned in exactly one place. Nothing
here re-implements verification, and the policy is NOT edited: operator
decision 2026-09-21 is that the stated order "ContactOut, Reoon, Deliverable"
is satisfied by the configured roles, with Reoon keeping the catch-all job it
holds through `accept_all_clears_on`.

RESUMABLE, BECAUSE THIS IS THE EXPENSIVE STAGE. Every address that gets an
answer is appended to the journal before the next is asked, so an interrupt
costs one address and never re-buys a verdict already held. `verify` itself
refuses to re-ask a provider whose answer is already on the contact.

SENDABLE IS NOT READY. This stage produces the verification half only. A lead
is READY when S6 collision and suppression have also cleared it fail-closed,
S7 has rendered copy, the MX decision is known_allowed or unknown_provider,
and the ICP verdict is IN. Those are separate columns in the journal and this
script never sets them.

EVERY CALL IS LEDGERED. `verify` writes the waterfall ledger and the spend
ledger only when it is handed a `rec`, and this script called it without one -
so roughly 22,000 credits of verification were invisible to the spend audit.
CLAUDE.md: a provider call that skips the ledger is invisible to the audit,
and an audit that reports clean because it watched nothing is worse than none.
`ledger_record` below is that carrier, and `spendledger.check` now refuses
this stage against the client's DECLARED ceilings like every other paid call.

RETRY ONCE, THEN PARK. A throttled hold is not a verdict and is re-asked - but
it was re-asked by EVERY pass, for ever, so the same addresses were re-bought
on each one. Operator decision 2026-09-24: one retry, then the address parks
and says why. `journal_state` is the one place that decides.

    py -3 scripts/stage_s5_verify.py                # all of them
    py -3 scripts/stage_s5_verify.py --limit 200    # a slice
    py -3 scripts/stage_s5_verify.py --s3 work/stage/s3-icp.jsonl

The default input is the amended 09-07 file - see `--s3` in `main`. The third
form names the superseded 09-21 pass, which is kept reachable because a
comparison against it is how the amendment was checked.
"""

import argparse
import concurrent.futures as cf
import csv
import datetime
import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import clients, spendledger, store, verification        # noqa: E402
from src.providers import load_env                              # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# WHICH CLIENT PAYS. Named once, because it is the client the config is loaded
# for AND the client the spend ledger is scoped to, and those two silently
# disagreeing is one tenant paying for another's run - `spendledger.check`
# refuses an unscoped budget for exactly that reason.
CLIENT = "productive"


# THE STAGE FILES MOVE WITH THE QUEUE, NOT WITH THE CHECKOUT.
#
# These were pinned to the directory this script lives under. `work/` is
# gitignored, so every git worktree carries its OWN nearly-empty copy, and a
# run from a worktree read an empty stage and printed a clean zero rather than
# failing. The state this stage reads and writes is client state and belongs
# beside the queue: `store.queue_path()` resolves that per call from `QUEUE`,
# which is the override the rest of the system already moves together, and
# `spendledger.path()` already derives itself the same way. So pointing
# `QUEUE` at a workspace moves the whole set - queue, spend ledger, stage -
# and leaves no file behind still reading the checkout.
def work_dir():
    return os.path.dirname(store.queue_path())


def stage_dir():
    return os.path.join(work_dir(), "stage")


def journal_path():
    return os.path.join(stage_dir(), "s5-verify.jsonl")


def source_path():
    return os.path.join(work_dir(), "Productive",
                        "productive_ICP_safe_to_send (1).csv")


# THE DEFAULT INPUT, AND WHY IT CHANGED. OPERATOR DECISION, 2026-09-24.
#
# It was `s3-icp.jsonl`, the 2026-09-21 S3 pass. That file carries verdict
# `out` on 15,642 domains the 09-23 amendment moved to `in`, with `mx: null`
# on every one of them, so this script's own predicate saw 4,869 eligible
# domains and 668 pending addresses - against 18,955 and 17,923 for the
# amended file. The runner was fast and pointed at almost nothing.
#
# The amended pair is `s3-icp-amended-PRODUCTIVE-2026-09-07.jsonl`, which
# holds the amended ICP verdicts, and `mx-amended-PRODUCTIVE-2026-09-07.jsonl`,
# which is that same set after the MX pass filled `mx` and `email_channel` in.
# ONLY THE SECOND IS READ HERE, because eligibility needs all three columns on
# one row and only the MX file has them: the ICP-amended file still has `mx`
# null on 15,642 rows and yields 5,815 domains, not 18,955.
#
# A previous agent added `--s3` and refused to move the default, because
# repointing it is ~35,000 credits of irreversible spend rather than a
# refactor. THE SPEND IS APPROVED, operator, 2026-09-24, so the default moves
# and the superseded file stays reachable by name.
S3_DEFAULT = "mx-amended-PRODUCTIVE-2026-09-07.jsonl"

# MX outcomes that permit the email channel. `known_blocked` and `no_mx` were
# already excluded at S4b; `dns_failure` is HELD because we could not ask,
# which is not the same fact as "no mail accepted".
MX_OK = ("known_allowed", "unknown_provider")


def read_addresses(path):
    """The address set a cohort file names, keyed as the journal keys them.

    Accepts a JSONL cohort (an `email` per row) or a plain list, one address
    per line, because the cohort files this stage is pointed at are built by
    other lanes and both shapes exist. Lower-cased on the way in: the journal,
    `contacts_for` and `verify` all key on the lower-cased address, and a set
    that disagreed about case would silently exclude the rows it should hold.
    """
    out = set()
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            email = line
            if line.startswith("{"):
                try:
                    email = (json.loads(line).get("email") or "").strip()
                except ValueError:
                    continue
            email = email.strip().lower()
            if "@" in email:
                out.add(email)
    return out


def eligible_domains(path=None):
    """IN domains whose email channel S4b left open."""
    out = {}
    with open(path or os.path.join(stage_dir(), S3_DEFAULT),
              encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if (row.get("verdict") == "in"
                    and row.get("email_channel") is True
                    and row.get("mx") in MX_OK):
                out[row["domain"]] = row
    return out


# A HOLD CAUSED BY A RATE-LIMITED PRIMARY IS NOT A VERDICT.
#
# Measured 2026-09-21: 980 of 1,052 holds read "reoon says valid but the
# primary is missing". ContactOut was answering 429 and billing nothing - the
# addresses were fine, the concurrency was not. Recording those as settled
# would bake a throttling artifact into batch 1 and they would never be
# re-asked, because `journal_state` skips anything already settled.
#
# So they are re-askable. The policy itself is untouched: a genuine
# "primary is missing" after a real answer still holds, it just gets asked
# again rather than being final on the first throttled try.
RETRYABLE = ("primary is missing", "primary is unknown",
             "every verifier failed")

# ... BUT RE-ASKABLE IS NOT RE-ASKABLE FOR EVER. Operator decision 2026-09-24.
#
# The rule above was written for one throttled run and had no end to it: an
# address whose last answer is retryable is un-settled by `journal_state`, so
# EVERY later pass buys it again, and buys it again after that. Measured on
# this journal: 23.5% of all 11,417 rows carry a retryable reason, and on the
# 400 addresses bought on 2026-09-24 - the clean, un-throttled arms - the rate
# is 45.5%. At that rate a pass over the 09-07 backlog leaves ~8,000 addresses
# that the next pass re-buys, and the one after that, with nothing in the
# system able to say how often any single address has been paid for.
#
# So: ONE retry, then PARK. Two attempts is what distinguishes a transient
# throttle - which a second ask clears - from an address the pair genuinely
# cannot agree on, which a third ask will not. A parked address is not bought
# again and the row that parks it says so in its own `parked_reason`.
#
# What this does NOT do is call a parked address invalid. It has no verdict,
# it has a hold, and `state`/`reason` still say which - parking is a spend
# decision about asking again, not a verification decision about the address.
MAX_ATTEMPTS = 2

# WHAT ONE ADDRESS IS ASSUMED TO COST BEFORE IT HAS COST IT.
#
# Used only to RESERVE against the per-run ceiling before a call is made, and
# replaced by the real figure from the ledger the moment the address answers.
# Measured 1.98 credits/address over this client's deliverable+reoon pair, so
# this is rounded UP: a reservation that under-counts would let the run cross
# the ceiling it is there to hold, and stopping one address early is the
# direction a spend control is allowed to be wrong in.
PER_ADDRESS_ESTIMATE = 2


def journal_state(path=None):
    """(settled, attempts) from the journal. The one authority on re-buying.

    `settled` is every address this pass must NOT pay for again, and it has
    two kinds in it: ANSWERED, where the last row is a verdict, and PARKED,
    where the address has had its `MAX_ATTEMPTS` and is still retryable.

    `attempts` counts only rows that were actually an attempt at an answer. A
    row carrying `stopped` is not one: the waterfall refused to spend - a
    budget ceiling, a per-contact cap - so nothing was asked, and counting it
    would park an address for a reason that has nothing to do with the
    address. The same row is left un-settled so the next pass re-asks it.
    """
    answered, attempts = set(), {}
    path = path or journal_path()
    if not os.path.exists(path):
        return answered, attempts
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            email = row.get("email")
            if not email:
                continue
            if row.get("stopped"):
                continue                 # refused, not asked; costs no attempt
            attempts[email] = attempts.get(email, 0) + 1
            if any(flag in str(row.get("reason") or "") for flag in RETRYABLE):
                answered.discard(email)
                continue
            answered.add(email)
    parked = {email for email, n in attempts.items()
              if n >= MAX_ATTEMPTS and email not in answered}
    return answered | parked, attempts


def contacts_for(domains):
    """Every contact in the source file on one of these domains, ONCE.

    The source CSV repeats an address where the same person appears twice -
    376 rows of the 26,628 on eligible domains. Each repeat was its own
    `contact` dict, so `verify`'s "already have this one" could not see it and
    the pass bought the same address twice inside a single run. De-duplicated
    here, on the same key the journal is keyed by, which is the only key that
    makes the within-run and across-run rules agree.
    """
    rows, seen = [], set()
    with open(source_path(), newline="", encoding="utf-8-sig") as handle:
        for raw in csv.DictReader(handle):
            email = (raw.get("Work Email") or "").strip().lower()
            if "@" not in email:
                continue
            domain = email.rsplit("@", 1)[1]
            if domain in domains and email not in seen:
                seen.add(email)
                rows.append({
                    "key": email,
                    "email": email,
                    "domain": domain,
                    "first_name": (raw.get("First Name") or "").strip(),
                    "title": (raw.get("Job Title") or "").strip(),
                    "company": (raw.get("Company") or "").strip(),
                    "linkedin": (raw.get("Url") or "").strip(),
                })
    return rows


def pair_of(contact):
    """The providers that actually answered, in the order they answered.

    Condition 1 of the batch-1 grant requires the PAIR recorded per lead, not
    just the verdict - "two independent fresh verifications passed (pair
    recorded per lead)". A state of `verified` without the names cannot be
    audited afterwards.
    """
    names = []
    for entry in verification.all_evidence(contact):
        provider = entry.get("provider")
        if provider and provider not in names and entry.get("status") != "error":
            names.append(provider)
    return names


def ledger_record(contact):
    """The ledger carrier for one address.

    EVERY GUARD IN `verify` IS GATED ON `rec is not None`. Both ledgers -
    `waterfall.record_step` per record and `spendledger.record`/`.check` per
    client - and every `events.record` besides. This script passed no `rec`,
    so the whole stage bought two credits an address and wrote nothing
    anywhere: ~22,000 credits of verification that the spend audit could not
    see. An audit that reports clean because it watched nothing is worse than
    none, and this is the shape that produced one.

    It carries `client` because that is what `spendledger` is scoped by and
    what `check` refuses to proceed without. ONE PER CONTACT, never shared:
    `events.record` scans the record's whole event list to de-duplicate, so a
    record reused across 18,000 addresses turns a linear pass quadratic.

    These addresses have no queue record - they are CSV rows that have not
    been ingested - so this is not a queue record and is never written to the
    queue. `store.refuse_production_write` still guards the spend ledger it
    causes to be written, exactly as it does for every other writer.
    """
    return {"id": f"s5:{contact['email']}", "client": CLIENT,
            "contacts": [contact], "events": [], "waterfall": []}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--workers", type=int, default=8,
                        help="concurrency; size against the TIGHTER provider")
    # THE INPUT IS STILL NAMEABLE, NOW THAT THE DEFAULT IS THE FUNNEL.
    #
    # See `S3_DEFAULT` for what moved and on whose authority. The flag stays
    # because the superseded 09-21 pass is how the amendment is checked, and
    # because a future amendment will arrive as another file rather than as an
    # edit to this one.
    parser.add_argument("--s3", default=None,
                        help="the S3/S4b journal to read eligibility from; "
                             f"default is {S3_DEFAULT}, the amended 09-07 set")
    parser.add_argument("--report-every", type=int, default=900,
                        help="seconds between progress lines; default 15 min")
    # SCOPE TO A COHORT BY ADDRESS, BECAUSE ELIGIBILITY IS BY DOMAIN AND THE
    # EXCLUSIONS ARE NOT.
    #
    # `eligible_domains` filters DOMAINS and `contacts_for` then takes every
    # address the source CSV holds on one - which is correct for the whole
    # 09-07 supply and wrong for a cohort whose exclusions are per PERSON.
    # Measured 2026-09-25 against the provider-confirmed US cold cohort:
    # 7,647 of its domains are S5-eligible and carry 6,817 pending addresses,
    # but only 6,019 of those are cohort members. The other 798 are addresses
    # the cohort's four exclusions REMOVED - replied, bounced, in-sequence -
    # and a domain-scoped run buys all 798 of them, about 1,580 credits spent
    # re-verifying people already excluded from the push.
    #
    # Restriction only. This can never add an address to the run, and an
    # address absent from the file is simply not bought.
    parser.add_argument("--only", default=None,
                        help="path to a JSONL/text file of addresses; the run "
                             "is intersected with it. Restriction only.")
    # THE DECLARED `per_run` CEILING, ENFORCED BY THE RUNNER BECAUSE `check`
    # DOES NOT ENFORCE IT.
    #
    # `spendledger.check` iterates `per_day` and `total` and then tests
    # `per_provider_per_day`. `per_run` is in `spendledger.SCOPES` and read by
    # `caps()`, and nothing on any spend path consults it - pinned as a known
    # LEAK by tests/test_the_second_client_runs_on_the_same_engine.py. While
    # `per_day` was 5,000 that gap was nearly harmless. The operator raised
    # `per_day` to 15,000 on 2026-09-25, and a declared 2,000-per-run ceiling
    # that nothing enforces now means one invocation may quietly spend seven
    # and a half times the limit the client file states.
    #
    # So the runner holds itself to it. The default is the client's OWN
    # declared `per_run` rather than a number chosen here, and the stop is the
    # same stand-down the durable ceiling uses: submitted workers return
    # without asking, nothing already bought is discarded, and the journal is
    # complete for every address that did get an answer. Resume by running
    # again - `journal_state` never re-buys a settled verdict.
    parser.add_argument("--max-credits", type=int, default=None,
                        help="stop the pass once this many credits have been "
                             "bought; default is the client's declared "
                             "per_run, which spendledger.check does not "
                             "enforce")
    args = parser.parse_args(argv)

    load_env()
    os.makedirs(stage_dir(), exist_ok=True)
    s3 = args.s3 or os.path.join(stage_dir(), S3_DEFAULT)
    config = clients.load(CLIENT)
    # THE CLIENT'S POLICY, NOT THE MODULE DEFAULT.
    #
    # This read DEFAULT_POLICY, which was harmless only while the two agreed.
    # On 2026-09-21 the operator removed ContactOut from Productive's
    # VERIFICATION roles - primary deliverable, secondary reoon, reoon keeps
    # the catch-all - and left the defaults alone for every other workspace.
    # `policy_for` is the mechanism built for exactly that, and a runner that
    # ignores it would have kept verifying with a provider the operator
    # removed while the config said otherwise.
    policy = verification.policy_for(config)
    print(f"  policy: primary={policy['primary']} "
          f"secondary={policy['secondary']} catch_all={policy['catch_all']} "
          f"confirmations={policy['required_confirmations']}", flush=True)

    # WHAT THE DECLARED CEILINGS ARE, BEFORE ANYTHING IS BOUGHT.
    #
    # Printed rather than assumed. `spendledger.check` enforces `per_day` and
    # `total`; `per_run` is declared in the client file and is NOT checked
    # there, so it is reported here as declared-but-unenforced rather than
    # left to look like a control that exists.
    ceilings = spendledger.caps(config)
    committed_today = spendledger.spent(CLIENT, day=spendledger.today())
    print(f"  spend ledger: {spendledger.path()}", flush=True)
    print(f"  ceilings {ceilings}  committed today {committed_today}"
          f"  (per_run is declared and NOT enforced by spendledger.check)",
          flush=True)

    domains = eligible_domains(s3)
    print(f"  eligibility from {s3}", flush=True)
    already, attempts = journal_state()
    people = [c for c in contacts_for(domains) if c["email"] not in already]
    print(f"S5  eligible domains {len(domains)}  contacts to verify "
          f"{len(people)}  settled or parked {len(already)}", flush=True)

    if args.only:
        allowed = read_addresses(args.only)
        before = len(people)
        people = [c for c in people if c["email"] in allowed]
        print(f"  scoped to {args.only}: {len(allowed)} address(es) named, "
              f"{before} pending -> {len(people)}  "
              f"({before - len(people)} outside the cohort, not bought)",
              flush=True)

    # The declared per_run, unless overridden DOWNWARD on the command line.
    max_credits = args.max_credits
    if max_credits is None:
        max_credits = ceilings.get("per_run")
    if max_credits is not None:
        print(f"  per_run self-enforced at {max_credits} credit(s) this "
              f"invocation (spendledger.check does not enforce it)",
              flush=True)

    if args.limit:
        people = people[:args.limit]

    counts = {}
    started = last = time.time()
    done = credits = parked = stopped_rows = 0

    # THE RUN STOPS WHEN THE DURABLE CEILING REFUSES, RATHER THAN GRINDING.
    #
    # `verify` catches `BudgetExceeded` itself, records the refusal and returns
    # a decision with `stopped` set - correctly, because one contact stopped by
    # a ceiling is not an error. But the ceiling is per client per day, so the
    # contact after it is refused too, and so is every one after that:
    # continuing would walk the remaining backlog asking nothing and writing
    # nothing. `Executor.map` has already submitted every task, so the workers
    # are told to stand down through this rather than by breaking the loop.
    halted = threading.Event()

    # BOUNDED CONCURRENCY, BECAUSE PROVIDER WAIT IS THE WHOLE COST.
    #
    # Measured 2026-09-21: sequentially this runs at 0.35 contacts/sec - about
    # 2.9s each, nearly all of it waiting on two HTTP calls - which is 7.4
    # HOURS for 9,312 addresses. The work is embarrassingly parallel: every
    # contact is its own dict and `verify` touches nothing shared.
    #
    # K=8, AND CONTACTOUT IS NOT IN THIS CLIENT'S POLICY AT ALL.
    #
    # K=3 was set on 2026-09-21 against ContactOut's 60/min, after eight
    # workers made ~168 calls/min and the primary went missing on 93% of
    # addresses. That reasoning was correct about ContactOut and wrong about
    # this runner: the same operator decision that day removed ContactOut
    # from Productive's VERIFICATION roles, and `policy_for(config)` above
    # resolves to primary=deliverable secondary=reoon catch_all=reoon. The
    # binding limit was sized against a provider this script never calls,
    # and the estate paid 351 minutes for 8,387 addresses for it.
    #
    # WHAT IS DOCUMENTED, AND WHAT IS NOT:
    #
    #   Reoon        4/sec, power mode. PROVIDER-ROUTING-POLICY.md, the
    #                operator's standing order of 2026-09-21. It is the only
    #                rate number in this repository for either verifier, and
    #                it is OPERATOR-STATED rather than vendor-published -
    #                docs/PERF-LATENCY-MODEL-2026-09-18.md classifies Reoon's
    #                published limit as NOT DOCUMENTED.
    #   Deliverable  NOT DOCUMENTED ANYWHERE. Not in `src/providers/
    #                deliverable.py`, which carries the transport contract
    #                read off the vendor's API page and no rate; not in any
    #                docs/ evidence file; explicitly UNKNOWN at
    #                docs/PERF-LATENCY-MODEL-2026-09-18.md:266.
    #
    # An unknown limit is not permission to guess one. It is measured, on the
    # real route, bounded, and classified OBSERVED with its date - the method
    # `ratelimit.LimitClassification.OBSERVED` exists for and
    # docs/PERF-CONCURRENCY-MEASURED-2026-09-18.md established.
    #
    # MEASURED 2026-09-24, three arms of 100 real addresses each, same estate,
    # back to back. Every address bought is in the journal and counted toward
    # the backlog, so the sample is spend rather than waste:
    #
    #     K      addr/s   speedup   pair=2    ERROR   verified
    #     3      0.268      1.0x    100/100     0       49%
    #     8      1.105      4.1x    100/100     0       50%
    #     16     1.759      6.6x    100/100     0       45%
    #
    # Both verifiers answered on 300 of 300 addresses at every K. The 09-21
    # failure signature - a pair of one, "the primary is missing" - did not
    # appear once, which is what distinguishes this from that run.
    #
    # K=8 is the default rather than K=16, on three grounds. Each contact
    # makes about one Reoon call, so K=8 is ~1.1 calls/sec against the stated
    # 4/sec - a quarter of the documented ceiling, and K=16 is 1.76/sec, still
    # inside it, so Reoon is not what decides this. Deliverable is, and its
    # limit is UNKNOWN: K=16 buys 59% over K=8 for twice the pressure on the
    # provider nobody has a number for, and the knee is already visible
    # between the two arms. And the escalation rule this repository already
    # wrote down - "a clean run at K is not permission to run at 2K",
    # scripts/measure_provider_concurrency.py - makes a bounded clean arm
    # evidence for that K and not for the next one. K=16 is measured clean and
    # is available with --workers 16; it is not the standing default.
    #
    # RE-CONFIRMED 2026-09-24 after the ledger was wired in, because that
    # added a per-call `spendledger.check`, which reads the whole ledger file
    # from disk under the GIL - work that did not exist when the table above
    # was measured, and work that gets slower as the ledger grows. It is not
    # what binds: see the run recorded in
    # docs/S5-LEDGERED-AND-PARKED-2026-09-24.md.
    lock = threading.Lock()

    # WHAT THE RUN HAS COMMITTED ITSELF TO, INCLUDING CALLS STILL IN FLIGHT.
    #
    # Measured, not reasoned: with the cap tested only AFTER each answer, a
    # real chunk at K=8 stopped at 2,044 against a ceiling of 2,000. The
    # first version of this comment claimed the overshoot was "at most one
    # address", which was true at --workers 1 - the width the unit tests run
    # at - and wrong by 22 addresses at the width production uses.
    #
    # `Executor.map` submits every task at once, so eight workers keep buying
    # while the consumer walks results in submission order; by the time the
    # consumer has added up 2,000 credits, the workers are already some way
    # past it. Checking after the fact can therefore only ever report an
    # overshoot, never prevent one.
    #
    # So a worker RESERVES before it asks. `PER_ADDRESS_ESTIMATE` is rounded
    # UP from the measured 1.98, so the reservation is never an under-count
    # and the run stops a little early rather than a little late - the
    # conservative direction for a spend control. The reservation is
    # reconciled against what the address actually cost once it answers, so
    # the estimate cannot drift away from the ledger over a long pass.
    reserved = 0

    def one(contact):
        nonlocal reserved
        if halted.is_set():
            return contact, None, None, None      # never asked; not an error
        if max_credits is not None:
            with lock:
                if reserved + PER_ADDRESS_ESTIMATE > max_credits:
                    if not halted.is_set():
                        halted.set()
                        # SAID OUT LOUD. A pass that stops spending without
                        # saying why is indistinguishable from one that ran
                        # out of work, and the difference is the whole
                        # question when the next run is being sized.
                        print(f"\n  HALTED: {reserved} credit(s) committed, "
                              f"and the next address would cross the "
                              f"client's declared per_run ceiling of "
                              f"{max_credits}. spendledger.check does NOT "
                              f"enforce per_run; this runner does. The "
                              f"address was not asked - run again to "
                              f"continue, the journal never re-buys a "
                              f"settled verdict.", flush=True)
                    return contact, None, None, None      # never asked
                reserved += PER_ADDRESS_ESTIMATE
        rec = ledger_record(contact)
        try:
            decision = verification.verify(contact, policy, live=True,
                                           rec=rec, config=config) or {}
            return contact, rec, decision, None
        except Exception as exc:                                # noqa: BLE001
            return contact, rec, None, exc

    with open(journal_path(), "a", encoding="utf-8") as journal:
        with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
            for contact, rec, decision, exc in pool.map(one, people):
                if exc is not None:
                    # A provider failure is not a verdict. The address is left
                    # ABSENT from the journal so the next pass re-asks it,
                    # rather than written as `unknown`, which looks settled.
                    with lock:
                        print(f"  ERROR {type(exc).__name__}: "
                              f"{str(exc)[:110]}", flush=True)
                    continue
                if decision is None:
                    continue                      # stood down after the halt

                state = decision.get("state") or "unknown"
                reason = decision.get("reason")
                stop = decision.get("stopped")
                pair = pair_of(contact)
                # WHAT WAS ACTUALLY BOUGHT FOR THIS ADDRESS, from the ledger
                # rather than from the number of providers named: a provider
                # that declined locally answers without charging, and a
                # provider already answered for is not asked again.
                spent = sum(step.get("expected_cost") or 0
                            for step in (rec.get("waterfall") or []))
                # An attempt only counts once it was allowed to ask. A row
                # that stopped at a ceiling is recorded and left un-settled.
                attempt = attempts.get(contact["email"], 0) + (0 if stop else 1)
                retryable = any(flag in str(reason or "")
                                for flag in RETRYABLE)
                park = bool(retryable and not stop and attempt >= MAX_ATTEMPTS)

                with lock:
                    done += 1
                    credits += spent
                    # The estimate was a placeholder for THIS address; what it
                    # really cost is now known from the ledger rows the
                    # waterfall wrote, so the reservation is corrected. Over a
                    # long pass this keeps `reserved` tracking the ledger
                    # rather than accumulating the rounding in the estimate.
                    if max_credits is not None:
                        reserved += spent - PER_ADDRESS_ESTIMATE
                    counts[state] = counts.get(state, 0) + 1
                    if park:
                        parked += 1
                    row = {
                        "email": contact["email"],
                        "domain": contact["domain"],
                        "state": state,
                        "sendable": bool(contact.get("sendable")),
                        "pair": pair,
                        "confirmations": len(pair),
                        "reason": reason,
                        "credits": spent,
                        "attempt": attempt,
                        "at": datetime.datetime.now(
                            datetime.timezone.utc).isoformat(),
                    }
                    if stop:
                        # NOT A VERDICT, AND THE FIELD SAYS SO. `journal_state`
                        # reads this key before anything else and neither
                        # settles the address nor counts the attempt.
                        stopped_rows += 1
                        row["stopped"] = stop
                    if park:
                        row["parked"] = True
                        row["parked_reason"] = (
                            f"retryable on attempt {attempt} of "
                            f"{MAX_ATTEMPTS}; not bought again - {reason}")
                    journal.write(json.dumps(row) + "\n")
                    journal.flush()

                    # ONLY THE DURABLE CEILING HALTS THE PASS. `verify` sets
                    # `stopped` for three different refusals and they are not
                    # the same fact: the per-contact cost cap is about ONE
                    # address and the next one is unaffected, while the
                    # spend-ledger ceiling is per client per day and refuses
                    # everything after it too. Halting on the first would stop
                    # a whole run over a single expensive address.
                    if (str(stop).startswith("durable budget")
                            and not halted.is_set()):
                        halted.set()
                        print(f"\n  HALTED: {stop}\n  The refusal is the "
                              f"client's declared ceiling doing its job. "
                              f"Nothing after this address was asked.",
                              flush=True)

                    # THE SAME CEILING, CHECKED AGAIN ON WHAT WAS REALLY SPENT.
                    #
                    # The reservation above is what PREVENTS the overshoot;
                    # this is the check on the authoritative number, summed
                    # from the ledger rows rather than from the estimate. It
                    # fires only if an address cost more than it reserved, so
                    # in a normal pass the reservation stops the run first and
                    # this never triggers.
                    if (max_credits is not None and credits >= max_credits
                            and not halted.is_set()):
                        halted.set()
                        print(f"\n  HALTED: {credits} credits bought, which "
                              f"reaches the client's declared per_run "
                              f"ceiling of {max_credits}. spendledger.check "
                              f"does NOT enforce per_run; this runner does. "
                              f"Nothing after this address was asked - run "
                              f"again to continue, the journal never re-buys "
                              f"a settled verdict.", flush=True)

                    if (time.time() - last >= args.report_every
                            or done == len(people)):
                        last = time.time()
                        rate = done / max(1e-9, time.time() - started)
                        verified = counts.get(verification.VERIFIED, 0)
                        print(f"  {done}/{len(people)}  verified {verified}  "
                              f"credits {credits}  states {counts}  "
                              f"{rate:.2f}/s  "
                              f"{(time.time()-started)/60:.0f}m", flush=True)

    elapsed = time.time() - started
    print(f"\nS5 DONE in {elapsed/60:.1f}m  states {counts}")
    print(f"  answered {done - stopped_rows}  parked {parked}  "
          f"refused by ceiling {stopped_rows}  "
          f"not asked {len(people) - done}")
    # THE COST, FROM THE LEDGER AND FROM THE RUN, PRINTED SIDE BY SIDE. Two
    # independent counts of the same spend: if they disagree, a call went
    # round the ledger and the audit is the thing that is wrong.
    print(f"  credits this run {credits}  "
          f"({credits/max(1e-9, elapsed/60):.0f}/min, "
          f"{done/max(1e-9, elapsed):.2f} addr/s at K={args.workers})")
    print(f"  spend ledger now reports {spendledger.spent(CLIENT, day=spendledger.today())} "
          f"committed today for {CLIENT}")
    print("  `verified` is the verification half only. READY additionally "
          "needs S6 collision/suppression, S7 copy, and the ICP verdict.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
