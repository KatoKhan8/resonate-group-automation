#!/usr/bin/env python3
"""Exclude OUR OWN identities as recipients. Idempotent, reproducible.

OPERATOR DECISION B3, Zvonimir, 2026-09-30.

THE DEFECT, MEASURED. `eligibility.must_not_contact` refused only the CLIENT's
own domain. Probed on 2026-09-30 against the real gates:

    someone@productive.io        BLOCKED  (client_own_domain)
    beslic.zvonimir@gmail.com    PASSES   <- the operator
    zvonimir@resonategroup.co    PASSES   <- the operator
    ivan@resonategroup.co        PASSES   <- our own agency
    225 of 225 sending addresses PASSES   <- the estate could email itself

The 225 addresses are every mailbox EmailBison sends OUR campaigns from, across
86 lookalike domains. Nothing stopped one of them being enrolled as a prospect.
A self-send is not merely embarrassing: it burns a sending mailbox's reputation
against itself and it puts a real send on a mailbox nobody is reading.

WHAT GOES WHERE, and why it is two registers rather than one.

  DOMAINS  -> config/operator-exclusions.jsonl, via `operatorexclusion`.
              Our agency domain and the 86 sending domains are whole accounts
              that must never be enrolled, which is exactly what that register
              records, one-way hashed, with who/why/when.

  ADDRESSES -> the SAME register, via `operatorexclusion.exclude_address`.
              The operator's personal address is at a public mailbox provider
              our prospects also use, so excluding its DOMAIN would refuse
              every prospect with a Gmail mailbox: the prohibition is about one
              person and has to be keyed on one person.

`agencydnc` was the first choice for the address half and was rejected on
durability: its file is `work/agency-dnc.jsonl`, which is gitignored, so an
exclusion recorded there does not survive a clean clone - and "never contact
the operator" is exactly the state that must. It is written there as well, so
the person-level gate that already reads it also refuses, but the tracked
register is the durable copy.

The only code change alongside this is that `_operator_excluded` now asks the
RECIPIENT's address and its domain as well as the account's, because a record
filed under one company can carry a contact at another.

Sources are read, never typed:
  work/sender-emails.csv   gitignored; 225 real mailboxes
  config/clients/*.yaml    our own agency domain is a constant below

Writes nothing to work/, touches no queue record, calls no provider.

  py -3 scripts/record_self_send_exclusions.py --dry-run
  py -3 scripts/record_self_send_exclusions.py --apply
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import agencydnc, operatorexclusion as oe  # noqa: E402

SENDERS = os.path.join("work", "sender-emails.csv")

BY = "Zvonimir (operator)"
AT = "2026-09-30"
TASK = "canary-B3"
AUTHORITY = ("operator decision B3, Zvonimir, 2026-09-30, in the canary "
             "resume directive: our own identities must never be recipients")

AGENCY_DOMAINS = ("resonategroup.co",)

OPERATOR_ADDRESSES = ("beslic.zvonimir@gmail.com",)

AGENCY_REASON = ("our own agency domain: a Resonate mailbox is never a "
                 "prospect, and an outreach sequence addressed to one is a "
                 "self-send")
SENDER_REASON = ("a mailbox EmailBison sends our own campaigns from: "
                 "enrolling it as a recipient would make the estate email "
                 "itself and burn a sending mailbox against its own "
                 "reputation")
OPERATOR_REASON = ("the operator's own address; suppressed as an internal "
                   "decision rather than by domain, because the domain is a "
                   "public mailbox provider our prospects also use")


def sending_domains(path):
    """Every distinct domain our own sending mailboxes live at."""
    with open(path, encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit(f"{path} is empty; refusing to derive an empty list")
    column = next((c for c in rows[0] if "mail" in c.lower()), None)
    if column is None:
        raise SystemExit(f"{path} has no address column: {list(rows[0])}")
    domains = set()
    for row in rows:
        address = (row.get(column) or "").strip().lower()
        if "@" in address:
            domains.add(address.rsplit("@", 1)[1])
    return sorted(domains)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")
    parser.add_argument("--senders", default=SENDERS)
    args = parser.parse_args(argv)

    domains = [(d, AGENCY_REASON) for d in AGENCY_DOMAINS]
    domains += [(d, SENDER_REASON) for d in sending_domains(args.senders)]

    index = oe.resolve()
    already = [d for d, _ in domains if oe.account_key(d) in index]
    todo = [(d, why) for d, why in domains if oe.account_key(d) not in index]

    # The dot-folded spelling is registered TOO, not just matched at read
    # time. `blocks_address` folds the address it is ASKED about; the stored
    # key is a hash and cannot be re-folded, so both spellings have to be
    # rows or a dotted variant would miss a dotless row and vice versa.
    wanted = []
    for address in OPERATOR_ADDRESSES:
        wanted.append(address)
        local, _, domain = address.partition("@")
        if domain in oe.DOT_FOLDING_DOMAINS and "." in local:
            wanted.append(f"{local.replace('.', '')}@{domain}")
    addr_todo = [a for a in wanted if oe.address_key(a) not in index]
    dnc = agencydnc.load()
    dnc_todo = [a for a in OPERATOR_ADDRESSES
                if agencydnc.fingerprint("email", a) not in dnc]

    print(f"domains to exclude   : {len(todo)} "
          f"({len(already)} already in the register)")
    print(f"addresses to exclude : {len(addr_todo)} "
          f"({len(OPERATOR_ADDRESSES) - len(addr_todo)} already in the "
          "register)")
    print(f"addresses to DNC     : {len(dnc_todo)} "
          f"({len(OPERATOR_ADDRESSES) - len(dnc_todo)} already listed)")

    if args.dry_run:
        for domain, _ in todo[:10]:
            print(f"  would exclude {domain}")
        if len(todo) > 10:
            print(f"  ... and {len(todo) - 10} more")
        for address in addr_todo:
            print(f"  would exclude {address}")
        for address in dnc_todo:
            print(f"  would DNC     {address}")
        return 0

    for domain, why in todo:
        oe.exclude(domain, by=BY, reason=why, authority=AUTHORITY, at=AT,
                   task=TASK)
    for address in addr_todo:
        oe.exclude_address(address, by=BY, reason=OPERATOR_REASON,
                           authority=AUTHORITY, at=AT, task=TASK)
    oe.forget()
    for address in dnc_todo:
        agencydnc.add("email", address, reason=agencydnc.INTERNAL, at=AT)

    print(f"recorded {len(todo)} domain exclusions, {len(addr_todo)} address "
          f"exclusions and {len(dnc_todo)} address suppressions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
