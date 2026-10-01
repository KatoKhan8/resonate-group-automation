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
import datetime
import json

from . import linkedin, replies, store
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

# The campaign statuses this system has actually seen EmailBison report, and
# therefore the only ones it may reason about. `in_sequence` is the one the
# module docstring records from the live estate - a campaign running right
# now; `sequence_finished` is the terminal counterpart. Anything else is a
# word nobody here has verified the meaning of, and `touches_of` reports it
# as unknown rather than assuming it is harmless. Adding a name to this set
# is a claim that somebody checked what it means at the provider.
# `sending_paused` joined on 2026-09-13, measured rather than assumed: a lead
# in a PAUSED campaign reads this, and it flips back to `in_sequence` the
# moment somebody resumes. So it is a known word, and it is NOT a touch -
# nothing has been sent - but it is also not `sequence_finished`, because the
# campaign can start again. `touches_of` counts it as membership without
# contact, which is what it is.
#
# It was found by the account gate holding on our own canary: staging one
# lead into a paused campaign made this system's own work look like an
# unverified status at the account. The gate was right to hold; the word
# simply had no meaning yet.
SENDING_PAUSED = "sending_paused"

# The rest of the vocabulary, established on 2026-09-13 by reading every
# membership status the Productive estate actually contains: `stopped` (8),
# `sequence_finished` (19), `in_sequence` (7), `bounced` (1), `replied` (1).
# Until then three of those were unread, and the accounts carrying them held
# on "nobody has verified this word" rather than on what the word says.
REPLIED = "replied"
BOUNCED = "bounced"
STOPPED = "stopped"

# A REPLY IS A REPLY EVEN WHEN THE COUNTER SAYS ZERO.
#
# The status and the count disagree, and the status is the one to trust.
# Measured: grayloon.com carries campaign 274 with status `replied` and
# `replies: 0` on the same row. `account_policy` reads the COUNT, so simply
# declaring `replied` a known word would have moved that account from HOLD to
# ALLOW - emailing somebody at an account that had already answered, which is
# the exact collision this module exists to prevent. Adding a word to the
# known set is not the same as understanding it.
ANSWERED_STATUSES = frozenset({REPLIED})

# Terminal, and not an answer, but not nothing either. `stopped` means future
# emails were cancelled for that person - by us, by an unsubscribe, or by the
# provider on a reply - and the status does not say which. `bounced` means the
# address failed. Neither is a live collision; both are a reason for somebody
# to look before we spend again.
SUSPECT_STATUSES = frozenset({STOPPED, BOUNCED})

KNOWN_STATUSES = frozenset({IN_SEQUENCE, "sequence_finished", SENDING_PAUSED,
                            REPLIED, BOUNCED, STOPPED})
UNKNOWN = "unknown"

# ------------------------------------------- our own staging, and only ours
#
# OUR OWN STAGING ARTIFACT IS NOT THE CLIENT'S HISTORY, AND IT LOOKED
# IDENTICAL. Measured 2026-09-16 on workspace 10 (PRODUCTIVE):
#
#     campaign 485  emails_sent 0  total_leads_contacted 0  opened 0
#                   replied 0  bounced 0  unsubscribed 0  status draft
#                   -> membership(485) reads `stopped` for 10 of 10 leads
#
# The provider stops a campaign's memberships when it archives a campaign that
# has no sending account attached. `stopped` is a SUSPECT status, so every one
# of those ten accounts answered HOLD - "a campaign at this account ended
# early and the status does not say whether we stopped it, they unsubscribed,
# or the provider stopped it on a reply" - and `bisonfactory` refused the
# whole cohort. The status was a fact about a campaign of ours that has never
# sent an email, and it was being read as a fact about the prospect.
#
# WHAT THIS DOES NOT DO, AND THE LIST IS THE DESIGN.
#
#   - It does not infer "safe" from ownership. A campaign being ours is the
#     cheap FILTER that decides which campaigns are worth a provider read; it
#     is never the evidence. `_ours` alone cannot exclude anything.
#   - It does not infer "we stopped it". Nothing here reads the stop reason,
#     because the provider does not record one. It proves the opposite thing:
#     that no email was ever sent from this campaign at all, in which case
#     there is no stop reason to get wrong.
#   - It does not cache a verdict or hardcode a campaign number. The evidence
#     is re-read from the provider in every process that asks (see
#     `forget_staging_evidence`), so a campaign that sends tomorrow stops
#     being an artifact tomorrow.
#   - A campaign with any confirmed touch is not an artifact, ever. Every
#     counter must be present AND integral AND zero; a counter the provider
#     does not return is unread, and unread is not zero.

#: The campaign statuses at which EmailBison is definitively not sending.
#: Deliberately a positive list: `bison.STARTED_STATES` and
#: `bison.STARTING_STATES` are the words known to mean "it is going out", and
#: every OTHER word - including the ones nobody here has read yet - has to
#: fail this check, because "I do not recognise this state" is not "it is not
#: sending". A campaign sitting at 0 sent because it started thirty seconds
#: ago is the case this arm exists for.
NOT_SENDING_STATES = frozenset({"draft", "paused", "archived", "failed",
                                bison.PENDING_DELETION})

#: Every campaign counter that must be present, integral and zero before the
#: campaign may be called prospect-facing-silent. `opened` and `unique_opens`
#: are in here even though an open is not a send: an open is only possible
#: after one, so a non-zero open count contradicts `emails_sent: 0` and the
#: contradiction has to fail closed rather than pick a winner.
ZERO_COUNTERS = ("emails_sent", "total_leads_contacted", "opened",
                 "unique_opens", "replied", "unique_replies", "bounced",
                 "unsubscribed", "interested")

#: Scheduled-email row statuses that mean the row never left the building.
#: `scheduled_emails` is the provider's own pre-send queue and it is the one
#: place a send is visible as a row rather than as a counter - campaign 451,
#: which sent exactly one email, carries exactly one row reading `sent`. Any
#: word outside this set, and any row carrying `sent_at`, disqualifies.
QUEUE_NOT_SENT = frozenset({"scheduled", "stopped", "cancelled", "canceled",
                            "paused", "draft", "skipped"})

#: The membership statuses our own zero-send staging leaves on a lead, and the
#: only ones an exclusion may remove. `bounced` is absent on purpose: a bounce
#: is a fact about the ADDRESS, not about the campaign that discovered it, and
#: it survives whoever staged the lead. `replied`, `in_sequence` and
#: `sequence_finished` are absent because none of them can be true of a
#: campaign that has sent nothing, so seeing one means the evidence is wrong.
EXCLUDABLE_MEMBERSHIP = frozenset({STOPPED, SENDING_PAUSED})

#: Membership statuses that mean "this lead is on the campaign and has not
#: been contacted through it". `in_sequence` joins the two above ONLY on the
#: per-lead path in `_excludable`, and only for a campaign of ours whose own
#: counters are all zero - see ISSUE-014. `bounced`, `replied` and
#: `sequence_finished` are deliberately absent: each asserts that something
#: reached the person, and a row asserting that on a campaign that has sent
#: nothing is a contradiction to be kept and looked at, never resolved in
#: favour of sending.
UNCONTACTED_MEMBERSHIP = frozenset(EXCLUDABLE_MEMBERSHIP | {IN_SEQUENCE})

#: The campaign counters that together mean "this campaign has reached
#: nobody". Checked instead of, not as well as, a verified not-sending status.
SILENCE_COUNTERS = ("emails_sent", "total_leads_contacted", "opened",
                    "unique_opens", "replied", "unique_replies", "bounced",
                    "unsubscribed", "interested")

#: Action-ledger states that mean one of our own sends may have reached a
#: person on this campaign. `failed` (the provider refused before acting) and
#: `abandoned` (a human called it off) are the only two that prove it did not,
#: so everything else - including `unresolved`, which exists precisely to say
#: "nobody knows" - disqualifies.
LEDGER_MAY_HAVE_REACHED = frozenset({"attempted", "sent", "unresolved"})


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
            # AN UNREADABLE PAGE COUNT IS NOT A LAST PAGE. This broke out of
            # the loop and returned page one as though it were the whole
            # answer, so an estate that omitted `meta` - or renamed
            # `last_page` - produced a confident `clear` from a fifteen-row
            # slice of it. Measured against a four-page estate: without
            # `meta` the read returned 15 leads and ALLOW, with it 4 pages
            # and the in-sequence colleague that makes the account STOP. The
            # same missing `meta` also skips the BROAD_MATCH check above, so
            # both protections disappear together and neither says so.
            #
            # An empty page is a real end: there is nothing here and nothing
            # after it. Anything else is a read that cannot prove it saw the
            # whole result, and this module's rule is that an estate we could
            # not read cannot certify that nobody is in it.
            if not chunk:
                break
            raise CollisionUnknown(
                f"emailbison leads: page {page} returned {len(chunk)} row(s) "
                f"and no readable `last_page`, so there is no way to tell "
                f"whether more rows exist. Refusing to read a partial page as "
                f"the whole estate.")
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
            # Carried because `_excludable` needs it, and it was the one
            # per-campaign counter the provider returns that this function
            # dropped. An open is only possible after a send, so a membership
            # claiming an open contradicts a campaign claiming none - and a
            # contradiction has to be visible to be refused.
            "opens": entry.get("opens"),
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
        "in_sequence": any(_norm(c["status"]) == IN_SEQUENCE
                           for c in campaigns),
        # A STATUS THIS SYSTEM DOES NOT RECOGNISE IS NOT A STATUS MEANING
        # "not running". The line above is a single literal, so every other
        # word the provider might use for a live campaign - and every word it
        # adds later - answered False and reached `account_policy` as ALLOW,
        # "history, not a live conflict". The two names below are the ones
        # this estate has actually been observed to use; anything else is
        # unread rather than safe, and is carried up so the account answer
        # can hold instead of guessing which it was.
        "unknown_statuses": sorted({
            _norm(c["status"]) for c in campaigns
            if _norm(c["status"]) and _norm(c["status"]) not in KNOWN_STATUSES}),
        "created_at": row.get("created_at"),
    }


def _int(value):
    """`value` as an int, or None. A string counter is not an int here.

    Fail-closed on purpose: every caller below treats None as "unread", and
    unread must never satisfy a "must be zero" test.
    """
    return value if isinstance(value, int) and not isinstance(value, bool) \
        else None


def campaign_bindings():
    """Provider campaign id -> the canonical campaign row that claims it.

    `work/campaigns.jsonl` is this system's own record of which EmailBison
    campaign it built for which client campaign, written by the factory the
    instant the provider answers. It is one half of the ownership proof and
    it is not sufficient by itself - see `_ours`.

    A provider id claimed by two canonical rows is DROPPED rather than
    resolved. An ambiguous claim of ownership is not a claim, and picking the
    last writer would make the answer depend on file order.
    """
    from . import campaigns          # lazy: campaigns pulls cadence and lint

    try:
        rows = list(campaigns.load())
    except Exception:                 # noqa: BLE001 - see below
        # A binding file that cannot be read means nothing can be proven ours,
        # which means nothing is excluded and every membership row reaches
        # `account_policy` exactly as it did before this code existed. That is
        # the safe direction, so it is silent rather than fatal: refusing here
        # would take the account gate itself offline over a file that only
        # ever RELAXES a verdict.
        return {}
    out, ambiguous = {}, set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        bound = _int(row.get("bison_campaign_id"))
        if bound is None:
            try:
                bound = int(str(row.get("bison_campaign_id")).strip())
            except (TypeError, ValueError):
                continue
        if bound in out:
            ambiguous.add(bound)
        out[bound] = row
    for key in ambiguous:
        out.pop(key, None)
    return out


def _ours(campaign_id, binding, provider_row):
    """Is this provider campaign one this system built? Proven on both sides.

    OWNERSHIP IS NEVER EVIDENCE OF SAFETY and this function does not pretend
    otherwise - it is the cheap filter that decides which campaigns are worth
    spending a provider read on. `staging_artifact_evidence` calls it first
    and then has to prove, from the provider, that the campaign reached
    nobody. Both must hold.

    It is proven on BOTH sides because either side alone is forgeable by
    accident. `work/campaigns.jsonl` is a local file this system writes, so it
    can name a provider campaign that was deleted and rebuilt by somebody
    else under the same id. The provider's own `name` carries the canonical
    binding - `bisonfactory.provider_campaign_name` derives it as
    `"<human> [<client>/<campaign_id>]"` - so the provider itself states who
    the campaign belongs to. The two have to agree about the same client and
    the same canonical campaign, or this answers no.

    The suffix is recomputed here rather than imported, because importing
    `bisonfactory` from this module closes an import cycle - the factory
    imports `collision`. `tests/test_our_own_staging_is_not_their_history.py`
    pins the two derivations against each other so the duplication cannot
    drift silently.
    """
    if not isinstance(binding, dict):
        return False, "no canonical campaign row claims this provider campaign"
    client = str(binding.get("client") or "").strip()
    canonical = str(binding.get("campaign_id") or "").strip()
    if not client or not canonical:
        return False, "the canonical campaign row names no client or campaign"
    suffix = f" [{client}/{canonical}]"
    name = str((provider_row or {}).get("name") or "")
    if not name.endswith(suffix):
        return False, (f"the provider's own name for campaign {campaign_id} "
                       f"does not carry this system's binding {suffix.strip()}")
    return True, f"claimed by {client}/{canonical} on both sides"


def _ledger_is_silent(binding):
    """Has this system ever recorded a prospect-facing action on this campaign?

    The provider's counters are one witness; this repository's own audit trail
    is a second and independent one. `actionledger` writes a reservation
    BEFORE the provider is called, so a send that timed out mid-flight leaves
    a row here even when no counter at the provider ever moved - which is the
    exact case a counter-only check would read as silence.

    An unreadable ledger answers no. A missing audit trail is not a clean one.
    """
    from . import actionledger

    canonical = str((binding or {}).get("campaign_id") or "").strip()
    if not canonical:
        return False, "no canonical campaign to look up in the action ledger"
    try:
        rows = actionledger.load()
    except Exception as e:                       # noqa: BLE001 - fail closed
        return False, (f"the action ledger could not be read "
                       f"({type(e).__name__}), so it cannot certify silence")
    # THE LATEST STATE PER KEY, NOT EVERY ROW EVER WRITTEN.
    #
    # `actionledger.settle` APPENDS - it never edits history, deliberately - so
    # a key that was reserved and then settled leaves BOTH rows in the file.
    # Scanning every row therefore counted the superseded `attempted` row
    # forever, and a key settled `abandoned` against provider proof that
    # nothing was sent still read as an unrefuted action. Measured on campaign
    # 487: ten keys, all ten `abandoned`, all ten counted as reached.
    #
    # That is the wrong direction for this particular check. Everywhere else
    # failing closed is right; here it meant a campaign could never be proven
    # silent once a single attempt had been settled, so its own staged leads
    # stayed indistinguishable from real prior contact and the campaign could
    # never be activated. `state_of` is what the ledger itself uses to answer
    # "what is true of this key now", and it is what belongs here.
    latest = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("campaign_id") or "") != canonical:
            continue
        key = row.get("key")
        if key:
            latest[key] = row
    hits = [k for k, r in latest.items()
            if _norm(r.get("state")) in LEDGER_MAY_HAVE_REACHED]
    if hits:
        return False, (f"this system's action ledger holds {len(hits)} "
                       f"unrefuted prospect-facing action(s) for {canonical}")
    return True, f"no prospect-facing action recorded for {canonical}"


def _queue_is_silent(campaign_id):
    """The provider's own pre-send queue, read as "did anything ever leave".

    Independent of the counters: `scheduled_emails` returns one ROW per
    message, and a sent one says so. Campaign 451 - one email, one recipient -
    answers a single row reading `sent`; 481 and 485 answer none.

    A read that raises answers no. `scheduled_emails` refuses a queue too big
    to walk rather than returning its first page, and a campaign nobody can
    walk is a campaign nobody can clear.
    """
    try:
        rows = bison.scheduled_emails(campaign_id)
    except Exception as e:                       # noqa: BLE001 - fail closed
        return False, (f"the scheduled-email queue for campaign {campaign_id} "
                       f"could not be read ({type(e).__name__})")
    for row in rows:
        if not isinstance(row, dict):
            return False, "a scheduled-email row was not readable"
        if row.get("sent_at"):
            return False, (f"campaign {campaign_id} has a queue row that was "
                           f"already sent")
        state = _norm(row.get("status"))
        if state not in QUEUE_NOT_SENT:
            return False, (f"campaign {campaign_id} has a queue row reading "
                           f"{state!r}, which this system cannot read as "
                           f"unsent")
    return True, (f"{len(rows)} queue row(s) for campaign {campaign_id}, none "
                  f"of them sent")


def zero_send_evidence(campaign_id, provider_row=None):
    """Positive proof from the provider that this campaign reached nobody.

    Every counter in `ZERO_COUNTERS` must be PRESENT, an int, and zero, and
    the campaign must be in a state at which the provider is definitively not
    sending. A counter the provider omits is unread; unread is not zero, and
    reading it as zero is how a campaign that has been working for a month
    gets called staging.

    Returns `(proven, why, counters)`. Never raises: a provider that cannot be
    read is simply not proof.
    """
    if provider_row is None:
        try:
            provider_row = bison.campaign(campaign_id)
        except Exception as e:                   # noqa: BLE001 - fail closed
            return False, (f"campaign {campaign_id} could not be read at the "
                           f"provider ({type(e).__name__})"), {}
    if not isinstance(provider_row, dict):
        return False, f"campaign {campaign_id} did not answer with a row", {}

    counters = {name: _int(provider_row.get(name)) for name in ZERO_COUNTERS}
    unread = sorted(n for n, v in counters.items() if v is None)
    if unread:
        return False, (f"campaign {campaign_id} does not report "
                       f"{', '.join(unread)}; an unread counter is not a zero "
                       f"one"), counters
    nonzero = sorted(n for n, v in counters.items() if v != 0)
    if nonzero:
        return False, (f"campaign {campaign_id} has touched somebody: "
                       f"{', '.join(f'{n}={counters[n]}' for n in nonzero)}"
                       ), counters

    state = _norm(provider_row.get("status"))
    if state not in NOT_SENDING_STATES:
        return False, (f"campaign {campaign_id} reads status {state!r}, which "
                       f"is not a state this system has verified means "
                       f"`not sending`; a campaign that started a moment ago "
                       f"also reports zero"), counters
    return True, (f"campaign {campaign_id} is {state} and every prospect-"
                  f"facing counter the provider reports is zero"), counters


def staging_artifact_evidence(campaign_id, bindings=None):
    """Is this provider campaign one of OUR proven-zero-send staging artifacts?

    Four independent arms, ALL of which must hold, and none of which is
    ownership-on-its-own:

      1. ours, stated by this system's binding file AND by the provider's own
         campaign name, and the two agree;
      2. every prospect-facing counter the provider reports is zero, and the
         campaign is in a state at which it is definitively not sending;
      3. the provider's pre-send queue holds no row that ever went out;
      4. this repository's action ledger records no unrefuted prospect-facing
         action against the canonical campaign.

    Returns a dict. `proven` is the answer; `why` is the sentence an operator
    reads; `arms` is every arm's own verdict, so a refusal names the arm that
    refused rather than the rule number.
    """
    bindings = campaign_bindings() if bindings is None else bindings
    binding = bindings.get(campaign_id)
    out = {"campaign_id": campaign_id, "proven": False, "arms": {},
           "counters": {}, "checked_at": store.now()}

    # Arm 1 first, and it is deliberately the cheapest: it costs one local
    # file read and it decides whether the provider is worth asking at all.
    if not isinstance(binding, dict):
        out["arms"]["ours"] = (False, "no canonical campaign row claims this "
                                      "provider campaign")
        out["why"] = out["arms"]["ours"][1]
        return out
    try:
        provider_row = bison.campaign(campaign_id)
    except Exception as e:                       # noqa: BLE001 - fail closed
        out["arms"]["ours"] = (False, f"campaign {campaign_id} could not be "
                                      f"read ({type(e).__name__})")
        out["why"] = out["arms"]["ours"][1]
        return out

    out["arms"]["ours"] = _ours(campaign_id, binding, provider_row)
    if out["arms"]["ours"][0]:
        proven, why, counters = zero_send_evidence(campaign_id, provider_row)
        out["counters"] = counters
        out["status"] = _norm(provider_row.get("status"))
        out["arms"]["zero_send"] = (proven, why)
        if proven:
            out["arms"]["queue"] = _queue_is_silent(campaign_id)
            if out["arms"]["queue"][0]:
                out["arms"]["ledger"] = _ledger_is_silent(binding)

    refused = [why for _ok, why in out["arms"].values() if not _ok]
    out["proven"] = not refused and len(out["arms"]) == 4
    out["why"] = (refused[0] if refused else
                  "; ".join(why for _ok, why in out["arms"].values()))
    return out


# Per-process, and that is the whole contract. The evidence is re-derived from
# the provider by the first ask in each run and reused for the rest of that
# run, so a campaign that starts sending is an artifact for at most one run's
# worth of reads and never across runs. Nothing is written to disk, and no
# campaign number is written down anywhere: delete this dict and the next ask
# goes back to the provider.
_EVIDENCE = {}


def forget_staging_evidence():
    """Drop what this process has read about our own campaigns.

    Called by tests, and available to any long-lived process that wants the
    provider asked again mid-run.
    """
    _EVIDENCE.clear()


def staging_artifacts(campaign_ids, bindings=None):
    """The subset of `campaign_ids` that is provably our own silent staging.

    Reads the provider once per candidate per process. Campaigns no canonical
    row claims never reach the provider at all, which is what keeps a worked
    estate - where a lead can sit in a dozen of the client's own campaigns -
    from costing a dozen reads per account.
    """
    bindings = campaign_bindings() if bindings is None else bindings
    found = {}
    for campaign_id in campaign_ids:
        key = _int(campaign_id)
        if key is None:
            try:
                key = int(str(campaign_id).strip())
            except (TypeError, ValueError):
                continue
        if key not in bindings:
            continue                      # not ours: never read, never excluded
        if key not in _EVIDENCE:
            _EVIDENCE[key] = staging_artifact_evidence(key, bindings)
        # EVERY CAMPAIGN OF OURS IS RETURNED, PROVEN OR NOT.
        #
        # It used to return only the proven ones, so an unproven campaign of
        # ours never reached `_excludable` at all and could not be judged on
        # the lead's own row. `_excludable` is where the two cases are told
        # apart, and it still refuses everything it refused before - a
        # campaign that is not ours never gets here, because the `bindings`
        # check above already dropped it.
        found[key] = _EVIDENCE[key]
    return found


def _excludable(entry, evidence):
    """May THIS membership row be dropped, given proof about its campaign?

    The campaign-level proof is necessary and not sufficient. This row has to
    agree: a status our own staging actually leaves, and its own counters at
    zero. A row that disagrees with the campaign it belongs to is a row this
    system has misread, and a misreading must not be resolved in favour of
    sending.
    """
    # THE ROW'S OWN COUNTERS COME FIRST, because both paths below need them
    # and neither may drop a row that shows contact. A row that disagrees with
    # the campaign it belongs to is a row this system has misread, and a
    # misreading must not be resolved in favour of sending.
    for field in ("emails_sent", "replies", "opens"):
        if _int(entry.get(field)) != 0:
            return False, (f"membership reports {field}="
                           f"{entry.get(field)!r}, so this lead has been "
                           f"contacted on this campaign")
    if entry.get("interested"):
        return False, "membership is marked interested"

    state = _norm(entry.get("status"))

    # PATH 1, unchanged: the whole campaign is proven to have sent nothing to
    # anybody, and the row reads a status that kind of staging leaves behind.
    if evidence.get("proven") and state in EXCLUDABLE_MEMBERSHIP:
        return True, evidence.get("why") or "our own proven-zero-send staging"

    # PATH 2: OUR OWN CAMPAIGN HAS NOT CONTACTED *THIS* LEAD.
    #
    # ISSUE-014. The campaign-level `zero_send` arm cannot be proven for an
    # ACTIVE campaign - correctly, since one that started a moment ago also
    # reports zero - so once this system activates a campaign, every account
    # it holds reads `in_sequence` from OUR OWN membership and every later
    # batch is refused at it. That made the continuous-cohort grant, whose
    # whole shape is batches 2..N filling eight standing campaigns,
    # unsatisfiable: 95 of 95 accounts across the campaigns sending on
    # 2026-09-22 read STOP, with zero client-side `in_sequence` rows among
    # them.
    #
    # The per-lead row answers the question the aggregate cannot. It carries
    # THIS lead's `emails_sent` FOR THIS CAMPAIGN, checked above and zero, so
    # the "it may have sent a moment ago" objection does not apply - it is the
    # lead's own row, not a counter that lags. A lead we have actually emailed
    # keeps its row and still collides, which is what the guard is for.
    #
    # This module answers "what has somebody ELSE already done at this
    # account". A membership in our own campaign that has reached nobody is
    # not something anybody has done to them. How soon WE may approach a
    # second person at an account is a different question with its own
    # answer: the client's `fatigue.account` policy - max_active_contacts and
    # min_hours_between_first_touches - which the batch builder enforces.
    # THREE CONDITIONS, and each one is a test that already existed:
    #
    #   the campaign is OURS on both sides of the binding
    #   the campaign's OWN counters are all zero - it has sent to NOBODY, not
    #     merely to nobody we have looked at. A campaign that has sent one
    #     email stops being excludable for every lead on it, because a row
    #     reading zero may simply lag
    #     (test_a_campaign_that_starts_sending_stops_being_an_artifact)
    #   the row reads a status consistent with "enrolled, not yet contacted".
    #     `bounced` and `sequence_finished` are NOT, and they stay - a bounce
    #     is a fact, and a campaign that sent nothing cannot have finished a
    #     sequence, so such a row contradicts itself and is a misreading
    #     (test_a_bounced_membership_of_ours_is_kept_in_the_answer,
    #      test_a_sequence_finished_membership_of_ours_is_kept)
    #
    # What this adds over PATH 1 is exactly one thing: it does not require the
    # campaign's STATUS to be a verified not-sending one. That is the single
    # condition ISSUE-014 turns on, and it is the only one the lead's own row
    # can replace.
    ours = (evidence.get("arms") or {}).get("ours") or ()
    counters = evidence.get("counters") or {}
    silent = all(_int(counters.get(field)) == 0 for field in SILENCE_COUNTERS)
    if ours and ours[0] and silent and state in UNCONTACTED_MEMBERSHIP:
        return True, (f"our own campaign, which has contacted nobody, and "
                      f"this lead's own row on it reads emails_sent 0 "
                      f"({state!r})")

    # PATH 3: OUR CAMPAIGN HAS SENT - TO SOMEBODY ELSE.
    #
    # ISSUE-018, and it is ISSUE-014 one step later. Path 2 requires the whole
    # campaign to be silent, so the FIRST send a standing campaign makes locks
    # it for every remaining lead on it. Campaign 495 sent one email at
    # 13:02:46Z on 2026-09-22 and its next top-up was refused at 26 accounts,
    # every one of them our own `in_sequence` rows with zero sends.
    #
    # THE "A ROW READING ZERO MAY LAG" OBJECTION IS NOW MEASURED, AND IT IS
    # FALSE FOR THIS PROVIDER. Seventeen minutes after that send, read back
    # live at the same account:
    #
    #     <prospect-c>@example.test    camp 495  in_sequence  emails_sent 1
    #     <prospect-d>@example.test  camp 495  in_sequence  emails_sent 0
    #
    # The per-lead counter updated, and it discriminated between two leads at
    # one account. So the lead's own row is not an aggregate that trails the
    # campaign; it is the per-lead fact, and it is strictly better evidence
    # than the campaign counter that Path 2 leans on.
    #
    # NARROWED TO `in_sequence` DELIBERATELY. A `stopped` or `sending_paused`
    # row means somebody stopped THIS lead and the reason is not recorded -
    # that keeps Path 2's campaign-level proof, and with it
    # `test_a_campaign_that_starts_sending_stops_being_an_artifact`, whose
    # caution is right for a stop nobody can explain. `in_sequence` with zero
    # sends means the opposite and says so plainly: the lead is queued behind
    # our own first step and has been reached by nobody.
    if ours and ours[0] and state == IN_SEQUENCE:
        return True, (f"our own campaign, and this lead's own row on it reads "
                      f"emails_sent 0 while queued ({state!r}); the campaign "
                      f"has sent to somebody else, not to them")

    if not evidence.get("proven"):
        return False, "not proven to be our own silent staging"
    return False, (f"membership reads {state!r}, which our own zero-send "
                   f"staging does not leave behind")


def without_our_staging(person, bindings=None):
    """One `touches_of` answer with our own silent staging rows removed.

    Returns `(person, excluded)`. `person` is rebuilt, never mutated in place,
    and its derived fields - `in_sequence`, `unknown_statuses` - are recomputed
    from what is left. `emails_sent` is NOT recomputed and does not need to be:
    a row may only be excluded when it sent nothing, so the lead's totals are
    arithmetically untouched. That is the invariant that keeps thirteen real
    emails to a colleague visible after this runs.
    """
    campaigns_of = [c for c in (person.get("campaigns") or [])
                    if isinstance(c, dict)]
    artifacts = staging_artifacts(
        {c.get("campaign_id") for c in campaigns_of}, bindings)
    kept, excluded = [], []
    for entry in campaigns_of:
        key = _int(entry.get("campaign_id"))
        evidence = artifacts.get(key) if key is not None else None
        drop, why = (_excludable(entry, evidence) if evidence
                     else (False, "not ours, or not proven silent"))
        if drop:
            excluded.append({"campaign_id": key,
                             "status": _norm(entry.get("status")),
                             "why": why})
        else:
            kept.append(entry)
    if not excluded:
        return person, []
    rebuilt = dict(person, campaigns=kept)
    rebuilt["in_sequence"] = any(_norm(c.get("status")) == IN_SEQUENCE
                                 for c in kept)
    rebuilt["unknown_statuses"] = sorted({
        _norm(c.get("status")) for c in kept
        if _norm(c.get("status")) and _norm(c.get("status"))
        not in KNOWN_STATUSES})
    rebuilt["our_staging_excluded"] = excluded
    return rebuilt, excluded


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


def _client_config(workspace):
    """The client config, or {} when it cannot be read.

    `{}` means the org-unit check has nothing to compare against, and
    `seats_whose_conversations_are_ours` then requires only that the estate
    states ONE unit - which is the weaker half of the same guarantee, not a
    licence to skip it.
    """
    from . import clients

    try:
        return clients.load(workspace)
    except Exception:
        return {}


def our_linkedin_seats(workspace):
    """The seats this client may SEND from. The attested sending pool.

    Deliberately narrow: a seat reaches a prospect under a real person's
    name, and `senderinventory` records which ones a human attested.
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


# The tenant scope costs two provider reads and does not change between
# profiles, so it is resolved once per process per workspace. Per-call it
# doubled the request count of every collision check for an answer that is
# the same every time. Cleared by `forget_tenant_scope` in tests.
_TENANT_SCOPE = {}


def forget_tenant_scope():
    """Drop the cached tenant scope. For tests and for a seat re-inventory."""
    _TENANT_SCOPE.clear()


def seats_whose_conversations_are_ours(workspace, config=None):
    """Every seat whose inbox counts as this client's history.

    A DIFFERENT QUESTION FROM `our_linkedin_seats`, AND THE TWO SHARED ONE
    LIST. "Which seats may we send from" is the attested pool - 32 rows a
    human signed off. "Whose conversations are ours" is the whole tenant, and
    scoping the second to the first discarded every conversation on a seat
    nobody had attested as belonging to another tenant.

    It did not. Measured 2026-09-13: all 82 HeyReach campaigns this key can
    see carry `organizationUnitId 118832`, 39 of 41 seats appear in those
    campaigns, and the conversation counts reconcile exactly - 23,617 on
    roster seats plus 2,422 off-roster is 26,039, the whole inbox. Of those
    2,422 discarded conversations, 188 are people who REPLIED. Every one of
    them would have answered CLEAR.

    So the tenant boundary is derived from the campaigns, which are the only
    rows that state an organisation unit - seat rows carry none. If a single
    campaign belongs to another unit, the key is multi-tenant, an inbox
    conversation cannot be attributed from the answer alone, and this refuses
    rather than guessing in either direction.
    """
    from .providers import heyreach

    if workspace in _TENANT_SCOPE:
        return set(_TENANT_SCOPE[workspace])
    expected = str(((config or {}).get("providers") or {}).get(
        "heyreach", {}).get("org_unit") or "")
    campaigns, _meta = heyreach.campaigns()
    units = {str(c.get("organizationUnitId")) for c in campaigns
             if c.get("organizationUnitId") is not None}
    if not units:
        raise CollisionUnknown(
            "no campaign this key can see states an organisation unit, so "
            "the tenant boundary cannot be established and an inbox "
            "conversation cannot be attributed to this client")
    if expected and units != {expected}:
        raise CollisionUnknown(
            f"this key sees campaigns in organisation unit(s) "
            f"{sorted(units)} and {workspace!r} is configured for "
            f"{expected!r}. The inbox mixes tenants, so a conversation in it "
            f"cannot be attributed from the answer alone")
    seats, _ = heyreach.all_li_accounts()
    everybody = {str(a.get("id")) for a in seats if a.get("id") is not None}
    # The attested pool is always ours even if a seat has since been removed
    # at the provider; a conversation it held is still this client's history.
    scope = everybody | our_linkedin_seats(workspace)
    _TENANT_SCOPE[workspace] = set(scope)
    return scope


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
    # THE SLUG FIRST, because it is free and local. Resolving the tenant
    # scope costs two provider reads, and spending them to reject a URL that
    # is not a profile is two requests for an answer already in hand.
    slug = profile_slug(url)
    if not slug:
        raise CollisionUnknown(f"{url!r} is not a LinkedIn profile to check")
    # THE TENANT'S SEATS, NOT THE SENDING POOL. A conversation on a seat
    # nobody attested is still this client's history - see
    # `seats_whose_conversations_are_ours`, which exists because scoping this
    # to the attested 32 discarded 188 people who had replied.
    seats = seats_whose_conversations_are_ours(
        expect_workspace, config=_client_config(expect_workspace))
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
        # OUR OWN SILENT STAGING IS NOT PRIOR CONTACT, HERE EITHER.
        #
        # `check_account` learned this and `check_address` did not, so staging
        # a cohort into a campaign of ours made every one of those people read
        # TOUCHED - "loaded as a lead, nothing sent yet" - and the gate refused
        # the activation of the very campaign that had just loaded them.
        # Measured on campaign 487: ten contacts staged, ten refusals, zero
        # emails sent by anybody.
        #
        # The same four arms decide it, reused rather than restated: the
        # campaign must be claimed by us on BOTH sides, every prospect-facing
        # counter present and zero, the status not sending, and both the
        # provider queue and our own ledger silent. A campaign of somebody
        # else's, or one of ours that has sent anything, is untouched by this.
        #
        # `emails_sent` is not recomputed because it does not need to be: a row
        # can only be dropped when it sent nothing. So a person with real
        # history keeps it and still reads TOUCHED below.
        found, excluded = without_our_staging(found)
        if excluded:
            found = dict(found, our_staging_excluded=excluded)
        if found["in_sequence"]:
            return IN_SEQUENCE, found
        if found["emails_sent"] > 0:
            return TOUCHED, found
        if found.get("campaigns"):
            # Loaded as a lead but never sent to, by somebody whose campaign
            # this is not proven to be ours-and-silent. Not a touch, and not
            # nothing: somebody has this person queued.
            return TOUCHED, dict(found,
                                 note="loaded as a lead, nothing sent yet")
        return CLEAR, dict(found, note=(
            "no prior contact; the only lead rows at this address belong to "
            "campaigns of ours that have provably sent nothing"))
    return CLEAR, {"email": address, "domain": domain,
                   "leads_at_domain": len(rows),
                   "note": "no lead at this address in the provider's estate"}


def check_account(domain, expect_workspace=REQUIRED):
    """Every lead the provider holds at one company, and the account verdict.

    Account-level, because outreach is account-based here: a colleague
    mid-sequence is a fact about the company even when the person we picked is
    untouched. That stays mandatory: nothing below turns this into a
    person-level question, and `check_address` is not a substitute for it.

    OUR OWN SILENT STAGING IS REMOVED FROM THE HISTORY, AND ONLY THAT. Every
    membership row is kept unless four independent arms prove it belongs to a
    campaign this system built that has never sent an email to anybody - see
    `staging_artifact_evidence`. The exclusions are reported on the answer, in
    `our_staging_excluded`, so an operator reading a clear account can see
    exactly what was taken out of it and why.

    The account's own totals are untouched by this. A row may only be dropped
    when it sent nothing, so `emails_sent_total` is the same number before and
    after, and an account with real history keeps it.
    """
    rows = leads_for_domain(domain, expect_workspace=expect_workspace)
    people = [touches_of(r) for r in rows if isinstance(r, dict)]
    bindings = campaign_bindings()
    excluded = []
    for index, person in enumerate(people):
        people[index], dropped = without_our_staging(person, bindings)
        for entry in dropped:
            excluded.append(dict(entry, email=person.get("email")))
    sent = sum(p["emails_sent"] for p in people)
    return {
        "domain": _norm(domain),
        # Stamped on every answer: a verdict without its estate is unreadable.
        "workspace": expect_workspace,
        "leads": len(people),
        "people": people,
        "our_staging_excluded": excluded,
        "emails_sent_total": sent,
        "anyone_in_sequence": any(p["in_sequence"] for p in people),
        "unknown_statuses": sorted({s for p in people
                                    for s in p["unknown_statuses"]}),
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

    WHAT THIS DOES NOT DECIDE, AND MUST NOT. Whether a membership row is the
    client's history or this system's own silent staging is settled before the
    account reaches here, by `check_account` calling `without_our_staging`,
    and only on four arms of positive provider evidence that nothing was ever
    sent. Every verdict above is unchanged for genuine history: a `stopped`
    whose campaign has sent even one email is still a HOLD here, because that
    row is still in `people` when this function reads it.

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
    # THE STATUS AND THE COUNT DISAGREE, AND THE STATUS WINS.
    #
    # `replies` is a counter and `status: replied` is the membership's own
    # verdict, and they are not always the same: grayloon.com carries campaign
    # 274 with status `replied` and `replies: 0` on the same row. Reading only
    # the counter would call that account unanswered and email somebody else
    # there. A reply is a reply whichever field records it.
    answered = [p for p in people
                if int(p.get("replies") or 0) > 0
                or any(c.get("interested") for c in (p.get("campaigns") or []))
                or any(_norm(c.get("status")) in ANSWERED_STATUSES
                       for c in (p.get("campaigns") or []))]
    if answered:
        return STOP, (f"{len(answered)} person(s) at this account have already "
                      f"replied or been marked interested; the account is "
                      f"answered and whoever is having that conversation "
                      f"owns it")
    unknown = account.get("unknown_statuses") or []
    if unknown:
        return HOLD, (f"a campaign at this account reports "
                      f"{', '.join(repr(s) for s in unknown)}, which this "
                      f"system has no verified meaning for. It may be running "
                      f"right now, and an unread status is not a finished one")
    if account.get("any_bounce"):
        return HOLD, "an address at this account bounced; the data is suspect"
    # Terminal, and the status does not say who ended it. A person should look
    # before we spend again - this used to reach the same HOLD through not
    # knowing the word at all, which said nothing useful to whoever read it.
    suspect = sorted({_norm(c.get("status")) for p in people
                      for c in (p.get("campaigns") or [])
                      if _norm(c.get("status")) in SUSPECT_STATUSES})
    if suspect:
        return HOLD, (f"a campaign at this account ended early "
                      f"({', '.join(suspect)}) and the status does not say "
                      f"whether we stopped it, they unsubscribed, or the "
                      f"provider stopped it on a reply")
    sent = int(account.get("emails_sent_total") or 0)
    if sent:
        return ALLOW, (f"{sent} email(s) were sent to this account in finished "
                       f"campaigns with no reply; history, not a live conflict"
                       f"{_staging_note(account)}")
    return ALLOW, f"no prior contact at this account{_staging_note(account)}"


def _staging_note(account):
    """What an ALLOW had removed from it, appended to the operator's sentence.

    An account that reads clear BECAUSE this system took its own rows out of
    it must say so. Silence here would make the exclusion invisible at exactly
    the moment somebody is deciding to spend on the account.
    """
    excluded = [e for e in (account.get("our_staging_excluded") or [])
                if isinstance(e, dict)]
    if not excluded:
        return ""
    ids = sorted({str(e.get("campaign_id")) for e in excluded})
    return (f" ({len(excluded)} membership row(s) of our own campaign(s) "
            f"{', '.join(ids)} excluded: each is proven at the provider to "
            f"have sent nothing to anybody)")


# ------------------------------------------------------- LEAD KLASIFIKACIJA
#
# THE OPERATOR'S PERMANENT RULE, 2026-10-01. It REPLACES "zero previous
# emails", and it replaces the 30-day cold-or-not binary that briefly stood in
# its place. `docs/OPERATING-MODE.md` carries the original under "LEAD
# KLASIFIKACIJA" and names where it goes: "implementira se u `eligibility` i u
# collision putu".
#
# FIVE OUTCOMES, MUTUALLY EXCLUSIVE, EVALUATED IN ORDER. The order is the rule,
# not a convenience: step 3 asks a question that only makes sense once steps 1
# and 2 have not answered, and a lead that would trip two steps belongs to the
# earlier one.
#
#   1  BLOCKED      a negative reply, DNC, unsubscribe, opt-out, bounce or
#                   invalid address, operator exclusion or suppression list -
#                   FROM ANY SOURCE: Resonate OS, an internal or manual
#                   campaign, HeyReach, or somebody's hand. Status is
#                   authoritative, never the replies counter. A live
#                   conversation or a positive reply is ALSO step 1: it goes to
#                   a HUMAN, not to automated outreach.
#   2  ON HOLD      the lead is CURRENTLY in a live campaign on any channel
#                   belonging to ANYONE - ours, internal, or manual - at
#                   `in_sequence`/`active`/`queued`/`pending`, or in a PAUSED
#                   campaign where it still holds non-terminal rows a resume
#                   would release. Treated as contacted, not touched, and
#                   re-evaluated when that campaign ends. THE LEGACY RESONATE
#                   OS CAMPAIGNS ARE THIS CASE: 1,555 rows sit behind a pause
#                   and their leads are ON HOLD until the operator formally
#                   closes them, not COLD.
#   3  OURS?        DID RESONATE OS CONTACT THEM? The authority is provider
#                   truth about sends or actions in campaigns POSITIVELY
#                   RECORDED AS RESONATE OS IN THE LEDGER - `work/
#                   campaigns.jsonl`, written by our own factory - on both
#                   channels. NOT the local touch ledger on its own, which is
#                   known to be empty: 912 provider-confirmed sends against
#                   one recorded touch.
#                     YES -> STARI LEAD -> REVIVAL (step 5)
#                     NO  -> COLD LEAD -> a completely new approach, full
#                            sequence, new copy, REGARDLESS of how much
#                            internal or manual history exists. MANUAL HISTORY
#                            DOES NOT MAKE A LEAD OURS.
#                     Undeterminable -> UNKNOWN -> BLOCKED until determined.
#                            UNKNOWN never becomes cold and never becomes
#                            revival.
#   4  THE GAP      a COLD lead contacted by a manual or internal campaign
#                   inside the last N days WAITS until N days have passed. N is
#                   a CONFIG value - see `settings` - because the operator is
#                   still deciding it and it must change in one edit rather
#                   than in code. 0 means no gap.
#   5  REVIVAL      PROPOSED, NOT YET APPROVED. Until the operator approves the
#                   first revival send, revival leads are CLASSIFIED ONLY and
#                   never sent. Minimum 30 days since OUR last touch, a new
#                   angle and new copy rather than a repeat, a shorter
#                   sequence, and copy that neither pretends to be a first
#                   contact nor rewrites the old messages.
#
# WHY THE WHOLE THING IS HERE AND NOT IN `eligibility`. Steps 1 to 4 are facts
# only the provider and our own campaign ledger hold. `claims.prior_contact`
# reads `rec["events"]` and nothing else - correctly, because it answers "what
# did WE do" - so a person worked by an internal campaign carries no local
# event and reads as never contacted. That is the defect this module exists
# for, and step 3 is the same defect asked the other way round.

#: The numbers and the one flag the operator controls, with the values that
#: apply when the client's own file says nothing.
DEFAULTS = {
    # STEP 4. The operator proposed 14 and is still deciding, so this is a
    # config value and NOT a constant somebody has to find in code. 0 means no
    # gap at all.
    "manual_gap_days": 14,
    # STEP 5. Minimum days since OUR OWN last touch before a revival is even a
    # candidate. Distinct from `revival.DEFAULTS["cooling_days"]` (90), which
    # is about re-approaching an ACCOUNT after a campaign ran its course, and
    # from `eligibility.DEFAULT_MIN_SEPARATION_DAYS` (one cadence day, between
    # two touches inside one plan). Three questions, three numbers.
    "revival_after_days": 30,
    # STEP 5. REVIVAL IS PROPOSED AND NOT APPROVED. False means a revival lead
    # is classified and never sent. Only the operator flips this.
    "revival_approved": False,
}

#: Where the three live in a client's own file. One edit, no code change.
SETTINGS_BLOCK = "recontact"


def settings(config=None):
    """The operator's three knobs, read from the CLIENT'S OWN YAML.

        recontact:
          manual_gap_days: 14        # 0 means no gap at all
          revival_after_days: 30
          revival_approved: false

    Absent keys take `DEFAULTS`, so the file need only carry the one being
    changed. `0` IS A VALUE AND NOT AN ABSENCE - the operator said 0 means no
    gap - so presence is tested with `in` rather than by truthiness, which is
    the difference between "no gap" and "the default 14".
    """
    block = {}
    if isinstance(config, dict):
        found = config.get(SETTINGS_BLOCK)
        if isinstance(found, dict):
            block = found
    out = dict(DEFAULTS)
    for name in DEFAULTS:
        if name in block:
            out[name] = block[name]
    for name in ("manual_gap_days", "revival_after_days"):
        try:
            out[name] = max(0, int(out[name]))
        except (TypeError, ValueError):
            # AN UNREADABLE NUMBER IS NOT ZERO. Zero means "no gap", which is a
            # decision; a typo must not silently become that decision.
            raise CollisionUnknown(
                f"{SETTINGS_BLOCK}.{name} is {out[name]!r}, which is not a "
                f"number of days. Refusing to guess - 0 means NO GAP and is a "
                f"decision somebody makes, not a fallback.")
    out["revival_approved"] = bool(out["revival_approved"])
    return out


#: The membership word for an opt-out. Deliberately NOT added to
#: `KNOWN_STATUSES`: nobody here has read one back from this estate, so the
#: existing account gate must keep holding on it. It is named so that when it
#: does arrive the reason reads "unsubscribed" rather than "a word nobody has
#: verified", and so the permanent set below can be spelled once.
UNSUBSCRIBED_STATUS = "unsubscribed"

#: STEP 2. Membership statuses that mean a campaign is working this lead RIGHT
#: NOW. `in_sequence` is the only one this estate has been observed to use; the
#: other three are named by the operator's rule. None of those three is in
#: `KNOWN_STATUSES`, so each would reach UNKNOWN and hold anyway - they are
#: named here so the REASON reads "in an active campaign" rather than "a word
#: nobody has verified the meaning of", which is the difference between a
#: sentence an operator can act on and one they have to investigate.
ACTIVE_MEMBERSHIP = frozenset({IN_SEQUENCE, "active", "queued", "pending"})

#: STEP 2. A PAUSE IS NOT AN ENDING. `sending_paused` flips back to
#: `in_sequence` the moment somebody resumes - this module's own header records
#: measuring that - so a lead holding it still has rows a resume would release.
#: This is what puts the 1,555 legacy rows ON HOLD rather than COLD.
PAUSED_MEMBERSHIP = frozenset({SENDING_PAUSED})

#: Terminal for this person: the campaign is over for them and a resume
#: releases nothing. `STOPPED` IS DELIBERATELY ABSENT - it is terminal in that
#: sense and NOT harmless, because the provider does not record who stopped it:
#: us, an unsubscribe, or the provider itself acting on a reply.
#: `account_policy` already holds on exactly that ambiguity, and this rule must
#: not resolve it in favour of sending, so `stopped` reaches UNKNOWN through
#: `SUSPECT_STATUSES`.
TERMINAL_MEMBERSHIP = frozenset({"sequence_finished", REPLIED, BOUNCED,
                                 UNSUBSCRIBED_STATUS})

#: STEP 1. Membership and queue statuses that disqualify the person FOREVER.
#: `bounced` is about the address; the rest are the person's own instruction.
#: None is ever lifted by a clock.
PERMANENT_MEMBERSHIP = frozenset({BOUNCED, UNSUBSCRIBED_STATUS, "complained",
                                  "blocked", "suppressed", "invalid"})

#: STEP 1, the reply half. Read from `replies`' own vocabulary rather than
#: restated, so a class renamed there is an import error here instead of a
#: silent reclassification. BOTH SETS ARE STEP 1 - the rule puts a negative
#: reply and a positive one in the same outcome for different reasons, one
#: because it is permanent and one because it belongs to a person - and they
#: are kept apart only so the sentence an operator reads is the right one.
PERMANENT_REPLIES = frozenset({replies.NEGATIVE, replies.UNSUBSCRIBE,
                               replies.ACCOUNT_DNC, replies.NOT_RELEVANT})

#: `not_now` is in the HUMAN half because the operator's rule names "get back
#: to me later" as a person's to answer, not a timer's. `unknown` and every
#: unlisted class are human too - see `_reply_decision`.
HUMAN_REPLIES = frozenset({replies.POSITIVE, replies.INTERESTED,
                           replies.MEETING_INTENT, replies.QUESTION,
                           replies.SEND_INFO, replies.REFERRAL,
                           replies.NOT_NOW, replies.OBJECTION})

# How a lookup answered. The two that ANSWER are `ok` and `absent`; everything
# else is the absence of an answer and reaches step 3's "undeterminable".
#
# `absent` IS AN ANSWER AND `not_asked` IS NOT, and conflating them is the
# failure mode this whole module was built around: "there is no lead at this
# address" and "nobody looked" must never collapse into one word.
LOOKUP_OK = "ok"
LOOKUP_ABSENT = "absent"
LOOKUP_FAILED = "failed"
LOOKUP_PARTIAL = "partial"
LOOKUP_NOT_ASKED = "not_asked"
LOOKUP_NO_IDENTIFIER = "no_identifier"
LOOKUPS = (LOOKUP_OK, LOOKUP_ABSENT, LOOKUP_FAILED, LOOKUP_PARTIAL,
           LOOKUP_NOT_ASKED, LOOKUP_NO_IDENTIFIER)
LOOKUPS_THAT_ANSWER = frozenset({LOOKUP_OK, LOOKUP_ABSENT})

# THE FIVE OUTCOMES. Vocabulary: renaming one breaks the ramp report, and the
# buckets are counted by these strings.
CLASS_BLOCKED = "blocked"            # step 1
CLASS_ON_HOLD = "on_hold"            # step 2
CLASS_UNKNOWN = "unknown"            # step 3c - blocked until determined
CLASS_REVIVAL = "revival"            # step 3a -> step 5
CLASS_COLD = "cold"                  # step 3b, gap satisfied
CLASS_COLD_WAITING = "cold_waiting"  # step 3b, waiting out step 4's gap
CLASSES = (CLASS_BLOCKED, CLASS_ON_HOLD, CLASS_UNKNOWN, CLASS_REVIVAL,
           CLASS_COLD, CLASS_COLD_WAITING)

#: The classes that permit an automated send RIGHT NOW. Exactly one, which is
#: the point of the rule.
SENDABLE_CLASSES = frozenset({CLASS_COLD})


def _aware(value):
    """`value` as an aware datetime, or None.

    A NAIVE TIMESTAMP IS UNREADABLE RATHER THAN ASSUMED TO BE UTC, which is
    `executionguard._at`'s rule and `conversation._at`'s before it. Guessing a
    zone on a window check moves the boundary by up to a day in the direction
    nobody would notice: a touch from 30 days and two hours ago reading as 31.
    An unreadable date reaches step 3c and blocks, which is the point.
    """
    try:
        parsed = datetime.datetime.fromisoformat(str(value or "").strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else None


def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


def dated_sends(rows, only_campaigns=None):
    """Every row in `rows` that is a SEND WITH A DATE, oldest first.

    WHAT A SEND IS, and nothing else qualifies: a queue row reading `sent`
    carrying a `sent_at` that parses to an aware datetime. `scheduled`,
    `active`, `paused` and `stopped` are not sends, and a `sent` row whose
    `sent_at` is null is not one either - the provider writes that shape, and
    `docs/REENGAGEMENT-COHORT-PROVIDER-CONFIRMED-2026-09-24.md` measured it.

    `only_campaigns` restricts to a set of campaign ids, which is how step 3
    asks "what did RESONATE OS send" separately from "what did anybody send".

    Returned sorted by date rather than in arrival order, so no caller can come
    to depend on the provider's paging order by accident. See `last_send_at`
    for why that order is not trusted at all.
    """
    wanted = None
    if only_campaigns is not None:
        wanted = {_int(c) for c in only_campaigns}
        wanted.discard(None)
    found = []
    for row in rows or ():
        if not isinstance(row, dict):
            continue
        if _norm(row.get("status")) != "sent":
            continue
        if wanted is not None and _int(row.get("campaign_id")) not in wanted:
            continue
        when = _aware(row.get("sent_at"))
        if when is None:
            continue
        found.append((when, row))
    found.sort(key=lambda pair: pair[0])
    return [row for _when, row in found]


def last_send_at(rows, claimed=None, complete=None, only_campaigns=None):
    """The last ACTUAL send to one person, and whether it is PROVEN.

    Returns `(when, detail)`. `when` is an aware datetime or None, and it is
    only ever non-None when `detail["proven"]` is True - a caller cannot read a
    date out of this that the evidence does not support.

    THE FIFTEEN-ROW TRAP, AND WHY THIS DOES NOT RELY ON THE ORDERING.
    `GET /leads/{id}/scheduled-emails` serves FIFTEEN ROWS PER PAGE whatever
    `per_page` says, newest first. A caller that reads page one and takes the
    first row relies on an ordering the provider never promised, and the
    failure is silent AND one-directional: if the newest rows are not on page
    one, the date computed is TOO OLD, and too old is the direction that turns
    somebody emailed last week into a cold lead.

    So the ordering is not relied on. Two independent things are required:

      `complete`  the walk read EVERY page. A maximum over a complete set is
                  the true maximum whatever order the rows arrived in, which
                  makes the provider's ordering irrelevant rather than trusted.
                  A truncated read is undeterminable, full stop.
      `claimed`   the provider's own send count for this person - for the whole
                  person, or for the subset of campaigns asked about. Fewer
                  dated rows than that means a send exists that cannot be
                  dated, and the undated one could be yesterday.

    `detail["ordering"]` records whether the rows ARRIVED newest-first, for the
    operator who wants to know. It is reported and never relied on: it is
    evidence about the pages that were read, not a promise about the ones that
    were not, and treating it as proof is the mistake this docstring exists to
    prevent.
    """
    sends = dated_sends(rows, only_campaigns=only_campaigns)
    detail = {
        "dated_sends": len(sends),
        "claimed_sends": claimed,
        "complete": bool(complete),
        "ordering": _arrival_ordering(rows, only_campaigns=only_campaigns),
        "proven": False,
    }
    if not complete:
        detail["why"] = ("the per-lead send history was not read to the end, "
                         "so the newest send may be on a page nobody read")
        return None, detail
    if claimed is not None and len(sends) < int(claimed or 0):
        detail["why"] = (f"the provider counts {int(claimed or 0)} send(s) here "
                         f"and only {len(sends)} of them carry a date; an "
                         f"undated send could be yesterday")
        return None, detail
    if not sends:
        detail["proven"] = True
        detail["why"] = "no dated send exists here"
        return None, detail
    when = _aware(sends[-1].get("sent_at"))
    detail["proven"] = True
    detail["last_sent_at"] = sends[-1].get("sent_at")
    detail["last_campaign_id"] = sends[-1].get("campaign_id")
    detail["why"] = ("the maximum over a complete read, which does not depend "
                     "on the order the provider served the pages in")
    return when, detail


def _arrival_ordering(rows, only_campaigns=None):
    """Did the dated rows ARRIVE newest-first? Reported, never relied on."""
    wanted = None
    if only_campaigns is not None:
        wanted = {_int(c) for c in only_campaigns}
        wanted.discard(None)
    dates = []
    for row in rows or ():
        if not isinstance(row, dict) or _norm(row.get("status")) != "sent":
            continue
        if wanted is not None and _int(row.get("campaign_id")) not in wanted:
            continue
        when = _aware(row.get("sent_at"))
        if when is not None:
            dates.append(when)
    if len(dates) < 2:
        return "unprovable: fewer than two dated rows"
    if all(a >= b for a, b in zip(dates, dates[1:])):
        return "consistent with newest-first"
    if all(a <= b for a, b in zip(dates, dates[1:])):
        return "consistent with oldest-first"
    return "neither: the rows are not sorted by date"


def _reply_decision(classification):
    """Which SENTENCE a classified reply gets. Both halves are step 1.

    An UNCLASSIFIED OR UNRECOGNISED REPLY IS A HUMAN'S, not a nothing. The
    rule's step 1 ends "a live conversation or a positive reply goes to a
    HUMAN", and a reply nobody could classify is precisely a reply somebody has
    to read. Defaulting the other way would send automated outreach into an
    open thread, which is the one outcome every step here exists to prevent.
    """
    name = _norm(classification)
    if name in PERMANENT_REPLIES:
        return "permanent"
    return "human"


def os_campaign_ids():
    """The provider campaign ids POSITIVELY RECORDED AS RESONATE OS.

    Returns `(ids, readable)`. STEP 3'S WHOLE AUTHORITY IS THIS SET, and the
    second element is why it is not just a set: `campaign_bindings` returns
    `{}` both when the ledger says we own nothing AND when the ledger could not
    be read at all, and under this rule those two have opposite consequences.
    An empty-but-read ledger makes every lead COLD, which is correct - manual
    history does not make a lead ours. An UNREADABLE ledger making every lead
    COLD would hand a full new sequence to every person we have already
    written to, so it is step 3c instead.

    Measured 2026-10-01: `work/campaigns.jsonl` holds twenty bound provider
    campaigns, 451 to 506. Campaigns 274, 327, 328 and 352 are NOT among them,
    which IS the ledger proof that they are not ours however much they have
    sent - together roughly 209,000 emails.
    """
    from . import campaigns

    try:
        rows = list(campaigns.load())
    except Exception:                                          # noqa: BLE001
        return frozenset(), False
    found = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        bound = _int(row.get("bison_campaign_id"))
        if bound is None:
            try:
                bound = int(str(row.get("bison_campaign_id")).strip())
            except (TypeError, ValueError):
                continue
        if bound is not None:
            found.add(bound)
    return frozenset(found), True


def email_history(lead_row=None, lookup=LOOKUP_NOT_ASKED, sent_rows=(),
                  sends_lookup=LOOKUP_NOT_ASKED, sends_complete=None,
                  bindings=None, os_campaigns=None, ledger_readable=None):
    """One person's EMAIL history, SPLIT BY WHO SENT IT.

    Built from the raw provider lead row through `touches_of`, so a caller
    cannot hand this a shape the provider does not produce, and through
    `without_our_staging`, so this system's own silent staging is not read as
    the client's history - the lesson `check_address` learned on campaign 487.

    THE SPLIT IS THE NEW PART AND IT IS WHAT STEP 3 ASKS. `ours` counts only
    campaigns in `os_campaigns` - the ledger's own set - and `anyone` counts
    every campaign. Each side carries its own claim and its own proof, so
    "Resonate OS last wrote 40 days ago" and "somebody last wrote 5 days ago"
    are two separately provable facts rather than one number with a guess
    attached.
    """
    if os_campaigns is None:
        os_campaigns, readable = os_campaign_ids()
    else:
        os_campaigns = frozenset(c for c in
                                 ({_int(x) for x in os_campaigns} - {None}))
        readable = True
    if ledger_readable is not None:
        readable = bool(ledger_readable)
    out = {"channel": "email", "lookup": _norm(lookup) or LOOKUP_NOT_ASKED,
           "sends_lookup": _norm(sends_lookup) or LOOKUP_NOT_ASKED,
           "active": [], "paused": [], "unknown_statuses": [],
           "permanent": [], "answered": [], "suspect": [], "memberships": 0,
           "claimed_sends": 0, "staging_excluded": [],
           "ledger_readable": readable,
           "os_campaigns_seen": [], "other_campaigns_seen": [],
           "ours": {"claimed": 0, "last_touch_at": None,
                    "last_send": {"proven": False, "dated_sends": 0,
                                  "why": "the lookup did not answer"}},
           "anyone": {"claimed": 0, "last_touch_at": None,
                      "last_send": {"proven": False, "dated_sends": 0,
                                    "why": "the lookup did not answer"}}}
    if out["lookup"] not in LOOKUPS_THAT_ANSWER:
        return out
    if not isinstance(lead_row, dict):
        # An answered lookup with no row IS an answer: nobody at the provider
        # holds this address, so no email touch can have happened through it.
        out["lookup"] = LOOKUP_ABSENT
        for side in ("ours", "anyone"):
            out[side]["last_send"] = {"proven": True, "dated_sends": 0,
                                      "why": "no lead row at this address"}
        return out
    found = touches_of(lead_row)
    found, excluded = without_our_staging(found, bindings)
    out["staging_excluded"] = excluded
    out["email"] = found.get("email")
    out["lead_id"] = found.get("lead_id")
    out["lead_status"] = _norm(found.get("lead_status"))
    members = [c for c in (found.get("campaigns") or []) if isinstance(c, dict)]
    out["memberships"] = len(members)
    per_campaign = 0
    for entry in members:
        status = _norm(entry.get("status"))
        cid = _int(entry.get("campaign_id"))
        sent = int(_int(entry.get("emails_sent")) or 0)
        per_campaign += sent
        if cid in os_campaigns:
            out["os_campaigns_seen"].append(cid)
            out["ours"]["claimed"] += sent
        else:
            out["other_campaigns_seen"].append(cid)
        if status in ACTIVE_MEMBERSHIP:
            out["active"].append(cid)
        elif status in PAUSED_MEMBERSHIP:
            out["paused"].append(cid)
        elif status in PERMANENT_MEMBERSHIP:
            out["permanent"].append((cid, status))
        elif status in ANSWERED_STATUSES:
            # THE STATUS IS AUTHORITATIVE, NOT THE COUNTER. grayloon.com
            # carries campaign 274 with status `replied` and `replies: 0` on
            # the same row. A gate that read the counter called that account
            # unanswered. The status wins, and the counter is not consulted
            # here at all.
            out["answered"].append((cid, status))
        elif status in SUSPECT_STATUSES:
            out["suspect"].append((cid, status))
        elif status in TERMINAL_MEMBERSHIP:
            pass
        elif status:
            out["unknown_statuses"].append(status)
        else:
            out["unknown_statuses"].append("<empty>")
        if entry.get("interested"):
            out["answered"].append((cid, "interested"))
    if int(found.get("replies") or 0) > 0:
        out["answered"].append((None, "overall_stats.replies"))
    if out["lead_status"] in PERMANENT_MEMBERSHIP:
        out["permanent"].append((None, out["lead_status"]))
    out["claimed_sends"] = max(int(found.get("emails_sent") or 0), per_campaign)
    out["anyone"]["claimed"] = out["claimed_sends"]
    out["unknown_statuses"] = sorted(set(out["unknown_statuses"]))
    out["os_campaigns_seen"] = sorted(c for c in out["os_campaigns_seen"]
                                      if c is not None)
    out["other_campaigns_seen"] = sorted(c for c in out["other_campaigns_seen"]
                                         if c is not None)

    # The dates, and only where the evidence carries them. A person the
    # provider counts no sends for needs no queue read at all: zero claimed
    # sends is proven by the same row the memberships came from.
    if not out["claimed_sends"]:
        for side in ("ours", "anyone"):
            out[side]["last_send"] = {
                "proven": True, "dated_sends": 0,
                "why": "the provider counts no send to this person"}
        return out
    if out["sends_lookup"] not in LOOKUPS_THAT_ANSWER:
        for side in ("ours", "anyone"):
            out[side]["last_send"] = {
                "proven": False, "dated_sends": 0,
                "claimed_sends": out[side]["claimed"],
                "why": (f"the provider counts {out['claimed_sends']} send(s) "
                        f"and the per-lead send history answered "
                        f"{out['sends_lookup']!r}")}
        return out
    when, detail = last_send_at(sent_rows, claimed=out["claimed_sends"],
                                complete=sends_complete)
    out["anyone"]["last_send"] = detail
    out["anyone"]["last_touch_at"] = when
    ours_when, ours_detail = last_send_at(
        sent_rows, claimed=out["ours"]["claimed"], complete=sends_complete,
        only_campaigns=os_campaigns)
    out["ours"]["last_send"] = ours_detail
    out["ours"]["last_touch_at"] = ours_when
    return out


def linkedin_history(conversation_rows=(), slug=None, lookup=LOOKUP_NOT_ASKED,
                     ours_recorded=None):
    """One person's LINKEDIN history, read the same way.

    `conversation_rows` must ALREADY be scoped to this client's own seats.
    `check_linkedin_profile` does that scoping and the reason is in its
    docstring: a conversation on a seat we do not own is another tenant's and
    must inform this verdict in neither direction.

    `ours_recorded` IS THE LEDGER'S ANSWER AND IT CANNOT BE DERIVED HERE. A
    HeyReach conversation carries no campaign id - the row has
    `correspondentProfile`, `linkedInAccount`, `totalMessages`, `lastMessageAt`
    and `lastMessageSender`, and nothing that names which campaign produced it.
    So whether a LinkedIn action was RESONATE OS's is settled by our own
    record that we staged this person into a HeyReach campaign of ours
    (`contact["heyreach_campaign_id"]`), which the caller supplies:

        True   the ledger records this person in a HeyReach campaign of ours,
               so a dated action on our seat counts as a Resonate OS contact
        False  the ledger records none, so by step 3's own construction this
               is not positively recorded as ours
        None   nobody asked. Treated as False for OWNERSHIP, which is what
               "positively recorded" means, and reported so the residual risk
               is visible rather than silent.
    """
    out = {"channel": "linkedin", "lookup": _norm(lookup) or LOOKUP_NOT_ASKED,
           "slug": slug, "conversations": 0, "answered": [], "undatable": [],
           "ours_recorded": ours_recorded,
           "ours": {"last_touch_at": None,
                    "last_send": {"proven": False,
                                  "why": "the lookup did not answer"}},
           "anyone": {"last_touch_at": None,
                      "last_send": {"proven": False,
                                    "why": "the lookup did not answer"}}}
    if out["lookup"] not in LOOKUPS_THAT_ANSWER:
        return out
    if not slug:
        out["lookup"] = LOOKUP_NO_IDENTIFIER
        return out
    newest = None
    for row in conversation_rows or ():
        if not isinstance(row, dict):
            continue
        found = linkedin_touches_of(row)
        if found.get("slug") != slug:
            continue
        out["conversations"] += 1
        if found.get("they_replied"):
            out["answered"].append(found.get("conversation_id"))
        when = _aware(found.get("last_message_at"))
        if not found.get("total_messages") or when is None:
            # Something happened on this thread and nothing here can date it.
            # `check_linkedin_profile` calls the zero-message case "a
            # conversation exists with no message counted" and reports TOUCHED
            # for it. It stays a touch, it carries no date, and an undatable
            # action is step 3c - never a step 4 pass.
            out["undatable"].append(found.get("conversation_id"))
            continue
        if newest is None or when > newest:
            newest = when
    proof = {"proven": not out["undatable"],
             "dated_conversations": out["conversations"] - len(out["undatable"]),
             "why": ("an action on this profile cannot be dated"
                     if out["undatable"] else
                     "the newest dated message on our own seats' threads")}
    out["anyone"]["last_touch_at"] = newest
    out["anyone"]["last_send"] = proof
    # OURS only when the ledger positively says so.
    out["ours"]["last_send"] = dict(proof)
    out["ours"]["last_touch_at"] = newest if ours_recorded else None
    return out


def recontact_dossier(email=None, linkedin_=None, suppression=(),
                      candidate_channel=None, reply_class=None):
    """Everything the five steps read, from both channels, in one dict.

    BOTH CHANNELS ARE REQUIRED WHATEVER CHANNEL IS SENDING, which is the
    operator's "on any channel" and also `account_policy`'s own hard-won rule:
    the email estate is read even when LinkedIn is the one about to send,
    because that is where the history lives. `candidate_channel` is carried for
    the report and decides nothing - a LinkedIn action blocks an email step and
    an email blocks a LinkedIn step, and the symmetry is the point.

    `suppression` is the local, already-decided half of step 1: whatever
    `agencydnc`, `operatorexclusion`, `hygiene` and the client's own
    suppression list already say, as strings. This does not re-derive them - a
    gate that classified a suppression reason again would be a second
    implementation of the one rule that must not have two. `reply_class` is
    `replies`' verdict for the same reason.
    """
    return {
        "email": email if isinstance(email, dict) else email_history(),
        "linkedin": (linkedin_ if isinstance(linkedin_, dict)
                     else linkedin_history()),
        "suppression": [s for s in (suppression or ()) if s],
        "reply_class": reply_class,
        "candidate_channel": candidate_channel,
    }


def classify(dossier, now=None, config=None, options=None):
    """THE FIVE STEPS, IN ORDER. `(decision, klass, why)`.

    `klass` is one of `CLASSES` and the five outcomes are mutually exclusive -
    the first step that answers, answers. `decision` is what the send path
    already consumes:

        CLASS_COLD           ALLOW   a new approach, full sequence, new copy
        CLASS_COLD_WAITING   HOLD    cold, waiting out step 4's gap
        CLASS_ON_HOLD        HOLD    somebody's live campaign has them
        CLASS_REVIVAL        HOLD    classified only until the operator
                                     approves the first revival send
        CLASS_BLOCKED        STOP
        CLASS_UNKNOWN        STOP    blocked until determined

    ONLY `CLASS_COLD` EVER ALLOWS, which is `SENDABLE_CLASSES`.
    """
    now = now or _utcnow()
    opts = dict(settings(config))
    if isinstance(options, dict):
        opts.update(options)
    mail = (dossier or {}).get("email") or {}
    link = (dossier or {}).get("linkedin") or {}
    suppression = [s for s in ((dossier or {}).get("suppression") or ()) if s]

    # ---- STEP 1: BLOCKED FOREVER, from ANY source.
    if suppression:
        return STOP, CLASS_BLOCKED, (
            f"permanently excluded: "
            f"{', '.join(sorted(set(map(str, suppression))))}. No source and "
            f"no clock lifts this")
    if mail.get("permanent"):
        return STOP, CLASS_BLOCKED, (
            f"the provider records {_pairs(mail['permanent'])} for this "
            f"person; a bounce or an opt-out is never lifted by a clock")
    answered = list(mail.get("answered") or ()) + list(link.get("answered") or ())
    if answered:
        if _reply_decision((dossier or {}).get("reply_class")) == "permanent":
            return STOP, CLASS_BLOCKED, (
                f"this person replied and the reply is classified "
                f"{_norm((dossier or {}).get('reply_class'))!r}; that is "
                f"permanent, whichever campaign or hand produced it")
        return STOP, CLASS_BLOCKED, (
            f"this person has replied, been marked interested, or has a live "
            f"conversation on one of our own seats "
            f"({_pairs(mail.get('answered') or ()) or 'linkedin'}"
            f"{'; ' + str(len(link.get('answered') or ())) + ' linkedin thread(s)' if link.get('answered') else ''}"
            f"). That goes to a HUMAN, never to automated outreach")

    # ---- STEP 2: ON HOLD. Anyone's live campaign, on any channel.
    if mail.get("active"):
        return HOLD, CLASS_ON_HOLD, (
            f"this person is in {len(mail['active'])} campaign(s) that are "
            f"running right now ({_ids(mail['active'])}), whoever owns them. "
            f"Treated as contacted; re-evaluate when that campaign ends")
    if mail.get("paused"):
        return HOLD, CLASS_ON_HOLD, (
            f"this person holds non-terminal rows in {len(mail['paused'])} "
            f"paused campaign(s) ({_ids(mail['paused'])}); a resume would "
            f"release them, so the pause is not an ending. The legacy Resonate "
            f"OS campaigns are this case until the operator closes them")

    # ---- STEP 3c FIRST, because steps 1 and 2 above are only as good as the
    # statuses they read, and step 3 cannot be asked at all without a readable
    # ledger. An unread status may be a campaign running right now.
    if mail.get("unknown_statuses"):
        return STOP, CLASS_UNKNOWN, (
            f"a campaign at this person reports "
            f"{', '.join(repr(s) for s in mail['unknown_statuses'])}, which "
            f"this system has no verified meaning for. It may be running right "
            f"now, and an unread status is not a finished one")
    if mail.get("suspect"):
        return STOP, CLASS_UNKNOWN, (
            f"a campaign at this person ended early "
            f"({_pairs(mail['suspect'])}) and the status does not say whether "
            f"we stopped it, they unsubscribed, or the provider stopped it on "
            f"a reply")
    for side in (mail, link):
        if side.get("lookup") not in LOOKUPS_THAT_ANSWER:
            return STOP, CLASS_UNKNOWN, (
                f"the {side.get('channel')} lookup answered "
                f"{side.get('lookup')!r}, so nobody can say what has already "
                f"happened to this person there. UNKNOWN never becomes cold "
                f"and never becomes revival")
    if link.get("undatable"):
        return STOP, CLASS_UNKNOWN, (
            f"{len(link['undatable'])} LinkedIn thread(s) with this person "
            f"carry an action nothing here can date")
    if not mail.get("ledger_readable", True):
        # THE FILENAME IS DELIBERATELY NOT IN THIS STRING. `store` is the one
        # module allowed to name a state file in code, and
        # `tests/test_invariants.py` enforces it - a path spelled anywhere else
        # drifts from `store`'s own resolution the moment a test or a worktree
        # redirects it, which is precisely the condition this message reports.
        return STOP, CLASS_UNKNOWN, (
            "the campaign ledger could not be read, so there is no way to tell "
            "a Resonate OS campaign from somebody else's. Calling that COLD "
            "would hand a full new sequence to everybody we have already "
            "written to")
    for side in (mail, link):
        for owner in ("ours", "anyone"):
            proof = (side.get(owner) or {}).get("last_send") or {}
            if not proof.get("proven"):
                return STOP, CLASS_UNKNOWN, (
                    f"the {side.get('channel')} send history is not proven for "
                    f"{owner}: {proof.get('why') or 'no evidence'}")

    # ---- STEP 3: DID RESONATE OS CONTACT THEM?
    ours = [(side.get("channel"), (side.get("ours") or {}).get("last_touch_at"))
            for side in (mail, link)
            if (side.get("ours") or {}).get("last_touch_at") is not None]
    if ours:
        # 3a - STARI LEAD -> step 5, REVIVAL.
        channel, last = max(ours, key=lambda pair: pair[1])
        days = (now - last).days
        if days < opts["revival_after_days"]:
            return HOLD, CLASS_REVIVAL, (
                f"Resonate OS last touched this person on {channel} {days} "
                f"day(s) ago, inside the {opts['revival_after_days']}-day "
                f"revival minimum. This is a STARI LEAD on the revival track, "
                f"not a cold lead, and it is too soon")
        if not opts["revival_approved"]:
            return HOLD, CLASS_REVIVAL, (
                f"STARI LEAD: Resonate OS last touched this person on "
                f"{channel} {days} day(s) ago, past the "
                f"{opts['revival_after_days']}-day minimum. REVIVAL IS "
                f"PROPOSED AND NOT APPROVED, so this is CLASSIFIED ONLY and "
                f"nothing may be sent. The copy, when it is approved, needs a "
                f"new angle and a shorter sequence, and must neither pretend "
                f"to be a first contact nor rewrite the old messages")
        return ALLOW, CLASS_REVIVAL, (
            f"STARI LEAD, revival approved: Resonate OS last touched this "
            f"person on {channel} {days} day(s) ago. New angle, new copy, "
            f"shorter sequence; not a first contact and not a repeat")

    # ---- 3b - COLD. Manual history does not make a lead ours.
    anyone = [(side.get("channel"),
               (side.get("anyone") or {}).get("last_touch_at"))
              for side in (mail, link)
              if (side.get("anyone") or {}).get("last_touch_at") is not None]
    manual = (f"{mail.get('other_campaigns_seen') and len(mail['other_campaigns_seen']) or 0} "
              f"internal/manual campaign(s)")
    if not anyone:
        return ALLOW, CLASS_COLD, (
            "no dated touch from anybody on either channel, and nothing from "
            "Resonate OS. A COLD LEAD and a genuine first contact: full "
            "sequence, new copy")
    channel, last = max(anyone, key=lambda pair: pair[1])
    days = (now - last).days
    # ---- STEP 4: THE GAP. N is config, and 0 means no gap.
    gap = opts["manual_gap_days"]
    if gap and days < gap:
        return HOLD, CLASS_COLD_WAITING, (
            f"COLD - Resonate OS has never contacted this person, and {manual} "
            f"did: the last was on {channel} {days} day(s) ago, inside the "
            f"{gap}-day gap. It WAITS until {gap} day(s) have passed")
    return ALLOW, CLASS_COLD, (
        f"COLD LEAD: Resonate OS has never contacted this person. {manual} "
        f"touched them, last on {channel} {days} day(s) ago, which clears the "
        f"{gap}-day gap. A completely new approach - full sequence, new copy - "
        f"and the copy must not pretend this is a first contact when somebody "
        f"else has already written, nor mention the prior campaigns")


def _ids(values):
    return ", ".join(str(v) for v in values)


def _pairs(values):
    out = []
    for entry in values:
        if isinstance(entry, (tuple, list)) and len(entry) == 2:
            where, what = entry
            out.append(f"{what}" if where is None else f"{what} on {where}")
        else:
            out.append(str(entry))
    return ", ".join(out)


#: The per-lead queue route. `GET /leads/{id}/scheduled-emails` returns every
#: queue row for ONE person ACROSS EVERY CAMPAIGN, including campaigns far too
#: large to walk per-campaign - 352's own queue is 96,419 rows over 6,428
#: pages, and 274/327/328/352 are exactly the four walks that did not complete
#: in `work/collision-index.json`. That is why this route and not the
#: per-campaign one: it is the only read that can date a send inside a campaign
#: nobody can enumerate. Measured at scale on 2026-09-24 over 2,081 candidates,
#: where it took `unread_campaign` from 1,284 to 0
#: (`docs/REENGAGEMENT-COHORT-PROVIDER-CONFIRMED-2026-09-24.md`).
LEAD_QUEUE_PATH = "/leads/{lead_id}/scheduled-emails"

#: Pages of one person's queue this will walk. Twenty-three sends is the most
#: this estate has been observed to hold against one person, so forty pages is
#: six hundred rows of headroom. PAST IT THIS RAISES rather than returning a
#: prefix: a short read of a send history is the one thing that turns somebody
#: emailed yesterday into a cold lead, and `last_send_at` is built to refuse a
#: truncated read for exactly that reason.
LEAD_QUEUE_PAGE_CAP = 40


def lead_sends(lead_id, cap=LEAD_QUEUE_PAGE_CAP, path=LEAD_QUEUE_PATH):
    """Every queue row the provider holds for one person. Read-only, GET only.

    Returns `(rows, detail)` where `detail["complete"]` is True ONLY when every
    page was read and the count reconciles with the provider's own
    `meta.total`. `last_send_at` will not produce a date without it.

    An unreadable `last_page` IS NOT A LAST PAGE, which is `leads_for_domain`'s
    hard-won rule and matters more here: that function's failure returns too
    few leads, and this one's returns a date that is too OLD, which is the
    direction nobody notices.
    """
    try:
        key = int(str(lead_id).strip())
    except (TypeError, ValueError):
        raise CollisionUnknown(f"{lead_id!r} is not a lead id to read")
    url = bison.base() + path.format(lead_id=key)
    rows, page, total = [], 1, None
    while page <= cap:
        status, data = request("GET", f"{url}?page={page}", bison.headers())
        if not ok(status):
            raise CollisionUnknown(
                f"emailbison lead queue: GET {path.format(lead_id=key)} "
                f"page {page} -> {status}")
        if not isinstance(data, dict):
            raise CollisionUnknown("emailbison lead queue: unexpected shape")
        chunk = data.get("data")
        if not isinstance(chunk, list):
            raise CollisionUnknown(
                "emailbison lead queue: no `data` array; refusing to read "
                "that as no prior send")
        rows += chunk
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        if total is None:
            total = meta.get("total")
        try:
            last = int(meta.get("last_page"))
        except (TypeError, ValueError):
            if not chunk:
                break
            raise CollisionUnknown(
                f"emailbison lead queue: page {page} returned {len(chunk)} "
                f"row(s) and no readable `last_page`, so nothing can tell "
                f"whether a newer send is on a page that was not read")
        if page >= last:
            break
        page += 1
    else:
        raise CollisionUnknown(
            f"emailbison lead queue: lead {key} needs more than {cap} pages. "
            f"Refusing to return a prefix: the newest send would be the row "
            f"most likely to be missing from it")
    if isinstance(total, int) and len(rows) != total:
        raise CollisionUnknown(
            f"emailbison lead queue: meta.total says {total} and {len(rows)} "
            f"arrived for lead {key}. A partial send history cannot date a "
            f"last touch")
    return rows, {"complete": True, "rows": len(rows), "pages": page,
                  "route": path, "lead_id": key}


def recontact_check(address, profile_url=None, name=None,
                    expect_workspace=REQUIRED, client=None, suppression=(),
                    reply_class=None, now=None, config=None, options=None,
                    ours_recorded=None, os_campaigns=None):
    """THE LIVE, END-TO-END ANSWER to the operator's lead classification.

    Returns `(decision, code, why, dossier)`. Read-only: every provider call
    below is a GET, and nothing is cached across processes.

    BOTH CHANNELS, WHATEVER CHANNEL IS SENDING, which is the rule's "on ANY
    channel" and `account_policy`'s own lesson. A channel that could not be
    read answers `failed` and reaches clause (e), so this never returns a cold
    verdict from half an answer.

    `ours_recorded` IS THE LEDGER'S LINKEDIN ANSWER and cannot be derived from
    a HeyReach conversation - see `linkedin_history`. The caller passes what our
    own record says: True when this person sits in a HeyReach campaign of ours
    (`contact["heyreach_campaign_id"]`), False when it records none.

    THIS IS THE ONE LINE `executionguard.authorize` NEEDS. Gate 4 already makes
    three provider collision reads - `check_address`, `check_linkedin_profile`
    and `check_account`; the dossier this returns is the fourth, and passing it
    to `eligibility.decide(recontact_dossier=...)` is what makes the rule bite
    on a live send rather than merely be implemented.
    """
    # TWO SCOPES, AND THEY ARE NOT THE SAME STRING. `expect_workspace` is the
    # EmailBison workspace id (`clients.provider_workspace(config,
    # "emailbison")` - "10" for Productive) and it pins which estate the lead
    # read answered for. `client` is the canonical CLIENT id ("productive"),
    # which is what `our_linkedin_seats` and `_client_config` take, because the
    # LinkedIn seat roster is keyed by client and not by a HeyReach workspace -
    # `provider_workspace(config, "heyreach")` is None for this client.
    # Passing one where the other belongs resolves to an empty seat set, and an
    # unscoped inbox read as "no prior contact" is the exact failure
    # `check_linkedin_profile` was hardened against. There is no default.
    if expect_workspace is REQUIRED:
        raise CollisionUnknown(
            "recontact_check needs the workspace whose estate this is. An "
            "unpinned read cannot say whose history it answered for, and the "
            "credential's binding is chosen in the vendor UI.")
    if not client:
        raise CollisionUnknown(
            "recontact_check needs the client id whose LinkedIn seats these "
            "are. Without it the inbox is unscoped, and an unscoped inbox "
            "cannot certify that nobody has talked to this person.")
    address = _norm(address)
    if not address or "@" not in address:
        raise CollisionUnknown(f"{address!r} is not an address to check")

    # ---- the email side
    lead_row, lookup, sent_rows, sends_lookup, complete = None, None, (), None, False
    try:
        rows = leads_for_domain(address.rsplit("@", 1)[-1],
                                expect_workspace=expect_workspace)
        lookup = LOOKUP_ABSENT
        for row in rows:
            if isinstance(row, dict) and _norm(row.get("email")) == address:
                lead_row, lookup = row, LOOKUP_OK
                break
    except Exception:                                          # noqa: BLE001
        # NOT swallowed: `failed` is carried into the dossier and clause (e)
        # blocks on it. The exception type is not the answer a gate needs.
        lookup = LOOKUP_FAILED
    if lead_row is None:
        sends_lookup, complete = LOOKUP_ABSENT, True
    else:
        try:
            sent_rows, detail = lead_sends(lead_row.get("id"))
            sends_lookup, complete = LOOKUP_OK, bool(detail["complete"])
        except Exception:                                      # noqa: BLE001
            sent_rows, sends_lookup, complete = (), LOOKUP_FAILED, False
    mail = email_history(lead_row=lead_row, lookup=lookup, sent_rows=sent_rows,
                         sends_lookup=sends_lookup, sends_complete=complete,
                         os_campaigns=os_campaigns)

    # ---- the linkedin side, scoped to this client's own seats
    slug = profile_slug(profile_url) if profile_url else None
    if not slug:
        link = linkedin_history(lookup=LOOKUP_NO_IDENTIFIER, slug=None,
                                ours_recorded=ours_recorded)
    else:
        try:
            seats = seats_whose_conversations_are_ours(
                client, config=_client_config(client))
            term = (str(name or "").strip().split()[0] if str(name or "").strip()
                    else slug.replace("-", " "))
            ours = [row for row in conversations_named(term)
                    if isinstance(row, dict)
                    and str(linkedin_touches_of(row).get("our_seat")) in seats]
            link = linkedin_history(conversation_rows=ours, slug=slug,
                                    lookup=LOOKUP_OK,
                                    ours_recorded=ours_recorded)
        except Exception:                                      # noqa: BLE001
            link = linkedin_history(lookup=LOOKUP_FAILED, slug=slug,
                                    ours_recorded=ours_recorded)

    dossier = recontact_dossier(email=mail, linkedin_=link,
                                suppression=suppression,
                                reply_class=reply_class)
    decision, klass, why = classify(dossier, now=now, config=config,
                                    options=options)
    return decision, klass, why, dossier


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
