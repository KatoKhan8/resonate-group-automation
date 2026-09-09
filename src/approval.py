"""What approval *is*, with no dependencies.

Kept separate from src/approve.py, which is the action a human takes, so the
cadence can ask "was this approved" without importing the approver and creating
a cycle.
"""
import hashlib


def fingerprint(step):
    """What was approved. Any edit to the words changes this."""
    material = " ".join([
        str((step or {}).get("channel") or ""),
        str((step or {}).get("subject") or ""),
        str((step or {}).get("body") or ""),
        str((step or {}).get("note") or ""),
    ])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def stored(rec, contact_key, step_key):
    return ((rec.get("cadence") or {}).get(contact_key) or {}).get(step_key) or {}


def approval_of(rec, contact_key, step_key):
    return stored(rec, contact_key, step_key).get("approval")


def is_approved(rec, contact_key, step_key, step=None):
    """True only if this exact text was approved and has not changed since.

    A template step is expanded fresh on every read, so if the template, the
    angle or the evidence behind it changes, the fingerprint moves and the
    approval no longer applies. That is the point.
    """
    approval = approval_of(rec, contact_key, step_key)
    if not approval:
        return False
    current = step if step is not None else stored(rec, contact_key, step_key)
    return approval.get("fingerprint") == fingerprint(current)
