# HANDOFF — GLM INDEPENDENT REVIEWER — 2026-09-26

Read this for **role and history only**. It is not a description of current
master and must never be used as one.

## ROLE

GLM is an independent reviewer and red-team critic. GLM is **not** the primary
implementer.

- **Claude** orchestrates and triages.
- **Qwen** implements.
- **GLM** independently reviews important safety, architecture, grounding and
  integration claims **when requested**.

Do not create work merely to keep GLM busy. Capacity is not a reason for a
review; a specific claim worth attacking is.

## COMPLETED REVIEW

| | |
|---|---|
| Review branch | `review/glm-b333697` |
| Reviewed master | `b33369748a91435f23524ede40ad74b1c54fb7cf` |
| Review commit | `db9c2b179c415f2610574bd2bca29abf919f1ec8` |
| Review document | `docs/glm-reviews/canary-readiness-b333697.md` |
| Review worktree | `C:\Users\Zvonimir\glm-review\glm-review-b333697` |

The review worktree is **intentionally still registered**. It holds the exact
SHA every citation in the review was taken at, which is what makes a finding
reproducible line by line. Do **not** remove it unless Claude explicitly says
triage and reproduction are complete.

## AUDIT RESULT AT REVIEW TIME

| Area | Status at `b333697` |
|---|---|
| Approval identity | REVIEWED — NO DEFECT FOUND (code level) |
| Provider write gate | DEFECTS FOUND |
| Suppression + cross-channel stop | DEFECTS FOUND |
| Cadence single source | DEFECTS FOUND |
| Spend ceiling | DEFECTS FOUND |
| Account identity | PARTIALLY REVIEWED |

Counts at audit time:

- P0: **1**
- P1: **4**
- UNVERIFIED: **4**
- RUNTIME VERIFICATION REQUIRED: **4**
- FALSE-CONFIDENCE TESTS: **3**

**These are HISTORICAL findings stamped to the reviewed SHA.** Claude and Qwen
may already have fixed or superseded some of them. A future GLM session **must
not** assume they are still current. Always fetch current `origin/master` and
independently re-check a finding before reporting it again.

This is not hypothetical. Master had already moved from `b333697` to `2fdb556`
by the time this handoff was written, and `2fdb556`'s own subject line is
"Integrate TASK-346: a model call can now be refused at a ceiling, and nothing
yet asks it to" — which speaks directly to one of the four P1s. Re-check, do
not re-report.

## MOST IMPORTANT HISTORICAL FINDING

P0 at audit time: **`EMAIL_RESUME` could bypass the prospect-facing
revalidation path**, and therefore skip the suppression re-read and the related
safety enforcement that every other sending verb passes through.

Handed to Claude for independent reproduction and triage. Do **not** reopen or
reimplement it automatically in a future session. Check current master first.

## REVIEW DISCIPLINE

Every future GLM review must:

- run in its **own isolated clean worktree** — never branch, switch, stash,
  reset or commit in the primary checkout or in a Qwen worker worktree (the
  primary checkout is routinely dirty; that is normal and is not a blocker,
  it is the reason not to work there)
- stamp an exact `START_MASTER_SHA` and take every citation from that SHA
- cite `file:line` plus the exact symbol
- give one reproducible **read-only** command per confirmed finding
- distinguish `CODE-LEVEL VERIFIED` from `RUNTIME VERIFICATION REQUIRED`, and
  never infer runtime behaviour from source: the long-lived loops import at
  process start and do not reload, so a merge is not a deploy
- put anything without a citation under `UNVERIFIED SUSPICIONS`, never under
  P0/P1
- never use an empty `work/` probe as evidence about production — a worktree's
  `work/` is nearly empty, so probes there return a confident, error-free zero.
  "Disconnected" is a static call-graph conclusion (imports, callers, call
  sites), never a probe result
- re-fetch master at the end and mark anything the interim commits may have
  touched as `POTENTIALLY SUPERSEDED — CLAUDE MUST RECHECK`
- state area coverage explicitly: "NO DEFECT FOUND" requires citing the code
  that enforces the invariant, or it is downgraded to PARTIALLY REVIEWED. Zero
  P0 is only credible when coverage is evidenced
- push **review-only** branches, one document per commit
- never merge, never modify production or provider state, never create Qwen
  tasks
- never invent work because GLM capacity is available

## PRODUCTION FREEZE

In force unless the operator explicitly changes it:

- no sends
- no activation
- no resume
- no enrolment
- no attachment
- no provider-changing tests
- no automatic offer approval

Read-only verification is allowed when explicitly authorized.

## NEXT SESSION START

Do **not** continue from assumptions in this handoff. Start with:

    git fetch origin
    git log -1 --format=%H origin/master

and stamp that SHA. Machine state wins over every document, this one included.

Read this handoff for role and history. Read the latest Claude/production
handoff for current execution state. Do not assume `b333697` resembles current
master.
