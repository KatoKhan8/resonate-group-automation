# Merge request — lane F, the standing QA suite

Branch `worktree-agent-af7c25390135b3474`, worktree
`.claude/worktrees/agent-af7c25390135b3474`, forked from `24acafff`.
**Documents only. No code, no provider call, no write to `work/`.**

Lane F is the AUTHOR lane. It writes the contract and the tasks so work can
start immediately; **Qwen implements with tests, GLM reviews the refusal
logic, the production session wires the push refusal and the watchers.**

---

## 1. WHAT THIS DELIVERS

    docs/QA-LANE-F-CONTRACT-2026-09-25.md      the scripts/qa/ interface
    docs/qwen-tasks/TODO/TASK-292 … TASK-299   eight tasks, all READY

    TASK-292  a push that cannot refuse is not a gate                    P0
    TASK-293  eligible in our store is not eligible at the provider      P0
    TASK-294  the researched set and the rendered set are disjoint       P0
    TASK-295  em4 reads BODY_3, and the step key is not the variable no. P0
    TASK-296  eleven campaigns legitimately hold three steps             P0
    TASK-297  the two halves of one cadence are on different clocks      P1
    TASK-298  absent within the window is not absent                     P0
    TASK-299  zero contacts carry the field the check is gated on        P1

**Numbering.** The true maximum across every ref in this repository is
**TASK-291** (lane E, on `worktree-agent-a12ddab5c442ad2f9`, not on master).
Checked across all refs before committing to numbers, because four issue
numbers were taken twice this week and TASK-287 exists because of it.

---

## 2. THE MINIMUM FOR TODAY'S 128

The 128 clean UK/EU leads go onto new four-step EmailBison campaigns **502 and
503** (501 is consumed by the stop-test campaign). The first QA table runs on
them before they go.

    GATES THE 128   292  the harness, the return shape, the refusal, the table
                    293  per-lead eligibility and state
                    294  per-lead research pack
                    295  per-lead copy
                    296  per-campaign EmailBison
                    298  post-push readback, within one cycle of the push

    DOES NOT        297  per-campaign HeyReach — the 128 are an EMAIL push.
                         Required before the 825 enrollment across 33 seats,
                         which is the next thing after this one.
                    299  ongoing reconciliation — runs from the first cycle
                         AFTER the push. Not a gate on it, and needed the same
                         day, because it is the one that catches ISSUE-041's
                         class and it is a CRITICAL when it fires.

Six workers can start on the minimum right now and two on the rest.

---

## 3. THE SPLIT, AND WHY IT IS THIS SPLIT

One module per **check group**, not per rule and not per provider. A group is
the set of rules that share a subject and a phase **and whose failure forces
the same decision**:

    lead_pack   fails -> re-research the account
    lead_copy   fails -> regenerate the copy
    lead_state  fails -> hold the lead
    campaign_*  fails -> fix the campaign at the provider
    readback    fails -> a person looks at the push that just happened
    reconcile   fails -> a CRITICAL, now

Splitting by rule would give thirty scripts and thirty table rows nobody
reads. Splitting by provider would put "is this lead eligible" in two places,
and the whole point of that rule is that it is one question asked of two
providers. Splitting by subject alone would put the pack check and the copy
check together, and they fail for unrelated reasons and are fixed by different
people.

The harness is its own task because the return shape, the refusal seam and the
table are a contract three other things consume, and because wiring a gate
into the real send path is the thing this project has got wrong twice in a
week.

---

## 4. `DEPENDS:` IS EMPTY ON ALL EIGHT, DELIBERATELY

`scripts/task_registry.py` parses `DEPENDS:` as **comma-separated task ids**
and marks a task BLOCKED when an entry is not in `DONE/`. Lane E wrote prose
there last night and **nine of its thirteen tasks were invisible to
`claim_task.py`** — the tool a worker takes a task with. Ten tasks written to
clear a CRITICAL, four of them dispatchable, green the whole time.

Lane F does not repeat it, and does not merely avoid prose: **it removes the
dependency.** The interface all eight conform to is
`docs/QA-LANE-F-CONTRACT-2026-09-25.md`, which is committed and frozen, so no
check imports another check's module and TASK-292 is first in *usefulness*
rather than in *compilability*. Seven tasks blocked behind one harness would
have left seven of eight workers idle on the morning the 128 go.

The ordering lives in a `DISPATCH NOTE` block at the top of each file, where
it is for a person.

**Verified by running the tool, not by reading the files** — §7.

---

## 5. THE CORRECTION THIS LANE FOUND

**Two committed documents describe the four-step cadence wrongly, and a check
written from either would report every lead blank.**

`PRODUCTION-HANDOFF-2026-09-24-LATE.md` §2 says em4 opens a NEW thread with
`SUBJECT_2`, and lane E's TASK-283 encodes that version. Read from lane B's
own config, `config/clients/productive.yaml` lines 590-626 on
`worktree-agent-a68c1abeb4d3a99f5` @ `472960eb`, which is the file the builder
reads:

    thread_reply_pattern: [false, true, true, true]

    em1  order 1  {SUBJECT_1}  {BODY_1}  wait 3
    em2  order 2  {SUBJECT_1}  {BODY_2}  wait 4
    em4  order 3  {SUBJECT_1}  {BODY_3}  wait 5      <- POSITION 3
    em5  order 4  {SUBJECT_1}  {BODY_4}  wait 1      <- POSITION 4

Three consequences, all in TASK-295:

1. **The step key is not the variable number.** A check mapping `em5 → BODY_5`
   looks for a variable that does not exist.
2. **There is no `SUBJECT_2` and no new-thread step.** All four carry
   `{SUBJECT_1}`; step 1 opens the thread and steps 2, 3 and 4 reply into it.
   Lane B's own commit `1abe88ca` — *"the fourth entry is four, not five, and
   em4 cannot open a second thread"* — is right and the handoff is not.
3. **A threaded step still carries a subject.**
   `bisonfactory._sequence_steps`: *"A follow-up step STILL CARRIES
   `email_subject` — the flag is the mechanism, not subject omission."* So
   subject-omission is not how threading is detected, and a check built on it
   passes a step that sends with an empty subject line.

TASK-295 instructs the worker to read the mapping **from the config the run
loads, at run time, and print it**, and to believe the config over either
document. **Lane E's TASK-283 should be corrected on the same point** — flagged
here rather than edited, because TASK-283 is on lane E's branch and not mine.

---

## 6. WHAT THE CONTRACT FIXES, AND WHY EACH LINE IS THERE

- **Four exit codes, not two.** `UNCONFIRMED` exists because ISSUE-043's
  campaign-membership index took **~30 seconds** against a **~15 second**
  readback: lead 205079 answered 200, raised, and was present at t+30s with
  the count moved 332 → 333. Folded into PASS it hides a real absence; folded
  into FAIL it makes somebody re-push a good push, and a re-push against a
  lead now `in_sequence` cannot be attached anywhere at all.
- **`VACUOUS` is named apart from `UNCONFIRMED`,** and `subjects == 0` is
  never a PASS. This is ISSUE-041 raised to the contract: **ZERO contacts in
  `work/queue.jsonl` carry `heyreach_lead_id`**, so every cross-channel stop
  ever run reported success having never called the provider, and read exactly
  like a working one.
- **Five invariants the RUNNER enforces on every result**, including that the
  arithmetic closes and that offenders hold ids rather than counts. The runner
  does not trust the check.
- **The refusal seam is `bisonfactory.stage`, immediately after lane D's
  `_refuse_copylint` at line 86, before the first provider call.** Never in
  `scripts/batch1_push.py`. TASK-277 wired a lint into `src/push.py`, whose
  `run()` raises on `live=True`, through a function nothing called, proved by
  eight tests that all called it directly. A gate in the caller is a gate the
  next caller skips.
- **No `--skip-qa` and no `--force`.** The only escape is `blocking=False` in
  the registry, in a commit, with a reason — visible in `git log`. A flag on a
  command line is not.
- **One table per push, every registered check gets a row**, including the
  ones that passed and the ones that were vacuous. A table listing only
  failures cannot be told apart from a table where nothing ran. Counts in the
  channel; ids in `work/qa/<run>/`.
- **`--workspaces` is required with no default.** A worktree has its own stale
  `work/`; most workers have none and the one that did was 37 minutes behind
  production.

Both house rules are in the acceptance bar of every task: **a suite baseline
is a LIST, not a count** (diff sets both directions), and **a green suite
proves nothing live** (read the provider and `work/*.jsonl`).

---

## 7. THE REGISTRY, BEFORE AND AFTER

Run in this worktree, which forked from `24acafff` and therefore does not
carry lane E's TASK-279 … TASK-291 (they are on
`worktree-agent-a12ddab5c442ad2f9`, not on master).

    BEFORE   counts: QUEUED 33 · AWAITING_REVIEW 11 · REWORK 1 · BLOCKED 2 · DONE 227
             READY: 33

    AFTER    counts: QUEUED 41 · AWAITING_REVIEW 11 · REWORK 1 · BLOCKED 2 · DONE 227
             READY: 41

**All eight appear in the READY list and none is BLOCKED.** Six of the eight
are P0 and sort to the top, which is the dispatch order for the morning.
`dependencies` is `[]` and `blocked_by` is `[]` on every one of the eight in
`docs/state/TASK-REGISTRY.json` — read out of the JSON, not inferred from the
printed list.

**And confirmed against the tool a worker actually claims with**, which is not
the registry:

    py -3 scripts/claim_task.py --status

    claims held: 0
    ready (unclaimed, deps met): 14
      P0   TASK-292   P0   TASK-293   P0   TASK-294   P0   TASK-295
      P0   TASK-296   P0   TASK-298   P1   TASK-297   P1   TASK-299

**Eight of the fourteen tasks claimable on this machine right now are lane
F's.** `claim_task.py` applies a branch-activity filter the registry does not,
so 14 and 41 are different questions and neither is wrong: the registry counts
what is queued, `claim_task` counts what is free. The number that matters for
"can a worker take this in the morning" is the second one, and all eight are
in it.

This was verified by **running both tools**, after committing the files and
after committing this document with the AFTER numbers still unchecked. Lane E's
lesson was not "write the DEPENDS line correctly", it was "run the tool".

When lane E's thirteen are integrated alongside these eight, the pool's READY
count is higher again; lane E measured 41 READY on its own branch after its
fix. Neither number is the integrated one, and the registry says so itself:
it reads master's directories alone and cannot see work finished on branches.

---

## 8. WHAT THIS LANE DID NOT DO, AND WHY

- **No `scripts/qa/*.py` implementation.** Lane F is the author lane; the
  contract carries example shapes and nothing executable.
- **No edit to `src/bisonfactory.py`.** The refusal seam is specified and
  TASK-292 delivers it as a patch proposal, because lane D holds that file on
  an unmerged branch and two hands on one seam is how a half-applied change
  happens.
- **No edit to lane B's `config/clients/productive.yaml`, `src/cadence.py` or
  `scripts/batch1_build.py`**, and no edit to lane D's `src/packfacts.py` or
  `src/copylint.py`. The correction in §5 is reported, not patched.
- **No provider call of any kind**, and no merge and no push.
- **TASK-283 not corrected** — lane E's branch, not mine. §5 is the flag.

---

## 9. RECOMMENDED ACTION

1. Merge these documents — they are additive, touch no shared file, and
   nothing in them runs.
2. Dispatch **292, 293, 294, 295, 296, 298** this morning, one task named per
   worker, each worker `git mv`-ing its file to `RUNNING/` as its first
   action. 297 and 299 to the remaining two.
3. **Correct lane E's TASK-283** on the step→variable mapping before anybody
   claims it, or the S7 verification will assert `SUBJECT_2` against a config
   that has none.
4. GLM reviews the refusal logic of TASK-292 before the gate is wired into
   `bisonfactory.stage`, and TASK-299's key-presence rule before it runs
   against the estate.
5. The first QA table runs on the 128 before they go, and the post-push table
   within one cycle after.
