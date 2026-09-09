#!/usr/bin/env python3
"""What a 5,000-domain campaign would consume, under assumptions you can change.

Every number here is an *operation count* multiplied by an assumption you
supply. Where a real price is known - a ContactOut search credit is one credit -
it is used. Where it is not, the answer is the string UNKNOWN, not a plausible
figure. A cost model that guesses is worse than no cost model, because someone
will budget against it.

Three columns, because the spread is the interesting part:

    LOW       everything goes well: high ContactOut hit rate, little fallback
    EXPECTED  the assumptions as given
    HIGH      the pessimistic end: heavy fallback, more verification

  python -m src.costsim
  python -m src.costsim --domains 5000 --contactout-success 0.6
"""
import argparse
import json
import sys

UNKNOWN = "UNKNOWN"

DEFAULTS = {
    "domains": 5000,
    "contactout_success": 0.70,      # domains where ContactOut finds people
    "contacts_per_company": 2.0,     # SELECTED, not found
    "found_per_company": 6.0,        # what ContactOut returns before selection
    "aiark_fallback": 0.25,          # domains where ContactOut found nobody
    "verification_valid": 0.65,
    "catch_all": 0.20,
    # Under `required_confirmations: 2` the secondary is not a fallback any
    # more: it runs on every address the primary did not settle as invalid.
    # Modelling it at 25% understated the bill by roughly three quarters of a
    # verification per contact.
    "primary_invalid": 0.15,         # settled by ContactOut alone, nothing more
    # How often the escalation is still needed after the secondary answered.
    # High today for one specific reason: Deliverable's response contract has
    # never been read, so `verify()` refuses and every address falls through
    # to Reoon for its second confirmation. Once one real response has been
    # validated this drops back to catch-alls and disagreements.
    "deliverable_unusable": 1.0,
    "reoon_fallback": 0.20,          # catch-alls needing a clearer
    "apify_usage": 0.30,             # domains needing public research
    "llm_calls_per_contact": 2.0,    # the generated steps
    # Share of selected contacts whose email domain sits behind a blocked
    # gateway. MX is free, so every one of these is a paid verification that
    # never happens.
    "mx_blocked_rate": 0.12,
}

# Prices we actually know, per BUILD-SPEC section 5.1 and the live tool schemas.
KNOWN_UNITS = {
    "contactout_people_count": 0,     # free
    "contactout_company_info": 1,     # 1 search credit per company found
    "contactout_decision_makers": 1,  # 1 search + 1 email credit per profile
    "contactout_email_credit": 1,
    "reoon_verify": 1,
    "deliverable_verify": 1,
}


def _spread(value, low=0.7, high=1.4):
    return {"low": round(value * low), "expected": round(value),
            "high": round(value * high)}


def simulate(**overrides):
    a = {**DEFAULTS, **{k: v for k, v in overrides.items() if v is not None}}
    domains = int(a["domains"])

    with_people = domains * a["contactout_success"]
    selected = with_people * a["contacts_per_company"]
    found = with_people * a["found_per_company"]

    # ContactOut: the free count runs on every domain, the company lookup on
    # every domain, and decision-makers only where the count found somebody.
    contactout_search = with_people * a["found_per_company"] + domains
    contactout_email = selected                     # reveal only what we send to
    aiark_domains = domains * a["aiark_fallback"]

    # MX runs before paid verification, so blocked contacts never reach it.
    # `enrich` does this for real now, not just in this model: a domain behind
    # a recognised gateway is screened out before a verifier credit is spent.
    mx_blocked = selected * a["mx_blocked_rate"]
    verifications = selected - mx_blocked

    # The primary runs on everything that survives MX. The secondary runs on
    # everything the primary did not settle as invalid, because two
    # independent confirmations are required and one answer is never two.
    unsettled = verifications * (1 - a["primary_invalid"])
    deliverable = unsettled
    catch_alls = verifications * a["catch_all"]

    # The escalation covers three cases: a catch-all that needs clearing, and
    # - while the Deliverable contract is unread - every address whose second
    # confirmation the secondary could not supply.
    reoon = (catch_alls * a["reoon_fallback"]
             + unsettled * a["deliverable_unusable"])
    reoon = min(reoon, unsettled)

    apify_runs = domains * a["apify_usage"]
    llm_calls = selected * a["llm_calls_per_contact"]

    return {
        "assumptions": a,
        "operations": {
            "domains": domains,
            "contactout_people_count": _spread(domains),
            "contactout_company_info": _spread(domains),
            "contactout_search_credits": _spread(contactout_search),
            "contactout_email_credits": _spread(contactout_email),
            "contacts_found": _spread(found),
            "contacts_selected": _spread(selected),
            "aiark_lookups": _spread(aiark_domains),
            "mx_lookups": _spread(domains),          # domain-level, cached
            "contacts_screened_by_mx": _spread(selected),
            "contacts_blocked_before_verification": _spread(mx_blocked),
            "contacts_linkedin_only": _spread(mx_blocked),
            "verifications": _spread(verifications),
            "deliverable_verifications": _spread(deliverable),
            "reoon_verifications": _spread(reoon),
            "apify_runs": _spread(apify_runs),
            "llm_calls": _spread(llm_calls),
            "email_steps": _spread(selected * 5),
            "linkedin_steps": _spread(selected * 2),
        },
        "known_costs": {
            "contactout_credits": _spread(contactout_search + contactout_email),
            "reoon_credits": _spread(reoon),
            "deliverable_credits": _spread(deliverable),
        },
        "avoided_by_mx": {
            # What screening first actually saves. It is a bigger number than
            # it used to be: a blocked domain now skips *two* verifications
            # rather than one and a bit, because the second confirmation is
            # mandatory for every address that reaches a verifier at all.
            "contactout_verifier_credits": _spread(mx_blocked),
            "deliverable_credits": _spread(mx_blocked
                                           * (1 - a["primary_invalid"])),
            "reoon_credits": _spread(mx_blocked * (1 - a["primary_invalid"])
                                     * a["deliverable_unusable"]),
            "email_steps_not_sent": _spread(mx_blocked * 5),
        },
        "unknown_costs": {
            "aiark": UNKNOWN,
            "apify_compute_units": UNKNOWN,
            "llm_tokens": UNKNOWN,
            "emailbison": UNKNOWN,
            "heyreach": UNKNOWN,
        },
        "notes": [
            "ContactOut people-count is free and runs on every domain, which "
            "is what stops the paid calls on dead domains.",
            "Email credits are spent only on SELECTED contacts, never on every "
            "profile found - that ratio is the single biggest lever here.",
            "AI Ark, Apify, LLM, EmailBison and HeyReach prices are not known "
            "to this system and are reported as UNKNOWN rather than estimated.",
            "MX is a free DNS lookup, cached per domain, and it runs before "
            "paid verification - so a blocked contact costs one lookup that "
            "was already shared with everyone else at that domain.",
        ],
    }


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.costsim")
    p.add_argument("--domains", type=int)
    p.add_argument("--contactout-success", type=float, dest="contactout_success")
    p.add_argument("--contacts-per-company", type=float,
                   dest="contacts_per_company")
    p.add_argument("--aiark-fallback", type=float, dest="aiark_fallback")
    p.add_argument("--catch-all", type=float, dest="catch_all")
    p.add_argument("--apify-usage", type=float, dest="apify_usage")
    p.add_argument("--llm-calls-per-contact", type=float,
                   dest="llm_calls_per_contact")
    p.add_argument("--mx-blocked-rate", type=float, dest="mx_blocked_rate")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    result = simulate(**{k: v for k, v in vars(a).items() if k != "json"})
    if a.json:
        print(json.dumps(result, indent=2))
        return 0

    ops = result["operations"]
    print(f"cost simulation for {ops['domains']} domains\n")
    print(f"{'operation':<32} {'low':>10} {'expected':>10} {'high':>10}")
    for name, value in ops.items():
        if isinstance(value, dict):
            print(f"{name:<32} {value['low']:>10} {value['expected']:>10} "
                  f"{value['high']:>10}")
    print("\nknown credit costs:")
    for name, value in result["known_costs"].items():
        print(f"  {name:<30} {value['low']:>10} {value['expected']:>10} "
              f"{value['high']:>10}")
    print("\nnot known to this system:")
    for name, value in result["unknown_costs"].items():
        print(f"  {name:<30} {value}")
    print()
    for note in result["notes"]:
        print(f"  - {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
