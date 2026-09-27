PRIORITY: READ FIRST

# PRODUCTION HANDOFF — 2026-09-27 afternoon

**Read this, then `docs/OPERATING-MODE.md`.** Supersedes the 2026-09-27 morning
handoff on everything it covers. That morning handoff was written at ~96-98% of the
previous account's weekly limit; this session ran on a fresh full allowance.

**Nothing was sent. No campaign was activated, resumed, paused, enrolled or
attached. No provider-changing test ran. Provider writes = 0.** Freeze stands.
487, 489 and 493 untouched.

## 0. JEZIK I FORMAT — novo trajno pravilo

Operator updates i statusi idu na **hrvatskom**; tehnički identifikatori (imena
testova, putanje, SHA-ovi, imena taskova) ostaju kakvi su u kodu. Odluke se traže
**jedna po jedna** u formatu **🔴 TREBAM TVOJU ODLUKU**, svaka s preporukom.
Vidi `docs/OPERATING-MODE.md`, sekcija "KOMUNIKACIJA S OPERATEROM". Ta je sekcija
izrijekom označena kao Claudeovo čitanje operaterove upute, ne citat — operater je
ispravlja ako je preširoka.

## 1. MASTER SHA

    origin/master   50b55c92        (local == origin, verified)

Derive it, never trust this line: `git fetch origin && git rev-parse master origin/master`.

## 2. TRIJAŽA — the headline result

**Nijedan guard nije BROKEN. Svih pet je UNPROVEN, svih pet iz istog razloga.**
Full per-row table: `docs/SUITE-TRIAGE-2026-09-27.md`.

    REGRESSION        87
    NEW_COVERAGE      19
    set diff          128 - 6 + 106 = 228, reconciles exactly

**TASK-372's 68/38 split was wrong.** It excused 19 tests as "new classes" that do
not exist. The triage AST-parsed every module at `0af11fcb`, checking each method
inside its OWN class so a same-named method elsewhere could not read as a phantom
regression: all 87 had both class and method present at baseline.

**71 of the 87 come from ONE commit: `6fa49014`** ("TASK-321 PARTIAL: sequencegate
is genuinely wired into bisonfactory"). `sequencegate.check` takes five inputs;
`bisonfactory.py:668` passes one. Missing: `qualification` (so `qualified` refuses),
`facts` (so `claims_supported` refuses any specific claim), `capability`,
`batch_capabilities`. Therefore **`bisonfactory.stage()` has been unable to succeed
for ANY input since 2026-09-26 15:27.** It fails CLOSED — nothing reached a provider
— but no campaign can be staged and the dry run would stage nothing.

Bisect evidence: killswitch module `OK` at `35dd8cbd`, `FAILED (2 failures, 3
errors)` at `6fa49014`, identical at HEAD. Largest affected module 7 -> 31 errors at
the same commit.

A further **12 of the 106 were Claude's own `ops_channel` regression**, fixed at
`156110f7`, verified green across 122 tests. Four remain individually attributed.

| Guard | Verdict | Proof restored? |
|---|---|---|
| killswitch | UNPROVEN | YES, 5/5, mutation works (tripped 0 leads, bypassed 2) |
| crash-restart idempotency | UNPROVEN | YES, 9/9 |
| staging collision refusal | UNPROVEN | NO, same blocker, 7 unchanged |
| copylint on send path | UNPROVEN | PARTIAL, exposes the `facts` omission |
| approval is not a fact-check | UNPROVEN | NO, base class was outside agent scope |

**KILLSWITCH RADI.** `src/killswitch.py`, six layers on `sending.live`, absence
means off and is asserted, decision is pure code with no LLM, and **no write path
skips it** (verified at every direct write call site outside `src/providers/`;
the two apparent holes are closed). What was lost on 09-26 is the PROOF, not the
protection.

**But: `killswitch.workspace_state('productive')` returns `sending=True`.** The
killswitch is NOT tripped and would permit sending. What prevents an EmailBison
write right now is the freeze plus the `6fa49014` defect. Consider turning
`sending.live` off for productive while the slice is built — that is an open
operator decision, not done.

## 3. P0 STATES WITH BRANCH SHAs

    TASK-426  bison stage passes all five sequencegate inputs
              TODO on master. NOT STARTED. THE highest-value fix in the repo:
              one change unblocks 71 tests, restores five proofs, makes stage()
              functional. Scaffolding to delete lives on
              worktree-agent-a94e75e1ade513080 (35df734f).

    TASK-364  one canonical SequencePlan
              BLOCKED TWICE. Rework 2 brief is on master.
              Attempt 2 reviewed at 6d1bab12 (on qwen-worker-r9): the derivation
              runs BACKWARDS. canonical_contacts built from already-built leads
              (bisonfactory:517), plan from those (:519), real sequence built at
              :447, writer reads plan["sequence"] at :1966; same shape in
              heyreachfactory 1048 vs 599/604, writers at 665 and 1343. So plan and
              sequence can never disagree because one is generated from the other,
              and a consistency test passes by construction. Its tests were hasattr
              and source-text assertions, which CLAUDE.md forbids.
              Deliberately offered for reimplementation: a reviewed-and-rejected
              result should lose to a newer rework brief.

    TASK-400  generate.py is the real caller
              READY on worktree-agent-a88cf873fc4570da2 at 5c356b7d (pushed).
              Three blocked defects fixed and falsified by performed mutations.
              Found the defect nobody had: generate_campaign stamps the PLAN while
              refuse_dry_run_records reads the stamp off the RECORD, so all four
              refusals were INERT and tests passed only because they hand-set
              rec["generation_stamp"]. Also _adapt_plan_to_cadence had been deleted,
              so copy was generated and discarded and rec["cadence"] never written.
              Both fixed. Four refusal tests now assert behaviour and booby-trap the
              request seam so the refusal is proven to precede the network.
              Context gap: chose REFUSE LOUDLY for single-step regeneration rather
              than defaulting sender_identity, which would manufacture the
              empty-signature launch blocker.
              NOT MERGED: 9 errors in tests/test_generate.py stand, 7 of them the
              old-pipeline behaviours in section 7.

    TASK-372  suite baseline
              BLOCK. Measurement good, conclusion wrong: it proposed adopting 228
              as the merge gate, which would normalise 68 caught regressions.
              228 IS NEVER A BASELINE. Standing baseline remains
              docs/state/SUITE-BASELINE-2026-09-26.txt, 128 named failures.
              Commits 91a280e2 and 6fc77fb0, both still on qwen-worker-2-r9 and on
              origin — an orphaned-commit warning was checked and was false.
              Rework not yet written.

    TASK-425  one-account dry run with the causal matrix
              TODO on master, DEPENDS on 400, 364, 372. Cannot start: waits on
              safety guards proven, 400 PASS and 364 PASS.

    TASK-427  _check_offers validates only the SELECTED offer
              APPROVED AND UNBLOCKED by the operator. Not implemented.
              Why it matters: _check_offers (generate_campaign.py:191-198) iterates
              the ENTIRE library and raises on the first unapproved offer. A and B
              are approved; the six capability offers they compose are pending, so
              every live run for productive refuses at OFFER-PM-001. This was
              invisible until offers.load() was fixed, because a gate that never ran
              looked identical to a gate that passed.

    TASK-428  client evidence path + narrow hygiene allowance
              Operator decision recorded. Not implemented.

    TASK-423  failure taxonomy of the fifty's 37 non-passing leads (Qwen lane B)
    TASK-424  canonical task-state registry, DESIGN ONLY, returned exit=0 on
              qwen-worker-6-r9, NOT YET REVIEWED by Claude.

## 4. GLM VERDICTS — valid vs void

    TASK-401  verifies 364    VALID    BLOCK, 4 of 6 criteria. Accepted.
    TASK-402  verifies 391    VOID     names NO SHA anywhere, existence-only.
                                       Claude re-verified 391 independently: HOLDS.
    TASK-403  verifies 318    RETURNED DONE on qwen-worker-2-r9, unread
    TASK-404  verifies 397    VOID     cites 44ce1762, which
                                       `git branch -a --contains` places on NO
                                       branch; data 6 days stale; its own
                                       arithmetic does not reproduce. Re-verify.
    TASK-405  verifies 394    VOID     "COMMIT SHA: N/A". Its redundancy finding is
                                       accepted on independent grounds; 394 is now
                                       STATUS: BLOCKED / ABSORBED_BY: TASK-389.
    TASK-406  verifies 396    RETURNED unread
    TASK-407  verifies 399    VALID    master was the right target (report-only).
                                       Found one 399 claim CONFIRMED FALSE; the
                                       stale-SHA part is already fixed.
    TASK-408  verifies 319    RETURNED unread
    TASK-409  verifies 294    VALID    BLOCK, best-evidenced of the five.
                                       TASK-294 WAS NEVER IMPLEMENTED: its three
                                       artifacts exist on no ref
                                       (--diff-filter=A across all refs). So the
                                       per-lead research-pack QA that would catch
                                       the 50-of-71 wrong-company defect DOES NOT
                                       EXIST. 294 requeued.
    TASK-410  verifies 400    VOID     reported "400 still in TODO" at 12:13 while
                                       the work sat in REVIEW on qwen-worker-4-r9
                                       since 09:38 — it read master, not the branch.
                                       Brief corrected to require a named branch
                                       head SHA. Its BLOCKED branch stage is now
                                       treated as its returned verdict.

**Standing rule: a GLM verdict that does not name the branch head SHA it reviewed
is VOID and is re-verified. Three of five returned verdicts were void on
provenance.**

## 5. WHAT IS RUNNING WHERE

At handoff time: **claims held 0, ready depth 0, awaiting integration 138,
recoverable 9. No Claude subagent and no Qwen worker is running.** All five of this
session's subagents completed.

    ready depth today: 0 -> 25 after the scheduler fix merged, then drained to 0
    as workers moved tasks to REVIEW/DONE on branches.

**That drain is the real bottleneck and the next session must face it: 138 results
exist on branches and are unintegrated. Integration is the constraint, not worker
capacity.** The scheduler now says so out loud instead of hiding it.

All branches pushed and verified (local == origin):

    worktree-agent-a02758daf4735119a   3fad16fa   scheduler fix (MERGED to master)
    worktree-agent-a61927afe01ec9ccf   42114d2f   sequencegate enforcement (NOT merged)
    worktree-agent-a88cf873fc4570da2   5c356b7d   TASK-400 rework 2 (NOT merged)
    worktree-agent-a94e75e1ade513080   35df734f   triage + restored proofs (doc merged only)
    qwen-worker-r9 9006d488 · -2-r9 f03c74fc · -3-r9 402a0d30 · -4-r9 c242cdad
    qwen-worker-6-r9 b06aadfb · -7-r9 8db92715 · -9-r9 f1b9c357 · -11-r9 6ed30491
    qwen-worker-12-r9 c5a756d2

`ResonatePoolSweep` every 15 min and `pool_watchdog.sh` were alive through the
session. Five older CRITICALs (281, 328, 372, 387, 403) were reconciled from machine
evidence: 281 and 403 had completed (stale alerts), 372 completed, 328 and 387 were
dead runs and are now recoverable. Orphan poll-loop PID 26052 killed — it waited on
`scripts/suite_verdict.txt` when the convention is `work/suite_verdict.txt`.

## 6. BACKUP AND SLACK

**BACKUP — closed, and the earlier "no backup exists" claim was WRONG.** The host
job was always healthy; the STAGING step was missing, and because
`nightly-backup.sh` logs "nothing to do" and still ships a 13 KB state archive, a
completely healthy-looking nightly run produced no estate backup for ~40 hours.
Green log, missing data.

    resonate-prodwork-2026-09-27.tar.gz.age   93,238,875 B   11:46 UTC
    encrypted, off-host, round trip byte-identical, restore check
    missing 0 / unexpected 0 / CHANGED 0, plain copy deleted after, retention 7 kept

`scripts/stage_work_to_host.sh` tars the laptop's `work/` (544 MB, 546 files) into
`~/backup/work-<date>/` on the host 30 min before the 22:30 job. Windows scheduled
task **ResonateStageWorkToHost**, daily 22:00. Secrets are excluded BY TAR, not
filtered after — verified 545 of 546 files arrived with zero secret matches. Extract
goes to `.partial` and renames only on success, so the host job can never ship a
half-written estate. Duplicate empty `HOST_IPV4` removed from
`hosts/production.env`.

**SLACK — fixed and proven.** `slack.live()` read `os.environ` directly while every
credential arrives via `key()`, which loads `config/.env` at call time. Any process
that had not already called `key()` saw no token and `post()` refused. **That is why
five CRITICAL alerts never reached anybody.** The watchdog was working; the
transport was refusing. Fixed, falsified both ways.

Routing: `C0C34GCAR27` is `#resonate-notifications`, **RETIRED**. `C0C3C6MDN9L` is
`#resonate-os`, the operator room. Both confirmed by `conversations.info`.
`ops_channel()` honours a real non-retired ops channel, else falls back to the
status channel, and `RETIRED_CHANNELS` makes the retired id unreachable.
`tests/test_no_route_resolves_to_retired_channel.py` asserts on the RESOLVED ID.

## 7. OPEN DECISIONS, each with the default if unanswered

    🔴 1  copylint retry — a draft failing copylint must be regenerated.
          DEFAULT: MUST reproduce. TASK-400 does not merge without it.
    🔴 2  a bad draft is never stored.
          DEFAULT: MUST reproduce. Same defence as 1, different place.
    🔴 3  a model failure holds the record.
          DEFAULT: MUST reproduce. Passing silently with no copy is fail-open.
    🔴 4  an existing draft is not regenerated.
          DEFAULT: allow the change for UNAPPROVED drafts only. An approved or
          sent draft must never be overwritten, because regeneration after
          approval invalidates the approval hash.
    🔴 5  sending.live is ON for productive. Turn it off while the slice is built?
          DEFAULT: leave as is and rely on the freeze. Claude changes no provider
          or workspace state without explicit APPROVED.

The 7 `tests/test_generate.py` errors map to decisions 1-4; the count is 7 errors
across 4 behaviours, not 7 behaviours.

## 8. OFFERS

**OFFER-A-ECONOMIC-BUYER v2 and OFFER-B-OPERATIONS v2 are APPROVED** by Zvonimir,
2026-09-27, recorded on each record with `approved_by`, `approved_on` and
`approved_at_sha: a04574be`, and `approval_history` keeps the v1 approval with
`carried_forward: false`. `campaigns: []` on both — approval is not attachment.

Mechanism for both: **a walkthrough with a Productive AE that unlocks the premium
trial including Productive's AI features**, CLIENT_APPROVED, source "client
confirmation, Bruno, 2026-09-27". The self-serve 14 day trial is
`RECORDED_NOT_LICENSED_FOR_COPY`. Single CTA `https://productive.io/get-started/`.

**Two provenances that must never be collapsed:** the AI features page
(`evidence.productive_ai`, retrieved 2026-09-27, VERIFIED_PUBLIC) supports what each
feature DOES in its own words and nothing else — no figure, no percentage, no time
saved. It states **no AI pricing tier**, so the premium trial traces to Bruno's
confirmation ONLY and copy must never cite the page for it.

All twelve customer stories still have `page_text: null`, so **no case study,
customer name, figure or percentage is licensed** until TASK-365 stores page text.
Marble Engine, MCP Server, Expenses Autofill and AI Writing Tools are excluded and
their text is deliberately NOT stored, so a tracing lint cannot license them.

`messaging_rules` is on master but marked **`DATA_ONLY_NOT_YET_ENFORCED`**:
`sequencegate` does not read `step_objectives` on master yet. Enforcement exists on
`worktree-agent-a61927afe01ec9ccf` (`42114d2f`, 19 tests, five mutations each caught
by the intended test) and is NOT merged. It also fixed a real token-coincidence
licensing bug: "AI Time Tracking removes the need to think about admin ever again"
came back licensed because the feature name shares the word "time" with its own page
text — the same `_traces` defect as launch blocker 5.

## 9. THE FIRST THREE ACTIONS FOR THE NEXT SESSION

Per the operator's decision, the critical path is implemented by **Claude subagents
(Opus)**, each in its own worktree with one acceptance check. GLM still gives an
independent verdict against the branch head SHA; Claude may merge on a GLM PASS, or
after 45 minutes without one on its own verification PLUS a second Claude subagent's
review. Qwen stays at full capacity off the critical path.

1. **TASK-426** — `bisonfactory.stage()` passes all five `sequencegate.check`
   inputs. One fix unblocks 71 tests, restores five safety proofs and makes staging
   functional for the first time since 2026-09-26. Do NOT fix it by relaxing the
   `qualified` check or defaulting a qualification. Delete the
   `restore_gate_reachability` scaffolding and `TheSequenceGateCallSiteIsIncomplete`
   when it lands; those assertions fail on purpose once the real fix is in.
2. **TASK-364 rework 2** — the plan is built FIRST from strategy and copy; both
   factories and every write path read only the plan; nothing reads
   `plan["sequence"]`. Acceptance: mutate the plan, BOTH provider projections change,
   through the real factory entry points. No `hasattr`, no source-text assertions.
3. **TASK-400** — merge once decisions 1-4 are answered and the 9
   `tests/test_generate.py` errors are resolved rather than retired. Branch
   `worktree-agent-a88cf873fc4570da2` at `5c356b7d`.

Then TASK-425, the one-account dry run with the causal matrix (A original, B one
fact changed, C persona switched, D evidence removed), provider writes 0, then STOP
for operator review. No ten accounts without an explicit decision.

## 10. WHAT THIS SESSION GOT WRONG, recorded so it is not repeated

1. **"There is no backup."** There was; the host job was healthy and the staging
   step was missing. Checked the laptop, not the host.
2. **Broke `offers.load()`** by validating YAML with `yaml.safe_load` while
   production uses `clients.parse`. The entrypoint was dead from `a04574be` to
   `603afbba`. A validator that accepts more than production proves nothing.
3. **Over-corrected `ops_channel()`**, collapsing ops onto status and breaking
   `test_ops_events_still_go_to_ops`. The operator's one-room decision changes which
   id ops resolves to, not whether the concept exists.
4. **Nearly re-dispatched six live GLM runs** by reading claim PIDs as worker
   liveness. `claim_task.py:140` documents that the pid belongs to the CLAIMING
   process; every live claim looks dead to a pid check. That is why `--reap` refuses.
5. **Left a phantom claim** on TASK-285 by probing with `--next`, which claims.
   Released immediately — but it is exactly the corruption the scheduler fix exists
   to prevent.

The invariant that came out of all five is now in `OPERATING-MODE`: **"State is
explicit, never inferred."** PID is not worker state; branch is not task state;
commit freshness is not worker state; a TODO file count is not ready depth; config
is not enforcement; a passing test is not runtime integration.
