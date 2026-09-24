#!/usr/bin/env python3
"""S8: the staging track becomes canonical records, campaigns and approvals.

    py -3 scripts/batch1_build.py --plan          # what it would build
    py -3 scripts/batch1_build.py --write         # write records + campaigns
    py -3 scripts/batch1_build.py --stats         # the batch stats block

WRITES NOTHING TO ANY PROVIDER. It writes canonical state only, and
`bisonfactory.stage` is what talks to EmailBison afterwards - which is the
whole point of this script existing.

## WHY THIS EXISTS AT ALL

The 24k track ran S1 -> S3 -> S4b -> S5 -> S6 -> S7 into JOURNALS. The push
path builds from RECORDS: `bisonfactory._plan` reads a record's contacts and
its approved cadence steps, and `executionguard` checks an approval
fingerprint against the exact words a payload carries. So a journal row
cannot be pushed, and the gap between the two is this script.

The alternative - writing leads straight to the provider from the journal -
would put every lead on the wire with none of tenancy, approval, collision,
suppression, copy, claims, fatigue or sender ever running. That is not a
shortcut, it is the whole safety model.

## THE THREE THINGS IT WRITES

    records     one per ACCOUNT, carrying the contacts that passed S5 with
                their verification pair, their MX decision and the S3
                evidence behind the ICP verdict
    cadence     em1/em2/em3 per contact, holding S7's rendered words, then
                APPROVED through `approve.approve_step` so the fingerprint is
                computed by the same code the guard checks it with
    campaigns   one canonical row per attested human, naming that human's
                single healthiest mailbox, with a window that matches its
                cohort

## TIMEZONE COHORTS ARE CAMPAIGN-SHAPED, NOT LEAD-SHAPED

EmailBison schedules ONE window per campaign, so a cohort mixing New York and
Berlin mails somebody in the middle of their night whatever the lead says.
Condition 3 of the grant asks for recipient-local windows and grouped
cohorts, so each campaign carries one cohort and one window:

    us      America/New_York   09:00-17:00   - the window 489 already uses
    uk      Europe/London      09:00-17:00
    eu      Europe/Zagreb      09:00-17:00

**Australia is HELD OUT of batch 1.** Thirteen leads is not a campaign, and
the grant says no inferred timezone where the country spans several. They
wait for a cohort of their own rather than being mailed at 03:00 local.

## THE PACING RULE DECIDES THE SIZE, NOT THE SUPPLY

Enrolled-but-unsent per campaign stays at or below three days of that
campaign's first-step capacity. Single-mailbox tonight: 15/day x 3 = 45 per
campaign, 360 across eight. 495 leads carry copy; the rest wait in the
reservoir, which is what a reservoir is for.
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import (approval, approve, campaigns, clients,  # noqa: E402
                 clientapproval as ca, identity, store)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE = os.path.join(ROOT, "work", "stage")
SOURCE_CSV = os.path.join(ROOT, "work", "Productive",
                          "productive_ICP_safe_to_send (1).csv")

CLIENT = "productive"

BATCH_ID = "batch-1-2026-09-21"

#: The grant, named as the approver. `approval.is_accountable_approver`
#: requires an address, and the parenthetical carries the provenance.
APPROVER = ("zvonimir@example.test "
            "(operator authorisation 2026-09-21 batch 1)")

#: 15 first-step sends per mailbox per day, three days of backlog.
PER_CAMPAIGN = 45
PER_MAILBOX_DAY = 15

COHORTS = {
    "us": {"countries": {"United States"},
           "window": {"days": ["monday", "tuesday", "wednesday", "thursday",
                               "friday"],
                      "start": "09:00", "end": "17:00",
                      "timezone": "America/New_York"},
           "campaigns": 5},
    "uk": {"countries": {"United Kingdom", "Ireland"},
           "window": {"days": ["monday", "tuesday", "wednesday", "thursday",
                               "friday"],
                      "start": "09:00", "end": "17:00",
                      "timezone": "Europe/London"},
           "campaigns": 2},
    "eu": {"countries": {"Germany", "Sweden", "France", "Finland",
                         "Netherlands", "Denmark", "Norway", "Belgium",
                         "Austria", "Switzerland", "Poland", "Spain",
                         "Italy", "Croatia", "Portugal", "Czechia"},
           "window": {"days": ["monday", "tuesday", "wednesday", "thursday",
                               "friday"],
                      "start": "09:00", "end": "17:00",
                      "timezone": "Europe/Zagreb"},
           "campaigns": 1},
}

STEP_KEYS = ("em1", "em2", "em3")

#: THE CAMPAIGN CARRIES ITS OWN SEQUENCE, exactly as 489 does.
#:
#: `cadence.steps_for` falls back to the client's default cadence when the
#: campaign names none, and Productive's default is five email steps. The
#: config's `email_sequence` declares three, and `bisonfactory` REFUSES when
#: those two disagree - "these must be the same keys" - which is the check
#: catching a real mismatch rather than an inconvenience: a campaign whose
#: provider sequence has three steps and whose cadence has five would silently
#: drop em4 and em5, and nothing downstream would say so.
#:
#: Copied from campaign 489's own row, which is the shape that has sent mail.
CADENCE_STEPS = [
    {"key": "em1", "day": 1, "channel": "email", "template": "persona_pain"},
    {"key": "em2", "day": 4, "channel": "email",
     "template": "comparable_proof"},
    {"key": "em3", "day": 8, "channel": "email", "template": "breakup"},
]


def _jsonl(path):
    out = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def load_inputs():
    icp = {}
    for row in _jsonl(os.path.join(STAGE, "s3-icp.jsonl")):
        icp[str(row.get("domain", "")).lower()] = row
    verify = {}
    for row in _jsonl(os.path.join(STAGE, "s5-verify.jsonl")):
        verify[str(row.get("email", "")).lower()] = row
    with open(os.path.join(ROOT, "work", "mx-cache.json"),
              encoding="utf-8") as handle:
        mx = {k.lower(): v for k, v in json.load(handle).items()}
    copy = {}
    for row in _jsonl(os.path.join(STAGE, "s7-copy.jsonl")):
        if row.get("state") == "rendered":
            copy[str(row.get("email", "")).lower()] = row["variables"]
    import csv
    people = {}
    with open(SOURCE_CSV, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            email = (row.get("Work Email") or "").strip().lower()
            if email and email not in people:
                people[email] = row
    return icp, verify, mx, copy, people


def cohort_of(country):
    for name, spec in COHORTS.items():
        if country in spec["countries"]:
            return name
    return None


def attested_mailboxes():
    """Each attested human's single healthiest mailbox by lifetime bounce.

    Condition 2, single-mailbox branch. The three excluded identities carry
    no attestation, so they cannot appear here even as a fallback - the
    register's row exists so nobody reads their 51 mailboxes as capacity.
    """
    rows = _jsonl(os.path.join(ROOT, "work", "senders.jsonl"))
    accounts = {r.get("account_id"): r for r in rows
                if r.get("kind") == "email_account"}
    per = collections.defaultdict(list)
    for row in rows:
        if (row.get("kind") == "ownership_attestation"
                and row.get("channel") == "email"):
            account = accounts.get(row.get("account_id"))
            if account:
                per[row.get("sender_id")].append(account)
    chosen = {}
    for human, mailboxes in per.items():
        scored = []
        for mailbox in mailboxes:
            state = mailbox.get("provider_state") or {}
            sent = state.get("emails_sent_count") or 0
            bounced = state.get("bounced_count") or 0
            rate = (bounced / sent) if sent else 9.0
            scored.append((rate, -sent, mailbox))
        scored.sort(key=lambda t: (t[0], t[1]))
        rate, _, mailbox = scored[0]
        chosen[human] = {
            "provider_account_id": str(mailbox.get("provider_account_id")),
            "account_id": mailbox.get("account_id"),
            "bounce_rate": rate,
            "mailboxes_attested": len(mailboxes),
        }
    return chosen


def select(copy, icp, people, apply_cohort_cap=True):
    """The leads batch 1 will carry, per cohort, under the pacing rule."""
    by_cohort = collections.defaultdict(list)
    held = collections.Counter()
    for email, variables in sorted(copy.items()):
        domain = email.split("@")[-1].lower()
        country = (icp.get(domain) or {}).get("country") or "unknown"
        cohort = cohort_of(country)
        if cohort is None:
            held[f"no campaign window for this cohort: {country}"] += 1
            continue
        if not ca.is_approved(domain, CLIENT):
            held["client approval not approved"] += 1
            continue
        by_cohort[cohort].append((email, variables, country))
    plan, spill = {}, collections.Counter()
    for cohort, entries in by_cohort.items():
        if not apply_cohort_cap:
            # FILL MODE: the room on the standing campaigns is the cap, and
            # it is read from the provider per campaign. A second cap here -
            # five campaigns times forty-five, from when each named one
            # mailbox - would hold back 112 US leads against 2,835 of room.
            plan[cohort] = entries
            continue
        cap = COHORTS[cohort]["campaigns"] * PER_CAMPAIGN
        plan[cohort] = entries[:cap]
        if len(entries) > cap:
            spill[cohort] = len(entries) - cap
    return plan, held, spill


def build_records(selection, icp, verify, mx, people):
    """One record per account, contacts attached, copy not yet approved."""
    records = {}
    for cohort, entries in selection.items():
        for email, variables, country in entries:
            domain = email.split("@")[-1].lower()
            person = people.get(email) or {}
            row = icp.get(domain) or {}
            record_id = domain.replace(".", "-")
            record = records.get(record_id)
            if record is None:
                record = {
                    "id": record_id,
                    "lane": "domains",
                    "client": CLIENT,
                    "company": (person.get("Company") or "").strip() or domain,
                    "domain": domain,
                    "context": "",
                    "signal": row.get("reason") or "",
                    "state": "verified",
                    "drop_reason": None,
                    # A MAPPING, because that is what `report.batch_of`
                    # reads and what the intake path has always written. The
                    # first version wrote a bare string and took out
                    # `report.rows` for the whole queue.
                    "batch": {"id": BATCH_ID, "source": "24k staging track"},
                    "cohort": cohort,
                    "company_facts": {
                        "name": (person.get("Company") or "").strip() or domain,
                        "domain": domain,
                        "employees": row.get("employees"),
                        "industry": row.get("industry"),
                        "country": row.get("country"),
                        "research_outcome": "supplier list, ICP re-verified",
                    },
                    "contacts": [],
                    "excluded": [],
                    "diagnosis": None,
                    "hook": None,
                    "cadence": {},
                    "stages": {},
                    "events": [],
                    "log": [],
                }
                records[record_id] = record
            name = " ".join(x for x in [(person.get("First Name") or "").strip(),
                                        (person.get("Last Name") or "").strip()]
                            if x)
            contact = {
                "name": name,
                "first_name": (person.get("First Name") or "").strip(),
                "last_name": (person.get("Last Name") or "").strip(),
                "title": variables.get("title"),
                "email": email,
                "email_source": "supplier list, independently verified",
                "persona": variables.get("persona"),
                "angle": variables.get("angle"),
                "verdict": "valid",
                "sendable": True,
                "primary": not record["contacts"],
                "linkedin": (person.get("Url") or "").strip() or None,
                "mx": mx.get(domain) or {},
                "verification": _verification(verify.get(email) or {}),
            }
            contact["key"] = identity.contact_key(
                contact, existing=[c.get("key") for c in record["contacts"]])
            record["contacts"].append(contact)
            record["cadence"][contact["key"]] = {
                "em1": {"channel": "email", "template": "persona_pain",
                        "generated": True,
                        "subject": variables["subject_1"],
                        "body": variables["body_1"]},
                "em2": {"channel": "email", "template": "comparable_proof",
                        "generated": True,
                        "subject": variables["subject_1"],
                        "body": variables["body_2"]},
                "em3": {"channel": "email", "template": "breakup",
                        "generated": True,
                        "subject": variables["subject_1"],
                        "body": variables["body_3"]},
            }
    return records


def _verification(row):
    """The S5 verdict, in the shape the record carries.

    The PAIR is the evidence: two independent providers, both fresh, which is
    condition 1. A supplier's own "Verified" column is not one of them and
    never enters here.

    **EVERY EVIDENCE ROW CARRIES THE ADDRESS IT IS ABOUT.**
    `verification.evidence_for` drops evidence that records no address, on
    the grounds that evidence outlives the mailbox it was obtained for: a
    corrected typo or a re-enrichment would otherwise inherit the previous
    address's confirmations and read as verified for a mailbox nobody has
    checked. The first run of this script omitted the address and all 1,068
    steps were correctly refused as "recipient is not sendable" - the guard
    recomputing from evidence rather than trusting the stored `state`, which
    is exactly what it is for.

    The status written here is a restatement, not an invention: S5's own
    `decide` required two confirmations before it wrote `verified`, so both
    named providers said valid for this address.
    """
    pair = list(row.get("pair") or ())
    email = str(row.get("email") or "").strip().lower()
    return {
        "state": row.get("state"),
        "sendable": bool(row.get("sendable")),
        "reason": row.get("reason"),
        "stopped": None,
        "at": row.get("at"),
        "confirmations": row.get("confirmations"),
        "evidence": [{"provider": name, "status": "valid", "email": email,
                      "at": row.get("at")} for name in pair],
    }


def assign(selection, records, mailboxes):
    """Which campaign each record belongs to. One cohort per campaign."""
    humans = sorted(mailboxes, key=lambda h: (-mailboxes[h]["mailboxes_attested"],
                                              h))
    slots = []
    for cohort, spec in COHORTS.items():
        for _ in range(spec["campaigns"]):
            slots.append(cohort)
    plan = collections.OrderedDict()
    for human, cohort in zip(humans, slots):
        plan[human] = {"cohort": cohort, "record_ids": [], "leads": 0}
    # AN ACCOUNT IS NOT SPLIT ACROSS CAMPAIGNS. Two people at one company
    # hearing from two different senders in the same week is the thing
    # account-based outreach exists to avoid, so the unit assigned here is
    # the account and the per-campaign cap is checked against the leads it
    # brings with it.
    #
    # THE CAP IS PER CAMPAIGN, which is what the pacing rule actually says:
    # enrolled-but-unsent per campaign at or below three days of THAT
    # campaign's first-step capacity. Capping the cohort total instead let a
    # campaign reach 49 while another sat at 41 - the same 360 in aggregate
    # and a four-day backlog on one of them.
    by_account = collections.OrderedDict()
    for cohort, entries in selection.items():
        for email, _variables, _country in entries:
            record_id = email.split("@")[-1].lower().replace(".", "-")
            by_account.setdefault((cohort, record_id), []).append(email)
    spilled = collections.Counter()
    for (cohort, record_id), emails in by_account.items():
        targets = [h for h in plan if plan[h]["cohort"] == cohort]
        room = [h for h in targets
                if plan[h]["leads"] + len(emails) <= PER_CAMPAIGN]
        if not room:
            spilled[cohort] += len(emails)
            continue
        human = min(room, key=lambda h: plan[h]["leads"])
        plan[human]["record_ids"].append(record_id)
        plan[human]["leads"] += len(emails)
    return plan, spilled



def standing_campaigns():
    """The campaigns that already exist, with their cohort and their room.

    ROOM IS READ FROM THE PROVIDER, and it is `cap - (enrolled - sent)`.
    Enrolled minus sent, because a campaign that has enrolled 45 and sent 30
    carries a 15-lead backlog, not a 45-lead one, and idling a mailbox that
    has room is the opposite of what the pacing rule is for.

    The cap moves with the mailboxes the campaign names: wave 2 bound 154
    attested inboxes across the eight, so `cap` is 15 x named x 3 days rather
    than the 45 that applied when each named one.

    ## ROOM IS ALSO CAPPED BY THE FORWARD BOOK, AND THAT IS THE TIGHTER NUMBER

    The pacing cap says how much BACKLOG a campaign may carry. It does not say
    whether the campaign's mailboxes can actually send anything, and those are
    different questions the moment a mailbox is shared with the client's own
    campaigns.

    Measured 2026-09-22: under the pacing cap alone, bojan/jakov/luka had room
    for 216/83/32 leads. Their forward-book room that day, and on every day
    through the 25th, was ZERO - 327/328/352 hold every one of those eight
    mailboxes at 15/day. Enrolling there would have built backlog that cannot
    send, which is the exact outcome the pacing rule exists to prevent.

    So room is `min(pacing room, free first-step slots today)`. The forward
    book must be COMPLETE, FRESH and COVERING or `senderheadroom` refuses per
    mailbox, and REFUSED IS NOT ROOM - a campaign whose book cannot be proven
    contributes nothing rather than its cap.
    """
    from src.providers import bison as _bison
    out = {}
    for row in campaigns.load():
        slug = str(row.get("campaign_id") or "")
        if not slug.startswith("productive-email-batch1-"):
            continue
        human = slug.rsplit("-", 1)[-1]
        named = len((row.get("senders") or {}).get("email") or [])
        cap = max(named, 1) * PER_MAILBOX_DAY * 3
        enrolled = sent = 0
        provider_id = row.get("bison_campaign_id")
        if provider_id:
            try:
                campaign = _bison.campaign(provider_id) or {}
                enrolled = int(campaign.get("total_leads") or 0)
                sent = int(campaign.get("emails_sent") or 0)
            except Exception as exc:                            # noqa: BLE001
                # A campaign whose room cannot be read gets NO room. The
                # alternative is enrolling against a number we guessed.
                print(f"    {human}: provider unreadable ({type(exc).__name__}"
                      f"), treated as full")
                cap = 0
        cohort = None
        timezone = (row.get("sending_window") or {}).get("timezone")
        for name, spec in COHORTS.items():
            if spec["window"]["timezone"] == timezone:
                cohort = name
        pacing_room = max(cap - max(enrolled - sent, 0), 0)
        book_room = _forward_book_room(row)
        out[human] = {"slug": slug, "cohort": cohort, "cap": cap,
                      "room": min(pacing_room, book_room),
                      "pacing_room": pacing_room, "book_room": book_room,
                      "enrolled": enrolled, "sent": sent,
                      "mailboxes": named}
    return out


def _forward_book_room(row):
    """Free first-step slots TODAY across this campaign's named mailboxes.

    Zero when the book cannot answer. `senderheadroom.verdict` returns ROOM
    only from a walk that is complete, fresh and covering; FULL and REFUSED
    both contribute nothing, and REFUSED IS NOT ROOM.
    """
    import datetime
    from src import senderheadroom as _sh

    state = _sh.load_state()
    active = tuple(sorted(int(c) for c in _sh.walked_campaigns(state)))
    if not active:
        return 0
    day = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    total = 0
    for entry in (row.get("senders") or {}).get("email") or []:
        # Each entry is `{"provider_account_id": "2769", "account_id":
        # "eb-2769"}`. The provider's own id is the one the forward book is
        # keyed by; `account_id` is ours and would match nothing.
        try:
            sid = int((entry or {}).get("provider_account_id"))
        except (TypeError, ValueError):
            continue
        verdict, _why, free = _sh.verdict(state, sid, day, PER_MAILBOX_DAY,
                                          active_campaign_ids=active)
        if verdict == _sh.ROOM:
            total += int(free or 0)
    if total:
        return total
    return _stale_book_ceiling(row)


#: OPERATOR RULE, 2026-09-24. A STAND-IN FOR A STALE CENSUS, NOT A DEFAULT.
#:
#: `senderheadroom` returns REFUSED when the forward-book walk is not
#: complete, fresh and covering, and REFUSED IS NOT ROOM - so the function
#: above correctly contributes nothing and every campaign reads `room 0`.
#: That is right, and on 2026-09-24 it meant the estate could not push at all
#: because the census was 30.4h old against a 24h limit and re-walking it
#: takes hours: fourteen campaigns, three of them the CLIENT'S OWN, and 352
#: alone reports ~95,000 rows. They have to be walked because they book the
#: same mailboxes we send from.
#:
#: So room falls back to the provider's own counters:
#:
#:     room = (daily_limit - sent_today - our scheduled rows today) x 0.5
#:
#: THE HALVING IS THE WHOLE POINT and it is not caution for its own sake.
#: The client's campaigns 327, 328 and 352 book these same mailboxes, their
#: bookings are exactly what the stale census cannot tell us, and CLAUDE.md's
#: worked example is sender 2736 booked 15/15 on the 21st by campaign 327.
#: Half the apparent room is reserved against bookings we cannot see.
#:
#: IT IS REPLACED BY THE CENSUS THE MOMENT ONE COMPLETES - the branch above
#: wins whenever it can answer at all. If this function starts being the
#: normal path, the census has stopped completing and that is the bug.
#: The campaigns whose queues count as OUR committed load today. Derived
#: from the monitor table rather than hand-listed: a hand-written list is
#: what left 496, 497 and 498 unwatched, and a campaign missing from THIS one
#: would have its sends counted as free capacity.
def _our_campaigns():
    from src import supervisor
    out = []
    for mon in supervisor.monitors():
        name = str(mon.get("name") or "")
        if name.startswith("bison_watch_"):
            tail = name.rsplit("_", 1)[-1]
            if tail.isdigit():
                out.append(int(tail))
    return tuple(sorted(out))


STALE_BOOK_RESERVE = 0.5


def _stale_book_ceiling(row):
    """Half of what the provider's own counters say is free today."""
    import datetime
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    used = _sender_load_today(today)
    limits = _sender_daily_limits()
    total = 0
    for entry in (row.get("senders") or {}).get("email") or []:
        try:
            sid = int((entry or {}).get("provider_account_id"))
        except (TypeError, ValueError):
            continue
        limit = int(limits.get(sid, PER_MAILBOX_DAY))
        free = max(0, limit - int(used.get(sid, 0)))
        total += int(free * STALE_BOOK_RESERVE)
    return total


_LOAD_CACHE = {}


def _sender_load_today(today):
    """Per-mailbox rows ALREADY committed today across our campaigns.

    Counts `sent` rows sent today and `scheduled` rows due today, both keyed
    by the row's own `sender_email.id`. Our commitments only - the client's
    are the unknown this whole rule reserves against.
    """
    if today in _LOAD_CACHE:
        return _LOAD_CACHE[today]
    from src.providers import bison as _b
    used = {}
    for cid in _our_campaigns():
        try:
            rows = _b.scheduled_emails(cid, cap=80)
        except Exception:                                    # noqa: BLE001
            # A campaign we cannot read is a campaign whose load is unknown,
            # and unknown load must not read as free capacity. Skipping it
            # would do exactly that, so the whole ceiling refuses instead.
            raise
        for r in rows:
            sid = ((r.get("sender_email") or {}) or {}).get("id")
            if not sid:
                continue
            status = str(r.get("status") or "")
            when = str(r.get("sent_at") or r.get("scheduled_date") or "")
            if status in ("sent", "scheduled", "queued_for_sending")                     and when.startswith(today):
                used[int(sid)] = used.get(int(sid), 0) + 1
    _LOAD_CACHE[today] = used
    return used


def _sender_daily_limits():
    from src.providers import bison as _b
    rows, _meta = _b.sender_emails()
    return {int(r["id"]): int(r.get("daily_limit") or PER_MAILBOX_DAY)
            for r in rows if r.get("id") is not None}


def assign_to_existing(selection):
    """Fill the standing campaigns to their room. Accounts stay whole."""
    standing = standing_campaigns()
    plan = collections.OrderedDict()
    for human, spec in standing.items():
        plan[human] = {"cohort": spec["cohort"], "record_ids": [], "leads": 0,
                       "room": spec["room"], "slug": spec["slug"],
                       "mailboxes": spec["mailboxes"]}
        print(f"    {human:10s} mailboxes {spec['mailboxes']:>3}  "
              f"cap {spec['cap']:>5}  enrolled {spec['enrolled']:>3}  "
              f"sent {spec['sent']:>3}  pacing {spec.get('pacing_room', 0):>5}"
              f"  book {spec.get('book_room', 0):>5}  room {spec['room']:>5}")
    by_account = collections.OrderedDict()
    for cohort, entries in selection.items():
        for email, _variables, _country in entries:
            record_id = email.split("@")[-1].lower().replace(".", "-")
            by_account.setdefault((cohort, record_id), []).append(email)
    spilled = collections.Counter()
    for (cohort, record_id), emails in by_account.items():
        targets = [h for h in plan if plan[h]["cohort"] == cohort]
        room = [h for h in targets
                if plan[h]["leads"] + len(emails) <= plan[h]["room"]]
        if not room:
            spilled[cohort] += len(emails)
            continue
        # LEAST-FILLED WINS, by fraction rather than by absolute room.
        # Picking the largest remaining room put all 225 US leads on the one
        # human with 63 mailboxes and left four campaigns empty. Filling by
        # fraction spreads a cohort across its campaigns in proportion to the
        # capacity each actually has, which is also what "round-robin across
        # seats" means on the LinkedIn side.
        human = min(room, key=lambda h: (plan[h]["leads"] /
                                         max(plan[h]["room"], 1)))
        plan[human]["record_ids"].append(record_id)
        plan[human]["leads"] += len(emails)
    return plan, spilled



def _released_accounts(held_accounts, now=None):
    """Accounts whose deferral has expired, and one line saying why not more.

    Returns `(released, detail)`. An account qualifies when ALL hold:

      - a message to somebody at it reads `sent` at the provider, with a
        `sent_at`. That is the register's definition of a send; `scheduled`
        and `active` are not.
      - that send is at least `min_hours_between_first_touches` old.
      - the account currently holds fewer than `max_active_contacts`.

    A provider that cannot be read releases NOTHING. Failing closed here costs
    a batch some supply; failing open puts a second sender in front of a
    company inside the window the client's own policy forbids.
    """
    import datetime
    from src.providers import bison as _bison

    policy = ((clients.load(CLIENT) or {}).get("fatigue") or {}).get("account") or {}
    min_hours = float(policy.get("min_hours_between_first_touches") or 0)
    max_active = int(policy.get("max_active_contacts") or 1)
    now = now or datetime.datetime.now(datetime.timezone.utc)

    sent_at_by_domain, active_by_domain = {}, collections.Counter()
    for row in campaigns.load():
        provider_id = row.get("bison_campaign_id")
        if not provider_id or row.get("client") != CLIENT:
            continue
        try:
            queue = _bison.scheduled_emails(provider_id)
        except Exception as exc:                                # noqa: BLE001
            print(f"  release: campaign {provider_id} unreadable "
                  f"({type(exc).__name__}); releasing nothing from it")
            return set(), "a campaign could not be read"
        for entry in queue:
            email = str(((entry.get("lead") or {}).get("email") or "")).lower()
            domain = email.split("@")[-1]
            if not domain:
                continue
            active_by_domain[domain] += 0      # seen is not active
            if str(entry.get("status") or "").lower() != "sent":
                continue
            stamp = entry.get("sent_at")
            if not stamp:
                continue
            when = datetime.datetime.fromisoformat(
                str(stamp).replace("Z", "+00:00"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=datetime.timezone.utc)
            prior = sent_at_by_domain.get(domain)
            if prior is None or when < prior:
                sent_at_by_domain[domain] = when

    for row in store.load():
        domain = str(row.get("domain") or "").lower()
        if domain:
            active_by_domain[domain] = len(row.get("contacts") or [])

    released, too_recent = set(), 0
    for domain in held_accounts:
        first = sent_at_by_domain.get(domain)
        if first is None:
            continue
        if (now - first).total_seconds() / 3600.0 < min_hours:
            too_recent += 1
            continue
        if active_by_domain.get(domain, 0) >= max_active:
            continue
        released.add(domain)
    detail = (f"{too_recent} sent but inside the {min_hours:.0f}h "
              f"first-touch window")
    return released, detail


def campaign_row(human, spec, mailbox):
    slug = f"productive-email-batch1-{human}"
    return {
        "campaign_id": slug,
        "client": CLIENT,
        "name": (f"RESONATE - PRODUCTIVE - EMAIL - "
                 f"{spec['cohort'].upper()}-HOURS - BATCH1 - {human.upper()}"),
        "status": "approved",
        "created_by": "operator",
        "batch_id": BATCH_ID,
        "lanes": ["domains"],
        "personas": [],
        "geos": [],
        "record_ids": spec["record_ids"],
        "daily_volume": {"email": PER_MAILBOX_DAY, "linkedin": 0},
        "senders": {"email": [{"provider_account_id":
                               mailbox["provider_account_id"],
                               "account_id": mailbox["account_id"]}],
                    "linkedin": []},
        "sending_window": COHORTS[spec["cohort"]]["window"],
        "cadence_steps": CADENCE_STEPS,
        "bison_campaign_id": None,
        "heyreach_campaign_id": None,
        "launch": {"state": "not_launched", "at": None},
        "pause": None,
        "log": [], "events": [],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--batch", default="batch-1-2026-09-21")
    parser.add_argument("--fill-existing", action="store_true",
                        help="add to the standing campaigns up to "
                             "their room, rather than creating any")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args(argv)

    global BATCH_ID
    BATCH_ID = args.batch

    icp, verify, mx, copy, people = load_inputs()
    mailboxes = attested_mailboxes()
    if args.fill_existing:
        # A LEAD ENTERS ONE BATCH, EVER. `excluded` counts as known: a
        # contact held for a live collision is not free to be picked up by
        # the next batch as though it were new - it is waiting on the thing
        # that excluded it.
        known, held_accounts = set(), set()
        for record in store.load():
            held_accounts.add(str(record.get("domain") or "").lower())
            for group in ("contacts", "excluded"):
                for contact in record.get(group) or []:
                    if contact.get("email"):
                        known.add(str(contact["email"]).strip().lower())
        before = len(copy)
        copy = {e: v for e, v in copy.items() if e not in known}
        same_person = before - len(copy)

        # AN ACCOUNT ALREADY IN A BATCH IS NOT FREE SUPPLY.
        #
        # 103 of batch 2's accounts are accounts batch 1 already holds, with
        # a DIFFERENT person at each. Enrolling them would put two of our
        # senders in front of one company in the same week, which is the
        # thing the account-level assignment in this same file exists to
        # prevent - and the client's own config caps contacts per domain for
        # the same reason.
        #
        # So they are DEFERRED, not dropped: once batch 1's first steps have
        # gone and we know how that account responded, a second person there
        # is a decision with evidence behind it instead of a coincidence of
        # two batches.
        # AN ACCOUNT IS RELEASED WHEN ITS FIRST TOUCH HAS AGED, NOT WHEN IT
        # HAS MERELY BEEN SENT.
        #
        # The deferral above is not permanent - a second person at an account
        # becomes a decision with evidence once we know how the first one
        # landed. What decides "once" is the CLIENT's own fatigue policy, not
        # our convenience:
        #
        #     account.min_hours_between_first_touches   72
        #     account.max_active_contacts                2
        #
        # So releasing on a confirmed send alone would breach the client's own
        # config by up to three days. An account is released only when its
        # first touch is PROVIDER-CONFIRMED SENT and that send is at least 72
        # hours old, and only while the account holds fewer than
        # max_active_contacts.
        #
        # Provider-confirmed, never inferred: the evidence is a scheduled-email
        # row reading `sent` with a `sent_at`, which is the same witness the
        # register accepts for a send. `scheduled` and `active` are not sends.
        released, release_detail = _released_accounts(held_accounts)
        held_accounts = held_accounts - released

        before = len(copy)
        copy = {e: v for e, v in copy.items()
                if e.split("@")[-1].lower() not in held_accounts}
        print(f"  same person, already enrolled {same_person}")
        print(f"  deferred - account already in a batch  {before - len(copy)}")
        print(f"  released - first touch sent and aged   {len(released)}"
              f"   ({release_detail})")
        print(f"  available to enrol            {len(copy)}")
    selection, held, spill = select(copy, icp, people,
                                    apply_cohort_cap=not args.fill_existing)
    records = build_records(selection, icp, verify, mx, people)
    if args.fill_existing:
        plan, spilled = assign_to_existing(selection)
    else:
        plan, spilled = assign(selection, records, mailboxes)

    total = sum(len(v) for v in selection.values())
    print(f"\nBATCH 1  client={CLIENT}\n")
    print(f"  leads with rendered copy      {len(copy)}")
    print(f"  selected under the pacing rule {total}")
    print(f"  accounts                      {len(records)}")
    for reason, count in held.most_common():
        print(f"  held: {reason[:50].ljust(50)} {count}")
    for cohort, count in spill.items():
        print(f"  reservoir ({cohort}): {count} over the cohort cap, waiting")
    for cohort, count in spilled.items():
        print(f"  reservoir ({cohort}): {count} more, every campaign in that "
              f"cohort has no room: every campaign in it is at "
              f"its pacing cap OR its mailboxes are full in the "
              f"forward book")
    print("\n  campaigns")
    for human, spec in plan.items():
        mailbox = mailboxes[human]
        print(f"    {human:10s} {spec['cohort']:3s} "
              f"{spec['leads']:>4} leads  {len(spec['record_ids']):>4} accounts  "
              f"mailbox {mailbox['provider_account_id']:>5} "
              f"bounce {mailbox['bounce_rate'] * 100:.2f}%")

    if not args.write:
        print("\n  PLAN ONLY. Nothing was written. Pass --write.")
        return 0

    assigned = {rid for spec in plan.values() for rid in spec["record_ids"]}
    records = {k: v for k, v in records.items() if k in assigned}
    current_rows = store.load()
    existing = {r.get("id") for r in current_rows}

    # RESUMABLE, and the distinction matters. A record THIS BATCH already
    # wrote is not a clash: the first run wrote 285 and then `cadence.build`
    # refused a greeting - the guard working - which left the records in
    # place and the approvals undone. Only a record belonging to something
    # else is the double-enrolment risk condition 5 names.
    ours = {r.get("id") for r in current_rows
            if r.get("batch") == BATCH_ID}
    clash = (existing & set(records)) - ours
    if clash:
        print(f"\n  REFUSED: {len(clash)} of these accounts are already in "
              f"the store under something other than this batch, which is "
              f"the double-enrolment risk condition 5 names. "
              f"First few: {sorted(clash)[:5]}")
        return 1

    fresh = {k: v for k, v in records.items() if k not in existing}
    if fresh:
        with store.transaction() as current:
            for record in fresh.values():
                current.append(record)
    print(f"\n  wrote {len(fresh)} records "
          f"({len(records) - len(fresh)} already written by an earlier run "
          f"of this batch)")

    # BIND EXISTING EVIDENCE TO ITS ADDRESS. ADD ONLY, NEVER REPLACE.
    #
    # The first run wrote evidence rows carrying no `email`, and
    # `verification.evidence_for` drops those: evidence outlives the mailbox
    # it was obtained for, so an unbound row could make a corrected address
    # look verified. Correct, and it is why all 1,068 steps refused.
    #
    # The obvious repair - rewrite the block from the journal - was REFUSED by
    # `store.refuse_evidence_loss`, and that refusal was right too. A record
    # holds one contact verified by (contactout, reoon) and another by
    # (deliverable, reoon); the journal row for one contact names two
    # providers, so writing it over the record's block would have deleted a
    # third provider's paid result. Two guards in a row, both correct, on the
    # same underlying mistake: reconstructing state that already exists.
    #
    # So this adds the address to the rows already there and touches nothing
    # else. No provider is dropped, no verdict changes, and a row that
    # already names an address is left exactly as it is.
    repaired, bound = 0, 0
    with store.transaction() as current:
        for index, stored_record in enumerate(current):
            if stored_record.get("id") not in records:
                continue
            changed = False
            for contact in stored_record.get("contacts") or []:
                address = (contact.get("email") or "").strip().lower()
                if not address:
                    continue
                block = contact.get("verification") or {}
                for row in block.get("evidence") or []:
                    if not row.get("email"):
                        row["email"] = address
                        changed = True
                        bound += 1
            if changed:
                current[index] = stored_record
                repaired += 1
    if repaired:
        print(f"  bound {bound} evidence rows to their address "
              f"on {repaired} records")

    approved, refused = 0, collections.Counter()
    unusable = {}
    recs = {r.get("id"): r for r in store.load()}
    config = clients.load(CLIENT)
    updated = []
    for record_id, record in recs.items():
        if record_id not in records:
            continue
        # A RECORD THE CADENCE REFUSES IS HELD WHOLE, NOT PART-APPROVED.
        # `cadence.build` raises CompanyNameUnusable when the only company
        # name it has is the domain - "Collier.Simon" for colliersimon.com -
        # because addressing a prospect by their own hostname is the defect
        # the greeting rules exist to stop. That refusal is correct and it is
        # per RECORD, so the record leaves the batch rather than shipping two
        # approved steps and one unapproved.
        try:
            steps = [(contact["key"], step_key)
                     for contact in (record.get("contacts") or [])
                     for step_key in STEP_KEYS]
            reasons = {(ck, sk): approve.why_not(record, ck, sk, config=config)
                       for ck, sk in steps}
        except Exception as exc:                                # noqa: BLE001
            unusable[record_id] = f"{type(exc).__name__}: {str(exc)[:120]}"
            continue
        for (contact_key, step_key), why in reasons.items():
            if why:
                refused[str(why)[:60]] += 1
                continue
            approve.approve_step(record, contact_key, step_key,
                                 by=APPROVER, config=config)
            approved += 1
        updated.append(record)
    with store.transaction() as current:
        by_id = {r.get("id"): i for i, r in enumerate(current)}
        for record in updated:
            if record.get("id") in by_id:
                current[by_id[record["id"]]] = record
    print(f"  approved {approved} steps")
    for reason, count in refused.most_common(8):
        print(f"    refused: {reason} x{count}")
    if unusable:
        print(f"  {len(unusable)} accounts HELD by the cadence itself:")
        for record_id, why in list(unusable.items())[:6]:
            print(f"    {record_id}: {why}")
        for spec in plan.values():
            spec["record_ids"] = [r for r in spec["record_ids"]
                                  if r not in unusable]

    # A CONTACT WITH NO APPROVED STEP IS NOT A LEAD, so it is moved to
    # `excluded` rather than left on `contacts` where `bisonfactory._plan`
    # would pick it up. The dry run found exactly this: 219 leads planned
    # against 188 approved, and the extra 31 were contacts verified by a pair
    # this client's policy no longer accepts, sitting at accounts that also
    # hold an approved contact. They would have been staged carrying no copy
    # at all.
    #
    # EXCLUDED, NOT DROPPED. They are re-askable: S5 is re-verifying them
    # against Deliverable right now, and they enter a later batch when it
    # answers. The reason travels with them so nobody has to re-derive it.
    moved = 0
    with store.transaction() as current:
        for index, record in enumerate(current):
            if record.get("batch") != BATCH_ID:
                continue
            keep, holding = [], list(record.get("excluded") or [])
            for contact in record.get("contacts") or []:
                approved_here = any(
                    approval.is_approved(record, contact.get("key"), step_key)
                    for step_key in STEP_KEYS)
                if approved_here:
                    keep.append(contact)
                else:
                    holding.append(dict(contact, excluded_reason=(
                        "no approved step: verification pair does not satisfy "
                        "this client's policy. Re-askable - S5 is verifying "
                        "it against the current primary")))
                    moved += 1
            if len(keep) != len(record.get("contacts") or []):
                record["contacts"] = keep
                record["excluded"] = holding
                current[index] = record
    if moved:
        print(f"  moved {moved} unapproved contacts to `excluded` "
              f"(re-askable, not dropped)")

    # A CAMPAIGN NAMES ONLY RECORDS THAT ACTUALLY CARRY APPROVED WORDS.
    #
    # The plan is built from what S7 rendered; the approvals are what
    # survived the gates. Those are different sets - 167 leads are verified
    # by a pair this client's policy no longer accepts, and one account's
    # greeting was refused - so a campaign built from the plan would name
    # records `bisonfactory._plan` will find nothing approved on. It would
    # stage, read back clean, and carry fewer leads than the stats promised.
    final = {r.get("id"): r for r in store.load()}

    def _has_approved(record_id):
        record = final.get(record_id) or {}
        for contact in record.get("contacts") or []:
            for step_key in STEP_KEYS:
                if approval.is_approved(record, contact.get("key"), step_key):
                    return True
        return False

    rows = campaigns.load()
    by_slug = {r.get("campaign_id"): i for i, r in enumerate(rows)}
    written, updated_rows, empty = 0, 0, []
    for human, spec in plan.items():
        spec["record_ids"] = [r for r in spec["record_ids"] if _has_approved(r)]
        if not spec["record_ids"]:
            empty.append(human)
            continue
        slug = spec.get("slug") or f"productive-email-batch1-{human}"
        if slug in by_slug:
            index = by_slug[slug]
            existing_row = rows[index]
            # APPEND. Wave 2 bound this campaign's mailboxes and batch 1 put
            # accounts on it; a later batch adds to both rather than
            # replacing either.
            have = list(existing_row.get("record_ids") or [])
            added = [r for r in spec["record_ids"] if r not in have]
            if added:
                existing_row["record_ids"] = have + added
                rows[index] = existing_row
                updated_rows += 1
            continue
        row = campaign_row(human, spec, mailboxes[human])
        rows.append(row)
        written += 1
    campaigns.save(rows)
    print(f"  wrote {written} campaign rows, updated {updated_rows}")
    if empty:
        print(f"  {len(empty)} campaigns carry nothing approved and were left "
              f"unbuilt: {', '.join(empty)}")
    enrolled = sum(len(spec["record_ids"]) for spec in plan.values())
    print(f"  {enrolled} accounts across "
          f"{len([h for h in plan if plan[h]['record_ids']])} campaigns")
    print("\n  Canonical only. No provider write has happened.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
