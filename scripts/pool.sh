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

WORKERS=(resonate-qwen-worker resonate-qwen-2 resonate-qwen-3 resonate-qwen-4 \
         resonate-qwen-5 resonate-qwen-6 resonate-qwen-7 resonate-qwen-8)

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
  py -3 "$MAIN/scripts/claim_task.py" --status 2>/dev/null \
    | awk '/^ready/{f=1;next} f&&/^  P[0-4]/{print $2; exit}'
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
docs/CONTEXT-RESET-2026-09-15-D.md, docs/PRODUCTION-SCALE-POLICY.md.

PUSH AFTER EVERY USEFUL RESULT. This machine died without warning yesterday:
  git add -A && git commit -m '...' && git push -u origin $br
Push BEFORE starting anything long.

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
  ( cd "$d" && git checkout -q -B "$br" master 2>/dev/null
    QWEN_CODE_SUPPRESS_YOLO_WARNING=1 "$QWEN" --approval-mode yolo "$prompt" \
      > "$LOGS/$wt.$ROUND.log" 2>&1
    echo "$(date +%H:%M:%S) DONE $wt $tid exit=$?" >> "$LOGS/pool.log"
    py -3 "$MAIN/scripts/claim_task.py" --release "$tid" >/dev/null 2>&1
    unlock_worktree "$wt" ) &
  echo "$(date +%H:%M:%S) dispatched $wt [$br] -> $tid" | tee -a "$LOGS/pool.log"
}

# One pass: give every free worker the next ready task.
sweep () {
  for wt in "${WORKERS[@]}"; do
    busy "$wt" && continue
    tid="$(next_ready)"
    [ -z "$tid" ] && { echo "$(date +%H:%M:%S) no ready task for $wt" >> "$LOGS/pool.log"; continue; }
    task="$(file_for "$tid")"
    [ -z "$task" ] && continue
    dispatch "$wt" "$(branch_for "$wt")" "$tid" "$task"
  done
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
