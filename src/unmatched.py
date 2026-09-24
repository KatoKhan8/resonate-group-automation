#!/usr/bin/env python3
"""An inbound event we could not match: whose campaign is it, and who is told.

## The failure this exists to end

Between 2026-09-22 and 2026-09-24 `#resonate-notifications` received 102
`UNMATCHED REPLY NEEDS REVIEW` posts. Every one of them carried the same five
fields - provider, `status: unmatched`, `why: no record for this event`,
`held: 0`, and a sentence saying a person decides - and named nothing at all.
No campaign, no lead, no event type, no time. An alert with nothing in it to
act on is noise, and noise is how a real CRITICAL gets missed.

Three separate faults produced it, and each is fixed here:

1. **NOTHING ASKED WHOSE CAMPAIGN IT WAS.** Both provider credentials are
   workspace-wide and the client runs their own outreach in the same two
   accounts. On 2026-09-24, 806 of the 841 EmailBison events after midnight
   were on the client's own campaigns 327, 328 and 352. An event on somebody
   else's campaign is not an unmatched reply; it is not our event.

2. **THE ONE ATTRIBUTION THAT EXISTED COMPARED THE WRONG NAMESPACE.**
   `inbound._positively_not_ours` tested an event's `external_campaign_id`
   against a set built from HeyReach campaign ids only. An EmailBison event on
   OUR campaign 491 is not in `{594061, 599020, 604869, 605487, 605732, ...}`,
   so it read as "positively not ours" and would have been DROPPED SILENTLY.
   It has never fired only because the ownership readback has been stale for
   32 hours and the function refuses while it cannot prove it is current - a
   silent drop of our own replies, held off by an unrelated timer. Campaign
   ids are per provider and are compared per provider here.

3. **SEAT ATTRIBUTION NO LONGER ANSWERS THE QUESTION.** TASK-238 dropped a
   HeyReach event on a seat we do not operate, measured when we ran 1 of 41
   seats. We now run 33 of 41, because the B1 campaigns were added to the
   CLIENT'S OWN seats - and the client's campaigns still run on those same
   seats. Sampled 2026-09-24: every conversation on our seats resolved, by
   `GetCampaignsForLead`, to the client's campaigns and to none of ours.
   **A seat is not a campaign**, so a seat can still prove an event is not
   ours and can no longer prove that it is.

## The rule

    campaign id present, in OUR registry for that provider   -> OURS
    campaign id present, in none of our campaigns            -> THEIRS
    no campaign id, lookup refused, lookup empty             -> UNATTRIBUTED

`OURS` and `UNATTRIBUTED` reach the channel, batched into one digest per hour.
`THEIRS` reaches the ledger and nothing else.

**UNATTRIBUTED IS KEPT, ALWAYS.** It is the whole of TASK-238's fail-closed
rule and it is not weakened: an absence of evidence is never a drop, a lookup
that raises is never a drop, and an empty answer is never a drop. What changed
is only what a kept event COSTS - a row in an hourly digest instead of a post
of its own.

`THEIRS` is the one place a drop is decided, and it rests on our own canonical
state (`work/campaigns.jsonl`) rather than on a provider readback that expires.
The residual risk is a campaign of ours that state does not name yet; the
digest carries the count of suppressed client events and the ledger carries
every id, so the answer to "did you throw one of ours away" is a file rather
than a shrug.

## No provider call on the ingest path

`record()` writes what the event already carries and performs no I/O.
`flush()` resolves attribution and builds the digest, on the reply watcher's
own thread, after the poll. So a lookup that hangs cannot delay a pause, and
`inbound.handle` keeps exactly the shape it had.

  python -m src.unmatched --status
  python -m src.unmatched --once
"""
import argparse
import collections
import datetime
import os
import sys

from . import campaigns as campaignstate
from . import notify, store

# --------------------------------------------------------------- verdicts

#: On a campaign this system runs. The alert that matters.
OURS = "ours"
#: On a campaign that is in neither provider registry of ours. Ledger only.
THEIRS = "theirs"
#: We cannot say. Kept, digested, and never dropped.
UNATTRIBUTED = "unattributed"

VERDICTS = (OURS, THEIRS, UNATTRIBUTED)

#: Which field on a campaign row carries each provider's own campaign id.
#: The whole point of this table is that the two are NEVER compared to each
#: other - fault 2 in the module docstring was one namespace tested against
#: the other's ids.
CAMPAIGN_ID_FIELD = {
    "emailbison": "bison_campaign_id",
    "heyreach": "heyreach_campaign_id",
}

PROVIDERS = tuple(sorted(CAMPAIGN_ID_FIELD))

#: The HeyReach readback, which names campaigns `work/campaigns.jsonl` does
#: not - the 33 B1 seat campaigns were created by a script that never wrote a
#: campaign row. Unioned in as a FLOOR and read regardless of its age: a stale
#: readback can only have MISSED a campaign of ours, never invented one, so
#: adding it can only ever move an event from THEIRS to OURS.
_READBACK_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs", "state", "PROVIDER-CAMPAIGNS.json")


def _readback_campaigns(path=None):
    """`{heyreach_id: name}` the provider confirmed are ours, at any age."""
    import contextlib
    import json
    try:
        with open(path or _READBACK_FILE, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    out = {}
    for row in ((data or {}).get("heyreach") or {}).get(
            "resonate_campaigns") or []:
        cid = row.get("heyreach_campaign_id")
        if cid is None:
            continue
        with contextlib.suppress(TypeError, ValueError):
            out[int(cid)] = row.get("name") or ""
    return out


def registry(rows=None, readback=None):
    """Every campaign this system runs, per provider, as `{id: name}`.

    Built from `work/campaigns.jsonl` - the canonical campaign state, written
    when we create a campaign - and unioned with the provider readback. Our
    own state is authoritative for the NAME; the readback only ever adds ids.
    """
    out = {provider: {} for provider in PROVIDERS}
    for row in (rows if rows is not None else campaignstate.load()):
        for provider, field in CAMPAIGN_ID_FIELD.items():
            cid = row.get(field)
            if cid is None:
                continue
            try:
                out[provider][int(cid)] = row.get("name") or ""
            except (TypeError, ValueError):
                continue
    confirmed = _readback_campaigns() if readback is None else readback
    for cid, name in confirmed.items():
        out["heyreach"].setdefault(cid, name)
    return out


# ------------------------------------------------------------- attribution

def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _handle(url):
    """The profile handle from a LinkedIn URL, or None. Never the whole URL."""
    text = str(url or "").strip().rstrip("/")
    if not text:
        return None
    return text.rsplit("/", 1)[-1] or None


def _domain(address):
    """The domain half of an address. THE LOCAL PART IS NEVER RETURNED.

    A prospect's mailbox name is the prospect. The domain says which company
    answered, which is what an operator needs to decide anything, and it is
    the most that may appear in an alert.
    """
    text = str(address or "").strip().lower()
    return text.rsplit("@", 1)[-1] if "@" in text else None


def subject_of(event):
    """The lead an event is about: a domain, or a LinkedIn handle. Never both
    and never the message."""
    return _domain(event.get("email")) or _handle(event.get("linkedin"))


def campaign_of(event):
    """The campaign id ON THE EVENT ITSELF, as an int, or None.

    EmailBison puts it on every reply row. HeyReach's inbox carries none: a
    conversation object has `linkedInAccountId` and no campaign at all, which
    is why `lookup` below exists.
    """
    return _int(event.get("external_campaign_id"))


def heyreach_lookup(profile_url):
    """`{campaign_id: name}` for every campaign HeyReach says this lead is in.

    `POST /campaign/GetCampaignsForLead`, a READ. TASK-238 concluded that
    campaign-level attribution was impossible on this provider, and it was
    measuring the wrong route: `GetConversationsV2` carries no campaign, and
    this one carries every campaign the lead is in, with its name and the
    lead's status in it. Measured 2026-09-24 against live conversations: 5 to
    18 campaigns per lead, and on the sample every one of them the client's.

    **IT MAY RAISE, AND THAT IS DELIBERATE.** The catch is in `attribute`,
    once, where the decision is made - so it can be broken by a mutation and
    caught by a test. A second catch here would be untestable in exactly the
    way `notify`'s duplicated idempotency check was.
    """
    from .providers import heyreach
    rows, _total = heyreach.campaigns_for_lead(profile_url=profile_url)
    found = {}
    for row in rows or []:
        cid = _int(row.get("campaignId"))
        if cid is not None:
            found[cid] = row.get("campaignName") or ""
    return found


def attribute(row, known=None, lookup=heyreach_lookup):
    """One ledger row -> `(verdict, campaign_id, campaign_name, why)`.

    `lookup` is injected so the decision is testable without a transport, and
    defaults to the live read. Passing `lookup=None` disables the lookup
    entirely, which is what the dry replay uses when it has no credentials.
    """
    known = registry() if known is None else known
    provider = row.get("provider")
    mine = known.get(provider) or {}

    cid = _int(row.get("campaign_id"))
    if cid is not None:
        if cid in mine:
            return OURS, cid, mine[cid], "the event names a campaign we run"
        # AN EMPTY REGISTRY PROVES NOTHING. "This id is in none of our
        # campaigns" and "we could not read our campaigns" are the same
        # expression and must never be the same answer: a provider nobody has
        # registered, or a `campaigns.jsonl` that would not parse, would
        # otherwise make EVERY event on that provider somebody else's. Same
        # argument as REFUSED IS NOT ROOM.
        if not mine:
            return (UNATTRIBUTED, cid, None,
                    f"the event names campaign {cid}, and we hold no campaign "
                    f"registry for {provider} to compare it against")
        return (THEIRS, cid, None,
                f"the event names campaign {cid}, which is in no campaign of "
                f"ours on {provider}")

    if provider != "heyreach" or not row.get("profile_url") or lookup is None:
        return (UNATTRIBUTED, None, None,
                "the event carries no campaign id and none can be looked up")

    # THE ONLY CATCH, AND IT FAILS OPEN. A lookup that raises, times out or
    # is rate-limited leaves the event exactly as it was found - TASK-238
    # invariant 3, and the criterion that task said a fix must not fail.
    # Broad on purpose and classified rather than swallowed: the reason
    # travels into the digest so an operator can see WHY it is unresolved.
    try:
        found = lookup(row["profile_url"])
    except Exception as exc:                                  # noqa: BLE001
        return (UNATTRIBUTED, None, None,
                f"the campaign lookup did not answer "
                f"({type(exc).__name__}: {exc})"[:200])
    if not found:
        return (UNATTRIBUTED, None, None,
                "the campaign lookup returned no campaign for this lead")
    ours = sorted(set(found) & set(mine))
    if ours:
        return (OURS, ours[0], mine[ours[0]],
                f"this lead is in {len(found)} campaigns, {len(ours)} of them "
                f"ours")
    if not mine:                                   # see the same test above
        return (UNATTRIBUTED, sorted(found)[0], None,
                f"this lead is in {len(found)} campaigns, and we hold no "
                f"campaign registry for {provider} to compare them against")
    return (THEIRS, sorted(found)[0], None,
            f"this lead is in {len(found)} campaigns and none of them is ours")


# ------------------------------------------------------------- the ledger
#
# One row per unmatched event, appended at ingest and resolved at flush. It is
# the answer to "what did you not tell me about", which an alert that was
# never posted cannot answer on its own.

LEDGER_VAR = "UNMATCHED_LEDGER"


def path():
    return os.path.abspath(os.environ.get(LEDGER_VAR)
                           or os.path.join(os.path.dirname(store.queue_path()),
                                           "unmatched-ledger.jsonl"))


def load():
    return store.read_jsonl(path())


def save(rows, timeout=None):
    with store.lock(timeout, for_path=path()):
        store.write_jsonl(path(), rows)


def transaction(timeout=None):
    return store.file_transaction(path(), timeout)


def hour_of(stamp):
    """The UTC hour a timestamp falls in, as `2026-09-24T17`.

    The digest's window and its notification id are both built from this, so
    a poll at 17:00:03 and another at 17:59 land in one digest and produce one
    notification - the same reasoning as `digestwatch`'s anchored boundary.
    """
    at = _parse(stamp)
    return None if at is None else at.strftime("%Y-%m-%dT%H")


def _parse(stamp):
    if isinstance(stamp, datetime.datetime):
        at = stamp
    else:
        try:
            at = datetime.datetime.fromisoformat(
                str(stamp).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    return at if at.tzinfo else at.replace(tzinfo=datetime.timezone.utc)


def record(event, why=None, held=0, at=None):
    """One unmatched event, written down. No provider call, never raises.

    What is stored is what an alert is allowed to say: ids, a campaign id, the
    lead's DOMAIN or LinkedIn handle, the event type, the time. The message
    body is not stored and is not passed in - `inbound` holds the text for
    classification and this is not classification.
    """
    try:
        stamp = at or event.get("at") or store.now()
        row = {
            "at": str(stamp),
            "hour": hour_of(stamp) or hour_of(store.now()),
            "provider": event.get("provider"),
            "provider_event_id": event.get("provider_event_id"),
            "event_type": event.get("type"),
            "campaign_id": campaign_of(event),
            "lead": subject_of(event),
            "profile_url": event.get("linkedin"),
            "held": int(held or 0),
            "why": why or "no record for this event",
            "verdict": None,
            "campaign_name": None,
            "verdict_why": None,
            "digest": None,
        }
        with transaction() as current:
            if any(r.get("provider_event_id") == row["provider_event_id"]
                   and row["provider_event_id"] for r in current):
                return None
            current.append(row)
        return row
    except Exception:                                         # noqa: BLE001
        # Same contract as `notify.notify`: the ledger may never break ingest.
        # The pause, the classification and the stop have already happened.
        return None


# -------------------------------------------------------------- the digest

#: How many individual rows a digest prints before it stops and points at the
#: ledger. A digest is a thing somebody reads in one glance; past this it is a
#: file, and the file is named in the payload.
MAX_ROWS = 20


def pending(rows=None, now=None):
    """Ledger rows in hours that have CLOSED and have no digest yet.

    The current hour is excluded on purpose: digesting it would post a partial
    hour and then be unable to post the rest, because the notification id is
    the hour and the second one would deduplicate onto the first.
    """
    current = hour_of(now or store.now())
    out = collections.defaultdict(list)
    for row in (rows if rows is not None else load()):
        hour = row.get("hour")
        if not hour or hour >= current or row.get("digest"):
            continue
        out[hour].append(row)
    return dict(out)


def _line(row):
    """One event, naming its object. NEVER the message body."""
    return (f"{row.get('provider')} campaign "
            f"{row.get('campaign_id') or 'unknown'}"
            f"{' ' + row['campaign_name'] if row.get('campaign_name') else ''}"
            f" | lead {row.get('lead') or 'unknown'}"
            f" | {row.get('event_type')}"
            f" | {row.get('provider_event_id')}"
            f" | {row.get('at')}")


def summarise(hour, rows):
    """The digest payload for one hour, or None when it has no rows to carry.

    `None` is the "a digest with zero rows is not posted" rule, and it is
    decided HERE and nowhere else so that a mutation to it fails a test.
    Client-attributed events are counted in the payload and never listed: the
    count is what tells an operator the suppression is working, and the ids
    are in the ledger for the one day somebody has to check it.
    """
    reportable = [r for r in rows if r.get("verdict") in (OURS, UNATTRIBUTED)]
    theirs = [r for r in rows if r.get("verdict") == THEIRS]
    if not reportable:
        return None

    by_campaign = collections.Counter()
    for row in reportable:
        if row.get("verdict") == OURS:
            by_campaign[f"{row.get('provider')} {row.get('campaign_id')} "
                        f"{row.get('campaign_name') or ''}".strip()] += 1
        else:
            by_campaign[f"{row.get('provider')} unattributed"] += 1
    by_provider = collections.Counter(r.get("provider") for r in reportable)

    shown = sorted(reportable, key=lambda r: str(r.get("at")))[:MAX_ROWS]
    payload = {
        "window": f"{hour}:00Z to {hour}:59Z",
        "unmatched": len(reportable),
        "on_our_campaigns": sum(1 for r in reportable
                                if r.get("verdict") == OURS),
        "unattributed": sum(1 for r in reportable
                            if r.get("verdict") == UNATTRIBUTED),
        "client_events_not_posted": len(theirs),
        "by_provider": dict(sorted(by_provider.items())),
        "by_campaign": [f"{name}: {count}"
                        for name, count in sorted(by_campaign.items())],
        "events": [_line(row) for row in shown],
        "action": ("open each event in the provider's inbox and decide who it "
                   "belongs to; nothing is auto-attributed. The full list, "
                   "client events included, is work/unmatched-ledger.jsonl"),
    }
    if len(reportable) > len(shown):
        payload["events"].append(
            f"... and {len(reportable) - len(shown)} more, in "
            f"work/unmatched-ledger.jsonl")
    return payload


def flush(now=None, rows=None, known=None, lookup=heyreach_lookup,
          post=True):
    """Resolve every closed hour and raise at most one digest per hour.

    Returns a list of `{hour, unmatched, theirs, notification, posted}`, one
    per hour considered - including the hours that produced nothing, because
    "we looked and there was nothing to say" is the result that proves the
    suppression is working rather than the watcher being dead.

    `post=False` resolves and records without building a notification. That
    is what the replay uses, and it is the only reason the flag exists.
    """
    known = registry() if known is None else known
    cache, results, settled = {}, [], {}

    # The rows are resolved IN PLACE. A caller that passed its own list gets
    # the verdicts back on the objects it handed over - which is what makes
    # the replay able to report an attribution summary without the ledger
    # being involved at all.
    for hour, batch in sorted(pending(rows=rows, now=now).items()):
        for row in batch:
            key = (row.get("provider"), row.get("campaign_id"),
                   row.get("profile_url"))
            if key not in cache:
                cache[key] = attribute(row, known=known, lookup=lookup)
            verdict, cid, name, why = cache[key]
            row.update(verdict=verdict, campaign_id=cid, campaign_name=name,
                       verdict_why=why)
            # Keyed on the provider's own id, and only when there is one. A
            # `None` key would match every OTHER id-less row on write-back
            # and stamp them all with this one's verdict.
            if row.get("provider_event_id"):
                settled[row["provider_event_id"]] = row

        payload = summarise(hour, batch)
        row_id = None
        if payload and post:
            planned = notify.notify(
                notify.UNMATCHED_DIGEST, None, fields=payload,
                ids={"hour": hour})
            row_id = (planned or {}).get("id")
        results.append({
            "hour": hour,
            "unmatched": (payload or {}).get("unmatched", 0),
            "theirs": sum(1 for r in batch if r["verdict"] == THEIRS),
            "notification": row_id,
            "posted": bool(payload),
        })
        for row in batch:
            row["digest"] = row_id or hour

    if settled and rows is None:
        with transaction() as current:
            for i, row in enumerate(current):
                identifier = row.get("provider_event_id")
                done = settled.get(identifier) if identifier else None
                if done is not None:
                    current[i] = done
    return results


# ------------------------------------------------------------------- CLI

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--once", action="store_true",
                        help="resolve every closed hour and raise its digest")
    parser.add_argument("--status", action="store_true",
                        help="what is in the ledger, by verdict")
    parser.add_argument("--no-lookup", action="store_true",
                        help="never ask a provider; everything unresolvable "
                             "stays UNATTRIBUTED")
    args = parser.parse_args(argv)

    if args.once:
        for result in flush(lookup=None if args.no_lookup else heyreach_lookup):
            print(f"{result['hour']}  unmatched={result['unmatched']}  "
                  f"client={result['theirs']}  "
                  f"{'posted ' + str(result['notification']) if result['posted'] else 'nothing to post'}")
        return 0

    rows = load()
    counts = collections.Counter(r.get("verdict") or "unresolved" for r in rows)
    print(f"{len(rows)} rows in {path()}")
    for verdict, count in sorted(counts.items()):
        print(f"  {verdict}: {count}")
    return 0


if __name__ == "__main__":                                # pragma: no cover
    sys.exit(main())
