"""Campaign-scoped authority for prospect-facing provider mutations.

WHY THIS EXISTS, AND WHY IT IS NOT THE KILL SWITCH.

`bisonfactory._ensure_leads` consulted `killswitch.workspace_state` and
nothing narrower, so the narrowest permission the system could express was
"Productive may have leads created" - every campaign of that client at once,
historical and paused ones included. Operator decision, 2026-09-29: that is
too wide to authorize a one-person canary with.

This module adds a NARROWER requirement on top. It removes nothing: the
global layer still refuses sending in code, the workspace switch still has to
be on, and this grant is a further gate that must ALSO pass. Default is
REFUSE - no grant, no write.

WHAT A GRANT BINDS

    client        the workspace the write belongs to
    provider      "bison" or "heyreach"; a bison grant never admits heyreach
    purpose       why this execution exists, for the ledger and the audit
    phase         SETUP or ACTIVATE - and SETUP NEVER IMPLIES ACTIVATE
    operations    the exact verbs, by their `providerwrites` constant
    campaign_id   the exact campaign, once it exists
    recipient     the exact address, where the verb is per-recipient
    approval_hash the artifact this execution was authorized against

THE BOOTSTRAP PROBLEM, SOLVED EXPLICITLY

A campaign id does not exist until `create_campaign` returns one. A grant may
therefore start with `campaign_id=None`, which admits the CREATE verb and
nothing else. `bind_campaign` then writes the returned id onto the grant, once,
and every later verb must match it exactly. There is deliberately no
"create any campaign for this client" authority: the grant names its purpose
and its recipient before the campaign exists, so what it may create is
already bounded.

SCOPE IS A ContextVar, for the reason `providers.allow_writes` is one: a
plain module global leaks into worker threads, and a thread that inherits an
authorization it was never given is the bug this whole layer exists to stop.
It fails CLOSED into any thread that did not open the scope.

RACHELE IS AN INSTANCE, NOT THE MODEL. Nothing here names her, 2020
Companies, or a hash. The first execution happens to be a canary of one; the
same grant shape carries the 5/10/15/20/25/50 ramp, one execution per batch.
"""
import contextlib
import contextvars
import uuid

SETUP = "setup"
ACTIVATE = "activate"
PHASES = (SETUP, ACTIVATE)


class ScopeRefused(RuntimeError):
    """No grant in scope admits this exact mutation. The default answer."""


class _Grant:
    """One execution's authority. Not a dict, for `Authorization`'s reason:
    a dict can be assembled by anybody."""

    __slots__ = ("execution_id", "client", "provider", "purpose", "phase",
                 "operations", "campaign_id", "recipient", "approval_hash")

    def __init__(self, *, client, provider, purpose, phase, operations,
                 campaign_id=None, recipient=None, approval_hash=None,
                 execution_id=None):
        if phase not in PHASES:
            raise ValueError("phase must be one of %r" % (PHASES,))
        if not client or not provider or not purpose:
            raise ValueError("a grant names client, provider and purpose")
        if not operations:
            raise ValueError("a grant with no operations authorizes nothing")
        self.execution_id = execution_id or ("exec-%s" % uuid.uuid4().hex[:12])
        self.client = client
        self.provider = provider
        self.purpose = purpose
        self.phase = phase
        self.operations = frozenset(operations)
        self.campaign_id = campaign_id
        self.recipient = recipient
        self.approval_hash = approval_hash

    def describe(self):
        return ("%s client=%s provider=%s purpose=%s phase=%s campaign=%s "
                "recipient=%s" % (self.execution_id, self.client,
                                  self.provider, self.purpose, self.phase,
                                  self.campaign_id, self.recipient))


_active = contextvars.ContextVar("executionscope_active", default=())


def active():
    """The grants in scope for THIS context. Empty is the normal state."""
    return _active.get()


@contextlib.contextmanager
def grant(**fields):
    """Open one execution's authority for the duration of a block."""
    g = _Grant(**fields)
    token = _active.set(tuple(_active.get()) + (g,))
    try:
        yield g
    finally:
        _active.reset(token)


def bind_campaign(g, campaign_id):
    """Write the campaign id onto a grant that was opened without one.

    ONCE. A grant whose campaign is already bound refuses a second binding:
    rebinding is how one authorization would come to cover two campaigns,
    which is the thing this module exists to prevent.
    """
    if not campaign_id:
        raise ScopeRefused("bind_campaign needs the id the provider returned")
    if g.campaign_id is not None and str(g.campaign_id) != str(campaign_id):
        raise ScopeRefused(
            "grant %s is already bound to campaign %r and may not be rebound "
            "to %r" % (g.execution_id, g.campaign_id, campaign_id))
    g.campaign_id = str(campaign_id)
    return g


def require(operation, *, client, provider, campaign_id=None, recipient=None,
            phase=SETUP):
    """The gate. Returns the grant that admits this, or raises.

    Every dimension must match. A missing grant, a grant for another client,
    another provider, another campaign, another recipient or another phase is
    a refusal, and so is a grant that does not name this operation.
    """
    reasons = []
    for g in active():
        if g.phase != phase:
            reasons.append("%s is phase %s" % (g.execution_id, g.phase))
            continue
        if g.client != client:
            reasons.append("%s is for client %r" % (g.execution_id, g.client))
            continue
        if g.provider != provider:
            reasons.append("%s is for provider %r"
                           % (g.execution_id, g.provider))
            continue
        if operation not in g.operations:
            reasons.append("%s does not name %s" % (g.execution_id, operation))
            continue
        # THE CAMPAIGN. `None` on the grant means "not created yet" and admits
        # only a call that also passes None - the bootstrap. Once bound, an
        # exact match is required and a call with no campaign is refused.
        if g.campaign_id is None:
            if campaign_id is not None:
                reasons.append("%s is unbound and cannot admit campaign %r"
                               % (g.execution_id, campaign_id))
                continue
        else:
            if campaign_id is None or str(campaign_id) != str(g.campaign_id):
                reasons.append("%s is bound to campaign %r, not %r"
                               % (g.execution_id, g.campaign_id, campaign_id))
                continue
        if g.recipient is not None and recipient is not None:
            if str(recipient).strip().lower() != str(g.recipient).strip().lower():
                reasons.append("%s is for recipient %r"
                               % (g.execution_id, g.recipient))
                continue
        return g
    raise ScopeRefused(
        "no campaign-scoped grant admits %s for client=%r provider=%r "
        "campaign=%r recipient=%r phase=%r. %s"
        % (operation, client, provider, campaign_id, recipient, phase,
           ("Grants in scope: " + "; ".join(reasons)) if reasons
           else "No grant is in scope; the default is refuse."))


def admits(operation, **kw):
    """`require` as a boolean, for a caller reporting rather than acting."""
    try:
        require(operation, **kw)
        return True
    except ScopeRefused:
        return False
