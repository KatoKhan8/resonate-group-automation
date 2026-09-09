#!/usr/bin/env python3
"""Fictional sender infrastructure, and the eight scenarios worth looking at.

## Why this is a separate file

`demodata.py` builds companies and contacts. This builds the *people doing the
sending* and then plants the specific situations that make the cross-channel
rules visible - which is a different job, and putting it in the same file would
have made the longest module in the repository longer still.

## The shape it builds

Productive gets four email humans and four LinkedIn humans, and the two sets
deliberately only partly overlap:

    email     Anna Novak, Mark Weber, John Adeyemi, Sarah Lindqvist
    linkedin  Petar Horvat, Sarah Lindqvist, Tom Ricci, John Adeyemi

Sarah and John send on both. Anna and Mark are email-only humans; Petar and Tom
are LinkedIn-only. That asymmetry is the entire point of the sender model, and
a demo where everybody appeared on both channels would demonstrate nothing.

Each email human owns several inboxes, because that is what a real client looks
like and because it is what proves an inbox is not a person.

## The scenarios

Eight, lettered to match the brief, planted onto real demo contacts so they
appear in the outreach preview rather than in a fixture nobody opens:

    A  confirmed email, different LinkedIn human   -> handoff allowed
    B  email planned but NOT sent                  -> reference refused
    C  same human on both channels, confirmed      -> continuity allowed
    D  LinkedIn confirmed first, email second      -> handoff in the email
    E  email-only contact
    F  LinkedIn-only contact
    G  paused after a reply
    H  held by verification or MX

E through H already occur naturally in the estate; A through D have to be
planted, because nothing in this build ever sends and so no touch is ever
confirmed by itself.

## Nothing here is real

`.test` domains, invented names, and no credential of any kind.
`tests/test_fixture_hygiene.py` keeps it that way.
"""
from .. import assignment, events, senderidentity as si, store

# (sender_id, display name, title, team, how many inboxes, linkedin?)
PRODUCTIVE_PEOPLE = (
    ("anna", "Anna Novak", "Account Director", "growth", 6, False),
    ("mark", "Mark Weber", "Growth Lead", "growth", 5, False),
    ("john", "John Adeyemi", "Partnerships", "partnerships", 4, True),
    ("sarah", "Sarah Lindqvist", "Client Director", "growth", 4, True),
    ("petar", "Petar Horvat", "Head of Partnerships", "partnerships", 0, True),
    ("tom", "Tom Ricci", "Business Development", "partnerships", 0, True),
)

CONTACTOUT_PEOPLE = (
    ("mara", "Mara Kovac", "Account Executive", "apac", 4, False),
    ("liam", "Liam Duarte", "Partnerships", "apac", 3, True),
    ("ines", "Ines Ferreira", "Client Lead", "apac", 0, True),
)

DEMO_CLIENT_PEOPLE = (
    ("ruth", "Ruth Bakker", "Founder", "founders", 3, True),
)

# Anna's email is followed up by Petar on LinkedIn; Mark's by Tom. John and
# Sarah carry both channels themselves, so they are deliberately not paired -
# a pairing that mapped somebody to themselves would be noise.
PRODUCTIVE_PAIRINGS = (
    ("anna", "petar"),
    ("mark", "tom"),
)

BY_WORKSPACE = {
    "productive": (PRODUCTIVE_PEOPLE, PRODUCTIVE_PAIRINGS),
    "contactout": (CONTACTOUT_PEOPLE, (("mara", "ines"),)),
    "demo-client": (DEMO_CLIENT_PEOPLE, ()),
}

# A daily limit on some accounts and not others, on purpose: the senders screen
# has to be able to show a partial capacity as partial rather than as a total.
# Every fourth inbox has no configured limit.
DEFAULT_LIMIT = 40


def build(workspace):
    """Every sender row for one workspace. Deterministic, writes nothing."""
    people, pairs = BY_WORKSPACE.get(workspace, ((), ()))
    rows = []
    for index, (sender_id, name, title, team, inboxes, has_li) in enumerate(
            people):
        rows.append(si.new_sender(
            workspace, sender_id, name, title=title, team=team,
            # Nobody is opted out individually. The gate that matters is the
            # workspace one, and leaving these unset is what shows a settings
            # screen the difference between "off" and "not configured".
            colleague_language=None))
        domain = f"{workspace}.test"
        for n in range(1, inboxes + 1):
            slot = index * 20 + n
            rows.append(si.new_email_account(
                workspace, f"{sender_id}{n:02d}", sender_id,
                f"{sender_id}{n:02d}@{domain}",
                provider_account_id=f"bison-{slot}",
                # Every fourth inbox has no known limit, so the capacity panel
                # has to render an incomplete total honestly.
                daily_limit=None if n % 4 == 0 else DEFAULT_LIMIT,
                health=_health_for(slot),
                # One inbox per person is switched off, to prove that an
                # inactive account is excluded from allocation rather than
                # hidden from the roster.
                active=(n != inboxes or inboxes < 4)))
        if has_li:
            rows.append(si.new_linkedin_account(
                workspace, f"{sender_id}-li", sender_id,
                f"https://www.linkedin.com/in/{sender_id}-{workspace}",
                provider_account_id=str(4000 + index),
                daily_limit=20 if index % 2 == 0 else None,
                health=_health_for(index)))
    for email_id, linkedin_id in pairs:
        rows.append(si.new_pairing(workspace, email_id, linkedin_id,
                                   note="standing pairing for this workspace"))
    return rows


def _health_for(slot):
    """A spread of states, so the health panel is not one colour.

    `unknown` is the most common on purpose: it is the honest default for an
    account nobody has checked, and a demo where everything is green teaches
    the reader that green is normal.
    """
    return {0: si.HEALTH_OK, 1: si.HEALTH_UNKNOWN, 2: si.HEALTH_WARMING,
            3: si.HEALTH_UNKNOWN, 4: si.HEALTH_OK,
            5: si.HEALTH_PAUSED}.get(slot % 6, si.HEALTH_UNKNOWN)


def install():
    """Write every workspace's roster. Demo mode only."""
    rows = []
    for workspace in BY_WORKSPACE:
        rows.extend(build(workspace))
    si.install(rows)
    return rows


# ---------------------------------------------------------- the scenarios

SCENARIOS = (
    ("A", "Confirmed email, different LinkedIn human",
     "The day-1 email actually went out from Anna. The day-3 LinkedIn note "
     "is written by Petar and is allowed to say so."),
    ("B", "Email planned, not sent",
     "The day-1 email has a payload and no send. The LinkedIn note must not "
     "claim anybody emailed, and the preview says which state stopped it."),
    ("C", "Same human on both channels",
     "John emails and John connects. Continuity language, and no claim about "
     "a colleague because there is no colleague involved."),
    ("D", "LinkedIn first, email second",
     "Petar's connection is confirmed, so Anna's later email may refer to "
     "it - the handoff works in both directions."),
    ("E", "Email only", "No usable LinkedIn profile, so no LinkedIn sender."),
    ("F", "LinkedIn only", "Email closed by the channel rules."),
    ("G", "Paused after a reply", "A reply pauses both channels for the "
     "whole company; the assignment stays for the audit."),
    ("H", "Held", "Verification or MX holds the email; nothing is confirmed "
     "and nothing may be referenced."),
)


def plant(recs, workspace="productive", config=None):
    """Assign senders across the estate and plant scenarios A to D.

    Returns {scenario letter: [record_id...]} so the demo can point at them.

    Everything here goes through the real functions: `assignment.ensure` for
    the allocation and `events.record` for the touch, with the sender on the
    event exactly as `push.mark_pushed` would write it. A scenario built by
    hand-editing a record would prove nothing about the code that reads it.
    """
    mine = [r for r in recs if r.get("client") == _client_of(workspace)]
    mine.sort(key=lambda r: r["id"])
    rows = si.load()
    found = {letter: [] for letter, _, _ in SCENARIOS}

    # Everybody gets an assignment first. Sticky from here on.
    for rec in mine:
        for contact in rec.get("contacts") or []:
            if contact.get("selected"):
                assignment.ensure(rec, contact, workspace, rows=rows,
                                  config=config, by="demo")

    for index, rec in enumerate(mine):
        contact = next((c for c in rec.get("contacts") or []
                        if c.get("selected")), None)
        if contact is None:
            continue
        block = assignment.stored(contact)
        email = block.get("email") or {}
        linkedin = block.get("linkedin") or {}
        letter = None

        if not linkedin:
            letter = "F" if not email else "E"
        elif not email:
            letter = "F"
        elif rec.get("paused"):
            letter = "G"
        elif index % 7 == 0:
            # A: confirmed email, and the two humans differ.
            if email.get("sender_id") != linkedin.get("sender_id"):
                _confirm(rec, contact, "email", "day1",
                         _shifted(contact, config, 1), email)
                letter = "A"
        elif index % 7 == 1:
            # B: a payload and no send. The near-miss that must refuse.
            events.record(rec, events.PUSH_PREPARED, contact_key=contact["key"],
                          channel="email", step="day1",
                          day=_shifted(contact, config, 1),
                          push_id=f"{rec['id']}:{contact['key']}:day1:email")
            letter = "B"
        elif index % 7 == 2 and email.get("sender_id") == linkedin.get("sender_id"):
            _confirm(rec, contact, "email", "day1",
                     _shifted(contact, config, 1), email)
            letter = "C"
        elif index % 7 == 3:
            # D: LinkedIn confirmed first, so a later email may refer to it.
            _confirm(rec, contact, "linkedin", "day3",
                     _shifted(contact, config, 3), linkedin)
            letter = "D"

        if letter:
            found[letter].append(rec["id"])

    # H is not planted: a held contact is one the verification or MX rules
    # already produced, and manufacturing one would be manufacturing the
    # verdict rather than the input.
    for rec in mine:
        for contact in rec.get("contacts") or []:
            if contact.get("selected") and _is_held(contact):
                found["H"].append(rec["id"])
                break
    return found


def _shifted(contact, config, day):
    """The day the cadence would actually put this step on.

    `cadence.expand_step` adds `track_offset` to every spec day - an economic
    buyer starts a few days behind a champion - so an event planted with the
    raw spec day sits *earlier* than the step it belongs to. A day-1 email
    would then find a "previous" LinkedIn touch that in fact happens two days
    after it, and open by referring to something that has not occurred.

    Ordering only means anything in one coordinate system, so the planted
    event uses the same shifted day the step will carry.
    """
    from .. import cadence

    return day + cadence.track_offset(contact, config)


def _confirm(rec, contact, channel, step, day, sender):
    """Plant one confirmed touch, exactly as `push.mark_pushed` would.

    The sender goes on the event. That is what makes it attributable, and a
    scenario that skipped it would be a scenario that tests nothing.
    """
    cad = rec.setdefault("cadence", {}).setdefault(contact["key"], {})
    entry = cad.setdefault(step, {})
    entry["status"] = "pushed"
    entry["pushed_at"] = store.now()
    events.record(rec, events.PUSH_MARKED, contact_key=contact["key"],
                  channel=channel, step=step, day=day,
                  push_id=f"{rec['id']}:{contact['key']}:{step}:{channel}",
                  id=f"{rec['id']}:{contact['key']}:{step}:{channel}:pushed",
                  sender_id=sender.get("sender_id"),
                  account_id=sender.get("account_id"))


def _is_held(contact):
    verification = (contact.get("verification") or {})
    return bool(verification.get("state") in ("held", "unknown")
                or (contact.get("mx") or {}).get("blocked"))


def _client_of(workspace):
    """Demo workspaces and clients share a slug; kept explicit rather than
    assumed, because the two are different concepts everywhere else."""
    return workspace
