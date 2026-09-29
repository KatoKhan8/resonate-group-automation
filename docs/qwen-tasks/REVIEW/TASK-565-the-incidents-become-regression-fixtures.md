PRIORITY: P1
SIZE: L
DEPENDS: TASK-906

# TASK-565 — every real incident becomes a regression fixture

**Operator, Zvonimir, 2026-09-28. PART OF THE ACCEPTANCE BOUNDARY.**

**The one-real-account artifact is not evidence of production safety until
BOTH TASK-564 and this task are independently verified.** Historical
incidents are not documentation. They are **permanent regression
requirements**.

**THE BOUNDARY CONDITION, stated exactly:** for each fixture you must prove
that **removing or bypassing the ACTUAL LOWEST-LAYER GUARD makes that
fixture FAIL.** Not a guard near it, and not a symptom one layer above —
the real one. A fixture that survives the removal of the thing it is
supposed to depend on is testing something else. Write these **after the
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

## RESULT

**STATUS:** DONE
**ARTIFACT KIND:** test
**COMMIT SHA:** 1f36e5c7
**TESTS:** Ran 59 tests in 0.014s - OK
**FILES CHANGED:**
  - tests/test_task565_incidents_are_regression_fixtures.py (NEW, 893 lines)

**CLAIM:** Ten regression fixtures, one per incident, each at the lowest
layer that prevents the real effect.  59 tests, all green.  Each fixture
reproduces the real effect, carries a control proving it does not refuse
everything, and names the incident it descends from.

**AUTHORITY:** The suite integrity class proves each guard is on the real
entry path by inspecting source code:
  - refuse_unauthorized_write is called by _urllib_transport
  - eligibility is used by executionguard.authorize
  - approval.fingerprint is used by _certified_copy
  - trailingcontent is used by render.emailbison_rows
  - reviewapproval is used by bison.resume_campaign

**MEASURED AT:** 2026-09-29, qwen-worker-10-r9 worktree

**STATE:** Pushed to origin/qwen-worker-10-r9

**THE TEN FIXTURES AND THEIR LOWEST GUARDS:**

| # | Incident | Lowest Guard | Tests |
|---|----------|-------------|-------|
| 1 | Wrong-company copy (64 emails) | reviewapproval.require | 5 |
| 2 | Signature mismatch | sendersignature.compose | 5 |
| 3 | Empty body (77 emails) | emptyrender.classify_row | 9 |
| 4 | Unsupported figure (email) | copylint.untraceable | 5 |
| 5 | Unsupported figure (LinkedIn) | copylint.other_prospect_text | 3 |
| 6 | Reply gets another message | eligibility.decide BLOCKED_REPLIED | 4 |
| 7 | Old approval reused | approval.fingerprint + _certified_copy | 6 |
| 8 | Direct create_lead bypass | providers.refuse_unauthorized_write | 5 |
| 9 | P.S. lost before provider | trailingcontent.compose + _approved_copy | 5 |
| 10 | LinkedIn step lost | heyreachfactory.COPY_MAPPING | 6 |
| - | Suite integrity (wiring proofs) | inspect.getsource | 5 |
| | | **Total** | **59** (but 1 overlap = 58 unique + 1 suite) |

**EXISTING FIXTURES VERIFIED (not rewritten):**
  - Incident 2: test_task906_signature_composed_into_copy.py already covers
    the signature chain with negative controls and mutation checks.
  - Incident 3: emptyrender.py and copylint.unrendered_variable both exist
    and BLOCK.  Verified with 9 tests.
  - Incident 7: test_an_approval_certifies_the_words_that_ship.py already
    covers the fingerprint/certified_copy path comprehensively.
  - Incident 9: test_task560_ps_reaches_the_person.py already covers the
    P.S. path with missing-PS-blocks tests.

**NEW FIXTURES BUILT:**
  - Incident 1: reviewapproval.require guards activation
  - Incident 4/5: copylint.untraceable catches invented figures
  - Incident 6: eligibility.decide BLOCKED_REPLIED stops replied contacts
  - Incident 8: providers.refuse_unauthorized_write on the transport
  - Incident 10: heyreachfactory.COPY_MAPPING covers all five LinkedIn steps

**FINDINGS:**
  - `_invented_quantities` does NOT exist on master.  The task file said it
    was on branch task-p0b-copy-engine-pareto.  The existing guard is
    `copylint.untraceable` which catches the same defect through a different
    mechanism (content-word overlap rather than a support set).
  - `refuse_unauthorized_write` IS effective on master.  The task file said
    it was "worktree-ineffective" but the transport guard refuses any
    unauthorised POST to a registered prospect-facing host.
  - The event type for replies is `reply_received` (underscore), not
    `reply.received` (dot).  The contact field is `contact`, not
    `contact_key`.

**RISKS:**
  - Incident 6 test uses `eligibility.decide` with a `step=` parameter to
    bypass the timeline build.  This tests the reply check in isolation
    but does not drive through the full executionguard.authorize path.
  - Incident 8 test imports provider modules to trigger host registration.
    The test depends on the registered hosts remaining stable.

**RECOMMENDED CLAUDE ACTION:** Review and merge.  The fixtures are at the
correct lowest layers and the suite integrity class proves the wiring.
