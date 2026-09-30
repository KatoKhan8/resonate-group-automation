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

#: THE ONE AUTHORITY THAT IS NOT A PERSON AND IS STILL ACCOUNTABLE.
#:
#: Operator decision, Zvonimir, 2026-09-30: the 48-hour autonomous production
#: authorization covers NEW prospect-facing copy the operator has NOT
#: personally read, provided that copy is generated through the canonical
#: path and passes every required gate. The ramp needs it - fifty-company
#: batches cannot be hand-read - and refusing it was blocking production.
#:
#: WHAT THIS IS NOT. It is NOT `by: "claude"` readmitted under a new name.
#: The 84 self-stamps this module was written against claimed a review that
#: never happened; this one claims something different and true: an OPERATOR
#: AUTHORIZED THE WINDOW, the SYSTEM generated and gated the artifact, and
#: the operator did NOT read it. `personally_reviewed` keeps those apart for
#: any caller that needs a human, and nothing here makes `claude`, `qwen`,
#: `glm`, `system` or `unknown` accountable - they still fail.
AUTONOMOUS_PRODUCTION = "autonomous-production"

#: The windows that authority is live inside, as (expires_on, provenance).
#:
#: TIME-BOXED AND IT REVERTS ON ITS OWN, which is `copylint.DEMOTIONS`'s
#: pattern and is here for the same reason: an authorization that outlives
#: the decision behind it is one nobody remembers to revoke. Past the expiry
#: this authority stops certifying copy and staging refuses it - fail-closed,
#: no human has to remember to edit a frozenset.
#:
#: It is DATA, not an `if`. A new window is a new line with a new operator
#: decision recorded beside it, and it is as visible as this one.
AUTONOMOUS_WINDOWS = (
    ("2026-10-01",
     "Zvonimir (operator), 2026-09-30: 48-hour autonomous production window. "
     "Operator authorized the WINDOW and the POLICY; the individual artifact "
     "was generated and gated by the canonical system; the operator did NOT "
     "personally review it."),
)


def autonomous_window(on=None):
    """The live autonomous-production window, or None. Absence is refusal."""
    import time

    today = on or time.strftime("%Y-%m-%d")
    for expires_on, provenance in AUTONOMOUS_WINDOWS:
        if str(today) <= expires_on:
            return {"expires_on": expires_on, "provenance": provenance}
    return None


def autonomous_stamp(on=None):
    """The exact `by` string an autonomous approval must carry, or None.

    Built here rather than by the caller so every autonomous approval in the
    estate reads the same and none of them can quietly omit the part that
    says a person did not read this.
    """
    window = autonomous_window(on)
    if window is None:
        return None
    return "%s (%s Expires %s.)" % (AUTONOMOUS_PRODUCTION,
                                    window["provenance"], window["expires_on"])


def is_autonomous_production(by, on=None):
    """Is this the autonomous authority, with its provenance, window open?

    THE WHOLE STAMP HAS TO MATCH, not just the token. The operator's decision
    requires the provenance to say which window authorized this and that no
    person read the artifact; a bare `autonomous-production` says neither, so
    accepting it would hand every future caller a one-word self-approval -
    the exact thing this module exists to refuse. Compared against
    `autonomous_stamp`, so the only way to write one is to ask for it.
    """
    who = str(by or "").strip().lower()
    if not who.startswith(AUTONOMOUS_PRODUCTION):
        return False
    canonical = autonomous_stamp(on)
    return canonical is not None and who == canonical.strip().lower()


def personally_reviewed(by):
    """Did a PERSON read these words? The strict question.

    `is_accountable_approver` answers "may this ship", which the autonomous
    window can now satisfy. This answers "did a human look", which it never
    can. Any caller that means the second one must ask this one.
    """
    who = str(by or "").strip().lower()
    if not who:
        return False
    if who in OPERATOR_ARMS:
        return True
    return _looks_like_an_address(who)


def _looks_like_an_address(who):
    head = who.split("(", 1)[0].strip()
    if head.count("@") != 1:
        return False
    local, _, domain = head.partition("@")
    return bool(local.strip()) and "." in domain and bool(
        domain.rsplit(".", 1)[-1].strip())


def is_accountable_approver(by, on=None):
    """Could a person be held to this approval afterwards?

    True for an address, for one of the declared operator arms, and - since
    the operator's 2026-09-30 decision - for the autonomous production
    authority while its window is open, because the operator is accountable
    for authorizing the window even though they did not read the artifact.

    Still False for a bare token: `claude`, `qwen`, `glm`, `system`.
    """
    who = str(by or "").strip().lower()
    if not who:
        return False
    if who in OPERATOR_ARMS:
        return True
    if is_autonomous_production(who, on):
        return True
    # `someone@example.com (operator authorisation 2026-09-16)` - the address
    # is the accountable part and the parenthetical is provenance.
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
    parts = [
        str((step or {}).get("channel") or ""),
        str((step or {}).get("subject") or ""),
        str((step or {}).get("body") or ""),
        str((step or {}).get("note") or ""),
    ]
    # Only include ps if present and non-empty, to preserve backward compatibility
    # with existing approvals that were computed without ps.
    ps = (step or {}).get("ps")
    if ps:
        parts.append(str(ps))
    material = " ".join(parts)
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
