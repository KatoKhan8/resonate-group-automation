#!/usr/bin/env python3
"""Has the client's own live estate already touched this person?

WHY THIS EXISTS, AND IT IS NOT HYPOTHETICAL. The two contacts selected for a
client's one-person canary were looked up in that client's live EmailBison
workspace for the first time. Both came back already worked (identities are
synthetic here; the measurement was real):

    alex@brightpath.test   two dozen emails across three campaigns,
                           0 opens, 0 replies
    sam@northbeam.test     a handful of emails on a campaign whose status
                           was `in_sequence` - running right now

Neither fact was knowable from canonical state. `work/queue.jsonl` said 0
confirmed touches for both, and it was right about what THIS system had done.
The client's own estate had been working the same list for months, across
dozens of campaigns and hundreds of sending inboxes, with a five-figure lead
list already loaded.

`PRODUCTION-TRANSITION.md` predicted exactly this and called it the single most
likely way a first pilot does visible damage. It is now measured rather than
predicted, on the specific people a canary was about to touch.

WHAT THIS MODULE IS. A read-only pre-send check against the provider's own lead
list. It is not suppression - `hygiene` owns that, over state we wrote - and it
is not a replacement for the confirmed-touch model. It answers one question the
confirmed-touch model structurally cannot: what has somebody ELSE already done
from this account.

WHY IT SEARCHES BY DOMAIN AND MATCHES LOCALLY. `GET /leads?search=` is not a
reliable equality filter. Probed:

    ?email=<addr>          ignored, returns the whole estate
    ?filter[email]=<addr>  ignored, returns the whole estate
    ?q=<term>              ignored, returns the whole estate
    ?search=<domain>       works: a real domain match came back single-digit
    ?search=<full addr>    UNRELIABLE: one address returned a five-figure count

So a check written as "search the address, and if the total is zero it is
clear" would have read five figures of unrelated rows as a match, and - far worse - a
naive variant would read a broad match as evidence of nothing. This module
searches the domain, walks every page of that result, and compares addresses
itself. When the response looks like a broad match rather than a filtered one
it refuses to answer at all.
"""
import argparse
import json

from . import linkedin, store
from .providers import bison, heyreach, request, ok

LEADS_PATH = "/leads"

# A domain search returning more than this many rows is not a filtered answer.
# The estate is a five-figure lead list and a real domain match has been
# single digits; a four-figure result means the filter was ignored, which
# must not be read as a clean sheet.
BROAD_MATCH = 200

# No default, deliberately. See `leads_for_domain`.
REQUIRED = object()

# A LinkedIn name search returning more than this is not a useful answer.
# `searchString` matches the correspondent's NAME only, so a common surname
# can legitimately return many people; past that we stop trusting a local
# profile match to have seen the right one and refuse instead.
BROAD_NAME_MATCH = 300

# What an account-level answer means for a step about to go out. The verdicts
# above say what the estate HOLDS; these say what may be DONE about it.
ALLOW = "allow"          # nothing at this account argues against the step
HOLD = "hold"            # a person should look before this goes
STOP = "stop"            # the account is answered or in play; do not add to it

TOUCHED = "touched"
IN_SEQUENCE = "in_sequence"
CLEAR = "clear"
UNKNOWN = "unknown"


class CollisionUnknown(RuntimeError):
    """The provider could not be asked, or answered unusably.

    Raised rather than returning CLEAR. "We could not check" and "there is
    nothing there" are the two answers this module exists to keep apart, and
    collapsing them is how a person who is mid-sequence gets a second sender.
    """


def _norm(value):
    return str(value or "").strip().lower()


def search_term(domain):
    """The label to search on, which is not the domain.

    `?search=` breaks on a term containing a dot: `brightpath.test` and
    `quicklead.test` both returned the same five-figure row count - the same
    number for both, and for a domain with no leads at all. The bare label is
    exact: `brightpath` returns just its own leads, `quicklead` returns 0.

    So the label is what gets searched and the full address is matched locally.
    That is not a workaround, it is the only form of the query whose absence of
    results means anything.
    """
    label = _norm(domain).split("@")[-1]
    parts = [p for p in label.split(".") if p]
    return parts[0] if parts else label


def leads_for_domain(domain, max_pages=40, expect_workspace=REQUIRED):
    """Every lead the provider holds whose row came back for this domain.

    Paginated properly - the estate's `per_page` is 15 and ignores overrides,
    and reading page one only is the defect this repository has already made
    once this week on `/sender-emails`.

    `expect_workspace` IS REQUIRED and has no default. On 2026-09-09 the
    credential's binding moved from PRODUCTIVE (10) to Bluewave (29)
    part-way through a session with nothing changing on this side - the vendor
    UI chooses it. Three prior-contact reads were taken against Bluewave's
    empty estate afterwards and every one answered CLEAR.

    That is not a weak answer, it is the wrong one. "Nobody has written to
    them", read from the wrong estate, is precisely the false clear that sends
    a second sender to somebody another campaign is mid-sequence with. The
    guard already existed here and was optional; an optional guard on this path
    is a guard that gets skipped, and it was.
    """
    domain = _norm(domain)
    if not domain:
        raise CollisionUnknown("no domain to check")
    if expect_workspace is REQUIRED:
        raise CollisionUnknown(
            "collision: expect_workspace is required. Name the provider "
            "workspace this question is about - the credential's binding is "
            "chosen in the vendor UI and has moved mid-session, so an "
            "unpinned read cannot say whose estate it answered for.")
    bison.require_workspace(expect_workspace)
    term = search_term(domain)
    rows, page = [], 1
    while page <= max_pages:
        status, data = request(
            "GET", f"{bison.base()}{LEADS_PATH}?search={term}&page={page}",
            bison.headers())
        if not ok(status):
            raise CollisionUnknown(
                f"emailbison leads: search for {domain} -> {status}")
        if not isinstance(data, dict):
            raise CollisionUnknown("emailbison leads: unexpected shape")
        chunk = data.get("data")
        if not isinstance(chunk, list):
            raise CollisionUnknown(
                "emailbison leads: no `data` array; refusing to read that as "
                "no prior contact")
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        total = meta.get("total")
        if isinstance(total, int) and total > BROAD_MATCH:
            # The filter was ignored. Answering from this would be answering
            # from the whole estate.
            raise CollisionUnknown(
                f"emailbison leads: search for {term!r} returned "
                f"{total} rows, which is a broad match rather than a filtered "
                f"one. Refusing to judge prior contact from it: a search that "
                f"ignores its term cannot prove absence.")
        rows += chunk
        last = meta.get("last_page")
        try:
            last = int(last)
        except (TypeError, ValueError):
            break
        if page >= last:
            break
        page += 1
    # A label search can match a different company - searching `clearwater`
    # returned `robin@adcrafters.test`. Keep only rows actually at this
    # domain, so a neighbour's lead is never reported as this account's.
    kept = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        address = _norm(row.get("email"))
        if address.endswith("@" + domain):
            kept.append(row)
    return kept


def touches_of(row):
    """What this lead has actually received, per the provider."""
    stats = row.get("overall_stats") if isinstance(row.get("overall_stats"),
                                                   dict) else {}
    per_campaign = row.get("lead_campaign_data")
    per_campaign = per_campaign if isinstance(per_campaign, list) else []
    campaigns = []
    for entry in per_campaign:
        if not isinstance(entry, dict):
            continue
        campaigns.append({
            "campaign_id": entry.get("campaign_id"),
            "status": entry.get("status"),
            "emails_sent": entry.get("emails_sent"),
            "replies": entry.get("replies"),
            "interested": entry.get("interested"),
        })
    return {
        "email": _norm(row.get("email")),
        "lead_id": row.get("id"),
        "lead_status": row.get("status"),
        "emails_sent": int(stats.get("emails_sent") or 0),
        "replies": int(stats.get("replies") or 0),
        "opens": int(stats.get("opens") or 0),
        "campaigns": campaigns,
        "in_sequence": any(_norm(c["status"]) == "in_sequence"
                           for c in campaigns),
        "created_at": row.get("created_at"),
    }


def profile_slug(url):
    """The stable part of a LinkedIn profile URL, via the canonical form.

    THIS IS `linkedin.key`, and it used to be a second implementation of it.
    The two disagreed exactly where it mattered: this one split on `?` but not
    `#`, and never percent-decoded, while `linkedin.canonical` does both. The
    docstring here already named the problem - "the same profile is written
    ... and with an encoded name" - and then did not handle that case.

    Measured on 2026-09-11 against a real conversation in the client's own
    inbox, on the client's own seat, where the prospect had REPLIED:

        .../in/jan-novak          -> in_sequence   (found)
        .../in/jan-novak/         -> in_sequence   (found)
        .../in/jan-novak#about    -> CLEAR         (missed)
        .../in/jan%2Dnovak        -> CLEAR         (missed)

    A miss here is a false CLEAR on the wrong-person gate, which is how
    somebody who already answered gets written to again. Two spellings of one
    identity is the defect; one function is the fix.

    Empty string, never None, because callers treat "" as "unanswerable" and
    raise rather than compare two blanks and call them equal.
    """
    return linkedin.key(url) or ""


def conversations_named(name, max_pages=10, page_size=100):
    """Every inbox conversation whose correspondent carries this name.

    THE FILTER'S REACH WAS MEASURED, NOT ASSUMED. `searchString` was probed
    against every field of a real conversation, and it matches the
    correspondent's first name, last name and full name and NOTHING ELSE -
    not `companyName`, not `profileUrl`, not `linkedin_id`, not message text.
    A key the route does not recognise is discarded in silence and the
    unfiltered 25,595 come back, so only proven keys are sent.

    Two consequences, and they are the whole reason this function is shaped
    the way it is. A name search IS a sound person-level question, and its
    negative control holds: a nonsense term answers 0 while a real name
    answers 1. And a search on a company or a profile URL answers 0 for
    every input, which must never be read as "nobody at that company" -
    see `account_is_unanswerable`.
    """
    term = str(name or "").strip()
    if not term:
        raise CollisionUnknown("no name to check the LinkedIn inbox for")
    rows, offset = [], 0
    for _ in range(max(1, max_pages)):
        items, total = heyreach.conversations(
            offset, page_size, filters={"searchString": term})
        if not isinstance(items, list):
            raise CollisionUnknown(
                "heyreach inbox: no conversation array; refusing to read that "
                "as no prior contact")
        if total is not None and int(total) > BROAD_NAME_MATCH:
            raise CollisionUnknown(
                f"heyreach inbox: {term!r} matches {total} conversations, "
                f"more than {BROAD_NAME_MATCH}. Too broad to conclude "
                f"anything about one person from.")
        rows.extend(r for r in items if isinstance(r, dict))
        offset += len(items)
        if not items or (total is not None and offset >= int(total)):
            break
    return rows


def linkedin_touches_of(row):
    """What this conversation actually is, per the provider."""
    profile = row.get("correspondentProfile")
    profile = profile if isinstance(profile, dict) else {}
    account = row.get("linkedInAccount")
    account = account if isinstance(account, dict) else {}
    return {
        "conversation_id": row.get("id"),
        "profile_url": profile.get("profileUrl"),
        "slug": profile_slug(profile.get("profileUrl")),
        "name": " ".join(x for x in (profile.get("firstName"),
                                     profile.get("lastName")) if x),
        "company": profile.get("companyName"),
        "our_seat": account.get("id"),
        "seat_name": " ".join(x for x in (account.get("firstName"),
                                          account.get("lastName")) if x),
        "total_messages": int(row.get("totalMessages") or 0),
        "last_message_at": row.get("lastMessageAt"),
        "last_message_sender": row.get("lastMessageSender"),
        "they_replied": str(row.get("lastMessageSender") or "").upper()
                        == heyreach.CORRESPONDENT.upper(),
    }


def our_linkedin_seats(workspace):
    """The provider seat ids this client owns, from canonical state.

    HeyReach's inbox route takes no organisation scope - `organizationUnitId`
    is readable on a campaign and is not a parameter anywhere - so the estate
    a conversation search covers is whatever the API key can see. The tenant
    boundary therefore cannot come from the query; it has to come from the
    answer, and this is the only canonical statement of which seats are ours.
    """
    from . import senderidentity

    seats = {str(a.get("provider_account_id"))
             for a in senderidentity.linkedin_accounts(workspace)
             if a.get("provider_account_id")}
    if not seats:
        raise CollisionUnknown(
            f"{workspace!r} has no inventoried LinkedIn seats, so a "
            f"conversation in this inbox cannot be attributed to this client. "
            f"Refusing to read an unscoped inbox as no prior contact.")
    return seats


def check_linkedin_profile(url, name=None, expect_workspace=REQUIRED):
    """`(verdict, detail)` for one LinkedIn profile, from our own inbox.

    The domain-side check cannot answer this. A live campaign is HeyReach-fed, so
    the LinkedIn lane could collide with a conversation one of the client's own
    33 seats is already having, and until now nothing looked.

    Searched by NAME because that is the only field the route filters on, then
    matched locally on the profile slug - the same shape as the EmailBison
    side, and for the same reason: the broad search is the provider's job and
    the identity match is ours.

    `expect_workspace` IS REQUIRED, and was not. This function is the LinkedIn
    half of the check whose EMAIL half answered CLEAR against another client's
    empty estate on 2026-09-09. That incident hardened `check_address`, which
    now takes `expect_workspace=REQUIRED` and verifies the credential binding
    before reading. This side kept the original signature - no workspace, no
    verification - on the channel the campaigns actually run on.

    Scoping cannot be done in the query, because the inbox route accepts no
    organisation parameter. So it is done on the answer: a conversation is
    evidence about THIS client only if it sits on a seat in THIS client's
    canonical roster. A conversation on a seat we do not own is another
    tenant's and must not inform this verdict in either direction - it must
    not create a false collision, and it must not be counted as coverage.
    """
    if expect_workspace is REQUIRED:
        raise CollisionUnknown(
            "check_linkedin_profile needs the workspace whose inbox this is. "
            "An unscoped CLEAR is not a statement about any client.")
    seats = our_linkedin_seats(expect_workspace)
    slug = profile_slug(url)
    if not slug:
        raise CollisionUnknown(f"{url!r} is not a LinkedIn profile to check")
    # THE FIRST NAME, not the full name. The search is literal on
    # punctuation - "O'neill" answers 4 and "Oneill" answers 0 - so a
    # full-name term is a fragile negative: one stored apostrophe, double
    # space or accent and a real prior conversation reads as CLEAR. The first
    # name is the most reliably stored token, it answered 12 and 41 for the
    # two live candidates rather than 0, and the local slug match supplies all
    # the precision. Broad in the query, exact in the comparison - the same
    # division of labour as stripping the TLD on the EmailBison side.
    term = str(name or "").strip().split()[0] if str(name or "").strip()         else slug.replace("-", " ")
    everything = conversations_named(term)
    # OURS ONLY. Dropped before any verdict is derived, so a foreign
    # conversation can neither raise a collision nor be counted as having
    # been looked at.
    rows, foreign = [], 0
    for row in everything:
        if str(linkedin_touches_of(row).get("our_seat")) in seats:
            rows.append(row)
        else:
            foreign += 1
    for row in rows:
        found = linkedin_touches_of(row)
        if found["slug"] != slug:
            continue
        if found["they_replied"]:
            return IN_SEQUENCE, dict(found, note="they have replied to us")
        if found["total_messages"] > 0:
            return TOUCHED, found
        return TOUCHED, dict(found, note="a conversation exists with no "
                                         "message counted")
    return CLEAR, {"profile_url": url, "slug": slug, "searched_as": term,
                   "workspace": expect_workspace,
                   "conversations_for_that_name": len(rows),
                   "other_tenants_conversations_ignored": foreign,
                   "seats_searched": len(seats),
                   "note": "no conversation with this profile in our inbox"}


def account_is_unanswerable(domain):
    """Why there is no company-level LinkedIn collision check.

    Recorded as a function rather than a comment so a caller has to confront
    it. `searchString` does not match `companyName`, so "has anybody at this
    company talked to one of our seats" cannot be asked as a query - it needs
    all 25,595 conversations walked and compared locally, 256 read-only pages.
    Until that exists, a clear person-level answer is exactly that and no
    more, and this returns UNKNOWN rather than letting a caller infer CLEAR.
    """
    return UNKNOWN, {
        "domain": _norm(domain),
        "why": "heyreach searchString matches the correspondent name only, "
               "never companyName, so no query can ask this",
        "do_not_conclude": "a person-level CLEAR is not a company-level CLEAR",
    }


def check_address(address, rows=None, expect_workspace=REQUIRED):
    """`(verdict, detail)` for one address, from the provider's own leads."""
    address = _norm(address)
    if not address or "@" not in address:
        raise CollisionUnknown(f"{address!r} is not an address to check")
    domain = address.rsplit("@", 1)[-1]
    rows = (leads_for_domain(domain, expect_workspace=expect_workspace)
            if rows is None else rows)
    for row in rows:
        if not isinstance(row, dict):
            continue
        if _norm(row.get("email")) != address:
            continue
        found = touches_of(row)
        if found["in_sequence"]:
            return IN_SEQUENCE, found
        if found["emails_sent"] > 0:
            return TOUCHED, found
        # Loaded as a lead but never sent to. Not a touch, and not nothing:
        # somebody has this person queued.
        return TOUCHED, dict(found, note="loaded as a lead, nothing sent yet")
    return CLEAR, {"email": address, "domain": domain,
                   "leads_at_domain": len(rows),
                   "note": "no lead at this address in the provider's estate"}


def check_account(domain, expect_workspace=REQUIRED):
    """Every lead the provider holds at one company, and the account verdict.

    Account-level, because outreach is account-based here: a colleague
    mid-sequence is a fact about the company even when the person we picked is
    untouched.
    """
    rows = leads_for_domain(domain, expect_workspace=expect_workspace)
    people = [touches_of(r) for r in rows if isinstance(r, dict)]
    sent = sum(p["emails_sent"] for p in people)
    return {
        "domain": _norm(domain),
        # Stamped on every answer: a verdict without its estate is unreadable.
        "workspace": expect_workspace,
        "leads": len(people),
        "people": people,
        "emails_sent_total": sent,
        "anyone_in_sequence": any(p["in_sequence"] for p in people),
        "any_bounce": any(_norm(p["lead_status"]) == "bounced"
                          for p in people),
        "verdict": (IN_SEQUENCE if any(p["in_sequence"] for p in people)
                    else TOUCHED if sent else CLEAR),
        "checked_at": store.now(),
    }


def account_policy(account):
    """ALLOW / HOLD / STOP for one account-level answer, and why.

    THE ACCOUNT IS THE UNIT OF OUTREACH AND THE SEND GATE COULD NOT SEE IT.
    `executionguard` ran `check_linkedin_profile` OR `check_address` - person
    level, one channel - and `check_account` had no caller on any send path.
    Measured on 2026-09-12 against the live pilot account: nine cold emails to
    a colleague on the same record, across two campaigns, since April, zero
    replies, and every gate answered that the account was cold.

    A BLANKET REFUSAL ON `TOUCHED` WOULD BE THE WRONG FIX. Most of a worked
    estate has been touched, and refusing all of it stops the product rather
    than protecting anybody. So the distinctions the provider already draws
    are kept:

      somebody is mid-sequence      -> STOP. A second channel now is the
                                       collision this module exists to stop.
      somebody replied or is marked -> STOP. The account is answered. Whoever
      interested                       is having that conversation owns it.
      an address there bounced      -> HOLD. The data is suspect; a person
                                       should look before we spend more on it.
      emailed before, all finished, -> ALLOW. A campaign that ran its course
      nobody replied                   months ago is history, not a live
                                       conflict. It is still REPORTED, so
                                       "cold outreach" is never claimed about
                                       an account that has heard from us.
      nothing at all                -> ALLOW.
      unanswerable                  -> HOLD. Missing evidence is not positive
                                       evidence; an estate we could not read
                                       cannot certify that nobody is in it.

    Returns (decision, why). The `why` is the sentence an operator reads, so
    it names the account fact rather than the rule number.
    """
    if not isinstance(account, dict) or account.get("verdict") == UNKNOWN:
        return HOLD, ("the provider estate could not be read for this "
                      "account, so nobody can say whether somebody there is "
                      "already in a sequence")
    people = [p for p in (account.get("people") or []) if isinstance(p, dict)]
    if account.get("anyone_in_sequence"):
        return STOP, "somebody at this account is mid-sequence right now"
    answered = [p for p in people
                if int(p.get("replies") or 0) > 0
                or any(c.get("interested") for c in (p.get("campaigns") or []))]
    if answered:
        return STOP, (f"{len(answered)} person(s) at this account have already "
                      f"replied or been marked interested; the account is "
                      f"answered and whoever is having that conversation "
                      f"owns it")
    if account.get("any_bounce"):
        return HOLD, "an address at this account bounced; the data is suspect"
    sent = int(account.get("emails_sent_total") or 0)
    if sent:
        return ALLOW, (f"{sent} email(s) were sent to this account in finished "
                       f"campaigns with no reply; history, not a live conflict")
    return ALLOW, "no prior contact at this account"


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.collision",
                               description=__doc__)
    p.add_argument("target", nargs="+",
                   help="a domain, or an email address")
    p.add_argument("--workspace", required=True,
                   help="the provider workspace id this question is about; "
                        "refused unless the credential is bound to it")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    out = []
    for target in a.target:
        try:
            if "@" in target:
                verdict, detail = check_address(
                    target, expect_workspace=a.workspace)
                out.append({"target": target, "verdict": verdict,
                            "detail": detail})
            else:
                out.append({"target": target,
                            **check_account(
                                target, expect_workspace=a.workspace)})
        except CollisionUnknown as e:
            out.append({"target": target, "verdict": UNKNOWN,
                        "why": str(e)})
    if a.json:
        print(json.dumps(out, indent=2, sort_keys=True))
        return 0
    for row in out:
        print(f"\n{row['target']}: {row.get('verdict')}")
        for person in row.get("people", []):
            flag = " IN SEQUENCE" if person["in_sequence"] else ""
            print(f"    {person['email']:44} sent={person['emails_sent']:<3} "
                  f"replies={person['replies']:<3} "
                  f"status={person['lead_status']}{flag}")
        if row.get("why"):
            print(f"    {row['why']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
