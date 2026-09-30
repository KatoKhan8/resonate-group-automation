#!/usr/bin/env python3
"""Walk the operator's approved source in DETERMINISTIC ORDER and report each
candidate's disposition against the canonical production pipeline.

Operator decision, Zvonimir, 2026-09-30: Rachele is HELD, and the replacement
live canary is "the next deterministic eligible company/contact from
`work/Productive/productive_ICP_safe_to_send (1).csv`". Explicitly: do NOT
manually cherry-pick a convenient prospect.

SO THE ORDER IS THE FILE'S AND THE SKIPS ARE RECORDED. Walking past a
candidate with a stated reason is not cherry-picking; walking past one
silently is. Every row this prints carries QUALIFIED / HELD / NOT_QUALIFIED
and the exact reason, and the counts are reported separately so an easy
account cannot quietly stand in for an attempted one.

READ-ONLY, AND THAT IS THE POINT. Nothing here writes a record, spends a
credit, contacts a provider or generates copy. Generation is the expensive
stage and it runs only for a candidate that has cleared everything cheap
first, in a separate step the operator can see. This script answers "who is
the next candidate" and nothing else.

    py -3 scripts/canary_candidate_walk.py --limit 200
"""
import argparse
import csv
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import (channels, clients, eligibility, generate_campaign, lint,
                 research, store)

SOURCE = os.path.join("work", "Productive",
                      "productive_ICP_safe_to_send (1).csv")

QUALIFIED = "QUALIFIED FOR CANARY"
HELD = "HELD"
NOT_QUALIFIED = "NOT_QUALIFIED"


def _domain_of(email):
    return (email or "").split("@")[-1].strip().lower()


def _discovered_contacts(rec):
    """The record's OWN contacts, in record order.

    NOT THE PERSON NAMED IN THE CSV ROW, and that is deliberate.
    `scripts/build_intake_batch.py` states the design: the purchased list
    supplies ACCOUNTS, and "contacts are discovered per account later by the
    existing enrichment path, which is the only path that verifies an address
    before anybody is contacted".

    So an address is admissible because THIS system discovered and verified
    it, never because a spreadsheet column said `Verified`. An earlier
    version of this walk matched the CSV address against the record and held
    every candidate for "this person has not been discovered" - which was
    true, and the wrong question. The CSV decides the ORDER companies are
    considered in; the estate decides who is written to.
    """
    return list(rec.get("contacts") or ())


def assess(row, recs_by_domain, config):
    """One candidate's disposition. Returns (verdict, reason, detail)."""
    email = (row.get("Work Email") or "").strip()
    domain = _domain_of(email)
    company = (row.get("Company") or "").strip() or domain
    if not email or not domain:
        return NOT_QUALIFIED, "the source row carries no work email", {}

    # THE SOURCE SAYS VERIFIED; THE ESTATE IS THE AUTHORITY. A column in a
    # spreadsheet is a claim about an address, not this system's own verdict.
    rec = recs_by_domain.get(domain)
    if rec is None:
        return NOT_QUALIFIED, ("no canonical record for %s: the company has "
                               "not been through intake, research and ICP"
                               % domain), {}

    state = rec.get("state")
    if state in ("dropped", "do_not_contact"):
        return NOT_QUALIFIED, "record state is %r" % state, {"record": rec["id"]}

    people = _discovered_contacts(rec)
    if not people:
        return HELD, ("no contact has been discovered for this account yet, "
                      "so there is nobody this system has verified"), {
            "record": rec["id"]}

    # THE FIRST CONTACT THIS SYSTEM WILL ACTUALLY WRITE TO. Each is asked in
    # record order and the reason the last one failed is what gets reported,
    # so an account is never held for a person who was never a candidate.
    contact, detail, last = None, {}, "no contact cleared"
    for person in people:
        d = {"record": rec["id"], "contact": person.get("key"),
             "name": person.get("name"), "title": person.get("title")}
        blocked = [r for r in eligibility.must_not_contact(rec, person, config)
                   if r]
        if blocked:
            last = "must_not_contact: %s" % "; ".join(
                str(b) for b in blocked)[:160]
            detail = detail or d
            continue
        # `email_verdict` is "reason first, verdict second" - a TUPLE, and
        # reading it as a dict silently makes every candidate look refused.
        ok, why_not = channels.email_verdict(rec, person, config)
        if not ok:
            last = "email channel refuses: %s" % str(why_not)[:160]
            detail = detail or d
            continue
        contact, detail = person, d
        break
    if contact is None:
        return HELD, last, detail

    # ICP.
    icp = (rec.get("qualification") or {}).get("verdict") or {}
    if icp.get("icp_status") == "rejected":
        return NOT_QUALIFIED, "ICP rejected: %s" % str(
            icp.get("why") or "")[:160], detail

    # EVIDENCE, at the bar the copy stage actually needs. This is the reason
    # `research.NEED_COPY_EVIDENCE` exists: a pack that qualifies an account
    # is not automatically a pack somebody can write eleven messages from.
    need = research.why(rec, for_copy=True)
    if need == research.NEED_COPY_EVIDENCE:
        return HELD, ("insufficient admissible evidence for prospect-facing "
                      "copy (needs %d admitted rows). RESEARCH FIRST, then "
                      "re-evaluate" % research.MIN_COPY_EVIDENCE_ROWS), detail
    if need:
        return HELD, "research needed: %s" % need, detail

    # PERSONA AND OFFER. An offer that selects nothing licenses no copy.
    persona = contact.get("persona") or rec.get("persona")
    if isinstance(persona, dict):
        persona = persona.get("key")
    if not persona:
        return HELD, "no persona on the contact, so no offer selects", detail
    detail["persona"] = persona
    try:
        offers = generate_campaign._select_offers(
            rec.get("segment") or rec.get("client") or "productive", persona)
    except Exception as exc:                                  # noqa: BLE001
        return HELD, "offer selection raised %s" % type(exc).__name__, detail
    if len(offers) != 1:
        return HELD, ("offer selection is not single-valued for persona %r "
                      "(%d selected)" % (persona, len(offers))), detail
    detail["offer"] = next(iter(offers))

    return QUALIFIED, ("cleared exclusion, verification, ICP, evidence, "
                       "persona and offer; generation and the copy gates "
                       "decide next"), detail


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=200,
                    help="how many source rows to walk")
    ap.add_argument("--stop-on-first", action="store_true",
                    help="stop at the first QUALIFIED candidate")
    args = ap.parse_args()

    config = clients.load("productive")
    recs = store.load()
    by_domain = {}
    for r in recs:
        d = (r.get("domain") or "").strip().lower()
        if d and d not in by_domain:
            by_domain[d] = r

    counts = {QUALIFIED: 0, HELD: 0, NOT_QUALIFIED: 0}
    first = None
    with io.open(SOURCE, encoding="utf-8-sig", newline="") as f:
        for i, row in enumerate(csv.DictReader(f), start=1):
            if i > args.limit:
                break
            verdict, reason, detail = assess(row, by_domain, config)
            counts[verdict] += 1
            if verdict == QUALIFIED and first is None:
                first = (i, row, detail, reason)
            print("%4d  %-18s %-30s %s"
                  % (i, verdict, (row.get("Company") or "?")[:28],
                     reason[:110]))
            if first and args.stop_on_first:
                break

    print()
    print("walked %d rows: %d qualified, %d held, %d not qualified"
          % (sum(counts.values()), counts[QUALIFIED], counts[HELD],
             counts[NOT_QUALIFIED]))
    if first:
        i, row, detail, _ = first
        print()
        print("FIRST QUALIFIED CANDIDATE, source row %d:" % i)
        print("  company : %s" % row.get("Company"))
        print("  contact : %s, %s" % (row.get("First Name", "") + " "
                                      + row.get("Last Name", ""),
                                      row.get("Job Title")))
        for k in ("record", "contact", "persona", "offer"):
            print("  %-8s: %s" % (k, detail.get(k)))
    else:
        print("no qualified candidate in the rows walked")


if __name__ == "__main__":
    main()
