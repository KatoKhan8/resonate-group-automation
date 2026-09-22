#!/usr/bin/env python3
"""What a client is shown, as opposed to what the system holds.

OPERATOR, 2026-09-22, after the first live answer in a client channel. Four
of the six faults in it were the same fault: **the material handed to the
model was internal material**, and the model wrote it down faithfully.

    said to a client                     should have been
    ------------------------------------ ----------------------------------
    "lokalno je upisano 724 leada         151, the provider's own membership
     na 643 računa"                       across 491-498
    "13:03 i 13:55 (UTC)"                 15:03 and 15:55 CEST
    "US-hours kontrolne kampanje"         an email campaign
    "prvi mailovi su prošli"              nothing has sent on this batch yet

None of those is a wording problem and none is fixable in a prompt. A model
told "do not say UTC" still cannot produce Zagreb time from a UTC string,
and a model handed 724 has no way to know the number is the wrong one. So
the numbers, the times and the labels are corrected HERE, before the
material is built, and the model is left with nothing wrong to repeat.

## THE ENROLLED NUMBER IS THE PROVIDER'S

`724 leads on 643 accounts` is the local store's enrolled state across
everything it has ever staged for this workspace. The client asked about
the batch that is live. The provider knows exactly how many leads each
campaign holds - `campaign_lead_count` reads `meta.total` and refuses to
count a page - and that is 151 across 491-498.

A client-facing enrolled figure is a sum of provider membership or it is
absent. It is never the local store's, in any phrasing.
"""
import datetime
import re

#: Where a workspace's people live, when nothing better is configured.
#: Not a guess about a reader: it is the timezone the workspace's own
#: sending window is written in, and if that is missing there is no local
#: time to give and the answer says UTC honestly.
DEFAULT_ZONE = None

_ISO = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?"
    r"(?:Z|[+-]\d{2}:?\d{2})?")


def zone_for(entry):
    """The timezone a workspace's times should be read in, or None.

    Taken from its own `sending_window.timezone` - the zone its mail is
    already scheduled against - rather than from a guess about where the
    reader sits.
    """
    if not isinstance(entry, dict):
        return None
    sending = entry.get("sending") or {}
    return (sending.get("timezone") or "").strip() or None


def _parse(text):
    body = str(text or "").strip()
    if not body:
        return None
    try:
        stamp = datetime.datetime.fromisoformat(body.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=datetime.timezone.utc)
    return stamp


def in_zone(value, zone):
    """`"15:03 CEST"`-shaped, or the original when it cannot be converted.

    Returns the input unchanged rather than raising or guessing. A time
    this cannot parse is somebody else's string and is left alone.
    """
    if not zone:
        return value
    stamp = _parse(value)
    if stamp is None:
        return value
    try:
        from zoneinfo import ZoneInfo
        local = stamp.astimezone(ZoneInfo(zone))
    except Exception:                                           # noqa: BLE001
        return value
    return local.strftime("%Y-%m-%d %H:%M %Z")


def localise(value, zone):
    """Every ISO timestamp inside a string or structure, in `zone`.

    Walks dicts and lists because a readback carries times at every depth,
    and a client should not meet one in UTC because it happened to be
    nested.
    """
    if not zone:
        return value
    if isinstance(value, dict):
        return {k: localise(v, zone) for k, v in value.items()}
    if isinstance(value, list):
        return [localise(v, zone) for v in value]
    if not isinstance(value, str):
        return value
    if _ISO.fullmatch(value.strip()):
        return in_zone(value, zone)
    return _ISO.sub(lambda m: in_zone(m.group(0), zone), value)


# ----------------------------------------------------------- the labels

#: Words inside a campaign's own name that are Resonate's shorthand for how
#: it is run, not a description of the client's outreach. A client hearing
#: "the US-hours control campaign" learns our experiment design.
INTERNAL_LABEL_WORDS = (
    "control", "kontroln", "canary", "cohort", "kohort", "batch",
    "us-hours", "zagreb-hours", "eu-hours", "liheavy", "li-heavy",
    "variant", "arm", "test", "holdout", "pilot",
    # 2026-09-22, found writing the operator's "a client channel never
    # receives an internal campaign name" test. This list decides whether
    # `slackagenttools._plain_labels` rewrites a name AT ALL, so a name it
    # does not recognise reaches a client VERBATIM.
    #
    # All 37 live HeyReach campaigns are named
    # `RESONATE <CLIENT> LI B1 SEAT <provider seat id>` and not one word of
    # that was on this list - "B1" is not "batch". So the seat id was
    # reaching client answers inside the campaign's own name, which is
    # exactly what increment 2 decided a client channel never carries: it
    # gives counts of seats and never attributes one.
    #
    # `resonate` goes on with it. Our own name at the head of a campaign
    # tells a client how we organise our estate, not how their outreach is
    # running, and it is the other half of every one of those 37 names.
    #
)

#: SHAPES rather than words, for the same job.
#:
#: `seat` was first added to the word list above and that was wrong, caught
#: by three existing tests in the same run. `_plain_labels` rewrites ANY
#: dict key called `name` whose value this function flags - not only a
#: campaign's - so the bare word turned a client's own sender, whose name
#: contains "seat-holder" in the fixtures, into "email campaign". A client
#: seeing their own sender named is the rule increment 2 established; I had
#: just deleted it.
#:
#: The leak is the provider SEAT ID, not the word, so this matches the id's
#: shape and nothing else. `resonate` came off the word list with it: our
#: own name at the head of a campaign tells a client nothing they do not
#: know, and the seat shape already catches every one of those names.
INTERNAL_LABEL_PATTERNS = (
    r"\bseat\s+\d{3,}\b",
    r"\bseat[-_]?id\b",
)

_LABEL = re.compile(r"\b(?:%s)\w*\b"
                    % "|".join(INTERNAL_LABEL_WORDS), re.I)

_LABEL_SHAPE = re.compile("|".join(INTERNAL_LABEL_PATTERNS), re.I)


def plain_campaign_label(name, campaign_id=None):
    """A campaign as a client should hear it named.

    `RESONATE - PRODUCTIVE - EMAIL - US-HOURS - CONTROL - COHORT B` says
    four internal things and one useful one. What survives is the channel
    and the id; the experiment design does not.
    """
    text = str(name or "")
    channel = "LinkedIn" if re.search(r"\bli(nkedin)?\b", text, re.I) \
        else "email"
    if campaign_id:
        return "%s campaign %s" % (channel, campaign_id)
    return "%s campaign" % channel


def carries_internal_label(name):
    text = str(name or "")
    return bool(_LABEL.search(text) or _LABEL_SHAPE.search(text))
