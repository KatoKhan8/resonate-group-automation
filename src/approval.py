"""What approval *is*, with no dependencies.

Kept separate from src/approve.py, which is the action a human takes, so the
cadence can ask "was this approved" without importing the approver and creating
a cycle.
"""
import hashlib

# WHO MAY BLESS WORDS A STRANGER WILL READ.
#
# The fingerprint answers "have these words changed since they were approved".
# It cannot answer "did a person approve them", and for one shape of step it
# never will: `li2`-`li5` are `generated: true`, so `cadence.expand_step`
# returns the stored words verbatim, the hash never moves, and an approval the
# SYSTEM recorded for itself stays current forever.
#
# Measured 2026-09-17 across the estate: 84 approvals stamped `by: "claude"`,
# 83 of them on generated steps. None of those contacts reaches READY today -
# but only because they happen to cover one to three of the five LinkedIn
# steps rather than all five. That is luck, not a gate.
#
# ACCOUNTABILITY IS A SHAPE, NOT A NAME. An allowlist of individuals goes stale
# the first time somebody new joins; a denylist of machine names fails OPEN for
# the next model added to this repo. So the test is whether the approver is an
# identity somebody can be held to: an address, or a declared operator arm that
# the client config names. `claude`, `qwen`, `glm`, `system`, `unknown` are
# none of those and never will be.
OPERATOR_ARMS = frozenset({"operator", "operator-control-arm"})


def is_accountable_approver(by):
    """Could a person be held to this approval afterwards?

    True for an address, or for one of the declared operator arms. False for a
    bare token - which is what every automated approver in this repository has
    ever written, and what a future one will write too.
    """
    who = str(by or "").strip().lower()
    if not who:
        return False
    if who in OPERATOR_ARMS:
        return True
    # `zvonimir@x.co (operator authorisation 2026-09-16)` - the address is the
    # accountable part and the parenthetical is provenance.
    #
    # BOTH SIDES OF THE @ HAVE TO BE THERE. An earlier version asked only for
    # an `@` and a dot after it, which accepted `@example.com` - a domain with
    # nobody in front of it, which is not an identity anybody can be reached
    # at. Its own test caught that, which is the argument for writing the
    # negative cases out rather than trusting the shape to be obvious.
    head = who.split("(", 1)[0].strip()
    if head.count("@") != 1:
        return False
    local, _, domain = head.partition("@")
    return bool(local.strip()) and "." in domain and bool(
        domain.rsplit(".", 1)[-1].strip())


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
