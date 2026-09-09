#!/usr/bin/env python3
"""Who is allowed to appear in one prospect's inbox.

## Why a team, when pairings already exist

`senderidentity.new_pairing` says "Anna's email goes with Petar's LinkedIn".
That is the right model for a two-person sequence and it does not extend: an
account-based campaign may involve two email humans and two LinkedIn humans
working three decision makers, and a set of pairings cannot express "these
four people, and nobody else".

A team is that closed set. It exists to make one guarantee:

    A sender outside the authorised team never enters a prospect's cadence.

Without it, "which humans might this company hear from" has no answer short
of reading every cadence node in every campaign. With it, the answer is one
list, and `cadencegraph.validate` refuses a graph that names anybody else.

## Not rotation

The team is an allowlist, not a pool to shuffle. Nothing here picks a sender.
Assignment stays with `src/assignment.py`, which is sticky and stored on the
contact, because a prospect who gets three emails from three different people
because a load balancer felt like it is a prospect who has learned exactly
what this is.

The team says *who may*; the assignment says *who does*; the touch log says
*who did*. Three different questions, and conflating any two of them is how a
message ends up signed by somebody who never wrote to that person.

## Stored with the sender roster

Teams live in the same JSONL as senders, accounts and pairings, under
`kind: "outreach_team"`, so they move with `store.use_directory` and are
scoped by workspace like everything else there.
"""
from . import senderidentity as si, store

TEAM = "outreach_team"

EMAIL = si.EMAIL
LINKEDIN = si.LINKEDIN


class TeamError(ValueError):
    """The team is not one this system will use."""


def new_team(workspace, team_id, name, email_senders=(), linkedin_senders=(),
             campaign_id=None, note=None):
    """A named set of humans authorised for a campaign.

    `campaign_id=None` is a workspace-level team; a campaign-scoped one wins
    over it. Same precedence rule as pairings, deliberately - two different
    precedence rules for two nearly identical objects is how somebody
    eventually gets the wrong one.
    """
    if not si.valid_id(team_id):
        raise TeamError(f"not a usable team id: {team_id!r}")
    email_senders = [s for s in email_senders if s]
    linkedin_senders = [s for s in linkedin_senders if s]
    if not email_senders and not linkedin_senders:
        raise TeamError("a team with nobody on it authorises nothing")
    return {
        "kind": TEAM,
        "workspace": workspace,
        "team_id": team_id,
        "name": name,
        "email_senders": list(dict.fromkeys(email_senders)),
        "linkedin_senders": list(dict.fromkeys(linkedin_senders)),
        "campaign_id": campaign_id,
        "note": note,
        "created_at": store.now(),
    }


def teams(workspace, rows=None, campaign_id=None):
    """Every team for this workspace, campaign-scoped ones first."""
    rows = si.load() if rows is None else rows
    found = [r for r in rows
             if r.get("kind") == TEAM and r.get("workspace") == workspace]
    if campaign_id is not None:
        found = [r for r in found
                 if r.get("campaign_id") in (None, campaign_id)]
    found.sort(key=lambda t: (t.get("campaign_id") is None,
                              str(t.get("team_id"))))
    return found


def team(workspace, team_id, rows=None):
    for entry in teams(workspace, rows):
        if entry.get("team_id") == team_id:
            return entry
    return None


def team_for(workspace, campaign_id=None, team_id=None, rows=None):
    """The team in force. Explicit id, then campaign-scoped, then workspace.

    Returns None when nothing is configured, which callers must treat as "no
    restriction recorded" rather than "nobody is allowed" - a workspace that
    has not set up teams should still be able to run a campaign, and
    `cadencegraph.validate` only enforces a team it was given.
    """
    if team_id:
        return team(workspace, team_id, rows)
    found = teams(workspace, rows, campaign_id)
    for entry in found:
        if entry.get("campaign_id") == campaign_id and campaign_id is not None:
            return entry
    return found[0] if found else None


def members(entry, channel=None):
    """Sender ids on the team, optionally for one channel."""
    if not entry:
        return []
    if channel == EMAIL:
        return list(entry.get("email_senders") or [])
    if channel == LINKEDIN:
        return list(entry.get("linkedin_senders") or [])
    return list(dict.fromkeys(list(entry.get("email_senders") or [])
                              + list(entry.get("linkedin_senders") or [])))


def allows(entry, sender_id, channel=None):
    """May this human appear in this cadence? Returns (bool, why).

    No team configured means no restriction *recorded*, and this returns True
    with a reason saying so. A screen showing that sentence is showing the
    truth; silently returning True with no explanation would let somebody
    believe a restriction was checked when none exists.
    """
    if entry is None:
        return True, "no outreach team is configured for this campaign"
    if not sender_id:
        return False, "no sender was named"
    if sender_id in members(entry, channel):
        return True, f"{sender_id} is on team {entry.get('name')}"
    if channel and sender_id in members(entry):
        return False, (f"{sender_id} is on team {entry.get('name')} but not "
                       f"for {channel}")
    return False, (f"{sender_id} is not on team {entry.get('name')}; a sender "
                   f"outside the team must not enter a prospect's cadence")


def describe(entry, workspace=None, rows=None):
    """The team with display names attached, for a screen."""
    if entry is None:
        return None
    rows = si.load() if rows is None else rows
    names = {s["sender_id"]: s.get("display_name") or s["sender_id"]
             for s in si.senders(workspace or entry.get("workspace"), rows)}
    return {
        "team_id": entry.get("team_id"),
        "name": entry.get("name"),
        "campaign_id": entry.get("campaign_id"),
        "scope": "campaign" if entry.get("campaign_id") else "workspace",
        "email": [{"sender_id": s, "name": names.get(s, s)}
                  for s in entry.get("email_senders") or []],
        "linkedin": [{"sender_id": s, "name": names.get(s, s)}
                     for s in entry.get("linkedin_senders") or []],
        "size": len(members(entry)),
        "note": entry.get("note"),
    }


def install(entries, rows=None):
    """Add teams to the roster. Replaces one with the same id."""
    rows = si.load() if rows is None else list(rows)
    keep = []
    incoming = {(e["workspace"], e["team_id"]) for e in entries}
    for row in rows:
        if row.get("kind") == TEAM and \
                (row.get("workspace"), row.get("team_id")) in incoming:
            continue
        keep.append(row)
    si.save(keep + list(entries))
    return si.load()


def validate_against(graph, entry, workspace=None, rows=None):
    """Every node whose sender is not on the team.

    `cadencegraph.validate` does the same check when handed a team list; this
    is the friendlier form for a screen, returning names rather than ids.
    """
    rows = si.load() if rows is None else rows
    names = {s["sender_id"]: s.get("display_name") or s["sender_id"]
             for s in si.senders(workspace or (entry or {}).get("workspace"),
                                 rows)}
    offenders = []
    for key, node in sorted((graph.get("nodes") or {}).items()):
        sender = node.get("sender_id")
        if not sender:
            continue
        ok, why = allows(entry, sender, node.get("channel"))
        if not ok:
            offenders.append({"node": key, "sender_id": sender,
                              "sender": names.get(sender, sender),
                              "why": why})
    return offenders
