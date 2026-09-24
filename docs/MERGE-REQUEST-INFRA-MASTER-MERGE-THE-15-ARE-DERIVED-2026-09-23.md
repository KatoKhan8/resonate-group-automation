# Merge request — master merged, both hand-written monitor tables deleted

Branch `infra`. Merge commit `f23d461a`, parents `c3a19132` (infra) and
`5c9fb515` (master). Pushed; `origin/infra` agrees.

---

## 0. THE HEADLINE, AND THE THING THE OPERATOR ASKED TO BE STATED

**Production hand-edited BOTH monitor tables to 15 entries tonight** for the
incident gate, after blank emails went out of campaign 497 — found BY HAND,
because nothing was watching it. `src/supervisor.py`'s constant gained
491–498; `scripts/start_monitors.py`'s list gained 496, 497, 498.

**Both hand-written lists are DELETED by this merge, not merged.** They were
the second and third copies of a table this branch had already made one, and
the derived table supersedes them.

**The 15 must come from the derived table**, and that is now a test rather
than an assurance:
`tests/test_the_derived_table_is_the_incident_gates_15.py`, which asserts the
derived set at today's registry against those 15 **by name**.

---

## 1. THE TEST, AND THE ANSWER IT ACTUALLY RETURNED

The operator asked for a test that the derived set at today's registry
**equals** those 15 by name. It does not equal them. It is a **bounded
superset of 20**, and the five extras are the argument for deriving rather
than a defect in it. This is the one place this merge request departs from
the instruction, so it is stated plainly rather than buried.

Measured against the real registry (26 rows, read-only, never written):

    derived total                    20
    every one of production's 15     PRESENT
    extras                            5, each named below

### 1a. `+493` — the campaign the hand-written list forgot

493 is `approved`, in the same batch as 491–498, and **is not in the list a
person typed while fixing an incident caused by campaigns missing from the
list a person typed**. Nobody decided to leave it out.

This is the whole case for a derived table, and it arrived unprompted within
an hour of the lists being written.

### 1b. `+451, +481, +484, +485` — four the registry calls `draft`

They are watched, and a rule that dropped them would be wrong, because **the
registry cannot be trusted to say what is sending**. 497's own row says:

    status = approved        launch.state = not_launched

while it was sending the blank emails this gate exists for. A rule that
retired a watcher on `status` or `launch.state` would read 497's row and
retire the watcher for the campaign in the incident.

So the rule watches every campaign that has a provider id. Over-watching
costs provider calls. Under-watching costs an unwatched sender.

**There is a way to make the derived set equal 15 exactly, and it is the
wrong fix.** `test_a_draft_is_still_watched_because_497_sent_while_not_launched`
exists to fail if somebody makes it.

### 1c. Why the whole live vocabulary misses the rule

Worth knowing before reading the `derived` reasons in the table: the
registry's statuses are `approved`, `draft` and `awaiting_approval`, and
**none of them is in `LIVE_STATUSES` or `FINISHED_STATUSES`.** Every campaign
therefore takes the `unknown status` branch, which watches. That branch was
written as a safety net and is currently carrying the entire table.

It is doing the right thing. But it means the grace window and the
leads-in-sequence refusal — the interesting half of the rule — **are not
exercised by production data at all today.** Filed for production: either the
registry should carry provider status, or the rule should stop pretending to
read one. **Question for the operator, §5.**

---

## 2. A DEFECT IN THIS BRANCH'S OWN DERIVED HALF, FOUND BY THE MERGE

`scripts/heyreach_watch_loop.py` hardcodes `PROVIDER_ID = 605732` and takes
no `--campaign`. **Which campaign it watches is therefore not a fact about
the registry** — and the derived half was deriving it from the registry.

The registry holds **five** heyreach rows. The derived half kept the
lowest-named, 594061 — the paused canary — and the entry's heartbeat resolved
to:

    verify looks for   work/heartbeat/heyreach-594061.json
    the loop writes    work/heartbeat/heyreach-605732.json

`cold_start --verify` would have polled a file nothing writes and reported
the LinkedIn monitor **down forever**. That is precisely the defect
`46474c6c` fixes for the static half, **arriving a second time through the
derived half** — and `46474c6c` is still not on master (four handoffs now).

### 2a. It was green the whole time, and why

`MonitorTableTest.ROWS` invents a registry with exactly one heyreach row, and
it is 605732. The fixture agreed with the loop, so the suite could not see
it. A fixture that invents the convenient input is not a witness. The bug was
visible only against the real file, and only because this merge read it.

### 2b. The fix

The entry is **declared, not derived**: `supervisor.HEYREACH_CAMPAIGN`, one
place, with `test_the_declared_heyreach_campaign_is_the_loops_own` asserting
it equals the loop's own constant so the two cannot drift. The loop's
constant is read **by `ast`, not imported** — importing the loop pulls in
providers.

`campaign_monitors` now derives bison only, and keeps the per-provider table
shape for the next provider whose loop does take a `--campaign`.

---

## 3. VERIFICATION

    tests/test_the_derived_table_is_the_incident_gates_15.py      7 green
    tests/test_supervisor.py                                     20 green
    tests/test_the_estate_comes_back_after_a_reboot.py           28 green
                                                                 55 total

**Mutations — four of five kill the new tests:**

    heyreach campaign back to 594061 (the original defect)   FAILED (5)
    heyreach derived from the registry again                 FAILED (3)
    unknown status no longer watched                         FAILED (4)
    slack_followup renamed out of the static half            FAILED (2)
    RETIRE_AFTER_DAYS = 0                                    OK  <- see below

**The fifth does not kill them, and should not.** No campaign in today's
registry is in a finished status (§1c), so the grace window is never
consulted by this test's data. Claiming 5/5 here would be claiming coverage
this file does not have. `MonitorTableTest` covers that path on fixture rows.

**No real registry is committed.** The test's rows carry provider campaign
ids and statuses only — the same ids already written in both tables' comments
— and no client, name, address or contact. The real file was copied to a
scratch directory to be read, and `work/` was never written.

---

## 4. WHAT THIS MERGE DID NOT TOUCH

`config/.env`, `work/`, `src/providers/*` — unchanged, verified against the
staged diff. No live writes. No timeout wrappers. Master is untouched: this
is `infra` only.

The two renamed task files under `docs/qwen-tasks/` came from master's side
of the merge, not from this session.

---

## 5. FOR THE OPERATOR — TWO DECISIONS

1. **Is 20 the right table, or should it be 16?** The four `draft` campaigns
   (451, 481, 484, 485) are the only genuinely arguable extras. Dropping them
   needs a signal that is *not* `status` or `launch.state`, because 497
   disproves both. Until such a signal exists the answer is to watch them.
   **493 is not arguable — it should be watched, and production's list
   omitting it is the bug this table prevents.**

2. **The registry's status vocabulary does not match the rule's** (§1c). The
   grace window and the leads-in-sequence refusal are unexercised by real
   data. Should the registry carry provider status, or should the rule stop
   reading one it never sees?

Neither blocks the next increment.
