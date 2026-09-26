#!/usr/bin/env bash
# Keep the Qwen pool at full capacity unattended, and say so loudly when it
# cannot.
#
# WHY THIS EXISTS
#
# 2026-09-26 evening. scripts/pool.sh's `loop` mode re-sweeps on an interval
# but STOPS when the ready backlog is empty - correct for "finish this batch
# and quit", wrong for "run overnight". Nobody was re-invoking `sweep` after
# the last batch finished, so the pool sat idle with real ready work waiting
# and nothing dispatched it. Separately: `pool.sh`'s wrapper records
# `DONE ... exit=0` whenever the qwen CLI process exits zero - which it does
# both on a clean finish AND when its own loop-detector halts a long task
# early (measured same evening: TASK-372, a suite-baseline regeneration that
# has to run the ~12,700-test suite twice, was almost certainly polling for
# `work/suite_verdict.txt` with the same repeated tool call, which trips the
# CLI's repetition guard - "exit=0" recorded, task genuinely unfinished,
# still sitting in RUNNING/ on an unpushed branch where the dispatcher could
# never see it again).
#
# WHAT THIS SCRIPT ADDS ON TOP OF pool.sh
#
# 1. Runs forever (or until told to stop), re-sweeping on an interval,
#    instead of stopping when the backlog empties.
# 2. Before each sweep: finds a task stuck in RUNNING/ on a pushed branch
#    with no local claim and no commit in the last STUCK_MINUTES - the exact
#    shape TASK-372 was in - and moves it back to TODO/ on that branch,
#    committing and pushing, so the dispatcher can see it again. This is the
#    same fix a human did by hand for TASK-354/365 earlier the same evening
#    (commit e2c73823) and for TASK-372 tonight - automated so it does not
#    need doing by hand again.
# 3. Tracks consecutive cycles where every worker is idle AND at least one
#    task is ready. One such cycle is tolerated (a sweep can race a worker
#    finishing). Two in a row means the pool is failing to self-heal, and
#    that is CRITICAL: written to notify.py's FAILED_JOB event (a stored,
#    durable notification - see src/notify.py; this does not itself post to
#    Slack, a separate consumer does that, same as every other notification
#    in this codebase) and to $LOGS/pool-critical.log so a status check can
#    grep it without querying the notification store.
#
# WHAT IT DOES NOT DO
#
# It does not review, integrate or push task work to master - unchanged from
# pool.sh, that stays Claude's. It does not change what "ready" means or how
# a task is claimed - both come from claim_task.py, unmodified. It does not
# retry a task an unbounded number of times: a task requeued by rule 2 above
# gets ONE automatic requeue per watchdog run; a second stall on the same
# task is reported CRITICAL rather than requeued again silently, because a
# task that stalls twice is a task with a real defect, not bad luck.

set -u

MAIN="C:/Users/Zvonimir/Desktop/resonate-group-automation"
POOL_SH="$MAIN/scripts/pool.sh"
LOGS="${POOL_LOGS:-$MAIN/../pool-logs}"
mkdir -p "$LOGS"
WATCHDOG_LOG="$LOGS/pool-watchdog.log"
CRITICAL_LOG="$LOGS/pool-critical.log"

WORKERS=(resonate-qwen-worker resonate-qwen-2 resonate-qwen-3 resonate-qwen-4 \
         resonate-qwen-5 resonate-qwen-6 resonate-qwen-7 resonate-qwen-8 \
         resonate-qwen-9 resonate-qwen-10 resonate-qwen-11 resonate-qwen-12)

# Minutes of no local commit on a RUNNING task's branch before it counts as
# stalled. Suite-regeneration tasks can legitimately run long, so this is
# generous rather than twitchy - it exists to catch "the process exited and
# nobody noticed", not to second-guess a worker still genuinely working.
STUCK_MINUTES="${STUCK_MINUTES:-30}"

log () { echo "$(date +'%Y-%m-%d %H:%M:%S') $*" | tee -a "$WATCHDOG_LOG"; }

# Has this exact task already been auto-requeued once by this watchdog? A
# second stall gets reported, not silently retried again.
already_requeued () {
  grep -q "^REQUEUED $1\$" "$LOGS/pool-watchdog-requeued.log" 2>/dev/null
}
mark_requeued () {
  echo "REQUEUED $1" >> "$LOGS/pool-watchdog-requeued.log"
}

# Find a task sitting in RUNNING/ on some worker's local branch, with a last
# commit older than STUCK_MINUTES, and requeue it to TODO/ on that branch.
# Checks the twelve known worker worktree directories directly - the same
# set pool.sh dispatches to - rather than every branch on origin, since a
# branch nobody's worktree is on cannot be "stuck", only abandoned (a
# different, rarer problem this does not try to solve).
#
# TWO GUARDS ADDED AFTER THE FIRST RUN MISFIRED, 2026-09-26 evening. The
# first version checked only "how old is the last commit touching this
# file" and requeued five ALREADY-MERGED tasks (331, 343, 365, 328, 245)
# whose worker had simply finished, pushed, and gone idle - the file's
# last-touch age looked identical to a genuinely stuck task. Never requeue
# a task that either (a) is already in docs/qwen-tasks/DONE/ on
# origin/master - it is finished, this branch is just stale - or (b) has a
# LIVE claim right now per claim_task.py --status - a worker can genuinely
# work for a long time between commits (research, thinking, running a long
# local test) and "no recent commit" alone does not mean "exited".
requeue_stuck () {
  local now_epoch; now_epoch=$(date +%s)
  local done_ids; done_ids="$(git -C "$MAIN" ls-tree --name-only origin/master:docs/qwen-tasks/DONE 2>/dev/null \
    | grep -oE '^TASK-[0-9]+' | sort -u)"
  local claimed_ids; claimed_ids="$(py -3 "$MAIN/scripts/claim_task.py" --status 2>/dev/null \
    | sed -n '/^claims held/,/^ready/p' | grep -oE '^  TASK-[0-9]+' | tr -d ' ')"
  for wt in "${WORKERS[@]}"; do
    local d="C:/Users/Zvonimir/Desktop/$wt"
    [ -d "$d/.git" ] || [ -f "$d/.git" ] || continue
    local running_dir="$d/docs/qwen-tasks/RUNNING"
    [ -d "$running_dir" ] || continue
    for f in "$running_dir"/TASK-*.md; do
      [ -e "$f" ] || continue
      local tid; tid="$(basename "$f" | grep -oE '^TASK-[0-9]+')"
      [ -n "$tid" ] || continue
      if echo "$done_ids" | grep -qx "$tid"; then
        continue   # already DONE on master - this branch is just stale, not stuck
      fi
      if echo "$claimed_ids" | grep -qx "$tid"; then
        continue   # a worker holds this claim right now - not stuck, working
      fi
      local last_ts
      last_ts=$(git -C "$d" log -1 --format=%ct -- "$(realpath --relative-to="$d" "$f" 2>/dev/null || echo "docs/qwen-tasks/RUNNING/$(basename "$f")")" 2>/dev/null)
      [ -n "$last_ts" ] || continue
      local age_min=$(( (now_epoch - last_ts) / 60 ))
      if [ "$age_min" -ge "$STUCK_MINUTES" ]; then
        if already_requeued "$tid"; then
          log "CRITICAL: $tid stuck in RUNNING on $wt a SECOND time ($age_min min since last commit) - not auto-requeuing again, needs a human look"
          py -3 -c "
import sys; sys.path.insert(0, '$MAIN')
from src import notify
notify.notify('failed_job_needs_attention', 'productive',
    fields={'reason': 'task stuck in RUNNING twice', 'task': '$tid',
            'worktree': '$wt', 'age_minutes': $age_min},
    ids={'task_id': '$tid', 'worktree': '$wt'})
" 2>>"$WATCHDOG_LOG"
          echo "$(date +%H:%M:%S) CRITICAL: $tid stuck twice on $wt" >> "$CRITICAL_LOG"
          continue
        fi
        log "requeuing $tid: stuck in RUNNING on $wt for $age_min min, no local claim expected (worker process exited)"
        ( cd "$d" \
          && git mv "docs/qwen-tasks/RUNNING/$(basename "$f")" "docs/qwen-tasks/TODO/$(basename "$f")" 2>/dev/null \
          && git commit -q -m "$tid back to TODO: watchdog found it stuck in RUNNING $age_min min with no progress (worker likely exited on the tool-call/loop-detection cap) - requeued so the dispatcher can see it" \
          && git push -q origin "$(git rev-parse --abbrev-ref HEAD)" 2>>"$WATCHDOG_LOG" )
        mark_requeued "$tid"
      fi
    done
  done
}

busy_count () {
  local n=0
  local status_out; status_out="$(py -3 "$MAIN/scripts/claim_task.py" --status 2>/dev/null)"
  for wt in "${WORKERS[@]}"; do
    if [ -d "$MAIN/work/worktree-locks/$wt" ]; then
      n=$((n+1)); continue
    fi
    echo "$status_out" | grep -q " $wt " && n=$((n+1))
  done
  echo "$n"
}

ready_count () {
  py -3 "$MAIN/scripts/claim_task.py" --status 2>/dev/null \
    | awk '/^ready/{print $3; exit}'
}

idle_ready_streak=0

cycle () {
  ( cd "$MAIN" && git fetch -q origin 2>>"$WATCHDOG_LOG" )
  requeue_stuck
  bash "$POOL_SH" sweep >> "$WATCHDOG_LOG" 2>&1

  local busy; busy=$(busy_count)
  local ready; ready=$(ready_count)
  ready="${ready:-0}"

  if [ "$busy" -eq 0 ] && [ "$ready" -gt 0 ]; then
    idle_ready_streak=$((idle_ready_streak+1))
    log "pool idle: 0 workers busy, $ready task(s) ready (streak=$idle_ready_streak)"
    if [ "$idle_ready_streak" -ge 2 ]; then
      log "CRITICAL: pool has been idle with ready work for $idle_ready_streak consecutive cycles"
      py -3 -c "
import sys; sys.path.insert(0, '$MAIN')
from src import notify
notify.notify('failed_job_needs_attention', 'productive',
    fields={'reason': 'pool idle with ready work', 'ready_tasks': $ready,
            'idle_cycles': $idle_ready_streak})
" 2>>"$WATCHDOG_LOG"
      echo "$(date +%H:%M:%S) CRITICAL: pool idle $idle_ready_streak cycles, $ready ready" >> "$CRITICAL_LOG"
    fi
  else
    idle_ready_streak=0
    log "pool ok: $busy busy, $ready ready"
  fi
}

case "${1:-loop}" in
  cycle) cycle ;;
  loop)
    log "watchdog starting: interval=${POOL_INTERVAL:-180}s stuck-threshold=${STUCK_MINUTES}min"
    while :; do
      cycle
      sleep "${POOL_INTERVAL:-180}"
    done ;;
  *) echo "usage: pool_watchdog.sh [cycle|loop]"; exit 2 ;;
esac
