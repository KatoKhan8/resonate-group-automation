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

#: EmailBison lead ids, both created 2026-09-23 for the stop test.
#:
#: 204966 is the FIRST test lead. It was stopped in 491 once the first test
#: concluded, and there is no un-stop route - `stop_contact` correctly treats
#: an already-stopped lead as a no-op, so it can never again be the subject of
#: a measurable stop. 204967 is the second, created and attached to 491 for
#: the operator's re-run. Both stay here permanently: the exclusion is about
#: who this is, not about which test is current.
LEAD_IDS = frozenset({204966, 204967, 205079, 205081})
#:
#: 205079 was created 2026-09-24 late on `zvonimir@resonategroup.co` for the
#: email->LinkedIn direction of the stop measurement, and adding it here was
#: NOT optional bookkeeping. `matches(205079)` was False the moment the lead
#: existed, and an EmailBison event is the one input that can arrive carrying
#: the lead id and nothing else - no address, no contact key. So the
#: operator's own test reply would have been counted as a prospect reply and
#: been eligible for the client channel: the exact outcome of the 09-23
#: misspelled-domain incident, reproduced by the fix for it. Checked by
#: asserting on the id ALONE rather than on the row that also carries the
#: address, because the row always passes.
#:
#: 205081 joined it minutes later, on `zvonimir+stoptest@resonategroup.co`.
#: EmailBison REFUSES a lead in two campaigns (422, "either in another
#: campaign"), so the dedicated 24h test campaign 501 needed its own lead and
#: 205079 could not be moved. Same reasoning as 205079: the id alone must
#: match, because an EmailBison event can carry nothing else.

#: The LinkedIn profile, matched case-insensitively on the vanity segment so
#: `/in/zbeslic`, the full https URL and a trailing slash all resolve.
LINKEDIN_SLUGS = frozenset({"zbeslic"})

#: The addresses on the EmailBison leads. The plus-addressed ones exist
#: because the provider holds 204966 against the bare address already.
#:
#: BOTH DOMAINS, AND THE SECOND IS THE REAL ONE. Leads 204966 and 204967 were
#: created on `resonate.co` - confirmed against the provider 2026-09-24 - and
#: the operator's actual address is on `resonategroup.co`. The wrong domain
#: was recorded here on 2026-09-23 and nothing noticed, because no test reply
#: had arrived since.
#:
#: WHAT IT WOULD HAVE COST, had it not been caught before tonight's
#: measurement: `notify.py` calls `testidentity.matches` to SUPPRESS anything
#: about this identity, so the operator's own test reply is never counted as
#: a prospect reply nor surfaced to the client. A reply from
#: `resonategroup.co` matched nothing, so it would have been treated as a
#: real prospect replying - counted in the reply figures, and eligible to
#: reach a client channel. That is the exact outcome this module exists to
#: prevent, and the identity it was protecting was misspelled.
#:
#: The `resonate.co` entries STAY. The leads at the provider carry them, so
#: removing them would un-suppress the two leads this module was written for.
EMAILS = frozenset({"zvonimir@resonate.co",
                    "zvonimir+stoptest2@resonate.co",
                    "zvonimir@resonategroup.co",
                    "zvonimir+stoptest@resonategroup.co",
                    "zvonimir+stoptest2@resonategroup.co"})

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
