"""POOL 0200 — does a direct add_leads_to_list write leave a ledger row?

Measures whether heyreach.add_leads_to_list called directly (the bypass
ARM A took in write_linkedin_lead_variables.py:157-170) leaves a row in
the provider-writes ledger, and how that row differs from the gated path.

Two arms, synthetic fixture, no provider transport:

  ARM A (gated): liststaging.stage_lead() -> providerwrites.perform()
                 -> _ledger() writes a row on every exit.
  ARM B (direct): heyreach.add_leads_to_list() called directly,
                  bypassing perform(). Does NOT call _ledger().

Controls:
  - ARM A must produce a ledger row (positive control).
  - The harness must be able to print BOTH "no row" and "a row" -
    if the base prints only one, the instrument is broken.
  - No real provider transport: mock at _write_body seam.
  - Isolated store so the production-write barrier does not fire.

Base SHA: b28652900 (CRLF tree)
step= fix (6b0462bec): INCLUDED in base.
"""
import json
import os
import subprocess
import sys
import tempfile

# ---- env: ensure this tree's src/ is importable ----
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

# ---- env: clear GIT_CONFIG_* so git works ----
for var in ("GIT_CONFIG_SYSTEM", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_COUNT"):
    os.environ.pop(var, None)

# ---- env: point the ledger at a scratch file BEFORE importing src ----
TMP = tempfile.mkdtemp(prefix="pool0200-")
LEDGER_PATH = os.path.join(TMP, "provider-writes.jsonl")
os.environ["PROVIDER_WRITES_LEDGER"] = LEDGER_PATH

# ---- env: isolate the store so the production-write barrier passes ----
from src import store as _store  # noqa: E402
_restore_store = _store.use_directory(TMP)

# Now import the rest
from src import providerwrites  # noqa: E402
from src.providers import heyreach  # noqa: E402

# ---- constants ----
SYNTH_LIST_ID = 999001
SYNTH_ROW = {
    "linkedin_url": "https://www.linkedin.com/in/synthetic-probe-0200",
    "first_name": "Synthetic",
    "last_name": "Probe",
    "custom_fields": {},
}


def count_ledger_rows():
    """Return list of parsed ledger rows."""
    if not os.path.exists(LEDGER_PATH):
        return []
    rows = []
    with open(LEDGER_PATH, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def reset_ledger():
    """Clear the ledger file."""
    if os.path.exists(LEDGER_PATH):
        os.unlink(LEDGER_PATH)


# ---- mock transport: no real provider call ----
# heyreach._write_body is the seam both add_leads_to_list and the gated
# transport would call. We patch it to return a synthetic success.
_ORIG_WRITE_BODY = heyreach._write_body


def _fake_write_body(path, body):
    # record the call so we can prove the transport was reached
    _fake_write_body.calls.append((path, body))
    return {
        "addedLeadsCount": 1,
        "updatedLeadsCount": 0,
        "failedLeadsCount": 0,
        "synthetic": True,
    }
_fake_write_body.calls = []


# ---- mock list_reader so assert_list_safe passes ----
def _fake_list_reader(list_id):
    return {
        "id": list_id,
        "campaignIds": [],  # unbound = safe
        "totalItemsCount": 0,
    }


def _fake_members_reader(list_id, offset=0, limit=100):
    return ([], 0)


# ---- patch the transport seam ----
heyreach._write_body = _fake_write_body

# ---- also need liststaging to see the patched heyreach ----
from src import liststaging  # noqa: E402


# ============================================================================
# ARM A: gated path through liststaging.stage_lead -> providerwrites.perform
# ============================================================================
print("=== ARM A (gated path) ===")
reset_ledger()
_fake_write_body.calls = []

try:
    liststaging.stage_lead(
        SYNTH_LIST_ID,
        SYNTH_ROW,
        transport=lambda payload: heyreach._write_body(
            "/list/AddLeadsToListV2", payload),
        list_reader=_fake_list_reader,
        members_reader=_fake_members_reader,
        by="pool-0200-arm-a",
    )
    arm_a_exception = None
except Exception as exc:
    arm_a_exception = exc

rows_after_a = count_ledger_rows()
print(f"  exception         : {arm_a_exception}")
print(f"  transport calls   : {len(_fake_write_body.calls)}")
print(f"  ledger rows       : {len(rows_after_a)}")
for row in rows_after_a:
    print(f"    - op={row.get('operation')!r} outcome={row.get('outcome')!r} "
          f"by={row.get('by')!r} step={row.get('step')!r} key={row.get('key')!r}")
    print(f"      detail={str(row.get('detail'))[:120]!r}")

# ============================================================================
# ARM B: direct heyreach.add_leads_to_list, bypassing the gate
# ============================================================================
print("\n=== ARM B (direct add_leads_to_list) ===")
reset_ledger()
_fake_write_body.calls = []

try:
    heyreach.add_leads_to_list(SYNTH_LIST_ID, [SYNTH_ROW])
    arm_b_exception = None
except Exception as exc:
    arm_b_exception = exc

rows_after_b = count_ledger_rows()
print(f"  exception         : {arm_b_exception}")
print(f"  transport calls   : {len(_fake_write_body.calls)}")
print(f"  ledger rows       : {len(rows_after_b)}")
for row in rows_after_b:
    print(f"    - op={row.get('operation')!r} outcome={row.get('outcome')!r} "
          f"by={row.get('by')!r} step={row.get('step')!r} key={row.get('key')!r}")
    print(f"      detail={str(row.get('detail'))[:120]!r}")

# ============================================================================
# CONTROLS: prove the instrument can print BOTH a row and no-row
# ============================================================================
print("\n=== instrument controls ===")

# Control 1: direct call to _ledger must produce a row
reset_ledger()
providerwrites._ledger("synthetic.control", "performed",
                       by="control", step="ctrl-step", key="ctrl-key")
ctrl_rows = count_ledger_rows()
print(f"  direct _ledger() call -> {len(ctrl_rows)} row(s)")
assert len(ctrl_rows) == 1, "CONTROL FAILED: _ledger cannot write a row"
print(f"    op={ctrl_rows[0].get('operation')!r} by={ctrl_rows[0].get('by')!r} "
      f"step={ctrl_rows[0].get('step')!r}")

# Control 2: an arm that writes nothing must produce zero rows
reset_ledger()
zero_rows = count_ledger_rows()
print(f"  empty ledger -> {len(zero_rows)} row(s)")
assert len(zero_rows) == 0, "CONTROL FAILED: empty ledger reads non-zero"

# ============================================================================
# VERDICT
# ============================================================================
print("\n=== VERDICT ===")
a_count = len(rows_after_a)
b_count = len(rows_after_b)

print(f"  ARM A ledger rows: {a_count}")
print(f"  ARM B ledger rows: {b_count}")

if a_count == 0:
    print("  WARNING: ARM A (gated path) produced NO row. Positive control failed.")
    print("  The ledger is not writing at all; verdict is UNMEASURABLE.")
    verdict = "UNMEASURABLE"
elif b_count == 0:
    print("  ARM B (direct write) produced NO ledger row.")
    print("  The bypass is LEDGER-BLIND: a direct add_leads_to_list call")
    print("  leaves no trace in the spend audit.")
    verdict = "LEDGER-BLIND"
elif b_count > 0:
    a_row = rows_after_a[0]
    b_row = rows_after_b[0]
    if (a_row.get("by") == b_row.get("by")
            and a_row.get("step") == b_row.get("step")):
        print("  ARM B produced a row that is byte-identical in by=/step= to ARM A.")
        verdict = "LEDGER-PRESENT-INDISTINGUISHABLE"
    else:
        print("  ARM B produced a row that differs from ARM A in by= or step=.")
        verdict = "LEDGER-PRESENT-DISTINGUISHABLE"
else:
    verdict = "UNMEASURABLE"

print(f"\n  FINAL VERDICT: {verdict}")

# ============================================================================
# TREE STATE: prove no tracked file was modified
# ============================================================================
print("\n=== tree state ===")
status = subprocess.run(
    ["git", "status", "--short"],
    cwd=ROOT, capture_output=True, text=True, check=True,
)
tracked_changes = [ln for ln in status.stdout.splitlines()
                   if not ln.startswith("??")]
print(f"  tracked file changes: {len(tracked_changes)}")
if tracked_changes:
    for line in tracked_changes:
        print(f"    {line}")
else:
    print("  tree is clean (only untracked scratch files)")

# Restore store
_restore_store()
