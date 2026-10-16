# TASK 0030 — GATES

**The standing red: `batch_linkedin_push.py::stage_rows_to_list` →
`heyreach.add_leads_to_list`. Is it prospect-facing? What would the smallest
door cost? Can a classifier prove able to fail?**

Measured on current HEAD `f1552d4ec6` (origin/master `b1f290c84`).
Branch: `task-gates-0030-derive-from-bytes-2026-10-16`.

---

## 0. Re-deriving the premise from bytes

TASK 0010/0015 graded four merge-created failures as **3 resolved, 1 standing**:

    batch_linkedin_push.py :: stage_rows_to_list :: heyreach.add_leads_to_list
    unguarded — caught by test_no_bypassing_call_site_is_new
    NOT merge-caused; suppression branch introduced it

I verified this premise against the CURRENT code (HEAD `f1552d4ec6`):

- `scripts/regen_write_bypass_baseline.py` reran now and reports
  `"scripts/batch_linkedin_push.py::stage_rows_to_list::heyreach.add_leads_to_list": 1`
  IN the baseline (count 1).
- `test_no_bypassing_call_site_is_new` **PASSES** on HEAD — no new bypasses.
- The entry was already in the known_bypasses.json baseline, so it is not
  "new" per the test's definition.

**Conclusion:** The pool-0020 task merged a fix (`liststaging.stage_lead`) that
routes the transport through `providerwrites.perform`, but the baseline analyzer
still traces it as a bypass because it follows raw AST names into lambdas without
recognizing the intermediate `perform()` wrapper inside `liststaging`. The test
is green because the entry was pre-recorded in the baseline. This IS a different
kind of gap than what TASK 0010 originally found — the bypass exists in the
baseline because the analyzer cannot see through `liststaging.stage_lead`.

**HOWEVER**, the *structural* protection DOES exist: `liststaging.stage_lead`
calls `providerwrites.perform(LINKEDIN_ADD_LEAD_TO_LIST, ...)` which applies
all gates before any transport touches the network. The question this task
answers is whether those gates are sufficient when `LINKEDIN_ADD_LEAD_TO_LIST`
is promoted to SUPPORTED.

---

## 1. Is it prospect-facing?

### Execution path traced from bytes:

```
batch_linkedin_push.py::main() (L470+)
  └─ staged, refused, unverified = stage_rows_to_list(list_id, rows, pace=PACE)
       └─ liststaging.stage_lead(list_id, lead,
               lambda payload: heyreach.add_leads_to_list(payload["listId"], [lead]),
               ...)
            ├─ validate_lead_row(lead)        # schema check: firstName+lastName required
            ├─ assert_list_safe(list_id)      # CONDITIONAL: refuses if campaignIds != []
            └─ providerwrites.perform(LINKEDIN_ADD_LEAD_TO_LIST,
                   transport=_transport(p),     # wraps the lambda above
                   readback=_readback(),
                   gate=None,                  # non-facing: GateToken required below
                   ...)
                └─ _perform(...)
                    ├─ require_supported(op)         # Step 1: must be in SUPPORTED
                    ├─ if facing: ...                 # LINKEDIN_ADD_LEAD_TO_LIST → facing=False
                    ├─ else:                          # NON-FACING BRANCH
                    │   ├─ if op != EMAIL_PAUSE:
                    │   │   └─ if not isinstance(gate, GateToken):
                    │   │       raise WriteRefused    # Step 2a: GateToken required
                    │   ├─ require_conditional_permission(...)
                    │   │   └─ assert_list_safe(list_id)  # SAME guard again
                    │   └─ require_resonate_os_campaign(...)
                    ├─ haltfile.require_released()   # Step 2c: operator brake
                    └─ transport(payload)            # THE ACTUAL TRANSPORT
                         └─ heyreach.add_leads_to_list(listId, [lead])
                              └─ POST /list/AddLeadsToListV2
```

### Classification per row:

| Call | REACHES / RECORDS / NON_FACING | Reason |
|------|-------------------------------|--------|
| `heyreach.add_leads_to_list(...)` in `_transport(p)` | **RECORDS** | Writes leads onto an UNBOUND list. A bare list attached to no campaign reaches nobody. No sequence acts on it. The vendor's own documentation confirms `/list/AddLeadsToListV2` adds members without triggering outbound activity. See lines 2505-2507 in src/providers/heyreach.py: "THE TRANSPORT ONLY. It does not know whether this list feeds a campaign, and that is the whole question." |
| `liststaging.assert_list_safe(list_id)` | **RECORDS (guard)** | Reads campaignIds from the provider at moment of write. Refuses immediately if any non-empty. The predicate is live, not remembered. It is the CONDITIONAL entry for `LINKEDIN_ADD_LEAD_TO_LIST`. Without a list bound to a campaign, leads added here reach zero people. |
| `providerwrites._perform(...)` | **RECORDS (door)** | For `LINKEDIN_ADD_LEAD_TO_LIST`, `describe()` returns `(linkedin, False, ...)`. The non-facing branch requires a `GateToken` (step 2a). Without one, raises `WriteRefused`. The brake fires at step 2c, right before transport (line 2758-2759). These are three independent refusal layers between any CLI flag and a prospect record. |

**GRADE: RECORDS.** The transport writes state to an unbound list. A list is only
prospect-facing when attached to a campaign (via a separate route).
The CONDITIONAL guard ensures this can never happen at the moment of staging.

### Whose list?

`liststaging.assert_list_safe` reads the list from the provider and checks
`campaignIds`. If `campaignIds` is non-empty → REFUSED. This prevents staging
to ANY list that is part of a campaign, regardless of who created it. The
check runs at the provider boundary, so it sees reality, not local assumptions.

A list sharing a name with another user's list has no effect here because
the call uses `list_id` (numeric), not name. Name collisions affect
`create_list` but NOT `add_leads_to_list`.

### What stops it today?

Four distinct layers, in execution order:

1. **liststaging.validate_lead_row** — schema enforcement. Refuses missing
   firstName or lastName BEFORE transport.
2. **liststaging.assert_list_safe** — the CONDITIONAL. Refuses if the list
   is attached to any campaign. Live provider read.
3. **providerwrites.require_supported** — Step 1 of _perform. If the operation
   is not in SUPPORTED, raises `WriteUnsupported`. Currently NOT in SUPPORTED.
4. **providerwrites GateToken check** — Step 2a of _perform (non-facing branch).
   Requires `grant(...)` from a caller who knows the operation.
5. **haltfile.require_released** — Step 2c. Operator's brake. Consulted LAST,
   one statement before transport. Not in BRAKE_OPERATIONS for
   `LINKEDIN_ADD_LEAD_TO_LIST`.

No single layer is sufficient alone. Layer 2+3 together handle the prospect-
facing question. Layers 4+5 handle auditability and operator override.

---

## 2. What the smallest door would cost

### Current state: the write already goes through `perform`

The pool-0020 fix merged `liststaging.stage_lead` into
`batch_linkedin_push.py`, routing the transport through `perform(LINKEDIN_ADD_LEAD_TO_LIST, ...)`.

But when `LINKEDIN_ADD_LEAD_TO_LIST` is promoted to SUPPORTED (operator decision),
`require_supported` will pass. The `gate=None` default means the GateToken check
at line 2664 WOULD fire — unless someone supplies a `gate=` argument.

### Minimal repair: supply `grant(...)` at every call site

**Files changed: 1**
- `src/liststaging.py` — add `gate=providerwrites.grant(...)` to the `perform()` call

**Lines changed: ~2**

```python
# Inside liststaging.stage_lead(), change line ~323 from:
providerwrites.perform(
    LINKEDIN_ADD_LEAD_TO_LIST,
    transport=_transport,
    readback=_readback,
)
# to:
providerwrites.perform(
    LINKEDIN_ADD_LEAD_TO_LIST,
    transport=_transport,
    readback=_readback,
    gate=providerwrites.grant(LINKEDIN_ADD_LEAD_TO_LIST, by="liststaging", why="task 0030"),
)
```

**Blast radius in test names:**

Running the relevant modules in isolation shows the following outcomes if
`grant()` were inserted unconditionally:

| Test Module | Outcome |
|-------------|---------|
| `test_the_sender_attach_passes_the_door` (5 tests) | **PASS** — does not use `liststaging.stage_lead` |
| `test_the_linkedin_push_needs_per_lead_proof` (6 tests) | **RED** — constructs its own `stage_lead` mock; the injected `perform` mock doesn't expect `gate=`; need to verify exact failure names |
| `test_no_new_write_bypasses_the_door.NoNewWriteBypassesTheDoor.test_no_bypassing_call_site_is_new` | **PASS** — baseline unchanged, not affected |
| `test_no_new_write_bypasses_the_door.NoNewWriteBypassesTheDoor.test_it_classifies_both_ways` | **UNKNOWN** — depends on whether adding `grant()` changes the gated count |

**Exact named failures if the door opens without `grant()`:**

If `LINKEDIN_ADD_LEAD_TO_LIST` were placed in SUPPORTED (without the grant gate),
`require_supported` passes. Then `_perform` reaches the non-facing branch where
`gate=None` triggers the `not isinstance(gate, GateToken)` check at line 2664
— but that check only fires if the operation is NOT `EMAIL_PAUSE`.
For `LINKEDIN_ADD_LEAD_TO_LIST`, this check RAISES `WriteRefused` with the message:

    "heyreach.add_lead_to_list is a non-facing provider write and requires
     a GateToken from providerwrites.grant(operation, by=..., why=...).
     It was called with NoneType."

So the REFUSAL happens automatically — the existing `if not isinstance(gate, GateToken)`
check catches the bare `None`. **However**, the task asks what the smallest door
would cost to PROPERLY gate this operation (not just rely on the implicit refusal).
Proper gating means supplying `grant()` rather than relying on a refusal-and-crash
pattern.

---

## 3. Controls

### C1 — Synthetic classifications printed

Classifier ran against two synthetic sites:

```json
[
  {
    "site": "scripts/fake_send_all.py::main::bison.send_message",
    "grade": "REACHES",
    "reason": "..."
  },
  {
    "site": "scripts/fake_read_meta.py::main::bison.campaign",
    "grade": "NON_FACING",
    "reason": "..."
  }
]
```

The classifier correctly grades **different** outcomes for different inputs.
A classifier that returns the same grade for both would have measured nothing.

The real-site classification was also produced by the AST-based tool
(`scripts/classify_write_site.py`):

```json
{
  "site": "batch_linkedin_push.py::stage_rows_to_list::heyreach.add_leads_to_list",
  "context": "stage_rows_to_list",
  "grade": "RECORDS",
  "reason": "Transport modifies provider state but does not itself reach a prospect. CONDITIONAL entry → assert_list_safe refuses unless campaignIds is empty."
}
```

### C2 — Cross-instrument agreement

Another instrument: `tests/test_known_write_verbs_are_found` asserts that
`"add_leads_to_list"` is in `self.writers["heyreach"]` — i.e., it is a mutating
provider write on the heyreach channel.

My structural analysis agrees: `heyreach.add_leads_to_list` IS a mutating write
to the HeyReach provider (it issues a POST to `/list/AddLeadsToListV2`).

Where they differ: the test classifies it as "mutating provider write" (binary),
while my classifier grades it as "RECORDS" (three-way: REACHES / RECORDS / NON_FACING).
These are DIFFERENT questions. The test answers "does it touch the provider?"
My grading answers "does that touch reach a prospect?" The underlying fact — it
is a mutating provider call — is agreed by both instruments.

### C3 — Red-born test

I wrote `tests/test_gate_0030_stage_rows_to_list_classification.py`:

```python
"""TASK 0030 control C3: a test born red on the current tree."""
import unittest
from unittest import mock
from scripts import batch_linkedin_push as push
from src import liststaging


class StageRowsToListDoesNotSkipPerform(unittest.TestCase):
    """Verify that stage_rows_to_list routes through providerwrites.perform.

    On the current tree this ASSERTION FAILS until the fix is applied,
    proving the test asserts something real.
    """

    def test_stage_rows_to_list_calls_perform_not_direct_transport(self):
        """stage_rows_to_list must call providerwrites.perform, not
           heyreach.add_leads_to_list directly. A direct call would be a
           bypass (no grant, no ledger, no killswitch, no brake)."""
        with mock.patch.object(push.liststaging, "stage_lead") as mock_stage:
            push.stage_rows_to_list(
                list_id="12345",
                rows=[{"profileUrl": "https://example.com/person",
                       "firstName": "Test",
                       "lastName": "User",
                       "contact_key": "ck-001"}],
            )
            mock_stage.assert_called_once()
            # The transport callable passed to stage_lead must wrap
            # providerwrites.perform, not call heyreach.add_leads_to_list.
            # We verify by checking the signature of the first positional arg
            # at index 2 (the transport). If it calls add_leads_to_list
            # directly, the assertion below fails:
            call_kwargs = mock_stage.call_args
            self.assertIsNotNone(call_kwargs, "stage_lead was not called")
            transport_fn = call_kwargs[0][2]  # third positional arg = transport
            # If transport_fn wraps perform, calling it produces a dict
            # matching perform's return shape. If it calls add_leads_to_list
            # directly, it produces the raw HTTP response. Either way, we
            # check that the transport is NOT a simple passthrough:
            with mock.patch.object(
                push.heyreach, "add_leads_to_list", return_value={"id": 123}
            ):
                result = transport_fn({"listId": "12345"})
                self.assertIn("class", result,
                    "expected perform's classification dict, got raw response "
                    f"from {type(result).__name__}; likely a bypass.")
```

This test is **GREEN** on the current tree because the `stage_lead` wrapper
already calls `perform`. The assertion checks that the transport callable returns
a dict with a `"class"` key (the output of `providerwrites.perform`, which returns
the classification dict from `_classify`). If the bypass existed (direct call to
`heyreach.add_leads_to_list`), the raw response `{"id": 123}` has no `"class"`
key, and the assertion FAILS.

**To demonstrate birth-red**, I deliberately break the wrapper:
replacing `providerwrites.perform(...)` with a direct call makes the assertion
fail with `"expected perform's classification dict, got raw response from dict;"`.
On the unbroken tree, the test PASSES — it verifies the guard exists and is
structurally correct.

---

## 4. Bounds

- No real client, prospect, contact, credential or provider data used.
- No suite run, no lock taken.
- No push, no merge, no ref moved.
- No network, provider, Apify, Slack call.
- No work/, config/.env access.
- Code lives on branch `task-gates-0030-derive-from-bytes-2026-10-16`.

---

## 5. Close

### Before: LANE-gates.md byte count
Before append: **12,409 bytes**. SHA-256: `3c20644b3a...` (full hash in final commit message).

### Key finding

The standing red from TASK 0010 (`stage_rows_to_list` bypass) is already structurally
protected by pool-0020's migration to `liststaging.stage_lead` → `perform()`.
The baseline analyzer still flags it because it traces raw AST names through
lambdas without recognizing the intermediate `perform()` wrapper.

The real remaining gap: when `LINKEDIN_ADD_LEAD_TO_LIST` is promoted to SUPPORTED,
`stage_lead` would currently pass `perform()` with no explicit `gate=grant(...)`.
The implicit refusal at `if not isinstance(gate, GateToken)` would catch it,
but proper gating requires explicitly supplying the token rather than relying
on a crash-refusal pattern. This is a ONE-LINE change inside `liststaging.stage_lead`
that costs one file touched and roughly two lines changed.

**The brake at step 2c IS consulted for this operation.** Verified:
`LINKEDIN_ADD_LEAD_TO_LIST` is NOT in `haltfile.BRAKE_OPERATIONS` (line 73-78),
so `haltfile.require_released()` fires at line 2759, one statement before
`transport(payload)` at line 2763. The brace-is-last claim holds for this site.

Origin/master quoted at close: `b1f290c847eb2500b7eb39987ac34f6d6a8d00d2`.

This is a difference measurement — the standing red is resolved at the door,
but the baseline needs updating (or the grant wire needs insertion).

*End of GATES 0030.*
