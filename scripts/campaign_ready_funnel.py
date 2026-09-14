#!/usr/bin/env python3
"""Campaign-ready funnel: how many accounts could be campaign-ready, and
what each blocked account is blocked ON.

Reads work/queue.jsonl via src.store and computes the funnel the operator
asked for:

    productive domains
    icp_pass
    + a verified sendable contact
    + a usable company name
    contacts with 5 approved email steps
      EMAIL-READY
    contacts with li1-li5 approved + URL
      LINKEDIN-READY

Plus a per-blocked-account breakdown ranked by closeness to ready, and a
"next best generation run" list: the accounts where one generation pass
would produce the most newly-ready accounts.

Nothing here calls a provider or mutates a record.
"""
import argparse
import collections
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import (approval, cadencelibrary, clients, store, verification)

# -------------------------------------------------------------- blocker codes
#
# Closed vocabulary. Each code is one thing that stopped a contact, and the
# ranking below orders them from "one generation pass away" to "needs a
# person". A contact with two blockers reports the FIRST one that applies
# reading forward through the funnel, because that is the one to fix.

NO_CONTACT = "no_contact"
CONTACT_NOT_VERIFIED = "contact_not_verified"
NO_USABLE_COMPANY = "no_usable_company"
MISSING_EMAIL_STEPS = "missing_email_steps"
MISSING_LI_STEPS = "missing_li_steps"
<<<<<<< HEAD
STEP_FAILS_LINT = "step_fails_repetition"
=======
STEP_FAILS_LINT = "step_fails_lint"
STEP_FAILS_REPETITION = "step_fails_repetition"
>>>>>>> master
STEP_FAILS_CLAIMS = "step_fails_claims"
NOT_SENDABLE = "not_sendable"
NO_LINKEDIN_URL = "no_linkedin_url"
ICP_NOT_QUALIFIED = "icp_not_qualified"
RECORD_DROPPED = "record_dropped"
SUPPRESSED = "suppressed"

# How many email steps the li_heavy cadence has, and which LinkedIn steps
# matter. Read from the library so a cadence change moves the number.
_LI_HEAVY = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
EMAIL_KEYS = tuple(s["key"] for s in _LI_HEAVY if s["channel"] == "email")
LI_KEYS = tuple(s["key"] for s in _LI_HEAVY if s["channel"] == "linkedin")


def _verdict(rec):
    return ((rec.get("qualification") or {}).get("verdict") or {})


def _is_qualified(rec):
    return _verdict(rec).get("icp_status") == "qualified"


def _contacts(rec):
    return list(rec.get("contacts") or [])


def _is_sendable(contact):
    return verification.is_sendable(contact)


def _has_usable_company(rec):
<<<<<<< HEAD
    company = (rec.get("company") or "").strip()
    return bool(company)
=======
    """Ask the engine's own gate, not whether a string is non-empty.

    `cadence.company_name` REFUSES a name that is domain-shaped - "refusing to
    address a prospect by their own hostname" - and that refusal is what keeps
    a real campaign from opening with the recipient's own hostname. A truthiness
    check here counted every record with any company string at all and reported
    54 where the real gate refuses some of them.
    """
    from src import cadence

    try:
        return bool(cadence.company_name(rec))
    except Exception:
        # `CompanyNameUnusable` is the expected one; anything else that stops
        # the name rendering is equally a record we cannot address.
        return False


def _email_step_repetition_failures(rec, contact, contact_key):
    """How many email steps repeat another step in the same sequence."""
    from src import clients, generate

    config = clients.load(rec.get("client") or "productive")
    stored = (rec.get("cadence") or {}).get(contact_key) or {}
    n = 0
    for key, step in stored.items():
        if (step or {}).get("channel") != "email" or not step.get("body"):
            continue
        if generate._quality_of(rec, {"name": contact_key}, stored, key,
                                config):
            n += 1
    return n
>>>>>>> master


def _approved_steps_for_contact(rec, contact_key, keys):
    """How many of the named step keys are approved for this contact."""
    cadence_map = (rec.get("cadence") or {}).get(contact_key) or {}
    n = 0
    for key in keys:
        step = cadence_map.get(key)
        if step and approval.is_approved(rec, contact_key, key, step):
            n += 1
    return n


def _all_email_steps_approved(rec, contact_key):
    return _approved_steps_for_contact(rec, contact_key, EMAIL_KEYS) == len(EMAIL_KEYS)


def _all_li_steps_approved(rec, contact_key):
    return _approved_steps_for_contact(rec, contact_key, LI_KEYS) == len(LI_KEYS)


def _email_step_lint_failures(rec, contact_key):
    """How many approved email steps fail lint. A step that was never
    generated (no body) is not a lint failure - it is a missing step."""
    from src import lint
    cadence_map = (rec.get("cadence") or {}).get(contact_key) or {}
    failures = 0
    for key in EMAIL_KEYS:
        step = cadence_map.get(key)
        if not step or not step.get("body"):
            continue
        if lint.check(rec, contact_key, step):
            failures += 1
    return failures


def _email_step_claims_failures(rec, contact, contact_key):
    """How many approved email steps fail claims."""
    from src import claims
    cadence_map = (rec.get("cadence") or {}).get(contact_key) or {}
    decision = contact.get("personalization") or {}
    ids = set(decision.get("selected_evidence_ids") or [])
    chosen = [e for e in rec.get("research") or []
              if e.get("evidence_id") in ids]
    failures = 0
    for key in EMAIL_KEYS:
        step = cadence_map.get(key)
        if not step or not step.get("body"):
            continue
        unsupported = claims.verify(step, rec, contact, chosen)
        if unsupported:
            failures += 1
    return failures


# -------------------------------------------------------- per-contact blocker

def _contact_blocker(rec, contact, config=None):
    """The FIRST thing blocking this contact, reading forward through the
    funnel. Returns (blocker_code, detail) or None if the contact is ready.

    The order is the funnel order: a contact with no verification AND no
    approved steps reports NOT_VERIFIED, because that is the first gate.
    """
    key = contact.get("key")

    if not _is_sendable(contact):
        if not contact.get("email"):
            return (NOT_SENDABLE, "no email address")
        return (NOT_SENDABLE, "address not verified sendable")

    n_email_approved = _approved_steps_for_contact(rec, key, EMAIL_KEYS)
    n_li_approved = _approved_steps_for_contact(rec, key, LI_KEYS)
    has_linkedin = bool(contact.get("linkedin"))

    email_complete = n_email_approved == len(EMAIL_KEYS)
    li_complete = n_li_approved == len(LI_KEYS)

    if not email_complete and not li_complete:
        missing_email = len(EMAIL_KEYS) - n_email_approved
        missing_li = len(LI_KEYS) - n_li_approved
        if missing_email <= missing_li:
            return (MISSING_EMAIL_STEPS,
                    f"{missing_email} email step(s) not approved "
                    f"({n_email_approved}/{len(EMAIL_KEYS)})")
        return (MISSING_LI_STEPS,
                f"{missing_li} LinkedIn step(s) not approved "
                f"({n_li_approved}/{len(LI_KEYS)})")

    if not email_complete:
        return (MISSING_EMAIL_STEPS,
                f"{len(EMAIL_KEYS) - n_email_approved} email step(s) not "
                f"approved ({n_email_approved}/{len(EMAIL_KEYS)})")

    lint_fails = _email_step_lint_failures(rec, key)
    if lint_fails:
        return (STEP_FAILS_LINT, f"{lint_fails} email step(s) fail lint")

<<<<<<< HEAD
=======
    # THE REPETITION GATE, which is a different question from lint and is the
    # one that actually decides this cohort. The constant was named
    # `step_fails_repetition` and ran lint only, so the funnel reported 13
    # email-ready contacts where applying repetition gives 8. `quality`
    # discounts the company's own name, which is why it is asked through
    # `generate._quality_of` rather than called directly.
    repeats = _email_step_repetition_failures(rec, contact, key)
    if repeats:
        return (STEP_FAILS_REPETITION,
                f"{repeats} email step(s) repeat another step in the sequence")

>>>>>>> master
    claims_fails = _email_step_claims_failures(rec, contact, key)
    if claims_fails:
        return (STEP_FAILS_CLAIMS,
                f"{claims_fails} email step(s) fail claims")

    if not li_complete:
        if not has_linkedin:
            return (NO_LINKEDIN_URL, "no LinkedIn profile URL")
        return (MISSING_LI_STEPS,
                f"{len(LI_KEYS) - n_li_approved} LinkedIn step(s) not "
                f"approved ({n_li_approved}/{len(LI_KEYS)})")

    if li_complete and not has_linkedin:
        return (NO_LINKEDIN_URL, "no LinkedIn profile URL")

    return None


def _record_blocker(rec, config=None):
    """The FIRST thing blocking this record, reading forward through the
    funnel. Returns (blocker_code, detail, contacts_detail_list)."""
    if rec.get("state") == "dropped":
        return (RECORD_DROPPED, rec.get("drop_reason") or "dropped", [])

    if (rec.get("suppression") or {}).get("suppressed"):
        return (SUPPRESSED, "domain suppressed", [])

    if not _is_qualified(rec):
        status = _verdict(rec).get("icp_status") or "not_processed"
        return (ICP_NOT_QUALIFIED, f"icp_status={status}", [])

    if not _has_usable_company(rec):
        return (NO_USABLE_COMPANY, "no company name", [])

    contacts = _contacts(rec)
    if not contacts:
        return (NO_CONTACT, "no contacts found", [])

    contact_details = []
    for c in contacts:
        blocker = _contact_blocker(rec, c, config)
        if blocker is None:
            contact_details.append({
                "contact_key": c.get("key"),
                "status": "ready",
                "blocker": None,
                "detail": None,
            })
        else:
            contact_details.append({
                "contact_key": c.get("key"),
                "status": "blocked",
                "blocker": blocker[0],
                "detail": blocker[1],
            })

    any_ready = any(d["status"] == "ready" for d in contact_details)
    if any_ready:
        return None

    best = min(contact_details, key=lambda d: _blocker_rank(d.get("blocker")))
    return (best["blocker"], f"best contact: {best['contact_key']}",
            contact_details)


# --------------------------------------------------------- blocker ranking
#
# Ordered from "one generation pass away" to "needs structural work".

_BLOCKER_RANK = {
    STEP_FAILS_LINT: 0,
<<<<<<< HEAD
=======
    STEP_FAILS_REPETITION: 0,
>>>>>>> master
    STEP_FAILS_CLAIMS: 1,
    MISSING_EMAIL_STEPS: 2,
    MISSING_LI_STEPS: 3,
    NOT_SENDABLE: 4,
    NO_LINKEDIN_URL: 5,
    NO_CONTACT: 6,
    NO_USABLE_COMPANY: 7,
    CONTACT_NOT_VERIFIED: 8,
    ICP_NOT_QUALIFIED: 9,
    RECORD_DROPPED: 10,
    SUPPRESSED: 11,
}


def _blocker_rank(code):
    return _BLOCKER_RANK.get(code, 99)


# --------------------------------------------------------------- the funnel

def compute_funnel(recs, client=None, config=None):
    """The funnel counts, matching the operator's numbers or explaining why
    not. Returns a dict with funnel stages and per-account blockers."""
    if client:
        recs = [r for r in recs if r.get("client") == client]

    total = len(recs)
    qualified = [r for r in recs if _is_qualified(r)]
    n_qualified = len(qualified)

    with_verified = 0
    for r in qualified:
        if any(_is_sendable(c) for c in _contacts(r)):
            with_verified += 1

    with_company = 0
    for r in qualified:
        if _has_usable_company(r) and any(_is_sendable(c) for c in _contacts(r)):
            with_company += 1

    email_steps_approved = 0
    email_ready = 0
    li_steps_approved = 0
    linkedin_ready = 0

    per_account = []

    for r in qualified:
        contacts = _contacts(r)
        for c in contacts:
            key = c.get("key")
            n_email = _approved_steps_for_contact(r, key, EMAIL_KEYS)
            n_li = _approved_steps_for_contact(r, key, LI_KEYS)

<<<<<<< HEAD
            if n_email == len(EMAIL_KEYS):
                email_steps_approved += 1
                lint_fails = _email_step_lint_failures(r, key)
                claims_fails = _email_step_claims_failures(r, c, key)
                if lint_fails == 0 and claims_fails == 0 and _is_sendable(c):
=======
            # THE COUNTERS ASK `_contact_blocker`, THEY DO NOT RE-DERIVE IT.
            #
            # They used to inline their own version of the gates and had
            # already drifted from the real one: the email counter checked
            # lint and claims but not REPETITION or the usable company name,
            # and the LinkedIn counter checked nothing at all beyond the
            # approvals and a URL. The report said 13 email-ready and 10
            # LinkedIn-ready where `_contact_blocker` says 9 and 8.
            #
            # A second representation of the same decision is how the two
            # drift, and a funnel that overstates readiness is the one number
            # in this script nobody can afford to have wrong.
            ready = (_is_sendable(c) and _has_usable_company(r)
                     and _contact_blocker(r, c, config) is None)

            if n_email == len(EMAIL_KEYS):
                email_steps_approved += 1
                if ready:
>>>>>>> master
                    email_ready += 1

            if n_li == len(LI_KEYS) and c.get("linkedin"):
                li_steps_approved += 1
<<<<<<< HEAD
                linkedin_ready += 1
=======
                if ready:
                    linkedin_ready += 1
>>>>>>> master

    for r in recs:
        result = _record_blocker(r, config)
        if result is not None:
            code, detail, contact_details = result
            per_account.append({
                "record_id": r.get("id"),
                "domain": r.get("domain"),
                "company": r.get("company"),
                "blocker": code,
                "detail": detail,
                "rank": _blocker_rank(code),
                "contacts": contact_details,
            })

    per_account.sort(key=lambda a: a["rank"])

    return {
        "client": client,
        "funnel": {
            "productive_domains": total,
            "icp_pass": n_qualified,
            "verified_sendable_contact": with_verified,
            "usable_company_name": with_company,
            "contacts_with_email_steps_approved": email_steps_approved,
            "email_ready": email_ready,
            "contacts_with_li_steps_approved_and_url": li_steps_approved,
            "linkedin_ready": linkedin_ready,
        },
        "blocked_accounts": per_account,
        "generation_priority": _generation_priority(per_account),
    }


def _generation_priority(blocked_accounts):
    """The 'next best generation run' list: accounts where one generation
    pass would produce the most newly-ready accounts.

    Ranked by: step_fails_lint and step_fails_claims first (a regeneration
    pass is the fix), then missing_email_steps and missing_li_steps (a
    generation pass fills them), then the rest (need more than generation).
    """
<<<<<<< HEAD
    gen_blockers = {STEP_FAILS_LINT, STEP_FAILS_CLAIMS,
=======
    gen_blockers = {STEP_FAILS_LINT, STEP_FAILS_REPETITION,
                    STEP_FAILS_CLAIMS,
>>>>>>> master
                    MISSING_EMAIL_STEPS, MISSING_LI_STEPS}
    gen = []
    non_gen = []
    for acct in blocked_accounts:
        contacts = acct.get("contacts") or []
        gen_contacts = [c for c in contacts
                        if c.get("blocker") in gen_blockers]
        if gen_contacts:
            gen.append({
                "record_id": acct["record_id"],
                "domain": acct["domain"],
                "company": acct["company"],
                "contacts_to_generate": len(gen_contacts),
                "total_contacts": len(contacts),
                "blockers": [c["blocker"] for c in gen_contacts],
            })
        else:
            non_gen.append(acct)

    gen.sort(key=lambda a: -a["contacts_to_generate"])
    return gen


def format_report(result):
    """Human-readable report."""
    f = result["funnel"]
    lines = [
        f"CAMPAIGN-READY FUNNEL  client={result['client'] or 'all'}",
        "",
        f"  {'stage':<45}{'count':>8}",
        f"  {'productive domains':<45}{f['productive_domains']:>8}",
        f"  {'icp_pass':<45}{f['icp_pass']:>8}",
        f"  {'+ verified sendable contact':<45}{f['verified_sendable_contact']:>8}",
        f"  {'+ usable company name':<45}{f['usable_company_name']:>8}",
        f"  {'contacts with 5 approved email steps':<45}{f['contacts_with_email_steps_approved']:>8}",
        f"  {'  EMAIL-READY':<45}{f['email_ready']:>8}",
        f"  {'contacts with li1-li5 approved + URL':<45}{f['contacts_with_li_steps_approved_and_url']:>8}",
        f"  {'  LINKEDIN-READY':<45}{f['linkedin_ready']:>8}",
        "",
    ]

    blocked = result["blocked_accounts"]
    if blocked:
        lines.append(f"BLOCKED ACCOUNTS: {len(blocked)}")
        lines.append("")

        by_blocker = collections.Counter(a["blocker"] for a in blocked)
        lines.append("  Blocker summary:")
        for code, count in sorted(by_blocker.items(),
                                   key=lambda kv: (_blocker_rank(kv[0]), kv[0])):
            lines.append(f"    {code:<35}{count:>6}")
        lines.append("")

        lines.append("  Per account (ranked by closeness to ready):")
        for acct in blocked[:50]:
            lines.append(
                f"    {acct['domain']:<35} {acct['blocker']:<30} "
                f"{acct['detail']}")
            for cd in (acct.get("contacts") or [])[:5]:
                if cd.get("status") == "blocked":
                    lines.append(
                        f"      contact {cd['contact_key']}: "
                        f"{cd['blocker']} - {cd['detail']}")
        if len(blocked) > 50:
            lines.append(f"    ... and {len(blocked) - 50} more")
        lines.append("")

    gen = result["generation_priority"]
    if gen:
        lines.append("NEXT BEST GENERATION RUN:")
        lines.append("")
        lines.append("  Accounts where one generation pass would produce the")
        lines.append("  most newly-ready accounts:")
        lines.append("")
        for entry in gen[:30]:
            lines.append(
                f"    {entry['domain']:<35} "
                f"{entry['contacts_to_generate']}/{entry['total_contacts']} "
                f"contacts need generation")
            lines.append(f"      blockers: {', '.join(entry['blockers'])}")
        if len(gen) > 30:
            lines.append(f"    ... and {len(gen) - 30} more")
        lines.append("")

    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Campaign-ready funnel report")
    p.add_argument("--client", default="productive",
                   help="Client to report on (default: productive)")
    p.add_argument("--json", action="store_true",
                   help="Output as JSON")
    p.add_argument("--queue", default=None,
                   help="Path to queue.jsonl (default: work/queue.jsonl)")
    a = p.parse_args(argv)

    if a.queue:
        os.environ["QUEUE"] = a.queue

    recs = store.load()

    config = None
    if a.client:
        try:
            config = clients.load(a.client)
        except Exception:
            config = None

    result = compute_funnel(recs, client=a.client, config=config)

    if a.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(format_report(result))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
