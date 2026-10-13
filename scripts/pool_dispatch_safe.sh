#!/usr/bin/env bash
# Dispatch a task to a Qwen worker WITHOUT touching anything that already exists.
#
## WHY THIS IS A SEPARATE SCRIPT AND NOT A PATCH TO pool.sh
#
# `pool.sh dispatch` does three things that destroy work, and the base-ref
# patch (55c3c3ab) left all three in place:
#
#   git push -q origin "$cur"              pushes the worker's CURRENT branch,
#                                          whatever it is, with no review
#   git checkout -q -B "$br" "$BASE"       RESETS that branch to the base,
#                                          discarding whatever it carried
#   prompt: git push -u origin $br         orders the worker to push the reset
#                                          branch over the old one
#
# Measured 2026-10-12: that cycle orphaned 1,352 reflog tips across all twelve
# r9 branches and left 29 finished results reachable from no remote ref.
#
# So this script never pushes, never resets, and never writes into an existing
# worktree or branch. Each dispatch gets:
#
#   * a FRESH worktree created from the pinned base SHA
#   * a NEW local branch name that cannot already exist
#   * its own claim file in its own ledger
#
# If any precondition fails, nothing is created and the log says ABORT or
# REFUSED. The word DISPATCHED is written only after a worker has actually
# been started.
#
## USAGE
#
#   pool_dispatch_safe.sh <TASK-ID> <task-filename>
#
# Environment:
#   SAFE_BASE_REF    base to work from            (default origin/master)
#   SAFE_ROUND       round label for ref names    (default s1)
#   SAFE_ROOT        where worktrees/claims/logs  (default <integration dir>)
#   SAFE_MAIN        repo to read tasks from      (default production checkout)
#   SAFE_DRY_RUN     run every guard, start no worker
#   SAFE_QWEN        qwen launcher                (default the standard path)

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SAFE_MAIN="${SAFE_MAIN:-C:/Users/Zvonimir/Desktop/resonate-group-automation}"
SAFE_ROOT="${SAFE_ROOT:-C:/Users/Zvonimir/Desktop/resonate-integration-2026-10-12/dispatch}"
SAFE_ROUND="${SAFE_ROUND:-s1}"
SAFE_BASE_REF="${SAFE_BASE_REF:-origin/master}"
SAFE_QWEN="${SAFE_QWEN:-C:/Users/Zvonimir/AppData/Local/qwen-code/bin/qwen.cmd}"
CLAIMS="$SAFE_ROOT/claims"
WTDIR="$SAFE_ROOT/wt"
LOGS="$SAFE_ROOT/logs"
LOG="$LOGS/dispatch.log"
mkdir -p "$CLAIMS" "$WTDIR" "$LOGS" 2>/dev/null

say ()     { echo "$(date +%H:%M:%S) $*" | tee -a "$LOG"; }
refuse ()  { say "REFUSED $TID: $*"; exit 1; }
abort ()   { say "ABORT $TID: $*"; exit 2; }

TID="${1:-}"
TASKFILE="${2:-}"
[ -n "$TID" ] && [ -n "$TASKFILE" ] || { echo "usage: $0 <TASK-ID> <task-filename>"; exit 64; }
case "$TID" in TASK-[0-9]*) ;; *) echo "bad task id: $TID"; exit 64 ;; esac

# ---------------------------------------------------------------- 1. the base
# Resolved ONCE to a SHA. A branch name can move mid-round, and then the guard
# compares the checkout against a different commit than the brief named.
BASE_SHA="$(git -C "$SAFE_MAIN" rev-parse --verify "${SAFE_BASE_REF}^{commit}" 2>/dev/null || true)"
[ -n "$BASE_SHA" ] || refuse "SAFE_BASE_REF='$SAFE_BASE_REF' does not resolve to a commit"

# ------------------------------------------------- 2. the task exists on base
git -C "$SAFE_MAIN" cat-file -e "$BASE_SHA:docs/qwen-tasks/TODO/$TASKFILE" 2>/dev/null \
  || refuse "$TASKFILE is not committed under TODO/ at $SAFE_BASE_REF ($BASE_SHA)"

TASK_BLOB="$(git -C "$SAFE_MAIN" rev-parse "$BASE_SHA:docs/qwen-tasks/TODO/$TASKFILE")"

# --------------------------------------------- 3. nobody else holds this task
# Read BOTH ledgers. The production one is read-only here: this script never
# creates, moves or releases a claim that belongs to pool.sh.
[ -e "$CLAIMS/$TID.claim" ] && refuse "already claimed in this ledger"
if [ -e "$SAFE_MAIN/work/claims/$TID.claim" ]; then
  refuse "held in the PRODUCTION ledger: $(tr -d '\n' < "$SAFE_MAIN/work/claims/$TID.claim")"
fi

# ------------------------------------------- 4. no finished result anywhere
# Including refs/preserve: a result whose branch copy was destroyed is still a
# result, and re-running the task would duplicate work that already exists.
if py -3 "$SCRIPT_DIR/finished_tasks.py" "$SAFE_MAIN" --cache "$SAFE_ROOT/finished-tasks-cache.json" --has "$TID" >/dev/null 2>&1; then
  refuse "a finished result for $TID already exists on a ref (refs/remotes, refs/heads or refs/preserve)"
fi

# ------------------------------------------------- 5. a UNIQUE output target
# A new branch name per round+task. `git worktree add -b` fails if the branch
# exists, so an accidental re-dispatch cannot land on somebody else's branch.
OUT_BRANCH="dispatch/$SAFE_ROUND/$TID"
OUT_WT="$WTDIR/$SAFE_ROUND-$TID"
git -C "$SAFE_MAIN" rev-parse -q --verify "refs/heads/$OUT_BRANCH" >/dev/null 2>&1 \
  && refuse "output branch $OUT_BRANCH already exists - refusing to reuse it"
[ -e "$OUT_WT" ] && refuse "output path already exists: $OUT_WT"

# -------------------------------- 6. this script writes to NO existing worktree
# It creates its own. Every pre-existing worktree - dirty, clean, unpushed or
# otherwise - is left exactly as it is. The check below exists so that a future
# edit reintroducing "reuse worker dir X" cannot pass silently.
if [ -n "${SAFE_REUSE_WORKTREE:-}" ]; then
  refuse "SAFE_REUSE_WORKTREE is set; reusing an existing worktree is not supported"
fi

# ------------------------------------------------------- 7. create and verify
# A LINKED WORKTREE SHARES THE OBJECT STORE AND THE REF NAMESPACE, so no brief
# can stop a worker pushing: it has git, the remote and the credentials.
# Measured 2026-10-13: the first real dispatch under this script produced
# refs/heads/dispatch/s1/TASK-270 ON THE REMOTE, because the worker pushed
# despite being told three times not to. A brief is not a control.
#
# So the workspace is a standalone CLONE WITH NO REMOTE. The worker cannot
# push because there is nowhere to push to, cannot write a shared ref, and
# cannot reach another worktree. Results are collected by fetching FROM the
# clone afterwards, which is a read.
git clone -q --no-hardlinks "$SAFE_MAIN" "$OUT_WT" 2>/dev/null || abort "could not clone into $OUT_WT"
for r in $(git -C "$OUT_WT" remote); do git -C "$OUT_WT" remote remove "$r" 2>/dev/null; done
if [ -n "$(git -C "$OUT_WT" remote)" ]; then abort "clone still has a remote"; fi
git -C "$OUT_WT" checkout -q -b "$OUT_BRANCH" "$BASE_SHA" 2>/dev/null || abort "could not create $OUT_BRANCH at $BASE_SHA in the clone"

GOT="$(git -C "$OUT_WT" rev-parse HEAD 2>/dev/null || true)"
if [ "$GOT" != "$BASE_SHA" ]; then
  rm -rf "$OUT_WT"
  
  abort "checkout landed on $GOT, expected $BASE_SHA"
fi
if [ -n "$(git -C "$OUT_WT" status --porcelain 2>/dev/null)" ]; then
  rm -rf "$OUT_WT"
  
  abort "freshly created worktree is not clean"
fi
git -C "$OUT_WT" cat-file -e "HEAD:docs/qwen-tasks/TODO/$TASKFILE" 2>/dev/null || {
  rm -rf "$OUT_WT"
  
  abort "task file absent in the created worktree"
}

# ------------------------------------------------------------- 8. claim, ours
printf '{"task":"%s","round":"%s","base":"%s","task_blob":"%s","branch":"%s","worktree":"%s","claimed_at":"%s","pid":%s}\n' \
  "$TID" "$SAFE_ROUND" "$BASE_SHA" "$TASK_BLOB" "$OUT_BRANCH" "$OUT_WT" \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$$" > "$CLAIMS/$TID.claim"

if [ -n "${SAFE_DRY_RUN:-}" ]; then
  say "DRYRUN-OK $TID base=$BASE_SHA blob=$TASK_BLOB branch=$OUT_BRANCH wt=$OUT_WT"
  rm -rf "$OUT_WT"
  
  rm -f "$CLAIMS/$TID.claim"
  exit 0
fi

# ------------------------------------------------------------- 9. the brief
PROMPT="YOUR ONLY TASK IS $TID, file docs/qwen-tasks/TODO/$TASKFILE

You are in a FRESH worktree created for this task alone:
  $OUT_WT
on a NEW local branch: $OUT_BRANCH, at base $BASE_SHA.

Read docs/qwen-tasks/TODO/$TASKFILE and do exactly what it says. The task
file's own rules outrank anything general you believe.

HOW TO SAVE WORK - READ THIS TWICE:
- COMMIT LOCALLY, OFTEN: git add -A && git commit -m '...'
- DO NOT PUSH. No 'git push', not with -u, not with --force, not ever.
- DO NOT touch any other branch or worktree. Do not checkout -B, do not
  reset, do not rebase onto anything, do not amend a commit you have already
  recorded in a result block.
- Your branch $OUT_BRANCH is yours alone and nothing else will reset it, so a
  local commit is durable. Pushing is what destroyed 29 finished results on
  2026-10-12.

Finish by appending a RESULT BLOCK (STATUS, COMMIT SHA, TESTS, FILES CHANGED,
FINDINGS, RISKS, RECOMMENDED CLAUDE ACTION) to the task file, git mv it to
DONE/, commit. Then STOP. Do not push.

HARD RULES:
- NO provider calls of any kind. No HeyReach, EmailBison, Apify, Slack, or any
  network service. Reads included: assume you have no credentials.
- No sends, no campaign creation or activation, no adding leads.
- Never commit config/.env, an API key or a token. Env var NAME only.
- Never commit unhashed PII - names, domains, emails, profile URLs, reply text.
- Never merge into master. Never push.
- Read test exit codes OFF THE PROCESS, never through a pipe.
- Never weaken a gate, lint rule or sender limit to pass.
- Do not report a PREDICTED result. Run it, measure it.
- A zero and a wrong lookup look identical from outside. Prove the field you
  read is the right one before reporting a zero.
- Boundary you may not cross: write it under FINDINGS, commit, stop.

IF A STEP TAKES MINUTES: launch it detached, redirect to a file, and poll with
INCREASING sleeps - never the identical check back to back, which the CLI's
loop detector halts a session for. Commit before you start waiting."

( cd "$OUT_WT" && QWEN_CODE_SUPPRESS_YOLO_WARNING=1 "$SAFE_QWEN" --approval-mode yolo "$PROMPT" \
    > "$LOGS/$SAFE_ROUND-$TID.log" 2>&1
  echo "$(date +%H:%M:%S) FINISHED $TID exit=$? branch=$OUT_BRANCH" >> "$LOG" ) &

say "DISPATCHED $TID base=$BASE_SHA blob=$TASK_BLOB branch=$OUT_BRANCH wt=$OUT_WT pid=$!"
exit 0
