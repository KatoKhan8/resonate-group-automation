#!/usr/bin/env python3
"""Who may do what. One table, no authentication.

This is deliberately the smallest thing that works: a role name maps to a set
of permissions, and every caller asks `may(role, PERMISSION)` before acting.
There is no login, no session and no UI, because none of those exist yet. What
matters now is that permission is asked in the same way everywhere, so when a
web layer does arrive it fills in *who the user is* and changes nothing about
*what they are allowed to do*.

The one rule worth stating: approving a campaign and launching it are separate
permissions. A reviewer may bless the words without being able to start the
sending, which is what keeps a single mistaken click from putting mail on the
wire.
"""

ADMIN = "admin"
REVIEWER = "reviewer"
VIEWER = "viewer"
ROLES = (ADMIN, REVIEWER, VIEWER)

# Permissions, named for the action rather than the screen.
READ = "read"
APPROVE_DRAFT = "approve_draft"
APPROVE_CAMPAIGN = "approve_campaign"
REJECT_CAMPAIGN = "reject_campaign"
LAUNCH_CAMPAIGN = "launch_campaign"
PAUSE_CAMPAIGN = "pause_campaign"
RESUME_CAMPAIGN = "resume_campaign"
CHANGE_MAPPING = "change_mapping"
ASSIGN_OWNER = "assign_owner"
MARK_MEETING = "mark_meeting"

PERMISSIONS = (READ, APPROVE_DRAFT, APPROVE_CAMPAIGN, REJECT_CAMPAIGN,
               LAUNCH_CAMPAIGN, PAUSE_CAMPAIGN, RESUME_CAMPAIGN, CHANGE_MAPPING,
               ASSIGN_OWNER, MARK_MEETING)

GRANTS = {
    ADMIN: set(PERMISSIONS),
    # A reviewer blesses words and campaigns, and can stop a run, but cannot
    # start one and cannot repoint a campaign at a different external id.
    REVIEWER: {READ, APPROVE_DRAFT, APPROVE_CAMPAIGN, REJECT_CAMPAIGN,
               PAUSE_CAMPAIGN, ASSIGN_OWNER, MARK_MEETING},
    VIEWER: {READ},
}


class NotPermitted(RuntimeError):
    """The actor's role does not carry this permission. Nothing happened."""


def role_of(config, actor, default=VIEWER):
    """The role a configured actor holds. Unknown actors get the least.

    Config shape, under a client's `slack:` block or a system config:

        allowed_approvers: [U123, U456]      -> admin
        allowed_reviewer_groups: [S789]      -> reviewer
    """
    slack = (config or {}).get("slack") or {}
    if actor in (slack.get("allowed_approvers") or []):
        return ADMIN
    if actor in (slack.get("allowed_reviewers") or []):
        return REVIEWER
    roles = (config or {}).get("roles") or {}
    for role in ROLES:
        if actor in (roles.get(role) or []):
            return role
    return default


def may(role, permission):
    if permission not in PERMISSIONS:
        raise ValueError(f"unknown permission: {permission}")
    return permission in GRANTS.get(role, set())


def require(role, permission, actor=None):
    if not may(role, permission):
        raise NotPermitted(
            f"{actor or 'this actor'} holds role {role!r}, which does not carry "
            f"{permission!r}")
    return True


def permissions_of(role):
    return sorted(GRANTS.get(role, set()))
