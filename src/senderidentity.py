#!/usr/bin/env python3
"""Who is sending, as distinct from what is sending.

## The distinction this module exists for

An inbox is not a person. A LinkedIn profile is not a person. And the person
behind the email is very often not the person behind the LinkedIn message.

A real client looks like this:

    Anna    anna01@ anna02@ ... anna20@      (one human, twenty inboxes)
    Mark    mark01@ ... mark20@
    John    john01@ ... john20@
    Sarah   sarah01@ ... sarah20@

    Petar LinkedIn      Sarah LinkedIn      Tom LinkedIn

Four email humans across eighty inboxes, and a LinkedIn roster that only
partly overlaps them. `src/senders.py` models the *accounts* - which inbox a
step goes out of, and whether it is over its daily allowance - and models them
well. What it has no concept of is the human, and without that concept there
is no way to answer the question this product now has to answer:

    "My colleague Anna emailed you on Monday" - is that true?

A per-channel account id cannot answer it. `bison-7` and `hr-3` are two
strings; whether they are the same person, two colleagues, or two strangers is
not recoverable from them. So this module adds the layer that was missing, and
deliberately adds it *beside* `senders.py` rather than inside it: that module
is the account-level allocator and stays exactly as correct as it was.

## Three objects, and one relationship

    HumanSenderIdentity   a person. Anna.
    EmailSenderAccount    an inbox. anna07@, owned by Anna.
    LinkedInSenderAccount a profile. "Petar Horvat", owned by Petar.
    SenderPairing         Anna's email goes out alongside Petar's LinkedIn.

Every one carries a workspace and is only ever reachable through a function
that takes a workspace. There is no unscoped read here; `src/repo.py` makes
the same trade for records and for the same reason.

## Capacity is nullable on purpose

`daily_limit` is `None` when nobody has told us what it is, and every caller
has to render that as UNKNOWN rather than as a number. A guessed sending limit
is the kind of number that looks like a control and is not one: it will be
believed, planned against, and wrong.

That is a deliberate difference from `senders.DEFAULT_DAILY_LIMIT`, which
assumes 50 for an account with no configured limit. See "Known conflict" at
the foot of this file.

## No secrets

`provider_account_id` is an identifier - the thing EmailBison or HeyReach
calls this account in its own API. It is not a credential and no credential
belongs on these rows. `tests/test_secrets.py` greps every rendered byte; this
module holds nothing that would fail it.
"""
import argparse
import hashlib
import json
import os
import re

from . import store

# ------------------------------------------------------------------ shapes

SENDER = "sender"
EMAIL_ACCOUNT = "email_account"
LINKEDIN_ACCOUNT = "linkedin_account"
PAIRING = "pairing"
KINDS = (SENDER, EMAIL_ACCOUNT, LINKEDIN_ACCOUNT, PAIRING)

EMAIL = "email"
LINKEDIN = "linkedin"
CHANNELS = (EMAIL, LINKEDIN)

# Health words. Deliberately few, and `unknown` is the default rather than
# `healthy`: an account nobody has checked is not an account known to be fine,
# and a dashboard that renders it green has told a lie a person will act on.
HEALTH_UNKNOWN = "unknown"
HEALTH_OK = "ok"
HEALTH_WARMING = "warming"
HEALTH_PAUSED = "paused"
HEALTH_BLOCKED = "blocked"
HEALTH = (HEALTH_UNKNOWN, HEALTH_OK, HEALTH_WARMING, HEALTH_PAUSED,
          HEALTH_BLOCKED)

# A sender or account id is used in a URL and in a filename-shaped position,
# so it is constrained the same way a client slug is.
ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class SenderError(RuntimeError):
    """The sender configuration could not be read or written as asked."""


class UnknownSender(KeyError):
    """No such sender in this workspace - or one belonging to another."""


class CrossWorkspaceSender(PermissionError):
    """A sender or account from another workspace was reached for.

    Raised rather than returning None, for the reason `repo.CrossClientAccess`
    gives: an empty result reads as "there is nothing there", and the
    difference between "does not exist" and "is not yours" is the difference
    between a bug and a breach.
    """


def valid_id(value):
    return bool(value and ID.match(str(value)))


# ------------------------------------------------------------------- store

def path():
    return os.path.abspath(os.environ.get("SENDERS")
                           or os.path.join(os.path.dirname(store.queue_path()),
                                           "senders.jsonl"))


def load():
    return store.read_jsonl(path())


def save(rows, timeout=None):
    with store.lock(timeout, for_path=path()):
        store.write_jsonl(path(), rows)


def transaction(timeout=None):
    return store.file_transaction(path(), timeout)


def _rows(kind, workspace, rows=None):
    """Every row of one kind in one workspace. There is no unscoped variant."""
    return [r for r in (load() if rows is None else rows)
            if r.get("kind") == kind and r.get("workspace") == workspace]


# ------------------------------------------------------------ constructors

def new_sender(workspace, sender_id, display_name, title=None, team=None,
               active=True, colleague_language=None):
    """One human. The thing a prospect would recognise as a person.

    `colleague_language` is tri-state on purpose: True and False are decisions
    somebody made, and None means nobody has. None is treated as "not
    permitted" everywhere it matters - see `relationship` - but it stays
    distinguishable so a settings screen can say "not configured" rather than
    "off", which are different things to an operator.
    """
    if not valid_id(sender_id):
        raise SenderError(
            f"{sender_id!r} is not a usable sender id: lower-case letters, "
            "digits, hyphens and underscores, up to 64 characters")
    return {
        "kind": SENDER,
        "workspace": workspace,
        "sender_id": sender_id,
        "display_name": display_name,
        "title": title,
        "team": team,
        "active": bool(active),
        "colleague_language": colleague_language,
        "created_at": store.now(),
    }


def new_email_account(workspace, account_id, sender_id, email_address,
                      provider="emailbison", provider_account_id=None,
                      active=True, daily_limit=None, health=HEALTH_UNKNOWN,
                      domain=None):
    """One inbox, owned by one human.

    `daily_limit=None` means nobody has told us, and stays None. See the module
    docstring: an invented limit is worse than an absent one.
    """
    if not valid_id(account_id):
        raise SenderError(f"{account_id!r} is not a usable account id")
    if health not in HEALTH:
        raise SenderError(f"{health!r} is not a health state")
    address = str(email_address or "").strip().lower()
    if "@" not in address:
        raise SenderError(f"{email_address!r} is not an email address")
    return {
        "kind": EMAIL_ACCOUNT,
        "workspace": workspace,
        "account_id": account_id,
        "sender_id": sender_id,
        "provider": provider,
        # What the provider calls this account. An identifier, never a secret.
        "provider_account_id": provider_account_id,
        "email_address": address,
        "domain": domain or address.rsplit("@", 1)[-1],
        "active": bool(active),
        "daily_limit": None if daily_limit is None else int(daily_limit),
        "health": health,
        "created_at": store.now(),
    }


def new_linkedin_account(workspace, account_id, sender_id, profile_url,
                         provider="heyreach", provider_account_id=None,
                         active=True, daily_limit=None,
                         health=HEALTH_UNKNOWN):
    """One LinkedIn profile, owned by one human.

    The URL is stored through `linkedin.canonical` by the caller that has one;
    this keeps whatever it is given so that a malformed profile is visible on
    the senders screen rather than silently normalised into looking fine.
    """
    if not valid_id(account_id):
        raise SenderError(f"{account_id!r} is not a usable account id")
    if health not in HEALTH:
        raise SenderError(f"{health!r} is not a health state")
    return {
        "kind": LINKEDIN_ACCOUNT,
        "workspace": workspace,
        "account_id": account_id,
        "sender_id": sender_id,
        "provider": provider,
        "provider_account_id": provider_account_id,
        "profile_url": profile_url,
        "active": bool(active),
        "daily_limit": None if daily_limit is None else int(daily_limit),
        "health": health,
        "created_at": store.now(),
    }


def new_pairing(workspace, email_sender_id, linkedin_sender_id,
                campaign_id=None, note=None):
    """Anna's email alongside Petar's LinkedIn.

    `campaign_id=None` is the workspace default. A campaign-scoped pairing
    wins over it, which is the only precedence rule here and is checked in
    `pairing_for`.
    """
    return {
        "kind": PAIRING,
        "workspace": workspace,
        "email_sender_id": email_sender_id,
        "linkedin_sender_id": linkedin_sender_id,
        "campaign_id": campaign_id,
        "note": note,
        "created_at": store.now(),
    }


# ------------------------------------------------------------------- reads

def senders(workspace, rows=None, active_only=False):
    found = _rows(SENDER, workspace, rows)
    if active_only:
        found = [s for s in found if s.get("active")]
    return sorted(found, key=lambda s: (s.get("display_name") or "",
                                        s["sender_id"]))


def sender(workspace, sender_id, rows=None):
    """One human, or a refusal. Never another workspace's."""
    for row in senders(workspace, rows):
        if row["sender_id"] == sender_id:
            return row
    # Present elsewhere is a different answer from absent, and the caller has
    # to be able to tell: one is a typo, the other is a boundary.
    for row in (load() if rows is None else rows):
        if row.get("kind") == SENDER and row.get("sender_id") == sender_id:
            raise CrossWorkspaceSender(
                f"sender {sender_id!r} belongs to another workspace")
    return None


def require_sender(workspace, sender_id, rows=None):
    found = sender(workspace, sender_id, rows)
    if found is None:
        raise UnknownSender(f"no sender {sender_id!r} in {workspace}")
    return found


def email_accounts(workspace, rows=None, sender_id=None, active_only=False):
    found = _rows(EMAIL_ACCOUNT, workspace, rows)
    if sender_id:
        found = [a for a in found if a.get("sender_id") == sender_id]
    if active_only:
        found = [a for a in found if a.get("active")]
    return sorted(found, key=lambda a: a["account_id"])


def linkedin_accounts(workspace, rows=None, sender_id=None, active_only=False):
    found = _rows(LINKEDIN_ACCOUNT, workspace, rows)
    if sender_id:
        found = [a for a in found if a.get("sender_id") == sender_id]
    if active_only:
        found = [a for a in found if a.get("active")]
    return sorted(found, key=lambda a: a["account_id"])


def accounts_for(workspace, channel, rows=None, sender_id=None,
                 active_only=False):
    if channel == EMAIL:
        return email_accounts(workspace, rows, sender_id, active_only)
    if channel == LINKEDIN:
        return linkedin_accounts(workspace, rows, sender_id, active_only)
    raise SenderError(f"{channel!r} is not a channel")


def account(workspace, channel, account_id, rows=None):
    """One provider account, or a refusal if it is somebody else's.

    A provider account id is exactly the kind of string somebody would try in
    a URL, so reaching for another workspace's raises rather than returning
    None - the handler turns that into the same 404 a foreign record gets.
    """
    for row in accounts_for(workspace, channel, rows):
        if row["account_id"] == account_id:
            return row
    kind = EMAIL_ACCOUNT if channel == EMAIL else LINKEDIN_ACCOUNT
    for row in (load() if rows is None else rows):
        if row.get("kind") == kind and row.get("account_id") == account_id:
            raise CrossWorkspaceSender(
                f"{channel} account {account_id!r} belongs to another workspace")
    return None


def by_provider_account(workspace, channel, provider_account_id, rows=None):
    """Resolve a provider's own id back to our account, inside one workspace.

    Scoped deliberately. A provider account id is somebody else's namespace
    and offers no guarantee of uniqueness across tenants, so resolving one
    globally would be a way to walk from a HeyReach id to another client's
    sender roster.
    """
    if not provider_account_id:
        return None
    for row in accounts_for(workspace, channel, rows):
        if str(row.get("provider_account_id") or "") == str(provider_account_id):
            return row
    return None


def pairings(workspace, rows=None, campaign_id=None):
    found = _rows(PAIRING, workspace, rows)
    if campaign_id is not None:
        found = [p for p in found
                 if p.get("campaign_id") in (None, campaign_id)]
    return sorted(found, key=lambda p: (p.get("campaign_id") or "",
                                        p.get("email_sender_id") or ""))


def _named_pairing(pairing, workspace, rows):
    """A pairing carrying the paired human's name as well as their id.

    The senders table shows the owner as "Mara Kovac" and showed who she is
    paired with as `ines`. One column of names beside one column of
    identifiers makes a reader work out that both are people.
    """
    if not pairing:
        return pairing
    linkedin = pairing.get("linkedin_sender_id")
    entry = sender(workspace, linkedin, rows) if linkedin else None
    return dict(pairing, linkedin_display_name=(
        (entry or {}).get("display_name") or linkedin))


def pairing_for(workspace, email_sender_id, campaign_id=None, rows=None):
    """The LinkedIn human paired with this email human, or None.

    A campaign-scoped pairing wins over the workspace default. That is the
    whole precedence rule, and it is one rule so that "why did this contact
    get Petar" has one answer.
    """
    scoped, default = None, None
    for row in pairings(workspace, rows):
        if row.get("email_sender_id") != email_sender_id:
            continue
        if row.get("campaign_id") == campaign_id and campaign_id is not None:
            scoped = row
        elif row.get("campaign_id") is None:
            default = row
    return scoped or default


# ---------------------------------------------------------- the relationship

SAME_PERSON = "same_person"
SAME_TEAM = "same_team"
SAME_COMPANY = "same_company"
UNRELATED = "unknown"


def relationship(workspace, first_id, second_id, rows=None, config=None):
    """How two senders may be described to a prospect.

    The output of this decides whether a message is allowed to say "my
    colleague". Three rules, and the conservative one is the default:

    **The same person is the same person.** No claim is being made about
    anybody else, so this needs no permission.

    **Colleague language is opt-in per workspace.** Two people being active
    senders in one client's workspace is not, by itself, evidence that a
    prospect would recognise them as colleagues - a workspace can hold an
    agency's own staff sending on a client's behalf. `sender_policy.
    colleague_language` in the client config is how somebody says otherwise,
    and until they do the answer is no.

    **A sender may opt out individually.** `colleague_language: false` on a
    sender row refuses regardless of the workspace setting, because the
    narrower "no" should always win.

    Returns a dict rather than a bool so the preview can print *why*.
    """
    if first_id and first_id == second_id:
        return {"kind": SAME_PERSON, "colleague_language_allowed": False,
                "why": "the same person sends on both channels, so no claim "
                       "about anybody else is being made",
                "wording": "self"}

    first = sender(workspace, first_id, rows) if first_id else None
    second = sender(workspace, second_id, rows) if second_id else None
    if not first or not second:
        return {"kind": UNRELATED, "colleague_language_allowed": False,
                "why": "one of the two senders is not a known sender in this "
                       "workspace, so nothing may be claimed about how they "
                       "are related",
                "wording": "neutral"}

    policy = ((config or {}).get("sender_policy") or {})
    workspace_allows = policy.get("colleague_language") is True
    opted_out = (first.get("colleague_language") is False
                 or second.get("colleague_language") is False)

    same_team = bool(first.get("team")) and first.get("team") == second.get("team")
    kind = SAME_TEAM if same_team else SAME_COMPANY

    if opted_out:
        return {"kind": kind, "colleague_language_allowed": False,
                "why": "a sender in this pair has colleague language turned "
                       "off, and the narrower refusal wins",
                "wording": "neutral"}
    if not workspace_allows:
        return {"kind": kind, "colleague_language_allowed": False,
                "why": "this workspace has not enabled "
                       "sender_policy.colleague_language, so two senders "
                       "sharing a workspace is not treated as evidence that a "
                       "prospect would call them colleagues",
                "wording": "neutral"}
    if not (first.get("active") and second.get("active")):
        return {"kind": kind, "colleague_language_allowed": False,
                "why": "a sender in this pair is not active",
                "wording": "neutral"}
    return {"kind": kind, "colleague_language_allowed": True,
            "why": (f"both are active senders in this workspace"
                    + (" on the same team" if same_team else "")
                    + ", and the workspace has enabled colleague language"),
            "wording": "colleague" if same_team else "team"}


# ------------------------------------------------------------- the roster

def roster(workspace, rows=None, config=None):
    """Everything about who can send here, arranged for a screen.

    One read of the file, then everything derived from it - the senders page
    asks four questions and a naive implementation reads the file four times.
    """
    rows = load() if rows is None else rows
    people = senders(workspace, rows)
    emails = email_accounts(workspace, rows)
    profiles = linkedin_accounts(workspace, rows)

    by_sender = {}
    for person in people:
        mine_email = [a for a in emails if a["sender_id"] == person["sender_id"]]
        mine_li = [a for a in profiles if a["sender_id"] == person["sender_id"]]
        by_sender[person["sender_id"]] = {
            **person,
            "email_accounts": mine_email,
            "linkedin_accounts": mine_li,
            "email_account_count": len(mine_email),
            "linkedin_account_count": len(mine_li),
            "active_email_accounts": len([a for a in mine_email if a["active"]]),
            "active_linkedin_accounts": len([a for a in mine_li if a["active"]]),
            "pairing": _named_pairing(
                pairing_for(workspace, person["sender_id"], rows=rows),
                workspace, rows),
        }

    # Accounts whose owner is missing are a real state and are surfaced rather
    # than hidden: an inbox nobody owns is an inbox nobody is accountable for.
    known = {p["sender_id"] for p in people}
    orphans = ([dict(a, channel=EMAIL) for a in emails
                if a["sender_id"] not in known]
               + [dict(a, channel=LINKEDIN) for a in profiles
                  if a["sender_id"] not in known])

    return {
        "workspace": workspace,
        "senders": [by_sender[p["sender_id"]] for p in people],
        "email_accounts": emails,
        "linkedin_accounts": profiles,
        "pairings": pairings(workspace, rows),
        "orphan_accounts": orphans,
        "counts": {
            "senders": len(people),
            "active_senders": len([p for p in people if p["active"]]),
            "email_accounts": len(emails),
            "active_email_accounts": len([a for a in emails if a["active"]]),
            "linkedin_accounts": len(profiles),
            "active_linkedin_accounts": len([a for a in profiles
                                             if a["active"]]),
            "email_senders": len({a["sender_id"] for a in emails}),
            "linkedin_senders": len({a["sender_id"] for a in profiles}),
        },
        "capacity": capacity(workspace, rows),
        "health": health_summary(workspace, rows),
    }


def capacity(workspace, rows=None):
    """What this workspace can send in a day, and what it cannot say.

    Two numbers per channel and they are not interchangeable: `known` is the
    sum of the limits somebody configured, and `unknown_accounts` is how many
    accounts contributed nothing to it because nobody has told us their limit.
    A single total would present a partial sum as a capacity.
    """
    rows = load() if rows is None else rows
    out = {}
    for channel in CHANNELS:
        active = [a for a in accounts_for(workspace, channel, rows)
                  if a.get("active")]
        with_limit = [a for a in active if a.get("daily_limit") is not None]
        out[channel] = {
            "accounts": len(active),
            "accounts_with_a_known_limit": len(with_limit),
            "accounts_with_no_known_limit": len(active) - len(with_limit),
            "known_daily_capacity": sum(a["daily_limit"] for a in with_limit),
            # True when the number above is the whole story. When it is False
            # the caller must not present it as the capacity.
            "complete": len(with_limit) == len(active) and bool(active),
        }
    return out


def health_summary(workspace, rows=None):
    rows = load() if rows is None else rows
    out = {}
    for channel in CHANNELS:
        counts = {state: 0 for state in HEALTH}
        for row in accounts_for(workspace, channel, rows):
            counts[row.get("health") or HEALTH_UNKNOWN] = counts.get(
                row.get("health") or HEALTH_UNKNOWN, 0) + 1
        out[channel] = counts
    return out


# -------------------------------------------------------------- the writes

def add(row, timeout=None):
    """Append one row. The only way anything gets into this file."""
    if row.get("kind") not in KINDS:
        raise SenderError(f"{row.get('kind')!r} is not a sender row")
    with transaction(timeout) as rows:
        rows.append(row)
    return row


def install(rows, timeout=None):
    """Replace the whole roster. Demo mode and tests only."""
    for row in rows:
        if row.get("kind") not in KINDS:
            raise SenderError(f"{row.get('kind')!r} is not a sender row")
    save(rows, timeout)
    return rows


def set_active(workspace, kind, identifier, active, rows=None):
    """Turn a sender or an account on or off. Nothing is ever deleted.

    Same reasoning as `store.drop`: a deactivated sender still owns the
    history of everything they sent, and deleting the row would orphan every
    touch that names them.
    """
    field = "sender_id" if kind == SENDER else "account_id"
    changed = None
    with transaction() as current:
        for i, row in enumerate(current):
            if (row.get("kind") == kind and row.get("workspace") == workspace
                    and row.get(field) == identifier):
                changed = dict(row, active=bool(active))
                current[i] = changed
                break
    if changed is None:
        raise UnknownSender(
            f"no {kind} {identifier!r} in {workspace}")
    return changed


# --------------------------------------------------------- Known conflict
#
# `senders.DEFAULT_DAILY_LIMIT` is 50: an account configured on a campaign
# with no explicit limit is treated as allowing fifty a day. This module
# refuses to do that - `daily_limit` stays None and every reader has to say
# UNKNOWN.
#
# The two are not reconciled here on purpose. `senders.py` is the allocator
# the launch checklist and the push path already depend on, and changing what
# it assumes would change which steps are refused, in a build where nothing
# sends and the change could not be observed end to end. The stricter
# behaviour lives in the new model, the planning screens read the new model,
# and the discrepancy is written down in WEB-APP.md rather than left for
# somebody to find by being surprised at a number.


def digest(workspace, rows=None):
    """A stable fingerprint of a workspace's roster.

    Sender assignment is sticky, and a stored assignment has to be able to say
    what roster it was made against - so that "the pool changed" is a fact a
    screen can state rather than something a reader has to infer.
    """
    rows = load() if rows is None else rows
    material = []
    for person in senders(workspace, rows):
        material.append(("s", person["sender_id"], person["active"]))
    for channel in CHANNELS:
        for row in accounts_for(workspace, channel, rows):
            material.append((channel, row["account_id"], row["sender_id"],
                             row["active"]))
    blob = json.dumps(sorted(str(m) for m in material), separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.senderidentity",
                               description=__doc__)
    p.add_argument("--workspace", required=True)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    data = roster(args.workspace)
    if args.json:
        print(json.dumps(data, indent=2, default=str))
        return 0
    counts = data["counts"]
    print(f"{args.workspace}: {counts['senders']} sender(s), "
          f"{counts['email_accounts']} inbox(es), "
          f"{counts['linkedin_accounts']} LinkedIn profile(s)")
    for person in data["senders"]:
        print(f"  {person['display_name']:<20} "
              f"{person['email_account_count']:>3} inbox(es)  "
              f"{person['linkedin_account_count']:>2} profile(s)")
    for channel, cap in data["capacity"].items():
        known = cap["known_daily_capacity"]
        note = "" if cap["complete"] else (
            f" (+{cap['accounts_with_no_known_limit']} with no known limit)")
        print(f"  {channel} capacity/day: {known}{note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
