# Workforce scorecard

**Evidence only.** Every row is a branch and a commit, a test count taken from
the diff, and an accepted/returned verdict taken from whether the commit is an
ancestor of `master`. **Task files are not evidence** — `claim_task.py --status`
currently reports twelve tasks whose branch state disagrees with master's, all
marked stale, which is why this file reads git instead.

Created 2026-09-24 14:4x Zagreb, at master `989ab174`. Updated in every
two-hourly status post under WORKFORCE.

---

## 1. QWEN — 8 DISPATCHED, 0 ACCEPTED, AND ALL 8 WORKERS ARE DEAD

**No Qwen process is running.** Last pool-log activity was 2026-09-23
21:37–22:22; there are zero `qwen` processes on this machine now. The
2026-09-24 morning handoff said "7 expected still running" and told the reader
to check before assuming — the check says none.

**Nothing they produced is on master.** Every commit below is on its own
`qwen-worker-*-r58` branch and is *not* an ancestor of master, which is
correct per the three-session rule — workers push to their own branch and
production reviews and merges. It also means **the accepted count is zero**,
and it has been zero since they were dispatched.

| task | commit | branch | diff | tests added | status |
|---|---|---|---|---|---|
| 266 | `cf1515fb` | qwen-worker-r58 | 1 file, +64 | **0** | delivered, NOT accepted |
| 267 | `440fa8a3` | qwen-worker-2-r58 | 2 files, +683 | 19 | delivered, NOT accepted |
| 268 | `0ae7f40c` | qwen-worker-3-r58 | 5 files, +947 | 19 | delivered, NOT accepted |
| 269 | `9d141ccb` | qwen-worker-4-r58 | — | 0 on the SHA-fill commit | delivered, NOT accepted |
| 270 | `7526ab4f` | qwen-worker-5-r58 | — | 0 | **self-blocked on TASK-247, correctly** |
| 271 | `c921c134` | qwen-worker-6-r58 | 4 files, +811 | 27 | delivered, NOT accepted |
| 272 | `78df2ddc` | qwen-worker-7-r58 | 5 files, +298 | 25 | delivered, NOT accepted |
| 273 | `1d86356f` | qwen-worker-8-r58 | 1 file, +451 | 37 | delivered, NOT accepted |
| 274 | `26eb2cd0` | qwen-worker-5-r58 | 2 files, +197 | **0** | delivered, NOT accepted |

**Returned: none.** Nothing has been reviewed, so nothing has been returned
either — "not accepted" here means *not yet looked at*, and saying it was
rejected would be a stronger and false claim.

**Two deliveries carry no tests at all** (266, 274). 274 is a knowledge-pack
document, where that is reasonable. 266 is `learningrules` — a module with an
approval guard and no test of it.

### Under FOCUS: 3 workers, lane 1 only

Keep, and they are the three that serve a push today:

- **(a) Apify research-pack adapter** — company posts, open roles, person
  posts, 30-day cache, cost per account. No task exists yet; needs writing.
- **(b) copy lint** — fact per step, no shared first lines, never-invent
  traceability, 5-step check. No task exists yet; needs writing.
- **(c) TASK-268 LinkedIn match validation** — already delivered at `0ae7f40c`
  with 19 tests and never reviewed. **Review it before re-dispatching it.**

Parked in TODO, one line each:

- **266** learning rules A/B/C — delivered, no tests, frozen under FOCUS.
- **267** LLM tiebreaker for FLAGGED domains — delivered with 19 tests; serves
  supply and is the strongest candidate to un-park first.
- **269** one derivation, three call sites — delivered, trivial diff.
- **270** blocked on TASK-247, which is in TODO and not `ready`. Unblocking
  means doing 247 first. Parked.
- **271** COMPLIANCE.md and the compliance gate — delivered, 27 tests.
- **272** explainable verdicts — delivered, 25 tests.
- **273** adapter conformance suite — delivered, 37 tests.
- **274** cross-channel stop in the knowledge pack — delivered, no tests.

---

## 2. GLM — THE THREE REVIEWS DID NOT RUN

The 2026-09-23 night handoff recorded three reviews as "queued and now
unblocked, the gate code having landed". **They did not run.**

Evidence: the newest GLM artifact in `docs/` is dated **2026-09-22** —
`GLM-REVIEW-BATCHPUSH-2026-09-22.md`, `GLM-REVIEW-SOURCING-2026-09-22.md`,
`GLM-REVIEW-ATTRIBUTION-2026-09-21.md`. The incident gate landed on
**2026-09-23** (`5c9fb515`). There is no GLM review of the empty-render guard,
the account-level stop, or the research-pack renderer.

    review                        findings raised    accepted
    empty-body push guard         DID NOT RUN        -
    account-level reply stop      DID NOT RUN        -
    research-pack renderer        DID NOT RUN        -

Under FOCUS, GLM reviews only lane-1 code. Two of the three qualify: the
**empty-render guard** and the **account-level stop**. The research-pack
renderer waits until the renderer exists.

---

## 3. GROK — ONE ARTIFACT, AND IT WAS LOAD-BEARING

| artifact | date | decision it unblocked |
|---|---|---|
| `docs/GROK-PROVIDER-RESEARCH-2026-09-23-NIGHT.md` | 09-23 | **Control (a) must read the provider's rendered queue back.** EmailBison's variable-injection timing, empty-variable behaviour and any pre-send render readback are all *undocumented by the vendor*, so the guard could not rest on a guarantee. This is the finding the whole incident gate is built on. |
| `docs/GROK-RESEARCH-2026-09-22.md` | 09-22 | prior week |
| `docs/GROK-CONVERSATION-ATTRIBUTION-2026-09-21.md` | 09-21 | prior week |

**Idle**, per FOCUS, unless a push is blocked on a provider question.

There is one such question open and it is **not** currently blocking a push:
ISSUE-030, whether EmailBison exposes any route that detaches a lead from a
campaign. It blocks the remove-lead verb, which FOCUS has frozen. If that
thaws, this is the Grok question.

---

## 4. THE THING THIS FILE EXISTS TO PREVENT

Two handoffs in a row reported the Qwen pool as running on the strength of
having dispatched it. The workers had been dead for hours. A dispatch is not a
worker, a delivery is not an acceptance, and a task file saying DONE is not
either of those — `claim_task.py --status` reports twelve tasks whose branch
state disagrees with master's and calls them stale, which is the same defect
one layer down.

Every row here is a commit you can check.
