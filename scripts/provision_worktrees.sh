#!/usr/bin/env bash
# Give every Qwen worktree the credentials and read-only inputs it needs.
#
# WHY THIS EXISTS. `config/.env` and `work/` are BOTH gitignored, deliberately:
# one holds credentials and the other holds 300 real companies and 92 real
# contacts that are not ours to publish. The consequence nobody had written
# down is that a fresh worktree has NEITHER, so a worker dispatched into one
# cannot reach a provider or read a lead.
#
# TASK-316 hit exactly that on 2026-09-25 and reported five blockers, all of
# them "this file exists only on another worktree". The task was written
# correctly and could not run.
#
# WHAT IS COPIED, AND WHAT IS NOT.
#
# Credentials: copied, because a worker with no key cannot call a model. They
# land in a gitignored path in a checkout of the same repo on the same machine
# under the same user, so this moves nothing across a trust boundary.
#
# READ-ONLY INPUTS ONLY. `work/queue.jsonl` is NOT copied: it is live
# production state with a cross-process lock, and twelve workers writing their
# own copies would produce twelve divergent truths. A task that needs the queue
# runs in the main checkout.
set -u
MAIN="C:/Users/Zvonimir/Desktop/resonate-group-automation"
INPUTS=(
  "work/sample50-built.json"
  "work/ten-pages-data.json"
  "work/v2-data.json"
  "work/v2_run.py"
  "work/v2_pages.py"
  "work/ten_pages.py"
  "work/ten_pages_html.py"
  "work/Productive/productive_ICP_safe_to_send (1).csv"
)
n=0
for d in "$MAIN"/../resonate-qwen-*; do
  [ -d "$d" ] || continue
  case "$d" in *scratch*) continue ;; esac
  mkdir -p "$d/config" "$d/work/Productive"
  cp -f "$MAIN/config/.env" "$d/config/.env" 2>/dev/null
  for f in "${INPUTS[@]}"; do
    [ -f "$MAIN/$f" ] && cp -f "$MAIN/$f" "$d/$f" 2>/dev/null
  done
  # research packs are large; link the newest few rather than all
  for p in $(ls -t "$MAIN"/work/researchpack*.jsonl 2>/dev/null | head -3); do
    cp -f "$p" "$d/work/" 2>/dev/null
  done
  n=$((n+1))
done
echo "provisioned $n worktrees"
