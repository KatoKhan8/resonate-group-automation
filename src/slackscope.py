#!/usr/bin/env python3
"""Which channel may hear what. The isolation boundary for the Slack agent.

OPERATOR, 2026-09-21: "Every channel is bound to a scope: internal (Resonate
team) or one client workspace. Unbound channels get read-only generic answers
only. Binding lives in workspace policy, set by the operator."

## THE BOUNDARY IS THE MATERIAL, NOT THE PROMPT

A client channel is safe because **the model is never handed another
client's data**, not because it was told not to repeat it. Scoping happens
three times, in this order, and the first one is the one that matters:

1. `Scope.tools()` removes every tool the scope may not call, so the
   readback is never taken.
2. `Scope.filter_pack()` removes every section and every other workspace
   from the knowledge pack before it is rendered into a prompt.
3. `Scope.check_outbound()` reads the finished text and REFUSES it if a
   forbidden term survived.

Step 3 exists to catch a mistake in steps 1 and 2. It is a backstop, and a
system whose only defence is a backstop has none - which is why the tests in
`tests/test_slack_agent_scope.py` assert the *material*, not the wording.

## THE THREE SCOPES

    internal    the Resonate team. Full detail, including who works on
                what, incidents, credits, engineering and every workspace.
    client      exactly one workspace. That client's own leads, accounts,
                campaigns, cadences and sends - and nothing else that
                exists. No other client, no Resonate-internal worker, no
                incident, no credit position, no engineering.
    unbound     a channel nobody bound. Generic, read-only, no client data
                at all. NOT a soft internal: an unbound channel may be
                anywhere, including a shared channel with a client in it.

A DM is scoped to what that Slack user is allowed to see, which is a
workspace question and not a channel one, so it resolves through the same
policy and lands on one of the same three.

## WHY UNBOUND IS THE DEFAULT

`resolve` returns `unbound` for anything it cannot prove. A channel id that
appears in no policy is not "probably internal" - it is a channel this
module has never heard of, and the only safe answer about a channel you
cannot identify is the one that discloses nothing.
"""
import os
import re

from . import workspaces

# ------------------------------------------------------------------ scopes

INTERNAL = "internal"
CLIENT = "client"
UNBOUND = "unbound"

SCOPES = (INTERNAL, CLIENT, UNBOUND)

#: Channels that are the Resonate team's own. Ids, comma separated. The ops
#: and status channels are internal by construction - they already carry
#: incidents and counts about the machine - and are added automatically.
INTERNAL_CHANNELS_VAR = "SLACK_INTERNAL_CHANNELS"
OPS_CHANNEL_VAR = "SLACK_OPS_CHANNEL"
STATUS_CHANNEL_VAR = "SLACK_STATUS_CHANNEL"

#: The workspace policy key that binds a channel to a client workspace for
#: the AGENT. Deliberately NOT `slack.workspace_channel`: that one is where
#: notifications are posted, and a channel being a good place to receive a
#: positive-reply alert is not the operator saying an agent may converse
#: there. Two different decisions get two different keys.
AGENT_CHANNEL_KEY = "slack.agent_channel"

#: Slack user ids that get internal scope in a DM. The operator's own id
#: belongs here; so does anybody on the Resonate team.
INTERNAL_USERS_KEY = "slack.internal_users"
INTERNAL_USERS_VAR = "SLACK_INTERNAL_USERS"

#: The one Slack user id that may approve a change request. Phase B reads
#: it; Phase A records it in the pack so "who can approve" is answerable.
OPERATOR_USER_VAR = "SLACK_OPERATOR_USER"

#: Slack user id -> workspace, recorded in workspace policy as a comma list.
WORKSPACE_USERS_KEY = "slack.workspace_users"


def _csv_env(name):
    return tuple(part.strip() for part in
                 (os.environ.get(name) or "").split(",") if part.strip())


def _policy_list(policy, key):
    """A policy value that may be a list OR a comma-separated string.

    `workspaces.coerce_policy` stores a `list` key as a real list, but the
    same key set by hand in `work/workspaces.jsonl` is a string. Reading
    only one of the two shapes would make a correctly-set binding look
    absent, and an absent binding silently widens nothing - it narrows a DM
    to unbound, which is a support call, not a breach.
    """
    raw = (policy or {}).get(key)
    if isinstance(raw, (list, tuple)):
        return [str(part).strip() for part in raw if str(part).strip()]
    return [part.strip() for part in str(raw or "").split(",") if part.strip()]


def internal_channels():
    """Every channel id the Resonate team owns, from env only.

    Env rather than workspace policy because an internal channel belongs to
    no workspace, and putting it under one would make it look like that
    client's channel - the exact confusion this module exists to prevent.
    """
    ids = set(_csv_env(INTERNAL_CHANNELS_VAR))
    for var in (OPS_CHANNEL_VAR, STATUS_CHANNEL_VAR):
        value = (os.environ.get(var) or "").strip()
        if value:
            ids.add(value)
    return ids


def internal_users(rows=None):
    """Slack user ids that hold internal scope in a DM."""
    ids = set(_csv_env(INTERNAL_USERS_VAR))
    operator = (os.environ.get(OPERATOR_USER_VAR) or "").strip()
    if operator:
        ids.add(operator)
    for entry in workspaces.workspaces(rows):
        policy = (entry.get("settings") or {}).get("policy") or {}
        ids.update(_policy_list(policy, INTERNAL_USERS_KEY))
    return ids


def client_channels(rows=None):
    """`{channel id: workspace slug}` from workspace policy.

    A channel bound to two workspaces is bound to NEITHER. An ambiguous
    binding is the one case where guessing is worst: it would answer about
    one client in a channel that may belong to another.
    """
    seen = {}
    conflicted = set()
    for entry in workspaces.workspaces(rows):
        slug = entry.get("slug")
        policy = (entry.get("settings") or {}).get("policy") or {}
        channel = str(policy.get(AGENT_CHANNEL_KEY) or "").strip()
        if not channel:
            continue
        if channel in seen and seen[channel] != slug:
            conflicted.add(channel)
        seen[channel] = slug
    for channel in conflicted:
        seen.pop(channel, None)
    return seen


# -------------------------------------------------------------- the terms
#
# What a CLIENT channel may never contain. Each entry is a word matched
# case-insensitively against the finished answer.

#: Resonate's own workers. Named, because a client hearing "Qwen is reworking
#: task 241" learns how their outreach is built and that is not theirs.
INTERNAL_WORKER_TERMS = (
    "claude code", "qwen", "glm", "grok", "buggie",
    "subagent", "model worker",
)

#: Engineering and incident vocabulary.
INTERNAL_ENGINEERING_TERMS = (
    "task-", "issue-", "refuted-", "problem register", "commit",
    "merge request", "regression test", "test suite", "worktree",
    "traceback", "stack trace", "pytest",
)

#: Money and machine capacity. A client's own send counts are theirs; what
#: Resonate spends to produce them is not.
INTERNAL_COMMERCIAL_TERMS = (
    "credit", "spend", "cost per", "api key",
    "contactout", "reoon", "ai ark", "aiark", "blitz",
    "apify", "openrouter",
)

#: Provider estate vocabulary. A client is told their campaign is sending;
#: they are not told which vendor's estate carries it.
#:
#: OPERATOR, 2026-09-22: "a client's OWN senders are the client's own data."
#: `mailbox` and `seat` came OFF this list with that decision, because the
#: people sending for Productive are Productive's own staff and half of them
#: are in the channel. Refusing to say "mailbox" to the person whose mailbox
#: it is was the module being cautious about the wrong thing.
#:
#: `attested` and `attestation` STAY, and not as an oversight. The operator
#: asked for the words "authorized senders", and how attestation works is
#: Resonate's internal control rather than a fact about the client's
#: estate - so the vocabulary is enforced here rather than hoped for in a
#: prompt. `warmup` stays for the same reason: it is a property of how we
#: run an estate, and it is not on the list of what a client may be told.
INTERNAL_PROVIDER_TERMS = (
    "emailbison", "email bison", "bison", "heyreach", "hey reach",
    "warmup", "attested", "attestation",
)

#: HOW WE RUN THE EXPERIMENT, which is ours and not the client's.
#:
#: `slackclientview.plain_campaign_label` already takes these words out of
#: campaign NAMES before the material is built, and that closed half of the
#: fault: the first live client answer said "US-hours kontrolne kampanje"
#: because the campaign was called that. The other half is the model
#: writing the framing itself - out of the thread above it, or out of its
#: own sense of what it is describing - and a readback fix cannot reach
#: that. So the vocabulary is enforced on the finished answer too.
#:
#: DELIBERATELY NARROWER THAN THE LABEL LIST. `test`, `arm`, `batch`,
#: `variant` and `pilot` are on the label list and are NOT here: they are
#: ordinary words, a false positive discards a whole correct answer, and
#: `UNBOUND_EXTRA_TERMS` below records what happened last time this list
#: reached for a word that had innocent uses. Only phrases with no innocent
#: reading in a client channel are here.
#:
#: `kontroln` is the one stem rather than a phrase, and it is here because
#: it is the exact word that went out. The Croatian adjective
#: kontrolna/kontrolni/kontrolne in an outbound conversation is about our
#: control campaign; "kontrola" and "kontrolirati" do not match it.
INTERNAL_EXPERIMENT_TERMS = (
    "control campaign", "control arm", "control cohort", "kontroln",
    "canary", "holdout", "cohort", "kohort",
    "us-hours", "eu-hours", "zagreb-hours", "li-heavy", "liheavy",
)

CLIENT_FORBIDDEN_TERMS = (INTERNAL_WORKER_TERMS + INTERNAL_ENGINEERING_TERMS
                          + INTERNAL_COMMERCIAL_TERMS
                          + INTERNAL_PROVIDER_TERMS
                          + INTERNAL_EXPERIMENT_TERMS)

#: An UNBOUND channel adds nothing to that list, and the reason is worth
#: writing down because the first version of this added four words and broke
#: the scope's whole purpose.
#:
#: "lead" was one of them - so the agent could not say "lead generation
#: engine", which is the ONE sentence an unbound channel exists to be able
#: to say. A term list that blocks the product's own name for itself is not
#: cautious, it is broken.
#:
#: An unbound channel is safe for a different reason: it is handed NO tools
#: and NO workspace material at all - `filter_pack` gives it the identity
#: section and nothing else - so there is no client datum in the prompt for
#: a word list to have to catch. Blocking the vocabulary as well would be
#: guarding the empty room and locking the door on the way out.
UNBOUND_EXTRA_TERMS = ()


#: Per-stage maps whose KEYS are internal diagnostics rather than numbers. The
#: counts beside them are the client's own business and stay; the reasons are
#: ours and do not.
_INTERNAL_REASON_KEYS = ("held_by_reason", "dropped_by_reason",
                         "refused_by_reason")


def _client_safe_workspace(workspace):
    """A workspace's own figures, with our internal reason strings removed.

    **THE LEAK WAS IN THE KEYS, NOT THE VALUES.** `s5_verification` carries
    `held_by_reason`, and its keys read "catch-all cleared by <verifier>, but
    only 1 of 2 required independent confirmations" - which names a provider
    to the client, in client-facing material, which the routing policy forbids
    and which every other client-facing guard already refuses. A scan that
    walks values and not keys sees nothing, and that is how this survived
    until Phase C3's live-pack test asserted against the real pack rather
    than a fixture.

    The COUNTS stay. A client may know how many addresses were held; which
    verifier held them, and how our confirmation policy is shaped, is ours.
    """
    if not isinstance(workspace, dict):
        return workspace
    stages = workspace.get("stages")
    if not isinstance(stages, dict):
        return workspace
    safe_stages = {}
    for name, stage in stages.items():
        if not isinstance(stage, dict):
            safe_stages[name] = stage
            continue
        cleaned = {k: v for k, v in stage.items()
                   if k not in _INTERNAL_REASON_KEYS}
        for key in _INTERNAL_REASON_KEYS:
            if isinstance(stage.get(key), dict):
                # The shape is kept so a reader sees the figure exists and is
                # withheld, rather than silently seeing no holds at all.
                cleaned[f"{key}_count"] = sum(
                    v for v in stage[key].values() if isinstance(v, int))
        safe_stages[name] = cleaned
    out = dict(workspace)
    out["stages"] = safe_stages
    return out


class ScopeViolation(RuntimeError):
    """The answer carried something this channel may not hear.

    Raised rather than redacted. A redacted answer still tells the reader
    that something was withheld about somebody, and a caller that believes
    it answered safely when it stripped a name learns nothing.
    """


class Scope:
    """One resolved channel binding. Immutable, cheap, and asked everything.

    `workspace` is set only for CLIENT. `source` records WHY the scope is
    what it is, so an answer can say "this channel is not bound" and a log
    can be read back later without re-deriving the binding.
    """

    __slots__ = ("kind", "workspace", "source", "user", "channel", "slugs")

    def __init__(self, kind, workspace=None, source="", user=None,
                 channel=None, slugs=None):
        if kind not in SCOPES:
            raise ValueError("unknown scope: %r" % (kind,))
        if kind == CLIENT and not workspace:
            raise ValueError("a client scope must name its workspace")
        if kind != CLIENT and workspace:
            raise ValueError("a %s scope names no workspace" % kind)
        self.kind = kind
        self.workspace = workspace
        self.source = source
        self.user = user
        self.channel = channel
        # EVERY WORKSPACE SLUG THAT EXISTED WHEN THIS SCOPE WAS RESOLVED.
        #
        # Captured rather than re-read, because `check_outbound` asking the
        # store again is a second read that can disagree with the first: if
        # it fails or comes back empty, the slug check passes vacuously and
        # a client name walks straight through the backstop. `coverage()`
        # defaulting to an empty tuple and therefore passing on nothing is
        # ISSUE F-003 in this project's own register, and this is the same
        # shape. The set that decided the binding is the set that polices
        # the answer.
        self.slugs = tuple(slugs) if slugs is not None else None

    def __repr__(self):
        target = " %s" % self.workspace if self.workspace else ""
        return "<Scope %s%s via %s>" % (self.kind, target, self.source)

    # ------------------------------------------------------------ queries

    @property
    def is_internal(self):
        return self.kind == INTERNAL

    @property
    def is_client(self):
        return self.kind == CLIENT

    @property
    def is_unbound(self):
        return self.kind == UNBOUND

    def known_slugs(self, rows=None):
        """Every workspace slug this scope was resolved against."""
        if self.slugs is not None:
            return self.slugs
        return _all_slugs(rows)

    def workspaces_visible(self, rows=None):
        """Exactly which workspace slugs this scope may hear about."""
        if self.kind == INTERNAL:
            return self.known_slugs(rows)
        if self.kind == CLIENT:
            return (self.workspace,)
        return ()

    def may_see_workspace(self, slug, rows=None):
        return slug in self.workspaces_visible(rows)

    def forbidden_terms(self):
        if self.kind == INTERNAL:
            return ()
        if self.kind == CLIENT:
            # A CLIENT'S OWN NAME IS NEVER A FORBIDDEN WORD IN THEIR OWN
            # CHANNEL. One of the workspaces here is called `contactout`,
            # which is also a provider on the commercial list - so every
            # answer naming that client by name was being discarded in that
            # client's own channel.
            #
            # A word list cannot tell "ContactOut the vendor we buy from"
            # from "ContactOut the client we work for", and refusing to say
            # a customer's name is unmistakably the worse of the two errors
            # - the same judgement `UNBOUND_EXTRA_TERMS` records about
            # blocking the word "lead".
            mine = str(self.workspace or "").strip().lower()
            return tuple(t for t in CLIENT_FORBIDDEN_TERMS
                         if not (mine and t == mine))
        return CLIENT_FORBIDDEN_TERMS + UNBOUND_EXTRA_TERMS

    # ------------------------------------------------------------ filters

    def filter_pack(self, pack):
        """The knowledge pack as THIS scope may see it.

        Internal gets it whole. A client gets the identity section, the
        policies that govern their own sending, and their own workspace -
        with every other workspace removed from the structure rather than
        hidden behind a flag. An unbound channel gets identity only.
        """
        if not isinstance(pack, dict):
            return {}
        if self.kind == INTERNAL:
            return pack
        out = {"built_at": pack.get("built_at"),
               "scope": self.kind,
               "identity": self._identity_for_scope(
                   pack.get("identity"))}
        if self.kind == UNBOUND:
            return out
        out["policies"] = client_safe_policies(pack.get("policies") or [])
        everything = pack.get("workspaces") or {}
        mine = everything.get(self.workspace)
        out["workspaces"] = ({self.workspace: _client_safe_workspace(mine)}
                             if mine else {})
        return out

    def _identity_for_scope(self, identity):
        """The product description as this scope may be handed it.

        THE MATERIAL MAY NOT CONTAIN A WORD THE ANSWER IS CHECKED FOR. That
        is the rule this implements, and it was learnt the hard way: asked
        "what is Resonate OS" in an unbound channel, the model wrote a good
        paragraph ending "...which is what keeps one client's data, senders
        and spend from ever touching another's" - paraphrasing
        PRODUCT-GOAL's own cross-client list, which says "one client's spend
        reaching another's ledger". The backstop then refused the answer for
        containing "spend", **a word the material had supplied**. The reader
        got a fallback sentence instead of a correct paragraph, and nothing
        had leaked.

        A check that fires on its own input is not a safety property, it is
        a bug with a good reputation. So the identity section is filtered
        here - any line naming a workspace this scope may not see, and any
        line carrying a term the answer will be checked against - and what
        survives is safe to repeat in full.

        The same reasoning covers "Not a Productive-specific automation",
        which is correct in the document and a disclosure in another
        client's channel.
        """
        if not isinstance(identity, dict):
            return identity
        allowed = set(self.workspaces_visible())
        banned = [slug for slug in self.known_slugs()
                  if slug and slug not in allowed]
        banned += list(self.forbidden_terms())
        if not banned:
            return identity

        def carries(value):
            lowered = str(value).lower()
            return any(term in lowered for term in banned)

        out = {}
        for key, value in identity.items():
            if isinstance(value, list):
                kept = [row for row in value if not carries(row)]
                if kept:
                    out[key] = kept
            elif isinstance(value, str):
                if not carries(value):
                    out[key] = value
            else:
                out[key] = value
        return out

    def check_outbound(self, text, rows=None):
        """The backstop. Returns the text, or raises `ScopeViolation`."""
        body = str(text or "")
        lowered = body.lower()
        for term in self.forbidden_terms():
            if term in lowered:
                raise ScopeViolation(
                    "an answer for a %s channel contained %r, which that "
                    "channel may not hear" % (self.kind, term))
        for slug in self.known_slugs(rows):
            if slug and slug in lowered and not self.may_see_workspace(
                    slug, rows):
                raise ScopeViolation(
                    "an answer for a %s channel named the workspace %r, "
                    "which it may not hear about" % (self.kind, slug))
        return body


def _all_slugs(rows=None):
    return tuple(str(w.get("slug") or "").lower()
                 for w in workspaces.workspaces(rows) if w.get("slug"))


#: Policy rows a client may hear: the ones that govern what reaches THEIR
#: prospects. A client is entitled to know their own people are contacted at
#: most so often and stopped on a reply. They are not entitled to Resonate's
#: provider order or its spend rule.
CLIENT_SAFE_POLICY_IDS = (
    "collision-recency", "pacing", "hard-stops", "client-approval-cycle",
    "cross-channel", "reengagement-lanes", "dual-channel",
)


#: Fields a client never sees on a policy, whatever the policy is.
#: `internal_note` is self-describing. `source` is a path into our
#: repository: it is where WE keep the decision, tells a client nothing
#: they can act on, and is the same class of thing as a commit id.
POLICY_FIELDS_WITHHELD = ("internal_note", "source")


def client_safe_policies(rows):
    """The policies a client may hear, with their internal text removed.

    TWO SEPARATE QUESTIONS, AND ONLY ONE OF THEM USED TO BE ASKED.
    `CLIENT_SAFE_POLICY_IDS` says a policy's SUBJECT is the client's
    business. It says nothing about the words the rule happens to be
    written in, and the rules here are written for the operator.

    `client-approval-cycle` is the row that proved it: an allow-listed
    policy whose rule text names both providers, the attestation control
    and what we spend - "one EmailBison campaign per attested human, 8
    max... credits spent. Then wait 15 minutes. If I do not veto...". That
    is the operating procedure, and it was going into every client prompt.

    This matters more than a leak that the outbound guard would catch,
    because `Scope._identity_for_scope` states the property the rest of the
    module depends on: THE MATERIAL MAY NOT CONTAIN A WORD THE ANSWER IS
    CHECKED FOR. When it does, an honest answer that quotes the policy is
    discarded by the guard and the reader gets a hedge - a correct system
    reading as an evasive one, which is the failure `slackagenttools.run`
    documents at length.

    So the rule text is checked against the same term list the answer is,
    and a rule that fails is withheld with a line saying so. The title and
    the why survive, because THAT a policy exists is a fact about how the
    client's outreach is run and is theirs.
    """
    out = []
    for row in rows or []:
        if row.get("id") not in CLIENT_SAFE_POLICY_IDS:
            continue
        clean = {k: v for k, v in row.items()
                 if k not in POLICY_FIELDS_WITHHELD}
        rule = str(clean.get("rule") or "").lower()
        if any(term in rule for term in CLIENT_FORBIDDEN_TERMS):
            clean["rule"] = ("the wording of this rule is Resonate's own "
                             "operating detail and is not shown here. What "
                             "it governs is in `why`.")
            clean["rule_withheld"] = True
        out.append(clean)
    return out


# ----------------------------------------------------------------- resolve

def resolve(channel=None, user=None, channel_type=None, rows=None):
    """The scope for one incoming message. Never raises, never guesses.

    `channel_type` is Slack's own: `im` for a DM. A DM is resolved by USER,
    because a DM channel id is per-conversation and binding one would mean
    the operator maintaining a row per person per client.
    """
    try:
        rows = workspaces.load() if rows is None else rows
    except Exception:                                           # noqa: BLE001
        # A workspace store that cannot be read is not a reason to widen a
        # scope. It is a reason to narrow every scope to unbound.
        rows = []
    channel = (channel or "").strip() or None
    user = (user or "").strip() or None
    slugs = _all_slugs(rows)

    if channel_type == "im":
        if user and user in internal_users(rows):
            return Scope(INTERNAL, source="dm: internal user", user=user,
                         channel=channel, slugs=slugs)
        slug = workspace_of_user(user, rows)
        if slug:
            return Scope(CLIENT, workspace=slug, source="dm: workspace user",
                         user=user, channel=channel, slugs=slugs)
        return Scope(UNBOUND, source="dm: unknown user", user=user,
                     channel=channel, slugs=slugs)

    if channel and channel in internal_channels():
        return Scope(INTERNAL, source="channel: internal", user=user,
                     channel=channel, slugs=slugs)
    bound = client_channels(rows)
    if channel and channel in bound:
        return Scope(CLIENT, workspace=bound[channel],
                     source="channel: workspace policy", user=user,
                     channel=channel, slugs=slugs)
    return Scope(UNBOUND, source="channel: no binding", user=user,
                 channel=channel, slugs=slugs)


def workspace_of_user(user, rows=None):
    """The single workspace a Slack user belongs to, or None.

    A user listed under two workspaces resolves to NEITHER, for the same
    reason a channel bound twice does: the wrong one is a disclosure.
    """
    if not user:
        return None
    found = set()
    for entry in workspaces.workspaces(rows):
        policy = (entry.get("settings") or {}).get("policy") or {}
        if user in _policy_list(policy, WORKSPACE_USERS_KEY):
            found.add(entry.get("slug"))
    return found.pop() if len(found) == 1 else None


# --------------------------------------------------------------- redaction

_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}")


def redact_addresses(text):
    """No mailbox leaves the agent in any scope but a client's own channel.

    The status-channel rule from `notify._status_payload`, applied to model
    output: counts and domains only.
    """
    return _EMAIL.sub("[address withheld]", str(text or ""))
