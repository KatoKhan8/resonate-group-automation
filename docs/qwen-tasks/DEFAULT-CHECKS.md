# Default checks — the idle-worker list

**STANDING RULE, operator, 2026-09-24. Idle workers are never idle.**

This list lives beside `TODO/` and is **refilled every status cycle** so that
it never drops below **ten** entries. When a worker has no claimed task, it
takes one of these instead of waiting, and instead of helping itself to a
`TODO/` file that was dispatched to somebody else.

## The three rules that make this safe

1. **A default check NEVER changes running code.** Its output is a short doc
   under `docs/` or a new task file under `TODO/`. If the check finds
   something that needs fixing, the fix is a TASK, written by the worker and
   left for dispatch. A worker that "just fixed it while I was in there" has
   made an unreviewed change to a live system.
2. **A default check is a READ.** No provider write, no send, no campaign
   mutation, no write to `work/`, no killswitch, no approval semantics. Reads
   at EmailBison, HeyReach, Apify and the rest are allowed and are the point.
3. **Findings that save time or cost become tasks the same day.** A finding
   that sits in a terminal is not a finding.

## Claiming one

Take the **lowest-numbered UNCLAIMED** check. Append your worker id and the
date to its line in this file and commit that, the same way a task file is
moved to `RUNNING/` — so the other seven can see the claim. A check may be
re-run later by somebody else; that is the point of a rolling list. It is
claimed for the cycle, not forever.

---

## QWEN — walk a live process, or measure a stage

The Qwen form is: **walk one live process end to end against provider truth
and report every mismatch with evidence**, or **measure one pipeline stage's
throughput and cost per row and propose the cheapest change that speeds it
up.** Evidence means the provider's own named response fields and the rows in
`work/*.jsonl` — never a fixture, and never a count with no names.

    DC-01  A campaign's queue vs our store. Pick one active campaign. Read
           the provider's lead list; read our store's rows for it. Report
           present-at-provider-absent-from-store, the reverse, and
           state-disagreements. Say which evidence decided ours vs the
           client's for every row - a seat is not a campaign.
           CLAIMED BY: ______

    DC-02  A watcher's heartbeat vs its own log. 21 monitors are derived and
           reported UP on two witnesses. For one watcher: is the heartbeat
           fresher than the log's last line, and is the log's last line
           fresher than the process start? A merge is not a deploy - about
           fifteen loops import at start and never reload, so check the
           module mtime against the process start time before believing a
           watcher is running the code you just read.
           CLAIMED BY: ______

    DC-03  A cohort's READY count vs the S5 journal. Take one cohort. Count
           READY in the store, count verified rows in the S5 journal, and
           reconcile. The funnel numbers have been wrong all week in one
           direction: every headline came from a stage that had not asked the
           next stage's question. Print the identity, not a summary.
           CLAIMED BY: ______

    DC-04  Throughput and cost of S5 verification. Measured at 0.40
           addresses/s, 351 minutes for 8,387, and that single number is what
           stands between the estate and the 19,612. Measure it again, per
           provider, and propose the cheapest change - each provider's
           documented concurrency limit, with the source.
           CLAIMED BY: ______

    DC-05  Throughput and cost of one other stage of your choice (S3 re-judge,
           MX, S7 render, the push). Rows/second, USD/row, and the single
           cheapest change. Cost per row comes from the spend ledger rows the
           run wrote, never from a price page.
           CLAIMED BY: ______

    DC-06  Campaign ordering. Order campaigns by PROVIDER ID, numerically.
           `created_at` is null on the campaigns that actually send, so any
           report sorted by it silently drops or reorders the live ones.
           Check every report and script that lists campaigns and name the
           ones that sort by `created_at`.
           CLAIMED BY: ______

    DC-07  Queue hygiene. `docs/qwen-tasks/TODO/` vs what is actually
           dispatchable. As of 2026-09-23 21:33, TASK-192 and TASK-262 sat in
           `TODO/` on master AND in `RUNNING/` inside qwen-worker, qwen-6,
           qwen-7 and qwen-8. Report dispatchable / claimed-elsewhere /
           superseded, with the worktree and mtime that says so. READ other
           worktrees; never write to one.
           CLAIMED BY: ______

## GLM — one merged safety path, looking for the bypass

Findings only, counted on the scorecard. The question is always the same:
**how can this pass without having checked anything?**

    DC-08  One gate or stop of your choice (the blank gate, the collision
           gate, the killswitch, `_refuse_unvariabled_leads`, the write-scope
           refusal). Find a way it can be bypassed, or a way it can PASS
           WITHOUT CHECKING. A stop against a finished lead returns "already
           settled" - a pass by construction - and that is the shape of the
           first blank-content halt, which alerted and halted nothing and read
           as working.
           CLAIMED BY: ______

    DC-09  One reconciliation or ownership path. `inbound._positively_not_ours`
           compares an EmailBison event's campaign id against a set of
           HeyReach ids without asking which provider it came from, so a reply
           on our own 491 reads as "provably not ours" and is dropped. Look
           for the same shape elsewhere: an id compared across providers, a
           set membership standing in for a resolution.
           CLAIMED BY: ______

    DC-10  One guard module with no caller. The recurring defect:
           `heyreach.linkedin_sequence` built the whole LinkedIn graph and had
           no caller; `extract_prospect_text` was correct and never called;
           `outreachclaims` is the authority on claims about us and has no
           consumer on the send path; `run_with_copylint` matched only its own
           `.pyc`. Pick a guard, trace the import graph to the real entry
           point, and report by name what does and does not reach it. An
           import-graph assertion, not a text grep.
           CLAIMED BY: ______

## GROK — one provider or cost question, with sources

    DC-11  A documented rate or concurrency limit that would speed a stage up,
           with the vendor page it came from. Undocumented behaviour counts
           if it is reproduced and the reproduction is shown.
           CLAIMED BY: ______

    DC-12  A cheaper endpoint or a batch API for something we currently call
           one row at a time, with the price and the source. Say what it would
           save at 19,612 and show the arithmetic.
           CLAIMED BY: ______

---

## Two things that make a default check worthless

**A count instead of a list.** `74 failures` and `74 failures` compare equal
while a different 74 tests fail — the 2026-09-23 host comparison hid 17
host-only failures behind two counts that differed by exactly 17. Report the
SET and diff it BOTH directions.

**A green suite as the evidence.** Fixtures get invented and then mock the
buggy function: about thirty tests were green against three Apify actor ids
that answer 404, because the cassette and the code agreed with each other and
neither agreed with Apify. **Read the provider and read `work/*.jsonl`.**

And one that makes a check a measurement of nothing: **a worktree has its own
stale `work/`.** Most worker worktrees have no `work/queue.jsonl` at all, and
the one that did held a copy 37 minutes behind production. Point `WORKSPACES`
at a copy of production's taken for the check, and name the copy and its
timestamp in the result.

---

## Refill log

    2026-09-24 late   Lane E   list created, 12 entries, 0 claimed.
                               Refill when it drops below 10.
