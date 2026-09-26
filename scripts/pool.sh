#!/usr/bin/env bash
# Keep all eight Qwen workers busy for as long as ready work exists.
#
# WHY THIS EXISTS
#
# The zero-idle rule: 8 workers -> 8 useful independent tasks, and a worker
# that finishes is reassigned immediately rather than waiting for Claude to
# review what it just produced. Review and execution run in parallel.
#
# Doing that by hand means a worker sits idle for however long Claude happens
# to take on something else. This loop closes that gap.
#
# HOW A TASK IS CLAIMED
#
# Through scripts/claim_task.py, which uses os.open(O_CREAT|O_EXCL) - atomic
# on Windows and POSIX. Six workers took one task this morning because reading
# a TODO directory claims nothing. The claim is the atomic write, not the read.
#
# WHAT IT DOES NOT DO
#
# It does not review, integrate, or push to master - those are Claude's. It
# does not reap stale claims on a timer: a crashed worker's claim looks exactly
# like a working worker's, and quietly reclaiming is how two workers end up on
# one task by a slower route. Run --reap deliberately.

set -u

MAIN="C:/Users/Zvonimir/Desktop/resonate-group-automation"
QWEN="C:/Users/Zvonimir/AppData/Local/qwen-code/bin/qwen.cmd"
LOGS="${POOL_LOGS:-$MAIN/../pool-logs}"
ROUND="${POOL_ROUND:-r9}"
mkdir -p "$LOGS"

# RAISED TO 12, 2026-09-25. Measured on this machine: AMD Ryzen 7 7735HS,
# 16 logical cores, 31.2 GB RAM with 6.4 GB free at the time of the change.
# RAM is the binding constraint here rather than cores - each worker runs
# several node processes - so 12 is chosen against free memory, and the
# status post reports actual usage so the next change is made from a
# measurement instead of an assumption.
WORKERS=(resonate-qwen-worker resonate-qwen-2 resonate-qwen-3 resonate-qwen-4 \
         resonate-qwen-5 resonate-qwen-6 resonate-qwen-7 resonate-qwen-8 \
         resonate-qwen-9 resonate-qwen-10 resonate-qwen-11 resonate-qwen-12)

# FORBIDDEN_TASKS removed 2026-09-27: claim_task.py now reads STATUS: BLOCKED
# and ABSORBED_BY: from each task file's own header, so the pool no longer
# needs a hand-maintained blocklist. One source of truth, not two.

branch_for () {   # worker dir name -> branch name for this round
  case "$1" in
    resonate-qwen-worker) echo "qwen-worker-$ROUND" ;;
    *)                    echo "qwen-worker-${1##*-}-$ROUND" ;;
  esac
}

# A WORKTREE LOCK, separate from the task claim, and both are needed.
#
# The task claim answers "is somebody working on this task". It does NOT
# answer "is this worktree free". On 2026-09-15 a manual sweep ran while the
# loop was sweeping, and three worktrees were each given a second task: the
# claims were for different tasks, so nothing collided at the claim level,
# while two qwen agents were pointed at one directory. Two agents running
# `git checkout -B` in the same worktree destroy each other's work.
#
# mkdir is the atomic primitive here - it either creates the directory or
# fails, with no read-then-write window.
LOCKS="$MAIN/work/worktree-locks"

lock_worktree () {
  mkdir -p "$LOCKS" 2>/dev/null
  mkdir "$LOCKS/$1" 2>/dev/null   # exit 0 only if WE created it
}

unlock_worktree () {
  rmdir "$LOCKS/$1" 2>/dev/null
}

busy () {   # occupied if the worktree is locked OR it holds a live claim
  [ -d "$LOCKS/$1" ] && return 0
  py -3 "$MAIN/scripts/claim_task.py" --status 2>/dev/null | grep -q " $1 "
}

next_ready () {   # highest-priority unclaimed task with deps met
  local tid
  tid="$(py -3 "$MAIN/scripts/claim_task.py" --status 2>/dev/null \
    | awk '/^ready/{f=1;next} f&&/^  P[0-4]/{print $2; exit}')"
  [ -n "$tid" ] && echo "$tid"
}

file_for () {
  ls "$MAIN/docs/qwen-tasks/TODO/$1"-*.md 2>/dev/null | head -1 | xargs -r basename
}

dispatch () {
  local wt="$1" br="$2" tid="$3" task="$4" d="C:/Users/Zvonimir/Desktop/$1"
  # Take the WORKTREE first. If another sweep already has it, stop before
  # claiming a task - otherwise the task is claimed and then abandoned.
  lock_worktree "$wt" || return 1
  py -3 "$MAIN/scripts/claim_task.py" --claim "$tid" --worker "$wt" >/dev/null 2>&1 || {
    unlock_worktree "$wt"; return 1; }
  local prompt="YOUR ONLY TASK IS $tid, file docs/qwen-tasks/TODO/$task

It is already CLAIMED for you atomically. No other worker can take it, and you
must not take any other - the rest of TODO/ belongs to the seven other workers
running right now.

FIRST ACTION, a tool call not a sentence:
  git mv docs/qwen-tasks/TODO/$task docs/qwen-tasks/RUNNING/
  git commit -m 'Take $tid'
  git push -u origin $br

Then read docs/qwen-tasks/RUNNING/$task and do exactly what it says. The task
file's own rules outrank anything general you believe.

Finish by appending a RESULT BLOCK (STATUS, COMMIT SHA, TESTS, FILES CHANGED,
FINDINGS, RISKS, RECOMMENDED CLAUDE ACTION), git mv to DONE/, commit, push.
Then STOP.

Worktree $d, branch $br. Context: QWEN.md, CLAUDE.md,
docs/CONTEXT-RESET-2026-09-15-E.md, docs/PRODUCTION-SCALE-POLICY.md.

PUSH AFTER EVERY USEFUL RESULT. This machine died without warning yesterday:
  git add -A && git commit -m '...' && git push -u origin $br
Push BEFORE starting anything long.

IF THE TASK NEEDS A LONG-RUNNING STEP (a full test suite, anything over a
few minutes): launch it detached (redirect output to a file and background
it) and poll with increasing sleep between checks, NEVER the identical
check repeated back to back - the CLI's own loop-detector halts a session
on repeated identical tool calls, and a tight poll loop looks exactly like
one. Measured 2026-09-26: a suite-regeneration task was redispatched from
scratch four times in one evening for exactly this reason, each attempt
losing all prior progress on the reset. Commit and push your progress
BEFORE you start waiting on anything long, not after.

HARD RULES:
- NO provider writes. No HeyReach or EmailBison POST/PATCH/PUT/DELETE, no
  sends, no campaign creation or activation, no adding leads. Reads only.
- Never commit config/.env, an API key or a token. Env var NAME only.
- Never commit unhashed PII - prospect or seat-holder names, domains, emails,
  profile URLs, reply text. Hash identifiers.
- Never merge into master.
- Read test exit codes OFF THE PROCESS, never through a pipe.
- Never weaken a gate, lint rule or sender limit to pass or to gain volume.
- Do not report a PREDICTED result. You have model access. Run it, measure it.
- A zero and a wrong lookup look identical from outside. Prove the field you
  read is the right one before reporting a zero.
- Boundary you may not cross: write it under FINDINGS, commit, push, stop.

Begin with the git mv."
  # RESETTING THE ROUND BRANCH TO MASTER DISCARDS THE LAST TASK IT CARRIED.
  #
  # `-B` is what makes each dispatch start from a clean master, and on
  # 2026-09-15 it also destroyed the local ref for five finished tasks when
  # their workers were reused within the same round. The work survived only
  # because it had been pushed, and `claim_task._claimed_on_a_branch` now
  # scans remote-tracking refs for exactly that reason.
  #
  # Push whatever the branch is carrying before resetting it, so the reset can
  # never be the thing that loses a result. A failure here is not fatal - the
  # worker is told to push after every result and usually already has - but it
  # is the last chance to catch one that did not.
  # PUSH THE BRANCH THE WORKTREE IS ACTUALLY ON, NOT THE ONE WE ARE ABOUT TO
  # CREATE. `$br` is the NEW round's branch, which usually does not exist yet,
  # so this safety push was a silent no-op for every worker carrying finished
  # work on a PREVIOUS round's branch.
  #
  # Measured 2026-09-16: TASK-169, TASK-170 and TASK-172 all finished, all
  # committed, none pushed. They survived because `checkout -B` creates the new
  # branch rather than deleting the old one, so the commits were still on
  # `qwen-worker-r24`, `qwen-worker-3-r24` and `qwen-worker-5-r25` locally - and
  # they were found by hand. `_claimed_on_a_branch` scans REMOTE refs, so an
  # unpushed result is also invisible to the collision detector, which is how
  # TASK-164 came to be dispatched twice.
  # VERIFY THE CHECKOUT BEFORE LAUNCHING QWEN, DO NOT TRUST ITS EXIT CODE.
  #
  # Measured 2026-09-26 22:10Z: of 12 concurrent dispatches, 6 landed on
  # stale, months-old branch history instead of fresh master - `checkout -B`
  # failed silently under concurrent load (`2>/dev/null` swallowed whatever
  # it was) and the worker built its whole task on the wrong codebase for
  # 30-50 minutes before anyone noticed. `2>/dev/null` on this line hid the
  # exact failure this now checks for directly: after the checkout, HEAD must
  # equal `origin/master`, or the dispatch aborts before spending a single
  # qwen turn on it.
  ( cd "$d" && cur="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
    [ -n "$cur" ] && [ "$cur" != "HEAD" ] && git push -q origin "$cur" 2>/dev/null
    git fetch -q origin master 2>/dev/null
    om="$(git rev-parse origin/master 2>/dev/null)"
    git checkout -q -B "$br" origin/master 2>/dev/null
    got="$(git rev-parse HEAD 2>/dev/null)"
    if [ -z "$om" ] || [ "$got" != "$om" ]; then
      echo "$(date +%H:%M:%S) ABORT $wt: checkout landed on $got, expected origin/master $om - NOT dispatching $tid" \
        | tee -a "$LOGS/pool.log"
      py -3 "$MAIN/scripts/claim_task.py" --release "$tid" >/dev/null 2>&1
      unlock_worktree "$wt"
      exit 1
    fi
    QWEN_CODE_SUPPRESS_YOLO_WARNING=1 "$QWEN" --approval-mode yolo "$prompt" \
      > "$LOGS/$wt.$ROUND.log" 2>&1
    echo "$(date +%H:%M:%S) DONE $wt $tid exit=$?" >> "$LOGS/pool.log"
    py -3 "$MAIN/scripts/claim_task.py" --release "$tid" >/dev/null 2>&1
    unlock_worktree "$wt" ) &
  echo "$(date +%H:%M:%S) dispatched $wt [$br] -> $tid" | tee -a "$LOGS/pool.log"
}

# One pass: give every free worker the next ready task.
#: Persisted across invocations (pool.sh is re-run fresh by cron each time)
#: so the CRITICAL-on-zero-claims-twice-in-a-row rule can count consecutive
#: sweeps rather than just this one.
ZERO_CLAIM_STREAK_FILE="$MAIN/work/.pool-zero-claim-streak"

#: Operator instruction, 2026-09-26/27 overnight: alert BEFORE morning
#: discovery, not after. Ready count is read straight from claim_task.py's
#: own report, not recomputed here, so this can never disagree with what a
#: human sees running --status by hand.
alert_if_needed () {
  local ready_n; ready_n=$(py -3 "$MAIN/scripts/claim_task.py" --status 2>/dev/null \
    | grep -oE '^ready \(unclaimed, deps met\): [0-9]+' | grep -oE '[0-9]+$')
  ready_n="${ready_n:-0}"
  local claims_n; claims_n=$(py -3 "$MAIN/scripts/claim_task.py" --status 2>/dev/null \
    | awk '/^claims held/{print $3}')
  claims_n="${claims_n:-0}"

  local streak=0
  [ -f "$ZERO_CLAIM_STREAK_FILE" ] && streak=$(cat "$ZERO_CLAIM_STREAK_FILE" 2>/dev/null || echo 0)
  if [ "$claims_n" -eq 0 ]; then
    streak=$((streak + 1))
  else
    streak=0
  fi
  echo "$streak" > "$ZERO_CLAIM_STREAK_FILE"

  local reason=""
  if [ "$ready_n" -lt 6 ]; then
    reason="ready tasks ($ready_n) below the floor of 6"
  fi
  if [ "$streak" -ge 2 ]; then
    reason="${reason:+$reason; }zero claims held for $streak consecutive sweeps"
  fi

  if [ -n "$reason" ]; then
    echo "$(date +%H:%M:%S) CRITICAL: $reason" | tee -a "$LOGS/pool.log" >> "$LOGS/pool-critical.log"
    py -3 -c "
import sys; sys.path.insert(0, '$MAIN')
from src import notify
notify.notify('failed_job_needs_attention', 'productive',
    fields={'reason': '''$reason''', 'ready_tasks': $ready_n, 'claims_held': $claims_n})
" 2>>"$LOGS/pool.log"
  fi
}

sweep () {
  for wt in "${WORKERS[@]}"; do
    busy "$wt" && continue
    tid="$(next_ready)"
    [ -z "$tid" ] && { echo "$(date +%H:%M:%S) no ready task for $wt" >> "$LOGS/pool.log"; continue; }
    task="$(file_for "$tid")"
    [ -z "$task" ] && continue
    dispatch "$wt" "$(branch_for "$wt")" "$tid" "$task"
  done
  alert_if_needed
}

case "${1:-sweep}" in
  sweep) sweep ;;
  loop)
    # Re-sweep on an interval so a finished worker is reassigned without
    # waiting for Claude. Bounded: it stops when nothing is ready.
    for _ in $(seq 1 "${2:-20}"); do
      sweep
      [ -z "$(next_ready)" ] && { echo "backlog empty, pool loop stopping" | tee -a "$LOGS/pool.log"; break; }
      sleep "${POOL_INTERVAL:-120}"
    done ;;
  *) echo "usage: pool.sh [sweep|loop [iterations]]"; exit 2 ;;
esac
