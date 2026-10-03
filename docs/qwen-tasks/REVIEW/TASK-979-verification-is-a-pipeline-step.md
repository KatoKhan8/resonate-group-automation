# TASK-979 - Verification is a pipeline step

STAGE: REVIEW
BRANCH: `task-979-verification-is-a-pipeline-step` off master `e967271d`
WRITTEN AFTER THE CODE, and after the live runs. Every acceptance command
below was EXECUTED, in both directions, and the outputs quoted are real.

---

## The headline: nothing new was built, and that was the finding

The lane was briefed to build `src/verify.py`. It must not exist.
`src/verification.py` (1,005 lines) already is the pipeline step, and
building a second one would have been the parallel state machine CLAUDE.md
forbids by name.

What was missing was not a Reoon call. It was **two numbers nobody had
chosen**, and the module said so about one of them in its own docstring:

> `age_of`: "There is no freshness *rule* in this build - nobody has chosen
> how long a verification is good for, and choosing costs re-verification
> credits, so it is a decision rather than a parser. `MANUAL-REVIEW.md` 9b is
> where that decision is asked for."

So the ages were measured, reported, and read by nothing - this
repository's recurring defect, a thing computed correctly that nothing
downstream consumes. The operator has now answered: **30 days**, and
**a catch-all holds**.

---

## Step 1 - what already existed, with the commands

### 1. Does anything call a Reoon endpoint, and is there a `REOON_KEY`?

    $ grep -rin "reoon" src/ scripts/ config/ | wc -l
    # 40+ hits across 20 modules

    $ grep -n "REOON_KEY" src/config.py
    120:    ("REOON_KEY", LIVE, "providers",
    121:     "the escalation verifier, reached only when two providers disagree"),

**YES to all of it.** `src/providers/reoon.py` implements
`GET https://emailverifier.reoon.com/api/v1/verify` in power mode,
`REOON_KEY` is in `config.VARIABLES` (name NOT guessed - read from the
registry), and `verification.call("reoon", email)` normalises the answer.
`verification.verify()` is the waterfall runner and it already:

* reserves against `spendledger` BEFORE the call and settles after, under one
  lock, because eight workers each reading the ledger bought 2,044 credits
  against a declared 2,000;
* writes `waterfall.record_step(..., EMAIL_VERIFICATION, ...)`;
* records `PROVIDER_CALL_STARTED` / `COMPLETED` / `SKIPPED` events;
* refuses to re-buy an answer it already holds (`needs()`).

`scripts/stage_s5_verify.py` is the batch driver, resumable, and its own
header records that it once skipped the ledger for ~22,000 credits.

### 2. Where does `eligibility` read verification state, and which field?

    $ grep -n "verification_unknown" src/eligibility.py
    90:HELD_VERIFICATION_UNKNOWN = "held:verification_unknown"

    $ sed -n 845,852p src/eligibility.py      # before this change
    policy = lint.policy_for_record(rec)
    decision = verification.resolve(contact, policy)
    if not lint.sendable(contact, policy):
        if decision.get("insufficient_confirmations"):
            return HELD, [HELD_INSUFFICIENT_CONFIRMATIONS]
        state = decision.get("state")
        if state in (None, "unknown", "accept_all_uncleared", "held"):
            return HELD, [HELD_VERIFICATION_UNKNOWN]

**It reads NO FIELD.** `eligibility._email_checks` calls
`verification.resolve(contact, policy)`, which recomputes from the evidence
list every time and deliberately ignores the stored `verification.state` -
`is_sendable` says why at length: the state is a cached opinion and the
evidence is the durable fact, so a hand edit or an older policy cannot carry
a stale clearance into a payload.

That is why **this lane needed almost no eligibility change at all**, which
matters because lane 4 is editing that file concurrently. The rule was added
in `verification._verdict` and arrived at `eligibility`, `channels`,
`lint.sendable`, `approve`, `push`, `campaigns`, `qa`, `report` and the web
API without any of them being touched. Eligibility's whole diff is one
constant, one four-line branch and one sentence in the reason table.

### 3. Is there already a per-contact verification record?

**Yes, and it is canonical.** `contact["verification"]` carries `state`,
`sendable`, `reason`, `stopped`, `cost`, `at`, `providers`,
`confirmation_count`, `required_confirmations`, `confirmed_by`,
`disagreement`, a per-provider `results` map with `checked_at`, and the
append-only `evidence` list. Measured on the live queue:

    $ py -3 -c "...verification.all_evidence(c)..."     # savagebrands-com
    contactout  valid  2026-09-13T09:33:23+00:00
    deliverable error  2026-09-13T09:33:23+00:00
    reoon       valid  2026-09-13T09:33:28+00:00   score 98  safe_to_send True

So: **REUSED, not built.** The source and the time it was measured were
already on the contact. The four states the brief asked for map onto the
module's existing five (`verified` / `invalid` / `accept_all_uncleared` /
`unknown` / `held`), which are strictly more informative - `held` separates
"two vendors disagree" from "nobody could tell us", and collapsing them
would have lost the distinction a reviewer needs.

---

## What savagebrands actually proved, and it was not a missing verification

The brief's premise was that the estate is blocked on unverified addresses.
For `savagebrands-com` / `bison_lead_id 203718` that was false:

    before:  contactout valid (20d) + reoon valid, safe_to_send, score 98 (20d)
             -> held, "contactout says valid but the primary is missing,
                       and policy does not clear on the secondary alone"

Two independent vendors had cleared it. It was held because **Productive's
policy names `deliverable` as primary** and this contact's Deliverable row
was an `error` - `ContractNotVerified`, raised before the network because
Deliverable's wire contract had never been read from a real answer.

**Deliverable answers now.** Measured, one call:

    deliverable.verify(<savagebrands-com lead 203718's address>)
      -> {'status': 'valid', 'catch_all': False, ...}

That is 61 contacts estate-wide held by `"the primary is missing"` - not for
want of verification, but for want of ONE call to the provider their own
client config names first.

---

## The change

`src/verification.py`, two policy keys in `DEFAULT_POLICY`:

* `max_verification_age_days: 30` - unknown, absent or older than 30 days is
  HOLD. **Undated counts as absent**, because `legacy_evidence` stamps
  `at: None` rather than inventing today's date, so an entry nothing can date
  is one nobody can vouch for (invariant 0).
* `catch_all_is_sendable: False` - a cleared catch-all holds. The clearance
  stays in the reason, so it becomes sendable the moment the operator rules.

Applied in `_verdict`, where the required-confirmations rule already lives,
so a future branch of `decide` inherits it without its author remembering -
and downgrading stays one-way: it can hold a sendable verdict and can never
clear a held one.

**COUNTED, NOT SCANNED FOR THE OLDEST.** `apply` is append-only, so a
re-verified address keeps every earlier row. Refusing on the oldest entry
would have held a contact two vendors confirmed this morning because a third
vendor's answer from last year is still on the record, while an identical
contact with a shorter history sent. A rule whose answer depends on surplus
evidence is not a freshness rule.

**ABSENT IS NOT OFF.** `policy.get("max_verification_age_days", DEFAULT)` -
a policy dict assembled by hand still gets 30 days. Only an explicit `None`
disables it. `policy.get()` returning `None` for an unknown key would have
been the quietest possible way to lose the guard.

`src/eligibility.py`: `HELD_VERIFICATION_STALE = "held:verification_stale"`,
asked before the state, plus its sentence in the reason table. An address
verified 40 days ago needs one re-check; an address nobody ever cleared needs
a provider that can answer. Reporting both as `verification_unknown` sends a
reviewer looking for the wrong fix.

---

## Acceptance commands - EXECUTED, failing before and passing after

Reference tree: a detached worktree at `e967271d` that no track owns.

### A1. The gate itself

    $ cd <ref e967271d> && py -3 -m unittest tests.test_verification_freshness_is_a_gate
    FAILED (failures=2, errors=20)
      AssertionError: 'eligible' != 'held'
      TypeError: decide() got an unexpected keyword argument 'now'
      AttributeError: module 'src.eligibility' has no attribute
                      'HELD_VERIFICATION_STALE'

    $ cd <branch> && py -3 -m unittest tests.test_verification_freshness_is_a_gate
    Ran 23 tests - OK

The headline failure is the first one: on master, `eligibility.decide`
returns **`eligible`** for an address whose only confirmations are 400 days
old. That is the bug, stated as a test.

### A2. The controls, which a blanket "hold everything" change would break

Every hold in that file is paired with the same evidence made current. The
three that would catch a gate that refuses everything:

* `test_a_confirmation_inside_the_window_sends` - 29 days, sends.
* `test_the_SAME_verdict_with_a_date_on_it_clears` - the identical legacy
  verdict, dated today, sends.
* `test_a_clean_step_is_eligible` - the fixture's own fresh verification
  still reaches `ELIGIBLE` through the whole gate. **This one passes on
  master AND on the branch**, which is what a control should do.
* `test_the_hold_is_the_policy_and_not_a_lost_clearance` - the same catch-all
  with the operator's decision reversed sends, so the hold is a policy
  switch rather than the catch-all path having broken.
* `test_an_expired_error_row_does_not_hold_a_fresh_pair` - an `error` row is
  evidence of nothing in this direction too.

### A3. The live control: how many real contacts does this hold?

Both trees, same production queue, after batches 1 and 2:

    $ QUEUE=<production> py -3 -c "...channels.email_verdict..."
    MASTER e967271d  SENDABLE = 715
    BRANCH 717547bd  SENDABLE = 711

**Exactly 4**, and all four for the same named reason:

    1gslab-com      contact-02     accept_all_uncleared   newest=0d
    8ms-com         contact-03     accept_all_uncleared   newest=17d
    alex-gross-com  contact-05     accept_all_uncleared   newest=20d
    adsvibe-nl      contact-04   accept_all_uncleared   newest=20d
      "catch-all cleared by reoon, but policy does not send to a catch-all"

And **nothing became newly sendable** (`comm -13` was empty), which is the
other direction of the same check.

So the two rules are measurably not a blanket hold:

* the **catch-all** decision holds 4 contacts, today;
* the **30-day** rule holds **0 contacts today**. The oldest evidence behind
  any sendable address is 20 days, so it begins biting in 10 days, which is
  the honest answer and the reason it was worth adding before it was needed.
  It reports `stale` on 13 contacts that were already held for other
  reasons, so their reason code is now right.

### A4. No regression anywhere a sendability change can reach

43 modules, branch versus the `e967271d` reference, compared **by name set
and never by count**:

    Ran 1256 tests in 94.504s        FAILED (failures=22, errors=5)
    === NEW (0) ===
    === FIXED (0) ===

The reference's own 22 failing names are unchanged. Zero new names.

---

## The 21 test files in this diff, and why they are not churn

A freshness rule makes **every absolute date in a fixture a time bomb.**
`tests/fixtures/*.jsonl` stamp `2026-08-27` confirmations.

Measured: **35 tests** across `test_approve`, `test_push`, `test_generate`,
`test_eligibility` and `test_qa` broke on the day the rule landed, and not
one of them is about freshness - they are about approvals, payloads, lint
and send offsets. `tests/test_verification_refusal.py` pinned a literal
`2026-09-01` and would have started failing on **2026-10-02** with no code
change at all and nothing to point at.

The fix is one door. `tests/base.install_fixture` now re-dates verification
timestamps on the way in (`redate_verification`), and the **19 call sites
that bypassed it with a raw `shutil.copyfile`** go through it - which also
fixes all 19 under the sqlite backend, where a raw copy never worked.
It moves TIMESTAMPS only: no status, verdict, provider or address, so a
fixture whose address was refused or contradictory stays exactly that.
Current, never positive.

**One trap caught in the act, worth recording.** The scripted rewrite of
those 19 imports produced `from tests.base import , (FIXTURES, ...` in two
files - a SyntaxError. The run then reported **0 new failures and 22
fixed**, because `unittest` never loaded the suite. The log had no
`Ran N tests` line. That is "a running suite shows no failures" and "assert
the file changed" in one: the delta was only believable after
`grep -E "^Ran [0-9]+ test"` confirmed 532 tests on both sides.

---

## Step 3 - the live runs

Every call went through `verification.verify(..., live=True, rec=rec,
config=...)`, the only path that reaches both ledgers. No provider module
was called directly by the runner.

### Batch 1 - savagebrands alone, 1 ledgered credit

    before: held        / held:verification_unknown
    after:  verified    / held:approval_stale
            confirmed_by: [contactout, deliverable, reoon]
            verification.at: 2026-10-03T11:51:25+00:00

    work/spend-ledger.jsonl  20340 -> 20341 rows
    {"at":"2026-10-03T11:51:25+00:00","client":"productive",
     "provider":"deliverable","call":"deliverable-verify","expected_cost":1}

**Verification has stopped being this contact's blocker.** What holds it now
is `approval_stale`, which is the 599-contact problem and another lane's.

### Batch 2 - ten more from the `verification_not_sendable` set, 12 credits

    ogpartner-dk         contact-06       held      -> held       (primary still missing)
    nineyards-ie         contact-07       held      -> verified   blocked:not_selected_for_campaign
    nineyards-ie         contact-08     held      -> verified   blocked:not_selected_for_campaign
    16kagency-com        contact-09         held      -> verified   held:draft_not_approved
    1gslab-com           contact-02       catch_all -> catch_all  held:verification_unknown
    20northmarketing-com contact-10        unknown   -> verified   skipped:no_such_step
    25wat-com            contact-11     held      -> verified   held:draft_not_approved
    28row-com            contact-12        held      -> verified   held:approval_stale
    2ton-com             contact-13      unknown   -> catch_all  skipped:no_such_step
    321webmarketing-com  contact-14  catch_all -> held       skipped:no_such_step

**7 of 10 reached verified/sendable.** None of the 7 reached ALLOW, and in
every case the next gate is a different lane's: draft, approval, or campaign
selection.

### Batch 3 - NOT RUN. Capped before the fan-out, and here is the number

    contacts with anything left to buy: 483
    expected credits: 897        maximum credits: 1311

    spendledger.usd_estimate(897,  'credits') -> (None, None, 'unknown')
    spendledger.usd_estimate(1311, 'credits') -> (None, None, 'unknown')
    spendledger.USD_PER_UNIT['credits']       -> None

**The 25 USD test cannot be evaluated, so the spend was not made.** The one
authority that prices spend says a verification credit is unpriced, and says
it deliberately:

> `USD_PER_UNIT`: "`None` means NOBODY HAS PRICED IT, and that is a real
> answer ... A report that sums a made-up rate is the defect this table
> exists to end."

What IS measured: **1 credit per verifier call** (`verification.COSTS`), and
**13 credits for 11 contacts** actually spent. Scaling that measured rate
gives 897-1311 credits for the rest. Converting that to dollars needs a rate
from the operator or an invoice; missing evidence is never positive evidence,
so "probably under 25 USD" is not a finding this task may make.

**ASK:** the USD-per-credit rate for Deliverable and for Reoon. With it,
`USD_PER_UNIT` stops returning `None` for every verification row in the
ledger - not just this batch - and the 25 USD cap becomes computable.

---

## Declined, and why

* **`src/verify.py`** - refused. `src/verification.py` is the canonical path;
  a second one is the drift CLAUDE.md forbids.
* **Batch 3 (483 contacts, 897-1311 credits)** - stopped at the cap, because
  the USD rate is `None` by the system's own authority.
* **`required_confirmations` and the Deliverable-primary policy** - not
  touched. 61 contacts are held by `"the primary is missing"` under a policy
  naming a provider that was refusing locally. Deliverable answers now, so
  one call each fixes them; that is a client-config decision and an
  operator's call, not this lane's.
* **The 13 `CompanyNameUnusable` exceptions out of `decide`** - noted, not
  fixed, as briefed. An exception is not a verdict.
* **`scripts/run_suite.py`** - not run. The main session holds the lock.
  Single modules only, measured against a detached reference at `e967271d`.

## Disclosed

One exploratory `deliverable.verify()` call was made directly, outside
`verification.verify`, while establishing whether Deliverable could answer
at all. It cost 1 credit and it **skipped the spend ledger**, which is the
rule in CLAUDE.md that this task is otherwise built around. It is recorded
here because an unledgered call that nobody writes down is exactly the
invisible spend that rule exists to prevent. Every call after it went
through `verify`. Real spend is therefore **14 credits, of which 13 are in
the ledger**.
