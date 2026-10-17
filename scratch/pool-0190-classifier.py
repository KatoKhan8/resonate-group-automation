#!/usr/bin/env python3
"""POOL 0190 — classify every exception shape at the stage_lead call site.

Tests whether an operator reading the output can distinguish a swallowed
programming error from a deliberate gate refusal.

Each shape is exercised and the output is captured. The classifier is the
print statement at lines 158-159 of write_linkedin_lead_variables.py:

    print(f"  REFUSED  {plan['hash']}  {type(exc).__name__}: "
          f"{str(exc)[:90]}")

The question: does the exception type name make the two classes distinguishable?
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

from src import liststaging

# Synthetic hash
SYNTHETIC_HASH = "a1b2c3d4e5f6"

def call_site_handler(exc):
    """Mimics the except Exception handler at lines 156-159."""
    print(f"  REFUSED  {SYNTHETIC_HASH}  {type(exc).__name__}: "
          f"{str(exc)[:90]}")

def test_shape_1_missing_kwarg():
    """Shape 1: missing required argument."""
    print("\n=== SHAPE 1: missing kwarg ===")
    try:
        liststaging.stage_lead(944355, {"linkedin_url": "https://www.linkedin.com/in/test"})
    except Exception as exc:
        call_site_handler(exc)

def test_shape_2_extra_kwarg():
    """Shape 2: extra keyword argument."""
    print("\n=== SHAPE 2: extra kwarg ===")
    try:
        liststaging.stage_lead(
            944355,
            {"linkedin_url": "https://www.linkedin.com/in/test", "first_name": "Test", "last_name": "User"},
            lambda p: None,
            allow_restage=True  # This kwarg does not exist
        )
    except Exception as exc:
        call_site_handler(exc)

def test_shape_3_wrong_type():
    """Shape 3: wrong type argument (transport not callable)."""
    print("\n=== SHAPE 3: wrong-type arg ===")
    try:
        liststaging.stage_lead(944355, {"linkedin_url": "https://www.linkedin.com/in/test", "first_name": "Test", "last_name": "User"}, None)
    except Exception as exc:
        call_site_handler(exc)

def test_shape_4_typeerror_inside():
    """Shape 4: TypeError raised inside stage_lead (before providerwrites.perform)."""
    print("\n=== SHAPE 4: TypeError inside callee ===")
    # Force a TypeError by passing a list_id that causes int() to fail with TypeError
    # (not ValueError)
    try:
        # int([1,2,3]) raises TypeError
        liststaging.stage_lead([1,2,3], {"linkedin_url": "https://www.linkedin.com/in/test", "first_name": "Test", "last_name": "User"}, lambda p: None)
    except Exception as exc:
        call_site_handler(exc)

def test_shape_5_gate_refusal():
    """Shape 5: deliberate gate refusal (ListStagingRefused)."""
    print("\n=== SHAPE 5: gate refusal ===")
    try:
        # Missing first_name triggers validate_lead_row to raise ListStagingRefused
        liststaging.stage_lead(944355, {"linkedin_url": "https://www.linkedin.com/in/test", "last_name": "User"}, lambda p: None)
    except Exception as exc:
        call_site_handler(exc)

def test_shape_6_synthetic_indistinguishable():
    """Shape 6: SYNTHETIC — gate raises TypeError instead of ListStagingRefused.

    This proves the classifier could have failed: if the gate raised a TypeError,
    the output would be indistinguishable from a programming error.
    """
    print("\n=== SHAPE 6: SYNTHETIC indistinguishable arm ===")
    # Patch validate_lead_row to raise TypeError
    original_validate = liststaging.validate_lead_row
    def fake_validate(row):
        raise TypeError("SYNTHETIC: gate raised TypeError instead of ListStagingRefused")
    liststaging.validate_lead_row = fake_validate
    try:
        liststaging.stage_lead(944355, {"linkedin_url": "https://www.linkedin.com/in/test", "first_name": "Test", "last_name": "User"}, lambda p: None)
    except Exception as exc:
        call_site_handler(exc)
    finally:
        liststaging.validate_lead_row = original_validate

if __name__ == "__main__":
    print("POOL 0190 — exception shape classifier")
    print("=" * 60)
    test_shape_1_missing_kwarg()
    test_shape_2_extra_kwarg()
    test_shape_3_wrong_type()
    test_shape_4_typeerror_inside()
    test_shape_5_gate_refusal()
    test_shape_6_synthetic_indistinguishable()
    print("\n" + "=" * 60)
    print("END OF CLASSIFIER TEST")
