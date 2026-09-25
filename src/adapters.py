#!/usr/bin/env python3
"""Real provider payloads into the neutral event model.

Kept apart from events.py because these are the only functions in the codebase
whose shape is dictated by somebody else's API. events.py owns what an event
*is*; this owns what each provider happens to call it, so a provider changing
its field names touches one file.

Both mappings were written against responses read from the live APIs on
2026-08-26, not from documentation. The two shapes are different in every
respect but share one hazard, and it is the reason this module exists:

    **Both feeds contain our own outgoing messages.**

EmailBison's `/replies` carries `type: "Outgoing Email"` rows sitting in folder
`Sent`. HeyReach's inbox carries conversations whose `lastMessageSender` is us.
Read either naively and every company is paused the moment we contact it -
the outbound engine would shut itself down, one prospect at a time, and the
logs would say "reply received" for all of them.

So both mappings are allowlists. A row is a reply only when it is positively
identified as one; anything unrecognised is reported as unknown and dropped,
never assumed inbound.
"""
from . import events
from .providers import bison, heyreach

EMAIL = events.EMAIL
LINKEDIN = events.LINKEDIN


def _body(row, *names):
    """The reply text, whatever this provider called it. Never persisted."""
    for name in names:
        value = row.get(name)
        if isinstance(value, str) and value.strip():
            return value
    return ""


#: Containers a provider nests the lead under on an INBOUND row. The reply
#: feed returns the whole lead object beside the message, and our identifiers
#: live on the lead rather than on the message.
_NESTED_CARRIERS = ("lead", "contact", "prospect")


def _custom(row, *names):
    """Our own identifiers, wherever this provider put them.

    LOOKS INSIDE `row["lead"]` AS WELL AS AT THE TOP LEVEL, and that is not
    defensive coding - it is the whole function working at all on EmailBison.

    MEASURED 2026-09-25 on a real reply to lead 205081:

        row["custom_variables"]          -> None
        row["lead"]["custom_variables"]  -> record_id, contact_key, client,
                                            subject_1, body_1..3

    `GET /api/replies` returns the message at the top level and the LEAD
    nested under it. This function only ever read the top level, so
    `record_id`, `contact_key` and `client` came back None for EVERY
    EmailBison reply this system has ever ingested, and `events.match_record`
    could never use its first and only unambiguous branch.

    IT HID BECAUSE THE FALLBACK WORKS. `match_record` then matches on the
    from-address, and for an ordinary prospect the from-address IS the
    contact's address - so the identifiers were dead and nothing looked
    wrong. It surfaced only when the operator's own test reply arrived from
    an address the contact record did not carry: unmatched, no stop, no
    error, no alert.

    `src/providers/heyreach.py:build_lead_pairs` records the same defect from
    the other side - "adapters.py has always read record_id and contact_key
    off an inbound conversation - so that branch could never fire and every
    LinkedIn reply fell through to URL matching". Both channels, same shape.

    The top-level read stays FIRST: a webhook batch carries the fields there,
    and a provider that starts sending them at the top level must keep
    working.
    """
    def _read(container):
        for name in names:
            blob = container.get(name)
            if isinstance(blob, dict):
                return blob
            if isinstance(blob, list):
                found = {f.get("name"): f.get("value") for f in blob
                         if isinstance(f, dict)}
                # An empty list is a provider saying "none", not a reason to
                # stop looking somewhere else that has them.
                if found:
                    return found
        return {}

    at_top = _read(row if isinstance(row, dict) else {})
    if at_top:
        return at_top
    for carrier in _NESTED_CARRIERS:
        nested = (row or {}).get(carrier)
        if isinstance(nested, dict):
            found = _read(nested)
            if found:
                return found
    return {}


# ------------------------------------------------------------ EmailBison

def from_emailbison(payload):
    """A page of `GET /api/replies` into neutral events.

    Live shape: {"data": [...], "meta": {"next_cursor"}}. Each row carries
    `id`, `uuid`, `type`, `folder`, `from_email_address`, `date_received`,
    `automated_reply`, `campaign_id`, `lead_id` and the bodies.

    The bodies are read for classification and never returned here: the
    neutral event carries `text` only so the caller can classify, and
    inbound.py is responsible for never persisting it.
    """
    rows = payload.get("data") if isinstance(payload, dict) else payload
    if rows is None and isinstance(payload, dict):
        rows = payload.get("events")          # a webhook batch, same fields
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        kind = bison.classify_reply_row(row)
        if kind == "outgoing":
            continue                          # our own mail. Never a reply.
        if kind == "bounce":
            event_type = events.EMAIL_BOUNCED
        elif kind == "reply":
            event_type = events.REPLY_RECEIVED
        elif kind == "delivered":
            event_type = events.EMAIL_DELIVERED
        else:
            continue                          # unknown: dropped, not guessed

        custom = _custom(row, "custom_variables", "customVariables")
        lead = row.get("lead") if isinstance(row.get("lead"), dict) else {}
        identifier = row.get("uuid") or row.get("id")
        out.append(events.neutral(
            type=event_type,
            channel=EMAIL,
            provider="emailbison",
            provider_event_id=f"emailbison:{identifier}",
            record_id=custom.get("record_id") or lead.get("record_id"),
            contact_key=custom.get("contact_key") or lead.get("contact_key"),
            client=custom.get("client") or lead.get("client"),
            email=(row.get("from_email_address") or row.get("email")
                   or lead.get("email")),
            at=(row.get("date_received") or row.get("timestamp")
                or row.get("created_at")),
            text=_body(row, "text_body", "text", "body", "message",
                       "snippet"),
            # The provider's own autoresponder flag. Better evidence than
            # anything we could infer from the words.
            #
            # Absence is preserved rather than collapsed to False: `bool(None)`
            # would turn "this provider does not say" into "this provider says
            # no", and `ooo.detect` treats those differently on purpose. Every
            # row on the live instance carries the field, so this changes
            # nothing there and stops a quieter provider from being read as an
            # authoritative denial.
            automated=(None if row.get("automated_reply") is None
                       else bool(row.get("automated_reply"))),
            external_campaign_id=row.get("campaign_id"),
        ))
    return out


def emailbison_delivered(payload):
    """Delivery events, if this instance is ever wired to report them.

    Nothing on the confirmed surface emits these: `/replies` carries replies,
    bounces and our own sends. Kept so a webhook that does carry them has a
    home, and so the neutral vocabulary is not silently incomplete.
    """
    rows = payload.get("events") if isinstance(payload, dict) else payload
    out = []
    for row in rows or []:
        if str(row.get("event") or "").strip().lower() not in ("delivered",
                                                               "email_sent",
                                                               "sent"):
            continue
        custom = _custom(row, "custom_variables", "customVariables")
        out.append(events.neutral(
            type=events.EMAIL_DELIVERED, channel=EMAIL, provider="emailbison",
            provider_event_id=f"emailbison:{row.get('id')}",
            record_id=custom.get("record_id"),
            contact_key=custom.get("contact_key"),
            client=custom.get("client"),
            email=row.get("email") or row.get("to_email_address"),
            at=row.get("timestamp") or row.get("created_at")))
    return out


# -------------------------------------------------------------- HeyReach

def from_heyreach(payload):
    """A page of `POST /inbox/GetConversationsV2` into neutral events.

    Live shape, confirmed 2026-08-26: {"items": [...], "totalCount": n}. Each
    item is a THREAD, not an event, and that distinction is the point:

      - `messages[]` was complete on every one of 100 sampled conversations
      - 8 of those 100 held a prospect reply that we had since answered, so
        the thread's `lastMessageSender` was ME and reading only the summary
        would have missed the reply entirely
      - `sender` takes exactly two values, ME and CORRESPONDENT. Anything else
        is unknown and is dropped rather than assumed inbound

    So one event is emitted per message the prospect sent, keyed by thread and
    that message's own timestamp.

    Identity comes from `correspondentProfile.profileUrl` and `linkedin_id`:
    `customFields` was empty on all 100, and no campaign id appears on a
    conversation at all.
    """
    rows = payload.get("items") if isinstance(payload, dict) else payload
    if rows is None and isinstance(payload, dict):
        rows = payload.get("events")          # a webhook batch
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue

        # A webhook-shaped item names its own event; a conversation does not.
        declared = str(row.get("eventType") or "").strip().lower().replace(" ", "_")
        if declared:
            if declared in ("connection_accepted", "connectionaccepted"):
                event_type = events.LINKEDIN_CONNECTED
            elif declared in ("message_reply", "replied", "reply"):
                event_type = events.REPLY_RECEIVED
            else:
                continue
            out.append(_heyreach_event(row, event_type,
                                       stamp=row.get("timestamp"),
                                       text=_body(row, "text", "message", "body")))
            continue

        for message in heyreach.inbound_messages(row):
            out.append(_heyreach_event(
                row, events.REPLY_RECEIVED,
                stamp=message.get("createdAt") or row.get("lastMessageAt"),
                text=_body(message, "body", "text", "message")))
    return out


def _heyreach_event(row, event_type, stamp=None, text=""):
    """One neutral event from a conversation and one of its messages."""
    custom = _custom(row, "customUserFields", "custom_fields", "customFields")
    profile = row.get("correspondentProfile")
    profile = profile if isinstance(profile, dict) else {}
    thread = row.get("id") or row.get("conversationId")
    stamp = stamp or ""
    return events.neutral(
        type=event_type,
        channel=LINKEDIN,
        provider="heyreach",
        # Thread plus the message's own timestamp: a thread id alone would
        # collapse two replies in one conversation into a single event.
        provider_event_id=f"heyreach:{thread}:{stamp}",
        record_id=custom.get("record_id"),
        contact_key=custom.get("contact_key"),
        client=custom.get("client"),
        linkedin=(row.get("profileUrl") or profile.get("profileUrl")
                  or profile.get("linkedInUrl")),
        at=stamp or None,
        text=text,
        # Always None on a conversation: no campaign id is exposed there.
        external_campaign_id=row.get("campaignId"),
        linkedin_account_id=row.get("linkedInAccountId"),
    )


ADAPTERS = {"emailbison": from_emailbison, "heyreach": from_heyreach}
