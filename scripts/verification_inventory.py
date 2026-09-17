#!/usr/bin/env python3
"""Every address in the estate, classified by what verification knows about it.

    py -3 scripts/verification_inventory.py            # the table
    py -3 scripts/verification_inventory.py --json out.json

STRICTLY READ-ONLY. No provider call, no credit, no state change. It reports
what a verification run WOULD cost; it never runs one.

## The question this answers

"No email is generated for an unverified address" is a rule in CLAUDE.md, so
the verified pool is the ceiling on every email cohort this system can ever
build. TASK-194 and TASK-203 both measured that ceiling and disagreed with
each other - 143 contacts held by insufficient confirmations, said one; 159
that never entered the waterfall at all, said the other - and the second was
right about the first being wrong for a reason that matters more than either
number: **they were both computed from `work/queue.snapshot.jsonl`**, a
point-in-time copy from 2026-09-15 that has produced a wrong number twice and
was retired on 2026-09-17.

This reads `store.load()`. Live, every time, no snapshot.

## The four answers, and why they are four rather than two

    SENDABLE       policy says this address may be written to
    HELD           evidence exists and policy is not satisfied by it
    NEVER_OFFERED  no evidence at all - nothing ever asked a provider
    NO_ADDRESS     there is nothing to verify

`HELD` and `NEVER_OFFERED` look identical in any summary that counts
"unverified", and they are completely different problems. HELD is a policy
question - a catch-all nobody cleared, a single confirmation where two are
required - and spending more credits on it may buy nothing. NEVER_OFFERED is
inventory that has been paid for once already, at the person-discovery step,
and abandoned before the cheap step that would license writing to it.

`NEVER_OFFERED` then splits again, because "we did not ask" has two causes:

    stage_never_ran   the RECORD has no `email_verification` row in its
                      waterfall: verification never ran over this record
    contact_skipped   the record HAS those rows, so the stage ran and this
                      contact was passed over - `enrich.verification_
                      candidates` caps how many contacts per record are
                      verified by the qualification tier (A:3, B:2, C:1)

Only the second is a selection effect worth arguing with, and the argument is
about the tier caps rather than about a defect.

## Cost

`verification.plan` per contact, summed by `verification.exposure`, which
distinguishes EXPECTED spend from CONDITIONAL exposure. A maximum is not a
forecast and the two are never added together here.

## PII

Counts and hashed contact keys. Never an address.
"""

import argparse
import collections
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import clients, store, verification  # noqa: E402

CLIENT = "productive"

SENDABLE = "SENDABLE"
HELD = "HELD"
NEVER_OFFERED = "NEVER_OFFERED"
NO_ADDRESS = "NO_ADDRESS"

STAGE_NEVER_RAN = "stage_never_ran"
CONTACT_SKIPPED = "contact_skipped"


def h12(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def ran_verification(rec):
    """Did the verification stage run over this RECORD at all?

    Read from the waterfall ledger rather than from any contact, because the
    two answer different questions: a record whose stage ran and whose fifth
    contact was capped out is not a record the stage skipped.
    """
    for row in rec.get("waterfall") or []:
        if isinstance(row, dict) and row.get("stage") == "email_verification":
            return True
    return False


def classify(contact, stage_ran, policy):
    if not contact.get("email"):
        return NO_ADDRESS, None, {}
    evidence = verification.all_evidence(contact)
    decision = verification.decide(evidence, policy)
    if decision.get("sendable") is True:
        return SENDABLE, None, decision
    if evidence:
        return HELD, None, decision
    return (NEVER_OFFERED,
            CONTACT_SKIPPED if stage_ran else STAGE_NEVER_RAN,
            decision)


def build(client=CLIENT):
    config = clients.load(client)
    policy = verification.policy_for(config)
    recs = [r for r in store.load() if r.get("client") == client]

    rows = []
    for rec in recs:
        stage_ran = ran_verification(rec)
        for contact in rec.get("contacts") or []:
            if not isinstance(contact, dict):
                continue
            state, why, decision = classify(contact, stage_ran, policy)
            ops = verification.plan(contact, policy) if contact.get("email") \
                else []
            spend = verification.exposure(ops)
            rows.append({
                "record": h12(rec.get("id")),
                "record_state": rec.get("state"),
                "contact": h12(contact.get("key")),
                "state": state,
                "why": why,
                "decision_state": decision.get("state"),
                "decision_reason": decision.get("reason"),
                # THE CAP IS `max_contacts_to_enrich`, NOT A TIER LETTER.
                # `persona_plan` carries no `tier` key at all - reading one
                # reported `None` for all 159 and would have been published as
                # "tier unknown" rather than as "this script asked for a field
                # that does not exist".
                "cap": ((rec.get("qualification") or {})
                        .get("persona_plan") or {}).get("max_contacts_to_enrich"),
                "cap_reason": ((rec.get("qualification") or {})
                               .get("persona_plan") or {}).get("cap_reason"),
                "contacts_on_record": len([c for c in (rec.get("contacts") or [])
                                           if isinstance(c, dict)]),
                "expected_cost": spend.get("expected"),
                "max_cost": spend.get("maximum"),
                "providers": [o["provider"] for o in ops],
            })
    return {"policy": policy, "records": len(recs), "contacts": len(rows),
            "rows": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--client", default=CLIENT)
    parser.add_argument("--json")
    args = parser.parse_args(argv)

    data = build(args.client)
    rows = data["rows"]
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True, default=str)
        print(f"wrote {args.json}")

    policy = data["policy"]
    print(f"=== POLICY === required_confirmations="
          f"{policy.get('required_confirmations')} primary="
          f"{policy.get('primary')} secondary={policy.get('secondary')} "
          f"catch_all={policy.get('catch_all')}")
    print(f"=== ESTATE === {data['records']} records, "
          f"{data['contacts']} contacts")

    by_state = collections.Counter(r["state"] for r in rows)
    for state in (SENDABLE, HELD, NEVER_OFFERED, NO_ADDRESS):
        print(f"  {state:<14} {by_state.get(state, 0)}")

    never = [r for r in rows if r["state"] == NEVER_OFFERED]
    print(f"\n=== NEVER_OFFERED ({len(never)}) === nothing ever asked a "
          f"provider about these addresses")
    for why, n in collections.Counter(r["why"] for r in never).most_common():
        print(f"  {why:<18} {n}")
    caps = collections.Counter(str(r["cap"]) for r in never)
    print(f"  by max_contacts_to_enrich: {dict(sorted(caps.items()))}")
    over = [r for r in never if isinstance(r["cap"], int)
            and r["contacts_on_record"] > r["cap"]]
    print(f"  on a record holding MORE contacts than its cap: {len(over)} "
          f"of {len(never)}")
    print("  cap reasons: "
          f"{dict(collections.Counter(str(r['cap_reason'])[:40] for r in never).most_common(4))}")
    print("  by record state:       "
          f"{dict(collections.Counter(str(r['record_state']) for r in never))}")
    planned = sum(r["expected_cost"] or 0 for r in never)
    maximum = sum(r["max_cost"] or 0 for r in never)
    print(f"  EXPECTED spend to verify all of them : {planned} credits")
    print(f"  MAXIMUM exposure (conditional legs) : {maximum} credits")
    print("  A maximum is not a forecast and the two are not added.")

    held = [r for r in rows if r["state"] == HELD]
    print(f"\n=== HELD ({len(held)}) === a provider answered and policy is "
          f"not satisfied")
    for reason, n in collections.Counter(
            str(r["decision_reason"])[:58] for r in held).most_common(8):
        print(f"  {n:>4}  {reason}")
    print(f"  EXPECTED spend to push them further  : "
          f"{sum(r['expected_cost'] or 0 for r in held)} credits")

    sendable = [r for r in rows if r["state"] == SENDABLE]
    print(f"\n=== SENDABLE ({len(sendable)}) === the ceiling on every email "
          f"cohort this estate can build today")
    print("  by record state: "
          f"{dict(collections.Counter(str(r['record_state']) for r in sendable))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
