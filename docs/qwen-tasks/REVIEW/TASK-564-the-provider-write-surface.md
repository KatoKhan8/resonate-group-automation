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

---

## RESULT

    STATUS       DONE
    COMMIT SHA   f3040b2d1adaf9046eb1f57a8caaf531daf3bdee
    TESTS        Read-only audit. No code changed. No tests run.
                 Conflict-marker check on src/, tests/, scripts/: clean.
    FILES        docs/PROVIDER-WRITE-SURFACE-2026-10-03.md (created)
    ARTIFACT     document — the enumeration table and findings
    FINDINGS     see below
    RISKS        The two-door architecture is unchanged: bisonfactory calls
                 eight EmailBison primitives directly, bypassing perform.
                 Compensating controls are factory-level, not the central
                 door's Authorization. This is documented, not new.
    RECOMMENDED  GLM verify the table against f3040b2d1.
    CLAUDE ACTION

### CLAIM / AUTHORITY / MEASURED AT / STATE

    CLAIM        every path that can mutate a prospect at EmailBison or
                 HeyReach is enumerated, with its enforcement stated
    AUTHORITY    the code at f3040b2d1, read directly; no empirical provider
                 probes (sending.live false, freeze active)
    MEASURED AT  qwen-worker-2-r9 f3040b2d1, 2026-10-03
    STATE        READ-ONLY AUDIT. No patching. Provider writes 0.

### THE THREE SEEDED FINDINGS

1. **`refuse_unauthorized_write` is ROOT-relative** — REFUTED. ROOT is used
   only for locating config/.env. The guard checks method, host, path and
   write-scope ContextVar; no filesystem path. The import-order weakness
   the 09-29 audit found (empty `_prospect_facing_hosts` until provider
   modules imported) is CLOSED: `KNOWN_PROSPECT_FACING_HOSTS` seeds both
   hosts at `providers/__init__.py` import time.

2. **Audit agent paused 487 by importing src** — CLOSED for every primitive.
   The transport guard fires before the socket on any unauthorised mutation
   to either prospect-facing host. The guard is armed at `providers` import.

3. **`_refuse_sequence_gate` has no tenant guard** — CONFIRMED, UNCHANGED.
   `offers._offers_path()` hardcodes Productive. No current risk (single
   tenant). A multi-tenant correctness defect and future canary blocker.

### THE SURFACE

SUPPORTED holds 16 operations (the 09-29 audit said 4; it was stale).
Two doors: `providerwrites.perform` (16 ops, full gate stack) and
`bisonfactory` direct calls (8 EmailBison primitives, factory-level gates
plus transport guard). HeyReach routes ALL writes through perform.

### WHERE A MISTAKE REACHES A REAL PERSON

1. `bison.create_lead` + `bison.attach_leads` via `_ensure_leads` — outside
   the central door, one step from a send
2. `bison.update_lead` — outside perform, wrong words on an attached lead
3. `bison.resume_campaign` — in SUPPORTED, through perform, a send if holds
4. `bison.set_limits/schedule/attach_senders/ensure_custom_variables` —
   staging, but determines blast radius of a later activation
5. Raw transport — governed only by the transport guard
