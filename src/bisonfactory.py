#!/usr/bin/env python3
"""Build a real EmailBison campaign from canonical state, and prove it.

The campaign row in `work/campaigns.jsonl` is the specification. There is no
second one: `campaigns.material()` already assembles every field an approval
decision covers, `campaigns.fingerprint()` already digests it, and
`providerwrites.staged_already()` already remembers what reached the provider.
This module orchestrates those; it invents no new state.

WHAT MAKES IT IDEMPOTENT. `bison_campaign_id` on the campaign row is the
anchor. It is written the instant the provider answers, inside the same
transaction that reads it, so a crash between the POST and the persist is the
one failure this cannot paper over - and that case is reported as ambiguous
rather than retried, because a retry would build a second campaign.

WHAT IT WILL NOT DO. It never resumes a campaign. Activation is what makes a
staged sequence start emailing real people, `bison.activate` is not in
`providerwrites.SUPPORTED`, and a factory that could start sending would make
every gate above it advisory. The campaign it leaves behind is populated,
sequenced and stopped.
"""
import argparse
import sys

from . import campaigns, clients, providerwrites, store
from .providers import ProviderError, bison


class FactoryRefused(Exception):
    """The campaign must not be staged, and the reason is not the provider's."""


class FactoryAmbiguous(Exception):
    """The provider may have acted. Read provider truth; do NOT retry."""


def stage(campaign_id, *, recs=None, config=None, live=False, by="system"):
    """Bring one campaign into existence at EmailBison, or confirm it is there.

    Returns a report: what was already true, what was done, and what the
    provider said afterwards. Dry run by default - `live=True` is explicit,
    because everything below this line writes to a real estate.
    """
    rows = campaigns.load()
    campaign = campaigns.require(str(campaign_id), rows)
    client = campaign.get("client")
    if not client:
        raise FactoryRefused(
            f"campaign {campaign_id} names no client; every provider write is "
            f"tenant-bound and an untenanted one cannot be attributed")
    if config is None:
        config = clients.load(client)
    recs = store.load() if recs is None else recs

    plan = _plan(campaign, recs, config)
    report = {"campaign": str(campaign_id), "client": client, "live": bool(live),
              "workspace": None, "plan": plan, "did": [], "provider": {}}
    if not live:
        report["did"].append("dry run: nothing was sent")
        return report

    # TENANCY, AGAINST THE PROVIDER, BEFORE ANYTHING IS WRITTEN.
    #
    # `workspace_id` is accepted and discarded by every list route on this
    # API, and the answer for a workspace that does not exist is identical to
    # the answer for the one that does - so a caller can believe it scoped a
    # read and be holding another client's estate. `GET /users` is the only
    # route that states which workspace the credential is actually bound to.
    workspace = bison.bound_workspace()
    report["workspace"] = workspace
    expected = ((config.get("providers") or {}).get("emailbison") or {}).get(
        "workspace")
    if expected is not None and str(workspace.get("id")) != str(expected):
        raise FactoryRefused(
            f"this credential is bound to EmailBison workspace "
            f"{workspace.get('id')} ({workspace.get('name')!r}) and {client!r} "
            f"is configured for workspace {expected}. Refusing to build one "
            f"client's campaign inside another client's estate")

    provider_id = _find_or_create(campaign, report, by=by)
    report["provider"]["campaign_id"] = provider_id

    _ensure_limits(provider_id, campaign, plan, report)
    _ensure_sequence(provider_id, campaign, plan, report, by=by)
    _ensure_leads(provider_id, campaign, plan, report, by=by)
    _ensure_stopped(provider_id, report, by=by)

    report["provider"]["readback"] = _readback(provider_id)
    return report


def _plan(campaign, recs, config):
    """What this campaign is, from canonical state. No provider call."""
    material = campaigns.material(campaign, recs=recs, config=config)
    # WHICH contacts comes from the approval material, because that is what
    # was blessed. Their NAMES come from the record: `_contact_material`
    # deliberately carries only what launching cares about - who, where, may
    # we send - and a name is none of those. Reading names out of it silently
    # produced empty ones, which the provider then rejected.
    by_id = {r.get("id"): r for r in recs}
    leads = []
    for record in material.get("records") or []:
        if record.get("missing") or record.get("dropped") or record.get("paused"):
            continue
        source = by_id.get(record.get("id")) or {}
        names = {c.get("key"): c for c in (source.get("contacts") or [])}
        for contact in record.get("contacts") or []:
            if not contact.get("email") or not contact.get("sendable"):
                continue
            person = names.get(contact.get("key")) or {}
            first = (person.get("first_name") or "").strip()
            if not first:
                raise FactoryRefused(
                    f"contact {contact.get('key')!r} on record "
                    f"{record.get('id')!r} has no first name, and EmailBison "
                    f"requires one. Refusing to invent a name that will greet "
                    f"a real person")
            leads.append({"record_id": record.get("id"),
                          "contact_key": contact.get("key"),
                          "email": contact.get("email"),
                          "first_name": first,
                          "last_name": (person.get("last_name") or "").strip()})
    return {"fingerprint": campaigns.fingerprint(campaign, recs=recs,
                                                 config=config),
            "name": campaign.get("name") or f"resonate-{campaign.get('id')}",
            "leads": leads,
            "bison_campaign_id": campaign.get("bison_campaign_id")}


def _find_or_create(campaign, report, by="system"):
    """The provider campaign for this row, reused if it exists.

    Reuse comes first and is checked against the PROVIDER, not against the
    row: a `bison_campaign_id` naming a campaign that has since been deleted
    is a stale binding, and building on it would attach leads to nothing.
    """
    bound = campaign.get("bison_campaign_id")
    if bound:
        try:
            live_row = bison.campaign(bound)
        except ProviderError as e:
            raise FactoryRefused(
                f"campaign {campaign.get('id')} is bound to EmailBison "
                f"campaign {bound}, which the provider will not return "
                f"({e}). Refusing to create a second one behind a binding "
                f"that may still be valid; reconcile by hand") from None
        report["did"].append(f"reused EmailBison campaign {bound}")
        report["provider"]["status_before"] = live_row.get("status")
        return bound

    payload = {"name": report["plan"]["name"]}
    # `perform` reports the response as trimmed JSON TEXT, which is right for
    # an audit line and useless for reading an id back out of. The transport
    # holds the real row, so it is captured here rather than reparsed.
    created = {}

    def _create(p):
        created.update(bison.create_campaign(p["name"]))
        return created

    providerwrites.perform(
        providerwrites.EMAIL_CREATE_CAMPAIGN,
        campaign=str(campaign.get("campaign_id")), tenant=campaign.get("client"),
        payload=payload, transport=_create,
        readback=lambda: {"exists": bool(created.get("id"))},
        expected={"exists": True}, by=by)
    provider_id = created.get("id")
    if not provider_id:
        raise FactoryAmbiguous(
            "EmailBison accepted the campaign but returned no id. A campaign "
            "may now exist that nothing here can name. Find it by name and "
            "bind it by hand; do NOT re-run this")

    # PERSIST IMMEDIATELY, IN ITS OWN TRANSACTION.
    # Everything after this point can be retried. This cannot: an unpersisted
    # id is a campaign nobody can find, and the next run would build another.
    with campaigns.transaction() as rows:
        row = campaigns.get(str(campaign.get("campaign_id")), rows)
        if row is not None:
            row["bison_campaign_id"] = provider_id
            campaigns.log(row, "provider", f"EmailBison campaign {provider_id} "
                                           f"created and bound")
    report["did"].append(f"created EmailBison campaign {provider_id}")
    return provider_id


def _ensure_limits(provider_id, campaign, plan, report):
    """Cap the campaign before it holds anybody.

    The provider's default is 1000 emails a day and `POST /campaigns` accepts
    a cap and stores 1000 anyway, so a campaign is uncapped until something
    explicitly caps it. This runs before leads are attached: the order is the
    point, since a cap applied afterwards is a cap that was briefly absent.

    A campaign whose daily volume nobody configured is REFUSED rather than
    left on the default. "Nobody said" and "a thousand a day" must not be the
    same state.
    """
    volume = (campaign.get("daily_volume") or {}).get("email")
    if not volume:
        raise FactoryRefused(
            f"campaign {campaign.get('campaign_id')!r} sets no email daily "
            f"volume. EmailBison defaults to 1000 a day and discards a cap "
            f"passed at create time, so staging this would leave a campaign "
            f"nobody rate-limited")
    state = bison.set_limits(provider_id, plan["name"], int(volume))
    report["provider"]["limits"] = state
    report["did"].append(f"capped at {state['max_emails_per_day']}/day")


def _ensure_sequence(provider_id, campaign, plan, report, by="system"):
    """Write the sequence once. The campaign row remembers that it was."""
    steps = plan.get("steps") or []
    if not steps:
        report["did"].append("no sequence staged: the plan carries no steps")
        return
    payload = {"title": plan["name"], "sequence_steps": steps}
    already = providerwrites.staged_already(campaign.get("campaign_id"),
                                            providerwrites.EMAIL_SET_SEQUENCE,
                                            payload)
    if already:
        report["did"].append("sequence already staged; unchanged")
        return
    providerwrites.perform(
        providerwrites.EMAIL_SET_SEQUENCE,
        campaign=str(campaign.get("campaign_id")), tenant=campaign.get("client"),
        payload=payload,
        transport=lambda p: bison.set_sequence(provider_id, p["title"],
                                               p["sequence_steps"]),
        readback=lambda: {"steps": len(steps)},
        expected={"steps": len(steps)}, by=by)
    report["did"].append(f"staged a {len(steps)}-step sequence")


def _known_lead_ids(campaign, wanted):
    """Provider lead ids this system already recorded, by contact key."""
    recs = store.load()
    by_id = {r.get("id"): r for r in recs}
    known = {}
    for lead in wanted:
        rec = by_id.get(lead["record_id"]) or {}
        for contact in rec.get("contacts") or []:
            if contact.get("key") == lead["contact_key"] and contact.get(
                    "bison_lead_id"):
                known[lead["contact_key"]] = contact["bison_lead_id"]
    return known


def _remember_lead(lead, lead_id):
    """Write the provider's id onto the contact, immediately.

    Immediately, and in its own transaction, for the same reason the campaign
    id is: an id the provider issued and this system did not record is a lead
    that will be created again, and the second attempt is the one that fails.
    """
    with store.transaction() as rows:
        for rec in rows:
            if rec.get("id") != lead["record_id"]:
                continue
            for contact in rec.get("contacts") or []:
                if contact.get("key") == lead["contact_key"]:
                    contact["bison_lead_id"] = lead_id


def _ensure_leads(provider_id, campaign, plan, report, by="system"):
    """Create the leads this campaign needs, then attach exactly those.

    Attachment is checked against provider membership on both sides, so a
    re-run costs reads and writes nothing. `bison.attach_leads` raises unless
    the readback contains what was asked for, which is what stops a partial
    attach being reported as a full one.
    """
    wanted = plan.get("leads") or []
    if not wanted:
        report["did"].append("no leads staged: the plan carries none")
        return
    # The variables must exist on the workspace before a lead may carry one:
    # the provider refuses an undeclared name outright. Idempotent, and it
    # creates nothing that can reach a person.
    bison.ensure_custom_variables()
    members = set(bison.campaign_lead_ids(provider_id))
    known = _known_lead_ids(campaign, wanted)
    ids, created, reconciled = [], 0, 0
    for lead in wanted:
        existing = known.get(lead["contact_key"])
        if existing:
            ids.append(existing)
            continue
        try:
            row = bison.create_lead({
                "email": lead["email"],
                "first_name": lead["first_name"],
                "last_name": lead["last_name"],
                # WHO THIS IS, IN THE PROVIDER'S OWN RECORD.
                # `adapters.from_emailbison` reads these back off an inbound
                # reply. Without them a reply arrives attached to an address
                # and to nothing else, and reply-stop cannot find the person
                # it is supposed to stop.
                "custom_variables": bison._variables({
                    "record_id": lead["record_id"],
                    "contact_key": lead["contact_key"],
                    "client": campaign.get("client") or ""})})
            created += 1
        except ProviderError as e:
            # ALREADY THERE, AND WE NEVER WROTE IT DOWN.
            # Creating it again is what the provider just refused, and
            # guessing an id would attach a stranger to this campaign. So the
            # address is looked up exactly, or this stops.
            if "already been taken" not in str(e):
                raise
            row = bison.find_lead_by_email(lead["email"])
            if not row:
                raise FactoryAmbiguous(
                    f"EmailBison says {lead['email']} already exists but will "
                    f"not return it - its lead search lags behind creation. "
                    f"Wait and re-run; do NOT create a duplicate") from None
            reconciled += 1
        _remember_lead(lead, row["id"])
        ids.append(row["id"])
    outcome = bison.attach_leads(provider_id, ids)
    report["provider"]["attached"] = outcome
    # Counted, not just narrated. Which PATH found each lead matters: the
    # remembered id is authoritative, while reconciliation leans on a provider
    # search that lags behind creation. A run that quietly stopped using the
    # first and started relying on the second would still avoid duplicates -
    # and would be one indexing delay away from not avoiding them.
    report["provider"]["leads"] = {"created": created, "reused": len(known),
                                   "reconciled": reconciled}
    report["did"].append(
        f"created {created} lead(s), reused {len(known)}, reconciled "
        f"{reconciled}; attached {len(outcome['attached'])}, "
        f"{len(outcome['already'])} already present, "
        f"{len(outcome['members'])} in campaign now")
    report["provider"]["members_before"] = sorted(members)


def _ensure_stopped(provider_id, report, by="system"):
    """Leave it stopped. A staged campaign that can send is not staged."""
    state = bison.pause_campaign(provider_id)
    report["did"].append(f"campaign left {state['status']}")


def _readback(provider_id):
    """What the provider says is true, after everything above."""
    row = bison.campaign(provider_id)
    return {"id": row.get("id"), "name": row.get("name"),
            "status": row.get("status"),
            "leads": len(bison.campaign_lead_ids(provider_id))}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("campaign", help="campaign id in work/campaigns.jsonl")
    parser.add_argument("--live", action="store_true",
                        help="actually write to EmailBison")
    args = parser.parse_args(argv)
    try:
        report = stage(args.campaign, live=args.live)
    except (FactoryRefused, FactoryAmbiguous, ProviderError) as e:
        print(f"{type(e).__name__}: {e}")
        return 1
    for line in report["did"]:
        print(" ", line)
    print(" provider:", report["provider"].get("readback"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
