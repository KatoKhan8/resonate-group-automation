#!/usr/bin/env python3
"""TASK-194: Trace every qualified record through the funnel.

Read-only analysis of the queue snapshot. No provider writes, no paid calls,
no state changes.
"""
import hashlib
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

SNAPSHOT = os.path.join(ROOT, "work", "queue.snapshot.jsonl")


def load_snapshot():
    recs = []
    with open(SNAPSHOT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def h(value):
    """Hash any identifier for safe reporting."""
    return hashlib.sha256(str(value).encode()).hexdigest()[:12]


def verdict_of(rec):
    return ((rec.get("qualification") or {}).get("verdict") or {})


def is_qualified(rec):
    return verdict_of(rec).get("icp_status") == "qualified"


def contacts_of(rec):
    return list(rec.get("contacts") or [])


def excluded_of(rec):
    return list(rec.get("excluded") or [])


def confirmations(contact):
    return int(((contact.get("verification") or {}).get("confirmation_count") or 0))


def has_email(contact):
    return bool(contact.get("email"))


def has_linkedin(contact):
    return bool(contact.get("linkedin"))


def verification_state(contact):
    v = contact.get("verification") or {}
    return v.get("state") or "unknown"


def verification_evidence(contact):
    v = contact.get("verification") or {}
    return v.get("evidence") or []


def check_mx(contact):
    mx = contact.get("mx") or {}
    return mx.get("status") or "unknown"


def check_reoon(contact):
    return contact.get("reoon") or {}


def log_steps(rec):
    return rec.get("log") or []


def run_eligibility_full(rec, config=None):
    """Run eligibility.decide for every step of every contact."""
    from src import eligibility, clients

    if config is None:
        try:
            config = clients.load(rec.get("client"))
        except Exception:
            config = {}

    results = []
    contacts = contacts_of(rec)
    cadence = rec.get("cadence") or {}

    for contact in contacts:
        contact_key = contact.get("key")
        steps = cadence.get(contact_key) or {}
        for step_key, step in steps.items():
            try:
                decision = eligibility.decide(
                    rec, contact, step_key,
                    channel=step.get("channel"),
                    step=step,
                    config=config
                )
                results.append({
                    "contact_key": contact_key,
                    "step_key": step_key,
                    "verdict": decision.get("verdict"),
                    "reasons": decision.get("reasons", []),
                    "reason": decision.get("reason"),
                })
            except Exception as e:
                results.append({
                    "contact_key": contact_key,
                    "step_key": step_key,
                    "verdict": "error",
                    "reasons": [f"error: {e}"],
                    "reason": f"error: {e}",
                })
    return results


def check_qualify_state(rec):
    from src import qualify
    return qualify.state_of(rec)


def classify_verification_failure(contact):
    """Classify WHY a contact is not verified."""
    email = contact.get("email")
    evidence = verification_evidence(contact)
    reoon = check_reoon(contact)
    mx_status = check_mx(contact)
    v_state = verification_state(contact)
    conf = confirmations(contact)

    if not email:
        return "no_email_found"

    providers = {}
    for ev in evidence:
        providers[ev.get("provider")] = ev.get("status")

    if mx_status == "known_blocked":
        return "mx_blocked"

    is_catch_all = reoon.get("is_catch_all", False)
    for ev in evidence:
        if ev.get("catch_all") is True:
            is_catch_all = True

    if is_catch_all and v_state in ("accept_all_uncleared", "held", "unknown"):
        return "catch_all_uncleared"

    statuses = [s for s in providers.values() if s]
    if "valid" in statuses and "invalid" in statuses:
        return "verifiers_disagree"

    if conf < 2:
        co = providers.get("contactout")
        dl = providers.get("deliverable")
        re = providers.get("reoon")
        if co == "valid" and dl in ("error", None, "unknown", "timeout"):
            if re in ("valid",):
                return "confirmed_by_contactout_reoon"
            return "insufficient_confirmations_primary_only"
        if co in ("error", "unknown", None) and re == "valid":
            return "insufficient_confirmations_reoon_only"
        if co == "accept_all" and re in ("valid",) and reoon.get("is_safe_to_send"):
            return "catch_all_cleared_by_reoon"
        return "insufficient_confirmations"

    if v_state in ("held", "unknown"):
        return "verification_held"
    if v_state == "invalid":
        return "verification_invalid"
    if v_state == "accept_all_uncleared":
        return "catch_all_uncleared"

    return f"other:{v_state}"


def classify_recoverable(reason):
    """Classify a refusal reason as recoverable or not."""
    if reason in ("held:draft_not_approved",):
        return "recoverable", "human_approval"
    if reason in ("held:approval_stale",):
        return "recoverable", "regenerate_and_approve"
    if reason in ("held:evidence_aged_out",):
        return "recoverable", "regenerate_draft"
    if reason in ("held:verification_unknown",):
        return "recoverable", "reverify_address"
    if reason in ("held:insufficient_verification_confirmations",):
        return "recoverable", "one_more_verification_call"
    if reason in ("held:dns_failure",):
        return "recoverable", "retry_dns"
    if reason in ("held:step_not_due",):
        return "recoverable", "time_will_resolve"
    if reason in ("held:awaiting_dependency",):
        return "recoverable", "earlier_step_must_complete"
    if reason in ("held:account_fatigue",):
        return "recoverable", "time_will_resolve"
    if reason in ("held:channel_separation",):
        return "recoverable", "time_will_resolve"
    if reason in ("held:campaign_not_approved",):
        return "recoverable", "campaign_approval"
    if reason in ("held:campaign_approval_stale",):
        return "recoverable", "re_approve_campaign"
    if reason in ("held:provider_mapping_missing",):
        return "recoverable", "create_provider_campaign"
    if reason in ("blocked:lint_failed",) or (isinstance(reason, str) and reason.startswith("blocked:lint:")):
        return "recoverable", "regenerate_copy"
    if reason in ("blocked:unsupported_claim",):
        return "recoverable", "regenerate_copy"
    if reason in ("blocked:review_required",):
        return "recoverable", "human_review"
    if reason in ("blocked:campaign_frozen",):
        return "recoverable", "unfreeze_campaign"
    if reason in ("blocked:record_in_two_campaigns",):
        return "recoverable", "resolve_campaign_conflict"

    # Not recoverable
    if reason.startswith("blocked:"):
        return "not_recoverable", reason.replace("blocked:", "")
    if reason.startswith("skipped:"):
        return "not_recoverable", reason.replace("skipped:", "")
    return "unknown", reason


def main():
    print("TASK-194 FUNNEL ANALYSIS")
    print("=" * 70)
    print(f"Snapshot: {SNAPSHOT}")

    recs = load_snapshot()
    print(f"Total records: {len(recs)}")

    qualified = [r for r in recs if is_qualified(r)]
    print(f"Qualified records: {len(qualified)}")

    # ---- STATE DISTRIBUTION ----
    print("\n--- State distribution of qualified records ---")
    states = {}
    for rec in qualified:
        s = rec.get("state") or "none"
        states[s] = states.get(s, 0) + 1
    for s, c in sorted(states.items(), key=lambda x: -x[1]):
        print(f"  {s}: {c}")

    # ---- QUALIFY STATE ----
    print("\n--- qualify.state_of distribution ---")
    qs = {}
    for rec in qualified:
        s = check_qualify_state(rec)
        qs[s] = qs.get(s, 0) + 1
    for s, c in sorted(qs.items(), key=lambda x: -x[1]):
        print(f"  {s}: {c}")

    # ---- CONTACT-LEVEL FUNNEL ----
    print("\n--- Contact-level funnel ---")
    total_contacts = 0
    contacts_with_email = 0
    contacts_with_linkedin = 0
    contacts_verified = 0
    contacts_sendable = 0

    for rec in qualified:
        for c in contacts_of(rec):
            total_contacts += 1
            if has_email(c):
                contacts_with_email += 1
            if has_linkedin(c):
                contacts_with_linkedin += 1
            if confirmations(c) >= 2:
                contacts_verified += 1
            if c.get("sendable"):
                contacts_sendable += 1

    print(f"  Total contacts on qualified records: {total_contacts}")
    print(f"  With email: {contacts_with_email}")
    print(f"  With LinkedIn: {contacts_with_linkedin}")
    print(f"  Verified (conf >= 2): {contacts_verified}")
    print(f"  Sendable: {contacts_sendable}")

    # Also count excluded contacts
    total_excluded = sum(len(excluded_of(r)) for r in qualified)
    print(f"  Excluded contacts: {total_excluded}")

    # ---- RECORD-LEVEL FUNNEL ----
    print("\n--- Record-level funnel ---")
    with_any_contacts = len([r for r in qualified if contacts_of(r)])
    with_email_contacts = len([r for r in qualified
                               if any(has_email(c) for c in contacts_of(r))])
    with_verified = len([r for r in qualified
                         if any(confirmations(c) >= 2 for c in contacts_of(r))])
    with_sendable = len([r for r in qualified
                         if any(c.get("sendable") for c in contacts_of(r))])

    print(f"  With any contacts: {with_any_contacts}")
    print(f"  With email contacts: {with_email_contacts}")
    print(f"  With verified contacts: {with_verified}")
    print(f"  With sendable contacts: {with_sendable}")

    # ================================================================
    # GAP 1: Qualified but no person discovery
    # ================================================================
    print("\n" + "=" * 70)
    print("GAP 1: Qualified but person discovery never ran or found nobody")
    print("=" * 70)

    gap1 = []
    for rec in qualified:
        contacts = contacts_of(rec)
        excluded = excluded_of(rec)
        log = log_steps(rec)
        qual_state = check_qualify_state(rec)
        qual = rec.get("qualification") or {}
        dm_approved = qual.get("dm_approved", False)
        cost_plan = qual.get("cost_plan") or {}

        # Did person discovery run?
        has_people_count = any("people-count" in (e.get("note") or "")
                               for e in log)
        has_dm = any("decision-maker" in (e.get("note") or "")
                     for e in log)
        enrich_steps = [e for e in log if e.get("step") == "enrich"]

        # Why no contacts?
        reason = "unknown"
        if not contacts and not excluded:
            if not has_people_count and not has_dm:
                reason = "discovery_never_ran"
            elif has_people_count and not has_dm:
                reason = "people_count_ran_no_dm_search"
            else:
                reason = "discovery_ran_found_nobody"
        elif not contacts and excluded:
            reason = "all_contacts_excluded"

        if not contacts:
            gap1.append({
                "id": h(rec.get("id")),
                "domain": h(rec.get("domain")),
                "company": rec.get("company", ""),
                "state": rec.get("state"),
                "qual_state": qual_state,
                "dm_approved": dm_approved,
                "drop_reason": rec.get("drop_reason"),
                "hold_reason": rec.get("hold_reason"),
                "has_people_count": has_people_count,
                "has_dm": has_dm,
                "enrich_logs": len(enrich_steps),
                "excluded_count": len(excluded),
                "excluded_reasons": [e.get("why", "?") for e in excluded],
                "cost_plan_calls": cost_plan.get("calls"),
                "cost_plan_enrichment": cost_plan.get("enrichment_required"),
                "reason": reason,
            })

    print(f"Records with no contacts: {len(gap1)}")

    # Group by reason
    gap1_reasons = {}
    for item in gap1:
        r = item["reason"]
        gap1_reasons[r] = gap1_reasons.get(r, 0) + 1
    print("\nReasons:")
    for r, c in sorted(gap1_reasons.items(), key=lambda x: -x[1]):
        print(f"  {r}: {c}")

    print("\nDetailed list:")
    for item in gap1:
        excl = f" excluded={item['excluded_count']}({','.join(item['excluded_reasons'][:3])})" if item['excluded_count'] else ""
        print(f"  {item['id']} | {item['domain']:12s} | state={item['state']:10s} | "
              f"qual={item['qual_state']:20s} | dm_app={item['dm_approved']} | "
              f"pc={item['has_people_count']} dm={item['has_dm']} | "
              f"drop={item['drop_reason']} | hold={item['hold_reason']}{excl} | "
              f"reason={item['reason']}")

    # ================================================================
    # GAP 2: Enriched but not verified
    # ================================================================
    print("\n" + "=" * 70)
    print("GAP 2: Contacts enriched but not verified")
    print("=" * 70)

    gap2 = []
    for rec in qualified:
        for c in contacts_of(rec):
            conf = confirmations(c)
            if conf >= 2:
                continue
            failure = classify_verification_failure(c)
            evidence = verification_evidence(c)
            providers = {}
            for ev in evidence:
                providers[ev.get("provider")] = ev.get("status")

            gap2.append({
                "record_id": h(rec.get("id")),
                "domain": h(rec.get("domain")),
                "contact_key": h(c.get("key")),
                "name": c.get("name", ""),
                "email": h(c.get("email")) if c.get("email") else "",
                "has_email": has_email(c),
                "has_linkedin": has_linkedin(c),
                "v_state": verification_state(c),
                "conf": conf,
                "mx": check_mx(c),
                "sendable": c.get("sendable"),
                "failure": failure,
                "providers": providers,
                "reoon_catch_all": check_reoon(c).get("is_catch_all"),
                "reoon_deliverable": check_reoon(c).get("is_deliverable"),
                "reoon_safe": check_reoon(c).get("is_safe_to_send"),
            })

    print(f"Contacts not verified: {len(gap2)}")

    # Group by failure
    gap2_failures = {}
    for item in gap2:
        f = item["failure"]
        gap2_failures[f] = gap2_failures.get(f, 0) + 1
    print("\nFailure kinds:")
    for f, c in sorted(gap2_failures.items(), key=lambda x: -x[1]):
        print(f"  {f}: {c}")

    # Distinguish "we found nobody" from "we found somebody and could not verify"
    found_but_unverified = [i for i in gap2 if i["has_email"]]
    not_found = [i for i in gap2 if not i["has_email"]]
    print(f"\n  Found email but could not verify: {len(found_but_unverified)}")
    print(f"  No email found at all: {len(not_found)}")

    # ================================================================
    # GAP 3: Verified but not campaign-ready
    # ================================================================
    print("\n" + "=" * 70)
    print("GAP 3: Records with verified contacts but not campaign-ready")
    print("=" * 70)

    # First, count campaign-ready
    campaign_ready_records = []
    not_ready_records = []

    for rec in qualified:
        contacts = contacts_of(rec)
        verified = [c for c in contacts if confirmations(c) >= 2]
        if not verified:
            continue

        elig = run_eligibility_full(rec)
        any_eligible = any(r["verdict"] == "eligible" for r in elig)

        if any_eligible:
            campaign_ready_records.append(rec)
        else:
            # Collect refusal reasons
            refusal_reasons = {}
            for r in elig:
                reason = r.get("reason") or "no_steps"
                if r["verdict"] != "eligible":
                    refusal_reasons[reason] = refusal_reasons.get(reason, 0) + 1

            # Check cadence state
            cadence = rec.get("cadence") or {}
            has_cadence = bool(cadence)
            total_steps = sum(len(steps) for steps in cadence.values())

            # Check approval
            from src import approval
            approved_steps = 0
            for ck, steps in cadence.items():
                for sk, step in steps.items():
                    if approval.is_approved(rec, ck, sk, step):
                        approved_steps += 1

            not_ready_records.append({
                "record_id": h(rec.get("id")),
                "domain": h(rec.get("domain")),
                "state": rec.get("state"),
                "verified_contacts": len(verified),
                "total_contacts": len(contacts),
                "has_cadence": has_cadence,
                "total_steps": total_steps,
                "approved_steps": approved_steps,
                "refusal_reasons": refusal_reasons,
                "drop_reason": rec.get("drop_reason"),
                "hold_reason": rec.get("hold_reason"),
                "elig_summary": [(r["step_key"], r["verdict"], r["reason"])
                                 for r in elig],
            })

    print(f"Campaign-ready records: {len(campaign_ready_records)}")
    print(f"Records with verified contacts but NOT campaign-ready: "
          f"{len(not_ready_records)}")

    # Aggregate refusal reasons
    all_refusals = {}
    for item in not_ready_records:
        for reason, count in item["refusal_reasons"].items():
            all_refusals[reason] = all_refusals.get(reason, 0) + count

    print("\nRefusal reasons (across all steps/contacts):")
    for reason, count in sorted(all_refusals.items(), key=lambda x: -x[1]):
        print(f"  {reason}: {count}")

    # Records with no cadence at all
    no_cadence = [i for i in not_ready_records if not i["has_cadence"]]
    print(f"\nRecords with NO cadence: {len(no_cadence)}")
    for item in no_cadence:
        print(f"  {item['record_id']} | {item['domain']} | "
              f"state={item['state']} | verified={item['verified_contacts']} | "
              f"refusals={item['refusal_reasons']}")

    # Records with cadence but no approval
    has_cad_no_approval = [i for i in not_ready_records
                           if i["has_cadence"] and i["approved_steps"] == 0]
    print(f"\nRecords with cadence but ZERO approvals: {len(has_cad_no_approval)}")

    # Records with some approvals but still not ready
    has_some_approval = [i for i in not_ready_records
                         if i["approved_steps"] > 0]
    print(f"Records with some approvals but still not ready: "
          f"{len(has_some_approval)}")
    for item in has_some_approval:
        print(f"  {item['record_id']} | {item['domain']} | "
              f"approved={item['approved_steps']}/{item['total_steps']} | "
              f"refusals={item['refusal_reasons']}")

    # ================================================================
    # RECOVERABLE vs NOT
    # ================================================================
    print("\n" + "=" * 70)
    print("RECOVERABLE vs NOT RECOVERABLE (Gap 3)")
    print("=" * 70)

    records_only_recoverable = []
    records_mixed = []
    records_only_not_recoverable = []
    records_no_refusals = []

    for item in not_ready_records:
        if not item["refusal_reasons"]:
            records_no_refusals.append(item)
            continue

        has_rec = False
        has_nonrec = False
        rec_actions = []
        nonrec_reasons = []

        for reason in item["refusal_reasons"]:
            cat, action = classify_recoverable(reason)
            if cat == "recoverable":
                has_rec = True
                rec_actions.append(action)
            elif cat == "not_recoverable":
                has_nonrec = True
                nonrec_reasons.append(action)
            else:
                print(f"  UNKNOWN: {reason}")

        if has_rec and not has_nonrec:
            records_only_recoverable.append(item)
        elif has_rec and has_nonrec:
            records_mixed.append(item)
        elif has_nonrec:
            records_only_not_recoverable.append(item)

    print(f"Records with ONLY recoverable refusals: {len(records_only_recoverable)}")
    print(f"Records with mixed refusals: {len(records_mixed)}")
    print(f"Records with ONLY non-recoverable refusals: "
          f"{len(records_only_not_recoverable)}")
    print(f"Records with no refusals (investigate): {len(records_no_refusals)}")

    # Best case
    best_case = len(campaign_ready_records) + len(records_only_recoverable)
    print(f"\nBest case if all recoverable resolved: {best_case}")
    print(f"  (current campaign-ready: {len(campaign_ready_records)})")
    print(f"  (+ recoverable: {len(records_only_recoverable)})")

    # ================================================================
    # INVESTIGATE records with no refusals
    # ================================================================
    if records_no_refusals:
        print("\n" + "=" * 70)
        print("INVESTIGATING: Records with verified contacts but no eligibility refusals")
        print("=" * 70)
        for item in records_no_refusals:
            rec_id = None
            for rec in qualified:
                if h(rec.get("id")) == item["record_id"]:
                    rec_id = rec
                    break
            if rec_id:
                cadence = rec_id.get("cadence") or {}
                print(f"\n  {item['record_id']} | {item['domain']} | "
                      f"state={item['state']} | "
                      f"verified={item['verified_contacts']} | "
                      f"cadence_keys={list(cadence.keys())}")
                for ck, steps in cadence.items():
                    print(f"    contact={h(ck)}: steps={list(steps.keys())}")
                    for sk, step in steps.items():
                        has_note = bool(step.get("note"))
                        has_body = bool(step.get("body"))
                        has_gen = step.get("generated", False)
                        has_appr = bool(step.get("approval"))
                        ch = step.get("channel", "?")
                        print(f"      {sk}: ch={ch} gen={has_gen} "
                              f"note={has_note} body={has_body} appr={has_appr}")

    # ================================================================
    # INVESTIGATE GAP 1 more deeply
    # ================================================================
    print("\n" + "=" * 70)
    print("GAP 1 DEEP DIVE: Why did discovery not run?")
    print("=" * 70)

    # Check dmplan state
    for item in gap1:
        rec_data = None
        for rec in qualified:
            if h(rec.get("id")) == item["id"]:
                rec_data = rec
                break
        if not rec_data:
            continue

        qual = rec_data.get("qualification") or {}
        cost_plan = qual.get("cost_plan") or {}
        messaging = qual.get("messaging") or {}
        persona_plan = qual.get("persona_plan") or {}
        log = log_steps(rec_data)

        # Check if there's a hold
        hold = rec_data.get("hold_reason")
        drop = rec_data.get("drop_reason")

        print(f"\n  {item['id']} | {item['domain']} | state={item['state']}")
        print(f"    qual_state={item['qual_state']} dm_approved={item['dm_approved']}")
        print(f"    drop={drop} hold={hold}")
        print(f"    cost_plan: calls={cost_plan.get('calls')} "
              f"enrichment={cost_plan.get('enrichment_required')} "
              f"max_credits={cost_plan.get('maximum_credits')}")
        print(f"    persona_plan: max_contacts={persona_plan.get('max_contacts')} "
              f"strategy={persona_plan.get('strategy')}")
        print(f"    enrich_log_entries: {item['enrich_logs']}")
        if item['excluded_count']:
            print(f"    excluded: {item['excluded_count']} -> "
                  f"{item['excluded_reasons']}")

        # Print relevant log entries
        for entry in log:
            step = entry.get("step")
            if step in ("enrich", "queued", "verified", "icp", "personas"):
                note = (entry.get("note") or "")[:80]
                print(f"    log: {step} -> {note}")

    # ================================================================
    # SUMMARY
    # ================================================================
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total records in snapshot: {len(recs)}")
    print(f"Qualified records: {len(qualified)}")
    print(f"  Gap 1 - no contacts: {len(gap1)}")
    print(f"  With contacts: {with_any_contacts}")
    print(f"    Gap 2 - contacts not verified: {len(gap2)}")
    print(f"    With verified contacts: {with_verified}")
    print(f"      Gap 3 - verified but not campaign-ready: {len(not_ready_records)}")
    print(f"      Campaign-ready: {len(campaign_ready_records)}")
    print()
    print(f"Best case campaign-ready (if all recoverable resolved): {best_case}")
    print(f"  vs 66 review records' best case (from TASK-194 context)")


if __name__ == "__main__":
    main()
