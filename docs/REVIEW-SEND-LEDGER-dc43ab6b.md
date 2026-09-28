# INDEPENDENT REVIEW — SEND LEDGER INGESTION — `dc43ab6b`

**Branch head reviewed: `dc43ab6bf1ea4a2766dfa643bbae288783260f0e`**
(`origin/task-send-ledger-ingest`, 2 commits: `32d211c3`, `dc43ab6b`).
Compared against `origin/master` = `ffbf4fba4c26e5bc8febc58e520f176be37a9ddf`.
Merge base = `4b1fb0c6bfc7dac2a00a1b91b4fd5f867d30f606`.

Reviewer: independent, own worktree, branch `review-send-ledger`.
Nothing was applied, merged, or pushed to the branch under review.

---

## 0. VERDICT

### DO NOT APPLY

**Blocking reason.** `confirm_email_touches` now makes an **unconditional
provider read** that its pre-existing test module does not patch. The result
is **15 new ERRORs** in
`tests/test_the_send_is_recorded_once_and_by_the_provider.py` — the module
that guards the exact contract this change touches, and a module that was
**green on master**. Per gate 7, a new failure blocks. Details in §3.

The same defect has a second and worse face: in any environment that *does*
have `BISON_KEY`, those 15 tests do not error — they silently make **live GET
calls to the real EmailBison from a unit test**. The branch's own new test
file warns about precisely this ("unpatched, the step resolver would reach the
real EmailBison from a unit test"), patches it in its own fixtures, and the
pre-existing module was never brought along.

This is a small, well-understood fix — patch `bison.sequence_steps` in that
module's harness, or have `email_step_ordinals` degrade rather than raise. But
it must be fixed, the suite re-measured, and the review re-run before the
ingestion is applied to production state.

**Everything else about this change is sound, and much of it is excellent.**
§2 and §4 record what I verified and could not break, because that work should
not have to be redone: provider writes are genuinely 0, the pagination fix is
right, the failure path is a real property, the step resolution is correct and
unclamped, and production state is untouched. The change is close. It is not
ready.

Two review gates are **VOID** and must be re-run — one of them because my own
instructions contaminated it. See §7. I am not counting either as a pass.

---

## 1. WHAT THIS CHANGE IS

Four files, and the branch's own diff is small and entirely on-task:

    docs/SEND-LEDGER-INGEST-2026-09-28.md                        +551
    src/leadobserve.py                                           +293 -15
    src/replywatch.py                                             +55
    tests/test_a_provider_confirmed_send_reaches_the_ledger.py   +599

    CLAIM        The branch changes only those four files.
    AUTHORITY    `git diff --stat 4b1fb0c6 dc43ab6b`.
    MEASURED AT  2026-09-28.
    STATE        VERIFIED

**A two-dot diff against master is misleading and should not be used to judge
this branch.** `git diff ffbf4fba dc43ab6b` shows ~14,555 deletions across 39
files. That is an artifact: the branch forks at `4b1fb0c6` and is **34 commits
behind master**. Those deletions are master's own later work, not reverts
authored here.

    CLAIM        Merging this branch reverts nothing on master.
    AUTHORITY    `git merge-tree --write-tree ffbf4fba dc43ab6b` produced a
                 tree with no conflict section; and
                 `git log 4b1fb0c6..ffbf4fba -- src/leadobserve.py
                 src/replywatch.py` is EMPTY — master never touched either
                 file after the fork.
    MEASURED AT  2026-09-28.
    STATE        VERIFIED

---

## 2. SCOPE DRIFT — specifically checked, and clean

    CLAIM        Nothing in this branch touches the killswitch gates,
                 `copylint._traces`, or `packfacts` claim-licensing.
    AUTHORITY    `git diff 4b1fb0c6 dc43ab6b` grepped case-insensitively for
                 `killswitch|copylint|_traces|packfacts|claim.licens` —
                 zero hits; and the changed-file list is the four above.
    MEASURED AT  2026-09-28.
    STATE        VERIFIED

Every changed line answers to this task. No unrelated edits, no opportunistic
refactors, no silent reverts.

---

## 3. THE BLOCKER

### What happens

`confirm_email_touches` gained one line, before the row loop:

    rows = scheduled_rows(campaign_id)
    ordinals = email_step_ordinals(campaign_id)      # <- new, unconditional

`email_step_ordinals` calls `bison.sequence_steps(campaign_id)` whenever its
`steps` argument is None, which is always on this path. That is a **second
provider route**, additional to `scheduled_emails`, reached on every call.

`tests/test_the_send_is_recorded_once_and_by_the_provider.py` patches
`bison.scheduled_emails` in five places and **never patches
`bison.sequence_steps`**:

    CLAIM        That module contains zero references to `sequence_steps`.
    AUTHORITY    `git show dc43ab6b:tests/test_the_send_is_recorded_once_and_
                 by_the_provider.py | grep -c sequence_steps` -> 0.
    MEASURED AT  2026-09-28.
    STATE        VERIFIED

So every test in it that reaches `confirm_email_touches` now walks into the
real credential path:

    Traceback (most recent call last):
      tests/test_the_send_is_recorded_once_and_by_the_provider.py:181
        out = leadobserve.confirm_email_touches(CAMPAIGN, live=live)
      src/leadobserve.py:737   ordinals = email_step_ordinals(campaign_id)
      src/leadobserve.py:588   rows = bison.sequence_steps(campaign_id)
      src/providers/bison.py:1577  "GET", f"{base()}/campaigns/.../sequence-steps", headers()
      src/providers/bison.py:35    return {"Authorization": f"Bearer {key('BISON_KEY')}"}
      src/providers/__init__.py:122 raise MissingKey
    src.providers.MissingKey: no BISON_KEY in config/.env

### That it is new, and that it is the branch

    CLAIM        The module was GREEN on master.
    AUTHORITY    It contributes none of the 128 names in
                 `docs/state/SUITE-BASELINE-2026-09-26.txt` (grep -c -> 0).
    MEASURED AT  baseline 2026-09-26, master 0af11fcb.
    STATE        VERIFIED

    CLAIM        It produces 15 ERRORs at dc43ab6b, and not because of suite
                 ordering.
    AUTHORITY    Full suite in the clean worktree at dc43ab6b; AND standalone,
                 `python -m unittest discover -s tests -p
                 "test_the_send_is_recorded_once_and_by_the_provider.py"`
                 -> `Ran 24 tests ... FAILED (errors=15)`.
    MEASURED AT  2026-09-28.
    STATE        VERIFIED

    CLAIM        The worktree that produced that result really is dc43ab6b and
                 is otherwise unmodified.
    AUTHORITY    `git rev-parse HEAD` = dc43ab6b; `src/leadobserve.py` sha256
                 ba49fbeb…, 48,045 B, defining all four new functions;
                 `tests/base.py` on disk is the dc43ab6b blob (35,915 B LF ->
                 36,706 B CRLF); `git status --porcelain` lists no tracked
                 modification.
    MEASURED AT  2026-09-28.
    STATE        VERIFIED

### Why it matters more than a red test

With credentials absent the tests error. **With credentials present they would
pass while making live calls to the production EmailBison account** — 15 unit
tests, silently, on every suite run. The repository already treats that as a
defect class: the new test file's own `provider()` helper says
`sequence_steps` "is patched too, and it must be: unpatched, the step resolver
would reach the real EmailBison from a unit test." The author saw the hazard,
handled it in his own fixtures, and did not check the module next door that
exercises the same function.

### The fix

Either is small:

1. Patch `bison.sequence_steps` in that module's harness, as the new test file
   already does. Lowest risk, matches existing practice.
2. Make `email_step_ordinals` degrade instead of raising — return `{}` on a
   provider failure. This is arguably right anyway: the function's whole
   design is fail-closed, `{}` already means "no rung, leave every step None",
   and a sequence read that cannot happen is exactly that case. It would also
   mean a transient provider error downgrades step resolution rather than
   blinding the whole campaign.

Option 2 is the better change and the one I would ask for, because it makes
the failure mode consistent with the rest of the function. Either way the
suite must be re-measured against the baseline as sets afterwards.

---

## 4. WHAT I VERIFIED AND COULD NOT BREAK

Recorded so this work does not have to be repeated after the fix.

### 4a. The write path runs the guards

    CLAIM        Each write runs `refuse_evidence_loss` and
                 `refuse_history_loss` with the lock held across
                 read-modify-write.
    AUTHORITY    `src/store.py:307` `transaction()` takes `lock(timeout)`,
                 `load()`s, yields, then runs both guards before `_write`.
                 `confirm_email_touches` writes only inside
                 `with store.transaction() as held:`.
    MEASURED AT  2026-09-28.
    STATE        VERIFIED

### 4b. Provider writes = 0, with the interceptor proven to fire

The author's interceptor sits on `src.providers._transport`. That is the real
chokepoint: `providers.request()` (`:824`) dispatches through the `_transport`
module global (`:826`), and every bison write helper — `_post` (`:524`),
`_patch` (`:529`), `_put` (`:534`), `_delete` (`:539`) — calls `request()`.

I did not take his result on trust. I built my own interceptor and **fired it
deliberately as the first action**, because an interceptor that never triggers
is indistinguishable from a clean pass:

    selftest -> INTERCEPTOR: refused POST
                https://send.resonategroup.co/api/leads

    run                                      verbs
    dry reconcile of 493 (live provider)     GET 6,   POST 1 (self-test)
    forced-BLIND run 451+493 (live)          GET 3,   POST 1 (self-test)
    FULL ESTATE dry, 20 campaigns (live)     GET 225, POST 1 (self-test)

    CLAIM        Writes reaching the provider: 0.
    AUTHORITY    My own write-interceptor on `providers._transport`, proven to
                 fire, across three live runs.
    MEASURED AT  2026-09-28.
    STATE        VERIFIED

### 4c. The pagination fix is right, and a truncated read reports UNKNOWN

`scheduled_rows` now passes `cap=bison.CAMPAIGN_QUEUE_PAGE_CAP` (400) instead
of taking the 40-page default; campaign 491 is 45 pages. The property is the
refusal, not the number: `_paged` (`bison.py:840`) does
`if page >= cap: raise PartialInventory(...)`.

I forced a genuine `PartialInventory` by setting the cap to 1 against the
**live** provider, with 451 (1 page, readable) beside 493 (5 pages, not):

    PASS  run reports INCOMPLETE
    PASS  493 is named blind
    PASS  493 is UNKNOWN, not a count
    PASS  493 contributes NO zero to totals
    PASS  451 was still read despite 493 refusing

    CLAIM        An unreadable campaign becomes UNKNOWN, never zero, and one
                 refusal does not blind the rest of the estate.
    AUTHORITY    The forced-refusal run above, live provider.
    MEASURED AT  2026-09-28.
    STATE        VERIFIED

### 4d. `already_sent` is correct, not merely non-empty

Live provider, campaign 493: `recorded 24, waiting 40, unmatched 0, refused 0,
stepless 0, sequence_ordered True`, steps resolved `em1 x22, em2 x2`.

Fails closed where it should, tested directly:

    a step with no readable `order`     -> {}   whole sequence refused
    two steps sharing one `order`       -> {}   whole sequence refused
    a missing `order`                   -> {}   whole sequence refused
    a variant of nothing                -> dropped, no rung invented
    rung 4 or 5 against a 3-step record -> None, NOT clamped to em3

The no-clamp case matters most — clamping would report three confirmed touches
as one — and it is correct. An exact prior event still overrules the
positional rung (a record carrying `scheduled_email_id S9 -> em3` returns
`em3` even when the rung says `em1`).

### 4e. A mid-write failure cannot become a zero, and a retry cannot double-write

The transaction is **per row, inside the loop** — which is what let run 1
commit 346 rows of campaign 491 before its `PermissionError`. That is
recoverable because `events.record` is idempotent on `provider_event_id`
(`events.py:301`), and the id written here —
`emailbison:{campaign}:{scheduled_email_id}:{state}` — does **not** contain
`step`, so a re-run whose step resolution differs still dedupes.

I reproduced run 1 rather than trusting it: six rows, one campaign,
`PermissionError [WinError 5]` injected into the third `os.replace`:

    RUN 1 (failure injected)   complete False | blind 700 | state UNKNOWN
                               recorded reported 0 | events on disk 2
    RUN 2 (no failure)         complete True | recorded 4 | already 2
                               events on disk 6

    PASS  run 1 reports INCOMPLETE
    PASS  campaign 700 named blind
    PASS  blind campaign is UNKNOWN, not a count
    PASS  run 1 did NOT report the rows it had already written
    PASS  run 2 reports COMPLETE
    PASS  run 2 sees the earlier writes as ALREADY
    PASS  no event written twice: total on disk == one per row

    CLAIM        A campaign that fails mid-write becomes UNKNOWN, never a
                 zero; the run cannot be mistaken for complete; committed rows
                 are not double-written on retry.
    AUTHORITY    The injected-failure run above.
    MEASURED AT  2026-09-28.
    STATE        VERIFIED

That is the author's `346`-then-`already 346` pattern in miniature, with the
same proportions. The behaviour he observed by accident is reproducible on
demand, which makes it a property rather than an anecdote.

### 4f. The premise, independently confirmed

    records                                1,582
    events                                28,355
    events carrying scheduled_email_id         1
    provider-confirmed emailbison touches      1

    AUTHORITY    The byte-verified copy of `work/queue.jsonl`, parsed by a
                 fresh process.
    STATE        VERIFIED

The single `scheduled_email_id` independently justifies why the rung fallback
had to exist at all: the exact reconciliation path can answer for one event in
the entire store.

---

## 5. WHAT THE APPLY WOULD WRITE — measured, and larger than stated

Full-estate DRY reconciliation against the live provider, on the copy, 47s:

    campaigns read      20
    WOULD RECORD     1,082          <- not ~850
    already known        1
    waiting          1,737
    unmatched           68
    refused              0
    stepless             2          (501 and 506, one each)
    complete          True
    blind               []
    sequence_unordered  []

**The apply writes ~1,082 events, not ~850.** Not a discrepancy in the
author's work: his 850 counts confirmed *touches* (`push_marked`), while
`recorded` also carries the bounce and stop states `EVENT_FOR` maps. Expect
the larger number.

Cross-checks, all consistent with the writeup:

    491        rec 481 + wait 182 + unmatched 2 = the provider's 665 rows
               exactly; his own 491 re-run reported recorded 135 + already
               346 = 481. Identical.
    487        6 recorded — matches the OPERATOR's figure, not the doc's 5.
               487 was still sending when the doc was written.
    503/504/505  26 + 15 + 25 = 66 unmatched, exactly his 66. My other 2 are
               his 2 on 491.
    451        the single pre-existing touch, seen as `already 1`.

**A whole-estate READ costs 47 seconds.** So the ~45-minute estimate is almost
entirely write cost: 1,082 sequential transactions each rewriting the full
24 MB and ending in `os.replace`.

    CLAIM        F1 (negative sequence `order`, §6) is unreachable across the
                 WHOLE estate.
    AUTHORITY    `sequence_unordered: []` over all 20 campaigns — every
                 sequence orders cleanly, so no rung is negative anywhere.
    MEASURED AT  2026-09-28.
    STATE        VERIFIED

---

## 6. OTHER DEFECTS FOUND

### F1 — a negative provider `order` silently yields the WRONG step (latent)

`_step_of` guards the upper bound and not the lower:

    if rung > len(declared):
        return None
    return declared[rung - 1]

A negative rung is a **negative Python index**, so it selects a real step from
the end of the list instead of refusing:

    order = -1  ->  'em2'      (should refuse)
    order = -2  ->  'em1'      (should refuse)
    order =  0  ->  None       (correct — caught by `if not rung`)

This contradicts the function's own "IT FAILS CLOSED" docstring and produces
the harm that docstring names: attributing a real message to the wrong rung,
putting *"as I mentioned"* in front of a prospect over words they never
received. No test covers a negative order. Verified unreachable on today's
estate (§5), so latent — but it is a one-line fix:

    if rung < 1 or rung > len(declared):
        return None

### F2 — a malformed campaign binding vanishes, and the docstring denies it

`claimed_email_campaigns` drops a `bison_campaign_id` that will not parse
(`except (TypeError, ValueError): continue`), while its docstring claims *"It
is left out and reported by the caller's `blind` list."* The caller **cannot**
do that — the function returns only the good ids, so a corrupt binding is
invisible and the run still reports `complete: true`. An UNKNOWN becoming
clean.

Verified not reachable today: all 67 rows of `work/campaigns.jsonl` parse to
20 usable integer bindings, 47 with no binding, **zero malformed**. Fix:
return the rejects so the caller can put them in `blind`.

### F3 — `--all-claimed --live` writes without `--confirm`

`--live` is documented as *"with --confirm, actually write the touches"*, but
the `--all-claimed` branch never consults `a.confirm`. Proven empirically by
stubbing the reconciler and observing the flag:

    --provider emailbison --all-claimed                    live=False  dry
    --provider emailbison --all-claimed --live             live=True   WOULD WRITE
    --provider emailbison --all-claimed --confirm --live   live=True   WOULD WRITE

An operator who omits `--confirm` expecting a dry run gets a live write of
~1,082 events. The documented apply command passes both, so it does not affect
the planned apply — but it is a foot-gun on the exact command that writes
production state.

### F4 — the fourth reader is still not pinned against cap drift

`tests/test_the_queue_cap_is_one_number.py` exists to stop readers disagreeing
about the queue cap, and pins `slackagentreadback` and
`scripts/hard_stop_check.py`. This branch adds a **fourth** reader,
`leadobserve.scheduled_rows`, and does not add it there. The branch's own
docstring says this reader was the fourth to get the cap wrong and that the
anti-drift test "never knew this reader existed". It still does not.

### F5 — `sends_complete: None` conflates "not applicable" with "failed"

`_reconcile_sends` returns `{}` for any non-EmailBison provider, so the
HeyReach status row reports `sends_complete: None` — a value the code's own
comment defines as "the reconciliation could not run at all". A reader cannot
distinguish "not applicable" from "it broke". Cosmetic; the behaviour is
correct and tested.

### F6 — the author's "production untouched" claim uses a weaker authority

§8 of the writeup gives AUTHORITY as **"mtime and size"**. The standard here
is content hash from a fresh process. I supplied that independently (§8) and
it agrees — but his own evidence could not have distinguished a same-size
rewrite.

### F7 — `refuse_production_write` does not guard production from a worktree
(PRE-EXISTING, not introduced here)

`src/store.py` sets `ROOT = abspath(dirname(store.py)/"..")`, and **both**
`queue_path()` and `PRODUCTION_WORK` (`:956`) are ROOT-relative. Measured from
this review's worktree with `QUEUE` unset:

    queue_path()     -> <worktree>/work/queue.jsonl      (does not exist)
    PRODUCTION_WORK  -> <worktree>/work
    guard covers the REAL production work/?   False

So the guard whose docstring says *"a test tried to write real client state"*
resolves against whichever tree the code is imported from, and covers nothing
when run from a worktree or copy. It removes a piece of false reassurance:
everything this task proved on a byte copy was safe **because a copy was
used**, not because the barrier would have caught a mistake. The same is true
of this review. Belongs in `docs/state/PROBLEM-REGISTER.md`.

---

## 7. TWO GATES ARE VOID

Recorded plainly, because a void gate must not be read as a pass.

### 7a. The mutation gate — VOID, tree was not the commit under review

Nine mutations were re-run for this review and reported all nine KILLED. **I
am withdrawing that result.** The harness tree was not `dc43ab6b`:

    src/leadobserve.py in that tree   34,260 B
      defines email_step_ordinals        NO
      defines declared_email_steps       NO
      defines confirm_all_email_touches  NO
      defines claimed_email_campaigns    NO

    the same file at dc43ab6b         48,045 B, all four present

    CLAIM        The mutation harness scored nine mutations against a tree
                 whose `leadobserve.py` contained none of the four functions
                 under review.
    AUTHORITY    Direct hash and `def` comparison of both trees; 18 files
                 differ after CRLF normalisation and 3 master-only files are
                 present.
    MEASURED AT  2026-09-28.
    STATE        VERIFIED — the gate is VOID, not failed.

The claimed byte-identical restore was also false. This is exactly the
repository's own "a mutation that never applied" defect one level up: the
restore was taken from the wrong source, so the tree drifted to master
mid-run. It is being re-run against a tree proven by hash before any mutation
is applied. **Until that lands, the mutation evidence for this branch is
UNPROVEN.**

It is also why my earlier reading of the blocker was briefly wrong: that tree
"passed" the send module simply because its `leadobserve.py` had no
`email_step_ordinals` to call.

### 7b. The suite's full NEW set — the baseline cannot attribute it

The gate run gave 147 failing names against the 128-name baseline: 117
unchanged, **30 NEW**, 11 no longer failing. Of those 30, the 15 in
`test_the_send_is_recorded_once_and_by_the_provider` are **proven
branch-caused** (§3) and are sufficient to block.

**The other 15 cannot be attributed to this branch, and the baseline is the
wrong instrument for trying.**

    CLAIM        `docs/state/SUITE-BASELINE-2026-09-26.txt` is not a
                 same-commit reference for dc43ab6b.
    AUTHORITY    It was measured at master 0af11fcb. dc43ab6b carries 675
                 test files against that commit's 620 — 55 added, 0 removed —
                 and the suite runs 13,614 tests against the baseline's
                 12,737.
    MEASURED AT  2026-09-28.
    STATE        VERIFIED

So a NEW name against the 128 can mean three different things — this branch
broke it, one of master's 34 later commits broke it, or the test did not exist
at 0af11fcb — and the baseline cannot separate them. **The branch forks at
`4b1fb0c6` and contains none of master's 34 commits**, so the only reference
that isolates its effect is its own merge base. A second suite run at
`4b1fb0c6` is in progress; `dc43ab6b` minus `4b1fb0c6`, as sets, is this
branch's true contribution. That is the number that should gate the apply,
and the 128-baseline diff is secondary context.

Known non-branch causes already identified in the 30:

    7   test_fixture_hygiene — MY contamination. My scratch directory held a
        second copy of `src/` and `tests/` plus an `estate_dry.json` of real
        account data from a live provider read, and that test enumerates with
        `git ls-files --others`, so untracked files are in scope BY DESIGN.
        Removed. Part of this cluster may be genuine, but it names files
        (`test_changing_an_approved_fact_changes_the_output.py`,
        `test_task400_rework2.py`) that are not in this branch's 4-file diff —
        they arrived with master's later commits.
    5   FileNotFoundError [WinError 2] from `subprocess.run(["bash", …])` and
        `(["grep", …])` — 4x test_provision_survives_its_own_firewall plus
        test_waterfall_order's xai check. An artifact of launching the suite
        through a PowerShell parent whose PATH lacks Git Bash. Not a branch
        defect.
    1   test_an_offer_cannot_be_invented.TestApprovalRefusal — the offer
        ladder is TASK-425, merged on MASTER at 439aa169. dc43ab6b does not
        contain it.

That leaves roughly two assertion failures with no environmental explanation
yet, including
`test_the_cadence_reacts_to_what_the_prospect_did.ThePlannerReadsTheBranch.test_the_meeting_reaches_the_send_gate_too`
(`None != 'blocked:company_paused'`). The merge-base run will settle whether
they belong to this branch. **I am not counting them against it until it
does, and neither should the operator.**

A second measurement problem, worth keeping: the baseline is only comparable
under its own *conditions*, not just its commit. Pointing state at a populated
24 MB queue made one module (`test_the_client_scope_under_attack`) take over
30 minutes against 117 seconds with default state, because it re-reads the
queue per tool per crafted argument. The baseline claims all 12,737 tests in
2,152s and that module passed there, so the baseline was measured with an
unpopulated `work/`. `tests/base.py` isolates per test via
`store.use_directory(tmp)`, so the suite is designed to run without external
state. The gate runs therefore use the default environment. My original
instruction to point the suite at a copy of production data was wrong: it
conflated "do not write production state" with "point the suite at production
data".

### 7c. Two corrections to the brief's own premises

    CLAIM        `test_a_resume_leaves_a_ledger_row` is NO LONGER red.
    AUTHORITY    The suite run at dc43ab6b — its whole module is green, and
                 its 5 names are 5 of the 11 that no longer fail.
    MEASURED AT  2026-09-28.
    STATE        VERIFIED

The baseline header's load-bearing note that those three tests are
PRE-EXISTING RED, and must not be read as new after a change, is out of date.
They pass now.

Separately: long jobs launched through background shell tasks in this
environment are being reaped at 1-4 minutes with no traceback. Three suite
attempts died that way before one launched detached ran to completion in 31
minutes. Anyone timing a suite here should not trust a short, silent death as
a result — it is the launcher, not the suite.

---

## 8. PRODUCTION STATE — UNCHANGED, BY CONTENT HASH

Fresh process, at review start and again at review end:

    work/queue.jsonl        24,033,849 B
      sha256 dd984f8a9e0d85082c36bd7912d7798c926867085342ca4096da069be08caee2
      UNCHANGED across the entire review
      mtime 2026-09-28T10:38:18Z — identical to the value the author recorded,
      so the ingestion has NOT been applied to production

    work/campaigns.jsonl       114,909 B
      sha256 00b6f103bbdb469f25a7977665e4e08339f30f2b827d9e2a3c82be560d4c5931
      UNCHANGED across the review

`campaigns.jsonl` DID change since the author measured it (114,171 ->
114,909 B, 2026-09-26T19:05:08Z -> 2026-09-28T12:54:46Z) — the operator's own
pausing of 487/489/493, not this branch. It matters only because that file
selects which campaigns are ingested, so I checked for drift:

    CLAIM        The claimed-campaign set is unchanged since validation.
    AUTHORITY    `claimed_email_campaigns()` over current state returns
                 exactly the author's 20: 451, 481, 484, 485, 487, 489, 491,
                 492, 493, 494, 495, 496, 497, 498, 500, 501, 503, 504, 505,
                 506.
    STATE        VERIFIED

The copy's `queue.jsonl` hash was also unchanged after every dry run,
including the full-estate one — so `live=False` is genuinely dry at estate
scale.

---

## 9. WHEN THE BLOCKER IS FIXED — the preconditions still stand

These are not code defects and they do not go away with the fix. They are the
difference between a clean apply and a repeat of run 1 on production state.

    CLAIM        24 production loops are running: digest_loop (300s),
                 weekly_report_loop (300s), reply_watch_loop (300s),
                 slack_agent_loop, slack_followup_loop (60s),
                 heyreach_watch_loop (300s) and TWENTY bison_watch_loop
                 processes (180s each).
    AUTHORITY    `Get-CimInstance Win32_Process` — started 2026-09-24/25.
    STATE        VERIFIED

    CLAIM        `store.load()` takes NO lock.
    AUTHORITY    `src/store.py:840` — `load()` calls `_current_records()`
                 directly; there is no `lock()` on the read path.
    STATE        VERIFIED

    CLAIM        Every transaction ends in `os.replace`.
    AUTHORITY    `src/store.py:371` and `:1013`.
    STATE        VERIFIED

On Windows `os.replace` fails with `PermissionError [WinError 5]` while
another process holds the target open. The apply performs ~1,082 sequential
whole-file rewrites over ~45 minutes against two dozen unsynchronised readers.
**This is not a hypothesis — it is what happened in run 1**, where 491 went
BLIND after 346 rows were already written, caused by the author's own
concurrent readers. The production loops are more numerous and more frequent
than what broke it. And a partial apply leaves the digest loop running, free
to post *"Confirmed sends: …"* to Slack within five minutes from a
half-ingested ledger.

### Mandatory, when the time comes

1. **Stop the loops** — at minimum `digest_loop.py`,
   `weekly_report_loop.py`, `reply_watch_loop.py` and all 20
   `bison_watch_loop.py`. The digest and weekly loops are what make a partial
   apply client-visible; the bison watchers are what make it likely.
2. **Back up `work/queue.jsonl`** and record its sha256 (§8) so a bad apply is
   revertible and provably so.
3. **Require `complete: true` and an EMPTY `blind` list** before restarting
   anything. A non-zero exit says the same thing.

Then restart the loops. Per *a merge is not a deploy*: `reply_watch_loop.py`
has run since 2026-09-25 and imports at start, so the wiring in `replywatch`
does nothing until that process is restarted.

### One standing-cost decision, separate from the apply

Once `reply_watch_loop` restarts, **every 300-second tick runs a full
reconciliation of all 20 campaigns** — there is no cursor or high-water mark;
it re-walks all ~2,888 queue rows every time. My full-estate run cost 225
GETs, so roughly 65,000 provider GETs a day, sustained, attached to a poll
that is otherwise a cheap high-water-mark feed. Correct, but a much larger
standing load than what it hangs off. Worth deciding deliberately rather than
meeting it in a rate-limit error.

---

## 10. WHAT I ATTACKED

So the verdict reads as a result rather than an absence of effort.

    the two-dot diff        looked like a 14,555-line revert of master. Fork
                            artifact; trial merge clean; master never touched
                            either file.
    the write path          hoped for a missing history-loss guard.
                            `transaction()` runs both under the lock.
    partial-write recovery  hoped a retry would double-record. It cannot.
                            Then injected run 1's own PermissionError and
                            confirmed UNKNOWN, incomplete, and no double write.
    the interceptor         hoped it sat on `bison` rather than the transport,
                            or never fired. It is on `providers._transport`;
                            re-proved with my own, fired deliberately, three
                            live runs.
    the cap                 hoped the new cap could truncate. `_paged` raises;
                            forced it live and got UNKNOWN.
    step resolution         found F1, a real fail-open on negative order, then
                            could not make it reachable — `sequence_unordered`
                            is empty across all 20 campaigns.
    campaign selection      found F2, a real docstring-versus-behaviour gap,
                            then could not make it reachable either: zero
                            malformed bindings in 67 rows.
    the estate              checked the claimed set had not drifted since
                            validation. It has not.
    dry mode                ran the real path live at estate scale and hashed
                            the copy before and after. Unchanged.
    the test module next    THIS is where it broke. Asked what else calls
      door                  `confirm_email_touches` and whether the new
                            provider read is patched there. It is not.

The last line is the whole finding. Everything the change does to the ledger
is right; what it does to the module that was already guarding the ledger is
not.

---

## 11. RECOMMENDATIONS, IN ORDER

1. **Fix the blocker** (§3). Prefer making `email_step_ordinals` degrade to
   `{}` on a provider failure over patching the test, because it also removes
   the "unit tests hit the live provider" face of the defect.
2. **Re-measure the suite** against the 128 baseline names as SETS, in the
   default environment, in a tree with no extra copies in it.
3. **Re-run the mutation gate** against a tree proven by hash first (§7a).
4. Fix F1 (one line) and F2, and add a negative-order test beside the existing
   no-clamp test.
5. Make `--all-claimed` honour `--confirm` (F3).
6. Add `leadobserve.scheduled_rows` to
   `tests/test_the_queue_cap_is_one_number.py` (F4); report a not-applicable
   reconciliation as something other than `None` (F5).
7. File F7 in `docs/state/PROBLEM-REGISTER.md` — the production-write barrier
   does not cover a worktree.
8. Decide whether a full 20-campaign reconciliation belongs on a 300-second
   tick (§9).

Items 1–3 gate the apply. The rest do not.
