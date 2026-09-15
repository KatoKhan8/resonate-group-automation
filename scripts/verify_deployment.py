#!/usr/bin/env python3
"""What the provider holds after a deployment, asked of the provider.

READ-ONLY, ALWAYS. This script has no `--live` because it never writes. It is
the thing that decides whether a deployment happened, and a verifier that
could change anything would be answering its own question.

WHY IT EXISTS RATHER THAN A REPORT ASSEMBLED FROM LOCAL STATE.

`work/campaigns.jsonl` and the action ledger both record what this system
BELIEVES it did. Neither is evidence. The standing rule is that a campaign is
not live because our ledger says it exists, and the only authority for
provider state is a provider readback - so every number below comes from a
read route, and where a route cannot answer, this prints UNVERIFIABLE rather
than a zero.

That distinction is the whole point. A zero and a wrong lookup look identical
from outside, and this repository has been bitten by exactly that: an
evaluator reported INSUFFICIENT_DATA forever because nothing wrote the field
it read.

    py -3 scripts/verify_deployment.py --campaign productive-linkedin-production-v1
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import campaigns, collision, configdiff, heyreachfactory, store  # noqa: E402
from src.providers import heyreach  # noqa: E402


def _expected_cohort(campaign, recs, config):
    """Who local state says should be there, and their merge variables.

    Local state is allowed to state the EXPECTATION. It is never allowed to
    state the outcome - that is what the provider read below is for.
    """
    wanted = set(campaign.get("record_ids") or ())
    rows = []
    for rec in recs:
        if rec.get("id") not in wanted:
            continue
        for contact in rec.get("contacts") or ():
            if not contact.get("linkedin"):
                continue
            fields, missing = heyreachfactory.custom_fields_for(
                rec, contact.get("key"), config=config)
            if missing:
                continue
            rows.append({
                "record_id": rec.get("id"),
                "contact_key": contact.get("key"),
                "url": contact.get("linkedin"),
                "slug": collision.profile_slug(contact.get("linkedin")),
                "variables": sorted(fields),
            })
    return rows


def main(argv=None):
    p = argparse.ArgumentParser(prog="verify_deployment", description=__doc__)
    p.add_argument("--campaign", required=True)
    a = p.parse_args(argv)

    rows = campaigns.load()
    campaign = campaigns.require(str(a.campaign), rows)
    provider_id = campaign.get("heyreach_campaign_id")
    if not provider_id:
        print("REFUSED: the canonical campaign names no heyreach_campaign_id")
        return 1
    from src import clients
    config = clients.load(campaign.get("client"))
    recs = store.load()
    expected = _expected_cohort(campaign, recs, config)

    # ------------------------------------------------ the provider's answer
    row = heyreach.campaign_read(provider_id)
    provider = configdiff.provider_heyreach(str(provider_id))
    leads, total = [], None
    for page in range(50):
        found, total = heyreach.campaign_leads(
            provider_id, offset=page * heyreach.MAX_PAGE)
        leads.extend(found)
        if not found or (total is not None and len(leads) >= int(total)):
            break
    try:
        stats = heyreach.campaign_stats(provider_id)
    except Exception as e:
        stats = {"UNVERIFIABLE": f"{type(e).__name__}: {e}"}

    present = {str(l.get("profile_url") or "").strip().lower()
               for l in leads if l.get("profile_url")}
    wanted_urls = {r["url"].strip().lower() for r in expected}
    missing = wanted_urls - present
    strangers = present - wanted_urls

    errored = [l for l in leads if l.get("error_code")]

    print("=" * 66)
    print(f"CAMPAIGN ID            {provider_id}  ({a.campaign})")
    print(f"CAMPAIGN NAME          {row.get('name')}")
    print(f"CAMPAIGN STATUS        {row.get('status')}")
    print(f"  startedAt            {row.get('startedAt')}")
    print(f"LEADS REQUESTED        {len(expected)}")
    print(f"LEADS ACTUALLY PRESENT {len(present)}"
          f"   (provider totalCount {total})")
    print(f"REJECTED/FAILED        {len(errored)} lead(s) carry an errorCode")
    for lead in errored[:10]:
        print(f"    {lead.get('profile_url')}  {lead.get('error_code')}  "
              f"{str(lead.get('state'))[:40]}")
    print(f"  missing from provider {len(missing)}")
    for url in sorted(missing)[:10]:
        print(f"    MISSING {url}")
    print(f"  present but not asked for {len(strangers)}")
    for url in sorted(strangers)[:10]:
        print(f"    STRANGER {url}")

    print(f"SENDERS                {sorted(provider.get('sender_ids') or [])}")
    print(f"  campaignAccountIds   {row.get('campaignAccountIds')}")
    print(f"  per-lead senders     "
          f"{sorted({l.get('sender_id') for l in leads}) if leads else '[]'}")
    print(f"CADENCE INSTALLED      {len(provider.get('actions') or [])} node "
          f"type(s): {sorted(provider.get('actions') or [])}")
    print(f"  connection copy      {provider.get('note')!r}")
    print(f"  delays               {provider.get('delays')}")
    print(f"  list                 {provider.get('list_id')}")
    print(f"  org unit             {provider.get('org_unit')}")

    print("MERGE VARIABLES")
    if not expected:
        print("    none - no contact has approved copy for every role")
    for r in expected[:12]:
        print(f"    {r['contact_key']:28} {len(r['variables'])} vars "
              f"{r['variables']}")

    print("PROVIDER READBACK")
    print(f"  per-lead states      "
          f"{json.dumps(_counts(leads, 'state'))}")
    print(f"  connection states    "
          f"{json.dumps(_counts(leads, 'connection_state'))}")
    print(f"  campaign counters    {json.dumps(stats)}")

    verdict = "CLEAN"
    why = []
    if missing:
        verdict, _ = "NOT CLEAN", why.append(
            f"{len(missing)} asked-for lead(s) are not at the provider")
    if strangers:
        verdict, _ = "NOT CLEAN", why.append(
            f"{len(strangers)} lead(s) are present that nobody asked for")
    if errored:
        verdict, _ = "NOT CLEAN", why.append(
            f"{len(errored)} lead(s) carry a provider errorCode")
    if not expected:
        verdict, _ = "NOT CLEAN", why.append("nothing was expected")
    print("=" * 66)
    print(f"VERDICT  {verdict}" + (f"  - {'; '.join(why)}" if why else ""))
    return 0 if verdict == "CLEAN" else 1


def _counts(leads, key):
    out = {}
    for lead in leads:
        value = str(lead.get(key))
        out[value] = out.get(value, 0) + 1
    return out


if __name__ == "__main__":
    raise SystemExit(main())
