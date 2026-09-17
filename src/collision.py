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
    hits = [r for r in rows
            if isinstance(r, dict)
            and str(r.get("campaign_id") or "") == canonical
            and _norm(r.get("state")) in LEDGER_MAY_HAVE_REACHED]
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
        if _EVIDENCE[key].get("proven"):
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
    if not evidence.get("proven"):
        return False, "not proven to be our own silent staging"
    state = _norm(entry.get("status"))
    if state not in EXCLUDABLE_MEMBERSHIP:
        return False, (f"membership reads {state!r}, which our own zero-send "
                       f"staging does not leave behind")
    for field in ("emails_sent", "replies", "opens"):
        if _int(entry.get(field)) != 0:
            return False, (f"membership reports {field}="
                           f"{entry.get(field)!r}, which contradicts a "
                           f"campaign that has sent nothing")
    if entry.get("interested"):
        return False, "membership is marked interested"
    return True, evidence.get("why") or "our own proven-zero-send staging"


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
