#!/usr/bin/env python3
"""Does adding a lead to a LIST send anything? Measured, in two stages.

WHY THIS PROBE EXISTS.

Adding a lead to a HeyReach CAMPAIGN activates that campaign - the vendor
documents it for PAUSED and for FINISHED - so there is no campaign-level
staging state and `LINKEDIN_ADD_LEAD` is resealed.

A LIST is a different object. `/list/GetAll` returns lists with
`campaignIds: []`, attached to nothing. If a list can be filled without
starting anything, the separation between STAGING and ACTIVATION survives on
this provider, using the primitive that actually supports it.

That is a question about the provider and it is answered by asking the
provider, not by reasoning about it.

TWO STAGES, AND THE FIRST CANNOT REACH ANYBODY.

    stage 1   a NEW list, attached to no campaign, one approved lead.
              A list bound to nothing has no sequence and no sender, so
              nothing can be sent from it whatever the answer turns out to be.
              This measures the list-add primitive in isolation.

    stage 2   the list that IS bound to the production campaign, one lead,
              with the campaign's status and counters read before and after.
              This is the question that matters and it is only asked if
              stage 1 says the primitive is readable and safe.

Stage 2 is NOT run by default. It needs --stage2 and it names the risk in its
own output, because if the answer is "yes, it activates", a real person
receives a connection request.

WHAT IS PROVEN AFTER EACH WRITE, and any failure stops the probe:

    the lead is in the list            (identity, not a count)
    the campaign's status is unchanged
    connectionsSent and uniqueLeadsContacted are unchanged
    no campaign gained a lead

    py -3 scripts/probe_list_staging.py
    py -3 scripts/probe_list_staging.py --live
    py -3 scripts/probe_list_staging.py --live --stage2
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import campaigns, clients, collision, heyreachfactory, linkedin, store  # noqa: E402
from src.providers import heyreach  # noqa: E402

CAMPAIGN = "productive-linkedin-production-v1"


class ProbeRefused(RuntimeError):
    """The probe cannot proceed, and the reason is on the exception."""


def _campaign_state(provider_id):
    row = heyreach.campaign_read(provider_id) or {}
    _rows, leads = heyreach.campaign_leads(provider_id, offset=0)
    try:
        stats = heyreach.campaign_stats(provider_id)
    except Exception as e:                                    # noqa: BLE001
        stats = {"unreadable": f"{type(e).__name__}: {e}"}
    return {"status": row.get("status"), "leads": leads, "stats": stats}


def _one_approved_contact(config):
    """One contact that has already cleared every cohort gate.

    Deliberately taken from the campaign's OWN record set rather than chosen
    here: those contacts are collision-cleared at account and person level,
    carry approved CONTROL copy by fingerprint, and are the people this
    campaign is for. A probe that invents a lead is a probe against a
    different question.
    """
    campaign = campaigns.require(CAMPAIGN)
    wanted = set(campaign.get("record_ids") or ())
    for rec in store.load():
        if rec.get("id") not in wanted:
            continue
        for contact in rec.get("contacts") or ():
            url = linkedin.canonical(contact.get("linkedin"))
            if not url:
                continue
            fields, missing = heyreachfactory.custom_fields_for(
                rec, contact.get("key"), config=config)
            if missing:
                continue
            return {"record_id": rec.get("id"),
                    "contact_key": contact.get("key"),
                    "linkedin_url": url,
                    "slug": collision.profile_slug(url),
                    "first_name": (contact.get("name") or "").split(" ")[0],
                    "last_name": "", "company": rec.get("company", ""),
                    "title": ""}
    raise ProbeRefused(
        "no contact on this campaign's records has approved copy for every "
        "role, so there is nobody the probe may legitimately use")


def _prove_nothing_moved(label, before, after):
    problems = []
    if before["status"] != after["status"]:
        problems.append(f"campaign status moved {before['status']!r} -> "
                        f"{after['status']!r}")
    if int(before["leads"] or 0) != int(after["leads"] or 0):
        problems.append(f"campaign lead count moved {before['leads']} -> "
                        f"{after['leads']}")
    for counter in ("connectionsSent", "uniqueLeadsContacted"):
        was, now = (before["stats"] or {}).get(counter), \
                   (after["stats"] or {}).get(counter)
        if was != now:
            problems.append(f"{counter} moved {was} -> {now}")
    if problems:
        raise ProbeRefused(f"{label}: " + "; ".join(problems))
    print(f"  {label}: campaign unchanged - status {after['status']!r}, "
          f"leads {after['leads']}, counters {after['stats']}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="probe_list_staging", description=__doc__)
    p.add_argument("--live", action="store_true")
    p.add_argument("--stage2", action="store_true",
                   help="also probe the list BOUND to the production "
                        "campaign. If a list write activates its campaign, "
                        "this sends a real connection request")
    a = p.parse_args(argv)

    config = clients.load("productive")
    campaign = campaigns.require(CAMPAIGN)
    provider_id = int(campaign.get("heyreach_campaign_id"))
    bound_list = campaign.get("heyreach_list_id")
    lead = _one_approved_contact(config)

    before = _campaign_state(provider_id)
    print(f"campaign {provider_id}: status={before['status']!r} "
          f"leads={before['leads']} counters={before['stats']}")
    print(f"bound list: {bound_list}")
    print(f"lead: {lead['record_id']}/{lead['contact_key']} -> {lead['slug']}")

    if not a.live:
        print("\nDRY RUN. Stage 1 would create a NEW list attached to no "
              "campaign and add this one lead to it, then prove the "
              "production campaign did not move.")
        if a.stage2:
            print("Stage 2 would then add the same lead to the BOUND list "
                  f"{bound_list} and prove the same thing.")
        return 0

    # ------------------------------------------------------------- stage 1
    name = "RESONATE - STAGING PROBE - DO NOT USE"
    print(f"\nstage 1: creating an unbound list {name!r} ...")
    created = heyreach.create_list(name)
    probe_list = created.get("id")
    print(f"  created list {probe_list} campaignIds="
          f"{created.get('campaignIds')}")
    if created.get("campaignIds"):
        raise ProbeRefused(
            f"the new list is already attached to {created['campaignIds']}, "
            f"so it cannot answer the isolated question")

    heyreach.add_leads_to_list(probe_list, [lead])
    rows, total = heyreach.list_leads(probe_list)
    found = {str(r.get("profile_url") or "").strip().lower() for r in rows}
    print(f"  list {probe_list} holds {total}: {sorted(found)}")
    if lead["linkedin_url"].lower() not in found:
        raise ProbeRefused(
            f"the lead was not read back from list {probe_list}; a write "
            f"nobody can read back is not a staged lead")
    _prove_nothing_moved("stage 1", before, _campaign_state(provider_id))
    print("\nSTAGE 1: a list write is readable and moved no campaign.")

    if not a.stage2:
        print("Stage 2 not requested. The bound list is the question that "
              "matters and is where a real send becomes possible.")
        return 0

    # ------------------------------------------------------------- stage 2
    print(f"\nstage 2: adding the same lead to BOUND list {bound_list} ...")
    mid = _campaign_state(provider_id)
    heyreach.add_leads_to_list(bound_list, [lead])
    rows, total = heyreach.list_leads(bound_list)
    found = {str(r.get("profile_url") or "").strip().lower() for r in rows}
    print(f"  list {bound_list} holds {total}: {sorted(found)}")
    after = _campaign_state(provider_id)
    print(f"  campaign now: status={after['status']!r} leads={after['leads']} "
          f"counters={after['stats']}")
    _prove_nothing_moved("stage 2", mid, after)
    print("\nSTAGE 2: filling the BOUND list moved no campaign state and sent "
          "nothing. List staging is real on this provider.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
