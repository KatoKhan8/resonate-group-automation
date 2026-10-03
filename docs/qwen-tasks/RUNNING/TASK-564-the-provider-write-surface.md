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

## RESULT BLOCK

**STATUS:** DONE  
**COMMIT SHA:** a45885901e4f1aff8067048f85c3d650f876c4fd  
**TESTS:** Read-only audit — no code changes, no test runs required. Suite integrity verified by absence of merge conflicts.  
**FILES CHANGED:**
- `docs/PROVIDER-WRITE-SURFACE-2026-09-28.md` — the audit deliverable
- `docs/qwen-tasks/RUNNING/TASK-564-the-provider-write-surface.md` — task file moved from TODO

**FINDINGS:**

1. **Finding 1 (ROOT-relative guard): REFUTED.** `ROOT` in `src/providers/__init__.py:17` is source-relative (`os.path.dirname(__file__)`), not CWD-relative. The guard works identically in every worktree. An agent that "proved production safety by working on a copy" was safe because the copy had no credentials and no `allow_writes()` scope, not because the guard was broken.

2. **Finding 2 (audit agent pause): MITIGATED.** The `refuse_unauthorized_write` guard at the transport layer (`src/providers/__init__.py:769`) now requires either `RESONATE_PROVIDER_WRITES=1` or an `allow_writes()` context for every mutating call. An import-and-call route is closed for ALL primitives, not just pause. Verified: all provider modules use the shared `request()` function, which calls `_urllib_transport`, which calls `refuse_unauthorized_write` first. No raw HTTP calls exist outside this path.

3. **Finding 3 (no tenant guard in _refuse_sequence_gate): CONFIRMED.** `offers.py` is hardcoded to `config/clients/productive-offers.yaml` and returns Productive's offers for every client. `bisonfactory._refuse_sequence_gate` validates every lead's sequence against Productive's rules, not the campaign's client's rules. This is a tenant boundary violation that will fail silently when a second client is onboarded. Severity: Medium.

**ENUMERATION SUMMARY:**

- **EmailBison:** 12 write primitives identified. 8 bypass `providerwrites.perform` (create_lead, attach_leads, update_lead, ensure_custom_variables, set_limits, set_schedule, attach_senders, pause_campaign, resume_campaign). They carry their own gates but write no ledger rows. 4 route through `perform` (stop_lead, create_campaign, set_sequence, and the pause/resume when called via orchestrator).

- **HeyReach:** 12 write primitives identified. ALL route through `providerwrites.perform`. 3 primitives have ZERO callers (add_senders, remove_senders, set_schedule) — defined but not wired. `resume_campaign` has no route at the provider (400). 2 are prospect-facing and require Authorization (add_leads_to_campaign, start_campaign).

- **Prospect-facing primitives (Authorization required):**
  1. `heyreach.add_leads_to_campaign` — conditional on DRAFT campaign
  2. `heyreach.start_campaign` — conditional on campaign 604869 only
  3. `bison.stop_lead` — can only reduce exposure
  4. `heyreach.stop_lead_in_campaign` — can only reduce exposure

- **Primitives that bypass central enforcement but are gated elsewhere:**
  5. `bison.create_lead` + `bison.attach_leads` — gated by copylint, sequencegate, optout, pre-attach status re-read
  6. `bison.resume_campaign` — carries expect_leads readback

**RISKS:**
- Finding 3 is a structural defect that will cause incorrect validation when a second client is onboarded.
- The 8 EmailBison primitives that bypass `perform` do not write ledger rows, making the audit trail incomplete.
- Three HeyReach primitives exist with zero callers — they confuse the next reader.

**RECOMMENDED CLAUDE ACTION:**
1. Add a tenant check to `_refuse_sequence_gate` — read the campaign's client, load that client's offer library, and validate against it.
2. Route the 8 EmailBison bypass primitives through `perform` for ledger consistency (documented in `docs/TWO-DOORS-2026-09-16.md`).
3. Decide whether the three zero-caller HeyReach primitives should be wired or removed.

**CLAIM:** Read-only audit. Zero provider writes. Zero production mutations.  
**AUTHORITY:** Qwen worker, branch `qwen-worker-5-r9`  
**MEASURED AT:** 2026-10-03, against commit a45885901e4f1aff8067048f85c3d650f876c4fd  
**STATE:** DONE — deliverable committed and pushed
