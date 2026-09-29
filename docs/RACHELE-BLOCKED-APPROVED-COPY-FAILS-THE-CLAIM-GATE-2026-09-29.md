PRIORITY: READ BEFORE THE NEXT RACHELE ATTEMPT

# RACHELE — DELIVERABLE CLEARED, GENERATION BLOCKED

    milestone SHA   50293a86   (local == origin/master, stamped before the run)
    account         2020 Companies / 2020companies.com
    contact         Rachele Crumpler, CFO, rachele-crumpler

    EMAIL VERIFICATION   CLEARED  -> verified, sendable
    GENERATION           BLOCKED
    SLACK                NOT POSTED

Nothing sent by this work. Provider writes 0, enrolments 0, prospect-facing
sends 0, campaign activation 0, `sending.live` false.
`work/campaigns.jsonl` unchanged.

---

## 1. THE PRIMARY VERIFIER CLEARED — AND THE OLD "ERROR" WAS NEVER A PROVIDER ANSWER

The handoff recorded `deliverable ERROR` and read it as the primary provider
failing. **It was not.** The stored evidence entry's own `reason` field is the
adapter's local refusal text:

    "Deliverable's response shape is undocumented and has not been read from
     a real answer, so a credit spent now might buy a..."

That is `deliverable.require_contract()` refusing **before any network call**,
because `DELIVERABLE_RESULT_SHAPE` was unset. The module's own docstring
records this: *"every Deliverable verification in the estate's history was a
local refusal rather than a parse failure"*, and the gate exists to make the
operator choose the spend — *"the operator sets one variable when they want
the calls made"*.

The operator authorised that spend for this address. The variable was set **in
the process only, never written to `config/.env`**, so the waterfall is not
left open for the other 159 contacts.

**Raw Deliverable answer:**

    provider     deliverable
    status       valid
    email        rcrumpler@2020companies.com
    catch_all    false
    at           2026-09-29T12:05:17+00:00

**Canonical decision (`verification.decide`, policy UNCHANGED):**

    state                   verified
    sendable                true
    reason                  "deliverable says valid"
    confirmation_count      3
    required_confirmations  2
    confirmed_by            contactout, deliverable, reoon
    disagreement            false
    cost                    1 credit

`lint.sendable` is now **True**. No policy, no `verification.py` and no
`lint.sendable` semantics were modified — the address cleared on the existing
policy's own terms once the primary finally answered.

Evidence persisted canonically through `verification.apply`, which is
append-only and RECOMPUTES the verdict from the merged list rather than
letting a caller assert one. `work/queue.jsonl` moved
`dd984f8a9e0d8508 -> a4add12fe42a5a61`; `work/campaigns.jsonl` unchanged.

---

## 2. WHY GENERATION IS BLOCKED

`generate.run(live=True, allow_whole_set_regeneration=True)` ran the real
entrypoint. It did **not** regenerate the emails. Record log, five times:

    Rachele Crumpler em1..em5: kept the stored copy, not overwritten -
    the stored copy is APPROVED and the approval hash is bound to exactly
    those words

`_protected_reason` enforces a standing **OPERATOR DECISION, 2026-09-27**: an
approved or sent step is never regenerated, because regeneration after
approval invalidates the hash the approval is bound to.

The approvals on `em1`-`em5` are:

    {"by": "claude", "at": "2026-09-13T21:47:32+00:00",
     "fingerprint": "2d94c3ced8e27065"}

**A machine self-approval from a session on 2026-09-13 — not a human one.**
The 2026-09-29 handoff states plainly that *no Slack approval artifact has
ever been posted*. So the rule's own rationale — *"the approval stays bound to
exactly the copy a person read"* — does not hold factually here. No person
read this copy. The mechanism cannot tell the two apart.

## 3. THE PART THAT MATTERS BEYOND RACHELE

**That protected, approved copy FAILS the claim gate that was merged today.**
Measured with `claims.check` at `50293a86` over the stored artifact:

    em1  REFUSED  customer-outcome claim, no licensed evidence
                  + "'profitability' is asserted about them and nothing
                     stored supports it"
    em2  REFUSED  customer-outcome claim, no licensed evidence
    em3  ok
    em4  REFUSED  customer-outcome claim, no licensed evidence
    em5  ok
    li1..li5  ok
    li6  ok  (orphan, see below)

The offending subjects are `"Driving Measurable Retail Growth at 2020
Companies"` and `"Enhancing Retail Performance with 2020 Companies"`.

So the record carries **approved copy that the current gate refuses, and the
approval is what prevents the canonical path from replacing it.** The approval
predates the gate. This is not specific to Rachele: any record approved before
TASK-914/917 may carry copy the gate would now refuse, protected from repair
by its own approval.

## 4. THE GATE WORKED, LIVE

The run's single reported op was the new claim authority refusing a freshly
generated draft:

    linkedin_note — "Rachele Crumpler's li5 note makes an unsupported claim
    (customer-outcome claim with no licensed evidence (missing: customer case
    studies, verified benchmarks))"

The unsafe new `li5` was refused and **not** stored; the previous `li5`, which
passes, was kept. That is TASK-917 doing its job on real generated copy rather
than on a fixture.

## 5. A SECOND, SMALLER DEFECT — ORPHAN li6

The canonical sequence resolves to ten steps:

    li1 em1 li2 em2 li3 em3 li4 em4 li5 em5

`cadencelibrary.LINKEDIN_WRITER_KEYS` is `li1..li5`. The record nonetheless
carries a sixth LinkedIn step, `li6`, left over from an older cadence shape:

    "happy to leave this here if the timing is off - would you mind pointing
     me to who handles project profitability at 2020 Companies?"

It is not in the sequence, nothing regenerates it, and it makes the stored
artifact 5+6 rather than the required 5+5. It should be dropped with a reason,
never silently deleted.

## 6. WHAT WAS NOT DONE, DELIBERATELY

- **No approval was revoked.** `approve.revoke()` exists and would unblock
  regeneration immediately. Using it would override a standing operator
  decision on a safety authority, so it needs the operator's explicit word.
- No copy was patched downstream. No unsafe sentence was rewritten by hand.
- No Slack post: there is no approval-ready artifact.
- No other prospect was selected.
- No batching, no canary, no enrolment, no send.

## 7. WHAT THE OPERATOR HAS TO DECIDE

The blocker is a decision, not a bug:

**Option A (recommended).** Authorise revoking the 2026-09-13 machine
approvals on `em1`-`em5` for `rachele-crumpler`, on the ground that no person
ever approved them and the copy fails the current gate. Then the canonical
path regenerates the whole set cleanly, and `li6` is dropped with a reason.

**Option B.** Treat machine self-approval as binding. Rachele's emails then
stay as they are — failing the claim gate — and the account cannot be made
approval-ready without operator-level intervention.

**The wider question either way:** how many other records carry pre-gate
approvals over copy that TASK-914/917 would now refuse? That is an estate
sweep, and it is a separate task, not this milestone.

## 8. UNCHANGED HARD GATES

The pre-existing `test_generate` retry defect (2 fail, 1 error) remains the
blocker before autonomous batching. TASK-564 and TASK-565 remain hard gates
before any live canary.
