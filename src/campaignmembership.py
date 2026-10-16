#!/usr/bin/env python3
"""Does this contact hold a lead row in a campaign that is not ours? READ ONLY.

## THE RULE THIS EXISTS TO MAKE ASKABLE

CLAUDE.md standing rule 2 and `docs/OPERATING-MODE.md` both say it:

    anyone with a lead row in 327/328/352 is NOT CLEAN for outreach,
    whoever owns them

and UNKNOWN ownership means do-not-touch and members NOT CLEAN. Measured
2026-10-16 and recorded in `CANARY-01-PREFLIGHT-2026-10-16.md`: **nothing in
`eligibility`, `suppression`, `hygiene` or `channels` asked it.** A member of
274, 327, 328 or 352 passed every one of the twenty-two preflight rules.

`providerwrites.classify_campaign` is not that rule and never was. It answers
*may we WRITE to this campaign*, which is a different question wearing the
same vocabulary: it classifies a DESTINATION, and nothing classifies a
CONTACT. This module holds the half that was missing - the lead rows - and
hands the classification back to `providerwrites`, which owns it.

## WHAT THIS MODULE DOES NOT DO

It makes **no provider call**. It cannot: the lead rows of forty campaigns
are a paginated provider read, and the only honest answer without one is
UNKNOWN. So this reads an authority a separate, already-existing, read-only
command produces, and every function here refuses rather than guesses when
that file is not there.

It also never decides ownership. `declared_internal` and the ledger decide
that, through `providerwrites.classify_campaign`, and the `owner` field this
authority carries is **ignored on purpose** - see THE FIELD WE IGNORE below.

## THE AUTHORITY, AND THE COMMAND THAT PRODUCES IT

    py -3 scripts/build_collision_index.py

writes `collision-index.json` beside the queue - gitignored, because it is
tens of thousands of real people. That script already exists, already reads
every lead of every campaign from the providers, and already records a walk
that did not finish. Nothing new has to be built to produce this authority;
it has to be RUN, on the main checkout, by somebody allowed to make a
provider read.

The shape this module requires of it:

    {
     "generated_at": "<ISO-8601 UTC>",     the read's own timestamp
     "source":       "<where it was read>",
     "campaigns": {"<provider campaign id>": {
                      "leads_read":     <int>,
                      "complete":       <bool>,
                      "leads_reported": <int>}},     see PROVEN COMPLETE
     "incomplete": [{"campaign": <id>, "why": "<...>"}],
     "by_email":   {"<address>": {"touches": [{"campaign": <id>, ...}]}}
    }

One record per lead row, keyed by address, each naming the campaign it was
read from, under one timestamp for the whole read.

## PROVEN COMPLETE, AND WHY `complete: true` IS NOT IT

`senderheadroom`'s rule, which this project already pays for twice over: a
walk can only UNDERCOUNT, so FULL is provable from any walk and ROOM is
provable only from a complete one. A non-match is the ROOM answer here.

`build_collision_index._walk_campaign_leads` sets `complete = False` **only
in its `except` branch**. It calls

    page_rows, _total = bison._paged(..., cap=bison.CAMPAIGN_QUEUE_PAGE_CAP)

and throws the provider's own total away - the `_total` on that line is
discarded at `scripts/build_collision_index.py:73`. So if `_paged` stops
quietly at its cap rather than raising, a truncated walk is recorded
`complete: true` and nothing anywhere can tell. **Which of the two it does is
a fact in `src/providers/bison.py`, which the lane that wrote this file was
forbidden to open**, so it is treated as the unsafe case:

    PROVEN COMPLETE  =  complete is True
                        AND leads_reported is an int
                        AND leads_read >= leads_reported
                        AND the campaign is not named in `incomplete`

`leads_reported` does not exist in the authority today, so every campaign is
PARTIAL today, and this module says so by name rather than by mood. The fix
is one line in the producer - keep `_total` instead of discarding it - and it
is NOT made here, because a change to a provider-reading script cannot be
verified by a lane that may not make a provider read. Code written is not
FIXED.

## WHAT PARTIAL COSTS, AND WHAT IT DOES NOT

A PARTIAL walk makes a NON-MATCH unanswerable. It does not make a MATCH
unanswerable: a lead row that was read is a lead row that exists. So this
module is useful before the producer is fixed - it can still EXCLUDE - and
it cannot clear anybody until it is.

## THE FIELD WE IGNORE, AND IT IS A MEASUREMENT

The authority carries `owner`, set by

    CLIENT_EMAIL_CAMPAIGNS = {327, 328, 352, 418}
    owner = "client" if int(cid) in CLIENT_EMAIL_CAMPAIGNS else "ours"

at `scripts/build_collision_index.py:43`, and read at `:109` and `:131`.
Line numbers checked by reading the file, not by memory. That is a retyped
literal, and it disagrees with `config/internal-campaigns.txt` - the only
place ownership is declared - in BOTH directions:

    274   DECLARED INTERNAL          the index labels it owner="ours"
    418   not declared at all        the index labels it owner="client"

CLAUDE.md is explicit that the provider cannot be asked who owns a campaign -
no owner, creator, user, team or tenant field, confirmed across all 29
listing keys - so `owner` here is a hint with no referential integrity.
**Every campaign id is therefore re-classified through
`providerwrites.classify_campaign`, and `owner` is never read.** Naming the
three ids in this module would be the same defect one file along.
"""
import json
import os

from . import store


class MembershipUnreadable(Exception):
    """The lead-row authority is absent, unparseable or not of this shape.

    IT RAISES, and that is the whole difference between this reader and the
    ones on the send path. `agencydnc.load` answers `{}` for a missing file
    because it must not take the estate down on a damaged byte; this module
    has no send-path caller and exists to answer a preflight question, where
    "I could not look" and "nobody is in there" must never be the same
    answer.
    """


#: The exact command, and it is not this lane's to run.
HOW_TO_PRODUCE = (
    "run `py -3 scripts/build_collision_index.py` from the MAIN checkout, "
    "which walks every lead of every campaign at the providers read-only and "
    "writes the authority beside the queue")

#: Every key this module requires, with what each is for. A file missing any
#: one of them is UNREADABLE rather than empty: a listing without
#: `by_email` is not a listing of nobody.
REQUIRED_KEYS = {
    "generated_at": "the read's own timestamp - a listing with no time "
                    "cannot be judged fresh or stale",
    "campaigns": "one entry per campaign walked, with its own completeness",
    "by_email": "the lead rows themselves, keyed by address",
}


def path():
    """The authority's absolute path. Resolved per call, never cached.

    Beside the queue rather than beside the repository, the same discipline
    `agencydnc.path()` uses and for the same reason: it is real people, it is
    gitignored, and it moves with the rest of the state when
    `store.use_directory` moves it. No environment override of its own -
    following `queue_path()` is what makes it move for free.
    """
    return os.path.abspath(
        os.path.join(os.path.dirname(store.queue_path()),
                     "collision-index.json"))


def load(file_path=None):
    """The authority, validated. RAISES rather than answering emptily."""
    file_path = file_path or path()
    if not os.path.exists(file_path):
        raise MembershipUnreadable(
            "%s does not exist. The lead-row listing is the only thing that "
            "can answer whether a contact holds a row in a campaign that is "
            "not ours, and an absent listing is not an empty one: %s"
            % (file_path, HOW_TO_PRODUCE))
    try:
        with open(file_path, encoding="utf-8") as handle:
            index = json.load(handle)
    except (OSError, ValueError) as exc:
        raise MembershipUnreadable(
            "%s could not be read (%s: %s)"
            % (file_path, type(exc).__name__, str(exc)[:160])) from None
    if not isinstance(index, dict):
        raise MembershipUnreadable(
            "%s does not hold an object at its top level" % (file_path,))
    missing = sorted(k for k in REQUIRED_KEYS if k not in index)
    if missing:
        raise MembershipUnreadable(
            "%s is missing %s. %s"
            % (file_path, ", ".join("`%s` (%s)" % (k, REQUIRED_KEYS[k])
                                    for k in missing), HOW_TO_PRODUCE))
    for key in ("campaigns", "by_email"):
        if not isinstance(index[key], dict):
            raise MembershipUnreadable(
                "%s: `%s` is not an object" % (file_path, key))
    if not isinstance(index.get("incomplete", []), list):
        raise MembershipUnreadable(
            "%s: `incomplete` is not a list" % (file_path,))
    return index


def records(index):
    """How many lead-row records the listing holds. The authority's count."""
    return len(index.get("by_email") or {})


def campaign_key(value):
    """One canonical spelling of a provider campaign id, or None.

    `327`, `"327"`, `" 0327"` and `327.0` are one campaign. Delegated to
    `providerwrites` so there is exactly one answer in the codebase to what a
    provider campaign id is.
    """
    from . import providerwrites
    return providerwrites._provider_key(value)


def proven_complete(index, campaign):
    """(bool, why). A walk this listing PROVES covered that campaign.

    FOUR CONDITIONS, and the third is the one the producer cannot satisfy
    yet. See PROVEN COMPLETE in the module docstring: `complete: true` means
    only that nothing raised.
    """
    key = campaign_key(campaign)
    row = (index.get("campaigns") or {}).get(str(key))
    if row is None:
        return False, ("campaign %s was never walked - it has no entry in "
                       "the listing at all" % (key,))
    if not isinstance(row, dict):
        return False, "campaign %s has a malformed entry" % (key,)
    named = [e for e in (index.get("incomplete") or [])
             if isinstance(e, dict) and campaign_key(e.get("campaign")) == key]
    if named:
        return False, ("the listing names campaign %s as incomplete: %s"
                       % (key, "; ".join(str(e.get("why")) for e in named)))
    if row.get("complete") is not True:
        return False, ("campaign %s records complete=%r"
                       % (key, row.get("complete")))
    reported, read = row.get("leads_reported"), row.get("leads_read")
    if not isinstance(reported, int) or isinstance(reported, bool):
        return False, (
            "campaign %s records no `leads_reported`, so there is nothing to "
            "compare its %r read rows against. `complete` here means only "
            "that no exception was raised, and the provider's own total is "
            "discarded at scripts/build_collision_index.py:73 - so a walk "
            "truncated at the page cap is indistinguishable from a finished "
            "one" % (key, read))
    if not isinstance(read, int) or read < reported:
        return False, ("campaign %s read %r of %r reported rows"
                       % (key, read, reported))
    return True, ("campaign %s: %d of %d rows, walk complete"
                  % (key, read, reported))


def covers_channel(index, channel):
    """(bool, why). Did this listing walk the channel being asked about?

    HEYREACH IS NOT WALKED. `build_collision_index` records
    `{"read": false, "why": ...}` for it and says why in its own source: it
    timed out on 2026-09-30 and EmailBison was done first. So the linkedin
    answer is UNKNOWN by coverage, not by absence of members - which is a
    live concern in this estate rather than a hypothetical, because the
    LinkedIn canary is one of the things waiting on this gate.
    """
    if channel == "email":
        if not (index.get("campaigns") or {}):
            return False, ("the listing walked no campaign at all, so it "
                           "cannot answer for the email channel")
        return True, "the listing walked %d EmailBison campaign(s)" % len(
            index["campaigns"])
    if channel == "linkedin":
        heyreach = index.get("heyreach")
        if isinstance(heyreach, dict) and heyreach.get("read") is True:
            return True, "the listing records a HeyReach walk"
        why = ((heyreach or {}).get("why")
               if isinstance(heyreach, dict) else None)
        return False, ("the listing records no HeyReach walk (%s), so no "
                       "linkedin membership can be ruled out"
                       % (why or "no `heyreach` record at all"))
    return False, "%r is not a channel this listing covers" % (channel,)


def lookup(index, email=None):
    """Which campaigns hold a lead row for this address.

    Returns `{"found": bool, "campaigns": [keys], "why": str}`. The address
    is matched exactly as the producer wrote it - lowercased and stripped -
    and nothing fuzzier, because a near-match that excluded the wrong person
    would be a silent false exclusion.
    """
    address = (email or "").strip().lower()
    row = (index.get("by_email") or {}).get(address)
    if not isinstance(row, dict):
        return {"found": False, "campaigns": [],
                "why": "no lead row for %s in %d indexed addresses"
                       % (address or "a contact with no address",
                          records(index))}
    found = []
    for touch in row.get("touches") or []:
        if not isinstance(touch, dict):
            continue
        key = campaign_key(touch.get("campaign"))
        if key is not None and key not in found:
            found.append(key)
    return {"found": True, "campaigns": found,
            "why": "a lead row for this address in campaign(s) %s"
                   % (", ".join(str(c) for c in found) or "none named")}


def declared_but_not_walked(index):
    """Declared-internal campaigns with no entry in the listing at all.

    The case a non-match cannot survive: if 327 was never walked, "not in the
    listing" says nothing about whether this person is in 327.
    """
    from . import providerwrites
    declared = providerwrites.declared_internal()[
        providerwrites.DECLARED_CHANNELS["email"]]
    walked = {str(campaign_key(c)) for c in (index.get("campaigns") or {})}
    return sorted(c for c in declared if str(c) not in walked)
