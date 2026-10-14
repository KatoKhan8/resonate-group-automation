# Slack agent — handoff, 2026-10-14

Lane closed. Nothing here is merged and nothing is deployed. `origin/master`
is `2bf7b8a571fe11bada4f56fbebeee768ab1e78a8` and was never touched.

---

## CROSS-LANE — two findings that belong to other lanes

### a. A control that could not fail is already fixed. Another lane is hunting it.

**Branch `task-guard-scope-is-relative`, SHA `01a576ccafc98849bdb10854eecd7380f3ce8ae1`, pushed.**

**What the fix changes, in one line:** `test_invariants.TestNothingCanSend` and
the same filter in `test_audit` matched their provider allowlist against the
file's ABSOLUTE path; they now match against the file's own basename, so no
directory name can widen the exemption.

**Why it mattered.** `slack` is one of the allowed provider tokens. From a
worktree at `.../scratchpad/wt-slack-24h`:

    exempt from a path containing "slack"   258 of 258  (100%)
    exempt from a neutral path               25 of 258  ( 10%)

The guard reported green while guarding nothing, and a completed
1,879-second suite run had to be discarded as void.

**Mutation evidence**, in a disposable worktree whose path deliberately
contains `bison`, `heyreach` and `slack`:

    with the fix      scope control OK (6 tests); the guard itself honestly
                      FAILS on its one real offender src/providers/__init__.py:376
    absolute filter   scope control -> 3 FAILURES; and the guard itself ->
    restored          OK, i.e. GREEN WHILE GUARDING NOTHING

    HOSTILE  exempt_under_FIX= 25 of 258   exempt_under_OLD_absolute=258
    NEUTRAL  exempt_under_FIX= 25 of 258   exempt_under_OLD_absolute= 25

Mutant reverted, tree verified clean, scope control green again.

**The control for the control** is `tests/test_a_guards_own_scope_cannot_exempt_what_it_guards.py`
— twelve hostile path prefixes, the exempt SET compared rather than the count,
and a positive control asserting the OLD rule really did exempt all 258.

**Audit of the doubt it casts.** Two historical runs are implicated, and the
second one matters to whoever owns merge gating:

    reference-230-master-ae134dd2.verdict.txt   ran from .../scratchpad/glm-940
                                                failures=230, guard NOT in its
                                                failure list, i.e. it passed

All three neutral-path references (`e9ae9e6b`, `cd8e00bc`, `f2690f57`) record
**231** and DO list that guard as failing. So the 230-vs-231 gap is exactly this
one guard, self-exempted by `glm` in the path — and that 230-name verdict was
used as a master reference for zero-new-names merge gating.

### b. Verdict parsing: failures are indented, logs are not. Fifth instance of a control that cannot fail.

**General finding, not a bug in one script.** `scripts/run_suite.py` writes
failures into `suite_verdict.txt` INDENTED:

    "  FAIL: test_module.Class.test_name"

while a verbose run writes them at column zero:

    "FAIL: test_module.Class.test_name"

Any reader that anchors on `^(FAIL|ERROR):` therefore matches the log and
silently misses every verdict. The tell is unmistakable once seen: **the same
run reads RED from its log and GREEN from its own verdict.** A reader built
that way reports a clean baseline for a suite that failed, and reports it
confidently.

Anything that parses verdict files should be checked against this, and the
cheap self-check is to parse both artefacts of one run and require that they
agree. `\s*` before the marker is the fix.

This is the fifth control-that-cannot-fail in this lane's history, after: the
catalogue parser that matched a bullet shape the document never used; a replay
scorer that never read the tool it recorded; a planner scorecard that would
have agreed with the planner it graded; and the allowlist above.

---

## Branches, with SHAs and contents

All five pushed; remote SHA verified equal to local for each.

| branch | SHA | contains |
| --- | --- | --- |
| `task-replay-expected-tool` | `e8da7edf07821df69ad8a3cdfe5b01c7e9dfca5b` | the replay harness scored the answer and never the read it was built from; adds the `tool` check plus 14 tests and two mutants |
| `task-tool-scorecard-review` | `93e2d658b1f3de43c00058b44a103471f2d435be` | planner-only scorecard, because `--catalogue` cannot score a tool at all (27 of 27 rows n/a, unbound scope has no tools); 20 tests |
| `task-planner-hr-keywords` | `d1669244039b61979051d04ba2336b1a1f9455d4` | Croatian keywords for meeting, lead and report in the no-model fallback |
| `task-slack-agent-review-24h` | `9fd8660e5626998ea698818b5fb2b35f9ec836c7` | narrows `poziv`/`report`, adds `leads` and `izvjestaj`, the honest unticketable refusal, the two test-hygiene fixes, the heartbeat inventory, and this handoff |
| `task-guard-scope-is-relative` | `01a576ccafc98849bdb10854eecd7380f3ce8ae1` | the allowlist-scope fix and its control — see CROSS-LANE a |

`src/` is touched by exactly two of them: `src/slackconversation.py` on
`task-planner-hr-keywords` and `task-slack-agent-review-24h`. Nothing else
under `src/` changes on any branch. `CLIENT_CHANNEL_GAG` is byte-identical to
master everywhere — the diff over that constant is zero lines.

## Worktrees

| path | safe to delete |
| --- | --- |
| `scratchpad/wt-replay-tools` | YES — branch pushed |
| `scratchpad/wt-tool-scorecard` | YES — branch pushed |
| `scratchpad/wt-hr-keywords` | YES — branch pushed |
| `scratchpad/wt-slack-24h` | YES — branch pushed |
| `scratchpad/wt-guard-scope` | YES — branch pushed |
| `scratchpad/wt-neutral-review` | YES — detached at `f81ae878e`, which is an ancestor of the pushed branch |
| `scratchpad/wt-slack-heyreach-bison-hostile` | YES — disposable, mutation evidence already recorded |
| `scratchpad/ref-master-2bf7b8a5` | YES — detached at `origin/master` |
| `scratchpad/ref-baseline-93e2d658b` | YES — detached at a pushed SHA |
| `resonate-ops/sandbox-evidence-2026-10-12/wt-endurance` | **NO — not mine to delete**, sandbox lane |
| `resonate-ops/wt-rt`, `ref-cd8e00bc`, `ref-e9ae9e6b` | **NO — not mine**, other lanes |

Every scratchpad worktree above is safe only because its branch is on the
remote. That was not true an hour ago.

## Reproducing each measurement

Run each from a worktree whose path contains none of `aiark apify blitz bison
contactout glm heyreach slack xai`. All are offline — no provider, model,
Slack or network call.

    py -3 scripts/slack_planner_scorecard.py --out <out.json>
    py -3 scripts/slack_agent_replay.py --catalogue --no-model --out <out.json>
    py -3 scripts/heartbeat_inventory.py --json <out.json>
    py -3 scripts/sandbox_copy_review.py --out <dir>          # endurance branch
    py -3 scripts/run_suite.py --offline                      # full suite
    py -3 name_set_diff.py <reference.log> <branch.log> --root <worktree>

Targeted tests on `task-slack-agent-review-24h`:

    py -3 -m unittest tests.test_the_fallback_answers_croatian_about_meetings_leads_and_reports
    py -3 -m unittest tests.test_a_request_to_stop_sending_has_no_safe_answer
    py -3 -m unittest tests.test_the_stop_sending_refusal_is_honest
    py -3 -m unittest tests.test_the_planner_scorecard_is_not_its_own_answer_key
    py -3 -m unittest tests.test_the_replay_scores_the_tool_it_chose

On `task-guard-scope-is-relative`:

    py -3 -m unittest tests.test_a_guards_own_scope_cannot_exempt_what_it_guards

Durable artefacts: `Desktop/resonate-ops/slack-agent-2026-10-14/` with its own
`MANIFEST.md`. The three ~3 MB suite logs are not duplicated there; they sit in
`resonate-ops/slack-agent-pid28428-stop-2026-10-13/` and the manifest says so.

## The planner figure, stated in full

**89%, 16 of 18 scored.** That is the **keyword fallback**, on **27 catalogue
phrasings**, under **scopes that are labelled rather than known**, and it says
**nothing about the live model** — the running loop has a model configured and
this number never exercised it.

It did not move across the `poziv`/`report` narrowing: 89% before, 89% after,
with a byte-identical per-expectation breakdown. That is the only basis on
which the narrowing can be called free, and it is the reason the narrowing was
taken: it removed seven false routings at no measured cost.

## Verdicts

PASS:

* suite gate on `task-slack-agent-review-24h` — reference on master `2bf7b8a5`
  231 failing names, branch 231, **name-set diff ZERO NEW NAMES**, neither run
  timed out, neither partial
* the allowlist-scope fix, its control, its mutation evidence and the audit
* the Croatian narrowing — 7 false routings removed, catalogue coverage 3/3
  meeting and 2/2 report retained, scorecard unmoved
* the unticketable refusal — no tool called (enforced by a spy that raises),
  nothing journalled, gag untouched, targeted ask still ticketed
* heartbeat inventory
* both Slack-posting processes stopped and confirmed absent

UNVERIFIED:

* the heartbeat contract and the idle detector — inventory only, nothing built
* the warm-reply classifier fix — never started on any branch, deliberately
* the 120-day endurance run — never started
* LinkedIn channel quantification — never started
* GLM review of any branch — never run, never authorised for these branches
* branch hygiene recommendation for the two old Slack branches

NEVER STARTED, and not dressed up as started: items TWO, THREE (beyond the
inventory), FOUR and FIVE of the final brief.

## Withdrawn — my own claims that the measurement overturned

**The identical-subject-lines "defect" was not a defect.** I reported em1, em2
and em3 sharing one subject line as a defect. `docs/EMAILBISON-COPY-REQUIREMENTS.md:50`
says the opposite: *"Do not generate a new subject for every step. A follow-up
preserves the subject."* Line 33 adds that a step carries `email_subject` even
when `thread_reply` is true, and line 42 allows EMAIL 4 a fresh subject if
justified — which is exactly the rendered pattern. A threaded follow-up threads
BECAUSE the subject is preserved. **Withdrawn: intended behaviour, correctly
implemented.**

**My loop classifier was unsound and its verdict is not shipped.** The first
version of `scripts/heartbeat_inventory.py` reported `slack_agent_loop.py` as
able to distinguish idle from dead, on the grounds that its beat is a direct
statement of the `while True` body. That contradicted a direct measurement: the
same loop's heartbeat sat frozen for 7,570 seconds while the process was alive.
The body blocks in `for kind, message in socketmode.envelopes(connection)`, so
it only comes round on reconnect — "direct statement of the loop body" is not
"reached on a bounded timer". The sound signal is a second measurement, sleeps
versus a blocking iterator, and on that reading `slack_agent_loop.py` is the
ONLY loop of nine with the defect.

**And the premise narrowed with it.** Freshness is not the systemic problem:
eight of nine loops already beat on a timer, `watchsink.beat` documents that
contract, and `reply_watch_loop.py:178` beats on every sweep. What no loop has
is any record of USEFUL work — a grep across `src` and `scripts` for
`last_useful|useful_work|last_work_at|work_done|useful_units` returns nothing.
So "healthy" means "alive", and the reply watcher is the proof: fresh heartbeat,
zero ingested, nothing able to see the difference.

**The audit instrument needed two corrections** before its output was usable:
the indented-verdict regex above, and per-guard reporting instead of OR-ing two
different guards, which had hidden the one green the audit existed to find.

## Still the operator's decision

Both sides recorded elsewhere; no recommendation here.

* whether 90 days of cooling is the right business rule
* whether the day-one double touch in the cadence definition is deliberate —
  the engine's `eligibility._separation` already holds whichever of li1/em1
  lands second, so the definition and the guard disagree in intent
* whether the planner change lands on master
* whether the two old Slack branches are abandoned — note `slack-agent` is
  misnamed, its two commits touch the research pack, not the agent
* the `CLIENT_CHANNEL_GAG` documentation drift: the gag is NOT total silence
  since 2026-09-24, and two docs still describe it as though it were
* any prospect-facing send, activation or canary
* history rewrite; repository visibility

## Confirmations

No production change. No provider, model, Apify, Slack or network call. Zero
credits. No message sent to any channel. No merge. `origin/master` unchanged at
`2bf7b8a571fe11bada4f56fbebeee768ab1e78a8`. The main checkout and other lanes'
worktrees were never touched. Two Slack-capable processes were stopped —
`slack_agent_loop.py` PID 28428 and `slack_followup_loop.py` PID 13232 — each
after confirming identity, ownership and that nothing was mid-delivery, each
with its state preserved first, and each confirmed absent afterwards.
