#!/usr/bin/env python3
"""How large a sender pool campaign 487 may safely hold, and why it is that.

    py -3 scripts/sender_pool_census.py
    py -3 scripts/sender_pool_census.py --json

READ-ONLY. Provider GETs and canonical reads. It writes nothing and it
attaches nothing.

## The question

"Thousands a day of safe available capacity exists while a production
campaign remains on two inboxes." The premise needs one correction and the
conclusion needs a number: 487 holds **one** inbox, not two - 3941 was
detached on 2026-09-17 - and the safe pool is not a matter of counting healthy
mailboxes.

Every filter below removes mailboxes for a reason that is written down
somewhere in this repository, and the last one removes almost all of them:

    TOTAL              every inbox the credential can see
    CORRECT_WORKSPACE  the credential is bound to one provider workspace;
                       `bison.sender_emails(expect_workspace=...)` refuses
                       before the first page rather than after the last
    CORRECT_CLIENT     the canonical roster says which tenant an account
                       belongs to. Tenancy is a gate, not a label
    CONNECTED          a mailbox the provider calls `Not connected` reports a
                       daily_limit and cannot send. Fifteen of them did
                       exactly that for eight days
    HEALTHY / WARM     `senderinventory.health_of` maps provider status and
                       warmup into the five-word vocabulary
                       `assignment.usable_health` reads
    ATTESTED           `senderownership.resolve_owner` - which human operates
                       this inbox. NOT a guess from the display name
    HEADROOM           daily_limit minus what the mailbox actually sent in a
                       measured window, not minus what we assume

## Why the answer is one and not two thousand

`executionguard._sender_for` refuses any campaign whose canonical row names
more than one sender for a channel: "a guarded action is attributed to
exactly one". So the ceiling on a campaign's pool is not the estate's health,
it is **the number of senders one campaign may name, which is one**, until
the predicate in `docs/SENDER-ATTRIBUTION-DESIGN-2026-09-17.md` replaces the
arity rule with something stronger.

And the arity rule is not the only thing in the way. `eligible_senders`
returns humans who OWN an active account, and zero productive accounts have
an owner, so the allocator would return an empty pool even with the arity rule
gone. Three facts have to land before a pool larger than one is safe, and this
script reports all three rather than the first one to fail.
"""

import argparse
import collections
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import senderidentity as si, senderownership as so  # noqa: E402
from src.providers import bison, load_env  # noqa: E402

CLIENT = "productive"
EMAIL_CAMPAIGN = 487
UTILISATION = os.path.join(ROOT, "work", "bison-mailbox-utilisation.jsonl")


def h(value):
    text = " ".join(str(value or "").split()).lower()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12] if text else None


def movement():
    """Per-sender sends inside the measured window, or ({}, None)."""
    if not os.path.exists(UTILISATION):
        return {}, None
    samples = []
    with open(UTILISATION, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                row = json.loads(line)
                if row.get("ok"):
                    samples.append(row)
    if len(samples) < 2:
        return {}, None
    first, last = samples[0], samples[-1]
    out = {}
    for ident, now in (last.get("senders") or {}).items():
        was = (first.get("senders") or {}).get(ident) or {}
        a, b = was.get("emails_sent_count"), now.get("emails_sent_count")
        if isinstance(a, int) and isinstance(b, int):
            out[ident] = b - a
    return out, (first["at"], last["at"])


def active_commitments():
    """`{sender_id: [active campaign ids]}`, read per campaign."""
    rows, _total = bison._paged(
        "campaigns",
        lambda page: bison.query(f"{bison.base()}/campaigns",
                                 {"page": page, "per_page": 100}))
    serves = collections.defaultdict(list)
    unreadable = []
    for row in rows or []:
        if str(row.get("status") or "").lower() != "active":
            continue
        cid = row.get("id")
        if not cid:
            continue
        try:
            for sid in bison.campaign_senders(cid) or []:
                serves[str(int(sid))].append(int(cid))
        except Exception as exc:                  # noqa: BLE001 - classified
            unreadable.append({"campaign": int(cid),
                               "error": f"{type(exc).__name__}: {exc}"})
    return serves, unreadable


def census():
    workspace = bison.bound_workspace()
    provider_rows, meta = bison.sender_emails()
    roster = si.load()
    canonical = {str(r.get("provider_account_id")): r for r in roster
                 if r.get("kind") == si.EMAIL_ACCOUNT
                 and r.get("workspace") == CLIENT}
    moved, window = movement()
    serves, unreadable = active_commitments()
    attached = [int(s) for s in (bison.campaign_senders(EMAIL_CAMPAIGN) or [])]

    out = {
        "TOTAL_BISON_INBOXES": len(provider_rows),
        "PROVIDER_META_TOTAL": meta.get("total"),
        "CREDENTIAL_WORKSPACE": workspace,
        "CORRECT_WORKSPACE": len(provider_rows),
        "CORRECT_CLIENT": sum(
            1 for r in provider_rows if str(r.get("id")) in canonical),
        "CONNECTED": 0, "NOT_CONNECTED": 0, "HEALTHY": 0, "WARM": 0,
        "HUMAN_IDENTITY_ATTESTED": 0,
        "CURRENTLY_COMMITTED": 0, "UNCOMMITTED": 0,
        "MEASURED_HEADROOM": 0,
        "MEASUREMENT_WINDOW": window or "UNKNOWN - fewer than two samples",
        "CURRENTLY_ATTACHED_TO_487": attached,
        "UNREADABLE_CAMPAIGNS": len(unreadable),
    }

    per_human = collections.defaultdict(
        lambda: {"inboxes": 0, "attested": 0, "headroom": 0})
    for row in provider_rows:
        sid = str(row.get("id"))
        connected = str(row.get("status")) == "Connected"
        out["CONNECTED" if connected else "NOT_CONNECTED"] += 1
        account = canonical.get(sid)
        health = (account or {}).get("health")
        if connected:
            if health == si.HEALTH_WARMING:
                out["WARM"] += 1
            elif health == si.HEALTH_OK:
                out["HEALTHY"] += 1
        owner = so.resolve_owner(account, roster) if account else None
        if owner:
            out["HUMAN_IDENTITY_ATTESTED"] += 1
        if serves.get(sid):
            out["CURRENTLY_COMMITTED"] += 1
        else:
            out["UNCOMMITTED"] += 1
        limit = int(row.get("daily_limit") or 0)
        used = moved.get(sid)
        if connected and isinstance(used, int):
            out["MEASURED_HEADROOM"] += max(limit - used, 0)
        person = per_human[h(row.get("name")) or "unnamed"]
        person["inboxes"] += 1
        if owner:
            person["attested"] += 1
        if connected and isinstance(used, int):
            person["headroom"] += max(limit - used, 0)

    # SAFE_FOR_PRODUCTIVE is the honest intersection, not the optimistic one.
    # An inbox is only usable by this system when it is connected, healthy,
    # in the right tenant, AND owned by a human the roster can name - because
    # `eligible_senders` walks HUMANS and asks which accounts they own. With
    # no attestations the intersection is empty however healthy the estate is.
    out["SAFE_FOR_PRODUCTIVE"] = sum(
        1 for row in provider_rows
        if str(row.get("status")) == "Connected"
        and canonical.get(str(row.get("id")))
        and (canonical[str(row.get("id"))].get("health")
             in (si.HEALTH_OK, si.HEALTH_WARMING))
        and so.resolve_owner(canonical[str(row.get("id"))], roster))

    # And the ceiling a campaign may actually hold, which is a different
    # question again and is currently the binding one.
    out["MAX_SENDERS_ONE_CAMPAIGN_MAY_NAME"] = 1
    out["MAX_SENDERS_REASON"] = (
        "executionguard._sender_for refuses a canonical row naming more than "
        "one sender for a channel: 'a guarded action is attributed to exactly "
        "one'. Replacing it is docs/SENDER-ATTRIBUTION-DESIGN-2026-09-17.md, "
        "not a config change")
    out["PER_HUMAN"] = {k: v for k, v in sorted(
        per_human.items(), key=lambda kv: -kv[1]["headroom"])}
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    load_env(os.path.join(ROOT, "config", ".env"))
    data = census()
    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True, default=str))
        return 0
    for key, value in data.items():
        if key == "PER_HUMAN":
            continue
        print(f"{key}={value}")
    print("\nPER HUMAN (hashed), by measured headroom:")
    print(f"  {'human':<16}{'inboxes':>9}{'attested':>10}{'headroom':>10}")
    for name, entry in data["PER_HUMAN"].items():
        print(f"  {name:<16}{entry['inboxes']:>9}{entry['attested']:>10}"
              f"{entry['headroom']:>10}")
    allocatable = min(data["SAFE_FOR_PRODUCTIVE"],
                      data["MAX_SENDERS_ONE_CAMPAIGN_MAY_NAME"])
    print(f"\nMAXIMUM SAFE SENDER POOL THE ALLOCATOR COULD PRODUCE: "
          f"{allocatable}")
    print("  the MINIMUM of two independent limits - how many inboxes are "
          "eligible at all")
    print("  (SAFE_FOR_PRODUCTIVE), and how many one campaign may name "
          "(the arity rule).")
    print("  BOTH have to move, and they are different pieces of work.")
    print(f"\nWHAT 487 ACTUALLY HOLDS TODAY: "
          f"{data['CURRENTLY_ATTACHED_TO_487']}")
    print("  A zero above does NOT mean the campaign cannot send. Its sender "
          "comes from the")
    print("  CANONICAL ROW, which names one inbox and is what "
          "`executionguard` checks against")
    print("  the provider - not from `assignment.allocate`, which would "
          "return nothing because")
    print("  no productive inbox has an attested owner. The campaign works "
          "and the allocator")
    print("  is empty, and those are two separate facts that look like one "
          "number.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
