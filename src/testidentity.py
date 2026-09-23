"""The operator's own test identity, named once, excluded everywhere.

OPERATOR INSTRUCTION, Zvonimir, 2026-09-23. `/in/zbeslic` and EmailBison lead
204966 are the cross-channel stop TEST identity. They are excluded from every
reply count, report and client figure, **now and permanently**.

WHY THIS IS A MODULE AND NOT A CHECK AT ONE CALL SITE.

On 2026-09-23 the operator replied to their own LinkedIn profile three times
to exercise the cross-channel stop. Each reply is a real provider event and
each one is ingested exactly like a prospect's. The first produced a
`positive_reply` notification routed to **C0BFUF4JRK9, Productive's own
channel** - the client would have been told a prospect was interested when
the "prospect" was the operator testing a stop. That one was suppressed by
hand. Nothing stopped the next one, because a hand-edit is not a mechanism.

Two places have to consult this and they fail in opposite directions, which
is why both are covered here rather than one being trusted to imply the other:

  the WRITE   `notify.plan` - so no future notification for this identity is
              ever given a channel. Recorded as SUPPRESSED with a reason
              rather than dropped, because a notification that silently does
              not exist is indistinguishable from one nobody built.
  the READ    the reply counts - so the rows ALREADY written, including the
              15:57:01Z one, never reach a figure. Suppressing at the write
              does nothing about history.

THE MATCH IS ON ANY BINDING, DELIBERATELY. A reply reaches the notification
layer carrying whichever identifiers its provider happened to supply - a
record id from the local store, a contact key, a lead id from EmailBison, a
profile URL from HeyReach. Requiring a particular one would mean the
exclusion holds on the path that was tested and fails on the path that was
not. Any one of them is proof enough that this is the operator's test.

This is an exclusion from COUNTS AND CLIENT-FACING REPORTS. It is not a
suppression of the person and not a DNC - those are recorded on the record
itself (`state=do_not_contact`, 2026-09-23). A future session must not read
this module as the reason the lead is stopped.
"""

#: The local record created for the test, 2026-09-23.
RECORD_IDS = frozenset({"crosschannel-stop-test-2026-09-23"})

#: The contact key that record carries.
CONTACT_KEYS = frozenset({"zvonimir-beslic"})

#: EmailBison lead id, created 2026-09-23 and attached to campaign 491.
LEAD_IDS = frozenset({204966})

#: The LinkedIn profile, matched case-insensitively on the vanity segment so
#: `/in/zbeslic`, the full https URL and a trailing slash all resolve.
LINKEDIN_SLUGS = frozenset({"zbeslic"})

#: The address on the EmailBison lead.
EMAILS = frozenset({"zvonimir@resonate.co"})

WHY = ("operator instruction 2026-09-23: /in/zbeslic and lead 204966 are the "
       "cross-channel stop TEST identity and are excluded from every reply "
       "count, report and client figure")


def _slug(value):
    """The vanity segment of a LinkedIn URL, or None.

    Tolerates the three shapes this estate actually stores: a bare
    `/in/zbeslic`, a full `https://www.linkedin.com/in/zbeslic`, and either
    with a trailing slash or a query string.
    """
    text = str(value or "").strip().lower()
    if "/in/" not in text:
        return None
    tail = text.split("/in/", 1)[1]
    for cut in ("/", "?", "#"):
        tail = tail.split(cut, 1)[0]
    return tail or None


def matches(*values, **fields):
    """True when any value or field names the test identity.

    Accepts loose input on purpose - a mix of ids, dicts, None and strings -
    because the callers are counting loops that hold whatever shape their
    provider gave them. It answers a yes/no question and never raises.
    """
    seen = []
    for value in values:
        if isinstance(value, dict):
            seen.extend(value.values())
        elif isinstance(value, (list, tuple, set, frozenset)):
            seen.extend(value)
        else:
            seen.append(value)
    seen.extend(fields.values())

    for value in seen:
        if value is None:
            continue
        if isinstance(value, dict):
            if matches(value):
                return True
            continue
        text = str(value).strip()
        if not text:
            continue
        if text in RECORD_IDS or text in CONTACT_KEYS:
            return True
        if text.lower() in EMAILS:
            return True
        if _slug(text) in LINKEDIN_SLUGS:
            return True
        try:
            if int(text) in LEAD_IDS:
                return True
        except (TypeError, ValueError):
            pass
    return False
