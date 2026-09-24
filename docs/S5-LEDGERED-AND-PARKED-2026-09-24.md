# S5: repointed, ledgered, parked — and the ledger tore

2026-09-24, lane 1. Four operator decisions of 2026-09-24 implemented in
`scripts/stage_s5_verify.py`, plus one production incident the fourth of them
uncovered within twenty minutes of going live.

**READ §5 FIRST IF YOU ARE PICKING THIS UP COLD.** The production spend ledger
is currently UNREADABLE, every paid call for `productive` is being refused
system-wide as a result, and the one-line repair is written out below but was
blocked by the permission classifier and needs the operator.

---

## 1. THE INPUT NOW POINTS AT THE FUNNEL

`stage_s5_verify.py` read `work/stage/s3-icp.jsonl` — the 2026-09-21 S3 pass,
which carries verdict `out` on 15,642 domains the 09-23 amendment moved to
`in`, with `mx: null` on every one of them.

    input                                          eligible domains   pending
    s3-icp.jsonl (09-21)                                      4,869       668
    s3-icp-amended-PRODUCTIVE-2026-09-07.jsonl                5,815         —
    mx-amended-PRODUCTIVE-2026-09-07.jsonl   <- new default   18,955    17,661

**Only the MX file is read, and that matters.** The operator's decision names
an amended *pair*, and the ICP-amended file is the wrong half of it on its
own: eligibility needs `verdict`, `email_channel` and `mx` on one row, and the
ICP-amended file still has `mx` null on the same 15,642 rows. It yields 5,815
domains, not 18,955. `mx-amended-...` is that same amended set after the MX
pass filled the two missing columns in.

`--s3` still names another file; the superseded 09-21 pass stays reachable
because comparing against it is how the amendment is checked.

Pending is 17,661 rather than the ~17,981 in the decision because 400
addresses were bought this afternoon, 20 more in the bounded arm below, and
because the source CSV is now de-duplicated — see §3.

## 2. K STAYS AT 8, AND THE LEDGER DID NOT MOVE IT

The measurement table is commit `5b1b2db3`'s, three arms of 100 real addresses
on this estate: K=3 → 0.268 addr/s, K=8 → 1.105, K=16 → 1.759, both verifiers
answering on 400 of 400 and no throttling signature anywhere. That commit had
already moved the default from 3 to 8; ContactOut's 60/min, which K=3 was
sized against, belongs to a provider `policy_for(config)` does not route to —
this client is `primary: deliverable / secondary: reoon`.

K=8 stays the default for the reason that commit gives and this run did not
disturb: **Reoon is not what decides it.** One Reoon call per contact puts K=8
at ~1.1/sec against the operator-stated 4/sec, and K=16 at 1.76/sec, both
inside it. Deliverable decides it, Deliverable's limit is documented NOWHERE —
not in `src/providers/deliverable.py`, explicitly UNKNOWN at
`docs/PERF-LATENCY-MODEL-2026-09-18.md:266` — and K=16 buys 59% for twice the
pressure on the provider nobody has a number for. "A clean run at K is not
permission to run at 2K." K=16 is measured clean and is available with
`--workers 16`.

**What this run adds is the re-confirmation the ledger wiring required.**
Routing every call through `spendledger` puts a whole-file read and parse in
front of each one, which did not exist when the table was measured and gets
slower as the ledger grows. Measured live at K=8 over 968 addresses:

    minute  3    4    5    6    7    8    9   10   11   12   13   14
    addr/s 1.32 1.19 1.13 1.09 1.13 1.20 1.17 1.14 1.12 1.12 1.10 1.06

Steady state ~1.12 addr/s against the 1.105 measured before the ledger
existed. **The ledger costs nothing measurable.** (The run's headline 0.80
addr/s is the whole-run average and is depressed by the six minutes it spent
refusing after §5 — the honest rate at K=8 is the table above.)

## 3. RETRY ONCE, THEN PARK

`RETRYABLE` was written for one throttled run in September and had no end to
it: an address whose last answer is retryable is un-settled, so **every** later
pass buys it again, and the pass after that, for ever. 23.5% of the 11,417
journal rows carried a retryable reason; on the clean un-throttled arms of this
afternoon the rate was 45.5%, and on this run's 988 fresh rows it was 29.6%.

New rule, `MAX_ATTEMPTS = 2`: one retry, then the address parks. A parked row
is not bought again and carries its own `parked_reason` saying so. Parking is
a spend decision about asking again, **not** a verification decision about the
address — `state` and `reason` still say it is held, never invalid.

Measured on the journal as it stands:

    unique addresses in the journal        10,185
    re-bought by EVERY pass, old rule         951
    re-bought by the next pass, new rule      867
    parked, out of the re-buy loop             84

84 is the standing backlog the rule clears at once. The forward-looking number
is the larger one: of the 988 addresses bought tonight, **292 are retryable**,
and under the old rule every one of them was a purchase repeated on every
future pass without limit. Each now gets exactly one more ask.

A row that `verify` refused to spend on — a ceiling, a per-contact cap —
carries `stopped` and is neither settled nor counted as an attempt. A budget
refusal is not evidence about an address and must not park one.

**Also stopped: the within-run double-buy.** The source CSV repeats 376
addresses among the 26,628 on eligible domains. Each repeat was its own
`contact` dict, so `verify`'s "already have this one" could not see it and a
single pass bought the same address twice. `contacts_for` now de-duplicates on
the key the journal is keyed by.

## 4. EVERY CALL IS NOW LEDGERED, AND THE TWO COUNTS AGREE

`verification.verify` gates **both** ledgers and every event behind
`if rec is not None`, and this script passed no `rec`. So the single most
expensive stage in the funnel was the one stage the spend audit could not see.

`ledger_record(contact)` is the carrier — one per contact, never shared, since
`events.record` scans a record's whole event list to de-duplicate and a shared
record would turn a linear pass quadratic. It carries `client`, which is what
`spendledger` scopes by and what `check()` refuses to proceed without.

**The proof is two independent counts of the same spend.** The runner totals
what the per-record waterfall ledgers say it bought; the spend ledger is a
separate file written per call. Tonight:

    runner's own count (waterfall, per address)     1,957 credits
    spend-ledger rows, productive, verification     1,956 readable + 1 torn
                                                  = 1,957

Exact agreement. Before this change the same 988 addresses would have written
**zero** ledger rows. `tests/test_every_s5_verification_reaches_the_spend_ledger.py`
pins it by counting the runner's provider calls against the ledger rows rather
than by grepping the source; with `rec=rec` removed it reports "4 calls and 0
ledger rows", which is the defect exactly.

**The cost actually incurred is 1,957 credits** over 988 addresses — 40 in a
bounded 20-address arm, 1,917 in the pass that followed. Not the ~35,000 in
the decision, for the two reasons in §5 and §6.

## 5. THE INCIDENT: A TORN LEDGER ROW, AND EVERY LATER CALL REFUSED

Twenty minutes in, at 1,957 rows, one append **tore**. The file kept a
complete row and then an orphaned eleven-byte tail, `id": null}`, whose own
head is gone. `spendledger.record` was a bare `open(path, "a")` + `write`,
which is atomic only by luck, and eight workers were appending to it twice per
contact.

**What it cost is the whole argument for fixing the writer rather than the
reader.** `load()` refuses an unreadable ledger instead of reading it as empty
— deliberately, because a spend control that opens when its own state is
damaged fails exactly when something is already wrong — and `check()` reads
the ledger before every paid call. So one torn line refused every subsequent
verification, the run bought nothing more, and 16,673 addresses went unasked.
**The guard behaved correctly and is not to be softened.** The run ended
clean, wrote no verdict it had not bought, and lost nothing but time.

### Fixed here

- `src/spendledger.py` — `record` now appends under `store.lock`. Cross-process
  rather than a `threading.Lock`, because the enrich loops, the monitors and
  the staging runners bill the same client from different processes and an
  in-process lock would have looked like a fix while leaving that race intact.
- `src/store.py` — `lock()` treated `PermissionError` as a fault. On Windows an
  exclusive create against a lock file another handle has just unlinked returns
  EACCES rather than EEXIST while the delete is pending, so under real
  contention the lock raised straight through its caller instead of waiting its
  turn. Found immediately at eight workers; never seen in two weeks of the
  single-writer queue path. It is contention and is now retried. Both paths
  still end with nothing written, so the guard is unchanged.
- `tests/test_two_writers_cannot_tear_the_spend_ledger.py` pins all three: the
  held lock blocks an append, many concurrent writers leave a readable ledger,
  and an unreadable ledger still refuses spend.

### NOT fixed — needs the operator

**`work/spend-ledger.jsonl` is still unreadable, and every paid call for
`productive` is refused system-wide until it is repaired.** Repairing it means
rewriting a production state file, which the permission classifier blocked
three times; that is destructive data mutation and is the operator's call
rather than mine.

A byte-identical backup was taken first and is at
`work/spend-ledger.jsonl.pre-repair-2026-09-24` (571,311 bytes).

The repair is one line. In `work/spend-ledger.jsonl` there is exactly one line
that is not JSON:

    id": null}

**Replace it — do not delete it.** The runner counted 1,957 credits from its
own waterfall ledgers and the file holds 1,956 readable rows, so the torn row
is a real purchase whose head was lost. Deleting it makes the ledger
under-report a real bill by one credit, and under-report is the dangerous
direction: `check()` reads this file to refuse the NEXT call, so a missing
credit is a ceiling that passes spend it should have refused. It is `reoon`
rather than `deliverable` because deliverable's rows are 174 bytes and reoon's
are 162, and the 989 readable deliverable rows already account for every
deliverable call.

    {"at": "2026-09-24T19:20:19+00:00", "day": "2026-09-24", "client":
     "productive", "provider": "reoon", "call": "reoon-verify",
     "expected_cost": 1, "run_id": null, "repaired": "torn write
     2026-09-24T19:20:19Z; head lost to a concurrent append"}

(one line, no wrapping). Then `py -3 -m src.spendledger --client productive`
should read it without raising and report **2,119 committed today** and
**4,159 in total** against the declared 5,000 and 50,000 — which leaves 2,881
credits of headroom today, about 1,450 more addresses.

## 6. THE SPEND THAT WAS APPROVED AND THE CEILING THAT IS DECLARED

The operator approved ~35,000 credits. `config/clients/productive.yaml`
declares:

    per_day                   5,000
    per_run                   2,000     <- NOT enforced by spendledger.check
    total                    50,000
    per_provider_per_day      none

`spendledger.check` enforces `per_day` and `total` only. **At the declared
5,000/day the approved 35,000 is at least seven days of work, not one night** —
and the backlog's own arithmetic is 17,661 addresses at ~1.98 credits each,
about 35,000 credits, which agrees with the decision and not with the ceiling.

I did not raise `per_day`. A declared ceiling is the client's, not an
engineering default, and raising one to seven times its value to fit a night's
plan is exactly the "irreversible external action — real credit spend" that
the standing rules say to ask about. The runner now prints both the ceilings
and what has been committed before it buys anything, and halts cleanly when
the durable ceiling refuses, recording each refused address as `stopped` so
none of them is mistaken for a verdict.

**The open decision for the operator is which of the two moves**: raise
`per_day` to match the approval, or run the backlog across seven or more
nights at the declared ceiling. Nothing else blocks it.

## 7. WHERE THE BACKLOG STANDS

    eligible domains (amended)                     18,955
    unique contacts on them                        26,252
    settled or parked in the journal                9,318
    still to verify                                16,934
    of tonight's 988:   verified 472 · held 370 · accept_all 108
                        invalid 20 · unknown 18

Roughly 48% verify, which matches every previous arm. The next pass, once the
ledger is readable, resumes where this one stopped and re-buys nothing it
already holds.

## 8. ONE MORE THING WORTH KEEPING

`scripts/stage_s5_verify.py` resolved its stage files from the directory the
script lives in. `work/` is gitignored, so every git worktree carries its own
nearly-empty copy — and a run from a worktree read an empty stage and printed a
clean zero rather than failing. The paths now derive from
`store.queue_path()`, which is the override the rest of the system already
moves together and which `spendledger.path()` already followed. Pointing
`QUEUE` at a workspace now moves queue, spend ledger and stage together, and
leaves no file behind still reading the checkout.
