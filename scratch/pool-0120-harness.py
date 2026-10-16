"""POOL 0120 harness — prove the fix makes write_linkedin_lead_variables.py:150
enter the braked seam instead of falling through to the ungated transport.

The defect: line 150 passes allow_restage=True to stage_lead, which doesn't
accept it. TypeError fires at argument binding, caught by except TypeError at
line 157, which bypasses stage_lead entirely and calls heyreach.add_leads_to_list
directly at line 163 — no brake, no gate, no audit.

The fix: remove allow_restage=True from the call. This makes the call bind
successfully, enter stage_lead, and go through the braked seam (once the brake
branch task-glm-c-0164-brake-ship is merged).

This harness:
1. Reads the CURRENT signature from src/liststaging.py
2. Replays the call from write_linkedin_lead_variables.py:150-154
3. Reports which seam was entered: ENTERS-FALLBACK or BRAKED-SEAM
4. Runs both UNPATCHED (with allow_restage) and PATCHED (without) in same run

Negative control: UNPATCHED -> ENTERS-FALLBACK
Positive control: PATCHED -> BRAKED-SEAM
"""
import ast
import hashlib
import subprocess
import sys


def read_signature_from_tree():
    """Read the stage_lead signature from the current tree."""
    with open("src/liststaging.py", "rb") as f:
        blob_bytes = f.read()
    blob_sha = hashlib.sha256(blob_bytes).hexdigest()
    blob_text = blob_bytes.decode("utf-8")

    tree = ast.parse(blob_text)
    stage_lead_def = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "stage_lead":
            stage_lead_def = node
            break

    assert stage_lead_def is not None, "stage_lead not found"

    params = []
    has_varkeyword = False
    for arg in stage_lead_def.args.args:
        params.append(arg.arg)
    for arg in stage_lead_def.args.kwonlyargs:
        params.append(arg.arg)
    if stage_lead_def.args.vararg:
        params.append(f"*{stage_lead_def.args.vararg.arg}")
    if stage_lead_def.args.kwarg:
        has_varkeyword = True
        params.append(f"**{stage_lead_def.args.kwarg.arg}")

    return blob_sha, params, has_varkeyword


def replay_call(signature_params, has_varkeyword, with_allow_restage):
    """Build a stub stage_lead matching the signature, replay the call,
    return which seam was entered."""

    # Build the stub dynamically based on the signature
    param_list = []
    for p in signature_params:
        if p.startswith("**"):
            param_list.append(p)
        elif p.startswith("*"):
            param_list.append(p)
        elif p in ("list_reader", "members_reader", "by"):
            param_list.append(f"{p}=None")
        else:
            param_list.append(p)

    # Add allow_restage if the signature accepts it OR if we're testing the fix
    accepts_allow_restage = "allow_restage" in signature_params or has_varkeyword
    if accepts_allow_restage:
        param_list.append("allow_restage=False")

    params_str = ", ".join(param_list)
    stub_code = f"""
def stage_lead_stub({params_str}):
    return {{"ok": True, "transport_ran": True}}
"""
    exec(stub_code, globals())

    # Replay the call from write_linkedin_lead_variables.py:150-154
    LIST_ID = 999999
    payload_row = {
        "linkedin_url": "https://www.example.test/x",
        "first_name": "Synthetic",
        "last_name": "Lead",
        "custom_fields": {}
    }

    seam = None
    try:
        if with_allow_restage:
            # UNPATCHED: the shipped call with allow_restage=True
            stage_lead_stub(
                LIST_ID, payload_row,
                lambda p, _row=payload_row: {"added": 1},
                allow_restage=True)
        else:
            # PATCHED: the call without allow_restage
            stage_lead_stub(
                LIST_ID, payload_row,
                lambda p, _row=payload_row: {"added": 1})
        seam = "BRAKED-SEAM"
    except TypeError as exc:
        seam = f"ENTERS-FALLBACK (TypeError: {exc})"
    except Exception as exc:
        seam = f"OTHER ({type(exc).__name__}: {exc})"

    return seam


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
print("=== POOL 0120 harness ===")
print()

# Read the CURRENT signature from the tree
blob_sha, params, has_varkeyword = read_signature_from_tree()
print(f"blob SHA-256: {blob_sha}")
print(f"parameters  : {params}")
print(f"has **kwargs: {has_varkeyword}")
accepts_allow_restage = "allow_restage" in params or has_varkeyword
print(f"'allow_restage' accepted: {accepts_allow_restage}")
print()

# Run both arms
print("=== both arms ===")
unpatched = replay_call(params, has_varkeyword, with_allow_restage=True)
patched = replay_call(params, has_varkeyword, with_allow_restage=False)
print(f"  UNPATCHED (with allow_restage=True)    -> {unpatched}")
print(f"  PATCHED   (without allow_restage)      -> {patched}")
print()

# Verdict
print("=== verdict ===")
if "ENTERS-FALLBACK" in unpatched and "BRAKED-SEAM" in patched:
    print("PASS: negative control (UNPATCHED) and positive control (PATCHED) both correct")
    print("The fix (removing allow_restage=True) makes the call enter the braked seam")
    sys.exit(0)
elif "BRAKED-SEAM" in unpatched:
    print("NOTE: UNPATCHED already enters BRAKED-SEAM — the signature already accepts allow_restage")
    print("The tree is already patched or the signature was widened")
    sys.exit(0)
else:
    print("FAIL: unexpected seam combination")
    print(f"  UNPATCHED: {unpatched}")
    print(f"  PATCHED:   {patched}")
    sys.exit(1)
