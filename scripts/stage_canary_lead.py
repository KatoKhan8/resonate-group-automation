#!/usr/bin/env python3
"""Stage ONE approved lead into the unbound HeyReach list. Authorized write.

    py -3 scripts/stage_canary_lead.py            # dry run: every check, no write
    py -3 scripts/stage_canary_lead.py --live     # perform the write

WHY THIS FILE EXISTS. Claude's own attempts to perform this write were refused
by Claude Code's auto-mode classifier - a harness control, not a gate, and not
something to work around. The operator authorized the write in writing
(OPERATOR-AUTHORIZATION-2026-09-16.md), so the work is packaged here as one
reviewed command the operator can run.

WHAT IS AUTHORIZED, EXACTLY. Adding an APPROVED Productive lead to an UNBOUND
HeyReach list, for staging. Not activation. Not a campaign add. The operator's
grant said: "Do NOT interpret this as permission to bypass gates or activate
arbitrary campaigns."

THE CANARY. Record and contact are selected by hash rather than spelled out, so
this file carries no prospect PII. TASK-209 chose them: state `verified`
(cleanest - no hold ambiguity), a LinkedIn profile present, li1 through li5 all
approved by `operator-control-arm` with fingerprints, persona and angle
assigned, and no prior history at the provider.

THE WRITE GOES THROUGH `providerwrites.perform`. `liststaging.stage_lead`
routes it there, so the enabled permission, the live unbound-list condition,
the action ledger, the spend ledger, the killswitch and the idempotency check
all apply. It was changed to do that on 2026-09-16; before then it called the
transport directly and the permission would have governed a path nobody used.

THE WIRING MISTAKE THIS FILE GETS RIGHT. `heyreach.add_leads_to_list` takes
INTERNAL rows (`linkedin_url`, `first_name`, `last_name`) and builds the
provider body itself. `stage_lead` separately builds a provider-shaped payload
for the ledger and the readback. Handing the payload's already-shaped `leads`
array to the transport makes it find no `linkedin_url` and refuse BEFORE any
HTTP call - which is what happened on the first attempt, and why provider truth
was unchanged afterwards. The transport below passes the internal row.
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import liststaging, store                      # noqa: E402
from src.providers import heyreach                      # noqa: E402

REC_HASH = "699952d14554"
CONTACT_HASH = "f4698472e36a"

# `held` IS NOT A BLOCKER FOR A LINKEDIN ADD, and TASK-209 proved it rather
# than assumed it: `approve.py` is explicit that `held` is an EMAIL judgment,
# and the LinkedIn staging path does not read record state at all. Five of the
# six fully-approved LinkedIn contacts sit on `held` records, so refusing them
# here would have left exactly one candidate - the one whose profile the
# provider will not accept.
STAGEABLE_STATES = ("verified", "drafted", "held")
LIST_ID = 940797
REQUIRED_APPROVER = "operator-control-arm"
REQUIRED_STEPS = ("li1", "li2", "li3", "li4", "li5")


def h12(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def find_canary(rec_hash=REC_HASH, contact_hash=CONTACT_HASH):
    """The record and contact, by hash. Returns (record, contact) or (None, None)."""
    for rec in store.load():
        if h12(rec["id"]) != rec_hash:
            continue
        for contact in rec.get("contacts") or []:
            if h12(contact.get("key")) == contact_hash:
                return rec, contact
    return None, None


def preflight(rec, contact):
    """Every local check, each one able to refuse. Returns a list of failures.

    These duplicate checks `stage_lead` and `perform` run again. That is
    deliberate: a refusal here costs nothing and names the problem in one line,
    where the same refusal inside `perform` arrives as an exception after a
    provider read.
    """
    problems = []
    if rec.get("state") not in STAGEABLE_STATES:
        problems.append(f"record state is {rec.get('state')!r}")
    if not contact.get("linkedin"):
        problems.append("contact has no LinkedIn profile URL")
    name = str(contact.get("name") or "").strip()
    if len(name.split()) < 2:
        problems.append("contact name does not split into first and last")

    cadence = (rec.get("cadence") or {}).get(contact.get("key")) or {}
    for step in REQUIRED_STEPS:
        approval = (cadence.get(step) or {}).get("approval") or {}
        if approval.get("by") != REQUIRED_APPROVER:
            problems.append(
                f"{step} is approved by {approval.get('by')!r}, not "
                f"{REQUIRED_APPROVER!r}")
        elif not approval.get("fingerprint"):
            problems.append(f"{step} approval carries no fingerprint")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true",
                        help="perform the write; omit for a dry run")
    parser.add_argument("--rec", help="record hash, overriding the default")
    parser.add_argument("--contact", help="contact hash, overriding the default")
    args = parser.parse_args(argv)

    rec_hash = args.rec or REC_HASH
    contact_hash = args.contact or CONTACT_HASH
    rec, contact = find_canary(rec_hash, contact_hash)
    if rec is None:
        print("REFUSED: the canary record/contact was not found in live state.")
        print("  Live state may have moved since TASK-209 selected it.")
        return 2

    problems = preflight(rec, contact)
    # PRINT WHAT WAS LOADED, not the module defaults. This line printed the
    # constants while --rec/--contact loaded a different pair, so a dry run
    # reported one identity and checked another.
    print(f"canary        record {rec_hash} contact {contact_hash}")
    print(f"record state  {rec.get('state')}")
    print(f"approvals     {', '.join(REQUIRED_STEPS)} by {REQUIRED_APPROVER}")
    if problems:
        print("REFUSED before any provider call:")
        for problem in problems:
            print(f"  - {problem}")
        return 2
    print("preflight     PASS")

    # THE LIST, READ LIVE. `assert_list_safe` reads it again inside the write
    # path; this read is so a dry run can report the same fact.
    try:
        list_row = heyreach.list_by_id(LIST_ID)
    except Exception as exc:
        print(f"REFUSED: list {LIST_ID} could not be read "
              f"({type(exc).__name__}). A list whose state is unknown is not "
              f"proven safe.")
        return 2
    bound_to = list_row.get("campaignIds") or []
    print(f"list {LIST_ID}  campaignIds={bound_to}")
    if bound_to:
        print("REFUSED: the list is attached to a campaign. Adding a lead to "
              "a bound list is adding to a campaign, which is the "
              "prospect-facing path and not staging.")
        return 2

    parts = str(contact.get("name") or "").strip().split()
    row = {
        "linkedin_url": str(contact.get("linkedin") or "").strip(),
        "first_name": parts[0],
        "last_name": " ".join(parts[1:]),
        "company": str(rec.get("company") or "").strip(),
        "title": str(contact.get("title") or "").strip(),
    }

    if not args.live:
        print("\nDRY RUN: every check passed and nothing was sent.")
        print("Re-run with --live to perform the authorized staging write.")
        return 0

    def transport(payload):
        # INTERNAL row, not payload["leads"]. See the module docstring.
        return heyreach.add_leads_to_list(payload["listId"], [row])

    try:
        result = liststaging.stage_lead(LIST_ID, row, transport)
    except liststaging.ListStagingRefused as exc:
        print(f"\nREFUSED, nothing was sent: {exc}")
        return 2
    except liststaging.ListStagingUnverified as exc:
        print(f"\nUNVERIFIED: {exc}")
        print("The provider MAY have acted. Read provider truth before doing "
              "anything else, and do NOT retry:")
        print(f"  py -3 -c \"from src.providers import heyreach; "
              f"print(heyreach.list_leads({LIST_ID}))\"")
        return 3

    print(f"\nSTAGED. class={result.get('class')}")
    print(f"provider response: {json.dumps(result.get('response'))[:300]}")
    readback = result.get("readback") or {}
    print("readback: found=%d missing=%d total=%s still_unbound=%s" % (
        len(readback.get("found") or []),
        len(readback.get("missing") or []),
        readback.get("total"), readback.get("still_unbound")))
    if not readback.get("still_unbound"):
        print("WARNING: the list is no longer unbound. The lead is in a list "
              "attached to a campaign. Investigate before staging anything "
              "else.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
