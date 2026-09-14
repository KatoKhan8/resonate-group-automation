#!/usr/bin/env python3
"""Which humans own this prospect, and why they never quietly change.

## The bug this module exists to remove

`src/senders.py` assigns an account by hashing the contact key over the list of
eligible accounts. That is deterministic for a fixed list, and the docstring
says so proudly - same contact, same inbox, every rerun.

It is only deterministic for a *fixed list*. Add an inbox, disable one, or let
one hit its daily cap and the modulus changes, and a contact silently moves to
a different account. At the account level that is survivable. At the level this
product now models - a *human*, whose name appears in the copy - it is not:

    Day 1   email from Anna
    (an inbox is added)
    Day 5   email from Mark, to the same prospect, mid-thread

So assignment stops being a function and becomes a *fact*. It is computed once,
written onto the contact, and read from there forever after. The hash still
decides the first allocation, because a first allocation should not depend on
who happens to run it - but after that the stored answer wins over anything
recomputation would say.

## What is stored, and where

On the contact, because it belongs to the contact and has to travel with it:

    contact["sender_assignment"] = {
      "email":    {"sender_id": "anna", "account_id": "anna07", ...},
      "linkedin": {"sender_id": "petar", "account_id": "petar-li", ...},
      "at": ..., "by": ..., "roster_digest": ..., "history": [...]
    }

`roster_digest` records which roster the decision was made against, so a screen
can say "the pool changed since this was assigned" as a fact rather than a
guess. It does *not* trigger reassignment: a changed pool is a reason for a
person to look, not a reason for the software to move a prospect between
humans.

## Reassignment is an event, not a recalculation

`reassign` is the only way an existing assignment changes, it records the old
sender, the new one, who did it and why, and it appends to `history` rather
than overwriting. `PLAYBOOK` never deletes a queue record; this never deletes
an assignment.
"""
import argparse
import hashlib
import json

from . import senderidentity as si
from . import senderownership as so
from . import store

EMAIL = si.EMAIL
LINKEDIN = si.LINKEDIN
CHANNELS = si.CHANNELS


class NoEligibleSender(RuntimeError):
    """Nothing in the pool can carry this channel for this contact.

    Reported rather than worked around. A contact with no eligible sender is a
    contact that does not get contacted on that channel, which is a smaller
    problem than one contacted by somebody who should not have.
    """


def _slot(key, count):
    """A stable index. sha1 of the key, not Python's salted hash.

    Same construction `senders._slot` uses, and deliberately the same: two
    allocators that disagree about "the first one" would be two allocators.
    """
    digest = hashlib.sha1(str(key).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % count


def stored(contact):
    return (contact or {}).get("sender_assignment") or {}


def assigned(contact, channel):
    """What this contact is already assigned on a channel, or None."""
    return stored(contact).get(channel) or None


# The health states that mean "do not send from this account". `warming`
# and `unknown` are deliberately not among them: the first is an account
# working up to volume, and the second is the default every real account
# starts in, so refusing it would empty a roster rather than protect it.
REFUSING_HEALTH = (si.HEALTH_PAUSED, si.HEALTH_BLOCKED)


def usable_health(account):
    """Is this account's health something other than a refusal?"""
    return str((account or {}).get("health") or "") not in REFUSING_HEALTH


def eligible_senders(workspace, channel, rows=None, config=None,
                     campaign=None):
    """Humans who can carry this channel, in a stable order.

    A human is eligible when they are active and own at least one active
    account on the channel whose health is not a refusal. Owning an inactive
    inbox is not eligibility, and a human with no inbox at all is not an
    email sender however active they are.

    `health` is consulted here because nothing consulted it anywhere.
    `senderidentity` defines five states, two of which say plainly that an
    account must not be used, and neither this module nor `push` mentioned
    the field - so an inbox somebody had marked `paused` was allocated
    prospects and written into a payload exactly like a healthy one. The
    state was recorded correctly and read by nobody, which is this
    repository's recurring defect, and here it is a deliverability harm:
    an inbox is usually paused because it is already in trouble.
    """
    rows = si.load() if rows is None else rows
    out = []
    all_accounts = si.accounts_for(workspace, channel, rows)
    for person in si.senders(workspace, rows, active_only=True):
        sid = person["sender_id"]
        mine = []
        for a in all_accounts:
            if not a.get("active") or not usable_health(a):
                continue
            if a.get("sender_id") == sid:
                mine.append(a)
            elif not a.get("sender_id"):
                owner = so.resolve_owner(a, rows)
                if owner == sid:
                    mine.append(a)
        if mine:
            out.append({"sender": person, "accounts": mine})
    return out


def _pick_account(accounts, contact_key, channel):
    """Which of one human's accounts. Hash again, over their accounts only.

    Spreading a human's own prospects across their own inboxes is the thing
    the account layer is for, and it is safe to do here because every one of
    these inboxes is the same person - the name in the copy does not change.
    """
    ordered = sorted(accounts, key=lambda a: a["account_id"])
    return ordered[_slot(f"{contact_key}:{channel}", len(ordered))]


def allocate(workspace, contact_key, channel, rows=None, config=None,
             campaign=None, prefer_sender_id=None):
    """The first allocation for one contact on one channel. Stores nothing.

    `prefer_sender_id` is how a pairing gets honoured: the LinkedIn side asks
    for the human the email side is paired with, and falls back to the pool
    only when that human cannot carry the channel.
    """
    rows = si.load() if rows is None else rows
    pool = eligible_senders(workspace, channel, rows, config, campaign)
    if not pool:
        raise NoEligibleSender(
            f"no active {channel} sender in {workspace} owns an active "
            f"{channel} account")

    chosen = None
    if prefer_sender_id:
        for entry in pool:
            if entry["sender"]["sender_id"] == prefer_sender_id:
                chosen = entry
                break
    if chosen is None:
        ordered = sorted(pool, key=lambda e: e["sender"]["sender_id"])
        chosen = ordered[_slot(f"{contact_key}:{channel}", len(ordered))]

    account = _pick_account(chosen["accounts"], contact_key, channel)
    return {
        "sender_id": chosen["sender"]["sender_id"],
        "display_name": chosen["sender"].get("display_name"),
        "title": chosen["sender"].get("title"),
        "team": chosen["sender"].get("team"),
        "account_id": account["account_id"],
        "provider": account.get("provider"),
        "provider_account_id": account.get("provider_account_id"),
        "address": account.get("email_address") or account.get("profile_url"),
        "workspace": workspace,
        "channel": channel,
        "via": "pairing" if (prefer_sender_id
                             and chosen["sender"]["sender_id"]
                             == prefer_sender_id) else "pool",
    }


def ensure(rec, contact, workspace, channels=None, rows=None, config=None,
           campaign=None, by="system", at=None):
    """Assign what is not assigned yet, and leave what is alone.

    Idempotent by construction: a channel with a stored assignment is skipped
    entirely, so calling this on every cadence build is safe and is what makes
    the assignment sticky in practice rather than only in principle.

    Returns the assignment block. Mutates the contact; the caller saves.
    """
    rows = si.load() if rows is None else rows
    channels = channels or CHANNELS
    contact_key = contact.get("key")
    block = contact.setdefault("sender_assignment", {})

    # Email first, always. The LinkedIn side may want to be paired with the
    # email human, and a pairing cannot be honoured before there is somebody
    # to pair with.
    ordered = [c for c in (EMAIL, LINKEDIN) if c in channels]
    for channel in ordered:
        if block.get(channel):
            continue
        prefer = None
        if channel == LINKEDIN and block.get(EMAIL):
            pair = si.pairing_for(
                workspace, block[EMAIL]["sender_id"],
                campaign_id=(campaign or {}).get("campaign_id"), rows=rows)
            if pair:
                prefer = pair.get("linkedin_sender_id")
        try:
            block[channel] = allocate(workspace, contact_key, channel, rows,
                                      config, campaign, prefer)
        except NoEligibleSender as e:
            # Recorded, not raised. A contact with no LinkedIn sender is an
            # email-only contact, which the channel model already understands;
            # refusing the whole assignment would take the email away too.
            block.setdefault("unavailable", {})[channel] = str(e)
            continue

    if block and "at" not in block:
        block["at"] = at or store.now()
        block["by"] = by
    block["roster_digest"] = si.digest(workspace, rows)
    return block


def reassign(rec, contact, workspace, channel, sender_id, by, reason,
             rows=None, config=None, campaign=None, at=None):
    """Move a contact to a different human, on the record, with the reason.

    The only way a stored assignment changes. Everything about the shape of
    this function is about making the change answerable a year later: the old
    sender is kept, the new one is named, the actor is named, the reason is
    required rather than optional, and the previous assignment is appended to
    `history` rather than overwritten.
    """
    if channel not in CHANNELS:
        raise ValueError(f"{channel!r} is not a channel")
    if not (reason or "").strip():
        raise ValueError(
            "a reassignment needs a reason: moving a prospect between humans "
            "mid-cadence is exactly the change somebody will ask about")
    rows = si.load() if rows is None else rows
    si.require_sender(workspace, sender_id, rows)

    block = contact.setdefault("sender_assignment", {})
    previous = block.get(channel)
    fresh = allocate(workspace, contact.get("key"), channel, rows, config,
                     campaign, prefer_sender_id=sender_id)
    if fresh["sender_id"] != sender_id:
        raise NoEligibleSender(
            f"{sender_id} cannot carry {channel} for this contact: they own "
            f"no active {channel} account in {workspace}")

    fresh["via"] = "reassigned"
    block[channel] = fresh
    entry = {
        "at": at or store.now(),
        "channel": channel,
        "by": by,
        "reason": str(reason).strip()[:300],
        "from": {"sender_id": (previous or {}).get("sender_id"),
                 "account_id": (previous or {}).get("account_id")},
        "to": {"sender_id": fresh["sender_id"],
               "account_id": fresh["account_id"]},
    }
    block.setdefault("history", []).append(entry)
    block["roster_digest"] = si.digest(workspace, rows)
    store.log(rec, "sender_reassigned",
              f"{contact.get('key')} {channel}: "
              f"{(previous or {}).get('sender_id')} -> {fresh['sender_id']}")
    return entry


def pair_of(contact):
    """The two humans on this contact, as a comparable key.

    Used by reporting to group "Anna email + Petar LinkedIn" as one thing.
    """
    block = stored(contact)
    email = (block.get(EMAIL) or {}).get("sender_id")
    linkedin = (block.get(LINKEDIN) or {}).get("sender_id")
    if not email and not linkedin:
        return None
    return f"{email or 'none'}+{linkedin or 'none'}"


def describe(contact):
    """A flat summary for a screen. Never raises on a half-assigned contact."""
    block = stored(contact)
    out = {"pair": pair_of(contact), "at": block.get("at"),
           "by": block.get("by"), "roster_digest": block.get("roster_digest"),
           "history": list(block.get("history") or []),
           "unavailable": dict(block.get("unavailable") or {})}
    for channel in CHANNELS:
        row = block.get(channel) or {}
        out[channel] = {
            "sender_id": row.get("sender_id"),
            "display_name": row.get("display_name"),
            "account_id": row.get("account_id"),
            "provider": row.get("provider"),
            "address": row.get("address"),
            "via": row.get("via"),
        } if row else None
    return out


def is_stale(contact, workspace, rows=None):
    """Was this assignment made against a roster that has since changed?

    A fact for a screen, never a trigger. A changed pool is a reason for a
    person to look at an assignment, not a reason for the software to move a
    prospect from one human to another behind their back.
    """
    block = stored(contact)
    if not block.get("roster_digest"):
        return False
    return block["roster_digest"] != si.digest(workspace, rows)


def summarise(recs, workspace, rows=None):
    """Who is carrying how much, across a whole workspace."""
    rows = si.load() if rows is None else rows
    by_sender, by_pair, unassigned = {}, {}, {EMAIL: 0, LINKEDIN: 0}
    contacts = 0
    for rec in recs:
        for contact in rec.get("contacts") or []:
            if not contact.get("selected"):
                continue
            contacts += 1
            block = stored(contact)
            for channel in CHANNELS:
                row = block.get(channel)
                if not row:
                    unassigned[channel] += 1
                    continue
                bucket = by_sender.setdefault(
                    (channel, row["sender_id"]),
                    {"channel": channel, "sender_id": row["sender_id"],
                     "display_name": row.get("display_name"),
                     "contacts": 0, "accounts": set()})
                bucket["contacts"] += 1
                bucket["accounts"].add(row.get("account_id"))
            pair = pair_of(contact)
            if pair:
                by_pair[pair] = by_pair.get(pair, 0) + 1
    rows_out = []
    for bucket in by_sender.values():
        rows_out.append({**bucket, "accounts": sorted(bucket["accounts"]),
                         "account_count": len(bucket["accounts"])})
    rows_out.sort(key=lambda r: (r["channel"], -r["contacts"], r["sender_id"]))
    ordered = dict(sorted(by_pair.items(), key=lambda kv: (-kv[1], kv[0])))
    return {
        "contacts": contacts,
        "by_sender": rows_out,
        "by_pair": ordered,
        # `mara+ines` is the grouping key and stays one. It is not what to
        # print under a note that says a pair is "how a prospect experiences
        # this: one human in their inbox, one on LinkedIn" - a prospect does
        # not experience a sender id.
        "pair_labels": {key: _pair_label(key, workspace, rows)
                        for key in ordered},
        "unassigned": unassigned,
    }


def _pair_label(key, workspace, rows):
    """"Mara Kovac + Ines Ferreira", from an `email+linkedin` key."""
    email, _, linkedin = str(key).partition("+")

    def named(sender_id):
        if not sender_id or sender_id == "none":
            return "nobody"
        entry = si.sender(workspace, sender_id, rows) or {}
        return entry.get("display_name") or sender_id

    return f"{named(email)} + {named(linkedin)}"


def resolve_reply_owner(workspace, channel, provider_account_id, rows=None):
    """Who did this prospect talk to? From a provider account to a human.

    The reply routing chain: a reply arrives with a provider account id (the
    inbox or LinkedIn profile the prospect is replying to). This function
    resolves that back to the human whose name was on the message.

    Returns a dict with `sender_id`, `display_name`, `account_id` and
    `source` (either "sender_id" or "attestation") when the owner is known.
    Returns a dict with `sender_id: UNKNOWN` and a reason when it is not.
    Never returns None - a caller that gets a result can always check
    `sender_id` to see whether routing is possible.
    """
    rows = si.load() if rows is None else rows
    if not provider_account_id:
        return {"sender_id": so.UNKNOWN,
                "reason": "no provider account id was supplied"}
    acct = si.by_provider_account(workspace, channel, provider_account_id,
                                  rows)
    if acct is None:
        return {"sender_id": so.UNKNOWN,
                "reason": (f"no {channel} account with provider id "
                           f"{provider_account_id!r} in {workspace}")}
    owner = so.resolve_owner(acct, rows)
    if owner is None:
        return {"sender_id": so.UNKNOWN,
                "account_id": acct.get("account_id"),
                "reason": ("account has no sender_id and no attestation "
                           "records an owner")}
    person = si.sender(workspace, owner, rows)
    return {
        "sender_id": owner,
        "display_name": (person or {}).get("display_name") or owner,
        "account_id": acct.get("account_id"),
        "source": ("sender_id" if acct.get("sender_id")
                   else "attestation"),
    }


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.assignment",
                               description=__doc__)
    p.add_argument("--workspace", required=True)
    p.add_argument("--client")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    recs = [r for r in store.load()
            if not args.client or r.get("client") == args.client]
    data = summarise(recs, args.workspace)
    if args.json:
        print(json.dumps(data, indent=2, default=str))
        return 0
    print(f"{data['contacts']} selected contact(s)")
    for row in data["by_sender"]:
        print(f"  {row['channel']:<9} {row['display_name'] or row['sender_id']:<18} "
              f"{row['contacts']:>4} contact(s) across "
              f"{row['account_count']} account(s)")
    for pair, count in data["by_pair"].items():
        print(f"  pair {pair:<28} {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
