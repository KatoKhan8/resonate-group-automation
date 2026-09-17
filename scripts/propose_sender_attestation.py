#!/usr/bin/env python3
"""Who the provider says owns each inbox, proposed for a human to confirm.

    py -3 scripts/propose_sender_attestation.py
    py -3 scripts/propose_sender_attestation.py --out work/ATTESTATION-PROPOSAL.md

READ-ONLY. Provider GETs and canonical reads. **It attests nothing.** There is
no `--live`, and adding one would be the mistake this file exists to avoid.

## Why a proposal and not a backfill

`SAFE_FOR_PRODUCTIVE = 0`. Not one of 225 productive inboxes has an owner, so
`assignment.eligible_senders` returns `[]` and every campaign falls back to
whatever its canonical row names. That is the single number standing between
campaign 487 and 2,595 emails a day of measured idle capacity.

The obvious fix is the dangerous one. The canonical roster already contains
seven `productive` humans - and **none of them exists at the provider**, which
owns its 225 inboxes under ten entirely different names
(`docs/THE-ROSTER-NAMES-PEOPLE-WHO-DO-NOT-SEND-2026-09-17.md`). Attaching the
257 accounts to those seven would attribute every real send to a person who
does not exist, while the inbox's own signature said otherwise. The emptiness
is protective.

So the attestation cannot be invented, and it does not have to be: the
provider publishes a `name` on every inbox. **That is EVIDENCE, not proof**,
and this script's whole job is to keep those two apart. It produces a proposal
with the evidence attached and the hazards named, for a person to confirm.
`senderownership.attest` then records who confirmed it and when, which is what
makes the resulting send answerable a year later.

## Why the provider's `name` is only evidence

A display name is set by whoever configured the inbox. Three specific hazards
in THIS estate, each of which the report flags rather than resolves:

    NEAR-DUPLICATE   two names differing by one letter, holding 66 inboxes and
                     5. One person typed twice, or two colleagues sharing a
                     surname. No amount of reading the provider settles it,
                     and guessing merges or splits a sending history.
    NO CANONICAL     a provider name matching no `sender` row in the roster.
                     Creating that human is a separate decision from attesting
                     the inbox, and this proposes it rather than doing it.
    UNHEALTHY        an inbox the provider calls `Not connected`. Proposing an
                     owner for a mailbox that cannot send is how a dead inbox
                     re-enters capacity planning wearing a person's name.

## What a confirmation would then unlock, and what it would not

It would make `eligible_senders` non-empty. It would NOT by itself let a
campaign hold more than one inbox: `executionguard._sender_for` refuses any
canonical row naming more than one sender, and replacing that with a
human-identity predicate is separate work
(`docs/SENDER-ATTRIBUTION-DESIGN-2026-09-17.md`).

Both have to land, and EmailBison's documented per-lead stickiness is what
makes the pair safe: once a lead is sent to, the same inbox sends the rest of
its sequence, so several inboxes of ONE attested human cannot produce a
prospect who hears from two people.

## PII

The proposal carries real names, because a person confirming ownership has to
read them. **It is written to `work/`, which is gitignored, and the console
output hashes them.** Never commit the proposal.
"""

import argparse
import collections
import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import senderidentity as si, senderownership as so  # noqa: E402
from src.providers import bison, load_env  # noqa: E402

CLIENT = "productive"
DEFAULT_OUT = os.path.join(ROOT, "work", "ATTESTATION-PROPOSAL-2026-09-17.md")


def h(value):
    text = " ".join(str(value or "").split()).lower()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12] if text else None


def near_duplicates(names):
    """Name pairs one edit apart. Flagged, never merged."""
    out = []
    ordered = sorted(n for n in names if n)
    for i, left in enumerate(ordered):
        for right in ordered[i + 1:]:
            if abs(len(left) - len(right)) > 1:
                continue
            if _one_edit_apart(left, right):
                out.append((left, right))
    return out


def _one_edit_apart(a, b):
    if a == b:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    for i in range(len(long_)):
        if long_[:i] + long_[i + 1:] == short:
            return True
    return False


def build():
    rows = si.load()
    canonical = {str(r.get("provider_account_id")): r for r in rows
                 if r.get("kind") == si.EMAIL_ACCOUNT
                 and r.get("workspace") == CLIENT}
    humans = {r.get("display_name", "").strip().lower(): r for r in rows
              if r.get("kind") == "sender" and r.get("workspace") == CLIENT}
    provider, _meta = bison.sender_emails()

    groups = collections.defaultdict(
        lambda: {"inboxes": [], "connected": 0, "not_connected": 0,
                 "already_attested": 0, "no_canonical_account": 0})
    for row in provider:
        sid = str(row.get("id"))
        name = str(row.get("name") or "").strip()
        entry = groups[name]
        account = canonical.get(sid)
        entry["inboxes"].append({
            "provider_id": sid,
            "account_id": (account or {}).get("account_id"),
            "domain": str(row.get("email") or "").split("@")[-1],
            "status": row.get("status"),
            "health": (account or {}).get("health"),
            "lifetime": row.get("emails_sent_count"),
            "bounced": row.get("bounced_count"),
        })
        if str(row.get("status")) == "Connected":
            entry["connected"] += 1
        else:
            entry["not_connected"] += 1
        if account is None:
            entry["no_canonical_account"] += 1
        elif so.resolve_owner(account, rows):
            entry["already_attested"] += 1

    return {"groups": groups, "canonical_humans": humans,
            "near_duplicates": near_duplicates(
                [n.lower() for n in groups if n])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    load_env(os.path.join(ROOT, "config", ".env"))
    data = build()
    groups, humans = data["groups"], data["canonical_humans"]

    print("=== PROPOSED ATTESTATIONS, BY PROVIDER DISPLAY NAME ===")
    print("  Nothing below is attested. Each row is a CANDIDATE for a person "
          "to confirm.")
    print(f"  {'human (hashed)':<16}{'inbox':>6}{'conn':>6}{'dead':>6}"
          f"{'attested':>9}  canonical row?")
    for name, entry in sorted(groups.items(),
                              key=lambda kv: -len(kv[1]["inboxes"])):
        known = "YES" if name.strip().lower() in humans else "NO - would have "\
            "to be created first, which is its own decision"
        print(f"  {str(h(name)):<16}{len(entry['inboxes']):>6}"
              f"{entry['connected']:>6}{entry['not_connected']:>6}"
              f"{entry['already_attested']:>9}  {known}")

    if data["near_duplicates"]:
        print("\n  NEAR-DUPLICATE NAMES - DO NOT MERGE WITHOUT ASKING:")
        for left, right in data["near_duplicates"]:
            print(f"    {h(left)} ({len(groups.get(left, {}).get('inboxes', []) or groups.get(left.title(), {}).get('inboxes', []) or [])} inboxes)"
                  f"  vs  {h(right)}")
            print(f"      one edit apart. One person typed twice, or two "
                  f"colleagues. Reading the provider does not settle it.")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write("# Proposed sender attestations - FOR CONFIRMATION, NOT "
                     "A RECORD\n\n")
        handle.write("Derived from EmailBison's own `name` field per inbox. "
                     "A display name is EVIDENCE of ownership and not proof: "
                     "it is set by whoever configured the mailbox.\n\n")
        handle.write("**Nothing here is attested.** Confirm or correct each "
                     "group, then `senderownership.attest` records WHO "
                     "confirmed it and WHEN.\n\n")
        handle.write("This file carries real names and lives in `work/`, "
                     "which is gitignored. Do not commit it.\n\n---\n\n")
        for name, entry in sorted(groups.items(),
                                  key=lambda kv: -len(kv[1]["inboxes"])):
            known = name.strip().lower() in humans
            handle.write(f"## {name or '(no name on the inbox)'}\n\n")
            handle.write(f"- inboxes: {len(entry['inboxes'])} "
                         f"({entry['connected']} connected, "
                         f"{entry['not_connected']} NOT connected)\n")
            handle.write(f"- canonical `sender` row in this workspace: "
                         f"{'yes' if known else 'NO - creating this human is '
                            'a separate decision'}\n")
            handle.write(f"- already attested: {entry['already_attested']}\n\n")
            handle.write("| provider id | account | domain | status | health "
                         "| lifetime | bounced |\n|---|---|---|---|---|---|---|\n")
            for box in sorted(entry["inboxes"],
                              key=lambda b: int(b["provider_id"])):
                handle.write(f"| {box['provider_id']} | {box['account_id']} | "
                             f"{box['domain']} | {box['status']} | "
                             f"{box['health']} | {box['lifetime']} | "
                             f"{box['bounced']} |\n")
            handle.write("\n")
    print(f"\nwrote {args.out}  (gitignored - carries real names)")
    print("NOTHING WAS ATTESTED. There is no --live here on purpose.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
