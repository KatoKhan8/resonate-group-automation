#!/usr/bin/env bash
# Dispatch NAMED tasks to named workers, one each.
#
# WHY THIS EXISTS, BESIDE pool.sh
#
# `pool.sh sweep` hands every free worker whatever `next_ready` returns - the
# highest-priority unclaimed task with deps met. That is right when the
# backlog is a queue and wrong when the operator has named the eight tasks
# they want run now: on 2026-09-23 the ready list led with TASK-245/249/250/264
# while the instruction was TASK-266..273, and a sweep would have started four
# tasks nobody asked for and left four of the named ones unclaimed.
#
# Everything else is pool.sh's: the worktree lock, the atomic claim, the
# prompt, the push-before-reset safety. This file only chooses the pairing, so
# there is one dispatch path to keep correct rather than two.
#
#     scripts/pool_dispatch.sh resonate-qwen-worker:TASK-266 resonate-qwen-2:TASK-267 ...
#
# A pair whose worktree is locked or whose task is already claimed is SKIPPED
# and reported, never forced - both of those mean somebody else is on it.

set -u

# Source pool.sh's definitions WITHOUT running its `case` dispatcher.
MAIN="C:/Users/Zvonimir/Desktop/resonate-group-automation"
# shellcheck disable=SC1090
source <(sed '/^case "${1:-sweep}"/,$d' "$MAIN/scripts/pool.sh")

[ "$#" -gt 0 ] || { echo "usage: pool_dispatch.sh <worker>:<TASK-NNN> ..."; exit 2; }

rc=0
for pair in "$@"; do
  wt="${pair%%:*}"
  tid="${pair##*:}"
  case " ${WORKERS[*]} " in
    *" $wt "*) ;;
    *) echo "  UNKNOWN worker $wt"; rc=1; continue ;;
  esac
  task="$(file_for "$tid")"
  if [ -z "$task" ]; then
    echo "  $wt  $tid NOT IN TODO/ - not dispatched"
    rc=1
    continue
  fi
  # THE WORKER CHECKS OUT master, NOT THIS WORKING TREE.
  #
  # `file_for` looks in MAIN's TODO/, which includes files that are written
  # but not yet committed. `dispatch` then runs `git checkout -B <br> master`
  # in the worktree, so a worker sent to an uncommitted task file finds
  # nothing and reports the task does not exist. Measured 2026-09-23: TASK-274
  # was staged and not committed, and the worker spent 29 seconds proving its
  # absence - correctly, and for nothing.
  #
  # Ask git what master actually carries, not what the filesystem shows.
  # ONE BASE REF, ONE CHECK, SHARED WITH pool.sh.
  #
  # This used to ask about the local `master` branch while `dispatch` checked
  # out `origin/master` - two refs that are usually equal and were not
  # guaranteed to be. Both now ask `task_on_base`, which tests the single
  # pinned POOL_BASE_SHA that the worker will actually check out.
  if ! task_on_base "$task"; then
    echo "  $wt  $tid IS NOT COMMITTED UNDER TODO/ AT $POOL_BASE_REF ($POOL_BASE_SHA) - not dispatched"
    rc=1
    continue
  fi
  if dispatch "$wt" "$(branch_for "$wt")" "$tid" "$task"; then
    :
  else
    echo "  $wt  SKIPPED ($tid already claimed, or worktree locked)"
    rc=1
  fi
done
exit "$rc"
