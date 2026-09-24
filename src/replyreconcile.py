#!/usr/bin/env python3
"""Close the gap between what our store believes and what the provider does.

    py -3 -m src.replyreconcile --campaign 491            # read-only
    py -3 -m src.replyreconcile --all                     # read-only
    py -3 -m src.replyreconcile --campaign 491 --live     # stop and write back

## WHY THIS EXISTS, MEASURED 2026-09-24

Five leads carried `reply_received` AND `reply_classified` in the store -
three of them also `contact_stopped` or `company_paused` - and were still
`in_sequence` at EmailBison in campaigns 491 and 492, both ACTIVE. They were
stopped by hand. 23 of the 28 flagged records were correctly stopped, so the
ingestion path works: what was missing was anything that compares the two
pictures afterwards.

PROBLEM-REGISTER ISSUE-001 - "reply ingestion discarded the reply event" - is
fixed. This is the next link down the same chain. `leadstop.sweep` can stop
everybody who must not be contacted, and `inbound` stops a replier at the
moment the reply lands, but nothing ran on a timer and nothing ever asked the
provider whether it agreed. A stop that silently did not happen is
indistinguishable from a stop that did.

## BOTH DIRECTIONS, AND THEY ARE DIFFERENT FAULTS

**FORWARD** - our store says this person must hear nothing further and the
provider still has them sendable. That is somebody about to receive an email
after they answered. It is repaired by STOPPING them at the provider.

**REVERSE** - the provider says this person replied or bounced and our store
holds no such event. That is a reply nobody has read and a bounce nobody has
counted, and every person-level gate downstream of the event log is deciding
from a picture that is missing it. It is repaired by WRITING the event.

The two are not symmetrical and must not be collapsed into one "sync": the
forward repair writes to a provider and the reverse repair writes to the
store, and only the forward one can reach a person.

## WHAT "SENDABLE" MEANS HERE

`bison.STOPPED_STATES` is the provider's own vocabulary for a membership that
will receive nothing further. Anything else - `in_sequence`,
`sending_paused`, `never_contacted`, or a word this system has never seen -
is treated as SENDABLE. That is deliberate and it is the fail-closed
direction: `sending_paused` is the campaign's pause borrowed by the
membership and reverses the moment somebody resumes, and an unrecognised
status is not evidence of safety. A lead the provider does not hold at all
answers `None` and is not a disagreement - it is not in this campaign.

## THE WRITE SCOPE

A watcher is a reader and holds no write scope. That is deliberate: the first
blank-content halt alerted and halted nothing for exactly this reason, which
was the guard being right. So the stop opens a scope that is narrow in TIME -
one lead, one write, reopened per lead rather than held across the cycle -
and narrow in POWER: `only=STOP_ROUTES` names the one route fragment, so
enrolling, resuming, pausing a campaign and attaching leads are all outside
it and would be refused by `providers.refuse_unauthorized_write` before the
socket was opened.

Stopping can only ever mean somebody receives less. That is the whole
argument for letting a watcher do it at all, and it is why the scope may
never be widened to a verb that could mean somebody receives more.

## WHAT IT DOES NOT DO

It does not un-stop anybody, resume anything, or write an event that makes
somebody MORE contactable. It does not classify a reply: a REPLY_RECEIVED
written from a membership status carries no body, no address and no verdict,
and `replies`/`replyverdict` remain the only things that classify. It does
not reconcile LinkedIn - `heyreach.stop_lead_in_campaign` is wired and
`leadstop.stop_linkedin_contact` is its door, but its docstring still says
NEVER LIVE-VALIDATED and a reconciliation loop is not the place to find out.
It does not write a provider `unsubscribed` back into the store: that status
exists and this deliberately covers only the two the brief named, so the gap
is visible rather than half-implemented.
"""
import argparse
import sys

from . import campaigns, eligibility, events, executionguard, leadstop, store
from . import providers as _providers
from .providers import ProviderError, bison

#: The ONE route this may use, as a fragment rather than a whole URL so a host
#: change cannot silently widen or void it - the contract
#: `providers.allow_writes(only=...)` documents. It names the per-lead stop
#: and nothing else: not `/pause`, not `/resume`, not `/leads/attach-leads`,
#: not `/campaigns`.
STOP_ROUTES = ("stop-future-emails",)

#: Why our store says this person must hear nothing further. One word each,
#: because the counts are reported per reason and prose does not aggregate.
REPLIED = "replied"
STOPPED = "stopped"
UNSUBSCRIBED = "unsubscribed"
BOUNCED = "bounced"

#: `eligibility`'s reasons, mapped onto the four words above. Built from the
#: constants rather than from their spellings so the two cannot drift, and
#: derived from `executionguard.SUPPRESSION_REASONS` - the canonical set of
#: "this person must not be contacted" - rather than from a second list.
_REASON_WORD = {
    eligibility.BLOCKED_REPLIED: REPLIED,
    eligibility.BLOCKED_CONTACT_STOPPED: STOPPED,
    eligibility.BLOCKED_UNSUBSCRIBED: UNSUBSCRIBED,
    eligibility.BLOCKED_SUPPRESSED: UNSUBSCRIBED,
    eligibility.BLOCKED_CLIENT_SUPPRESSED: UNSUBSCRIBED,
    eligibility.BLOCKED_AGENCY_DNC: UNSUBSCRIBED,
    eligibility.BLOCKED_ACCOUNT_SUPPRESSED: UNSUBSCRIBED,
}

#: The provider statuses the reverse direction writes back, and the event each
#: becomes. `unsubscribed` is a provider status too and is deliberately absent
#: - see the module docstring.
_REVERSE_EVENT = {
    "replied": events.REPLY_RECEIVED,
    "bounced": events.EMAIL_BOUNCED,
}


def store_stop_reason(rec, contact):
    """The word for why this person must hear nothing further, or None.

    `eligibility.must_not_contact` is the canonical person-level predicate and
    `executionguard.SUPPRESSION_REASONS` is the canonical subset of it that
    means DO NOT CONTACT - the same pair `leadstop.sweep` asks. Re-deriving
    either here would be a second implementation of the one rule that must not
    have two.

    A BOUNCE IS ADDED, because that pair does not carry one.
    `eligibility.BLOCKED_BOUNCED` is raised by `decide` from the verification
    block and is about an ADDRESS rather than about a person, so
    `must_not_contact` never returns it - which is correct for that function
    and would be a hole here. A bounced address that the provider still has
    `in_sequence` is the same fault as a replier still in sequence: the next
    step goes out.
    """
    for reason in eligibility.must_not_contact(rec, contact):
        if reason in executionguard.SUPPRESSION_REASONS:
            return _REASON_WORD.get(reason, STOPPED)
    key = (contact or {}).get("key")
    for entry in (rec or {}).get("events") or []:
        if entry.get("type") == events.EMAIL_BOUNCED and \
                entry.get("contact") == key:
            return BOUNCED
    return None


def provider_is_sendable(status):
    """True when the provider will still work this membership through its
    sequence. `None` - the lead is not in this campaign - answers False.

    Everything that is not one of the provider's own settled words counts as
    sendable, INCLUDING a word this system has never seen. An unrecognised
    status is not evidence of safety, and a new one appeared in this estate as
    recently as 2026-09-24 (`queued_for_sending`).
    """
    if status is None:
        return False
    return str(status).lower() not in bison.STOPPED_STATES


def _leads_of(campaign_row, recs):
    """`{lead_id: (rec, contact)}` for one campaign's staged email contacts."""
    wanted = set(campaign_row.get("record_ids") or [])
    out = {}
    for rec in recs:
        if rec.get("id") not in wanted:
            continue
        for contact in rec.get("contacts") or []:
            lead_id = contact.get("bison_lead_id")
            if lead_id:
                out[int(lead_id)] = (rec, contact)
    return out


def _index_by_lead(recs):
    """`{lead_id: (rec, contact)}` over the WHOLE store.

    The reverse direction needs this rather than the campaign's own record
    list: a provider lead that replied is our person if any contact carries
    that `bison_lead_id`, whichever campaign row happens to name the record.
    Binding by the id the provider itself gave us is exact; searching by
    address and guessing is what `leadstop` refuses to do.
    """
    out = {}
    for rec in recs:
        for contact in rec.get("contacts") or []:
            lead_id = contact.get("bison_lead_id")
            if lead_id:
                out[int(lead_id)] = (rec, contact)
    return out


def _has_reverse_event(rec, contact, provider_status):
    """Does the store already hold the event the provider is asserting?"""
    key = (contact or {}).get("key")
    entries = [e for e in (rec.get("events") or []) if e.get("contact") == key]
    if provider_status == "replied":
        return any(events.is_reply(e) for e in entries)
    return any(e.get("type") == events.EMAIL_BOUNCED for e in entries)


def _stop_one(rec, contact, reason, campaign_row, rows, by):
    """Stop one person at the provider, inside a scope built for one write.

    THE SCOPE IS THE POINT, and it is copied from
    `bison_watch_loop._halt_on_blank_content` on purpose - same argument, one
    route further down. Without `only=`, this block would authorise every
    mutating route for its duration and a function believed only to stop a
    lead would be one refactor from enrolling, resuming or pausing. It is
    also opened PER LEAD rather than around the loop, so the window in which
    any write is authorised at all is one provider call wide.

    `leadstop.stop_contact` is the door: it re-reads the provider's own
    `lead_campaign_data` for this exact lead before writing, treats an
    already-stopped membership as a success with no write, enforces the
    tenancy check, goes through `providerwrites.perform` with
    `EMAIL_STOP_LEAD`, and records `PROVIDER_STOP_CONFIRMED` where the rest of
    this person's history is. Re-implementing any of that here would be a
    second stop path with different rules.
    """
    with _providers.allow_writes(
            f"reply reconciliation on EmailBison campaign "
            f"{campaign_row.get('bison_campaign_id')}: the store records "
            f"{reason!r} for lead {contact.get('bison_lead_id')} and the "
            f"provider still has them sendable",
            only=STOP_ROUTES):
        return leadstop.stop_contact(rec, contact, reason,
                                     campaign=campaign_row, rows=rows,
                                     live=True, by=by)


def _write_back(pending, by):
    """Write the provider's replies and bounces into the store. One save.

    ONE TRANSACTION FOR THE WHOLE CYCLE, because `store.save` is guarded by a
    content digest and a transaction per row would make a cycle's worth of
    repairs into a cycle's worth of chances to lose one to `QueueChanged`.

    IDEMPOTENT ON `provider_event_id`. The id names the provider, the
    campaign, the lead and the status, so the same membership read every five
    minutes for a week appends one row. That is the same key `events.record`
    already uses for a webhook delivered twice.

    NO BODY, NO ADDRESS, NO VERDICT. This event asserts only what a membership
    status can prove: that the provider recorded a reply, or a bounce, for
    this lead in this campaign. `source` says where it came from so a later
    reader can tell it apart from an ingested reply that carries words.
    """
    written = []
    if not pending:
        return written
    with store.transaction() as rows:
        by_id = {r.get("id"): r for r in rows}
        for item in pending:
            row = by_id.get(item["record"])
            if row is None:
                continue
            entry = events.record(
                row, item["event"],
                contact_key=item["contact"], channel="email",
                provider="emailbison",
                provider_event_id=("emailbison:membership:"
                                   f"{item['campaign']}:{item['lead_id']}:"
                                   f"{item['provider_status']}"),
                lead_id=item["lead_id"], campaign=item["campaign"],
                source="provider_membership_reconcile", by=by)
            if entry is not None:
                written.append(item)
    return written


def check(provider_campaign_id, membership=None, recs=None, rows=None,
          live=False, by="replyreconcile", emit=None):
    """Compare our store with provider truth for one EmailBison campaign.

    `membership` is the provider's per-lead status map. It is accepted from
    the caller because `bison_watch_loop.snapshot` has already paid for that
    walk every cycle, and two reads of the same campaign in one cycle would
    be two readers that can disagree about who is in sequence.

    `live=False` reports and writes nothing, anywhere. That is the default on
    purpose: a library that repairs by default is a library somebody imports
    and is surprised by.

    Never raises for a provider or a store failure on one lead: the failure is
    counted and reported, and the rest of the cycle continues. A reconciliation
    that dies on the first refusal reconciles one lead.
    """
    emit = emit or (lambda _line: None)
    recs = store.load() if recs is None else recs
    rows = campaigns.load() if rows is None else rows
    campaign_row = next(
        (r for r in rows
         if str(r.get("bison_campaign_id")) == str(provider_campaign_id)), None)

    report = {
        "campaign": str(provider_campaign_id),
        "live": bool(live),
        "membership_read": membership is not None,
        "forward": {"checked": 0, "disagreements": [], "stopped": 0,
                    "already": 0, "failed": []},
        "reverse": {"replied": 0, "bounced": 0, "missing": [], "written": 0,
                    "unmatched": 0, "failed": []},
        "repliers_sendable": [],
    }
    if campaign_row is None:
        report["refused"] = (
            f"no local campaign row names EmailBison campaign "
            f"{provider_campaign_id}, so there is nothing to reconcile it "
            f"against")
        return report
    if membership is None:
        # UNREADABLE IS NOT EMPTY. An absent membership answers "unknown", and
        # a reconciliation run against `{}` would report every replier as
        # correctly stopped - a false clean on the safety path, which is the
        # substitution this whole watcher exists to catch at the provider.
        try:
            membership = bison.membership(provider_campaign_id)
        except Exception as exc:                                # noqa: BLE001
            report["refused"] = (
                f"the provider membership for {provider_campaign_id} could "
                f"not be read ({type(exc).__name__}); refusing to call "
                f"anybody reconciled from a read that did not happen")
            emit(f"RECONCILE-UNREADABLE {provider_campaign_id} "
                 f"{type(exc).__name__}")
            return report
        report["membership_read"] = True
    membership = {int(k): v for k, v in (membership or {}).items()}

    _forward(report, campaign_row, recs, rows, membership, live, by, emit)
    _reverse(report, provider_campaign_id, recs, membership, live, by, emit)
    return report


def _forward(report, campaign_row, recs, rows, membership, live, by, emit):
    """Our store says stop; does the provider agree?"""
    campaign_id = campaign_row.get("bison_campaign_id")
    for lead_id, (rec, contact) in sorted(_leads_of(campaign_row, recs).items()):
        reason = store_stop_reason(rec, contact)
        if not reason:
            continue
        report["forward"]["checked"] += 1
        status = membership.get(lead_id)
        if not provider_is_sendable(status):
            if status is not None:
                report["forward"]["already"] += 1
            continue
        finding = {"record": rec.get("id"), "contact": contact.get("key"),
                   "lead_id": lead_id, "reason": reason,
                   "provider_status": status, "stopped": False}
        report["forward"]["disagreements"].append(finding)
        if reason == REPLIED:
            report["repliers_sendable"].append(finding)
        emit(f"RECONCILE-FORWARD {campaign_id} lead {lead_id} store says "
             f"{reason} provider says {status}")
        if not live:
            continue
        try:
            out = _stop_one(rec, contact, reason, campaign_row, rows, by)
        except (leadstop.StopRefused, leadstop.StopUnverified, ProviderError,
                _providers.ProviderWriteRefused) as exc:
            report["forward"]["failed"].append(
                {"lead_id": lead_id, "reason": reason,
                 "error": f"{type(exc).__name__}: {exc}"[:200]})
            emit(f"RECONCILE-STOP-REFUSED {campaign_id} lead {lead_id}: "
                 f"{type(exc).__name__}")
            continue
        finding["stopped"] = True
        finding["provider_status_after"] = out.get("status_after")
        report["forward"]["stopped"] += 1
        emit(f"RECONCILE-STOPPED {campaign_id} lead {lead_id} "
             f"{status} -> {out.get('status_after')}")


def _reverse(report, campaign_id, recs, membership, live, by, emit):
    """The provider says replied or bounced; does our store hold it?"""
    index = _index_by_lead(recs)
    pending = []
    for lead_id, status in sorted(membership.items()):
        word = str(status or "").lower()
        if word not in _REVERSE_EVENT:
            continue
        report["reverse"][word] += 1
        bound = index.get(lead_id)
        if bound is None:
            # NOT AN ERROR, AND NOT OURS TO WRITE. Most of these campaigns
            # also hold leads this system never staged; a reply from one of
            # them belongs to whoever did. Counted so the number is visible.
            report["reverse"]["unmatched"] += 1
            continue
        rec, contact = bound
        if _has_reverse_event(rec, contact, word):
            continue
        item = {"record": rec.get("id"), "contact": contact.get("key"),
                "lead_id": lead_id, "campaign": str(campaign_id),
                "provider_status": word, "event": _REVERSE_EVENT[word]}
        report["reverse"]["missing"].append(item)
        pending.append(item)
        emit(f"RECONCILE-REVERSE {campaign_id} lead {lead_id} provider says "
             f"{word} and the store holds no such event")
    if not live or not pending:
        return
    try:
        report["reverse"]["written"] = len(_write_back(pending, by))
    except Exception as exc:                                    # noqa: BLE001
        report["reverse"]["failed"].append(
            f"{type(exc).__name__}: {exc}"[:200])
        emit(f"RECONCILE-WRITEBACK-FAILED {campaign_id} {type(exc).__name__}")


# ---------------------------------------------------------------- reporting

def announce(report):
    """Post the cycle's counts, and a CRITICAL for any replier still sendable.

    Counts and ids, never a person. `notify._status_payload` REFUSES a field
    whose name or value looks like a prospect rather than stripping it, so a
    field added here carelessly fails loudly instead of reaching the channel
    with the widest audience in the product.

    TWO POSTS, AND THE ORDER MATTERS. The CRITICAL goes first: a notification
    that cannot be built must not be able to swallow the finding, and the
    counts line is the less important of the two by a distance.

    ## The counts go to the status feed at INFO

    `STATUS_CHECKPOINT` routes `(STATUS, INFO)` - the daily operations feed -
    and carries counts only by construction.

    ## What "per cycle" means, and why it is not one post every five minutes

    The notification id is built from the campaign, the UTC day and the COUNTS
    THEMSELVES. So a cycle whose picture is identical to the last one lands on
    the same id and writes nothing, and a cycle whose picture MOVED posts a
    new line. Every cycle is reported; an unchanged cycle is reported by the
    line that is already there.

    That is this repository's watcher convention - silence means unchanged,
    never dead - and it is also what keeps the feed readable: nine campaigns
    at a 300s interval would otherwise be 2,592 identical lines a day, and a
    channel nobody reads is a channel the CRITICAL is lost in.

    ## The CRITICAL

    `REPLY_PROTECTION_FAILED` routes `(GLOBAL, CRITICAL)`. It is the existing
    verb for "somebody replied and may still receive the next step", raised by
    `replywatch` when polling dies and by `reply_watch_loop` when a stop is
    refused. A replier the provider still calls sendable is the same fact
    arriving by a different route, and giving it a new name would split one
    incident across two alerts.

    It is raised on DISCOVERY and carries whether the stop then succeeded,
    rather than being conditional on the stop failing. The blank-content halt
    settled that argument: a repair that refuses must not swallow the finding.
    """
    from . import notify

    campaign = report.get("campaign")
    forward, reverse = report["forward"], report["reverse"]
    for finding in report.get("repliers_sendable") or []:
        notify.notify(
            notify.REPLY_PROTECTION_FAILED, None,
            fields={"campaign": campaign,
                    "lead_id": finding.get("lead_id"),
                    "store_says": finding.get("reason"),
                    "provider_says": finding.get("provider_status"),
                    "stopped_by_reconciliation":
                        "yes" if finding.get("stopped") else "NO",
                    "action": "this person replied and the provider still "
                              "has them sendable. If the stop did not land, "
                              "stop them by hand and read provider truth "
                              "before anything else is sent"},
            ids={"campaign_id": campaign,
                 "lead_id": str(finding.get("lead_id")),
                 "check": "reply_reconcile"})
    notify.notify(
        notify.STATUS_CHECKPOINT, None,
        fields={"check": "reply reconciliation",
                "campaign": campaign,
                "store_says_stop": forward["checked"],
                "provider_still_sendable": len(forward["disagreements"]),
                "stopped_by_reconciliation": forward["stopped"],
                "stops_refused": len(forward["failed"]),
                "provider_replied": reverse["replied"],
                "provider_bounced": reverse["bounced"],
                "events_missing_from_store": len(reverse["missing"]),
                "events_written_back": reverse["written"],
                "provider_leads_we_never_staged": reverse["unmatched"],
                "mode": "live" if report.get("live") else "read-only"},
        ids={"campaign_id": campaign, "check": "reply_reconcile",
             "day": str(store.now())[:10],
             # THE COUNTS ARE PART OF THE ID. See the docstring: this is what
             # makes an unchanged cycle silent and a changed one loud.
             "picture": "%s/%s/%s/%s/%s" % (
                 forward["checked"], len(forward["disagreements"]),
                 forward["stopped"], len(reverse["missing"]),
                 reverse["unmatched"])})
    return report


def line(report):
    """One human-readable line. Ids and counts; never a person."""
    forward, reverse = report["forward"], report["reverse"]
    if report.get("refused"):
        return f"RECONCILE {report['campaign']} REFUSED: {report['refused']}"
    return (f"RECONCILE {report['campaign']} "
            f"forward {len(forward['disagreements'])}/{forward['checked']} "
            f"disagree (stopped {forward['stopped']}, "
            f"refused {len(forward['failed'])}, "
            f"already {forward['already']}) "
            f"reverse {len(reverse['missing'])} missing of "
            f"{reverse['replied']} replied + {reverse['bounced']} bounced "
            f"(written {reverse['written']}, "
            f"unmatched {reverse['unmatched']})")


def campaign_ids(rows=None):
    """Every EmailBison campaign this system has a row for, in provider order.

    NUMERICALLY BY PROVIDER ID, never by `created_at`: that column is null on
    the campaigns that actually send, which is recorded in the register and
    has produced a wrong ordering here before.
    """
    rows = campaigns.load() if rows is None else rows
    ids = {int(r["bison_campaign_id"]) for r in rows
           if str(r.get("bison_campaign_id") or "").strip().isdigit()}
    return sorted(ids)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--campaign", type=int, action="append", default=None)
    parser.add_argument("--all", action="store_true",
                        help="every EmailBison campaign this system has a "
                             "campaign row for")
    parser.add_argument("--live", action="store_true",
                        help="stop at the provider and write events back")
    parser.add_argument("--announce", action="store_true",
                        help="also plan the notifications")
    args = parser.parse_args(argv)

    from .providers import load_env
    load_env()

    wanted = args.campaign or (campaign_ids() if args.all else None)
    if not wanted:
        parser.error("name --campaign, or --all")

    recs, rows = store.load(), campaigns.load()
    worst = 0
    for provider_id in wanted:
        report = check(provider_id, recs=recs, rows=rows, live=args.live,
                       emit=lambda l: print("   ", l, flush=True))
        print(line(report), flush=True)
        if args.announce:
            announce(report)
        if report.get("refused"):
            worst = max(worst, 1)
        if report["forward"]["disagreements"] or report["reverse"]["missing"]:
            worst = max(worst, 2)
    return worst


if __name__ == "__main__":
    sys.exit(main())
