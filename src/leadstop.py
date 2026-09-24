#!/usr/bin/env python3
"""Stop the next email to one person, at the provider, and prove it stopped.

A local pause stops OUR cadence from planning another step. It does not stop
the provider, which runs its own scheduler and holds its own queue - so until
something in this module ran, "suppressed" meant "we will not plan another
one" and never "they will not receive another one". For a reply EmailBison
happens to stop natively; for a suppression, an agency DNC, an account stop or
a client's own do-not-contact list, nothing was telling it anything.

    POST /api/campaigns/{id}/leads/stop-future-emails  {"lead_ids": [...]}

Measured 2026-09-13: one lead moved `in_sequence` -> `stopped` in about two
seconds, its sibling untouched, the campaign untouched.

WHY IDEMPOTENCY COMES FROM THE PROVIDER HERE. `providerwrites.staged_already`
remembers one entry per operation on the CAMPAIGN row, which is the right
shape for staging a campaign and the wrong one for a per-person verb: the
second person stopped would overwrite the first's record. The provider's own
`lead_campaign_data` already holds this per person, so it is read rather than
mirrored - and a lead that already reads as stopped costs one GET and no
write.
"""
import argparse
import sys

from . import campaigns, events, providerwrites, store
from .providers import ProviderError, bison, heyreach


class StopRefused(Exception):
    """This stop must not be attempted, and the provider is not the reason."""


class StopUnverified(Exception):
    """The provider may or may not have stopped them. Never retried blindly."""


def stop_contact(rec, contact, why, *, campaign=None, rows=None, live=False,
                 by="system", persist=True):
    """Prevent the next email to this one person. Returns what is now true.

    Refuses rather than guesses at every point where it cannot name exactly
    who is being stopped: an unbound lead, an unbound campaign, or a record
    whose client disagrees with the campaign's.
    """
    lead_id = (contact or {}).get("bison_lead_id")
    if not lead_id:
        raise StopRefused(
            f"contact {(contact or {}).get('key')!r} on record "
            f"{(rec or {}).get('id')!r} carries no `bison_lead_id`, so there "
            f"is nobody at the provider to stop. If they were ever staged, "
            f"reconcile the binding first - do NOT search by address and "
            f"guess")
    campaign = campaign or _campaign_of(rec, rows,
                                        requires="bison_campaign_id")
    if campaign is None:
        raise StopRefused(
            f"record {(rec or {}).get('id')!r} is in no campaign, so there is "
            f"no provider campaign to stop them in")
    # TENANCY. The same check `executionguard` makes, for the same reason: a
    # stop aimed through another client's campaign is still a write into
    # another client's estate.
    if rec.get("client") and campaign.get("client") and \
            rec["client"] != campaign["client"]:
        raise StopRefused(
            f"record {rec['id']!r} belongs to {rec['client']!r} and campaign "
            f"{campaign.get('campaign_id')!r} to {campaign['client']!r}")
    provider_campaign = campaign.get("bison_campaign_id")
    if not provider_campaign:
        raise StopRefused(
            f"campaign {campaign.get('campaign_id')!r} names no EmailBison "
            f"campaign, so this lead's membership cannot be addressed")

    report = {"record": rec.get("id"), "contact": contact.get("key"),
              "lead_id": lead_id, "campaign": campaign.get("campaign_id"),
              "provider_campaign": provider_campaign, "why": why,
              "live": bool(live), "already": False, "stopped": False}

    # ALREADY STOPPED IS A SUCCESS, NOT A WRITE.
    current = bison.membership(provider_campaign, [lead_id]).get(int(lead_id))
    report["status_before"] = current
    if current is None:
        raise StopRefused(
            f"lead {lead_id} is not a member of EmailBison campaign "
            f"{provider_campaign}. The stop route answers 200 for a lead it "
            f"does not hold and does nothing, so this refuses rather than "
            f"recording a stop that cannot happen")
    if str(current).lower() in bison.STOPPED_STATES:
        report["already"] = True
        report["stopped"] = True
        report["status_after"] = current
        return report
    if not live:
        report["note"] = "dry run: the provider was not written to"
        return report

    try:
        outcome = providerwrites.perform(
            providerwrites.EMAIL_STOP_LEAD,
            campaign=str(campaign.get("campaign_id")),
            tenant=campaign.get("client"),
            payload={"lead_ids": [lead_id], "why": why},
            transport=lambda p: bison.stop_lead(provider_campaign,
                                                p["lead_ids"]),
            readback=lambda: {"stopped": True},
            expected={"stopped": True}, by=by)
    except providerwrites.WriteUnverified as e:
        raise StopUnverified(
            f"the stop for lead {lead_id} could not be confirmed: {e}. Read "
            f"provider truth before anything else is sent to this person"
        ) from None
    report["stopped"] = True
    report["status_after"] = bison.membership(
        provider_campaign, [lead_id]).get(int(lead_id))
    report["verdict"] = (outcome or {}).get("class")

    # Written where the rest of this person's history is, so a later audit can
    # answer "when did they stop hearing from us, and on whose say-so".
    _record(rec, contact, report, persist=persist)
    return report


def stop_linkedin_contact(rec, contact, why, *, campaign=None, rows=None,
                          live=False, by="system", persist=True):
    """Prevent the next LinkedIn step to this one person.

    The LinkedIn counterpart of `stop_contact`. Uses `heyreach_lead_id` and
    `heyreach_campaign_id` rather than the EmailBison equivalents. The
    transport is `heyreach.stop_lead_in_campaign`, which reads back per lead
    and refuses when the provider still reports the lead as running.

    Goes through `providerwrites.perform` with `LINKEDIN_STOP_LEAD`. That
    verb is NOT in `SUPPORTED` - the mechanism exists and the door is shut
    until Claude enables it. A `WriteRefused` from the door is translated
    into `StopRefused` so the sweep can report it without learning a second
    exception type.
    """
    lead_id = (contact or {}).get("heyreach_lead_id")
    if not lead_id:
        raise StopRefused(
            f"contact {(contact or {}).get('key')!r} on record "
            f"{(rec or {}).get('id')!r} carries no `heyreach_lead_id`, so "
            f"there is nobody at HeyReach to stop")
    campaign = campaign or _campaign_of(rec, rows,
                                        requires="heyreach_campaign_id")
    if campaign is None:
        raise StopRefused(
            f"record {(rec or {}).get('id')!r} is in no campaign, so there "
            f"is no provider campaign to stop them in")
    provider_campaign = campaign.get("heyreach_campaign_id")
    if not provider_campaign:
        raise StopRefused(
            f"campaign {campaign.get('campaign_id')!r} names no HeyReach "
            f"campaign, so this lead's membership cannot be addressed")

    # THE FIELD IS `linkedin`. IT HAS NEVER BEEN `linkedin_url`.
    #
    # MEASURED 2026-09-23, the evening LINKEDIN_STOP_LEAD was enabled: 1,014
    # contacts in the store carry `linkedin` and ZERO carry `linkedin_url`.
    # This line read the second, so `profile_url` was ALWAYS the empty
    # string, and `heyreach.stop_lead_in_campaign` refuses an empty leadUrl -
    # correctly, because "the provider matches on them and a partial body is
    # a call that stops nobody while returning success".
    #
    # So the email->LinkedIn stop could never have succeeded. Not sometimes:
    # never. It was invisible because the verb was sealed - `perform` refused
    # before the transport ran, so the empty URL never reached the provider -
    # and enabling the verb is exactly what would have made it live. This is
    # the register's "existence is not function" in its purest form: wired,
    # tested, sealed, and incapable.
    #
    # `linkedin_url` is kept as a fallback rather than replaced outright:
    # `heyreachfactory` builds ENRICHED ROWS under that key, and a caller
    # passing one of those instead of a contact should keep working rather
    # than start failing closed for a new reason.
    profile_url = ((contact or {}).get("linkedin")
                   or (contact or {}).get("linkedin_url") or "")

    report = {"record": rec.get("id"), "contact": contact.get("key"),
              "lead_id": lead_id, "campaign": campaign.get("campaign_id"),
              "provider_campaign": provider_campaign, "why": why,
              "live": bool(live), "already": False, "stopped": False,
              "channel": "linkedin"}

    if not live:
        report["note"] = "dry run: the provider was not written to"
        return report

    try:
        outcome = providerwrites.perform(
            providerwrites.LINKEDIN_STOP_LEAD,
            campaign=str(campaign.get("campaign_id")),
            tenant=campaign.get("client"),
            payload={"lead_id": lead_id, "why": why},
            transport=lambda p: heyreach.stop_lead_in_campaign(
                provider_campaign, lead_id, profile_url),
            readback=lambda: heyreach.campaigns_for_lead(
                profile_url=profile_url)[0],
            expected={"stopped": True}, by=by)
    except providerwrites.WriteRefused as e:
        raise StopRefused(
            f"the LinkedIn stop for lead {lead_id} was refused by the write "
            f"layer: {e}") from None
    except providerwrites.WriteUnverified as e:
        raise StopUnverified(
            f"the LinkedIn stop for lead {lead_id} could not be confirmed: "
            f"{e}") from None
    report["stopped"] = True
    report["verdict"] = (outcome or {}).get("class")
    _record_linkedin(rec, contact, report, persist=persist)
    return report


def sweep(recs=None, rows=None, live=False, by="system"):
    """Stop everybody at the provider who must not be contacted any more.

    A reply arrives through `inbound` and stops that person there. Nothing
    else does: a suppression, an agency DNC, an account stop, a client's
    do-not-contact list and an unsubscribe read from a file all change
    canonical state and tell the provider nothing. Hooking each of those
    writers separately would mean finding all of them and never missing a
    future one.

    So this asks the question the other way round: of the people this system
    has actually STAGED at the provider, which are now ineligible for a reason
    that means "do not contact"? It re-derives that from `eligibility` rather
    than from a flag somebody remembered to set, so a stop reason added later
    is covered without editing this.

    Idempotent and safe to re-run: `stop_contact` reads provider truth first
    and writes nothing for somebody already stopped. Dry run by default.
    """
    from . import eligibility, executionguard

    recs = store.load() if recs is None else recs
    rows = campaigns.load() if rows is None else rows
    report = {"checked": 0, "stopped": [], "already": [], "failed": [],
              "live": bool(live)}
    for rec in recs:
        # RESOLVED PER CHANNEL, NOT ONCE. One channel-blind lookup passed to
        # both stops is the same defect `_campaign_of(requires=...)` fixes,
        # reintroduced here by the explicit `campaign=` argument: a contact on
        # both channels would have had its LinkedIn stop handed the email row.
        # Passing the row explicitly overrides the callee's own resolution, so
        # the fix has to be made here too rather than inherited.
        email_campaign = _campaign_of(rec, rows, requires="bison_campaign_id")
        linkedin_campaign = _campaign_of(rec, rows,
                                         requires="heyreach_campaign_id")
        for contact in rec.get("contacts") or []:
            # TASK-235: count every staged contact, not just email-staged
            # ones. A contact with only heyreach_lead_id was previously
            # skipped silently, which is why a missing LinkedIn stop looked
            # like a working sweep.
            has_email = bool(contact.get("bison_lead_id"))
            has_linkedin = bool(contact.get("heyreach_lead_id"))
            if not has_email and not has_linkedin:
                continue
            why = _must_stop(rec, contact, eligibility, executionguard)
            if not why:
                # Count even contacts that do not need stopping - they were
                # examined and found clean.
                if has_email:
                    report["checked"] += 1
                if has_linkedin:
                    report["checked"] += 1
                continue
            # A contact live on both channels gets stopped on both.
            if has_email:
                report["checked"] += 1
                try:
                    out = stop_contact(rec, contact, why,
                                       campaign=email_campaign,
                                       rows=rows, live=live, by=by)
                except (StopRefused, StopUnverified, ProviderError) as e:
                    report["failed"].append(
                        {"record": rec.get("id"),
                         "contact": contact.get("key"),
                         "channel": "email",
                         "why": why,
                         "error": f"{type(e).__name__}: {e}"[:200]})
                else:
                    entry = {"record": rec.get("id"),
                             "contact": contact.get("key"),
                             "channel": "email",
                             "why": why,
                             "status": out.get("status_after")}
                    report["already" if out.get("already")
                           else "stopped"].append(entry)
            if has_linkedin:
                report["checked"] += 1
                try:
                    out = stop_linkedin_contact(
                        rec, contact, why, campaign=linkedin_campaign,
                        rows=rows, live=live, by=by)
                except (StopRefused, StopUnverified, ProviderError) as e:
                    report["failed"].append(
                        {"record": rec.get("id"),
                         "contact": contact.get("key"),
                         "channel": "linkedin",
                         "why": why,
                         "error": f"{type(e).__name__}: {e}"[:200]})
                else:
                    entry = {"record": rec.get("id"),
                             "contact": contact.get("key"),
                             "channel": "linkedin",
                             "why": why,
                             "status": out.get("status_after")}
                    report["already" if out.get("already")
                           else "stopped"].append(entry)
    return report


def _must_stop(rec, contact, eligibility, executionguard):
    """The reason this person must receive nothing further, or None.

    Only reasons that mean DO NOT CONTACT. A step held for approval, blocked
    on lint or waiting on a delay is not a stop - those are people we have not
    written to yet, and detaching them would throw away the staging.
    """
    for reason in eligibility.must_not_contact(rec, contact):
        if reason in executionguard.SUPPRESSION_REASONS:
            return reason
    return None


def _campaign_of(rec, rows=None, requires=None):
    """The record's campaign - optionally only one that can serve a channel.

    `requires` names the provider-campaign field the CALLER needs
    (`bison_campaign_id` for email, `heyreach_campaign_id` for LinkedIn).

    WITHOUT IT THIS RETURNED THE FIRST ROW HOLDING THE RECORD, WHATEVER
    CHANNEL IT WAS FOR. A contact staged on both channels would have its
    LinkedIn stop resolved to the EMAIL campaign, which names no HeyReach
    campaign, and `stop_linkedin_contact` would raise StopRefused - "campaign
    ... names no HeyReach campaign" - about a lead that was perfectly
    stoppable through the row sitting later in the same list.

    NOT A LIVE FAILURE ON 2026-09-24, and the measurement is the reason to fix
    it rather than a reason not to: ZERO of 1,582 records sat in both an email
    row and a HeyReach row, so no stop has yet been misrouted. The 825
    enrollment across 33 seats is precisely the plan that creates the first
    records in both, and it is the plan gated on the cross-channel stop
    working.

    SKIPPING CANNOT MAKE A STOP WORSE. A row lacking the field could only ever
    produce a refusal at the next line; passing over it either finds a row
    that CAN serve the channel or returns None and refuses exactly as before.
    So this turns refusals into stops and never the reverse.
    """
    for campaign in campaigns.load() if rows is None else rows:
        if rec.get("id") in (campaign.get("record_ids") or []):
            if requires and not campaign.get(requires):
                continue
            return campaign
    return None


def _stop_event(target, contact, report, *, channel, provider, prefix):
    """Append the PROVIDER_STOP_CONFIRMED event to one record.

    One writer for both channels so the email and LinkedIn stop paths cannot
    drift in what they record or in how they key idempotency.

    `target` is whichever record object is about to be persisted - the
    in-memory `rec` when the caller owns the save, or the canonical row
    inside a transaction when it does not. `events.record` does not care
    which; the difference is entirely about who writes the file.
    """
    events.record(
        target, events.PROVIDER_STOP_CONFIRMED,
        contact_key=contact.get("key"), channel=channel,
        provider=provider,
        provider_event_id=(f"{prefix}:stop:"
                           f"{report['provider_campaign']}:"
                           f"{report['lead_id']}"),
        lead_id=report["lead_id"],
        campaign=report["provider_campaign"],
        why=report["why"],
        status=report.get("status_after"))


def _record(rec, contact, report, persist=True):
    """Write the confirmed stop through the canonical writer.

    ## `persist=False` MEANS THE CALLER OWNS THE SAVE, and it is not a tidying

    PROBLEM-REGISTER ISSUE-001. `inbound.ingest` reads
    `base = store.digest()`, builds its records, then calls
    `store.save(recs, expect_digest=base)` which REFUSES if the queue changed
    in between. This function is reached from inside that window, and opening
    its own transaction here changes the file - `store.digest()` is a content
    hash - so the outer save raises `QueueChanged` and ingest's own work is
    discarded: the REPLY_RECEIVED event, its classification, and the account
    pause.

    The stop itself survived, because this transaction committed. That is why
    the defect was narrower than first reported and also why it could not be
    fixed by simply removing the transaction: **two of the three callers have
    no save of their own.** `sweep` and the CLI reach here outside any ingest
    window, and there this commit is the only write that happens. GLM raised
    exactly that in review of the proposed fix.

    So the caller declares it. `persist=True` keeps the independent commit for
    callers that own no save. `persist=False` writes onto the in-memory record
    the caller is holding and lets their single save persist it - which is
    what ingest already does for everything else it touches.

    ## Why this goes through `events.record` rather than writing the list

    This appended to `rec["events"]` directly, and the bypass hid a bug in
    itself: `PROVIDER_STOP_CONFIRMED` was in neither `INTERNAL` nor
    `EXTERNAL`, so it was not in `events.KNOWN` and `events.record` RAISED on
    it. Nothing noticed, because nothing called `events.record`. A writer that
    goes round the door is also the reason nobody finds the door locked.

    The bypass cost more than tidiness. Events written that way carry no `id`
    and get no idempotency, so the same stop recorded twice - a re-run, a
    retry, a sweep crossing a reply - appended two identical rows that nothing
    could collapse. `provider_event_id` keys this one to the exact provider
    lead and campaign, which is what makes a repeat a no-op.
    """
    if not persist:
        _stop_event(rec, contact, report, channel="email",
                    provider="emailbison", prefix="emailbison")
        return
    with store.transaction() as rows:
        for row in rows:
            if row.get("id") != rec.get("id"):
                continue
            _stop_event(row, contact, report, channel="email",
                        provider="emailbison", prefix="emailbison")


def _record_linkedin(rec, contact, report, persist=True):
    """Write the confirmed LinkedIn stop through the canonical writer.

    `persist=False` means the caller owns the save - see `_record`, which
    carries the full argument. Kept identical to the email path on purpose:
    two stop recorders with different persistence rules is how the two drift.
    """
    if not persist:
        _stop_event(rec, contact, report, channel="linkedin",
                    provider="heyreach", prefix="heyreach")
        return
    with store.transaction() as rows:
        for row in rows:
            if row.get("id") != rec.get("id"):
                continue
            _stop_event(row, contact, report, channel="linkedin",
                        provider="heyreach", prefix="heyreach")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("record", nargs="?")
    parser.add_argument("contact", nargs="?")
    parser.add_argument("--why", default="operator")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--sweep", action="store_true",
                        help="stop everybody staged who must not be contacted")
    args = parser.parse_args(argv)

    if args.sweep:
        report = sweep(live=args.live)
        print(f"  checked {report['checked']} staged contact(s): "
              f"{len(report['stopped'])} stopped, "
              f"{len(report['already'])} already, "
              f"{len(report['failed'])} failed")
        for row in report["failed"]:
            print(f"    FAILED {row['record']}/{row['contact']}: {row['error']}")
        return 1 if report["failed"] else 0

    recs = store.load()
    rec = next((r for r in recs if r.get("id") == args.record), None)
    if rec is None:
        print(f"no record {args.record!r}")
        return 1
    contact = next((c for c in rec.get("contacts") or []
                    if c.get("key") == args.contact), None)
    if contact is None:
        print(f"no contact {args.contact!r} on {args.record!r}")
        return 1
    try:
        report = stop_contact(rec, contact, args.why, live=args.live)
    except (StopRefused, StopUnverified, ProviderError) as e:
        print(f"{type(e).__name__}: {e}")
        return 1
    print(f"  {report['status_before']!r} -> {report.get('status_after')!r}"
          f"{' (already)' if report['already'] else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
