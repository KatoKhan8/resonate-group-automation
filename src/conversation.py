#!/usr/bin/env python3
"""One person, both channels, in the order it happened.

## The gap this closes

`account.timeline` answers "what happened at this company". Nobody could ask
"what happened with this *person*". Their email steps, their LinkedIn note,
the reply that arrived on one of the two, the hold it caused and the date
they named were four separate lists in four different places, and an
operator opening a contact was expected to interleave them by eye.

That is not only inconvenient. The single most important thing about a
multichannel cadence is only visible when the channels are read together: a
reply on LinkedIn is supposed to stop the *email* sequence, and whether it
did is a question you cannot ask one channel at a time.

## What is derived here and what is not

Everything. The thread is the event log, filtered to one contact, joined
and given sentences. It stores nothing, decides nothing, and cannot move
any state - which is deliberate for a screen that will be read while
somebody decides what to do about a person.

`after_a_reply` is the one derived judgement, and it is stated narrowly: a
*confirmed* touch whose timestamp is later than a reply from the same
person. Not "a violation" - a person reading the thread decides that. In
this build nothing sends, so a confirmed touch comes from a provider, and
one appearing after a reply means a live sequence carried on. It is worth
seeing.

Where a timestamp cannot be read, or is naive where the other is not,
nothing is claimed. Missing evidence is not positive evidence, and a
confident "a step went out after they replied" built on an unreadable clock
would be worse than the silence.

## The message text is not here, and cannot be

No reply body is stored on a record - `events.apply` records that a reply
arrived, not what it said, and the excerpt that reaches a Slack alert is
never written down. So this is a thread of *what happened*, not of what was
written, and it says so rather than showing empty quotes. See
`PRODUCT-GAPS.md`.

## The same person elsewhere

Two records can hold the same human - the same address imported twice, or a
person who moved. `also_known` finds those, and only on an identifier that
*is* an identity: a normalised mailbox, a canonical profile URL, a
provider's own id, all via `dedupe.keys_for`. A name is never enough.

It lists them; it does not merge them. Merging would put one company's
events under another company's heading on the strength of a match nobody
reviewed. And it never leaves the workspace: another tenant's activity is
not this tenant's thread, whoever the person is.
"""
import argparse
import datetime
import json

from . import account, dedupe, events, senderidentity as si, store

# What kind of thing an entry is. The vocabulary a screen renders.
TOUCH = "touch"
REPLY = "reply"
CONNECTION = "connection"
DECISION = "decision"
INTENT = "intent"
REFERRAL = "referral"
ACCOUNT = "account"

KINDS = (TOUCH, REPLY, CONNECTION, DECISION, INTENT, REFERRAL, ACCOUNT)

# Which way it went. `None` is neither - a hold is something we did about
# them, not something either side said.
OUT = "out"
IN = "in"

# What we did about a reply, in an operator's words rather than in event
# names. Every one of these is written by `accountpolicy`, which is the only
# thing that moves reply state.
DECISIONS = {
    events.CONTACT_HELD: "their sequence was paused",
    events.CONTACT_STOPPED: "their sequence was stopped",
    events.CONTACT_SUPPRESSED: "they were suppressed - permanently",
    events.ACCOUNT_SUPPRESSED: "the whole company was suppressed",
    events.REVIEW_REQUIRED: "flagged for somebody to read",
    events.REFERRED_CONTACT_ACTIVATED: "they were activated by a referral",
}

INTENTS = {
    events.OUT_OF_OFFICE_RECORDED: "away",
    events.NOT_NOW_RECORDED: "asked us to come back later",
}


def _at(value):
    """An aware datetime, or None. A naive one is unreadable, not UTC."""
    try:
        parsed = datetime.datetime.fromisoformat(str(value or ""))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None


def _channel(entry):
    return entry.get("channel") or None


def _replies(rec, contact_key):
    """Receipts, with their verdict joined on. One row per reply.

    `reply_received`, `reply_classified` and `positive_reply_detected` are
    the same message seen three times. Listing all three would treble every
    conversation and make a person look three times as talkative.
    """
    verdicts = {}
    for entry in rec.get("events") or []:
        if entry.get("type") != events.REPLY_CLASSIFIED:
            continue
        if entry.get("contact") != contact_key:
            continue
        verdicts[(entry.get("channel"), entry.get("at"))] = entry

    out = []
    for entry in rec.get("events") or []:
        if entry.get("type") != events.REPLY_RECEIVED:
            continue
        if entry.get("contact") != contact_key:
            continue
        verdict = verdicts.get((entry.get("channel"), entry.get("at"))) or {}
        out.append({
            "at": entry.get("at"),
            "channel": _channel(entry),
            "provider": entry.get("provider"),
            "classification": verdict.get("classification"),
            "confidence": verdict.get("confidence"),
            "handled": entry.get("handled") or verdict.get("handled"),
        })
    return out


def thread(rec, contact_key, workspace=None, rows=None):
    """Everything that happened with one person, in order.

    Returns None when the contact is not on the record, rather than an empty
    thread: "nobody by that key" and "nothing has happened yet" are
    different answers and a screen should not print the second for the first.
    """
    contact = None
    for candidate in account.contacts_of(rec):
        if candidate.get("key") == contact_key:
            contact = candidate
            break
    if contact is None:
        return None

    rows = si.load() if rows is None else rows
    names = account._sender_names(workspace, rows)
    entries = []

    theirs = _replies(rec, contact_key)
    # The moment of their first reply on each channel, and overall. Used
    # only to describe a later touch, never to decide anything.
    reply_moments = [(_at(r["at"]), r["channel"]) for r in theirs]
    reply_moments = [(m, c) for m, c in reply_moments if m is not None]

    for item in account.touches(rec, contact_key):
        moment = _at(item["at"])
        earlier = [(m, c) for m, c in reply_moments
                   if moment is not None and m < moment]
        after = bool(earlier) and item["confirmed"]
        sender = names.get(item["sender_id"], item["sender_id"])
        entries.append({
            "at": item["at"],
            "kind": TOUCH,
            "direction": OUT,
            "channel": item["channel"],
            "confirmed": item["confirmed"],
            "state": item["state"],
            "step": item.get("step"),
            "day": item.get("day"),
            "sender": sender,
            "after_a_reply": after,
            # Which is the more interesting half: a LinkedIn reply is
            # meant to stop the email sequence too.
            "crossed_channels": after and any(
                c and c != item["channel"] for _, c in earlier),
            "summary": (f"{sender or 'a sender'} - "
                        f"{item['channel'] or 'unknown channel'}"
                        + ("" if item["confirmed"] else ", not confirmed")),
        })

    for item in theirs:
        entries.append({
            "at": item["at"],
            "kind": REPLY,
            "direction": IN,
            "channel": item["channel"],
            "confirmed": True,
            "classification": item["classification"],
            "confidence": item["confidence"],
            "handled": item["handled"],
            "summary": ("they replied on "
                        + (item["channel"] or "an unknown channel")
                        + (f" - {item['classification']}"
                           if item["classification"] else
                           " - nobody has classified it")),
        })

    for entry in rec.get("events") or []:
        kind = entry.get("type")
        mine = entry.get("contact") == contact_key

        if kind == events.LINKEDIN_CONNECTED and mine:
            entries.append({
                "at": entry.get("at"), "kind": CONNECTION, "direction": IN,
                "channel": events.LINKEDIN, "confirmed": True,
                "summary": "they accepted the connection"})
        elif kind in DECISIONS and mine:
            entries.append({
                "at": entry.get("at"), "kind": DECISION, "direction": None,
                "channel": _channel(entry), "confirmed": True,
                "outcome": entry.get("outcome"),
                "summary": DECISIONS[kind]})
        elif kind in INTENTS and mine:
            when = entry.get("return_date")
            entries.append({
                "at": entry.get("at"), "kind": INTENT, "direction": None,
                "channel": _channel(entry), "confirmed": True,
                "return_date": when,
                "return_status": entry.get("return_status"),
                "summary": (f"{INTENTS[kind]} - back on {when}" if when else
                            f"{INTENTS[kind]}, with no date we could read")})
        elif kind == events.REFERRAL_MENTIONED and mine:
            entries.append({
                "at": entry.get("at"), "kind": REFERRAL, "direction": IN,
                "channel": _channel(entry), "confirmed": True,
                "referral_status": entry.get("referral_status"),
                "named": entry.get("named"),
                "summary": ("they pointed us at "
                            + (entry.get("named") or "somebody")
                            + " - " + str(entry.get("reason") or ""))})
        elif kind == events.COMPANY_PAUSED:
            entries.append({
                "at": entry.get("at"), "kind": ACCOUNT, "direction": None,
                "channel": _channel(entry), "confirmed": True,
                "summary": "the whole company was paused"})

    for edge in account.referrals(rec):
        if edge["from_contact"] == contact_key:
            entries.append({
                "at": edge["at"], "kind": REFERRAL, "direction": IN,
                "channel": edge.get("channel"), "confirmed": True,
                "summary": f"they referred us to {edge['to_name']}"})
        elif edge["to_contact"] == contact_key:
            entries.append({
                "at": edge["at"], "kind": REFERRAL, "direction": None,
                "channel": edge.get("channel"), "confirmed": True,
                "summary": f"{edge['from_name']} referred us to them"})

    # Undated events sort first rather than being dropped. Something that
    # happened at an unknown time still happened.
    entries.sort(key=lambda e: (str(e.get("at") or ""), e["kind"]))
    return {
        "record_id": rec.get("id"),
        "company": rec.get("company"),
        "client": rec.get("client"),
        "contact_key": contact_key,
        "name": contact.get("name") or contact_key,
        "title": contact.get("title"),
        "email": contact.get("email"),
        "linkedin": contact.get("linkedin"),
        "entries": entries,
        "summary": _summary(rec, contact, entries, theirs),
        "text_note": "the messages themselves are not stored here - only "
                     "that they happened, when, and on which channel",
    }


def _summary(rec, contact, entries, theirs):
    """The header. Every number counted from the entries above it."""
    touched = [e for e in entries if e["kind"] == TOUCH and e["confirmed"]]
    planned = [e for e in entries if e["kind"] == TOUCH and not e["confirmed"]]
    crossed = [e for e in touched if e["after_a_reply"]]
    dated = [e for e in entries
             if e["kind"] == INTENT and e.get("return_date")]

    flags = []
    if crossed:
        flags.append(
            f"{len(crossed)} confirmed step(s) went out after they replied"
            + (" - including on the other channel"
               if any(e["crossed_channels"] for e in crossed) else ""))
    if any(r["classification"] is None for r in theirs):
        flags.append("a reply here has never been classified")
    if any(r["classification"] == "positive" and not r["handled"]
           for r in theirs):
        flags.append("they said yes and nobody has marked it read")

    return {
        "state": account._contact_state(
            contact, touched, theirs, rec.get("paused") or {}),
        "channels_used": sorted({e["channel"] for e in touched
                                 if e["channel"]}),
        "channels_replied": sorted({r["channel"] for r in theirs
                                    if r["channel"]}),
        "confirmed_touches": len(touched),
        "planned_touches": len(planned),
        "replies": len(theirs),
        "positive": len([r for r in theirs
                         if r["classification"] == "positive"]),
        "first_at": entries[0]["at"] if entries else None,
        "last_at": entries[-1]["at"] if entries else None,
        "return_date": dated[-1]["return_date"] if dated else None,
        "account_paused": bool(rec.get("paused")),
        "flags": flags,
    }


def also_known(recs, rec, contact):
    """The same person on another record, on an exact identifier only.

    Listed, never merged: putting one company's events under another
    company's heading on the strength of a match nobody reviewed is how a
    thread starts telling somebody something untrue.

    Workspace-scoped by construction - a record belonging to another client
    is skipped whatever the identifiers say.
    """
    mine = {key for _, key in dedupe.keys_for(rec, contact)
            if not key.startswith("record:")}
    if not mine:
        return []

    found = []
    for other in recs or []:
        if other.get("id") == rec.get("id"):
            continue
        if other.get("client") != rec.get("client"):
            continue
        for person in account.contacts_of(other):
            shared = sorted(
                mine & {key for _, key in dedupe.keys_for(other, person)
                        if not key.startswith("record:")})
            if not shared:
                continue
            found.append({
                "record_id": other.get("id"),
                "company": other.get("company"),
                "contact_key": person.get("key"),
                "name": person.get("name") or person.get("key"),
                "matched_on": shared,
                "events": len([e for e in other.get("events") or []
                               if e.get("contact") == person.get("key")]),
                "where": f"/contacts/{other.get('id')}/{person.get('key')}",
            })
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m src.conversation",
        description="One person, both channels, in order. Reads only.")
    parser.add_argument("--record", required=True)
    parser.add_argument("--contact", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    recs = store.load()
    rec = next((r for r in recs if r.get("id") == args.record), None)
    if rec is None:
        print(f"  no record {args.record!r}")
        return 1
    found = thread(rec, args.contact, workspace=rec.get("client"))
    if found is None:
        print(f"  no contact {args.contact!r} on {args.record}")
        return 1
    if args.json:
        print(json.dumps({"thread": found,
                          "also_known": also_known(recs, rec, next(
                              c for c in account.contacts_of(rec)
                              if c.get("key") == args.contact))}, indent=2))
        return 0

    summary = found["summary"]
    print(f"  {found['name']} at {found['company']} - {summary['state']}")
    print(f"  {summary['confirmed_touches']} confirmed touch(es), "
          f"{summary['replies']} repl(ies)")
    for flag in summary["flags"]:
        print(f"  ! {flag}")
    print()
    for entry in found["entries"]:
        arrow = {OUT: "->", IN: "<-"}.get(entry["direction"], "  ")
        print(f"    {str(entry['at'] or 'undated'):32} {arrow} "
              f"{entry['summary']}")
    print()
    print("  " + found["text_note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
