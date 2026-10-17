
---

## 2026-10-17 POOL 0200 — direct add_leads_to_list write leaves NO ledger row

**Task**: queue/pool/0200-ledger-blind-bypass.md (this brief)
**Base SHA**: b28652900 (CRLF tree flavour, 15 CR in requirements.txt)
**step= fix (6b0462bec)**: INCLUDED in base
**Tree state after run**: clean (only untracked scratch files)

### Question

Does a direct `heyreach.add_leads_to_list` write — the shape ARM A took when
the `except TypeError` handler in write_linkedin_lead_variables.py:157-170
bypassed the gate — leave a row in the provider-writes ledger?

### Method

Synthetic fixture, no provider transport (mocked at `heyreach._write_body`
seam), isolated store via `store.use_directory(tmp)`. Two arms:

- **ARM A (gated path)**: `liststaging.stage_lead(SYNTH_LIST_ID, SYNTH_ROW,
  transport=..., by="pool-0200-arm-a")` → `providerwrites.perform()` →
  `_ledger()` writes a row on every exit.
- **ARM B (direct)**: `heyreach.add_leads_to_list(SYNTH_LIST_ID, [SYNTH_ROW])`
  called directly, bypassing `perform()` entirely.

Instrument controls: a direct call to `_ledger()` writes a row (proves the
instrument can print a row); an empty ledger reads zero rows (proves the
instrument can print no-row). Both controls pass.

### Results

Both arms reached the transport (ARM A: 1 transport call, ARM B: 1 transport
call). The difference is what happened around the transport call.

```
ARM A (gated):
  outcome    : unverified (readback could not confirm, mock fixture)
  ledger row : YES, 1 row
  operation  : heyreach.add_lead_to_list
  by         : None (stage_lead passes by inside grant(), not as kwarg)
  step       : UNKNOWN (no Authorization object; the step= fix is working)
  key        : UNKNOWN (same reason)

ARM B (direct):
  outcome    : None (no exception, transport returned synthetic success)
  ledger row : ZERO
  transport  : called (synthetic success returned)
```

### Verdict

**LEDGER-BLIND**

A direct `heyreach.add_leads_to_list` call leaves no trace in the
provider-writes ledger. The bypass is invisible to the spend audit: no row,
no `by=`, no `step=`, no `key=`, nothing. A ledger reader cannot tell that
the write happened.

The gated path, even when it ends in `unverified` (because the mock readback
does not populate the list), still writes a row. The two paths are not
indistinguishable — one leaves a row and the other does not. That is exactly
the definition of LEDGER-BLIND.

### What this means

The operator's picture of what a bypass costs in auditability now has a
number: **zero rows per bypass**. The 2026-10-01 incident log names 4684b25b0372
as one lead that went through the direct path; the ledger has no record of it.

The `step=` fix (commit 6b0462bec) is in the base and working correctly — it
records UNKNOWN when there is no Authorization, loudly, never a guess. But
the fix only applies to writes that go through `perform()`. A direct call
does not go through `perform()`, so the fix does not reach it.

### Files

- `scratch/pool-0200-harness.py`: measurement harness (created, not committed)
- `scratch/pool-0170-arm-a-with-handler.py`: read-only (the bypass shape)

### Recommendation

The bypass is invisible to the audit. The operator may wish to consider
whether `heyreach.add_leads_to_list` should itself write a ledger row, or
whether the `except TypeError` handler in write_linkedin_lead_variables.py
should be removed so all writes go through the gated path. This is a finding
for the operator, not a fix to implement here.
