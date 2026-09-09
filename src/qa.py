#!/usr/bin/env python3
"""What is wrong with this campaign, ranked by how much it matters.

## What this is for

The launch checklist in campaigns.py answers "may this go?" - seventeen
conditions, pass or block. This answers a different question: "should it?" A
campaign can pass every safety check and still be worth stopping, because half
the contacts have no personalisation, or the persona mix is wrong, or forty
addresses are held and nobody has looked at them.

So QA is advisory where the checklist is binding, with one exception: a BLOCK
here is still a block. An unresolved placeholder or an unsupported claim is not
a quality opinion, it is a defect, and no average can outvote it.

## The score does not hide the blocker

There is a health score, and it is six named sub-scores rather than one number,
because a single number lets a strong showing in five dimensions bury a
catastrophe in the sixth. Any BLOCK condition sets the overall verdict to BLOCK
regardless of what the arithmetic says. The score is there to tell an operator
where to look, not to make the decision for them.

  python -m src.qa <campaign-id>
"""
import argparse
import json
import sys

from . import (approval, cadence, campaigns, claims, clients, dedupe,
               duplicates,
               eligibility, evidence, lint, linkedin, mx, personalization,
               store, verification)

PASS = "PASS"
WARN = "WARN"
BLOCK = "BLOCK"
VERDICTS = (PASS, WARN, BLOCK)

# Conditions that are defects rather than opinions. Configurable, because a
# client running a template-only campaign may legitimately not care about
# personalisation coverage - but never silently.
DEFAULTS = {
    "block_on": {
        "unresolved_placeholders": True,
        "unsupported_claims": True,
        "duplicate_identity": True,
        "lint_failures": True,
        # Two steps that say the same thing. Each passes lint alone and the
        # sequence is still broken: the defect only exists the second time it
        # arrives, which is why no per-step check can see it.
        "duplicate_email_body": True,
        "stale_approval": True,
        "no_sendable_contacts": True,
    },
    "warn_below": {
        "personalization_coverage": 0.80,
        "verification_coverage": 0.90,
        "contactability_coverage": 0.85,
        "champion_coverage": 0.50,
    },
    "warn_above": {
        "mx_blocked_share": 0.30,
        "held_share": 0.20,
    },
}

DIMENSIONS = ("targeting", "contactability", "personalization", "copy",
              "safety", "cadence")


def settings(config):
    block = ((config or {}).get("qa") or {})
    merged = {k: dict(v) for k, v in DEFAULTS.items()}
    for group in merged:
        for key, value in (block.get(group) or {}).items():
            if key in merged[group]:
                merged[group][key] = value
    return merged


def _share(part, whole):
    return round(part / whole, 3) if whole else None


# --------------------------------------------------------------- the report

def report(campaign, recs=None, config=None):
    """Everything QA knows, computed once. Calls no provider."""
    recs = store.load() if recs is None else recs
    if config is None:
        try:
            config = clients.load(campaign.get("client"))
        except Exception:
            config = {}
    policy = settings(config)
    # The verification policy is a different object from the QA one.
    verify_policy = verification.policy_for(config)

    ids = set(campaign.get("record_ids") or [])
    mine = [r for r in recs if r.get("id") in ids]
    paused_set = cadence.paused_domains(recs)

    targeting = {"records": len(mine), "contacts": 0, "champions": 0,
                 "buyers": 0, "personas": {}, "records_with_no_contact": 0}
    contact_data = {"with_email": 0, "with_linkedin": 0, "sendable": 0,
                    "verification_unknown": 0, "mx_blocked": 0, "held": 0,
                    "mx_dns_failure": 0,
                    # Double verification. `single_verified` is the number a
                    # reviewer should look at first: those contacts are one
                    # call away from sending, which is a different problem
                    # from an address nobody can vouch for.
                    "double_verified": 0, "single_verified": 0,
                    "verification_disagreement": 0, "verification_failed": 0,
                    "reoon_escalations": 0, "verification_blocked": 0,
                    "verification_skipped_by_mx": 0}
    personal = {"strong": 0, "medium": 0, "weak": 0, "none": 0,
                "with_evidence": 0, "recent_signal": 0}
    copy = {"email_steps": 0, "lint_failures": 0, "placeholders": 0,
            "unsupported_claims": 0, "generated": 0, "template": 0,
            "unapproved": 0, "duplicate_bodies": 0, "duplicate_subjects": 0,
            "duplicate_pairs": []}
    safety = {"suppressed": 0, "dropped": 0, "duplicates": 0,
              "possible_duplicates": 0, "collisions": 0, "paused": 0,
              "stale_approval": 0, "mapping_missing": 0}
    cadence_counts = {"complete": 0, "email_only": 0, "linkedin_only": 0,
                      "multichannel": 0, "no_steps": 0, "skipped_email": 0}
    issues = []

    for rec in sorted(mine, key=lambda r: r.get("id") or ""):
        contacts = rec.get("contacts") or []
        if not contacts:
            targeting["records_with_no_contact"] += 1
            issues.append(_issue("warn", "targeting", rec.get("id"), None,
                                 "no contacts found for this company"))
        if rec.get("state") == "dropped":
            safety["dropped"] += 1
        if (rec.get("drop_reason") or "").startswith("suppress"):
            safety["suppressed"] += 1
        if cadence.pause_state(rec):
            safety["paused"] += 1
            issues.append(_issue("critical", "safety", rec.get("id"), None,
                                 "company is paused: nothing may be sent"))

        timeline = cadence.build(rec, config, paused_set=paused_set,
                                 campaign=campaign).get(
            "contacts") or {}

        for contact in contacts:
            targeting["contacts"] += 1
            persona = (contact.get("persona") or "unknown")
            targeting["personas"][persona] = targeting["personas"].get(persona, 0) + 1
            if persona == "champion":
                targeting["champions"] += 1
            elif "buyer" in persona:
                targeting["buyers"] += 1

            if contact.get("email"):
                contact_data["with_email"] += 1
            if linkedin.canonical(contact.get("linkedin")):
                contact_data["with_linkedin"] += 1
            allowed, why = mx.allows_email(contact, config)
            stored = mx.stored_decision(contact)

            # Verification, recomputed. Counted before the sendable branch so
            # the numbers describe the evidence rather than the conclusion.
            if contact.get("email"):
                decision = verification.resolve(contact, verify_policy)
                count = decision["confirmation_count"]
                required = decision["required_confirmations"]
                if decision.get("disagreement"):
                    contact_data["verification_disagreement"] += 1
                    issues.append(_issue(
                        "critical", "contactability", rec.get("id"),
                        contact.get("key"),
                        f"verifiers disagree: {decision['reason']}"))
                if "reoon" in (decision.get("confirmed_by") or []):
                    contact_data["reoon_escalations"] += 1
                if any(e.get("status") in (verification.S_ERROR,
                                           verification.S_TIMEOUT)
                       for e in verification.all_evidence(contact)):
                    contact_data["verification_failed"] += 1
                if decision["state"] == verification.INVALID:
                    contact_data["verification_blocked"] += 1
                elif count >= required:
                    contact_data["double_verified"] += 1
                elif not allowed and count == 0:
                    # Screened out before a verifier was ever asked. Not a
                    # gap: the saving the MX-first ordering exists for.
                    contact_data["verification_skipped_by_mx"] += 1
                else:
                    contact_data["single_verified"] += 1
                    issues.append(_issue(
                        "held", "contactability", rec.get("id"),
                        contact.get("key"),
                        f"{count} of {required} independent verification "
                        f"confirmations"))

            if lint.sendable(contact):
                contact_data["sendable"] += 1
            else:
                state = (contact.get("verification") or {}).get("state")
                if state in (None, "unknown", "accept_all_uncleared", "held"):
                    contact_data["verification_unknown"] += 1
                    issues.append(_issue(
                        "held", "contactability", rec.get("id"),
                        contact.get("key"),
                        f"verification is {state or 'missing'}"))

            if not allowed:
                if stored.get("status") == mx.DNS_FAILURE:
                    contact_data["mx_dns_failure"] += 1
                    issues.append(_issue("held", "contactability", rec.get("id"),
                                         contact.get("key"),
                                         "DNS did not answer for this domain"))
                else:
                    contact_data["mx_blocked"] += 1

            if dedupe.is_duplicate(contact):
                safety["duplicates"] += 1
                issues.append(_issue("critical", "safety", rec.get("id"),
                                     contact.get("key"),
                                     dedupe.duplicate_reason(contact)
                                     or "duplicate identity"))
            if contact.get("possible_duplicate"):
                safety["possible_duplicates"] += 1
                issues.append(_issue("warn", "safety", rec.get("id"),
                                     contact.get("key"),
                                     "possible duplicate: a human decides"))

            decision = contact.get("personalization") or \
                personalization.decide(rec, contact, config)
            quality = decision.get("quality") or "none"
            personal[quality if quality in ("strong", "medium", "weak")
                     else "none"] += 1
            if decision.get("selected_evidence_ids"):
                personal["with_evidence"] += 1
            if decision.get("freshness") in (evidence.HIGH, evidence.MEDIUM):
                personal["recent_signal"] += 1
            if quality in ("weak", "none"):
                issues.append(_issue("warn", "personalization", rec.get("id"),
                                     contact.get("key"),
                                     f"personalisation is {quality}"))

            steps = timeline.get(contact.get("key")) or {}
            channels = {s.get("channel") for s in steps.values()}
            if not steps:
                cadence_counts["no_steps"] += 1
            elif channels == {"email"}:
                cadence_counts["email_only"] += 1
            elif channels == {"linkedin"}:
                cadence_counts["linkedin_only"] += 1
            elif len(channels) > 1:
                cadence_counts["multichannel"] += 1
            if steps and all(s.get("status") != "planned" for s in steps.values()):
                cadence_counts["complete"] += 1

            # `timeline` here is already the per-contact map, which is the
            # shape for_contact expects.
            for finding in duplicates.for_contact(rec, contact.get("key"),
                                                  timeline, config):
                if finding["code"] == duplicates.DUPLICATE_BODY:
                    copy["duplicate_bodies"] += 1
                    copy["duplicate_pairs"].append(finding)
                    issues.append(_issue(
                        "critical", "copy", rec.get("id"), contact.get("key"),
                        f"{' and '.join(finding['steps'])} send the same "
                        f"email: {finding['why']}"))
                else:
                    copy["duplicate_subjects"] += 1
                    issues.append(_issue(
                        "warn", "copy", rec.get("id"), contact.get("key"),
                        f"{' and '.join(finding['steps'])} share a subject "
                        "line, with different bodies"))

            chosen = [e for e in rec.get("research") or []
                      if e.get("evidence_id") in
                      set(decision.get("selected_evidence_ids") or [])]
            for key, step in steps.items():
                if step.get("channel") == "email":
                    copy["email_steps"] += 1
                    failures = lint.check(rec, contact.get("key"), step)
                    if failures:
                        copy["lint_failures"] += 1
                        if any("placeholder" in f for f in failures):
                            copy["placeholders"] += 1
                        issues.append(_issue(
                            "critical", "copy", rec.get("id"),
                            contact.get("key"),
                            f"{key} fails lint: {', '.join(failures)}"))
                    unsupported = claims.verify(step, rec, contact, chosen)
                    if unsupported:
                        copy["unsupported_claims"] += 1
                        issues.append(_issue(
                            "critical", "copy", rec.get("id"),
                            contact.get("key"),
                            f"{key} asserts something unsupported: "
                            f"{unsupported[0]['why']}"))
                if step.get("status") == "skipped":
                    cadence_counts["skipped_email"] += 1
                if step.get("generated"):
                    copy["generated"] += 1
                else:
                    copy["template"] += 1
                if not approval.is_approved(rec, contact.get("key"), key, step):
                    copy["unapproved"] += 1

    safety["collisions"] = len(dedupe.company_collisions(mine))
    fingerprint = campaigns.fingerprint(campaign, recs, config)
    given = campaign.get("approval") or {}
    if given.get("action") == "approve" and given.get("fingerprint") != fingerprint:
        safety["stale_approval"] = 1
        issues.append(_issue("critical", "safety", campaign.get("campaign_id"),
                             None, "the campaign changed since it was approved"))
    for channel, field in (("email", "bison_campaign_id"),
                           ("linkedin", "heyreach_campaign_id")):
        if not campaign.get(field):
            safety["mapping_missing"] += 1

    scores = _scores(targeting, contact_data, personal, copy, safety,
                     cadence_counts)
    verdict, reasons = _verdict(policy, targeting, contact_data, personal, copy,
                               safety, scores)
    return {
        "campaign_id": campaign.get("campaign_id"),
        "client": campaign.get("client"),
        "verdict": verdict,
        "reasons": reasons,
        "scores": scores,
        "targeting": targeting,
        "contact_data": contact_data,
        "personalization": personal,
        "copy": copy,
        "safety": safety,
        "cadence": cadence_counts,
        "issues": queue(issues),
        "fingerprint": fingerprint,
    }


def _issue(severity, dimension, record_id, contact_key, message):
    return {"severity": severity, "dimension": dimension,
            "record_id": record_id, "contact_key": contact_key,
            "message": message}


# The order an operator should work through them.
SEVERITY_ORDER = {"critical": 0, "held": 1, "warn": 2, "info": 3}


def queue(issues):
    """The review queue: critical, then held, then warnings, then the rest.

    Deterministic within a severity so a re-run does not reshuffle the list
    someone is halfway through.
    """
    return sorted(issues or [], key=lambda i: (
        SEVERITY_ORDER.get(i["severity"], 9), i["dimension"],
        i.get("record_id") or "", i.get("contact_key") or "", i["message"]))


def _scores(targeting, contact_data, personal, copy, safety, cadence_counts):
    """Six sub-scores, each interpretable on its own."""
    contacts = targeting["contacts"] or 1
    email_steps = copy["email_steps"] or 1
    return {
        "targeting": _clamp(
            0.5 * _share(targeting["champions"], contacts or 1)
            + 0.3 * min(1.0, targeting["contacts"] / max(1, targeting["records"]))
            + 0.2 * (1.0 - _share(targeting["records_with_no_contact"],
                                  targeting["records"] or 1))),
        "contactability": _clamp(_share(contact_data["sendable"], contacts)),
        "personalization": _clamp(
            _share(personal["strong"] + personal["medium"], contacts)),
        "copy": _clamp(1.0 - _share(copy["lint_failures"]
                                    + copy["unsupported_claims"], email_steps)),
        "safety": _clamp(1.0 - _share(
            safety["duplicates"] + safety["paused"] + safety["stale_approval"],
            contacts)),
        "cadence": _clamp(_share(cadence_counts["multichannel"]
                                 + cadence_counts["email_only"]
                                 + cadence_counts["linkedin_only"], contacts)),
    }


def _clamp(value):
    if value is None:
        return None
    return round(max(0.0, min(1.0, float(value))), 3)


def _verdict(policy, targeting, contact_data, personal, copy, safety, scores):
    """PASS, WARN or BLOCK. A blocker is never averaged away."""
    blocks, warns = [], []
    block_on = policy["block_on"]
    contacts = targeting["contacts"] or 0

    if block_on.get("unresolved_placeholders") and copy["placeholders"]:
        blocks.append(f"{copy['placeholders']} step(s) contain an unresolved "
                      "placeholder")
    if block_on.get("lint_failures") and copy["lint_failures"]:
        blocks.append(f"{copy['lint_failures']} step(s) fail lint")
    if block_on.get("duplicate_email_body") and copy["duplicate_bodies"]:
        blocks.append(f"{copy['duplicate_bodies']} pair(s) of email steps send "
                      "the same message twice")
    # A shared subject line with different bodies is worth seeing and is not
    # worth stopping a campaign for: the body is what arrives.
    if copy["duplicate_subjects"]:
        warns.append(f"{copy['duplicate_subjects']} pair(s) of email steps "
                     "share a subject line")
    if block_on.get("unsupported_claims") and copy["unsupported_claims"]:
        blocks.append(f"{copy['unsupported_claims']} step(s) assert something "
                      "nothing supports")
    if block_on.get("duplicate_identity") and safety["duplicates"]:
        blocks.append(f"{safety['duplicates']} duplicate identity/identities")
    if block_on.get("stale_approval") and safety["stale_approval"]:
        blocks.append("the campaign changed since it was approved")
    if block_on.get("no_sendable_contacts") and contacts and \
            not contact_data["sendable"] and not contact_data["with_linkedin"]:
        blocks.append("no contact in this campaign can be reached on any channel")

    for name, floor in policy["warn_below"].items():
        key = {"personalization_coverage": "personalization",
               "verification_coverage": "contactability",
               "contactability_coverage": "contactability",
               "champion_coverage": "targeting"}.get(name)
        score = scores.get(key)
        if score is not None and floor is not None and score < float(floor):
            warns.append(f"{name} is {score}, below {floor}")

    if contacts:
        mx_share = _share(contact_data["mx_blocked"], contacts) or 0
        ceiling = policy["warn_above"].get("mx_blocked_share")
        if ceiling is not None and mx_share > float(ceiling):
            warns.append(f"{mx_share} of contacts are behind a blocked gateway")
        held_share = _share(contact_data["verification_unknown"], contacts) or 0
        ceiling = policy["warn_above"].get("held_share")
        if ceiling is not None and held_share > float(ceiling):
            warns.append(f"{held_share} of contacts are held on verification")

    if blocks:
        return BLOCK, blocks + warns
    return (WARN, warns) if warns else (PASS, [])


# --------------------------------------------------------------------- CLI

def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.qa")
    p.add_argument("campaign_id")
    p.add_argument("--json", action="store_true")
    p.add_argument("--issues", type=int, default=15)
    a = p.parse_args(argv)

    try:
        campaign = campaigns.require(a.campaign_id)
    except campaigns.NotFound as e:
        print(f"REFUSED: {e}")
        return 2
    result = report(campaign, store.load())

    if a.json:
        print(json.dumps(result, indent=2))
        return 0 if result["verdict"] != BLOCK else 1

    print(f"campaign {result['campaign_id']}  ({result['client']})")
    print(f"  verdict   {result['verdict']}")
    for reason in result["reasons"]:
        print(f"            - {reason}")
    print("\n  health:")
    for name in DIMENSIONS:
        score = result["scores"].get(name)
        bar = "#" * int((score or 0) * 20)
        print(f"    {name:<16} {score if score is not None else 'n/a':<6} {bar}")
    print("\n  counts:")
    for section in ("targeting", "contact_data", "personalization", "copy",
                    "safety", "cadence"):
        interesting = {k: v for k, v in result[section].items() if v}
        if interesting:
            print(f"    {section:<16} {json.dumps(interesting, sort_keys=True)}")
    if result["issues"]:
        print(f"\n  review queue ({len(result['issues'])} item(s), "
              f"most serious first):")
        for issue in result["issues"][:a.issues]:
            where = issue.get("contact_key") or issue.get("record_id") or "-"
            print(f"    {issue['severity']:<9} {where:<20} {issue['message']}")
        if len(result["issues"]) > a.issues:
            print(f"    ... and {len(result['issues']) - a.issues} more")
    print("\n  Advisory, except the blockers. Nothing here sent anything.")
    return 0 if result["verdict"] != BLOCK else 1


if __name__ == "__main__":
    sys.exit(main())
