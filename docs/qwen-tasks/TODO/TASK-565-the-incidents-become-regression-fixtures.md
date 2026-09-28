PRIORITY: P1
SIZE: L
DEPENDS: TASK-906

# TASK-565 — every real incident becomes a regression fixture

**Operator, Zvonimir, 2026-09-28. A CANARY gate.** Write these **after the
Brand IQ artifact exists and before any canary.** Do not start earlier — the
artifact is the priority and these must not compete with it.

## The rule for where each one lives
**Each fixture goes at the LOWEST LAYER THAT PREVENTS THE REAL EFFECT.** Not at
the layer where the bug happened to be found. A test that asserts a symptom one
layer above the guard passes when the guard is removed — that exact failure was
measured here on 2026-09-28: a bypass mutation left a test green because a
*different* guard produced a HELD instead of a BLOCK.

## The ten
1. **Wrong-company copy sent from a Productive mailbox** — 64 emails carrying
   another agency's pitch, signed with the operator's name, from 503/504/505.
2. **Signature not matching the mailbox owner.**
3. **Empty body from unresolved variables** — 77 emails with an empty subject
   and a `<p></p>` body, 2026-09-23.
4. **An unsupported figure on an email.**
5. **An unsupported figure on a LinkedIn message.**
6. **A prospect who replied "no thank you" receiving another message** —
   happened 2026-09-23, seven minutes after the refusal.
7. **An old approval reused after the copy changed.**
8. **A direct `create_lead` / attach bypassing the factory.**
9. **The P.S. lost before it reaches the provider.**
10. **A LinkedIn step lost before HeyReach** — see TASK-548.

## STEP ONE: mark which already exist, and VERIFY rather than assume
My own reading, **all UNVERIFIED — check each before writing anything**:

    2   negative controls exist on branch task-p0a-signature-chain (d93b0674),
        NOT on master
    3   `unrendered_variable` exists; whether it BLOCKS is unverified
    4,5 `_invented_quantities` exists on task-p0b-copy-engine-pareto
        (556593a0) and carries the defect TASK-557 fixes
    8   `refuse_unauthorized_write` exists but is worktree-ineffective
    1,6,7,9,10  believed ABSENT

**Do not rewrite a fixture that already exists** — extend it or say it is
covered. **Do not claim one exists without running it.**

## Each fixture must
- reproduce the **real effect**, not a paraphrase of it
- **FAIL if its guard is removed** — prove that with a mutation, restore
  byte-identical by sha256
- carry a **control** proving it does not refuse everything
- name the incident it descends from, in the test's own docstring, so the next
  person knows why it exists

## Rules
No prospect data in a tracked file — these are real incidents and real people;
use the shapes, never the identities. **Never weaken a gate to make a fixture
pass.** Provider writes 0, `sending.live` false, freeze active. Suite logs
outside the repository; compare the baseline **as sets**; derive a suite verdict
from a `Ran N tests` line, never from `$?`. Commit, push, verify the remote
after your last commit. Report **CLAIM / AUTHORITY / MEASURED AT / STATE**.
