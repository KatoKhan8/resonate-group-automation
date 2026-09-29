PRIORITY: P0
SIZE: L
DEPENDS:

# TASK-564 — enumerate every path that can mutate a prospect at a provider

**Operator, Zvonimir, 2026-09-28. P0. A HARD CANARY GATE.**

It runs in PARALLEL and must not unnecessarily block Qwen implementation —
but it is **not optional and not P1**. **No zero-write artifact may be
called production-safe, canary-ready, or accepted until this task is
INDEPENDENTLY VERIFIED and every production-active prospect-facing write
primitive is accounted for.**

**Why it carries that weight, in the operator's own terms:** if the seeded
finding is true — `refuse_unauthorized_write` is `ROOT`-relative and so did
not protect worktree execution — that is **the same class of architectural
failure that allowed the 503/504/505 incident: a path existed outside the
safety boundary.** Sixty-four emails carrying another agency's pitch went to
real people through such a path.

## IF YOU FIND A BYPASS: STOP AT THE FINDING

**READ-ONLY. NO PATCHING. Do not silently fix a bypass inside the audit** —
a fix buried in an audit is a change nobody reviewed, and it destroys the
evidence of what the surface looked like.

    1. STOP at the finding.
    2. CLASSIFY it - what mutation it permits, and whether it is reachable
       from a production entry point today.
    3. Write the SMALLEST REMEDIATION BRIEF as its own task.
    4. Then continue the enumeration.

A bypass found and left recorded is worth more than a bypass quietly closed.

## What to enumerate
Every code path that can cause a **prospect-facing mutation** at EmailBison or
HeyReach:

    create / attach / enrol a lead      update variables or content
    schedule                            activate · resume
    LinkedIn enrol · LinkedIn message   raw HTTP client methods

## Per primitive, one row, every column filled

    entry point                     the function, by name
    callers                         who reaches it - and ZERO CALLERS is a
                                    finding, not a blank
    central enforcement present     does it go through providerwrites.perform,
                                    or around it
    operator approval required      is an Authorization object required
    canonical plan required         must the payload derive from a SequencePlan
    copy / claim gates              which gates run before it, by name
    suppression checked             yes / no / partially, and by what
    ledger effect                   what row it writes, and whether it writes
                                    one on the refusal path too
    callable from a scratch script  could `import src` + call reach it
    production active               is it reachable from a production entry
                                    point today

**An UNKNOWN cell is a legitimate answer and is more useful than a guess.**
Mark it UNKNOWN and say what could not be read.

## Three findings to start from — confirm or refute each, do not assume
1. **`refuse_unauthorized_write` is `ROOT`-relative and protects nothing when
   called from a worktree.** Confirmed by artifact 2026-09-28. So every agent
   that "proved" production safety by working on a copy was safe *because a
   copy was used*, not because the barrier would have caught a mistake.
2. **An audit agent paused live campaign 487 on 2026-09-20 simply by importing
   `src` and calling through.** That is why the write guard exists. Establish
   whether that route is closed for every primitive, or only for pause.
3. **`bisonfactory._refuse_sequence_gate` has no tenant guard**, while
   `offers.py` returns Productive's offers for every client — so one client's
   ladder is enforced against every client's push.

## Deliverable
`docs/PROVIDER-WRITE-SURFACE-2026-09-28.md` — the table, plus a short list of
the rows where a mistake would reach a real person. **GLM verifies the table
against your exact branch head SHA.**

## Rules
No patching, no refactoring, no new abstractions. Provider **reads** only where
needed; **writes 0**. `sending.live` false, freeze active, every Resonate
campaign paused. Production `work/` read-only, verified by sha256 from a fresh
process. Suite logs outside the repository. Commit, push, and verify the remote
with `git rev-parse` **after your last commit**. Report **CLAIM / AUTHORITY /
MEASURED AT / STATE** and your head SHA.
