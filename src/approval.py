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


def fingerprint(step, skip_subject=False):
    """What was approved. Any edit to the words changes this.

    TASK-219: for a threaded follow-up, the subject is NOT sendable content -
    the provider continues the original thread and prepends ``Re:`` itself.
    ``skip_subject=True`` excludes the subject from the hash, so the approval
    covers only the body (and channel/note). A follow-up whose body changes
    invalidates the approval; a follow-up whose generated subject changes
    does not, because that subject never reaches a prospect.
    """
    parts = [str((step or {}).get("channel") or "")]
    if not skip_subject:
        parts.append(str((step or {}).get("subject") or ""))
    parts.append(str((step or {}).get("body") or ""))
    parts.append(str((step or {}).get("note") or ""))
    material = " ".join(parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def stored(rec, contact_key, step_key):
    return ((rec.get("cadence") or {}).get(contact_key) or {}).get(step_key) or {}


def approval_of(rec, contact_key, step_key):
    return stored(rec, contact_key, step_key).get("approval")


def is_approved(rec, contact_key, step_key, step=None, campaign=None):
    """True only if this exact text was approved and has not changed since.

    A template step is expanded fresh on every read, so if the template, the
    angle or the evidence behind it changes, the fingerprint moves and the
    approval no longer applies. That is the point.

    TASK-219: for a threaded follow-up, the approval fingerprint excludes
    the subject. If the stored slot carries the ``threaded_follow_up`` flag
    (set by ``approve.approve_step``), the current step's fingerprint is
    computed with ``skip_subject=True`` to match. ``campaign`` is needed to
    determine threading when the flag is absent from an older slot.
    """
    approval = approval_of(rec, contact_key, step_key)
    if not approval:
        return False
    slot = stored(rec, contact_key, step_key)
    current = step if step is not None else slot
    skip = slot.get("threaded_follow_up")
    if skip is None and campaign is not None:
        skip = _is_threaded_follow_up(step_key, campaign)
    return approval.get("fingerprint") == fingerprint(current,
                                                      skip_subject=bool(skip))


def _is_threaded_follow_up(step_key, campaign):
    """True when this step key is a threaded follow-up in the campaign's
    email sequence.

    Reads the client config's ``email_sequence.thread_reply_pattern`` and
    the cadence's email step order to decide whether ``step_key`` sits at
    a position where ``thread_reply`` is true. Returns False when the
    question cannot be answered (no campaign, no config, no cadence).
    """
    if not campaign or not step_key:
        return False
    from . import clients

    client = campaign.get("client")
    if not client:
        return False
    try:
        config = clients.load(client)
    except clients.ConfigError:
        return False
    seq = (config.get("email_sequence") or {})
    steps_block = seq.get("steps") or {}
    if step_key not in steps_block:
        return False
    pattern = seq.get("thread_reply_pattern") or []
    if not pattern:
        return False
    email_keys = sorted(
        steps_block,
        key=lambda k: (steps_block[k] or {}).get("order", 0))
    try:
        idx = email_keys.index(step_key)
    except ValueError:
        return False
    if idx < 1 or idx >= len(pattern):
        return False
    return bool(pattern[idx])
