#!/usr/bin/env python3
"""Who owns what, when the provider cannot say.

## The gap this module fills

`senderinventory` rebuilds the sender roster from provider truth and
deliberately sets `sender_id=None` on every row - the provider knows nothing
about which human sends from an inbox or sits behind a LinkedIn profile. That
is the correct default: inventing an owner is worse than leaving one absent.

But it leaves the system with no way to answer "who does this prospect reply
to?" The provider account that sent the message is identifiable; the human
behind it is not. This module bridges that gap with an OPERATOR ATTESTATION:
a person says "I own this account" and the system records it.

## What an attestation is, and what it is not

An attestation is a row in `senders.jsonl` with `kind: "ownership_attestation"`.
It says "in workspace W, on channel C, account A is operated by sender S,
attested by actor X at time T." It is not derived from provider data and it is
not automatic - it is a human statement recorded for audit.

Attestations do not replace `sender_id` on the account row. They sit beside
it. `resolve_owner` checks the account's own `sender_id` first; if that is
empty, it checks attestations. Both paths lead to the same answer; the
attestation is the fallback for accounts the inventory rebuilt without an
owner.

## Why this is not inside senderidentity

`senderidentity` models the canonical objects - humans, accounts, pairings,
teams. An attestation is not a canonical object; it is a REPAIR for a gap
between what the provider can supply and what the system needs. Keeping it
separate means the inventory rebuild stays pure (provider truth only) and the
attestation layer is an operator tool that can be run, audited and reversed
without touching either the provider read or the canonical model.
"""
import json

from . import senderidentity as si, store

ATTESTATION = "ownership_attestation"

UNKNOWN = "UNKNOWN"


def _attestation_path():
    """Same file as the sender roster. Moves with `store.use_directory`."""
    return si.path()


def attest(workspace, channel, account_id, sender_id, by, at=None):
    """Record that a human operates this account. The only write path.

    Refuses when the sender is not a known human in this workspace - attesting
    ownership to a stranger would route a reply to a person who was never part
    of this roster, which is the exact failure mode this module exists to
    prevent.
    """
    if channel not in si.CHANNELS:
        raise ValueError(f"{channel!r} is not a channel")
    if not si.valid_id(account_id):
        raise ValueError(f"{account_id!r} is not a usable account id")
    if not si.valid_id(sender_id):
        raise ValueError(f"{sender_id!r} is not a usable sender id")
    if not (by or "").strip():
        raise ValueError("an attestation needs an actor: who is vouching for this")
    si.require_sender(workspace, sender_id)
    row = {
        "kind": ATTESTATION,
        "workspace": workspace,
        "channel": channel,
        "account_id": account_id,
        "sender_id": sender_id,
        "by": by.strip(),
        "at": at or store.now(),
    }
    with si.transaction() as rows:
        existing = [r for r in rows
                    if r.get("kind") == ATTESTATION
                    and r.get("workspace") == workspace
                    and r.get("channel") == channel
                    and r.get("account_id") == account_id]
        for old in existing:
            rows.remove(old)
        rows.append(row)
    return row


def _attestations(workspace, rows=None):
    """Every attestation for this workspace. No unscoped variant."""
    return [r for r in (si.load() if rows is None else rows)
            if r.get("kind") == ATTESTATION
            and r.get("workspace") == workspace]


def attestation_for(workspace, channel, account_id, rows=None):
    """The attestation for one account on one channel, or None."""
    for row in _attestations(workspace, rows):
        if (row.get("channel") == channel
                and row.get("account_id") == account_id):
            return row
    return None


def resolve_owner(account, rows=None):
    """Who operates this account, or None when nothing is known.

    Two paths, checked in order:
    1. The account's own `sender_id` - set when the account was created with
       a known owner.
    2. An attestation - an operator said "I own this" after the fact.

    Returns None when neither path resolves. The caller decides what None
    means in context; `assignment.resolve_reply_owner` renders it as UNKNOWN.
    A function that returns None is honest about uncertainty; a function that
    returns a sentinel string bakes a rendering decision into the resolution.
    """
    if not account:
        return None
    direct = account.get("sender_id")
    if direct:
        return direct
    workspace = account.get("workspace")
    channel = _channel_of(account)
    account_id = account.get("account_id")
    if not (workspace and channel and account_id):
        return None
    att = attestation_for(workspace, channel, account_id, rows)
    if att:
        return att.get("sender_id")
    return None


def _channel_of(account):
    """Derive the channel from the account's kind. One mapping, not two."""
    kind = account.get("kind")
    if kind == si.EMAIL_ACCOUNT:
        return si.EMAIL
    if kind == si.LINKEDIN_ACCOUNT:
        return si.LINKEDIN
    return None


def dry_run_report(workspace, rows=None):
    """What a backfill WOULD write. Reads the roster, resolves what it can,
    and reports the rest as needing attestation.

    This is the script the task asks for: it does not write anything. It
    produces a report that an operator reads and decides from.
    """
    rows = si.load() if rows is None else rows
    accounts = []
    for channel, kind in ((si.EMAIL, si.EMAIL_ACCOUNT),
                          (si.LINKEDIN, si.LINKEDIN_ACCOUNT)):
        for row in rows:
            if (row.get("kind") == kind
                    and row.get("workspace") == workspace):
                accounts.append((channel, row))

    resolved, needs_attestation = [], []
    for channel, acct in sorted(accounts, key=lambda x: (x[0], x[1].get("account_id", ""))):
        owner = resolve_owner(acct, rows)
        entry = {
            "account_id": acct.get("account_id"),
            "channel": channel,
            "provider_account_id": acct.get("provider_account_id"),
            "address": (acct.get("email_address")
                        or acct.get("profile_url")),
            "sender_id": acct.get("sender_id"),
            "active": acct.get("active"),
            "health": acct.get("health"),
        }
        if owner:
            source = ("sender_id" if acct.get("sender_id")
                      else "attestation")
            resolved.append({**entry, "resolved_owner": owner,
                             "source": source})
        else:
            needs_attestation.append(entry)

    return {
        "workspace": workspace,
        "total_accounts": len(accounts),
        "resolved": len(resolved),
        "needs_attestation": len(needs_attestation),
        "resolved_accounts": resolved,
        "unresolved_accounts": needs_attestation,
    }
