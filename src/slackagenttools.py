#!/usr/bin/env python3
"""The bounded read-only tools the Slack agent may call before answering.

OPERATOR, 2026-09-21: "Bounded read-only tools the model may call before
answering (up to 5 per turn)."

## WHAT THE MODEL CHOOSES, AND WHAT IT DOES NOT

The model chooses a NAME from this registry and, at most, one string
argument. It does not choose a query, a table, a file or a verb. Every tool
is a Python function written here, every one of them reads, and the ones
that reach a provider reach it through `slackagentreadback`, whose import
contract forbids the write path.

So "call a tool" is the model picking one of thirteen buttons. A model that
picks the wrong button gets the wrong readback and says something unhelpful.
There is no button that changes anything.

## SCOPE IS CHECKED HERE, NOT AT THE PROMPT

`for_scope(scope)` returns only the tools that scope may call, and `run`
refuses a tool the scope does not carry even if it is asked for by name.
A client channel cannot call `who_does_what` or `credits`, and its
`lead_lookup` is pinned to its own workspace before the lookup happens - so
a prompt-injected "look up this lead at another client" reads that client's
store and finds nothing, because it never looks there.

## THE BUDGET

`MAX_CALLS_PER_TURN = 5`. Not a performance limit: an agent that can call
tools in a loop can be driven into one by a message, and a fixed budget
turns that from an outage into a worse answer.
"""
import json
import os
import time

from . import slackagentreadback as readback
from . import slackclientview as clientview
from . import slackknowledge as knowledge
from . import slackscope

MAX_CALLS_PER_TURN = 5

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class ToolRefused(RuntimeError):
    """The tool does not exist, or this scope may not call it."""


# ------------------------------------------------------------ the tools

def workspace_summary(scope, argument=None):
    """Everything configured for one client: ICP, personas, angles, caps."""
    slug = _workspace_for(scope, argument)
    pack = knowledge.pack()
    entry = (pack.get("workspaces") or {}).get(slug)
    if not entry:
        return {"read_at": _now(),
                "_error": "no workspace %r in the knowledge pack" % slug}
    return entry


def campaign_detail(scope, argument=None):
    """One campaign as the PROVIDER states it: status, sent, queue rows."""
    campaign_id = str(argument or "").strip()
    if not campaign_id.isdigit():
        return {"read_at": _now(),
                "_error": "campaign_detail needs a numeric campaign id"}
    if not _campaign_is_visible(scope, campaign_id):
        return {"read_at": _now(),
                "_error": "campaign %s does not belong to this channel's "
                          "workspace" % campaign_id}
    return readback.campaign_by_id(campaign_id)


def cadence_detail(scope, argument=None):
    """The sequence: email steps and the LinkedIn graph, day by day."""
    slug = _workspace_for(scope, argument)
    entry = (knowledge.pack().get("workspaces") or {}).get(slug) or {}
    cadence = entry.get("cadence")
    if not cadence:
        return {"read_at": _now(),
                "_error": "no cadence is configured for %s" % slug}
    return dict(cadence, workspace=slug, read_at=_now())


def lead_lookup(scope, argument=None):
    """One contact's state. A CLIENT channel may name its own people.

    An internal channel gets counts and domains, never an address - the rule
    the status channel already enforces. A client channel is looking at its
    own data in its own channel, so the address is theirs to see.
    """
    needle = str(argument or "").strip().lower()
    if not needle:
        return {"read_at": _now(), "_error": "lead_lookup needs an address"}
    slug = _workspace_for(scope, None)
    found = _find_contacts(slug, needle, limit=5)
    if not found:
        return {"read_at": _now(), "matches": 0,
                "note": "nothing in %s's store matches that" % slug}
    if not scope.is_client:
        # A NAME IS AS IDENTIFYING AS AN ADDRESS. The first version stripped
        # only `contact`, which left "Jacob Faertz" in an internal answer -
        # and `notify._status_payload` refuses a person's name for the same
        # reason it refuses a mailbox.
        for row in found:
            row.pop("contact", None)
            row.pop("name", None)
    return {"read_at": _now(), "workspace": slug, "matches": len(found),
            "leads": found}


def account_lookup(scope, argument=None):
    """One account by domain: state, contacts, and whether it is approved."""
    domain = str(argument or "").strip().lower().lstrip("@")
    if not domain:
        return {"read_at": _now(), "_error": "account_lookup needs a domain"}
    slug = _workspace_for(scope, None)
    rows = _records(slug)
    hits = [r for r in rows if domain in str(r.get("domain") or "").lower()]
    if not hits:
        return {"read_at": _now(), "workspace": slug, "matches": 0,
                "note": "no account in %s's store matches %s" % (slug, domain)}
    out = []
    for record in hits[:5]:
        contacts = _contacts_of(record)
        out.append({
            "domain": record.get("domain"),
            "state": record.get("state"),
            "icp_verdict": (record.get("icp") or {}).get("verdict"),
            "contacts": len(contacts),
            "sendable_contacts": len([c for c in contacts
                                      if c.get("sendable")]),
            "contact_states": _count(c.get("state") or c.get("verdict")
                                     for c in contacts),
            "in_campaigns": campaigns_of_record(slug, record.get("id")),
        })
    return {"read_at": _now(), "workspace": slug, "matches": len(hits),
            "accounts": out}


def sender_summary(scope, argument=None):
    """How many sending accounts are working this client's campaigns.

    COUNTS AND PROVIDER IDS ONLY. The people behind the estate are real
    humans whose names live in a gitignored file, and a client is owed the
    answer to "how many senders are sending for us" without being owed the
    roster. The campaign rows carry `provider_account_id`, which is exactly
    that: a count of distinct sending accounts, no name and no address.
    """
    slug = _workspace_for(scope, argument)
    rows = _campaign_rows(slug)
    email, linkedin = set(), set()
    volume = {"email": 0, "linkedin": 0}
    live = 0
    for row in rows:
        senders = row.get("senders") or {}
        for entry in senders.get("email") or []:
            email.add(str(entry.get("provider_account_id")
                          or entry.get("account_id")))
        for entry in senders.get("linkedin") or []:
            linkedin.add(str(entry.get("provider_account_id")
                             or entry.get("account_id")))
        if (row.get("status") or "").lower() in ("approved", "launched",
                                                 "active"):
            live += 1
            for channel in ("email", "linkedin"):
                value = (row.get("daily_volume") or {}).get(channel)
                if isinstance(value, int):
                    volume[channel] += value
    out = {"read_at": _now(), "workspace": slug,
           "email_sending_accounts": len(email),
           "linkedin_sending_accounts": len(linkedin),
           "campaigns_they_serve": len(rows),
           "campaigns_approved_or_live": live,
           "combined_daily_volume": volume}
    if not email and not linkedin:
        out["note"] = ("no sending account is bound to any campaign for "
                       "this workspace yet")
    else:
        out["note"] = ("a sending account is bound to a campaign; bound is "
                       "not the same as sending, and sends_today is the "
                       "figure that says what actually went out")
    return out


#: The bounce rate at which sending stops. A client is owed this number
#: beside their own senders' rates, because a rate means nothing without the
#: line it is measured against.
BOUNCE_HARD_STOP_PERCENT = 2.0


def sender_roster(scope, argument=None):
    """This client's OWN authorized senders, by name.

    OPERATOR, 2026-09-22: "a client's OWN senders are the client's own data.
    In #productive-resonate-outbound the agent may name Productive's
    authorized sender humans, say how many mailboxes and LinkedIn seats each
    has, their daily capacity, which campaigns they carry, and their health."

    THE PEOPLE SENDING FOR PRODUCTIVE ARE PRODUCTIVE'S OWN STAFF, and half
    of them are in that channel. Withholding their own colleagues' names
    from them was this module protecting the wrong thing.

    What it still refuses, and the refusals are structural rather than
    phrased:

    - Every row is filtered on `workspace` before it is read, so another
      client's senders are never in the material at all.
    - The provider's estate read is filtered against THIS workspace's own
      account ids rather than trusted to be scoped. A provider workspace is
      a binding beneath a client, not the client, and `PRODUCT-GOAL` says a
      credential that reaches an estate proves nothing about whose it is.
    - An account with no attestation is not in the roster. That is what
      keeps the three excluded identities out without naming them: they are
      excluded by having no attestation, so a filter on attestation cannot
      list them however the question is phrased.
    - The attestation's `by` text - which records how attestation works and
      who signed it - is never read into the answer.
    """
    slug = _workspace_for(scope, argument)
    try:
        from . import senderidentity, senderownership
        rows = senderidentity.load()
    except Exception as exc:                                    # noqa: BLE001
        return {"read_at": _now(), "workspace": slug,
                "_error": "sender roster unreadable: %s" % type(exc).__name__}

    # THE ATTESTATION DRIVES THE ROSTER, not the account's own `sender_id`.
    #
    # An account row imported from the provider carries no owner - 225
    # mailboxes arrived that way and 159 of them were attested afterwards -
    # so joining on the account's `sender_id` found nobody at all. The
    # attestation IS the authorization record, which makes it both the
    # correct join and the one that cannot list an unauthorized account:
    # walking attestations means an account with none is not reachable,
    # rather than reachable and then filtered.
    owned = {}
    for attestation in rows:
        if (attestation.get("kind") != "ownership_attestation"
                or attestation.get("workspace") != slug):
            continue
        owned.setdefault(attestation.get("sender_id"), {}).setdefault(
            attestation.get("channel"), set()).add(
                attestation.get("account_id"))
    if not owned:
        return {"read_at": _now(), "workspace": slug, "senders": [],
                "note": "no authorized sender is recorded for this workspace"}

    by_id = {p.get("sender_id"): p
             for p in senderidentity.senders(slug, rows=rows)}
    campaigns_by_account = _campaigns_by_sending_account(slug)
    bounce = _bounce_by_provider_account(slug, rows)

    out, mailboxes, seats = [], 0, 0
    for sender_id, channels in sorted(owned.items()):
        person = by_id.get(sender_id) or {}
        email = [a for a in senderidentity.email_accounts(
            slug, rows=rows, active_only=True)
            if a.get("account_id") in channels.get("email", ())]
        linkedin = [a for a in senderidentity.linkedin_accounts(
            slug, rows=rows, active_only=True)
            if _same_seat(a, channels.get("linkedin", ()))]
        if not email and not linkedin:
            # Authorized, but every account of theirs is inactive. Absent
            # rather than listed as zero: a row of zeroes is still a name,
            # and this person is not currently part of the sending estate.
            continue
        if scope.is_client and not email:
            # A LINKEDIN SEAT DOES NOT ESTABLISH WHOSE PERSON THIS IS.
            #
            # Resolving the `hr-`/`li-` schemes made 32 seats resolve, and
            # the roster they resolve to mixes two organisations: alongside
            # the client's own staff it carries Resonate's - the register
            # already records "we own 4 of 86" seats in this estate. Nothing
            # in the data says which seat belongs to whom.
            #
            # The operator's rule is that a client channel never names
            # "Resonate's own accounts". The eight EMAIL senders are known
            # to be the client's: they are the attested mailbox estate and
            # they match the humans in the handoff. A seat-only person is
            # not established either way, so they are counted in the
            # workspace total below and not named. Internal scope sees
            # everything.
            seats += len(linkedin)
            continue
        mailboxes += len(email)
        seats += len(linkedin)
        carried = sorted({name for account in email + linkedin
                          for name in campaigns_by_account.get(
                              str(account.get("provider_account_id")), ())})
        rates = [bounce[str(a.get("provider_account_id"))] for a in email
                 if str(a.get("provider_account_id")) in bounce]
        row = {
            "name": person.get("display_name") or sender_id,
            "title": person.get("title"),
            "mailboxes": len(email),
            "linkedin_seats": len(linkedin),
            "daily_email_capacity": sum(a.get("daily_limit") or 0
                                        for a in email),
            "daily_linkedin_capacity": sum(a.get("daily_limit") or 0
                                           for a in linkedin),
            "campaigns_carried": carried,
        }
        if rates:
            sent = sum(r["sent"] for r in rates)
            bounced = sum(r["bounced"] for r in rates)
            row["emails_sent_lifetime"] = sent
            row["bounces_lifetime"] = bounced
            row["bounce_rate_percent"] = (round(100.0 * bounced / sent, 2)
                                          if sent else None)
            if row["bounce_rate_percent"] is not None:
                row["over_hard_stop"] = (row["bounce_rate_percent"]
                                         > BOUNCE_HARD_STOP_PERCENT)
        else:
            row["bounce_rate_percent"] = None
            row["bounce_note"] = ("the provider estate could not be read, so "
                                  "no bounce rate is claimed")
        out.append(row)

    answer = {"read_at": _now(), "workspace": slug,
              "senders": out,
              "authorized_people": len(out),
              "mailboxes": mailboxes,
              "linkedin_seats": seats,
              "bounce_hard_stop_percent": BOUNCE_HARD_STOP_PERCENT,
              "note": "these are this workspace's own authorized senders. "
                      "Capacity is a per-day ceiling, not a plan."}

    # AN AUTHORIZATION THAT RESOLVES TO NOTHING IS SAID OUT LOUD.
    #
    # Measured 2026-09-22 against the live roster: LinkedIn authorizations
    # carry account ids prefixed `hr-` while the seat rows carry `li-`, same
    # numbers. The overlap is ZERO, so no LinkedIn seat can resolve its
    # authorization and the honest seat count is not "0 seats" - it is "the
    # seats cannot be matched". Reporting zero would read as "you have no
    # LinkedIn sending", which is a different and false statement.
    #
    # Not joined by stripping the prefix. That would be this module
    # inventing an identity mapping between two id spaces, which is exactly
    # what an attestation exists to prevent somebody doing.
    if scope.is_client:
        out_names = {row["name"] for row in out}
        answer["note"] = (
            "these are this workspace's own authorized email senders. "
            "LinkedIn seats are given as a workspace total: the seat "
            "roster does not record which organisation each seat belongs "
            "to, so seats are not attributed to named people here.")
        answer["named_people"] = len(out_names)
    unresolved = len([1 for channels in owned.values()
                      for account in channels.get("linkedin", ())]) - seats
    if unresolved > 0:
        answer["linkedin_authorizations_unresolved"] = unresolved
        answer["linkedin_note"] = (
            "LinkedIn seat ownership is recorded but does not currently "
            "match a seat on the roster, so no seat count is claimed. This "
            "is not a statement that there are none.")
    return answer


def sending_domains(scope, argument=None):
    """Which DOMAINS this workspace's mail goes out from, grouped by sender.

    OPERATOR, 2026-09-22, from a real question: a Productive person asked
    Jelena and Tina for "popis domena s kojih šaljete mailove u email
    kampanjama". What they were sent was a 194KB CSV of every sender, and
    the next message in the thread was "dontgoproductive.com, kakva je ovo
    domena?" - a question caused by answering with addresses when the
    question was about domains.

    DOMAINS ONLY. The mailbox address is never in the answer, in any scope.
    `email_address` is read to derive the domain and is dropped; the queue
    row's `sender_email` is read the same way. A client asked which domains
    we send from, and the addresses are neither what they asked for nor
    theirs to hold in a Slack thread.

    Attested mailboxes only, on the same rule as `sender_roster`: a domain
    reaches this list because an authorized person's mailbox sits on it.
    """
    slug = _workspace_for(scope, argument)
    try:
        from . import senderidentity
        rows = senderidentity.load()
    except Exception as exc:                                    # noqa: BLE001
        return {"read_at": _now(), "workspace": slug,
                "_error": "sender roster unreadable: %s" % type(exc).__name__}

    owned = {}
    for attestation in rows:
        if (attestation.get("kind") != "ownership_attestation"
                or attestation.get("workspace") != slug
                or attestation.get("channel") != "email"):
            continue
        owned.setdefault(attestation.get("sender_id"), set()).add(
            attestation.get("account_id"))
    if not owned:
        return {"read_at": _now(), "workspace": slug, "senders": [],
                "note": "no authorized email sender is recorded for this "
                        "workspace"}

    by_id = {p.get("sender_id"): p
             for p in senderidentity.senders(slug, rows=rows)}
    accounts = {a.get("account_id"): a
                for a in senderidentity.email_accounts(slug, rows=rows)}
    recent, unreadable = _recent_send_domains(slug)

    senders, every_domain, mailboxes = [], set(), 0
    for sender_id, account_ids in sorted(owned.items()):
        person = by_id.get(sender_id) or {}
        grouped = {}
        for account_id in account_ids:
            account = accounts.get(account_id)
            if not account:
                continue
            domain = str(account.get("domain") or "").lower().strip()
            if not domain:
                continue
            entry = grouped.setdefault(domain, {"domain": domain,
                                                "mailboxes": 0})
            entry["mailboxes"] += 1
            if scope.is_internal:
                # Health is Resonate's operational reading of the estate.
                # A client is told which domains send for them and whether
                # they are sending; how healthy we judge a mailbox is our
                # own assessment of our own infrastructure.
                states = entry.setdefault("health", {})
                state = str(account.get("health")
                            or account.get("provider_state") or "unknown")
                states[state] = states.get(state, 0) + 1
        if not grouped:
            continue
        for domain, entry in grouped.items():
            entry["sent_last_7_days"] = (domain in recent if recent is not None
                                         else None)
            every_domain.add(domain)
            mailboxes += entry["mailboxes"]
        senders.append({"sender": person.get("display_name") or sender_id,
                        "domains": sorted(grouped.values(),
                                          key=lambda d: d["domain"])})

    out = {"read_at": _now(), "workspace": slug,
           "domains_total": len(every_domain),
           "mailboxes_total": mailboxes,
           "senders": senders,
           "note": "domains only. The mailbox addresses behind them are not "
                   "part of this answer."}
    if unreadable:
        out["campaigns_unreadable"] = unreadable
        out["recency_note"] = (
            "%d campaign queue(s) could not be read, so "
            "'sent in the last 7 days' is a floor rather than the whole "
            "picture" % unreadable)
    if recent is None:
        out["recency_note"] = ("no campaign queue could be read, so no "
                               "claim is made about which domains sent "
                               "recently")
    out["listing"] = render_domain_listing(out)
    out["listing_rows"] = len(out["listing"].splitlines())
    return out


def domain_detail(scope, argument=None):
    """ONE domain: whose mailboxes sit on it, what it carried, how it did.

    The catalogue's third tool, and the shape of the real question:

    > *dontgoproductive.com, kakva je ovo domena?*

    That is the message that followed `sending_domains` being answered with
    a 194KB CSV. The catalogue puts it plainly - *almost never "list the
    domains". Usually ONE domain, one sender, one campaign* - and a list of
    sixty-nine answers a question nobody asked while leaving the one they
    did ask unanswered.

    ## A DOMAIN THAT IS NOT YOURS READS THE SAME AS A DOMAIN THAT IS NOBODY'S

    The same rule as `lead_in_campaign`, for the same reason. An answer that
    distinguished "not yours" from "another client's" would confirm the
    other client's estate exists, and that confirmation IS the disclosure.
    So both produce `ours: false` and one sentence, and the sentence does
    not vary.

    ## THE ARGUMENT MAY ARRIVE AS AN ADDRESS AND LEAVES AS A DOMAIN

    People paste `tina@dontgoproductive.com` when they mean the domain.
    Taking the domain is right; echoing the local part back would put a
    mailbox in the answer, which `sending_domains` refuses on purpose in
    every scope. The local part is dropped before anything is looked up and
    the answer names only what was resolved.
    """
    domain = _as_domain(argument)
    if not domain:
        return {"read_at": _now(),
                "_error": "domain_detail needs a domain, like example.com"}
    slug = _workspace_for(scope, None)
    #: The one sentence for "nobody's" and "somebody else's" alike.
    absent = ("%s is not one of the domains sending for this workspace"
              % domain)

    try:
        from . import senderidentity
        rows = senderidentity.load()
    except Exception as exc:                                    # noqa: BLE001
        return {"read_at": _now(), "workspace": slug, "domain": domain,
                "_error": "sender roster unreadable: %s" % type(exc).__name__}

    attested = set()
    for attestation in rows:
        if (attestation.get("kind") == "ownership_attestation"
                and attestation.get("workspace") == slug
                and attestation.get("channel") == "email"):
            attested.add((attestation.get("sender_id"),
                          attestation.get("account_id")))
    people = {p.get("sender_id"): p
              for p in senderidentity.senders(slug, rows=rows)}
    accounts = {a.get("account_id"): a
                for a in senderidentity.email_accounts(slug, rows=rows)}

    mine, owners = [], set()
    for sender_id, account_id in attested:
        account = accounts.get(account_id)
        if not account:
            continue
        if str(account.get("domain") or "").lower().strip() != domain:
            continue
        mine.append(account)
        owners.add((people.get(sender_id) or {}).get("display_name")
                   or sender_id)

    out = {"read_at": _now(), "workspace": slug, "domain": domain,
           "ours": bool(mine)}
    if not mine:
        out["note"] = absent
        return out

    out["mailboxes"] = len(mine)
    # THE SENDER HUMANS, BY NAME. The operator's decision of 2026-09-22: a
    # client's own senders are the client's own data, and the people
    # sending for them are their own staff.
    out["senders"] = sorted(owners)
    out["daily_capacity"] = sum(a.get("daily_limit") or 0 for a in mine)

    carried = _campaigns_by_sending_account(slug)
    out["campaigns_carried"] = sorted(
        {name for a in mine
         for name in carried.get(str(a.get("provider_account_id")), ())})

    week = _week_for_domain(slug, domain)
    if week is None:
        out["last_7_days_note"] = (
            "no campaign queue could be read, so nothing is claimed about "
            "what this domain sent this week")
    else:
        emails, persons, unreadable = week
        out["emails_sent_last_7_days"] = emails
        out["leads_emailed_last_7_days"] = persons
        if unreadable:
            out["campaigns_unreadable"] = unreadable
            out["last_7_days_note"] = (
                "%d campaign queue(s) refused, so these are floors"
                % unreadable)

    if scope.is_internal:
        # HOW WE JUDGE OUR OWN INFRASTRUCTURE. `sending_domains` keeps
        # health internal for the same reason: which domains send for a
        # client is theirs, our assessment of the mailboxes is ours.
        health = {}
        for account in mine:
            state = str(account.get("health")
                        or account.get("provider_state") or "unknown")
            health[state] = health.get(state, 0) + 1
        out["health"] = health
        bounce = _bounce_by_provider_account(slug, rows)
        rates = [bounce[str(a.get("provider_account_id"))] for a in mine
                 if str(a.get("provider_account_id")) in bounce]
        if rates:
            sent = sum(r["sent"] for r in rates)
            bounced = sum(r["bounced"] for r in rates)
            out["emails_sent_lifetime"] = sent
            out["bounces_lifetime"] = bounced
            out["bounce_rate_percent"] = (round(100.0 * bounced / sent, 2)
                                          if sent else None)
            if out["bounce_rate_percent"] is not None:
                out["over_hard_stop"] = (out["bounce_rate_percent"]
                                         > BOUNCE_HARD_STOP_PERCENT)
                out["bounce_hard_stop_percent"] = BOUNCE_HARD_STOP_PERCENT
        else:
            out["bounce_rate_percent"] = None
            out["bounce_note"] = ("the provider estate could not be read, "
                                  "so no bounce rate is claimed")

    out["note"] = ("one domain, with the mailbox addresses on it left out - "
                   "the count is the answer, the addresses are not.")
    return out


def _as_domain(argument):
    """`"tina@dontgoproductive.com"` -> `"dontgoproductive.com"`, or None.

    Takes what a person would actually paste - an address, a bare domain, a
    URL - and returns the registrable text or nothing. It never guesses: a
    value with no dot in it is not a domain and gets None rather than being
    looked up as one.
    """
    import re
    text = str(argument or "").strip().lower()
    text = re.sub(r"^[a-z]+://", "", text)
    text = text.split("/")[0].split("?")[0]
    # THE LOCAL PART IS DROPPED HERE AND NEVER READ AGAIN. `sending_domains`
    # refuses to put a mailbox in an answer in any scope, and echoing back
    # the address somebody pasted would do it by the back door.
    if "@" in text:
        text = text.rsplit("@", 1)[-1]
    text = text.strip(" <>,.;:\"'").strip()
    if "." not in text or " " in text:
        return None
    return text


def _week_for_domain(slug, domain):
    """`(emails, people, campaigns that refused)` for one domain this week.

    `None` rather than zeroes when NOTHING could be read, which is the
    distinction `_recent_send_domains` draws and for the same reason: a
    silent outage reported as a quiet week is the failure this repository
    keeps finding.
    """
    import datetime
    entry = (knowledge.pack().get("workspaces") or {}).get(slug) or {}
    ids = entry.get("provider_campaign_ids") or []
    if not ids:
        return None
    cutoff = datetime.datetime.now(datetime.timezone.utc) - \
        datetime.timedelta(seconds=WEEK_SECONDS)
    emails, people, unreadable, read_any = 0, set(), 0, False
    for campaign_id in ids[:12]:
        try:
            from .providers import bison
            queue = bison.scheduled_emails(campaign_id) or []
        except Exception:                                       # noqa: BLE001
            unreadable += 1
            continue
        read_any = True
        for row in queue:
            stamp = row.get("sent_at")
            address = str(row.get("sender_email") or "")
            if not stamp or "@" not in address:
                continue
            if address.rsplit("@", 1)[-1].lower() != domain:
                continue
            try:
                when = datetime.datetime.fromisoformat(
                    str(stamp).replace("Z", "+00:00"))
            except ValueError:
                continue
            if when.tzinfo is None:
                when = when.replace(tzinfo=datetime.timezone.utc)
            if when < cutoff:
                continue
            emails += 1
            lead = row.get("lead")
            lead_id = lead.get("id") if isinstance(lead, dict) else None
            people.add(lead_id if lead_id is not None
                       else ("row:%s" % row.get("id")))
    if not read_any:
        return None
    return emails, len(people), unreadable


def _recent_send_domains(slug):
    """`(domains that sent inside the window, campaigns that refused)`.

    `None` for the set rather than an empty one when nothing could be read.
    A queue that refused and a week with no sends are different answers, and
    returning "no domains sent" for both is how a silent outage gets
    reported as a quiet week.
    """
    import datetime
    entry = (knowledge.pack().get("workspaces") or {}).get(slug) or {}
    ids = entry.get("provider_campaign_ids") or []
    if not ids:
        return None, 0
    cutoff = datetime.datetime.now(datetime.timezone.utc) - \
        datetime.timedelta(seconds=WEEK_SECONDS)
    found, unreadable, read_any = set(), 0, False
    for campaign_id in ids[:12]:
        try:
            from .providers import bison
            queue = bison.scheduled_emails(campaign_id) or []
        except Exception:                                       # noqa: BLE001
            unreadable += 1
            continue
        read_any = True
        for row in queue:
            stamp = row.get("sent_at")
            address = str(row.get("sender_email") or "")
            if not stamp or "@" not in address:
                continue
            try:
                when = datetime.datetime.fromisoformat(
                    str(stamp).replace("Z", "+00:00"))
            except ValueError:
                continue
            if when.tzinfo is None:
                when = when.replace(tzinfo=datetime.timezone.utc)
            if when >= cutoff:
                # The DOMAIN, never the address. This is the one place a
                # sending address is in memory at all, and it leaves as its
                # domain or not at all.
                found.add(address.rsplit("@", 1)[-1].lower())
    return (found if read_any else None), unreadable


#: Above this many lines the listing is a block of its own rather than
#: prose. The operator: "if the list exceeds ~40 lines".
LISTING_IS_LONG = 40


def render_domain_listing(answer, code=None):
    """The domains, one per line, grouped by sender. Built in CODE.

    NOT LEFT TO THE MODEL. Sixty-nine domains retyped by a language model
    is sixty-nine chances to drop a hyphen, and the reader cannot tell a
    typo from a domain they have not seen before - which is exactly the
    confusion that produced "dontgoproductive.com, kakva je ovo domena?".
    The model writes the sentence around this block; the block itself is
    assembled from the readback and appended verbatim.

    IT CARRIES ITS OWN SUMMARY LINE, and the line says DISTINCT. A domain
    can sit under more than one sender - `dontgoproductive.com` is under
    two - so the rows outnumber the domains, and a reader who counts rows
    and compares them to "69 domains" finds a discrepancy that is not one.

    And it is localised, because it is appended to an answer that may be in
    Croatian and a block of English inside it reads as a machine bolted on
    to a person.
    """
    words = LISTING_WORDS.get(code or "en") or LISTING_WORDS["en"]
    lines = [words["summary"] % (answer.get("domains_total") or 0,
                                 answer.get("mailboxes_total") or 0),
             words["repeat_note"], ""]
    for sender in answer.get("senders") or []:
        lines.append("%s:" % sender.get("sender"))
        for entry in sender.get("domains") or []:
            mark = ""
            if entry.get("sent_last_7_days") is True:
                mark = "  ·  %s" % words["sent"]
            elif entry.get("sent_last_7_days") is False:
                mark = "  ·  %s" % words["quiet"]
            lines.append("  %s  (%d)%s"
                         % (entry["domain"], entry["mailboxes"], mark))
    return chr(10).join(lines)


#: The listing's own words, per language. Deliberately few: this block is a
#: list, and the sentence that frames it is the model's job.
LISTING_WORDS = {
    "en": {"summary": "%d distinct sending domains across %d mailboxes.",
           "repeat_note": "A domain can appear under more than one sender.",
           "sent": "sent in the last 7 days",
           "quiet": "no sends in the last 7 days"},
    "hr": {"summary": "%d različitih domena za slanje, "
                      "ukupno %d mailboxova.",
           "repeat_note": "Ista domena može biti kod više "
                          "pošiljatelja.",
           "sent": "slano u zadnjih 7 dana",
           "quiet": "bez slanja u zadnjih 7 dana"},
}


def listing_is_long(answer):
    listing = (answer or {}).get("listing") or ""
    return len(listing.splitlines()) > LISTING_IS_LONG


def _bare_seat_id(value):
    """The provider's own seat id, with whichever prefix stripped.

    TWO ID SCHEMES, NEITHER OF THEM `senderownership`'s. That module stores
    whatever `account_id` its caller hands it and owns no scheme at all.
    The roster writes `li-116968` (`senderinventory`, in code); the LinkedIn
    attestations carry `hr-116968`, written ad hoc - nothing in the tree
    produces that prefix. The numbers are identical and the overlap on the
    full strings is zero, so every LinkedIn attestation resolved to nothing
    and no seat was provably authorized.

    This is NOT a mapping invented here. `scripts/batch_linkedin_push.py`
    already normalises the same way - `str(account_id).replace("hr-", "")`
    - and pushes live campaigns on the result, so the bare provider id is
    already the join the production session relies on. The account row
    carries it outright as `provider_account_id`, which makes this an exact
    match on a field both sides hold rather than a guess about prefixes.

    Reconciling the two schemes is still the production session's call and
    is filed as a merge-request note.
    """
    text = str(value or "").strip()
    for prefix in ("li-", "hr-"):
        if text.startswith(prefix):
            return text[len(prefix):]
    return text


def _same_seat(account, attested_ids):
    """Is this seat one of the attested ones, under either scheme?"""
    if account.get("account_id") in attested_ids:
        return True
    bare = str(account.get("provider_account_id") or "").strip() \
        or _bare_seat_id(account.get("account_id"))
    if not bare:
        return False
    return bare in {_bare_seat_id(i) for i in attested_ids}


def _campaigns_by_sending_account(slug):
    """`{provider account id: {campaign names}}` for THIS workspace."""
    out = {}
    for row in _campaign_rows(slug):
        name = row.get("name") or row.get("campaign_id")
        for channel in ("email", "linkedin"):
            for entry in (row.get("senders") or {}).get(channel) or []:
                key = str(entry.get("provider_account_id")
                          or entry.get("account_id"))
                out.setdefault(key, set()).add(name)
    return out


def _bounce_by_provider_account(slug, rows):
    """Lifetime sent and bounced per mailbox, from the provider.

    FILTERED AGAINST THIS WORKSPACE'S OWN ACCOUNT IDS, not against whatever
    the provider hands back. `sender_emails()` returns the estate the
    credential reaches, and PRODUCT-GOAL is explicit that a credential
    reaching an estate proves nothing about whose estate it is. So the
    provider supplies the counters and the local roster decides which of
    them belong to this client.
    """
    try:
        from . import senderidentity
        from .providers import bison
        mine = {str(a.get("provider_account_id"))
                for a in senderidentity.email_accounts(slug, rows=rows)
                if a.get("provider_account_id")}
        if not mine:
            return {}
        # `(rows, meta)`, not a list. It reads the envelope first and
        # REFUSES a short list rather than returning a page as a total -
        # which is the defect its own docstring records, where fifteen rows
        # of a 225-inbox estate were reported as the estate. A refusal
        # lands here as an exception and becomes "no bounce rate claimed",
        # which is the right answer: a partial estate cannot give a rate.
        estate, _meta = bison.sender_emails()
    except Exception:                                           # noqa: BLE001
        return {}
    out = {}
    for row in estate:
        key = str(row.get("id") or row.get("provider_account_id") or "")
        if key not in mine:
            continue
        out[key] = {"sent": row.get("emails_sent_count") or 0,
                    "bounced": row.get("bounced_count") or 0}
    return out


#: A week, in seconds. The window "this week" means, and it is a rolling
#: seven days rather than a calendar week on purpose: a client asking on a
#: Monday means the last seven days, not the four hours since midnight.
WEEK_SECONDS = 7 * 24 * 3600


def activity_this_week(scope, argument=None):
    """What actually went out in the last seven days, per campaign.

    THE PROVIDER'S `emails_sent` IS A LIFETIME COUNTER, not a weekly one.
    Reporting it as "this week" would be the same class of error as reading
    `active` as a send, which is the error this project's register exists
    for. The weekly figure is counted from the QUEUE ROWS, each of which
    carries its own `sent_at`, and the lifetime counter is reported beside
    it so the two are never confused.
    """
    import datetime
    slug = _workspace_for(scope, argument)
    entry = (knowledge.pack().get("workspaces") or {}).get(slug) or {}
    ids = entry.get("provider_campaign_ids") or []
    cutoff = datetime.datetime.now(datetime.timezone.utc) - \
        datetime.timedelta(seconds=WEEK_SECONDS)

    rows, sent_week, lifetime, unreadable = [], 0, 0, 0
    for campaign_id in ids[:10]:
        detail = readback.campaign_by_id(campaign_id)
        if detail.get("_error"):
            unreadable += 1
            rows.append({"campaign_id": campaign_id,
                         "_error": detail["_error"]})
            continue
        week = _sent_since(campaign_id, cutoff)
        counter = detail.get("emails_sent")
        if isinstance(counter, int):
            lifetime += counter
        if isinstance(week, int):
            sent_week += week
        rows.append({"campaign_id": campaign_id,
                     "name": detail.get("name"),
                     "status": detail.get("status"),
                     "sent_last_7_days": week,
                     "sent_lifetime": counter,
                     "replied_lifetime": detail.get("replied"),
                     "bounced_lifetime": detail.get("bounced"),
                     "queue_rows": detail.get("queue_rows")})
    out = {"read_at": _now(), "workspace": slug,
           "campaigns_read": len(rows),
           "campaigns_unreadable": unreadable,
           "sent_last_7_days": sent_week,
           "sent_lifetime": lifetime,
           "campaigns": rows,
           "note": "sent_last_7_days is counted from queue rows carrying a "
                   "sent_at inside the window. sent_lifetime is the "
                   "provider's own counter and is NOT a weekly figure."}
    if unreadable:
        out["warning"] = ("%d campaign(s) could not be read, so this total "
                          "is a floor and not the whole picture" % unreadable)
    return out


def _sent_since(campaign_id, cutoff):
    """Queue rows sent since `cutoff`, or None if the queue cannot be read.

    None rather than 0. A queue that refused and a week with no sends are
    different answers, and returning 0 for both is how "nothing went out"
    gets reported for a campaign nobody could read.
    """
    import datetime
    try:
        from .providers import bison
        queue = bison.scheduled_emails(campaign_id) or []
    except Exception:                                           # noqa: BLE001
        return None
    count = 0
    for row in queue:
        stamp = row.get("sent_at")
        if not stamp:
            continue
        try:
            when = datetime.datetime.fromisoformat(
                str(stamp).replace("Z", "+00:00"))
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=datetime.timezone.utc)
        if when >= cutoff:
            count += 1
    return count


def lead_counts(scope, argument=None):
    """HOW MANY. Enrolled, emailed, replied - counted, per campaign.

    THE CATALOGUE'S SECOND GAP, and the largest one by volume: 175 of the
    988 classified questions are about leads and lists, and almost none of
    them is a lookup. *na koliko leadova smo poslali ovaj tjedan*, *jel
    bilo dobrih leadova danas*, *imamo 1.5 kontakata po domeni*. What the
    agent could answer was "is this person in a campaign", which the corpus
    shows nobody has ever asked.

    ## TWO NUMBERS THAT ARE NOT THE SAME NUMBER

    *Na koliko LEADOVA smo poslali* asks how many PEOPLE. A three-step
    sequence sends three emails to one of them, so the queue's row count
    and the number of people it reached differ by the length of the
    cadence - and the difference grows every day the sequence runs. Both
    are reported, named apart, and the people figure is counted by distinct
    provider lead id rather than derived from the other.

    A person in two of the workspace's campaigns is ONE person in the
    workspace total and appears under both campaigns. Summing the
    per-campaign figures therefore does not give the total, which the note
    says out loud so nobody adds them up.

    ## ENROLLED IS THE PROVIDER'S MEMBERSHIP, IN EVERY SCOPE

    `campaign_lead_count` reads `meta.total` and refuses to count a page.
    The local store's enrolled state answers a different question - what we
    have ever staged - and reached a client once already. It is available
    here to an internal channel, under its own name, and to a client not at
    all.

    ## A CAMPAIGN THAT CANNOT BE READ MAKES EVERY TOTAL A FLOOR

    Never a zero, and never quietly dropped: the count of unreadable
    campaigns travels with the answer and the note changes shape when it is
    non-zero, because "we emailed 40 people this week" and "we emailed at
    least 40 people this week, two campaigns did not answer" are different
    claims and only one of them is true.
    """
    import datetime
    slug = _workspace_for(scope, None)
    entry = (knowledge.pack().get("workspaces") or {}).get(slug) or {}
    mine = [str(i) for i in (entry.get("provider_campaign_ids") or [])]
    asked = str(argument or "").strip()
    if asked:
        if asked not in mine:
            return {"read_at": _now(),
                    "_error": "campaign %s does not belong to this "
                              "channel's workspace" % asked}
        wanted = [asked]
    else:
        wanted = mine[:10]

    cutoff = datetime.datetime.now(datetime.timezone.utc) - \
        datetime.timedelta(seconds=WEEK_SECONDS)

    rows, unreadable, queue_unreadable = [], 0, 0
    enrolled_total = sent_total = replied_total = emails_week = 0
    people_week = set()

    for campaign_id in wanted:
        row = {"campaign_id": campaign_id}
        detail = readback.campaign_by_id(campaign_id)
        if detail.get("_error"):
            unreadable += 1
            row["_error"] = detail["_error"]
            rows.append(row)
            continue
        row["name"] = detail.get("name")
        row["status"] = detail.get("status")
        for key, target in (("emails_sent", "sent_lifetime"),
                            ("replied", "replied_lifetime"),
                            ("bounced", "bounced_lifetime")):
            value = detail.get(key)
            if isinstance(value, int):
                row[target] = value
        sent_total += row.get("sent_lifetime") or 0
        replied_total += row.get("replied_lifetime") or 0

        enrolled = _provider_membership(campaign_id)
        if enrolled is None:
            unreadable += 1
            row["enrolled_unreadable"] = True
        else:
            row["enrolled"] = enrolled
            enrolled_total += enrolled

        week = _week_activity(campaign_id, cutoff)
        if week is None:
            queue_unreadable += 1
            row["last_7_days_unreadable"] = True
        else:
            emails, people = week
            row["emails_sent_last_7_days"] = emails
            row["leads_emailed_last_7_days"] = len(people)
            emails_week += emails
            people_week |= people
        rows.append(row)

    out = {"read_at": _now(), "workspace": slug,
           "campaigns_asked_for": len(wanted),
           "campaigns_unreadable": unreadable + queue_unreadable,
           "enrolled_total": enrolled_total,
           "sent_lifetime_total": sent_total,
           "replied_lifetime_total": replied_total,
           "emails_sent_last_7_days": emails_week,
           "leads_emailed_last_7_days": len(people_week),
           "per_campaign": rows}
    out["note"] = (
        "enrolled is the provider's own membership count per campaign and "
        "is NOT sent. emails_sent_last_7_days counts QUEUE ROWS; "
        "leads_emailed_last_7_days counts distinct PEOPLE, which is the "
        "smaller number whenever a sequence has more than one step. The "
        "workspace people figure de-duplicates across campaigns, so the "
        "per-campaign figures do not sum to it. sent_lifetime is the "
        "provider's lifetime counter and is not a weekly figure.")
    if unreadable or queue_unreadable:
        out["warning"] = (
            "%d campaign read(s) failed, so every total here is a FLOOR and "
            "not the whole picture" % (unreadable + queue_unreadable))

    if scope.is_internal:
        # THE LOCAL PIPELINE, UNDER ITS OWN NAME. "how many are ready" is
        # an internal question about our own staging, and the answer is
        # ours - it is not a worse version of the provider's enrolled
        # figure, it is a different one, which is exactly how the 724
        # reached a client.
        out["local_pipeline"] = _try_local_pipeline()
        out["local_pipeline_note"] = (
            "counted from OUR store, not the provider. These are staging "
            "states, not campaign membership, and they are internal.")
    return out


def _provider_membership(campaign_id):
    """The provider's membership count for one campaign, or None.

    None rather than 0, for the reason every other reader here gives: a
    campaign that could not be read and a campaign holding nobody are
    different answers, and reporting the second for the first is how an
    outage becomes a reassuring number.
    """
    try:
        from .providers import bison
        count = bison.campaign_lead_count(campaign_id)
    except Exception:                                           # noqa: BLE001
        return None
    return count if isinstance(count, int) else None


def _week_activity(campaign_id, cutoff):
    """`(emails, {lead ids})` sent since `cutoff`, or None if unreadable.

    One queue read answering both halves. `_sent_since` reads the same rows
    for the row count alone; this exists because the PEOPLE figure cannot
    be derived from it, and reading the queue twice to get two numbers out
    of the same rows is a second chance for them to disagree.
    """
    import datetime
    try:
        from .providers import bison
        queue = bison.scheduled_emails(campaign_id) or []
    except Exception:                                           # noqa: BLE001
        return None
    emails, people = 0, set()
    for row in queue:
        stamp = row.get("sent_at")
        if not stamp:
            continue
        try:
            when = datetime.datetime.fromisoformat(
                str(stamp).replace("Z", "+00:00"))
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=datetime.timezone.utc)
        if when < cutoff:
            continue
        emails += 1
        lead = row.get("lead")
        lead_id = lead.get("id") if isinstance(lead, dict) else None
        # A ROW WITH NO LEAD ID IS STILL A PERSON. Counting it as nobody
        # would make the people figure quietly smaller than the truth, so
        # it is counted under its own row id - distinct from every other
        # row, which is the conservative direction and can never make the
        # people figure exceed the email count.
        people.add(lead_id if lead_id is not None
                   else ("row:%s" % row.get("id")))
    return emails, people


def _try_local_pipeline():
    try:
        return readback.pipeline()
    except Exception as exc:                                    # noqa: BLE001
        return {"_error": "%s: %s" % (type(exc).__name__, str(exc)[:200])}


#: How many of a workspace's campaigns one membership question may cost.
#: One provider read each, and a question about one person should not turn
#: into thirty.
MEMBERSHIP_CAMPAIGN_CAP = 12


def lead_in_campaign(scope, argument=None):
    """Is this person in one of THIS workspace's campaigns - ask the provider.

    `lead_lookup` answers this from our own store, where a contact carrying
    a `bison_lead_id` was STAGED. Staged is not enrolled: the push can have
    been refused, the lead can have been stopped, the campaign can have
    been rebuilt around them. The provider is the only witness to
    membership, and this asks it.

    ## IT NEVER CONFIRMS A PERSON IT CANNOT SHOW

    `find_lead_by_email` searches the whole provider estate, which spans
    every workspace we run there. A client channel asking about an address
    that belongs to ANOTHER client's campaign must learn nothing - not the
    lead's name, not that a lead exists, not that the search found
    something. So the only thing carried out of that search is the numeric
    id, it is asked about THIS workspace's campaign ids and no others, and
    an empty result reads "in none of your campaigns" in both cases. The
    two situations are indistinguishable in the answer because they have to
    be.

    ## ONE READ PER CAMPAIGN, AND THAT IS WHY IT IS CAPPED

    `membership(campaign_id, lead_ids=[id])` asks the lead about itself,
    which is exact whatever page of a twenty-thousand-lead campaign the
    person is on. There is no route that asks the other direction, so a
    workspace with twelve campaigns costs twelve reads. Capped at
    `MEMBERSHIP_CAMPAIGN_CAP`, and the answer says how many it checked
    rather than implying it checked everything.
    """
    address = str(argument or "").strip().lower()
    if "@" not in address:
        return {"read_at": _now(),
                "_error": "lead_in_campaign needs an email address"}
    slug = _workspace_for(scope, None)
    entry = (knowledge.pack().get("workspaces") or {}).get(slug) or {}
    mine = [str(i) for i in (entry.get("provider_campaign_ids") or [])][
        :MEMBERSHIP_CAMPAIGN_CAP]
    out = {"read_at": _now(), "workspace": slug, "address": address,
           "campaigns_checked": len(mine), "source": "provider"}
    #: The one sentence for both "no such lead" and "not one of yours".
    absent = ("the provider has no lead with that address in any of this "
              "workspace's campaigns")

    try:
        from .providers import bison
        lead = bison.find_lead_by_email(address)
    except Exception as exc:                                    # noqa: BLE001
        return dict(out, _error="the provider could not be asked: %s: %s"
                                % (type(exc).__name__, str(exc)[:200]))
    lead_id = (lead or {}).get("id")
    if lead_id is None:
        return dict(out, in_campaigns=[], found=False, note=absent)

    found, unreadable = [], 0
    for campaign_id in mine:
        try:
            status = bison.membership(campaign_id, lead_ids=[lead_id])
        except Exception:                                       # noqa: BLE001
            unreadable += 1
            continue
        state = (status or {}).get(int(lead_id))
        if state is not None:
            found.append({"campaign_id": campaign_id, "status": state})
    out["in_campaigns"] = found
    out["found"] = bool(found)
    if unreadable:
        out["campaigns_unreadable"] = unreadable
        out["warning"] = ("%d campaign(s) could not be read, so an empty or "
                          "short list here is a floor" % unreadable)
    if not found:
        # THE SAME SENTENCE AS THE NO-SUCH-LEAD CASE. Saying "the lead
        # exists but is in none of your campaigns" tells a client that we
        # hold that person for somebody else.
        out["note"] = absent
    else:
        out["note"] = ("membership as the provider states it, per campaign. "
                       "Being in a campaign is not having been emailed - "
                       "ask lead_counts or campaign_detail for sends.")
    return out


def replies(scope, argument=None):
    """What has come back: the provider's counters and the reply feed.

    Two sources that answer different halves. The provider counts replies
    per campaign and knows nothing about what they said; the notification
    feed carries the classified ones and is the only place a positive reply
    is recorded. Both are reported, labelled, and an empty feed says it is
    empty rather than implying nobody replied.
    """
    slug = _workspace_for(scope, argument)
    entry = (knowledge.pack().get("workspaces") or {}).get(slug) or {}
    out = {"read_at": _now(), "workspace": slug}

    counted, unreadable = 0, 0
    for campaign_id in (entry.get("provider_campaign_ids") or [])[:10]:
        detail = readback.campaign_by_id(campaign_id)
        if detail.get("_error"):
            unreadable += 1
            continue
        if isinstance(detail.get("replied"), int):
            counted += detail["replied"]
    out["replies_counted_by_provider"] = counted
    if unreadable:
        out["campaigns_unreadable"] = unreadable

    try:
        from . import notify
        rows = notify.history(workspace=slug, limit=50)
    except Exception as exc:                                    # noqa: BLE001
        out["feed_error"] = type(exc).__name__
        return out

    kinds = {}
    recent = []
    for row in rows:
        kind = row.get("type") or "unknown"
        kinds[kind] = kinds.get(kind, 0) + 1
        if kind in ("positive_reply", "neutral_reply", "negative_reply"):
            recent.append({"at": row.get("at"), "type": kind,
                           "campaign": (row.get("ids") or {}).get("campaign")})
    out["reply_feed_by_kind"] = kinds
    out["classified_replies"] = recent[:10]
    if not rows:
        out["note"] = ("nothing is recorded in this workspace's "
                       "notification feed yet - that is an empty feed, not "
                       "a proven zero")
    return out


def batch_state(scope, argument=None):
    """Where the current batch stands: campaigns, accounts, enrolled.

    DELEGATES to `slackagentreadback.batch_state` when that module carries
    one, and then REPLACES its enrolled figure for a client.

    OPERATOR, 2026-09-22: "Enrolled counts shown to a client must be
    provider-confirmed membership per campaign, never the local store's
    enrolled state."

    The first live client answer said "lokalno je upisano 724 leada na 643
    računa". That is the local store's enrolled state across everything
    ever staged for this workspace; the batch the client was asking about
    holds 151. The local number is not a worse version of the right one, it
    is a different question - and it reached a client in their own channel.

    So for a client the local figure is REMOVED rather than corrected
    alongside, because a readback carrying both invites an answer carrying
    both.
    """
    canonical = getattr(readback, "batch_state", None)
    state = canonical() if callable(canonical) else _batch_state_local(scope)
    if not scope.is_client:
        return state

    # THE BATCH'S OWN CAMPAIGNS, not every campaign this workspace has
    # ever had. The first pass summed all twelve provider ids on the
    # workspace and reported 422 where the batch holds 151 - a number as
    # wrong as the local one it replaced, arrived at more honestly.
    batch_ids = [str(i) for i in (state.get("bound_to_provider") or [])]
    state.pop("bound_to_provider", None)
    for key in ("leads_enrolled_locally", "accounts", "records",
                "leads_enrolled", "enrolled"):
        state.pop(key, None)
    confirmed = provider_enrolled(scope, batch_ids or None)
    state["enrolled_confirmed_by_provider"] = confirmed.get("total")
    state["enrolled_per_campaign"] = confirmed.get("per_campaign")
    state["sent_from_these_campaigns"] = confirmed.get("sent_total")
    state["sent_per_campaign"] = confirmed.get("sent_per_campaign")
    if confirmed.get("unreadable"):
        state["enrolled_unreadable_campaigns"] = confirmed["unreadable"]
        state["enrolled_note"] = (
            "%d campaign(s) could not be read, so the enrolled total is a "
            "floor" % confirmed["unreadable"])
    else:
        state["enrolled_note"] = ("enrolled is the provider's own membership "
                                  "count per campaign. Enrolled is not sent.")
    return state


def provider_enrolled(scope, campaign_ids=None):
    """How many leads the PROVIDER says each named campaign holds.

    `campaign_lead_count` reads `meta.total` and refuses to count a page,
    which is what makes this a membership figure rather than a page length.
    One read per campaign.

    `campaign_ids` is REQUIRED in spirit: with none, this falls back to
    every campaign the workspace has, which answers a question nobody
    asked. The caller names the campaigns it means.
    """
    slug = _workspace_for(scope, None)
    entry = (knowledge.pack().get("workspaces") or {}).get(slug) or {}
    wanted = [str(i) for i in (campaign_ids
                               or entry.get("provider_campaign_ids") or [])]
    # Only this workspace's own campaigns, whatever the caller passed.
    mine = {str(i) for i in (entry.get("provider_campaign_ids") or [])}
    wanted = [i for i in wanted if i in mine][:16]
    per_campaign, unreadable, total = {}, 0, 0
    for campaign_id in wanted:
        try:
            from .providers import bison
            count = bison.campaign_lead_count(campaign_id)
        except Exception:                                       # noqa: BLE001
            unreadable += 1
            continue
        if isinstance(count, int):
            per_campaign[str(campaign_id)] = count
            total += count
    # SENT, BESIDE ENROLLED, FROM THE SAME CAMPAIGNS.
    #
    # The first live answer opened "Da, prvi mailovi su prošli" on the
    # strength of three sends that belonged to a DIFFERENT campaign, while
    # every campaign in the batch stood at zero. The two numbers travel
    # together now so the material cannot be read as one.
    sent, sent_total = {}, 0
    for campaign_id in wanted:
        detail = readback.campaign_by_id(campaign_id)
        value = detail.get("emails_sent")
        if isinstance(value, int):
            sent[str(campaign_id)] = value
            sent_total += value
    return {"read_at": _now(), "workspace": slug, "total": total,
            "per_campaign": per_campaign, "unreadable": unreadable,
            "sent_per_campaign": sent, "sent_total": sent_total}


def _batch_state_local(scope):
    """The fallback: the most recent batch, from the campaign store."""
    slug = _workspace_for(scope, None)
    entry = (knowledge.pack().get("workspaces") or {}).get(slug) or {}
    batches = entry.get("batch_history") or {}
    if not batches:
        return {"read_at": _now(), "workspace": slug,
                "note": "no batch is recorded for %s" % slug}
    latest = sorted(batches)[-1]
    row = dict(batches[latest])
    row.update({"read_at": _now(), "workspace": slug, "batch_id": latest,
                "note": "counts are ENROLLED, not sent. Ask sends_today for "
                        "what the provider has actually sent."})
    return row


def next_actions(scope, argument=None):
    """What happens next, and what it is waiting on.

    Reads `knowledge.current_state`, which follows the NEWEST handoff. An
    earlier version named the evening handoff and its section number
    directly; a night handoff landed the same day with different headings,
    and this tool went on reporting the superseded list as what was next.
    """
    if not scope.is_internal:
        return {"read_at": _now(),
                "note": "the next actions list is internal"}
    state = knowledge.pack().get("current_state") or knowledge.current_state()
    return {"read_at": _now(),
            "source": state.get("waiting_source") or state.get("source"),
            "headline": state.get("headline"),
            "waiting_on_operator": state.get("waiting_on_operator") or [],
            "problem_register": open_issues(),
            "campaigns_awaiting_decision": _awaiting_decision()}


def open_issues():
    """The problem register's rows. DELEGATES to the one reader.

    This used to parse the register itself, because `slackagentreadback.
    blocked` counted bullets and reported 47 where there are ten rows. That
    was the right call at the time and the wrong thing to keep: two readers
    of one file drift, and the operator asked for them folded into one.

    `blocked()` now counts rows, so this hands off to it and reshapes the
    answer for callers that expect this module's keys.
    """
    data = readback.blocked() or {}
    if data.get("_error"):
        return data
    return {"read_at": data.get("read_at"),
            "total": data.get("issue_rows"),
            "open": data.get("open_count"),
            "fixed": data.get("fixed_count"),
            "by_severity": data.get("by_severity"),
            "rows": data.get("open_items")}

def _awaiting_decision():
    try:
        from . import campaigns
        rows = campaigns.load()
    except Exception:                                           # noqa: BLE001
        return []
    return [{"campaign_id": str(r.get("campaign_id")),
             "status": (r.get("status") or "").lower(),
             "client": r.get("client")}
            for r in rows
            if (r.get("status") or "").lower() in (
                "review", "needs_approval", "awaiting_approval", "paused")]


def decisions_log(scope, argument=None):
    """The standing decisions with their dates, who made them, and why."""
    rows = knowledge.pack().get("policies") or []
    if not scope.is_internal:
        rows = slackscope.client_safe_policies(rows)
    return {"read_at": _now(), "decisions": rows}


def who_does_what(scope, argument=None):
    """Who works on this and what each is doing. INTERNAL ONLY."""
    return knowledge.pack().get("workers") or {}


def timeline(scope, argument=None):
    """When the project started, and the milestones since."""
    return knowledge.pack().get("timeline") or {}


def sends_today(scope, argument=None):
    """What actually went out, from the provider's own counters."""
    slug = _workspace_for(scope, None)
    entry = (knowledge.pack().get("workspaces") or {}).get(slug) or {}
    ids = entry.get("provider_campaign_ids") or []
    rows = []
    for campaign_id in ids[:8]:
        row = readback.campaign_by_id(campaign_id)
        if row.get("emails_sent") or row.get("queue_rows"):
            rows.append(row)
    return {"read_at": _now(), "workspace": slug,
            "campaigns_read": len(rows),
            "campaigns": rows,
            "note": "enrolled is not sent; emails_sent is the provider's "
                    "own counter and queue_sent_rows is the queue's"}


def weekly_plan(scope, argument=None):
    """This week, as an ANSWER - what is running, what starts, what waits.

    `docs/SLACK-AGENT-EXPECTATIONS.md`: the weekly update is "a habit with
    a shape", asked every Monday and Tuesday, and the 07:15 briefing is
    supposed to already hold it when somebody asks. Until now the agent
    could answer every piece of it separately and none of it as the
    question people actually ask, which is *what is happening this week*.

    ## THE FORWARD HALF IS TWO DAYS LONG AND SAYS SO

    The provider answers `today`, `tomorrow` and `day_after_tomorrow` and
    nothing further - `docs/GROK-SCHEDULING-2026-09-20.md`. So the honest
    forward answer covers those three days, names them, and states the
    horizon in the readback. Everything past it would be our inference
    dressed as the provider's plan, and this project's whole register
    exists because `scheduled` got read as `sent` once.

    A campaign the provider says nothing about is reported as `no schedule
    returned`, which is its own state - separate from zero, and separate
    from a campaign that could not be read at all.

    ## AND THE BACKWARD HALF IS WHAT MAKES IT AN ANSWER

    "Nothing goes out tomorrow" means one thing after a week of sending and
    another after a week of silence. The last seven days travel with the
    plan so the reader has both, counted the same way `lead_counts` counts
    them - people and emails apart.

    ## A PLAN IS NOT A PROMISE

    This is the tool most likely to turn into one. Nothing here commits to
    a date: it reports what the provider currently intends for three named
    days and what has already happened. The note says that in the material,
    so a model summarising it has the disclaimer in front of it rather than
    having to remember the rule.
    """
    import datetime
    slug = _workspace_for(scope, argument)
    entry = (knowledge.pack().get("workspaces") or {}).get(slug) or {}
    ids = [str(i) for i in (entry.get("provider_campaign_ids") or [])][:10]
    cutoff = datetime.datetime.now(datetime.timezone.utc) - \
        datetime.timedelta(seconds=WEEK_SECONDS)

    running, unreadable = [], 0
    emails_week, people_week = 0, set()
    for campaign_id in ids:
        detail = readback.campaign_by_id(campaign_id)
        if detail.get("_error"):
            unreadable += 1
            continue
        week = _week_activity(campaign_id, cutoff)
        row = {"campaign_id": campaign_id, "name": detail.get("name"),
               "status": detail.get("status")}
        if week is not None:
            emails, people = week
            row["emails_sent_last_7_days"] = emails
            row["leads_emailed_last_7_days"] = len(people)
            emails_week += emails
            people_week |= people
        else:
            row["last_7_days_unreadable"] = True
        running.append(row)

    out = {"read_at": _now(), "workspace": slug,
           "campaigns": running,
           "campaigns_unreadable": unreadable,
           "emails_sent_last_7_days": emails_week,
           "leads_emailed_last_7_days": len(people_week),
           "forward": _forward_window(ids),
           "forward_horizon": "the provider answers today, tomorrow and the "
                              "day after, and nothing beyond that",
           "note": "the forward half is what the PROVIDER currently intends "
                   "for three named days, not a commitment and not a date "
                   "anyone has promised. The backward half is the last 7 "
                   "days, with people and emails counted apart."}
    if unreadable:
        out["warning"] = ("%d campaign(s) could not be read, so this is a "
                          "partial picture of the week" % unreadable)

    if scope.is_internal:
        # WHAT THE WEEK IS WAITING ON. Internal only, and not because it is
        # secret: an open change request names the operator and the gate,
        # which is Resonate's machinery, and the client already knows what
        # they asked for.
        out["waiting_on_a_decision"] = _open_tickets()
        out["campaigns_awaiting_decision"] = _awaiting_decision()
    return out


#: The three days the provider will answer for. Its own vocabulary, in its
#: own order, so nothing here has to do calendar arithmetic against a
#: timezone the provider did not tell us about.
FORWARD_DAYS = ("today", "tomorrow", "day_after_tomorrow")


def _forward_window(campaign_ids):
    """`{day: {campaign: planned}}` for the three days the provider answers.

    Three states per campaign per day and they are kept apart:

        an integer          the provider plans this many
        "none scheduled"    the provider's own empty answer - its 400 with
                            "No emails scheduled for this period", which is
                            a result and not a failure
        "unreadable"        the read failed

    Collapsing the middle two into 0 is the mistake this whole codebase is
    a monument to, so they never meet.
    """
    out = {}
    for day in FORWARD_DAYS:
        planned = {}
        for campaign_id in campaign_ids:
            try:
                from .providers import bison
                row = bison.sending_schedule(campaign_id, day)
            except Exception as exc:                            # noqa: BLE001
                planned[campaign_id] = (
                    "none scheduled"
                    if type(exc).__name__ == "SendingScheduleEmpty"
                    else "unreadable")
                continue
            value = (row or {}).get("emails_being_sent")
            planned[campaign_id] = value if isinstance(value, int) \
                else "unreadable"
        out[day] = planned
    return out


def _open_tickets():
    """Change requests still with the operator. Ids, kinds and ages only."""
    try:
        from . import slackrequests
        rows = slackrequests.pending()
    except Exception as exc:                                    # noqa: BLE001
        return {"_error": "%s: %s" % (type(exc).__name__, str(exc)[:200])}
    return [{"id": r.get("id"), "kind": r.get("kind"),
             "workspace": r.get("workspace"), "origin": r.get("origin"),
             "raised_at": r.get("raised_at"),
             "authority": r.get("requester_authority")} for r in rows]


def held_by_reason(scope, argument=None):
    """Why leads are held, grouped by reason. Counts only.

    Same delegation as `batch_state`: the canonical `stages` readback if the
    module has one, otherwise the staging journals read here.
    """
    canonical = getattr(readback, "stages", None)
    stages = canonical() if callable(canonical) else _stages_local()
    out = {"read_at": stages.get("read_at")}
    copy = stages.get("s7_copy_leads") or {}
    verify = stages.get("s5_verification_leads") or {}
    if copy.get("held_by_reason"):
        out["copy_held_by_reason"] = copy["held_by_reason"]
    if verify.get("by_state"):
        out["verification_by_state"] = verify["by_state"]
    if not out.get("copy_held_by_reason") and not out.get(
            "verification_by_state"):
        out["note"] = "no staging journal is present to group"
    return out


def _stages_local():
    """The staging journals, keyed the way `readback.stages` keys them."""
    counts = knowledge._stage_counts()
    out = {"read_at": _now()}
    if counts.get("s7_copy"):
        out["s7_copy_leads"] = counts["s7_copy"]
    if counts.get("s5_verification"):
        out["s5_verification_leads"] = counts["s5_verification"]
    return out


def credits(scope, argument=None):
    """The credit position. INTERNAL ONLY - spend is Resonate's, not a
    client's."""
    return readback.credits()


def monitors(scope, argument=None):
    """Which watchers are beating, and how long ago. INTERNAL ONLY."""
    return readback.monitors()


# ----------------------------------------------------------- the registry

#: name -> (callable, one-line description, scopes that may call it)
_INTERNAL = (slackscope.INTERNAL,)
_INTERNAL_CLIENT = (slackscope.INTERNAL, slackscope.CLIENT)
# There is deliberately no ANY tuple. Every tool reads either Resonate's
# own state or a client's, and an unbound channel is entitled to neither -
# it gets the identity section of the pack and no readback at all.

REGISTRY = {
    "workspace_summary": (
        workspace_summary,
        "a client's ICP, personas, angles, cadence, sending window and caps",
        _INTERNAL_CLIENT, "workspace slug (optional in a client channel)"),
    "campaign_detail": (
        campaign_detail,
        "one campaign from the provider: status, emails sent, queue rows",
        _INTERNAL_CLIENT, "the campaign id"),
    "cadence_detail": (
        cadence_detail,
        "the sequence day by day: email steps and the LinkedIn graph",
        _INTERNAL_CLIENT, "workspace slug (optional in a client channel)"),
    "lead_lookup": (
        lead_lookup,
        "one contact's state by address",
        _INTERNAL_CLIENT, "an email address"),
    "lead_counts": (
        lead_counts,
        "how many leads: enrolled per campaign from the provider, how many "
        "PEOPLE were emailed in the last 7 days and how many emails that "
        "was, replies and bounces",
        _INTERNAL_CLIENT, "a campaign id (optional; default all of them)"),
    "lead_in_campaign": (
        lead_in_campaign,
        "whether one address is in any of this workspace's campaigns, as "
        "the provider states it, with its status per campaign",
        _INTERNAL_CLIENT, "an email address"),
    "account_lookup": (
        account_lookup,
        "one account's state by domain, with its contact counts",
        _INTERNAL_CLIENT, "a domain"),
    "sender_summary": (
        sender_summary,
        "how many sending accounts are working this client's campaigns",
        _INTERNAL_CLIENT, None),
    "sending_domains": (
        sending_domains,
        "which domains this workspace's mail is sent from, grouped by "
        "sender, with mailboxes per domain and whether it sent this week",
        _INTERNAL_CLIENT, None),
    "domain_detail": (
        domain_detail,
        "one sending domain: how many mailboxes are on it, whose they are, "
        "which campaigns it carries and what it sent this week",
        _INTERNAL_CLIENT, "a domain, like example.com"),
    "sender_roster": (
        sender_roster,
        "this client's own authorized senders by name, with their mailboxes, "
        "seats, daily capacity, campaigns carried and bounce rate",
        _INTERNAL_CLIENT, None),
    "activity_this_week": (
        activity_this_week,
        "what actually went out in the last seven days, per campaign",
        _INTERNAL_CLIENT, None),
    "replies": (
        replies,
        "what has come back: provider reply counts and the classified feed",
        _INTERNAL_CLIENT, None),
    "batch_state": (
        batch_state,
        "where the current batch stands: campaigns, accounts, enrolled",
        _INTERNAL_CLIENT, None),
    "next_actions": (
        next_actions,
        "what happens next and what it waits on",
        _INTERNAL, None),
    "decisions_log": (
        decisions_log,
        "the standing decisions, dated, with who made them and why",
        _INTERNAL_CLIENT, None),
    "who_does_what": (
        who_does_what,
        "who works on this and what each is doing right now",
        _INTERNAL, None),
    # INTERNAL AND CLIENT ONLY. The milestones name campaign ids, send
    # times and the size of the sender estate - Resonate's operational
    # detail, correct in a client's own channel and not in a room nobody
    # has identified. An unbound channel gets the identity section and no
    # tool at all, which is what makes its term list able to be empty.
    "timeline": (
        timeline,
        "when the project started and the milestones since",
        _INTERNAL_CLIENT, None),
    "sends_today": (
        sends_today,
        "what actually went out, from the provider's own counters",
        _INTERNAL_CLIENT, None),
    "weekly_plan": (
        weekly_plan,
        "this week in one answer: what is running, what the provider plans "
        "for today / tomorrow / the day after, and what went out in the "
        "last seven days",
        _INTERNAL_CLIENT, None),
    "held_by_reason": (
        held_by_reason,
        "why leads are held, grouped by reason",
        _INTERNAL_CLIENT, None),
    "credits": (
        credits,
        "the credit position",
        _INTERNAL, None),
    "monitors": (
        monitors,
        "which watchers are beating and how long ago",
        _INTERNAL, None),
}

TOOL_NAMES = tuple(sorted(REGISTRY))


def for_scope(scope):
    """The tools this scope may call, as `{name: description}`."""
    return {name: spec[1] for name, spec in sorted(REGISTRY.items())
            if scope.kind in spec[2]}


def catalogue(scope):
    """The tool list as the model is shown it. One line each."""
    lines = []
    for name, spec in sorted(REGISTRY.items()):
        if scope.kind not in spec[2]:
            continue
        argument = (" (argument: %s)" % spec[3]) if spec[3] else \
            " (no argument)"
        lines.append("  %s - %s%s" % (name, spec[1], argument))
    return "\n".join(lines)


def run(scope, name, argument=None):
    """One tool call. Refuses rather than widening a scope."""
    spec = REGISTRY.get(name)
    if spec is None:
        raise ToolRefused("no tool named %r" % (name,))
    function, _description, scopes, _argument_help = spec
    if scope.kind not in scopes:
        raise ToolRefused(
            "a %s channel may not call %r" % (scope.kind, name))
    try:
        return for_client(scope, function(scope, argument))
    except Exception as exc:                                    # noqa: BLE001
        # THE MESSAGE, NOT JUST THE TYPE. A bare "sender_summary failed:
        # NameError" is what this returned when two tools called a helper
        # that did not exist in this module - and because the model is
        # handed the readback and asked for prose, what a person SAW was a
        # polite "I don't have a confirmed sender count in front of me".
        # A broken tool read as a cautious agent. The exception text is our
        # own code's, carries no credential, and is what makes the
        # difference between a fault and a hedge visible in one line.
        return {"read_at": _now(),
                "_error": "%s failed: %s: %s"
                          % (name, type(exc).__name__, str(exc)[:200])}


def for_client(scope, result):
    """The last pass over a readback before a client can see it.

    Two corrections that a prompt cannot make, applied to the MATERIAL so
    the model has nothing wrong to repeat:

    1. **Times in the workspace's own zone, named.** Taken from its own
       `sending_window.timezone` - the zone its mail is already scheduled
       against - so "13:03 UTC" becomes "15:03 CEST" for a Zagreb client.
       UTC is what an internal channel gets and what this leaves alone
       when a workspace has no zone configured.
    2. **Campaign names without our experiment design.** `RESONATE -
       PRODUCTIVE - EMAIL - US-HOURS - CONTROL - COHORT B` becomes "email
       campaign 491". The channel and the id survive; how we run the test
       does not.
    """
    if not scope.is_client or not isinstance(result, dict):
        return result
    entry = (knowledge.pack().get("workspaces") or {}).get(
        scope.workspace) or {}
    result = _plain_labels(result)
    return clientview.localise(result, clientview.zone_for(entry))


def _plain_labels(value):
    """Replace every campaign `name` with one a client should hear."""
    if isinstance(value, list):
        return [_plain_labels(v) for v in value]
    if not isinstance(value, dict):
        return value
    out = {}
    for key, item in value.items():
        if key == "name" and clientview.carries_internal_label(item):
            out[key] = clientview.plain_campaign_label(
                item, value.get("campaign_id") or value.get("id"))
            continue
        out[key] = _plain_labels(item)
    return out


def run_all(scope, calls):
    """Up to `MAX_CALLS_PER_TURN` calls. Returns `[(name, arg, result)]`.

    Over-budget calls are DROPPED and recorded as dropped, not silently
    truncated: an answer assembled from three readbacks when five were
    asked for should be able to say so.
    """
    out = []
    for index, call in enumerate(calls or []):
        name = (call or {}).get("name")
        argument = (call or {}).get("argument")
        if index >= MAX_CALLS_PER_TURN:
            out.append((name, argument,
                        {"_error": "dropped: over the %d-call budget"
                                   % MAX_CALLS_PER_TURN}))
            continue
        try:
            out.append((name, argument, run(scope, name, argument)))
        except ToolRefused as exc:
            out.append((name, argument, {"_error": str(exc)}))
    return out


# ------------------------------------------------------------- rendering

def render(results):
    """Tool results as text for the prompt. Errors shown, never dropped."""
    lines = []
    for name, argument, result in results or []:
        head = "## %s" % name
        if argument:
            head += "(%s)" % argument
        lines.append(head)
        lines.append(json.dumps(result, default=str, indent=1)[:4000])
        lines.append("")
    return "\n".join(lines)


# -------------------------------------------------------------- internals

def _workspace_for(scope, argument):
    """Which workspace a tool call is about. A client channel: only its own.

    The argument is IGNORED in a client channel rather than validated
    against it. Validating would mean answering "no" to a question about
    another client, and "no" to that question confirms the other client
    exists.
    """
    if scope.is_client:
        return scope.workspace
    slug = str(argument or "").strip().lower()
    if slug:
        return slug
    return _default_workspace()


def _default_workspace():
    try:
        from . import workspaces
        rows = workspaces.workspaces()
    except Exception:                                           # noqa: BLE001
        return "productive"
    live = [w.get("slug") for w in rows
            if ((w.get("settings") or {}).get("policy") or {}).get(
                "sending.live") == "on"]
    return live[0] if live else (rows[0].get("slug") if rows
                                 else "productive")


def _campaign_is_visible(scope, campaign_id):
    if scope.is_internal:
        return True
    if not scope.is_client:
        return False
    entry = (knowledge.pack().get("workspaces") or {}).get(
        scope.workspace) or {}
    return str(campaign_id) in (entry.get("provider_campaign_ids") or [])


def _campaign_rows(slug):
    """This workspace's campaign rows, and no other's.

    A row with no client is EXCLUDED, for the same reason `_records`
    excludes an unattributed record: an unattributed row must never reach a
    client channel, and defaulting it into one is how it would.
    """
    try:
        from . import campaigns
        rows = campaigns.load()
    except Exception:                                           # noqa: BLE001
        return []
    return [r for r in rows
            if (r.get("client") or r.get("workspace")) == slug]


def _records(slug):
    """This workspace's records, and no other's.

    The filter is on the record's own client field. A record carrying no
    client is EXCLUDED rather than included - an unattributed row is
    exactly the thing the product goal says must never reach a client
    channel.
    """
    try:
        from . import store
        rows = store.load()
    except Exception:                                           # noqa: BLE001
        return []
    return [r for r in rows
            if (r.get("client") or r.get("workspace")) == slug]


def _contacts_of(record):
    """The contact dicts of a record, whichever shape it carries.

    The production queue stores a LIST; some fixtures and older rows store a
    dict keyed by address. Reading only one shape would make a real person
    look absent, and "no, they are not in a campaign" is exactly the answer
    that must not be given wrongly.
    """
    contacts = record.get("contacts")
    if isinstance(contacts, dict):
        return [c for c in contacts.values() if isinstance(c, dict)]
    return [c for c in (contacts or []) if isinstance(c, dict)]


def campaigns_of_record(slug, record_id):
    """Which of this client's campaigns hold a given record."""
    out = []
    for row in _campaign_rows(slug):
        if record_id in (row.get("record_ids") or []):
            out.append({"campaign_id": row.get("campaign_id"),
                        "name": row.get("name"),
                        "status": row.get("status"),
                        "provider_campaign_id": row.get("bison_campaign_id")})
    return out


def _find_contacts(slug, needle, limit=5):
    out = []
    for record in _records(slug):
        domain = str(record.get("domain") or "").lower()
        for contact in _contacts_of(record):
            address = str(contact.get("email") or "").lower()
            name = str(contact.get("name") or "").lower()
            if needle not in address and needle not in domain \
                    and needle not in name:
                continue
            out.append({
                "domain": record.get("domain"),
                "record_state": record.get("state"),
                "state": contact.get("state"),
                "sendable": contact.get("sendable"),
                "verification": (contact.get("verification") or {}).get(
                    "state") or contact.get("verdict"),
                "channel_states": contact.get("channels"),
                # THE ANSWER TO "is this person in a campaign". Membership is
                # a campaign-row fact, not a contact field, so it is looked
                # up rather than read off the contact - a contact carrying a
                # `bison_lead_id` was STAGED, which is not the same thing.
                "in_campaigns": campaigns_of_record(slug, record.get("id")),
                # AND WHERE THAT CAME FROM. Our campaign rows record what we
                # STAGED; the provider records what it holds. They agree
                # until a push is refused or a lead is stopped, and the one
                # moment somebody asks is the moment they disagree.
                "in_campaigns_source": "our store, not the provider - ask "
                                       "lead_in_campaign for the provider's "
                                       "own membership",
                "contact": address,
                "name": contact.get("name"),
            })
            if len(out) >= limit:
                return out
    return out


def _count(values):
    out = {}
    for value in values:
        key = value or "unknown"
        out[key] = out.get(key, 0) + 1
    return out
