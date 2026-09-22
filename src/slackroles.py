#!/usr/bin/env python3
"""Who, inside one client workspace, is asking - and what that licenses.

OPERATOR, 2026-09-22: "Per-user roles inside a client workspace."

Until now every person in a client's channel was the same person to this
agent: the channel resolved to a workspace and the workspace answered.
That is right for reading - what is in a client's channel is that client's
data and everybody in the room can see it - and it is not right for the
change-request flow, where the ticket that reaches the operator says only
"a client asked for this" and the operator has no way to tell whether the
asker is the person who can ask.

## THE ROLE NEVER REFUSES ANYTHING

This is the property to hold on to, and it is the opposite of what a
permission system usually does.

The highest-severity message in the entire Slack corpus is a client
writing, in their own channel:

    can you please stop sending messages to people who have replied????

A role check that made that message wait for the right person to repeat it
would be the worst thing this agent could do. Every request that REDUCES
reach - stop an account, remove a lead, pause a campaign - is taken from
anybody in the channel, always, with no authority check of any kind. The
role is recorded on the ticket and changes nothing about whether it is
raised.

What the role does is tell the OPERATOR what they are looking at, for the
requests that WIDEN or ALTER sending: add a lead, change approved copy,
move a sending window. Those arrive flagged when the requester has no
recorded authority, so the operator knows to confirm rather than assume.
The agent still raises them, still says the same sentence to the client,
and still decides nothing.

## AND IT IS NEVER SAID BACK INTO THE CHANNEL

"You are not authorised to ask for that" is internal framing, and worse, it
is internal framing about a colleague in front of their colleagues. The
flag goes on the ticket and into the ACTION REQUIRED post, which are ours.
The client hears exactly what they heard before.

## WHERE ROLES COME FROM

Workspace policy, beside the users list that already exists:

    "slack.workspace_users": ["U0AAA", "U0BBB"]
    "slack.roles": {"U0AAA": "owner", "U0BBB": "observer"}

A user in the users list with no role entry is a MEMBER - the default, and
the state almost every real user will be in, because nobody will fill this
in for a week. Member is not an error and is not treated as suspicious; it
is simply "no authority recorded either way", which is what the flag says.
"""
import os

#: The person at the client who owns the engagement. Their ask needs no
#: confirming; the ticket says so and the operator can act on it.
OWNER = "owner"

#: Everybody else in the room, and the default for anybody not listed.
#: Their narrowing asks are taken exactly like an owner's; their widening
#: asks are raised with "no recorded authority" on the face of the ticket.
MEMBER = "member"

#: Somebody who reads. Same rules as a member for requests - the role is
#: information for the operator, not a gate - and named separately because
#: an operator who has taken the trouble to write `observer` has said
#: something, and flattening that to `member` throws it away.
OBSERVER = "observer"

ROLES = (OWNER, MEMBER, OBSERVER)

#: The policy key. `slackscope.WORKSPACE_USERS_KEY` says WHO is in the
#: workspace; this says what each of them is.
ROLES_KEY = "slack.roles"

#: Handy for a single-workspace deployment, and for a test.
#: `U0AAA:owner,U0BBB:observer`.
ROLES_VAR = "SLACK_WORKSPACE_ROLES"

#: Ticket kinds that make outreach SMALLER. Taken from anybody, always.
#: This tuple is the safety property of this module and the reason its
#: docstring is longer than its code.
NARROWING_KINDS = ("stop_account", "remove_lead", "pause_campaign")

#: Ticket kinds that make outreach bigger, or change what it says. These
#: are the ones an operator wants attribution on.
WIDENING_KINDS = ("add_lead", "change_copy", "change_window")


def _from_env():
    out = {}
    for part in (os.environ.get(ROLES_VAR) or "").split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        user, _, role = part.partition(":")
        user, role = user.strip(), role.strip().lower()
        if user and role in ROLES:
            out[user] = role
    return out


def roles_for(workspace, rows=None):
    """`{user id: role}` for one workspace. Env first, then policy.

    A role that is not one of `ROLES` is DROPPED rather than kept as a
    string nobody checks. A typo'd role that silently became authority
    would be the one bug this file must not have; a typo'd role that
    becomes `member` is visible the moment somebody looks at a ticket.
    """
    out = dict(_from_env())
    if not workspace:
        return out
    try:
        from . import workspaces
        entries = workspaces.workspaces(rows)
    except Exception:                                           # noqa: BLE001
        # A workspace store that cannot be read gives NO authority to
        # anybody, which is the conservative direction: everything is a
        # member, everything widening is flagged, nothing is refused.
        return out
    for entry in entries:
        if entry.get("slug") != workspace:
            continue
        policy = (entry.get("settings") or {}).get("policy") or {}
        raw = policy.get(ROLES_KEY)
        if isinstance(raw, dict):
            pairs = raw.items()
        elif isinstance(raw, str):
            pairs = [tuple(p.split(":", 1)) for p in raw.split(",")
                     if ":" in p]
        else:
            pairs = []
        for user, role in pairs:
            user, role = str(user).strip(), str(role).strip().lower()
            if user and role in ROLES:
                out[user] = role
    return out


def role_of(user, workspace, rows=None):
    """One person's role. `MEMBER` when nothing is recorded.

    Never None: a caller that has to decide what None means is a caller
    that will decide differently in two places.
    """
    if not user:
        return MEMBER
    return roles_for(workspace, rows).get(user, MEMBER)


def is_recorded(user, workspace, rows=None):
    """Has anybody actually written this person down?

    The flag on a widening ticket is about this, not about the role: an
    operator reading "requester has no recorded role" knows the register is
    empty, whereas "requester is an observer" is a statement somebody made
    on purpose.
    """
    return bool(user) and user in roles_for(workspace, rows)


def narrows(kind):
    return kind in NARROWING_KINDS


def authority_note(kind, user, scope, rows=None):
    """What the TICKET should say about who asked. Never a refusal.

    Returns `(authority, note)`:

        authority  "owner" | "recorded: <role>" | "not recorded" | "internal"
        note       one line for the operator, or None when nothing is worth
                   saying

    A narrowing request gets a note saying it was taken from anybody on
    purpose, so that an operator does not read the absent authority line as
    an oversight and start adding one.
    """
    if not getattr(scope, "is_client", False):
        return "internal", None
    workspace = getattr(scope, "workspace", None)
    role = role_of(user, workspace, rows)
    recorded = is_recorded(user, workspace, rows)

    if narrows(kind):
        return ("owner" if role == OWNER
                else ("recorded: %s" % role if recorded else "not recorded"),
                "This request REDUCES outreach, so it was taken from the "
                "requester without any authority check. That is deliberate: "
                "a stop is never made to wait for the right person to ask.")
    if role == OWNER:
        return "owner", None
    if recorded:
        return ("recorded: %s" % role,
                "The requester is recorded as %s for %s, not as the owner. "
                "This request widens or alters sending - confirm with the "
                "owner before approving." % (role, workspace))
    return ("not recorded",
            "No role is recorded for this requester in %s, so the agent "
            "cannot tell you whether they can ask for this. It widens or "
            "alters sending - confirm before approving. Set "
            "`%s` in the workspace policy to stop seeing this line."
            % (workspace, ROLES_KEY))
