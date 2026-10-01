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


# WHICH MAILBOX IS WRITING IS PART OF WHAT WAS APPROVED.
#
# `fingerprint` above answers "have these WORDS changed". It never answered
# "is the same person still sending them", because the sender is not in the
# step: it is in the client config, resolved at render time by
# `clients.sender_identity` and composed into every body by
# `sendersignature.compose`. So swapping the mailbox - or the signature block
# it renders - after an approval changed the email a real person receives
# while every fingerprint in the estate stayed put.
#
# That is incident B's shape exactly: 64 emails went out signed with the
# operator's name from somebody else's mailboxes. A signature is a claim about
# who is writing, and a claim nobody approved is the thing this module exists
# to refuse.
#
# THE FIELDS ARE THE WHOLE DECLARED BLOCK, not the subset any one renderer
# reads. `clients.sender_identity` drops `email` and `mode`; a swap of the
# sending address with the display name left alone is still a different
# mailbox, and an approval that did not notice is not an approval of the
# message that ships.
SENDER_FIELDS = ("mode", "name", "title", "role", "company", "works_on",
                 "email")

#: THE ABSENCE IS FINGERPRINTED, NOT REPRESENTED BY AN EMPTY ANSWER.
#:
#: The first version of this returned `""` for a client that declares no
#: sender - the starter config's shape - and `is_approved` normalized a stamp
#: with no binding to `""` as well. So `"" == ""` was True and a pre-binding
#: stamp authorized a send for every client with no declared sender. Measured
#: on 8ab8f8dc: productive False (correct), no-sender-block True (the hole),
#: and the same for a blank block and for a non-dict one.
#:
#: ABSENT IS NOT ABSENT-EQUALS-ABSENT. "The stamp recorded no binding" and
#: "the binding is that there is no sender" are different facts, and the
#: defect this repository keeps rediscovering is absence of evidence read as
#: evidence of a match. Every answer here is now a 16-hex digest and none is
#: falsy, so no stamp that recorded nothing can equal one - the collision is
#: removed rather than guarded at one call site, which is what stops a later
#: caller reintroducing it by forgetting a presence check.
#:
#: A client with NO sender still gets a real binding rather than a permanent
#: refusal: the operator approved copy that renders no signature, and if a
#: sender is declared later the digest moves and the approval goes stale. The
#: two branches carry distinct tags so a declared sender can never collide
#: with the declaration of none.
NO_SENDER_DECLARED = "no-sender-declared"
_SENDER_TAG = "sender"


def sender_fingerprint(config):
    """Which mailbox is writing, and exactly what it signs with.

    A digest of the client's declared `sender:` block TOGETHER WITH the
    signature that block renders through `sendersignature.compose` - the same
    function `bisonfactory._variables_for` and `render` use, so what is bound
    here is the string the prospect reads and not a proxy for it.

    NEVER EMPTY, FOR ANY INPUT. A client that declares no sender, one whose
    `sender:` is not a map, and one whose declared fields are all blank all
    render the same thing - nothing - so they bind to the same digest of
    `NO_SENDER_DECLARED`. That is a positive statement about this client,
    which is the point: it is distinguishable from a stamp that recorded no
    binding at all, and an unreadable config (`{}`) still cannot satisfy a
    stamp taken against a real mailbox. Fail closed, every direction.
    """
    # Local, so this module keeps the no-dependency property its docstring
    # claims at import time. `clients` reaches `store`; neither reaches back.
    from . import clients, sendersignature

    block = (config or {}).get("sender")
    identity = {}
    if isinstance(block, dict):
        for key in SENDER_FIELDS:
            value = " ".join(str(block.get(key) or "").split())
            if value:
                identity[key] = value
    if not identity:
        material = NO_SENDER_DECLARED
    else:
        material = "\x1f".join(
            [_SENDER_TAG]
            + ["%s=%s" % (key, identity[key]) for key in sorted(identity)]
            + [sendersignature.compose(clients.sender_identity(config))])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def stored(rec, contact_key, step_key):
    return ((rec.get("cadence") or {}).get(contact_key) or {}).get(step_key) or {}


def approval_of(rec, contact_key, step_key):
    return stored(rec, contact_key, step_key).get("approval")


def is_approved(rec, contact_key, step_key, step=None, config=None):
    """True only if this exact text was approved and has not changed since.

    A template step is expanded fresh on every read, so if the template, the
    angle or the evidence behind it changes, the fingerprint moves and the
    approval no longer applies. That is the point.

    `config` EXTENDS THE QUESTION FROM THE WORDS TO THE MAILBOX. A caller that
    supplies the client config is asking the whole question - these words,
    from this sender, signed this way - and gets False when any of the three
    moved. A caller with no config in hand asks only about the words, which is
    the question it could ask before and the only one it has the inputs for.
    The send gate (`eligibility`) and the record's derived approval state
    (`approve.fully_approved`) both supply it; the reporting surfaces do not.

    A stamp taken before the sender was bound carries no `sender_fingerprint`,
    so it matches NO client - including one that declares no sender, because
    `sender_fingerprint` fingerprints that absence rather than answering with
    an empty string. An approval that never covered the mailbox is STALE for
    everybody rather than grandfathered for some. Re-approving is the repair,
    and it is the only honest one.

    `config=None` IS NOT A CLIENT: it means no config was supplied, and the
    answer is the words-only one the caller has the inputs for. Both gates
    that can release a step resolve a config of their own, so neither reaches
    this with None.

    The recorded value is compared AS STORED, with no `or ""` normalization,
    and the explicit truth test below says in one line that a stamp which
    recorded nothing is not a stamp that recorded a match. MEASURED: this half
    is DEFENCE IN DEPTH, not the load-bearing guard. Put the normalization
    back on its own and every test still passes, because no answer from
    `sender_fingerprint` is falsy any more; the hole needs BOTH halves undone.
    It stays because it costs one line and it is what holds if the digest
    property is ever broken - which is the half a future edit is likelier to
    reach for.
    """
    approval = approval_of(rec, contact_key, step_key)
    if not approval:
        return False
    current = step if step is not None else stored(rec, contact_key, step_key)
    if approval.get("fingerprint") != fingerprint(current):
        return False
    if config is None:
        return True
    recorded = approval.get("sender_fingerprint")
    if not recorded:
        return False
    return recorded == sender_fingerprint(config)
