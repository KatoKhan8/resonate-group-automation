#!/usr/bin/env python3
"""Which channels this person can be reached on, decided one channel at a time.

The mistake this module exists to prevent is treating reachability as a single
boolean. A prospect behind Proofpoint is not unreachable; they are unreachable
*by email*. A prospect with a verified address and no profile is not a failure;
they are an email-only prospect. Collapsing those into "sendable" throws away
half the addressable market and hides why.

So there are two independent verdicts with their own reasons, and a mode
derived from the pair:

    multichannel   both channels open
    email_only     email open, LinkedIn closed
    linkedin_only  LinkedIn open, email closed
    none           neither, with a reason for each

A contact is never dropped for losing one channel. `none` is held for review,
not deleted, because the reason is usually fixable.

Everything is recomputed from primary state - the verification evidence, the
MX hostnames, the profile URL - rather than read from a stored verdict. A
tampered `email_eligible` on a contact changes nothing about what this
returns.
"""
import argparse
import json

from . import clients, ingest, linkedin, lint, mx, store

MULTICHANNEL = "multichannel"
EMAIL_ONLY = "email_only"
LINKEDIN_ONLY = "linkedin_only"
NONE = "none"
MODES = (MULTICHANNEL, EMAIL_ONLY, LINKEDIN_ONLY, NONE)

EMAIL = "email"
LINKEDIN = "linkedin"

# Stable reason codes. These are read by reporting and by the preview, so they
# are vocabulary rather than prose; the human sentence lives in `explain()`.
NO_ADDRESS = "no_email_address"
NOT_VERIFIED = "verification_not_sendable"
UNSUBSCRIBED = "unsubscribed"
SUPPRESSED = "suppressed"
NO_PROFILE = "no_linkedin_profile"
PROFILE_UNUSABLE = "linkedin_url_not_canonical"
IDENTITY_UNCERTAIN = "identity_uncertain"
DUPLICATE = "duplicate_identity"

# MX supplies its own codes, already in the mx_protection:<vendor> form.
REASONS = (NO_ADDRESS, NOT_VERIFIED, UNSUBSCRIBED, SUPPRESSED, NO_PROFILE,
           PROFILE_UNUSABLE, IDENTITY_UNCERTAIN, DUPLICATE)

HUMAN = {
    NO_ADDRESS: "no email address was ever found for this person",
    NOT_VERIFIED: "the address did not clear verification",
    UNSUBSCRIBED: "this person asked us to stop",
    SUPPRESSED: "this domain or address is on the suppression list",
    NO_PROFILE: "no LinkedIn profile was found",
    PROFILE_UNUSABLE: "the LinkedIn URL is not a usable profile URL",
    IDENTITY_UNCERTAIN: "we cannot say with confidence who this is",
    DUPLICATE: "this person is already in the batch under another record",
}


def explain(reason):
    """A sentence for a human, from a code. Unknown codes are passed through
    rather than swallowed, because a code nobody can explain is a bug."""
    if not reason:
        return ""
    if reason in HUMAN:
        return HUMAN[reason]
    if reason.startswith(mx.PROTECTION_REASON + ":"):
        vendor = reason.split(":", 1)[1]
        name = (mx.ALL_KNOWN.get(vendor) or {}).get("name") or vendor
        return f"{name} filters cold mail for this domain"
    if reason == "mx_" + mx.NO_MX:
        return "the domain publishes no MX record, so it accepts no mail"
    if reason == "mx_" + mx.DNS_FAILURE:
        return "DNS did not answer, so email is held rather than assumed safe"
    return reason


# --------------------------------------------------------------- the checks

def _unsubscribed(rec, contact):
    """Both places an unsubscribe can be recorded. Either one stops us."""
    return bool(contact.get("unsubscribed")
                or (rec.get("suppression") or {}).get("unsubscribed"))


def _suppressed(rec, suppressed=None):
    """The same domain-level check eligibility makes, asked the same way."""
    domain = (rec.get("domain") or "").lower()
    suppressed = ingest.load_suppress() if suppressed is None else suppressed
    if domain and domain in suppressed:
        return True
    return (rec.get("drop_reason") or "").startswith("suppress")


def email_verdict(rec, contact, config=None, suppressed=None):
    """Can we write to this address today? Reason first, verdict second."""
    if _unsubscribed(rec, contact):
        return False, UNSUBSCRIBED
    if _suppressed(rec, suppressed):
        return False, SUPPRESSED
    if not (contact.get("email") or "").strip():
        return False, NO_ADDRESS
    # MX before verification, and in that order for a reason. It is the order
    # the pipeline spends in - a free DNS lookup gates two paid verifier calls
    # - so it is also the order that gives the honest reason. A contact behind
    # Proofpoint whose address was never verified *because* the channel was
    # already closed is not "unverified": reporting it that way sends a
    # reviewer looking for a verification problem that does not exist.
    allowed, _ = mx.allows_email(contact, config)
    if not allowed:
        # Re-derived from the hostnames, not read from the stored verdict.
        fresh = mx.fresh_decision(contact, config) or mx.stored_decision(contact)
        return False, (fresh or {}).get("email_excluded_reason") or "mx_blocked"
    if not lint.sendable(contact):
        return False, NOT_VERIFIED
    return True, None


def linkedin_verdict(rec, contact, config=None, suppressed=None):
    """Can we approach this person on LinkedIn today?"""
    if _unsubscribed(rec, contact):
        return False, UNSUBSCRIBED
    if _suppressed(rec, suppressed):
        return False, SUPPRESSED
    if contact.get("duplicate_of"):
        return False, DUPLICATE
    url = (contact.get("linkedin") or "").strip()
    if not url:
        return False, NO_PROFILE
    if not linkedin.canonical(url):
        # A company page, a search URL or a truncated share link. Sending a
        # connection request to one of those is not a smaller mistake than
        # sending it to nobody.
        return False, PROFILE_UNUSABLE
    return True, None


def evaluate(rec, contact, config=None, suppressed=None):
    """Both verdicts and the mode they imply. Calls nothing and stores nothing."""
    email_ok, email_reason = email_verdict(rec, contact, config, suppressed)
    linkedin_ok, linkedin_reason = linkedin_verdict(rec, contact, config,
                                                    suppressed)
    if email_ok and linkedin_ok:
        mode = MULTICHANNEL
    elif email_ok:
        mode = EMAIL_ONLY
    elif linkedin_ok:
        mode = LINKEDIN_ONLY
    else:
        mode = NONE
    return {
        "email_eligible": email_ok,
        "email_excluded_reason": email_reason,
        "linkedin_eligible": linkedin_ok,
        "linkedin_excluded_reason": linkedin_reason,
        "mode": mode,
        # Held, not dropped. The distinction is the whole point of the module.
        "held": mode == NONE,
        "checked_at": store.now(),
    }


def of(rec, contact, config=None, suppressed=None):
    """The verdict, recomputed. Never the stored one - that is the point."""
    return evaluate(rec, contact, config, suppressed)


def allows(rec, contact, channel, config=None, suppressed=None):
    verdict = evaluate(rec, contact, config, suppressed)
    return bool(verdict.get(f"{channel}_eligible"))


def apply_to_record(rec, config=None, suppressed=None):
    """Store the verdict on each contact, for the preview and reporting.

    Stored for display only. Every gate that matters recomputes, so a stored
    verdict that somebody edits changes what a page shows and nothing else.
    """
    suppressed = ingest.load_suppress() if suppressed is None else suppressed
    out = {}
    for contact in rec.get("contacts") or []:
        verdict = evaluate(rec, contact, config, suppressed)
        contact["channels"] = verdict
        # The two contract fields, promoted so a reader does not have to know
        # where they live.
        contact["email_eligible"] = verdict["email_eligible"]
        contact["email_excluded_reason"] = verdict["email_excluded_reason"]
        out[contact.get("key")] = verdict
    return out


def summarise(recs, config=None, selected_only=True, suppressed=None):
    """Coverage across a batch: the numbers a campaign summary needs."""
    from . import personalization

    suppressed = ingest.load_suppress() if suppressed is None else suppressed
    counts = {mode: 0 for mode in MODES}
    counts.update({"contacts": 0, "email_eligible": 0, "linkedin_eligible": 0,
                   "held": 0})
    reasons = {"email": {}, "linkedin": {}}
    for rec in recs or []:
        contacts = (personalization.selected_contacts(rec, config)
                    if selected_only else (rec.get("contacts") or []))
        for contact in contacts:
            verdict = evaluate(rec, contact, config, suppressed)
            counts["contacts"] += 1
            counts[verdict["mode"]] += 1
            counts["email_eligible"] += int(verdict["email_eligible"])
            counts["linkedin_eligible"] += int(verdict["linkedin_eligible"])
            counts["held"] += int(verdict["held"])
            for channel in ("email", "linkedin"):
                reason = verdict[f"{channel}_excluded_reason"]
                if reason:
                    bucket = reasons[channel]
                    bucket[reason] = bucket.get(reason, 0) + 1
    counts["reasons"] = reasons
    # Coverage as a share of contacts, or None when there is nothing to divide.
    counts["email_coverage"] = (round(counts["email_eligible"]
                                      / counts["contacts"], 3)
                                if counts["contacts"] else None)
    counts["linkedin_coverage"] = (round(counts["linkedin_eligible"]
                                         / counts["contacts"], 3)
                                   if counts["contacts"] else None)
    counts["multichannel_coverage"] = (round(counts[MULTICHANNEL]
                                             / counts["contacts"], 3)
                                       if counts["contacts"] else None)
    return counts


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--client")
    p.add_argument("--all", action="store_true",
                   help="every contact, not only the selected ones")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    recs = store.load()
    if a.client:
        recs = [r for r in recs if r.get("client") == a.client]
    config = {}
    if a.client:
        try:
            config = clients.load(a.client)
        except Exception:
            config = {}
    result = summarise(recs, config, selected_only=not a.all)
    if a.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    print(f"  contacts            {result['contacts']}")
    for mode in MODES:
        print(f"  {mode:<19} {result[mode]}")
    for channel in ("email", "linkedin"):
        for reason, count in sorted(result["reasons"][channel].items()):
            print(f"    {channel} blocked: {reason} x{count}"
                  f"  ({explain(reason)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
